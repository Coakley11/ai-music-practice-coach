"""Developer-only deploy / persistence probe (``?dev=1``)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Any

SUITE_BUILD_MARKER = "unknown-deploy-marker"


def developer_mode(st: Any) -> bool:
    return bool(st.session_state.get("developer_mode"))


def init_developer_mode_from_query(st: Any) -> None:
    try:
        raw = st.query_params.get("dev")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        if str(raw or "").strip().lower() in {"1", "true", "yes", "on"}:
            st.session_state["developer_mode"] = True
    except Exception:
        pass


def _git_short() -> str:
    env = str(os.environ.get("SOURCE_VERSION") or os.environ.get("COMMIT_SHA") or "").strip()
    if env:
        return env[:12]
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            cwd=str(Path(__file__).resolve().parent),
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            cwd=str(Path(__file__).resolve().parent),
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _module_loaded(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _callable_exists(module_name: str, attr: str) -> bool:
    try:
        mod = __import__(module_name, fromlist=[attr])
        return callable(getattr(mod, attr, None))
    except Exception:
        return False


def cloud_config_probe() -> dict[str, Any]:
    out: dict[str, Any] = {
        "cloud_enabled": False,
        "storage_module": "",
        "suite_user_id_set": False,
        "config_error": None,
    }
    try:
        from suite_storage_config import cloud_storage_enabled, get_cloud_config
        from suite_user import get_external_user_id

        cfg = get_cloud_config()
        out["cloud_enabled"] = cloud_storage_enabled()
        out["suite_user_id_set"] = bool(str(get_external_user_id() or "").strip())
        if cfg is not None:
            out["supabase_url_set"] = bool(str(cfg.url or "").strip())
    except Exception as exc:
        out["config_error"] = str(exc)
        return out
    try:
        from suite_cloud_state import _import_storage

        _, out["storage_module"] = _import_storage()
    except Exception as exc:
        out["config_error"] = out.get("config_error") or str(exc)
    return out


def _resolve_build_marker() -> str:
    try:
        from music_persistence_trace import MUSIC_PERSIST_DEPLOY_VERSION

        return str(MUSIC_PERSIST_DEPLOY_VERSION or "").strip() or SUITE_BUILD_MARKER
    except ImportError:
        pass
    try:
        from studio_nav_history import NAVIGATION_UI_DEPLOY_MARKER

        return str(NAVIGATION_UI_DEPLOY_MARKER or "").strip() or SUITE_BUILD_MARKER
    except ImportError:
        pass
    return SUITE_BUILD_MARKER


def _resolve_nav_ui_marker() -> str:
    try:
        from studio_nav_history import NAVIGATION_UI_DEPLOY_MARKER

        return str(NAVIGATION_UI_DEPLOY_MARKER or "").strip()
    except ImportError:
        return ""


def deploy_info() -> dict[str, str]:
    return {
        "commit": _git_short(),
        "branch": _git_branch(),
        "build_marker": _resolve_build_marker(),
        "nav_ui_marker": _resolve_nav_ui_marker(),
    }


def _persist_ops(st: Any, app_id: str) -> dict[str, Any]:
    raw = st.session_state.get("_suite_persist_ops")
    if not isinstance(raw, dict):
        return {}
    block = raw.get(app_id)
    return dict(block) if isinstance(block, dict) else {}


def render_music_deploy_probe(st: Any) -> None:
    try:
        from suite_workspace import can_show_developer_tools

        if not can_show_developer_tools(st=st):
            return
    except ImportError:
        if not developer_mode(st):
            return
    info = deploy_info()
    cloud = cloud_config_probe()
    ss = st.session_state
    ops = _persist_ops(st, "music")
    trace = ss.get("_music_persist_trace")
    if not isinstance(trace, dict):
        trace = {}

    snapshot_restore = None
    try:
        from music_persistence_trace import snapshot_workspace_restore_trace

        snapshot_restore = snapshot_workspace_restore_trace(st)
    except Exception:
        pass

    with st.sidebar.expander("Music deploy probe", expanded=False):
        st.markdown("**Live deploy**")
        st.text(f"commit: {info['commit']}")
        st.text(f"branch: {info['branch']}")
        st.text(f"build_marker: {info['build_marker']}")
        st.text(f"git_commit: {info['commit']}")
        st.text(f"git_branch: {info['branch']}")
        if info.get("nav_ui_marker"):
            st.text(f"nav_ui_marker: {info['nav_ui_marker']}")

        st.markdown("**Modules / functions**")
        st.text(f"Supabase/cloud configured: {cloud.get('cloud_enabled')}")
        st.text(f"storage module: {cloud.get('storage_module')}")
        st.text(f"autosave_music_state exists: {_callable_exists('music_persistent_state', 'autosave_music_state')}")
        st.text(f"apply_music_disk_state exists: {_callable_exists('music_persistent_state', 'apply_music_disk_state')}")
        st.text(
            "persist_music_local_state calls cloud save: "
            f"{trace.get('persist_calls_autosave', ops.get('persist_calls_autosave', 'see trace'))}"
        )

        if cloud.get("config_error"):
            st.warning(f"Cloud config: {cloud['config_error']}")
        elif not cloud.get("cloud_enabled"):
            st.warning(
                "Supabase/cloud persistence is NOT configured. "
                "Session will reset after Streamlit Cloud reboot."
            )

        st.markdown("**Last save / restore**")
        for label, key in (
            ("last restore source", "last_restore_source"),
            ("last save source", "last_save_source"),
            ("cloud save attempted", "last_cloud_save_attempted"),
            ("cloud save success", "last_cloud_save_ok"),
            ("cloud save error", "last_cloud_save_error"),
            ("autosave ran", "autosave_ran"),
            ("trusted-core init ran", "trusted_core_init_ran"),
        ):
            val = trace.get(key) if key in trace else ops.get(key)
            if val is not None and val != "":
                st.text(f"{label}: {val}")

        core = ss.get("selected_song") if isinstance(ss.get("selected_song"), dict) else {}
        st.text(f"restored pick_key: {trace.get('restored_pick_key', '')}")
        st.text(f"final pick_key: {ss.get('active_catalog_pick_key')}")
        st.text(f"final song: {core.get('title', '')}")
        st.text(f"final display_key: {ss.get('display_key')}")
        st.text(f"final instrument: {ss.get('instrument')}")
        st.text(f"final studio_page: {ss.get('studio_page')}")

        if isinstance(snapshot_restore, dict):
            st.markdown("**Workspace restore snapshot**")
            for key in (
                "cloud_fetch_studio_page",
                "restore_decision",
                "restore_skip_reason",
                "restored_studio_page",
                "cloud_updated_at",
            ):
                val = snapshot_restore.get(key)
                st.text(f"{key}: {val if val not in (None, '') else '(not set)'}")
