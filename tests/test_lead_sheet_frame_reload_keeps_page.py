"""A Lead Sheet frame that reloads keeps the page where it is.

Browser run 2026-11-21 (360 px, b72dc357, scroll spy): a rerun that changes the full-height sheet's HTML (a new
key after a Key Cycling step, the cycle's own end) makes Streamlit create its frame again at the 820 px default
before the sheet's script grows it back to the chart (2686 -> 820 -> 2686 px). No script scrolled: Chrome's scroll
anchoring moved the page 1.9-2.7k px each time, and for good when the cycle had just stopped, because the follow
controller never moves the page then. The sheet now holds its height on its keyed host while the frame reloads.
"""
from __future__ import annotations

import unittest

import streamlit_music_practice_app as app

_CHART = "<div class='lead-grid'>" + "".join(
    f"<div class='chord-cell' style='height:28px'>Bar {i} Am7</div>" for i in range(1, 91)) + "</div>"

_PARENT = """<html><body style="margin:0">
<section data-testid="stMain" id="main" style="height:800px; overflow-y:auto">
  <div style="height:3000px; background:#eee">above</div>
  <div class="st-key-ls_follow_panel_host"><div data-testid="stElementContainer" id="host">
    <iframe id="sheet" style="width:100%; height:820px; border:0" height="820"></iframe></div></div>
  <div style="height:4000px; background:#ddd">below</div>
</section></body></html>"""

_SAMPLE = """() => { const m = document.getElementById('main'); const f = document.getElementById('sheet');
  return { y: Math.round(m.scrollTop), top: Math.round(f.getBoundingClientRect().top),
           h: Math.round(f.getBoundingClientRect().height), doc: Math.round(m.scrollHeight) }; }"""

_RELOAD = """(html) => { const old = document.getElementById('sheet');
  const f = document.createElement('iframe'); f.id = 'sheet'; f.style.width = '100%'; f.style.height = '820px';
  f.style.border = '0'; f.setAttribute('height', '820');
  const host = document.getElementById('host'); host.style.cssText = '';
  // the real sheet's HTML is megabytes: the new frame sits at 820 px for a while before its script runs
  old.replaceWith(f); setTimeout(() => { f.srcdoc = html; }, 700); }"""


def _html() -> str:
    return app.live_follow_along_component_html(b"", [], _CHART, audio_url="/app/static/x.wav", page_follow=True)


def run_reload(test: unittest.TestCase, html: str) -> tuple[dict, list]:
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover
        test.skipTest("playwright not installed")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 360, "height": 800})
            page.route("http://sheet.test/**", lambda r: r.fulfill(status=200, content_type="text/html", body=_PARENT))
            page.goto("http://sheet.test/app/")
            page.evaluate("(html) => { document.getElementById('sheet').srcdoc = html; }", html)
            page.wait_for_timeout(2500)                                # the sheet grew to its chart, past 2 s
            page.evaluate("() => { document.getElementById('main').scrollTop = 4200; }")  # inside the chart
            page.wait_for_timeout(400)
            before = page.evaluate(_SAMPLE)
            page.evaluate(_RELOAD, html)                               # Streamlit's new frame at 820 px
            samples = []
            for _ in range(50):
                page.wait_for_timeout(50)
                samples.append(page.evaluate(_SAMPLE))
        finally:
            browser.close()
    return before, samples


class AReloadedSheetFrameKeepsThePage(unittest.TestCase):
    def test_the_page_does_not_move_while_the_frame_reloads(self) -> None:
        before, samples = run_reload(self, _html())
        self.assertGreater(before["h"], 2000, before)                 # the chart's full height
        # The space is held: without the reservation the page shrank by the frame's 1880 px while it reloaded
        # (measured 9702 -> 7820 here), which is what Chrome's scroll anchoring answered with a 1.9-2.7k px move.
        self.assertGreaterEqual(min(s["doc"] for s in samples), before["doc"] - 40, samples[:12])
        moved = [s for s in samples if abs(s["y"] - before["y"]) > 40 or abs(s["top"] - before["top"]) > 40]
        self.assertEqual(moved, [], {"before": before, "samples": samples[:12]})
        self.assertGreater(samples[-1]["h"], 2000, samples[-1])       # grown back to the chart

    def test_the_html_reserves_the_height_on_the_keyed_host(self) -> None:
        html = _html()
        self.assertIn(".st-key-ls_follow_panel_host", html)
        self.assertIn("ls-panel-reserve", html)
        src = open(app.__file__, encoding="utf-8").read()
        self.assertIn('with st.container(key="ls_follow_panel_host"):', src)


if __name__ == "__main__":
    unittest.main()
