"""Pre-widget Style Jam / Generator generation consumers."""

from __future__ import annotations

import uuid
from typing import Any, Literal

PENDING_GENERATED_PROGRESSION_KEY = "_music_pending_generated_progression"
PENDING_GENERATED_PROGRESSION_DIAG_KEY = "_music_pending_generated_progression_diag"

GeneratedOwner = Literal["style_jam", "jam_session_generator"]


def queue_generated_progression_intent(
    session: dict[str, Any],
    *,
    owner: GeneratedOwner,
    request_token: str | None = None,
) -> None:
    session[PENDING_GENERATED_PROGRESSION_KEY] = {
        "owner": owner,
        "request_token": request_token or str(uuid.uuid4()),
    }


def peek_pending_generated_progression(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(PENDING_GENERATED_PROGRESSION_KEY)
    return dict(raw) if isinstance(raw, dict) else None


def consume_pending_generated_progression(session: dict[str, Any], *, st: Any | None = None) -> str:
    pending = peek_pending_generated_progression(session)
    if not pending:
        return "idle"
    owner = str(pending.get("owner") or "").strip()
    token = str(pending.get("request_token") or "")
    session.pop(PENDING_GENERATED_PROGRESSION_KEY, None)
    try:
        if owner == "style_jam":
            from improvisation_intelligence import generate_style_progression
            from music_workflow_generated_session import (
                commit_style_jam_generation,
                finalize_generated_style_jam_key_seal,
                resolve_generated_concert_key_for_owner,
            )

            style = str(session.get("improv_style") or "Jazz Swing")
            k = resolve_generated_concert_key_for_owner(session, "style_jam")
            sections = generate_style_progression(
                style=style,
                key_center=k,
                difficulty=str(session.get("improv_difficulty") or "Intermediate"),
                mood=str(session.get("improv_mood") or "Mellow"),
            )
            session["improv_generated_sections"] = sections
            commit_style_jam_generation(
                session,
                key_center=k,
                style=style,
                section_map=dict(sections or {}),
                mood=str(session.get("improv_mood") or ""),
                groove=str(session.get("improv_groove") or ""),
                tempo_bpm=int(session.get("improv_style_bpm") or 0),
                new_session=True,
            )
            try:
                from generated_workflow_artifact import commit_generated_artifact_revision

                commit_generated_artifact_revision(session, owner="style_jam", generation_request_token=token)
            except ImportError:
                pass
            try:
                from creative_key_sync import apply_creative_concert_key

                finalize_generated_style_jam_key_seal(session, k)
                apply_creative_concert_key(session, k, st_like=st)
            except ImportError:
                pass
        elif owner == "jam_session_generator":
            from improvisation_intelligence import generate_jam_session
            from music_workflow_generated_session import (
                commit_jam_session_generation,
                finalize_generated_jam_session_key_seal,
                resolve_generated_concert_key_for_owner,
            )

            ensemble = str(
                session.get("improv_ensemble") or session.get("improv_jam_ensemble") or "Jazz trio"
            )
            style = str(session.get("improv_jam_style") or "Jazz Swing")
            try:
                from jam_generator_live_runtime_trace import record_jam_pre_generate_trace

                record_jam_pre_generate_trace(session, token=token)
            except ImportError:
                pass
            key_c = resolve_generated_concert_key_for_owner(session, "jam_session_generator")
            jam_mood = str(session.get("improv_jam_mood") or "Mellow")
            jam = generate_jam_session(
                ensemble=ensemble,
                style=style,
                key_center=key_c,
                tempo=int(session.get("improv_jam_bpm") or 110),
                mood=jam_mood,
            )
            session["improv_jam_session"] = jam
            commit_jam_session_generation(
                session,
                jam if isinstance(jam, dict) else {},
                key_center=key_c,
                style=style,
                new_session=True,
            )
            session["improv_jam_mood"] = jam_mood
            session["improv_jam_style"] = style
            session["improv_jam_key"] = key_c
            try:
                from generated_workflow_artifact import commit_generated_artifact_revision

                commit_generated_artifact_revision(session, owner="jam_session_generator", generation_request_token=token)
            except ImportError:
                pass
            try:
                from creative_key_sync import apply_creative_concert_key

                finalize_generated_jam_session_key_seal(session, key_c)
                apply_creative_concert_key(session, key_c, st_like=st)
            except ImportError:
                pass
            try:
                from improv_jam_session_projection import sync_improv_jam_session_from_active_blob

                sync_improv_jam_session_from_active_blob(
                    session, writer="post_generate_consume", phase="jam_session_generator"
                )
            except ImportError:
                pass
            try:
                from creative_session_state import sync_creative_session_from_session

                sync_creative_session_from_session(session)
            except ImportError:
                pass
            try:
                from jam_generator_live_runtime_trace import record_jam_post_generate_trace

                record_jam_post_generate_trace(session, key_c=key_c, owner=owner, token=token)
            except ImportError:
                pass
        else:
            session[PENDING_GENERATED_PROGRESSION_DIAG_KEY] = {"status": "unknown_owner", "owner": owner}
            return "unknown_owner"
    except Exception as exc:
        session[PENDING_GENERATED_PROGRESSION_DIAG_KEY] = {"status": "fail", "owner": owner, "error": str(exc)}
        return f"fail:{exc}"
    session[PENDING_GENERATED_PROGRESSION_DIAG_KEY] = {"status": "done", "owner": owner, "token": token}
    return "done"


__all__ = [
    "PENDING_GENERATED_PROGRESSION_DIAG_KEY",
    "PENDING_GENERATED_PROGRESSION_KEY",
    "consume_pending_generated_progression",
    "peek_pending_generated_progression",
    "queue_generated_progression_intent",
]
