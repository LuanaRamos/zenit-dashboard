"""Isolated fixtures: the test suite never uses live Meta credentials."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "dashboard"))
os.environ["META_MASTER_TOKEN"] = "test-token-not-valid"
os.environ["CLIENTS_JSON"] = (
    '[{"name":"Cliente Teste","ad_account_id":"act_test","page_id":"page_test"}]'
)
os.environ.pop("SENTRY_DSN", None)


@pytest.fixture(autouse=True)
def no_live_requests(monkeypatch):
    import requests

    def blocked(*args, **kwargs):
        raise AssertionError("Tests must provide a fixture instead of calling Meta")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
