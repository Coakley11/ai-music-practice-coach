"""Unsaved-take state for Multitrack layers: record, listen, discard, record again.

A layer's audio is kept the moment it is recorded or uploaded, so the musician can hear it straight
away - but until they press *Save layer* it is only a **take**. A take can be thrown away in one click,
and the recorder widget is rebuilt (a new widget key) so the old take stops playing back and the next
attempt starts clean. Saved layers are not discarded by that control; they say "Delete layer" instead
and are only removed deliberately.

Pure state helpers (no Streamlit import) so the rules are unit-testable.
"""

from __future__ import annotations

from typing import Any, MutableMapping

TAKE_SAVED_PREFIX = "mt_take_saved_"
TAKE_NONCE_PREFIX = "mt_take_nonce_"


def _slot_key(prefix: str, slot: str) -> str:
    return f"{prefix}{slot}"


def take_nonce(session_state: MutableMapping[str, Any], slot: str) -> int:
    """Widget generation for this slot. Bumping it gives the recorder/uploader a fresh widget."""
    try:
        return int(session_state.get(_slot_key(TAKE_NONCE_PREFIX, slot)) or 0)
    except (TypeError, ValueError):
        return 0


def recorder_widget_key(session_state: MutableMapping[str, Any], slot: str, kind: str = "record") -> str:
    """Key for this slot's recorder / uploader widget, including the take generation."""
    n = take_nonce(session_state, slot)
    base = f"mt_{kind}_{slot}"
    return base if n == 0 else f"{base}__take{n}"


def is_take_saved(session_state: MutableMapping[str, Any], slot: str) -> bool:
    """True when this slot's audio has been deliberately saved (not just recorded)."""
    return bool(session_state.get(_slot_key(TAKE_SAVED_PREFIX, slot)))


def mark_take_unsaved(session_state: MutableMapping[str, Any], slot: str) -> None:
    """New audio arrived from the recorder or uploader: it is a take until Save layer is pressed."""
    session_state[_slot_key(TAKE_SAVED_PREFIX, slot)] = False


def mark_take_saved(session_state: MutableMapping[str, Any], slot: str) -> None:
    session_state[_slot_key(TAKE_SAVED_PREFIX, slot)] = True


def discard_take(session_state: MutableMapping[str, Any], slot: str) -> bool:
    """Throw away this slot's current audio and reset its recorder. True when something was removed.

    Only this slot is touched: other layers, the monitor backing, the mixed export and every saved
    project row are left exactly as they were.
    """
    tracks = session_state.get("mt_tracks")
    had = bool(isinstance(tracks, dict) and tracks.get(slot))
    if isinstance(tracks, dict):
        tracks[slot] = None
    names = session_state.get("mt_track_filenames")
    if isinstance(names, dict):
        names[slot] = f"{slot.replace(' ', '_').lower()}.wav"
    session_state[_slot_key(TAKE_SAVED_PREFIX, slot)] = False
    session_state[_slot_key(TAKE_NONCE_PREFIX, slot)] = take_nonce(session_state, slot) + 1
    # Drop the old widget values too, so the previous take cannot play back from the recorder.
    for kind in ("record", "upload"):
        session_state.pop(f"mt_{kind}_{slot}", None)
        for n in range(max(0, take_nonce(session_state, slot))):
            session_state.pop(f"mt_{kind}_{slot}__take{n}", None)
    return had


def adopt_restored_layers_as_saved(session_state: MutableMapping[str, Any], slots: Any) -> None:
    """Audio that came back from a saved project / cloud workspace is a SAVED layer, not a fresh take.

    Only fills in slots with no recorded answer yet, so a take the musician is still working on keeps
    its unsaved state across reruns.
    """
    tracks = session_state.get("mt_tracks")
    if not isinstance(tracks, dict):
        return
    for slot in slots or ():
        key = _slot_key(TAKE_SAVED_PREFIX, slot)
        if key not in session_state and tracks.get(slot):
            session_state[key] = True


def discard_button_label(session_state: MutableMapping[str, Any], slot: str) -> str:
    """"Discard take" while unsaved, "Delete layer" once it has been saved."""
    return "🗑 Delete layer" if is_take_saved(session_state, slot) else "🗑 Discard take"


def take_status_line(session_state: MutableMapping[str, Any], slot: str) -> str:
    """One short line telling the musician whether what they hear is saved."""
    tracks = session_state.get("mt_tracks")
    if not (isinstance(tracks, dict) and tracks.get(slot)):
        return ""
    if is_take_saved(session_state, slot):
        return "Saved layer — it plays with the mix and exports."
    return "Unsaved take — press **Save layer** to keep it, or **Discard take** to record again."


__all__ = [
    "TAKE_NONCE_PREFIX",
    "adopt_restored_layers_as_saved",
    "TAKE_SAVED_PREFIX",
    "discard_button_label",
    "discard_take",
    "is_take_saved",
    "mark_take_saved",
    "mark_take_unsaved",
    "recorder_widget_key",
    "take_nonce",
    "take_status_line",
]
