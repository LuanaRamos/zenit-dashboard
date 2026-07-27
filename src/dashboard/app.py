import logging
import sys
from pathlib import Path

import sentry_sdk
import streamlit as st

# Configuração da página DEVE ser a primeira chamada do Streamlit
st.set_page_config(
    page_title="Zenit Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from streamlit_option_menu import option_menu
    from core.config import settings

    if settings.sentry_dsn:
        from sentry_sdk.integrations.threading import ThreadingIntegration
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            release=settings.sentry_release,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            enable_tracing=True,
            integrations=[
                ThreadingIntegration(propagate_traces=False),
            ],
        )

    # Adiciona o diretório dashboard ao path para permitir imports absolutos internos
    sys.path.append(str(Path(__file__).parent))

    from api.exceptions import InstagramAPIError, MetaAPIError  # noqa: E402
    from ui.components import (  # noqa: E402
        render_general_campaigns,
        render_metric_cards,
        render_objective_pie_chart,
        render_profile_campaigns,
        render_whatsapp_campaigns,
    )
    from ui.data_loader import fetch_active_stories, fetch_campaigns_v8, fetch_organic_v12, fetch_account_demographics  # noqa: E402
    from ui.layouts import render_sidebar  # noqa: E402
    from ui.organic_components import render_organic_metrics_cards, render_posts_table, render_top_posts_and_comments, render_historic_top_comment  # noqa: E402

    # Configuração do Logging
    logging.basicConfig(level=logging.INFO)  # noqa: E402

    def load_css():
        css_path = Path(__file__).parent / "ui" / "style.css"
        if css_path.exists():
            with open(css_path, "r", encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    def main() -> None:  # noqa: C901
        try:
            # Aplica o CSS global do Zenit
            load_css()
            
            # Inicializa variáveis no session state caso necessário (Best Practice Streamlit)
            if "data_loaded" not in st.session_state:
                st.session_state["data_loaded"] = False

            selected_module, date_preset, time_range, selected_client = render_sidebar()

            if selected_module == "Visão Geral (Ads)":
                st.title("Resumo de Campanhas")
                st.markdown(
                    f"Acompanhe o retorno sobre investimento (ROI) da conta **{selected_client.name}**."
                )
                st.info("ℹ️ Métricas calibradas: removemos duplicidades da Meta para garantir 100% de precisão real.")

                try:
                    # Tenta carregar os dados (isso usa Cache, não fará 10 requisições seguidas)
                    with st.spinner(f"Buscando dados das campanhas de {selected_client.name}..."):
                        campaigns = fetch_campaigns_v8(date_preset, time_range, selected_client.name)

                    if not campaigns:
                        st.warning(
                            "Não localizamos campanhas ativas neste período. Acesse o Gerenciador de Anúncios da Meta para ativar suas campanhas e visualizar o retorno aqui."
                        )
                        return

                    tab_overview, tab_demographics, tab_creatives, tab_catalog = st.tabs([
                        "📊 Visão Geral", 
                        "👥 Público (Demografia)", 
                        "🎨 Laboratório de Criativos", 
                        "🛍️ Catálogo & E-commerce"
                    ])

                    with tab_overview:
                        from ui.data_loader import fetch_organic_leads_cached
                        organic_leads = fetch_organic_leads_cached(date_preset, time_range, selected_client.name)
                        
                        total_spend = sum(c.spend for c in campaigns)
                        paid_conversions = sum((c.leads + c.whatsapp_starts) for c in campaigns)
                        
                        total_conversions = paid_conversions + organic_leads
                        avg_cpa = total_spend / paid_conversions if paid_conversions > 0 else 0.0

                        # Renderiza a UI
                        # --- BENTO GRID: Topo (Métricas) ---
                        st.write("")
                        render_metric_cards(total_spend, total_conversions, avg_cpa, paid_conversions, organic_leads)
                        st.write("")

                        # Filtragem inteligente por Objetivo ODAX, Legacy ou presença de métricas fortes
                        whatsapp_campaigns = [
                            c
                            for c in campaigns
                            if c.objective in ["OUTCOME_ENGAGEMENT", "MESSAGES"]
                            or c.whatsapp_starts > 0
                        ]
                        profile_campaigns = [
                            c
                            for c in campaigns
                            if c.objective in ["OUTCOME_TRAFFIC", "LINK_CLICKS"]
                            or c.instagram_follows > 0
                            or c.profile_visits > 0
                        ]

                        # As demais que não caíram nos filtros primários
                        general_campaigns = [
                            c
                            for c in campaigns
                            if c not in whatsapp_campaigns and c not in profile_campaigns
                        ]

                        # --- BENTO GRID: Gráficos ---
                        from ui.components import render_whatsapp_cost_chart
                        
                        charts_c1, charts_c2 = st.columns([1, 1])
                        with charts_c1:
                            render_objective_pie_chart(campaigns)
                        with charts_c2:
                            render_whatsapp_cost_chart(whatsapp_campaigns)
                        
                        st.write("")

                        # --- BENTO GRID: Tabelas (Uma abaixo da outra) ---
                        render_whatsapp_campaigns(whatsapp_campaigns)
                        st.write("")
                        
                        render_profile_campaigns(profile_campaigns)
                        st.write("")
                        
                        render_general_campaigns(general_campaigns)

                    with tab_demographics:
                        from ui.demographics_components import render_demographics_tab
                        render_demographics_tab(date_preset, time_range, selected_client.name)

                    with tab_creatives:
                        from ui.creatives_components import render_creatives_tab
                        render_creatives_tab(date_preset, time_range, selected_client.name)

                    with tab_catalog:
                        from ui.catalog_components import render_catalog_tab
                        render_catalog_tab(selected_client.name)

                    st.session_state["data_loaded"] = True

                except MetaAPIError as e:
                    sentry_sdk.capture_exception(e)
                    st.error(f"Não foi possível conectar à Meta: {str(e)}")
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    st.error("Ocorreu um erro ao carregar o painel. Detalhes técnicos abaixo:")
                    st.exception(e)

            elif selected_module == "Orgânico (Instagram)":
                st.title("📱 Desempenho no Instagram")
                st.markdown(
                    "Veja o impacto real das suas publicações, separando o alcance orgânico do pago."
                )

                try:
                    with st.spinner(f"Cruzando dados do Instagram e anúncios para {selected_client.name}..."):
                        media_list = fetch_organic_v12(date_preset, time_range, selected_client.name)
                        stories_list = fetch_active_stories(selected_client.name)
                        account_demographics = fetch_account_demographics(selected_client.name)

                    tab_geral, tab_demografico = st.tabs(["📊 Desempenho", "👥 Demografia (Público)"])

                    with tab_geral:
                        st.write("")
                        render_organic_metrics_cards(media_list)

                        st.write("")
                        render_historic_top_comment()

                        st.write("")
                        render_posts_table(media_list, stories_list)

                        st.write("")
                        render_top_posts_and_comments(media_list)

                    with tab_demografico:
                        from ui.demographics_components import render_demographics_dashboard
                        render_demographics_dashboard(account_demographics)

                except InstagramAPIError as e:
                    sentry_sdk.capture_exception(e)
                    st.warning("A conexão com o Instagram está instável no momento. Mostrando dados em cache ou parciais.")
                except MetaAPIError as e:
                    sentry_sdk.capture_exception(e)
                    st.error("Falha ao tentar cruzar dados com os anúncios do Facebook.")
                    st.exception(e)
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    st.error("Ocorreu um erro inesperado. Detalhes técnicos abaixo:")
                    st.exception(e)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            st.error("Ocorreu uma instabilidade inesperada na conexão. Nossa equipe já foi notificada via Sentry.")

    if __name__ == "__main__":
        main()

except Exception as e:
    import traceback
    st.error("⚠️ Ooops! Ocorreu um problema ao carregar o sistema.")
    st.info("Nossa equipe de suporte técnico (Antigravity) já foi notificada silenciosamente. Isso geralmente se resolve em alguns minutos com um simples recarregamento de página. Por favor, recarregue a página.")
