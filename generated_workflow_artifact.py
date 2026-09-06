"""Owner-complete generated workflow artifact — immutable backing handoff snapshot."""

from __future__ import annotations

import copy
import hashlib
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

GeneratedOwner = Literal["style_jam", "jam_session_generator"]

BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY = "_backing_owner_artifact_snapshot"
WORKFLOW_OWNER_INTEGRITY_FAILURE = "WORKFLOW_OWNER_INTEGRITY_FAILURE"
WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY = "_workflow_owner_integrity_user_message"


class WorkflowOwnerIntegrityError(RuntimeError):
    """Raised when backing must not render a hybrid generated card."""


_ENTRY_MODE_FOR_OWNER: dict[str, str] = {
    "style_jam": "Style Jam Mode",
    "jam_session_generator": "Jam Session Generator",
}


@dataclass
class GeneratedWorkflowArtifactSnapshot:
    workflow_owner: str = ""
    workflow_session_id: str = ""
    artifact_id: str = ""
    artifact_revision: int = 0
    generation_request_token: str = ""
    generation_sequence: int = 0
    control_fingerprint: str = ""
    practice_tonic: str = "C"
    practice_mode: str = "major"
    style: str = ""
    mood: str = ""
    groove: str = ""
    intensity: str = ""
    bpm: int = 110
    meter: str = "4/4"
    level: str = "Intermediate"
    section_map: dict[str, list[str]] = field(default_factory=dict)
    selected_scope: str = "Full song"
    selected_section_ids: list[str] = field(default_factory=list)
    progression: list[str] = field(default_factory=list)
    backing_configuration: dict[str, Any] = field(default_factory=dict)
    exact_return_destination: str = "creative"
    entry_mode: str = ""
    bound_pick_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> GeneratedWorkflowArtifactSnapshot | None:
        if not isinstance(raw, dict):
            return None
        sec = raw.get("section_map")
        if not isinstance(sec, dict):
            sec = {}
        section_map = {
            str(k): [str(c) for c in v if str(c).strip()]
            for k, v in sec.items()
            if isinstance(v, list)
        }
        prog = raw.get("progression")
        progression = [str(c) for c in prog if str(c).strip()] if isinstance(prog, list) else []
        sel = raw.get("selected_section_ids")
        selected_section_ids = [str(s) for s in sel if str(s).strip()] if isinstance(sel, list) else []
        return cls(
            workflow_owner=str(raw.get("workflow_owner") or ""),
            workflow_session_id=str(raw.get("workflow_session_id") or ""),
            artifact_id=str(raw.get("artifact_id") or ""),
            artifact_revision=int(raw.get("artifact_revision") or 0),
            generation_request_token=str(raw.get("generation_request_token") or ""),
            generation_sequence=int(raw.get("generation_sequence") or 0),
            control_fingerprint=str(raw.get("control_fingerprint") or ""),
            practice_tonic=str(raw.get("practice_tonic") or "C"),
            practice_mode=str(raw.get("practice_mode") or "major"),
            style=str(raw.get("style") or ""),
            mood=str(raw.get("mood") or ""),
            groove=str(raw.get("groove") or ""),
            intensity=str(raw.get("intensity") or ""),
            bpm=int(raw.get("bpm") or 110),
            meter=str(raw.get("meter") or "4/4"),
            level=str(raw.get("level") or "Intermediate"),
            section_map=section_map,
            selected_scope=str(raw.get("selected_scope") or "Full song"),
            selected_section_ids=selected_section_ids,
            progression=progression,
            backing_configuration=dict(raw.get("backing_configuration") or {}),
            exact_return_destination=str(raw.get("exact_return_destination") or "creative"),
            entry_mode=str(raw.get("entry_mode") or ""),
            bound_pick_key=str(raw.get("bound_pick_key") or ""),
        )


def _practice_key_label(tonic: str, mode: str) -> str:
    t = str(tonic or "C").strip()
    m = str(mode or "major").strip().lower()
    if m == "minor":
        if t.endswith("m") or t.endswith("b") and len(t) <= 3:
            return t if t.endswith("m") else f"{t}m"
        return f"{t}m"
    return t.rstrip("M")


def _control_fingerprint(
    owner: str,
    *,
    style: str,
    mood: str,
    groove: str,
    tonic: str,
    mode: str,
    section_names: list[str],
) -> str:
    src = f"{owner}|{style}|{mood}|{groove}|{tonic}|{mode}|{'/'.join(sorted(section_names))}|{time.time_ns()}"
    return hashlib.sha256(src.encode()).hexdigest()[:16]


def _flatten_sections(section_map: dict[str, list[str]]) -> list[str]:
    try:
        from improvisation_intelligence import flatten_sections

        return flatten_sections(section_map)
    except ImportError:
        out: list[str] = []
        for chords in section_map.values():
            if isinstance(chords, list):
                out.extend(str(c) for c in chords if str(c).strip())
        return out


def resolve_handoff_entry_mode(session: dict[str, Any]) -> str:
    """Entry mode that owns a generated-artifact seal — never leftover SBI radio state.

    Opening entry_jam backing must seal Style Jam / Jam Generator from the generated
    session, even when ``improv_entry_mode`` still says Song-Based Improvisation.
    """
    try:
        from backing_source_navigation import resolve_entry_jam_entry_mode

        resolved = resolve_entry_jam_entry_mode(session)
        if resolved in ("Style Jam Mode", "Jam Session Generator"):
            return resolved
    except ImportError:
        pass
    try:
        from backing_source_navigation import _creative_handoff_entry_mode

        return _creative_handoff_entry_mode(session)
    except ImportError:
        return str(session.get("improv_entry_mode") or "").strip()


def owner_for_entry_mode(entry: str) -> GeneratedOwner | None:
    if entry == "Style Jam Mode":
        return "style_jam"
    if entry == "Jam Session Generator":
        return "jam_session_generator"
    return None


def _legacy_style_jam_section_map(session: dict[str, Any]) -> dict[str, list[str]]:
    gen = session.get("improv_generated_sections")
    if isinstance(gen, dict) and gen:
        return {
            str(k): [str(c) for c in v if str(c).strip()]
            for k, v in gen.items()
            if isinstance(v, list)
        }
    return {}


def _legacy_generator_section_map(session: dict[str, Any]) -> dict[str, list[str]]:
    jam = session.get("improv_jam_session")
    if isinstance(jam, dict):
        raw = jam.get("sections")
        if isinstance(raw, dict) and raw:
            return {
                str(k): [str(c) for c in v if str(c).strip()]
                for k, v in raw.items()
                if isinstance(v, list)
            }
    return {}


def build_snapshot_from_session(
    session: dict[str, Any],
    *,
    owner: GeneratedOwner,
    entry_mode: str | None = None,
    new_revision: bool = False,
    generation_request_token: str = "",
) -> GeneratedWorkflowArtifactSnapshot | None:
    """Materialize owner-complete artifact from workflow store + owner-scoped legacy keys."""
    entry = str(entry_mode or _ENTRY_MODE_FOR_OWNER.get(owner) or "").strip()
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob
        from music_workflow_compatibility import legacy_session_id_for_owner

        ptr = get_active_workflow_pointer(session)
        sid = ""
        if ptr and str(ptr.workflow_owner or "") == owner:
            sid = str(ptr.workflow_session_id or "")
        if owner == "jam_session_generator":
            try:
                from generated_jam_key_change import resolve_generated_workflow_session_id

                resolved = str(resolve_generated_workflow_session_id(session, owner) or "").strip()
                if resolved:
                    sid = resolved
            except ImportError:
                pass
        if not sid:
            sid = str(legacy_session_id_for_owner(session, owner) or "")
        blob = get_workflow_blob(session, owner, sid) if sid else None
    except ImportError:
        blob = None
        sid = ""

    section_map: dict[str, list[str]] = {}
    style = mood = groove = level = ""
    bpm = 110
    meter = "4/4"
    pt, pm = "C", "major"
    artifact_rev = 1
    artifact_id = str(uuid.uuid4())
    gen_seq = int(session.get("_generated_artifact_sequence") or 0)

    if blob is not None:
        section_map = copy.deepcopy(blob.section_map or {})
        style = str(blob.style or "")
        mood = str(blob.mood or "")
        groove = str(blob.groove or "")
        bpm = int(blob.tempo_bpm or 110)
        meter = str(blob.meter or "4/4")
        pt = str(blob.keys.practice_tonic or blob.keys.original_tonic or "C")
        pm = str(blob.keys.practice_mode or blob.keys.original_mode or "major")
        artifact_rev = int(blob.context_revision or 1)
        artifact_id = str(blob.generated_session_id or blob.workflow_session_id or artifact_id)
        sid = str(blob.workflow_session_id or sid)
        blob_authoritative = True
    elif owner == "style_jam":
        blob_authoritative = False
        section_map = _legacy_style_jam_section_map(session)
        style = str(session.get("improv_style") or "")
        mood = str(session.get("improv_mood") or "")
        groove = str(session.get("improv_groove") or "")
        bpm = int(session.get("improv_style_bpm") or 110)
        level = str(session.get("improv_difficulty") or "Intermediate")
        try:
            from music_workflow_compatibility import _tonic_mode_from_token

            pt, pm = _tonic_mode_from_token(str(session.get("improv_style_key") or "C"))
        except ImportError:
            pt, pm = "C", "major"
    else:
        blob_authoritative = False
        section_map = _legacy_generator_section_map(session)
        style = str(session.get("improv_jam_style") or "")
        mood = str(session.get("improv_jam_mood") or "")
        groove = str(session.get("improv_groove") or style)
        bpm = int(session.get("improv_jam_bpm") or 110)
        try:
            from music_workflow_compatibility import _tonic_mode_from_token

            pt, pm = _tonic_mode_from_token(str(session.get("improv_jam_key") or "C"))
        except ImportError:
            pt, pm = "C", "major"
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict) and jam.get("id"):
            artifact_id = str(jam.get("id"))

    if not blob_authoritative:
        if owner == "style_jam":
            sm = str(session.get("improv_mood") or "").strip()
            if sm:
                mood = sm
            sg = str(session.get("improv_groove") or "").strip()
            if sg:
                groove = sg
            ss = str(session.get("improv_style") or "").strip()
            if ss:
                style = ss
        elif owner == "jam_session_generator":
            jk = str(session.get("improv_jam_key") or "").strip()
            if jk:
                try:
                    from music_workflow_compatibility import _tonic_mode_from_token

                    pt, pm = _tonic_mode_from_token(jk)
                except ImportError:
                    pass
    if owner == "jam_session_generator":
        jm = str(session.get("improv_jam_mood") or "").strip()
        if jm:
            mood = jm
        js = str(session.get("improv_jam_style") or "").strip()
        if js:
            style = js

    if owner == "style_jam" and not str(mood or "").strip() and not blob_authoritative:
        mood = str(session.get("improv_mood") or "")

    last_raw = session.get(f"_generated_artifact_last_{owner}")
    if isinstance(last_raw, dict):
        artifact_id = str(last_raw.get("artifact_id") or artifact_id)
        artifact_rev = int(last_raw.get("artifact_revision") or artifact_rev)
        gen_seq = int(last_raw.get("generation_sequence") or gen_seq)
        if not generation_request_token:
            generation_request_token = str(last_raw.get("generation_request_token") or "")

    if not section_map:
        return None

    if new_revision:
        gen_seq += 1
        session["_generated_artifact_sequence"] = gen_seq
        last_raw = session.get(f"_generated_artifact_last_{owner}")
        if isinstance(last_raw, dict):
            artifact_rev = max(artifact_rev, int(last_raw.get("artifact_revision") or 0)) + 1
            artifact_id = str(uuid.uuid4())
        else:
            artifact_rev = max(artifact_rev, 0) + 1
            artifact_id = str(uuid.uuid4())

    progression = _flatten_sections(section_map)
    fp = _control_fingerprint(
        owner,
        style=style,
        mood=mood,
        groove=groove,
        tonic=pt,
        mode=pm,
        section_names=list(section_map.keys()),
    )
    from backing_musical_profile import normalize_backing_play_intensity

    diff_label = level or str(session.get("improv_difficulty") or "Intermediate")
    play_intensity = normalize_backing_play_intensity("", difficulty=diff_label)
    return GeneratedWorkflowArtifactSnapshot(
        workflow_owner=owner,
        workflow_session_id=sid or artifact_id,
        artifact_id=artifact_id or sid or str(uuid.uuid4()),
        artifact_revision=artifact_rev,
        generation_request_token=generation_request_token or fp,
        generation_sequence=gen_seq,
        control_fingerprint=fp,
        practice_tonic=pt,
        practice_mode=pm,
        style=style,
        mood=mood,
        groove=groove,
        intensity=play_intensity,
        bpm=bpm,
        meter=meter,
        level=level or str(session.get("improv_difficulty") or "Intermediate"),
        section_map=section_map,
        selected_scope="Full song",
        selected_section_ids=list(section_map.keys()),
        progression=progression,
        backing_configuration={"source": "entry_jam", "loop": True},
        exact_return_destination="creative",
        entry_mode=entry,
        bound_pick_key="",
    )


def validate_owner_artifact_snapshot(snapshot: GeneratedWorkflowArtifactSnapshot | None) -> list[str]:
    if snapshot is None:
        return [f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} missing_snapshot"]
    violations: list[str] = []
    if snapshot.workflow_owner not in {"style_jam", "jam_session_generator"}:
        violations.append(f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} invalid_owner={snapshot.workflow_owner}")
    if not snapshot.section_map or not snapshot.progression:
        violations.append(f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} incomplete_progression")
    if snapshot.entry_mode != _ENTRY_MODE_FOR_OWNER.get(snapshot.workflow_owner, ""):
        violations.append(
            f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} entry_mode_mismatch expected={_ENTRY_MODE_FOR_OWNER.get(snapshot.workflow_owner)} actual={snapshot.entry_mode}"
        )
    style_blob = f"{snapshot.style}|{snapshot.mood}|{'/'.join(snapshot.section_map.keys())}".lower()
    for token in ("hevenu", "jewish|"):
        if token in style_blob and token not in str(snapshot.style).lower():
            violations.append(f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} catalog_metadata_leak token={token}")
    if snapshot.bound_pick_key:
        violations.append(f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} catalog_bound_pick={snapshot.bound_pick_key}")
    return violations


def detect_cross_owner_handoff_fields(
    session: dict[str, Any],
    snapshot: GeneratedWorkflowArtifactSnapshot,
) -> list[str]:
    """Detect deliberate or accidental mixed-owner handoff payloads."""
    violations: list[str] = []
    declared = str(snapshot.workflow_owner or "")
    entry_owner = owner_for_entry_mode(str(snapshot.entry_mode or ""))
    if entry_owner and declared and entry_owner != declared:
        violations.append(
            f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} owner={declared} entry_mode_owner={entry_owner}"
        )
    prog_head = " ".join(list(snapshot.progression or [])[:4]).upper()
    if declared == "style_jam" and "JEWISH BALLAD" in str(snapshot.style or "").upper():
        violations.append(f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} progression_owner=old_generator actual={prog_head[:32]}")
    if declared == "style_jam" and "jam_session_generator" in str(session.get("_backing_handoff_entry_mode") or ""):
        violations.append(f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} handoff_entry=jam_session_generator card_owner=style_jam")
    meta = f"{snapshot.style}|{snapshot.mood}".lower()
    if declared in {"style_jam", "jam_session_generator"} and any(t in meta for t in ("hevenu", "jewish ballad")):
        if "jewish" not in str(session.get("improv_jam_style") or session.get("improv_style") or "").lower():
            violations.append(f"{WORKFLOW_OWNER_INTEGRITY_FAILURE} metadata_owner=catalog_song")
    return violations


def last_valid_generated_artifact_snapshot(
    session: dict[str, Any],
    owner: GeneratedOwner,
) -> GeneratedWorkflowArtifactSnapshot | None:
    raw = session.get(f"_generated_artifact_last_{owner}")
    snap = GeneratedWorkflowArtifactSnapshot.from_dict(raw)
    if snap is None:
        return None
    violations = validate_owner_artifact_snapshot(snap)
    violations.extend(detect_cross_owner_handoff_fields(session, snap))
    if violations:
        return None
    return snap


def seal_backing_handoff_snapshot_for_creative_open(session: dict[str, Any]) -> bool:
    """Seal immutable owner snapshot immediately before entry_jam backing_context build."""
    try:
        from music_workflow_generated_session import align_generated_session_to_declared_concert_key

        align_generated_session_to_declared_concert_key(session)
    except ImportError:
        pass
    entry = resolve_handoff_entry_mode(session)
    owner = owner_for_entry_mode(entry)
    if owner is None:
        session.pop(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY, None)
        return False
    snap = build_snapshot_from_session(session, owner=owner, entry_mode=entry, new_revision=False)
    if snap is None:
        session.pop(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY, None)
        return False
    violations = validate_owner_artifact_snapshot(snap)
    if violations:
        session[WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY] = "\n".join(violations)
        session.pop(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY, None)
        return False
    try:
        from musical_context_coherence import (
            GENERATED_OWNERS,
            record_coherence_handoff_block,
            resolve_coherent_musical_context,
            validate_coherent_musical_context,
            validate_generated_snapshot_coherence,
        )

        coherent = resolve_coherent_musical_context(session, prefer_owners=(owner,))
        if coherent is not None:
            coherence_v = validate_coherent_musical_context(coherent)
        else:
            prog = list(snap.progression or [])
            if not prog and snap.section_map:
                try:
                    from improvisation_intelligence import flatten_sections

                    prog = flatten_sections(snap.section_map)
                except ImportError:
                    prog = [c for chs in snap.section_map.values() for c in chs if str(c).strip()]
            coherence_v = validate_generated_snapshot_coherence(
                practice_tonic=str(snap.practice_tonic or "C"),
                practice_mode=str(snap.practice_mode or "major"),
                progression=prog,
                style_id=str(snap.style or ""),
                mood=str(snap.mood or "Mellow"),
                owner=owner,
            )
        if coherence_v:
            record_coherence_handoff_block(session, coherence_v)
            session.pop(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY, None)
            return False
    except ImportError:
        pass
    session.pop(WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY, None)
    session[BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY] = snap.to_dict()
    session["_backing_handoff_entry_mode"] = entry
    try:
        from musical_context_coherence import clear_coherence_handoff_block

        clear_coherence_handoff_block(session)
    except ImportError:
        pass
    return True


def peek_backing_owner_artifact_snapshot(session: dict[str, Any]) -> GeneratedWorkflowArtifactSnapshot | None:
    raw = session.get(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY)
    snap = GeneratedWorkflowArtifactSnapshot.from_dict(raw)
    owner = str(snap.workflow_owner or "") if snap is not None else ""
    if owner == "jam_session_generator" or (snap is None and session.get("improv_entry_mode") == "Jam Session Generator"):
        live = live_jam_canonical_snapshot_for_render(session)
        if live is not None:
            return live
        if snap is not None and owner == "jam_session_generator":
            # Stale cache with no live UUID blob: do not treat existence as current.
            return None
    return snap


def concert_key_from_snapshot(snapshot: GeneratedWorkflowArtifactSnapshot) -> str:
    return _practice_key_label(snapshot.practice_tonic, snapshot.practice_mode)


def _canonical_jam_blob_and_sid(session: dict[str, Any]) -> tuple[str, Any]:
    """Canonical generated UUID blob for Jam Session Generator — never leftover groove ids."""
    try:
        from generated_jam_key_change import resolve_generated_workflow_session_id
        from music_workflow_state_store import get_workflow_blob
    except ImportError:
        return "", None
    sid = str(resolve_generated_workflow_session_id(session, "jam_session_generator") or "").strip()
    if not sid:
        return "", None
    blob = get_workflow_blob(session, "jam_session_generator", sid)
    return sid, blob


def jam_owner_snapshot_is_current(snap: GeneratedWorkflowArtifactSnapshot | None, blob: Any, sid: str) -> bool:
    """True only when the derived snapshot still matches the live UUID blob."""
    if snap is None or blob is None:
        return False
    if str(snap.workflow_owner or "") != "jam_session_generator":
        return False
    if str(snap.workflow_session_id or "").strip() != str(sid or "").strip():
        return False
    snap_t = str(snap.practice_tonic or "").strip()
    blob_t = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "").strip()
    if not snap_t or not blob_t or snap_t != blob_t:
        return False
    blob_map = getattr(blob, "section_map", None)
    if isinstance(blob_map, dict) and blob_map and blob_map != (snap.section_map or {}):
        return False
    return True


def rebuild_jam_owner_artifact_snapshot_from_canonical_blob(
    session: dict[str, Any],
) -> GeneratedWorkflowArtifactSnapshot | None:
    """Option A: rewrite the owner snapshot as a projection of the live UUID blob.

    Musical fields always come from the generated UUID blob. A leftover C snapshot
    must never remain the render authority after the blob is Eb.
    """
    sid, blob = _canonical_jam_blob_and_sid(session)
    if blob is None or not sid:
        return None
    prev = GeneratedWorkflowArtifactSnapshot.from_dict(session.get(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY))
    snap = build_snapshot_from_session(
        session,
        owner="jam_session_generator",
        entry_mode="Jam Session Generator",
        new_revision=False,
    )
    if snap is None:
        return None
    if prev is not None and str(prev.workflow_session_id or "").strip() == str(sid):
        if str(prev.exact_return_destination or "").strip():
            snap.exact_return_destination = prev.exact_return_destination
        if str(prev.selected_scope or "").strip():
            snap.selected_scope = prev.selected_scope
        if prev.selected_section_ids:
            snap.selected_section_ids = list(prev.selected_section_ids)
    # Widget mood/style are control metadata, not a second key authority.
    jm = str(session.get("improv_jam_mood") or "").strip()
    if jm:
        snap.mood = jm
    js = str(session.get("improv_jam_style") or "").strip()
    if js:
        snap.style = js
    session[BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY] = snap.to_dict()
    return snap


def live_jam_canonical_snapshot_for_render(
    session: dict[str, Any],
) -> GeneratedWorkflowArtifactSnapshot | None:
    """Snapshot used by live Jam Backing render — UUID blob wins over a stale cache."""
    sid, blob = _canonical_jam_blob_and_sid(session)
    if blob is None or not sid:
        return None
    sm = getattr(blob, "section_map", None)
    if not (isinstance(sm, dict) and any(isinstance(v, list) and v for v in sm.values())):
        return None
    snap = GeneratedWorkflowArtifactSnapshot.from_dict(session.get(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY))
    if jam_owner_snapshot_is_current(snap, blob, sid):
        jm = str(session.get("improv_jam_mood") or "").strip()
        js = str(session.get("improv_jam_style") or "").strip()
        if snap is not None and (jm or js):
            if jm:
                snap.mood = jm
            if js:
                snap.style = js
            session[BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY] = snap.to_dict()
        return snap
    return rebuild_jam_owner_artifact_snapshot_from_canonical_blob(session)


def invalidate_jam_backing_render_snapshot(session: dict[str, Any]) -> None:
    """Drop Jam render cache/handoff so it cannot paint Catalog (or a later owner)."""
    session.pop(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY, None)
    session.pop("_backing_handoff_entry_mode", None)
    session.pop("_backing_creative_chart_sections", None)
    cws = session.get("creative_workspace_state")
    if isinstance(cws, dict):
        cws.pop(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY, None)
        cws.pop("_backing_handoff_entry_mode", None)
        cws.pop("_backing_creative_chart_sections", None)


def commit_generated_artifact_revision(
    session: dict[str, Any],
    *,
    owner: GeneratedOwner,
    generation_request_token: str = "",
) -> GeneratedWorkflowArtifactSnapshot | None:
    entry = _ENTRY_MODE_FOR_OWNER.get(owner, "")
    snap = build_snapshot_from_session(
        session,
        owner=owner,
        entry_mode=entry,
        new_revision=True,
        generation_request_token=generation_request_token,
    )
    if snap is None:
        return None
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob, save_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == owner:
            blob = get_workflow_blob(session, owner, str(ptr.workflow_session_id or ""))
            if blob is not None:
                blob.context_revision = int(snap.artifact_revision)
                blob.artifact_fingerprint = snap.control_fingerprint
                blob.section_map = copy.deepcopy(snap.section_map)
                blob.progression = list(snap.progression)
                blob.mood = snap.mood
                blob.groove = snap.groove
                blob.style = snap.style
                blob.style_owner = owner
                blob.progression_owner = owner
                save_workflow_blob(session, blob, source="generated_artifact_revision")
    except ImportError:
        pass
    if owner == "style_jam":
        session["improv_generated_sections"] = copy.deepcopy(snap.section_map)
    else:
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict):
            jam = copy.deepcopy(jam)
            jam["sections"] = copy.deepcopy(snap.section_map)
            try:
                from generated_workflow_artifact import seal_jam_session_musical_context

                key_label = _practice_key_label(snap.practice_tonic, snap.practice_mode)
                jam = seal_jam_session_musical_context(
                    jam,
                    key_center=key_label,
                    sections=snap.section_map,
                )
            except ImportError:
                pass
            try:
                from improv_jam_session_projection import set_improv_jam_session

                set_improv_jam_session(
                    session,
                    jam,
                    writer="commit_generated_artifact_revision",
                    phase="jam_session_generator",
                )
            except ImportError:
                session["improv_jam_session"] = jam
    if owner == "style_jam":
        snap.mood = str(session.get("improv_mood") or snap.mood or "Mellow")
        ig = str(session.get("improv_groove") or "").strip()
        if ig and "jewish" not in str(snap.style or "").lower() and "jewish" in ig.lower():
            ig = ""
        snap.groove = ig or str(snap.groove or "").strip() or str(snap.intensity or "Medium")
        snap.style = str(session.get("improv_style") or snap.style)
    elif owner == "jam_session_generator":
        snap.mood = str(session.get("improv_jam_mood") or snap.mood or "Mellow")
        snap.style = str(session.get("improv_jam_style") or snap.style)
    session[f"_generated_artifact_last_{owner}"] = snap.to_dict()
    return snap


__all__ = [
    "BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY",
    "GeneratedWorkflowArtifactSnapshot",
    "WORKFLOW_OWNER_INTEGRITY_FAILURE",
    "WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY",
    "build_snapshot_from_session",
    "commit_generated_artifact_revision",
    "concert_key_from_snapshot",
    "invalidate_jam_backing_render_snapshot",
    "jam_owner_snapshot_is_current",
    "live_jam_canonical_snapshot_for_render",
    "owner_for_entry_mode",
    "peek_backing_owner_artifact_snapshot",
    "rebuild_jam_owner_artifact_snapshot_from_canonical_blob",
    "resolve_handoff_entry_mode",
    "seal_backing_handoff_snapshot_for_creative_open",
    "validate_owner_artifact_snapshot",
]
