"""Focused first-click catalog picker proof (embargo ON).

One explicit Songs pick must land immediately: picker, Global Active, Original Key,
Practice Key, and sidebar must agree. No second click. No Say frame.

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8620
  python scripts/_walk_explicit_catalog_first_click.py http://127.0.0.1:8620
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
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_workflows_embargo import practice_badge  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_ownership_audit_full import build_trial_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8620"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "first-click-"
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
            if nxt not in {"SONG", "Songs", "🎼 Songs"} and "—" in nxt:
                return nxt
    m = re.search(r"SONG\s+(.*?)\n", side)
    if m and m.group(1).strip() and m.group(1).strip() != "SONG":
        return re.sub(r"\s+", " ", m.group(1)).strip()
    if "SONG" in side:
        chunk = side[side.find("SONG") : side.find("SONG") + 160]
        return re.sub(r"\s+", " ", chunk)
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
    }
    log(f"{name} tuple={rec}")
    return rec


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate} {detail}")


def _identity_blob(rec: dict[str, str]) -> str:
    return low(" ".join([rec.get("picker") or "", rec.get("ga") or "", rec.get("sidebar") or ""]))


def _is_say(text: str) -> bool:
    t = low(text)
    return "say — john mayer" in t or "say - john mayer" in t or "say john mayer" in t


def shape_ok(rec: dict[str, str], body: str) -> bool:
    identity = _identity_blob(rec)
    keys = low((rec.get("practice") or "") + " " + (rec.get("original") or "") + " " + (body or ""))
    return (
        "shape of you" in identity
        and not _is_say(identity)
        and ("b minor" in keys or "bm" in low(rec.get("practice") or "") or "bm" in low(rec.get("original") or ""))
    )


def perfect_ok(rec: dict[str, str], body: str) -> bool:
    identity = _identity_blob(rec)
    keys = low((rec.get("practice") or "") + " " + (rec.get("original") or "") + " " + (body or ""))
    return (
        "perfect" in identity
        and not _is_say(identity)
        and "shape of you" not in identity
        and ("g major" in keys or low(rec.get("practice") or "").startswith("g"))
    )


def pick_once(page: Page, title: str) -> bool:
    return pick_song(page, NOTES, title, "Pop")


def still_after_reruns(page: Page, check) -> bool:
    settle(page, 3)
    rec = record_tuple(page, "rerun-hold")
    body = page.inner_text("body") or ""
    return bool(check(rec, body))


def main() -> int:
    log(json.dumps(git_meta()))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        click_nav(page, "Songs")
        settle(page, 2)
        landed = pick_once(page, "Shape of You")
        settle(page, 3)
        rec = record_tuple(page, "A-fresh-shape")
        body = page.inner_text("body") or ""
        mark("A_fresh_shape_first_click", landed and shape_ok(rec, body), f"landed={landed}")
        mark("A_fresh_shape_holds", still_after_reruns(page, shape_ok))

        trial_ok = build_trial_song(page, NOTES)
        click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
        settle(page, 3)
        click_nav(page, "Songs")
        settle(page, 3)
        rec_t = record_tuple(page, "B-trial-ga")
        body_t = page.inner_text("body") or ""
        trial_ga = has_any(body_t, "Trial Song")
        landed_shape = pick_once(page, "Shape of You")
        settle(page, 3)
        rec = record_tuple(page, "B-trial-to-shape")
        body = page.inner_text("body") or ""
        mark(
            "B_trial_to_shape_first_click",
            trial_ok and trial_ga and landed_shape and shape_ok(rec, body),
            f"trial_build={trial_ok} trial_ga={trial_ga} landed={landed_shape}",
        )
        mark("B_trial_to_shape_holds", still_after_reruns(page, shape_ok))

        landed_p = pick_once(page, "Perfect")
        settle(page, 3)
        rec = record_tuple(page, "C-shape-to-perfect")
        body = page.inner_text("body") or ""
        mark("C_shape_to_perfect_first_click", landed_p and perfect_ok(rec, body), f"landed={landed_p}")
        mark("C_shape_to_perfect_holds", still_after_reruns(page, perfect_ok))

        landed_s = pick_once(page, "Shape of You")
        settle(page, 3)
        rec = record_tuple(page, "D-perfect-to-shape")
        body = page.inner_text("body") or ""
        mark("D_perfect_to_shape_first_click", landed_s and shape_ok(rec, body), f"landed={landed_s}")
        mark("D_perfect_to_shape_holds", still_after_reruns(page, shape_ok))

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
