"""Key-cycle WAV URLs must resolve under the app's base path, not the site root.

Streamlit Community Cloud serves the app under /~/+/. A root "/app/static/kc/…"
URL reached the Cloud wrapper (303 to the login page) instead of the app, so
every dual-buffer element failed with MEDIA_ERR 4 and Key Cycling was silent.
"""
from __future__ import annotations

import io
import os
import tempfile
import unittest
import wave
from pathlib import Path

import backing_key_cycle as kc


def _wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(bytes(16000))
    return buf.getvalue()


class PublishedUrlFormTests(unittest.TestCase):
    def test_publish_returns_a_page_relative_url_that_is_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "take.wav"
            src.write_bytes(_wav_bytes())
            url = kc.publish_cycle_wav_static_url(str(src), signature=("base-path-test", os.getpid()))
            try:
                self.assertTrue(url.startswith("app/static/kc/"), url)
                self.assertFalse(url.startswith("/"), url)
                self.assertTrue(kc._kc_static_url_on_disk(url))
                # A root URL is never handed out as servable.
                self.assertFalse(kc._kc_static_url_on_disk("/" + url))
            finally:
                (kc._kc_static_dir() / url.rsplit("/", 1)[-1]).unlink(missing_ok=True)


class BrowserResolutionTests(unittest.TestCase):
    """The browser resolves the published URL under the page's base path and loads it."""

    def test_page_relative_url_loads_under_a_mounted_base_path(self) -> None:
        sync_api = __import__("pytest").importorskip("playwright.sync_api")
        wav = _wav_bytes()
        served: list[str] = []

        def handle(route) -> None:
            url = route.request.url
            if url.startswith("http://kc.test/mount/app/static/kc/") and url.endswith(".wav"):
                served.append(url)
                route.fulfill(status=200, content_type="audio/wav", body=wav)
            elif url.endswith("/mount/") or url.endswith("/mount/index.html"):
                route.fulfill(status=200, content_type="text/html", body="<html></html>")
            else:  # the site root is not the app
                route.fulfill(status=303, headers={"Location": "http://kc.test/-/login"}, body="")

        script = (
            "async (want) => { const a = document.createElement('audio'); a.preload = 'auto';"
            "document.body.appendChild(a); a.src = want; a.load();"
            "await new Promise(r => { a.addEventListener('loadedmetadata', r, {once: true});"
            "a.addEventListener('error', r, {once: true}); setTimeout(r, 4000); });"
            "return {currentSrc: a.currentSrc, rs: a.readyState, err: a.error ? a.error.code : null,"
            "dur: a.duration}; }"
        )
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.route("http://kc.test/**", handle)
                page.goto("http://kc.test/mount/")
                res = page.evaluate(script, "app/static/kc/aaaaaaaaaaaaaaaaaaaa.wav")
                root = page.evaluate(script, "/app/static/kc/aaaaaaaaaaaaaaaaaaaa.wav")
            finally:
                browser.close()
        self.assertEqual(res["currentSrc"], "http://kc.test/mount/app/static/kc/aaaaaaaaaaaaaaaaaaaa.wav")
        self.assertIsNone(res["err"], res)
        self.assertGreaterEqual(res["rs"], 1, res)
        self.assertEqual(len(served), 1, served)
        # The old root form escapes the mount and fails to load.
        self.assertIsNotNone(root["err"], root)


if __name__ == "__main__":
    unittest.main()
