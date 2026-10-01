"""Practice Melody -> Backing handoff lifecycle (Slice E).

Carries the *exact* ``practice_melody_model.PracticeMelody`` object a
musician was looking at in Practice's "Generated Practice Melody" panel
over to the Backing page, so the same melody (same seed/alt_index, same
notes) is visible while the backing track plays -- without regenerating,
and without this module becoming a second owner of canonical song/key
state.

Mirrors the existing pending-handoff pattern used for Practice's
section-loop -> Backing handoff (``backing_source_navigation.
begin_practice_loop_backing_handoff`` / the ``PENDING_BACKING_*`` keys
consumed once Backing's widgets build): a "begin" call stamps a pending
payload from Practice; a "consume" call, made once when Backing renders,
promotes it into the active slot -- but only if the song identity it was
generated for still matches the song Backing is actually showing. This
module owns exactly three of its own session keys and never reads or
writes canonical song/source/key/level state.

Lifecycle (see tests/test_practice_melody_backing.py for the exhaustive
version of each case below):

* Backing first opens with a pending handoff for the current song -> that
  melody becomes active.
* A pending handoff for a *different* song than the one Backing actually
  ends up showing (the user changed song between the click and Backing's
  first render) -> dropped, not shown.
* Ordinary Streamlit reruns on Backing (no new handoff) -> the active
  melody is returned unchanged, rerun after rerun, as long as the song
  identity still matches.
* The user changes song/source -> the next resolve call detects the
  mismatch and clears the active melody; Song A's melody never appears
  over Song B.
* A second handoff (e.g. after "Generate Another Melody" back in Practice,
  or picking a different alternate) deliberately replaces the first.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from practice_melody_model import PracticeMelody

PENDING_MELODY_KEY = "pending_backing_practice_melody"
PENDING_MELODY_SONG_IDENTITY_KEY = "pending_backing_practice_melody_song_identity"
BACKING_MELODY_KEY = "backing_practice_melody"
BACKING_MELODY_SONG_IDENTITY_KEY = "backing_practice_melody_song_identity"

_OWNED_KEYS = (
    PENDING_MELODY_KEY,
    PENDING_MELODY_SONG_IDENTITY_KEY,
    BACKING_MELODY_KEY,
    BACKING_MELODY_SONG_IDENTITY_KEY,
)


def begin_practice_melody_backing_handoff(
    session_state: MutableMapping[str, Any],
    *,
    melody: PracticeMelody,
    song_identity: str,
) -> None:
    """Stamp a pending Practice Melody handoff for Backing to consume once.

    Called from Practice's "Practice with Backing" button. Stores the exact
    melody object (same seed/alt_index) and the song identity it belongs
    to; never touches canonical song, key, instrument, or level state.
    """
    session_state[PENDING_MELODY_KEY] = melody
    session_state[PENDING_MELODY_SONG_IDENTITY_KEY] = str(song_identity or "")


def clear_backing_practice_melody(session_state: MutableMapping[str, Any]) -> None:
    """Drop the active Backing-side melody (used on identity mismatch)."""
    session_state.pop(BACKING_MELODY_KEY, None)
    session_state.pop(BACKING_MELODY_SONG_IDENTITY_KEY, None)


def clear_practice_melody_backing_state(session_state: MutableMapping[str, Any]) -> None:
    """Drop all state this module owns (pending and active)."""
    for key in _OWNED_KEYS:
        session_state.pop(key, None)


def consume_pending_practice_melody_handoff(
    session_state: MutableMapping[str, Any],
    *,
    current_song_identity: str,
) -> PracticeMelody | None:
    """Call once per Backing render, before/alongside other pending-Backing
    consumption. Idempotent and rerun-safe:

    * If a pending handoff exists: it is always consumed (popped) exactly
      once. If its song identity matches ``current_song_identity``, it
      becomes the active melody (replacing whatever was active before --
      a deliberate "second handoff wins"). If it belongs to a different
      song (the user navigated/changed song between the Practice click and
      this render), it is dropped and the active melody is cleared rather
      than shown.
    * If no pending handoff exists: falls through to
      ``resolve_active_backing_practice_melody`` so ordinary reruns keep
      returning the same already-active melody untouched.
    """
    has_pending = PENDING_MELODY_KEY in session_state
    pending = session_state.pop(PENDING_MELODY_KEY, None)
    pending_identity = session_state.pop(PENDING_MELODY_SONG_IDENTITY_KEY, None)
    if not has_pending:
        return resolve_active_backing_practice_melody(
            session_state, current_song_identity=current_song_identity
        )
    if not isinstance(pending, PracticeMelody) or pending_identity != current_song_identity:
        clear_backing_practice_melody(session_state)
        return None
    session_state[BACKING_MELODY_KEY] = pending
    session_state[BACKING_MELODY_SONG_IDENTITY_KEY] = pending_identity
    return pending


def resolve_active_backing_practice_melody(
    session_state: Mapping[str, Any],
    *,
    current_song_identity: str,
) -> PracticeMelody | None:
    """Rerun-stable read of the currently active Backing-side melody.

    Returns the same object every call as long as ``current_song_identity``
    still matches the song it was handed off for; clears and returns
    ``None`` the moment it doesn't (song/source changed), so a stale melody
    from a previous song can never be displayed over the new one.
    """
    melody = session_state.get(BACKING_MELODY_KEY)
    if not isinstance(melody, PracticeMelody):
        return None
    identity = session_state.get(BACKING_MELODY_SONG_IDENTITY_KEY)
    if identity != current_song_identity:
        if isinstance(session_state, MutableMapping):
            clear_backing_practice_melody(session_state)
        return None
    return melody
