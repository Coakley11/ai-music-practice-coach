"""?dev=1 widget ownership debug panel — shows live vs cloud vs last writer."""

from __future__ import annotations

from typing import Any

WIDGET_CONTROL_SPECS: tuple[dict[str, str], ...] = (
    {
        "label": "Music source",
        "session_key": "song_picker_active_source",
        "source_key": "song_picker_source_change_source",
        "cloud_path": ("session", "song_picker_active_source"),
    },
    {
        "label": "Active pick",
        "session_key": "active_catalog_pick_key",
        "source_key": "active_song_last_write_reason",
        "cloud_path": ("core", "pick_key"),
    },
    {
        "label": "Song title",
        "session_key": "active_song_title",
        "source_key": "active_song_last_write_reason",
        "cloud_path": ("core", "title"),
    },
    {
        "label": "Instrument",
        "session_key": "instrument",
        "source_key": "instrument_change_source",
        "cloud_path": ("core", "instrument"),
    },
    {
        "label": "Level",
        "session_key": "level",
        "source_key": "level_change_source",
        "cloud_path": ("core", "level"),
    },
    {
        "label": "Practice focus",
        "session_key": "focus",
        "source_key": "focus_change_source",
        "cloud_path": ("core", "focus"),
    },
    {
        "label": "Display key",
        "session_key": "display_key",
        "source_key": "display_key_change_source",
        "cloud_path": ("core", "display_key"),
    },
    {
        "label": "Backing BPM",
        "session_key": "backing_track_bpm",
        "source_key": "_backing_filters_source",
        "cloud_path": ("session", "backing_track_bpm"),
    },
    {
        "label": "MT layers",
        "session_key": "_mt_tracks_count_live",
        "source_key": "_multitrack_last_write_reason",
        "cloud_path": ("session", "mt_tracks"),
    },
)


def _cloud_value(payload: dict[str, Any], path: tuple[str, str]) -> str:
    root, key = path
    blob = payload.get(root) if isinstance(payload.get(root), dict) else {}
    val = blob.get(key) if isinstance(blob, dict) else None
    if key == "mt_tracks" and isinstance(val, dict):
        return str(sum(1 for v in val.values() if v))
    if key == "backing_track_bpm" and val is None:
        meta = payload.get("backing_track_state")
        if isinstance(meta, dict):
            val = meta.get("backing_track_bpm")
    return str(val or "").strip()


def _last_write_for_key(session: dict[str, Any], key: str) -> str:
    try:
        from music_state_writes import last_contested_write

        entry = last_contested_write(session, key)
        if isinstance(entry, dict):
            blocked = " BLOCKED" if entry.get("blocked") else ""
            return f"{entry.get('writer')}:{entry.get('origin')}{blocked}"
    except ImportError:
        pass
    return ""


def render_widget_control_debug(st: Any, session: dict[str, Any]) -> None:
    """Sidebar table: widget value vs cloud vs restore/dirty flags."""
    try:
        from active_song_state import ACTIVE_SONG_DIRTY_KEY, is_active_song_locally_dirty
        from music_restore_phase import (
            authoritative_restore_in_progress,
            music_restore_phase_complete,
            workspace_is_truly_empty,
        )
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY, custom_progression_is_active
    except ImportError:
        return

    payload = session.get("_suite_last_cloud_fetch_payload")
    if not isinstance(payload, dict):
        payload = {}

    mt = session.get("mt_tracks")
    if isinstance(mt, dict):
        session["_mt_tracks_count_live"] = sum(1 for v in mt.values() if v)
    else:
        session["_mt_tracks_count_live"] = 0

    mt_diag = session.get("_multitrack_persist_diag")
    if isinstance(mt_diag, dict):
        skipped = mt_diag.get("skipped_due_to_size") or []
        if skipped:
            st.sidebar.warning(f"Multitrack skipped_due_to_size: {skipped}")

    canonical_pick = ""
    meta = session.get("active_song_state")
    if isinstance(meta, dict):
        canonical_pick = str(meta.get("pick_key") or meta.get("active_catalog_pick_key") or "")

    st.sidebar.markdown("**Widget control debug**")
    st.sidebar.caption(
        f"restore_phase_done=`{music_restore_phase_complete(session)}` · "
        f"restore_in_progress=`{authoritative_restore_in_progress(session)}` · "
        f"workspace_empty=`{workspace_is_truly_empty(session)}` · "
        f"local_edit=`{is_active_song_locally_dirty(session)}` · "
        f"user_catalog=`{bool(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))}` · "
        f"custom_active=`{custom_progression_is_active(session)}`"
    )
    st.sidebar.caption(
        f"backing_autoplay=`{bool(session.get('_backing_autoplay'))}` · "
        f"transport=`{session.get('backing_transport_status')}` · "
        f"sync_attempted=`{bool(session.get('_suite_workspace_sync_attempted'))}` · "
        f"canonical_pick=`{canonical_pick}`"
    )

    rows: list[str] = []
    for spec in WIDGET_CONTROL_SPECS:
        key = spec["session_key"]
        live = session.get(key)
        if key == "_mt_tracks_count_live":
            live = session.get("_mt_tracks_count_live")
        if key == "active_song_title":
            sel = session.get("selected_song")
            if isinstance(sel, dict) and sel.get("title"):
                live = sel.get("title")
        source = str(session.get(spec["source_key"]) or session.get("global_control_overwrite_source") or "")
        write_trace = _last_write_for_key(session, key)
        cloud = _cloud_value(payload, tuple(spec["cloud_path"])) if payload else ""
        canonical = ""
        if isinstance(meta, dict) and spec["session_key"] in {"instrument", "level", "focus", "display_key"}:
            canonical = str(meta.get(spec["session_key"]) or "")
        flag = ""
        if authoritative_restore_in_progress(session) and cloud and str(live or "") != cloud:
            flag = " ⚠ restore overwriting"
        elif music_restore_phase_complete(session) and canonical and str(live or "") != canonical and source != "sidebar_on_change":
            flag = " ⚠ canonical drift"
        rows.append(
            f"**{spec['label']}** (`{key}`) live=`{live}` cloud=`{cloud}` "
            f"canonical=`{canonical}` src=`{source}` trace=`{write_trace}`{flag}"
        )
    for row in rows:
        st.sidebar.caption(row)

    trace = session.get("_music_state_write_trace")
    if isinstance(trace, list) and trace:
        last = trace[-3:]
        st.sidebar.caption(f"state_writes_tail: `{last}`")

    trace2 = session.get("_global_control_widget_trace")
    if isinstance(trace2, dict) and trace2:
        st.sidebar.caption(f"last_widget_trace: `{trace2}`")
