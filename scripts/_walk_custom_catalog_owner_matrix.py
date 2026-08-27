"""Focused real-browser ownership matrix: Catalog ↔ Custom activations.

Path:
  Shape Bm → Dm
  → Trial GA Custom D / Em Em D D
  → explicit Shape (fresh Bm)
  → first-click Dm
  → Perfect (fresh G)
  → Trial (fresh D)

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8541
  python3 scripts/_walk_custom_catalog_owner_matrix.py http://127.0.0.1:8541
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_button_has, click_nav, expand_sidebar, wait_idle
from walk_guitar_shape_key import pick_song
from _walk_core_key_coherence import card_practice_label, set_songs_practice_key
from _walk_core_workflows_embargo import practice_badge  # includes Custom "Practice / Concert Key D major"
from _walk_custom_practice_key import goto_custom, pk_val
from _walk_ownership_audit_full import build_trial_song, rendered_em_em_d_d

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8541"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "owner-mx-"
RESULTS: dict[str, str] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def mark(gate: str, status: str, detail: str = "") -> None:
    RESULTS[gate] = status
    log(f"[{status}] {gate}" + (f" — {detail}" if detail else ""))


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    try:
        expand_sidebar(page)
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    (OUT / f"{stem}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:8000]}\n\n=== BODY ===\n{body[:16000]}",
        encoding="utf-8",
    )
    return f"{side}\n{body}"


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(body: str, *needles: str) -> bool:
    b = low(body)
    return any(n.lower() in b for n in needles)


def activate_trial(page: Page) -> bool:
    clicked = click_button_has(page, r"Set as Active Song") or click_button_has(
        page, r"Set as Active"
    )
    settle(page, 3)
    return bool(clicked)


def owner_snapshot(page: Page) -> dict[str, str]:
    body = page.inner_text("body") or ""
    try:
        expand_sidebar(page)
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    blob = f"{side}\n{body}"
    badge = practice_badge(blob) or card_practice_label(blob)
    source = "custom" if has_any(blob, "CUSTOM PROGRESSION", "custom progression") and has_any(
        blob, "Trial Song"
    ) and not has_any(side, "Shape of You", "Perfect") else "catalog"
    if has_any(side, "Trial Song") and has_any(side, "CUSTOM"):
        source = "custom"
    if has_any(side, "Shape of You") and not has_any(side, "Trial Song"):
        source = "catalog"
    if has_any(side, "Perfect") and not has_any(side, "Trial Song"):
        source = "catalog"
    identity = ""
    if has_any(blob, "Trial Song"):
        identity = "Trial Song"
    if has_any(side, "Shape of You") or has_any(body, "NOW LOADED FOR PRACTICE\nShape of You"):
        identity = "Shape of You"
    if has_any(side, "Perfect") or has_any(body, "NOW LOADED FOR PRACTICE\nPerfect"):
        identity = "Perfect"
    return {
        "source": source,
        "identity": identity,
        "practice": badge,
        "sidebar": side[:400],
    }


def main() -> int:
    meta = {
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=str(ROOT), text=True).strip(),
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip(),
        "url": URL,
    }
    log(json.dumps(meta))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        body = shot(page, "01-shape-fresh")
        snap = owner_snapshot(page)
        shape_bm = has_any(body, "Shape of You") and "b minor" in low(snap["practice"] or practice_badge(body))
        mark("A_shape_bm", "PASS" if shape_bm else "RED", json.dumps(snap))

        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        body = shot(page, "02-shape-dm")
        snap = owner_snapshot(page)
        shape_dm = has_any(body, "Shape of You") and "d minor" in low(snap["practice"] or practice_badge(body))
        mark("B_shape_dm", "PASS" if shape_dm else "RED", json.dumps(snap))

        trial_ok = build_trial_song(page, NOTES)
        settle(page, 2)
        act = activate_trial(page)
        settle(page, 3)
        body = shot(page, "03-trial-ga")
        snap = owner_snapshot(page)
        trial_ga = (
            trial_ok
            and has_any(body, "Trial Song")
            and (
                "d major" in low(snap["practice"] or practice_badge(body) or pk_val(page) or body)
            )
            and (rendered_em_em_d_d(body) or bool(re.search(r"Em.{0,20}Em.{0,20}D.{0,20}D", body, re.I | re.S)))
        )
        mark(
            "D_trial_ga_custom",
            "PASS" if trial_ga else "RED",
            f"build={trial_ok} act={act} {json.dumps(snap)}",
        )

        click_nav(page, "Songs")
        settle(page, 2)
        landed = pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        body = shot(page, "04-shape-reactivate")
        snap = owner_snapshot(page)
        shape_fresh = (
            landed
            and has_any(body, "Shape of You")
            and not has_any(page.inner_text('[data-testid="stSidebar"]') or "", "Trial Song")
            and "b minor" in low(snap["practice"] or practice_badge(body))
            and "d minor" not in low(snap["practice"] or practice_badge(body))
        )
        mark(
            "E_shape_fresh_bm",
            "PASS" if shape_fresh else "RED",
            f"landed={landed} {json.dumps(snap)}",
        )

        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        body = shot(page, "05-shape-dm-first-click")
        snap = owner_snapshot(page)
        dm_first = has_any(body, "Shape of You") and "d minor" in low(snap["practice"] or practice_badge(body))
        mark("E2_shape_dm_first_click", "PASS" if dm_first else "RED", json.dumps(snap))

        landed_p = pick_song(page, NOTES, "Perfect", "Pop")
        settle(page, 3)
        body = shot(page, "06-perfect")
        snap = owner_snapshot(page)
        perfect_ok = (
            landed_p
            and has_any(body, "Perfect")
            and "g major" in low(snap["practice"] or practice_badge(body))
            and "minor" not in low(snap["practice"] or "")
        )
        mark("F_perfect_fresh_g", "PASS" if perfect_ok else "RED", json.dumps(snap))

        goto_custom(page)
        settle(page, 2)
        act2 = activate_trial(page)
        settle(page, 3)
        body = shot(page, "07-trial-again")
        snap = owner_snapshot(page)
        trial_again = (
            act2
            and has_any(body, "Trial Song")
            and "d major" in low(snap["practice"] or practice_badge(body) or pk_val(page) or body)
        )
        mark("G_trial_fresh_d", "PASS" if trial_again else "RED", f"act={act2} {json.dumps(snap)}")

        from _walk_core_workflows_embargo import open_sbi_active
        from _walk_pass8_validate import ensure_missions_workspace
        from walk_creative_backing_matrix import click_open_backing_studio, goto_improv

        sbi_ok = bool(goto_improv(page, NOTES) and open_sbi_active(page))
        settle(page, 3)
        body = shot(page, "08-sbi")
        snap = owner_snapshot(page)
        sbi_vis = (
            sbi_ok
            and has_any(body, "Trial Song")
            and not has_any(body, "Say — John Mayer")
            and (rendered_em_em_d_d(body) or "d major" in low(snap["practice"] or body))
        )
        mark("H_sbi", "PASS" if sbi_vis else "RED", json.dumps(snap))

        click_nav(page, "Creative")
        settle(page, 2)
        goto_improv(page, NOTES)
        ensure_missions_workspace(page, NOTES)
        settle(page, 2)
        body = shot(page, "09-missions")
        snap = owner_snapshot(page)
        from _walk_ownership_audit_full import missions_derived_from_custom_trial

        m_vis = (
            has_any(body, "Trial Song")
            and missions_derived_from_custom_trial(body, projected="D")
            and not has_any(body, "Say — John Mayer")
        )
        mark("I_missions", "PASS" if m_vis else "RED", json.dumps(snap))

        clicked_back = click_open_backing_studio(page, NOTES, "visual-sanity-backing")
        settle(page, 4)
        body = shot(page, "10-backing")
        snap = owner_snapshot(page)
        back_vis = (
            bool(clicked_back)
            and has_any(body, "Trial Song")
            and not has_any(body, "Say — John Mayer")
            and not (
                has_any(body, "Shape of You")
                and has_any(page.inner_text('[data-testid="stSidebar"]') or "", "Trial Song")
            )
        )
        mark("J_backing", "PASS" if back_vis else "RED", json.dumps(snap))

        browser.close()

    reds = [k for k, v in RESULTS.items() if v == "RED"]
    passes = [k for k, v in RESULTS.items() if v == "PASS"]
    overall = "PASS" if not reds else "RED"
    summary = {
        "meta": meta,
        "overall": overall,
        "results": RESULTS,
        "pass": passes,
        "red": reds,
        "notes": NOTES[-60:],
    }
    (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / f"{PREFIX}summary.txt").write_text(
        "\n".join(
            [
                f"OVERALL={overall}",
                f"PASS={len(passes)} RED={len(reds)}",
                json.dumps(RESULTS, indent=2),
                "",
                *NOTES[-40:],
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(RESULTS, indent=2), flush=True)
    print(f"OVERALL={overall}", flush=True)
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
