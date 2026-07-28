# Auditoria técnica — Meta/Instagram Graph API do Zenit Dashboard

## Veredito executivo

**Hoje o sistema não consegue garantir “100% orgânico isolado, sem duplicidade e sem mistura”.** Existem acertos importantes — principalmente a separação da Marketing API por `publisher_platform=instagram` —, mas há problemas conceituais e técnicos que contaminam os números:

1. Métricas orgânicas de mídia são tratadas como se estivessem limitadas ao filtro de datas, mas normalmente representam o acumulado da publicação.
2. `like_count`, `comments_count` e métricas pagas são somadas, embora possam se referir à mesma interação.
3. Alcances únicos são somados entre posts, anúncios e janelas temporais, o que duplica pessoas.
4. A conta tenta obter orgânico por `total - pago`, mas as duas APIs não garantem a mesma população, janela, atribuição ou definição.
5. Vários `action_type` da Ads Insights API são sobrepostos e estão sendo somados ou escolhidos por heurística.
6. Há fields de mídia provavelmente inválidos em `/media`, como `saved_count`, `shares_count` e `reposts_count`.
7. Métricas incompatíveis são enviadas juntas; uma única inválida faz a chamada inteira falhar.
8. A UI faz afirmações como “100% orgânico” e “100% precisão real” que o contrato das APIs não sustenta.

A arquitetura confiável deve manter três conjuntos separados:

- **Instagram Insights**, com o nome e a semântica retornados pela Instagram Graph API;
- **Meta Ads Insights**, exclusivamente pagos;
- **Estimativas/resíduos**, claramente marcados como aproximações, nunca como dado puro.

---

# 1. O maior problema: filtro por data da publicação não filtra a métrica orgânica

Em `get_recent_media()`, o código usa:

```http
GET /{ig-user-id}/media?since=...&until=...
```

Isso filtra **quais publicações foram criadas no período**.

Depois chama:

```http
GET /{ig-media-id}/insights?metric=reach,saved,shares,...
```

Esses insights de mídia, em regra, não ficam limitados pelo `since/until` usado em `/media`. Portanto, se o usuário selecionar 1º a 30 de junho:

- o sistema seleciona posts publicados entre 1º e 30 de junho;
- mas pode mostrar o acumulado desses posts até o momento da consulta;
- enquanto Ads Insights usa exatamente o período solicitado.

Assim, orgânico e pago podem estar em janelas diferentes.

## Correção

Renomeie a apresentação para algo como:

> “Métricas atuais/acumuladas das publicações criadas no período”.

Para ter métricas orgânicas realmente limitadas por data, é necessário armazenar snapshots próprios:

```text
instagram_media_daily_snapshot
- media_id
- snapshot_date
- reach
- views
- saved
- shares
- like_count
- comments_count
```

Então calcule deltas:

```python
valor_no_periodo = snapshot_final - snapshot_anterior_ao_inicio
```

Mesmo isso exige cuidado: `reach` é uma métrica única/estimada e o delta não significa necessariamente “novas pessoas únicas no período”. Para contadores cumulativos, como salvamentos, curtidas e comentários, o delta é mais defensável.

---

# 2. Fields incorretos no endpoint `/media`

O código pede:

```python
"fields": (
    "id,caption,media_url,thumbnail_url,permalink,timestamp,"
    "like_count,comments_count,saved_count,shares_count,reposts_count,"
    "media_type,media_product_type"
)
```

Os fields confiáveis para o objeto de mídia são, em geral:

```text
id
caption
media_url
thumbnail_url
permalink
timestamp
like_count
comments_count
media_type
media_product_type
```

`save`, `share` e métricas semelhantes devem ser buscadas em:

```http
GET /v25.0/{ig-media-id}/insights
```

Não presuma que estes sejam fields do objeto:

```text
saved_count
shares_count
reposts_count
```

Um field inválido pode invalidar a consulta inteira de `/media`, não apenas retornar zero.

## Chamada recomendada

```http
GET /v25.0/{ig-user-id}/media
  ?fields=id,caption,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count,media_type,media_product_type
  &limit=100
```

Depois, por mídia:

### Reels

```http
GET /v25.0/{ig-media-id}/insights
  ?metric=reach,views,saved,shares,total_interactions,ig_reels_video_view_total_time,ig_reels_avg_watch_time
```

### Feed/carrossel

```http
GET /v25.0/{ig-media-id}/insights
  ?metric=reach,views,saved,shares,total_interactions
```

Métricas como `profile_activity`, `profile_visits` e `follows` devem ser consultadas separadamente e somente quando forem suportadas para aquele tipo de mídia.

## Não envie todas as métricas em uma requisição única

Faça grupos compatíveis:

```python
METRICS_BY_PRODUCT = {
    "REELS": [
        "reach",
        "views",
        "saved",
        "shares",
        "total_interactions",
        "ig_reels_video_view_total_time",
        "ig_reels_avg_watch_time",
    ],
    "FEED": [
        "reach",
        "views",
        "saved",
        "shares",
        "total_interactions",
    ],
}
```

Se uma métrica opcional falhar, consulte-a individualmente. Não use fallback com várias métricas antigas.

---

# 3. O fallback `engagement,impressions,reach,saved` é perigoso

Atualmente:

```python
metrics = "engagement,impressions,reach,saved"
```

`engagement` e `impressions` são métricas antigas/depreciadas ou incompatíveis em diversos contextos da Instagram Insights API moderna. Como estão agrupadas, uma única métrica inválida pode fazer o fallback inteiro falhar.

O ultra-fallback com apenas `reach` evita o crash, mas transforma falha de API em zeros silenciosos para as outras métricas.

## Correção

- Use `views` em vez de `impressions` onde a documentação da versão aplicável exigir.
- Use `total_interactions` em vez de `engagement`.
- Registre indisponibilidade como `None`, não como zero.

Exemplo:

```python
{
    "reach": 1200,
    "saved": None,
    "shares": None,
    "_errors": {
        "saved": "metric not supported for media type"
    }
}
```

**Zero significa valor medido igual a zero. `None` significa que não foi possível medir.** O dashboard hoje mistura os dois casos.

---

# 4. `like_count` não deve ser somado com `paid_likes`

Hoje existe:

```python
@property
def total_likes(self) -> int:
    return self.like_count + self.paid_likes
```

Isso pode duplicar interações.

Em publicações existentes usadas em anúncios, as interações geradas pelo anúncio podem compor o social proof visível da própria publicação. Portanto, `like_count` e `actions` da Marketing API não são necessariamente conjuntos disjuntos.

O mesmo problema existe em:

```python
total_shares = shares_count + paid_shares
total_saved = saved_count + paid_saved
```

## Regra segura

Mostre separadamente:

- `like_count`: contador atual do objeto Instagram;
- `paid_post_reactions`: ações atribuídas aos anúncios no período;
- não calcule `total_likes = like_count + paid_likes`.

Exemplo de nomenclatura correta:

| Campo | Nome exibido |
|---|---|
| `like_count` | Curtidas atuais da publicação |
| Ads `post_reaction` | Reações atribuídas aos anúncios no período |
| Ads `onsite_conversion.post_net_like` | Curtidas líquidas atribuídas aos anúncios |
| Soma | Não calcular |

Também remova afirmações “Curtidas orgânicas” para `like_count`. O nome correto é:

> “Curtidas atuais da publicação”

A Meta não fornece um breakdown universal e confiável `organic/paid` para o contador social atual da publicação.

---

# 5. Não existe “subtração mágica” confiável para alcance

O código faz:

```python
r_org = max(0, r_tot - r_paid)
```

Isso só seria matematicamente válido se:

- `r_tot` e `r_paid` tivessem a mesma definição;
- a mesma janela;
- o mesmo timezone;
- a mesma identidade de usuário;
- a mesma deduplicação;
- a mesma superfície;
- o total contivesse exatamente o pago como subconjunto.

A Graph API não garante isso.

Exemplo:

- total Instagram reach: 1.000 contas;
- paid reach: 400 contas;
- 200 dessas 400 também viram organicamente.

O alcance orgânico único pode ser 800, não 600. A operação:

```text
1.000 - 400 = 600
```

remove também a sobreposição entre orgânico e pago.

## Regra correta

Apresente:

```text
Alcance reportado pelo Instagram Insights: 1.000
Alcance pago reportado pelo Ads Insights: 400
```

Não apresente:

```text
Alcance orgânico puro: 600
```

A menos que a documentação da métrica específica declare explicitamente que o endpoint retorna apenas orgânico.

Mesmo nesse caso, mantenha datasets separados. Não some:

```python
organic_reach + paid_reach
```

porque alcance representa pessoas únicas e pode haver sobreposição.

## Alteração obrigatória na UI

Remover ou corrigir:

```python
"Subtração Mágica"
"100% Orgânico"
"Alcance Total = Orgânico + Pago"
"removemos duplicidades da Meta para garantir 100% de precisão real"
```

Sugestão:

> “Os dados de Instagram Insights e Ads Insights são exibidos separadamente. Métricas de alcance não são somadas, pois podem compartilhar as mesmas pessoas.”

---

# 6. Alcance não pode ser somado entre posts, anúncios ou chunks

## Problema por publicação

```python
total_organic_reach = sum(m.organic_reach for m in media_list)
total_paid_reach = sum(m.paid_reach for m in media_list)
```

Uma pessoa que viu três posts é contada três vezes. Isso não é alcance único da conta.

O nome correto seria:

> “Soma do alcance reportado por publicação”

Não:

> “Pessoas alcançadas”

## Problema em `get_account_insights()`

O código divide o período em chunks e soma:

```python
results[name] += val
```

Isso é inválido para métricas únicas como:

- `reach`;
- `accounts_engaged`;
- eventualmente outros totalizadores baseados em contas únicas.

Uma pessoa alcançada em dois chunks será contada duas vezes.

## Correção

### Para até a janela suportada

Faça uma única requisição para o intervalo completo:

```http
GET /v25.0/{ig-user-id}/insights
  ?metric=reach,accounts_engaged
  &metric_type=total_value
  &since=...
  &until=...
```

### Para intervalos maiores que o permitido

Não existe forma de reconstruir alcance único global somando chunks.

Retorne:

```python
{
    "reach": None,
    "reach_reason": "intervalo excede a janela máxima de deduplicação da API",
    "summed_period_reach": 12345
}
```

E exiba como:

> “Soma dos alcances das janelas”, não “alcance único”.

Métricas aditivas, como comentários ou salvamentos ocorridos, podem ser somadas quando a definição da API for realmente por evento e as janelas não se sobrepuserem.

---

# 7. Paid reach: endpoint correto para deduplicação

## Total pago do Instagram

A abordagem conceitualmente correta é consultar no nível agregado:

```http
GET /v25.0/act_{ad-account-id}/insights
  ?level=account
  &fields=reach,impressions,spend
  &breakdowns=publisher_platform
  &time_range={"since":"2026-07-01","until":"2026-07-28"}
```

Depois selecionar:

```python
item["publisher_platform"] == "instagram"
```

Isso é muito melhor que somar `reach` de anúncios individuais.

## Paid reach por publicação promovida por múltiplos anúncios

Não some:

```python
reach_post = sum(reach_de_cada_ad)
```

Agrupe os `ad_id` ligados ao mesmo `source_instagram_media_id` e faça uma nova consulta agregada para o conjunto:

```http
GET /v25.0/act_{ad-account-id}/insights
  ?level=account
  &fields=reach,impressions,spend,actions
  &breakdowns=publisher_platform
  &filtering=[{"field":"ad.id","operator":"IN","value":["AD1","AD2"]}]
  &time_range={"since":"2026-07-01","until":"2026-07-28"}
```

Então use somente a linha:

```text
publisher_platform = instagram
```

Isso permite que a Meta faça a deduplicação de `reach` dentro daquele conjunto de anúncios.

## Problema no uso atual de `summary`

O código usa:

```python
"summary": '["reach"]'
```

Não é seguro assumir que esse `summary.reach` represente alcance deduplicado do conjunto filtrado. Dependendo do contrato da versão, o parâmetro pode ser ignorado, inválido ou produzir um summary diferente do esperado.

Prefira uma linha agregada via `level=account` com filtro pelos `ad.id`.

Mesmo assim:

- alcance de cada post pode ser deduplicado dentro do grupo de anúncios daquele post;
- a soma do alcance de vários posts continua não sendo alcance único da conta.

---

# 8. `actions` contém métricas hierárquicas e sobrepostas

A Ads Insights API frequentemente retorna ações agregadas e subtipos. Hoje o código mistura ou soma tipos que podem se sobrepor.

## Leads

Atualmente:

```python
if act_type == "lead":
    site_leads += val
elif act_type == "leadgen":
    native_leads += val

leads = site_leads + native_leads
```

`lead` pode ser um total agregado que já contenha subtipos de lead. Somá-lo com uma ação nativa pode duplicar conversões.

Além disso, `leadgen` isolado não deve ser presumido como o action type atual para todas as contas.

## Estratégia correta

Escolha uma das duas abordagens.

### A. Total de leads compatível com Ads Manager

Use somente o action type agregado correspondente à coluna configurada no Ads Manager, por exemplo `lead`, se ele estiver presente e for o total oficial desejado.

```python
total_leads = action_value(actions, "lead")
```

Não some com subtipos.

### B. Separação por origem

Use action types mutuamente exclusivos observados na resposta real da conta, por exemplo:

```text
onsite_conversion.lead_grouped
onsite_conversion.leadgen_grouped
offsite_conversion.fb_pixel_lead
```

Os nomes disponíveis dependem da configuração, pixel/dataset, formulário e versão. Deve haver uma allowlist por conta, validada contra uma exportação do Ads Manager.

Exemplo:

```python
NATIVE_LEAD_TYPES = {
    "onsite_conversion.lead_grouped",
    "onsite_conversion.leadgen_grouped",
}

SITE_LEAD_TYPES = {
    "offsite_conversion.fb_pixel_lead",
}
```

Nunca some `lead` agregado com esses subtipos.

## WhatsApp/mensagens

Hoje:

```python
act_type.startswith("onsite_conversion.messaging_conversation_started")
```

Esse prefixo pode capturar mais de uma variante da mesma ação e somá-las.

Use um action type canônico, validado na conta, por exemplo:

```text
onsite_conversion.messaging_conversation_started_7d
```

Não some variantes de janelas distintas.

## Curtidas

Hoje há prioridade:

```python
like_priority = {
    "onsite_conversion.post_net_like": 3,
    "like": 2,
    "post_reaction": 1,
}
```

Essas métricas não são equivalentes:

- `post_reaction`: reações atribuídas;
- `onsite_conversion.post_net_like`: curtidas líquidas;
- `like`: pode ter semântica diferente conforme objeto/contexto.

Escolha uma definição e mantenha-a:

```python
paid_reactions = action_value(actions, "post_reaction")
paid_net_likes = action_value(actions, "onsite_conversion.post_net_like")
```

Não substitua uma pela outra por prioridade. Exiba-as separadamente se ambas forem relevantes.

---

# 9. Cliques estão sendo recalculados incorretamente

O código faz:

```python
clicks = link_clicks + profile_visits + other_clicks
```

E define:

```python
other_clicks = post_interaction_gross
```

`post_interaction_gross` não significa “cliques no criativo”. Pode incluir engajamentos como reações, comentários, compartilhamentos e outras interações.

Portanto:

```text
link_click + profile_visit + post_interaction_gross
```

não é “total de cliques”.

## Fields corretos para Ads Insights

Solicite explicitamente:

```text
clicks
inline_link_clicks
outbound_clicks
unique_outbound_clicks
actions
```

Exemplo:

```http
GET /v25.0/act_{ad-account-id}/insights
  ?level=ad
  &fields=ad_id,ad_name,spend,impressions,reach,clicks,inline_link_clicks,outbound_clicks,unique_outbound_clicks,actions
```

Use:

- `clicks`: todos os cliques reportados pela Meta;
- `inline_link_clicks`: cliques em links no anúncio;
- `outbound_clicks`: cliques que levam para fora das propriedades da Meta;
- `profile_visits`: ação específica, se retornada;
- `post_engagement`: engajamento, não clique.

Não sobrescreva `clicks` recebido da API.

Se desejar “outros cliques”:

```python
other_clicks_estimated = max(0, clicks - inline_link_clicks)
```

Ainda assim, nomeie como estimativa e não subtraia visitas ao perfil sem provar que elas estão contidas no mesmo total.

Também não trate `outbound_clicks` como sinônimo de `link_clicks`; são definições diferentes.

---

# 10. Parâmetros necessários para paridade com Ads Manager

Para evitar diferenças de atribuição, as chamadas pagas devem definir ou registrar:

```text
action_report_time
use_unified_attribution_setting
action_attribution_windows
time_increment
timezone da conta
```

Recomendação inicial:

```python
params = {
    "level": "ad",
    "fields": (
        "ad_id,ad_name,campaign_id,campaign_name,objective,"
        "spend,reach,impressions,frequency,clicks,inline_link_clicks,"
        "outbound_clicks,unique_outbound_clicks,actions,action_values"
    ),
    "breakdowns": "publisher_platform",
    "action_breakdowns": "action_type",
    "action_report_time": "impression",
    "use_unified_attribution_setting": "true",
    "limit": "1000",
}
```

Observações:

- Para reproduzir exatamente uma coluna do Ads Manager, use a mesma janela de atribuição daquela visualização.
- `action_report_time=impression` associa a conversão à impressão; `conversion` associa à data da conversão. Escolha conscientemente.
- Congele a semântica em configuração, em vez de depender do default da conta.
- Conversões atribuídas não são necessariamente “ocorridas dentro do Instagram”, mesmo quando a impressão veio de placement Instagram.

---

# 11. Isolamento por placement do Instagram

Para entrega paga do Instagram, use:

```text
breakdowns=publisher_platform
```

e filtre:

```text
publisher_platform=instagram
```

Se precisar separar Feed, Stories e Reels:

```text
breakdowns=publisher_platform,platform_position
```

Exemplo:

```http
GET /v25.0/act_{ad-account-id}/insights
  ?level=ad
  &fields=ad_id,reach,impressions,spend,clicks,inline_link_clicks,actions
  &breakdowns=publisher_platform,platform_position
```

Isso permite distinguir, conforme os valores efetivamente retornados:

```text
instagram / feed
instagram / story
instagram / reels
instagram / explore
```

Não misture `facebook`, `audience_network`, `messenger` e `instagram` antes de calcular métricas.

### Importante

`publisher_platform=instagram` isola a **entrega paga em placements Instagram**. Não significa automaticamente que toda conversão ocorreu dentro do Instagram. A conversão pode acontecer em site, app ou WhatsApp depois da impressão/clique.

---

# 12. Mapeamento entre anúncio e publicação Instagram

A ordem atual é razoável:

```python
source_instagram_media_id
or effective_instagram_media_id
or effective_instagram_story_id
```

Mas os significados precisam ser preservados:

- `source_instagram_media_id`: publicação original usada pelo anúncio;
- `effective_instagram_media_id`: mídia efetiva do criativo;
- `effective_instagram_story_id`: objeto efetivo relacionado ao Story.

Não trate todo `effective_instagram_media_id` como publicação orgânica existente. Ele pode representar mídia criada especificamente para anúncio/dark post.

## Estrutura recomendada

```python
{
    "source_instagram_media_id": "...",
    "effective_instagram_media_id": "...",
    "effective_instagram_story_id": "...",
    "mapping_type": "existing_post" | "dark_post" | "story"
}
```

Somente associe a uma mídia retornada por:

```http
/{ig-user-id}/media
```

quando o ID realmente corresponder.

Dark posts devem aparecer apenas no dataset pago, não ser forçados para a tabela orgânica.

---

# 13. Account Insights não deve ser chamado com todas as métricas juntas

Atualmente:

```python
metrics_list = (
    "profile_links_taps,website_clicks,profile_views,reach,"
    "total_interactions,accounts_engaged,likes,comments,shares,saves"
)
```

Se uma única métrica estiver depreciada ou indisponível para aquela conta, a consulta inteira pode falhar e o código devolve zeros.

`website_clicks` deve ser especialmente validado porque métricas de perfil foram alteradas ao longo das versões.

## Divisão recomendada

### Métricas aditivas de interação

```http
GET /{ig-user-id}/insights
  ?metric=likes,comments,shares,saves,total_interactions
  &metric_type=total_value
  &since=...
  &until=...
```

### Métricas únicas

```http
GET /{ig-user-id}/insights
  ?metric=reach,accounts_engaged
  &metric_type=total_value
  &since=...
  &until=...
```

### Perfil

```http
GET /{ig-user-id}/insights
  ?metric=profile_views,profile_links_taps
  &metric_type=total_value
  &since=...
  &until=...
```

Consulte `website_clicks` separadamente apenas se o endpoint da versão e o tipo da conta confirmarem suporte.

---

# 14. Visitas ao perfil e cliques no link não são “100% orgânicos”

A UI declara:

```python
st.markdown("#### 👤 Exceções e Ações (100% Orgânico)")
```

e inclui:

```text
Visitas ao Perfil
Toques no Link
Cliques no Site
Contas Engajadas
```

Essa afirmação não é segura.

Anúncios podem:

- levar ao perfil;
- gerar visita ao perfil;
- provocar clique no link da bio;
- gerar engajamento na conta.

A menos que a documentação da métrica diga explicitamente “organic only”, exiba:

> “Métricas reportadas pelo Instagram Insights”

Não:

> “100% orgânico”.

---

# 15. Seguidores: `follower_count` e `follows_and_unfollows`

O método:

```python
get_followers_history()
```

rotula `follower_count` como novos seguidores diários. Essa semântica precisa ser validada para a versão e a conta; não deve ser tratada como histórico do total de seguidores sem confirmação.

Já `follows_and_unfollows` pode retornar breakdown, e não necessariamente um inteiro simples.

## Chamada recomendada para entradas e saídas

```http
GET /v25.0/{ig-user-id}/insights
  ?metric=follows_and_unfollows
  &period=day
  &metric_type=total_value
  &breakdown=follow_type
  &since=...
  &until=...
```

Leia:

```text
total_value.breakdowns[].dimension_keys
total_value.breakdowns[].results[]
```

E mantenha:

```python
follows = ...
unfollows = ...
net_follows = follows - unfollows
```

Hoje o código soma cegamente:

```python
results["follows_and_unfollows"] += val_data.get("value", 0)
```

Se `value` for um objeto ou se a métrica representar movimentos separados, o resultado estará incorreto.

Também não chame o campo de “Novos Seguidores” se ele representar saldo líquido.

---

# 16. Stories: métricas antigas devem ser substituídas/isoladas

Atualmente:

```python
metrics = "reach,exits,replies,taps_forward,taps_back"
```

`exits`, `taps_forward` e `taps_back` tiveram alterações/depreciações em versões recentes. O modelo mais atual tende a usar uma métrica agregada de navegação com breakdown da ação.

Faça duas chamadas:

### Métricas gerais

```http
GET /v25.0/{story-media-id}/insights
  ?metric=reach,views,replies,shares,total_interactions
```

### Navegação

```http
GET /v25.0/{story-media-id}/insights
  ?metric=navigation
  &metric_type=total_value
  &breakdown=story_navigation_action_type
```

Então mapeie os valores efetivamente retornados, como:

```text
TAP_FORWARD
TAP_BACK
EXIT
SWIPE_FORWARD
```

Não misture a métrica `navigation` com métricas que não aceitam o mesmo `breakdown` na mesma requisição.

Stories também têm retenção limitada. Se quiser histórico, capture os insights enquanto a mídia ainda está disponível e persista em banco.

---

# 17. Demografia orgânica

A estrutura:

```http
GET /{ig-user-id}/insights
  ?metric=follower_demographics
  &period=lifetime
  &metric_type=total_value
  &breakdown=age,gender
```

é conceitualmente adequada.

Também está correto fazer chamadas separadas para:

```text
age,gender
city
country
```

Não some as consultas; cada uma é uma projeção diferente da mesma audiência.

Entretanto, `timeframe` precisa ser validado contra os valores permitidos pela versão da API. Não fixe silenciosamente:

```python
timeframe="this_month"
```

sem tratar erro de parâmetro como indisponibilidade.

Recomendo uma configuração testada por métrica:

```python
DEMOGRAPHIC_CONFIG = {
    "follower_demographics": {
        "period": "lifetime",
        "timeframe": None,
    },
    "engaged_audience_demographics": {
        "period": "lifetime",
        "timeframe": "this_month",
    },
    "reached_audience_demographics": {
        "period": "lifetime",
        "timeframe": "this_month",
    },
}
```

Se a Meta alterar os enums, falhe explicitamente e não retorne gráficos vazios como se fossem zero.

---

# 18. Demografia paga

Somar `impressions` por anúncio é matematicamente aceitável porque impressões são aditivas. Porém, para a visão geral da conta, é mais simples e consistente chamar diretamente:

```http
GET /v25.0/act_{ad-account-id}/insights
  ?level=account
  &fields=impressions,spend
  &breakdowns=age,gender
```

Depois:

```http
...?level=account&fields=impressions,spend&breakdowns=country
```

e:

```http
...?level=account&fields=impressions,spend&breakdowns=region
```

Para separar Instagram de Facebook, tente a combinação suportada:

```text
breakdowns=publisher_platform,age,gender
```

ou faça consultas compatíveis separadas conforme as restrições de breakdown da Ads Insights API.

A tela chama `region` de cidade em alguns pontos:

```python
cities[region] = ...
```

Isso está semanticamente errado. `region` é estado/região, não cidade.

Renomeie:

```python
regions: dict[str, int]
```

e exiba “Estados/Regiões”.

---

# 19. Custo, CPC, CTR e CPA

## `CPP`

O código recalcula:

```python
cpp = (spend / reach) * 1000
```

Confirme a definição desejada. Em Ads Insights, `cpp` é custo por 1.000 pessoas alcançadas. A fórmula é compatível, mas o nome da UI deve ser claro:

> “Custo por 1.000 pessoas alcançadas”

## CPC

Não use:

```python
spend / clicks_reconstruidos
```

Use:

- `cpc` da API para CPC de todos os cliques;
- ou `spend / inline_link_clicks` para CPC de link;
- ou `cost_per_outbound_click` para clique de saída.

São métricas diferentes.

## CPA

O código usa:

```python
cost_per_action_type["post_engagement"]
```

e depois, para multi-ad:

```python
spend / (likes + comments + shares + saved)
```

Essas definições não são equivalentes. `post_engagement` pode conter mais ações do que as quatro listadas.

Escolha uma definição:

```python
cost_per_post_engagement = API cost_per_action_type[post_engagement]
```

ou:

```python
cost_per_selected_interaction = (
    spend / (reactions + comments + shares + saves)
)
```

Use nomes diferentes. Não apresente ambos como “CPA”.

---

# 20. `get_instagram_paid_totals()` usa `max()` incorretamente

Atualmente:

```python
totals["likes"] = max(totals["likes"], val)
```

Isso não é uma estratégia geral de deduplicação. Se houver várias linhas válidas, `max()` pode descartar dados legítimos.

Com:

```text
level=account
breakdowns=publisher_platform
```

deve existir uma linha agregada por plataforma no período. Para a linha `instagram`, atribua diretamente o action type canônico:

```python
totals["post_reactions"] = action_value(actions, "post_reaction")
totals["net_likes"] = action_value(
    actions,
    "onsite_conversion.post_net_like",
)
```

Não trate ambas como a mesma métrica e não escolha a maior.

---

# 21. Comentários: o código não busca “todos”

Cada batch chama:

```http
/{media-id}/comments?...&limit=50
```

mas ignora o `paging.next` dentro de cada resposta. Portanto, são obtidos no máximo 50 comentários por publicação.

Além disso, o método é chamado de:

```python
get_all_comments_for_account
```

o que é enganoso.

## Correção

Para cada mídia:

1. processar a primeira página;
2. seguir `paging.next`;
3. deduplicar por `comment.id`;
4. considerar respostas, se necessárias, através do endpoint apropriado.

```python
comments_by_id[comment["id"]] = comment
```

Também há um bug em `render_top_posts_and_comments()`:

```python
ig_client = InstagramClient()
```

O construtor exige `client_config`.

E o método chamado não existe:

```python
get_top_comment_for_account()
```

---

# 22. Batch API está sem versão efetivamente garantida

O comentário afirma:

```python
# Batch Requests (SEM versão — exigência da Graph API)
BATCH_URL = "https://graph.facebook.com"
```

Isso não deve ser tratado como exigência. Usar a raiz sem versão pode fazer o batch depender da versão padrão do app, divergindo das requisições normais em `v25.0`.

Prefira garantir a versão explicitamente, conforme o formato aceito pela API:

```python
BATCH_URL = "https://graph.facebook.com/v25.0"
```

com `relative_url` sem repetir a versão, ou valide a forma aprovada para batch na versão utilizada.

O ponto obrigatório é: **todas as chamadas devem usar a mesma versão**, inclusive batch.

---

# 23. Outros bugs críticos que afetam a confiabilidade

## TLS desabilitado

Todas as chamadas usam:

```python
verify=False
```

Isso desabilita a validação TLS e permite ataques man-in-the-middle. Remova imediatamente:

```python
response = self.session.get(url, params=params, timeout=10)
```

## Erros viram zeros

Há muitos blocos como:

```python
except Exception:
    return []
```

ou métricas default `0`.

Isso faz a UI mostrar “zero” quando houve:

- field inválido;
- token sem permissão;
- rate limit;
- erro de rede;
- métrica não suportada.

Use estado explícito:

```python
class MetricValue(BaseModel):
    value: int | float | None
    status: Literal["ok", "unsupported", "permission_error", "api_error"]
```

## Métodos inexistentes

Em `data_loader.py`:

```python
client.get_account_created_time()
```

não existe em `MetaAdsClient`.

## Schema duplicado

`InstagramMedia` declara vários campos duas vezes:

```python
paid_reach
paid_impressions
paid_clicks
...
```

As declarações posteriores sobrescrevem as anteriores e podem alterar defaults/tipos silenciosamente. Mantenha uma única declaração.

## `daily_budget`

`CampaignInsight.from_api_response()` lê:

```python
data.get("daily_budget")
```

mas `get_campaign_insights()` não solicita `daily_budget`. Além disso, orçamento é normalmente propriedade de campaign/ad set, não um insight financeiro diretamente disponível em todos os níveis. Busque em endpoint próprio de campaigns/adsets.

---

# Matriz recomendada de endpoints

| Necessidade | Endpoint/nível | Fields/métricas | Observação |
|---|---|---|---|
| Lista de posts | `/{ig-user-id}/media` | `id,caption,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count,media_type,media_product_type` | `since/until` filtra publicação, não necessariamente os insights |
| Insights de post | `/{ig-media-id}/insights` | `reach,views,saved,shares,total_interactions` | Consultar métricas compatíveis por tipo |
| Reels | `/{ig-media-id}/insights` | anteriores + `ig_reels_video_view_total_time,ig_reels_avg_watch_time` | Não usar `plays` se a versão exige `views` |
| Stories gerais | `/{story-id}/insights` | `reach,views,replies,shares,total_interactions` | Persistir enquanto disponível |
| Navegação Story | `/{story-id}/insights` | `metric=navigation`, `breakdown=story_navigation_action_type` | Chamada separada |
| Conta Instagram | `/{ig-user-id}/insights` | separar grupos de métricas | Não somar reach de chunks |
| Demografia IG | `/{ig-user-id}/insights` | `follower_demographics`, etc. + `metric_type=total_value` | Uma chamada por breakdown |
| Ads total Instagram | `/act_{id}/insights`, `level=account` | `reach,impressions,spend,actions` | `breakdowns=publisher_platform` |
| Ads por anúncio | `/act_{id}/insights`, `level=ad` | `reach,impressions,clicks,inline_link_clicks,outbound_clicks,actions` | Não somar reach entre ads |
| Ads por placement | mesmo | mesmos fields | `breakdowns=publisher_platform,platform_position` |
| Paid reach por post | `/act_{id}/insights`, `level=account`, filtrado por `ad.id IN [...]` | `reach,impressions,spend,actions` | Deduplica dentro do grupo de anúncios do post |
| Demografia paga | `/act_{id}/insights`, `level=account` | `impressions,spend` | `breakdowns=age,gender`, `country`, `region` |
| Relação ad/post | `/act_{id}/ads` | `creative{source_instagram_media_id,effective_instagram_media_id,effective_instagram_story_id}` | Distinguir existing post de dark post |

---

# Modelo de dados recomendado

Não use prefixos “organic” sem comprovação documental. Prefira:

```python
class InstagramMediaMetrics(BaseModel):
    # Estado atual do objeto
    current_like_count: int | None
    current_comments_count: int | None

    # Insights retornados pela Instagram API
    instagram_insights_reach: int | None
    instagram_insights_views: int | None
    instagram_insights_saved: int | None
    instagram_insights_shares: int | None
    instagram_insights_total_interactions: int | None

    # Ads Insights no período
    paid_reach: int | None
    paid_impressions: int | None
    paid_post_reactions: int | None
    paid_net_likes: int | None
    paid_comments: int | None
    paid_shares: int | None
    paid_saves: int | None

    # Contexto temporal
    media_published_at: datetime
    instagram_snapshot_at: datetime
    paid_period_start: date
    paid_period_end: date
```

Não crie automaticamente:

```python
organic_reach = total_reach - paid_reach
total_reach = organic_reach + paid_reach
total_likes = like_count + paid_likes
```

---

# Prioridade de correção

## P0 — Corrigir antes de chamar o painel de preciso

1. Remover `verify=False`.
2. Remover as afirmações “100% orgânico” e “100% precisão real”.
3. Parar de somar alcance entre posts, anúncios e chunks.
4. Parar de calcular orgânico por `total - pago`.
5. Parar de somar `like_count + paid_likes`.
6. Não sobrescrever `clicks` da API.
7. Não usar `post_interaction_gross` como “cliques no criativo”.
8. Remover `saved_count`, `shares_count` e `reposts_count` do `/media` até confirmar suporte formal na versão.
9. Separar métricas incompatíveis em chamadas diferentes.
10. Não somar `lead` agregado com subtipos.

## P1 — Confiabilidade e paridade

1. Fixar atribuição com `use_unified_attribution_setting`.
2. Definir `action_report_time`.
3. Buscar paid reach agregado por conjunto de `ad_id`.
4. Persistir snapshots orgânicos.
5. Diferenciar `None` de zero.
6. Versionar corretamente os batch requests.
7. Paginar comentários e formulários.
8. Separar dark posts de publicações existentes.

## P2 — Qualidade analítica

1. Criar catálogo versionado de action types por conta.
2. Registrar response bruto para auditoria.
3. Comparar diariamente a API com exportação do Ads Manager.
4. Persistir timezone, attribution window e versão da API junto ao dado.
5. Criar testes de invariantes, por exemplo:

```python
assert impressions >= reach
assert spend >= 0
assert paid_reach is None or paid_reach >= 0
assert clicks >= inline_link_clicks
```

A última regra pode ter exceções de reporting, mas deve pelo menos gerar alerta.

---

# Conclusão

A separação mais confiável possível é:

```text
Instagram Insights != Ads Insights
```

Mantenha ambos lado a lado, com suas definições originais. Para delivery pago, use Marketing API com:

```text
level agregado apropriado
breakdowns=publisher_platform
publisher_platform=instagram
```

Para separar placements:

```text
breakdowns=publisher_platform,platform_position
```

Para deduplicar alcance de vários anúncios associados ao mesmo post, faça uma consulta agregada filtrada pelos `ad_id`, em vez de somar alcance por anúncio.

Por outro lado, **não há base matemática confiável para obter alcance orgânico puro por `total - paid`**, nem para obter alcance total único por `organic + paid`. Também não é seguro somar contadores sociais do objeto Instagram com ações atribuídas aos anúncios.

Depois dessas correções, o dashboard poderá afirmar algo tecnicamente defensável:

> “Métricas do Instagram Insights e do Meta Ads são coletadas separadamente, com alcance pago deduplicado no nível suportado pela API e sem soma indevida de métricas únicas.”

Mas não:

> “100% orgânico isolado e 100% preciso” para todas as métricas.