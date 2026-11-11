"""Issue 64 slice 4: knowing what is at risk before anything replaces it.

Four different things get called "my recording", and only one of them is safe to throw
away without asking:

``WORK_NONE``              nothing recorded or prepared - switching costs nothing.
``WORK_UNSAVED_TAKE``      audio exists and has never been saved to any project.
``WORK_SAVED_PROJECT``     a saved project is open and matches what is on disk.
``WORK_LOADED_CHANGED``    a saved project is open and has been changed since.

The distinction matters because the app must not silently discard a take, and must not
carry it into an unrelated song either. A flute take recorded against *All the Things
You Are* is not part of *Eleanor Rigby* just because the musician navigated there.

**How "changed" is decided.** Not by instrumenting every widget - that would mean a new
flag beside every control and one missed call away from lying. Instead the saveable
content is fingerprinted, and anything differing from the stamp taken at the last save
or load is an unsaved change. A fingerprint cannot miss a change it was never told
about.

**What goes into it, and why not the whole WAV.** Hashing every byte of every layer on
every rerun would be the obvious answer and an expensive one. Length alone is the cheap
answer and a wrong one: two takes of the same length are indistinguishable, and a second
attempt at the same phrase is exactly that. So each slot contributes its length *and* a
hash of its first and last few kilobytes - constant work whatever the file size, and a
different performance differs in its samples well before the end. The take markers the
recorder already maintains (``take_nonce``, ``is_take_saved``) go in as well, so a
re-record that somehow produced byte-identical audio would still register.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

__all__ = [
    "WORK_LOADED_CHANGED",
    "WORK_NONE",
    "WORK_SAVED_PROJECT",
    "WORK_UNSAVED_TAKE",
    "WORK_STAMP_KEY",
    "classify_work",
    "describe_work",
    "mark_project_saved",
    "switch_guard",
    "work_fingerprint",
    "work_is_at_risk",
]

WORK_NONE = "none"
WORK_UNSAVED_TAKE = "unsaved_take"
WORK_SAVED_PROJECT = "saved_project"
WORK_LOADED_CHANGED = "loaded_with_changes"

#: Where the fingerprint of the last save or load is kept.
WORK_STAMP_KEY = "_mt_work_stamp"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _active_project_id(session_state: Mapping[str, Any]) -> str:
    for key in ("multitrack_catalog_active_id", "mt_hist_active_item",
                "_last_catalog_multitrack_id"):
        value = _text(session_state.get(key))
        if value:
            return value
    return ""


def _slot_names() -> list[str]:
    try:
        from multitrack_slots import MULTITRACK_SLOTS

        return list(MULTITRACK_SLOTS)
    except Exception:
        return []


#: How much of each end of a layer is hashed. Enough to cover a WAV header and a real
#: stretch of samples; small enough that the cost does not grow with the recording.
_SAMPLE_BYTES = 8192


def _audio_identity(audio: Any) -> str:
    """A cheap, stable identity for one layer's audio.

    Length plus a digest of both ends. Constant work regardless of how long the
    recording is, and two different performances of the same length differ somewhere in
    the first or last few kilobytes in any realistic case - whereas comparing lengths
    alone treats them as the same take.
    """
    if not isinstance(audio, (bytes, bytearray)):
        return "0"
    raw = bytes(audio)
    digest = hashlib.sha256()
    digest.update(raw[:_SAMPLE_BYTES])
    if len(raw) > _SAMPLE_BYTES:
        digest.update(raw[-_SAMPLE_BYTES:])
    return f"{len(raw)}:{digest.hexdigest()[:16]}"


def _take_markers(session_state: Mapping[str, Any], slot: str) -> str:
    """The recorder's own revision markers for this slot, when they are available."""
    try:
        from multitrack_takes import is_take_saved, take_nonce

        # Both read through .get only, so the live proxy can go straight in - copying
        # the session per slot would be pure waste on a path that runs every rerun.
        nonce = take_nonce(session_state, slot)
        return f"{nonce}:{int(bool(is_take_saved(session_state, slot)))}"
    except Exception:
        return ""


def work_fingerprint(session_state: Mapping[str, Any]) -> str:
    """A digest of everything a save would capture."""
    parts: list[str] = [_active_project_id(session_state)]
    tracks = session_state.get("mt_tracks")
    tracks = tracks if isinstance(tracks, Mapping) else {}
    for slot in _slot_names():
        parts.append(f"{slot}:{_audio_identity(tracks.get(slot))}")
        parts.append(f"{slot}:take:{_take_markers(session_state, slot)}")
        for control in ("vol", "delay", "mute", "solo"):
            parts.append(f"{slot}:{control}:{session_state.get(f'mt_{control}_{slot}')}")
        parts.append(f"{slot}:name:{_text(session_state.get(f'mt_name_{slot}'))}")
        parts.append(
            f"{slot}:inst:{_text(session_state.get(f'mt_layer_instrument_{slot}'))}")
    parts.append(f"mix:{_audio_identity(session_state.get('mixed_track_wav'))}")
    parts.append(f"backing:{_text(session_state.get('mt_backing_prepared_at'))}")
    parts.append(f"backing_ref:{_text(session_state.get('mt_backing_storage_ref'))}")
    parts.append(f"backing_scope:{_text(session_state.get('mt_backing_scope'))}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]


def _has_content(session_state: Mapping[str, Any]) -> bool:
    try:
        from media_multitrack_catalog import session_has_saveable_multitrack_content

        return bool(session_has_saveable_multitrack_content(dict(session_state)))
    except Exception:
        tracks = session_state.get("mt_tracks")
        if isinstance(tracks, Mapping):
            return any(isinstance(v, (bytes, bytearray)) and v for v in tracks.values())
        return False


def mark_project_saved(session_state: Any) -> str:
    """Record that what is in the session is now what is on disk.

    Called after a save and after a load - the two moments the working state and the
    stored project agree.
    """
    stamp = work_fingerprint(session_state)
    try:
        session_state[WORK_STAMP_KEY] = stamp
    except Exception:
        pass
    return stamp


def classify_work(session_state: Mapping[str, Any]) -> str:
    if not _has_content(session_state):
        return WORK_NONE
    if not _active_project_id(session_state):
        return WORK_UNSAVED_TAKE
    stamp = _text(session_state.get(WORK_STAMP_KEY))
    if stamp and stamp == work_fingerprint(session_state):
        return WORK_SAVED_PROJECT
    # No stamp means this session never saw the save or load that produced the project,
    # so it cannot claim the content matches. Treat it as changed and ask.
    return WORK_LOADED_CHANGED


def work_is_at_risk(session_state: Mapping[str, Any]) -> bool:
    """True when replacing the working project would lose something not on disk."""
    return classify_work(session_state) in (WORK_UNSAVED_TAKE, WORK_LOADED_CHANGED)


def describe_work(session_state: Mapping[str, Any]) -> dict[str, Any]:
    """What is at risk, in words, with the choices that make sense for it."""
    state = classify_work(session_state)
    project = _active_project_id(session_state)
    if state == WORK_NONE:
        return {"state": state, "at_risk": False, "message": "", "choices": []}
    if state == WORK_UNSAVED_TAKE:
        return {
            "state": state,
            "at_risk": True,
            "message": (
                "This recording has never been saved. Opening another project or song "
                "would discard it."
            ),
            "choices": ["Save as New Project", "Continue Editing", "Discard", "Cancel"],
            "project_id": "",
        }
    if state == WORK_LOADED_CHANGED:
        return {
            "state": state,
            "at_risk": True,
            "message": (
                "This project has changes that are not saved yet. Opening another "
                "project or song would lose them."
            ),
            "choices": ["Save Changes", "Save as New Project", "Continue Editing",
                        "Discard", "Cancel"],
            "project_id": project,
        }
    return {
        "state": state,
        "at_risk": False,
        "message": "This project is saved.",
        "choices": [],
        "project_id": project,
    }


def switch_guard(
    session_state: Mapping[str, Any],
    *,
    reason: str = "",
    target: str = "",
) -> dict[str, Any]:
    """Whether an action that replaces the working project may proceed unasked.

    ``allowed`` is only ever true when nothing would be lost. The caller must not
    treat a guard it did not run as permission - a silent replace is the failure this
    exists to prevent.
    """
    described = describe_work(session_state)
    return {
        **described,
        "allowed": not described["at_risk"],
        "reason": _text(reason),
        "target": _text(target),
    }
