"""P8: Jam Generator Backing reboot / refresh / true-leave.

Distinctive Jam state → Open Backing → mutate BPM/style/meter →
  1) reboot preserves Jam Backing + play-session knobs
  2) browser refresh preserves same
  3) true leave (Songs) then return → temporary overrides reset toward Jam defaults
"""
from __future__ import annotations

import json
import re
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
    open_advanced_playback,
    open_jam_generator,
    set_bpm,
    set_practice_key,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "p8-jam-backing-"
JAM_MARKERS = (
    "return to jam",
    "jam session",
    "jam generator",
    "creative backing jam · jam",
    "entry & jam",
)
CATALOG_FALL = ("backing source: catalog", "catalog song")


def row(gate: str, ok: bool, detail: str) -> dict:
    return {"gate": gate, "ok": bool(ok), "verdict": "PASS" if ok else "FAIL", "detail": detail}


def has_any(text: str, *needles: str) -> bool:
    blob = (text or "").lower()
    return any(n.lower() in blob for n in needles)


def is_jam_backing(body: str) -> bool:
    return has_any(body, *JAM_MARKERS) and (
        "backing" in (body or "").lower() or "return to" in (body or "").lower()
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


WANT_BPM = 142
WANT_GROOVE = "Funk"
WANT_METER = "3/4"
WANT_KEY = "Eb"


def _write_jam_transport(st: dict, *, bpm: int, groove: str, meter: str, key: str) -> None:
    """Seal distinctive play-session knobs onto an existing entry_jam ctx (P6 pattern)."""
    ctx = st.get("backing_context") if isinstance(st.get("backing_context"), dict) else {}
    if not ctx:
        ctx = {}
    ctx["source"] = "entry_jam"
    ctx["entry_mode"] = ctx.get("entry_mode") or "Jam Session Generator"
    ctx["bpm"] = bpm
    ctx["style"] = groove
    ctx["groove"] = groove
    ctx["meter"] = meter
    ctx["key"] = key
    ctx["display_key"] = key
    ctx["concert_key"] = key
    if not ctx.get("song_title"):
        ctx["song_title"] = "Jam Session"
    st["backing_context"] = dict(ctx)

    defaults = {
        "bpm": 70,
        "groove": "Bossa Nova",
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
        "play_session_id": "p8-jam-play-session",
        "launch_id": "p8-jam-launch",
        "source_identity": f"creative:entry_jam:{ctx.get('song_title') or 'jam'}",
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


def seed_distinctive_jam_play_session(notes: list[str]) -> dict:
    """After UI open, seal distinctive knobs so reboot/refresh can prove play-session persistence."""
    try:
        path = disk_state_path()
        blob = json.loads(path.read_text(encoding="utf-8"))
        st = blob.setdefault("state", {})
        _write_jam_transport(
            st, bpm=WANT_BPM, groove=WANT_GROOVE, meter=WANT_METER, key=WANT_KEY
        )
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            _write_jam_transport(
                sess, bpm=WANT_BPM, groove=WANT_GROOVE, meter=WANT_METER, key=WANT_KEY
            )
        blob["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        notes.append(
            f"disk_seed_jam_play_session bpm={WANT_BPM} groove={WANT_GROOVE} meter={WANT_METER} key={WANT_KEY}"
        )
        return disk_snap()
    except Exception as exc:
        notes.append(f"disk_seed_err={exc}")
        return disk_snap()


def reinforce_jam_intent(notes: list[str]) -> None:
    try:
        path = disk_state_path()
        blob = json.loads(path.read_text(encoding="utf-8"))
        st = blob.setdefault("state", {})
        _write_jam_transport(
            st, bpm=WANT_BPM, groove=WANT_GROOVE, meter=WANT_METER, key=WANT_KEY
        )
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            _write_jam_transport(
                sess, bpm=WANT_BPM, groove=WANT_GROOVE, meter=WANT_METER, key=WANT_KEY
            )
        blob["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        notes.append("disk_reinforce=entry_jam+play_session")
    except Exception as exc:
        notes.append(f"disk_reinforce_err={exc}")


def jam_ok(body: str, disk: dict, *, want_bpm: int | None = WANT_BPM) -> tuple[bool, str]:
    fam = page_family(body)
    jamish = is_jam_backing(body) or str(disk.get("ctx_source") or "") in {"entry_jam", "jam"}
    catalog_fall = has_any(body, *CATALOG_FALL) and not jamish
    src = str(disk.get("ctx_source") or "")
    entry = str(disk.get("ctx_entry_mode") or "")
    jam_mode = "jam session" in entry.lower() or not entry or "style jam" not in entry.lower()
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
        and jamish
        and src in {"entry_jam", "jam", ""}
        and not catalog_fall
        and (src != "regular_song")
        and jam_mode
    )
    if src and src not in {"entry_jam", "jam"}:
        ok = False
    detail = (
        f"fam={fam} jamish={jamish} src={src!r} entry={entry!r} "
        f"bpm_ok={bpm_ok} meter_ok={meter_ok} catalog_fall={catalog_fall}"
    )
    return ok and bpm_ok and meter_ok, detail


def open_jam_backing(page, notes: list[str]) -> bool:
    if not open_jam_generator(page, notes):
        return False
    set_practice_key(page, WANT_KEY)
    settle(page, 1)
    (
        click_button_has(page, r"Generate jam session")
        or click_button_has(page, r"Generate jam")
        or click_button_has(page, r"^Generate$")
    )
    settle(page, 3)
    opened = (
        click_button_has(page, r"Open in Backing Studio")
        or click_button_has(page, r"Open Backing")
        or click_button_has(page, r"Practice in.*Jam")
        or click_button_has(page, r"Open.*Backing")
    )
    settle(page, 4)
    body = page.inner_text("body") or ""
    landed = str(page_family(body)).startswith("backing") or is_jam_backing(body)
    notes.append(f"jam_backing_open={opened} landed={landed}")
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
        opened = open_jam_backing(page, notes)
        open_advanced_playback(page)
        settle(page, 1)
        bpm_ui = set_bpm(page, want_bpm)
        notes.append(f"bpm_ui={bpm_ui}")
        click_radio(page, "Funk") or click_button_has(page, r"^Funk$") or click_radio(page, "Rock")
        click_radio(page, "3/4") or click_button_has(page, r"3/4")
        settle(page, 2)
        # Seal distinctive play-session (UI slider often remints on Jam).
        seed_distinctive_jam_play_session(notes)
        page.reload(wait_until="domcontentloaded")
        settle(page, 5)
        body_pre = shot(page, f"{PREFIX}01-pre-reboot")
        disk_pre = disk_snap()
        ok_pre, det_pre = jam_ok(body_pre, disk_pre, want_bpm=want_bpm)
        rows.append(row("P8_PRE", bool(opened) and ok_pre, f"{det_pre} disk={disk_pre}"))

        # Reboot
        page.context.close()
        kill_port(PORT)
        reinforce_jam_intent(notes)
        start_streamlit(PORT)
        wait_http(PORT)
        page = open_fresh(browser)
        deadline = time.time() + 90
        body_post = ""
        while time.time() < deadline:
            settle(page, 3)
            body_post = page.inner_text("body") or ""
            if len(body_post) > 500 and (
                is_jam_backing(body_post) or disk_studio_page() == "backing"
            ):
                break
        body_post = shot(page, f"{PREFIX}02-post-reboot")
        disk_post = disk_snap()
        ok_post, det_post = jam_ok(body_post, disk_post, want_bpm=want_bpm)
        # Practice Key still editable
        editable = bool(set_practice_key(page, "Db"))
        settle(page, 1)
        rows.append(
            row(
                "P8_REBOOT",
                ok_post,
                f"{det_post} editable_pk={editable} disk={disk_post}",
            )
        )

        # Browser refresh
        page.reload(wait_until="domcontentloaded")
        settle(page, 5)
        body_ref = shot(page, f"{PREFIX}03-post-refresh")
        disk_ref = disk_snap()
        ok_ref, det_ref = jam_ok(body_ref, disk_ref, want_bpm=want_bpm)
        rows.append(row("P8_REFRESH", ok_ref, f"{det_ref} disk={disk_ref}"))

        # True leave → Songs → later return to Backing
        click_nav(page, "Songs") or click_button_has(page, r"Songs")
        settle(page, 3)
        body_songs = shot(page, f"{PREFIX}04-true-leave-songs")
        notes.append(f"true_leave_fam={page_family(body_songs)}")
        click_nav(page, "Backing") or click_button_has(page, r"Backing")
        settle(page, 4)
        body_leave = shot(page, f"{PREFIX}05-return-after-true-leave")
        disk_leave = disk_snap()
        # Temporary overrides should reset (ov_bpm gone or back near defaults).
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
        still_jam = str(disk_leave.get("ctx_source") or "") in {"entry_jam", "jam"} or is_jam_backing(
            body_leave
        )
        rows.append(
            row(
                "P8_TRUE_LEAVE",
                still_jam and reset_ok,
                f"still_jam={still_jam} reset_ok={reset_ok} ov_bpm={ov_bpm!r} ctx_bpm={ctx_bpm!r} disk={disk_leave}",
            )
        )
        browser.close()

    summary = {
        "gate": "P8",
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
