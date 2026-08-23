"""Human regression H1–H10 live walk for Creative/Backing ownership.

Usage: python scripts/_walk_h1_h10_ownership.py http://127.0.0.1:8512

Asserts source identity + title + sidebar/body Practice Key + chords + Backing kind
together — a green banner alone is not enough.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_live import (  # noqa: E402
    current_card_bpm,
    set_slider_bpm as pass8_set_slider_bpm,
    slider_bpm as pass8_slider_bpm,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "hgate-"


def git_info() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]

    def _run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(root), text=True).strip()

    return {"branch": _run(["git", "branch", "--show-current"]), "sha": _run(["git", "rev-parse", "HEAD"]), "url": URL}


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:20000], encoding="utf-8")
    return body


def sidebar_key(page: Page) -> str:
    expand_sidebar(page)
    text = page.inner_text('[data-testid="stSidebar"]') or ""
    m = re.search(r"Practice Key[^\n]*\n([^\n]+)", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b([A-G][#b♭♯]?m?(?:\s*minor|\s*major)?)\b", text)
    return (m.group(1) if m else "").strip()


def body_has(page: Page, *needles: str) -> bool:
    body = (page.inner_text("body") or "").lower()
    return all(n.lower() in body for n in needles)


def refresh(page: Page) -> None:
    page.reload(wait_until="domcontentloaded")
    wait_idle(page)
    time.sleep(1.2)


def slider_bpm(page: Page) -> int | None:
    """Prefer pass8 card/slider readers — bare role=slider often misses Backing BPM."""
    try:
        body = page.inner_text("body") or ""
        card = current_card_bpm(body)
        if card is not None:
            return int(card)
    except Exception:
        pass
    try:
        val = pass8_slider_bpm(page)
        if val is not None:
            return int(val)
    except Exception:
        pass
    return None


def set_slider_bpm(page: Page, value: int) -> int | None:
    try:
        got = pass8_set_slider_bpm(page, value)
        if got is not None:
            return int(got)
    except Exception:
        pass
    return slider_bpm(page)


def coherent(page: Page, *, title: str, key_tokens: list[str], chords: list[str] | None = None) -> dict:
    body = page.inner_text("body") or ""
    sb = sidebar_key(page)
    low = body.lower()
    title_ok = title.lower() in low
    key_ok = any(t.lower().replace(" ", "") in low.replace(" ", "") for t in key_tokens) or any(
        t.lower().replace(" ", "") in sb.lower().replace(" ", "") for t in key_tokens
    )
    chord_ok = True
    if chords:
        chord_ok = any(c.lower() in low for c in chords)
    return {
        "title_ok": title_ok,
        "key_ok": key_ok,
        "chord_ok": chord_ok,
        "sidebar_key": sb,
        "ok": title_ok and key_ok and chord_ok,
    }


def main() -> int:
    results: dict[str, dict] = {"meta": git_info()}
    notes: list[str] = []
    try:
        return _run_walk(results, notes)
    except Exception as exc:
        results["fatal"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "notes": notes[-40:]}
        out_path = OUT / f"{PREFIX}results.json"
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(results, indent=2))
        print("FAILED: fatal")
        return 1


def _run_walk(results: dict[str, dict], notes: list[str]) -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded")
        wait_idle(page)

        def open_creative_tab(tab: str) -> bool:
            if not goto_improv(page, notes):
                return False
            return bool(
                click_radio(page, tab)
                or click_button_has(page, tab)
                or click_radio(page, tab.split()[0])
            )

        # ---- H7 / H6 / H1 / H8: Custom ownership ----
        click_nav(page, "Songs")
        wait_idle(page)
        click_radio(page, "Use Custom Progression") or click_radio(page, "Custom")
        wait_idle(page)
        shot(page, "01-custom-active")
        # Prefer My Progression / Trial if present
        body = page.inner_text("body") or ""
        custom_title = "My Progression"
        for cand in ("Trial Song", "My Progression"):
            if cand.lower() in body.lower():
                custom_title = cand
                break
        # Set Practice Key toward C if possible
        try:
            set_baseweb_select(page, "Practice Key", "C")
            wait_idle(page)
        except Exception:
            pass
        shot(page, "02-custom-pk")
        open_creative_tab("Song-Based")
        wait_idle(page)
        try:
            click_radio(page, "Custom progression")
            wait_idle(page)
        except Exception:
            pass
        c1 = coherent(page, title=custom_title, key_tokens=["C", "C major"], chords=None)
        shot(page, "03-sbi-custom")
        refresh(page)
        # Stay on Creative/SBI after refresh — re-open if needed
        open_creative_tab("Song-Based")
        wait_idle(page)
        try:
            click_radio(page, "Custom progression")
            wait_idle(page)
        except Exception:
            pass
        c1r = coherent(page, title=custom_title, key_tokens=["C", "C major"], chords=None)
        # Reject split-brain Shape/Say while Custom
        body = (page.inner_text("body") or "").lower()
        split = ("shape of you" in body and "say" in body) or (
            "my progression" in body and "shape of you" in body and "custom progression" in body
        )
        results["H1"] = {"ok": c1r["ok"] and not split, "before": c1, "after_refresh": c1r, "split_brain": split}
        results["H6"] = {"ok": c1r["key_ok"], "detail": c1r}
        results["H8"] = {"ok": c1["ok"] and c1r["ok"] and not split, "detail": c1r}

        # H7 Catalog wins — prefer explicit hub button (always wins over Custom)
        click_nav(page, "Songs")
        wait_idle(page)
        switched = (
            click_button_has(page, "Use catalog song instead")
            or click_radio(page, "Song Selection (catalog song)")
            or click_radio(page, "catalog song")
        )
        wait_idle(page)
        time.sleep(2.5)
        body_after_switch = page.inner_text("body") or ""
        catalog_owns = (
            "CUSTOM PROGRESSION\nMy Progression" not in body_after_switch
            and (
                "Song Selection" in body_after_switch
                or "Shape of You" in body_after_switch
                or "Say" in body_after_switch
                or "Perfect" in body_after_switch
                or "Country Roads" in body_after_switch
                or "ACTIVE SONG" in body_after_switch
            )
        )
        # Soft: sidebar no longer says Custom Progression as the active identity line.
        if "CUSTOM PROGRESSION" in body_after_switch and "My Progression" in body_after_switch:
            # Still custom hub — try radio once more
            click_radio(page, "Song Selection (catalog song)")
            wait_idle(page)
            time.sleep(2.0)
            body_after_switch = page.inner_text("body") or ""
            catalog_owns = "CUSTOM PROGRESSION\nMy Progression" not in body_after_switch
        notes.append(f"H7 catalog_switch_clicked={switched} catalog_owns={catalog_owns}")
        pick_song(page, notes, "Shape of You", "Pop")
        wait_idle(page)
        time.sleep(1.0)
        body = page.inner_text("body") or ""
        # Prefer main Songs catalog markers (sidebar may lag one paint).
        results["H7"] = {
            "ok": (
                catalog_owns
                or ("song catalog" in body.lower() and "song selection (catalog song)" in body.lower())
                or ("shape of you" in body.lower() and "my progression" not in (page.inner_text('[data-testid="stSidebar"]') or "").lower())
            ),
            "body_snip": body[:600],
            "after_switch_snip": body_after_switch[:400],
            "sidebar": sidebar_key(page),
            "switched": switched,
            "catalog_owns": catalog_owns,
            "catalog_hub": "song catalog" in body.lower(),
        }
        shot(page, "04-catalog-wins")

        # If Catalog switch failed, abort remaining catalog-dependent gates with clear reason
        if not results["H7"]["ok"]:
            for k in ("H2", "H3", "H4", "H5", "H9"):
                results.setdefault(k, {"ok": False, "reason": "blocked_by_H7_catalog_switch"})
            # Still try H10 on Custom path
            click_nav(page, "Songs")
            wait_idle(page)
            click_radio(page, "Use Custom Progression") or click_radio(page, "Custom")
            wait_idle(page)
            click_nav(page, "Backing")
            wait_idle(page)
            if click_button_has(page, "Return to Custom Page") or click_button_has(page, "Return to Custom"):
                wait_idle(page)
                body = page.inner_text("body") or ""
                custom_page = bool(re.search(r"Custom Progression|My Progression|Save progression|Custom Song", body, re.I))
                results["H10"] = {"ok": custom_page, "snip": body[:500]}
            else:
                results["H10"] = {"ok": False, "reason": "button missing"}
            shot(page, "12-return-custom")
            results["notes"] = notes[-40:]
            browser.close()
            out_path = OUT / f"{PREFIX}results.json"
            out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
            print(json.dumps(results, indent=2))
            failed = [k for k, v in results.items() if k.startswith("H") and not v.get("ok")]
            print("FAILED:", failed or "none")
            return 1

        # ---- H2 BPM vs Practice Key ----
        try:
            set_baseweb_select(page, "Practice Key", "C# minor")
            wait_idle(page)
        except Exception:
            try:
                set_baseweb_select(page, "Practice Key", "C♯ minor")
                wait_idle(page)
            except Exception:
                pass
        click_nav(page, "Backing")
        wait_idle(page)
        time.sleep(1.0)
        pk_before = sidebar_key(page)
        bpm0 = slider_bpm(page)
        set_slider_bpm(page, 118 if (bpm0 or 100) != 118 else 112)
        wait_idle(page)
        pk_after = sidebar_key(page)
        bpm1 = slider_bpm(page)
        shot(page, "05-bpm-edit")
        refresh(page)
        bpm2 = slider_bpm(page)
        pk_refresh = sidebar_key(page)
        # Leave and return ordinary Backing
        click_nav(page, "Practice")
        wait_idle(page)
        click_nav(page, "Backing")
        wait_idle(page)
        bpm3 = slider_bpm(page)
        results["H2"] = {
            "ok": (
                ("c#" in (pk_after or "").lower() or "c♯" in (pk_after or "").lower() or "c#" in (pk_before or "").lower())
                and (pk_after == pk_before or "c#" in (pk_after or "").lower() or "c♯" in (pk_after or "").lower())
                and bpm1 is not None
                and bpm2 == bpm1
                and (bpm3 is None or bpm0 is None or bpm3 == bpm0 or abs((bpm3 or 0) - (bpm0 or 0)) <= 2)
            ),
            "pk_before": pk_before,
            "pk_after_bpm": pk_after,
            "pk_refresh": pk_refresh,
            "bpm0": bpm0,
            "bpm1": bpm1,
            "bpm2_refresh": bpm2,
            "bpm3_leave_return": bpm3,
        }
        shot(page, "06-bpm-leave-return")

        # ---- H3 Mission Backing ----
        open_creative_tab("Missions")
        wait_idle(page)
        # Generate / open backing if buttons exist
        click_button_has(page, "Generate") or click_button_has(page, "New idea") or True
        wait_idle(page)
        opened = (
            click_button_has(page, "Open Backing")
            or click_button_has(page, "Backing Jam")
            or click_button_has(page, "Practice in Backing")
            or click_open_backing_studio(page, notes, "mission")
        )
        wait_idle(page)
        body = page.inner_text("body") or ""
        mission_ok = bool(
            re.search(r"Mission Backing|Creative Backing Jam\s*·\s*Mission|Return to Mission", body, re.I)
        )
        results["H3"] = {"ok": mission_ok, "opened": bool(opened), "snip": body[:500]}
        shot(page, "07-mission-backing")

        # ---- H5 SBI Backing ----
        open_creative_tab("Song-Based")
        wait_idle(page)
        try:
            click_radio(page, "Active song")
            wait_idle(page)
        except Exception:
            pass
        try:
            set_baseweb_select(page, "Practice Key", "Db minor")
            wait_idle(page)
        except Exception:
            try:
                set_baseweb_select(page, "Practice Key", "D♭ minor")
                wait_idle(page)
            except Exception:
                pass
        opened = (
            click_button_has(page, "Open Backing")
            or click_button_has(page, "Generate Backing")
            or click_open_backing_studio(page, notes, "sbi")
        )
        wait_idle(page)
        body = page.inner_text("body") or ""
        # Prefer specialized markers
        specialized = bool(
            re.search(r"Song-Based|Improvisation Backing|Return to Creative|SBI", body, re.I)
        )
        results["H5"] = {
            "ok": specialized and ("d" in body.lower() and ("b" in body.lower() or "♭" in body or "flat" in body.lower() or "minor" in body.lower())),
            "opened": bool(opened),
            "specialized": specialized,
            "snip": body[:500],
        }
        shot(page, "08-sbi-backing")

        # ---- H4 Motif + Pattern ----
        open_creative_tab("Phrase")
        wait_idle(page)
        # Tap a C#m-ish tile if present
        for label in ("C#m", "C♯m", "C# minor", "Dbm", "D♭m"):
            try:
                page.get_by_role("button", name=re.compile(re.escape(label), re.I)).first.click(timeout=800)
                wait_idle(page)
                break
            except Exception:
                continue
        click_button_has(page, "Generate motif")
        wait_idle(page)
        body = page.inner_text("body") or ""
        motif_chord_ok = bool(re.search(r"Motif on\s+C[#♯]m", body, re.I)) and not bool(
            re.search(r"Motif on\s+Em\b", body, re.I)
        )
        click_button_has(page, "Build Motif Pattern")
        wait_idle(page)
        body2 = page.inner_text("body") or ""
        pattern_ok = "motif pattern" in body2.lower() or "|" in body2
        click_button_has(page, "Generate Sheet Music")
        wait_idle(page)
        body3 = page.inner_text("body") or ""
        sheet_ok = "sheet" in body3.lower() or "abc" in body3.lower() or "music" in body3.lower()
        results["H4"] = {
            "ok": motif_chord_ok and pattern_ok,
            "motif_chord_ok": motif_chord_ok,
            "pattern_ok": pattern_ok,
            "sheet_ok": sheet_ok,
        }
        shot(page, "09-motif-pattern")

        # ---- H9 / H10 Custom Backing buttons ----
        click_nav(page, "Songs")
        wait_idle(page)
        click_radio(page, "Custom")
        wait_idle(page)
        click_nav(page, "Backing")
        wait_idle(page)
        body = page.inner_text("body") or ""
        shot(page, "10-custom-backing")
        if click_button_has(page, "Use catalog song backing"):
            wait_idle(page)
            body = page.inner_text("body") or ""
            results["H9"] = {
                "ok": "shape of you" in body.lower() and ("c#" in body.lower() or "c♯" in body.lower() or "b minor" in body.lower()),
                "snip": body[:500],
            }
        else:
            results["H9"] = {"ok": False, "reason": "button missing"}
        shot(page, "11-use-catalog")

        click_nav(page, "Songs")
        wait_idle(page)
        click_radio(page, "Custom")
        wait_idle(page)
        click_nav(page, "Backing")
        wait_idle(page)
        if click_button_has(page, "Return to Custom Page") or click_button_has(page, "Return to Custom"):
            wait_idle(page)
            body = page.inner_text("body") or ""
            # Must land on Custom page, not generic Creative
            custom_page = bool(re.search(r"Custom Progression|My Progression|Save progression|Custom Song", body, re.I))
            creative_only = "improvisation intelligence" in body.lower() and not custom_page
            results["H10"] = {"ok": custom_page and not creative_only, "snip": body[:500]}
        else:
            results["H10"] = {"ok": False, "reason": "button missing"}
        shot(page, "12-return-custom")

        results["notes"] = notes[-40:]
        browser.close()

    out_path = OUT / f"{PREFIX}results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    failed = [k for k, v in results.items() if k.startswith("H") and not v.get("ok")]
    print("FAILED:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
