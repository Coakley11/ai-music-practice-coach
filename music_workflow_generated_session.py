"""Commit generated Style Jam / Jam Session into authoritative workflow store."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
from music_workflow_compatibility import _tonic_mode_from_token
from music_workflow_mutation import mutate_active_workflow
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    get_workflow_blob,
    save_workflow_blob,
)


def resolve_generated_concert_key_for_owner(session: dict[str, Any], owner: str) -> str:
    """Concert key from live widget / pending hydrate — not stale session defaults."""
    if owner == "jam_session_generator":
        try:
            from creative_session_state import _live_jam_session_fields

            _style, concert, _bpm, _mood = _live_jam_session_fields(session)
            if concert:
                return concert
        except ImportError:
            pass
        return str(session.get("improv_jam_key") or "C").strip() or "C"
    try:
        from creative_key_sync import PENDING_IMPROV_STYLE_KEY

        pending = session.get(PENDING_IMPROV_STYLE_KEY)
        if pending is not None:
            tok = str(pending).strip()
            if tok:
                return tok
    except ImportError:
        pending = session.get("_pending_improv_style_key")
        if pending is not None:
            tok = str(pending).strip()
            if tok:
                return tok
    return str(session.get("improv_style_key") or "C").strip() or "C"


def seal_jam_session_musical_context(
    jam: dict[str, Any],
    *,
    key_center: str,
    sections: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Align jam snapshot metadata with sealed concert key and section progressions."""
    out = copy.deepcopy(jam)
    k = str(key_center or out.get("key") or "C").strip() or "C"
    out["key"] = k
    if sections is not None:
        out["sections"] = copy.deepcopy(sections)
    ensemble = str(out.get("ensemble") or "Jazz trio")
    style = str(out.get("style") or "Jazz Swing")
    try:
        tempo = int(out.get("bpm") or 110)
    except (TypeError, ValueError):
        tempo = 110
    atmosphere = str(out.get("atmosphere") or out.get("mood") or "Mellow")
    out["prompt"] = f"**{ensemble}** in **{k}** · {style} · ~{tempo} BPM · {atmosphere}."
    return out


def finalize_generated_jam_session_key_seal(session: dict[str, Any], key_center: str) -> None:
    """After generate or authoritative key change — one sealed jam + sidebar ownership."""
    k = str(key_center or "C").strip() or "C"
    sections: dict[str, list[str]] | None = None
    try:
        ptr = get_active_workflow_pointer(session)
        if ptr and ptr.workflow_owner == "jam_session_generator":
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob is not None and isinstance(blob.section_map, dict) and blob.section_map:
                sections = copy.deepcopy(blob.section_map)
    except Exception:
        pass
    jam = session.get("improv_jam_session")
    if isinstance(jam, dict):
        session["improv_jam_session"] = seal_jam_session_musical_context(
            jam,
            key_center=k,
            sections=sections if sections is not None else jam.get("sections"),
        )
    session["improv_jam_key"] = k
    try:
        from improv_jam_session_projection import sync_improv_jam_session_from_active_blob

        sync_improv_jam_session_from_active_blob(
            session, writer="finalize_generated_jam_session_key_seal", phase="post_seal"
        )
    except ImportError:
        pass
    try:
        from generated_jam_key_context import activate_generated_jam_key_ownership

        activate_generated_jam_key_ownership(
            session,
            entry_mode="Jam Session Generator",
            practice_key=k,
        )
    except ImportError:
        pass
    try:
        from creative_key_sync import sync_creative_style_jam_meta

        sync_creative_style_jam_meta(session)
    except ImportError:
        pass


def finalize_generated_style_jam_key_seal(session: dict[str, Any], key_center: str) -> None:
    k = str(key_center or "C").strip() or "C"
    session["improv_style_key"] = k
    try:
        from generated_jam_key_context import activate_generated_jam_key_ownership

        activate_generated_jam_key_ownership(session, entry_mode="Style Jam Mode", practice_key=k)
    except ImportError:
        pass
    try:
        from creative_key_sync import sync_creative_style_jam_meta

        sync_creative_style_jam_meta(session)
    except ImportError:
        pass


def commit_style_jam_generation(
    session: dict[str, Any],
    *,
    key_center: str,
    style: str,
    section_map: dict[str, list[str]],
    mood: str = "",
    groove: str = "",
    tempo_bpm: int = 0,
    new_session: bool = False,
) -> bool:
    style_id = str(session.get("improv_style") or style or "style_jam").strip() or "style_jam"
    ptr = get_active_workflow_pointer(session)
    sid = style_id
    if ptr and ptr.workflow_owner == "style_jam" and not new_session:
        sid = ptr.workflow_session_id or sid
    pt, pm = _tonic_mode_from_token(key_center)

    def _mut(b: WorkflowStateBlob) -> None:
        b.keys = KeyAuthority(
            original_tonic=pt,
            original_mode=pm,
            practice_tonic=pt,
            practice_mode=pm,
            key_owner="style_jam",
        )
        b.style = style_id
        b.section_map = copy.deepcopy(section_map)
        b.mood = mood
        b.groove = groove
        if tempo_bpm:
            b.tempo_bpm = int(tempo_bpm)
        b.generated_session_id = sid
        b.source_type = "generated"

    if ptr and ptr.workflow_owner == "style_jam" and ptr.workflow_session_id == sid:
        result = mutate_active_workflow(session, _mut, mutation_type="style_jam_generate", source="generate_progression")
        return result.ok
    blob = WorkflowStateBlob(
        workflow_owner="style_jam",
        workflow_session_id=sid,
        keys=KeyAuthority(practice_tonic=pt, practice_mode=pm, original_tonic=pt, original_mode=pm),
        style=style_id,
        section_map=copy.deepcopy(section_map),
        generated_session_id=sid,
        source_type="generated",
        mood=mood,
        groove=groove,
        tempo_bpm=int(tempo_bpm or 0),
    )
    save_workflow_blob(session, blob, source="style_jam_generate")
    act = activate_workflow(
        session,
        ActivateWorkflowRequest(
            target_owner="style_jam",
            target_session_id=sid,
            activation_source="style_jam_generate",
            navigation_intent="creative_entry",
            incoming_blob=blob,
        ),
    )
    return act.ok


def commit_jam_session_generation(
    session: dict[str, Any],
    jam: dict[str, Any],
    *,
    key_center: str,
    style: str = "",
    new_session: bool = False,
) -> bool:
    jam = copy.deepcopy(jam)
    sid = str(jam.get("id") or "").strip()
    if new_session or not sid:
        sid = str(uuid.uuid4())
        jam["id"] = sid
    pt, pm = _tonic_mode_from_token(key_center)
    sections = jam.get("sections") if isinstance(jam.get("sections"), dict) else {}
    jam = seal_jam_session_musical_context(jam, key_center=key_center, sections=sections)
    sections = jam.get("sections") if isinstance(jam.get("sections"), dict) else {}

    def _mut(b: WorkflowStateBlob) -> None:
        b.keys = KeyAuthority(
            original_tonic=pt,
            original_mode=pm,
            practice_tonic=pt,
            practice_mode=pm,
            key_owner="jam_session_generator",
        )
        b.generated_session_id = sid
        b.style = str(style or session.get("improv_jam_style") or "")
        b.mood = str(session.get("improv_jam_mood") or b.mood or "Mellow")
        b.section_map = copy.deepcopy(sections)
        b.source_type = "generated"

    ptr = get_active_workflow_pointer(session)
    if ptr and ptr.workflow_owner == "jam_session_generator" and ptr.workflow_session_id == sid and not new_session:
        try:
            from improv_jam_session_projection import set_improv_jam_session

            set_improv_jam_session(session, jam, writer="commit_jam_session_generation", phase="mutate")
        except ImportError:
            session["improv_jam_session"] = jam
        result = mutate_active_workflow(session, _mut, mutation_type="jam_session_generate", source="generate_jam")
        return result.ok
    blob = WorkflowStateBlob(
        workflow_owner="jam_session_generator",
        workflow_session_id=sid,
        keys=KeyAuthority(practice_tonic=pt, practice_mode=pm, original_tonic=pt, original_mode=pm),
        generated_session_id=sid,
        style=str(style or ""),
        mood=str(session.get("improv_jam_mood") or "Mellow"),
        section_map=copy.deepcopy(sections),
        source_type="generated",
    )
    save_workflow_blob(session, blob, source="jam_session_generate")
    try:
        from improv_jam_session_projection import set_improv_jam_session

        set_improv_jam_session(session, jam, writer="commit_jam_session_generation", phase="new_session")
    except ImportError:
        session["improv_jam_session"] = jam
    act = activate_workflow(
        session,
        ActivateWorkflowRequest(
            target_owner="jam_session_generator",
            target_session_id=sid,
            activation_source="jam_session_generate",
            navigation_intent="creative_entry",
            incoming_blob=blob,
        ),
    )
    return act.ok


__all__ = [
    "commit_jam_session_generation",
    "commit_style_jam_generation",
    "finalize_generated_jam_session_key_seal",
    "finalize_generated_style_jam_key_seal",
    "resolve_generated_concert_key_for_owner",
    "seal_jam_session_musical_context",
]
