from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src/dashboard/app.py"


def organic_app(monkeypatch):
    from core.config import settings
    from schemas.instagram import InstagramMedia
    from ui import data_loader, layouts

    monkeypatch.setattr(
        layouts,
        "render_sidebar",
        lambda: ("Orgânico (Instagram)", "last_30d", None, settings.get_clients()[0]),
    )
    monkeypatch.setattr(
        data_loader,
        "fetch_organic_media",
        lambda *a: [
            InstagramMedia(
                id="post1",
                media_type="IMAGE",
                like_count=7,
                comments_count=3,
                total_interactions=10,
                organic_views=100,
                timestamp="2026-09-01T12:00:00Z",
            )
        ],
        raising=False,
    )
    return data_loader


def test_organic_page_does_not_request_ads_by_default(monkeypatch):
    loader = organic_app(monkeypatch)
    calls = []

    def ads_unavailable(*args):
        calls.append(args)
        raise RuntimeError("Ads permission denied")

    monkeypatch.setattr(loader, "enrich_media_with_ads", ads_unavailable, raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert not app.error
    assert calls == []
    assert app.checkbox(key="compare_ads_Cliente Teste").value is False
    assert any("orgânic" in text.value.lower() for text in app.markdown)


def test_ads_comparison_failure_keeps_organic_results(monkeypatch):
    loader = organic_app(monkeypatch)

    def ads_unavailable(*args):
        raise RuntimeError("Ads permission denied")

    monkeypatch.setattr(loader, "enrich_media_with_ads", ads_unavailable, raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=15)
    before = [text.value for text in app.markdown if "kpi-card" in text.value]
    assert before
    app.checkbox(key="compare_ads_Cliente Teste").check().run()
    assert not app.exception
    assert not app.error
    assert any("indisponível" in warning.value for warning in app.warning)
    assert [text.value for text in app.markdown if "kpi-card" in text.value] == before
