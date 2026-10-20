# Zenit Analytics

Painel Streamlit para acompanhar campanhas Meta Ads e conteúdo orgânico do Instagram. Versão consolidada: **0.1.0**.

## Organização

- **Ads:** indicadores, campanhas, público pago e criativos, com dados da conta de anúncios.
- **Orgânico:** interações, curtidas, comentários e visualizações de Media Insights em destaque; tabela orgânica e publicações de maior interação.
- **Comparativo:** seção recolhida e carregamento opcional de Ads do Instagram vinculados às publicações selecionadas. Não representa todos os anúncios da conta nem inclui dark posts sem vínculo com publicações.

O filtro orgânico seleciona **data de publicação**. As métricas são o acumulado das publicações até a consulta. Ads usa **datas de veiculação**. A comparação é descritiva, não uma decomposição exata de um total. Dados ausentes aparecem como N/D e somas parciais identificam a cobertura. Alcance, salvamentos e compartilhamentos de Media Insights permanecem em detalhes com rótulos neutros.

No Instagram, **Histórico disponível** percorre todas as páginas sem corte por data, até a publicação mais antiga que a API disponibilizar para o perfil selecionado. O tamanho de 100 itens por página não limita o total. A busca continua mesmo após uma página vazia com continuação, remove publicações repetidas e informa erro se a paginação travar, em vez de apresentar um histórico parcial como completo. O painel mostra a quantidade e o período das publicações carregadas. O intervalo de Ads não limita essa busca. Publicações excluídas ou indisponíveis na API não podem ser recuperadas por essa consulta.

O CSV orgânico inclui o ID da publicação, a legenda completa e os links da mídia principal e da miniatura para pesquisa de conteúdo. Esses links não incluem todas as páginas dos carrosséis nem texto extraído das imagens.

O CSV de comentários inclui `media_id` e, quando a publicação está no período carregado, `media_permalink`. A consulta considera até 30 publicações e a primeira página de até 25 comentários por publicação. O arquivo representa os comentários consultados, sem garantir cobertura completa do histórico ou das respostas.

## Executar

Python 3.11 ou superior:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run src/dashboard/app.py
```

Configure `META_MASTER_TOKEN` e `CLIENTS_JSON` no ambiente ou em `.env` local. Cada entrada de `CLIENTS_JSON` contém `name`, `ad_account_id`, `page_id` e, opcionalmente, `token`. Nunca versione tokens. `SENTRY_DSN` é opcional.

## Validar

```sh
python -m pytest -q
python -m ruff check src/ tests/
python -m compileall -q src/dashboard
```

Os testes bloqueiam chamadas reais à Meta e usam fixtures. Eles verificam separação de fontes, valores ausentes/zero, isolamento de falhas e renderização Streamlit. Não substituem a conferência com uma conta real e o mesmo período, fuso, moeda e atribuição no Ads Manager.

## Histórico e auditorias

A consolidação preserva a `main` em `a1af0c4` e os nove commits da branch `codex/meta-v26-organic-metrics` até `1c9369e`. Não havia tags no repositório consultado. O ajuste de imports do PR #1 já estava presente na `main`; a migração do PR #2 foi incorporada e revisada.

Consulte [CHANGELOG.md](CHANGELOG.md), [o plano desta consolidação](docs/superpowers/plans/2026-09-22-consolidate-ads-organic.md) e [o acompanhamento das auditorias](docs/auditorias-2026-09-22.md). Auditorias descrevem achados no momento em que foram escritas; planos antigos não são evidência de funcionalidades implementadas.
