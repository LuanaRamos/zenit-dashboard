import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
from schemas.instagram import InstagramMedia, InstagramStory
from ui.components import render_metric_card
from typing import Any

try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

    HAS_AGGRID = True
except ImportError:
    HAS_AGGRID = False

# Formatador JavaScript para o AgGrid: Exibe numeros com ponto no padrao pt-BR (ex: 4.400)
# mas mantem a ordenacao inteiramente numerica
NUMBER_FORMATTER = (
    JsCode("""
function(params) {
    if (params.value === undefined || params.value === null) return '0';
    return Number(params.value).toLocaleString('pt-BR');
}
""")
    if HAS_AGGRID
    else None
)

# Renderizador JavaScript de Link usando o contrato oficial de Componente de Celula do AG Grid
LINK_RENDERER = (
    JsCode("""
(function() {
    function UrlRenderer() {}
    UrlRenderer.prototype.init = function(params) {
        this.eGui = document.createElement('a');
        if (params.value) {
            this.eGui.href = params.value;
            this.eGui.target = '_blank';
            this.eGui.rel = 'noopener noreferrer';
            this.eGui.style.color = '#4da6ff';
            this.eGui.style.textDecoration = 'none';
            this.eGui.style.fontWeight = '600';
            this.eGui.innerHTML = 'Abrir post 🔗';
        }
    };
    UrlRenderer.prototype.getGui = function() {
        return this.eGui;
    };
    return UrlRenderer;
})()
""")
    if HAS_AGGRID
    else None
)


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
                <div class="glass-card" style="margin-bottom: 1rem; height: 100%;">
                    <div class="top-post-card">
                        <div class="top-post-icon">{icon}</div>
                        <div class="top-post-info">
                            <div class="top-post-caption" title="{post.caption}">{short_text}</div>
                            <div class="top-post-stats">
                                👁️ {reach:,} <span style="margin: 0 4px;">•</span> ❤️ {likes:,}
                            </div>
                            <div class="top-post-link-wrapper">
                                <a href="{post.permalink}" target="_blank" class="top-post-link">Ver no Instagram ↗</a>
                            </div>
                        </div>
                    </div>
                </div>
                """.replace(",", "."), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

def _ms_to_hhmmss(ms: float) -> str:
    """
    Converte milissegundos em string HH:MM:SS com zero-padding.
    Zero-padding garante que a ordenacao alfabetica coincide com a numerica:
    '00:09:03' < '00:45:01' < '06:29:00' - correto em ambas as ordens.
    """
    if not ms or ms <= 0:
        return "00:00:00"
    total_s = int(ms / 1000)
    hours = total_s // 3600
    minutes = (total_s % 3600) // 60
    seconds = total_s % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _render_aggrid_table(
    df: pd.DataFrame, numeric_cols: list[str], link_col: str = "Visualizar no IG"
) -> None:
    """Funcao auxiliar para configurar e renderizar o AgGrid com estilo e ordenacao."""
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, sortable=True, filter=True)

    # Aplica formatador pt-BR com ponto para colunas numericas
    for col in numeric_cols:
        if col in df.columns:
            gb.configure_column(
                col, type=["numericColumn"], valueFormatter=NUMBER_FORMATTER
            )

    # Aplica renderizador de Link
    if link_col in df.columns:
        gb.configure_column(link_col, cellRenderer=LINK_RENDERER, width=130)

    grid_options = gb.build()

    AgGrid(
        df,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        theme="balham-dark",
        fit_columns_on_grid_load=True,
        height=350,
    )


def render_posts_table(
    media_list: list[InstagramMedia], stories_list: list[InstagramStory] | None = None
) -> None:
    """
    Renderiza a tabela de publicacoes.
    - Se streamlit-aggrid instalado: Usa AgGrid com formatacao de milhar em pt-BR (ponto) e ordenacao numerica.
    - Fallback: st.dataframe nativo.
    """
    if stories_list is None:
        stories_list = []

    st.markdown("### Análise Individual por Publicação")

    view_col, format_col = st.columns([1, 1])

    with view_col:
        st.markdown("<h4 style='color: #9c9ca3; font-size: 0.9rem; margin-bottom: 10px; font-weight: 500;'>Visão de Dados:</h4>", unsafe_allow_html=True)
        data_view = option_menu(
            menu_title=None,
            options=["Total (Mix)", "Apenas Orgânico", "Apenas Pago (Ads)"],
            icons=["pie-chart-fill", "hash", "cash-coin"],
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#9c9ca3", "font-size": "14px"},
                "nav-link": {
                    "font-size": "13px",
                    "text-align": "center",
                    "margin": "0px 6px 0px 0px",
                    "--hover-color": "rgba(30, 30, 36, 0.85)",
                    "border-radius": "0.5rem",
                    "padding": "8px 12px",
                    "border": "1px solid transparent",
                    "color": "#9c9ca3",
                    "font-family": "Inter, sans-serif",
                    "font-weight": "600",
                    "transition": "all 0.2s ease",
                },
                "nav-link-selected": {
                    "background": "rgba(24, 24, 28, 0.7)",
                    "border": "1px solid rgba(255, 179, 0, 0.25)",
                    "box-shadow": "0px 4px 24px rgba(255, 179, 0, 0.12)",
                    "color": "#ffb300",
                    "font-weight": "700"
                },
            }
        )

    with format_col:
        media_type_filter = st.selectbox(
            "Filtrar por Formato:",
            ["Reels", "Carrossel", "Post Estático", "Stories (Ativos 24h)"],
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
                "Visualizar no IG": s.permalink,
            }
            for s in stories_list
        ]

        df_stories = pd.DataFrame(data)
        num_cols = ["Alcance", "Avanços", "Voltas", "Saídas", "Respostas"]

        if HAS_AGGRID:
            _render_aggrid_table(df_stories, num_cols)
        else:
            st.dataframe(df_stories, use_container_width=True, hide_index=True)
        return

    # --- Feed / Reels ---
    filtered_media = []
    for m in media_list:
        if (
            media_type_filter == "Reels"
            and m.media_product_type == "REELS"
            or media_type_filter == "Carrossel"
            and m.media_type == "CAROUSEL_ALBUM"
            or (
                media_type_filter == "Post Estático"
                and m.media_type in ["IMAGE", "VIDEO"]
                and m.media_product_type != "REELS"
            )
        ):
            filtered_media.append(m)

    if not filtered_media:
        st.info(f"Nenhum {media_type_filter} encontrado neste período.")
        return

    data = []
    for m in filtered_media:
        short_caption = (
            m.caption[:40].replace("\n", " ") + "..."
            if len(m.caption) > 40
            else m.caption
        )

        if data_view == "Apenas Orgânico":
            likes = int(m.like_count)
            reach = int(m.organic_reach)
            shares = int(m.shares)
            saved = int(m.saved)
        elif data_view == "Apenas Pago (Ads)":
            likes = int(m.paid_likes)
            reach = int(m.paid_reach)
            shares = int(m.paid_shares)
            saved = int(m.paid_saved)
        else:  # Total Mix
            likes = int(m.total_likes)
            reach = int(m.reach)
            shares = int(m.total_shares)
            saved = int(m.total_saved)

        row: dict[str, Any] = {
            "Publicação": short_caption,
            "Likes": likes,
            "Alcance": reach,
            "Shares": shares,
            "Salvos": saved,
        }

        if data_view != "Apenas Pago (Ads)":
            if media_type_filter == "Reels":
                row["Watch Time Total"] = _ms_to_hhmmss(
                    m.ig_reels_video_view_total_time
                )
                row["Retenção Média"] = _ms_to_hhmmss(m.ig_reels_avg_watch_time)
            else:
                row["Seguidores"] = int(m.follows)
                row["Visitas ao Perfil"] = int(m.profile_visits)

        row["Visualizar no IG"] = m.permalink
        data.append(row)

    df = pd.DataFrame(data).fillna(0)
    num_cols = [
        "Likes",
        "Alcance",
        "Shares",
        "Salvos",
        "Seguidores",
        "Visitas ao Perfil",
    ]

    if HAS_AGGRID:
        _render_aggrid_table(df, num_cols)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
