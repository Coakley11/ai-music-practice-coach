"""The Missions Example buttons and the Motif buttons carry the shared action icons.

Issue 61 gave these icons to the Span-mission Example buttons only (mission_span_ui); the same
four actions on the Missions surface and the four Motif actions were still plain text.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from music_feature_icons import ACTION_ICONS

SRC = (Path(__file__).resolve().parents[1] / "improvisation_intelligence_ui.py").read_text(encoding="utf-8")


class Icons(unittest.TestCase):
    def test_missions_example_buttons(self):
        for verb, text in (("generate", "Generate example"), ("easier", "Easier example"),
                           ("harder", "Harder example"), ("idea", "New idea")):
            self.assertIn(f'action_label("{verb}", "{text}")', SRC)

    def test_motif_buttons(self):
        self.assertIn('action_label("generate", f"Generate motif for {gen_chord}")', SRC)
        for verb, text in (("idea", "New motif"), ("harder", "Harder motif"), ("easier", "Easier motif")):
            self.assertIn(f'action_label("{verb}", "{text}")', SRC)

    def test_the_verbs_reuse_the_shared_glyphs(self):
        self.assertEqual((ACTION_ICONS["generate"], ACTION_ICONS["easier"], ACTION_ICONS["harder"], ACTION_ICONS["idea"]),
                         ("🪄", "🌱", "🧠", "💡"))


if __name__ == "__main__":
    unittest.main()
