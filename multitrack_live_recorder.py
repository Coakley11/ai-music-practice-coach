"""Record a Multitrack layer on the same clock as its count-in and the layers it plays along with.

The old per-layer control was ``st.audio_input``, which runs in the Streamlit document and knows
nothing about the transport iframe. Recording an overdub therefore meant two separate human
actions - press Play, press Record - and the gap between them, plus browser start-up latency,
*became* the take's pre-roll. Nothing measured that gap, so no later alignment could undo it.

This renders the shared recorder component (``mission_recorder_component``, the same AudioWorklet
and the same single ``AudioContext`` the Mission recorder uses) with the whole monitor set for one
overdub: the generated backing as the primary asset, plus every saved layer the player should hear,
each at the position the shared Align contract gives it. One Record click arms the microphone,
counts the player in, and starts all of it on that one clock, so where musical zero sits inside the
take is a difference of frame counters.

Nothing here changes the Mission recorder's own behaviour: a request with one asset and no count-in
is the path Mission has always taken.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Mapping, MutableMapping, Sequence

from multitrack_align_contract import transport_payload

LAST_TAKE_ID_PREFIX = "_mt_live_take_id_"
TAKE_TIMING_KEY = "mt_take_timing"
# How a take arrived. Only the first of these is on the recording clock; the other two are honest
# about having no measurement rather than quietly looking like one.
SOURCE_SHARED_CLOCK = "shared-clock"
SOURCE_BASIC_RECORDER = "basic-recorder"
SOURCE_UPLOAD = "upload"
# A monitor the player can barely hear is worse than no monitor: it reads as a fault in the take.
MIN_MONITOR_VOLUME = 0.05


def monitor_fingerprint(data: bytes) -> str:
    """A stable short fingerprint for one monitor asset's bytes."""
    return hashlib.sha1(bytes(data)).hexdigest()[:16]


def _control(session_state: Mapping[str, Any], slot: str) -> dict[str, Any]:
    try:
        from multitrack_mixer_state import resolve_slot_control

        return dict(resolve_slot_control(session_state, slot))
    except Exception:
        return {
            "volume": float(session_state.get(f"mt_vol_{slot}", 1.0) or 1.0),
            "delay": float(session_state.get(f"mt_delay_{slot}", 0.0) or 0.0),
            "mute": bool(session_state.get(f"mt_mute_{slot}", False)),
            "solo": bool(session_state.get(f"mt_solo_{slot}", False)),
        }


def monitor_slots(
    session_state: Mapping[str, Any],
    *,
    recording_slot: str,
    slots: Sequence[str],
) -> list[str]:
    """Which saved layers the player should hear while overdubbing ``recording_slot``.

    The slot being recorded is never monitored against itself - that take is about to be replaced,
    and playing it back into the room would be heard as a double. Otherwise this follows the mixer
    the player can see: Solo narrows to the soloed layers, Mute removes a layer.
    """
    tracks = session_state.get("mt_tracks") or {}
    candidates = [s for s in slots if s != recording_slot and tracks.get(s)]
    controls = {s: _control(session_state, s) for s in candidates}
    soloed = [s for s in candidates if controls[s].get("solo")]
    chosen = soloed or [s for s in candidates if not controls[s].get("mute")]
    return chosen


def build_monitors(
    session_state: Mapping[str, Any],
    *,
    recording_slot: str,
    slots: Sequence[str],
    media_url: Any,
) -> list[dict[str, Any]]:
    """The saved layers to play along with, each at its shared-contract Align position.

    ``media_url(bytes, coordinates) -> str`` registers one asset for the browser to fetch.
    """
    tracks = session_state.get("mt_tracks") or {}
    out: list[dict[str, Any]] = []
    for slot in monitor_slots(session_state, recording_slot=recording_slot, slots=slots):
        data = tracks.get(slot)
        if not data:
            continue
        ctrl = _control(session_state, slot)
        fp = monitor_fingerprint(data)
        try:
            url = media_url(data, f"mtmonitor.{slot}.{fp}")
        except Exception:
            continue
        # The same Align rule the transport and the exported mix use, so the player hears each
        # layer where the mix will put it rather than where it happens to have been captured.
        schedule = transport_payload(ctrl.get("delay", 0.0))
        volume = float(ctrl.get("volume", 1.0) or 0.0)
        out.append(
            {
                "id": f"layer:{slot}",
                "fp": fp,
                "url": str(url),
                "start_delay_sec": float(schedule["startDelaySec"]),
                "buffer_offset_sec": float(schedule["bufferOffsetSec"]),
                "volume": max(MIN_MONITOR_VOLUME, min(1.5, volume)) if volume > 0 else MIN_MONITOR_VOLUME,
            }
        )
    return out


def take_filename(slot: str) -> str:
    """A filename for a live take that is safe to use as a storage path component.

    Slot labels contain spaces and slashes ("sax / winds"), and this name reaches durable storage
    through ``persist_track_audio``, so it is reduced to plain characters here rather than relied on
    to be harmless downstream.
    """
    safe = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in str(slot).strip().lower())
    while "--" in safe:
        safe = safe.replace("--", "-")
    safe = safe.strip("-") or "layer"
    return f"{safe[:60]}-take.wav"


def count_in_beats(*, bars: Any, beats_per_bar: Any) -> int:
    """Beats of click for a count-in of ``bars`` bars."""
    try:
        bars_i = max(0, int(bars))
        per_bar = max(1, int(beats_per_bar))
    except (TypeError, ValueError):
        return 0
    return bars_i * per_bar


def ready_text(*, beats: int, monitors: int, has_backing: bool) -> str:
    """What the recorder says it is about to do, in the player's terms."""
    parts: list[str] = []
    if beats > 0:
        parts.append(f"a {beats}-beat count-in")
    if has_backing:
        parts.append("the backing")
    if monitors == 1:
        parts.append("your other layer")
    elif monitors > 1:
        parts.append(f"your {monitors} other layers")
    if not parts:
        return "Record captures this layer on its own. Nothing else is playing."
    if len(parts) == 1:
        listed = parts[0]
    else:
        listed = ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"Record starts {listed} together with your take, on one clock."


def _f(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def normalize_timing(timing: Mapping[str, Any] | None) -> dict[str, Any]:
    """The timing fields worth keeping with a take, as plain JSON-safe values.

    Stored additively beside the take: no existing project, take, mixer or export contract reads
    these, and a take without them behaves exactly as takes always have.
    """
    src = timing if isinstance(timing, Mapping) else {}
    out: dict[str, Any] = {}
    for key in (
        "sample_rate",
        "count_in_sec",
        "count_in_offset_sec",
        "scheduled_count_in_offset_sec",
        "music_offset_sec",
        "scheduled_music_offset_sec",
        "backing_offset_sec",
        "scheduled_backing_offset_sec",
        "output_latency_sec",
        "input_latency_sec",
        "dry_duration_sec",
        "wall_sec",
    ):
        value = _f(src.get(key))
        if value is not None:
            out[key] = value
    for key in (
        "capture_first_frame",
        "music_start_frame",
        "count_in_start_frame",
        "backing_start_frame",
        "monitor_count",
        # What the recorder was ASKED to play along with. If fewer parts actually started, the
        # player did not hear what this take was aligned against, and the take is not trustworthy.
        "monitors_expected",
    ):
        value = _f(src.get(key))
        if value is not None:
            out[key] = int(value)
    for key in ("backing_fp", "request_fp", "device", "source", "unsynchronized_reason"):
        text = src.get(key)
        if text:
            out[key] = str(text)[:160]
    settings = src.get("settings")
    if isinstance(settings, Mapping):
        out["settings"] = {str(k): settings[k] for k in list(settings)[:12]}
    return out


def sync_state(timing: Mapping[str, Any] | None) -> dict[str, Any]:
    """Was this take measured on the recording clock? With the reason when it was not.

    A take is synchronized only when every part of the measurement needed to place bar 1 beat 1
    inside the audio is present AND every part the recorder was asked to play along with actually
    started. Anything else is reported as unsynchronized with a reason, because a take that is
    silently assumed to be aligned is worse than one the player knows to align by hand.
    """
    data = timing if isinstance(timing, Mapping) else {}
    source = str(data.get("source") or "")
    if not data:
        return {"synchronized": False, "source": source, "reason": "nothing was measured"}
    if source and source != SOURCE_SHARED_CLOCK:
        reason = str(data.get("unsynchronized_reason") or "")
        if not reason:
            reason = (
                "uploaded audio, not recorded here"
                if source == SOURCE_UPLOAD
                else "recorded with the compatibility recorder, which is not on the shared clock"
            )
        return {"synchronized": False, "source": source, "reason": reason}
    missing = [
        name
        for name in ("sample_rate", "capture_first_frame", "music_start_frame", "music_offset_sec")
        if _f(data.get(name)) is None
    ]
    if missing:
        return {
            "synchronized": False,
            "source": source or SOURCE_SHARED_CLOCK,
            "reason": "the recorder did not report " + ", ".join(missing),
        }
    if (_f(data.get("sample_rate")) or 0.0) <= 0:
        return {
            "synchronized": False,
            "source": source or SOURCE_SHARED_CLOCK,
            "reason": "the capture reported no sample rate",
        }
    if (_f(data.get("music_offset_sec")) or 0.0) < 0:
        return {
            "synchronized": False,
            "source": source or SOURCE_SHARED_CLOCK,
            "reason": "bar 1 beat 1 was measured before the recording started",
        }
    expected = _f(data.get("monitors_expected"))
    if expected is not None:
        started = _f(data.get("monitor_count")) or 0.0
        if int(started) != int(expected):
            return {
                "synchronized": False,
                "source": source or SOURCE_SHARED_CLOCK,
                "reason": (
                    f"{int(expected)} part(s) should have played along but {int(started)} did"
                ),
            }
    return {"synchronized": True, "source": source or SOURCE_SHARED_CLOCK, "reason": ""}


def record_take_timing(
    session_state: MutableMapping[str, Any],
    slot: str,
    timing: Mapping[str, Any] | None,
    *,
    source: str = SOURCE_SHARED_CLOCK,
) -> dict[str, Any]:
    """Keep this take's measured timing beside the take, with its verdict, for its own slot."""
    store = session_state.get(TAKE_TIMING_KEY)
    if not isinstance(store, dict):
        store = {}
        session_state[TAKE_TIMING_KEY] = store
    clean = normalize_timing(timing)
    clean["source"] = str(source or SOURCE_SHARED_CLOCK)
    verdict = sync_state(clean)
    clean["synchronized"] = bool(verdict["synchronized"])
    if not clean["synchronized"]:
        clean["unsynchronized_reason"] = verdict["reason"]
    store[slot] = clean
    return clean


def record_unsynchronized_take(
    session_state: MutableMapping[str, Any],
    slot: str,
    *,
    source: str,
    reason: str = "",
) -> dict[str, Any]:
    """Record that this slot's audio was NOT measured on the recording clock, and why.

    An upload and a compatibility-recorder take both have no measurement. Storing nothing would
    leave them indistinguishable from a take whose timing simply has not loaded yet, and would let
    the player believe the mix can place them. This states it instead.
    """
    return record_take_timing(
        session_state,
        slot,
        {"source": str(source), "unsynchronized_reason": str(reason or "")},
        source=str(source),
    )


def take_timing(session_state: Mapping[str, Any], slot: str) -> dict[str, Any]:
    """What was measured for the take currently in ``slot`` (empty for an older or uploaded take)."""
    store = session_state.get(TAKE_TIMING_KEY)
    if isinstance(store, Mapping) and isinstance(store.get(slot), Mapping):
        return dict(store[slot])
    return {}


def forget_take_timing(session_state: MutableMapping[str, Any], slot: str) -> None:
    """Drop the timing when its take is discarded, so it can never describe a different take."""
    store = session_state.get(TAKE_TIMING_KEY)
    if isinstance(store, dict):
        store.pop(slot, None)


def timing_caption(timing: Mapping[str, Any] | None) -> str:
    """One honest line about how this take was captured, or nothing to say."""
    data = timing if isinstance(timing, Mapping) else {}
    if not data:
        return ""
    verdict = sync_state(data)
    if not verdict["synchronized"]:
        source = verdict["source"]
        reason = verdict["reason"]
        if source == SOURCE_UPLOAD:
            return (
                "Uploaded audio - nothing was measured on the recording clock, so where bar 1 "
                "beat 1 sits in it is not known. Line it up with this layer's Align control."
            )
        if source == SOURCE_BASIC_RECORDER:
            return (
                "Recorded with the compatibility recorder, NOT on the shared clock: no count-in "
                "was played and bar 1 beat 1 was not measured, so this take has to be lined up by "
                "hand with the Align control."
            )
        return (
            "This take is NOT time-aligned: " + (reason or "its timing could not be measured")
            + ". Line it up with the Align control, or record it again."
        )
    bits: list[str] = []
    rate = _f(data.get("sample_rate"))
    if rate:
        bits.append(f"captured at {int(rate) / 1000:.1f} kHz")
    count_in = _f(data.get("count_in_sec")) or 0.0
    if count_in > 0:
        bits.append(f"{count_in:.1f} s count-in")
    music = _f(data.get("music_offset_sec"))
    if music is not None:
        bits.append(f"bar 1 beat 1 lands {music:.3f} s into the recording")
    monitors = _f(data.get("monitor_count")) or 0.0
    if monitors:
        bits.append(f"{int(monitors)} part(s) playing along")
    if not bits:
        return ""
    return "Measured on the recording clock: " + "; ".join(bits) + "."


def render_layer_recorder(
    st: Any,
    session_state: MutableMapping[str, Any],
    *,
    key: str,
    slot: str,
    slots: Sequence[str],
    backing_wav: bytes | None = None,
    backing_duration_sec: float = 0.0,
    count_in_bars: Any = 0,
    bpm: Any = 0,
    beats_per_bar: Any = 4,
    disabled_reason: str = "",
) -> dict[str, Any] | None:
    """Draw the shared-clock recorder for one layer; return a new take once per take.

    The return is ``{"take_id", "wav", "timing"}`` - the same shape the Mission recorder returns,
    so the take lands through the path takes have always landed through.
    """
    from mission_recorder import RECORDER_COMPONENT, backing_media_url

    beats = count_in_beats(bars=count_in_bars, beats_per_bar=beats_per_bar)
    monitors = build_monitors(
        session_state, recording_slot=slot, slots=slots, media_url=backing_media_url
    )
    args: dict[str, Any] = {
        "require_backing": False,
        "disabled": bool(disabled_reason),
        "disabled_reason": str(disabled_reason or ""),
        "backing_fp": "",
        "backing_url": "",
        "backing_duration_sec": 0.0,
        "monitors": monitors,
        "count_in_beats": int(beats),
        "count_in_bpm": float(_f(bpm) or 0.0),
        "count_in_beats_per_bar": int(max(1, int(_f(beats_per_bar) or 4))),
        "acked_instance": "",
    }
    try:
        from mission_music_capture import MUSIC_CAPTURE_CONSTRAINTS

        args["constraints"] = dict(MUSIC_CAPTURE_CONSTRAINTS)
    except Exception:
        args["constraints"] = {}
    if backing_wav:
        fp = monitor_fingerprint(backing_wav)
        try:
            args["backing_url"] = str(backing_media_url(backing_wav, f"mtbacking.{fp}"))
            args["backing_fp"] = fp
            args["backing_duration_sec"] = float(_f(backing_duration_sec) or 0.0)
        except Exception:
            args["backing_url"] = ""
            args["backing_fp"] = ""
    args["ready_text"] = ready_text(
        beats=int(beats), monitors=len(monitors), has_backing=bool(args["backing_fp"])
    )
    # Only a discarded take invalidates what the browser already decoded; an ordinary rerun must
    # not restart the loads, or Record would keep going unavailable under the player's hand.
    try:
        from multitrack_takes import take_nonce

        args["load_nonce"] = int(take_nonce(session_state, slot)) + 1
    except Exception:
        args["load_nonce"] = 1

    value = RECORDER_COMPONENT(key=key, default=None, **args)
    if not isinstance(value, dict) or not value.get("take_id") or not value.get("wav_b64"):
        return None
    last_key = f"{LAST_TAKE_ID_PREFIX}{slot}"
    if value["take_id"] == session_state.get(last_key):
        return None
    try:
        wav = base64.b64decode(value["wav_b64"])
    except Exception:
        return None
    if not wav:
        return None
    session_state[last_key] = str(value["take_id"])
    return {"take_id": str(value["take_id"]), "wav": wav, "timing": dict(value.get("timing") or {})}


__all__ = [
    "SOURCE_BASIC_RECORDER",
    "SOURCE_SHARED_CLOCK",
    "SOURCE_UPLOAD",
    "TAKE_TIMING_KEY",
    "build_monitors",
    "count_in_beats",
    "forget_take_timing",
    "monitor_fingerprint",
    "monitor_slots",
    "normalize_timing",
    "ready_text",
    "record_take_timing",
    "record_unsynchronized_take",
    "render_layer_recorder",
    "sync_state",
    "take_filename",
    "take_timing",
    "timing_caption",
]
