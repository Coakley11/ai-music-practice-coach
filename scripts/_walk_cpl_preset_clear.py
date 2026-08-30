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


def has_seq(body: str, chords: list[str], *, section: str = "Verse") -> bool:
    """Match bar-chart / song-structure chord order, not compact preset button labels."""
    chunk = _region(body, f"{section} Progression", r"¼ bar|1/4 bar|Presets\b")
    extra = _region(body, f"{section}:", r"Launch in the studio|Chorus:|Verse:|Bridge:")
    compact = re.sub(r"[\s|·\-–]+", " ", chunk + "\n" + extra)
    if not compact.strip():
        compact = re.sub(r"[\s|·\-–]+", " ", body or "")
    pat = r"\s+".join(re.escape(c) for c in chords)
    return bool(re.search(pat, compact))


def is_d_major(text: str) -> bool:
    t = (text or "").lower()
    return "d major" in t or bool(re.search(r"\bpractice / concert key\s*\n\s*d\s+major", t))


def set_section(page: Page, name: str) -> bool:
    from walk_creative_backing_matrix import set_baseweb_select

    return bool(set_baseweb_select(page, "Section to edit", name))


def click_preset(page: Page, needle: str) -> bool:
    loc = page.locator('[data-testid="stAppViewContainer"] button').filter(
        has_text=re.compile(re.escape(needle), re.I)
    )
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if el.is_visible():
                el.scroll_into_view_if_needed()
                el.click(timeout=5000)
                wait_idle(page, 4000)
                return True
        except Exception:
            continue
    return click_button_has(page, needle)


def click_clear_section(page: Page) -> bool:
    loc = page.get_by_role("button", name=re.compile(r"^Clear section$", re.I))
    if loc.count():
        try:
            loc.first.scroll_into_view_if_needed()
            loc.first.click(timeout=5000)
            wait_idle(page, 4000)
            return True
        except Exception:
            pass
    return click_button_has(page, r"^Clear section$")


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
        set_presets_key(page, "C")
        wait_idle(page, 2000)
        click_preset(page, "C G Am F") or click_preset(page, "I–V–vi–IV")
        wait_idle(page, 3000)
        body_a = shot(page, "A-preset-c")
        GATES["A_preset_c_family"] = has_seq(body_a, ["C", "G", "Am", "F"]) and not has_seq(
            body_a, ["D", "A", "Bm", "G"]
        )
        GATES["B_song_pk_stays_d"] = is_d_major(body_a) or (pk_val(page) in {"D", "D major"})
        log(f"A c-family={GATES['A_preset_c_family']} pk_d={GATES['B_song_pk_stays_d']}")

        # C. existing + preset + manual: start from Em A then C-preset then Dm
        click_clear_section(page)
        wait_idle(page, 2500)
        add_chord_bar(page, "Em")
        add_chord_bar(page, "A")
        set_presets_key(page, "C")
        click_preset(page, "C G Am F") or click_preset(page, "I–V–vi–IV")
        wait_idle(page, 2500)
        add_chord_bar(page, "Dm")
        body_c = shot(page, "C-existing-preset-manual")
        GATES["C_existing_plus_preset_manual"] = has_seq(
            body_c, ["Em", "A", "C", "G", "Am", "F", "Dm"]
        )
        log(f"C mixed={GATES['C_existing_plus_preset_manual']}")

        # E-major preset after clear
        click_clear_section(page)
        wait_idle(page, 2500)
        set_presets_key(page, "E")
        wait_idle(page, 2000)
        click_preset(page, "E B C#m A") or click_preset(page, "I–V–vi–IV")
        wait_idle(page, 3000)
        body_e = shot(page, "E-preset-e")
        GATES["E_preset_e_family"] = has_seq(body_e, ["E", "B", "C#m", "A"]) or has_seq(
            body_e, ["E", "B", "C♯m", "A"]
        )
        GATES["E_song_pk_stays_d"] = is_d_major(body_e) or (pk_val(page) in {"D", "D major"})
        log(f"E e-family={GATES['E_preset_e_family']} pk_d={GATES['E_song_pk_stays_d']}")

        # F-family
        click_clear_section(page)
        wait_idle(page, 2500)
        set_presets_key(page, "F")
        wait_idle(page, 2000)
        click_preset(page, "F C Dm Bb") or click_preset(page, "I–V–vi–IV")
        wait_idle(page, 3000)
        body_f = shot(page, "F-preset-f")
        GATES["F_preset_f_family"] = has_seq(body_f, ["F", "C", "Dm", "Bb"]) or has_seq(
            body_f, ["F", "C", "Dm", "B♭"]
        )
        log(f"F f-family={GATES['F_preset_f_family']}")

        # D/G. Clear Section + refresh
        click_clear_section(page)
        wait_idle(page, 3000)
        body_d = shot(page, "D-cleared")
        GATES["D_clear_empties"] = not has_seq(body_d, ["F", "C", "Dm", "Bb"]) and not has_seq(
            body_d, ["C", "G", "Am", "F"]
        )
        log(f"D cleared={GATES['D_clear_empties']}")

        # Isolation: Verse vs Chorus
        set_section(page, "Verse")
        set_presets_key(page, "C")
        click_preset(page, "C G Am F") or click_preset(page, "I–V–vi–IV")
        wait_idle(page, 2500)
        set_section(page, "Chorus")
        add_chord_bar(page, "D")
        add_chord_bar(page, "G")
        add_chord_bar(page, "A")
        body_ch = shot(page, "iso-chorus-filled")
        set_section(page, "Verse")
        wait_idle(page, 2000)
        click_clear_section(page)
        wait_idle(page, 2500)
        body_v = shot(page, "iso-verse-cleared")
        verse_empty = not has_seq(body_v, ["C", "G", "Am", "F"], section="Verse")
        set_section(page, "Chorus")
        wait_idle(page, 2000)
        body_ch2 = shot(page, "iso-chorus-untouched")
        chorus_kept = has_seq(body_ch2, ["D", "G", "A"], section="Chorus")
        set_presets_key(page, "C")
        click_preset(page, "C G Am F") or click_preset(page, "I–V–vi–IV")
        wait_idle(page, 2500)
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
        click_clear_section(page)
        wait_idle(page, 2500)
        set_presets_key(page, "C")
        click_preset(page, "C G Am F") or click_preset(page, "I–V–vi–IV")
        wait_idle(page, 2500)
        add_chord_bar(page, "Dm")
        body_f2 = shot(page, "F-clear-preset-manual")
        GATES["F_clear_preset_manual"] = has_seq(body_f2, ["C", "G", "Am", "F", "Dm"])
        log(f"F clear-preset-manual={GATES['F_clear_preset_manual']}")

        # G. refresh
        page.reload(wait_until="domcontentloaded", timeout=180000)
        wait_idle(page, 6000)
        goto_custom(page)
        wait_idle(page, 3000)
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
