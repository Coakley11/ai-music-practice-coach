"""Practice Start / Stop icons, as rendered (user 2026-11-20): metronome (Tuner tool + Notation tab),
live tuner, the tool's Close and Generate notation / TAB - at 1280, 390 and 360 px.

Each control: the icon is first, the label is whole (not clipped), it is inside the screen, and it
still works - the metronome counts beats after Start and resets after Stop; the tuner's Start / Stop
swap their disabled states (Chromium's FAKE microphone: this proves the UI, not real pitch detection).

    python -X utf8 scripts/_probe_practice_start_stop.py http://127.0.0.1:<port> [worktree] --width 390
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Frame, Page, sync_playwright

SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS.parent)]
URL = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8678")
WIDTH = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 1280
HEIGHT = 900 if WIDTH > 640 else 800

from music_feature_icons import ACTION_ICONS  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

PLAY, STOP, CLOSE, SHEET = ACTION_ICONS["play"], ACTION_ICONS["stop"], ACTION_ICONS["close"], ACTION_ICONS["sheet_music"]
OUT = SCRIPTS / "evidence-practice-start-stop"
OUT.mkdir(parents=True, exist_ok=True)
GATES: list = []
NOTES: list = []

GEOM_JS = """(el) => { const r = el.getBoundingClientRect(); return {
  text: (el.innerText || '').trim(), aria: el.getAttribute('aria-label') || '',
  disabled: el.disabled === true, clipped: el.scrollWidth > el.clientWidth + 1,
  l: Math.round(r.left), r: Math.round(r.right), w: Math.round(r.width), h: Math.round(r.height)}; }"""
FRAME_BOX_JS = """(sel) => { const out = [];
  document.querySelectorAll('iframe').forEach((f, i) => { const r = f.getBoundingClientRect();
    out.push({i, l: Math.round(r.left), r: Math.round(r.right), w: Math.round(r.width)}); }); return out; }"""


def mark(gate: str, ok: bool, detail: str = "") -> bool:
    GATES.append((gate, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  [{WIDTH}px] {gate}" + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


def settle(page: Page, s: float = 5) -> None:
    wait_idle(page, int(s * 1000))


def frames_with(page: Page, selector: str) -> list[Frame]:
    out = []
    for fr in page.frames:
        try:
            if fr.locator(selector).count():
                out.append(fr)
        except Exception:
            continue
    return out


def frame_offset(page: Page, frame: Frame) -> int:
    try:
        el = frame.frame_element()
        box = el.bounding_box() or {}
        return int(box.get("x") or 0)
    except Exception:
        return 0


def check_button(page: Page, frame: Frame, selector: str, icon: str, words: str, where: str) -> dict | None:
    loc = frame.locator(selector).first
    if not loc.count():
        mark(f"{where}: {words} is on the page", False, "not rendered")
        return None
    loc.scroll_into_view_if_needed()
    g = loc.evaluate(GEOM_JS)
    left = frame_offset(page, frame) + g["l"]
    right = frame_offset(page, frame) + g["r"]
    mark(f"{where}: '{words}' shows {icon} first", g["text"].startswith(icon + " ") and words in g["text"], g["text"])
    mark(f"{where}: '{words}' label whole and on screen", not g["clipped"] and left >= -1 and right <= WIDTH + 1,
         f"l={left} r={right} vw={WIDTH} clipped={g['clipped']}")
    mark(f"{where}: '{words}' keeps an accessible name and a tappable size", bool(g["aria"] or g["text"]) and g["h"] >= 24,
         f"aria={g['aria']!r} h={g['h']}")
    return g


def no_hscroll(page: Page, where: str) -> None:
    sw, cw = page.evaluate("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    mark(f"{where}: no horizontal page scroll", int(sw) <= int(cw) + 2, f"{sw} vs {cw}")


def metronome_works(page: Page, frame: Frame, where: str) -> None:
    beat = frame.locator("#metro-beat").first
    frame.locator("#metro-start").first.click()
    page.wait_for_timeout(2500)
    running = (beat.inner_text() or "").strip()
    frame.locator("#metro-stop").first.click()
    page.wait_for_timeout(800)
    stopped = (beat.inner_text() or "").strip()
    mark(f"{where}: Start still starts the metronome (beat counter moves)", running not in ("", "-"), f"beat={running!r}")
    mark(f"{where}: Stop still stops it (counter resets)", stopped == "-", f"beat={stopped!r}")


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            "--autoplay-policy=no-user-gesture-required"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, permissions=["microphone"])
        page = ctx.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 8)
            pick_song(page, NOTES, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            click_nav(page, "Practice")
            settle(page, 10)
            # ---- A/C/D: Metronome, Tuner & Tone (metronome + live tuner with string targets)
            page.locator('[class*="st-key-practice_tool_pick_time_and_pitch"] button').first.click()
            settle(page, 10)
            page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
            settle(page, 6)
            metros = frames_with(page, "#metro-start")
            mark("Tuner tool: the metronome is rendered", bool(metros), f"frames={len(metros)}")
            if metros:
                check_button(page, metros[0], "#metro-start", PLAY, "Start", "Tuner-tool metronome")
                check_button(page, metros[0], "#metro-stop", STOP, "Stop", "Tuner-tool metronome")
                metronome_works(page, metros[0], "Tuner-tool metronome")
            tuners = frames_with(page, "button.lt-btn")
            mark("Tuner tool: the live tuner is rendered", bool(tuners), f"frames={len(tuners)}")
            if tuners:
                fr = tuners[0]
                s0 = check_button(page, fr, "button.lt-btn.primary", PLAY, "Start Tuner", "Live tuner")
                t0 = check_button(page, fr, "button.lt-btn.danger", STOP, "Stop Tuner", "Live tuner")
                mark("Live tuner: Stop Tuner starts disabled (visibly, label kept)", bool(t0 and t0["disabled"]),
                     f"disabled={(t0 or {}).get('disabled')}")
                fr.locator("button.lt-btn.primary").first.click()
                page.wait_for_timeout(2500)
                s1 = fr.locator("button.lt-btn.primary").first.evaluate(GEOM_JS)
                t1 = fr.locator("button.lt-btn.danger").first.evaluate(GEOM_JS)
                mark("Live tuner: Start Tuner still starts listening (Start disabled, Stop enabled)",
                     s1["disabled"] and not t1["disabled"], f"start.disabled={s1['disabled']} stop.disabled={t1['disabled']}")
                mark("Live tuner: icons stay on the labels while listening", s1["text"].startswith(PLAY) and t1["text"].startswith(STOP),
                     f"{s1['text']!r} / {t1['text']!r}")
                fr.locator("button.lt-btn.danger").first.click()
                page.wait_for_timeout(1200)
                s2 = fr.locator("button.lt-btn.primary").first.evaluate(GEOM_JS)
                t2 = fr.locator("button.lt-btn.danger").first.evaluate(GEOM_JS)
                mark("Live tuner: Stop Tuner still stops (Start enabled, Stop disabled)",
                     not s2["disabled"] and t2["disabled"], f"start.disabled={s2['disabled']} stop.disabled={t2['disabled']}")
                strings = fr.locator("[id$='-strings'] *, .lt-strings *").count()
                NOTES.append(f"tuner string targets rendered: {strings}")
            close = page.locator('[class*="st-key-practice_tool_close_btn"] button').first
            if close.count():
                g = close.evaluate(GEOM_JS)
                mark("Practice tool: Close shows the close icon", g["text"].startswith(CLOSE + " "), g["text"])
                mark("Practice tool: Close label whole and on screen", not g["clipped"] and g["l"] >= -1 and g["r"] <= WIDTH + 1,
                     f"l={g['l']} r={g['r']}")
            else:
                mark("Practice tool: Close is on the page", False, "not rendered")
            no_hscroll(page, "Tuner tool")
            page.screenshot(path=str(OUT / f"tuner-tool-{WIDTH}.png"), full_page=True)
            # ---- B: Notation / TAB metronome (Chart tool)
            if close.count():
                close.click()
                settle(page, 8)
            page.set_viewport_size({"width": 1280, "height": 900})
            settle(page, 3)
            page.locator('[class*="st-key-practice_tool_pick_chart"] button').first.click()
            settle(page, 10)
            exp = page.locator('[data-testid="stExpander"] summary').filter(has_text="Notation / TAB").first
            if exp.count():
                exp.scroll_into_view_if_needed()
                if "Generate notation" not in (page.inner_text('[data-testid="stMain"]') or ""):
                    exp.click()
                    settle(page, 6)
            gen = page.locator('[class*="st-key-practice_generate_notation"] button').first
            if gen.count():
                page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
                settle(page, 5)
                g = gen.evaluate(GEOM_JS)
                mark("Notation: Generate notation / TAB shows the sheet-music icon", g["text"].startswith(SHEET + " "), g["text"])
                mark("Notation: Generate label whole and on screen", not g["clipped"] and g["l"] >= -1 and g["r"] <= WIDTH + 1,
                     f"l={g['l']} r={g['r']}")
                gen.scroll_into_view_if_needed()
                gen.click()
                settle(page, 14)
                metros = frames_with(page, "#metro-start")
                mark("Notation tab: its metronome is rendered after Generate", bool(metros), f"frames={len(metros)}")
                if metros:
                    check_button(page, metros[-1], "#metro-start", PLAY, "Start", "Notation metronome")
                    check_button(page, metros[-1], "#metro-stop", STOP, "Stop", "Notation metronome")
                    metronome_works(page, metros[-1], "Notation metronome")
                no_hscroll(page, "Notation tab")
                page.screenshot(path=str(OUT / f"notation-{WIDTH}.png"), full_page=True)
            else:
                mark("Notation: Generate notation / TAB is on the page", False, "not rendered")
        finally:
            (OUT / f"results-{WIDTH}.json").write_text(json.dumps({"gates": GATES, "notes": NOTES}, indent=1,
                                                               ensure_ascii=False), encoding="utf-8")
            browser.close()
    failed = [g for g, ok, _ in GATES if not ok]
    print(f"\n{len(GATES) - len(failed)}/{len(GATES)} gates passed at {WIDTH}px")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
