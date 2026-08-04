"""Phase 2A — authoritative mission practice context and exact-chord backing."""

from __future__ import annotations

import unittest

from mission_practice_context import (
    MISSION_BACKING_SOUNDING_CHORD_KEY,
    MISSION_EXACT_BACKING_ARMED_KEY,
    MISSION_RECORDING_SEAL_KEY,
    build_mission_practice_context,
    enrich_analysis_context,
    mission_capture_allowed,
    parse_mission_chord,
    recording_context_stale_warning,
    refresh_mission_practice_context,
    seal_recording_context,
    ui_backing_chord_mismatch,
)


class TestMissionPracticeContextPhase2A(unittest.TestCase):
    def test_parse_mission_chord_slash_bass(self) -> None:
        parsed = parse_mission_chord("G/B", section="Verse", chord_index=3, chord_label="G/B")
        self.assertEqual(parsed.root, "G")
        self.assertEqual(parsed.bass, "B")
        self.assertIn("/", parsed.inversion_hint)

    def test_authoritative_chord_uses_index_not_name(self) -> None:
        session = {
            "improv_active_mission": "Target tone drill",
            "improv_mission_chord_options": ["Bm", "Em", "G", "A"] * 2,
            "ii_selected_chord": "A",
            "ii_selected_section": "Chorus",
            "ii_selected_chord_index": 7,
            "backing_track_bpm": 92,
            "improv_style_meta": {"style": "Pop", "groove": "Pop groove", "bpm": 92},
        }
        ctx = build_mission_practice_context(session)
        self.assertEqual(ctx.chord.symbol, "A")
        self.assertEqual(ctx.chord.chord_index, 7)
        self.assertEqual(ctx.mission_type, "Target tone drill")
        self.assertEqual(ctx.tempo_bpm, 92)

    def test_ui_backing_mismatch_detected(self) -> None:
        session = {
            "ii_selected_chord": "Am7",
            "ii_selected_chord_index": 0,
            "improv_mission_chord_options": ["Am7"],
            MISSION_BACKING_SOUNDING_CHORD_KEY: "Dm7",
        }
        bad, msg = ui_backing_chord_mismatch(session)
        self.assertTrue(bad)
        self.assertIn("Am7", msg)
        self.assertIn("Dm7", msg)

    def test_seal_and_stale_warning(self) -> None:
        session = {
            "improv_active_mission": "Develop one motif",
            "improv_mission_chord_options": ["Cmaj7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Cmaj7",
            MISSION_EXACT_BACKING_ARMED_KEY: True,
        }
        seal_recording_context(session, association="test")
        self.assertIn(MISSION_RECORDING_SEAL_KEY, session)
        session["ii_selected_chord_index"] = 0
        session["improv_mission_chord_options"] = ["Dm7"]
        session["ii_selected_chord"] = "Dm7"
        refresh_mission_practice_context(session)
        warn = recording_context_stale_warning(session)
        self.assertIn("chord changed", warn.lower())

    def test_enrich_analysis_context_single_chord(self) -> None:
        session = {
            "improv_active_mission": "Chord-tone targeting",
            "improv_mission_chord_options": ["Fmaj7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Fmaj7",
            "ii_selected_section": "Chorus",
        }
        base = {"target_chords": ["C", "G", "Am"], "sections": {"Verse": ["C", "G"]}}
        out = enrich_analysis_context(session, base)
        self.assertEqual(out["target_chords"], ["Fmaj7"])
        self.assertEqual(out["mission_chord"], "Fmaj7")
        self.assertEqual(out["sections"], {"Chorus": ["Fmaj7"]})

    def test_capture_blocked_without_armed_backing(self) -> None:
        session = {
            "improv_active_mission": "Guide-tone targeting",
            "improv_mission_chord_options": ["Em7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Em7",
            MISSION_BACKING_SOUNDING_CHORD_KEY: "Em7",
        }
        ok, msg = mission_capture_allowed(session, require_mission_workflow=True)
        self.assertFalse(ok)
        self.assertIn("exact-chord backing", msg.lower())


if __name__ == "__main__":
    unittest.main()
