"""Display-only backing card routing tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from backing_context import BackingContext, build_custom_progression_context, set_backing_context
from backing_context_ui import (
    render_backing_creative_context_card,
    render_backing_custom_progression_context_card,
)


class TestBackingContextUiCards(unittest.TestCase):
    def test_creative_card_skips_custom_progression(self) -> None:
        session = {
            "cpl_active_progression": {
                "name": "Trial Song",
                "id": "trial-1",
                "original_key_center": "D",
                "bpm": 120,
                "original_sections": {"Main": [{"chord": "D", "bars": 4}]},
            },
        }
        ctx = build_custom_progression_context(session)
        st = MagicMock()
        render_backing_creative_context_card(
            st,
            ctx,
            session,
            applied_bpm=120,
            applied_groove="Pop groove",
        )
        st.markdown.assert_not_called()

    def test_custom_card_uses_progression_not_style_jam(self) -> None:
        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_generated_sections": {"Style Jam": ["D", "D", "A", "A"]},
            "cpl_active_progression": {
                "name": "Trial Song",
                "id": "trial-1",
                "original_key_center": "D",
                "bpm": 120,
                "original_sections": {
                    "Verse": [{"chord": "Dm7", "bars": 2}, {"chord": "G7", "bars": 2}],
                    "Chorus": [],
                    "Bridge": [],
                    "Intro": [],
                    "Outro": [],
                },
            },
        }
        ctx = build_custom_progression_context(session)
        set_backing_context(session, ctx)
        st = MagicMock()
        render_backing_custom_progression_context_card(
            st,
            ctx,
            session,
            applied_bpm=120,
            applied_groove="Pop groove",
            practice_key="D",
        )
        st.markdown.assert_called_once()
        html_out = str(st.markdown.call_args[0][0])
        self.assertIn("Custom progression backing", html_out)
        self.assertIn("Trial Song", html_out)
        self.assertNotIn("Creative backing session", html_out)
        self.assertNotIn("Style Jam", html_out)


if __name__ == "__main__":
    unittest.main()
