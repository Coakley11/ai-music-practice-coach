"""Discarding a take, and making it stay discarded. Issue 77B.

``multitrack_takes.discard_take`` has always emptied the slot correctly. The take came back anyway,
and the trace is worth keeping because the mechanism is not obvious:

1. when a take lands, the page saves, and ``build_music_disk_state`` caches an encoded copy of every
   layer in ``_mt_tracks_persist_blob``;
2. the Discard handler empties the slot and saves again - but that save **skips the whole
   ``mt_tracks`` key** when no layer holds audio (``if count_mt_layers(val) == 0: continue``), so the
   cached copy still holds the take;
3. the Multitrack page calls ``restore_multitrack_layers_from_workspace`` on **every** render, which
   treats "this session has no layers" as "this session needs hydrating" and decodes the cached copy
   straight back into ``mt_tracks``.

Measured: the restored bytes were identical to the discarded take, and the status line went back to
"Unsaved take". Discarding one take while another layer held audio stuck, because step 3
short-circuits when any layer has audio - which is why this only ever bit the last take in a
project.

That skip in step 2 is not a bug by itself. It is what stops a half-restored session - one that is
momentarily empty while a workspace loads - from writing an empty layer map over real saved
recordings. So it stays, and this module supplies the one thing it was missing: a way to tell a
**deliberate** deletion from an **incomplete** restoration.

Everything here is slot-scoped and pure. It never deletes a file, never touches a saved project row,
and never looks at a layer other than the one named.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, MutableMapping

#: Set only by a deliberate Discard Take / Delete Layer that leaves no layer holding audio. The
#: autosave consults it to tell an intended empty project from a session that has not hydrated yet.
DELIBERATELY_EMPTY_KEY = "_mt_layers_deliberately_empty"

#: Bumped by a successful removal. The transport and the chord strips use it to return to bar 1
#: beat 1 exactly once - never on an ordinary rerun.
POSITION_RESET_TOKEN_KEY = "_mt_position_reset_token"

#: Identity for a project that has no library id yet, so two unsaved projects for the same song
#: cannot share one remembered position.
WORKING_PROJECT_TOKEN_KEY = "_mt_working_project_token"

_BLOB_KEY = "_mt_tracks_persist_blob"
_SNAPSHOT_STORE_KEY = "_studio_page_snapshots"
_SNAPSHOT_PAGE = "multitrack"


# --------------------------------------------------------------------------------------------
# the caches a discarded take can come back from
# --------------------------------------------------------------------------------------------
def _has_audio(value: Any) -> bool:
    return bool(value) and isinstance(value, (bytes, bytearray))


def live_layer_count(session_state: Mapping[str, Any], slots: Iterable[str] | None = None) -> int:
    tracks = session_state.get("mt_tracks")
    if not isinstance(tracks, Mapping):
        return 0
    keys = list(slots) if slots is not None else list(tracks.keys())
    return sum(1 for slot in keys if _has_audio(tracks.get(slot)))


def clear_slot_from_caches(session_state: MutableMapping[str, Any], slot: str) -> dict[str, bool]:
    """Blank ONE slot in every cached copy a restore could hand back.

    Slot-scoped on purpose: the other layers' cached audio is left exactly as it is, so removing one
    layer can never cost the musician another. Entries are set to ``None`` rather than deleted, which
    keeps each cache's shape - a map with a key per slot - the same as the code that reads it expects.
    """
    touched = {"persist_blob": False, "page_snapshot": False}
    name = str(slot)

    blob = session_state.get(_BLOB_KEY)
    if isinstance(blob, dict) and name in blob:
        blob[name] = None
        touched["persist_blob"] = True

    store = session_state.get(_SNAPSHOT_STORE_KEY)
    snap = store.get(_SNAPSHOT_PAGE) if isinstance(store, dict) else None
    if isinstance(snap, dict):
        snap_tracks = snap.get("mt_tracks")
        if isinstance(snap_tracks, dict) and name in snap_tracks:
            snap_tracks[name] = None
            touched["page_snapshot"] = True
    return touched


# --------------------------------------------------------------------------------------------
# deliberate deletion versus incomplete restoration
# --------------------------------------------------------------------------------------------
def mark_layers_deliberately_empty(
    session_state: MutableMapping[str, Any],
    slots: Iterable[str] | None = None,
) -> bool:
    """Record that the project is empty because the musician emptied it. True when it now is.

    Only ever called straight after a removal the musician asked for, and only when nothing is left:
    an intended empty project is then saved as empty, while a session that merely has not hydrated
    yet never reaches here and is still protected by the autosave's skip.
    """
    empty = live_layer_count(session_state, slots) == 0
    if empty:
        session_state[DELIBERATELY_EMPTY_KEY] = True
    return empty


def layers_deliberately_empty(session_state: Mapping[str, Any]) -> bool:
    return bool(session_state.get(DELIBERATELY_EMPTY_KEY))


def clear_deliberately_empty(session_state: MutableMapping[str, Any]) -> None:
    """Audio is present again (a take landed, a project loaded, a workspace restored)."""
    try:
        session_state.pop(DELIBERATELY_EMPTY_KEY, None)
    except Exception:
        pass


def should_persist_empty_layer_map(
    session_state: Mapping[str, Any],
    layer_count: int,
) -> bool:
    """May an empty ``mt_tracks`` be written to the saved workspace?

    Yes when layers exist (nothing to decide), and yes when the emptiness was deliberate. No for a
    session that is merely empty, which is the state a half-finished restore passes through.
    """
    if layer_count > 0:
        return True
    return layers_deliberately_empty(session_state)


# --------------------------------------------------------------------------------------------
# the visible position, reset deliberately and only then
# --------------------------------------------------------------------------------------------
def position_reset_token(session_state: Mapping[str, Any]) -> int:
    try:
        return int(session_state.get(POSITION_RESET_TOKEN_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def request_position_reset(session_state: MutableMapping[str, Any]) -> int:
    """Return the transport and the chord strips to bar 1 beat 1, once.

    Advanced ONLY by a removal that actually removed something. An ordinary rerun - a Volume change,
    Mute, Solo, opening a panel, saving a layer, recording again - leaves it alone, so the musician's
    position survives those.
    """
    token = position_reset_token(session_state) + 1
    session_state[POSITION_RESET_TOKEN_KEY] = token
    return token


def working_project_token(session_state: MutableMapping[str, Any]) -> str:
    """A stable identity for a Multitrack project that has not been saved to the library yet.

    A saved project has ``multitrack_catalog_active_id``. An unsaved one has nothing, and a display
    name will not do - two projects for the same song can share one. Without an identity of its own,
    every unsaved project for a given song and scope keyed its remembered position to the same
    string, so starting a new one could inherit the previous one's position. This mints a token the
    first time it is needed and keeps it until the working session is deliberately reset.
    """
    token = str(session_state.get(WORKING_PROJECT_TOKEN_KEY) or "").strip()
    if not token:
        import uuid

        token = uuid.uuid4().hex[:10]
        try:
            session_state[WORKING_PROJECT_TOKEN_KEY] = token
        except Exception:
            return token
    return token


def clear_working_project_token(session_state: MutableMapping[str, Any]) -> None:
    """A new / different working project begins, so its predecessor's position must not apply."""
    try:
        session_state.pop(WORKING_PROJECT_TOKEN_KEY, None)
    except Exception:
        pass


def position_context(session_state: Any) -> str:
    """Which user, song, project and scope a remembered position belongs to.

    A position is meaningless outside the music it was taken in, so it is stored against this
    string. Four things make it up, and each one is here because leaving it out lets a position
    reach music it does not describe:

    * the **workspace** - ``sessionStorage`` is per browser tab, not per account, so two musicians
      sharing a browser would otherwise share positions;
    * the **song**;
    * the **project** - its library id when it has one, and otherwise a token of its own
      (:func:`working_project_token`), because two unsaved projects for the same song cannot be told
      apart by name;
    * the **playback scope**, since a position in "full song" means nothing in a single section.
    """
    get = session_state.get if hasattr(session_state, "get") else (lambda *_a, **_k: None)
    project = str(
        get("multitrack_catalog_active_id") or get("_last_catalog_multitrack_id") or ""
    ).strip()
    if not project:
        try:
            project = "new:" + working_project_token(session_state)
        except Exception:
            project = "new"
    parts = [
        str(get("_suite_active_workspace_id") or ""),
        str(get("active_song_title") or ""),
        project,
        str(get("mt_playback_scope") or ""),
        str(get("mt_backing_scope") or ""),
    ]
    cleaned = "|".join(p.replace("|", "/") for p in parts).strip("|")
    return cleaned or "multitrack"


# --------------------------------------------------------------------------------------------
# one entry point the page calls
# --------------------------------------------------------------------------------------------
def remove_take(
    session_state: MutableMapping[str, Any],
    slot: str,
    *,
    slots: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Discard a take / delete a layer so that it stays gone, and ask for one position reset.

    Returns what happened, so the caller can tell a real removal from a no-op: the position reset and
    the deliberate-empty marker are applied **only** when something was actually removed, which is
    what keeps a failed or repeated press from rewinding the musician's music.
    """
    from multitrack_takes import discard_take

    removed = bool(discard_take(session_state, slot))
    report: dict[str, Any] = {
        "removed": removed,
        "slot": str(slot),
        "caches": {"persist_blob": False, "page_snapshot": False},
        "deliberately_empty": False,
        "reset_token": position_reset_token(session_state),
        "timing_cleared": False,
    }
    if not removed:
        return report

    report["caches"] = clear_slot_from_caches(session_state, slot)

    # The take's own file too, with a tombstone of its hash, so a discarded take cannot be
    # restored - not even from a file that failed to delete.
    try:
        from multitrack_draft_store import discard_draft

        report["draft_discarded"] = bool(discard_draft(session_state, slot))
    except Exception:
        report["draft_discarded"] = False

    try:
        from multitrack_live_recorder import forget_take_timing

        forget_take_timing(session_state, slot)
        report["timing_cleared"] = True
    except ImportError:
        pass

    report["deliberately_empty"] = mark_layers_deliberately_empty(session_state, slots)
    report["reset_token"] = request_position_reset(session_state)
    return report


__all__ = [
    "DELIBERATELY_EMPTY_KEY",
    "POSITION_RESET_TOKEN_KEY",
    "WORKING_PROJECT_TOKEN_KEY",
    "clear_deliberately_empty",
    "clear_working_project_token",
    "clear_slot_from_caches",
    "layers_deliberately_empty",
    "live_layer_count",
    "mark_layers_deliberately_empty",
    "position_context",
    "position_reset_token",
    "remove_take",
    "request_position_reset",
    "should_persist_empty_layer_map",
    "working_project_token",
]
