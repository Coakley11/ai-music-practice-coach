"""Shared chord/key utilities for the practice coach and song catalog."""

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
    normalize_root(k.rstrip("m")) for k in ("Em", "Bm", "F#m", "C#m", "G#m", "D#m", "A#m")
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


def key_is_minor(key: str) -> bool:
    """True when the key center is minor (e.g. Dm, F#m), not major or maj7-style."""
    _, suffix = split_chord(str(key or "").strip() or "C")
    sl = suffix.lower()
    if not sl:
        return False
    if sl.startswith("maj"):
        return False
    return sl.startswith("m")


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


def transpose_chord(chord, steps, *, reference_key: str | None = None):
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


def transpose_sections(song_data, target_key):
    original_key = song_data["key"]

    steps = semitone_distance(
        original_key,
        target_key
    )

    out = {}

    for section_name, chords in song_data["sections"].items():

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
