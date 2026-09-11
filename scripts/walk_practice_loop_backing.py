"""Browser proof: Practice Loop [section] opens regular Catalog/Custom/Composition Backing.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_practice_loop streamlit run streamlit_music_practice_app.py --server.port 8594
  python scripts/walk_practice_loop_backing.py http://127.0.0.1:8594
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
    expand_pages_nav,
    expand_sidebar,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8594"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "practice-loop-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, seconds: float = 2.0) -> None:
    wait_idle(page, int(seconds * 1000))


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body[:28000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    return body


def goto_studio(page: Page, name: str) -> bool:
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
        settle(page, 3.5)
        return True
    return click_nav(page, name)


def wait_practice_studio(page: Page) -> bool:
    for _ in range(10):
        body = low(page.inner_text("body") or "")
        if "section focus" in body or "loop " in body and "backing track" in body:
            return True
        settle(page, 1.0)
    return False


def click_section(page: Page, section: str) -> bool:
    if click_radio(page, section):
        settle(page, 1.5)
        return True
    loc = page.locator("label").filter(has_text=re.compile(rf"^{re.escape(section)}$", re.I))
    if loc.count():
        try:
            loc.first.click(timeout=4000)
            settle(page, 1.5)
            return True
        except Exception:
            pass
    loc = page.locator("button").filter(has_text=re.compile(rf"^{re.escape(section)}$", re.I))
    for i in range(min(loc.count(), 8)):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            el.scroll_into_view_if_needed()
            el.click(timeout=4000)
            settle(page, 1.5)
            return True
        except Exception:
            continue
    return False


def loop_section(page: Page, section: str = "Verse 1") -> bool:
    candidates = [section]
    if section == "Verse 1":
        candidates.append("Verse")
    clicked_section = False
    used = section
    for cand in candidates:
        if click_section(page, cand):
            clicked_section = True
            used = cand
            break
    log(f"section_click={clicked_section} {used}")
    settle(page, 2.0)
    key_loc = page.locator('[class*="st-key-practice_loop_section_to_backing"] button')
    if key_loc.count():
        try:
            key_loc.first.scroll_into_view_if_needed()
            key_loc.first.click(timeout=5000)
            settle(page, 4.5)
            return True
        except Exception:
            pass
    pattern = rf"Loop {re.escape(used)} in Backing"
    if click_button_has(page, pattern):
        settle(page, 3.5)
        return True
    return click_button_has(page, r"Loop .+ in Backing Track")


def on_backing(body: str) -> bool:
    b = low(body)
    return "backing track studio" in b or "playback scope" in b or "tempo (bpm)" in b or "quick bpm" in b


def owner_kind(body: str) -> str:
    b = low(body)
    if "backing source: mission" in b:
        return "mission"
    if "backing source: composition" in b:
        return "composition"
    if "backing source: custom" in b:
        return "custom"
    if "backing source: catalog" in b:
        return "catalog"
    if "return to mission" in b:
        return "mission"
    if "style jam" in b and "backing track studio" in b and "backing source: catalog" not in b:
        return "jam"
    return "unknown"


def has_section(body: str, section: str) -> bool:
    b = low(body)
    return low(section) in b and ("selected sections" in b or "playback scope" in b)


def refresh(page: Page) -> str:
    page.reload(wait_until="domcontentloaded")
    settle(page, 8)
    for _ in range(10):
        body = low(page.inner_text("body") or "")
        if "backing source:" in body or "section focus" in body:
            break
        settle(page, 1.0)
    return shot(page, "after-refresh")


def seed_stale_mission(page: Page) -> None:
    goto_studio(page, "Creative")
    settle(page, 2.5)
    click_button_has(page, r"^Missions$") or click_button_has(page, r"Missions")
    settle(page, 2)
    shot(page, "stale-mission-tab")


def seed_stale_jam(page: Page) -> None:
    goto_studio(page, "Creative")
    settle(page, 2.5)
    click_button_has(page, r"Entry") or click_button_has(page, r"Jam")
    settle(page, 1.5)
    click_button_has(page, r"Style Jam") or click_radio(page, "Style Jam Mode")
    settle(page, 2)
    shot(page, "stale-jam-tab")


def catalog_path(page: Page) -> None:
    notes: list[str] = []
    ok = pick_song(page, notes, "Shape of You", "Pop")
    log(" ".join(notes))
    mark("catalog_pick", ok, "Shape of You")
    goto_studio(page, "Practice")
    wait_practice_studio(page)
    settle(page, 3)
    shot(page, "catalog-practice")
    looped = loop_section(page, "Verse 1")
    mark("catalog_loop_click", looped)
    for _ in range(8):
        if "backing source:" in low(page.inner_text("body") or ""):
            break
        settle(page, 1.0)
    body = shot(page, "catalog-backing")
    mark("catalog_on_backing", on_backing(body), owner_kind(body))
    kind = owner_kind(body)
    mark("catalog_owner", kind == "catalog", kind)
    mark("catalog_not_mission", kind != "mission")
    mark("catalog_not_jam", kind != "jam")
    mark("catalog_not_custom", kind != "custom")
    mark("catalog_section", has_section(body, "Verse") or "verse" in low(body), "Verse")
    body = refresh(page)
    mark("catalog_refresh_owner", owner_kind(body) == "catalog", owner_kind(body))
    mark("catalog_refresh_section", has_section(body, "Verse") or "verse" in low(body))


def custom_path(page: Page) -> None:
    notes: list[str] = []
    try:
        from _walk_ownership_audit_full import build_trial_song

        built = build_trial_song(page, notes)
        log(" ".join(notes[-8:]))
        mark("custom_trial_song", built)
    except Exception as exc:
        log(f"trial_song_err={exc}")
        mark("custom_trial_song", False, str(exc))
    goto_studio(page, "Songs")
    settle(page, 2.5)
    clicked = click_radio(page, "Custom") or click_button_has(page, r"Custom Progression")
    mark("custom_radio", clicked)
    settle(page, 3)
    goto_studio(page, "Practice")
    wait_practice_studio(page)
    settle(page, 3)
    shot(page, "custom-practice")
    looped = loop_section(page, "Verse 1") or loop_section(page, "Verse")
    mark("custom_loop_click", looped)
    for _ in range(8):
        if "backing source:" in low(page.inner_text("body") or ""):
            break
        settle(page, 1.0)
    body = shot(page, "custom-backing")
    kind = owner_kind(body)
    mark("custom_on_backing", on_backing(body), kind)
    mark("custom_owner", kind == "custom", kind)
    mark("custom_not_catalog", kind != "catalog")
    mark("custom_not_mission", kind != "mission")
    body = refresh(page)
    mark("custom_refresh_owner", owner_kind(body) == "custom", owner_kind(body))


def composition_path(page: Page) -> None:
    goto_studio(page, "Compose")
    settle(page, 3)
    goto_studio(page, "Songs")
    settle(page, 2.5)
    clicked = click_radio(page, "Composition") or click_button_has(page, r"Composition")
    mark("composition_radio", clicked)
    settle(page, 4)
    goto_studio(page, "Practice")
    wait_practice_studio(page)
    settle(page, 3)
    shot(page, "composition-practice")
    looped = loop_section(page, "Verse 1") or loop_section(page, "Verse")
    mark("composition_loop_click", looped)
    body = shot(page, "composition-backing")
    kind = owner_kind(body)
    mark("composition_on_backing", on_backing(body), kind)
    mark("composition_owner", kind == "composition", kind)
    mark("composition_not_catalog", kind != "catalog")
    mark("composition_not_custom", kind != "custom")
    body = refresh(page)
    mark("composition_refresh_owner", owner_kind(body) == "composition", owner_kind(body))


def stale_isolation(page: Page) -> None:
    seed_stale_mission(page)
    goto_studio(page, "Practice")
    wait_practice_studio(page)
    settle(page, 3)
    loop_section(page, "Verse 1")
    body = shot(page, "stale-mission-after-loop")
    kind = owner_kind(body)
    mark("stale_mission_isolation", kind not in {"mission", "jam"}, kind)
    seed_stale_jam(page)
    goto_studio(page, "Practice")
    wait_practice_studio(page)
    settle(page, 3)
    loop_section(page, "Verse 1")
    body = shot(page, "stale-jam-after-loop")
    kind = owner_kind(body)
    mark("stale_jam_isolation", kind not in {"mission", "jam"}, kind)


def main() -> int:
    only = (sys.argv[2] if len(sys.argv) > 2 else "").strip().lower()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        settle(page, 5)
        shot(page, "home")
        if only in {"", "catalog"}:
            catalog_path(page)
        if only in {"", "stale"}:
            stale_isolation(page)
        if only in {"", "custom"}:
            custom_path(page)
        if only in {"", "composition"}:
            composition_path(page)
        browser.close()
    summary = {"gates": GATES, "notes": NOTES, "url": URL}
    (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    failed = [k for k, v in GATES.items() if not v]
    log(f"failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
