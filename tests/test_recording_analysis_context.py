"""Tests for recording analysis-context snapshot + workflow-gated recording types."""

from __future__ import annotations

import unittest

from recording_analysis_context import (
    ANALYSIS_EVAL_INSTRUMENT_KEY,
    ANALYSIS_EVAL_INSTRUMENTS_KEY,
    ANALYSIS_IDENTITY_LOCKED_KEY,
    ANALYSIS_MISSION_CONSTRAINT_KEY,
    ANALYSIS_SONG_SOURCE_ID_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    RECORDING_TYPE_BACKING,
    RECORDING_TYPE_MISSION,
    RECORDING_TYPE_MT_LAYER,
    RECORDING_TYPE_MT_MIX,
    RECORDING_TYPE_PRACTICE,
    RECORDING_TYPE_SOLO,
    SONG_SOURCE_CATALOG,
    WORKFLOW_MULTITRACK,
    WORKFLOW_SINGLE,
    apply_manual_mission_recording_defaults,
    apply_mission_recording_defaults,
    apply_snapshot_to_analysis_ctx,
    build_analysis_context_snapshot,
    coach_emphasis_notes,
    is_genuine_mission_upload_handoff,
    load_snapshot_from_result,
    maybe_apply_manual_mission_defaults,
    normalize_recording_type_for_workflow,
    persist_snapshot_on_result,
    recording_types_for_workflow,
)
from recording_analysis import build_coach_summary, build_practice_plan, _apply_context_emphasis_to_categories
from upload_analysis_modes import MULTITRACK_RECORDING, SINGLE_RECORDING


class RecordingTypesByWorkflowTests(unittest.TestCase):
    def test_single_recording_types(self) -> None:
        types = recording_types_for_workflow(WORKFLOW_SINGLE)
        self.assertEqual(
            types,
            (
                RECORDING_TYPE_SOLO,
                RECORDING_TYPE_PRACTICE,
                RECORDING_TYPE_BACKING,
                RECORDING_TYPE_MISSION,
            ),
        )
        self.assertNotIn(RECORDING_TYPE_MT_MIX, types)

    def test_multitrack_types(self) -> None:
        types = recording_types_for_workflow(WORKFLOW_MULTITRACK)
        self.assertEqual(types, (RECORDING_TYPE_MT_LAYER, RECORDING_TYPE_MT_MIX))
        self.assertNotIn(RECORDING_TYPE_SOLO, types)
        self.assertNotIn(RECORDING_TYPE_MISSION, types)

    def test_normalize_swaps_invalid_type(self) -> None:
        session = {
            "analysis_mode": MULTITRACK_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_SOLO,
        }
        out = normalize_recording_type_for_workflow(session)
        self.assertEqual(out, RECORDING_TYPE_MT_MIX)
        self.assertEqual(session["analysis_recording_type"], RECORDING_TYPE_MT_MIX)


class HandoffDetectionTests(unittest.TestCase):
    def test_ordinary_upload_not_treated_as_handoff(self) -> None:
        session = {
            "analysis_sync_creative_mission": True,
            "improv_active_mission": "Only Chord Tones",
            "improv_mission_pick": "Only Chord Tones",
        }
        self.assertFalse(is_genuine_mission_upload_handoff(session))

    def test_genuine_handoff_flag_detected(self) -> None:
        session = {"_mission_upload_analysis_handoff": True}
        self.assertTrue(is_genuine_mission_upload_handoff(session))

    def test_non_mission_type_excludes_ambient_mission_from_snapshot(self) -> None:
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
            "improv_active_mission": "Only Chord Tones",
            "analysis_sync_creative_mission": True,
            "instrument": "Piano",
            "focus": "Improvisation",
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Say",
        }
        snap = build_analysis_context_snapshot(session)
        self.assertEqual(snap["recording_type"], RECORDING_TYPE_PRACTICE)
        self.assertEqual(snap["mission_type"], "")
        self.assertEqual(snap["mission_constraint"], "")

    def test_mission_recording_includes_selected_constraint(self) -> None:
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_MISSION,
            ANALYSIS_MISSION_CONSTRAINT_KEY: "Only Chord Tones",
            "instrument": "Tenor Sax",
            "focus": "Improvisation",
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Say",
        }
        snap = build_analysis_context_snapshot(session)
        self.assertEqual(snap["recording_type"], RECORDING_TYPE_MISSION)
        self.assertEqual(snap["mission_type"], "Only Chord Tones")
        self.assertEqual(snap["mission_constraint"], "Only Chord Tones")


class SnapshotBuildTests(unittest.TestCase):
    def test_build_snapshot_captures_core_fields(self) -> None:
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
            "improv_ai_metric_ids": ["phrase_structure"],
            "analysis_effective_metric_ids": ["phrase_structure"],
            "focus": "Improvisation",
            "instrument": "Tenor Sax",
            "level": "Intermediate",
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Tenor Sax"],
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CATALOG,
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Say",
            "analysis_song_source_id": "catalog:say",
            "song": "Say",
        }
        snap = build_analysis_context_snapshot(session, association="unit_test")
        self.assertEqual(snap["workflow"], WORKFLOW_SINGLE)
        self.assertEqual(snap["recording_type"], RECORDING_TYPE_PRACTICE)
        self.assertEqual(snap["practice_focus"], "Improvisation")
        self.assertEqual(snap["instruments"], ["Tenor Sax"])
        self.assertEqual(snap["level"], "Intermediate")
        self.assertEqual(snap["song_source_name"], "Say")
        self.assertEqual(snap["song_source_type"], SONG_SOURCE_CATALOG)
        self.assertIn("phrase_structure", snap["evaluating_criteria_ids"])

    def test_snapshot_owns_ctx_over_ambient_state(self) -> None:
        snap = {
            "recording_type": RECORDING_TYPE_BACKING,
            "instruments": ["Piano"],
            "level": "Advanced",
            "practice_focus": "Groove",
            "song_source_name": "Song A",
            "song_source_type": SONG_SOURCE_CATALOG,
            "evaluating_criteria_ids": ["tone"],
            "evaluating_criteria_labels": ["Tone"],
            "mission_type": "",
            "workflow": WORKFLOW_SINGLE,
        }
        ctx = {
            "song": "Song B",
            "instrument": "Guitar",
            "level": "Beginner",
            "focus": "Technique",
            "recording_type": "practice",
        }
        merged = apply_snapshot_to_analysis_ctx(ctx, snap)
        self.assertEqual(merged["song"], "Song A")
        self.assertEqual(merged["instrument"], "Piano")
        self.assertEqual(merged["level"], "Advanced")
        self.assertEqual(merged["focus"], "Groove")
        self.assertEqual(merged["recording_type"], RECORDING_TYPE_BACKING)

    def test_persist_and_reload_roundtrip(self) -> None:
        snap = build_analysis_context_snapshot(
            {
                "analysis_mode": SINGLE_RECORDING,
                "analysis_recording_type": RECORDING_TYPE_SOLO,
                "instrument": "Flute",
                "focus": "Tone",
                ANALYSIS_SONG_SOURCE_NAME_KEY: "Custom Piece",
            }
        )
        result = persist_snapshot_on_result({"ok": True, "scores": {"timing": 70}}, snap)
        loaded = load_snapshot_from_result(result)
        self.assertEqual(loaded["recording_type"], RECORDING_TYPE_SOLO)
        self.assertEqual(loaded["song_source_name"], "Custom Piece")
        self.assertEqual(result["analysis_context_snapshot"]["instruments"], ["Flute"])


class MissionDefaultsTests(unittest.TestCase):
    def test_mission_defaults_mission_recording_single(self) -> None:
        session = {
            "instrument": "Guitar",
            "song": "Autumn Leaves",
            "level": "Intermediate",
            "focus": "Improvisation",
            "improv_active_mission": "Only Chord Tones",
        }
        apply_mission_recording_defaults(session)
        self.assertEqual(session["analysis_mode"], SINGLE_RECORDING)
        self.assertEqual(session["analysis_recording_type"], RECORDING_TYPE_MISSION)
        self.assertEqual(session.get(ANALYSIS_EVAL_INSTRUMENTS_KEY), ["Guitar"])
        self.assertEqual(session.get(ANALYSIS_MISSION_CONSTRAINT_KEY), "Only Chord Tones")
        self.assertTrue(session.get("analysis_identity_locked"))

    def test_manual_mission_defaults_editable_not_locked(self) -> None:
        session = {
            "instrument": "Tenor Sax",
            "song": "Say",
            "level": "Intermediate",
            "focus": "Improvisation",
            "pick_key": "Jazz\x1fSay — John Legend",
            "selected_song": {"title": "Say", "artist": "John Legend"},
            "improv_active_mission": "Only Chord Tones",
            "analysis_recording_type": RECORDING_TYPE_SOLO,
        }
        maybe_apply_manual_mission_defaults(session)  # no-op until type flips
        session["analysis_recording_type"] = RECORDING_TYPE_MISSION
        maybe_apply_manual_mission_defaults(session)
        self.assertEqual(session["analysis_recording_type"], RECORDING_TYPE_MISSION)
        self.assertFalse(bool(session.get(ANALYSIS_IDENTITY_LOCKED_KEY)))
        self.assertEqual(session.get(ANALYSIS_EVAL_INSTRUMENTS_KEY), ["Tenor Sax"])
        self.assertEqual(session.get(ANALYSIS_SONG_SOURCE_NAME_KEY), "Say")
        self.assertEqual(session.get(ANALYSIS_SONG_SOURCE_TYPE_KEY), SONG_SOURCE_CATALOG)

    def test_handoff_locks_identity_ambient_does_not(self) -> None:
        ambient = {
            "analysis_sync_creative_mission": True,
            "improv_active_mission": "Only Chord Tones",
            "analysis_recording_type": RECORDING_TYPE_SOLO,
            "instrument": "Piano",
        }
        self.assertFalse(is_genuine_mission_upload_handoff(ambient))
        handoff = {
            "_mission_upload_analysis_handoff": True,
            "instrument": "Tenor Sax",
            "song": "Say",
            "improv_active_mission": "Only Chord Tones",
            "selected_song": {"title": "Say", "artist": "John Legend"},
        }
        apply_mission_recording_defaults(handoff)
        self.assertTrue(handoff.get(ANALYSIS_IDENTITY_LOCKED_KEY))
        snap = build_analysis_context_snapshot(handoff)
        self.assertTrue(snap.get("identity_locked"))
        self.assertEqual(snap.get("recording_type"), RECORDING_TYPE_MISSION)
        self.assertEqual(snap.get("instruments"), ["Tenor Sax"])

    def test_single_instrument_key_feeds_snapshot(self) -> None:
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_SOLO,
            ANALYSIS_EVAL_INSTRUMENT_KEY: "Tenor Sax",
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CATALOG,
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Say",
            ANALYSIS_SONG_SOURCE_ID_KEY: "catalog:say",
        }
        snap = build_analysis_context_snapshot(session)
        self.assertEqual(snap["instruments"], ["Tenor Sax"])
        self.assertEqual(snap["song_source_id"], "catalog:say")


class MultitrackHeadingTests(unittest.TestCase):
    def test_multitrack_heading_uses_bpm_loop_groove(self) -> None:
        from pathlib import Path

        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn('section_open_fn(st, "BPM / Loop / Groove", icon="⏱")', src)
        self.assertNotIn('section_open_fn(st, "Key / BPM / meter", icon="⏱")', src)


class CoachEmphasisTests(unittest.TestCase):
    def test_practice_take_more_diagnostic_than_solo(self) -> None:
        practice_notes = coach_emphasis_notes({"recording_type": RECORDING_TYPE_PRACTICE})
        solo_notes = coach_emphasis_notes({"recording_type": RECORDING_TYPE_SOLO})
        self.assertTrue(any("Practice Take" in n or "diagnostic" in n.lower() for n in practice_notes))
        self.assertTrue(any("Solo Performance" in n for n in solo_notes))
        self.assertNotEqual(practice_notes[0], solo_notes[0])

    def test_criteria_changes_next_focus(self) -> None:
        scores = {"timing": 60, "pitch": 80, "technique": 70, "groove": 75, "musicality": 72, "confidence": 78, "tone": 74}
        categories = {
            "timing": {"findings": ["timing issue"], "tips": ["metronome"]},
            "pitch": {"findings": ["pitch ok"], "tips": ["drone"]},
            "technique": {"findings": ["tech"], "tips": ["slow"]},
            "groove": {"findings": ["groove"], "tips": ["pocket"]},
            "musicality": {"findings": ["mus"], "tips": ["shape"]},
            "confidence": {"findings": ["conf"], "tips": ["take2"]},
            "tone": {"findings": ["tone"], "tips": ["air"]},
        }
        _, _, _, focus_phrasing = build_coach_summary(
            scores,
            categories,
            {"evaluating_criteria_labels": ["Phrasing"], "focus": "Improvisation"},
        )
        _, _, _, focus_tone = build_coach_summary(
            scores,
            categories,
            {"evaluating_criteria_labels": ["Tone"], "focus": "Improvisation"},
        )
        self.assertIn("Phrasing", focus_phrasing)
        self.assertIn("Tone", focus_tone)
        self.assertNotEqual(focus_phrasing, focus_tone)

    def test_recording_type_changes_practice_plan(self) -> None:
        class _F:
            tempo = 90

        scores = {"timing": 55, "pitch": 70, "technique": 68, "groove": 60, "musicality": 65, "confidence": 70, "tone": 72}
        practice = build_practice_plan(scores, {"recording_type": RECORDING_TYPE_PRACTICE, "display_key": "C"}, _F())
        backing = build_practice_plan(scores, {"recording_type": RECORDING_TYPE_BACKING, "display_key": "C"}, _F())
        self.assertTrue(any("Diagnostic" in p or "weakest" in p.lower() for p in practice))
        self.assertTrue(any("backing" in p.lower() or "Lock" in p for p in backing))

    def test_criteria_augments_categories_without_changing_scores(self) -> None:
        categories = {
            "musicality": {
                "title": "Musicality",
                "findings": ["base"],
                "tips": ["base tip"],
                "score": 71,
            },
            "timing": {"title": "Timing", "findings": ["t"], "tips": ["tt"], "score": 60},
        }
        out = _apply_context_emphasis_to_categories(
            categories,
            {"evaluating_criteria_labels": ["Phrasing"], "recording_type": RECORDING_TYPE_SOLO},
        )
        self.assertEqual(out["musicality"]["score"], 71)
        joined = " ".join(out["musicality"]["findings"])
        self.assertTrue(
            "Phrasing" in joined or "Evaluating Criteria" in joined,
            joined,
        )
        # Chord-tone criteria should deepen pitch coaching without score mutation
        pitch_out = _apply_context_emphasis_to_categories(
            {
                "pitch": {"title": "Pitch", "findings": ["base"], "tips": ["base tip"], "score": 66},
                "musicality": {"title": "Musicality", "findings": ["m"], "tips": ["mt"], "score": 70},
            },
            {
                "evaluating_criteria_labels": ["Chord-tone targeting"],
                "recording_type": RECORDING_TYPE_MISSION,
                "mission_type": "Only Chord Tones",
                "level": "Advanced",
            },
        )
        self.assertEqual(pitch_out["pitch"]["score"], 66)
        self.assertTrue(any("Chord-tone" in f or "chord tone" in f.lower() for f in pitch_out["pitch"]["findings"]))


class ManualMissionLifecycleTests(unittest.TestCase):
    def test_manual_mission_defaults_apply_before_widget_keys_would_bind(self) -> None:
        """Simulate Streamlit rerun: type already Mission; defaults must run pre-widget."""
        from recording_analysis_context import (
            ANALYSIS_PLAYER_LEVEL_KEY,
            ANALYSIS_PRACTICE_FOCUS_KEY,
        )

        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_SOLO,
            "instrument": "Saxophone",
            "level": "Intermediate",
            "focus": "Tone",
            "song": "Blue Bossa",
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CATALOG,
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Blue Bossa",
        }
        # First paint records previous type
        maybe_apply_manual_mission_defaults(session)
        # User selects Mission Recording → Streamlit reruns with new value already in state
        session["analysis_recording_type"] = RECORDING_TYPE_MISSION
        # Defaults MUST run before any widget bind (we only mutate session_state here)
        applied = maybe_apply_manual_mission_defaults(session)
        self.assertTrue(applied)
        self.assertEqual(session["analysis_mode"], SINGLE_RECORDING)
        self.assertEqual(session["analysis_recording_type"], RECORDING_TYPE_MISSION)
        self.assertFalse(bool(session.get(ANALYSIS_IDENTITY_LOCKED_KEY)))
        instruments = session.get(ANALYSIS_EVAL_INSTRUMENTS_KEY) or []
        self.assertTrue(instruments)
        self.assertTrue(
            any("Sax" in str(x) for x in instruments),
            instruments,
        )
        self.assertEqual(session.get(ANALYSIS_PLAYER_LEVEL_KEY), "Intermediate")
        # Fields remain editable (not identity-locked)
        session[ANALYSIS_EVAL_INSTRUMENT_KEY] = "Flute"
        session[ANALYSIS_EVAL_INSTRUMENTS_KEY] = ["Flute"]
        session[ANALYSIS_PRACTICE_FOCUS_KEY] = "Articulation"
        self.assertEqual(session[ANALYSIS_EVAL_INSTRUMENTS_KEY], ["Flute"])
        self.assertEqual(session[ANALYSIS_PRACTICE_FOCUS_KEY], "Articulation")


class SnapshotPersistenceTests(unittest.TestCase):
    def test_snapshot_survives_global_song_instrument_focus_change(self) -> None:
        from recording_analysis_context import (
            ANALYSIS_PLAYER_LEVEL_KEY,
            ANALYSIS_PRACTICE_FOCUS_KEY,
        )

        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Tenor Sax"],
            ANALYSIS_PLAYER_LEVEL_KEY: "Intermediate",
            ANALYSIS_PRACTICE_FOCUS_KEY: "Tone",
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CATALOG,
            ANALYSIS_SONG_SOURCE_ID_KEY: "Jazz::Blue Bossa — Kenny Dorham",
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Blue Bossa — Kenny Dorham",
            "analysis_effective_metric_ids": ["phrasing"],
            "instrument": "Tenor Sax",
            "song": "Blue Bossa — Kenny Dorham",
            "level": "Intermediate",
            "focus": "Tone",
        }
        snap = build_analysis_context_snapshot(session)
        result = persist_snapshot_on_result({"ok": True, "scores": {"timing": 70}}, snap)
        # Ambient globals change after save
        session["song"] = "Song A Ambient"
        session["instrument"] = "Piano"
        session["focus"] = "Voicings"
        session[ANALYSIS_SONG_SOURCE_NAME_KEY] = "Song A Ambient"
        loaded = load_snapshot_from_result(result)
        self.assertEqual(loaded["song_source_name"], "Blue Bossa — Kenny Dorham")
        self.assertEqual(loaded["instruments"], ["Tenor Sax"])
        self.assertEqual(loaded["practice_focus"], "Tone")
        self.assertEqual(loaded["level"], "Intermediate")
        self.assertEqual(loaded["recording_type"], RECORDING_TYPE_PRACTICE)


class SelectedSongHarmonyTests(unittest.TestCase):
    def test_upload_selected_song_b_not_ambient_song_a(self) -> None:
        from custom_progression_lab import CPL_SAVED_KEY
        from recording_analysis_context import (
            SONG_SOURCE_CUSTOM,
            attach_selected_song_harmony_to_snapshot,
        )

        song_a_chords = ["Cmaj7", "Am7"]
        session = {
            "song": "Song A",
            "active_song_name": "Song A",
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CUSTOM,
            ANALYSIS_SONG_SOURCE_ID_KEY: "custom::Song B",
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Song B",
            CPL_SAVED_KEY: {
                "Song B": {
                    "name": "Song B",
                    "original_key_center": "E minor",
                    "original_sections": {
                        "A": [{"chord": "F#m7b5"}, {"chord": "B7"}, {"chord": "Em"}],
                    },
                },
                "Song A": {
                    "name": "Song A",
                    "original_sections": {
                        "A": [{"chord": "Cmaj7"}, {"chord": "Am7"}],
                    },
                },
            },
        }
        snap = build_analysis_context_snapshot(session)
        snap = attach_selected_song_harmony_to_snapshot(session, snap)
        self.assertTrue(snap.get("target_chords"))
        self.assertEqual(snap["song_source_name"], "Song B")
        # Must be Song B harmony, not Song A
        self.assertIn("F#m7b5", snap["target_chords"])
        self.assertNotIn("Cmaj7", snap["target_chords"])
        ambient_ctx = {
            "song": "Song A",
            "sections": {"A": song_a_chords},
            "target_chords": song_a_chords,
            "evaluating_criteria_labels": ["Chord-tone targeting"],
        }
        merged = apply_snapshot_to_analysis_ctx(ambient_ctx, snap)
        self.assertEqual(merged["song"], "Song B")
        self.assertIn("F#m7b5", merged["target_chords"])
        self.assertNotEqual(merged["target_chords"], song_a_chords)


class PracticeFocusSelectionTests(unittest.TestCase):
    def test_single_recording_one_instrument_one_focus_from_options(self) -> None:
        from pathlib import Path

        from practice_setup_controls import focus_options_for_instrument
        from recording_analysis_context import ANALYSIS_PRACTICE_FOCUS_KEY

        options = focus_options_for_instrument("Saxophone")
        self.assertTrue(options)
        session = {
            "analysis_mode": SINGLE_RECORDING,
            ANALYSIS_EVAL_INSTRUMENT_KEY: "Saxophone",
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Saxophone"],
            ANALYSIS_PRACTICE_FOCUS_KEY: options[0],
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
        }
        snap = build_analysis_context_snapshot(session)
        self.assertEqual(len(snap["instruments"]), 1)
        self.assertEqual(snap["instruments"][0], "Saxophone")
        self.assertEqual(snap["practice_focus"], options[0])
        src = Path("upload_analysis_setup_ui.py").read_text(encoding="utf-8")
        self.assertIn('"Practice Focus"', src)
        self.assertIn("focus_options_for_instrument", src)
        # Practice Focus must be a multiselect (any number of Focuses), not free-text.
        focus_idx = src.find('"Practice Focus"')
        window = src[max(0, focus_idx - 120) : focus_idx + 80]
        self.assertIn("multiselect", window)
        self.assertIn("ANALYSIS_PRACTICE_FOCUSES_KEY", src)


class MultitrackStepLabelTests(unittest.TestCase):
    def test_multitrack_capture_is_step_2(self) -> None:
        from pathlib import Path

        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        marker = "Upload stems for multitrack analysis"
        idx = src.find(marker)
        self.assertGreater(idx, 0, "Multitrack capture kicker not found")
        window = src[max(0, idx - 250) : idx + 80]
        self.assertIn("Step 2", window)
        self.assertIn("Capture audio", window)


class AmiUploadContextTests(unittest.TestCase):
    def test_compact_recording_for_ami_keeps_analysis_context(self) -> None:
        from media_state import build_media_ami_payload_from_catalog, compact_recording_for_ami

        entry = {
            "recording_id": "rec-1",
            "created_at": "2026-08-01T12:00:00",
            "filename": "take.wav",
            "song": "Blue Bossa — Kenny Dorham",
            "instrument": "Tenor Sax",
            "duration_seconds": 12.0,
            "analysis_summary": {
                "coach_summary": "Solid take.",
                "scores": {"timing": 70},
                "weakest_category": "timing",
                "strongest_category": "tone",
            },
            "analysis_context_snapshot": {
                "workflow": WORKFLOW_SINGLE,
                "recording_type": RECORDING_TYPE_MISSION,
                "instruments": ["Tenor Sax"],
                "level": "Intermediate",
                "practice_focus": "Tone",
                "evaluating_criteria_ids": ["phrasing"],
                "evaluating_criteria_labels": ["Phrasing"],
                "song_source_type": SONG_SOURCE_CATALOG,
                "song_source_id": "Jazz::Blue Bossa — Kenny Dorham",
                "song_source_name": "Blue Bossa — Kenny Dorham",
                "mission_type": "Only Chord Tones",
                "mission_constraint": "Only Chord Tones",
                "mission_parameters": {"backing_track": True},
            },
        }
        compact = compact_recording_for_ami(entry)
        self.assertEqual(compact.get("practice_focus"), "Tone")
        self.assertEqual(compact.get("evaluating_criteria_labels"), ["Phrasing"])
        self.assertEqual(compact.get("recording_type"), RECORDING_TYPE_MISSION)
        self.assertEqual(compact.get("song_source_name"), "Blue Bossa — Kenny Dorham")
        self.assertEqual(compact.get("mission_type"), "Only Chord Tones")
        self.assertEqual(compact.get("level"), "Intermediate")
        payload = build_media_ami_payload_from_catalog(
            {
                "uploaded_recordings": [entry],
                "multitrack_sessions": [],
                "tone_takes": [],
                "multitrack_exports": [],
            },
            window_days=3650,
        )
        rows = payload.get("recording_analysis_context") or []
        self.assertTrue(rows)
        self.assertEqual(rows[0].get("practice_focus"), "Tone")
        self.assertEqual(rows[0].get("evaluating_criteria_labels"), ["Phrasing"])
        self.assertEqual(rows[0].get("recording_type"), RECORDING_TYPE_MISSION)



class MultitrackInstrumentFocusTests(unittest.TestCase):
    def test_single_recording_multiple_focuses_from_instrument_options(self) -> None:
        from practice_setup_controls import focus_options_for_instrument
        from recording_analysis_context import (
            ANALYSIS_INSTRUMENT_FOCUSES_KEY,
            ANALYSIS_PRACTICE_FOCUSES_KEY,
        )

        flute_opts = focus_options_for_instrument("Flute")
        self.assertTrue(flute_opts)
        selected = [flute_opts[0], flute_opts[1], flute_opts[2]]
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Flute"],
            ANALYSIS_PRACTICE_FOCUSES_KEY: list(selected),
            ANALYSIS_INSTRUMENT_FOCUSES_KEY: {"Flute": list(selected)},
        }
        snap = build_analysis_context_snapshot(session)
        self.assertEqual(snap["instruments"], ["Flute"])
        self.assertEqual(snap["instrument_focuses"]["Flute"], selected)
        self.assertEqual(snap["practice_focuses"], selected)
        self.assertEqual(snap["practice_focus"], selected[0])
        for foc in selected:
            self.assertIn(foc, flute_opts)

    def test_multitrack_independent_focus_lists_and_ui_labels(self) -> None:
        from pathlib import Path

        from practice_setup_controls import focus_options_for_instrument
        from recording_analysis_context import (
            ANALYSIS_INSTRUMENT_FOCUSES_KEY,
            instrument_focus_widget_key,
            prepare_instrument_focus_ui,
        )

        sax_opts = focus_options_for_instrument("Saxophone")
        piano_opts = focus_options_for_instrument("Piano")
        self.assertTrue(sax_opts)
        self.assertTrue(piano_opts)
        self.assertNotEqual(sax_opts, piano_opts)

        sax_focuses = [sax_opts[0], sax_opts[1]]
        piano_focuses = [piano_opts[0], piano_opts[1]]
        session = {
            "analysis_mode": MULTITRACK_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_MT_MIX,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Saxophone", "Piano"],
            ANALYSIS_INSTRUMENT_FOCUSES_KEY: {
                "Saxophone": list(sax_focuses),
                "Piano": list(piano_focuses),
            },
        }
        session[instrument_focus_widget_key("Saxophone")] = list(sax_focuses)
        session[instrument_focus_widget_key("Piano")] = list(piano_focuses)
        prepared = prepare_instrument_focus_ui(session, ["Saxophone", "Piano"])
        self.assertEqual(prepared["Saxophone"], sax_focuses)
        self.assertEqual(prepared["Piano"], piano_focuses)

        snap = build_analysis_context_snapshot(session)
        self.assertEqual(snap["instrument_focuses"]["Saxophone"], sax_focuses)
        self.assertEqual(snap["instrument_focuses"]["Piano"], piano_focuses)
        self.assertEqual(len(snap["instrument_focuses"]), 2)

        src = Path("upload_analysis_setup_ui.py").read_text(encoding="utf-8")
        self.assertIn("{inst} — Practice Focus", src)
        self.assertIn("st.multiselect", src)
        self.assertIn("prepare_instrument_focus_ui", src)

    def test_removing_instrument_prunes_focus_list_from_snapshot_and_ui(self) -> None:
        from practice_setup_controls import focus_options_for_instrument
        from recording_analysis_context import (
            ANALYSIS_INSTRUMENT_FOCUSES_KEY,
            instrument_focus_widget_key,
            prepare_instrument_focus_ui,
        )

        sax_opts = focus_options_for_instrument("Saxophone")
        piano_opts = focus_options_for_instrument("Piano")
        guitar_opts = focus_options_for_instrument("Guitar")
        session = {
            "analysis_mode": MULTITRACK_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_MT_MIX,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Saxophone", "Piano", "Guitar"],
            ANALYSIS_INSTRUMENT_FOCUSES_KEY: {
                "Saxophone": [sax_opts[0]],
                "Piano": [piano_opts[0], piano_opts[1]],
                "Guitar": [guitar_opts[0]],
            },
        }
        for inst, foc in session[ANALYSIS_INSTRUMENT_FOCUSES_KEY].items():
            session[instrument_focus_widget_key(inst)] = list(foc)

        snap = build_analysis_context_snapshot(session)
        self.assertEqual(set(snap["instrument_focuses"]), {"Saxophone", "Piano", "Guitar"})

        session[ANALYSIS_EVAL_INSTRUMENTS_KEY] = ["Saxophone", "Piano"]
        snap2 = build_analysis_context_snapshot(session)
        self.assertEqual(set(snap2["instrument_focuses"]), {"Saxophone", "Piano"})
        self.assertNotIn("Guitar", snap2["instrument_focuses"])

        # UI sync (pre-widget) is responsible for pruning session map / widget seeds.
        prepare_instrument_focus_ui(session, ["Saxophone", "Piano"])
        self.assertNotIn("Guitar", session.get(ANALYSIS_INSTRUMENT_FOCUSES_KEY) or {})
        self.assertNotIn(instrument_focus_widget_key("Guitar"), session)

    def test_changing_single_instrument_prunes_invalid_focuses(self) -> None:
        from practice_setup_controls import focus_options_for_instrument
        from recording_analysis_context import (
            ANALYSIS_INSTRUMENT_FOCUSES_KEY,
            ANALYSIS_PRACTICE_FOCUSES_KEY,
            prepare_instrument_focus_ui,
        )

        flute_opts = set(focus_options_for_instrument("Flute"))
        guitar_opts = focus_options_for_instrument("Guitar")
        # Force a Flute-only Focus into session, then switch instrument to Guitar.
        session = {
            "analysis_mode": SINGLE_RECORDING,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Guitar"],
            ANALYSIS_PRACTICE_FOCUSES_KEY: ["Tone", "Articulation", guitar_opts[0]],
            ANALYSIS_INSTRUMENT_FOCUSES_KEY: {
                "Guitar": ["Tone", "Articulation", guitar_opts[0]],
            },
        }
        prepared = prepare_instrument_focus_ui(
            session,
            ["Guitar"],
            single_recording=True,
        )
        kept = prepared["Guitar"]
        for foc in kept:
            self.assertIn(foc, guitar_opts)
        if "Tone" not in guitar_opts:
            self.assertNotIn("Tone", kept)
        # Snapshot should also omit invalid Flute Focuses after UI prune.
        snap = build_analysis_context_snapshot(session)
        for foc in snap["instrument_focuses"]["Guitar"]:
            self.assertIn(foc, guitar_opts)
            self.assertTrue(foc not in flute_opts or foc in guitar_opts)

    def test_history_reload_and_ami_preserve_focus_lists(self) -> None:
        from media_state import build_media_ami_payload_from_catalog, compact_recording_for_ami
        from practice_setup_controls import focus_options_for_instrument
        from recording_analysis_context import (
            ANALYSIS_INSTRUMENT_FOCUSES_KEY,
            instrument_focus_widget_key,
        )

        sax_opts = focus_options_for_instrument("Saxophone")
        piano_opts = focus_options_for_instrument("Piano")
        mapping = {
            "Saxophone": [sax_opts[0], sax_opts[1]],
            "Piano": [piano_opts[0], piano_opts[1]],
        }
        session = {
            "analysis_mode": MULTITRACK_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_MT_MIX,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Saxophone", "Piano"],
            ANALYSIS_INSTRUMENT_FOCUSES_KEY: {k: list(v) for k, v in mapping.items()},
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CATALOG,
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Blue Bossa",
        }
        for inst, foc in mapping.items():
            session[instrument_focus_widget_key(inst)] = list(foc)
        snap = build_analysis_context_snapshot(session)
        result = persist_snapshot_on_result({"ok": True}, snap)
        loaded = load_snapshot_from_result(result)
        self.assertEqual(loaded["instrument_focuses"], mapping)

        entry = {
            "recording_id": "rec-mt-1",
            "created_at": "2026-08-01T12:00:00",
            "filename": "mix.wav",
            "song": "Blue Bossa",
            "instrument": "Saxophone",
            "duration_seconds": 20.0,
            "analysis_summary": {"coach_summary": "Ensemble take."},
            "analysis_context_snapshot": loaded,
        }
        compact = compact_recording_for_ami(entry)
        self.assertEqual(compact.get("instrument_focuses"), mapping)
        self.assertEqual(compact.get("practice_focuses"), mapping["Saxophone"])
        payload = build_media_ami_payload_from_catalog(
            {
                "uploaded_recordings": [entry],
                "multitrack_sessions": [],
                "tone_takes": [],
                "multitrack_exports": [],
            },
            window_days=3650,
        )
        rows = payload.get("recording_analysis_context") or []
        self.assertTrue(rows)
        self.assertEqual(rows[0].get("instrument_focuses"), mapping)

    def test_layer_coaching_receives_all_target_focuses(self) -> None:
        snap = {
            "workflow": WORKFLOW_MULTITRACK,
            "recording_type": RECORDING_TYPE_MT_LAYER,
            "instruments": ["Saxophone", "Piano"],
            "target_layer": "Piano",
            "practice_focus": "Improvisation",
            "practice_focuses": ["Improvisation"],
            "instrument_focuses": {
                "Saxophone": ["Improvisation", "Phrasing"],
                "Piano": ["Comping", "Voicings"],
            },
        }
        ctx = apply_snapshot_to_analysis_ctx({"recording_type": RECORDING_TYPE_MT_LAYER}, snap)
        self.assertEqual(ctx.get("practice_focuses"), ["Comping", "Voicings"])
        self.assertEqual(ctx.get("focuses"), ["Comping", "Voicings"])
        self.assertEqual(ctx.get("focus"), "Comping")
        self.assertEqual(ctx.get("instrument_focuses"), snap["instrument_focuses"])

    def test_mix_coaching_retains_full_mapping(self) -> None:
        from recording_analysis import analyze_multitrack

        ctx = {
            "recording_type": RECORDING_TYPE_MT_MIX,
            "workflow": WORKFLOW_MULTITRACK,
            "instruments": ["Saxophone", "Piano"],
            "instrument_focuses": {
                "Saxophone": ["Improvisation", "Phrasing"],
                "Piano": ["Comping", "Voicings"],
            },
            "practice_focuses": ["Improvisation", "Phrasing"],
            "focus": "Improvisation",
            "evaluating_criteria_labels": [],
        }
        # Minimal fake layer features path: call helper body via importing analyze if audio-free path exists.
        # If analyze_multitrack requires audio, assert apply/coach notes instead.
        notes = coach_emphasis_notes(
            {
                "workflow": WORKFLOW_MULTITRACK,
                "recording_type": RECORDING_TYPE_MT_MIX,
                "instruments": ["Saxophone", "Piano"],
                "instrument_focuses": ctx["instrument_focuses"],
            }
        )
        joined = " ".join(notes)
        self.assertIn("Saxophone", joined)
        self.assertIn("Piano", joined)
        self.assertIn("Improvisation", joined)
        self.assertIn("Comping", joined)

    def test_legacy_scalar_instrument_focus_migrates_to_list(self) -> None:
        from recording_analysis_context import normalize_instrument_focuses_map

        self.assertEqual(
            normalize_instrument_focuses_map({"Flute": "Tone"}),
            {"Flute": ["Tone"]},
        )
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Flute"],
            "analysis_instrument_focuses": {"Flute": "Tone"},
        }
        snap = build_analysis_context_snapshot(session)
        self.assertEqual(snap["instrument_focuses"]["Flute"], ["Tone"])
        self.assertEqual(snap["practice_focuses"], ["Tone"])
        self.assertEqual(snap["practice_focus"], "Tone")

    def test_legacy_practice_focus_scalar_still_usable(self) -> None:
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Flute"],
            "analysis_practice_focus": "Tone",
        }
        snap = build_analysis_context_snapshot(session)
        self.assertEqual(snap["practice_focus"], "Tone")
        self.assertEqual(snap["practice_focuses"], ["Tone"])
        self.assertEqual(snap["instrument_focuses"]["Flute"], ["Tone"])

    def test_build_snapshot_does_not_mutate_widget_backed_keys(self) -> None:
        from recording_analysis_context import (
            ANALYSIS_INSTRUMENT_FOCUSES_KEY,
            ANALYSIS_PRACTICE_FOCUS_KEY,
            ANALYSIS_PRACTICE_FOCUSES_KEY,
            instrument_focus_widget_key,
        )

        wk = instrument_focus_widget_key("Flute")
        session = {
            "analysis_mode": SINGLE_RECORDING,
            "analysis_recording_type": RECORDING_TYPE_PRACTICE,
            ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Flute"],
            ANALYSIS_PRACTICE_FOCUSES_KEY: ["Tone", "Phrasing"],
            ANALYSIS_PRACTICE_FOCUS_KEY: "Tone",
            ANALYSIS_INSTRUMENT_FOCUSES_KEY: {"Flute": ["Tone", "Phrasing"]},
            wk: ["Tone", "Phrasing"],
        }
        before = {
            ANALYSIS_PRACTICE_FOCUS_KEY: session[ANALYSIS_PRACTICE_FOCUS_KEY],
            ANALYSIS_PRACTICE_FOCUSES_KEY: list(session[ANALYSIS_PRACTICE_FOCUSES_KEY]),
            wk: list(session[wk]),
            ANALYSIS_INSTRUMENT_FOCUSES_KEY: {
                k: list(v) for k, v in session[ANALYSIS_INSTRUMENT_FOCUSES_KEY].items()
            },
        }
        snap = build_analysis_context_snapshot(session)
        self.assertEqual(snap["practice_focuses"], ["Tone", "Phrasing"])
        # Widget-backed / Focus UI keys must remain untouched by snapshot construction.
        self.assertEqual(session[ANALYSIS_PRACTICE_FOCUS_KEY], before[ANALYSIS_PRACTICE_FOCUS_KEY])
        self.assertEqual(session[ANALYSIS_PRACTICE_FOCUSES_KEY], before[ANALYSIS_PRACTICE_FOCUSES_KEY])
        self.assertEqual(session[wk], before[wk])
        self.assertEqual(
            session[ANALYSIS_INSTRUMENT_FOCUSES_KEY],
            before[ANALYSIS_INSTRUMENT_FOCUSES_KEY],
        )



if __name__ == "__main__":
    unittest.main()
