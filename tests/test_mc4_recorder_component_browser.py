"""MC4 — the Mission recorder page, driven in a real browser (skipped when Playwright/Chromium is absent).

The page is loaded as the top document, so ``window.parent`` is itself: messages it would send to
Streamlit land on ``window`` where the harness records them, and ``streamlit:render`` is posted back
the same way. Media responses are routed, so every failure mode of the generated-backing load can be
produced on demand: transient 404, permanent 404, undecodable bytes, a late response for a backing that
has since been replaced.
"""

from __future__ import annotations

import io
import math
import struct
import unittest
import wave
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency
    sync_playwright = None

HTML = (Path(__file__).resolve().parents[1] / "mission_recorder_component" / "index.html").read_text(encoding="utf-8")
BASE = "http://localhost:4999"  # localhost is a secure context (microphone); nothing listens: every request is routed


def wav_bytes(seconds: float, sr: int = 44100, hz: float = 440.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        n = int(seconds * sr)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * hz * i / sr))) for i in range(n)))
    return buf.getvalue()


SENT_JS = """window.__sent = [];
window.addEventListener('message', (e) => {
  if (e.data && e.data.isStreamlitMessage && e.data.type === 'streamlit:setComponentValue') window.__sent.push(e.data.value);
});"""


@unittest.skipIf(sync_playwright is None, "playwright is not installed")
class TestRecorderComponent(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
        except Exception as exc:  # pragma: no cover
            cls._pw.stop()
            raise unittest.SkipTest(f"chromium unavailable: {exc}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls._pw.stop()

    def setUp(self) -> None:
        self.ctx = self.browser.new_context()
        self.page = self.ctx.new_page()
        self.page.add_init_script(SENT_JS)
        self.media: dict[str, object] = {}     # path -> bytes | callable(route) | list of those (consumed in order)
        self.requests: list[str] = []

        def handler(route):
            url = route.request.url
            path = url[len(BASE):]
            if path == "/index.html":
                return route.fulfill(status=200, content_type="text/html", body=HTML)
            self.requests.append(path)
            entry = self.media.get(path)
            if isinstance(entry, list):
                entry = entry.pop(0) if len(entry) > 1 else entry[0]
            if callable(entry):
                return entry(route)
            if isinstance(entry, (bytes, bytearray)):
                return route.fulfill(status=200, content_type="audio/wav", body=bytes(entry))
            return route.fulfill(status=404, body="gone")

        self.page.route(BASE + "/**", handler)
        self.page.goto(BASE + "/index.html")
        self.page.wait_for_function("() => typeof window.__recorderState === 'function'")

    def tearDown(self) -> None:
        self.ctx.close()

    # -- helpers
    def render(self, **args) -> None:
        base = {"require_backing": True, "disabled": False, "disabled_reason": "", "backing_fp": "", "backing_url": "",
                "backing_duration_sec": 0.0, "load_nonce": 1, "acked_instance": "", "constraints": {}}
        base.update(args)
        self.page.evaluate("(a) => window.postMessage({type: 'streamlit:render', args: a}, '*')", base)

    def state(self) -> dict:
        return self.page.evaluate("() => window.__recorderState()")

    def wait_state(self, want: str, timeout: int = 15000) -> None:
        self.page.wait_for_function("(w) => window.__recorderState().bk.state === w", arg=want, timeout=timeout)

    def acks(self) -> list[dict]:
        return [v["ack"] for v in self.page.evaluate("() => window.__sent") if v and v.get("ack")]

    def status(self) -> str:
        return self.page.locator("#status").inner_text()

    def steps(self) -> list[str]:
        return self.page.evaluate("() => window.__recorderTrace.map(e => e.step)")

    # -- the lifecycle
    def test_ready_only_after_decode_and_acknowledged_with_the_exact_asset(self) -> None:
        self.media["/media/a.wav"] = wav_bytes(1.0)
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0)
        self.wait_state("ready")
        self.assertFalse(self.page.locator("#rec").is_disabled())
        self.assertIn("Backing ready · 1.0 s", self.status())
        (ack,) = self.acks()
        self.assertEqual((ack["fp"], ack["state"], ack["nonce"], ack["attempts"], ack["mime"]), ("fpA", "ready", 1, 1, "audio/wav"))
        self.assertGreater(ack["bytes"], 40000)
        self.assertEqual((ack["sample_rate"], ack["channels"]), (44100, 1))
        self.assertAlmostEqual(ack["duration_sec"], 1.0, places=2)
        self.assertEqual(self.steps(), ["request", "attempt", "fetch_response", "fetch_done", "decode_start", "decode_ok",
                                        "armed", "ack_sent"])

    def test_record_is_disabled_until_ready_and_says_preparing(self) -> None:
        release = []
        self.media["/media/a.wav"] = lambda route: release.append(route)     # response held back
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0)
        self.page.wait_for_function("() => window.__recorderState().bk.state === 'loading'")
        self.assertTrue(self.page.locator("#rec").is_disabled())
        self.assertIn("Preparing recorder", self.status())
        self.assertEqual(self.acks(), [])                                     # nothing acknowledged yet
        self.page.wait_for_function("() => true")
        while not release:
            self.page.wait_for_timeout(50)
        release[0].fulfill(status=200, content_type="audio/wav", body=wav_bytes(1.0))
        self.wait_state("ready")
        self.assertFalse(self.page.locator("#rec").is_disabled())

    def test_transient_media_failure_is_retried_then_ready(self) -> None:
        self.media["/media/a.wav"] = [lambda route: route.fulfill(status=404, body="gone"), wav_bytes(1.0)]
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0)
        self.wait_state("ready")
        (ack,) = self.acks()
        self.assertEqual((ack["state"], ack["attempts"]), ("ready", 2))
        self.assertEqual(self.requests.count("/media/a.wav"), 2)

    def test_persistent_failure_ends_in_an_explicit_error_not_an_endless_load(self) -> None:
        self.render(backing_fp="fpA", backing_url="/media/missing.wav", backing_duration_sec=1.0)   # always 404
        self.wait_state("failed")
        self.assertTrue(self.page.locator("#rec").is_disabled())
        self.assertEqual(self.status(), "Backing was generated but could not be loaded into the recorder. Generate it again.")
        self.assertEqual(self.requests.count("/media/missing.wav"), 3)
        (ack,) = self.acks()
        self.assertEqual((ack["fp"], ack["state"], ack["attempts"], ack["error"]), ("fpA", "failed", 3, "HTTP 404"))
        # further render messages (any Streamlit rerun) must neither wipe the error nor re-trigger a load
        self.render(backing_fp="fpA", backing_url="/media/missing.wav", backing_duration_sec=1.0)
        self.page.wait_for_timeout(300)
        self.assertEqual(self.requests.count("/media/missing.wav"), 3)
        self.assertIn("could not be loaded", self.status())
        self.assertEqual(len(self.acks()), 1)

    def test_a_new_request_nonce_retries_after_failure(self) -> None:
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0, load_nonce=1)
        self.wait_state("failed")
        self.media["/media/a.wav"] = wav_bytes(1.0)                           # the asset is available again
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0, load_nonce=2)
        self.wait_state("ready")
        last = self.acks()[-1]
        self.assertEqual((last["state"], last["nonce"]), ("ready", 2))

    def test_undecodable_bytes_fail_without_pointless_retries(self) -> None:
        self.media["/media/bad.wav"] = b"RIFF....not really a wav file"
        self.render(backing_fp="fpA", backing_url="/media/bad.wav", backing_duration_sec=1.0)
        self.wait_state("failed")
        self.assertEqual(self.requests.count("/media/bad.wav"), 1)
        (ack,) = self.acks()
        self.assertEqual((ack["state"], ack["attempts"]), ("failed", 1))
        self.assertTrue(self.page.locator("#rec").is_disabled())

    def test_a_wrong_length_asset_is_refused(self) -> None:
        self.media["/media/a.wav"] = wav_bytes(1.0)
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=30.0)
        self.wait_state("failed")
        self.assertIn("expected 30.00 s", self.acks()[-1]["error"])
        self.assertTrue(self.page.locator("#rec").is_disabled())

    def test_a_late_response_for_an_older_backing_cannot_arm_the_newer_one(self) -> None:
        held = []
        self.media["/media/a.wav"] = lambda route: held.append(route)         # backing A hangs …
        self.media["/media/b.wav"] = wav_bytes(2.0)
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0, load_nonce=1)
        while not held:
            self.page.wait_for_timeout(50)
        self.render(backing_fp="fpB", backing_url="/media/b.wav", backing_duration_sec=2.0, load_nonce=2)   # … B is requested
        self.wait_state("ready")
        held[0].fulfill(status=200, content_type="audio/wav", body=wav_bytes(1.0))                        # A finally answers
        self.page.wait_for_timeout(500)
        st = self.state()
        self.assertEqual((st["bk"]["fp"], st["bk"]["state"]), ("fpB", "ready"))
        self.assertAlmostEqual(st["bk"]["duration"], 2.0, places=2)
        self.assertEqual([(a["fp"], a["state"]) for a in self.acks()], [("fpB", "ready")])

    def test_clearing_the_backing_disarms_the_recorder(self) -> None:
        self.media["/media/a.wav"] = wav_bytes(1.0)
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0)
        self.wait_state("ready")
        self.render(backing_fp="", backing_url="")                            # settings changed → Python offers nothing
        self.wait_state("idle")
        self.assertFalse(self.state()["ready"])
        self.assertTrue(self.page.locator("#rec").is_disabled())
        self.assertIn("Generate Backing first", self.status())
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0, load_nonce=2)  # generated again
        self.wait_state("ready")
        self.assertFalse(self.page.locator("#rec").is_disabled())

    def test_clearing_mid_load_discards_the_result(self) -> None:
        held = []
        self.media["/media/a.wav"] = lambda route: held.append(route)
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0)
        while not held:
            self.page.wait_for_timeout(50)
        self.render(backing_fp="", backing_url="")
        self.wait_state("idle")
        held[0].fulfill(status=200, content_type="audio/wav", body=wav_bytes(1.0))
        self.page.wait_for_timeout(500)
        self.assertEqual(self.state()["bk"]["state"], "idle")
        self.assertTrue(self.page.locator("#rec").is_disabled())
        self.assertEqual(self.acks(), [])

    def test_a_remounted_recorder_corrects_pythons_belief_before_reloading(self) -> None:
        self.media["/media/a.wav"] = wav_bytes(1.0)
        # Python still holds a "ready" acknowledgement from the previous instance of this recorder
        self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0, acked_instance="oldInstance")
        self.wait_state("ready")
        acks = self.acks()
        self.assertEqual([a["state"] for a in acks], ["loading", "ready"])
        self.assertEqual({a["instance"] for a in acks}, {self.state()["instance"]})

    def test_stopping_a_take_raises_no_page_error_and_returns_the_take(self) -> None:
        # stop() waits ~120 ms for the last audio quanta; their handler used the (already cleared) module-level
        # take, so every one threw "Cannot read properties of null (reading 'firstFrame')" and was dropped.
        errors: list[str] = []
        self.page.on("pageerror", lambda e: errors.append(str(e)))
        self.render(require_backing=False)
        self.page.wait_for_function("() => !document.getElementById('rec').disabled")
        self.page.click("#rec")
        self.page.wait_for_function("() => window.__recorderState && document.getElementById('rec').textContent.includes('Stop')")
        self.page.wait_for_timeout(1200)
        self.page.click("#rec")
        self.page.wait_for_function("() => window.__sent.some(v => v && v.wav_b64)", timeout=15000)
        self.page.wait_for_timeout(400)
        self.assertEqual(errors, [])
        take = self.page.evaluate("() => window.__sent.find(v => v && v.wav_b64)")
        self.assertGreater(take["timing"]["dry_duration_sec"], 0.8)

    def test_rerenders_with_the_same_request_do_not_reload_or_reack(self) -> None:
        self.media["/media/a.wav"] = wav_bytes(1.0)
        for _ in range(3):
            self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0)
        self.wait_state("ready")
        for _ in range(3):
            self.render(backing_fp="fpA", backing_url="/media/a.wav", backing_duration_sec=1.0)
        self.page.wait_for_timeout(300)
        self.assertEqual(self.requests.count("/media/a.wav"), 1)
        self.assertEqual(len(self.acks()), 1)


if __name__ == "__main__":
    unittest.main()
