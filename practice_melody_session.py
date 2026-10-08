"""Session-state lifecycle policy for the Practice page's Generated Practice
Melody sub-view.

Kept separate from the Streamlit rendering code (in
``streamlit_music_practice_app.py``) so the identity/regeneration policy is
unit-testable without a live Streamlit session — ``session_state`` here is
any plain ``dict``-like object.

Policy (see ``resolve_practice_melody`` for the authoritative statement):

* The cached melody is keyed by ``(song identity, level)``. As long as both
  match the live Practice context, the same cached
  ``practice_melody_model.PracticeMelody`` is returned on every call — so
  ordinary Streamlit reruns triggered by *unrelated* Practice controls never
  regenerate or replace it.
* The moment either the active song/source identity or the active level
  changes, the cache is treated as stale and a fresh, deterministic
  *baseline* melody (``alt_index=0``) is generated for the new context —
  never the previous context's melody, and never a silently mismatched
  level label.
* "Generate Another Melody" is the only thing that advances ``alt_index``
  for an unchanged identity, via the accepted
  ``practice_melody_generator.generate_another_practice_melody`` — a new
  composition.
* A ``key_center`` change with the song/level identity otherwise unchanged
  is a *different* operation: the cached melody is transposed in place
  (``practice_melody_transpose.transpose_practice_melody``), never
  regenerated. Same composition (``melody_id``/``seed``/``alt_index``
  unchanged), new projection key — see Slice F1.
* Song identity uses ``songs.music_source.resolve_active_song_identity`` —
  the same canonical identity string the rest of the app already uses to
  detect song/source changes — so this cache cannot be fooled by the same
  class of stale-source bugs the rest of Practice/Backing is being
  stabilized against. This module never reads or writes canonical song,
  key, instrument, or level state; it only ever reads the values the caller
  passes in and writes its own three session keys below.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

from practice_melody_generator import generate_another_practice_melody, generate_practice_melody
from practice_melody_model import PracticeMelody
from practice_melody_transpose import transpose_practice_melody

RESULT_KEY = "practice_melody_result"
IDENTITY_KEY = "practice_melody_identity"
ALT_INDEX_KEY = "practice_melody_alt_index"

_OWNED_KEYS = (RESULT_KEY, IDENTITY_KEY, ALT_INDEX_KEY)


def identity_token(song_identity: str, level: str, focus: str = "") -> str:
    """Identity for the cached melody -- song + level + Practice Focus.

    Focus is part of identity (not a separate state owner -- the canonical
    value still lives in session Practice Focus state; this just folds it
    into the existing cache key) so selecting a different focus resolves
    to a fresh baseline for the new context, the same way a level change
    already does, instead of silently keeping an unconditioned melody on
    screen."""
    return f"{song_identity}::{level}::{focus}"


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
) -> PracticeMelody | None:
    """Return the Practice Melody to display for the current live context.

    Returns ``None`` when there isn't enough structured chord/section data
    to generate from (the caller should render a graceful "unavailable"
    state) — any previously cached melody is cleared in that case rather
    than left on screen for a source it no longer belongs to.
    """
    if not sections:
        clear_practice_melody_state(session_state)
        return None

    token = identity_token(song_identity, level, focus)
    cached_token = session_state.get(IDENTITY_KEY)
    cached_melody = current_cached_melody(session_state)
    identity_matches = cached_token == token and cached_melody is not None

    if regenerate and identity_matches:
        next_melody = generate_another_practice_melody(
            cached_melody,
            sections={name: list(chords) for name, chords in sections.items()},
            section_order=list(section_order) if section_order else list(sections.keys()),
            key_center=key_center,
            tempo_bpm=tempo_bpm,
            style=style,
            meter=meter,
            focus=focus,
        )
        session_state[RESULT_KEY] = next_melody
        session_state[IDENTITY_KEY] = token
        session_state[ALT_INDEX_KEY] = next_melody.alt_index
        return next_melody

    if identity_matches:
        target_key = str(key_center or "").strip()
        if target_key and cached_melody.key_center != target_key:
            # Same song/level, different key: transpose the existing
            # composition rather than generating an unrelated new one.
            transposed = transpose_practice_melody(cached_melody, new_key_center=target_key)
            session_state[RESULT_KEY] = transposed
            session_state[IDENTITY_KEY] = token
            session_state[ALT_INDEX_KEY] = transposed.alt_index
            return transposed
        return cached_melody

    # No cached melody, or the song/level identity moved on: resolve
    # deliberately to a fresh, deterministic baseline for the *new*
    # context rather than showing (or silently keeping) anything from the
    # old one.
    melody = generate_practice_melody(
        song_id=song_id_for_generation,
        song_title=song_title,
        sections={name: list(chords) for name, chords in sections.items()},
        section_order=list(section_order) if section_order else list(sections.keys()),
        key_center=key_center,
        level=level,
        tempo_bpm=tempo_bpm,
        style=style,
        meter=meter,
        alt_index=0,
        focus=focus,
    )
    session_state[RESULT_KEY] = melody
    session_state[IDENTITY_KEY] = token
    session_state[ALT_INDEX_KEY] = 0
    return melody
