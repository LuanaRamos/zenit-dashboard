"""Regressões de KPIs da conta e exportação completa de publicações."""

from types import SimpleNamespace

from schemas.instagram import InstagramMedia
from ui.organic_components import (
    ORGANIC_POST_EXPORT_COLUMNS,
    _organic_post_rows,
    account_engagement_rows,
)


def test_profile_link_taps_are_not_url_specific_clicks():
    rows = account_engagement_rows({
        "profile_links_taps": 24,
        "_coverage": {
            "profile_links_taps": {
                "since": "2026-11-01",
                "until": "2026-11-08",
                "status": "ok",
            }
        },
    })
    taps = next(row for row in rows if row["Campo API"] == "profile_links_taps")
    exact = next(row for row in rows if row["Indicador"] == "Cliques na URL específica da bio")
    assert taps["Valor"] == 24
    assert exact["Valor"] is None
    assert exact["Status"] == "nao_fornecido_pela_meta"


def test_export_has_all_loaded_posts_regardless_of_format():
    posts = [
        InstagramMedia(id="one", media_type="IMAGE", saved=3, shares=2),
        InstagramMedia(
            id="two",
            media_type="VIDEO",
            media_product_type="REELS",
            organic_views=320,
            insights_status="parcial",
            insights_available=("views", "reach"),
            insights_missing=("shares",),
        ),
    ]
    all_rows = _organic_post_rows(posts, "Todos")
    assert len(all_rows) == 2
    assert len(_organic_post_rows(posts, "Imagem")) == 1
    assert set(ORGANIC_POST_EXPORT_COLUMNS).issubset(all_rows[0])
    assert all_rows[0]["Compartilhamentos (Media Insights)"] == 2
    assert all_rows[0]["Salvamentos (Media Insights)"] == 3
    assert all_rows[1]["Visualizações orgânicas"] == 320
    assert all_rows[1]["Métricas indisponíveis"] == "shares"


def test_metric_none_is_not_converted_to_zero_in_export():
    row = _organic_post_rows([InstagramMedia(id="no-insights")], "Todos")[0]
    assert row["Alcance (Media Insights)"] is None
    assert row["Compartilhamentos (Media Insights)"] is None
    assert row["Curtidas públicas (objeto mídia)"] is None
    assert row["Status da coleta de Insights"] == "indisponivel"


def test_media_metric_fallback_preserves_other_metrics():
    from api.instagram_client import InstagramClient

    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig-account"
    client.token = "test-token"
    client._make_request = lambda endpoint, params: {
        "data": [{"id": "media-one", "media_type": "IMAGE", "like_count": 5}],
    }

    def batch_request(_url, data=None, timeout=None):
        import json

        entries = json.loads(data["batch"])
        payload = []
        for entry in entries:
            metric_set = entry["relative_url"].split("?metric=", 1)[1].split(",")
            if len(metric_set) > 1 and "shares" in metric_set:
                payload.append({"code": 400, "body": "{}"})
            else:
                payload.append({
                    "code": 200,
                    "body": json.dumps({"data": [
                        {"name": metric, "values": [{"value": 9}]}
                        for metric in metric_set
                        if metric in {"views", "reach", "likes", "comments", "saved"}
                    ]}),
                })
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    client.session = SimpleNamespace(post=batch_request)
    result = client.get_recent_media()
    assert len(result) == 1
    media = result[0]
    assert media.reach == 9
    assert media.organic_views == 9
    assert media.like_count == 9
    assert media.shares is None
    assert "reach" in media.insights_available
    assert "shares" in media.insights_missing
    assert media.insights_status == "parcial"
