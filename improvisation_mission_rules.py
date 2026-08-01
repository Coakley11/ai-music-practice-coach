"""Mission constraints applied after base motif generation."""

from __future__ import annotations

import random
from typing import Any

from music_theory import classify_chord_quality, normalize_root, split_chord
from improvisation_motif import (
    _RHYTHM_PATTERNS,
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


def _guide_tones(chord: str, *, key_center: str) -> list[str]:
    tones = chord_tone_names(chord, reference_key=key_center)
    if len(tones) >= 4:
        return [tones[0], tones[1], tones[3]]
    if len(tones) >= 2:
        return [tones[0], tones[1]]
    return tones


def _line_from_pool(pool: list[str], count: int, rng: random.Random) -> list[str]:
    if not pool:
        return []
    out: list[str] = []
    for _ in range(count):
        out.append(pool[rng.randrange(len(pool))])
    return out


def _enforce_chord_tones_only(notes: list[str], allowed: set[int]) -> list[str]:
    out: list[str] = []
    for n in notes:
        if _pc(n) in allowed:
            out.append(n)
        elif out:
            out.append(out[-1])
        elif allowed:
            # fallback: nearest chord tone spelling handled upstream
            pass
    return out or notes[:3]


def _split_rhythm_halves(motif: dict[str, Any], rk_a: str, rk_b: str) -> dict[str, Any]:
    notes = list(motif.get("notes") or [])
    if len(notes) < 4:
        return motif
    mid = len(notes) // 2
    syms_a = list(_RHYTHM_PATTERNS.get(rk_a, _RHYTHM_PATTERNS["quarter-quarter-quarter"]))
    syms_b = list(_RHYTHM_PATTERNS.get(rk_b, _RHYTHM_PATTERNS["eighth-eighth-quarter"]))
    while len(syms_a) < mid:
        syms_a += syms_a
    while len(syms_b) < len(notes) - mid:
        syms_b += syms_b
    syms = syms_a[:mid] + syms_b[: len(notes) - mid]
    updated = dict(motif)
    updated["rhythm_key"] = f"{rk_a}|{rk_b}"
    updated["rhythm_symbols"] = syms
    updated["rhythm"] = " ".join(syms)
    return sync_motif_midi(updated)


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
    guides = _guide_tones(chord, key_center=key_center)
    qual = classify_chord_quality(chord)
    notes = list(motif.get("notes") or [])

    if "chord tone" in low and "only" in low:
        count = max(4, min(8, len(notes) or 6))
        pool = chord_tone_names(chord, reference_key=key_center)
        motif["notes"] = _line_from_pool(pool, count, rng)
        motif["variation_prompt"] = f"Chord tones only on **{chord}** — every note is part of the harmony."
        return sync_motif_midi(motif)

    if "guide tone" in low:
        count = max(6, min(12, len(notes) or 8))
        pool = guides if len(guides) >= 2 else chord_tone_names(chord, reference_key=key_center)[:2]
        motif["notes"] = _line_from_pool(pool, count, rng)
        motif["variation_prompt"] = (
            f"Guide tones (3rd & 7th) on **{chord}** — lean on {', '.join(pool[1:2] + pool[-1:])}."
        )
        return sync_motif_midi(motif)

    if "scalar" in low and "without" in low:
        motif["notes"] = _enforce_chord_tones_only(notes, allowed)[:10]
        motif["variation_prompt"] = "No scalar runs — step only between chord tones."
        return sync_motif_midi(motif)

    if ("dominant" in low or "tension" in low) and qual == "dom":
        pool = guides if len(guides) >= 3 else chord_tone_names(chord, reference_key=key_center)
        tension_line = _line_from_pool(pool, max(6, len(notes)), rng)
        motif["notes"] = tension_line
        motif["variation_prompt"] = (
            f"Dominant tension on **{chord}** — emphasize 3rd and b7, resolve forward on the next change."
        )
        return sync_motif_midi(motif)

    if "motif" in low and "solo" in low:
        if len(notes) >= 3:
            core = notes[:3]
            developed = core + [notes[1], notes[2], notes[0], notes[2], core[0], core[1]]
            motif["notes"] = developed[:12]
        motif["variation_prompt"] = f"Develop this cell through **{chord}** — repeat, then vary one note."
        return sync_motif_midi(motif)

    if "rhythm" in low and "note" in low:
        motif = transform_motif(motif, "rhythmic", key_center=key_center)
        pool = chord_tone_names(chord, reference_key=key_center)[:3]
        motif["notes"] = _line_from_pool(pool, len(motif.get("notes") or []), rng)
        motif["variation_prompt"] = "Rhythm leads — keep pitches simple, change placement every bar."
        return sync_motif_midi(motif)

    if "silence" in low or "rest" in low:
        motif["rhythm"] = "♩ z ♩"
        motif["rhythm_key"] = "quarter-quarter-quarter"
        motif["variation_prompt"] = f"Rest intentionally on **{chord}** — space is part of the phrase."
        return sync_motif_midi(motif)

    if "resolve" in low and "beat 1" in low:
        root = chord_tone_names(chord, reference_key=key_center)[0]
        rest = list(motif.get("notes") or [])[1:5]
        motif["notes"] = [root] + rest
        motif["variation_prompt"] = "Land beat 1 on the root (or strongest chord tone) each phrase."
        return sync_motif_midi(motif)

    if "pattern" in low and "twice" in low:
        keys = ["quarter-quarter-quarter", "eighth-eighth-quarter", "quarter-eighth-eighth"]
        a, b = keys[rng.randrange(len(keys))], keys[(rng.randrange(len(keys)) + 1) % len(keys)]
        if a == b:
            b = keys[(keys.index(a) + 1) % len(keys)]
        motif = _split_rhythm_halves(motif, a, b)
        motif["variation_prompt"] = "Alternate rhythmic shapes — never repeat the same pattern twice in a row."
        return motif

    if "5 notes" in low:
        pool = chord_tone_names(chord, reference_key=key_center)
        motif["notes"] = (pool * 2)[:5]
        motif["variation_prompt"] = "Five-note cell in one register — repeat and transpose the rhythm."
        return sync_motif_midi(motif)

    return sync_motif_midi(motif)
