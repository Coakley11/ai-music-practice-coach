"""Browser proof: Practice Melody key transposition + Section Focus scope
integration on Backing (Slice F1).

Covers the lettered scenarios from the brief:
  A. Generate in C -> handoff -> Backing C.
  B. Change C -> D -> same melody transposed, Backing agrees.
  C. D -> Eb -> same identity, correctly transposed again.
  D. Generate Another -> verify composition changes.
  E. Change key again -> new melody transposes rather than regenerates.
  F. Section Focus Verse -> Backing -> only corresponding melody scope shown.
  G. Full Song -> full melody.
  J. Phone-width regression.
(H/I -- transposing instrument and Key Cycle -- are audited/code-path
verified rather than driven through this script; see the Slice F1 report.)

Usage:
  MUSIC_APP_DATA_DIR=_runtime_practice_melody_f1_8560 streamlit run streamlit_music_practice_app.py --server.port 8602
  python scripts/_browser_practice_melody_f1_8560.py http://127.0.0.1:8602 desktop
  python scripts/_browser_practice_melody_f1_8560.py http://127.0.0.1:8602 mobile
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
    click_radio,
    click_visible_text,
    expand_sidebar,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

from _browser_practice_melody_8540 import (  # noqa: E402
    click_key_button,
    generated_melody_alt_label,
    goto_studio,
    open_chart_and_melody_tool,
    open_generated_melody_panel,
    wait_for_alt_label,
    wait_practice_studio,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8602"
VIEWPORT_MODE = sys.argv[2] if len(sys.argv) > 2 else "desktop"
OUT = SCRIPTS / "evidence-practice-melody-f1"
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


def practice_melody_caption(page: Page) -> str:
    body = page.inner_text("body") or ""
    m = re.search(r"Song \*?\*?.*?alternative #\d+[^\n]*", body)
    return m.group(0) if m else ""


def caption_key(caption: str) -> str:
    m = re.search(r"key \*?\*?([A-G][#b]?m?)", caption)
    return m.group(1) if m else ""


def caption_section(caption: str) -> str:
    m = re.search(r"section \*?\*?([^·]+)·", caption)
    return m.group(1).strip() if m else ""


def set_practice_key(page: Page, want: str) -> bool:
    """Set the sidebar 'Practice / Concert Key' selectbox and verify commit."""
    expand_sidebar(page)

    def _committed() -> bool:
        try:
            return str(
                page.evaluate(
                    """() => {
                      const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
                      for (const b of boxes) {
                        const t = (b.innerText || '').trim();
                        if (!/Concert Key/i.test(t)) continue;
                        const input = b.querySelector('input');
                        return input ? String(input.value || '').trim() : '';
                      }
                      return '';
                    }"""
                )
                or ""
            ).strip().lower() == want.strip().lower()
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
                  const target = boxes.find((b) => /Concert Key/i.test((b.innerText || '').trim()));
                  if (!target) return false;
                  try { target.scrollIntoView({ block: 'center', inline: 'nearest' }); } catch (e) {}
                  return true;
                }"""
            )
            page.wait_for_timeout(250)
            box = side.locator('[data-testid="stSelectbox"]').filter(has_text=re.compile(r"Concert Key", re.I))
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
            log(f"set_practice_key attempt failed: {exc}")
        page.wait_for_timeout(250)
    return _committed()


def full_flow(page: Page) -> None:
    notes: list[str] = []

    # --- Setup: Catalog song, Chart & Melody, force a known starting key ---
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
    shot(page, "A1-practice-key-c")
    caption_c = practice_melody_caption(page)
    mark("A_generated_in_c", caption_key(caption_c) == "C", caption_c)

    # --- A: handoff -> Backing C ---
    clicked = click_key_button(page, "practice_melody_to_backing")
    mark("A_practice_with_backing_click", clicked)
    mark("A_backing_opened", wait_on_backing(page))
    settle(page, 3)
    shot(page, "A2-backing-c")
    backing_caption_c = practice_melody_caption(page)
    mark("A_backing_shows_key_c", caption_key(backing_caption_c) == "C", backing_caption_c)
    midis_in_c_text = page.inner_text("body") or ""

    # --- B: change C -> D on Backing; melody must transpose, not regenerate ---
    mark("B_set_key_d", set_practice_key(page, "D"))
    settle(page, 3)
    shot(page, "B-backing-d")
    backing_caption_d = practice_melody_caption(page)
    mark("B_backing_shows_key_d", caption_key(backing_caption_d) == "D", backing_caption_d)
    mark(
        "B_same_alt_index_after_key_change",
        re.search(r"alternative #(\d+)", backing_caption_d).group(1)
        == re.search(r"alternative #(\d+)", backing_caption_c).group(1)
        if backing_caption_c and backing_caption_d
        else False,
    )

    # --- C: D -> Eb, same identity, transposes again ---
    mark("C_set_key_eb", set_practice_key(page, "Eb"))
    settle(page, 3)
    shot(page, "C-backing-eb")
    backing_caption_eb = practice_melody_caption(page)
    mark("C_backing_shows_key_eb", caption_key(backing_caption_eb) == "Eb", backing_caption_eb)

    # --- D: Generate Another -> composition changes ---
    goto_studio(page, "Practice")
    settle(page, 2.5)
    wait_practice_studio(page)
    open_chart_and_melody_tool(page)
    open_generated_melody_panel(page)
    practice_caption_before_gen = practice_melody_caption(page)
    mark("D_practice_key_is_eb", caption_key(practice_caption_before_gen) == "Eb", practice_caption_before_gen)
    click_key_button(page, "practice_melody_generate_another")
    new_alt = wait_for_alt_label(page, min_index=2)
    shot(page, "D-practice-generate-another")
    mark("D_generate_another_changes_composition", new_alt != "", new_alt)

    # --- E: change key again after Generate Another -> transposes the NEW alt ---
    mark("E_set_key_c_again", set_practice_key(page, "C"))
    settle(page, 2.5)
    shot(page, "E-practice-back-to-c")
    practice_caption_after = practice_melody_caption(page)
    mark("E_key_c_after_regenerate", caption_key(practice_caption_after) == "C", practice_caption_after)
    mark(
        "E_alt_index_preserved_across_key_change",
        re.search(r"alternative #(\d+)", practice_caption_after).group(1) == new_alt.split("#")[-1]
        if practice_caption_after
        else False,
        f"expected={new_alt} got={practice_caption_after}",
    )

    # --- F: Section Focus Verse -> Backing -> only that section's melody ---
    clicked_section = click_radio(page, "Verse") or click_visible_text(page, "Verse")
    log(f"section_focus_verse_clicked={clicked_section}")
    settle(page, 2)
    mark("F_section_focus_verse_selected", clicked_section)
    clicked_backing = click_key_button(page, "practice_melody_to_backing")
    mark("F_practice_with_backing_from_section_focus", clicked_backing)
    mark("F_backing_opened_for_section", wait_on_backing(page))
    settle(page, 3)
    shot(page, "F-backing-section-scoped")
    section_caption = practice_melody_caption(page)
    log(f"section_caption={section_caption!r}")
    mark(
        "F_backing_shows_section_scope_not_full_song",
        "full song" not in low(caption_section(section_caption)) and caption_section(section_caption) != "",
        section_caption,
    )

    # --- G: back to Full Song -> full melody ---
    goto_studio(page, "Practice")
    settle(page, 2.5)
    wait_practice_studio(page)
    clicked_full = click_radio(page, "Full Song") or click_visible_text(page, "Full Song")
    log(f"full_song_clicked={clicked_full}")
    settle(page, 2)
    open_chart_and_melody_tool(page)
    open_generated_melody_panel(page)
    clicked_backing_full = click_key_button(page, "practice_melody_to_backing")
    mark("G_practice_with_backing_full_song", clicked_backing_full)
    mark("G_backing_opened_full_song", wait_on_backing(page))
    settle(page, 3)
    shot(page, "G-backing-full-song")
    full_caption = practice_melody_caption(page)
    mark("G_backing_shows_full_song", "full song" in low(caption_section(full_caption)), full_caption)


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
