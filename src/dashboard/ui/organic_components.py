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
    """Renderiza destaques e os melhores comentários de cada post."""
    st.markdown("### 🏆 Top Posts (Maior Alcance Total)")
    
    if not media_list:
        return
        
    # Ordena por alcance total (orgânico + pago)
    sorted_media = sorted(media_list, key=lambda x: (x.organic_reach + x.paid_reach), reverse=True)
    top_3 = sorted_media[:3]
    
    cols = st.columns(3)
    
    try:
        from api.instagram_client import InstagramClient
        ig_client = InstagramClient()
        top_ids = [m.id for m in top_3]
        best_comments = []
        for m_id in top_ids:
            comment = ig_client.get_top_comment_for_account([m_id])
            best_comments.append(comment)
    except Exception as e:
        import sentry_sdk
        sentry_sdk.capture_exception(e)
        best_comments = [None, None, None]
    
    for i, m in enumerate(top_3):
        with cols[i]:
            img = getattr(m, "thumbnail_url", None) or m.media_url or "https://via.placeholder.com/150"
            html = f"""
            <div class="glass-card" style="padding: 15px; text-align: center; height: 100%;">
                <img src="{img}" style="width: 100%; max-height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 10px;">
                <div style="color: #FFB300; font-size: 1.2rem; font-weight: bold;">Alcance: {f"{int(m.organic_reach + m.paid_reach):,}".replace(",", ".")}</div>
                <div style="font-size: 0.8rem; color: #8B949E; margin-bottom: 10px;">Orgânico: {f"{int(m.organic_reach):,}".replace(",", ".")} | Pago: {f"{int(m.paid_reach):,}".replace(",", ".")}</div>
            """
            
            c = best_comments[i] if i < len(best_comments) else None
            if c:
                text = c.get("text", "")
                username = c.get("username", "Usuário")
                likes = c.get("like_count", 0)
                html += f"""
                <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; text-align: left; font-size: 0.85rem; border-left: 3px solid #FFB300;">
                    <div style="color: #E2E8F0; margin-bottom: 4px;">"{text}"</div>
                    <div style="color: #8B949E; font-size: 0.75rem;"><strong>@{username}</strong> • {likes} curtidas</div>
                </div>
                """
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)
