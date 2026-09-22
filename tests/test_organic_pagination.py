import pytest

from api.exceptions import InstagramAPIError
from api.instagram_client import InstagramClient


def _client_with_media_request(request):
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "ig-account"
    client._make_request = request
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
                "paging": {"cursors": {"after": "next-page"}},
            }
        raise InstagramAPIError("second page unavailable")

    client = _client_with_media_request(fail_second_page)

    with pytest.raises(InstagramAPIError, match="second page unavailable"):
        client.get_recent_media()

    assert calls == 2
