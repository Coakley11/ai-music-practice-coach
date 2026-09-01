"""Focused ownership/key tuple walk — human embargo 12 checks.

Does not replace the larger core-workflow suite. Covers:

1. Trial Global Active C → SBI Custom = Trial C
2. Non-active SBI Custom Trial lifecycle stays D
3. Composition Song Source shows the 🎹 Composition logo
4-8. Style Jam C# does not contaminate explicit Shape (Bm everywhere)
9. Guitar Shape C inherits minor (C minor)
10. Bm → Dm stays minor
11-12. Refresh / Songs↔Creative nav stay coherent

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8542
  python scripts/_walk_owner_key_tuple.py http://127.0.0.1:8542
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

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8542"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "owner-tuple-"
RESULTS: dict[str, str] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, status: str, detail: str = "") -> None:
    RESULTS[gate] = status
    log(f"[{status}] {gate}" + (f" — {detail}" if detail else ""))


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(body: str, *needles: str) -> bool:
    b = low(body)
    return any(n.lower() in b for n in needles)


def settle(page: Page, sec: float = 2.0) -> None:
    from walk_creative_backing_matrix import wait_idle

    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> tuple[str, str]:
    from walk_creative_backing_matrix import expand_sidebar

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


def pk_label(text: str) -> str:
    from _walk_core_workflows_embargo import practice_badge
    from _walk_core_key_coherence import card_practice_label

    return practice_badge(text) or card_practice_label(text) or ""


def is_c_major(label: str) -> bool:
    t = low(label)
    return "c major" in t or (t.startswith("c") and "minor" not in t and "c#" not in t)


def is_d_major(label: str) -> bool:
    t = low(label)
    return "d major" in t or (re.search(r"\bd\s+major\b", t) is not None)


def is_b_minor(label: str) -> bool:
    t = low(label)
    return "b minor" in t or bool(re.search(r"\bbm\b", t))


def is_d_minor(label: str) -> bool:
    t = low(label)
    return "d minor" in t or bool(re.search(r"\bdm\b", t))


def click_sbi_song_source(page: Page, which: str) -> bool:
    """Click SBI Song Source Active vs Custom via native radio input."""
    needle = "custom" if which == "custom" else "active"
    try:
        via = page.evaluate(
            """(which) => {
              const groups = [...document.querySelectorAll('[role="radiogroup"]')];
              for (const g of groups) {
                const gtxt = (g.innerText || '').toLowerCase();
                if (!gtxt.includes('custom progression')) continue;
                if (!gtxt.includes('active source') && !gtxt.includes('active song')) continue;
                const labels = [...g.querySelectorAll('label')];
                const target = labels.find((l) => {
                  const t = (l.innerText || '').toLowerCase();
                  if (which === 'custom') return t.includes('custom progression');
                  return t.includes('active source') || t.includes('active song');
                });
                if (!target) continue;
                target.scrollIntoView({block:'center'});
                const input = target.querySelector('input[type=radio]');
                if (input) {
                  input.click();
                  input.dispatchEvent(new Event('input', {bubbles: true}));
                  input.dispatchEvent(new Event('change', {bubbles: true}));
                  return 'input';
                }
                target.click();
                return 'label';
              }
              return '';
            }""",
            needle,
        )
        return bool(via)
    except Exception:
        return False


def has_c_sharp_major(text: str) -> bool:
    t = low(text)
    return "c# major" in t or "c sharp major" in t or bool(re.search(r"c#\s+major", t))


def main() -> int:
    from walk_creative_backing_matrix import (
        click_button_has,
        click_nav,
        click_open_backing_studio,
        click_radio,
        expand_sidebar,
        goto_improv,
        set_instrument,
        wait_idle,
    )
    from walk_guitar_shape_key import enable_guitar_capo, pick_song
    from _walk_acceptance_an import force_pk_token, set_style_jam_concert_key
    from _walk_core_key_coherence import set_songs_practice_key
    from _walk_core_workflows_embargo import open_sbi_active
    from _walk_custom_practice_key import pk_val
    from _walk_ownership_audit_full import build_trial_song, rendered_dm_dm_c_c, rendered_em_em_d_d
    from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source

    meta = git_meta()
    log(json.dumps(meta))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        # ---- Seed Trial as Global Active at C ----
        trial_ok = build_trial_song(page, NOTES)
        mark("seed_trial", "PASS" if trial_ok else "RED", "Trial Song D / Em Em D D")
        click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
        settle(page, 3)
        click_nav(page, "Songs")
        settle(page, 3)
        set_songs_practice_key(page, "C")
        settle(page, 3)
        force_pk_token(page, "C")
        settle(page, 2)
        side, body = shot(page, "01-trial-ga-c")
        songs_c = is_c_major(pk_label(body + side)) or is_c_major(pk_val(page) or "")
        mark("1_songs_trial_c", "PASS" if songs_c else "RED", pk_label(body + side) or pk_val(page))

        # 1. SBI Custom CASE A = Trial C
        ok_custom = open_sbi_custom_source(page, NOTES)
        if not ok_custom:
            try:
                page.get_by_role("radio", name=re.compile(r"Active Source", re.I)).last.focus()
                page.keyboard.press("ArrowRight")
                settle(page, 3)
                ok_custom = True
            except Exception:
                pass
        settle(page, 3)
        side, body = shot(page, "02-sbi-custom-case-a")
        pk = pk_label(body + side) or pk_val(page) or ""
        case_a = (
            has_any(body, "Trial Song")
            and (is_c_major(pk) or bool(re.search(r"practice concert key:\s*c\b(?!#)", low(body))))
            and not is_d_major(pk)
            and (rendered_dm_dm_c_c(body) or has_any(body, "Dm"))
        )
        mark(
            "1_sbi_custom_case_a_c",
            "PASS" if case_a else "RED",
            f"open={ok_custom} pk={pk!r} dm={rendered_dm_dm_c_c(body)}",
        )

        # SBI Active while Trial is GA may also be Trial/C
        ok_active = open_sbi_active(page)
        settle(page, 3)
        side, body = shot(page, "03-sbi-active-trial")
        active_trial = ok_active and has_any(body, "Trial Song") and (
            is_c_major(pk_label(body + side) or pk_val(page) or "")
            or bool(re.search(r"practice concert key:\s*c\b", low(body)))
        )
        mark("1b_sbi_active_trial_c", "PASS" if active_trial else "PARTIAL", pk_label(body + side))

        # 3. Composition feather/piano logo
        try:
            labels = page.evaluate(
                """() => [...document.querySelectorAll('label, p, span')]
                  .map(el => (el.innerText || '').trim())
                  .filter(t => /composition/i.test(t))
                  .slice(0, 12)"""
            )
        except Exception:
            labels = []
        logo_ok = any("🎹" in str(t) and "composition" in low(str(t)) for t in (labels or []))
        if not logo_ok:
            logo_ok = "🎹 composition" in low(body) or "🎹 composition" in (page.inner_text("body") or "").lower()
        # Streamlit may keep the emoji in the radio option even if innerText dumps poorly.
        if not logo_ok:
            try:
                logo_ok = bool(
                    page.evaluate(
                        """() => /🎹\\s*Composition/u.test(document.body.innerText || '')"""
                    )
                )
            except Exception:
                pass
        mark("3_composition_logo", "PASS" if logo_ok else "RED", "piano-emoji Composition" if logo_ok else "missing")

        # 2. Explicit Shape → non-active SBI Custom = Trial D
        click_nav(page, "Songs")
        settle(page, 3)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 4)
        side, body = shot(page, "04-explicit-shape")
        shape_bm = has_any(body, "Shape of You") and is_b_minor(pk_label(body + side) or pk_val(page) or "")
        no_c_sharp = not has_c_sharp_major(body + side)
        mark(
            "2_explicit_shape_bm",
            "PASS" if shape_bm and no_c_sharp else "RED",
            f"pk={pk_label(body + side)!r} c#={not no_c_sharp}",
        )

        ok_custom_b = open_sbi_custom_source(page, NOTES)
        if not ok_custom_b:
            try:
                page.get_by_role("radio", name=re.compile(r"Active Source", re.I)).last.focus()
                page.keyboard.press("ArrowRight")
                settle(page, 3)
            except Exception:
                pass
        settle(page, 3)
        side, body = shot(page, "05-sbi-custom-case-b")
        pk = pk_label(body + side) or pk_val(page) or ""
        case_b = (
            has_any(body, "Trial Song")
            and (is_d_major(pk) or bool(re.search(r"practice concert key:\s*d\b(?!m)", low(body))))
            and not is_b_minor(pk)
            and not has_c_sharp_major(body + side)
            and (rendered_em_em_d_d(body) or has_any(body, "Em"))
        )
        mark(
            "2_sbi_custom_case_b_d",
            "PASS" if case_b else "RED",
            f"open={ok_custom_b} pk={pk!r} em={rendered_em_em_d_d(body)}",
        )

        # 4-7. Style Jam C# → Open Backing → Songs explicit Shape = Bm
        click_nav(page, "Creative")
        settle(page, 3)
        if goto_improv(page, NOTES):
            click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
            settle(page, 2)
            click_radio(page, "Style Jam") or click_button_has(page, r"Style Jam Mode")
            settle(page, 2)
            set_style_jam_concert_key(page, "C#") or set_style_jam_concert_key(page, "C# major")
            settle(page, 2)
            concert_ok = False
            for _ in range(4):
                set_style_jam_concert_key(page, "C#") or set_style_jam_concert_key(page, "C# major")
                settle(page, 2)
                jam_pre = page.inner_text("body") or ""
                if has_c_sharp_major(jam_pre) or "c#" in low(jam_pre):
                    concert_ok = True
                    break
            click_button_has(page, r"Generate progression")
            try:
                page.wait_for_function(
                    """() => {
                      const t = document.body ? (document.body.innerText || '') : '';
                      return /Generated\\b/i.test(t)
                        && /Open in Backing Studio/i.test(t)
                        && (/C#\\s*major/i.test(t) || /C sharp major/i.test(t));
                    }""",
                    timeout=20_000,
                )
            except Exception:
                click_button_has(page, r"Generate progression")
                settle(page, 5)
            opened_jam = click_button_has(page, r"Open in Backing Studio") or click_open_backing_studio(
                page, NOTES, "jam-c#"
            )
            settle(page, 4)
            side, body = shot(page, "06-style-jam-backing")
            jam_c = has_c_sharp_major(body + side) or "c#" in low(pk_val(page) or "") or "c#" in low(body)
            mark("4_style_jam_c_sharp", "PASS" if jam_c else "RED", f"backing={opened_jam} set={concert_ok} pk={pk_val(page)}")

        click_nav(page, "Songs")
        settle(page, 3)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 4)
        side, body = shot(page, "07-songs-shape-after-jam")
        combined = body + side
        no_leak = not has_c_sharp_major(combined)
        sidebar_bm = is_b_minor(pk_val(page) or "") or is_b_minor(pk_label(side) or "")
        shape_fresh = has_any(side, "Shape of You") and sidebar_bm
        mark(
            "4_shape_bm_after_jam",
            "PASS" if shape_fresh and no_leak else "RED",
            f"pk={pk_label(side)!r} sidebar={pk_val(page)!r} c#={not no_leak}",
        )

        # 8. SBI Active coherent tuple — Active Source after explicit Shape.
        ok_sbi = open_sbi_active(page)
        click_sbi_song_source(page, "active")
        settle(page, 2)
        try:
            page.wait_for_function(
                """() => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  return /Shape of You/i.test(t)
                    && (/B minor/i.test(t) || /practice concert key:\\s*bm/i.test(t));
                }""",
                timeout=20_000,
            )
        except Exception:
            click_sbi_song_source(page, "active")
            settle(page, 3)
        side, body = shot(page, "08-sbi-active-shape")
        combined = body + side
        card_shape = has_any(body, "Shape of You") and (
            "active song · song selection" in low(body)
            or "practice concert key: bm" in low(body)
            or is_b_minor(pk_val(page) or "")
            or is_b_minor(pk_label(combined) or "")
        )
        custom_card = "custom progression\n\ntrial song" in low(body) or (
            "trial song" in low(body) and "practice concert key: d" in low(body)
        )
        sbi_bm = is_b_minor(pk_label(combined) or pk_val(page) or "") or is_b_minor(
            pk_val(page) or ""
        )
        sbi_prog = has_any(body, "Bm") or has_any(body, "Em")
        no_g_major_split = "g major" not in low(combined) or is_b_minor(pk_val(page) or "")
        no_gm_shape = "practice concert key: g" not in low(body)
        sbi_ok = (
            card_shape
            and not custom_card
            and sbi_bm
            and sbi_prog
            and no_g_major_split
            and no_leak
            and no_gm_shape
        )
        mark(
            "8_sbi_active_tuple",
            "PASS" if sbi_ok else "RED",
            f"card_shape={card_shape} custom_card={custom_card} bm={sbi_bm} "
            f"open={ok_sbi} pk={pk_label(combined)!r} card={pk_val(page)!r}",
        )

        click_nav(page, "Songs")
        settle(page, 2)
        set_instrument(page, "Guitar")
        settle(page, 2)
        try:
            enable_guitar_capo(page, NOTES, "C")
        except Exception as exc:
            log(f"enable_guitar_capo failed: {exc}")
        settle(page, 3)
        side, body = shot(page, "08b-songs-guitar-c")
        combined = body + side
        c_minor_ctx = (
            has_any(combined, "Charts in C minor")
            or has_any(combined, "C minor")
        )
        still_bm = is_b_minor(pk_val(page) or "") or is_b_minor(pk_label(combined) or "")
        mark(
            "10_guitar_shape_c_minor",
            "PASS" if c_minor_ctx and still_bm else "PARTIAL",
            f"c_minor={c_minor_ctx} bm={still_bm} charts_b={'charts in b minor' in low(combined)}",
        )

        # 11. Bm → Dm on Songs, then confirm it persists
        click_nav(page, "Songs")
        settle(page, 3)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 1)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        expand_sidebar(page)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        force_pk_token(page, "Dm")
        settle(page, 3)
        side, body = shot(page, "09-sbi-shape-dm")
        combined = body + side
        dm_ok = is_d_minor(pk_label(combined) or pk_val(page) or "") and has_any(
            combined, "Shape of You"
        )
        no_jam = not has_c_sharp_major(combined)
        mark(
            "11_bm_to_dm",
            "PASS" if dm_ok and no_jam else "RED",
            f"pk={pk_label(combined)!r}",
        )

        click_nav(page, "Songs")
        settle(page, 3)
        side, body = shot(page, "10-songs-shape-dm")
        persist_dm = is_d_minor(pk_label(body + side) or pk_val(page) or "")
        mark("11b_songs_shape_dm", "PASS" if persist_dm else "RED", pk_label(body + side))

        # Reset to Bm for refresh check
        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 1)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        force_pk_token(page, "Bm")
        settle(page, 3)
        ok_sbi = open_sbi_active(page)
        click_sbi_song_source(page, "active")
        settle(page, 3)
        page.reload(wait_until="domcontentloaded", timeout=120000)
        settle(page, 8)
        from _walk_core_workflows_embargo import wait_for_body

        wait_for_body(page, "Shape of You", "Practice concert key", timeout_s=45.0)
        side, body = shot(page, "11-refresh-sbi-active")
        refresh_ok = has_any(body + side, "Shape of You") and is_b_minor(
            pk_label(body + side) or pk_val(page) or ""
        )
        mark("13_refresh_sbi_active", "PASS" if refresh_ok else "RED", pk_label(body + side))

        click_nav(page, "Songs")
        settle(page, 2)
        click_nav(page, "Creative")
        settle(page, 2)
        open_sbi_active(page)
        settle(page, 3)
        side, body = shot(page, "12-nav-sbi-active")
        nav_ok = has_any(body + side, "Shape of You") and not has_c_sharp_major(body + side)
        mark("13_nav_sbi_active", "PASS" if nav_ok else "RED", pk_label(body + side))

        browser.close()

    reds = [k for k, v in RESULTS.items() if v == "RED"]
    partials = [k for k, v in RESULTS.items() if v == "PARTIAL"]
    passes = [k for k, v in RESULTS.items() if v == "PASS"]
    overall = "PASS" if not reds and not partials else ("PARTIAL" if not reds else "RED")
    summary = {
        "meta": meta,
        "overall": overall,
        "results": RESULTS,
        "pass": passes,
        "partial": partials,
        "red": reds,
        "notes": NOTES[-80:],
    }
    (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / f"{PREFIX}summary.txt").write_text(
        "\n".join(
            [
                f"OVERALL={overall}",
                f"PASS={len(passes)} PARTIAL={len(partials)} RED={len(reds)}",
                json.dumps(RESULTS, indent=2),
                "",
                *NOTES[-60:],
            ]
        ),
        encoding="utf-8",
    )
    log(f"OVERALL={overall} PASS={len(passes)} PARTIAL={len(partials)} RED={len(reds)}")
    return 0 if overall != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
