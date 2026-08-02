"""
Cross-device full-session persistence via Supabase ``suite_app_current_state``.

Apps autosave a JSON blob under ``metrics.full_session``. On startup, when no
Continue/deep-link query params are present, ``suite_user_persistence.restore_once``
loads the newer of cloud vs local disk and applies it to ``st.session_state``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Literal

FULL_SESSION_KEY = "full_session"

PickSource = Literal["cloud", "disk", "none"]

CLOUD_SAVE_DIAG_KEY = "_suite_last_cloud_save_result"


@dataclass(frozen=True)
class CloudSaveResult:
    success: bool
    failure_stage: str = ""
    exception: str = ""
    supabase_response_status: int | None = None
    account_resolution_attempted: bool = False
    account_id_resolved: bool = False
    account_id: str = ""
    workspace_id_resolved: str = ""
    cloud_document_path: str = ""
    cloud_write_allowed: bool = True
    cloud_write_block_reason: str = ""
    cloud_client_available: bool = False
    cloud_auth_available: bool = False
    cloud_payload_built: bool = False
    cloud_payload_revision: int = 0
    save_cloud_full_session_called: bool = True
    save_cloud_full_session_return_value: bool = False
    cloud_upsert_attempted: bool = False
    cloud_upsert_succeeded: bool = False
    storage_module: str = ""
    storage_app_key: str = ""

    def __bool__(self) -> bool:
        return self.success

    def to_diag(self) -> dict[str, Any]:
        return {
            "save_cloud_full_session_return_value": self.success,
            "save_cloud_full_session_failure_stage": self.failure_stage or "(none)",
            "save_cloud_full_session_exception": self.exception or "(none)",
            "supabase_response_status": self.supabase_response_status,
            "account_resolution_attempted": self.account_resolution_attempted,
            "account_id_resolved": self.account_id_resolved,
            "account_id": self.account_id or "(none)",
            "workspace_id_resolved": self.workspace_id_resolved or "(none)",
            "cloud_document_path": self.cloud_document_path or "(none)",
            "cloud_write_allowed": self.cloud_write_allowed,
            "cloud_write_block_reason": self.cloud_write_block_reason or "(none)",
            "cloud_client_available": self.cloud_client_available,
            "cloud_auth_available": self.cloud_auth_available,
            "cloud_payload_built": self.cloud_payload_built,
            "cloud_payload_revision": self.cloud_payload_revision,
            "save_cloud_full_session_called": self.save_cloud_full_session_called,
            "cloud_upsert_attempted": self.cloud_upsert_attempted,
            "cloud_upsert_succeeded": self.cloud_upsert_succeeded,
            "cloud_storage_module": self.storage_module or "(none)",
            "cloud_storage_app_key": self.storage_app_key or "(none)",
        }


def _record_cloud_save_result(session: dict[str, Any] | None, result: CloudSaveResult) -> None:
    if session is None:
        return
    session[CLOUD_SAVE_DIAG_KEY] = result.to_diag()
    session["_suite_last_cloud_save_failure_stage"] = result.failure_stage or None
    session["_suite_last_cloud_save_exception"] = result.exception or None


def _cloud_save_account_context() -> dict[str, Any]:
    out: dict[str, Any] = {
        "account_resolution_attempted": True,
        "account_id_resolved": False,
        "account_id": "",
        "workspace_id_resolved": "",
        "cloud_document_path": "",
        "cloud_auth_available": False,
    }
    try:
        from suite_user import get_account_user_id

        uid = str(get_account_user_id() or "").strip()
        out["account_id"] = uid
        if uid and not uid.startswith("local:"):
            out["account_id_resolved"] = True
            out["cloud_auth_available"] = True
    except Exception:
        pass
    try:
        from suite_workspace import get_active_workspace_id, scoped_cloud_app_id

        ws = str(get_active_workspace_id() or "").strip()
        out["workspace_id_resolved"] = ws
        out["cloud_document_path"] = scoped_cloud_app_id("music")
    except Exception:
        pass
    return out


@dataclass(frozen=True)
class RestorePickResult:
    state: dict[str, Any]
    source: PickSource
    reason: str
    cloud_ts: str | None
    disk_ts: str | None

_RESUME_QUERY_KEYS: dict[str, tuple[str, ...]] = {
    "music": (
        "suite_resume",
        "suite_page",
        "suite_pick_key",
        "suite_song",
        "suite_display_key",
        "suite_instrument",
        "suite_section_focus",
        "suite_ami_insight",
        "suite_ai_question_id",
    ),
    "baseball": (
        "suite_resume",
        "suite_page",
        "suite_trend_player",
        "suite_player_a",
        "suite_player_b",
        "suite_draft_room",
        "suite_draft_section",
    ),
    "investment": ("suite_page",),
    "nba": ("suite_resume", "suite_page", "suite_team"),
    "future_lens": (
        "suite_resume",
        "suite_page",
        "suite_sim",
        "suite_fl_domain",
        "suite_fl_area",
        "suite_fl_timeline_year",
        "suite_fl_sim_year",
        "suite_fl_view",
    ),
    "applied_intelligence": (
        "suite_page",
        "suite_lesson",
        "suite_ai_question",
        "suite_ai_question_id",
        "suite_ai_source_app",
        "suite_ai_context",
    ),
}


def _normalize_resume_app_key(app_key: str) -> str:
    key = str(app_key or "").strip()
    if key == "math":
        return "applied_intelligence"
    return key


# URL params that must preserve return/source page navigation — block cloud workspace restore.
_WORKSPACE_RESTORE_BLOCKING_QUERY_KEYS: dict[str, tuple[str, ...]] = {
    "music": (
        "suite_resume",
        "suite_page",
        "suite_ami_insight",
        "suite_ai_question_id",
    ),
    "baseball": (
        "suite_resume",
        "suite_page",
        "suite_draft_room",
        "suite_draft_section",
    ),
}


def _workspace_restore_blocking_keys(app_key: str) -> tuple[str, ...]:
    key = _normalize_resume_app_key(app_key)
    if key in _WORKSPACE_RESTORE_BLOCKING_QUERY_KEYS:
        return _WORKSPACE_RESTORE_BLOCKING_QUERY_KEYS[key]
    return _RESUME_QUERY_KEYS.get(key, ("suite_resume", "suite_page"))


def _qp_get(st: Any, name: str) -> str:
    try:
        raw = st.query_params.get(name)
    except Exception:
        return ""
    if raw is None:
        return ""
    if isinstance(raw, list):
        return str(raw[0] or "").strip()
    return str(raw).strip()


def _ami_resume_consumed_flag(app_key: str) -> str:
    key = str(app_key or "").strip().lower()
    if key == "math":
        key = "applied_intelligence"
    return f"_ami_resume_consumed_{key}"


def ami_return_resume_consumed(st: Any, app_key: str) -> bool:
    """True after AMI insight was hydrated+rendered once on the source page."""
    return bool(st.session_state.get(_ami_resume_consumed_flag(app_key)))


def list_active_resume_query_params(st: Any, app_key: str) -> list[str]:
    """Resume / deep-link query param names currently present in the URL."""
    key = _normalize_resume_app_key(app_key)
    params = _RESUME_QUERY_KEYS.get(key, ("suite_resume", "suite_page"))
    return [name for name in params if _qp_get(st, name)]


def list_workspace_restore_blocking_query_params(st: Any, app_key: str) -> list[str]:
    """URL params that block cloud workspace restore (return/AMI navigation, not song hydrate)."""
    key = _normalize_resume_app_key(app_key)
    params = _workspace_restore_blocking_keys(key)
    return [name for name in params if _qp_get(st, name)]


def _ami_return_url_active(st: Any, app_key: str) -> bool:
    """True when return/AMI URL params steer page navigation (not song hydrate-only params)."""
    if list_workspace_restore_blocking_query_params(st, app_key):
        return True
    try:
        from applied_math_return_insight import _active_ami_return_query_param_keys, insight_return_query_id

        if insight_return_query_id(st) or _active_ami_return_query_param_keys(st):
            return True
    except ImportError:
        pass
    return False


_STALE_RESUME_SESSION_FLAGS: tuple[str, ...] = (
    "_suite_resume_launch_music",
    "_suite_resume_launch",
    "_suite_resume_launch_baseball",
    "_suite_resume_launch_app",
    "_suite_resume_launch_key",
    "_suite_resume_launch_applied_intelligence",
    "_suite_resume_insight_hydration_only",
    "_suite_workspace_sync_skipped_no_apply",
    "_skip_page_restore_for",
    "_navigate_to_studio_page",
    "_navigate_to_page",
    "_suite_cloud_target_page",
    "ami_return_force_active_page",
    "ami_return_forced_page",
    "_ami_insight_return_preserve",
)


def reconcile_stale_resume_session_flags(st: Any, app_key: str) -> list[str]:
    """
    Drop stale resume/AMI session flags when the URL no longer carries resume params.

    Returns flag names cleared. Does not clear flags during a live URL resume/AMI return.
    """
    ss = st.session_state
    if _ami_return_url_active(st, app_key):
        return []
    cleared: list[str] = []
    key = _normalize_resume_app_key(app_key)
    for flag in (*_STALE_RESUME_SESSION_FLAGS, f"_suite_resume_launch_{key}"):
        if flag in ss:
            ss.pop(flag, None)
            cleared.append(flag)
    for flag in list(ss.keys()):
        name = str(flag)
        if name.startswith("_suite_resume_launch_") and name not in cleared:
            ss.pop(flag, None)
            cleared.append(name)
    try:
        from applied_math_return_insight import reconcile_stale_page_navigation

        reconcile_stale_page_navigation(st, app_key)
    except ImportError:
        pass
    return cleared


def should_skip_workspace_restore_for_resume(
    st: Any,
    app_key: str,
    *,
    reconcile_first: bool = True,
) -> bool:
    """
    Skip cloud workspace restore only for live URL resume params or URL-driven AMI return.

    Session-only ``_suite_resume_launch_*`` / ``_ami_insight_return_preserve`` flags
    must not block cross-device page sync.
    """
    if ami_return_resume_consumed(st, app_key):
        if reconcile_first:
            reconcile_stale_resume_session_flags(st, app_key)
        return False
    if reconcile_first:
        reconcile_stale_resume_session_flags(st, app_key)
    if list_workspace_restore_blocking_query_params(st, app_key):
        return True
    try:
        from applied_math_return_insight import ami_return_navigation_active

        return ami_return_navigation_active(st, app_key)
    except ImportError:
        return False


def has_resume_query_params(st: Any, app_key: str) -> bool:
    """True when live URL resume/AMI params should defer cloud workspace restore."""
    return should_skip_workspace_restore_for_resume(st, app_key, reconcile_first=True)


def parse_persist_timestamp(ts: str | None) -> float:
    """Parse ISO / Supabase timestamps to UTC epoch seconds (naive => UTC)."""
    if not ts:
        return 0.0
    s = str(ts).strip()
    if not s:
        return 0.0
    if "T" not in s and " " in s:
        s = s.replace(" ", "T", 1)
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s[:32])
    except ValueError:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.timestamp()


def _parse_ts(ts: str | None) -> float:
    return parse_persist_timestamp(ts)


def _import_storage() -> tuple[Any, str]:
    """Resolve storage backend; standalone deploys use ``suite_storage_supabase``."""
    try:
        import suite_storage as storage

        return storage, "suite_storage"
    except ImportError:
        import suite_storage_supabase as storage

        return storage, "suite_storage_supabase"


def probe_cloud_restore_diagnostics(st: Any, app_id: str) -> dict[str, Any]:
    """
    Explain why cloud restore may be empty (for in-app diagnostics).

    Does not mutate session state except reading query params / flags.
    """
    diag: dict[str, Any] = {
        "cloud_enabled": False,
        "account_mode": "unknown",
        "account_user_id": "",
        "suite_user_id": "",
        "storage_module": "",
        "skip_resume_params": False,
        "resume_launch_flag": False,
        "cloud_row_found": False,
        "cloud_has_full_session": False,
        "cloud_updated_at": None,
        "cloud_load_error": None,
    }
    try:
        from suite_user import account_mode, get_account_user_id, get_external_user_id

        diag["account_mode"] = account_mode()
        diag["account_user_id"] = get_account_user_id()
        diag["suite_user_id"] = get_external_user_id()
    except Exception as exc:
        diag["cloud_load_error"] = f"account probe: {exc}"

    key = str(app_id or "").strip()
    if key == "math":
        key = "applied_intelligence"
    diag["resume_launch_flag"] = bool(st.session_state.get(f"_suite_resume_launch_{key}"))
    try:
        diag["skip_resume_params"] = has_resume_query_params(st, app_id)
    except Exception:
        pass

    try:
        from suite_storage_config import cloud_storage_enabled

        diag["cloud_enabled"] = cloud_storage_enabled()
    except ImportError:
        diag["cloud_load_error"] = diag.get("cloud_load_error") or "suite_storage_config missing"
        return diag

    if not diag["cloud_enabled"]:
        return diag

    try:
        storage, diag["storage_module"] = _import_storage()
        app_key = storage.normalize_app_key(app_id)
        meta_fn = getattr(storage, "load_current_state_meta_for_app", None)
        row_fn = getattr(storage, "load_current_state_for_app", None)
        if meta_fn and row_fn:
            meta = meta_fn(app_id) or {}
            if isinstance(meta, dict) and meta:
                diag["cloud_row_found"] = True
                diag["cloud_updated_at"] = str(meta.get("updated_at") or "") or None
            row = row_fn(app_id) if diag["cloud_row_found"] else {}
        else:
            row = storage.load_current_states(include_metrics=True).get(app_key) or {}
            if isinstance(row, dict) and row:
                diag["cloud_row_found"] = True
                diag["cloud_updated_at"] = str(row.get("updated_at") or "") or None
        if isinstance(row, dict) and row:
            metrics = row.get("metrics")
            if isinstance(metrics, dict):
                blob = metrics.get(FULL_SESSION_KEY)
                diag["cloud_has_full_session"] = isinstance(blob, dict) and bool(blob)
    except Exception as exc:
        diag["cloud_load_error"] = str(exc)

    return diag


def _cloud_storage_app_id(app_id: str) -> str:
    try:
        from suite_workspace import scoped_cloud_app_id

        return scoped_cloud_app_id(app_id)
    except ImportError:
        return str(app_id or "").strip()


def _full_session_cache_keys(app_key: str) -> tuple[str, str]:
    return f"_suite_full_session_ts_{app_key}", f"_suite_full_session_blob_{app_key}"


def _streamlit_session() -> Any | None:
    try:
        import streamlit as st  # noqa: WPS433

        return st.session_state
    except Exception:
        return None


def invalidate_cloud_full_session_cache(app_id: str) -> None:
    """Drop cached full_session after a local or cloud write."""
    try:
        storage, _ = _import_storage()
    except ImportError:
        return
    app_key = storage.normalize_app_key(_cloud_storage_app_id(app_id))
    ss = _streamlit_session()
    if ss is None:
        return
    ts_key, blob_key = _full_session_cache_keys(app_key)
    ss.pop(ts_key, None)
    ss.pop(blob_key, None)


def load_cloud_full_session(app_id: str, *, force: bool = False) -> tuple[dict[str, Any], str | None]:
    """Return ``(session_dict, updated_at_iso)`` from cloud, or empty dict."""
    ss = _streamlit_session()
    if ss is not None:
        ss["_cloud_fetch_attempted"] = True
    try:
        from suite_storage_config import cloud_storage_enabled
    except ImportError:
        if ss is not None:
            ss["_cloud_fetch_error"] = "cloud_storage_config_missing"
        return {}, None
    if not cloud_storage_enabled():
        if ss is not None:
            ss["_cloud_fetch_error"] = "cloud_storage_disabled"
            ss["_cloud_fetch_succeeded"] = False
            ss["_cloud_document_found"] = False
        return {}, None
    try:
        storage, _ = _import_storage()

        app_key = storage.normalize_app_key(_cloud_storage_app_id(app_id))
        meta_fn = getattr(storage, "load_current_state_meta_for_app", None)
        row_fn = getattr(storage, "load_current_state_for_app", None)
        ts_key, blob_key = _full_session_cache_keys(app_key)

        updated_at: str | None = None
        if meta_fn:
            meta = meta_fn(app_id) or {}
            updated_at = str(meta.get("updated_at") or "") or None
            if not force and ss is not None and ss.get(ts_key) == updated_at:
                cached = ss.get(blob_key)
                if isinstance(cached, dict):
                    if ss is not None:
                        ss["_cloud_fetch_succeeded"] = True
                        ss["_cloud_document_found"] = bool(cached)
                    return copy.deepcopy(cached), updated_at

        if row_fn:
            row = row_fn(app_id) or {}
        else:
            row = storage.load_current_states(include_metrics=True).get(app_key) or {}
        if not isinstance(row, dict):
            if ss is not None:
                ss["_cloud_fetch_succeeded"] = False
                ss["_cloud_document_found"] = False
                ss["_cloud_fetch_error"] = "invalid_cloud_row"
            return {}, None
        updated_at = str(row.get("updated_at") or "") or updated_at
        metrics = row.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}
        blob = metrics.get(FULL_SESSION_KEY)
        session_out: dict[str, Any] = {}
        if isinstance(blob, dict) and blob:
            session_out = copy.deepcopy(blob)
        if ss is not None:
            ss[blob_key] = copy.deepcopy(session_out)
            ss[ts_key] = updated_at
            ss["_cloud_fetch_succeeded"] = True
            ss["_cloud_document_found"] = bool(session_out)
            ss.pop("_cloud_fetch_error", None)
            try:
                from workspace_revision import workspace_revision_from_blob

                ss["_cloud_loaded_revision"] = workspace_revision_from_blob(session_out)
            except ImportError:
                pass
        return session_out, updated_at
    except Exception as exc:
        if ss is not None:
            ss["_cloud_fetch_succeeded"] = False
            ss["_cloud_document_found"] = False
            ss["_cloud_fetch_error"] = str(exc)
        return {}, None


def save_cloud_full_session(
    app_id: str,
    state: dict[str, Any],
    *,
    page: str = "",
    summary: str = "",
) -> CloudSaveResult:
    """Persist full_session to Supabase. Returns structured result with failure stage."""
    ss = _streamlit_session()
    ctx = _cloud_save_account_context()
    try:
        from workspace_revision import workspace_revision_from_blob
    except ImportError:
        workspace_revision_from_blob = lambda _s: 0  # type: ignore[assignment,misc]

    base = CloudSaveResult(
        success=False,
        save_cloud_full_session_return_value=False,
        account_resolution_attempted=bool(ctx.get("account_resolution_attempted")),
        account_id_resolved=bool(ctx.get("account_id_resolved")),
        account_id=str(ctx.get("account_id") or ""),
        workspace_id_resolved=str(ctx.get("workspace_id_resolved") or ""),
        cloud_document_path=str(ctx.get("cloud_document_path") or ""),
        cloud_auth_available=bool(ctx.get("cloud_auth_available")),
        cloud_payload_built=bool(state),
        cloud_payload_revision=workspace_revision_from_blob(state if isinstance(state, dict) else {}),
    )

    if not state:
        result = replace(base, failure_stage="empty_state")
        _record_cloud_save_result(ss, result)
        return result

    try:
        from suite_storage_config import cloud_storage_enabled
    except ImportError as exc:
        result = replace(
            base,
            failure_stage="cloud_config_import_error",
            exception=str(exc),
            cloud_client_available=False,
        )
        _record_cloud_save_result(ss, result)
        return result

    if not cloud_storage_enabled():
        result = replace(
            base,
            failure_stage="cloud_storage_disabled",
            cloud_write_allowed=False,
            cloud_write_block_reason="cloud_storage_disabled",
            cloud_client_available=False,
        )
        _record_cloud_save_result(ss, result)
        return result

    try:
        storage, module_name = _import_storage()
    except Exception as exc:
        result = replace(
            base,
            failure_stage="storage_import_error",
            exception=str(exc),
            cloud_client_available=False,
        )
        _record_cloud_save_result(ss, result)
        return result

    logical_app = storage.normalize_app_key(app_id)
    storage_app_key = storage.normalize_app_key(_cloud_storage_app_id(app_id))
    try:
        from suite_workspace import logical_storage_app_key

        logical_app = logical_storage_app_key(storage_app_key)
    except ImportError:
        logical_app = storage.normalize_app_key(_cloud_storage_app_id(app_id))
    try:
        import suite_storage_supabase as supabase_mod

        active_keys = getattr(storage, "ACTIVE_APP_KEYS", supabase_mod.ACTIVE_APP_KEYS)
        if not isinstance(active_keys, frozenset):
            active_keys = supabase_mod.ACTIVE_APP_KEYS
        if logical_app not in active_keys:
            result = replace(
                base,
                failure_stage="inactive_app_key",
                cloud_client_available=True,
                storage_module=module_name,
                storage_app_key=storage_app_key,
                cloud_write_block_reason=f"inactive_app:{logical_app}",
            )
            _record_cloud_save_result(ss, result)
            return result
    except Exception:
        pass

    try:
        from suite_storage_config import get_cloud_config

        if get_cloud_config() is None:
            result = replace(
                base,
                failure_stage="supabase_not_configured",
                cloud_client_available=False,
                storage_module=module_name,
                storage_app_key=storage_app_key,
            )
            _record_cloud_save_result(ss, result)
            return result
    except Exception as exc:
        result = replace(
            base,
            failure_stage="cloud_config_error",
            exception=str(exc),
            storage_module=module_name,
            storage_app_key=storage_app_key,
        )
        _record_cloud_save_result(ss, result)
        return result

    try:
        storage.save_current_state(
            storage_app_key,
            page=page or "",
            summary=summary or "Last session",
            metrics={FULL_SESSION_KEY: copy.deepcopy(state)},
        )
        invalidate_cloud_full_session_cache(app_id)
        result = CloudSaveResult(
            success=True,
            save_cloud_full_session_return_value=True,
            account_resolution_attempted=base.account_resolution_attempted,
            account_id_resolved=base.account_id_resolved,
            account_id=base.account_id,
            workspace_id_resolved=base.workspace_id_resolved,
            cloud_document_path=base.cloud_document_path,
            cloud_auth_available=base.cloud_auth_available,
            cloud_payload_built=True,
            cloud_payload_revision=base.cloud_payload_revision,
            cloud_client_available=True,
            cloud_upsert_attempted=True,
            cloud_upsert_succeeded=True,
            supabase_response_status=200,
            storage_module=module_name,
            storage_app_key=storage_app_key,
        )
        _record_cloud_save_result(ss, result)
        return result
    except RuntimeError as exc:
        status = None
        msg = str(exc)
        if "failed (" in msg:
            try:
                status = int(msg.split("failed (")[1].split(")")[0])
            except (IndexError, ValueError):
                status = None
        result = replace(
            base,
            failure_stage="supabase_http_error",
            exception=msg,
            supabase_response_status=status,
            cloud_client_available=True,
            cloud_upsert_attempted=True,
            cloud_upsert_succeeded=False,
            storage_module=module_name,
            storage_app_key=storage_app_key,
        )
        _record_cloud_save_result(ss, result)
        return result
    except Exception as exc:
        result = replace(
            base,
            failure_stage="unexpected_exception",
            exception=str(exc),
            cloud_client_available=True,
            cloud_upsert_attempted=True,
            cloud_upsert_succeeded=False,
            storage_module=module_name,
            storage_app_key=storage_app_key,
        )
        _record_cloud_save_result(ss, result)
        return result


def clear_cloud_full_session(app_id: str) -> None:
    """Remove persisted full_session blob from cloud (reset flows)."""
    try:
        from suite_storage_config import cloud_storage_enabled
    except ImportError:
        return
    if not cloud_storage_enabled():
        return
    try:
        storage, _ = _import_storage()
        app_key = storage.normalize_app_key(_cloud_storage_app_id(app_id))
        storage.save_current_state(
            app_key,
            page="",
            summary="",
            metrics={FULL_SESSION_KEY: {}},
        )
    except Exception:
        pass


def pick_restore_session(
    cloud_state: dict[str, Any],
    cloud_ts: str | None,
    disk_state: dict[str, Any],
    disk_ts: str | None,
    *,
    local_dirty: bool = False,
    prefer_cloud_on_tie: bool = True,
    cloud_first: bool = True,
) -> RestorePickResult:
    """
    Choose restore payload for direct open / cloud re-sync.

    When ``local_dirty`` is False and ``cloud_first`` is True (default), cloud
    ``full_session`` is the cross-device source of truth whenever it exists.
    Local disk is a per-device cache used only when cloud is empty/unavailable
    or this device has unsaved local edits.
    """
    cloud_epoch = _parse_ts(cloud_ts)
    disk_epoch = _parse_ts(disk_ts)

    if not cloud_state and not disk_state:
        return RestorePickResult({}, "none", "empty", cloud_ts, disk_ts)
    if cloud_state and not disk_state:
        return RestorePickResult(cloud_state, "cloud", "disk missing", cloud_ts, disk_ts)
    if disk_state and not cloud_state:
        return RestorePickResult(disk_state, "disk", "cloud missing", cloud_ts, disk_ts)

    if local_dirty:
        return RestorePickResult(
            disk_state,
            "disk",
            "local unsaved edits",
            cloud_ts,
            disk_ts,
        )

    if cloud_first and cloud_state:
        return RestorePickResult(
            cloud_state,
            "cloud",
            "cloud-first workspace sync",
            cloud_ts,
            disk_ts,
        )

    if cloud_epoch > disk_epoch:
        return RestorePickResult(cloud_state, "cloud", "cloud newer", cloud_ts, disk_ts)
    if disk_epoch > cloud_epoch:
        return RestorePickResult(disk_state, "disk", "disk newer", cloud_ts, disk_ts)
    if prefer_cloud_on_tie:
        return RestorePickResult(cloud_state, "cloud", "tie → cloud", cloud_ts, disk_ts)
    return RestorePickResult(disk_state, "disk", "tie → disk", cloud_ts, disk_ts)


def pick_newer_session(
    cloud_state: dict[str, Any],
    cloud_ts: str | None,
    disk_state: dict[str, Any],
    disk_ts: str | None,
) -> dict[str, Any]:
    return pick_restore_session(
        cloud_state, cloud_ts, disk_state, disk_ts, local_dirty=False
    ).state


def session_page_summary(app_id: str, state: dict[str, Any]) -> tuple[str, str]:
    """Derive dashboard page + summary from a persisted session blob."""
    app_key = str(app_id or "").strip()
    if app_key == "baseball":
        page = str(state.get("active_page") or "")
        return page, page or "Baseball session"
    if app_key == "music":
        meta = state.get("music_workspace_state") if isinstance(state.get("music_workspace_state"), dict) else {}
        core = state.get("core") if isinstance(state.get("core"), dict) else state
        page = str(
            meta.get("studio_page")
            or (core or {}).get("studio_page")
            or (core or {}).get("page")
            or state.get("studio_page")
            or ""
        )
        song = str((core or {}).get("song") or state.get("song") or "")
        return page, song or page or "Music session"
    if app_key == "investment":
        tab = str(
            state.get("investment_active_tab")
            or state.get("health_active_tab")
            or state.get("experience")
            or ""
        )
        return tab, tab or "Portfolio session"
    if app_key == "future_lens":
        skill = str(state.get("specific_skill") or state.get("broad_domain") or "")
        year = state.get("sim_year")
        summary = skill
        if year is not None:
            summary = f"{skill} · {year}".strip(" ·")
        return str(state.get("_suite_fl_view") or "simulation"), summary or "Future Lens session"
    page = str(state.get("page") or "")
    return page, str(state.get("summary") or page or "Session")
