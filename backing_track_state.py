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

BACKING_WIDGETS_SEEDED_KEY = "_backing_durable_widgets_seeded"

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
    "mark_backing_local_edit",
    "mark_backing_pending_sync",
    "normalize_backing_groove",
    "normalize_backing_scope",
    "backing_canonical_playback_seed",
    "backing_canonical_meter_seed",
    "backing_filters_for_workspace_envelope",
    "classify_backing_sync_failure_class",
    "bind_backing_rendered_widgets_from_canonical",
    "collect_rendered_backing_widget_trace",
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


def _should_seed_widgets_from_canonical(session: dict[str, Any]) -> bool:
    """True when canonical may hydrate widget keys (restore / first load), not mid-edit reruns."""
    if is_backing_locally_dirty(session):
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
    """Align scope, single section, and Step-2 quick section from live widget keys."""
    quick = str(session.get(BACKING_QUICK_SECTION_WIDGET_KEY) or "").strip()
    scope = normalize_backing_scope(session.get(BACKING_SCOPE_WIDGET_KEY))
    single = str(session.get(BACKING_SINGLE_SECTION_WIDGET_KEY) or "").strip()
    if quick and quick != "Full song":
        if scope == "Full song":
            scope = "Single section"
            single = quick
    elif scope == "Single section" and single:
        quick = single
    elif scope == "Full song" and not quick:
        quick = "Full song"
    return {
        "backing_track_scope": scope,
        "backing_track_single_section": single,
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
        "backing_rendered_scope": session.get(BACKING_SCOPE_WIDGET_KEY, ""),
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
    if is_backing_locally_dirty(session) or session.get(BACKING_PENDING_SYNC_KEY):
        return collect_rendered_backing_widget_trace(session, sync_id=sync_id)

    canonical = canonical_backing_filters(session)
    if canonical is None:
        return collect_rendered_backing_widget_trace(session, sync_id=sync_id)

    should_bind = (
        session.get(BACKING_RESTORED_KEY)
        or not session.get(BACKING_WIDGETS_SEEDED_KEY)
        or _rendered_differs_from_canonical(session, sync_id, canonical)
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
            "backing_track_multi_sections": session.get(BACKING_MULTI_SECTIONS_WIDGET_KEY),
            "backing_track_loops": loops_val,
            "backing_track_bpm": bpm_val,
            "backing_groove_style": session.get("backing_groove_style"),
            "backing_volume": volume_val,
            "backing_time_signature": meter_val,
            "backing_time_signature_override": bool(
                session.get(BACKING_METER_OVERRIDE_WIDGET_KEY, False)
            ),
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


def has_restored_backing_canonical(session: dict[str, Any]) -> bool:
    """True when a durable backing blob exists (cloud restore or prior edit)."""
    return canonical_backing_filters(session) is not None


def backing_canonical_playback_seed(session: dict[str, Any]) -> tuple[int | None, str | None]:
    """BPM + groove from canonical blob for playback-default seeding on hard refresh."""
    if is_backing_locally_dirty(session):
        return None, None
    canonical = canonical_backing_filters(session) or {}
    bpm = normalize_backing_bpm(canonical.get("backing_track_bpm"))
    groove = normalize_backing_groove(canonical.get("backing_groove_style"))
    return bpm, groove or None


def backing_canonical_meter_seed(session: dict[str, Any]) -> tuple[str | None, bool | None]:
    """Meter + override flag from canonical blob for hard-refresh meter sync."""
    if is_backing_locally_dirty(session):
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


def _gathered_looks_like_song_defaults(filters: dict[str, Any]) -> bool:
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
        if (
            is_backing_locally_dirty(session)
            or session.get(BACKING_PENDING_SYNC_KEY)
            or normalized != normalize_backing_groove(default_groove)
        ):
            session["backing_groove_style"] = normalized
        return normalized
    fallback = normalize_backing_groove(default_groove) or "Auto"
    session.setdefault("backing_groove_style", fallback)
    return str(session["backing_groove_style"])


def prepare_backing_bpm_for_widget(session: dict[str, Any], *, default_bpm: int = 100) -> int:
    if (
        not is_backing_locally_dirty(session)
        and not session.get(BACKING_PENDING_SYNC_KEY)
        and _should_seed_widgets_from_canonical(session)
    ):
        canonical = canonical_backing_filters(session) or {}
        canon_bpm = normalize_backing_bpm(canonical.get("backing_track_bpm"))
        if canon_bpm is not None:
            session["backing_track_bpm"] = int(canon_bpm)
            return int(canon_bpm)
    bpm = normalize_backing_bpm(session.get("backing_track_bpm"), default=default_bpm)
    if bpm is not None and (
        is_backing_locally_dirty(session)
        or session.get(BACKING_PENDING_SYNC_KEY)
        or _should_seed_widgets_from_canonical(session)
    ):
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
    _apply_filters_to_session_keys(session, normalized)
    if local_edit:
        mark_backing_local_edit(session)
    session.pop(BACKING_PENDING_SYNC_KEY, None)
    return normalized


def prepare_backing_page(session: dict[str, Any]) -> dict[str, Any]:
    """Reconcile Backing canonical blob before page widgets render."""
    if is_backing_locally_dirty(session) or session.get(BACKING_PENDING_SYNC_KEY):
        gathered = gather_backing_filters(session)
        return write_canonical_backing_state(
            session,
            gathered,
            reason="local_edit_preserve",
            local_edit=True,
        )
    gathered = gather_backing_filters(session)
    canonical = canonical_backing_filters(session)
    if canonical is not None and _filters_differ(canonical, gathered):
        if _should_seed_widgets_from_canonical(session) or (
            _filters_have_content(canonical) and _gathered_looks_like_song_defaults(gathered)
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
    return write_canonical_backing_state(session, filters, reason=reason, local_edit=True)


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
    if is_backing_locally_dirty(session):
        session["_backing_restore_skipped_reason"] = "local_dirty"
        session["_backing_restore_source"] = "skipped_local_dirty"
        return False
    filters = _backing_filters_from_blob(state)
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
        return "flush_save_not_triggered"

    if widget_bpm != "" and not last_save_cloud and force_reason != "backing_edit":
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
        "cloud_save_blocked_reason": session.get("_suite_autosave_cloud_blocked_reason", ""),
    }
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
