"""A saved Karaoke setlist stays saved until the singer deliberately changes it.

The defect this closes (reproduced on dev f42e1d0b, isolated data,
``scripts/_accept_karaoke_setlist_durability.py``): every save writes a WHOLE session - to the
server's disk and to the cloud row - and the setlist rode along in it. So any session that did not
hold the setlist could erase it without anyone touching it:

1. a tab opened before the setlist existed changes page, and its save writes a session with no
   setlist to the server disk;
2. the next new session on that server restores from that disk, so it shows an empty setlist;
3. that session changes page, and its save replaces the cloud row's session - setlist gone;
4. the tab that built the setlist is now behind the cloud, so its saves are refused, silently;
5. a restart or redeploy replaces the disk, and nothing anywhere still holds the setlist.

The rule here: **only a deliberate edit can change a stored setlist.** Every edit made through the
setlist controls is stamped (``karaoke_setlist_meta.saved_at``). Whenever two copies meet - a save
meeting what is already stored, or a restore meeting the copies on disk and in the cloud - the
newest deliberate edit wins. A copy that is missing, or empty without a deliberate clear behind it,
never replaces a real setlist. A deliberate Clear is an edit like any other, so it does win.

No expiry: nothing here ages a setlist out.
"""
from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any

QUEUE_KEY = "karaoke_queue"
META_KEY = "karaoke_setlist_meta"
SAVE_STATUS_KEY = "_karaoke_setlist_save_status"
TRACE_KEY = "_karaoke_setlist_durability_trace"

_LOCK = threading.Lock()
#: Last setlist this server process wrote to (or read from) each disk state file. All sessions on a
#: server share the process, so this is what the file holds without re-reading a large file on
#: every save. A process restart empties it and the file is read once.
_DISK_SETLIST: dict[str, tuple[tuple[int, int], list | None, dict | None]] = {}


def _file_sig(path_key: str) -> tuple[int, int] | None:
    import os

    try:
        st_ = os.stat(path_key)
    except OSError:
        return None
    return (int(st_.st_mtime_ns), int(st_.st_size))


def _disk_known(path_key: str, load_prior: Any) -> tuple[list | None, dict | None]:
    """What the disk file holds now. The cache is trusted only while the file is unchanged."""
    sig = _file_sig(path_key)
    if sig is None:
        return None, None
    with _LOCK:
        hit = _DISK_SETLIST.get(path_key)
    if hit is not None and hit[0] == sig:
        return hit[1], hit[2]
    try:
        known = setlist_of(load_prior())
    except Exception:
        return None, None
    with _LOCK:
        _DISK_SETLIST[path_key] = (sig, copy.deepcopy(known[0]), copy.deepcopy(known[1]))
    return known


def now_stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _session_part(state: Any) -> dict | None:
    """The dict that holds the setlist: a disk/cloud state has it under ``session``."""
    if not isinstance(state, dict):
        return None
    inner = state.get("session")
    if isinstance(inner, dict):
        return inner
    if QUEUE_KEY in state or META_KEY in state:
        return state
    return None


def setlist_of(state: Any) -> tuple[list | None, dict | None]:
    part = _session_part(state)
    if part is None:
        return None, None
    queue = part.get(QUEUE_KEY)
    meta = part.get(META_KEY)
    return (queue if isinstance(queue, list) else None), (meta if isinstance(meta, dict) else None)


def _rank(queue: list | None, meta: dict | None) -> tuple:
    """Higher wins. Missing < legacy (no stamp) < stamped; stamped ones by time.

    Among unstamped (older) copies a non-empty one beats an empty one, so an empty list that no
    deliberate clear produced can never replace songs.
    """
    if queue is None:
        return (0,)
    stamp = str((meta or {}).get("saved_at") or "")
    if stamp:
        return (2, stamp)
    return (1, 1 if queue else 0)


def better(candidate: tuple[list | None, dict | None], incumbent: tuple[list | None, dict | None]) -> bool:
    """True when ``candidate`` should replace ``incumbent``."""
    return _rank(*candidate) > _rank(*incumbent)


def _trace(session: Any, event: str, **fields: Any) -> None:
    try:
        if session is None:
            return
        log = session.get(TRACE_KEY)
        if not isinstance(log, list):
            log = []
        rec = {"event": event, **fields}
        log.append(rec)
        session[TRACE_KEY] = log[-40:]
    except Exception:
        pass


def _summary(queue: list | None, meta: dict | None) -> dict:
    return {"songs": None if queue is None else len(queue), "stamp": str((meta or {}).get("saved_at") or "")}


# --------------------------------------------------------------------------- edits

def stamp_deliberate_edit(session: Any) -> dict:
    """Mark the session's current setlist as the singer's latest deliberate choice."""
    queue = session.get(QUEUE_KEY)
    if not isinstance(queue, list):
        queue = []
        session[QUEUE_KEY] = queue
    meta = {"saved_at": now_stamp(), "count": len(queue), "deliberate": True}
    session[META_KEY] = meta
    _trace(session, "deliberate_edit", **_summary(queue, meta))
    return meta


# --------------------------------------------------------------------------- saves

def merge_into_state(new_state: dict, prior_state: Any, *, where: str, session: Any = None) -> dict:
    """Return ``new_state`` with the stored setlist kept when the new one may not replace it."""
    prior = setlist_of(prior_state)
    if prior[0] is None:
        return new_state
    incoming = setlist_of(new_state)
    if not better(prior, incoming):
        return new_state
    out = dict(new_state)
    if isinstance(out.get("session"), dict):
        part = dict(out["session"])
        out["session"] = part
    elif "core" in out:
        part = {}
        out["session"] = part
    else:
        part = out
    part[QUEUE_KEY] = copy.deepcopy(prior[0])
    if prior[1] is not None:
        part[META_KEY] = copy.deepcopy(prior[1])
    else:
        part.pop(META_KEY, None)
    _trace(session, "kept_stored_setlist", where=where, stored=_summary(*prior), refused=_summary(*incoming))
    return out


def merge_disk_state(path_key: str, new_state: dict, load_prior: Any, *, session: Any = None) -> dict:
    """Disk save: keep the setlist the file holds unless this save may replace it."""
    known = _disk_known(path_key, load_prior)
    prior = {"session": {QUEUE_KEY: known[0], META_KEY: known[1]}} if known[0] is not None else None
    return merge_into_state(new_state, prior, where="disk", session=session)


def note_disk_written(path_key: str, state: Any) -> None:
    q, m = setlist_of(state)
    sig = _file_sig(path_key)
    with _LOCK:
        if sig is None:
            _DISK_SETLIST.pop(path_key, None)
        else:
            _DISK_SETLIST[path_key] = (sig, copy.deepcopy(q), copy.deepcopy(m))


def merge_cloud_full_session(incoming_full_session: Any, prior_full_session: Any, *, session: Any = None) -> Any:
    """Cloud save: the same rule against the full session the row already stores.

    When the stored setlist is kept, the saving session adopts it too, so what it shows and what
    it saves next match the row (otherwise its read-back check would see a mismatch and retry).
    """
    if not isinstance(incoming_full_session, dict):
        return incoming_full_session
    merged = merge_into_state(incoming_full_session, prior_full_session, where="cloud", session=session)
    if merged is not incoming_full_session and session is not None:
        _adopt(session, setlist_of(merged), where="cloud_save")
    return merged


def _adopt(session: Any, setlist: tuple[list | None, dict | None], *, where: str) -> None:
    queue, meta = setlist
    if queue is None:
        return
    try:
        session[QUEUE_KEY] = copy.deepcopy(queue)
        if meta is not None:
            session[META_KEY] = copy.deepcopy(meta)
        else:
            session.pop(META_KEY, None)
        _trace(session, "adopted_stored_setlist", where=where, **_summary(queue, meta))
    except Exception:
        pass


def forget_disk_file(path_key: str) -> None:
    """The file was deleted on purpose (Reset to default): forget what it held."""
    with _LOCK:
        _DISK_SETLIST.pop(path_key, None)


def reset_disk_cache_for_tests() -> None:
    with _LOCK:
        _DISK_SETLIST.clear()


# --------------------------------------------------------------------------- restores

def reconcile_session(session: Any, sources: list[tuple[str, Any]]) -> str:
    """Give the session the best setlist among its own and each restore source. Returns the winner."""
    best_name = "session"
    best = (session.get(QUEUE_KEY) if isinstance(session.get(QUEUE_KEY), list) else None,
            session.get(META_KEY) if isinstance(session.get(META_KEY), dict) else None)
    seen = {"session": _summary(*best)}
    for name, state in sources:
        cand = setlist_of(state)
        seen[name] = _summary(*cand)
        # Copies saved before stamps existed keep the old behaviour: the copy being restored
        # brings its setlist (a song added on another device arrives) - unless it is empty.
        legacy_sync = (
            name == "payload" and cand[0] and not (cand[1] or {}).get("saved_at")
            and not (best[1] or {}).get("saved_at") and _rank(*cand) == _rank(*best)
        )
        if better(cand, best) or legacy_sync:
            best, best_name = cand, name
    if best_name != "session":
        session[QUEUE_KEY] = copy.deepcopy(best[0])
        if best[1] is not None:
            session[META_KEY] = copy.deepcopy(best[1])
        else:
            session.pop(META_KEY, None)
    _trace(session, "restore_reconcile", winner=best_name, seen=seen)
    return best_name


# --------------------------------------------------------------------------- save status

def record_save_status(session: Any, *, ok: bool, cloud_enabled: bool, cloud_ok: bool, reason: str = "") -> dict:
    queue = session.get(QUEUE_KEY) if isinstance(session.get(QUEUE_KEY), list) else []
    if cloud_enabled:
        where = "cloud" if (ok and cloud_ok) else "not_saved_to_cloud"
    else:
        where = "server" if ok else "not_saved"
    status = {"where": where, "songs": len(queue), "reason": str(reason or ""), "at": now_stamp()}
    session[SAVE_STATUS_KEY] = status
    _trace(session, "save_status", **status)
    return status


def save_status_message(status: dict | None) -> tuple[str, str]:
    """(level, text) for the setlist panel. Levels: success / error / info."""
    if not isinstance(status, dict):
        return "", ""
    n = int(status.get("songs") or 0)
    songs = f"{n} song{'s' if n != 1 else ''}"
    where = status.get("where")
    if where == "cloud":
        return "success", f"Setlist saved to your account ({songs})."
    if where == "server":
        return "info", f"Setlist saved ({songs}). Cloud storage is not set up for this app, so it is kept on this server."
    reason = str(status.get("reason") or "")
    if reason == "stale_revision_conflict":
        why = "another tab or device saved your workspace more recently"
    elif reason:
        why = f"the save did not complete ({reason})"
    else:
        why = "the save could not be confirmed"
    return "error", (
        f"Your setlist was NOT saved to your account: {why}. It is still here on this page - "
        "press Retry saving setlist to try again."
    )
