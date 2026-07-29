"""Unit tests for Composition Studio document and snapshot."""

import unittest

from composition_document import (
    bootstrap_from_seed,
    chords_for_playback,
    parse_chord_paste,
    touch_composition,
)
from composition_snapshot import build_composition_snapshot, snapshot_invalidate_token


class TestCompositionDocument(unittest.TestCase):
    def test_bootstrap_from_chords_seed(self) -> None:
        doc = bootstrap_from_seed(seed_type="chords", seed_text="| G | Am | C |")
        self.assertEqual(doc["origin"]["seed_type"], "chords")
        chords = chords_for_playback(doc, scope="song")
        self.assertEqual(chords[:3], ["G", "Am", "C"])

    def test_bootstrap_style_intent_sets_style(self) -> None:
        doc = bootstrap_from_seed(seed_type="style_intent", seed_text="I want a jazz ballad")
        self.assertIn("Jazz", str(doc.get("metadata", {}).get("style", "")))

    def test_parse_chord_paste(self) -> None:
        entries = parse_chord_paste("G Am C D")
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0]["chord"], "G")

    def test_snapshot_updates_after_edit(self) -> None:
        doc = bootstrap_from_seed(seed_type="exploring", seed_text="")
        token_a = snapshot_invalidate_token(doc)
        sections = list((doc.get("form") or {}).get("section_order") or [])
        sec_id = sections[0]
        sec = doc["form"]["sections"][sec_id]
        sec["chords"] = parse_chord_paste("Em C G D")
        touch_composition(doc)
        token_b = snapshot_invalidate_token(doc)
        self.assertNotEqual(token_a, token_b)
        snap = build_composition_snapshot(doc, active_section_id=sec_id)
        self.assertTrue(snap.get("commitment", {}).get("has_chords"))
        self.assertEqual(snap["active_section"]["chord_symbols"][:2], ["Em", "C"])


if __name__ == "__main__":
    unittest.main()
