import logging
import sys
from pathlib import Path

import sentry_sdk
import streamlit as st
from streamlit_option_menu import option_menu
from core.config import settings

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        release=settings.sentry_release,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        enable_tracing=True,
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
from ui.data_loader import fetch_active_stories, fetch_campaigns_v8, fetch_organic_v12  # noqa: E402
from ui.layouts import render_sidebar  # noqa: E402
from ui.organic_components import render_organic_metrics_cards, render_posts_table  # noqa: E402

# Configuração do Logging
logging.basicConfig(level=logging.INFO)  # noqa: E402

# Configuração da página DEVE ser a primeira chamada
st.set_page_config(
    page_title="Zenit Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

def load_css():
    css_path = Path(__file__).parent / "ui" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def main() -> None:  # noqa: C901
    # Aplica o CSS global do Zenit
    load_css()
    
    # Inicializa variáveis no session state caso necessário (Best Practice Streamlit)
    if "data_loaded" not in st.session_state:
        st.session_state["data_loaded"] = False

    selected_module, date_preset, time_range = render_sidebar()

    if selected_module == "Visão Geral (Ads)":
        st.title("Resumo de Campanhas")
        st.markdown(
            "Acompanhe o retorno sobre investimento (ROI) da conta **CA MS - 01**."
        )

        try:
            # Tenta carregar os dados (isso usa Cache, não fará 10 requisições seguidas)
            with st.spinner("Buscando dados das campanhas..."):
                campaigns = fetch_campaigns_v8(date_preset, time_range)

            if not campaigns:
                st.warning(
                    "Não localizamos campanhas ativas neste período. Acesse o Gerenciador de Anúncios da Meta para ativar suas campanhas e visualizar o retorno aqui."
                )
                return

            total_spend = sum(c.spend for c in campaigns)
            total_conversions = sum((c.leads + c.whatsapp_starts) for c in campaigns)
            avg_cpa = total_spend / total_conversions if total_conversions > 0 else 0.0

            # Renderiza a UI
            # --- BENTO GRID: Topo ---
            st.write("")
            top_c1, top_c2 = st.columns([1.5, 1])
            with top_c1:
                render_metric_cards(total_spend, total_conversions, avg_cpa)
            with top_c2:
                render_objective_pie_chart(campaigns)

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

            # --- BENTO GRID: Meio (WhatsApp) ---
            render_whatsapp_campaigns(whatsapp_campaigns)
            st.write("")

            # --- BENTO GRID: Base (Demais Campanhas Lado a Lado) ---
            b_c1, b_c2 = st.columns([1, 1])
            with b_c1:
                render_profile_campaigns(profile_campaigns)
            with b_c2:
                render_general_campaigns(general_campaigns)

            st.session_state["data_loaded"] = True

        except MetaAPIError as e:
            sentry_sdk.capture_exception(e)
            # Trata os erros de token, permissão ou rede amigavelmente na UI
            st.error(
                "Não foi possível conectar à Meta. Verifique sua conexão ou se o token de acesso expirou."
            )
            # Tratado pela UI amigável e logs via Sentry
        except Exception as e:
            sentry_sdk.capture_exception(e)
            st.error("Ocorreu um erro ao carregar o painel. Tente recarregar a página.")
            # Tratado pela UI amigável e logs via Sentry

    elif selected_module == "Orgânico (Instagram)":
        st.title("📱 Desempenho no Instagram")
        st.markdown(
            "Veja o impacto real das suas publicações, separando o alcance orgânico do pago."
        )

        try:
            with st.spinner("Cruzando dados do Instagram e anúncios..."):
                media_list = fetch_organic_v12(date_preset, time_range)
                stories_list = fetch_active_stories()

            st.write("")
            render_organic_metrics_cards(media_list)

            st.write("")
            render_posts_table(media_list, stories_list)

        except InstagramAPIError as e:
            sentry_sdk.capture_exception(e)
            st.error("Não foi possível comunicar com o Instagram.")
            st.error(str(e))
        except MetaAPIError as e:
            sentry_sdk.capture_exception(e)
            st.error("Falha ao tentar cruzar dados com os anúncios do Facebook.")
            st.error(str(e))
        except Exception as e:
            sentry_sdk.capture_exception(e)
            st.error("Ocorreu um erro inesperado. Tente novamente.")
            # Tratado pela UI amigável e logs via Sentry


if __name__ == "__main__":
    main()
# Force hot reload
