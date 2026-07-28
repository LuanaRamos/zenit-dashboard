import streamlit as st
import pandas as pd
from typing import Any, List
from schemas.instagram import InstagramMedia
import plotly.graph_objects as go
from ui.components import render_glass_table, render_metric_card

def format_hhmmss(ms_val: float) -> str:
    """Formata milissegundos em HH:MM:SS"""
    if not ms_val: return "0s"
    s = int(ms_val / 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h > 0:
        return f"{h:02d}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m:02d}m {s:02d}s"
    else:
        return f"{s:02d}s"

def render_account_insights_cards(insights: dict) -> None:
    """Renderiza os KPIs de nível de conta (Visitas, Cliques, etc)."""
    st.markdown("### 👁️ Visão Geral da Conta (Últimos 28 dias)")
    cols = st.columns(4)
    with cols[0]:
        render_metric_card("Visitas ao Perfil", f"{insights.get('profile_views', 0):,}".replace(",", "."), "Vistas", "Total da conta")
    with cols[1]:
        render_metric_card("Toques no Link", f"{insights.get('profile_links_taps', 0):,}".replace(",", "."), "Cliques", "Bio")
    with cols[2]:
        render_metric_card("Cliques no Site", f"{insights.get('website_clicks', 0):,}".replace(",", "."), "Cliques", "Site")
    with cols[3]:
        render_metric_card("Alcance da Conta", f"{insights.get('reach', 0):,}".replace(",", "."), "Pessoas", "Total")


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
    
    col1, col2 = st.columns([1, 3])
    with col1:
        filtro_tipo = st.selectbox("Filtrar por formato", options=["Todos", "Imagem", "Vídeo", "Carrossel", "Reels"])
        
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
        tipo = "Reels" if m.media_product_type == "REELS" else tipo_map.get(m.media_type, m.media_type)
        
        if filtro_tipo != "Todos" and tipo != filtro_tipo:
            continue
            
        data.append({
            "Tipo": tipo,
            "Alcance (Orgânico)": m.organic_reach,
            "Alcance (Pago)": m.paid_reach,
            "Visitas ao Perfil (Org)": m.profile_visits,
            "Tempo Assistido": format_hhmmss(m.ig_reels_video_view_total_time),
            "Tempo Médio": format_hhmmss(m.ig_reels_avg_watch_time),
            "Curtidas (Orgânico)": m.like_count,
            "Curtidas (Pago)": m.paid_likes,
            "Cliques no Criativo (Pago)": m.paid_other_clicks,
            "Cliques no Link (Pago)": m.paid_link_clicks,
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
            # Vídeos do CDN do Instagram têm CORS — não reproduzem em iframe/video.
            # Solução: usar thumbnail_url como imagem + link para o permalink.
            thumb = getattr(m, "thumbnail_url", None) or m.media_url or ""
            is_video = m.media_type in ("VIDEO", "REELS") or (m.media_url or "").split("?")[0].lower().endswith(".mp4")
            img_url = thumb if thumb else (m.media_url or "https://via.placeholder.com/400x400?text=Sem+Imagem")
            permalink = getattr(m, "permalink", "") or ""

            alcance_total = f"{int(m.organic_reach + m.paid_reach):,}".replace(",", ".")
            alcance_org = f"{int(m.organic_reach):,}".replace(",", ".")
            alcance_pago = f"{int(m.paid_reach):,}".replace(",", ".")
            curtidas = f"{int(m.total_likes):,}".replace(",", ".")
            comentarios = f"{int(m.comments_count):,}".replace(",", ".")
            compartilhamentos = f"{int(m.total_shares):,}".replace(",", ".")
            
            play_badge = (
                '<div style="position:absolute;top:8px;right:10px;background:rgba(0,0,0,0.6);'
                'color:white;border-radius:20px;padding:2px 10px;font-size:0.75rem;'
                'font-weight:600;">&#9654; Vídeo</div>'
            ) if is_video else ""

            img_link_open = f'<a href="{permalink}" target="_blank" style="display:block;position:relative;">' if permalink else '<div style="position:relative;">'
            img_link_close = "</a>" if permalink else "</div>"

            media_html = (
                f'{img_link_open}'
                f'<img src="{img_url}" style="width:100%;height:200px;object-fit:cover;'
                f'border-radius:8px;margin-bottom:15px;background:#1a1a1a;">'
                f'{play_badge}'
                f'{img_link_close}'
            )

            html = f"""<div class="glass-card" style="padding: 15px; text-align: center; height: 100%;">
    {media_html}
    <div style="display: flex; justify-content: space-between; margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px;">
        <div style="text-align: center;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #E2E8F0;">{curtidas}</div>
            <div style="font-size: 0.7rem; color: #8B949E;">&#10084; Curtidas</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #E2E8F0;">{comentarios}</div>
            <div style="font-size: 0.7rem; color: #8B949E;">&#128172; Coment.</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #E2E8F0;">{compartilhamentos}</div>
            <div style="font-size: 0.7rem; color: #8B949E;">&#128260; Comp.</div>
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
        <div style="color: #8B949E; font-size: 0.75rem;"><strong>@{username}</strong> &bull; {likes} curtidas</div>
    </div>"""
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

def render_historic_top_comment(client_name: str) -> None:
    """Renderiza o comentário mais curtido da história do perfil e permite baixar todos."""
    try:
        from ui.data_loader import fetch_all_historic_comments
        import pandas as pd
        all_comments = fetch_all_historic_comments(client_name)
        
        if not all_comments:
            return
            
        best = max(all_comments, key=lambda c: int(c.get("like_count", 0)), default=None)
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
        
        st.write("")
        df_comments = pd.DataFrame(all_comments)
        csv = df_comments.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar todos os comentários (CSV)",
            data=csv,
            file_name=f"todos_comentarios_{client_name}.csv",
            mime="text/csv",
        )
    except Exception as e:
        import sentry_sdk
        import logging
        logging.getLogger(__name__).error(f"Erro ao renderizar top comment historico: {e}")
        sentry_sdk.capture_exception(e)

def render_followers_timeline(history_data: list) -> None:
    """Renderiza a linha do tempo de ganho de seguidores dos últimos 30 dias."""
    if not history_data:
        st.info("O histórico de seguidores não está disponível para esta conta.")
        return
        
    import pandas as pd
    import plotly.express as px
    
    df = pd.DataFrame(history_data)
    if df.empty or "Data" not in df.columns or "Novos Seguidores" not in df.columns:
        st.info("Sem dados suficientes de histórico no momento.")
        return
        
    st.markdown("### 📈 Evolução de Seguidores (Últimos 30 Dias)")
    
    # Encontrar o pico
    peak_row = df.loc[df["Novos Seguidores"].idxmax()]
    peak_val = peak_row["Novos Seguidores"]
    peak_date = peak_row["Data"]
    
    # Criar um card de destaque para o recorde
    st.markdown(f"""
    <div class="metric-card" style="margin-bottom: 20px;">
        <div class="metric-label">Maior Pico (Últimos 30d)</div>
        <div class="metric-value" style="color: #FFB300;">+{int(peak_val)} <span style="font-size: 0.9rem; font-weight: normal; color: #8B949E;">Seguidores</span></div>
        <div style="font-size: 0.8rem; color: #8B949E; margin-top: 5px;">Recorde registrado em: <strong>{peak_date}</strong></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Gráfico de Área
    fig = px.area(
        df, 
        x="Data", 
        y="Novos Seguidores",
        color_discrete_sequence=["#FFB300"]
    )
    
    fig.update_traces(
        line_shape='spline',
        mode='lines+markers',
        fill='tozeroy',
        marker=dict(size=6, color="#FFB300", line=dict(width=1, color="white")),
        hovertemplate="<b>%{x}</b><br>Novos Seguidores: %{y}<extra></extra>"
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="#E2E8F0"),
        xaxis=dict(
            title="", 
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor="rgba(255,255,255,0.1)",
            tickangle=-45
        ),
        yaxis=dict(
            title="", 
            showgrid=True,
            gridcolor="rgba(255,255,255,0.05)",
            zeroline=True,
            zerolinecolor="rgba(255,255,255,0.1)"
        ),
        margin=dict(l=10, r=45, t=10, b=45),
        height=350,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
