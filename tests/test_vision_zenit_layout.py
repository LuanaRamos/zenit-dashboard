"""Referência Vision UI adaptada para a paleta Zenit; não depende de API real."""
from datetime import date, timedelta

import plotly.graph_objects as go

from schemas.meta import CampaignInsight
from ui import components, organic_components
from pathlib import Path


STYLE = Path(__file__).resolve().parents[1] / "src/dashboard/ui/style.css"


def test_vision_style_preserves_zenit_gold_and_compact_grid():
    css = STYLE.read_text(encoding="utf-8").lower()
    assert "--primary: #ffb300;" in css
    assert "--zenit-chart-gold:" in css
    assert "--zenit-panel:" in css
    assert ".zenit-feature-card" in css
    assert ".kpi-icon" in css
    assert "@media (max-width: 640px)" in css
    assert "prefers-reduced-motion" in css


def test_kpi_uses_real_bootstrap_icon_and_never_invents_trend(monkeypatch):
    rendered = []
    monkeypatch.setattr(components.st, "markdown", lambda value, **_: rendered.append(value))
    components.render_metric_card(
        "INVESTIMENTO TOTAL", "R$ 800,00", "No período", "Valores da Meta"
    )
    html = rendered[0]
    assert 'data-lucide="wallet"' in html
    assert 'aria-hidden="true"' in html
    assert 'R$ 800,00' in html
    assert "%" not in html


def test_campaign_highlight_uses_actual_messaging_result(monkeypatch):
    rendered = []
    monkeypatch.setattr(components.st, "markdown", lambda value, **_: rendered.append(value))
    campaigns = [
        CampaignInsight(campaign_name="Feriado", spend=200, whatsapp_starts=12),
        CampaignInsight(campaign_name="Vídeo novo", spend=350, whatsapp_starts=24),
    ]
    components.render_campaign_highlight(campaigns)
    html = rendered[0]
    assert "Vídeo novo" in html
    assert "24" in html
    assert "Mais conversas no período" in html
    assert "reserva" not in html.lower()  # Sem inferir venda a partir de conversa


def test_objective_chart_is_vision_style_donut_not_old_full_pie(monkeypatch):
    figures = []
    monkeypatch.setattr(components, "render_glass_chart", lambda fig, **kw: figures.append(fig))
    components.render_objective_pie_chart([
        CampaignInsight(objective="OUTCOME_ENGAGEMENT", spend=100, whatsapp_starts=5),
        CampaignInsight(objective="OUTCOME_TRAFFIC", spend=70),
    ])
    chart = figures[0]
    assert isinstance(chart.data[0], go.Pie)
    assert chart.data[0].hole >= 0.58
    assert chart.layout.paper_bgcolor == "rgba(0,0,0,0)"


def test_cost_chart_uses_actual_costs_and_gold_bars(monkeypatch):
    figures = []
    monkeypatch.setattr(components, "render_glass_chart", lambda fig, **kw: figures.append(fig))
    rows = [
        CampaignInsight(campaign_name="Campanha A", spend=60, whatsapp_starts=12, cost_per_whatsapp=5),
        CampaignInsight(campaign_name="Campanha B", spend=100, whatsapp_starts=20, cost_per_whatsapp=5),
    ]
    components.render_whatsapp_cost_chart(rows)
    assert figures
    chart = figures[0]
    assert isinstance(chart.data[0], go.Bar)
    assert list(chart.data[0].y) == [5, 5]
    assert chart.data[0].marker.color == "#FFB300"


def test_followers_area_and_moving_average_use_real_history(monkeypatch):
    figures = []
    monkeypatch.setattr(organic_components.st, "plotly_chart", lambda fig, **kw: figures.append(fig))
    monkeypatch.setattr(organic_components.st, "markdown", lambda value, **kw: None)
    start = date(2026, 11, 1)
    data = [
        {"Data": str(start + timedelta(days=d)), "Novos Seguidores": n}
        for d, n in enumerate([1, 0, 5, 2, 7, 3, 4, 6])
    ]
    organic_components.render_followers_timeline(data)
    assert len(figures) == 1
    fig = figures[0]
    assert len(fig.data) >= 2
    assert fig.data[0].type == "scatter"
    assert fig.data[0].fill == "tozeroy"
    assert "Média móvel" in fig.data[1].name
    assert list(fig.data[0].y) == [1, 0, 5, 2, 7, 3, 4, 6]


def test_reusable_lucide_icons_have_accessible_vector_strokes():
    from ui.iconography import lucide_icon
    icon = lucide_icon("chart", size=20)
    assert 'data-lucide="chart"' in icon
    assert 'viewBox="0 0 24 24"' in icon
    assert 'aria-hidden="true"' in icon
    assert "<svg" in icon


def test_profile_notices_are_consolidated_under_diagnostics():
    import inspect
    source = inspect.getsource(organic_components.render_account_engagement_summary)
    assert '"Diagnóstico e cobertura"' in source
    assert 'st.info(' not in source
    assert 'st.warning(' not in source
    assert '"Toques em botões de contato"' in inspect.getsource(
        organic_components.account_engagement_rows
    )
