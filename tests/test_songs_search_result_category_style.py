"""Songs search results carry their song's own category identity.

The colors/emoji are the canonical ``genre_visual_style`` values already used by
the genre filter pills; the result stays one ordinary button.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from practice_studio import (
    genre_search_result_css,
    genre_search_result_row_key,
    genre_visual_style,
)


def _genre_block(css: str, genre: str) -> str:
    """The base (non-hover) declaration block for one genre's rows."""
    marker = f'browse_search_row_{genre}__"] .stButton > button,'
    start = css.index(marker)
    open_brace = css.index("{", start)
    return css[open_brace : css.index("}", open_brace)]


class TestSearchResultCategoryStyle(unittest.TestCase):
    def test_css_reuses_the_canonical_genre_colors(self) -> None:
        css = genre_search_result_css(["Pop", "Rock", "Jewish"])
        for genre in ("Pop", "Rock", "Jewish"):
            style = genre_visual_style(genre)
            block = _genre_block(css, genre)
            self.assertIn(style["soft"], block)
            self.assertIn(style["accent"], block)
            self.assertIn(style["ink"], block)

    def test_row_key_carries_the_songs_own_genre_not_the_query(self) -> None:
        self.assertEqual(genre_search_result_row_key("Rock", 3), "browse_search_row_Rock__3")
        self.assertNotEqual(
            genre_search_result_row_key("Pop", 0), genre_search_result_row_key("Rock", 0)
        )

    def test_each_genre_is_styled_independently(self) -> None:
        css = genre_search_result_css(["Pop", "Rock"])
        pop = _genre_block(css, "Pop")
        rock = _genre_block(css, "Rock")
        self.assertNotEqual(pop, rock)
        self.assertNotIn(genre_visual_style("Rock")["accent"], pop)

    def test_duplicate_genres_emit_one_block_and_unknown_genre_has_a_fallback(self) -> None:
        css = genre_search_result_css(["Pop", "Pop", "Zydeco"])
        self.assertEqual(css.count('browse_search_row_Pop__"] .stButton > button,'), 1)
        self.assertIn('browse_search_row_Zydeco__"]', css)

    def test_mobile_safe_wrapping_and_no_forced_width(self) -> None:
        css = genre_search_result_css(["Pop"])
        self.assertIn("white-space: normal", css)
        self.assertIn("overflow-wrap: anywhere", css)
        # no fixed content width (borders like border-left-width are fine)
        self.assertNotRegex(css, r"(?<![-\w])(min-|max-)?width:\s*\d+px")

    def test_renderer_keeps_one_button_with_unchanged_wiring(self) -> None:
        src = (Path(__file__).resolve().parent.parent / "streamlit_music_practice_app.py").read_text(
            encoding="utf-8"
        )
        block = src[src.index("def _render_browse_search_results"):]
        block = block[: block.index("if len(filtered) > max_shown")]
        # The result list itself holds exactly one button per row. (The empty
        # state has its own, separate clear-filters button above this list.)
        results_part = block[block.index("with st.container(height") :]
        self.assertEqual(len(re.findall(r"st\.button\(", results_part)), 1)
        for needle in (
            'key=f"browse_search_result::{pk}"',
            "disabled=is_active",
            "on_click=_apply_catalog_pick",
            "args=(pk,)",
            "use_container_width=True",
        ):
            self.assertIn(needle, block)
        # category comes from the record's own genre
        self.assertIn('rec.get("genre")', block)
        self.assertNotIn("query", block.split("with st.container(height")[1])


if __name__ == "__main__":
    unittest.main()
