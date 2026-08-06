"""Commit generated Style Jam / Jam Session into authoritative workflow store."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
from music_workflow_compatibility import _tonic_mode_from_token
from music_workflow_mutation import mutate_active_workflow
from music_workflow_state_store import KeyAuthority, WorkflowStateBlob, get_active_workflow_pointer, save_workflow_blob


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


__all__ = ["commit_jam_session_generation", "commit_style_jam_generation"]
