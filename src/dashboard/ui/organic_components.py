import html as html_lib
from dataclasses import dataclass
from typing import Any, List

import pandas as pd
import streamlit as st
from schemas.instagram import InstagramMedia
from ui.components import render_glass_table, render_metric_card


@dataclass(frozen=True)
class OrganicMetricAggregate:
    """A sum plus the number of selected publications that supplied it."""

    total: int | None
    available: int
    selected: int


ORGANIC_METRIC_FIELDS = (
    "total_interactions",
    "like_count",
    "comments_count",
    "organic_views",
)


def _value(media: Any, field: str, default: Any = None) -> Any:
    return getattr(media, field, default)


def _sum_available(media_list: list[Any], field: str) -> OrganicMetricAggregate:
    values = [_value(media, field) for media in media_list]
    available = [value for value in values if value is not None]
    total = sum(int(value) for value in available) if available else None
    return OrganicMetricAggregate(total, len(available), len(media_list))


def aggregate_organic_metrics(
    media_list: list[Any],
) -> dict[str, OrganicMetricAggregate]:
    """Aggregate confirmed publication-level organic fields without inventing zeros."""

    return {
        field: _sum_available(media_list, field) for field in ORGANIC_METRIC_FIELDS
    }


def _format_optional_int(value: Any) -> str:
    if value is None:
        return "N/D"
    return f"{int(value):,}".replace(",", ".")


def _media_type_label(media: Any) -> str:
    if _value(media, "media_product_type", "") == "REELS":
        return "Reels"
    return {
        "VIDEO": "Vídeo",
        "IMAGE": "Imagem",
        "CAROUSEL_ALBUM": "Carrossel",
        "REELS": "Reels",
    }.get(_value(media, "media_type", ""), _value(media, "media_type", "") or "N/D")


def _format_timestamp(value: Any) -> Any:
    if not value or not isinstance(value, str):
        return value
    return value.replace("+0000", "").replace(".000Z", "").replace("T", " ")

def format_hhmmss(ms_val: float) -> str:
    """Formata milissegundos em HH:MM:SS"""
    if not ms_val:
        return "0s"
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
    """Render the four confirmed organic Media Insights aggregates."""
    st.markdown("### 📊 Desempenho orgânico das publicações")
    totals = aggregate_organic_metrics(list(media_list))
    cards = (
        ("Interações orgânicas", "total_interactions"),
        ("Curtidas orgânicas", "like_count"),
        ("Comentários orgânicos", "comments_count"),
        ("Visualizações orgânicas", "organic_views"),
    )

    cols = st.columns(4)
    for column, (label, field) in zip(cols, cards):
        aggregate = totals[field]
        if aggregate.available == 0:
            coverage = "Sem dados nos Media Insights"
        elif aggregate.available < aggregate.selected:
            coverage = (
                f"Cobertura: {aggregate.available} de {aggregate.selected} publicações"
            )
        else:
            coverage = f"Cobertura: {aggregate.selected} de {aggregate.selected} publicações"
        with column:
            render_metric_card(
                label,
                _format_optional_int(aggregate.total),
                coverage,
                "Soma dos resultados orgânicos disponíveis por publicação",
            )

    st.caption(
        "Resultados acumulados das publicações selecionadas pela data de publicação; "
        "não representam apenas interações ocorridas dentro do período filtrado."
    )


ORGANIC_POST_COLUMNS = [
    "Data e Hora",
    "Tipo",
    "Interações orgânicas",
    "Curtidas orgânicas",
    "Comentários orgânicos",
    "Visualizações orgânicas",
    "Link",
]


def _organic_post_rows(media_list: list[Any], selected_type: str) -> list[dict[str, Any]]:
    rows = []
    for media in media_list:
        media_type = _media_type_label(media)
        if selected_type != "Todos" and media_type != selected_type:
            continue
        rows.append(
            {
                "Data e Hora": _format_timestamp(_value(media, "timestamp")),
                "Tipo": media_type,
                "Interações orgânicas": _value(media, "total_interactions"),
                "Curtidas orgânicas": _value(media, "like_count"),
                "Comentários orgânicos": _value(media, "comments_count"),
                "Visualizações orgânicas": _value(media, "organic_views"),
                "Link": _value(media, "permalink", ""),
            }
        )
    return rows


def render_posts_table(
    media_list: List[InstagramMedia], stories_list: List[Any] | None = None
) -> None:
    """Render the primary publication table with confirmed organic fields only."""
    del stories_list  # Kept for compatibility with existing callers.
    st.markdown("### 📝 Publicações orgânicas")

    filter_column, _ = st.columns([1, 3])
    with filter_column:
        selected_type = st.selectbox(
            "Filtrar por formato",
            options=["Todos", "Imagem", "Vídeo", "Carrossel", "Reels"],
        )

    if not media_list:
        st.info("Nenhuma publicação encontrada no período.")
        return

    filtered_media = [
        media
        for media in media_list
        if selected_type == "Todos" or _media_type_label(media) == selected_type
    ]
    dataframe = pd.DataFrame(
        _organic_post_rows(filtered_media, "Todos"), columns=ORGANIC_POST_COLUMNS
    )
    if dataframe.empty:
        st.info("Nenhuma publicação corresponde ao filtro selecionado.")
        return

    st.download_button(
        label="⬇ Baixar CSV orgânico",
        data=dataframe.to_csv(index=False).encode("utf-8-sig"),
        file_name="publicacoes_organicas.csv",
        mime="text/csv",
    )
    render_glass_table(
        dataframe,
        key="tbl_posts_org",
        hide_download=True,
        link_col="Link",
        link_label="Ver no Instagram",
    )

    neutral_fields = ("reach", "saved", "shares")
    if any(
        _value(media, field) is not None
        for media in filtered_media
        for field in neutral_fields
    ):
        detail_rows = [
            {
                "Data e Hora": _format_timestamp(_value(media, "timestamp")),
                "Tipo": _media_type_label(media),
                "Alcance (Media Insights)": _value(media, "reach"),
                "Salvamentos (Media Insights)": _value(media, "saved"),
                "Compartilhamentos (Media Insights)": _value(media, "shares"),
                "Link": _value(media, "permalink", ""),
            }
            for media in filtered_media
        ]
        with st.expander("Outros detalhes do Media Insights", expanded=False):
            st.caption(
                "Métricas informativas por publicação. A fonte não garante que sejam "
                "exclusivamente orgânicas, por isso elas não entram nos totais acima."
            )
            render_glass_table(
                pd.DataFrame(detail_rows),
                key="tbl_posts_media_insights_details",
                hide_download=True,
                link_col="Link",
                link_label="Ver no Instagram",
            )


def _has_paid_mapping(media: Any) -> bool:
    fields = (
        "paid_ad_count",
        "paid_reach",
        "paid_impressions",
        "paid_views",
        "paid_likes",
        "paid_reactions",
        "paid_comments",
        "paid_shares",
        "paid_saved",
        "paid_spend",
    )
    return any((_value(media, field, 0) or 0) > 0 for field in fields)


def render_paid_comparison(media_list: List[InstagramMedia]) -> None:
    """Render a secondary per-publication comparison for posts mapped to Ads."""
    st.markdown("#### Comparação secundária com Ads")
    st.info(
        "Orgânico e Ads têm escopos e períodos de atribuição diferentes; "
        "compare as colunas sem somá-las. Reproduções pagas contam ações de vídeo "
        "de 3 segundos e não equivalem às visualizações orgânicas. "
        "Curtidas líquidas e reações pagas são eventos distintos, exibidos separadamente."
    )

    rows = []
    for media in media_list:
        if not _has_paid_mapping(media):
            continue
        rows.append(
            {
                "Data e Hora": _format_timestamp(_value(media, "timestamp")),
                "Tipo": _media_type_label(media),
                "Interações orgânicas": _value(media, "total_interactions"),
                "Curtidas orgânicas": _value(media, "like_count"),
                "Curtidas líquidas pagas (Ads)": _value(media, "paid_likes"),
                "Reações pagas (Ads)": _value(media, "paid_reactions"),
                "Comentários orgânicos": _value(media, "comments_count"),
                "Comentários pagos (Ads)": _value(media, "paid_comments"),
                "Visualizações orgânicas (Media Insights)": _value(
                    media, "organic_views"
                ),
                "Reproduções pagas de 3 s (Ads)": _value(media, "paid_views"),
                "Soma do alcance pago por publicação": _value(media, "paid_reach"),
                "Impressões pagas": _value(media, "paid_impressions"),
                "Investimento (R$)": _value(media, "paid_spend"),
                "Anúncios mapeados": _value(media, "paid_ad_count"),
                "Link": _value(media, "permalink", ""),
            }
        )

    if not rows:
        st.info("Nenhuma publicação selecionada foi mapeada a anúncios.")
        return

    render_glass_table(
        pd.DataFrame(rows),
        key="tbl_posts_paid_comparison",
        currency_cols=["Investimento (R$)"],
        hide_download=True,
        link_col="Link",
        link_label="Ver no Instagram",
    )

def render_top_posts_and_comments(media_list: List[InstagramMedia]) -> None:
    """Render the posts with most confirmed organic interactions."""
    st.markdown("### 🏆 Top posts por interações orgânicas")

    if not media_list:
        return

    ranked_media = [
        media for media in media_list if _value(media, "total_interactions") is not None
    ]
    if not ranked_media:
        st.info("Ranking indisponível: as publicações não têm interações orgânicas informadas.")
        return
    sorted_media = sorted(
        ranked_media,
        key=lambda item: (
            _value(item, "total_interactions") is not None,
            _value(item, "total_interactions") or 0,
        ),
        reverse=True,
    )
    top_posts = sorted_media[:3]
    cols = st.columns(len(top_posts))

    for column, media in zip(cols, top_posts):
        with column:
            thumbnail = _value(media, "thumbnail_url") or _value(media, "media_url") or ""
            media_url = _value(media, "media_url") or ""
            permalink = _value(media, "permalink", "") or ""
            media_type = _value(media, "media_type", "")
            is_video = media_type in ("VIDEO", "REELS") or media_url.split("?")[
                0
            ].lower().endswith(".mp4")

            safe_thumbnail = html_lib.escape(thumbnail, quote=True)
            safe_permalink = html_lib.escape(permalink, quote=True)
            image_open = (
                f'<a href="{safe_permalink}" target="_blank" '
                'style="display:block;position:relative;">'
                if permalink
                else '<div style="position:relative;">'
            )
            image_close = "</a>" if permalink else "</div>"
            play_badge = (
                '<div style="position:absolute;top:8px;right:10px;'
                'background:rgba(0,0,0,0.6);color:white;border-radius:20px;'
                'padding:2px 10px;font-size:0.75rem;font-weight:600;">'
                "&#9654; Vídeo</div>"
                if is_video
                else ""
            )
            if safe_thumbnail:
                preview = (
                    f"{image_open}<img src=\"{safe_thumbnail}\" "
                    'style="width:100%;height:200px;object-fit:cover;border-radius:8px;'
                    f'margin-bottom:15px;background:#1a1a1a;">{play_badge}{image_close}'
                )
            else:
                preview = (
                    '<div style="height:200px;display:flex;align-items:center;'
                    'justify-content:center;background:#1a1a1a;border-radius:8px;'
                    'margin-bottom:15px;color:#c4c9ac;">Sem prévia</div>'
                )

            interactions = _format_optional_int(_value(media, "total_interactions"))
            likes = _format_optional_int(_value(media, "like_count"))
            comments = _format_optional_int(_value(media, "comments_count"))
            views = _format_optional_int(_value(media, "organic_views"))
            post_link = (
                f'<a href="{safe_permalink}" target="_blank" class="glass-link">'
                "Ver no Instagram</a>"
                if permalink
                else ""
            )

            html = f"""<div class="glass-card" style="padding:15px;text-align:center;height:100%;">
    {preview}
    <div style="color:#FFB300;font-size:1.2rem;font-weight:bold;margin-bottom:12px;">
        {interactions} interações orgânicas
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:15px;padding:10px;background:rgba(255,255,255,0.03);border-radius:8px;">
        <div><strong>{likes}</strong><br><span style="font-size:0.7rem;color:#c4c9ac;">Curtidas orgânicas</span></div>
        <div><strong>{comments}</strong><br><span style="font-size:0.7rem;color:#c4c9ac;">Comentários orgânicos</span></div>
        <div><strong>{views}</strong><br><span style="font-size:0.7rem;color:#c4c9ac;">Visualizações orgânicas</span></div>
    </div>
    {post_link}
</div>"""
            st.markdown(html, unsafe_allow_html=True)

def render_historic_top_comment(client_name: str) -> None:
    """Renderiza o comentário mais curtido entre os consultados e permite exportá-los."""
    try:
        from ui.data_loader import fetch_all_historic_comments
        import pandas as pd
        all_comments = fetch_all_historic_comments(client_name)
        
        if not all_comments:
            return
            
        best = max(all_comments, key=lambda c: int(c.get("like_count", 0)), default=None)
        if not best:
            return
            
        st.markdown("### 💬 Comentário com mais curtidas entre os consultados")
        
        text = html_lib.escape(str(best.get("text", "")))
        username = html_lib.escape(str(best.get("username", "Usuário")))
        likes = best.get("like_count", 0)
        
        html = f"""<div class="glass-card" style="padding: 20px; border-left: 4px solid #FFB300; background: rgba(255,179,0,0.05); border-radius: 8px; margin-bottom: 20px;">
    <div style="font-size: 1.1rem; color: #E2E8F0; margin-bottom: 8px; font-style: italic;">"{text}"</div>
    <div style="color: #c4c9ac; font-size: 0.9rem;">
        <strong>@{username}</strong> • 🏆 {int(likes):,} curtidas
    </div>
</div>"""
        st.markdown(html, unsafe_allow_html=True)
        
        st.write("")
        df_comments = pd.DataFrame(all_comments)
        
        # Formatar Data e Hora para o CSV de comentários
        if "timestamp" in df_comments.columns:
            df_comments["Data e Hora"] = df_comments["timestamp"].str.replace("+0000", "", regex=False).str.replace(".000Z", "", regex=False).str.replace("T", " ", regex=False)
            df_comments = df_comments.drop(columns=["timestamp"])
            
        csv = df_comments.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar comentários consultados (CSV)",
            data=csv,
            file_name=f"comentarios_consultados_{client_name}.csv",
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
