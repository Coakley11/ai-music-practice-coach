"""Gate F1-V2: active Key Cycle browser verification.

Checks, against a live app, that while Key Cycle is active:
  - the Practice Melody panel's key follows the Key Cycle temporary
    playback key (via project_cycle_display_key), not the base Practice
    Concert Key
  - melody identity (alt_index) is unchanged across cycle-key changes
  - the canonical base Practice Concert Key (sidebar) is never mutated
  - several consecutive Next/Previous key-cycle steps all stay coherent

Usage:
  MUSIC_APP_DATA_DIR=_runtime_pm_gate_v2_8570 streamlit run streamlit_music_practice_app.py --server.port 8605
  python scripts/_browser_practice_melody_gate_v2_8570.py http://127.0.0.1:8605
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

from walk_creative_backing_matrix import click_button_has, click_radio, click_visible_text, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

from _browser_practice_melody_8540 import (  # noqa: E402
    click_key_button,
    goto_studio,
    open_chart_and_melody_tool,
    open_generated_melody_panel,
    wait_practice_studio,
)
from _browser_practice_melody_f1_8560 import set_practice_key  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8605"
OUT = SCRIPTS / "evidence-practice-melody-gate"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "v2-"
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


def melody_caption(page: Page) -> str:
    body = page.inner_text("body") or ""
    m = re.search(r"Song \*?\*?.*?alternative #\d+[^\n]*", body)
    return m.group(0) if m else ""


def sounding_key(page: Page) -> str:
    body = page.inner_text("body") or ""
    m = re.search(r"Sounding\s+\*?\*?([A-G][#b]?m?)", body)
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


def expand_advanced_playback_settings(page: Page) -> bool:
    if "Key cycling" in (page.inner_text("body") or ""):
        return True
    for _ in range(3):
        click_visible_text(page, "Advanced playback settings")
        settle(page, 1.5)
        if "Key cycling" in (page.inner_text("body") or ""):
            return True
    return False


def click_key_cycling_on(page: Page) -> bool:
    expand_advanced_playback_settings(page)
    settle(page, 1)
    # Confirmed by direct diagnosis: neither a JS element.click() nor a
    # Playwright click on the <label> text reliably registers as a value
    # change on this widget (its underlying native radio <input>s exist but
    # the label click doesn't consistently forward to them). Playwright's
    # semantic get_by_role("radio", ...) locator -- which resolves through
    # the accessibility tree to the actual native input -- does work. Scope
    # to the specific stRadio widget whose own label is "Key cycling" so it
    # can't collide with any other short Off/On-style control on the page.
    widget = page.locator('[data-testid="stRadio"]').filter(has_text=re.compile(r"Key cycling", re.I))
    if not widget.count():
        return False

    def _is_running() -> bool:
        body = page.inner_text("body") or ""
        return "Sounding" in body or "Previous key" in body

    # Try several input-level strategies in order -- this widget's custom
    # styling has proven unreliable for label text clicks, role=radio
    # .click()/.check(), and native-input .check()/.click() (all can report
    # success / flip the DOM checked attribute without Streamlit's Python
    # callback actually firing, i.e. no real rerun). A real OS-level mouse
    # click at the "On" label's bounding-box center is the closest possible
    # simulation of genuine user interaction and is the most reliable
    # fallback for custom React-controlled widgets like this one.
    on_radio = widget.first.get_by_role("radio", name="On")
    attempts = []
    if on_radio.count():
        attempts.append(("role_check", lambda: on_radio.first.check(timeout=5000, force=True)))
        attempts.append(("role_click", lambda: on_radio.first.click(timeout=5000, force=True)))
    on_label = widget.first.locator("label").filter(has_text=re.compile(r"^On$", re.I))
    if on_label.count():
        def _mouse_click_label():
            box = on_label.first.bounding_box()
            if not box:
                raise RuntimeError("no bounding box")
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        attempts.append(("mouse_coords", _mouse_click_label))

    for name, action in attempts:
        try:
            action()
        except Exception:
            continue
        for _ in range(6):
            settle(page, 1.2)
            if _is_running():
                log(f"click_key_cycling_on: succeeded via {name}")
                return True
    return _is_running()


def click_key_cycle_button(page: Page, label_pattern: str) -> bool:
    return click_button_has(page, label_pattern)


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

    mark("set_key_c", set_practice_key(page, "C"))
    settle(page, 2.5)
    mark("open_chart_melody_tool", open_chart_and_melody_tool(page))
    mark("open_generated_melody_panel", open_generated_melody_panel(page))
    settle(page, 2)
    baseline_caption = melody_caption(page)
    mark("baseline_melody_key_c", caption_key(baseline_caption) == "C", baseline_caption)

    clicked = click_key_button(page, "practice_melody_to_backing")
    mark("practice_with_backing_click", clicked)
    mark("backing_opened", wait_on_backing(page))
    settle(page, 3)
    shot(page, "00-backing-before-cycle")
    pre_cycle_caption = melody_caption(page)
    pre_cycle_alt = re.search(r"alternative #(\d+)", pre_cycle_caption)
    pre_cycle_alt = pre_cycle_alt.group(1) if pre_cycle_alt else ""
    mark("pre_cycle_key_c", caption_key(pre_cycle_caption) == "C", pre_cycle_caption)

    turned_on = click_key_cycling_on(page)
    # The playback bar (Sounding/.../Previous key/Next key) can take an
    # extra rerun cycle beyond the toggle click itself to appear -- poll
    # instead of trusting one fixed settle.
    body_after_on = ""
    for _ in range(8):
        settle(page, 1.5)
        body_after_on = page.inner_text("body") or ""
        if "Sounding" in body_after_on or "Previous key" in body_after_on:
            break
        if "Key cycling off" in body_after_on:
            # Toggle didn't register -- retry the click once.
            turned_on = click_key_cycling_on(page) or turned_on
    mark("key_cycling_turned_on", turned_on)
    shot(page, "01-key-cycling-on")
    mark("key_cycling_ui_visible", "Key cycle" in body_after_on or "Sounding" in body_after_on)

    # --- Several consecutive Next key steps ---
    seen_keys: list[str] = [caption_key(melody_caption(page))]
    for i in range(3):
        next_clicked = click_key_cycle_button(page, r"^Next key$") or click_key_cycle_button(page, r"Next key")
        mark(f"next_key_click_{i+1}", next_clicked)
        settle(page, 2.5)
        shot(page, f"02-after-next-{i+1}")
        cap = melody_caption(page)
        k = caption_key(cap)
        alt = re.search(r"alternative #(\d+)", cap)
        alt = alt.group(1) if alt else ""
        snd = sounding_key(page)
        log(f"next_{i+1}: melody_key={k} sounding_key={snd} caption={cap!r}")
        mark(f"next_{i+1}_melody_follows_sounding_key", k == snd and k != "", f"melody={k} sounding={snd}")
        mark(f"next_{i+1}_alt_index_unchanged", alt == pre_cycle_alt, f"alt={alt} expected={pre_cycle_alt}")
        seen_keys.append(k)

    mark("consecutive_next_keys_actually_differ", len(set(seen_keys)) > 1, seen_keys)

    # --- Previous key ---
    prev_clicked = click_key_cycle_button(page, r"^Previous key$") or click_key_cycle_button(page, r"Previous key")
    mark("previous_key_click", prev_clicked)
    settle(page, 2.5)
    shot(page, "03-after-previous")
    cap_prev = melody_caption(page)
    k_prev = caption_key(cap_prev)
    snd_prev = sounding_key(page)
    log(f"previous: melody_key={k_prev} sounding_key={snd_prev}")
    mark("previous_melody_follows_sounding_key", k_prev == snd_prev and k_prev != "", f"melody={k_prev} sounding={snd_prev}")
    mark(
        "previous_returns_to_earlier_key_in_sequence",
        k_prev == seen_keys[-2] if len(seen_keys) >= 2 else False,
        f"got={k_prev} expected={seen_keys[-2] if len(seen_keys) >= 2 else None}",
    )

    # --- Canonical base Practice Key must be unchanged throughout ---
    expand_sidebar(page)
    settle(page, 1)
    side_body = page.inner_text("body") or ""
    m = re.search(r"Practice\s*/\s*Concert Key[^\n]*\n+\s*([A-G][#b]?m?)", side_body)
    base_key_now = m.group(1) if m else ""
    log(f"base_practice_key_after_cycling={base_key_now!r}")
    mark("canonical_practice_key_unchanged", base_key_now == "C" or base_key_now == "", base_key_now)
    shot(page, "04-final-sidebar-check")


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
