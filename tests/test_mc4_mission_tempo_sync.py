"""MC4 — the Mission recorder tempo is one tempo everywhere.

Human failure: Mission at 82 BPM → recorder slider 82 → 129 → recorded at 129 → the summary
still said 82, Performance + Backing did not line up, and Run AI Coaching refused with "Take
context changed: tempo changed from 129 to 82 BPM".

Cause: the slider wrote only ``backing_track_bpm``, a key owned by the Backing page whose
canonical state re-applies it (82) at the start of every run. The Mission context therefore
flipped 82 ↔ 129 within each run and was 82 wherever the slider was not rendered (Upload
Analysis).
"""

from __future__ import annotations

import io
import unittest
import wave
from contextlib import ExitStack
from unittest import mock

import numpy as np

import mission_span_recording_context as src
from mission_exact_chord_backing import generate_exact_chord_backing_wav
from mission_live_recording_mix import build_live_recording_previews, estimate_backing_offset_samples
from mission_practice_context import (
    MISSION_BACKING_SOUNDING_SPAN_KEY,
    MISSION_RECORDING_SEAL_KEY,
    MissionPracticeContext,
    enrich_analysis_context,
    ensure_mission_practice_context,
    mission_capture_allowed,
    recording_context_stale_warning,
    seal_recording_context,
    set_mission_tempo,
    ui_backing_chord_mismatch,
    validate_analysis_mission_context,
)
from mission_span_take import CURRENT_AUDIO_FP_KEY, audio_fp, record_span_take, run_span_take_analysis
from tests.mc4_audio_fixtures import phrase_wav
from tests.test_mc4_span_recording import GOLDEN_SESSION, SCOPE_KEY, _stage

IIVI = ["Gm7", "C7", "Fmaj7"]
TWO = ["Gm7", "C7"]


def _tone_wav(sec: float, amp: float, sr: int = 22050) -> bytes:
    t = np.arange(int(sec * sr)) / sr
    x = (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return out.getvalue()


class _Env:
    """Live song / key resolvers, Mission song id, and a backing renderer that records its BPM."""

    def __init__(self, song="song-A"):
        self.song = song
        self.rendered: list[int] = []

    def __enter__(self):
        import mission_exact_chord_backing

        mission_exact_chord_backing._WAV_CACHE.clear()  # renders are cached per span/tempo across tests
        self._s = ExitStack()
        self._s.enter_context(mock.patch.object(src, "_song_session", lambda s: self.song))
        self._s.enter_context(mock.patch.object(src, "_live_practice_key", lambda s: "F"))
        self._s.enter_context(mock.patch.object(src, "_live_chart_key", lambda s: "F"))
        self._s.enter_context(mock.patch("mission_practice_context._tempo_song", lambda s: self.song))
        self._s.enter_context(mock.patch("mission_span_backing._song_session", lambda s: self.song))
        self._s.enter_context(mock.patch("backing_context.get_backing_context", lambda s: None))

        def render(chords, *, bpm, **_k):
            self.rendered.append(int(bpm))
            return _tone_wav(len(chords) * 4 * 60.0 / bpm, 0.3)

        self._s.enter_context(mock.patch("backing_audio.generate_backing_track", render))
        self._s.enter_context(mock.patch("mission_analysis_ui.is_analysis_criteria_locked", lambda s: True))
        return self

    def __exit__(self, *exc):
        self._s.close()


def _mission(chords, *, single=False):
    s = dict(GOLDEN_SESSION, backing_track_bpm=82)
    s.pop("improv_style_meta", None)
    if single:
        s[SCOPE_KEY] = "single"
    else:
        _stage(s, chords)
    ensure_mission_practice_context(s, force=True)
    return s


def _canonical_backing_reset(s):
    """What the Backing page's canonical state does at the start of every run."""
    s["backing_track_bpm"] = 82


def _record_live(s, bpm):
    """Record Live: seal at record start, take audio, hand off (live source) and select it."""
    seal_recording_context(s, association="live_record_start")
    audio = phrase_wav([("Bb4", 0, 1), ("A4", 1, 1), ("G4", 2, 1), ("F4", 3, 1), ("E4", 4, 2), ("G4", 6, 2)],
                       bpm=bpm, loop_beats=8, repeat=2)
    take = record_span_take(s, audio_bytes=audio, source="live")
    s[CURRENT_AUDIO_FP_KEY] = audio_fp(audio)
    return audio, take


class TestMissionTempoIsOneTempo(unittest.TestCase):
    def _check_current_change(self, chords):
        with _Env() as env:
            s = _mission(chords)
            self.assertEqual(ensure_mission_practice_context(s).tempo_bpm, 82)
            generate_exact_chord_backing_wav(s)  # backing armed at 82
            self.assertEqual(s[MISSION_BACKING_SOUNDING_SPAN_KEY]["bpm"], 82)

            set_mission_tempo(s, 129)  # the slider's on_change
            # The 82 backing is gone: not cached as current, not sounding.
            self.assertNotIn("mission_exact_backing_wav", s)
            self.assertNotIn(MISSION_BACKING_SOUNDING_SPAN_KEY, s)

            _canonical_backing_reset(s)  # next run: Backing page state re-applies 82
            ctx = ensure_mission_practice_context(s)
            self.assertEqual(ctx.tempo_bpm, 129)
            self.assertEqual(ctx.span["bpm"], 129)
            self.assertAlmostEqual(ctx.span["loop_sec"], len(chords) * 4 * 60 / 129, places=2)
            self.assertEqual(dict(src.span_summary_rows(ctx.span))["Tempo"], "129 BPM")
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))

            generate_exact_chord_backing_wav(s)  # Play
            self.assertEqual(env.rendered, [82, 129])
            self.assertEqual(s[MISSION_BACKING_SOUNDING_SPAN_KEY]["bpm"], 129)
            self.assertEqual(ui_backing_chord_mismatch(s), (False, ""))

    def test_two_chord_slider_change_reaches_everything(self) -> None:
        self._check_current_change(TWO)

    def test_three_chord_slider_change_reaches_everything(self) -> None:
        self._check_current_change(IIVI)

    def test_record_after_slider_change_seals_129(self) -> None:
        with _Env():
            s = _mission(IIVI)
            s["mission_exact_backing_count_in"] = True
            set_mission_tempo(s, 129)
            _canonical_backing_reset(s)
            generate_exact_chord_backing_wav(s)
            _audio, take = _record_live(s, 129)
            sealed = MissionPracticeContext.from_dict(s[MISSION_RECORDING_SEAL_KEY])
            self.assertEqual((sealed.tempo_bpm, sealed.span["bpm"]), (129, 129))
            self.assertEqual(take["span"]["bpm"], 129)
            self.assertAlmostEqual(take["alignment"]["offset_sec"], 4 * 60 / 129, places=3)  # 1-bar count-in at 129
            self.assertEqual(recording_context_stale_warning(s), "")

    def test_preview_uses_the_129_backing_and_take_timeline(self) -> None:
        with _Env():
            s = _mission(TWO)
            s["mission_exact_backing_count_in"] = True
            set_mission_tempo(s, 129)
            _canonical_backing_reset(s)
            backing, _ = generate_exact_chord_backing_wav(s)
            dry = _tone_wav(6.0, 0.02)  # a quiet flute line
            out = build_live_recording_previews(s, dry, backing_wav=backing, bpm=129, meter="4/4", backing_gain=0.65)
            diag = s["_mission_live_mix_diag"]
            self.assertAlmostEqual(diag["offset_samples"], 44100 * 4 * 60 / 129, delta=5)  # first downbeat at 129
            self.assertEqual(estimate_backing_offset_samples(s, bpm=129, meter="4/4"), diag["offset_samples"])
            self.assertGreater(diag["performance_boost"], 1.0)  # performance lifted in the preview…
            self.assertEqual(out["dry"], dry)  # …never in the take used for analysis
            self.assertTrue(diag["backing_clearly_audible"])

    def test_run_ai_coaching_sees_129_and_proceeds(self) -> None:
        with _Env():
            s = _mission(IIVI)
            set_mission_tempo(s, 129)
            _canonical_backing_reset(s)
            generate_exact_chord_backing_wav(s)
            audio, take = _record_live(s, 129)
            _canonical_backing_reset(s)  # Upload Analysis run: the slider is not rendered there
            self.assertEqual(validate_analysis_mission_context(s), (True, ""))
            ctx = enrich_analysis_context(s, {})
            self.assertEqual(ctx["practice_bpm"], 129)
            result = run_span_take_analysis(s, dict(take, audio_fp=audio_fp(audio)), audio)
            self.assertEqual(result["bpm"], 129)  # chord boundaries on the 129 grid

    def test_genuine_later_change_keeps_the_take_at_129(self) -> None:
        with _Env():
            s = _mission(TWO)
            set_mission_tempo(s, 129)
            generate_exact_chord_backing_wav(s)
            audio, take = _record_live(s, 129)
            set_mission_tempo(s, 82)  # the player deliberately goes back to 82 afterwards
            self.assertEqual(ensure_mission_practice_context(s).tempo_bpm, 82)
            self.assertIn("tempo changed from 129 to 82", recording_context_stale_warning(s))  # still reported…
            self.assertEqual(validate_analysis_mission_context(s), (True, ""))  # …but the take stays analyzable
            self.assertEqual(enrich_analysis_context(s, {})["practice_bpm"], 129)
            self.assertEqual(run_span_take_analysis(s, dict(take, audio_fp=audio_fp(audio)), audio)["bpm"], 129)

    def test_single_chord_tempo_follows_slider_and_keeps_its_stale_rule(self) -> None:
        with _Env():
            s = _mission([], single=True)
            set_mission_tempo(s, 129)
            _canonical_backing_reset(s)
            ctx = ensure_mission_practice_context(s)
            self.assertIsNone(ctx.span)
            self.assertEqual(ctx.tempo_bpm, 129)
            seal_recording_context(s, association="live_record_start")
            set_mission_tempo(s, 82)
            ok, msg = mission_capture_allowed(s, require_mission_workflow=True, capture_path="analysis")
            self.assertFalse(ok)  # one-chord takes: unchanged behaviour
            self.assertIn("tempo changed from 129 to 82", msg)

    def test_tempo_belongs_to_the_song_it_was_set_on(self) -> None:
        with _Env() as env:
            s = _mission(IIVI)
            set_mission_tempo(s, 129)
            env.song = "song-B"
            s["backing_track_bpm"] = 104  # song B's Backing tempo
            ctx = ensure_mission_practice_context(s, force=True)
            self.assertEqual(ctx.tempo_bpm, 104)

    def test_slider_callback_sets_the_mission_tempo(self) -> None:
        from mission_exact_chord_backing_ui import _on_mission_tempo_change

        with _Env():
            s = _mission(TWO)
            s["improv_mission_live_span_backing_bpm"] = 129
            _on_mission_tempo_change(s, "improv_mission_live_span_backing_bpm")
            _canonical_backing_reset(s)
            self.assertEqual(ensure_mission_practice_context(s).span["bpm"], 129)


if __name__ == "__main__":
    unittest.main()
