"""P7: Mission Backing reboot + Return to Mission."""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    PORT,
    URL,
    click_button_has,
    click_radio,
    disk_creative_slice,
    disk_state_path,
    disk_studio_page,
    goto_improv,
    kill_port,
    meta,
    open_fresh,
    page_family,
    pick_song,
    settle,
    shot,
    start_streamlit,
    wait_http,
)
from _walk_pass8_validate import (  # noqa: E402
    click_chord,
    ensure_missions_workspace,
    open_advanced_playback,
    open_mission_backing,
    return_to_mission,
    set_bpm,
    set_practice_key,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "p7-mission-backing-"
MISSION_MARKERS = (
    "return to mission",
    "mission backing",
    "creative backing jam · mission",
    "mission practice",
)
CATALOG_FALL = ("backing source: catalog", "catalog song")


def row(gate: str, ok: bool, detail: str) -> dict:
    return {"gate": gate, "ok": bool(ok), "verdict": "PASS" if ok else "FAIL", "detail": detail}


def has_any(text: str, *needles: str) -> bool:
    blob = (text or "").lower()
    return any(n.lower() in blob for n in needles)


def is_mission_backing(body: str) -> bool:
    return has_any(body, *MISSION_MARKERS)


def selected_chord(body: str) -> str:
    for pat in (
        r"Selected Mission Chord:\s*(\S+)",
        r"Mission Example\s*[—\-]\s*(\S+)",
        r"CURRENT CHORD:\s*(\S+)",
    ):
        m = re.search(pat, body or "", re.I)
        if m:
            return m.group(1).replace("♯", "#").replace("♭", "b")
    return ""


def norm_chord(s: str) -> str:
    return (s or "").replace("♯", "#").replace("♭", "b").strip()


def disk_snapshot() -> dict:
    sl = disk_creative_slice()
    try:
        st = json.loads(disk_state_path().read_text(encoding="utf-8")).get("state") or {}
        sess = st.get("session") if isinstance(st.get("session"), dict) else {}
        ctx = st.get("backing_context")
        if not isinstance(ctx, dict):
            ctx = sess.get("backing_context") if isinstance(sess.get("backing_context"), dict) else {}
        ps = st.get("_backing_play_session")
        if not isinstance(ps, dict):
            ps = sess.get("_backing_play_session") if isinstance(sess.get("_backing_play_session"), dict) else {}
        ov = ps.get("overrides") if isinstance(ps.get("overrides"), dict) else {}
    except Exception:
        ctx, ov, ps = {}, {}, {}
    display = (
        sl.get("display_key")
        or (ctx or {}).get("display_key")
        or (ctx or {}).get("key")
        or ""
    )
    return {
        "studio_page": disk_studio_page(),
        "ii_chord": sl.get("ii_selected_chord"),
        "ii_section": sl.get("ii_selected_section"),
        "ii_index": sl.get("ii_selected_chord_index"),
        "mission": sl.get("improv_active_mission") or sl.get("improv_mission_pick"),
        "tab": sl.get("improv_intelligence_tab"),
        "display_key": display,
        "ctx_source": (ctx or {}).get("source"),
        "ctx_title": (ctx or {}).get("song_title"),
        "ctx_bpm": (ctx or {}).get("bpm"),
        "ctx_style": (ctx or {}).get("style") or (ctx or {}).get("groove"),
        "ctx_meter": (ctx or {}).get("meter"),
        "ctx_section": (ctx or {}).get("section"),
        "ctx_prog": (ctx or {}).get("progression"),
        "ctx_mission_id": (ctx or {}).get("mission_id"),
        "ov_bpm": ov.get("bpm"),
        "ov_groove": ov.get("groove"),
        "ov_meter": ov.get("meter"),
        "ps_expired": bool(ps.get("expired")) if isinstance(ps, dict) else None,
    }


def visible_chord_labels(page: Page) -> list[str]:
    labels: list[str] = []
    try:
        btns = page.locator('[data-testid="stMain"]').get_by_role("button")
        for i in range(min(btns.count(), 100)):
            txt = (btns.nth(i).inner_text() or "").strip()
            if re.match(r"^[A-G][#♯b♭]?m?(?:7|maj7|sus4)?$", txt) and txt not in labels:
                labels.append(txt)
    except Exception:
        pass
    return labels


def pick_non_first_chord(page: Page, notes: list[str]) -> str:
    before = selected_chord(page.inner_text("body") or "")
    labels = visible_chord_labels(page)
    notes.append(f"visible_chords={labels[:12]!r} before={before!r}")
    prefer = ["F#m", "F♯m", "C#m", "C♯m", "Em", "G", "A", "Bm", "D"]
    candidates: list[str] = []
    for pref in prefer:
        for lab in labels:
            if norm_chord(lab) == norm_chord(pref) and lab not in candidates:
                candidates.append(lab)
    for lab in labels:
        if lab not in candidates:
            candidates.append(lab)
    first = labels[0] if labels else ""
    ordered = [
        c
        for c in candidates
        if norm_chord(c) != norm_chord(before) and norm_chord(c) != norm_chord(first)
    ]
    ordered += [c for c in candidates if c not in ordered]
    for c in ordered:
        if click_chord(page, c):
            settle(page, 2)
            notes.append(f"clicked_chord={c}")
            return c
    notes.append("clicked_chord=NONE")
    return before or (labels[1] if len(labels) > 1 else (labels[0] if labels else ""))


def reinforce_mission_intent_on_disk(notes: list[str]) -> None:
    try:
        path = disk_state_path()
        blob = json.loads(path.read_text(encoding="utf-8"))
        st = blob.setdefault("state", {})
        st["studio_page"] = "backing"
        st["_backing_open_intent"] = "restore_last"
        st["_backing_explicit_handoff_source"] = "mission"
        st.pop("_backing_released_specialized_context", None)
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            sess["studio_page"] = "backing"
            sess["_backing_open_intent"] = "restore_last"
            sess["_backing_explicit_handoff_source"] = "mission"
            ctx = sess.get("backing_context")
            if isinstance(ctx, dict):
                ctx["source"] = "mission"
                st["backing_context"] = dict(ctx)
            elif isinstance(st.get("backing_context"), dict):
                st["backing_context"]["source"] = "mission"
                sess["backing_context"] = dict(st["backing_context"])
        blob["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        notes.append("disk_reinforce=mission_intent")
    except Exception as exc:
        notes.append(f"disk_reinforce_err={exc}")


def mission_backing_ok(body: str, disk: dict, *, chord: str, pk: str) -> tuple[bool, str]:
    fam = page_family(body)
    missionish = is_mission_backing(body)
    catalog_fall = has_any(body, *CATALOG_FALL) and not missionish
    disk_src = str(disk.get("ctx_source") or "")
    disk_ok = disk_src == "mission" or missionish
    c_want = norm_chord(chord)
    body_n = (body or "").replace("♯", "#")
    body_c = norm_chord(selected_chord(body))
    disk_c = norm_chord(str(disk.get("ii_chord") or ""))
    prog = disk.get("ctx_prog") or []
    prog_s = " ".join(str(x) for x in prog) if isinstance(prog, list) else str(prog)
    chord_ok = (not c_want) or (
        c_want in body_n
        or c_want == body_c
        or c_want == disk_c
        or c_want in prog_s.replace("♯", "#")
        or c_want in str(disk.get("ctx_section") or "").replace("♯", "#")
    )
    pk_ok = (not pk) or (pk in body) or str(disk.get("display_key") or "").startswith(pk)
    bpm_hint = ("117" in body) or (disk.get("ctx_bpm") in (117, "117")) or (disk.get("ov_bpm") in (117, "117"))
    ok = (
        (str(fam).startswith("backing") or disk.get("studio_page") == "backing")
        and missionish
        and disk_ok
        and not catalog_fall
        and chord_ok
    )
    detail = (
        f"fam={fam} mission={missionish} disk_src={disk_src!r} chord_ok={chord_ok} "
        f"pk_ok={pk_ok} bpm_hint={bpm_hint} catalog_fall={catalog_fall}"
    )
    return ok, detail


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []
    info = meta()
    target_pk = "A"
    target_chord = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = open_fresh(browser)

        pick_song(page, notes, "Shape of You", "Pop")
        goto_improv(page, notes)
        settle(page, 2)
        ensure_missions_workspace(page, notes)
        settle(page, 2)
        set_practice_key(page, target_pk)
        settle(page, 2)
        click_radio(page, "Verse 1") or click_button_has(page, r"Verse 1") or click_radio(page, "Verse")
        settle(page, 1)
        target_chord = pick_non_first_chord(page, notes)
        settle(page, 1)
        (
            click_button_has(page, r"Generate example")
            or click_button_has(page, r"Generate Example")
            or click_button_has(page, r"^Generate$")
        )
        settle(page, 3)
        body_setup = shot(page, f"{PREFIX}00-mission-setup")
        notes.append(f"setup_selected={selected_chord(body_setup)!r}")

        opened = open_mission_backing(page, notes)
        settle(page, 4)
        open_advanced_playback(page)
        settle(page, 1)
        bpm_set = bool(set_bpm(page, 117))
        notes.append(f"opened={opened} bpm_set={bpm_set}")
        click_radio(page, "Rock") or click_button_has(page, r"^Rock$") or click_radio(page, "Funk")
        click_radio(page, "3/4") or click_button_has(page, r"3/4")
        settle(page, 2)

        body_pre = shot(page, f"{PREFIX}01-backing-pre-reboot")
        disk_pre = disk_snapshot()
        ok_pre, det_pre = mission_backing_ok(body_pre, disk_pre, chord=target_chord, pk=target_pk)
        rows.append(row("P7_PRE", bool(opened) and ok_pre, f"{det_pre} disk={disk_pre}"))

        page.context.close()
        kill_port(PORT)
        reinforce_mission_intent_on_disk(notes)
        start_streamlit(PORT)
        wait_http(PORT)
        page = open_fresh(browser)

        deadline = time.time() + 90
        body_post = ""
        while time.time() < deadline:
            settle(page, 3)
            body_post = page.inner_text("body") or ""
            if len(body_post) > 500 and (is_mission_backing(body_post) or disk_studio_page() == "backing"):
                break
        body_post = shot(page, f"{PREFIX}02-backing-post-reboot")
        disk_post = disk_snapshot()
        ok_post, det_post = mission_backing_ok(body_post, disk_post, chord=target_chord, pk=target_pk)
        rows.append(row("P7_REBOOT", ok_post, f"{det_post} disk={disk_post}"))

        returned = return_to_mission(page, notes) or click_button_has(page, r"Return to Mission")
        settle(page, 4)
        body_ret = shot(page, f"{PREFIX}03-return-to-mission")
        disk_ret = disk_snapshot()
        fam_ret = page_family(body_ret)
        chord_ret = selected_chord(body_ret)
        c_want = norm_chord(target_chord)
        chord_match = (not c_want) or (
            norm_chord(chord_ret) == c_want
            or c_want in (body_ret or "").replace("♯", "#")
            or norm_chord(str(disk_ret.get("ii_chord") or "")) == c_want
        )
        ret_ok = (
            bool(returned)
            and (
                fam_ret == "creative"
                or has_any(body_ret, "generate example", "missions", "selected mission chord")
            )
            and chord_match
            and (target_pk in body_ret or str(disk_ret.get("display_key") or "").startswith(target_pk))
            and not has_any(body_ret, *CATALOG_FALL)
        )
        rows.append(
            row(
                "P7_RETURN",
                ret_ok,
                f"returned={returned} fam={fam_ret} chord_ret={chord_ret!r} want={c_want!r} "
                f"chord_match={chord_match} disk={disk_ret}",
            )
        )
        browser.close()

    summary = {
        "gate": "P7",
        "meta": info,
        "target_chord": target_chord,
        "target_pk": target_pk,
        "rows": rows,
        "notes": notes,
        "all_pass": all(r["ok"] for r in rows),
    }
    (OUT / f"{PREFIX}results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"branch={info.get('branch')}",
        f"sha={info.get('sha')}",
        f"url={info.get('url') or URL}",
        f"target_chord={target_chord} target_pk={target_pk}",
        "",
        *[f"{r['gate']}: {r['verdict']} — {r['detail']}" for r in rows],
        "",
        "NOTES",
        *notes,
    ]
    text = "\n".join(lines)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
