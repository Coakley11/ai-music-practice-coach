"""Measure click → effect latency for Backing transport + settings controls.

For each control this records, in milliseconds from the click:

* ``label_ms``  — first visible change to the transport label / control text
* ``audio_ms``  — first change in the live <audio> state (paused flag or src)
* ``settle_ms`` — when Streamlit finished the rerun it triggered (spinner gone)

Those three separate "client transport" from "Streamlit rerun" so we can see
which layer each delay belongs to.

Usage:
  python scripts/_probe_transport_latency.py http://127.0.0.1:8530 OUT_DIR [tag]
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from playwright.sync_api import Page, sync_playwright  # noqa: E402

from _walk_pass8_nav_first_click import click_sidebar_once, expand_pages  # noqa: E402
from walk_creative_backing_matrix import click_nav, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8530"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else SCRIPTS / "evidence-transport"
TAG = sys.argv[3] if len(sys.argv) > 3 else "before"
OUT.mkdir(parents=True, exist_ok=True)

POLL_MS = 40
MAX_WAIT_MS = 25000

_BUSY_JS = r"""() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  const running = !!(w && /running|stop/i.test(w.innerText || ''));
  return running || !!document.querySelector('[data-stale="true"]');
}"""

# One snapshot of everything we time against.
_STATE_JS = r"""() => {
  const btn = document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"] button');
  const label = btn ? (btn.innerText || btn.textContent || '').replace(/\s+/g,' ').trim() : '';
  let a = document.querySelector('audio');
  if (!a) {
    for (const f of document.querySelectorAll('iframe')) {
      try { const d = f.contentDocument; if (d) { const x = d.querySelector('audio'); if (x) { a = x; break; } } } catch(e) {}
    }
  }
  const bufs = ['kc-buf-0','kc-buf-1'].map((id) => {
    const el = document.getElementById(id);
    return el ? {paused: el.paused, t: Math.round((el.currentTime||0)*100)/100, src: (el.currentSrc||'').slice(-24), muted: el.muted} : null;
  });
  const card = document.querySelector('#motif-live-card, [data-testid="stMarkdownContainer"]');
  return {
    label,
    audio: a ? {paused: a.paused, t: Math.round((a.currentTime||0)*100)/100, src: (a.currentSrc||'').slice(-24), muted: a.muted} : null,
    bufs,
    body: (document.body.innerText || '').slice(0, 0),  // not needed; keep payload small
  };
}"""


def settle(page: Page, timeout: float = 180.0) -> None:
    end = time.time() + timeout
    quiet = 0
    page.wait_for_timeout(300)
    while time.time() < end:
        quiet = 0 if page.evaluate(_BUSY_JS) else quiet + 1
        if quiet >= 3:
            return
        page.wait_for_timeout(300)
    raise TimeoutError("Streamlit did not settle")


def audio_sig(state: dict) -> tuple:
    a = state.get("audio") or {}
    bufs = tuple(
        (b or {}).get("paused") if b else None for b in (state.get("bufs") or [])
    )
    srcs = tuple((b or {}).get("src") if b else None for b in (state.get("bufs") or []))
    return (a.get("paused"), a.get("src"), a.get("muted"), bufs, srcs)


def measure(page: Page, name: str, click, *, expect_audio: bool = True) -> dict:
    """Click, then poll for the first label change, audio change, and settle."""
    before = page.evaluate(_STATE_JS)
    t0 = time.perf_counter()
    click()
    label_ms = audio_ms = None
    deadline = t0 + MAX_WAIT_MS / 1000.0
    # Both ends of this comparison must come from the same clock: perf_counter,
    # not time.time() (epoch), or the loop exits immediately and never samples.
    while time.perf_counter() < deadline and (
        label_ms is None or (expect_audio and audio_ms is None)
    ):
        now = page.evaluate(_STATE_JS)
        el = (time.perf_counter() - t0) * 1000.0
        if label_ms is None and now.get("label") != before.get("label"):
            label_ms = round(el)
        if audio_ms is None and audio_sig(now) != audio_sig(before):
            audio_ms = round(el)
        if label_ms is not None and (audio_ms is not None or not expect_audio):
            break
        page.wait_for_timeout(POLL_MS)
    try:
        settle(page)
        settle_ms = round((time.perf_counter() - t0) * 1000.0)
    except TimeoutError:
        settle_ms = None
    after = page.evaluate(_STATE_JS)
    row = {
        "control": name,
        "label_ms": label_ms,
        "audio_ms": audio_ms,
        "settle_ms": settle_ms,
        "label_before": before.get("label"),
        "label_after": after.get("label"),
        "audio_before": before.get("audio"),
        "audio_after": after.get("audio"),
    }
    print(
        f"  {name:22} label={label_ms!s:>6}ms audio={audio_ms!s:>6}ms settle={settle_ms!s:>6}ms"
        f"  [{before.get('label')!r} -> {after.get('label')!r}]",
        flush=True,
    )
    return row


def click_key(page: Page, key: str):
    def _do():
        btn = page.locator(f".st-key-{key}").locator("button").first
        btn.scroll_into_view_if_needed()
        btn.click(no_wait_after=True)
    return _do


def click_text_in_frames(page: Page, needle: str):
    """Click a raw HTML button (live follow-along) wherever it lives."""
    def _do():
        page.evaluate(
            """(label) => {
              const docs = [document];
              document.querySelectorAll('iframe').forEach((f) => {
                try { if (f.contentDocument) docs.push(f.contentDocument); } catch(e) {}
              });
              for (const d of docs) {
                const b = [...d.querySelectorAll('button')].find(
                  (el) => ((el.innerText || el.textContent || '').trim()).includes(label));
                if (b) { b.click(); return true; }
              }
              return false;
            }""",
            needle,
        )
    return _do


def open_backing(page: Page) -> None:
    page.goto(URL, wait_until="domcontentloaded", timeout=180000)
    settle(page)
    expand_pages(page)
    notes: list[str] = []
    for _ in range(2):
        if pick_song(page, notes, "Perfect", "Pop"):
            break
        settle(page)
    settle(page)
    click_nav(page, "Backing") or click_sidebar_once(page, "Backing")
    settle(page)


def main() -> None:
    rows: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--disable-dev-shm-usage", "--disable-gpu", "--no-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.set_default_timeout(60000)
        open_backing(page)

        # Guitar + capo shape so the capo-fret display is exercised too.
        try:
            set_baseweb_select(page, "Instrument", "Guitar")
            settle(page)
        except Exception as exc:
            print(f"  (instrument select skipped: {exc})", flush=True)

        print("[play]", flush=True)
        for _ in range(6):
            if page.evaluate("() => !!document.querySelector('audio')"):
                break
            page.evaluate(
                """() => {
                  const b = [...document.querySelectorAll('button')].find(
                    (el) => (el.innerText || '').includes('Play Backing Track'));
                  if (b) b.click();
                }"""
            )
            settle(page)

        # Key cycling on
        page.evaluate(
            """() => {
              const sums = [...document.querySelectorAll('summary')];
              for (const s of sums) {
                if ((s.innerText||'').toLowerCase().includes('advanced playback')) { s.click(); return; }
              }
            }"""
        )
        settle(page)
        page.evaluate(
            """() => {
              const radios = [...document.querySelectorAll('[data-testid="stRadio"]')];
              for (const r of radios) {
                if ((r.innerText||'').toLowerCase().includes('key cycling')) {
                  const lab = [...r.querySelectorAll('label')].find(
                    (l) => (l.innerText||'').trim() === 'On');
                  if (lab) { lab.click(); return; }
                }
              }
            }"""
        )
        settle(page)
        cycling = page.evaluate("() => (document.body.innerText||'').includes('Turn off cycling')")
        print(f"[key cycling on] {cycling}", flush=True)

        print(f"[measure: {TAG}]", flush=True)
        rows.append(measure(page, "pause", click_key(page, "backing_key_cycle_pause_btn")))
        rows.append(measure(page, "resume", click_key(page, "backing_key_cycle_pause_btn")))
        rows.append(measure(page, "next_key", click_key(page, "backing_key_cycle_advance_btn")))
        rows.append(measure(page, "previous_key", click_key(page, "backing_key_cycle_prev_btn")))

        # Back to loop start lives in the live follow-along panel.
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find(
                (el) => (el.innerText||'').includes('Open lead sheet'));
              if (b) b.click();
            }"""
        )
        settle(page)
        rows.append(
            measure(page, "back_to_loop_start", click_text_in_frames(page, "Back to loop start"))
        )

        # Settings
        def sel(label: str, value: str):
            def _do():
                set_baseweb_select(page, label, value)
            return _do

        for name, label, value in (
            ("scope", "Section scope", "Full song"),
            ("feel", "Groove style", "Blues groove"),
        ):
            try:
                rows.append(measure(page, name, sel(label, value), expect_audio=False))
            except Exception as exc:
                print(f"  {name:22} SKIPPED ({type(exc).__name__})", flush=True)

        try:
            def bump_bpm():
                page.evaluate(
                    """() => {
                      const b = [...document.querySelectorAll('button')].find(
                        (el) => (el.innerText||'').trim() === '+');
                      if (b) b.click();
                    }"""
                )
            rows.append(measure(page, "bpm", bump_bpm, expect_audio=False))
        except Exception as exc:
            print(f"  bpm SKIPPED ({type(exc).__name__})", flush=True)

        capo = page.evaluate(
            """() => {
              const t = document.body.innerText || '';
              const m = t.match(/[^\\n]*(capo|fret)[^\\n]*/i);
              return m ? m[0].trim().slice(0, 160) : '';
            }"""
        )
        print(f"[capo text] {capo!r}", flush=True)
        page.screenshot(path=str(OUT / f"transport_{TAG}.png"), full_page=True)
        browser.close()

    report = {"tag": TAG, "rows": rows, "capo_text": capo}
    (OUT / f"TRANSPORT_LATENCY_{TAG}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
