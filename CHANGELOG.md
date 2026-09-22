# Histórico de versões

## 0.1.0 — 2026-09-22

Primeira versão identificada desta consolidação, sobre `main` a1af0c4 e `codex/meta-v26-organic-metrics` 1c9369e.

- Preserva a identidade dourada, logo, gráficos, tabelas e a migração Graph API v26.
- Remove leads orgânicos da visão de anúncios e o CPA combinado de leads com conversas.
- Preserva cliques oficiais de Ads, distingue cliques no link e de saída e elimina dupla contagem de leads e conversas.
- Separa curtidas líquidas de reações pagas no comparativo e usa rótulos de mensagens sem presumir WhatsApp.
- Separa carregamento orgânico de Ads; coloca comparação paga em seção opcional e recolhida.
- Destaca somente quatro métricas orgânicas confirmadas de Media Insights.
- Elimina fallback silencioso para contadores visíveis e diferencia ausência de zero.
- Propaga falhas na paginação orgânica e exibe leads pagos agregados mesmo quando o detalhamento por fonte está ausente.
- Explica datas de publicação versus janelas de anúncios, cobertura parcial e limites do mapeamento.
- Corrige filtro de formato sem resultados e a seleção de destaques com métricas indisponíveis.
- Mantém público e comentários como contexto opcional do perfil; retira catálogo incompleto da navegação principal.
- Restaura verificação TLS, corrige tratamento HTTP 401 e preserva o orgânico quando Ads falha.
- Remove bytecode versionado, corrige `.gitignore`, adiciona testes e validação no CI.

Validação com fixtures; reconciliação com dados reais da conta ainda depende de credenciais e configurações de atribuição correspondentes.
