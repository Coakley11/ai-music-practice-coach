"""Tests for Composition Studio melody suggestions (CS-B3)."""

import unittest

from composition_document import (
    apply_melody_concept,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    section_has_melody,
)
from composition_melody_suggestions import (
    default_melody_feel_for_section,
    suggest_melody_concepts,
)


class TestCompositionMelodySuggestions(unittest.TestCase):
    def test_default_feel_for_chorus(self) -> None:
        sec = {"label": "Chorus", "label_variant": "Chorus"}
        self.assertEqual(default_melody_feel_for_section(sec), "bold")

    def test_suggest_melody_concepts(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="A catchy song.")
        apply_structure_template(doc, "simple")
        chorus = next(s for s in ordered_sections(doc) if s.get("label") == "Chorus")
        ideas = suggest_melody_concepts(doc, chorus, "bold", "simple", limit=3)
        self.assertGreaterEqual(len(ideas), 2)
        self.assertTrue(all(i.get("motif_hint") for i in ideas))

    def test_apply_melody_concept(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        concept = suggest_melody_concepts(doc, verse, "lyrical", "simple", limit=1)[0]
        apply_melody_concept(doc, str(verse["id"]), concept)
        self.assertTrue(section_has_melody(verse))

    def test_hum_notes_count_as_melody(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        verse.setdefault("melody", {"intent": {}, "phrases": []})
        verse["melody"]["intent"]["hum_notes"] = "Da da da rising hook"
        self.assertTrue(section_has_melody(verse))


if __name__ == "__main__":
    unittest.main()
