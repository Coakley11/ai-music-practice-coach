"""Composition -> Backing must keep the composition's saved style (e.g. Pop)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock


def _active_composition(style: str, *, title: str = "My Composition", groove: str = "Auto") -> tuple[dict, MagicMock]:
    from composition_songs_bridge import (
        commit_composition_active_song,
        ensure_generic_composition_document,
        set_composition_source,
    )

    ss: dict = {"instrument": "Piano", "composer_saved_compositions": {}, "display_key": "C"}
    st = MagicMock()
    st.session_state = ss
    set_composition_source(ss)
    doc = ensure_generic_composition_document(ss)
    doc["title"] = title
    doc.setdefault("global", {})["progression_style"] = style
    doc["global"]["groove_style"] = groove
    commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
    return ss, st


class TestCompositionBackingStyle(unittest.TestCase):
    def test_pop_composition_is_not_replaced_by_auto(self) -> None:
        from backing_context import build_composition_song_context

        ss, _ = _active_composition("Pop")
        ctx = build_composition_song_context(ss)
        self.assertEqual(ctx.style, "Pop")

    def test_other_saved_styles_survive(self) -> None:
        from backing_context import build_composition_song_context

        for style in ("Rock", "Blues", "Bossa Nova", "Jazz Swing"):
            with self.subTest(style=style):
                ss, _ = _active_composition(style)
                self.assertEqual(build_composition_song_context(ss).style, style)

    def test_named_composition_keeps_style_too(self) -> None:
        from backing_context import build_composition_song_context

        ss, _ = _active_composition("Rock", title="Sunrise")
        self.assertEqual(build_composition_song_context(ss).style, "Rock")

    def test_authored_auto_groove_is_a_mode_not_the_style(self) -> None:
        from backing_context import build_composition_song_context

        ss, _ = _active_composition("Pop", groove="Auto")
        ctx = build_composition_song_context(ss)
        self.assertEqual(ctx.style, "Pop")
        self.assertNotEqual(ctx.style, "Auto")

    def test_backing_card_shows_pop_not_auto(self) -> None:
        from backing_context import build_composition_song_context
        from backing_context_ui import render_backing_composition_song_context_card

        ss, _ = _active_composition("Pop")
        ctx = build_composition_song_context(ss)
        st_ui = MagicMock()
        render_backing_composition_song_context_card(
            st_ui, ctx, ss, applied_bpm=100, applied_groove="Pop groove", practice_key="C"
        )
        html_out = " ".join(str(c.args[0]) for c in st_ui.markdown.call_args_list if c.args)
        self.assertIn("Pop", html_out)
        self.assertNotIn("Style: <strong>Auto", html_out)

    def test_switching_sources_does_not_leak_style(self) -> None:
        from backing_context import build_composition_song_context

        ss, _ = _active_composition("Pop")
        ss["progression_style"] = "Bossa Nova"  # Custom leftover must not win
        ss["backing_groove_style"] = "Auto"
        self.assertEqual(build_composition_song_context(ss).style, "Pop")


if __name__ == "__main__":
    unittest.main()
