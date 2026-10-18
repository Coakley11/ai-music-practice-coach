"""MC4 — a Mission Recording is coached against its sealed Mission practice tempo, not the song's catalog tempo.

Review of an Autumn Leaves take: played at ~137 BPM with the Mission set to 136, the report still said
"song reference = 82 BPM", offered "Song-tempo ladder toward 82 BPM: 66 → 74 → 82" and recommended drills
at 70 BPM. Song reference tempo, Mission practice tempo and detected pulse are three different things.
"""

from __future__ import annotations

import unittest

import numpy as np

from mission_analysis import build_mission_recommendation
from mission_coaching_tempo import (
    coaching_target_tempo,
    mission_tempo,
    next_practice_tempo,
    practice_ladder,
    song_reference_tempo,
    tempo_relation_sentence,
)
from recording_analysis import AudioFeatures, _timing_analysis, build_practice_plan
from recording_analysis_ui import render_analysis_dashboard
from tests.test_mc4_flute_pitch_evidence import _features


def _ctx(mission=136, ref=82, **kw) -> dict:
    ctx = {"reference_bpm": ref, "practice_bpm": ref, "time_signature": "4/4", "instrument": "Flute",
           "song": "Autumn Leaves", "display_key": "Bm", "level": "Intermediate"}
    if mission is not None:
        ctx["mission_tempo_bpm"] = mission
    ctx.update(kw)
    return ctx


def _timing(tempo, **ctx_kw):
    out = _timing_analysis(_features(tempo=float(tempo), beat_interval_cv=0.08, tempo_drift_pct=0.0), _ctx(**ctx_kw))
    return " | ".join(out["findings"]), " | ".join(out["tips"])


class TestTempoAuthority(unittest.TestCase):
    def test_mission_tempo_wins_over_song_reference(self) -> None:
        ctx = _ctx(136, 82)
        self.assertEqual((mission_tempo(ctx), song_reference_tempo(ctx), coaching_target_tempo(ctx)), (136, 82, 136))
        plain = _ctx(None, 82)                                   # ordinary song analysis: unchanged
        self.assertEqual((mission_tempo(plain), coaching_target_tempo(plain)), (None, 82))
        self.assertIsNone(coaching_target_tempo({}))

    def test_ladder_and_next_tempo_derive_from_the_mission_tempo(self) -> None:
        self.assertEqual(practice_ladder(136), (122, 129, 136))
        self.assertEqual(next_practice_tempo(136, 90), 136)                  # strong timing: keep the tempo
        self.assertEqual(next_practice_tempo(136, 70), 129)                  # middling: ease off 5 %
        self.assertEqual(next_practice_tempo(136, 50), 122)                  # weak: 10 %
        self.assertEqual(next_practice_tempo(136, 90, "Beginner"), 129)      # level steps one tier easier
        self.assertEqual(next_practice_tempo(136, None), 136)
        self.assertGreaterEqual(next_practice_tempo(60, 10, "Beginner"), 55)  # floor

    def test_relation_sentences(self) -> None:
        self.assertEqual(
            tempo_relation_sentence(137, 136, 82, 1),
            "Your detected pulse (~137 BPM) is very close to the Mission practice tempo (136 BPM). The song's catalog "
            "reference is 82 BPM, but this take was intentionally practiced faster.")
        self.assertIn("practiced slower", tempo_relation_sentence(70, 70, 120, 0))
        self.assertEqual(tempo_relation_sentence(121, 120, 120, 1),
                         "Detected tempo ≈ 121 BPM is near the Mission practice tempo (120 BPM, also the song's reference tempo).")
        self.assertEqual(tempo_relation_sentence(137, 136, 82, None), "")    # subdivision caution handled by the caller


class TestTimingCoaching(unittest.TestCase):
    def test_song_82_mission_136_detected_137(self) -> None:
        findings, tips = _timing(137, mission=136, ref=82)
        self.assertIn("Your detected pulse (~137 BPM) is very close to the Mission practice tempo (136 BPM)", findings)
        self.assertIn("this take was intentionally practiced faster", findings)
        self.assertNotIn("above the reference", findings)
        self.assertNotIn("near the song reference", findings)
        self.assertIn("Practice ladder around 136 BPM: 122 → 129 → 136", tips)
        self.assertNotIn("66", tips)
        self.assertNotIn("toward 82", tips)
        self.assertNotIn("Song-tempo ladder", tips)

    def test_song_82_mission_100_detected_85_is_slow_for_the_mission(self) -> None:
        findings, tips = _timing(85, mission=100, ref=82)
        self.assertIn("15 BPM below the Mission practice tempo (100 BPM)", findings)
        self.assertIn("slow relative to the Mission target of 100 BPM", findings)
        self.assertIn("context only", findings)
        self.assertIn("Practice ladder around 100 BPM: 90 → 95 → 100", tips)
        self.assertNotIn("near the song reference", findings)

    def test_song_reference_equals_mission_tempo_stays_natural(self) -> None:
        findings, tips = _timing(121, mission=120, ref=120)
        self.assertIn("near the Mission practice tempo (120 BPM, also the song's reference tempo)", findings)
        self.assertNotIn("catalog reference", findings)
        self.assertIn("Practice ladder around 120 BPM: 108 → 114 → 120", tips)

    def test_without_a_mission_tempo_the_song_reference_still_applies(self) -> None:
        findings, tips = _timing(85, mission=None, ref=82)
        self.assertIn("near the song reference (82 BPM)", findings)
        self.assertIn("Song-tempo ladder toward 82 BPM: 66 → 74 → 82", tips)
        self.assertNotIn("Mission", findings + tips)

    def test_subdivision_caution_is_phrased_against_the_mission_tempo(self) -> None:
        findings, _tips = _timing(136, mission=68, ref=82)       # the detector is on the half-time pulse
        self.assertIn("Mission practice tempo (68 BPM)", findings)


class TestNextPractice(unittest.TestCase):
    def _plan(self, timing, **ctx_kw):
        f = _features(tempo=137.0)
        scores = {"timing": timing, "pitch": 80, "technique": 80, "groove": 80, "musicality": 80, "confidence": 80, "tone": 80}
        return " ".join(build_practice_plan(scores, _ctx(**ctx_kw), f))

    def test_drills_follow_the_mission_tempo_not_the_catalog(self) -> None:
        strong = self._plan(88, mission=136, ref=82)
        self.assertIn("@ 136 BPM", strong)
        self.assertNotIn("@ 70 BPM", strong)
        self.assertNotIn("@ 82 BPM", strong)
        weak = self._plan(55, mission=136, ref=82)
        self.assertIn("@ 122 BPM", weak)                                    # modest reduction from 136 — not 82
        self.assertNotIn(" 70 BPM", weak)

    def test_mission_recommendation_uses_the_mission_tempo(self) -> None:
        results = [{"label": "Chord-tone targeting", "score": 60, "improve_to": "Land the 3rds."}]
        rec = build_mission_recommendation(results, _ctx(136, 82), {"timing_stability": 85.0})
        self.assertIn("at 136 BPM", rec)
        rec_weak = build_mission_recommendation(results, _ctx(136, 82), {"timing_stability": 40.0})
        self.assertIn("at 122 BPM", rec_weak)
        legacy = build_mission_recommendation(results, _ctx(None, 82), {"timing_stability": 85.0})
        self.assertIn("at 70 BPM", legacy)                                  # ordinary analysis: unchanged (82 − 12)


class TestSealedTakeTempo(unittest.TestCase):
    def test_single_chord_take_keeps_the_tempo_it_was_recorded_at(self) -> None:
        from mission_practice_context import ensure_mission_practice_context, seal_recording_context, set_mission_tempo
        from recording_analysis_context import build_analysis_context_snapshot
        from tests.test_mc4_span_recording import GOLDEN_SESSION

        session = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording",
                       analysis_mission_parameters={"chord": "A", "mission_type": "Target tone drill"})
        set_mission_tempo(session, 136)
        seal_recording_context(session, association="live_record_take")
        set_mission_tempo(session, 100)                                      # the Mission is changed after recording
        self.assertEqual(ensure_mission_practice_context(session).tempo_bpm, 100)
        snap = build_analysis_context_snapshot(session, association="t")
        self.assertEqual(snap["mission_tempo_bpm"], 136)
        self.assertIsNone(snap["practice_bpm"])                              # the song reference is a separate field

    def test_span_take_uses_its_sealed_span_tempo(self) -> None:
        from recording_analysis_context import build_analysis_context_snapshot
        from mission_span_take import SPAN_TAKE_KEY
        from tests.test_mc4_span_recording import GOLDEN_SESSION, _World, _block

        block = _block(bpm=136)
        session = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording",
                       analysis_mission_parameters={"chord": "A", "mission_type": "Target tone drill"})
        session[SPAN_TAKE_KEY] = {"version": 1, "span": block, "source": "live", "audio_fp": "fpS", "song_session": "song-A"}
        session["_analysis_current_audio_fp"] = "fpS"
        with _World():
            snap = build_analysis_context_snapshot(session, association="test")
        self.assertEqual(snap["mission_tempo_bpm"], 136)
        self.assertEqual(snap["mission_span"]["bpm"], 136)

    def test_ordinary_song_analysis_has_no_mission_tempo(self) -> None:
        from recording_analysis_context import build_analysis_context_snapshot, apply_snapshot_to_analysis_ctx
        from tests.test_mc4_span_recording import GOLDEN_SESSION

        snap = build_analysis_context_snapshot(dict(GOLDEN_SESSION, analysis_recording_type="Practice take"), association="t")
        self.assertIsNone(snap["mission_tempo_bpm"])
        self.assertNotIn("mission_tempo_bpm", apply_snapshot_to_analysis_ctx({}, snap))

    def test_snapshot_tempo_reaches_the_analysis_context(self) -> None:
        from recording_analysis_context import apply_snapshot_to_analysis_ctx

        ctx = apply_snapshot_to_analysis_ctx({}, {"mission_tempo_bpm": 136, "practice_bpm": 82})
        self.assertEqual(mission_tempo(ctx), 136)


class TestReportSurface(unittest.TestCase):
    def test_report_shows_both_tempos_without_calling_either_wrong(self) -> None:
        result = {"ok": True, "coach_summary": "Solid take.", "biggest_issue": "tone", "next_focus": "Timing", "most_improved": "tone",
                  "instrument": "Flute", "duration": 10.0, "tempo": 137.0, "reference_bpm": 82, "mission_tempo_bpm": 136,
                  "scores": {"timing": 87, "pitch": 71, "technique": 77, "groove": 82, "musicality": 94, "confidence": 74, "tone": 66},
                  "categories": {}, "practice_plan": ["Loop at 136 BPM."]}
        html = render_analysis_dashboard(result)
        self.assertIn("~137 BPM detected", html)
        self.assertIn("Mission tempo 136 BPM", html)
        self.assertIn("Song reference 82 BPM", html)

    def test_coach_summary_names_the_mission_tempo_and_the_reference(self) -> None:
        import io
        import wave

        import recording_analysis as ra

        sr = 22050
        y = np.zeros(int(8 * sr), np.float32)
        for k in range(int(8 * 136 / 60)):                                  # a click track at 136 BPM
            i = int(k * 60 / 136 * sr)
            y[i:i + 400] += np.hanning(400).astype(np.float32) * 0.8
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((y * 32767).astype(np.int16).tobytes())
        ctx = _ctx(136, 82, recording_type="Mission Recording",
                   selected_song_analysis_context={"title": "Autumn Leaves", "key": "Bm", "meter": "4/4", "bpm": 82})
        result = ra.analyze_recording(buf.getvalue(), "take.wav", ctx)
        self.assertTrue(result["ok"])
        self.assertEqual((result["mission_tempo_bpm"], result["reference_bpm"]), (136, 82))
        self.assertIn("Mission practice tempo 136 BPM (song reference 82 BPM)", result["coach_summary"])
        self.assertNotIn("reference tempo 82 BPM", result["coach_summary"])
        timing = " ".join(result["categories"]["timing"]["findings"] + result["categories"]["timing"]["tips"])
        self.assertIn("Practice ladder around 136 BPM", timing)
        self.assertNotIn("toward 82", timing)


if __name__ == "__main__":
    unittest.main()
