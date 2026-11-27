"""Where bar 1 beat 1 sits inside a Composition recording, measured rather than assumed.

Composition records with ``st.audio_input``, which runs in the Streamlit document and knows
nothing about the chord transport playing in its own iframe. Pressing Play and pressing Record
are two human actions, and the gap between them - plus the browser's own start-up latency -
becomes the take's pre-roll. Nothing measures that gap, so the transcriber had to assume the
take began exactly with the count-in. When it did not, the assumption moved every note.

The shared recorder component (``mission_recorder.RECORDER_COMPONENT``, the same AudioWorklet
and single ``AudioContext`` Mission and Multitrack overdubs use) arms the microphone and starts
the backing on one clock, so musical zero is a difference of frame counters. This module turns
that measurement into the one number transcription needs, and - just as importantly - refuses
to produce a number when the measurement is absent.

Nothing here renders anything or touches Multitrack state: no slots, no mixer, no mute/solo, no
take bookkeeping. It reads a timing mapping and Composition's own section identity. The two
Multitrack functions it does reuse, ``normalize_timing`` and ``sync_state``, are pure functions
over a mapping, and they are imported lazily so this module stays importable without them.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

#: How a Composition take arrived. Only the first is on the recording clock; the others are
#: honest about having no measurement rather than quietly looking like one.
SOURCE_SHARED_CLOCK = "shared-clock"
SOURCE_BASIC_RECORDER = "basic-recorder"
SOURCE_UPLOAD = "upload"

#: Per-section, so one section's take can never be read as another's. Composition identifies
#: material by section id; Multitrack's slot keys are deliberately not reused.
TAKE_ID_PREFIX = "_composer_take_id_"
TAKE_TIMING_PREFIX = "_composer_take_timing_"


def take_id_key(section_id: str) -> str:
    return f"{TAKE_ID_PREFIX}{section_id}"


def take_timing_key(section_id: str) -> str:
    return f"{TAKE_TIMING_PREFIX}{section_id}"


def _f(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def normalize(timing: Mapping[str, Any] | None) -> dict[str, Any]:
    """The timing fields worth keeping with a take, as plain JSON-safe values."""
    try:
        from multitrack_live_recorder import normalize_timing

        return dict(normalize_timing(timing))
    except Exception:
        src = timing if isinstance(timing, Mapping) else {}
        return {k: src[k] for k in list(src)[:24]} if src else {}


def sync_status(timing: Mapping[str, Any] | None) -> dict[str, Any]:
    """``{synchronized, source, reason}`` for one take.

    The reason matters more than the flag: a take that is silently assumed to be aligned is
    worse than one the musician is told to line up by hand.
    """
    try:
        from multitrack_live_recorder import sync_state

        return dict(sync_state(timing))
    except Exception:
        return {
            "synchronized": False,
            "source": str((timing or {}).get("source") or ""),
            "reason": "the recording clock could not be read",
        }


def measured_music_offset_sec(timing: Mapping[str, Any] | None) -> float | None:
    """Seconds from the start of the take to bar 1 beat 1, or ``None`` if unmeasured.

    ``None`` is a real answer and must stay distinguishable from ``0.0``: zero means the take
    demonstrably begins on the downbeat, while ``None`` means nobody knows and the caller must
    not invent an offset.
    """
    if not isinstance(timing, Mapping) or not timing:
        return None
    if not bool(sync_status(timing).get("synchronized")):
        return None
    direct = _f(timing.get("music_offset_sec"))
    if direct is not None and direct >= 0:
        return direct
    frames = _f(timing.get("music_start_frame"))
    first = _f(timing.get("capture_first_frame")) or 0.0
    rate = _f(timing.get("sample_rate"))
    if frames is None or rate is None or rate <= 0:
        return None
    offset = (frames - first) / rate
    return offset if offset >= 0 else None


def count_in_sec_for_transcription(
    timing: Mapping[str, Any] | None,
    *,
    requested_sec: float = 0.0,
) -> dict[str, Any]:
    """What to pass as ``transcribe_hum_audio(count_in_sec=...)``, and why.

    Returns ``{"count_in_sec", "measured", "reason"}``. When the take was recorded on the shared
    clock the offset is the measurement. When it was not, this returns ``count_in_sec=None`` and
    a reason: the transcriber then applies its own evidence rule (remove a count-in only when the
    audio actually starts after one) instead of trusting a number nobody measured. The requested
    count-in is reported for display, never substituted for a measurement.
    """
    measured = measured_music_offset_sec(timing)
    if measured is not None:
        return {
            "count_in_sec": float(measured),
            "measured": True,
            "reason": "",
            "requested_sec": float(requested_sec or 0.0),
        }
    status = sync_status(timing)
    return {
        "count_in_sec": None,
        "measured": False,
        "reason": str(status.get("reason") or "this take was not recorded on the shared clock"),
        "requested_sec": float(requested_sec or 0.0),
    }


def accept_take(
    session_state: MutableMapping[str, Any],
    section_id: str,
    take: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a take the recorder has not already handed over for this section.

    The component re-sends its last take on ordinary reruns, so without this the same recording
    would be ingested again on every interaction. Keyed by section, so recording in one section
    never suppresses or overwrites another's take.
    """
    if not isinstance(take, Mapping):
        return None
    take_id = str(take.get("take_id") or "").strip()
    wav = take.get("wav")
    if not take_id or not isinstance(wav, (bytes, bytearray)) or not wav:
        return None
    seen_key = take_id_key(section_id)
    if session_state.get(seen_key) == take_id:
        return None
    session_state[seen_key] = take_id
    timing = normalize(take.get("timing"))
    session_state[take_timing_key(section_id)] = timing
    return {"take_id": take_id, "wav": bytes(wav), "timing": timing}


def stored_timing(session_state: Mapping[str, Any], section_id: str) -> dict[str, Any]:
    raw = session_state.get(take_timing_key(section_id))
    return dict(raw) if isinstance(raw, Mapping) else {}


def forget_take(session_state: MutableMapping[str, Any], section_id: str) -> None:
    """Drop one section's take identity and timing, so a re-record is ingested afresh."""
    session_state.pop(take_id_key(section_id), None)
    session_state.pop(take_timing_key(section_id), None)


def alignment_caption(timing: Mapping[str, Any] | None) -> str:
    """One line a musician can act on, never a reassuring guess."""
    status = sync_status(timing)
    if status.get("synchronized"):
        offset = measured_music_offset_sec(timing)
        if offset is None:
            return "Recorded in time with the chords."
        return f"Recorded in time with the chords — bar 1 lands {offset:.2f}s into the take."
    reason = str(status.get("reason") or "").strip()
    base = "This take's timing could not be measured, so it is not aligned to the chords"
    return f"{base} — {reason}." if reason else f"{base}."
