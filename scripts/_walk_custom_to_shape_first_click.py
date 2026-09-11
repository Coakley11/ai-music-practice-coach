"""Custom Global Active → Shape once (embargo ON).

Path A: Trial active → Songs → Shape dropdown (no Use catalog).
Path B: Trial active → Songs → Catalog selector → Shape once.
Neither path may canonicalize Say.

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8621
  python scripts/_walk_custom_to_shape_first_click.py http://127.0.0.1:8621
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

from walk_creative_backing_matrix import click_button_has, click_nav, wait_idle  # noqa: E402
from walk_guitar_shape_key import (  # noqa: E402
    ensure_songs_catalog_source,
    pick_active_song_from_dropdown,
    pick_song,
)
from _walk_core_workflows_embargo import practice_badge  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_ownership_audit_full import build_trial_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8621"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "owner-switch-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "url": URL,
    }


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(body: str, *needles: str) -> bool:
    b = low(body)
    return any(n.lower() in b for n in needles)


def sidebar_song(page: Page) -> str:
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    lines = [ln.strip() for ln in side.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if ln == "SONG" and i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt not in {"SONG", "Songs", "🎼 Songs"} and ("—" in nxt or "Trial" in nxt or nxt == "CUSTOM PROGRESSION"):
                if nxt == "CUSTOM PROGRESSION" and i + 2 < len(lines):
                    return f"{nxt} / {lines[i + 2]}"
                return nxt
    return ""


def original_key(body: str) -> str:
    m = re.search(r"Song Original Key:\s*([A-G](?:#|b)?m?)", body or "", re.I)
    if m:
        return m.group(1)
    m2 = re.search(r"Original Key:\s*([A-G](?:#|b)?(?:\s*major|\s*minor|m)?)", body or "", re.I)
    return (m2.group(1) if m2 else "").strip()


def picker_title(body: str) -> str:
    m = re.search(r"NOW LOADED FOR PRACTICE\s*\n\s*(.+)", body or "")
    if m:
        return m.group(1).strip().split("\n")[0].strip()
    return ""


def is_say(text: str) -> bool:
    t = low(text)
    return "say — john mayer" in t or "say - john mayer" in t or "say john mayer" in t


def record_tuple(page: Page, name: str) -> dict[str, str]:
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body[:18000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    rec = {
        "picker": picker_title(body),
        "ga": sidebar_song(page),
        "original": original_key(body),
        "practice": practice_badge(body) or pk_val(page) or "",
        "sidebar": sidebar_song(page),
        "source": (
            "custom"
            if has_any(body, "CUSTOM PROGRESSION", "Trial Song")
            and not has_any(body, "Shape of You")
            else "catalog"
            if has_any(body, "Shape of You", "Perfect", "Say")
            else ""
        ),
    }
    log(f"{name} tuple={rec}")
    return rec


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate} {detail}")


def identity_blob(rec: dict[str, str]) -> str:
    return low(" ".join([rec.get("picker") or "", rec.get("ga") or "", rec.get("sidebar") or ""]))


def shape_ok(rec: dict[str, str], body: str) -> bool:
    identity = identity_blob(rec)
    hub = low(body or "")
    loaded = "now loaded for practice" in hub and "shape of you" in hub
    keys = low((rec.get("practice") or "") + " " + (rec.get("original") or "") + " " + hub)
    has_shape = "shape of you" in identity or loaded
    return (
        has_shape
        and not is_say(identity)
        and "say — john mayer" not in low(rec.get("ga") or "")
        and ("b minor" in keys or "bm" in low(rec.get("practice") or "") or "bm" in low(rec.get("original") or ""))
        and "trial song" not in identity
    )


def perfect_ok(rec: dict[str, str], body: str) -> bool:
    identity = identity_blob(rec)
    keys = low((rec.get("practice") or "") + " " + (rec.get("original") or "") + " " + (body or ""))
    return (
        "perfect" in identity
        and not is_say(identity)
        and "shape of you" not in identity
        and ("g major" in keys or low(rec.get("practice") or "").startswith("g"))
    )


def trial_ok(rec: dict[str, str], body: str) -> bool:
    blob = low(" ".join(rec.values()) + " " + (body or ""))
    return (
        "trial song" in blob
        and not is_say(identity_blob(rec))
        and ("d major" in blob or low(rec.get("practice") or "").startswith("d"))
    )


def say_is_canonical(page: Page) -> bool:
    body = page.inner_text("body") or ""
    rec = {
        "picker": picker_title(body),
        "ga": sidebar_song(page),
        "sidebar": sidebar_song(page),
    }
    return is_say(identity_blob(rec)) or (
        picker_title(body).strip().lower() == "say" and "trial song" not in low(body[:4000])
    )


def activate_trial(page: Page) -> bool:
    ok = build_trial_song(page, NOTES)
    click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
    settle(page, 3)
    rec = record_tuple(page, "trial-active")
    body = page.inner_text("body") or ""
    return bool(ok) and trial_ok(rec, body)


def pick_shape_direct(page: Page) -> bool:
    click_nav(page, "Songs")
    settle(page, 3)
    return bool(pick_active_song_from_dropdown(page, "Shape of You"))


def main() -> int:
    log(json.dumps(git_meta()))
    say_seen = False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        trial_a = activate_trial(page)
        rec_pre = record_tuple(page, "A-songs-before-shape")
        click_nav(page, "Songs")
        settle(page, 3)
        rec_songs = record_tuple(page, "A-songs-custom-hub")
        body_songs = page.inner_text("body") or ""
        songs_shows_trial = trial_ok(rec_songs, body_songs) or has_any(body_songs, "Trial Song")
        mark("A_songs_shows_trial", trial_a and songs_shows_trial, f"trial_build={trial_a}")
        if say_is_canonical(page):
            say_seen = True

        # Path B first: no remembered last catalog. Use catalog must not
        # canonicalize Say; then Shape once.
        used = ensure_songs_catalog_source(page, NOTES)
        settle(page, 3)
        rec_sel = record_tuple(page, "B-after-catalog-selector")
        body_sel = page.inner_text("body") or ""
        selector_not_say = not is_say(identity_blob(rec_sel))
        still_trial_or_pending = (
            "trial song" in low(body_sel)
            or "custom" in low(rec_sel.get("ga") or "")
        ) and not is_say(identity_blob(rec_sel))
        remembered_shape_ok = shape_ok(rec_sel, body_sel)
        mark(
            "B_catalog_selector_not_say",
            trial_a
            and used
            and selector_not_say
            and (still_trial_or_pending or remembered_shape_ok),
            f"used={used} selector_not_say={selector_not_say} remembered_shape={remembered_shape_ok}",
        )
        if say_is_canonical(page):
            say_seen = True
        landed_b = pick_active_song_from_dropdown(page, "Shape of You")
        settle(page, 3)
        rec = record_tuple(page, "B-selector-to-shape")
        body = page.inner_text("body") or ""
        mark(
            "B_selector_then_shape",
            landed_b and shape_ok(rec, body),
            f"landed={landed_b}",
        )
        settle(page, 3)
        rec_hold = record_tuple(page, "B-hold")
        mark("B_selector_then_shape_holds", shape_ok(rec_hold, page.inner_text("body") or ""))

        trial_a2 = activate_trial(page)
        click_nav(page, "Songs")
        settle(page, 3)
        landed = pick_shape_direct(page)
        settle(page, 3)
        rec = record_tuple(page, "A-trial-to-shape")
        body = page.inner_text("body") or ""
        mark(
            "A_trial_to_shape_direct",
            trial_a2 and landed and shape_ok(rec, body) and not is_say(identity_blob(rec)),
            f"landed={landed}",
        )
        if say_is_canonical(page):
            say_seen = True
        settle(page, 3)
        rec_hold = record_tuple(page, "A-hold")
        body_hold = page.inner_text("body") or ""
        mark("A_trial_to_shape_holds", shape_ok(rec_hold, body_hold))

        trial_c = activate_trial(page)
        rec = record_tuple(page, "C-shape-to-trial")
        mark("C_shape_to_trial", trial_c and trial_ok(rec, page.inner_text("body") or ""))

        landed_p = pick_song(page, NOTES, "Perfect", "Pop")
        settle(page, 3)
        rec = record_tuple(page, "D-perfect")
        mark("D_trial_to_perfect_or_shape_to_perfect", landed_p and perfect_ok(rec, page.inner_text("body") or ""))

        landed_s = pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        rec = record_tuple(page, "E-perfect-to-shape")
        mark("E_perfect_to_shape", landed_s and shape_ok(rec, page.inner_text("body") or ""))

        landed_p2 = pick_song(page, NOTES, "Perfect", "Pop")
        settle(page, 3)
        rec = record_tuple(page, "F-shape-to-perfect")
        mark("F_shape_to_perfect", landed_p2 and perfect_ok(rec, page.inner_text("body") or ""))

        trial_d = activate_trial(page)
        rec = record_tuple(page, "G-perfect-to-trial")
        mark("G_perfect_to_trial", trial_d and trial_ok(rec, page.inner_text("body") or ""))

        mark("no_say_canonical", not say_seen and not say_is_canonical(page))

        browser.close()

    failed = [k for k, v in GATES.items() if not v]
    print(json.dumps(GATES, indent=2), flush=True)
    print("FAILED:" if failed else "ALL_PASS", failed or [], flush=True)
    (OUT / f"{PREFIX}summary.json").write_text(
        json.dumps({"gates": GATES, "failed": failed, "notes": NOTES}, indent=2),
        encoding="utf-8",
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
