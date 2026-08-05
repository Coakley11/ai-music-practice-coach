"""Clear stale derived mission/notation/backing projection after authoritative key change."""

from __future__ import annotations

from typing import Any


def invalidate_key_dependent_session_projections(session: dict[str, Any], *, owner: str) -> list[str]:
    cleared: list[str] = []
    for key in (
        "_mission_example_output_fp",
        "improv_mission_example",
        "_mission_exact_backing_armed",
        "improv_mission_backing_handoff",
        "improv_mission_recording_seal",
        "_mission_notation_display_cache",
        "_mission_chord_spelling_cache",
        "_creative_mission_abc_cache",
        "_creative_mission_musicxml_cache",
    ):
        if session.pop(key, None) is not None:
            cleared.append(key)
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        if session.pop(MISSION_EXAMPLE_KEY, None) is not None:
            cleared.append(MISSION_EXAMPLE_KEY)
    except ImportError:
        pass
    if owner in {"mission_jam", "song_based_improvisation", "style_jam", "jam_session_generator"}:
        for key in ("_backing_context_cache", "_canonical_artifact_projection_cache"):
            if session.pop(key, None) is not None:
                cleared.append(key)
        try:
            from songs.key_state import invalidate_backing_cache

            invalidate_backing_cache(session)
            cleared.append("backing_audio_fingerprint")
        except ImportError:
            pass
        try:
            from mission_exact_chord_backing import invalidate_exact_chord_backing_cache

            invalidate_exact_chord_backing_cache(session)
            cleared.append("exact_chord_backing_cache")
        except ImportError:
            pass
    return cleared


__all__ = ["invalidate_key_dependent_session_projections"]
