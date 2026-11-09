"""Regressões para cobertura histórica e métricas de Meta Ads / Instagram."""
from __future__ import annotations

import datetime
from types import SimpleNamespace

from api.instagram_client import InstagramClient
from api.meta_client import MetaAdsClient
from schemas.meta import CampaignInsight


def _instagram_client(request):
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig123"
    client._make_request = request
    return client


def _ads_client(request):
    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_456"
    client._make_request = request
    return client


def test_account_unique_reach_is_not_summed_across_windows():
    calls = []

    def fake_request(_endpoint, params):
        calls.append(dict(params))
        metrics = params["metric"].split(",")
        return {"data": [
            {"name": name, "total_value": {"value": 100 if name == "reach" else 7}}
            for name in metrics
        ]}

    report = _instagram_client(fake_request).get_account_insights("maximum")
    assert report["reach"] == 100
    assert report["accounts_engaged"] == 7
    assert report["views"] > 7
    assert report["_coverage"]["reach"]["status"] == "parcial"
    assert report["_coverage"]["reach"]["since"] is not None
    assert report["_coverage"]["views"]["since"] is not None
    assert report["profile_views"] is None
    assert report["_coverage"]["profile_views"]["status"] == "indisponivel"
    assert len([call for call in calls if call["metric"] == "reach"]) == 1


def test_account_metric_error_is_missing_not_zero():
    def broken(_endpoint, _params):
        raise RuntimeError("Unsupported metric")

    report = _instagram_client(broken).get_account_insights("last_30d")
    assert report["views"] is None
    assert report["reach"] is None
    assert report["_coverage"]["views"]["status"] == "indisponivel"


def test_paid_actions_from_distinct_rows_are_summed_not_maxed():
    def fake_request(_endpoint, _params):
        return {"data": [
            {
                "publisher_platform": "instagram",
                "reach": "100", "impressions": "200",
                "actions": [
                    {"action_type": "post", "value": "15"},
                    {"action_type": "onsite_conversion.post_net_save", "value": "3"},
                    {"action_type": "onsite_conversion.post_net_like", "value": "7"},
                ],
            },
            {
                "publisher_platform": "instagram",
                "reach": "50", "impressions": "90",
                "actions": [
                    {"action_type": "post", "value": "25"},
                    {"action_type": "onsite_conversion.post_net_save", "value": "4"},
                    {"action_type": "onsite_conversion.post_net_like", "value": "8"},
                ],
            },
            {"publisher_platform": "facebook", "reach": "9999", "impressions": "9999"},
        ]}

    totals = _ads_client(fake_request).get_instagram_paid_totals()
    assert totals["shares"] == 40
    assert totals["saved"] == 7
    assert totals["likes"] == 15
    assert totals["impressions"] == 290


def test_paid_profile_fields_override_legacy_action_aliases():
    ad = CampaignInsight.from_api_response({
        "campaign_name": "Teste", "spend": "200",
        "instagram_profile_follow": "12",
        "instagram_profile_visits": "45",
        "actions": [
            {"action_type": "instagram_follows", "value": "1"},
            {"action_type": "profile_visit", "value": "2"},
        ],
    })
    assert ad.instagram_follows == 12
    assert ad.profile_visits == 45


def test_first_delivery_is_found_in_first_active_month():
    def request(_endpoint, params):
        if params["time_increment"] == "monthly":
            return {"data": [
                {"date_start": "2026-09-01", "date_stop": "2026-09-30",
                 "spend": "50", "impressions": "200"},
                {"date_start": "2026-10-01", "date_stop": "2026-10-31",
                 "spend": "80", "impressions": "500"},
            ]}
        return {"data": [
            {"date_start": "2026-09-01", "spend": "0", "impressions": "0"},
            {"date_start": "2026-09-09", "spend": "1.3", "impressions": "40"},
        ]}

    client = _ads_client(request)
    client.get_ads_history_range = lambda: {
        "since": "2026-08-01", "until": "2026-11-09"
    }
    result = client.get_ads_history_coverage()
    assert result["first_delivery"] == "2026-09-09"
    assert result["status"] == "ok"


def test_ads_history_not_fixed_to_395_days():
    today = datetime.date.today()

    def request(_endpoint, _params):
        return {"created_time": "2024-01-10T12:00:00+0000"}

    result = _ads_client(request).get_ads_history_range()
    start = datetime.date.fromisoformat(result["since"])
    assert (today - start).days > 395
    assert (today - start).days <= 1135
