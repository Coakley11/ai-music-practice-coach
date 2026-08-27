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

    def test_working_draft_is_not_a_library_save(self) -> None:
        from composition_document import apply_lyrics_text, apply_melody_events, parse_chord_paste
        from composition_session_state import (
            COMPOSER_LIBRARY_KEY,
            get_active_document,
            save_document_to_library,
            set_active_document,
        )
        from composition_vocal_render import (
            build_vocal_render_plan,
            render_vocal_audio,
            vocal_render_available,
        )

        doc = bootstrap_from_vision(genre="Pop", song_idea="Home.", key="C major", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        sid = str(ordered_sections(doc)[0]["id"])
        apply_section_chords(doc, sid, parse_chord_paste("C Am F G"))
        apply_melody_events(
            doc,
            sid,
            [
                {"pitch": "C4", "duration_beats": 1.0, "beat": 0.0, "measure": 1},
                {"pitch": "E4", "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            ],
            source="ai",
        )
        apply_lyrics_text(doc, sid, "Go")
        ss: dict = {}
        set_active_document(ss, doc)
        self.assertFalse(ss.get(COMPOSER_LIBRARY_KEY))
        self.assertIsNone((get_active_document(ss) or {}).get("library_id"))

        saved = save_document_to_library(ss, doc)
        self.assertEqual(saved.get("library_id"), saved.get("id"))
        self.assertTrue(saved.get("library_saved_at"))
        self.assertIn(str(saved.get("id")), ss.get(COMPOSER_LIBRARY_KEY) or {})

        self.assertFalse(vocal_render_available())
        plan = build_vocal_render_plan(doc, scope="section", section_id=sid)
        self.assertGreaterEqual(plan["note_count"], 1)
        self.assertGreaterEqual(plan["aligned_count"], 1)
        self.assertEqual(plan["notes"][0]["syllable"].lower(), "go")
        result = render_vocal_audio(plan)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["audio"])
        self.assertIn("singing-synthesis", result["message"])
        self.assertIn("speech TTS is not used", result["message"])


if __name__ == "__main__":
    unittest.main()
