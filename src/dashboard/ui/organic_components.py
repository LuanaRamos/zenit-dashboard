import streamlit as st
import pandas as pd
from typing import List
from schemas.instagram import InstagramMedia, InstagramStory

def render_organic_metrics_cards(media_list: List[InstagramMedia]):
    """Renderiza os cartões de métricas consolidadas (Visão Geral)."""
    if not media_list:
        st.info("Você não publicou conteúdo orgânico recentemente. Poste um Reels ou Carrossel no Instagram para acompanhar seu alcance gratuito aqui.")
        return

    total_organic_reach = sum(m.organic_reach for m in media_list)
    total_paid_reach = sum(m.paid_reach for m in media_list)
    total_reach = total_organic_reach + total_paid_reach
    
    pct_organic = (total_organic_reach / total_reach * 100) if total_reach > 0 else 0
    pct_paid = (total_paid_reach / total_reach * 100) if total_reach > 0 else 0
    st.markdown(f"### Visão Geral ({len(media_list)} Publicações)")
    cols = st.columns(3)
    
    with cols[0]:
        st.metric(
            label="Alcance Total Global", 
            value=f"{total_reach:,}".replace(",", "."),
            help="Total de pessoas alcançadas (Orgânico + Pago)."
        )
        
    with cols[1]:
        st.metric(
            label="Alcance Puramente Orgânico", 
            value=f"{total_organic_reach:,}".replace(",", "."),
            delta=f"{pct_organic:.1f}% do Total",
            delta_color="normal",
            help="Pessoas alcançadas naturalmente, sem o uso de anúncios."
        )
        
    with cols[2]:
        st.metric(
            label="Alcance via Ads (Pago)", 
            value=f"{total_paid_reach:,}".replace(",", "."),
            delta=f"{pct_paid:.1f}% do Total",
            delta_color="off",
            help="Pessoas alcançadas através de impulsionamento pago."
        )


def _ms_to_hhmmss(ms: float) -> str:
    """
    Converte milissegundos em string HH:MM:SS com zero-padding.
    
    Zero-padding garante que a ordenacao alfabetica coincide com a numerica:
    '00:09:03' < '00:45:01' < '06:29:00' - correto em ambas as ordens.
    """
    if not ms or ms <= 0:
        return "00:00:00"
    total_s = int(ms / 1000)
    hours   = total_s // 3600
    minutes = (total_s % 3600) // 60
    seconds = total_s % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def render_posts_table(media_list: List[InstagramMedia], stories_list: List[InstagramStory] = None):
    """
    Renderiza a tabela de publicacoes.
    - Colunas numericas: valores int/float para ordenacao correta pelo Streamlit.
    - format=',.0f' usa separador de milhar do locale do browser (pt-BR = ponto).
    - Colunas de tempo: string HH:MM:SS (zero-padded = ordena corretamente mesmo sendo string).
    """
    if stories_list is None:
        stories_list = []
        
    st.markdown("### Análise Individual por Publicação")
    
    view_col, format_col = st.columns([1, 1])
    
    with view_col:
        data_view = st.radio(
            "Visão de Dados:",
            ["Total (Mix)", "Apenas Orgânico", "Apenas Pago (Ads)"],
            horizontal=True,
            help="Decida como os dados numéricos devem ser exibidos nas tabelas abaixo."
        )
        
    with format_col:
        media_type_filter = st.selectbox(
            "Filtrar por Formato:",
            ["Reels", "Carrossel", "Post Estático", "Stories (Ativos 24h)"]
        )
        
    # --- Stories ---
    if media_type_filter == "Stories (Ativos 24h)":
        if not stories_list:
            st.info("Você não tem Stories ativos no momento. Publique algo para acompanhar o desempenho aqui.")
            return
            
        st.markdown("#### Desempenho de Stories (Últimas 24h)")
        data = [{
            "Resumo": "Story Ativo",
            "Alcance":   s.reach,
            "Avanços":  s.taps_forward,
            "Voltas":    s.taps_back,
            "Saídas":   s.exits,
            "Respostas": s.replies,
            "Visualizar no IG": s.permalink
        } for s in stories_list]
            
        df_stories = pd.DataFrame(data)
        st.dataframe(
            df_stories,
            use_container_width=True,
            column_config={
                # format=',.0f' = separador de milhar via locale do browser (pt-BR = ponto)
                "Alcance":   st.column_config.NumberColumn("Alcance",   format=",.0f"),
                "Avanços":  st.column_config.NumberColumn("Avanços",   format=",.0f"),
                "Voltas":    st.column_config.NumberColumn("Voltas",    format=",.0f"),
                "Saídas":   st.column_config.NumberColumn("Saídas",   format=",.0f"),
                "Respostas": st.column_config.NumberColumn("Respostas", format=",.0f"),
                "Visualizar no IG": st.column_config.LinkColumn("Link Direto", display_text="Abrir Story")
            },
            hide_index=True
        )
        return

    # --- Feed / Reels ---
    filtered_media = []
    for m in media_list:
        if media_type_filter == "Reels" and m.media_product_type == "REELS":
            filtered_media.append(m)
        elif media_type_filter == "Carrossel" and m.media_type == "CAROUSEL_ALBUM":
            filtered_media.append(m)
        elif media_type_filter == "Post Estático" and m.media_type in ["IMAGE", "VIDEO"] and m.media_product_type != "REELS":
            filtered_media.append(m)
            
    if not filtered_media:
        st.info(f"Nenhum {media_type_filter} encontrado neste período.")
        return

    data = []
    for m in filtered_media:
        short_caption = m.caption[:40].replace('\n', ' ') + "..." if len(m.caption) > 40 else m.caption
        
        # Valores NUMERICOS (int) para que a ordenacao do Streamlit funcione corretamente
        if data_view == "Apenas Orgânico":
            likes  = m.like_count
            reach  = m.organic_reach
            shares = m.shares
            saved  = m.saved
        elif data_view == "Apenas Pago (Ads)":
            likes  = m.paid_likes
            reach  = m.paid_reach
            shares = m.paid_shares
            saved  = m.paid_saved
        else:  # Total Mix
            likes  = m.total_likes
            reach  = m.reach
            shares = m.total_shares
            saved  = m.total_saved

        row: dict = {
            "Publicação": short_caption,
            "Likes":   likes,
            "Alcance": reach,
            "Shares":  shares,
            "Salvos":  saved,
        }
        
        # Watch time apenas nos modos que incluem dados organicos
        if data_view != "Apenas Pago (Ads)":
            if media_type_filter == "Reels":
                # HH:MM:SS com zero-padding ordena corretamente mesmo sendo string
                row["Watch Time Total"] = _ms_to_hhmmss(m.ig_reels_video_view_total_time)
                row["Retenção Média"]  = _ms_to_hhmmss(m.ig_reels_avg_watch_time)
            else:
                row["Seguidores"]        = m.follows
                row["Visitas ao Perfil"] = m.profile_visits
        
        row["Visualizar no IG"] = m.permalink
        data.append(row)
        
    df = pd.DataFrame(data).fillna(0)
    
    # format=',.0f' = notacao d3, usa separador de milhar do locale do browser
    # Em navegadores pt-BR: 4.400 | Em navegadores en-US: 4,400
    col_config: dict = {
        "Likes":   st.column_config.NumberColumn("Likes",   format=",.0f"),
        "Alcance": st.column_config.NumberColumn("Alcance", format=",.0f"),
        "Shares":  st.column_config.NumberColumn("Shares",  format=",.0f"),
        "Salvos":  st.column_config.NumberColumn("Salvos",  format=",.0f"),
        "Visualizar no IG": st.column_config.LinkColumn("Link Direto", display_text="Abrir post"),
    }
    
    if data_view != "Apenas Pago (Ads)" and media_type_filter != "Reels":
        col_config["Seguidores"]        = st.column_config.NumberColumn("Seguidores",       format=",.0f")
        col_config["Visitas ao Perfil"] = st.column_config.NumberColumn("Visitas ao Perfil", format=",.0f")
    
    st.dataframe(
        df,
        use_container_width=True,
        column_config=col_config,
        hide_index=True
    )
