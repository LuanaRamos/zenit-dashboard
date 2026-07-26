"""Laboratório de Criativos — renderiza anúncios com métricas, público REAL atraído e agendamento."""
from __future__ import annotations

import plotly.express as px
import streamlit as st
import sentry_sdk
import pandas as pd


@st.cache_data(ttl=3600)
def fetch_creatives(date_preset: str, time_range: dict | None = None) -> list[dict]:
    """
    Busca performance + público REAL entregue por anúncio.
    Usa 2 chamadas paralelas à API:
    1. get_creative_performance → métricas + criativo + datas
    2. get_creative_real_audience → quem de fato viu o anúncio (age/gender/region/country)
    """
    from api.meta_client import MetaAdsClient
    client = MetaAdsClient()

    creatives = client.get_creative_performance(date_preset, time_range)
    real_audience = client.get_creative_real_audience(date_preset, time_range)

    results = []
    for d in creatives:
        dump = d.model_dump()
        dump["objective_friendly"] = d.objective_friendly
        # Injetar audiência real (quem foi atraído pelo criativo)
        aud = real_audience.get(d.ad_id, {})
        dump["real_age_gender"] = aud.get("age_gender", {})
        dump["real_regions"] = aud.get("regions", {})
        dump["real_countries"] = aud.get("countries", {})
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
    colors = {
        "ACTIVE":   ("#16a34a", "#dcfce7", "● Ativo"),
        "PAUSED":   ("#d97706", "#fef3c7", "⏸ Pausado"),
        "DELETED":  ("#dc2626", "#fee2e2", "✕ Deletado"),
        "ARCHIVED": ("#6b7280", "#f3f4f6", "↓ Arquivado"),
    }
    color, bg, label = colors.get(status.upper(), ("#6b7280", "#f3f4f6", status))
    return (
        f'<span style="background:{bg};color:{color};padding:2px 10px;'
        f'border-radius:20px;font-size:0.75rem;font-weight:700;">{label}</span>'
    )


_GENDER_PT = {"male": "Masculino", "female": "Feminino", "unknown": "Indefinido"}
_AGE_ORDER = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
_COLORS = {"Masculino": "#2A85FF", "Feminino": "#FF2A85", "Indefinido": "#8B949E"}


def _render_real_audience(ad: dict) -> None:
    """Renderiza o público real que foi atraído pelo criativo."""
    age_gender: dict = ad.get("real_age_gender", {})
    regions: dict = ad.get("real_regions", {})
    countries: dict = ad.get("real_countries", {})

    if not age_gender and not regions and not countries:
        st.caption("Sem dados demográficos de entrega para este anúncio.")
        return

    st.markdown(
        "<div style='background:rgba(99,102,241,0.10);border-left:3px solid #6366F1;"
        "border-radius:0 8px 8px 0;padding:6px 12px;margin-bottom:8px;'>"
        "<span style='color:#A5B4FC;font-weight:700;font-size:0.82rem;'>👥 Público Atraído pelo Criativo</span>"
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
                font=dict(color="#CBD5E1", size=11),
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)", showticklabels=False),
                yaxis=dict(showgrid=False),
                margin=dict(l=0, r=0, t=30, b=0),
                legend=dict(orientation="h", y=1.12, font=dict(size=10)),
                height=260,
                title_font=dict(size=12, color="#94A3B8"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Regiões + Países ─────────────────────────────────────────────────────
    if regions or countries:
        c1, c2 = st.columns(2)
        with c1:
            if regions:
                _render_mini_bars(regions, "Top Regiões", "#2A85FF")
        with c2:
            if countries:
                _render_mini_bars(countries, "Top Países", "#6366F1")


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

    fig = go.Figure(go.Bar(
        x=values,
        y=names,
        orientation="h",
        marker_color=color,
        text=[_fmt_int(v) for v in values],
        textposition="outside",
        textfont=dict(color="#E2E8F0", size=10),
        cliponaxis=False,
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color="#94A3B8", size=11), x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1", size=10),
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            range=[0, max(values) * 1.4] if values else [0, 1],
        ),
        yaxis=dict(showgrid=False, autorange="reversed", tickfont=dict(size=10)),
        margin=dict(l=0, r=right_margin, t=28, b=0),
        height=chart_height,
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



def render_creatives_tab(date_preset: str, time_range: dict | None = None) -> None:
    """Renderiza o Laboratório de Criativos com público real atraído e datas de veiculação."""
    st.subheader("🎨 Laboratório de Criativos")
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
            data = fetch_creatives(date_preset, time_range)

        if not data:
            st.warning("Sem dados de criativos no período selecionado.")
            return

        top_ads = data[:10]

        for i in range(0, len(top_ads), 2):
            cols = st.columns(2, gap="medium")
            for j, col in enumerate(cols):
                if i + j >= len(top_ads):
                    break
                with col:
                    _render_creative_card(top_ads[i + j])

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
        f"<span style='font-weight:700;font-size:0.95rem;color:#F1F5F9;'>{ad_name}</span>"
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
    cpa = ad.get("cpa", 0.0)
    leads = int(ad.get("leads", 0))
    wpp = int(ad.get("whatsapp_starts", 0))
    impressions = int(ad.get("impressions", 0))
    clicks = int(ad.get("clicks", 0))

    c1, c2 = st.columns(2)
    c1.metric("💸 Gasto", _fmt_brl(gasto))
    c2.metric("🎯 CPA", _fmt_brl(cpa) if cpa > 0 else "—")
    c1.metric("📋 Leads", _fmt_int(leads))
    c2.metric("💬 WhatsApp", _fmt_int(wpp))
    c1.metric("👁 Impressões", _fmt_int(impressions))
    c2.metric("🖱 Cliques", _fmt_int(clicks))

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
        f"<div style='background:rgba(16,185,129,0.10);border-left:3px solid #10B981;"
        f"border-radius:0 8px 8px 0;padding:8px 12px;margin:8px 0;font-size:0.82rem;color:#A7F3D0;'>"
        f"<strong style='color:#6EE7B7;'>📅 Veiculação</strong>"
        f"{' — ' + adset_name if adset_name else ''} {adset_badge}<br>"
        f"Início: <b>{start}</b>&nbsp;&nbsp;Fim: <b>{end}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.06);margin:12px 0;'>",
        unsafe_allow_html=True,
    )
