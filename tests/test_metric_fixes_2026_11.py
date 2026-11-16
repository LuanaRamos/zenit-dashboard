"""Regressões de métricas e integrações: somente fixtures, sem chamadas reais à Meta."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from api.exceptions import MetaAPIError
from api.instagram_client import InstagramClient
from api.meta_client import MetaAdsClient
from core.config import Settings
from schemas.instagram import InstagramMedia
from schemas.meta import CampaignInsight, cost_per_account_conversation


def _meta(request):
    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_test"
    client._make_request = request
    return client


def test_campaign_insights_stops_when_cursor_exists_but_next_is_absent():
    calls = []
    def request(endpoint, params):
        calls.append(dict(params))
        return {
            "data": [{"campaign_name": "A", "campaign_id": "1", "spend": "90"}],
            "paging": {"cursors": {"after": "terminal-cursor"}},
        }
    rows = _meta(request).get_campaign_insights()
    assert len(rows) == 1
    assert len(calls) == 1


def test_creative_cpa_never_adds_leads_to_messaging_conversations():
    def request(endpoint, params):
        if endpoint.endswith("/insights"):
            return {"data": [{
                "ad_id": "1", "ad_name": "Duplicated funnel",
                "objective": "OUTCOME_LEADS", "spend": "100",
                "actions": [
                    {"action_type": "lead", "value": "2"},
                    {"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "2"},
                ],
            }]}
        return {"data": []}
    row = _meta(request).get_creative_performance()[0]
    assert row.leads == 2
    assert row.whatsapp_starts == 2
    assert row.cpl == 50.0
    assert row.cost_per_whatsapp == 50.0
    assert row.cpa == 50.0


def test_creative_api_errors_do_not_become_fake_empty_results():
    def request(endpoint, params):
        if endpoint.endswith("/insights"):
            raise MetaAPIError("Meta API offline")
        return {"data": []}
    with pytest.raises(MetaAPIError):
        _meta(request).get_creative_performance()


def test_ads_region_breakdown_does_not_use_invalid_audience_city():
    requested = []
    def request(endpoint, params):
        requested.append(params.get("breakdowns"))
        if params.get("breakdowns") == "region":
            return {"data": [{"region": "Paraíba", "impressions": "44"}]}
        return {"data": []}
    meta = _meta(request)
    summary = meta.get_demographics_insights()
    assert "region" in requested
    assert "audience_city" not in requested
    assert summary.cities == {"Paraíba": 44}


def test_paid_reach_preserves_unavailable_instead_of_zero():
    assert InstagramMedia(id="ig-id", paid_reach=None).paid_reach is None


def test_cost_per_conversation_uses_entire_account_spend_and_explicit_label():
    campaigns = [
        CampaignInsight(spend=100, whatsapp_starts=10, objective="OUTCOME_ENGAGEMENT"),
        CampaignInsight(spend=100, whatsapp_starts=0, objective="OUTCOME_ENGAGEMENT"),
    ]
    assert cost_per_account_conversation(campaigns) == 20.0


def test_invalid_client_configuration_is_not_disguised_as_empty_list():
    settings = Settings(
        META_MASTER_TOKEN="fake",
        CLIENTS_JSON=json.dumps([
            {"name": "Válido", "ad_account_id": "act_one", "page_id": "page_one"},
            {"name": None, "ad_account_id": "act_two", "page_id": "page_two"},
        ]),
    )
    with pytest.raises(ValueError, match="2"):
        settings.get_clients()


def test_reel_never_requests_unsupported_follows_or_profile_visits():
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig_account"
    client.token = "fake"
    client._make_request = lambda endpoint, params: {"data": [
        {"id": "reel-1", "media_product_type": "REELS", "media_type": "VIDEO"},
        {"id": "feed-1", "media_product_type": "FEED", "media_type": "IMAGE"},
    ]}
    calls = []
    def fake_post(url, data, timeout):
        entries = json.loads(data["batch"])
        output = []
        for entry in entries:
            path, requested = entry["relative_url"].split("?metric=", 1)
            media_id = path.split("/")[-2]
            metrics = requested.split(",")
            calls.append((media_id, metrics))
            output.append({"code": 200, "body": json.dumps({"data": [
                {"name": m, "values": [{"value": 1}]} for m in metrics
            ]})})
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: output)
    client.session = SimpleNamespace(post=fake_post)
    reel, feed = client.get_recent_media()
    assert reel.follows is None and reel.profile_visits is None
    assert "follows" in reel.insights_unsupported
    assert "profile_visits" in reel.insights_unsupported
    assert feed.insights_unsupported == ()
    assert all(not (set(metrics) & {"follows", "profile_visits"})
               for media_id, metrics in calls if media_id == "reel-1")
    assert any("follows" in metrics for media_id, metrics in calls if media_id == "feed-1")


def test_account_follow_activity_parses_follow_type_breakdown():
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig_account"
    def request(endpoint, params):
        if params.get("metric") == "follows_and_unfollows":
            assert params.get("breakdown") == "follow_type"
            return {"data": [{
                "name": "follows_and_unfollows",
                "total_value": {"breakdowns": [{
                    "dimension_keys": ["follow_type"],
                    "results": [
                        {"dimension_values": ["FOLLOWER"], "value": 8},
                        {"dimension_values": ["NON_FOLLOWER"], "value": 3},
                    ],
                }]},
            }]}
        return {"data": []}
    client._make_request = request
    insights = client.get_account_insights(
        "custom", {"since": "2026-11-01", "until": "2026-11-15"}
    )
    assert insights["new_follows"] == 8
    assert insights["unfollows"] == 3
    assert insights["net_follows"] == 5
    assert insights["_coverage"]["follows_and_unfollows"]["status"] == "ok"


def test_dashboard_account_rows_preserve_follows_source_and_contact_button_meaning():
    from ui.organic_components import account_engagement_rows

    rows = account_engagement_rows({
        "new_follows": 8, "unfollows": 3, "net_follows": 5,
        "profile_links_taps": 2,
        "_coverage": {"follows_and_unfollows": {
            "status": "ok", "since": "2026-11-01", "until": "2026-11-15",
        }},
    })
    by_label = {r["Indicador"]: r for r in rows}
    assert by_label["Novos seguidores"]["Valor"] == 8
    assert by_label["Deixaram de seguir"]["Valor"] == 3
    assert by_label["Saldo de seguidores"]["Valor"] == 5
    assert by_label["Novos seguidores"]["Status"] == "ok"
    assert by_label["Toques em botões de contato"]["Valor"] == 2
    assert by_label["Cliques na URL específica da bio"]["Valor"] is None


def test_api_clients_are_not_shared_request_sessions_between_callers(monkeypatch):
    from ui import data_loader

    cfg = SimpleNamespace(
        name="Conta Exemplo", ad_account_id="act_test", page_id="page_test", token="fake"
    )
    monkeypatch.setattr(
        data_loader, "settings", SimpleNamespace(get_clients=lambda: [cfg])
    )
    first = data_loader.get_api_client("Conta Exemplo")
    second = data_loader.get_api_client("Conta Exemplo")
    assert first is not second
    assert first.session is not second.session
