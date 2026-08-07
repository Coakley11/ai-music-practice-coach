"""Shared parent-song chord focus — separate from Song-Based full progression."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any

SONG_CREATIVE_FOCUS_KEY = "_music_song_creative_focus"
SONG_CREATIVE_FOCUS_REVISION_KEY = "_music_song_creative_focus_revision"

_VALID_SOURCE_PAGES = frozenset(
    {
        "Missions",
        "Harmony Map",
        "Live Coach",
        "Phrase / Motif",
        "Motifs",
        "Deep Harmony",
    }
)


def _practice_key_fields(session: dict[str, Any]) -> tuple[str, str]:
    try:
        from musical_context_authority import resolve_authoritative_practice_key

        pk = resolve_authoritative_practice_key(session)
        return str(pk.practice_tonic or "C"), str(pk.practice_mode or "major")
    except ImportError:
        pass
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr:
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob is not None:
                return str(blob.keys.practice_tonic or "C"), str(blob.keys.practice_mode or "major")
    except ImportError:
        pass
    return "C", "major"


def stable_song_id(session: dict[str, Any]) -> str:
    try:
        from music_workflow_song_practice import song_based_blob_session_id

        sid = str(song_based_blob_session_id(session) or "").strip()
        if sid:
            return sid
    except ImportError:
        pass
    return str(session.get("active_catalog_pick_key") or session.get("song") or "").strip() or "song"


def source_type(session: dict[str, Any]) -> str:
    try:
        from music_workflow_song_practice import song_practice_storage_id

        stype, _sid = song_practice_storage_id(session)
        return str(stype or "catalog")
    except ImportError:
        return "catalog"


def focus_binding_matches(session: dict[str, Any], focus: dict[str, Any]) -> bool:
    if not isinstance(focus, dict):
        return False
    sid = stable_song_id(session)
    pt, pm = _practice_key_fields(session)
    if str(focus.get("stable_song_id") or "").strip() and str(focus.get("stable_song_id") or "").strip() != sid:
        return False
    if str(focus.get("practice_tonic") or "").strip() and str(focus.get("practice_tonic") or "").upper() != pt.upper():
        return False
    if str(focus.get("practice_mode") or "").strip() and str(focus.get("practice_mode") or "").lower() != pm.lower():
        return False
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    fpick = str(focus.get("active_catalog_pick_key") or "").strip()
    if fpick and pick and fpick != pick:
        return False
    return True


def read_song_creative_focus(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(SONG_CREATIVE_FOCUS_KEY)
    if isinstance(raw, dict) and focus_binding_matches(session, raw):
        return copy.deepcopy(raw)
    try:
        from music_workflow_state_store import get_workflow_blob
        from music_workflow_song_practice import song_based_blob_session_id

        sid = song_based_blob_session_id(session)
        blob = get_workflow_blob(session, "song_based_improvisation", sid)
        if blob is None or not str(blob.selected_chord_symbol or "").strip():
            return None
        rebuilt = {
            "source_type": str(blob.source_type or source_type(session)),
            "stable_song_id": sid,
            "active_catalog_pick_key": str(session.get("active_catalog_pick_key") or sid),
            "practice_tonic": str(blob.keys.practice_tonic or "C"),
            "practice_mode": str(blob.keys.practice_mode or "major"),
            "selected_section_id": str(blob.selected_section or ""),
            "selected_chord_id": int(blob.selected_chord_index or 0),
            "selected_concert_chord": str(blob.selected_chord_symbol or ""),
            "selected_written_chord": "",
            "source_page": "song_blob_restore",
            "revision": int(session.get(SONG_CREATIVE_FOCUS_REVISION_KEY) or 0),
        }
        if focus_binding_matches(session, rebuilt):
            session[SONG_CREATIVE_FOCUS_KEY] = copy.deepcopy(rebuilt)
            return copy.deepcopy(rebuilt)
    except ImportError:
        pass
    return None


def _next_revision(session: dict[str, Any]) -> int:
    prev = int(session.get(SONG_CREATIVE_FOCUS_REVISION_KEY) or 0)
    raw = session.get(SONG_CREATIVE_FOCUS_KEY)
    if isinstance(raw, dict):
        prev = max(prev, int(raw.get("revision") or 0))
    n = prev + 1
    session[SONG_CREATIVE_FOCUS_REVISION_KEY] = n
    return n


def build_song_creative_focus(
    session: dict[str, Any],
    *,
    section: str,
    concert_chord: str,
    chord_index: int,
    source_page: str,
    written_chord: str = "",
) -> dict[str, Any]:
    pt, pm = _practice_key_fields(session)
    sid = stable_song_id(session)
    rev = _next_revision(session)
    token = hashlib.sha256(
        json.dumps(
            {
                "rev": rev,
                "sid": sid,
                "pt": pt,
                "pm": pm,
                "ch": concert_chord,
                "sec": section,
                "idx": int(chord_index),
                "page": source_page,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:24]
    return {
        "source_type": source_type(session),
        "stable_song_id": sid,
        "active_catalog_pick_key": str(session.get("active_catalog_pick_key") or sid),
        "practice_tonic": pt,
        "practice_mode": pm,
        "selected_section_id": str(section or "").strip(),
        "selected_chord_id": int(chord_index),
        "selected_concert_chord": str(concert_chord or "").strip(),
        "selected_written_chord": str(written_chord or "").strip(),
        "source_page": str(source_page or "").strip(),
        "revision": rev,
        "update_token": token,
    }


def project_song_creative_focus_to_pages(session: dict[str, Any], focus: dict[str, Any]) -> None:
    chord = str(focus.get("selected_concert_chord") or "").strip()
    section = str(focus.get("selected_section_id") or "").strip()
    idx = int(focus.get("selected_chord_id") or 0)
    if not chord:
        return
    session["ii_selected_chord"] = chord
    session["II_SELECTED_CHORD"] = chord
    session["ii_selected_section"] = section
    session["II_SELECTED_SECTION"] = section
    session["ii_selected_chord_index"] = idx
    session["II_SELECTED_CHORD_INDEX"] = idx
    label = f"{section} · {chord}" if section else chord
    session["ii_selected_chord_label"] = label
    session["II_SELECTED_CHORD_LABEL"] = label
    session["harmony_map_chord"] = chord
    session["harmony_map_section"] = section


def persist_focus_on_song_blob(session: dict[str, Any], focus: dict[str, Any]) -> bool:
    try:
        from music_workflow_song_practice import song_based_blob_session_id
        from music_workflow_state_store import get_workflow_blob, save_workflow_blob

        sid = song_based_blob_session_id(session)
        blob = get_workflow_blob(session, "song_based_improvisation", sid)
        if blob is None:
            return False
        blob.selected_chord_symbol = str(focus.get("selected_concert_chord") or "")
        blob.selected_section = str(focus.get("selected_section_id") or "")
        blob.selected_chord_index = int(focus.get("selected_chord_id") or 0)
        save_workflow_blob(session, blob, source="song_creative_focus")
        return True
    except ImportError:
        return False


def commit_song_creative_focus(session: dict[str, Any], focus: dict[str, Any]) -> None:
    session[SONG_CREATIVE_FOCUS_KEY] = copy.deepcopy(focus)
    persist_focus_on_song_blob(session, focus)
    project_song_creative_focus_to_pages(session, focus)


def hydrate_creative_pages_from_song_focus(session: dict[str, Any], *, tab: str = "") -> bool:
    focus = read_song_creative_focus(session)
    if not focus:
        return False
    resolved = resolve_focus_against_progression(session, focus)
    if resolved.get("resolve_pending"):
        project_song_creative_focus_to_pages(session, focus)
        return True
    commit_song_creative_focus(session, resolved)
    return True


def _section_map_for_focus(session: dict[str, Any], ctx: Any) -> list[tuple[str, list[str]]]:
    raw = session.get("improv_song_concert_sections") or session.get("home_sections") or {}
    if isinstance(raw, dict) and raw:
        return [(str(k), [str(c) for c in v if str(c).strip()]) for k, v in raw.items() if isinstance(v, list)]
    try:
        from improvisation_motif import resolve_improv_sections

        return resolve_improv_sections(session, ctx)
    except ImportError:
        return []


def resolve_focus_against_progression(session: dict[str, Any], focus: dict[str, Any]) -> dict[str, Any]:
    """Re-bind global index / spelling against the active full song progression."""
    try:
        from improvisation_intelligence import ImprovSessionContext
        from improvisation_motif import flatten_section_map, section_and_chord_at_global_index
    except ImportError:
        return focus
    ctx = ImprovSessionContext(
        song_title=str(session.get("song") or ""),
        artist="",
        key_center=str(session.get("concert_key") or session.get("display_key") or "C"),
        display_key=str(session.get("display_key") or session.get("concert_key") or "C"),
        instrument=str(session.get("instrument") or "Piano"),
        level=str(session.get("level") or "Intermediate"),
        focus="Improvisation",
        sections=session.get("home_sections") or {},
        bpm=100,
        style_label="",
        progression_flat=[],
        section_order=[],
    )
    section_map = _section_map_for_focus(session, ctx)
    if not section_map:
        return focus
    chords = flatten_section_map(section_map)
    if not chords:
        return focus
    out = copy.deepcopy(focus)
    target = str(out.get("selected_concert_chord") or "").strip()
    sec_hint = str(out.get("selected_section_id") or "").strip()
    idx = int(out.get("selected_chord_id") or 0)
    if 0 <= idx < len(chords) and chords[idx] == target:
        sec, ch = section_and_chord_at_global_index(section_map, idx)
        if not sec_hint or sec == sec_hint:
            out["selected_section_id"] = sec or sec_hint
            out["selected_concert_chord"] = ch
            out["selected_chord_id"] = idx
            return out
    if sec_hint and target:
        try:
            from improvisation_motif import global_chord_index

            for si, (sec, chs) in enumerate(section_map):
                if sec != sec_hint:
                    continue
                for ci, ch in enumerate(chs):
                    if ch != target:
                        continue
                    gidx = global_chord_index(section_map, si, ci)
                    out["selected_chord_id"] = gidx
                    out["selected_section_id"] = sec
                    out["selected_concert_chord"] = ch
                    return out
        except ImportError:
            pass
        out["resolve_pending"] = True
        return out
    for i, ch in enumerate(chords):
        if ch == target:
            sec, _ = section_and_chord_at_global_index(section_map, i)
            if sec_hint and sec != sec_hint:
                continue
            out["selected_chord_id"] = i
            out["selected_section_id"] = sec or sec_hint
            out["selected_concert_chord"] = ch
            return out
    if target:
        out["resolve_pending"] = True
        return out
    out["selected_chord_id"] = 0
    sec, ch = section_and_chord_at_global_index(section_map, 0)
    out["selected_section_id"] = sec or ""
    out["selected_concert_chord"] = ch
    out["fallback_reason"] = "chord_not_in_progression"
    return out


def retarget_song_creative_focus_after_practice_key_change(session: dict[str, Any]) -> None:
    focus = read_song_creative_focus(session)
    if not focus:
        return
    pt, pm = _practice_key_fields(session)
    focus["practice_tonic"] = pt
    focus["practice_mode"] = pm
    resolved = resolve_focus_against_progression(session, focus)
    commit_song_creative_focus(session, resolved)


__all__ = [
    "SONG_CREATIVE_FOCUS_KEY",
    "SONG_CREATIVE_FOCUS_REVISION_KEY",
    "build_song_creative_focus",
    "commit_song_creative_focus",
    "focus_binding_matches",
    "hydrate_creative_pages_from_song_focus",
    "persist_focus_on_song_blob",
    "project_song_creative_focus_to_pages",
    "read_song_creative_focus",
    "resolve_focus_against_progression",
    "retarget_song_creative_focus_after_practice_key_change",
    "stable_song_id",
]
