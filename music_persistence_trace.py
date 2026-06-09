"""Developer-mode persistence trace for Music (``?dev=1`` or Developer Mode sidebar)."""



from __future__ import annotations



import subprocess

from typing import Any



MUSIC_PERSIST_DEPLOY_VERSION = "studio-nav-stable-v27-practice-durable-restore"

TRACE_KEY = "_music_persist_trace"



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

    "restore_decision",

    "restore_skip_reason",

    "restored_studio_page",

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

    return fields





def _workspace_restore_row_values(st: Any, trace: dict[str, Any]) -> dict[str, Any]:

    ss = st.session_state

    return {

        "cloud_fetch_studio_page": trace.get("cloud_fetch_studio_page")

        or ss.get("_suite_cloud_fetch_studio_page"),

        "restore_decision": trace.get("restore_decision") or ss.get("_suite_restore_decision"),

        "restore_skip_reason": trace.get("restore_skip_reason")

        or ss.get("_suite_persist_restore_skip_reason")

        or ss.get("_suite_restore_skip_reason"),

        "restored_studio_page": trace.get("restored_studio_page"),

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



        st.markdown("**Workspace restore (Dell)**")

        for label in WORKSPACE_RESTORE_TRACE_LABELS:

            st.text(f"{label}: {_trace_display(restore_rows.get(label))}")



        st.markdown("**Save / phone**")

        phone_rows = [

            ("cloud_payload_studio_page", trace.get("cloud_payload_studio_page")),

            ("last_save_cloud", trace.get("last_save_cloud")),

            ("force_save_reason", trace.get("force_save_reason") or ss.get("_suite_persist_last_save_reason")),

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

            from practice_state import render_practice_state_debug

            from studio_nav_state import render_studio_nav_state_debug



            render_studio_nav_state_debug(st, ss)

            render_active_song_state_debug(st, ss)

            render_practice_state_debug(st, ss)

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


