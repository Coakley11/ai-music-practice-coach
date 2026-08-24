"""P6 proof: Custom SBI Backing reboot keeps ownership + play-session knobs.

Seeds:
  Global Active = Shape of You
  LAST_CUSTOM = Trial Song
  Backing = song_improv Custom Trial Song
  PK E / BPM 113 / Blues / Chorus / 3/4

Then:
  1) server reboot — same specialized Backing + same play-session knobs
  2) browser refresh — same again
  3) true leave to Songs then return — temporary knobs reset toward source defaults
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    click_nav,
    disk_state_path,
    disk_studio_page,
    open_fresh,
    page_family,
    reboot_server,
    seed_trial_song_last_custom,
    settle,
    shot,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)

SHAPE_PICK = "Pop\x1fShape of You — Ed Sheeran"
TRIAL_PICK = "custom::trial-song"
TRIAL_REV = "trial-rev-1"


def _stamp_page(st: dict, page: str) -> None:
    st["studio_page"] = page
    for key in (
        "studio_nav_state",
        "music_workspace_state",
        "practice_workspace_state",
        "core",
        "session",
    ):
        node = st.get(key)
        if not isinstance(node, dict):
            node = {}
            st[key] = node
        node["studio_page"] = page
        if key == "studio_nav_state":
            node["page"] = page
            node["last_write_reason"] = "p6_custom_sbi_backing_seed"
        elif key == "music_workspace_state":
            node["page"] = page


def seed_p6_disk() -> dict:
    path = disk_state_path()
    blob = json.loads(path.read_text(encoding="utf-8"))
    st = blob.setdefault("state", {})
    _stamp_page(st, "backing")

    st["active_catalog_pick_key"] = SHAPE_PICK
    st["selected_song"] = {
        "title": "Shape of You — Ed Sheeran",
        "pick_key": SHAPE_PICK,
    }
    st["display_key"] = "E"
    st["concert_key"] = "E"
    st["improv_entry_mode"] = "Song-Based Improvisation"
    st["improv_intelligence_tab"] = "Entry & Jam"
    st["improv_song_source"] = "Custom progression"
    st["sbi_preview_source"] = "Custom progression"
    st["_backing_open_intent"] = "restore_last"
    st["_backing_explicit_handoff_source"] = "song_improv"
    st.pop("_backing_released_specialized_context", None)

    cw = st.get("creative_workspace_state")
    if not isinstance(cw, dict):
        cw = {}
        st["creative_workspace_state"] = cw
    cw.update(
        {
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Entry & Jam",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
        }
    )

    ctx = {
        "source": "song_improv",
        "source_label": "Song-Based Improvisation",
        "song_title": "Trial Song",
        "active_song_id": TRIAL_PICK,
        "bound_pick_key": TRIAL_PICK,
        "custom_revision_id": TRIAL_REV,
        "key": "E",
        "display_key": "E",
        "concert_key": "E",
        "bpm": 113,
        "style": "Blues",
        "groove": "",
        "scope": "Chorus",
        "loops": 3,
        "progression": ["E", "A", "B7"],
        "progression_label": "Trial Song",
        "entry_mode": "Song-Based Improvisation",
        "mode_label": "Song-Based Improvisation",
        "meter": "3/4",
    }
    play_session = {
        "play_session_id": "p6-play-session-seed",
        "launch_id": "p6-launch-seed",
        "source_identity": f"creative:song_improv:{TRIAL_PICK}",
        "expired": False,
        "defaults": {
            "bpm": 100,
            "groove": "Pop",
            "meter": "4/4",
            "scope": "Full song",
            "loops": 2,
        },
        "overrides": {
            "bpm": 113,
            "groove": "Blues",
            "meter": "3/4",
            "scope": "Chorus",
            "loops": 3,
        },
        "current_bpm_lock": 113,
    }

    def _write_transport(target: dict) -> None:
        target["backing_context"] = dict(ctx)
        target["_backing_play_session"] = dict(play_session)
        target["_backing_play_session_expired"] = False
        target["_backing_current_bpm_lock"] = 113
        target["backing_track_bpm"] = 113
        target["backing_groove_style"] = "Blues"
        target["backing_track_scope"] = "Chorus"
        target["backing_track_loops"] = 3
        target["backing_time_signature"] = "3/4"
        target["backing_source"] = "song_improv"
        target["_last_valid_backing_source"] = "song_improv"

    _write_transport(st)
    sess = st.get("session")
    if not isinstance(sess, dict):
        sess = {}
        st["session"] = sess
    _write_transport(sess)

    pk = st.get("practice_key_by_source")
    if not isinstance(pk, dict):
        pk = {}
        st["practice_key_by_source"] = pk
    pk[TRIAL_PICK] = "E"
    pk[SHAPE_PICK] = "C#m"

    try:
        from custom_progression_lab import CPL_ACTIVE_KEY
    except ImportError:
        CPL_ACTIVE_KEY = "cpl_active_progression"
    chord_rows = [{"symbol": "E"}, {"symbol": "A"}, {"symbol": "B7"}]
    cpl = {
        "id": TRIAL_REV,
        "name": "Trial Song",
        "original_key_center": "C",
        # Durable SOURCE defaults (temporary play session overrides are 113/Blues).
        "bpm": 100,
        "progression_style": "Pop",
        "original_sections": {"A": chord_rows, "Chorus": chord_rows},
    }
    st[CPL_ACTIVE_KEY] = cpl
    sess[CPL_ACTIVE_KEY] = dict(cpl)

    bts = st.get("backing_track_state")
    if not isinstance(bts, dict):
        bts = {}
        st["backing_track_state"] = bts
    bts["backing_track_bpm"] = 113
    bts["backing_track_groove_style"] = "Blues"

    # Page-local Backing snapshot must match CURRENT visit — a stale Catalog
    # snapshot would otherwise clobber sealed ctx on restore_page_snapshot.
    snaps = st.get("_studio_page_snapshots")
    if not isinstance(snaps, dict):
        snaps = {}
        st["_studio_page_snapshots"] = snaps
    snaps["backing"] = {
        "backing_context": dict(ctx),
        "backing_track_bpm": 113,
        "backing_groove_style": "Blues",
        "backing_track_scope": "Chorus",
        "backing_track_loops": 3,
        "backing_time_signature": "3/4",
        "creative_session": dict(cw),
    }
    sess_snaps = sess.get("_studio_page_snapshots")
    if not isinstance(sess_snaps, dict):
        sess_snaps = {}
        sess["_studio_page_snapshots"] = sess_snaps
    sess_snaps["backing"] = dict(snaps["backing"])

    # Bump saved_at so same-device restore prefers this disk seed over a stale
    # cloud full_session that still holds reminted CPL defaults (100/Pop).
    from datetime import datetime, timezone

    blob["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    return {
        "studio_page": st.get("studio_page"),
        "ctx_source": ctx["source"],
        "ctx_title": ctx["song_title"],
        "bpm": ctx["bpm"],
        "style": ctx["style"],
        "scope": ctx["scope"],
        "meter": ctx["meter"],
        "display_key": st.get("display_key"),
        "catalog": st.get("active_catalog_pick_key"),
        "play_overrides": play_session["overrides"],
        "saved_at": blob.get("saved_at"),
    }


def body_signals(body: str) -> dict:
    low = (body or "").lower()
    return {
        "family": page_family(body),
        "disk_page": disk_studio_page(),
        "has_trial": "trial song" in low,
        "has_shape": "shape of you" in low,
        "has_sbi": (
            "song-based" in low
            or "song based" in low
            or "custom progression" in low
            or "return to creative" in low
            or "song-based improvisation" in low
        ),
        "has_catalog_label": bool(
            re.search(r"catalog\s+song|backing source:\s*catalog|catalog ·", low)
        ),
        "has_blues": "blues" in low,
        "has_113": "113" in low,
        "has_chorus": "chorus" in low,
        "has_3_4": "3/4" in low or "3⁄4" in low,
        "has_e_key": bool(re.search(r"\be major\b|practice key:\s*e\b|key:\s*e\b", low)),
    }


def disk_play_snapshot() -> dict:
    try:
        blob = json.loads(disk_state_path().read_text(encoding="utf-8"))
        st = blob.get("state") or {}
        sess = st.get("session") if isinstance(st.get("session"), dict) else {}
        ctx = st.get("backing_context")
        if not isinstance(ctx, dict):
            ctx = sess.get("backing_context") if isinstance(sess.get("backing_context"), dict) else {}
        ps = st.get("_backing_play_session")
        if not isinstance(ps, dict):
            ps = (
                sess.get("_backing_play_session")
                if isinstance(sess.get("_backing_play_session"), dict)
                else {}
            )
        ov = ps.get("overrides") if isinstance(ps.get("overrides"), dict) else {}
        return {
            "ctx_source": (ctx or {}).get("source"),
            "ctx_title": (ctx or {}).get("song_title"),
            "ctx_bpm": (ctx or {}).get("bpm"),
            "ctx_style": (ctx or {}).get("style"),
            "ctx_scope": (ctx or {}).get("scope"),
            "ctx_meter": (ctx or {}).get("meter"),
            "ov_bpm": ov.get("bpm"),
            "ov_groove": ov.get("groove"),
            "ov_scope": ov.get("scope"),
            "ov_meter": ov.get("meter"),
            "ps_expired": bool(ps.get("expired")) if isinstance(ps, dict) else None,
        }
    except Exception as exc:
        return {"error": str(exc)}


def main() -> int:
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = open_fresh(browser)
        seed_trial_song_last_custom(page, notes)
        settle(page, 2)
        page.context.close()

        # Kill first so shutdown autosave cannot overwrite the seeded play session.
        from _walk_reboot_persistence_ai_p19 import PORT, kill_port, start_streamlit, wait_http

        kill_port(PORT)
        seeded = seed_p6_disk()
        notes.append(f"seeded={seeded}")
        start_streamlit(PORT)
        wait_http(PORT)
        page = open_fresh(browser)

        deadline = time.time() + 90
        body = ""
        while time.time() < deadline:
            settle(page, 3)
            body = page.inner_text("body") or ""
            if len(body) > 600 and (
                "backing" in body.lower()
                or "trial song" in body.lower()
                or "shape of you" in body.lower()
            ):
                break

        body = shot(page, "p6-custom-sbi-backing-post-reboot")
        sig = body_signals(body)
        disk_reboot = disk_play_snapshot()
        notes.append(f"signals_reboot={sig}")
        notes.append(f"disk_after_reboot={disk_reboot}")

        catalog_fallback = sig["has_shape"] and sig["has_catalog_label"] and not sig["has_trial"]
        ownership_ok = (
            (str(sig["family"]).startswith("backing") or sig["disk_page"] == "backing")
            and sig["has_trial"]
            and not catalog_fallback
        )
        def _style_is_blues(val: object) -> bool:
            return "blues" in str(val or "").strip().lower()

        play_ok = (
            int(disk_reboot.get("ctx_bpm") or 0) == 113
            and _style_is_blues(disk_reboot.get("ctx_style"))
            and str(disk_reboot.get("ctx_source") or "") == "song_improv"
            and int(disk_reboot.get("ov_bpm") or 0) == 113
            and str(disk_reboot.get("ctx_scope") or "") == "Chorus"
        )

        page.reload(wait_until="domcontentloaded", timeout=120_000)
        settle(page, 5)
        body_refresh = shot(page, "p6-custom-sbi-backing-post-refresh")
        sig_refresh = body_signals(body_refresh)
        disk_refresh = disk_play_snapshot()
        notes.append(f"signals_refresh={sig_refresh}")
        notes.append(f"disk_after_refresh={disk_refresh}")
        refresh_ok = (
            sig_refresh["has_trial"]
            and int(disk_refresh.get("ctx_bpm") or 0) == 113
            and _style_is_blues(disk_refresh.get("ctx_style"))
            and str(disk_refresh.get("ctx_source") or "") == "song_improv"
        )

        click_nav(page, "Songs")
        settle(page, 4)
        click_nav(page, "Backing")
        settle(page, 6)
        shot(page, "p6-custom-sbi-backing-post-true-leave")
        disk_leave = disk_play_snapshot()
        notes.append(f"disk_after_true_leave={disk_leave}")
        leave_reset_ok = (
            int(disk_leave.get("ov_bpm") or 0) != 113
            or bool(disk_leave.get("ps_expired"))
            or int(disk_leave.get("ctx_bpm") or 0) == 100
        )

        ok = bool(ownership_ok and play_ok and refresh_ok)
        report = {
            "gate": "P6",
            "ok": ok,
            "ownership_ok": ownership_ok,
            "play_session_ok": play_ok,
            "refresh_ok": refresh_ok,
            "true_leave_reset_ok": leave_reset_ok,
            "seeded": seeded,
            "signals_reboot": sig,
            "knobs_visible": {
                "bpm_113": sig["has_113"],
                "style_blues": sig["has_blues"],
                "key_e": sig["has_e_key"],
                "scope_chorus": sig["has_chorus"],
                "meter_3_4": sig["has_3_4"],
            },
            "disk_after_reboot": disk_reboot,
            "disk_after_refresh": disk_refresh,
            "disk_after_true_leave": disk_leave,
            "notes": notes,
        }
        out = OUT / "p6-custom-sbi-backing-reboot.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        page.context.close()
        browser.close()
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
