"""Backing-track time signature session state (song default + user override)."""

from __future__ import annotations

from typing import Any

from .meter import BACKING_TIME_SIGNATURES, normalize_time_signature

BACKING_METER_KEY = "backing_time_signature"
BACKING_METER_OVERRIDE_KEY = "backing_time_signature_override"
LAST_BACKING_METER_SONG = "_last_backing_meter_song"
# Which active song (``sync_id``) a genuine user meter override was chosen for.
# Persisted next to ``backing_time_signature_override`` so "Load Last Song" /
# restore can tell "my override for THIS song" from a leftover of another song.
BACKING_METER_OVERRIDE_SONG_KEY = "backing_time_signature_override_song"
_CANONICAL_BACKING_ID_KEY = "_canonical_active_backing_song_id"


def reset_backing_meter_tracking(st: Any) -> None:
    st.session_state.pop(LAST_BACKING_METER_SONG, None)
    st.session_state.pop(BACKING_METER_KEY, None)
    st.session_state.pop(BACKING_METER_OVERRIDE_KEY, None)
    st.session_state.pop(BACKING_METER_OVERRIDE_SONG_KEY, None)


def capture_saved_meter_override(session: dict[str, Any]) -> dict[str, str] | None:
    """The user's meter override as currently held (live session, else canonical blob).

    Used by a song (re)activation such as "Load Last Song" BEFORE the song-change
    reset wipes it. Returns ``{"meter", "song"}`` or ``None`` when no override
    flag is set. The live session wins when it carries the flag key (it is what
    the radio last wrote); the persisted blob is only the fallback.
    """
    if BACKING_METER_OVERRIDE_KEY in session:
        if not bool(session.get(BACKING_METER_OVERRIDE_KEY)):
            return None
        return {
            "meter": str(session.get(BACKING_METER_KEY) or ""),
            "song": str(session.get(BACKING_METER_OVERRIDE_SONG_KEY) or ""),
        }
    try:
        from backing_track_state import canonical_backing_filters

        blob = canonical_backing_filters(session) or {}
    except ImportError:
        blob = {}
    if not blob.get(BACKING_METER_OVERRIDE_KEY):
        return None
    return {
        "meter": str(blob.get(BACKING_METER_KEY) or ""),
        "song": str(blob.get(BACKING_METER_OVERRIDE_SONG_KEY) or ""),
    }


def restore_saved_meter_override(
    session: dict[str, Any],
    saved: dict[str, str] | None,
    *,
    sync_id: str,
    song_default_meter: str,
    untagged_ok: bool = True,
) -> bool:
    """Re-apply a genuine saved override right after a song (re)activation reset.

    Genuine = the flag was set AND the saved meter differs from this song's own
    meter (an override equal to the song meter has no effect) AND it was chosen
    for this same song (tag == ``sync_id``). A legacy blob without a song tag is
    accepted only under the first two conditions: it cannot be told apart from an
    old-bug ``(4/4, True)`` leftover, which is documented residual ambiguity; it
    is only accepted when ``untagged_ok`` (cold start or re-activating the very
    same song), never when the user is leaving another song for this one.
    Anything else (another song's override, equal meter) stays cleared.
    """
    if not saved:
        return False
    song_default = normalize_time_signature(song_default_meter)
    meter = normalize_time_signature(saved.get("meter") or "")
    if meter not in BACKING_TIME_SIGNATURES or meter == song_default:
        return False
    tag = str(saved.get("song") or "").strip()
    if tag and tag != str(sync_id or "").strip():
        return False
    if not tag and not untagged_ok:
        return False
    session[BACKING_METER_KEY] = meter
    session[BACKING_METER_OVERRIDE_KEY] = True
    session[BACKING_METER_OVERRIDE_SONG_KEY] = str(sync_id or "")
    session[LAST_BACKING_METER_SONG] = str(sync_id or "")
    try:
        from backing_track_state import BACKING_STATE_KEY

        blob = session.get(BACKING_STATE_KEY)
        if isinstance(blob, dict):
            session[BACKING_STATE_KEY] = {
                **blob,
                BACKING_METER_KEY: meter,
                BACKING_METER_OVERRIDE_KEY: True,
                BACKING_METER_OVERRIDE_SONG_KEY: str(sync_id or ""),
            }
    except ImportError:
        pass
    return True


def apply_backing_meter_for_song(
    st: Any,
    *,
    song_id: str,
    default_time_signature: str,
) -> tuple[str, bool, str]:
    """
    Sync meter with active song; preserve user override until the song changes.

    Returns (applied_meter, user_override, song_default_meter).
    """
    song_default = normalize_time_signature(default_time_signature)
    ss = st.session_state
    if bool(ss.get(BACKING_METER_OVERRIDE_KEY, False)):
        applied = normalize_time_signature(ss.get(BACKING_METER_KEY, song_default))
        if applied not in BACKING_TIME_SIGNATURES:
            applied = song_default
            ss[BACKING_METER_KEY] = applied
        return applied, True, song_default

    song_changed = ss.get(LAST_BACKING_METER_SONG) != song_id

    if song_changed and st.session_state.get(LAST_BACKING_METER_SONG) is None:
        try:
            from backing_track_state import has_restored_backing_canonical, prepare_backing_meter_for_widget

            if has_restored_backing_canonical(st.session_state):
                applied, override = prepare_backing_meter_for_widget(
                    st.session_state,
                    default_meter=song_default,
                )
                st.session_state[LAST_BACKING_METER_SONG] = song_id
                if not override:
                    # No genuine user override: a restored/saved meter (the blob
                    # defaults to "4/4") must never beat the song's own meter.
                    applied = song_default
                    st.session_state[BACKING_METER_KEY] = applied
                    st.session_state[BACKING_METER_OVERRIDE_KEY] = False
                    st.session_state.pop(BACKING_METER_OVERRIDE_SONG_KEY, None)
                if applied not in BACKING_TIME_SIGNATURES:
                    applied = song_default
                    st.session_state[BACKING_METER_KEY] = applied
                return applied, override, song_default
        except ImportError:
            pass

    if song_changed:
        from .key_state import invalidate_backing_cache

        invalidate_backing_cache(st)
        st.session_state[LAST_BACKING_METER_SONG] = song_id
        st.session_state[BACKING_METER_KEY] = song_default
        st.session_state[BACKING_METER_OVERRIDE_KEY] = False
        st.session_state.pop(BACKING_METER_OVERRIDE_SONG_KEY, None)
    elif BACKING_METER_KEY not in st.session_state:
        st.session_state[BACKING_METER_KEY] = song_default

    applied = normalize_time_signature(ss.get(BACKING_METER_KEY, song_default))
    if applied not in BACKING_TIME_SIGNATURES:
        applied = song_default
        ss[BACKING_METER_KEY] = applied

    override = bool(ss.get(BACKING_METER_OVERRIDE_KEY, False))
    if not override and applied != song_default:
        override = True
        ss[BACKING_METER_OVERRIDE_KEY] = True
    return applied, override, song_default


def note_backing_meter_override(st: Any, time_signature: str) -> None:
    from .key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

    st.session_state[BACKING_METER_KEY] = normalize_time_signature(time_signature)
    st.session_state[BACKING_METER_OVERRIDE_KEY] = True
    st.session_state[BACKING_METER_OVERRIDE_SONG_KEY] = str(
        st.session_state.get(_CANONICAL_BACKING_ID_KEY) or ""
    )
    invalidate_backing_cache(st)
    st.session_state[BACKING_NEEDS_REGEN] = True


def sync_backing_meter_override_from_widget(
    session: dict[str, Any],
    song_default_meter: str,
) -> tuple[str, bool]:
    """Post-render: derive override flag from live meter radio (deferred sync)."""
    song_default = normalize_time_signature(song_default_meter)
    choice = normalize_time_signature(session.get(BACKING_METER_KEY, song_default))
    if choice not in BACKING_TIME_SIGNATURES:
        choice = song_default
        session[BACKING_METER_KEY] = choice
    override = choice != song_default
    session[BACKING_METER_OVERRIDE_KEY] = override
    if not override:
        session.pop(BACKING_METER_OVERRIDE_SONG_KEY, None)
    elif not session.get(BACKING_METER_OVERRIDE_SONG_KEY):
        session[BACKING_METER_OVERRIDE_SONG_KEY] = str(session.get(_CANONICAL_BACKING_ID_KEY) or "")
    return choice, override
