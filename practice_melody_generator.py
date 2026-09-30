"""Generation engine for Practice Melody.

Composes a new, song-specific practice melody for an existing Catalog/Custom
song's chart — NOT a generic improvisation generator, and NOT a
reconstruction/approximation of any copyrighted original melody. The
generator only ever reads **chord symbols, key, meter, tempo and section
structure** that the app already owns for the song; it has no access to,
and never receives, any actual recorded/transcribed melody data. That is a
structural guarantee against reproducing a real song's melody, not just a
policy statement.

This module is independent of:
  * ``improvisation_motif.py`` / ``motif_engine.py`` — the Motif/Phrase
    pattern-vocabulary system, which generates short improvisation patterns
    with no bar/beat timeline. Practice Melody is a *composed, whole-song*
    melody with an explicit measure/beat structure (see
    ``practice_melody_model.py``).
  * ``composition_melody_suggestions.py`` — Composition Studio's melody
    generator for songs a user is *writing*. Practice Melody generates over
    an existing chart the user is *rehearsing*.

It reuses existing low-level theory primitives rather than duplicating
theory logic: ``music_theory.spell_chord_tones`` for chord-tone pitch
classes, ``harmonic_spelling.spell_pitch_classes_for_chord`` for key/chord-
aware note spelling, and ``practice_studio.practice_section_type`` for
section-type normalization. It does not resolve or own a key — the caller
supplies ``key_center`` (from ``songs/key_state.py``'s resolver).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import replace

from harmonic_spelling import spell_pitch_classes_for_chord
from music_theory import pitch_class_from_spelled_note, spell_chord_tones, split_key_center
from practice_melody_model import MelodyEvent, MelodySection, PracticeMelody, SCHEMA_VERSION

try:
    from practice_studio import practice_section_type
except ImportError:  # pragma: no cover - defensive fallback if practice_studio's
    # heavier Streamlit-adjacent imports are ever unavailable in a minimal context.
    import re as _re

    _TRAIL = _re.compile(r"\s+\d+[A-Za-z]?\s*$")

    def practice_section_type(section_name: str | None) -> str:  # type: ignore[misc]
        s = str(section_name or "").strip()
        return _TRAIL.sub("", s).strip() or s


GENERATOR_VERSION = "practice-melody-gen-1"

_MAJOR_SCALE_STEPS = (0, 2, 4, 5, 7, 9, 11)
_MINOR_SCALE_STEPS = (0, 2, 3, 5, 7, 8, 10)

# Comfortable register per level (MIDI). Advanced gets a wider window but all
# three stay in a singable range — this is a *practice* melody, not an
# instrumental solo.
_LEVEL_RANGE: dict[str, tuple[int, int]] = {
    "Beginner": (60, 74),       # C4 - D5
    "Intermediate": (57, 77),   # A3 - F5
    "Advanced": (55, 81),       # G3 - A5
}
_MAX_LEAP_SEMITONES: dict[str, int] = {
    "Beginner": 7,        # perfect 5th ceiling
    "Intermediate": 9,    # major 6th
    "Advanced": 12,       # octave, with step-back-on-landing pitch selection
}
_PASSING_TONE_PROB: dict[str, float] = {
    "Beginner": 0.05,
    "Intermediate": 0.30,
    "Advanced": 0.50,
}
_CHROMATIC_APPROACH_PROB: dict[str, float] = {
    "Beginner": 0.0,
    "Intermediate": 0.05,
    "Advanced": 0.18,
}
_START_MIDI: dict[str, int] = {"Beginner": 67, "Intermediate": 65, "Advanced": 64}

# Rhythm archetypes are expressed in quarter-note beats and always sum to
# exactly 4.0; ``_fit_archetype_to_measure`` scales them to the section's
# actual ``beats_per_measure`` so the same vocabulary works for other meters.
_SPARSE_ARCHETYPES: tuple[tuple[tuple[float, bool], ...], ...] = (
    ((4.0, False),),
    ((2.0, False), (2.0, False)),
    ((2.0, False), (1.0, False), (1.0, False)),
    ((1.0, False), (1.0, False), (2.0, False)),
    ((2.0, False), (1.0, True), (1.0, False)),
    ((1.0, True), (1.0, False), (2.0, False)),
    ((3.0, False), (1.0, False)),
)
_BEGINNER_ARCHETYPES = _SPARSE_ARCHETYPES + (
    ((1.0, False), (1.0, False), (1.0, False), (1.0, False)),
    ((1.0, False), (0.5, False), (0.5, False), (1.0, False), (1.0, False)),
    ((1.0, True), (1.0, False), (1.0, False), (1.0, False)),
)
_INTERMEDIATE_ARCHETYPES = _SPARSE_ARCHETYPES + (
    ((0.5, False),) * 8,
    ((1.0, False), (0.5, False), (0.5, False), (1.0, False), (1.0, False)),
    ((0.5, False), (0.5, False), (1.0, False), (0.5, False), (0.5, False), (1.0, False)),
    ((1.5, False), (0.5, False), (1.0, False), (1.0, False)),
    ((1.0, False), (1.0, False), (0.5, False), (0.5, False), (1.0, False)),
    ((0.5, True), (0.5, False), (1.0, False), (1.0, False), (1.0, False)),
    ((2.0, False), (0.5, False), (0.5, False), (1.0, False)),
)
_ADVANCED_ARCHETYPES = _SPARSE_ARCHETYPES + (
    ((0.5, False),) * 6 + ((1.0, False),),
    ((0.25, False), (0.25, False), (0.5, False), (1.0, False), (1.0, False), (1.0, False)),
    ((0.5, False), (1.0, False), (0.5, False), (1.0, False), (1.0, False)),
    ((1.5, False), (0.5, False), (0.5, False), (0.5, False), (1.0, False)),
    ((0.5, False), (0.25, False), (0.25, False), (0.5, False), (0.5, False), (1.0, False), (1.0, False)),
    ((0.5, True), (0.5, False), (0.5, False), (0.5, False), (1.0, False), (1.0, False)),
)
_LEVEL_ARCHETYPES: dict[str, tuple[tuple[tuple[float, bool], ...], ...]] = {
    "Beginner": _BEGINNER_ARCHETYPES,
    "Intermediate": _INTERMEDIATE_ARCHETYPES,
    "Advanced": _ADVANCED_ARCHETYPES,
}

# Keeps tempo/style musically important (per the brief): a slow, lyrical song
# stays spacious even at Advanced level instead of turning into continuous
# fast notes just because the level is high.
_SLOW_TEMPO_BPM = 84.0
_SPARSE_BIAS_AT_SLOW_TEMPO = 0.55


def _seed_for(song_id: str, level: str, alt_index: int, explicit_seed: int | None) -> int:
    if explicit_seed is not None:
        return int(explicit_seed)
    digest = hashlib.sha256(f"{song_id}|{level}|{alt_index}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _melody_id(song_id: str, level: str, alt_index: int, seed: int) -> str:
    return f"pm:{song_id}:{level.lower()}:{alt_index}:{seed:x}"


def _diatonic_scale_pcs(key_center: str) -> list[int]:
    tonic, mode = split_key_center(key_center)
    tonic_pc = pitch_class_from_spelled_note(tonic)
    steps = _MINOR_SCALE_STEPS if mode == "minor" else _MAJOR_SCALE_STEPS
    return [(tonic_pc + s) % 12 for s in steps]


def _chord_tone_pcs(chord: str) -> list[int]:
    tones = spell_chord_tones(chord)
    pcs: list[int] = []
    for tone in tones:
        pc = pitch_class_from_spelled_note(tone)
        if pc not in pcs:
            pcs.append(pc)
    return pcs or [0]


def _pick_archetype(level: str, tempo_bpm: float, rng: random.Random) -> tuple[tuple[float, bool], ...]:
    pool = _LEVEL_ARCHETYPES[level]
    if tempo_bpm and tempo_bpm < _SLOW_TEMPO_BPM and rng.random() < _SPARSE_BIAS_AT_SLOW_TEMPO:
        pool = _SPARSE_ARCHETYPES
    return rng.choice(pool)


def _fit_archetype_to_measure(
    archetype: tuple[tuple[float, bool], ...], beats_per_measure: float
) -> list[tuple[float, bool]]:
    scale = beats_per_measure / 4.0
    return [(round(dur * scale, 6), is_rest) for dur, is_rest in archetype]


def _closest_midi_for_pc(target_pc: int, prev_midi: int, low: int, high: int) -> int:
    best: int | None = None
    best_dist: int | None = None
    for octave_shift in range(-2, 3):
        candidate = prev_midi - (prev_midi % 12) + target_pc + 12 * octave_shift
        if candidate < low or candidate > high:
            continue
        dist = abs(candidate - prev_midi)
        if best is None or dist < best_dist:
            best, best_dist = candidate, dist
    if best is None:
        # Range too narrow to contain this pitch class near prev_midi — clamp
        # to the nearest in-range octave of the target pitch class.
        candidate = low + ((target_pc - low) % 12)
        best = min(max(candidate, low), high)
    return best


def _choose_pitch_class(
    *,
    level: str,
    is_strong_beat: bool,
    is_phrase_end: bool,
    chord_pcs: list[int],
    scale_pcs: list[int],
    next_chord_pcs: list[int] | None,
    rng: random.Random,
) -> tuple[int, str]:
    if is_phrase_end:
        # Resolve phrase endings to the chord's root or third for a clear
        # harmonic landing rather than any chord tone at random.
        target_set = chord_pcs[:2] or chord_pcs
        return rng.choice(target_set), "chord_tone"
    if is_strong_beat:
        return rng.choice(chord_pcs), "chord_tone"
    roll = rng.random()
    chromatic_prob = _CHROMATIC_APPROACH_PROB[level]
    passing_prob = _PASSING_TONE_PROB[level]
    if roll < chromatic_prob and next_chord_pcs:
        target = rng.choice(next_chord_pcs)
        approach = (target + rng.choice((-1, 1))) % 12
        return approach, "approach"
    if roll < chromatic_prob + passing_prob:
        non_chord_scale = [pc for pc in scale_pcs if pc not in chord_pcs]
        if non_chord_scale:
            return rng.choice(non_chord_scale), "passing"
    return rng.choice(chord_pcs), "chord_tone"


def _closest_chord_tone_within_budget(
    *,
    preferred_pcs: list[int],
    chord_pcs: list[int],
    prev_midi: int,
    low: int,
    high: int,
    max_leap: int,
) -> int | None:
    """Closest chord tone reachable within the leap budget, preferring
    ``preferred_pcs`` (root/third for a phrase ending) before widening to
    any chord tone -- so a leap-budget fallback still resolves as strongly
    as the range allows, rather than landing on whichever chord tone happens
    to be nearest regardless of its harmonic weight."""
    for pool in (preferred_pcs, chord_pcs):
        best_midi: int | None = None
        best_dist: int | None = None
        for alt_pc in pool:
            alt_midi = _closest_midi_for_pc(alt_pc, prev_midi, low, high)
            dist = abs(alt_midi - prev_midi)
            if dist <= max_leap and (best_dist is None or dist < best_dist):
                best_midi, best_dist = alt_midi, dist
        if best_midi is not None:
            return best_midi
    return None


def _generate_section_events(
    *,
    chords: list[str],
    key_center: str,
    level: str,
    tempo_bpm: float,
    beats_per_measure: float,
    rng: random.Random,
    start_midi: int,
) -> tuple[list[MelodyEvent], int]:
    low, high = _LEVEL_RANGE[level]
    max_leap = _MAX_LEAP_SEMITONES[level]
    scale_pcs = _diatonic_scale_pcs(key_center)
    events: list[MelodyEvent] = []
    prev_midi = start_midi
    num_measures = len(chords)

    for m_idx, chord in enumerate(chords):
        chord_pcs = _chord_tone_pcs(chord)
        next_chord = chords[m_idx + 1] if m_idx + 1 < num_measures else None
        next_chord_pcs = _chord_tone_pcs(next_chord) if next_chord else None
        cells = _fit_archetype_to_measure(_pick_archetype(level, tempo_bpm, rng), beats_per_measure)
        is_last_measure = m_idx == num_measures - 1
        num_sounding = sum(1 for _, is_rest in cells if not is_rest)
        sounding_seen = 0
        beat_cursor = 0.0

        for dur, is_rest in cells:
            if is_rest:
                events.append(
                    MelodyEvent(
                        measure=m_idx,
                        beat=beat_cursor,
                        duration_beats=dur,
                        is_rest=True,
                        chord=str(chord),
                        tone_role="rest",
                    )
                )
                beat_cursor += dur
                continue

            sounding_seen += 1
            is_strong_beat = beat_cursor == 0.0 or (
                beats_per_measure >= 4 and abs(beat_cursor - (beats_per_measure // 2)) < 1e-6
            )
            is_phrase_end = is_last_measure and sounding_seen == num_sounding

            pc, role = _choose_pitch_class(
                level=level,
                is_strong_beat=is_strong_beat,
                is_phrase_end=is_phrase_end,
                chord_pcs=chord_pcs,
                scale_pcs=scale_pcs,
                next_chord_pcs=next_chord_pcs,
                rng=rng,
            )
            candidate_midi = _closest_midi_for_pc(pc, prev_midi, low, high)
            if abs(candidate_midi - prev_midi) > max_leap:
                # Leap too large for this level — fall back to the closest
                # in-budget chord tone instead of an unplayable jump. A
                # phrase ending prefers root/third first, only widening to
                # any chord tone if neither is reachable within the leap
                # budget from here.
                fallback_midi = _closest_chord_tone_within_budget(
                    preferred_pcs=(chord_pcs[:2] if is_phrase_end else chord_pcs),
                    chord_pcs=chord_pcs,
                    prev_midi=prev_midi,
                    low=low,
                    high=high,
                    max_leap=max_leap,
                )
                if fallback_midi is not None:
                    candidate_midi = fallback_midi
                    role = "chord_tone"

            spelled = spell_pitch_classes_for_chord(
                [candidate_midi % 12], chord, song_display_key=key_center
            )[0]
            events.append(
                MelodyEvent(
                    measure=m_idx,
                    beat=beat_cursor,
                    duration_beats=dur,
                    is_rest=False,
                    pitch=spelled,
                    midi=candidate_midi,
                    chord=str(chord),
                    tone_role=role,
                )
            )
            prev_midi = candidate_midi
            beat_cursor += dur

    return events, prev_midi


def generate_practice_melody(
    *,
    song_id: str,
    song_title: str,
    sections: dict[str, list[str]],
    section_order: list[str] | None = None,
    key_center: str,
    level: str,
    tempo_bpm: float = 100.0,
    style: str = "",
    meter: tuple[int, int] = (4, 4),
    seed: int | None = None,
    alt_index: int = 0,
) -> PracticeMelody:
    """Generate a structured Practice Melody for one song, level and alternative.

    ``sections`` follows the existing Catalog/Custom convention: one chord
    symbol per measure, keyed by section name (e.g. ``{"Verse 1": ["G",
    "Em7", ...]}``). This function never mutates or resolves the song's key —
    ``key_center`` is supplied by the caller.

    Reproducible by construction: with an explicit ``seed`` the output is
    byte-identical across runs; without one, a seed is derived deterministically
    from ``(song_id, level, alt_index)`` so the same call always reproduces the
    same melody, while a different ``alt_index`` reliably yields a different
    (but still level/song-appropriate) alternative — the mechanism "Generate
    Another Melody" will build on in a later slice.
    """
    if level not in _LEVEL_ARCHETYPES:
        level = "Intermediate"

    order = list(section_order) if section_order else list(sections.keys())
    ordered_names = [name for name in order if name in sections]
    ordered_names += [name for name in sections if name not in ordered_names]

    resolved_seed = _seed_for(song_id, level, alt_index, seed)
    rng = random.Random(resolved_seed)
    beats_per_measure = float(meter[0]) if meter and meter[0] else 4.0
    prev_end_midi = _START_MIDI[level]

    generated_by_chords: dict[tuple[str, ...], MelodySection] = {}
    out_sections: list[MelodySection] = []

    for name in ordered_names:
        chords = [str(c) for c in (sections.get(name) or [])]
        if not chords:
            continue
        chord_key = tuple(chords)
        existing = generated_by_chords.get(chord_key)
        if existing is not None:
            # Deliberate repeat handling: reuse the earlier section's melody
            # verbatim rather than generating a fresh (and possibly
            # incoherent) one for an identical repeated progression.
            repeated = replace(existing, section_id=name, repeat_of=existing.section_id)
            out_sections.append(repeated)
            if repeated.events:
                last_sounding = [e for e in repeated.events if not e.is_rest]
                if last_sounding:
                    prev_end_midi = last_sounding[-1].midi  # type: ignore[assignment]
            continue

        events, prev_end_midi = _generate_section_events(
            chords=chords,
            key_center=key_center,
            level=level,
            tempo_bpm=tempo_bpm,
            beats_per_measure=beats_per_measure,
            rng=rng,
            start_midi=prev_end_midi,
        )
        section = MelodySection(
            section_id=name,
            section_type=practice_section_type(name),
            measures=len(chords),
            beats_per_measure=beats_per_measure,
            chords=tuple(chords),
            events=tuple(events),
            repeat_of=None,
        )
        generated_by_chords[chord_key] = section
        out_sections.append(section)

    return PracticeMelody(
        schema_version=SCHEMA_VERSION,
        melody_id=_melody_id(song_id, level, alt_index, resolved_seed),
        source="generated",
        song_id=song_id,
        song_title=song_title,
        level=level,
        key_center=key_center,
        meter=(int(meter[0]), int(meter[1])),
        tempo_bpm=float(tempo_bpm),
        style=style,
        seed=resolved_seed,
        alt_index=alt_index,
        generator_version=GENERATOR_VERSION,
        section_order=tuple(s.section_id for s in out_sections),
        sections=tuple(out_sections),
    )


def generate_another_practice_melody(
    previous: PracticeMelody, **overrides: object
) -> PracticeMelody:
    """Produce the next alternative for the same song/level — the backend for
    a future "Generate Another Melody" action. Deterministic: calling this
    twice on the same ``previous`` melody (with no overrides) always yields
    the same next alternative.
    """
    kwargs: dict[str, object] = dict(
        song_id=previous.song_id,
        song_title=previous.song_title,
        sections={s.section_id: list(s.chords) for s in previous.sections},
        section_order=list(previous.section_order),
        key_center=previous.key_center,
        level=previous.level,
        tempo_bpm=previous.tempo_bpm,
        style=previous.style,
        meter=previous.meter,
        seed=None,
        alt_index=previous.alt_index + 1,
    )
    kwargs.update(overrides)
    return generate_practice_melody(**kwargs)  # type: ignore[arg-type]
