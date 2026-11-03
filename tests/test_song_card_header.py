"""Song card header (v12): source identity + style treatment from the app's genre definitions."""
from __future__ import annotations

import pytest

from song_card_header import header_source, header_theme, song_card_header_html


@pytest.mark.parametrize(
    "raw, want",
    [
        ("Catalog Song", "catalog"),
        ("catalog_song", "catalog"),
        ("", "catalog"),
        ("Custom progression", "custom"),
        ("custom_progression", "custom"),
        ("Composition", "composition"),
        ("composition_song", "composition"),
    ],
)
def test_source_spellings_normalize(raw: str, want: str) -> None:
    assert header_source(raw) == want


@pytest.mark.parametrize(
    "style, art",
    [
        ("Jazz", "sax"),
        ("Jazz Standard", "sax"),
        ("Blues", "guitar"),
        ("Soul", "vinyl"),
        ("Funk", "bars"),
        ("Pop", "mic"),
        ("Country", "guitar"),
        ("Bossa Nova", "guitar"),
        ("Rock", "guitar"),
    ],
)
def test_catalog_style_artwork(style: str, art: str) -> None:
    t = header_theme("Catalog Song", style)
    assert t["art"] == art
    assert "#1e3a8a" in t["background"]  # Catalog blue base


def test_unknown_style_gets_a_neutral_header() -> None:
    t = header_theme("Catalog Song", "Polka-Ambient")
    assert t["art"] == "vinyl"
    assert t["source"] == "catalog"


def test_custom_keeps_green_base_and_yellow_accent() -> None:
    t = header_theme("Custom progression", "Blues")
    assert "#047857" in t["background"] and "rgba(250,204,21" in t["background"]
    assert t["art"] == "guitar" and t["art_color"] == "#fde047"
    assert t["source_label"] == "Custom progression"


def test_composition_is_black_and_gold_with_a_quill() -> None:
    t = header_theme("Composition", "Pop")
    assert "#020617" in t["background"]
    assert t["art"] == "quill" and t["art_color"] == "#e9c46a"
    html = song_card_header_html(source="Composition", style="Pop", title="My Tune", artist="Me")
    assert 'class="ui-sch-staff"' in html
    assert ">Pop<" in html  # the composition's own style still shows as a chip


def test_html_escapes_text_and_shows_status_and_favorite() -> None:
    html = song_card_header_html(
        source="Catalog Song", style="Jazz", title="<Wave>", artist="A & B", favorite=True
    )
    assert "&lt;Wave&gt;" in html and "A &amp; B" in html
    assert "Now loaded for practice" in html
    assert 'class="ui-sch-fav"' in html
    assert 'data-style="Jazz"' in html and "ui-sch-art-sax" in html
    assert "container-type:inline-size" in html  # responsive by card width


def test_no_favorite_no_artist() -> None:
    html = song_card_header_html(source="Catalog Song", style="Soul", title="T")
    assert 'class="ui-sch-fav"' not in html and 'class="ui-sch-artist"' not in html


def test_custom_bars_only_on_custom() -> None:
    html_c = song_card_header_html(source="custom", style="Blues", title="T", bars=["A7", "D7", "A7", "E7", "B7"])
    assert html_c.count('class="ui-sch-bar"') == 4
    html_k = song_card_header_html(source="catalog", style="Blues", title="T", bars=["A7"])
    assert 'class="ui-sch-bar"' not in html_k
