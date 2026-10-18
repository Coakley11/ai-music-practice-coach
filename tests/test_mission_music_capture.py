"""Mission recording captures the whole instrument take (flute investigation).

Browser side: the Mission recorder asks for music capture (no echo cancellation / noise
suppression / AGC), scoped to its own Record button. App side: the take is kept exactly as
recorded — no trimming, gating or normalisation — from the recorder through the Upload
Analysis handoff to the analysis decode. (Browser MediaRecorder chunk / Stop behaviour is
covered by test_mission_music_capture_browser.py.)
"""

from __future__ import annotations

import io
import re
import unittest
import wave
from unittest import mock

import numpy as np

from mission_music_capture import ARM_WINDOW_MS, MUSIC_CAPTURE_CONSTRAINTS, music_capture_script, render_music_capture_mode

SR = 16000


def _flute(f: float, dur: float, amp: float) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    x = np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 5 * t)) + 0.18 * np.sin(4 * np.pi * f * t)
    env = np.minimum(1.0, np.minimum(t / 0.05, (dur - t) / 0.1))
    return (amp * x * env).astype(np.float32)


SEGMENTS = [  # (name, samples) — sustained, quiet sustained, rests, short notes, final long note
    ("lead", np.zeros(SR // 2, np.float32)),
    ("loud_sustain", _flute(440, 4.0, 0.5)),
    ("rest", np.zeros(SR, np.float32)),
    ("quiet_sustain", _flute(523.25, 4.0, 0.02)),  # ~ -28 dB
    ("rest2", np.zeros(SR, np.float32)),
    ("short_notes", np.concatenate([_flute(f, 0.25, 0.4) for f in (587, 659, 784, 659)])),
    ("final_long_note", _flute(440, 3.0, 0.35)),
]


def _wav(x: np.ndarray) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return out.getvalue()


def _performance() -> tuple[bytes, list[tuple[str, int, int]]]:
    spans, pos = [], 0
    for name, x in SEGMENTS:
        spans.append((name, pos, pos + x.size))
        pos += x.size
    return _wav(np.concatenate([x for _n, x in SEGMENTS])), spans


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


class TestMusicCaptureScript(unittest.TestCase):
    def test_constraints_are_music_friendly(self) -> None:
        self.assertEqual(MUSIC_CAPTURE_CONSTRAINTS,
                         {"echoCancellation": False, "noiseSuppression": False, "autoGainControl": False})
        js = music_capture_script(["improv_mission_live_span_live_mic"])
        self.assertIn('"echoCancellation": false', js)
        self.assertIn("voiceIsolation = false", js)  # where the browser has it
        self.assertIn('["improv_mission_live_span_live_mic"]', js)
        self.assertIn(str(ARM_WINDOW_MS), js)

    def test_scoped_to_mission_record_button_and_falls_back(self) -> None:
        js = music_capture_script(["k"])
        # Armed only by a Record click inside this recorder's mic widget; Stop is checked first
        # ("Stop recording" contains "record").
        self.assertIn("st-key-' + state.keys[i]", js)
        self.assertLess(js.index("/^stop/i"), js.index("/^record$/i"))
        self.assertIn("if (!armed) return original(c);", js)
        self.assertIn("OverconstrainedError", js)
        self.assertIn("return original(c);", js)
        self.assertNotRegex(js, r"exact\s*:")  # never a required constraint

    def test_render_uses_page_script_and_degrades(self) -> None:
        st = mock.MagicMock()
        self.assertTrue(render_music_capture_mode(st, mic_key="improv_mission_live_live_mic"))
        args, kwargs = st.html.call_args
        self.assertTrue(kwargs.get("unsafe_allow_javascript"))
        self.assertIn("improv_mission_live_live_mic", args[0])
        old = mock.MagicMock()
        old.html.side_effect = TypeError("unexpected keyword")
        self.assertFalse(render_music_capture_mode(old, mic_key="x"))
        self.assertFalse(render_music_capture_mode(object(), mic_key="x"))


class TestRecorderInstallsMusicCapture(unittest.TestCase):
    """Single-chord and span Missions record through the same Mission recorder, with music capture."""

    def _render(self, *, span: dict | None, key_prefix: str) -> list[dict]:
        import mission_recorder
        import mission_upload_recording_ui as ui

        calls: list[dict] = []
        st = mock.MagicMock()
        st.button.return_value = False
        st.file_uploader.return_value = None
        with mock.patch.object(ui, "_span_block", return_value=span),              mock.patch.object(ui, "_compact_summary", return_value=("Mission", "Bm")),              mock.patch.object(ui, "render_exact_chord_mission_backing_panel"),              mock.patch.object(ui, "ui_backing_chord_mismatch", return_value=(False, "")),              mock.patch.object(ui, "recording_context_stale_warning", return_value=""),              mock.patch.object(ui, "mission_capture_allowed", return_value=(True, "")),              mock.patch.object(ui, "seal_recording_context"),              mock.patch.object(ui, "ensure_mission_practice_context", return_value=None),              mock.patch.object(ui, "_render_span_summary"),              mock.patch.object(ui, "_render_span_file_upload"),              mock.patch.object(mission_recorder, "_COMPONENT", side_effect=lambda **k: calls.append(k)):
            ui.render_mission_live_recording_studio(st, {}, key_prefix=key_prefix)
        st.audio_input.assert_not_called()  # no separate st.audio_input recorder any more
        return calls

    def test_single_chord_and_span_use_the_same_music_capture_recorder(self) -> None:
        for span, prefix in ((None, "improv_mission_live"), ({"timeline": [{"chord": "Gm7"}]}, "improv_mission_live_span")):
            calls = self._render(span=span, key_prefix=prefix)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["key"], f"{prefix}_recorder")
            self.assertEqual(calls[0]["constraints"], MUSIC_CAPTURE_CONSTRAINTS)
            self.assertTrue(calls[0]["require_backing"])


class TestTakeIntegrityThroughApp(unittest.TestCase):
    def test_dry_take_is_kept_byte_for_byte(self) -> None:
        from mission_live_recording_mix import build_live_recording_previews, wav_duration_sec

        take, _spans = _performance()
        session: dict = {}
        out = build_live_recording_previews(session, take, backing_wav=None, bpm=82, meter="4/4", backing_gain=0.65)
        self.assertEqual(out["dry"], take)
        self.assertEqual(session["_mission_live_mic_dry"], take)
        self.assertAlmostEqual(session["_mission_live_mix_diag"]["dry_sec"], wav_duration_sec(take), places=3)

    def test_mixed_preview_never_replaces_the_dry_take(self) -> None:
        from mission_live_recording_mix import build_live_recording_previews

        take, _ = _performance()
        backing = _wav(_flute(110, 6.0, 0.3))
        session: dict = {}
        out = build_live_recording_previews(session, take, backing_wav=backing, bpm=82, meter="4/4", backing_gain=0.65)
        self.assertEqual(out["dry"], take)
        self.assertNotEqual(out["mixed"], take)

    def test_handoff_passes_the_exact_take(self) -> None:
        from mission_upload_handoff import handoff_mission_take_to_upload_analysis

        take, _ = _performance()
        session: dict = {}
        with mock.patch("mission_pending_upload_persistence.persist_mission_pending_upload_handoff",
                        return_value={"persistence_write": "ok", "cloud_confirmed": True}):
            ok, err = handoff_mission_take_to_upload_analysis(session, audio_bytes=take, filename="t.wav", source="live")
        self.assertTrue(ok, err)
        self.assertEqual(session["_analysis_prepared_upload"].getvalue(), take)
        self.assertEqual(session["last_analysis_audio"], take)

    def test_analysis_decode_keeps_sustains_rests_and_final_note(self) -> None:
        from recording_analysis import _load_audio

        take, spans = _performance()
        y, sr, _path = _load_audio(take, "take.wav")
        self.assertEqual(sr, SR)
        self.assertEqual(y.size, sum(x.size for _n, x in SEGMENTS))  # nothing trimmed
        src = np.frombuffer(take[44:], np.int16).astype(np.float32) / 32767
        for name, a, b in spans:
            got, want = _rms(y[a:b]), _rms(src[a:b])
            if want == 0:
                self.assertLess(got, 1e-4, name)  # rests stay silent, and stay in the take
            else:
                self.assertAlmostEqual(got / want, 1.0, delta=0.02, msg=name)
        tail = y[spans[-1][1] - SR // 2 : spans[-1][2]]
        self.assertGreater(_rms(tail), 0.05)  # the last half second of the final note is there


if __name__ == "__main__":
    unittest.main()
