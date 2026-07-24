import logging
import sys
from pathlib import Path

import sentry_sdk
import streamlit as st
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
    render_profile_campaigns,
    render_whatsapp_campaigns,
)
from ui.data_loader import fetch_active_stories, fetch_campaigns_v8, fetch_organic_v12  # noqa: E402
from ui.layouts import render_sidebar  # noqa: E402
from ui.organic_components import render_organic_metrics_cards, render_posts_table  # noqa: E402

# Configuração do Logging
logging.basicConfig(level=logging.INFO)  # noqa: E402

# Configuração inicial da página SEMPRE no topo
st.set_page_config(
    page_title="Meta Ads | Zenit Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:  # noqa: C901
    # Inicializa variáveis no session state caso necessário (Best Practice Streamlit)
    if "data_loaded" not in st.session_state:
        st.session_state["data_loaded"] = False

    selected_module, date_preset, time_range = render_sidebar()

    if selected_module == "📈 Visão Geral (Ads)":
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

            # Agregações simples para os cards
            total_spend = sum(c.spend for c in campaigns)
            total_leads = sum(c.leads for c in campaigns)
            avg_cpl = total_spend / total_leads if total_leads > 0 else 0.0

            # Renderiza a UI
            st.write("")
            render_metric_cards(total_spend, total_leads, avg_cpl)

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

            # Renderizar Dinamicamente
            render_whatsapp_campaigns(whatsapp_campaigns)
            st.write("")

            render_profile_campaigns(profile_campaigns)
            st.write("")

            render_general_campaigns(general_campaigns)

            st.session_state["data_loaded"] = True

        except MetaAPIError as e:
            sentry_sdk.capture_exception(e)
            # Trata os erros de token, permissão ou rede amigavelmente na UI
            st.error(
                "Não foi possível conectar à Meta. Verifique sua conexão ou se o token de acesso expirou."
            )
            st.exception(e)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            st.error("Ocorreu um erro ao carregar o painel. Tente recarregar a página.")
            st.exception(e)

    elif selected_module == "📱 Orgânico (Instagram)":
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
            st.exception(e)


if __name__ == "__main__":
    main()
