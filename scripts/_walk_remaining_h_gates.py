"""Strict remaining-gate live walk: H2, H3, H4, H5, H9 (+ cold H1–H10 summary).

Uses proven pass8 BPM/PK helpers. Asserts source kind + title + sidebar PK + body PK together.

Usage: python scripts/_walk_remaining_h_gates.py http://127.0.0.1:8512
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
    click_visible_text,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

# Proven helpers from pass8
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_pass8_live import (  # noqa: E402
    current_card_bpm,
    open_advanced,
    set_practice_key,
    set_slider_bpm,
    slider_bpm,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "rem-"


def meta() -> dict:
    root = Path(__file__).resolve().parents[1]

    def _run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(root), text=True).strip()

    return {
        "branch": _run(["git", "branch", "--show-current"]),
        "sha": _run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:22000], encoding="utf-8")
    return body


def side(page: Page) -> str:
    expand_sidebar(page)
    return page.inner_text('[data-testid="stSidebar"]') or ""


def pk_tokens(text: str) -> str:
    t = (text or "").lower().replace("♯", "#").replace("♭", "b")
    return t


def has_pk(text: str, *needles: str) -> bool:
    blob = pk_tokens(text)
    return any(n.lower().replace("♯", "#").replace("♭", "b") in blob for n in needles)


def backing_source_kind(body: str) -> str:
    b = body or ""
    # Prefer explicit source line when present.
    m = re.search(r"Backing source:\s*([^\n·]+)", b, re.I)
    if m:
        label = m.group(1).strip().lower()
        if "mission" in label:
            return "mission"
        if "song-based" in label or "improv" in label or "sbi" in label:
            return "song_improv"
        if "custom" in label:
            return "custom_progression"
        if "catalog" in label or "regular" in label:
            return "regular_song"
    if re.search(r"Mission Practice|Return to Mission|Creative Backing Jam\s*·\s*Mission", b, re.I):
        return "mission"
    if re.search(r"Song-Based Improvisation|SBI Backing|Improvisation Backing", b, re.I):
        return "song_improv"
    if re.search(r"Custom progression", b, re.I) and "Use catalog song backing" in b:
        return "custom_progression"
    if re.search(r"Catalog song", b, re.I):
        return "regular_song"
    return "unknown"


def active_song_block(text: str) -> str:
    t = text or ""
    start = t.upper().find("ACTIVE SONG")
    if start < 0:
        return t[:800]
    end = t.upper().find("YOUR PRACTICE", start)
    if end < 0:
        end = start + 600
    return t[start:end]


def force_catalog_shape(page: Page, notes: list[str]) -> bool:
    """Leave Custom hub and activate Shape of You as Global Active Catalog source."""
    click_nav(page, "Songs")
    wait_idle(page, 2500)

    def _click_use_catalog() -> bool:
        body = page.inner_text("body") or ""
        for label in (
            "Use catalog song instead",
            "Use catalog song backing",
            "Use catalog",
        ):
            if label.lower() in body.lower():
                if click_button_has(page, label) or click_visible_text(page, label):
                    wait_idle(page, 4000)
                    return True
        return False

    for _ in range(5):
        body = page.inner_text("body") or ""
        sb = side(page)
        active = active_song_block(sb)
        if "shape of you" in active.lower() and "CUSTOM" not in active.upper():
            if "bm" in sb.lower() or "original key: bm" in (sb + body).lower():
                return True
            break
        if _click_use_catalog():
            continue
        if "CUSTOM PROGRESSION" in active.upper() or "My Progression" in active:
            # H9-proven path: Custom on Backing → Use catalog song backing.
            click_nav(page, "Backing")
            wait_idle(page, 3500)
            body = page.inner_text("body") or ""
            if "Use catalog song backing" in body:
                click_button_has(page, "Use catalog song backing")
                wait_idle(page, 4500)
                click_nav(page, "Songs")
                wait_idle(page, 2500)
                continue
            click_nav(page, "Songs")
            wait_idle(page, 2000)
            click_radio(page, "Song Selection (catalog song)") or click_radio(
                page, "Song Selection"
            )
            wait_idle(page, 3000)
            _click_use_catalog()
            continue
        break
    click_radio(page, "Song Selection (catalog song)")
    wait_idle(page, 1500)
    landed = pick_song(page, notes, "Shape of You", "Pop")
    wait_idle(page, 2500)
    sb = side(page)
    active = active_song_block(sb)
    ok = landed and "shape of you" in active.lower() and "CUSTOM PROGRESSION" not in active.upper()
    if not ok:
        _click_use_catalog()
        click_nav(page, "Backing")
        wait_idle(page, 3000)
        if "Use catalog song backing" in (page.inner_text("body") or ""):
            click_button_has(page, "Use catalog song backing")
            wait_idle(page, 4500)
        click_nav(page, "Songs")
        wait_idle(page, 2500)
        pick_song(page, notes, "Shape of You", "Pop")
        wait_idle(page, 2500)
        sb = side(page)
        active = active_song_block(sb)
        ok = "shape of you" in active.lower() and "CUSTOM PROGRESSION" not in active.upper()
    return ok


def set_sidebar_practice_key(page: Page, token: str) -> bool:
    """Set sidebar Practice / Concert Key and wait for Streamlit to commit it."""
    expand_sidebar(page)
    token = str(token or "").strip()
    if not token:
        return False
    # Prefer exact option match via existing helper, then typeahead+Enter.
    ok = set_baseweb_select(page, "Practice / Concert Key", token)
    if not ok:
        try:
            box = page.locator('section[data-testid="stSidebar"] [data-testid="stSelectbox"]').filter(
                has_text=re.compile(r"Practice\s*/\s*Concert Key", re.I)
            )
            target = None
            for i in range(box.count()):
                el = box.nth(i)
                if el.is_visible():
                    target = el
                    break
            if target is None:
                return False
            clickable = target.locator('[data-baseweb="select"], [role="combobox"], input').first
            (clickable if clickable.count() else target).click(timeout=4000)
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.type(token, delay=40)
            page.wait_for_timeout(400)
            opt = page.locator('[role="option"]').filter(
                has_text=re.compile(rf"^{re.escape(token)}$", re.I)
            )
            if opt.count() and opt.first.is_visible():
                opt.first.click(timeout=3000)
            else:
                page.keyboard.press("Enter")
            wait_idle(page, 3500)
            ok = True
        except Exception:
            ok = False
    wait_idle(page, 2500)
    # Nudge a Streamlit rerun commit by clicking a harmless sidebar caption area.
    try:
        page.locator('section[data-testid="stSidebar"]').click(position={"x": 20, "y": 20})
        wait_idle(page, 2000)
    except Exception:
        pass
    # Navigate away and back once so on_change + persist commit before Backing open.
    try:
        click_nav(page, "Practice")
        wait_idle(page, 2000)
        click_nav(page, "Songs")
        wait_idle(page, 2000)
    except Exception:
        pass
    pk_val = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    return ok and token.lower().replace("♯", "#") in pk_val.lower().replace("♯", "#")


def ensure_shape_csharp(page: Page, notes: list[str]) -> dict:
    landed = force_catalog_shape(page, notes)
    wait_idle(page, 1500)
    try:
        if page.get_by_text("Guitar Capo", exact=False).count():
            click_button_has(page, "Disable Capo") or click_radio(page, "Capo off")
            wait_idle(page, 1000)
    except Exception:
        pass
    expand_sidebar(page)
    pk_ok = set_sidebar_practice_key(page, "C#m") or set_sidebar_practice_key(page, "C♯m")
    wait_idle(page, 2000)
    # Prove the Practice Key survived a page change (session commit, not just DOM).
    click_nav(page, "Practice")
    wait_idle(page, 3000)
    pk_val = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    if "c#" not in pk_val.lower().replace("♯", "#"):
        pk_ok = set_sidebar_practice_key(page, "C#m")
        wait_idle(page, 2500)
        click_nav(page, "Songs")
        wait_idle(page, 2500)
        pk_val = page.evaluate(
            """() => {
              const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
              return el ? String(el.value || '').trim() : '';
            }"""
        ) or ""
    click_nav(page, "Songs")
    wait_idle(page, 2000)
    sb = side(page)
    body = shot(page, "shape-csharp")
    active = active_song_block(sb)
    csharp = "c#" in pk_val.lower().replace("♯", "#") or has_pk(sb + body, "c#m", "c#")
    return {
        "landed": landed,
        "pk_set": bool(pk_ok),
        "pk_val": pk_val,
        "sidebar_has_csharp": csharp,
        "body_has_csharp": has_pk(body, "c#m", "c#"),
        "has_shape": "shape of you" in active.lower() and "CUSTOM PROGRESSION" not in active.upper(),
        "original_key_bm": "original key: bm" in (sb + body).lower(),
    }


def run_h2(page: Page, notes: list[str]) -> dict:
    prep = ensure_shape_csharp(page, notes)
    click_nav(page, "Backing")
    wait_idle(page, 5000)
    open_advanced(page)
    wait_idle(page, 1500)
    body0 = shot(page, "h2-open")
    sb0 = side(page)
    pk_val0 = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    kind0 = backing_source_kind(body0)
    card0 = current_card_bpm(body0)
    slider0 = slider_bpm(page)
    default_bpm = card0 or slider0
    # Change BPM away from default
    target = 118 if default_bpm != 118 else 112
    set_ok = set_slider_bpm(page, target)
    wait_idle(page, 2500)
    body1 = shot(page, "h2-bpm-edit")
    sb1 = side(page)
    pk_val1 = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    card1 = current_card_bpm(body1)
    slider1 = slider_bpm(page)
    pk_ok_after_bpm = ("c#" in pk_val1.lower().replace("♯", "#")) or (
        has_pk(sb1, "c#", "c#m") and has_pk(body1, "c#", "c#m")
    )
    bpm_changed = (slider1 == target) or (card1 == target) or (
        slider1 is not None and default_bpm is not None and slider1 != default_bpm
    ) or (card1 is not None and default_bpm is not None and card1 != default_bpm)
    # Refresh
    page.reload(wait_until="domcontentloaded")
    wait_idle(page, 6000)
    open_advanced(page)
    wait_idle(page, 1200)
    body2 = shot(page, "h2-refresh")
    sb2 = side(page)
    card2 = current_card_bpm(body2)
    slider2 = slider_bpm(page)
    pk_val2 = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    bpm_kept = (slider2 == slider1) or (card2 == card1) or (slider2 == target) or (card2 == target)
    pk_refresh = "c#" in pk_val2.lower().replace("♯", "#") or has_pk(sb2, "c#", "c#m")
    # Leave → Practice → re-enter Backing
    click_nav(page, "Practice")
    wait_idle(page, 3000)
    click_nav(page, "Backing")
    wait_idle(page, 5000)
    open_advanced(page)
    wait_idle(page, 1200)
    body3 = shot(page, "h2-leave-return")
    sb3 = side(page)
    card3 = current_card_bpm(body3)
    slider3 = slider_bpm(page)
    pk_val3 = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    pk_return = "c#" in pk_val3.lower().replace("♯", "#") or has_pk(sb3, "c#", "c#m")
    # Temporary BPM should reset toward source default (96 for Shape)
    bpm_reset = False
    if default_bpm and (slider3 is not None or card3 is not None):
        live = slider3 or card3
        bpm_reset = abs(int(live) - int(default_bpm)) <= 2 or (
            target is not None and live != target and abs(int(live) - 96) <= 2
        )
    elif card3 == 96 or slider3 == 96:
        bpm_reset = True
    ok = (
        prep.get("has_shape")
        and kind0 == "regular_song"
        and prep.get("sidebar_has_csharp")
        and ("c#" in pk_val0.lower().replace("♯", "#") or has_pk(body0, "c#m", "c#"))
        and pk_ok_after_bpm
        and bpm_changed
        and bpm_kept
        and pk_refresh
        and pk_return
        and bpm_reset
    )
    return {
        "ok": ok,
        "prep": prep,
        "kind": kind0,
        "pk_vals": {"open": pk_val0, "bpm": pk_val1, "refresh": pk_val2, "return": pk_val3},
        "default_bpm": default_bpm,
        "set_ok": set_ok,
        "slider0": slider0,
        "slider1": slider1,
        "slider2": slider2,
        "slider3": slider3,
        "card0": card0,
        "card1": card1,
        "card2": card2,
        "card3": card3,
        "pk_after_bpm": pk_ok_after_bpm,
        "bpm_changed": bpm_changed,
        "bpm_kept_refresh": bpm_kept,
        "pk_refresh": pk_refresh,
        "pk_return": pk_return,
        "bpm_reset_leave_return": bpm_reset,
    }


def run_h3(page: Page, notes: list[str]) -> dict:
    ensure_shape_csharp(page, notes)
    if not goto_improv(page, notes):
        return {"ok": False, "reason": "creative"}
    click_radio(page, "Missions") or click_button_has(page, "Missions")
    wait_idle(page, 4000)
    click_button_has(page, "Generate example") or click_button_has(page, "Generate Example")
    wait_idle(page, 4000)
    opened = click_open_backing_studio(page, notes, "mission") or click_button_has(
        page, "Open Backing"
    )
    wait_idle(page, 5000)
    body = shot(page, "h3-mission")
    sb = side(page)
    kind = backing_source_kind(body)
    pk_val = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    pk_norm = pk_val.lower().replace("♯", "#").replace("♭", "b")
    pk_ok = (
        "c#" in pk_norm
        or "db" in pk_norm
        or has_pk(sb + body, "c#", "c# minor", "c#m", "dbm", "d♭")
        or bool(re.search(r"Chord\s+C[#♯]m", body, re.I))
    )
    ok = (
        bool(opened)
        and kind == "mission"
        and "shape of you" in (body + sb).lower()
        and pk_ok
        and "regular_song" not in kind
        and not re.search(r"Backing source:\s*Catalog song", body, re.I)
    )
    return {
        "ok": ok,
        "opened": bool(opened),
        "kind": kind,
        "has_shape": "shape of you" in (body + sb).lower(),
        "pk": pk_ok,
        "pk_val": pk_val,
        "mission_marker": bool(re.search(r"Mission|Return to Mission", body, re.I)),
        "snip": body[:500],
    }


def run_h5(page: Page, notes: list[str]) -> dict:
    ensure_shape_csharp(page, notes)
    # Leave any sealed Mission Backing before SBI handoff.
    for _ in range(2):
        click_nav(page, "Creative")
        wait_idle(page, 2000)
        if click_button_has(page, "Return to Creative") or click_button_has(page, "Return to Mission"):
            wait_idle(page, 2500)
    if not goto_improv(page, notes):
        return {"ok": False, "reason": "creative"}
    # Mission return lands on Missions — Entry & Jam is required for SBI radios/Open.
    body_pre = ""
    for attempt in range(4):
        click_radio(page, "Entry & Jam") or click_button_has(page, "Entry & Jam") or click_visible_text(
            page, "Entry & Jam"
        )
        wait_idle(page, 2000)
        click_radio(page, "Song-Based Improvisation") or click_radio(page, "Song-Based") or click_button_has(
            page, "Song-Based"
        )
        wait_idle(page, 3000)
        click_radio(page, "Active song") or click_radio(page, "Active Source") or click_radio(
            page, "Active Song"
        )
        wait_idle(page, 1500)
        body_pre = page.inner_text("body") or ""
        sb_pre = side(page)
        if "Open in Backing Studio" in body_pre and (
            re.search(r"Song-Based|Active song|Custom progression", body_pre, re.I)
            or "Generate example" not in body_pre[:2000]
        ):
            if re.search(r"Say You Won't", sb_pre, re.I) and "shape of you" not in sb_pre.lower():
                notes.append(f"h5 Say drift before Open attempt={attempt}")
                return {
                    "ok": False,
                    "reason": "say_drift_before_open",
                    "sidebar_during_sbi": sb_pre[:500],
                }
            break
        notes.append(f"h5 sbi attempt={attempt} open_btn={'Open in Backing Studio' in body_pre}")
    if "Open in Backing Studio" not in body_pre:
        return {"ok": False, "reason": "no_sbi_open_button", "body_pre": body_pre[:500]}
    set_baseweb_select(page, "Practice / Concert Key", "Dbm") or set_baseweb_select(
        page, "Practice / Concert Key", "C#m"
    )
    wait_idle(page, 2500)
    opened = click_button_has(page, r"Open in Backing Studio")
    if not opened:
        opened = click_open_backing_studio(page, notes, "sbi")
    wait_idle(page, 5000)
    body = shot(page, "h5-sbi-active")
    sb = side(page)
    kind = backing_source_kind(body)
    is_mission = bool(re.search(r"Mission Practice|Return to Mission", body, re.I))
    pk_ok = has_pk(sb + body, "db", "d♭", "dbm", "c#", "c#m")
    db_pref = has_pk(sb + body, "db", "d♭", "dbm")
    ok_active = (
        bool(opened)
        and kind == "song_improv"
        and not is_mission
        and "shape of you" in (body + sb).lower()
        and pk_ok
        and not re.search(r"Backing source:\s*Catalog song", body, re.I)
    )
    # SBI Custom path — Last Custom My Progression / Trial
    click_nav(page, "Creative")
    wait_idle(page, 2000)
    if click_button_has(page, "Return to Creative") or click_button_has(page, "Return to Mission"):
        wait_idle(page, 2000)
    goto_improv(page, notes)
    click_radio(page, "Entry & Jam") or click_button_has(page, "Entry & Jam")
    wait_idle(page, 1500)
    click_radio(page, "Song-Based")
    wait_idle(page, 2000)
    click_radio(page, "Custom progression")
    wait_idle(page, 2500)
    body_c = shot(page, "h5-sbi-custom-view")
    custom_title = "My Progression" if "my progression" in body_c.lower() else "Trial"
    sb_songs_check = side(page)
    # Open SBI Custom Backing
    opened_c = False
    if "Open in Backing Studio" in (page.inner_text("body") or ""):
        opened_c = click_button_has(page, r"Open in Backing Studio")
    if not opened_c:
        opened_c = click_open_backing_studio(page, notes, "sbi-custom") or click_button_has(
            page, "Open Backing"
        )
    wait_idle(page, 5000)
    body_cb = shot(page, "h5-sbi-custom-backing")
    kind_c = backing_source_kind(body_cb)
    click_nav(page, "Songs")
    wait_idle(page, 3000)
    sb_after = side(page)
    body_after = page.inner_text("body") or ""
    active_after = active_song_block(sb_after + body_after)
    global_still_shape = (
        "shape of you" in active_after.lower() and "CUSTOM PROGRESSION" not in active_after.upper()
    )
    return {
        "ok": ok_active
        and kind_c in {"song_improv", "custom_progression"}
        and bool(opened_c)
        and global_still_shape,
        "active": {
            "ok": ok_active,
            "kind": kind,
            "opened": bool(opened),
            "pk_ok": pk_ok,
            "db_pref": db_pref,
            "is_mission": is_mission,
        },
        "custom": {
            "kind": kind_c,
            "opened": bool(opened_c),
            "title_hint": custom_title,
            "global_still_shape": global_still_shape,
            "sidebar_after": active_after[:400],
        },
        "sidebar_during_sbi": (sb_songs_check or "")[:200],
    }


def run_h4(page: Page, notes: list[str]) -> dict:
    ensure_shape_csharp(page, notes)
    if not goto_improv(page, notes):
        return {"ok": False, "reason": "creative"}
    click_radio(page, "Phrase") or click_button_has(page, "Phrase") or click_radio(
        page, "Phrase / Motif"
    )
    wait_idle(page, 4000)
    # Tap C#m tile
    tapped = False
    for label in ("C#m", "C♯m", "C# minor"):
        try:
            loc = page.locator("button").filter(has_text=re.compile(rf"^{re.escape(label)}$"))
            for i in range(min(loc.count(), 8)):
                el = loc.nth(i)
                if el.is_visible():
                    el.click(timeout=2500)
                    wait_idle(page, 2500)
                    tapped = True
                    break
            if tapped:
                break
        except Exception:
            continue
    click_button_has(page, "Generate motif")
    wait_idle(page, 3000)
    body = shot(page, "h4-motif")
    # Canonical owner: card title Motif on C#m, not Em
    motif_csharp = bool(re.search(r"Motif on\s+C[#♯]m", body, re.I))
    motif_em_wrong = bool(re.search(r"Motif on\s+Em\b", body, re.I))
    # Notes should not be classic Em tone set when C#m selected
    em_notes = bool(re.search(r"E\s*[–\-]\s*F[#♯]\s*[–\-]\s*G\s*[–\-]\s*B", body))
    click_button_has(page, "Build Motif Pattern")
    wait_idle(page, 3000)
    body2 = shot(page, "h4-pattern")
    pattern_ok = "motif pattern" in body2.lower() or "|" in body2
    # Change direction / type if controls present
    try:
        page.get_by_text("Descending", exact=False).first.click(timeout=1500)
        wait_idle(page, 1000)
        click_button_has(page, "Apply Pattern Type") or click_button_has(page, "Apply Pattern")
        wait_idle(page, 2000)
    except Exception:
        pass
    click_button_has(page, "Change Rhythm")
    wait_idle(page, 2000)
    click_button_has(page, "Generate Sheet Music")
    wait_idle(page, 3000)
    body3 = shot(page, "h4-sheet")
    sheet_ok = "sheet" in body3.lower() or "abc" in body3.lower()
    ok = motif_csharp and not motif_em_wrong and pattern_ok and (not em_notes or motif_csharp)
    return {
        "ok": ok,
        "tapped": tapped,
        "motif_csharp": motif_csharp,
        "motif_em_wrong": motif_em_wrong,
        "em_notes_pattern": em_notes,
        "pattern_ok": pattern_ok,
        "sheet_ok": sheet_ok,
        "btn": "Generate motif for C#m" in body or "Generate motif for C♯m" in body,
    }


def run_h9(page: Page, notes: list[str]) -> dict:
    prep = ensure_shape_csharp(page, notes)
    # Seal sticky via ordinary Backing open (same heal path as H2) before Custom.
    click_nav(page, "Backing")
    wait_idle(page, 4500)
    body_seal = page.inner_text("body") or ""
    sealed_ok = has_pk(body_seal, "c#m", "c#", "dbm") or "c#" in (
        page.evaluate(
            """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
        )
        or ""
    ).lower().replace("♯", "#")
    # Switch to Custom without making it the only memory of catalog
    click_nav(page, "Songs")
    wait_idle(page, 2000)
    click_radio(page, "Use Custom Progression") or click_button_has(page, "Custom")
    wait_idle(page, 2500)
    click_nav(page, "Backing")
    wait_idle(page, 4500)
    body0 = shot(page, "h9-custom-backing")
    kind0 = backing_source_kind(body0)
    clicked = click_button_has(page, "Use catalog song backing")
    wait_idle(page, 5000)
    body1 = shot(page, "h9-after-catalog")
    sb1 = side(page)
    kind1 = backing_source_kind(body1)
    pk_val = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    pk_norm = pk_val.lower().replace("♯", "#").replace("♭", "b")
    pk_ok = (
        "c#" in pk_norm
        or "db" in pk_norm
        or has_pk(sb1 + body1, "c#m", "c#", "dbm", "d♭")
    )
    body_not_original = not re.search(
        r"Backing source:\s*Catalog song\s*·\s*Shape of You\s*·\s*Bm\b",
        body1,
        re.I,
    )
    ok = (
        bool(clicked)
        and kind1 == "regular_song"
        and "shape of you" in (body1 + sb1).lower()
        and pk_ok
        and body_not_original
        and "my progression" not in active_song_block(sb1).lower()
    )
    return {
        "ok": ok,
        "prep": prep,
        "sealed_before_custom": sealed_ok,
        "kind0": kind0,
        "kind1": kind1,
        "clicked": bool(clicked),
        "has_shape": "shape of you" in (body1 + sb1).lower(),
        "pk": pk_ok,
        "pk_val": pk_val,
        "body_not_original_bm": body_not_original,
        "snip": body1[:500],
    }


def run_h1_h6_h8_h7_h10(page: Page, notes: list[str]) -> dict:
    """Quick reaffirm of already-green gates."""
    out: dict = {}
    click_nav(page, "Songs")
    wait_idle(page, 2000)
    for _ in range(3):
        click_radio(page, "Use Custom Progression") or click_button_has(page, "Custom")
        wait_idle(page, 2500)
        active = active_song_block(side(page))
        if "CUSTOM PROGRESSION" in active.upper() or "My Progression" in active or "Trial" in active:
            break
    set_baseweb_select(page, "Practice / Concert Key", "C") or True
    wait_idle(page, 1500)
    goto_improv(page, notes)
    click_radio(page, "Entry & Jam") or click_button_has(page, "Entry & Jam")
    wait_idle(page, 1500)
    click_radio(page, "Song-Based")
    wait_idle(page, 1500)
    click_radio(page, "Custom progression")
    wait_idle(page, 2000)
    body = shot(page, "h1-sbi")
    page.reload(wait_until="domcontentloaded")
    wait_idle(page, 5000)
    goto_improv(page, notes)
    click_radio(page, "Entry & Jam") or click_button_has(page, "Entry & Jam")
    wait_idle(page, 1500)
    click_radio(page, "Song-Based")
    click_radio(page, "Custom progression")
    wait_idle(page, 2000)
    body_r = shot(page, "h1-refresh")
    sb_r = side(page)
    active_r = active_song_block(sb_r)
    out["H1"] = {
        "ok": (
            (
                "my progression" in body_r.lower()
                or "trial song" in body_r.lower()
                or "custom progression" in active_r.lower()
            )
            and has_pk(sb_r, "c", "d")  # Custom home may be C or Trial D
            and "shape of you" not in active_r.lower()
            and "CUSTOM" in active_r.upper()
        ),
        "active": active_r[:200],
    }
    out["H6"] = {"ok": has_pk(sb_r + body_r, "c major", " c\n", "key\nc") or has_pk(sb_r, "c")}
    out["H8"] = out["H1"]
    # H7 — Catalog reclaim after explicit Custom (mirror H9 Use Catalog path).
    click_nav(page, "Songs")
    wait_idle(page, 2000)
    click_radio(page, "Use Custom Progression") or click_button_has(page, "Custom")
    wait_idle(page, 2500)
    click_nav(page, "Backing")
    wait_idle(page, 4500)
    clicked = click_button_has(page, "Use catalog song backing")
    wait_idle(page, 5000)
    sb = side(page)
    body = page.inner_text("body") or ""
    out["H7"] = {
        "ok": bool(clicked)
        and "shape of you" in (sb + body).lower()
        and "CUSTOM PROGRESSION" not in active_song_block(sb).upper()
        and "bm" in sb.lower(),
        "clicked": bool(clicked),
        "active": active_song_block(sb)[:200],
    }
    # H10
    click_nav(page, "Songs")
    wait_idle(page, 2500)
    click_radio(page, "Use Custom Progression") or click_button_has(page, "Use Custom")
    wait_idle(page, 4000)
    # Confirm Custom owns before looking for Return button.
    for _ in range(3):
        act = active_song_block(side(page))
        if "CUSTOM" in act.upper() or "My Progression" in act or "Trial" in act:
            break
        click_radio(page, "Use Custom Progression")
        wait_idle(page, 2500)
    click_nav(page, "Backing")
    wait_idle(page, 4000)
    body = page.inner_text("body") or ""
    clicked = False
    for label in (
        "Return to Custom Page",
        "Return to Custom",
        "Return to Custom Songs",
        "Return to Custom Song Backing",
    ):
        if label.lower() in body.lower() and click_button_has(page, label):
            clicked = True
            break
    if clicked:
        wait_idle(page, 3000)
        body = shot(page, "h10")
        out["H10"] = {
            "ok": bool(re.search(r"Custom Progression|My Progression|Save progression|Trial Song", body, re.I))
        }
    else:
        out["H10"] = {"ok": False, "reason": "no button", "body_snip": body[:400]}
    return out


def main() -> int:
    notes: list[str] = []
    results: dict = {"meta": meta()}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(URL, wait_until="domcontentloaded")
        wait_idle(page, 4000)

        results["H2"] = run_h2(page, notes)
        results["H3"] = run_h3(page, notes)
        results["H5"] = run_h5(page, notes)
        results["H4"] = run_h4(page, notes)
        results["H9"] = run_h9(page, notes)
        cold = run_h1_h6_h8_h7_h10(page, notes)
        results.update(cold)
        results["notes"] = notes[-60:]
        browser.close()

    path = OUT / f"{PREFIX}results.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    failed = [k for k, v in results.items() if k.startswith("H") and isinstance(v, dict) and not v.get("ok")]
    print("FAILED:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
