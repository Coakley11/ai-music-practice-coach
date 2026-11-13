"""The one timing contract for a Multitrack layer's Align offset.

Issue 78 found the transport preview and the exported mix disagreeing about what a
negative Align means. The transport computed ``musicStart + Math.max(0, delay)``, so a
negative offset moved nothing at all and the layer stayed on bar 1. The export mixer did
``y = y[-ds:]``, which really did drop that much from the front. The same slider position
therefore produced two different performances, and the one the musician checked by ear in
the preview was not the one that got written to the file.

**The contract.** An Align offset ``d`` seconds says where the layer's first recorded
sample sits relative to musical bar 1 of the mix:

* ``d > 0`` - the take starts ``d`` seconds **after** bar 1. Nothing is lost: ``d``
  seconds of silence go in front of it.
* ``d == 0`` - the take's first sample **is** bar 1. This is the default and it stays the
  default.
* ``d < 0`` - the musician is saying the take begins ``|d|`` seconds too early, because
  it carries that much count-in or pre-roll. The aligned presentation therefore starts
  ``|d|`` seconds **into** the take, so that what lands on bar 1 is the audio that was
  played ``|d|`` seconds after the recording began.

A negative offset is the only case that drops audio, and it drops it only from the
*presentation*. ``resolve`` returns the offset to read from, never a shortened recording:
the stored take is handed to the mixer and to the browser unchanged, and returning the
Align slider to 0 brings the discarded head straight back. Nothing here writes to
``mt_tracks``.

Both surfaces consume the same two numbers:

* the transport calls ``AudioBufferSourceNode.start(musicStart + start_delay_sec,
  buffer_offset_sec)``, which is Web Audio's own way of beginning part-way into a buffer;
* the export mixer pads the front with ``start_delay_sec`` of zeros and begins reading at
  ``buffer_offset_sec``.

Those are two spellings of one rule, which is why they can now be tested against each
other rather than inspected separately.

Pure Python and numpy, no Streamlit, so the contract is unit-testable on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# A take shorter than its own negative offset would vanish entirely. Keep a floor so an
# over-dragged slider yields a very short layer rather than silence the musician cannot
# explain. One pulse at a slow tempo is comfortably under any musical offset.
MIN_AUDIBLE_SEC = 0.05


@dataclass(frozen=True)
class LayerSchedule:
    """Where one layer's audio goes, expressed the same way for both surfaces."""

    start_delay_sec: float
    """Seconds of silence in front of the layer, measured from musical bar 1."""

    buffer_offset_sec: float
    """Seconds to skip at the head of the stored take before it is heard."""

    @property
    def delay(self) -> float:
        """The Align offset this schedule came from."""
        return self.start_delay_sec - self.buffer_offset_sec


def resolve(delay: Any) -> LayerSchedule:
    """Turn an Align offset into the schedule both surfaces apply.

    A value that is not a number at all is treated as 0, which is the safe default: the
    layer lands on bar 1 and nothing is skipped.
    """
    try:
        d = float(delay)
    except (TypeError, ValueError):
        d = 0.0
    if d != d or d in (float("inf"), float("-inf")):  # NaN / infinity
        d = 0.0
    if d >= 0:
        return LayerSchedule(start_delay_sec=d, buffer_offset_sec=0.0)
    return LayerSchedule(start_delay_sec=0.0, buffer_offset_sec=-d)


def describe(delay: Any) -> str:
    """One plain sentence about what this offset does, for a caption or a warning."""
    sched = resolve(delay)
    if sched.buffer_offset_sec > 0:
        return (
            f"Starts {sched.buffer_offset_sec:.3g}s into the recording, so the first "
            f"{sched.buffer_offset_sec:.3g}s is not heard. The saved recording keeps it — "
            "set Align back to 0 to hear it again."
        )
    if sched.start_delay_sec > 0:
        return f"Starts {sched.start_delay_sec:.3g}s after bar 1. Nothing is left out."
    return "Starts on bar 1. The whole recording is heard."


def apply_to_samples(y: Any, delay: Any, sr: int) -> Any:
    """The mixer's half of the contract: pad the front, or skip into the take.

    ``y`` is never modified in place and is never written back anywhere; the caller
    receives a new array and the stored take is untouched.
    """
    import numpy as np

    samples = np.asarray(y)
    if samples.size == 0:
        return samples
    sched = resolve(delay)
    rate = int(sr) if sr else 44100
    if rate <= 0:
        rate = 44100

    skip = int(round(sched.buffer_offset_sec * rate))
    if skip > 0:
        floor = max(1, int(MIN_AUDIBLE_SEC * rate))
        if samples.size - skip < floor:
            # Dragged past the end of the take: keep the last sliver rather than nothing,
            # so the layer is still audible and the cause is obvious.
            skip = max(0, samples.size - floor)
        # A slice is a view onto the caller's buffer, and this function promises a new
        # array - a caller that wrote into the result would otherwise be writing into
        # the take it was told was untouched.
        samples = samples[skip:].copy()

    pad = int(round(sched.start_delay_sec * rate))
    if pad > 0:
        samples = np.concatenate([np.zeros(pad, dtype=samples.dtype), samples])
    elif samples is y or samples.base is not None:
        samples = np.array(samples, copy=True)
    return samples


def transport_payload(delay: Any) -> dict[str, float]:
    """The same schedule as plain numbers, for the transport component's track payload."""
    sched = resolve(delay)
    return {
        "startDelaySec": float(sched.start_delay_sec),
        "bufferOffsetSec": float(sched.buffer_offset_sec),
    }


__all__ = [
    "LayerSchedule",
    "MIN_AUDIBLE_SEC",
    "apply_to_samples",
    "describe",
    "resolve",
    "transport_payload",
]
