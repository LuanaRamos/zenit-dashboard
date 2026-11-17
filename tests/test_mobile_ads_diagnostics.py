"""Regressões de produção: erro Ads legível e layout estreito no celular."""
from pathlib import Path

import pytest

from api.exceptions import MetaAPIError
from ui import ads_diagnostics, organic_components


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "src/dashboard/ui/style.css"
APP = ROOT / "src/dashboard/app.py"
LAYOUT = ROOT / "src/dashboard/ui/layouts.py"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("(#200) Permissions error", "permission"),
        ("Error validating access token: (#190)", "auth"),
        ("Unsupported get request. Object with ID does not exist", "access"),
        ("Unknown field in query", "fields"),
        ("Connection timed out", "network"),
        ("Something else", "unknown"),
    ],
)
def test_safe_ads_error_classification(message, expected):
    result = ads_diagnostics.classify_ads_error(MetaAPIError(message))
    assert result["code"] == expected
    assert "title" in result and "action" in result
    assert "#200" not in result["title"]


def test_ads_diagnostics_never_discloses_access_token():
    result = ads_diagnostics.classify_ads_error(
        MetaAPIError("Error validating access token SECRET_ABC123")
    )
    assert "SECRET_ABC123" not in str(result)


def test_ads_client_can_probe_account_without_changing_campaigns():
    from api.meta_client import MetaAdsClient

    client = object.__new__(MetaAdsClient)
    client.ad_account_id = "act_fixture"
    requests = []
    client._make_request = lambda endpoint, params: (
        requests.append((endpoint, dict(params)))
        or {"id": "act_fixture", "account_status": 1}
    )
    outcome = client.probe_ads_account()
    assert outcome["ok"] is True
    assert requests == [
        ("act_fixture", {"fields": "id,name,account_status"})
    ]


def test_mobile_layout_wraps_columns_at_main_container_width():
    css = STYLE.read_text(encoding="utf-8")
    assert "container-type: inline-size" in css
    assert "@container" in css
    assert 'data-testid="stHorizontalBlock"' in css
    assert "flex-wrap: wrap" in css
    assert ".zenit-post-card" in css
    assert "minmax(0, 1fr)" in css


def test_version_marker_is_visible_in_sidebar():
    c = LAYOUT.read_text(encoding="utf-8")
    assert "UI_BUILD_ID" in c
    assert "build" in c.lower()


def test_ads_errors_have_diagnostic_action_not_only_global_fallback():
    c = APP.read_text(encoding="utf-8")
    assert "render_ads_diagnostic(" in c
    assert "Testar acesso à conta" in c


def test_compact_post_metrics_keep_coverage_in_single_diagnostic_section(monkeypatch):
    class Capture:
        def __init__(self):
            self.columns_calls = []
            self.metric_cards = []
            self.expanders = []
            self.captions = []
        def markdown(self, *a, **kw): pass
        def columns(self, count):
            from contextlib import nullcontext
            self.columns_calls.append(count)
            return [nullcontext() for _ in range(count)]
        def expander(self, label, **kw):
            from contextlib import nullcontext
            self.expanders.append(label)
            return nullcontext()
        def caption(self, text): self.captions.append(text)
        def dataframe(self, *a, **kw): pass

    cap = Capture()
    monkeypatch.setattr(organic_components, "st", cap)
    monkeypatch.setattr(
        organic_components, "render_metric_card",
        lambda label, value, subtext=None, help_text=None:
            cap.metric_cards.append((label, value, subtext, help_text)),
    )
    media = [
        {"like_count": 10, "comments_count": 2, "shares": 1, "saved": 0, "organic_views": 100},
        {"like_count": None, "comments_count": 1, "shares": 1, "saved": 0, "organic_views": 50},
    ]
    organic_components.render_organic_metrics_cards(media)
    assert cap.columns_calls == [2, 2, 1]
    assert any("Cobertura" in label for label in cap.expanders)
    assert all("Cobertura:" not in (subtitle or "") for *_, subtitle, __ in cap.metric_cards)
    assert [x[1] for x in cap.metric_cards] == ["10", "3", "2", "0", "150"]
