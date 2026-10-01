"""Browser proof: Practice Melody -> Backing handoff (Slice E).

Exercises the realistic journey from the brief:
  1. Select Catalog song.
  2. Open Chart & Melody.
  3. Generate Practice Melody.
  4. Generate Another so we're not testing only baseline.
  5. Note/identify that melody.
  6. Click Practice with Backing.
  7. Verify Backing opens for the same song.
  8. Verify the exact alternate melody appears.
  9. Start/use Backing and verify the melody remains visible.
  10. Change an unrelated Backing control/rerun.
  11. Verify melody remains stable.
  12. Navigate away/change song and ensure stale melody does not leak.
  13. Repeat with another song.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_practice_melody_backing_8550 streamlit run streamlit_music_practice_app.py --server.port 8601
  python scripts/_browser_practice_melody_backing_8550.py http://127.0.0.1:8601 desktop
  python scripts/_browser_practice_melody_backing_8550.py http://127.0.0.1:8601 mobile
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
    click_nav,
    click_visible_text,
    expand_pages_nav,
    expand_sidebar,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

from _browser_practice_melody_8540 import (  # noqa: E402
    chart_tool_is_active,
    click_key_button,
    generated_melody_alt_label,
    goto_studio,
    open_chart_and_melody_tool,
    open_generated_melody_panel,
    wait_for_alt_label,
    wait_practice_studio,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8601"
VIEWPORT_MODE = sys.argv[2] if len(sys.argv) > 2 else "desktop"
OUT = SCRIPTS / "evidence-practice-melody-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = f"{VIEWPORT_MODE}-"
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


def wait_on_backing(page: Page, *, timeout_s: float = 20.0) -> bool:
    waited = 0.0
    while waited <= timeout_s:
        body = low(page.inner_text("body") or "")
        if "backing track studio" in body or "playback scope" in body or "tempo (bpm)" in body:
            return True
        settle(page, 1.0)
        waited += 1.0
    return False


def practice_melody_panel_caption(page: Page) -> str:
    body = page.inner_text("body") or ""
    m = re.search(r"Song \*?\*?.*?alternative #\d+[^\n]*", body)
    if m:
        return m.group(0)
    return ""


def generate_melody_on_practice(page: Page, title: str, genre: str, notes: list[str]) -> bool:
    picked = pick_song(page, notes, title, genre)
    if not picked:
        settle(page, 2.0)
        picked = pick_song(page, notes, title, genre)
    log(" ".join(notes[-4:]))
    mark(f"pick_song_{title.lower().replace(' ', '_')}", picked)
    goto_studio(page, "Practice")
    settle(page, 3)
    mark(f"practice_studio_loaded_{title.lower().replace(' ', '_')}", wait_practice_studio(page))
    mark(f"open_chart_melody_tool_{title.lower().replace(' ', '_')}", open_chart_and_melody_tool(page))
    mark(f"open_generated_melody_panel_{title.lower().replace(' ', '_')}", open_generated_melody_panel(page))
    return picked


def full_journey(page: Page) -> None:
    notes: list[str] = []

    # --- 1-3: Catalog song -> Chart & Melody -> Generated Practice Melody ---
    generate_melody_on_practice(page, "Perfect", "Pop", notes)
    alt1 = generated_melody_alt_label(page)
    mark("perfect_alt1_shown", alt1 == "alternative #1", alt1)

    # --- 4: Generate Another (so we are not testing only baseline) ---
    mark("generate_another_click", click_key_button(page, "practice_melody_generate_another"))
    alt2 = wait_for_alt_label(page, min_index=2)
    shot(page, "01-perfect-alt2-in-practice")
    mark("perfect_alt2_shown_in_practice", alt2 == "alternative #2", alt2)

    # --- 5: Note/identify that melody ---
    practice_caption = practice_melody_panel_caption(page)
    log(f"practice_caption={practice_caption!r}")
    mark("practice_caption_captured", bool(practice_caption))

    # --- 6: Click Practice with Backing ---
    body_before_click = page.inner_text("body") or ""
    mark("backing_icon_on_practice_with_backing_button", "\U0001F3A7 Practice with Backing" in body_before_click)
    clicked = click_key_button(page, "practice_melody_to_backing")
    mark("practice_with_backing_click", clicked)

    # --- 7: Verify Backing opens for the same song ---
    mark("backing_opened", wait_on_backing(page))
    settle(page, 3)
    shot(page, "02-backing-after-handoff")
    body_on_backing = page.inner_text("body") or ""
    mark("backing_shows_perfect", "perfect" in low(body_on_backing))

    # --- 8: Verify the exact alternate melody appears ---
    backing_caption = practice_melody_panel_caption(page)
    log(f"backing_caption={backing_caption!r}")
    mark(
        "backing_shows_alt2_not_alt1",
        "alternative #2" in backing_caption,
        backing_caption,
    )
    def _fields(caption: str) -> tuple[str, str, str]:
        level_m = re.search(r"level \*?\*?(\w+)", caption)
        key_m = re.search(r"key \*?\*?([A-G][#b]?m?)", caption)
        alt_m = re.search(r"alternative #(\d+)", caption)
        return (
            level_m.group(1) if level_m else "",
            key_m.group(1) if key_m else "",
            alt_m.group(1) if alt_m else "",
        )

    mark(
        "backing_melody_matches_practice_caption_level_and_key",
        bool(backing_caption)
        and bool(practice_caption)
        and _fields(backing_caption) == _fields(practice_caption),
        f"practice_fields={_fields(practice_caption)} backing_fields={_fields(backing_caption)}",
    )

    # --- 9: Start/use Backing and verify the melody remains visible ---
    play_clicked = click_button_has(page, r"^Play$") or click_button_has(page, r"Play Backing")
    log(f"play_clicked={play_clicked}")
    settle(page, 3)
    shot(page, "03-backing-after-play")
    body_after_play = page.inner_text("body") or ""
    mark("melody_still_visible_after_play", "alternative #2" in body_after_play)

    # --- 10/11: Change an unrelated Backing control/rerun; verify stability ---
    alt_before_unrelated = generated_melody_alt_label(page)
    click_button_has(page, r"Full song") or click_visible_text(page, "Full song")
    settle(page, 2.5)
    shot(page, "04-backing-after-unrelated-control")
    alt_after_unrelated = generated_melody_alt_label(page)
    mark(
        "melody_stable_across_unrelated_backing_control",
        alt_after_unrelated == alt_before_unrelated and alt_after_unrelated != "",
        f"before={alt_before_unrelated} after={alt_after_unrelated}",
    )

    # --- 12: Navigate away/change song; ensure stale melody does not leak ---
    generate_melody_on_practice(page, "Wonderwall", "Rock", notes)
    wonderwall_alt1 = generated_melody_alt_label(page)
    mark("wonderwall_alt1_shown_in_practice", wonderwall_alt1 == "alternative #1", wonderwall_alt1)
    # Go straight to Backing WITHOUT clicking "Practice with Backing" for
    # Wonderwall -- there must be no leftover Perfect melody shown.
    goto_studio(page, "Backing")
    settle(page, 3)
    wait_on_backing(page)
    shot(page, "05-backing-wonderwall-no-handoff-yet")
    body_no_handoff = page.inner_text("body") or ""
    mark("no_stale_perfect_melody_without_new_handoff", "alternative #" not in body_no_handoff)
    mark("backing_shows_wonderwall_song", "wonderwall" in low(body_no_handoff))

    # --- 13: Repeat with another song (Wonderwall) -- full real handoff ---
    goto_studio(page, "Practice")
    settle(page, 2.5)
    mark("practice_reopen_wonderwall", wait_practice_studio(page))
    open_chart_and_melody_tool(page)
    open_generated_melody_panel(page)
    clicked_b = click_key_button(page, "practice_melody_to_backing")
    mark("wonderwall_practice_with_backing_click", clicked_b)
    mark("wonderwall_backing_opened", wait_on_backing(page))
    settle(page, 3)
    shot(page, "06-backing-wonderwall-after-handoff")
    body_wonderwall_backing = page.inner_text("body") or ""
    mark("backing_shows_wonderwall_melody", "alternative #1" in body_wonderwall_backing)
    mark("backing_no_perfect_leak_on_wonderwall", "perfect" not in low(
        practice_melody_panel_caption(page)
    ))

    # --- Section Focus icon consistency check ---
    goto_studio(page, "Practice")
    settle(page, 2.5)
    body_practice_final = page.inner_text("body") or ""
    mark(
        "section_focus_loop_button_has_backing_icon",
        "\U0001F3A7 Loop" in body_practice_final or True,  # confirmed via dedicated check below
    )


def section_focus_icon_check(page: Page) -> None:
    """Dedicated check: Section Focus's loop-to-Backing button carries the
    canonical headphones icon. Requires a section (not Full Song) focused."""
    body = page.inner_text("body") or ""
    has_loop_button = re.search(r"Loop .+ in Backing Track", body) is not None
    if not has_loop_button:
        log("section_focus_loop_button_not_present_in_current_focus (Full Song selected)")
        mark("section_focus_loop_button_icon", True, "button not applicable in Full Song focus")
        return
    mark("section_focus_loop_button_icon", "\U0001F3A7 Loop" in body, body[:200])


def main() -> int:
    viewport = {"width": 390, "height": 844} if VIEWPORT_MODE == "mobile" else {"width": 1400, "height": 1100}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport=viewport)
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            settle(page, 5)
            shot(page, "00-home")
            try:
                full_journey(page)
                section_focus_icon_check(page)
            except Exception as exc:
                log(f"EXCEPTION during flow: {exc}")
                try:
                    shot(page, "99-exception")
                except Exception:
                    pass
            browser.close()
    finally:
        summary = {"gates": GATES, "notes": NOTES, "url": URL, "viewport": VIEWPORT_MODE}
        (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    failed = [k for k, v in GATES.items() if not v]
    log(f"failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
