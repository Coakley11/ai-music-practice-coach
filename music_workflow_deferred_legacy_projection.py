"""Complete deferred compatibility projection at legal pre-widget / pre-lock points."""

from __future__ import annotations

from typing import Any

DEFERRED_LEGACY_PROJECTION_KEY = "_music_workflow_deferred_legacy_projection"
DEFERRED_LEGACY_PROJECTION_LAST_KEY = "_music_workflow_deferred_legacy_projection_last"


def try_complete_deferred_legacy_projection(session: dict[str, Any]) -> dict[str, str]:
    """Project canonical blob to legacy fields when widgets are not yet locked."""
    raw = session.get(DEFERRED_LEGACY_PROJECTION_KEY)
    if not isinstance(raw, dict) or not raw.get("owner"):
        return {"compatibility_projection": "NONE"}
    try:
        from session_widget_safe import widgets_likely_instantiated

        if widgets_likely_instantiated(session):
            session[DEFERRED_LEGACY_PROJECTION_LAST_KEY] = {
                "result": "STILL_DEFERRED",
                "reason": "widgets_locked",
                **raw,
            }
            return {"compatibility_projection": "DEFERRED"}
    except ImportError:
        if session.get("_streamlit_widgets_locked_this_run"):
            return {"compatibility_projection": "DEFERRED"}
    try:
        from music_workflow_legacy_projection import project_active_blob_to_legacy_session
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr is None:
            return {"compatibility_projection": "DEFERRED"}
        owner = str(raw.get("owner") or ptr.workflow_owner or "")
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        if blob is None:
            return {"compatibility_projection": "DEFERRED"}
        project_active_blob_to_legacy_session(session, blob)
        session.pop(DEFERRED_LEGACY_PROJECTION_KEY, None)
        session[DEFERRED_LEGACY_PROJECTION_LAST_KEY] = {
            "result": "SUCCESS",
            "owner": owner,
            "source": str(raw.get("source") or ""),
        }
        return {"compatibility_projection": "SUCCESS"}
    except Exception as exc:
        session[DEFERRED_LEGACY_PROJECTION_LAST_KEY] = {
            "result": "FAILED",
            "error": str(exc),
            **raw,
        }
        return {"compatibility_projection": "FAILED"}


__all__ = [
    "DEFERRED_LEGACY_PROJECTION_KEY",
    "DEFERRED_LEGACY_PROJECTION_LAST_KEY",
    "try_complete_deferred_legacy_projection",
]
