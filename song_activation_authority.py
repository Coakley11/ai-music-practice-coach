"""Explicit song activation is the authority for which song Creative restores (MC3.3).

An explicit Songs selection commits a new source/song. Everything Creative restores
afterwards — workflow hints, sealed Mission Return destinations, page snapshots — is
scoped to the song it was saved for and is never promoted over the live song.
"""

from __future__ import annotations

from typing import Any

SONG_ACTIVATION_KEY = "_explicit_song_activation"

# Dict fields that name the song a stored value belongs to.
_SONG_IDENTITY_FIELDS = ("source_identity", "bound_pick_key", "active_song_id", "pick_key", "song_pick_key")


def song_id_from_workflow_session(session_id: Any) -> str:
    """Song part of a workflow session id (``mission|catalog|<pick>``, ``custom|<id>``, ``<pick>``)."""
    sid = str(session_id or "").strip()
    if sid.startswith("mission|"):
        sid = sid.split("|", 2)[-1]
    if sid.startswith("custom|"):
        sid = sid.split("|", 1)[-1]
    for prefix in ("custom::", "composition::", "pk::"):
        if sid.startswith(prefix):
            sid = sid[len(prefix):]
    return sid


def live_song_identity(session: dict[str, Any]) -> str:
    """``source|song`` of the song the session is on now."""
    try:
        from music_workflow_song_practice import song_practice_storage_id

        src, sid = song_practice_storage_id(session)
        return f"{src}|{sid}"
    except Exception:
        pick = str(session.get("active_catalog_pick_key") or session.get("song") or "").strip()
        return f"catalog|{pick}"


def _normalize_song_id(value: Any) -> str:
    out = str(value or "").strip()
    if out.startswith("pk::"):
        out = out[4:]
    return out


def _is_catalog_song_id(value: str) -> bool:
    return "\x1f" in value and not value.startswith(("custom::", "composition::"))


def live_catalog_song_id(session: dict[str, Any]) -> str:
    """Live catalog pick key, or "" while a Custom / Composition source is active."""
    try:
        from songs.music_source import SOURCE_CATALOG
    except ImportError:  # pragma: no cover
        SOURCE_CATALOG = "catalog_song"
    source = str(session.get("active_music_source") or "").strip()
    if source and source != SOURCE_CATALOG:
        return ""
    pick = _normalize_song_id(session.get("active_catalog_pick_key"))
    return pick if _is_catalog_song_id(pick) else ""


def belongs_to_another_song(session: dict[str, Any], song_id: Any) -> bool:
    """True when ``song_id`` names a catalog song other than the live catalog song."""
    sid = _normalize_song_id(song_id)
    live = live_catalog_song_id(session)
    return bool(live and _is_catalog_song_id(sid) and sid != live)


def stored_value_belongs_to_another_song(session: dict[str, Any], value: Any) -> bool:
    """A stored dict (snapshot entry, backing context, chord seal) saved for another song."""
    if not isinstance(value, dict):
        return False
    return any(belongs_to_another_song(session, value.get(f)) for f in _SONG_IDENTITY_FIELDS if value.get(f))


def commit_explicit_song_activation(
    session: dict[str, Any],
    *,
    owner: str,
    previous_session_id: str = "",
) -> bool:
    """Record a Songs activation; retire the previous song's workflow hint when the song changed.

    The legacy ``_active_workflow_owner`` hint describes the Creative workflow of the song
    that was active before. Once the user commits a different song or source, that hint is
    residue: left in place, it makes the next Creative activation for the new song fail
    closed (LEGACY_OWNER_ACTIVE_POINTER_MISMATCH) and keeps the old song's Creative state.
    Re-activations of the same song keep the hint, so current-song restores are unchanged.
    """
    identity = live_song_identity(session)
    record = session.get(SONG_ACTIVATION_KEY)
    previous = str(record.get("identity") or "") if isinstance(record, dict) else ""
    if previous:
        changed = previous != identity
    else:
        prev_song = song_id_from_workflow_session(previous_session_id)
        changed = bool(prev_song and prev_song != song_id_from_workflow_session(identity.split("|", 1)[-1]))
    session[SONG_ACTIVATION_KEY] = {"identity": identity, "owner": str(owner or "")}
    if changed:
        try:
            from music_workflow_mutation import set_legacy_owner_compat_hint

            set_legacy_owner_compat_hint(session, owner)
        except ImportError:
            pass
    return changed


__all__ = [
    "SONG_ACTIVATION_KEY",
    "belongs_to_another_song",
    "commit_explicit_song_activation",
    "live_catalog_song_id",
    "live_song_identity",
    "song_id_from_workflow_session",
    "stored_value_belongs_to_another_song",
]
