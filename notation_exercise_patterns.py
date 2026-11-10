"""Technical exercise patterns for the Notation tab.

The Notation tab is a *practice-room exercise builder*, not a second Practice Melody: it writes the
material a player uses to internalise a progression - arpeggios up and down, scales up and down,
sequences in thirds and fourths, and nearest-tone voice leading across the bar line. The shapes are
deliberate and repeatable, which is exactly what makes them unmusical as a melody and useful as an
exercise. Practice Melody keeps its own phrasing, rests and contour and is untouched by this module.

Pitch material reuses the app's existing theory: chord tones from ``music_theory.spell_chord_tones``
and, for scalar patterns, the harmony-aware chord scale from ``chord_scale_selection`` (so a bar of
Am6 runs Dorian and a bar of G7alt runs altered). Register comes from ``instrument_register_fit``, the
same comfortable window Missions and Practice Melodies are fitted to.

Pure Python: no Streamlit, no randomness beyond an explicit seed.
"""

from __future__ import annotations

import random
from typing import Sequence

# Pattern id -> what the musician is practising.
EXERCISE_PATTERNS: dict[str, str] = {
    "arpeggio_up": "Arpeggio ascending",
    "arpeggio_down": "Arpeggio descending",
    "arpeggio_up_down": "Arpeggio up then back down",
    "scale_up": "Scale ascending",
    "scale_down": "Scale descending",
    "scale_up_down": "Scale up then back down",
    "thirds": "Scale in thirds",
    "fourths": "Scale in fourths",
    "voice_leading": "Nearest chord tone (voice leading)",
    "arpeggio_inversions": "Arpeggio through inversions",
    "triplet_sequence": "Scale in three-note groups",
    "four_note_sequence": "Scale in four-note groups",
}

# The two things a musician asks for by name. "auto" keeps today's behaviour, where
# Practice Focus and level choose the drills.
EXERCISE_MODES: tuple[str, ...] = ("auto", "arpeggios", "scales")

MODE_LABELS: dict[str, str] = {
    "auto": "Auto (follow Practice Focus)",
    "arpeggios": "Arpeggios",
    "scales": "Scales",
}

# Choosing a mode must not flatten the levels: each still drills something harder than
# the last, inside the mode the musician asked for.
_MODE_PLANS: dict[str, dict[str, tuple[str, ...]]] = {
    "arpeggios": {
        "Beginner": ("arpeggio_up", "arpeggio_down"),
        "Intermediate": ("arpeggio_up", "arpeggio_down", "arpeggio_up_down"),
        "Advanced": ("arpeggio_up_down", "arpeggio_inversions", "voice_leading"),
    },
    "scales": {
        "Beginner": ("scale_up", "scale_down"),
        "Intermediate": ("scale_up", "scale_down", "scale_up_down", "thirds"),
        "Advanced": ("thirds", "fourths", "triplet_sequence", "four_note_sequence"),
    },
}


def normalize_exercise_mode(mode: str) -> str:
    text = str(mode or "auto").strip().lower()
    return text if text in EXERCISE_MODES else "auto"


# Which patterns each level drills, in the order they cycle through the progression.
_LEVEL_PLANS: dict[str, tuple[str, ...]] = {
    "Beginner": ("arpeggio_up", "arpeggio_down"),
    "Intermediate": ("arpeggio_up", "scale_up", "arpeggio_down", "scale_down"),
    "Advanced": ("arpeggio_up_down", "thirds", "scale_up_down", "fourths", "voice_leading"),
}

# Notes written per bar, by level.
NOTES_PER_BAR: dict[str, int] = {"Beginner": 4, "Intermediate": 6, "Advanced": 8}

# Practice Focus steers which drills the exercise uses, so the Notation tab keeps answering to the
# focus the musician selected (Scales really does drill scales).
_FOCUS_PLANS: dict[str, tuple[str, ...]] = {
    "scales": ("scale_up", "scale_down", "thirds", "fourths"),
    "pentatonics": ("scale_up", "scale_down", "thirds"),
    "guide tones": ("voice_leading", "arpeggio_up", "voice_leading", "arpeggio_down"),
    "arpeggios": ("arpeggio_up", "arpeggio_down", "arpeggio_up_down"),
    "voicings": ("arpeggio_up", "arpeggio_down"),
}


def _focus_plan(focus: str) -> tuple[str, ...] | None:
    text = str(focus or "").strip().lower()
    if not text:
        return None
    for needle, plan in _FOCUS_PLANS.items():
        if needle in text:
            return plan
    return None


def _level(level: str) -> str:
    text = str(level or "Intermediate").strip().title()
    return text if text in _LEVEL_PLANS else "Intermediate"


def pattern_plan(
    level: str,
    n_measures: int,
    *,
    seed: int | None = None,
    focus: str = "",
    mode: str = "auto",
) -> list[str]:
    """One pattern per bar: the drills for this level (or Practice Focus) cycled so the exercise
    keeps changing direction.

    An explicit ``mode`` of "arpeggios" or "scales" is the musician asking directly, so it
    outranks the Practice Focus guess; "auto" leaves today's behaviour alone.
    """
    lvl = _level(level)
    chosen = normalize_exercise_mode(mode)
    if chosen != "auto":
        plan = _MODE_PLANS[chosen][lvl]
    else:
        plan = _focus_plan(focus) or _LEVEL_PLANS[lvl]
    if n_measures <= 0:
        return []
    start = (random.Random(seed).randrange(len(plan))) if seed is not None else 0
    return [plan[(start + i) % len(plan)] for i in range(n_measures)]


def chord_tone_pcs(chord: str, key_center: str = "C") -> list[int]:
    """Ascending pitch classes of the chord's own tones.

    ``spell_chord_tones`` answers with the plain seventh-chord skeleton for every altered
    dominant: C7b5, C7#5, C7alt and C7b9 all come back as C E G Bb. The scale side already
    reads the symbol correctly (C7b5 runs altered), but an arpeggio built from those tones
    would sound a natural fifth the symbol explicitly denies. So the fifth is corrected
    here, from the symbol, without touching the shared speller.

    An explicit b5 or #5 says which fifth to play. A bare "alt" does not, so the natural
    fifth is simply dropped rather than a replacement being invented - root, third and
    seventh are the tones an altered dominant is sure of.
    """
    from music_theory import pitch_class_from_spelled_note, spell_chord_tones

    out: list[int] = []
    for tone in spell_chord_tones(chord) or []:
        pc = pitch_class_from_spelled_note(tone) % 12
        if pc not in out:
            out.append(pc)
    if not out:
        return [0]

    try:
        from chord_scale_selection import _alterations

        alts = _alterations(chord)
    except Exception:
        alts = set()
    if alts & {"b5", "#5", "alt"}:
        root = out[0]
        natural_fifth = (root + 7) % 12
        if natural_fifth in out:
            replacement = None
            if "b5" in alts:
                replacement = (root + 6) % 12
            elif "#5" in alts:
                replacement = (root + 8) % 12
            out = [pc for pc in out if pc != natural_fifth]
            if replacement is not None and replacement not in out:
                out.append(replacement)
    elif alts:
        # Other alteration combinations (b9 with #9, #9 with b13) also imply the fifth is
        # gone, and chord_scale_selection already decides that. Rather than restate its
        # rules here and risk the two drifting apart, defer to the scale it chose: if the
        # natural fifth is not in the chord's own scale, it is not a tone of this chord.
        root = out[0]
        natural_fifth = (root + 7) % 12
        if natural_fifth in out:
            try:
                in_scale = natural_fifth in set(scale_pcs(chord, key_center or "C"))
            except Exception:
                in_scale = True
            if not in_scale:
                out = [pc for pc in out if pc != natural_fifth]
    return out or [0]


def scale_pcs(chord: str, key_center: str = "C") -> list[int]:
    """Pitch classes of the scale that fits this chord in this key (harmony-aware)."""
    try:
        from chord_scale_selection import chord_scale_pcs

        pcs = list(chord_scale_pcs(chord, key_center or "C"))
        if pcs:
            return sorted(set(pcs))
    except Exception:
        pass
    return sorted(set(chord_tone_pcs(chord)))


def _ladder(pcs: Sequence[int], low: int, high: int) -> list[int]:
    """Every pitch of ``pcs`` inside [low, high], ascending."""
    allowed = {int(p) % 12 for p in pcs}
    return [m for m in range(int(low), int(high) + 1) if m % 12 in allowed]


def _walk(ladder: Sequence[int], start_index: int, count: int, step: int, direction: int) -> list[int]:
    """Walk the ladder ``count`` notes, moving ``step`` rungs each time, folding at the ends."""
    if not ladder or count <= 0:
        return []
    out: list[int] = []
    i = max(0, min(int(start_index), len(ladder) - 1))
    d = 1 if direction >= 0 else -1
    for _ in range(count):
        out.append(int(ladder[i]))
        nxt = i + d * max(1, int(step))
        if nxt >= len(ladder) or nxt < 0:
            d = -d                                  # fold back instead of running off the instrument
            nxt = i + d * max(1, int(step))
            nxt = max(0, min(nxt, len(ladder) - 1))
        i = nxt
    return out


def _grouped_walk(
    ladder: Sequence[int], start_index: int, count: int, group: int
) -> list[int]:
    """Overlapping ascending groups: 0 1 2 / 1 2 3 / 2 3 4 ...

    This is what makes a sequence a sequence rather than a plain run - each group starts
    one rung higher than the last, so the shape repeats while the pitch moves.
    """
    if not ladder or group <= 0:
        return []
    out: list[int] = []
    offset = 0
    while len(out) < count:
        base = start_index + offset
        for step in range(group):
            idx = base + step
            if idx < 0 or idx >= len(ladder):
                idx = max(0, min(len(ladder) - 1, idx))
            out.append(ladder[idx])
            if len(out) >= count:
                break
        offset += 1
        if offset > len(ladder) * 2:  # never spin on a one-note ladder
            break
    while len(out) < count:
        out.append(out[-1] if out else ladder[0])
    return out[:count]


def _nearest_index(ladder: Sequence[int], midi: int) -> int:
    if not ladder:
        return 0
    return min(range(len(ladder)), key=lambda i: abs(ladder[i] - int(midi)))


def _start_index(ladder: Sequence[int], anchor: int, count: int, step: int, direction: int) -> int:
    """Where a run should begin so it (a) carries on from the previous bar and (b) actually fits.

    An ascending run started near the top folded back after two notes, which reads as a wobble rather
    than a scale; and because each bar continues from the last, the exercise could march to the extreme
    top of the instrument. The start is therefore pulled back far enough for the whole run to fit, and
    kept inside the middle of the register when the previous bar drifted to an edge.
    """
    if not ladder:
        return 0
    span = max(0, (count - 1) * max(1, int(step)))
    lo_bound, hi_bound = 0, max(0, len(ladder) - 1)
    # Keep the running pitch inside the central two thirds of the register.
    centre_lo = len(ladder) // 6
    centre_hi = max(centre_lo, len(ladder) - 1 - len(ladder) // 6)
    i = _nearest_index(ladder, anchor)
    i = max(centre_lo, min(i, centre_hi))
    if direction >= 0:
        i = min(i, max(lo_bound, hi_bound - span))
    else:
        i = max(i, min(hi_bound, lo_bound + span))
    return max(lo_bound, min(i, hi_bound))


def exercise_measure_midis(
    chord: str,
    *,
    pattern: str,
    key_center: str = "C",
    low: int = 55,
    high: int = 79,
    start_midi: int | None = None,
    count: int = 4,
) -> list[int]:
    """The written pitches for one bar of ``pattern`` on ``chord``, inside [low, high]."""
    count = max(1, int(count))
    tones = _ladder(chord_tone_pcs(chord, key_center), low, high)
    scale = _ladder(scale_pcs(chord, key_center), low, high)
    anchor = int(start_midi) if start_midi is not None else (low + high) // 2

    if pattern in (
        "arpeggio_up", "arpeggio_down", "arpeggio_up_down", "voice_leading",
        "arpeggio_inversions",
    ):
        ladder = tones or scale
    else:
        ladder = scale or tones
    if not ladder:
        return [anchor] * count

    if pattern == "voice_leading":
        # Start on the chord tone nearest the previous note, then outline the chord upward.
        return _walk(ladder, _nearest_index(ladder, anchor), count, 1, +1)
    if pattern == "arpeggio_up":
        return _walk(ladder, _start_index(ladder, anchor, count, 1, +1), count, 1, +1)
    if pattern == "arpeggio_down":
        return _walk(ladder, _start_index(ladder, anchor, count, 1, -1), count, 1, -1)
    if pattern == "scale_up":
        return _walk(ladder, _start_index(ladder, anchor, count, 1, +1), count, 1, +1)
    if pattern == "scale_down":
        return _walk(ladder, _start_index(ladder, anchor, count, 1, -1), count, 1, -1)
    if pattern == "thirds":
        return _walk(ladder, _start_index(ladder, anchor, count, 2, +1), count, 2, +1)
    if pattern == "fourths":
        return _walk(ladder, _start_index(ladder, anchor, count, 3, +1), count, 3, +1)
    if pattern == "arpeggio_inversions":
        # Successive chord tones, not a repeated root-position outline: each group of
        # three starts one chord tone higher than the one before.
        return _grouped_walk(ladder, _nearest_index(ladder, anchor), count, 3)
    if pattern == "triplet_sequence":
        return _grouped_walk(ladder, _nearest_index(ladder, anchor), count, 3)
    if pattern == "four_note_sequence":
        return _grouped_walk(ladder, _nearest_index(ladder, anchor), count, 4)
    if pattern in ("arpeggio_up_down", "scale_up_down"):
        half = max(1, count // 2)
        up = _walk(ladder, _start_index(ladder, anchor, half, 1, +1), half, 1, +1)
        down = _walk(ladder, _nearest_index(ladder, up[-1]), count - half, 1, -1)
        return up + down
    return _walk(ladder, _start_index(ladder, anchor, count, 1, +1), count, 1, +1)


def build_exercise_midis(
    chords: Sequence[str],
    *,
    level: str = "Intermediate",
    instrument: str = "",
    key_center: str = "C",
    low: int | None = None,
    high: int | None = None,
    seed: int | None = None,
    focus: str = "",
    mode: str = "auto",
    register_instrument: str = "",
) -> tuple[list[list[int]], list[str]]:
    """``(midis per bar, pattern per bar)`` for a whole progression.

    Bars are connected: each one starts from the pitch nearest where the previous bar finished, so the
    exercise reads as one continuous study rather than a series of unrelated fragments.
    """
    chords = [str(c or "").strip() or "C" for c in (chords or [])]
    lvl = _level(level)
    if low is None or high is None:
        # The Practice page passes the instrument *family* ("Saxophone"), which resolves
        # to the alto register. A baritone or soprano player needs their own range, so the
        # caller may pass the specific type it already resolved for the written key.
        # Only a name the transposition table actually knows is trusted: an unrecognised
        # one resolves to a generic default profile, which would be a worse answer than
        # the family's own register rather than a better one.
        lo, hi = _register(_known_register_name(register_instrument) or instrument, lvl)
    else:
        lo, hi = int(low), int(high)
    per_bar = NOTES_PER_BAR[lvl]
    plan = pattern_plan(lvl, len(chords), seed=seed, focus=focus, mode=mode)
    out: list[list[int]] = []
    cursor: int | None = None
    for chord, pattern in zip(chords, plan):
        bar = exercise_measure_midis(
            chord, pattern=pattern, key_center=key_center,
            low=lo, high=hi, start_midi=cursor, count=per_bar,
        )
        out.append(bar)
        cursor = bar[-1] if bar else cursor
    return out, plan


def _known_register_name(name: str) -> str:
    """``name`` if the transposition table knows it, else "" so the caller falls back."""
    text = str(name or "").strip()
    if not text:
        return ""
    try:
        from instrument_transposition import TRANSPOSING_SEMITONE_STEPS

        return text if text in TRANSPOSING_SEMITONE_STEPS else ""
    except Exception:
        return ""


def _register(instrument: str, level: str) -> tuple[int, int]:
    try:
        from chord_navigation_notation import instrument_register

        lo, hi, _start = instrument_register(instrument, level)
    except Exception:
        lo, hi = 55, 79
    try:
        from instrument_register_fit import comfortable_written_range

        comfort = comfortable_written_range(instrument, level)
    except Exception:
        comfort = None
    if comfort:
        n_lo, n_hi = max(int(lo), int(comfort[0])), min(int(hi), int(comfort[1]))
        if n_hi - n_lo >= 12:
            lo, hi = n_lo, n_hi
    # An exercise is repeated many times, so it stays in a register the player can sustain: even at
    # Advanced the ceiling is the comfortable *practising* top, not the instrument's performance
    # extreme (an Advanced flute study would otherwise climb to F#7).
    try:
        from instrument_register_fit import comfortable_written_range as _cw

        drill = _cw(instrument, "Intermediate")
    except Exception:
        drill = None
    if drill:
        capped = min(int(hi), int(drill[1]))
        if capped - int(lo) >= 12:
            hi = capped
    return int(lo), int(hi)


def exercise_summary(plan: Sequence[str]) -> str:
    """Human-readable description of what the exercise drills, in bar order."""
    seen: list[str] = []
    for pattern in plan:
        label = EXERCISE_PATTERNS.get(pattern, pattern)
        if label not in seen:
            seen.append(label)
    return " · ".join(seen)


def build_exercise_events(
    chords: Sequence[str],
    *,
    level: str = "Intermediate",
    instrument: str = "",
    key_center: str = "C",
    beats_per_measure: int = 4,
    seed: int | None = None,
    focus: str = "",
    mode: str = "auto",
    register_instrument: str = "",
):
    """``(ArpeggioEvent list, pattern per bar)`` - the exercise as the notation renderer consumes it.

    Reuses ``ArpeggioEvent`` and the existing spelling/ABC pipeline, so an exercise renders through
    exactly the same path as the connected chord-tone line it replaces.
    """
    from chord_navigation_notation import ArpeggioEvent
    from music_theory import spell_note_in_key

    bars, plan = build_exercise_midis(
        chords, level=level, instrument=instrument, key_center=key_center, seed=seed,
        focus=focus, mode=mode, register_instrument=register_instrument,
    )
    lvl = _level(level)
    events = []
    for measure, (chord, midis) in enumerate(zip(chords, bars)):
        if not midis:
            continue
        dur = float(beats_per_measure) / len(midis)
        for i, midi in enumerate(midis):
            # Articulation rises with the level: Beginner plain, Intermediate accents the downbeat,
            # Advanced also detaches the off-beats.
            articulation = ""
            if lvl != "Beginner" and i == 0:
                articulation = "accent"
            elif lvl == "Advanced" and i % 2 == 1:
                articulation = "staccato"
            events.append(
                ArpeggioEvent(
                    chord=str(chord),
                    measure=measure,
                    beat=i * dur,
                    duration_beats=dur,
                    is_rest=False,
                    pitch=spell_note_in_key(int(midi) % 12, key_center or "C"),
                    midi=int(midi),
                    articulation=articulation,
                    slur="start" if (lvl != "Beginner" and i == 0) else ("end" if (lvl != "Beginner" and i == len(midis) - 1) else ""),
                )
            )
    return events, plan


__all__ = [
    "EXERCISE_MODES",
    "MODE_LABELS",
    "normalize_exercise_mode",
    "EXERCISE_PATTERNS",
    "NOTES_PER_BAR",
    "build_exercise_events",
    "build_exercise_midis",
    "chord_tone_pcs",
    "exercise_measure_midis",
    "exercise_summary",
    "pattern_plan",
    "scale_pcs",
]
