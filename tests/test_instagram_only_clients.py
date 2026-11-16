"""Regressões de clientes com somente Instagram, sem conta Meta Ads.

Nenhum teste chama a API real. A conta de anúncios é opcional por cliente;
page_id e acesso da Meta continuam necessários para o Instagram.
"""
import json
from types import SimpleNamespace

import pytest

from core.config import Settings
from ui.layouts import available_modules_for_client
from ui.data_loader import get_api_client


def _settings(clients):
    return Settings(
        META_MASTER_TOKEN="dummy-global-test-token",
        CLIENTS_JSON=json.dumps(clients),
    )


def test_mixed_clients_accept_one_empty_ad_account_without_hiding_other_clients():
    clients = _settings([
        {"name": "VIP Pilates", "ad_account_id": "1395506237791220", "page_id": "404192349440178"},
        {"name": "Pousada dos Mundos", "ad_account_id": "1551709412804972", "page_id": "809464095591694"},
        {"name": "Bruno Dantas Advocacia", "ad_account_id": "", "page_id": "108012941877296", "token": ""},
    ]).get_clients()
    assert len(clients) == 3
    assert clients[2].name == "Bruno Dantas Advocacia"
    assert clients[2].has_ads is False
    assert clients[0].has_ads is True


def test_clients_may_omit_ads_field_when_only_using_instagram():
    client = _settings([
        {"name": "Bruno Dantas Advocacia", "page_id": "108012941877296"},
    ]).get_clients()[0]
    assert client.ad_account_id == ""
    assert client.has_ads is False


def test_two_organic_only_clients_are_not_considered_duplicate_ad_accounts():
    clients = _settings([
        {"name": "Cliente 1", "ad_account_id": "", "page_id": "page1"},
        {"name": "Cliente 2", "ad_account_id": "", "page_id": "page2"},
    ]).get_clients()
    assert len(clients) == 2


def test_organic_only_clients_have_no_ads_navigation():
    client = _settings([
        {"name": "Bruno Dantas Advocacia", "ad_account_id": "", "page_id": "page1"}
    ]).get_clients()[0]
    assert available_modules_for_client(client) == ["Orgânico (Instagram)"]


def test_clients_with_ads_keep_both_sections():
    client = _settings([
        {"name": "VIP Pilates", "ad_account_id": "123", "page_id": "page1"}
    ]).get_clients()[0]
    assert available_modules_for_client(client) == [
        "Visão Geral (Ads)", "Orgânico (Instagram)"
    ]


def test_ads_client_refuses_an_organic_only_client(monkeypatch):
    from ui import data_loader

    client = _settings([
        {"name": "Bruno Dantas Advocacia", "ad_account_id": "", "page_id": "page1"}
    ]).get_clients()[0]
    monkeypatch.setattr(
        data_loader, "settings", SimpleNamespace(get_clients=lambda: [client])
    )
    with pytest.raises(ValueError, match="sem conta de anúncios"):
        get_api_client("Bruno Dantas Advocacia")
