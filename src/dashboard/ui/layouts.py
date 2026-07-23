import streamlit as st

def render_sidebar():
    """
    Configura e renderiza a barra lateral de navegação e filtros.
    """
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/2560px-Meta_Platforms_Inc._logo.svg.png", width=150)
        st.title("Meta Ads Dashboard")
        st.markdown("---")
        
        st.markdown(
            """
            **Módulos**
            - 📈 Visão Geral (Ads)
            - 📱 Orgânico (Instagram)
            """
        )
        
        st.markdown("---")
        st.caption("Atualizado em tempo real via Meta Graph API v20.0")
        
        if st.button("🔄 Forçar Atualização"):
            st.cache_data.clear()
            st.rerun()