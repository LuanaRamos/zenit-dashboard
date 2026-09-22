import json

import pytest
import requests

from api.exceptions import InstagramAPIError, MetaAPIError
from api.instagram_client import InstagramClient
from api.meta_client import MetaAdsClient
from schemas.instagram import InstagramMedia
from ui import data_loader


class _BatchResponse:
    status_code = 200

    def __init__(self, insights):
        self._insights = insights

    def raise_for_status(self):
        return None

    def json(self):
        return [{"code": 200, "body": json.dumps({"data": self._insights})}]


class _BatchSession:
    def __init__(self, insights):
        self._insights = insights
        self.post_calls = []

    def post(self, *_args, **_kwargs):
        self.post_calls.append(_kwargs)
        return _BatchResponse(self._insights)


def _media_client(insights):
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig-account"
    client.token = "test-token"
    client.session = _BatchSession(insights)
    client._make_request = lambda _endpoint, _params: {
        "data": [
            {
                "id": "media-1",
                "like_count": 91,
                "comments_count": 17,
                "media_type": "IMAGE",
                "media_product_type": "FEED",
            }
        ]
    }
    return client


def test_media_insights_do_not_fall_back_to_visible_object_counters():
    media = _media_client([{"name": "reach", "values": [{"value": 12}]}]).get_recent_media()[0]

    assert media.like_count is None
    assert media.comments_count is None
    assert media.organic_views is None
    assert media.total_interactions is None
    assert media.visible_like_count == 91
    assert media.visible_comments_count == 17


def test_media_organic_fields_come_from_media_insights():
    insights = [
        {"name": "likes", "values": [{"value": 8}]},
        {"name": "comments", "values": [{"value": 3}]},
        {"name": "views", "values": [{"value": 55}]},
        {"name": "total_interactions", "values": [{"value": 14}]},
    ]

    media = _media_client(insights).get_recent_media()[0]

    assert (media.like_count, media.comments_count) == (8, 3)
    assert (media.organic_views, media.total_interactions) == (55, 14)


def test_feed_media_requests_supported_views_metric():
    client = _media_client([])

    client.get_recent_media()

    batch = json.loads(client.session.post_calls[0]["data"]["batch"])
    assert "views" in batch[0]["relative_url"].split("metric=", 1)[1].split(",")


def test_fetch_organic_media_never_constructs_a_meta_ads_client(monkeypatch):
    expected = [InstagramMedia(id="media-1", like_count=4)]

    class OrganicClient:
        def get_recent_media(self, **_kwargs):
            return expected

    monkeypatch.setattr(data_loader, "get_instagram_client", lambda _name: OrganicClient())
    monkeypatch.setattr(
        data_loader,
        "get_api_client",
        lambda _name: pytest.fail("organic fetch must not construct MetaAdsClient"),
    )

    result = data_loader.fetch_organic_media.__wrapped__("last_30d", None, "client-a")

    assert result == expected


def test_ad_enrichment_preserves_organic_values(monkeypatch):
    original = InstagramMedia(
        id="media-1",
        like_count=4,
        comments_count=2,
        organic_views=30,
        total_interactions=9,
    )
    monkeypatch.setattr(
        data_loader,
        "fetch_instagram_ads_mapping_cached",
        lambda *_args: {
            "media-1": {
                "reach": 20,
                "impressions": 40,
                "clicks": 5,
                "link_clicks": 2,
                "likes": 99,
                "reactions": 12,
                "shares": 7,
                "saved": 6,
                "views": 100,
            }
        },
    )

    enriched = data_loader.enrich_media_with_ads.__wrapped__(
        [original], "last_30d", None, "client-a"
    )[0]

    assert enriched.like_count == 4
    assert enriched.comments_count == 2
    assert enriched.organic_views == 30
    assert enriched.total_interactions == 9
    assert enriched.paid_likes == 99
    assert enriched.paid_reactions == 12


def test_ads_mapping_keeps_net_likes_separate_from_reactions_and_generic_like():
    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_1"

    responses = iter(
        [
            {
                "data": [
                    {
                        "ad_id": "ad-reaction",
                        "publisher_platform": "instagram",
                        "actions": [
                            {"action_type": "post_reaction", "value": "4"},
                            {"action_type": "like", "value": "99"},
                        ],
                    },
                    {
                        "ad_id": "ad-like-zero",
                        "publisher_platform": "instagram",
                        "actions": [
                            {
                                "action_type": "onsite_conversion.post_net_like",
                                "value": "0",
                            },
                            {"action_type": "post_reaction", "value": "3"},
                        ],
                    },
                ]
            },
            {
                "data": [
                    {
                        "id": "ad-reaction",
                        "creative": {"source_instagram_media_id": "media-reaction"},
                    },
                    {
                        "id": "ad-like-zero",
                        "creative": {"source_instagram_media_id": "media-like-zero"},
                    },
                ]
            },
        ]
    )
    client._make_request = lambda *_args, **_kwargs: next(responses)

    mapping = client.get_ads_reach_mapping()

    assert mapping["media-reaction"]["likes"] is None
    assert mapping["media-reaction"]["reactions"] == 4
    assert mapping["media-like-zero"]["likes"] == 0
    assert mapping["media-like-zero"]["reactions"] == 3


def test_multi_ad_mapping_preserves_missing_net_likes():
    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_1"
    responses = iter(
        [
            {
                "data": [
                    {
                        "ad_id": "ad-1",
                        "publisher_platform": "instagram",
                        "actions": [
                            {"action_type": "post_reaction", "value": "2"}
                        ],
                    },
                    {
                        "ad_id": "ad-2",
                        "publisher_platform": "instagram",
                        "actions": [
                            {"action_type": "post_reaction", "value": "3"},
                            {"action_type": "like", "value": "88"},
                        ],
                    },
                ]
            },
            {
                "data": [
                    {
                        "id": "ad-1",
                        "creative": {"source_instagram_media_id": "media-1"},
                    },
                    {
                        "id": "ad-2",
                        "creative": {"source_instagram_media_id": "media-1"},
                    },
                ]
            },
            {
                "data": [
                    {"publisher_platform": "instagram", "reach": "10"}
                ]
            },
        ]
    )
    client._make_request = lambda *_args, **_kwargs: next(responses)

    metrics = client.get_ads_reach_mapping()["media-1"]

    assert metrics["likes"] is None
    assert metrics["reactions"] == 5
    assert metrics["cpa"] is None


def test_paid_totals_propagate_api_failure():
    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_1"
    client._make_request = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        MetaAPIError("paid unavailable")
    )

    with pytest.raises(MetaAPIError, match="paid unavailable"):
        client.get_instagram_paid_totals()


@pytest.mark.parametrize(
    ("client_class", "error_class"),
    [(MetaAdsClient, MetaAPIError), (InstagramClient, InstagramAPIError)],
)
def test_http_401_is_detected_and_tls_verification_is_not_disabled(client_class, error_class):
    response = requests.Response()
    response.status_code = 401
    response._content = b'{"error":{"message":"expired"}}'

    class Session:
        def get(self, *_args, **kwargs):
            assert kwargs.get("verify", True) is True
            raise requests.HTTPError(response=response)

    client = object.__new__(client_class)
    client.session = Session()

    with pytest.raises(error_class, match="401"):
        client._make_request("endpoint")
