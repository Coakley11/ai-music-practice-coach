"""Cold Capo acceptance A–F on :8512 — no Practice hop after refresh.

Usage: python scripts/_walk_pass8_capo_accept.py http://127.0.0.1:8512
Optional: --with-trial-residue
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_pages_nav,
    expand_sidebar,
    wait_idle,
)
from walk_guitar_shape_key import enable_guitar_capo, pick_song  # noqa: E402
from _walk_pass8_charts_capo import (  # noqa: E402
    capo_fret_token,
    checkbox_state,
    click_sidebar_once,
    fret_is_exactly_2,
    open_mission_backing,
    click_return_to_mission,
    practice_key,
    sidebar_full,
    wait,
)
from _walk_pass8_nav_first_click import ensure_catalog_song  # noqa: E402

URL = "http://127.0.0.1:8512"
WITH_TRIAL = "--with-trial-residue" in sys.argv
for a in sys.argv[1:]:
    if a.startswith("http"):
        URL = a


def _capo_ok(body: str, *, expect_pk: str = "C", expect_fret_2: bool | None = None) -> dict:
    enabled = "Capo Shape Mode" in (body or "")
    fret = capo_fret_token(body) or ""
    charts_bb = bool(re.search(r"Charts in Bb", body or "", re.I))
    pk = ""
    # Prefer practice key from caller
    fret2 = fret_is_exactly_2(body) or fret_is_exactly_2(fret)
    return {
        "charts_bb": charts_bb,
        "fret": fret or "missing",
        "fret2": fret2,
        "body_has_bb": "Bb" in (body or ""),
    }


def main() -> int:
    notes: list[str] = []
    results: dict[str, object] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        wait(page, 5000)
        expand_pages_nav(page)
        expand_sidebar(page)

        if WITH_TRIAL:
            # Activate Trial Custom then explicit Love Story Catalog.
            from _walk_pass8_validate import (  # late — heavy
                click_button_has,
            )

            click_nav(page, "Custom") or click_nav(page, "Custom Progression")
            wait(page, 2500)
            if click_button_has(page, r"Set as Active Song"):
                wait(page, 3500)
                notes.append("trial_activate_clicked=True")
            ensure_catalog_song(page, notes)
        else:
            ensure_catalog_song(page, notes)

        pick_song(page, notes, "Love Story", "Country")
        wait(page, 2000)
        click_sidebar_once(page, "Practice")
        wait(page, 2000)

        # A: Capo ON Shape Bb
        ok = enable_guitar_capo(page, notes, "Bb")
        wait(page, 2500)
        expand_sidebar(page)
        body = sidebar_full(page)
        pk = practice_key(page) or ""
        enabled = checkbox_state(page, "Capo Shape Mode") is True
        fret = capo_fret_token(body) or ""
        a_pass = (
            ok
            and enabled
            and bool(re.match(r"^C\b", pk, re.I))
            and (fret_is_exactly_2(body) or fret_is_exactly_2(fret))
            and bool(re.search(r"Charts in Bb", body or "", re.I))
        )
        results["A_immediate"] = {
            "pass": a_pass,
            "ok": ok,
            "enabled": enabled,
            "pk": pk,
            "fret": fret,
            "charts_bb": bool(re.search(r"Charts in Bb", body or "", re.I)),
        }
        notes.append(f"A {results['A_immediate']}")

        # B: ordinary rerun
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass
        wait(page, 2800)
        expand_sidebar(page)
        body = sidebar_full(page)
        pk = practice_key(page) or ""
        b_pass = (
            checkbox_state(page, "Capo Shape Mode") is True
            and bool(re.match(r"^C\b", pk, re.I))
            and (
                fret_is_exactly_2(body)
                or bool(re.search(r"Charts in Bb", body or "", re.I))
            )
        )
        results["B_rerun"] = {
            "pass": b_pass,
            "pk": pk,
            "fret": capo_fret_token(body) or "missing",
            "charts_bb": bool(re.search(r"Charts in Bb", body or "", re.I)),
        }
        notes.append(f"B {results['B_rerun']}")

        # Flush Capo to disk via a real page change, then refresh WITHOUT a Practice hop.
        click_sidebar_once(page, "Songs")
        wait(page, 2000)
        click_sidebar_once(page, "Practice")
        wait(page, 2000)

        # Browser refresh — Capo must settle WITHOUT a Practice hop (hydrate-order contract).
        page.reload(wait_until="domcontentloaded")
        wait(page, 4000)
        expand_sidebar(page)
        # Stay on the same page; wait for Guitar Capo widgets after hydrate.
        c_pass = False
        body = ""
        pk = ""
        for attempt in range(1, 16):
            expand_sidebar(page)
            body = sidebar_full(page)
            pk = practice_key(page) or ""
            enabled = checkbox_state(page, "Capo Shape Mode") is True
            c_pass = (
                enabled
                and bool(re.match(r"^C\b", pk, re.I))
                and (
                    fret_is_exactly_2(body)
                    or bool(re.search(r"Charts in Bb", body or "", re.I))
                )
                and bool(re.search(r"Guitar|GUITAR CAPO", body or "", re.I))
            )
            notes.append(
                f"C_settle attempt={attempt} enabled={enabled} pk={pk or 'missing'} "
                f"fret={capo_fret_token(body) or 'missing'}"
            )
            if c_pass:
                break
            wait(page, 1000)
        results["C_refresh"] = {
            "pass": c_pass,
            "pk": pk,
            "fret": capo_fret_token(body) or "missing",
            "charts_bb": bool(re.search(r"Charts in Bb", body or "", re.I)),
            "enabled": checkbox_state(page, "Capo Shape Mode") is True,
        }
        notes.append(f"C {results['C_refresh']}")

        # D: nav sequence
        nav_ok = True
        details = []
        for target in ["Songs", "Creative", "Backing", "Upload", "Practice"]:
            if target == "Creative":
                click_sidebar_once(page, "Creative") or click_nav(page, "Creative")
            else:
                click_sidebar_once(page, target)
            wait(page, 2500)
            expand_sidebar(page)
            body = sidebar_full(page)
            pk_n = practice_key(page) or ""
            capo_ok = checkbox_state(page, "Capo Shape Mode") is True and (
                fret_is_exactly_2(body)
                or bool(re.search(r"Charts in Bb", body or "", re.I))
                or bool(re.search(r"Sounding Key:\s*C\b", body or "", re.I))
            )
            # Prefer Capo sounding / charts; Practice Key input can lag on Upload.
            pk_ok = bool(re.match(r"^C\b", pk_n, re.I)) or bool(
                re.search(r"Sounding Key:\s*C\b", body or "", re.I)
            )
            love = "Love Story" in (
                body[body.find("ACTIVE SONG") : body.find("ACTIVE SONG") + 280]
                if "ACTIVE SONG" in body
                else body
            )
            step = capo_ok and pk_ok and love
            nav_ok = nav_ok and step
            details.append(
                f"{target}: ok={step} pk={pk_n} fret={capo_fret_token(body)} love={love}"
            )
        results["D_nav"] = {"pass": nav_ok, "details": details}
        notes.append(f"D {results['D_nav']}")

        # E: Mission
        enable_guitar_capo(page, notes, "Bb")
        wait(page, 1500)
        mission_ok = open_mission_backing(page, notes)
        wait(page, 2500)
        expand_sidebar(page)
        m_body = sidebar_full(page)
        m_live = checkbox_state(page, "Capo Shape Mode") is True and (
            fret_is_exactly_2(m_body) or bool(re.search(r"Charts in Bb", m_body or "", re.I))
        )
        page.reload(wait_until="domcontentloaded")
        wait(page, 6000)
        expand_sidebar(page)
        m_ref_body = sidebar_full(page)
        m_ref = checkbox_state(page, "Capo Shape Mode") is True and (
            fret_is_exactly_2(m_ref_body)
            or bool(re.search(r"Charts in Bb", m_ref_body or "", re.I))
        )
        returned = click_return_to_mission(page)
        wait(page, 3000)
        expand_sidebar(page)
        m_ret_body = sidebar_full(page)
        m_ret = checkbox_state(page, "Capo Shape Mode") is True and (
            fret_is_exactly_2(m_ret_body)
            or bool(re.search(r"Charts in Bb", m_ret_body or "", re.I))
        )
        results["E_mission"] = {
            "pass": bool(mission_ok and m_live and m_ref and m_ret),
            "opened": mission_ok,
            "live": m_live,
            "refresh": m_ref,
            "returned": returned,
            "after_return": m_ret,
        }
        notes.append(f"E {results['E_mission']}")

        # F: song change Clocks — Shape Bb player context, fret re-derives
        ensure_catalog_song(page, notes)
        pick_song(page, notes, "Clocks", "Pop") or pick_song(page, notes, "Clocks", "Rock")
        wait(page, 3000)
        expand_sidebar(page)
        f_body = sidebar_full(page)
        f_pk = practice_key(page) or ""
        f_enabled = checkbox_state(page, "Capo Shape Mode") is True
        f_bb = bool(re.search(r"Charts in Bb", f_body or "", re.I)) or "Bb" in (
            f_body or ""
        )
        f_pk_clocks = bool(re.search(r"^Eb\b", f_pk, re.I))
        results["F_song_change"] = {
            "pass": bool(f_enabled and f_bb and f_pk_clocks),
            "enabled": f_enabled,
            "charts_bb": f_bb,
            "pk": f_pk,
            "fret": capo_fret_token(f_body) or "missing",
        }
        notes.append(f"F {results['F_song_change']}")

        browser.close()

    gate = all(
        bool((results.get(k) or {}).get("pass"))
        for k in ("A_immediate", "B_rerun", "C_refresh", "D_nav", "E_mission", "F_song_change")
    )
    out = ROOT / "scripts" / "evidence-creative-backing" / (
        "pass8-capo-accept-trial-result.txt" if WITH_TRIAL else "pass8-capo-accept.txt"
    )
    lines = [
        f"url={URL}",
        f"with_trial_residue={WITH_TRIAL}",
        f"gate_pass={gate}",
        "",
        *[f"{k}: {v}" for k, v in results.items()],
        "",
        "NOTES",
        *notes,
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8", "replace"))
    return 0 if gate else 2


if __name__ == "__main__":
    raise SystemExit(main())
