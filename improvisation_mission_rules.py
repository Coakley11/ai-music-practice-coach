"""Mission constraints applied after base motif generation.

C4: a handful of missions additionally draw their *pitch shape* from the
shared ``melodic_pattern_engine`` vocabulary (the same engine Phrase & Motif
uses) so Intermediate/Advanced examples are more than a random walk over a
2-4 note pool. The mission's own hard constraint always wins: every engine
candidate is still clamped/validated against the exact rule the mission
teaches before it is accepted, and any family the engine cannot realize for
this chord/direction/level simply falls back to the original, always-safe
pool logic below. No second vocabulary is introduced here — this only calls
``melodic_pattern_engine``/``melodic_rhythm_engine``.
"""

from __future__ import annotations

import math
import random
from typing import Any

from music_theory import classify_chord_quality, normalize_root, split_chord
from improvisation_motif import (
    _RHYTHM_PATTERNS,
    _midi_from_note,
    _motif_notes_for_tier,
    _normalize_motif_level,
    _parse_key_scale,
    _rhythm_for_harder,
    apply_engine_rhythm,
    chord_tone_names,
    sync_motif_midi,
    transform_motif,
)
from melodic_pattern_engine import _step, eligible_families, generate_pattern, normalize_difficulty


def _pc(note: str) -> int:
    from music_theory import NOTE_TO_MIDI

    root, _ = split_chord(str(note))
    return NOTE_TO_MIDI.get(normalize_root(root), 60) % 12


def _chord_tone_pcs(chord: str, *, key_center: str) -> set[int]:
    return {_pc(n) for n in chord_tone_names(chord, reference_key=key_center)}


def _guide_third_seventh(chord: str, *, key_center: str) -> list[str]:
    """3rd and 7th of ``chord`` — guide tones are a 7th-chord concept, so a
    bare triad symbol (very common in real songs: "G", "Am", "C"...) must
    still produce two distinct tones, not collapse to the 3rd alone.

    The chord symbol always wins when it names a seventh explicitly (G7,
    Gmaj7, Gm7, ...). When it doesn't, the implied 7th is the *diatonic*
    7th in the active key/Mission context — not a universal b7 — found by
    locating the chord's root in the key's diatonic scale and taking the
    scale tone one step below it (= a 7th above, same pitch class):
    G in C major -> F; G in G major -> F#; Dm in C major -> C;
    F in C major -> E; Bb in F major -> A. A fixed b7 is only used as a
    last-resort fallback when no usable key context is available at all.
    """
    tones = chord_tone_names(chord, reference_key=key_center)
    if len(tones) >= 4:
        return [tones[1], tones[3]]
    if len(tones) >= 2:
        from improvisation_motif import _nearest_scale_degree, _note_from_midi

        third = tones[1]
        root = tones[0]
        root_midi = _midi_from_note(root, 4)
        try:
            _mode, scale_pcs = _parse_key_scale(key_center)
        except Exception:
            scale_pcs = []
        if scale_pcs:
            degree = _nearest_scale_degree(root, scale_pcs)
            seventh_pc = scale_pcs[(degree - 1) % len(scale_pcs)]
            # Land the chosen pitch class just below the root's own octave
            # register so "7th above root" reads as expected, not a 2nd below.
            candidate = (root_midi // 12) * 12 + seventh_pc
            if candidate >= root_midi:
                candidate -= 12
            implied_seventh = _note_from_midi(candidate, key_center)
        else:
            # No usable key context — documented fallback: dominant b7.
            implied_seventh = _note_from_midi(root_midi + 10, key_center)
        return [third, implied_seventh]
    return tones[:1]


def _line_from_pool(pool: list[str], count: int, rng: random.Random) -> list[str]:
    if not pool:
        return []
    return [pool[rng.randrange(len(pool))] for _ in range(count)]


def _snap_notes_to_pcs(notes: list[str], allowed_pcs: set[int], *, key_center: str) -> list[str]:
    """Re-spell every note onto the nearest pitch class in ``allowed_pcs``.

    Keeps the engine's contour/rhythm shape while guaranteeing the mission's
    hard "only these tones" constraint can never be violated, regardless of
    which vocabulary family produced the line.
    """
    if not allowed_pcs:
        return list(notes)
    from improvisation_motif import _note_from_midi

    ordered = sorted(allowed_pcs)
    out: list[str] = []
    for n in notes:
        midi = _midi_from_note(str(n), 4)
        pc = midi % 12
        nearest = min(ordered, key=lambda target: min((pc - target) % 12, (target - pc) % 12))
        delta = min(((nearest - pc) % 12, -((pc - nearest) % 12)), key=abs)
        out.append(_note_from_midi(midi + delta, key_center))
    return out


def _nearest_midi_for_pc(target_midi: int, pc: int) -> int:
    base = (int(target_midi) // 12) * 12 + int(pc)
    return min((base - 12, base, base + 12), key=lambda m: abs(m - target_midi))


def _guide_tone_musical_line(
    *,
    key_center: str,
    level: str,
    rng: random.Random,
    count: int,
    guide_tones: list[str],
) -> list[str]:
    """A genuinely melodic guide-tone line — register, contour and
    sequencing, not mechanical alternation — while staying strictly on the
    two legal pitch classes (3rd/7th) the mission allows. No illegal note is
    ever introduced; only these two pitch classes are used, in different
    octaves and a shaped contour instead of a flat random pool draw."""
    if len(guide_tones) < 2:
        return list(guide_tones) * max(1, count) if guide_tones else []
    from improvisation_motif import _note_from_midi

    third_pc = _midi_from_note(guide_tones[0], 4) % 12
    seventh_pc = _midi_from_note(guide_tones[1], 4) % 12
    level_norm = _normalize_motif_level(level)
    # How wide a register the line is allowed to roam — Advanced gets the
    # widest arch, Intermediate a modest one.
    span_semitones = {"Beginner": 5, "Intermediate": 8, "Advanced": 14}.get(level_norm, 8)
    center = 69  # A4 — comfortable middle register for any instrument.
    center += rng.choice([-2, 0, 0, 2])  # small, idea-to-idea register shift
    descending_first = rng.random() < 0.5
    notes: list[str] = []
    n = max(1, count)
    for i in range(n):
        progress = i / max(1, n - 1)
        wave = math.sin(progress * math.pi)  # arch: 0 -> 1 -> 0
        if descending_first:
            wave = -wave
        target_midi = center + int(round(wave * span_semitones))
        third_midi = _nearest_midi_for_pc(target_midi, third_pc)
        seventh_midi = _nearest_midi_for_pc(target_midi, seventh_pc)
        d_third = abs(third_midi - target_midi)
        d_seventh = abs(seventh_midi - target_midi)
        if d_third == d_seventh:
            use_third = (i % 2 == 0)
        else:
            use_third = d_third < d_seventh
        chosen_midi = third_midi if use_third else seventh_midi
        notes.append(_note_from_midi(chosen_midi, key_center))
    return notes


def _pattern_engine_notes(
    chord: str,
    *,
    key_center: str,
    level: str,
    rng: random.Random,
    categories: set[str],
    length: int,
    allowed_pcs: set[int] | None = None,
    max_families_tried: int = 4,
) -> list[str] | None:
    """Draw a pitch line from the shared pattern engine for one mission branch.

    Tries up to ``max_families_tried`` eligible families (level-appropriate,
    per ``melodic_pattern_engine.eligible_families``), favoring the
    higher-weighted ones. Returns ``None`` if no family can be realized for
    this chord/key/direction so the caller can fall back to the plain pool
    logic — a vocabulary family that cannot satisfy the context is simply
    skipped, never forced.
    """
    difficulty = normalize_difficulty(level)
    weighted = [
        (fam, weight)
        for fam, weight in eligible_families(key=key_center, chord=chord, difficulty=difficulty, chromatic="auto")
        if fam.category in categories
    ]
    if not weighted:
        return None
    # Weighted-*sample* the try order using the caller's seeded rng, rather
    # than always trying the same fixed weight-sorted order — otherwise a
    # context with few eligible families can realize the exact same output
    # for every nonce/idea-index (Easier/Harder repeats, human-review
    # finding), since only the first family that successfully realizes ever
    # gets used.
    pool = list(weighted)
    order: list = []
    for _ in range(min(max_families_tried, len(pool))):
        total = sum(w for _f, w in pool) or 1.0
        pick = rng.random() * total
        running = 0.0
        chosen_idx = len(pool) - 1
        for i, (_f, w) in enumerate(pool):
            running += w
            if pick <= running:
                chosen_idx = i
                break
        order.append(pool.pop(chosen_idx)[0])
    for fam in order:
        direction = "ascending" if rng.random() < 0.5 else "descending"
        try:
            result = generate_pattern(
                fam,
                key=key_center,
                chord=chord,
                direction=direction,
                length=max(1, min(16, length)),
                seed=rng.randrange(1_000_000),
            )
        except ValueError:
            continue
        notes = list(result.notes)[:length]
        if not notes:
            continue
        if allowed_pcs is not None:
            notes = _snap_notes_to_pcs(notes, allowed_pcs, key_center=key_center)
        while len(notes) < length:
            notes.append(notes[-1])
        return notes
    return None


def _apply_rhythm_pattern(motif: dict[str, Any], rhythm_key: str, note_count: int) -> dict[str, Any]:
    syms = list(_RHYTHM_PATTERNS.get(rhythm_key, _RHYTHM_PATTERNS["quarter-quarter-quarter"]))
    while len(syms) < note_count:
        syms += syms
    updated = dict(motif)
    updated["rhythm_key"] = rhythm_key
    updated["rhythm_symbols"] = syms[:note_count]
    updated["rhythm"] = " ".join(updated["rhythm_symbols"])
    return updated


def _split_rhythm_halves(motif: dict[str, Any], rk_a: str, rk_b: str) -> dict[str, Any]:
    notes = list(motif.get("notes") or [])
    if len(notes) < 4:
        notes = (notes * 2)[:6]
        motif = dict(motif)
        motif["notes"] = notes
    mid = max(2, len(notes) // 2)
    syms_a = list(_RHYTHM_PATTERNS.get(rk_a, _RHYTHM_PATTERNS["quarter-quarter-quarter"]))
    syms_b = list(_RHYTHM_PATTERNS.get(rk_b, _RHYTHM_PATTERNS["eighth-eighth-quarter"]))
    while len(syms_a) < mid:
        syms_a += syms_a
    while len(syms_b) < len(notes) - mid:
        syms_b += syms_b
    syms = syms_a[:mid] + syms_b[: len(notes) - mid]
    updated = dict(motif)
    updated["notes"] = notes
    updated["rhythm_key"] = f"{rk_a}|{rk_b}"
    updated["rhythm_symbols"] = syms
    updated["rhythm"] = " ".join(syms)
    return sync_motif_midi(updated)


def _five_notes_one_register(chord: str, *, key_center: str) -> list[str]:
    tones = chord_tone_names(chord, reference_key=key_center)
    base_midi = _midi_from_note(tones[0], 4) if tones else 60
    pool: list[str] = []
    for t in tones:
        if t not in pool:
            pool.append(t)
    for step in (2, -2, 4):
        if len(pool) >= 5:
            break
        cand_midi = base_midi + step
        from improvisation_motif import _note_from_midi

        name = _note_from_midi(cand_midi, key_center)
        if name not in pool:
            pool.append(name)
    pool = pool[:5]
    while len(pool) < 5 and tones:
        pool.append(tones[len(pool) % len(tones)])
    midis = [_midi_from_note(n, 4) for n in pool[:5]]
    low, high = min(midis), max(midis)
    if high - low > 12:
        pool = pool[:3]
        while len(pool) < 5:
            pool.append(pool[-1])
    return pool[:5]


def _silence_motif(chord: str, *, key_center: str, every_two_bars: bool) -> dict[str, Any]:
    tones = chord_tone_names(chord, reference_key=key_center)
    a = tones[0] if tones else "C"
    b = tones[1] if len(tones) > 1 else a
    if every_two_bars:
        notes = [a, b, a]
        rhythm_symbols = ["♩", "z", "♩", "z", "𝅗"]
    else:
        notes = [a, b]
        rhythm_symbols = ["♩", "z", "♩", "z", "♩", "z", "♩"]
    return sync_motif_midi({
        "chord": chord,
        "notes": notes,
        "rhythm_key": "mission-silence",
        "rhythm_symbols": rhythm_symbols,
        "rhythm": " ".join(rhythm_symbols),
    })


def _dominant_tension_line(chord: str, *, key_center: str, rng: random.Random) -> list[str]:
    tones = chord_tone_names(chord, reference_key=key_center)
    if len(tones) < 4:
        return tones
    third, seventh = tones[1], tones[3]
    root = tones[0]
    from improvisation_motif import _note_from_midi

    approach7 = _note_from_midi(_midi_from_note(seventh, 4) - 1, key_center)
    pool = [approach7, seventh, third, seventh, root, third, approach7, seventh]
    return _line_from_pool(pool, 8, rng)


def apply_mission_rules(
    mission: str,
    motif: dict[str, Any],
    *,
    chord: str,
    key_center: str,
    level: str,
    variant: str,
    rng: random.Random,
) -> dict[str, Any]:
    """Shape generated motif so the example teaches the selected mission."""
    low = str(mission or "").lower()
    allowed = _chord_tone_pcs(chord, key_center=key_center)
    qual = classify_chord_quality(chord)
    notes = list(motif.get("notes") or [])

    if "chord tone" in low and "only" in low:
        pool = chord_tone_names(chord, reference_key=key_center)
        count = max(6, min(10, len(notes) or 8))
        level_norm = _normalize_motif_level(level)
        engine_notes = None
        if level_norm != "Beginner":
            engine_notes = _pattern_engine_notes(
                chord,
                key_center=key_center,
                level=level,
                rng=rng,
                categories={"chord_tone", "arpeggio_scale"},
                length=count,
                allowed_pcs=allowed,
            )
        motif["notes"] = engine_notes or _line_from_pool(pool, count, rng)
        motif["variation_prompt"] = f"Chord tones only on **{chord}** — every note is part of the harmony."
        return sync_motif_midi(motif)

    if "guide tone" in low:
        pool = _guide_third_seventh(chord, key_center=key_center)
        count = max(8, min(12, len(notes) or 10))
        level_norm = _normalize_motif_level(level)
        if level_norm == "Beginner":
            motif["notes"] = _line_from_pool(pool, count, rng)
        else:
            # Register/contour/sequencing instead of a flat random pool draw
            # or snap-induced mechanical alternation — still strictly only
            # the 3rd and 7th pitch classes (human-review finding).
            motif["notes"] = _guide_tone_musical_line(
                key_center=key_center, level=level, rng=rng, count=count, guide_tones=pool,
            )
            motif = apply_engine_rhythm(
                motif,
                meter=str(motif.get("meter") or "4/4"),
                level=level_norm,
                seed=rng.randrange(1_000_000),
            )
        motif["variation_prompt"] = (
            f"Guide tones only on **{chord}** — stay on the 3rd and 7th ({', '.join(pool)})."
        )
        return sync_motif_midi(motif)

    if "5 notes" in low and "register" in low:
        motif["notes"] = _five_notes_one_register(chord, key_center=key_center)
        motif = _apply_rhythm_pattern(motif, "quarter-eighth-eighth", len(motif["notes"]))
        motif["variation_prompt"] = "Five notes in one register — repeat the cell, don’t wander."
        return sync_motif_midi(motif)

    if "scalar" in low and "only" in low:
        _mode, scale_pcs = _parse_key_scale(key_center)
        from improvisation_motif import _note_from_midi

        if scale_pcs:
            ordered = sorted(scale_pcs)
            run: list[str] = []
            start = rng.randrange(len(ordered))
            for i in range(max(6, len(notes) or 8)):
                pc = ordered[(start + i) % len(ordered)]
                run.append(_note_from_midi(60 + pc, key_center))
            motif["notes"] = run
        motif["variation_prompt"] = "Scalar run only — step through the scale, not arpeggios."
        return sync_motif_midi(motif)

    if "scalar" in low and "without" in low:
        pool = chord_tone_names(chord, reference_key=key_center)
        motif["notes"] = _line_from_pool(pool, 8, rng)
        motif["variation_prompt"] = "No scalar runs — chord tones and steps between them only."
        return sync_motif_midi(motif)

    if ("dominant" in low or "tension" in low) and qual == "dom":
        level_norm = _normalize_motif_level(level)
        engine_notes = None
        if level_norm == "Advanced":
            # No hard pitch constraint gates this mission — an excellent
            # place for b9/#9/b5-type color via real chromatic-approach /
            # bebop vocabulary rather than the fixed hand-written line.
            engine_notes = _pattern_engine_notes(
                chord,
                key_center=key_center,
                level=level,
                rng=rng,
                categories={"chromatic_approach", "bebop", "chromatic_sequence"},
                length=8,
            )
        motif["notes"] = engine_notes or _dominant_tension_line(chord, key_center=key_center, rng=rng)
        motif["variation_prompt"] = (
            f"Dominant tension on **{chord}** — 3rd, b7, and chromatic approaches into the next change."
        )
        return sync_motif_midi(motif)

    if "motif" in low and "solo" in low:
        tones = chord_tone_names(chord, reference_key=key_center)[:3]
        if len(tones) >= 3:
            core = tones
            developed = core + [core[1], core[2], core[0], core[2], core[0], core[1], core[2]]
            motif["notes"] = developed[:12]
        motif["variation_prompt"] = f"Develop this cell through **{chord}** — repeat, then vary one note."
        return sync_motif_midi(motif)

    if "rhythm" in low and "note" in low:
        pool = chord_tone_names(chord, reference_key=key_center)[:3]
        level_norm = _normalize_motif_level(level)
        tier = {"easier": "easier", "harder": "harder"}.get(variant, "normal")
        _mode, scale_pcs = _parse_key_scale(key_center)
        tones = chord_tone_names(chord, reference_key=key_center)
        tier_notes = _motif_notes_for_tier(chord, tones, scale_pcs, level_norm, tier, rng, 0)
        if variant == "easier":
            count = min(max(len(tier_notes), 4), 6)
        elif variant == "harder":
            count = max(len(tier_notes), 10 if level_norm != "Advanced" else 12)
        else:
            count = max(8, len(tier_notes))
        motif["notes"] = _line_from_pool(pool, count, rng)
        if variant == "harder" and level_norm == "Advanced":
            rk, _syms = _rhythm_for_harder(count, 0)
            motif = _apply_rhythm_pattern(motif, rk, count)
            motif["harder_example"] = True
        else:
            # Pitch stays a plain chord-tone pool on purpose — this mission is
            # literally "rhythm over note choice". The shared rhythm engine
            # (same one Phrase & Motif's Change Rhythm uses) gives the rhythm
            # itself level-appropriate variety instead of one of 3 fixed cells.
            motif = apply_engine_rhythm(
                motif,
                meter=str(motif.get("meter") or "4/4"),
                level=level_norm,
                seed=rng.randrange(1_000_000),
            )
        motif["variation_prompt"] = "Rhythm leads — simple chord tones, bold rhythmic placement."
        return sync_motif_midi(motif)

    if "silence" in low or "rest" in low:
        every_two = "2 bar" in low or "two bar" in low or "every 2" in low
        out = _silence_motif(chord, key_center=key_center, every_two_bars=every_two)
        out["variation_prompt"] = (
            f"Rest intentionally on **{chord}** — the rests are part of the phrase."
        )
        return out

    if "resolve" in low and "beat 1" in low:
        root = chord_tone_names(chord, reference_key=key_center)[0]
        pool = chord_tone_names(chord, reference_key=key_center)
        level_norm = _normalize_motif_level(level)
        engine_tail = None
        if level_norm == "Advanced":
            # Richer bebop/enclosure/chromatic-approach shape for the notes
            # leading up to the landing — the landing note itself (index 0,
            # beat 1) is still forced to the mission's actual target below,
            # regardless of what the vocabulary family proposed there.
            engine_tail = _pattern_engine_notes(
                chord,
                key_center=key_center,
                level=level,
                rng=rng,
                categories={"chromatic_approach", "enclosure", "bebop"},
                length=5,
            )
        tail = engine_tail or _line_from_pool(pool, 5, rng)
        motif["notes"] = [root] + list(tail[1:5])
        motif["rhythm_symbols"] = ["♩", "♩", "♩", "♩", "♩"]
        motif["rhythm"] = "♩ ♩ ♩ ♩ ♩"
        motif["meter"] = str(motif.get("meter") or "4/4")
        motif["variation_prompt"] = "Land beat 1 on the root (or strongest chord tone) each phrase."
        return sync_motif_midi(motif)

    if "pattern" in low and "twice" in low:
        keys = ["quarter-quarter-quarter", "eighth-eighth-quarter", "quarter-eighth-eighth", "syncopated-four"]
        a = keys[rng.randrange(len(keys))]
        b = keys[(keys.index(a) + 1 + rng.randrange(len(keys) - 1)) % len(keys)]
        pool = chord_tone_names(chord, reference_key=key_center)[:3]
        motif["notes"] = _line_from_pool(pool, 8, rng)
        motif = _split_rhythm_halves(motif, a, b)
        motif["variation_prompt"] = "Alternate rhythmic shapes — never repeat the same pattern twice in a row."
        return motif

    if "chromatic" in low and "approach" in low:
        return _apply_chromatic_approach_mission(motif, chord=chord, key_center=key_center, level=level, rng=rng)

    if "enclose" in low or "enclosure" in low:
        return _apply_enclosure_mission(motif, chord=chord, key_center=key_center, level=level, rng=rng)

    if "3rd" in low and "resolve" in low:
        return _apply_target_third_mission(
            motif, chord=chord, key_center=key_center, level=level, variant=variant, rng=rng
        )

    if "bebop" in low:
        return _apply_bebop_line_mission(motif, chord=chord, key_center=key_center, level=level, rng=rng)

    if "pentatonic" in low:
        return _apply_pentatonic_mission(
            motif, chord=chord, key_center=key_center, level=level, variant=variant, rng=rng
        )

    return sync_motif_midi(motif)


def _apply_chromatic_approach_mission(
    motif: dict[str, Any], *, chord: str, key_center: str, level: str, rng: random.Random
) -> dict[str, Any]:
    from improvisation_motif import _note_from_midi

    level_norm = _normalize_motif_level(level)
    tones = chord_tone_names(chord, reference_key=key_center)
    targets = tones[:3] if len(tones) >= 3 else tones
    engine_notes = None
    if level_norm != "Beginner":
        engine_notes = _pattern_engine_notes(
            chord, key_center=key_center, level=level, rng=rng,
            categories={"chromatic_approach", "bebop"}, length=8,
        )
    if engine_notes:
        notes = engine_notes
    else:
        # Beginner: one explicit half-step approach into each chord tone —
        # the most direct, obvious reading of the mission.
        notes = []
        for t in (targets or ["C"]):
            above = rng.random() < 0.5
            tmidi = _midi_from_note(t, 4)
            approach = _note_from_midi(tmidi + (1 if above else -1), key_center)
            notes.extend([approach, t])
    motif["notes"] = notes
    motif["variation_prompt"] = f"Chromatic approach into **{chord}** chord tones — step in from a half step away."
    return sync_motif_midi(motif)


def _apply_enclosure_mission(
    motif: dict[str, Any], *, chord: str, key_center: str, level: str, rng: random.Random
) -> dict[str, Any]:
    from improvisation_motif import _note_from_midi

    level_norm = _normalize_motif_level(level)
    tones = chord_tone_names(chord, reference_key=key_center)
    target = tones[0] if tones else "C"
    if level_norm == "Beginner":
        # Simplified one-sided enclosure: a single neighbor, then land.
        tmidi = _midi_from_note(target, 4)
        above = rng.random() < 0.5
        neighbor = _note_from_midi(tmidi + (1 if above else -1), key_center)
        notes = [neighbor, target] * 3
    else:
        categories = {"enclosure"} if level_norm == "Intermediate" else {"enclosure", "bebop"}
        engine_notes = _pattern_engine_notes(
            chord, key_center=key_center, level=level, rng=rng, categories=categories, length=8,
        )
        notes = engine_notes or ([target] * 6)
    motif["notes"] = notes
    motif["variation_prompt"] = f"Enclose a target chord tone on **{chord}** — neighbor from both sides, then resolve."
    return sync_motif_midi(motif)


def _simple_third_approach(
    target: str, *, key_center: str, rng: random.Random
) -> list[str]:
    """Beginner / Intermediate-Easier: the single most direct, obvious
    reading of "approach -> 3rd" - one chromatic half-step OR one diatonic
    neighbor, from above or below, then the target. Always exactly two
    notes, so the 3rd is unmistakably the destination the listener hears."""
    from improvisation_motif import _note_from_midi, _scale_step_note

    tmidi = _midi_from_note(target, 4)
    above = rng.random() < 0.5
    if rng.random() < 0.6:
        approach = _note_from_midi(tmidi + (1 if above else -1), key_center)
    else:
        try:
            _mode, scale_pcs = _parse_key_scale(key_center)
        except Exception:
            scale_pcs = []
        if scale_pcs and len(scale_pcs) > 1:
            approach = _scale_step_note(scale_pcs, target, 1 if above else -1)
        else:
            approach = _note_from_midi(tmidi + (1 if above else -1), key_center)
    return [approach, target]


def _target_third_setup_note(
    chord: str, *, key_center: str, rng: random.Random, avoid_pc: int
) -> str:
    """One chord tone, different from the target, opening the phrase before
    the approach - the extra "setup" element Harder/Advanced phrases add so
    they read as a short line arriving at the 3rd, not just a longer cell."""
    tones = chord_tone_names(chord, reference_key=key_center)
    pool = [t for t in tones if _pc(t) != avoid_pc] or tones
    if not pool:
        return "C"
    return pool[rng.randrange(len(pool))]


def _pattern_engine_target_notes(
    chord: str,
    *,
    key_center: str,
    difficulty: str,
    rng: random.Random,
    categories: set[str],
    target_role: str,
    max_families_tried: int = 4,
) -> list[str] | None:
    """Approach-and-resolve line from the shared pattern engine, forced to
    land exactly on ``target_role`` (e.g. the chord's 3rd) instead of
    whichever chord tone the family's own seeded rotation would otherwise
    land on. Every note the family contributes belongs to one cell that
    actually resolves onto the target - never a disconnected pattern with
    the target note stapled on afterward, which is what made earlier
    examples wander chromatically without the 3rd reading as a destination.

    Only families whose resolution note IS the starting chord tone itself
    are eligible: in those families (every ``enclosure``/``chromatic_approach``
    family except ``lower_approach_arpeggio``) pinning the start to
    ``target_role`` pins the landing note to the same role. Builder families
    (bebop runs) are not eligible here - they use a different algorithm that
    cannot be pinned this way, and stay available to Advanced through the
    existing bebop-category paths elsewhere in this module.

    Returns the notes truncated to end exactly at the family's resolution,
    so the LAST note returned is always the target - never a trailing
    ornament or the start of the next cell in a longer sequence.
    """
    import dataclasses

    weighted = [
        (fam, w)
        for fam, w in eligible_families(
            key=key_center, chord=chord, difficulty=difficulty, chromatic="auto"
        )
        if fam.category in categories
        and fam.builder is None
        and fam.target_index is not None
        and target_role in fam.start_roles
        and fam.target_index < len(fam.cell)
        and fam.cell[fam.target_index] == ("A", 0)
    ]
    if not weighted:
        return None
    pool = list(weighted)
    order: list = []
    for _ in range(min(max_families_tried, len(pool))):
        total = sum(w for _f, w in pool) or 1.0
        pick = rng.random() * total
        running = 0.0
        chosen_idx = len(pool) - 1
        for i, (_f, w) in enumerate(pool):
            running += w
            if pick <= running:
                chosen_idx = i
                break
        order.append(pool.pop(chosen_idx)[0])
    for fam in order:
        forced = dataclasses.replace(fam, start_roles=(target_role,))
        direction = "ascending" if rng.random() < 0.5 else "descending"
        try:
            result = generate_pattern(
                forced,
                key=key_center,
                chord=chord,
                direction=direction,
                length=1,
                seed=rng.randrange(1_000_000),
            )
        except ValueError:
            continue
        return list(result.notes)[: fam.target_index + 1]
    return None


def _apply_target_third_mission(
    motif: dict[str, Any], *, chord: str, key_center: str, level: str, variant: str, rng: random.Random
) -> dict[str, Any]:
    """Approach-and-resolve onto the chord's 3rd.

    The 3rd is the destination, not merely a note that happens to appear:
    every lead-in note is drawn from the SAME shared pattern-engine cell that
    actually resolves onto the 3rd (see ``_pattern_engine_target_notes``), so
    the approach/enclosure/chromatic vocabulary genuinely targets it instead
    of wandering and then landing on an unrelated extra note. Intermediate's
    Easier/Normal/Harder stepper widens the vocabulary pool (and, at Harder,
    adds a setup note plus rhythmic displacement) while the destination and
    the hard "ends on the 3rd" contract never change.
    """
    tones = chord_tone_names(chord, reference_key=key_center)
    third = tones[1] if len(tones) >= 2 else (tones[0] if tones else "C")
    level_norm = _normalize_motif_level(level)
    tier = str(variant or "normal").strip().lower()

    if level_norm == "Beginner" or (level_norm == "Intermediate" and tier == "easier"):
        notes = _simple_third_approach(third, key_center=key_center, rng=rng)
        add_setup = False
    else:
        if level_norm == "Intermediate":
            difficulty = "Advanced" if tier == "harder" else "Intermediate"
        else:  # Advanced
            difficulty = "Intermediate" if tier == "easier" else "Advanced"
        add_setup = tier == "harder" or (level_norm == "Advanced" and tier != "easier")
        lead = _pattern_engine_target_notes(
            chord,
            key_center=key_center,
            difficulty=difficulty,
            rng=rng,
            categories={"chromatic_approach", "enclosure"},
            target_role="3",
        )
        if lead is None:
            # No eligible shared-vocabulary family could be realized in this
            # chord/key context - fall back to the always-safe simple
            # approach rather than ever breaking the resolve-to-3rd contract.
            notes = _simple_third_approach(third, key_center=key_center, rng=rng)
            add_setup = False
        else:
            notes = list(lead)

    if add_setup:
        setup = _target_third_setup_note(chord, key_center=key_center, rng=rng, avoid_pc=_pc(third))
        notes = [setup] + notes

    motif["notes"] = notes
    if tier == "harder" and level_norm != "Beginner":
        rk, _syms = _rhythm_for_harder(len(notes), rng.randrange(3))
        motif = _apply_rhythm_pattern(motif, rk, len(notes))
        motif["harder_example"] = True
    else:
        motif["rhythm_symbols"] = ["♩"] * len(notes)
        motif["rhythm"] = " ".join(motif["rhythm_symbols"])
    motif["variation_prompt"] = (
        f"Resolve convincingly to the 3rd of **{chord}** ({third}) - every note leads into that target."
    )
    return sync_motif_midi(motif)


def _apply_bebop_line_mission(
    motif: dict[str, Any], *, chord: str, key_center: str, level: str, rng: random.Random
) -> dict[str, Any]:
    level_norm = _normalize_motif_level(level)
    pool = chord_tone_names(chord, reference_key=key_center)
    if level_norm == "Beginner":
        notes = _line_from_pool(pool, 8, rng) if pool else []
    else:
        categories = (
            {"chord_tone", "chromatic_approach"}
            if level_norm == "Intermediate"
            else {"bebop", "chromatic_approach", "chromatic_sequence"}
        )
        notes = _pattern_engine_notes(
            chord, key_center=key_center, level=level, rng=rng, categories=categories, length=10,
        ) or _line_from_pool(pool, 8, rng)
    motif["notes"] = notes
    motif["variation_prompt"] = f"Bebop-style line on **{chord}** — chord tones on strong beats, intentional chromatic motion between."
    return sync_motif_midi(motif)


# ---------------------------------------------------------------------------
# C4 Slice 3 - "Improvise using a pentatonic scale that fits the chord."
#
# The pentatonic CHOICE is relationship-based (root-anchored, or a fixed
# interval offset from the chord root) rather than a stored literal note set.
# Re-resolving a relationship against a transposed chord after a Practice-Key
# change gives the correctly transposed pentatonic automatically, through the
# existing R7/R8/R9 chord/key transpose alone - there is no second,
# independent pentatonic owner and no separate pentatonic-specific transpose
# step. Scale spelling reuses the existing _SCALE_INTERVALS/spell_scale_notes
# theory utilities rather than a new scale table.
# ---------------------------------------------------------------------------

PENTATONIC_RELATIONSHIPS: tuple[str, ...] = ("root_minor", "root_major", "fourth_above_major")


def _pentatonic_relationship_for_quality(quality: str) -> str:
    """Default (rng-free) relationship for a chord-quality bucket.

    Used both as the generation default and as the validator's fallback when
    an older/foreign stored example has no ``pentatonic_relationship`` tag.
    """
    if quality in ("major", "maj7", "sus", "aug"):
        return "root_major"
    if quality in ("minor", "m7", "half-dim", "dim"):
        return "root_minor"
    # Dominant (and anything unclassified) - root minor pentatonic is the
    # straightforward blues-oriented default.
    return "root_minor"


def choose_pentatonic_relationship(
    chord: str, *, level: str, variant: str, rng: random.Random | None = None
) -> str:
    """Pick the pentatonic relationship for one Mission generation.

    Dominant chords get a deliberate, visible alternative at the richer
    tiers only: a major pentatonic rooted a 4th above the chord root (e.g.
    C major pentatonic over G7) is a standard, non-exotic dominant color
    (4/5/13/R/9 of the chord), not introduced merely to look different at
    Advanced, and chosen only about half the time so New Idea can land on
    either valid relationship.
    """
    quality = classify_chord_quality(chord)
    base = _pentatonic_relationship_for_quality(quality)
    if quality == "dom" and rng is not None:
        level_norm = _normalize_motif_level(level)
        tier = str(variant or "normal").strip().lower()
        richer_tier = level_norm == "Advanced" or (level_norm == "Intermediate" and tier == "harder")
        if richer_tier and rng.random() < 0.5:
            return "fourth_above_major"
    return base


def resolve_pentatonic_choice(
    chord: str, key_center: str, relationship: str
) -> tuple[str, str, list[str], str]:
    """(pentatonic_root, scale_kind, spelled_notes, display_label).

    Pure function of (chord, key_center, relationship) - the same inputs
    always give the same transposed result, which is what makes a Practice-
    Key change "just work" by re-deriving from the new chord.
    """
    from improvisation_intelligence import spell_scale_notes
    from improvisation_motif import _note_from_midi

    tones = chord_tone_names(chord, reference_key=key_center)
    root = tones[0] if tones else "C"
    rel = str(relationship or "root_minor").strip()
    if rel == "fourth_above_major":
        proot = _note_from_midi(_midi_from_note(root, 4) + 5, key_center)
        kind = "major pentatonic"
    elif rel == "root_major":
        proot, kind = root, "major pentatonic"
    else:
        proot, kind = root, "minor pentatonic"
    notes = spell_scale_notes(proot, kind, key_center)
    label = f"{proot} {'Minor' if 'minor' in kind else 'Major'} Pentatonic"
    return proot, kind, notes, label


# (length_range, max_step_in_collection, direction_changes, octave_jumps, sequence)
# Each tier strictly widens length/max_step/direction_changes over the one
# before it within the same level, and Advanced widens further over
# Intermediate at the matching tier - the measurable "sophistication ladder"
# the Mission asks for, independent of which exact notes are drawn.
_PENTATONIC_DIFFICULTY_PROFILE: dict[tuple[str, str], dict[str, Any]] = {
    ("Beginner", "easier"): dict(length=(3, 5), max_step=1, direction_changes=0, octave_jumps=0, sequence=False),
    ("Beginner", "normal"): dict(length=(4, 6), max_step=1, direction_changes=1, octave_jumps=0, sequence=False),
    ("Beginner", "harder"): dict(length=(6, 8), max_step=2, direction_changes=2, octave_jumps=0, sequence=False),
    ("Intermediate", "easier"): dict(length=(4, 6), max_step=2, direction_changes=1, octave_jumps=0, sequence=False),
    ("Intermediate", "normal"): dict(length=(6, 8), max_step=3, direction_changes=2, octave_jumps=0, sequence=True),
    ("Intermediate", "harder"): dict(length=(8, 10), max_step=3, direction_changes=3, octave_jumps=1, sequence=True),
    ("Advanced", "easier"): dict(length=(6, 8), max_step=3, direction_changes=2, octave_jumps=0, sequence=True),
    ("Advanced", "normal"): dict(length=(9, 11), max_step=3, direction_changes=3, octave_jumps=1, sequence=True),
    ("Advanced", "harder"): dict(length=(10, 13), max_step=4, direction_changes=4, octave_jumps=2, sequence=True),
}


def _pentatonic_line(
    pcs: set[int],
    *,
    level: str,
    variant: str,
    rng: random.Random,
    key_center: str,
    chord_tone_pcs: set[int],
    anchor_pc: int,
) -> list[str]:
    """Shape a line entirely inside ``pcs`` (the chosen pentatonic collection).

    Every pitch is reached via ``melodic_pattern_engine._step`` - the same
    "walk N members of a pitch-class collection" primitive the shared
    pattern-engine families use - which is what guarantees every note stays
    inside the collection by construction, not by post-hoc filtering.
    Beginner favors small adjacent steps; Intermediate adds short sequenced
    cells; Advanced adds wider intervallic steps, register displacement and
    more direction changes - see ``_PENTATONIC_DIFFICULTY_PROFILE``.
    """
    from improvisation_motif import _note_from_midi

    level_norm = _normalize_motif_level(level)
    tier = str(variant or "normal").strip().lower()
    profile = _PENTATONIC_DIFFICULTY_PROFILE.get(
        (level_norm, tier), _PENTATONIC_DIFFICULTY_PROFILE[("Intermediate", "normal")]
    )
    length = rng.randint(*profile["length"])
    max_step = profile["max_step"]

    center = 67  # G4 - comfortable middle register for any instrument.
    anchor_midi = _nearest_midi_for_pc(center, anchor_pc)
    midis = [anchor_midi]
    direction = 1 if rng.random() < 0.5 else -1
    flips_remaining = profile["direction_changes"]
    cell_deltas: list[int] = []
    use_sequence = bool(profile["sequence"])
    for i in range(length - 1):
        step_mag = rng.randint(1, max(1, max_step))
        if flips_remaining > 0 and rng.random() < 0.45:
            direction *= -1
            flips_remaining -= 1
        if use_sequence and cell_deltas and i >= len(cell_deltas) and i % len(cell_deltas) == 0:
            delta = cell_deltas[i % len(cell_deltas)]
        else:
            delta = direction * step_mag
            if use_sequence and len(cell_deltas) < 3:
                cell_deltas.append(delta)
        midis.append(_step(midis[-1], delta, pcs))
    for _ in range(int(profile["octave_jumps"])):
        if len(midis) > 1:
            idx = rng.randrange(1, len(midis))
            midis[idx] += 12 if rng.random() < 0.5 else -12

    # Chord-tone-aware ending: nudge the last note onto a chord tone that is
    # also in the pentatonic collection, when one exists and isn't already
    # the landing note - a clear, chord-friendly resolution.
    if chord_tone_pcs:
        landing_pcs = {p for p in pcs if p in chord_tone_pcs}
        if landing_pcs and (midis[-1] % 12) not in landing_pcs:
            best = None
            for k in range(1, 7):
                for sign in (1, -1):
                    cand = _step(midis[-1], sign * k, pcs)
                    if cand % 12 in landing_pcs:
                        best = cand
                        break
                if best is not None:
                    break
            if best is not None:
                midis[-1] = best

    return [_note_from_midi(m, key_center) for m in midis]


def _apply_pentatonic_mission(
    motif: dict[str, Any], *, chord: str, key_center: str, level: str, variant: str, rng: random.Random
) -> dict[str, Any]:
    """Improvise using a pentatonic scale that fits the chord.

    The generated line uses only notes from the chosen pentatonic collection
    - proved structurally by the generator (every note is reached by
    stepping inside that collection) and re-checked by the Mission validator.
    """
    relationship = choose_pentatonic_relationship(chord, level=level, variant=variant, rng=rng)
    proot, _kind, scale_notes, label = resolve_pentatonic_choice(chord, key_center, relationship)
    pcs = {_pc(n) for n in scale_notes}
    chord_tone_pcs = _chord_tone_pcs(chord, key_center=key_center)
    anchor_pc = _pc(proot)

    notes = _pentatonic_line(
        pcs,
        level=level,
        variant=variant,
        rng=rng,
        key_center=key_center,
        chord_tone_pcs=chord_tone_pcs,
        anchor_pc=anchor_pc,
    )
    motif["notes"] = notes
    # Relationship, not a literal note set - transpose-safe metadata that
    # rides along through the existing payload transposer untouched, since
    # it is not one of the pitch-bearing fields that transposer rewrites.
    motif["pentatonic_relationship"] = relationship

    level_norm = _normalize_motif_level(level)
    tier = str(variant or "normal").strip().lower()
    if tier == "harder" and level_norm != "Beginner":
        rk, _syms = _rhythm_for_harder(len(notes), rng.randrange(3))
        motif = _apply_rhythm_pattern(motif, rk, len(notes))
        motif["harder_example"] = True
    else:
        motif = apply_engine_rhythm(
            motif, meter=str(motif.get("meter") or "4/4"), level=level_norm, seed=rng.randrange(1_000_000),
        )
    motif["variation_prompt"] = (
        f"Pentatonic: **{label}** — `{' · '.join(scale_notes)}` — fits **{chord}**."
    )
    return sync_motif_midi(motif)
