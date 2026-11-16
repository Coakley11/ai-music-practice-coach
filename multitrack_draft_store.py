"""Unsaved Multitrack takes kept as their own audio files, so a long take survives a session ending.

Measured: ``encode_mt_tracks_for_persist`` drops any take over ``MAX_MT_TRACK_BYTES`` (2 MiB) from
the persisted copy, and the recorder writes 16-bit stereo 44.1 kHz - so any take longer than about
12 seconds existed ONLY in the live session. A song-length layer (an 86 s backing is ~15 MB) was
never written anywhere, and a refresh, an idle disconnect or a Cloud restart destroyed it:

    3 s take   0.50 MiB   durable copy   survived a refresh
    30 s take  2.95 MiB   none           lost - found nowhere

The cap exists to keep the workspace JSON small, so it is not raised. Instead each unsaved take is
written here as a WAV file of its own, beside a small JSON sidecar, and never inside the workspace
state at all.

Save layer did not make a long take durable either
--------------------------------------------------
Measured: a 30 s take, Save layer pressed, then a refresh - found nowhere. Save layer flips a session
flag and runs the workspace save, and that save passes EVERY layer, saved or not, through the same
2 MiB cap. So this store does not delete a file when the musician saves: it marks it saved in the
sidecar, and a restore brings it back as a saved layer. Deleting it on save would have destroyed the
only copy that exists.

What a draft is, and what it is not
-----------------------------------
* A draft is **temporary**. On Streamlit Cloud this directory is on the app server's disk, which is
  replaced when the app restarts, sleeps or redeploys - so a draft survives a refresh or a dropped
  connection, and does NOT survive a restart. Only **Save layer** does. The interface says so; it
  never calls a draft saved, and never says "this device" about a file that lives on a server.
* A draft is **never a saved layer**. Restoring one puts the audio back in the working session and
  marks it UNSAVED explicitly, before ``adopt_restored_layers_as_saved`` runs - that function treats
  any audio with no recorded saved-state as a saved layer, and after a refresh there is no recorded
  state, so without this a restored draft would be silently promoted.

Isolation
---------
A draft belongs to one workspace, one song and one project. That identity is written into the
sidecar and checked on every read: a draft whose identity does not match the current session is not
returned, so one song, project or user can never receive another's. Paths are built only from
hashes of that identity and of the slot name - no title or slot text ever becomes a path component -
and every path goes through ``media_storage.workspace_contained_path``.

Discard stays discarded
-----------------------
Discarding deletes the files and leaves a small **tombstone** naming the discarded take's SHA-256.
A read refuses any draft whose hash is tombstoned, so even a file that failed to delete can never
come back. Writing a NEW take for that slot supersedes the tombstone, since it is different audio.

Integrity
---------
The take was decoded before it became a layer (``check_audio_bytes`` runs on every landed take). The
sidecar records the SHA-256 of exactly those bytes, and a read refuses a file that no longer matches
- a truncated or altered draft is not restored as though it were the take.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable, MutableMapping

DRAFT_REL_DIR = "media/multitrack/drafts"
#: Session flag set on a slot whose audio came back from a draft file, for the status line.
RESTORED_FLAG_PREFIX = "mt_draft_restored_"
#: Drafts nobody returned to are removed after this long, so the directory cannot grow forever.
DRAFT_RETENTION_SEC = 14 * 24 * 3600

_CONTROL_KEYS = ("mt_name_", "mt_vol_", "mt_delay_", "mt_mute_", "mt_solo_")


# ------------------------------------------------------------------------------------- identity
def _get(session: Any, key: str) -> Any:
    try:
        return session.get(key)
    except Exception:
        return None


def draft_identity(session: Any) -> dict[str, str]:
    """Which workspace, song and project a draft belongs to.

    The same three sources ``multitrack_take_removal.position_context`` uses, minus playback scope:
    switching between "full song" and one section must not hide a take the musician recorded.
    """
    project = str(_get(session, "multitrack_catalog_active_id")
                  or _get(session, "_last_catalog_multitrack_id") or "").strip()
    if not project:
        try:
            from multitrack_take_removal import working_project_token

            project = "new:" + working_project_token(session)
        except Exception:
            project = "new"
    return {
        "workspace": str(_get(session, "_suite_active_workspace_id") or ""),
        "song_pick": str(_get(session, "active_catalog_pick_key") or ""),
        "song_title": str(_get(session, "active_song_title") or ""),
        "project": project,
    }


def _digest(text: str, n: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def _identity_key(identity: dict[str, str]) -> str:
    return _digest(json.dumps(identity, sort_keys=True), 20)


def _workspace_id(st: Any = None) -> str:
    try:
        from media_storage import _resolve_workspace_id

        return str(_resolve_workspace_id(st=st) or "daniel")
    except Exception:
        return "daniel"


def _paths(session: Any, slot: str, *, st: Any = None) -> tuple[Path, Path, Path] | None:
    """(audio, sidecar, tombstone) for this slot of this session's project - or None if unsafe."""
    try:
        from media_storage import workspace_contained_path
    except ImportError:
        return None
    rel = f"{DRAFT_REL_DIR}/{_identity_key(draft_identity(session))}/{_digest(str(slot), 16)}"
    ws = _workspace_id(st)
    out = []
    for suffix in (".wav", ".json", ".tombstone"):
        p = workspace_contained_path(ws, rel + suffix)
        if p is None:
            return None
        out.append(p)
    return out[0], out[1], out[2]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------- write
def write_draft(session: MutableMapping[str, Any], slot: str, data: bytes, *,
                source: str = "", st: Any = None) -> dict[str, Any]:
    """Keep this unsaved take on disk. Returns ``{ok, bytes, sha, error}``."""
    raw = bytes(data or b"")
    if not raw:
        return {"ok": False, "error": "no audio"}
    paths = _paths(session, slot, st=st)
    if paths is None:
        return {"ok": False, "error": "no safe location for the draft"}
    wav_path, meta_path, tomb_path = paths
    sha = _sha(raw)
    controls = {}
    for prefix in _CONTROL_KEYS:
        value = _get(session, f"{prefix}{slot}")
        if value is not None:
            controls[prefix] = value
    timing = None
    try:
        store = _get(session, "mt_take_timing")
        if isinstance(store, dict):
            timing = store.get(slot)
    except Exception:
        timing = None
    meta = {
        "identity": draft_identity(session),
        "slot": str(slot),
        "sha256": sha,
        "bytes": len(raw),
        "source": str(source or ""),
        "filename": str((_get(session, "mt_track_filenames") or {}).get(slot) or ""),
        "controls": controls,
        "timing": timing,
        "written_at": time.time(),
        "saved": False,
    }
    try:
        _write_atomic(wav_path, raw)
        _write_atomic(meta_path, json.dumps(meta, default=str).encode("utf-8"))
        # A new take supersedes the tombstone of an older one in this slot.
        try:
            tomb_path.unlink(missing_ok=True)
        except Exception:
            pass
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    _sweep_old_drafts(st=st)
    return {"ok": True, "bytes": len(raw), "sha": sha[:12], "error": ""}


# ------------------------------------------------------------------------------------- read
def read_draft(session: Any, slot: str, *, st: Any = None) -> tuple[bytes | None, dict | None, str]:
    """``(audio, sidecar, why_not)``. Audio only if it is this session's, intact and not discarded."""
    paths = _paths(session, slot, st=st)
    if paths is None:
        return None, None, "no safe location"
    wav_path, meta_path, tomb_path = paths
    if not wav_path.exists() or not meta_path.exists():
        return None, None, "no draft"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None, "unreadable sidecar"
    if meta.get("identity") != draft_identity(session) or str(meta.get("slot")) != str(slot):
        return None, None, "belongs to a different song, project or user"
    try:
        raw = wav_path.read_bytes()
    except Exception:
        return None, None, "unreadable audio"
    sha = _sha(raw)
    if sha != meta.get("sha256"):
        return None, None, "the file no longer matches the recorded take"
    if tomb_path.exists():
        try:
            if tomb_path.read_text(encoding="utf-8").strip() == sha:
                return None, None, "this take was discarded"
        except Exception:
            return None, None, "this take was discarded"
    return raw, meta, ""


# ------------------------------------------------------------------------------------- remove
def _remove(paths: tuple[Path, Path, Path], *, tombstone: str = "") -> bool:
    wav_path, meta_path, tomb_path = paths
    removed = False
    for p in (wav_path, meta_path):
        try:
            if p.exists():
                p.unlink()
                removed = True
        except Exception:
            pass
    if tombstone:
        try:
            tomb_path.parent.mkdir(parents=True, exist_ok=True)
            tomb_path.write_text(tombstone, encoding="utf-8")
        except Exception:
            pass
    return removed


def discard_draft(session: Any, slot: str, *, st: Any = None) -> bool:
    """The musician threw this take away: delete it, and make sure it can never come back."""
    paths = _paths(session, slot, st=st)
    if paths is None:
        return False
    sha = ""
    try:
        meta = json.loads(paths[1].read_text(encoding="utf-8"))
        sha = str(meta.get("sha256") or "")
    except Exception:
        try:
            sha = _sha(paths[0].read_bytes())
        except Exception:
            sha = ""
    return _remove(paths, tombstone=sha)


def mark_draft_saved(session: Any, slot: str, *, st: Any = None) -> bool:
    """Save layer was pressed: the file becomes this layer's kept copy rather than a draft.

    NOT deleted. Save layer runs the workspace save, which drops any layer over 2 MiB, so for a
    song-length take this file is the only copy that survives the session ending.
    """
    paths = _paths(session, slot, st=st)
    if paths is None or not paths[1].exists():
        return False
    try:
        meta = json.loads(paths[1].read_text(encoding="utf-8"))
        meta["saved"] = True
        meta["saved_at"] = time.time()
        _write_atomic(paths[1], json.dumps(meta, default=str).encode("utf-8"))
        return True
    except Exception:
        return False


# ------------------------------------------------------------------------------------- restore
def restore_drafts(session: MutableMapping[str, Any], slots: Iterable[str], *,
                   st: Any = None) -> list[str]:
    """Put back any unsaved take this session has lost but its draft file still holds.

    Only fills a slot whose live audio is gone - a take still in the session always wins - and marks
    what it restores UNSAVED, before anything can adopt it as a saved layer.
    """
    tracks = _get(session, "mt_tracks")
    if not isinstance(tracks, dict):
        return []
    restored = []
    for slot in slots or ():
        if tracks.get(slot):
            continue
        raw, meta, _why = read_draft(session, slot, st=st)
        if raw is None or meta is None:
            continue
        tracks[slot] = raw
        saved = bool(meta.get("saved"))
        try:
            from multitrack_takes import mark_take_saved, mark_take_unsaved

            (mark_take_saved if saved else mark_take_unsaved)(session, slot)
        except Exception:
            session[f"mt_take_saved_{slot}"] = saved
        names = _get(session, "mt_track_filenames")
        if isinstance(names, dict) and meta.get("filename"):
            names[slot] = meta["filename"]
        for prefix, value in (meta.get("controls") or {}).items():
            if f"{prefix}{slot}" not in session:
                session[f"{prefix}{slot}"] = value
        if meta.get("timing") is not None:
            store = _get(session, "mt_take_timing")
            if not isinstance(store, dict):
                store = {}
                session["mt_take_timing"] = store
            store.setdefault(slot, meta["timing"])
        session[f"{RESTORED_FLAG_PREFIX}{slot}"] = True
        restored.append(str(slot))
    return restored


def was_restored(session: Any, slot: str) -> bool:
    return bool(_get(session, f"{RESTORED_FLAG_PREFIX}{slot}"))


# ------------------------------------------------------------------------------------- retention
def _sweep_old_drafts(*, st: Any = None) -> None:
    """Remove drafts nobody came back to, so this directory cannot grow without bound."""
    try:
        from media_storage import workspace_contained_path

        root = workspace_contained_path(_workspace_id(st), DRAFT_REL_DIR)
    except Exception:
        return
    if root is None or not root.exists():
        return
    cutoff = time.time() - DRAFT_RETENTION_SEC
    for p in root.rglob("*"):
        try:
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink()
        except Exception:
            continue


__all__ = [
    "DRAFT_REL_DIR",
    "DRAFT_RETENTION_SEC",
    "RESTORED_FLAG_PREFIX",
    "mark_draft_saved",
    "discard_draft",
    "draft_identity",
    "read_draft",
    "restore_drafts",
    "was_restored",
    "write_draft",
]
