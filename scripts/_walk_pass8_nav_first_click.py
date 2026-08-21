"""Pass 8 live acceptance: first-click page navigation must be authoritative.

Usage: python scripts/_walk_pass8_nav_first_click.py http://127.0.0.1:8512

Contract: each explicit sidebar page click must open that page on the FIRST click.
Never one-rerun/one-click behind.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_radio,
    expand_sidebar,
    goto_improv,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
PREFIX = "pass8-nav-first-click-"

# Sidebar button labels (exact title; ignore emoji prefix).
NAV_LABEL = {
    "Songs": "Song Selection",
    "Creative": "Creative Lab",
    "Backing": "Backing Track",
    "Upload": "Upload Analysis",
    "Practice": "Practice",
}

# Marker id → walk name
MARKER_TO_NAME = {
    "picker": "Songs",
    "creative": "Creative",
    "backing": "Backing",
    "analysis": "Upload",
    "practice": "Practice",
    "custom": "Custom",
    "composer": "Compose",
    "multitrack": "Multitrack",
    "log": "Log",
}


def wait(page: Page, ms: int = 1200) -> None:
    page.wait_for_timeout(ms)
    try:
        page.locator('[data-testid="stSpinner"]').first.wait_for(state="hidden", timeout=8000)
    except Exception:
        pass


def shot(page: Page, name: str) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body, encoding="utf-8")
    page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    return body


def detect_page(page: Page) -> str:
    info = page.evaluate(
        """() => {
          const markers = [...document.querySelectorAll('#studio-ui-release-marker,[data-studio-page]')];
          const last = markers.length ? markers[markers.length - 1] : null;
          return {
            markerFirst: (() => {
              const m = document.getElementById('studio-ui-release-marker');
              return m ? (m.getAttribute('data-studio-page') || '') : '';
            })(),
            markerLast: last ? (last.getAttribute('data-studio-page') || '') : '',
            body: document.body.dataset.studioPage || '',
            markerCount: markers.filter((el) => el.id === 'studio-ui-release-marker').length,
          };
        }"""
    )
    # Prefer body dataset (latest script), then last marker — first marker can be stale.
    raw = str(
        (info or {}).get("body")
        or (info or {}).get("markerLast")
        or (info or {}).get("markerFirst")
        or ""
    ).strip().lower()
    return MARKER_TO_NAME.get(raw, raw or "unknown")


def wait_for_page(page: Page, expected: str, *, timeout_ms: int = 8000) -> str:
    deadline = timeout_ms
    stepped = 0
    while stepped < deadline:
        cur = detect_page(page)
        if cur == expected:
            return cur
        page.wait_for_timeout(250)
        stepped += 250
    return detect_page(page)


def expand_pages(page: Page) -> None:
    expand_sidebar(page)
    if page.locator('section[data-testid="stSidebar"] button').filter(
        has_text=re.compile(r"Creative Lab", re.I)
    ).count():
        return
    rail = page.locator('section[data-testid="stSidebar"] button').filter(
        has_text=re.compile(r"^\s*☰?\s*Pages\s*$|Pages", re.I)
    )
    for i in range(rail.count()):
        el = rail.nth(i)
        try:
            if el.is_visible():
                el.click()
                wait(page, 2200)
                break
        except Exception:
            continue


def click_sidebar_once(page: Page, name: str) -> bool:
    """Single explicit sidebar nav click (exact label; Practice != Practice Log)."""
    expand_pages(page)
    label = NAV_LABEL[name]
    loc = page.locator('section[data-testid="stSidebar"] button')
    for i in range(loc.count() - 1, -1, -1):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            text = re.sub(r"\s+", " ", (el.inner_text() or "")).strip()
            # Strip leading emoji / symbols
            core = re.sub(r"^[^\w]+", "", text).strip()
            if name == "Practice":
                if core != "Practice":
                    continue
            elif not core.endswith(label) and core != label:
                continue
            el.evaluate("node => node.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(150)
            el.click()
            wait(page, 3200)
            return True
        except Exception:
            continue
    return False


def step(page: Page, target: str, notes: list[str], tag: str) -> dict:
    before = detect_page(page)
    marker_meta = page.evaluate(
        """() => ({
          body: document.body.dataset.studioPage || '',
          first: (document.getElementById('studio-ui-release-marker')||{}).getAttribute?.('data-studio-page') || '',
          count: document.querySelectorAll('#studio-ui-release-marker').length,
        })"""
    )
    clicked = click_sidebar_once(page, target)
    after = wait_for_page(page, target, timeout_ms=9000)
    body = shot(page, tag)
    ok = bool(clicked) and after == target
    notes.append(
        f"{tag}: before={before} click={target} after={after} clicked={clicked} "
        f"PASS={ok} meta_before={marker_meta}"
    )
    if not ok:
        snip = re.sub(r"\s+", " ", body)[:220]
        notes.append(f"{tag} FAIL_SNIP={snip!r}")
    return {
        "before": before,
        "clicked": target,
        "after": after,
        "clicked_ok": clicked,
        "pass": ok,
    }


def ensure_catalog_song(page: Page, notes: list[str]) -> bool:
    """Leave Custom Trial Song and land a catalog title for Mission Backing.

    Product path: hub ``Use catalog song instead`` and/or Music-source Catalog radio,
    then an explicit catalog song pick (Love Story / Clocks).
    """
    expand_pages(page)
    click_sidebar_once(page, "Songs")
    wait(page, 2200)
    body0 = page.inner_text("body") or ""
    still_custom = "CUSTOM PROGRESSION" in (
        body0[body0.find("ACTIVE SONG") : body0.find("ACTIVE SONG") + 280]
        if "ACTIVE SONG" in body0
        else body0
    )
    if still_custom and "Use catalog song instead" not in body0:
        page.reload(wait_until="domcontentloaded")
        wait(page, 4500)
        expand_pages(page)
        click_sidebar_once(page, "Songs")
        wait(page, 2500)
        notes.append("ensure_catalog songs_reload_for_hub=True")
        body0 = page.inner_text("body") or ""
        still_custom = "CUSTOM PROGRESSION" in (
            body0[body0.find("ACTIVE SONG") : body0.find("ACTIVE SONG") + 280]
            if "ACTIVE SONG" in body0
            else body0
        )
    flipped = False
    if still_custom and click_button_has(page, r"Use catalog song instead"):
        flipped = True
        wait(page, 3000)
        notes.append("clicked Use catalog song instead")
    if still_custom or "CUSTOM PROGRESSION" in (page.inner_text("body") or ""):
        try:
            group = page.get_by_role("radiogroup", name="Music source")
            if group.count():
                txt = group.get_by_text("Song Selection (catalog song)", exact=True)
                if txt.count():
                    txt.first.click(timeout=4000, force=True)
                    flipped = True
                    wait(page, 3500)
                    notes.append("ensure_catalog radiogroup_catalog=True")
        except Exception as exc:
            notes.append(f"ensure_catalog radiogroup_err={exc}")
        try:
            click_radio(page, "Song Selection (catalog song)") or click_radio(page, "catalog song")
        except Exception:
            pass
    if flipped:
        page.reload(wait_until="domcontentloaded")
        wait(page, 4000)
        expand_pages(page)
        click_sidebar_once(page, "Songs")
        wait(page, 2000)
    ok = pick_song(page, notes, "Love Story", "Country") or pick_song(
        page, notes, "Love Story", "Pop"
    ) or pick_song(page, notes, "Clocks", "Pop")
    side = page.inner_text("body") or ""
    side_block = (
        side[side.find("ACTIVE SONG") : side.find("ACTIVE SONG") + 280]
        if "ACTIVE SONG" in side
        else ""
    )
    custom = "CUSTOM PROGRESSION" in side_block
    notes.append(f"ensure_catalog ok={ok} still_custom={custom} flipped={flipped}")
    return bool(ok) and not custom


def open_mission_backing(page: Page, notes: list[str]) -> bool:
    if not ensure_catalog_song(page, notes):
        notes.append("mission_open blocked: still on custom / no catalog song")
        # Continue anyway — Missions may still open on custom, but require mission chrome.
    if not goto_improv(page, notes):
        return False
    wait(page, 1800)
    click_radio(page, "Missions") or click_button_has(page, r"Missions")
    wait(page, 1800)
    click_button_has(page, r"Generate") or click_button_has(page, r"example")
    wait(page, 2500)
    opened = (
        click_button_has(page, r"Open in Backing")
        or click_button_has(page, r"Practice in.*Jam")
        or click_button_has(page, r"Open Mission Backing")
        or click_button_has(page, r"Open.*Backing")
    )
    wait(page, 3500)
    body = page.inner_text("body") or ""
    missionish = bool(
        re.search(
            r"Return to Mission|MISSION BACKING|Creative Backing Jam\s*·\s*Mission",
            body,
            flags=re.I,
        )
    )
    notes.append(f"mission_open clicked={opened} page={detect_page(page)} missionish={missionish}")
    return bool(opened) and detect_page(page) == "Backing" and missionish


def click_return_to_mission(page: Page) -> bool:
    return (
        click_button_has(page, r"←\s*Return to Mission")
        or click_button_has(page, r"Return to Mission")
        or click_button_has(page, r"Return to Missions")
    )


def git_info() -> dict[str, str]:
    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(
                cmd, text=True, cwd=str(Path(__file__).resolve().parents[1])
            ).strip()
        except Exception:
            return ""

    return {
        "branch": _run(["git", "branch", "--show-current"]),
        "sha": _run(["git", "rev-parse", "--short", "HEAD"]),
        "url": URL,
    }


def main() -> int:
    notes: list[str] = []
    results: dict[str, object] = {}
    info = git_info()
    sequence = [
        "Songs",
        "Creative",
        "Backing",
        "Upload",
        "Practice",
        "Songs",
        "Backing",
        "Creative",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        wait(page, 4500)
        expand_pages(page)
        # Prefer a known catalog song when possible; nav contract does not require it.
        try:
            pick_song(page, notes, "Love Story", "Country")
        except Exception:
            pass
        wait(page, 1200)
        shot(page, "00-start")
        notes.append(f"start_page={detect_page(page)}")

        seq_rows: list[dict] = []
        for i, target in enumerate(sequence, start=1):
            seq_rows.append(step(page, target, notes, f"S{i:02d}-{target.lower()}"))
        results["sequence"] = seq_rows
        results["sequence_pass"] = all(r["pass"] for r in seq_rows)

        click_sidebar_once(page, "Songs")
        wait(page, 2000)
        page.reload(wait_until="domcontentloaded")
        wait(page, 4500)
        expand_pages(page)
        notes.append(f"reload_landed={detect_page(page)}")
        r1 = step(page, "Creative", notes, "R01-creative")
        r2 = step(page, "Backing", notes, "R02-backing")
        results["after_refresh"] = [r1, r2]
        results["after_refresh_pass"] = r1["pass"] and r2["pass"]

        mission_ok = open_mission_backing(page, notes)
        notes.append(f"mission_backing_opened={mission_ok}")
        results["mission_opened"] = mission_ok
        mission_rows: list[dict] = []
        if mission_ok:
            before = detect_page(page)
            returned = click_return_to_mission(page)
            wait(page, 3500)
            after = wait_for_page(page, "Creative", timeout_ms=10000)
            mission_rows.append(
                {
                    "before": before,
                    "clicked": "Return to Mission",
                    "after": after,
                    "clicked_ok": returned,
                    "pass": bool(returned) and after == "Creative",
                }
            )
            notes.append(
                f"M-return: before={before} after={after} returned={returned} "
                f"PASS={mission_rows[-1]['pass']}"
            )
            for i, target in enumerate(["Upload", "Backing", "Songs"], start=1):
                mission_rows.append(step(page, target, notes, f"M{i:02d}-{target.lower()}"))
        results["mission_path"] = mission_rows
        results["mission_path_pass"] = bool(mission_ok) and all(r["pass"] for r in mission_rows)

        browser.close()

    failed = not (
        results.get("sequence_pass")
        and results.get("after_refresh_pass")
        and results.get("mission_path_pass")
    )
    text = "\n".join(
        [
            f"branch={info['branch']}",
            f"sha={info['sha']}",
            f"url={info['url']}",
            f"sequence_pass={results.get('sequence_pass')}",
            f"after_refresh_pass={results.get('after_refresh_pass')}",
            f"mission_path_pass={results.get('mission_path_pass')}",
            "",
            "SEQUENCE",
            *[
                f"  {r['before']} -> click {r['clicked']} => {r['after']} PASS={r['pass']}"
                for r in seq_rows
            ],
            "",
            "NOTES",
            *notes,
        ]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    (OUT / f"{PREFIX}summary.json").write_text(
        json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
        encoding="utf-8",
    )
    print(text.encode("ascii", "replace").decode("ascii"), flush=True)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
