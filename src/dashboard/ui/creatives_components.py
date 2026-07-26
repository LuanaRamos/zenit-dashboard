import streamlit as st
import pandas as pd
from api.meta_client import MetaAdsClient
import sentry_sdk

@st.cache_data(ttl=3600)
def fetch_creatives(date_preset: str, time_range: dict = None):
    client = MetaAdsClient()
    data = client.get_creative_performance(date_preset, time_range)
    results = []
    for d in data:
        dump = d.model_dump()
        dump["objective_friendly"] = d.objective_friendly
        results.append(dump)
    return results

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
                        st.markdown(f"### {ad.get('ad_name', '')}")
                        if ad.get('image_url'):
                            st.image(ad['image_url'], use_container_width=True)
                        elif ad.get('thumbnail_url'):
                            st.image(ad['thumbnail_url'], use_container_width=True)
                        else:
                            st.info("Imagem indisponível")
                        
                        gasto = ad.get('spend', 0.0)
                        cpa = ad.get('cpa', 0.0)
                        cpc = ad.get('cpc', 0.0)
                        
                        gasto_fmt = f"R\$ {gasto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        cpa_fmt = f"R\$ {cpa:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        cpc_fmt = f"R\$ {cpc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        
                        leads = int(ad.get('leads', 0))
                        wpp = int(ad.get('whatsapp_starts', 0))
                        leads_fmt = f"{leads:,}".replace(",", ".")
                        wpp_fmt = f"{wpp:,}".replace(",", ".")
                        
                        imp = int(ad.get('impressions', 0))
                        clicks = int(ad.get('clicks', 0))
                        imp_fmt = f"{imp:,}".replace(",", ".")
                        clicks_fmt = f"{clicks:,}".replace(",", ".")
                        
                        ctr = (clicks / imp * 100) if imp > 0 else 0
                        ctr_fmt = f"{ctr:.2f}%".replace(".", ",")

                        obj_friendly = ad.get('objective_friendly', 'N/A')
                        st.markdown(f"**Objetivo:** {obj_friendly}")
                        
                        if "Tráfego" in obj_friendly or "Reconhecimento" in obj_friendly or "Visitas" in obj_friendly or "Engajamento" in obj_friendly:
                            st.markdown(f"**Gasto:** {gasto_fmt} | **CPC:** {cpc_fmt}")
                            st.markdown(f"**Impressões:** {imp_fmt} | **Cliques:** {clicks_fmt} | **CTR:** {ctr_fmt}")
                        else:
                            st.markdown(f"**Gasto:** {gasto_fmt} | **CPA:** {cpa_fmt} | **CPC:** {cpc_fmt}")
                            st.markdown(f"**Leads:** {leads_fmt} | **WhatsApp:** {wpp_fmt}")
                            st.markdown(f"**Impressões:** {imp_fmt} | **Cliques:** {clicks_fmt} | **CTR:** {ctr_fmt}")
                        st.markdown("---")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        st.error("Ocorreu um erro ao carregar os criativos. Nossa equipe já foi notificada e está trabalhando nisso.")