"""The failing asset must identify itself, measured in a real browser.

Issue 77A's page message can only name the part that failed if the component actually sends the
asset's id. That is the one link in the chain the Python tests cannot prove and the full-app
acceptance cannot reach any more - once uploads are validated, a file that cannot be decoded never
becomes a layer, so the failure state is no longer reachable through the UI. Which is the right
outcome for a musician and a hole in the evidence.

So this loads the real component into Chromium, hands it an asset that cannot be decoded, and reads
what it tells its host:

  * the acknowledgement says ``state: "failed"`` and names ``failed_asset``;
  * Record is disabled while a requested part has not loaded (the guarantee 77A keeps);
  * the host-visible status still mentions the parts, so nothing silently claims to be ready.

The id it reports is then fed through the real message builder, so the sentence the musician would
see is produced from a genuine browser failure rather than a hand-written dictionary.
"""

from __future__ import annotations

import functools
import http.server
import json
import socketserver
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "mission_recorder_component"

BAD_ASSET_NAME = "_i77a_undecodable.wav"
HOST_NAME = "_i77a_failure_host.html"

HOST_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>asset failure host</title>
<style>body{margin:0;font:14px sans-serif}iframe{width:100%;border:0;display:block}</style>
</head><body>
<iframe id="f" src="index.html" height="0" title="mission_recorder"></iframe>
<script>
  window.values = [];
  window.renders = 0;
  window.addEventListener("message", (e) => {
    const d = e.data || {};
    if (!d.isStreamlitMessage) return;
    if (d.type === "streamlit:setFrameHeight") {
      document.getElementById("f").style.height = d.height + "px";
    }
    if (d.type === "streamlit:setComponentValue") {
      window.values.push(d.value);
    }
    if (d.type === "streamlit:componentReady") {
      window.renders += 1;
      document.getElementById("f").contentWindow.postMessage({
        type: "streamlit:render",
        args: {
          ready_text: "Ready.",
          count_in_beats: 4,
          count_in_bpm: 90,
          count_in_beats_per_bar: 4,
          require_backing: false,
          disabled_reason: "",
          backing_fp: "",
          backing_url: "",
          backing_duration_sec: 0,
          load_nonce: 1,
          acked_instance: "",
          monitors: [{
            id: "layer:Sax / winds",
            fp: "deadbeef",
            url: "__BAD__",
            expected_duration_sec: 0,
            start_delay_sec: 0,
            buffer_offset_sec: 0,
            volume: 1
          }]
        }
      }, "*");
    }
  });
</script>
</body></html>
"""


def _serve(directory: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


class AFailedAssetNamesItself(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment without Playwright
            raise unittest.SkipTest(f"Playwright is not installed: {exc}") from exc
        cls._bad = COMPONENT_DIR / BAD_ASSET_NAME
        cls._bad.write_bytes(b"RIFF" + (900).to_bytes(4, "little") + b"WAVEjunk" + b"\x7f" * 900)
        cls._host = COMPONENT_DIR / HOST_NAME
        cls._host.write_text(HOST_PAGE.replace("__BAD__", BAD_ASSET_NAME), encoding="utf-8")
        cls._httpd, cls._port = _serve(COMPONENT_DIR)

    @classmethod
    def tearDownClass(cls) -> None:
        for attr in ("_httpd",):
            try:
                getattr(cls, attr).shutdown()
                getattr(cls, attr).server_close()
            except Exception:
                pass
        for path in (getattr(cls, "_host", None), getattr(cls, "_bad", None)):
            try:
                if path is not None:
                    path.unlink()
            except Exception:
                pass

    def test_the_component_reports_which_asset_failed_and_refuses_to_record(self) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:  # pragma: no cover - no browser binary
                raise unittest.SkipTest(f"no Chromium available: {exc}") from exc
            try:
                page = browser.new_page(viewport={"width": 480, "height": 900})
                page.goto(f"http://127.0.0.1:{self._port}/{HOST_NAME}", wait_until="load")
                # three attempts with backoff inside the component, then it gives up
                page.wait_for_timeout(12000)

                self.assertGreaterEqual(page.evaluate("() => window.renders"), 1,
                                        "the component never announced itself")
                values = page.evaluate("() => window.values.slice()")
                acks = [v.get("ack") for v in values
                        if isinstance(v, dict) and isinstance(v.get("ack"), dict)]
                self.assertTrue(acks, f"no acknowledgement was sent at all: {values!r}")
                failed = [a for a in acks if a.get("state") == "failed"]
                self.assertTrue(failed, f"the component never reported a failure: {acks!r}")
                ack = failed[-1]

                # 1. THE POINT OF THIS TEST: the asset identifies itself.
                self.assertEqual(
                    ack.get("failed_asset"), "layer:Sax / winds",
                    f"the failed asset was not named, so the page cannot name it either: {ack!r}",
                )
                self.assertIn("decode", str(ack.get("error") or "").lower())

                # 2. The guarantee: nothing records while a requested part is missing.
                btn = page.frame_locator("#f").locator("#rec")
                self.assertTrue(btn.is_disabled(), "Record was left usable with a part missing")
                status = page.frame_locator("#f").locator("#status").inner_text()
                self.assertIn("could not be loaded", status.lower())

                # 3. And the sentence a musician would read, built from this real failure.
                from multitrack_monitor_assets import monitor_failure_message

                ss = {"mt_name_Sax / winds": "Tenor sax"}
                from multitrack_monitor_assets import record_layer_recorder_ack

                self.assertTrue(record_layer_recorder_ack(ss, "Guitar", ack))
                message = monitor_failure_message(ss, "Guitar")
                self.assertIn("Tenor sax", message)
                self.assertNotIn("Unable to decode audio data", message)
                self.assertIn("Record or upload that layer again", message)
                print("\nmessage from a real browser failure:\n  " + message, flush=True)
                print("  ack: " + json.dumps(
                    {k: ack.get(k) for k in ("state", "failed_asset", "bytes", "mime", "attempts")},
                    default=str), flush=True)
            finally:
                browser.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
