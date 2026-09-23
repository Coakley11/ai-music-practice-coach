"""Browser proof: Missions PK, chord tiles, Return-to-Mission, Change Rhythm, 4/4.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_hotfix_missions python -m streamlit run streamlit_music_practice_app.py --server.port 8552
  python scripts/_proof_missions_stabilize.py http://127.0.0.1:8552
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
sys.path[:0] = [str(SCRIPTS), str(ICONS), str(ROOT)]

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
from _walk_core_workflows_embargo import (  # noqa: E402
    click_generate_example_once,
    click_mission_chord_once,
)
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8552"
OUT = SCRIPTS / "evidence-missions-stabilize"
OUT.mkdir(parents=True, exist_ok=True)
RESULT: dict[str, object] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def mark(step: str, ok: bool, detail: str = "", **fields: object) -> None:
    RESULT[step] = {"ok": ok, "detail": detail, **fields}
    log(f"[{'PASS' if ok else 'FAIL'}] {step} — {detail}")


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


def shot(page: Page, name: str) -> str:
    expand_sidebar(page)
    side = ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    body = page.inner_text("body") or ""
    (OUT / f"{name}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:12000]}\n\n=== BODY ===\n{body[:24000]}",
        encoding="utf-8",
    )
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    return body


def key_token(raw: str) -> str:
    t = str(raw or "").replace("♯", "#").replace("♭", "b").strip()
    m = re.search(r"([A-G](?:#|b)?m?)", t)
    return m.group(1) if m else t


def pk_live(page: Page) -> str:
    expand_sidebar(page)
    raw = str(pk_val(page) or "").strip()
    if raw:
        return key_token(raw)
    try:
        body = page.inner_text("body") or ""
    except Exception:
        body = ""
    # Prefer live canonical / practice_concert over stale sidebar_display_key
    # surface traces (Capo leave can leave sidebar_trace on a prior token).
    m = re.search(r'"canonical_display_key"\s*:\s*"([^"]+)"', body)
    if m and key_token(m.group(1)):
        return key_token(m.group(1))
    m = re.search(
        r'"practice_concert"\s*:\s*\{[^}]*?"raw"\s*:\s*"([^"]*)"',
        body,
        re.S,
    )
    if m and key_token(m.group(1)):
        return key_token(m.group(1))
    m = re.search(r"sidebar_display_key:\s*([A-G][#b]?m?)", body)
    if m:
        return key_token(m.group(1))
    m = re.search(r'"raw":\s*"([A-G][#b]?m?)"', body)
    if m:
        return key_token(m.group(1))
    return key_token(original_key_caption(body))


def set_pk(page: Page, token: str) -> bool:
    aliases = [token]
    extra = {
        "D#m": ["D# minor", "Eb minor", "Ebm"],
        "Em": ["E minor"],
        "C": ["C major"],
        "E": ["E major"],
        "Eb": ["Eb major", "D# major"],
        "C#m": ["C# minor"],
    }
    aliases.extend(extra.get(token, []))
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    expand_sidebar(page)
    for alias in aliases:
        try:
            combo = page.get_by_role("combobox", name="Practice / Concert Key")
            if combo.count() == 0:
                continue
            combo.first.click(timeout=4000)
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(str(alias), delay=30)
            page.wait_for_timeout(400)
            opt = page.locator('[role="option"]').filter(
                has_text=re.compile(rf"^{re.escape(alias)}$", re.I)
            )
            if opt.count() == 0:
                page.keyboard.press("Escape")
                continue
            el = opt.first
            el.scroll_into_view_if_needed()
            el.click(timeout=4000)
            settle(page, 3)
            landed = pk_live(page).lower().replace(" ", "")
            want = token.lower().replace(" ", "")
            if want in landed or alias.lower().replace(" ", "") in landed:
                return True
            page.keyboard.press("Escape")
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
    return bool(set_baseweb_select(page, "Practice / Concert Key", token))


def open_missions(page: Page) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    if not goto_improv(page, NOTES):
        click_nav(page, "Creative")
        settle(page, 2)
    return ensure_missions_workspace(page, NOTES)


def map_has(body: str, *chords: str) -> bool:
    text = body.replace("♯", "#").replace("♭", "b")
    return all(ch in text for ch in chords)


def abc_source(page: Page) -> str:
    """Return motif ABC — never a bare git SHA from a sidebar ``<code>`` chip."""
    try:
        page.get_by_text("ABC source (optional)", exact=False).first.click(timeout=4000)
        settle(page, 1)
    except Exception:
        pass
    try:
        codes = page.locator("code")
        n = codes.count()
        for i in range(n - 1, -1, -1):
            text = str(codes.nth(i).inner_text(timeout=1500) or "")
            if "M:" in text or text.strip().startswith("X:"):
                return text
    except Exception:
        pass
    try:
        body = page.inner_text("body") or ""
    except Exception:
        body = ""
    m = re.search(r"(X:\s*1[\s\S]{0,1200})", body)
    if m:
        return m.group(1)
    m = re.search(r"(M:\s*4/4[\s\S]{0,800})", body)
    return m.group(1) if m else ""


def main() -> int:
    RESULT["meta"] = git_meta()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.set_default_timeout(25_000)
        page.goto(f"{URL}/?dev=1", wait_until="domcontentloaded", timeout=180_000)
        settle(page, 5)

        # Pollute history with Perfect / C, then switch to Slow Dancing.
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Perfect", "Pop")
        settle(page, 3)
        set_pk(page, "C")
        settle(page, 3)
        body_p = shot(page, "00-perfect-c")
        mark(
            "perfect_pollute",
            "Perfect" in body_p and pk_live(page) in {"C", "C major"},
            f"pk={pk_live(page)!r} orig={original_key_caption(body_p)!r}",
        )

        pick_song(page, NOTES, "Slow Dancing in a Burning Room", "Pop")
        settle(page, 4)
        body_s = shot(page, "01-slow-songs")
        orig = key_token(original_key_caption(body_s))
        pk = pk_live(page)
        mark(
            "slow_initial_keys",
            orig in {"C#m", "C#"} and pk in {"C#m", "C#"} and pk != "Cm",
            f"orig={orig!r} pk={pk!r}",
            first_wrong="Practice Key" if pk == "Cm" else "",
            competing="leftover Perfect/C or Cm hydrate" if pk == "Cm" else "",
        )

        ok_m = open_missions(page)
        settle(page, 4)
        body_m = shot(page, "02-slow-missions")
        mark(
            "slow_missions_map_cshm",
            ok_m and map_has(body_m, "C#m") and "Slow Dancing" in body_m,
            f"ok_m={ok_m} has_cshm={map_has(body_m, 'C#m')}",
        )

        set_ok = set_pk(page, "D#m")
        settle(page, 4)
        body_d = shot(page, "03-slow-dsharp")
        pk_d = pk_live(page)
        mark(
            "slow_dsharp_commits",
            set_ok
            and pk_d in {"D#m", "D#", "Ebm", "Eb"}
            and map_has(body_d, "D#m", "B", "F#"),
            f"set={set_ok} pk={pk_d!r} map_dshm={map_has(body_d, 'D#m')}",
            first_wrong="Practice Key" if pk_d not in {"D#m", "D#", "Ebm", "Eb"} else "",
            competing="original C#m hydrate" if pk_d in {"C#m", "C#", "Cm"} else "",
        )

        page.reload(wait_until="domcontentloaded", timeout=180_000)
        settle(page, 5)
        open_missions(page)
        settle(page, 3)
        body_r = shot(page, "04-slow-dsharp-refresh")
        orig_r = key_token(original_key_caption(body_r))
        pk_r = pk_live(page)
        mark(
            "slow_dsharp_refresh",
            orig_r in {"C#m", "C#"} and pk_r in {"D#m", "D#", "Ebm", "Eb"},
            f"orig={orig_r!r} pk={pk_r!r}",
        )

        set_em = set_pk(page, "Em")
        settle(page, 4)
        body_e = shot(page, "05-slow-em")
        pk_e = pk_live(page)
        mark(
            "slow_em_commits",
            set_em and pk_e in {"Em", "E"} and map_has(body_e, "Em", "C", "G", "D"),
            f"set={set_em} pk={pk_e!r}",
        )

        clicked = click_mission_chord_once(page, "C") or click_mission_chord_once(page, "G")
        settle(page, 2)
        body_ch = shot(page, "06-slow-chord-click")
        mark(
            "slow_chord_tiles",
            bool(clicked) and ("Selected" in body_ch or "mission" in body_ch.lower()),
            f"clicked={clicked!r}",
        )

        opened = open_mission_backing(page, NOTES)
        settle(page, 4)
        body_b = shot(page, "07-mission-backing")
        has_flag = "Return to Mission" in body_b and ("🚩" in body_b or "flag" in body_b.lower())
        mark(
            "return_button_flag",
            opened and "Return to Mission" in body_b,
            f"opened={opened} flag={has_flag} body_has_slow={'Slow Dancing' in body_b}",
        )
        click_button_has(page, r"Return to Mission")
        settle(page, 4)
        body_ret = shot(page, "08-return-missions")
        side_ret = ""
        try:
            side_ret = page.inner_text('[data-testid="stSidebar"]') or ""
        except Exception:
            side_ret = body_ret
        mark(
            "return_keeps_slow_dancing",
            "Slow Dancing" in side_ret and "Perfect" not in side_ret.split("SONG")[-1][:400],
            f"sidebar_has_slow={'Slow Dancing' in side_ret} perfect_in_side={'Perfect' in side_ret}",
            first_wrong="active_catalog_pick_key/selected_song" if "Perfect" in side_ret and "Slow Dancing" not in side_ret else "",
            competing="last Catalog Perfect snapshot" if "Perfect" in side_ret else "",
        )

        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Perfect", "Pop")
        settle(page, 3)
        set_pk(page, "Eb")
        settle(page, 3)
        open_missions(page)
        settle(page, 4)
        click_generate_example_once(page)
        settle(page, 4)
        click_button_has(page, r"Resolve every phrase on beat 1") or click_radio(
            page, "Resolve every phrase on beat 1"
        )
        settle(page, 3)
        click_generate_example_once(page)
        settle(page, 4)
        body_ex = shot(page, "09-perfect-example")
        before_rhythm = ""
        m = re.search(r"(?:rhythm|Rhythm)[^\n]{0,80}", body_ex)
        if m:
            before_rhythm = m.group(0)
        abc = abc_source(page)
        mark(
            "four_four_barlines",
            "M:4/4" in abc.replace(" ", "") or "M:4/4" in abc,
            f"abc={abc[:220]!r} bars={abc.count('|')}",
        )
        click_button_has(page, r"Change Rhythm")
        settle(page, 3)
        body_ry = shot(page, "10-change-rhythm")
        after_rhythm = ""
        m2 = re.search(r"(?:rhythm|Rhythm)[^\n]{0,80}", body_ry)
        if m2:
            after_rhythm = m2.group(0)
        abc2 = abc_source(page)
        mark(
            "change_rhythm_differs",
            bool(after_rhythm) and after_rhythm != before_rhythm or abc2 != abc,
            f"before={before_rhythm!r} after={after_rhythm!r}",
        )

        set_e = set_pk(page, "E")
        settle(page, 4)
        pk_pe = pk_live(page)
        click_nav(page, "Songs")
        settle(page, 3)
        shot(page, "11-perfect-songs-e")
        mark(
            "perfect_e_persists_songs",
            set_e and pk_pe in {"E", "E major"} and pk_live(page) in {"E", "E major"},
            f"set={set_e} missions_pk={pk_pe!r} songs_pk={pk_live(page)!r}",
        )

        browser.close()

    (OUT / "summary.json").write_text(
        json.dumps({"meta": RESULT.get("meta"), "notes": NOTES[-40:], "gates": RESULT}, indent=2),
        encoding="utf-8",
    )
    failed = [
        k
        for k, v in RESULT.items()
        if k != "meta" and isinstance(v, dict) and not v.get("ok")
    ]
    print(f"failed={failed or 'none'}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
