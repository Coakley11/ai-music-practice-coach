"""Streamlit UI for Upload + Multitrack cloud history libraries."""

from __future__ import annotations

from typing import Any, Callable

from multitrack_history import (
    FLASH_KEY as MT_FLASH_KEY,
    default_project_name,
    queue_multitrack_history_load,
)
from media_multitrack_catalog import (
    apply_catalog_multitrack_to_session,
    catalog_multitrack_row_summary,
    delete_catalog_multitrack_session,
    list_catalog_multitrack_sessions,
    save_multitrack_session_with_notes,
)
from studio_history_cloud import (
    cloud_block_reason,
    cloud_enabled,
    format_saved_at,
    widget_key_suffix,
)
from upload_history import (
    FLASH_KEY as UPLOAD_FLASH_KEY,
    default_upload_title,
)
from media_upload_catalog import (
    apply_catalog_recording_to_session,
    catalog_upload_row_summary,
    delete_catalog_upload_recording,
    list_catalog_upload_recordings,
    save_upload_recording_with_notes,
)


def _format_save_error(err: str) -> str:
    code = str(err or "").strip()
    mapping = {
        "cloud_disabled": "Cloud storage is disabled.",
        "no_analysis_result": "No analysis result in session — analyze a take first.",
        "analysis_failed": "The last analysis failed — run a successful analysis before saving.",
        "analysis_not_serializable": "Could not serialize the analysis result for cloud save.",
        "missing_title": "Title is required.",
        "missing_item_key": "Internal save key missing.",
        "cloud_write_skipped": "Cloud rejected the save (missing title, key, or app scope).",
        "no_layers_or_mix": "Add at least one layer or create a mix before saving.",
        "build_failed": "Could not build the save payload.",
    }
    return mapping.get(code, code or "Unknown save error.")


def _after_history_load(session_state: dict[str, Any], st_obj: Any, *, page: str) -> None:
    try:
        if page == "analysis":
            from analysis_session_persistence import save_analysis_session
            from music_persistent_state import force_save_music_state

            save_analysis_session(session_state, st=st_obj)
            force_save_music_state(st_obj, reason="history_load")
        elif page == "multitrack":
            from music_persistent_state import force_save_music_state

            force_save_music_state(st_obj, reason="history_load")
    except Exception:
        pass


def _render_history_list(
    st_obj: Any,
    *,
    item_type: str,
    rows: list[dict[str, Any]],
    list_error: str | None,
    summary_fn: Callable[[dict[str, Any]], str],
    on_load: Callable[[dict[str, Any]], tuple[bool, str]],
    on_delete: Callable[[str], tuple[bool, str]],
    key_prefix: str,
    active_item_key: str = "",
) -> None:
    if list_error:
        st_obj.error(f"Could not load history: {list_error}")
    if not rows:
        st_obj.caption("No saved items yet.")
        return

    st_obj.markdown(
        '<style>'
        f"div[data-testid='stVerticalBlock']:has(.{key_prefix}-hist-row) "
        "div[data-testid='column'] {padding-top:0;padding-bottom:0;}"
        f".{key_prefix}-hist-row .stButton > button "
        "{padding:0.18rem 0.45rem;font-size:0.82rem;line-height:1.25;text-align:left;}"
        f".{key_prefix}-hist-del .stButton > button "
        "{padding:0.12rem 0.35rem;min-width:2rem;}"
        "</style>",
        unsafe_allow_html=True,
    )

    for row in rows:
        item_key = str(row.get("item_key") or "")
        if not item_key:
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        saved_at = format_saved_at(str(payload.get("saved_at") or row.get("updated_at") or ""))
        title = str(row.get("title") or payload.get("title") or payload.get("project_name") or "Saved item")
        summary = summary_fn(row)
        suffix = widget_key_suffix(item_key)
        is_active = bool(active_item_key and item_key == active_item_key)
        row_label = f"{title}  ·  {saved_at}"
        if summary:
            row_label = f"{row_label}  ·  {summary}"
        if is_active:
            row_label = f"▸ {row_label}"

        row_cols = st_obj.columns([12, 1])
        with row_cols[0]:
            st_obj.markdown(f'<div class="{key_prefix}-hist-row"></div>', unsafe_allow_html=True)
            if is_active:
                st_obj.caption(row_label)
            elif st_obj.button(
                row_label,
                key=f"{key_prefix}_open_{suffix}",
                use_container_width=True,
            ):
                ok, msg = on_load(payload)
                if ok:
                    st_obj.session_state[f"{key_prefix}_flash"] = msg
                    st_obj.session_state[f"{key_prefix}_active_item"] = item_key
                    st_obj.rerun()
                else:
                    st_obj.error(msg)
        with row_cols[1]:
            st_obj.markdown(f'<div class="{key_prefix}-hist-del"></div>', unsafe_allow_html=True)
            if st_obj.button("✕", key=f"{key_prefix}_del_{suffix}", help="Delete"):
                ok, err = on_delete(item_key)
                if ok:
                    st_obj.session_state[f"{key_prefix}_flash"] = "Deleted from history."
                    if st_obj.session_state.get(f"{key_prefix}_active_item") == item_key:
                        st_obj.session_state.pop(f"{key_prefix}_active_item", None)
                    st_obj.rerun()
                else:
                    st_obj.error(_format_save_error(err))


def render_upload_history_panel(st_obj: Any) -> None:
    ss = st_obj.session_state
    raw_result = ss.get("last_analysis_result")
    has_result = isinstance(raw_result, dict) and bool(raw_result) and raw_result.get("ok") is not False

    flash = ss.pop(UPLOAD_FLASH_KEY, None) or ss.pop("upload_hist_flash", None)

    with st_obj.expander("Upload History", expanded=False):
        if flash:
            st_obj.success(str(flash))
        if not cloud_enabled():
            st_obj.caption(
                cloud_block_reason()
                or "Cloud storage is disabled — saved uploads use local media catalog on this device."
            )

        if has_result:
            st_obj.markdown("##### Save current analysis")
            title_default = default_upload_title(ss)
            if "upload_history_save_title" not in ss:
                ss["upload_history_save_title"] = title_default
            title = st_obj.text_input(
                "Title / name",
                key="upload_history_save_title",
            )
            notes = st_obj.text_area(
                "Notes (optional)",
                key="upload_history_save_notes",
                height=68,
                placeholder="Rehearsal take, gig prep, etc.",
            )
            if st_obj.button("Save to History", type="primary", key="upload_history_save_btn", use_container_width=True):
                ok, item_key, err = save_upload_recording_with_notes(ss, title=title, notes=notes, st=st_obj)
                if ok:
                    ss[UPLOAD_FLASH_KEY] = f"Saved to media catalog ({item_key})."
                    ss["upload_hist_active_item"] = item_key
                    ss["upload_catalog_active_recording_id"] = item_key
                    st_obj.rerun()
                else:
                    st_obj.error(_format_save_error(err))

        st_obj.markdown("##### Saved analyses")

        rows, list_err = list_catalog_upload_recordings(st=st_obj)
        active_key = str(
            ss.get("upload_catalog_active_recording_id")
            or ss.get("upload_hist_active_item")
            or ss.get("upload_history_loaded_item_key")
            or ""
        )

        def _load_upload(payload: dict[str, Any]) -> tuple[bool, str]:
            ok, msg = apply_catalog_recording_to_session(ss, payload, st=st_obj)
            if ok:
                rid = str(payload.get("recording_id") or "")
                if rid:
                    ss["upload_catalog_active_recording_id"] = rid
                _after_history_load(ss, st_obj, page="analysis")
                playback = str(ss.get("upload_catalog_playback_status") or "")
                if playback == "metadata_only":
                    return True, "Loaded analysis metadata only — audio file not stored for this recording."
                if playback == "missing_file":
                    return True, "Loaded analysis metadata, but the audio file is missing."
                if msg:
                    return True, f"Loaded saved upload. {msg}"
                return True, "Loaded saved upload analysis with audio."
            return False, msg or "Could not load recording metadata."

        def _delete_upload(item_key: str) -> tuple[bool, str]:
            return delete_catalog_upload_recording(item_key, st=st_obj)

        _render_history_list(
            st_obj,
            item_type="uploaded_recording",
            rows=rows,
            list_error=list_err,
            summary_fn=catalog_upload_row_summary,
            on_load=_load_upload,
            on_delete=_delete_upload,
            key_prefix="upload_hist",
            active_item_key=active_key,
        )


def render_multitrack_history_panel(st_obj: Any, *, song_title: str = "") -> None:
    ss = st_obj.session_state
    mt = ss.get("mt_tracks") if isinstance(ss.get("mt_tracks"), dict) else {}
    has_layers = any(mt.get(slot) for slot in mt) or ss.get("mixed_track_wav")

    flash = ss.pop(MT_FLASH_KEY, None) or ss.pop("mt_hist_flash", None)

    with st_obj.expander("Project Library", expanded=False):
        if flash:
            st_obj.success(str(flash))
        if not cloud_enabled():
            st_obj.caption(
                cloud_block_reason()
                or "Cloud storage is disabled — saved projects use local media catalog on this device."
            )

        st_obj.markdown("##### Save current project")
        st_obj.caption(
            "Save to History stores the current layers and prepared backing as a Project Library version. "
            "Use separate names (e.g. Trial 1, Trial 2) for multiple backing/project versions."
        )
        name_default = default_project_name(ss, song_title=song_title)
        if "mt_history_save_name" not in ss:
            ss["mt_history_save_name"] = name_default
        project_name = st_obj.text_input(
            "Project name",
            key="mt_history_save_name",
        )
        notes = st_obj.text_area(
            "Notes (optional)",
            key="mt_history_save_notes",
            height=68,
            placeholder="Arrangement idea, mix notes, etc.",
        )
        if not has_layers:
            st_obj.caption("Load at least one layer or create a mix before saving.")
        if st_obj.button(
            "Save to History",
            type="primary",
            key="mt_history_save_btn",
            use_container_width=True,
            disabled=not has_layers,
        ):
            ok, item_key, err = save_multitrack_session_with_notes(
                ss,
                project_name=project_name,
                notes=notes,
                song_title=song_title,
                st=st_obj,
            )
            if ok:
                ss[MT_FLASH_KEY] = f"Saved to media catalog ({item_key})."
                ss["mt_hist_active_item"] = item_key
                ss["multitrack_catalog_active_id"] = item_key
                ss["_last_catalog_multitrack_id"] = item_key
                st_obj.rerun()
            else:
                st_obj.error(_format_save_error(err))

        st_obj.markdown("##### Saved projects")

        rows, list_err = list_catalog_multitrack_sessions(st=st_obj)
        active_key = str(
            ss.get("multitrack_catalog_active_id")
            or ss.get("mt_hist_active_item")
            or ss.get("multitrack_history_loaded_item_key")
            or ""
        )

        def _load_mt(payload: dict[str, Any]) -> tuple[bool, str]:
            ok, msg = apply_catalog_multitrack_to_session(ss, payload, st=st_obj, load_audio=True)
            if ok:
                mid = str(payload.get("multitrack_id") or "")
                if mid:
                    ss["multitrack_catalog_active_id"] = mid
                _after_history_load(ss, st_obj, page="multitrack")
                if msg == "metadata_only":
                    return True, "Loaded project metadata — track audio not stored for this session."
                if msg.startswith("loaded_"):
                    return True, f"Loaded multitrack project ({msg.replace('_', ' ')})."
                return True, "Loaded multitrack project with audio."
            queue_multitrack_history_load(ss, payload)
            return True, "Queued legacy project load — applying on next render."

        def _delete_mt(item_key: str) -> tuple[bool, str]:
            return delete_catalog_multitrack_session(item_key, st=st_obj)

        _render_history_list(
            st_obj,
            item_type="multitrack_session",
            rows=rows,
            list_error=list_err,
            summary_fn=catalog_multitrack_row_summary,
            on_load=_load_mt,
            on_delete=_delete_mt,
            key_prefix="mt_hist",
            active_item_key=active_key,
        )
