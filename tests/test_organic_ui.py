from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "dashboard"))

from ui import organic_components as organic_ui  # noqa: E402


def media(**overrides):
    values = {
        "id": "post-1",
        "timestamp": "2026-09-01T12:00:00+0000",
        "media_type": "IMAGE",
        "media_product_type": "FEED",
        "caption": "Legenda",
        "thumbnail_url": "https://example.com/thumb.jpg",
        "media_url": "https://example.com/media.jpg",
        "permalink": "https://instagram.com/p/post-1",
        "total_interactions": None,
        "like_count": None,
        "comments_count": None,
        "organic_views": None,
        "reach": None,
        "saved": None,
        "shares": None,
        "profile_visits": None,
        "ig_reels_video_view_total_time": None,
        "ig_reels_avg_watch_time": None,
        "paid_reach": 0,
        "paid_impressions": 0,
        "paid_views": 0,
        "paid_likes": 0,
        "paid_comments": 0,
        "paid_shares": 0,
        "paid_saved": 0,
        "paid_spend": 0.0,
        "paid_ad_count": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StreamlitCapture:
    def __init__(self, selected_type="Todos"):
        self.selected_type = selected_type
        self.markdowns = []
        self.infos = []
        self.captions = []
        self.downloads = []
        self.expanders = []
        self.warnings = []
        self.errors = []

    def markdown(self, body, **kwargs):
        self.markdowns.append(body)

    def info(self, body, **kwargs):
        self.infos.append(body)

    def caption(self, body, **kwargs):
        self.captions.append(body)

    def warning(self, body, **kwargs):
        self.warnings.append(body)

    def error(self, body, **kwargs):
        self.errors.append(body)

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [nullcontext() for _ in range(count)]

    def selectbox(self, *args, **kwargs):
        return self.selected_type

    def download_button(self, *args, **kwargs):
        self.downloads.append(kwargs)

    def expander(self, *args, **kwargs):
        self.expanders.append((args, kwargs))
        return nullcontext()

    def write(self, *args, **kwargs):
        pass

    def empty(self):
        return nullcontext()

    def plotly_chart(self, *args, **kwargs):
        pass


def test_organic_aggregate_sums_only_available_values_and_reports_coverage():
    items = [
        media(total_interactions=10, like_count=4, comments_count=2),
        media(total_interactions=5, like_count=None, comments_count=1),
        media(total_interactions=None, like_count=3, comments_count=None),
    ]

    totals = organic_ui.aggregate_organic_metrics(items)

    assert totals["total_interactions"].total == 15
    assert totals["total_interactions"].available == 2
    assert totals["like_count"].total == 7
    assert totals["like_count"].available == 2
    assert totals["comments_count"].total == 3
    assert totals["organic_views"].total is None
    assert totals["organic_views"].available == 0
    assert all(metric.selected == 3 for metric in totals.values())


def test_metric_cards_show_nd_for_missing_and_partial_coverage(monkeypatch):
    st = StreamlitCapture()
    cards = []
    monkeypatch.setattr(organic_ui, "st", st)
    monkeypatch.setattr(
        organic_ui,
        "render_metric_card",
        lambda label, value, subtext=None, help_text=None: cards.append(
            (label, value, subtext, help_text)
        ),
    )
    items = [
        media(total_interactions=10, like_count=4, comments_count=2),
        media(total_interactions=5, like_count=None, comments_count=1),
        media(total_interactions=None, like_count=3, comments_count=None),
    ]

    organic_ui.render_organic_metrics_cards(items)

    assert [(label, value) for label, value, _, _ in cards] == [
        ("Interações orgânicas", "15"),
        ("Curtidas orgânicas", "7"),
        ("Comentários orgânicos", "3"),
        ("Visualizações orgânicas", "N/D"),
    ]
    assert cards[0][2] == "Cobertura: 2 de 3 publicações"
    assert cards[3][2] == "Sem dados nos Media Insights"
    assert any("data de publicação" in caption for caption in st.captions)


def test_posts_table_contains_only_confirmed_organic_columns(monkeypatch):
    st = StreamlitCapture()
    rendered = []
    monkeypatch.setattr(organic_ui, "st", st)
    monkeypatch.setattr(
        organic_ui,
        "render_glass_table",
        lambda dataframe, **kwargs: rendered.append((dataframe.copy(), kwargs)),
    )

    organic_ui.render_posts_table(
        [
            media(
                total_interactions=12,
                like_count=7,
                comments_count=2,
                organic_views=100,
                paid_reach=9999,
                paid_spend=123.45,
            )
        ]
    )

    assert len(rendered) == 1
    dataframe, kwargs = rendered[0]
    assert list(dataframe.columns) == [
        "Data e Hora",
        "Tipo",
        "Interações orgânicas",
        "Curtidas orgânicas",
        "Comentários orgânicos",
        "Visualizações orgânicas",
        "Link",
    ]
    assert dataframe.iloc[0]["Interações orgânicas"] == 12
    assert not any("Pago" in column or "Ads" in column for column in dataframe.columns)
    assert kwargs["link_col"] == "Link"


def test_posts_table_empty_filter_is_handled_without_dataframe_key_error(monkeypatch):
    st = StreamlitCapture(selected_type="Reels")
    rendered = []
    monkeypatch.setattr(organic_ui, "st", st)
    monkeypatch.setattr(
        organic_ui, "render_glass_table", lambda dataframe, **kwargs: rendered.append(dataframe)
    )

    organic_ui.render_posts_table([media(media_type="IMAGE")])

    assert rendered == []
    assert any("filtro" in message.lower() for message in st.infos)


def test_posts_table_keeps_neutral_media_insights_in_collapsed_details(monkeypatch):
    st = StreamlitCapture()
    rendered = []
    monkeypatch.setattr(organic_ui, "st", st)
    monkeypatch.setattr(
        organic_ui,
        "render_glass_table",
        lambda dataframe, **kwargs: rendered.append((dataframe.copy(), kwargs)),
    )

    organic_ui.render_posts_table(
        [media(reach=120, saved=8, shares=3, total_interactions=12)]
    )

    assert len(rendered) == 2
    details, _ = rendered[1]
    assert list(details.columns) == [
        "Data e Hora",
        "Tipo",
        "Alcance (Media Insights)",
        "Salvamentos (Media Insights)",
        "Compartilhamentos (Media Insights)",
        "Link",
    ]
    assert details.iloc[0]["Alcance (Media Insights)"] == 120
    assert st.expanders == [
        (("Outros detalhes do Media Insights",), {"expanded": False})
    ]
    assert any("exclusivamente orgânicas" in caption for caption in st.captions)


def test_paid_comparison_uses_raw_non_equivalent_ads_metrics_and_has_no_cards(monkeypatch):
    st = StreamlitCapture()
    rendered = []
    cards = []
    monkeypatch.setattr(organic_ui, "st", st)
    monkeypatch.setattr(
        organic_ui,
        "render_glass_table",
        lambda dataframe, **kwargs: rendered.append((dataframe.copy(), kwargs)),
    )
    monkeypatch.setattr(organic_ui, "render_metric_card", lambda *args, **kwargs: cards.append(args))
    mapped = media(
        id="mapped",
        total_interactions=20,
        like_count=11,
        comments_count=3,
        organic_views=500,
        paid_reach=800,
        paid_views=900,
        paid_likes=40,
        paid_reactions=45,
        paid_comments=5,
        paid_shares=4,
        paid_saved=2,
        paid_spend=70.5,
        paid_ad_count=2,
    )
    unmapped = media(id="unmapped", total_interactions=100)

    organic_ui.render_paid_comparison([mapped, unmapped])

    assert cards == []
    assert len(rendered) == 1
    dataframe, _ = rendered[0]
    assert len(dataframe) == 1
    assert dataframe.iloc[0]["Curtidas líquidas pagas (Ads)"] == 40
    assert dataframe.iloc[0]["Reações pagas (Ads)"] == 45
    assert dataframe.iloc[0]["Comentários pagos (Ads)"] == 5
    assert "Interações pagas" not in dataframe.columns
    assert "Visualizações orgânicas (Media Insights)" in dataframe.columns
    assert "Reproduções pagas de 3 s (Ads)" in dataframe.columns
    assert "Soma do alcance pago por publicação" in dataframe.columns
    assert "Total combinado" not in dataframe.columns
    assert any("períodos" in message and "escopos" in message for message in st.infos)
    assert any("3 segundos" in message for message in st.infos)


def test_top_posts_sorts_by_reach_as_primary_metric(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [
        media(id="low_reach_high_int", reach=200, total_interactions=99, like_count=10),
        media(id="high_reach_low_int", reach=1500, total_interactions=5, like_count=20),
        media(id="mid_reach", reach=800, total_interactions=30, like_count=15),
    ]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert len(cards) == 3
    # First post must be the one with reach=1500
    assert "1.500" in cards[0] or "1500" in cards[0]
    # Second post must be the one with reach=800
    assert "800" in cards[1]
    # Third post must be the one with reach=200
    assert "200" in cards[2]
    assert all("Pago" not in body and "Ads" not in body for body in cards)


def test_top_posts_falls_back_to_total_interactions_when_reach_is_none(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [
        media(id="no_reach_low_int", reach=None, total_interactions=12, like_count=5),
        media(id="no_reach_high_int", reach=None, total_interactions=85, like_count=40),
    ]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert len(cards) == 2
    assert "85" in cards[0]
    assert "12" in cards[1]


def test_top_posts_reach_takes_precedence_over_interactions_only(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [
        media(id="has_reach", reach=50, total_interactions=2, like_count=1),
        media(id="interactions_only", reach=None, total_interactions=999, like_count=500),
    ]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert len(cards) == 2
    assert "50" in cards[0]
    assert "999" in cards[1]


def test_top_posts_handles_reach_tie_using_interactions_or_likes(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [
        media(id="tie_low", reach=500, total_interactions=10, like_count=100),
        media(id="tie_high", reach=500, total_interactions=50, like_count=200),
    ]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert len(cards) == 2
    assert "200" in cards[0]
    assert "100" in cards[1]


def test_top_posts_excludes_posts_with_neither_reach_nor_interactions(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [
        media(id="valid", reach=100, total_interactions=10),
        media(id="invalid_empty", reach=None, total_interactions=None, like_count=None),
    ]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert len(cards) == 1
    assert "100" in cards[0]


def test_top_posts_reports_unavailable_ranking_without_known_reach_or_interactions(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)

    organic_ui.render_top_posts_and_comments([media(reach=None, total_interactions=None)])

    assert any("Ranking indisponível" in message for message in st.infos)
    assert not any("glass-card" in body for body in st.markdowns)


def test_top_posts_empty_media_list_renders_nothing_cleanly(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)

    organic_ui.render_top_posts_and_comments([])

    assert not any("glass-card" in body for body in st.markdowns)
    assert not any("Ranking indisponível" in message for message in st.infos)


def test_top_posts_limits_to_top_three_posts(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [media(id=f"p{i}", reach=i * 100, total_interactions=i) for i in range(1, 6)]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert len(cards) == 3
    assert "500" in cards[0]
    assert "400" in cards[1]
    assert "300" in cards[2]


def test_top_posts_renders_video_badge_for_reels_and_video(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [
        media(id="v1", media_type="VIDEO", reach=500, total_interactions=10),
        media(id="img1", media_type="IMAGE", reach=400, total_interactions=10),
    ]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert "Vídeo" in cards[0]
    assert "Vídeo" not in cards[1]


def test_top_posts_renders_preview_fallback_when_no_thumbnails(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [media(thumbnail_url="", media_url="", reach=100, total_interactions=5)]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert any("Sem prévia" in card for card in cards)


def test_top_posts_escapes_xss_in_permalinks_and_thumbnails(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    xss_url = 'https://instagram.com/p/test"><script>alert(1)</script>'
    items = [media(permalink=xss_url, thumbnail_url=xss_url, reach=100, total_interactions=5)]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert "<script>" not in cards[0]
    assert "&lt;script&gt;" in cards[0] or "&quot;&gt;&lt;script&gt;" in cards[0]


def test_top_posts_card_displays_reach_when_available(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [media(reach=8500, total_interactions=40, like_count=30, comments_count=10)]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert "8.500" in cards[0] or "8500" in cards[0]
    assert "alcance" in cards[0].lower()


def test_profile_bio_header_renders_complete_data(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    profile = {
        "username": "zenit.growth",
        "name": "Zenit Growth Intelligence",
        "biography": "Impulsionando marcas no digital 🚀\nConsultoria de Dados",
        "profile_picture_url": "https://example.com/avatar.jpg",
        "followers_count": 12500,
        "follows_count": 450,
        "media_count": 89,
    }

    organic_ui.render_profile_bio_header(profile)

    output = "\n".join(str(m) for m in st.markdowns)
    assert "zenit.growth" in output
    assert "Zenit Growth Intelligence" in output
    assert "Impulsionando marcas no digital" in output
    assert "12.500" in output or "12500" in output
    assert "450" in output
    assert "89" in output
    assert "avatar.jpg" in output


def test_profile_bio_header_renders_partial_and_missing_data_gracefully(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    partial_profile = {
        "username": "zenit_only",
        "followers_count": None,
    }

    # Deve executar perfeitamente sem levantar exceção por chaves ausentes
    organic_ui.render_profile_bio_header(partial_profile)

    output = "\n".join(str(m) for m in st.markdowns)
    assert "zenit_only" in output


def test_profile_bio_header_escapes_xss_in_name_username_and_bio(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    malicious = {
        "username": "<script>alert('user')</script>",
        "name": "<b onmouseover=evil()>Name</b>",
        "biography": "<img src=x onerror=alert('bio')>",
        "followers_count": 100,
        "profile_picture_url": 'https://example.com/pic.jpg"><script>evil()</script>',
    }

    organic_ui.render_profile_bio_header(malicious)

    output = "\n".join(str(m) for m in st.markdowns)
    assert "<script>alert" not in output
    assert "<img src=x" not in output
    assert "&lt;script&gt;" in output
    assert "&lt;img src=x" in output


def test_profile_bio_header_handles_none_or_empty_dict(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)

    organic_ui.render_profile_bio_header(None)
    organic_ui.render_profile_bio_header({})

    # Deve executar suavemente sem erros


def test_profile_bio_header_formats_large_numbers_with_thousand_separators(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    profile = {
        "username": "big_account",
        "followers_count": 1500000,
        "follows_count": 3200,
        "media_count": 1200,
    }

    organic_ui.render_profile_bio_header(profile)

    output = "\n".join(str(m) for m in st.markdowns)
    assert "1.500.000" in output or "1500000" in output
    assert "3.200" in output or "3200" in output


def test_historic_comment_copy_describes_consulted_subset_and_escapes_text(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    from ui import data_loader

    monkeypatch.setattr(
        data_loader,
        "fetch_all_historic_comments",
        lambda *a, **k: [
            {
                "text": "olá, <script>alert(1)</script>",
                "username": "<admin>",
                "like_count": 7,
                "timestamp": "2026-09-01T10:00:00+0000",
            }
        ],
    )

    organic_ui.render_historic_top_comment("cliente")

    output = "\n".join(str(item) for item in st.markdowns)
    assert "Comentário com mais curtidas entre os consultados" in output
    assert "olá, &lt;script&gt;alert(1)&lt;/script&gt;" in output
    assert "&lt;admin&gt;" in output
    assert "Recorde da Conta" not in output
    assert st.downloads[0]["label"] == "📥 Baixar comentários consultados (CSV)"


def test_historic_comment_with_media_list_parameter(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    from ui import data_loader

    called_args = []

    def mock_fetch(client_name, media_ids=None):
        called_args.append((client_name, media_ids))
        return [
            {
                "text": "Comentário no post recente",
                "username": "usuario_ativo",
                "like_count": 19,
                "timestamp": "2026-09-01T12:00:00Z",
            }
        ]

    monkeypatch.setattr(data_loader, "fetch_all_historic_comments", mock_fetch)

    items = [media(id="post_recent_1")]
    organic_ui.render_historic_top_comment("cliente", items)

    output = "\n".join(str(item) for item in st.markdowns)
    assert "Comentário no post recente" in output
    assert "usuario_ativo" in output


def test_historic_comment_empty_comments_renders_nothing(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    from ui import data_loader

    monkeypatch.setattr(data_loader, "fetch_all_historic_comments", lambda *a, **k: [])

    organic_ui.render_historic_top_comment("cliente")

    assert not any("glass-card" in body for body in st.markdowns)
    assert len(st.downloads) == 0


def test_historic_comment_handles_zero_likes_and_missing_like_count(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    from ui import data_loader

    monkeypatch.setattr(
        data_loader,
        "fetch_all_historic_comments",
        lambda *a, **k: [
            {"text": "Primeiro comentário", "username": "user1", "like_count": None},
            {"text": "Segundo comentário", "username": "user2", "like_count": 0},
        ],
    )

    organic_ui.render_historic_top_comment("cliente")

    output = "\n".join(str(item) for item in st.markdowns)
    assert "Primeiro comentário" in output or "Segundo comentário" in output
    assert len(st.downloads) == 1


def test_historic_comment_handles_loader_exception_gracefully(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    from ui import data_loader

    def broken(*a, **k):
        raise RuntimeError("API timeout loading comments")

    monkeypatch.setattr(data_loader, "fetch_all_historic_comments", broken)

    # Não deve subir exceção
    organic_ui.render_historic_top_comment("cliente")
    assert not any("glass-card" in body for body in st.markdowns)


def test_historic_comment_csv_download_content_and_headers(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    from ui import data_loader

    monkeypatch.setattr(
        data_loader,
        "fetch_all_historic_comments",
        lambda *a, **k: [
            {
                "text": "Conteúdo teste para exportação",
                "username": "autor_teste",
                "like_count": 3,
                "timestamp": "2026-09-01T12:00:00+0000",
            }
        ],
    )

    organic_ui.render_historic_top_comment("cliente")

    assert len(st.downloads) == 1
    download = st.downloads[0]
    assert download["label"] == "📥 Baixar comentários consultados (CSV)"
    assert download["file_name"] == "comentarios_consultados_cliente.csv"
    csv_text = download["data"].decode("utf-8")
    assert "Conteúdo teste para exportação" in csv_text
    assert "autor_teste" in csv_text


def test_render_followers_timeline_empty_returns_info(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)

    organic_ui.render_followers_timeline([])
    assert any("não está disponível" in str(msg) for msg in st.infos)


def test_render_followers_timeline_with_data_renders_peak_and_chart(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)

    history = [
        {"Data": "01/09", "Novos Seguidores": 12},
        {"Data": "02/09", "Novos Seguidores": 45},
        {"Data": "03/09", "Novos Seguidores": 18},
    ]

    organic_ui.render_followers_timeline(history)
    output = "\n".join(str(m) for m in st.markdowns)
    assert "+45" in output
    assert "02/09" in output
    assert "Evolução de Seguidores" in output

