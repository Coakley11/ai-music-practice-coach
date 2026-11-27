"""Unsaved-take state for Multitrack layers: record, listen, discard, record again.

A layer's audio is kept the moment it is recorded or uploaded, so the musician can hear it straight
away - but until they press *Save layer* it is only a **take**. A take can be thrown away in one click,
and the recorder widget is rebuilt (a new widget key) so the old take stops playing back and the next
attempt starts clean. Saved layers are not discarded by that control; they say "Delete layer" instead
and are only removed deliberately.

Pure state helpers (no Streamlit import) so the rules are unit-testable.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, MutableMapping

# The recorder module owns these names (a take's timing record is keyed by them); never respell them here.
from multitrack_live_recorder import SOURCE_BASIC_RECORDER, SOURCE_SHARED_CLOCK, SOURCE_UPLOAD

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


#: Input events already adopted (or superseded) for one slot. A Streamlit uploader and the fallback
#: recorder keep handing back their last value on every rerun, so "the widget holds a file" is not a
#: user action. Only an event this slot has not seen yet is.
CONSUMED_INPUTS_PREFIX = "_mt_consumed_inputs::"
_CONSUMED_CAP = 40


def input_event_id(obj: Any) -> str:
    """Identity of ONE upload or fallback recording.

    Streamlit gives every uploaded file (and every ``st.audio_input`` recording) its own ``file_id``:
    it stays the same across reruns and changes when the musician removes and adds the file again,
    so re-uploading the same file on purpose is a new event. Without one, the content stands in.
    """
    if obj is None:
        return ""
    fid = str(getattr(obj, "file_id", "") or "").strip()
    if fid:
        return f"fid:{fid}"
    try:
        data = bytes(obj.getvalue())
    except Exception:
        return ""
    if not data:
        return ""
    name = str(getattr(obj, "name", "") or "")
    return f"sha:{hashlib.sha256(data).hexdigest()[:32]}:{len(data)}:{name}"


def _consumed(session_state: MutableMapping[str, Any], slot: str) -> list[str]:
    raw = session_state.get(f"{CONSUMED_INPUTS_PREFIX}{slot}")
    return [str(x) for x in raw] if isinstance(raw, (list, tuple)) else []


def choose_landed_take(
    session_state: MutableMapping[str, Any],
    slot: str,
    *,
    live_take: Mapping[str, Any] | None = None,
    recorded: Any = None,
    uploaded: Any = None,
    live_name: str = "layer-take.wav",
) -> dict[str, Any] | None:
    """The take that lands on THIS run, or None. Reads nothing but this slot's inputs; writes nothing.

    * A take from the synchronized recorder always wins: the recorder returns it once, on the run it
      arrives, and whatever the uploader or fallback recorder still hold is older than it.
    * Otherwise the fallback recorder, then the uploader - but only an input EVENT this slot has not
      adopted yet. The old rule landed "recorded or uploaded" on every rerun, so one rerun after a new
      microphone take the uploader's earlier file overwrote it.

    The caller validates the bytes and, only if it adopts them, calls :func:`consume_landed_take`; a
    rejected input therefore stays the musician's latest action instead of being silently swallowed.
    """
    held = [(obj, src) for obj, src in ((recorded, SOURCE_BASIC_RECORDER), (uploaded, SOURCE_UPLOAD)) if obj is not None]
    held_ids = [i for i in (input_event_id(obj) for obj, _ in held) if i]
    if isinstance(live_take, Mapping) and live_take.get("wav"):
        return {
            "bytes": bytes(live_take["wav"]),
            "name": str(live_name or "layer-take.wav"),
            "source": SOURCE_SHARED_CLOCK,
            "event": f"live:{live_take.get('take_id') or ''}",
            "supersedes": held_ids,
        }
    seen = set(_consumed(session_state, slot))
    for obj, src in held:
        event = input_event_id(obj)
        if not event or event in seen:
            continue
        try:
            data = bytes(obj.getvalue())
        except Exception:
            continue
        return {
            "bytes": data,
            "name": str(getattr(obj, "name", "") or f"{slot}.wav"),
            "source": src,
            "event": event,
            # Adopting the fallback recording also retires an upload held at the same moment, and the
            # reverse: neither may come back later over the take that was chosen.
            "supersedes": [i for i in held_ids if i != event],
        }
    return None


def consume_landed_take(session_state: MutableMapping[str, Any], slot: str, choice: Mapping[str, Any] | None) -> None:
    """Record that this slot adopted ``choice``: its event, and every widget value it supersedes, never land again."""
    if not isinstance(choice, Mapping):
        return
    seen = _consumed(session_state, slot)
    for event in [str(choice.get("event") or "")] + [str(x) for x in choice.get("supersedes") or ()]:
        if event and not event.startswith("live:") and event not in seen:
            seen.append(event)
    session_state[f"{CONSUMED_INPUTS_PREFIX}{slot}"] = seen[-_CONSUMED_CAP:]


#: One message from the last Save layer press, shown on the next run (the press reruns the page).
LAYER_SAVE_FLASH_PREFIX = "_mt_layer_save_flash::"


def save_layer_take(session_state: MutableMapping[str, Any], slot: str, *, st: Any = None) -> dict[str, Any]:
    """Save layer: keep THIS slot's current audio. Success only once the kept copy reads back as it.

    The kept copy is this layer's file on the app's server (multitrack_draft_store) - a refresh brings
    it back, a restart of the app can lose it. The account copy is made by saving the project, so this
    never reports ``where="account"``. On any failure the take stays in the session untouched and is
    not marked saved.

    Returns ``{ok, where, error, bytes}``; ``where`` is ``server_only`` | ``session_only`` | ``none``.
    """
    tracks = session_state.get("mt_tracks")
    data = tracks.get(slot) if isinstance(tracks, dict) else None
    if not data:
        return {"ok": False, "where": "none", "error": "no_audio", "bytes": 0}
    try:
        data = bytes(data)
    except Exception:
        return {"ok": False, "where": "session_only", "error": "the recording could not be read", "bytes": 0}
    try:
        from multitrack_draft_store import mark_draft_saved, read_draft, write_draft
    except ImportError:
        return {"ok": False, "where": "session_only", "error": "the layer store is not available", "bytes": len(data)}
    fail = {"ok": False, "where": "session_only", "bytes": len(data)}
    try:
        kept, _meta, _why = read_draft(session_state, slot, st=st)
        if kept != data:
            # The file on disk is an older take (or none): the kept copy must be what the layer holds now.
            written = write_draft(session_state, slot, data, st=st)
            if not written.get("ok"):
                return {**fail, "error": str(written.get("error") or "the recording could not be written")}
        if not mark_draft_saved(session_state, slot, st=st):
            return {**fail, "error": "the kept copy could not be marked as saved"}
        kept, meta, why = read_draft(session_state, slot, st=st)
    except Exception as exc:
        return {**fail, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    if kept != data or not (meta or {}).get("saved"):
        return {**fail, "error": why or "the kept copy did not read back as this recording"}
    mark_take_saved(session_state, slot)
    return {"ok": True, "where": "server_only", "error": "", "bytes": len(data)}


def layer_save_message(result: Mapping[str, Any] | None, layer_name: str) -> tuple[str, str]:
    """(level, text) for a Save layer result. Never "success": a layer is not in the account until the project is."""
    name = str(layer_name or "This layer").strip() or "This layer"
    if not isinstance(result, Mapping):
        return ("warning", f"**{name}**: the save could not be confirmed. The recording is still here in this "
                           "session - press **Save layer** again.")
    if result.get("ok"):
        return ("warning", f"**{name}** is saved as a layer on this app's server, so it comes back after a refresh. "
                           "It is **not in your account** yet: a restart of the app can lose it. To keep it in "
                           "your account, save the project in **Project Library**.")
    if str(result.get("error") or "") == "no_audio":
        return ("warning", "Record or upload audio first.")
    return ("error", f"**{name}** could not be saved ({result.get('error') or 'unknown error'}). The recording is "
                     "still here in this session - nothing was deleted. Press **Save layer** again, or save the "
                     "project in **Project Library**.")


def set_layer_save_flash(session_state: MutableMapping[str, Any], slot: str, message: tuple[str, str]) -> None:
    session_state[f"{LAYER_SAVE_FLASH_PREFIX}{slot}"] = list(message)


def pop_layer_save_flash(session_state: MutableMapping[str, Any], slot: str) -> tuple[str, str] | None:
    raw = session_state.pop(f"{LAYER_SAVE_FLASH_PREFIX}{slot}", None)
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return str(raw[0]), str(raw[1])
    return None


AUTO_OPEN_DECIDED_KEY = "_mt_auto_open_decided"
AUTO_OPEN_SLOT_KEY = "_mt_auto_open_slot"


def auto_open_slot(session_state: MutableMapping[str, Any], slots: Any) -> str:
    """Which empty layer should start open, so the Record control is visible without a tap.

    Issue 78C. Every layer panel is collapsed while its slot is empty, which is exactly the state a
    musician is in before their first take - so the recorder sat behind a tap, and (before the
    component's height was fixed) was invisible even after it.

    Exactly ONE layer opens: the first slot with no audio. Opening all of them would make the phone
    page enormous, which is not an improvement.

    It stays open only while the project holds **no audio at all**. That is the case the complaint
    is about - arriving at an empty Multitrack page and finding no way to record - and in it the
    layer must stay open on every render, because Streamlit re-applies ``expanded`` on each rerun
    and anything less makes the control the musician was just given close itself. Once any layer
    holds a take, the musician is working and knows where the controls are, so this stops
    altogether rather than fighting their own collapses.
    """
    tracks = session_state.get("mt_tracks")
    tracks = tracks if isinstance(tracks, dict) else {}
    if any(tracks.get(slot) for slot in (slots or ())):
        session_state[AUTO_OPEN_DECIDED_KEY] = True
        session_state[AUTO_OPEN_SLOT_KEY] = ""
        return ""
    for slot in slots or ():
        if not tracks.get(slot):
            session_state[AUTO_OPEN_DECIDED_KEY] = True
            session_state[AUTO_OPEN_SLOT_KEY] = str(slot)
            return str(slot)
    session_state[AUTO_OPEN_SLOT_KEY] = ""
    return ""


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


#: Shown for a take too large for the workspace save. Measured: a 30 s take is dropped from it
#: whether or not Save layer was pressed, so its only copy is a file on the app's server, which a
#: restart replaces. Nothing here may say "saved for good" or "on this device" about that.
LONG_TAKE_NOTICE = (
    "Long recordings are kept as a temporary file on the app's server: they come back after a "
    "refresh or a dropped connection, but **a restart of the app can lose them, saved or not.** "
    "**Save layer** alone does not keep a long recording permanently - to keep it, save the project "
    "in **Project Library**."
)


def _take_is_long(session_state: MutableMapping[str, Any], slot: str) -> bool:
    tracks = session_state.get("mt_tracks")
    data = tracks.get(slot) if isinstance(tracks, dict) else None
    try:
        from multitrack_session_persistence import MAX_MT_TRACK_BYTES
    except ImportError:
        MAX_MT_TRACK_BYTES = 2_097_152
    try:
        return len(bytes(data)) > MAX_MT_TRACK_BYTES
    except Exception:
        return False


def take_status_line(session_state: MutableMapping[str, Any], slot: str) -> str:
    """One short line telling the musician whether what they hear is saved - and how far to trust it."""
    tracks = session_state.get("mt_tracks")
    if not (isinstance(tracks, dict) and tracks.get(slot)):
        return ""
    restored = bool(session_state.get(f"mt_draft_restored_{slot}"))
    long_take = _take_is_long(session_state, slot)
    if is_take_saved(session_state, slot):
        line = "Saved layer — it plays with the mix and exports."
    else:
        line = ("**Unsaved Draft — Temporary.** Press **Save layer** to keep this recording, or "
                "**Discard take** to record again.")
    if restored:
        line += " Brought back after the page reloaded."
    if long_take:
        line += " " + LONG_TAKE_NOTICE
    return line


__all__ = [
    "AUTO_OPEN_DECIDED_KEY",
    "AUTO_OPEN_SLOT_KEY",
    "TAKE_NONCE_PREFIX",
    "auto_open_slot",
    "adopt_restored_layers_as_saved",
    "CONSUMED_INPUTS_PREFIX",
    "choose_landed_take",
    "consume_landed_take",
    "input_event_id",
    "LAYER_SAVE_FLASH_PREFIX",
    "layer_save_message",
    "pop_layer_save_flash",
    "save_layer_take",
    "set_layer_save_flash",
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
