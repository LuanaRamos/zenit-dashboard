import streamlit as st
import pandas as pd
from typing import Any
from schemas.meta import CreativePerformance

def render_creatives_tab(creatives: list[CreativePerformance]) -> None:
    """Renderiza a aba de Laboratório de Criativos"""
    st.markdown("### 🎨 Laboratório de Criativos (Ranking por CPA)")
    
    if not creatives:
        st.info("Não há dados suficientes de criativos no período selecionado.")
        return

    # Separar os top 3 para destaque
    top_3 = creatives[:3]
    others = creatives[3:]

    # --- TOP 3 DESTAQUES ---
    st.markdown("#### 🏆 Top 3 Criativos (Menor Custo por Conversão)")
    cols = st.columns(3)
    
    for i, creative in enumerate(top_3):
        with cols[i]:
            img_url = creative.thumbnail_url or creative.image_url or "https://via.placeholder.com/300x300?text=Sem+Imagem"
            
            html = f"""
            <div class="glass-card" style="padding: 15px; margin-bottom: 20px; text-align: center;">
                <h2 style="color: #FFD700; margin-top: 0;">#{i+1}</h2>
                <img src="{img_url}" style="width: 100%; max-height: 250px; object-fit: cover; border-radius: 8px; margin-bottom: 15px;">
                <div style="font-size: 0.9rem; color: #E2E8F0; margin-bottom: 5px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;" title="{creative.ad_name}">
                    {creative.ad_name}
                </div>
                <div style="color: #FFB300; font-size: 1.5rem; font-weight: bold; margin-bottom: 5px;">
                    R$ {creative.cpa:,.2f} <span style="font-size: 0.8rem; color: #8B949E; font-weight: normal;">/ conv</span>
                </div>
                <div style="display: flex; justify-content: space-around; font-size: 0.8rem; color: #8B949E; margin-top: 10px;">
                    <div><b>{creative.leads + creative.whatsapp_starts}</b> Conv.</div>
                    <div><b>R$ {creative.spend:,.2f}</b> Gasto</div>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

    # --- TODOS OS OUTROS CRIATIVOS ---
    if others:
        st.markdown("#### Todos os Criativos")
        
        data = []
        for c in creatives:
            data.append({
                "Anúncio": c.ad_name,
                "Gasto": round(c.spend, 2),
                "Conversões": c.leads + c.whatsapp_starts,
                "CPA": round(c.cpa, 2),
                "Cliques": c.clicks,
                "CPC": round(c.cpc, 2),
                "Imagem": c.image_url or c.thumbnail_url
            })
            
        df = pd.DataFrame(data)
        from ui.components import render_glass_table
        render_glass_table(
            df,
            currency_cols=["Gasto", "CPA", "CPC"],
            link_col="Imagem",
            link_label="Ver Arte",
            key="tbl_creatives",
            csv_filename="criativos.csv"
        )