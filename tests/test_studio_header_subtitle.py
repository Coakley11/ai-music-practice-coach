"""The page header's description must be readable in full, with real emphasis.

Two separate defects on the Songs page card:

1. the header is raw HTML, so ``**Active Song**`` reached the musician as literal
   asterisks instead of bold;
2. a phone-only ``-webkit-line-clamp: 2`` cut the sentence off mid-way, around
   "Karaoke Performance Setlist".
"""

from __future__ import annotations

import re

from app_ui import (
    _decorative_studio_header_css,
    _mobile_m5_fold_density_css,
    header_subtitle_html,
)

SONGS_SUBTITLE = (
    "Pick songs in **Active Song**, use **Edit Song Chart** for chords, "
    "or build your **Karaoke Performance Setlist** below."
)


# --- emphasis -----------------------------------------------------------------

def test_the_songs_description_renders_bold_not_asterisks() -> None:
    out = header_subtitle_html(SONGS_SUBTITLE)
    assert "**" not in out
    assert "<strong>Active Song</strong>" in out
    assert "<strong>Edit Song Chart</strong>" in out
    assert "<strong>Karaoke Performance Setlist</strong>" in out


def test_the_whole_sentence_survives() -> None:
    """Nothing may be dropped - the end of the line is the part that was missing."""
    out = header_subtitle_html(SONGS_SUBTITLE)
    assert out.startswith("Pick songs in ")
    assert out.endswith(" below.")
    assert re.sub(r"</?strong>", "", out) == SONGS_SUBTITLE.replace("**", "")


def test_plain_text_is_unchanged() -> None:
    assert header_subtitle_html("Choose your active song.") == "Choose your active song."
    assert header_subtitle_html("") == ""
    assert header_subtitle_html(None) == ""


def test_markup_in_the_text_is_escaped() -> None:
    """Only the <strong> this helper adds may reach the page."""
    out = header_subtitle_html("<script>alert(1)</script> and **bold**")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert out.endswith("<strong>bold</strong>")


def test_an_unpaired_marker_is_shown_as_written() -> None:
    """Better a visible asterisk than a guess that swallows the rest of the line."""
    out = header_subtitle_html("Pick **Active Song and keep going")
    assert out == "Pick **Active Song and keep going"


def test_the_header_renderer_uses_the_helper() -> None:
    import inspect

    from app_ui import compact_page_title

    src = inspect.getsource(compact_page_title)
    assert "header_subtitle_html(subtitle)" in src
    assert "html.escape(subtitle)" not in src


# --- no clipping --------------------------------------------------------------

def _sub_rules(css: str) -> list[str]:
    """Every declaration block that targets the header subtitle."""
    return [
        block
        for block in re.findall(
            r"\.ui-studio-script-header-sub\s*\{\{?(.*?)\}\}?", css, re.DOTALL
        )
    ]


def test_the_phone_css_no_longer_clamps_the_description() -> None:
    css = _mobile_m5_fold_density_css()
    blocks = _sub_rules(css)
    assert blocks, "expected the phone rules to still style the subtitle"
    for block in blocks:
        assert "line-clamp" not in block, block
        assert "-webkit-box" not in block, block
        assert "overflow: hidden" not in block, block
        assert "max-height" not in block, block


def test_no_stylesheet_clamps_or_caps_the_description() -> None:
    for css in (_mobile_m5_fold_density_css(), _decorative_studio_header_css()):
        for block in _sub_rules(css):
            assert "line-clamp" not in block, block
            assert "max-height" not in block, block


def test_long_text_wraps_instead_of_scrolling_sideways() -> None:
    blocks = _sub_rules(_mobile_m5_fold_density_css()) + _sub_rules(_decorative_studio_header_css())
    assert any("overflow-wrap: break-word" in block for block in blocks)


def test_the_text_column_can_shrink_on_a_narrow_phone() -> None:
    """A flex child without ``min-width: 0`` pushes the card wider than the screen."""
    css = _decorative_studio_header_css()
    assert re.search(
        r"\.ui-studio-script-header\s*>\s*div\s*\{[^}]*min-width:\s*0", css, re.DOTALL
    )
