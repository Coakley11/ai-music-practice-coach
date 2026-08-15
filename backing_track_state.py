"""Canonical Backing Track page filters — scope, tempo, groove, meter, volume."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

BACKING_STATE_KEY = "backing_track_state"
BACKING_DIRTY_KEY = "backing_track_state_dirty"
BACKING_LOCAL_EDIT_TS_KEY = "backing_track_state_last_local_edit_ts"
BACKING_USER_EDIT_INTENT_KEY = "_backing_user_edit_intent"
BACKING_USER_EDITS_ALLOWED_KEY = "_backing_user_edits_allowed"
BACKING_PENDING_SYNC_KEY = "_backing_filters_pending_sync"
BACKING_RESTORED_KEY = "_backing_track_state_cloud_restored"

BACKING_SCOPE_CHOICES = (
    "Full song",
    "Selected sections",
    "Single section",
    "Multiple selected sections",
)

BACKING_LOOPS_MIN = 1
BACKING_LOOPS_MAX = 10
BACKING_LOOPS_DEFAULT = 2
BACKING_VOLUME_DEFAULT = 0.75

# Live Streamlit widget keys — must match gather_backing_filters + envelope fields.
BACKING_METER_WIDGET_KEY = "backing_time_signature"
BACKING_METER_OVERRIDE_WIDGET_KEY = "backing_time_signature_override"
BACKING_SCOPE_WIDGET_KEY = "backing_track_scope"
BACKING_SINGLE_SECTION_WIDGET_KEY = "backing_track_single_section"
BACKING_MULTI_SECTIONS_WIDGET_KEY = "backing_track_multi_sections"
BACKING_LOOPS_WIDGET_KEY = "backing_track_loops"
BACKING_QUICK_SECTION_WIDGET_KEY = "backing_quick_section"

BACKING_DURABLE_WIDGET_KEYS = frozenset(
    {
        BACKING_METER_WIDGET_KEY,
        BACKING_METER_OVERRIDE_WIDGET_KEY,
        BACKING_SCOPE_WIDGET_KEY,
        BACKING_SINGLE_SECTION_WIDGET_KEY,
        BACKING_MULTI_SECTIONS_WIDGET_KEY,
        BACKING_LOOPS_WIDGET_KEY,
        BACKING_QUICK_SECTION_WIDGET_KEY,
        "backing_track_bpm",
        "backing_groove_style",
    }
)

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
    "backing_autoplay",
    "backing_transport_status",
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
    "backing_autoplay",
    "backing_transport_status",
)

BACKING_WIDGETS_SEEDED_KEY = "_backing_durable_widgets_seeded"

BACKING_DEVICE_COMPARE_LABELS: tuple[str, ...] = (
    "device_id",
    "trace_captured_at",
    "cloud_updated_at",
    "local_updated_at",
    "backing_last_save_at",
    "backing_local_edit_at",
    "backing_last_write",
    "last_save_cloud",
    "cloud_payload_source",
    "backing_cloud_writer_device_id",
    "backing_cloud_writer_updated_at",
    "backing_rendered_bpm",
    "backing_rendered_scope",
    "backing_rendered_loops",
    "backing_rendered_groove",
    "backing_rendered_meter",
    "backing_rendered_meter_override",
    "backing_canonical_bpm",
    "backing_canonical_scope",
    "backing_canonical_loops",
    "backing_canonical_groove",
    "backing_canonical_meter",
    "backing_payload_bpm",
    "backing_payload_scope",
    "backing_payload_loops",
    "backing_payload_groove",
    "backing_cloud_bpm",
    "backing_cloud_scope",
    "backing_cloud_loops",
    "backing_cloud_groove",
    "backing_cloud_meter",
    "backing_widget_canonical_mismatch",
    "backing_sync_failure_class",
    "backing_stale_cloud_hint",
    "backing_user_edit_intent",
    "backing_user_edits_allowed",
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
    "BACKING_DURABLE_WIDGET_KEYS",
    "BACKING_LOOPS_WIDGET_KEY",
    "BACKING_METER_OVERRIDE_WIDGET_KEY",
    "BACKING_METER_WIDGET_KEY",
    "BACKING_QUICK_SECTION_WIDGET_KEY",
    "BACKING_SCOPE_WIDGET_KEY",
    "BACKING_SINGLE_SECTION_WIDGET_KEY",
    "apply_backing_source_state_from_ami",
    "apply_cloud_backing_state_if_allowed",
    "canonical_backing_filters",
    "clear_backing_local_edit",
    "collect_backing_persistence_trace",
    "commit_backing_canonical_blob_only",
    "commit_backing_state_from_session",
    "coerce_backing_groove_for_widget",
    "flush_backing_edits",
    "gather_backing_filters",
    "is_backing_locally_dirty",
    "begin_backing_page_widget_phase",
    "enable_backing_user_edits",
    "is_backing_user_dirty",
    "mark_backing_local_edit",
    "mark_backing_user_edit",
    "mark_backing_pending_sync",
    "normalize_backing_groove",
    "normalize_backing_scope",
    "resolve_selected_section_names",
    "reset_backing_playback_scope_to_full_song",
    "seed_backing_multi_sections_for_widget",
    "backing_canonical_playback_seed",
    "backing_canonical_meter_seed",
    "backing_filters_for_workspace_envelope",
    "classify_backing_sync_failure_class",
    "BACKING_DEVICE_COMPARE_LABELS",
    "bind_backing_rendered_widgets_from_canonical",
    "collect_backing_device_context",
    "collect_rendered_backing_widget_trace",
    "format_backing_device_compare_trace",
    "has_restored_backing_canonical",
    "record_backing_disk_payload_trace",
    "resolve_backing_trace_payloads",
    "snapshot_backing_path_trace",
    "sync_backing_session_keys_for_save",
    "seed_backing_widgets_from_canonical",
    "prepare_backing_bpm_for_widget",
    "prepare_backing_durable_widgets",
    "prepare_backing_meter_for_widget",
    "prepare_backing_page",
    "prepare_backing_scope_for_widget",
    "render_backing_state_debug",
    "strip_durable_backing_snapshot_keys",
    "sync_backing_scope_widgets_after_user_edit",
    "write_canonical_backing_state",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_backing_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(BACKING_DIRTY_KEY))


def is_backing_user_dirty(session: dict[str, Any]) -> bool:
    """True only when the user changed a Backing widget after page load."""
    return bool(session.get(BACKING_DIRTY_KEY)) and bool(session.get(BACKING_USER_EDIT_INTENT_KEY))


def mark_backing_local_edit(session: dict[str, Any]) -> None:
    session[BACKING_DIRTY_KEY] = True
    session[BACKING_LOCAL_EDIT_TS_KEY] = _utc_now_iso()


def mark_backing_user_edit(session: dict[str, Any]) -> None:
    """Mark a real user Backing widget change (not widget seeding / restore)."""
    session[BACKING_DIRTY_KEY] = True
    session[BACKING_USER_EDIT_INTENT_KEY] = True
    session[BACKING_LOCAL_EDIT_TS_KEY] = _utc_now_iso()
    session[BACKING_PENDING_SYNC_KEY] = True


def clear_backing_local_edit(session: dict[str, Any]) -> None:
    session.pop(BACKING_DIRTY_KEY, None)
    session.pop(BACKING_LOCAL_EDIT_TS_KEY, None)
    session.pop(BACKING_USER_EDIT_INTENT_KEY, None)
    session.pop(BACKING_PENDING_SYNC_KEY, None)


def mark_backing_pending_sync(session: dict[str, Any]) -> None:
    session[BACKING_PENDING_SYNC_KEY] = True


def begin_backing_page_widget_phase(session: dict[str, Any]) -> None:
    """Reset user-edit gate before Backing widgets render; drop spurious dirty flags."""
    session[BACKING_USER_EDITS_ALLOWED_KEY] = False
    if session.get(BACKING_PENDING_SYNC_KEY) and not is_backing_user_dirty(session):
        session.pop(BACKING_PENDING_SYNC_KEY, None)
    if is_backing_locally_dirty(session) and not session.get(BACKING_USER_EDIT_INTENT_KEY):
        session.pop(BACKING_DIRTY_KEY, None)
        session.pop(BACKING_LOCAL_EDIT_TS_KEY, None)


def enable_backing_user_edits(session: dict[str, Any]) -> None:
    """Allow widget on_change handlers to count as user edits after first render."""
    session[BACKING_USER_EDITS_ALLOWED_KEY] = True


def _clear_spurious_backing_dirty(session: dict[str, Any]) -> None:
    if is_backing_locally_dirty(session) and not session.get(BACKING_USER_EDIT_INTENT_KEY):
        session.pop(BACKING_DIRTY_KEY, None)
        session.pop(BACKING_LOCAL_EDIT_TS_KEY, None)
    if session.get(BACKING_PENDING_SYNC_KEY) and not is_backing_user_dirty(session):
        session.pop(BACKING_PENDING_SYNC_KEY, None)


def _should_seed_widgets_from_canonical(session: dict[str, Any]) -> bool:
    """True when canonical may hydrate widget keys (restore / first load), not mid-edit reruns."""
    try:
        from backing_play_session import play_session_blocks_canonical_seed

        if play_session_blocks_canonical_seed(session):
            return False
    except ImportError:
        pass
    if is_backing_user_dirty(session):
        return False
    if session.get(BACKING_PENDING_SYNC_KEY):
        return False
    if session.get(BACKING_RESTORED_KEY):
        return True
    if session.get(BACKING_WIDGETS_SEEDED_KEY):
        return False
    canonical = canonical_backing_filters(session)
    if canonical is None:
        return False
    if not any(key in session for key in BACKING_DURABLE_WIDGET_KEYS):
        return True
    return False


def seed_backing_widgets_from_canonical(
    session: dict[str, Any],
    canonical: dict[str, Any],
    *,
    reason: str = "canonical_preserve",
) -> dict[str, Any]:
    """One-way canonical → widget hydrate for restore / first page load only."""
    normalized = write_canonical_backing_state(session, canonical, reason=reason)
    session[BACKING_WIDGETS_SEEDED_KEY] = True
    session.pop(BACKING_RESTORED_KEY, None)
    return normalized


def normalize_backing_scope(scope: Any) -> str:
    raw = str(scope or "").strip()
    if raw in BACKING_SCOPE_CHOICES:
        if raw in ("Single section", "Multiple selected sections"):
            return "Selected sections"
        return raw
    low = raw.lower()
    if "selected" in low and "section" in low:
        return "Selected sections"
    if "multiple" in low or "single" in low:
        return "Selected sections"
    return "Full song"


def resolve_selected_section_names(
    session: dict[str, Any],
    section_names_in_order: list[str],
) -> list[str]:
    """Return chosen sections in original song order (empty = full song)."""
    scope = normalize_backing_scope(session.get(BACKING_SCOPE_WIDGET_KEY) or session.get("backing_track_scope"))
    if scope != "Selected sections":
        return []
    multi = _normalize_multi_sections(session.get(BACKING_MULTI_SECTIONS_WIDGET_KEY))
    if not multi:
        single = str(session.get(BACKING_SINGLE_SECTION_WIDGET_KEY) or "").strip()
        if single:
            multi = [single]
    if not multi:
        return []
    chosen = set(multi)
    return [name for name in section_names_in_order if name in chosen]


def seed_backing_multi_sections_for_widget(
    session: dict[str, Any],
    section_names: list[str],
) -> list[str]:
    """Ensure multiselect has a default when scope is Selected sections."""
    names = list(section_names or [])
    if not names:
        return []
    existing = _normalize_multi_sections(session.get(BACKING_MULTI_SECTIONS_WIDGET_KEY))
    if existing:
        ordered = [n for n in names if n in set(existing)]
        if ordered:
            session[BACKING_MULTI_SECTIONS_WIDGET_KEY] = ordered
            if len(ordered) == 1:
                session[BACKING_SINGLE_SECTION_WIDGET_KEY] = ordered[0]
            return ordered
    single = str(session.get(BACKING_SINGLE_SECTION_WIDGET_KEY) or "").strip()
    if single in names:
        session[BACKING_MULTI_SECTIONS_WIDGET_KEY] = [single]
        return [single]
    preferred = [
        n
        for n in names
        if any(token in n.lower() for token in ("verse", "chorus"))
    ]
    seed = preferred[:2] if preferred else names[:1]
    session[BACKING_MULTI_SECTIONS_WIDGET_KEY] = seed
    if len(seed) == 1:
        session[BACKING_SINGLE_SECTION_WIDGET_KEY] = seed[0]
    return seed


def reset_backing_playback_scope_to_full_song(session: dict[str, Any], *, source: str) -> None:
    """Reset session + canonical backing scope to Full Song (entry, song change, return handoff)."""
    session[BACKING_SCOPE_WIDGET_KEY] = "Full song"
    session.pop(BACKING_SINGLE_SECTION_WIDGET_KEY, None)
    session.pop(BACKING_MULTI_SECTIONS_WIDGET_KEY, None)
    session[BACKING_QUICK_SECTION_WIDGET_KEY] = "Full song"
    try:
        from custom_progression_lab import (
            PENDING_BACKING_MULTI_SECTIONS,
            PENDING_BACKING_SCOPE,
            PENDING_BACKING_SINGLE_SECTION,
        )

        session.pop(PENDING_BACKING_SCOPE, None)
        session.pop(PENDING_BACKING_SINGLE_SECTION, None)
        session.pop(PENDING_BACKING_MULTI_SECTIONS, None)
    except ImportError:
        pass
    try:
        from backing_workflow_context import BACKING_WORKFLOW_SCOPE_OWNER_KEY

        session.pop(BACKING_WORKFLOW_SCOPE_OWNER_KEY, None)
    except ImportError:
        session.pop("_backing_workflow_scope_owner", None)
    canon = dict(canonical_backing_filters(session) or {})
    merged = {
        **canon,
        "backing_track_scope": "Full song",
        "backing_track_single_section": "",
        "backing_track_multi_sections": [],
        "backing_quick_section": "Full song",
    }
    normalized = _normalize_filters(merged)
    session[BACKING_STATE_KEY] = {
        **normalized,
        "last_write_reason": f"playback_scope_default:{source}",
    }
    session.pop(BACKING_PENDING_SYNC_KEY, None)
    session.pop(BACKING_WIDGETS_SEEDED_KEY, None)


def sync_backing_scope_widgets_after_user_edit(session: dict[str, Any]) -> None:
    """Keep section widget keys consistent with the scope radio after a user change."""
    scope = normalize_backing_scope(session.get(BACKING_SCOPE_WIDGET_KEY))
    if scope == "Full song":
        session.pop(BACKING_SINGLE_SECTION_WIDGET_KEY, None)
        session.pop(BACKING_MULTI_SECTIONS_WIDGET_KEY, None)
        session[BACKING_QUICK_SECTION_WIDGET_KEY] = "Full song"


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
    loops_raw = src.get("backing_track_loops")
    if loops_raw is None:
        loops_norm = BACKING_LOOPS_DEFAULT
    else:
        loops_norm = normalize_backing_loops(loops_raw)
    meter_raw = src.get("backing_time_signature")
    if meter_raw is None:
        meter_norm = "4/4"
    else:
        meter_norm = normalize_backing_meter(meter_raw)
    return {
        "backing_track_scope": normalize_backing_scope(src.get("backing_track_scope")),
        "backing_track_single_section": str(src.get("backing_track_single_section") or "").strip(),
        "backing_track_multi_sections": _normalize_multi_sections(src.get("backing_track_multi_sections")),
        "backing_track_loops": loops_norm,
        "backing_track_bpm": normalize_backing_bpm(src.get("backing_track_bpm")),
        "backing_groove_style": normalize_backing_groove(src.get("backing_groove_style")),
        "backing_volume": normalize_backing_volume(src.get("backing_volume")),
        "backing_time_signature": meter_norm,
        "backing_time_signature_override": bool(override_raw),
        "backing_quick_section": str(src.get("backing_quick_section") or "").strip(),
        "backing_autoplay": bool(src.get("backing_autoplay")),
        "backing_transport_status": str(src.get("backing_transport_status") or "").strip(),
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


def strip_durable_backing_snapshot_keys(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Drop canonical-backed widget keys from legacy page snapshots."""
    if not isinstance(snapshot, dict):
        return {}
    return {key: val for key, val in snapshot.items() if key not in BACKING_DURABLE_WIDGET_KEYS}


def _sync_scope_keys_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Align scope, selected sections, and legacy quick-section from live widget keys."""
    quick = str(session.get(BACKING_QUICK_SECTION_WIDGET_KEY) or "").strip()
    scope_raw = session.get(BACKING_SCOPE_WIDGET_KEY)
    scope = normalize_backing_scope(scope_raw)
    if BACKING_SCOPE_WIDGET_KEY in session and scope == "Full song":
        return {
            "backing_track_scope": "Full song",
            "backing_track_single_section": "",
            "backing_track_multi_sections": [],
            "backing_quick_section": "Full song",
        }
    single = str(session.get(BACKING_SINGLE_SECTION_WIDGET_KEY) or "").strip()
    multi = _normalize_multi_sections(session.get(BACKING_MULTI_SECTIONS_WIDGET_KEY))
    if scope == "Selected sections":
        if multi:
            single = multi[0] if len(multi) == 1 else ""
            quick = multi[0] if len(multi) == 1 else "Full song"
        elif single:
            multi = [single]
            quick = single
    elif quick and quick != "Full song":
        scope = "Selected sections"
        single = quick
        multi = [quick]
    elif scope == "Full song" and not quick:
        quick = "Full song"
    return {
        "backing_track_scope": scope,
        "backing_track_single_section": single,
        "backing_track_multi_sections": multi,
        "backing_quick_section": quick,
    }


def _per_song_bpm_slider_key(sync_id: str) -> str:
    try:
        from songs.playback_defaults import backing_bpm_slider_widget_key

        return backing_bpm_slider_widget_key(sync_id)
    except ImportError:
        safe = str(sync_id).replace(":", "_").replace("/", "_").replace(" ", "_")
        return f"backing_track_bpm::{safe}"


def _rendered_bpm_from_session(session: dict[str, Any], *, sync_id: str = "") -> tuple[str, int | None]:
    """BPM from the visible per-song slider key (what Streamlit renders)."""
    if sync_id:
        slider_key = _per_song_bpm_slider_key(sync_id)
        if slider_key in session:
            return slider_key, normalize_backing_bpm(session[slider_key])
    for key, val in session.items():
        if str(key).startswith("backing_track_bpm::"):
            return str(key), normalize_backing_bpm(val)
    if "backing_track_bpm" in session:
        return "backing_track_bpm", normalize_backing_bpm(session.get("backing_track_bpm"))
    return "", None


def _widget_bpm_from_session(session: dict[str, Any]) -> int | None:
    """BPM from gather/commit keys (may differ from rendered slider)."""
    _, rendered = _rendered_bpm_from_session(session)
    if rendered is not None:
        return rendered
    if "backing_track_bpm" in session:
        return normalize_backing_bpm(session.get("backing_track_bpm"))
    return None


def _rendered_differs_from_canonical(
    session: dict[str, Any],
    sync_id: str,
    canonical: dict[str, Any] | None = None,
) -> bool:
    canon = _normalize_filters(canonical if isinstance(canonical, dict) else (canonical_backing_filters(session) or {}))
    if not _filters_have_content(canon):
        return False
    _, rendered_bpm = _rendered_bpm_from_session(session, sync_id=sync_id)
    canon_bpm = normalize_backing_bpm(canon.get("backing_track_bpm"))
    if rendered_bpm is not None and canon_bpm is not None and rendered_bpm != canon_bpm:
        return True
    pairs = (
        (BACKING_SCOPE_WIDGET_KEY, "backing_track_scope", normalize_backing_scope),
        (BACKING_LOOPS_WIDGET_KEY, "backing_track_loops", normalize_backing_loops),
        ("backing_groove_style", "backing_groove_style", normalize_backing_groove),
        (BACKING_QUICK_SECTION_WIDGET_KEY, "backing_quick_section", str),
        (BACKING_METER_WIDGET_KEY, "backing_time_signature", normalize_backing_meter),
    )
    for wkey, ckey, norm in pairs:
        if wkey not in session and ckey not in canon:
            continue
        wval = norm(session.get(wkey)) if wkey in session else None
        cval = norm(canon.get(ckey)) if canon.get(ckey) not in (None, "") else None
        if cval is not None and wval is not None and wval != cval:
            return True
    if bool(session.get(BACKING_METER_OVERRIDE_WIDGET_KEY)) != bool(canon.get("backing_time_signature_override")):
        return True
    return False


def collect_rendered_backing_widget_trace(
    session: dict[str, Any],
    *,
    sync_id: str = "",
) -> dict[str, Any]:
    """Trace values bound to visible Streamlit widget keys (not canonical blob alone)."""
    slider_key, rendered_bpm = _rendered_bpm_from_session(session, sync_id=sync_id)
    canonical = canonical_backing_filters(session) or {}
    canon_bpm = canonical.get("backing_track_bpm", "")
    mismatch = _rendered_differs_from_canonical(session, sync_id, canonical) if sync_id else False
    return {
        "backing_rendered_bpm_key": slider_key,
        "backing_rendered_bpm": rendered_bpm if rendered_bpm is not None else "",
        "backing_rendered_scope": normalize_backing_scope(session.get(BACKING_SCOPE_WIDGET_KEY, "")),
        "backing_rendered_loops": session.get(BACKING_LOOPS_WIDGET_KEY, ""),
        "backing_rendered_groove": session.get("backing_groove_style", ""),
        "backing_rendered_quick_section": session.get(BACKING_QUICK_SECTION_WIDGET_KEY, ""),
        "backing_rendered_meter": session.get(BACKING_METER_WIDGET_KEY, ""),
        "backing_rendered_meter_override": bool(session.get(BACKING_METER_OVERRIDE_WIDGET_KEY, False)),
        "backing_rendered_single_section": session.get(BACKING_SINGLE_SECTION_WIDGET_KEY, ""),
        "backing_widget_canonical_mismatch": mismatch,
        "backing_render_bind_reason": session.get("_backing_render_bind_reason", ""),
        "backing_rendered_bpm_vs_canonical": (
            f"{rendered_bpm}!={canon_bpm}"
            if rendered_bpm is not None and canon_bpm not in (None, "") and rendered_bpm != canon_bpm
            else ""
        ),
    }


def bind_backing_rendered_widgets_from_canonical(
    session: dict[str, Any],
    *,
    sync_id: str,
    default_bpm: int = 100,
    default_groove: str = "",
    default_meter: str = "4/4",
) -> dict[str, Any]:
    """Push canonical blob into every visible widget key (incl. per-song BPM slider)."""
    if is_backing_user_dirty(session) or session.get("_backing_transport_user_stopped"):
        return collect_rendered_backing_widget_trace(session, sync_id=sync_id)
    try:
        from backing_play_session import play_session_blocks_canonical_seed

        if play_session_blocks_canonical_seed(session):
            return collect_rendered_backing_widget_trace(session, sync_id=sync_id)
    except ImportError:
        pass

    canonical = canonical_backing_filters(session)
    if canonical is None:
        return collect_rendered_backing_widget_trace(session, sync_id=sync_id)

    _clear_spurious_backing_dirty(session)
    rendered_mismatch = _rendered_differs_from_canonical(session, sync_id, canonical)
    if (
        rendered_mismatch
        and session.get(BACKING_WIDGETS_SEEDED_KEY)
        and not session.get(BACKING_RESTORED_KEY)
        and session.get("_backing_restore_source") != "cloud_restore"
    ):
        gathered = gather_backing_filters(session)
        write_canonical_backing_state(
            session,
            gathered,
            reason="rendered_widget_wins",
            local_edit=True,
        )
        mark_backing_user_edit(session)
        return collect_rendered_backing_widget_trace(session, sync_id=sync_id)

    should_bind = (
        session.get(BACKING_RESTORED_KEY)
        or not session.get(BACKING_WIDGETS_SEEDED_KEY)
        or rendered_mismatch
    )
    if not should_bind:
        return collect_rendered_backing_widget_trace(session, sync_id=sync_id)

    bind_reason = (
        "cloud_restore"
        if session.get(BACKING_RESTORED_KEY) or session.get("_backing_restore_source") == "cloud_restore"
        else "rendered_canonical_mismatch"
    )
    _apply_filters_to_session_keys(session, canonical)
    slider_key = _per_song_bpm_slider_key(sync_id)
    bpm = normalize_backing_bpm(canonical.get("backing_track_bpm"), default=default_bpm)
    if bpm is not None:
        session[slider_key] = int(bpm)
        session["backing_track_bpm"] = int(bpm)
        session["bpm"] = int(bpm)
    groove = normalize_backing_groove(canonical.get("backing_groove_style") or default_groove)
    if groove:
        session["backing_groove_style"] = groove
    meter = normalize_backing_meter(canonical.get("backing_time_signature") or default_meter)
    if meter:
        session[BACKING_METER_WIDGET_KEY] = meter
    session[BACKING_METER_OVERRIDE_WIDGET_KEY] = bool(canonical.get("backing_time_signature_override"))
    session[BACKING_WIDGETS_SEEDED_KEY] = True
    session.pop(BACKING_RESTORED_KEY, None)
    session["_backing_render_bind_reason"] = bind_reason
    return collect_rendered_backing_widget_trace(session, sync_id=sync_id)


def sync_backing_session_keys_for_save(session: dict[str, Any]) -> None:
    """Mirror live widget keys into gather/commit keys before flush or disk build."""
    bpm = _widget_bpm_from_session(session)
    if bpm is not None:
        session["backing_track_bpm"] = int(bpm)
    groove = str(session.get("backing_groove_style") or "").strip()
    if not groove:
        try:
            from songs.playback_defaults import BACKING_GROOVE_KEY

            groove = str(session.get(BACKING_GROOVE_KEY) or "").strip()
            if groove:
                session["backing_groove_style"] = groove
        except ImportError:
            pass


def gather_backing_filters(session: dict[str, Any]) -> dict[str, Any]:
    """Read Backing page filters from live session keys."""
    sync_backing_session_keys_for_save(session)
    bpm_val = _widget_bpm_from_session(session)
    volume = session.get("backing_volume")
    if volume is None and "backing_volume" not in session:
        volume_val = None
    else:
        volume_val = normalize_backing_volume(volume)
    loops_raw = session.get(BACKING_LOOPS_WIDGET_KEY)
    if loops_raw is None and BACKING_LOOPS_WIDGET_KEY not in session:
        pending = session.get("_pending_backing_loops")
        if pending is not None:
            loops_raw = pending
            loops_val = normalize_backing_loops(pending)
        else:
            loops_val = None
    else:
        loops_val = normalize_backing_loops(loops_raw)
    scope_keys = _sync_scope_keys_from_session(session)
    meter = session.get(BACKING_METER_WIDGET_KEY)
    if meter is None and BACKING_METER_WIDGET_KEY not in session:
        meter_val = None
    else:
        meter_val = normalize_backing_meter(meter)
    return _normalize_filters(
        {
            **scope_keys,
            "backing_track_loops": loops_val,
            "backing_track_bpm": bpm_val,
            "backing_groove_style": session.get("backing_groove_style"),
            "backing_volume": volume_val,
            "backing_time_signature": meter_val,
            "backing_time_signature_override": bool(
                session.get(BACKING_METER_OVERRIDE_WIDGET_KEY, False)
            ),
            "backing_autoplay": bool(session.get("_backing_autoplay", False)),
            "backing_transport_status": str(session.get("backing_transport_status") or "").strip(),
        }
    )


def canonical_backing_filters(session: dict[str, Any]) -> dict[str, Any] | None:
    meta = session.get(BACKING_STATE_KEY)
    if not isinstance(meta, dict):
        return None
    filters = _normalize_filters(meta)
    if _filters_have_content(filters):
        return filters
    reason = str(meta.get("last_write_reason") or "")
    if reason.startswith("playback_scope_default:") or reason.startswith("song_improv_scope:"):
        return filters
    return None


def has_restored_backing_canonical(session: dict[str, Any]) -> bool:
    """True when a durable backing blob exists (cloud restore or prior edit)."""
    return canonical_backing_filters(session) is not None


def backing_canonical_playback_seed(session: dict[str, Any]) -> tuple[int | None, str | None]:
    """BPM + groove from canonical blob for playback-default seeding on hard refresh."""
    if is_backing_user_dirty(session):
        return None, None
    canonical = canonical_backing_filters(session) or {}
    bpm = normalize_backing_bpm(canonical.get("backing_track_bpm"))
    groove = normalize_backing_groove(canonical.get("backing_groove_style"))
    return bpm, groove or None


def backing_canonical_meter_seed(session: dict[str, Any]) -> tuple[str | None, bool | None]:
    """Meter + override flag from canonical blob for hard-refresh meter sync."""
    if is_backing_user_dirty(session):
        return None, None
    canonical = canonical_backing_filters(session) or {}
    meter_raw = str(canonical.get("backing_time_signature") or "").strip()
    override = bool(canonical.get("backing_time_signature_override"))
    if not meter_raw and not override:
        return None, None
    meter = normalize_backing_meter(meter_raw) if meter_raw else None
    return meter, override


def _filters_differ(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a = _normalize_filters(left)
    b = _normalize_filters(right)
    for key in BACKING_SCALAR_KEYS:
        if a.get(key) != b.get(key):
            return True
    return False


def _gathered_looks_like_song_defaults(
    filters: dict[str, Any],
    *,
    canonical: dict[str, Any] | None = None,
) -> bool:
    """True when live widget keys match generic song-default backing (not a user edit)."""
    f = _normalize_filters(filters)
    if normalize_backing_scope(f.get("backing_track_scope")) != "Full song":
        return False
    if normalize_backing_loops(f.get("backing_track_loops")) != BACKING_LOOPS_DEFAULT:
        return False
    if str(f.get("backing_track_single_section") or "").strip():
        return False
    if f.get("backing_track_multi_sections"):
        return False
    quick = str(f.get("backing_quick_section") or "").strip().lower()
    if quick not in ("", "full song"):
        return False
    if f.get("backing_time_signature_override"):
        return False
    if str(f.get("backing_time_signature") or "").strip() not in ("", "4/4"):
        return False
    canon = _normalize_filters(canonical) if isinstance(canonical, dict) else {}
    gather_bpm = normalize_backing_bpm(f.get("backing_track_bpm"))
    canon_bpm = normalize_backing_bpm(canon.get("backing_track_bpm"))
    if gather_bpm is not None and canon_bpm is not None and gather_bpm != canon_bpm:
        return False
    return True


def _preserve_durable_filters_for_autosave(
    session: dict[str, Any],
    filters: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    """Keep cloud-restored durable filters when song-default seeding clobbered widget keys."""
    if reason != "autosave":
        return filters
    if is_backing_locally_dirty(session) or session.get(BACKING_PENDING_SYNC_KEY):
        return filters
    existing = canonical_backing_filters(session) or {}
    merged = dict(filters)
    for key in _DURABLE_FILTER_KEYS:
        existing_val = existing.get(key)
        if existing_val in (None, ""):
            continue
        if key == "backing_track_multi_sections" and not existing_val:
            continue
        gathered_val = merged.get(key)
        if gathered_val != existing_val:
            merged[key] = existing_val
    return merged


def _resolve_backing_filters_for_envelope(
    session: dict[str, Any],
    *,
    state_blob: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """Authoritative backing_filters for workspace envelope + cloud (canonical first)."""
    session_canon = canonical_backing_filters(session)
    if session_canon is not None and _filters_have_content(session_canon):
        return _normalize_filters(session_canon), "canonical"

    blob = state_blob if isinstance(state_blob, dict) else {}
    blob_meta = blob.get(BACKING_STATE_KEY)
    if isinstance(blob_meta, dict):
        filters = _normalize_filters(blob_meta)
        if _filters_have_content(filters):
            return filters, "canonical"

    gathered = gather_backing_filters(session)
    normalized = _normalize_filters(gathered)
    if _filters_have_content(normalized):
        return normalized, "widget_fallback"
    return normalized, "widget_fallback"


def _apply_filters_to_session_keys(session: dict[str, Any], filters: dict[str, Any]) -> None:
    scope = normalize_backing_scope(filters.get("backing_track_scope"))
    session["backing_track_scope"] = scope
    if scope == "Full song":
        session.pop(BACKING_SINGLE_SECTION_WIDGET_KEY, None)
        session.pop(BACKING_MULTI_SECTIONS_WIDGET_KEY, None)
        session[BACKING_QUICK_SECTION_WIDGET_KEY] = "Full song"
    else:
        section = str(filters.get("backing_track_single_section") or "").strip()
        if section:
            session[BACKING_SINGLE_SECTION_WIDGET_KEY] = section
        else:
            session.pop(BACKING_SINGLE_SECTION_WIDGET_KEY, None)
        multi = _normalize_multi_sections(filters.get("backing_track_multi_sections"))
        if multi:
            session[BACKING_MULTI_SECTIONS_WIDGET_KEY] = multi
        else:
            session.pop(BACKING_MULTI_SECTIONS_WIDGET_KEY, None)
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
    if scope == "Full song":
        session[BACKING_QUICK_SECTION_WIDGET_KEY] = "Full song"
    elif quick:
        session[BACKING_QUICK_SECTION_WIDGET_KEY] = quick
    if "backing_autoplay" in filters:
        session["_backing_autoplay"] = bool(filters.get("backing_autoplay"))
    transport = str(filters.get("backing_transport_status") or "").strip()
    if transport:
        session["backing_transport_status"] = transport


def prepare_backing_transport_for_session(session: dict[str, Any]) -> None:
    """Restore backing transport — never replay autoplay from cloud; default stopped."""
    # One-shot: honor an in-session Play / karaoke auto-generate across the next rerun.
    if session.pop("_backing_play_request", False):
        session.pop("_backing_transport_user_stopped", None)
        session["_backing_autoplay"] = True
        session["backing_transport_status"] = "playing"
        return
    session["_backing_autoplay"] = False
    if session.get("_backing_transport_user_stopped"):
        session["backing_transport_status"] = "stopped"
        return
    if session.get("_last_backing_wav") and str(session.get("backing_transport_status") or "").strip().lower() in (
        "ready",
        "generating",
        "preparing",
    ):
        session["backing_transport_status"] = "ready"
        return
    canonical = canonical_backing_filters(session) or {}
    transport = str(canonical.get("backing_transport_status") or "").strip().lower()
    if transport in ("ready", "generating", "preparing"):
        session["backing_transport_status"] = "ready"
    elif transport == "playing":
        session["backing_transport_status"] = "stopped"
    elif transport:
        session["backing_transport_status"] = transport
    else:
        session["backing_transport_status"] = "stopped"


def commit_backing_transport_from_session(session: dict[str, Any], *, reason: str = "transport") -> None:
    """Persist transport flags into canonical backing blob without touching BPM widgets."""
    session["_backing_autoplay"] = bool(session.get("_backing_autoplay", False))
    transport = str(session.get("backing_transport_status") or "").strip().lower()
    if session.get("_backing_transport_user_stopped") or not session["_backing_autoplay"]:
        session["_backing_autoplay"] = False
        session["backing_transport_status"] = "stopped"
        transport = "stopped"
    meta = session.get(BACKING_STATE_KEY)
    if not isinstance(meta, dict):
        meta = {}
    meta = dict(meta)
    meta["backing_autoplay"] = False
    meta["backing_transport_status"] = transport or "stopped"
    meta["last_write_reason"] = reason
    session[BACKING_STATE_KEY] = meta


def coerce_backing_groove_for_widget(session: dict[str, Any], *, default_groove: str = "") -> str:
    if (
        not is_backing_locally_dirty(session)
        and not session.get(BACKING_PENDING_SYNC_KEY)
        and _should_seed_widgets_from_canonical(session)
    ):
        canonical = canonical_backing_filters(session) or {}
        canon_groove = normalize_backing_groove(canonical.get("backing_groove_style"))
        if canon_groove:
            session["backing_groove_style"] = canon_groove
            return canon_groove
    current = session.get("backing_groove_style")
    if current is not None and str(current).strip():
        normalized = normalize_backing_groove(current)
        if is_backing_user_dirty(session) or normalized != normalize_backing_groove(default_groove):
            session["backing_groove_style"] = normalized
        return normalized
    fallback = normalize_backing_groove(default_groove) or "Auto"
    session.setdefault("backing_groove_style", fallback)
    return str(session["backing_groove_style"])


def prepare_backing_bpm_for_widget(session: dict[str, Any], *, default_bpm: int = 100) -> int:
    try:
        from backing_play_session import backing_play_session_has_override, effective_backing_play_overrides

        if backing_play_session_has_override(session, "bpm"):
            resolved = int(effective_backing_play_overrides(session).get("bpm") or 0)
            if resolved > 0:
                session["backing_track_bpm"] = resolved
                return resolved
    except ImportError:
        pass
    if not is_backing_user_dirty(session) and _should_seed_widgets_from_canonical(session):
        canonical = canonical_backing_filters(session) or {}
        canon_bpm = normalize_backing_bpm(canonical.get("backing_track_bpm"))
        if canon_bpm is not None:
            session["backing_track_bpm"] = int(canon_bpm)
            return int(canon_bpm)
    bpm = normalize_backing_bpm(session.get("backing_track_bpm"), default=default_bpm)
    if bpm is not None and (is_backing_user_dirty(session) or _should_seed_widgets_from_canonical(session)):
        session["backing_track_bpm"] = int(bpm)
    return int(bpm or default_bpm)


def prepare_backing_durable_widgets(
    session: dict[str, Any],
    *,
    sync_id: str = "",
    default_bpm: int = 100,
    default_groove: str = "",
    default_meter: str = "4/4",
) -> None:
    """Bind all visible widget keys to canonical blob before Step 1/2 widgets render."""
    if sync_id:
        bind_backing_rendered_widgets_from_canonical(
            session,
            sync_id=sync_id,
            default_bpm=default_bpm,
            default_groove=default_groove,
            default_meter=default_meter,
        )
        return
    prepare_backing_scope_for_widget(session)


def prepare_backing_scope_for_widget(session: dict[str, Any]) -> None:
    """Bind scope/loop widgets to canonical blob before Step 1 widgets render."""
    if not _should_seed_widgets_from_canonical(session):
        return
    canonical = canonical_backing_filters(session)
    if canonical is None:
        return
    session["backing_track_scope"] = normalize_backing_scope(canonical.get("backing_track_scope"))
    section = str(canonical.get("backing_track_single_section") or "").strip()
    if section:
        session["backing_track_single_section"] = section
    multi = _normalize_multi_sections(canonical.get("backing_track_multi_sections"))
    if multi:
        session["backing_track_multi_sections"] = multi
    elif section and normalize_backing_scope(session.get("backing_track_scope")) == "Selected sections":
        session["backing_track_multi_sections"] = [section]
    session["backing_track_loops"] = normalize_backing_loops(canonical.get("backing_track_loops"))
    quick = str(canonical.get("backing_quick_section") or "").strip()
    if quick:
        session["backing_quick_section"] = quick
    session[BACKING_WIDGETS_SEEDED_KEY] = True
    session.pop(BACKING_RESTORED_KEY, None)


def prepare_backing_meter_for_widget(session: dict[str, Any], *, default_meter: str = "4/4") -> tuple[str, bool]:
    """Return meter for Step 2 radio; only seed widget keys on restore / first load."""
    if _should_seed_widgets_from_canonical(session):
        canonical = canonical_backing_filters(session) or {}
        meter_raw = str(canonical.get("backing_time_signature") or "").strip()
        override = bool(canonical.get("backing_time_signature_override"))
        if meter_raw or override:
            meter = normalize_backing_meter(meter_raw or default_meter)
            session["backing_time_signature"] = meter
            session["backing_time_signature_override"] = override
            session[BACKING_WIDGETS_SEEDED_KEY] = True
            session.pop(BACKING_RESTORED_KEY, None)
            return meter, override
    meter = normalize_backing_meter(session.get("backing_time_signature"), default=default_meter)
    override = bool(session.get("backing_time_signature_override"))
    return meter, override


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
    if not session.get(BACKING_USER_EDITS_ALLOWED_KEY):
        _apply_filters_to_session_keys(session, normalized)
    if local_edit:
        mark_backing_local_edit(session)
    session.pop(BACKING_PENDING_SYNC_KEY, None)
    return normalized


def prepare_backing_page(session: dict[str, Any]) -> dict[str, Any]:
    """Reconcile Backing canonical blob before page widgets render."""
    _clear_spurious_backing_dirty(session)
    prepare_backing_transport_for_session(session)
    if is_backing_user_dirty(session):
        gathered = gather_backing_filters(session)
        return write_canonical_backing_state(
            session,
            gathered,
            reason="local_edit_preserve",
            local_edit=False,
        )
    gathered = gather_backing_filters(session)
    canonical = canonical_backing_filters(session)
    if canonical is not None and _filters_differ(canonical, gathered):
        if _should_seed_widgets_from_canonical(session) or (
            _filters_have_content(canonical)
            and _gathered_looks_like_song_defaults(gathered, canonical=canonical)
        ):
            return seed_backing_widgets_from_canonical(
                session,
                canonical,
                reason="canonical_over_defaults",
            )
        if _filters_have_content(gathered) and not _gathered_looks_like_song_defaults(gathered):
            merged = dict(canonical)
            merged.update(gathered)
            return write_canonical_backing_state(
                session,
                merged,
                reason="session_backing_wins",
                local_edit=True,
            )
    if canonical is not None and _should_seed_widgets_from_canonical(session):
        return seed_backing_widgets_from_canonical(session, canonical, reason="canonical_preserve")
    if canonical is not None:
        return canonical
    if _filters_have_content(gathered):
        return write_canonical_backing_state(session, gathered, reason="reconcile_on_load")
    return gathered


def commit_backing_canonical_blob_only(
    session: dict[str, Any],
    *,
    reason: str = "reconcile",
    local_edit: bool = False,
) -> dict[str, Any]:
    """Update canonical blob from session without writing widget-backed keys.

    Safe after Backing widgets render — use instead of write_canonical_backing_state
    or prepare_backing_durable_widgets on post-render paths.
    """
    filters = gather_backing_filters(session)
    normalized = _normalize_filters(filters)
    session[BACKING_STATE_KEY] = {
        **normalized,
        "last_write_reason": reason or None,
    }
    if local_edit:
        mark_backing_local_edit(session)
    session.pop(BACKING_PENDING_SYNC_KEY, None)
    return normalized


def commit_backing_state_from_session(session: dict[str, Any], *, reason: str = "autosave") -> dict[str, Any]:
    filters = gather_backing_filters(session)
    if reason not in ("autosave",):
        return write_canonical_backing_state(session, filters, reason=reason, local_edit=False)
    filters = _preserve_durable_filters_for_autosave(session, filters, reason=reason)
    return write_canonical_backing_state(session, filters, reason=reason, local_edit=False)


def flush_backing_edits(session: dict[str, Any], *, reason: str = "backing_edit") -> dict[str, Any]:
    filters = gather_backing_filters(session)
    if reason == "stop":
        return commit_backing_canonical_blob_only(session, reason=reason)
    return write_canonical_backing_state(session, filters, reason=reason, local_edit=False)


def backing_filters_for_workspace_envelope(
    session: dict[str, Any],
    *,
    state_blob: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalized ``music_workspace_state.backing_filters`` from canonical blob or live widgets."""
    filters, source = _resolve_backing_filters_for_envelope(session, state_blob=state_blob)
    session["_backing_filters_source"] = source
    return filters


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
    if is_backing_user_dirty(session):
        session["_backing_restore_skipped_reason"] = "local_dirty"
        session["_backing_restore_source"] = "skipped_local_dirty"
        return False
    _clear_spurious_backing_dirty(session)
    filters = _backing_filters_from_blob(state)
    if not filters:
        try:
            from music_persistent_state import APP_ID
            from suite_cloud_state import load_cloud_full_session

            cloud_state, _ = load_cloud_full_session(APP_ID)
            if isinstance(cloud_state, dict):
                filters = _backing_filters_from_blob(cloud_state)
        except Exception:
            filters = None
    if not filters:
        session.pop(BACKING_RESTORED_KEY, None)
        session["_backing_restore_source"] = "skipped_no_blob"
        return False
    write_canonical_backing_state(session, filters, reason="cloud_restore")
    session[BACKING_RESTORED_KEY] = True
    session.pop(BACKING_WIDGETS_SEEDED_KEY, None)
    session["_backing_restore_skipped_reason"] = None
    session["_backing_restore_source"] = "cloud_restore"
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


def resolve_backing_trace_payloads(
    st: Any,
    session: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve envelope (canonical-derived) and cloud payloads for ?dev=1 backing trace."""
    envelope: dict[str, Any] = {}
    cloud: dict[str, Any] = {}

    filters, source = _resolve_backing_filters_for_envelope(session)
    session["_backing_filters_source"] = source
    if _filters_have_content(filters):
        ws = session.get("music_workspace_state")
        ws_shell = dict(ws) if isinstance(ws, dict) else {}
        envelope = {
            "music_workspace_state": {**ws_shell, "backing_filters": filters},
            BACKING_STATE_KEY: session.get(BACKING_STATE_KEY) or filters,
        }

    last_write = session.get("_suite_last_cloud_save_payload")
    if isinstance(last_write, dict) and session.get("_suite_persist_last_save_cloud"):
        cloud = last_write
        session["_backing_cloud_payload_source"] = "last_write"
    else:
        try:
            from music_persistent_state import APP_ID
            from suite_cloud_state import load_cloud_full_session

            cloud_state, _ = load_cloud_full_session(APP_ID)
            if isinstance(cloud_state, dict):
                cloud = cloud_state
            session["_backing_cloud_payload_source"] = "fetch" if cloud else "none"
        except Exception:
            session["_backing_cloud_payload_source"] = "none"

    return envelope, cloud


def _trace_bpm(val: Any) -> int | str:
    if val in (None, ""):
        return ""
    try:
        return int(val)
    except (TypeError, ValueError):
        return ""


def classify_backing_sync_failure_class(trace: dict[str, Any]) -> str:
    """Classify Test C failure into Dell save vs phone restore vs flush timing."""
    widget_bpm = _trace_bpm(trace.get("backing_widget_bpm"))
    canonical_bpm = _trace_bpm(trace.get("backing_canonical_bpm"))
    payload_bpm = _trace_bpm(trace.get("backing_payload_bpm"))
    cloud_bpm = _trace_bpm(trace.get("backing_cloud_bpm"))
    pending = bool(trace.get("backing_pending_sync"))
    last_write = str(trace.get("backing_last_write") or "")
    force_reason = str(trace.get("force_save_reason") or "")
    restore_source = str(trace.get("backing_restore_source") or "")
    last_save_cloud = bool(trace.get("last_save_cloud"))

    if restore_source.startswith("skipped"):
        return "phone_restore_skipped"

    if (
        cloud_bpm != ""
        and widget_bpm != ""
        and cloud_bpm != widget_bpm
        and restore_source == "cloud_restore"
        and _gathered_looks_like_song_defaults(
            {
                "backing_track_scope": trace.get("backing_widget_scope"),
                "backing_track_loops": trace.get("backing_widget_loops"),
                "backing_quick_section": trace.get("backing_widget_quick_section"),
                "backing_track_bpm": widget_bpm,
            }
        )
    ):
        return "phone_restore_overwrite_defaults"

    if widget_bpm != "" and canonical_bpm != "" and widget_bpm != canonical_bpm:
        return "dell_widget_canonical_mismatch"

    if trace.get("backing_widget_canonical_mismatch"):
        return "rendered_canonical_mismatch"

    if canonical_bpm != "" and payload_bpm != "" and canonical_bpm != payload_bpm:
        return "dell_canonical_payload_mismatch"

    if payload_bpm != "" and cloud_bpm != "" and payload_bpm != cloud_bpm:
        return "dell_payload_cloud_mismatch"

    if pending and force_reason != "backing_edit":
        block = str(trace.get("force_save_block_reason") or trace.get("cloud_write_error") or "")
        if block:
            return f"flush_save_not_triggered:{block}"
        return "flush_save_not_triggered"

    if widget_bpm != "" and not last_save_cloud and force_reason != "backing_edit":
        block = str(trace.get("force_save_block_reason") or trace.get("cloud_write_error") or "")
        if block:
            return f"flush_save_not_triggered:{block}"
        return "flush_save_not_triggered"

    if (
        widget_bpm != ""
        and canonical_bpm == widget_bpm
        and payload_bpm == widget_bpm
        and (cloud_bpm == "" or cloud_bpm == payload_bpm)
    ):
        return "path_ok"

    if cloud_bpm != "" and widget_bpm == cloud_bpm:
        return "path_ok"

    return "unclassified"


def record_backing_disk_payload_trace(session: dict[str, Any], state: dict[str, Any]) -> None:
    """Capture backing BPM from the disk/cloud payload about to be written."""
    if not isinstance(state, dict):
        return
    ws = state.get("music_workspace_state")
    bf: dict[str, Any] = {}
    if isinstance(ws, dict) and isinstance(ws.get("backing_filters"), dict):
        bf = _normalize_filters(ws["backing_filters"])
    elif isinstance(state.get(BACKING_STATE_KEY), dict):
        bf = _normalize_filters(state[BACKING_STATE_KEY])
    session["_music_backing_payload_bpm"] = bf.get("backing_track_bpm", "")
    session["_music_backing_payload_scope"] = bf.get("backing_track_scope", "")
    session["_music_backing_payload_loops"] = bf.get("backing_track_loops", "")
    session["_music_backing_payload_groove"] = bf.get("backing_groove_style", "")


def collect_backing_device_context(st: Any | None, session: dict[str, Any]) -> dict[str, Any]:
    """Device id + timestamps for cross-device Test C comparison."""
    device_id = "unknown"
    if st is not None:
        try:
            from music_persistent_state import get_music_device_id

            device_id = get_music_device_id(st)
        except ImportError:
            pass

    cloud_updated = (
        session.get("_suite_cloud_fetch_updated_at")
        or session.get("_suite_persist_debug_cloud_ts")
        or ""
    )
    if not cloud_updated and st is not None:
        try:
            from music_persistent_state import APP_ID
            from suite_cloud_state import load_cloud_full_session

            _, cloud_ts = load_cloud_full_session(APP_ID)
            if cloud_ts:
                cloud_updated = cloud_ts
                session["_suite_cloud_fetch_updated_at"] = cloud_ts
        except Exception:
            pass

    local_updated = (
        session.get("_suite_persist_debug_disk_ts")
        or session.get("_suite_persist_last_save_at")
        or session.get("_suite_persist_last_restore_at")
        or ""
    )

    cloud_writer_device = ""
    cloud_writer_updated = ""
    last_write = session.get("_suite_last_cloud_save_payload")
    if isinstance(last_write, dict):
        ws = last_write.get("music_workspace_state")
        if isinstance(ws, dict):
            cloud_writer_device = str(ws.get("device_id") or "")
            cloud_writer_updated = str(ws.get("updated_at") or "")
    if not cloud_writer_device:
        ws_local = session.get("music_workspace_state")
        if isinstance(ws_local, dict):
            cloud_writer_device = str(ws_local.get("device_id") or "")
            if not cloud_writer_updated:
                cloud_writer_updated = str(ws_local.get("updated_at") or "")

    return {
        "device_id": device_id,
        "trace_captured_at": _utc_now_iso(),
        "cloud_updated_at": cloud_updated,
        "local_updated_at": local_updated,
        "backing_last_save_at": session.get("_suite_persist_last_save_at", ""),
        "backing_local_edit_at": session.get(BACKING_LOCAL_EDIT_TS_KEY, ""),
        "backing_cloud_writer_device_id": cloud_writer_device,
        "backing_cloud_writer_updated_at": cloud_writer_updated,
    }


def format_backing_device_compare_trace(trace: dict[str, Any]) -> str:
    """Single copy-paste block for side-by-side Dell vs phone comparison."""
    lines = ["# Backing device compare (Test C)", ""]
    for label in BACKING_DEVICE_COMPARE_LABELS:
        val = trace.get(label)
        if val is None or val == "":
            lines.append(f"{label}: (empty)")
        else:
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


def classify_backing_stale_cloud_hint(trace: dict[str, Any]) -> str:
    """Single-device hint: cloud may be older than local or rendered widgets."""
    cloud_updated = str(trace.get("cloud_updated_at") or "")
    local_updated = str(trace.get("local_updated_at") or "")
    last_save = str(trace.get("backing_last_save_at") or "")
    cloud_bpm = _trace_bpm(trace.get("backing_cloud_bpm"))
    rendered_bpm = _trace_bpm(trace.get("backing_rendered_bpm"))
    payload_bpm = _trace_bpm(trace.get("backing_payload_bpm"))

    if trace.get("backing_widget_canonical_mismatch"):
        return "rendered_widgets_stale_vs_canonical"

    if cloud_bpm != "" and rendered_bpm != "" and cloud_bpm != rendered_bpm:
        if local_updated and cloud_updated and local_updated > cloud_updated:
            return "local_newer_than_cloud_fetch"
        if last_save and cloud_updated and last_save > cloud_updated:
            return "local_save_after_cloud_fetch"
        return "rendered_differs_from_cloud"

    if payload_bpm != "" and cloud_bpm != "" and payload_bpm != cloud_bpm:
        if trace.get("last_save_cloud"):
            return "local_payload_ahead_of_cloud_fetch"
        return "payload_differs_from_cloud_fetch"

    if local_updated and cloud_updated and local_updated > cloud_updated:
        return "local_newer_than_cloud_no_field_diff"

    return ""


def snapshot_backing_path_trace(st: Any) -> dict[str, Any]:
    """Refresh full Backing path trace for ?dev=1 (widget → canonical → payload → cloud)."""
    try:
        from music_persistence_trace import get_trace, update_trace

        session = st.session_state
        sync_id = str(session.get("_backing_trace_sync_id") or "")
        envelope_payload, cloud_payload = resolve_backing_trace_payloads(st, session)
        trace = collect_backing_persistence_trace(
            session,
            envelope_payload=envelope_payload,
            cloud_payload=cloud_payload,
            sync_id=sync_id,
            st=st,
        )
        update_trace(st, **trace)
        return trace
    except Exception:
        return {}


def collect_backing_persistence_trace(
    session: dict[str, Any],
    *,
    payload: dict[str, Any] | None = None,
    envelope_payload: dict[str, Any] | None = None,
    cloud_payload: dict[str, Any] | None = None,
    sync_id: str = "",
    st: Any | None = None,
) -> dict[str, Any]:
    sync_backing_session_keys_for_save(session)
    effective_sync_id = sync_id or str(session.get("_backing_trace_sync_id") or "")
    canonical = canonical_backing_filters(session) or {}
    envelope: dict[str, Any] = {}
    cloud_meta: dict[str, Any] = {}
    env_src = envelope_payload if envelope_payload is not None else payload
    cloud_src = cloud_payload if cloud_payload is not None else payload
    if isinstance(env_src, dict):
        ws = env_src.get("music_workspace_state")
        if isinstance(ws, dict) and isinstance(ws.get("backing_filters"), dict):
            envelope = _normalize_filters(ws["backing_filters"])
        elif isinstance(env_src.get(BACKING_STATE_KEY), dict):
            envelope = _normalize_filters(env_src[BACKING_STATE_KEY])
    if isinstance(cloud_src, dict):
        cloud_meta = _backing_filters_from_blob(cloud_src) or {}
    payload_bpm = session.get("_music_backing_payload_bpm")
    if payload_bpm in (None, "") and envelope.get("backing_track_bpm") not in (None, ""):
        payload_bpm = envelope.get("backing_track_bpm")
    rendered_trace = collect_rendered_backing_widget_trace(session, sync_id=effective_sync_id)
    _, rendered_bpm = _rendered_bpm_from_session(session, sync_id=effective_sync_id)
    widget_bpm = rendered_bpm if rendered_bpm is not None else _widget_bpm_from_session(session)
    trace = {
        **rendered_trace,
        "backing_widget_bpm": widget_bpm if widget_bpm is not None else "",
        "backing_widget_scope": session.get(BACKING_SCOPE_WIDGET_KEY, ""),
        "backing_widget_loops": session.get(BACKING_LOOPS_WIDGET_KEY, ""),
        "backing_widget_groove": session.get("backing_groove_style", ""),
        "backing_widget_quick_section": session.get(BACKING_QUICK_SECTION_WIDGET_KEY, ""),
        "backing_canonical_bpm": canonical.get("backing_track_bpm", ""),
        "backing_canonical_groove": canonical.get("backing_groove_style", ""),
        "backing_canonical_scope": canonical.get("backing_track_scope", ""),
        "backing_canonical_loops": canonical.get("backing_track_loops", ""),
        "backing_canonical_meter": canonical.get("backing_time_signature", ""),
        "backing_canonical_section": canonical.get("backing_track_single_section", ""),
        "backing_filters_bpm": envelope.get("backing_track_bpm", ""),
        "backing_filters_groove": envelope.get("backing_groove_style", ""),
        "backing_filters_scope": envelope.get("backing_track_scope", ""),
        "backing_filters_loops": envelope.get("backing_track_loops", ""),
        "backing_filters_meter": envelope.get("backing_time_signature", ""),
        "backing_filters_section": envelope.get("backing_track_single_section", ""),
        "cloud_payload_backing_bpm": cloud_meta.get("backing_track_bpm", ""),
        "cloud_payload_backing_groove": cloud_meta.get("backing_groove_style", ""),
        "cloud_payload_backing_scope": cloud_meta.get("backing_track_scope", ""),
        "cloud_payload_backing_loops": cloud_meta.get("backing_track_loops", ""),
        "cloud_payload_backing_meter": cloud_meta.get("backing_time_signature", ""),
        "cloud_payload_backing_section": cloud_meta.get("backing_track_single_section", ""),
        "backing_cloud_bpm": cloud_meta.get("backing_track_bpm", ""),
        "backing_cloud_scope": cloud_meta.get("backing_track_scope", ""),
        "backing_cloud_loops": cloud_meta.get("backing_track_loops", ""),
        "backing_cloud_groove": cloud_meta.get("backing_groove_style", ""),
        "backing_cloud_meter": cloud_meta.get("backing_time_signature", ""),
        "backing_cloud_section": cloud_meta.get("backing_track_single_section", ""),
        "backing_payload_bpm": payload_bpm if payload_bpm is not None else "",
        "backing_payload_scope": session.get("_music_backing_payload_scope", envelope.get("backing_track_scope", "")),
        "backing_payload_loops": session.get("_music_backing_payload_loops", envelope.get("backing_track_loops", "")),
        "backing_payload_groove": session.get("_music_backing_payload_groove", envelope.get("backing_groove_style", "")),
        "backing_restore_source": session.get("_backing_restore_source", ""),
        "backing_render_bind_reason": session.get("_backing_render_bind_reason", ""),
        "restored_backing_bpm": session.get("backing_track_bpm", ""),
        "restored_backing_groove": session.get("backing_groove_style", ""),
        "restored_backing_scope": session.get("backing_track_scope", ""),
        "restored_backing_loops": session.get("backing_track_loops", ""),
        "restored_backing_meter": session.get("backing_time_signature", ""),
        "restored_backing_section": session.get("backing_track_single_section", ""),
        "restored_backing_quick_section": session.get("backing_quick_section", ""),
        "restored_backing_meter_override": session.get("backing_time_signature_override", ""),
        "backing_dirty": is_backing_locally_dirty(session),
        "backing_user_edit_intent": bool(session.get(BACKING_USER_EDIT_INTENT_KEY)),
        "backing_user_edits_allowed": bool(session.get(BACKING_USER_EDITS_ALLOWED_KEY)),
        "backing_restore_applied": bool(session.get(BACKING_RESTORED_KEY)),
        "backing_restore_skipped": session.get("_backing_restore_skipped_reason"),
        "backing_last_write": canonical.get("last_write_reason")
        or (session.get(BACKING_STATE_KEY) or {}).get("last_write_reason"),
        "backing_overwrite_source": session.get("_backing_overwrite_source"),
        "raw_backing_track_scope": session.get(BACKING_SCOPE_WIDGET_KEY, ""),
        "raw_backing_track_loops": session.get(BACKING_LOOPS_WIDGET_KEY, ""),
        "raw_backing_quick_section": session.get(BACKING_QUICK_SECTION_WIDGET_KEY, ""),
        "raw_backing_time_signature": session.get(BACKING_METER_WIDGET_KEY, ""),
        "raw_backing_time_signature_override": session.get(BACKING_METER_OVERRIDE_WIDGET_KEY, ""),
        "raw_pending_backing_loops": session.get("_pending_backing_loops", ""),
        "backing_pending_sync": bool(session.get(BACKING_PENDING_SYNC_KEY)),
        "backing_filters_source": session.get("_backing_filters_source", ""),
        "cloud_payload_source": session.get("_backing_cloud_payload_source", ""),
        "force_save_reason": session.get("_suite_persist_last_save_reason", ""),
        "last_save_cloud": bool(session.get("_suite_persist_last_save_cloud")),
        "cloud_save_blocked_reason": (
            ""
            if session.get("_suite_persist_last_save_cloud")
            else str(session.get("_suite_autosave_cloud_blocked_reason") or "")
        ),
    }
    try:
        from music_workspace_cloud_save import collect_save_transaction_diagnostics

        tx = collect_save_transaction_diagnostics(session)
        for key in (
            "force_save_requested",
            "force_save_reason",
            "force_save_allowed",
            "force_save_block_reason",
            "workspace_dirty_before_save",
            "workspace_dirty_fields",
            "envelope_built",
            "envelope_revision_before",
            "envelope_revision_after",
            "cloud_write_attempted",
            "cloud_write_succeeded",
            "cloud_write_error",
            "cloud_readback_attempted",
            "cloud_readback_revision",
            "cloud_readback_matches",
            "dirty_cleared_after_confirmed_save",
        ):
            if key in tx and tx[key] is not None:
                trace[key] = tx[key]
        if tx.get("force_save_block_reason") and not trace.get("cloud_save_blocked_reason"):
            if not session.get("_suite_persist_last_save_cloud"):
                trace["cloud_save_blocked_reason"] = tx["force_save_block_reason"]
        for key in (
            "save_cloud_full_session_failure_stage",
            "save_cloud_full_session_exception",
            "supabase_response_status",
            "cloud_upsert_attempted",
            "cloud_upsert_succeeded",
        ):
            if key in tx and tx[key] not in (None, "", "(none)"):
                trace[key] = tx[key]
    except ImportError:
        pass
    if st is not None:
        trace.update(collect_backing_device_context(st, session))
    trace["backing_stale_cloud_hint"] = classify_backing_stale_cloud_hint(trace)
    trace["backing_sync_failure_class"] = classify_backing_sync_failure_class(trace)
    return trace


def render_backing_state_debug(st: Any, session: dict[str, Any]) -> None:
    envelope_payload, cloud_payload = resolve_backing_trace_payloads(st, session)
    trace = collect_backing_persistence_trace(
        session,
        envelope_payload=envelope_payload,
        cloud_payload=cloud_payload,
    )
    st.sidebar.caption(
        f"**backing canonical:** scope=`{trace['backing_canonical_scope']}` "
        f"sec=`{trace['backing_canonical_section']}` "
        f"loops=`{trace['backing_canonical_loops']}` "
        f"meter=`{trace['backing_canonical_meter']}` "
        f"bpm=`{trace['backing_canonical_bpm']}` "
        f"groove=`{trace['backing_canonical_groove']}` "
        f"dirty=`{trace['backing_dirty']}`"
    )
    st.sidebar.caption(
        f"**backing envelope:** scope=`{trace['backing_filters_scope']}` "
        f"sec=`{trace['backing_filters_section']}` "
        f"loops=`{trace['backing_filters_loops']}` "
        f"meter=`{trace['backing_filters_meter']}` "
        f"bpm=`{trace['backing_filters_bpm']}` "
        f"groove=`{trace['backing_filters_groove']}`"
    )
    st.sidebar.caption(
        f"**backing cloud:** scope=`{trace['cloud_payload_backing_scope']}` "
        f"sec=`{trace['cloud_payload_backing_section']}` "
        f"loops=`{trace['cloud_payload_backing_loops']}` "
        f"meter=`{trace['cloud_payload_backing_meter']}` "
        f"bpm=`{trace['cloud_payload_backing_bpm']}` "
        f"groove=`{trace['cloud_payload_backing_groove']}`"
    )
    st.sidebar.caption(
        f"**backing widget:** scope=`{trace['restored_backing_scope']}` "
        f"sec=`{trace['restored_backing_section']}` "
        f"loops=`{trace['restored_backing_loops']}` "
        f"meter=`{trace['restored_backing_meter']}` "
        f"ovr=`{trace['restored_backing_meter_override']}` "
        f"quick=`{trace['restored_backing_quick_section']}` "
        f"bpm=`{trace['restored_backing_bpm']}` "
        f"groove=`{trace['restored_backing_groove']}` "
        f"restore=`{trace['backing_restore_applied']}`"
    )
    if trace.get("backing_last_write"):
        st.sidebar.caption(f"**backing last_write:** `{trace['backing_last_write']}`")
    if trace.get("backing_restore_skipped"):
        st.sidebar.caption(f"**backing restore skipped:** `{trace['backing_restore_skipped']}`")
    if trace.get("backing_overwrite_source"):
        st.sidebar.caption(f"**backing overwrite:** `{trace['backing_overwrite_source']}`")
    st.sidebar.caption(
        f"**backing raw:** scope=`{trace.get('raw_backing_track_scope', '')}` "
        f"loops=`{trace.get('raw_backing_track_loops', '')}` "
        f"quick=`{trace.get('raw_backing_quick_section', '')}` "
        f"meter=`{trace.get('raw_backing_time_signature', '')}` "
        f"ovr=`{trace.get('raw_backing_time_signature_override', '')}` "
        f"pending_loops=`{trace.get('raw_pending_backing_loops', '')}` "
        f"sync=`{trace.get('backing_pending_sync', '')}`"
    )
    if trace.get("backing_filters_source"):
        st.sidebar.caption(f"**backing_filters_source:** `{trace['backing_filters_source']}`")
    if trace.get("cloud_payload_source"):
        st.sidebar.caption(f"**cloud_payload_source:** `{trace['cloud_payload_source']}`")
    if trace.get("force_save_reason"):
        st.sidebar.caption(f"**force_save_reason:** `{trace['force_save_reason']}`")
    st.sidebar.caption(f"**last_save_cloud:** `{trace.get('last_save_cloud', False)}`")
    if trace.get("cloud_save_blocked_reason"):
        st.sidebar.caption(f"**cloud_save_blocked:** `{trace['cloud_save_blocked_reason']}`")
    failure_class = trace.get("backing_sync_failure_class")
    if failure_class:
        st.sidebar.caption(f"**backing_sync_class:** `{failure_class}`")
