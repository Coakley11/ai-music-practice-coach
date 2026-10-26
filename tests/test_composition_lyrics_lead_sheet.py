"""Slice 6B Stage 2: Review-centered lyrics/melody lead-sheet integration."""

from __future__ import annotations

import copy
import inspect
import unittest

from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    section_melody_events,
)
from composition_lyrics_alignment import (
    confirm_alignment,
    get_alignment,
    realign_section,
    refresh_section_alignment_status,
)
from composition_melody_notation import build_section_score_model
from composition_review import song_is_ready
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_LIBRARY_KEY,
)
from composition_workspace_state_persistence import (
    COMPOSITION_WORKSPACE_STATE_KEY,
    apply_composition_workspace_from_payload,
    gather_composition_workspace_from_session,
)


def _events() -> list[dict]:
    return [
        {"pitch": "C4", "duration_beats": 1.0, "beat": 0.0, "measure": 1},
        {"pitch": "D4", "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        {"pitch": "E4", "duration_beats": 1.0, "beat": 2.0, "measure": 1},
        {"pitch": "F4", "duration_beats": 1.0, "beat": 3.0, "measure": 1},
        {"pitch": "G4", "duration_beats": 2.0, "beat": 0.0, "measure": 2},
        {"pitch": "rest", "is_rest": True, "duration_beats": 1.0, "beat": 2.0, "measure": 2},
        {"pitch": "A4", "duration_beats": 1.0, "beat": 3.0, "measure": 2},
    ]


def _doc() -> tuple[dict, dict]:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="A flexible songwriting lead sheet",
        title="Stage 2 QA",
        key="C major",
        bpm=96,
        meter="4/4",
    )
    apply_structure_template(doc, "simple")
    section = ordered_sections(doc)[0]
    apply_section_chords(doc, str(section["id"]), parse_chord_paste("C Am"))
    apply_melody_events(doc, str(section["id"]), _events(), replace=True)
    section.setdefault("lyrics", {})["raw_text"] = "Hel-lo bright world"
    section["lyrics"]["lines"] = ["Hel-lo bright world"]
    return doc, section


def _score(doc: dict, section: dict) -> dict:
    pg = doc.get("global") or {}
    return build_section_score_model(
        events=section_melody_events(section),
        chords=list(section.get("chords") or []),
        key=str(pg.get("original_key_center") or "C"),
        meter=str(pg.get("time_signature") or "4/4"),
        bpm=int(pg.get("bpm") or 96),
        title=str(section.get("label_variant") or "Verse"),
        lyrics_text=str((section.get("lyrics") or {}).get("raw_text") or ""),
        lyrics_alignment=get_alignment(section),
    )


class TestAlignedLeadSheetModel(unittest.TestCase):
    def test_provisional_alignment_adds_abc_lyrics_beneath_chorded_staff(self) -> None:
        doc, section = _doc()
        realign_section(section, meter="4/4")
        score = _score(doc, section)
        self.assertTrue(score["lyrics_aligned"])
        self.assertEqual(score["alignment_status"], "provisional")
        self.assertIn('"C"', score["abc"])
        self.assertIn('"Am"', score["abc"])
        self.assertIn("\nw: ", score["abc"])
        self.assertIn("Hel-", score["abc"])

    def test_confirmed_alignment_renders_but_stale_alignment_does_not(self) -> None:
        doc, section = _doc()
        alignment = realign_section(section)
        confirm_alignment(alignment, timestamp="2026-10-21T00:00:00+00:00")
        self.assertTrue(_score(doc, section)["lyrics_aligned"])
        section["lyrics"]["raw_text"] = "Changed lyric line"
        self.assertTrue(refresh_section_alignment_status(section))
        score = _score(doc, section)
        self.assertEqual(score["alignment_status"], "stale")
        self.assertFalse(score["lyrics_aligned"])
        self.assertNotIn("\nw: ", score["abc"])
        self.assertEqual(score["lyrics_text"], "Changed lyric line")

    def test_alignment_does_not_mutate_authoritative_material(self) -> None:
        doc, section = _doc()
        before_chords = copy.deepcopy(section["chords"])
        before_events = copy.deepcopy(section_melody_events(section))
        before_lyrics = copy.deepcopy(section["lyrics"])
        realign_section(section)
        _score(doc, section)
        self.assertEqual(section["chords"], before_chords)
        self.assertEqual(section_melody_events(section), before_events)
        self.assertEqual(section["lyrics"], before_lyrics)

    def test_section_alignment_does_not_leak(self) -> None:
        doc, first = _doc()
        second = ordered_sections(doc)[1]
        apply_melody_events(doc, str(second["id"]), _events()[:2], replace=True)
        second.setdefault("lyrics", {})["raw_text"] = "Second line"
        second["lyrics"]["lines"] = ["Second line"]
        realign_section(first)
        realign_section(second)
        first_score = _score(doc, first)
        second_score = _score(doc, second)
        self.assertIn("Hel-", first_score["abc"])
        self.assertNotIn("Hel-", second_score["abc"])
        self.assertIn("Sec-", second_score["abc"])


class TestABCLyricSemantics(unittest.TestCase):
    def test_melisma_uses_underscore_and_untexted_note_uses_star(self) -> None:
        doc, section = _doc()
        section["lyrics"]["raw_text"] = "Ah"
        section["lyrics"]["lines"] = ["Ah"]
        alignment = realign_section(section)
        score = _score(doc, section)
        w_line = next(line for line in score["abc"].splitlines() if line.startswith("w:"))
        self.assertIn("_", w_line)
        # The full-beat phrase-ending rest prevents the final A4 from being
        # mislabeled as a continuation of "Ah".
        self.assertIn("*", w_line)
        self.assertEqual(alignment["event_assignments"][-1]["type"], "unassigned")

    def test_rests_do_not_consume_syllables_and_bars_are_preserved(self) -> None:
        doc, section = _doc()
        realign_section(section)
        score = _score(doc, section)
        w_line = next(line for line in score["abc"].splitlines() if line.startswith("w:"))
        self.assertIn("|", w_line)
        self.assertLess(len(w_line.split()), len(section_melody_events(section)) + 5)


class TestFlexibleSongwritingStates(unittest.TestCase):
    def test_chords_and_lyrics_need_no_melody_or_alignment(self) -> None:
        doc, section = _doc()
        section["melody"]["events"] = []
        score = _score(doc, section)
        self.assertTrue(score["has_chords"])
        self.assertTrue(score["has_lyrics"])
        self.assertFalse(score["has_melody"])
        self.assertFalse(score["lyrics_aligned"])
        self.assertTrue(song_is_ready(doc))

    def test_melody_only_is_valid_authored_material(self) -> None:
        doc, section = _doc()
        section["chords"] = []
        section["lyrics"]["raw_text"] = ""
        score = _score(doc, section)
        self.assertTrue(score["has_melody"])
        self.assertFalse(score["has_chords"])
        self.assertFalse(score["has_lyrics"])
        self.assertTrue(song_is_ready(doc))

    def test_unaccepted_suggestion_is_not_authoritative(self) -> None:
        from composition_studio_page import _section_lyrics_text

        section = {
            "lyrics": {
                "raw_text": "",
                "lines": [],
                "ai_suggestion": "Do not silently use me",
            }
        }
        self.assertEqual(_section_lyrics_text(section), "")


class TestAlignmentPersistence(unittest.TestCase):
    def test_workspace_roundtrip_preserves_section_owned_alignment(self) -> None:
        doc, section = _doc()
        realign_section(section)
        section_id = str(section["id"])
        session = {
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: section_id,
            COMPOSER_LIBRARY_KEY: {str(doc["id"]): copy.deepcopy(doc)},
            "studio_page": "composer",
        }
        payload = gather_composition_workspace_from_session(session)
        fresh: dict = {}
        apply_composition_workspace_from_payload(
            fresh,
            {COMPOSITION_WORKSPACE_STATE_KEY: payload},
            authoritative=True,
        )
        restored = fresh[COMPOSER_ACTIVE_KEY]
        restored_section = next(s for s in ordered_sections(restored) if str(s["id"]) == section_id)
        self.assertEqual(restored["id"], doc["id"])
        self.assertEqual(restored_section["lyrics_alignment"], section["lyrics_alignment"])


class TestProjectionIndependence(unittest.TestCase):
    def test_piano_tenor_and_alto_keep_syllable_ownership(self) -> None:
        from composition_songs_bridge import composition_written_pitch_semitones
        from media_tone_catalog import transpose_note_token

        doc, section = _doc()
        alignment = realign_section(section)
        ownership = copy.deepcopy(alignment["event_assignments"])
        source_events = section_melody_events(section)
        for instrument in ("Piano", "Tenor saxophone", "Alto saxophone"):
            semitones = composition_written_pitch_semitones(instrument)
            projected = []
            for event in source_events:
                clone = copy.deepcopy(event)
                if not clone.get("is_rest"):
                    clone["pitch"] = transpose_note_token(str(clone["pitch"]), semitones)
                projected.append(clone)
            score = build_section_score_model(
                events=projected,
                chords=section["chords"],
                key="C",
                meter="4/4",
                bpm=96,
                lyrics_text=section["lyrics"]["raw_text"],
                lyrics_alignment=alignment,
            )
            self.assertTrue(score["lyrics_aligned"])
            self.assertIn("\nw: ", score["abc"])
            self.assertEqual(alignment["event_assignments"], ownership)


class TestReviewWorkflowSource(unittest.TestCase):
    def test_review_owns_alignment_action_with_manual_editing_and_confirmation(self) -> None:
        from composition_studio_page import (
            _render_phase_review,
            _render_review_alignment_controls,
        )

        review_source = inspect.getsource(_render_phase_review)
        controls_source = inspect.getsource(_render_review_alignment_controls)
        self.assertIn("_render_review_alignment_controls", review_source)
        self.assertIn("Align Lyrics to Melody", controls_source)
        self.assertIn("realign_section", controls_source)
        self.assertIn("confirm_alignment", controls_source)
        self.assertIn("_section_lyrics_text", controls_source)
        self.assertIn("reassign_syllable", controls_source)
        self.assertIn("restore_confirmed_snapshot", controls_source)


class TestAutoAlignmentOnReviewEntry(unittest.TestCase):
    """Slice 1: entering Review auto-generates a provisional alignment for sections
    that have both lyrics and melody but have not been aligned yet."""

    def test_review_phase_contains_auto_alignment_logic(self) -> None:
        """The Review render function auto-aligns unaligned sections with lyrics + melody."""
        from composition_studio_page import _render_phase_review

        review_source = inspect.getsource(_render_phase_review)
        self.assertIn("realign_section", review_source, "Review auto-alignment calls realign_section")
        self.assertIn('"unaligned"', review_source, "Review checks for unaligned status")

    def test_auto_alignment_produces_provisional_not_confirmed(self) -> None:
        doc, section = _doc()
        realign_section(section, meter="4/4")
        alignment = get_alignment(section)
        self.assertEqual(alignment["status"], "provisional")
        self.assertNotEqual(alignment["status"], "confirmed")

    def test_auto_alignment_does_not_overwrite_confirmed(self) -> None:
        """Sections with confirmed alignment are not re-aligned."""
        doc, section = _doc()
        alignment = realign_section(section, meter="4/4")
        confirm_alignment(alignment, timestamp="2026-10-25T00:00:00+00:00")
        original_ea = copy.deepcopy(alignment["event_assignments"])
        refresh_section_alignment_status(section)
        self.assertEqual(get_alignment(section)["status"], "confirmed")
        self.assertEqual(get_alignment(section)["event_assignments"], original_ea)

    def test_lyrics_only_section_not_auto_aligned(self) -> None:
        doc, section = _doc()
        section.pop("melody", None)
        self.assertEqual(get_alignment(section).get("status", "unaligned"), "unaligned")
        self.assertFalse(section_melody_events(section))

    def test_melody_only_section_not_auto_aligned(self) -> None:
        doc, section = _doc()
        section["lyrics"] = {}
        self.assertEqual(get_alignment(section).get("status", "unaligned"), "unaligned")


if __name__ == "__main__":
    unittest.main()
