"""Tests for Composition Studio review helpers (CS-B5)."""

import unittest

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
)
from composition_review import (
    build_readiness_checklist,
    coach_line_for_review,
    harmony_overview_rows,
    song_is_ready,
)


class TestCompositionReview(unittest.TestCase):
    def test_readiness_checklist_instrumental_skips_lyrics(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="An ambient piece.", instrumental=True)
        apply_structure_template(doc, "simple")
        rows = {r["phase"]: r for r in build_readiness_checklist(doc)}
        self.assertEqual(rows["lyrics"]["status"], "skipped")

    def test_harmony_overview_shows_linked_note(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test song idea here.")
        apply_structure_template(doc, "simple")
        sections = ordered_sections(doc)
        verse2 = next(s for s in sections if str(s.get("label_variant") or "").startswith("Verse 2"))
        apply_section_chords(doc, str(sections[0]["id"]), [{"chord": "C", "bars": 4}])
        overview = harmony_overview_rows(doc)
        self.assertTrue(any("Verse" in r["variant"] for r in overview))

    def test_coach_line_mentions_vision(self) -> None:
        doc = bootstrap_from_vision(genre="Folk", song_idea="Walking home in the rain.")
        apply_structure_template(doc, "simple")
        text = coach_line_for_review(doc)
        self.assertIn("Walking home", text)

    def test_song_not_ready_without_chords(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="A song.")
        apply_structure_template(doc, "simple")
        self.assertFalse(song_is_ready(doc))


if __name__ == "__main__":
    unittest.main()
