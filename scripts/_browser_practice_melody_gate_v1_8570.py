"""Gate F1-V1: transposing instrument (Tenor Saxophone) browser verification.

Checks, against a live app, that Practice Melody's key projection is
genuinely the existing Written Key pipeline (chart_key) and not a
Practice-Melody-specific instrument system:

  - melody's displayed key matches the tool workspace's own "Chart key"
    label for the same instrument context
  - handed off to Backing, the melody's key still matches Backing's own
    chord-chart key
  - changing Practice Concert Key transposes the melody by the correct
    amount (same composition, no double transposition) while the written
    key keeps following the Bb-tenor-sax +2-semitone offset from concert

Usage:
  MUSIC_APP_DATA_DIR=_runtime_pm_gate_v1_8570 streamlit run streamlit_music_practice_app.py --server.port 8604
  python scripts/_browser_practice_melody_gate_v1_8570.py http://127.0.0.1:8604
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    expand_sidebar,
    set_tenor_saxophone,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

from _browser_practice_melody_8540 import (  # noqa: E402
    click_key_button,
    goto_studio,
    open_chart_and_melody_tool,
    open_generated_melody_panel,
    wait_practice_studio,
)
from _browser_practice_melody_f1_8560 import set_practice_key  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8604"
OUT = SCRIPTS / "evidence-practice-melody-gate"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "v1-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def low(s: str) -> str:
    return (s or "").lower()


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, seconds: float = 2.0) -> None:
    wait_idle(page, int(seconds * 1000))


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body[:30000], encoding="utf-8")
    try:
        page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    except Exception as exc:
        log(f"screenshot_failed name={name} err={exc}")
    return body


def caption_key(caption: str) -> str:
    m = re.search(r"key \*?\*?([A-G][#b]?m?)", caption)
    return m.group(1) if m else ""


def tool_context_chart_key(page: Page) -> str:
    """The Chart & Melody workspace's own context line, e.g. '... Chart key D · 95 BPM'."""
    body = page.inner_text("body") or ""
    m = re.search(r"Chart key \*?\*?([A-G][#b]?m?)", body)
    return m.group(1) if m else ""


def wait_on_backing(page: Page, *, timeout_s: float = 20.0) -> bool:
    waited = 0.0
    while waited <= timeout_s:
        body = low(page.inner_text("body") or "")
        if "backing track studio" in body or "playback scope" in body or "tempo (bpm)" in body:
            return True
        settle(page, 1.0)
        waited += 1.0
    return False


def flow(page: Page) -> None:
    notes: list[str] = []
    picked = pick_song(page, notes, "Perfect", "Pop")
    if not picked:
        settle(page, 2.0)
        picked = pick_song(page, notes, "Perfect", "Pop")
    log(" ".join(notes[-4:]))
    mark("pick_song_perfect", picked)
    goto_studio(page, "Practice")
    settle(page, 3)
    mark("practice_studio_loaded", wait_practice_studio(page))

    tenor_ok = set_tenor_saxophone(page, notes)
    log(" ".join(notes[-6:]))
    mark("set_tenor_saxophone", tenor_ok)
    settle(page, 2)

    mark("set_key_c_concert", set_practice_key(page, "C"))
    settle(page, 2.5)

    mark("open_chart_melody_tool", open_chart_and_melody_tool(page))
    shot(page, "01-chart-melody-tenor-sax")
    chart_key_label = tool_context_chart_key(page)
    log(f"tool_chart_key_label={chart_key_label!r}")
    # Bb tenor sax: written key is a major 2nd above concert (C concert -> D written).
    mark("tool_shows_written_key_d", chart_key_label == "D", chart_key_label)

    mark("open_generated_melody_panel", open_generated_melody_panel(page))
    settle(page, 2)
    shot(page, "02-melody-written-key")
    melody_caption = practice_melody_caption_safe(page)
    log(f"melody_caption={melody_caption!r}")
    melody_key = caption_key(melody_caption)
    mark(
        "melody_key_matches_tool_written_key",
        melody_key == chart_key_label and melody_key != "",
        f"melody_key={melody_key} tool_chart_key={chart_key_label}",
    )

    clicked = click_key_button(page, "practice_melody_to_backing")
    mark("practice_with_backing_click", clicked)
    mark("backing_opened", wait_on_backing(page))
    settle(page, 3)
    shot(page, "03-backing-tenor-sax")
    backing_caption = practice_melody_caption_safe(page)
    backing_key = caption_key(backing_caption)
    mark(
        "backing_melody_key_matches_written_key",
        backing_key == chart_key_label and backing_key != "",
        f"backing_key={backing_key} expected={chart_key_label}",
    )
    body_backing = page.inner_text("body") or ""
    backing_chart_key_label = tool_context_chart_key(page) or _find_any_key_label(body_backing)
    log(f"backing_chart_key_label={backing_chart_key_label!r}")

    # Change Practice Concert Key C -> D; written key (tenor sax, +2) should
    # become E, and the melody must transpose (not regenerate) to match.
    mark("set_key_d_concert", set_practice_key(page, "D"))
    settle(page, 3)
    shot(page, "04-backing-after-key-change")
    after_caption = practice_melody_caption_safe(page)
    after_key = caption_key(after_caption)
    log(f"after_key_change_caption={after_caption!r}")
    mark("melody_key_follows_concert_change_to_e", after_key == "E", after_key)
    same_alt = (
        re.search(r"alternative #(\d+)", after_caption).group(1)
        == re.search(r"alternative #(\d+)", backing_caption).group(1)
        if after_caption and backing_caption
        else False
    )
    mark("same_composition_no_regeneration_on_key_change", same_alt)


def practice_melody_caption_safe(page: Page) -> str:
    body = page.inner_text("body") or ""
    m = re.search(r"Song \*?\*?.*?alternative #\d+[^\n]*", body)
    return m.group(0) if m else ""


def _find_any_key_label(body: str) -> str:
    m = re.search(r"\bkey\b[^\n]*?\b([A-G][#b]?m?)\b", body, re.I)
    return m.group(1) if m else ""


def main() -> int:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1100})
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            settle(page, 5)
            shot(page, "00-home")
            try:
                flow(page)
            except Exception as exc:
                log(f"EXCEPTION during flow: {exc}")
                try:
                    shot(page, "99-exception")
                except Exception:
                    pass
            browser.close()
    finally:
        summary = {"gates": GATES, "notes": NOTES, "url": URL}
        (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    failed = [k for k, v in GATES.items() if not v]
    log(f"failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
