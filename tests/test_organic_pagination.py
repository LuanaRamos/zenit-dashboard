from types import SimpleNamespace

import pytest

from api.exceptions import InstagramAPIError
from api.instagram_client import InstagramClient


def _client_with_media_request(request):
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig-account"
    client._make_request = request
    client.token = "test-token"
    client.session = SimpleNamespace(
        post=lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: []
        )
    )
    return client


def test_first_media_page_failure_is_not_reported_as_an_empty_account():
    def fail_first_page(_endpoint, _params):
        raise InstagramAPIError("media list unavailable")

    client = _client_with_media_request(fail_first_page)

    with pytest.raises(InstagramAPIError, match="media list unavailable"):
        client.get_recent_media()


def test_later_media_page_failure_is_not_returned_as_partial_results():
    calls = 0

    def fail_second_page(_endpoint, _params):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "data": [{"id": "media-1", "media_type": "IMAGE"}],
                "paging": {
                    "cursors": {"after": "next-page"},
                    "next": "https://graph.facebook.com/ig-account/media?after=next-page",
                },
            }
        raise InstagramAPIError("second page unavailable")

    client = _client_with_media_request(fail_second_page)

    with pytest.raises(InstagramAPIError, match="second page unavailable"):
        client.get_recent_media()

    assert calls == 2


def test_full_history_reaches_oldest_post_beyond_page_size_and_empty_page():
    recent = [
        {"id": str(index), "media_type": "IMAGE", "timestamp": "2026-10-01T12:00:00Z"}
        for index in range(100)
    ]
    pages = {
        None: {
            "data": recent,
            "paging": {"next": "page-2", "cursors": {"after": "cursor-2"}},
        },
        "cursor-2": {
            "data": [],
            "paging": {"next": "page-3", "cursors": {"after": "cursor-3"}},
        },
        "cursor-3": {
            "data": [
                recent[-1],
                {
                    "id": "first-post",
                    "media_type": "IMAGE",
                    "caption": "Primeira publicação do perfil",
                    "timestamp": "2011-05-02T12:00:00Z",
                },
            ],
            # A última página ainda pode ter cursor, mas não tem próxima página.
            "paging": {"cursors": {"after": "end"}},
        },
    }
    requests = []

    def request(endpoint, params):
        requests.append((endpoint, dict(params)))
        return pages[params.get("after")]

    media = _client_with_media_request(request).get_recent_media(limit=100)

    assert len(media) == 101
    assert len({item.id for item in media}) == 101
    assert media[-1].id == "first-post"
    assert media[-1].caption == "Primeira publicação do perfil"
    assert media[-1].timestamp == "2011-05-02T12:00:00Z"
    assert len(requests) == 3
    assert all(endpoint == "ig-account/media" for endpoint, _ in requests)
    assert all("since" not in params and "until" not in params for _, params in requests)


@pytest.mark.parametrize("after", [None, "same-cursor"])
def test_broken_pagination_does_not_claim_partial_history_is_complete(after):
    requests = []

    def request(_endpoint, params):
        requests.append(dict(params))
        return {
            "data": [{"id": str(len(requests)), "media_type": "IMAGE"}],
            "paging": {"next": "next-page", "cursors": {"after": after}},
        }

    client = _client_with_media_request(request)

    with pytest.raises(InstagramAPIError, match="histórico completo"):
        client.get_recent_media()

    assert len(requests) == (1 if after is None else 2)


@pytest.mark.parametrize("client_name", ["Pousada dos Mundos", "VIP Pilates"])
def test_maximum_history_has_no_date_cutoff_for_selected_profile(monkeypatch, client_name):
    from ui import data_loader

    calls = []

    def get_client(selected_name):
        def get_recent_media(**kwargs):
            calls.append((selected_name, kwargs))
            return [selected_name]

        return SimpleNamespace(get_recent_media=get_recent_media)

    monkeypatch.setattr(data_loader, "get_instagram_client", get_client)
    stale_range = {"since": "2026-09-01", "until": "2026-10-01"}

    result = data_loader.fetch_organic_media.__wrapped__("maximum", stale_range, client_name)

    assert result == [client_name]
    assert calls == [(client_name, {"limit": 100})]


def test_custom_period_keeps_its_date_filter(monkeypatch):
    from ui import data_loader

    calls = []
    monkeypatch.setattr(
        data_loader,
        "get_instagram_client",
        lambda _: SimpleNamespace(get_recent_media=lambda **kwargs: calls.append(kwargs)),
    )

    data_loader.fetch_organic_media.__wrapped__(
        "custom", {"since": "2026-09-01", "until": "2026-10-01"}, "Pousada dos Mundos"
    )

    assert calls[0]["since_timestamp"] < calls[0]["until_timestamp"]
