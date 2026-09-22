# Zenit Analytics

Painel Streamlit para acompanhar campanhas Meta Ads e conteúdo orgânico do Instagram. Versão consolidada: **0.1.0**.

## Organização

- **Ads:** indicadores, campanhas, público pago e criativos, com dados da conta de anúncios.
- **Orgânico:** interações, curtidas, comentários e visualizações de Media Insights em destaque; tabela orgânica e publicações de maior interação.
- **Comparativo:** seção recolhida e carregamento opcional de Ads do Instagram vinculados às publicações selecionadas. Não representa todos os anúncios da conta nem inclui dark posts sem vínculo com publicações.

O filtro orgânico seleciona **data de publicação**. As métricas são o acumulado das publicações até a consulta. Ads usa **datas de veiculação**. A comparação é descritiva, não uma decomposição exata de um total. Dados ausentes aparecem como N/D e somas parciais identificam a cobertura. Alcance, salvamentos e compartilhamentos de Media Insights permanecem em detalhes com rótulos neutros.

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
