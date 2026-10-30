"""Roman numeral harmonic analysis for chords relative to a key center.

Shared by Custom Progression Lab and Composition Studio.
"""

from __future__ import annotations

from typing import Any

from music_theory import (
    CHROMATIC,
    classify_chord_quality,
    is_no_chord_token,
    normalize_chord_for_theory,
    normalize_root,
    split_chord,
    split_key_center,
)

_MAJOR_SCALE_SEMITONES = (0, 2, 4, 5, 7, 9, 11)
_MINOR_SCALE_SEMITONES = (0, 2, 3, 5, 7, 8, 10)

_DEGREE_ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")

_DIATONIC_QUALITY_MAJOR: dict[int, str] = {
    0: "major",
    1: "minor",
    2: "minor",
    3: "major",
    4: "major",
    5: "minor",
    6: "dim",
}
_DIATONIC_QUALITY_MINOR: dict[int, str] = {
    0: "minor",
    1: "dim",
    2: "major",
    3: "minor",
    4: "minor",
    5: "major",
    6: "major",
}

_QUALITY_SUFFIX_MAP: dict[str, str] = {
    "major": "",
    "minor": "",
    "m7": "7",
    "maj7": "maj7",
    "dom": "7",
    "half-dim": "ø7",
    "dim": "°",
    "aug": "+",
    "sus": "sus",
}


def _root_pc(root: str) -> int:
    """Pitch class 0-11 for a chord root spelling."""
    nr = normalize_root(root)
    try:
        return CHROMATIC.index(nr)
    except ValueError:
        return -1


def _find_scale_degree(
    root_pc: int,
    tonic_pc: int,
    mode: str,
    *,
    root_spelling: str = "",
) -> tuple[int, int]:
    """Return (degree_0_based, alteration_semitones) for a root relative to a key.

    ``alteration_semitones`` is 0 for diatonic, -1 for flat, +1 for sharp.
    When both ♭-upper and ♯-lower are valid, *root_spelling* disambiguates:
    a sharp-spelled root (F#) → ♯IV; a flat-spelled root (Bb) → ♭VII.
    Default (natural or unknown) prefers ♭ of the upper degree.
    """
    interval = (root_pc - tonic_pc) % 12
    scale = _MAJOR_SCALE_SEMITONES if mode == "major" else _MINOR_SCALE_SEMITONES
    if interval in scale:
        return scale.index(interval), 0
    flat_match: tuple[int, int] | None = None
    sharp_match: tuple[int, int] | None = None
    for deg, semi in enumerate(scale):
        if (semi - 1) % 12 == interval:
            flat_match = (deg, -1)
        if (semi + 1) % 12 == interval:
            sharp_match = (deg, +1)
    if flat_match and sharp_match:
        if "#" in str(root_spelling):
            return sharp_match
        return flat_match
    if flat_match:
        return flat_match
    if sharp_match:
        return sharp_match
    best_deg = 0
    best_diff = 99
    for deg, semi in enumerate(scale):
        diff = (interval - semi) % 12
        if diff > 6:
            diff = 12 - diff
        if diff < best_diff:
            best_diff = diff
            best_deg = deg
    alt = (interval - scale[best_deg]) % 12
    if alt > 6:
        alt = alt - 12
    return best_deg, alt


def _case_roman(roman: str, quality: str) -> str:
    """Apply case convention: uppercase for major/aug/dom, lowercase for minor/dim."""
    if quality in ("minor", "m7", "half-dim", "dim"):
        return roman.lower()
    return roman.upper()


def _alteration_prefix(alt: int) -> str:
    if alt == -1:
        return "♭"
    if alt == 1:
        return "♯"
    if alt < -1:
        return "♭" * abs(alt)
    if alt > 1:
        return "♯" * alt
    return ""


def _extension_suffix(chord_suffix: str) -> str:
    """Extract numeric extension (7, 9, 11, 13, 6, add9, sus2, sus4) from the chord suffix."""
    low = str(chord_suffix or "").lower()
    if "add9" in low:
        return "add9"
    if "sus2" in low:
        return "sus2"
    if "sus4" in low:
        return "sus4"
    if "13" in low:
        return "13"
    if "11" in low:
        return "11"
    if "9" in low and "6" not in low:
        return "9"
    if "7" in low:
        return "7"
    if "6" in low:
        return "6"
    return ""


def _bass_degree_label(bass_root: str, tonic_pc: int, mode: str) -> str:
    """Roman numeral for a slash bass note."""
    bass_pc = _root_pc(bass_root)
    if bass_pc < 0:
        return ""
    deg, alt = _find_scale_degree(bass_pc, tonic_pc, mode, root_spelling=bass_root)
    prefix = _alteration_prefix(alt)
    return prefix + _DEGREE_ROMAN[deg]


def chord_to_roman(chord: str | Any, key: str) -> str:
    """Convert a chord symbol to its Roman numeral analysis relative to *key*.

    Returns an empty string for N.C., unparseable, or empty chords.

    Examples (key of C major):
        C     → I
        Dm    → ii
        G7    → V7
        Am7   → vi7
        Bdim  → vii°
        C/E   → I/III   (chord-tone bass → degree label)
        F/A   → IV/VI
        Bb    → ♭VII    (chromatic)
    """
    raw = str(chord or "").strip()
    if not raw or is_no_chord_token(raw):
        return ""

    norm = normalize_chord_for_theory(raw)
    if not norm:
        return ""

    tonic_str, mode = split_key_center(str(key or "C").strip() or "C")
    tonic_pc = _root_pc(tonic_str)
    if tonic_pc < 0:
        return ""

    slash_bass = ""
    main_chord = norm
    if "/" in norm:
        parts = norm.split("/", 1)
        main_chord = parts[0].strip()
        bass_str = parts[1].strip()
        if bass_str:
            bass_root, _ = split_chord(bass_str)
            bass_root_norm = normalize_root(bass_root) if bass_root else ""
            if bass_root_norm and bass_root_norm in CHROMATIC:
                slash_bass = _bass_degree_label(bass_root, tonic_pc, mode)

    root, suffix = split_chord(main_chord)
    root_pc = _root_pc(root)
    if root_pc < 0:
        return ""

    quality = classify_chord_quality(main_chord)
    deg, alt = _find_scale_degree(root_pc, tonic_pc, mode, root_spelling=root)

    prefix = _alteration_prefix(alt)
    roman = _DEGREE_ROMAN[deg]
    roman = _case_roman(roman, quality)

    qual_suffix = _QUALITY_SUFFIX_MAP.get(quality, "")
    ext = _extension_suffix(suffix)
    if ext and qual_suffix not in ("°", "+", "ø7", "sus", "maj7"):
        qual_suffix = ext
    elif ext and qual_suffix == "maj7":
        qual_suffix = "maj" + ext
    elif ext and qual_suffix in ("°",):
        if "7" in ext:
            qual_suffix = "°7"
    elif ext and qual_suffix == "ø7":
        pass
    elif ext and qual_suffix == "+":
        if "7" in ext:
            qual_suffix = "+7"
    elif ext and qual_suffix == "sus":
        qual_suffix = "sus" + ext.replace("sus", "")

    result = prefix + roman + qual_suffix
    if slash_bass:
        result += "/" + slash_bass
    return result


def analyze_progression(
    chords: list[str | Any],
    key: str,
) -> list[str]:
    """Return Roman numeral labels for a list of chord symbols."""
    return [chord_to_roman(c, key) for c in chords]


def chord_with_roman(chord: str | Any, key: str) -> dict[str, str]:
    """Return dict with 'chord' and 'roman' for a single chord."""
    c = str(chord or "").strip()
    return {
        "chord": c,
        "roman": chord_to_roman(c, key),
    }
