"""Session-state lifecycle policy for the Practice page's Generated Practice
Melody sub-view.

Kept separate from the Streamlit rendering code (in
``streamlit_music_practice_app.py``) so the identity/regeneration policy is
unit-testable without a live Streamlit session — ``session_state`` here is
any plain ``dict``-like object.

The store and the composing / projecting policy are ``practice_melody_library``'s: one melody per song or jam
and per style, level and Practice Focus, transposed (never recomposed) for a key, refitted (never recomposed) for
an instrument, with every alternative kept. This module feeds it the Practice page's live context, including the
instrument's register, and holds the melody now on that page. It never reads or writes canonical song, key,
instrument or level state.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

import practice_melody_library as library
from practice_melody_model import PracticeMelody

RESULT_KEY = "practice_melody_result"
IDENTITY_KEY = "practice_melody_identity"
ALT_INDEX_KEY = "practice_melody_alt_index"

_OWNED_KEYS = (RESULT_KEY, IDENTITY_KEY, ALT_INDEX_KEY)


def instrument_register_args(session_state: Mapping[str, Any], instrument: str) -> dict[str, Any]:
    """``instrument`` / ``written_offset`` for the generator, from the canonical transposition state
    (selected saxophone type + whether the chart is in the instrument's written key)."""
    name = str(instrument or "").strip()
    if not name:
        return {}
    offset = 0
    try:
        from instrument_transposition import (
            TRANSPOSING_INSTRUMENTS,
            chart_in_instrument_key,
            is_transposing_instrument,
            selected_transposing_type,
        )

        if is_transposing_instrument(name):
            name = selected_transposing_type(dict(session_state), name) or name
            if not chart_in_instrument_key(session_state):
                offset = int(TRANSPOSING_INSTRUMENTS.get(name, 0))      # concert chart: pitches sit below written
    except Exception:
        pass
    return {"instrument": name, "written_offset": offset}


def identity_token(song_identity: str, level: str, focus: str = "", register: str = "") -> str:
    """Identity for the cached melody -- song + level + Practice Focus.

    Focus is part of identity (not a separate state owner -- the canonical
    value still lives in session Practice Focus state; this just folds it
    into the existing cache key) so selecting a different focus resolves
    to a fresh baseline for the new context, the same way a level change
    already does, instead of silently keeping an unconditioned melody on
    screen."""
    return f"{song_identity}::{level}::{focus}" + (f"::{register}" if register else "")


def clear_practice_melody_state(session_state: MutableMapping[str, Any]) -> None:
    for key in _OWNED_KEYS:
        session_state.pop(key, None)


def current_cached_melody(session_state: Mapping[str, Any]) -> PracticeMelody | None:
    cached = session_state.get(RESULT_KEY)
    return cached if isinstance(cached, PracticeMelody) else None


def resolve_practice_melody(
    session_state: MutableMapping[str, Any],
    *,
    song_identity: str,
    song_id_for_generation: str,
    song_title: str,
    sections: Mapping[str, Sequence[str]] | None,
    section_order: Sequence[str] | None,
    key_center: str,
    level: str,
    tempo_bpm: float,
    style: str,
    meter: tuple[int, int] = (4, 4),
    regenerate: bool = False,
    focus: str = "",
    instrument: str = "",
) -> PracticeMelody | None:
    """The Practice Melody for the current live context (None without chord data: nothing from another source
    is left on screen). ``sections`` are in ``key_center``. ``regenerate`` composes another alternative."""
    if not sections:
        clear_practice_melody_state(session_state)
        return None
    register_args = instrument_register_args(session_state, instrument)
    melody = library.resolve(
        session_state,
        identity=song_id_for_generation or song_identity,
        title=song_title,
        sections={name: list(chords) for name, chords in sections.items()},
        section_order=list(section_order) if section_order else list(sections),
        sections_key=str(key_center or "C"),
        level=level,
        tempo_bpm=tempo_bpm,
        style=style,
        meter=meter,
        focus=focus,
        instrument=str(register_args.get("instrument") or instrument or ""),
        written_offset=int(register_args.get("written_offset") or 0),
        another=bool(regenerate and library.has_melody(session_state, song_id_for_generation or song_identity)),
    )
    if melody is None:
        clear_practice_melody_state(session_state)
        return None
    session_state[RESULT_KEY] = melody
    session_state[IDENTITY_KEY] = identity_token(song_identity, level, focus)
    session_state[ALT_INDEX_KEY] = melody.alt_index
    return melody
