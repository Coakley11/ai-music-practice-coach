"""Creative Backing Stabilization — broader live-draft rendered sweep (A–I).

Exercises SBI, Missions, Motif, Style Jam, key layers, instruments, and
refresh/reboot. Clicks real Streamlit widgets and asserts visible text.

Usage:
  MUSIC_APP_DATA_DIR=/tmp/cbs-live-<sha> streamlit run streamlit_music_practice_app.py --server.port 8543
  python3 scripts/_walk_cbs_live_draft.py http://127.0.0.1:8543
"""
from __future__ import annotations

import json
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

from cbs_rendered_contracts import mixed_state_failures  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8543"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "cbs-live-"
RESULTS: dict[str, str] = {}
NOTES: list[str] = []
CRITICAL = {
    "A_sbi_active_pk",
    "A_sbi_active_restore",
    "B_custom_sbi_trial",
    "B_custom_lab_creative",
    "C_mission_interval",
    "D_mission_backing_return",
    "E_motif_pipes",
    "F_jam_ga_restore",
    "G_key_layers_minor",
    "G_key_layers_major",
    "H_instrument_pk",
    "I_hard_reboot",
}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


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
    blob = low(body)
    return any(n.lower() in blob for n in needles if n)


def key_hits(text: str, *tokens: str) -> bool:
    """Normalized key-label match. Never treat a lone letter such as E as a hit."""
    blob = f" {low(text)} "
    aliases = {
        "fm": ("f minor", "fm"),
        "f minor": ("f minor", "fm"),
        "dm": ("d minor", "dm"),
        "d minor": ("d minor", "dm"),
        "bm": ("b minor", "bm"),
        "b minor": ("b minor", "bm"),
        "eb": ("eb", "e-flat", "e flat", "eb major", "d#", "d# major"),
        "d#": ("eb", "e-flat", "e flat", "eb major", "d#", "d# major"),
        "a major": ("a major",),
        "c#m": ("c# minor", "c#m", "db minor", "dbm"),
        "dbm": ("c# minor", "c#m", "db minor", "dbm"),
    }
    for tok in tokens:
        t = low(tok).strip()
        if not t or t in {"e", "a", "d", "c", "b", "f", "g"}:
            continue
        for lab in aliases.get(t, (t,)):
            if f" {lab} " in blob or f" {lab}\n" in blob or f"\n{lab} " in blob:
                return True
            if re.search(rf"(?<![a-z#]){re.escape(lab)}(?![a-z])", blob):
                return True
    return False


def settle(page: Page, sec: float = 2.0) -> None:
    from walk_creative_backing_matrix import wait_idle

    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:24000], encoding="utf-8")
    return body


def sidebar_text(page: Page) -> str:
    try:
        from walk_creative_backing_matrix import expand_sidebar

        expand_sidebar(page)
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def main_text(page: Page) -> str:
    for sel in ('[data-testid="stMain"]', '[data-testid="stAppViewContainer"]'):
        try:
            loc = page.locator(sel)
            if loc.count():
                return loc.first.inner_text() or ""
        except Exception:
            continue
    return page.inner_text("body") or ""


def fail_mixed(page: Page, surface: str) -> list[str]:
    errs = mixed_state_failures(
        body=page.inner_text("body") or "",
        main=main_text(page),
        sidebar=sidebar_text(page),
        surface=surface,
    )
    if errs:
        log(f"MIXED {surface}: {errs}")
    return errs


def selectbox_value(page: Page, label: str) -> str:
    return (
        page.evaluate(
            """(label) => {
              const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
              for (const box of boxes) {
                const t = (box.innerText || '');
                if (!new RegExp(label, 'i').test(t)) continue;
                const inp = box.querySelector('input');
                if (inp && inp.value) return String(inp.value).trim();
                const first = (t.split('\\n').map(s => s.trim()).filter(Boolean)[1] || '');
                return first;
              }
              return '';
            }""",
            label,
        )
        or ""
    )


def written_val(page: Page) -> str:
    return selectbox_value(page, "Written Key") or selectbox_value(page, "Written")


def shape_val(page: Page) -> str:
    return selectbox_value(page, "Shape Key") or selectbox_value(page, "Guitar Shape")


def enable_written_charts(page: Page) -> bool:
    from walk_creative_backing_matrix import click_button_has, click_radio

    try:
        page.get_by_text(re.compile(r"Written Charts|Show chart in instrument", re.I)).first.click(
            timeout=3000
        )
        settle(page, 2)
        return True
    except Exception:
        ok = click_radio(page, "Written Charts on") or click_button_has(page, r"Written Charts")
        settle(page, 2)
        return bool(ok)


def port_from_url(url: str) -> int:
    m = re.search(r":(\d+)", url or "")
    return int(m.group(1)) if m else 8543


def hard_reboot(port: int) -> None:
    from _walk_core_workflows_embargo import hard_reboot_streamlit

    hard_reboot_streamlit(port)


def wait_up(page: Page, url: str) -> None:
    for _ in range(40):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            settle(page, 3)
            if page.inner_text("body"):
                return
        except Exception:
            time.sleep(2)


def owner_split(body: str) -> bool:
    """Trial title with Shape chords on the same card — not sidebar GA + Custom SBI."""
    blob = low(body)
    if "trial song" in blob and "184 chords" in blob:
        return True
    if "trial song" in blob and "active song · song selection" in blob:
        return True
    if "trial song" in blob and "shape of you" in blob:
        if "b minor" in blob and "d major" in blob and "em · em · d · d" not in blob and "em em d d" not in blob:
            if "4 chords" not in blob:
                return True
    return False


def main() -> int:
    from walk_creative_backing_matrix import (
        click_button_has,
        click_nav,
        click_open_backing_studio,
        click_radio,
        goto_improv,
        set_baseweb_select,
        set_instrument,
        wait_for_backing,
    )
    from walk_guitar_shape_key import pick_song, set_shape_tonic
    from _walk_ownership_audit_full import build_trial_song, rendered_em_em_d_d
    from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source
    from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing
    from _walk_core_key_coherence import set_songs_practice_key, card_practice_label
    from _walk_custom_practice_key import goto_custom, pk_val
    from _walk_core_workflows_embargo import (
        click_available_mission_chord,
        click_generate_example,
        motif_notes_from_body,
        open_sbi_active,
        practice_badge,
        sidebar_pk_input,
        wait_for_body,
        leave_mission_backing,
    )
    from _walk_core_workflows_embargo import absurd_octave_jumps

    meta = git_meta()
    log(json.dumps(meta))
    port = port_from_url(URL)
    NOTES[:] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)
        wait_for_body(page, "Songs", "Practice", timeout_s=40)

        # Seed Catalog Shape + Trial
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        shot(page, "00-shape-bm")
        build_trial_song(page, NOTES)
        settle(page, 2)

        # ---------- A. SBI Active Source ----------
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        set_songs_practice_key(page, "Fm")
        settle(page, 2)
        body_pk = shot(page, "A-shape-fm")
        pk_fm = pk_val(page) or sidebar_pk_input(page) or practice_badge(body_pk)
        card_fm = card_practice_label(body_pk)
        pk_once = has_any(pk_fm + " " + card_fm + " " + body_pk, "F minor", "Fm")
        mark("A_sbi_active_pk", "PASS" if pk_once else "RED", f"pk={pk_fm!r} card={card_fm!r}")

        set_instrument(page, "Guitar") or True
        settle(page, 1)
        enable_written_charts(page)
        set_shape_tonic(page, "C") or set_shape_tonic(page, "D")
        settle(page, 2)
        shape_before = shape_val(page)
        written_before = written_val(page)
        pk_after_proj = pk_val(page) or sidebar_pk_input(page)
        proj_ok = has_any(str(pk_after_proj), "F", "Fm") or has_any(
            page.inner_text("body") or "", "F minor", "Fm"
        )
        mark(
            "A_projection_layers",
            "PASS" if proj_ok else "PARTIAL",
            f"pk={pk_after_proj!r} written={written_before!r} shape={shape_before!r}",
        )

        ok_active = open_sbi_active(page)
        settle(page, 3)
        body_sa = shot(page, "A-sbi-active")
        side_sa = sidebar_text(page)
        sbi_owner = has_any(body_sa, "Shape of You") and not (
            has_any(body_sa, "Trial Song") and not has_any(body_sa, "Shape of You")
        )
        sbi_pk = has_any(body_sa + side_sa, "F minor", "Fm")
        mixed_sa = fail_mixed(page, "sbi")
        mark(
            "A_sbi_active_owner",
            "PASS" if ok_active and sbi_owner and not mixed_sa else "RED",
            f"open={ok_active} pk={sbi_pk} mixed={mixed_sa}",
        )

        ok_cs = open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        body_sc = shot(page, "A-sbi-custom")
        custom_card = has_any(body_sc, "Open Custom Lab") and not has_any(
            body_sc, "Active song · Song Selection", "ACTIVE SONG · SONG SELECTION"
        )
        custom_on = bool(ok_cs) and has_any(body_sc, "Trial Song") and custom_card
        mark(
            "A_sbi_switch_custom",
            "PASS" if custom_on else "RED",
            f"open={ok_cs} card={custom_card}",
        )

        ok_back = open_sbi_active(page)
        settle(page, 3)
        body_back = shot(page, "A-sbi-active-restore")
        restored = bool(ok_back) and has_any(body_back, "Shape of You") and not (
            has_any(body_back, "Trial Song") and not has_any(body_back, "Shape of You")
        )
        pk_restored = key_hits(body_back + sidebar_text(page), "F minor", "Fm")
        mark(
            "A_sbi_active_restore",
            "PASS" if restored and pk_restored else "RED",
            f"pk={pk_restored}",
        )

        click_radio(page, "Phrase / Motif") or click_button_has(page, r"Phrase / Motif")
        settle(page, 2)
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
        settle(page, 2)
        open_sbi_active(page)
        settle(page, 2)
        body_nav = shot(page, "A-sbi-after-subtool")
        nav_ok = has_any(body_nav, "Shape of You")
        mark("A_sbi_subtool_return", "PASS" if nav_ok else "RED")

        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Shape of You", "Creative", timeout_s=50)
        settle(page, 3)
        body_ar = shot(page, "A-sbi-refresh")
        refresh_a = has_any(body_ar, "Shape of You") and not owner_split(body_ar)
        mark("A_sbi_refresh", "PASS" if refresh_a else "RED")

        # ---------- B. Custom SBI ----------
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        set_baseweb_select(page, "Practice / Concert Key", "D") or set_baseweb_select(
            page, "Practice / Concert Key", "D major"
        )
        settle(page, 2)
        body_b = shot(page, "B-custom-sbi")
        custom_card_b = has_any(body_b, "Open Custom Lab") and not has_any(
            body_b, "Active song · Song Selection", "ACTIVE SONG · SONG SELECTION"
        )
        trial_ok = (
            has_any(body_b, "Trial Song")
            and custom_card_b
            and (rendered_em_em_d_d(body_b) or has_any(body_b, "Em"))
        )
        split_b = owner_split(body_b) or (
            has_any(body_b, "Trial Song")
            and has_any(body_b, "184 chords", "Active song · Song Selection")
        ) or (
            has_any(body_b, "Trial Song")
            and has_any(body_b, "Shape of You")
            and has_any(body_b, "D minor")
            and not rendered_em_em_d_d(body_b)
        )
        mark(
            "B_custom_sbi_trial",
            "PASS" if trial_ok and not split_b else "RED",
            f"split={split_b} card={custom_card_b}",
        )

        from _walk_cbs_rendered_sweep import click_main_button

        opened_lab = click_main_button(page, r"Open Custom Lab") or click_button_has(
            page, r"Open Custom Lab"
        )
        settle(page, 3)
        body_lab = shot(page, "B-custom-lab")
        pk_lab = pk_val(page) or sidebar_pk_input(page)
        lab_d = str(pk_lab or "").strip() in {"D", "D major"} or (
            "d" in low(str(pk_lab or "")) and "minor" not in low(str(pk_lab or ""))
        )
        landed_lab = has_any(body_lab, "Leave Custom page", "Custom Progression Lab", "Presets")
        lab_ok = (
            bool(opened_lab)
            and has_any(body_lab, "Trial Song")
            and lab_d
            and landed_lab
            and not has_any(body_lab, "184 chords", "Active song · Song Selection")
        )
        mark(
            "B_open_custom_lab",
            "PASS" if lab_ok else "RED",
            f"pk={pk_lab!r} landed={landed_lab}",
        )

        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Trial Song", timeout_s=40)
        settle(page, 2)
        mark(
            "B_lab_refresh",
            "PASS" if has_any(page.inner_text("body") or "", "Trial Song") else "RED",
        )

        click_nav(page, "Creative")
        settle(page, 4)
        body_cr = shot(page, "B-creative-return")
        creative_ok = has_any(body_cr, "Trial Song") and (
            has_any(body_cr, "Custom progression", "Custom Progression") or rendered_em_em_d_d(body_cr)
        )
        split_cr = owner_split(body_cr) or (
            has_any(body_cr, "Trial Song")
            and has_any(body_cr, "Shape of You")
            and has_any(body_cr, "D minor")
            and not rendered_em_em_d_d(body_cr)
        )
        mark(
            "B_custom_lab_creative",
            "PASS" if creative_ok and not split_cr else "RED",
            f"split={split_cr}",
        )

        open_sbi_active(page)
        settle(page, 3)
        body_ga = shot(page, "B-active-after-custom")
        ga_ok = has_any(body_ga, "Shape of You") and not (
            has_any(body_ga, "Trial Song") and not has_any(body_ga, "Shape of You")
        )
        ga_pk = key_hits(body_ga + sidebar_text(page), "B minor", "Bm")
        mark(
            "B_active_restores_shape",
            "PASS" if ga_ok and ga_pk else "RED",
            f"pk_bm={ga_pk}",
        )

        open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Trial Song", timeout_s=40)
        settle(page, 3)
        body_br = shot(page, "B-custom-refresh")
        mark(
            "B_custom_sbi_refresh",
            "PASS" if has_any(body_br, "Trial Song") and not owner_split(body_br) else "RED",
        )

        # ---------- C + D. Missions + Mission Backing ----------
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        goto_improv(page, NOTES)
        ensure_missions_workspace(page, NOTES)
        settle(page, 2)
        # Prefer chords that exist on Shape-in-Dm (Em Am C D) and the simplified
        # test chart (Dm Gm Bb C). Fail if the map is still at a prior Fm PK.
        h_gm = click_available_mission_chord(page, prefer=["Gm", "Em", "Am"])
        settle(page, 2)
        click_generate_example(page)
        settle(page, 2)
        body_gm = shot(page, "C-mission-gm")
        notes_gm = ""
        nm = re.search(r"Notes:\s*([^\n]+)", body_gm, re.I)
        if nm:
            notes_gm = nm.group(1)
        stale_fm = has_any(body_gm, "Selected Mission Chord: Fm") and has_any(
            body_gm, "Practice Key: Dm"
        )
        chord_ok = bool(h_gm) and str(h_gm) not in {"Fm", "Bbm"} and not stale_fm
        mark(
            "C_mission_gm",
            "PASS" if chord_ok and has_any(body_gm, "Mission") else "RED",
            f"chord={h_gm!r} stale_fm={stale_fm} notes={notes_gm!r}",
        )

        h2 = click_available_mission_chord(page, prefer=["Am", "Bb", "Em"])
        settle(page, 2)
        click_generate_example(page)
        settle(page, 2)
        body_h2 = shot(page, "C-mission-second")
        second_ok = bool(h2) and has_any(body_h2, str(h2) if h2 else "Mission")
        mark("C_mission_second_chord", "PASS" if second_ok else "PARTIAL", f"chord={h2!r}")

        click_available_mission_chord(page, prefer=["Gm"])
        settle(page, 1)
        click_generate_example(page)
        settle(page, 2)
        try:
            opened_mb = bool(open_mission_backing(page, NOTES))
        except Exception:
            opened_mb = click_button_has(page, r"Open Mission Backing") or click_button_has(
                page, r"Open in Backing"
            )
        settle(page, 4)
        try:
            wait_for_backing(page, NOTES, "mission")
        except Exception:
            pass
        body_mb = shot(page, "D-mission-backing")
        is_mb = has_any(body_mb, "Return to Mission", "Mission Backing")
        side_mb = sidebar_text(page)
        sel_chord = str(h_gm or "Gm")
        agree = is_mb and has_any(body_mb, sel_chord) and not has_any(side_mb, "Trial Song")
        mark(
            "D_mission_backing_agree",
            "PASS" if opened_mb and agree else "RED",
            f"open={opened_mb} is_mb={is_mb}",
        )

        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Backing", "Mission", timeout_s=50)
        settle(page, 3)
        body_mbr = shot(page, "D-mission-backing-refresh")
        refresh_mb = has_any(body_mbr, "Return to Mission", "Mission") and has_any(
            body_mbr, sel_chord, "Gm", "G#m", "Abm", "Em", "Fm", "G minor"
        )
        mark("D_mission_backing_refresh", "PASS" if refresh_mb else "RED")

        set_baseweb_select(page, "Practice / Concert Key", "D#m") or set_baseweb_select(
            page, "Practice / Concert Key", "Ebm"
        )
        settle(page, 3)
        body_plus1 = shot(page, "C-mission-plus1")
        plus1_ok = (
            has_any(body_plus1, "G#m", "Abm", "Fm", "F#m")
            and not has_any(body_plus1, "A#m")
            and not has_any(body_plus1, "Notes: C – E – A")
        )
        notes_plus1 = ""
        n1 = re.search(r"Notes:\s*([^\n]+)", body_plus1, re.I)
        if n1:
            notes_plus1 = n1.group(1)
        remap = bool(re.search(r"Notes:\s*C\s*[–-]\s*E\s*[–-]\s*A", body_plus1, re.I))
        mark(
            "C_mission_interval",
            "PASS" if plus1_ok and not remap else "RED",
            f"notes={notes_plus1!r} remap={remap}",
        )

        set_baseweb_select(page, "Practice / Concert Key", "Fm") or set_baseweb_select(
            page, "Practice / Concert Key", "F minor"
        )
        settle(page, 3)
        body_plus5 = shot(page, "C-mission-plus5")
        # Gm in Dm → +5 semitones to Fm song: Cm (or B#m). Fail if still Gm or song tonic Fm.
        plus5_ok = has_any(body_plus5, "Cm", "C minor") and not (
            has_any(body_plus5, "Selected Mission Chord: Fm")
            and not has_any(body_plus5, "Cm", "C minor")
        )
        mark(
            "C_mission_larger_interval",
            "PASS" if plus5_ok else "PARTIAL",
            f"has_cm={has_any(body_plus5, 'Cm')}",
        )

        ret_m = click_button_has(page, r"Return to Mission")
        settle(page, 3)
        body_mr = shot(page, "D-mission-return")
        mixed_m = fail_mixed(page, "mission_return")
        tonic_stole = bool(
            re.search(r"selected mission chord:\s*f\s*m", low(body_mr))
        ) and not has_any(body_mr, "Cm", "C minor")
        ret_ok = bool(ret_m) and has_any(body_mr, "Mission", "Generate") and not mixed_m
        mark(
            "D_mission_backing_return",
            "PASS" if ret_ok and not tonic_stole else "RED",
            f"ret={ret_m} tonic_stole={tonic_stole} mixed={mixed_m}",
        )

        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Mission", timeout_s=40)
        settle(page, 2)
        body_mrr = shot(page, "C-mission-return-refresh")
        mark(
            "C_mission_return_refresh",
            "PASS" if has_any(body_mrr, "Mission") and not fail_mixed(page, "mission") else "RED",
        )

        # ---------- E. Motif / Phrase ----------
        leave_mission_backing(page)
        goto_improv(page, NOTES)
        settle(page, 2)
        click_radio(page, "Phrase / Motif") or click_button_has(page, r"Phrase / Motif")
        settle(page, 3)
        click_available_mission_chord(page, prefer=["Dm", "Gm", "Am"])
        click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
        settle(page, 3)
        body_mo = shot(page, "E-motif")
        notes0 = motif_notes_from_body(body_mo)
        click_button_has(page, r"Sequence Up") or click_button_has(page, r"Ascending")
        settle(page, 3)
        click_button_has(page, r"Build Motif Pattern") or click_button_has(
            page, r"Build Pattern"
        )
        settle(page, 3)
        body_up = shot(page, "E-motif-up")
        notes_up = motif_notes_from_body(body_up)
        pipes = bool(re.search(r"\s\|\s", body_up)) or " | " in (body_up or "")
        click_button_has(page, r"Sequence Down") or click_button_has(page, r"Descending")
        settle(page, 3)
        notes_dn = motif_notes_from_body(shot(page, "E-motif-down"))
        click_button_has(page, r"Invert") or click_button_has(page, r"Inversion")
        settle(page, 2)
        notes_inv = motif_notes_from_body(shot(page, "E-motif-invert"))
        before_r = [re.sub(r"\d", "", n) for n in (notes_inv or notes_dn or notes0)]
        click_button_has(page, r"^Change Rhythm$") or click_button_has(page, r"Change Rhythm")
        settle(page, 3)
        body_rh = shot(page, "E-motif-rhythm")
        after_r = [re.sub(r"\d", "", n) for n in motif_notes_from_body(body_rh)]
        rhythm_hold = True
        if before_r and after_r:
            n = min(len(before_r), len(after_r))
            rhythm_hold = before_r[:n] == after_r[:n]
        jumps = absurd_octave_jumps(notes0) if notes0 else False
        motif_ok = bool(notes0) and not jumps and notes_up != notes0 and rhythm_hold
        mark(
            "E_motif_transforms",
            "PASS" if motif_ok else "RED",
            f"n={len(notes0 or [])} up={notes_up != notes0} dn={notes_dn != notes_up} "
            f"inv={bool(notes_inv)} rhythm={rhythm_hold}",
        )
        mark("E_motif_pipes", "PASS" if pipes else "RED", f"pipe={pipes} n_up={len(notes_up or [])}")

        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Motif", "Phrase", timeout_s=40)
        settle(page, 2)
        body_mor = shot(page, "E-motif-refresh")
        mark(
            "E_motif_refresh",
            "PASS" if has_any(body_mor, "Motif", "Phrase") else "PARTIAL",
        )

        # ---------- F. Entry Style Jam ----------
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        goto_custom(page)
        settle(page, 2)
        goto_improv(page, NOTES)
        settle(page, 2)
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
        settle(page, 2)
        click_radio(page, "Style Jam Mode") or click_button_has(page, r"Style Jam") or click_radio(
            page, "Style Jam"
        )
        settle(page, 2)
        opened_ej = click_open_backing_studio(page, NOTES, "entry") or click_button_has(
            page, r"Open in Backing"
        )
        settle(page, 4)
        body_ej = shot(page, "F-jam-backing")
        ej_ok = bool(opened_ej) and has_any(body_ej, "Backing", "Jam", "Style")
        click_button_has(page, r"Return to Creative") or click_button_has(page, r"Back Creative")
        settle(page, 3)
        ok_sa2 = open_sbi_active(page)
        settle(page, 3)
        body_sa2 = shot(page, "F-sbi-after-jam")
        sbi_after = bool(ok_sa2) and has_any(body_sa2, "Shape of You") and not (
            has_any(body_sa2, "Trial Song") and not has_any(body_sa2, "Shape of You")
        )
        pk_dm = key_hits(body_sa2 + sidebar_text(page), "D minor", "Dm")
        mark(
            "F_jam_ga_restore",
            "PASS" if ej_ok and sbi_after and pk_dm else "RED",
            f"open={opened_ej} sbi={sbi_after} pk_dm={pk_dm}",
        )
        ok_cs2 = open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        body_cs2 = shot(page, "F-custom-after-jam")
        custom_after = bool(ok_cs2) and has_any(body_cs2, "Trial Song")
        mark("F_jam_custom_remembered", "PASS" if custom_after else "RED")

        # ---------- G. Key-layer matrix ----------
        set_instrument(page, "Guitar") or set_instrument(page, "Piano")
        settle(page, 1)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        enable_written_charts(page)
        pk_g1 = pk_val(page) or sidebar_pk_input(page)
        set_shape_tonic(page, "E") or set_shape_tonic(page, "A")
        settle(page, 2)
        pk_g2 = pk_val(page) or sidebar_pk_input(page)
        shape_g = shape_val(page)
        written_g = written_val(page)
        body_gmin = shot(page, "G-minor-layers")
        pk_still_dm = has_any(str(pk_g2) + " " + body_gmin, "D minor", "Dm")
        shape_changed = bool(shape_g) and low(shape_g) not in {"", "b", "bm"}
        mark(
            "G_key_layers_minor",
            "PASS" if pk_still_dm else "RED",
            f"pk1={pk_g1!r} pk2={pk_g2!r} shape={shape_g!r} written={written_g!r} "
            f"shape_set={shape_changed}",
        )

        pick_song(page, NOTES, "Perfect", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "A")
        settle(page, 2)
        enable_written_charts(page)
        set_shape_tonic(page, "C") or set_shape_tonic(page, "D")
        settle(page, 2)
        body_gmaj = shot(page, "G-major-layers")
        pk_a = pk_val(page) or sidebar_pk_input(page)
        card_a = card_practice_label(body_gmaj)
        major_ok = key_hits(str(pk_a) + " " + card_a + " " + body_gmaj, "A major")
        minor_leak = has_any(card_a, "A minor") and not has_any(card_a, "A major")
        mark(
            "G_key_layers_major",
            "PASS" if major_ok and not minor_leak else "RED",
            f"pk={pk_a!r} card={card_a!r} leak={minor_leak}",
        )

        # Enharmonic-ish: Ab / G#
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "C#m") or set_songs_practice_key(page, "Dbm")
        settle(page, 2)
        body_enh = shot(page, "G-enharmonic")
        enh_ok = has_any(body_enh, "C# minor", "Db minor", "C#m", "Dbm")
        mark("G_enharmonic_pk", "PASS" if enh_ok else "PARTIAL")

        def _caption_key(body: str, label: str) -> str:
            m = re.search(label + r":\s*([A-G](?:#|b)?(?:\s*(?:major|minor|m))?)", body or "", re.I)
            return (m.group(1) if m else "").strip()

        # ---------- H. Instrument-sensitive ----------
        set_instrument(page, "Piano")
        settle(page, 2)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Eb") or set_songs_practice_key(page, "D#")
        settle(page, 2)
        if not key_hits(page.inner_text("body") or "", "Eb", "D#"):
            set_songs_practice_key(page, "Eb")
            settle(page, 2)
        body_p = shot(page, "H-piano")
        pk_p = pk_val(page) or sidebar_pk_input(page) or _caption_key(body_p, "Concert key")
        written_p = written_val(page) or _caption_key(body_p, "Written key")
        set_instrument(page, "Saxophone") or set_instrument(page, "Alto Saxophone")
        settle(page, 2)
        set_baseweb_select(page, "Saxophone", "Alto") or set_baseweb_select(
            page, "Type", "Alto saxophone (Eb)"
        )
        settle(page, 1)
        enable_written_charts(page)
        settle(page, 2)
        body_sx = shot(page, "H-alto")
        pk_sx = pk_val(page) or sidebar_pk_input(page) or _caption_key(body_sx, "Concert key")
        written_sx = written_val(page) or _caption_key(body_sx, "Written key")
        concert_held = key_hits(str(pk_p) + " " + str(pk_sx) + " " + body_sx, "Eb", "D#")
        written_moved = bool(written_sx) and low(written_sx) != low(written_p or "")
        owner_held = has_any(body_sx, "Shape of You") and not (
            has_any(body_sx, "Trial Song") and not has_any(body_sx, "Shape of You")
        )
        inst_ok = concert_held and owner_held and "undefined" not in low(body_sx)
        mark(
            "H_instrument_pk",
            "PASS" if inst_ok and written_moved else "RED",
            f"piano={pk_p!r} sax={pk_sx!r} written_p={written_p!r} written_sx={written_sx!r} "
            f"concert={concert_held} moved={written_moved} owner={owner_held}",
        )
        set_instrument(page, "Piano")
        settle(page, 2)
        body_back_i = shot(page, "H-piano-return")
        pk_back = pk_val(page) or sidebar_pk_input(page)
        back_i = (
            has_any(body_back_i, "Shape of You")
            and key_hits(str(pk_back) + " " + body_back_i, "Eb", "D#")
            and "undefined" not in low(body_back_i)
        )
        mark("H_instrument_return", "PASS" if back_i else "RED", f"pk={pk_back!r}")

        # ---------- I. Navigation / persistence ----------
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        click_nav(page, "Practice")
        settle(page, 2)
        click_nav(page, "Backing")
        settle(page, 3)
        click_nav(page, "Creative")
        settle(page, 3)
        click_nav(page, "Songs")
        settle(page, 2)
        body_navi = shot(page, "I-nav-cycle")
        nav_cycle = has_any(body_navi, "Shape of You") and has_any(body_navi, "D minor", "Dm")
        mark("I_nav_cycle", "PASS" if nav_cycle else "RED")

        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Shape of You", timeout_s=50)
        settle(page, 3)
        body_ir = shot(page, "I-songs-refresh")
        refresh_i = has_any(body_ir, "Shape of You") and has_any(body_ir, "D minor", "Dm")
        mark("I_songs_refresh", "PASS" if refresh_i else "RED")

        goto_custom(page)
        settle(page, 2)
        shot(page, "I-pre-reboot-custom")
        click_nav(page, "Songs")
        settle(page, 2)
        shot(page, "I-pre-reboot-songs")
        hard_reboot(port)
        page2 = browser.new_page(viewport={"width": 1440, "height": 960})
        wait_up(page2, URL)
        wait_for_body(page2, "Shape of You", "Songs", "Welcome", timeout_s=70)
        settle(page2, 4)
        body_rb = shot(page2, "I-post-reboot")
        reboot_songs = has_any(body_rb, "Shape of You")
        click_nav(page2, "Songs")
        settle(page2, 2)
        body_rbs = shot(page2, "I-post-reboot-songs")
        reboot_pk = key_hits(body_rbs, "D minor", "Dm")
        goto_custom(page2)
        settle(page2, 3)
        body_rbc = shot(page2, "I-post-reboot-custom")
        reboot_custom = has_any(body_rbc, "Trial Song")
        mark(
            "I_hard_reboot",
            "PASS" if reboot_songs and reboot_pk and reboot_custom else "RED",
            f"songs={reboot_songs} pk={reboot_pk} custom={reboot_custom}",
        )

        browser.close()

    passed = sum(1 for v in RESULTS.values() if v == "PASS")
    red = sum(1 for v in RESULTS.values() if v == "RED")
    partial = sum(1 for v in RESULTS.values() if v == "PARTIAL")
    critical_red = [g for g in CRITICAL if RESULTS.get(g) == "RED"]
    overall = "PASS" if red == 0 and not critical_red else "RED"
    summary = {
        "meta": meta,
        "OVERALL": overall,
        "PASS": passed,
        "RED": red,
        "PARTIAL": partial,
        "critical_red": critical_red,
        "results": RESULTS,
        "notes": NOTES[-50:],
    }
    (OUT / "cbs-live-draft-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"OVERALL={overall}, PASS={passed}, PARTIAL={partial}, RED={red}",
        f"sha={meta.get('sha')}",
        f"critical_red={critical_red}",
    ]
    for gate, status in RESULTS.items():
        lines.append(f"{status} {gate}")
    (OUT / "cbs-live-draft-summary.txt").write_text("\n".join(lines), encoding="utf-8")
    log(lines[0])
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
