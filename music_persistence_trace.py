"""Developer-mode persistence trace for Music (``?dev=1`` or Developer Mode sidebar)."""

from __future__ import annotations

import subprocess
from typing import Any

MUSIC_PERSIST_DEPLOY_VERSION = "2026-06-08-prod-persist-v3"
TRACE_KEY = "_music_persist_trace"


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


def render_persistence_trace_sidebar(st: Any) -> None:
    if not music_developer_mode(st):
        return
    trace = get_trace(st)
    ss = st.session_state
    ops = {}
    raw_ops = ss.get("_suite_persist_ops")
    if isinstance(raw_ops, dict):
        ops = dict(raw_ops.get("music") or {})
    with st.sidebar.expander("Music persistence trace", expanded=False):
        st.caption(f"Deploy: {trace.get('deploy_version', MUSIC_PERSIST_DEPLOY_VERSION)}")
        st.caption(f"Commit: {trace.get('git_commit', 'unknown')}")
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
            ("restored studio_page", trace.get("restored_studio_page")),
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
            ("final studio_page", ss.get("studio_page")),
        ]
        for label, val in rows:
            if val is not None and val != "":
                st.text(f"{label}: {val}")
