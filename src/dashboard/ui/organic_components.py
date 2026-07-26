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
        render_metric_card("Engajamento Total", f"{int(total_engagement):,}".replace(",", "."), "Interações", "Curtidas, comentários")

def render_posts_table(media_list: List[InstagramMedia], stories_list: List[Any]) -> None:
    """Renderiza tabela de posts."""
    st.markdown("### 📝 Publicações")
    if not media_list:
        st.info("Nenhuma publicação encontrada no período.")
        return
        
    data = []
    tipo_map = {
        "VIDEO": "Vídeo",
        "IMAGE": "Imagem",
        "CAROUSEL_ALBUM": "Carrossel",
        "REELS": "Reels"
    }
    for m in media_list:
        data.append({
            "Tipo": tipo_map.get(m.media_type, m.media_type),
            "Alcance Orgânico": m.organic_reach,
            "Alcance Pago": m.paid_reach,
            "Curtidas (Orgânico)": m.like_count,
            "Curtidas (Pago)": m.paid_likes,
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
            img = getattr(m, "thumbnail_url", None) or m.media_url or "https://via.placeholder.com/400x400?text=Imagem+Indisponível"
            is_video_url = img and (img.split("?")[0].lower().endswith(".mp4") or m.media_type == "VIDEO")
            
            media_tag = f'<video src="{img}" controls style="width: 100%; height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 15px; background: #1a1a1a;"></video>' if is_video_url else f'<img src="{img}" style="width: 100%; height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 15px; background: #1a1a1a;">'

            alcance_total = f"{int(m.organic_reach + m.paid_reach):,}".replace(",", ".")
            alcance_org = f"{int(m.organic_reach):,}".replace(",", ".")
            alcance_pago = f"{int(m.paid_reach):,}".replace(",", ".")
            curtidas = f"{int(m.total_likes):,}".replace(",", ".")
            comentarios = f"{int(m.comments_count):,}".replace(",", ".")
            compartilhamentos = f"{int(m.total_shares):,}".replace(",", ".")
            
            html = f"""<div class="glass-card" style="padding: 15px; text-align: center; height: 100%;">
    {media_tag}
    <div style="display: flex; justify-content: space-between; margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px;">
        <div style="text-align: center;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #E2E8F0;">{curtidas}</div>
            <div style="font-size: 0.7rem; color: #8B949E;">❤️ Curtidas</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #E2E8F0;">{comentarios}</div>
            <div style="font-size: 0.7rem; color: #8B949E;">💬 Coment.</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #E2E8F0;">{compartilhamentos}</div>
            <div style="font-size: 0.7rem; color: #8B949E;">🔁 Comp.</div>
        </div>
    </div>
    <div style="margin-bottom: 15px;">
        <div style="color: #FFB300; font-size: 1.2rem; font-weight: bold;">Alcance: {alcance_total}</div>
        <div style="font-size: 0.8rem; color: #8B949E;">Orgânico: {alcance_org} | Pago: {alcance_pago}</div>
    </div>"""
            
            c = best_comments[i] if i < len(best_comments) else None
            if c:
                text = c.get("text", "")
                username = c.get("username", "Usuário")
                likes = c.get("like_count", 0)
                html += f"""<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; text-align: left; font-size: 0.85rem; border-left: 3px solid #FFB300; margin-top: 10px;">
        <div style="color: #E2E8F0; margin-bottom: 4px;">"{text}"</div>
        <div style="color: #8B949E; font-size: 0.75rem;"><strong>@{username}</strong> • {likes} curtidas</div>
    </div>"""
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

def render_historic_top_comment() -> None:
    """Renderiza o comentário mais curtido da história do perfil."""
    try:
        from ui.data_loader import fetch_best_historic_comment
        best = fetch_best_historic_comment()
        
        if not best:
            return
            
        st.markdown("### 👑 O Comentário de Ouro (Recorde da Conta)")
        
        text = best.get("text", "")
        username = best.get("username", "Usuário")
        likes = best.get("like_count", 0)
        
        html = f"""<div class="glass-card" style="padding: 20px; border-left: 4px solid #FFB300; background: rgba(255,179,0,0.05); border-radius: 8px; margin-bottom: 20px;">
    <div style="font-size: 1.1rem; color: #E2E8F0; margin-bottom: 8px; font-style: italic;">"{text}"</div>
    <div style="color: #8B949E; font-size: 0.9rem;">
        <strong>@{username}</strong> • 🏆 {int(likes):,} curtidas
    </div>
</div>""".replace(",", ".")
        st.markdown(html, unsafe_allow_html=True)
    except Exception as e:
        import sentry_sdk
        import logging
        logging.getLogger(__name__).error(f"Erro ao renderizar top comment historico: {e}")
        sentry_sdk.capture_exception(e)
