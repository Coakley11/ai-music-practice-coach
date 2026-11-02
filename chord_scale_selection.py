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




# ---------------------------------------------------------------------------------------------
# Mission scale selection (Issue 39): a deliberate, explainable choice of ONE pitch collection per
# Mission example, from chord quality + alterations, the next chord (resolution), the song's key and
# mode, genre/feel, player level, and the Mission's own focus. Level never forces a "fancier" scale.
# ---------------------------------------------------------------------------------------------

_LETTERS = "CDEFGAB"
_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SCALE_LABEL = {
    "ionian": "major", "lydian": "Lydian", "mixolydian": "Mixolydian", "dorian": "Dorian", "aeolian": "natural minor",
    "phrygian": "Phrygian", "locrian": "Locrian", "locrian_natural_2": "Locrian natural 2", "melodic_minor": "melodic minor",
    "harmonic_minor": "harmonic minor", "lydian_dominant": "Lydian dominant", "altered": "altered",
    "phrygian_dominant": "Phrygian dominant", "whole_tone": "whole-tone", "diminished_half_whole": "half-whole diminished",
    "diminished_whole_half": "whole-half diminished",
}
_JAZZ_STYLES = ("jazz", "bebop", "swing", "bossa", "fusion", "latin", "samba", "gypsy")
_BLUESY_STYLES = ("blues", "rock", "funk", "country", "gospel", "soul", "r&b", "shuffle", "boogie")
# Missions whose line is chord tones only: no scale is ever introduced for them.
_CHORD_TONE_MISSIONS = ("chord tone", "guide tone", "5 notes", "motif", "silence", "beat 1")


def _spell_collection(root_name: str, scale_key: str) -> list[str]:
    """Spell a scale on ``root_name``: 7-note scales get one letter per degree (B altered = B C D Eb F G A);
    others are spelled by the root's accidental preference."""
    steps = SCALES[scale_key]
    root_name = str(root_name or "C").strip()
    root_letter = root_name[0].upper()
    root_pc = pitch_class_from_spelled_note(root_name) % 12
    if len(steps) == 7:
        out = []
        base = _LETTERS.index(root_letter)
        for i, st in enumerate(steps):
            letter = _LETTERS[(base + i) % 7]
            diff = ((root_pc + st) % 12 - _LETTER_PC[letter] + 6) % 12 - 6
            if -2 <= diff <= 2:
                out.append(letter + {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}[diff])
            else:
                out.append("")
        if all(out):
            return out
    from music_theory import spell_note_in_key

    flat = "b" in root_name[1:] or root_name in ("F",)
    ref = root_name + ("" if True else "")
    return [spell_note_in_key((root_pc + st) % 12, ref) for st in steps]


def _style_class(style: str) -> str:
    low = str(style or "").lower()
    if any(t in low for t in _BLUESY_STYLES):
        return "bluesy"
    if any(t in low for t in _JAZZ_STYLES):
        return "jazz"
    return "other"


def _resolves_to_minor(chord: str, next_chord: str, key_center: str) -> bool:
    """A dominant whose next chord is the minor chord a fifth below (a perfect-fourth up), or, with no next
    chord known, the V of a minor key."""
    if next_chord:
        try:
            nq = chord_family(next_chord)
            if nq in ("minor", "m7", "m6", "mmaj7") and (_root_pc(next_chord) - _root_pc(chord)) % 12 == 5:
                return True
            return False
        except Exception:
            return False
    tonic, mode = split_key_center(key_center or "C")
    return mode == "minor" and (pitch_class_from_spelled_note(tonic) - _root_pc(chord)) % 12 == 5


def select_mission_scale(
    chord: str,
    *,
    key_center: str = "C",
    next_chord: str = "",
    level: str = "Intermediate",
    style: str = "",
    mission: str = "",
) -> dict | None:
    """Choose the pitch collection for a scale-based Mission example, or None for chord-tone Missions.

    Returns ``{"key", "label", "root", "notes", "pcs", "reason"}``. The reason says WHY (shown to the player).
    Conservative by design: plain dominants stay Mixolydian unless the context (resolution to a minor chord,
    jazz feel, level >= Intermediate/Advanced) justifies Phrygian dominant / altered; Blues-family styles never
    turn altered from level alone; a chord symbol that asks for an alteration always wins.
    """
    low = str(mission or "").lower()
    if any(t in low for t in _CHORD_TONE_MISSIONS):
        return None
    base = chord_scale_name(chord, key_center, style=style)
    fam = chord_family(chord)
    lvl = str(level or "Intermediate").strip().title()
    cls = _style_class(style)
    reason = f"fits the {chord} chord tones"
    pick = base
    if fam == "dom" and base == "mixolydian":
        minor_target = _resolves_to_minor(chord, next_chord, key_center)
        tension = "tension" in low or "dominant" in low
        if cls == "bluesy":
            reason = f"{chord} is a bluesy dominant: Mixolydian keeps it conventional"
        elif cls == "jazz" and lvl == "Advanced" and (minor_target or tension):
            pick = "altered"
            reason = f"Advanced jazz: {chord} resolves to a minor chord, so altered tensions lead into it" if minor_target else f"Advanced jazz dominant tension on {chord}"
        elif minor_target and lvl in ("Intermediate", "Advanced"):
            pick = "phrygian_dominant"
            reason = f"{chord} resolves to a minor chord: the b9 and b13 of Phrygian dominant point at it"
        else:
            reason = f"{chord} is an ordinary dominant: Mixolydian"
    elif base != "mixolydian" and fam == "dom":
        reason = f"the {chord} symbol asks for {_SCALE_LABEL[base]} colour"
    root_name = _spelled_root(chord)
    notes = _spell_collection(root_name, pick)
    pcs = sorted({(pitch_class_from_spelled_note(root_name) + st) % 12 for st in SCALES[pick]})
    return {
        "key": pick,
        "label": f"{root_name} {_SCALE_LABEL[pick]}",
        "root": root_name,
        "notes": notes,
        "pcs": pcs,
        "reason": reason,
    }


def scale_pcs_for(scale_key: str, chord: str) -> set[int]:
    """Pitch classes of ``scale_key`` built on ``chord``'s root (empty for an unknown scale)."""
    if scale_key not in SCALES:
        return set()
    root = pitch_class_from_spelled_note(_spelled_root(chord)) % 12
    return {(root + st) % 12 for st in SCALES[scale_key]}


def scale_names_for(scale_key: str, chord: str) -> dict[int, str]:
    """{pitch class: spelled note} of ``scale_key`` on ``chord``'s root."""
    if scale_key not in SCALES:
        return {}
    notes = _spell_collection(_spelled_root(chord), scale_key)
    return {pitch_class_from_spelled_note(n) % 12: n for n in notes}


def scale_label_for(scale_key: str, chord: str) -> str:
    if scale_key not in SCALES:
        return ""
    return f"{_spelled_root(chord)} {_SCALE_LABEL[scale_key]}"


def _spelled_root(chord: str) -> str:
    tones = spell_chord_tones(chord)
    return tones[0] if tones else "C"


__all__ = ["SCALES", "blue_note_pcs", "chord_family", "chord_scale_name", "chord_scale_pcs", "select_mission_scale", "scale_pcs_for", "scale_names_for", "scale_label_for"]
