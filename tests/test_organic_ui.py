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

    def markdown(self, body, **kwargs):
        self.markdowns.append(body)

    def info(self, body, **kwargs):
        self.infos.append(body)

    def caption(self, body, **kwargs):
        self.captions.append(body)

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


def test_top_posts_sort_by_confirmed_organic_interactions_and_show_no_paid_values(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    items = [
        media(id="wide", total_interactions=1, reach=999, like_count=111),
        media(id="engaged", total_interactions=9, reach=1, like_count=222),
        media(id="missing", total_interactions=None, like_count=None),
    ]

    organic_ui.render_top_posts_and_comments(items)

    cards = [body for body in st.markdowns if "glass-card" in body]
    assert "222" in cards[0]
    assert "111" in cards[1]
    assert len(cards) == 2  # Unavailable scores cannot earn a ranking position.
    assert all("Pago" not in body and "Ads" not in body for body in cards)


def test_top_posts_reports_unavailable_ranking_without_known_interactions(monkeypatch):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)

    organic_ui.render_top_posts_and_comments([media(total_interactions=None)])

    assert any("Ranking indisponível" in message for message in st.infos)
    assert not any("glass-card" in body for body in st.markdowns)


def test_historic_comment_copy_describes_consulted_subset_and_escapes_text(
    monkeypatch,
):
    st = StreamlitCapture()
    monkeypatch.setattr(organic_ui, "st", st)
    from ui import data_loader

    monkeypatch.setattr(
        data_loader,
        "fetch_all_historic_comments",
        lambda client_name: [
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
