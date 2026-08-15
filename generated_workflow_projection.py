"""Project active generated workflow blob → legacy Creative/Style UI (read-only consumers)."""

from __future__ import annotations

import copy
from typing import Any


def _active_generated_blob(session: dict[str, Any], owner: str):
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == owner:
            blob = get_workflow_blob(session, owner, str(ptr.workflow_session_id or ""))
            return ptr, blob
    except ImportError:
        pass
    return None, None


def sync_style_jam_legacy_from_active_blob(
    session: dict[str, Any],
    *,
    writer: str,
    phase: str = "",
    include_controls: bool = True,
) -> bool:
    """Style Jam page/backing must not mix widget controls with stale improv_generated_sections."""
    _ptr, blob = _active_generated_blob(session, "style_jam")
    if blob is None:
        return False
    from music_theory import format_key_label_from_parts, key_center_token

    token = key_center_token(
        str(blob.keys.practice_tonic or "C"),
        str(blob.keys.practice_mode or "major"),
    )
    label = format_key_label_from_parts(
        str(blob.keys.practice_tonic or "C"),
        str(blob.keys.practice_mode or "major"),
    )
    session["improv_entry_mode"] = "Style Jam Mode"
    if include_controls:
        session["improv_style"] = str(blob.style or "").strip()
        session["improv_mood"] = str(blob.mood or "").strip()
        session["improv_groove"] = str(blob.groove or "").strip()
        if blob.tempo_bpm:
            session["improv_style_bpm"] = int(blob.tempo_bpm)
    session["improv_style_key"] = token
    if isinstance(blob.section_map, dict) and blob.section_map:
        session["improv_generated_sections"] = copy.deepcopy(blob.section_map)
    try:
        from workflow_key_identity import WorkflowKeyIdentity, apply_practice_key_identity_to_session

        ident = WorkflowKeyIdentity(
            workflow_owner="style_jam",
            workflow_session_id=str(blob.workflow_session_id or ""),
            practice_tonic=str(blob.keys.practice_tonic or "C"),
            practice_mode=str(blob.keys.practice_mode or "major"),
            practice_key_token=token,
            practice_label=label,
            source=f"sync_style_jam_legacy:{writer}",
        )
        apply_practice_key_identity_to_session(
            session,
            ident,
            source=f"sync_style_jam_legacy:{writer}",
            widget_safe=True,
        )
    except ImportError:
        session["improv_style_key"] = token
    try:
        from creative_key_sync import IMPROV_STYLE_KEY_TRACKER

        session[IMPROV_STYLE_KEY_TRACKER] = token
    except ImportError:
        pass
    session["_style_jam_legacy_projection_writer"] = f"{writer}:{phase}"
    return True


def project_generated_owner_from_active_blob(
    session: dict[str, Any],
    *,
    writer: str,
    include_controls: bool = True,
) -> bool:
    """Reconcile legacy Creative fields from the active generated workflow blob."""
    try:
        from workflow_key_identity import generated_workflow_owns_practice_key

        if not generated_workflow_owns_practice_key(session):
            return False
    except ImportError:
        return False
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        owner = str(ptr.workflow_owner or "") if ptr else ""
    except ImportError:
        return False
    if owner == "style_jam":
        return sync_style_jam_legacy_from_active_blob(
            session, writer=writer, phase="project_owner", include_controls=include_controls
        )
    if owner == "jam_session_generator":
        try:
            from improv_jam_session_projection import sync_improv_jam_session_from_active_blob

            return sync_improv_jam_session_from_active_blob(
                session,
                writer=writer,
                phase="project_owner",
            )
        except ImportError:
            return False
    return False


def style_jam_control_blob_drift(session: dict[str, Any]) -> dict[str, Any]:
    """Detect hybrid Style Jam UI (new controls vs old blob sections/style)."""
    out: dict[str, Any] = {"drift": False, "violations": []}
    _ptr, blob = _active_generated_blob(session, "style_jam")
    if blob is None:
        return out
    blob_style = str(blob.style or "").strip()
    live_style = str(session.get("improv_style") or "").strip()
    if blob_style and live_style and blob_style.lower() != live_style.lower():
        out["drift"] = True
        out["violations"].append(f"style:{live_style}!={blob_style}")
    gen = session.get("improv_generated_sections")
    if isinstance(gen, dict) and isinstance(blob.section_map, dict) and blob.section_map:
        if list(gen.keys()) != list(blob.section_map.keys()):
            out["drift"] = True
            out["violations"].append("section_names_mismatch")
    return out


__all__ = [
    "project_generated_owner_from_active_blob",
    "style_jam_control_blob_drift",
    "sync_style_jam_legacy_from_active_blob",
]
