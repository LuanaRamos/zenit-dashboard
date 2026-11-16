"""Laboratório de Criativos — renderiza anúncios com métricas, público REAL atraído e agendamento."""

from __future__ import annotations

import plotly.express as px
import streamlit as st
import sentry_sdk
import pandas as pd
from html import escape as escape_html
from ui.iconography import lucide_icon


@st.cache_data(ttl=3600)
def fetch_creatives(
    date_preset: str, time_range: dict | None, client_name: str
) -> list[dict]:
    """
    Busca performance + público REAL entregue por anúncio.
    Consolida métricas de todos os posicionamentos, público efetivamente
    alcançado e comparativo por plataforma, sem somar duas vezes os anúncios.
    """
    from ui.data_loader import get_api_client

    client = get_api_client(client_name)

    creatives = client.get_creative_performance(date_preset, time_range)
    real_audience = client.get_creative_real_audience(date_preset, time_range)
    try:
        platform_breakdown = client.get_creative_platform_breakdown(date_preset, time_range)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Comparação por plataforma indisponível: %s", exc
        )
        platform_breakdown = {}

    results = []
    for d in creatives:
        dump = d.model_dump()
        dump["objective_friendly"] = d.objective_friendly
        # Injetar audiência real (quem foi atraído pelo criativo)
        aud = real_audience.get(d.ad_id, {})
        dump["real_age_gender"] = aud.get("age_gender", {})
        dump["real_regions"] = aud.get("regions", {})
        dump["real_countries"] = aud.get("countries", {})
        dump["platform_breakdown"] = platform_breakdown.get(d.ad_id, [])
        results.append(dump)

    return results


def _fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _parse_dt(dt_str: str | None) -> str:
    """Converte ISO datetime do Meta API para formato legível."""
    if not dt_str:
        return "—"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return dt_str[:16] if dt_str else "—"


def _status_badge(status: str) -> str:
    """Etiqueta retangular discreta, sem bolinhas ou caracteres decorativos."""
    colors = {
        "ACTIVE": ("#9edbb3", "rgba(24, 120, 77, 0.14)", "Ativo"),
        "PAUSED": ("#ffd56c", "rgba(255, 179, 0, 0.10)", "Pausado"),
        "DELETED": ("#ffadad", "rgba(205, 58, 58, 0.14)", "Excluído"),
        "ARCHIVED": ("#b9c1cd", "rgba(119, 136, 160, 0.13)", "Arquivado"),
    }
    color, bg, label = colors.get(
        status.upper(), ("#b9c1cd", "rgba(119,136,160,.12)", status)
    )
    return (
        f'<span style="background:{bg};color:{color};padding:5px 9px;'
        f'border:1px solid rgba(255,255,255,.08);border-radius:6px;'
        f'font-size:0.75rem;font-weight:650;">{escape_html(label)}</span>'
    )


_GENDER_PT = {"male": "Masculino", "female": "Feminino", "unknown": "Indefinido"}
_AGE_ORDER = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
_COLORS = {"Masculino": "#FFB300", "Feminino": "#FFD56C", "Indefinido": "#78869B"}


def _render_real_audience(ad: dict) -> None:
    """Renderiza o público real que foi atraído pelo criativo."""
    age_gender: dict = ad.get("real_age_gender", {})
    regions: dict = ad.get("real_regions", {})
    countries: dict = ad.get("real_countries", {})

    if not age_gender and not regions and not countries:
        st.caption("Sem dados demográficos de entrega para este anúncio.")
        return

    st.markdown(
        "<div style='background:rgba(255,179,0,0.045);border-left:2px solid #FFB300;"
        "border-radius:0 7px 7px 0;padding:8px 12px;margin-bottom:10px;'>"
        f"<span style='color:#FFD56C;display:inline-flex;align-items:center;gap:8px;"
        f"font-weight:650;font-size:0.83rem;'>{lucide_icon('users', 15)} Público alcançado</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Gráfico Idade × Gênero ───────────────────────────────────────────────
    if age_gender:
        rows = []
        for key, val in age_gender.items():
            if " (" in key and ")" in key:
                age = key.split(" (")[0].strip()
                gender_raw = key.split(" (")[1].replace(")", "").strip()
                gender = _GENDER_PT.get(gender_raw, gender_raw)
                rows.append({"Faixa": age, "Gênero": gender, "Impressões": val})

        if rows:
            df = pd.DataFrame(rows)

            n_age_groups = df["Faixa"].nunique()
            n_genders = df["Gênero"].nunique()

            # Dynamic height calculation standardized
            per_item = 28
            if n_genders > 1:
                per_item = int(28 * 1.6)
            chart_height = max(200, n_age_groups * per_item + 120)

            fig = px.bar(
                df,
                x="Impressões",
                y="Faixa",
                color="Gênero",
                barmode="group",
                orientation="h",
                category_orders={"Faixa": _AGE_ORDER},
                color_discrete_map=_COLORS,
                title="Impressões por Idade & Gênero",
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E2E8F0", size=11),
                xaxis=dict(
                    showgrid=True,
                    gridcolor="rgba(255,255,255,0.07)",
                    showticklabels=False,
                    title_text="",
                ),
                yaxis=dict(
                    showgrid=False,
                    tickfont=dict(color="#F1F5F9", size=11),
                    title_text="",
                    automargin=True,
                ),
                margin=dict(l=60, r=10, t=40, b=50),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.05,
                    xanchor="center",
                    x=0.5,
                    title_text="",
                    font=dict(size=11, color="#F1F5F9"),
                    itemwidth=40,
                ),
                hoverlabel=dict(
                    bgcolor="rgba(15, 23, 42, 0.95)",
                    bordercolor="rgba(255,255,255,0.2)",
                    font=dict(color="#FFFFFF", size=11, family="Inter"),
                ),
                height=chart_height,
                title_font=dict(size=12, color="#94A3B8"),
            )
            # iframe obrigatorio aqui: chart esta dentro de st.columns aninhadas
            import streamlit.components.v1 as st_components

            plotly_html = fig.to_html(
                full_html=False,
                include_plotlyjs="cdn",
                config={"displayModeBar": False},
            )
            iframe_html = (
                "<html><head>"
                "<style>html,body{margin:0;padding:0;overflow:hidden;background:transparent;}</style>"
                "</head>"
                f"<body>{plotly_html}</body></html>"
            )
            st_components.html(iframe_html, height=chart_height + 10, scrolling=False)

    # ── Regiões + Países ─────────────────────────────────────────────────────
    if regions or countries:
        c1, c2 = st.columns(2)
        with c1:
            if regions:
                _render_mini_bars(regions, "Top regiões", "#FFB300")
        with c2:
            if countries:
                _render_mini_bars(countries, "Top países", "#C48A24")


def _render_mini_bars(data: dict, title: str, color: str, max_items: int = 6) -> None:
    """Gráfico de barras compacto via iframe — evita clipping de labels dentro de colunas."""
    import streamlit.components.v1 as st_components
    import plotly.graph_objects as go

    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_items]
    if not sorted_items:
        return

    names = [x[0] for x in sorted_items]
    values = [x[1] for x in sorted_items]
    right_margin = max(65, max(len(f"{v:,}") for v in values) * 9)
    chart_height = max(160, len(sorted_items) * 28 + 50)

    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker_color=color,
            text=[_fmt_int(v) for v in values],
            textposition="outside",
            textfont=dict(color="#FFFFFF", size=10, family="Inter"),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:,}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(color="#94A3B8", size=11), x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0", size=10),
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            range=[0, max(values) * 1.4] if values else [0, 1],
        ),
        yaxis=dict(
            showgrid=False,
            autorange="reversed",
            tickfont=dict(size=10, color="#F1F5F9"),
            automargin=True,
        ),
        margin=dict(l=40, r=right_margin, t=28, b=10),
        height=chart_height,
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.95)",
            bordercolor="rgba(255,255,255,0.2)",
            font=dict(color="#FFFFFF", size=11, family="Inter"),
        ),
    )

    plotly_html = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": False},
    )
    iframe_html = (
        "<html><head>"
        "<style>html,body{margin:0;padding:0;overflow:hidden;background:transparent;}</style>"
        "</head>"
        f"<body>{plotly_html}</body></html>"
    )
    st_components.html(iframe_html, height=chart_height + 10, scrolling=False)


def render_creatives_tab(
    date_preset: str, time_range: dict | None, client_name: str
) -> None:
    """Renderiza o Laboratório de Criativos com público real atraído e datas de veiculação."""
    st.subheader("Laboratório de criativos")
    st.markdown(
        "<p style='color:#94A3B8;margin-bottom:8px;'>"
        "Analise quais criativos performam melhor e quem eles estão atraindo de verdade "
        "(baseado na entrega real da Meta, não no targeting configurado)."
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.3);"
        "border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:0.82rem;color:#A5B4FC;'>"
        "&#9888; <b>Advantage+ / IA da Meta:</b> Os dados de Público Atraído mostram quem "
        "<i>realmente</i> foi impactado pelo anúncio — independente de qualquer configuração manual de audiência."
        "</div>",
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("Analisando criativos e audiência real..."):
            data = fetch_creatives(date_preset, time_range, client_name)

        if not data:
            st.warning("Sem dados de criativos no período selecionado.")
            return

        st.caption(
            "Resultados consolidados de todos os posicionamentos da conta Meta Ads. "
            "O comparativo por plataforma é exibido separadamente e não é somado ao total."
        )
        platforms = sorted({
            entry["platform"]
            for ad in data for entry in ad.get("platform_breakdown", [])
        })
        selected_platform = st.selectbox(
            "Comparar posicionamentos",
            options=["Todos os posicionamentos", *platforms],
            key=f"creative_platform_{client_name}",
        )
        if selected_platform != "Todos os posicionamentos":
            # Nunca recalcular o total do anúncio com métricas do Instagram apenas.
            # O filtro seleciona os anúncios com entrega nesta plataforma; o
            # cartão explicita a visão agregada e detalha o placement abaixo.
            data = [
                ad for ad in data
                if any(p["platform"] == selected_platform
                       for p in ad.get("platform_breakdown", []))
            ]
        st.caption(
            f"{len(data)} criativos encontrados. O filtro de plataforma seleciona "
            "quais anúncios aparecem; os cartões sempre mostram o total de todas as plataformas."
        )
        page_size = st.selectbox(
            "Quantos criativos exibir?",
            options=[10, 25, 50, "Todos"],
            index=1,
            key=f"creative_limit_{client_name}",
        )
        top_ads = data if page_size == "Todos" else data[:int(page_size)]

        for i in range(0, len(top_ads), 2):
            cols = st.columns(2, gap="medium")
            for j, col in enumerate(cols):
                if i + j >= len(top_ads):
                    break
                with col:
                    try:
                        _render_creative_card(top_ads[i + j])
                    except Exception as card_err:
                        sentry_sdk.capture_exception(card_err)
                        st.warning("Erro ao carregar este criativo.")

    except Exception as e:
        sentry_sdk.capture_exception(e)
        st.error(
            "Ocorreu um erro ao carregar os criativos. "
            "Nossa equipe já foi notificada e está trabalhando nisso."
        )


def _render_creative_card(ad: dict) -> None:
    """Renderiza card completo: criativo + métricas + público real + agendamento."""
    ad_name = ad.get("ad_name", "—")
    image_url = ad.get("image_url") or ad.get("thumbnail_url")
    ad_status = ad.get("ad_status", "")

    # ── Título + Status ──────────────────────────────────────────────────────
    status_html = _status_badge(ad_status) if ad_status else ""
    st.markdown(
        f"<div style='margin-bottom:6px;'>"
        f"<span style='font-weight:700;font-size:0.95rem;color:#F1F5F9;'>{escape_html(str(ad_name))}</span>"
        f"&nbsp;&nbsp;{status_html}</div>",
        unsafe_allow_html=True,
    )

    # ── Criativo ─────────────────────────────────────────────────────────────
    if image_url:
        st.image(image_url, use_container_width=True)
    else:
        st.markdown(
            "<div style='height:140px;background:rgba(255,255,255,0.04);"
            "border-radius:10px;display:flex;align-items:center;justify-content:center;"
            "color:#64748B;font-size:0.85rem;'>Imagem indisponível</div>",
            unsafe_allow_html=True,
        )

    # ── Métricas de Performance ───────────────────────────────────────────────
    gasto = ad.get("spend", 0.0)
    leads = int(ad.get("leads", 0))
    wpp = int(ad.get("whatsapp_starts", 0))
    instagram_follows = int(ad.get("instagram_follows", 0))
    profile_visits = int(ad.get("profile_visits", 0))
    impressions = int(ad.get("impressions", 0))
    clicks = int(ad.get("clicks", 0))
    link_clicks = int(ad.get("link_clicks", 0))
    outbound_clicks = int(ad.get("outbound_clicks", 0))

    objective_friendly = ad.get("objective_friendly", "Desconhecido")
    traffic_dest = ad.get("traffic_destination", "Não Identificado")

    st.markdown(
        f"<div style='margin-bottom: 8px; font-size: 0.85rem; color: #c4c9ac;'>"
        f"{lucide_icon('target', 15)} Objetivo: <span style='color: #F1F5F9;'>{escape_html(str(objective_friendly))}</span><br>"
        f"{lucide_icon('link', 15)} Destino: <span style='color: #F1F5F9;'>{escape_html(str(traffic_dest))}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Visitas ao perfil não são subtraídas dos cliques de anúncios.
    outros_cliques = int(ad.get("other_clicks", max(0, clicks - link_clicks)))

    c1, c2, c3 = st.columns(3)

    # Linha 1
    c1.metric("Investimento", _fmt_brl(gasto))
    c2.metric("Impressões", _fmt_int(impressions))

    if objective_friendly == "Mensagens" or wpp > 0:
        c3.metric("Conversas iniciadas", _fmt_int(wpp))
        # Linha 2
        c1.metric("Custo por conversa", _fmt_brl(gasto / wpp) if wpp > 0 else "N/D")
        if instagram_follows > 0:
            c2.metric("Seguidores", _fmt_int(instagram_follows))
            c3.metric("Custo por seguidor", _fmt_brl(gasto / instagram_follows))
    elif objective_friendly in ["Tráfego", "Reconhecimento"]:
        cpc_link = gasto / link_clicks if link_clicks > 0 else 0.0
        ctr_link = (link_clicks / impressions * 100) if impressions > 0 else 0.0
        c3.metric("CPC do link", _fmt_brl(cpc_link) if cpc_link > 0 else "—")
        # Linha 2
        c1.metric("CTR do link", f"{ctr_link:.2f}%" if ctr_link > 0 else "—")
        if instagram_follows > 0:
            c2.metric("Seguidores", _fmt_int(instagram_follows))
            c3.metric("Custo por seguidor", _fmt_brl(gasto / instagram_follows))
    else:
        c3.metric("Leads", _fmt_int(leads))
        # Linha 2
        c1.metric("Custo por lead", _fmt_brl(gasto / leads) if leads > 0 else "N/D")
        if instagram_follows > 0:
            c2.metric("Seguidores", _fmt_int(instagram_follows))
            c3.metric("Custo por seguidor", _fmt_brl(gasto / instagram_follows))

    # Linha 3 (Os 3 tipos de cliques separados, sem somar)
    c1.metric("Cliques no link", _fmt_int(link_clicks))
    c1.metric("Cliques de saída", _fmt_int(outbound_clicks))
    c2.metric("Visitas ao perfil", _fmt_int(profile_visits))

    with c3:
        st.metric(
            "Outros cliques",
            _fmt_int(outros_cliques),
            help="Diferença entre cliques totais e cliques no link; não inclui uma soma de interações.",
        )
        if outros_cliques > 0:
            likes = ad.get("post_reactions", 0)
            shares = ad.get("post_shares", 0)
            saves = ad.get("post_saves", 0)
            comments = ad.get("post_comments", 0)

            # HTML para o texto pequeno alinhado ao Metric
            st.markdown(
                f"<div style='font-size:0.75rem; color:#A0AEC0; margin-top:-10px; line-height:1.2;'>"
                f"{f'Curtidas: {likes}<br>' if likes else ''}"
                f"{f'Compartilhamentos: {shares}<br>' if shares else ''}"
                f"{f'Comentários: {comments}<br>' if comments else ''}"
                f"{f'Salvamentos: {saves}<br>' if saves else ''}"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Quebra por plataforma sem misturar com o total agregado ──────────────
    placements = ad.get("platform_breakdown", [])
    if placements:
        with st.expander("Desempenho por plataforma", expanded=False):
            platform_names = {
                "instagram": "Instagram", "facebook": "Facebook",
                "messenger": "Messenger", "audience_network": "Audience Network",
                "threads": "Threads",
            }
            table = []
            for part in placements:
                spend_part = part["spend"]
                messages = part["messaging_conversations"]
                table.append({
                    "Plataforma": platform_names.get(part["platform"], part["platform"]),
                    "Investimento (R$)": spend_part,
                    "Impressões": part["impressions"],
                    "Cliques": part["clicks"],
                    "Conversas": messages,
                    "Custo/conversa (R$)": (
                        round(spend_part / messages, 2) if messages else None
                    ),
                })
            st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
            st.caption(
                "Recorte por plataforma. Os totais do cartão são da consulta "
                "agregada e não devem ser somados novamente."
            )

    # ── Público REAL Atraído ─────────────────────────────────────────────────
    _render_real_audience(ad)

    # ── Agendamento ──────────────────────────────────────────────────────────
    start = _parse_dt(ad.get("start_time"))
    end_raw = ad.get("end_time")
    end = _parse_dt(end_raw) if end_raw else "Sem data de término"
    adset_name = ad.get("adset_name", "")
    adset_status = ad.get("adset_status", "")
    adset_badge = _status_badge(adset_status) if adset_status else ""

    st.markdown(
        f"<div style='background:rgba(255,179,0,0.045);border-left:2px solid #FFB300;"
        f"border-radius:0 8px 8px 0;padding:9px 12px;margin:8px 0;font-size:0.82rem;color:#cbd3df;'>"
        f"<strong style='color:#FFD56C;'>{lucide_icon('calendar', 15)} Veiculação</strong>"
        f"{' — ' + escape_html(str(adset_name)) if adset_name else ''} {adset_badge}<br>"
        f"Início: <b>{start}</b>&nbsp;&nbsp;Fim: <b>{end}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.06);margin:12px 0;'>",
        unsafe_allow_html=True,
    )
