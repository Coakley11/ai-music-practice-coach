"""Canonical music source ownership transitions — full clear, full rebuild.

When ownership changes the previous owner loses completely; the new owner
rebuilds backing_context, key, BPM, style, sections, and preference together.
"""

from __future__ import annotations

from typing import Any, Literal

PracticeOwner = Literal["catalog", "custom"]
BackingOwner = Literal["catalog", "custom", "entry_jam", "song_improv", "mission"]


def intended_practice_owner(session: dict[str, Any]) -> PracticeOwner | None:
    """Live practice owner from active_music_source (not backing_pref or backing_context).

    Returns None when an intentional Creative backing workflow owns the session
    (Entry Jam / SBI / Mission opened from Creative) so practice catalog pick
    does not clobber active creative backing.
    """
    try:
        from songs.music_source import (
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        if (
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        ):
            return "custom"
        if session.get(USER_CATALOG_SOURCE_CHOICE_KEY):
            return "catalog"
        try:
            from backing_context import (
                BACKING_PREF_CREATIVE,
                get_backing_context,
                get_backing_source_preference,
            )

            pref = get_backing_source_preference(session)
            ctx = get_backing_context(session)
            if (
                pref == BACKING_PREF_CREATIVE
                and ctx is not None
                and str(ctx.source or "") in {"entry_jam", "song_improv", "mission"}
            ):
                return None
        except ImportError:
            pass
        if str(session.get("active_music_source") or "").strip() == SOURCE_CATALOG:
            return "catalog"
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        if pick and not pick.startswith("custom::"):
            return "catalog"
    except ImportError:
        pass
    return None


def current_backing_owner(session: dict[str, Any]) -> BackingOwner | None:
    """Owner implied by the active backing_context snapshot."""
    try:
        from backing_context import get_backing_context
    except ImportError:
        return None
    ctx = get_backing_context(session)
    if ctx is None:
        return None
    src = str(ctx.source or "").strip()
    if src == "regular_song":
        return "catalog"
    if src == "custom_progression":
        return "custom"
    if src in {"entry_jam", "song_improv", "mission"}:
        return src  # type: ignore[return-value]
    return None


def backing_preference_owner(session: dict[str, Any]) -> PracticeOwner | None:
    try:
        from backing_context import (
            BACKING_PREF_CATALOG,
            BACKING_PREF_CUSTOM,
            get_backing_source_preference,
        )

        pref = get_backing_source_preference(session)
        if pref == BACKING_PREF_CATALOG:
            return "catalog"
        if pref == BACKING_PREF_CUSTOM:
            return "custom"
    except ImportError:
        pass
    return None


def practice_backing_owners_align(session: dict[str, Any]) -> bool:
    """True when live practice source, backing_context, and pref all agree."""
    practice = intended_practice_owner(session)
    if practice is None:
        return True
    backing = current_backing_owner(session)
    pref = backing_preference_owner(session)
    if practice == "catalog":
        return backing == "catalog" and pref == "catalog"
    return backing == "custom" and pref == "custom"


def _clear_cross_owner_transport(session: dict[str, Any]) -> None:
    """Drop transport keys that leak BPM/style/meter across owners."""
    for key in (
        "last_backing_defaults_song_id",
        "_canonical_backing_id",
        "_backing_trace_sync_id",
    ):
        session.pop(key, None)
    try:
        from songs.bpm_state import LAST_BPM_SONG

        session.pop(LAST_BPM_SONG, None)
    except ImportError:
        session.pop("_last_bpm_song", None)
    try:
        from songs.playback_defaults import _CANONICAL_BACKING_ID_KEY

        session.pop(_CANONICAL_BACKING_ID_KEY, None)
    except ImportError:
        pass


def activate_catalog_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    """Catalog song owns everything — release prior owner, rebuild from active catalog pick."""
    _clear_cross_owner_transport(session)
    from backing_context import restore_regular_song_backing

    return restore_regular_song_backing(session, st_like=st_like)


def activate_custom_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    """Custom progression owns everything — release prior owner, rebuild from CPL active song."""
    _clear_cross_owner_transport(session)
    from backing_context import restore_custom_song_backing

    return restore_custom_song_backing(session, st_like=st_like)


def activate_entry_jam_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    """Entry Jam / Style Jam owns backing — rebuild creative entry_jam context."""
    from backing_context import open_backing_from_creative

    return open_backing_from_creative(session, source="entry_jam", st_like=st_like)


def activate_sbi_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    """Song-Based Improvisation owns backing — rebuild song_improv context."""
    from backing_context import open_backing_from_creative

    return open_backing_from_creative(session, source="song_improv", st_like=st_like)


def activate_mission_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> Any:
    from backing_context import open_backing_from_creative

    return open_backing_from_creative(session, source="mission", st_like=st_like)


def reconcile_source_ownership(session: dict[str, Any], *, st_like: Any | None = None) -> bool:
    """Transition backing to match practice owner when practice owns and backing is stale."""
    practice = intended_practice_owner(session)
    if practice is None:
        return False
    if practice_backing_owners_align(session):
        return False
    try:
        from backing_context import ctx_is_stale_creative_for_practice, get_backing_context

        ctx = get_backing_context(session)
        if not ctx_is_stale_creative_for_practice(session, ctx):
            backing = current_backing_owner(session)
            pref = backing_preference_owner(session)
            if backing == practice and pref == practice:
                return False
    except ImportError:
        pass
    if practice == "catalog":
        activate_catalog_ownership(session, st_like=st_like)
        return True
    activate_custom_ownership(session, st_like=st_like)
    return True


__all__ = [
    "PracticeOwner",
    "BackingOwner",
    "activate_catalog_ownership",
    "activate_custom_ownership",
    "activate_entry_jam_ownership",
    "activate_mission_ownership",
    "activate_sbi_ownership",
    "backing_preference_owner",
    "current_backing_owner",
    "intended_practice_owner",
    "practice_backing_owners_align",
    "reconcile_source_ownership",
]
