"""Minimal Mission backing click capture — queue typed intent only (no UI / navigation)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

MISSION_BACKING_CLICK_INTENT_KEY = "_music_mission_backing_click_intent"


def capture_mission_backing_click_intent(
    session: dict[str, Any],
    *,
    with_practice_lick: bool,
    mission: str,
    cur_chord: str,
    section_label: str,
    chord_idx: int,
    song_title: str,
    concert_key: str,
    display_key: str,
) -> None:
    session[MISSION_BACKING_CLICK_INTENT_KEY] = {
        "with_practice_lick": bool(with_practice_lick),
        "mission": str(mission or ""),
        "cur_chord": str(cur_chord or ""),
        "section_label": str(section_label or ""),
        "chord_idx": int(chord_idx),
        "song_title": str(song_title or ""),
        "concert_key": str(concert_key or ""),
        "display_key": str(display_key or ""),
    }
    session["improv_mission_backing_handoff"] = True


def peek_mission_backing_click_intent(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(MISSION_BACKING_CLICK_INTENT_KEY)
    return dict(raw) if isinstance(raw, dict) else None


def clear_mission_backing_click_intent(session: dict[str, Any]) -> None:
    session.pop(MISSION_BACKING_CLICK_INTENT_KEY, None)


def _click_intent_fingerprint(intent: dict[str, Any]) -> str:
    blob = json.dumps(intent, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def request_mission_backing_click_rerun(st_module: Any, session: dict[str, Any], intent: dict[str, Any]) -> bool:
    try:
        from music_app_rerun import request_app_rerun

        return bool(
            request_app_rerun(
                st_module,
                session,
                reason="mission_backing_click_intent",
                stage="mission_backing_callback",
                fingerprint=_click_intent_fingerprint(intent),
            )
        )
    except ImportError:
        return False


def apply_mission_backing_click_intent(session: dict[str, Any], *, st_module: Any | None = None) -> bool:
    """Expand captured click into alignment + deferred handoff queue (pre-widget or guarded rerun follow-up)."""
    intent = peek_mission_backing_click_intent(session)
    if not intent:
        return False
    clear_mission_backing_click_intent(session)
    with_lick = bool(intent.get("with_practice_lick"))
    try:
        from mission_backing_alignment import MISSION_PENDING_BACKING_ALIGNMENT_KEY, build_mission_backing_alignment_payload
    except ImportError:
        return False
    session[MISSION_PENDING_BACKING_ALIGNMENT_KEY] = build_mission_backing_alignment_payload(
        session,
        mission=str(intent.get("mission") or ""),
        cur_chord=str(intent.get("cur_chord") or ""),
        section_label=str(intent.get("section_label") or ""),
        chord_idx=int(intent.get("chord_idx") or 0),
        song_title=str(intent.get("song_title") or ""),
        concert_key=str(intent.get("concert_key") or ""),
        display_key=str(intent.get("display_key") or ""),
        with_practice_lick=with_lick,
    )
    if with_lick:
        try:
            from improvisation_missions import MISSION_EXAMPLE_KEY, queue_mission_practice_lick_handoff, store_mission_practice_lick_for_backing

            example = session.get(MISSION_EXAMPLE_KEY)
            if isinstance(example, dict):
                store_mission_practice_lick_for_backing(
                    session,
                    example=example,  # type: ignore[arg-type]
                    mission_title=str(intent.get("mission") or ""),
                    instrument=str(session.get("instrument") or "Piano"),
                    bpm=int(session.get("backing_track_bpm") or 100),
                    groove=str(session.get("improv_groove") or "Auto"),
                    meter=str(session.get("backing_time_signature") or "4/4"),
                    song_title=str(intent.get("song_title") or ""),
                    section_label=str(intent.get("section_label") or ""),
                    persist_artifact=False,
                )
                queue_mission_practice_lick_handoff(session)
        except ImportError:
            pass
    try:
        from music_workflow_mission_backing_orchestration import prepare_deferred_mission_backing_handoff
        from music_workflow_pending_backing_handoff import resolve_backing_workflow_owner

        if st_module is None:
            import streamlit as st_module  # type: ignore[assignment]

        return bool(
            prepare_deferred_mission_backing_handoff(
                st_module,
                session,
                backing_source="mission",
                workflow_owner=resolve_backing_workflow_owner(session, backing_source="mission"),
                with_practice_lick=with_lick,
                mission_alignment=session.get(MISSION_PENDING_BACKING_ALIGNMENT_KEY),
            )
        )
    except ImportError:
        return False


__all__ = [
    "MISSION_BACKING_CLICK_INTENT_KEY",
    "apply_mission_backing_click_intent",
    "capture_mission_backing_click_intent",
    "clear_mission_backing_click_intent",
    "peek_mission_backing_click_intent",
    "request_mission_backing_click_rerun",
]
