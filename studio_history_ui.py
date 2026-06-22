"""Streamlit UI for Upload + Multitrack cloud history libraries."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from multitrack_history import (
    ITEM_TYPE as MT_ITEM_TYPE,
    apply_multitrack_history,
    default_project_name,
    history_row_summary as mt_row_summary,
    list_multitrack_history,
    save_multitrack_to_history,
)
from studio_history_cloud import (
    cloud_enabled,
    delete_history_item,
    format_saved_at,
    widget_key_suffix,
)
from upload_history import (
    ITEM_TYPE as UPLOAD_ITEM_TYPE,
    apply_upload_history,
    default_upload_title,
    history_row_summary as upload_row_summary,
    list_upload_history,
    save_upload_to_history,
)


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
    summary_fn: Callable[[dict[str, Any]], str],
    on_load: Callable[[dict[str, Any]], None],
    key_prefix: str,
) -> None:
    if not rows:
        st_obj.caption("No saved items yet.")
        return

    for row in rows:
        item_key = str(row.get("item_key") or "")
        if not item_key:
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        saved_at = format_saved_at(str(payload.get("saved_at") or row.get("updated_at") or ""))
        title = str(row.get("title") or payload.get("title") or payload.get("project_name") or "Saved item")
        suffix = widget_key_suffix(item_key)

        with st_obj.container(border=True):
            st_obj.markdown(f"**{title}**")
            st_obj.caption(f"{saved_at} · {summary_fn(row)}")
            notes = str(payload.get("notes") or "").strip()
            if notes:
                st_obj.caption(f"Notes: {notes[:160]}{'…' if len(notes) > 160 else ''}")
            if payload.get("audio_skip_reason") or payload.get("mixed_skip_reason"):
                skip = payload.get("audio_skip_reason") or payload.get("mixed_skip_reason")
                st_obj.caption(f"Audio preview not stored ({skip}). Report and metadata still saved.")

            col_load, col_del = st_obj.columns(2)
            with col_load:
                if st_obj.button("Load", key=f"{key_prefix}_load_{suffix}", use_container_width=True):
                    on_load(payload)
            with col_del:
                if st_obj.button("Delete", key=f"{key_prefix}_del_{suffix}", use_container_width=True):
                    delete_history_item(item_type=item_type, item_key=item_key)
                    st_obj.success("Deleted from history.")
                    st_obj.rerun()


def render_upload_history_panel(st_obj: Any) -> None:
    ss = st_obj.session_state
    has_result = bool(ss.get("last_analysis_result", {}).get("ok", True) and ss.get("last_analysis_result"))

    with st_obj.expander("Upload History", expanded=False):
        if not cloud_enabled():
            st_obj.warning("Cloud storage is required for Upload History. Sign in with cloud persistence enabled.")
            return

        if has_result:
            st_obj.markdown("##### Save current analysis")
            title = st_obj.text_input(
                "Title / name",
                value=default_upload_title(ss),
                key="upload_history_save_title",
            )
            notes = st_obj.text_area(
                "Notes (optional)",
                key="upload_history_save_notes",
                height=68,
                placeholder="Rehearsal take, gig prep, etc.",
            )
            if st_obj.button("Save to History", type="primary", key="upload_history_save_btn", use_container_width=True):
                ok, _key = save_upload_to_history(ss, title=title, notes=notes, st=st_obj)
                if ok:
                    st_obj.success("Saved to Upload History.")
                    st_obj.rerun()
                else:
                    st_obj.error("Could not save — check cloud connection.")

        st_obj.markdown("##### Saved analyses")

        def _load_upload(payload: dict[str, Any]) -> None:
            if apply_upload_history(ss, payload):
                _after_history_load(ss, st_obj, page="analysis")
                st_obj.success("Loaded saved upload analysis.")
                st_obj.rerun()
            else:
                st_obj.error("Could not load that saved item.")

        _render_history_list(
            st_obj,
            item_type=UPLOAD_ITEM_TYPE,
            rows=list_upload_history(st=st_obj),
            summary_fn=upload_row_summary,
            on_load=_load_upload,
            key_prefix="upload_hist",
        )


def render_multitrack_history_panel(st_obj: Any, *, song_title: str = "") -> None:
    ss = st_obj.session_state
    mt = ss.get("mt_tracks") if isinstance(ss.get("mt_tracks"), dict) else {}
    has_layers = any(mt.get(slot) for slot in mt) or ss.get("mixed_track_wav")

    with st_obj.expander("Project Library", expanded=False):
        if not cloud_enabled():
            st_obj.warning("Cloud storage is required for Project Library. Sign in with cloud persistence enabled.")
            return

        st_obj.markdown("##### Save current project")
        project_name = st_obj.text_input(
            "Project name",
            value=default_project_name(ss, song_title=song_title),
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
            ok, _key = save_multitrack_to_history(
                ss,
                project_name=project_name,
                notes=notes,
                song_title=song_title,
                st=st_obj,
            )
            if ok:
                st_obj.success("Saved to Project Library.")
                st_obj.rerun()
            else:
                st_obj.error("Could not save — add layers or check cloud connection.")

        st_obj.markdown("##### Saved projects")

        def _load_mt(payload: dict[str, Any]) -> None:
            info = apply_multitrack_history(ss, payload)
            _after_history_load(ss, st_obj, page="multitrack")
            msg = "Loaded project."
            if info.get("metadata_only_layers"):
                msg += f" {info['metadata_only_layers']} layer(s) need audio re-upload (metadata restored)."
            if info.get("restored_layers"):
                msg += f" {info['restored_layers']} layer audio restored."
            if info.get("mixed_restored"):
                msg += " Mix preview restored."
            st_obj.success(msg)
            st_obj.rerun()

        _render_history_list(
            st_obj,
            item_type=MT_ITEM_TYPE,
            rows=list_multitrack_history(st=st_obj),
            summary_fn=mt_row_summary,
            on_load=_load_mt,
            key_prefix="mt_hist",
        )
