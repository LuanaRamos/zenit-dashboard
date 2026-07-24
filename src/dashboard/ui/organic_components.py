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


def _format_compact(val: int) -> str:
    """Função utilitária (Dataviz) para encurtar números para K ou M."""
    if pd.isna(val):
        return "0"
    if val >= 1_000_000:
        return f"{val/1_000_000:.1f}M"
    elif val >= 1_000:
        return f"{val/1_000:.1f}K"
    return str(int(val))

def render_posts_table(media_list: List[InstagramMedia], stories_list: List[InstagramStory] = None):
    """Renderiza a tabela linha a linha filtrada por tipo de conteúdo e visão de dados."""
    if stories_list is None:
        stories_list = []
        
    st.markdown("### Análise Individual por Publicação")
    
    # UI: Filtro de Visão de Dados (Big Picture) e Formato
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
        
    # Renderização Condicional de Stories
    if media_type_filter == "Stories (Ativos 24h)":
        if not stories_list:
            st.info("Você não tem Stories ativos no momento. Publique algo para acompanhar o desempenho aqui.")
            return
            
        st.markdown("#### Desempenho de Stories (Últimas 24h)")
        data = []
        for s in stories_list:
            data.append({
                "Resumo": "Story Ativo",
                "Alcance": _format_compact(s.reach),
                "Avanços": _format_compact(s.taps_forward),
                "Voltas": _format_compact(s.taps_back),
                "Saídas": _format_compact(s.exits),
                "Respostas": _format_compact(s.replies),
                "Visualizar no IG": s.permalink
            })
            
        df_stories = pd.DataFrame(data)
        st.dataframe(
            df_stories,
            use_container_width=True,
            column_config={
                "Visualizar no IG": st.column_config.LinkColumn("Link Direto", display_text="Abrir Story")
            },
            hide_index=True
        )
        return

    # Filtragem Base para Posts do Feed/Reels
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
        
        # Mapeamento Condicional baseado no Radio Button
        if data_view == "Apenas Orgânico":
            likes = m.like_count
            reach = m.organic_reach
            shares = m.shares
            saved = m.saved
        elif data_view == "Apenas Pago (Ads)":
            likes = m.paid_likes
            reach = m.paid_reach
            shares = m.paid_shares
            saved = m.paid_saved
        else: # Total Mix
            likes = m.total_likes
            reach = m.reach
            shares = m.total_shares
            saved = m.total_saved

        row = {
            "Publicação": short_caption,
            "Likes": _format_compact(likes),
            "Alcance": _format_compact(reach),
            "Shares": _format_compact(shares),
            "Salvos": _format_compact(saved)
        }
        
        # O Ads Manager não fornece watch_time nem follows para os posts patrocinados, 
        # então ocultamos no Paid mode para evitar laranjas misturadas com maçãs.
        if data_view != "Apenas Pago (Ads)":
            if media_type_filter == "Reels":
                # API devolve em ms, convertendo para segundos:
                watch_time_s = m.ig_reels_video_view_total_time / 1000.0 if m.ig_reels_video_view_total_time > 0 else 0
                avg_watch_time_s = m.ig_reels_avg_watch_time / 1000.0 if m.ig_reels_avg_watch_time > 0 else 0
                row["Watch Time Total"] = f"{watch_time_s:.1f}s"
                row["Retenção Média"] = f"{avg_watch_time_s:.1f}s"
            else:
                row["Seguidores (Follows)"] = _format_compact(m.follows)
                row["Visitas ao Perfil"] = _format_compact(m.profile_visits)
        
        row["Visualizar no IG"] = m.permalink
        data.append(row)
        
    df = pd.DataFrame(data).fillna(0)
    
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Visualizar no IG": st.column_config.LinkColumn("Link Direto", display_text="Abrir post")
        },
        hide_index=True
    )
