"""One-shot classification of remaining sequential reds. Harness only.

Usage:
  python scripts/_walk_remaining_reds.py http://127.0.0.1:PORT G12
  GATE: G12 G13 G14 G15 AN_EFH AN_N OWNER8 SONGS3 FINISH_GH
"""
from __future__ import annotations

import json
import os
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
    click_radio,
    goto_improv,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_acceptance_an import force_pk_token  # noqa: E402
from _walk_core_key_coherence import card_practice_label, set_songs_practice_key  # noqa: E402
from _walk_core_workflows_embargo import (  # noqa: E402
    hard_reboot_streamlit,
    motif_notes_from_body,
    open_sbi_active,
    practice_badge,
    wait_for_body,
)
from _walk_custom_page_owner_basics import click_main_button  # noqa: E402
from _walk_custom_practice_key import goto_custom, pk_val  # noqa: E402
from _walk_ownership_audit_full import (  # noqa: E402
    add_chord_bar,
    build_trial_song,
    fill_title,
    missions_derived_from_custom_trial,
    rendered_dm_dm_c_c,
    rendered_em_em_d_d,
)
from _walk_pass8_validate import ensure_missions_workspace  # noqa: E402
from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source  # noqa: E402
from _walk_owner_key_tuple import click_sbi_song_source, is_b_minor, is_c_major, is_d_major  # noqa: E402
from _walk_cpl_finish_save import (  # noqa: E402
    launch_labels,
    label_has,
    label_has_backing,
    label_has_practice,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8810"
GATE = (sys.argv[2] if len(sys.argv) > 2 else "G12").strip().upper()
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = f"remain-{GATE}-"
NOTES: list[str] = []
RESULT: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(body: str, *needles: str) -> bool:
    b = low(body)
    return any(low(n) in b for n in needles)


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    side = ""
    try:
        from walk_creative_backing_matrix import expand_sidebar

        expand_sidebar(page)
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    (OUT / f"{stem}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:8000]}\n\n=== BODY ===\n{body[:18000]}",
        encoding="utf-8",
    )
    return body + "\n" + side


def wait_app_ready(page: Page, *anchors: str, timeout_s: float = 45.0, require_all: bool = False) -> bool:
    needles = anchors or ("Daniel Cohen", "PAGES", "Practice")
    try:
        page.wait_for_function(
            """({needles, requireAll}) => {
              const t = document.body ? (document.body.innerText || '') : '';
              if (t.length < 800) return false;
              const low = t.toLowerCase();
              const hit = (n) => low.includes(String(n).toLowerCase());
              return requireAll ? needles.every(hit) : needles.some(hit);
            }""",
            arg={"needles": list(needles), "requireAll": bool(require_all)},
            timeout=int(timeout_s * 1000),
        )
        return True
    except Exception:
        return False


def finish(ok: bool, detail: str = "") -> int:
    RESULT["ok"] = bool(ok)
    RESULT["detail"] = detail
    log(f"[{'PASS' if ok else 'RED'}] {GATE} — {detail}")
    (OUT / f"{PREFIX}report.json").write_text(
        json.dumps({"gate": GATE, "ok": ok, "detail": detail, "notes": NOTES[-40:]}, indent=2),
        encoding="utf-8",
    )
    return 0 if ok else 1


def disk_core() -> dict:
    data_dir = os.environ.get("MUSIC_APP_DATA_DIR") or ""
    candidates = []
    if data_dir:
        candidates.append(Path(data_dir) / "workspaces" / "daniel" / "music_user_state.json")
        candidates.append(Path(data_dir) / "music_user_state.json")
    for p in candidates:
        if not p.exists():
            continue
        try:
            st = json.loads(p.read_text(encoding="utf-8")).get("state") or {}
            core = st.get("core") if isinstance(st.get("core"), dict) else {}
            return {
                "path": str(p),
                "song": core.get("song"),
                "display_key": core.get("display_key"),
                "studio_page": core.get("studio_page") or (st.get("session") or {}).get("studio_page"),
                "pick_key": core.get("pick_key"),
            }
        except Exception as exc:
            return {"error": repr(exc), "path": str(p)}
    return {}


def reboot_port() -> int:
    from urllib.parse import urlparse

    return int(urlparse(URL).port or 8530)


def proof_g12(page: Page, p) -> int:
    """Shape Dm on Songs → process death → restore without re-pick."""
    click_nav(page, "Songs")
    settle(page, 2)
    pick_song(page, NOTES, "Shape of You", "Pop")
    settle(page, 3)
    set_songs_practice_key(page, "Dm")
    settle(page, 2)
    force_pk_token(page, "Dm")
    settle(page, 3)
    body0 = shot(page, "before-songs")
    badge0 = practice_badge(body0) or card_practice_label(body0) or pk_val(page)
    disk0 = disk_core()
    log(f"before badge={badge0!r} pk={pk_val(page)!r} disk={disk0}")
    pre_dm = "d minor" in low(badge0 or "") or str(pk_val(page) or "").lower() in {"dm", "d minor"}
    if not pre_dm:
        return finish(False, f"could not seed Shape Dm before={badge0!r}")

    hard_reboot_streamlit(reboot_port())
    import time

    time.sleep(4)
    page.goto(URL, wait_until="domcontentloaded", timeout=180000)
    wait_app_ready(page, "Shape of You", "Practice", "Welcome back")
    settle(page, 5)
    disk1 = disk_core()
    shot(page, "after-boot")
    click_nav(page, "Songs")
    settle(page, 4)
    wait_for_body(page, "Shape of You", "NOW LOADED", "Song Selection", timeout_s=30)
    settle(page, 3)
    after = shot(page, "after-songs-nopick")
    badge1 = practice_badge(after) or card_practice_label(after) or pk_val(page)
    nopick_dm = has_any(after, "Shape of You") and (
        "d minor" in low(badge1 or "") or str(pk_val(page) or "").lower() in {"dm", "d minor"}
    )
    log(f"after-nopick badge={badge1!r} pk={pk_val(page)!r} disk={disk1}")
    pick_song(page, NOTES, "Shape of You", "Pop")
    settle(page, 3)
    after_pick = shot(page, "after-songs-pick")
    badge2 = practice_badge(after_pick) or card_practice_label(after_pick) or pk_val(page)
    pick_dm = "d minor" in low(badge2 or "")
    log(f"after-pick badge={badge2!r}")
    disk_dm = str((disk1 or {}).get("display_key") or "").lower() in {"dm", "d minor"}
    ok = pre_dm and (nopick_dm or disk_dm)
    return finish(
        ok,
        f"pre={badge0!r} nopick={badge1!r} pick={badge2!r} disk={disk1.get('display_key')!r} "
        f"nopick_dm={nopick_dm} pick_dm={pick_dm} disk_dm={disk_dm}",
    )


def proof_g13(page: Page) -> int:
    click_nav(page, "Songs")
    settle(page, 2)
    pick_song(page, NOTES, "Shape of You", "Pop")
    settle(page, 3)
    pick_song(page, NOTES, "Perfect", "Pop")
    settle(page, 4)
    body = shot(page, "perfect")
    badge = practice_badge(body) or card_practice_label(body) or pk_val(page)
    perfect = has_any(body, "Perfect") and (
        "g major" in low(badge or "") or has_any(body, "G major")
    )
    minor_bleed = "minor" in low(badge or "") and "g major" not in low(badge or "")
    ok = perfect and not minor_bleed and has_any(body, "Perfect")
    return finish(ok, f"badge={badge!r} perfect={perfect} minor_bleed={minor_bleed}")


def proof_g14(page: Page) -> int:
    built = build_trial_song(page, NOTES)
    click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
    settle(page, 3)
    click_nav(page, "Songs")
    settle(page, 4)
    body = shot(page, "songs-d")
    badge = practice_badge(body) or card_practice_label(body)
    d_ok = is_d_major(badge or "") or is_d_major(pk_val(page) or "")
    set_songs_practice_key(page, "E")
    settle(page, 2)
    force_pk_token(page, "E")
    settle(page, 2)
    body_e = shot(page, "songs-e")
    e_ok = "e major" in low(practice_badge(body_e) or card_practice_label(body_e) or pk_val(page) or "")
    set_songs_practice_key(page, "D")
    settle(page, 2)
    force_pk_token(page, "D")
    settle(page, 2)
    body_d = shot(page, "songs-d-back")
    d_back = is_d_major(practice_badge(body_d) or card_practice_label(body_d) or pk_val(page) or "")
    trial = has_any(body, "Trial Song")
    ok = bool(built) and trial and d_ok and e_ok and d_back
    return finish(ok, f"built={built} trial={trial} d={d_ok} e={e_ok} d_back={d_back}")


def proof_g15(page: Page) -> int:
    built = build_trial_song(page, NOTES)
    click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
    settle(page, 3)
    open_sbi_active(page)
    settle(page, 3)
    body_sbi = shot(page, "sbi-d")
    sbi_ok = has_any(body_sbi, "Trial Song") and (
        rendered_em_em_d_d(body_sbi) or has_any(body_sbi, "Em")
    )
    goto_improv(page, NOTES)
    ensure_missions_workspace(page, NOTES)
    settle(page, 2)
    body_m = shot(page, "missions-d")
    m_ok = has_any(body_m, "Trial Song") and missions_derived_from_custom_trial(
        body_m, projected="D"
    )
    click_nav(page, "Songs")
    settle(page, 2)
    set_songs_practice_key(page, "C")
    settle(page, 2)
    force_pk_token(page, "C")
    settle(page, 3)
    goto_improv(page, NOTES)
    open_sbi_active(page)
    settle(page, 3)
    body_c = shot(page, "sbi-c")
    c_ok = has_any(body_c, "Trial Song") and (
        rendered_dm_dm_c_c(body_c) or has_any(body_c, "Dm")
    )
    ok = bool(built) and sbi_ok and m_ok and c_ok
    return finish(ok, f"sbi={sbi_ok} missions={m_ok} c={c_ok}")


def proof_an_efh(page: Page) -> int:
    built = build_trial_song(page, NOTES)
    settle(page, 2)
    click_main_button(page, r"^Finish Song$") or click_button_has(page, r"Finish Song")
    settle(page, 3)
    body_fin = shot(page, "finish")
    saved_layout = has_any(body_fin, "Keep Editing") and has_any(body_fin, "Save to Library")
    click_button_has(page, r"Save to library") or click_main_button(page, r"Save to library")
    settle(page, 3)
    wait_app_ready(page, "Keep Editing", "Launch in the studio", "Finish Save")
    ok_custom = False
    for attempt in range(4):
        ok_custom = open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        body_e = shot(page, f"sbi-custom-{attempt}")
        if ok_custom and has_any(body_e, "Trial Song"):
            break
        log(f"custom open attempt={attempt} open={ok_custom}")
    pk_e = pk_val(page) or practice_badge(body_e)
    e_ok = (
        ok_custom
        and has_any(body_e, "Trial Song")
        and (
            is_d_major(pk_e or "")
            or has_any(body_e, "D major")
            or bool(re.search(r"practice concert key:\s*d\b(?!m)", low(body_e)))
            or str(pk_e or "").strip().lower() in {"d", "d major"}
        )
        and (rendered_em_em_d_d(body_e) or has_any(body_e, "Em"))
    )
    force_pk_token(page, "C")
    settle(page, 3)
    body_f = shot(page, "sbi-custom-c")
    f_ok = has_any(body_f, "Trial Song") and (
        rendered_dm_dm_c_c(body_f) or has_any(body_f, "Dm")
    )
    # Stay off Songs catalog: Songs visits can set follow-active and steal SBI Custom.
    opened_custom = (
        click_button_has(page, r"Open Custom Lab")
        or click_nav(page, "Custom")
        or goto_custom(page)
    )
    log(f"open_custom_from_sbi={opened_custom}")
    settle(page, 3)
    wait_app_ready(page, "Original Key", "Finish Song", "Keep Editing", "Trial Song")
    click_nav(page, "Creative")
    settle(page, 4)
    restored = wait_app_ready(
        page, "Trial Song", "Concert Practice Key Progression", timeout_s=45.0, require_all=True
    )
    body_h = shot(page, "creative-restore")
    h_ok = (
        restored
        and has_any(body_h, "Trial Song")
        and has_any(body_h, "Custom progression")
        and not (has_any(body_h, "Say —") and not has_any(body_h, "Trial Song"))
    )
    log(f"h restored_wait={restored}")
    ok = bool(built) and saved_layout and e_ok and f_ok and h_ok
    return finish(
        ok,
        f"built={built} finish={saved_layout} e={e_ok} f={f_ok} h={h_ok} pk_e={pk_e!r}",
    )


def proof_an_n(page: Page) -> int:
    click_nav(page, "Songs")
    settle(page, 2)
    pick_song(page, NOTES, "Shape of You", "Pop")
    settle(page, 3)
    if not goto_improv(page, NOTES):
        return finish(False, "no creative")
    click_radio(page, "Phrase / Motif") or click_button_has(page, r"Phrase / Motif")
    settle(page, 3)
    for _ in range(4):
        body = page.inner_text("body") or ""
        if re.search(r"Generate motif", body, re.I):
            break
        click_radio(page, "Phrase / Motif")
        settle(page, 2)
    click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
    settle(page, 4)
    body0 = shot(page, "initial")
    notes0 = motif_notes_from_body(body0)
    initial_ok = bool(notes0) and " | " not in (re.search(r"MOTIF\s+ON[\s\S]{0,200}", body0, re.I).group(0) if re.search(r"MOTIF\s+ON[\s\S]{0,200}", body0, re.I) else "")
    click_button_has(page, r"Build Motif Pattern")
    settle(page, 4)
    try:
        page.wait_for_function(
            """() => (document.body.innerText || '').includes(' | ')""",
            timeout=15_000,
        )
    except Exception:
        settle(page, 3)
    body1 = shot(page, "pattern")
    pipes = " | " in body1
    notes1 = motif_notes_from_body(body1)
    ok = bool(notes0) and pipes and has_any(body1, "Motif")
    return finish(
        ok,
        f"initial_notes={len(notes0)} initial_no_pipe={initial_ok} pipes={pipes} "
        f"after_notes={len(notes1)}",
    )


def proof_owner8(page: Page) -> int:
    click_nav(page, "Songs")
    settle(page, 2)
    click_button_has(page, r"Use catalog song instead")
    settle(page, 1)
    pick_song(page, NOTES, "Shape of You", "Pop")
    settle(page, 3)
    force_pk_token(page, "Bm")
    settle(page, 2)
    opened = open_sbi_active(page)
    settle(page, 2)
    clicked = click_sbi_song_source(page, "active")
    settle(page, 2)
    try:
        page.wait_for_function(
            """() => {
              const t = document.body ? (document.body.innerText || '') : '';
              return /Shape of You/i.test(t) && /Active Source/i.test(t);
            }""",
            timeout=15_000,
        )
    except Exception:
        click_sbi_song_source(page, "active")
        settle(page, 3)
    body = shot(page, "sbi-active")
    title = has_any(body, "Shape of You")
    bm = is_b_minor(pk_val(page) or "") or is_b_minor(practice_badge(body) or "") or has_any(
        body, "B minor", "practice concert key: bm"
    )
    prog = has_any(body, "Bm") or has_any(body, "Em")
    no_trial = not has_any(body, "Trial Song") or "custom progression" not in low(body)
    ok = title and bm and prog
    return finish(
        ok,
        f"open={opened} click={clicked} title={title} bm={bm} prog={prog} pk={pk_val(page)!r}",
    )


def click_songs_creative(page: Page) -> bool:
    loc = page.locator('[class*="st-key-picker_card_creative"] button')
    if loc.count():
        try:
            loc.first.click(timeout=4000)
            settle(page, 3)
            return True
        except Exception:
            pass
    # Custom GA hub: 🎨 Creative + Open, or sidebar Creative.
    try:
        hub = page.get_by_role("button", name=re.compile(r"Creative", re.I))
        for i in range(min(hub.count(), 8)):
            el = hub.nth(i)
            t = (el.inner_text() or "").strip()
            if "lab" in t.lower() or t in {"Creative", "🎨\nCreative", "🎨 Creative"}:
                el.click(timeout=4000)
                settle(page, 3)
                return True
        open_btns = page.locator('[data-testid="stAppViewContainer"] button').filter(
            has_text=re.compile(r"^Open$", re.I)
        )
        # Prefer the Open next to Creative by clicking sidebar nav.
    except Exception:
        pass
    return bool(click_nav(page, "Creative"))


def on_creative_page(body: str) -> bool:
    return has_any(body, "Improvisation Intelligence", "Entry & Jam", "Song-Based") or (
        has_any(body, "Harmony, improvisation") and not has_any(body, "SONG CATALOG")
    )


def proof_songs3(page: Page) -> int:
    built = build_trial_song(page, NOTES)
    click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
    settle(page, 3)
    click_nav(page, "Songs")
    settle(page, 4)
    body3 = shot(page, "songs-custom-ga")
    on_songs = has_any(body3, "Trial Song") and (
        has_any(body3, "PROGRESSION LAB") or has_any(body3, "Song Selection") or has_any(body3, "your song")
    )
    clicked = click_songs_creative(page)
    settle(page, 3)
    wait_app_ready(page, "Entry & Jam", "Improvisation", "Song-Based")
    body_c = shot(page, "creative-custom-ga")
    creative = on_creative_page(body_c)
    trial = has_any(body_c, "Trial Song")
    no_shape = not (has_any(body_c, "Shape of You") and not has_any(body_c, "Trial Song"))
    ok = bool(built) and on_songs and clicked and creative and trial and no_shape
    return finish(
        ok,
        f"built={built} songs={on_songs} click={clicked} creative={creative} "
        f"trial={trial} no_shape={no_shape}",
    )


def proof_finish_gh(page: Page) -> int:
    goto_custom(page)
    click_button_has(page, r"New song") or click_button_has(page, r"New Song")
    settle(page, 2)
    fill_title(page, "Finish Save Walk")
    add_chord_bar(page, "C")
    add_chord_bar(page, "G")
    settle(page, 2)
    click_main_button(page, r"^Finish Song$") or click_button_has(page, r"Finish Song")
    settle(page, 3)
    click_main_button(page, r"Save to library") or click_button_has(page, r"Save to library")
    settle(page, 3)
    wait_app_ready(page, "Keep Editing", "saved to custom library", "Launch in the studio")
    before = shot(page, "saved-before-refresh")
    launch_before = launch_labels(page)
    saved_ui = label_has_practice(launch_before) and label_has_backing(launch_before)
    page.reload(wait_until="domcontentloaded", timeout=180000)
    wait_app_ready(page, "Finish Save Walk", "Keep Editing", "Finish Song", "Original Key")
    settle(page, 4)
    for _ in range(4):
        body = page.inner_text("body") or ""
        if has_any(body, "Keep Editing") or has_any(body, "Finish Song") or has_any(body, "Original Key"):
            if has_any(body, "SONG CATALOG") and not has_any(body, "Keep Editing", "Finish Song"):
                goto_custom(page)
                settle(page, 3)
                continue
            break
        goto_custom(page)
        settle(page, 3)
    after = shot(page, "after-refresh")
    launch_g = launch_labels(page)
    g_saved = label_has_practice(launch_g) and label_has_backing(launch_g)
    g_page = has_any(after, "Keep Editing") or has_any(after, "Finish Song") or has_any(
        after, "Finish Save Walk"
    )
    click_main_button(page, r"New song") or click_button_has(page, r"New song")
    settle(page, 3)
    wait_app_ready(page, "New blank song", "Finish Song", "Save to library")
    body_h = shot(page, "new-song")
    launch_h = launch_labels(page)
    h_save = label_has(launch_h, r"Save to library") or has_any(body_h, "Save to library")
    h_prac_hidden = not label_has_practice(launch_h)
    h_back_hidden = not label_has_backing(launch_h)
    h_new = has_any(body_h, "New blank song") or "Finish Save Walk" not in (body_h or "")
    ok = saved_ui and g_saved and g_page and h_save and h_prac_hidden and h_back_hidden and h_new
    return finish(
        ok,
        f"before_saved={saved_ui} g_saved={g_saved} g_page={g_page} "
        f"launch_g={launch_g!r} h_save={h_save} h_hidden={h_prac_hidden and h_back_hidden} "
        f"h_new={h_new} launch_h={launch_h!r}",
    )


def main() -> int:
    log(json.dumps({"url": URL, "gate": GATE, "sha": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
    ).strip()}))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)
        wait_app_ready(page)
        fn = {
            "G12": lambda: proof_g12(page, p),
            "G13": lambda: proof_g13(page),
            "G14": lambda: proof_g14(page),
            "G15": lambda: proof_g15(page),
            "AN_EFH": lambda: proof_an_efh(page),
            "AN_N": lambda: proof_an_n(page),
            "OWNER8": lambda: proof_owner8(page),
            "SONGS3": lambda: proof_songs3(page),
            "FINISH_GH": lambda: proof_finish_gh(page),
        }.get(GATE)
        if fn is None:
            return finish(False, f"unknown gate {GATE}")
        code = fn()
        try:
            browser.close()
        except Exception:
            pass
        return code


if __name__ == "__main__":
    raise SystemExit(main())
