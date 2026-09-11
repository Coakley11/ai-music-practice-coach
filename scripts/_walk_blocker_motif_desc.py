"""Focused Descending Motif pitch/octave check (agent-only).

Trace: Motif → generate → Build Pattern → Descending button → Apply → sheet music.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_blocker_motif python -m streamlit run streamlit_music_practice_app.py --server.port 8674 --server.headless true
  python scripts/_walk_blocker_motif_desc.py http://127.0.0.1:8674
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from _walk_core_workflows_embargo import _to_midiish, motif_notes_from_body  # noqa: E402
from _walk_human_acceptance_ap import (  # noqa: E402
    body_text,
    extract_abc,
    log,
    parse_notes,
    seed_shape_cm,
    wait_idle,
)
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_radio,
    expand_sidebar,
    goto_improv,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8674"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []


def _shot(page, name: str) -> str:
    path = OUT / f"blocker-motif-{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception as exc:
        log(f"shot_err {name}: {exc!r}")
    text = body_text(page)
    (OUT / f"blocker-motif-{name}.txt").write_text(text[:24000], encoding="utf-8")
    return text


def _cell_starts(text: str) -> list[str]:
    blob = str(text or "")
    m = re.search(r"((?:[A-G][#b]?\s*[–—-]\s*)+[A-G][#b]?(?:\s*\|\s*(?:[A-G][#b]?\s*[–—-]\s*)+[A-G][#b]?){2,})", blob)
    if not m:
        return []
    cells = [c.strip() for c in m.group(1).split("|") if c.strip()]
    starts: list[str] = []
    for cell in cells:
        n = re.match(r"([A-G][#b]?)", cell.strip())
        if n:
            starts.append(n.group(1))
    return starts


def _abc_midi_contour(abc: str) -> list[int]:
    """Best-effort MIDI from ABC pitch tokens (octaves via , and ')."""
    body = str(abc or "")
    music = ""
    for line in body.splitlines():
        if line[:2] in {"X:", "T:", "M:", "L:", "Q:", "K:", "%%"}:
            continue
        music += " " + line
    tokens = re.findall(r"(\^+|_+|=)?([A-Ga-g])([,']*)", music)
    out: list[int] = []
    for acc, name, octs in tokens:
        pc_map = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        pc = pc_map.get(name.upper(), 0)
        if acc == "^" or acc.startswith("^"):
            pc = (pc + acc.count("^")) % 12
        elif acc == "_" or acc.startswith("_"):
            pc = (pc - acc.count("_")) % 12
        if name.islower():
            midi = 72 + pc  # C5
        else:
            midi = 60 + pc  # C4
        midi += 12 * octs.count("'")
        midi -= 12 * octs.count(",")
        out.append(midi)
    return out


def _click_descending_button(page) -> bool:
    try:
        btn = page.get_by_role("button", name=re.compile(r"^Descending$"))
        if btn.count():
            btn.last.scroll_into_view_if_needed()
            btn.last.click(timeout=5000)
            wait_idle(page, 2500)
            return True
    except Exception as exc:
        log(f"desc_btn_err={exc!r}")
    return click_button_has(page, r"^Descending$")


def main() -> int:
    result: dict = {"ok": False, "notes": NOTES}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 5000)
        expand_sidebar(page)
        landed = False
        for attempt in range(4):
            seed_shape_cm(page)
            side = page.locator('section[data-testid="stSidebar"]').inner_text()
            if "Shape of You" in side:
                landed = True
                break
            log(f"seed_shape retry={attempt}")
            wait_idle(page, 2500)
        if not landed:
            log("setup: Shape of You did not land; continuing if a motif can still be built")
        goto_improv(page, NOTES)
        wait_idle(page, 2500)
        click_radio(page, "Motif") or click_button_has(page, r"Motif")
        wait_idle(page, 2000)
        click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
        wait_idle(page, 2500)
        before = _shot(page, "before-pattern")
        before_notes = parse_notes(before) or motif_notes_from_body(before)
        click_button_has(page, r"Build Motif Pattern")
        wait_idle(page, 2500)
        after_build = _shot(page, "after-build")
        built_notes = parse_notes(after_build) or motif_notes_from_body(after_build)
        clicked = _click_descending_button(page)
        wait_idle(page, 2500)
        click_button_has(page, r"Apply Pattern Type / Direction")
        wait_idle(page, 2500)
        click_button_has(page, r"Generate Sheet Music")
        wait_idle(page, 2500)
        click_button_has(page, r"ABC source")
        wait_idle(page, 1000)
        text = _shot(page, "after-desc")
        notes = parse_notes(text) or motif_notes_from_body(text)
        cells = _cell_starts(text)
        cell_midi = _to_midiish(cells)
        name_midi = _to_midiish(notes)
        abc = extract_abc(page)
        abc_midi = _abc_midi_contour(abc)
        cell_desc = bool(cell_midi) and len(cell_midi) >= 4 and cell_midi[0] > cell_midi[-1]
        name_desc = bool(name_midi) and len(name_midi) >= 4 and name_midi[0] > name_midi[-1]
        abc_desc = bool(abc_midi) and len(abc_midi) >= 4 and abc_midi[0] > abc_midi[-1]
        leaps = [abc_midi[i] - abc_midi[i - 1] for i in range(1, len(abc_midi))] if abc_midi else []
        wrap = any(abs(leap) >= 11 and abs(leap) % 12 == 0 for leap in leaps)
        result.update(
            {
                "clicked_descending": clicked,
                "before_notes": before_notes[:12],
                "built_notes": built_notes[:12],
                "motif_notes": notes[:16],
                "cells": cells,
                "cell_midi": cell_midi,
                "name_midi": name_midi[:16],
                "abc_present": bool(abc),
                "abc_midi": abc_midi[:16],
                "cell_desc": cell_desc,
                "name_desc": name_desc,
                "abc_desc": abc_desc,
                "wrap": wrap,
                "has_descending_label": "descending" in text.lower(),
            }
        )
        result["ok"] = bool(
            clicked
            and cell_desc
            and not wrap
            and (abc or notes or cells)
        )
        browser.close()

    result["motif_notes"] = notes[:16]
    result["sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    result["log"] = NOTES[-40:]
    (OUT / "blocker-motif-summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    log(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
