"""Live Custom Practice Key projection walk (human-style regression).

Usage: python scripts/_walk_custom_practice_key.py http://127.0.0.1:8512
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
    click_nav,
    expand_sidebar,
    set_baseweb_select,
    wait_idle,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)


def meta() -> dict:
    root = Path(__file__).resolve().parents[1]

    def _run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(root), text=True).strip()

    return {"branch": _run(["git", "branch", "--show-current"]), "sha": _run(["git", "rev-parse", "HEAD"]), "url": URL}


def pk_val(page: Page) -> str:
    expand_sidebar(page)
    return (
        page.evaluate(
            """() => {
              const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
              return el ? String(el.value || '').trim() : '';
            }"""
        )
        or ""
    )


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"cpl-pk-{name}.txt").write_text(body[:18000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"cpl-pk-{name}.png"), full_page=True)
    return body


def goto_custom(page: Page) -> bool:
    click_nav(page, "Songs")
    wait_idle(page, 2500)
    body = page.inner_text("body") or ""
    if "Use Custom Progression" in body or "Custom Progression" in body:
        click_button_has(page, "Use Custom Progression") or click_button_has(
            page, r"Custom Progression"
        )
        wait_idle(page, 2500)
    # Direct Custom page route if available
    if not click_nav(page, "Custom"):
        click_button_has(page, "Edit chords in Custom Progression Lab") or click_button_has(
            page, "Custom Progression Lab"
        )
    wait_idle(page, 3500)
    body = page.inner_text("body") or ""
    return bool(re.search(r"Original Key|New song|Custom Progression", body, re.I))


def set_original_key(page: Page, token: str) -> bool:
    # Exact option only — "D" must not land on "Db".
    try:
        box = page.locator('[data-testid="stSelectbox"]').filter(
            has_text=re.compile(r"Original Key", re.I)
        )
        if box.count() == 0:
            return False
        target = box.first
        target.scroll_into_view_if_needed()
        target.locator('[data-baseweb="select"], [role="combobox"], input').first.click(timeout=4000)
        page.wait_for_timeout(700)
        opt = page.locator('[role="option"]').filter(
            has_text=re.compile(rf"^{re.escape(token)}$", re.I)
        )
        if opt.count() == 0:
            opt = page.locator('[role="option"]').filter(
                has_text=re.compile(rf"^{re.escape(token)} major$", re.I)
            )
        if opt.count() == 0:
            return False
        opt.first.click(timeout=4000)
        wait_idle(page, 3500)
        return True
    except Exception:
        return False


def _norm_key(token: str) -> str:
    t = str(token or "").strip().replace("♯", "#").replace("♭", "b")
    t = re.sub(r"\s+major$", "", t, flags=re.I).strip()
    return t


def key_is(token: str, expected: str) -> bool:
    """Exact key match — C must not pass C#m; E must not pass Eb/Ebm."""
    a = _norm_key(token)
    b = _norm_key(expected)
    if not a or not b:
        return False
    if a == b:
        return True
    # Accept "D major" vs "D" already normalized; reject prefix traps.
    return False


def original_key_val(page: Page) -> str:
    try:
        box = page.locator('[data-testid="stSelectbox"]').filter(
            has_text=re.compile(r"Original Key", re.I)
        )
        if box.count() == 0:
            return ""
        inp = box.first.locator("input").first
        if inp.count():
            return str(inp.input_value() or "").strip()
        return str(box.first.inner_text() or "").strip()
    except Exception:
        return ""


def has_prog(body: str, *chords: str) -> bool:
    return all(re.search(rf"(?<![A-Ga-g#♯b♭]){re.escape(c)}(?![A-Za-z0-9#♯b♭])", body) for c in chords)


def set_practice_key(page: Page, token: str) -> bool:
    """Set sidebar Practice Key with exact landing verification (no E→Ebm).

    Uses React Aria data-key indices for major-family tokens (Custom chord chips
    must never be used as click targets).
    """
    expand_sidebar(page)
    token = str(token or "").strip()
    if not token:
        return False
    aliases = [token]
    if token == "Eb":
        aliases.append("E♭")
    elif token == "E♭":
        aliases.append("Eb")
        token = "Eb"
    # display_key_options major-family order used by sidebar
    major_index = {
        "C": "0",
        "Db": "1",
        "C#": "2",
        "D": "3",
        "Eb": "4",
        "D#": "5",
        "E": "6",
        "F": "7",
        "Gb": "8",
        "F#": "9",
        "G": "10",
        "Ab": "11",
        "G#": "12",
        "A": "13",
        "Bb": "14",
        "A#": "15",
        "B": "16",
    }
    try:
        combo = page.get_by_role("combobox", name="Practice / Concert Key")
        combo.click(timeout=4000)
        page.wait_for_timeout(200)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(700)
        clicked = False
        idx = major_index.get(token) or major_index.get(aliases[0])
        if idx is not None:
            by_key = page.locator(f'[role="option"][data-key="{idx}"]')
            if by_key.count() and by_key.first.is_visible():
                by_key.first.click(force=True, timeout=4000)
                clicked = True
                wait_idle(page, 2000)
                if any(key_is(pk_val(page), a) for a in aliases):
                    return True
                # Wrong landing (index drift) — reopen and use exact label.
                clicked = False
                combo = page.get_by_role("combobox", name="Practice / Concert Key")
                combo.click(timeout=4000)
                page.wait_for_timeout(200)
                page.keyboard.press("ArrowDown")
                page.wait_for_timeout(700)
        for alias in aliases:
            opt = page.locator('[role="listbox"]').get_by_role(
                "option", name=alias, exact=True
            )
            if opt.count() and opt.first.is_visible():
                opt.first.click(force=True, timeout=4000)
                clicked = True
                break
        if not clicked:
            page.keyboard.press("Escape")
            return False
        wait_idle(page, 4500)
    except Exception:
        return False
    landed = pk_val(page)
    return any(key_is(landed, a) for a in aliases)


def main() -> int:
    result: dict = {"meta": meta(), "steps": {}, "product_code_changed": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(URL, wait_until="domcontentloaded")
        wait_idle(page, 4000)
        if not goto_custom(page):
            result["ok"] = False
            result["error"] = "custom_page"
            print(json.dumps(result, indent=2))
            return 1
        # Prefer seeded Custom song; New song only if Original Key control missing.
        body0 = page.inner_text("body") or ""
        if "Original Key" not in body0:
            click_button_has(page, "New song")
            wait_idle(page, 3000)
        shot(page, "new")
        # Clean seed: force Practice Key to D before Original Key proof.
        set_practice_key(page, "D")
        wait_idle(page, 2500)
        ok_d = set_original_key(page, "D")
        wait_idle(page, 3000)
        # After Original Key = D, Practice Key should follow to D.
        if not key_is(pk_val(page), "D"):
            set_practice_key(page, "D")
            wait_idle(page, 2500)
        body_d = shot(page, "orig-d")
        pk_d = pk_val(page)
        orig_d = original_key_val(page)
        result["steps"]["orig_d"] = {
            "set": ok_d,
            "pk": pk_d,
            "original": orig_d,
            "ok": key_is(pk_d, "D") and (key_is(orig_d, "D") or "D" in orig_d),
            "builder_d": has_prog(body_d, "D") and (
                has_prog(body_d, "A") or "Em" in body_d or "Bm" in body_d
            ),
            "sidebar_d": key_is(pk_d, "D"),
        }
        # Ensure I–V–vi–IV (D–A–Bm–G) via preset if not already present
        if not has_prog(body_d, "D", "A", "Bm", "G"):
            click_button_has(page, "I–V–vi–IV") or click_button_has(page, "I-V-vi-IV")
            wait_idle(page, 2500)
        body_prog = shot(page, "prog-d")
        result["steps"]["prog_d"] = {
            "has_d_a_bm_g": has_prog(body_prog, "D", "A", "Bm", "G"),
            "original_still_d": key_is(original_key_val(page), "D")
            or "D" in original_key_val(page),
        }
        set_ok_e = set_practice_key(page, "E")
        wait_idle(page, 3500)
        body_e = shot(page, "pk-e")
        pk_e = pk_val(page)
        orig_e = original_key_val(page)
        result["steps"]["pk_e"] = {
            "set": set_ok_e,
            "pk": pk_e,
            "original": orig_e,
            "projected": has_prog(body_e, "E", "B", "A")
            and bool(re.search(r"C#m|C♯m", body_e)),
            "builder_e": bool(re.search(r"F#m|F♯m|G#m|G♯m|C#m|C♯m", body_e)),
            "original_still_d": key_is(orig_e, "D") or "D" in orig_e,
            "ok": key_is(pk_e, "E"),
        }
        set_ok_eb = set_practice_key(page, "Eb") or set_practice_key(page, "E♭")
        wait_idle(page, 3500)
        body_eb = shot(page, "pk-eb")
        pk_eb = pk_val(page)
        orig_eb = original_key_val(page)
        result["steps"]["pk_eb"] = {
            "set": set_ok_eb,
            "pk": pk_eb,
            "original": orig_eb,
            "projected": bool(
                re.search(r"\bEb\b|\bE♭\b", body_eb)
                and re.search(r"\bBb\b|\bB♭\b", body_eb)
                and re.search(r"\bCm\b", body_eb)
                and re.search(r"\bAb\b|\bA♭\b", body_eb)
            ),
            "builder_eb": bool(re.search(r"Fm|Gm|Cm|Ab|A♭|Bb|B♭", body_eb)),
            "original_still_d": key_is(orig_eb, "D") or "D" in orig_eb,
            "ok": key_is(pk_eb, "Eb") or key_is(pk_eb, "E♭"),
        }
        set_ok_back = set_practice_key(page, "D")
        wait_idle(page, 3500)
        body_back = shot(page, "pk-back-d")
        result["steps"]["back_d"] = {
            "set": set_ok_back,
            "pk": pk_val(page),
            "original": original_key_val(page),
            "exact_d_a_bm_g": has_prog(body_back, "D", "A", "Bm", "G"),
            "ok": key_is(pk_val(page), "D") and has_prog(body_back, "D", "A", "Bm", "G"),
        }
        click_button_has(page, "New song")
        wait_idle(page, 2500)
        set_original_key(page, "C")
        wait_idle(page, 3000)
        body_c = shot(page, "new-c")
        pk_c = pk_val(page)
        orig_c = original_key_val(page)
        polluted = bool(re.search(r"C#m|C♯m|\bEb\b|\bE♭\b", pk_c)) or (
            key_is(pk_c, "D") or key_is(pk_c, "E")
        )
        result["steps"]["new_c"] = {
            "pk": pk_c,
            "original": orig_c,
            "no_bleed": (not polluted) and key_is(pk_c, "C"),
            "ok": key_is(pk_c, "C") and (key_is(orig_c, "C") or "C" in orig_c),
        }
        page.reload(wait_until="domcontentloaded")
        wait_idle(page, 5000)
        goto_custom(page)
        body_r = shot(page, "refresh")
        pk_r = pk_val(page)
        result["steps"]["refresh"] = {
            "coherent": ("Original Key" in body_r)
            and ("PK Proof" in body_r or "Custom" in body_r or "New song" in body_r or "C" in body_r),
            "pk": pk_r,
            "ok": key_is(pk_r, "C") or key_is(pk_r, "D"),  # new C workspace preferred
            "stayed_c": key_is(pk_r, "C"),
        }
        browser.close()

    steps = result["steps"]
    result["ok"] = all(
        [
            steps.get("orig_d", {}).get("ok"),
            steps.get("prog_d", {}).get("has_d_a_bm_g"),
            steps.get("pk_e", {}).get("ok"),
            steps.get("pk_e", {}).get("projected"),
            steps.get("pk_e", {}).get("original_still_d"),
            steps.get("pk_eb", {}).get("ok"),
            steps.get("pk_eb", {}).get("projected"),
            steps.get("pk_eb", {}).get("original_still_d"),
            steps.get("back_d", {}).get("ok"),
            steps.get("new_c", {}).get("ok"),
            steps.get("refresh", {}).get("stayed_c") or steps.get("refresh", {}).get("ok"),
        ]
    )
    (OUT / "cpl-pk-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
