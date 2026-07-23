import streamlit as st
import logging
import sys
from pathlib import Path

# Adiciona o diretório dashboard ao path para permitir imports absolutos internos
sys.path.append(str(Path(__file__).parent))

from api.exceptions import MetaAPIError, InstagramAPIError
from ui.data_loader import load_campaigns_data, load_organic_data
from ui.layouts import render_sidebar
from ui.components import render_metric_cards, render_campaign_table
from ui.organic_components import render_organic_metrics_cards, render_posts_table


# Configuração do Logging
logging.basicConfig(level=logging.INFO)

# Configuração inicial da página SEMPRE no topo
st.set_page_config(
    page_title="Meta Ads | Zenit Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    # Inicializa variáveis no session state caso necessário (Best Practice Streamlit)
    if "data_loaded" not in st.session_state:
        st.session_state["data_loaded"] = False
        
    selected_module = render_sidebar()
    
    if selected_module == "📈 Visão Geral (Ads)":
        st.title("Visão Geral das Campanhas")
        st.markdown("Acompanhe o retorno sobre o investimento da **CA MS - 01** em tempo real.")
        
        try:
            # Tenta carregar os dados (isso usa Cache, não fará 10 requisições seguidas)
            with st.spinner("Consultando Graph API..."):
                campaigns = load_campaigns_data()
                
            if not campaigns:
                st.warning("Nenhuma campanha encontrada nos últimos 30 dias.")
                return
                
            # Agregações simples para os cards
            total_spend = sum(c.spend for c in campaigns)
            total_leads = sum(c.leads for c in campaigns)
            avg_cpl = total_spend / total_leads if total_leads > 0 else 0.0
            
            # Renderiza a UI
            st.markdown("<br>", unsafe_allow_html=True)
            render_metric_cards(total_spend, total_leads, avg_cpl)
            
            st.markdown("<br>", unsafe_allow_html=True)
            render_campaign_table(campaigns)

            st.session_state["data_loaded"] = True
            
        except MetaAPIError as e:
            # Trata os erros de token, permissão ou rede amigavelmente na UI
            st.error("Falha ao se conectar com a Meta API.")
            st.exception(e)
        except Exception as e:
            st.error("Ocorreu um erro inesperado interno no Dashboard.")
            st.exception(e)
            
    elif selected_module == "📱 Orgânico (Instagram)":
        st.title("📱 Desempenho Orgânico (Instagram)")
        st.markdown("Acompanhe e isole as métricas do seu perfil separando Tráfego Pago do Orgânico.")
        
        try:
            with st.spinner("Consultando Instagram Graph API e extraindo dados dos anúncios..."):
                media_list = load_organic_data()
                
            st.markdown("<br>", unsafe_allow_html=True)
            render_organic_metrics_cards(media_list)
            
            st.markdown("<br>", unsafe_allow_html=True)
            render_posts_table(media_list)
            
        except InstagramAPIError as e:
            st.error("Falha de Comunicação com o Instagram.")
            st.error(str(e))
        except MetaAPIError as e:
            st.error("Falha ao cruzar dados com os anúncios do Facebook.")
            st.error(str(e))
        except Exception as e:
            st.error("Erro Inesperado.")
            st.exception(e)

if __name__ == "__main__":
    main()