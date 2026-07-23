import streamlit as st

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
            ["Últimos 30 Dias", "Desde o Início (Máximo)"]
        )
        
        # Mapear a escolha para o padrão da Meta API
        date_preset = "maximum" if periodo_selecionado == "Desde o Início (Máximo)" else "last_30d"

        st.markdown("---")
        st.caption("Atualizado em tempo real via Meta Graph API v20.0")
        
        if st.button("🔄 Forçar Atualização"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
            
    return selected_module, date_preset
