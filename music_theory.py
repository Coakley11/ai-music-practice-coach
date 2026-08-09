"""Shared chord/key utilities for the practice coach and song catalog."""

from typing import Any

import re

COMMON_KEYS = [
    "C", "Db", "D", "Eb", "E", "F",
    "Gb", "G", "Ab", "A", "Bb", "B",
]

# Both enharmonic spellings for each black-key pitch class (musician-friendly dropdowns).
ENHARMONIC_MAJOR_KEYS = [
    "C", "Db", "C#", "D", "Eb", "D#", "E", "F", "Gb", "F#", "G", "Ab", "G#", "A", "Bb", "A#", "B",
]
ENHARMONIC_MINOR_KEYS = [
    "Cm", "Dbm", "C#m", "Dm", "D#m", "Ebm", "Em", "Fm", "Gbm", "F#m", "Gm", "G#m", "Abm", "Am", "A#m", "Bbm", "Bm",
]

# Major + parallel minor centers (legacy combined list).
PRACTICE_KEYS = [k for pair in zip(COMMON_KEYS, [f"{k}m" for k in COMMON_KEYS]) for k in pair]
MAJOR_PRACTICE_KEYS = list(COMMON_KEYS)
MINOR_PRACTICE_KEYS = [f"{k}m" for k in COMMON_KEYS]

_FLAT_PITCH_CLASSES: tuple[str, ...] = (
    "C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B",
)
_SHARP_PITCH_CLASSES: tuple[str, ...] = (
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
)
_NATURAL_PITCH_CLASSES: frozenset[str] = frozenset({"C", "D", "E", "F", "G", "A", "B"})

CHROMATIC = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B",
]

FLAT_TO_SHARP = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
}

NOTE_TO_MIDI = {
    "C": 60, "C#": 61, "Db": 61,
    "D": 62, "D#": 63, "Eb": 63,
    "E": 64,
    "F": 65, "F#": 66, "Gb": 66,
    "G": 67, "G#": 68, "Ab": 68,
    "A": 69, "A#": 70, "Bb": 70,
    "B": 71,
}


def normalize_root(root):
    return FLAT_TO_SHARP.get(root, root)


# Circle-of-fifths side — used when the key name has no #/b (e.g. E minor → sharp family).
_SHARP_SIDE_MAJOR: frozenset[str] = frozenset(
    normalize_root(k) for k in ("G", "D", "A", "E", "B", "F#", "C#")
)
_FLAT_SIDE_MAJOR: frozenset[str] = frozenset(
    normalize_root(k) for k in ("F", "Bb", "Eb", "Ab", "Db", "Gb")
)
_SHARP_SIDE_MINOR: frozenset[str] = frozenset(
    normalize_root(k.rstrip("m")) for k in ("Em", "Bm", "F#m", "C#m", "G#m", "D#m", "A#m", "Am")
)
_FLAT_SIDE_MINOR: frozenset[str] = frozenset(
    normalize_root(k.rstrip("m")) for k in ("Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm", "Abm")
)


# Tokens (case-insensitive, dot/space-tolerant) that should be treated as
# *no chord / tacet* bars: harmony instruments lay out, drums/percussion
# carry the groove. ``"N.C."`` is the lead-sheet convention; we also
# accept a handful of plain variants and an empty string.
_NO_CHORD_TOKENS = {"N.C.", "NC", "N.C", "N/C", "(N.C.)", "TACET", "—", "-", ""}


def is_no_chord_token(chord) -> bool:
    """Return True for ``N.C.``-style "no chord / tacet" bars.

    Recognises the lead-sheet convention ``N.C.`` plus common variants
    (``NC``, ``N/C``, ``Tacet``, em/en dashes, empty string). The check
    is case-insensitive and tolerant of surrounding whitespace and
    parentheses so chart authors can write ``"N.C."``, ``"(N.C.)"``,
    ``"nc"``, etc., interchangeably.
    """
    if chord is None:
        return False
    raw = str(chord).strip()
    if not raw:
        return False  # blank cells are treated as "missing", not tacet
    cleaned = raw.replace(" ", "").upper()
    if cleaned in _NO_CHORD_TOKENS:
        return True
    return cleaned.strip("()") in _NO_CHORD_TOKENS


def split_chord(chord):
    chord = str(chord)
    if len(chord) >= 2 and chord[1] in ["b", "#"]:
        return chord[:2], chord[2:]
    return chord[:1], chord[1:]


_KEY_CENTER_RE = re.compile(
    r"^(?P<root>[A-Ga-g](?:#|b)?)(?:(?P<minor>m(?!aj)|min|minor))?$",
    re.IGNORECASE,
)


def split_key_center(key: str) -> tuple[str, str]:
    """Parse a key-center token into (tonic spelling, major|minor) — not a chord quality suffix."""
    text = str(key or "C").strip() or "C"
    if text.lower().endswith(" minor"):
        text = text[: -len(" minor")].strip() or "C"
        mode = "minor"
    else:
        mode = ""
    compact = text.replace(" ", "")
    m = _KEY_CENTER_RE.match(compact)
    if m:
        root = str(m.group("root") or "C")
        root = root[0].upper() + root[1:]
        if not mode:
            mode = "minor" if m.group("minor") else "major"
        return root, mode
    root, suffix = split_chord(compact)
    root = str(root or "C")
    root = root[0].upper() + root[1:] if root else "C"
    sl = str(suffix or "").lower()
    if not mode:
        if sl.startswith("maj"):
            mode = "major"
        elif sl.startswith("m"):
            mode = "minor"
        else:
            mode = "major"
    return root, mode


def key_center_token(tonic: str, mode: str) -> str:
    """Structured tonic + mode → sidebar token (Dm, D, etc.)."""
    t = str(tonic or "C").strip() or "C"
    t = t[0].upper() + t[1:] if len(t) > 1 else t.upper()
    if str(mode or "major").lower() == "minor":
        if t.lower().endswith("m") and "maj" not in t.lower():
            return t
        return f"{t}m"
    return t.rstrip("m") if t.lower().endswith("m") and len(t) > 1 else t


def format_key_label_from_parts(tonic: str, mode: str) -> str:
    """Human label: D + minor → 'Dm' style display for UI (not D#)."""
    token = key_center_token(tonic, mode)
    if str(mode or "major").lower() == "minor":
        root, _ = split_key_center(token)
        return f"{root} minor"
    root, _ = split_key_center(token)
    return f"{root} major"


_BAR_WEIGHT_SUFFIX = re.compile(
    r"^(?P<chord>.+):(?P<weight>\d+(?:\.\d+)?)(?P<push>[pP!]?)$"
)


def _strip_trailing_bar_weight(chord: str) -> str:
    """Remove whole-bar ``:beats`` suffix when not using ``|`` subdivisions."""
    m = _BAR_WEIGHT_SUFFIX.match(str(chord or "").strip())
    if not m:
        return str(chord or "").strip()
    return str(m.group("chord")).strip()


def normalize_chord_for_theory(token: object) -> str:
    """Bare chord symbol for analysis (no bar weights, pipes, push markers, or ``.hit``)."""
    try:
        from chord_subdivisions import hit_underlying_chord, parse_subdivisions
    except ImportError:
        hit_underlying_chord = lambda t: str(t or "").strip()  # type: ignore[misc,assignment]
        parse_subdivisions = None  # type: ignore[assignment,misc]

    raw = hit_underlying_chord(str(token or "").strip())
    if not raw:
        return ""
    if parse_subdivisions is not None:
        subs = parse_subdivisions(raw, beats_per_bar=4.0)
        if subs:
            out = str(subs[0].chord or "").strip()
            if "|" not in raw:
                out = _strip_trailing_bar_weight(out)
            return out
    head = raw.split("|", 1)[0].strip()
    head = _strip_trailing_bar_weight(head)
    if ":" in head and "|" in raw:
        head = head.split(":", 1)[0].strip()
    for mark in ("p", "P", "!"):
        if head.endswith(mark):
            head = head[: -len(mark)].strip()
            break
    return head


def chord_root_for_theory(chord: object) -> str:
    """Spelled root pitch class for harmonic analysis (playback tokens normalized first)."""
    head = normalize_chord_for_theory(chord).split("/", 1)[0].strip()
    if not head:
        return ""
    root, _ = split_chord(head)
    return normalize_root(root)


_QUALITY_COACHING_LABELS: dict[str, str] = {
    "major": "major",
    "minor": "minor",
    "m7": "minor seventh",
    "maj7": "major seventh",
    "dom": "dominant seventh",
    "half-dim": "half-diminished",
    "dim": "diminished",
    "aug": "augmented",
    "sus": "suspended",
}


def chord_quality_label(chord: object) -> str:
    """Human-readable quality for lab / analyzer text (uses :func:`classify_chord_quality`)."""
    return _QUALITY_COACHING_LABELS.get(classify_chord_quality(chord), "major")


def classify_chord_quality(chord: object) -> str:
    """Quality bucket for coaching: major, minor, m7, maj7, dom, half-dim, dim, aug, sus."""
    head = normalize_chord_for_theory(chord).split("/", 1)[0].strip()
    if not head:
        return "major"
    _, suffix = split_chord(head)
    low = str(suffix or "").lower()
    if "m7b5" in low or "ø" in low:
        return "half-dim"
    if "dim" in low:
        return "dim"
    if "aug" in low or "+" in str(suffix or ""):
        return "aug"
    if "sus" in low:
        return "sus"
    if "maj7" in low or "maj9" in low or (low.startswith("maj") and "7" in low):
        return "maj7"
    if "m7" in low or "m9" in low or "m11" in low or "min7" in low:
        return "m7"
    if low == "m" or low.startswith("min") or (low.startswith("m") and "maj" not in low and "7" not in low):
        return "minor"
    if re.search(r"(?<![a-z])7", low) and "maj" not in low:
        return "dom"
    if "7" in low or "9" in low or "11" in low or "13" in low:
        return "dom"
    return "major"


def key_is_minor(key: str) -> bool:
    """True when the key center is minor (e.g. Dm, F#m), not major or maj7-style."""
    _, mode = split_key_center(str(key or "").strip() or "C")
    return mode == "minor"


def key_mode(key: str) -> str:
    """Return ``major`` or ``minor`` for a key center string."""
    return "minor" if key_is_minor(key) else "major"


def enharmonic_keys_for_mode(mode: str) -> list[str]:
    """Major or minor key centers with both flat and sharp spellings where applicable."""
    return list(ENHARMONIC_MINOR_KEYS if str(mode or "").lower() == "minor" else ENHARMONIC_MAJOR_KEYS)


def practice_keys_for_mode(mode: str) -> list[str]:
    """Key centers for the requested mode (includes enharmonic spellings)."""
    return enharmonic_keys_for_mode(mode)


def reference_spelling_mode(reference_key: str) -> str:
    """flat | sharp | natural — follow concert/display key accidental family."""
    root, suffix = split_chord(str(reference_key or "C"))
    root = str(root or "C")
    if "b" in root:
        return "flat"
    if "#" in root:
        return "sharp"
    nr = normalize_root(root)
    if key_is_minor(str(root) + suffix):
        if nr in _SHARP_SIDE_MINOR:
            return "sharp"
        if nr in _FLAT_SIDE_MINOR:
            return "flat"
    else:
        if nr in _SHARP_SIDE_MAJOR:
            return "sharp"
        if nr in _FLAT_SIDE_MAJOR:
            return "flat"
    return "natural"


def spell_pitch_class(pitch_idx: int, *, mode: str) -> str:
    idx = int(pitch_idx) % 12
    if mode == "flat":
        return _FLAT_PITCH_CLASSES[idx]
    if mode == "sharp":
        return _SHARP_PITCH_CLASSES[idx]
    natural = _FLAT_PITCH_CLASSES[idx]
    if natural in _NATURAL_PITCH_CLASSES:
        return natural
    return _FLAT_PITCH_CLASSES[idx]


def spell_note_in_key(pitch_class: int, reference_key: str) -> str:
    """Musician-facing pitch-class name for the key signature (flat vs sharp family)."""
    return spell_pitch_class(int(pitch_class) % 12, mode=reference_spelling_mode(reference_key))


def respell_note_for_key(note_name: str, reference_key: str) -> str:
    """Re-spell a note name to match the reference key's accidental family."""
    root, _ = split_chord(str(note_name or "C").strip() or "C")
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return str(note_name)
    return spell_note_in_key(CHROMATIC.index(nr), reference_key)


def respell_notes_for_key(notes: list[str], reference_key: str) -> list[str]:
    return [respell_note_for_key(n, reference_key) for n in notes]


def abc_key_signature_for_reference(reference_key: str, *, scale_type: str = "major") -> str:
    """Conventional ABC ``K:`` token for a reference key (Eb major → ``Eb``, not enharmonic ``D``)."""
    ref = str(reference_key or "C").strip() or "C"
    st = str(scale_type or "major").lower()
    minor = (
        "minor" in st
        and "major" not in st
        and "pentatonic" not in st
        and "blues" not in st
        and "dorian" not in st
        and "mixolydian" not in st
        and "lydian" not in st
        and "locrian" not in st
    )
    if minor and not ref.lower().endswith("m"):
        ref = f"{ref}m"
    root, _ = split_chord(ref)
    spelled = respell_note_for_key(root, ref)
    if minor:
        low = str(spelled or "C")
        return f"{low}m" if not low.lower().endswith("m") else low
    return str(spelled or "C")


def format_musician_note_name(note: str, reference_key: str) -> str:
    """Musician-facing note with Unicode ♭/♯ when the key family uses accidentals."""
    spelled = respell_note_for_key(str(note or "C").strip() or "C", reference_key)
    if len(spelled) > 1 and spelled[1] == "b":
        return f"{spelled[0]}♭"
    if len(spelled) > 1 and spelled[1] == "#":
        return f"{spelled[0]}♯"
    return spelled


_DIATONIC_LETTERS = "CDEFGAB"
_NATURAL_LETTER_PC: dict[str, int] = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


def _chord_letter_interval_spec(suffix: str) -> list[tuple[int, int]]:
    """Diatonic letter steps from root (0,2,4,6) and semitone offsets from root."""
    low = str(suffix or "").lower()
    if "m7b5" in low:
        return [(0, 0), (2, 3), (4, 6), (6, 10)]
    if "dim" in low:
        if "dim7" in low or "°7" in low:
            return [(0, 0), (2, 3), (4, 6), (6, 9)]
        return [(0, 0), (2, 3), (4, 6)]
    if "aug" in low or "+" in str(suffix or ""):
        return [(0, 0), (2, 4), (4, 8)]
    if "sus" in low:
        return [(0, 0), (1, 2), (4, 7)] if "sus2" in low else [(0, 0), (3, 5), (4, 7)]
    if "maj7" in low:
        return [(0, 0), (2, 4), (4, 7), (6, 11)]
    if "m7" in low and "maj" not in low:
        return [(0, 0), (2, 3), (4, 7), (6, 10)]
    if re.search(r"(?<![a-z])7", low) and "maj" not in low:
        return [(0, 0), (2, 4), (4, 7), (6, 10)]
    if "m" in low and "maj" not in low:
        return [(0, 0), (2, 3), (4, 7)]
    return [(0, 0), (2, 4), (4, 7)]


def _spell_letter_to_pitch_class(letter: str, target_pc: int) -> str:
    """Pick accidental so ``letter`` matches ``target_pc`` (0–11)."""
    base = _NATURAL_LETTER_PC.get(letter.upper(), 0)
    diff = (int(target_pc) - base) % 12
    if diff == 0:
        return letter.upper()
    if diff == 1:
        return f"{letter.upper()}#"
    if diff == 11:
        return f"{letter.upper()}b"
    if diff == 2:
        return f"{letter.upper()}#"
    if diff == 10:
        return f"{letter.upper()}b"
    if diff == 3:
        return f"{letter.upper()}#"
    if diff == 9:
        return f"{letter.upper()}b"
    return spell_pitch_class(int(target_pc) % 12, mode="sharp")


_HEPTATONIC_SCALE_TEMPLATES: tuple[tuple[int, ...], ...] = (
    (0, 2, 4, 5, 7, 9, 11),
    (0, 2, 3, 5, 7, 8, 10),
    (0, 2, 3, 5, 7, 9, 10),
    (0, 2, 3, 5, 7, 9, 11),
    (0, 2, 4, 5, 7, 9, 10),
)


def _letter_steps_for_scale_intervals(intervals: tuple[int, ...] | list[int]) -> list[int]:
    if len(intervals) == 7:
        return list(range(7))
    ints = tuple(int(i) for i in intervals)
    for tpl in _HEPTATONIC_SCALE_TEMPLATES:
        steps: list[int] = []
        used: set[int] = set()
        ok = True
        for semi in ints:
            found = False
            for li, tsemi in enumerate(tpl):
                if tsemi == semi and li not in used:
                    steps.append(li)
                    used.add(li)
                    found = True
                    break
            if not found:
                ok = False
                break
        if ok and len(steps) == len(ints):
            return steps
    return list(range(len(ints)))


def spell_diatonic_scale_from_root(root: str, semitone_intervals: list[int] | tuple[int, ...]) -> list[str]:
    """Spell each scale degree with consecutive diatonic letters from the root (mode-aware)."""
    root_spelled = str(root or "C").strip() or "C"
    root_letter = root_spelled[0].upper()
    if root_letter not in _DIATONIC_LETTERS:
        root_letter = "C"
    root_pc = NOTE_TO_MIDI.get(normalize_root(split_chord(root_spelled)[0]), 60) % 12
    root_li = _DIATONIC_LETTERS.index(root_letter)
    letter_steps = _letter_steps_for_scale_intervals(semitone_intervals)
    out: list[str] = []
    for i, semi in enumerate(semitone_intervals):
        li = (root_li + letter_steps[i]) % 7
        letter = _DIATONIC_LETTERS[li]
        target_pc = (root_pc + int(semi)) % 12
        out.append(_spell_letter_to_pitch_class(letter, target_pc))
    return out


def spell_chord_tones(chord: object, *, reference_key: str = "") -> list[str]:
    """
    Chord tones with correct diatonic letter names (root, third, fifth, seventh).

    Uses chord structure for letter names; ``reference_key`` only breaks ties when needed.
    """
    _ = reference_key
    head = normalize_chord_for_theory(chord).split("/", 1)[0].strip()
    if not head:
        head = str(chord or "").split("/", 1)[0].strip()
    root_raw, suffix = split_chord(head)
    root_spelled = str(root_raw or "C").strip() or "C"
    root_letter = root_spelled[0].upper()
    if root_letter not in _DIATONIC_LETTERS:
        root_letter = "C"
    root_pc = NOTE_TO_MIDI.get(normalize_root(root_spelled), 60) % 12
    root_li = _DIATONIC_LETTERS.index(root_letter)
    spec = _chord_letter_interval_spec(suffix)
    tones: list[str] = []
    for letter_step, semi in spec:
        li = (root_li + int(letter_step)) % 7
        letter = _DIATONIC_LETTERS[li]
        target_pc = (root_pc + int(semi)) % 12
        tones.append(_spell_letter_to_pitch_class(letter, target_pc))
    ref = str(reference_key or "").strip()
    if ref and reference_spelling_mode(ref) == "flat":
        root_tone = tones[0] if tones else ""
        tones = [respell_note_for_key(t, ref) for t in tones]
        if root_spelled and tones:
            tones[0] = respell_note_for_key(root_spelled, ref) if root_spelled[0].upper() in _DIATONIC_LETTERS else tones[0]
    return tones[:4]


def _practice_key_for_pitch_class(key: str, mode: str) -> str:
    """Pick a dropdown spelling for a pitch class, preserving user spelling when possible."""
    raw = str(key or "C").strip() or "C"
    root, suffix = split_chord(raw)
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return raw
    want_minor = str(mode or "").lower() == "minor"
    if want_minor == key_is_minor(raw) and raw in practice_keys_for_mode(mode):
        return raw
    for candidate in practice_keys_for_mode(mode):
        cr, cs = split_chord(candidate)
        if normalize_root(cr) != nr:
            continue
        if want_minor == key_is_minor(candidate):
            return candidate
    return (nr + "m") if want_minor else nr


def coerce_key_to_mode(key: str, mode: str) -> str:
    """Normalize a key to the nearest center in the requested mode."""
    return _practice_key_for_pitch_class(key, mode)


def _enharmonic_in_options(key: str, options: list[str]) -> str | None:
    root, _ = split_chord(str(key or "C"))
    nr = normalize_root(root)
    for opt in options:
        cr, _ = split_chord(opt)
        if normalize_root(cr) == nr:
            return opt
    return None


def display_key_options(original_key: str) -> list[str]:
    """Key choices for the active song mode — major songs show major keys only."""
    original_key = str(original_key or "C").strip() or "C"
    mode = key_mode(original_key)
    options = list(practice_keys_for_mode(mode))

    if key_mode(original_key) == mode:
        canonical = original_key
    else:
        canonical = coerce_key_to_mode(original_key, mode)

    if canonical in options:
        return [canonical] + [k for k in options if k != canonical]

    twin = _enharmonic_in_options(canonical, options)
    if twin:
        return [canonical] + [k for k in options if k != twin]

    return [canonical] + options


def relative_minor_of_major(major_key: str) -> str:
    """Relative minor for a major key center (e.g. D → Bm)."""
    root, _ = split_chord(str(major_key or "C").strip() or "C")
    new_root = _transpose_root(root, -3, reference_key=major_key)
    return new_root + "m"


def relative_major_of_minor(minor_key: str) -> str:
    """Relative major for a minor key center (e.g. Gm → Bb)."""
    root, _ = split_chord(str(minor_key or "Am").strip() or "Am")
    new_root = _transpose_root(root, 3, reference_key=minor_key)
    return new_root


def semitone_distance(from_key, to_key):
    a = normalize_root(split_chord(from_key)[0])
    b = normalize_root(split_chord(to_key)[0])

    if a not in CHROMATIC or b not in CHROMATIC:
        return 0

    return (CHROMATIC.index(b) - CHROMATIC.index(a)) % 12


def _transpose_root(root: str, steps: int, *, reference_key: str | None) -> str:
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return root
    ref = str(reference_key if reference_key is not None else root)
    mode = reference_spelling_mode(ref)
    new_idx = (CHROMATIC.index(nr) + steps) % 12
    return spell_pitch_class(new_idx, mode=mode)


def _transpose_chord_atom(chord: str, steps: int, *, reference_key: str | None = None) -> str:
    """Transpose a single chord symbol (no bar-level ``|`` subdivisions)."""
    chord = str(chord).strip()
    ref = reference_key
    if "/" in chord:
        left, bass = chord.split("/", 1)
        lr, ls = split_chord(left)
        left_out = _transpose_root(lr, steps, reference_key=ref) + ls
        if not bass.strip():
            return left_out + "/"
        br, bs = split_chord(bass)
        bass_out = _transpose_root(br, steps, reference_key=ref) + bs
        return f"{left_out}/{bass_out}"

    root, suffix = split_chord(chord)
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return chord

    new_root = _transpose_root(root, steps, reference_key=ref)
    return new_root + suffix


def transpose_chord(chord, steps, *, reference_key: str | None = None):
    chord = str(chord).strip()
    ref = reference_key
    try:
        from chord_subdivisions import (
            SUBDIVISION_SEPARATOR,
            WEIGHT_SEPARATOR,
            Subdivision,
            hit_underlying_chord,
            is_hit_token,
            join_subdivisions,
            join_weighted_subdivisions,
            make_hit_token,
            parse_subdivisions,
        )
    except Exception:
        return _transpose_chord_atom(chord, steps, reference_key=ref)

    if is_hit_token(chord):
        inner = hit_underlying_chord(chord)
        return make_hit_token(
            transpose_chord(inner, steps, reference_key=ref)
        )

    has_pipe = SUBDIVISION_SEPARATOR in chord
    has_weight = WEIGHT_SEPARATOR in chord
    if has_pipe or has_weight:
        subs = parse_subdivisions(chord)
        if subs:
            transposed = [
                Subdivision(
                    chord=_transpose_chord_atom(s.chord, steps, reference_key=ref),
                    weight=s.weight,
                    push=s.push,
                )
                for s in subs
            ]
            if has_weight:
                return join_weighted_subdivisions(transposed)
            if len(transposed) > 1:
                return join_subdivisions([s.chord for s in transposed])
            return transposed[0].chord

    return _transpose_chord_atom(chord, steps, reference_key=ref)


def transpose_guitar_tabs(g_tabs: dict, from_key: str, to_key: str) -> dict:
    """Transpose dictionary keys (chord symbols) so labels match displayed harmony."""
    if not g_tabs:
        return {}
    steps = semitone_distance(from_key, to_key)
    if steps == 0:
        return dict(g_tabs)
    return {
        transpose_chord(name, steps, reference_key=from_key): shape
        for name, shape in g_tabs.items()
    }


class MissingOriginalSongKeyError(ValueError):
    """Raised when section transposition requires a catalog original key."""


def resolve_original_song_key(
    record: dict[str, Any] | None,
    *,
    catalog_session: dict[str, Any] | None = None,
) -> str:
    """Public helper — see ``songs.catalog_song_resolution``."""
    from songs.catalog_song_resolution import resolve_original_song_key as _resolve

    return _resolve(record, catalog_session=catalog_session)


class ChartSongNotReadyError(ValueError):
    """Raised when chart construction lacks a complete canonical song record."""


def validate_chart_song_for_transpose(
    level_song_data: dict[str, Any],
    *,
    original_key: str,
    provenance: str,
) -> None:
    """Guard before transpose_sections — partial session overlays must not pass through."""
    if not isinstance(level_song_data, dict):
        raise ChartSongNotReadyError(
            f"Chart song payload is not a mapping (provenance={provenance})."
        )
    key = level_song_data.get("key")
    if key is None or not str(key).strip():
        raise MissingOriginalSongKeyError(
            "Cannot transpose song sections because the original song key is missing."
        )
    if not str(original_key or "").strip():
        raise MissingOriginalSongKeyError(
            "Cannot transpose song sections because the original song key is missing."
        )
    sections = level_song_data.get("sections")
    if not isinstance(sections, dict):
        raise ChartSongNotReadyError(
            f"Chart song sections are missing (provenance={provenance})."
        )
    title = str(level_song_data.get("title") or level_song_data.get("name") or "").strip()
    if not title and provenance.startswith("catalog"):
        raise ChartSongNotReadyError(
            f"Chart song identity is incomplete (provenance={provenance})."
        )


def chart_bundle_cache_signature(
    session_state: dict[str, Any],
    catalog_song_data: dict[str, Any],
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
) -> tuple[Any, ...]:
    """Cache key fragment so pre-reconciliation partial overlays cannot reuse chart bundles."""
    from songs.state import reconcile_active_pick_key

    reconciled_pk = reconcile_active_pick_key(
        session_state,
        song_picker_catalog=song_picker_catalog,
    )
    sel = session_state.get("selected_song") if isinstance(session_state.get("selected_song"), dict) else {}
    overlay_key = str((catalog_song_data or {}).get("key") or "").strip()
    sel_key = str(sel.get("key") or "").strip()
    meta_pk = ""
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session_state.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict):
            meta_pk = str(meta.get("pick_key") or meta.get("active_catalog_pick_key") or "").strip()
    except ImportError:
        pass
    return (
        reconciled_pk,
        meta_pk,
        overlay_key,
        sel_key,
        bool(session_state.get("_music_active_pick_key_reconciled")),
        bool(session_state.get("_music_startup_restore_finalized")),
        bool(session_state.get("_music_workspace_blob_hydrated")),
        bool((catalog_song_data or {}).get("sections")),
    )


def transpose_sections(song_data, target_key):
    if not isinstance(song_data, dict):
        raise TypeError("transpose_sections requires a song_data mapping")
    original_key = song_data.get("key")
    if original_key is None or not str(original_key).strip():
        raise MissingOriginalSongKeyError(
            "Cannot transpose song sections because the original song key is missing."
        )
    original_key = str(original_key).strip()

    steps = semitone_distance(
        original_key,
        target_key
    )

    out = {}

    for section_name, chords in (song_data.get("sections") or {}).items():

        out[section_name] = [
            transpose_chord(ch, steps, reference_key=target_key)
            for ch in chords
        ]

    return out


def transpose_sections_dict(sections, from_key, to_key):
    """Transpose a sections mapping from one key center to another."""
    steps = semitone_distance(from_key, to_key)
    return {
        name: [transpose_chord(ch, steps, reference_key=to_key) for ch in chords]
        for name, chords in sections.items()
    }
