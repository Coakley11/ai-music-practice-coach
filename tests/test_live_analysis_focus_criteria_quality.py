"""Live-analysis quality: Focus blocks, criteria, artist ownership, tempo/harmony safety."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from mission_analysis import score_missions
from multitrack_upload_analysis import build_target_layer_focus_analysis
from recording_analysis import (
    _chord_tone_coaching_hint,
    _meter_aware_tempo_delta,
    _pitch_analysis,
    _plan_bpm,
    _timing_analysis,
    build_practice_plan,
)
from recording_analysis_context import (
    ANALYSIS_SONG_SOURCE_ID_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    build_analysis_context_snapshot,
    selected_song_analysis_context,
    split_song_title_artist,
)


class ArtistOwnershipTests(unittest.TestCase):
    def test_split_title_artist(self) -> None:
        title, artist = split_song_title_artist("Perfect — Ed Sheeran")
        self.assertEqual(title, "Perfect")
        self.assertEqual(artist, "Ed Sheeran")

    def test_upload_perfect_does_not_inherit_mayer(self) -> None:
        session = {
            "selected_song": {"title": "Gravity", "artist": "John Mayer"},
            "song": "Gravity",
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Perfect — Ed Sheeran",
            ANALYSIS_SONG_SOURCE_ID_KEY: "catalog::perfect",
            ANALYSIS_SONG_SOURCE_TYPE_KEY: "Catalog Song",
        }
        snap = build_analysis_context_snapshot(session)
        self.assertIn("Perfect", snap.get("song_source_name") or "")
        self.assertEqual(snap.get("song_artist"), "Ed Sheeran")
        self.assertNotIn("Mayer", snap.get("song_artist") or "")
        ctx = selected_song_analysis_context(session, snapshot=snap)
        self.assertEqual(ctx.get("artist"), "Ed Sheeran")
        self.assertNotIn("Mayer", (ctx.get("artist") or "") + (ctx.get("title") or ""))


class PracticeFocusBlockTests(unittest.TestCase):
    def _features(self):
        return SimpleNamespace(
            onset_strength_mean=1.1,
            onset_density=1.8,
            groove_tightness=0.48,
            spectral_centroid_mean=2100.0,
            dyn_flatness=0.35,
            dyn_range=0.08,
            pitch_cents_std=22.0,
            pitch_note="B3",
        )

    def test_four_focuses_render_four_blocks(self) -> None:
        focuses = ["Articulation", "Scales", "Tone", "Dynamics"]
        blocks = build_target_layer_focus_analysis(
            features=self._features(),
            scores={"technique": 68, "tone": 70, "timing": 60, "musicality": 55, "pitch": 40},
            categories={
                "technique": {"findings": ["Clear tongued attacks"]},
                "tone": {"findings": ["Stable spectral color"]},
                "timing": {"findings": []},
                "musicality": {"findings": []},
            },
            ctx={
                "instruments": ["Flute"],
                "target_layer": "Flute",
                "practice_focuses": focuses,
                "recording_type": "Over a Backing Track",
                "display_key": "G major",
                "target_chords": ["G", "D/F#", "Em7", "D"],
                "selected_song_analysis_context": {
                    "title": "Perfect",
                    "artist": "Ed Sheeran",
                    "key": "G major",
                    "has_song_harmony": True,
                    "has_song_form": True,
                    "chord_progression": ["G", "D/F#", "Em7", "D"],
                    "sections": {"Verse": ["G", "D/F#"], "Chorus": ["Em7", "D"]},
                },
            },
            musical_metrics={
                "scale_adherence": 74,
                "chord_tone_accuracy": 61,
                "guide_tone_usage": 48,
            },
        )
        labels = [str(b.get("focus")) for b in blocks]
        self.assertEqual(labels, focuses)
        by = {b["focus"]: b for b in blocks}

        art = " ".join(by["Articulation"].get("findings") or []).lower()
        self.assertTrue("attack" in art or "onset" in art)

        tone = " ".join(by["Tone"].get("findings") or []).lower()
        self.assertTrue("spectral" in tone or "brightness" in tone or "centroid" in tone)

        dyn = " ".join(by["Dynamics"].get("findings") or []).lower()
        self.assertTrue("dynamic" in dyn or "rms" in dyn or "flatness" in dyn or "energy" in dyn)

        scales = " ".join(by["Scales"].get("findings") or []).lower()
        self.assertIn("g major", scales)
        self.assertTrue("chord" in scales or "scale" in scales or "harmonic" in scales)
        self.assertNotIn("embouchure", scales)
        self.assertNotIn("long tone", scales)
        self.assertTrue("mixed" in scales or "backing" in scales)


class TempoMeterTests(unittest.TestCase):
    def test_six_eight_incompatible_subdivision_not_naive_rush(self) -> None:
        note, delta = _meter_aware_tempo_delta(120, 95, "6/8")
        self.assertTrue(note)
        self.assertTrue(delta is None or delta == 0)
        self.assertNotIn("25 BPM", note)
        joined = note.lower()
        self.assertTrue(
            "cautious" in joined
            or "subdivision" in joined
            or "consistent" in joined
            or "mapping" in joined
            or "beat unit" in joined
        )

    def test_comparable_tempo_still_reports_delta(self) -> None:
        note, delta = _meter_aware_tempo_delta(100, 95, "4/4")
        self.assertEqual(note, "")
        self.assertEqual(delta, 5)


class ChordQualityCoachingTests(unittest.TestCase):
    def test_triads_do_not_invent_sevenths(self) -> None:
        hint = _chord_tone_coaching_hint(["G", "D/F#", "Em7", "D"])
        self.assertIn("G: root/3rd/5th", hint)
        self.assertIn("D/F#: root/3rd/5th", hint)
        self.assertIn("Em7:", hint)
        em7_part = hint.split("Em7:")[1].split(";")[0]
        self.assertIn("7th", em7_part)
        self.assertNotIn("G: 3rd+7th", hint)

    def test_plan_bpm_anchors_to_reference(self) -> None:
        self.assertEqual(_plan_bpm({"reference_bpm": 95}, 80), 95)
        plan = build_practice_plan(
            {
                "timing": 50,
                "pitch": 40,
                "technique": 60,
                "groove": 55,
                "musicality": 50,
                "confidence": 50,
                "tone": 55,
            },
            {
                "instrument": "Flute",
                "reference_bpm": 95,
                "practice_bpm": 95,
                "display_key": "G major",
                "song": "Perfect — Ed Sheeran",
                "target_chords": ["G", "D/F#", "Em7", "D"],
                "sections": {"Chorus": ["Em7", "D"]},
                "recording_type": "Over a Backing Track",
                "practice_focuses": ["Scales"],
                "evaluating_criteria_labels": ["Scale/mode usage"],
            },
            SimpleNamespace(tempo=120, duration=30.0),
        )
        joined = " | ".join(plan)
        self.assertNotRegex(joined, r"@ (98|100) BPM")
        self.assertTrue("95 BPM" in joined or "80 BPM" in joined or "81 BPM" in joined)


class FormEvidenceGateTests(unittest.TestCase):
    def test_chorus_metadata_is_prospective_not_observed(self) -> None:
        cat = _timing_analysis(
            SimpleNamespace(
                tempo=95,
                beat_interval_cv=0.08,
                tempo_drift_pct=2.0,
                groove_tightness=0.5,
                onset_density=1.2,
            ),
            {
                "reference_bpm": 95,
                "time_signature": "6/8",
                "sections": {"Intro": ["G"], "Verse": ["G"], "Chorus": ["Em7"]},
            },
        )
        findings = " ".join(cat.get("findings") or []).lower()
        self.assertIn("chorus", findings)
        self.assertTrue("prospective" in findings or "when you reach" in findings)
        self.assertNotIn("your chorus entrance rushed", findings)


class CriteriaEvidenceTests(unittest.TestCase):
    def test_score_missions_emits_evidence_per_criterion(self) -> None:
        results = score_missions(
            ["scale_connection", "articulation", "dynamic_contrast"],
            {
                "scale_adherence": 70,
                "phrase_contour_variety": 60,
                "melodic_diversity": 55,
                "articulation": 62,
                "rhythmic_diversity": 50,
                "groove_consistency": 58,
                "dynamic_contrast": 66,
                "phrase_pacing": 54,
                "musical_expression": 57,
            },
            {
                "song": "Perfect — Ed Sheeran",
                "display_key": "G major",
                "instrument": "Flute",
                "recording_type": "Over a Backing Track",
            },
        )
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertTrue(r.get("label"))
            self.assertTrue(r.get("observed_evidence"))
            self.assertTrue(r.get("assessment"))

        limited = score_missions(
            ["guide_tones"],
            {"melodic_diversity": 80},
            {"song": "Perfect", "display_key": "G major", "instrument": "Flute"},
        )
        self.assertEqual(len(limited), 1)
        self.assertTrue(limited[0].get("limited_evidence"))
        self.assertIsNone(limited[0].get("score"))


class PitchHarmonySeparationTests(unittest.TestCase):
    def test_center_pitch_not_treated_as_key(self) -> None:
        cat = _pitch_analysis(
            SimpleNamespace(
                pitch_note="B3",
                voiced_ratio=0.7,
                pitch_cents_std=30.0,
                pitch_sharp_bias=0.0,
            ),
            "Flute",
            {
                "display_key": "G major",
                "recording_type": "Over a Backing Track",
                "backing_track_context": True,
            },
        )
        findings = " ".join(cat.get("findings") or []).lower()
        self.assertIn("not the selected song key", findings)
        self.assertIn("mixed-recording", findings)
        self.assertNotIn("key is b", findings)


if __name__ == "__main__":
    unittest.main()
