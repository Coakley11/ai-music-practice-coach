"""Tests for Composition Studio chord suggestions (CS-B2)."""

import unittest

from composition_chord_suggestions import (
    default_feeling_for_section,
    suggest_progressions,
    symbols_to_entries,
)
from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    sync_linked_chord_sections,
)


class TestCompositionChordSuggestions(unittest.TestCase):
    def test_default_feeling_for_chorus(self) -> None:
        sec = {"label": "Chorus", "label_variant": "Chorus"}
        self.assertEqual(default_feeling_for_section(sec), "uplifting")

    def test_suggest_progressions_in_key(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="A hopeful song.")
        doc["global"]["original_key_center"] = "G"
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        ideas = suggest_progressions(doc, verse, "stable", limit=3)
        self.assertGreaterEqual(len(ideas), 2)
        self.assertTrue(all(i.get("line") for i in ideas))
        self.assertIn("G", ideas[0]["line"])

    def test_apply_section_chords_syncs_linked(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse2 = next(s for s in ordered_sections(doc) if s.get("label_variant") == "Verse 2")
        verse1 = next(s for s in ordered_sections(doc) if s.get("label_variant") == "Verse 1")
        entries = parse_chord_paste("G Am C D")
        apply_section_chords(doc, str(verse1["id"]), entries)
        sync_linked_chord_sections(doc, str(verse1["id"]))
        self.assertEqual(len(verse2.get("chords") or []), 4)

    def test_symbols_to_entries(self) -> None:
        entries = symbols_to_entries(["C", "G", "Am"])
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["chord"], "C")


if __name__ == "__main__":
    unittest.main()
