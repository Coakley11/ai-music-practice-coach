"""RequiresPreWidgetActivation diagnostics — call stack and run context."""

from __future__ import annotations

import traceback
from typing import Any

PROJECTION_BLOCK_DIAG_KEY = "_music_projection_block_last"


def classify_projection_block_path(
    session: dict[str, Any],
    *,
    mutation_source: str = "",
    workflow_owner: str = "",
) -> str:
    """Best-effort path class from session flags and caller — not inferred from error text alone."""
    if session.get("_music_pre_widget_bootstrap_active"):
        return "pre_widget_bootstrap"
    if session.get("_music_pending_generated_key_edit"):
        return "pending_generated_key_consumer"
    if mutation_source in {"on_improv_style_key_change", "on_improv_jam_key_change"}:
        if session.get("_music_pre_widget_bootstrap_ran_this_run"):
            return "pending_generated_key_consumer"
        return "legacy_projection"
    src = str(mutation_source or "")
    if "restore" in src or session.get("_music_restore_phase_complete") is False:
        if "restore" in src or session.get("_suite_persist_restore_applied"):
            return "restore"
    if "sidebar" in src or "prepare_creative_sidebar" in src:
        return "sidebar_preparation"
    if "hydrate" in src or session.get("_music_workspace_blob_hydrated"):
        return "hydration"
    if "activate" in src or "activation" in src:
        return "ownership_activation"
    stack = " ".join(traceback.format_stack(limit=8)).lower()
    if "generated_jam_key_change" in stack or "consume_pending_generated_key" in stack:
        return "pending_generated_key_consumer"
    if "prepare_creative_sidebar" in stack:
        return "sidebar_preparation"
    if "sync_sidebar_creative" in stack:
        return "legacy_projection"
    if workflow_owner in {"style_jam", "jam_session_generator"}:
        return "legacy_projection"
    return "another_duplicate_path"


def record_requires_pre_widget_activation(
    session: dict[str, Any],
    exc: Any,
    *,
    path_class: str = "",
    mutation_source: str = "",
    workflow_owner: str = "",
    workflow_session_id: str = "",
) -> dict[str, Any]:
    stack = traceback.format_stack(limit=24)
    try:
        from music_run_lifecycle import current_run_phase

        phase = current_run_phase(session)
    except ImportError:
        phase = str(session.get("_music_run_phase_current") or "")
    owner = str(getattr(exc, "owner", "") or workflow_owner)
    if not path_class:
        path_class = classify_projection_block_path(
            session,
            mutation_source=mutation_source,
            workflow_owner=owner,
        )
    diag: dict[str, Any] = {
        "error": str(exc),
        "owner": owner,
        "field": str(getattr(exc, "field", "") or "display_key"),
        "path_class": path_class,
        "mutation_source": mutation_source or path_class,
        "workflow_owner": workflow_owner or owner,
        "workflow_session_id": workflow_session_id,
        "run_id": session.get("_music_script_run_id") or session.get("_music_script_browser_session_id"),
        "script_run_seq": session.get("_script_run_seq"),
        "run_phase": phase,
        "widgets_locked_flag": session.get("_streamlit_widgets_locked_this_run"),
        "pre_widget_bootstrap_last": session.get("_music_pre_widget_bootstrap_last"),
        "pre_widget_bootstrap_ran": session.get("_music_pre_widget_bootstrap_ran_this_run"),
        "first_widget_marker": session.get("_music_first_streamlit_widget"),
        "projection_call_chain": stack[-12:],
        "pending_generated_key_edit": bool(session.get("_music_pending_generated_key_edit")),
    }
    session[PROJECTION_BLOCK_DIAG_KEY] = diag
    return diag


__all__ = [
    "PROJECTION_BLOCK_DIAG_KEY",
    "classify_projection_block_path",
    "record_requires_pre_widget_activation",
]
