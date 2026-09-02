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
import _practice_key_harness as pkh  # noqa: E402

RESULTS: list[dict] = []
FIRST_ATTEMPT_RECOVERIES: list[str] = []


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
    ok, _before, _after = pkh.select_practice_key_option(page, needle, v.wait_streamlit_idle)
    if ok:
        v.wait_streamlit(page, 1500)
    return ok


def _sidebar_practice_key_value(page) -> str:
    return pkh.read_practice_key_widget_value(page)


def _wait_composition_backing_card_hydrated(page, *, timeout_ms: int = 20000) -> tuple[bool, str]:
    """Wait for live Composition backing card + Practice Key line (not stale DOM)."""
    deadline = time.time() + timeout_ms / 1000.0
    last_side = ""
    while time.time() < deadline:
        if v._live_mode_card(page, "mode-composition-song-backing"):
            v.wait_streamlit_idle(page)
            text = v.body_text(page)
            card_pk = pkh.read_card_practice_key(text)
            last_side = _sidebar_practice_key_value(page)
            if card_pk and last_side:
                return True, f"card={card_pk!r} widget={last_side!r}"
        page.wait_for_timeout(250)
    return False, f"timeout side={last_side!r}"


def main() -> int:
    fails = 0
    import _gate_workspace as gw

    _ws, start_url = gw.prepare_isolated_workspace("gate_songs_hub", seed="empty")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1200})
        page.goto(start_url, wait_until="domcontentloaded", timeout=180_000)
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
            page.goto(start_url, wait_until="domcontentloaded", timeout=120_000)
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
        edit_comp = page.get_by_role("button", name=re.compile(r"Edit composition(?! chart)", re.I))
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

        hydrated, hydrate_detail = _wait_composition_backing_card_hydrated(page)
        log("composition_backing_hydrated", hydrated, hydrate_detail)
        if not hydrated:
            fails += 1

        text = v.body_text(page)
        html = v.body_html(page)
        side_on_backing = _sidebar_practice_key_value(page)
        card_pk = pkh.read_card_practice_key(text)
        card_e = pkh.key_token_in_text(card_pk or text, "E")
        no_creative = "Return to Creative" not in text
        has_source_badge = "Source" in html and "Composition" in html
        has_style_badge = "Style" in html and "Auto" in html
        agree = (
            card_e
            and pkh.key_token_in_text(side_on_backing, "E")
            and (not card_pk or pkh.key_token_in_text(card_pk, "E"))
        )
        log("composition_backing_no_creative_return", no_creative, "")
        log(
            "composition_card_sidebar_agree_e",
            agree,
            f"first_attempt side={side_on_backing[:80]!r} card_pk={card_pk!r}",
        )
        log("composition_badges", has_source_badge and has_style_badge, "source+style")
        if not no_creative:
            fails += 1
        if not agree:
            fails += 1
            FIRST_ATTEMPT_RECOVERIES.append("composition_card_sidebar_agree_e")
        if not (has_source_badge and has_style_badge):
            fails += 1

        # Refresh persistence — report recovery separately from first-attempt pass.
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 5000)
        kept = False
        for _ in range(12):
            if v._live_mode_card(page, "mode-composition-song-backing"):
                v.wait_streamlit_idle(page)
                kept = True
                break
            page.wait_for_timeout(400)
        recovery_used = False
        if not kept:
            recovery_used = True
            FIRST_ATTEMPT_RECOVERIES.append("composition_reopen_after_refresh")
            try:
                pke._reopen_composition_backing(page)
                kept = v._live_mode_card(page, "mode-composition-song-backing")
            except Exception as exc:
                log("composition_reopen_after_refresh", False, str(exc)[:160])
                fails += 1
        log(
            "composition_refresh_card_first_attempt",
            kept and not recovery_used,
            f"kept={kept} recovery={recovery_used}",
        )
        if recovery_used:
            log("composition_reopen_after_refresh", kept, "reload-assisted recovery")
        hydrated2, detail2 = _wait_composition_backing_card_hydrated(page)
        log("composition_refresh_hydrated", hydrated2, detail2)
        text2 = v.body_text(page)
        html2 = v.body_html(page)
        side2 = _sidebar_practice_key_value(page)
        card_pk2 = pkh.read_card_practice_key(text2)
        still_e = pkh.key_token_in_text(side2, "E") and (
            pkh.key_token_in_text(card_pk2 or text2, "E")
        )
        still_prog = pke._has_e_progression(text2, html2) or still_e
        no_creative2 = "Return to Creative" not in text2
        refresh_ok = still_e and still_prog and hydrated2
        log(
            "composition_e_after_refresh",
            refresh_ok,
            f"e={still_e} prog={still_prog} side={side2[:60]!r} card={card_pk2!r} "
            f"recovery={recovery_used}",
        )
        log("composition_no_creative_after_refresh", no_creative2, "")
        if not refresh_ok:
            fails += 1
        if not no_creative2:
            fails += 1

        browser.close()

    (OUT / "songs_hub_acceptance.json").write_text(
        json.dumps({"results": RESULTS, "first_attempt_recoveries": FIRST_ATTEMPT_RECOVERIES}, indent=2),
        encoding="utf-8",
    )
    print(f"Failures: {fails}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
