"""Mission constraints applied after base motif generation."""

from __future__ import annotations

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
    chord_tone_names,
    sync_motif_midi,
    transform_motif,
)


def _pc(note: str) -> int:
    from music_theory import NOTE_TO_MIDI

    root, _ = split_chord(str(note))
    return NOTE_TO_MIDI.get(normalize_root(root), 60) % 12


def _chord_tone_pcs(chord: str, *, key_center: str) -> set[int]:
    return {_pc(n) for n in chord_tone_names(chord, reference_key=key_center)}


def _guide_third_seventh(chord: str, *, key_center: str) -> list[str]:
    tones = chord_tone_names(chord, reference_key=key_center)
    if len(tones) >= 4:
        return [tones[1], tones[3]]
    if len(tones) >= 2:
        return [tones[1]]
    return tones[:1]


def _line_from_pool(pool: list[str], count: int, rng: random.Random) -> list[str]:
    if not pool:
        return []
    return [pool[rng.randrange(len(pool))] for _ in range(count)]


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
        motif["notes"] = _line_from_pool(pool, count, rng)
        motif["variation_prompt"] = f"Chord tones only on **{chord}** — every note is part of the harmony."
        return sync_motif_midi(motif)

    if "guide tone" in low:
        pool = _guide_third_seventh(chord, key_center=key_center)
        count = max(8, min(12, len(notes) or 10))
        motif["notes"] = _line_from_pool(pool, count, rng)
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
        motif["notes"] = _dominant_tension_line(chord, key_center=key_center, rng=rng)
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
            rk = rng.choice(["syncopated-four", "eighth-quart-eighth-eighth", "quarter-eighth-eighth"])
            motif = _apply_rhythm_pattern(motif, rk, count)
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
        tail = _line_from_pool(pool, 5, rng)
        motif["notes"] = [root] + tail[1:5]
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

    return sync_motif_midi(motif)
