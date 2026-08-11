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

def render_account_insights_cards(insights: dict, paid_totals: dict, followers_history: list = None) -> None:
    """Renderiza KPIs sem apresentar métricas mistas como se fossem orgânicas."""
    st.markdown("### 👁️ Visão Geral da Conta")
    if insights.get("_is_partial"):
        st.info("⚠️ **Nota sobre o Período:** A Meta restringe algumas métricas gerais de conta aos últimos 13 meses. Insights detalhados de publicações ficam disponíveis por até 2 anos.")
    if insights.get("_is_segmented"):
        st.info("ℹ️ Em períodos maiores que 30 dias, alcance e contas engajadas são somas de janelas. A mesma pessoa pode aparecer em mais de uma janela.")
    
    # Calcula novos seguidores dos últimos 30 dias a partir do histórico real da API
    new_followers_30d = 0
    if followers_history:
        for item in followers_history:
            # Suporta tanto o formato raw {"value": N} quanto o transformado {"Novos Seguidores": N}
            val = item.get("Novos Seguidores") or item.get("value", 0)
            if val and val > 0:
                new_followers_30d += val
    
    # O alcance de conta inclui anúncios. Não é matematicamente seguro subtrair
    # o reach pago porque as audiências podem se sobrepor. As demais métricas
    # de conta também não são apresentadas como um total orgânico.
    r_ig = insights.get('reach', 0)
    r_paid = paid_totals.get('reach', 0)
    
    likes_ig = insights.get('likes', 0)
    likes_paid = paid_totals.get('likes', 0)
    
    shares_ig = insights.get('shares', 0)
    shares_paid = paid_totals.get('shares', 0)
    
    saves_ig = max(0, insights.get('saves', 0))
    saves_paid = max(0, paid_totals.get('saved', 0))
    
    int_ig = insights.get('total_interactions', 0)
    
    def fmt(val): return f"{int(val):,}".replace(",", ".")
    def paid_context(paid): return f"Pago no Instagram: {fmt(paid)} (já pode estar incluído no total)"
    
    st.markdown("#### 🎯 Métricas Totais")
    cols_mix = st.columns(5)
    with cols_mix[0]:
        render_metric_card("Alcance da Conta", fmt(r_ig), "Inclui anúncios", "Total informado pelo Instagram; não subtrair o pago")
    with cols_mix[1]:
        render_metric_card("Alcance Pago no Instagram", fmt(r_paid), "Ads do Instagram", "Não inclui placements do Facebook")
    with cols_mix[2]:
        render_metric_card("Total de Interações", fmt(int_ig), "Total da conta", "Não é usado como total orgânico")
    with cols_mix[3]:
        render_metric_card("Curtidas", fmt(likes_ig), paid_context(likes_paid), "Não é usado como total orgânico")
    with cols_mix[4]:
        render_metric_card("Compartilhamentos", fmt(shares_ig), paid_context(shares_paid), "Não é usado como total orgânico")

    st.write("")
    st.markdown("#### 👤 Ações Registradas no Perfil")
    cols_org = st.columns(4)
    with cols_org[0]:
        render_metric_card("Visitas ao Perfil", fmt(insights.get('profile_views', 0)), "Total", "Acessos à bio")
    with cols_org[1]:
        render_metric_card("Toques no Link", fmt(insights.get('profile_links_taps', 0)), "Total", "Cliques no link da bio")
    with cols_org[2]:
        render_metric_card("Cliques no Site", fmt(insights.get('website_clicks', 0)), "Total", "Cliques gerais")
    with cols_org[3]:
        render_metric_card("Contas Engajadas", fmt(insights.get('accounts_engaged', 0)), "Total (Max 13m)", "Usuários únicos")
        
    st.write("")
    cols_org2 = st.columns(4)
    with cols_org2[0]:
        render_metric_card("Comentários", fmt(insights.get('comments', 0)), "Total da conta", "Não é usado como total orgânico")
    with cols_org2[1]:
        render_metric_card("Salvamentos", fmt(saves_ig), paid_context(saves_paid), "Total da conta")
    with cols_org2[2]:
        render_metric_card(
            "Novos Seguidores",
            fmt(new_followers_30d),
            "Total",
            "⚠️ A Meta só permite consultar seguidores dos últimos 30 dias, independente do filtro."
        )
    with cols_org2[3]:
        st.empty() # Espaço vazio para alinhar

def render_organic_metrics_cards(media_list: List[InstagramMedia]) -> None:
    """Renderiza somas por publicação, deixando explícita a não deduplicação."""
    st.markdown("### 📊 Publicações: Orgânico vs Ads")
    
    total_ig_reach = sum(m.reach for m in media_list)
    total_paid_reach = sum(m.paid_reach for m in media_list)
    total_engagement = sum(
        m.total_interactions
        + m.paid_likes
        + m.paid_comments
        + m.paid_shares
        + m.paid_saved
        for m in media_list
    )
    
    cols = st.columns(3)
    with cols[0]:
        render_metric_card("Soma do Alcance Orgânico", f"{int(total_ig_reach):,}".replace(",", "."), "Não deduplicado", "A mesma pessoa pode aparecer em mais de um post")
    with cols[1]:
        render_metric_card("Soma do Alcance Pago", f"{int(total_paid_reach):,}".replace(",", "."), "Não deduplicado", "Somente placements do Instagram")
    with cols[2]:
        render_metric_card("Interações nas Publicações", f"{int(total_engagement):,}".replace(",", "."), "Orgânico + pago", "Curtidas, comentários, compartilhamentos e salvamentos")

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
            
        # Fallbacks (None) para métricas que não existem em certos formatos
        visitas = None if tipo == "Reels" else m.profile_visits
        tempo_total = format_hhmmss(m.ig_reels_video_view_total_time) if tipo == "Reels" else None
        tempo_medio = format_hhmmss(m.ig_reels_avg_watch_time) if tipo == "Reels" else None
        
        visualizacoes = None if tipo not in ["Reels", "Vídeo"] else m.organic_views

        # Format timestamp if possible
        data_hora = m.timestamp
        if data_hora and "T" in data_hora:
            try:
                # Basic ISO format parse
                data_hora = data_hora.replace("+0000", "").replace(".000Z", "")
                data_hora = data_hora.replace("T", " ")
            except:
                pass

        data.append({
            "ID": m.id,
            "Data e Hora": data_hora,
            "Tipo": tipo,
            "Legenda (Texto)": m.caption,
            "Imagem (URL)": m.thumbnail_url if m.thumbnail_url else m.media_url,
            "Visualizações (Orgânico)": visualizacoes,
            "Alcance (Instagram)": m.reach,
            "Visitas ao Perfil": visitas,
            "Tempo Assistido": tempo_total,
            "Tempo Médio": tempo_medio,
            "Curtidas (Instagram)": m.like_count,
            "Comentários (Instagram)": m.comments_count,
            "Salvamentos (Instagram)": m.saved,
            "Compartilhamentos (Instagram)": m.shares,
            "Alcance (Pago)": m.paid_reach,
            "Curtidas (Pago)": m.paid_likes,
            "Cliques no Criativo (Pago)": m.paid_other_clicks,
            "Cliques de Saída (Pago)": m.paid_link_clicks,
            "Destino do Tráfego (Pago)": m.paid_destination,
            "Qtd. Anúncios": m.paid_ad_count if m.paid_ad_count > 0 else None,
            
            # Custos
            "Custo (R$)": m.paid_spend,
            "CPM (R$)": m.paid_cpm,
            "CPC (R$)": m.paid_cpc,
            "CPP (R$)": m.paid_cpp,
            "CTR (%)": m.paid_ctr,
            "Custo por Engajamento (CPA) (R$)": m.paid_cpa if m.paid_cpa > 0 else None,
            "Custo por Clique de Saída (R$)": m.paid_cost_per_outbound_click if m.paid_cost_per_outbound_click > 0 else None,
            
            # Entrega
            "Impressões (Pago)": m.paid_impressions,
            "Frequência": m.paid_frequency,
            
            # Engajamento Pago Puro
            "Comentários (Pago)": m.paid_comments,
            "Salvamentos (Pago)": m.paid_saved,
            "Compartilhamentos (Pago)": m.paid_shares,
            
            # Vídeo Pago
            "Tempo Assistido Médio (Pago)": format_hhmmss(m.paid_video_avg_time * 1000),
            "Vídeo 25% (Pago)": m.paid_video_p25,
            "Vídeo 50% (Pago)": m.paid_video_p50,
            "Vídeo 75% (Pago)": m.paid_video_p75,
            
            # Conversão (N/A se não há pixel de compra)
            "Valor de Ação (R$)": m.paid_action_values if m.paid_action_values > 0 else None,
            "ROAS": m.paid_roas if m.paid_roas > 0 else None,
            
            # Contexto
            "Objetivo (Pago)": m.paid_objective,
            "Meta de Otimização (Pago)": m.paid_optimization_goal,
            "Data Início (Pago)": m.paid_date_start,
            "Data Fim (Pago)": m.paid_date_stop,
            
            "Link": m.permalink
        })
        
    df = pd.DataFrame(data)
    
    # 1. Download Unificado
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇ Baixar CSV Unificado (Orgânico + Pago)",
        data=csv_bytes,
        file_name="posts_unificado.csv",
        mime="text/csv",
    )
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2. Tabela Instagram
    st.markdown("#### Desempenho no Instagram")
    cols_org = ["ID", "Data e Hora", "Tipo", "Visualizações (Orgânico)", "Alcance (Instagram)", "Visitas ao Perfil", "Tempo Assistido", "Tempo Médio", "Curtidas (Instagram)", "Comentários (Instagram)", "Salvamentos (Instagram)", "Compartilhamentos (Instagram)", "Link"]
    df_org = df[cols_org]
    render_glass_table(df_org, key="tbl_posts_org", hide_download=True, link_col="Link", link_label="Ver no Instagram")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 3. Tabela Paga (apenas posts que receberam tráfego pago)
    st.markdown("#### Desempenho Pago (Dark Posts / Impulsionados)")
    cols_paid = [
        "ID", "Data e Hora", "Tipo", "Qtd. Anúncios", "Destino do Tráfego (Pago)", "Alcance (Pago)", "Impressões (Pago)", "Frequência", 
        "Custo (R$)", "CPM (R$)", "CPC (R$)", "CPP (R$)", "CTR (%)", "Custo por Engajamento (CPA) (R$)", "Custo por Clique de Saída (R$)", 
        "Curtidas (Pago)", "Comentários (Pago)", "Salvamentos (Pago)", "Compartilhamentos (Pago)", 
        "Cliques no Criativo (Pago)", "Cliques de Saída (Pago)", 
        "Tempo Assistido Médio (Pago)", "Vídeo 25% (Pago)", "Vídeo 50% (Pago)", "Vídeo 75% (Pago)", 
        "Valor de Ação (R$)", "ROAS", "Objetivo (Pago)", "Meta de Otimização (Pago)", "Data Início (Pago)", "Data Fim (Pago)", 
        "Link"
    ]
    df_paid = df[df["Alcance (Pago)"] > 0][cols_paid]
    
    if not df_paid.empty:
        curr_cols = ["Custo (R$)", "CPM (R$)", "CPC (R$)", "CPP (R$)", "Custo por Engajamento (CPA) (R$)", "Custo por Clique de Saída (R$)", "Valor de Ação (R$)"]
        float_cols = ["Frequência", "ROAS"]
        pct_cols = ["CTR (%)"]
        render_glass_table(df_paid, key="tbl_posts_paid", currency_cols=curr_cols, float_cols=float_cols, percent_cols=pct_cols, hide_download=True, link_col="Link", link_label="Ver no Instagram")
    else:
        st.info("Nenhum post desta lista recebeu tráfego pago no período.")

def render_top_posts_and_comments(media_list: List[InstagramMedia]) -> None:
    """Renderiza destaques e os melhores comentários de cada post."""
    st.markdown("### 🏆 Top Posts (Maior Alcance Total)")
    
    if not media_list:
        return
        
    # Ordena por alcance IG
    sorted_media = sorted(media_list, key=lambda x: x.reach, reverse=True)
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

            alcance_org = f"{int(m.reach):,}".replace(",", ".")
            alcance_pago = f"{int(m.paid_reach):,}".replace(",", ".")
            curtidas = f"{int(m.like_count):,}".replace(",", ".")
            comentarios = f"{int(m.comments_count):,}".replace(",", ".")
            compartilhamentos = f"{int(m.shares):,}".replace(",", ".")
            
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
            <div style="font-size: 0.7rem; color: #c4c9ac;">&#10084; Curtidas</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #E2E8F0;">{comentarios}</div>
            <div style="font-size: 0.7rem; color: #c4c9ac;">&#128172; Coment.</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #E2E8F0;">{compartilhamentos}</div>
            <div style="font-size: 0.7rem; color: #c4c9ac;">&#128260; Comp.</div>
        </div>
    </div>
    <div style="margin-bottom: 15px;">
        <div style="color: #FFB300; font-size: 1.2rem; font-weight: bold;">Alcance (Instagram): {alcance_org}</div>
        <div style="font-size: 0.8rem; color: #c4c9ac;">Alcance Pago (Ads): {alcance_pago}</div>
    </div>"""
            
            c = best_comments[i] if i < len(best_comments) else None
            if c:
                text = c.get("text", "")
                username = c.get("username", "Usuário")
                likes = c.get("like_count", 0)
                html += f"""<div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; text-align: left; font-size: 0.85rem; border-left: 3px solid #FFB300; margin-top: 10px;">
        <div style="color: #E2E8F0; margin-bottom: 4px;">"{text}"</div>
        <div style="color: #c4c9ac; font-size: 0.75rem;"><strong>@{username}</strong> &bull; {likes} curtidas</div>
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
    <div style="color: #c4c9ac; font-size: 0.9rem;">
        <strong>@{username}</strong> • 🏆 {int(likes):,} curtidas
    </div>
</div>""".replace(",", ".")
        st.markdown(html, unsafe_allow_html=True)
        
        st.write("")
        df_comments = pd.DataFrame(all_comments)
        
        # Formatar Data e Hora para o CSV de comentários
        if "timestamp" in df_comments.columns:
            df_comments["Data e Hora"] = df_comments["timestamp"].str.replace("+0000", "", regex=False).str.replace(".000Z", "", regex=False).str.replace("T", " ", regex=False)
            df_comments = df_comments.drop(columns=["timestamp"])
            
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
        <div class="metric-value" style="color: #FFB300;">+{int(peak_val)} <span style="font-size: 0.9rem; font-weight: normal; color: #c4c9ac;">Seguidores</span></div>
        <div style="font-size: 0.8rem; color: #c4c9ac; margin-top: 5px;">Recorde registrado em: <strong>{peak_date}</strong></div>
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
