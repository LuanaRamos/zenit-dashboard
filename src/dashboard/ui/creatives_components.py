import streamlit as st
import pandas as pd
from api.meta_client import MetaAdsClient
import sentry_sdk

@st.cache_data(ttl=3600)
def fetch_creatives(date_preset: str, time_range: dict = None):
    client = MetaAdsClient()
    return client.get_creative_performance(date_preset, time_range)

def render_creatives_tab(date_preset: str, time_range: dict = None):
    st.subheader("🎨 Laboratório de Criativos")
    st.markdown("Descubra quais imagens/vídeos estão gerando os melhores resultados e o menor custo (CPA/CPC).")
    
    try:
        with st.spinner("Analisando criativos..."):
            data = fetch_creatives(date_preset, time_range)
            
        if not data:
            st.warning("Sem dados de criativos no período.")
            return
            
        # Exibir top 10
        top_ads = data[:10]
        
        for i in range(0, len(top_ads), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                if i + j < len(top_ads):
                    ad = top_ads[i + j]
                    with col:
                        st.markdown(f"### {ad.ad_name}")
                        if ad.image_url:
                            st.image(ad.image_url, use_container_width=True)
                        elif ad.thumbnail_url:
                            st.image(ad.thumbnail_url, use_container_width=True)
                        else:
                            st.info("Imagem indisponível")
                        
                        st.markdown(f"**Gasto:** R$ {ad.spend:.2f} | **CPA:** R$ {ad.cpa:.2f}")
                        st.markdown(f"**Leads:** {ad.leads} | **WhatsApp:** {ad.whatsapp_starts}")
                        st.markdown(f"**Impressões:** {ad.impressions} | **Cliques:** {ad.clicks}")
                        st.markdown("---")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        st.error("Ocorreu um erro ao carregar os criativos. Nossa equipe já foi notificada e está trabalhando nisso.")
