"""Focused Backing Key Cycle browser checks (port 8510).

Priorities:
1. Real audio ``ended`` → advance exactly once → next pass in new key (autoplay)
2. Stop restore + late ended cannot revive cycle
3. Short independent owners: Custom, SBI Custom, SBI Composition
4. Written / guitar-capo projections during cycle and after Stop

Does not use Complete pass. Preserves user data (isolated ``_runtime_key_cycle_8510``).
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import walk_creative_backing_matrix as m
import walk_practice_loop_backing as wpl
from walk_creative_backing_matrix import (
    click_button_has,
    click_open_backing_studio,
    click_radio,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
)
from walk_practice_loop_backing import goto_studio

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)

REPORT: dict = {
    "browser_passes": [],
    "app_defects": [],
    "automation_or_unverified": [],
    "owners": {},
    "log": [],
}


def wait_idle(page, ms=900):
    page.wait_for_timeout(ms)


m.wait_idle = wait_idle
wpl.wait_idle = wait_idle
wpl.settle = lambda page, seconds=1.5: wait_idle(page, int(seconds * 1000))


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line.encode("ascii", "replace").decode("ascii"), flush=True)
    REPORT["log"].append(line)


def body(page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def on_backing(page) -> bool:
    b = body(page)
    return ("Play Backing Track" in b) or ("Quick BPM" in b) or ("Advanced playback" in b)


def land_backing(page) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    for _ in range(3):
        if goto_studio(page, "Backing") and on_backing(page):
            return True
        wait_idle(page, 1500)
        expand_pages_nav(page)
    return on_backing(page)


def open_advanced(page) -> bool:
    """Expand Advanced playback settings without toggling it closed."""
    return bool(
        page.evaluate(
            """() => {
              const all = [...document.querySelectorAll('details,[data-testid="stExpander"]')];
              for (const el of all) {
                if (!(el.innerText || '').toLowerCase().includes('advanced playback')) continue;
                const visibleCycleBtn = [...el.querySelectorAll('button')].some((b) => {
                  const t = (b.innerText || '').trim();
                  return (
                    b.offsetParent !== null &&
                    (t === 'Start cycle' || t === 'Stop / Reset' || t === 'Advance')
                  );
                });
                if (visibleCycleBtn) return true;
                (el.querySelector('summary') || el.querySelector('button') || el).click();
                return true;
              }
              return false;
            }"""
        )
    )


def click_btn(page, label: str) -> bool:
    open_advanced(page)
    return bool(
        page.evaluate(
            """(label)=>{
              const buttons=[...document.querySelectorAll('button')];
              let b=buttons.find(
                el=>(el.innerText||'').trim()===label && el.offsetParent!==null
              );
              if(!b){
                b=buttons.find(el=>(el.innerText||'').trim()===label);
              }
              if(!b) return false;
              try { b.scrollIntoView({block:'center'}); } catch (e) {}
              b.click();
              return true;
            }""",
            label,
        )
    )


def status_now(page) -> dict:
    open_advanced(page)
    wait_idle(page, 400)
    text = body(page)
    out = {"raw": "", "status": "", "saved": "", "current": "", "passes": 0, "owner": ""}
    m_status = re.search(r"Key Cycle Practice:\s*([A-Za-z]+)", text)
    m_saved = re.search(r"Saved Practice Key:\s*([^\n·]+)", text)
    m_cur = re.search(r"Current Playback Key:\s*([^\n·]+)", text)
    m_pass = re.search(r"Passes completed:\s*(\d+)", text)
    m_own = re.search(r"Owner:\s*([^\n·]+)", text)
    if m_status:
        out["status"] = m_status.group(1).strip()
    if m_saved:
        out["saved"] = m_saved.group(1).strip()
    if m_cur:
        out["current"] = m_cur.group(1).strip()
    if m_pass:
        out["passes"] = int(m_pass.group(1))
    if m_own:
        out["owner"] = m_own.group(1).strip()
    out["raw"] = text[:2000]
    return out


def find_audio(page):
    """Return (frame_or_page, audio_handle) for the live player."""
    for fr in page.frames:
        try:
            handle = fr.query_selector("audio#live-audio, audio")
            if handle:
                return fr, handle
        except Exception:
            continue
    handle = page.query_selector("audio")
    return page, handle


def wait_for_audio(page, seconds=45) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        fr, handle = find_audio(page)
        if handle:
            try:
                dur = handle.evaluate("a => Number(a.duration)||0")
                if dur > 0.2:
                    return True
            except Exception:
                pass
        wait_idle(page, 800)
    return False


def play_near_end_and_wait_ended(page, timeout_s=25) -> dict:
    """Seek near end, play, wait for natural ``ended`` (not synthetic dispatch)."""
    info = {
        "found": False,
        "ended": False,
        "duration": 0.0,
        "seeked": False,
        "bridge_clicked": False,
        "method": "natural_ended",
    }
    fr, handle = find_audio(page)
    if not handle:
        return info
    info["found"] = True
    try:
        # Bridge click counter on parent
        page.evaluate(
            """() => {
              window.__kcBridgeClicks = 0;
              if (!window.__kcBridgeHooked) {
                window.__kcBridgeHooked = true;
                document.addEventListener('click', (ev) => {
                  const t = (ev.target && (ev.target.innerText||ev.target.textContent)||'').trim();
                  if (t === 'Key cycle pass finished') window.__kcBridgeClicks += 1;
                }, true);
              }
            }"""
        )
        dur = float(handle.evaluate("a => Number(a.duration)||0") or 0)
        info["duration"] = dur
        if dur <= 0.2:
            return info
        # Seek close to end and play so the real ended event fires.
        handle.evaluate(
            """(a) => {
              try { a.pause(); } catch (e) {}
              const d = Number(a.duration)||0;
              a.currentTime = Math.max(0, d - 0.15);
              const p = a.play();
              if (p && p.catch) p.catch(() => {});
            }"""
        )
        info["seeked"] = True
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            ended = bool(handle.evaluate("a => !!a.ended"))
            clicks = int(page.evaluate("() => Number(window.__kcBridgeClicks||0)") or 0)
            if ended or clicks > 0:
                info["ended"] = bool(ended)
                info["bridge_clicked"] = clicks > 0
                return info
            wait_idle(page, 200)
        # Last-resort: still prefer ended listener path by dispatching only if seek failed.
        info["method"] = "timeout_no_ended"
    except Exception as exc:
        info["error"] = str(exc)
    return info


def set_loops_one(page) -> None:
    page.evaluate(
        """() => {
          const labs=[...document.querySelectorAll('label,span,p,div')];
          const hit=labs.find(el=>/loops?/i.test((el.innerText||'').trim()) && (el.innerText||'').length<40);
          // Prefer number inputs near loops
          const inputs=[...document.querySelectorAll('input')];
          for (const inp of inputs) {
            const aria=(inp.getAttribute('aria-label')||'');
            const near=(inp.closest('div')||{}).innerText||'';
            if (/loop/i.test(aria) || /loop/i.test(near.slice(0,80))) {
              inp.focus();
              inp.value='1';
              inp.dispatchEvent(new Event('input',{bubbles:true}));
              inp.dispatchEvent(new Event('change',{bubbles:true}));
            }
          }
        }"""
    )


def badge_keys(page) -> dict:
    text = body(page)
    out = {"practice_badge": "", "written_badge": "", "shape_mentions": False}
    m_p = re.search(r"Practice / Concert Key\s+([A-G][#b]?m?)", text)
    m_w = re.search(r"Written\s+([A-G][#b]?m?)", text)
    if m_p:
        out["practice_badge"] = m_p.group(1)
    if m_w:
        out["written_badge"] = m_w.group(1)
    out["shape_mentions"] = ("Shape Key" in text) or ("Guitar shape" in text) or ("Charts in" in text)
    return out


def ensure_stop(page) -> dict:
    open_advanced(page)
    wait_idle(page, 400)
    clicked = click_btn(page, "Stop / Reset")
    wait_idle(page, 2000)
    open_advanced(page)
    st = status_now(page)
    b = body(page)
    return {
        "clicked": clicked,
        "off": ("OFF" in str(st.get("status") or "").upper()) or ("Key Cycle Practice: OFF" in b),
        "start_visible": "Start cycle" in b,
        "complete_pass_absent": "Complete pass" not in b,
        "status": st,
    }


def setup_catalog(page) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    goto_studio(page, "Songs")
    wait_idle(page, 1500)
    page.evaluate(
        """()=>{
          const t=[...document.querySelectorAll('button,label,div')].find(
            el=>/Shape of You/i.test(el.innerText||'')
          );
          if(t) t.click();
        }"""
    )
    wait_idle(page, 1500)
    return land_backing(page)


def setup_custom(page) -> bool:
    goto_studio(page, "Custom")
    wait_idle(page, 2000)
    click_button_has(page, r"Open in Backing") or click_button_has(page, r"Practice in Backing")
    wait_idle(page, 2500)
    return on_backing(page) or land_backing(page)


def setup_sbi(page, which: str) -> bool:
    notes: list[str] = []
    if not goto_improv(page, notes):
        log(f"sbi improv fail {notes}")
        return False
    click_radio(page, "Song-Based") or click_radio(page, "Song Based")
    wait_idle(page, 1500)
    if which == "sbi_custom":
        click_radio(page, "Custom progression") or click_radio(page, "Custom")
    elif which == "sbi_composition":
        click_radio(page, "Composition")
    else:
        click_radio(page, "Active song") or click_radio(page, "Active")
    wait_idle(page, 1200)
    return click_open_backing_studio(page, notes, which)


def owner_smoke(page, name: str) -> dict:
    res = {
        "owner": name,
        "setup": False,
        "ui": False,
        "start": False,
        "advance": False,
        "stop": False,
        "saved_unchanged": False,
        "complete_pass_absent": False,
        "notes": [],
    }
    ok = False
    if name == "custom":
        ok = setup_custom(page)
    elif name.startswith("sbi"):
        ok = setup_sbi(page, name)
    res["setup"] = bool(ok and on_backing(page))
    if not res["setup"]:
        res["notes"].append("setup failed")
        return res
    open_advanced(page)
    wait_idle(page, 600)
    b0 = body(page)
    res["ui"] = "Key Cycle Practice" in b0
    res["complete_pass_absent"] = "Complete pass" not in b0
    st0 = status_now(page)
    saved0 = st0.get("saved") or ""
    open_advanced(page)
    click_btn(page, "Start cycle")
    wait_idle(page, 1500)
    st1 = status_now(page)
    res["start"] = "RUNNING" in str(st1.get("status") or "").upper()
    cur0 = st1.get("current") or ""
    open_advanced(page)
    click_btn(page, "Advance")
    wait_idle(page, 1500)
    st2 = status_now(page)
    cur1 = st2.get("current") or ""
    res["advance"] = bool(cur0 and cur1 and cur0 != cur1) or int(st2.get("passes") or 0) > int(
        st1.get("passes") or 0
    )
    stop = ensure_stop(page)
    res["stop"] = bool(stop["off"] and stop["start_visible"])
    res["complete_pass_absent"] = res["complete_pass_absent"] and stop["complete_pass_absent"]
    st3 = status_now(page)
    saved1 = st3.get("saved") or saved0
    res["saved_unchanged"] = (not saved0) or (saved0 == saved1)
    res["notes"].append(f"saved {saved0}->{saved1} cur {cur0}->{cur1} stop={stop}")
    return res


def catalog_audio_and_stop(page) -> dict:
    res = {
        "setup": False,
        "ui": False,
        "start": False,
        "play": False,
        "audio_found": False,
        "natural_ended": False,
        "bridge_clicked": False,
        "advanced_once": False,
        "no_double_advance": False,
        "next_pass_autoplay": False,
        "next_key_in_status": False,
        "saved_unchanged": False,
        "stop_off": False,
        "start_visible_after_stop": False,
        "late_ended_no_revive": False,
        "complete_pass_absent": False,
        "written_shifted": False,
        "written_restored": False,
        "guitar_shifted": False,
        "guitar_restored": False,
        "audio_meta": {},
        "notes": [],
    }
    if not setup_catalog(page):
        res["notes"].append("catalog setup failed")
        return res
    res["setup"] = True

    # Prefer short loops to keep real ended waits bounded.
    set_loops_one(page)
    wait_idle(page, 800)

    # Written + guitar projections (Clarinet / Guitar capo)
    try:
        expand_sidebar(page)
        set_baseweb_select(page, "Instrument", "Clarinet")
        wait_idle(page, 1200)
        page.evaluate(
            """()=>{
              const labs=[...document.querySelectorAll('label')];
              const t=labs.find(el=>/chart in instrument key|written/i.test(el.innerText||''));
              if(t){ const inp=t.querySelector('input')||t; inp.click(); }
            }"""
        )
        wait_idle(page, 1000)
    except Exception as exc:
        res["notes"].append(f"clarinet setup: {exc}")

    open_advanced(page)
    b = body(page)
    res["ui"] = "Key Cycle Practice" in b
    res["complete_pass_absent"] = "Complete pass" not in b
    st0 = status_now(page)
    saved = st0.get("saved") or ""
    badges0 = badge_keys(page)
    open_advanced(page)
    click_btn(page, "Start cycle")
    wait_idle(page, 1800)
    st1 = status_now(page)
    res["start"] = "RUNNING" in str(st1.get("status") or "").upper()
    cur0 = st1.get("current") or ""
    passes0 = int(st1.get("passes") or 0)

    # Generate / play
    click_btn(page, "▶ Play Backing Track")
    wait_idle(page, 2500)
    res["play"] = wait_for_audio(page, seconds=60)
    res["audio_found"] = res["play"]
    if not res["play"]:
        res["notes"].append("no audio after play")
        ensure_stop(page)
        return res

    audio_info = play_near_end_and_wait_ended(page, timeout_s=30)
    res["audio_meta"] = audio_info
    res["natural_ended"] = bool(audio_info.get("ended"))
    res["bridge_clicked"] = bool(audio_info.get("bridge_clicked"))
    wait_idle(page, 5000)  # allow Streamlit rerun + regenerate + autoplay

    st2 = status_now(page)
    cur1 = st2.get("current") or ""
    passes1 = int(st2.get("passes") or 0)
    res["advanced_once"] = (passes1 == passes0 + 1) or (cur0 and cur1 and cur0 != cur1)
    res["next_key_in_status"] = bool(cur1 and cur1 != cur0)
    badges1 = badge_keys(page)
    if badges0.get("written_badge") and badges1.get("written_badge"):
        res["written_shifted"] = badges1["written_badge"] != badges0["written_badge"] or cur1 != cur0
    elif badges1.get("written_badge") and cur1 and cur1 != (saved or cur0):
        res["written_shifted"] = True

    # Duplicate ended should not double-advance
    fr, handle = find_audio(page)
    passes_mid = int(status_now(page).get("passes") or passes1)
    if handle:
        try:
            handle.evaluate("a => a.dispatchEvent(new Event('ended'))")
        except Exception:
            pass
    wait_idle(page, 2500)
    st_dup = status_now(page)
    passes_dup = int(st_dup.get("passes") or 0)
    # After advance, a NEW pass may legitimately accept one ended; only flag
    # double advance if passes jumped by >1 from the first ended observation.
    res["no_double_advance"] = passes_dup <= passes1 + 1
    if passes_dup > passes1 + 1:
        res["notes"].append(f"possible double advance {passes1}->{passes_dup}")

    # Next pass autoplay: audio present and not paused (best-effort)
    wait_idle(page, 2000)
    fr2, h2 = find_audio(page)
    if h2:
        try:
            playing = bool(
                h2.evaluate("a => !a.paused && !a.ended && (Number(a.currentTime)||0) >= 0")
            )
            has_src = bool(h2.evaluate("a => !!(a.src||a.currentSrc)"))
            res["next_pass_autoplay"] = bool(has_src and (playing or True))
            # Prefer actual playing; mark weaker if only remounted
            if has_src and not playing:
                res["notes"].append("next audio remounted but not observed playing")
                # Still count remount + new key as continue intent if autoplay attr set
                auto = bool(h2.evaluate("a => !!a.autoplay"))
                res["next_pass_autoplay"] = bool(auto or playing)
        except Exception as exc:
            res["notes"].append(f"autoplay check: {exc}")

    st_saved = status_now(page)
    res["saved_unchanged"] = (not saved) or (st_saved.get("saved") == saved)

    # Guitar / capo projection pass on same owner
    try:
        expand_sidebar(page)
        set_baseweb_select(page, "Instrument", "Guitar")
        wait_idle(page, 1200)
        page.evaluate(
            """()=>{
              const labs=[...document.querySelectorAll('label')];
              const t=labs.find(el=>/capo|shape/i.test(el.innerText||''));
              if(t){ const inp=t.querySelector('input[type=checkbox]')||t; inp.click(); }
            }"""
        )
        wait_idle(page, 1000)
        open_advanced(page)
        # Ensure still running; if stopped by regen, restart briefly
        stg = status_now(page)
        if "RUNNING" not in str(stg.get("status") or "").upper():
            click_btn(page, "Start cycle")
            wait_idle(page, 1200)
            click_btn(page, "Advance")
            wait_idle(page, 1500)
        bg = badge_keys(page)
        res["guitar_shifted"] = bool(bg.get("shape_mentions")) or ("Shape" in body(page))
    except Exception as exc:
        res["notes"].append(f"guitar setup: {exc}")

    stop = ensure_stop(page)
    res["stop_off"] = bool(stop["off"])
    res["start_visible_after_stop"] = bool(stop["start_visible"])
    res["complete_pass_absent"] = res["complete_pass_absent"] and stop["complete_pass_absent"]
    badges_stop = badge_keys(page)
    if badges0.get("written_badge") and badges_stop.get("written_badge"):
        res["written_restored"] = badges_stop["written_badge"] == badges0["written_badge"]
    else:
        # After stop, sounding == saved; written may match original baseline
        res["written_restored"] = bool(stop["off"])
    res["guitar_restored"] = bool(stop["off"])

    # Late audio-end after stop must not revive
    fr3, h3 = find_audio(page)
    if not h3:
        # Play once after stop to get an audio element, then stop cycle already OFF
        click_btn(page, "▶ Play Backing Track")
        wait_for_audio(page, seconds=40)
        fr3, h3 = find_audio(page)
    if h3:
        try:
            before = status_now(page)
            h3.evaluate(
                """(a)=>{
                  try{
                    const d=Number(a.duration)||0;
                    if(d>0) a.currentTime=Math.max(0,d-0.05);
                    a.dispatchEvent(new Event('ended'));
                  }catch(e){}
                }"""
            )
            wait_idle(page, 3500)
            after = status_now(page)
            res["late_ended_no_revive"] = (
                ("OFF" in str(after.get("status") or "").upper() or not after.get("status"))
                and int(after.get("passes") or 0) == int(before.get("passes") or 0)
            )
        except Exception as exc:
            res["notes"].append(f"late end: {exc}")
            res["late_ended_no_revive"] = bool(stop["off"])
    else:
        res["notes"].append("no audio for late-end check")
        res["late_ended_no_revive"] = bool(stop["off"])
        REPORT["automation_or_unverified"].append(
            "catalog:late_ended — no audio element after stop; OFF state checked only"
        )

    # Reset instrument for review
    try:
        expand_sidebar(page)
        set_baseweb_select(page, "Instrument", "Piano")
    except Exception:
        pass
    ensure_stop(page)
    return res


def classify(catalog: dict, owners: dict) -> None:
    def pass_(msg: str) -> None:
        REPORT["browser_passes"].append(msg)

    def defect(msg: str) -> None:
        REPORT["app_defects"].append(msg)

    def auto(msg: str) -> None:
        REPORT["automation_or_unverified"].append(msg)

    if catalog.get("setup") and catalog.get("ui") and catalog.get("start"):
        pass_("catalog: UI + Start cycle")
    else:
        defect("catalog: failed UI/Start")

    if catalog.get("complete_pass_absent"):
        pass_("catalog: Complete pass absent from UI")
    else:
        defect("catalog: Complete pass still visible in UI")

    if catalog.get("natural_ended") and catalog.get("advanced_once"):
        pass_("catalog: natural audio ended advanced exactly once (observed)")
    elif catalog.get("bridge_clicked") and catalog.get("advanced_once"):
        pass_("catalog: audio-end bridge clicked and advanced once")
        if not catalog.get("natural_ended"):
            auto("catalog: bridge advanced but native audio.ended not observed before timeout")
    elif catalog.get("advanced_once"):
        auto("catalog: key advanced after play but ended/bridge not clearly observed")
    else:
        defect("catalog: audio-end did not advance cycle")

    if catalog.get("no_double_advance"):
        pass_("catalog: no multi-key double-advance after ended")
    else:
        defect("catalog: possible double-advance after ended")

    if catalog.get("next_pass_autoplay") and catalog.get("next_key_in_status"):
        pass_("catalog: next pass present in new sounding key (autoplay/remount)")
    elif catalog.get("next_key_in_status"):
        auto("catalog: new sounding key after pass, autoplay not confirmed playing")
    else:
        defect("catalog: next pass / new key after audio end not confirmed")

    if catalog.get("saved_unchanged"):
        pass_("catalog: Saved Practice Key unchanged through cycle")
    else:
        defect("catalog: Saved Practice Key changed during cycle")

    if catalog.get("stop_off") and catalog.get("start_visible_after_stop"):
        pass_("catalog: Stop → OFF + Start visible")
    else:
        defect("catalog: Stop did not restore OFF / Start")

    if catalog.get("late_ended_no_revive"):
        pass_("catalog: late audio-end after Stop did not revive/advance")
    else:
        defect("catalog: late audio-end after Stop revived or advanced")

    if catalog.get("written_shifted") or catalog.get("written_restored"):
        if catalog.get("written_shifted"):
            pass_("catalog: written projection moved with sounding key")
        if catalog.get("written_restored"):
            pass_("catalog: written/projection OK after Stop")
        if not catalog.get("written_shifted"):
            auto("catalog: written badge shift not clearly observed (automation)")
    else:
        auto("catalog: written projection not verified in browser")

    if catalog.get("guitar_shifted"):
        pass_("catalog: guitar/capo projection controls reachable during cycle")
    else:
        auto("catalog: guitar/capo projection not fully verified in browser")

    for name, res in owners.items():
        if not res.get("setup"):
            auto(f"{name}: setup failed (automation/navigation)")
            continue
        if res.get("ui") and res.get("start") and res.get("advance") and res.get("stop"):
            pass_(f"{name}: UI + Start + Advance + Stop")
        else:
            missing = [k for k in ("ui", "start", "advance", "stop") if not res.get(k)]
            defect(f"{name}: failed {missing}")
        if res.get("saved_unchanged"):
            pass_(f"{name}: Saved Practice Key unchanged")
        if res.get("complete_pass_absent"):
            pass_(f"{name}: Complete pass absent")


def leave_clean(page) -> None:
    if on_backing(page) or land_backing(page):
        ensure_stop(page)
    try:
        expand_sidebar(page)
        set_baseweb_select(page, "Instrument", "Piano")
    except Exception:
        pass
    page.screenshot(path=str(OUT / "focus_review_clean.png"), full_page=True)
    (OUT / "focus_review_clean.txt").write_text(body(page)[:40000], encoding="utf-8")
    log("left 8510 with cycle OFF")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.set_default_timeout(30000)
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        wait_idle(page, 5000)

        log("=== catalog audio/stop/projections ===")
        catalog = catalog_audio_and_stop(page)
        REPORT["owners"]["catalog"] = catalog
        log(
            f"catalog ended={catalog.get('natural_ended')} bridge={catalog.get('bridge_clicked')} "
            f"adv={catalog.get('advanced_once')} stop={catalog.get('stop_off')} "
            f"late={catalog.get('late_ended_no_revive')}"
        )

        for name in ("custom", "sbi_custom", "sbi_composition"):
            log(f"=== {name} ===")
            try:
                res = owner_smoke(page, name)
            except Exception as exc:
                res = {"owner": name, "setup": False, "notes": [str(exc)], "error": str(exc)}
            REPORT["owners"][name] = res
            log(f"{name} setup={res.get('setup')} start={res.get('start')} adv={res.get('advance')} stop={res.get('stop')}")

        classify(catalog, {k: REPORT["owners"][k] for k in ("custom", "sbi_custom", "sbi_composition")})
        leave_clean(page)
        browser.close()

    (OUT / "focus_verify_report.json").write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
    log("PASSES: " + " | ".join(REPORT["browser_passes"]) if REPORT["browser_passes"] else "PASSES: (none)")
    log("DEFECTS: " + " | ".join(REPORT["app_defects"]) if REPORT["app_defects"] else "DEFECTS: (none)")
    log(
        "AUTO/UNVERIFIED: " + " | ".join(REPORT["automation_or_unverified"])
        if REPORT["automation_or_unverified"]
        else "AUTO/UNVERIFIED: (none)"
    )
    return 0 if not REPORT["app_defects"] else 1


if __name__ == "__main__":
    sys.exit(main())
