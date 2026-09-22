from api.meta_client import MetaAdsClient
from schemas.meta import CampaignInsight, parse_paid_actions


def test_campaign_parser_preserves_official_clicks_and_distinct_click_types():
    campaign = CampaignInsight.from_api_response(
        {
            "clicks": "17",
            "inline_link_clicks": "6",
            "outbound_clicks": [{"action_type": "outbound_click", "value": "4"}],
            "actions": [
                {"action_type": "link_click", "value": "9"},
                {"action_type": "profile_visit", "value": "3"},
                {"action_type": "post_interaction_gross", "value": "40"},
            ],
        }
    )

    assert campaign.clicks == 17
    assert campaign.link_clicks == 6
    assert campaign.inline_link_clicks == 6
    assert campaign.outbound_clicks == 4
    assert campaign.other_clicks == 11


def test_campaign_parser_prefers_canonical_lead_even_when_it_is_zero():
    campaign = CampaignInsight.from_api_response(
        {
            "actions": [
                {"action_type": "lead", "value": "0"},
                {"action_type": "leadgen", "value": "8"},
                {"action_type": "offsite_conversion.fb_pixel_lead", "value": "5"},
            ]
        }
    )

    assert campaign.leads == 0
    assert campaign.site_leads == 5
    assert campaign.native_leads == 8


def test_campaign_parser_falls_back_to_named_lead_sources_without_overlap():
    campaign = CampaignInsight.from_api_response(
        {
            "actions": [
                {"action_type": "leadgen", "value": "3"},
                {"action_type": "offsite_conversion.fb_pixel_lead", "value": "4"},
            ]
        }
    )

    assert campaign.leads == 7
    assert campaign.site_leads == 4
    assert campaign.native_leads == 3


def test_messaging_uses_one_exact_canonical_event_without_prefix_double_counting():
    metrics = parse_paid_actions(
        [
            {
                "action_type": "onsite_conversion.messaging_conversation_started_7d",
                "value": "2",
            },
            {
                "action_type": "onsite_conversion.messaging_conversation_started_7d_extra",
                "value": "99",
            },
            {
                "action_type": "onsite_conversion.messaging_conversation_started",
                "value": "7",
            },
        ]
    )

    assert metrics["messaging_conversations"] == 2


def test_messaging_canonical_zero_does_not_fall_back_to_legacy_event():
    metrics = parse_paid_actions(
        [
            {
                "action_type": "onsite_conversion.messaging_conversation_started_7d",
                "value": "0",
            },
            {
                "action_type": "onsite_conversion.messaging_conversation_started",
                "value": "7",
            },
        ]
    )

    assert metrics["messaging_conversations"] == 0


def test_campaign_request_fetches_distinct_click_fields_and_uses_canonical_parser():
    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_1"
    calls = []

    def request(endpoint, params):
        calls.append((endpoint, params.copy()))
        return {
            "data": [
                {
                    "clicks": "12",
                    "inline_link_clicks": "5",
                    "outbound_clicks": [
                        {"action_type": "outbound_click", "value": "3"}
                    ],
                    "actions": [
                        {"action_type": "lead", "value": "2"},
                        {"action_type": "leadgen", "value": "9"},
                    ],
                }
            ]
        }

    client._make_request = request

    [campaign] = client.get_campaign_insights()

    assert "inline_link_clicks,outbound_clicks" in calls[0][1]["fields"]
    assert (campaign.clicks, campaign.inline_link_clicks, campaign.outbound_clicks) == (
        12,
        5,
        3,
    )
    assert campaign.leads == 2
