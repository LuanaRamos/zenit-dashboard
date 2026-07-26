import streamlit as st
import pandas as pd
from typing import Any, List
from schemas.instagram import InstagramMedia
import plotly.graph_objects as go
from ui.components import render_glass_table, render_metric_card

def render_organic_metrics_cards(media_list: List[InstagramMedia]) -> None:
    """Renderiza KPIs orgânicos vs pagos."""
    st.markdown("### 📊 Alcance: Orgânico vs Ads")
    
    total_organic_reach = sum(m.organic_reach for m in media_list)
    total_paid_reach = sum(m.paid_reach for m in media_list)
    total_engagement = sum(m.like_count + m.comments_count + m.paid_likes for m in media_list)
    
    cols = st.columns(3)
    with cols[0]:
        render_metric_card("Alcance Orgânico", f"{int(total_organic_reach):,}".replace(",", "."), "Pessoas", "Tráfego gratuito")
    with cols[1]:
        render_metric_card("Alcance Pago", f"{int(total_paid_reach):,}".replace(",", "."), "Pessoas", "Impulsionamentos")
    with cols[2]:
        render_metric_card("Engajamento Total", f"{int(total_engagement):,}".replace(",", "."), "Interações", "Likes, comentários")

def render_posts_table(media_list: List[InstagramMedia], stories_list: List[Any]) -> None:
    """Renderiza tabela de posts."""
    st.markdown("### 📝 Publicações")
    if not media_list:
        st.info("Nenhuma publicação encontrada no período.")
        return
        
    data = []
    for m in media_list:
        data.append({
            "Tipo": m.media_type,
            "Alcance Orgânico": m.organic_reach,
            "Alcance Pago": m.paid_reach,
            "Likes (Orgânico)": m.like_count,
            "Likes (Pago)": m.paid_likes,
            "Cliques (Pago)": m.paid_clicks,
            "Link": m.permalink
        })
        
    df = pd.DataFrame(data)
    render_glass_table(df, key="tbl_posts", csv_filename="posts.csv", link_col="Link", link_label="Ver no Instagram")

def render_top_posts_and_comments(media_list: List[InstagramMedia]) -> None:
    """Renderiza destaques."""
    st.markdown("### 🏆 Top Posts (Maior Alcance Total)")
    
    if not media_list:
        return
        
    # Ordena por alcance total (orgânico + pago)
    sorted_media = sorted(media_list, key=lambda x: (x.organic_reach + x.paid_reach), reverse=True)
    top_3 = sorted_media[:3]
    
    cols = st.columns(3)
    for i, m in enumerate(top_3):
        with cols[i]:
            img = m.thumbnail_url or m.media_url or "https://via.placeholder.com/150"
            html = f"""
            <div class="glass-card" style="padding: 15px; text-align: center;">
                <img src="{img}" style="width: 100%; max-height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 10px;">
                <div style="color: #FFB300; font-size: 1.2rem; font-weight: bold;">Alcance: {f"{int(m.organic_reach + m.paid_reach):,}".replace(",", ".")}</div>
                <div style="font-size: 0.8rem; color: #8B949E;">Orgânico: {f"{int(m.organic_reach):,}".replace(",", ".")} | Pago: {f"{int(m.paid_reach):,}".replace(",", ".")}</div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
