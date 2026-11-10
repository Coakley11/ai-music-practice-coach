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

__all__ = (
    "musical_sample_count",
    "pass_sample_count",
    "seamless_tile",
    "loop_boundary_report",
    "tile_pass",
)


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


def _last_audible_sample(y: np.ndarray, floor: float = 1e-4) -> int:
    """Index just past the last sample above the audibility floor."""
    mag = np.abs(y if y.ndim == 1 else y.mean(axis=1))
    peak = float(mag.max()) if len(mag) else 0.0
    if peak <= 0.0:
        return 0
    thr = max(floor, peak * 1e-5)
    nz = np.nonzero(mag > thr)[0]
    return int(nz[-1]) + 1 if len(nz) else 0


def _join_gap_seconds(y: np.ndarray, period: int, reps: int, sr: int, floor: float) -> float:
    """Worst silence immediately before any loop join in a finished buffer.

    The threshold is the same absolute audibility floor ``_last_audible_sample``
    trims at, deliberately not a fraction of the peak: a chord's decay tail sits
    around -60 dBFS while the groove peaks near full scale, so a peak-relative
    threshold would score a perfectly good quiet decay as silence and report a
    gap that nobody can hear.
    """
    if period <= 0 or reps < 2:
        return 0.0
    mag = np.abs(y if y.ndim == 1 else y.mean(axis=1))
    thr = float(floor)
    worst = 0.0
    for i in range(1, reps):
        join = i * period
        if join > len(mag):
            break
        before = mag[:join]
        nz = np.nonzero(before > thr)[0]
        if len(nz):
            worst = max(worst, float((join - 1 - nz[-1]) / sr))
    return worst


def pass_sample_count(n_events: int, bpm: float, time_signature: str = "4/4", sr: int = 44100) -> int:
    """Samples of music in one rendered pass.

    This mirrors what the renderer actually does, which is not the same as the
    progression's beat count: ``synthesize_chords_to_numpy`` allocates
    ``sr * bar * len(chord_list)``, giving every chord event one whole bar
    whatever its ``beats`` value. A progression with split measures therefore
    occupies more audio than its beats imply, and ``layer_chord_timeline``
    agrees - it places cell ``i`` at ``i * bar_duration``. Deriving the length
    from beats instead would fold real music onto the next downbeat.
    """
    count = int(n_events or 0)
    if count <= 0 or not bpm or float(bpm) <= 0:
        return 0
    from songs.meter import meter_timing

    timing = meter_timing(int(round(float(bpm))), time_signature or "4/4")
    return int(round(float(timing.bar_sec) * count * float(sr)))


def tile_pass(
    y: np.ndarray,
    loops: int,
    *,
    musical_samples: int,
    sr: int = 44100,
    max_gap_sec: float = 0.25,
    max_overhang_sec: float = 1.25,
) -> tuple:
    """Repeat one rendered pass for ``loops`` laps, and say what it did.

    Returns ``(audio, diag)``. ``diag["ok"]`` is False whenever the result still
    carries an audible gap at a join, so a failure is reported rather than
    quietly shipping the fault this function exists to remove.

    Strategies, in order of preference:

    ``overlap_add``   the musical length is known and plausible: fold each
                      pass's decay onto the next downbeat (musically correct).
    ``trim_silence``  the musical length is unusable or implausible, so fall
                      back on the signal itself and drop only trailing samples
                      below the audibility floor. Gapless by construction -
                      silence cannot be audible decay - but the ring-over is
                      lost, and it can never cut into real music.
    ``plain_tile``    nothing else worked. Reported as not ok.
    """
    reps = int(loops or 1)
    diag = {"strategy": "single", "ok": True, "gap_sec": 0.0, "loops": reps, "detail": ""}
    if y is None or len(y) == 0 or reps < 2:
        return y, diag

    # A pass with no audible content has no gap to close; repeating it verbatim
    # is correct, and warning about it would be a false alarm.
    if _last_audible_sample(y) <= 0:
        out = np.tile(y, reps if y.ndim == 1 else (reps, 1))
        diag["strategy"] = "silent"
        return out, diag

    n = int(musical_samples or 0)
    overhang_sec = (len(y) - n) / float(sr) if n > 0 else 0.0
    # The renderer pads by exactly one second. A much larger overhang means the
    # length we were given is too short, and folding at it would drop real music
    # onto the next downbeat - so distrust it and use the signal instead.
    plausible = 0 < n <= len(y) and overhang_sec <= max_overhang_sec
    period = n
    try:
        if plausible:
            out = seamless_tile(y, reps, musical_samples=n)
            diag["strategy"] = "overlap_add"
        else:
            period = _last_audible_sample(y)
            if period <= 0 or period > len(y):
                raise ValueError(
                    f"cannot locate the musical end (musical_samples={musical_samples!r}, "
                    f"samples={len(y)})"
                )
            core = y[:period]
            out = np.tile(core, reps if core.ndim == 1 else (reps, 1))
            diag["strategy"] = "trim_silence"
            diag["detail"] = (
                f"the stated musical length ({n} samples, leaving "
                f"{overhang_sec:.3f}s of overhang) is not plausible; trimmed "
                f"{(len(y) - period) / sr:.3f}s of trailing silence instead"
            )
    except Exception as exc:  # pragma: no cover - last resort only
        out = np.tile(y, reps if y.ndim == 1 else (reps, 1))
        period = len(y)
        diag["strategy"] = "plain_tile"
        diag["ok"] = False
        diag["detail"] = f"gapless tiling failed, loops may stutter: {exc}"
        return out, diag

    # Verify rather than assume: if a gap survived, say so.
    diag["gap_sec"] = _join_gap_seconds(out, period, reps, sr, 1e-4)
    if diag["gap_sec"] > max_gap_sec:
        diag["ok"] = False
        diag["detail"] = (
            f"{diag['gap_sec']:.3f}s of silence remains before each loop join "
            f"(strategy={diag['strategy']})"
        )
    return out, diag
