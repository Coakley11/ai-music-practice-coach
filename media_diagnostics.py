"""Developer diagnostics for media catalog sync (?dev=1)."""

from __future__ import annotations

import json
from typing import Any

from media_persistence import (
    MEDIA_PERSIST_VERSION,
    _load_cloud_catalog,
    _load_local_catalog,
    _local_path,
    _resolve_workspace_id,
    load_media_catalog,
)
from media_state import (
    is_multitrack_tombstone,
    is_recording_tombstone,
    normalize_multitrack_sessions,
    normalize_uploaded_recordings,
)


def _json_preview(value: Any, *, limit: int = 2400) -> str:
    try:
        text = json.dumps(value, indent=2, default=str)
    except Exception:
        text = str(value)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def collect_media_catalog_stats(*, st: Any | None = None) -> dict[str, Any]:
    """Snapshot counts for Upload / Multitrack diagnostics."""
    ws = _resolve_workspace_id(st=st)
    local_path = _local_path(st=st)
    local_raw = _load_local_catalog(st=st)
    cloud_raw, cloud_load_err = _load_cloud_catalog(st=st)
    merged = load_media_catalog(st=st)

    local_uploads = local_raw.get("uploaded_recordings") if isinstance(local_raw.get("uploaded_recordings"), list) else []
    local_mt = local_raw.get("multitrack_sessions") if isinstance(local_raw.get("multitrack_sessions"), list) else []
    cloud_uploads = cloud_raw.get("uploaded_recordings") if isinstance(cloud_raw.get("uploaded_recordings"), list) else []
    cloud_mt = cloud_raw.get("multitrack_sessions") if isinstance(cloud_raw.get("multitrack_sessions"), list) else []
    merged_uploads = merged.get("uploaded_recordings") if isinstance(merged.get("uploaded_recordings"), list) else []
    merged_mt = merged.get("multitrack_sessions") if isinstance(merged.get("multitrack_sessions"), list) else []

    visible_uploads = normalize_uploaded_recordings(merged_uploads)
    visible_mt = normalize_multitrack_sessions(merged_mt)

    tomb_rec = sum(1 for r in merged_uploads if isinstance(r, dict) and is_recording_tombstone(r))
    tomb_mt = sum(1 for r in merged_mt if isinstance(r, dict) and is_multitrack_tombstone(r))

    def _count_refs(rows: list[dict[str, Any]]) -> tuple[int, int]:
        metadata_only = 0
        storage_refs = 0
        for row in rows:
            if not isinstance(row, dict) or row.get("deleted"):
                continue
            if row.get("storage_ref") or row.get("local_path"):
                storage_refs += 1
            else:
                metadata_only += 1
            for track in row.get("tracks") or []:
                if not isinstance(track, dict):
                    continue
                if track.get("storage_ref") or track.get("local_path"):
                    storage_refs += 1
                elif not track.get("deleted"):
                    metadata_only += 1
            if row.get("mix_storage_ref") or row.get("mix_local_path"):
                storage_refs += 1
        return metadata_only, storage_refs

    meta_only, storage_ref_count = _count_refs(visible_uploads + visible_mt)

    ss = None
    if st is not None:
        try:
            ss = st.session_state if hasattr(st, "session_state") else st
        except Exception:
            ss = None

    trace = list((ss or {}).get("_media_persist_trace") or []) if isinstance(ss, dict) else []
    last_save = next((row for row in reversed(trace) if row.get("phase") == "save"), {})
    last_load = next((row for row in reversed(trace) if row.get("phase") == "load"), {})

    last_upload = visible_uploads[0] if visible_uploads else {}

    try:
        from studio_history_cloud import cloud_block_reason, cloud_enabled
    except ImportError:
        cloud_enabled = lambda: False  # type: ignore[misc, assignment]
        cloud_block_reason = lambda: None  # type: ignore[misc, assignment]

    return {
        "workspace_id": ws,
        "local_path": str(local_path),
        "local_catalog_upload_count": len(local_uploads),
        "local_catalog_multitrack_count": len(local_mt),
        "cloud_catalog_upload_count": len(cloud_uploads),
        "cloud_catalog_multitrack_count": len(cloud_mt),
        "merged_upload_count": len(merged_uploads),
        "merged_multitrack_count": len(merged_mt),
        "visible_upload_count": len(visible_uploads),
        "visible_multitrack_count": len(visible_mt),
        "tombstone_recording_count": tomb_rec,
        "tombstone_multitrack_count": tomb_mt,
        "tombstone_total": tomb_rec + tomb_mt,
        "metadata_only_count": meta_only,
        "storage_ref_count": storage_ref_count,
        "deleted_hidden": True,
        "cloud_load_error": cloud_load_err,
        "cloud_enabled": bool(cloud_enabled()),
        "cloud_block_reason": cloud_block_reason(),
        "last_save": last_save,
        "last_load": last_load,
        "last_upload_recording_id": last_upload.get("recording_id"),
        "last_upload_title": last_upload.get("filename") or last_upload.get("song"),
        "last_upload_song": last_upload.get("song"),
        "last_upload_instrument": last_upload.get("instrument"),
        "last_upload_date": last_upload.get("updated_at") or last_upload.get("created_at"),
        "session_last_save_ok": (ss or {}).get("_media_last_save_ok") if isinstance(ss, dict) else None,
        "session_last_save_error": (ss or {}).get("_media_last_save_error") if isinstance(ss, dict) else None,
    }


def render_media_diagnostics(st: Any, session_state: dict[str, Any], *, page: str = "analysis") -> None:
    """Render ?dev=1 media catalog diagnostics panel."""
    try:
        from music_persistence_trace import music_developer_mode
    except ImportError:
        return
    if not music_developer_mode(st):
        return

    try:
        from suite_deploy_probe import deploy_info
    except ImportError:
        deploy_info = lambda: {"commit": "unknown"}  # type: ignore[misc, assignment]

    deploy = deploy_info()
    stats = collect_media_catalog_stats(st=st)

    with st.expander(f"Media catalog diagnostics (?dev=1) — {page}", expanded=False):
        st.caption(
            f"Deploy commit `{deploy.get('commit', 'unknown')}` · "
            f"persist `{MEDIA_PERSIST_VERSION}`"
        )
        st.markdown("**Workspace / path**")
        st.text(f"workspace_id: {stats.get('workspace_id')}")
        st.text(f"media_catalog_local_path: {stats.get('local_path')}")

        st.markdown("**Catalog counts**")
        st.text(f"uploaded_recordings (visible): {stats.get('visible_upload_count')}")
        st.text(f"multitrack_sessions (visible): {stats.get('visible_multitrack_count')}")
        st.text(f"local catalog uploads: {stats.get('local_catalog_upload_count')}")
        st.text(f"local catalog multitracks: {stats.get('local_catalog_multitrack_count')}")
        st.text(f"cloud catalog uploads: {stats.get('cloud_catalog_upload_count')}")
        st.text(f"cloud catalog multitracks: {stats.get('cloud_catalog_multitrack_count')}")
        st.text(f"merged raw uploads: {stats.get('merged_upload_count')}")
        st.text(f"merged raw multitracks: {stats.get('merged_multitrack_count')}")
        st.text(f"tombstones (recordings): {stats.get('tombstone_recording_count')}")
        st.text(f"tombstones (multitracks): {stats.get('tombstone_multitrack_count')}")
        st.text(f"metadata-only entries: {stats.get('metadata_only_count')}")
        st.text(f"storage_ref entries: {stats.get('storage_ref_count')}")
        st.text(f"deleted items hidden from UI lists: {stats.get('deleted_hidden')}")

        st.markdown("**Last uploaded recording (visible)**")
        st.text(f"recording_id: {stats.get('last_upload_recording_id')}")
        st.text(f"title/filename: {stats.get('last_upload_title')}")
        st.text(f"song: {stats.get('last_upload_song')}")
        st.text(f"instrument: {stats.get('last_upload_instrument')}")
        st.text(f"date: {stats.get('last_upload_date')}")
        try:
            from media_storage import playback_status_label, recording_playback_status

            catalog = load_media_catalog(st=st)
            uploads = normalize_uploaded_recordings(catalog.get("uploaded_recordings") or [])
            if uploads:
                last_status = recording_playback_status(uploads[0], st=st)
                st.text(f"last upload playback: {playback_status_label(last_status)} ({last_status})")
        except ImportError:
            pass

        st.markdown("**Cloud / save**")
        st.text(f"cloud_enabled: {stats.get('cloud_enabled')}")
        st.text(f"cloud_block_reason: {stats.get('cloud_block_reason')}")
        st.text(f"cloud_load_error: {stats.get('cloud_load_error')}")
        st.text(f"last save overall_ok: {stats.get('last_save', {}).get('overall_ok')}")
        st.text(f"last save local_ok: {stats.get('last_save', {}).get('local_ok')}")
        st.text(f"last save cloud_ok: {stats.get('last_save', {}).get('cloud_ok')}")
        st.text(f"last save local_error: {stats.get('last_save', {}).get('local_error')}")
        st.text(f"last save cloud_error: {stats.get('last_save', {}).get('cloud_error')}")
        st.text(f"session _media_last_save_ok: {stats.get('session_last_save_ok')}")
        st.text(f"session _media_last_save_error: {stats.get('session_last_save_error')}")

        st.markdown("**Last load trace**")
        st.code(_json_preview(stats.get("last_load") or {"note": "no load trace yet"}), language="json")
        st.markdown("**Last save trace**")
        st.code(_json_preview(stats.get("last_save") or {"note": "no save trace yet"}), language="json")

        if st.button("Reload media catalog", key=f"media_diag_reload_{page}"):
            from media_upload_catalog import migrate_legacy_upload_history
            from media_multitrack_catalog import migrate_legacy_multitrack_history

            migrate_legacy_upload_history(st=st)
            migrate_legacy_multitrack_history(st=st)
            reloaded = load_media_catalog(st=st)
            up = len(normalize_uploaded_recordings(reloaded.get("uploaded_recordings") or []))
            mt = len(normalize_multitrack_sessions(reloaded.get("multitrack_sessions") or []))
            st.success(f"Reloaded catalog — {up} upload(s), {mt} multitrack session(s) visible.")
            st.rerun()

        if st.button("Force test upload catalog entry", key=f"media_diag_force_upload_{page}"):
            from media_persistence import add_uploaded_recording, update_uploaded_recording
            from media_storage import persist_recording_audio, recording_playback_status

            tiny_wav = (
                b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
                b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            )
            row = add_uploaded_recording(
                st,
                {
                    "filename": "dev_test_upload.wav",
                    "song": "Dev Test Song",
                    "instrument": "Tenor Saxophone",
                    "notes": "Forced test entry from ?dev=1 with playable audio blob",
                    "analysis_summary": {"coach_summary": "Dev test upload catalog entry", "ok": True},
                    "mime_type": "audio/wav",
                },
            )
            rid = str(row.get("recording_id") or "")
            store = persist_recording_audio(
                st,
                rid,
                tiny_wav,
                filename="dev_test_upload.wav",
                mime_type="audio/wav",
                workspace_id=str(row.get("workspace_id") or "daniel"),
            )
            if rid and (store.get("local_path") or store.get("storage_ref")):
                row = update_uploaded_recording(
                    st,
                    rid,
                    {
                        "local_path": store.get("local_path"),
                        "storage_ref": store.get("storage_ref"),
                        "playback_status": store.get("playback_status"),
                        "storage_error": store.get("storage_error") or "",
                    },
                )
            session_state["_last_catalog_recording_id"] = rid
            status = recording_playback_status(row or {}, st=st)
            st.success(f"Added test recording {rid} — playback status: {status}")
            st.rerun()
