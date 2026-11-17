"""Does a karaoke take keep playing, or is it being retired and re-rendered?

The audio acceptance starts the take successfully - ``paused: false``, the button flips to
"Pause playback" - and four seconds later nothing is sounding. Before the hotfix merge the same
sequence played continuously to t=59s, so this samples the element every second and prints what
changes: the source URL, whether it is paused, and the position. A source that keeps changing
means the take is being regenerated under the player; a position that stops advancing while the
source stays put means something paused it.

Usage:  python -X utf8 scripts/_probe_take_continuity.py http://127.0.0.1:8660
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8660"
SECONDS = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 30

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    press_play,
    settle,
    wait_for_app,
)
from _accept_karaoke_slice2 import surface_frame  # noqa: E402
from _accept_karaoke_slice2b import SURFACE_AUDIO, wait_for_take  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-slice2-audio"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []

ALL_AUDIO = """
() => {
  const rows = [];
  const look = (doc, where) => {
    if (!doc) return;
    for (const a of doc.querySelectorAll('audio')) {
      rows.push({where: where, src: String(a.currentSrc || a.src || '').slice(-30),
                 paused: !!a.paused, t: Number((a.currentTime || 0).toFixed(2)),
                 ready: Number(a.readyState)});
    }
  };
  look(document, 'page');
  let i = 0;
  for (const f of document.querySelectorAll('iframe')) {
    i += 1;
    try { look(f.contentDocument, 'frame' + i); } catch (e) {}
  }
  return rows;
}
"""


def main() -> int:
    samples = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(viewport={"width": 1280, "height": 900}, has_touch=True)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            wait_for_app(page, 300)
            pick_song(page, NOTES, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)
            click_nav(page, "Songs")
            settle(page, 3)
            click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            click_nav(page, "Backing")
            settle(page, 6)
            press_play(page)

            frame = None
            for _ in range(60):
                frame = surface_frame(page)
                if frame:
                    break
                settle(page, 3)
            if frame is None:
                print("no surface")
                return 2
            print("take as mounted:", json.dumps(wait_for_take(page, frame, 180)))

            state = frame.evaluate(SURFACE_AUDIO) or {}
            if state.get("paused") and str((state.get("button") or {}).get("state")) == "resume":
                frame.locator("#live-stop-btn").click(timeout=10000)
                print("pressed the surface's play once")

            print(f"\nsampling every second for {SECONDS}s")
            print("  %-4s %-9s %-7s %-8s %s" % ("sec", "where", "paused", "t", "src tail"))
            for i in range(SECONDS):
                try:
                    rows = page.evaluate(ALL_AUDIO) or []
                except Exception as exc:
                    rows = [{"where": "err", "src": str(exc)[:30], "paused": None, "t": None}]
                samples.append({"sec": i, "rows": rows})
                for r in rows:
                    print("  %-4d %-9s %-7s %-8s ...%s" % (
                        i, r.get("where"), r.get("paused"), r.get("t"), r.get("src")))
                page.wait_for_timeout(1000)

            srcs = []
            for s in samples:
                for r in s["rows"]:
                    if r.get("src") and r["src"] not in srcs:
                        srcs.append(r["src"])
            print(f"\ndistinct sources seen: {len(srcs)}")
            for s in srcs:
                print("   ..." + str(s))
            playing = sum(1 for s in samples for r in s["rows"] if r.get("paused") is False)
            print(f"samples with something playing: {playing}/{len(samples)}")
            (OUT / "take-continuity.json").write_text(
                json.dumps({"samples": samples, "sources": srcs}, indent=2), encoding="utf-8")
        finally:
            context.close()
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
