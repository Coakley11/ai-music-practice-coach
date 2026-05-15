"""Shared chord/key utilities for the practice coach and song catalog."""

COMMON_KEYS = [
    "C", "Db", "D", "Eb", "E", "F",
    "Gb", "G", "Ab", "A", "Bb", "B",
]

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


def split_chord(chord):
    chord = str(chord)
    if len(chord) >= 2 and chord[1] in ["b", "#"]:
        return chord[:2], chord[2:]
    return chord[:1], chord[1:]


def semitone_distance(from_key, to_key):
    a = normalize_root(split_chord(from_key)[0])
    b = normalize_root(split_chord(to_key)[0])

    if a not in CHROMATIC or b not in CHROMATIC:
        return 0

    return (CHROMATIC.index(b) - CHROMATIC.index(a)) % 12


def transpose_chord(chord, steps):
    chord = str(chord).strip()
    if "/" in chord:
        left, bass = chord.split("/", 1)
        lr, ls = split_chord(left)
        nr = normalize_root(lr)
        left_out = (
            CHROMATIC[(CHROMATIC.index(nr) + steps) % 12] + ls
            if nr in CHROMATIC
            else left
        )
        if not bass.strip():
            return left_out + "/"
        br, bs = split_chord(bass)
        nbr = normalize_root(br)
        bass_out = (
            CHROMATIC[(CHROMATIC.index(nbr) + steps) % 12] + bs
            if nbr in CHROMATIC
            else bass
        )
        return f"{left_out}/{bass_out}"

    root, suffix = split_chord(chord)
    root = normalize_root(root)

    if root not in CHROMATIC:
        return chord

    new_root = CHROMATIC[(CHROMATIC.index(root) + steps) % 12]

    return new_root + suffix


def transpose_guitar_tabs(g_tabs: dict, from_key: str, to_key: str) -> dict:
    """Transpose dictionary keys (chord symbols) so labels match displayed harmony."""
    if not g_tabs:
        return {}
    steps = semitone_distance(from_key, to_key)
    if steps == 0:
        return dict(g_tabs)
    return {transpose_chord(name, steps): shape for name, shape in g_tabs.items()}


def transpose_sections(song_data, target_key):
    original_key = song_data["key"]

    steps = semitone_distance(
        original_key,
        target_key
    )

    out = {}

    for section_name, chords in song_data["sections"].items():

        out[section_name] = [
            transpose_chord(ch, steps)
            for ch in chords
        ]

    return out


def transpose_sections_dict(sections, from_key, to_key):
    """Transpose a sections mapping from one key center to another."""
    steps = semitone_distance(from_key, to_key)
    return {
        name: [transpose_chord(ch, steps) for ch in chords]
        for name, chords in sections.items()
    }
