"""MC4 — Generate Backing + one synchronized Mission recorder, flute-aware analysis.

Human review: Performance + Backing did not line up with the flute. Root cause: the backing
(Play) and the microphone (Record) were started by two separate user actions, while the mix
assumed they started together. Now "Generate Backing" renders an authoritative asset and one
browser controller starts the mic and that asset on the same clock; the take stores the measured
offset and the asset identity, which the preview and the live alignment use.
"""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import unittest
import wave
from unittest import mock

import numpy as np

from mission_generated_backing import (
    backing_asset,
    current_generated_backing,
    generate_mission_backing,
)
from mission_practice_context import ensure_mission_practice_context, set_mission_passes, set_mission_tempo
from tests.test_mc4_mission_tempo_sync import IIVI, TWO, _Env, _mission, _tone_wav

SR = 44100


def _sine_wav(freq: float, sec: float, amp: float, sr: int = SR, lead_sec: float = 0.0) -> bytes:
    t = np.arange(int(sec * sr)) / sr
    x = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    x = np.concatenate([np.zeros(int(lead_sec * sr), np.float32), x])
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return out.getvalue()


def _samples(wav: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(wav)) as w:
        sr = w.getframerate()
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32767, sr


def _live_take(session, raw: bytes, *, offset_sec: float, gen):
    """What the studio stores when the Mission recorder returns a take."""
    from mission_recorder import LIVE_TAKE_KEY
    from mission_span_take import audio_fp
    from mission_upload_recording_ui import _dry_wav_fingerprint

    session[LIVE_TAKE_KEY] = {
        "take_id": "t1", "dry_fp": _dry_wav_fingerprint(raw), "audio_fp": audio_fp(raw),
        "timing": {"backing_offset_sec": offset_sec, "backing_fp": gen["fp"], "scheduled_backing_offset_sec": offset_sec - 0.02,
                   "output_latency_sec": 0.015, "input_latency_sec": 0.005},
        "backing": dict(gen),
    }


class TestGenerateBacking(unittest.TestCase):
    def test_generated_backing_is_sealed_and_goes_stale_on_tempo_and_passes(self) -> None:
        for chords in (TWO, IIVI):
            with _Env():
                s = _mission(chords)
                gen = generate_mission_backing(s)
                self.assertIsNotNone(gen)
                self.assertEqual(current_generated_backing(s), (gen, ""))
                self.assertIsNotNone(backing_asset(s, gen["fp"]))
                self.assertEqual(gen["timeline"], chords)
                set_mission_tempo(s, 129)
                self.assertEqual(current_generated_backing(s)[1], "settings changed")
                gen2 = generate_mission_backing(s)
                self.assertEqual((gen2["bpm"], current_generated_backing(s)[1]), (129, ""))
                set_mission_passes(s, 3)
                self.assertEqual(current_generated_backing(s)[1], "settings changed")
                self.assertEqual(generate_mission_backing(s)["loops"], 3)

    def test_single_chord_generate(self) -> None:
        with _Env():
            s = _mission([], single=True)
            gen = generate_mission_backing(s)
            self.assertEqual((gen["kind"], gen["chord"]), ("chord", "A"))
            self.assertEqual(current_generated_backing(s)[1], "")


class TestTakeUsesTheGeneratedBacking(unittest.TestCase):
    def test_span_take_carries_asset_and_measured_offset(self) -> None:
        from mission_span_take import record_span_take

        for chords in (TWO, IIVI):
            with _Env():
                s = _mission(chords)
                s["mission_exact_backing_count_in"] = True
                gen = generate_mission_backing(s)
                raw = _sine_wav(660, 6.0, 0.3)
                _live_take(s, raw, offset_sec=0.312, gen=gen)
                take = record_span_take(s, audio_bytes=raw, source="live")
                self.assertEqual(take["backing"]["fp"], gen["fp"])
                count_in = ensure_mission_practice_context(s).span["count_in_sec"]
                self.assertAlmostEqual(take["alignment"]["offset_sec"], 0.312 + count_in, places=3)
                self.assertEqual(take["alignment"]["detail"]["mix_offset_sec"], 0.312)
                self.assertEqual(take["recording"]["timing"]["backing_fp"], gen["fp"])

    def test_preview_uses_the_same_asset_at_the_stored_offset(self) -> None:
        from mission_upload_recording_ui import _refresh_live_previews

        with _Env():
            s = _mission(TWO)
            gen = generate_mission_backing(s)
            # A distinctive backing asset so its position in the mix can be found exactly.
            asset = _sine_wav(220, 1.0, 0.4)
            s["_mission_backing_assets"][gen["fp"]] = asset
            raw = _sine_wav(880, 3.0, 0.05)
            _live_take(s, raw, offset_sec=0.5, gen=gen)
            out = _refresh_live_previews(s, raw, bpm=100, meter="4/4", backing_gain=0.65)
            self.assertEqual(s["_mission_live_backing_source"], "take_backing_asset")
            diag = s["_mission_live_mix_diag"]
            self.assertEqual(diag["offset_source"], "measured")
            self.assertEqual(diag["offset_samples"], int(round(0.5 * SR)))
            self.assertEqual(out["dry"], raw)  # Performance Only = the microphone take, untouched
            mixed, sr = _samples(out["mixed"])
            from scipy.signal import butter, sosfilt

            low = sosfilt(butter(4, 400, fs=sr, output="sos"), mixed)  # the 220 Hz backing
            frame = int(0.02 * sr)
            env = np.array([np.sqrt(np.mean(low[i:i + frame] ** 2)) for i in range(0, len(low) - frame, frame)])
            onset = int(np.argmax(env > 0.5 * env.max())) * 0.02
            self.assertAlmostEqual(onset, 0.5, delta=0.03)  # backing starts where it was measured

    def test_performance_only_has_no_app_added_backing(self) -> None:
        from mission_live_recording_mix import build_live_recording_previews

        raw = _sine_wav(880, 2.0, 0.2)
        s: dict = {}
        out = build_live_recording_previews(s, raw, backing_wav=_sine_wav(220, 2.0, 0.4), bpm=100, meter="4/4",
                                            backing_gain=0.65, backing_offset_samples=1000)
        self.assertEqual(out["dry"], raw)
        self.assertEqual(s["_mission_live_mic_dry"], raw)
        self.assertNotEqual(out["mixed"], raw)

    def test_preview_fx_keeps_flute_present_without_clipping(self) -> None:
        from mission_live_recording_mix import mix_dry_mic_with_backing

        flute = _sine_wav(880, 3.0, 0.03)
        band = _sine_wav(110, 3.0, 0.5)
        mixed, diag = mix_dry_mic_with_backing(flute, band, backing_offset_samples=0, loop_backing=False,
                                               performance_forward=True, performance_fx=True)
        self.assertEqual(diag["performance_fx"], "hpf+comp+plate")
        x, sr = _samples(mixed)
        self.assertLessEqual(float(np.max(np.abs(x))), 0.99)
        spec = np.abs(np.fft.rfft(x))
        f = np.fft.rfftfreq(len(x), 1 / sr)
        flute_e = spec[(f > 860) & (f < 900)].sum()
        band_e = spec[(f > 100) & (f < 120)].sum()
        self.assertGreater(flute_e, band_e)  # the soloist sits over the accompaniment


class TestFluteAwareAnalysis(unittest.TestCase):
    def test_sounding_ranges_from_the_shared_registry(self) -> None:
        from instrument_pitch_range import sounding_pitch_range

        lo, hi, specific = sounding_pitch_range("Flute")
        self.assertTrue(specific)
        self.assertEqual(lo, 60)  # flute bottom C4 exactly (concert = written); nothing below — that is bleed
        self.assertGreaterEqual(hi, 96)  # at least C7 (the registry's widened top + margin)
        clo, chi, _ = sounding_pitch_range("Clarinet")
        self.assertLess(clo, 58)  # clarinet keeps its chalumeau register (comfort profile is widened)
        alo, _ahi, _ = sounding_pitch_range("Saxophone")
        self.assertLess(alo, 60)
        self.assertEqual(sounding_pitch_range("Piano")[2], False)

    def test_backing_bass_is_not_counted_as_flute(self) -> None:
        from mission_span_transcription import transcribe

        # Flute line (A5 / C6) with a quieter bass (C3) underneath, like speaker bleed.
        flute = _sine_wav(880, 2.0, 0.3, lead_sec=0.2)
        bass_then = _sine_wav(130.8, 1.5, 0.12, lead_sec=2.4)
        a, sr = _samples(flute)
        b, _ = _samples(bass_then)
        n = max(len(a), len(b))
        x = np.zeros(n, np.float32); x[: len(a)] += a; x[: len(b)] += b
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
        wav = buf.getvalue()
        generic = transcribe(wav)
        flute_only = transcribe(wav, midi_range=(58, 100))
        self.assertTrue(any(nn["midi"] < 55 for nn in generic["notes"]))  # the bass is heard…
        self.assertFalse(any(nn["midi"] < 58 for nn in flute_only["notes"]))  # …but not as flute
        self.assertGreaterEqual(flute_only["rejected"]["out_of_range"], 1)
        self.assertTrue(any(abs(nn["midi"] - 81) <= 1 for nn in flute_only["notes"]))

    def test_coach_pitch_uses_instrument_range(self) -> None:
        from tests.test_mc4_flute_pitch_evidence import flute_phrase_with_bass

        from recording_analysis import _pyin_features

        y, sr = flute_phrase_with_bass()
        stats = _pyin_features(y, sr, midi_range=(60, 106))
        self.assertEqual(stats["pitch_evidence"], "high")
        self.assertGreaterEqual(int(stats["pitch_note"][-1]), 5)  # the flute line (octave 5), not the bass

    def test_flute_report_has_no_piano_advice_and_honest_attribution(self) -> None:
        from multitrack_upload_analysis import _mixed_attribution_confidence
        from recording_analysis import analyze_recording

        wav = _sine_wav(880, 4.0, 0.3)
        res = analyze_recording(wav, "take.wav", {"instrument": "Flute", "recording_type": "Mission Recording"})
        text = json.dumps(res, default=str).lower()
        self.assertNotIn("voicing", text)
        self.assertNotIn("piano", text)
        self.assertIn("flute's sounding range", text)
        msg = _mixed_attribution_confidence({})
        self.assertNotIn("no backing track in this take", msg)
        self.assertIn("dry microphone take", msg)
        self.assertIn("acoustically", msg)


class TestUploadContextLine(unittest.TestCase):
    def test_span_take_shows_its_span_not_the_one_chord_mission(self) -> None:
        from mission_analysis_ui import render_mission_upload_compact_context

        st = mock.MagicMock()
        take = {"span": {"mission_label": "Target each chord change", "relationship_label": "V–I",
                         "timeline": [{"chord": "G", "chart_chord": "G"}, {"chord": "C", "chart_chord": "C"}]}}
        with mock.patch("mission_span_take.analysis_span_take", return_value=take):
            render_mission_upload_compact_context(st, {"improv_active_mission": "Improvise using only chord tones",
                                                       "ii_selected_chord": "G"})
        line = st.markdown.call_args.args[0]
        self.assertIn("Target each chord change", line)
        self.assertIn("**Span:** G → C", line)
        self.assertNotIn("Chord:", line)


class TestMissionComplianceLabels(unittest.TestCase):
    def test_labels(self) -> None:
        from analysis_coach_quality import criteria_overall_score_label
        from mission_span_upload_ui import render_span_take_result

        self.assertEqual(criteria_overall_score_label(mission_evaluation_active=True), "Overall Performance Coaching")
        st = mock.MagicMock()
        render_span_take_result(st, {"score": 100, "headline": "Target each chord change · C/E → G → C", "aligned": True,
                                     "what_worked": ["x"], "try_next": [], "chord_detail": []})
        heads = [c.args[0] for c in st.markdown.call_args_list if c.args]
        self.assertIn("#### Mission Compliance: 100%", heads)


try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "Playwright not installed")
class TestRecorderComponentInBrowser(unittest.TestCase):
    """The real component in Chromium (fake microphone): one clock, measured offset, full take."""

    def test_record_with_backing_returns_wav_and_timing(self) -> None:
        import http.server
        import socketserver
        import threading
        from pathlib import Path

        comp = (Path(__file__).resolve().parent.parent / "mission_recorder_component" / "index.html").read_text(encoding="utf-8")
        tmp = tempfile.mkdtemp(prefix="mc4_rec_")
        Path(tmp, "index.html").write_text(comp, encoding="utf-8")
        mic = os.path.join(tmp, "mic.wav")
        Path(mic).write_bytes(_sine_wav(880, 6.0, 0.3, sr=48000))
        backing = _sine_wav(220, 4.0, 0.3)
        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=tmp, **k)  # noqa: E731
        handler.log_message = lambda *a, **k: None
        httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                try:
                    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                                f"--use-file-for-fake-audio-capture={mic}"])
                except Exception as exc:  # pragma: no cover
                    self.skipTest(f"Chromium unavailable: {exc}")
                page = b.new_context(permissions=["microphone"]).new_page()
                page.add_init_script("""window.__values = []; window.addEventListener('message', e => {
                    if (e.data && e.data.type === 'streamlit:setComponentValue') window.__values.push(e.data.value); });""")
                page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/index.html")
                url = "data:audio/wav;base64," + base64.b64encode(backing).decode()
                page.evaluate("""(u) => window.postMessage({type: 'streamlit:render', args: {
                    require_backing: true, backing_fp: 'fp1', backing_url: u,
                    constraints: {echoCancellation: false, noiseSuppression: false, autoGainControl: false}}}, '*')""", url)
                page.wait_for_function("() => !document.getElementById('rec').disabled", timeout=15000)
                page.click("#rec")
                page.wait_for_timeout(2500)
                page.click("#rec")
                page.wait_for_function("() => window.__values.length > 0", timeout=15000)
                value = page.evaluate("() => window.__values[0]")
                b.close()
        finally:
            httpd.shutdown(); httpd.server_close()
        t = value["timing"]
        self.assertEqual(t["backing_fp"], "fp1")
        self.assertIsNotNone(t["scheduled_backing_offset_sec"])
        self.assertGreater(t["scheduled_backing_offset_sec"], 0.15)  # scheduled lead on the capture clock
        self.assertLess(t["scheduled_backing_offset_sec"], 0.6)
        self.assertAlmostEqual(t["backing_offset_sec"],
                               t["scheduled_backing_offset_sec"] + t["output_latency_sec"] + t["input_latency_sec"], places=6)
        self.assertEqual((t["settings"]["echoCancellation"], t["settings"]["noiseSuppression"], t["settings"]["autoGainControl"]),
                         (False, False, False))
        x, sr = _samples(base64.b64decode(value["wav_b64"]))
        self.assertAlmostEqual(len(x) / sr, t["dry_duration_sec"], places=2)
        self.assertGreater(t["dry_duration_sec"], 1.0)  # a real take was captured (mic start-up varies)
        # The take runs from capture start to Stop (mic start-up before capture is not audio).
        self.assertAlmostEqual(t["dry_duration_sec"], (t["stop_click_ms"] - t["capture_start_ms"]) / 1000.0, delta=0.3)


if __name__ == "__main__":
    unittest.main()
