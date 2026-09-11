"""Targeted one-shots for remaining broad-suite reds. Product frozen. Harness only.

Usage:
  python scripts/_oneshot_confirm_reds.py http://127.0.0.1:9210 <which>

which:
  style_jam_c_sharp   — Style Jam C# → generate → specialized Backing C# → refresh C#
  custom_sbi_d_to_e   — SBI Custom Trial → Backing native D→E → refresh E
  sbi_active          — Global Active Shape/Bm → SBI Custom → Active Source once
  songs_shape_creative — Songs land Shape/Bm then Creative
  hard_reboot_mission — Mission Backing last page → kill/restart same data dir
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9210"
WHICH = sys.argv[2] if len(sys.argv) > 2 else "style_jam_c_sharp"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = f"oneshot-{WHICH}-"
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def settle(page: Page, sec: float = 2.0) -> None:
    from walk_creative_backing_matrix import wait_idle

    wait_idle(page, int(sec * 1000))


def sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()


def shot(page: Page, name: str) -> tuple[str, str]:
    from walk_creative_backing_matrix import expand_sidebar

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
    return side, body


def persist_slice() -> dict:
    from _walk_human_h1_h9 import persist_h3_slice

    return persist_h3_slice()


def result(ok: bool, detail: str) -> int:
    payload = {
        "which": WHICH,
        "sha": sha(),
        "ok": bool(ok),
        "detail": detail,
        "notes": NOTES[-40:],
    }
    print(json.dumps(payload, indent=2), flush=True)
    print("RESULT=" + ("PASS" if ok else "RED"), flush=True)
    (OUT / f"{PREFIX}report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0 if ok else 1


def has_c_sharp(text: str) -> bool:
    t = low(text)
    return "c# major" in t or "c sharp major" in t or bool(re.search(r"c#\s+major", t))


def on_backing(body: str) -> bool:
    t = low(body)
    return "return to creative" in t or "return to mission" in t or (
        "backing track studio" in t and "tempo" in t
    )


def land_shape_bm(page: Page) -> bool:
    from _walk_owner_key_tuple import (
        custom_hub_to_catalog_song,
        land_songs_picker,
        pick_matching_song_once,
        songs_hub_state,
        wait_for_studio_ready,
        wait_shape_activation_bm,
    )

    wait_for_studio_ready(page)
    if not land_songs_picker(page):
        log("land_shape: picker miss")
        return False
    st = songs_hub_state(page)
    log(f"land_shape before={json.dumps(st, default=str)}")
    if st.get("ga_shape"):
        return wait_shape_activation_bm(page)
    if st.get("custom_hub") or st.get("ga_trial"):
        return bool(custom_hub_to_catalog_song(page, NOTES, "Shape of You").get("ok"))
    pick_matching_song_once(page, "Shape of You")
    return wait_shape_activation_bm(page)


def style_jam_owner(body: str, side: str, persist: dict) -> bool:
    blob = low(body + " " + side)
    src = str(persist.get("backing_source") or "")
    specialized = (
        "style jam" in blob
        or "entry style" in blob
        or src in {"entry_style_jam", "entry_jam"}
        or ("jam" in blob and "return to" in blob)
    )
    catalog = "shape of you" in blob and "catalog song" in blob and "return to" not in blob
    trial = "trial song" in blob and "custom" in blob and "return to" not in blob
    return specialized and not catalog and not trial


def run_style_jam_c_sharp() -> int:
    from walk_creative_backing_matrix import (
        click_button_has,
        click_open_backing_studio,
        click_radio,
        goto_improv,
        wait_for_backing,
    )
    from _walk_acceptance_an import set_style_jam_concert_key
    from _walk_human_h1_h9 import main_card_pk, native_pk
    from _walk_custom_practice_key import pk_val
    from _walk_owner_key_tuple import style_jam_concert_closed, wait_for_studio_ready

    log(json.dumps({"sha": sha(), "which": WHICH, "url": URL}))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 6)
        wait_for_studio_ready(page)
        shape = land_shape_bm(page)
        log(f"shape_land={shape}")
        if not goto_improv(page, NOTES):
            browser.close()
            return result(False, "goto_improv failed")
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
        settle(page, 2)
        click_radio(page, "Style Jam") or click_button_has(page, r"Style Jam Mode")
        settle(page, 3)
        concert_ok = False
        live = ""
        for _ in range(4):
            set_style_jam_concert_key(page, "C#") or set_style_jam_concert_key(page, "C# major")
            settle(page, 2)
            live = style_jam_concert_closed(page)
            if has_c_sharp(live) or str(live).strip() in {"C#", "C♯"}:
                concert_ok = True
                break
        log(f"jam_live={live!r} concert_ok={concert_ok}")
        if not concert_ok:
            browser.close()
            return result(False, f"setter did not commit C# live={live!r}")
        gen_heading = ""
        for attempt in range(3):
            click_button_has(page, r"Generate progression")
            settle(page, 4)
            try:
                page.wait_for_function(
                    """() => {
                      const t = document.body ? (document.body.innerText || '') : '';
                      return /Generated\\b/i.test(t) && /Open in Backing Studio/i.test(t);
                    }""",
                    timeout=20_000,
                )
            except Exception:
                pass
            body_gen = page.inner_text("body") or ""
            m = re.search(r"Generated[^\n]*", body_gen)
            gen_heading = (m.group(0) if m else body_gen[:240]).strip()
            log(f"generate attempt={attempt} heading={gen_heading!r}")
            if has_c_sharp(gen_heading) or has_c_sharp(body_gen):
                break
            set_style_jam_concert_key(page, "C#") or set_style_jam_concert_key(page, "C# major")
            settle(page, 2)
        side_g, body_g = shot(page, "generated")
        opened = click_button_has(page, r"Open in Backing Studio") or click_open_backing_studio(
            page, NOTES, "oneshot-jam"
        )
        landed = wait_for_backing(page, NOTES, "oneshot-jam")
        settle(page, 3)
        side, body = shot(page, "backing")
        persist = persist_slice()
        pk = pk_val(page) or ""
        card = main_card_pk(page, body)
        owner = style_jam_owner(body, side, persist)
        c_ok = has_c_sharp(body + side + pk + card) or "c#" in low(pk + card)
        still_creative = "open in backing studio" in low(body) and not on_backing(body)
        log(
            f"open={opened} landed={landed} still_creative={still_creative} "
            f"owner={owner} pk={pk!r} card={card!r} persist={persist}"
        )
        page.reload(wait_until="domcontentloaded", timeout=120_000)
        settle(page, 8)
        wait_for_backing(page, NOTES, "oneshot-jam-refresh")
        side_r, body_r = shot(page, "refresh")
        persist_r = persist_slice()
        pk_r = pk_val(page) or ""
        card_r = main_card_pk(page, body_r)
        refresh_ok = (
            style_jam_owner(body_r, side_r, persist_r)
            and (has_c_sharp(body_r + side_r + pk_r + card_r) or "c#" in low(pk_r + card_r))
        )
        click_button_has(page, r"Return to Creative") or click_button_has(page, r"Return to Style")
        settle(page, 4)
        side_ret, body_ret = shot(page, "return")
        no_bleed = "trial song" not in low(side_ret[:900]) or "style jam" in low(body_ret)
        browser.close()
        ok = (
            concert_ok
            and opened
            and landed
            and owner
            and c_ok
            and not still_creative
            and refresh_ok
        )
        return result(
            ok,
            f"live={live!r} gen={gen_heading!r} open={opened} landed={landed} "
            f"still_creative={still_creative} owner={owner} pk={pk!r} card={card!r} "
            f"c#={c_ok} refresh={refresh_ok} pk_r={pk_r!r} card_r={card_r!r} "
            f"src={persist.get('backing_source')!r} src_r={persist_r.get('backing_source')!r} "
            f"no_bleed={no_bleed}",
        )


def run_custom_sbi_d_to_e() -> int:
    from walk_creative_backing_matrix import click_button_has, click_open_backing_studio, wait_for_backing
    from _walk_human_h1_h9 import main_card_pk, native_pk
    from _walk_custom_practice_key import pk_val
    from _walk_ownership_audit_full import build_trial_song
    from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source

    log(json.dumps({"sha": sha(), "which": WHICH, "url": URL}))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 6)
        trial_ok = build_trial_song(page, NOTES)
        click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
        settle(page, 3)
        opened_sbi = open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        opened = click_open_backing_studio(page, NOTES, "custom-sbi") or click_button_has(
            page, r"Open in Backing"
        )
        landed = wait_for_backing(page, NOTES, "custom-sbi")
        settle(page, 4)
        side0, body0 = shot(page, "open")
        persist0 = persist_slice()
        pk0 = pk_val(page) or ""
        card0 = main_card_pk(page, body0)
        trial0 = "trial song" in low(body0 + side0)
        native_pk(page, "D") or native_pk(page, "D major")
        settle(page, 2)
        changed = native_pk(page, "E") or native_pk(page, "E major")
        settle(page, 5)
        side1, body1 = shot(page, "after-e")
        persist1 = persist_slice()
        pk1 = pk_val(page) or ""
        card1 = main_card_pk(page, body1)
        e_side = "e" in low(pk1) and "minor" not in low(pk1)
        e_card = "e" in low(card1) and "minor" not in low(card1)
        trial1 = "trial song" in low(body1 + side1)
        src1 = str(persist1.get("backing_source") or persist1.get("backing_pref") or "")
        page.reload(wait_until="domcontentloaded", timeout=120_000)
        settle(page, 8)
        wait_for_backing(page, NOTES, "custom-sbi-refresh")
        side2, body2 = shot(page, "refresh")
        persist2 = persist_slice()
        pk2 = pk_val(page) or ""
        card2 = main_card_pk(page, body2)
        e_refresh = ("e" in low(pk2) and "minor" not in low(pk2)) and (
            not str(card2).strip() or ("e" in low(card2) and "minor" not in low(card2))
        )
        trial2 = "trial song" in low(body2 + side2)
        browser.close()
        ok = (
            trial_ok
            and opened_sbi
            and opened
            and landed
            and trial0
            and changed
            and e_side
            and e_card
            and trial1
            and e_refresh
            and trial2
        )
        return result(
            ok,
            f"trial_build={trial_ok} sbi={opened_sbi} open={opened} landed={landed} "
            f"pk0={pk0!r} card0={card0!r} changed={changed} pk1={pk1!r} card1={card1!r} "
            f"e_side={e_side} e_card={e_card} trial1={trial1} src1={src1!r} "
            f"pk2={pk2!r} card2={card2!r} e_refresh={e_refresh} trial2={trial2} "
            f"persist0={persist0.get('backing_source')!r} persist2={persist2.get('backing_source')!r}",
        )


def run_sbi_active() -> int:
    from walk_creative_backing_matrix import click_button_has
    from _walk_custom_practice_key import pk_val
    from _walk_owner_key_tuple import (
        click_sbi_song_source,
        sbi_source_state,
        wait_sbi_tuple,
    )
    from _walk_core_workflows_embargo import open_sbi_active
    from _walk_ownership_audit_full import build_trial_song
    from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source

    log(json.dumps({"sha": sha(), "which": WHICH, "url": URL}))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 6)
        build_trial_song(page, NOTES)
        click_button_has(page, r"Set as Active Song")
        settle(page, 2)
        shape = land_shape_bm(page)
        log(f"shape_land={shape}")
        open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        side_c, body_c = shot(page, "custom-before")
        radio_before = sbi_source_state(page)
        from walk_creative_backing_matrix import click_radio

        clicked = click_radio(page, "Active Source") or click_sbi_song_source(page, "active")
        if not clicked:
            clicked = bool(open_sbi_active(page))
        settle(page, 2)
        landed = wait_sbi_tuple(page, source="active", title="Shape of You", timeout_ms=25_000)
        if not landed:
            try:
                page.wait_for_function(
                    """() => {
                      const main = (document.querySelector('[data-testid="stMain"]') || {}).innerText || '';
                      const low = main.toLowerCase();
                      return /Shape of You/i.test(main)
                        && (/B minor/i.test(main) || /practice concert key:\\s*bm/i.test(low))
                        && !(/trial song/i.test(main) && /custom progression/i.test(low));
                    }""",
                    timeout=20_000,
                )
                landed = True
            except Exception:
                landed = False
        settle(page, 2)
        side, body = shot(page, "after-active")
        radio = sbi_source_state(page)
        pk = pk_val(page) or ""
        catalog = "catalog song" in low(body) or "active song · song selection" in low(body)
        shape_id = "shape of you" in low(body + side)
        trial = "trial song" in low(body) and "custom progression" in low(body)
        bm = "b minor" in low(pk + body + side) or bool(re.search(r"\bbm\b", low(pk + body)))
        browser.close()
        ok = clicked and landed and radio == "active" and shape_id and bm and catalog and not trial
        return result(
            ok,
            f"shape={shape} radio_before={radio_before!r} clicked={clicked} landed={landed} "
            f"radio={radio!r} pk={pk!r} shape_id={shape_id} bm={bm} catalog={catalog} trial={trial}",
        )


def run_songs_shape_creative() -> int:
    from walk_creative_backing_matrix import click_nav
    from _walk_owner_key_tuple import songs_hub_state
    from _walk_songs_creative_nav import click_songs_creative_button, on_creative

    log(json.dumps({"sha": sha(), "which": WHICH, "url": URL}))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 6)
        click_nav(page, "Songs")
        settle(page, 3)
        before = songs_hub_state(page)
        log(f"before={before}")
        landed = land_shape_bm(page)
        after = songs_hub_state(page)
        log(f"after_pick landed={landed} state={after}")
        if not landed:
            side, body = shot(page, "shape-miss")
            browser.close()
            return result(False, f"Shape did not land before Creative before={before} after={after}")
        clicked = click_songs_creative_button(page)
        settle(page, 3)
        try:
            page.wait_for_function(
                """() => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  return /Entry & Jam/i.test(t) || /Improvisation Intelligence/i.test(t)
                    || /Song-Based/i.test(t);
                }""",
                timeout=20_000,
            )
        except Exception:
            pass
        side, body = shot(page, "creative")
        creative = on_creative(body)
        still_shape = "shape of you" in low(body + side)
        browser.close()
        ok = landed and clicked and creative and still_shape
        return result(
            ok,
            f"landed={landed} click={clicked} creative={creative} still_shape={still_shape} after={after}",
        )


def run_hard_reboot_mission() -> int:
    from walk_creative_backing_matrix import click_button_has, wait_for_backing
    from _walk_core_key_coherence import set_songs_practice_key
    from _walk_core_workflows_embargo import (
        click_available_mission_chord,
        click_generate_example_once,
        hard_reboot_streamlit,
        wait_for_body,
    )
    from _walk_custom_practice_key import pk_val
    from walk_guitar_shape_key import pick_song
    from _walk_owner_key_tuple import wait_for_studio_ready
    from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing
    from walk_creative_backing_matrix import goto_improv
    from urllib.parse import urlparse

    log(json.dumps({"sha": sha(), "which": WHICH, "url": URL}))
    port = int(urlparse(URL).port or 9211)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 6)
        wait_for_studio_ready(page)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        if not goto_improv(page, NOTES):
            browser.close()
            return result(False, "goto_improv failed before reboot")
        ensure_missions_workspace(page, NOTES)
        settle(page, 2)
        chord = click_available_mission_chord(page)
        click_generate_example_once(page)
        opened = False
        try:
            opened = bool(open_mission_backing(page, NOTES))
        except Exception:
            opened = click_button_has(page, r"Open Mission Backing")
        wait_for_backing(page, NOTES, "pre-reboot-mission")
        settle(page, 4)
        side0, body0 = shot(page, "before")
        persist0 = persist_slice()
        pk0 = pk_val(page) or ""
        on_mb = "return to mission" in low(body0) or "mission backing" in low(body0)
        before = {
            "studio_page": persist0.get("studio_page"),
            "page_layers": persist0.get("page_layers"),
            "backing_source": persist0.get("backing_source"),
            "display_key": persist0.get("display_key"),
            "pk": pk0,
            "on_mission_backing": on_mb,
            "chord": chord,
            "opened": opened,
        }
        log(f"before={json.dumps(before, default=str)}")
        browser.close()

        hard_reboot_streamlit(port)
        settle_wait = 8
        import time as _t

        _t.sleep(settle_wait)
        browser2 = p.chromium.launch(headless=True)
        page2 = browser2.new_page(viewport={"width": 1440, "height": 960})
        page2.goto(URL, wait_until="domcontentloaded", timeout=180000)
        first_body = wait_for_body(
            page2,
            "Return to Mission",
            "MISSION BACKING",
            "Shape of You",
            "Welcome back",
            "Entry & Jam",
            timeout_s=75,
        )
        settle(page2, 6)
        side1, body1 = shot(page2, "after")
        persist1 = persist_slice()
        pk1 = pk_val(page2) or ""
        first_page = persist1.get("studio_page")
        first_src = persist1.get("backing_source")
        boot_mission = "return to mission" in low(body1) or "mission backing" in low(body1)
        after = {
            "studio_page": first_page,
            "page_layers": persist1.get("page_layers"),
            "backing_source": first_src,
            "display_key": persist1.get("display_key"),
            "pk": pk1,
            "boot_mission": boot_mission,
            "first_body_head": (first_body or body1)[:400],
        }
        log(f"after={json.dumps(after, default=str)}")
        # Do not navigate to Missions during boot observation.
        restored = boot_mission or (
            str(first_page or "").lower() in {"backing", "creative"}
            and str(first_src or "") == "mission"
        )
        browser2.close()
        ok = bool(on_mb and restored)
        return result(
            ok,
            f"before={before} after={after} restored={restored}",
        )


if __name__ == "__main__":
    runners = {
        "style_jam_c_sharp": run_style_jam_c_sharp,
        "custom_sbi_d_to_e": run_custom_sbi_d_to_e,
        "sbi_active": run_sbi_active,
        "songs_shape_creative": run_songs_shape_creative,
        "hard_reboot_mission": run_hard_reboot_mission,
    }
    fn = runners.get(WHICH)
    if fn is None:
        print("unknown which=" + WHICH, flush=True)
        raise SystemExit(2)
    raise SystemExit(fn())
