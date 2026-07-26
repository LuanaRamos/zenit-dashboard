import streamlit as st
from api.meta_client import MetaAdsClient
import sentry_sdk

@st.cache_data(ttl=3600)
def fetch_catalogs():
    client = MetaAdsClient()
    return client.check_catalog_assets()

def render_catalog_tab():
    st.subheader("🛍️ Catálogo & E-commerce")
    st.markdown("Confira se o catálogo de produtos está saudável e vinculado corretamente.")
    
    try:
        with st.spinner("Buscando catálogos..."):
            data = fetch_catalogs()
            
        if not data:
            st.info("Nenhum catálogo de produtos foi encontrado vinculado diretamente a esta conta de anúncios. Se houver um e-commerce, verifique se o catálogo está compartilhado com a conta de anúncios no Business Manager.")
            return
            
        for cat in data:
            st.markdown(f"### 📦 Catálogo: {cat.name}")
            st.markdown(f"**ID:** `{cat.catalog_id}`")
            st.metric("Total de Produtos", cat.product_count)
            st.markdown("---")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        st.error("Ocorreu um erro ao carregar os dados do catálogo. Nossa equipe já foi notificada e está trabalhando nisso.")
