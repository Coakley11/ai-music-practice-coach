"""Roman numeral harmonic analysis for chords relative to a key center.

Shared by Custom Progression Lab and Composition Studio.
"""

from __future__ import annotations

import re
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
    "minmaj7": "(maj7)",
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
    if mode == "minor":
        # Minor keys borrow the raised 6th/7th (melodic/harmonic minor): the root a major
        # 6th / major 7th above the tonic is a raised degree, never a "flattened" 7th/tonic.
        if interval == 11:
            return 6, +1
        if interval == 9:
            return 5, +1
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
    if quality in ("minor", "m7", "half-dim", "dim", "minmaj7"):
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


def _roman_quality(main_chord: str) -> str:
    """Quality bucket for Roman analysis.

    Wraps ``classify_chord_quality`` and corrects spellings it mis-buckets:
    ``CΔ7`` (maj7), ``Cdom7`` (dom), ``Cadd9`` (plain major, not dominant) and
    ``Cmmaj7`` / ``Cm(maj7)`` (minor-major seventh).
    """
    _, suffix = split_chord(main_chord.split("/", 1)[0])
    low = str(suffix or "").lower().replace(" ", "")
    raw = str(suffix or "")
    if "Δ" in raw or "△" in raw:
        return "maj7"
    if low.startswith("dom"):
        return "dom"
    if low in {"mmaj7", "m(maj7)", "minmaj7", "mmaj9", "m(maj9)"}:
        return "minmaj7"
    if low.startswith("add") or low.startswith("madd"):
        return "minor" if low.startswith("madd") else "major"
    return classify_chord_quality(main_chord)


def _altered_extension(low: str) -> str:
    """Return e.g. ``7♭9`` / ``7♯9`` / ``7alt`` for altered dominants, else ``""``."""
    if "alt" in low and "7" in low:
        return "7alt"
    m = re.search(r"7((?:[b#]\d+)+)", low)
    if m:
        return "7" + m.group(1).replace("b", "♭").replace("#", "♯")
    return ""


def _extension_suffix(chord_suffix: str) -> str:
    """Extract numeric extension (7, 9, 11, 13, 6, add9, sus2, sus4) from the chord suffix."""
    low = str(chord_suffix or "").lower()
    alt_ext = _altered_extension(low)
    if alt_ext:
        return alt_ext
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

    quality = _roman_quality(main_chord)
    deg, alt = _find_scale_degree(root_pc, tonic_pc, mode, root_spelling=root)

    prefix = _alteration_prefix(alt)
    roman = _DEGREE_ROMAN[deg]
    roman = _case_roman(roman, quality)

    qual_suffix = _QUALITY_SUFFIX_MAP.get(quality, "")
    ext = _extension_suffix(suffix)
    if ext and qual_suffix not in ("°", "+", "ø7", "sus", "maj7", "(maj7)"):
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

    if (
        mode == "minor"
        and deg == 6
        and alt == 1
        and quality in {"dim", "half-dim"}
    ):
        prefix = ""  # harmonic-minor leading-tone chord: vii° / viiø7, not ♯vii°
    result = prefix + roman + qual_suffix
    if slash_bass:
        result += "/" + slash_bass
    return result


DIM_MARK = "°"


def _parse_for_analysis(chord: str | Any, key: str) -> dict[str, Any] | None:
    """Structured parse of one chord relative to *key* (None for N.C./unparseable)."""
    raw = str(chord or "").strip()
    if not raw or is_no_chord_token(raw):
        return None
    norm = normalize_chord_for_theory(raw)
    if not norm:
        return None
    tonic_str, mode = split_key_center(str(key or "C").strip() or "C")
    tonic_pc = _root_pc(tonic_str)
    if tonic_pc < 0:
        return None
    main = norm.split("/", 1)[0].strip()
    root, suffix = split_chord(main)
    root_pc = _root_pc(root)
    if root_pc < 0:
        return None
    bass_pc = root_pc
    if "/" in norm:
        bass_str = norm.split("/", 1)[1].strip()
        b_root, _ = split_chord(bass_str) if bass_str else ("", "")
        b_pc = _root_pc(b_root) if b_root else -1
        if b_pc >= 0:
            bass_pc = b_pc
    deg, alt = _find_scale_degree(root_pc, tonic_pc, mode, root_spelling=root)
    quality = _roman_quality(main)
    table = _DIATONIC_QUALITY_MAJOR if mode == "major" else _DIATONIC_QUALITY_MINOR
    return {
        "chord": raw,
        "mode": mode,
        "tonic_pc": tonic_pc,
        "root_pc": root_pc,
        "root_name": root,
        "bass_pc": bass_pc,
        "degree": deg,
        "alt": alt,
        "quality": quality,
        "diatonic_quality": table[deg],
        "interval": (root_pc - tonic_pc) % 12,
        "suffix": suffix,
        "plain_roman": chord_to_roman(raw, key),
    }


def _target_numeral(pc: int, p: dict[str, Any], spelling: str = "") -> tuple[str, int] | None:
    """(numeral cased by the key's diatonic quality, degree) for a resolution target pc.

    None when the target is chromatic or a diminished degree (secondary
    dominants to vii° are not labelled).
    """
    deg, alt = _find_scale_degree(pc, p["tonic_pc"], p["mode"], root_spelling=spelling)
    if alt != 0:
        return None
    table = _DIATONIC_QUALITY_MAJOR if p["mode"] == "major" else _DIATONIC_QUALITY_MINOR
    dq = table[deg]
    if dq == "dim":
        return None
    return _case_roman(_DEGREE_ROMAN[deg], dq), deg


def _dominant_extension(suffix: str) -> str:
    ext = _extension_suffix(suffix)
    return ext if ext and ext[0].isdigit() else "7"


def analyze_progression_detailed(
    chords: list[str | Any],
    key: str,
) -> list[dict[str, Any]]:
    """Context-aware Roman analysis of a progression.

    Each row has ``chord``, ``roman`` (context-aware label), ``plain_roman``
    (context-free label, same as :func:`chord_to_roman`), ``role`` and, for
    chords that lead somewhere, ``target_index`` / ``target_roman``.

    Roles: ``diatonic``, ``dominant`` (the key's own V), ``secondary_dominant``,
    ``tritone_sub``, ``leading_tone_dim``, ``borrowed`` (chromatic degree or
    changed quality), ``none`` (N.C./unparseable).

    Secondary dominants are derived from the local resolution: a dominant-quality
    chord (or chromatic major triad) whose root is a fifth above the next chord's
    root is ``V7/x`` with ``x`` = that chord's diatonic degree (cased by the key's
    diatonic quality for the degree, e.g. ``V7/ii``, ``V7/V``). With no resolving
    chord after it, a dominant seventh on a degree that is not diatonically major
    is still labelled by its root (``D7`` in C = ``V7/V``, never ``ii7``/``II7``).
    """
    parsed = [_parse_for_analysis(c, key) for c in chords]
    rows: list[dict[str, Any]] = []
    for i, p in enumerate(parsed):
        raw = str(chords[i] or "").strip()
        if p is None:
            rows.append({"chord": raw, "roman": "", "plain_roman": "", "role": "none",
                         "target_index": None, "target_roman": ""})
            continue
        nxt = parsed[i + 1] if i + 1 < len(parsed) else None
        roman = p["plain_roman"]
        role = "diatonic"
        target_index: int | None = None
        target_roman = ""
        q = p["quality"]
        interval = p["interval"]
        mode = p["mode"]
        is_dom = q == "dom"
        is_major_tri = q == "major" and not re.search(r"[679]|11|13", p["suffix"] or "")
        diatonic_root = p["alt"] == 0
        major_diatonic_root = diatonic_root and p["diatonic_quality"] == "major"
        next_root = nxt["root_pc"] if nxt else None
        next_bass = nxt["bass_pc"] if nxt else None
        next_spell = nxt["root_name"] if nxt else ""
        resolves_down_fifth = nxt is not None and next_root == (p["root_pc"] + 5) % 12
        decided = False

        # Tritone substitute: dominant a half step above a diatonic target.
        if is_dom and nxt is not None and next_root == (p["root_pc"] - 1) % 12 and interval != 0:
            tgt = _target_numeral(next_root, p, next_spell)
            if tgt is not None:
                if tgt[1] != 0:
                    roman = f"subV{_dominant_extension(p['suffix'])}/{tgt[0]}"
                role, target_index, target_roman, decided = "tritone_sub", i + 1, tgt[0], True

        # Leading-tone diminished: root a half step below the next bass/root.
        if not decided and q == "dim" and nxt is not None and next_bass == (p["root_pc"] + 1) % 12:
            tgt = _target_numeral(next_bass, p, next_spell if next_bass == next_root else "")
            if tgt is not None and tgt[1] != 0:
                seven = "7" if "7" in (p["suffix"] or "") else ""
                roman = f"vii{DIM_MARK}{seven}/{tgt[0]}"
                role, target_index, target_roman, decided = "leading_tone_dim", i + 1, tgt[0], True

        # Secondary dominant (V7/x or V/x).
        if (
            not decided
            and (is_dom or is_major_tri)
            and interval not in (0, 7)
            and p["bass_pc"] == p["root_pc"]
        ):
            tgt_pc = (p["root_pc"] + 5) % 12
            tgt = _target_numeral(tgt_pc, p, next_spell if resolves_down_fifth else "")
            if (
                tgt is not None
                and mode == "minor"
                and tgt[1] == 4
                and resolves_down_fifth
                and nxt is not None
                and nxt["quality"] in {"major", "dom"}
            ):
                tgt = ("V", 4)  # B7 -> E(7) in a minor key: V7/V (harmonic-minor V), not V7/v
            if tgt is not None and tgt[1] != 0:
                if is_dom:
                    eligible = resolves_down_fifth or (diatonic_root and not major_diatonic_root)
                else:
                    eligible = resolves_down_fifth and diatonic_root and not major_diatonic_root
                if eligible:
                    ext = _dominant_extension(p["suffix"]) if is_dom else ""
                    roman = f"V{ext}/{tgt[0]}"
                    role, decided, target_roman = "secondary_dominant", True, tgt[0]
                    if resolves_down_fifth:
                        target_index = i + 1

        if not decided:
            if interval == 7 and q in {"dom", "major", "sus"}:
                role = "dominant"
                if nxt is not None and next_root == p["tonic_pc"]:
                    target_index = i + 1
                    target_roman = "I" if mode == "major" else "i"
            elif interval == 7 and mode == "minor" and q == "minor":
                role = "diatonic"  # natural-minor v
            elif p["alt"] != 0:
                role = "borrowed"
            elif q in {"major", "minor"} and q != p["diatonic_quality"]:
                role = "borrowed"
            elif is_dom and interval != 7:
                role = "borrowed"  # e.g. C7 / F7 in C: dominant colour on I or IV
        rows.append({
            "chord": raw,
            "roman": roman,
            "plain_roman": p["plain_roman"],
            "role": role,
            "degree": p["degree"],
            "alt": p["alt"],
            "quality": q,
            "target_index": target_index,
            "target_roman": target_roman,
        })
    return rows


def analyze_progression(
    chords: list[str | Any],
    key: str,
) -> list[str]:
    """Return context-aware Roman numeral labels for a list of chord symbols.

    Unlike :func:`chord_to_roman` (single chord, no context) this reads each
    chord's local resolution, so ``Cmaj7 | Em7 | D7 | G7`` in C is
    ``Imaj7 iii7 V7/V V7`` rather than ``... II7 ...``.
    """
    return [r["roman"] for r in analyze_progression_detailed(chords, key)]


def chord_with_roman(chord: str | Any, key: str) -> dict[str, str]:
    """Return dict with 'chord' and 'roman' for a single chord."""
    c = str(chord or "").strip()
    return {
        "chord": c,
        "roman": chord_to_roman(c, key),
    }
