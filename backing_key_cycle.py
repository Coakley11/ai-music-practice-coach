"""Shared Backing Practice Key cycling — one owner, concert authority.

Cycling mutates only the current Backing owner's concert Practice Key.
Written Key is derived from the new concert token. Mode is preserved.
"""

from __future__ import annotations

from typing import Any

from music_theory import (
    NOTE_TO_MIDI,
    key_center_token,
    normalize_root,
    split_key_center,
)

BACKING_KEY_CYCLE_STEP_KEY = "backing_key_cycle_step"
BACKING_KEY_CYCLE_DIRECTION_KEY = "backing_key_cycle_direction"
BACKING_KEY_SPELLING_PREFS_KEY = "backing_key_spelling_prefs"

# Pitch-class → default spelling for black-key keys (musician-friendly).
_DEFAULT_BLACK_SPELLING: dict[int, str] = {
    1: "Db",
    3: "Eb",
    6: "F#",
    8: "Ab",
    10: "Bb",
}

_NATURAL_SPELLING: dict[int, str] = {
    0: "C",
    2: "D",
    4: "E",
    5: "F",
    7: "G",
    9: "A",
    11: "B",
}

ENHARMONIC_SPELLING_PAIRS: tuple[tuple[str, str], ...] = (
    ("C#", "Db"),
    ("D#", "Eb"),
    ("F#", "Gb"),
    ("G#", "Ab"),
    ("A#", "Bb"),
)


def _pc_of_tonic(tonic: str) -> int:
    root = normalize_root(str(tonic or "C").strip() or "C")
    return int(NOTE_TO_MIDI.get(root, 60)) % 12


def default_spelling_prefs() -> dict[str, str]:
    return {
        "C#/Db": "Db",
        "D#/Eb": "Eb",
        "F#/Gb": "F#",
        "G#/Ab": "Ab",
        "A#/Bb": "Bb",
    }


def spelling_prefs_from_session(session: dict[str, Any]) -> dict[str, str]:
    raw = session.get(BACKING_KEY_SPELLING_PREFS_KEY)
    prefs = default_spelling_prefs()
    if isinstance(raw, dict):
        for pair, default in list(prefs.items()):
            chosen = str(raw.get(pair) or "").strip()
            options = pair.split("/")
            if chosen in options:
                prefs[pair] = chosen
    return prefs


def _spelling_for_pc(pc: int, prefs: dict[str, str]) -> str:
    pc = int(pc) % 12
    if pc in _NATURAL_SPELLING:
        return _NATURAL_SPELLING[pc]
    pair_map = {
        1: "C#/Db",
        3: "D#/Eb",
        6: "F#/Gb",
        8: "G#/Ab",
        10: "A#/Bb",
    }
    pair = pair_map.get(pc, "")
    chosen = str(prefs.get(pair) or "").strip()
    if chosen:
        return chosen
    return _DEFAULT_BLACK_SPELLING.get(pc, _NATURAL_SPELLING.get(pc, "C"))


def cycle_concert_practice_key(
    token: str,
    *,
    semitones: int,
    spelling_prefs: dict[str, str] | None = None,
) -> str:
    """Move concert Practice Key by ``semitones``; preserve major/minor mode."""
    tonic, mode = split_key_center(str(token or "C").strip() or "C")
    prefs = spelling_prefs or default_spelling_prefs()
    pc = (_pc_of_tonic(tonic) + int(semitones)) % 12
    new_tonic = _spelling_for_pc(pc, prefs)
    return key_center_token(new_tonic, mode or "major")


def cycle_step_semitones(session: dict[str, Any]) -> int:
    step = str(session.get(BACKING_KEY_CYCLE_STEP_KEY) or "semitone").strip().lower()
    direction = str(session.get(BACKING_KEY_CYCLE_DIRECTION_KEY) or "up").strip().lower()
    magnitude = 2 if step in {"whole", "wholetone", "whole_tone", "whole tone"} else 1
    return magnitude if direction != "down" else -magnitude


def current_backing_owner_practice_key(session: dict[str, Any]) -> str:
    """Concert Practice Key of the current Backing owner only."""
    try:
        from backing_practice_key_control import canonical_concert_key_for_owner

        owned = str(canonical_concert_key_for_owner(session) or "").strip()
        if owned:
            return owned
    except ImportError:
        pass
    try:
        from creative_key_sync import live_backing_source, resolve_practice_key_write_owner

        owner = resolve_practice_key_write_owner(session)
        src = live_backing_source(session)
    except ImportError:
        owner = ""
        src = ""
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "backing" and src == "entry_jam":
        entry = str(session.get("improv_entry_mode") or "").strip()
        if "Style Jam" in entry:
            tok = str(session.get("improv_style_key") or "").strip()
            if tok:
                return tok
        try:
            from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY

            raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
            if isinstance(raw, dict):
                tok = str(raw.get("practice_key_token") or "").strip()
                if tok:
                    return tok
        except ImportError:
            pass
        if "Style Jam" in entry:
            return str(session.get("improv_style_key") or session.get("display_key") or "C").strip()
        return str(
            session.get("improv_jam_key")
            or session.get("improv_style_key")
            or session.get("display_key")
            or "C"
        ).strip()
    if page == "backing" and src == "mission":
        try:
            from creative_key_sync import canonical_mission_practice_key

            tok = str(canonical_mission_practice_key(session) or "").strip()
            if tok:
                return tok
        except ImportError:
            pass
    if owner == "custom" or src == "custom_progression":
        try:
            from source_session_state import resolve_sbi_custom_practice_key

            tok = str(resolve_sbi_custom_practice_key(session) or "").strip()
            if tok:
                return tok
        except ImportError:
            pass
        return str(session.get("display_key") or "C").strip()
    if src == "song_improv":
        try:
            from source_session_state import get_sbi_preview_source, resolve_sbi_custom_practice_key

            if get_sbi_preview_source(session) == "Custom progression":
                tok = str(resolve_sbi_custom_practice_key(session) or "").strip()
                if tok:
                    return tok
        except ImportError:
            pass
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

        pick = str(resolve_practice_source_pick(session) or "").strip()
        if pick and not pick.startswith("creative::"):
            saved = str(get_practice_concert_key(session, pick) or "").strip()
            if saved:
                return saved
    except ImportError:
        pass
    return str(session.get("display_key") or session.get("concert_key") or "C").strip() or "C"


def _stamp_cycle_commit(session: dict[str, Any], new: str) -> None:
    session["display_key"] = new
    session["concert_key"] = new
    session["_pending_display_key"] = new
    session["_pk_user_commit_token"] = new
    session["display_key_change_source"] = "backing_key_cycle"
    try:
        from backing_practice_key_control import backing_practice_key_widget_id

        session[backing_practice_key_widget_id(session)] = new
    except ImportError:
        pass
    try:
        import time as _time

        session["_pk_user_commit_at"] = _time.time()
    except Exception:
        pass


def apply_backing_key_cycle(session: dict[str, Any], *, semitones: int | None = None) -> str:
    """Cycle the current Backing owner's concert Practice Key. Written is derived."""
    try:
        from creative_key_sync import live_backing_source, resolve_practice_key_write_owner

        owner = resolve_practice_key_write_owner(session)
        src = live_backing_source(session)
    except ImportError:
        owner = "catalog"
        src = ""
    steps = int(semitones) if semitones is not None else cycle_step_semitones(session)
    current = current_backing_owner_practice_key(session)
    prefs = spelling_prefs_from_session(session)
    new = cycle_concert_practice_key(current, semitones=steps, spelling_prefs=prefs)
    if not new:
        return current
    if owner == "entry_jam" or src == "entry_jam":
        applied = ""
        try:
            from creative_key_sync import apply_specialized_jam_practice_key

            applied = str(apply_specialized_jam_practice_key(session, new) or "").strip()
        except ImportError:
            applied = ""
        if not applied:
            session["improv_style_key"] = new
            session["improv_jam_key"] = new
        else:
            entry = str(session.get("improv_entry_mode") or "").strip()
            if "Style Jam" in entry:
                session["improv_style_key"] = new
            else:
                session["improv_jam_key"] = new
        _stamp_cycle_commit(session, new)
        return new
    if owner == "mission" or src == "mission":
        try:
            from creative_key_sync import apply_specialized_mission_practice_key

            apply_specialized_mission_practice_key(session, new)
        except ImportError:
            session["improv_mission_concert_key"] = new
        _stamp_cycle_commit(session, new)
        return new
    if owner == "custom" or src == "custom_progression":
        try:
            from custom_progression_lab import cpl_active_from_session, sync_custom_workspace_practice_key

            sync_custom_workspace_practice_key(
                session,
                practice_key=new,
                active=cpl_active_from_session(session),
                source="backing_key_cycle",
            )
        except ImportError:
            pass
        _stamp_cycle_commit(session, new)
        return new
    if src == "song_improv":
        try:
            from source_session_state import get_sbi_preview_source

            if get_sbi_preview_source(session) == "Custom progression":
                session["_sbi_custom_visit_pk"] = new
                _stamp_cycle_commit(session, new)
                return new
        except ImportError:
            pass
    try:
        from songs.practice_key_state import resolve_practice_source_pick, set_practice_concert_key

        pick = str(resolve_practice_source_pick(session) or "").strip()
        if pick and not str(pick).startswith("creative::"):
            set_practice_concert_key(session, new, pick_key=pick, allow_restore_original=True)
    except ImportError:
        pass
    session["_creative_visit_practice_key"] = new
    _stamp_cycle_commit(session, new)
    return new


def render_backing_key_cycle_controls(st: Any, session: dict[str, Any]) -> None:
    """No-op: Backing transport Cycle key UI is deferred, not a merge requirement.

    Helpers such as ``apply_backing_key_cycle`` remain for isolated tests. Do not
    render visible Cycle controls until the deferred Key Cycle Practice feature
    is scheduled after Creative/Backing stabilization.
    """
    _ = (st, session)
    return


__all__ = [
    "BACKING_KEY_CYCLE_DIRECTION_KEY",
    "BACKING_KEY_CYCLE_STEP_KEY",
    "BACKING_KEY_SPELLING_PREFS_KEY",
    "ENHARMONIC_SPELLING_PAIRS",
    "apply_backing_key_cycle",
    "current_backing_owner_practice_key",
    "cycle_concert_practice_key",
    "cycle_step_semitones",
    "default_spelling_prefs",
    "render_backing_key_cycle_controls",
    "spelling_prefs_from_session",
]
