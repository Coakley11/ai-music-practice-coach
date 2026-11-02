"""Harmony-aware chord-scale selection for generated practice melodies.

A progression is not one scale. Each chord gets the scale that (1) contains every one of its chord tones
(Am6's F# is a chord tone, so it needs Dorian or melodic minor, never natural minor), and (2) stays closest to
the key the song is in, so the melody does not wander outside the harmony without a reason. Colourful sounds
(Lydian dominant, altered, whole-tone, diminished, phrygian dominant) are only offered when the chord symbol
asks for them (``7#11``, ``7alt``, ``7b9``, ``aug`` ...) - never merely because the player picked Advanced.

Pure pitch-class logic: no Streamlit, no randomness.
"""

from __future__ import annotations

import re

from music_theory import classify_chord_quality, pitch_class_from_spelled_note, spell_chord_tones, split_key_center

SCALES: dict[str, tuple[int, ...]] = {
    "ionian": (0, 2, 4, 5, 7, 9, 11),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "locrian_natural_2": (0, 2, 3, 5, 6, 8, 10),
    "melodic_minor": (0, 2, 3, 5, 7, 9, 11),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "lydian_dominant": (0, 2, 4, 6, 7, 9, 10),
    "altered": (0, 1, 3, 4, 6, 8, 10),
    "phrygian_dominant": (0, 1, 4, 5, 7, 8, 10),
    "whole_tone": (0, 2, 4, 6, 8, 10),
    "diminished_half_whole": (0, 1, 3, 4, 6, 7, 9, 10),
    "diminished_whole_half": (0, 2, 3, 5, 6, 8, 9, 11),
}

# Preference order inside each quality (earlier wins ties on closeness to the key).
_BY_QUALITY: dict[str, tuple[str, ...]] = {
    "major": ("ionian", "mixolydian", "lydian"),
    "maj7": ("ionian", "lydian"),
    "sixth": ("ionian", "lydian"),
    "minor": ("dorian", "aeolian", "phrygian", "melodic_minor", "harmonic_minor"),
    "m6": ("dorian", "melodic_minor"),
    "m7": ("dorian", "aeolian", "phrygian"),
    "mmaj7": ("melodic_minor", "harmonic_minor"),
    "dom": ("mixolydian",),
    "sus": ("mixolydian", "dorian"),
    "half-dim": ("locrian", "locrian_natural_2"),
    "dim": ("diminished_whole_half",),
    "aug": ("whole_tone", "lydian_dominant"),
}


def _suffix(chord: str) -> str:
    from music_theory import normalize_chord_for_theory, split_chord

    head = normalize_chord_for_theory(chord).split("/", 1)[0].strip() or str(chord or "")
    return str(split_chord(head)[1] or "")


def _root_pc(chord: str) -> int:
    tones = spell_chord_tones(chord)
    return pitch_class_from_spelled_note(tones[0]) if tones else 0


def _key_pcs(key_center: str) -> set[int]:
    tonic, mode = split_key_center(key_center or "C")
    t = pitch_class_from_spelled_note(tonic)
    steps = SCALES["aeolian"] if mode == "minor" else SCALES["ionian"]
    pcs = {(t + s) % 12 for s in steps}
    if mode == "minor":                      # harmonic/melodic minor raise the 7th/6th: part of the key's sound
        pcs |= {(t + 11) % 12}
    return pcs


def chord_family(chord: str) -> str:
    """Finer bucket than ``classify_chord_quality``: separates m6 / mMaj7 / 6 from plain minor / maj7."""
    suf = _suffix(chord)
    low = suf.lower()
    q = classify_chord_quality(chord)
    if re.search(r"(?:m|min|mi|-)\s*\(?\s*(?:maj|Maj|ma|M)7", suf):
        return "mmaj7"
    if re.search(r"(?<![0-9#b♯♭])6(?:9|(?![0-9]))", suf) and "7" not in low:
        return "m6" if q == "minor" else "sixth"
    return q


def _alterations(chord: str) -> set[str]:
    low = _suffix(chord).lower().replace("♯", "#").replace("♭", "b")
    out = set()
    for tag in ("b9", "#9", "#11", "b13", "#5", "b5", "alt"):
        if tag in low:
            out.add(tag)
    return out


def chord_scale_name(chord: str, key_center: str = "C", *, style: str = "") -> str:
    """The scale (a key of ``SCALES``) that fits ``chord`` in ``key_center``."""
    fam = chord_family(chord)
    alts = _alterations(chord)
    root = _root_pc(chord)
    tones = {pitch_class_from_spelled_note(t) % 12 for t in spell_chord_tones(chord)}
    if fam == "dom":
        if "alt" in alts or ("b9" in alts and "#9" in alts):
            return "altered"
        if "b9" in alts or "b13" in alts:
            tonic, mode = split_key_center(key_center or "C")
            minor_target = mode == "minor"
            return "phrygian_dominant" if minor_target and "b9" in alts and "#9" not in alts else "altered"
        if "#11" in alts or "b5" in alts:
            return "lydian_dominant" if "b5" not in alts else "whole_tone" if "#5" in alts else "altered"
        if "#5" in alts:
            return "whole_tone"
    candidates = _BY_QUALITY.get(fam) or _BY_QUALITY["major"]
    key = _key_pcs(key_center)
    best, best_score = candidates[0], None
    for rank, name in enumerate(candidates):
        pcs = {(root + s) % 12 for s in SCALES[name]}
        if not tones <= pcs:                        # every chord tone (incl. the 6th) must be in the scale
            continue
        outside = len(pcs - key)                    # notes foreign to the song's key
        score = (outside, rank)
        if best_score is None or score < best_score:
            best, best_score = name, score
    return best


def chord_scale_pcs(chord: str, key_center: str = "C", *, style: str = "") -> list[int]:
    """Sorted pitch classes of the chord's scale."""
    root = _root_pc(chord)
    return sorted({(root + s) % 12 for s in SCALES[chord_scale_name(chord, key_center, style=style)]})


def blue_note_pcs(chord: str, style: str = "") -> list[int]:
    """b3 / b5 colour for dominant and minor chords in a Blues style (empty otherwise)."""
    if "blues" not in str(style or "").lower():
        return []
    fam = chord_family(chord)
    root = _root_pc(chord)
    if fam in ("dom", "major"):
        return [(root + 3) % 12, (root + 6) % 12]
    if fam in ("minor", "m7", "m6"):
        return [(root + 6) % 12]
    return []


__all__ = ["SCALES", "blue_note_pcs", "chord_family", "chord_scale_name", "chord_scale_pcs"]
