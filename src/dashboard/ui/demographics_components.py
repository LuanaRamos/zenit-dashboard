"""Componentes de visualização demográfica para Orgânico (Instagram) e Pago (Meta Ads)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.express as px
import streamlit as st
import pandas as pd
from schemas.instagram import AccountDemographics, InstagramDemographics

if TYPE_CHECKING:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# Helpers de renderização reutilizáveis
# ─────────────────────────────────────────────────────────────────────────────

_GENDER_MAP = {"M": "Masculino", "F": "Feminino", "U": "Indefinido",
               "male": "Masculino", "female": "Feminino", "unknown": "Indefinido"}

_AGE_ORDER = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]

_COLOR_GENDER = {
    "Masculino": "#2A85FF",
    "Feminino":  "#FF2A85",
    "Indefinido": "#8B949E",
}


def _normalize_age_gender(raw: dict[str, int]) -> list[dict]:
    """Normaliza as chaves '25-34 (M)' ou '25-34 (male)' para formato padronizado."""
    rows = []
    for key, value in raw.items():
        # Suporta '25-34 (M)', '25-34 (male)', '25-34 (F)', etc.
        if " (" in key and ")" in key:
            age = key.split(" (")[0].strip()
            gender_raw = key.split(" (")[1].replace(")", "").strip()
            gender = _GENDER_MAP.get(gender_raw, gender_raw)
            rows.append({"Faixa Etária": age, "Gênero": gender, "Pessoas": value})
    return rows


def render_age_gender_chart(demo: InstagramDemographics, title: str) -> None:
    """Gráfico de barras horizontais com pirâmide de Idade × Gênero."""
    parsed = _normalize_age_gender(demo.age_gender)
    if not parsed:
        st.info("Sem dados de Idade/Gênero disponíveis.")
        return

    df = pd.DataFrame(parsed)

    fig = px.bar(
        df,
        x="Pessoas",
        y="Faixa Etária",
        color="Gênero",
        barmode="group",
        category_orders={"Faixa Etária": _AGE_ORDER},
        color_discrete_map=_COLOR_GENDER,
        orientation="h",
        title=f"Idade & Gênero — {title}",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0", size=13),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", tickfont=dict(size=12)),
        yaxis=dict(showgrid=False, tickfont=dict(size=13)),
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_top_locations(
    data: dict[str, int],
    title: str,
    color: str = "#2A85FF",
    max_items: int = 15,
) -> None:
    """Renderiza barras de localização via Plotly (evita bug de HTML cru em colunas no Streamlit Cloud)."""
    if not data:
        st.info(f"Sem dados de {title.lower()} disponíveis.")
        return

    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_items]
    names = [x[0] for x in sorted_items]
    values = [x[1] for x in sorted_items]

    import plotly.graph_objects as go
    fig = go.Figure(go.Bar(
        x=values,
        y=names,
        orientation="h",
        marker_color=color,
        text=[f"{v:,}".replace(",", ".") for v in values],
        textposition="outside",
        textfont=dict(color="#E2E8F0", size=12),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color="#F8FAFC", size=14), x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1", size=12),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)", showticklabels=False),
        yaxis=dict(showgrid=False, autorange="reversed", tickfont=dict(size=12)),
        margin=dict(l=0, r=60, t=36, b=0),
        height=max(220, len(sorted_items) * 28 + 60),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_full_demo_section(demo: InstagramDemographics, label: str) -> None:
    """Renderiza Idade/Gênero + Cidades + Países para uma audiência."""
    if not demo.age_gender and not demo.cities and not demo.countries:
        st.warning(
            f"Sem dados suficientes para **{label}**. "
            "Isso pode ocorrer em contas novas, com poucas interações, "
            "ou quando os dados ainda estão sendo processados pela Meta (delay de até 48h)."
        )
        return

    render_age_gender_chart(demo, label)

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        render_top_locations(
            demo.cities,
            f"Top Cidades — {label}",
            color="#2A85FF",
        )
    with col2:
        render_top_locations(
            demo.countries,
            f"Top Países — {label}",
            color="#6366F1",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Aba Orgânico — Instagram
# ─────────────────────────────────────────────────────────────────────────────

def render_demographics_dashboard(demo: AccountDemographics) -> None:
    """Renderiza a aba completa de Dados Demográficos para o Instagram Orgânico."""
    st.markdown("### Perfil da Audiência (Orgânico — Instagram)")
    st.markdown(
        "<p style='color:#94A3B8;margin-bottom:8px;'>"
        "Quem são as pessoas que te seguem, interagem e são alcançadas pelo seu conteúdo."
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);"
        "border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:0.83rem;color:#8B949E;'>"
        "⚠️ <b>Nota:</b> A Meta fornece dados de <i>Seguidores</i> como retrato atual (lifetime). "
        "Para <i>Engajados</i> e <i>Alcançados</i>, o timeframe disponível na API é o mês corrente. "
        "Esses dados <b>não são afetados</b> pelo filtro de período da barra lateral."
        "</div>",
        unsafe_allow_html=True,
    )

    selected = st.pills(
        "Selecione o Público",
        options=["👥 Seguidores (Lifetime)", "💬 Engajados (Este Mês)", "📡 Alcançados (Este Mês)"],
        default="👥 Seguidores (Lifetime)",
    )
    if not selected:
        selected = "👥 Seguidores (Lifetime)"

    if "Seguidores" in selected:
        _render_full_demo_section(demo.followers, "Seguidores")
    elif "Engajados" in selected:
        _render_full_demo_section(demo.engaged, "Público Engajado (Este Mês)")
    elif "Alcançados" in selected:
        _render_full_demo_section(demo.reached, "Público Alcançado (Este Mês)")


# ─────────────────────────────────────────────────────────────────────────────
# Aba Pago — Meta Ads
# ─────────────────────────────────────────────────────────────────────────────

def render_demographics_tab(date_preset: str, time_range: dict | None = None) -> None:
    """Renderiza a aba Demográfica de Anúncios (Ads)."""
    st.markdown("### 👥 Perfil de Audiência (Anúncios Pagos — Meta Ads)")
    st.markdown(
        "<p style='color:#94A3B8;margin-bottom:24px;'>"
        "Visão demográfica das pessoas impactadas pelas suas campanhas pagas "
        "(Idade/Gênero, Região/Estado e País)."
        "</p>",
        unsafe_allow_html=True,
    )

    try:
        from api.meta_client import MetaAdsClient

        client = MetaAdsClient()
        demo = client.get_demographics_insights(date_preset, time_range)

        if not demo or (not demo.age_gender and not demo.cities and not demo.countries):
            st.info("Não há dados demográficos disponíveis para o período selecionado.")
            return

        # Normalizar keys do Ads para formato uniforme (ex: "25-34 (male)" → "25-34 (M)")
        formatted_ag: dict[str, int] = {}
        for k, v in demo.age_gender.items():
            norm = k.replace("(male)", "(M)").replace("(female)", "(F)").replace("(unknown)", "(U)")
            formatted_ag[norm] = v

        demo_fmt = InstagramDemographics(
            age_gender=formatted_ag,
            cities=demo.cities,     # regions/estados
            countries=demo.countries,
        )

        render_age_gender_chart(demo_fmt, "Anúncios (Impressões por faixa)")

        st.write("")
        col1, col2 = st.columns(2)
        with col1:
            render_top_locations(
                demo_fmt.cities,
                "Top Regiões/Estados (Ads)",
                color="#F59E0B",
            )
        with col2:
            render_top_locations(
                demo_fmt.countries,
                "Top Países (Ads)",
                color="#10B981",
            )

    except Exception as e:
        st.error("Erro ao carregar dados demográficos de anúncios.")
        import sentry_sdk
        sentry_sdk.capture_exception(e)
        import logging
        logging.getLogger(__name__).error(f"Erro demographics ads: {e}")
