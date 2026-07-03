"""Global practice key mode — standard (per-song) vs fixed key family."""

from __future__ import annotations

from typing import Any

from music_theory import (
    coerce_key_to_mode,
    key_is_minor,
    key_mode,
    relative_major_of_minor,
    relative_minor_of_major,
)

PRACTICE_KEY_MODE_KEY = "practice_key_mode"
FIXED_PRACTICE_KEY = "fixed_practice_key"

MODE_STANDARD = "standard"
MODE_FIXED = "fixed"

_MODE_LABELS = {
    MODE_STANDARD: "Standard (Follow Song Key)",
    MODE_FIXED: "Fixed Practice Key",
}


def practice_key_mode_label(mode: str) -> str:
    return _MODE_LABELS.get(str(mode or "").strip(), _MODE_LABELS[MODE_STANDARD])


def ensure_practice_key_mode_defaults(session: dict[str, Any]) -> None:
    if str(session.get(PRACTICE_KEY_MODE_KEY) or "").strip() not in {
        MODE_STANDARD,
        MODE_FIXED,
    }:
        session[PRACTICE_KEY_MODE_KEY] = MODE_STANDARD


def get_practice_key_mode(session: dict[str, Any]) -> str:
    ensure_practice_key_mode_defaults(session)
    return str(session.get(PRACTICE_KEY_MODE_KEY) or MODE_STANDARD).strip()


def is_fixed_practice_key_mode(session: dict[str, Any]) -> bool:
    return get_practice_key_mode(session) == MODE_FIXED


def get_fixed_practice_key(session: dict[str, Any]) -> str:
    return str(session.get(FIXED_PRACTICE_KEY) or "").strip()


def set_fixed_practice_key(session: dict[str, Any], key: str) -> None:
    anchor = str(key or "").strip()
    if anchor:
        session[FIXED_PRACTICE_KEY] = anchor


def set_practice_key_mode(session: dict[str, Any], mode: str) -> None:
    m = str(mode or MODE_STANDARD).strip()
    if m not in {MODE_STANDARD, MODE_FIXED}:
        m = MODE_STANDARD
    session[PRACTICE_KEY_MODE_KEY] = m


def resolve_fixed_practice_concert_key(fixed_key: str, song_original_key: str) -> str:
    """Map a fixed key-family anchor onto the active song's major/minor mode."""
    fixed = str(fixed_key or "C").strip() or "C"
    original = str(song_original_key or "C").strip() or "C"
    if key_mode(fixed) == "major":
        if key_mode(original) == "major":
            return coerce_key_to_mode(fixed, "major")
        return relative_minor_of_major(fixed)
    if key_mode(original) == "minor":
        return coerce_key_to_mode(fixed, "minor")
    return relative_major_of_minor(fixed)


def resolve_practice_concert_key_for_song(
    session: dict[str, Any],
    song_original_key: str,
    *,
    pick_key: str = "",
    fallback: str = "",
) -> str:
    """Effective practice concert key for one song — honors fixed mode when enabled."""
    original = str(song_original_key or fallback or "C").strip() or "C"
    if is_fixed_practice_key_mode(session):
        fixed = get_fixed_practice_key(session)
        if fixed:
            return resolve_fixed_practice_concert_key(fixed, original)
        live = str(session.get("display_key") or "").strip()
        if live:
            return resolve_fixed_practice_concert_key(live, original)
        return original
    try:
        from songs.practice_key_state import get_practice_concert_key

        pk = str(pick_key or "").strip()
        saved = get_practice_concert_key(session, pk) if pk else ""
        if saved:
            return saved
    except ImportError:
        pass
    fb = str(fallback or "").strip()
    return fb or original


def apply_fixed_mode_target(
    session: dict[str, Any],
    target: str,
    song_original_key: str,
) -> str:
    """When fixed mode is on, replace a standard-mode target with the family key."""
    if not is_fixed_practice_key_mode(session):
        return str(target or "").strip() or str(song_original_key or "C").strip() or "C"
    fixed = get_fixed_practice_key(session)
    anchor = fixed or str(target or session.get("display_key") or "").strip()
    if not anchor:
        anchor = str(song_original_key or "C").strip() or "C"
    return resolve_fixed_practice_concert_key(anchor, song_original_key)


def on_practice_key_mode_change(session: dict[str, Any], *, original_key: str = "") -> None:
    """Sidebar callback when the user toggles practice key mode."""
    mode = get_practice_key_mode(session)
    if mode == MODE_FIXED:
        anchor = str(session.get("display_key") or original_key or "C").strip() or "C"
        set_fixed_practice_key(session, anchor)
        try:
            from songs.key_state import (
                BACKING_NEEDS_REGEN,
                PENDING_DISPLAY_KEY,
                invalidate_backing_cache,
                request_display_key,
            )

            resolved = resolve_fixed_practice_concert_key(anchor, original_key or anchor)
            request_display_key(session, resolved)
            session.pop(PENDING_DISPLAY_KEY, None)
            session[BACKING_NEEDS_REGEN] = True
            invalidate_backing_cache(session)
        except ImportError:
            pass
    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(session)
    except Exception:
        pass


def on_fixed_practice_concert_key_change(session: dict[str, Any], concert_key: str) -> None:
    """Persist the fixed-family anchor when the user edits Practice / Concert Key."""
    if not is_fixed_practice_key_mode(session):
        return
    key = str(concert_key or "").strip()
    if key:
        set_fixed_practice_key(session, key)


__all__ = [
    "FIXED_PRACTICE_KEY",
    "MODE_FIXED",
    "MODE_STANDARD",
    "PRACTICE_KEY_MODE_KEY",
    "apply_fixed_mode_target",
    "ensure_practice_key_mode_defaults",
    "get_fixed_practice_key",
    "get_practice_key_mode",
    "is_fixed_practice_key_mode",
    "on_fixed_practice_concert_key_change",
    "on_practice_key_mode_change",
    "practice_key_mode_label",
    "resolve_fixed_practice_concert_key",
    "resolve_practice_concert_key_for_song",
    "set_fixed_practice_key",
    "set_practice_key_mode",
]
