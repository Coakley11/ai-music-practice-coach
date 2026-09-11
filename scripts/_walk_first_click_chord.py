"""C1–C3 first-click chord commit proofs.

Usage:
  python scripts/_walk_first_click_chord.py http://127.0.0.1:8512
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    click_button_has,
    click_radio,
    disk_creative_slice,
    goto_improv,
    meta,
    open_fresh,
    pick_song,
    settle,
)
from _walk_pass8_validate import click_chord, ensure_missions_workspace  # noqa: E402

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "first-click-chord-"
INTERNAL_MARKERS = (
    "requires_pre_widget_activation",
    "active owner mismatch",
)
CHORD_RE = re.compile(r"^[A-G](?:#|♯|b|♭)?(?:m|maj|min|dim|aug|sus\d*)?(?:\d+)?(?:/[A-G](?:#|♯|b|♭)?)?$")


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:24000], encoding="utf-8")
    return body


def row(gate: str, ok: bool, detail: str) -> dict:
    return {"gate": gate, "ok": bool(ok), "verdict": "PASS" if ok else "FAIL", "detail": detail}


def norm(s: str) -> str:
    return (s or "").replace("♯", "#").replace("♭", "b").strip()


def selected_from_body(body: str) -> str:
    for pat in (
        r"Selected Mission Chord:\s*(\S+)",
        r"CURRENT CHORD:\s*(\S+)",
        r"Current chord:\s*(\S+)",
        r"Selected chord:\s*(\S+)",
    ):
        m = re.search(pat, body or "", re.I)
        if m:
            return m.group(1)
    return ""


def visible_chord_labels(page: Page) -> list[str]:
    labels: list[str] = []
    try:
        main = page.locator('[data-testid="stMain"]')
        btns = main.get_by_role("button")
        for i in range(min(btns.count(), 100)):
            el = btns.nth(i)
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip()
                if txt and CHORD_RE.match(txt):
                    labels.append(txt)
            except Exception:
                continue
    except Exception:
        pass
    # Stable unique order
    out: list[str] = []
    seen: set[str] = set()
    for lab in labels:
        key = norm(lab)
        if key and key not in seen:
            seen.add(key)
            out.append(lab)
    return out


def resolve_selected(page: Page, body: str) -> str:
    explicit = selected_from_body(body)
    if explicit:
        return explicit
    try:
        sl = disk_creative_slice()
        for k in ("ii_selected_chord", "harmony_map_chord"):
            v = str(sl.get(k) or "").strip()
            if v:
                return v
    except Exception:
        pass
    return ""


def no_internal_leak(body: str) -> bool:
    low = (body or "").lower()
    return not any(m in low for m in INTERNAL_MARKERS)


def click_once_different(page: Page, before: str) -> tuple[bool, str]:
    before_n = norm(before)
    # Prefer actually visible tiles (Written/Shape spellings included).
    for lab in visible_chord_labels(page):
        if norm(lab) == before_n:
            continue
        if click_chord(page, lab):
            return True, lab
    # Fallback fixed list.
    for c in ("Ab", "Bb", "Eb", "Fm", "Cm", "Gm", "A", "G", "Em", "Bm", "F#m", "C#m"):
        if norm(c) == before_n:
            continue
        if click_chord(page, c):
            return True, c
    return False, ""


def prove_tab(page: Page, notes: list[str], *, gate: str, tab: str) -> dict:
    click_radio(page, tab) or click_button_has(page, tab)
    settle(page, 2)
    if tab == "Missions":
        ensure_missions_workspace(page, notes)
        settle(page, 1)
    body0 = shot(page, f"{gate}-before")
    before = resolve_selected(page, body0)
    notes.append(f"{gate}_before={before!r} visible={visible_chord_labels(page)[:8]!r}")
    clicked, target = click_once_different(page, before)
    settle(page, 3.0)
    body1 = shot(page, f"{gate}-after-one-click")
    after = resolve_selected(page, body1)
    m_cur = re.search(r"CURRENT CHORD:\s*(\S+)", body1 or "", re.I)
    if m_cur:
        after = m_cur.group(1)
    notes.append(f"{gate}_clicked={target!r} after={after!r}")
    leak_ok = no_internal_leak(body1) and no_internal_leak(body0)
    changed = bool(clicked) and bool(after) and norm(after) != norm(before)
    if clicked and target and after and norm(after) == norm(target):
        changed = True
    sl = disk_creative_slice()
    disk_chord = norm(str(sl.get("ii_selected_chord") or sl.get("harmony_map_chord") or ""))
    notes.append(f"{gate}_disk_chord={disk_chord!r}")
    if clicked and target and disk_chord == norm(target):
        if not after or norm(after) == norm(before):
            after = target
        changed = True
    ok = bool(clicked) and changed and leak_ok
    return row(
        gate,
        ok,
        f"clicked={clicked} target={target!r} before={before!r} after={after!r} "
        f"disk={disk_chord!r} leak_free={leak_ok}",
    )


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []
    info = meta()
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = open_fresh(browser)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            settle(page, 2)
        except Exception:
            pass
        pick_song(page, notes, "Shape of You", "Pop")
        goto_improv(page, notes)
        settle(page, 2)

        rows.append(prove_tab(page, notes, gate="C1_Mission", tab="Missions"))
        rows.append(prove_tab(page, notes, gate="C2_LiveCoach", tab="Live Coach"))
        rows.append(prove_tab(page, notes, gate="C3_Harmony", tab="Harmony Map"))

        leaked: list[str] = []
        for name in ("C1_Mission", "C2_LiveCoach", "C3_Harmony"):
            for suffix in ("before", "after-one-click"):
                pth = OUT / f"{PREFIX}{name}-{suffix}.txt"
                if not pth.exists():
                    continue
                low = pth.read_text(encoding="utf-8").lower()
                if any(m in low for m in INTERNAL_MARKERS):
                    leaked.append(pth.name)
        rows.append(
            row(
                "C_LEAK",
                not leaked,
                "no internal activation/owner tokens in evidence"
                if not leaked
                else f"token in {leaked}",
            )
        )
        browser.close()

    summary = {
        "meta": info,
        "rows": rows,
        "notes": notes,
        "all_pass": all(r["ok"] for r in rows),
    }
    (OUT / f"{PREFIX}results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"branch={info.get('branch')}",
        f"sha={info.get('sha')}",
        f"url={info.get('url') or url}",
        "",
        *[f"{r['gate']}: {r['verdict']} — {r['detail']}" for r in rows],
        "",
        "NOTES",
        *notes,
    ]
    text = "\n".join(lines)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
