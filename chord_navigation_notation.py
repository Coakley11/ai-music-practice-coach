"""Chord-tone / arpeggio navigation exercises for the Practice page's
Notation / TAB tool.

This is deliberately **not** Generated Practice Melody. Practice Melody
composes a melodic line over the changes; this module builds an exercise
that teaches *navigating* the changes themselves -- a connected chord-tone
line (wind/vocal/generic instruments), connected close-position voicings
(piano), or shape-connected fretted positions (guitar, handled separately
in ``practice_notation.py`` since it reuses that module's existing
hand-curated shape data). The through-line for all three: each chord's
realization is chosen to minimize melodic/registral distance from what
came immediately before -- voice leading -- rather than independent
root-position shapes per chord.

Reuses existing infrastructure rather than inventing new ones:
- ``music_theory.spell_chord_tones`` for letter-correct chord-tone names
  (the same spelling the rest of the app uses for chord-tone display).
- ``harmonic_spelling.spell_pitch_classes_for_chord`` for approach/passing
  tones outside the chord, the same helper ``practice_melody_generator.py``
  uses for its own passing/approach tones.
- ``composition_melody_notation.build_abc_from_melody_events`` for the
  melodic-line ABC output -- the same chord-annotated ABC pipeline already
  used by Practice Melody and the existing Notation/TAB tool, so chord
  symbols land above the correct measures the same way everywhere.

Does not resolve or transpose keys itself: callers pass the same
already-projected ``display_key`` (chart/written key) the rest of Practice
already resolved, exactly like Practice Melody does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harmonic_spelling import spell_pitch_classes_for_chord
from music_theory import NOTE_TO_MIDI, classify_chord_quality, normalize_root, spell_chord_tones

VALID_LEVELS = ("Beginner", "Intermediate", "Advanced")

# ---------------------------------------------------------------------------
# Practice Focus conditioning
# ---------------------------------------------------------------------------
# Canonical Practice Focus values (practice_setup_controls.FOCUS_OPTIONS_BY_
# INSTRUMENT / practice_focus_policy.py) that materially change what this
# module generates, normalized from whatever free-text focus label the UI
# passes in. A focus with no dedicated policy here falls back to the plain
# level-driven chord-tone behavior that already existed -- this module never
# invents a second focus *list*, it only recognizes a subset of the existing
# canonical values closely enough to condition generation.
_FOCUS_SCALES = "scales"
_FOCUS_TONE = "tone"
_FOCUS_ARTICULATION = "articulation"
_FOCUS_GUIDE_TONES = "guide_tones"
_FOCUS_DYNAMICS = "dynamics"
_FOCUS_PENTATONICS = "pentatonics"


def normalize_generation_focus(focus: str) -> str:
    f = str(focus or "").strip().lower()
    if "pentaton" in f:
        return _FOCUS_PENTATONICS
    if "guide" in f and "tone" in f:
        return _FOCUS_GUIDE_TONES
    if "scale" in f:
        return _FOCUS_SCALES
    if "articulat" in f:
        return _FOCUS_ARTICULATION
    if "dynamic" in f:
        return _FOCUS_DYNAMICS
    if f == "tone" or f.startswith("tone "):
        return _FOCUS_TONE
    return ""


# Diatonic-ish mode semitone sets used for Scales-focus scalar material,
# keyed by the same quality buckets music_theory.classify_chord_quality
# already produces -- reuses the app's one chord-quality classifier rather
# than re-parsing chord suffixes here.
_SCALE_INTERVALS_BY_QUALITY: dict[str, tuple[int, ...]] = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "maj7": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "m7": (0, 2, 3, 5, 7, 9, 10),  # dorian -- the idiomatic ii-chord scale
    "dom": (0, 2, 4, 5, 7, 9, 10),  # mixolydian
    "half-dim": (0, 1, 3, 5, 6, 8, 10),  # locrian
    "dim": (0, 2, 3, 5, 6, 8, 9, 11),
    "aug": (0, 2, 4, 6, 8, 10),
    "sus": (0, 2, 5, 7, 9),
}

# Pentatonic semitone sets, major and minor, used for Pentatonics-focus
# material. Dominant chords at Advanced level use the major pentatonic a
# fourth above the root (the common "dominant pentatonic" substitution --
# e.g. G7 -> C major pentatonic) instead of the plain root pentatonic used
# at Beginner/Intermediate, giving higher levels a more sophisticated,
# still harmonically valid chord-specific choice.
_MAJOR_PENTATONIC = (0, 2, 4, 7, 9)
_MINOR_PENTATONIC = (0, 3, 5, 7, 10)


def _pool_from_intervals(chord: str, root_pc: int, intervals: tuple[int, ...]) -> list[str]:
    pcs = [(root_pc + iv) % 12 for iv in intervals]
    return spell_pitch_classes_for_chord(pcs, chord, song_display_key="")


def _scale_pool(chord: str) -> list[str]:
    """Stepwise scale pool for Scales-focus material."""
    quality = classify_chord_quality(chord)
    root_pc = _pc_of(chord_root_for_theory_safe(chord))
    intervals = _SCALE_INTERVALS_BY_QUALITY.get(quality, _SCALE_INTERVALS_BY_QUALITY["major"])
    return _pool_from_intervals(chord, root_pc, intervals)


def _pentatonic_pool(chord: str, level_name: str) -> list[str]:
    """Pentatonic pool for Pentatonics-focus material -- chord-aware, not
    one blind scale over the whole progression."""
    quality = classify_chord_quality(chord)
    root_pc = _pc_of(chord_root_for_theory_safe(chord))
    if quality in ("minor", "m7", "half-dim", "dim"):
        return _pool_from_intervals(chord, root_pc, _MINOR_PENTATONIC)
    if quality == "dom" and level_name == "Advanced":
        # Dominant pentatonic: major pentatonic built a fourth above the root.
        return _pool_from_intervals(chord, (root_pc + 5) % 12, _MAJOR_PENTATONIC)
    return _pool_from_intervals(chord, root_pc, _MAJOR_PENTATONIC)


def _guide_tone_pool(chord: str) -> list[str]:
    """3rd/7th (or 3rd/5th for a bare triad) -- the guide-tone pair."""
    tones = spell_chord_tones(chord)
    if len(tones) >= 4:
        return [tones[1], tones[3]]
    if len(tones) >= 3:
        return [tones[1], tones[2]]
    return tones or ["C"]


def chord_root_for_theory_safe(chord: str) -> str:
    from music_theory import chord_root_for_theory

    return chord_root_for_theory(chord) or "C"


def _tone_pool_for_focus(chord: str, focus_key: str, level_name: str) -> list[str]:
    if focus_key == _FOCUS_PENTATONICS:
        return _pentatonic_pool(chord, level_name)
    if focus_key == _FOCUS_SCALES:
        return _scale_pool(chord)
    if focus_key == _FOCUS_GUIDE_TONES:
        return _guide_tone_pool(chord)
    return chord_tone_pool(chord)

# Tones per chord, rhythmic/directional character, and whether an approach
# tone bridges into the next chord -- mirrors the Beginner/Intermediate/
# Advanced differentiation already established for Generated Practice
# Melody, applied here to chord-navigation instead of melodic composition.
LEVEL_PROFILES: dict[str, dict[str, Any]] = {
    "Beginner": {
        "tones_per_chord": 2,
        "direction_changes": False,
        "approach_tones": False,
        "rest_tail": True,
    },
    "Intermediate": {
        "tones_per_chord": 3,
        "direction_changes": True,
        "approach_tones": False,
        "rest_tail": False,
    },
    "Advanced": {
        "tones_per_chord": 4,
        "direction_changes": True,
        "approach_tones": True,
        "rest_tail": False,
    },
}

# Rhythm cells for the wind/brass connected line: (duration_beats, is_rest)
# slots that always sum to a 4-beat bar (scaled for other meters in
# ``_rhythm_pattern``). Picked deterministically by measure index so a
# given progression always produces the same exercise (reproducible for
# practice, and testable), while varying measure to measure instead of one
# identical rhythmic cell repeated for every chord. Beginner patterns stay
# mostly quarter notes with an occasional simple eighth pair and a clear
# breathing-point rest; Intermediate adds real eighth-note movement and
# pickup-like short notes near the end of the bar; Advanced adds syncopated
# off-beat entrances and a shape-making rest.
_BEGINNER_RHYTHMS: tuple[tuple[tuple[float, bool], ...], ...] = (
    ((1.0, False), (1.0, False), (1.0, False), (1.0, False)),
    ((1.0, False), (1.0, False), (2.0, False)),
    ((1.0, False), (1.0, False), (1.0, False), (1.0, True)),
    ((0.5, False), (0.5, False), (1.0, False), (1.0, False), (1.0, False)),
)
_INTERMEDIATE_RHYTHMS: tuple[tuple[tuple[float, bool], ...], ...] = (
    ((0.5, False), (0.5, False), (0.5, False), (0.5, False), (1.0, False), (1.0, False)),
    ((1.0, False), (0.5, False), (0.5, False), (1.0, False), (1.0, False)),
    ((0.5, False), (0.5, False), (1.0, False), (0.5, False), (0.5, False), (1.0, False)),
    ((1.0, False), (1.0, False), (0.5, False), (0.5, False), (1.0, False)),
)
_ADVANCED_RHYTHMS: tuple[tuple[tuple[float, bool], ...], ...] = (
    ((0.5, False), (1.0, False), (0.5, False), (1.0, False), (1.0, False)),
    ((0.5, False), (0.5, False), (0.5, False), (0.5, False), (0.5, False), (0.5, False), (1.0, False)),
    ((1.0, False), (0.5, False), (0.5, False), (0.5, False), (0.5, False), (1.0, False)),
    ((0.5, False), (1.0, False), (1.0, False), (0.5, False), (1.0, False)),
    ((1.0, False), (1.0, False), (0.5, False), (0.5, True), (1.0, False)),
)


def _rhythm_pattern(level_name: str, m_idx: int, beats_per_measure: int) -> list[tuple[float, bool]]:
    """Deterministic (duration, is_rest) slot list for measure *m_idx*,
    scaled so it always sums to exactly *beats_per_measure* -- the F2
    measure-sync invariant (each measure's generated duration must equal
    the authoritative chart duration) holds by construction, not by
    coincidence, because every pool entry already sums to a 4-beat bar."""
    pool = {
        "Beginner": _BEGINNER_RHYTHMS,
        "Intermediate": _INTERMEDIATE_RHYTHMS,
        "Advanced": _ADVANCED_RHYTHMS,
    }.get(level_name, _INTERMEDIATE_RHYTHMS)
    pattern = pool[m_idx % len(pool)]
    scale = float(beats_per_measure) / 4.0
    return [(dur * scale, is_rest) for dur, is_rest in pattern]


# Phrase length (in measures) and "every Nth group left unslurred" for
# mixed articulation, by level. Beginner slurs each short, obvious
# in-measure group; Intermediate and Advanced slur across barlines for
# longer connected phrases, periodically leaving a group plain/tongued so
# the line isn't indiscriminately slurred end to end.
_PHRASE_SHAPE: dict[str, tuple[int, int]] = {
    "Beginner": (1, 0),
    "Intermediate": (2, 3),
    "Advanced": (4, 3),
}


def _phrase_groups(level_name: str, n_measures: int) -> list[tuple[int, int, bool]]:
    """[(start_measure, end_measure_inclusive, is_slurred), ...] covering
    every measure in order."""
    size, skip_every = _PHRASE_SHAPE.get(level_name, (1, 0))
    groups: list[tuple[int, int, bool]] = []
    start = 0
    group_idx = 0
    while start < n_measures:
        end = min(start + size - 1, n_measures - 1)
        slurred = not (skip_every and (group_idx % skip_every == skip_every - 1))
        groups.append((start, end, slurred))
        start = end + 1
        group_idx += 1
    return groups

def _phrase_groups_override(n_measures: int, *, size: int, skip_every: int) -> list[tuple[int, int, bool]]:
    """Same shape as :func:`_phrase_groups` but with an explicit (size,
    skip_every) instead of the level default -- used by Articulation focus
    to force a shorter, more frequently-broken phrase than the player's
    level would otherwise use, for a more pronounced tongued/slurred mix."""
    groups: list[tuple[int, int, bool]] = []
    start = 0
    group_idx = 0
    while start < n_measures:
        end = min(start + size - 1, n_measures - 1)
        slurred = not (skip_every and (group_idx % skip_every == skip_every - 1))
        groups.append((start, end, slurred))
        start = end + 1
        group_idx += 1
    return groups


# Sparse rhythm for Tone focus / Ballad groove: long sustained notes, fewer
# attacks, a comfortable breathing rest -- independent of level, since Tone
# focus means the same thing (fewer events, longer durations) regardless
# of how advanced the player is.
_SPARSE_RHYTHMS: tuple[tuple[tuple[float, bool], ...], ...] = (
    ((4.0, False),),
    ((3.0, False), (1.0, True)),
    ((2.0, False), (2.0, False)),
    ((2.0, False), (1.0, False), (1.0, True)),
)


def _sparse_rhythm_pattern(m_idx: int, beats_per_measure: int) -> list[tuple[float, bool]]:
    pattern = _SPARSE_RHYTHMS[m_idx % len(_SPARSE_RHYTHMS)]
    scale = float(beats_per_measure) / 4.0
    return [(dur * scale, is_rest) for dur, is_rest in pattern]


# Phrase-level dynamic arc for Dynamics focus: a single musical shape over
# the whole section (build toward a climax roughly 2/3 of the way through,
# taper at the end) rather than a different marking every measure.
_DYNAMIC_ARC_SHAPE: tuple[str, ...] = ("mp", "mp", "mf", "f", "f", "mf", "mp", "p")


def _dynamics_arc(n_measures: int) -> dict[int, str]:
    if n_measures <= 1:
        return {0: "mf"}
    out: dict[int, str] = {}
    for m_idx in range(n_measures):
        pos = m_idx / max(1, n_measures - 1)
        shape_idx = min(len(_DYNAMIC_ARC_SHAPE) - 1, int(pos * (len(_DYNAMIC_ARC_SHAPE) - 1)))
        out[m_idx] = _DYNAMIC_ARC_SHAPE[shape_idx]
    return out


PIANO_VOICING_RANGE = (48, 84)  # C3..C6 -- comfortable two-hand-adjacent reading range.

# Semitones the comfortable written register widens on each side per level --
# Beginner stays inside the instrument's own pedagogical "comfortable middle"
# register; higher levels progressively use more of the instrument's real
# playable range while staying inside it (never impossible/unplayable notes).
_LEVEL_REGISTER_EXPANSION: dict[str, int] = {"Beginner": 0, "Intermediate": 3, "Advanced": 6}


def _normalize_level(level: str) -> str:
    text = str(level or "").strip().title()
    return text if text in LEVEL_PROFILES else "Intermediate"


def instrument_register(instrument: str, level: str = "Intermediate") -> tuple[int, int, int]:
    """(midi_low, midi_high, start_midi) for *instrument* at *level*.

    Reuses the AMI per-instrument written-register table
    (``music_coach_ami.notation_profile``, already covering Alto/Tenor/
    Soprano/Bari Sax, Trumpet, Trombone, Tuba, Clarinet, Flute, Piano roles,
    Bass and Guitar) instead of inventing a second range table. Beginner
    uses that profile's own comfortable middle register unchanged; higher
    levels symmetrically widen it, still bounded by real instrument limits.
    """
    from music_coach_ami.notation_profile import notation_profile_for_instrument

    profile = notation_profile_for_instrument(instrument or "")
    expand = _LEVEL_REGISTER_EXPANSION.get(_normalize_level(level), 0)
    lo = max(21, int(profile.midi_low) - expand)
    hi = min(108, int(profile.midi_high) + expand)
    if hi <= lo:
        hi = lo + 12
    start = (lo + hi) // 2
    return lo, hi, start


def _nearest_octave_in_range(pc: int, near_midi: int, lo: int, hi: int) -> int:
    """Nearest MIDI with pitch class *pc* to *near_midi*, octave-shifted to
    stay inside [lo, hi] -- keeps the connected line both voice-led AND
    inside the instrument's playable register. Every register this module
    resolves spans at least an octave, so a representative of *pc* always
    exists in range."""
    candidate = _nearest_octave(pc, near_midi)
    while candidate < lo:
        candidate += 12
    while candidate > hi:
        candidate -= 12
    return candidate


def chord_tone_pool(chord: str) -> list[str]:
    """Letter-spelled root/3rd/5th/7th for *chord* (reuses music_theory)."""
    tones = spell_chord_tones(chord)
    return tones if tones else ["C"]


def _pc_of(name: str) -> int:
    return NOTE_TO_MIDI.get(normalize_root(name), 60) % 12


def _nearest_octave(pc: int, near_midi: int) -> int:
    """Nearest MIDI with pitch class *pc* to *near_midi* -- the voice-leading
    primitive: every successive chord tone is realized as close as possible
    to wherever the line/voicing already is, instead of defaulting to a
    fixed octave per chord."""
    pc = int(pc) % 12
    near_midi = int(near_midi)
    base = (near_midi // 12) * 12 + pc
    candidates = (base - 12, base, base + 12)
    return min(candidates, key=lambda m: abs(m - near_midi))


def _spelled_with_octave(name: str, midi: int) -> str:
    return f"{name}{midi // 12 - 1}"


def validate_events_in_register(events: list["ArpeggioEvent"], lo: int, hi: int) -> None:
    """Hard assertion: no generated pitch may fall outside [lo, hi].

    Called at the end of every chord-navigation generator (item 1: "Add a
    hard validation pass/assertion so generated exercises cannot emit
    notes outside the selected instrument/level policy") so a register
    regression fails loudly in tests/dev instead of quietly shipping an
    unplayable note. The generators themselves never need this to pass --
    every pitch is already produced via ``_nearest_octave_in_range`` -- but
    this is the backstop that proves it, not an assumption of it.
    """
    for ev in events:
        if not ev.is_rest and ev.midi is not None:
            if not (lo <= ev.midi <= hi):
                raise AssertionError(
                    f"generated pitch {ev.midi} (measure {ev.measure}, "
                    f"chord {ev.chord!r}) outside register [{lo}, {hi}]"
                )


@dataclass(frozen=True)
class ArpeggioEvent:
    """One note or rest in a connected chord-tone line."""

    chord: str
    measure: int
    beat: float
    duration_beats: float
    is_rest: bool
    pitch: str | None = None
    midi: int | None = None
    articulation: str = ""  # "", "accent", "staccato", or "tenuto"
    slur: str = ""  # "", "start", "end", or "both"
    dynamic: str = ""  # "", "p", "mp", "mf", "f", "cresc_start", "cresc_end", "dim_start", "dim_end"


def _with_slur(event: "ArpeggioEvent", slur: str) -> "ArpeggioEvent":
    from dataclasses import replace

    return replace(event, slur=slur)


def build_connected_arpeggio_line(
    chords: list[str],
    *,
    level: str = "Intermediate",
    beats_per_measure: int = 4,
    instrument: str = "",
    start_midi: int | None = None,
    focus: str = "",
    groove_style: str = "",
) -> list[ArpeggioEvent]:
    """A single connected melodic line through *chords* for wind/vocal/
    generic (non-piano, non-guitar) instruments -- each chord's tones
    realized at the register nearest the previous note, so the line
    audibly connects one harmony to the next instead of resetting to a
    fixed octave every measure. Register stays inside *instrument*'s
    playable written range for *level* (see ``instrument_register``);
    pass an explicit ``start_midi`` to override the derived register
    midpoint without changing the clamping bounds.

    ``focus`` conditions the generated material when it resolves to one of
    the canonical Practice Focus policies this module recognizes (Scales,
    Tone, Articulation, Guide Tones, Dynamics, Pentatonics) -- the tone
    *vocabulary* changes (scale/pentatonic/guide-tone pool instead of plain
    chord tones) and, for Tone/Articulation/Dynamics, the rhythm/slur/
    dynamic-marking choices change too, but the underlying voice-leading,
    register-clamping and F2 measure-duration invariants are untouched: an
    unrecognized or empty focus reproduces the original plain behavior
    exactly. ``groove_style`` lets the song's own canonical feel (e.g. a
    Ballad's sustained, sparse phrasing) bias rhythm the same way Tone
    focus does, independent of whether Tone is the selected focus."""
    focus_key = normalize_generation_focus(focus)
    sparse_groove = "ballad" in str(groove_style or "").lower()
    profile = LEVEL_PROFILES[_normalize_level(level)]
    level_name = _normalize_level(level)
    reg_lo, reg_hi, reg_start = instrument_register(instrument, level)
    n_measures = len(chords)

    # Phase 1: decide each measure's tone order (contour) up front.
    # Entry tone is whichever chord tone sits nearest the line's current
    # position -- a genuine nearest chord-tone connection -- instead of
    # always restarting on the root. direction_changes alternates ascending
    #/descending every other measure for Intermediate+; a register-boundary
    # redirect additionally forces an early reversal (item 1: turn around /
    # invert instead of clipping) whenever the previewed line would end
    # within 2 semitones of either register edge.
    ordered_tones_by_measure: list[list[str]] = []
    reverse_flag = False
    preview_midi = int(start_midi) if start_midi is not None else int(reg_start)
    for m_idx, chord in enumerate(chords):
        tones = _tone_pool_for_focus(chord, focus_key, level_name)
        n = min(int(profile["tones_per_chord"]), len(tones)) if focus_key != _FOCUS_SCALES else len(tones)
        entry_idx = min(
            range(len(tones)),
            key=lambda i: abs(_nearest_octave(_pc_of(tones[i]), preview_midi) - preview_midi),
        )
        ordered = [tones[(entry_idx + i) % len(tones)] for i in range(n)]
        want_reverse = reverse_flag
        if profile["direction_changes"] and m_idx % 2 == 1:
            want_reverse = not want_reverse
        if want_reverse:
            ordered = list(reversed(ordered))
        ordered_tones_by_measure.append(ordered)
        cursor = preview_midi
        for tone in ordered:
            cursor = _nearest_octave_in_range(_pc_of(tone), cursor, reg_lo, reg_hi)
        reverse_flag = (cursor - reg_lo) <= 2 or (reg_hi - cursor) <= 2
        preview_midi = cursor

    # Phrase/slur plan (item 3): which measure spans are one slurred
    # phrase, by level -- computed once so slur start/end can be stamped
    # onto the first/last *sounded* event of each span below. Articulation
    # focus asks for a *more* pronounced tongued/slurred mixture, not more
    # slurring overall, so it shortens the phrase span and breaks plain
    # more often than the level default rather than lengthening slurs.
    if focus_key == _FOCUS_ARTICULATION:
        phrase_groups = _phrase_groups_override(n_measures, size=2, skip_every=2)
    else:
        phrase_groups = _phrase_groups(level_name, n_measures)
    slur_start_measures = {start for start, _end, slurred in phrase_groups if slurred}
    slur_end_measures = {end for _start, end, slurred in phrase_groups if slurred}
    dynamic_by_measure = _dynamics_arc(n_measures) if focus_key == _FOCUS_DYNAMICS else {}

    events: list[ArpeggioEvent] = []
    prev_midi = int(start_midi) if start_midi is not None else int(reg_start)
    for m_idx, chord in enumerate(chords):
        ordered_tones = ordered_tones_by_measure[m_idx]
        if focus_key == _FOCUS_TONE or sparse_groove:
            pattern = _sparse_rhythm_pattern(m_idx, beats_per_measure)
        else:
            pattern = _rhythm_pattern(level_name, m_idx, beats_per_measure)
        has_next = m_idx + 1 < n_measures
        use_approach = bool(profile["approach_tones"]) and has_next and len(pattern) > 1
        n_slots = len(pattern)

        tone_cursor = 0
        cursor_midi = prev_midi
        measure_events: list[ArpeggioEvent] = []
        beat_cursor = 0.0
        for slot_i, (dur, is_rest) in enumerate(pattern):
            is_last_slot = slot_i == n_slots - 1
            if is_rest and not (use_approach and is_last_slot):
                measure_events.append(
                    ArpeggioEvent(
                        chord=chord, measure=m_idx, beat=beat_cursor,
                        duration_beats=dur, is_rest=True,
                    )
                )
                beat_cursor += dur
                continue
            if use_approach and is_last_slot:
                # Chromatic approach tone (item 2/4): a quick connecting
                # gesture that targets whichever tone the *next* measure
                # actually enters on, not always that chord's root.
                next_first_tone = ordered_tones_by_measure[m_idx + 1][0]
                target = _nearest_octave_in_range(_pc_of(next_first_tone), cursor_midi, reg_lo, reg_hi)
                approach_midi = target - 1 if target >= cursor_midi else target + 1
                approach_midi = max(reg_lo, min(reg_hi, approach_midi))
                approach_name = spell_pitch_classes_for_chord(
                    [approach_midi % 12], chord, song_display_key=""
                )[0]
                measure_events.append(
                    ArpeggioEvent(
                        chord=chord, measure=m_idx, beat=beat_cursor,
                        duration_beats=dur, is_rest=False,
                        pitch=approach_name, midi=approach_midi,
                        articulation="staccato",
                    )
                )
                cursor_midi = approach_midi
                beat_cursor += dur
                continue
            # Cycle through this chord's chosen tones to fill however many
            # rhythm slots the measure needs (natural arpeggio repetition
            # when there are more slots than distinct tones) -- the line
            # never independently restarts on the root each chord.
            tone = ordered_tones[tone_cursor % len(ordered_tones)]
            tone_cursor += 1
            realized = _nearest_octave_in_range(_pc_of(tone), cursor_midi, reg_lo, reg_hi)
            # Articulation: the arrival note on each new harmony is the
            # natural emphasis point, so it gets a light accent from
            # Intermediate up (Beginner stays unmarked for the simplest
            # possible reading). Articulation focus asks for a richer,
            # more varied mixture, so it also alternates tenuto on
            # mid-measure arrivals instead of leaving them unmarked.
            if focus_key == _FOCUS_ARTICULATION:
                if slot_i == 0:
                    articulation = "accent"
                elif slot_i % 2 == 0:
                    articulation = "tenuto"
                else:
                    articulation = "staccato" if slot_i == n_slots - 1 else ""
            else:
                articulation = "accent" if slot_i == 0 and level_name != "Beginner" else ""
            dynamic = dynamic_by_measure.get(m_idx, "") if slot_i == 0 else ""
            measure_events.append(
                ArpeggioEvent(
                    chord=chord, measure=m_idx, beat=beat_cursor,
                    duration_beats=dur, is_rest=False,
                    pitch=tone, midi=realized, articulation=articulation,
                    dynamic=dynamic,
                )
            )
            cursor_midi = realized
            beat_cursor += dur

        sounded_idx = [i for i, e in enumerate(measure_events) if not e.is_rest]
        if sounded_idx:
            if m_idx in slur_start_measures:
                i = sounded_idx[0]
                measure_events[i] = _with_slur(measure_events[i], "start")
            if m_idx in slur_end_measures:
                i = sounded_idx[-1]
                prior = measure_events[i]
                measure_events[i] = _with_slur(prior, "both" if prior.slur == "start" else "end")

        events.extend(measure_events)
        prev_midi = cursor_midi

    validate_events_in_register(events, reg_lo, reg_hi)
    return events


def bass_groove_style(groove_style: str) -> str:
    """Map a resolved Practice groove/feel to a bass-line pattern family.

    The bass study must follow the song's own authoritative feel (a swing
    tune earns a walking-style line, a Pop tune does not) rather than
    defaulting to one generic bass treatment regardless of groove."""
    g = (groove_style or "").lower()
    if "swing" in g or "jazz" in g or "bebop" in g:
        return "walking"
    if "bossa" in g or "latin" in g or "samba" in g:
        return "latin"
    if "ballad" in g:
        return "ballad"
    return "straight"


def build_bass_line(
    chords: list[str],
    *,
    level: str = "Intermediate",
    groove_style: str = "",
    beats_per_measure: int = 4,
    start_midi: int | None = None,
    focus: str = "",
) -> list[ArpeggioEvent]:
    """An actual bass-line study over *chords* -- not the wind/vocal
    arpeggio engine rendered in bass clef. Beginner anchors on roots and
    fifths at strong beats; Intermediate adds thirds/sevenths, passing and
    approach tones; Advanced produces a real connected line (walking
    quarter notes for swing/jazz grooves, a syncopated pattern for Latin/
    bossa grooves, a sustained arpeggiated line for ballads, a driving
    root/fifth/octave pattern otherwise) that voice-leads into the next
    chord's root, matching the song's own resolved groove rather than
    forcing a walking jazz line onto a Pop tune or vice versa.

    ``focus``: Guide Tones biases the line's secondary tone toward the 7th
    (3rd+7th guide-tone pair) instead of 3rd+5th; Pentatonics substitutes a
    chord-aware pentatonic passing step for the plain 3rd; Dynamics stamps
    a phrase-level dynamic arc onto each measure's downbeat. Unrecognized/
    empty focus reproduces the original root/3rd/5th/7th plan exactly."""
    style = bass_groove_style(groove_style)
    lvl = _normalize_level(level)
    focus_key = normalize_generation_focus(focus)
    reg_lo, reg_hi, reg_start = instrument_register("Bass", level)
    events: list[ArpeggioEvent] = []
    n = len(chords)
    prev_midi = int(start_midi) if start_midi is not None else int(reg_start)
    dynamic_by_measure = _dynamics_arc(n) if focus_key == _FOCUS_DYNAMICS else {}

    def tone_or(tones: list[str], idx: int) -> str:
        return tones[idx] if idx < len(tones) else tones[0]

    def realize(name: str, near: int) -> int:
        return _nearest_octave_in_range(_pc_of(name), near, reg_lo, reg_hi)

    def chromatic_approach(target_pc: int, near: int) -> int:
        target = _nearest_octave_in_range(target_pc, near, reg_lo, reg_hi)
        step = target - 1 if target >= near else target + 1
        return max(reg_lo, min(reg_hi, step))

    def spell(name_hint: str, midi_val: int, chord: str) -> str:
        if _pc_of(name_hint) == midi_val % 12:
            return name_hint
        return spell_pitch_classes_for_chord([midi_val % 12], chord, song_display_key="")[0]

    for m_idx, chord in enumerate(chords):
        tones = chord_tone_pool(chord)
        root, third, fifth, seventh = (
            tone_or(tones, 0), tone_or(tones, 1), tone_or(tones, 2), tone_or(tones, 3)
        )
        if focus_key == _FOCUS_GUIDE_TONES:
            fifth = seventh  # bias the secondary tone toward the guide-tone pair (3rd + 7th)
        elif focus_key == _FOCUS_PENTATONICS:
            penta = _pentatonic_pool(chord, lvl)
            if len(penta) >= 2:
                third = penta[1]  # a chord-aware pentatonic passing step, not the plain 3rd
        next_chord = chords[m_idx + 1] if m_idx + 1 < n else None
        next_root_pc = _pc_of(chord_tone_pool(next_chord)[0]) if next_chord else None

        root_midi = realize(root, prev_midi)
        # plan: list of (name_hint, midi, beat, duration, is_rest)
        plan: list[tuple[str, int, float, float, bool]] = []

        if lvl == "Beginner":
            fifth_midi = realize(fifth, root_midi)
            plan = [(root, root_midi, 0.0, 2.0, False), (fifth, fifth_midi, 2.0, 2.0, False)]
            cursor = fifth_midi
        elif lvl == "Intermediate":
            third_midi = realize(third, root_midi)
            fifth_midi = realize(fifth, third_midi)
            if style == "walking":
                tail = realize(next_root_pc, fifth_midi) if next_root_pc is not None else realize(seventh, fifth_midi)
                plan = [
                    (root, root_midi, 0.0, 1.0, False),
                    (third, third_midi, 1.0, 1.0, False),
                    (fifth, fifth_midi, 2.0, 1.0, False),
                    ("", tail, 3.0, 1.0, False),
                ]
                cursor = tail
            elif style == "latin":
                plan = [
                    (root, root_midi, 0.0, 1.0, False),
                    ("", 0, 1.0, 0.5, True),
                    (fifth, fifth_midi, 1.5, 0.5, False),
                    (root, root_midi, 2.0, 1.0, False),
                    (fifth, fifth_midi, 3.0, 1.0, False),
                ]
                cursor = fifth_midi
            elif style == "ballad":
                plan = [(root, root_midi, 0.0, 2.0, False), (third, third_midi, 2.0, 2.0, False)]
                cursor = third_midi
            else:
                plan = [
                    (root, root_midi, 0.0, 1.0, False),
                    (fifth, fifth_midi, 1.0, 1.0, False),
                    (root, root_midi, 2.0, 1.0, False),
                    (fifth, fifth_midi, 3.0, 1.0, False),
                ]
                cursor = fifth_midi
        else:  # Advanced
            third_midi = realize(third, root_midi)
            fifth_midi = realize(fifth, third_midi)
            seventh_midi = realize(seventh, fifth_midi)
            if style == "walking":
                approach = (
                    chromatic_approach(next_root_pc, seventh_midi)
                    if next_root_pc is not None
                    else seventh_midi
                )
                plan = [
                    (root, root_midi, 0.0, 1.0, False),
                    (third, third_midi, 1.0, 1.0, False),
                    (fifth, fifth_midi, 2.0, 1.0, False),
                    ("", approach, 3.0, 1.0, False),
                ]
                cursor = approach
            elif style == "latin":
                octave_midi = realize(root, fifth_midi)
                plan = [
                    (root, root_midi, 0.0, 1.0, False),
                    ("", 0, 1.0, 0.5, True),
                    (fifth, fifth_midi, 1.5, 0.5, False),
                    (root, octave_midi, 2.0, 1.0, False),
                    (fifth, fifth_midi, 3.0, 1.0, False),
                ]
                cursor = fifth_midi
            elif style == "ballad":
                plan = [
                    (root, root_midi, 0.0, 1.5, False),
                    (third, third_midi, 1.5, 1.0, False),
                    (fifth, fifth_midi, 2.5, 1.5, False),
                ]
                cursor = fifth_midi
            else:
                octave_midi = realize(root, fifth_midi)
                plan = [
                    (root, root_midi, 0.0, 1.0, False),
                    (fifth, fifth_midi, 1.0, 1.0, False),
                    (root, octave_midi, 2.0, 1.0, False),
                    (fifth, fifth_midi, 3.0, 1.0, False),
                ]
                cursor = fifth_midi

        for name_hint, midi_val, beat, dur, is_rest in plan:
            if is_rest:
                events.append(
                    ArpeggioEvent(
                        chord=chord, measure=m_idx, beat=beat, duration_beats=dur, is_rest=True
                    )
                )
                continue
            spelled = spell(name_hint, midi_val, chord) if name_hint else spell_pitch_classes_for_chord(
                [midi_val % 12], chord, song_display_key=""
            )[0]
            events.append(
                ArpeggioEvent(
                    chord=chord,
                    measure=m_idx,
                    beat=beat,
                    duration_beats=dur,
                    is_rest=False,
                    pitch=spelled,
                    midi=midi_val,
                    dynamic=dynamic_by_measure.get(m_idx, "") if beat == 0.0 else "",
                )
            )
        prev_midi = cursor
    validate_events_in_register(events, reg_lo, reg_hi)
    return events


def arpeggio_events_to_melody_dicts(events: list[ArpeggioEvent]) -> list[dict[str, Any]]:
    """Adapt to the ``{pitch, is_rest, duration_beats}`` shape
    ``composition_melody_notation.build_abc_from_melody_events`` expects --
    the same adapter shape ``practice_melody_notation.py`` uses, so both
    tools render through the identical ABC pipeline."""
    out: list[dict[str, Any]] = []
    for ev in events:
        out.append(
            {
                "pitch": _spelled_with_octave(ev.pitch, ev.midi) if not ev.is_rest and ev.pitch else "rest",
                "is_rest": ev.is_rest,
                "duration_beats": ev.duration_beats,
                "articulation": ev.articulation,
                "slur": ev.slur,
                "dynamic": ev.dynamic,
            }
        )
    return out


@dataclass(frozen=True)
class VoicingEvent:
    """One connected close-position chord voicing hit (piano).

    ``beat``/``duration_beats`` place this hit within its measure -- a
    measure may contain several ``VoicingEvent``s (comping rhythm) rather
    than always exactly one whole-measure chord."""

    chord: str
    measure: int
    pitches: tuple[str, ...]
    midis: tuple[int, ...]
    beat: float = 0.0
    duration_beats: float = 4.0


# Comping rhythm cells (beat durations summing to a 4-beat bar, scaled for
# other meters): Beginner mostly holds one voicing per measure with an
# occasional simple re-strike; Intermediate adds real rhythmic comping
# (syncopated re-attacks, not one static block chord); Advanced adds
# busier, more syncopated comping patterns.
_BEGINNER_COMP_PATTERNS: tuple[tuple[float, ...], ...] = (
    (4.0,),
    (2.0, 2.0),
    (4.0,),
)
_INTERMEDIATE_COMP_PATTERNS: tuple[tuple[float, ...], ...] = (
    (1.5, 1.5, 1.0),
    (2.0, 1.0, 1.0),
    (1.0, 1.0, 2.0),
    (1.5, 1.0, 1.5),
)
_ADVANCED_COMP_PATTERNS: tuple[tuple[float, ...], ...] = (
    (1.5, 0.5, 1.0, 1.0),
    (1.0, 0.5, 0.5, 1.0, 1.0),
    (0.5, 1.5, 1.0, 1.0),
    (1.5, 1.5, 0.5, 0.5),
)


def _comp_pattern(level_name: str, m_idx: int, beats_per_measure: int) -> list[float]:
    pool = {
        "Beginner": _BEGINNER_COMP_PATTERNS,
        "Intermediate": _INTERMEDIATE_COMP_PATTERNS,
        "Advanced": _ADVANCED_COMP_PATTERNS,
    }.get(level_name, _INTERMEDIATE_COMP_PATTERNS)
    pattern = pool[m_idx % len(pool)]
    scale = float(beats_per_measure) / 4.0
    return [d * scale for d in pattern]


def _chord_supports_added_9th(chord: str) -> bool:
    """True for plain 7th-type chords (maj7/min7/dom7/m7b5 etc.) where an
    added 9th is harmonically idiomatic -- false for plain triads (no 7th
    to extend from) and for chords that already name an extension/
    alteration (9/11/13/alt/sus), where guessing a 9th could clash."""
    head = str(chord or "").split("/", 1)[0]
    low = head.lower()
    if any(tag in low for tag in ("9", "11", "13", "alt", "sus", "add")):
        return False
    return "7" in low


def build_connected_piano_voicings(
    chords: list[str],
    *,
    level: str = "Intermediate",
    start_center: int = 64,
    focus: str = "",
    groove_style: str = "",
) -> list[VoicingEvent]:
    """Each chord realized as a close-position voicing chosen to minimize
    registral movement from the *previous* voicing -- "closest voicing"
    connection, not independent root-position stacks per chord. Advanced
    adds a 9th on top of plain 7th-type chords where harmonically
    idiomatic (not on bare triads, not on chords that already name their
    own extension/alteration).

    Guide Tones focus narrows the voicing to just the 3rd/7th shell (the
    standard jazz-piano guide-tone exercise); a Ballad groove uses the
    sparsest comping pattern regardless of level, matching that groove's
    own sustained, unhurried feel."""
    level_name = _normalize_level(level)
    focus_key = normalize_generation_focus(focus)
    sparse_groove = "ballad" in str(groove_style or "").lower()
    profile = LEVEL_PROFILES[level_name]
    n_tones = 3 if level_name == "Beginner" else min(4, int(profile["tones_per_chord"]) + 1)
    expand = _LEVEL_REGISTER_EXPANSION.get(level_name, 0)
    lo, hi = PIANO_VOICING_RANGE
    lo, hi = lo - expand, hi + expand
    events: list[VoicingEvent] = []
    prev_midis: list[int] = []
    for m_idx, chord in enumerate(chords):
        if focus_key == _FOCUS_GUIDE_TONES:
            tones = _guide_tone_pool(chord)
        else:
            tones = chord_tone_pool(chord)[:n_tones]
        if focus_key != _FOCUS_GUIDE_TONES and level_name == "Advanced" and _chord_supports_added_9th(chord):
            root_pc = _pc_of(tones[0])
            ninth_pc = (root_pc + 2) % 12
            ninth_name = spell_pitch_classes_for_chord([ninth_pc], chord, song_display_key="")[0]
            tones = [*tones, ninth_name]
        if not prev_midis:
            midis: list[int] = []
            cursor = start_center - 6
            for tone in tones:
                realized = _nearest_octave(_pc_of(tone), cursor)
                while midis and realized <= midis[-1]:
                    realized += 12
                midis.append(realized)
                cursor = realized
        else:
            ref = int(round(sum(prev_midis) / len(prev_midis)))
            midis = sorted(_nearest_octave(_pc_of(tone), ref) for tone in tones)
            for i in range(1, len(midis)):
                while midis[i] <= midis[i - 1]:
                    midis[i] += 12
        midis = [max(lo, min(hi, m)) for m in midis]
        pitches = tuple(_spelled_with_octave(t, m) for t, m in zip(tones, midis))
        # Comping rhythm (item 9: "beyond one vertical chord per measure"):
        # the SAME voice-led voicing is re-articulated on this measure's
        # comping pattern rather than struck once and held -- the harmonic
        # content stays clean (no ad hoc passing dissonance stacked into a
        # vertical sonority), the rhythm is what varies by level.
        pattern = [4.0] if sparse_groove else _comp_pattern(level_name, m_idx, 4)
        beat_cursor = 0.0
        for dur in pattern:
            events.append(
                VoicingEvent(
                    chord=chord, measure=m_idx, pitches=pitches,
                    midis=tuple(midis), beat=beat_cursor, duration_beats=dur,
                )
            )
            beat_cursor += dur
        prev_midis = midis
    return events


def build_piano_voicing_abc(
    events: list[VoicingEvent],
    *,
    key: str,
    meter: str = "4/4",
    bpm: int = 96,
    title: str = "Chord navigation",
) -> str:
    """ABC text for connected piano voicings. A measure may hold several
    comping hits (see ``_comp_pattern``) rather than always exactly one
    whole-measure voicing; the chord symbol is placed above each measure's
    first hit only, same chord-annotation convention (``"Chord"[notes]``)
    abcjs already renders for every other notation path in this app."""
    from composition_hum_transcription import parse_meter
    from composition_melody_notation import composition_abc_key_field
    from music_theory import abc_pitch_for_spelled_note

    num, den = parse_meter(meter)
    k_field = composition_abc_key_field(key)

    def _voicing_token(pitches: tuple[str, ...]) -> str:
        toks = []
        for p in pitches:
            i = len(p) - 1
            while i >= 0 and p[i].isdigit():
                i -= 1
            name, octave_str = p[: i + 1] or "C", p[i + 1 :]
            try:
                octave = int(octave_str)
            except ValueError:
                octave = 4
            toks.append(abc_pitch_for_spelled_note(name, octave=octave, k_field=k_field))
        return "[" + "".join(toks) + "]"

    def _length_token(duration_beats: float) -> str:
        eighths = max(1, int(round(float(duration_beats) * 2)))
        return str(eighths) if eighths != 1 else ""

    measures: dict[int, list[VoicingEvent]] = {}
    for ev in events:
        measures.setdefault(ev.measure, []).append(ev)

    bars: list[str] = []
    for m_idx in sorted(measures):
        hits = sorted(measures[m_idx], key=lambda e: e.beat)
        toks = []
        for hit_i, ev in enumerate(hits):
            prefix = f'"{ev.chord}"' if hit_i == 0 else ""
            toks.append(f"{prefix}{_voicing_token(ev.pitches)}{_length_token(ev.duration_beats)}")
        bars.append(" ".join(toks))
    music = " | ".join(bars) + " |" if bars else "z4 |"
    return f"""X:1
T:{title}
M:{num}/{den}
L:1/8
Q:1/4={int(bpm)}
K:{k_field}
{music}"""
