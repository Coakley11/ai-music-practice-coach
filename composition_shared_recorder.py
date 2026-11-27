"""Composition's own view of the shared-clock recorder, behind a flag that defaults to off.

``st.audio_input`` remains the default and the fallback. This module adds a second route
that renders ``mission_recorder.RECORDER_COMPONENT`` - the same AudioWorklet and the same
single ``AudioContext`` Mission and Multitrack overdubs use - so the microphone and the
section's chord backing start on one clock and bar 1 beat 1 is a frame counter rather than
an assumption. Nothing here switches the page over; that waits on browser acceptance.

What this module deliberately does NOT do:

* It does not touch Multitrack. No slots, no mixer, no mute/solo, no take bookkeeping, and
  none of ``multitrack_draft_store``'s sidecar controls. The only Multitrack code it reuses
  is ``count_in_beats`` and, through ``composition_recording_timing``, the pure mapping
  functions ``normalize_timing`` and ``sync_state``.
* It does not accept, replace or activate a melody. A take that arrives is audio plus
  timing, nothing more: the musician still presses Analyze and then Use this melody. A new
  recording landing must never overwrite a melody somebody already accepted.
* It does not guess an offset. When the recorder reports no usable measurement the take is
  labelled unsynchronized, with the reason, and transcription falls back to its own
  evidence rule rather than trusting a number nobody measured.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import wave
from typing import Any, Callable, Mapping, MutableMapping

from composition_recording_timing import (
    SOURCE_BASIC_RECORDER,
    SOURCE_SHARED_CLOCK,
    accept_take,
    alignment_caption,
    forget_take,
    stored_timing,
    sync_status,
)

#: Off unless a session explicitly turns it on, or the environment does for a test run.
FLAG_SESSION_KEY = "composer_shared_recorder_enabled"
FLAG_ENV = "COMPOSITION_SHARED_RECORDER"

#: Composition-owned, and scoped to document AND section: a take belongs to one section of
#: one song, and switching either must not surface the other's recording.
AUDIO_PREFIX = "_composer_take_audio_"
NONCE_PREFIX = "_composer_recorder_nonce_"
#: The chord accompaniment prepared for one section's recorder, with the fingerprint of the
#: settings it was built from. Kept separate from the Play-chords preview cache, which is
#: keyed by section alone and records no fingerprint - so it cannot be shown to match.
BACKING_PREFIX = "_composer_rec_backing_"

_TRUE = {"1", "true", "yes", "on"}


def shared_recorder_enabled(session: Mapping[str, Any] | None = None) -> bool:
    """False unless deliberately enabled. The old recorder stays the default route."""
    if isinstance(session, Mapping) and session.get(FLAG_SESSION_KEY) is not None:
        return bool(session.get(FLAG_SESSION_KEY))
    return str(os.environ.get(FLAG_ENV, "")).strip().lower() in _TRUE


def recording_scope(document_id: Any, section_id: Any) -> str:
    """One take's owner: this section of this document.

    A bare section id is not enough. Section ids are only unique within a document, so two
    songs with a section called the same thing would otherwise read each other's take.
    """
    doc = str(document_id or "").strip() or "unsaved"
    sec = str(section_id or "").strip() or "section"
    return f"{doc}:{sec}"


def audio_key(scope: str) -> str:
    return f"{AUDIO_PREFIX}{scope}"


def nonce_key(scope: str) -> str:
    return f"{NONCE_PREFIX}{scope}"


def recorder_load_nonce(session: Mapping[str, Any] | None, scope: str) -> int:
    """Stable across ordinary reruns; changes only when a take is discarded.

    The component reloads its assets when this changes, and a reload makes Record briefly
    unavailable. Bumping it on every rerun would take the control out from under the
    musician's hand mid-performance, so a rerun must read the same number back.
    """
    try:
        raw = (session or {}).get(nonce_key(scope))
        return int(raw) if raw is not None else 1
    except (TypeError, ValueError):
        return 1


def discard_recording(session: MutableMapping[str, Any], scope: str) -> None:
    """Forget this section's take and let the component load afresh."""
    session[nonce_key(scope)] = recorder_load_nonce(session, scope) + 1
    session.pop(audio_key(scope), None)
    forget_take(session, scope)


def backing_key(scope: str) -> str:
    return f"{BACKING_PREFIX}{scope}"


def accompaniment_fingerprint(
    *,
    scope: str,
    chords: Any,
    bpm: Any,
    meter: Any,
    key: Any,
    count_in_bars: Any,
) -> str:
    """Identity of one accompaniment render: everything that changes the audio.

    The scope is part of it, so one song's cached chords can never be served to another
    even if two sections happen to agree on every musical setting.
    """
    payload = json.dumps(
        {
            "scope": str(scope or ""),
            "chords": [str(c) for c in list(chords or [])],
            "bpm": str(bpm or ""),
            "meter": str(meter or ""),
            "key": str(key or ""),
            "count_in_bars": str(count_in_bars or 0),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _wav_duration_sec(data: bytes) -> float:
    """Length from the WAV header - no decoder, no guess from BPM."""
    try:
        with wave.open(io.BytesIO(bytes(data)), "rb") as handle:
            rate = int(handle.getframerate() or 0)
            if rate <= 0:
                return 0.0
            return round(handle.getnframes() / rate, 4)
    except Exception:
        return 0.0


def prepare_accompaniment(
    session: MutableMapping[str, Any],
    scope: str,
    *,
    chords: Any,
    bpm: Any,
    meter: Any,
    key: Any,
    count_in_bars: Any,
    generate: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """The chord audio this section's recorder should play, built if it does not exist.

    Returns ``{wav, duration_sec, fingerprint, reused, error, has_chords}``. The musician
    never has to press Play chords first: a cold start generates the accompaniment here,
    from THIS section's chords, BPM, meter and key.

    A cached render is reused only when its fingerprint matches exactly. Anything else -
    edited chords, a different tempo or meter, a changed count-in, another section or
    another song - is a miss and is regenerated, because serving a stale or foreign
    accompaniment would have the musician record against chords they cannot hear.

    ``count_in_bars`` belongs to the fingerprint because it changes the rendered audio. It
    is NOT an alignment offset: where bar 1 beat 1 falls inside a take comes only from the
    recorder's measured timing, and nothing here reports or implies one.
    """
    rows = [str(c) for c in list(chords or []) if str(c).strip()]
    fingerprint = accompaniment_fingerprint(
        scope=scope, chords=rows, bpm=bpm, meter=meter, key=key, count_in_bars=count_in_bars
    )
    out: dict[str, Any] = {
        "wav": b"",
        "duration_sec": 0.0,
        "fingerprint": fingerprint,
        "reused": False,
        "error": "",
        "has_chords": bool(rows),
    }
    if not rows:
        # A section with no chords yet is not a failure: humming to the count-in alone is a
        # legitimate way to capture an idea, and require_backing is False for that reason.
        return out
    cached = session.get(backing_key(scope))
    if isinstance(cached, Mapping) and str(cached.get("fingerprint") or "") == fingerprint:
        data = cached.get("wav")
        if isinstance(data, (bytes, bytearray)) and data:
            out["wav"] = bytes(data)
            out["duration_sec"] = float(cached.get("duration_sec") or 0.0)
            out["reused"] = True
            return out
    if generate is None:
        out["error"] = "Chord accompaniment is unavailable on this server."
        return out
    try:
        wav = generate()
    except Exception:
        wav = None
    if not isinstance(wav, (bytes, bytearray)) or not wav:
        out["error"] = (
            "Could not build the chord accompaniment for this section. "
            "Check the section's chords and try again - recording now would be "
            "against chords you cannot hear."
        )
        return out
    out["wav"] = bytes(wav)
    out["duration_sec"] = _wav_duration_sec(out["wav"])
    session[backing_key(scope)] = {
        "fingerprint": fingerprint,
        "wav": out["wav"],
        "duration_sec": out["duration_sec"],
    }
    return out


def build_recorder_args(
    *,
    backing_url: str = "",
    backing_fp: str = "",
    backing_duration_sec: float = 0.0,
    bpm: Any = 0,
    beats_per_bar: Any = 4,
    count_in_bars: Any = 0,
    load_nonce: int = 1,
    disabled_reason: str = "",
    ready_text: str = "",
) -> dict[str, Any]:
    """The component's argument contract, built from Composition's own section settings.

    ``beats_per_bar`` is the meter's numerator, matching ``_beats_per_bar`` in
    composition_hum_transcription, so in a compound meter the count-in clicks at the same
    pulse Composition counts in. ``require_backing`` is False because a section may have no
    chords yet, and humming without chords must still record.
    """
    try:
        from multitrack_live_recorder import count_in_beats

        beats = int(count_in_beats(bars=count_in_bars, beats_per_bar=beats_per_bar))
    except Exception:
        try:
            beats = max(0, int(count_in_bars or 0)) * max(1, int(beats_per_bar or 4))
        except (TypeError, ValueError):
            beats = 0
    try:
        bpm_f = float(bpm or 0.0)
    except (TypeError, ValueError):
        bpm_f = 0.0
    try:
        bpb = max(1, int(beats_per_bar or 4))
    except (TypeError, ValueError):
        bpb = 4
    args: dict[str, Any] = {
        "require_backing": False,
        "disabled": bool(disabled_reason),
        "disabled_reason": str(disabled_reason or ""),
        "backing_url": str(backing_url or ""),
        "backing_fp": str(backing_fp or ""),
        "backing_duration_sec": float(backing_duration_sec or 0.0),
        # Composition overdubs nothing: the chords are the only thing to play along with.
        "monitors": [],
        "count_in_beats": int(beats),
        "count_in_bpm": bpm_f,
        "count_in_beats_per_bar": bpb,
        "acked_instance": "",
        "load_nonce": int(load_nonce),
        # What the idle readout says. Without it the component falls back to "Ready.", which
        # does not tell the player whether the chords will come in with their first note.
        "ready_text": str(ready_text or ""),
    }
    try:
        from mission_music_capture import MUSIC_CAPTURE_CONSTRAINTS

        # Music capture, not speech: echo cancellation, noise suppression and automatic gain
        # control all off. The old route applies none of these.
        args["constraints"] = dict(MUSIC_CAPTURE_CONSTRAINTS)
    except Exception:
        args["constraints"] = {}
    return args


def ingest_take(
    session: MutableMapping[str, Any],
    scope: str,
    take: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Store a newly arrived take as audio + timing. Never as a melody.

    Returns the take once, or None - on an ordinary rerun the component re-sends its last
    take and this must not look like a new one. The accepted melody, the proposal and the
    document are not touched: a recording arriving is not a decision to use it.
    """
    fresh = accept_take(session, scope, take)
    if not fresh:
        return None
    session[audio_key(scope)] = fresh["wav"]
    return fresh


def take_audio(session: Mapping[str, Any] | None, scope: str) -> bytes:
    raw = (session or {}).get(audio_key(scope))
    return bytes(raw) if isinstance(raw, (bytes, bytearray)) else b""


def take_source(session: Mapping[str, Any] | None, scope: str) -> str:
    """Which route this section's audio came from, for an honest status line."""
    timing = stored_timing(session or {}, scope)
    if not timing:
        return SOURCE_BASIC_RECORDER if take_audio(session, scope) else ""
    return str(timing.get("source") or SOURCE_SHARED_CLOCK)


def recording_status(session: Mapping[str, Any] | None, scope: str) -> dict[str, Any]:
    """``{synchronized, source, reason, caption}`` for whatever audio this section holds.

    A take from the old ``st.audio_input`` route has no timing at all, so it is reported
    unsynchronized with a reason rather than being quietly treated as aligned.
    """
    timing = stored_timing(session or {}, scope)
    status = dict(sync_status(timing or None))
    status["caption"] = alignment_caption(timing or None)
    status["has_audio"] = bool(take_audio(session, scope))
    if not timing and status["has_audio"]:
        status["source"] = SOURCE_BASIC_RECORDER
    return status


def render_shared_recorder(
    st: Any,
    session: MutableMapping[str, Any],
    *,
    scope: str,
    backing_wav: bytes | None = None,
    backing_duration_sec: float = 0.0,
    bpm: Any = 0,
    beats_per_bar: Any = 4,
    count_in_bars: Any = 0,
    disabled_reason: str = "",
    component: Callable[..., Any] | None = None,
    key: str | None = None,
    chords: Any = None,
    meter: Any = "4/4",
    section_key: Any = "C",
    generate_backing: Callable[[], Any] | None = None,
) -> dict[str, Any] | None:
    """Draw the shared recorder for one section; return a take the first time it arrives.

    ``component`` is injectable so the take lifecycle can be exercised without a browser.
    It defaults to the shared declared component, never a second declaration of it.
    """
    if component is None:
        try:
            from mission_recorder import RECORDER_COMPONENT

            component = RECORDER_COMPONENT
        except Exception:
            return None
    # Cold start: prepare this section's accompaniment rather than depending on whatever
    # the Play chords button happened to leave behind.
    if backing_wav is None and (chords or generate_backing is not None):
        prepared = prepare_accompaniment(
            session,
            scope,
            chords=chords,
            bpm=bpm,
            meter=meter,
            key=section_key,
            count_in_bars=count_in_bars,
            generate=generate_backing,
        )
        if prepared.get("error"):
            try:
                st.warning(str(prepared["error"]))
            except Exception:
                pass
            return None
        backing_wav = prepared.get("wav") or None
        backing_duration_sec = float(prepared.get("duration_sec") or 0.0)
    backing_url = ""
    backing_fp = ""
    if backing_wav:
        try:
            from mission_recorder import backing_media_url
            from multitrack_live_recorder import monitor_fingerprint

            backing_fp = str(monitor_fingerprint(bytes(backing_wav)))
            backing_url = str(backing_media_url(bytes(backing_wav), f"composerbacking.{backing_fp}"))
        except Exception:
            backing_url = ""
            backing_fp = ""
    if backing_url:
        ready_text = "Record starts your take and this section's chords together."
    elif chords:
        ready_text = "Record starts your take — the chords could not be loaded, so you will hear the count-in only."
    else:
        ready_text = "Record starts your take with the count-in only — this section has no chords yet."
    args = build_recorder_args(
        ready_text=ready_text,
        backing_url=backing_url,
        backing_fp=backing_fp,
        backing_duration_sec=backing_duration_sec,
        bpm=bpm,
        beats_per_bar=beats_per_bar,
        count_in_bars=count_in_bars,
        load_nonce=recorder_load_nonce(session, scope),
        disabled_reason=disabled_reason,
    )
    try:
        value = component(key=key or f"composer_shared_rec_{scope}", default=None, **args)
    except Exception:
        return None
    if not isinstance(value, Mapping):
        return None
    wav_b64 = value.get("wav_b64")
    take: dict[str, Any] = {
        "take_id": value.get("take_id"),
        "timing": value.get("timing") or {},
    }
    if isinstance(wav_b64, str) and wav_b64:
        import base64

        try:
            take["wav"] = base64.b64decode(wav_b64)
        except Exception:
            return None
    elif isinstance(value.get("wav"), (bytes, bytearray)):
        take["wav"] = bytes(value["wav"])
    else:
        return None
    return ingest_take(session, scope, take)
