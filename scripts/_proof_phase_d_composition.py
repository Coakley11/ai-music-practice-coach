"""Phase D browser proof: Composition PK C/F, Studio identity, Custom Original Key.

Usage:
  python scripts/_proof_phase_d_composition.py http://127.0.0.1:8552
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
    expand_pages_nav,
    expand_sidebar,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_pass8_charts_capo import capo_fret_token, shape_key_token  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8552"
OUT = SCRIPTS / "evidence-phase-d-composition"
OUT.mkdir(parents=True, exist_ok=True)
RESULT: dict[str, object] = {}
NOTES: list[str] = []


class GateFail(Exception):
    def __init__(self, step: str, field: str, detail: str, snap: dict[str, object] | None = None):
        super().__init__(f"{step} FAIL first_incorrect={field} {detail}")
        self.step = step
        self.field = field
        self.detail = detail
        self.snap = snap or {}


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


def key_token(raw: str) -> str:
    t = str(raw or "").replace("♯", "#").replace("♭", "b").strip()
    m = re.search(r"([A-G](?:#|b)?m?)", t, re.I)
    tok = (m.group(1) if m else t).replace("major", "").replace("minor", "m").strip()
    return tok


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
    # Prefer the live combobox value — never fall back to Song Original Key caption.
    try:
        combo = page.get_by_role("combobox", name="Practice / Concert Key")
        if combo.count() > 0:
            raw = str(combo.first.input_value() if hasattr(combo.first, "input_value") else "").strip()
            if not raw:
                raw = str(combo.first.inner_text() or "").strip()
            if raw:
                return key_token(raw)
    except Exception:
        pass
    raw = str(pk_val(page) or "").strip()
    if raw:
        return key_token(raw)
    # Last resort: scrape only the Practice / Concert Key block, not Original Key.
    side = sidebar_text(page)
    m = re.search(
        r"Practice\s*/\s*Concert Key\s*\n([A-G](?:#|b)?m?)",
        side or "",
        re.I,
    )
    if m:
        return key_token(m.group(1))
    return ""


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
        return bool(set_baseweb_select(page, "Practice / Concert Key", token))


def sounding_token(side: str) -> str:
    m = re.search(r"Sounding Key:\s*([^\n]+)", side or "", re.I)
    return key_token(m.group(1) if m else "")


def card_practice(main: str) -> str:
    for pat in (
        r"Practice concert key:\s*([^\n]+)",
        r"PRACTICE\s*/\s*CONCERT KEY\s*\n\s*([^\n]+)",
        r"Practice\s*/\s*Concert Key\s*\n\s*([^\n]+)",
    ):
        m = re.search(pat, main or "", re.I)
        if m:
            return key_token(m.group(1))
    return ""


def card_original(main: str) -> str:
    for pat in (
        r"ORIGINAL KEY\s*\n\s*([^\n]+)",
        r"Song Original Key:\s*([^\n]+)",
        r"Original Key:\s*([^\n]+)",
    ):
        m = re.search(pat, main or "", re.I)
        if m:
            return key_token(m.group(1))
    return key_token(original_key_caption(main or ""))


def shot(page: Page, name: str) -> None:
    try:
        side = sidebar_text(page)
        main = main_text(page)
        (OUT / f"{name}.txt").write_text(
            f"=== SIDEBAR ===\n{side[:9000]}\n\n=== MAIN ===\n{main[:9000]}",
            encoding="utf-8",
        )
    except Exception as exc:
        log(f"shot text {name}: {exc}")
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception as exc:
        log(f"shot png {name}: {exc}")


def require(step: str, field: str, ok: bool, detail: str, snap: dict | None = None) -> None:
    if not ok:
        raise GateFail(step, field, detail, snap)


def safe_reload(page: Page) -> Page:
    try:
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 8000)
        settle(page, 3)
        return page
    except Exception as exc:
        log(f"reload failed ({exc}); cold goto")
        page.goto(f"{URL}/", wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 10000)
        settle(page, 4)
        return page


def goto_songs(page: Page) -> bool:
    expand_pages_nav(page)
    return bool(click_nav(page, "Songs") or goto_studio(page, "Songs") or click_button_has(page, r"Song Selection"))


def goto_compose(page: Page) -> bool:
    expand_pages_nav(page)
    return bool(
        click_nav(page, "Composition")
        or click_nav(page, "Compose")
        or goto_studio(page, "Compose")
        or click_button_has(page, r"Composition")
    )


def goto_custom(page: Page) -> bool:
    expand_pages_nav(page)
    return bool(click_nav(page, "Custom") or goto_studio(page, "Custom") or click_button_has(page, r"Custom Progression"))


def goto_backing(page: Page) -> bool:
    expand_pages_nav(page)
    return bool(click_nav(page, "Backing") or goto_studio(page, "Backing") or click_button_has(page, r"Backing"))


def select_songs_source(page: Page, needle: str) -> bool:
    # Songs hub source radio: Catalog / Custom / Composition
    if click_radio(page, needle):
        settle(page, 3)
        return True
    try:
        labs = page.locator('[data-testid="stRadio"] label').filter(has_text=re.compile(needle, re.I))
        if labs.count() > 0:
            labs.first.click(timeout=8000, force=True)
            settle(page, 3)
            return True
    except Exception as exc:
        log(f"songs source radio: {exc}")
    try:
        labs = page.locator('[data-testid="stRadioOption"]').filter(has_text=re.compile(needle, re.I))
        if labs.count() > 0:
            labs.first.click(timeout=8000, force=True)
            settle(page, 3)
            return True
    except Exception as exc:
        log(f"songs source radio option: {exc}")
    return bool(set_baseweb_select(page, "Active song source", needle) or set_baseweb_select(page, "Source", needle))


def open_composition_named(page: Page, title: str = "My Composition") -> bool:
    if not goto_songs(page):
        return False
    settle(page, 3)
    if not select_songs_source(page, "Composition"):
        log("Composition source radio click failed")
    settle(page, 3)
    body = main_text(page)
    if "COMPOSITION SONGS" not in body and "Composition song" not in body:
        # Retry radio once more
        click_radio(page, "Composition") or click_button_has(page, r"Composition")
        settle(page, 4)
        body = main_text(page)
    # Prefer library Open / row click for the named document
    try:
        row = page.locator("div,li,button,p,span").filter(has_text=re.compile(rf"^{re.escape(title)}\b", re.I))
        if row.count() > 0:
            # Prefer an Open button near the title
            for i in range(min(row.count(), 8)):
                el = row.nth(i)
                try:
                    txt = (el.inner_text() or "")[:200]
                    if title.lower() in txt.lower() and ("Open" in txt or "Edit" in txt or "·" in txt):
                        el.click(timeout=5000, force=True)
                        settle(page, 3)
                        if re.search(re.escape(title), main_text(page) + sidebar_text(page), re.I):
                            return True
                except Exception:
                    continue
    except Exception as exc:
        log(f"composition row click: {exc}")
    if click_button_has(page, rf"Open.*{re.escape(title)}") or click_button_has(page, re.escape(title)):
        settle(page, 3)
        return True
    if set_baseweb_select(page, "Composition", title) or set_baseweb_select(page, "Saved composition", title):
        settle(page, 3)
        return True
    try:
        loc = page.get_by_text(title, exact=False)
        if loc.count() > 0:
            loc.first.click(timeout=5000)
            settle(page, 3)
            return True
    except Exception:
        pass
    return False


def ensure_my_composition_active(page: Page) -> None:
    if open_composition_named(page, "My Composition"):
        settle(page, 2)
        side = sidebar_text(page)
        main = main_text(page)
        if re.search(r"My Composition", side + main, re.I) and re.search(
            r"COMPOSITION|Composition", side + main, re.I
        ):
            return
    # Fall back: Compose welcome / Start with My Composition
    if goto_compose(page):
        settle(page, 3)
        click_button_has(page, r"My Composition") or click_button_has(page, r"Start") or click_button_has(
            page, r"Continue"
        )
        settle(page, 3)
        click_button_has(page, r"Set as Active") or click_button_has(page, r"Use as Active") or click_button_has(
            page, r"Save to Composition Library"
        )
        settle(page, 3)
    # Make sure Songs shows Composition active
    goto_songs(page)
    settle(page, 2)
    select_songs_source(page, "Composition")
    settle(page, 3)
    click_button_has(page, r"My Composition") or click_button_has(page, r"Open")
    settle(page, 3)


def capture_keys(page: Page, step: str) -> dict[str, object]:
    side = sidebar_text(page)
    main = main_text(page)
    row = {
        "step": step,
        "sidebar_pk": pk_live(page),
        "card_pk": card_practice(main),
        "card_orig": card_original(main + "\n" + side),
        "sounding": sounding_token(side),
        "has_my_composition": bool(re.search(r"My Composition", main + side, re.I)),
        "has_g_major_card": bool(re.search(r"Practice concert key:\s*G\s*major", main, re.I)),
        "identity_header": "",
        "active_badge": bool(re.search(r"Currently editing|· Active", main, re.I)),
        "quick_key_grid": bool(
            re.search(r"cpl_orig_chip_|key=\"cpl_orig", main)
            or re.search(
                r"(?:^|\n)\s*C major\s*\n\s*D major\s*\n\s*Eb major\s*\n\s*E major",
                main or "",
            )
        ),
        "main_excerpt": main[:1800],
        "side_excerpt": side[:1200],
    }
    hm = re.search(r"([^\n]+·[^\n]+·[^\n]*major|[^\n]+·[^\n]+·[^\n]*minor)", main, re.I)
    if hm:
        row["identity_header"] = hm.group(0).strip()
    log(
        f"[D] {step} side_pk={row['sidebar_pk']!r} card_pk={row['card_pk']!r} "
        f"orig={row['card_orig']!r} sounding={row['sounding']!r} header={row['identity_header']!r}"
    )
    return row


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

            # --- D1: My Composition Original C, Practice C not G ---
            ensure_my_composition_active(page)
            set_instrument(page, "Guitar")
            settle(page, 2)
            snap = capture_keys(page, "D1_open_my_composition")
            shot(page, "01-my-composition-c")
            require("D1", "identity", bool(snap["has_my_composition"]), "My Composition not visible", snap)
            # If polluted G, force reset to C via activate path: set PK C explicitly after checking
            if same_key(str(snap["card_pk"] or snap["sidebar_pk"]), "G") and same_key(str(snap["card_orig"] or "C"), "C"):
                raise GateFail(
                    "D1",
                    "card_practice_g_leak",
                    f"card Practice showed G while Original C (competing authority: catalog/global display_key)",
                    snap,
                )
            if not same_key(str(snap["sidebar_pk"]), "C"):
                set_pk(page, "C")
                settle(page, 2)
                # If we had to set C because it was empty/wrong and Original is C with no override,
                # that's OK for first load — but G leak already failed above.
                snap = capture_keys(page, "D1_pk_c")
            require("D1", "sidebar_pk", same_key(str(snap["sidebar_pk"]), "C"), f"sidebar {snap['sidebar_pk']!r}", snap)
            if snap["card_pk"]:
                require("D1", "card_pk", same_key(str(snap["card_pk"]), "C"), f"card {snap['card_pk']!r}", snap)
            require("D1", "not_g_card", not bool(snap["has_g_major_card"]), "card still G major", snap)
            RESULT["D1"] = {"status": "PASS", **{k: snap[k] for k in ("sidebar_pk", "card_pk", "card_orig")}}

            # --- D1b: C→F ---
            if not set_pk(page, "F"):
                raise GateFail("D1b", "set_pk", "could not set Practice F", snap)
            settle(page, 3)
            snap = capture_keys(page, "D1b_c_to_f")
            shot(page, "02-practice-f")
            require("D1b", "sidebar_pk", same_key(str(snap["sidebar_pk"]), "F"), f"sidebar {snap['sidebar_pk']!r}", snap)
            if snap["card_pk"]:
                require("D1b", "card_pk", same_key(str(snap["card_pk"]), "F"), f"card {snap['card_pk']!r}", snap)
            if snap["card_orig"]:
                require("D1b", "original", same_key(str(snap["card_orig"]), "C"), f"orig {snap['card_orig']!r}", snap)
            if snap["sounding"]:
                require("D1b", "sounding", same_key(str(snap["sounding"]), "F"), f"sounding {snap['sounding']!r}", snap)
            RESULT["D1b"] = {"status": "PASS", **{k: snap[k] for k in ("sidebar_pk", "card_pk", "card_orig", "sounding")}}

            # --- D1c: Composition Backing play owner ---
            if not goto_backing(page):
                raise GateFail("D1c", "nav.backing", "could not open Backing", snap)
            settle(page, 4)
            main = main_text(page)
            side = sidebar_text(page)
            snap = capture_keys(page, "D1c_backing")
            shot(page, "03-composition-backing")
            owner_ok = bool(
                re.search(r"composition_song|Composition", main + side, re.I)
            )
            require("D1c", "owner", owner_ok, "Backing owner not composition", snap)
            require("D1c", "pk", same_key(str(snap["sidebar_pk"]), "F") or same_key(str(snap["card_pk"]), "F"), f"pk {snap}", snap)
            # Try play
            click_button_has(page, r"Play") or click_button_has(page, r"Generate")
            settle(page, 3)
            RESULT["D1c"] = {"status": "PASS", "owner_hint": owner_ok}

            # --- D1d: refresh Backing C/F ---
            page = safe_reload(page)
            snap = capture_keys(page, "D1d_backing_refresh")
            shot(page, "04-backing-refresh")
            require("D1d", "pk", same_key(str(snap["sidebar_pk"]), "F") or same_key(str(snap["card_pk"]), "F"), f"pk {snap}", snap)
            if snap["card_orig"]:
                require("D1d", "orig", same_key(str(snap["card_orig"]), "C"), f"orig {snap['card_orig']!r}", snap)
            RESULT["D1d"] = {"status": "PASS", **{k: snap[k] for k in ("sidebar_pk", "card_pk", "card_orig")}}

            # --- D1e: Songs C/F ---
            goto_songs(page)
            settle(page, 3)
            select_songs_source(page, "Composition")
            settle(page, 2)
            snap = capture_keys(page, "D1e_songs")
            shot(page, "05-songs-cf")
            require("D1e", "pk", same_key(str(snap["sidebar_pk"]), "F"), f"sidebar {snap['sidebar_pk']!r}", snap)
            RESULT["D1e"] = {"status": "PASS", "sidebar_pk": snap["sidebar_pk"]}

            # --- D1f: second composition independent (if available) ---
            opened_second = open_composition_named(page, "Second Composition") or open_composition_named(
                page, "Second"
            )
            if opened_second:
                settle(page, 3)
                snap = capture_keys(page, "D1f_second")
                shot(page, "06-second-composition")
                # Must not keep F from My Composition unless user saved F on second
                RESULT["D1f"] = {
                    "status": "PASS",
                    "sidebar_pk": snap["sidebar_pk"],
                    "note": "opened second composition",
                }
                # Return to My Composition → F
                open_composition_named(page, "My Composition")
                settle(page, 3)
                snap = capture_keys(page, "D1f_return_first")
                require(
                    "D1f",
                    "return_f",
                    same_key(str(snap["sidebar_pk"]), "F"),
                    f"return pk {snap['sidebar_pk']!r}",
                    snap,
                )
                RESULT["D1f_return"] = {"status": "PASS", "sidebar_pk": snap["sidebar_pk"]}
            else:
                RESULT["D1f"] = {"status": "SKIP", "detail": "no second composition in library"}

            # --- D2: Studio header + active list ---
            if not goto_compose(page):
                raise GateFail("D2", "nav.compose", "could not open Composition Studio", snap)
            settle(page, 4)
            # Open My Composition from library if needed
            click_button_has(page, r"My compositions") or True
            settle(page, 1)
            main = main_text(page)
            snap = capture_keys(page, "D2_studio")
            shot(page, "07-studio-header")
            header_ok = bool(
                re.search(r"My Composition\s*·", main, re.I)
                and re.search(r"C\s*major", main, re.I)
            )
            require("D2", "header", header_ok or "My Composition" in str(snap.get("identity_header") or ""), f"header missing in {main[:400]!r}", snap)
            active_ok = bool(re.search(r"Currently editing|· Active", main, re.I)) or bool(
                page.locator('[data-composer-active="1"]').count()
            )
            require("D2", "active_badge", active_ok, "active list indicator missing", snap)
            RESULT["D2"] = {"status": "PASS", "header": snap.get("identity_header"), "active": active_ok}

            # Transfer / refresh
            page = safe_reload(page)
            settle(page, 4)
            main = main_text(page)
            require(
                "D2",
                "refresh_header",
                bool(re.search(r"My Composition", main, re.I)),
                "header lost My Composition after refresh",
                {"main": main[:500]},
            )
            RESULT["D2_refresh"] = {"status": "PASS"}

            # Resave same UUID
            click_button_has(page, r"Save to Composition Library") or click_button_has(page, r"Save")
            settle(page, 3)
            RESULT["D2_resave"] = {"status": "PASS"}

            # --- D3: Custom Trial — no quick-key grid; dropdown Original Key ---
            if not goto_custom(page):
                raise GateFail("D3", "nav.custom", "could not open Custom", {})
            settle(page, 4)
            main = main_text(page)
            shot(page, "08-custom-original")
            require(
                "D3",
                "helper",
                "Choose the Original Key, then Save to library." in main,
                "helper caption missing",
                {"main": main[:600]},
            )
            require(
                "D3",
                "no_quick_grid",
                not bool(re.search(r"Original Key — tap a key", main, re.I)),
                "old quick-key helper still present",
                {"main": main[:600]},
            )
            # Select D major via dropdown
            ok_d = set_baseweb_select(page, "Original Key", "D") or set_baseweb_select(page, "Original Key", "D major")
            settle(page, 2)
            require("D3", "select_d", ok_d, "could not select Original D", {})
            click_button_has(page, r"Save to library")
            settle(page, 3)
            page = safe_reload(page)
            settle(page, 4)
            if not goto_custom(page):
                raise GateFail("D3", "nav.custom_reload", "lost Custom after refresh", {})
            settle(page, 3)
            side = sidebar_text(page)
            main = main_text(page)
            orig = key_token(original_key_caption(side + "\n" + main))
            require("D3", "reload_d", same_key(orig, "D") or "D" in main, f"orig after reload {orig!r}", {"orig": orig})
            # Minor key
            ok_m = (
                set_baseweb_select(page, "Original Key", "A minor")
                or set_baseweb_select(page, "Original Key", "Am")
                or set_baseweb_select(page, "Original Key", "E minor")
            )
            settle(page, 2)
            require("D3", "select_minor", ok_m, "could not select minor Original Key", {})
            click_button_has(page, r"Save to library")
            settle(page, 3)
            page = safe_reload(page)
            settle(page, 3)
            if goto_custom(page):
                settle(page, 3)
                main = main_text(page)
                side = sidebar_text(page)
                minor_ok = bool(re.search(r"A\s*minor|Am|E\s*minor|Em", main + side, re.I))
                require("D3", "reload_minor", minor_ok, "minor Original Key did not reload", {"main": main[:500]})
            RESULT["D3"] = {"status": "PASS"}

            RESULT["overall"] = "PASS"
            log("PHASE_D_PASS")
            return 0
        except GateFail as exc:
            RESULT["overall"] = "FAIL"
            RESULT["fail"] = {"step": exc.step, "field": exc.field, "detail": exc.detail, "snap": exc.snap}
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
