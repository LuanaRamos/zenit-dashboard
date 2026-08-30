# Design: contrato confiável de métricas Meta v26

Data: 30 de agosto de 2026

Status: aprovado para planejamento

Base: PR #2, codex/meta-v26-organic-metrics

Auditoria relacionada: [auditoria independente](../../../AUDITORIA_INDEPENDENTE_META_API_V26_2026-08-30.md)

## Objetivo

Garantir que o Zenit Dashboard:

- apresente como orgânico somente o que a Meta documenta como orgânico;
- apresente como pago somente Ads Insights no escopo de plataforma declarado;
- não misture Account Insights com Media Insights ou Ads Insights;
- não transforme erro, ausência ou resposta parcial em zero;
- permita rastrear cada valor até endpoint, escopo, período e status.

O desenho preserva a arquitetura atual de clientes de API, data loader e componentes Streamlit. Não adiciona banco, fila ou framework genérico de métricas.

## Abordagens avaliadas

### A. Patch mínimo de campos e rótulos

Corrigiria os campos mais visíveis diretamente nos clientes e componentes atuais.

Vantagem: mudança menor e rápida.

Desvantagem: o mesmo modelo continuaria contendo orgânico e pago; novos fallbacks poderiam voltar a misturar escopos. Não resolve rastreabilidade nem estados de erro.

### B. Contrato por dataset, com escopos separados — escolhida

Introduz relatórios tipados para orgânico, conta e Ads; separa identidade da mídia das métricas; transporta metadados de fonte, período e qualidade.

Vantagem: corrige a causa sem reescrever o dashboard. Permite testes puros e impede regressão por design.

Desvantagem: exige alterar schemas, loaders e componentes em conjunto.

### C. Persistência histórica ou data warehouse

Salvaria todos os payloads e snapshots para auditoria temporal completa.

Vantagem: máxima rastreabilidade e séries históricas próprias.

Desvantagem: amplia escopo operacional, segurança e custo sem ser necessário para corrigir o produto atual.

Decisão: abordagem B.

## Vocabulário de domínio

### Escopos

- organic_media: Media Insights de conteúdo, limitado às métricas com garantia orgânica.
- media_insights: métrica de mídia cujo escopo é conhecido, mas sem garantia textual suficiente para usar “orgânico” no rótulo.
- account_total_including_ads: Instagram Account Insights que inclui Ads ou conteúdo boosted.
- paid_ads: Ads Insights.
- mixed_visible_count: contador visível do objeto, mantido separado e nunca usado como fallback orgânico.

### Plataforma paga

Paid Ads precisa declarar platform_scope:

- instagram: somente publisher_platform=instagram;
- all_meta: todas as plataformas presentes no relatório;
- conjunto explícito de plataformas quando a UI oferecer filtro.

A comparação com conteúdo do Instagram só aceita instagram. A aba geral de Ads pode usar all_meta, mas precisa mostrar o escopo.

### Status

- ok: payload completo para o contrato solicitado;
- partial: uma ou mais páginas, grupos ou métricas falharam;
- unavailable: a métrica não foi retornada, não é suportada ou não há permissão;
- empty: a API respondeu com conjunto vazio válido.

Zero só é válido com status ok ou empty. Valor ausente usa None.

Cada campo ausente recebe uma issue com metric_name e reason: not_applicable, not_returned, permission_denied, deprecated, unsupported ou error. Isso preserva a diferença sem criar um wrapper genérico para cada número.

### Bases de período

- publication_window: período usado para selecionar mídias pela data de publicação;
- media_lifetime_snapshot: acumulado da mídia até o momento da coleta;
- account_measurement_window: intervalo de Account Insights;
- ad_delivery_window: intervalo de Ads Insights;
- active_story_window: Story ainda ativo, com restrições próprias.

## Modelo de dados

### DatasetMeta

Novo schema compartilhado em src/dashboard/schemas/metrics.py:

- source_endpoint: str;
- api_version: str;
- metric_scope: enum;
- platform_scope: str ou conjunto;
- status: enum;
- requested_since e requested_until: date opcionais;
- effective_since e effective_until: date opcionais;
- period_basis: enum;
- retrieved_at: datetime;
- timezone: str opcional;
- currency: str opcional;
- truncated: bool;
- issues: lista de mensagens estruturadas.

Metadados ficam no relatório, não em cada número. Isso evita um wrapper genérico excessivo por métrica.

Quando um relatório contém mais de um escopo, cada grupo usa ScopedMetricGroup com scope, status e issues próprios. DatasetMeta mantém apenas os dados comuns de request, versão e período.

### Identidade e métricas de mídia

O atual InstagramMedia mistura identidade, orgânico e Ads. Ele será dividido em:

- MediaIdentity: id, caption, URL, permalink, timestamp, media type e product type;
- OrganicMediaMetrics: comments, likes, views, total_interactions;
- MediaInsightMetrics: reach, saved, shares e métricas de watch time;
- VisibleMediaCounters: like_count/comments_count do objeto, se necessários;
- PaidMediaMetrics: reach, impressions, clicks, inline_link_clicks, outbound_clicks, spend, actions e metadados de entrega;
- MediaComparison: identity + organic/media insights + paid opcional.

PaidMediaMetrics nunca é copiado para OrganicMediaMetrics. VisibleMediaCounters nunca substitui falha de Media Insights.

### Relatórios

#### InstagramMediaReport

- items: lista de mídia; cada item contém identity e três grupos tipados independentes;
- organic por item: ScopedMetricGroup de comments, likes, views e total_interactions;
- media_insights por item: ScopedMetricGroup de reach, saved, shares e watch time;
- visible_counters por item: ScopedMetricGroup separado para contadores públicos do objeto;
- meta: DatasetMeta comum;
- publication_selection: período de seleção;
- measurement_note: snapshot/lifetime e possível atraso.

O relatório não fabrica um agregado top-level desses grupos. A comparação com Ads é construída depois, no loader, por `identity.id`, sem copiar valores pagos para o item orgânico.

#### InstagramAccountReport

- metrics: reach, accounts_engaged, total_interactions e demais totais compatíveis;
- meta: DatasetMeta com account_total_including_ads;
- segment_results opcionais para janelas que não podem ser agregadas;
- nenhum campo organic_reach.

#### PaidAdsReport

- totals;
- campaigns;
- creatives;
- by_media;
- unmapped;
- raw_actions e raw_action_values preservados;
- meta com platform_scope, moeda, timezone e ad delivery window.

O mesmo tipo pode representar all_meta ou instagram. A UI decide onde cada instância é válida.

Actions e action_values também preservam as linhas brutas e todas as dimensões. Índices derivados usam chave composta por action_type, action_destination, demais breakdowns e janela de atribuição; um dicionário simples por action_type não pode descartar linhas.

## Clientes e parsing

### InstagramClient

O cliente continua responsável por requests e paginação. Parsing e classificação vão para funções puras testáveis.

Media Insights:

- grupos de métricas compatíveis por media type;
- comments, likes, views e total_interactions classificados como organic_media;
- total_comments, total_likes e total_views nunca entram no objeto orgânico;
- reach, saved e shares classificados como media_insights até validação ao vivo;
- nenhuma leitura silenciosa de video_views;
- falha de grupo vira issue/status, não zero.

Story Insights:

- navigation solicitado separadamente com breakdown story_navigation_action_type;
- mapear os valores documentados de navigation de forma case-insensitive;
- requests com breakdown incompatível não são agrupados;
- classificar code, error_subcode e message; audiência insuficiente só é usada quando a resposta a identifica.

Account Insights:

- requests agrupados por compatibilidade de metric_type, breakdown e timeframe;
- reach, accounts_engaged e total_interactions sempre account_total_including_ads;
- follows_and_unfollows usa follow_type;
- preservar o breakdown bruto de follows_and_unfollows; nomes de ganho, perda e saldo exigem fixture e reconciliação com a conta;
- demografia usa apenas métricas e timeframes documentados;
- métricas únicas não são somadas entre chunks;
- User Metrics respeitam retenção oficial de até 90 dias;
- se o intervalo não puder ser retornado como agregado único, conservar segmentos e marcar partial/not_aggregable.

### MetaAdsClient

- preservar clicks da raiz;
- modelar inline_link_clicks e outbound_clicks separadamente;
- preservar raw_actions/raw_action_values e derivar índices com chave composta;
- não somar lead agregado e leadgen;
- não chamar um action type de messaging de WhatsApp sem action_destination ou metadado equivalente;
- cada CPL/CPA usa um denominador nomeado;
- paid comparison com Instagram mantém apenas publisher_platform=instagram;
- aba Meta Ads declara all_meta ou breakdown atual;
- buscar account_currency e timezone_name;
- buscar e persistir attribution_spec de cada ad set usado, além das janelas retornadas nas actions;
- reach multi-ad só é único quando vem de consulta agregada válida;
- fallback de soma não substitui reach único;
- registrar que action_report_time e use_unified_attribution_setting são ignorados e que o report time efetivo é mixed;
- não esperar 7d_view ou 28d_view em action_attribution_windows na v26.
- aplicar limites de histórico por métrica e breakdown: até 37 meses no caso geral e limites menores para métricas únicas com breakdown; nunca rotular 395 dias como maximum.

## Orquestração

ui/data_loader.py:

- solicita relatórios completos, sem model_copy para injetar paid no objeto orgânico;
- une relatórios somente pela identity em MediaComparison;
- mantém gasto não mapeado a uma mídia publicada;
- propaga status e issues sem engolir erros;
- usa a mesma política de cache para relatórios comparados ou mostra retrieved_at diferente.

## Interface

### Estrutura

1. Conteúdo orgânico — Media Insights.
2. Total da conta — inclui anúncios/impulsionados.
3. Pago — Ads Insights, com plataforma explícita.

### Regras de apresentação

- None é “N/D”, nunca 0.
- Partial mostra aviso junto ao conjunto afetado.
- Todo bloco mostra fonte, período efetivo e última coleta.
- Não existe card de alcance único organic + paid.
- Soma de reach por publicação usa o texto “soma de alcances por item — não deduplicada”.
- Inline link click usa “Cliques no link”.
- Outbound click usa “Cliques de saída”.
- Messaging usa “Conversas por mensagem”; WhatsApp exige destino confirmado.
- CPA/CPL inclui o nome da ação no título.
- Moeda vem da conta.
- “100% de precisão real” é removido.
- O filtro de data explica se controla publicação, medição ou entrega.

### Dark posts e cobertura

O módulo pago mostra:

- investimento total no escopo;
- investimento associado a uma mídia publicada;
- investimento não mapeado;
- percentual de cobertura do mapping.

Não será usado o título “dark posts cobertos” enquanto a cobertura não for demonstrada.

## Erros e observabilidade

Issues estruturadas devem registrar:

- endpoint/grupo afetado;
- tipo: permission, unsupported_metric, rate_limit, network, parse, partial_pagination ou not_aggregable;
- mensagem segura;
- code, error_subcode, fbtrace_id e IDs necessários para diagnóstico, sem token;
- headers X-App-Usage, X-Page-Usage e X-Business-Use-Case-Usage quando presentes;
- se o resultado pode ser exibido.

Retry usa exponential backoff com jitter apenas para erros transitórios e rate limit. TLS verification volta a ser habilitada. Tokens nunca entram em fixtures ou logs.

TLS verification, code/error_subcode/fbtrace_id e sucesso individual de cada subrequest de batch são bloqueadores de merge, não melhoria posterior.

## Estratégia de testes

### TDD

Cada correção começa com um teste falhando usando fixture sanitizada. Produção só muda após a falha esperada.

### P0

- clicks da raiz preservado;
- link e outbound distintos;
- lead agregado e subtipo não somados;
- messaging não recebe o rótulo WhatsApp sem destino confirmado;
- total pago Instagram ignora Facebook;
- mapping pago ignora outras plataformas;
- organic_media aceita apenas os campos orgânicos documentados;
- total_* nunca classificado como orgânico;
- contador visível não faz fallback orgânico;
- Account Insights sempre including_ads;
- reach único não pode usar sum;
- zero, missing, unsupported e error distintos;
- paginação parcial marcada;
- Story navigation v26 parseado.
- retenção de User Metrics limitada a 90 dias e Ads com política específica por métrica/breakdown.

### P1

- período pedido e efetivo;
- moeda/timezone não hardcoded;
- UI sem “orgânico” em Account Insights;
- UI com N/D;
- UI com plataforma paga;
- cursor repetido interrompe paginação e marca partial;
- toda métrica exibida tem dataset meta.

### Integração e live smoke

Fixtures ficam em tests/fixtures. Testes live usam marker próprio e não rodam no CI comum.

Reconciliação live:

- publicação não promovida e promovida;
- imagem, carrossel, Reel e Story;
- um anúncio e múltiplos anúncios por mídia;
- placements Instagram e Facebook no mesmo período;
- dark post;
- período encerrado há pelo menos 48 horas;
- mesma moeda, timezone e configuração de atribuição do Ads Manager;
- payload, resultado parseado e UI registrados sem segredos.
- probe comparativo v25/v26 em ativos controlados antes de remover a possibilidade de rollback.

## CI

Adicionar:

- pytest para unit, contract e integration sem live;
- compileall sem gerar artefatos versionados;
- Ruff incremental: arquivos alterados precisam passar, enquanto a dívida antiga é tratada separadamente;
- live smoke manual ou agendado apenas com secrets adequados.

## Migração

1. Introduzir metrics.py e testes de contrato.
2. Corrigir parsers Ads sem mudar a UI.
3. Corrigir grupos Instagram/User/Story.
4. Criar relatórios e adaptar data loader.
5. Migrar componentes para os três blocos.
6. Remover campos mistos e fallbacks antigos.
7. Rodar reconciliação ao vivo.
8. Marcar PR #2 pronta e mesclar em main.

Durante a migração, adapters temporários podem manter componentes antigos funcionando, mas devem ser removidos antes do merge.

## Fora de escopo desta entrega

- banco ou warehouse histórico;
- scheduler de coleta;
- nova autenticação Meta;
- previsão ou modelagem estatística;
- correção completa dos 209 itens históricos de Ruff;
- redesign visual amplo sem relação com rastreabilidade.

## Critérios de aceite

- todos os testes P0 e P1 passam;
- CI novo fica verde nos arquivos tocados;
- nenhuma UI chama Account Insights de orgânico;
- nenhum alcance único é soma de subconjuntos;
- nenhum zero representa erro ou ausência;
- valores Ads preservam os campos oficiais e o escopo da plataforma;
- payload bruto e dashboard reconciliam no smoke test, salvo arredondamento documentado;
- diferenças para Ads Manager têm explicação rastreável;
- PR #2 deixa de ser draft;
- merge em main ocorre somente após estes critérios.
