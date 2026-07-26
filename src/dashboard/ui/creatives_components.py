"""Laboratório de Criativos — renderiza anúncios com métricas, público-alvo e agendamento."""
from __future__ import annotations

import streamlit as st
import sentry_sdk


@st.cache_data(ttl=3600)
def fetch_creatives(date_preset: str, time_range: dict | None = None) -> list[dict]:
    """Busca e serializa a performance de criativos (incluindo targeting e datas)."""
    from api.meta_client import MetaAdsClient
    client = MetaAdsClient()
    data = client.get_creative_performance(date_preset, time_range)
    results = []
    for d in data:
        dump = d.model_dump()
        dump["objective_friendly"] = d.objective_friendly
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
        # Meta retorna algo como "2026-07-02T14:13:32-0200"
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return dt_str[:16] if dt_str else "—"


def _status_badge(status: str) -> str:
    """Retorna badge colorida para o status do anúncio."""
    colors = {
        "ACTIVE": ("#16a34a", "#dcfce7", "● Ativo"),
        "PAUSED": ("#d97706", "#fef3c7", "⏸ Pausado"),
        "DELETED": ("#dc2626", "#fee2e2", "✕ Deletado"),
        "ARCHIVED": ("#6b7280", "#f3f4f6", "↓ Arquivado"),
    }
    color, bg, label = colors.get(status.upper(), ("#6b7280", "#f3f4f6", status))
    return (
        f'<span style="background:{bg};color:{color};padding:2px 10px;'
        f'border-radius:20px;font-size:0.75rem;font-weight:700;">{label}</span>'
    )


def _build_audience_text(ad: dict) -> str:
    """Monta string descritiva do público-alvo."""
    parts = []

    age_min = ad.get("age_min")
    age_max = ad.get("age_max")
    if age_min or age_max:
        a_min = str(age_min) if age_min else "?"
        a_max = str(age_max) if age_max else "65+"
        parts.append(f"🎂 {a_min}–{a_max} anos")

    genders = ad.get("genders") or []
    if genders and genders != ["Todos"]:
        parts.append("👤 " + ", ".join(genders))
    else:
        parts.append("👤 Todos os gêneros")

    cities = ad.get("target_cities") or []
    regions = ad.get("target_regions") or []
    countries = ad.get("target_countries") or []

    locs = cities + regions + countries
    if locs:
        parts.append("📍 " + ", ".join(locs[:5]) + ("..." if len(locs) > 5 else ""))

    return "  ·  ".join(parts) if parts else "Público não definido"


def render_creatives_tab(date_preset: str, time_range: dict | None = None) -> None:
    """Renderiza o Laboratório de Criativos com público-alvo e datas de veiculação."""
    st.subheader("🎨 Laboratório de Criativos")
    st.markdown(
        "<p style='color:#94A3B8;margin-bottom:20px;'>"
        "Analise quais criativos performam melhor, para qual público e por quanto tempo rodaram."
        "</p>",
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("Analisando criativos..."):
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
                ad = top_ads[i + j]
                with col:
                    _render_creative_card(ad)

    except Exception as e:
        sentry_sdk.capture_exception(e)
        st.error(
            "Ocorreu um erro ao carregar os criativos. "
            "Nossa equipe já foi notificada e está trabalhando nisso."
        )


def _render_creative_card(ad: dict) -> None:
    """Renderiza o card completo de um criativo."""
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

    # ── Imagem do criativo ───────────────────────────────────────────────────
    if image_url:
        st.image(image_url, use_container_width=True)
    else:
        st.markdown(
            "<div style='height:160px;background:rgba(255,255,255,0.04);"
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

    # ── Público-Alvo ─────────────────────────────────────────────────────────
    audience_text = _build_audience_text(ad)
    st.markdown(
        f"<div style='background:rgba(99,102,241,0.12);border-left:3px solid #6366F1;"
        f"border-radius:0 8px 8px 0;padding:8px 12px;margin:8px 0;font-size:0.82rem;color:#C7D2FE;'>"
        f"<strong style='color:#A5B4FC;'>👥 Público-Alvo</strong><br>{audience_text}</div>",
        unsafe_allow_html=True,
    )

    # ── Agendamento ──────────────────────────────────────────────────────────
    start = _parse_dt(ad.get("start_time"))
    end_raw = ad.get("end_time")
    end = _parse_dt(end_raw) if end_raw else "Sem data de término (em aberto)"

    adset_name = ad.get("adset_name", "")
    adset_status = ad.get("adset_status", "")
    adset_badge = _status_badge(adset_status) if adset_status else ""

    st.markdown(
        f"<div style='background:rgba(16,185,129,0.10);border-left:3px solid #10B981;"
        f"border-radius:0 8px 8px 0;padding:8px 12px;margin:8px 0;font-size:0.82rem;color:#A7F3D0;'>"
        f"<strong style='color:#6EE7B7;'>📅 Veiculação</strong>"
        f"{' — ' + adset_name if adset_name else ''} {adset_badge}<br>"
        f"Início: <b>{start}</b><br>"
        f"Fim: <b>{end}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:rgba(255,255,255,0.06);margin:10px 0;'>", unsafe_allow_html=True)
