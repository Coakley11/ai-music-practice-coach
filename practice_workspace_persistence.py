"""Canonical Practice Tools workspace — tool selection, time/pitch modes, settings."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from practice_tools_ui import (
    PRACTICE_ACTIVE_TOOL_KEY,
    PRACTICE_TIME_PITCH_MODE_KEY,
    PRACTICE_TIME_PITCH_TOOL_ID,
    normalize_practice_active_tool,
)

PRACTICE_WORKSPACE_STATE_KEY = "practice_workspace_state"
PRACTICE_WORKSPACE_DIRTY_KEY = "practice_workspace_state_dirty"
PRACTICE_WORKSPACE_RESTORED_KEY = "_practice_workspace_state_restored"
PRACTICE_WORKSPACE_MIGRATED_KEY = "_practice_workspace_legacy_migrated"
PRACTICE_WORKSPACE_LAST_SAVE_REASON_KEY = "_practice_workspace_last_save_reason"
PRACTICE_WORKSPACE_LAST_SKIP_KEY = "_practice_workspace_last_apply_skipped"
PRACTICE_TOOL_SYNC_DIAG_KEY = "_practice_tool_sync_diag"

PRACTICE_METRONOME_BPM_KEY = "practice_metronome_bpm"
PRACTICE_METRONOME_METER_KEY = "practice_metronome_meter"
PRACTICE_METRONOME_SUBDIVISION_KEY = "practice_metronome_subdivision"
PRACTICE_METRONOME_ACCENT_KEY = "practice_metronome_accent_enabled"

PRACTICE_TUNER_REFERENCE_PITCH_KEY = "practice_tuner_reference_pitch"
PRACTICE_TUNER_INSTRUMENT_CONTEXT_KEY = "practice_tuner_instrument_context"
PRACTICE_TUNER_TRANSPOSITION_MODE_KEY = "practice_tuner_transposition_mode"
PRACTICE_TUNER_UI_MODE_KEY = "practice_tuner_ui_mode"

PRACTICE_TONE_PITCH_CLASS_KEY = "practice_tone_pitch_class"
PRACTICE_TONE_OCTAVE_KEY = "practice_tone_octave"
PRACTICE_TONE_REFERENCE_PITCH_KEY = "practice_tone_reference_pitch"

TIME_PITCH_MODE_METRONOME = "metronome"
TIME_PITCH_MODE_TUNER = "tuner"
TIME_PITCH_MODE_TONE = "tone"

SCHEMA_VERSION = 1

_DEFAULT_METRONOME = {
    "bpm": 100,
    "meter": "4/4",
    "subdivision": "quarter",
    "accent_enabled": True,
}
_DEFAULT_TUNER = {
    "reference_pitch": 440,
    "instrument_context": "",
    "transposition_mode": "concert",
    "ui_mode": "live",
}
_DEFAULT_TONE = {
    "pitch_class": "A",
    "octave": 4,
    "reference_pitch": 440,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_merge_missing(target: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(defaults)
    for key, val in (target or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            nested = copy.deepcopy(out[key])
            nested.update(val)
            out[key] = nested
        elif val is not None:
            out[key] = copy.deepcopy(val)
    return out


def default_practice_workspace_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "selected_practice_tool": "",
        "selected_time_pitch_mode": "",
        "metronome": copy.deepcopy(_DEFAULT_METRONOME),
        "tuner": copy.deepcopy(_DEFAULT_TUNER),
        "tone": copy.deepcopy(_DEFAULT_TONE),
        "updated_at": _utc_now_iso(),
    }


def _time_pitch_mode_for_tool(tool_id: str, *, tuner_ui_mode: str = "", explicit_mode: str = "") -> str:
    mode = str(explicit_mode or session_mode_from_session_keys(tuner_ui_mode) or "").strip().lower()
    if tool_id == PRACTICE_TIME_PITCH_TOOL_ID or tool_id in ("timing", "tuner"):
        if mode in (TIME_PITCH_MODE_METRONOME, TIME_PITCH_MODE_TUNER, TIME_PITCH_MODE_TONE):
            return mode
        if "sustain" in mode or mode == "tone":
            return TIME_PITCH_MODE_TONE
        if mode == "live" or mode == "tuner":
            return TIME_PITCH_MODE_TUNER
        if tool_id == "timing":
            return TIME_PITCH_MODE_METRONOME
        return TIME_PITCH_MODE_TUNER
    return ""


def session_mode_from_session_keys(tuner_ui_mode: str = "") -> str:
    ui = str(tuner_ui_mode or "").strip().lower()
    if ui in ("tone", "sustain"):
        return TIME_PITCH_MODE_TONE
    if ui == "live":
        return TIME_PITCH_MODE_TUNER
    return ""


def gather_practice_workspace_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Read live session → canonical practice_workspace_state."""
    base = session.get(PRACTICE_WORKSPACE_STATE_KEY)
    if not isinstance(base, dict):
        base = default_practice_workspace_state()
    else:
        base = _deep_merge_missing(base, default_practice_workspace_state())

    tool = normalize_practice_active_tool(session)
    base["selected_practice_tool"] = tool
    tuner_ui = str(session.get(PRACTICE_TUNER_UI_MODE_KEY) or base.get("tuner", {}).get("ui_mode") or "live")
    explicit_mode = str(session.get(PRACTICE_TIME_PITCH_MODE_KEY) or "").strip()
    if not explicit_mode and tool in (PRACTICE_TIME_PITCH_TOOL_ID, "timing", "tuner"):
        explicit_mode = session_mode_from_session_keys(str(session.get(PRACTICE_TUNER_UI_MODE_KEY) or ""))
    if not explicit_mode:
        explicit_mode = str(base.get("selected_time_pitch_mode") or "").strip()
    base["selected_time_pitch_mode"] = _time_pitch_mode_for_tool(
        tool,
        tuner_ui_mode=tuner_ui,
        explicit_mode=explicit_mode,
    )

    metro = dict(base.get("metronome") or {})
    try:
        metro["bpm"] = int(session.get(PRACTICE_METRONOME_BPM_KEY) or metro.get("bpm") or 100)
    except (TypeError, ValueError):
        metro["bpm"] = 100
    metro["meter"] = str(session.get(PRACTICE_METRONOME_METER_KEY) or metro.get("meter") or "4/4")
    metro["subdivision"] = str(
        session.get(PRACTICE_METRONOME_SUBDIVISION_KEY) or metro.get("subdivision") or "quarter"
    )
    metro["accent_enabled"] = bool(
        session.get(PRACTICE_METRONOME_ACCENT_KEY)
        if PRACTICE_METRONOME_ACCENT_KEY in session
        else metro.get("accent_enabled", True)
    )
    base["metronome"] = metro

    tuner = dict(base.get("tuner") or {})
    try:
        tuner["reference_pitch"] = int(
            session.get(PRACTICE_TUNER_REFERENCE_PITCH_KEY) or tuner.get("reference_pitch") or 440
        )
    except (TypeError, ValueError):
        tuner["reference_pitch"] = 440
    tuner["instrument_context"] = str(
        session.get(PRACTICE_TUNER_INSTRUMENT_CONTEXT_KEY) or tuner.get("instrument_context") or ""
    ).strip()
    tuner["transposition_mode"] = str(
        session.get(PRACTICE_TUNER_TRANSPOSITION_MODE_KEY) or tuner.get("transposition_mode") or "concert"
    ).strip()
    tuner["ui_mode"] = str(session.get(PRACTICE_TUNER_UI_MODE_KEY) or tuner.get("ui_mode") or "live").strip()
    base["tuner"] = tuner

    tone = dict(base.get("tone") or {})
    tone["pitch_class"] = str(
        session.get(PRACTICE_TONE_PITCH_CLASS_KEY) or tone.get("pitch_class") or "A"
    ).strip()
    try:
        tone["octave"] = int(session.get(PRACTICE_TONE_OCTAVE_KEY) or tone.get("octave") or 4)
    except (TypeError, ValueError):
        tone["octave"] = 4
    try:
        tone["reference_pitch"] = int(
            session.get(PRACTICE_TONE_REFERENCE_PITCH_KEY) or tone.get("reference_pitch") or 440
        )
    except (TypeError, ValueError):
        tone["reference_pitch"] = 440
    base["tone"] = tone

    base["updated_at"] = _utc_now_iso()
    return base


def write_canonical_practice_workspace(
    session: dict[str, Any],
    blob: dict[str, Any],
    *,
    reason: str = "autosave",
) -> dict[str, Any]:
    canonical = _deep_merge_missing(blob, default_practice_workspace_state())
    session[PRACTICE_WORKSPACE_STATE_KEY] = copy.deepcopy(canonical)
    session[PRACTICE_WORKSPACE_LAST_SAVE_REASON_KEY] = reason
    session.pop(PRACTICE_WORKSPACE_DIRTY_KEY, None)
    return canonical


def mark_practice_workspace_dirty(session: dict[str, Any], *, reason: str = "user_edit") -> None:
    session[PRACTICE_WORKSPACE_DIRTY_KEY] = True
    session[PRACTICE_WORKSPACE_LAST_SAVE_REASON_KEY] = reason


def is_practice_workspace_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(PRACTICE_WORKSPACE_DIRTY_KEY))


def practice_workspace_restored(session: dict[str, Any]) -> bool:
    return bool(session.get(PRACTICE_WORKSPACE_RESTORED_KEY))


def sync_practice_workspace_before_persist(session: dict[str, Any], *, reason: str = "autosave") -> None:
    gathered = gather_practice_workspace_from_session(session)
    write_canonical_practice_workspace(session, gathered, reason=reason)


def _practice_workspace_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    top = payload.get(PRACTICE_WORKSPACE_STATE_KEY)
    if isinstance(top, dict) and top:
        return copy.deepcopy(top)
    ws = payload.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get("practice_workspace_state"), dict):
        return copy.deepcopy(ws["practice_workspace_state"])
    return None


def _legacy_tool_from_snapshots(session: dict[str, Any], payload: dict[str, Any]) -> str:
    snaps = session.get("_studio_page_snapshots")
    if not isinstance(snaps, dict):
        session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        snaps = session_extra.get("_studio_page_snapshots")
    if isinstance(snaps, dict) and isinstance(snaps.get("practice"), dict):
        raw = str(snaps["practice"].get("practice_active_tool") or "").strip()
        if raw:
            return raw
    flat = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    raw = str(flat.get("practice_active_tool") or session.get("practice_active_tool") or "").strip()
    if raw:
        return raw
    return ""


def migrate_legacy_practice_workspace_once(
    session: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if session.get(PRACTICE_WORKSPACE_MIGRATED_KEY):
        return None
    if _practice_workspace_from_payload(payload):
        session[PRACTICE_WORKSPACE_MIGRATED_KEY] = True
        return None
    tool = _legacy_tool_from_snapshots(session, payload)
    if not tool:
        session[PRACTICE_WORKSPACE_MIGRATED_KEY] = True
        return None
    raw_tool = tool
    tool = normalize_practice_active_tool({PRACTICE_ACTIVE_TOOL_KEY: raw_tool}) or tool
    if raw_tool in ("timing", "tuner") and tool != PRACTICE_TIME_PITCH_TOOL_ID:
        tool = PRACTICE_TIME_PITCH_TOOL_ID
    if raw_tool == "timing":
        mode = TIME_PITCH_MODE_METRONOME
    elif raw_tool == "tuner":
        mode = TIME_PITCH_MODE_TUNER
    else:
        mode = _time_pitch_mode_for_tool(tool)
    blob = default_practice_workspace_state()
    blob["selected_practice_tool"] = tool
    blob["selected_time_pitch_mode"] = mode
    session[PRACTICE_WORKSPACE_MIGRATED_KEY] = True
    session["_practice_workspace_migrated_from"] = "page_snapshot"
    return blob


def apply_practice_workspace_to_session(
    session: dict[str, Any],
    blob: dict[str, Any],
    *,
    source: str = "cloud_restore",
) -> None:
    canonical = _deep_merge_missing(blob, default_practice_workspace_state())
    write_canonical_practice_workspace(session, canonical, reason=source)
    project_practice_workspace_to_session(session, overwrite=True)
    session[PRACTICE_WORKSPACE_RESTORED_KEY] = True
    session.pop(PRACTICE_WORKSPACE_LAST_SKIP_KEY, None)


def apply_practice_workspace_from_payload(
    session: dict[str, Any],
    payload: dict[str, Any],
    *,
    authoritative: bool = False,
) -> bool:
    if is_practice_workspace_locally_dirty(session) and not authoritative:
        session[PRACTICE_WORKSPACE_LAST_SKIP_KEY] = "local_dirty"
        return False
    blob = _practice_workspace_from_payload(payload)
    if not blob:
        migrated = migrate_legacy_practice_workspace_once(session, payload)
        if migrated:
            apply_practice_workspace_to_session(session, migrated, source="legacy_migration")
            return True
        session[PRACTICE_WORKSPACE_LAST_SKIP_KEY] = "missing_in_envelope"
        return False
    apply_practice_workspace_to_session(session, blob, source="cloud_restore" if authoritative else "disk_restore")
    session[PRACTICE_WORKSPACE_MIGRATED_KEY] = True
    record_practice_tool_apply_diag(session, payload)
    return True


def project_practice_workspace_to_session(session: dict[str, Any], *, overwrite: bool = False) -> None:
    """Project canonical blob → session keys used by Practice Tools UI."""
    meta = session.get(PRACTICE_WORKSPACE_STATE_KEY)
    if not isinstance(meta, dict):
        return
    tool = str(meta.get("selected_practice_tool") or "").strip()
    if tool or overwrite:
        if tool:
            session[PRACTICE_ACTIVE_TOOL_KEY] = tool
        elif overwrite and PRACTICE_ACTIVE_TOOL_KEY in session and not tool:
            session[PRACTICE_ACTIVE_TOOL_KEY] = ""
    mode = str(meta.get("selected_time_pitch_mode") or "").strip()
    if mode:
        session[PRACTICE_TIME_PITCH_MODE_KEY] = mode
        if mode == TIME_PITCH_MODE_TONE:
            session[PRACTICE_TUNER_UI_MODE_KEY] = "tone"
        elif mode == TIME_PITCH_MODE_TUNER:
            session[PRACTICE_TUNER_UI_MODE_KEY] = "live"

    metro = meta.get("metronome") if isinstance(meta.get("metronome"), dict) else {}
    if overwrite or PRACTICE_METRONOME_BPM_KEY not in session:
        session[PRACTICE_METRONOME_BPM_KEY] = int(metro.get("bpm") or 100)
    if overwrite or PRACTICE_METRONOME_METER_KEY not in session:
        session[PRACTICE_METRONOME_METER_KEY] = str(metro.get("meter") or "4/4")
    if overwrite or PRACTICE_METRONOME_SUBDIVISION_KEY not in session:
        session[PRACTICE_METRONOME_SUBDIVISION_KEY] = str(metro.get("subdivision") or "quarter")
    if overwrite or PRACTICE_METRONOME_ACCENT_KEY not in session:
        session[PRACTICE_METRONOME_ACCENT_KEY] = bool(metro.get("accent_enabled", True))

    tuner = meta.get("tuner") if isinstance(meta.get("tuner"), dict) else {}
    if overwrite or PRACTICE_TUNER_REFERENCE_PITCH_KEY not in session:
        session[PRACTICE_TUNER_REFERENCE_PITCH_KEY] = int(tuner.get("reference_pitch") or 440)
    if overwrite or PRACTICE_TUNER_INSTRUMENT_CONTEXT_KEY not in session:
        session[PRACTICE_TUNER_INSTRUMENT_CONTEXT_KEY] = str(tuner.get("instrument_context") or "")
    if overwrite or PRACTICE_TUNER_TRANSPOSITION_MODE_KEY not in session:
        session[PRACTICE_TUNER_TRANSPOSITION_MODE_KEY] = str(tuner.get("transposition_mode") or "concert")
    if overwrite or PRACTICE_TUNER_UI_MODE_KEY not in session:
        session[PRACTICE_TUNER_UI_MODE_KEY] = str(tuner.get("ui_mode") or "live")

    tone = meta.get("tone") if isinstance(meta.get("tone"), dict) else {}
    if overwrite or PRACTICE_TONE_PITCH_CLASS_KEY not in session:
        session[PRACTICE_TONE_PITCH_CLASS_KEY] = str(tone.get("pitch_class") or "A")
    if overwrite or PRACTICE_TONE_OCTAVE_KEY not in session:
        session[PRACTICE_TONE_OCTAVE_KEY] = int(tone.get("octave") or 4)
    if overwrite or PRACTICE_TONE_REFERENCE_PITCH_KEY not in session:
        session[PRACTICE_TONE_REFERENCE_PITCH_KEY] = int(tone.get("reference_pitch") or 440)


def prepare_practice_workspace_for_render(session: dict[str, Any]) -> None:
    """Before page widgets: project canonical → session without clobbering restored values."""
    if isinstance(session.get(PRACTICE_WORKSPACE_STATE_KEY), dict):
        project_practice_workspace_to_session(session, overwrite=practice_workspace_restored(session))
        return
    if practice_workspace_restored(session):
        return
    sync_practice_workspace_before_persist(session, reason="prepare_render_seed")


def commit_practice_tool_selection(session: dict[str, Any], tool_id: str) -> None:
    """User picked a tool — update canonical first."""
    session[PRACTICE_ACTIVE_TOOL_KEY] = str(tool_id or "").strip()
    mark_practice_workspace_dirty(session, reason="tool_select")
    sync_practice_workspace_before_persist(session, reason="tool_select")


def commit_practice_time_pitch_settings(session: dict[str, Any], *, reason: str = "tool_settings") -> None:
    mark_practice_workspace_dirty(session, reason=reason)
    sync_practice_workspace_before_persist(session, reason=reason)


def practice_workspace_for_envelope(session: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(gather_practice_workspace_from_session(session))


def metronome_render_defaults(session: dict[str, Any], *, fallback_bpm: int, fallback_meter: str) -> tuple[int, str]:
    prepare_practice_workspace_for_render(session)
    try:
        bpm = int(session.get(PRACTICE_METRONOME_BPM_KEY) or fallback_bpm)
    except (TypeError, ValueError):
        bpm = int(fallback_bpm)
    meter = str(session.get(PRACTICE_METRONOME_METER_KEY) or fallback_meter or "4/4")
    return bpm, meter


def _cloud_practice_workspace_blob(cloud_state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(cloud_state, dict):
        return {}
    top = cloud_state.get(PRACTICE_WORKSPACE_STATE_KEY)
    if isinstance(top, dict):
        return top
    ws = cloud_state.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get("practice_workspace_state"), dict):
        return ws["practice_workspace_state"]
    return {}


def music_practice_workspace_cloud_drift(
    st: Any,
    cloud_state: dict[str, Any],
    cloud_ts: str | None,
) -> tuple[bool, str]:
    _ = cloud_ts
    ss = getattr(st, "session_state", st)
    if not isinstance(ss, dict):
        return False, ""
    cloud_pw = _cloud_practice_workspace_blob(cloud_state)
    if not cloud_pw:
        return False, ""
    if is_practice_workspace_locally_dirty(ss):
        return False, ""
    live = ss.get(PRACTICE_WORKSPACE_STATE_KEY)
    if not isinstance(live, dict):
        return True, "practice_workspace_missing_local"
    for key in ("selected_practice_tool", "selected_time_pitch_mode", "updated_at"):
        if cloud_pw.get(key) != live.get(key):
            return True, f"practice_workspace:{key}"
    return False, ""


def _record_practice_tool_sync_diag(session: dict[str, Any], **fields: Any) -> None:
    diag = session.get(PRACTICE_TOOL_SYNC_DIAG_KEY)
    if not isinstance(diag, dict):
        diag = {}
    diag.update({k: v for k, v in fields.items() if v is not None})
    session[PRACTICE_TOOL_SYNC_DIAG_KEY] = diag


def persist_practice_tool_user_action(
    st: Any,
    tool_id: str,
    *,
    time_pitch_mode: str = "",
) -> bool:
    """User selected a Practice Tool — update canonical state and force cloud save."""
    ss = st.session_state
    _record_practice_tool_sync_diag(
        ss,
        practice_tool_user_action_received=True,
        canonical_practice_tool_after_click=str(tool_id or ""),
    )
    commit_practice_tool_selection(ss, tool_id)
    if time_pitch_mode:
        ss[PRACTICE_TIME_PITCH_MODE_KEY] = time_pitch_mode
        if time_pitch_mode == TIME_PITCH_MODE_TONE:
            ss[PRACTICE_TUNER_UI_MODE_KEY] = "tone"
        elif time_pitch_mode == TIME_PITCH_MODE_TUNER:
            ss[PRACTICE_TUNER_UI_MODE_KEY] = "live"
        sync_practice_workspace_before_persist(ss, reason="time_pitch_mode")
    _record_practice_tool_sync_diag(
        ss,
        practice_workspace_dirty=bool(ss.get(PRACTICE_WORKSPACE_DIRTY_KEY)),
        canonical_practice_tool_after_click=normalize_practice_active_tool(ss),
    )
    try:
        from workspace_revision import workspace_revision_from_blob

        rev_before = workspace_revision_from_blob(
            {PRACTICE_WORKSPACE_STATE_KEY: ss.get(PRACTICE_WORKSPACE_STATE_KEY)}
        )
        local_rev = int(ss.get("_suite_workspace_revision") or rev_before or 0)
        _record_practice_tool_sync_diag(ss, cloud_revision_before_save=local_rev)
    except ImportError:
        local_rev = 0
    _record_practice_tool_sync_diag(ss, autosave_requested=True)
    ok = False
    save_skipped = ""
    try:
        from music_persistent_state import APP_ID, build_music_disk_state, force_autosave

        ok = bool(
            force_autosave(
                st,
                APP_ID,
                build_state=build_music_disk_state,
                reason="practice_tool_select",
            )
        )
        if not ok:
            save_skipped = str(
                ss.get("_suite_autosave_block_reason")
                or ss.get("_suite_autosave_cloud_blocked_reason")
                or "force_autosave_returned_false"
            )
    except Exception as exc:
        save_skipped = str(exc)
    _record_practice_tool_sync_diag(
        ss,
        autosave_completed=ok,
        save_skipped_reason=save_skipped or None,
        cloud_revision_after_save=int(ss.get("_suite_workspace_revision") or 0),
    )
    if ok:
        try:
            from suite_cloud_state import load_cloud_full_session
            from music_persistent_state import APP_ID

            cloud_state, _ts = load_cloud_full_session(APP_ID)
            cloud_pw = _cloud_practice_workspace_blob(cloud_state if isinstance(cloud_state, dict) else {})
            _record_practice_tool_sync_diag(
                ss,
                cloud_saved_practice_tool=str(cloud_pw.get("selected_practice_tool") or ""),
            )
        except Exception:
            pass
        ss.pop(PRACTICE_WORKSPACE_DIRTY_KEY, None)
    ss["_practice_tool_overwrite_stage"] = None
    _record_practice_tool_sync_diag(
        ss,
        final_rendered_practice_tool=normalize_practice_active_tool(ss),
    )
    return ok


def record_practice_tool_apply_diag(session: dict[str, Any], payload: dict[str, Any]) -> None:
    cloud_pw = _cloud_practice_workspace_blob(payload)
    try:
        from workspace_revision import workspace_revision_from_blob

        device_rev = workspace_revision_from_blob(payload)
    except ImportError:
        device_rev = 0
    _record_practice_tool_sync_diag(
        session,
        device_loaded_revision=device_rev,
        device_applied_practice_tool=str(cloud_pw.get("selected_practice_tool") or ""),
        apply_skipped_reason=session.get(PRACTICE_WORKSPACE_LAST_SKIP_KEY),
        final_rendered_practice_tool=normalize_practice_active_tool(session),
    )


def collect_practice_workspace_audit(session: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    saved_blob = _practice_workspace_from_payload(payload or {}) if payload else None
    if saved_blob is None and isinstance(session.get("_suite_last_cloud_fetch_payload"), dict):
        saved_blob = _practice_workspace_from_payload(session["_suite_last_cloud_fetch_payload"])
    applied = session.get(PRACTICE_WORKSPACE_STATE_KEY) if isinstance(session.get(PRACTICE_WORKSPACE_STATE_KEY), dict) else {}
    final_tool = normalize_practice_active_tool(session)
    saved_tool = str((saved_blob or {}).get("selected_practice_tool") or "").strip()
    applied_tool = str((applied or {}).get("selected_practice_tool") or "").strip()

    saved_mode = str((saved_blob or {}).get("selected_time_pitch_mode") or "").strip()
    applied_mode = str((applied or {}).get("selected_time_pitch_mode") or "").strip()
    final_mode = _time_pitch_mode_for_tool(
        final_tool,
        tuner_ui_mode=str(session.get(PRACTICE_TUNER_UI_MODE_KEY) or ""),
    )

    def _match_block(name: str) -> bool:
        if not saved_blob:
            return True
        sb = saved_blob.get(name) if isinstance(saved_blob.get(name), dict) else {}
        ab = applied.get(name) if isinstance(applied.get(name), dict) else {}
        live = gather_practice_workspace_from_session(session).get(name) or {}
        return sb == ab == live if sb else True

    return {
        "practice_state_present_in_saved_envelope": bool(saved_blob),
        "practice_tool_saved": saved_tool or "(none)",
        "practice_tool_applied": applied_tool or "(none)",
        "practice_tool_final": final_tool or "(none)",
        "time_pitch_mode_saved": saved_mode or "(none)",
        "time_pitch_mode_applied": applied_mode or "(none)",
        "time_pitch_mode_final": final_mode or "(none)",
        "metronome_settings_match": _match_block("metronome"),
        "tuner_settings_match": _match_block("tuner"),
        "tone_settings_match": _match_block("tone"),
        "practice_tool_overwrite_stage": session.get("_practice_workspace_overwrite_stage")
        or session.get(PRACTICE_WORKSPACE_LAST_SKIP_KEY),
        "practice_state_last_save_reason": session.get(PRACTICE_WORKSPACE_LAST_SAVE_REASON_KEY),
        "practice_state_last_save_skipped_reason": session.get(PRACTICE_WORKSPACE_LAST_SKIP_KEY),
        **(session.get(PRACTICE_TOOL_SYNC_DIAG_KEY) or {}),
    }


__all__ = [
    "PRACTICE_WORKSPACE_STATE_KEY",
    "apply_practice_workspace_from_payload",
    "commit_practice_tool_selection",
    "commit_practice_time_pitch_settings",
    "gather_practice_workspace_from_session",
    "metronome_render_defaults",
    "prepare_practice_workspace_for_render",
    "practice_workspace_for_envelope",
    "practice_workspace_restored",
    "project_practice_workspace_to_session",
    "sync_practice_workspace_before_persist",
    "persist_practice_tool_user_action",
    "music_practice_workspace_cloud_drift",
    "record_practice_tool_apply_diag",
    "collect_practice_workspace_audit",
]
