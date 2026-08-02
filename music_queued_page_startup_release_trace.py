"""Runtime trace for queued page_change startup release (?dev=1 diagnostics)."""

from __future__ import annotations

import inspect
from typing import Any

QUEUED_PAGE_STARTUP_RELEASE_IMPL = "QUEUED_PAGE_STARTUP_RELEASE_IMPL: 38664fc-v2"
QUEUED_PAGE_RELEASE_TRACE_KEY = "_music_queued_page_release_trace"


def _trace(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(QUEUED_PAGE_RELEASE_TRACE_KEY)
    if isinstance(raw, dict):
        return raw
    fresh: dict[str, Any] = {
        "queued_release_impl_marker": QUEUED_PAGE_STARTUP_RELEASE_IMPL,
        "events": [],
    }
    session[QUEUED_PAGE_RELEASE_TRACE_KEY] = fresh
    return fresh


def _fn_probe(fn: Any) -> dict[str, Any]:
    try:
        return {
            "queued_release_function_module": getattr(fn, "__module__", None),
            "queued_release_function_file": inspect.getfile(fn),
            "queued_release_function_line": inspect.getsourcelines(fn)[1],
        }
    except Exception as exc:
        return {"queued_release_function_probe_error": str(exc)}


def record_force_save_page_change_entry(session: dict[str, Any]) -> None:
    t = _trace(session)
    t.update(
        {
            "queued_release_impl_marker": QUEUED_PAGE_STARTUP_RELEASE_IMPL,
            "force_save_page_change_entry": True,
            "entry_hydrated_fp": session.get("hydrated_canonical_fingerprint"),
            "entry_post_restore_fp": session.get("post_restore_canonical_fingerprint"),
            "entry_startup_fingerprint_matches": session.get("startup_fingerprint_matches"),
            "entry_startup_revision_loaded": session.get("startup_revision_loaded"),
            "entry_startup_revision_final": session.get("startup_revision_final"),
            "entry_page_change_origin": session.get("music_page_change_origin"),
            "entry_user_nav_page_this_run": session.get("_music_user_navigated_page_this_run"),
        }
    )


def record_attempt_release_dispatch(
    session: dict[str, Any],
    *,
    attempt_fn: Any,
    release_fn: Any,
) -> None:
    t = _trace(session)
    t["queued_release_function_called"] = True
    t.update(_fn_probe(release_fn))
    t["attempt_release_function_module"] = getattr(attempt_fn, "__module__", None)
    t["attempt_release_function_file"] = (
        inspect.getfile(attempt_fn) if callable(attempt_fn) else None
    )


def record_release_function_body(
    session: dict[str, Any],
    *,
    phase: str,
    detail: dict[str, Any],
) -> None:
    t = _trace(session)
    t.setdefault("release_phases", []).append({"phase": phase, **detail})
    t.update({k: v for k, v in detail.items() if k.startswith("queued_release_")})


def record_attempt_release_result(
    session: dict[str, Any],
    *,
    return_value: bool,
    branch_selected: str,
    next_function: str,
) -> None:
    t = _trace(session)
    t["queued_release_return_value"] = return_value
    t["queued_release_branch_selected"] = branch_selected
    t["next_function_called_after_release"] = next_function
    t["suppression_state_immediately_after_release"] = session.get("startup_suppression_released")
    t["revision_immediately_after_release"] = session.get("startup_revision_final")


def record_finalize_fallback_blocked(session: dict[str, Any], *, stage: str) -> None:
    t = _trace(session)
    t["finalize_deferred_for_queued_page_change"] = True
    t["finalize_deferred_stage"] = stage


def record_finalize_fallback_entered(session: dict[str, Any], *, stage: str) -> None:
    t = _trace(session)
    t["queued_release_fell_back_to_old_finalize"] = True
    t["old_finalize_stage"] = stage


def build_queued_release_trace_copy(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(QUEUED_PAGE_RELEASE_TRACE_KEY)
    if not isinstance(raw, dict):
        return {"queued_release_impl_marker": QUEUED_PAGE_STARTUP_RELEASE_IMPL, "status": "no_trace"}
    return dict(raw)


__all__ = [
    "QUEUED_PAGE_STARTUP_RELEASE_IMPL",
    "QUEUED_PAGE_RELEASE_TRACE_KEY",
    "build_queued_release_trace_copy",
    "record_attempt_release_dispatch",
    "record_attempt_release_result",
    "record_finalize_fallback_blocked",
    "record_finalize_fallback_entered",
    "record_force_save_page_change_entry",
    "record_release_function_body",
]
