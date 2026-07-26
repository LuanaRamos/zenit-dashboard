import streamlit as st
from ui.data_loader import get_api_client
import sentry_sdk

@st.cache_data(ttl=3600)
def fetch_catalogs(client_name: str):
    client = get_api_client(client_name)
    return client.check_catalog_assets()

def render_catalog_tab(client_name: str) -> None:
    st.markdown("### 🛍️ Catálogo de Produtos e E-commerce")
    st.markdown("Acompanhe a performance dos produtos anunciados no Meta Ads e Shopping.")
    
    st.info("🚧 Em construção: A integração com os IDs do Catálogo da Meta será liberada na próxima fase.")
    
    try:
        with st.spinner("Buscando catálogos..."):
            data = fetch_catalogs(client_name)
            
        if not data:
            st.info("Nenhum catálogo de produtos foi encontrado vinculado diretamente a esta conta de anúncios. Se houver um e-commerce, verifique se o catálogo está compartilhado com a conta de anúncios no Business Manager.")
            return
            
        for cat in data:
            st.markdown(f"### 📦 Catálogo: {cat.name}")
            st.markdown(f"**ID:** `{cat.catalog_id}`")
            count_fmt = f"{int(cat.product_count):,}".replace(",", ".")
            st.metric("Total de Produtos", count_fmt)
            st.markdown("---")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        st.error("Ocorreu um erro ao carregar os dados do catálogo. Nossa equipe já foi notificada e está trabalhando nisso.")
