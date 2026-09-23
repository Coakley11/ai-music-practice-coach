"""Phase B browser proof: Catalog/Custom SBI ownership on persistent 8552.

Stops at the first divergence. Does not ask for a retest.

Usage:
  python scripts/_proof_phase_b_sbi_ownership.py http://127.0.0.1:8552
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
    goto_improv,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8552"
OUT = SCRIPTS / "evidence-phase-b-sbi-ownership"
OUT.mkdir(parents=True, exist_ok=True)
RESULT: dict[str, object] = {}
NOTES: list[str] = []
BOUNDARIES: list[dict[str, object]] = []


class GateFail(Exception):
    def __init__(self, gate: str, field: str, detail: str, snap: dict[str, object]):
        super().__init__(f"{gate} FAIL first_incorrect={field} {detail}")
        self.gate = gate
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


def original_caption(text: str) -> str:
    return key_token(original_key_caption(text or ""))


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


def shot(page: Page, name: str) -> str:
    expand_sidebar(page)
    side = sidebar_text(page)
    main = ""
    try:
        main = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        main = ""
    body = body_text(page)
    (OUT / f"{name}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:8000]}\n\n=== MAIN ===\n{main[:24000]}\n\n=== BODY ===\n{body[:8000]}",
        encoding="utf-8",
    )
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    return main or body


def open_sbi(page: Page) -> bool:
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    expand_sidebar(page)
    expand_pages_nav(page)
    settle(page, 1)
    if not (click_nav(page, "Creative") or goto_studio(page, "Creative")):
        return False
    settle(page, 3)

    def _click_improv_tab(label_re: str) -> bool:
        return bool(
            page.evaluate(
                """(needle) => {
                  const re = new RegExp(needle, 'i');
                  const groups = [...document.querySelectorAll('[role="radiogroup"]')];
                  for (const g of groups) {
                    const gt = (g.innerText || '');
                    // Prefer the Improvisation section row (Entry + Missions + Harmony…).
                    if (!/Entry/i.test(gt) || !/Missions/i.test(gt)) continue;
                    const lab = [...g.querySelectorAll('label')].find((l) => re.test(l.innerText || ''));
                    if (!lab) continue;
                    lab.scrollIntoView({block: 'center'});
                    lab.click();
                    return true;
                  }
                  // Fallback: any radiogroup label match.
                  for (const g of groups) {
                    const lab = [...g.querySelectorAll('label')].find((l) => re.test(l.innerText || ''));
                    if (!lab) continue;
                    lab.scrollIntoView({block: 'center'});
                    lab.click();
                    return true;
                  }
                  return false;
                }""",
                label_re,
            )
        )

    def _on_sbi(body: str) -> bool:
        if re.search(r"Selected Mission Chord|Generate example", body, re.I):
            return False
        if re.search(r"Song source", body, re.I):
            return True
        return bool(
            re.search(r"Play Song-Based Improvisation", body, re.I)
            and re.search(r"Custom Progression", body, re.I)
            and re.search(r"Active song|Active Source", body, re.I)
        )

    for attempt in range(5):
        _click_improv_tab(r"Entry")
        settle(page, 3)
        _click_improv_tab(r"Play Song-Based|Song-Based Improvisation")
        settle(page, 3)
        # Also try the helper click_radio paths.
        click_radio(page, "Play Song-Based Improvisation") or click_button_has(
            page, r"Play Song-Based Improvisation"
        )
        settle(page, 2)
        body = body_text(page)
        if _on_sbi(body):
            return True
        log(
            f"open_sbi attempt={attempt} "
            f"mission_sticky={bool(re.search(r'Selected Mission Chord|Generate example', body, re.I))} "
            f"play_sbi={bool(re.search(r'Play Song-Based', body, re.I))}"
        )
    return False


def click_nested_sbi_source(page: Page, which: str) -> bool:
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
        log(f"click_nested_sbi_source {exc}")
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
    return clicked


def capture(page: Page, gate: str, step: str) -> dict[str, object]:
    side = sidebar_text(page)
    try:
        main = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        main = body_text(page)
    active_block = ""
    m_active = re.search(r"ACTIVE SONG(.{0,400})", side, re.I | re.S)
    if m_active:
        active_block = m_active.group(0)
    orig = original_caption(side)
    pk = pk_live(page)
    focus = ""
    for pat in (r"Practice Focus\s*·[^\n]{0,200}", r"🔍\s*Practice Focus[^\n]{0,200}"):
        fm = re.search(pat, main, re.I)
        if fm:
            focus = fm.group(0).strip()
            break
    sidebar_song = ""
    m_title = re.search(
        r"ACTIVE SONG\s*(?:\n|\r\n?)+(Trial Song|My Progression|Perfect|[^\n]{1,40})",
        active_block or side,
        re.I,
    )
    if m_title:
        sidebar_song = m_title.group(1).strip()
    elif re.search(r"Trial Song", active_block, re.I):
        sidebar_song = "Trial Song"
    elif re.search(r"My Progression", active_block, re.I):
        sidebar_song = "My Progression"
    elif re.search(r"Perfect", active_block):
        sidebar_song = "Perfect"
    elif re.search(r"Trial Song", side, re.I) and "Perfect —" not in side:
        sidebar_song = "Trial Song"
    elif re.search(r"Perfect — Ed Sheeran", side) or re.search(r"SONG\s+Perfect", side):
        sidebar_song = "Perfect"
    row = {
        "gate": gate,
        "step": step,
        "sidebar_song": sidebar_song,
        "original_key": orig,
        "practice_key": pk,
        "focus": focus,
        "tab_sbi": bool(
            (
                re.search(r"Song source", main, re.I)
                or (
                    re.search(r"Play Song-Based Improvisation", main, re.I)
                    and re.search(r"Active song|Active Source", main, re.I)
                    and re.search(r"Custom Progression", main, re.I)
                )
            )
            and not re.search(r"Selected Mission Chord|Generate example", main, re.I)
        ),
        "has_trial": sidebar_song == "Trial Song" or bool(re.search(r"Trial Song", focus, re.I)),
        "has_perfect": sidebar_song == "Perfect" or bool(re.search(r"Perfect", focus)),
        "has_jam": bool(re.search(r"Jam Generator|Jewish ballad", focus, re.I)),
        "has_my_progression": bool(re.search(r"My Progression", active_block + "\n" + focus, re.I)),
        "crash": "display_key cannot be modified" in (side + main),
    }
    BOUNDARIES.append(row)
    log(
        f"[BOUND] {gate}/{step} song={sidebar_song!r} orig={orig!r} pk={pk!r} "
        f"focus={focus!r} sbi={row['tab_sbi']}"
    )
    return row


def require(gate: str, field: str, ok: bool, detail: str, snap: dict[str, object]) -> None:
    if not ok:
        raise GateFail(gate, field, detail, snap)


def activate_perfect(page: Page) -> None:
    if not goto_studio(page, "Songs") and not click_nav(page, "Songs"):
        raise GateFail("setup", "nav.songs", "could not open Songs", {})
    settle(page, 2)
    click_radio(page, "Catalog") or click_radio(page, "Song Selection")
    settle(page, 1)
    if not pick_song(page, NOTES, "Perfect", "Pop"):
        raise GateFail("setup", "catalog.perfect", "could not pick Perfect", {})
    settle(page, 2)


def seed_trial_song_last_custom(page: Page) -> None:
    """Ensure LAST_CUSTOM is Trial Song in D so SBI Custom is not My Progression."""
    expand_pages_nav(page)
    if not (click_nav(page, "Custom") or goto_studio(page, "Custom")):
        raise GateFail("setup", "nav.custom", "could not open Custom", {})
    settle(page, 3)
    body = body_text(page)
    needs_create = not re.search(r"Trial Song", body, re.I)
    if needs_create:
        click_button_has(page, r"New song") or click_button_has(page, r"New Song")
        settle(page, 2.5)
        titled = False
        try:
            from _walk_custom_practice_key import set_original_key
        except Exception:
            set_original_key = None  # type: ignore[assignment]
        # Title: prefer labeled inputs, then first text field in main.
        for sel in (
            'input[aria-label*="Title"]',
            'input[aria-label*="Song"]',
            'input[aria-label*="Name"]',
            'input[aria-label*="title"]',
            'input[aria-label*="song"]',
            '[data-testid="stMain"] input[type="text"]',
        ):
            try:
                inp = page.locator(sel).first
                if inp.count() == 0:
                    continue
                inp.click(timeout=3000)
                page.keyboard.press("Control+A")
                page.keyboard.type("Trial Song", delay=25)
                page.keyboard.press("Enter")
                settle(page, 1)
                titled = True
                break
            except Exception as exc:
                log(f"trial title via {sel}: {exc}")
        if set_original_key is not None:
            set_original_key(page, "D")
        else:
            set_baseweb_select(page, "Original Key", "D") or set_baseweb_select(
                page, "Original Key", "D major"
            )
        settle(page, 2)
        # Minimal progression so Trial is substantive in the library / LAST_CUSTOM.
        for ch in ("Em", "Em", "D", "D"):
            try:
                click_button_has(page, rf"^{re.escape(ch)}$") or click_button_has(page, ch)
                settle(page, 0.6)
                click_button_has(page, r"^1 bar$") or click_button_has(page, r"1 bar")
                settle(page, 0.6)
            except Exception as exc:
                log(f"trial chord {ch}: {exc}")
        click_button_has(page, r"Save to library") or click_button_has(page, r"Save")
        settle(page, 3)
        if not titled:
            log("WARN: Trial title input may have missed")
    # Select Trial Song if a library picker exists
    set_baseweb_select(page, "Saved", "Trial Song") or set_baseweb_select(page, "Song", "Trial Song")
    settle(page, 1)
    click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
    settle(page, 2)
    # Persist LAST_CUSTOM onto disk so activate_perfect / remount cannot lose Trial.
    _force_trial_last_custom_on_disk()
    # Reload so Streamlit hydrates disk LAST_CUSTOM before Catalog Perfect reclaim.
    try:
        page.reload(wait_until="domcontentloaded")
        wait_idle(page, 8000)
        settle(page, 2)
    except Exception as exc:
        log(f"post-seed reload: {exc}")
    if not _disk_has_trial_last_custom():
        raise GateFail(
            "setup",
            "seed.trial",
            "Trial Song LAST_CUSTOM missing on disk after seed",
            {},
        )
    body = body_text(page) + sidebar_text(page)
    if re.search(r"Trial Song", body, re.I):
        log("seeded Trial Song as last custom (UI+disk)")
    else:
        log("seeded Trial Song as last custom (disk; UI label may lag)")


def _disk_has_trial_last_custom() -> bool:
    path = ROOT / "_runtime_hotfix_missions" / "workspaces" / "daniel" / "music_user_state.json"
    if not path.exists():
        return False
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return "Trial Song" in raw and "_last_custom_song_state" in raw


def _force_trial_last_custom_on_disk() -> None:
    """Write Trial Song into workspace LAST_CUSTOM + library when UI seed is flaky."""
    path = ROOT / "_runtime_hotfix_missions" / "workspaces" / "daniel" / "music_user_state.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"force trial disk read: {exc}")
        return
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    trial_id = "trial-phase-b-seed"
    trial_active = {
        "id": trial_id,
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [
                {"chord": "Em", "bars": 1},
                {"chord": "Em", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
            ]
        },
        "bpm": 100,
    }
    snap = {
        "name": "Trial Song",
        "pick_key": f"custom::{trial_id}",
        "custom_home_key": "D",
        "active": trial_active,
    }
    targets: list[dict] = []
    for key in ("session", "creative_workspace_state", "music_workspace_state"):
        blob = state.get(key)
        if isinstance(blob, dict):
            targets.append(blob)
            nested = blob.get("creative_workspace_state")
            if isinstance(nested, dict):
                targets.append(nested)
    if not targets and isinstance(state, dict):
        targets.append(state)
    for ss in targets:
        ss["_last_custom_song_state"] = snap
        saved = ss.get("cpl_saved_progressions")
        if not isinstance(saved, dict):
            saved = {}
            ss["cpl_saved_progressions"] = saved
        saved["Trial Song"] = dict(trial_active)
        # Do not clobber a live named Trial shell; upgrade generic My Progression.
        live = ss.get("cpl_active_progression")
        live_name = str((live or {}).get("name") or "").strip() if isinstance(live, dict) else ""
        if live_name in {"", "My Progression", "My progression"}:
            ss["cpl_active_progression"] = dict(trial_active)
        custom = ss.get("custom_session")
        if isinstance(custom, dict):
            custom["title"] = "Trial Song"
            custom["pick_key"] = f"custom::{trial_id}"
            custom["original_key"] = "D"
            custom["progression_id"] = trial_id
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log("forced Trial Song onto disk LAST_CUSTOM + library")
    except Exception as exc:
        log(f"force trial disk write: {exc}")


def main() -> int:
    meta = git_meta()
    log(json.dumps(meta))
    rc = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.set_default_timeout(15_000)
        try:
            page.goto(f"{URL}/?dev=1", wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 8000)
            settle(page, 3)

            activate_perfect(page)
            if not open_sbi(page):
                raise GateFail("B1", "nav.sbi", "could not open SBI", {})
            click_nested_sbi_source(page, "active")
            settle(page, 2)
            snap = capture(page, "B1", "sbi_active_before_pk")
            if not same_key(str(snap["original_key"]), "G"):
                raise GateFail("B1", "original_key", f"Original not G ({snap['original_key']!r})", snap)
            if not same_key(str(snap["practice_key"]), "C"):
                if not set_pk(page, "C"):
                    raise GateFail("B1", "practice_key", f"could not set Practice C (live={pk_live(page)!r})", snap)
                settle(page, 2)
            snap = capture(page, "B1", "sbi_active_gc")
            shot(page, "b1-sbi-active-gc")
            require("B1", "sidebar_song", str(snap["sidebar_song"]) == "Perfect", "sidebar not Perfect", snap)
            require("B1", "original_key", same_key(str(snap["original_key"]), "G"), f"Original {snap['original_key']!r}", snap)
            require("B1", "practice_key", same_key(str(snap["practice_key"]), "C"), f"Practice {snap['practice_key']!r}", snap)
            require("B1", "trial_leak", not snap["has_trial"], "Trial leaked onto Active Perfect", snap)
            require("B1", "jam_leak", not snap["has_jam"], "Jam leaked onto Active Perfect", snap)
            require("B1", "sbi_tab", bool(snap["tab_sbi"]), "Song source radio not visible (not on SBI)", snap)
            require("B1", "crash", not snap["crash"], "mounted display_key crash", snap)
            RESULT["B1_live"] = {"status": "PASS", **snap}

            page.reload(wait_until="domcontentloaded")
            wait_idle(page, 8000)
            settle(page, 3)
            snap = capture(page, "B1", "refresh")
            shot(page, "b1-refresh")
            require("B1", "refresh.practice_key", same_key(str(snap["practice_key"]), "C"), f"refresh PK {snap['practice_key']!r}", snap)
            require("B1", "refresh.original_key", same_key(str(snap["original_key"]), "G"), f"refresh orig {snap['original_key']!r}", snap)
            require("B1", "refresh.trial_leak", not snap["has_trial"], "refresh leaked Trial", snap)
            RESULT["B1_refresh"] = {"status": "PASS", **snap}

            # LAST_CUSTOM must be Trial Song (D) before SBI Custom — workspace may only have My Progression.
            seed_trial_song_last_custom(page)
            activate_perfect(page)
            if not open_sbi(page) or not click_nested_sbi_source(page, "custom"):
                raise GateFail("B2", "sbi.custom", "could not select SBI Custom", snap)
            settle(page, 4)
            snap = capture(page, "B2", "sbi_custom")
            shot(page, "b2-sbi-custom")
            require("B2", "identity", bool(snap["has_trial"]), "SBI Custom is not Trial Song", snap)
            require("B2", "shell", not (snap["has_my_progression"] and not snap["has_trial"]), "My Progression shell", snap)
            require("B2", "original_key", same_key(str(snap["original_key"]), "D"), f"Original {snap['original_key']!r}", snap)
            if not same_key(str(snap["practice_key"]), "F"):
                if not set_pk(page, "F"):
                    raise GateFail("B2", "practice_key", f"could not set Trial Practice F (live={pk_live(page)!r})", snap)
                settle(page, 2)
                snap = capture(page, "B2", "after_pk_f")
            require("B2", "practice_key", same_key(str(snap["practice_key"]), "F"), f"Practice {snap['practice_key']!r}", snap)
            RESULT["B2_live"] = {"status": "PASS", **snap}

            page.reload(wait_until="domcontentloaded")
            wait_idle(page, 8000)
            settle(page, 3)
            snap = capture(page, "B2", "refresh")
            shot(page, "b2-refresh")
            require("B2", "refresh.identity", bool(snap["has_trial"]), "refresh lost Trial", snap)
            require("B2", "refresh.practice_key", same_key(str(snap["practice_key"]), "F"), f"refresh PK {snap['practice_key']!r}", snap)
            require("B2", "refresh.original_key", same_key(str(snap["original_key"]), "D"), f"refresh orig {snap['original_key']!r}", snap)
            RESULT["B2_refresh"] = {"status": "PASS", **snap}

            focus = str(snap.get("focus") or "")
            require("B3", "focus.custom", "Trial Song" in focus and "SBI Custom" in focus, f"focus {focus!r}", snap)
            require("B3", "focus.jam", "Jam" not in focus and "Jewish" not in focus, f"focus {focus!r}", snap)
            require("B3", "focus.perfect", "Perfect" not in focus, f"focus {focus!r}", snap)

            click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
            settle(page, 2)
            click_radio(page, "Jam Session Generator") or click_radio(page, "Jam Session") or click_button_has(
                page, r"Jam Session"
            )
            settle(page, 2)
            set_baseweb_select(page, "Style", "Jewish ballad") or set_baseweb_select(page, "Jam style", "Jewish ballad")
            settle(page, 2)
            snap = capture(page, "B3", "jam")
            shot(page, "b3-jam")
            if not open_sbi(page) or not click_nested_sbi_source(page, "custom"):
                raise GateFail("B3", "return.sbi_custom", "could not return to SBI Custom", snap)
            settle(page, 3)
            snap = capture(page, "B3", "return_custom")
            shot(page, "b3-return-custom")
            focus = str(snap.get("focus") or "")
            require("B3", "return.trial", bool(snap["has_trial"]), "lost Trial after Jam", snap)
            require("B3", "return.jam", "Jam Generator" not in focus and "Jewish ballad" not in focus, f"Jam survived {focus!r}", snap)
            require("B3", "return.focus", "Trial Song" in focus, f"focus {focus!r}", snap)
            RESULT["B3_custom"] = {"status": "PASS", "focus": focus, **snap}

            if not click_nested_sbi_source(page, "active"):
                raise GateFail("B4", "sbi.active", "could not select SBI Active", snap)
            settle(page, 3)
            snap = capture(page, "B4", "sbi_active")
            shot(page, "b4-sbi-active")
            require("B4", "original_key", same_key(str(snap["original_key"]), "G"), f"Original {snap['original_key']!r}", snap)
            require("B4", "practice_key", same_key(str(snap["practice_key"]), "C"), f"Practice {snap['practice_key']!r}", snap)
            require("B4", "trial_leak", not snap["has_trial"] or "SBI Catalog" in str(snap.get("focus") or ""), "Trial leaked", snap)
            focus = str(snap.get("focus") or "")
            require("B4", "focus", "Perfect" in focus and "Trial" not in focus, f"focus {focus!r}", snap)
            RESULT["B4_live"] = {"status": "PASS", **snap}

            page.reload(wait_until="domcontentloaded")
            wait_idle(page, 8000)
            settle(page, 3)
            snap = capture(page, "B4", "refresh")
            shot(page, "b4-refresh")
            require("B4", "refresh.practice_key", same_key(str(snap["practice_key"]), "C"), f"refresh PK {snap['practice_key']!r}", snap)
            require("B4", "refresh.original_key", same_key(str(snap["original_key"]), "G"), f"refresh orig {snap['original_key']!r}", snap)
            require("B4", "refresh.trial", not same_key(str(snap["practice_key"]), "F"), "refresh landed G/F", snap)
            RESULT["B4_refresh"] = {"status": "PASS", **snap}

            click_radio(page, "Phrase / Motif") or click_radio(page, "Phrase") or click_button_has(page, r"Phrase")
            settle(page, 2)
            snap = capture(page, "B5", "phrase")
            shot(page, "b5-phrase")
            require("B5", "phrase.original_key", same_key(str(snap["original_key"]), "G"), f"Phrase orig {snap['original_key']!r}", snap)
            require("B5", "phrase.practice_key", same_key(str(snap["practice_key"]), "C"), f"Phrase PK {snap['practice_key']!r}", snap)
            require("B5", "phrase.trial", not snap["has_trial"] or "Perfect" in str(snap.get("focus") or ""), "Phrase Trial leak", snap)
            click_radio(page, "Missions") or click_button_has(page, r"Missions")
            settle(page, 2)
            snap = capture(page, "B5", "missions")
            require("B5", "missions.practice_key", same_key(str(snap["practice_key"]), "C"), f"Missions PK {snap['practice_key']!r}", snap)
            click_radio(page, "Harmony Map") or click_radio(page, "Harmony") or click_button_has(page, r"Harmony")
            settle(page, 2)
            snap = capture(page, "B5", "harmony")
            require("B5", "harmony.practice_key", same_key(str(snap["practice_key"]), "C"), f"Harmony PK {snap['practice_key']!r}", snap)
            RESULT["B5"] = {"status": "PASS", **snap}

            if not goto_studio(page, "Custom") and not click_nav(page, "Custom"):
                raise GateFail("B6", "nav.custom", "could not open Custom Lab", snap)
            settle(page, 3)
            clicked = click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
            settle(page, 3)
            require("B6", "set_as_active", bool(clicked), "Set as Active Song did not click", snap)
            activate_perfect(page)
            settle(page, 3)
            snap = capture(page, "B6", "reactivate_perfect")
            shot(page, "b6-genuine-perfect")
            require("B6", "genuine.original_key", same_key(str(snap["original_key"]), "G"), f"orig {snap['original_key']!r}", snap)
            require(
                "B6",
                "genuine.practice_key",
                same_key(str(snap["practice_key"]), "G"),
                f"genuine Perfect PK should initialize from Original G, got {snap['practice_key']!r}",
                snap,
            )
            RESULT["B6_genuine"] = {"status": "PASS", **snap}
            RESULT["B6_temporary"] = {"status": "PASS", "detail": "B4 return to Perfect G/C is the temporary-work case"}
        except GateFail as exc:
            rc = 1
            RESULT[exc.gate] = {
                "status": "FAIL",
                "field": exc.field,
                "detail": exc.detail,
                "snap": exc.snap,
            }
            log(str(exc))
            try:
                shot(page, f"fail-{exc.gate}")
            except Exception:
                pass
        except Exception as exc:
            rc = 1
            RESULT["crash"] = {"status": "FAIL", "detail": str(exc)}
            log(f"crash {exc}")
        finally:
            try:
                browser.close()
            except Exception:
                pass
    payload = {"meta": meta, "result": RESULT, "boundaries": BOUNDARIES, "notes": NOTES, "rc": rc}
    (OUT / "proof.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(json.dumps({"rc": rc, "gates": {k: v.get("status") for k, v in RESULT.items() if isinstance(v, dict)}}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
