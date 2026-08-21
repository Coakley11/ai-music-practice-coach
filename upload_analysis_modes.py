"""Upload Analysis workflow mode labels and backward-compatible session values."""

from __future__ import annotations

from typing import Any

SINGLE_RECORDING = "Single recording"
MULTITRACK_RECORDING = "Multitrack recording"
MULTITRACK_RECORDING_LEGACY = "Multitrack comparison"

WORKFLOW_OPTIONS: tuple[str, ...] = (SINGLE_RECORDING, MULTITRACK_RECORDING)


def normalize_analysis_workflow(session_state: dict[str, Any]) -> None:
    """Map legacy stored values to current user-facing workflow labels."""
    mode = str(session_state.get("analysis_mode") or "").strip()
    if mode == MULTITRACK_RECORDING_LEGACY:
        session_state["analysis_mode"] = MULTITRACK_RECORDING


def is_multitrack_workflow(session_state: dict[str, Any]) -> bool:
    mode = str(session_state.get("analysis_mode") or SINGLE_RECORDING).strip()
    return mode in (MULTITRACK_RECORDING, MULTITRACK_RECORDING_LEGACY)


def recording_type_options_for_session(session_state: dict[str, Any]) -> tuple[str, ...]:
    """Recording types allowed for the current Workflow selection."""
    from recording_analysis_context import recording_types_for_workflow

    return recording_types_for_workflow(
        MULTITRACK_RECORDING if is_multitrack_workflow(session_state) else SINGLE_RECORDING
    )
