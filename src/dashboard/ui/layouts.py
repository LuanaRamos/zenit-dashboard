import streamlit as st
import datetime
from ui.data_loader import get_account_creation_date_cached

def render_sidebar():
    """
    Configura e renderiza a barra lateral de navegação e filtros.
    Retorna o módulo selecionado.
    """
    with st.sidebar:
        st.markdown("## 🌐 Meta Platforms")
        st.title("Zenit Dashboard")
        st.markdown("---")
        
        # O rádio permite clicar e trocar de tela
        selected_module = st.radio(
            "Módulos",
            ["📈 Visão Geral (Ads)", "📱 Orgânico (Instagram)"]
        )
        
        # Filtro de Tempo Global
        st.markdown("---")
        periodo_selecionado = st.selectbox(
            "Período de Análise",
            ["Últimos 30 Dias", "Máximo (Ads: Sempre | Orgânico: 1 Ano)", "Personalizado"]
        )
        
        date_preset = "last_30d"
        time_range = None
        
        if "Máximo" in periodo_selecionado:
            date_preset = "maximum"
        elif "Personalizado" in periodo_selecionado:
            date_preset = "custom"
            
            min_date = get_account_creation_date_cached()
            max_date = datetime.date.today()
            
            custom_dates = st.date_input(
                "Selecione o intervalo:",
                value=(max_date - datetime.timedelta(days=30), max_date),
                min_value=min_date,
                max_value=max_date
            )
            
            if len(custom_dates) == 2:
                time_range = {"since": custom_dates[0].strftime("%Y-%m-%d"), "until": custom_dates[1].strftime("%Y-%m-%d")}
            else:
                st.warning("Selecione a data final.")
                st.stop()

        st.markdown("---")
        st.caption("Atualizado em tempo real via Meta Graph API v20.0")
        
        if st.button("🔄 Forçar Atualização"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
            
    return selected_module, date_preset, time_range
