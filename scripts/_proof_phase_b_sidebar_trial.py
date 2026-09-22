"""Narrow Phase B addendum: visible SBI Custom sidebar must say Trial Song.

Does not re-run the full B1-B6 matrix. Inspects rendered sidebar text.

Usage:
  python scripts/_proof_phase_b_sidebar_trial.py http://127.0.0.1:8552
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
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8552"
OUT = SCRIPTS / "evidence-phase-b-sidebar-trial"
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
    wait_idle(page, int(sec * 1000))


def key_token(raw: str) -> str:
    t = str(raw or "").replace("♯", "#").replace("♭", "b").strip()
    m = re.search(r"([A-G](?:#|b)?m?)", t)
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
    try:
        labeled = str(
            page.evaluate(
                """() => {
                  const labeled = [...document.querySelectorAll('input, [role="combobox"]')].find((el) => {
                    const a = (el.getAttribute('aria-label') || '');
                    return /practice\\s*\\/?\\s*concert\\s*key/i.test(a);
                  });
                  return labeled ? String(labeled.value || labeled.textContent || '').trim() : '';
                }"""
            )
            or ""
        ).strip()
        if labeled:
            return key_token(labeled)
    except Exception:
        pass
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
        return same_key(pk_live(page), token)
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return bool(set_baseweb_select(page, "Practice / Concert Key", token))


def shot(page: Page, name: str) -> None:
    side = sidebar_text(page)
    main = main_text(page)
    (OUT / f"{name}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:12000]}\n\n=== MAIN ===\n{main[:20000]}",
        encoding="utf-8",
    )
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


def parse_active_song_banner(side: str) -> dict[str, str]:
    """Parse the visible Active Song sidebar card — not ?dev=1 dumps."""
    block = ""
    m = re.search(
        r"ACTIVE SONG\s*(.*?)(?:\n\s*(?:PAGES|SESSION|Music sidebar|Ask the Music|Key display diagnostics))",
        side,
        re.I | re.S,
    )
    if m:
        block = m.group(1)
    else:
        m2 = re.search(r"ACTIVE SONG(.{0,500})", side, re.I | re.S)
        block = m2.group(1) if m2 else side[:500]
    # Stop before Songs hub caption / key widgets when possible.
    block = re.split(r"\n\s*🎼\s*Songs\b|\n\s*Song Original Key|\n\s*Practice\s*/\s*Concert Key", block, maxsplit=1)[0]
    kind = ""
    title = ""
    if re.search(r"CUSTOM PROGRESSION", block, re.I):
        kind = "Custom Progression"
        tm = re.search(r"CUSTOM PROGRESSION\s*\n\s*([^\n]+)", block, re.I)
        title = (tm.group(1).strip() if tm else "")
    elif re.search(r"\bSONG\b", block, re.I):
        kind = "Song"
        tm = re.search(r"\bSONG\s*\n\s*([^\n]+)", block, re.I)
        title = (tm.group(1).strip() if tm else "")
    elif re.search(r"COMPOSITION", block, re.I):
        kind = "Composition"
        tm = re.search(r"COMPOSITION\s*\n\s*([^\n]+)", block, re.I)
        title = (tm.group(1).strip() if tm else "")
    return {"kind": kind, "title": title, "block": block.strip()[:400]}


def open_sbi(page: Page) -> bool:
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    expand_sidebar(page)
    expand_pages_nav(page)
    settle(page, 1)
    if not (click_nav(page, "Creative") or click_nav(page, "Creative Lab") or goto_studio(page, "Creative")):
        return False
    settle(page, 3)
    # Prefer Improvisation Lab entry when Creative lands on a non-SBI analyzer.
    # Analysis mode sits below large ?dev=1 dumps — query the live DOM, not truncated text.
    has_analysis = bool(
        page.evaluate(
            """() => /analysis\\s*mode/i.test((document.querySelector('[data-testid="stMain"]')||document.body).innerText||'')"""
        )
    )
    has_song_source = bool(
        page.evaluate(
            """() => /song\\s*source/i.test((document.querySelector('[data-testid="stMain"]')||document.body).innerText||'')"""
        )
    )
    log(f"open_sbi after creative analysis_mode={has_analysis} song_source={has_song_source}")
    if not has_song_source:
        switched = set_baseweb_select(
            page, "Analysis mode", "Improvisation Intelligence", prefer_sidebar=False
        ) or set_baseweb_select(page, "Analysis mode", "Improvisation Lab", prefer_sidebar=False)
        log(f"open_sbi analysis_mode_switch={switched}")
        settle(page, 3)
    click_radio(page, "Song-Based Improvisation") or click_radio(page, "Play Song-Based") or click_radio(
        page, "Song-Based"
    ) or click_button_has(page, r"Song-Based")
    settle(page, 3)
    if _sbi_source_controls_present(page):
        return True
    click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
    settle(page, 2)
    click_radio(page, "Play Song-Based") or click_radio(page, "Song-Based Improvisation") or click_radio(
        page, "Song-Based"
    )
    settle(page, 3)
    ok = _sbi_source_controls_present(page)
    if not ok:
        # Wait one more settle — Analysis mode switch often needs an extra Streamlit rerun.
        settle(page, 4)
        ok = _sbi_source_controls_present(page)
    if not ok:
        click_radio(page, "Song-Based Improvisation") or click_radio(page, "Play Song-Based")
        settle(page, 3)
        ok = _sbi_source_controls_present(page)
    if not ok:
        flags = page.evaluate(
            """() => {
              const hay = ((document.querySelector('[data-testid="stMain"]')||document.body).innerText||'');
              return {
                song_source: /song\\s*source/i.test(hay),
                custom_progression: /custom\\s*progression/i.test(hay),
                active_song: /active\\s*song/i.test(hay),
                song_based: /song-?based/i.test(hay),
                entry_jam: /entry\\s*&\\s*jam/i.test(hay),
                improv_intel: /improvisation\\s*intelligence/i.test(hay),
              };
            }"""
        )
        log(f"open_sbi miss flags={flags!r}")
        shot(page, "debug-open-sbi-miss")
    return ok


def _sbi_source_controls_present(page: Page) -> bool:
    main = main_text(page)
    if re.search(r"Song source", main, re.I) and re.search(r"Custom Progression", main, re.I):
        return True
    try:
        if page.get_by_role("radio", name=re.compile(r"Custom Progression", re.I)).count():
            return True
    except Exception:
        pass
    try:
        return bool(
            page.evaluate(
                """() => {
                  const root = document.querySelector('[data-testid="stMain"]') || document.body;
                  const hay = (root && root.innerText) || '';
                  if (!/song\\s*source/i.test(hay)) return false;
                  return /custom\\s*progression/i.test(hay) && /active\\s*song/i.test(hay);
                }"""
            )
        )
    except Exception:
        return False


def click_nested_sbi_source(page: Page, which: str) -> bool:
    needle = "Custom Progression" if which == "custom" else "Active song"
    # Click the visible label — Streamlit radio inputs are intercepted by <p>/<label>.
    try:
        labels = page.locator('[data-testid="stRadioOption"]').filter(has_text=re.compile(needle, re.I))
        if labels.count() > 0:
            lab = labels.first
            lab.scroll_into_view_if_needed()
            lab.click(timeout=8000, force=True)
            settle(page, 3)
            return True
    except Exception as exc:
        log(f"click_nested_sbi_source label={exc}")
    try:
        radios = page.get_by_role("radio", name=re.compile(needle, re.I))
        if radios.count() > 0:
            radios.first.scroll_into_view_if_needed()
            radios.first.click(timeout=8000, force=True)
            settle(page, 3)
            return True
    except Exception as exc:
        log(f"click_nested_sbi_source role={exc}")
    try:
        if set_baseweb_select(page, "Song source", needle, prefer_sidebar=False):
            settle(page, 3)
            return True
    except Exception as exc:
        log(f"click_nested_sbi_source select={exc}")
    clicked = bool(
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
    settle(page, 3)
    return clicked


def capture(page: Page, step: str) -> dict[str, object]:
    side = sidebar_text(page)
    main = main_text(page)
    banner = parse_active_song_banner(side)
    orig = key_token(original_key_caption(side))
    pk = pk_live(page)
    focus = ""
    for pat in (r"Practice Focus\s*·[^\n]{0,200}", r"🔍\s*Practice Focus[^\n]{0,200}"):
        fm = re.search(pat, main, re.I)
        if fm:
            focus = fm.group(0).strip()
            break
    # Prefer visible SBI card title over sidebar when inspecting main.
    card_title = ""
    for pat in (
        r"Trial Song",
        r"My Progression",
        r"Perfect\s+[—\-]",
    ):
        if re.search(pat, main, re.I):
            card_title = re.search(pat, main, re.I).group(0)  # type: ignore[union-attr]
            if "Trial" in card_title or "My Progression" in card_title:
                break
    # UUID / identity from ?dev dumps if present, else banner title.
    uuid = ""
    um = re.search(r"custom::[a-zA-Z0-9_\-]+", side + "\n" + main)
    if um:
        uuid = um.group(0)
    row = {
        "step": step,
        "banner_kind": banner["kind"],
        "banner_title": banner["title"],
        "banner_block": banner["block"],
        "original_key": orig,
        "practice_key": pk,
        "focus": focus,
        "card_has_trial": bool(re.search(r"Trial Song", main, re.I)),
        "card_has_my_progression": bool(re.search(r"My Progression", main, re.I)),
        "focus_has_trial": "Trial Song" in focus,
        "focus_has_sbi_custom": "SBI Custom" in focus,
        "focus_has_perfect": "Perfect" in focus and "Trial" not in focus,
        "custom_uuid": uuid,
        "deploy_sha": "",
    }
    dm = re.search(r"deployed_commit:\s*([0-9a-f]+)", side, re.I)
    if dm:
        row["deploy_sha"] = dm.group(1)
    log(
        f"[BOUND] {step} banner={banner['kind']!r}/{banner['title']!r} "
        f"orig={orig!r} pk={pk!r} focus={focus!r} uuid={uuid!r}"
    )
    return row


def require(step: str, field: str, ok: bool, detail: str, snap: dict[str, object]) -> None:
    if not ok:
        raise GateFail(step, field, detail, snap)


def activate_perfect(page: Page) -> None:
    if not goto_studio(page, "Songs") and not click_nav(page, "Songs"):
        raise GateFail("setup", "nav.songs", "could not open Songs", {})
    settle(page, 2)
    click_radio(page, "Catalog") or click_radio(page, "Song Selection")
    settle(page, 1)
    if not pick_song(page, NOTES, "Perfect", "Pop"):
        raise GateFail("setup", "catalog.perfect", "could not pick Perfect", {})
    settle(page, 2)


def main() -> int:
    meta = git_meta()
    log(json.dumps(meta))
    rc = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(20_000)
        page.set_default_navigation_timeout(180_000)
        try:
            # Prefer a lighter page — ?dev=1 dumps can crash Chromium on long walks.
            page.goto(f"{URL}/", wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 10000)
            settle(page, 4)
            log("page_loaded")

            activate_perfect(page)
            log("perfect_activated")
            if not open_sbi(page):
                raise GateFail("B_sidebar", "nav.sbi", "could not open SBI", {})
            log("sbi_opened")
            click_nested_sbi_source(page, "active")
            settle(page, 2)
            snap = capture(page, "perfect_active")
            if not same_key(str(snap["practice_key"]), "C"):
                if not set_pk(page, "C"):
                    raise GateFail("B_sidebar", "perfect.pk", f"could not set Perfect C ({snap['practice_key']!r})", snap)
                settle(page, 2)
                snap = capture(page, "perfect_active_c")
            require("B_sidebar", "perfect.orig", same_key(str(snap["original_key"]), "G"), f"orig {snap['original_key']!r}", snap)
            require("B_sidebar", "perfect.pk", same_key(str(snap["practice_key"]), "C"), f"pk {snap['practice_key']!r}", snap)
            RESULT["perfect_gc"] = {"status": "PASS", **snap}

            if not open_sbi(page):
                raise GateFail("B_sidebar", "nav.sbi_before_custom", "lost SBI before Custom click", snap)
            if not click_nested_sbi_source(page, "custom"):
                try:
                    radios = page.evaluate(
                        """() => [...document.querySelectorAll('[role="radiogroup"] label')]
                          .slice(0, 60)
                          .map((el) => (el.innerText || '').trim())
                          .filter(Boolean)"""
                    )
                    log(f"sbi.custom radios={radios!r}")
                except Exception as exc:
                    log(f"sbi.custom radio dump failed {exc}")
                raise GateFail("B_sidebar", "sbi.custom", "could not select SBI Custom", snap)
            settle(page, 4)
            snap = capture(page, "sbi_custom")
            shot(page, "01-sbi-custom-sidebar")
            require(
                "B_sidebar",
                "banner_kind",
                str(snap["banner_kind"]).lower().startswith("custom"),
                f"banner kind {snap['banner_kind']!r}",
                snap,
            )
            require(
                "B_sidebar",
                "banner_title",
                "Trial Song" in str(snap["banner_title"]),
                f"sidebar title still {snap['banner_title']!r} block={snap['banner_block']!r}",
                snap,
            )
            require(
                "B_sidebar",
                "banner_not_my_progression",
                "My Progression" not in str(snap["banner_title"]),
                f"sidebar still My Progression: {snap['banner_block']!r}",
                snap,
            )
            require("B_sidebar", "original_key", same_key(str(snap["original_key"]), "D"), f"orig {snap['original_key']!r}", snap)
            if not same_key(str(snap["practice_key"]), "F"):
                if not set_pk(page, "F"):
                    raise GateFail("B_sidebar", "practice_key", f"could not set Trial F ({snap['practice_key']!r})", snap)
                settle(page, 2)
                snap = capture(page, "sbi_custom_f")
                shot(page, "01b-sbi-custom-f")
            require("B_sidebar", "practice_key", same_key(str(snap["practice_key"]), "F"), f"pk {snap['practice_key']!r}", snap)
            require("B_sidebar", "card_trial", bool(snap["card_has_trial"]), "main card missing Trial Song", snap)
            require(
                "B_sidebar",
                "focus",
                bool(snap["focus_has_trial"]) and bool(snap["focus_has_sbi_custom"]),
                f"focus {snap['focus']!r}",
                snap,
            )
            RESULT["sbi_custom_live"] = {"status": "PASS", **snap}

            page.reload(wait_until="domcontentloaded")
            wait_idle(page, 8000)
            settle(page, 3)
            snap = capture(page, "sbi_custom_refresh")
            shot(page, "02-sbi-custom-refresh")
            require(
                "B_sidebar",
                "refresh.banner_title",
                "Trial Song" in str(snap["banner_title"]),
                f"refresh sidebar title {snap['banner_title']!r} block={snap['banner_block']!r}",
                snap,
            )
            require("B_sidebar", "refresh.orig", same_key(str(snap["original_key"]), "D"), f"refresh orig {snap['original_key']!r}", snap)
            require("B_sidebar", "refresh.pk", same_key(str(snap["practice_key"]), "F"), f"refresh pk {snap['practice_key']!r}", snap)
            require(
                "B_sidebar",
                "refresh.focus",
                bool(snap["focus_has_trial"]) and bool(snap["focus_has_sbi_custom"]),
                f"refresh focus {snap['focus']!r}",
                snap,
            )
            require("B_sidebar", "refresh.card", bool(snap["card_has_trial"]), "refresh card lost Trial", snap)
            RESULT["sbi_custom_refresh"] = {"status": "PASS", **snap}

            if not click_nested_sbi_source(page, "active"):
                raise GateFail("B_sidebar", "sbi.active", "could not return to SBI Active", snap)
            settle(page, 3)
            snap = capture(page, "return_active")
            shot(page, "03-return-active")
            require("B_sidebar", "return.orig", same_key(str(snap["original_key"]), "G"), f"return orig {snap['original_key']!r}", snap)
            require("B_sidebar", "return.pk", same_key(str(snap["practice_key"]), "C"), f"return pk {snap['practice_key']!r}", snap)
            require(
                "B_sidebar",
                "return.banner",
                "Perfect" in str(snap["banner_title"]) or str(snap["banner_kind"]) == "Song",
                f"return banner {snap['banner_kind']!r}/{snap['banner_title']!r}",
                snap,
            )
            RESULT["return_active"] = {"status": "PASS", **snap}

            page.reload(wait_until="domcontentloaded")
            wait_idle(page, 8000)
            settle(page, 3)
            snap = capture(page, "return_active_refresh")
            shot(page, "04-return-active-refresh")
            require("B_sidebar", "return_refresh.orig", same_key(str(snap["original_key"]), "G"), f"orig {snap['original_key']!r}", snap)
            require("B_sidebar", "return_refresh.pk", same_key(str(snap["practice_key"]), "C"), f"pk {snap['practice_key']!r}", snap)
            RESULT["return_active_refresh"] = {"status": "PASS", **snap}
        except GateFail as exc:
            rc = 1
            RESULT[exc.step] = {
                "status": "FAIL",
                "field": exc.field,
                "detail": exc.detail,
                "snap": exc.snap,
            }
            log(str(exc))
            try:
                shot(page, f"fail-{exc.step}")
            except Exception:
                pass
        except Exception as exc:
            rc = 1
            RESULT["crash"] = {"status": "FAIL", "detail": str(exc)}
            log(f"crash {exc}")
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
    payload = {"meta": meta, "result": RESULT, "notes": NOTES, "rc": rc}
    (OUT / "proof.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(json.dumps({"rc": rc, "gates": {k: (v.get("status") if isinstance(v, dict) else v) for k, v in RESULT.items()}}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
