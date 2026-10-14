"""MC4 — one span-aware layer that puts performed notes on the chord timeline.

Inputs are timestamps (seconds into the take) plus the span's concert chord timeline, BPM,
meter and an alignment offset (where bar 1 of the span starts). Outputs say, for every
detected note, which loop / bar / beat / chord it belongs to and how far it is from the
neighbouring chord changes. Every span Mission evaluator reads this; none re-derives it.

Also here: loop coverage (complete / long / short / multi-loop) and alignment for uploaded
files — estimated from onsets, tempo fit and harmonic fit, with an honest confidence — plus
beat / bar nudges that only move the offset (no new pitch detection).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

# Alignment sources.
SOURCE_LIVE = "live"
SOURCE_DETECTED = "detected"
SOURCE_CONFIRMED = "user_confirmed"
SOURCE_ADJUSTED = "user_adjusted"
TRUSTED_SOURCES = (SOURCE_LIVE, SOURCE_CONFIRMED, SOURCE_ADJUSTED)
# A detected start is trusted without confirmation only above this confidence.
AUTO_TRUST_CONFIDENCE = 0.8
# Fraction of a loop's bars that must be covered to call it complete.
_COMPLETE_EPS_BEATS = 0.75


# --------------------------------------------------------------------------- grid


@dataclass(frozen=True)
class Slot:
    index: int
    chord: str
    start_beat: float
    beats: float

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.beats


@dataclass(frozen=True)
class SpanGrid:
    bpm: int
    meter: str
    pulse_sec: float
    bar_sec: float
    pulses_per_bar: int
    slots: tuple[Slot, ...]

    @property
    def loop_beats(self) -> float:
        return self.slots[-1].end_beat if self.slots else 0.0

    @property
    def loop_sec(self) -> float:
        return self.loop_beats * self.pulse_sec

    @property
    def loop_bars(self) -> float:
        return self.loop_beats / max(1, self.pulses_per_bar)

    def slot_at(self, beat_in_loop: float) -> Slot:
        for s in self.slots:
            if s.start_beat <= beat_in_loop < s.end_beat:
                return s
        return self.slots[-1]

    def change_beats(self) -> list[float]:
        """Beat positions (within a loop) where a new chord starts, excluding beat 0."""
        return [s.start_beat for s in self.slots[1:]]


def build_grid(timeline: Sequence[dict[str, Any]], *, bpm: int, meter: str) -> SpanGrid:
    from songs.meter import meter_timing

    timing = meter_timing(int(bpm or 100), str(meter or "4/4"))
    slots: list[Slot] = []
    beat = 0.0
    for i, t in enumerate(timeline):
        bars = max(1, int(t.get("bars") or 1))
        beats = float(bars * timing.pulses_per_bar)
        slots.append(Slot(i, str(t.get("chord") or ""), beat, beats))
        beat += beats
    return SpanGrid(
        bpm=int(bpm or 100),
        meter=timing.time_signature,
        pulse_sec=float(timing.pulse_sec),
        bar_sec=float(timing.bar_sec),
        pulses_per_bar=int(timing.pulses_per_bar),
        slots=tuple(slots),
    )


# --------------------------------------------------------------------------- assignment


@dataclass(frozen=True)
class AssignedEvent:
    time: float
    duration: float
    midi: int
    loop_index: int  # -1 = before bar 1 of the first loop (pickup)
    beat: float  # absolute beats from bar 1 of loop 0 (negative for pickups)
    beat_in_loop: float
    bar_in_loop: int
    chord_index: int
    chord: str
    beats_since_change: float  # since the start of its chord
    beats_to_next_change: float | None  # until the next chord in this loop (None: last chord)

    @property
    def pc(self) -> int:
        return self.midi % 12

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


BOUNDARY_SLOP_BEATS = 0.15


def _next_boundary(beat: float, grid: SpanGrid) -> float | None:
    """The next chord-change beat (absolute, across loops) at or after ``beat``."""
    loop_beats = grid.loop_beats
    if loop_beats <= 0:
        return None
    if beat < 0:
        return 0.0
    loop = int(beat // loop_beats)
    within = beat - loop * loop_beats
    for s in grid.slots:
        if s.start_beat > within:
            return loop * loop_beats + s.start_beat
    return (loop + 1) * loop_beats


def assign_events(
    notes: Sequence[dict[str, Any]], grid: SpanGrid, *, offset_sec: float,
) -> list[AssignedEvent]:
    """Place each detected note (``t`` seconds, ``midi``, ``dur``) on the span timeline."""
    out: list[AssignedEvent] = []
    loop_beats = grid.loop_beats
    if loop_beats <= 0:
        return out
    for n in notes:
        t = float(n.get("t", n.get("time", 0.0)))
        midi = int(round(float(n.get("midi", 0))))
        dur = float(n.get("dur", n.get("duration", 0.0)) or 0.0)
        beat = (t - float(offset_sec)) / grid.pulse_sec
        # Detection jitter: a note starting a hair before a chord boundary (or bar 1) belongs to
        # the chord it is played into. Deliberate anticipations (≥ an eighth early) are kept.
        nxt = _next_boundary(beat, grid)
        if nxt is not None and 0 < nxt - beat <= BOUNDARY_SLOP_BEATS:
            beat = nxt
        if beat < 0:
            loop_index = -1
            beat_in_loop = beat  # pickup: before bar 1
            slot = grid.slots[0]
            since = beat
            to_next: float | None = -beat  # time to the first chord's downbeat
        else:
            loop_index = int(beat // loop_beats)
            beat_in_loop = beat - loop_index * loop_beats
            slot = grid.slot_at(beat_in_loop)
            since = beat_in_loop - slot.start_beat
            to_next = (slot.end_beat - beat_in_loop) if slot.index < len(grid.slots) - 1 else None
        out.append(
            AssignedEvent(
                time=t,
                duration=dur,
                midi=midi,
                loop_index=loop_index,
                beat=beat,
                beat_in_loop=beat_in_loop,
                bar_in_loop=int(beat_in_loop // grid.pulses_per_bar) if beat_in_loop >= 0 else -1,
                chord_index=slot.index,
                chord=slot.chord,
                beats_since_change=since,
                beats_to_next_change=to_next,
            )
        )
    return out


# --------------------------------------------------------------------------- coverage


@dataclass
class Coverage:
    status: str  # complete | long | multi | short | empty
    complete_loops: int
    covered_beats_last: float  # beats covered in the last (incomplete) loop
    analyzed_loop: int
    loops_with_notes: list[int] = field(default_factory=list)
    covered_chords: list[int] = field(default_factory=list)  # chord indices reached in the analyzed loop
    missing_chords: list[int] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def coverage(
    duration_sec: float, grid: SpanGrid, *, offset_sec: float, events: Sequence[AssignedEvent],
) -> Coverage:
    """How much of the span the take covers once bar 1 is at ``offset_sec``."""
    loop_beats = grid.loop_beats
    covered = max(0.0, (float(duration_sec) - float(offset_sec)) / grid.pulse_sec)
    complete = int((covered + _COMPLETE_EPS_BEATS) // loop_beats) if loop_beats else 0
    with_notes = sorted({e.loop_index for e in events if e.loop_index >= 0})
    if not with_notes:
        return Coverage("empty", complete, covered, 0, note="No notes were detected after the start of bar 1.")
    if complete == 0:
        # A chord counts as covered only when a usable part of it is in the recording
        # (at least one beat, or half of a short chord) — not a trailing fraction of a beat.
        reached = sorted({s.index for s in grid.slots if covered >= s.start_beat + min(1.0, 0.5 * (s.end_beat - s.start_beat))})
        missing = [s.index for s in grid.slots if s.index not in reached]
        return Coverage("short", 0, covered, 0, with_notes, reached, missing)
    last_partial = covered - complete * loop_beats
    status = "complete" if complete == 1 and last_partial < 1.0 else ("multi" if complete > 1 else "long")
    return Coverage(
        status, complete, max(0.0, last_partial), with_notes[0] if with_notes[0] < complete else 0,
        with_notes, [s.index for s in grid.slots], [],
    )


def events_in_loop(events: Sequence[AssignedEvent], loop_index: int, *, pickup_beats: float = 1.0) -> list[AssignedEvent]:
    """A loop's notes, plus anticipations just before its bar 1 (pickups into chord 1)."""
    out = [e for e in events if e.loop_index == loop_index]
    if loop_index == 0:
        out = [e for e in events if e.loop_index == -1 and e.beat >= -pickup_beats] + out
    return out


# --------------------------------------------------------------------------- alignment


@dataclass
class Alignment:
    offset_sec: float
    confidence: float
    source: str
    detected_offset_sec: float
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def trusted(self) -> bool:
        return self.source in TRUSTED_SOURCES or (
            self.source == SOURCE_DETECTED and self.confidence >= AUTO_TRUST_CONFIDENCE
        )

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["trusted"] = self.trusted
        return out

    @classmethod
    def from_dict(cls, raw: Any) -> "Alignment | None":
        if not isinstance(raw, dict) or raw.get("offset_sec") is None:
            return None
        return cls(
            offset_sec=float(raw.get("offset_sec") or 0.0),
            confidence=float(raw.get("confidence") or 0.0),
            source=str(raw.get("source") or SOURCE_DETECTED),
            detected_offset_sec=float(raw.get("detected_offset_sec", raw.get("offset_sec")) or 0.0),
            detail=dict(raw.get("detail") or {}),
        )


def live_alignment(*, count_in_sec: float, mix_offset_sec: float = 0.0, loop_sec: float = 0.0, loops: int = 1) -> Alignment:
    """A take recorded with the app's backing: bar 1 follows the count-in (same model as the mix)."""
    offset = max(0.0, float(count_in_sec) + float(mix_offset_sec))
    return Alignment(
        offset_sec=round(offset, 4),
        confidence=1.0,
        source=SOURCE_LIVE,
        detected_offset_sec=round(offset, 4),
        detail={
            "audio_start_sec": 0.0,
            "count_in_sec": round(float(count_in_sec), 4),
            "mix_offset_sec": round(float(mix_offset_sec), 4),
            "first_span_downbeat_sec": round(offset, 4),
            "loop_sec": round(float(loop_sec), 4),
            "loop_count": int(loops),
        },
    )


def _harmonic_fit(notes: Sequence[dict[str, Any]], grid: SpanGrid, offset: float, chord_pcs: Sequence[Sequence[int]]) -> float:
    """Duration-weighted share of notes that are chord tones of the chord they land on."""
    events = assign_events(notes, grid, offset_sec=offset)
    total = 0.0
    hit = 0.0
    for e in events:
        if e.loop_index < 0:
            continue
        w = max(0.05, min(2.0, e.duration or 0.25))
        total += w
        if e.pc in chord_pcs[e.chord_index]:
            hit += w
    return hit / total if total else 0.0


def _change_fit(notes: Sequence[dict[str, Any]], grid: SpanGrid, offset: float, chord_pcs: Sequence[Sequence[int]], duration: float) -> tuple[float, float]:
    """(target fit, downbeat fit) over every chord change the take covers.

    target fit: a note within half a beat of the change is a chord tone of the arriving chord.
    downbeat fit: some note starts within a quarter beat of the change at all.
    """
    starts = [(float(n.get("t", 0.0)), int(round(float(n.get("midi", 0)))) % 12) for n in notes]
    loops = max(1, int((duration - offset) / grid.loop_sec + 0.25)) if grid.loop_sec else 1
    hits = targets = onsets = 0
    for loop in range(loops):
        for s in grid.slots:
            t_change = offset + (loop * grid.loop_beats + s.start_beat) * grid.pulse_sec
            if t_change > duration - 0.1:
                continue
            targets += 1
            near = [(abs(t - t_change), pc) for t, pc in starts if abs(t - t_change) <= 0.5 * grid.pulse_sec]
            if near:
                if min(d for d, _ in near) <= 0.25 * grid.pulse_sec:
                    onsets += 1
                pc = min(near)[1]
                if pc in chord_pcs[s.index]:
                    hits += 1
    if not targets:
        return 0.0, 0.0
    return hits / targets, onsets / targets


def _grid_fit(onsets: Sequence[float], grid: SpanGrid, offset: float) -> float:
    """Share of onsets within an eighth-note tolerance of the beat grid from ``offset``."""
    if not onsets:
        return 0.0
    half = grid.pulse_sec / 2.0
    tol = 0.12 * grid.pulse_sec
    near = 0
    for t in onsets:
        r = (t - offset) % half
        if min(r, half - r) <= tol:
            near += 1
    return near / len(onsets)


def _tempo_fit(detected_bpm: float | None, expected_bpm: int) -> float:
    if not detected_bpm or detected_bpm <= 0:
        return 0.5  # unknown, neither for nor against
    best = min(abs(detected_bpm * f / expected_bpm - 1.0) for f in (0.5, 1.0, 2.0, 2.0 / 3.0, 1.5))
    return max(0.0, 1.0 - best / 0.12)


def estimate_upload_alignment(
    transcription: dict[str, Any],
    grid: SpanGrid,
    *,
    chord_pcs: Sequence[Sequence[int]],
) -> Alignment:
    """Where bar 1 of the span most likely starts in an uploaded take, with a confidence.

    Candidates sit on the beat grid around the first strong onset (a phrase may start with a
    pickup, so the first note is not assumed to be beat 1). Each candidate is scored by how
    well the notes fit the chords they would fall on; onset-grid fit and tempo agreement
    with the Mission BPM temper the confidence, and a near-tie lowers it.
    """
    notes = list(transcription.get("notes") or [])
    onsets = [float(x) for x in transcription.get("onsets") or [n["t"] for n in notes]]
    strengths = list(transcription.get("onset_strengths") or [])
    duration = float(transcription.get("duration") or 0.0)
    if not notes or not onsets:
        return Alignment(0.0, 0.0, SOURCE_DETECTED, 0.0, {"reason": "no notes detected"})
    # Anchor on the first detected *note* (same time base as the notes being assigned); the
    # onset strengths only break ties when the very first note is a faint sliver.
    first_strong = float(notes[0].get("t", 0.0))
    if strengths and len(strengths) == len(onsets):
        peak = max(strengths) or 1.0
        strong = [t for t, s in zip(onsets, strengths) if s >= 0.3 * peak]
        if strong and strong[0] < first_strong - 0.05:
            first_strong = min(first_strong, strong[0])
    pulses = grid.pulses_per_bar
    shifts = range(-(pulses - 1), pulses)
    scored = []
    for k in shifts:
        c = round(first_strong + k * grid.pulse_sec, 4)
        if c < -0.05:
            continue
        c = max(0.0, c)
        h_fit = _harmonic_fit(notes, grid, c, chord_pcs)
        t_fit, d_fit = _change_fit(notes, grid, c, chord_pcs, duration)
        prior = 1.0 if k == 0 else 0.4  # after silence, a phrase most often starts on beat 1
        score = 0.40 * t_fit + 0.25 * h_fit + 0.20 * d_fit + 0.15 * prior
        scored.append((score, c, h_fit, t_fit, d_fit))
    scored.sort(key=lambda x: (-x[0], abs(x[1] - first_strong)))
    best_score, best, best_fit, best_target, best_down = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    margin = max(0.0, best_score - runner)
    grid_fit = _grid_fit(onsets, grid, best)
    tempo_fit = _tempo_fit(transcription.get("tempo"), grid.bpm)
    covered_loops = (duration - best) / grid.loop_sec if grid.loop_sec else 0.0
    # Confidence: the cues have to agree on one bar phase, and by a clear margin.
    confidence = (
        0.35 * best_score
        + 0.30 * min(1.0, margin / 0.15)
        + 0.20 * grid_fit
        + 0.15 * tempo_fit
    )
    if covered_loops < 0.6:
        confidence *= 0.7  # too little of the span to be sure where it starts
    confidence = round(max(0.0, min(1.0, confidence)), 3)
    return Alignment(
        offset_sec=round(best, 4),
        confidence=confidence,
        source=SOURCE_DETECTED,
        detected_offset_sec=round(best, 4),
        detail={
            "first_strong_onset_sec": round(first_strong, 4),
            "score": round(best_score, 3),
            "harmonic_fit": round(best_fit, 3),
            "change_target_fit": round(best_target, 3),
            "downbeat_fit": round(best_down, 3),
            "runner_up_score": round(runner, 3),
            "margin": round(margin, 3),
            "grid_fit": round(grid_fit, 3),
            "tempo_fit": round(tempo_fit, 3),
            "detected_tempo": transcription.get("tempo"),
            "candidates": [(round(s[0], 3), s[1]) for s in scored[:6]],
        },
    )


def nudge(alignment: Alignment, grid: SpanGrid, *, beats: float = 0.0, bars: float = 0.0) -> Alignment:
    """Move bar 1 by whole beats / bars; becomes a user-adjusted alignment."""
    delta = beats * grid.pulse_sec + bars * grid.bar_sec
    return Alignment(
        offset_sec=round(max(0.0, alignment.offset_sec + delta), 4),
        confidence=alignment.confidence,
        source=SOURCE_ADJUSTED,
        detected_offset_sec=alignment.detected_offset_sec,
        detail=dict(alignment.detail),
    )


def confirm(alignment: Alignment) -> Alignment:
    if alignment.source in (SOURCE_ADJUSTED, SOURCE_LIVE):
        return alignment
    return Alignment(alignment.offset_sec, alignment.confidence, SOURCE_CONFIRMED,
                     alignment.detected_offset_sec, dict(alignment.detail))


def reset(alignment: Alignment) -> Alignment:
    """Back to the app's own start: the live count-in model, or the detection for a file."""
    source = SOURCE_LIVE if "count_in_sec" in (alignment.detail or {}) else SOURCE_DETECTED
    return Alignment(alignment.detected_offset_sec, alignment.confidence, source,
                     alignment.detected_offset_sec, dict(alignment.detail))


def format_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


__all__ = [
    "AUTO_TRUST_CONFIDENCE",
    "Alignment",
    "AssignedEvent",
    "Coverage",
    "SOURCE_ADJUSTED",
    "SOURCE_CONFIRMED",
    "SOURCE_DETECTED",
    "SOURCE_LIVE",
    "SpanGrid",
    "TRUSTED_SOURCES",
    "assign_events",
    "build_grid",
    "confirm",
    "coverage",
    "estimate_upload_alignment",
    "events_in_loop",
    "format_time",
    "live_alignment",
    "nudge",
    "reset",
]
