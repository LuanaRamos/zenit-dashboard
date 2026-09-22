from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "dashboard"))

from api.exceptions import InstagramAPIError  # noqa: E402
from api.instagram_client import InstagramClient  # noqa: E402
from ui import data_loader  # noqa: E402
from ui import organic_components as organic_ui  # noqa: E402



def _make_client():
    client = object.__new__(InstagramClient)
    client.instagram_account_id = "17841400000000"
    client.token = "test-token"
    client.API_VERSION = "v26.0"
    client.BASE_URL = "https://graph.facebook.com/v26.0"
    client.BATCH_URL = "https://graph.facebook.com"
    client.session = SimpleNamespace()
    return client


class _MockBatchResponse:
    def __init__(self, items, status_code=200):
        self.status_code = status_code
        self._items = items

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._items


# =====================================================================
# Testes de InstagramClient
# =====================================================================

def test_client_get_account_profile_info_success():
    client = _make_client()
    api_payload = {
        "id": "17841400000000",
        "username": "zenit.growth",
        "name": "Zenit Growth",
        "biography": "Estratégia e Dados",
        "profile_picture_url": "https://example.com/avatar.jpg",
        "followers_count": 15400,
        "follows_count": 320,
        "media_count": 115,
    }
    client._make_request = lambda endpoint, params: api_payload

    profile = client.get_account_profile_info()

    assert profile["username"] == "zenit.growth"
    assert profile["name"] == "Zenit Growth"
    assert profile["biography"] == "Estratégia e Dados"
    assert profile["profile_picture_url"] == "https://example.com/avatar.jpg"
    assert profile["followers_count"] == 15400
    assert profile["follows_count"] == 320
    assert profile["media_count"] == 115


def test_client_get_account_profile_info_partial_fields():
    client = _make_client()
    # Retorna apenas id e username
    client._make_request = lambda endpoint, params: {
        "id": "17841400000000",
        "username": "zenit_partial",
    }

    profile = client.get_account_profile_info()

    assert profile["username"] == "zenit_partial"
    assert profile["name"] == ""
    assert profile["biography"] == ""
    assert profile["followers_count"] == 0
    assert profile["follows_count"] == 0
    assert profile["media_count"] == 0


def test_client_get_account_profile_info_api_error_returns_fallback_dict():
    client = _make_client()

    def error_request(endpoint, params):
        raise InstagramAPIError("Graph API endpoint failed")

    client._make_request = error_request

    # Não deve levantar exceção, deve retornar dict padrão
    profile = client.get_account_profile_info()

    assert isinstance(profile, dict)
    assert profile["id"] == "17841400000000"
    assert profile["username"] == ""
    assert profile["followers_count"] == 0


def test_client_get_account_profile_info_requests_expected_fields():
    client = _make_client()
    called = []

    def mock_request(endpoint, params):
        called.append((endpoint, params))
        return {"id": "17841400000000", "username": "zenit"}

    client._make_request = mock_request

    client.get_account_profile_info()

    assert len(called) == 1
    endpoint, params = called[0]
    assert endpoint == "17841400000000"
    assert "username" in params["fields"]
    assert "followers_count" in params["fields"]
    assert "media_count" in params["fields"]


def test_client_get_comments_for_media_empty_list_returns_empty():
    client = _make_client()
    result = client.get_comments_for_media([])
    assert result == []


def test_client_get_comments_for_media_single_media_success():
    client = _make_client()
    comments_payload = {
        "data": [
            {
                "id": "c1",
                "text": "Excelente post!",
                "like_count": 12,
                "username": "maria",
                "timestamp": "2026-09-01T12:00:00+0000",
            },
            {
                "id": "c2",
                "text": "Parabéns equipe!",
                "like_count": 5,
                "username": "joao",
                "timestamp": "2026-09-01T12:30:00+0000",
            },
        ]
    }
    batch_response_item = [
        {"code": 200, "body": json.dumps(comments_payload)}
    ]

    client.session.post = lambda *args, **kwargs: _MockBatchResponse(batch_response_item)

    comments = client.get_comments_for_media(["media_101"])

    assert len(comments) == 2
    assert comments[0]["id"] == "c1"
    assert comments[0]["like_count"] == 12
    assert comments[1]["username"] == "joao"


def test_client_get_comments_for_media_batches_over_50_items():
    client = _make_client()
    post_calls = []

    def mock_post(*args, **kwargs):
        post_calls.append(kwargs)
        batch = json.loads(kwargs["data"]["batch"])
        # Retorna resposta vazia para cada item do batch
        items = [{"code": 200, "body": json.dumps({"data": []})} for _ in batch]
        return _MockBatchResponse(items)

    client.session.post = mock_post

    # 75 mídias devem gerar 2 chunks (50 + 25)
    media_ids = [f"media_{i}" for i in range(75)]
    client.get_comments_for_media(media_ids)

    assert len(post_calls) == 2
    batch_1 = json.loads(post_calls[0]["data"]["batch"])
    batch_2 = json.loads(post_calls[1]["data"]["batch"])
    assert len(batch_1) == 50
    assert len(batch_2) == 25


def test_client_get_comments_for_media_handles_item_level_batch_error():
    client = _make_client()
    success_payload = {
        "data": [{"id": "c1", "text": "Post válido", "like_count": 8, "username": "user1"}]
    }
    batch_response_item = [
        {"code": 200, "body": json.dumps(success_payload)},
        {"code": 400, "body": json.dumps({"error": {"message": "Invalid media"}})},
    ]

    client.session.post = lambda *args, **kwargs: _MockBatchResponse(batch_response_item)

    comments = client.get_comments_for_media(["m_valid", "m_invalid"])

    assert len(comments) == 1
    assert comments[0]["id"] == "c1"


def test_client_get_comments_for_media_http_error_returns_collected_without_crash():
    client = _make_client()

    def failing_post(*args, **kwargs):
        raise requests.RequestException("Connection timeout")

    client.session.post = failing_post

    comments = client.get_comments_for_media(["m1"])
    assert comments == []


def test_client_get_all_comments_for_account_delegates_to_media_ids():
    client = _make_client()
    # Se media_ids for passado diretamente
    client.get_comments_for_media = lambda ids, limit=25: [
        {"id": "c1", "text": "Comentário direto", "like_count": 3}
    ]

    comments = client.get_all_comments_for_account(["m1", "m2"])
    assert len(comments) == 1
    assert comments[0]["id"] == "c1"


def test_client_get_all_comments_for_account_empty_returns_empty():
    client = _make_client()
    assert client.get_all_comments_for_account([]) == []


def test_client_get_total_media_count_success_and_error():
    client = _make_client()
    client._make_request = lambda endpoint, params: {"media_count": 73}
    assert client.get_total_media_count() == 73

    def failing_req(endpoint, params):
        raise Exception("API failure")

    client._make_request = failing_req
    assert client.get_total_media_count() == 0


def test_client_get_all_media_ids_since_beginning_pagination():
    client = _make_client()
    pages = [
        {
            "data": [{"id": "m1"}, {"id": "m2"}],
            "paging": {"cursors": {"after": "page_2_cursor"}},
        },
        {
            "data": [{"id": "m3"}],
            "paging": {},
        },
    ]
    call_count = 0

    def mock_paginate(endpoint, params):
        nonlocal call_count
        res = pages[call_count]
        call_count += 1
        return res

    client._make_request = mock_paginate

    ids = client.get_all_media_ids_since_beginning()
    assert ids == ["m1", "m2", "m3"]
    assert call_count == 2


def test_client_get_all_media_ids_since_beginning_handles_api_error():
    client = _make_client()

    def fail_req(endpoint, params):
        raise InstagramAPIError("Error fetching media ids")

    client._make_request = fail_req
    ids = client.get_all_media_ids_since_beginning()
    assert ids == []


def test_client_get_followers_history_success_and_error():
    client = _make_client()
    history_data = [
        {"end_time": "2026-09-01T07:00:00+0000", "value": 5},
        {"end_time": "2026-09-02T07:00:00+0000", "value": 8},
    ]
    client._make_request = lambda *a, **k: {"data": [{"values": history_data}]}
    assert client.get_followers_history() == history_data

    def failing_req(*a, **k):
        raise Exception("demographics error")

    client._make_request = failing_req
    assert client.get_followers_history() == []


# =====================================================================
# Testes de data_loader
# =====================================================================

def test_data_loader_fetch_account_profile_cached_calls_client(monkeypatch):
    client = _make_client()
    client.get_account_profile_info = lambda: {
        "username": "zenit.test",
        "followers_count": 9800,
        "name": "Zenit Test",
    }
    monkeypatch.setattr(data_loader, "get_instagram_client", lambda name: client)

    profile = data_loader.fetch_account_profile_cached.__wrapped__("Cliente Teste")
    assert profile["username"] == "zenit.test"
    assert profile["followers_count"] == 9800


def test_data_loader_fetch_account_profile_cached_handles_client_exception(monkeypatch):
    def broken_client(name):
        raise RuntimeError("Cannot instantiate client")

    monkeypatch.setattr(data_loader, "get_instagram_client", broken_client)

    profile = data_loader.fetch_account_profile_cached.__wrapped__("Cliente Teste")
    assert isinstance(profile, dict)
    assert profile["username"] == "cliente_teste"
    assert profile["followers_count"] == 0


def test_data_loader_fetch_recent_comments_cached_calls_client(monkeypatch):
    client = _make_client()
    client.get_comments_for_media = lambda media_ids, limit=25: [
        {"id": "c1", "text": "Post recente", "like_count": 7}
    ]
    monkeypatch.setattr(data_loader, "get_instagram_client", lambda name: client)

    comments = data_loader.fetch_recent_comments_cached.__wrapped__("Cliente Teste", ["m1"])
    assert len(comments) == 1
    assert comments[0]["text"] == "Post recente"


def test_data_loader_fetch_recent_comments_cached_empty_media_ids(monkeypatch):
    client = _make_client()
    monkeypatch.setattr(data_loader, "get_instagram_client", lambda name: client)

    comments = data_loader.fetch_recent_comments_cached.__wrapped__("Cliente Teste", [])
    assert comments == []


def test_data_loader_fetch_all_historic_comments_with_media_ids(monkeypatch):
    client = _make_client()
    client.get_all_comments_for_account = lambda media_ids: [
        {"id": "c1", "like_count": 5}
    ]
    monkeypatch.setattr(data_loader, "get_instagram_client", lambda name: client)

    comments = data_loader.fetch_all_historic_comments.__wrapped__("Cliente Teste", ["m1"])
    assert len(comments) == 1


def test_data_loader_fetch_all_historic_comments_without_media_ids(monkeypatch):
    client = _make_client()
    client.get_all_media_ids_since_beginning = lambda: ["m_all_1", "m_all_2"]
    client.get_all_comments_for_account = lambda media_ids: [
        {"id": "c_all", "like_count": 10}
    ]
    monkeypatch.setattr(data_loader, "get_instagram_client", lambda name: client)

    comments = data_loader.fetch_all_historic_comments.__wrapped__("Cliente Teste")
    assert len(comments) == 1
    assert comments[0]["id"] == "c_all"


def test_data_loader_fetch_followers_history_cached_transforms_dates(monkeypatch):
    client = _make_client()
    client.get_followers_history = lambda: [
        {"end_time": "2026-09-01T07:00:00+0000", "value": 15},
        {"end_time": "2026-09-02T07:00:00+0000", "value": 22},
    ]
    monkeypatch.setattr(data_loader, "get_instagram_client", lambda name: client)

    history = data_loader.fetch_followers_history_cached.__wrapped__("Cliente Teste")
    assert len(history) == 2
    assert history[0] == {"Data": "01/09", "Novos Seguidores": 15}
    assert history[1] == {"Data": "02/09", "Novos Seguidores": 22}


def test_data_loader_fetch_followers_history_cached_skips_invalid_dates(monkeypatch):
    client = _make_client()
    client.get_followers_history = lambda: [
        {"end_time": "formato-invalido", "value": 10},
        {"end_time": "2026-09-05T07:00:00+0000", "value": 30},
    ]
    monkeypatch.setattr(data_loader, "get_instagram_client", lambda name: client)

    history = data_loader.fetch_followers_history_cached.__wrapped__("Cliente Teste")
    assert len(history) == 1
    assert history[0]["Data"] == "05/09"


def test_data_loader_fetch_account_demographics(monkeypatch):
    client = _make_client()
    expected = SimpleNamespace(followers=SimpleNamespace(cities={"SP": 50}))
    client.get_account_demographics = lambda: expected
    monkeypatch.setattr(data_loader, "get_instagram_client", lambda name: client)

    result = data_loader.fetch_account_demographics.__wrapped__("Cliente Teste")
    assert result == expected


# =====================================================================
# Testes de Agregação de Métricas Orgânicas
# =====================================================================

def test_aggregate_organic_metrics_all_present():
    items = [
        SimpleNamespace(
            total_interactions=20, like_count=15, comments_count=5, organic_views=200
        ),
        SimpleNamespace(
            total_interactions=10, like_count=8, comments_count=2, organic_views=100
        ),
    ]

    totals = organic_ui.aggregate_organic_metrics(items)

    assert totals["total_interactions"].total == 30
    assert totals["total_interactions"].available == 2
    assert totals["total_interactions"].selected == 2

    assert totals["like_count"].total == 23
    assert totals["comments_count"].total == 7
    assert totals["organic_views"].total == 300


def test_aggregate_organic_metrics_partial_coverage():
    items = [
        SimpleNamespace(total_interactions=10, like_count=5, comments_count=None, organic_views=50),
        SimpleNamespace(total_interactions=None, like_count=3, comments_count=1, organic_views=None),
        SimpleNamespace(total_interactions=None, like_count=None, comments_count=None, organic_views=None),
    ]

    totals = organic_ui.aggregate_organic_metrics(items)

    assert totals["total_interactions"].total == 10
    assert totals["total_interactions"].available == 1
    assert totals["total_interactions"].selected == 3

    assert totals["like_count"].total == 8
    assert totals["like_count"].available == 2

    assert totals["comments_count"].total == 1
    assert totals["comments_count"].available == 1

    assert totals["organic_views"].total == 50
    assert totals["organic_views"].available == 1


def test_aggregate_organic_metrics_empty_media_list():
    totals = organic_ui.aggregate_organic_metrics([])
    for metric in totals.values():
        assert metric.total is None
        assert metric.available == 0
        assert metric.selected == 0


def test_aggregate_organic_metrics_all_none_values():
    items = [
        SimpleNamespace(total_interactions=None, like_count=None, comments_count=None, organic_views=None),
        SimpleNamespace(total_interactions=None, like_count=None, comments_count=None, organic_views=None),
    ]

    totals = organic_ui.aggregate_organic_metrics(items)
    for metric in totals.values():
        assert metric.total is None
        assert metric.available == 0
        assert metric.selected == 2


def test_aggregate_organic_metrics_string_and_float_coercion():
    items = [
        SimpleNamespace(total_interactions="25", like_count=10.0, comments_count=5, organic_views=150.0),
    ]

    totals = organic_ui.aggregate_organic_metrics(items)
    assert totals["total_interactions"].total == 25
    assert totals["like_count"].total == 10
    assert totals["comments_count"].total == 5
    assert totals["organic_views"].total == 150
