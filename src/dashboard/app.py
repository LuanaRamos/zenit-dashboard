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
        page_icon=str(icon) if icon.exists() else "📈",
        layout="wide",
        initial_sidebar_state="expanded",
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
    st.error(f"{message}\n\nDetalhes do erro: {type(error).__name__} - {error}")


def render_ads_page(date_preset, time_range, client):
    from ui.components import (
        render_general_campaigns,
        render_metric_cards,
        render_objective_pie_chart,
        render_profile_campaigns,
        render_whatsapp_campaigns,
        render_whatsapp_cost_chart,
    )
    from ui.data_loader import fetch_campaigns_v8

    st.title("Desempenho dos anúncios")
    st.markdown(f"Resultados pagos de **{client.name}**.")
    st.caption(
        "Fonte: Meta Ads · Campanhas e posicionamentos da conta de anúncios no período selecionado."
    )
    with st.spinner("Carregando anúncios..."):
        campaigns = fetch_campaigns_v8(date_preset, time_range, client.name)
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
    messages_spend = sum(
        c.spend
        for c in campaigns
        if c.whatsapp_starts > 0 or c.objective == "MESSAGES"
    )
    cpl = leads_spend / total_leads if total_leads else None
    cost_per_message = messages_spend / total_messages if total_messages else None
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
    chart1, chart2 = st.columns(2)
    with chart1:
        render_objective_pie_chart(campaigns)
    with chart2:
        render_whatsapp_cost_chart(messages)
    render_whatsapp_campaigns(messages)
    render_profile_campaigns(profile)
    render_general_campaigns(other)


def render_organic_page(date_preset, time_range, client):
    from ui import data_loader
    from ui.organic_components import (
        render_followers_timeline,
        render_historic_top_comment,
        render_metric_card,
        render_organic_metrics_cards,
        render_posts_table,
        render_profile_bio_header,
        render_top_posts_and_comments,
    )

    st.title("Conteúdo orgânico do Instagram")
    st.markdown(f"Resultados orgânicos de **{client.name}**.")
    st.caption(
        "O filtro seleciona a data de publicação. Os Insights mostram os resultados acumulados "
        "dessas publicações até a consulta, não somente as interações ocorridas no período."
    )

    # 1. Métricas de perfil e bio visíveis no topo da tela
    try:
        profile_info = data_loader.fetch_account_profile_cached(client.name)
        if profile_info and any(profile_info.values()):
            render_profile_bio_header(profile_info, client.name)
    except Exception as error:
        logger.warning(
            f"Erro ao carregar dados do perfil de {client.name}: {error}"
        )
        sentry_sdk.capture_exception(error)

    tab_posts, tab_growth, tab_audience = st.tabs([
        "📊 Publicações & Conteúdo",
        "📈 Seguidores & Crescimento",
        "👥 Audiência & Demografia",
    ])

    with tab_posts:
        media = []
        try:
            with st.spinner("Carregando publicações orgânicas..."):
                media = data_loader.fetch_organic_media(date_preset, time_range, client.name)
        except Exception as error:
            logger.error(f"Erro ao carregar publicações orgânicas de {client.name}: {error}")
            sentry_sdk.capture_exception(error)
            st.warning(f"Aviso sobre as publicações do Instagram ({client.name}): {error}")
            media = []

        if not media:
            st.info("Nenhuma publicação encontrada no período selecionado.")
        else:
            # 2. Desempenho orgânico das publicações
            render_organic_metrics_cards(media)

            # 3. Ranking de publicações ordenado primariamente por alcance (reach)
            render_top_posts_and_comments(media)

            # 4. Comentário mais curtido em destaque com download CSV rápido
            render_historic_top_comment(client.name, media)

            # 5. Tabela de publicações orgânicas com filtros
            render_posts_table(media)

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
        st.markdown("### 📈 Crescimento e Histórico de Seguidores")
        st.caption("Acompanhamento de novos seguidores diários e ações registradas no perfil.")

        # 1. Gráfico de novos seguidores diários (Plotly com spline e maior pico)
        try:
            with st.spinner("Carregando evolução de seguidores..."):
                followers_history = data_loader.fetch_followers_history_cached(client.name)
            if followers_history:
                render_followers_timeline(followers_history)
            else:
                st.info("Histórico de novos seguidores diários não disponível no momento para esta conta.")
        except Exception as error:
            logger.warning(f"Erro ao buscar histórico de seguidores de {client.name}: {error}")
            sentry_sdk.capture_exception(error)
            st.info("Histórico de novos seguidores diários não disponível no momento para esta conta.")

        # 2. Ações no perfil (visitas, toques no link, engajamento)
        try:
            insights = data_loader.fetch_account_insights_cached(client.name, date_preset, time_range)
            if insights:
                st.write("")
                st.markdown("#### 👤 Ações e Interações no Perfil")
                st.caption("Ações diretas realizadas pelos usuários no perfil do Instagram durante o período.")
                cols_act = st.columns(3)

                def _fmt(val):
                    try:
                        return f"{int(val):,}".replace(",", ".")
                    except Exception:
                        return str(val or 0)

                with cols_act[0]:
                    render_metric_card(
                        "Visitas ao Perfil",
                        _fmt(insights.get("profile_views", 0)),
                        "Acessos à bio",
                        "Visualizações diretas do perfil no período",
                    )
                with cols_act[1]:
                    render_metric_card(
                        "Cliques no Link",
                        _fmt(insights.get("profile_links_taps", 0)),
                        "Cliques no site",
                        "Conversões diretas pelo link da bio",
                    )
                with cols_act[2]:
                    engaged = insights.get("engaged_audience") or insights.get("total_interactions") or 0
                    render_metric_card(
                        "Contas com Engajamento",
                        _fmt(engaged),
                        "Público ativo",
                        "Contas únicas que interagiram com seu conteúdo",
                    )
        except Exception as error:
            logger.warning(f"Erro ao buscar ações do perfil de {client.name}: {error}")
            sentry_sdk.capture_exception(error)

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
            render_ads_page(date_preset, time_range, client)
        else:
            render_organic_page(date_preset, time_range, client)
    except Exception as error:
        report_error(
            "Não foi possível carregar esta área. Verifique a configuração da conta e tente novamente.",
            error,
        )


if __name__ == "__main__":
    main()
