"""Interface Zenit: testes de regressão de acessibilidade e responsividade.

Esses testes são locais e não consultam Meta Ads ou Instagram.
"""
from pathlib import Path

import pandas as pd

from ui import components


CSS_PATH = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "ui" / "style.css"


def test_layout_preserves_streamlit_sidebar_toggle():
    css = CSS_PATH.read_text(encoding="utf-8")
    header_rules = css.split('[data-testid="stHeader"]', 1)[1].split("}", 1)[0]
    assert "display: none" not in header_rules
    assert "background" in header_rules


def test_layout_has_keyboard_focus_touch_and_mobile_breakpoints():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert ":focus-visible" in css
    assert "min-height: 44px" in css
    assert "@media (max-width: 640px)" in css
    assert "min-width: 0" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition: all" not in css
    assert "opacity: 0.01" not in css


def test_sortable_headers_are_buttons_and_announce_sort_state(monkeypatch):
    markup = []
    monkeypatch.setattr(components.components, "html", lambda html, **kw: markup.append(html))
    df = pd.DataFrame([{"Campanha": "Um anúncio", "Gasto": 15.0, "Link": "https://example.com"}])
    components.render_glass_table(df, link_col="Link", key="tabela-ux", hide_download=True)
    html = markup[0]
    assert '<button type="button" class="sort-button"' in html
    assert 'aria-sort="none"' in html
    assert 'aria-sort", asc ? "ascending" : "descending"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "addEventListener(\"click\"" in html


def test_kpi_card_uses_accessible_text_and_tabular_numbers(monkeypatch):
    markup = []
    monkeypatch.setattr(components.st, "markdown", lambda html, **kw: markup.append(html))
    components.render_metric_card("Conversas", "1.234", "Acumulado", "Número de conversas")
    html = markup[0]
    assert "font-variant-numeric: tabular-nums" in html
    assert "1.234" in html
    assert "Número de conversas" in html
