"""Regressões: cobertura de posicionamentos e atividade real do perfil.

Os testes usam somente respostas simuladas, nunca tokens reais.
"""
from datetime import date

from api.meta_client import MetaAdsClient
from api.instagram_client import InstagramClient
from ui.organic_components import account_engagement_rows


def test_creative_performance_includes_facebook_and_aggregated_placements():
    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_fixture"
    observed = []
    def request(endpoint, params):
        observed.append((endpoint, dict(params)))
        if endpoint.endswith("/insights"):
            return {"data": [
                {"ad_id": "ad-facebook", "ad_name": "FB", "spend": "30",
                 "impressions": "1000", "clicks": "10",
                 "actions": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "3"}]},
                {"ad_id": "ad-multiplatform", "ad_name": "All", "spend": "20",
                 "impressions": "500", "clicks": "4", "actions": []},
            ]}
        if endpoint.endswith("/ads"):
            return {"data": []}
        raise AssertionError(endpoint)
    client._make_request = request
    rows = client.get_creative_performance("last_30d")
    assert {row.ad_id for row in rows} == {"ad-facebook", "ad-multiplatform"}
    assert any(row.ad_id == "ad-facebook" and row.whatsapp_starts == 3 for row in rows)
    assert "breakdowns" not in observed[0][1]


def test_platform_breakdown_covers_multiple_networks_without_changing_total():
    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_fixture"
    def request(endpoint, params):
        assert params["breakdowns"] == "publisher_platform"
        return {"data": [
            {"ad_id": "ad1", "publisher_platform": "instagram", "spend": "15",
             "impressions": "100", "clicks": "10", "actions": []},
            {"ad_id": "ad1", "publisher_platform": "facebook", "spend": "5",
             "impressions": "50", "clicks": "1", "actions": []},
        ]}
    client._make_request = request
    result = client.get_creative_platform_breakdown("last_30d")
    assert [(p["platform"], p["spend"]) for p in result["ad1"]] == [
        ("instagram", 15.0), ("facebook", 5.0)
    ]


def test_profile_activity_keeps_supported_values_and_missing_address_separate():
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig_fixture"
    def request(endpoint, params):
        metric = params["metric"]
        if metric == "profile_views":
            return {"data": [{"name": "profile_views", "total_value": {"value": 677}}]}
        if metric == "website_clicks":
            return {"data": [{"name": "website_clicks", "total_value": {"value": 168}}]}
        if metric == "profile_links_taps":
            return {"data": [{"name": metric, "total_value": {"value": 120}}]}
        return {"data": []}
    client._make_request = request
    insights = client.get_account_insights(
        "custom", {"since": "2026-11-01", "until": "2026-11-15"}
    )
    assert insights["profile_views"] == 677
    assert insights["website_clicks"] == 168
    assert insights["profile_links_taps"] == 120
    rows = {row["Indicador"]: row for row in account_engagement_rows(insights)}
    assert rows["Visitas ao perfil"]["Valor"] == 677
    assert rows["Toques no endereço comercial"]["Valor"] is None
    assert rows["Cliques na URL específica da bio"]["Valor"] is None


def test_legacy_profile_activity_does_not_fabricate_zero_on_error():
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig_fixture"
    def request(endpoint, params):
        if params["metric"] in {"profile_views", "website_clicks"}:
            raise ValueError("Métrica indisponível")
        return {"data": []}
    client._make_request = request
    insights = client.get_account_insights(
        "custom", {"since": "2026-11-01", "until": "2026-11-15"}
    )
    assert insights["profile_views"] is None
    assert insights["website_clicks"] is None
    assert insights["_coverage"]["profile_views"]["status"] == "indisponivel"
