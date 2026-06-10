"""Developer-mode persistence trace for Music (``?dev=1`` or Developer Mode sidebar)."""



from __future__ import annotations



import subprocess

from typing import Any



MUSIC_PERSIST_DEPLOY_VERSION = "page-change-save-stamp-v24-transposing-receive"

TRACE_KEY = "_music_persist_trace"



BACKING_PATH_TRACE_LABELS: tuple[str, ...] = (
    "device_id",
    "trace_captured_at",
    "cloud_updated_at",
    "local_updated_at",
    "backing_last_save_at",
    "backing_local_edit_at",
    "backing_cloud_writer_device_id",
    "backing_cloud_writer_updated_at",
    "backing_stale_cloud_hint",
    "backing_sync_failure_class",
    "backing_rendered_bpm_key",
    "backing_rendered_bpm",
    "backing_rendered_bpm_vs_canonical",
    "backing_widget_canonical_mismatch",
    "backing_render_bind_reason",
    "backing_widget_bpm",
    "backing_canonical_bpm",
    "backing_payload_bpm",
    "backing_cloud_bpm",
    "backing_cloud_scope",
    "backing_cloud_loops",
    "backing_cloud_groove",
    "backing_cloud_meter",
    "backing_rendered_scope",
    "backing_canonical_scope",
    "backing_payload_scope",
    "cloud_payload_backing_scope",
    "backing_rendered_loops",
    "backing_widget_loops",
    "backing_canonical_loops",
    "backing_payload_loops",
    "cloud_payload_backing_loops",
    "backing_rendered_quick_section",
    "backing_rendered_single_section",
    "backing_rendered_groove",
    "backing_rendered_meter",
    "backing_rendered_meter_override",
    "backing_restore_source",
    "backing_last_write",
    "backing_widget_scope",
    "backing_pending_sync",
    "backing_dirty",
    "backing_user_edit_intent",
    "backing_user_edits_allowed",
    "force_save_reason",
    "last_save_cloud",
    "cloud_payload_source",
    "cloud_save_blocked_reason",
)


PRACTICE_RESTORE_TRACE_LABELS: tuple[str, ...] = (
    "practice_canonical_groove",
    "practice_canonical_minutes",
    "practice_filters_groove",
    "practice_filters_minutes",
    "cloud_payload_practice_groove",
    "cloud_payload_practice_minutes",
    "restored_practice_groove",
    "restored_practice_minutes",
    "practice_dirty",
    "practice_restore_applied",
    "practice_restore_skipped",
    "practice_last_write",
    "practice_overwrite_source",
)


# Always shown in ?dev=1 sidebar (Dell restore classification C/D/E).

WORKSPACE_RESTORE_TRACE_LABELS: tuple[str, ...] = (
    "cloud_fetch_studio_page",

    "restore_intermediate_studio_page",

    "restore_decision",

    "restore_skip_reason",

    "restored_studio_page",

    "restored_studio_page_source",

    "final_studio_page",

    "cloud_updated_at",

    "local_updated_at",

    "persist restore skip",

    "page overwrite source",

    "workspace_sync_attempted",

    "workspace_restore_applied",

    "restore_pick_reason",

    "live_resume_url_params",

    "stale_resume_flags_cleared",

    "has_resume_query_params_result",

    "should_skip_workspace_restore_for_resume",

    "ami_return_navigation_active",

)





def init_developer_mode_from_query(st: Any) -> None:

    try:

        raw = st.query_params.get("dev")

        if isinstance(raw, list):

            raw = raw[0] if raw else ""

        if str(raw or "").strip().lower() in {"1", "true", "yes", "on"}:

            st.session_state["developer_mode"] = True

    except Exception:

        pass





def music_developer_mode(st: Any) -> bool:

    return bool(st.session_state.get("developer_mode"))





def get_trace(st: Any) -> dict[str, Any]:

    raw = st.session_state.get(TRACE_KEY)

    return dict(raw) if isinstance(raw, dict) else {}





def update_trace(st: Any, **fields: Any) -> None:

    trace = get_trace(st)

    trace.update({k: v for k, v in fields.items() if v is not None or k in fields})

    trace.setdefault("deploy_version", MUSIC_PERSIST_DEPLOY_VERSION)

    try:

        trace.setdefault("git_commit", _git_head_short())

    except Exception:

        pass

    st.session_state[TRACE_KEY] = trace





def record_music_resume_restore_trace(st: Any, **fields: Any) -> None:

    """Record resume-flag reconciliation before workspace sync (Dell classification D)."""

    update_trace(st, **fields)





def _git_head_short() -> str:

    try:

        out = subprocess.check_output(

            ["git", "rev-parse", "--short", "HEAD"],

            stderr=subprocess.DEVNULL,

            timeout=2,

        )

        return out.decode().strip()

    except Exception:

        return "unknown"





def _trace_display(val: Any) -> str:

    if val is None:

        return "(not set)"

    if isinstance(val, bool):

        return str(val)

    text = str(val).strip()

    if not text:

        return "(empty)"

    return text


TEST_D_TRACE_LABELS: tuple[str, ...] = (
    "device_id",
    "trace_captured_at",
    "cloud_updated_at",
    "local_updated_at",
    "final_pick_key",
    "final_display_key",
    "final_instrument",
    "final_studio_page",
    "cloud_fetch_studio_page",
    "restored_pick_key",
    "restored_display_key",
    "restored_instrument",
    "restored_studio_page",
    "restore_decision",
    "restore_skip_reason",
    "active_song_restore_skipped",
    "active_song_dirty",
    "workspace_restore_source",
    "page_overwrite_source",
    "written_key_mode_widget",
    "written_key_mode_canonical",
    "written_key_mode_cloud",
    "written_key_mode_restored",
    "written_key_restore_source",
    "transposing_subtype_widget",
    "transposing_subtype_canonical",
    "transposing_subtype_cloud",
    "transposing_subtype_restored",
)


def collect_test_d_trace_rows(st: Any, trace: dict[str, Any]) -> dict[str, Any]:
    """Snapshot fields for Test D cross-device compare (song + key + instrument + page)."""
    from datetime import datetime, timezone

    from instrument_transposition import (
        CHART_IN_INSTRUMENT_KEY_KEY,
        SELECTED_TRANSPOSING_INSTRUMENT_KEY,
        chart_in_instrument_key,
        selected_transposing_type,
    )

    ss = st.session_state
    device_id = "unknown"
    try:
        from music_persistent_state import get_music_device_id

        device_id = get_music_device_id(st)
    except ImportError:
        pass
    song = ss.get("selected_song") if isinstance(ss.get("selected_song"), dict) else {}
    active_meta = ss.get("active_song_state") if isinstance(ss.get("active_song_state"), dict) else {}
    written_key_mode_widget = (
        ss.get(CHART_IN_INSTRUMENT_KEY_KEY)
        if CHART_IN_INSTRUMENT_KEY_KEY in ss
        else chart_in_instrument_key(ss)
    )
    written_key_mode_canonical = active_meta.get(CHART_IN_INSTRUMENT_KEY_KEY)
    written_key_mode_cloud = (
        trace.get("written_key_mode_cloud")
        if trace.get("written_key_mode_cloud") is not None
        else ss.get("_written_key_mode_cloud")
    )
    if written_key_mode_cloud is None:
        try:
            from active_song_state import written_key_mode_from_blob

            for blob_key in ("_suite_last_cloud_fetch_payload", "_suite_last_cloud_save_payload"):
                cloud_blob = ss.get(blob_key)
                if isinstance(cloud_blob, dict):
                    written_key_mode_cloud = written_key_mode_from_blob(cloud_blob)
                    if written_key_mode_cloud is not None:
                        break
        except ImportError:
            pass
    instrument_name = str(ss.get("instrument") or "").strip()
    transposing_subtype_widget = (
        ss.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
        if SELECTED_TRANSPOSING_INSTRUMENT_KEY in ss
        else (selected_transposing_type(ss, instrument_name) if instrument_name else "")
    )
    transposing_subtype_canonical = active_meta.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
    transposing_subtype_cloud = (
        trace.get("transposing_subtype_cloud")
        if trace.get("transposing_subtype_cloud") is not None
        else ss.get("_transposing_subtype_cloud")
    )
    if transposing_subtype_cloud is None:
        try:
            from active_song_state import transposing_subtype_from_blob

            for blob_key in ("_suite_last_cloud_fetch_payload", "_suite_last_cloud_save_payload"):
                cloud_blob = ss.get(blob_key)
                if isinstance(cloud_blob, dict):
                    transposing_subtype_cloud = transposing_subtype_from_blob(cloud_blob)
                    if transposing_subtype_cloud:
                        break
        except ImportError:
            pass
    active_song_dirty = bool(ss.get("active_song_state_dirty"))
    try:
        from active_song_state import is_active_song_locally_dirty

        active_song_dirty = is_active_song_locally_dirty(ss)
    except ImportError:
        pass
    return {
        "device_id": device_id,
        "trace_captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "cloud_updated_at": trace.get("cloud_updated_at")
        or ss.get("_suite_cloud_fetch_updated_at")
        or ss.get("_suite_persist_debug_cloud_ts"),
        "local_updated_at": trace.get("local_updated_at")
        or ss.get("_suite_persist_debug_disk_ts")
        or ss.get("_suite_persist_last_save_at"),
        "final_pick_key": ss.get("active_catalog_pick_key") or trace.get("final_pick_key"),
        "final_display_key": ss.get("display_key") or trace.get("final_display_key"),
        "final_instrument": ss.get("instrument") or trace.get("final_instrument"),
        "final_studio_page": trace.get("final_studio_page") or ss.get("studio_page"),
        "cloud_fetch_studio_page": trace.get("cloud_fetch_studio_page")
        or ss.get("_suite_cloud_fetch_studio_page"),
        "restored_pick_key": trace.get("restored_pick_key"),
        "restored_display_key": trace.get("restored_display_key"),
        "restored_instrument": trace.get("restored_instrument"),
        "restored_studio_page": trace.get("restored_studio_page"),
        "restore_decision": trace.get("restore_decision") or ss.get("_suite_restore_decision"),
        "restore_skip_reason": trace.get("restore_skip_reason")
        or ss.get("_suite_persist_restore_skip_reason"),
        "active_song_restore_skipped": ss.get("_active_song_restore_skipped_reason"),
        "active_song_dirty": active_song_dirty,
        "workspace_restore_source": trace.get("workspace_restore_source")
        or ss.get("_suite_persist_last_restore_source"),
        "page_overwrite_source": trace.get("page_overwrite_source")
        or ss.get("_suite_page_overwrite_source"),
        "written_key_mode_widget": written_key_mode_widget,
        "written_key_mode_canonical": written_key_mode_canonical,
        "written_key_mode_cloud": written_key_mode_cloud,
        "written_key_mode_restored": ss.get("_written_key_mode_restored")
        or trace.get("written_key_mode_restored"),
        "written_key_restore_source": ss.get("_written_key_restore_source")
        or trace.get("written_key_restore_source"),
        "transposing_subtype_widget": transposing_subtype_widget,
        "transposing_subtype_canonical": transposing_subtype_canonical,
        "transposing_subtype_cloud": transposing_subtype_cloud,
        "transposing_subtype_restored": ss.get("_transposing_subtype_restored")
        or trace.get("transposing_subtype_restored"),
        "final_song_title": song.get("title") or "",
    }


def format_test_d_compare_trace(rows: dict[str, Any]) -> str:
    """Copy-paste block for Dell vs phone Test D comparison."""
    lines = ["# Test D — active song + key + instrument + page", ""]
    for label in TEST_D_TRACE_LABELS:
        val = rows.get(label)
        if val is None or val == "":
            lines.append(f"{label}: (empty)")
        else:
            lines.append(f"{label}: {val}")
    title = rows.get("final_song_title")
    if title:
        lines.append(f"final_song_title: {title}")
    return "\n".join(lines)


def _cloud_studio_page_from_state(state: dict[str, Any]) -> str:

    if not isinstance(state, dict) or not state:

        return ""

    try:

        from suite_user_persistence import _workspace_page_from_blob



        return str(_workspace_page_from_blob("music", state) or "").strip()

    except Exception:

        meta = state.get("music_workspace_state")

        core = state.get("core")

        if isinstance(meta, dict):

            page = str(meta.get("studio_page") or "").strip()

            if page:

                return page

        if isinstance(core, dict):

            return str(core.get("studio_page") or core.get("page") or "").strip()

    return ""





def snapshot_workspace_restore_trace(st: Any) -> dict[str, Any]:

    """

    Merge session restore diagnostics + read-only cloud probe into trace.



    Called at render time so Dell ?dev=1 always exposes C/D/E fields even when

    workspace sync skipped before ``apply_music_disk_state`` ran.

    """

    ss = st.session_state

    trace = get_trace(st)



    cloud_fetch = str(

        trace.get("cloud_fetch_studio_page")

        or ss.get("_suite_cloud_fetch_studio_page")

        or ""

    ).strip()

    cloud_updated = (

        trace.get("cloud_updated_at")

        or ss.get("_suite_cloud_fetch_updated_at")

        or ss.get("_suite_persist_debug_cloud_ts")

    )

    local_updated = (

        trace.get("local_updated_at")

        or ss.get("_suite_persist_debug_disk_ts")

        or ss.get("_suite_persist_last_restore_at")

    )

    restore_decision = (

        trace.get("restore_decision")

        or ss.get("_suite_restore_decision")

        or ss.get("_suite_page_overwrite_source")

        or ss.get("_suite_persist_debug_pick_source")

    )

    restore_skip = (

        trace.get("restore_skip_reason")

        or ss.get("_suite_persist_restore_skip_reason")

        or ss.get("_suite_restore_skip_reason")

    )

    restored_studio = trace.get("restored_studio_page")



    try:

        from suite_cloud_state import load_cloud_full_session



        cloud_state, cloud_ts = load_cloud_full_session("music")

        if cloud_ts and not cloud_updated:

            cloud_updated = cloud_ts

        if isinstance(cloud_state, dict) and cloud_state:

            probed_page = _cloud_studio_page_from_state(cloud_state)

            if probed_page:

                cloud_fetch = cloud_fetch or probed_page

                ss["_suite_cloud_fetch_studio_page"] = probed_page

            if cloud_ts:

                ss["_suite_cloud_fetch_updated_at"] = cloud_ts

    except Exception:

        pass



    fields = {

        "cloud_fetch_studio_page": cloud_fetch or None,

        "cloud_updated_at": cloud_updated,

        "local_updated_at": local_updated,

        "restore_decision": restore_decision,

        "restore_skip_reason": restore_skip,

        "restored_studio_page": restored_studio,

        "final_studio_page": ss.get("studio_page"),

        "persist_restore_skip": ss.get("_suite_persist_restore_skip_reason"),

        "page_overwrite_source": ss.get("_suite_page_overwrite_source"),

        "workspace_sync_attempted": ss.get("_suite_workspace_sync_attempted"),

        "workspace_restore_applied": ss.get("_suite_persist_restore_applied"),

        "restore_pick_reason": ss.get("_suite_persist_debug_pick_reason")

        or ss.get("_suite_restore_pick_reason"),

        "live_resume_url_params": trace.get("live_resume_url_params")

        or ss.get("_suite_live_resume_url_params"),

        "stale_resume_flags_cleared": trace.get("stale_resume_flags_cleared")

        or ss.get("_suite_stale_resume_flags_cleared"),

        "has_resume_query_params_result": trace.get("has_resume_query_params_result"),

        "should_skip_workspace_restore_for_resume": trace.get("should_skip_workspace_restore_for_resume"),

        "ami_return_navigation_active": trace.get("ami_return_navigation_active"),

    }

    update_trace(st, **fields)

    try:
        from backing_track_state import snapshot_backing_path_trace

        snapshot_backing_path_trace(st)
    except ImportError:
        pass

    return fields





def _workspace_restore_row_values(st: Any, trace: dict[str, Any]) -> dict[str, Any]:

    ss = st.session_state

    return {

        "cloud_fetch_studio_page": trace.get("cloud_fetch_studio_page")

        or ss.get("_suite_cloud_fetch_studio_page"),

        "restore_intermediate_studio_page": trace.get("restore_intermediate_studio_page"),

        "restore_decision": trace.get("restore_decision") or ss.get("_suite_restore_decision"),

        "restore_skip_reason": trace.get("restore_skip_reason")

        or ss.get("_suite_persist_restore_skip_reason")

        or ss.get("_suite_restore_skip_reason"),

        "restored_studio_page": trace.get("restored_studio_page"),

        "restored_studio_page_source": trace.get("restored_studio_page_source"),

        "final_studio_page": trace.get("final_studio_page") or ss.get("studio_page"),

        "cloud_updated_at": trace.get("cloud_updated_at")

        or ss.get("_suite_cloud_fetch_updated_at")

        or ss.get("_suite_persist_debug_cloud_ts"),

        "local_updated_at": trace.get("local_updated_at")

        or ss.get("_suite_persist_debug_disk_ts"),

        "persist restore skip": trace.get("persist_restore_skip")

        or ss.get("_suite_persist_restore_skip_reason"),

        "page overwrite source": trace.get("page_overwrite_source")

        or ss.get("_suite_page_overwrite_source"),

        "workspace_sync_attempted": trace.get("workspace_sync_attempted")

        or ss.get("_suite_workspace_sync_attempted"),

        "workspace_restore_applied": trace.get("workspace_restore_applied")

        or ss.get("_suite_persist_restore_applied"),

        "restore_pick_reason": trace.get("restore_pick_reason")

        or ss.get("_suite_persist_debug_pick_reason")

        or ss.get("_suite_restore_pick_reason"),

        "live_resume_url_params": trace.get("live_resume_url_params")

        or ss.get("_suite_live_resume_url_params"),

        "stale_resume_flags_cleared": trace.get("stale_resume_flags_cleared")

        or ss.get("_suite_stale_resume_flags_cleared"),

        "has_resume_query_params_result": trace.get("has_resume_query_params_result"),

        "should_skip_workspace_restore_for_resume": trace.get("should_skip_workspace_restore_for_resume"),

        "ami_return_navigation_active": trace.get("ami_return_navigation_active"),

    }





def render_persistence_trace_sidebar(st: Any) -> None:

    if not music_developer_mode(st):

        return

    snapshot_workspace_restore_trace(st)

    trace = get_trace(st)

    ss = st.session_state

    ops = {}

    raw_ops = ss.get("_suite_persist_ops")

    if isinstance(raw_ops, dict):

        ops = dict(raw_ops.get("music") or {})

    restore_rows = _workspace_restore_row_values(st, trace)



    with st.sidebar.expander("Music persistence trace", expanded=False):

        st.caption(f"Deploy: {trace.get('deploy_version', MUSIC_PERSIST_DEPLOY_VERSION)}")

        st.caption(f"Commit: {trace.get('git_commit', 'unknown')}")



        try:
            from local_nav_trace import render_local_nav_trace_sidebar

            st.markdown("**Local nav (this run)**")
            render_local_nav_trace_sidebar(st)
        except ImportError:
            pass

        st.markdown("**Workspace restore (Dell)**")

        for label in WORKSPACE_RESTORE_TRACE_LABELS:

            st.text(f"{label}: {_trace_display(restore_rows.get(label))}")

        st.markdown("**Test D compare (active song + page)**")
        st.caption(
            "Frozen: Tests A–C passed. "
            "1) Dell: non-default song, key, instrument, page → wait 10s → copy block. "
            "2) Phone hard refresh (no touches) → copy block. "
            "3) Compare final_* fields."
        )
        test_d_rows = collect_test_d_trace_rows(st, trace)
        for label in TEST_D_TRACE_LABELS:
            st.text(f"{label}: {_trace_display(test_d_rows.get(label))}")
        st.text_area(
            "Copy Test D compare",
            value=format_test_d_compare_trace(test_d_rows),
            height=280,
            label_visibility="collapsed",
        )

        st.markdown("**Backing path (Test C — frozen)**")

        backing_rows = {label: trace.get(label) for label in BACKING_PATH_TRACE_LABELS}

        for label in BACKING_PATH_TRACE_LABELS:

            st.text(f"{label}: {_trace_display(backing_rows.get(label))}")

        failure_class = trace.get("backing_sync_failure_class") or ""

        if failure_class and failure_class not in ("path_ok", "unclassified"):

            st.warning(f"Backing sync class: {failure_class}")

        elif failure_class == "path_ok":

            st.success("Backing sync class: path_ok")

        stale_hint = trace.get("backing_stale_cloud_hint") or ""
        if stale_hint:
            st.warning(f"Backing stale-cloud hint: {stale_hint}")

        st.markdown("**Device compare (Test C)**")
        st.caption(
            "1) Dell: set obvious Backing values → wait 10s → copy block below. "
            "2) Hard-refresh phone → open Backing ?dev=1 → copy block. "
            "3) Compare device_id, timestamps, rendered_*, backing_cloud_*, backing_last_write."
        )
        try:
            from backing_track_state import format_backing_device_compare_trace

            compare_text = format_backing_device_compare_trace(trace)
            st.text_area(
                "Copy Backing device compare",
                value=compare_text,
                height=360,
                label_visibility="collapsed",
            )
        except ImportError:
            pass

        st.markdown("**Save / phone**")

        phone_rows = [

            ("page_change_write_pending", trace.get("page_change_write_pending") or ss.get("_suite_page_change_write_pending")),

            ("page_change_write_coerced", trace.get("page_change_write_coerced") if trace.get("page_change_write_coerced") is not None else ss.get("page_change_write_coerced")),

            ("music_cloud_write_path", trace.get("music_cloud_write_path") or ss.get("_music_cloud_write_path")),

            ("music_stamp_before_cloud_write_ran", trace.get("music_stamp_before_cloud_write_ran") if trace.get("music_stamp_before_cloud_write_ran") is not None else ss.get("_music_stamp_before_cloud_write_ran")),

            ("music_pre_write_path", trace.get("music_pre_write_path") or ss.get("music_pre_write_path")),

            ("music_pre_write_stamp_ran", trace.get("music_pre_write_stamp_ran") if trace.get("music_pre_write_stamp_ran") is not None else ss.get("music_pre_write_stamp_ran")),

            ("music_disk_build_error", trace.get("music_disk_build_error") or ss.get("_music_disk_build_error")),

            ("music_commit_error", trace.get("music_commit_error") or ss.get("_music_commit_error")),

            ("music_last_cloud_write_ok", trace.get("music_last_cloud_write_ok") if trace.get("music_last_cloud_write_ok") is not None else ss.get("_music_last_cloud_write_ok")),

            ("music_last_cloud_write_error", trace.get("music_last_cloud_write_error") or ss.get("_music_last_cloud_write_error")),

            ("force_autosave_ok", trace.get("force_autosave_ok") if trace.get("force_autosave_ok") is not None else ss.get("_music_force_save_ok")),

            ("force_autosave_error", trace.get("force_autosave_error") or ss.get("_suite_force_autosave_error")),

            ("page_change_finalize_ran", trace.get("page_change_finalize_ran") if trace.get("page_change_finalize_ran") is not None else ss.get("page_change_finalize_ran")),

            ("page_change_finalize_target", trace.get("page_change_finalize_target") or ss.get("page_change_finalize_target")),

            ("page_change_finalize_source", trace.get("page_change_finalize_source") or ss.get("page_change_finalize_source")),

            ("page_change_finalize_error", trace.get("page_change_finalize_error") or ss.get("page_change_finalize_error")),

            ("save_reason_at_write", trace.get("save_reason_at_write") or ss.get("_music_save_reason_at_write")),

            ("build_save_reason", trace.get("build_save_reason") or ss.get("_music_build_save_reason")),

            ("build_page_change_target", trace.get("build_page_change_target") or ss.get("_music_build_page_change_target")),

            ("final_payload_studio_page", trace.get("final_payload_studio_page") or ss.get("_music_final_payload_studio_page")),

            ("final_payload_source", trace.get("final_payload_source")),

            ("cloud_payload_studio_page", trace.get("cloud_payload_studio_page") or ss.get("_music_cloud_payload_studio_page")),

            ("cloud_payload_source", trace.get("cloud_payload_source") or ss.get("_music_cloud_payload_source")),

            ("cloud_write_studio_page", trace.get("cloud_write_studio_page") or ss.get("_music_cloud_write_studio_page")),

            ("disk_write_studio_page", trace.get("disk_write_studio_page") or ss.get("_music_disk_write_studio_page")),

            ("last_save_cloud", trace.get("last_save_cloud")),

            ("force_save_reason", trace.get("force_save_reason") or ss.get("_suite_persist_last_save_reason")),

            ("pre_save_studio_page", trace.get("pre_save_studio_page")),

            ("pre_save_nav_page", trace.get("pre_save_nav_page")),

            ("pre_save_page_owner", trace.get("pre_save_page_owner")),

            ("pre_stamp_core_page", trace.get("pre_stamp_core_page")),

            ("pre_stamp_session_page", trace.get("pre_stamp_session_page")),

            ("pre_stamp_workspace_page", trace.get("pre_stamp_workspace_page")),

            ("pre_stamp_studio_nav_page", trace.get("pre_stamp_studio_nav_page")),

            ("post_stamp_core_page", trace.get("post_stamp_core_page")),

            ("post_stamp_session_page", trace.get("post_stamp_session_page")),

            ("post_stamp_workspace_page", trace.get("post_stamp_workspace_page")),

            ("post_stamp_studio_nav_page", trace.get("post_stamp_studio_nav_page")),

            ("save_payload_source", trace.get("save_payload_source")),

            ("save_payload_core_page", trace.get("post_stamp_core_page") or trace.get("save_payload_core_page")),

            ("save_payload_session_page", trace.get("post_stamp_session_page") or trace.get("save_payload_session_page")),

            ("save_payload_workspace_page", trace.get("post_stamp_workspace_page") or trace.get("save_payload_workspace_page")),

            ("save_payload_studio_nav_page", trace.get("post_stamp_studio_nav_page") or trace.get("save_payload_studio_nav_page")),

            ("page_owner flag", trace.get("page_owner_flag") if trace.get("page_owner_flag") is not None else ss.get("_suite_page_user_nav")),

            ("_suite_page_user_nav", ss.get("_suite_page_user_nav")),

            ("normalized studio_page", trace.get("normalized_studio_page")),

            ("music_workspace_state studio_page", trace.get("music_workspace_state_studio_page")),

        ]

        for label, val in phone_rows:

            st.text(f"{label}: {_trace_display(val)}")



        st.markdown("**Phase C canonical state**")

        try:

            from active_song_state import render_active_song_state_debug
            from backing_track_state import render_backing_state_debug
            from practice_state import render_practice_state_debug
            from studio_nav_state import render_studio_nav_state_debug

            render_studio_nav_state_debug(st, ss)
            render_active_song_state_debug(st, ss)
            render_practice_state_debug(st, ss)
            render_backing_state_debug(st, ss)

        except ImportError:

            st.text("Phase C modules not available")



        st.markdown("**Practice restore trace**")

        for label in PRACTICE_RESTORE_TRACE_LABELS:

            st.text(f"{label}: {_trace_display(trace.get(label))}")



        st.markdown("**Other**")

        rows = [

            ("cloud restore attempted", trace.get("cloud_restore_attempted")),

            ("cloud restore success", trace.get("cloud_restore_success")),

            ("restore source", trace.get("restore_source") or ops.get("last_restore_source")),

            ("disk restore attempted", trace.get("disk_restore_attempted")),

            ("apply_saved result", trace.get("apply_saved_result")),

            ("apply_pick_key result", trace.get("apply_pick_key_result")),

            ("trusted-core init ran", trace.get("trusted_core_init_ran")),

            ("restored pick_key", trace.get("restored_pick_key")),

            ("restored display_key", trace.get("restored_display_key")),

            ("restored instrument", trace.get("restored_instrument")),

            ("autosave ran", trace.get("autosave_ran")),

            ("cloud save attempted", trace.get("cloud_save_attempted") or ops.get("last_cloud_save_attempted")),

            ("cloud save success", trace.get("cloud_save_success") or ops.get("last_cloud_save_ok")),

            ("cloud save error", trace.get("cloud_save_error") or ops.get("last_cloud_save_error")),

            ("last save source", trace.get("last_save_source") or ops.get("last_save_source")),

            ("saved pick_key", trace.get("saved_pick_key") or ops.get("last_saved_pick_key")),

            ("last cloud ts", trace.get("last_cloud_ts")),

            ("restore error", trace.get("restore_error")),

            ("final pick_key", ss.get("active_catalog_pick_key")),

            ("final song", (ss.get("selected_song") or {}).get("title") if isinstance(ss.get("selected_song"), dict) else ""),

            ("final display_key", ss.get("display_key")),

            ("final instrument", ss.get("instrument")),

            ("studio_page raw", trace.get("studio_page_raw") or ss.get("studio_page")),

            ("insight render skipped", ss.get("_ami_insight_render_skipped_reason")),

            ("insight scope decision", ss.get("_ami_insight_scope_decision")),

        ]

        for label, val in rows:

            if val is not None and val != "":

                st.text(f"{label}: {val}")


