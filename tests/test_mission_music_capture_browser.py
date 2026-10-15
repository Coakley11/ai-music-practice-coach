"""Real-browser checks for Mission music capture (skipped when Playwright / Chromium is missing).

A local page (secure context) carries the production capture script and a Mission-recorder
style mic widget; Chromium's fake microphone plays a flute-like performance. Checks:

* only a Record click inside the Mission mic widget arms music capture (EC / NS / AGC off);
  an unrelated recorder keeps the request it made;
* MediaRecorder in small timeslices: the first, middle and final chunks all reach the blob,
  Stop waits for the final ``dataavailable``, decoded duration ≈ Record → Stop time;
* the quiet sustained note, the rests and the final long note right before Stop survive.
"""

from __future__ import annotations

import http.server
import io
import os
import socketserver
import tempfile
import threading
import unittest
import wave

import numpy as np

from mission_music_capture import music_capture_script

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

SR = 48000


def _tone(f: float, dur: float, amp: float) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    x = np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 5 * t)) + 0.18 * np.sin(4 * np.pi * f * t)
    env = np.minimum(1.0, np.minimum(t / 0.04, (dur - t) / 0.08))
    return (amp * x * env).astype(np.float32)


SEGMENTS = [
    ("lead", np.zeros(int(0.5 * SR), np.float32)),
    ("loud_sustain", _tone(440, 2.0, 0.5)),
    ("rest", np.zeros(int(0.5 * SR), np.float32)),
    ("quiet_sustain", _tone(523.25, 2.0, 0.025)),
    ("rest2", np.zeros(int(0.5 * SR), np.float32)),
    ("short_notes", np.concatenate([_tone(f, 0.25, 0.4) for f in (587, 659, 784, 659)])),
    ("final_long_note", _tone(440, 1.5, 0.35)),
]

PAGE = """<!doctype html><html><body>
<div class="st-key-improv_mission_live_span_live_mic"><button data-testid="stAudioInputActionButton" aria-label="Record" id="mrec">r</button>
<button data-testid="stAudioInputActionButton" aria-label="Stop recording" id="mstop">s</button></div>
<div class="st-key-analysis_audio_record"><button data-testid="stAudioInputActionButton" aria-label="Record" id="orec">r</button></div>
__SCRIPT__
<script>
window.__gum = [];
const md = navigator.mediaDevices, inner = md.getUserMedia.bind(md);
// Log what reaches the browser (installed under the Mission wrapper below).
md.getUserMedia = (c) => { window.__gum.push(JSON.parse(JSON.stringify(c))); return inner(c); };
</script>
__SCRIPT_AGAIN__
<script>
window.recordTake = async (ms, timeslice) => {
  const stream = await navigator.mediaDevices.getUserMedia({audio: {sampleRate: {ideal: 16000}}});
  const rec = new MediaRecorder(stream);
  const chunks = []; const events = []; let stopCalledAt = 0;
  rec.ondataavailable = e => { events.push({t: performance.now(), size: e.data.size, afterStop: stopCalledAt > 0}); if (e.data.size) chunks.push(e.data); };
  const stopped = new Promise(r => rec.onstop = () => r(performance.now()));
  const t0 = performance.now(); rec.start(timeslice);
  await new Promise(r => setTimeout(r, ms));
  stopCalledAt = performance.now(); rec.stop(); const stopEvent = await stopped;
  stream.getTracks().forEach(t => t.stop());
  const blob = new Blob(chunks, {type: rec.mimeType});
  const ac = new AudioContext(); const audio = await ac.decodeAudioData(await blob.arrayBuffer()); ac.close();
  const x = audio.getChannelData(0), sr = audio.sampleRate, hop = Math.round(sr * 0.02), env = [];
  for (let i = 0; i + hop <= x.length; i += hop) { let s = 0; for (let j = i; j < i + hop; j++) s += x[j] * x[j]; env.push(Math.sqrt(s / hop)); }
  return {wall: (stopCalledAt - t0) / 1000, decoded: audio.duration, chunks: chunks.length, events,
          lastEventBeforeOnstop: events.length ? events[events.length - 1].t <= stopEvent : false, env};
};
</script></body></html>"""


def _write_wav(path: str, x: np.ndarray) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


class _Server:
    def __init__(self, root: str):
        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=root, **k)  # noqa: E731
        handler.log_message = lambda *a, **k: None
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@unittest.skipIf(sync_playwright is None, "Playwright not installed")
class TestMissionMusicCaptureInBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.mkdtemp(prefix="mc4_capture_")
        cls.signal = np.concatenate([x for _n, x in SEGMENTS])
        cls.wav = os.path.join(cls.tmp, "flute.wav")
        _write_wav(cls.wav, cls.signal)
        script = music_capture_script(["improv_mission_live_span_live_mic"])
        # The Mission wrapper goes on top of the logging wrapper (as in the app, it wraps
        # whatever getUserMedia it finds); the first copy is a no-op re-install check.
        page = PAGE.replace("__SCRIPT__", "").replace("__SCRIPT_AGAIN__", script)
        with open(os.path.join(cls.tmp, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(page)
        cls.server = _Server(cls.tmp)
        cls.url = f"http://127.0.0.1:{cls.server.port}/index.html"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.close()

    def _page(self, p):
        try:
            browser = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                              f"--use-file-for-fake-audio-capture={self.wav}%noloop"])
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"Chromium unavailable: {exc}")
        ctx = browser.new_context(permissions=["microphone"])
        page = ctx.new_page()
        page.goto(self.url)
        return browser, page

    def test_only_a_mission_record_click_arms_music_capture(self) -> None:
        with sync_playwright() as p:
            browser, page = self._page(p)
            page.click("#orec")  # another recorder's Record button
            page.evaluate("navigator.mediaDevices.getUserMedia({audio: {sampleRate: {ideal: 16000}}}).then(s => s.getTracks().forEach(t => t.stop()))")
            page.click("#mrec")  # the Mission recorder's Record button
            page.evaluate("navigator.mediaDevices.getUserMedia({audio: {sampleRate: {ideal: 16000}}}).then(s => s.getTracks().forEach(t => t.stop()))")
            page.click("#mstop")  # "Stop recording" must not re-arm (it contains the word "record")
            page.evaluate("navigator.mediaDevices.getUserMedia({audio: true}).then(s => s.getTracks().forEach(t => t.stop()))")
            gum = page.evaluate("window.__gum")
            takes = page.evaluate("window.__mcMusicCapture.takes")
            browser.close()
        self.assertEqual(gum[0], {"audio": {"sampleRate": {"ideal": 16000}}})  # untouched
        self.assertEqual({k: gum[1]["audio"].get(k) for k in ("echoCancellation", "noiseSuppression", "autoGainControl")},
                         {"echoCancellation": False, "noiseSuppression": False, "autoGainControl": False})
        self.assertEqual(gum[1]["audio"]["sampleRate"], {"ideal": 16000})  # the recorder's own request is kept
        self.assertEqual(gum[2], {"audio": True})  # armed once: the next request is untouched
        self.assertEqual(len(takes), 1)
        self.assertEqual(takes[0]["mode"], "music")
        self.assertGreaterEqual(takes[0]["wallSec"], 0)  # Stop recorded the Record → Stop time

    def test_full_take_survives_chunking_and_stop(self) -> None:
        dur = self.signal.size / SR
        with sync_playwright() as p:
            browser, page = self._page(p)
            page.click("#mrec")
            r = page.evaluate("([ms, ts]) => window.recordTake(ms, ts)", [int((dur + 0.3) * 1000), 250])
            browser.close()
        self.assertGreater(r["chunks"], 10)  # first / middle / final timeslice chunks
        self.assertTrue(any(e["afterStop"] for e in r["events"]))  # the final chunk arrives after stop()
        self.assertTrue(r["lastEventBeforeOnstop"])  # …and before onstop: the blob is complete
        self.assertAlmostEqual(r["decoded"], r["wall"], delta=0.35)
        self.assertGreater(r["decoded"], dur - 0.2)
        env = np.array(r["env"])
        src = np.array([np.sqrt(np.mean(self.signal[i:i + 960] ** 2)) for i in range(0, self.signal.size - 959, 960)])
        lag = max(range(-25, 25), key=lambda k: float(np.dot(np.log10(src[max(0, -k):src.size - max(0, k)] + 1e-5),
                                                             np.log10(env[max(0, k):max(0, k) + src.size - abs(k)] + 1e-5))))
        pos = 0
        for name, x in SEGMENTS:
            a0, a1 = pos // 960, (pos + x.size) // 960
            pos += x.size
            got = env[max(0, a0 + lag + 2):a1 + lag - 2]
            want = src[a0 + 2:a1 - 2]
            if not want.size:
                continue
            if want.max() < 1e-4:
                self.assertLess(float(np.median(got)), 1e-3, name)  # rests are silence, and present
            else:
                ratio = float(np.median(got)) / float(np.median(want))
                self.assertGreater(ratio, 0.7, name)
                self.assertLess(ratio, 1.4, name)
        final = env[(self.signal.size - SEGMENTS[-1][1].size) // 960 + lag:]
        self.assertGreater(float(np.median(final[: final.size // 2])), 0.1)  # the last note before Stop


if __name__ == "__main__":
    unittest.main()
