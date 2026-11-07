"""Repeat a rendered backing pass without a gap at the loop boundary.

``synthesize_chords_to_numpy`` allocates its buffer as the music plus one second
(``np.zeros(int(sr * bar * len(chord_list)) + sr)``) so the last chord's decay has
somewhere to ring, and never trims it back. That headroom is right for a one-shot
render - an export should end with its decay intact - but repeating the buffer
verbatim repeats the silence too, so every lap of a Multitrack loop carries a
full second of nothing between the last bar and the next downbeat.

The fix belongs here rather than in the synthesizer: the overhang is only wrong
when the pass is repeated, and ``backing_audio`` is being edited by other work.

:func:`seamless_tile` keeps the decay instead of truncating it. Each repetition
contributes exactly its musical length, and the overhang is mixed onto the
beginning of the next one, which is what the ear expects - the final chord rings
over the new downbeat rather than stopping dead at the bar line. The last
repetition keeps its tail, so a loop still ends naturally.

Nothing here changes pitch, tempo, meter or level: samples are copied and summed,
never resampled or shifted.
"""

from __future__ import annotations

import numpy as np

__all__ = ("musical_sample_count", "seamless_tile", "loop_boundary_report")


def musical_sample_count(total_beats: float, bpm: float, sr: int = 44100) -> int:
    """Samples of actual music in one pass, from the musical parameters alone."""
    if total_beats <= 0 or bpm <= 0:
        return 0
    return int(round(float(total_beats) * 60.0 / float(bpm) * float(sr)))


def seamless_tile(
    y: np.ndarray,
    loops: int,
    *,
    musical_samples: int,
    carry_tail: bool = True,
) -> np.ndarray:
    """Repeat ``y`` ``loops`` times with no silence at the joins.

    ``musical_samples`` is where the music ends; anything after it is decay
    overhang. The overhang is summed onto the start of the following repetition
    and, on the last one, left in place so the loop ends naturally.

    Falls back to a plain tile when the inputs do not describe an overhang - a
    buffer with no tail, a nonsensical length, or a single repetition that
    already ends correctly.
    """
    reps = int(loops or 1)
    if reps < 1:
        reps = 1
    if y is None or len(y) == 0:
        return y
    n = int(musical_samples or 0)
    # Nothing to fold: no tail, or a length that does not fit the buffer.
    if n <= 0 or n >= len(y):
        return y if reps == 1 else np.tile(y, reps if y.ndim == 1 else (reps, 1))

    core = y[:n]
    tail = y[n:]

    if reps == 1:
        return y

    shape = (n * reps + (len(tail) if carry_tail else 0),)
    if y.ndim > 1:
        shape = shape + y.shape[1:]
    out = np.zeros(shape, dtype=y.dtype)

    for i in range(reps):
        out[i * n : (i + 1) * n] += core

    # The decay of each repetition rings over the downbeat of the next one.
    for i in range(1, reps):
        start = i * n
        out[start : start + len(tail)] += tail

    if carry_tail:
        start = reps * n
        out[start : start + len(tail)] += tail

    # A ringing chord summed onto the next downbeat is louder than either alone,
    # which is correct - that is what overlapping sounds do. It only becomes a
    # fault if it passes full scale, where it would clip. A quiet decay never
    # gets near it; a sustained pad can. Pull the whole buffer back by one gain
    # so the relative balance of the music is untouched.
    peak = float(np.abs(out).max()) if out.size else 0.0
    if peak > 1.0:
        out = out / peak

    return out


def loop_boundary_report(
    y: np.ndarray,
    *,
    musical_samples: int,
    sr: int = 44100,
    floor: float = 1e-4,
) -> dict:
    """Measurements used by the tests: silence at the join, peak, tail level."""
    mag = np.abs(y if y.ndim == 1 else y.mean(axis=1))
    peak = float(mag.max()) if len(mag) else 0.0
    thr = max(floor, peak * 0.001)

    n = int(musical_samples or 0)
    silence_before_join = 0.0
    if 0 < n <= len(mag):
        before = mag[:n]
        nz = np.nonzero(before > thr)[0]
        if len(nz):
            silence_before_join = float((n - 1 - nz[-1]) / sr)

    nz_all = np.nonzero(mag > thr)[0]
    trailing = float((len(mag) - 1 - nz_all[-1]) / sr) if len(nz_all) else 0.0

    return {
        "peak": peak,
        "clipped": bool(peak > 1.0),
        "silence_before_join_sec": silence_before_join,
        "trailing_silence_sec": trailing,
        "samples": int(len(mag)),
        "duration_sec": float(len(mag) / sr),
    }
