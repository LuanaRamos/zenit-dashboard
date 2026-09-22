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
                reach=120,
                timestamp="2026-09-01T12:00:00Z",
            )
        ],
        raising=False,
    )
    monkeypatch.setattr(
        data_loader,
        "fetch_account_profile_cached",
        lambda *a, **k: {
            "id": "ig_123",
            "username": "cliente_teste",
            "name": "Cliente Teste",
            "biography": "Biografia da conta de teste",
            "profile_picture_url": "https://example.com/avatar.jpg",
            "followers_count": 2500,
            "follows_count": 350,
            "media_count": 48,
        },
        raising=False,
    )
    monkeypatch.setattr(
        data_loader,
        "fetch_all_historic_comments",
        lambda *a, **k: [
            {
                "id": "c1",
                "text": "Comentário teste histórico",
                "username": "usuario_fa",
                "like_count": 14,
                "timestamp": "2026-09-01T12:00:00Z",
            }
        ],
        raising=False,
    )
    monkeypatch.setattr(
        data_loader,
        "fetch_recent_comments_cached",
        lambda *a, **k: [
            {
                "id": "c1",
                "text": "Comentário teste histórico",
                "username": "usuario_fa",
                "like_count": 14,
                "timestamp": "2026-09-01T12:00:00Z",
            }
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


def test_organic_page_renders_profile_bio_header(monkeypatch):
    organic_app(monkeypatch)
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert not app.error
    visible = "\n".join(text.value for text in app.markdown)
    assert "cliente_teste" in visible
    assert "Biografia da conta de teste" in visible


def test_organic_page_renders_top_posts_ranking_by_reach(monkeypatch):
    organic_app(monkeypatch)
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert not app.error
    visible = "\n".join(text.value for text in app.markdown)
    assert "Top posts" in visible or "alcance" in visible.lower()


def test_organic_page_handles_profile_fetch_failure_gracefully(monkeypatch):
    loader = organic_app(monkeypatch)

    def profile_fails(*a, **k):
        raise RuntimeError("Profile API error")

    monkeypatch.setattr(loader, "fetch_account_profile_cached", profile_fails, raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception


def test_organic_page_with_empty_media_list_renders_empty_notice(monkeypatch):
    loader = organic_app(monkeypatch)
    monkeypatch.setattr(loader, "fetch_organic_media", lambda *a: [], raising=False)
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert not app.error
    assert any("Nenhuma publicação encontrada" in info.value for info in app.info)


def test_organic_page_historic_top_comment_with_comments_data(monkeypatch):
    organic_app(monkeypatch)
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert not app.error
    visible = "\n".join(text.value for text in app.markdown)
    assert "Comentário" in visible or "usuario_fa" in visible or "Comentários" in visible


def test_organic_page_renders_growth_and_followers(monkeypatch):
    loader = organic_app(monkeypatch)
    monkeypatch.setattr(
        loader,
        "fetch_followers_history_cached",
        lambda name: [{"Data": "01/09", "Novos Seguidores": 33}],
        raising=False,
    )
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert not app.error
    visible = "\n".join(text.value for text in app.markdown)
    assert "Seguidores" in visible or "Crescimento" in visible

