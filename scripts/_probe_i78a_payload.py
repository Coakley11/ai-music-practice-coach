"""Why did the app's transport see Align 0 when the slider said -0.5?

The component harness passes because it builds the track payload itself. The app builds
it in multitrack_studio_track_payloads from the committed mixer controls. So read what
the iframe was actually handed, rather than reasoning about which of the two could be
wrong.

Usage:
  python scripts/_probe_i78a_payload.py http://127.0.0.1:8591
"""

from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _probe_i78_recording_clock import (  # noqa: E402
    click_text_button,
    expand_layer,
    iframe_frame,
    upload_into_slot,
)
from _accept_issue78a_app import set_align, slider_report  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8591"
WORK = Path(tempfile.mkdtemp(prefix="i78a-payload-"))
NOTES: list[str] = []
SR = 44100


def log(m: str) -> None:
    NOTES.append(m)
    print(m.encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page: Page, s: float = 2.5) -> None:
    wait_idle(page, int(s * 1000))


def make_layer(path: Path) -> Path:
    n = int(SR * 6.0)
    body = bytearray()
    for i in range(n):
        v = 32000 if i == SR else int(3000 * math.sin(2 * math.pi * 196.0 * i / SR))
        body += struct.pack("<h", v)
    head = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(body), b"WAVE",
                       b"fmt ", 16, 1, 1, SR, SR * 2, 2, 16, b"data", len(body))
    path.write_bytes(head + bytes(body))
    return path


def read_tracks(page: Page) -> object:
    fr = iframe_frame(page)
    if fr is None:
        return "no-iframe"
    return fr.evaluate(
        """() => {
          if (typeof tracks === 'undefined') return 'tracks-undefined';
          return tracks.map((t) => ({
            name: t.name, delay: t.delay,
            startDelaySec: t.startDelaySec, bufferOffsetSec: t.bufferOffsetSec,
            keys: Object.keys(t).filter((k) => k !== 'b64'),
          }));
        }"""
    )


def read_state_from_ui(page: Page) -> object:
    fr = iframe_frame(page)
    if fr is None:
        return "no-iframe"
    return fr.evaluate(
        """() => {
          if (typeof trackStateFromUI === 'undefined') return 'fn-undefined';
          return trackStateFromUI();
        }"""
    )


def main() -> int:
    layer = make_layer(WORK / "guitar.wav")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            waited = 0
            while waited < 150:
                b = page.inner_text("body") or ""
                if len(b.strip()) > 400 and "PAGES" in b.upper():
                    break
                settle(page, 3)
                waited += 3
            expand_sidebar(page)
            try:
                pick_song(page, NOTES, "Let It Be", "Rock")
                settle(page, 4)
            except Exception as exc:
                log(f"pick_song raised {exc}")
            click_nav(page, "Multitrack")
            settle(page, 6)
            log(f"Prepare backing -> {click_text_button(page, 'prepare backing')}")
            settle(page, 14)
            expand_layer(page, "guitar")
            settle(page, 2)
            upload_into_slot(page, "guitar", layer)
            settle(page, 8)

            for target in (0.0, 0.5, -0.5, -1.25):
                expand_layer(page, "guitar")
                settle(page, 2)
                res = set_align(page, "guitar", target)
                log(f"\n=== Align target {target:+.2f} -> slider {res.get('value')} ===")
                log(f"  tracks handed to the iframe: "
                    f"{json.dumps(read_tracks(page), default=str)}")
                log(f"  trackStateFromUI() returns:  "
                    f"{json.dumps(read_state_from_ui(page), default=str)}")
        finally:
            (SCRIPTS / "evidence-issue78a" / "payload-probe.txt").write_text(
                "\n".join(NOTES), encoding="utf-8")
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
