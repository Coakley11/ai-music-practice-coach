"""Canonical Backing Track page filters — scope, tempo, groove, meter, volume."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

BACKING_STATE_KEY = "backing_track_state"
BACKING_DIRTY_KEY = "backing_track_state_dirty"
BACKING_LOCAL_EDIT_TS_KEY = "backing_track_state_last_local_edit_ts"
BACKING_PENDING_SYNC_KEY = "_backing_filters_pending_sync"
BACKING_RESTORED_KEY = "_backing_track_state_cloud_restored"

BACKING_SCOPE_CHOICES = (
    "Full song",
    "Single section",
    "Multiple selected sections",
)

BACKING_LOOPS_MIN = 1
BACKING_LOOPS_MAX = 10
BACKING_LOOPS_DEFAULT = 2
BACKING_VOLUME_DEFAULT = 0.75

BACKING_SCALAR_KEYS = (
    "backing_track_scope",
    "backing_track_single_section",
    "backing_track_multi_sections",
    "backing_track_loops",
    "backing_track_bpm",
    "backing_groove_style",
    "backing_volume",
    "backing_time_signature",
    "backing_time_signature_override",
    "backing_quick_section",
)

_DURABLE_FILTER_KEYS = (
    "backing_track_scope",
    "backing_track_single_section",
    "backing_track_multi_sections",
    "backing_track_loops",
    "backing_track_bpm",
    "backing_groove_style",
    "backing_volume",
    "backing_time_signature",
    "backing_time_signature_override",
    "backing_quick_section",
)

__all__ = (
    "BACKING_DIRTY_KEY",
    "BACKING_LOOPS_DEFAULT",
    "BACKING_PENDING_SYNC_KEY",
    "BACKING_RESTORED_KEY",
    "BACKING_SCALAR_KEYS",
    "BACKING_SCOPE_CHOICES",
    "BACKING_STATE_KEY",
    "BACKING_VOLUME_DEFAULT",
    "apply_backing_source_state_from_ami",
    "apply_cloud_backing_state_if_allowed",
    "canonical_backing_filters",
    "clear_backing_local_edit",
    "collect_backing_persistence_trace",
    "commit_backing_state_from_session",
    "coerce_backing_groove_for_widget",
    "flush_backing_edits",
    "gather_backing_filters",
    "is_backing_locally_dirty",
    "mark_backing_local_edit",
    "mark_backing_pending_sync",
    "normalize_backing_groove",
    "normalize_backing_scope",
    "prepare_backing_bpm_for_widget",
    "prepare_backing_page",
    "render_backing_state_debug",
    "write_canonical_backing_state",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_backing_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(BACKING_DIRTY_KEY))


def mark_backing_local_edit(session: dict[str, Any]) -> None:
    session[BACKING_DIRTY_KEY] = True
    session[BACKING_LOCAL_EDIT_TS_KEY] = _utc_now_iso()


def clear_backing_local_edit(session: dict[str, Any]) -> None:
    session.pop(BACKING_DIRTY_KEY, None)
    session.pop(BACKING_LOCAL_EDIT_TS_KEY, None)
    session.pop(BACKING_PENDING_SYNC_KEY, None)


def mark_backing_pending_sync(session: dict[str, Any]) -> None:
    session[BACKING_PENDING_SYNC_KEY] = True


def normalize_backing_scope(scope: Any) -> str:
    raw = str(scope or "").strip()
    if raw in BACKING_SCOPE_CHOICES:
        return raw
    low = raw.lower()
    if "multiple" in low:
        return "Multiple selected sections"
    if "single" in low:
        return "Single section"
    return "Full song"


def normalize_backing_groove(groove: Any) -> str:
    raw = str(groove or "").strip()
    if not raw:
        return ""
    try:
        from songs.playback_defaults import normalize_groove_label

        return normalize_groove_label(raw)
    except ImportError:
        return raw


def normalize_backing_bpm(val: Any, *, default: int | None = None) -> int | None:
    if val is None or val == "":
        return default
    try:
        from songs.bpm_state import normalize_backing_bpm as _clamp

        return _clamp(val)
    except ImportError:
        try:
            return int(val)
        except (TypeError, ValueError):
            return default


def normalize_backing_loops(val: Any, *, default: int = BACKING_LOOPS_DEFAULT) -> int:
    try:
        n = int(val)
    except (TypeError, ValueError):
        return default
    return max(BACKING_LOOPS_MIN, min(BACKING_LOOPS_MAX, n))


def normalize_backing_volume(val: Any, *, default: float = BACKING_VOLUME_DEFAULT) -> float:
    try:
        n = float(val)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.5, round(n, 2)))


def normalize_backing_meter(val: Any, *, default: str = "4/4") -> str:
    try:
        from songs.meter import normalize_time_signature

        return normalize_time_signature(str(val or default))
    except ImportError:
        return str(val or default).strip() or default


def _normalize_multi_sections(val: Any) -> list[str]:
    if not isinstance(val, list):
        return []
    return [str(x).strip() for x in val if str(x).strip()]


def _normalize_filters(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    override_raw = src.get("backing_time_signature_override")
    return {
        "backing_track_scope": normalize_backing_scope(src.get("backing_track_scope")),
        "backing_track_single_section": str(src.get("backing_track_single_section") or "").strip(),
        "backing_track_multi_sections": _normalize_multi_sections(src.get("backing_track_multi_sections")),
        "backing_track_loops": normalize_backing_loops(src.get("backing_track_loops")),
        "backing_track_bpm": normalize_backing_bpm(src.get("backing_track_bpm")),
        "backing_groove_style": normalize_backing_groove(src.get("backing_groove_style")),
        "backing_volume": normalize_backing_volume(src.get("backing_volume")),
        "backing_time_signature": normalize_backing_meter(src.get("backing_time_signature")),
        "backing_time_signature_override": bool(override_raw),
        "backing_quick_section": str(src.get("backing_quick_section") or "").strip(),
    }


def _filters_have_content(filters: dict[str, Any]) -> bool:
    if normalize_backing_scope(filters.get("backing_track_scope")) != "Full song":
        return True
    if str(filters.get("backing_track_single_section") or "").strip():
        return True
    if filters.get("backing_track_multi_sections"):
        return True
    if normalize_backing_loops(filters.get("backing_track_loops"), default=0) != BACKING_LOOPS_DEFAULT:
        return True
    if filters.get("backing_track_bpm") is not None:
        return True
    if str(filters.get("backing_groove_style") or "").strip():
        return True
    vol = filters.get("backing_volume")
    if vol is not None and float(vol) != BACKING_VOLUME_DEFAULT:
        return True
    if str(filters.get("backing_time_signature") or "").strip() not in ("", "4/4"):
        return True
    if filters.get("backing_time_signature_override"):
        return True
    if str(filters.get("backing_quick_section") or "").strip() not in ("", "Full song"):
        return True
    return False


def gather_backing_filters(session: dict[str, Any]) -> dict[str, Any]:
    """Read Backing page filters from live session keys."""
    bpm = session.get("backing_track_bpm")
    if bpm is None and "backing_track_bpm" not in session:
        bpm_val = None
    else:
        bpm_val = normalize_backing_bpm(bpm)
    volume = session.get("backing_volume")
    if volume is None and "backing_volume" not in session:
        volume_val = None
    else:
        volume_val = normalize_backing_volume(volume)
    return _normalize_filters(
        {
            "backing_track_scope": session.get("backing_track_scope"),
            "backing_track_single_section": session.get("backing_track_single_section"),
            "backing_track_multi_sections": session.get("backing_track_multi_sections"),
            "backing_track_loops": session.get("backing_track_loops"),
            "backing_track_bpm": bpm_val,
            "backing_groove_style": session.get("backing_groove_style"),
            "backing_volume": volume_val,
            "backing_time_signature": session.get("backing_time_signature"),
            "backing_time_signature_override": session.get("backing_time_signature_override"),
            "backing_quick_section": session.get("backing_quick_section"),
        }
    )


def canonical_backing_filters(session: dict[str, Any]) -> dict[str, Any] | None:
    meta = session.get(BACKING_STATE_KEY)
    if not isinstance(meta, dict):
        return None
    filters = _normalize_filters(meta)
    if not _filters_have_content(filters):
        return None
    return filters


def _preserve_durable_filters_for_autosave(
    session: dict[str, Any],
    filters: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    if reason != "autosave":
        return filters
    if is_backing_locally_dirty(session) or session.get(BACKING_PENDING_SYNC_KEY):
        return filters
    existing = canonical_backing_filters(session) or {}
    merged = dict(filters)
    for key in _DURABLE_FILTER_KEYS:
        existing_val = existing.get(key)
        if existing_val in (None, "", [], False):
            continue
        gathered_val = merged.get(key)
        if gathered_val != existing_val:
            merged[key] = copy.deepcopy(existing_val) if key == "backing_track_multi_sections" else existing_val
    return merged


def _apply_filters_to_session_keys(session: dict[str, Any], filters: dict[str, Any]) -> None:
    session["backing_track_scope"] = normalize_backing_scope(filters.get("backing_track_scope"))
    section = str(filters.get("backing_track_single_section") or "").strip()
    if section:
        session["backing_track_single_section"] = section
    multi = _normalize_multi_sections(filters.get("backing_track_multi_sections"))
    if multi:
        session["backing_track_multi_sections"] = multi
    session["backing_track_loops"] = normalize_backing_loops(filters.get("backing_track_loops"))
    bpm = filters.get("backing_track_bpm")
    if bpm is not None:
        session["backing_track_bpm"] = int(bpm)
    groove = normalize_backing_groove(filters.get("backing_groove_style"))
    if groove:
        session["backing_groove_style"] = groove
    volume = filters.get("backing_volume")
    if volume is not None:
        session["backing_volume"] = float(volume)
    meter = normalize_backing_meter(filters.get("backing_time_signature"))
    if meter:
        session["backing_time_signature"] = meter
    session["backing_time_signature_override"] = bool(filters.get("backing_time_signature_override"))
    quick = str(filters.get("backing_quick_section") or "").strip()
    if quick:
        session["backing_quick_section"] = quick


def coerce_backing_groove_for_widget(session: dict[str, Any], *, default_groove: str = "") -> str:
    if not is_backing_locally_dirty(session):
        canonical = canonical_backing_filters(session) or {}
        canon_groove = normalize_backing_groove(canonical.get("backing_groove_style"))
        if canon_groove:
            session["backing_groove_style"] = canon_groove
            return canon_groove
    current = session.get("backing_groove_style")
    if current is not None and str(current).strip():
        normalized = normalize_backing_groove(current)
        session["backing_groove_style"] = normalized
        return normalized
    fallback = normalize_backing_groove(default_groove) or "Auto"
    session.setdefault("backing_groove_style", fallback)
    return str(session["backing_groove_style"])


def prepare_backing_bpm_for_widget(session: dict[str, Any], *, default_bpm: int = 100) -> int:
    if not is_backing_locally_dirty(session):
        canonical = canonical_backing_filters(session) or {}
        canon_bpm = normalize_backing_bpm(canonical.get("backing_track_bpm"))
        if canon_bpm is not None:
            session["backing_track_bpm"] = int(canon_bpm)
            return int(canon_bpm)
    bpm = normalize_backing_bpm(session.get("backing_track_bpm"), default=default_bpm)
    if bpm is not None:
        session["backing_track_bpm"] = int(bpm)
    return int(bpm or default_bpm)


def write_canonical_backing_state(
    session: dict[str, Any],
    filters: dict[str, Any],
    *,
    reason: str = "",
    local_edit: bool = False,
) -> dict[str, Any]:
    normalized = _normalize_filters(filters)
    session[BACKING_STATE_KEY] = {
        **normalized,
        "last_write_reason": reason or None,
    }
    _apply_filters_to_session_keys(session, normalized)
    if local_edit:
        mark_backing_local_edit(session)
    session.pop(BACKING_PENDING_SYNC_KEY, None)
    return normalized


def prepare_backing_page(session: dict[str, Any]) -> dict[str, Any]:
    """Reconcile Backing widgets with canonical blob before page widgets render."""
    if is_backing_locally_dirty(session):
        gathered = gather_backing_filters(session)
        return write_canonical_backing_state(
            session,
            gathered,
            reason="local_edit_preserve",
            local_edit=True,
        )
    canonical = canonical_backing_filters(session)
    if canonical is not None:
        return write_canonical_backing_state(session, canonical, reason="canonical_preserve")
    gathered = gather_backing_filters(session)
    if _filters_have_content(gathered):
        return write_canonical_backing_state(session, gathered, reason="reconcile_on_load")
    return gathered


def commit_backing_state_from_session(session: dict[str, Any], *, reason: str = "autosave") -> dict[str, Any]:
    filters = gather_backing_filters(session)
    filters = _preserve_durable_filters_for_autosave(session, filters, reason=reason)
    return write_canonical_backing_state(session, filters, reason=reason, local_edit=False)


def flush_backing_edits(session: dict[str, Any], *, reason: str = "backing_edit") -> dict[str, Any]:
    filters = gather_backing_filters(session)
    return write_canonical_backing_state(session, filters, reason=reason, local_edit=True)


def _backing_filters_from_blob(state: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return None
    meta = state.get(BACKING_STATE_KEY)
    if isinstance(meta, dict):
        filters = _normalize_filters(meta)
        if _filters_have_content(filters):
            return filters
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get("backing_filters"), dict):
        filters = _normalize_filters(ws["backing_filters"])
        if _filters_have_content(filters):
            return filters
    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}
    if isinstance(session_extra, dict):
        filters = _normalize_filters(
            {key: session_extra.get(key) for key in BACKING_SCALAR_KEYS if key in session_extra}
        )
        if _filters_have_content(filters):
            return filters
    return None


def apply_cloud_backing_state_if_allowed(session: dict[str, Any], state: dict[str, Any]) -> bool:
    if is_backing_locally_dirty(session):
        session["_backing_restore_skipped_reason"] = "local_dirty"
        return False
    filters = _backing_filters_from_blob(state)
    if not filters:
        session.pop(BACKING_RESTORED_KEY, None)
        return False
    write_canonical_backing_state(session, filters, reason="cloud_restore")
    session[BACKING_RESTORED_KEY] = True
    session["_backing_restore_skipped_reason"] = None
    clear_backing_local_edit(session)
    return True


def apply_backing_source_state_from_ami(
    session: dict[str, Any],
    source_state: dict[str, Any],
) -> None:
    if not isinstance(source_state, dict):
        return
    filters = gather_backing_filters(session)
    widgets = source_state.get("widget_params")
    if isinstance(widgets, dict):
        for key in BACKING_SCALAR_KEYS:
            if key not in widgets or widgets[key] in (None, ""):
                continue
            if key == "backing_track_multi_sections":
                filters[key] = _normalize_multi_sections(widgets[key])
            elif key == "backing_track_bpm":
                filters[key] = normalize_backing_bpm(widgets[key])
            elif key == "backing_volume":
                filters[key] = normalize_backing_volume(widgets[key])
            elif key == "backing_track_loops":
                filters[key] = normalize_backing_loops(widgets[key])
            elif key == "backing_time_signature_override":
                filters[key] = bool(widgets[key])
            elif key == "backing_groove_style":
                filters[key] = normalize_backing_groove(widgets[key])
            elif key == "backing_track_scope":
                filters[key] = normalize_backing_scope(widgets[key])
            elif key == "backing_time_signature":
                filters[key] = normalize_backing_meter(widgets[key])
            else:
                filters[key] = str(widgets[key]).strip()
    write_canonical_backing_state(session, filters, reason="ami_return")
    clear_backing_local_edit(session)


def collect_backing_persistence_trace(
    session: dict[str, Any],
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonical_backing_filters(session) or {}
    envelope: dict[str, Any] = {}
    cloud_meta: dict[str, Any] = {}
    if isinstance(payload, dict):
        ws = payload.get("music_workspace_state")
        if isinstance(ws, dict) and isinstance(ws.get("backing_filters"), dict):
            envelope = _normalize_filters(ws["backing_filters"])
        cloud_meta = payload.get(BACKING_STATE_KEY) if isinstance(payload.get(BACKING_STATE_KEY), dict) else {}
    return {
        "backing_canonical_bpm": canonical.get("backing_track_bpm", ""),
        "backing_canonical_groove": canonical.get("backing_groove_style", ""),
        "backing_canonical_scope": canonical.get("backing_track_scope", ""),
        "backing_filters_bpm": envelope.get("backing_track_bpm", ""),
        "backing_filters_groove": envelope.get("backing_groove_style", ""),
        "cloud_payload_backing_bpm": cloud_meta.get("backing_track_bpm", ""),
        "cloud_payload_backing_groove": cloud_meta.get("backing_groove_style", ""),
        "restored_backing_bpm": session.get("backing_track_bpm", ""),
        "restored_backing_groove": session.get("backing_groove_style", ""),
        "backing_dirty": is_backing_locally_dirty(session),
        "backing_restore_applied": bool(session.get(BACKING_RESTORED_KEY)),
        "backing_restore_skipped": session.get("_backing_restore_skipped_reason"),
        "backing_last_write": canonical.get("last_write_reason")
        or (session.get(BACKING_STATE_KEY) or {}).get("last_write_reason"),
    }


def render_backing_state_debug(st: Any, session: dict[str, Any]) -> None:
    trace = collect_backing_persistence_trace(session)
    st.sidebar.caption(
        f"**backing_state:** dirty=`{trace['backing_dirty']}` "
        f"scope=`{trace['backing_canonical_scope']}` "
        f"bpm=`{trace['backing_canonical_bpm']}` "
        f"groove=`{trace['backing_canonical_groove']}`"
    )
    st.sidebar.caption(
        f"**backing widget:** bpm=`{trace['restored_backing_bpm']}` "
        f"groove=`{trace['restored_backing_groove']}` "
        f"restore=`{trace['backing_restore_applied']}`"
    )
    if trace.get("backing_last_write"):
        st.sidebar.caption(f"**backing last_write:** `{trace['backing_last_write']}`")
    if trace.get("backing_restore_skipped"):
        st.sidebar.caption(f"**backing restore skipped:** `{trace['backing_restore_skipped']}`")
