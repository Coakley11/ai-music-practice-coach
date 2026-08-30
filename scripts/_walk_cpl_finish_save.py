"""Browser proof: Custom Finish / Save to Library / Launch workflow (embargo ON).

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8572
  python scripts/_walk_cpl_finish_save.py http://127.0.0.1:8572
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import click_button_has, click_nav, wait_idle  # noqa: E402
from _walk_custom_page_owner_basics import click_main_button  # noqa: E402
from _walk_custom_practice_key import goto_custom  # noqa: E402
from _walk_ownership_audit_full import add_chord_bar, fill_title  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8572"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "cpl-finish-save-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def _git() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]

    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(root), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "url": URL,
    }


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body[:18000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    return body


def has_workflow_steps(body: str) -> bool:
    compact = re.sub(r"\s+", " ", body or "")
    return all(
        needle in compact
        for needle in (
            "1 Style",
            "2 Key",
            "3 Chords",
            "4 Finish",
            "5 Save to Library",
            "6 Backing Track",
        )
    )


def launch_chunk(body: str) -> str:
    text = body or ""
    idx = text.find("Launch in the studio")
    if idx < 0:
        return ""
    return text[idx : idx + 1800]


def launch_has(body: str, needle: str) -> bool:
    return bool(re.search(needle, launch_chunk(body), re.I))


def buttons_below_heading(page: Page, heading: str) -> list[str]:
    loc = page.get_by_text(heading, exact=False)
    if loc.count() == 0:
        return []
    box = None
    for i in range(loc.count()):
        try:
            el = loc.nth(i)
            if el.is_visible():
                box = el.bounding_box()
                if box:
                    break
        except Exception:
            continue
    if not box:
        return []
    y0 = box["y"]
    labels: list[str] = []
    btns = page.locator('[data-testid="stAppViewContainer"] button')
    for i in range(btns.count()):
        el = btns.nth(i)
        try:
            if not el.is_visible():
                continue
            bb = el.bounding_box()
            if not bb or bb["y"] < y0 - 2:
                continue
            labels.append(re.sub(r"\s+", " ", (el.inner_text() or "").strip()))
        except Exception:
            continue
    return labels


def launch_labels(page: Page) -> list[str]:
    """Buttons in the Launch-in-the-studio cluster only (not footer nav)."""
    loc = page.get_by_text("Launch in the studio", exact=False)
    if loc.count() == 0:
        return []
    box = None
    for i in range(loc.count()):
        try:
            el = loc.nth(i)
            if el.is_visible():
                box = el.bounding_box()
                if box:
                    break
        except Exception:
            continue
    if not box:
        return []
    y0 = box["y"]
    labels: list[str] = []
    btns = page.locator('[data-testid="stAppViewContainer"] button')
    for i in range(btns.count()):
        el = btns.nth(i)
        try:
            if not el.is_visible():
                continue
            bb = el.bounding_box()
            if not bb:
                continue
            if bb["y"] < y0 - 2 or bb["y"] > y0 + 180:
                continue
            text = re.sub(r"\s+", " ", (el.inner_text() or "").strip())
            if not text:
                continue
            if re.search(r"Upload Analysis|Practice Log|Multitrack|Creative Lab", text):
                continue
            labels.append(text)
        except Exception:
            continue
    return labels


def label_has(labels: list[str], pattern: str) -> bool:
    pat = re.compile(pattern, re.I)
    return any(pat.search(t or "") for t in labels)


def label_has_practice(labels: list[str]) -> bool:
    return any(re.search(r"🎯\s*Practice", t or "") for t in labels)


def label_has_backing(labels: list[str]) -> bool:
    return any(re.search(r"🎧\s*Backing", t or "") for t in labels)


def count_main_buttons(page: Page, pattern: str) -> int:
    loc = page.locator(
        '[data-testid="stAppViewContainer"] button, section.main button, .main button'
    ).filter(has_text=re.compile(pattern, re.I))
    n = 0
    for i in range(loc.count()):
        try:
            if loc.nth(i).is_visible():
                n += 1
        except Exception:
            continue
    return n


def click_launch_button(page: Page, pattern: str) -> bool:
    labels = launch_labels(page)
    if not label_has(labels, pattern):
        return click_main_button(page, pattern)
    heading = page.get_by_text("Launch in the studio", exact=False)
    box = None
    for i in range(heading.count()):
        try:
            el = heading.nth(i)
            if el.is_visible():
                box = el.bounding_box()
                if box:
                    break
        except Exception:
            continue
    if not box:
        return click_main_button(page, pattern)
    y0 = box["y"]
    loc = page.locator('[data-testid="stAppViewContainer"] button').filter(
        has_text=re.compile(pattern, re.I)
    )
    for i in range(loc.count() - 1, -1, -1):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            bb = el.bounding_box()
            if not bb or bb["y"] < y0 - 2:
                continue
            el.scroll_into_view_if_needed()
            el.click(timeout=5000)
            wait_idle(page, 4000)
            return True
        except Exception:
            continue
    return click_main_button(page, pattern)


def main() -> int:
    meta = _git()
    print(json.dumps(meta), flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 980})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        wait_idle(page, 5000)

        ok_custom = goto_custom(page)
        click_button_has(page, r"New song") or click_button_has(page, r"New Song")
        wait_idle(page, 2500)
        fill_title(page, "Finish Save Walk")
        add_chord_bar(page, "C")
        add_chord_bar(page, "G")
        wait_idle(page, 2000)
        body_a = shot(page, "A-workflow")
        GATES["A_workflow_1_6"] = has_workflow_steps(body_a)
        log(f"A custom={ok_custom} steps={GATES['A_workflow_1_6']}")

        launch_b = launch_labels(page)
        save_count_b = count_main_buttons(page, r"Save to library")
        GATES["B_save_visible"] = save_count_b >= 1 and (
            "save to library" in (body_a or "").lower()
        )
        GATES["B_launch_save"] = launch_has(body_a, r"Save to library") or label_has(
            launch_b, r"Save to library"
        )
        GATES["B_launch_practice_hidden"] = not label_has_practice(launch_b)
        GATES["B_launch_backing_hidden"] = not label_has_backing(launch_b)
        log(
            f"B save_count={save_count_b} launch={launch_b!r} "
            f"save={GATES['B_save_visible']} launch_save={GATES['B_launch_save']} "
            f"prac_hidden={GATES['B_launch_practice_hidden']} "
            f"back_hidden={GATES['B_launch_backing_hidden']}"
        )

        click_main_button(page, r"^Finish Song$") or click_button_has(page, r"Finish Song")
        wait_idle(page, 3000)
        body_c = shot(page, "C-finish")
        launch_c = launch_labels(page)
        GATES["C_finish_ui"] = all(
            needle in (body_c or "")
            for needle in ("Keep Editing", "Set as Active Song")
        )
        GATES["C_save_still_visible"] = count_main_buttons(page, r"Save to library") >= 1
        GATES["C_new_still_visible"] = count_main_buttons(page, r"New song") >= 1
        GATES["C_launch_save"] = label_has(launch_c, r"Save to library") or launch_has(
            body_c, r"Save to library"
        )
        GATES["C_launch_practice_hidden"] = not label_has_practice(launch_c)
        GATES["C_launch_backing_hidden"] = not label_has_backing(launch_c)
        log(
            f"C finish_ui={GATES['C_finish_ui']} save={GATES['C_save_still_visible']} "
            f"new={GATES['C_new_still_visible']} launch={launch_c!r}"
        )

        click_launch_button(page, r"Save to library") or click_main_button(
            page, r"Save to library"
        )
        wait_idle(page, 3000)
        body_d = shot(page, "D-saved")
        launch_d = launch_labels(page)
        GATES["D_save_confirmation"] = "saved to custom library" in (body_d or "").lower()
        GATES["D_save_still_available"] = count_main_buttons(page, r"Save to library") >= 1
        GATES["D_launch_practice"] = label_has_practice(launch_d)
        GATES["D_launch_backing"] = label_has_backing(launch_d)
        log(
            f"D confirm={GATES['D_save_confirmation']} launch={launch_d!r} "
            f"prac={GATES['D_launch_practice']} back={GATES['D_launch_backing']}"
        )

        click_launch_button(page, r"Practice") or click_main_button(page, r"Practice")
        wait_idle(page, 4000)
        body_e = shot(page, "E-practice")
        on_practice = "practice" in (page.url or "").lower() or bool(
            re.search(r"\bPractice\b", body_e or "")
        )
        goto_custom(page)
        wait_idle(page, 3000)
        body_e2 = shot(page, "E-return-custom")
        GATES["E_practice_nav"] = bool(on_practice)
        GATES["E_return_custom"] = "Finish Save Walk" in (body_e2 or "") or has_workflow_steps(
            body_e2
        )
        log(f"E practice={on_practice} return={GATES['E_return_custom']}")

        click_launch_button(page, r"Backing") or click_main_button(page, r"Backing")
        wait_idle(page, 4000)
        body_f = shot(page, "F-backing")
        on_backing = bool(
            re.search(r"Backing", body_f or "", re.I)
        ) and "custom" in (body_f or "").lower()
        GATES["F_backing_nav"] = bool(on_backing) or "backing" in (page.url or "").lower()
        goto_custom(page)
        wait_idle(page, 3000)
        log(f"F backing={GATES['F_backing_nav']}")

        page.reload(wait_until="domcontentloaded", timeout=180000)
        wait_idle(page, 6000)
        goto_custom(page)
        wait_idle(page, 3000)
        body_g = shot(page, "G-refresh")
        launch_g = launch_labels(page)
        GATES["G_refresh_saved"] = label_has_practice(launch_g) and label_has_backing(
            launch_g
        )
        GATES["G_refresh_finish_or_builder"] = (
            "Keep Editing" in (body_g or "") or "Finish Song" in (body_g or "")
        )
        log(
            f"G launch={launch_g!r} saved_btns={GATES['G_refresh_saved']} "
            f"finish={GATES['G_refresh_finish_or_builder']}"
        )

        click_main_button(page, r"New song") or click_button_has(page, r"New song")
        wait_idle(page, 3000)
        body_h = shot(page, "H-new-song")
        launch_h = launch_labels(page)
        GATES["H_new_practice_hidden"] = not label_has_practice(launch_h)
        GATES["H_new_backing_hidden"] = not label_has_backing(launch_h)
        GATES["H_new_save_visible"] = label_has(launch_h, r"Save to library") or (
            count_main_buttons(page, r"Save to library") >= 1
        )
        stale_title = "Finish Save Walk" in (body_h or "") and "New blank song" not in (
            body_h or ""
        )
        GATES["H_new_not_stale_title"] = "New blank song started" in (body_h or "") or (
            "Finish Save Walk" not in (body_h or "")
        )
        log(
            f"H launch={launch_h!r} prac_hidden={GATES['H_new_practice_hidden']} "
            f"back_hidden={GATES['H_new_backing_hidden']} stale={stale_title}"
        )

        browser.close()

    failed = [k for k, v in GATES.items() if not v]
    print(json.dumps(GATES, indent=2), flush=True)
    print("FAILED:" if failed else "ALL_PASS", failed or [], flush=True)
    (OUT / f"{PREFIX}summary.txt").write_text(
        json.dumps({"meta": meta, "gates": GATES, "failed": failed, "notes": NOTES}, indent=2),
        encoding="utf-8",
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
