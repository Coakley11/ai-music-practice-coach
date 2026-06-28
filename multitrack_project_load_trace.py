"""Explicit Project Library load debug trace (?dev=1 + Project Library panel)."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

TRACE_KEY = "_mt_project_load_trace"
TRACE_HISTORY_KEY = "_mt_project_load_trace_history"
MAX_HISTORY = 8

_COMPARE_FIELDS = (
    ("title", "mt_history_save_name", "project title"),
    ("notes", "mt_history_save_notes", "notes"),
    ("song", "active_song_title", "song"),
    ("backing_volume", "mt_backing_volume", "backing volume"),
    ("transport_loop_backing", "mt_loop_backing", "loop section"),
    ("transport_metronome", "mt_metronome_playback", "click monitor"),
    ("transport_use_backing_monitor", "mt_use_backing_monitor", "hear backing monitor"),
    ("backing_storage_ref", "_mt_session_backing_storage_ref", "backing storage ref"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _trace(session_state: dict[str, Any]) -> dict[str, Any]:
    raw = session_state.get(TRACE_KEY)
    if not isinstance(raw, dict):
        raw = {}
        session_state[TRACE_KEY] = raw
    return raw


def _push_history(session_state: dict[str, Any], entry: dict[str, Any]) -> None:
    hist = session_state.get(TRACE_HISTORY_KEY)
    if not isinstance(hist, list):
        hist = []
    hist.insert(0, copy.deepcopy(entry))
    session_state[TRACE_HISTORY_KEY] = hist[:MAX_HISTORY]


def begin_project_load_trace(
    session_state: dict[str, Any],
    *,
    clicked_project_id: str,
    clicked_project_title: str = "",
    clicked_project_updated_at: str = "",
    payload_multitrack_id: str = "",
) -> None:
    """Start a new trace for one Load Project click."""
    entry: dict[str, Any] = {
        "started_at": _utc_now(),
        "clicked": {
            "clicked_project_id": str(clicked_project_id or ""),
            "clicked_project_title": str(clicked_project_title or ""),
            "clicked_project_updated_at": str(clicked_project_updated_at or ""),
            "payload_multitrack_id": str(payload_multitrack_id or ""),
            "click_id_matches_payload": str(clicked_project_id or "") == str(payload_multitrack_id or ""),
        },
        "catalog_row": {},
        "session_after_load": {},
        "session_after_render": {},
        "load_stages": [],
        "restore_events": [],
        "snapshot": {},
        "verification": {},
        "ok": None,
        "message": "",
    }
    session_state[TRACE_KEY] = entry
    record_load_stage(session_state, "click", clicked_id=clicked_project_id)


def record_load_stage(session_state: dict[str, Any], stage: str, **details: Any) -> None:
    trace = _trace(session_state)
    stages = trace.setdefault("load_stages", [])
    if not isinstance(stages, list):
        stages = []
        trace["load_stages"] = stages
    stages.append({"at": _utc_now(), "stage": stage, **details})


def record_restore_event(session_state: dict[str, Any], event: str, **details: Any) -> None:
    trace = _trace(session_state)
    events = trace.setdefault("restore_events", [])
    if not isinstance(events, list):
        events = []
        trace["restore_events"] = events
    events.append({"at": _utc_now(), "event": event, **details})


def _catalog_row_summary(row: dict[str, Any]) -> dict[str, Any]:
    tracks = row.get("tracks") if isinstance(row.get("tracks"), list) else []
    track_ids: list[str] = []
    layer_names: list[str] = []
    for track in tracks:
        if not isinstance(track, dict) or track.get("deleted"):
            continue
        tid = str(track.get("track_id") or "")
        if tid:
            track_ids.append(tid)
        slot = str(track.get("slot") or "")
        name = str(track.get("name") or slot)
        if slot or name:
            layer_names.append(f"{slot}:{name}" if slot else name)
    controls = row.get("track_controls") if isinstance(row.get("track_controls"), dict) else {}
    return {
        "loaded_project_id": str(row.get("multitrack_id") or ""),
        "loaded_project_title": str(row.get("title") or ""),
        "loaded_project_song": str(row.get("song") or ""),
        "loaded_project_notes": str(row.get("notes") or ""),
        "loaded_project_updated_at": str(row.get("updated_at") or row.get("created_at") or ""),
        "loaded_backing_storage_ref": str(row.get("backing_storage_ref") or ""),
        "loaded_backing_local_path": str(row.get("backing_local_path") or ""),
        "loaded_track_count": len(track_ids),
        "loaded_track_ids": track_ids,
        "loaded_layer_names": layer_names,
        "loaded_mixer_summary": copy.deepcopy(controls),
        "loaded_transport_summary": {
            "transport_loop_backing": row.get("transport_loop_backing"),
            "transport_metronome": row.get("transport_metronome"),
            "transport_use_backing_monitor": row.get("transport_use_backing_monitor"),
            "transport_include_backing_in_mix": row.get("transport_include_backing_in_mix"),
        },
        "loaded_backing_volume": row.get("backing_volume"),
        "loaded_bpm": row.get("bpm"),
        "loaded_backing_meter": row.get("backing_meter"),
    }


def _session_summary(session_state: dict[str, Any]) -> dict[str, Any]:
    mt = session_state.get("mt_tracks") if isinstance(session_state.get("mt_tracks"), dict) else {}
    track_slots = [slot for slot, raw in mt.items() if raw]
    controls = session_state.get("mt_track_controls") if isinstance(session_state.get("mt_track_controls"), dict) else {}
    layer_names: list[str] = []
    for slot in track_slots:
        layer_names.append(f"{slot}:{session_state.get(f'mt_name_{slot}', slot)}")
    try:
        from media_multitrack_catalog import loaded_multitrack_project_banner

        banner = loaded_multitrack_project_banner(session_state)
    except ImportError:
        banner = ""
    backing_bytes = 0
    raw_backing = session_state.get("multitrack_backing_music_wav")
    if isinstance(raw_backing, (bytes, bytearray)):
        backing_bytes = len(raw_backing)
    return {
        "active_catalog_multitrack_id": str(
            session_state.get("multitrack_catalog_active_id")
            or session_state.get("_last_catalog_multitrack_id")
            or ""
        ),
        "loaded_project_banner_title": banner,
        "session_song": str(session_state.get("active_song_title") or ""),
        "session_notes": str(session_state.get("mt_history_save_notes") or ""),
        "session_backing_storage_ref": str(session_state.get("_mt_session_backing_storage_ref") or ""),
        "session_backing_project_id": str(session_state.get("_mt_loaded_backing_project_id") or ""),
        "session_track_slots_with_audio": track_slots,
        "session_layer_names": layer_names,
        "session_mixer_values": copy.deepcopy(controls),
        "session_loop": session_state.get("mt_loop_backing"),
        "session_click_monitor": session_state.get("mt_metronome_playback"),
        "session_hear_backing_monitor": session_state.get("mt_use_backing_monitor"),
        "session_backing_volume": session_state.get("mt_backing_volume"),
        "session_bpm": session_state.get("multitrack_bpm"),
        "session_meter": session_state.get("mt_time_signature"),
        "session_backing_bytes": backing_bytes,
        "active_song_bpm": session_state.get("bpm"),
    }


def finalize_project_load_trace(
    session_state: dict[str, Any],
    *,
    catalog_row: dict[str, Any] | None,
    ok: bool,
    message: str,
    snapshot_flushed: bool = False,
    snapshot_restore_skipped: bool = False,
    layer_restore_skipped: bool = False,
) -> None:
    trace = _trace(session_state)
    trace["finished_at"] = _utc_now()
    trace["ok"] = ok
    trace["message"] = str(message or "")
    if isinstance(catalog_row, dict):
        try:
            from media_state import migrate_multitrack_session

            migrated = migrate_multitrack_session(catalog_row)
        except ImportError:
            migrated = catalog_row
        trace["catalog_row"] = _catalog_row_summary(migrated)
        session_state["_mt_session_backing_storage_ref"] = str(migrated.get("backing_storage_ref") or "")
    trace["session_after_load"] = _session_summary(session_state)
    trace["snapshot"] = {
        "snapshot_flushed_after_load": snapshot_flushed,
        "snapshot_restore_skipped_on_load": snapshot_restore_skipped,
        "layer_restore_skipped_on_load": layer_restore_skipped,
        "skip_snapshot_restore_remaining": session_state.get("_mt_skip_snapshot_restore_count"),
    }
    try:
        from media_multitrack_catalog import _record_multitrack_catalog_load_diag  # type: ignore[attr-defined]

        _record_multitrack_catalog_load_diag(
            session_state,
            requested_id=str((trace.get("clicked") or {}).get("clicked_project_id") or ""),
            loaded_row=catalog_row,
            ok=ok,
            message=message,
            snapshot_flushed=snapshot_flushed,
        )
    except ImportError:
        pass
    _push_history(session_state, trace)


def capture_post_render_session_trace(session_state: dict[str, Any], *, source: str = "multitrack_page") -> None:
    """Record session state after multitrack widgets render (detect post-load overwrites)."""
    trace = session_state.get(TRACE_KEY)
    if not isinstance(trace, dict) or not trace.get("started_at"):
        return
    trace["session_after_render"] = _session_summary(session_state)
    trace["post_render_source"] = source
    trace["post_render_at"] = _utc_now()
    record_restore_event(session_state, "post_render_capture", source=source)


def _catalog_value(row: dict[str, Any], field: str) -> Any:
    if field == "transport_loop_backing":
        return row.get("transport_loop_backing")
    if field == "transport_metronome":
        return row.get("transport_metronome")
    if field == "transport_use_backing_monitor":
        return row.get("transport_use_backing_monitor")
    if field == "backing_storage_ref":
        return str(row.get("backing_storage_ref") or "")
    return row.get(field)


def _session_value(session_state: dict[str, Any], session_key: str) -> Any:
    if session_key == "_mt_session_backing_storage_ref":
        return str(session_state.get("_mt_session_backing_storage_ref") or "")
    return session_state.get(session_key)


def verify_loaded_project_matches_catalog(
    session_state: dict[str, Any],
    *,
    st: Any | None = None,
) -> dict[str, Any]:
    """Compare active catalog row to live session; return field-by-field mismatches."""
    active_id = str(
        session_state.get("multitrack_catalog_active_id")
        or session_state.get("_last_catalog_multitrack_id")
        or ""
    ).strip()
    result: dict[str, Any] = {
        "at": _utc_now(),
        "active_catalog_multitrack_id": active_id,
        "match": True,
        "mismatches": [],
        "catalog_missing": False,
    }
    if not active_id:
        result["match"] = False
        result["error"] = "no_active_catalog_project"
        trace = _trace(session_state)
        trace["verification"] = result
        return result
    try:
        from media_persistence import load_media_catalog
        from media_state import migrate_multitrack_session, normalize_multitrack_sessions

        catalog = load_media_catalog(st=st)
        rows = normalize_multitrack_sessions(
            catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
        )
        row = next((r for r in rows if str(r.get("multitrack_id") or "") == active_id), None)
    except ImportError:
        row = None
    if not isinstance(row, dict):
        result["match"] = False
        result["catalog_missing"] = True
        result["error"] = "catalog_row_not_found"
        trace = _trace(session_state)
        trace["verification"] = result
        return result
    migrated = migrate_multitrack_session(row)
    result["catalog_row"] = _catalog_row_summary(migrated)
    result["session"] = _session_summary(session_state)
    mismatches: list[dict[str, Any]] = []
    for catalog_field, session_key, label in _COMPARE_FIELDS:
        expected = _catalog_value(migrated, catalog_field)
        actual = _session_value(session_state, session_key)
        if catalog_field == "backing_volume":
            try:
                expected = round(float(expected), 2) if expected is not None else None
                actual = round(float(actual), 2) if actual is not None else None
            except (TypeError, ValueError):
                pass
        if expected is None and actual in (None, "", False):
            continue
        if expected != actual:
            mismatches.append(
                {
                    "field": label,
                    "catalog_field": catalog_field,
                    "session_key": session_key,
                    "expected": expected,
                    "actual": actual,
                }
            )
    cat_controls = migrated.get("track_controls") if isinstance(migrated.get("track_controls"), dict) else {}
    sess_controls = session_state.get("mt_track_controls") if isinstance(session_state.get("mt_track_controls"), dict) else {}
    if cat_controls != sess_controls:
        mismatches.append(
            {
                "field": "track_controls",
                "catalog_field": "track_controls",
                "session_key": "mt_track_controls",
                "expected": copy.deepcopy(cat_controls),
                "actual": copy.deepcopy(sess_controls),
            }
        )
    result["mismatches"] = mismatches
    result["match"] = not mismatches
    trace = _trace(session_state)
    trace["verification"] = result
    record_load_stage(session_state, "verify", match=result["match"], mismatch_count=len(mismatches))
    return result


def _developer_mode(st: Any | None) -> bool:
    try:
        from music_persistence_trace import music_developer_mode

        return bool(music_developer_mode(st))
    except ImportError:
        return False


def render_project_load_debug_panel(st_obj: Any, session_state: dict[str, Any]) -> None:
    """Show last Load Project trace + verify action near Project Library."""
    if not _developer_mode(st_obj):
        return
    trace = session_state.get(TRACE_KEY) if isinstance(session_state.get(TRACE_KEY), dict) else {}
    with st_obj.expander("Project Load Debug Trace (?dev=1)", expanded=False):
        st_obj.caption("Last Load Project click — compare clicked row, catalog row, session, and post-render state.")
        clicked = trace.get("clicked") if isinstance(trace.get("clicked"), dict) else {}
        st_obj.markdown("**1. Clicked row**")
        st_obj.text(f"clicked_project_id: {clicked.get('clicked_project_id')}")
        st_obj.text(f"clicked_project_title: {clicked.get('clicked_project_title')}")
        st_obj.text(f"clicked_project_updated_at: {clicked.get('clicked_project_updated_at')}")
        st_obj.text(f"payload_multitrack_id: {clicked.get('payload_multitrack_id')}")
        st_obj.text(f"click_id_matches_payload: {clicked.get('click_id_matches_payload')}")

        catalog = trace.get("catalog_row") if isinstance(trace.get("catalog_row"), dict) else {}
        st_obj.markdown("**2. Catalog row loaded**")
        for key in (
            "loaded_project_id",
            "loaded_project_title",
            "loaded_project_song",
            "loaded_project_notes",
            "loaded_backing_storage_ref",
            "loaded_track_count",
            "loaded_track_ids",
            "loaded_layer_names",
            "loaded_backing_volume",
            "loaded_bpm",
        ):
            st_obj.text(f"{key}: {catalog.get(key)}")
        st_obj.text(f"loaded_mixer_summary: {catalog.get('loaded_mixer_summary')}")
        st_obj.text(f"loaded_transport_summary: {catalog.get('loaded_transport_summary')}")

        after_load = trace.get("session_after_load") if isinstance(trace.get("session_after_load"), dict) else {}
        st_obj.markdown("**3. Session after load**")
        for key, val in after_load.items():
            st_obj.text(f"{key}: {val}")

        after_render = trace.get("session_after_render") if isinstance(trace.get("session_after_render"), dict) else {}
        st_obj.markdown("**4. Session after page render**")
        if after_render:
            for key, val in after_render.items():
                st_obj.text(f"{key}: {val}")
        else:
            st_obj.caption("Not captured yet — scroll the multitrack page or interact once.")

        snap = trace.get("snapshot") if isinstance(trace.get("snapshot"), dict) else {}
        restore_events = trace.get("restore_events") if isinstance(trace.get("restore_events"), list) else []
        st_obj.markdown("**5. Snapshot / restore**")
        st_obj.text(f"snapshot_flushed_after_load: {snap.get('snapshot_flushed_after_load')}")
        st_obj.text(f"snapshot_restore_skipped_on_load: {snap.get('snapshot_restore_skipped_on_load')}")
        st_obj.text(f"layer_restore_skipped_on_load: {snap.get('layer_restore_skipped_on_load')}")
        st_obj.text(f"skip_snapshot_restore_remaining: {snap.get('skip_snapshot_restore_remaining')}")
        if restore_events:
            st_obj.text("restore_events:")
            for ev in restore_events[-12:]:
                st_obj.text(f"  · {ev.get('event')} {ev}")
        else:
            st_obj.caption("No restore events recorded yet.")

        stages = trace.get("load_stages") if isinstance(trace.get("load_stages"), list) else []
        if stages:
            st_obj.markdown("**Load stages**")
            for stage in stages:
                st_obj.text(f"  · {stage.get('stage')} @ {stage.get('at')} { {k: v for k, v in stage.items() if k not in ('stage', 'at')} }")

        st_obj.text(f"load ok: {trace.get('ok')} · message: {trace.get('message')}")

        if st_obj.button(
            "Verify loaded project matches selected catalog row",
            key="mt_verify_loaded_project",
            use_container_width=True,
        ):
            result = verify_loaded_project_matches_catalog(session_state, st=st_obj)
            if result.get("match"):
                st_obj.success("Session matches the active catalog row.")
            else:
                st_obj.error(f"{len(result.get('mismatches') or [])} mismatch(es) found.")
                for row in result.get("mismatches") or []:
                    st_obj.warning(
                        f"{row.get('field')}: expected `{row.get('expected')}` · session `{row.get('actual')}`"
                    )
