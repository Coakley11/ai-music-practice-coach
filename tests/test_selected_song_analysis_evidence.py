"""Upload-selected song is first-class analysis evidence (Single + Multitrack)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from custom_progression_lab import CPL_SAVED_KEY
from recording_analysis_context import (
    ANALYSIS_EVAL_INSTRUMENTS_KEY,
    ANALYSIS_INSTRUMENT_FOCUSES_KEY,
    ANALYSIS_PLAYER_LEVEL_KEY,
    ANALYSIS_SONG_SOURCE_ID_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    ANALYSIS_TARGET_LAYER_KEY,
    RECORDING_TYPE_MT_LAYER,
    RECORDING_TYPE_MT_MIX,
    RECORDING_TYPE_PRACTICE,
    SONG_SOURCE_CUSTOM,
    SONG_SOURCE_OTHER,
    apply_snapshot_to_analysis_ctx,
    attach_selected_song_harmony_to_snapshot,
    build_analysis_context_snapshot,
    selected_song_analysis_context,
)
from upload_analysis_modes import MULTITRACK_RECORDING, SINGLE_RECORDING


def _song_b_session(**extra: object) -> dict:
    session = {
        "analysis_mode": SINGLE_RECORDING,
        "analysis_recording_type": RECORDING_TYPE_PRACTICE,
        "song": "Song A",
        "active_song_name": "Song A",
        "chart_key": "G",
        "display_key": "G",
        ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CUSTOM,
        ANALYSIS_SONG_SOURCE_ID_KEY: "custom::Song B",
        ANALYSIS_SONG_SOURCE_NAME_KEY: "Song B",
        ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Alto Saxophone"],
        ANALYSIS_PLAYER_LEVEL_KEY: "Intermediate",
        CPL_SAVED_KEY: {
            "Song B": {
                "name": "Song B",
                "original_key_center": "Eb",
                "bpm": 92,
                "time_signature": "4/4",
                "original_sections": {
                    "A": [
                        {"chord": "Cm7"},
                        {"chord": "Fm7"},
                        {"chord": "Bb7"},
                        {"chord": "Ebmaj7"},
                    ],
                    "Bridge": [{"chord": "Abmaj7"}, {"chord": "G7"}, {"chord": "Cm7"}],
                },
            },
            "Song A": {
                "name": "Song A",
                "original_key_center": "G",
                "original_sections": {
                    "A": [{"chord": "Gmaj7"}, {"chord": "Em7"}],
                },
            },
        },
    }
    session.update(extra)
    return session


class SelectedSongAuthorityTests(unittest.TestCase):
    def test_single_uses_upload_song_b_not_ambient_song_a(self) -> None:
        session = _song_b_session()
        snap = build_analysis_context_snapshot(session)
        snap = attach_selected_song_harmony_to_snapshot(session, snap)
        song_ctx = selected_song_analysis_context(session, snapshot=snap)
        self.assertEqual(song_ctx["title"], "Song B")
        self.assertEqual(song_ctx["key"], "Eb")
        self.assertIn("Cm7", song_ctx["chord_progression"])
        self.assertNotIn("Gmaj7", song_ctx["chord_progression"])
        ambient = {
            "song": "Song A",
            "display_key": "G",
            "sections": {"A": ["Gmaj7", "Em7"]},
            "target_chords": ["Gmaj7", "Em7"],
            "level": "Advanced",
        }
        merged = apply_snapshot_to_analysis_ctx(ambient, snap)
        self.assertEqual(merged["song"], "Song B")
        self.assertEqual(merged["display_key"], "Eb")
        self.assertIn("Cm7", merged["target_chords"])
        self.assertNotIn("Gmaj7", merged["target_chords"])
        self.assertEqual(merged["level"], "Intermediate")

    def test_layer_and_mix_consume_upload_song_b(self) -> None:
        for mode, rtype in (
            (MULTITRACK_RECORDING, RECORDING_TYPE_MT_LAYER),
            (MULTITRACK_RECORDING, RECORDING_TYPE_MT_MIX),
        ):
            session = _song_b_session(
                analysis_mode=mode,
                analysis_recording_type=rtype,
                **{
                    ANALYSIS_EVAL_INSTRUMENTS_KEY: ["Alto Saxophone", "Guitar"],
                    ANALYSIS_TARGET_LAYER_KEY: "Alto Saxophone",
                    ANALYSIS_INSTRUMENT_FOCUSES_KEY: {
                        "Alto Saxophone": ["Tone", "Scales", "Articulation", "Dynamics"],
                        "Guitar": ["Strumming"],
                    },
                },
            )
            snap = build_analysis_context_snapshot(session)
            snap = attach_selected_song_harmony_to_snapshot(session, snap)
            merged = apply_snapshot_to_analysis_ctx(
                {"display_key": "G", "target_chords": ["Gmaj7"], "sections": {"A": ["Gmaj7"]}},
                snap,
            )
            self.assertEqual(merged["display_key"], "Eb", msg=rtype)
            self.assertIn("Cm7", merged["target_chords"], msg=rtype)
            self.assertNotIn("Gmaj7", merged["target_chords"], msg=rtype)

    def test_other_not_a_song_clears_ambient_harmony(self) -> None:
        session = _song_b_session(
            **{
                ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_OTHER,
                ANALYSIS_SONG_SOURCE_ID_KEY: "",
                ANALYSIS_SONG_SOURCE_NAME_KEY: "Free long tones",
            }
        )
        snap = build_analysis_context_snapshot(session)
        snap = attach_selected_song_harmony_to_snapshot(session, snap)
        self.assertEqual(snap.get("sections"), {})
        self.assertEqual(snap.get("target_chords"), [])
        merged = apply_snapshot_to_analysis_ctx(
            {"sections": {"A": ["Gmaj7"]}, "target_chords": ["Gmaj7"], "display_key": "G"},
            snap,
        )
        self.assertEqual(merged.get("sections"), {})
        self.assertEqual(merged.get("target_chords"), [])
        self.assertEqual(merged.get("display_key"), "")

    def test_detected_center_pitch_is_not_selected_song_key(self) -> None:
        from recording_analysis import _pitch_analysis
        from types import SimpleNamespace

        f = SimpleNamespace(
            pitch_note="G3",
            voiced_ratio=0.8,
            pitch_cents_std=20.0,
            pitch_sharp_bias=0.0,
        )
        out = _pitch_analysis(
            f,
            "Alto Saxophone",
            {"display_key": "Eb", "song_source_type": SONG_SOURCE_CUSTOM, "sections": {"A": ["Cm7"]}},
        )
        blob = " ".join(out["findings"] + out["tips"]).lower()
        self.assertIn("not the selected song key", blob)
        self.assertNotIn("g major scale", blob)

    def test_practice_plan_uses_selected_song_not_ambient_g_major(self) -> None:
        from recording_analysis import build_practice_plan

        class _F:
            tempo = 81.0

        plan = build_practice_plan(
            {
                "timing": 60,
                "pitch": 40,
                "technique": 65,
                "groove": 68,
                "musicality": 70,
                "confidence": 72,
                "tone": 66,
            },
            {
                "instrument": "Alto Saxophone",
                "display_key": "Eb",
                "song": "Song B",
                "song_source_type": SONG_SOURCE_CUSTOM,
                "song_source_name": "Song B",
                "recording_type": RECORDING_TYPE_PRACTICE,
                "sections": {"A": ["Cm7", "Fm7", "Bb7", "Ebmaj7"]},
                "target_chords": ["Cm7", "Fm7", "Bb7", "Ebmaj7"],
                "practice_focuses": ["Scales", "Tone"],
                "practice_bpm": 92,
                "reference_bpm": 92,
            },
            _F(),
        )
        joined = " | ".join(plan)
        self.assertIn("Song B", joined)
        self.assertIn("Eb", joined)
        self.assertNotIn("G major scale", joined)
        self.assertTrue("Cm7" in joined or "first eight bars" in joined.lower())

    def test_current_level_owns_advanced_wording(self) -> None:
        from recording_analysis import _apply_context_emphasis_to_categories

        cats = {
            "musicality": {"title": "Musicality", "findings": [], "tips": []},
            "technique": {"title": "Technique", "findings": [], "tips": []},
        }
        advanced = _apply_context_emphasis_to_categories(
            cats, {"level": "Advanced", "recording_type": RECORDING_TYPE_PRACTICE}
        )
        intermediate = _apply_context_emphasis_to_categories(
            {
                "musicality": {"title": "Musicality", "findings": [], "tips": []},
                "technique": {"title": "Technique", "findings": [], "tips": []},
            },
            {"level": "Intermediate", "recording_type": RECORDING_TYPE_PRACTICE},
        )
        self.assertTrue(
            any("Advanced coaching" in x for x in advanced["musicality"]["findings"])
        )
        self.assertFalse(
            any("Advanced coaching" in x for x in intermediate["musicality"]["findings"])
        )
        self.assertTrue(
            any("Intermediate coaching" in x for x in intermediate["technique"]["tips"])
        )


class ScalesFocusSongEvidenceTests(unittest.TestCase):
    def test_scales_uses_song_harmony_not_long_tone_tip(self) -> None:
        from multitrack_upload_analysis import build_target_layer_focus_analysis

        blocks = build_target_layer_focus_analysis(
            features={"pitch_note": "G3", "spectral_centroid_mean": 1800.0},
            scores={"tone": 70, "technique": 72, "musicality": 88},
            categories={
                "technique": {
                    "tips": ["Long tones 60s — same attack, same release, same pitch."],
                    "findings": [],
                }
            },
            ctx={
                "recording_type": RECORDING_TYPE_MT_LAYER,
                "instruments": ["Alto Saxophone", "Guitar"],
                "target_layer": "Alto Saxophone",
                "instrument_focuses": {
                    "Alto Saxophone": ["Tone", "Scales", "Articulation", "Dynamics"],
                    "Guitar": ["Strumming"],
                },
                "song": "Song B",
                "song_source_type": SONG_SOURCE_CUSTOM,
                "display_key": "Eb",
                "sections": {"A": ["Cm7", "Fm7", "Bb7", "Ebmaj7"]},
                "target_chords": ["Cm7", "Fm7", "Bb7", "Ebmaj7"],
                "selected_song_analysis_context": {
                    "title": "Song B",
                    "key": "Eb",
                    "source_type": SONG_SOURCE_CUSTOM,
                    "chord_progression": ["Cm7", "Fm7", "Bb7", "Ebmaj7"],
                    "sections": {"A": ["Cm7", "Fm7", "Bb7", "Ebmaj7"]},
                    "has_song_harmony": True,
                    "has_song_form": True,
                    "authority": "selected",
                },
            },
            musical_metrics={"scale_adherence": 64, "chord_tone_accuracy": 58},
        )
        by_focus = {b["focus"]: b for b in blocks}
        self.assertIn("Scales", by_focus)
        scales = by_focus["Scales"]
        findings = " ".join(scales.get("findings") or []).lower()
        self.assertIn("song b", findings)
        self.assertIn("eb", findings)
        self.assertIn("cm7", findings)
        self.assertNotIn("long tones 60s", findings)
        self.assertNotIn("was analyzed with scales as an explicit coaching goal", (scales.get("went_well") or "").lower())
        self.assertIn("cm7", (scales.get("drill") or "").lower())
        # Guitar remains context only in arrangement helper
        from multitrack_upload_analysis import build_layer_arrangement_context

        arrangement = build_layer_arrangement_context(
            {
                "instruments": ["Alto Saxophone", "Guitar"],
                "target_layer": "Alto Saxophone",
                "instrument_focuses": {
                    "Alto Saxophone": ["Scales"],
                    "Guitar": ["Strumming"],
                },
                "song": "Song B",
                "display_key": "Eb",
                "sections": {"A": ["Cm7"], "Bridge": ["Abmaj7"]},
                "selected_song_analysis_context": {
                    "title": "Song B",
                    "key": "Eb",
                    "sections": {"A": ["Cm7"], "Bridge": ["Abmaj7"]},
                    "has_song_harmony": True,
                    "has_song_form": True,
                },
            }
        ).lower()
        self.assertIn("strumming", arrangement)
        self.assertIn("song b", arrangement)
        self.assertIn("no audio was scored", arrangement)

    def test_layer_enrich_summary_mentions_song(self) -> None:
        from multitrack_upload_analysis import enrich_layer_analysis_result

        out = enrich_layer_analysis_result(
            {
                "ok": True,
                "coach_summary": "Baseline.",
                "scores": {"tone": 70, "technique": 70},
                "features": {"pitch_note": "G3"},
                "categories": {},
                "practice_plan": ["G major scale @ 59 BPM — 2 octaves, even subdivisions."],
                "musical_metrics": {"scale_adherence": 70},
            },
            {
                "recording_type": RECORDING_TYPE_MT_LAYER,
                "instruments": ["Alto Saxophone"],
                "target_layer": "Alto Saxophone",
                "instrument_focuses": {"Alto Saxophone": ["Scales", "Tone"]},
                "practice_focuses": ["Scales", "Tone"],
                "song": "Song B",
                "display_key": "Eb",
                "sections": {"A": ["Cm7", "Fm7"]},
                "target_chords": ["Cm7", "Fm7"],
                "selected_song_analysis_context": {
                    "title": "Song B",
                    "key": "Eb",
                    "bpm": 92,
                    "meter": "4/4",
                    "chord_progression": ["Cm7", "Fm7"],
                    "sections": {"A": ["Cm7", "Fm7"]},
                    "has_song_harmony": True,
                    "has_song_form": True,
                    "resolved": True,
                },
            },
            uploaded_track_count=1,
        )
        summary = (out.get("coach_summary") or "").lower()
        self.assertIn("song b", summary)
        self.assertIn("eb", summary)
        scales = next(
            b for b in out.get("target_layer_focus_analysis") or [] if b.get("focus") == "Scales"
        )
        self.assertNotIn("long tones 60s", " ".join(scales.get("findings") or []).lower())


class HistorySongOwnershipTests(unittest.TestCase):
    def test_persisted_snapshot_keeps_selected_song_when_ambient_changes(self) -> None:
        from recording_analysis_context import persist_snapshot_on_result

        session = _song_b_session()
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        result = persist_snapshot_on_result({"ok": True}, snap)
        self.assertEqual(result.get("song_source_name"), "Song B")
        self.assertEqual(result.get("display_key"), "Eb")
        self.assertIn("Cm7", (result.get("analysis_context_snapshot") or {}).get("target_chords") or [])
        # Ambient later changes to Song A — historical snap stays Song B.
        later = apply_snapshot_to_analysis_ctx(
            {"song": "Song A", "display_key": "G", "target_chords": ["Gmaj7"]},
            result["analysis_context_snapshot"],
        )
        self.assertEqual(later["display_key"], "Eb")
        self.assertIn("Cm7", later["target_chords"])


class HarmonyWithoutNamedFormTests(unittest.TestCase):
    def _flat_song_b_session(self) -> dict:
        return _song_b_session(
            **{
                ANALYSIS_SONG_SOURCE_ID_KEY: "custom::Song Flat B",
                ANALYSIS_SONG_SOURCE_NAME_KEY: "Song Flat B",
                CPL_SAVED_KEY: {
                    "Song Flat B": {
                        "name": "Song Flat B",
                        "original_key_center": "Eb",
                        "bpm": 92,
                        "time_signature": "4/4",
                        "original_sections": {},
                        "chords": ["Cm7", "Fm7", "Bb7", "Ebmaj7"],
                    },
                    "Song A": {
                        "name": "Song A",
                        "original_key_center": "G",
                        "original_sections": {
                            "A": [{"chord": "Gmaj7"}, {"chord": "Em7"}],
                        },
                    },
                },
            }
        )

    def test_flat_progression_uses_real_harmony_without_inventing_form(self) -> None:
        from analysis_coach_quality import has_song_form_context, has_song_harmony_context
        from recording_analysis import build_practice_plan
        from multitrack_upload_analysis import build_target_layer_focus_analysis

        session = self._flat_song_b_session()
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        song_ctx = selected_song_analysis_context(session, snapshot=snap)
        self.assertEqual(song_ctx["source_id"], "custom::Song Flat B")
        self.assertEqual(song_ctx["key"], "Eb")
        self.assertIn("Cm7", song_ctx["chord_progression"])
        self.assertEqual(song_ctx["sections"], {})
        self.assertTrue(song_ctx["has_song_harmony"])
        self.assertFalse(song_ctx["has_song_form"])

        merged = apply_snapshot_to_analysis_ctx(
            {"display_key": "G", "target_chords": ["Gmaj7"], "sections": {"Verse": ["Gmaj7"]}},
            snap,
        )
        self.assertEqual(merged["display_key"], "Eb")
        self.assertIn("Cm7", merged["target_chords"])
        self.assertEqual(merged.get("sections"), {})
        self.assertTrue(has_song_harmony_context(merged))
        self.assertFalse(has_song_form_context(merged))

        class _F:
            tempo = 81.0

        plan = build_practice_plan(
            {
                "timing": 60,
                "pitch": 40,
                "technique": 65,
                "groove": 68,
                "musicality": 70,
                "confidence": 72,
                "tone": 66,
            },
            {
                **merged,
                "instrument": "Alto Saxophone",
                "song": "Song Flat B",
                "song_source_type": SONG_SOURCE_CUSTOM,
                "recording_type": RECORDING_TYPE_PRACTICE,
                "practice_focuses": ["Scales"],
            },
            _F(),
        )
        joined = " | ".join(plan).lower()
        self.assertIn("cm7", joined)
        self.assertIn("eb", joined)
        self.assertNotIn("g major scale", joined)
        self.assertNotIn("verse", joined)
        self.assertNotIn("chorus", joined)
        self.assertNotIn("bridge", joined)

        blocks = build_target_layer_focus_analysis(
            features={"pitch_note": "G3"},
            scores={"tone": 70, "technique": 72, "musicality": 88},
            categories={"technique": {"tips": ["Long tones 60s"], "findings": []}},
            ctx={
                **merged,
                "recording_type": RECORDING_TYPE_MT_LAYER,
                "instruments": ["Alto Saxophone"],
                "target_layer": "Alto Saxophone",
                "instrument_focuses": {"Alto Saxophone": ["Scales"]},
                "song": "Song Flat B",
                "selected_song_analysis_context": song_ctx,
            },
            musical_metrics={"scale_adherence": 61, "chord_tone_accuracy": 55},
        )
        scales = next(b for b in blocks if b.get("focus") == "Scales")
        findings = " ".join(scales.get("findings") or []).lower()
        self.assertIn("eb", findings)
        self.assertIn("cm7", findings)
        self.assertIn("flat progression", findings)
        self.assertIn("no named verse/chorus", findings)
        self.assertNotIn("loop verse", findings)
        self.assertNotIn("loop chorus", findings)
        self.assertNotIn("long tones 60s", findings)

    def test_named_sections_allow_section_aware_advice(self) -> None:
        from recording_analysis import build_practice_plan

        class _F:
            tempo = 81.0

        plan = build_practice_plan(
            {
                "timing": 60,
                "pitch": 40,
                "technique": 65,
                "groove": 68,
                "musicality": 70,
                "confidence": 72,
                "tone": 66,
            },
            {
                "instrument": "Alto Saxophone",
                "display_key": "Eb",
                "song": "Song B",
                "song_source_type": SONG_SOURCE_CUSTOM,
                "recording_type": RECORDING_TYPE_PRACTICE,
                "sections": {
                    "Verse": ["Cm7", "Fm7"],
                    "Bridge": ["Abmaj7", "G7"],
                },
                "target_chords": ["Cm7", "Fm7", "Abmaj7", "G7"],
                "practice_focuses": ["Scales"],
            },
            _F(),
        )
        joined = " | ".join(plan).lower()
        self.assertIn("loop the first eight bars of verse", joined)
        self.assertTrue("bridge" in joined or "verse" in joined)
        self.assertNotIn("2 octaves, even subdivisions", joined)

    def test_other_stays_generic_exercise(self) -> None:
        from analysis_coach_quality import has_song_form_context, has_song_harmony_context
        from recording_analysis import build_practice_plan

        ctx = {
            "instrument": "Alto Saxophone",
            "display_key": "",
            "song": "Free long tones",
            "song_source_type": SONG_SOURCE_OTHER,
            "recording_type": RECORDING_TYPE_PRACTICE,
            "sections": {},
            "target_chords": [],
            "practice_focuses": ["Tone"],
        }
        self.assertFalse(has_song_harmony_context(ctx))
        self.assertFalse(has_song_form_context(ctx))

        class _F:
            tempo = 72.0

        plan = " | ".join(
            build_practice_plan(
                {
                    "timing": 70,
                    "pitch": 55,
                    "technique": 60,
                    "groove": 68,
                    "musicality": 70,
                    "confidence": 72,
                    "tone": 66,
                },
                ctx,
                _F(),
            )
        ).lower()
        self.assertIn("2 octaves", plan)
        self.assertIn("drone", plan)
        self.assertNotIn("cm7", plan)

    def test_stable_source_id_survives_persist_and_reload(self) -> None:
        from recording_analysis_context import persist_snapshot_on_result

        session = self._flat_song_b_session()
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        self.assertEqual(snap.get("song_source_id"), "custom::Song Flat B")
        song_ctx = snap.get("selected_song_analysis_context") or {}
        self.assertEqual(song_ctx.get("source_id"), "custom::Song Flat B")
        result = persist_snapshot_on_result({"ok": True}, snap)
        self.assertEqual(result.get("song_source_id"), "custom::Song Flat B")
        reloaded = apply_snapshot_to_analysis_ctx({}, result["analysis_context_snapshot"])
        self.assertEqual(reloaded.get("song_source_id"), "custom::Song Flat B")
        nested = reloaded.get("selected_song_analysis_context") or {}
        self.assertEqual(nested.get("source_id"), "custom::Song Flat B")
        self.assertTrue(nested.get("has_song_harmony"))
        self.assertFalse(nested.get("has_song_form"))

    def test_ambient_song_a_cannot_replace_flat_song_b(self) -> None:
        session = self._flat_song_b_session()
        snap = attach_selected_song_harmony_to_snapshot(
            session, build_analysis_context_snapshot(session)
        )
        merged = apply_snapshot_to_analysis_ctx(
            {
                "song": "Song A",
                "display_key": "G",
                "sections": {"Verse": ["Gmaj7"], "Chorus": ["Em7"]},
                "target_chords": ["Gmaj7", "Em7"],
            },
            snap,
        )
        self.assertEqual(merged["song"], "Song Flat B")
        self.assertEqual(merged["display_key"], "Eb")
        self.assertIn("Cm7", merged["target_chords"])
        self.assertNotIn("Gmaj7", merged["target_chords"])
        self.assertEqual(merged.get("sections"), {})
        self.assertNotIn("Verse", merged.get("sections") or {})


if __name__ == "__main__":
    unittest.main()
