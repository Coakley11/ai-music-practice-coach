"""Canonical MissionExample normalization before display / Practice-in-Jam handoff."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any

from improvisation_missions import MissionExample, _fallback_chord_insight

_LOG = logging.getLogger("music.mission_example_normalize")

MISSION_EXAMPLE_NORMALIZE_DIAG_KEY = "_music_mission_example_normalize_diag"
MISSION_BACKING_EXAMPLE_ERROR_KEY = "_music_mission_backing_example_error"

ERROR_MISSING_MOTIF = "MISSION_EXAMPLE_MISSING_MOTIF"
ERROR_INVALID_SHAPE = "MISSION_EXAMPLE_INVALID_SHAPE"
ERROR_MISSING_CHORD = "MISSION_EXAMPLE_MISSING_CHORD"


@dataclass
class MissionExampleNormalizeResult:
    ok: bool
    example: MissionExample | None = None
    error_code: str = ""
    message: str = ""
    authoritative_concert_key: str = ""
    authoritative_display_key: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)


def resolve_authoritative_mission_keys(
    session: dict[str, Any],
    *,
    intent_concert_key: str = "",
    intent_display_key: str = "",
) -> tuple[str, str]:
    """Concert key from workflow blob / session; display from intent or session (not stale example fields)."""
    concert = str(intent_concert_key or session.get("concert_key") or session.get("practice_concert_key") or "").strip()
    display = str(intent_display_key or session.get("display_key") or "").strip()
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == "mission_jam":
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob and getattr(blob, "keys", None):
                tonic = str(blob.keys.practice_tonic or "").strip()
                mode = str(blob.keys.practice_mode or "major").strip().lower()
                if tonic:
                    concert = f"{tonic}m" if mode == "minor" else tonic
    except ImportError:
        pass
    if concert and not display:
        display = concert
    return concert, display


def _log_normalize_diag(session: dict[str, Any] | None, diag: dict[str, Any]) -> None:
    if session is not None:
        session[MISSION_EXAMPLE_NORMALIZE_DIAG_KEY] = diag
    _LOG.info(
        "[mission_example_normalize] type=%s class=%s keys=%s mission=%s chord=%s fp=%s source=%s",
        diag.get("raw_type"),
        diag.get("class_name"),
        diag.get("available_keys"),
        diag.get("mission_id"),
        diag.get("chord"),
        diag.get("material_fp"),
        diag.get("source"),
    )


def normalize_mission_example_for_display(
    raw_example: Any,
    *,
    session_state: dict[str, Any] | None = None,
    authoritative_concert_key: str = "",
    authoritative_display_key: str = "",
    instrument: str = "",
    level: str = "",
    focus: str = "",
    song_title: str = "",
    section: str = "",
    mission: str = "",
) -> MissionExampleNormalizeResult:
    session = session_state or {}
    concert, display = resolve_authoritative_mission_keys(
        session,
        intent_concert_key=authoritative_concert_key,
        intent_display_key=authoritative_display_key,
    )
    raw_type = type(raw_example).__name__
    available: list[str] = []
    source = "unknown"
    material_fp = ""
    if isinstance(raw_example, dict):
        available = sorted(str(k) for k in raw_example.keys())
        source = str(raw_example.get("source") or "session_dict")
        material_fp = str(raw_example.get("material_fp") or "")
    elif isinstance(raw_example, MissionExample):
        available = list(raw_example.__dataclass_fields__.keys())  # type: ignore[attr-defined]
        source = "mission_example_dataclass"
        material_fp = str(getattr(raw_example, "variant", "") or "")
    elif raw_example is not None:
        available = sorted(str(k) for k in getattr(raw_example, "__dict__", {}).keys())
        source = "object"

    diag_base = {
        "raw_type": raw_type,
        "class_name": raw_type,
        "available_keys": available,
        "mission_id": mission,
        "chord": "",
        "material_fp": material_fp,
        "source": source,
        "authoritative_concert_key": concert,
        "authoritative_display_key": display,
    }
    _log_normalize_diag(session, diag_base)

    if raw_example is None:
        return MissionExampleNormalizeResult(
            ok=False,
            error_code=ERROR_INVALID_SHAPE,
            message="No mission example is available for this chord.",
            diagnostics=diag_base,
        )

    if isinstance(raw_example, MissionExample):
        ex = raw_example
        chord = str(ex.chord or "").strip()
        motif = ex.motif if isinstance(ex.motif, dict) else {}
    elif isinstance(raw_example, dict):
        chord = str(raw_example.get("chord") or mission or "").strip()
        motif = dict(raw_example.get("motif") or {})
        if not mission:
            mission = str(raw_example.get("mission") or "")
        if not section:
            section = str(raw_example.get("section") or "")
        if not song_title:
            song_title = str(raw_example.get("song_title") or session.get("song") or "")
        try:
            from mission_pitch_spelling import chord_coach_insight_for_mission

            insight = chord_coach_insight_for_mission(
                chord,
                song_display_key=display or str(raw_example.get("display_key") or ""),
                song_key_center=concert or str(raw_example.get("concert_key") or ""),
                instrument=str(instrument or session.get("instrument") or "Piano"),
                level=str(level or session.get("level") or "Intermediate"),
            )
        except ImportError:
            insight = _fallback_chord_insight(chord)
        ex = MissionExample(
            mission=str(mission or raw_example.get("mission") or ""),
            variant=str(raw_example.get("variant") or "normal"),
            chord=chord,
            section=str(section or raw_example.get("section") or ""),
            song_title=str(song_title or ""),
            display_key=display or str(raw_example.get("display_key") or raw_example.get("key_center") or ""),
            concert_key=concert or str(raw_example.get("concert_key") or ""),
            instrument=str(instrument or raw_example.get("instrument") or session.get("instrument") or "Piano"),
            level=str(level or raw_example.get("level") or session.get("level") or "Intermediate"),
            focus=str(focus or raw_example.get("focus") or session.get("focus") or "Improvisation"),
            motif=motif,
            abc=str(raw_example.get("abc") or ""),
            tab=str(raw_example.get("tab") or ""),
            piano_html=str(raw_example.get("piano_html") or ""),
            why=str(raw_example.get("why") or ""),
            practice_steps=list(raw_example.get("practice_steps") or []),
            insight=insight,
            show_tab=bool(raw_example.get("show_tab")),
            show_piano=bool(raw_example.get("show_piano")),
        )
    else:
        return MissionExampleNormalizeResult(
            ok=False,
            error_code=ERROR_INVALID_SHAPE,
            message="Mission example is in an unsupported format.",
            diagnostics={**diag_base, "chord": ""},
        )

    if not chord:
        return MissionExampleNormalizeResult(
            ok=False,
            error_code=ERROR_MISSING_CHORD,
            message="Mission example is missing a chord.",
            diagnostics={**diag_base, "chord": chord},
        )
    if not motif or not list(motif.get("notes") or []):
        return MissionExampleNormalizeResult(
            ok=False,
            error_code=ERROR_MISSING_MOTIF,
            message="Generate an example on this mission before Practice in Backing Jam.",
            diagnostics={**diag_base, "chord": chord},
        )

    # Authoritative keys override stale example metadata.
    auth_concert = str(authoritative_concert_key or concert or "").strip()
    auth_display = str(authoritative_display_key or display or "").strip()
    if auth_concert and not auth_display:
        auth_display = auth_concert
    if auth_concert:
        final_concert = auth_concert
        final_display = auth_display or auth_concert
    else:
        final_concert = str(ex.concert_key or ex.display_key or "").strip()
        final_display = str(ex.display_key or ex.concert_key or final_concert).strip()

    ex = replace(
        ex,
        display_key=final_display,
        concert_key=final_concert,
        instrument=str(instrument or ex.instrument or "Piano"),
        level=str(level or ex.level or "Intermediate"),
        focus=str(focus or ex.focus or "Improvisation"),
    )

    diag_ok = {
        **diag_base,
        "chord": chord,
        "normalized_concert_key": ex.concert_key,
        "normalized_display_key": ex.display_key,
        "had_legacy_display_key": bool(isinstance(raw_example, dict) and raw_example.get("display_key")),
    }
    _log_normalize_diag(session, diag_ok)
    return MissionExampleNormalizeResult(
        ok=True,
        example=ex,
        authoritative_concert_key=str(ex.concert_key or ""),
        authoritative_display_key=str(ex.display_key or ""),
        diagnostics=diag_ok,
    )


__all__ = [
    "ERROR_INVALID_SHAPE",
    "ERROR_MISSING_CHORD",
    "ERROR_MISSING_MOTIF",
    "MISSION_BACKING_EXAMPLE_ERROR_KEY",
    "MISSION_EXAMPLE_NORMALIZE_DIAG_KEY",
    "MissionExampleNormalizeResult",
    "normalize_mission_example_for_display",
    "resolve_authoritative_mission_keys",
]
