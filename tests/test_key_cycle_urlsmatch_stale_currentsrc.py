"""A torn-down Key Cycling buffer must not count as holding a WAV via stale ``currentSrc``.

Off teardown does ``removeAttribute('src')`` + ``load()``; Chromium keeps the old URL in
``currentSrc``. The content-hashed WAV URL is identical on replay, so ``urlsMatch`` used to
report the empty buffer as "already playing" and the player never assigned a ``src``
(first chord shown, Play and Next inert).
"""
from __future__ import annotations

import io
import re
import unittest
import wave
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "backing_key_cycle.py"


def _urls_match_js() -> str:
    text = _SRC.read_text(encoding="utf-8")
    m = re.search(
        r"function urlsMatch\(el, want\) \{\{.*?\n    \}\}\n(?=    function cancelPendingPlays)",
        text,
        re.S,
    )
    assert m, "urlsMatch not found in backing_key_cycle.py"
    return m.group(0).replace("{{", "{").replace("}}", "}")


class UrlsMatchContractTests(unittest.TestCase):
    def test_sourceless_guard_precedes_currentsrc_fallback(self) -> None:
        js = _urls_match_js()
        guard = js.index("if (!el.getAttribute('src')) return false;")
        self.assertLess(js.index("data-kc-url"), guard)
        self.assertLess(guard, js.index("el.currentSrc"))


class UrlsMatchBrowserTests(unittest.TestCase):
    """Run the real function against real Chromium audio elements."""

    def test_stale_current_src_does_not_match(self) -> None:
        sync_api = __import__("pytest").importorskip("playwright.sync_api")
        wav = "/app/static/kc/aaaaaaaaaaaaaaaaaaaa.wav"
        script = (
            "async () => {"
            "const parentWin = window;"
            + _urls_match_js()
            + "const want = '" + wav + "';"
            "const mk = () => document.createElement('audio');"
            "const out = {};"
            # data-kc-url match
            "const a = mk(); a.setAttribute('data-kc-url', want); out.dataAttr = urlsMatch(a, want);"
            # real src attribute present and matching (no network needed: attribute is enough)
            "const b = mk(); b.setAttribute('src', want); out.realSrc = urlsMatch(b, want);"
            # real src attribute present but different
            "const c = mk(); c.setAttribute('src', '/app/static/kc/bbbbbbbbbbbbbbbbbbbb.wav'); out.otherSrc = urlsMatch(c, want);"
            # torn down: src removed + load(); Chromium may keep stale currentSrc
            "const d = mk(); d.setAttribute('src', want); d.load();"
            "await new Promise(r => setTimeout(r, 300));"
            "d.removeAttribute('src'); d.removeAttribute('data-kc-url'); d.load();"
            "await new Promise(r => setTimeout(r, 300));"
            "out.staleCurrentSrc = d.currentSrc; out.tornDown = urlsMatch(d, want);"
            "return out; }"
        )
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                buf = io.BytesIO()
                with wave.open(buf, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(8000)
                    w.writeframes(bytes(16000))
                wav_bytes = buf.getvalue()
                page.route(
                    "http://kc.test/**",
                    lambda r: r.fulfill(
                        status=200,
                        content_type="audio/wav" if r.request.url.endswith(".wav") else "text/html",
                        body=wav_bytes if r.request.url.endswith(".wav") else "<html></html>",
                    ),
                )
                page.goto("http://kc.test/index.html")
                res = page.evaluate(script)
            finally:
                browser.close()
        self.assertTrue(res["dataAttr"])
        self.assertTrue(res["realSrc"])
        self.assertFalse(res["otherSrc"])
        self.assertFalse(res["tornDown"], res)


if __name__ == "__main__":
    unittest.main()
