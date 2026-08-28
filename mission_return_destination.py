"""Immutable exact return destination for Mission Backing → Creative."""

from __future__ import annotations

import copy
from typing import Any

MISSION_CANONICAL_RETURN_DESTINATION_KEY = "_music_mission_canonical_return_destination"
MISSION_RETURN_DESTINATION_BLOB_KEY = "mission_return_destination"


def _backing_context_blob(session: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from backing_context import BACKING_CONTEXT_KEY

        raw = session.get(BACKING_CONTEXT_KEY)
    except ImportError:
        raw = session.get("backing_context")
    return raw if isinstance(raw, dict) else None


def _valid_dest(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict) and str(raw.get("mission_id") or "").strip():
        return copy.deepcopy(raw)
    return None


def recover_mission_return_destination_from_backing_session(
    session: dict[str, Any],
) -> dict[str, Any] | None:
    """Recover the sealed Mission launch identity from the Mission Backing session.

    Does not mint a new Mission. Uses dest stamped on ``backing_context``, then
    the sealed ``creative_return_route`` + ctx ``mission_id`` from that same session.
    """
    blob = _backing_context_blob(session)
    if blob is None:
        return None
    dest = _valid_dest(blob.get(MISSION_RETURN_DESTINATION_BLOB_KEY))
    if dest is not None:
        return dest
    if str(blob.get("source") or "").strip() != "mission":
        return None
    route = blob.get("creative_return_route")
    route = route if isinstance(route, dict) else {}
    mission_id = str(route.get("mission_id") or blob.get("mission_id") or "").strip()
    if not mission_id:
        return None
    recovered = {
        "destination_page": "creative",
        "creative_tab": "Missions",
        "workflow_owner": "mission_jam",
        "handoff_mode": str(route.get("handoff_mode") or "mission_backing"),
        "with_practice_lick": bool(route.get("with_practice_lick")),
        "mission_id": mission_id,
        "section_label": str(route.get("mission_section") or blob.get("section") or "").strip(),
        "chord_symbol": str(route.get("mission_chord") or "").strip(),
        "song_pick_key": str(route.get("song_pick_key") or blob.get("bound_pick_key") or "").strip(),
        "concert_key": str(blob.get("concert_key") or blob.get("key") or "").strip(),
        "display_key": str(blob.get("display_key") or blob.get("concert_key") or blob.get("key") or "").strip(),
        "return_route": "creative",
    }
    chord = str(recovered.get("chord_symbol") or "").strip()
    section = str(recovered.get("section_label") or "").strip()
    if section or chord:
        recovered["chord_display_label"] = f"{section} · {chord}".strip(" ·")
    return recovered


def stamp_mission_return_destination_on_backing_context(
    session: dict[str, Any],
    destination: dict[str, Any] | None = None,
) -> None:
    dest = _valid_dest(destination) or _valid_dest(session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY))
    blob = _backing_context_blob(session)
    if dest is None or blob is None:
        return
    blob[MISSION_RETURN_DESTINATION_BLOB_KEY] = copy.deepcopy(dest)


def rehydrate_mission_return_destination_from_backing_context(session: dict[str, Any]) -> dict[str, Any] | None:
    """Restore the session dest key from the Mission Backing session after Upload/refresh."""
    existing = _valid_dest(session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY))
    if existing is not None:
        stamp_mission_return_destination_on_backing_context(session, existing)
        return existing
    recovered = recover_mission_return_destination_from_backing_session(session)
    if recovered is None:
        return None
    session[MISSION_CANONICAL_RETURN_DESTINATION_KEY] = copy.deepcopy(recovered)
    stamp_mission_return_destination_on_backing_context(session, recovered)
    return copy.deepcopy(recovered)


def build_mission_return_destination(
    alignment: dict[str, Any],
    *,
    handoff_mode: str,
    with_practice_lick: bool,
    request_seq: int | None = None,
) -> dict[str, Any]:
    dest = copy.deepcopy(alignment)
    dest["destination_page"] = "creative"
    dest["creative_tab"] = "Missions"
    dest["workflow_owner"] = "mission_jam"
    dest["handoff_mode"] = str(handoff_mode or ("practice_in_jam" if with_practice_lick else "mission_backing"))
    dest["with_practice_lick"] = bool(with_practice_lick)
    fp = str(dest.get("alignment_fingerprint") or "")
    seq = int(request_seq or 0)
    dest["return_token"] = f"{seq}:{fp}:{dest['handoff_mode']}:lick={int(with_practice_lick)}"
    return dest


def seal_mission_return_destination(session: dict[str, Any], destination: dict[str, Any]) -> None:
    dest = _valid_dest(destination)
    if dest is None:
        return
    try:
        from mission_backing_transpose import ensure_mission_backing_pitch_seal

        dest = ensure_mission_backing_pitch_seal(dest)
    except ImportError:
        pass
    session[MISSION_CANONICAL_RETURN_DESTINATION_KEY] = dest
    stamp_mission_return_destination_on_backing_context(session, dest)


def sync_mission_return_destination_after_practice_key_change(
    session: dict[str, Any],
    *,
    new_key: str,
    from_key: str = "",
) -> dict[str, Any] | None:
    """Keep Return-to-Mission sealed dest aligned with Mission Backing PK mutation.

    Sealing at handoff captures the pre-Backing key (e.g. Cm). A later Practice Key
    change on Mission Backing must update that dest so Return does not snap back.
    """
    new = str(new_key or "").strip()
    if not new:
        return None
    dest = peek_mission_return_destination(session)
    if dest is None:
        return None
    old = str(from_key or dest.get("display_key") or dest.get("concert_key") or "").strip()
    dest = copy.deepcopy(dest)
    dest["display_key"] = new
    dest["concert_key"] = new
    try:
        from workflow_key_identity import normalize_user_practice_key_selection

        tonic, mode, token = normalize_user_practice_key_selection(new, default_mode="minor")
        dest["concert_tonic"] = tonic
        dest["concert_mode"] = mode
        dest["display_key"] = token
        dest["concert_key"] = token
        new = token
    except ImportError:
        pass
    # Prefer live Mission selection when it is not just the song tonic replacing
    # a sealed Mission chord (Daniel: PK D#m must not become the selected chord).
    live_chord = str(session.get("ii_selected_chord") or session.get("II_SELECTED_CHORD") or "").strip()
    live_sec = str(session.get("ii_selected_section") or session.get("II_SELECTED_SECTION") or "").strip()
    sealed_chord = str(dest.get("sealed_chord_symbol") or dest.get("chord_symbol") or "").strip()
    live_is_song_tonic = False
    try:
        from mission_backing_transpose import _chord_root_matches_key

        live_is_song_tonic = bool(
            live_chord
            and _chord_root_matches_key(live_chord, new)
            and sealed_chord
            and not _chord_root_matches_key(sealed_chord, new)
        )
    except ImportError:
        live_is_song_tonic = False
    if live_chord and not live_is_song_tonic:
        dest["chord_symbol"] = live_chord
    elif old and old != new:
        try:
            from music_theory import semitone_distance, transpose_chord

            steps = semitone_distance(old, new)
            sealed_ch = str(dest.get("chord_symbol") or "").strip()
            if steps and sealed_ch:
                dest["chord_symbol"] = transpose_chord(sealed_ch, steps, reference_key=new)
        except Exception:
            pass
    if live_sec:
        dest["section_label"] = live_sec
    section = str(dest.get("section_label") or "").strip()
    chord = str(dest.get("chord_symbol") or "").strip()
    if section or chord:
        dest["chord_display_label"] = f"{section} · {chord}".strip(" ·")
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        raw = session.get(MISSION_EXAMPLE_KEY)
        if isinstance(raw, dict):
            motif = raw.get("motif") if isinstance(raw.get("motif"), dict) else {}
            notes = list(motif.get("notes") or [])
            if notes:
                dest["example_notes"] = [str(n) for n in notes]
                dest["example_midi"] = [int(m) for m in (motif.get("midi") or []) if str(m).strip() != ""]
                dest["example_display"] = str(motif.get("display") or " – ".join(str(n) for n in notes))
                dest["example_abc"] = str(raw.get("abc") or dest.get("example_abc") or "")
                dest["example_rhythm"] = str(motif.get("rhythm") or dest.get("example_rhythm") or "")
    except ImportError:
        pass
    try:
        idx = session.get("ii_selected_chord_index")
        if idx is not None and str(idx).strip() != "":
            dest["chord_index"] = int(idx)
    except (TypeError, ValueError):
        pass
    seal_mission_return_destination(session, dest)
    # Keep backing_context musical keys aligned for restore_session_widgets_from_backing_context.
    blob = _backing_context_blob(session)
    if blob is not None and str(blob.get("source") or "").strip() == "mission":
        blob["display_key"] = new
        blob["concert_key"] = new
        blob["key"] = new
        route = blob.get("creative_return_route")
        if isinstance(route, dict):
            route = dict(route)
            route["mission_chord"] = chord or route.get("mission_chord")
            if live_sec:
                route["mission_section"] = live_sec
            blob["creative_return_route"] = route
    # Sticky Practice Key for the Mission song pick must track Mission Backing PK.
    pick = str(dest.get("song_pick_key") or session.get("active_catalog_pick_key") or "").strip()
    if pick and new:
        try:
            from songs.practice_key_state import set_practice_concert_key

            set_practice_concert_key(session, new, pick_key=pick)
        except ImportError:
            pass
    # Parent song/mission Practice Key blob must track Mission Backing PK so
    # Live Coach → Missions hydrate cannot re-project a stale Cm snapshot.
    try:
        from music_workflow_song_practice import (
            ensure_song_practice_blob_for_active_song,
            mirror_mission_keys_from_song_blob,
        )

        ensure_song_practice_blob_for_active_song(session, practice_key=new)
        mirror_mission_keys_from_song_blob(session)
    except ImportError:
        pass
    return copy.deepcopy(dest)


def peek_mission_return_destination(session: dict[str, Any]) -> dict[str, Any] | None:
    existing = _valid_dest(session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY))
    if existing is not None:
        return existing
    return rehydrate_mission_return_destination_from_backing_context(session)


def apply_sealed_mission_return_destination(session: dict[str, Any], dest: dict[str, Any] | None = None) -> bool:
    """Restore exact mission identity from sealed return destination (Backing → Missions)."""
    sealed = dest if isinstance(dest, dict) else peek_mission_return_destination(session)
    if not isinstance(sealed, dict) or not str(sealed.get("mission_id") or "").strip():
        return False
    try:
        from mission_backing_alignment import apply_pending_mission_backing_alignment

        apply_pending_mission_backing_alignment(session, sealed)
    except ImportError:
        pass
    try:
        from music_workflow_pending_mission_return import _apply_return_destination_session_fields

        _apply_return_destination_session_fields(session, sealed)
    except ImportError:
        mission_id = str(sealed.get("mission_id") or "").strip()
        if mission_id:
            session["improv_active_mission"] = mission_id
            session["improv_mission_pick"] = mission_id
    try:
        from mission_practice_context import refresh_mission_practice_context

        refresh_mission_practice_context(session)
    except ImportError:
        pass
    return True


def seal_mission_return_destination_from_handoff(session: dict[str, Any], pending: dict[str, Any]) -> None:
    align = pending.get("mission_alignment")
    if not isinstance(align, dict):
        return
    dest = build_mission_return_destination(
        align,
        handoff_mode=str(pending.get("handoff_mode") or "mission_backing"),
        with_practice_lick=bool(pending.get("with_practice_lick")),
        request_seq=int(pending.get("request_seq") or 0),
    )
    seal_mission_return_destination(session, dest)


__all__ = [
    "MISSION_CANONICAL_RETURN_DESTINATION_KEY",
    "MISSION_RETURN_DESTINATION_BLOB_KEY",
    "apply_sealed_mission_return_destination",
    "build_mission_return_destination",
    "peek_mission_return_destination",
    "recover_mission_return_destination_from_backing_session",
    "rehydrate_mission_return_destination_from_backing_context",
    "seal_mission_return_destination",
    "seal_mission_return_destination_from_handoff",
    "stamp_mission_return_destination_on_backing_context",
    "sync_mission_return_destination_after_practice_key_change",
]
