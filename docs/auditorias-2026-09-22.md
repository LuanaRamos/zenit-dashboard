# Conferência das auditorias — consolidação 0.1.0

Foram lidos os três relatórios do repositório e confrontados com a branch de consolidação, não tratados como descrição automaticamente atual do sistema:

- `AUDITORIA_GPT5_6_SOL.md`
- `AUDITORIA_VARIAVEIS_META.md`
- `AUDITORIA_INDEPENDENTE_META_API_V26_2026-08-30.md`

## Decisões aplicadas

| Achado dos relatórios | Tratamento nesta consolidação |
| --- | --- |
| Leads orgânicos misturados à página Ads | A página consulta apenas anúncios; removido o loader orgânico deste fluxo. |
| Total de conta tratado como orgânico | Totais de conta saíram do destaque e do cálculo orgânico. |
| Total menos pago / soma de orgânico e pago | Não há derivação desse tipo na página orgânica ativa. Comparação em colunas independentes. |
| Fallback dos Insights para contadores públicos | Fonte visível mantida em campos separados; nunca preenche o orgânico. |
| Curtida líquida, reação e curtida de página confundidas | Comparativo usa eventos distintos para curtidas líquidas e reações, sem fallback de curtida de página; ausência continua indisponível. |
| Erro na paginação de publicações parece conta vazia ou resultado completo | Falha de qualquer página interrompe o relatório orgânico com erro; não publica totais silenciosamente parciais. |
| Erro ou métrica ausente convertido em zero | Campos orgânicos ausentes são opcionais; cobertura parcial aparece nos cards. Erro de consulta do comparativo pago é propagado à seção secundária. |
| Datas de publicação confundidas com janela da métrica | A UI identifica acumulado por publicação e janela de veiculação de Ads; não promete paridade entre universos. |
| Alcance único somado ou subtraído | Não entra nos cards orgânicos. Valores por publicação têm rótulos neutros; soma paga de fallback é identificada como soma. |
| Facebook misturado a comparação Instagram | Mantido filtro explícito por publisher_platform=instagram no mapping. |
| Leads agregado + subtipo / cliques recalculados por engajamento | Normalização corrigida e coberta por testes de sobreposição e preservação de zero. |
| CPA combinado de leads e conversas | Retirado; custos específicos por lead e conversa. |
| Mensagens genericamente rotuladas como WhatsApp | Rótulos públicos de conversas e mensagens; destino só quando há dado do criativo. |
| Destaques com alcance/pago e falha de cliente sem configuração | Ranking por interações orgânicas confirmadas; sem consulta inválida de comentários por card. |
| TLS desativado e tratamento incorreto de 401 | Verificação TLS reativada; Response é comparado a None, não por truthiness. |
| Campos legados / versão do Batch | Migração v26 preservada da branch anterior; feed também solicita views. |
| Catálogo incompleto e excesso de carregamento | Catálogo retirado da navegação principal; público, criativos e comparações carregados por seleção. |

## Achados históricos

Alguns trechos citados nas primeiras auditorias já não existiam na base consultada: fields de objeto `saved_count/shares_count/reposts_count`, schema Instagram duplicado e parte da subtração de alcance. A branch v26 já corrigia o ID legado de mídia e isolava parte dos placements. A consolidação preservou essas correções em vez de reaplicar patches antigos.

## Trabalho ainda necessário

A versão 0.1.0 não declara todas as auditorias resolvidas:

- Reconciliação com payloads reais, mesma atribuição, fuso, moeda e período do Ads Manager.
- Metadados de moeda e timezone por cliente; valores monetários ainda seguem a apresentação BRL existente.
- Contrato de erro/parcial/indisponível uniforme nos relatórios legados, sobretudo demografia, criativos e Account Insights.
- Account Insights legado ainda soma janelas para métricas únicas; não é usado no destaque orgânico desta versão.
- Migração completa de Stories/navigation e de séries de seguidores; não compõem os cards principais.
- Cobertura de dark posts e gasto não mapeado a publicações: aparecem no universo de campanhas Ads, mas não no comparativo por publicação.
- Paginação e completude dos comentários históricos; a UI os identifica como dados consultados.
- Deduplicação do alcance pago por mídia com vários anúncios: quando a consulta agregada falha, o código legado mantém soma; a apresentação não a chama de pessoas únicas.
- Preservação abrangente de taxonomias brutas e seus metadados em todos os relatórios, além dos parsers corrigidos.

Fontes oficiais usadas para a semântica dos campos: [Media Insights](https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media/insights), [User Insights](https://developers.facebook.com/documentation/instagram-platform/api-reference/instagram-user/insights), [Ads Insights](https://developers.facebook.com/docs/marketing-api/insights/).
