"""Browser proof: Presets key append + Clear Section (human embargo still ON).

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8570
  python scripts/_walk_cpl_preset_clear.py http://127.0.0.1:8570
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import click_button_has, click_nav, wait_idle  # noqa: E402
from _walk_custom_practice_key import goto_custom, pk_val, set_original_key, set_practice_key  # noqa: E402
from _walk_custom_page_owner_basics import set_presets_key  # noqa: E402
from _walk_ownership_audit_full import add_chord_bar, fill_title  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8570"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "cpl-preset-clear-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def _git() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]

    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(root), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "url": URL,
    }


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body[:18000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    return body


def _region(body: str, start: str, end_pat: str) -> str:
    text = body or ""
    idx = text.find(start)
    if idx < 0:
        return ""
    chunk = text[idx:]
    m = re.search(end_pat, chunk[len(start) :], re.I)
    if m:
        return chunk[: len(start) + m.start()]
    return chunk[:1200]


def _norm_syms(text: str) -> str:
    return (text or "").replace("♯", "#").replace("♭", "b")


def has_seq(body: str, chords: list[str], *, section: str = "Verse") -> bool:
    """Match bar-chart / song-structure chord order, not compact preset button labels."""
    chunk = _region(body, f"{section} Progression", r"¼ bar|1/4 bar|Presets\b")
    extra = _region(body, f"{section}:", r"Launch in the studio|Chorus:|Verse:|Bridge:")
    compact = _norm_syms(re.sub(r"[\s|·\-–]+", " ", chunk + "\n" + extra))
    if not compact.strip():
        compact = _norm_syms(re.sub(r"[\s|·\-–]+", " ", body or ""))
    pat = r"\s+".join(re.escape(_norm_syms(c)) for c in chords)
    return bool(re.search(pat, compact))


def is_d_major(text: str) -> bool:
    t = (text or "").lower()
    return "d major" in t or bool(re.search(r"\bpractice / concert key\s*\n\s*d\s+major", t))


def wait_pred(page: Page, pred, timeout_s: float = 30.0) -> str:
    """Poll the live page until pred(body) is true. Streamlit reruns can exceed wait_idle."""
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        last = page.inner_text("body") or ""
        try:
            if pred(last):
                return last
        except Exception:
            pass
        page.wait_for_timeout(400)
    return last


def wait_seq(page: Page, chords: list[str], *, section: str = "Verse", timeout_s: float = 30.0) -> str:
    return wait_pred(page, lambda b: has_seq(b, chords, section=section), timeout_s=timeout_s)


def wait_seq_gone(page: Page, chords: list[str], *, section: str = "Verse", timeout_s: float = 30.0) -> str:
    return wait_pred(page, lambda b: not has_seq(b, chords, section=section), timeout_s=timeout_s)


def wait_presets_key_caption(page: Page, token: str, timeout_s: float = 20.0) -> bool:
    needle = str(token or "").strip()
    if not needle:
        return False

    def _ok(body: str) -> bool:
        t = (body or "").lower()
        return f"preset buttons use {needle.lower()}" in t

    body = wait_pred(page, _ok, timeout_s=timeout_s)
    return _ok(body)


def choose_presets_key(page: Page, token: str) -> bool:
    ok = bool(set_presets_key(page, token))
    landed = wait_presets_key_caption(page, token)
    return bool(ok and landed)


def set_section(page: Page, name: str) -> bool:
    from walk_creative_backing_matrix import set_baseweb_select

    ok = bool(set_baseweb_select(page, "Section to edit", name))
    wait_pred(
        page,
        lambda b: f"appends to {name}" in (b or ""),
        timeout_s=20.0,
    )
    return ok


def click_preset(page: Page, needle: str, expect: list[str] | None = None, section: str = "Verse") -> bool:
    loc = page.locator('[data-testid="stAppViewContainer"] button').filter(
        has_text=re.compile(re.escape(needle), re.I)
    )
    clicked = False
    for i in range(loc.count() - 1, -1, -1):
        el = loc.nth(i)
        try:
            if el.is_visible():
                el.scroll_into_view_if_needed()
                el.click(timeout=5000)
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        clicked = bool(click_button_has(page, needle))
    if clicked and expect:
        wait_seq(page, expect, section=section, timeout_s=30.0)
    elif clicked:
        wait_idle(page, 2500)
    return clicked


def click_clear_section(page: Page, gone: list[str] | None = None, section: str = "Verse") -> bool:
    loc = page.get_by_role("button", name=re.compile(r"^Clear section$", re.I))
    ok = False
    if loc.count():
        try:
            loc.first.scroll_into_view_if_needed()
            loc.first.click(timeout=5000)
            ok = True
        except Exception:
            pass
    if not ok:
        ok = bool(click_button_has(page, r"^Clear section$"))
    if ok and gone:
        wait_seq_gone(page, gone, section=section, timeout_s=30.0)
    elif ok:
        wait_idle(page, 2500)
    return ok


def add_manual_chord(page: Page, chord: str, expect: list[str], *, section: str = "Verse") -> bool:
    """Chip or Custom-chord fallback, then wait until the section shows expect."""
    add_chord_bar(page, chord)
    body = wait_seq(page, expect, section=section, timeout_s=12.0)
    if has_seq(body, expect, section=section):
        return True
    try:
        inp = page.get_by_label(re.compile(r"^Custom chord$", re.I))
        if inp.count() == 0:
            inp = page.locator('input[placeholder*="Cmaj7"]')
        if inp.count() > 0:
            inp.first.click(timeout=4000)
            inp.first.fill(chord)
            inp.first.press("Tab")
            wait_idle(page, 1200)
            click_button_has(page, r"^Use chord$")
            wait_idle(page, 1200)
            click_button_has(page, r"^1 bar$")
            wait_seq(page, expect, section=section, timeout_s=20.0)
    except Exception:
        pass
    return has_seq(page.inner_text("body") or "", expect, section=section)


def server_reachable() -> str:
    try:
        urllib.request.urlopen(URL, timeout=5)
        return "up"
    except Exception as exc:
        return f"down:{exc!r}"


def main() -> int:
    meta = _git()
    print(json.dumps(meta), flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 980})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        wait_idle(page, 5000)

        ok_custom = goto_custom(page)
        click_button_has(page, r"New song") or click_button_has(page, r"New Song")
        wait_idle(page, 2500)
        fill_title(page, "Preset Clear Song")
        set_original_key(page, "D") or set_original_key(page, "D major")
        set_practice_key(page, "D")
        wait_idle(page, 2000)
        body0 = shot(page, "00-new-d")
        song_d = is_d_major(body0) or (pk_val(page) in {"D", "D major"})
        GATES["setup_song_d"] = bool(ok_custom and song_d)
        log(f"setup custom={ok_custom} song_d={song_d} pk={pk_val(page)!r}")

        # A. Presets C → I–V–vi–IV appends C G Am F
        choose_presets_key(page, "C")
        click_preset(page, "C G Am F", expect=["C", "G", "Am", "F"]) or click_preset(
            page, "I–V–vi–IV", expect=["C", "G", "Am", "F"]
        )
        body_a = shot(page, "A-preset-c")
        GATES["A_preset_c_family"] = has_seq(body_a, ["C", "G", "Am", "F"]) and not has_seq(
            body_a, ["D", "A", "Bm", "G"]
        )
        GATES["B_song_pk_stays_d"] = is_d_major(body_a) or (pk_val(page) in {"D", "D major"})
        log(f"A c-family={GATES['A_preset_c_family']} pk_d={GATES['B_song_pk_stays_d']}")

        # C. existing + preset + manual: start from Em A then C-preset then Dm
        click_clear_section(page, gone=["C", "G", "Am", "F"])
        add_manual_chord(page, "Em", ["Em"])
        add_manual_chord(page, "A", ["Em", "A"])
        choose_presets_key(page, "C")
        click_preset(
            page, "C G Am F", expect=["Em", "A", "C", "G", "Am", "F"]
        ) or click_preset(page, "I–V–vi–IV", expect=["Em", "A", "C", "G", "Am", "F"])
        add_manual_chord(page, "Dm", ["Em", "A", "C", "G", "Am", "F", "Dm"])
        body_c = shot(page, "C-existing-preset-manual")
        GATES["C_existing_plus_preset_manual"] = has_seq(
            body_c, ["Em", "A", "C", "G", "Am", "F", "Dm"]
        )
        log(f"C mixed={GATES['C_existing_plus_preset_manual']}")

        # E-major preset after clear
        click_clear_section(page, gone=["Em", "A", "C", "G", "Am", "F"])
        choose_presets_key(page, "E")
        click_preset(page, "E B C#m A", expect=["E", "B", "C#m", "A"]) or click_preset(
            page, "I–V–vi–IV", expect=["E", "B"]
        )
        body_e = shot(page, "E-preset-e")
        GATES["E_preset_e_family"] = has_seq(body_e, ["E", "B", "C#m", "A"]) or has_seq(
            body_e, ["E", "B", "C♯m", "A"]
        )
        GATES["E_song_pk_stays_d"] = is_d_major(body_e) or (pk_val(page) in {"D", "D major"})
        log(f"E e-family={GATES['E_preset_e_family']} pk_d={GATES['E_song_pk_stays_d']}")

        # F-family
        click_clear_section(page, gone=["E", "B"])
        choose_presets_key(page, "F")
        click_preset(page, "F C Dm Bb", expect=["F", "C", "Dm", "Bb"]) or click_preset(
            page, "I–V–vi–IV", expect=["F", "C", "Dm"]
        )
        body_f = shot(page, "F-preset-f")
        GATES["F_preset_f_family"] = has_seq(body_f, ["F", "C", "Dm", "Bb"]) or has_seq(
            body_f, ["F", "C", "Dm", "B♭"]
        )
        log(f"F f-family={GATES['F_preset_f_family']}")

        # D/G. Clear Section + refresh
        click_clear_section(page, gone=["F", "C", "Dm"])
        body_d = shot(page, "D-cleared")
        GATES["D_clear_empties"] = not has_seq(body_d, ["F", "C", "Dm", "Bb"]) and not has_seq(
            body_d, ["C", "G", "Am", "F"]
        )
        log(f"D cleared={GATES['D_clear_empties']}")

        # Isolation: Verse vs Chorus
        set_section(page, "Verse")
        choose_presets_key(page, "C")
        click_preset(page, "C G Am F", expect=["C", "G", "Am", "F"]) or click_preset(
            page, "I–V–vi–IV", expect=["C", "G", "Am", "F"]
        )
        set_section(page, "Chorus")
        add_manual_chord(page, "D", ["D"], section="Chorus")
        add_manual_chord(page, "G", ["D", "G"], section="Chorus")
        add_manual_chord(page, "A", ["D", "G", "A"], section="Chorus")
        body_ch = shot(page, "iso-chorus-filled")
        set_section(page, "Verse")
        click_clear_section(page, gone=["C", "G", "Am", "F"], section="Verse")
        body_v = shot(page, "iso-verse-cleared")
        verse_empty = not has_seq(body_v, ["C", "G", "Am", "F"], section="Verse")
        set_section(page, "Chorus")
        body_ch2 = shot(page, "iso-chorus-untouched")
        chorus_kept = has_seq(body_ch2, ["D", "G", "A"], section="Chorus")
        choose_presets_key(page, "C")
        click_preset(
            page, "C G Am F", expect=["D", "G", "A", "C", "G", "Am", "F"], section="Chorus"
        ) or click_preset(
            page, "I–V–vi–IV", expect=["C", "G", "Am", "F"], section="Chorus"
        )
        body_ch3 = shot(page, "iso-chorus-appended")
        chorus_appended = has_seq(
            body_ch3, ["D", "G", "A", "C", "G", "Am", "F"], section="Chorus"
        ) or (
            has_seq(body_ch3, ["D", "G", "A"], section="Chorus")
            and has_seq(body_ch3, ["C", "G", "Am", "F"], section="Chorus")
        )
        GATES["iso_verse_cleared"] = verse_empty
        GATES["iso_chorus_kept"] = chorus_kept
        GATES["iso_chorus_append"] = chorus_appended
        log(
            f"iso verse_empty={verse_empty} chorus_kept={chorus_kept} "
            f"chorus_append={chorus_appended} "
            f"chorus_pre={has_seq(body_ch, ['D', 'G', 'A'], section='Chorus')}"
        )

        # F. Clear → preset C → manual Dm
        set_section(page, "Verse")
        click_clear_section(page, gone=["C", "G", "Am", "F"])
        choose_presets_key(page, "C")
        click_preset(page, "C G Am F", expect=["C", "G", "Am", "F"]) or click_preset(
            page, "I–V–vi–IV", expect=["C", "G", "Am", "F"]
        )
        add_manual_chord(page, "Dm", ["C", "G", "Am", "F", "Dm"])
        body_f2 = shot(page, "F-clear-preset-manual")
        GATES["F_clear_preset_manual"] = has_seq(body_f2, ["C", "G", "Am", "F", "Dm"])
        log(f"F clear-preset-manual={GATES['F_clear_preset_manual']}")

        # G. refresh
        log(f"pre_reload_server={server_reachable()}")
        try:
            page.reload(wait_until="domcontentloaded", timeout=180000)
        except Exception as exc:
            log(f"reload_exc={exc!r}")
            log(f"post_reload_server={server_reachable()}")
            raise
        wait_idle(page, 6000)
        goto_custom(page)
        wait_idle(page, 3000)
        wait_seq(page, ["C", "G", "Am", "F", "Dm"], timeout_s=30.0)
        body_g = shot(page, "G-refresh")
        GATES["G_refresh_keeps_cleared_or_current"] = has_seq(
            body_g, ["C", "G", "Am", "F", "Dm"]
        ) and not has_seq(body_g, ["D", "A", "Bm", "G"])
        log(f"G refresh={GATES['G_refresh_keeps_cleared_or_current']}")

        browser.close()

    failed = [k for k, v in GATES.items() if not v]
    print(json.dumps(GATES, indent=2), flush=True)
    print("FAILED:" if failed else "ALL_PASS", failed or [], flush=True)
    (OUT / f"{PREFIX}summary.txt").write_text(
        json.dumps({"meta": meta, "gates": GATES, "failed": failed, "notes": NOTES}, indent=2),
        encoding="utf-8",
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
