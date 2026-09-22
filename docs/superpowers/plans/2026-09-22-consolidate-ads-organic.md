# Consolidar Ads e Orgânico

**Objetivo:** integrar o melhor das branches existentes, mantendo Ads exclusivamente pago e dando destaque apenas às métricas orgânicas confirmadas na área Instagram.

**Base:** main a1af0c4; codex/meta-v26-organic-metrics 1c9369e, 9 commits à frente e nenhum atrás. Sem tags existentes. PR #1 está fechado sem merge e seu ajuste de import já existe na main. PR #2 é a migração v26 em rascunho.

**Decisão:** partir da branch v26, que já contém integralmente a main e seu visual dourado. Preservar o histórico; incorporar correções de fonte e apresentação necessárias ao pedido atual. Planos antigos descrevem trabalho futuro, não funcionalidades já prontas.

## Contrato desta entrega

- Ads usa exclusivamente Ads Insights. Não consulta nem soma leads orgânicos.
- Cards orgânicos usam likes, comments, views e total_interactions de Media Insights. Nunca contadores visíveis como fallback, totais de conta ou subtração de Ads.
- Ausente é N/D; zero confirmado continua zero. Somas parciais mostram cobertura.
- Dados pagos da área Instagram ficam em comparativo recolhido, carregado somente por opção explícita, restrito ao Instagram e aos posts mapeados.
- Métricas acumuladas de posts selecionados por data de publicação e métricas pagas de um período têm escopos diferentes, declarados na comparação. Não criar total orgânico + pago.
- Reach, saved e shares de Media Insights recebem rótulos neutros em detalhes; alcance somado não representa pessoas únicas.
- Falha de Ads não impede ver os dados orgânicos. Filtro sem resultados não gera exceção.
- Preservar marca, tabelas exportáveis e módulos Ads úteis; retirar catálogo incompleto da navegação principal.

## Tarefas e verificação

1. Backend: testes de payload incompleto, fonte orgânica, exclusão de Facebook e independência do carregamento. Alterar API/schema/data_loader. Interface: fetch_organic_media(date_preset, time_range, client_name), enrich_media_with_ads(media_list, date_preset, time_range, client_name).
2. UI orgânica: testes de cards sem valores pagos, ausência/zero, comparação secundária e filtro vazio. Alterar organic_components e helpers. Interface: render_organic_metrics_cards(media_list), render_posts_table(media_list, stories_list=[]), render_paid_comparison(media_list).
3. App/Ads: testes Streamlit com fixtures de Ads e ausência de consultas secundárias por padrão. Separar páginas e manter precisão monetária. Verificar erro isolado do comparativo.
4. Versionamento: remover bytecode versionado, corrigir gitignore UTF-16, registrar primeira versão consolidada 0.1.0 e changelog, adicionar suíte ao CI.
5. Executar pytest, compileall e Ruff; revisão independente do diff. Integrar mediante PR com testes registrados, preservando os commits anteriores e sem force push.

## Limites

Sem credenciais reais nesta execução: testes locais usam respostas controladas. Não declarar reconciliação com o Ads Manager nem publicação do serviço. Erros de métricas pagas não relacionadas à separação de canais serão registrados, sem reescrever toda a integração.
