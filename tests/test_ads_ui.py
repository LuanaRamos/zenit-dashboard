from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src/dashboard/app.py"


def test_ads_overview_contains_only_paid_leads(monkeypatch):
    from core.config import settings
    from schemas.meta import CampaignInsight
    from ui import data_loader, layouts
    from ui import demographics_components, creatives_components, catalog_components

    monkeypatch.setattr(
        layouts,
        "render_sidebar",
        lambda: ("Visão Geral (Ads)", "last_30d", None, settings.get_clients()[0]),
    )
    monkeypatch.setattr(
        data_loader,
        "fetch_campaigns_v8",
        lambda *a: [
            CampaignInsight(
                campaign_name="Aquisição",
                objective="OUTCOME_LEADS",
                spend=250.75,
                leads=5,
            )
        ],
    )
    monkeypatch.setattr(data_loader, "fetch_organic_leads_cached", lambda *a: 999)
    monkeypatch.setattr(
        demographics_components, "render_demographics_tab", lambda *a: None
    )
    monkeypatch.setattr(creatives_components, "render_creatives_tab", lambda *a: None)
    monkeypatch.setattr(catalog_components, "render_catalog_tab", lambda *a: None)

    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert not app.error
    visible = "\n".join(element.value for element in app.markdown)
    assert "1.004" not in visible
    assert "999" not in visible
    assert "250,75" in visible  # Keep cents, not the old int(spend) truncation.
    assert "5" in visible


def test_zero_conversations_does_not_claim_free_acquisition():
    app = AppTest.from_string("""
from ui.components import render_metric_cards
render_metric_cards(100.0, 0, None, 0, None)
""").run()
    assert not app.exception
    visible = "\n".join(element.value for element in app.markdown)
    assert "N/D" in visible
    assert "R$ 0,00" not in visible


def test_creative_card_keeps_click_types_and_message_cost_separate():
    app = AppTest.from_string("""
from ui.creatives_components import _render_creative_card
_render_creative_card({"ad_name": "Teste", "spend": 100.0,
    "clicks": 100, "link_clicks": 30, "outbound_clicks": 12,
    "other_clicks": 70, "profile_visits": 8, "whatsapp_starts": 5,
    "objective_friendly": "Mensagens", "cpa": 1.0})
""").run()
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics.get("Cliques no link") == "30"
    assert metrics.get("Cliques de saída") == "12"
    assert metrics.get("Outros cliques") == "70"
    assert metrics.get("💬 Conversas por mensagens") == "5"
    assert metrics.get("🎯 Custo p/ Mens.") == "R$ 20,00"


def test_campaign_table_keeps_aggregate_leads_without_inventing_source_breakdown(monkeypatch):
    import pandas as pd
    from schemas.meta import CampaignInsight
    from ui import components

    tables = []
    monkeypatch.setattr(components, "render_glass_table", lambda df, **kw: tables.append(df))
    campaign = CampaignInsight.from_api_response({
        "campaign_name": "Leads sem detalhamento", "spend": "100",
        "actions": [{"action_type": "lead", "value": "10"}],
    })
    components.render_general_campaigns([campaign])

    row = tables[0].iloc[0]
    assert row["Leads pagos"] == 10
    assert pd.isna(row["Leads (Site)"])
    assert pd.isna(row["Leads (Form)"])
