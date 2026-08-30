# Auditoria independente — Zenit Dashboard x Meta APIs v26

Data da auditoria: 30 de agosto de 2026

Repositório: [LuanaRamos/zenit-dashboard](https://github.com/LuanaRamos/zenit-dashboard)

Base auditada: main em [a1af0c4](https://github.com/LuanaRamos/zenit-dashboard/commit/a1af0c4038664f9720bfdc5cef1dff4823d2a512)

PR avaliada: [#2 — Meta v26 e métricas orgânicas](https://github.com/LuanaRamos/zenit-dashboard/pull/2), head [0675f41](https://github.com/LuanaRamos/zenit-dashboard/commit/0675f416f147f363164b53795448c7964729e2da)

## Veredito

O dashboard ainda não pode garantir que todo número chamado de orgânico seja realmente orgânico nem que toda métrica de Ads tenha a mesma definição exibida no rótulo.

O problema principal não é só de campo ou versão da API. O código atual mistura três universos que a Meta entrega separadamente:

1. Media Insights: desempenho de uma publicação específica.
2. Instagram Account Insights: totais da conta, que em métricas importantes incluem anúncios ou conteúdo impulsionado.
3. Ads Insights: entrega paga, com plataforma, nível, atribuição, moeda, timezone e janela próprios.

A implementação correta deve manter esses universos separados desde o payload até o card. Não é válido calcular orgânico por subtração, somar alcances únicos ou inventar um total orgânico + pago quando as audiências e as taxonomias se sobrepõem.

### Estado por área

| Área | Estado atual | Conclusão |
|---|---|---|
| Orgânico por publicação | Parcial | Comments, likes, views e total_interactions podem vir de Media Insights como orgânicos, mas falhas ainda viram zero e alguns fallbacks mudam silenciosamente a fonte. |
| Totais da conta Instagram | Misto | Reach, accounts_engaged e total_interactions não são orgânicos puros. A UI precisa dizer que incluem anúncios. |
| Pago no Instagram | Parcial | A PR #2 filtra alguns totais por publisher_platform=instagram, mas outros fluxos ainda misturam plataformas ou usam agregações frágeis. |
| Campanhas Ads | Incorreto em campos críticos | Clicks é sobrescrito, link click é rotulado como outbound e leads podem ser duplicados. |
| Períodos | Inconsistente | O mesmo filtro visual representa janela de publicação, snapshot/lifetime de mídia, User Insights retidos por até 90 dias, 395 dias artificiais de Ads e 30 dias de seguidores. |
| Falhas e ausência | Incorreto | Zero real, campo ausente, erro, permissão insuficiente e resposta parcial são frequentemente indistinguíveis. |
| Testes | Insuficiente | Não há suíte automatizada de contrato; o CI executa apenas Ruff e já está vermelho por dívida preexistente. |

## Escopo e método

A auditoria rastreou cada métrica da interface até:

- endpoint, nível e campos solicitados;
- filtro de plataforma e período efetivo;
- transformação, fallback e agregação local;
- schema usado para transportar o valor;
- rótulo mostrado na interface;
- tratamento de paginação, erro e ausência.

Também foram comparados:

- main no commit a1af0c4;
- PR #2 no commit 0675f41;
- as duas auditorias já existentes no repositório;
- documentação oficial vigente da Meta para Instagram Platform, Graph API v26 e Ads Insights.

Não foi usado conteúdo de blogs de terceiros para definir o contrato das métricas.

## O que a Meta entrega atualmente

### 1. Media Insights: conteúdo específico

A documentação oficial de [Instagram Media Insights](https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media/insights) afirma explicitamente que comments, likes, views e total_interactions reportam somente interações orgânicas; interações em anúncios que contêm aquela mídia não entram nesses campos.

Para contagens agregadas que podem incluir mídia promovida, impulsionada ou usada em anúncio, a Meta introduziu total_comments, total_likes e total_views. Esses campos não devem ser chamados de orgânicos.

Reach é definido pela Meta como o número estimado de usuários únicos que viram a mídia. Saved e shares também pertencem ao endpoint de mídia, mas a frase oficial que garante exclusão de Ads cita explicitamente os quatro campos acima. Por prudência, a interface deve chamar reach, saved e shares de métricas de Media Insights até que um teste ao vivo com mídia promovida confirme o comportamento da conta usada pelo dashboard.

O filtro de datas do endpoint /media seleciona quais publicações entram na lista. Ele não transforma o insight de cada mídia em desempenho ocorrido somente naquele período. A própria documentação descreve a resposta de Media Insights como lifetime e informa que os dados podem ficar disponíveis por até dois anos, com atraso de até 48 horas.

### 2. Account Insights: total da conta, incluindo Ads

A documentação de [Instagram Account Insights](https://developers.facebook.com/documentation/instagram-platform/api-reference/instagram-user/insights) define:

- reach como contas únicas que viram conteúdo, inclusive em anúncios;
- accounts_engaged como contas que interagiram com conteúdo, inclusive em anúncios;
- total_interactions como interações da conta, incluindo conteúdo boosted.

Portanto:

- esses valores não podem ser rotulados como orgânicos;
- reach orgânico não pode ser calculado como reach da conta menos reach pago;
- account total não deve ser somado novamente com Ads Insights;
- media_product_type=AD não constitui, por si só, um breakdown documentado e completo de orgânico versus pago.

O [guia oficial de Instagram Insights](https://developers.facebook.com/documentation/instagram-platform/insights) informa que User Metrics ficam armazenadas por até 90 dias. O clamp de aproximadamente 13 meses existente no código não representa esse contrato.

### 3. Ads Insights: pago

A documentação oficial de [Ads Insights](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights) define o endpoint como a fonte de performance e estatísticas de anúncios. O [Ad Account Insights reference](https://developers.facebook.com/documentation/ads-commerce/marketing-api/reference/ad-account/insights) expõe breakdowns como publisher_platform e platform_position.

Para qualquer card chamado “Pago no Instagram”, o conjunto precisa conter apenas linhas publisher_platform=instagram. Uma visão chamada “Meta Ads” pode incluir outras plataformas, mas deve mostrar seu escopo e não ser comparada diretamente a conteúdo orgânico do Instagram.

Clicks, inline_link_clicks e outbound_clicks são métricas diferentes e potencialmente sobrepostas. Outbound clicks é uma lista de AdsActionStats, não um escalar simples. Actions e action_values também são listas por action_type; o parser deve preservar a taxonomia bruta e não somar um agregado com seus subtipos sem uma regra comprovada para aquela conta.

Segundo as [boas práticas oficiais de Ads Insights](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights/best-practices), desde 10 de junho de 2025 os parâmetros use_unified_attribution_setting e action_report_time são ignorados para reduzir divergências com o Ads Manager. A resposta usa a atribuição do ad set e o comportamento mixed: ações on-Meta ficam no tempo da impressão e ações off-Meta ficam no tempo da conversão. Assim, a recomendação antiga de simplesmente adicionar esses parâmetros está desatualizada; o dashboard deve registrar e exibir o contexto de atribuição efetivo.

Desde 12 de janeiro de 2026, as janelas 7d_view e 28d_view não são mais retornadas por action_attribution_windows. Ausência dessas chaves não significa zero.

### 4. Versão e permissões

O [changelog oficial](https://developers.facebook.com/docs/graph-api/changelog/) lista v26.0 como a versão atual. Para Facebook Login, os endpoints de Instagram Insights documentam instagram_basic, instagram_manage_insights e pages_read_engagement; conforme a forma de acesso ao ativo, ads_read ou ads_management também pode ser exigida. Ads Insights exige ao menos ads_read ou ads_management, além de acesso ao ad account alvo. Os nomes de permissões de Facebook Login e Instagram Login não devem ser misturados.

Falha de permissão deve produzir “indisponível” com motivo, nunca um zero.

## Contrato de métricas recomendado

| Métrica exibida | Fonte correta | Escopo correto | Agregação permitida | Rótulo seguro |
|---|---|---|---|---|
| Likes por publicação | Media Insights / likes | Orgânico documentado | Soma entre posts somente como “soma de interações”, não pessoas | Curtidas orgânicas |
| Comments por publicação | Media Insights / comments | Orgânico documentado | Soma aditiva, com aviso de snapshot da mídia | Comentários orgânicos |
| Views por publicação | Media Insights / views | Orgânico documentado | Soma de exibições; não é alcance | Visualizações orgânicas |
| Total interactions por publicação | Media Insights / total_interactions | Orgânico documentado | Soma aditiva entre mídias | Interações orgânicas |
| Reach por publicação | Media Insights / reach | Mídia, estimado | Nunca apresentar soma como alcance único | Alcance do conteúdo — Media Insights |
| total_likes/comments/views | Media Insights / total_* | Agregado, pode incluir promoção | Separado do orgânico | Total agregado — inclui promoção |
| Reach da conta | User Insights / reach | Conta, inclui Ads | Não somar chunks nem subtrair Ads | Alcance da conta — inclui anúncios |
| Accounts engaged | User Insights | Conta, inclui Ads | Não somar janelas como pessoas únicas | Contas engajadas — inclui anúncios |
| Total interactions da conta | User Insights | Conta, inclui boosted | Não somar com Ads Insights | Interações da conta — inclui impulsionados |
| Reach pago no Instagram | Ads Insights + publisher_platform | Pago, Instagram | Consultar agregado deduplicado no nível adequado | Alcance pago — Instagram |
| Impressions paid | Ads Insights | Pago | Aditiva dentro do mesmo escopo/período | Impressões pagas |
| Clicks | Ads Insights / clicks | Pago | Preservar valor da raiz | Cliques — todos |
| Link clicks | Ads Insights / inline_link_clicks ou action type preservado | Pago | Separado de outbound | Cliques no link |
| Outbound clicks | Ads Insights / outbound_clicks | Pago | Separado de link clicks | Cliques de saída |
| Leads | Ads actions | Pago, por action_type | Não somar lead agregado com subtipo | Nome do evento de conversão |
| Spend, CPC, CPM | Ads Insights + moeda da conta | Pago | Mesmo nível, período e timezone | Valor na moeda real da conta |

## Achados no código

### P0 — bloqueiam uma entrega confiável

#### P0-01 — clicks oficial é sobrescrito

Em [CampaignInsight.from_api_response](https://github.com/LuanaRamos/zenit-dashboard/blob/0675f416f147f363164b53795448c7964729e2da/src/dashboard/schemas/meta.py#L88-L185), o parser lê clicks da raiz e depois o substitui por link_clicks + profile_visits + post_interaction_gross. Post interaction é engajamento, não clique. O CPC continua vindo da API com outro denominador.

Correção: preservar clicks exatamente como entregue. Modelar link clicks, outbound clicks, profile visits e post interactions em campos distintos.

#### P0-02 — “Cliques de saída” usa link_click

Campanhas não solicitam outbound_clicks, e criativos solicitam mas ignoram o campo em parte do fluxo. A UI usa “Cliques de Saída” para link_click.

Correção: solicitar e parsear outbound_clicks; usar inline_link_clicks ou o action type preservado para “Cliques no link”, sem tratar um como sinônimo do outro.

#### P0-03 — leads podem ser duplicados

O parser soma action_type=lead e action_type=leadgen sem uma regra de negócio documentada nem prova de que os conjuntos são disjuntos. Sem preservar a taxonomia crua, a soma não é auditável.

Correção: preservar todas as linhas e dimensões de actions; exibir os action types separadamente até existir um mapeamento comprovado; só escolher um denominador canônico e nomeado por card de CPL.

#### P0-04 — ausência, erro e zero são confundidos

Os schemas usam zero como default e os clientes engolem exceções. Uma resposta sem campo, erro 400 por métrica incompatível, erro de permissão, rate limit ou página faltante vira zero ou lista parcial.

Correção: valores anuláveis, status ok/partial/unavailable, issues e período efetivo em cada relatório.

#### P0-05 — alcance único é somado

Account Insights soma reach e accounts_engaged em chunks de aproximadamente 30 dias. A mesma conta pode aparecer em vários chunks. Em posts, a soma de reach entre mídias também não representa pessoas únicas. No mapping pago, o fallback multi-ad conserva soma de reach se a consulta agregada falha.

Correção: proibir soma de métricas únicas. Quando não houver agregado deduplicado válido, exibir N/D ou “soma de alcances por item — não deduplicada”, nunca “alcance total”.

#### P0-06 — PR #2 mantém métricas antigas de Story

[get_active_stories](https://github.com/LuanaRamos/zenit-dashboard/blob/0675f416f147f363164b53795448c7964729e2da/src/dashboard/api/instagram_client.py#L290-L365) força v26 e ainda pede exits, taps_forward e taps_back. Na v26, a métrica documentada é navigation com breakdown story_navigation_action_type, retornando TAP_BACK, TAP_EXIT, TAP_FORWARD e SWIPE_FORWARD.

Correção: request separado de navigation com o breakdown correto; mapear cada ação de forma case-insensitive. Código 10 não basta para concluir audiência insuficiente: classificar pelo code, error_subcode e texto efetivo, e só usar insufficient_audience quando a resposta disser isso.

#### P0-07 — messaging é chamado de WhatsApp sem prova do destino

O parser converte action types de messaging diretamente em whatsapp_starts. A referência oficial chama esses eventos de Messaging Conversations; eles podem representar destinos diferentes.

Correção: usar o rótulo “Conversas por mensagem” por padrão. Só chamar de WhatsApp quando metadados do anúncio ou action_breakdowns=action_destination confirmarem o destino.

#### P0-08 — validação TLS está desativada

As chamadas relevantes usam verify=False. Isso permite interceptação do token e adulteração da resposta, comprometendo segurança e integridade dos dados.

Correção: reativar a validação TLS e tratar falhas de certificado explicitamente. É bloqueador de merge.

### P1 — divergências materiais

#### P1-01 — PR #2 melhora rótulos, mas volta a fabricar “orgânico + pago”

[render_organic_metrics_cards](https://github.com/LuanaRamos/zenit-dashboard/blob/0675f416f147f363164b53795448c7964729e2da/src/dashboard/ui/organic_components.py#L99-L120) soma total_interactions orgânico de Media Insights com uma seleção de actions de Ads. As composições não são equivalentes e o resultado é apresentado como completo.

Correção: dois cards separados ou duas colunas, sem total sintético.

#### P1-02 — fallback do contador visível pode mudar o escopo

A PR usa likes/comments de Media Insights, mas recorre a like_count/comments_count do objeto quando faltam. A fonte do fallback não é registrada e o resultado continua parecendo orgânico confirmado.

Correção: Media Insights ausente deve ser N/D. Se o contador visível for útil, armazená-lo em campo separado com origem visible_object_count e escopo não garantido.

#### P1-03 — account metrics incompatíveis são agrupadas

Várias métricas de conta são solicitadas juntas. Métricas com breakdown, timeframe ou suporte diferente podem derrubar toda a consulta. A Meta recomenda agrupar apenas métricas compatíveis.

Correção: grupos de request por contrato; demografia com timeframe, follows_and_unfollows com follow_type e demais totais em chamadas compatíveis.

#### P1-04 — períodos não representam a mesma coisa

Hoje e no contrato oficial:

- posts: janela de publicação;
- Media Insights: snapshot/lifetime no momento da coleta;
- Instagram User Insights: a Meta retém até 90 dias, mas o código tenta usar cerca de 13 meses;
- Ads: “maximum” vira 395 dias, embora o limite geral documentado seja de até 37 meses e métricas únicas com breakdown tenham regras mais restritas, como 13 meses;
- followers: sempre 30 dias;
- Stories: somente ativos nas últimas 24 horas.

Correção: cada relatório transporta requested period, effective period e period_basis. Limites são específicos por fonte, métrica e breakdown. “Maximum” só pode aparecer se for realmente consultado; caso contrário, mostrar “últimos 395 dias”.

#### P1-05 — Ads “Instagram” ainda pode receber outras plataformas

A PR corrige get_instagram_paid_totals e o agregado de reach multi-ad, mas a audiência de criativos continua multicanal e outros relatórios não carregam platform scope. Um fluxo chamado Instagram deve filtrar ou separar publisher_platform no cliente.

Correção: paid report com platform_scope explícito. A aba geral pode ser Meta Ads; qualquer comparação com Instagram deve usar somente Instagram.

#### P1-06 — moeda e timezone são assumidos

A UI mostra R$ sem consultar account_currency. Datas são criadas no timezone do servidor, não no timezone do ad account.

Correção: buscar currency e timezone_name da conta de anúncios, usar o timezone no contrato de período e formatar a moeda real.

#### P1-07 — CPA e ROAS mudam de definição

CPA representa denominadores diferentes conforme a tela e a quantidade de anúncios. ROAS ignora o campo website_purchase_roas solicitado e usa apenas uma variante de purchase em action_values.

Correção: cada custo deve nomear sua ação; exibir CPL, custo por conversa, custo por outbound click etc. ROAS precisa dizer qual purchase/value usa ou ficar N/D.

#### P1-08 — dark posts e cobertura não são demonstrados

O join de publicações pagas parte do /media. Anúncios sem mídia publicada correspondente podem não entrar, embora a seção afirme cobrir dark posts.

Correção: relatório de cobertura com gasto total de Ads, gasto mapeado a mídia e gasto não mapeado; linha própria para dark posts quando houver identity suficiente.

#### P1-09 — seguidores e demografia não seguem o contrato v26

O código usa follower_count para “Novos Seguidores”, enquanto a tabela v26 documenta follows_and_unfollows com breakdown follow_type. A documentação descreve o total de contas que seguiram e deixaram de seguir/saíram do Instagram; o dashboard deve preservar os valores brutos do breakdown e só nomear ganhos, perdas ou saldo após fixture e reconciliação confirmarem o mapeamento. O argumento timeframe de demografia é criado, mas não enviado; reached_audience_demographics não aparece na tabela vigente.

Correção: usar apenas combinações atualmente documentadas, mostrar limiar mínimo e período efetivo e não chamar mapa vazio de zero.

#### P1-10 — paginação e comentários são parciais

Comentários usam limit=50 por mídia sem seguir o cursor interno. O componente de comentário destaque instancia InstagramClient sem configuração e chama método inexistente. Formulários de leads também não paginam a coleção de formulários.

Correção: paginação completa com proteção contra cursor repetido; parcialidade explícita.

### P2 — qualidade, segurança e observabilidade

- “100% de precisão real” é incompatível com fallbacks, estimativas e atraso da Meta.
- “Cliques no criativo” é calculado como clicks menos outbound_clicks e não corresponde a uma métrica oficial.
- “Top Posts — Maior Alcance Total” ordena apenas reach de Media Insights.
- Stories são buscados, mas o resultado não participa de forma útil da tabela.
- cache de 1 hora e 15 minutos em relatórios relacionados pode gerar valores temporariamente diferentes.
- paginação não possui proteção contra cursor repetido.
- respostas de erro não preservam code, error_subcode, fbtrace_id nem headers de uso para auditoria.
- CI não executa testes e a PR #2 está em draft com o check de Ruff vermelho por 209 ocorrências preexistentes.

## Avaliação da PR #2

### Correções que devem ser aproveitadas

- Graph API v26 explícita nos dois clientes e nos relative URLs de batch.
- likes, comments, views e total_interactions vindos de Media Insights.
- remoção da subtração “mágica” de reach.
- rótulo “Alcance da Conta — inclui anúncios”.
- get_instagram_paid_totals com publisher_platform=instagram.
- agregado multi-ad no nível de conta filtrado para Instagram.
- uso inicial de None em três campos realmente indisponíveis.

### Bloqueadores antes do merge

- Stories v26 ainda usam métricas antigas.
- clicks e link/outbound continuam incorretos.
- leads continuam potencialmente duplicados.
- eventos de messaging continuam sendo chamados de WhatsApp sem confirmar action destination.
- total sintético orgânico + pago continua existindo.
- erros e campos ausentes ainda viram zero.
- métricas únicas ainda são somadas.
- moeda, timezone, atribuição e período efetivo não são transportados.
- não há testes automatizados nem reconciliação ao vivo.

Conclusão: a PR é uma boa base de trabalho, mas não deve ser mesclada no estado atual.

## Arquitetura recomendada

A solução recomendada é contract-first e preserva a estrutura atual API → loader → Streamlit. Não exige banco nem reescrita.

### Relatórios separados

- InstagramMediaReport: identidade da mídia, um grupo de métricas orgânicas confirmadas e outro grupo de Media Insights ainda não rotulado como orgânico.
- InstagramAccountReport: totais de conta explicitamente marcados como incluindo Ads/boosted.
- PaidAdsReport: Ads Insights com platform_scope explícito; para comparação com conteúdo, usar Instagram.
- MediaComparison: união apenas na camada de apresentação, mantendo organic e paid em objetos separados.

### Metadados mínimos

Cada relatório deve carregar:

- source endpoint e Graph API version;
- scope e platform_scope;
- status ok, partial ou unavailable;
- requested_since/until e effective_since/until;
- period_basis: publication_window, media_lifetime_snapshot, account_measurement_window ou ad_delivery_window;
- retrieved_at e timezone;
- truncated e issues.

Valores numéricos devem ser opcionais. None significa indisponível; zero com status ok significa zero real.

### Invariantes obrigatórias

1. Account Insights nunca recebe rótulo orgânico.
2. Orgânico nunca é account total menos Ads.
3. Métrica única nunca é somada entre chunks, posts ou anúncios.
4. Ads em comparação com Instagram usa publisher_platform=instagram.
5. Clicks da raiz nunca é sobrescrito.
6. Link click nunca recebe o rótulo outbound.
7. Lead agregado nunca é somado com seus subtipos.
8. Messaging só recebe o rótulo WhatsApp com destino confirmado.
9. TLS verification permanece habilitada.
10. Falha, ausência e zero permanecem distintos até a UI.
11. Todo card é rastreável a source, scope, período e status.
12. Janela de publicação nunca é apresentada como janela de medição.

## Estratégia de testes

### Testes P0

- parser preserva clicks da raiz;
- link click e outbound click permanecem distintos;
- lead e leadgen não são somados;
- paid totals e mapping ignoram linhas fora de Instagram;
- Media Insights orgânico nunca recebe total_*;
- falha de Media Insights não recorre silenciosamente ao contador visível;
- Account Insights sempre tem escopo including_ads;
- reach e accounts_engaged não são somados entre chunks;
- reach de Ads multi-ad não usa soma como alcance único;
- organic reach e paid reach nunca viram total único;
- zero real, missing, unsupported e error são diferentes;
- resposta parcial nunca é exibida como completa;
- Story v26 usa navigation + breakdown.
- messaging não vira WhatsApp sem action_destination confirmado.
- TLS verification habilitada.

### Reconciliação ao vivo

Antes do merge:

1. capturar payloads sanitizados de imagem, carrossel, Reel, vídeo legado e Story;
2. usar uma mídia nunca promovida e uma promovida;
3. comparar orgânico com Media Insights bruto;
4. confirmar que total_* não aparece como orgânico;
5. comparar Ads com publisher_platform=instagram;
6. usar o mesmo intervalo, timezone, moeda e configuração de atribuição do Ads Manager;
7. testar uma mídia com um anúncio e outra com múltiplos anúncios;
8. medir gasto mapeado e não mapeado, incluindo dark post;
9. testar permissão insuficiente, rate limit e erro no meio da paginação;
10. guardar request, payload, resultado renderizado e divergência explicada.

Critério: payload bruto e dashboard devem bater exatamente, exceto arredondamento de apresentação. Diferença para o Ads Manager precisa ser explicada por configuração, atraso, estimativa ou escopo — nunca corrigida com fórmula inventada.

## Ordem de implementação

1. Criar contratos de scope, status, período e issues.
2. Extrair parsers puros e escrever fixtures/testes antes das correções.
3. Corrigir parser de Ads: clicks, outbound, actions, leads, moeda e timezone.
4. Corrigir Instagram Media/User/Story requests v26 e agrupamentos compatíveis.
5. Separar modelos organic, account e paid; remover fallback silencioso.
6. Corrigir agregações únicas e cobertura de plataforma.
7. Atualizar loader e UI com seções, rótulos e N/D.
8. Adicionar CI de pytest, compileall e política incremental de Ruff.
9. Executar reconciliação ao vivo com credenciais da conta.
10. Tornar a PR pronta e mesclar em main somente com os bloqueadores resolvidos.

## Fontes oficiais

- [Instagram Media Insights](https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media/insights)
- [Instagram Account Insights](https://developers.facebook.com/documentation/instagram-platform/api-reference/instagram-user/insights)
- [Instagram Insights overview](https://developers.facebook.com/documentation/instagram-platform/insights)
- [Instagram Platform changelog](https://developers.facebook.com/documentation/instagram-platform/changelog)
- [Graph API v22 changelog](https://developers.facebook.com/docs/graph-api/changelog/version22.0/)
- [Graph API changelog e versões](https://developers.facebook.com/docs/graph-api/changelog/)
- [Ads Insights API](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights)
- [Ad Account Insights reference](https://developers.facebook.com/documentation/ads-commerce/marketing-api/reference/ad-account/insights)
- [Ads Insights limits and best practices](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights/best-practices)
- [Ads Insights breakdowns](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights/breakdowns)
- [Ads Action Stats v26](https://developers.facebook.com/docs/marketing-api/reference/ads-action-stats/)
- [Ads Insights metric availability updates](https://developers.facebook.com/blog/post/2025/10/16/ads-insights-api-metric-availability-updates/)
- [Coleção oficial Meta Instagram no Postman](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [Coleção oficial Meta Facebook Marketing API no Postman](https://www.postman.com/meta/facebook-marketing-api/folder/zzd6d5p/insights-api)

## Limitações desta auditoria

A análise estática e a documentação oficial permitem determinar o contrato correto e encontrar violações no código. Elas não substituem a reconciliação com uma conta real, porque a Meta usa métricas estimadas, aplica configurações da conta/ad set, possui limiares de privacidade e pode atrasar dados em até 48 horas. A implementação só deve ser declarada reconciliada após o smoke test ao vivo descrito acima.
