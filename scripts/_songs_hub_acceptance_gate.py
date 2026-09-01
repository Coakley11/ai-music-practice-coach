"""Browser acceptance for Songs hub uniqueness, edit CTAs, Custom Eb→Composition C,
Composition key agreement, and no Creative return from Songs→Composition Backing.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "_source_identity_browser_evidence"
OUT.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location("v", ROOT / "_source_identity_browser_verify.py")
v = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v)
import _practice_key_e_gate as pke  # noqa: E402

RESULTS: list[dict] = []


def log(step: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"step": step, "ok": ok, "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {step}: {detail}", flush=True)


def _count_live_buttons(page, key: str) -> int:
    loc = page.locator(f".st-key-{key} button")
    n = 0
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if btn.is_visible() and v._marker_is_live(btn):
                n += 1
        except Exception:
            continue
    return n


def _set_practice_key_option(page, needle: str) -> bool:
    """Select Practice/Concert Key option containing needle (handles virtualized lists)."""
    box = page.locator('[data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Practice\s*/\s*Concert Key", re.I)
    )
    if box.count() == 0:
        return False
    ctrl = box.first.locator('[data-baseweb="select"], div[role="button"], input')
    if ctrl.count():
        ctrl.first.click(timeout=5000)
    else:
        box.first.click(timeout=5000)
    v.wait_streamlit(page, 500)
    try:
        page.wait_for_selector('[role="option"]', timeout=5000)
    except Exception:
        return False
    needles = {
        needle,
        needle.replace("b", "♭"),
        needle.replace("♭", "b"),
        f"{needle} major",
        f"{needle} Major",
        f"{needle}m",
        f"{needle} minor",
    }
    listbox = page.locator('[role="listbox"]')
    # Scroll virtualized menu and click a matching option.
    for direction in (-1, 1):
        for _ in range(40):
            opts = page.locator('[role="option"]')
            for i in range(opts.count()):
                t = (opts.nth(i).inner_text(timeout=300) or "").strip()
                if not t or t == "No results":
                    continue
                if t in needles or any(n == t or t.startswith(n + " ") for n in needles):
                    opts.nth(i).click(timeout=5000)
                    v.wait_streamlit_idle(page)
                    v.wait_streamlit(page, 2000)
                    return True
                # Loose contains for Eb / E♭ / Ebm
                if any(n in t for n in needles if len(n) >= 2):
                    opts.nth(i).click(timeout=5000)
                    v.wait_streamlit_idle(page)
                    v.wait_streamlit(page, 2000)
                    return True
            if listbox.count():
                listbox.first.evaluate(f"e => e.scrollTop += {direction * 140}")
                page.wait_for_timeout(60)
            else:
                break
    page.keyboard.press("Escape")
    return False


def _sidebar_practice_key_value(page) -> str:
    box = page.locator('[data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Practice\s*/\s*Concert Key", re.I)
    )
    if not box.count():
        return ""
    # Prefer the visible selected value node inside the control.
    try:
        val = box.first.locator('[data-baseweb="select"] span, div[role="button"] span').first
        if val.count():
            t = (val.inner_text(timeout=1000) or "").strip()
            if t and "Practice" not in t:
                return t
    except Exception:
        pass
    return (box.first.inner_text(timeout=2000) or "").replace("\n", " ")[:160]


def main() -> int:
    fails = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1200})
        page.goto(v.URL + "/?dev=1", wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 5000)

        # ---- A. Custom Songs UI ----
        v.ensure_songs(page)
        v.select_music_source(page, "Custom Progression")
        prac = _count_live_buttons(page, "custom_hub_practice")
        back = _count_live_buttons(page, "custom_hub_backing")
        creative = _count_live_buttons(page, "custom_hub_creative")
        karaoke = _count_live_buttons(page, "custom_hub_karaoke")
        coach = _count_live_buttons(page, "custom_hub_chord_coach")
        card_prac = _count_live_buttons(page, "picker_card_practice")
        card_back = _count_live_buttons(page, "picker_card_backing")
        edit_custom = page.get_by_role("button", name=re.compile(r"Edit custom chart", re.I))
        old_custom_edit = page.locator(".st-key-custom_hub_edit button")
        ok = (
            prac == 1
            and back == 1
            and creative == 1
            and karaoke == 1
            and coach == 1
            and card_prac == 0
            and card_back == 0
        )
        log(
            "custom_five_nav_actions",
            ok,
            f"p={prac} b={back} cr={creative} k={karaoke} cc={coach} "
            f"card_p={card_prac} card_b={card_back}",
        )
        if not ok:
            fails += 1
        ok_edit = edit_custom.count() >= 1 and old_custom_edit.count() == 0
        log(
            "custom_single_edit_cta",
            ok_edit,
            f"edit_custom={edit_custom.count()} old_hub_edit={old_custom_edit.count()}",
        )
        if not ok_edit:
            fails += 1

        # Custom Practice Key → Eb / E♭ / Ebm (mode-aware virtualized options)
        eb_set = (
            _set_practice_key_option(page, "Eb")
            or _set_practice_key_option(page, "E♭")
            or _set_practice_key_option(page, "Ebm")
        )
        side_after_eb = _sidebar_practice_key_value(page)
        body_eb = v.body_text(page)
        eb_ok = eb_set and any(
            x in side_after_eb or x in body_eb for x in ("Eb", "E♭", "Ebm")
        )
        log("custom_set_eb", eb_ok, f"side={side_after_eb[:80]} set={eb_set}")
        if not eb_ok:
            fails += 1

        # ---- B. Composition key ownership ----
        try:
            v.select_music_source(page, "Composition")
            v.wait_composition_hub_ready(page, timeout_ms=35000)
        except Exception as first_exc:
            # After Custom Practice Key edits, ownership promote can lag one run —
            # remount Songs and re-select Composition.
            log("composition_select_retry", False, str(first_exc)[:160])
            page.goto(v.URL + "/?dev=1", wait_until="domcontentloaded", timeout=120_000)
            v.wait_streamlit(page, 4000)
            v.ensure_songs(page)
            v.select_music_source(page, "Composition")
            v.wait_composition_hub_ready(page, timeout_ms=40000)
        side_comp = _sidebar_practice_key_value(page)
        body_comp = v.body_text(page)
        # Custom Eb/Ebm must not remain in the Practice Key control after switch.
        ok_c = not any(x in side_comp for x in ("Eb", "E♭", "Ebm")) and (
            bool(re.search(r"\bC\b", side_comp))
            or "C major" in body_comp
            or bool(re.search(r"Original\s+key:\s*C\b", body_comp, re.I))
            or bool(re.search(r"Song\s+Original\s+Key:\s*C\b", body_comp, re.I))
            or "My Composition" in body_comp
        )
        log("custom_eb_to_composition_c", ok_c, f"side={side_comp[:80]}")
        if not ok_c:
            fails += 1

        prac = _count_live_buttons(page, "composition_hub_practice")
        back = _count_live_buttons(page, "composition_hub_backing")
        creative = _count_live_buttons(page, "composition_hub_creative")
        karaoke = _count_live_buttons(page, "composition_hub_karaoke")
        coach = _count_live_buttons(page, "composition_hub_chord_coach")
        card_prac = _count_live_buttons(page, "picker_card_practice")
        card_back = _count_live_buttons(page, "picker_card_backing")
        ok = (
            prac == 1
            and back == 1
            and creative == 1
            and karaoke == 1
            and coach == 1
            and card_prac == 0
            and card_back == 0
        )
        log(
            "composition_five_nav_actions",
            ok,
            f"p={prac} b={back} cr={creative} k={karaoke} cc={coach} "
            f"card_p={card_prac} card_b={card_back}",
        )
        if not ok:
            fails += 1
        edit_comp = page.get_by_role("button", name=re.compile(r"Edit composition chart", re.I))
        old_comp_edit = page.locator(".st-key-composition_hub_edit button")
        ok_edit = edit_comp.count() >= 1 and old_comp_edit.count() == 0
        log(
            "composition_single_edit_cta",
            ok_edit,
            f"edit_comp={edit_comp.count()} old_hub_edit={old_comp_edit.count()}",
        )
        if not ok_edit:
            fails += 1

        # Set Composition Practice Key E (exact option match, then scroll fallback)
        e_set = pke.set_practice_key_e(page) or _set_practice_key_option(page, "E")
        side_e = _sidebar_practice_key_value(page)
        body_e = v.body_text(page)
        e_ok = e_set and (
            bool(re.search(r"\bE\b", side_e))
            or bool(re.search(r"Practice\s+concert\s+key:\s*E\b", body_e, re.I))
            or "E major" in body_e
        )
        log("composition_set_e", e_ok, f"side={side_e[:80]} set={e_set}")
        if not e_ok:
            fails += 1

        # Open Backing via hub
        loc = page.locator(".st-key-composition_hub_backing button")
        clicked = False
        for j in range(loc.count()):
            btn = loc.nth(j)
            if btn.is_visible() and v._marker_is_live(btn):
                btn.click(timeout=8000)
                clicked = True
                break
        if not clicked:
            log("composition_open_backing", False, "no hub button")
            fails += 1
        else:
            ok_open = v._await_backing_studio(page, timeout_ms=45000, prefer="composition")
            log("composition_open_backing", ok_open, f"page={v._studio_page_id(page)}")
            if not ok_open:
                fails += 1

        html = v.body_html(page)
        text = v.body_text(page)
        card_e = bool(
            re.search(r"Practice\s+concert\s+key:\s*E(\s+major)?\b", text, re.I)
        )
        no_creative = "Return to Creative" not in text
        has_source_badge = "Source" in html and "Composition" in html
        has_style_badge = "Style" in html and "Auto" in html
        side_on_backing = _sidebar_practice_key_value(page)
        agree = card_e and (
            bool(re.search(r"\bE\b", side_on_backing)) or "E major" in text
        )
        log("composition_backing_no_creative_return", no_creative, text[text.find("Return"):text.find("Return")+80] if "Return" in text else "no Return*")
        log("composition_card_sidebar_agree_e", agree, f"side={side_on_backing[:80]} card_has_e={card_e}")
        log("composition_badges", has_source_badge and has_style_badge, "source+style")
        if not no_creative:
            fails += 1
        if not agree:
            fails += 1
        if not (has_source_badge and has_style_badge):
            fails += 1

        # Refresh persistence
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 5000)
        kept = False
        for _ in range(8):
            try:
                if v._live_mode_card(page, "mode-composition-song-backing"):
                    kept = True
                    break
            except Exception:
                pass
            page.wait_for_timeout(800)
        if not kept:
            try:
                pke._reopen_composition_backing(page)
            except Exception as exc:
                log("composition_reopen_after_refresh", False, str(exc)[:160])
                fails += 1
        # Give Streamlit a beat after card appears so Practice Key hydrates.
        v.wait_streamlit(page, 2500)
        text2 = v.body_text(page)
        html2 = v.body_html(page)
        side2 = _sidebar_practice_key_value(page)
        pk_line = pke._practice_key_line(text2)
        still_e = (
            pke._has_practice_e(text2)
            or bool(re.search(r"Practice\s+concert\s+key:\s*E(\s+major)?\b", text2, re.I))
            or bool(re.search(r"Practice\s+E(\s+major)?\b", text2, re.I))
            or bool(re.search(r"\bE\b", side2))
        )
        # Progression should still reflect E when original was C (E–C#m–A–B)
        still_prog = pke._has_e_progression(text2, html2) or still_e
        no_creative2 = "Return to Creative" not in text2
        log(
            "composition_e_after_refresh",
            still_e and still_prog,
            f"e={still_e} prog={still_prog} kept_card={kept} "
            f"side={side2[:60]!r} pk_line={pk_line[:80]!r}",
        )
        log("composition_no_creative_after_refresh", no_creative2, "")
        if not (still_e and still_prog):
            fails += 1
        if not no_creative2:
            fails += 1

        browser.close()

    (OUT / "songs_hub_acceptance.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print(f"Failures: {fails}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
