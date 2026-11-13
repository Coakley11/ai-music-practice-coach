"""Songs-page card sees a saved Composition's own chord chart (and melody)."""

from __future__ import annotations

import unittest

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_songs_bridge import composition_song_card_record
from song_card_guidance import build_song_card_guidance

EMPTY = "Add a chord chart"


def _doc(chords: str | None, key: str = "C major"):
    doc = bootstrap_from_vision(genre="Jazz", song_idea="card", title="Jazz Tune", key=key, bpm=100)
    apply_structure_template(doc, "simple")
    if chords:
        apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste(chords))
    return doc


def _card(rec, **kw):
    args = dict(level="Intermediate", instrument="Piano", focus="", practice_key=None, chart_key=None)
    args.update(kw)
    return build_song_card_guidance(rec, **args)


class CompositionSongCardChartTests(unittest.TestCase):
    def test_chart_present_shows_harmony(self):
        rec = composition_song_card_record(_doc("Dm7 G7 Cmaj7 Cmaj7"))
        self.assertTrue(rec["sections"])
        g = _card(rec)
        self.assertNotIn(EMPTY, g["harmony"])
        self.assertIn("Dm7", g["harmony"] + " " + str(g["facts"].distinct))
        self.assertEqual(g["facts"].distinct, ["Dm7", "G7", "Cmaj7"])
        self.assertTrue(g["facts"].ii_v)  # derived ii-V, not hardcoded

    def test_no_chart_keeps_instruction(self):
        rec = composition_song_card_record(_doc(None))
        self.assertEqual(rec["sections"], {})
        self.assertIn(EMPTY, _card(rec)["harmony"])

    def test_identity_preserved(self):
        doc = _doc("C F G C")
        rec = composition_song_card_record(doc)
        self.assertEqual(rec["pick_key"], f"composition::{doc['id']}")
        self.assertEqual(rec["source"], "Composition")

    def test_written_key_for_transposing_instrument(self):
        rec = composition_song_card_record(_doc("C F G C"))
        g = _card(rec, instrument="Trumpet", practice_key="C", chart_key="D",
                  key_mode="written", transposing_type="Trumpet (Bb)")
        self.assertEqual(g["key_mode"], "written")
        self.assertIn("Written key", g["key_mode_label"])
        self.assertIn("D", g["harmony"] + g["key_mode_label"])
        # facts stay in the composition's concert chart
        self.assertEqual(g["facts"].distinct, ["C", "F", "G"])

    def test_melody_recognised(self):
        rec = composition_song_card_record(_doc("C F G C"))
        self.assertIn("generated", _card(rec)["melody"])
        rec["extensions"]["composition_melody_sections"] = ["Verse"]
        m = _card(rec)["melody"]
        self.assertIn("composed melody", m)
        self.assertNotIn("generated for this song", m)


if __name__ == "__main__":
    unittest.main()
