"""Phase C Capo/Shape browser proof on persistent 8552.

Sequence: Perfect C + Shape C → refresh → SBI Custom Trial F/capo 5 → refresh →
Active Perfect open → Beat It Ebm/capo 3 → PK change → nav sticky → Off/On → leave Guitar.

Usage:
  python scripts/_proof_phase_c_capo_shape.py http://127.0.0.1:8552
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
ICONS = Path(r"C:\Users\danie\Documents\GitHub\AI-Music-Practice-Coach-icons\scripts")
sys.path[:0] = [str(SCRIPTS), str(ROOT), str(ICONS)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_radio,
    ensure_checkbox,
    expand_pages_nav,
    expand_sidebar,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import enable_guitar_capo, pick_song, set_shape_tonic  # noqa: E402
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_pass8_charts_capo import checkbox_state, capo_fret_token, shape_key_token  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8552"
OUT = SCRIPTS / "evidence-phase-c-capo-shape"
OUT.mkdir(parents=True, exist_ok=True)
RESULT: dict[str, object] = {}
NOTES: list[str] = []


class GateFail(Exception):
    def __init__(self, step: str, field: str, detail: str, snap: dict[str, object]):
        super().__init__(f"{step} FAIL first_incorrect={field} {detail}")
        self.step = step
        self.field = field
        self.detail = detail
        self.snap = snap


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "full": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def settle(page: Page, sec: float = 2.0) -> None:
    try:
        wait_idle(page, int(sec * 1000))
    except Exception as exc:
        log(f"settle skipped: {exc}")


def safe_reload(page: Page) -> Page:
    """Reload without killing the walk when Chromium drops the target."""
    try:
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 8000)
        settle(page, 3)
        return page
    except Exception as exc:
        log(f"reload failed ({exc}); cold goto")
        try:
            page.goto(f"{URL}/", wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 10000)
            settle(page, 4)
            return page
        except Exception as exc2:
            log(f"cold goto also failed: {exc2}")
            raise


def key_token(raw: str) -> str:
    t = str(raw or "").replace("♯", "#").replace("♭", "b").strip()
    m = re.search(r"([A-G](?:#|b)?m?)", t, re.I)
    return (m.group(1) if m else t).replace("major", "").replace("minor", "m").strip()


def same_key(a: str, b: str) -> bool:
    return key_token(a).upper() == key_token(b).upper()


def body_text(page: Page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def sidebar_text(page: Page) -> str:
    expand_sidebar(page)
    try:
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def main_text(page: Page) -> str:
    try:
        return page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        return body_text(page)


def pk_live(page: Page) -> str:
    expand_sidebar(page)
    raw = str(pk_val(page) or "").strip()
    if raw:
        return key_token(raw)
    return key_token(original_key_caption(body_text(page)))


def set_pk(page: Page, token: str) -> bool:
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    expand_sidebar(page)
    try:
        combo = page.get_by_role("combobox", name="Practice / Concert Key")
        if combo.count() == 0:
            return bool(set_baseweb_select(page, "Practice / Concert Key", token))
        combo.first.click(timeout=4000)
        page.wait_for_timeout(400)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(str(token), delay=30)
        page.wait_for_timeout(400)
        opt = page.locator('[role="option"]').filter(has_text=re.compile(rf"^{re.escape(token)}$", re.I))
        if opt.count() == 0:
            opt = page.locator('[role="option"]').filter(has_text=re.compile(re.escape(token), re.I))
        if opt.count() == 0:
            page.keyboard.press("Escape")
            return bool(set_baseweb_select(page, "Practice / Concert Key", token))
        opt.first.click(timeout=4000)
        settle(page, 3)
        return True
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return bool(set_baseweb_select(page, "Practice / Concert Key", token))


def sounding_token(side: str) -> str:
    m = re.search(r"Sounding Key:\s*([^\n]+)", side or "", re.I)
    return key_token(m.group(1) if m else "")


def shape_token(side: str) -> str:
    tok = shape_key_token(side or "")
    if tok:
        return key_token(tok)
    m = re.search(r"Shape Key:\s*([A-G](?:#|b)?)", side or "", re.I)
    return key_token(m.group(1) if m else "")


def fret_open(side: str) -> bool:
    text = side or ""
    if re.search(r"Capo Fret:\s*open", text, re.I):
        return True
    if re.search(r"Capo Fret:\s*0(?:\D|$)", text, re.I):
        return True
    if re.search(r"open \(no capo\)", text, re.I):
        return True
    tok = capo_fret_token(text)
    return bool(re.fullmatch(r"0|open(?:\s*\(.*\))?", tok or "", re.I))


def fret_is(side: str, n: int) -> bool:
    text = side or ""
    if re.search(rf"Capo Fret:\s*{n}(?:\D|$)", text, re.I):
        return True
    if re.search(rf"Capo:\s*{n}(?:st|nd|rd|th)?\s*fret", text, re.I):
        return True
    tok = capo_fret_token(text)
    return bool(re.fullmatch(rf"{n}(?:st|nd|rd|th)?(?:\s*fret)?", tok or "", re.I))


def shape_mode_on(page: Page) -> bool | None:
    expand_sidebar(page)
    return checkbox_state(page, "Capo Shape Mode")


def shot(page: Page, name: str) -> None:
    try:
        side = sidebar_text(page)
        main = main_text(page)
        (OUT / f"{name}.txt").write_text(
            f"=== SIDEBAR ===\n{side[:8000]}\n\n=== MAIN ===\n{main[:8000]}",
            encoding="utf-8",
        )
    except Exception as exc:
        log(f"shot text failed {name}: {exc}")
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception as exc:
        log(f"shot png failed {name}: {exc}")


def capture(page: Page, step: str) -> dict[str, object]:
    side = sidebar_text(page)
    main = main_text(page)
    row = {
        "step": step,
        "sounding": sounding_token(side),
        "shape": shape_token(side),
        "fret_token": capo_fret_token(side),
        "fret_open": fret_open(side),
        "shape_mode": shape_mode_on(page),
        "practice_key": pk_live(page),
        "has_capo_section": "Capo Shape Mode" in side or "Guitar Capo" in side,
        "instrument_guitar": bool(re.search(r"\bGuitar\b", side)),
        "sidebar_excerpt": side[:2500],
    }
    log(
        f"[CAPO] {step} sounding={row['sounding']!r} shape={row['shape']!r} "
        f"fret={row['fret_token']!r} open={row['fret_open']} mode={row['shape_mode']} pk={row['practice_key']!r}"
    )
    return row


def require(step: str, field: str, ok: bool, detail: str, snap: dict[str, object]) -> None:
    if not ok:
        raise GateFail(step, field, detail, snap)


def open_sbi(page: Page) -> bool:
    expand_pages_nav(page)
    for _ in range(3):
        if (
            click_nav(page, "Creative")
            or click_button_has(page, r"Creative")
            or goto_studio(page, "Creative")
        ):
            break
        settle(page, 1)
    settle(page, 3)
    body = body_text(page)
    if "Improvisation" not in body and "Song-Based" not in body and "Missions" not in body:
        # Force Improvisation Intelligence analysis mode
        set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence") or set_baseweb_select(
            page, "Analysis", "Improvisation Intelligence"
        )
        settle(page, 3)
    clicked = (
        click_radio(page, "Song-Based Improvisation")
        or click_radio(page, "Song-Based")
        or click_radio(page, "Entry & Jam")
        or click_button_has(page, r"Song-Based")
    )
    settle(page, 3)
    body = body_text(page)
    return clicked or "Song source" in body or "Custom Progression" in body or "Active song" in body


def click_nested_sbi_source(page: Page, which: str) -> bool:
    needle = "Custom Progression" if which == "custom" else "Active song"
    try:
        labels = page.locator('[data-testid="stRadioOption"]').filter(has_text=re.compile(needle, re.I))
        if labels.count() > 0:
            labels.first.scroll_into_view_if_needed()
            labels.first.click(timeout=8000, force=True)
            settle(page, 3)
            return True
    except Exception as exc:
        log(f"nested source label={exc}")
    try:
        radios = page.get_by_role("radio", name=re.compile(needle, re.I))
        if radios.count() > 0:
            radios.first.click(timeout=8000, force=True)
            settle(page, 3)
            return True
    except Exception as exc:
        log(f"nested source role={exc}")
    return bool(
        page.evaluate(
            """(needle) => {
              const n = String(needle || '').toLowerCase();
              const labels = [...document.querySelectorAll('[data-testid="stRadioOption"], label, [role="radio"]')];
              const match = labels.find((el) => {
                const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).toLowerCase();
                return t.includes(n);
              });
              if (!match) return false;
              match.scrollIntoView({block: 'center'});
              match.click();
              return true;
            }""",
            needle.lower(),
        )
    )


def activate_perfect(page: Page) -> None:
    if not pick_song(page, NOTES, "Perfect", "Pop"):
        raise GateFail("setup", "catalog.perfect", "could not pick Perfect", {})
    settle(page, 3)


def nav_chain_shape_sticky(page: Page) -> None:
    for label in ("Songs", "Creative"):
        expand_pages_nav(page)
        click_nav(page, label) or click_button_has(page, label)
        settle(page, 2)
    # Creative → Missions → Phrase/Motif → Backing
    click_radio(page, "Missions") or click_button_has(page, r"Missions")
    settle(page, 2)
    (
        click_radio(page, "Phrase")
        or click_radio(page, "Phrase & Motif")
        or click_radio(page, "Motif")
        or click_button_has(page, r"Phrase")
    )
    settle(page, 2)
    click_nav(page, "Backing") or click_button_has(page, r"Backing")
    settle(page, 3)


def main() -> int:
    meta = git_meta()
    RESULT["meta"] = meta
    log(f"meta={meta}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--disable-gpu", "--no-sandbox"],
        )
        context = browser.new_context(viewport={"width": 1400, "height": 960})
        page = context.new_page()
        try:
            page.goto(f"{URL}/", wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 10000)
            settle(page, 4)

            # --- C1: Guitar + Perfect Practice C + Shape C ON ---
            activate_perfect(page)
            if not set_instrument(page, "Guitar"):
                raise GateFail("C1", "instrument", "could not set Guitar", {})
            settle(page, 2)
            if not set_pk(page, "C"):
                raise GateFail("C1", "practice_key", "could not set Perfect Practice C", {})
            settle(page, 2)
            if not enable_guitar_capo(page, NOTES, "C"):
                # Fallback: checkbox + shape separately
                ensure_checkbox(page, "Capo Shape Mode", checked=True)
                settle(page, 2)
                set_shape_tonic(page, "C") or set_baseweb_select(page, "Shape Key", "C")
                settle(page, 3)
            if not same_key(pk_live(page), "C"):
                set_pk(page, "C")
                settle(page, 2)
            snap = capture(page, "C1_perfect_shape_c")
            require("C1", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require("C1", "sounding", same_key(str(snap["sounding"]), "C"), f"sounding {snap['sounding']!r}", snap)
            require("C1", "shape", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            require("C1", "fret_open", bool(snap["fret_open"]), f"fret {snap['fret_token']!r}", snap)
            RESULT["C1"] = {"status": "PASS", **{k: snap[k] for k in ("sounding", "shape", "fret_token", "shape_mode")}}
            shot(page, "01-perfect-shape-c")

            # --- C2: refresh retains ON / C / C / open ---
            page = safe_reload(page)
            snap = capture(page, "C2_refresh_perfect")
            require("C2", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require("C2", "sounding", same_key(str(snap["sounding"]), "C"), f"sounding {snap['sounding']!r}", snap)
            require("C2", "shape", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            require("C2", "fret_open", bool(snap["fret_open"]), f"fret {snap['fret_token']!r}", snap)
            RESULT["C2"] = {"status": "PASS", **{k: snap[k] for k in ("sounding", "shape", "fret_token", "shape_mode")}}
            shot(page, "02-refresh-perfect")

            # --- C3: temporary SBI Custom Trial Practice F ---
            if not open_sbi(page):
                raise GateFail("C3", "nav.sbi", "could not open SBI", snap)
            if not click_nested_sbi_source(page, "custom"):
                raise GateFail("C3", "sbi.custom", "could not select SBI Custom", snap)
            settle(page, 3)
            side = sidebar_text(page)
            main = main_text(page)
            if "Trial Song" not in side and "Trial Song" not in main:
                raise GateFail("C3", "trial_identity", "SBI Custom did not land Trial Song", {"side": side[:800]})
            # Prefer the card's Practice concert key path; set F until sounding follows.
            for attempt in range(3):
                if same_key(sounding_token(sidebar_text(page)), "F"):
                    break
                set_pk(page, "F")
                settle(page, 3)
            snap = capture(page, "C3_sbi_custom_f")
            require("C3", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require("C3", "sounding", same_key(str(snap["sounding"]), "F"), f"sounding {snap['sounding']!r}", snap)
            require("C3", "shape", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            require("C3", "fret_5", fret_is(str(snap["sidebar_excerpt"]), 5), f"fret {snap['fret_token']!r}", snap)
            RESULT["C3"] = {"status": "PASS", **{k: snap[k] for k in ("sounding", "shape", "fret_token", "shape_mode")}}
            shot(page, "03-sbi-custom-f")
            # Re-click Custom so Creative dirty/save stamps Trial before refresh
            # (Capo no longer force-saves over temporary Custom).
            click_nested_sbi_source(page, "custom")
            settle(page, 4)

            # --- C4: refresh in SBI Custom ---
            page = safe_reload(page)
            snap = capture(page, "C4_refresh_custom")
            require("C4", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require("C4", "sounding", same_key(str(snap["sounding"]), "F"), f"sounding {snap['sounding']!r}", snap)
            require("C4", "shape", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            require("C4", "fret_5", fret_is(str(snap["sidebar_excerpt"]), 5), f"fret {snap['fret_token']!r}", snap)
            RESULT["C4"] = {"status": "PASS", **{k: snap[k] for k in ("sounding", "shape", "fret_token", "shape_mode")}}
            shot(page, "04-refresh-custom")

            # --- C5: return Active Perfect → C / C / open ---
            if not open_sbi(page):
                raise GateFail("C5", "nav.sbi", "could not reopen SBI", snap)
            if not click_nested_sbi_source(page, "active"):
                raise GateFail("C5", "sbi.active", "could not select SBI Active", snap)
            settle(page, 3)
            # Ensure Perfect is still Active Global
            side = sidebar_text(page)
            if "Perfect" not in side:
                activate_perfect(page)
                open_sbi(page)
                click_nested_sbi_source(page, "active")
                settle(page, 2)
            if not same_key(pk_live(page), "C"):
                set_pk(page, "C")
                settle(page, 2)
            snap = capture(page, "C5_return_perfect")
            shot(page, "05-return-perfect")
            require("C5", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require("C5", "sounding", same_key(str(snap["sounding"]), "C"), f"sounding {snap['sounding']!r}", snap)
            require("C5", "shape", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            require("C5", "fret_open", bool(snap["fret_open"]), f"fret {snap['fret_token']!r}", snap)
            RESULT["C5"] = {"status": "PASS", **{k: snap[k] for k in ("sounding", "shape", "fret_token", "shape_mode")}}

            # --- C6: Beat It Eb minor + retained Shape C → capo 3 ---
            if not pick_song(page, NOTES, "Beat It", "Pop"):
                raise GateFail("C6", "catalog.beat_it", "could not pick Beat It", snap)
            settle(page, 4)
            # Original Ebm should hydrate; force if needed
            pk = pk_live(page)
            if not (same_key(pk, "Ebm") or same_key(pk, "Eb") or "eb" in pk.lower()):
                if not (set_pk(page, "Eb minor") or set_pk(page, "Ebm")):
                    raise GateFail("C6", "practice_key", f"could not land Eb minor (pk={pk!r})", snap)
                settle(page, 3)
            # Keep Shape Mode ON + Shape C
            ensure_checkbox(page, "Capo Shape Mode", checked=True)
            settle(page, 2)
            cur_shape = shape_token(sidebar_text(page))
            if not same_key(cur_shape, "C"):
                set_shape_tonic(page, "C") or set_baseweb_select(page, "Shape Key", "C")
                settle(page, 3)
            snap = capture(page, "C6_beat_it_ebm")
            shot(page, "06-beat-it-ebm")
            require("C6", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require(
                "C6",
                "sounding",
                same_key(str(snap["sounding"]), "Ebm")
                or same_key(str(snap["sounding"]), "Eb")
                or str(snap["sounding"]).lower().startswith("eb"),
                f"sounding {snap['sounding']!r}",
                snap,
            )
            require("C6", "shape", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            require("C6", "fret_3", fret_is(str(snap["sidebar_excerpt"]), 3), f"fret {snap['fret_token']!r}", snap)
            RESULT["C6"] = {"status": "PASS", **{k: snap[k] for k in ("sounding", "shape", "fret_token", "shape_mode")}}

            # --- C7: change Practice Key → sounding changes, Shape C, capo recalcs ---
            if not (set_pk(page, "F minor") or set_pk(page, "Fm") or set_pk(page, "F")):
                raise GateFail("C7", "practice_key", "could not change Beat It Practice Key", snap)
            settle(page, 3)
            snap = capture(page, "C7_pk_change")
            shot(page, "07-pk-change")
            require("C7", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require(
                "C7",
                "sounding",
                same_key(str(snap["sounding"]), "Fm")
                or same_key(str(snap["sounding"]), "F")
                or str(snap["sounding"]).lower().startswith("f"),
                f"sounding {snap['sounding']!r}",
                snap,
            )
            require("C7", "shape", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            require("C7", "fret_recalc", fret_is(str(snap["sidebar_excerpt"]), 5), f"fret {snap['fret_token']!r}", snap)
            RESULT["C7"] = {"status": "PASS", **{k: snap[k] for k in ("sounding", "shape", "fret_token", "shape_mode")}}

            # --- C8: Songs → Missions → Phrase/Motif → Backing + refresh ---
            nav_chain_shape_sticky(page)
            snap = capture(page, "C8_nav_chain")
            shot(page, "08-nav-chain")
            require("C8", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require("C8", "shape", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            page = safe_reload(page)
            snap = capture(page, "C8_nav_refresh")
            require("C8", "shape_mode_refresh", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require("C8", "shape_refresh", same_key(str(snap["shape"]), "C"), f"shape {snap['shape']!r}", snap)
            RESULT["C8"] = {"status": "PASS", **{k: snap[k] for k in ("sounding", "shape", "fret_token", "shape_mode")}}
            shot(page, "08b-nav-refresh")

            # --- C9: manual Shape Mode OFF survives refresh ---
            ensure_checkbox(page, "Capo Shape Mode", checked=False)
            settle(page, 3)
            snap = capture(page, "C9_manual_off")
            require("C9", "shape_mode", snap["shape_mode"] is False, f"mode={snap['shape_mode']}", snap)
            page = safe_reload(page)
            snap = capture(page, "C9_off_refresh")
            require("C9", "shape_mode_refresh", snap["shape_mode"] is False, f"mode={snap['shape_mode']}", snap)
            RESULT["C9"] = {"status": "PASS", "shape_mode": snap["shape_mode"]}
            shot(page, "09-manual-off")

            # --- C10: manual ON initializes from sounding; open capo; old C gone ---
            sounding_before = sounding_token(sidebar_text(page)) or key_token(pk_live(page))
            ensure_checkbox(page, "Capo Shape Mode", checked=True)
            settle(page, 4)
            snap = capture(page, "C10_manual_on")
            shot(page, "10-manual-on")
            require("C10", "shape_mode", snap["shape_mode"] is True, f"mode={snap['shape_mode']}", snap)
            require("C10", "fret_open", bool(snap["fret_open"]), f"fret {snap['fret_token']!r}", snap)
            # Shape should initialize from current sounding tonic — not resurrect sticky C
            # unless sounding tonic is itself C.
            snd = key_token(str(snap["sounding"]) or sounding_before)
            shp = key_token(str(snap["shape"]))
            snd_tonic = re.sub(r"m$", "", snd, flags=re.I)
            if not same_key(snd_tonic, "C"):
                require(
                    "C10",
                    "no_old_c",
                    not same_key(shp, "C"),
                    f"old C resurrected; sounding={snd!r} shape={shp!r}",
                    snap,
                )
            require(
                "C10",
                "shape_from_sounding",
                same_key(shp, snd_tonic) or same_key(shp, snd),
                f"shape {shp!r} not from sounding {snd!r}",
                snap,
            )
            RESULT["C10"] = {
                "status": "PASS",
                "sounding": snap["sounding"],
                "shape": snap["shape"],
                "fret_token": snap["fret_token"],
            }

            # --- C11: leave Guitar — Shape Mode UI may turn off / disappear ---
            if not set_instrument(page, "Piano"):
                raise GateFail("C11", "instrument", "could not leave Guitar", snap)
            settle(page, 3)
            snap = capture(page, "C11_leave_guitar")
            shot(page, "11-leave-guitar")
            mode = snap["shape_mode"]
            has_section = bool(snap["has_capo_section"])
            require(
                "C11",
                "non_guitar",
                mode is not True or not has_section,
                f"Shape Mode still ON for non-Guitar mode={mode} section={has_section}",
                snap,
            )
            RESULT["C11"] = {"status": "PASS", "shape_mode": mode, "has_capo_section": has_section}

            RESULT["overall"] = "PASS"
            log("PHASE_C_PASS")
            return 0
        except GateFail as exc:
            RESULT["overall"] = "FAIL"
            RESULT["fail"] = {
                "step": exc.step,
                "field": exc.field,
                "detail": exc.detail,
                "snap": {k: v for k, v in exc.snap.items() if k != "sidebar_excerpt"},
            }
            try:
                shot(page, f"FAIL-{exc.step}-{exc.field}")
            except Exception:
                pass
            log(str(exc))
            return 1
        except Exception as exc:
            RESULT["overall"] = "ERROR"
            RESULT["error"] = repr(exc)
            log(f"ERROR {exc!r}")
            try:
                shot(page, "FAIL-error")
            except Exception:
                pass
            return 2
        finally:
            (OUT / "result.json").write_text(json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
            (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
            context.close()
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
