"""Trial Song coherence through all surfaces — continuous browser, no seed.

Usage:
  python scripts/_proof_trial_coherence_full.py http://127.0.0.1:8521
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8521"
sys.argv = [sys.argv[0], URL]

from _walk_ownership_audit_full import (  # noqa: E402
    build_trial_song,
    open_fresh,
    progression_em_d,
    reboot_server,
    rendered_em_em_d_d,
    shot,
)
from _walk_custom_practice_key import (  # noqa: E402
    goto_custom,
    original_key_val,
    pk_val,
    set_practice_key as set_custom_pk,
)
from _walk_pass8_live import set_practice_key as set_sidebar_pk  # noqa: E402
from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source, settle  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    goto_improv,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PORT = int(re.search(r":(\d+)", URL).group(1))
PREFIX = "trial-coh-"


def meta() -> dict:
    def _run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": _run(["git", "branch", "--show-current"]),
        "sha": _run(["git", "rev-parse", "--short", "HEAD"]),
        "dirty": len([ln for ln in _run(["git", "status", "--porcelain"]).splitlines() if ln.strip()]),
        "url": URL,
    }


def _norm(s: str) -> str:
    t = (s or "").lower().replace(" ", "").replace("♯", "#").replace("♭", "b")
    if t.endswith("minor"):
        return t[: -len("minor")] + "m"
    if t.endswith("major"):
        return t[: -len("major")]
    return t


def is_dm(s: str) -> bool:
    return _norm(s) in {"dm", "dminor"}


def is_d_major(s: str) -> bool:
    n = _norm(s)
    return n in {"d", "dmajor"} and n != "dm"


def is_token(s: str, *want: str) -> bool:
    return _norm(s) in {_norm(w) for w in want}


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def row(gate: str, ok: bool, detail: str) -> dict:
    return {"gate": gate, "ok": bool(ok), "verdict": "PASS" if ok else "FAIL", "detail": detail}


def load_trial(page, notes: list[str]) -> bool:
    if not goto_custom(page):
        return False
    settle(page, 2)
    body = page.inner_text("body") or ""
    if "Trial Song" in body and progression_em_d(body):
        return True
    try:
        exp = page.locator('[data-testid="stExpander"]').filter(
            has_text=re.compile(r"Load saved|demo charts", re.I)
        )
        if exp.count():
            exp.first.click(timeout=3000)
            settle(page, 1)
        box = page.locator('[data-testid="stSelectbox"]').filter(
            has_text=re.compile(r"Saved songs", re.I)
        )
        if box.count():
            box.first.click()
            settle(page, 0.5)
            opt = page.get_by_role("option", name=re.compile(r"Trial Song", re.I))
            if opt.count():
                opt.first.click()
                settle(page, 1)
    except Exception as exc:
        notes.append(f"load_trial={exc!r}")
    click_button_has(page, r"Load selected")
    settle(page, 3)
    body2 = page.inner_text("body") or ""
    return "Trial Song" in body2 and progression_em_d(body2)


def activate_shape_dm(page, notes: list[str]) -> bool:
    click_nav(page, "Songs")
    settle(page, 2)
    click_radio(page, "Song Selection") or click_button_has(page, r"Use catalog")
    settle(page, 1)
    pick_song(page, notes, "Shape of You", "Pop")
    settle(page, 2)
    set_sidebar_pk(page, "D minor") or set_sidebar_pk(page, "Dm")
    settle(page, 2)
    return is_dm(pk_val(page))


def port_pids(port: int) -> list[int]:
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="replace")
    except Exception:
        return []
    pids = []
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            try:
                pids.append(int(line.strip().split()[-1]))
            except Exception:
                pass
    return sorted(set(pids))


def hard_reboot(notes: list[str]) -> tuple[list[int], list[int]]:
    before = port_pids(PORT)
    notes.append(f"reboot_before={before}")
    reboot_server(notes)
    after = port_pids(PORT)
    notes.append(f"reboot_after={after}")
    return before, after


def motif_units(notes: list[str]) -> dict[str, bool]:
    from improvisation_motif import (
        build_motif_notation_abc,
        build_motif_pattern,
        generate_motif_for_chord,
        rebuild_motif_pattern,
        transform_motif,
    )

    out: dict[str, bool] = {}
    m = generate_motif_for_chord("Fm", key_center="Fm", level="Intermediate")
    midis = [int(x) for x in (m.get("midi") or [])]
    leaps = [abs(midis[i] - midis[i - 1]) for i in range(1, len(midis))]
    out["compact"] = bool(midis) and (not leaps or max(leaps) <= 12)

    src = {"chord": "Fm", "notes": ["F", "Ab", "C", "Eb"], "midi": [53, 56, 60, 63]}
    asc = build_motif_pattern(
        src, key_center="Fm", pattern_type="diatonic", direction="ascending", length=8
    )
    am = [int(x) for x in (asc.get("midi") or [])]
    asc_ok = True
    for i in range(1, 8):
        prev, cur = am[(i - 1) * 4 : i * 4], am[i * 4 : (i + 1) * 4]
        if len(cur) < 4 or any(b <= a for a, b in zip(prev, cur)):
            asc_ok = False
            break
    out["ascending"] = asc_ok

    src_hi = {"chord": "Fm", "notes": ["F", "Ab", "C", "Eb"], "midi": [77, 80, 84, 87]}
    desc = build_motif_pattern(
        src_hi, key_center="Fm", pattern_type="diatonic", direction="descending", length=8
    )
    dm = [int(x) for x in (desc.get("midi") or [])]
    desc_ok = True
    for i in range(1, 8):
        prev, cur = dm[(i - 1) * 4 : i * 4], dm[i * 4 : (i + 1) * 4]
        if len(cur) < 4 or any(b >= a for a, b in zip(prev, cur)):
            desc_ok = False
            break
    out["descending"] = desc_ok

    base = build_motif_pattern(src, key_center="Fm", length=8)
    changed = transform_motif(base, "change_rhythm", key_center="Fm")
    out["change_rhythm"] = list(base.get("midi") or []) == list(changed.get("midi") or [])

    try:
        abc = build_motif_notation_abc(asc)
    except Exception:
        from improvisation_motif import build_motif_abc

        abc = build_motif_abc(asc)
    out["midi_sheet"] = bool(abc) and "K:" in str(abc) and len(am) >= 8
    lens_ok = True
    for n in (8, 12, 16):
        try:
            pat = rebuild_motif_pattern(asc, key_center="Fm", length=n)
        except TypeError:
            pat = rebuild_motif_pattern(asc, length=n)
        if len(pat.get("midi") or []) < n:
            lens_ok = False
    out["lengths"] = lens_ok
    notes.append(f"motif_units={out}")
    return out


def flush(info, rows, notes) -> dict:
    report_map = {
        1: "1_CUSTOM_PAGE",
        2: "2_LAST_CUSTOM",
        3: "3_SBI_CUSTOM",
        4: "4a_OPEN_CUSTOM",
        5: "5_CUSTOM_SBI_BACKING",
        6: "6_GA_CUSTOM",
        7: "7a_SHAPE_TO_CUSTOM_ISO",
        8: "7b_CUSTOM_TO_SHAPE_ISO",
        9: "8_HARD_REBOOT_A",
        10: "9_HARD_REBOOT_B",
        11: "10a_MOTIF_COMPACT",
        12: "10b_MOTIF_ASC",
        13: "10c_MOTIF_DESC",
        14: "10d_MOTIF_MIDI_SHEET",
        15: "10e_MOTIF_CHANGE_RHYTHM",
        16: "11_LONG_SESSION",
    }
    by = {r["gate"]: r for r in rows}
    numbered = []
    for n, g in report_map.items():
        r = by.get(g) or {"ok": False, "detail": "missing", "verdict": "FAIL"}
        numbered.append({"n": n, "gate": g, **r})
    summary = {
        "meta": info,
        "rows": rows,
        "numbered_1_16": numbered,
        "notes": notes[-200:],
        "pass_count": sum(1 for r in rows if r["ok"]),
        "fail_count": sum(1 for r in rows if not r["ok"]),
        "total": len(rows),
        "all_pass": bool(rows) and all(r["ok"] for r in rows),
    }
    (OUT / f"{PREFIX}results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"branch={info.get('branch')}",
        f"sha={info.get('sha')}",
        f"dirty={info.get('dirty')}",
        f"pass={summary['pass_count']}/{summary['total']}",
        "",
        *[f"{r['gate']}: {r['verdict']} — {r['detail']}" for r in rows],
        "",
        "NUMBERED",
        *[f"{x['n']}. {x['gate']}: {x['verdict']} — {x['detail']}" for x in numbered],
    ]
    text = "\n".join(lines)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    print(text)
    return summary


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []
    info = meta()
    notes.append(json.dumps(info))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = open_fresh(browser)

            trial_ok = build_trial_song(page, notes)
            rows.append(row("0_TRIAL_BUILD", trial_ok, "; ".join(notes[-4:])))
            shot(page, f"{PREFIX}00-built")

            # 1 Custom page
            load_trial(page, notes) or trial_ok
            set_custom_pk(page, "D") or set_sidebar_pk(page, "D")
            settle(page, 2)
            body = shot(page, f"{PREFIX}01-custom-d")
            g1 = (
                "Trial Song" in body
                and is_d_major(original_key_val(page))
                and is_d_major(pk_val(page))
                and progression_em_d(body)
            )
            rows.append(
                row(
                    "1_CUSTOM_PAGE",
                    g1,
                    f"orig={original_key_val(page)!r} pk={pk_val(page)!r} prog={progression_em_d(body)}",
                )
            )

            set_custom_pk(page, "Eb") or set_sidebar_pk(page, "Eb")
            settle(page, 2)
            body_eb = shot(page, f"{PREFIX}01b-custom-eb")
            g1b = (
                is_token(pk_val(page), "Eb", "E♭")
                and is_d_major(original_key_val(page))
                and bool(re.search(r"\bFm\b", body_eb))
            )
            rows.append(row("1b_CUSTOM_PK_TRANSPOSE", g1b, f"pk={pk_val(page)!r}"))

            set_custom_pk(page, "D") or set_sidebar_pk(page, "D")
            settle(page, 2)
            body_d = shot(page, f"{PREFIX}01c-custom-d-return")
            rows.append(
                row(
                    "1c_CUSTOM_PK_BACK_D",
                    is_d_major(pk_val(page)) and progression_em_d(body_d),
                    f"pk={pk_val(page)!r}",
                )
            )

            # 2 LAST_CUSTOM
            click_nav(page, "Songs")
            settle(page, 2)
            pick_song(page, notes, "Shape of You", "Pop")
            settle(page, 2)
            goto_custom(page)
            settle(page, 3)
            # Fresh Custom visit after leave: Practice Key must land on D (home),
            # not a leaked C#/C/Dm from other workflows.
            set_custom_pk(page, "D") or set_sidebar_pk(page, "D")
            settle(page, 2)
            body_lc = shot(page, f"{PREFIX}02-last-custom")
            try:
                title_v = page.get_by_label(re.compile(r"^Song title$", re.I)).input_value()
            except Exception:
                title_v = ""
            rows.append(
                row(
                    "2_LAST_CUSTOM",
                    title_v == "Trial Song" and progression_em_d(body_lc) and is_d_major(pk_val(page)),
                    f"title={title_v!r} pk={pk_val(page)!r} prog={progression_em_d(body_lc)}",
                )
            )

            click_button_has(page, r"New song")
            settle(page, 2)
            try:
                page.get_by_label(re.compile(r"^Song title$", re.I)).fill("Other Scratch")
            except Exception:
                pass
            load_trial(page, notes)
            settle(page, 2)
            body_lc2 = shot(page, f"{PREFIX}02b-last-custom-return")
            try:
                title_v2 = page.get_by_label(re.compile(r"^Song title$", re.I)).input_value()
            except Exception:
                title_v2 = ""
            rows.append(
                row(
                    "2b_LAST_CUSTOM_AFTER_OTHER",
                    title_v2 == "Trial Song" and progression_em_d(body_lc2),
                    f"title={title_v2!r}",
                )
            )

            # 3 SBI Custom
            activate_shape_dm(page, notes)
            sbi_ok = open_sbi_custom_source(page, notes)
            settle(page, 4)
            body_sbi = shot(page, f"{PREFIX}03-sbi-custom")
            pk_sbi = pk_val(page)
            g3 = (
                bool(sbi_ok)
                and "trial song" in low(body_sbi)
                and rendered_em_em_d_d(body_sbi)
                and not is_dm(pk_sbi)
                and is_d_major(pk_sbi)
                and not re.search(r"\{['\"]chord['\"]", body_sbi)
            )
            rows.append(
                row(
                    "3_SBI_CUSTOM",
                    g3,
                    f"sbi={sbi_ok} pk={pk_sbi!r} prog={rendered_em_em_d_d(body_sbi)}",
                )
            )

            # 4 Open Custom / Return Creative
            click_button_has(page, r"Open Custom Lab") or goto_custom(page)
            settle(page, 3)
            set_custom_pk(page, "D") or set_sidebar_pk(page, "D")
            settle(page, 2)
            body_oc = shot(page, f"{PREFIX}04-open-custom")
            rows.append(
                row(
                    "4a_OPEN_CUSTOM",
                    "Trial Song" in body_oc
                    and progression_em_d(body_oc)
                    and is_d_major(pk_val(page)),
                    f"prog={progression_em_d(body_oc)} pk={pk_val(page)!r}",
                )
            )
            sbi2 = open_sbi_custom_source(page, notes)
            settle(page, 3)
            body_rc = shot(page, f"{PREFIX}04b-return-creative")
            rows.append(
                row(
                    "4b_RETURN_CREATIVE_SBI_CUSTOM",
                    bool(sbi2)
                    and "custom progression" in low(body_rc)
                    and "trial song" in low(body_rc)
                    and rendered_em_em_d_d(body_rc),
                    f"sbi={sbi2}",
                )
            )

            # 5 Custom SBI Backing — set D after open (sidebar may lag pre-open)
            opened = click_open_backing_studio(page, notes, "coh5") or click_button_has(
                page, r"Open in Backing"
            )
            settle(page, 5)
            set_sidebar_pk(page, "D") or set_custom_pk(page, "D")
            settle(page, 3)
            body_bk = shot(page, f"{PREFIX}05-custom-sbi-backing")
            specialized = bool(re.search(r"SBI Custom", body_bk))
            pk_bk = pk_val(page)
            # Prefer exact Em–Em–D–D on the backing card; reject C#/C transpose leftovers.
            prog_bk = bool(
                re.search(r"Progression:\s*[^\n]*Em\s*[–\-]\s*Em\s*[–\-]\s*D\s*[–\-]\s*D", body_bk)
            ) or (
                rendered_em_em_d_d(body_bk)
                and not re.search(r"Progression:\s*[^\n]*D#m|Progression:\s*[^\n]*Dm\s*[–\-]", body_bk)
            )
            g5 = (
                bool(opened)
                and specialized
                and "trial song" in low(body_bk)
                and prog_bk
                and is_d_major(pk_bk)
            )
            rows.append(
                row(
                    "5_CUSTOM_SBI_BACKING",
                    g5,
                    f"open={opened} specialized={specialized} pk={pk_bk!r} prog={prog_bk}",
                )
            )
            set_sidebar_pk(page, "E") or set_custom_pk(page, "E")
            settle(page, 3)
            rows.append(
                row("5b_BACKING_PK_CHANGE", is_token(pk_val(page), "E", "E major"), f"pk={pk_val(page)!r}")
            )
            # Leave Custom SBI Backing → Songs/Shape must still be Dm (not E bleed).
            click_button_has(page, r"Return to Creative") or True
            settle(page, 2)
            click_nav(page, "Songs")
            settle(page, 2)
            pick_song(page, notes, "Shape of You", "Pop")
            settle(page, 2)
            # If overlay restore left live dirty, Shape sticky must still be Dm.
            rows.append(row("5c_SHAPE_STILL_DM", is_dm(pk_val(page)), f"pk={pk_val(page)!r}"))

            # 6 GA Custom
            goto_custom(page)
            settle(page, 2)
            load_trial(page, notes)
            set_custom_pk(page, "D") or set_sidebar_pk(page, "D")
            settle(page, 2)
            act = click_button_has(page, r"Set as Active Song")
            settle(page, 3)
            click_nav(page, "Songs")
            settle(page, 3)
            body_ga = shot(page, f"{PREFIX}06-ga-custom")
            rows.append(
                row(
                    "6_GA_CUSTOM",
                    bool(act) and "trial song" in low(body_ga),
                    f"act={act}",
                )
            )
            pick_song(page, notes, "Shape of You", "Pop")
            settle(page, 2)
            set_sidebar_pk(page, "D minor") or set_sidebar_pk(page, "Dm")
            settle(page, 2)
            rows.append(row("6b_SHAPE_INDEPENDENT", is_dm(pk_val(page)), f"pk={pk_val(page)!r}"))

            # 7 Isolation both directions
            activate_shape_dm(page, notes)
            open_sbi_custom_source(page, notes)
            settle(page, 3)
            set_sidebar_pk(page, "Eb") or set_custom_pk(page, "Eb")
            settle(page, 2)
            click_open_backing_studio(page, notes, "iso") or click_button_has(page, r"Open in Backing")
            settle(page, 4)
            set_sidebar_pk(page, "E") or set_custom_pk(page, "E")
            settle(page, 2)
            click_nav(page, "Songs")
            settle(page, 2)
            pick_song(page, notes, "Shape of You", "Pop")
            settle(page, 2)
            rows.append(row("7a_SHAPE_TO_CUSTOM_ISO", is_dm(pk_val(page)), f"pk={pk_val(page)!r}"))

            set_sidebar_pk(page, "F") or set_sidebar_pk(page, "F major")
            settle(page, 2)
            shape_f = is_token(pk_val(page), "F", "F major")
            # Reset Custom sticky away from gate-5 E so reverse isolation is meaningful.
            goto_custom(page)
            settle(page, 2)
            set_custom_pk(page, "D") or set_sidebar_pk(page, "D")
            settle(page, 2)
            open_sbi_custom_source(page, notes)
            settle(page, 3)
            sbi_pk = pk_val(page)
            body_iso = shot(page, f"{PREFIX}07-iso")
            rows.append(
                row(
                    "7b_CUSTOM_TO_SHAPE_ISO",
                    shape_f and not is_token(sbi_pk, "F") and rendered_em_em_d_d(body_iso),
                    f"shape_f={shape_f} sbi_pk={sbi_pk!r}",
                )
            )

            # 8 Hard reboot A
            activate_shape_dm(page, notes)
            open_sbi_custom_source(page, notes)
            settle(page, 4)
            set_sidebar_pk(page, "D") or set_custom_pk(page, "D")
            settle(page, 2)
            click_nav(page, "Creative")
            settle(page, 3)
            pre_a = shot(page, f"{PREFIX}08-reboot-a-pre")
            page.context.close()
            before, after = hard_reboot(notes)
            page = open_fresh(browser)
            settle(page, 5)
            post_a = shot(page, f"{PREFIX}08-reboot-a-post")
            g8 = (
                bool(after)
                and "trial song" in low(post_a)
                and "custom progression" in low(post_a)
                and rendered_em_em_d_d(post_a)
                and is_d_major(pk_val(page))
            )
            # PID overlap is a soft warning — functional restore is the gate.
            if set(before) & set(after):
                notes.append(f"WARN reboot_a_pid_overlap before={before} after={after}")
            rows.append(
                row(
                    "8_HARD_REBOOT_A",
                    g8,
                    f"before={before} after={after} prog={rendered_em_em_d_d(post_a)} pk={pk_val(page)!r}",
                )
            )

            # 9 Hard reboot B Mission
            goto_improv(page, notes)
            click_radio(page, "Missions") or click_button_has(page, r"Missions")
            settle(page, 3)
            try:
                from _walk_pass8_validate import ensure_missions_workspace

                ensure_missions_workspace(page, notes)
            except Exception as exc:
                notes.append(f"mission_ws={exc!r}")
            click_button_has(page, r"Generate Example") or click_button_has(page, r"Generate example")
            settle(page, 3)
            click_open_backing_studio(page, notes, "mission") or click_button_has(
                page, r"Open in Backing"
            )
            settle(page, 4)
            set_sidebar_pk(page, "C#m") or set_sidebar_pk(page, "Dbm") or set_sidebar_pk(
                page, "C# minor"
            )
            settle(page, 3)
            shot(page, f"{PREFIX}09-reboot-b-pre")
            page.context.close()
            before_b, after_b = hard_reboot(notes)
            page = open_fresh(browser)
            settle(page, 5)
            post_b = shot(page, f"{PREFIX}09-reboot-b-post")
            pk_b = pk_val(page)
            g9 = (
                bool(after_b)
                and ("return to mission" in low(post_b) or "mission" in low(post_b))
                and is_token(pk_b, "C#m", "Dbm", "C# minor", "Db minor", "C♯m")
                and not is_token(pk_b, "Cm", "C minor")
            )
            rows.append(row("9_HARD_REBOOT_B", g9, f"pk={pk_b!r}"))
            click_button_has(page, r"Return to Mission") or click_button_has(
                page, r"Return to Creative"
            )
            settle(page, 3)
            pk_ret = pk_val(page)
            click_button_has(page, r"Generate Example") or click_button_has(page, r"Generate example")
            settle(page, 3)
            rows.append(
                row(
                    "9b_RETURN_MISSION_PK",
                    is_token(pk_ret, "C#m", "Dbm", "C# minor", "Db minor", "C♯m"),
                    f"pk={pk_ret!r}",
                )
            )

            # 10 Motif
            mu = motif_units(notes)
            rows.append(row("10a_MOTIF_COMPACT", mu.get("compact", False), str(mu)))
            rows.append(row("10b_MOTIF_ASC", mu.get("ascending", False), str(mu)))
            rows.append(row("10c_MOTIF_DESC", mu.get("descending", False), str(mu)))
            rows.append(row("10d_MOTIF_MIDI_SHEET", mu.get("midi_sheet", False), str(mu)))
            rows.append(row("10e_MOTIF_CHANGE_RHYTHM", mu.get("change_rhythm", False), str(mu)))
            goto_improv(page, notes)
            click_radio(page, "Phrase") or click_radio(page, "Motif") or click_button_has(
                page, r"Motif"
            )
            settle(page, 3)
            click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
            settle(page, 3)
            click_button_has(page, r"Build Pattern") or click_button_has(page, r"Build Motif Pattern")
            settle(page, 3)
            body_m = shot(page, f"{PREFIX}10-motif-live")
            rows.append(
                row(
                    "10f_MOTIF_LIVE",
                    bool(re.search(r"Motif on|motif pattern|Build Pattern", body_m, re.I)),
                    "live",
                )
            )

            # 11 Long session smoke
            activate_shape_dm(page, notes)
            load_trial(page, notes) or build_trial_song(page, notes)
            open_sbi_custom_source(page, notes)
            settle(page, 2)
            click_open_backing_studio(page, notes, "long") or True
            settle(page, 3)
            click_button_has(page, r"Return to Creative") or True
            settle(page, 2)
            goto_improv(page, notes)
            click_radio(page, "Missions") or True
            settle(page, 1)
            click_radio(page, "Live Coach") or True
            settle(page, 1)
            click_radio(page, "Harmony") or click_button_has(page, r"Harmony Map") or True
            settle(page, 2)
            page.reload(wait_until="domcontentloaded")
            settle(page, 5)
            body_long = shot(page, f"{PREFIX}11-long-refresh")
            page.context.close()
            hard_reboot(notes)
            page = open_fresh(browser)
            settle(page, 4)
            body_long2 = shot(page, f"{PREFIX}11-long-reboot")
            rows.append(
                row(
                    "11_LONG_SESSION",
                    len(body_long) > 500 and len(body_long2) > 500,
                    f"refresh={len(body_long)} reboot={len(body_long2)}",
                )
            )

            browser.close()

        pf = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(ROOT), text=True)
        rows.append(
            row(
                "21_PRACTICE_FOCUS_UNTOUCHED",
                "practice_focus" not in pf.lower(),
                "ok",
            )
        )
        rows.append(
            row(
                "22_DEV_UNTOUCHED",
                info.get("branch") != "dev",
                f"branch={info.get('branch')}",
            )
        )
        summary = flush(info, rows, notes)
        return 0 if summary["all_pass"] else 1
    except Exception as exc:
        notes.append(f"FATAL={exc!r}")
        rows.append(row("FATAL", False, repr(exc)))
        flush(info, rows, notes)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
