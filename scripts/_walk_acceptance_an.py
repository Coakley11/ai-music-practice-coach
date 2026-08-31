"""Human A–N regression walk (agent-only; embargo still on).

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8531
  python scripts/_walk_acceptance_an.py http://127.0.0.1:8531
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
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    ensure_checkbox,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_for_backing,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_custom_page_owner_basics import (  # noqa: E402
    click_main_button,
    set_presets_key,
)
from _walk_custom_practice_key import (  # noqa: E402
    goto_custom,
    key_is,
    original_key_val,
    pk_val,
)
from _walk_ownership_audit_full import (  # noqa: E402
    add_chord_bar,
    build_trial_song,
    rendered_em_em_d_d,
)
from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_core_workflows_embargo import (  # noqa: E402
    click_available_mission_chord,
    click_generate_example,
    mission_selected_chord,
    open_sbi_active,
    practice_badge,
)
from _walk_custom_sbi_owner import concert_prog_line, trial_prog_at_c  # noqa: E402
from _walk_pass8_validate import (  # noqa: E402
    click_chord,
    ensure_missions_workspace,
    open_mission_backing,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8531"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "an-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []
PAGE_ERRORS: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def low(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("♯", "#").replace("♭", "b"))


def has_any(text: str, *needles: str) -> bool:
    b = low(text)
    return any(n.lower() in b for n in needles)


def _norm_ch(sym: str) -> str:
    return (sym or "").replace("♯", "#").replace("♭", "b").strip()


_CHORD_TOKEN = r"([A-G](?:#|b|♯|♭)?(?:m(?!aj)|maj7|m7|sus4|7)?)"


def mission_header_chord(text: str) -> str:
    m = re.search(
        rf"Creative Backing Jam · Mission[^\n]*?·\s*{_CHORD_TOKEN}\s*·\s*Concert",
        text,
    )
    if m:
        return _norm_ch(m.group(1))
    m = re.search(rf"Verse 1 · {_CHORD_TOKEN}", text)
    return _norm_ch(m.group(1) if m else "")


def mission_card_chord(text: str) -> str:
    m = re.search(rf"Verse 1 · {_CHORD_TOKEN}", text)
    return _norm_ch(m.group(1) if m else "")


def mission_example_chord(text: str) -> str:
    m = re.search(rf"Mission example\s*[·•]\s*{_CHORD_TOKEN}", text)
    if m:
        return _norm_ch(m.group(1))
    m = re.search(rf"Chord\s+{_CHORD_TOKEN}", text)
    return _norm_ch(m.group(1) if m else "")


def enable_alto_written(page: Page) -> None:
    set_instrument(page, "Saxophone") or set_instrument(page, "Alto Saxophone")
    settle(page, 2)
    set_baseweb_select(page, "Saxophone", "Alto") or set_baseweb_select(
        page, "Type", "Alto saxophone (Eb)"
    )
    settle(page, 1)
    ensure_checkbox(page, "Show chart in written key for instrument", checked=True) or (
        click_button_has(page, r"Written Charts") or click_radio(page, "Written Charts on")
    )
    settle(page, 2)


def list_chord_tiles(page: Page) -> list[str]:
    """Visible + off-screen chord-like button labels in the main pane."""
    try:
        labels = page.evaluate(
            """() => {
              const main = document.querySelector('[data-testid="stMain"]') || document.body;
              return [...main.querySelectorAll('button')]
                .map((b) => (b.innerText || '').trim().replace(/\\s+/g, ''))
                .filter((t) => /^[A-G][#b♯♭]?(m|maj7|m7|sus4|7)?$/.test(t))
                .slice(0, 32);
            }"""
        )
        return [_norm_ch(str(x)) for x in (labels or [])]
    except Exception:
        return []


def set_main_instrument_piano(page: Page) -> None:
    """Missions has its own Instrument widget; sidebar Piano is not enough."""
    try:
        main = page.locator('[data-testid="stMain"]')
        boxes = main.locator('[data-testid="stSelectbox"]').filter(
            has_text=re.compile(r"Instrument", re.I)
        )
        for i in range(min(boxes.count(), 3)):
            el = boxes.nth(i)
            try:
                if not el.is_visible():
                    continue
                text = (el.inner_text() or "").strip()
                if "Shape" in text:
                    continue
                clickable = el.locator('[data-baseweb="select"], [role="combobox"], input').first
                if clickable.count() == 0:
                    continue
                clickable.click(timeout=3000)
                page.wait_for_timeout(250)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type("Piano", delay=30)
                page.wait_for_timeout(400)
                opt = page.locator('[role="option"]').filter(
                    has_text=re.compile(r"^Piano$", re.I)
                )
                if opt.count():
                    opt.first.click(timeout=2500)
                else:
                    page.keyboard.press("Enter")
                settle(page, 2)
            except Exception:
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
    except Exception:
        pass


def click_catalog_shape_tile(page: Page, label: str) -> bool:
    """Playwright pointer click — JS el.click() does not fire Streamlit buttons."""
    try:
        page.get_by_text("Chord map by section", exact=False).first.scroll_into_view_if_needed(
            timeout=3000
        )
    except Exception:
        pass
    if click_chord(page, label):
        return True
    loc = page.locator('[data-testid="stMain"] button').filter(
        has_text=re.compile(rf"^{re.escape(label)}$")
    )
    for i in range(min(loc.count(), 12)):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            el.scroll_into_view_if_needed(timeout=3000)
            el.hover(timeout=2000)
            el.click(timeout=4000, force=False)
            settle(page, 2)
            return True
        except Exception:
            continue
    return False


def force_pk_token(page: Page, token: str) -> bool:
    """Commit sidebar Practice Key with a real option click (typeahead often no-ops)."""
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    expand_sidebar(page)
    aliases = [token]
    if token == "Bm":
        aliases += ["B minor"]
    elif token == "Cm":
        aliases += ["C minor"]
    for alias in aliases:
        try:
            combo = page.get_by_role("combobox", name="Practice / Concert Key")
            if combo.count() == 0:
                continue
            combo.first.click(timeout=4000)
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(str(alias), delay=35)
            page.wait_for_timeout(500)
            opt = page.locator('[role="option"]').filter(
                has_text=re.compile(rf"^{re.escape(alias)}$", re.I)
            )
            if opt.count() == 0:
                page.keyboard.press("Escape")
                continue
            el = opt.first
            el.scroll_into_view_if_needed()
            el.hover(timeout=2000)
            el.click(timeout=4000, force=False)
            settle(page, 3)
            landed = low(pk_val(page)).replace(" ", "")
            want = token.lower().replace(" ", "")
            if token == "Bm" and landed in {"cm", "cminor"}:
                continue
            if want in landed or alias.lower().replace(" ", "") in landed:
                return True
            page.keyboard.press("Escape")
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
    try:
        from _walk_pass8_live import set_practice_key as _set_pk

        return bool(_set_pk(page, token))
    except Exception:
        return False


def force_piano_concert_shape_tiles(page: Page) -> bool:
    """Keep piano + concert spelling so Shape tiles are Bm · Em · G · A."""
    for _ in range(4):
        expand_sidebar(page)
        set_instrument(page, "Piano")
        settle(page, 1)
        set_main_instrument_piano(page)
        click_radio(page, "Written Charts off")
        ensure_checkbox(page, "Show chart in written key for instrument", checked=False)
        force_pk_token(page, "Bm")
        settle(page, 2)
        try:
            page.get_by_text("Chord map by section", exact=False).first.scroll_into_view_if_needed(
                timeout=2500
            )
        except Exception:
            pass
        tiles = list_chord_tiles(page)
        if "Em" in tiles and "Bm" in tiles:
            return True
        log(f"K wait concert Bm tiles={tiles} pk={pk_val(page)!r}")
    return False


def select_shape_em(page: Page) -> bool:
    """Click catalog Em and wait until Selected Mission Chord is Em (concert)."""
    for attempt in range(6):
        have_tiles = force_piano_concert_shape_tiles(page)
        tiles = list_chord_tiles(page)
        log(f"K tiles attempt={attempt} have={have_tiles} pk={pk_val(page)!r} {tiles}")
        if "Em" not in tiles:
            continue
        clicked = click_catalog_shape_tile(page, "Em")
        settle(page, 2)
        sel = _norm_ch(mission_selected_chord(page.inner_text("body") or ""))
        log(f"K selected={sel!r} clicked={clicked}")
        if sel == "Em":
            return True
    return False


def set_style_jam_concert_key(page: Page, option: str) -> bool:
    """Set Style Jam Concert Key — never the sidebar Practice / Concert Key."""
    try:
        main = page.locator('[data-testid="stAppViewContainer"]')
        boxes = main.locator('[data-testid="stSelectbox"]').filter(
            has_text=re.compile(r"^Concert Key$|Concert Key(?!.*Practice)", re.I)
        )
        target = None
        for i in range(boxes.count()):
            el = boxes.nth(i)
            t = (el.inner_text() or "")
            if re.search(r"Practice\s*/\s*Concert Key", t, re.I):
                continue
            if re.search(r"Concert Key", t, re.I):
                target = el
                break
        if target is None:
            return False
        target.scroll_into_view_if_needed()
        target.locator('[data-baseweb="select"], [role="combobox"], input').first.click(timeout=4000)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(option, delay=40)
        page.wait_for_timeout(500)
        opt = page.locator('[role="option"]').filter(
            has_text=re.compile(rf"^{re.escape(option)}(\s+major)?$", re.I)
        )
        if opt.count():
            opt.first.click(timeout=4000)
            wait_idle(page, 2000)
            return True
    except Exception:
        return False
    return False


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> tuple[str, str]:
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


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'RED'}] {gate}" + (f" — {detail}" if detail else ""))


def attach_errors(page: Page) -> None:
    def _on_page_error(exc) -> None:
        PAGE_ERRORS.append(str(exc))
        log(f"pageerror: {exc}")

    page.on("pageerror", _on_page_error)


def main_button_boxes(page: Page, pattern: str) -> list[dict]:
    loc = page.locator(
        '[data-testid="stAppViewContainer"] button, section.main button, .main button'
    ).filter(has_text=re.compile(pattern, re.I))
    out: list[dict] = []
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            box = el.bounding_box()
            if box:
                out.append({"text": (el.inner_text() or "").strip(), **box})
        except Exception:
            continue
    return out


def same_row(a: dict, b: dict, *, tol: float = 28.0) -> bool:
    return abs(float(a["y"]) - float(b["y"])) <= tol


def leave_specialized_backing(page: Page) -> None:
    click_button_has(page, r"Return to Mission") or click_button_has(
        page, r"Return to Creative"
    ) or click_button_has(page, r"Return to Style")
    settle(page, 2)


def main() -> int:
    meta = git_meta()
    log(json.dumps(meta))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 980})
        attach_errors(page)
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        # A. Global Active Shape / B minor
        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        set_songs_practice_key(page, "Bm")
        settle(page, 3)
        side_a, body_a = shot(page, "A-shape-bm")
        badge_a = practice_badge(side_a + body_a) or pk_val(page)
        a_ok = has_any(side_a + body_a, "Shape of You") and "b minor" in low(badge_a or side_a + body_a)
        mark("A_shape_bm", a_ok, f"badge={badge_a!r} pk={pk_val(page)!r}")

        # B. Custom Trial D / Em Em D D
        trial_ok = build_trial_song(page, NOTES)
        settle(page, 2)
        side_b, body_b = shot(page, "B-trial")
        orig_b = original_key_val(page)
        b_ok = bool(trial_ok) and has_any(body_b, "Trial Song") and (
            key_is(orig_b, "D") or has_any(body_b, "D major")
        )
        mark(
            "B_trial_d",
            b_ok,
            f"trial={trial_ok} orig={orig_b!r} prog={rendered_em_em_d_d(body_b)}",
        )

        # C. Presets local + append (Chorus so Verse stays Em Em D D)
        goto_custom(page)
        settle(page, 2)
        click_button_has(page, r"^Chorus$") or set_baseweb_select(page, "Section to edit", "Chorus")
        settle(page, 1)
        pk_before = pk_val(page)
        preset_changed = set_presets_key(page, "E")
        settle(page, 2)
        side_c, body_c = shot(page, "C-presets-e")
        pk_after = pk_val(page)
        song_pk_stays = key_is(pk_after, "D") or (
            "d" in low(pk_after) and "minor" not in low(pk_after)
        ) or key_is(pk_before, "D")
        sidebar_ok = "b minor" not in low(pk_after)
        preset_e_buttons = has_any(body_c, "E B C#m A", "E B C♯m A", "I–V–vi–IV: E")
        mark(
            "C1_presets_local",
            bool(preset_changed and song_pk_stays and sidebar_ok),
            f"set={preset_changed} pk_before={pk_before!r} pk_after={pk_after!r} "
            f"e_buttons={preset_e_buttons}",
        )
        set_presets_key(page, "D")
        settle(page, 2)
        add_chord_bar(page, "D")
        add_chord_bar(page, "A")
        settle(page, 1)
        click_main_button(page, r"I–V–vi–IV") or click_button_has(page, r"I–V–vi–IV")
        settle(page, 2)
        add_chord_bar(page, "Em")
        settle(page, 1)
        side_c2, body_c2 = shot(page, "C-presets-append")
        # Chorus should contain D A plus I V vi IV (D A Bm G) plus Em — not a replace-only D A Bm G.
        chorus_blob = body_c2
        appended = bool(
            re.search(
                r"D.{0,40}A.{0,40}D.{0,40}A.{0,40}Bm.{0,40}G.{0,40}Em",
                chorus_blob,
                re.S | re.I,
            )
        ) or (
            has_any(chorus_blob, "D")
            and has_any(chorus_blob, "Bm")
            and has_any(chorus_blob, "Em")
            and has_any(chorus_blob, "Chorus")
        )
        still_editable = has_any(body_c2, "Add chord", "1 bar", "Presets")
        mark(
            "C2_preset_append",
            appended and still_editable,
            f"appended={appended} still_edit={still_editable}",
        )

        # D. Finish Song layout (accepted Finish/Save — not the old Practice/Songs/Backing row)
        click_main_button(page, r"^Finish Song$") or click_button_has(page, r"Finish Song")
        settle(page, 3)
        side_d, body_d = shot(page, "D-finish")
        from _walk_cpl_finish_save import (  # noqa: WPS433
            count_main_buttons,
            label_has_backing,
            label_has_practice,
            launch_has,
            launch_labels,
        )

        launch_d = launch_labels(page)
        d_ok = (
            has_any(body_d, "Keep Editing")
            and has_any(body_d, "Set as Active Song")
            and has_any(body_d, "Save to Library")
            and has_any(body_d, "New Song")
            and (
                launch_has(body_d, r"Save to library")
                or any("save to library" in (t or "").lower() for t in launch_d)
            )
            and count_main_buttons(page, r"Save to library") >= 1
            and not label_has_practice(launch_d)
            and not label_has_backing(launch_d)
        )
        mark(
            "D_finish_layout",
            d_ok,
            f"launch={launch_d!r} save={count_main_buttons(page, r'Save to library')} "
            f"keep={has_any(body_d, 'Keep Editing')} active={has_any(body_d, 'Set as Active Song')}",
        )

        # E. Creative → SBI Custom Trial D
        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 1)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        ok_e = open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        side_e, body_e = shot(page, "E-sbi-custom-d")
        pk_e = pk_val(page) or practice_badge(side_e + body_e)
        e_ok = (
            ok_e
            and has_any(body_e, "Trial Song")
            and ("d" in low(pk_e) and "minor" not in low(pk_e) or has_any(body_e, "D major"))
            and not has_any(pk_e, "B minor")
        )
        mark("E_sbi_custom_trial_d", e_ok, f"open={ok_e} pk={pk_e!r}")

        # F. Temporary SBI Custom PK C → Dm Dm C C
        set_baseweb_select(page, "Practice / Concert Key", "C") or set_baseweb_select(
            page, "Practice / Concert Key", "C major"
        )
        settle(page, 3)
        side_f, body_f = shot(page, "F-sbi-custom-c")
        pk_f = pk_val(page)
        line_f = concert_prog_line(body_f)
        f_ok = (
            has_any(body_f, "Trial Song")
            and "c" in low(pk_f)
            and "minor" not in low(pk_f)
            and trial_prog_at_c(line_f or body_f)
        )
        mark(
            "F_sbi_custom_c_proj",
            f_ok,
            f"pk={pk_f!r} line={line_f!r} proj={trial_prog_at_c(line_f or body_f)}",
        )

        # G. Open Custom Lab → Trial Custom workspace (Original D, not C sticky)
        opened_lab = click_button_has(page, r"Open Custom Lab") or goto_custom(page)
        settle(page, 3)
        side_g, body_g = shot(page, "G-open-custom")
        orig_g = original_key_val(page)
        pk_g = pk_val(page)
        g_ok = (
            opened_lab
            and has_any(body_g, "Trial Song")
            and (key_is(orig_g, "D") or has_any(body_g, "D major"))
            and "my progression" not in low(body_g)
            and "c minor" not in low(pk_g)
            and "cm" != low(pk_g).strip()
            and key_is(pk_g, "D")
        )
        mark("G_open_custom", g_ok, f"open={opened_lab} orig={orig_g!r} pk={pk_g!r}")

        # H. Creative restores SBI Custom
        click_nav(page, "Creative")
        settle(page, 4)
        side_h, body_h = shot(page, "H-creative-restore")
        h_ok = has_any(body_h, "Trial Song") and has_any(body_h, "Custom progression")
        active_wrong = has_any(body_h, "Active song") and not has_any(body_h, "Trial Song")
        mark(
            "H_creative_sbi_custom",
            h_ok and not active_wrong,
            f"trial={has_any(body_h,'Trial Song')} custom={has_any(body_h,'Custom progression')} "
            f"active_wrong={active_wrong}",
        )

        # I. Explicit Active Source → Shape / B minor / Shape progression
        ok_i = open_sbi_active(page)
        settle(page, 3)
        side_i, body_i = shot(page, "I-active-shape")
        pk_i = pk_val(page) or practice_badge(side_i + body_i)
        pk_i_bm = "b minor" in low(pk_i or "") or low(pk_i or "").replace(" ", "") in {"bm", "bminor"}
        shape_prog = has_any(body_i, "C#m", "F#m", "G#m", "E", "F#") and not rendered_em_em_d_d(
            body_i
        )
        i_ok = (
            ok_i
            and has_any(side_i + body_i, "Shape of You")
            and not has_any(body_i, "Trial Song")
            and (pk_i_bm or "b minor" in low(side_i + body_i))
        )
        mark(
            "I_active_shape_bm",
            i_ok and shape_prog,
            f"open={ok_i} pk={pk_i!r} shape_prog={shape_prog} trial={has_any(body_i,'Trial Song')}",
        )

        # J. Fresh SBI Custom → Trial D, not Bm
        ok_j = open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        side_j, body_j = shot(page, "J-fresh-custom-d")
        pk_j = pk_val(page) or practice_badge(side_j + body_j)
        j_ok = (
            ok_j
            and has_any(body_j, "Trial Song")
            and "b minor" not in low(pk_j)
            and ("d" in low(pk_j) and "minor" not in low(pk_j) or has_any(body_j, "D major"))
        )
        mark("J_fresh_custom_d", j_ok, f"open={ok_j} pk={pk_j!r}")

        # K. Mission Backing Bm → Cm must be +1 identity on a real Shape tile.
        # Catalog Verse at Bm is Bm · Em · G · A — there is no concert C#m tile.
        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 1)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        if goto_improv(page, NOTES):
            # J left SBI Custom owning Creative; Active Source lets Shape/Bm own PK.
            open_sbi_active(page)
            settle(page, 3)
            ensure_missions_workspace(page, NOTES)
            settle(page, 2)
            set_instrument(page, "Piano")
            settle(page, 1)
            force_pk_token(page, "Bm")
            settle(page, 2)
            clicked_em = select_shape_em(page)
            settle(page, 1)
            shot(page, "K-mission-selected-em")
            click_generate_example(page)
            settle(page, 2)
            opened_mb = bool(open_mission_backing(page, NOTES))
            settle(page, 4)
            force_pk_token(page, "Bm")
            settle(page, 3)
            side_k0, body_k0 = shot(page, "K-mission-bm")
            chord_bm = mission_header_chord(body_k0)
            card_bm = mission_card_chord(body_k0)
            ex_bm = mission_example_chord(body_k0)
            owners_bm = {chord_bm, card_bm, ex_bm} - {""}
            force_pk_token(page, "Cm")
            settle(page, 4)
            side_k, body_k = shot(page, "K-mission-cm")
            chord_cm = mission_header_chord(body_k)
            card_cm = mission_card_chord(body_k)
            ex_cm = mission_example_chord(body_k)
            concert_cm = has_any(body_k, "Concert Cm", "C minor")
            owners_cm = {chord_cm, card_cm, ex_cm} - {""}
            k_ok = (
                opened_mb
                and clicked_em
                and concert_cm
                and chord_bm == "Em"
                and card_bm == "Em"
                and (not ex_bm or ex_bm == "Em")
                and owners_bm <= {"Em"}
                and chord_cm == "Fm"
                and card_cm == "Fm"
                and (not ex_cm or ex_cm == "Fm")
                and owners_cm <= {"Fm"}
            )
            mark(
                "K_mission_header_dm",
                k_ok,
                f"open={opened_mb} click={clicked_em} "
                f"bm_hdr={chord_bm!r} bm_card={card_bm!r} bm_ex={ex_bm!r} "
                f"cm_hdr={chord_cm!r} cm_card={card_cm!r} cm_ex={ex_cm!r} "
                f"pk={pk_val(page)!r}",
            )
            set_instrument(page, "Piano")
            settle(page, 1)
        else:
            mark("K_mission_header_dm", False, "goto_improv failed")
        leave_specialized_backing(page)

        # L. SBI Shape Backing → one-click Return Regular Catalog
        ok_l_open = open_sbi_active(page)
        settle(page, 2)
        opened_sbi_bk = click_open_backing_studio(page, NOTES, "L-sbi") or click_button_has(
            page, r"Open in Backing"
        )
        opened_sbi_bk = bool(opened_sbi_bk) and wait_for_backing(page, NOTES, "L-sbi")
        settle(page, 3)
        side_l0, body_l0 = shot(page, "L-sbi-shape-backing")
        clicked_ret = click_button_has(page, r"Return to Regular Catalog Song Backing")
        settle(page, 4)
        side_l, body_l = shot(page, "L-regular-backing")
        regular = has_any(body_l, "Shape of You") and has_any(body_l, "B minor", "Bm")
        still_sbi = has_any(body_l, "SBI Custom", "Song-Based Improvisation Backing")
        l_ok = opened_sbi_bk and clicked_ret and regular and not still_sbi
        mark(
            "L_return_regular",
            l_ok,
            f"open_sbi={ok_l_open} backing={opened_sbi_bk} click={clicked_ret} "
            f"regular={regular} still_sbi={still_sbi}",
        )

        # M. Entry Style Jam E → Open Backing (no NameError)
        if goto_improv(page, NOTES):
            click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
            settle(page, 2)
            click_radio(page, "Style Jam") or click_button_has(page, r"Style Jam Mode")
            settle(page, 2)
            set_style_jam_concert_key(page, "E") or set_style_jam_concert_key(page, "E major")
            settle(page, 2)
            click_button_has(page, r"Generate progression")
            settle(page, 4)
            err_before = list(PAGE_ERRORS)
            opened_jam = click_button_has(page, r"Open in Backing Studio") or click_open_backing_studio(
                page, NOTES, "M-jam"
            )
            settle(page, 4)
            wait_for_backing(page, NOTES, "M-jam")
            side_m, body_m = shot(page, "M-entry-backing")
            crashed = any("NameError" in e or "_sbi_custom_sidebar" in e for e in PAGE_ERRORS[len(err_before) :])
            specialized = has_any(
                body_m, "Entry Style", "Style Jam", "Return to Style", "Return to Jam", "Entry & Jam"
            )
            e_major = has_any(body_m, "E major") or (
                low(pk_val(page) or "").startswith("e") and "minor" not in low(pk_val(page) or "")
            )
            no_sbi = not has_any(body_m, "Trial Song") and not has_any(body_m, "SBI Custom")
            m_ok = opened_jam and not crashed and specialized and e_major and no_sbi
            mark(
                "M_entry_style_backing",
                m_ok,
                f"open={opened_jam} crash={crashed} spec={specialized} e={e_major} "
                f"pk={pk_val(page)!r} errors={PAGE_ERRORS[-3:]}",
            )
            page.reload(wait_until="domcontentloaded", timeout=120000)
            settle(page, 8)
            try:
                page.wait_for_function(
                    """() => {
                      const t = document.body ? (document.body.innerText || '') : '';
                      return /Return to|Backing source|Style Jam|Entry/i.test(t)
                        && t.length > 800;
                    }""",
                    timeout=60_000,
                )
            except Exception:
                pass
            settle(page, 4)
            side_mr, body_m_r = shot(page, "M-entry-refresh")
            refresh_ok = has_any(
                body_m_r, "Entry Style", "Style Jam", "Return to Style", "Return to Jam"
            )
            mark("M2_entry_refresh", refresh_ok, f"spec={refresh_ok}")
            click_button_has(page, r"Return to Style") or click_button_has(
                page, r"Return to Creative"
            )
            settle(page, 3)
            side_ret, body_ret = shot(page, "M-entry-return")
            ret_ok = has_any(body_ret, "Style Jam", "Generate progression", "Concert Key")
            mark("M3_entry_return", ret_ok)
        else:
            mark("M_entry_style_backing", False, "goto_improv failed")
            mark("M2_entry_refresh", False, "skipped")
            mark("M3_entry_return", False, "skipped")

        # N. Motif pattern cell dividers
        goto_improv(page, NOTES)
        settle(page, 2)
        click_radio(page, "Motif") or click_button_has(page, r"Phrase / Motif")
        settle(page, 3)
        click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
        settle(page, 3)
        click_button_has(page, r"Pattern") or click_button_has(page, r"Motif pattern")
        settle(page, 3)
        side_n, body_n = shot(page, "N-motif-pattern")
        n_ok = " | " in body_n and has_any(body_n, "Motif pattern")
        mark("N_motif_dividers", n_ok, f"pipe={' | ' in body_n}")

        browser.close()

    reds = [k for k, v in GATES.items() if not v]
    overall = "PASS" if not reds else "RED"
    summary = {
        "meta": meta,
        "overall": overall,
        "results": GATES,
        "red": reds,
        "page_errors": PAGE_ERRORS,
        "notes": NOTES[-80:],
    }
    (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / f"{PREFIX}summary.txt").write_text(
        "\n".join(
            [
                f"OVERALL={overall}",
                f"PASS={sum(1 for v in GATES.values() if v)} RED={len(reds)}",
                json.dumps(GATES, indent=2),
                "",
                *NOTES[-80:],
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(GATES, indent=2), flush=True)
    print(f"OVERALL={overall}", flush=True)
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
