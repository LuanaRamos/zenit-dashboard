"""Zenit Analytics: fontes pagas e orgânicas separadas desde o carregamento."""

import logging
import os
import sys
from pathlib import Path

import sentry_sdk
import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

logger = logging.getLogger(__name__)


def configure_page():
    icon = DASHBOARD_DIR / "assets" / "zenit_logo.png"
    st.set_page_config(
        page_title="Zenit Analytics",
        page_icon=str(icon) if icon.exists() else ":material/analytics:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    css = DASHBOARD_DIR / "ui" / "style.css"
    if css.exists():
        st.markdown(
            f"<style>{css.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )
    if os.getenv("SENTRY_DSN"):
        sentry_sdk.init(
            dsn=os.environ["SENTRY_DSN"],
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            release=os.getenv("SENTRY_RELEASE", "0.1.0"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        )


def report_error(message, error):
    logger.error(message, exc_info=error)
    sentry_sdk.capture_exception(error)
    st.error(f"{message}\n\nFalha registrada para diagnóstico. Nenhum token ou detalhe técnico é exibido.")


def render_ads_page(date_preset, time_range, client):
    from ui.components import (
        render_general_campaigns,
        render_metric_cards,
        render_objective_pie_chart,
        render_profile_campaigns,
        render_whatsapp_campaigns,
        render_whatsapp_cost_chart,
        render_campaign_highlight,
    )
    from ui.data_loader import fetch_campaigns_v8

    st.title("Desempenho dos anúncios")
    st.caption(f"{client.name} · Meta Ads · Dados do período selecionado.")
    try:
        with st.spinner("Carregando anúncios..."):
            campaigns = fetch_campaigns_v8(date_preset, time_range, client.name)
    except Exception as error:
        from ui.ads_diagnostics import render_ads_diagnostic
        render_ads_diagnostic(client, error, stage="consulta de campanhas")
        return
    if not campaigns:
        st.info("Nenhum resultado de anúncios disponível para este período.")
        return

    # Seleção explícita evita buscar público/criativos em cada visita ao resumo.
    section = st.radio(
        "Análise de anúncios",
        ["Visão geral", "Público dos anúncios", "Criativos"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"ads_section_{client.name}",
    )
    if section == "Público dos anúncios":
        from ui.demographics_components import render_demographics_tab

        render_demographics_tab(date_preset, time_range, client.name)
        return
    if section == "Criativos":
        from ui.creatives_components import render_creatives_tab

        render_creatives_tab(date_preset, time_range, client.name)
        return

    total_spend = sum(c.spend for c in campaigns)
    total_leads = sum(c.leads for c in campaigns)
    total_messages = sum(c.whatsapp_starts for c in campaigns)
    leads_spend = sum(
        c.spend
        for c in campaigns
        if c.leads > 0 or c.objective in {"OUTCOME_LEADS", "LEAD_GENERATION"}
    )
    # Métrica da CONTA: inclui todo o gasto, inclusive anúncios sem conversa.
    # Não pressupõe que OUTCOME_ENGAGEMENT foi uma campanha de WhatsApp.
    from schemas.meta import cost_per_account_conversation

    cpl = leads_spend / total_leads if total_leads else None
    cost_per_message = cost_per_account_conversation(campaigns)
    render_metric_cards(
        total_spend, total_leads, cpl, total_messages, cost_per_message
    )

    messages = [
        c for c in campaigns if c.whatsapp_starts > 0 or c.objective == "MESSAGES"
    ]
    profile = [
        c
        for c in campaigns
        if c not in messages and (c.instagram_follows > 0 or c.profile_visits > 0)
    ]
    other = [c for c in campaigns if c not in messages and c not in profile]
    if any(item.whatsapp_starts > 0 for item in campaigns):
        overview, distribution = st.columns([1.35, 1])
        with overview:
            render_campaign_highlight(campaigns)
        with distribution:
            render_objective_pie_chart(campaigns)
    else:
        render_objective_pie_chart(campaigns)

    if messages:
        render_whatsapp_cost_chart(messages)
    render_whatsapp_campaigns(messages)
    render_profile_campaigns(profile)
    render_general_campaigns(other)


def render_organic_page(date_preset, time_range, client):
    from ui import data_loader
    from ui.organic_components import (
        render_followers_timeline,
        render_historic_top_comment,
        render_meta_content_import,
        render_metric_card,
        render_organic_history_summary,
        render_organic_metrics_cards,
        render_account_engagement_summary,
        render_posts_table,
        render_top_posts_and_comments,
    )

    st.title("Instagram")
    st.caption(f"{client.name} · Atividade da conta no período selecionado.")

    # Primeiro bloco visível: atividade do período, independente da data
    # de publicação dos posts listados nas abas abaixo.
    account_insights = {}
    try:
        with st.spinner("Consultando engajamento da conta no período..."):
            account_insights = data_loader.fetch_account_insights_cached(
                client.name, date_preset, time_range
            )
    except Exception as error:
        logger.warning("Não foi possível carregar Insights da conta: %s", error)

    render_account_engagement_summary(account_insights)

    st.divider()
    st.caption("Publicações: filtro por data de postagem; resultados acumulados desde a publicação.")

    tab_posts, tab_growth, tab_audience = st.tabs([
        "Publicações",
        "Seguidores",
        "Audiência",
    ])

    with tab_posts:
        media = []
        try:
            with st.spinner("Carregando publicações orgânicas..."):
                media = data_loader.fetch_organic_media(date_preset, time_range, client.name)
        except Exception as error:
            logger.error(f"Erro ao carregar publicações orgânicas de {client.name}: {error}")
            sentry_sdk.capture_exception(error)
            st.warning("Publicações indisponíveis. Consulte Diagnóstico e cobertura ou tente atualizar.")
            media = []

        if not media:
            st.info("Nenhuma publicação encontrada no período selecionado.")
        else:
            if date_preset == "maximum":
                render_organic_history_summary(media)

            media = render_meta_content_import(media, client.name)

            # 2. Desempenho orgânico das publicações
            render_organic_metrics_cards(media)

            # 3. Ranking de publicações ordenado primariamente por alcance (reach)
            render_top_posts_and_comments(media)

            # 4. Comentário mais curtido em destaque com download CSV rápido
            render_historic_top_comment(client.name, media)

            # 5. Tabela de publicações orgânicas com filtros
            render_posts_table(media)

        if client.has_ads:
            with st.expander("Comparativo com anúncios do Instagram", expanded=False):
                st.caption(
                    "Consulta opcional de anúncios vinculados às publicações acima. "
                    "Os resultados pagos não entram nos indicadores orgânicos."
                )
                if st.checkbox("Carregar comparação com Ads", key=f"compare_ads_{client.name}"):
                    try:
                        from ui.organic_components import render_paid_comparison
    
                        with st.spinner("Carregando comparação..."):
                            compared = data_loader.enrich_media_with_ads(
                                media, date_preset, time_range, client.name
                            )
                        render_paid_comparison(compared)
                    except Exception as error:
                        sentry_sdk.capture_exception(error)
                        st.warning(
                            "Comparativo pago indisponível no momento. Os resultados orgânicos acima continuam disponíveis."
                        )
    
    with tab_growth:
        st.markdown("### Seguidores")
        try:
            with st.spinner("Carregando evolução de seguidores..."):
                followers_history = data_loader.fetch_followers_history_cached(client.name)
            if followers_history:
                render_followers_timeline(followers_history)
            else:
                st.caption("Histórico diário não disponível nesta conta.")
        except Exception as error:
            logger.warning("Falha no histórico de seguidores de %s: %s", client.name, error)
            sentry_sdk.capture_exception(error)
            st.caption("Histórico diário indisponível.")

        if account_insights:
            insights = account_insights

            def _fmt(val):
                if val is None:
                    return "N/D"
                try:
                    return f"{int(val):,}".replace(",", ".")
                except (TypeError, ValueError):
                    return "N/D"

            st.markdown("### Ações no perfil")
            cols_act = st.columns(4)
            with cols_act[0]:
                render_metric_card(
                    "Visitas ao perfil", _fmt(insights.get("profile_views")),
                    "Conta · Período selecionado",
                )
            with cols_act[1]:
                render_metric_card(
                    "Toques em botões", _fmt(insights.get("profile_links_taps")),
                    "Ações de contato",
                )
            with cols_act[2]:
                render_metric_card(
                    "Cliques no site", _fmt(insights.get("website_clicks")),
                    "Métrica da API",
                )
            with cols_act[3]:
                render_metric_card(
                    "Toques no endereço", _fmt(insights.get("business_address_taps")),
                    "Métrica não confirmada",
                )
            st.caption("Detalhes da fonte e dos períodos: Diagnóstico e cobertura, na visão geral.")

    with tab_audience:
        # Demografia e Audiência do Instagram
        try:
            from ui.demographics_components import render_demographics_dashboard

            with st.spinner("Carregando dados de audiência..."):
                demographics = data_loader.fetch_account_demographics(client.name)
            if demographics:
                render_demographics_dashboard(demographics)
            else:
                st.info("Dados demográficos de audiência indisponíveis para esta conta.")
        except Exception as error:
            logger.warning(f"Erro ao carregar dados demográficos de {client.name}: {error}")
            sentry_sdk.capture_exception(error)
            st.warning("Dados de audiência indisponíveis no momento.")


def main():
    configure_page()
    try:
        from ui.layouts import render_sidebar

        module, date_preset, time_range, client = render_sidebar()
        if module == "Visão Geral (Ads)":
            try:
                render_ads_page(date_preset, time_range, client)
            except Exception as error:
                from ui.ads_diagnostics import render_ads_diagnostic
                render_ads_diagnostic(client, error, stage="renderização dos anúncios")
        else:
            render_organic_page(date_preset, time_range, client)
    except Exception as error:
        report_error(
            "Não foi possível carregar esta área. Verifique a configuração da conta e tente novamente.",
            error,
        )


if __name__ == "__main__":
    main()
