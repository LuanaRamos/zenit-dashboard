# Auditoria técnica — separação entre tráfego pago e orgânico

## Veredito

**A separação atual não é confiável.** Existem bugs objetivos de variável e problemas conceituais de agregação capazes de:

- classificar métricas totais como orgânicas;
- descontar métricas pagas de universos incompatíveis;
- somar alcance único como se fosse aditivo;
- duplicar curtidas, compartilhamentos e leads;
- esconder inconsistências com `max(0, ...)`;
- omitir dark posts e anúncios não vinculados a mídias publicadas;
- produzir resultados diferentes dependendo do período selecionado.

O tráfego pago vem corretamente da Marketing/Ads Insights API na maior parte do código. O principal problema está na tentativa de inferir o orgânico por nomes de variáveis ou pela fórmula:

```python
organico = total_instagram - pago_ads
```

Essa fórmula não é universalmente válida, especialmente para **alcance**, usuários únicos e métricas com modelos de atribuição diferentes.

---

# Problemas críticos

## 1. “Subtração mágica” de alcance está matematicamente errada

### Local

`ui/organic_components.py`:

```python
r_tot = insights.get('reach', 0)
r_paid = paid_totals.get('reach', 0)
r_org = max(0, r_tot - r_paid)
```

### Problema

Alcance representa pessoas/contas únicas e não é uma métrica aditiva.

Considere:

- Orgânico: `{A, B, C}`
- Pago: `{B, C, D}`
- Total: `{A, B, C, D}`

Então:

```text
Total - Pago = 4 - 3 = 1
```

Mas o alcance orgânico foi `3`, não `1`.

A subtração calcula, na melhor hipótese:

```text
Pessoas alcançadas somente pelo orgânico
```

e não:

```text
Alcance orgânico total
```

Além disso, o alcance do Instagram Insights e o alcance do Ads Insights podem ter diferenças de:

- atribuição;
- timezone;
- processamento;
- janela;
- deduplicação;
- universo de mídias;
- inclusão ou não de anúncios/dark posts.

### Consequência

O card:

```text
Org: X | Pago: Y
```

pode mostrar um valor orgânico severamente subestimado.

### Correção

Não subtrair métricas únicas.

Exibir separadamente:

- `Alcance no Instagram Insights`;
- `Alcance atribuído a anúncios`;
- eventualmente `Alcance exclusivamente orgânico`, somente se a API fornecer essa dimensão explicitamente.

Não apresentar:

```python
organic_reach = total_reach - paid_reach
```

como alcance orgânico.

O mesmo vale para:

- `accounts_engaged`;
- frequência;
- seguidores únicos;
- qualquer outra métrica de pessoas/contas únicas.

---

## 2. Há uma contradição central sobre o significado de `media.reach`

### Locais

`schemas/instagram.py`:

```python
reach: int = Field(
    default=0, description="Alcance total da Graph API (Orgânico + Pago)"
)
```

`ui/data_loader.py`:

```python
# A API Graph do Instagram (media/{id}/insights) já retorna APENAS o alcance orgânico
update_data['organic_reach'] = media.reach
```

### Problema

O mesmo campo é tratado de duas formas incompatíveis:

1. no schema, como total orgânico + pago;
2. no loader, como exclusivamente orgânico.

Não existe nenhum parâmetro na consulta que peça explicitamente um breakdown orgânico/pago:

```python
metrics = "reach,..."
```

O código simplesmente renomeia `reach` para `organic_reach`.

### Consequência

Se a métrica da versão/endpoint utilizado incluir alcance de conteúdo promovido, o pago será classificado como orgânico. Se ela for exclusivamente de mídia própria/orgânica, a descrição do schema e os cálculos de “alcance total” estarão errados.

### Correção

Até validar formalmente a semântica da métrica na Graph API v25.0, o campo deve ter nome neutro:

```python
instagram_media_reach
```

Não:

```python
organic_reach
```

Recomendo registrar respostas reais da API e manter uma definição documentada por métrica:

```python
METRIC_SEMANTICS = {
    "instagram_media_reach": {
        "source": "Instagram Graph /media/{id}/insights",
        "is_unique": True,
        "includes_paid": None,  # validar na documentação e conta real
    }
}
```

Não se deve definir “orgânico” apenas por a informação vir da Instagram Graph API. A origem da API não garante a natureza da métrica.

---

## 3. `saved` e `shares` são buscados corretamente, mas a UI usa outras variáveis

### Local da coleta

`api/instagram_client.py`:

```python
metrics = "reach,saved,shares,..."
```

E depois:

```python
shares=int(metrics_dict.get("shares", 0)),
saved=int(metrics_dict.get("saved", 0)),
```

### Local do uso incorreto

`ui/organic_components.py`:

```python
"Salvamentos (Orgânico)": m.saved_count,
"Compartilhamentos (Orgânico)": m.shares_count,
```

E no schema:

```python
@property
def total_shares(self) -> int:
    return self.shares_count + self.paid_shares

@property
def total_saved(self) -> int:
    return self.saved_count + self.paid_saved
```

### Problema

Os insights são guardados em:

```python
m.saved
m.shares
```

Mas a interface e os totalizadores usam:

```python
m.saved_count
m.shares_count
```

Esses últimos vêm da consulta de fields do objeto de mídia:

```python
saved_count,shares_count,reposts_count
```

Além de possivelmente não serem fields válidos para todos os tipos/versões de mídia, eles não são os valores já obtidos pelo endpoint de insights.

### Consequência

Salvamentos e compartilhamentos orgânicos podem aparecer como zero ou ficar inconsistentes com a resposta real da API.

### Correção

Usar as métricas de insights:

```python
"Salvamentos (Instagram)": m.saved,
"Compartilhamentos (Instagram)": m.shares,
```

E:

```python
@property
def total_shares(self) -> int:
    return self.shares + self.paid_shares

@property
def total_saved(self) -> int:
    return self.saved + self.paid_saved
```

Antes de chamar isso de “total”, ainda é necessário validar se `shares` e `paid_shares` são universos exclusivos ou sobrepostos.

---

## 4. Curtidas e comentários podem estar sendo duplicados

### Local

`schemas/instagram.py`:

```python
@property
def total_likes(self) -> int:
    return self.like_count + self.paid_likes
```

E:

```python
@property
def total_shares(self) -> int:
    return self.shares_count + self.paid_shares
```

### Problema

`like_count` e `comments_count` são contadores visíveis da publicação. Em publicações existentes promovidas, interações geradas por anúncios podem alimentar os próprios contadores do post.

Já `paid_likes` e `paid_comments` vêm das ações atribuídas aos anúncios.

Portanto, isto não é necessariamente válido:

```python
total = contador_do_post + ações_atribuídas_ao_anúncio
```

O primeiro valor pode já conter parte ou todo o segundo.

### Consequência

Os “Top Posts” podem duplicar curtidas e compartilhamentos:

```python
curtidas = m.total_likes
compartilhamentos = m.total_shares
```

Comentários são ainda mais inconsistentes: na tabela são tratados como orgânicos:

```python
"Comentários (Orgânico)": m.comments_count
```

mas o próprio sistema também possui:

```python
m.paid_comments
```

### Correção

Separar por fonte e não somar sem comprovação:

- `Curtidas visíveis no post`;
- `Curtidas atribuídas a Ads`;
- `Comentários visíveis no post`;
- `Comentários atribuídos a Ads`.

Evitar o nome “orgânico” para `like_count` e `comments_count`.

Exemplo:

```python
visible_like_count = media.like_count
ads_attributed_likes = mapping.paid_likes
```

Não criar `total_likes` pela soma dos dois.

---

## 5. Comentários pagos estão sendo contabilizados como orgânicos no nível da conta

### Local

`ui/organic_components.py`:

```python
int_paid = likes_paid + shares_paid + saves_paid
int_org = max(0, int_tot - int_paid)
```

E:

```python
render_metric_card(
    "Comentários",
    fmt(insights.get('comments', 0)),
    "Total",
    "Respostas no perfil"
)
```

### Problema

`int_paid` ignora:

- comentários pagos;
- respostas;
- outros tipos de interação;
- possivelmente cliques e interações que integram `total_interactions`.

Ao mesmo tempo, o sistema já extrai comentários pagos no mapeamento por anúncio:

```python
elif action_type == "comment":
    ad_metrics_map[ad_id]["comments"] = val
```

### Consequência

Comentários gerados por anúncios permanecem dentro da parcela apresentada como orgânica.

Além disso:

```python
total_interactions - (likes + shares + saves)
```

compara métricas que não têm necessariamente a mesma composição.

### Correção

Se for mantida uma decomposição de interações, o conjunto de componentes precisa ser semanticamente idêntico nos dois lados.

Ainda assim, o mais seguro é apresentar:

- `Total interactions — Instagram Insights`;
- `Post engagements/actions — Ads Insights`;

sem afirmar que a diferença é orgânica.

---

## 6. Métricas anunciadas como “100% Orgânico” não são garantidamente orgânicas

### Local

`ui/organic_components.py`:

```python
st.markdown("#### 👤 Exceções e Ações (100% Orgânico)")
```

Inclui:

```python
profile_views
profile_links_taps
website_clicks
accounts_engaged
comments
follows_and_unfollows
```

### Problema

O próprio projeto extrai ações pagas de:

- visitas ao perfil;
- seguidores;
- comentários;
- cliques;
- interações.

Exemplo:

```python
if act_type in ["profile_visit", "instagram_profile_views"]:
    profile_visits += val
```

e:

```python
if act_type == "instagram_follows":
    instagram_follows += val
```

Logo, é incorreto declarar que visitas ao perfil, comentários, seguidores e contas engajadas são automaticamente “100% orgânicos”.

Mesmo que uma métrica específica do Instagram Insights exclua anúncios, isso precisa estar documentado por métrica e versão. O código atual não prova essa exclusão.

### Correção

Renomear a seção para:

```text
Ações registradas pelo Instagram Insights
```

Até haver uma fonte/breakdown explícito, não usar “100% orgânico”.

---

## 7. `get_instagram_paid_totals()` usa action types diferentes como se fossem aliases equivalentes

### Local

`api/meta_client.py`:

```python
if action_type in ["like", "onsite_conversion.post_net_like"]:
    totals["likes"] = max(totals["likes"], val)
```

### Problema

`like`, `post_reaction`, `onsite_conversion.post_net_like` e outros eventos não devem ser considerados automaticamente sinônimos.

Usar `max()` não é uma forma confiável de desduplicação:

```python
max(valor_a, valor_b)
```

Isso apenas escolhe o maior número; não garante que os dois eventos representem a mesma ação.

O mapeamento por anúncio usa outra regra:

```python
like_priority = {
    "onsite_conversion.post_net_like": 3,
    "like": 2,
    "post_reaction": 1
}
```

Assim, o sistema tem duas definições diferentes de “curtida paga”:

- uma por prioridade;
- outra por máximo;
- ambas sem preservar os eventos crus.

### Consequência

O total pago da conta pode não reconciliar com a soma por anúncio e pode misturar curtidas em post, reações e outros tipos de “like”.

### Correção

Definir métricas distintas:

```python
paid_post_reactions
paid_instagram_net_likes
paid_page_likes
```

Manter o payload cru para auditoria e escolher uma métrica canônica conforme o objetivo da tela.

Não usar `max()` para desduplicar eventos semanticamente diferentes.

---

## 8. O alcance pago por post ainda pode estar duplicado

### Local

`get_ads_reach_mapping()`:

```python
ig_mapping[ig_id]["reach"] += metrics["reach"]
```

Depois, para posts com múltiplos anúncios:

```python
summary_params = {
    "level": "ad",
    "fields": "reach",
    "summary": '["reach"]',
    "filtering": ...
}
```

### Problema

O código assume que o `summary.reach` retornado com `level="ad"` e filtro por IDs será alcance deduplicado entre os anúncios.

Isso precisa ser validado contra a resposta real da API. Dependendo da agregação, o summary pode refletir a soma das linhas no nível solicitado, e não a união de pessoas entre os anúncios.

Quando a consulta falha, o fallback mantém:

```python
soma do reach de cada anúncio
```

que certamente pode duplicar pessoas.

Depois, a UI ainda faz:

```python
total_paid_reach = sum(m.paid_reach for m in media_list)
```

Mesmo que cada post estivesse corretamente deduplicado, a mesma pessoa pode ter visto vários posts. Portanto, a soma entre posts também não representa pessoas únicas.

### Consequência

O card:

```text
Alcance Pago — Pessoas
```

pode estar inflado.

### Correção

Usar `get_instagram_paid_totals()` no nível da conta para o alcance pago consolidado.

A soma por post deve ser rotulada como:

```text
Soma do alcance por publicação
```

e não “pessoas únicas alcançadas”.

A mesma observação vale para:

```python
total_organic_reach = sum(m.organic_reach for m in media_list)
```

---

## 9. Dark posts não aparecem no relatório por publicação

### Fluxo atual

1. Ads são ligados a um ID de mídia:

```python
source_instagram_media_id
or effective_instagram_media_id
or effective_instagram_story_id
```

2. Depois, o mapping só é aplicado às mídias retornadas por:

```python
/{instagram_account_id}/media
```

3. O loop é dirigido pela lista orgânica:

```python
for media in media_list:
    if media.id in ads_mapping:
        ...
```

### Problema

Dark posts não publicados no perfil podem aparecer no Ads Insights, mas não na lista `/media` do perfil.

Consequentemente, eles ficam em `ads_mapping`, mas nunca viram um `InstagramMedia`.

A interface afirma:

```text
Desempenho Pago (Dark Posts / Impulsionados)
```

mas a tabela não inclui todos os dark posts.

O total de conta em `get_instagram_paid_totals()` pode incluí-los, enquanto a tabela por post não.

### Consequência

Os cards pagos da conta podem ser maiores que a soma da tabela, sem nenhuma explicação.

### Correção

Criar duas coleções:

```python
published_media_rows
unmatched_paid_creatives
```

Depois do cruzamento:

```python
matched_ids = {media.id for media in media_list}
unmatched = {
    ig_id: metrics
    for ig_id, metrics in ads_mapping.items()
    if ig_id not in matched_ids
}
```

Exibir os não encontrados em uma seção:

```text
Anúncios/Dark posts sem publicação correspondente no perfil
```

Também deve existir reconciliação por investimento:

```python
coverage = mapped_instagram_spend / total_instagram_ads_spend
```

Se a cobertura for menor que 100%, a UI deve avisar.

---

## 10. `paid_other_clicks` mistura tipos diferentes de clique

### Local

`ui/data_loader.py`:

```python
paid_other_clicks = max(0, paid_clicks - paid_link_clicks)
```

Onde:

- `paid_clicks` vem do campo raiz `clicks`;
- `paid_link_clicks` vem de `outbound_clicks`.

### Problema

O nome da coluna é:

```text
Cliques no Criativo (Pago)
```

Mas a fórmula é:

```text
Todos os cliques - cliques de saída
```

O resultado pode conter:

- visitas ao perfil;
- expansão de imagem;
- interação com CTA;
- reprodução;
- cliques internos;
- outros eventos.

Não é exclusivamente “clique no criativo”.

### Correção

Renomear para:

```text
Outros cliques pagos
```

ou:

```text
Cliques totais menos cliques de saída
```

Se o objetivo for clique no criativo, é necessário usar os action types específicos e não uma subtração genérica.

---

## 11. Na visão de campanhas, `post_interaction_gross` está sendo tratado como clique

### Local

`schemas/meta.py`:

```python
elif act_type == "post_interaction_gross":
    other_clicks += val
```

Depois:

```python
clicks = link_clicks + profile_visits + other_clicks
```

O mesmo padrão aparece em `get_creative_performance()`.

### Problema

`post_interaction_gross` é interação grossa com o post, não um contador puro de cliques. Pode incorporar eventos como reações, comentários, compartilhamentos e outros engajamentos.

Portanto:

```python
link_clicks + profile_visits + post_interaction_gross
```

não recria matematicamente o campo `clicks`.

### Consequências

Ficam incorretos:

- total de cliques;
- CPC;
- “cliques no criativo”;
- ranking de criativos;
- comparações entre campanhas.

### Correção

Preservar o valor oficial:

```python
clicks = int(data.get("clicks", 0))
```

E separar ações:

```python
link_clicks
outbound_clicks
profile_visits
post_engagements
post_reactions
comments
shares
saves
```

Não reconstruir `clicks` somando ações potencialmente sobrepostas.

---

## 12. `link_click` e `outbound_click` são usados como se fossem a mesma métrica

### Locais

Campanhas e criativos:

```python
if act_type == "link_click":
    link_clicks += val
```

Mapping de posts:

```python
for out_action in item.get("outbound_clicks", []):
    ...
    link_clicks = ...
```

A UI chama ambos de:

```text
Cliques de Saída
```

### Problema

`link_click` e `outbound_click` não são equivalentes:

- `link_click`: cliques em links, inclusive alguns destinos dentro do ecossistema Meta;
- `outbound_click`: cliques que levam para fora das propriedades Meta.

### Consequência

A mesma coluna tem significado diferente conforme a tela.

### Correção

Criar campos distintos em todos os schemas:

```python
link_clicks
outbound_clicks
```

E exibir:

- `Cliques no link`;
- `Cliques de saída`.

O custo por clique de saída deve usar exclusivamente `outbound_clicks`.

---

## 13. Leads pagos podem ser duplicados

### Local

`CampaignInsight.from_api_response()`:

```python
elif act_type == "lead":
    site_leads += val
elif act_type == "leadgen":
    native_leads += val
```

Depois:

```python
leads = site_leads + native_leads
```

### Problema

Dependendo do payload e da configuração da conta, `lead` pode ser uma métrica agregada e coexistir com eventos específicos de formulário/conversão.

Somar action types sem validar sua relação pode duplicar o mesmo lead.

Além disso, classificar:

```python
lead -> site_leads
leadgen -> native_leads
```

não é uma separação suficientemente robusta. Os action types exatos variam conforme:

- pixel/CAPI;
- Instant Forms;
- conversão no site;
- versão da API;
- eventos customizados.

### Consequência

`total_leads`, CPL e CPA podem ficar subestimados por um denominador duplicado.

### Correção

Definir uma taxonomia baseada nos payloads reais da conta:

```python
CANONICAL_LEAD_ACTIONS = {
    "website": {...},
    "instant_form": {...},
}
```

Não somar evento agregado com seus componentes.

Também é recomendável armazenar todas as `actions` cruas para reconciliação com o Ads Manager.

---

## 14. O “CPA médio” usa gasto e conversões de universos diferentes

### Local

`ui/components.py`:

```python
total_conv = total_leads + total_wpp
avg_cpa = total_spend / total_conv
```

### Problema

`total_spend` inclui todas as campanhas:

- alcance;
- reconhecimento;
- tráfego;
- engajamento;
- vídeo;
- leads;
- WhatsApp.

O denominador inclui apenas:

- leads;
- WhatsApp.

Assim, gasto de campanhas sem intenção de conversão entra no CPA.

Além disso, o card de leads apresenta pago + orgânico:

```python
total_leads + organic_leads
```

mas o CPA não usa os leads orgânicos. Isso é defensável para “CPA pago”, mas a interface precisa deixar isso explícito.

### Correção

Calcular:

```python
conversion_spend = gasto das campanhas elegíveis para a conversão
paid_conversions = paid_leads + paid_whatsapp
paid_cpa = conversion_spend / paid_conversions
```

Ou exibir claramente:

```text
Gasto total da conta / conversões atribuídas aos anúncios
```

Não chamar de “CPA médio geral” sem explicar o universo.

---

## 15. Gasto pode ser apropriado simultaneamente para CPL e custo de WhatsApp

### Local

`app.py`:

```python
leads_spend = sum(
    c.spend for c in campaigns
    if c.leads > 0 or c.objective_friendly == "Cadastros"
)

wpp_spend = sum(
    c.spend for c in campaigns
    if c.whatsapp_starts > 0
    or c.objective_friendly == "Mensagens (WhatsApp/Direct)"
)
```

### Problema

Uma campanha pode gerar lead e conversa. Nesse caso, o gasto integral entra nos dois cálculos:

```python
CPL = gasto integral / leads
CPW = gasto integral / WhatsApp
```

Não é mistura entre orgânico e pago, mas é dupla apropriação de investimento.

### Correção

Assumir explicitamente que cada custo é:

```text
Gasto da campanha que gerou a ação / quantidade da ação
```

Ou separar por campanhas/ad sets com objetivo predominante.

Não existe uma divisão confiável do gasto entre ações sem um modelo de alocação.

---

## 16. A mesma campanha pode aparecer simultaneamente em WhatsApp e Perfil

### Local

`app.py`:

```python
whatsapp_campaigns = [
    c for c in campaigns
    if c.objective in ["OUTCOME_ENGAGEMENT", "MESSAGES"]
    or c.whatsapp_starts > 0
]

profile_campaigns = [
    c for c in campaigns
    if c.objective in ["OUTCOME_TRAFFIC", "LINK_CLICKS"]
    or c.instagram_follows > 0
    or c.profile_visits > 0
]
```

### Problema

Os filtros são independentes. Uma campanha pode satisfazer os dois.

Além disso, qualquer campanha `OUTCOME_ENGAGEMENT` entra em WhatsApp, mesmo que tenha:

```python
whatsapp_starts == 0
```

### Consequência

Campanhas podem ser duplicadas em tabelas e campanhas de engajamento podem ser classificadas como WhatsApp sem gerar mensagens.

### Correção

Criar uma classificação única com prioridade explícita:

```python
def classify_campaign(c):
    if c.whatsapp_starts > 0:
        return "whatsapp"
    if c.profile_visits > 0 or c.instagram_follows > 0:
        return "profile"
    if c.leads > 0:
        return "leads"
    return "other"
```

Se uma campanha puder pertencer a vários grupos, a UI deve declarar que os grupos são sobrepostos.

---

## 17. O período “Desde o início” usa janelas diferentes entre Instagram e Ads

### Instagram account insights

`instagram_client.py`:

```python
elif date_preset == "maximum":
    until = now
    since = until - relativedelta(years=2)
```

### Ads

`meta_client.py`:

```python
params["date_preset"] = "maximum"
```

### Mídias

`data_loader.py`:

```python
media_list = ig_client.get_recent_media(limit=100)
```

com paginação potencialmente até o início.

### Problema

“Desde o início” significa:

- Instagram account insights: somente dois anos;
- Ads Insights: máximo disponibilizado pela conta;
- lista de mídias: potencialmente todo o histórico;
- seguidores: sempre últimos 30 dias;
- demografia: lifetime ou mês corrente.

### Consequência

As subtrações e comparações misturam períodos diferentes.

### Correção

Definir janelas explícitas por fonte e mostrar na UI.

Se o Instagram só permitir dois anos:

```text
Instagram Insights: últimos 24 meses
Ads: últimos 24 meses
```

A consulta de Ads precisa usar o mesmo `time_range`, e não `maximum`.

---

## 18. Somar `reach` de chunks de 30 dias duplica usuários

### Local

`InstagramClient.get_account_insights()`:

```python
results[name] = results.get(name, 0) + val
```

O método divide períodos longos em chunks e soma tudo, inclusive:

```python
reach
accounts_engaged
```

### Problema

Uma pessoa alcançada em janeiro e novamente em fevereiro será contada duas vezes.

Isso pode ser aceitável para métricas aditivas, como certas contagens de ações, mas não para usuários únicos.

### Consequência

Em períodos superiores a 30 dias, o `reach` do Instagram fica inflado. Depois ele é comparado e subtraído do reach pago do período inteiro, agravando a incompatibilidade.

### Correção

Classificar métricas:

```python
ADDITIVE_METRICS = {
    "likes", "comments", "shares", "saves",
    "profile_views", ...
}

NON_ADDITIVE_METRICS = {
    "reach", "accounts_engaged"
}
```

Para métricas não aditivas:

- consultar o maior intervalo suportado diretamente;
- exibir série por período;
- ou rotular como “soma dos alcances mensais”, nunca “pessoas únicas no período”.

---

## 19. `max(0, total - paid)` mascara erros de reconciliação

### Local

```python
r_org = max(0, r_tot - r_paid)
likes_org = max(0, likes_tot - likes_paid)
shares_org = max(0, shares_tot - shares_paid)
```

### Problema

Se pago for maior que total por diferença de fonte, janela ou definição, o sistema converte silenciosamente o erro em zero.

### Consequência

Uma incompatibilidade de dados parece ser um resultado legítimo.

### Correção

Não ocultar a divergência:

```python
delta = total - paid
if delta < 0:
    logger.warning(...)
    organic = None
else:
    organic = delta
```

Na UI:

```text
Não reconciliável: as fontes retornaram universos diferentes.
```

---

## 20. Demografia chamada de orgânica pode incluir audiência promovida

### Local

`ui/demographics_components.py`:

```python
st.markdown("### Perfil da Audiência (Orgânico — Instagram)")
```

Dados:

```python
engaged_audience_demographics
reached_audience_demographics
```

### Problema

Essas métricas descrevem a audiência da conta do Instagram. O código não fornece nenhum parâmetro que filtre origem orgânica.

Classificá-las como “Orgânico” é uma inferência não demonstrada.

### Correção

Usar:

```text
Audiência da conta no Instagram
```

e manter separada da seção:

```text
Audiência entregue por anúncios — Ads Insights
```

---

# Problemas adicionais de schema e implementação

## 21. Campos pagos estão declarados duas vezes em `InstagramMedia`

Exemplo:

```python
paid_reach: int = 0
...
paid_reach: int = Field(default=0, ...)
```

Também ocorre com:

- `paid_impressions`;
- `paid_clicks`;
- `paid_link_clicks`;
- `paid_other_clicks`;
- `paid_likes`;
- `paid_shares`;
- `paid_saved`;
- `paid_views`;
- `paid_destination`;
- `paid_ctr`;
- `paid_frequency`.

A segunda declaração sobrescreve conceitualmente a primeira. Há inclusive conflito:

```python
paid_destination: str | None = None
```

e depois:

```python
paid_destination: str = "N/A"
```

Isso não mistura métricas diretamente, mas torna o contrato do modelo ambíguo e aumenta muito o risco de erro.

---

## 22. Fallback de `instagram_follows` não funciona como esperado

Há:

```python
instagram_follows = int(item.get("instagram_follows", 0))
```

Mas os campos solicitados nos endpoints de insights são:

```python
"...actions"
```

e não incluem `instagram_follows` na raiz.

Portanto, esse fallback tende a ser sempre zero. Se o field de raiz for suportado pela versão utilizada, deve ser explicitamente solicitado. Caso contrário, deve ser removido.

O mesmo cuidado vale para action types exatos de visita ao perfil e seguidores: correspondências exatas podem perder variantes retornadas pela conta.

---

## 23. CPA de um anúncio e CPA de vários anúncios têm denominadores diferentes

Para um anúncio:

```python
cost_per_action_type["post_engagement"]
```

Para múltiplos anúncios:

```python
spend / (likes + comments + shares + saved)
```

`post_engagement` pode conter mais ações do que essas quatro.

Consequentemente, o “Custo por Engajamento” muda de definição dependendo de quantos anúncios promoveram o post.

A fórmula deve ser única e baseada no mesmo contador canônico.

---

# Arquitetura recomendada

## 1. Não use “orgânico”, “pago” e “total” como simples nomes de campos

Modele também a fonte e a semântica:

```python
class MetricValue(BaseModel):
    value: float
    source: str
    metric_name: str
    is_unique: bool
    attribution: str | None
    includes_paid: bool | None
    period_start: datetime
    period_end: datetime
```

Exemplo:

```python
MetricValue(
    value=1000,
    source="instagram_media_insights",
    metric_name="reach",
    is_unique=True,
    attribution=None,
    includes_paid=None,
)
```

---

## 2. Separar os universos

### Orgânico/Instagram

Fonte:

```text
Instagram Graph API
```

Guardar como:

```python
instagram_reported_reach
instagram_reported_views
instagram_reported_shares
instagram_reported_saves
visible_like_count
visible_comment_count
```

### Pago

Fonte:

```text
Meta Ads Insights
```

Guardar como:

```python
ads_reach
ads_impressions
ads_outbound_clicks
ads_link_clicks
ads_post_reactions
ads_comments
ads_shares
ads_saves
ads_spend
```

Não chamar automaticamente a primeira coleção de “orgânica”.

---

## 3. Remover totais derivados inseguros

Evitar:

```python
total_reach = instagram_reach + ads_reach
organic_reach = instagram_total_reach - ads_reach
total_likes = visible_likes + ads_likes
```

Manter os valores lado a lado.

---

## 4. Adicionar reconciliação obrigatória

Para cada período:

```python
total_instagram_ads_spend
mapped_post_spend
unmapped_dark_post_spend
```

Validar:

```python
mapped_post_spend + unmapped_spend == total_instagram_ads_spend
```

Com tolerância para arredondamento.

Também reconciliar:

- impressões;
- outbound clicks;
- ações;
- quantidade de ads;
- IDs não mapeados.

---

## 5. Preservar ações cruas

Não transformar imediatamente `actions` em uma única métrica genérica.

Exemplo:

```python
raw_actions = {
    action["action_type"]: Decimal(action["value"])
    for action in item.get("actions", [])
}
```

A camada de negócio decide depois:

```python
canonical_paid_comments
canonical_paid_post_reactions
canonical_paid_leads
canonical_paid_whatsapp_starts
```

Isso permite conferir divergências com o Ads Manager.

---

# Prioridade de correção

## P0 — corrigir antes de confiar no dashboard

1. Remover a subtração de reach total menos reach pago.
2. Parar de chamar `media.reach` de orgânico sem validação.
3. Trocar `saved_count`/`shares_count` por `saved`/`shares` nos insights.
4. Remover `total_likes = like_count + paid_likes`.
5. Não classificar comentários, visitas e seguidores como “100% orgânicos”.
6. Parar de reconstruir cliques com `post_interaction_gross`.
7. Separar `link_click` de `outbound_click`.
8. Exibir dark posts não mapeados.
9. Uniformizar os períodos entre Instagram e Ads.
10. Parar de somar reach entre posts/chunks como se fossem pessoas únicas.

## P1 — impacto alto nos custos e conversões

1. Corrigir a taxonomia de leads.
2. Corrigir CPA/CPL/CPW e o universo de gasto.
3. Tornar a classificação de campanhas exclusiva ou declarar sobreposição.
4. Unificar a definição de engajamento e CPA.
5. Remover o uso de `max()` para “desduplicar” action types.

## P2 — qualidade e manutenção

1. Remover campos duplicados de `InstagramMedia`.
2. Adicionar timezone explícito.
3. Registrar payloads e métricas não reconhecidas.
4. Criar testes de reconciliação e fixtures de `actions`.
5. Mostrar a janela real de cada métrica na UI.

---

# Conclusão

Hoje existem **dois tipos de mistura**:

1. **Mistura direta por variável**, principalmente:
   - `saved` versus `saved_count`;
   - `shares` versus `shares_count`;
   - `like_count + paid_likes`;
   - `comments_count` chamado de orgânico;
   - `reach` renomeado para `organic_reach` sem breakdown.

2. **Mistura conceitual por cálculo**, principalmente:
   - `total - pago = orgânico`;
   - soma de reach único entre anúncios, posts e chunks;
   - soma de contadores visíveis com ações atribuídas;
   - uso de action types diferentes como se fossem equivalentes;
   - períodos diferentes sob o mesmo filtro.

Portanto, **não é seguro afirmar atualmente que o Zenit Dashboard separa com precisão o tráfego pago do orgânico**. Os números de investimento e impressões pagas tendem a ser os mais confiáveis. Já alcance orgânico, engajamento orgânico, curtidas totais, comentários orgânicos, compartilhamentos, salvamentos e leads precisam das correções acima antes de serem usados como indicadores auditáveis.