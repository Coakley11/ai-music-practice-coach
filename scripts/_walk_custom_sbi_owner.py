"""Custom SBI + Custom SBI Backing owner walk (embargo still on).

Continues from Shape GA Bm + LAST_CUSTOM Trial (Original D, PK E if set).

Usage:
  python scripts/_walk_custom_sbi_owner.py http://127.0.0.1:8541
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
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
    expand_sidebar,
    set_baseweb_select,
    wait_for_backing,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_custom_practice_key import goto_custom, pk_val  # noqa: E402
from _walk_ownership_audit_full import (  # noqa: E402
    build_trial_song,
    rendered_em_em_d_d,
)
from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_core_workflows_embargo import (  # noqa: E402
    hard_reboot_streamlit,
    open_sbi_active,
    practice_badge,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8541"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "sbi-owner-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def low(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("♯", "#").replace("♭", "b"))


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


def has_any(text: str, *needles: str) -> bool:
    b = low(text)
    return any(n.lower() in b for n in needles)


def concert_prog_line(text: str) -> str:
    m = re.search(r"Concert Practice Key Progression:\s*([^\n]+)", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"Progression:\s*Verse\s*[·•]\s*([^\n]+)", text)
    return m.group(1).strip() if m else ""


def practice_concert_line(text: str) -> str:
    m = re.search(r"Practice concert key:\s*([^\n·]+)", text, flags=re.I)
    return (m.group(1) if m else "").strip()


def card_key_is_original_d(text: str) -> bool:
    line = low(practice_concert_line(text))
    return bool(line) and "d major" in line


def trial_prog_at_d(text: str) -> bool:
    return rendered_em_em_d_d(text) or bool(
        re.search(r"Em.{0,40}Em.{0,40}(?<![A-G#b])D\b.{0,40}(?<![A-G#b])D\b", text, re.S)
    )


def trial_prog_at_c(text: str) -> bool:
    """D: Em Em D D  →  C: Dm Dm C C."""
    return bool(re.search(r"Dm.{0,40}Dm.{0,40}(?<![A-G#b])C\b.{0,40}(?<![A-G#b])C\b", text, re.S))


def trial_prog_at_f(text: str) -> bool:
    """D: Em Em D D  →  F: Gm Gm F F."""
    return bool(re.search(r"Gm.{0,40}Gm.{0,40}(?<![A-G#b])F\b.{0,40}(?<![A-G#b])F\b", text, re.S))


def trial_prog_at_e(text: str) -> bool:
    """D: Em Em D D  →  E: F#m F#m E E."""
    if re.search(r"F#m.{0,40}F#m.{0,40}(?<![A-G#b])E\b.{0,40}(?<![A-G#b])E\b", text, re.S):
        return True
    if re.search(r"F#m\s*[·•–\-]\s*F#m\s*[·•–\-]\s*E\s*[·•–\-]\s*E", text):
        return True
    return False


def shape_bleed(text: str) -> bool:
    t = low(text)
    if "trial song" in t and re.search(r"\bb minor\b", t):
        # Sidebar GA Shape caption is OK; reject if Custom/SBI PK is B minor.
        if re.search(r"practice\s*/\s*concert key[^\n]{0,80}b minor", t):
            return True
        if re.search(r"concert practice key progression:[^\n]*b minor", t):
            return True
    return False


def ensure_shape_and_trial(page: Page, notes: list[str]) -> None:
    click_nav(page, "Songs")
    settle(page, 2)
    click_button_has(page, r"Use catalog song instead")
    settle(page, 2)
    pick_song(page, notes, "Shape of You", "Pop")
    settle(page, 2)
    set_songs_practice_key(page, "Bm")
    settle(page, 2)
    body = page.inner_text("body") or ""
    if "Trial Song" not in body:
        build_trial_song(page, notes)
        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 2)
        pick_song(page, notes, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)


def main() -> int:
    notes = NOTES
    port = 8541
    m = re.search(r":(\d+)", URL)
    if m:
        port = int(m.group(1))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        ensure_shape_and_trial(page, notes)
        side0, body0 = shot(page, "00-seed")
        mark(
            "seed_shape",
            "shape of you" in low(side0 + body0) and has_any(side0 + body0, "B minor", "Bm"),
            f"side_pk={pk_val(page)!r}",
        )

        # Ensure Trial PK is E on Custom (prior walk end-state) then return Shape GA.
        goto_custom(page)
        settle(page, 3)
        set_baseweb_select(page, "Practice / Concert Key", "E major") or set_baseweb_select(
            page, "Practice / Concert Key", "E"
        )
        settle(page, 3)
        side_t, body_t = shot(page, "00b-trial-e")
        trial_e = has_any(body_t, "Trial Song") and (
            low(pk_val(page)).startswith("e") or "e major" in low(body_t)
        )
        mark("seed_trial_e", trial_e, f"pk={pk_val(page)!r} prog_e={trial_prog_at_e(body_t)}")
        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 2)
        pick_song(page, notes, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)

        # 1. SBI Active = Shape, not Trial
        for _try in range(3):
            ok_a = open_sbi_active(page)
            settle(page, 3)
            body_try = page.inner_text("body") or ""
            if has_any(body_try, "Shape of You") and not has_any(body_try, "Trial Song"):
                break
            if has_any(body_try, "CUSTOM PROGRESSION") or has_any(body_try, "Trial Song"):
                continue
        side1, body1 = shot(page, "01-sbi-active")
        blob1 = side1 + body1
        active_ok = (
            ok_a
            and has_any(blob1, "Shape of You")
            and not has_any(body1, "Trial Song")
            and "my progression" not in low(body1)
            and has_any(body1, "ACTIVE SONG")
        )
        mark(
            "1_sbi_active",
            active_ok,
            f"open={ok_a} shape={has_any(blob1,'Shape of You')} trial={has_any(body1,'Trial Song')}",
        )

        # 2. SBI Custom = Trial, current PK, projected prog, no Shape Bm PK
        ok_c = open_sbi_custom_source(page, notes)
        settle(page, 3)
        side2, body2 = shot(page, "02-sbi-custom")
        pk2 = pk_val(page) or practice_badge(body2)
        line2 = concert_prog_line(body2)
        pk2_e = "e" in low(pk2) and "minor" not in low(pk2)
        prog2 = trial_prog_at_e(line2 or body2)
        stale_orig = trial_prog_at_d(line2) and not trial_prog_at_e(line2)
        custom_ok = (
            ok_c
            and has_any(body2, "Trial Song")
            and not has_any(body2, "My Progression")
            and prog2
            and pk2_e
            and not stale_orig
            and not shape_bleed(side2 + body2)
            and "b minor" not in low(pk2)
        )
        mark(
            "2_sbi_custom",
            custom_ok,
            f"open={ok_c} pk={pk2!r} line={line2!r} prog_e={prog2} stale_d={stale_orig}",
        )

        # 3. Change Custom SBI PK once
        before = pk2
        set_baseweb_select(page, "Practice / Concert Key", "F") or set_baseweb_select(
            page, "Practice / Concert Key", "F major"
        )
        settle(page, 3)
        side3, body3 = shot(page, "03-sbi-custom-pk")
        pk3 = pk_val(page) or practice_badge(body3)
        line3 = concert_prog_line(body3)
        pk_moved = low(pk3).startswith("f") and "minor" not in low(pk3)
        transposed = trial_prog_at_f(line3 or body3) and not trial_prog_at_d(line3)
        still_trial = has_any(body3, "Trial Song")
        mark(
            "3_sbi_custom_pk",
            pk_moved and still_trial and transposed and not shape_bleed(side3 + body3),
            f"before={before!r} after={pk3!r} line={line3!r} transposed={transposed}",
        )

        ok_a2 = open_sbi_active(page)
        settle(page, 3)
        side_a2, body_a2 = shot(page, "03b-sbi-active-after-pk")
        mark(
            "3b_sbi_active_shape",
            ok_a2 and has_any(side_a2 + body_a2, "Shape of You") and not has_any(body_a2, "Trial Song"),
            f"shape={has_any(side_a2+body_a2,'Shape of You')}",
        )
        open_sbi_custom_source(page, notes)
        settle(page, 3)
        side_c2, body_c2 = shot(page, "03c-sbi-custom-return")
        mark(
            "3c_sbi_custom_return",
            has_any(body_c2, "Trial Song") and trial_prog_at_f(concert_prog_line(body_c2) or body_c2),
            f"pk={pk_val(page)!r} line={concert_prog_line(body_c2)!r}",
        )

        # 4. Open Custom Lab from SBI Custom
        opened_lab = click_button_has(page, r"Open Custom Lab") or goto_custom(page)
        settle(page, 3)
        side4, body4 = shot(page, "04-open-custom-lab")
        presets = bool(
            page.locator('[data-testid="stSelectbox"]').filter(
                has_text=re.compile(r"Presets key", re.I)
            ).count()
        )
        custom_lab_ok = (
            opened_lab
            and has_any(body4, "Trial Song")
            and has_any(body4, "D major")
            and presets
            and "my progression" not in low(body4)
            and "e minor" not in low(body4.split("PREVIEW")[-1] if "PREVIEW" in body4 else body4)
            and (
                low(pk_val(page) or "").startswith("f")
                or "f major" in low(body4)
            )
        )
        mark(
            "4_open_custom_lab",
            custom_lab_ok,
            f"presets={presets} pk={pk_val(page)!r}",
        )
        # Return to Creative → SBI Custom
        click_nav(page, "Creative")
        settle(page, 3)
        # If radio flipped, re-open Custom source
        still_custom = page.evaluate(
            """() => {
              const labels = [...document.querySelectorAll('[role="radiogroup"] label')];
              for (const l of labels) {
                if (!/custom progression/i.test(l.innerText || '')) continue;
                const input = l.querySelector('input[type=radio]');
                const role = l.closest('[role=radio]') || l;
                return !!(input && input.checked) || role.getAttribute('aria-checked') === 'true';
              }
              return false;
            }"""
        )
        if not still_custom:
            open_sbi_custom_source(page, notes)
            settle(page, 2)
        side4b, body4b = shot(page, "04b-return-creative-sbi")
        on_creative = has_any(body4b, "Entry & Jam", "Song-Based", "Song source")
        not_top_custom = not (
            has_any(body4b, "Create Your Own Song", "Custom Progression Lab")
            and not has_any(body4b, "Song source", "Entry & Jam")
        )
        mark(
            "4b_return_sbi_custom",
            on_creative and not_top_custom and (still_custom or has_any(body4b, "Trial Song")),
            f"radio_custom={still_custom} creative={on_creative}",
        )

        # 5-6. Custom SBI Backing
        if not still_custom:
            open_sbi_custom_source(page, notes)
            settle(page, 2)
        opened_bk = click_open_backing_studio(page, notes, "sbi-custom") or click_button_has(
            page, r"Open in Backing"
        )
        opened_bk = bool(opened_bk) and wait_for_backing(page, notes, "sbi-custom")
        settle(page, 4)
        side5, body5 = shot(page, "05-custom-sbi-backing")
        specialized = has_any(
            body5, "SBI Custom", "Custom SBI", "Return to Creative · SBI Custom", "CUSTOM PROGRESSION"
        ) and has_any(body5, "Trial Song")
        bad_prog = has_any(body5, "My Progression") or has_any(body5, "N.C.")
        line5 = concert_prog_line(body5)
        concert5 = practice_concert_line(body5)
        prog5 = trial_prog_at_f(line5 or body5)
        pk5 = pk_val(page) or practice_badge(body5)
        concert_ok = "f" in low(concert5) and "minor" not in low(concert5) and "d major" not in low(concert5)
        mark(
            "5_custom_sbi_backing",
            opened_bk
            and specialized
            and prog5
            and concert_ok
            and not bad_prog
            and not card_key_is_original_d(body5)
            and not shape_bleed(side5 + body5),
            f"open={opened_bk} spec={specialized} pk={pk5!r} concert={concert5!r} line={line5!r}",
        )

        set_baseweb_select(page, "Practice / Concert Key", "C major") or set_baseweb_select(
            page, "Practice / Concert Key", "C"
        )
        settle(page, 3)
        side6, body6 = shot(page, "06-backing-pk")
        pk6 = pk_val(page) or practice_badge(body6)
        concert6 = practice_concert_line(body6)
        line6 = concert_prog_line(body6)
        still_spec = has_any(body6, "Trial Song") and has_any(
            body6, "SBI Custom", "Custom SBI", "Return to Creative · SBI Custom"
        )
        pk6_ok = "c" in low(pk6) and "minor" not in low(pk6)
        concert6_ok = "c" in low(concert6) and "minor" not in low(concert6) and "d major" not in low(concert6)
        mark(
            "6_backing_pk",
            still_spec and pk6_ok and concert6_ok and trial_prog_at_c(line6 or body6),
            f"pk={pk6!r} concert={concert6!r} line={line6!r} spec={still_spec}",
        )
        # restore E
        set_baseweb_select(page, "Practice / Concert Key", "E major") or set_baseweb_select(
            page, "Practice / Concert Key", "E"
        )
        settle(page, 2)

        click_nav(page, "Songs")
        settle(page, 3)
        side_s, body_s = shot(page, "06b-songs-after-backing")
        mark(
            "6b_shape_still",
            has_any(side_s + body_s, "Shape of You") and has_any(side_s + body_s, "B minor", "Bm"),
            f"shape={has_any(side_s+body_s,'Shape of You')} bm={has_any(side_s+body_s,'B minor','Bm')}",
        )

        # 7. Return Creative from Custom SBI Backing
        open_sbi_custom_source(page, notes)
        settle(page, 2)
        click_open_backing_studio(page, notes, "sbi-ret") or click_button_has(page, r"Open in Backing")
        wait_for_backing(page, notes, "sbi-ret")
        settle(page, 3)
        click_button_has(page, r"Return to Creative") or click_button_has(
            page, r"Return to Creative · SBI Custom"
        )
        settle(page, 4)
        side7, body7 = shot(page, "07-return-creative")
        ret_ok = (
            has_any(body7, "Trial Song")
            and has_any(body7, "Song source", "Entry & Jam", "Song-Based")
            and not (
                has_any(body7, "Create Your Own Song")
                and not has_any(body7, "Song source")
            )
        )
        mark("7_return_sbi_custom", ret_ok, f"trial={has_any(body7,'Trial Song')}")

        # 8. Refresh on Custom SBI Backing
        open_sbi_custom_source(page, notes)
        settle(page, 2)
        click_open_backing_studio(page, notes, "sbi-rf") or click_button_has(page, r"Open in Backing")
        wait_for_backing(page, notes, "sbi-rf")
        settle(page, 3)
        page.reload(wait_until="domcontentloaded")
        settle(page, 6)
        side8, body8 = shot(page, "08-refresh-backing")
        refresh_ok = (
            has_any(body8, "Trial Song")
            and has_any(body8, "SBI Custom", "Custom SBI", "Return to Creative · SBI Custom")
            and not has_any(body8, "My Progression")
            and not card_key_is_original_d(body8)
        )
        mark(
            "8_refresh_backing",
            refresh_ok,
            f"trial={has_any(body8,'Trial Song')} concert={practice_concert_line(body8)!r} line={concert_prog_line(body8)!r}",
        )

        browser.close()

        # 9. Hard reboot — rebuild backing state then kill/restart
        os.environ["MUSIC_APP_DATA_DIR"] = str(ROOT / "_runtime_custom_basics")
        hard_reboot_streamlit(port)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 8)
        side9, body9 = shot(page, "09-reboot")
        reboot_ok = (
            has_any(body9, "Trial Song")
            and has_any(body9, "SBI Custom", "Custom SBI", "Return to Creative · SBI Custom")
            and not has_any(body9, "My Progression")
            and not card_key_is_original_d(body9)
        )
        mark(
            "9_hard_reboot",
            reboot_ok,
            f"trial={has_any(body9,'Trial Song')} concert={practice_concert_line(body9)!r} line={concert_prog_line(body9)!r} practice_len={has_any(body9,'PRACTICE LENGTH')}",
        )
        browser.close()

    failed = [k for k, v in GATES.items() if not v]
    report = {"gates": GATES, "failed": failed, "notes": NOTES}
    (OUT / f"{PREFIX}report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(GATES, indent=2), flush=True)
    print("FAILED:" if failed else "ALL_PASS", failed or [], flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
