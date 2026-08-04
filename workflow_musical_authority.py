"""Workflow-specific musical ownership — key, progression, style isolated per Creative workflow."""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Literal

WorkflowType = Literal[
    "song_based_improvisation",
    "style_jam",
    "jam_session_generator",
    "entry_jam",
    "mission_jam",
    "regular_catalog_backing",
    "regular_custom_backing",
]

WORKFLOW_MUSICAL_STATES_KEY = "_workflow_musical_states"
ACTIVE_WORKFLOW_OWNER_KEY = "_active_workflow_owner"
WORKFLOW_CONSISTENCY_DIAG_KEY = "_workflow_consistency_diag"

_ENTRY_TO_WORKFLOW = {
    "Song-Based Improvisation": "song_based_improvisation",
    "Style Jam Mode": "style_jam",
    "Jam Session Generator": "jam_session_generator",
}


def workflow_type_from_entry(entry: str) -> WorkflowType | None:
    text = str(entry or "").strip()
    wf = _ENTRY_TO_WORKFLOW.get(text)
    return wf  # type: ignore[return-value]


def workflow_type_from_backing_source(source: str, *, entry_mode: str = "") -> WorkflowType:
    src = str(source or "").strip()
    entry = str(entry_mode or "").strip()
    if src == "song_improv":
        return "song_based_improvisation"
    if src == "mission":
        return "mission_jam"
    if src == "custom_progression":
        return "regular_custom_backing"
    if src == "entry_jam":
        if entry == "Jam Session Generator":
            return "jam_session_generator"
        if entry == "Style Jam Mode":
            return "style_jam"
        return "entry_jam"
    return "regular_catalog_backing"


def _state_id_for_workflow(session: dict[str, Any], wf: WorkflowType) -> str:
    if wf == "song_based_improvisation":
        return str(session.get("active_catalog_pick_key") or session.get("song") or "song").strip() or "song"
    if wf == "jam_session_generator":
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict) and jam.get("id"):
            return str(jam.get("id"))
        return str(session.get("improv_jam_style") or "jam_gen").strip() or "jam_gen"
    if wf == "style_jam":
        return str(session.get("improv_style") or "style_jam").strip() or "style_jam"
    return wf


def _tonic_mode_from_key_token(key: str) -> tuple[str, str]:
    from music_theory import key_is_minor, normalize_root, split_chord

    text = str(key or "C").strip() or "C"
    root, suffix = split_chord(text)
    tonic = normalize_root(root) or "C"
    mode = "minor" if key_is_minor(text) else "major"
    return tonic, mode


def capture_workflow_musical_state(session: dict[str, Any], wf: WorkflowType) -> dict[str, Any]:
    """Snapshot current session fields owned by a workflow."""
    entry = str(session.get("improv_entry_mode") or "").strip()
    blob: dict[str, Any] = {
        "workflow_type": wf,
        "session_id": _state_id_for_workflow(session, wf),
        "entry_mode": entry,
    }
    if wf == "song_based_improvisation":
        blob["display_key"] = str(session.get("display_key") or "").strip()
        blob["concert_key"] = str(session.get("concert_key") or "").strip()
        blob["sections"] = copy.deepcopy(session.get("improv_song_concert_sections") or {})
    elif wf == "style_jam":
        blob["tonic_key"] = str(session.get("improv_style_key") or "C").strip() or "C"
        blob["tonic"], blob["mode"] = _tonic_mode_from_key_token(blob["tonic_key"])
        blob["style"] = str(session.get("improv_style") or "").strip()
        blob["mood"] = str(session.get("improv_mood") or "").strip()
        blob["groove"] = str(session.get("improv_groove") or "").strip()
        blob["bpm"] = int(session.get("improv_style_bpm") or 110)
        blob["sections"] = copy.deepcopy(session.get("improv_generated_sections") or {})
    elif wf == "jam_session_generator":
        blob["tonic_key"] = str(session.get("improv_jam_key") or "C").strip() or "C"
        blob["tonic"], blob["mode"] = _tonic_mode_from_key_token(blob["tonic_key"])
        blob["style"] = str(session.get("improv_jam_style") or "").strip()
        blob["mood"] = str(session.get("improv_jam_mood") or "").strip()
        blob["groove"] = str(session.get("improv_groove") or "").strip()
        blob["bpm"] = int(session.get("improv_jam_bpm") or 110)
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict):
            blob["jam_session"] = copy.deepcopy(jam)
            blob["sections"] = copy.deepcopy(jam.get("sections") or {})
    elif wf == "mission_jam":
        blob["display_key"] = str(session.get("display_key") or "").strip()
        blob["concert_key"] = str(session.get("concert_key") or "").strip()
        blob["sections"] = copy.deepcopy(session.get("improv_song_concert_sections") or {})
        blob["ii_selected_chord"] = str(session.get("ii_selected_chord") or "").strip()
        blob["ii_selected_section"] = str(session.get("ii_selected_section") or "").strip()
        blob["ii_selected_chord_index"] = int(session.get("ii_selected_chord_index") or 0)
        blob["improv_active_mission"] = str(session.get("improv_active_mission") or "").strip()
        blob["improv_mission_pick"] = str(session.get("improv_mission_pick") or "").strip()
        blob["improv_intelligence_tab"] = "Missions"
    blob["fingerprint"] = hashlib.sha256(repr(sorted(blob.items())).encode()).hexdigest()[:12]
    return blob


def save_workflow_snapshot(session: dict[str, Any], wf: WorkflowType) -> None:
    store = session.get(WORKFLOW_MUSICAL_STATES_KEY)
    if not isinstance(store, dict):
        store = {}
    store[wf] = capture_workflow_musical_state(session, wf)
    session[WORKFLOW_MUSICAL_STATES_KEY] = store


def restore_workflow_snapshot(session: dict[str, Any], wf: WorkflowType) -> bool:
    store = session.get(WORKFLOW_MUSICAL_STATES_KEY)
    if not isinstance(store, dict):
        return False
    blob = store.get(wf)
    if not isinstance(blob, dict):
        return False
    session[ACTIVE_WORKFLOW_OWNER_KEY] = wf
    if wf == "song_based_improvisation":
        for k in ("display_key", "concert_key"):
            v = str(blob.get(k) or "").strip()
            if v:
                session[k] = v
                session["_pending_display_key"] = v
        sec = blob.get("sections")
        if isinstance(sec, dict) and sec:
            session["improv_song_concert_sections"] = copy.deepcopy(sec)
        return True
    if wf == "style_jam":
        session["improv_entry_mode"] = "Style Jam Mode"
        key = str(blob.get("tonic_key") or "C").strip() or "C"
        session["improv_style_key"] = key
        session["improv_style"] = str(blob.get("style") or "").strip()
        session["improv_mood"] = str(blob.get("mood") or "").strip()
        session["improv_groove"] = str(blob.get("groove") or "").strip()
        session["improv_style_bpm"] = int(blob.get("bpm") or 110)
        sec = blob.get("sections")
        if isinstance(sec, dict):
            session["improv_generated_sections"] = copy.deepcopy(sec)
        try:
            from creative_key_sync import apply_creative_concert_key, IMPROV_STYLE_KEY_TRACKER

            apply_creative_concert_key(session, key, source="workflow_restore_style_jam")
            session[IMPROV_STYLE_KEY_TRACKER] = key
        except ImportError:
            pass
        session["display_key"] = key
        session["concert_key"] = key
        session["_pending_display_key"] = key
        return True
    if wf == "jam_session_generator":
        session["improv_entry_mode"] = "Jam Session Generator"
        key = str(blob.get("tonic_key") or "C").strip() or "C"
        session["improv_jam_key"] = key
        session["improv_jam_style"] = str(blob.get("style") or "").strip()
        session["improv_jam_mood"] = str(blob.get("mood") or "").strip()
        session["improv_jam_bpm"] = int(blob.get("bpm") or 110)
        jam = blob.get("jam_session")
        if isinstance(jam, dict):
            session["improv_jam_session"] = copy.deepcopy(jam)
        try:
            from creative_key_sync import apply_creative_concert_key, IMPROV_JAM_KEY_TRACKER
            from generated_jam_key_context import activate_generated_jam_key_ownership

            apply_creative_concert_key(session, key, source="workflow_restore_jam_gen")
            session[IMPROV_JAM_KEY_TRACKER] = key
            activate_generated_jam_key_ownership(session, entry_mode="Jam Session Generator")
        except ImportError:
            session["display_key"] = key
            session["concert_key"] = key
        return True
    if wf == "mission_jam":
        session["improv_intelligence_tab"] = "Missions"
        session["creative_improv_intelligence_tab"] = "Missions"
        for k in ("display_key", "concert_key"):
            v = str(blob.get(k) or "").strip()
            if v:
                session[k] = v
                session["_pending_display_key"] = v
        sec = blob.get("sections")
        if isinstance(sec, dict) and sec:
            session["improv_song_concert_sections"] = copy.deepcopy(sec)
        for k in (
            "ii_selected_chord",
            "ii_selected_section",
            "improv_active_mission",
            "improv_mission_pick",
        ):
            v = blob.get(k)
            if v is not None and str(v).strip() != "":
                session[k] = v
        if blob.get("ii_selected_chord_index") is not None:
            session["ii_selected_chord_index"] = int(blob.get("ii_selected_chord_index") or 0)
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            deactivate_generated_jam_key_ownership(session)
        except ImportError:
            pass
        return True
    return False


def switch_workflow_owner(session: dict[str, Any], new_wf: WorkflowType) -> None:
    """Persist outgoing workflow, restore incoming — delegates to activate_workflow."""
    try:
        from music_workflow_activation import activate_workflow_simple

        activate_workflow_simple(
            session,
            str(new_wf),
            activation_source="switch_workflow_owner",
        )
        return
    except ImportError:
        pass
    prev = str(session.get(ACTIVE_WORKFLOW_OWNER_KEY) or "").strip()
    if prev:
        save_workflow_snapshot(session, prev)  # type: ignore[arg-type]
    else:
        entry = str(session.get("improv_entry_mode") or "").strip()
        inferred = workflow_type_from_entry(entry)
        if inferred:
            save_workflow_snapshot(session, inferred)
    ok = restore_workflow_snapshot(session, new_wf)
    if new_wf == "mission_jam":
        if not ok:
            restore_workflow_snapshot(session, "song_based_improvisation")
        session["improv_intelligence_tab"] = "Missions"
        session["creative_improv_intelligence_tab"] = "Missions"
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            deactivate_generated_jam_key_ownership(session)
        except ImportError:
            pass
    session[ACTIVE_WORKFLOW_OWNER_KEY] = new_wf


def sync_song_improv_sections_to_practice_key(session: dict[str, Any]) -> dict[str, list[str]]:
    """Full catalog song sections transposed to current practice concert key."""
    practice = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not practice:
        return {}
    try:
        from backing_context import _current_pick_key
        from songs.music_source import resolve_catalog_song_for_pick
        from music_theory import transpose_sections_dict

        pick = _current_pick_key(session)
        selected, ok = resolve_catalog_song_for_pick(session, pick)
        if not ok or not isinstance(selected, dict):
            return {}
        original = str(selected.get("key") or selected.get("original_key") or "").strip()
        sections = selected.get("sections")
        if not isinstance(sections, dict) or not sections:
            return {}
        base = {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in sections.items()
            if isinstance(chords, list)
        }
        if not original or original == practice:
            out = base
        else:
            out = transpose_sections_dict(base, original, practice)
        session["improv_song_concert_sections"] = copy.deepcopy(out)
        return out
    except ImportError:
        return {}


def validate_workflow_consistency(session: dict[str, Any], ctx: Any | None = None) -> dict[str, Any]:
    """Detect label/progression/style owner mismatches for ?dev=1."""
    violations: list[str] = []
    wf = str(session.get(ACTIVE_WORKFLOW_OWNER_KEY) or "").strip()
    launch = str(session.get("_backing_launch_workflow") or "").strip()
    rendered = ""
    if ctx is not None:
        try:
            from workflow_musical_authority import workflow_type_from_backing_source

            rendered = workflow_type_from_backing_source(
                str(getattr(ctx, "source", "") or ""),
                entry_mode=str(getattr(ctx, "entry_mode", "") or ""),
            )
        except Exception:
            rendered = str(getattr(ctx, "source", "") or "")
    if launch and rendered and launch != rendered:
        if launch == "style_jam" and rendered == "jam_session_generator":
            violations.append("STYLE_JAM_OPENED_AS_GENERATOR")
        violations.append("BACKING_WORKFLOW_ROUTE_MISMATCH")
    practice = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if ctx is not None and str(getattr(ctx, "source", "") or "") == "song_improv":
        prog = list(getattr(ctx, "progression", None) or [])
        if prog and practice:
            first = str(prog[0] or "")
            try:
                from music_theory import normalize_root, split_chord, key_is_minor

                pr = normalize_root(split_chord(practice)[0])
                cr = normalize_root(split_chord(first)[0])
                song_minor = key_is_minor(practice)
                chord_minor = "m" in first.lower() and "maj" not in first.lower()
                if song_minor != chord_minor and len(prog) >= 3:
                    violations.append("KEY_LABEL_PROGRESSION_MISMATCH")
            except ImportError:
                pass
    style = str(getattr(ctx, "style", "") or "") if ctx else ""
    if rendered in {"jam_session_generator", "style_jam"} and style:
        low = style.lower()
        if any(x in low for x in ("jewish", "hevenu", "ballad")) and "bossa" not in low:
            if str(session.get("improv_jam_style") or session.get("improv_style") or "").lower().find("jewish") < 0:
                violations.append("GENERATED_JAM_CATALOG_STYLE_LEAK")
    diag = {
        "launch_workflow": launch,
        "rendered_workflow": rendered,
        "active_owner": wf,
        "violations": violations,
        "consistent": not violations,
    }
    session[WORKFLOW_CONSISTENCY_DIAG_KEY] = diag
    return diag


__all__ = [
    "ACTIVE_WORKFLOW_OWNER_KEY",
    "WORKFLOW_CONSISTENCY_DIAG_KEY",
    "WORKFLOW_MUSICAL_STATES_KEY",
    "WorkflowType",
    "capture_workflow_musical_state",
    "restore_workflow_snapshot",
    "save_workflow_snapshot",
    "switch_workflow_owner",
    "sync_song_improv_sections_to_practice_key",
    "validate_workflow_consistency",
    "workflow_type_from_backing_source",
    "workflow_type_from_entry",
]
