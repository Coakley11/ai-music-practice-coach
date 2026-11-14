"""The measured guard the Issue 78C decision asked to keep: a real browser, a real frame height.

    "Please retain measured iframe-height checks in the regression suite so that future testing
     cannot report success when a button is hidden inside a four-pixel frame."

Everything else about Issue 78C can be asserted by reading the source, and is, in
``test_issue78c_recorder_visibility.py``. This file is the one that would still catch the defect if
the source checks were deleted or rewritten, because it does not read the component - it loads it
into Chromium, hides it the way a collapsed Streamlit expander hides it, and reads the heights the
component actually publishes to its host.

Why it does not start the app: Multitrack's own state lives in the checkout's ``data/`` directory,
so booting Streamlit from a test run inside the user's main checkout would write into their saved
projects and recordings. The full-app version of this check is
``scripts/_accept_issue78c_visibility.py``, which refuses to run outside a worktree. What is
reproduced here instead is the exact mechanism that failed:

  1. the component is mounted inside a **closed** ``<details>`` - a hidden iframe has no layout, so
     ``document.body.scrollHeight`` is 0, and the old code published ``0 + 4``;
  2. the ``<details>`` is then opened, which in Streamlit sends **no** render message of any kind -
     the missing event that left the frame four pixels tall for the rest of the session.

The three assertions are therefore: no published height is ever below the floor; opening the
container alone makes the component republish a real height; and the Record button fits inside the
height that was published.
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "mission_recorder_component"

#: Must match MIN_FRAME_H in the component. A frame shorter than this is a coloured line.
MIN_FRAME_H = 52

#: The page that stands in for Streamlit: a closed expander, an iframe, and a recorder of every
#: height the component asks for. The parent answers componentReady with a render, exactly as
#: Streamlit does, and then deliberately sends nothing more.
HOST_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>frame height host</title>
<style>body{margin:0;font:14px sans-serif}iframe{width:100%;border:0;display:block}</style>
</head><body>
<details id="panel"><summary>Layer controls - guitar</summary>
  <iframe id="f" src="index.html" height="0" title="mission_recorder"></iframe>
</details>
<script>
  window.heights = [];
  window.renders_sent = 0;
  window.addEventListener("message", (e) => {
    const d = e.data || {};
    if (!d.isStreamlitMessage) return;
    if (d.type === "streamlit:setFrameHeight") {
      window.heights.push(d.height);
      // Streamlit applies the height to the element; without this the frame never grows.
      document.getElementById("f").setAttribute("height", String(d.height));
      document.getElementById("f").style.height = d.height + "px";
    }
    if (d.type === "streamlit:componentReady") {
      window.renders_sent += 1;
      document.getElementById("f").contentWindow.postMessage({
        type: "streamlit:render",
        args: {ready_text: "Ready.", count_in_beats: 4, bpm: 90, disabled_reason: ""}
      }, "*");
    }
  });
</script>
</body></html>
"""


def _serve(directory: Path) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


class TheRecorderIsNeverFourPixelsTall(unittest.TestCase):
    """Measured in Chromium, not read from the source."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment without Playwright
            raise unittest.SkipTest(f"Playwright is not installed: {exc}") from exc
        cls._host = COMPONENT_DIR / "_i78c_height_host.html"
        cls._host.write_text(HOST_PAGE, encoding="utf-8")
        cls._httpd, cls._port = _serve(COMPONENT_DIR)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._httpd.shutdown()
            cls._httpd.server_close()
        except Exception:
            pass
        try:
            cls._host.unlink()
        except Exception:
            pass

    def test_a_hidden_recorder_still_publishes_a_usable_height(self) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:  # pragma: no cover - no browser binary
                raise unittest.SkipTest(f"no Chromium available: {exc}") from exc
            try:
                page = browser.new_page(viewport={"width": 420, "height": 900})
                page.goto(f"http://127.0.0.1:{self._port}/_i78c_height_host.html",
                          wait_until="load")
                page.wait_for_timeout(2500)

                collapsed = page.evaluate("() => window.heights.slice()")
                self.assertTrue(
                    page.evaluate("() => window.renders_sent") >= 1,
                    "the component never announced itself, so this test measured nothing",
                )
                # 1. THE DEFECT. Collapsed, the body has no layout and scrollHeight is 0. Publishing
                #    that - as `0 + 4` - is what put the Record button inside a four-pixel frame.
                self.assertTrue(collapsed, "the component published no height at all")
                self.assertGreaterEqual(
                    min(collapsed), MIN_FRAME_H,
                    f"a height below the floor was published while hidden: {collapsed}",
                )

                # 2. THE MISSING EVENT. Opening an expander sends no render message, so the
                #    component has to notice the new layout by itself.
                page.evaluate("() => { document.getElementById('panel').open = true; }")
                page.wait_for_timeout(3000)
                self.assertEqual(
                    page.evaluate("() => window.renders_sent"), 1,
                    "the host sent another render, so this no longer tests the missing event",
                )
                after = page.evaluate("() => window.heights.slice()")
                self.assertGreater(
                    max(after), MIN_FRAME_H,
                    "opening the panel never produced a real measurement; the frame would have "
                    f"stayed at the floor for the whole session: {after}",
                )

                # 3. And the control fits in the height that was published.
                frame_h = page.evaluate(
                    "() => document.getElementById('f').getBoundingClientRect().height"
                )
                box = page.frame_locator("#f").locator("#rec").bounding_box()
                self.assertIsNotNone(box, "no Record button in the component")
                self.assertGreaterEqual(float(box["height"]), 28.0)
                self.assertTrue(
                    page.frame_locator("#f").locator("#rec").is_visible(),
                    "the browser does not consider the Record button visible",
                )
                self.assertGreaterEqual(
                    frame_h, float(box["height"]),
                    f"the frame ({frame_h}px) is shorter than the button inside it "
                    f"({box['height']}px) - the musician sees a sliver",
                )
            finally:
                browser.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
