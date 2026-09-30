"""Browser proof: Practice page "Chart & Melody" / Generated Practice Melody
(Slice B+C). Exercises the real Practice workflow end to end:

  1. Catalog song -> Generated Practice Melody
  2. Generate Another Melody
  3. Generate again
  4. change level
  5. change song
  6. return to first song
  7. change unrelated Practice controls/rerun
  8. verify existing Chord Chart and Notation/TAB still work

Usage:
  MUSIC_APP_DATA_DIR=_runtime_practice_melody_8540 streamlit run streamlit_music_practice_app.py --server.port 8596
  python scripts/_browser_practice_melody_8540.py http://127.0.0.1:8596 desktop
  python scripts/_browser_practice_melody_8540.py http://127.0.0.1:8596 mobile
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
    click_radio,
    click_visible_text,
    expand_pages_nav,
    expand_sidebar,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402


def goto_studio(page: Page, name: str) -> bool:
    """Proven navigation helper, mirrored from walk_practice_loop_backing.py
    (not imported directly -- that module reads sys.argv at import time)."""
    expand_sidebar(page)
    expand_pages_nav(page)
    labels = {
        "Practice": ["Practice"],
        "Songs": ["Song Selection", "Songs"],
        "Backing": ["Backing Track", "Backing"],
        "Custom": ["Custom Progression", "Custom"],
        "Compose": ["Composition Studio", "Compose"],
        "Creative": ["Creative Lab", "Creative"],
    }
    needles = labels.get(name, [name])
    clicked = page.evaluate(
        """(needles) => {
          const sidebar = document.querySelector('section[data-testid="stSidebar"]');
          const root = sidebar || document;
          const buttons = [...root.querySelectorAll('button')].filter((b) => b.offsetParent);
          const norm = (el) => (el.innerText || '').replace(/^[\\s\\S]*?([A-Za-z][A-Za-z ]+)$/, '$1').trim().toLowerCase();
          for (const needle of needles) {
            const n = String(needle).toLowerCase();
            const b = buttons.find((btn) => {
              const lines = (btn.innerText || '').split('\\n').map((x) => x.trim()).filter(Boolean);
              const last = (lines[lines.length - 1] || '').toLowerCase();
              const joined = (btn.innerText || '').trim().toLowerCase();
              if (last === 'practice log' || joined.includes('practice log')) return false;
              return last === n || joined === n || joined.endsWith(' ' + n);
            });
            if (b) { b.click(); return true; }
          }
          return false;
        }""",
        needles,
    )
    if clicked:
        wait_idle(page, 3500)
        return True
    return click_nav(page, name)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8596"
VIEWPORT_MODE = sys.argv[2] if len(sys.argv) > 2 else "desktop"
OUT = SCRIPTS / "evidence-practice-melody"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = f"ui-{VIEWPORT_MODE}-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def low(s: str) -> str:
    return (s or "").lower().replace("’", "'")


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
    except Exception as exc:  # pragma: no cover - best effort evidence
        log(f"screenshot_failed name={name} err={exc}")
    return body


def click_key_button(page: Page, session_key: str, *, timeout: int = 5000) -> bool:
    loc = page.locator(f'[class*="st-key-{session_key}"] button')
    if not loc.count():
        return False
    try:
        loc.first.scroll_into_view_if_needed()
        loc.first.click(timeout=timeout)
        return True
    except Exception:
        return False


def wait_practice_studio(page: Page) -> bool:
    for _ in range(10):
        body = low(page.inner_text("body") or "")
        if "section focus" in body or ("loop " in body and "backing track" in body):
            return True
        settle(page, 1.0)
    return False


def chart_tool_is_active(page: Page) -> bool:
    body = page.inner_text("body") or ""
    return "Generated Practice Melody" in body and "Notation / TAB" in body


def open_chart_and_melody_tool(page: Page) -> bool:
    # The app persists last-used tool/song/level across sessions ("Saved
    # Sessions"), so the chart tool chip may already be active -- clicking
    # it again would *toggle it off* (same chip semantics as the rest of
    # the launcher). Only click when it isn't already open, and always
    # verify the workspace actually rendered rather than trusting the click.
    for attempt in range(3):
        if chart_tool_is_active(page):
            return True
        click_key_button(page, "practice_tool_pick_chart")
        settle(page, 2.5 + attempt)
    return chart_tool_is_active(page)


def open_generated_melody_panel(page: Page) -> bool:
    body = low(page.inner_text("body") or "")
    if "hide generated practice melody" in body:
        return True
    # "Generated Practice Melody" is itself a collapsed st.expander (same
    # nested-collapse pattern as the existing "Chord chart" panel) -- its
    # "Load Generated Practice Melody" button is invisible/unclickable
    # until the outer expander header is opened first.
    if "Load Generated Practice Melody" not in (page.inner_text("body") or ""):
        click_visible_text(page, "Generated Practice Melody")
        settle(page, 1)
    if not click_key_button(page, "practice_melody_show_btn"):
        return False
    return wait_for_alt_label(page, min_index=1) != ""


def generated_melody_alt_label(page: Page) -> str:
    body = page.inner_text("body") or ""
    m = re.search(r"alternative #(\d+)", body)
    return m.group(0) if m else ""


def wait_for_alt_label(page: Page, *, min_index: int, timeout_s: float = 12.0) -> str:
    """Poll for the melody caption's "alternative #N" (N >= min_index).

    A button click here causes two Streamlit reruns back to back (the
    implicit one from the widget state change, then an explicit
    ``st.rerun()`` in the click handler), and a fixed settle can land in the
    brief idle gap between them. Polling with a floor on N avoids treating
    that stale mid-rerun DOM as the final state.
    """
    deadline = timeout_s
    waited = 0.0
    step = 1.0
    while waited <= deadline:
        settle(page, step)
        waited += step
        label = generated_melody_alt_label(page)
        m = re.match(r"alternative #(\d+)", label)
        if m and int(m.group(1)) >= min_index:
            return label
    return generated_melody_alt_label(page)


def melody_caption_line(page: Page) -> str:
    body = page.inner_text("body") or ""
    m = re.search(r"Song \*?\*?.*?alternative #\d+.*", body)
    if m:
        return m.group(0)
    m2 = re.search(r"alternative #\d+.*", body)
    return m2.group(0) if m2 else ""


def set_level(page: Page, name: str) -> bool:
    """Set the sidebar Level selectbox and verify the committed value."""
    expand_sidebar(page)
    want = str(name or "").strip()

    def _committed() -> bool:
        try:
            return str(
                page.evaluate(
                    """() => {
                      const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
                      for (const b of boxes) {
                        const t = (b.innerText || '').trim();
                        if (!/^Level\\b/i.test(t)) continue;
                        const input = b.querySelector('input');
                        return input ? String(input.value || '').trim() : '';
                      }
                      return '';
                    }"""
                )
                or ""
            ).lower() == want.lower()
        except Exception:
            return False

    if _committed():
        return True

    side = page.locator('section[data-testid="stSidebar"]')
    for _attempt in range(4):
        expand_sidebar(page)
        try:
            page.evaluate(
                """() => {
                  const side = document.querySelector('section[data-testid="stSidebar"]');
                  if (!side) return false;
                  const boxes = [...side.querySelectorAll('[data-testid="stSelectbox"]')];
                  const target = boxes.find((b) => /^Level\\b/i.test((b.innerText || '').trim()));
                  if (!target) return false;
                  try { target.scrollIntoView({ block: 'center', inline: 'nearest' }); } catch (e) {}
                  return true;
                }"""
            )
            page.wait_for_timeout(250)
            box = side.locator('[data-testid="stSelectbox"]').filter(
                has_text=re.compile(r"^Level\b", re.I)
            )
            if not box.count():
                continue
            target = box.first
            target.scroll_into_view_if_needed(timeout=3000)
            page.wait_for_timeout(150)
            try:
                target.click(timeout=4000, force=True)
            except Exception:
                target.locator("input").first.click(timeout=4000, force=True)
            page.wait_for_timeout(450)
            opt_re = re.compile(rf"^{re.escape(want)}$", re.I)
            clicked = False
            try:
                page.get_by_role("option", name=opt_re).click(timeout=5000, force=True)
                clicked = True
            except Exception:
                clicked = bool(
                    page.evaluate(
                        """(want) => {
                          const opts = [...document.querySelectorAll('[role="option"]')];
                          const wantL = String(want || '').trim().toLowerCase();
                          const el = opts.find((o) => (o.innerText || '').trim().toLowerCase() === wantL);
                          if (!el) return false;
                          el.click();
                          return true;
                        }""",
                        want,
                    )
                )
            if not clicked:
                page.keyboard.type(want, delay=25)
                page.wait_for_timeout(250)
                page.keyboard.press("Enter")
            page.wait_for_timeout(1400)
            try:
                page.wait_for_function(
                    """() => !document.querySelector('[data-testid="stStatusWidget"]')""",
                    timeout=18000,
                )
            except Exception:
                pass
            if _committed():
                return True
        except Exception as exc:
            log(f"set_level attempt failed: {exc}")
        page.wait_for_timeout(250)
    return _committed()


def full_flow(page: Page) -> None:
    notes: list[str] = []

    # --- 1. Catalog song -> Generated Practice Melody -------------------
    picked = pick_song(page, notes, "Perfect", "Pop")
    log(" ".join(notes[-4:]))
    mark("pick_song_perfect", picked)
    goto_studio(page, "Practice")
    settle(page, 3)
    mark("practice_studio_loaded", wait_practice_studio(page))

    # The app persists the last-used level across sessions -- force a known
    # starting level so the later "change level to Advanced" step is a real
    # transition regardless of what a prior run left behind.
    set_level(page, "Beginner")
    settle(page, 2)

    mark("open_chart_melody_tool", open_chart_and_melody_tool(page))
    shot(page, "01-chart-melody-tool")
    body = low(page.inner_text("body") or "")
    mark("tool_label_renamed", "chart & melody" in body, "expected renamed tool label visible")

    mark("open_generated_melody_panel", open_generated_melody_panel(page))
    settle(page, 2)
    shot(page, "02-generated-melody-alt1")
    alt1_label = generated_melody_alt_label(page)
    mark("melody_alt1_shown", alt1_label == "alternative #1", alt1_label)
    caption1 = melody_caption_line(page)
    mark("melody_caption_has_song", "perfect" in low(caption1), caption1)
    mark(
        "melody_caption_not_original",
        "original recorded melody" in low(caption1) or "composed for this song" in low(page.inner_text("body") or ""),
        caption1,
    )

    # --- 2. Generate Another Melody --------------------------------------
    mark("generate_another_click_1", click_key_button(page, "practice_melody_generate_another"))
    alt2_label = wait_for_alt_label(page, min_index=2)
    shot(page, "03-generated-melody-alt2")
    mark("melody_alt2_shown", alt2_label == "alternative #2", alt2_label)

    # --- 3. Generate again -------------------------------------------------
    mark("generate_another_click_2", click_key_button(page, "practice_melody_generate_another"))
    alt3_label = wait_for_alt_label(page, min_index=3)
    shot(page, "04-generated-melody-alt3")
    mark("melody_alt3_shown", alt3_label == "alternative #3", alt3_label)
    alt3_body = page.inner_text("body") or ""

    # --- 4. Change level -----------------------------------------------
    mark("set_level_advanced", set_level(page, "Advanced"))
    settle(page, 3)
    wait_practice_studio(page)
    open_chart_and_melody_tool(page)
    open_generated_melody_panel(page)
    settle(page, 2)
    shot(page, "05-after-level-advanced")
    caption_after_level = melody_caption_line(page)
    mark("level_reflected_advanced", "advanced" in low(caption_after_level), caption_after_level)
    alt_after_level = generated_melody_alt_label(page)
    mark("level_change_reset_to_alt1", alt_after_level == "alternative #1", alt_after_level)

    # --- 5. Change song --------------------------------------------------
    picked_b = pick_song(page, notes, "Wonderwall", "Rock")
    log(" ".join(notes[-4:]))
    mark("pick_song_wonderwall", picked_b)
    goto_studio(page, "Practice")
    settle(page, 3)
    wait_practice_studio(page)
    open_chart_and_melody_tool(page)
    open_generated_melody_panel(page)
    settle(page, 2)
    shot(page, "06-song-b-wonderwall")
    caption_song_b = melody_caption_line(page)
    mark("song_change_shows_new_song", "wonderwall" in low(caption_song_b), caption_song_b)
    mark("song_change_reset_to_alt1", "alternative #1" in caption_song_b or generated_melody_alt_label(page) == "alternative #1")
    mark("song_change_no_leftover_old_song", "perfect" not in low(caption_song_b), caption_song_b)

    # --- 6. Return to first song ------------------------------------------
    picked_back = pick_song(page, notes, "Perfect", "Pop")
    log(" ".join(notes[-4:]))
    mark("pick_song_perfect_again", picked_back)
    goto_studio(page, "Practice")
    settle(page, 3)
    wait_practice_studio(page)
    open_chart_and_melody_tool(page)
    open_generated_melody_panel(page)
    settle(page, 2)
    shot(page, "07-back-to-perfect")
    caption_back = melody_caption_line(page)
    mark("return_to_song_a_shows_song_a", "perfect" in low(caption_back), caption_back)
    mark("return_to_song_a_no_wonderwall_leak", "wonderwall" not in low(caption_back), caption_back)
    mark(
        "return_to_song_a_fresh_baseline",
        "alternative #1" in caption_back or generated_melody_alt_label(page) == "alternative #1",
        caption_back,
    )

    # --- 7. Unrelated control interaction must not disturb the melody ---
    before_body = page.inner_text("body") or ""
    before_alt = generated_melody_alt_label(page)
    # Load Chord Chart (an unrelated expander in the same tool) and reload it.
    click_key_button(page, "practice_chart_show_btn")
    settle(page, 2)
    shot(page, "08-after-chord-chart-open")
    after_body = page.inner_text("body") or ""
    after_alt = generated_melody_alt_label(page)
    mark(
        "melody_stable_across_unrelated_control",
        after_alt == before_alt and after_alt != "",
        f"before={before_alt} after={after_alt}",
    )

    # --- 8. Existing Chord Chart / Notation-TAB still work --------------
    body_now = low(page.inner_text("body") or "")
    mark("chord_chart_still_renders", "chord chart" in body_now)
    # The Notation/TAB expander starts collapsed until a notation has been
    # generated this session -- open it before the button inside is clickable.
    body_check = page.inner_text("body") or ""
    if "Generate notation / TAB" not in body_check:
        click_visible_text(page, "Notation / TAB")
        settle(page, 1.5)
    gen_notation_clicked = click_key_button(page, "practice_generate_notation")
    settle(page, 3)
    shot(page, "09-notation-tab")
    body_notation = low(page.inner_text("body") or "")
    mark(
        "notation_tab_still_works",
        gen_notation_clicked and ("standard notation" in body_notation or "note guide" in body_notation or "tab" in body_notation),
        f"clicked={gen_notation_clicked}",
    )

    # --- Placeholders: My Uploaded Melody / Original Melody -------------
    click_visible_text(page, "Original Melody")
    settle(page, 1)
    body_final = page.inner_text("body") or ""
    mark("uploaded_melody_placeholder_present", "My Uploaded Melody" in body_final)
    mark("original_melody_placeholder_present", "Original Melody" in body_final)
    mark(
        "no_false_original_melody_claim",
        "does not currently" in low(body_final) or "coming soon" in low(body_final),
    )


def mobile_flow(page: Page) -> None:
    """Trimmed check for the phone-width viewport: does the new Chart &
    Melody / Generated Practice Melody UI render and work at narrow width,
    without depending on the sidebar Level selectbox's mobile drawer
    behavior (a pre-existing, feature-independent responsive-sidebar
    concern, not something this slice changed)."""
    notes: list[str] = []
    picked = pick_song(page, notes, "Perfect", "Pop")
    log(" ".join(notes[-4:]))
    mark("mobile_pick_song", picked)
    goto_studio(page, "Practice")
    settle(page, 3)
    mark("mobile_practice_studio_loaded", wait_practice_studio(page))
    shot(page, "01-practice-mobile")

    mark("mobile_open_chart_melody_tool", open_chart_and_melody_tool(page))
    shot(page, "02-chart-melody-mobile")
    body = low(page.inner_text("body") or "")
    mark("mobile_tool_label_renamed", "chart & melody" in body)

    mark("mobile_open_generated_melody_panel", open_generated_melody_panel(page))
    shot(page, "03-generated-melody-mobile")
    alt1_label = generated_melody_alt_label(page)
    mark("mobile_melody_alt1_shown", alt1_label == "alternative #1", alt1_label)

    mark("mobile_generate_another_click", click_key_button(page, "practice_melody_generate_another"))
    alt2_label = wait_for_alt_label(page, min_index=2)
    shot(page, "04-generated-melody-alt2-mobile")
    mark("mobile_melody_alt2_shown", alt2_label == "alternative #2", alt2_label)

    body_now = page.inner_text("body") or ""
    mark("mobile_uploaded_melody_placeholder_present", "My Uploaded Melody" in body_now)
    mark("mobile_original_melody_placeholder_present", "Original Melody" in body_now)

    click_key_button(page, "practice_chart_show_btn")
    settle(page, 2)
    shot(page, "05-chord-chart-mobile")
    mark("mobile_chord_chart_still_renders", "chord chart" in low(page.inner_text("body") or ""))
    after_alt = generated_melody_alt_label(page)
    mark(
        "mobile_melody_stable_after_chord_chart",
        after_alt == alt2_label,
        f"before={alt2_label} after={after_alt}",
    )


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
                if VIEWPORT_MODE == "mobile":
                    mobile_flow(page)
                else:
                    full_flow(page)
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
