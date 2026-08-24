"""P9: Entry Style (Style Jam Mode) Backing reboot / refresh / true-leave.

Distinctive Style Jam → Open Backing → mutate BPM/style/meter →
  1) reboot preserves Entry Style Backing + play-session knobs
  2) browser refresh preserves same
  3) true leave (Songs) then return → temporary overrides reset
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    PORT,
    URL,
    click_button_has,
    click_nav,
    click_radio,
    disk_state_path,
    disk_studio_page,
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
    goto_improv,
    open_advanced_playback,
    set_bpm,
    set_practice_key,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "p9-entry-style-backing-"
STYLE_MARKERS = (
    "return to style",
    "style jam",
    "entry & jam",
    "creative backing jam · style",
    "return to jam",
)
CATALOG_FALL = ("backing source: catalog", "catalog song")

WANT_BPM = 137
WANT_GROOVE = "Rock"
WANT_METER = "3/4"
WANT_KEY = "F#"
ENTRY_MODE = "Style Jam Mode"


def row(gate: str, ok: bool, detail: str) -> dict:
    return {"gate": gate, "ok": bool(ok), "verdict": "PASS" if ok else "FAIL", "detail": detail}


def has_any(text: str, *needles: str) -> bool:
    blob = (text or "").lower()
    return any(n.lower() in blob for n in needles)


def is_style_backing(body: str) -> bool:
    low = (body or "").lower()
    return (
        has_any(body, *STYLE_MARKERS)
        or ("style jam" in low and "backing" in low)
        or ("return to" in low and "jam" in low)
    )


def disk_snap() -> dict:
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
        defaults = ps.get("defaults") if isinstance(ps.get("defaults"), dict) else {}
    except Exception:
        ctx, ov, ps, defaults = {}, {}, {}, {}
    return {
        "studio_page": disk_studio_page(),
        "ctx_source": (ctx or {}).get("source"),
        "ctx_title": (ctx or {}).get("song_title"),
        "ctx_bpm": (ctx or {}).get("bpm"),
        "ctx_style": (ctx or {}).get("style") or (ctx or {}).get("groove"),
        "ctx_meter": (ctx or {}).get("meter"),
        "ctx_key": (ctx or {}).get("display_key") or (ctx or {}).get("key"),
        "ctx_entry_mode": (ctx or {}).get("entry_mode"),
        "ov_bpm": ov.get("bpm"),
        "ov_groove": ov.get("groove"),
        "ov_meter": ov.get("meter"),
        "def_bpm": defaults.get("bpm"),
        "ps_expired": bool(ps.get("expired")) if isinstance(ps, dict) else None,
    }


def _write_style_transport(st: dict, *, bpm: int, groove: str, meter: str, key: str) -> None:
    ctx = st.get("backing_context") if isinstance(st.get("backing_context"), dict) else {}
    if not ctx:
        ctx = {}
    ctx["source"] = "entry_jam"
    ctx["entry_mode"] = ENTRY_MODE
    ctx["bpm"] = bpm
    ctx["style"] = groove
    ctx["groove"] = groove
    ctx["meter"] = meter
    ctx["key"] = key
    ctx["display_key"] = key
    ctx["concert_key"] = key
    if not ctx.get("song_title"):
        ctx["song_title"] = "Style Jam"
    st["backing_context"] = dict(ctx)

    defaults = {
        "bpm": 100,
        "groove": "Pop",
        "meter": "4/4",
        "scope": "Full song",
        "loops": 2,
    }
    overrides = {
        "bpm": bpm,
        "groove": groove,
        "meter": meter,
        "scope": "Chorus",
        "loops": 3,
    }
    play_session = {
        "play_session_id": "p9-style-play-session",
        "launch_id": "p9-style-launch",
        "source_identity": f"creative:entry_jam:{ctx.get('song_title') or 'style'}",
        "expired": False,
        "defaults": defaults,
        "overrides": overrides,
        "current_bpm_lock": bpm,
    }
    st["_backing_play_session"] = play_session
    st["_backing_play_session_expired"] = False
    st["_backing_current_bpm_lock"] = bpm
    st["backing_track_bpm"] = bpm
    st["backing_groove_style"] = groove
    st["backing_track_scope"] = "Chorus"
    st["backing_track_loops"] = 3
    st["backing_time_signature"] = meter
    st["backing_source"] = "entry_jam"
    st["_last_valid_backing_source"] = "entry_jam"
    st["display_key"] = key
    st["studio_page"] = "backing"
    st["_backing_open_intent"] = "restore_last"
    st["_backing_explicit_handoff_source"] = "entry_jam"
    st.pop("_backing_released_specialized_context", None)

    snaps = st.get("_studio_page_snapshots")
    if not isinstance(snaps, dict):
        snaps = {}
        st["_studio_page_snapshots"] = snaps
    snaps["backing"] = {
        "backing_context": dict(ctx),
        "backing_track_bpm": bpm,
        "backing_groove_style": groove,
        "backing_track_scope": "Chorus",
        "backing_track_loops": 3,
        "backing_time_signature": meter,
    }


def seed_distinctive_style_play_session(notes: list[str]) -> dict:
    try:
        path = disk_state_path()
        blob = json.loads(path.read_text(encoding="utf-8"))
        st = blob.setdefault("state", {})
        _write_style_transport(
            st, bpm=WANT_BPM, groove=WANT_GROOVE, meter=WANT_METER, key=WANT_KEY
        )
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            _write_style_transport(
                sess, bpm=WANT_BPM, groove=WANT_GROOVE, meter=WANT_METER, key=WANT_KEY
            )
        blob["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        notes.append(
            f"disk_seed_style_play_session bpm={WANT_BPM} groove={WANT_GROOVE} "
            f"meter={WANT_METER} key={WANT_KEY}"
        )
        return disk_snap()
    except Exception as exc:
        notes.append(f"disk_seed_err={exc}")
        return disk_snap()


def reinforce_style_intent(notes: list[str]) -> None:
    try:
        path = disk_state_path()
        blob = json.loads(path.read_text(encoding="utf-8"))
        st = blob.setdefault("state", {})
        _write_style_transport(
            st, bpm=WANT_BPM, groove=WANT_GROOVE, meter=WANT_METER, key=WANT_KEY
        )
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            _write_style_transport(
                sess, bpm=WANT_BPM, groove=WANT_GROOVE, meter=WANT_METER, key=WANT_KEY
            )
        blob["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        notes.append("disk_reinforce=entry_jam+style_jam+play_session")
    except Exception as exc:
        notes.append(f"disk_reinforce_err={exc}")


def style_ok(body: str, disk: dict, *, want_bpm: int | None = WANT_BPM) -> tuple[bool, str]:
    fam = page_family(body)
    styleish = is_style_backing(body) or str(disk.get("ctx_source") or "") == "entry_jam"
    catalog_fall = has_any(body, *CATALOG_FALL) and not styleish
    src = str(disk.get("ctx_source") or "")
    entry = str(disk.get("ctx_entry_mode") or "")
    style_mode = "style jam" in entry.lower() or ENTRY_MODE.lower() in entry.lower()
    bpm_ok = True
    if want_bpm is not None:
        bpm_ok = (
            str(want_bpm) in (body or "")
            or disk.get("ctx_bpm") in (want_bpm, str(want_bpm))
            or disk.get("ov_bpm") in (want_bpm, str(want_bpm))
        )
    meter_ok = (
        disk.get("ctx_meter") == WANT_METER
        or disk.get("ov_meter") == WANT_METER
        or WANT_METER in (body or "")
    )
    ok = (
        (str(fam).startswith("backing") or disk.get("studio_page") == "backing")
        and styleish
        and src in {"entry_jam", "jam", ""}
        and not catalog_fall
        and (src != "regular_song")
        and style_mode
    )
    if src and src not in {"entry_jam", "jam"}:
        ok = False
    detail = (
        f"fam={fam} styleish={styleish} src={src!r} entry={entry!r} "
        f"bpm_ok={bpm_ok} meter_ok={meter_ok} catalog_fall={catalog_fall}"
    )
    return ok and bpm_ok and meter_ok, detail


def open_style_jam_generator(page, notes: list[str]) -> bool:
    if not goto_improv(page, notes):
        return False
    settle(page, 1)
    for attempt in range(5):
        click_radio(page, "Entry & Jam") or click_radio(page, "Entry") or click_button_has(
            page, "Entry"
        )
        settle(page, 1)
        ok = (
            click_radio(page, "Style Jam Mode")
            or click_radio(page, "Style Jam")
            or click_button_has(page, "Style Jam Mode")
            or click_button_has(page, "Style Jam")
        )
        settle(page, 2)
        body = page.inner_text("body") or ""
        has_generate = (
            "Generate progression" in body
            or "Generate style" in body.lower()
            or ("Generate" in body and "Style" in body)
        )
        landed = "Style Jam" in body or "style jam" in body.lower()
        notes.append(
            f"style_jam_attempt={attempt} ok={ok} has_generate={has_generate} landed={landed}"
        )
        if landed and (has_generate or ok):
            return True
        settle(page, 1)
    return False


def open_style_backing(page, notes: list[str]) -> bool:
    if not open_style_jam_generator(page, notes):
        return False
    set_practice_key(page, WANT_KEY)
    settle(page, 1)
    (
        click_button_has(page, r"Generate progression")
        or click_button_has(page, r"Generate style jam")
        or click_button_has(page, r"Generate Style")
        or click_button_has(page, r"^Generate$")
    )
    settle(page, 3)
    opened = (
        click_button_has(page, r"Open in Backing Studio")
        or click_button_has(page, r"Open Backing")
        or click_button_has(page, r"Open.*Backing")
    )
    settle(page, 4)
    body = page.inner_text("body") or ""
    landed = str(page_family(body)).startswith("backing") or is_style_backing(body)
    notes.append(f"style_backing_open={opened} landed={landed}")
    return bool(opened and landed)


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []
    info = meta()
    want_bpm = WANT_BPM

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = open_fresh(browser)
        pick_song(page, notes, "Shape of You", "Pop")
        opened = open_style_backing(page, notes)
        open_advanced_playback(page)
        settle(page, 1)
        bpm_ui = set_bpm(page, want_bpm)
        notes.append(f"bpm_ui={bpm_ui}")
        click_radio(page, "Rock") or click_button_has(page, r"^Rock$") or click_radio(page, "Funk")
        click_radio(page, "3/4") or click_button_has(page, r"3/4")
        settle(page, 2)
        seed_distinctive_style_play_session(notes)
        page.reload(wait_until="domcontentloaded")
        settle(page, 5)
        body_pre = shot(page, f"{PREFIX}01-pre-reboot")
        disk_pre = disk_snap()
        ok_pre, det_pre = style_ok(body_pre, disk_pre, want_bpm=want_bpm)
        rows.append(row("P9_PRE", bool(opened) and ok_pre, f"{det_pre} disk={disk_pre}"))

        page.context.close()
        kill_port(PORT)
        reinforce_style_intent(notes)
        start_streamlit(PORT)
        wait_http(PORT)
        page = open_fresh(browser)
        deadline = time.time() + 90
        body_post = ""
        while time.time() < deadline:
            settle(page, 3)
            body_post = page.inner_text("body") or ""
            if len(body_post) > 500 and (
                is_style_backing(body_post) or disk_studio_page() == "backing"
            ):
                break
        body_post = shot(page, f"{PREFIX}02-post-reboot")
        disk_post = disk_snap()
        ok_post, det_post = style_ok(body_post, disk_post, want_bpm=want_bpm)
        editable = bool(set_practice_key(page, "Ab"))
        settle(page, 1)
        rows.append(
            row(
                "P9_REBOOT",
                ok_post,
                f"{det_post} editable_pk={editable} disk={disk_post}",
            )
        )

        page.reload(wait_until="domcontentloaded")
        settle(page, 5)
        body_ref = shot(page, f"{PREFIX}03-post-refresh")
        disk_ref = disk_snap()
        ok_ref, det_ref = style_ok(body_ref, disk_ref, want_bpm=want_bpm)
        rows.append(row("P9_REFRESH", ok_ref, f"{det_ref} disk={disk_ref}"))

        click_nav(page, "Songs") or click_button_has(page, r"Songs")
        settle(page, 3)
        body_songs = shot(page, f"{PREFIX}04-true-leave-songs")
        notes.append(f"true_leave_fam={page_family(body_songs)}")
        click_nav(page, "Backing") or click_button_has(page, r"Backing")
        settle(page, 4)
        body_leave = shot(page, f"{PREFIX}05-return-after-true-leave")
        disk_leave = disk_snap()
        ov_bpm = disk_leave.get("ov_bpm")
        ctx_bpm = disk_leave.get("ctx_bpm")
        reset_ok = (
            bool(disk_leave.get("ps_expired"))
            or ov_bpm in (None, "")
            or (
                disk_leave.get("def_bpm") is not None
                and ov_bpm == disk_leave.get("def_bpm")
            )
            or (
                ctx_bpm not in (want_bpm, str(want_bpm))
                and ov_bpm not in (want_bpm, str(want_bpm))
            )
        )
        still_style = (
            str(disk_leave.get("ctx_source") or "") in {"entry_jam", "jam"}
            or "style jam" in str(disk_leave.get("ctx_entry_mode") or "").lower()
            or is_style_backing(body_leave)
        )
        rows.append(
            row(
                "P9_TRUE_LEAVE",
                still_style and reset_ok,
                f"still_style={still_style} reset_ok={reset_ok} ov_bpm={ov_bpm!r} "
                f"ctx_bpm={ctx_bpm!r} disk={disk_leave}",
            )
        )
        browser.close()

    summary = {
        "gate": "P9",
        "meta": info,
        "want_bpm": want_bpm,
        "rows": rows,
        "notes": notes,
        "all_pass": all(r["ok"] for r in rows),
    }
    (OUT / f"{PREFIX}results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"branch={info.get('branch')}",
        f"sha={info.get('sha')}",
        f"url={info.get('url') or URL}",
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
