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


def commit_style_jam_control_settings(session: dict[str, Any]) -> bool:
    """Write Style / Mood / Groove / BPM / difficulty from widgets into the generated blob.

    Widget values are the user intent. Do not project the old blob over them first.
    """
    entry = str(session.get("improv_entry_mode") or "").strip()
    owner = "jam_session_generator" if entry == "Jam Session Generator" else "style_jam"
    if entry == "Jam Session Generator":
        style = str(session.get("improv_jam_style") or "").strip()
        mood = str(session.get("improv_jam_mood") or "").strip()
        groove = str(session.get("improv_groove") or "").strip()
        try:
            tempo = int(session.get("improv_jam_bpm") or 0)
        except (TypeError, ValueError):
            tempo = 0
    else:
        style = str(session.get("improv_style") or "").strip()
        mood = str(session.get("improv_mood") or "").strip()
        groove = str(session.get("improv_groove") or "").strip()
        try:
            tempo = int(session.get("improv_style_bpm") or 0)
        except (TypeError, ValueError):
            tempo = 0
    difficulty = str(session.get("improv_difficulty") or "").strip()
    meter = str(session.get("improv_style_meter") or session.get("backing_time_signature") or "").strip()
    ptr = get_active_workflow_pointer(session)
    if ptr is None or str(ptr.workflow_owner or "") != owner:
        try:
            from generated_jam_key_change import align_generated_workflow_pointer_for_key_edit

            align_generated_workflow_pointer_for_key_edit(session, owner)
            ptr = get_active_workflow_pointer(session)
        except ImportError:
            pass
    if ptr is None or str(ptr.workflow_owner or "") != owner:
        try:
            from music_workflow_compatibility import build_workflow_blob_from_legacy, legacy_session_id_for_owner
            from music_workflow_state_store import ActiveWorkflowPointer, set_active_workflow_pointer

            sid = str(legacy_session_id_for_owner(session, owner) or "").strip()
            if not sid:
                sid = str(uuid.uuid4()) if owner == "jam_session_generator" else (style or "style_jam")
            blob = build_workflow_blob_from_legacy(session, owner)
            blob.workflow_owner = owner
            blob.workflow_session_id = sid
            save_workflow_blob(session, blob, source="style_jam_control_settings_align")
            set_active_workflow_pointer(
                session,
                ActiveWorkflowPointer(workflow_owner=owner, workflow_session_id=sid),
                source="style_jam_control_settings_align",
            )
            ptr = get_active_workflow_pointer(session)
        except ImportError:
            pass
    if ptr is None or str(ptr.workflow_owner or "") != owner:
        return False

    def _mut(b: WorkflowStateBlob) -> None:
        if style:
            b.style = style
        if mood:
            b.mood = mood
        if groove:
            b.groove = groove
        if tempo:
            b.tempo_bpm = int(tempo)
        if meter:
            b.meter = meter
        _ = difficulty

    result = mutate_active_workflow(
        session,
        _mut,
        mutation_type="style_jam_control_settings",
        source="on_improv_style_jam_setting_change",
        expected_owner=owner,
    )
    return bool(result.ok)


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
    try:
        from generated_jam_key_context import snapshot_song_practice_key_if_needed

        snapshot_song_practice_key_if_needed(session)
    except ImportError:
        pass
    style_id = str(style or session.get("improv_style") or "style_jam").strip() or "style_jam"
    ptr = get_active_workflow_pointer(session)
    sid = style_id
    if ptr and ptr.workflow_owner == "style_jam" and not new_session:
        sid = ptr.workflow_session_id or sid
    session["_style_jam_workflow_session_id"] = sid
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
    try:
        tempo_bpm = int(session.get("improv_jam_bpm") or jam.get("bpm") or 0)
    except (TypeError, ValueError):
        tempo_bpm = 0
    mood = str(jam.get("mood") or jam.get("atmosphere") or session.get("improv_jam_mood") or "Mellow")
    groove = str(session.get("improv_groove") or jam.get("style") or style or "")

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
        b.mood = mood
        b.groove = groove
        if tempo_bpm:
            b.tempo_bpm = int(tempo_bpm)
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
        mood=mood,
        groove=groove,
        tempo_bpm=int(tempo_bpm or 0),
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


def align_generated_session_to_declared_concert_key(session: dict[str, Any]) -> bool:
    """Retranspose generated sections onto the declared jam Concert Key before seal.

    Keeps snapshot validation strict: the generated session must be internally
    consistent (complete Concert Key + matching progression) before Backing
    rebuilds from it.
    """
    entry = str(session.get("improv_entry_mode") or "").strip()
    owner = "jam_session_generator" if entry == "Jam Session Generator" else "style_jam"
    declared = resolve_generated_concert_key_for_owner(session, owner)
    ptr = get_active_workflow_pointer(session)
    blob = None
    if ptr is not None and str(ptr.workflow_owner or "") in {"style_jam", "jam_session_generator"}:
        owner = str(ptr.workflow_owner or owner)
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        if blob is not None:
            try:
                from music_theory import key_center_token

                blob_token = key_center_token(
                    str(blob.keys.practice_tonic or "C"),
                    str(blob.keys.practice_mode or "major"),
                )
            except ImportError:
                blob_token = str(blob.keys.practice_tonic or "")
            if not declared:
                declared = blob_token
    if not declared:
        return False
    sections: dict[str, list[str]] = {}
    if blob is not None and isinstance(blob.section_map, dict) and blob.section_map:
        sections = copy.deepcopy(blob.section_map)
    elif owner == "jam_session_generator":
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict) and isinstance(jam.get("sections"), dict):
            sections = copy.deepcopy(jam.get("sections") or {})
    else:
        raw = session.get("improv_generated_sections")
        if isinstance(raw, dict) and raw:
            sections = copy.deepcopy(raw)
    if not sections:
        return False
    try:
        from creative_key_sync import retranspose_generated_sections
        from improvisation_intelligence import flatten_sections
        from musical_context_coherence import infer_major_tonic_from_progression
        from music_theory import normalize_root, semitone_distance, split_chord
    except ImportError:
        return False
    flat = flatten_sections(sections)
    inferred = infer_major_tonic_from_progression(flat)
    if not inferred:
        return True
    inf_root = normalize_root(split_chord(inferred)[0])
    dest_root = normalize_root(split_chord(str(declared))[0])
    if not inf_root or not dest_root or semitone_distance(inf_root, dest_root) == 0:
        return True
    aligned = retranspose_generated_sections(sections, from_key=inferred, to_key=str(declared))
    if owner == "jam_session_generator":
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict):
            session["improv_jam_session"] = seal_jam_session_musical_context(
                jam, key_center=str(declared), sections=aligned
            )
        else:
            session["improv_generated_sections"] = aligned
    else:
        session["improv_generated_sections"] = aligned
    if blob is not None:
        from music_workflow_compatibility import _tonic_mode_from_token

        pt, pm = _tonic_mode_from_token(str(declared))
        blob.keys = KeyAuthority(
            original_tonic=str(blob.keys.original_tonic or pt),
            original_mode=str(blob.keys.original_mode or pm),
            practice_tonic=pt,
            practice_mode=pm,
            written_tonic=blob.keys.written_tonic,
            written_mode=blob.keys.written_mode,
            instrument=blob.keys.instrument,
            key_owner=str(blob.keys.key_owner or owner),
        )
        blob.section_map = copy.deepcopy(aligned)
        save_workflow_blob(session, blob, source="align_generated_session_to_declared_concert_key")
    return True


__all__ = [
    "align_generated_session_to_declared_concert_key",
    "commit_jam_session_generation",
    "commit_style_jam_control_settings",
    "commit_style_jam_generation",
    "finalize_generated_jam_session_key_seal",
    "finalize_generated_style_jam_key_seal",
    "resolve_generated_concert_key_for_owner",
    "seal_jam_session_musical_context",
]
