import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
from schemas.instagram import InstagramMedia, InstagramStory
from ui.components import render_metric_card, render_glass_table
from typing import Any


def render_organic_metrics_cards(media_list: list[InstagramMedia]) -> None:
    """Renderiza os cartões de métricas consolidadas (Visão Geral)."""
    if not media_list:
        st.info(
            "Você não publicou conteúdo orgânico recentemente. Poste um Reels ou Carrossel no Instagram para acompanhar seu alcance gratuito aqui."
        )
        return

    total_organic_reach = sum(m.organic_reach for m in media_list)
    total_paid_reach = sum(m.paid_reach for m in media_list)
    total_reach = total_organic_reach + total_paid_reach

    pct_organic = (total_organic_reach / total_reach * 100) if total_reach > 0 else 0
    pct_paid = (total_paid_reach / total_reach * 100) if total_reach > 0 else 0
    
    st.markdown(f"### Visão Geral ({len(media_list)} Publicações)")
    cols = st.columns(3)

    with cols[0]:
        render_metric_card(
            label='<i class="bi bi-people"></i> Alcance Total Global',
            value=f"{total_reach:,}".replace(",", "."),
            help_text="Orgânico + Pago"
        )

    with cols[1]:
        render_metric_card(
            label='<i class="bi bi-phone"></i> Alcance Puramente Orgânico',
            value=f"{total_organic_reach:,}".replace(",", "."),
            delta=f"{pct_organic:.1f}% do Total",
            delta_type="green"
        )

    with cols[2]:
        render_metric_card(
            label='<i class="bi bi-megaphone"></i> Alcance via Ads (Pago)',
            value=f"{total_paid_reach:,}".replace(",", "."),
            delta=f"{pct_paid:.1f}% do Total",
            delta_type="gold"
        )


    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- Top Posts Bento Grid ---
    if media_list:
        st.markdown("#### 🔥 Top Posts de Maior Alcance")
        # Sort by total reach
        top_posts = sorted(media_list, key=lambda x: (x.organic_reach + x.paid_reach), reverse=True)[:3]
        
        b1, b2, b3 = st.columns(3)
        cols = [b1, b2, b3]
        
        for idx, post in enumerate(top_posts):
            with cols[idx]:
                short_text = (post.caption[:50].replace("\n", " ") + "...") if len(post.caption) > 50 else post.caption
                likes = post.like_count
                reach = post.organic_reach + post.paid_reach
                
                # Choose icon based on type
                if post.media_product_type == "REELS":
                    icon = "🎬"
                elif post.media_type == "CAROUSEL_ALBUM":
                    icon = "📸"
                else:
                    icon = "📱"
                
                st.markdown(f"""
                <div class="glass-card" style="margin-bottom: 1rem; display: flex; flex-direction: column;">
                    <div style="font-size: 1.5rem; margin-bottom: 12px;">{icon}</div>
                    <div style="color: #8B949E; font-size: 0.85rem; line-height: 1.4; margin-bottom: 16px;">{short_text}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px; margin-top: auto;">
                        <div style="color: #ffffff; font-weight: 600; font-size: 0.95rem;">👁️ {reach:,} &nbsp; <span style="color:#8B949E; font-weight:400;">❤️ {likes:,}</span></div>
                        <a href="{post.permalink}" target="_blank" style="color: #FFB300; font-size: 1.1rem; text-decoration: none;"><i class="bi bi-box-arrow-up-right"></i></a>
                    </div>
                </div>
                """.replace(",", "."), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

def _ms_to_hhmmss(ms: float) -> str:
    if not ms or ms <= 0:
        return "00:00:00"
    total_s = int(ms / 1000)
    hours = total_s // 3600
    minutes = (total_s % 3600) // 60
    seconds = total_s % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def render_posts_table(
    media_list: list[InstagramMedia], stories_list: list[InstagramStory] | None = None
) -> None:
    if stories_list is None:
        stories_list = []

    st.markdown("### Análise Individual por Publicação")

    view_col, format_col = st.columns([1, 1])

    with view_col:
        st.markdown("<h4 style='color: #8B949E; font-size: 0.85rem; margin-bottom: 8px; font-weight: 500;'>Visão de Dados:</h4>", unsafe_allow_html=True)
        data_view = option_menu(
            menu_title=None,
            options=["Total (Mix)", "Apenas Orgânico", "Apenas Pago (Ads)"],
            icons=["pie-chart-fill", "hash", "cash-coin"],
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#8B949E", "font-size": "14px"},
                "nav-link": {
                    "font-size": "13px",
                    "text-align": "center",
                    "margin": "0px 6px 0px 0px",
                    "--hover-color": "rgba(255, 255, 255, 0.03)",
                    "border-radius": "8px",
                    "padding": "8px 12px",
                    "border": "1px solid transparent",
                    "color": "#8B949E",
                    "font-family": "Inter, sans-serif",
                    "font-weight": "500",
                    "transition": "all 0.2s ease",
                },
                "nav-link-selected": {
                    "background": "rgba(255, 179, 0, 0.1)",
                    "border": "1px solid rgba(255, 179, 0, 0.2)",
                    "box-shadow": "none",
                    "color": "#FFB300",
                    "font-weight": "600"
                },
            }
        )

    with format_col:
        st.markdown("<h4 style='color: transparent; font-size: 0.85rem; margin-bottom: -15px;'>.</h4>", unsafe_allow_html=True)
        media_type_filter = st.selectbox(
            "Filtrar por Formato:",
            ["Reels", "Carrossel", "Post Estático", "Stories (Ativos 24h)"],
            label_visibility="collapsed"
        )

    # --- Stories ---
    if media_type_filter == "Stories (Ativos 24h)":
        if not stories_list:
            st.info(
                "Você não tem Stories ativos no momento. Publique algo para acompanhar o desempenho aqui."
            )
            return

        st.markdown("#### Desempenho de Stories (Últimas 24h)")
        data = [
            {
                "Resumo": "Story Ativo",
                "Alcance": int(s.reach),
                "Avanços": int(s.taps_forward),
                "Voltas": int(s.taps_back),
                "Saídas": int(s.exits),
                "Respostas": int(s.replies),
                "Visualizar no IG": s.permalink if s.permalink else "",
            }
            for s in stories_list
        ]

        df_stories = pd.DataFrame(data)
        render_glass_table(df_stories)
        return

def render_posts_table(media_list: list[InstagramMedia], stories_list: list[InstagramStory]) -> None:
    """Renderiza tabela detalhada de publicações combinando Feed e Stories."""
    if not media_list and not stories_list:
        return
        
    st.markdown("#### Análise Individual por Publicação")
    
    # Toggle Filters inside layout
    f1, f2, f3, f4 = st.columns([1.5, 1, 1, 2])
    with f1:
        view_mode = option_menu(
            menu_title=None,
            options=["Total (Mix)", "Apenas Orgânico", "Apenas Pago (Ads)"],
            icons=["pie-chart", "hash", "megaphone"],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "#151515", "border-radius": "8px", "border": "1px solid rgba(255,255,255,0.05)"},
                "icon": {"color": "#8B949E", "font-size": "12px"},
                "nav-link": {"font-size": "11px", "text-align": "center", "margin": "0px", "--hover-color": "rgba(255, 255, 255, 0.05)", "color": "#8B949E"},
                "nav-link-selected": {"background-color": "rgba(255, 179, 0, 0.1)", "color": "#FFB300", "font-weight": "600", "border-radius": "8px"},
            }
        )
    with f4:
        content_type_filter = st.selectbox(
            "Tipo de Conteúdo",
            ["Todos os Formatos", "Reels", "Carrossel", "Imagem Única", "Stories (24h)"],
            label_visibility="collapsed"
        )
        
    st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)

    data = []
    
    # 1. Process Feed Media
    for m in media_list:
        if content_type_filter == "Reels" and m.media_type != "VIDEO": continue
        if content_type_filter == "Carrossel" and m.media_type != "CAROUSEL_ALBUM": continue
        if content_type_filter == "Imagem Única" and m.media_type != "IMAGE": continue
        if content_type_filter == "Stories (24h)": continue # Skip feed when filtering for stories

        # View Mode Logic
        if "Apenas Orgânico" in view_mode:
            reach = m.organic_reach
            likes = m.like_count
            shares = m.shares
            saved = m.saved
            follows = m.follows
            profile_visits = m.profile_visits
            if reach == 0 and m.paid_reach > 0: continue # Purely paid post
        elif "Apenas Pago" in view_mode:
            reach = m.paid_reach
            likes = m.paid_likes
            shares = m.paid_shares
            saved = m.paid_saved
            follows = 0 # Follows attribution in ads is handled in profile campaigns
            profile_visits = 0
            if reach == 0: continue # Purely organic post
        else:
            reach = m.organic_reach + m.paid_reach
            likes = m.total_likes
            shares = m.total_shares
            saved = m.total_saved
            follows = m.follows
            profile_visits = m.profile_visits

        # Fix attribute names matching InstagramMedia schema
        row = {
            "Tipo": "🎬 Reels" if m.media_type == "VIDEO" else "📱 Carrossel" if m.media_type == "CAROUSEL_ALBUM" else "🖼️ Imagem",
            "Publicação": m.caption[:45] + "..." if m.caption else "Sem legenda",
            "Data": m.timestamp.split("T")[0] if m.timestamp else "-",
            "Alcance": reach,
            "Likes": likes,
            "Comentários": m.comments_count,
            "Shares": shares,
            "Salvos": saved,
            "Seguidores": follows,
            "Visitas Perfil": profile_visits,
        }
        
        # Link in raw HTML for st.markdown, but we are switching to st.dataframe which supports clickable URLs if configured, but let's just use the URL
        row["Visualizar no IG"] = m.permalink
        data.append(row)

    # 2. Process Stories
    if content_type_filter in ["Todos os Formatos", "Stories (24h)"]:
        for s in stories_list:
            if "Apenas Pago" in view_mode:
                continue # Stories API generally only returns organic data unless promoted
                
            row = {
                "Tipo": "⏱️ Story",
                "Publicação": s.caption[:45] + "..." if s.caption else "Story 24h",
                "Data": s.timestamp.split("T")[0] if s.timestamp else "-",
                "Alcance": s.reach,
                "Likes": s.replies, # Stories don't have public likes in the same way, using replies or 0
                "Comentários": s.replies,
                "Shares": 0,
                "Salvos": 0,
                "Seguidores": 0,
                "Visitas Perfil": 0,
                "Visualizar no IG": s.permalink
            }
            data.append(row)

    if not data:
        st.info("Nenhuma publicação encontrada para os filtros selecionados.")
        return

    df = pd.DataFrame(data).fillna(0)
    num_cols = [
        "Likes",
        "Alcance",
        "Shares",
        "Salvos",
        "Seguidores",
        "Visitas Perfil",
        "Comentários"
    ]
    
    for c in num_cols:
        if c in df.columns:
            # Convert to numeric first, coercing errors
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # Sort
    df = df.sort_values(by="Alcance", ascending=False)
    
    # Use a tabela de vidro estilizada
    render_glass_table(
        df,
        currency_cols=[],
        link_col="Visualizar no IG",
        link_label="Abrir ↗",
        key="organic_posts_table",
        csv_filename="publicacoes_organicas.csv"
    )
