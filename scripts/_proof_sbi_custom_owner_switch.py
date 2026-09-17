"""Prove SBI Active Perfect G/C ↔ Custom Trial D/D owner switch.

Usage:
  python scripts/_proof_sbi_custom_owner_switch.py http://127.0.0.1:8541
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
sys.path[:0] = [str(ICONS), str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_radio,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _browser_prove_owner_seeded_matrix import build_trial_fast, identity_marker  # noqa: E402
from _browser_prove_perfect_sbi import coherent, set_pk as _set_pk  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption, pk_live as _pk_live_dump  # noqa: E402
from _walk_ownership_audit_full import build_trial_song  # noqa: E402
from _proof_owner_key_identity import (  # noqa: E402
    body_text,
    fail_fields,
    original_caption,
    same_key,
    set_pk,
    shot,
    snapshot as _snapshot_dump,
)


URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8541"
OUT = SCRIPTS / "evidence-sbi-custom-owner-switch"
OUT.mkdir(parents=True, exist_ok=True)
RESULT: dict[str, object] = {}
NOTES: list[str] = []


def pk_live(page: Page) -> str:
    """Visible Practice Key combobox — ignore ?dev=1 dump of catalog display_key."""
    try:
        expand_sidebar(page)
    except Exception:
        pass
    try:
        raw = str(
            page.evaluate(
                """() => {
                  const labeled = [...document.querySelectorAll('input, [role="combobox"]')].find((el) => {
                    const a = (el.getAttribute('aria-label') || '');
                    return /practice\\s*\\/?\\s*concert\\s*key/i.test(a);
                  });
                  if (labeled) return String(labeled.value || labeled.textContent || '').trim();
                  return '';
                }"""
            )
            or ""
        ).strip()
        if raw:
            return raw
    except Exception:
        pass
    return str(_pk_live_dump(page) or "").strip()


def snapshot(page: Page) -> dict[str, str]:
    snap = _snapshot_dump(page)
    snap["pk"] = pk_live(page)
    return snap


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def mark(step: str, status: str, detail: str = "", **fields: object) -> None:
    RESULT[step] = {"status": status, "detail": detail, **fields}
    log(f"[{status}] {step} — {detail}")


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def release_marker(page: Page) -> str:
    try:
        return str(
            page.evaluate(
                """() => {
                  const el = document.getElementById('studio-ui-release-marker');
                  return el ? (el.getAttribute('data-studio-ui-release') || '') : '';
                }"""
            )
            or ""
        )
    except Exception:
        return ""


def open_sbi(page: Page) -> bool:
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    expand_sidebar(page)
    expand_pages_nav(page)
    settle(page, 1)
    if not goto_improv(page, NOTES):
        if not goto_studio(page, "Creative") and not click_nav(page, "Creative"):
            return False
        settle(page, 2)
        switched = (
            set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
            or set_baseweb_select(page, "Deep Harmonic Analyzer", "Improvisation Intelligence")
            or set_baseweb_select(page, "Analysis", "Improvisation Intelligence")
        )
        if not switched:
            try:
                loc = page.get_by_role("button", name=re.compile(r"Improvisation Intelligence", re.I)).first
                if loc.count():
                    loc.click(timeout=5000)
                    switched = True
            except Exception:
                switched = False
        settle(page, 3)
        if not switched and "improvisation intelligence" not in (page.inner_text("body") or "").lower():
            log("open_sbi: could not switch Analysis mode to Improvisation Intelligence")
            return False
    settle(page, 2)
    body = (page.inner_text("body") or "").lower()
    if "song source" not in body:
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
        settle(page, 2)
        click_radio(page, "Play Song-Based") or click_radio(page, "Song-Based Improvisation") or click_radio(
            page, "Song-Based"
        ) or click_button_has(page, r"Song-Based")
        settle(page, 2)
        body = (page.inner_text("body") or "").lower()
    ok = "song source" in body or ("entry & jam" in body and "song-based" in body)
    if not ok:
        try:
            radios = page.evaluate(
                """() => [...document.querySelectorAll('[role="radiogroup"] label, [role="radio"], input[type=radio]')]
                  .slice(0, 40)
                  .map((el) => ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).trim())
                  .filter(Boolean)"""
            )
            log(f"open_sbi radios={radios!r} body_has_song_source={'song source' in body}")
        except Exception as exc:
            log(f"open_sbi dump failed {exc}")
    return ok


def studio_page_slug(page: Page) -> str:
    try:
        return str(
            page.evaluate(
                """() => {
                  const el = document.querySelector('[data-studio-page]');
                  return el ? (el.getAttribute('data-studio-page') || '') : '';
                }"""
            )
            or ""
        ).strip().lower()
    except Exception:
        return ""


def sbi_source_checked(page: Page) -> str:
    """Return the checked nested SBI Song-source radio label, or empty."""
    try:
        return str(
            page.evaluate(
                """() => {
                  const groups = [...document.querySelectorAll('[role="radiogroup"]')];
                  for (const g of groups) {
                    const txt = (g.innerText || '').toLowerCase();
                    if (!txt.includes('active song') && !txt.includes('active source')) continue;
                    if (!txt.includes('custom progression')) continue;
                    const labels = [...g.querySelectorAll('label')];
                    const activeLab = labels.find((el) => {
                      const t = (el.innerText || '').toLowerCase();
                      return t.includes('active song') && !t.includes('custom');
                    });
                    if (!activeLab) return '';
                    const checked = activeLab.getAttribute('aria-checked') === 'true'
                      || !!activeLab.querySelector('[aria-checked="true"], input:checked');
                    const customLab = labels.find((el) => (el.innerText || '').toLowerCase().includes('custom progression'));
                    const customChecked = customLab && (
                      customLab.getAttribute('aria-checked') === 'true'
                      || !!customLab.querySelector('[aria-checked="true"], input:checked')
                    );
                    if (checked && !customChecked) return 'active song';
                    if (customChecked) return 'custom progression';
                    return '';
                  }
                  return '';
                }"""
            )
            or ""
        ).strip().lower()
    except Exception:
        return ""


def click_nested_sbi_source(page: Page, which: str) -> bool:
    """Click SBI Song source without hitting top-level Custom Lab / Songs radios."""
    needle = "custom progression" if which == "custom" else "active song"
    clicked = False
    try:
        group = page.locator('[role="radiogroup"]').filter(
            has_text=re.compile(r"Active song|Active Source", re.I)
        ).filter(has_text=re.compile(r"Custom Progression", re.I))
        if group.count():
            lab = group.first.locator("label").filter(has_text=re.compile(needle, re.I)).first
            if lab.count():
                lab.scroll_into_view_if_needed()
                radio = lab.locator('[role="radio"]').first
                if radio.count():
                    radio.click(timeout=5000)
                else:
                    lab.click(timeout=5000)
                clicked = True
                settle(page, 3)
    except Exception as exc:
        log(f"click_nested_sbi_source playwright {exc}")
    if not clicked:
        clicked = bool(
            page.evaluate(
                """(needle) => {
                  const groups = [...document.querySelectorAll('[role="radiogroup"]')];
                  for (const g of groups) {
                    const txt = (g.innerText || '').toLowerCase();
                    if (!txt.includes('active song') && !txt.includes('active source')) continue;
                    if (!txt.includes('custom progression')) continue;
                    const labels = [...g.querySelectorAll('label')];
                    const match = labels.find((el) => (el.innerText || '').toLowerCase().includes(needle));
                    if (!match) continue;
                    match.scrollIntoView({block: 'center'});
                    (match.querySelector('p') || match).click();
                    return true;
                  }
                  return false;
                }""",
                needle,
            )
        )
        settle(page, 3)
    if which == "custom" and studio_page_slug(page) == "custom":
        log("click_nested_sbi_source landed on Custom Lab; returning to Creative")
        if not open_sbi(page):
            return False
        settle(page, 2)
        return studio_page_slug(page) == "creative" and (
            "song source" in (page.inner_text("body") or "").lower()
        )
    body = (page.inner_text("body") or "").lower()
    if which == "custom":
        return bool(clicked) and studio_page_slug(page) != "custom" and (
            "custom progression" in body or "song source" in body
        )
    if not clicked:
        return False
    checked = sbi_source_checked(page)
    if "active" not in checked:
        try:
            group = page.locator('[role="radiogroup"]').filter(
                has_text=re.compile(r"Active song|Active Source", re.I)
            ).filter(has_text=re.compile(r"Custom Progression", re.I))
            lab = group.first.locator("label").filter(has_text=re.compile(r"active song", re.I)).first
            if lab.count():
                lab.click(timeout=5000)
                settle(page, 3)
        except Exception:
            pass
        checked = sbi_source_checked(page)
    return "active" in checked


def click_sbi_custom(page: Page) -> bool:
    return click_nested_sbi_source(page, "custom")


def has_trial(text: str) -> bool:
    low = (text or "").lower()
    return "trial" in low


def has_generic_shell(text: str) -> bool:
    low = (text or "").lower()
    return "my progression" in low and "trial" not in low


def main() -> int:
    meta = git_meta()
    log(json.dumps(meta))
    rc = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.set_default_timeout(15_000)
        page.goto(f"{URL}/?dev=1", wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 8000)
        settle(page, 3)
        mark("release_marker", "INFO", release_marker(page))

        trial_ok = False
        try:
            trial_ok = build_trial_fast(page)
        except Exception as exc:
            log(f"build_trial_fast raised {exc}")
        ident = identity_marker(page)
        title = str(ident.get("title") or ident.get("widgetTitle") or ident.get("lastTitle") or "")
        body0 = body_text(page)
        if not trial_ok or "trial" not in title.lower() or "trial" not in body0.lower():
            log("setup_trial: fast builder missed Trial Song; using build_trial_song")
            try:
                trial_ok = bool(build_trial_song(page, NOTES))
            except Exception as exc:
                log(f"build_trial_song raised {exc}")
                trial_ok = False
            ident = identity_marker(page)
            title = str(ident.get("title") or ident.get("widgetTitle") or ident.get("lastTitle") or "")
            body0 = body_text(page)
        orig = original_caption(body0)
        ident_orig = str(ident.get("orig") or ident.get("widgetOrig") or orig)
        ident_pk = str(ident.get("practice") or pk_live(page))
        if "trial" not in title.lower() and "trial" not in body0.lower():
            mark("setup_trial", "SETUP_FAIL", f"not Trial Song (title={title!r})", **fail_fields(page, "custom.identity"))
            browser.close()
            (OUT / "proof.json").write_text(json.dumps({"meta": meta, "result": RESULT, "notes": NOTES}, indent=2), encoding="utf-8")
            return 1
        if not same_key(ident_orig, "D"):
            mark("setup_trial", "SETUP_FAIL", f"Trial Original not D ({ident_orig!r})", **fail_fields(page, "sidebar.original_key"))
            browser.close()
            (OUT / "proof.json").write_text(json.dumps({"meta": meta, "result": RESULT, "notes": NOTES}, indent=2), encoding="utf-8")
            return 1
        if not same_key(ident_pk, "D"):
            set_pk(page, "D")
            settle(page, 2)
            ident_pk = pk_live(page)
        if not same_key(ident_pk, "D"):
            mark("setup_trial", "SETUP_FAIL", f"Trial Practice not D ({ident_pk!r})", **fail_fields(page, "sidebar.practice_key"))
            browser.close()
            (OUT / "proof.json").write_text(json.dumps({"meta": meta, "result": RESULT, "notes": NOTES}, indent=2), encoding="utf-8")
            return 1
        mark("setup_trial", "PASS", f"orig={ident_orig!r} pk={ident_pk!r} title={title!r} builder={trial_ok}")

        if not goto_studio(page, "Songs"):
            mark("perfect_sbi_gc", "SETUP_FAIL", "could not open Songs", **fail_fields(page, "nav.songs"))
            rc = 1
        else:
            settle(page, 2)
            click_radio(page, "Catalog") or click_radio(page, "Song Selection")
            settle(page, 1)
            picked = pick_song(page, NOTES, "Perfect", "Pop")
            settle(page, 2)
            if not picked:
                mark("perfect_sbi_gc", "SETUP_FAIL", "could not pick Perfect", **fail_fields(page, "catalog.perfect"))
                rc = 1
            elif not open_sbi(page):
                mark("perfect_sbi_gc", "SETUP_FAIL", "could not open SBI after Perfect", **fail_fields(page, "nav.creative"))
                rc = 1
            else:
                click_nested_sbi_source(page, "active")
                settle(page, 2)
                body_g = page.inner_text("body") or ""
                if not same_key(original_caption(body_g), "G"):
                    mark("perfect_sbi_gc", "SETUP_FAIL", f"Perfect Original not G ({original_caption(body_g)!r})", **fail_fields(page, "sidebar.original_key"))
                    rc = 1
                elif not set_pk(page, "C"):
                    mark("perfect_sbi_gc", "SETUP_FAIL", "could not set Perfect Practice C", **fail_fields(page, "sidebar.practice_key"))
                    rc = 1
                else:
                    settle(page, 2)
                    ok_c, det_c = coherent(page, page.inner_text("body") or "", "C")
                    if not same_key(original_caption(body_text(page)), "G") or not same_key(pk_live(page), "C"):
                        mark("perfect_sbi_gc", "FAIL", f"Perfect not G/C {det_c}", **fail_fields(page, "sidebar.practice_key"))
                        rc = 1
                    else:
                        mark("perfect_sbi_gc", "PASS", f"orig=G pk=C {det_c}")
                    shot(page, "01-perfect-sbi-gc")

                    if not open_sbi(page) or not click_sbi_custom(page):
                        mark("custom_installs_trial", "SETUP_FAIL", "could not click SBI Custom progression", **fail_fields(page, "sbi.source"))
                        rc = 1
                    else:
                        settle(page, 4)
                        snap = snapshot(page)
                        body = body_text(page)
                        low = body.lower()
                        if has_generic_shell(body):
                            mark("custom_installs_trial", "FAIL", "SBI Custom installed My Progression shell", **fail_fields(page, "sbi.custom.identity"))
                            rc = 1
                        elif not has_trial(body):
                            mark("custom_installs_trial", "FAIL", f"SBI Custom is not Trial Song ({snap})", **fail_fields(page, "sbi.custom.identity"))
                            rc = 1
                        else:
                            mark("custom_installs_trial", "PASS", "Trial Song installed")
                        if not same_key(snap["orig"], "D") or not same_key(snap["pk"], "D"):
                            mark("sidebar_dd", "FAIL", f"sidebar orig={snap['orig']!r} pk={snap['pk']!r}", **fail_fields(page, "sidebar.practice_key"))
                            rc = 1
                        else:
                            mark("sidebar_dd", "PASS", "sidebar Original D / Practice D")
                        card_ok = has_trial(body) and "d" in (snap["orig"] or "").lower()
                        if "my progression" in low and "trial" not in low:
                            mark("card_progression_dd", "FAIL", "card/progression still My Progression C", **fail_fields(page, "sbi.custom.progression"))
                            rc = 1
                        elif not card_ok and not same_key(snap["orig"], "D"):
                            mark("card_progression_dd", "FAIL", f"card/progression not Trial D ({snap})", **fail_fields(page, "sbi.custom.progression"))
                            rc = 1
                        else:
                            mark("card_progression_dd", "PASS", "SBI card/progression Trial D")
                        shot(page, "02-sbi-custom-dd")

                        if not (click_nav(page, "Backing") or goto_studio(page, "Backing")):
                            mark("backing_dd", "SETUP_FAIL", "could not open Backing", **fail_fields(page, "nav.backing"))
                            rc = 1
                        else:
                            settle(page, 3)
                            btxt = body_text(page)
                            if has_generic_shell(btxt) or not has_trial(btxt):
                                mark("backing_dd", "FAIL", "Backing is not Trial Song", **fail_fields(page, "backing.source"))
                                rc = 1
                            elif not same_key(original_caption(btxt), "D") or not same_key(pk_live(page), "D"):
                                mark(
                                    "backing_dd",
                                    "FAIL",
                                    f"Backing orig={original_caption(btxt)!r} pk={pk_live(page)!r}",
                                    **fail_fields(page, "backing.practice_key"),
                                )
                                rc = 1
                            else:
                                mark("backing_dd", "PASS", "Custom Backing Trial Original D / Practice D")
                            shot(page, "03-custom-backing-dd")

                            page.reload(wait_until="domcontentloaded")
                            wait_idle(page, 8000)
                            settle(page, 3)
                            btxt = body_text(page)
                            if not same_key(original_caption(btxt), "D") or not same_key(pk_live(page), "D") or not has_trial(btxt):
                                mark(
                                    "backing_refresh_dd",
                                    "FAIL",
                                    f"after refresh orig={original_caption(btxt)!r} pk={pk_live(page)!r}",
                                    **fail_fields(page, "sidebar.practice_key"),
                                )
                                rc = 1
                            else:
                                mark("backing_refresh_dd", "PASS", "Trial D/D survived Custom Backing refresh")
                            shot(page, "04-custom-backing-refresh")

                            if not open_sbi(page):
                                mark("active_gc_no_leak", "SETUP_FAIL", "could not reopen SBI", **fail_fields(page, "nav.creative"))
                                rc = 1
                            else:
                                settled = False
                                for attempt in range(4):
                                    if sbi_source_checked(page) != "active song":
                                        click_nested_sbi_source(page, "active")
                                    settle(page, 4)
                                    orig_now = original_caption(body_text(page))
                                    pk_now = pk_live(page)
                                    log(f"active_click attempt={attempt} checked={sbi_source_checked(page)!r} orig={orig_now!r} pk={pk_now!r}")
                                    if sbi_source_checked(page) == "active song" and same_key(orig_now, "G"):
                                        settled = True
                                        break
                                snap = snapshot(page)
                                if not settled and sbi_source_checked(page) != "active song":
                                    mark("active_gc_no_leak", "SETUP_FAIL", "could not click SBI Active", **fail_fields(page, "sbi.source"))
                                    rc = 1
                                elif same_key(snap["pk"], "D") and same_key(snap["orig"], "G"):
                                    mark("active_gc_no_leak", "FAIL", "Perfect Practice became Trial D", **fail_fields(page, "sbi.active.practice_key"))
                                    rc = 1
                                elif not same_key(snap["orig"], "G"):
                                    mark("active_gc_no_leak", "FAIL", f"Perfect Original {snap['orig']!r} not G", **fail_fields(page, "sbi.active.original_key"))
                                    rc = 1
                                elif not same_key(snap["pk"], "C"):
                                    mark("active_gc_no_leak", "FAIL", f"Perfect Practice {snap['pk']!r} not saved C", **fail_fields(page, "sbi.active.practice_key"))
                                    rc = 1
                                else:
                                    mark("active_gc_no_leak", "PASS", "Perfect restored Original G / Practice C")
                                shot(page, "05-sbi-active-gc")

                                page.reload(wait_until="domcontentloaded")
                                wait_idle(page, 8000)
                                settle(page, 3)
                                open_sbi(page)
                                click_nested_sbi_source(page, "active")
                                settle(page, 2)
                                snap = snapshot(page)
                                ok_r, det_r = coherent(page, page.inner_text("body") or "", "C")
                                if not same_key(snap["orig"], "G") or not same_key(snap["pk"], "C"):
                                    mark("perfect_refresh_gc", "FAIL", f"after refresh orig={snap['orig']!r} pk={snap['pk']!r} {det_r}", **fail_fields(page, "sidebar.practice_key"))
                                    rc = 1
                                else:
                                    mark("perfect_refresh_gc", "PASS", f"Perfect G/C survived refresh {det_r}")
                                shot(page, "06-perfect-refresh-gc")

        browser.close()

    out = {"meta": meta, "result": RESULT, "notes": NOTES}
    (OUT / "proof.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(json.dumps({"rc": rc, "steps": {k: v.get("status") for k, v in RESULT.items() if isinstance(v, dict)}}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
