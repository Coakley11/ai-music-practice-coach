"""Hand off mission captures to Upload Analysis (no analysis on Missions page)."""

from __future__ import annotations

from typing import Any

from upload_media import PreparedUpload

MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY = "_mission_upload_analysis_handoff"

def _default_analysis_metric_ids_for_focus(focus: str) -> list[str]:
    try:
        from mission_analysis import MISSION_BY_ID
    except ImportError:
        return []
    label = str(focus or "").strip().lower()
    mapping = {
        "overall mission execution": "mission_completion",
        "phrasing": "phrase_structure",
        "melodic development": "melodic_diversity_goal",
        "motif development": "motif_development",
        "rhythmic variety": "rhythmic_diversity",
        "use of space": "space_silence",
        "chord-tone targeting": "chord_tone_targeting",
        "harmonic fit": "deep_harmony",
    }
    for key, mid in mapping.items():
        if key in label and mid in MISSION_BY_ID:
            return [mid]
    return []


def handoff_mission_take_to_upload_analysis(
    session: dict[str, Any],
    *,
    audio_bytes: bytes,
    filename: str,
    source: str,
    st: Any | None = None,
) -> tuple[bool, str]:
    """Preload take + mission context; leave AI criteria editable on Upload Analysis."""
    from mission_analysis_ui import (
        ANALYSIS_CRITERIA_LOCKED,
        clear_analysis_workflow_flags,
        prepare_mission_upload_from_missions,
    )

    try:
        from media_multitrack_export_catalog import clear_upload_analysis_prepared_recording
    except ImportError:

        def clear_upload_analysis_prepared_recording(_s: dict[str, Any]) -> None:
            return None

    try:
        from mission_evaluation_focus import authoritative_evaluation_focus
    except ImportError:
        authoritative_evaluation_focus = lambda _s: ""  # type: ignore[assignment,misc]

    clear_upload_analysis_prepared_recording(session)
    session.pop("last_analysis_result", None)
    prepared = PreparedUpload(bytes(audio_bytes), str(filename or "mission_take.wav"))
    session["_analysis_prepared_upload"] = prepared
    session["last_analysis_audio"] = bytes(audio_bytes)
    session["last_analysis_source_label"] = prepared.name
    session["analysis_mode"] = "Single recording"
    session["analysis_recording_type"] = "Mission Recording"
    session["mission_upload_capture_mode"] = source
    session["_mission_upload_handoff_source"] = source
    session["_mission_upload_is_live_take"] = source == "live"
    session["_mission_upload_is_file_take"] = source == "upload"

    try:
        from recording_analysis_context import apply_mission_recording_defaults

        apply_mission_recording_defaults(session)
    except ImportError:
        pass

    prepare_mission_upload_from_missions(session)
    clear_analysis_workflow_flags(session)
    session[MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY] = True
    session["analysis_sync_creative_mission"] = True

    try:
        from mission_upload_metrics import seed_upload_metrics_from_mission_handoff

        seed_upload_metrics_from_mission_handoff(session)
    except ImportError:
        focus = authoritative_evaluation_focus(session)
        default_ids = _default_analysis_metric_ids_for_focus(focus)
        if default_ids:
            session.setdefault("analysis_ai_metric_ids", list(default_ids))
            session.setdefault("analysis_mission_ids", list(default_ids))

    try:
        from mission_practice_context import MISSION_RECORDING_STUDIO_ENGAGED_KEY

        session[MISSION_RECORDING_STUDIO_ENGAGED_KEY] = True
    except ImportError:
        pass

    try:
        from mission_pending_upload_persistence import persist_mission_pending_upload_handoff

        mixed = session.get("_mission_live_mic_mixed")
        mixed_opt = bytes(mixed) if isinstance(mixed, (bytes, bytearray)) and mixed != audio_bytes else None
        diag = persist_mission_pending_upload_handoff(
            session,
            dry_bytes=bytes(audio_bytes),
            mixed_bytes=mixed_opt,
            filename=str(filename or "mission_live_take.wav"),
            st=st,
        )
        write_state = str(diag.get("persistence_write") or "")
        if write_state != "ok" or not diag.get("cloud_confirmed"):
            msg = write_state or "cloud_save_unconfirmed"
            session.pop("_navigate_to_studio_page", None)
            return False, msg
        session["_navigate_to_studio_page"] = "analysis"
        return True, ""
    except ImportError:
        session["_navigate_to_studio_page"] = "analysis"
        return True, ""


def release_stale_mission_upload_identity_on_songs_leave(session: dict[str, Any]) -> bool:
    """Songs Catalog/Custom/Composition selection leaves Mission recording ownership.

    Clears the Upload identity lock and active Mission→Upload pending handoff so
    Upload follows the selected song. Does **not** delete Practice Log / library
    Mission recordings or Mission evaluation-criteria definitions (metric catalogs).
    """
    had_handoff = bool(session.get(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY))
    had_envelope = False
    try:
        from mission_pending_upload_persistence import (
            PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY,
            clear_prepared_mission_upload,
        )

        had_envelope = bool(session.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY))
        cws = session.get("creative_workspace_state")
        if isinstance(cws, dict) and cws.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY):
            had_envelope = True
        # No ``st`` → clear session/canonical pending handoff without a cloud force-save.
        clear_prepared_mission_upload(session, st=None)
    except ImportError:
        session.pop(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY, None)
        session.pop("_analysis_prepared_upload", None)
        session.pop("last_analysis_audio", None)

    session.pop(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY, None)
    session.pop("_mission_upload_handoff_source", None)
    session.pop("_mission_upload_is_live_take", None)
    session.pop("_mission_upload_is_file_take", None)
    session.pop("mission_upload_capture_mode", None)
    # Explicit False so studio defaults do not re-bind ambient Creative mission.
    session["analysis_sync_creative_mission"] = False

    try:
        from recording_analysis_context import (
            ANALYSIS_IDENTITY_LOCKED_KEY,
            RECORDING_TYPE_PRACTICE,
            is_mission_recording_type,
        )

        session.pop(ANALYSIS_IDENTITY_LOCKED_KEY, None)
        if is_mission_recording_type(session.get("analysis_recording_type")):
            session["analysis_recording_type"] = RECORDING_TYPE_PRACTICE
    except ImportError:
        session.pop("analysis_identity_locked", None)
        if str(session.get("analysis_recording_type") or "").strip().lower() in {
            "mission recording",
            "mission",
        }:
            session["analysis_recording_type"] = "Practice take"

    try:
        from mission_analysis_ui import ANALYSIS_CRITERIA_LOCKED

        session.pop(ANALYSIS_CRITERIA_LOCKED, None)
    except ImportError:
        session.pop("analysis_criteria_locked", None)

    return had_handoff or had_envelope


__all__ = [
    "MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY",
    "handoff_mission_take_to_upload_analysis",
    "release_stale_mission_upload_identity_on_songs_leave",
]
