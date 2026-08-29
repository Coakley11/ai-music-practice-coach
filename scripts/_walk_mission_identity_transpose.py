"""Focused Mission identity proof: Bm → Cm must be +1 (C#m → Dm, F# → G).

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8532
  python scripts/_walk_mission_identity_transpose.py http://127.0.0.1:8532
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

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_radio,
    ensure_checkbox,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_core_workflows_embargo import click_generate_example  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_pass8_validate import click_chord, ensure_missions_workspace, open_mission_backing  # noqa: E402

_CHORD_TOKEN = r"([A-G](?:#|b|♯|♭)?(?:m(?!aj)|maj7|m7|sus4|7)?)"


def _norm_ch(sym: str) -> str:
    return (sym or "").replace("♯", "#").replace("♭", "b").strip()


def mission_header_chord(text: str) -> str:
    m = re.search(
        rf"Creative Backing Jam · Mission[^\n]*?·\s*{_CHORD_TOKEN}\s*·\s*Concert",
        text,
    )
    if m:
        return _norm_ch(m.group(1))
    m = re.search(rf"Verse 1 · {_CHORD_TOKEN}", text)
    return _norm_ch(m.group(1) if m else "")


def mission_card_chord(text: str) -> str:
    m = re.search(rf"Verse 1 · {_CHORD_TOKEN}", text)
    return _norm_ch(m.group(1) if m else "")


def mission_example_chord(text: str) -> str:
    m = re.search(rf"Mission example\s*[·•]\s*{_CHORD_TOKEN}", text)
    if m:
        return _norm_ch(m.group(1))
    m = re.search(rf"Chord\s+{_CHORD_TOKEN}", text)
    return _norm_ch(m.group(1) if m else "")


def enable_alto_written(page: Page) -> None:
    set_instrument(page, "Saxophone") or set_instrument(page, "Alto Saxophone")
    settle(page, 2)
    set_baseweb_select(page, "Saxophone", "Alto") or set_baseweb_select(
        page, "Type", "Alto saxophone (Eb)"
    )
    settle(page, 1)
    ensure_checkbox(page, "Show chart in written key for instrument", checked=True) or (
        click_button_has(page, r"Written Charts") or click_radio(page, "Written Charts on")
    )
    settle(page, 2)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8532"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "id-"
NOTES: list[str] = []
RESULTS: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    side = ""
    try:
        expand_sidebar(page)
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    (OUT / f"{stem}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:9000]}\n\n=== BODY ===\n{body[:18000]}",
        encoding="utf-8",
    )
    return body


def list_chord_tiles(page: Page) -> list[str]:
    try:
        labels = page.evaluate(
            """() => [...document.querySelectorAll('button')]
              .filter(b => b.offsetParent)
              .map(b => (b.innerText||'').trim())
              .filter(t => /^[A-G][#b♯♭]?(m|maj7|m7|sus4|dim|aug|7)?$/.test(t))
              .slice(0, 24)"""
        )
        return [str(x).replace("♯", "#").replace("♭", "b") for x in (labels or [])]
    except Exception as exc:
        log(f"tile_dump_err={exc}")
        return []


def owners(body: str, page: Page) -> dict[str, str]:
    notes = ""
    m = re.search(r"Notes:\s*`([^`]+)`", body)
    if m:
        notes = m.group(1).strip()
    abc = ""
    m = re.search(r"T:.*?(?:Chord|—|-)\s*([A-G][#b]?(?:m)?)", body)
    if m:
        abc = m.group(1)
    return {
        "header": mission_header_chord(body),
        "card": mission_card_chord(body),
        "example": mission_example_chord(body),
        "notes": notes,
        "abc": abc,
        "pk": pk_val(page) or "",
        "concert_cm": "yes" if ("Concert Cm" in body or "C minor" in (body or "").lower()) else "",
    }


def _norm(s: str) -> str:
    return (s or "").replace("♯", "#").replace("♭", "b")


def owners_match(got: dict[str, str], expected: str) -> bool:
    exp = _norm(expected)
    visible = [_norm(got.get("header") or ""), _norm(got.get("card") or ""), _norm(got.get("example") or "")]
    present = [v for v in visible if v]
    if not present:
        return False
    return all(v == exp for v in present) and got.get("header") == exp


def setup_shape_missions(page: Page, notes: list[str]) -> bool:
    click_nav(page, "Songs")
    settle(page, 2)
    click_button_has(page, r"Use catalog song instead")
    settle(page, 1)
    pick_song(page, notes, "Shape of You", "Pop")
    settle(page, 2)
    set_songs_practice_key(page, "Bm")
    settle(page, 2)
    if not goto_improv(page, notes):
        return False
    ensure_missions_workspace(page, notes)
    settle(page, 2)
    set_baseweb_select(page, "Practice / Concert Key", "Bm") or set_songs_practice_key(page, "Bm")
    settle(page, 2)
    return True


def select_and_open(
    page: Page, notes: list[str], chord: str, shot_name: str
) -> tuple[bool, dict[str, str]]:
    tiles = list_chord_tiles(page)
    log(f"{shot_name} tiles={tiles}")
    clicked = click_chord(page, chord) or click_chord(page, chord.replace("#", "♯"))
    log(f"{shot_name} click {chord}={clicked}")
    settle(page, 2)
    click_generate_example(page)
    settle(page, 2)
    opened = bool(open_mission_backing(page, notes))
    settle(page, 4)
    set_baseweb_select(page, "Practice / Concert Key", "Bm") or set_baseweb_select(
        page, "Practice / Concert Key", "B minor"
    )
    settle(page, 3)
    click_chord(page, chord) or click_chord(page, chord.replace("#", "♯"))
    settle(page, 2)
    body = shot(page, shot_name)
    got = owners(body, page)
    got["opened"] = str(opened)
    got["clicked"] = str(clicked)
    log(f"{shot_name} owners={got}")
    return opened, got


def change_to_cm(page: Page, shot_name: str) -> dict[str, str]:
    set_baseweb_select(page, "Practice / Concert Key", "Cm") or set_baseweb_select(
        page, "Practice / Concert Key", "C minor"
    )
    settle(page, 4)
    body = shot(page, shot_name)
    got = owners(body, page)
    log(f"{shot_name} owners={got}")
    return got


def main() -> int:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    meta = {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }
    log(json.dumps(meta))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 980})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        notes: list[str] = NOTES
        if not setup_shape_missions(page, notes):
            log("setup failed")
            RESULTS["csm"] = False
            RESULTS["fsharp"] = False
            return 1

        set_instrument(page, "Piano")
        settle(page, 1)
        tiles_piano = list_chord_tiles(page)
        log(f"piano_bm_tiles={tiles_piano}")
        used_alto = False
        if "C#m" not in tiles_piano and "C♯m" not in tiles_piano:
            enable_alto_written(page)
            used_alto = True
            set_baseweb_select(page, "Practice / Concert Key", "Bm") or set_songs_practice_key(
                page, "Bm"
            )
            settle(page, 2)
            log(f"alto_bm_tiles={list_chord_tiles(page)}")

        opened, before = select_and_open(page, notes, "C#m", "csm-bm")
        after = change_to_cm(page, "csm-cm") if opened else {}
        csm_ok = (
            opened
            and owners_match(before, "C#m")
            and owners_match(after, "Dm")
            and bool(after.get("concert_cm"))
            and _norm(after.get("header") or "") != "Bb"
        )
        RESULTS["csm"] = csm_ok
        RESULTS["csm_before"] = before
        RESULTS["csm_after"] = after
        RESULTS["used_alto"] = used_alto
        log(f"[{'PASS' if csm_ok else 'RED'}] C#m->Dm alto={used_alto}")

        click_button_has(page, r"Return to Mission") or click_button_has(page, r"Return to Creative")
        settle(page, 3)
        goto_improv(page, notes)
        ensure_missions_workspace(page, notes)
        settle(page, 2)
        if used_alto:
            enable_alto_written(page)
        else:
            set_instrument(page, "Piano")
            settle(page, 1)
        set_baseweb_select(page, "Practice / Concert Key", "Bm") or set_songs_practice_key(page, "Bm")
        settle(page, 2)
        tiles_f = list_chord_tiles(page)
        log(f"fsharp_tiles={tiles_f}")
        fsharp_present = "F#" in tiles_f or "F♯" in tiles_f
        RESULTS["fsharp_present"] = fsharp_present
        if fsharp_present:
            opened_f, before_f = select_and_open(page, notes, "F#", "fsharp-bm")
            after_f = change_to_cm(page, "fsharp-cm") if opened_f else {}
            f_ok = (
                opened_f
                and owners_match(before_f, "F#")
                and owners_match(after_f, "G")
                and _norm(after_f.get("header") or "") != "Bb"
            )
            RESULTS["fsharp"] = f_ok
            RESULTS["fsharp_before"] = before_f
            RESULTS["fsharp_after"] = after_f
            log(f"[{'PASS' if f_ok else 'RED'}] F#->G")
        else:
            RESULTS["fsharp"] = "skipped"
            log("[SKIP] F# not a valid selected chord in this section")

        set_instrument(page, "Piano")
        browser.close()

    out_path = OUT / "id-identity-proof.json"
    payload = {"meta": meta, "results": RESULTS, "notes": NOTES[-80:]}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(str(out_path))
    csm = bool(RESULTS.get("csm"))
    fsharp = RESULTS.get("fsharp")
    fsharp_ok = fsharp is True or fsharp == "skipped"
    return 0 if csm and fsharp_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
