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

    def test_span_motif_buttons(self):
        """The 2-3 chord span motif row (Creative Lab Phrase/Motif) was still plain text on dev 212e0c63."""
        for verb, text, key in (("generate", "Generate span motif", "improv_span_gen"),
                                ("idea", "New span idea", "improv_span_new"),
                                ("easier", "Easier", "improv_span_easier"),
                                ("harder", "Harder", "improv_span_harder")):
            row = [ln for ln in SRC.splitlines() if f'"{key}"' in ln and f'"{text}"' in ln]
            self.assertEqual(len(row), 1, key)
            self.assertTrue(row[0].rstrip().endswith(f'"{verb}"),'), row[0])
        self.assertIn("st.button(action_label(verb, label), key=key, type=kind", SRC)

    def test_transform_and_develop_buttons(self):
        """User 2026-11-20: every Missions / Motif / Span Motif action button carries its icon."""
        for verb, text in (("sequence_up", "Sequence Up"), ("sequence_down", "Sequence Down"),
                           ("reverse", "Reverse Order"), ("rhythm", "Change Rhythm"),
                           ("build", "Build Motif Pattern"), ("apply_settings", "Apply Pattern Type / Direction"),
                           ("build", "Build span exercise"), ("reset", "Back to seed motif"),
                           ("sheet_music", "Generate Sheet Music"), ("guitar_tab", "Generate Guitar TAB")):
            self.assertIn(f'action_label("{verb}", "{text}")', SRC)
        # One look per act across the three surfaces: Missions, single-chord Motif, Span Motif.
        self.assertEqual(SRC.count('action_label("sequence_up", "Sequence Up")'), 3)
        self.assertEqual(SRC.count('action_label("reverse", "Reverse Order")'), 3)
        self.assertEqual(SRC.count('action_label("rhythm", "Change Rhythm")'), 4)
        # The arrows typed into the labels are gone - the icon is the one convention.
        for old in ("Sequence Up ↑", "Sequence Down ↓", "Reverse Order ⇄"):
            self.assertNotIn(f'"{old}"', SRC)

    def test_the_span_transforms_stay_disabled(self):
        row = SRC[SRC.index('"improv_span_seq_up"') - 200: SRC.index('"improv_span_invert"') + 400]
        self.assertIn("st.button(label, key=key, disabled=True", row)

    def test_mission_generate_backing(self):
        src = (Path(__file__).resolve().parents[1] / "mission_exact_chord_backing_ui.py").read_text(encoding="utf-8")
        self.assertIn('action_label("generate", "Generate Backing")', src)

    def test_the_new_creative_glyphs(self):
        want = {"sequence_up": "⬆️", "sequence_down": "⬇️", "reverse": "🔄", "rhythm": "🥁", "build": "🧩",
                "apply_settings": "✅", "sheet_music": "🎼", "guitar_tab": "🎸"}
        self.assertEqual({k: ACTION_ICONS[k] for k in want}, want)

    def test_the_verbs_reuse_the_shared_glyphs(self):
        self.assertEqual((ACTION_ICONS["generate"], ACTION_ICONS["easier"], ACTION_ICONS["harder"], ACTION_ICONS["idea"]),
                         ("🪄", "🌱", "🧠", "💡"))


if __name__ == "__main__":
    unittest.main()
