"""MC4 — "Passes of the span" is the Mission's own, like the tempo.

Reproduced: the recorder kept its pass count in ``backing_track_loops`` — the Backing page's
widget key. It held while the recorder was on screen, but after a trip to Upload Analysis the
key was gone and the control came back at the Backing default (2 → 4); and every recorder run
overwrote the Backing page's own loop preference with the Mission's count.
"""

from __future__ import annotations

import unittest
from unittest import mock

from mission_exact_chord_backing import generate_exact_chord_backing_wav
from mission_live_recording_mix import build_live_recording_previews, wav_duration_sec
from mission_practice_context import (
    MISSION_BACKING_SOUNDING_SPAN_KEY,
    MISSION_RECORDING_SEAL_KEY,
    MissionPracticeContext,
    ensure_mission_practice_context,
    seal_recording_context,
    set_mission_passes,
    validate_analysis_mission_context,
)
from mission_span_take import audio_fp, run_span_take_analysis
from tests.test_mc4_mission_tempo_sync import IIVI, TWO, _Env, _mission, _record_live, _tone_wav


class _PassesEnv(_Env):
    """Backing renderer that records the passes and returns a WAV of the matching length."""

    def __enter__(self):
        super().__enter__()
        self.passes: list[int] = []

        def render(chords, *, bpm, loops, **_k):
            self.passes.append(int(loops))
            return _tone_wav(len(chords) * int(loops) * 4 * 60.0 / bpm, 0.3)

        self._s.enter_context(mock.patch("backing_audio.generate_backing_track", render))
        return self


def _leave_missions(s):
    """Upload Analysis round trip: the Backing page widget key is not kept."""
    s.pop("backing_track_loops", None)


class TestMissionPasses(unittest.TestCase):
    def _check(self, chords, target):
        with _PassesEnv() as env:
            s = _mission(chords)
            s["backing_track_loops"] = 4  # the Backing page's preference
            set_mission_passes(s, 1)
            wav1, _ = generate_exact_chord_backing_wav(s)
            set_mission_passes(s, target)
            self.assertNotIn("mission_exact_backing_wav", s)  # the 1-pass backing is gone
            self.assertNotIn(MISSION_BACKING_SOUNDING_SPAN_KEY, s)
            self.assertEqual(s["backing_track_loops"], 4)  # Backing preference untouched
            _leave_missions(s)
            ctx = ensure_mission_practice_context(s)
            self.assertEqual((ctx.loops, ctx.span["loops"]), (target, target))
            wav, _ = generate_exact_chord_backing_wav(s)
            self.assertEqual(env.passes, [1, target])
            bpm = ctx.tempo_bpm
            self.assertAlmostEqual(wav_duration_sec(wav1), len(chords) * 4 * 60 / bpm, places=1)
            self.assertAlmostEqual(wav_duration_sec(wav), len(chords) * target * 4 * 60 / bpm, places=1)

    def test_two_chord_1_to_2(self) -> None:
        self._check(TWO, 2)

    def test_three_chord_1_to_3(self) -> None:
        self._check(IIVI, 3)

    def test_rerun_and_round_trip_keep_the_count(self) -> None:
        with _PassesEnv():
            s = _mission(IIVI)
            set_mission_passes(s, 3)
            for _ in range(3):
                s["backing_track_loops"] = 4  # Backing page state re-applied
                self.assertEqual(ensure_mission_practice_context(s).loops, 3)
                _leave_missions(s)
                self.assertEqual(ensure_mission_practice_context(s).loops, 3)

    def test_sealed_take_preview_and_analysis_use_the_count(self) -> None:
        with _PassesEnv():
            s = _mission(TWO)
            set_mission_passes(s, 2)
            backing, _ = generate_exact_chord_backing_wav(s)
            audio, take = _record_live(s, ensure_mission_practice_context(s).tempo_bpm)
            sealed = MissionPracticeContext.from_dict(s[MISSION_RECORDING_SEAL_KEY])
            self.assertEqual((sealed.loops, sealed.span["loops"]), (2, 2))
            self.assertEqual(take["span"]["loops"], 2)
            self.assertEqual(take["alignment"]["detail"]["loop_count"], 2)
            build_live_recording_previews(s, audio, backing_wav=backing, bpm=sealed.tempo_bpm, meter="4/4",
                                          backing_gain=0.65)
            self.assertAlmostEqual(s["_mission_live_mix_diag"]["backing_sec"], 2 * 2 * 4 * 60 / sealed.tempo_bpm, places=1)
            _leave_missions(s)
            self.assertEqual(validate_analysis_mission_context(s), (True, ""))
            result = run_span_take_analysis(s, dict(take, audio_fp=audio_fp(audio)), audio)
            self.assertEqual(len(result["loop_scores"]), 2)  # both recorded passes in the window

    def test_song_switch_isolation(self) -> None:
        with _PassesEnv() as env:
            s = _mission(IIVI)
            set_mission_passes(s, 3)
            env.song = "song-B"
            s["backing_track_loops"] = 2
            self.assertEqual(ensure_mission_practice_context(s, force=True).loops, 2)

    def test_untouched_mission_keeps_the_existing_default(self) -> None:
        with _PassesEnv():
            s = _mission(TWO)
            s["backing_track_loops"] = 4
            self.assertEqual(ensure_mission_practice_context(s, force=True).loops, 4)

    def test_single_chord_loop_bars(self) -> None:
        with _PassesEnv():
            s = _mission([], single=True)
            set_mission_passes(s, 3)
            _leave_missions(s)
            ctx = ensure_mission_practice_context(s)
            self.assertIsNone(ctx.span)
            self.assertEqual(ctx.loops, 3)
            seal_recording_context(s, association="live_record_start")
            self.assertEqual(MissionPracticeContext.from_dict(s[MISSION_RECORDING_SEAL_KEY]).loops, 3)

    def test_control_callback_sets_count_without_touching_backing_preference(self) -> None:
        from mission_exact_chord_backing_ui import _on_mission_passes_change

        with _PassesEnv():
            s = _mission(TWO)
            s["backing_track_loops"] = 6
            s["improv_mission_live_span_backing_loops"] = 2
            _on_mission_passes_change(s, "improv_mission_live_span_backing_loops")
            self.assertEqual(ensure_mission_practice_context(s).span["loops"], 2)
            self.assertEqual(s["backing_track_loops"], 6)


if __name__ == "__main__":
    unittest.main()
