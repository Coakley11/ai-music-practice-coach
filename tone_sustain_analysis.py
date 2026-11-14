"""How steadily was a long tone held? The measurement, separated from the display.

Issue 79. The previous analysis answered three different questions with two numbers, and answered
all three badly:

* **Volume consistency** was the spread of the RMS over the *whole recording*, silence included. A
  steady tone with a second of silence at each end therefore scored 4% where the same tone trimmed
  scored 95% - the measurement was dominated by the parts where the musician was not playing.
* **Pitch stability** was ``100 - 4.5 * stdev(cents)``, which reaches zero at a spread of 22 cents.
  A quarter-tone wobble, a semitone change and an octave jump all came out as 0%, so the number
  could not tell a musician which of those had happened. Onset and release frames went into the
  same standard deviation, so the beginning and end of the note counted as instability.
* **Tuning** was folded into pitch stability's frame of reference. A note held perfectly steady but
  30 cents sharp was indistinguishable, in the stored numbers, from one that wandered by 30 cents.

So this module measures four separate things and says when it cannot measure them at all:

1. **the sustained portion** - which frames were really voiced, loud enough and not onset/release;
2. **pitch stability** - how steadily the pitch was held *around its own centre*, so being sharp or
   flat cannot change it;
3. **volume consistency** - how evenly the sound was sustained, with a deliberate crescendo or
   decrescendo reported as shape rather than counted as fluctuation;
4. **tuning offset against an explicit target note and octave**, with any octave difference stated
   as an octave difference instead of being presented as 1200 cents of being out of tune.

Nothing here imports Streamlit, and every function is deterministic for a given array, so the whole
thing is testable from synthesized signals with known properties.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

# --------------------------------------------------------------------------------------------
# Frame selection constants. Every one of these is a judgement about music, so each says why.
# --------------------------------------------------------------------------------------------

#: A frame counts as sounding when it is within this many dB of the loudest frame. Twenty-five dB
#: below the peak of a long tone is room noise or the tail of the release, not the note.
SOUNDING_FLOOR_DB = 25.0

#: pyin's own confidence in a frame. Below this its frequency is a guess, and a guess in the middle
#: of a stability measurement is indistinguishable from the musician moving.
MIN_VOICED_PROB = 0.5

#: Gaps this short inside a held note are pitch-tracker dropouts, not the end of the note.
MAX_GAP_SEC = 0.08

#: A longer silent gap between two runs of the SAME note is a dropout in one note, not two notes -
#: the sound failed. Up to this long it is still one note with a hole in it.
MAX_DROPOUT_SEC = 1.20

#: Two runs belong to the same note when their centres agree this closely.
SAME_NOTE_CENTS = 50.0

#: The attack and the release are not the sustain. Trim this much from each end of the held note -
#: or this fraction of it, whichever is smaller, so a short note is not trimmed into nothing.
EDGE_TRIM_SEC = 0.15
EDGE_TRIM_FRACTION = 0.12

#: Below this there is not enough held sound to say anything about steadiness.
MIN_SUSTAIN_SEC = 0.60
MIN_SUSTAIN_FRAMES = 8

#: A recording whose loudest moment is below this is too quiet to measure rather than badly played.
WEAK_PEAK_DBFS = -45.0

#: Only report a signal-to-noise figure when this much of the recording is quiet enough to serve
#: as a noise floor. A recording that is all note has no measurable noise floor, and pretending
#: otherwise rejected four perfectly good signals.
MIN_FLOOR_FRACTION = 0.10

#: Pitch movement over a block at least this long is a different note, not a wobble.
NOTE_CHANGE_BLOCK_SEC = 0.25
NOTE_CHANGE_CENTS = 50.0

#: Vibrato lives in this band. Slower is drift; faster is not something a player sustains.
VIBRATO_MIN_HZ = 3.0
VIBRATO_MAX_HZ = 9.0
VIBRATO_MIN_DEPTH_CENTS = 10.0

#: Window for the "where was the pitch centred" curve, which is what drifts under a vibrato.
CENTRE_WINDOW_SEC = 0.40

#: Identifies which algorithm produced a score, so a stored score is never silently reinterpreted
#: as if it had been produced by a different one. Rows saved before this existed have no version.
SCORING_VERSION = "tone-sustain-2026-11-v2"


# --------------------------------------------------------------------------------------------
# The two scoring curves. Both are anchor tables interpolated in log space, for one reason: a
# formula that saturates cannot answer "how bad?", and the whole complaint about the old score was
# that everything past a quarter tone was zero. These keep every size of error distinguishable,
# and the raw measurement is reported next to the score so the score is never the only evidence.
# --------------------------------------------------------------------------------------------

#: Pitch stability: robust spread of the sustained pitch, in cents, to a 0-100 score.
#: 0c=100 (nothing moved) · 6c=95 (a fine long tone) · 12c=88 · 25c=75 (audible waver)
#: 50c=58 (quarter tone) · 100c=38 (a semitone of movement) · 200c=22 · 400c=12 · 1200c=4 (an
#: octave) · 2400c=1. It never reaches 0: 0 is reserved for "not measured".
PITCH_STABILITY_ANCHORS: tuple[tuple[float, float], ...] = (
    (0.0, 100.0),
    (3.0, 98.0),
    (6.0, 95.0),
    (12.0, 88.0),
    (25.0, 75.0),
    (50.0, 58.0),
    (100.0, 38.0),
    (200.0, 22.0),
    (400.0, 12.0),
    (1200.0, 4.0),
    (2400.0, 1.0),
)

#: Volume consistency: robust spread in dB of the sustained loudness *after* removing a steady
#: crescendo or decrescendo, to a 0-100 score. 0dB=100 · 0.5dB=97 · 1dB=92 · 2dB=82 · 3dB=72 ·
#: 5dB=55 · 8dB=35 · 12dB=18 · 20dB=5 · 30dB=1. A dropout lands in the low numbers; a smooth
#: crescendo barely moves it, because the trend was removed first and is reported on its own.
VOLUME_CONSISTENCY_ANCHORS: tuple[tuple[float, float], ...] = (
    (0.0, 100.0),
    (0.5, 97.0),
    (1.0, 92.0),
    (2.0, 82.0),
    (3.0, 72.0),
    (5.0, 55.0),
    (8.0, 35.0),
    (12.0, 18.0),
    (20.0, 5.0),
    (30.0, 1.0),
)


def _interpolate_anchors(value: float, anchors: Sequence[tuple[float, float]]) -> float:
    """Score ``value`` against an anchor table, interpolating in log space between anchors.

    Log space because the musical meaning of a measurement is multiplicative: the step from 6 to
    12 cents matters as much as the step from 600 to 1200.
    """
    v = max(0.0, float(value))
    if not math.isfinite(v):
        return float(anchors[-1][1])
    if v <= anchors[0][0]:
        return float(anchors[0][1])
    if v >= anchors[-1][0]:
        return float(anchors[-1][1])
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if v <= x1:
            # log1p keeps the first segment, which starts at zero, well behaved.
            lo, hi, cur = math.log1p(x0), math.log1p(x1), math.log1p(v)
            frac = 0.0 if hi <= lo else (cur - lo) / (hi - lo)
            return float(y0 + frac * (y1 - y0))
    return float(anchors[-1][1])


def pitch_stability_from_spread(spread_cents: float) -> float:
    """Documented map from a robust pitch spread (cents) to a 0-100 stability score."""
    return round(_interpolate_anchors(spread_cents, PITCH_STABILITY_ANCHORS), 1)


def volume_consistency_from_fluctuation(fluctuation_db: float) -> float:
    """Documented map from a robust de-trended loudness spread (dB) to a 0-100 score."""
    return round(_interpolate_anchors(fluctuation_db, VOLUME_CONSISTENCY_ANCHORS), 1)


# --------------------------------------------------------------------------------------------
# Small robust statistics. Robust because one bad pitch frame in a hundred should not decide the
# answer, while a hundred frames of genuine movement must.
# --------------------------------------------------------------------------------------------


#: Trim this fraction off each end before taking the standard deviation, and rescale by the factor
#: below so the result still equals sigma for normally distributed frames. The factor is the
#: standard deviation of a standard normal truncated at the 2nd and 98th percentiles; it is checked
#: against ``statistics.NormalDist`` in the test suite rather than taken on trust.
SPREAD_TRIM_FRACTION = 0.02
SPREAD_TRIM_FACTOR = 0.890415


def robust_spread(values: np.ndarray) -> float:
    """A standard-deviation-like spread that a stray frame cannot dominate but a real minority can.

    A trimmed standard deviation: the most extreme 2% at each end are dropped, the rest is a plain
    standard deviation, and the result is rescaled so that for normally distributed frames it still
    equals sigma.

    Why not the median absolute deviation, which was the first attempt: the MAD of 200 identical
    frames and one wild one is exactly zero, so it needed a fallback for the case where more than
    half the frames agree exactly - and that fallback was the plain standard deviation, which the
    one wild frame then dominated completely (351 cents of "movement" from a note that never moved).
    Trimming has neither problem: the stray frame is trimmed away, while a fifth of the note an
    octave away is far too much to trim and shows up in full.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return 0.0
    ordered = np.sort(arr)
    n = ordered.size
    k = max(1, int(SPREAD_TRIM_FRACTION * n)) if n >= 25 else 0
    core = ordered[k : n - k] if (n - 2 * k) >= 2 else ordered
    return float(np.std(core)) / SPREAD_TRIM_FACTOR


def _linear_trend(times: np.ndarray, values: np.ndarray) -> tuple[float, np.ndarray]:
    """Total change of a least-squares line across ``times``, and the residual after removing it."""
    t = np.asarray(times, dtype=float)
    v = np.asarray(values, dtype=float)
    if t.size < 3 or float(np.ptp(t)) <= 0:
        return 0.0, v - (float(np.median(v)) if v.size else 0.0)
    slope, intercept = np.polyfit(t, v, 1)
    fitted = slope * t + intercept
    return float(slope * float(np.ptp(t))), v - fitted


def _moving_median(values: np.ndarray, window: int) -> np.ndarray:
    """Centred moving median, used to find where the pitch was centred under a vibrato."""
    arr = np.asarray(values, dtype=float)
    w = max(1, int(window))
    if w <= 1 or arr.size <= 2:
        return arr.copy()
    half = w // 2
    out = np.empty_like(arr)
    for i in range(arr.size):
        lo = max(0, i - half)
        hi = min(arr.size, i + half + 1)
        out[i] = np.median(arr[lo:hi])
    return out


# --------------------------------------------------------------------------------------------
# Frames
# --------------------------------------------------------------------------------------------


@dataclass
class ToneFrames:
    """Per-frame pitch and loudness for one recording, before any judgement is made."""

    times_sec: np.ndarray
    hz: np.ndarray
    voiced: np.ndarray
    voiced_prob: np.ndarray
    rms: np.ndarray
    hop_sec: float
    sample_rate: int
    duration_sec: float
    peak_dbfs: float

    def frame_db(self) -> np.ndarray:
        """Frame loudness in dB relative to the loudest frame of this recording."""
        peak = float(np.max(self.rms)) if self.rms.size else 0.0
        if peak <= 0:
            return np.full(self.rms.shape, -120.0)
        with np.errstate(divide="ignore"):
            return 20.0 * np.log10(np.maximum(self.rms, 1e-12) / peak)


@dataclass
class SustainWindow:
    """The part of the recording that is actually a held note."""

    start_index: int
    end_index: int  # exclusive
    start_sec: float
    end_sec: float
    seconds: float
    trimmed_onset_sec: float
    trimmed_release_sec: float
    voiced_seconds: float  # before trimming, the whole held run
    frames: int
    dropout_seconds: float = 0.0
    dropout_count: int = 0
    gap_mask: Any = None  # frames inside the window where the sound dropped out


@dataclass
class ToneMeasurement:
    """Everything measured about one long tone, and nothing inferred about what it means."""

    status: str  # "measured" | "insufficient"
    reason: str = ""
    scoring_version: str = SCORING_VERSION

    duration_sec: float = 0.0
    sustain_seconds: float = 0.0
    voiced_seconds: float = 0.0
    sustain_start_sec: float = 0.0
    sustain_end_sec: float = 0.0
    trimmed_onset_sec: float = 0.0
    trimmed_release_sec: float = 0.0
    frames_used: int = 0
    confidence: float = 0.0
    peak_dbfs: float = 0.0
    snr_db: float = 0.0

    detected_hz: float = 0.0
    detected_midi: float = 0.0
    detected_note: str = "—"

    pitch_spread_cents: float = 0.0
    max_deviation_cents: float = 0.0
    pitch_drift_cents: float = 0.0
    pitch_centre_drift_cents: float = 0.0
    largest_step_cents: float = 0.0
    note_change_detected: bool = False
    vibrato_rate_hz: float = 0.0
    vibrato_depth_cents: float = 0.0
    detection_octave_frames: int = 0
    pitch_stability_score: float | None = None

    volume_fluctuation_db: float = 0.0
    volume_trend_db: float = 0.0
    volume_dip_db: float = 0.0
    volume_consistency_score: float | None = None
    dropout_seconds: float = 0.0
    dropout_count: int = 0

    target_note: str | None = None
    target_midi: float | None = None
    target_is_pitch_class_only: bool = False
    tuning_offset_cents: float | None = None
    raw_offset_cents: float | None = None
    octave_offset_semitones: int = 0

    pitch_trace_hz: list[float] = field(default_factory=list)
    time_trace_sec: list[float] = field(default_factory=list)
    cents_trace: list[float] = field(default_factory=list)

    @property
    def measured(self) -> bool:
        return self.status == "measured"


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def hz_to_midi(hz: float) -> float:
    if hz <= 0 or not math.isfinite(hz):
        return float("nan")
    return 69.0 + 12.0 * math.log2(hz / 440.0)


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((float(midi) - 69.0) / 12.0))


FLAT_NOTE_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")


def midi_to_note_label(midi: float, *, prefer_flats: bool = False) -> str:
    """Name a MIDI number. ``prefer_flats`` spells it the way a Bb instrument's player reads it.

    A tenor saxophonist who asked for Bb3 should not be told they played A#3; it is the same pitch,
    but it is not the name they chose, and a readout that renames their note reads like an error.
    """
    if not math.isfinite(midi):
        return "—"
    rounded = int(round(midi))
    names = FLAT_NOTE_NAMES if prefer_flats else NOTE_NAMES
    return f"{names[rounded % 12]}{rounded // 12 - 1}"


def usable_mask(frames: ToneFrames) -> np.ndarray:
    """Frames that are voiced, confident, sounding and have a usable frequency.

    This is the one place silence leaves the measurement. Everything downstream sees only frames
    where the musician was actually making the note.
    """
    db = frames.frame_db()
    loud_enough = db >= -SOUNDING_FLOOR_DB
    confident = np.asarray(frames.voiced_prob, dtype=float) >= MIN_VOICED_PROB
    voiced = np.asarray(frames.voiced, dtype=bool)
    usable_hz = np.isfinite(frames.hz) & (np.asarray(frames.hz, dtype=float) > 0)
    return voiced & confident & loud_enough & usable_hz


def longest_run(mask: np.ndarray, *, hop_sec: float, max_gap_sec: float = MAX_GAP_SEC) -> tuple[int, int]:
    """The longest stretch of ``mask``, bridging gaps too short to be the end of a note.

    Returns a half-open index range; (0, 0) when there is nothing.
    """
    m = np.asarray(mask, dtype=bool)
    if not m.any():
        return (0, 0)
    gap_frames = max(0, int(round(max_gap_sec / hop_sec))) if hop_sec > 0 else 0
    best = (0, 0)
    i = 0
    n = m.size
    while i < n:
        if not m[i]:
            i += 1
            continue
        start = i
        end = i + 1
        j = i + 1
        while j < n:
            if m[j]:
                end = j + 1
                j += 1
                continue
            # How long is this gap? Bridge it only if short AND the note resumes afterwards.
            k = j
            while k < n and not m[k]:
                k += 1
            if k < n and (k - j) <= gap_frames:
                j = k
                continue
            break
        if (end - start) > (best[1] - best[0]):
            best = (start, end)
        i = max(j, end)
    return best


def _runs(mask: np.ndarray, *, hop_sec: float) -> list[tuple[int, int]]:
    """Every maximal run of ``mask``, bridging only tracker-length gaps."""
    m = np.asarray(mask, dtype=bool)
    out: list[tuple[int, int]] = []
    gap_frames = max(0, int(round(MAX_GAP_SEC / hop_sec))) if hop_sec > 0 else 0
    i = 0
    n = m.size
    while i < n:
        if not m[i]:
            i += 1
            continue
        start = i
        end = i + 1
        j = i + 1
        while j < n:
            if m[j]:
                end = j + 1
                j += 1
                continue
            k = j
            while k < n and not m[k]:
                k += 1
            if k < n and (k - j) <= gap_frames:
                j = k
                continue
            break
        out.append((start, end))
        i = max(j, end)
    return out


def join_dropouts(
    runs: list[tuple[int, int]],
    midi: np.ndarray,
    *,
    hop_sec: float,
) -> tuple[tuple[int, int], float, int]:
    """Join neighbouring runs of the same note across a dropout, and say how much was missing.

    A note the musician meant to hold can lose its sound for a moment - a breath that collapses, a
    reed that chokes, a bow that leaves the string. Measured as two separate notes, the better half
    gets a good score and the fault disappears. So runs are joined when the gap between them is
    short enough to be a dropout and the pitch on both sides is the same note.
    """
    if not runs:
        return (0, 0), 0.0, 0
    max_gap = max(1, int(round(MAX_DROPOUT_SEC / hop_sec))) if hop_sec > 0 else 1

    def centre(run: tuple[int, int]) -> float:
        seg = midi[run[0] : run[1]]
        seg = seg[np.isfinite(seg)]
        return float(np.median(seg)) if seg.size else float("nan")

    best: tuple[int, int] = max(runs, key=lambda r: r[1] - r[0])
    best_dropout = 0.0
    best_count = 0
    for i in range(len(runs)):
        start, end = runs[i]
        dropout_frames = 0
        count = 0
        base = centre(runs[i])
        j = i + 1
        while j < len(runs):
            gap = runs[j][0] - end
            same_note = (
                math.isfinite(base)
                and math.isfinite(centre(runs[j]))
                and abs(centre(runs[j]) - base) * 100.0 <= SAME_NOTE_CENTS
            )
            if gap <= 0 or gap > max_gap or not same_note:
                break
            dropout_frames += gap
            count += 1
            end = runs[j][1]
            j += 1
        if (end - start) > (best[1] - best[0]):
            best = (start, end)
            best_dropout = dropout_frames * hop_sec
            best_count = count
    return best, float(best_dropout), int(best_count)


def sustain_window(frames: ToneFrames, mask: np.ndarray | None = None) -> SustainWindow | None:
    """The held part of the note, with the attack and release trimmed off the ends."""
    m = usable_mask(frames) if mask is None else np.asarray(mask, dtype=bool)
    midi_all = np.array(
        [hz_to_midi(float(v)) if v and np.isfinite(v) else float("nan") for v in frames.hz],
        dtype=float,
    )
    (start, end), dropout_sec, dropout_count = join_dropouts(
        _runs(m, hop_sec=frames.hop_sec), midi_all, hop_sec=frames.hop_sec
    )
    if end <= start:
        return None
    run_seconds = (end - start) * frames.hop_sec
    trim_sec = min(EDGE_TRIM_SEC, run_seconds * EDGE_TRIM_FRACTION)
    trim_frames = int(round(trim_sec / frames.hop_sec)) if frames.hop_sec > 0 else 0
    # Never trim a short note into nothing: keep at least the minimum sustain, or no trim at all.
    if (end - start) - 2 * trim_frames < MIN_SUSTAIN_FRAMES:
        trim_frames = 0
    t_start = start + trim_frames
    t_end = end - trim_frames
    if t_end <= t_start:
        t_start, t_end = start, end
        trim_frames = 0
    times = np.asarray(frames.times_sec, dtype=float)
    return SustainWindow(
        start_index=int(t_start),
        end_index=int(t_end),
        start_sec=float(times[t_start]) if times.size else 0.0,
        end_sec=float(times[min(t_end, times.size - 1)]) if times.size else 0.0,
        seconds=float((t_end - t_start) * frames.hop_sec),
        trimmed_onset_sec=float(trim_frames * frames.hop_sec),
        trimmed_release_sec=float(trim_frames * frames.hop_sec),
        voiced_seconds=float(run_seconds),
        frames=int(t_end - t_start),
        dropout_seconds=float(dropout_sec),
        dropout_count=int(dropout_count),
        gap_mask=~m[t_start:t_end],
    )


def correct_detection_octaves(midi: np.ndarray, *, hop_sec: float) -> tuple[np.ndarray, int]:
    """Repair pyin's occasional octave slips without hiding a real octave change.

    A pitch tracker reports an exact octave away now and then, for a frame or two. Those frames are
    not the musician, and left in they add 1200 cents of "instability" that never happened. But a
    player really can jump an octave, and that must survive the measurement - so a displaced
    stretch longer than a note change's worth of frames is left exactly as it is.
    """
    arr = np.array(midi, dtype=float)
    if arr.size == 0:
        return arr, 0
    median = float(np.nanmedian(arr))
    offsets = np.round((arr - median) / 12.0)
    displaced = np.isfinite(arr) & (np.abs(offsets) >= 1)
    if not displaced.any():
        return arr, 0
    block = max(1, int(round(NOTE_CHANGE_BLOCK_SEC / hop_sec))) if hop_sec > 0 else 1
    repaired = 0
    i = 0
    n = arr.size
    while i < n:
        if not displaced[i]:
            i += 1
            continue
        j = i
        while j < n and displaced[j] and offsets[j] == offsets[i]:
            j += 1
        run = j - i
        if run < block:
            # Short enough to be the tracker, not the player - and only when folding it back
            # actually lands near the centre, so an unrelated frequency is never "corrected".
            folded = arr[i:j] - offsets[i] * 12.0
            if np.all(np.abs(folded - median) <= 0.5):
                arr[i:j] = folded
                repaired += run
        i = j
    return arr, int(repaired)


def _vibrato(cents: np.ndarray, hop_sec: float) -> tuple[float, float]:
    """Rate (Hz) and depth (cents, half of peak-to-peak) of a regular modulation, or (0, 0).

    Rate comes from counting mean crossings of the de-trended curve, which is robust for the few
    cycles a practice long tone contains and needs no FFT resolution gymnastics.
    """
    if cents.size < 8 or hop_sec <= 0:
        return 0.0, 0.0
    t = np.arange(cents.size) * hop_sec
    _, residual = _linear_trend(t, cents)
    centred = residual - float(np.mean(residual))
    signs = np.sign(centred)
    signs = signs[signs != 0]
    if signs.size < 4:
        return 0.0, 0.0
    crossings = int(np.sum(signs[1:] != signs[:-1]))
    span = float(cents.size * hop_sec)
    if span <= 0 or crossings < 2:
        return 0.0, 0.0
    rate = crossings / (2.0 * span)
    depth = float(np.percentile(centred, 95) - np.percentile(centred, 5)) / 2.0
    if not (VIBRATO_MIN_HZ <= rate <= VIBRATO_MAX_HZ) or depth < VIBRATO_MIN_DEPTH_CENTS:
        return 0.0, 0.0
    return float(rate), float(depth)


def _largest_step(cents: np.ndarray, hop_sec: float) -> float:
    """The biggest change between consecutive blocks of held sound.

    This is what separates "wandered a little" from "changed note": a wobble averages out inside a
    quarter-second block, a step does not.
    """
    if hop_sec <= 0:
        return 0.0
    block = max(2, int(round(NOTE_CHANGE_BLOCK_SEC / hop_sec)))
    if cents.size < 2 * block:
        return 0.0
    medians = [
        float(np.median(cents[i : i + block]))
        for i in range(0, cents.size - block + 1, block)
    ]
    if len(medians) < 2:
        return 0.0
    return float(max(abs(b - a) for a, b in zip(medians, medians[1:])))


def resolve_target(target_note: str | None) -> tuple[float | None, bool]:
    """Parse a target into a MIDI number, saying whether it named an octave at all.

    ``"E4"`` is a note. ``"E"`` is a pitch class: a contract where any E counts, which the analysis
    must then honour instead of quietly assuming octave 4 - the whole of defect 3.
    """
    token = str(target_note or "").strip().replace("♯", "#").replace("♭", "b")
    if not token:
        return None, False
    name = token[0].upper()
    if name not in "ABCDEFG":
        return None, False
    rest = token[1:]
    base = NOTE_NAMES.index(name)
    if rest.startswith("#"):
        base = (base + 1) % 12
        rest = rest[1:]
    elif rest.startswith("b"):
        base = (base - 1) % 12
        rest = rest[1:]
    rest = rest.strip()
    if not rest:
        return float(base), True  # pitch class only: octave deliberately unknown
    try:
        octave = int(rest)
    except ValueError:
        return None, False
    return float((octave + 1) * 12 + base), False


def tuning_against_target(
    detected_midi: float,
    target_note: str | None,
) -> tuple[float | None, float | None, int, bool, float | None]:
    """Tuning offset in cents, octaves stated separately rather than folded into the cents.

    Returns ``(offset_cents, raw_offset_cents, octave_offset_semitones, pitch_class_only,
    target_midi)``. ``offset_cents`` is how far the note is from the *nearest octave* of the target
    pitch class, which is what a musician means by "am I in tune"; ``raw_offset_cents`` is the plain
    difference, kept so nothing is hidden and a stored legacy value can still be explained.
    """
    target_midi, pitch_class_only = resolve_target(target_note)
    if target_midi is None or not math.isfinite(detected_midi):
        return None, None, 0, False, None
    if pitch_class_only:
        # Any octave of this pitch class is the target. Choose the one the musician actually played.
        pc = float(target_midi) % 12.0
        candidate = round(detected_midi - pc)
        nearest = pc + 12.0 * round((detected_midi - pc) / 12.0)
        offset = (detected_midi - nearest) * 100.0
        del candidate
        return float(offset), float(offset), 0, True, float(nearest)
    raw = (detected_midi - float(target_midi)) * 100.0
    octaves = int(round(raw / 1200.0))
    offset = raw - octaves * 1200.0
    return float(offset), float(raw), int(octaves * 12), False, float(target_midi)


def measure_tone(
    frames: ToneFrames,
    *,
    target_note: str | None = None,
    trace_points: int = 120,
) -> ToneMeasurement:
    """Measure one long tone from its frames, or say why it cannot be measured.

    Never returns a zero score to mean "unknown": an unmeasurable recording comes back with
    ``status="insufficient"``, the scores left as ``None``, and a reason in a musician's words.
    """
    out = ToneMeasurement(status="insufficient")
    out.duration_sec = float(frames.duration_sec)
    out.peak_dbfs = float(frames.peak_dbfs)
    out.target_note = str(target_note) if target_note else None

    if frames.peak_dbfs < WEAK_PEAK_DBFS:
        out.reason = (
            "The recording is too quiet to measure - move closer to the microphone or play louder."
        )
        return out

    mask = usable_mask(frames)
    db = frames.frame_db()
    quiet = db[~mask]
    # Reported only when there is really a quiet stretch to measure against; a recording that is
    # all note has no noise floor, and inventing one is how four good signals got rejected.
    if mask.any() and quiet.size >= max(3, int(MIN_FLOOR_FRACTION * db.size)):
        out.snr_db = round(float(np.median(db[mask]) - np.percentile(quiet, 90)), 1)
    if not mask.any():
        out.reason = "Not enough reliable pitch detected - no sustained note was found."
        return out

    window = sustain_window(frames, mask)
    if window is None:
        out.reason = "Not enough reliable pitch detected - no sustained note was found."
        return out
    out.voiced_seconds = window.voiced_seconds
    out.sustain_seconds = window.seconds
    out.sustain_start_sec = window.start_sec
    out.sustain_end_sec = window.end_sec
    out.trimmed_onset_sec = window.trimmed_onset_sec
    out.trimmed_release_sec = window.trimmed_release_sec
    out.frames_used = window.frames

    sl = slice(window.start_index, window.end_index)
    # Loudness is measured over the WHOLE sustained window, dropouts included: a moment where the
    # sound failed is the most important thing that happened to the loudness of that note.
    rms_window = np.asarray(frames.rms, dtype=float)[sl]
    times_window = np.asarray(frames.times_sec, dtype=float)[sl]
    out.dropout_seconds = float(window.dropout_seconds)
    out.dropout_count = int(window.dropout_count)
    # Pitch is measured only where there is a pitch to measure.
    hz = np.asarray(frames.hz, dtype=float)[sl]
    prob = np.asarray(frames.voiced_prob, dtype=float)[sl]
    rms = rms_window
    times = times_window
    keep = np.isfinite(hz) & (hz > 0)
    hz, prob, rms, times = hz[keep], prob[keep], rms[keep], times[keep]

    if hz.size < MIN_SUSTAIN_FRAMES or window.seconds < MIN_SUSTAIN_SEC:
        out.reason = (
            "Not enough steady sound to measure - hold one note for at least "
            f"{MIN_SUSTAIN_SEC:.1f} seconds."
        )
        out.confidence = float(np.mean(prob)) if prob.size else 0.0
        return out
    out.confidence = float(np.mean(prob))

    # ---- pitch -----------------------------------------------------------------------------
    midi = np.array([hz_to_midi(float(v)) for v in hz], dtype=float)
    midi, repaired = correct_detection_octaves(midi, hop_sec=frames.hop_sec)
    out.detection_octave_frames = repaired
    centre_midi = float(np.median(midi))
    out.detected_midi = centre_midi
    out.detected_hz = float(midi_to_hz(centre_midi))
    prefer_flats = "b" in str(target_note or "")[1:2].lower()
    out.detected_note = midi_to_note_label(centre_midi, prefer_flats=prefer_flats)

    # Stability is measured around the note's OWN centre, so a note that is sharp or flat but
    # perfectly steady scores as steady. Tuning is a separate measurement, below.
    cents = (midi - centre_midi) * 100.0
    out.pitch_spread_cents = round(robust_spread(cents), 2)
    # The single worst excursion, kept because a musician asks "how far did it go?" as well as
    # "how much did it move on average".
    out.max_deviation_cents = round(float(np.max(np.abs(cents))) if cents.size else 0.0, 2)
    drift, _ = _linear_trend(times, cents)
    out.pitch_drift_cents = round(float(drift), 2)
    window_frames = max(1, int(round(CENTRE_WINDOW_SEC / frames.hop_sec))) if frames.hop_sec else 1
    centre_curve = _moving_median(cents, window_frames)
    centre_drift, _ = _linear_trend(times, centre_curve)
    out.pitch_centre_drift_cents = round(float(centre_drift), 2)
    out.largest_step_cents = round(_largest_step(cents, frames.hop_sec), 2)
    out.note_change_detected = bool(out.largest_step_cents >= NOTE_CHANGE_CENTS)
    rate, depth = _vibrato(cents, frames.hop_sec)
    out.vibrato_rate_hz = round(rate, 2)
    out.vibrato_depth_cents = round(depth, 2)
    out.pitch_stability_score = pitch_stability_from_spread(out.pitch_spread_cents)

    # ---- loudness --------------------------------------------------------------------------
    peak = float(np.max(rms_window)) if rms_window.size else 0.0
    with np.errstate(divide="ignore"):
        sustain_db = 20.0 * np.log10(np.maximum(rms_window, 1e-12) / max(peak, 1e-12))
    # Floor the dB curve: a dropout to digital silence would otherwise read as -240 dB and swamp
    # every other variation. Thirty dB down is already inaudible under one's own playing.
    sustain_db = np.maximum(sustain_db, -30.0)
    trend, residual = _linear_trend(times_window, sustain_db)
    out.volume_trend_db = round(float(trend), 2)
    # The plain standard deviation, on purpose. A robust spread ignores a small minority of frames
    # by design, and a dropout IS a small minority of frames - a note that fell silent for 0.4 s
    # out of 2.7 scored 99.9% for evenness until this changed. Unlike pitch, loudness has no
    # tracker artefacts to protect against: every frame is sound the musician really made.
    out.volume_fluctuation_db = round(float(np.std(residual)) if residual.size else 0.0, 2)
    # And the single deepest moment below the overall shape, which is what a dropout feels like.
    out.volume_dip_db = round(float(-np.min(residual)) if residual.size else 0.0, 2)
    out.volume_consistency_score = volume_consistency_from_fluctuation(out.volume_fluctuation_db)

    # ---- tuning, with octaves stated as octaves ---------------------------------------------
    offset, raw, octave_semitones, pc_only, target_midi = tuning_against_target(
        centre_midi, target_note
    )
    out.tuning_offset_cents = None if offset is None else round(offset, 1)
    out.raw_offset_cents = None if raw is None else round(raw, 1)
    out.octave_offset_semitones = octave_semitones
    out.target_is_pitch_class_only = pc_only
    out.target_midi = target_midi

    # ---- traces, which must describe the same frames as the numbers --------------------------
    step = max(1, int(math.ceil(hz.size / max(1, trace_points))))
    out.pitch_trace_hz = [float(v) for v in hz[::step]]
    out.time_trace_sec = [float(v) for v in times[::step]]
    out.cents_trace = [float(v) for v in cents[::step]]

    out.status = "measured"
    return out


def explain(measurement: ToneMeasurement) -> list[str]:
    """What the numbers mean, in a musician's words - and never contradicting them."""
    m = measurement
    if not m.measured:
        return [m.reason or "Not enough reliable sound to measure."]

    lines: list[str] = []

    if m.note_change_detected:
        lines.append(
            f"The pitch **changed by about {m.largest_step_cents:.0f} cents** during the note "
            f"({_interval_words(m.largest_step_cents)}), so this is two notes rather than one held "
            "tone. Pitch stability describes the whole recording."
        )
    elif m.vibrato_rate_hz:
        lines.append(
            f"Regular **vibrato** at {m.vibrato_rate_hz:.1f} Hz, about "
            f"±{m.vibrato_depth_cents:.0f} cents. That movement is intentional and it is included "
            f"in the stability number; the centre of the vibrato moved "
            f"{abs(m.pitch_centre_drift_cents):.0f} cents."
        )
    elif abs(m.pitch_drift_cents) >= 15:
        direction = "upward" if m.pitch_drift_cents > 0 else "downward"
        lines.append(
            f"The pitch drifted **{direction} by {abs(m.pitch_drift_cents):.0f} cents** across the "
            "held note - steady air and a settled embouchure keep it centred."
        )
    elif m.pitch_spread_cents <= 8:
        lines.append(
            f"**Pitch held very steadily** - it moved about {m.pitch_spread_cents:.0f} cents."
        )
    else:
        lines.append(
            f"Pitch moved about **{m.pitch_spread_cents:.0f} cents** around its centre."
        )

    if m.volume_trend_db <= -4:
        lines.append(
            f"The sound **faded by {abs(m.volume_trend_db):.0f} dB** from start to end. A "
            "decrescendo is fine if you meant it; if not, it is air support running out."
        )
    elif m.volume_trend_db >= 4:
        lines.append(f"The sound **grew by {m.volume_trend_db:.0f} dB** - a crescendo shape.")
    if m.volume_dip_db >= 6 and not m.dropout_count:
        lines.append(
            f"The sound **fell about {m.volume_dip_db:.0f} dB below its own level** at its weakest "
            "moment during the sustain - that dip is what pulled the evenness number down."
        )
    if m.dropout_count:
        lines.append(
            f"The sound **dropped out {m.dropout_count} time"
            f"{'s' if m.dropout_count != 1 else ''}** during the note, for about "
            f"{m.dropout_seconds:.1f} s in total. That is counted as unevenness, not as the end of "
            "the note."
        )
    if m.volume_fluctuation_db >= 3:
        lines.append(
            f"Loudness **wavered by about {m.volume_fluctuation_db:.1f} dB** during the sustain, "
            "beyond that overall shape."
        )
    elif m.volume_fluctuation_db <= 1:
        lines.append("**Volume stayed even** through the sustain.")

    if m.octave_offset_semitones:
        octaves = abs(m.octave_offset_semitones) // 12
        where = "above" if m.octave_offset_semitones > 0 else "below"
        lines.append(
            f"You played **{octaves} octave{'s' if octaves != 1 else ''} {where} the reference "
            f"{m.target_note}** - the detected note is {m.detected_note}. Tuning is reported "
            "against that octave, not against the reference's own octave."
        )
    if m.tuning_offset_cents is not None and abs(m.tuning_offset_cents) >= 10:
        side = "sharp" if m.tuning_offset_cents > 0 else "flat"
        lines.append(
            f"**Tuning:** about {abs(m.tuning_offset_cents):.0f} cents {side} of "
            f"{m.detected_note}. Tuning is separate from steadiness - a steady note can be sharp."
        )
    elif m.tuning_offset_cents is not None:
        lines.append(f"**Tuning:** within {abs(m.tuning_offset_cents):.0f} cents of {m.detected_note}.")

    if m.confidence < 0.75:
        lines.append(
            f"Pitch-detection confidence was moderate ({m.confidence * 100:.0f}%), so treat the "
            "fine detail with some caution."
        )
    return lines


def _interval_words(cents: float) -> str:
    """Name a pitch distance the way a musician would, so a number is never the only clue."""
    c = abs(float(cents))
    if c >= 1150:
        return "about an octave"
    if c >= 650:
        return "more than a tritone"
    if c >= 250:
        return "more than a whole tone"
    if c >= 150:
        return "about a whole tone"
    if c >= 75:
        return "about a semitone"
    if c >= 40:
        return "about a quarter tone"
    return "less than a quarter tone"


def frames_from_arrays(
    *,
    times_sec: Sequence[float],
    hz: Sequence[float],
    voiced: Sequence[bool],
    voiced_prob: Sequence[float],
    rms: Sequence[float],
    hop_sec: float,
    sample_rate: int,
    duration_sec: float,
    peak_dbfs: float,
) -> ToneFrames:
    """Build frames directly, for tests and for any detector other than the default one."""
    return ToneFrames(
        times_sec=np.asarray(times_sec, dtype=float),
        hz=np.asarray(hz, dtype=float),
        voiced=np.asarray(voiced, dtype=bool),
        voiced_prob=np.asarray(voiced_prob, dtype=float),
        rms=np.asarray(rms, dtype=float),
        hop_sec=float(hop_sec),
        sample_rate=int(sample_rate),
        duration_sec=float(duration_sec),
        peak_dbfs=float(peak_dbfs),
    )


def measurement_as_dict(m: ToneMeasurement) -> dict[str, Any]:
    """A JSON-safe record of the measurement, for storage beside a saved take."""
    return {
        "status": m.status,
        "reason": m.reason,
        "scoring_version": m.scoring_version,
        "duration_sec": round(m.duration_sec, 3),
        "sustain_seconds": round(m.sustain_seconds, 3),
        "voiced_seconds": round(m.voiced_seconds, 3),
        "frames_used": m.frames_used,
        "confidence": round(m.confidence, 3),
        "peak_dbfs": round(m.peak_dbfs, 1),
        "snr_db": round(m.snr_db, 1),
        "detected_note": m.detected_note,
        "detected_hz": round(m.detected_hz, 3),
        "pitch_spread_cents": m.pitch_spread_cents,
        "max_deviation_cents": m.max_deviation_cents,
        "pitch_drift_cents": m.pitch_drift_cents,
        "pitch_centre_drift_cents": m.pitch_centre_drift_cents,
        "largest_step_cents": m.largest_step_cents,
        "note_change_detected": m.note_change_detected,
        "vibrato_rate_hz": m.vibrato_rate_hz,
        "vibrato_depth_cents": m.vibrato_depth_cents,
        "detection_octave_frames": m.detection_octave_frames,
        "pitch_stability_score": m.pitch_stability_score,
        "volume_fluctuation_db": m.volume_fluctuation_db,
        "volume_trend_db": m.volume_trend_db,
        "volume_dip_db": m.volume_dip_db,
        "dropout_seconds": round(m.dropout_seconds, 3),
        "dropout_count": m.dropout_count,
        "volume_consistency_score": m.volume_consistency_score,
        "target_note": m.target_note,
        "target_is_pitch_class_only": m.target_is_pitch_class_only,
        "tuning_offset_cents": m.tuning_offset_cents,
        "raw_offset_cents": m.raw_offset_cents,
        "octave_offset_semitones": m.octave_offset_semitones,
    }


__all__ = [
    "FLAT_NOTE_NAMES",
    "SPREAD_TRIM_FACTOR",
    "SPREAD_TRIM_FRACTION",
    "PITCH_STABILITY_ANCHORS",
    "SCORING_VERSION",
    "VOLUME_CONSISTENCY_ANCHORS",
    "SustainWindow",
    "ToneFrames",
    "ToneMeasurement",
    "correct_detection_octaves",
    "explain",
    "frames_from_arrays",
    "join_dropouts",
    "hz_to_midi",
    "longest_run",
    "measure_tone",
    "measurement_as_dict",
    "midi_to_hz",
    "midi_to_note_label",
    "pitch_stability_from_spread",
    "resolve_target",
    "robust_spread",
    "sustain_window",
    "tuning_against_target",
    "usable_mask",
    "volume_consistency_from_fluctuation",
]
