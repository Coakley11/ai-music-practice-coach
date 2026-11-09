"""Musician-grade microphone capture for Multitrack layers.

Two browser-side defaults damage recorded instruments before the app ever sees the audio,
and both apply to the Multitrack recorder today:

**Bandwidth.** ``st.audio_input`` defaults to ``sample_rate=16000``. 16 kHz is a speech rate:
everything above 8 kHz is gone at capture. A flute's fundamentals fit under that, but the
bright upper partials that make a high note sound like a flute do not, so high notes come
back dull, thin or seemingly "missing". Guitar pick attacks, cymbals and saxophone edge lose
their definition the same way. No later stage can restore a band that was never recorded,
and resampling 16 kHz up to the 44.1 kHz mix rate only interpolates the loss.

**Voice processing.** Chrome and Edge apply echo cancellation, noise suppression and
automatic gain control to a microphone by default. Noise suppression treats a held, steady
tone — a sustained flute or saxophone note — as background noise and pulls it down, which is
exactly the "sustained note fades out" symptom. AGC pumps the level between loud and quiet
phrases. ``mission_music_capture`` already solves this for the Mission recorder by adding
``echoCancellation / noiseSuppression / autoGainControl: false`` to that one ``getUserMedia``
call; its own docstring notes that Multitrack still keeps the browser defaults. This module
reuses that same script for the Multitrack mics rather than building a second mechanism.

Pure Python apart from the optional Streamlit handle, so the policy is unit-testable.
"""

from __future__ import annotations

from typing import Any, Iterable

# 48 kHz is the native rate of most browser audio pipelines, so asking for it avoids a
# browser-side resample as well as keeping the full instrument band. It is one of the rates
# st.audio_input accepts, and Streamlit's own documented "high quality audio" example.
MULTITRACK_CAPTURE_SAMPLE_RATE = 48000

# Rates st.audio_input accepts; anything else raises inside Streamlit.
ALLOWED_CAPTURE_SAMPLE_RATES: frozenset[int] = frozenset(
    {8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000}
)

# The speech default that band-limits a recorded instrument to 8 kHz.
SPEECH_DEFAULT_SAMPLE_RATE = 16000


def capture_sample_rate() -> int:
    """The sample rate every Multitrack layer should be captured at."""
    return MULTITRACK_CAPTURE_SAMPLE_RATE


def is_music_grade_sample_rate(rate: Any) -> bool:
    """True when a capture rate keeps a real instrument band (>= 44.1 kHz)."""
    try:
        value = int(rate)
    except (TypeError, ValueError):
        return False
    return value >= 44100


def nyquist_hz(rate: Any) -> float:
    """Highest frequency a capture at ``rate`` can represent at all."""
    try:
        return float(rate) / 2.0
    except (TypeError, ValueError):
        return 0.0


def widget_key_class_candidates(key: str) -> list[str]:
    """Every plausible ``st-key-*`` spelling for one widget key.

    A Multitrack recorder key carries its slot name verbatim ("mt_record_Sax / winds"), and
    the frontend rewrites characters that cannot appear in a CSS class. The exact rewrite is
    a frontend detail, so each plausible spelling is offered and the capture script matches
    whichever one the browser actually produced. Offering a spare spelling costs nothing —
    the script only ever compares it against a class that is already on the element.
    """
    raw = str(key or "").strip()
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            out.append(value)

    add(raw)
    add("".join(ch if (ch.isalnum() or ch in "_-") else "-" for ch in raw))
    add("".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in raw))
    add("".join(ch for ch in raw if ch.isalnum() or ch in "_-"))
    return out


def multitrack_mic_keys(
    session_state: dict[str, Any],
    slots: Iterable[str] | None = None,
) -> list[str]:
    """The recorder widget keys for every Multitrack layer slot, take generation included."""
    if slots is None:
        try:
            from multitrack_slots import MULTITRACK_SLOTS

            slots = list(MULTITRACK_SLOTS)
        except Exception:
            slots = []
    try:
        from multitrack_takes import recorder_widget_key
    except Exception:
        return []

    keys: list[str] = []
    for slot in slots:
        slot = str(slot or "").strip()
        if not slot:
            continue
        try:
            keys.append(recorder_widget_key(session_state, slot, "record"))
        except Exception:
            continue
    return keys


def multitrack_capture_class_keys(
    session_state: dict[str, Any],
    slots: Iterable[str] | None = None,
) -> list[str]:
    """Class-name candidates for all Multitrack mics, ready for the capture script."""
    out: list[str] = []
    seen: set[str] = set()
    for key in multitrack_mic_keys(session_state, slots):
        for candidate in widget_key_class_candidates(key):
            if candidate not in seen:
                seen.add(candidate)
                out.append(candidate)
    return out


def install_multitrack_music_capture(
    st: Any,
    session_state: dict[str, Any],
    slots: Iterable[str] | None = None,
) -> bool:
    """Disable voice DSP for the Multitrack mics, reusing the Mission capture script.

    Returns False (leaving browser defaults in place) when the script cannot be installed;
    recording itself is never blocked by this.
    """
    keys = multitrack_capture_class_keys(session_state, slots)
    if not keys:
        return False
    html = getattr(st, "html", None)
    if html is None:
        return False
    try:
        from mission_music_capture import music_capture_script

        html(music_capture_script(keys), unsafe_allow_javascript=True)
    except TypeError:
        return False  # Older Streamlit without script support: defaults remain.
    except Exception:
        return False
    return True


def capture_quality_findings(rate: Any) -> list[str]:
    """Plain statements about what a capture at ``rate`` can and cannot preserve."""
    findings: list[str] = []
    if not is_music_grade_sample_rate(rate):
        findings.append(
            f"Capture is band-limited to {nyquist_hz(rate):.0f} Hz — the upper partials "
            "that give high flute, saxophone and guitar notes their tone are not recorded."
        )
    try:
        if int(rate) == SPEECH_DEFAULT_SAMPLE_RATE:
            findings.append(
                "This is st.audio_input's speech default, not a deliberate music setting."
            )
    except (TypeError, ValueError):
        findings.append("Capture rate is unknown, so bandwidth cannot be confirmed.")
    return findings


__all__ = [
    "ALLOWED_CAPTURE_SAMPLE_RATES",
    "MULTITRACK_CAPTURE_SAMPLE_RATE",
    "SPEECH_DEFAULT_SAMPLE_RATE",
    "capture_quality_findings",
    "capture_sample_rate",
    "install_multitrack_music_capture",
    "is_music_grade_sample_rate",
    "multitrack_capture_class_keys",
    "multitrack_mic_keys",
    "nyquist_hz",
    "widget_key_class_candidates",
]
