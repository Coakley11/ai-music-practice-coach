"""Workflow-gated icons, through the real workflow: Upload Analysis (upload -> Run AI coach analysis ->
Save to History) and Multitrack's Project Library saves. Each label starts with its icon, is not
clipped, and is on screen - at 1280, 390 and 360 px.

    python -X utf8 scripts/_probe_icons_workflows.py http://127.0.0.1:<port> [--width 390]
"""
from __future__ import annotations

import io
import json
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))
URL = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8690")
WIDTH = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 1280

from _accept_issue69_karaoke_transposition import settle, wait_for_app  # noqa: E402
import _accept_issue78c_visibility as H  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-icons-workflows"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list = []
NOTES: list = []

BTN_JS = """(key) => {
  const b = document.querySelector('.st-key-' + key + ' button');
  if (!b) return null;
  const r = b.getBoundingClientRect(), p = b.querySelector('p') || b;
  return {text: (b.innerText || '').trim(), l: Math.round(r.left), r: Math.round(r.right),
          vw: document.documentElement.clientWidth, clipped: p.scrollWidth > p.clientWidth + 1, disabled: b.disabled};
}"""


def mark(gate: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((gate, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  [{WIDTH}px] {gate}" + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


def tone_wav(seconds: float = 4.0, sr: int = 44100) -> Path:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * i / sr))) for i in range(int(sr * seconds)))
        w.writeframes(frames)
    path = Path(tempfile.mkdtemp(prefix="icons-wav-")) / "a440.wav"
    path.write_bytes(buf.getvalue())
    return path


def check(page: Page, key: str, icon: str, name: str) -> None:
    loc = page.locator(f".st-key-{key}")
    if loc.count():
        loc.first.scroll_into_view_if_needed()
    g = page.evaluate(BTN_JS, key)
    if g is None:
        mark(f"{name}: on the page", False, "not rendered")
        return
    mark(f"{name}: shows {icon} before its label", g["text"].startswith(icon), g["text"][:40])
    mark(f"{name}: not clipped, on screen", not g["clipped"] and g["l"] >= -1 and g["r"] <= g["vw"] + 1,
         f"l={g['l']} r={g['r']} vw={g['vw']} disabled={g['disabled']}")


def narrow(page: Page) -> None:
    if WIDTH != 1280:
        page.set_viewport_size({"width": WIDTH, "height": 800})
        settle(page, 4)


def wide(page: Page) -> None:
    page.set_viewport_size({"width": 1280, "height": 900})
    settle(page, 2)


def main() -> int:
    wav = tone_wav()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(45000)
        H.URL = URL
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            wait_for_app(page, 300)
            pick_song(page, NOTES, "Say", "pop")
            settle(page, 4)
            # --- Upload Analysis: upload -> Run AI coach analysis -> Save to History ---
            # A phrase only this page has ("upload" alone also matches the Songs page).
            arrived = H.open_studio_page(page, "Upload Analysis", "drop your recording here", tries=8)
            NOTES.append(f"opened Upload Analysis: {arrived}")
            settle(page, 6)
            inp = page.locator('.st-key-analysis_audio_upload input[type="file"]')
            uploaded = False
            if inp.count():
                inp.first.set_input_files(str(wav))
                uploaded = True
            NOTES.append(f"uploaded test tone: {uploaded}")
            settle(page, 10)
            narrow(page)
            check(page, "analysis_run_btn", "🎯", "Run AI coach analysis")
            wide(page)
            run = page.locator(".st-key-analysis_run_btn button")
            if run.count() and run.first.is_enabled():
                run.first.scroll_into_view_if_needed()
                run.first.click()
                settle(page, 30)
            # Save to History lives inside the collapsed "Upload History" section: open it as a user would.
            for sm in page.locator("summary").all():
                try:
                    if "upload history" in (sm.inner_text() or "").lower():
                        sm.scroll_into_view_if_needed()
                        sm.click()
                        settle(page, 3)
                        break
                except Exception:
                    continue
            narrow(page)
            check(page, "upload_history_save_btn", "💾", "Save to History (saved analysis)")
            page.screenshot(path=str(OUT / f"upload-analysis-{WIDTH}.png"))
            # --- Multitrack: Project Library saves ---
            wide(page)
            H.goto_multitrack(page)
            settle(page, 8)
            for s in page.locator("summary").all():
                try:
                    if "project library" in (s.inner_text() or "").lower():
                        s.click()
                        settle(page, 2)
                        break
                except Exception:
                    continue
            narrow(page)
            check(page, "mt_history_save_new_btn", "💾", "Save New Project")
            page.screenshot(path=str(OUT / f"multitrack-{WIDTH}.png"))
        finally:
            (OUT / f"results-{WIDTH}.json").write_text(json.dumps({"results": RESULTS, "notes": NOTES}, indent=1), encoding="utf-8")
            browser.close()
    failed = [g for g, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed at {WIDTH}px")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
