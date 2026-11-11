"""Issue 64 G26: why a restored key does not reach the sidebar in a live session.

The load path sets the pick-scoped store correctly when called on a plain dict, and
leaves the sidebar showing the old key in the real application - sixty seconds and six
navigations later. So the interesting state is the one only a running session has, and
this drives the smallest scenario that reproduces it, with the restore tracing what it
decided and what the store held immediately afterwards.

Usage:
  MUSIC_MT_KEY_TRACE=1 MUSIC_APP_DATA_DIR=<dir> streamlit run ... --server.port 8561
  python scripts/_probe_issue64_key_restore.py http://127.0.0.1:8561
"""

from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from walk_creative_backing_matrix import click_nav, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8561"
DATA = ROOT / "_runtime_issue64_probe"
AUDIO = Path(tempfile.mkdtemp(prefix="issue64-probe-"))


def log(msg: str) -> None:
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page, seconds: float = 3.0) -> None:
    wait_idle(page, int(seconds * 1000))


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def make_wav(name: str, freq: float = 466.0) -> Path:
    path = AUDIO / name
    rate = 22050
    frames = bytearray()
    for i in range(rate):
        frames += struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)))
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(bytes(frames))
    return path


def on_multitrack(page) -> bool:
    return "multitrack session workspace" in low(page.inner_text("body") or "")


def goto_multitrack(page) -> bool:
    if on_multitrack(page):
        return True
    click_nav(page, "Multitrack")
    settle(page, 4)
    return on_multitrack(page)


def expand_layer(page, slot: str) -> bool:
    page.evaluate(
        """(slot) => {
          const want = ('Layer controls \\u2014 ' + slot).toLowerCase();
          const el = [...document.querySelectorAll('details')].find((d) => {
            const s = d.querySelector('summary');
            return s && (s.innerText || '').toLowerCase().includes(want);
          });
          if (!el) return false;
          const s = el.querySelector('summary');
          s.scrollIntoView({block: 'center'});
          if (!el.hasAttribute('open')) {
            ['pointerdown','mousedown','pointerup','mouseup','click'].forEach((t) =>
              s.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window})));
          }
          return true;
        }""",
        slot,
    )
    settle(page, 3)
    return True


def slot_state(page, slot: str) -> str:
    lines = [l.strip() for l in (page.inner_text("body") or "").splitlines()]
    for i, line in enumerate(lines):
        if line == slot:
            for nxt in lines[i + 1:i + 4]:
                if "HAS AUDIO" in nxt:
                    return "has_audio"
                if "EMPTY" in nxt:
                    return "empty"
    return "unknown"


def upload(page, slot: str, wav: Path) -> bool:
    for _ in range(3):
        expand_layer(page, slot)
        idx = page.evaluate(
            """(slot) => {
              const want = ('Layer controls \\u2014 ' + slot).toLowerCase();
              const d = [...document.querySelectorAll('details')].find((x) => {
                const s = x.querySelector('summary');
                return s && (s.innerText || '').toLowerCase().includes(want);
              });
              const all = [...document.querySelectorAll('[data-testid="stFileUploaderDropzoneInput"]')];
              return d ? all.findIndex((e) => d.contains(e)) : -1;
            }""",
            slot,
        )
        if not isinstance(idx, int) or idx < 0:
            return False
        page.locator('[data-testid="stFileUploaderDropzoneInput"]').nth(idx).set_input_files(str(wav))
        for _ in range(4):
            settle(page, 3)
            if slot_state(page, slot) == "has_audio":
                return True
        page.reload(wait_until="domcontentloaded")
        settle(page, 8)
        goto_multitrack(page)
        if slot_state(page, slot) == "has_audio":
            return True
    return False


def open_library(page) -> bool:
    page.evaluate(
        """() => {
          const el = [...document.querySelectorAll('details')].find((d) => {
            const s = d.querySelector('summary');
            return s && (s.innerText || '').includes('Project Library');
          });
          if (el && !el.hasAttribute('open')) el.querySelector('summary').click();
          return !!el;
        }"""
    )
    settle(page, 3)
    return True


def click_exact(page, label: str) -> bool:
    return bool(page.evaluate(
        """(label) => {
          const b = [...document.querySelectorAll('button')].find(
            (x) => ((x.innerText || '').trim().replace(/^[^0-9A-Za-z]+/, '')) === label);
          if (!b) return false;
          b.scrollIntoView({block: 'center'});
          b.click();
          return true;
        }""",
        label,
    ))


def trace_lines() -> list[dict]:
    path = DATA / "_mt_key_restore.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(20000)
        page.goto(URL, wait_until="domcontentloaded")
        settle(page, 8)
        for _ in range(20):
            body = page.inner_text("body") or ""
            if len(body.strip()) > 400 and "PAGES" in body.upper():
                break
            settle(page, 3)

        pick_song(page, [], "All the Things You Are", "jazz")
        settle(page, 4)
        set_songs_practice_key(page, "Bb")
        settle(page, 4)
        log(f"STEP 1 song picked, key = {pk_val(page)!r}")

        goto_multitrack(page)
        if not upload(page, "Sax / winds", make_wav("probe-bb.wav")):
            log("FAILED: could not place a take")
            browser.close()
            return 1
        log("STEP 2 take placed in Sax / winds")

        open_library(page)
        if not (click_exact(page, "Save New Project") or click_exact(page, "Save as New Project")):
            log("FAILED: no save button")
            browser.close()
            return 1
        settle(page, 8)
        log(f"STEP 3 project saved, key = {pk_val(page)!r}")

        set_songs_practice_key(page, "E")
        settle(page, 6)
        log(f"STEP 4 key moved away, key = {pk_val(page)!r}")

        before = len(trace_lines())
        goto_multitrack(page)
        open_library(page)
        if not click_exact(page, "Load Project"):
            log("FAILED: no Load Project button (is the project the open one?)")
            # Start a new project so the saved row becomes loadable, then retry.
            click_exact(page, "New Project")
            settle(page, 5)
            if not click_exact(page, "Discard"):
                pass
            settle(page, 5)
            open_library(page)
            if not click_exact(page, "Load Project"):
                log("FAILED: still no Load Project button")
                browser.close()
                return 1
        settle(page, 10)
        log(f"STEP 5 project loaded, key = {pk_val(page)!r}")

        # Force real script runs. goto_multitrack returns immediately when already on
        # the page, so using it as a "nudge" produced no rerun at all - which is what
        # made two earlier measurements look like the key never arrived.
        log("  forcing a rerun by navigating away and back")
        click_nav(page, "Backing")
        settle(page, 6)
        log(f"  on Backing: key = {pk_val(page)!r}")
        click_nav(page, "Multitrack")
        settle(page, 6)
        log(f"  back on Multitrack: key = {pk_val(page)!r}")
        page.reload(wait_until="domcontentloaded")
        settle(page, 10)
        log(f"  after a full reload: key = {pk_val(page)!r}")

        log("\n--- restore trace ---")
        for row in trace_lines()[before:]:
            log(json.dumps(row, ensure_ascii=True))
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
