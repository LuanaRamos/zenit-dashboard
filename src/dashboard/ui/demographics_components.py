"""Componentes de visualização demográfica para Orgânico (Instagram) e Pago (Meta Ads)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as st_components
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
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(color="#F1F5F9", size=12),
        ),
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.95)",
            bordercolor="rgba(255,255,255,0.2)",
            font=dict(color="#FFFFFF", size=12, family="Inter"),
        ),
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_top_locations(
    data: dict[str, int],
    title: str,
    color: str = "#2A85FF",
    max_items: int = 15,
) -> None:
    """
    Renderiza barras de localização via iframe (components.html).
    Usa o mesmo padrão do render_glass_chart para evitar corte de labels
    que ocorre com st.plotly_chart dentro de colunas no Streamlit Cloud.
    """
    if not data:
        st.info(f"Sem dados de {title.lower()} disponíveis.")
        return

    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_items]
    names = [x[0] for x in sorted_items]
    values = [x[1] for x in sorted_items]

    # Margem direita generosa para não cortar os valores (textposition=outside)
    right_margin = max(70, max(len(f"{v:,}") for v in values) * 9)
    chart_height = max(240, len(sorted_items) * 30 + 70)

    fig = go.Figure(go.Bar(
        x=values,
        y=names,
        orientation="h",
        marker_color=color,
        text=[f"{v:,}".replace(",", ".") for v in values],
        textposition="outside",
        textfont=dict(color="#FFFFFF", size=12, family="Inter"),
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{x:,}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(color="#F8FAFC", size=13), x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1", size=12),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.07)",
            showticklabels=False,
            range=[0, max(values) * 1.35] if values else [0, 1],
        ),
        yaxis=dict(showgrid=False, autorange="reversed", tickfont=dict(size=12, color="#F1F5F9")),
        margin=dict(l=0, r=right_margin, t=36, b=0),
        height=chart_height,
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.95)",
            bordercolor="rgba(255,255,255,0.2)",
            font=dict(color="#FFFFFF", size=12, family="Inter"),
        ),
    )

    plotly_html = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": False},
    )
    iframe_html = f"""
    <html><head>
    <style>
        html, body {{ margin:0; padding:0; overflow:hidden; background:transparent; }}
    </style></head>
    <body>{plotly_html}</body></html>
    """
    st_components.html(iframe_html, height=chart_height + 10, scrolling=False)


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

@st.cache_data(ttl=3600)
def _fetch_ads_real_audience(date_preset: str, time_range: dict | None) -> dict:
    """Agrega o público REAL entregue (impressões) por todas as campanhas no período."""
    from api.meta_client import MetaAdsClient
    raw = MetaAdsClient().get_creative_real_audience(date_preset, time_range)

    age_gender: dict[str, int] = {}
    regions: dict[str, int] = {}
    countries: dict[str, int] = {}

    for aud in raw.values():
        for k, v in aud.get("age_gender", {}).items():
            age_gender[k] = age_gender.get(k, 0) + v
        for k, v in aud.get("regions", {}).items():
            regions[k] = regions.get(k, 0) + v
        for k, v in aud.get("countries", {}).items():
            countries[k] = countries.get(k, 0) + v

    return {"age_gender": age_gender, "regions": regions, "countries": countries}


def _render_age_gender_impressions(ag: dict[str, int], title: str) -> None:
    """Gráfico Idade × Gênero com eixo em Impressões (para Ads)."""
    rows = _normalize_age_gender(ag)
    if not rows:
        st.info("Sem dados de Idade/Gênero disponíveis.")
        return

    df = pd.DataFrame(rows).rename(columns={"Pessoas": "Impressões"})

    fig = px.bar(
        df,
        x="Impressões",
        y="Faixa Etária",
        color="Gênero",
        barmode="group",
        category_orders={"Faixa Etária": _AGE_ORDER},
        color_discrete_map=_COLOR_GENDER,
        orientation="h",
        title=title,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0", size=13),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", showticklabels=False),
        yaxis=dict(showgrid=False, tickfont=dict(size=13)),
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_demographics_tab(date_preset: str, time_range: dict | None = None) -> None:
    """Renderiza a aba Demográfica de Anúncios (Ads) — público real entregue pelo algoritmo."""
    st.markdown("### 👥 Perfil de Audiência (Anúncios Pagos — Meta Ads)")
    st.markdown(
        "<p style='color:#94A3B8;margin-bottom:8px;'>"
        "Dados reais de entrega: quem de fato viu seus anúncios "
        "(Idade/Gênero, Estado/Região e País) — em Impressões."
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.3);"
        "border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:0.82rem;color:#A5B4FC;'>"
        "&#9888; <b>Advantage+ / IA da Meta:</b> Os dados refletem a entrega <i>real</i> "
        "do algoritmo — não o público configurado manualmente."
        "</div>",
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("Carregando audiência real entregue..."):
            real = _fetch_ads_real_audience(date_preset, time_range)

        if not any([real["age_gender"], real["regions"], real["countries"]]):
            st.info("Não há dados demográficos disponíveis para o período selecionado.")
            return

        _render_age_gender_impressions(
            real["age_gender"],
            "Impressões por Idade & Gênero (Entrega Real)",
        )

        st.write("")
        col1, col2 = st.columns(2)
        with col1:
            render_top_locations(real["regions"], "Top Estados/Regiões", color="#F59E0B")
        with col2:
            render_top_locations(real["countries"], "Top Países", color="#10B981")

    except Exception as e:
        import sentry_sdk
        import logging
        sentry_sdk.capture_exception(e)
        logging.getLogger(__name__).error(f"Erro demographics ads: {e}")
        st.error("Erro ao carregar dados demográficos de anúncios.")
