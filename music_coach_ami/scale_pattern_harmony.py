"""Harmony and pitch rules for AMI scale-pattern exercises.

Everything here is a pure function of the app's own data (Practice Key token, the section's chord slots, the instrument's notation
profile). It creates no second authority: the Practice Key and its mode come from the token the caller passes in, the chord
slots from the chart, the written range from ``notation_profile``.

* ``practice_key_scale``     - tonic + mode of the pattern's key, from the Practice Key (not assumed major).
* ``timeline_segments``      - the chart's bar slots as (bar, beat, beats, chord) segments, split bars included
                               (``chord_subdivisions`` is the single source of truth for ``"C:2|G:2"`` style slots).
* ``chord_scale_for``        - the scale a chord calls for, with the reason, verified to contain every chord tone.
* ``exact_offset``           - how far written pitch sits above sounding pitch for an instrument, octave included.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

_LETTERS = "CDEFGAB"
_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_MAJOR_PC = (0, 2, 4, 5, 7, 9, 11)


def _clean(value: object) -> str:
    return str(value or "").strip()


# ---------------------------------------------------------------- spelling


def pc_of(note: str) -> int:
    text = _clean(note).replace("♯", "#").replace("♭", "b")
    if not text or text[0].upper() not in _LETTER_PC:
        raise ValueError(f"not a note name: {note!r}")
    pc = _LETTER_PC[text[0].upper()]
    for ch in text[1:]:
        pc += 1 if ch == "#" else -1 if ch == "b" else 0
    return pc % 12


def _spell(letter_index: int, target_pc: int) -> str:
    letter = _LETTERS[letter_index % 7]
    delta = (target_pc - _LETTER_PC[letter] + 6) % 12 - 6
    if abs(delta) > 1:
        raise ValueError(f"needs a double accidental on {letter}")
    return letter + ("#" if delta == 1 else "b" if delta == -1 else "")


# degree formulas: (degree number, accidental relative to the major scale)
_FORMULAS: dict[str, tuple[tuple[int, int], ...]] = {
    "ionian": ((1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0)),
    "dorian": ((1, 0), (2, 0), (3, -1), (4, 0), (5, 0), (6, 0), (7, -1)),
    "phrygian": ((1, 0), (2, -1), (3, -1), (4, 0), (5, 0), (6, -1), (7, -1)),
    "lydian": ((1, 0), (2, 0), (3, 0), (4, 1), (5, 0), (6, 0), (7, 0)),
    "mixolydian": ((1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, -1)),
    "aeolian": ((1, 0), (2, 0), (3, -1), (4, 0), (5, 0), (6, -1), (7, -1)),
    "locrian": ((1, 0), (2, -1), (3, -1), (4, 0), (5, -1), (6, -1), (7, -1)),
    "melodic minor": ((1, 0), (2, 0), (3, -1), (4, 0), (5, 0), (6, 0), (7, 0)),
    "mixolydian b6": ((1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, -1), (7, -1)),
    "altered": ((1, 0), (2, -1), (3, -1), (3, 0), (5, -1), (6, -1), (7, -1)),
    "lydian dominant": ((1, 0), (2, 0), (3, 0), (4, 1), (5, 0), (6, 0), (7, -1)),
    "phrygian dominant": ((1, 0), (2, -1), (3, 0), (4, 0), (5, 0), (6, -1), (7, -1)),
}


def spell_scale(root: str, kind: str) -> list[str]:
    """Seven spelled notes of ``kind`` from ``root`` (one letter per degree, except altered's two thirds)."""
    formula = _FORMULAS[kind]
    root_letter = _LETTERS.index(_clean(root)[0].upper())
    root_pc = pc_of(root)
    out: list[str] = []
    for number, accidental in formula:
        semis = _MAJOR_PC[number - 1] + accidental
        out.append(_spell(root_letter + number - 1, (root_pc + semis) % 12))
    return out


# ---------------------------------------------------------------- the key of the pattern


@dataclass(frozen=True)
class KeyScale:
    tonic: str
    tonality: str          # "major" | "natural minor"
    source: str            # practice_key | song_original_key | default

    @property
    def token(self) -> str:
        return self.tonic + ("m" if self.tonality == "natural minor" else "")


def _token_parts(token: object) -> tuple[str, str] | None:
    text = _clean(token)
    m = re.match(r"^([A-Ga-g])([#b♯♭]?)\s*(major|maj|minor|min|m)?$", text, re.I)
    if not m:
        return None
    root = m.group(1).upper() + {"♯": "#", "♭": "b"}.get(m.group(2), m.group(2))
    word = _clean(m.group(3))
    minor = word.lower() in ("minor", "min") or word == "m"
    return root, "natural minor" if minor else "major"


def practice_key_scale(practice_key: object, original_key: object = "") -> KeyScale:
    """The key the pattern lives in. The Practice Key token carries its own mode ("Cm", "G minor"); only when there is no
    Practice Key at all does the song's own key stand in, and only with neither is C major assumed."""
    parts = _token_parts(practice_key)
    if parts:
        return KeyScale(parts[0], parts[1], "practice_key")
    parts = _token_parts(original_key)
    if parts:
        return KeyScale(parts[0], parts[1], "song_original_key")
    return KeyScale("C", "major", "default")


# ---------------------------------------------------------------- chord slots


@dataclass(frozen=True)
class Segment:
    bar: int
    beat: Fraction        # offset inside the bar
    beats: Fraction       # length
    chord: str            # the chord symbol as the chart writes it
    push: bool = False


def _beats_per_bar(meter: str) -> Fraction:
    return Fraction(3) if _clean(meter) in ("3/4", "6/8") else Fraction(2) if _clean(meter) == "2/4" else Fraction(4)


def timeline_segments(slots: list[str], bars: int, meter: str = "4/4") -> list[Segment]:
    """The first ``bars`` bar slots of the section (cycled if the section is shorter), as chord segments with their beats.

    A slot may be a split bar (``"C:2|G:2"``, ``"C:3.5|D:0.5p"``, ``"Fmaj7|Am7"`` for equal parts). Chord-less slots are an error:
    the caller must say the harmony is incomplete rather than guess one.
    """
    from chord_subdivisions import parse_subdivisions

    usable = [_clean(s) for s in slots if _clean(s)]
    if not usable:
        raise ValueError("no chords")
    per_bar = _beats_per_bar(meter)
    out: list[Segment] = []
    for bar in range(max(1, int(bars))):
        token = usable[bar % len(usable)]
        subs = parse_subdivisions(token, beats_per_bar=float(per_bar)) if "|" in token else None
        if not subs:
            out.append(Segment(bar, Fraction(0), per_bar, token.split(".hit")[0]))
            continue
        cursor = Fraction(0)
        for sub in subs:
            length = Fraction(str(sub.weight)).limit_denominator(8)
            out.append(Segment(bar, cursor, length, _clean(sub.chord), bool(getattr(sub, "push", False))))
            cursor += length
        if cursor != per_bar:
            raise ValueError(f"the beats of {token!r} do not add up to a {meter} bar")
    return out


# ---------------------------------------------------------------- what the player asked for


_FOLLOW_RE = re.compile(
    r"(?:\b(?:over|through|following|follow(?:s|ing)?|with|along|outline(?:s|d)?|on|for)\s+(?:(?:all|each|every|the)\s+)*(?:chord\s+)?"
    r"(?:changes|chords|progression|harmony)\b"
    r"|\bchord[- ]follow\w*|\bchord\s+by\s+chord\b|\b(?:each|every)\s+chord\b|\bthe changes\b)", re.I)


def wants_chord_following(question: str) -> bool:
    """True when the player asks for a pattern that follows the chords ("over the chord changes", "for each chord"), not just the key."""
    return bool(_FOLLOW_RE.search(_clean(question)))


# ---------------------------------------------------------------- chord -> scale


@dataclass(frozen=True)
class ChordScale:
    chord: str
    root: str
    kind: str
    notes: tuple[str, ...]
    why: str

    @property
    def label(self) -> str:
        return f"{self.root} {self.kind}"


_ROOT_RE = re.compile(r"^([A-G])([#b♯♭]?)(.*)$")


def _split_chord(chord: str) -> tuple[str, str]:
    text = _clean(chord).split("/")[0].strip()
    m = _ROOT_RE.match(text)
    if not m:
        raise ValueError("unreadable chord")
    return m.group(1) + {"♯": "#", "♭": "b"}.get(m.group(2), m.group(2)), m.group(3)


_MINOR_RE = re.compile(r"^(?:m(?!aj)|min|-)(?!aj)")


def _classify(quality: str) -> str:
    if quality[:1] == "M" and not quality.lower().startswith(("maj", "mmaj")):
        quality = "maj" + quality[1:]          # "CM7": capital M is major
    q = quality.replace(" ", "").replace("(", "").replace(")", "").lower()
    q = q.replace("♯", "#").replace("♭", "b").replace("Δ".lower(), "maj").replace("∆", "maj")
    if "dim" in q or "°" in q and "ø" not in q:
        return "unsupported:diminished"
    if "m7b5" in q or "ø" in q or "min7b5" in q or "-7b5" in q:
        return "half_diminished"
    if re.match(r"^(?:m|min|-)(?:maj|ma)7", q) or q.startswith("mmaj") or q.startswith("m(maj"):
        return "minor_major"
    if _MINOR_RE.match(q):
        return "minor"
    if q.startswith(("maj", "ma", "j")) or q in ("", "6", "69", "6/9", "add9", "2", "5"):
        return "major_lydian" if "#11" in q else "major"
    if "sus" in q:
        return "sus"
    if re.search(r"(?:7|9|13|11)", q) and not q.startswith(("maj", "ma")):
        if re.search(r"alt|b9|#9|b13|#5|\+|b5", q):
            return "altered"
        if "#11" in q:
            return "lydian_dominant"
        return "dominant"
    return "unsupported:unrecognised"


def chord_tone_roles(chord: str) -> dict[int, str]:
    """Pitch class -> role ("R", "3", "5", "7", "6", "9", "11", "13") for the chord symbol, alterations included.

    Computed from the symbol itself: the app's ``chord_tone_names`` ignores ♭5/♯5 and the altered tensions, which an altered-scale
    check cannot afford to."""
    root, quality = _split_chord(chord)
    base = pc_of(root)
    q = quality.replace(" ", "").replace("(", "").replace(")", "").replace("♯", "#").replace("♭", "b").replace("∆", "maj").replace("Δ", "maj")
    low = q.lower()
    roles: dict[int, str] = {base % 12: "R"}
    minor = bool(_MINOR_RE.match(low)) and not q.startswith("M") and not low.startswith("maj")
    if "dim" in low or "°" in low:
        minor = True
    if "sus2" in low:
        roles[(base + 2) % 12] = "3"
    elif "sus" in low:
        roles[(base + 5) % 12] = "3"
    else:
        roles[(base + (3 if minor else 4)) % 12] = "3"
    if "b5" in low or "dim" in low or "°" in low or "ø" in low:
        fifth = 6
    elif "#5" in low or "+" in low or "aug" in low:
        fifth = 8
    else:
        fifth = 7
    if "alt" not in low:
        roles[(base + fifth) % 12] = "5"
    major_seventh = q.startswith("M") or "maj" in low or low.startswith("ma") or bool(re.search(r"(?:^|m)j7", low))
    if "dim7" in low or "°7" in low:
        roles[(base + 9) % 12] = "7"
    elif major_seventh:
        roles[(base + 11) % 12] = "7"
    elif re.search(r"(?:7|9|11|13)", low) and not low.startswith(("6", "69")):
        roles[(base + 10) % 12] = "7"
    if re.search(r"(?:^|[^0-9])6(?![0-9])", low) or low.startswith("69"):
        roles.setdefault((base + 9) % 12, "6")
    for token, semis, label in (("b9", 1, "9"), ("#9", 3, "9"), ("#11", 6, "11"), ("b13", 8, "13")):
        if token in low:
            roles[(base + semis) % 12] = label
    if re.search(r"(?<![b#])9", low) and "69" not in low:
        roles.setdefault((base + 2) % 12, "9")
    if re.search(r"(?<![b#])13", low):
        roles.setdefault((base + 9) % 12, "13")
    if re.search(r"(?<![b#])11", low) and "sus" not in low:
        roles.setdefault((base + 5) % 12, "11")
    return roles


def chord_scale_for(chord: str, key: KeyScale) -> ChordScale:
    """The scale this chord calls for in this key, or ``ValueError(reason)``. Every chord tone must be inside it; the first scale of the
    chord's ordered candidates that holds them all is used, so an unusual chord is never forced into the wrong scale."""
    root, quality = _split_chord(chord)
    kind_of = _classify(quality)
    if kind_of.startswith("unsupported"):
        raise ValueError(f"{chord}: {kind_of.split(':', 1)[1]} chords aren't supported yet")
    key_root_pc = pc_of(key.tonic)
    degree_semis = (pc_of(root) - key_root_pc) % 12
    minor_key = key.tonality == "natural minor"
    roles = chord_tone_roles(chord)
    has_sixth = "6" in roles.values() or "13" in roles.values()
    cands: list[tuple[str, str]] = []
    if kind_of == "major":
        cands = [("ionian", "a major chord → its major scale (Ionian)"), ("lydian", "a major chord with a ♯11 → Lydian")]
    elif kind_of == "major_lydian":
        cands = [("lydian", "a major chord with a ♯11 → Lydian")]
    elif kind_of == "minor":
        if has_sixth:
            cands = [("dorian", "a minor chord with a 6th → Dorian (its natural 6th)")]
        elif minor_key and degree_semis == 0:
            cands = [("aeolian", f"the tonic minor chord of {key.tonic} minor → natural minor (the Practice Key's own mode)"),
                     ("dorian", "a minor 7th chord → Dorian")]
        elif not minor_key and degree_semis == 9:
            cands = [("aeolian", f"the vi chord of {key.tonic} major → natural minor (Aeolian)"), ("dorian", "a minor 7th chord → Dorian")]
        elif not minor_key and degree_semis == 4:
            cands = [("phrygian", f"the iii chord of {key.tonic} major → Phrygian"), ("dorian", "a minor 7th chord → Dorian")]
        else:
            cands = [("dorian", "a minor 7th chord → Dorian")]
    elif kind_of == "half_diminished":
        cands = [("locrian", "a half-diminished chord → Locrian")]
    elif kind_of == "minor_major":
        cands = [("melodic minor", "a minor chord with a major 7th → melodic minor")]
    elif kind_of == "sus":
        cands = [("mixolydian", "a suspended dominant → Mixolydian")]
    elif kind_of == "lydian_dominant":
        cands = [("lydian dominant", "a dominant chord with a ♯11 → Lydian dominant")]
    elif kind_of == "altered":
        cands = [("altered", "a dominant chord with altered tensions (♭5/♯5/♭9/♯9/♭13) → altered scale"),
                 ("phrygian dominant", "a dominant chord with a ♭9 and a natural 5th → Phrygian dominant"),
                 ("lydian dominant", "a dominant chord with a ♯11 → Lydian dominant")]
    elif kind_of == "dominant":
        if minor_key and degree_semis == 7:
            cands.append(("mixolydian b6", f"the dominant (V) of {key.tonic} minor → Mixolydian ♭6, the 5th mode of {key.tonic} melodic minor"))
        cands.append(("mixolydian", "a dominant 7th chord → Mixolydian"))
    else:
        raise ValueError(f"{chord}: unrecognised chord quality")
    needed = set(roles)
    for kind, why in cands:
        try:
            notes = tuple(spell_scale(root, kind))
        except ValueError:
            continue
        if needed <= {pc_of(n) for n in notes}:
            return ChordScale(chord=_clean(chord), root=root, kind=kind, notes=notes, why=why)
    raise ValueError(f"{chord}: none of the scales I know for this kind of chord holds all of its chord tones")


# ---------------------------------------------------------------- instruments: written vs sounding, octave included

# written pitch minus sounding pitch, in semitones, octave included (an Eb alto sounds a major 6th below what is written, a Bb tenor a major
# 9th, an Eb baritone a major 13th, a Bb soprano / trumpet / clarinet a major 2nd). Only instruments listed here are verified.
_OFFSETS: dict[str, int] = {
    "flute": 0, "piano": 0, "alto saxophone": 9, "tenor saxophone": 14, "soprano saxophone": 2, "baritone saxophone": 21, "trumpet": 2,
    "clarinet": 2,
}

# The lowest and highest WRITTEN pitch the instrument can play (midi). The app's notation profiles are comfort windows and, for tenor
# and baritone sax, reach below the horn's lowest written note (Bb3), so the written line is also held inside these limits.
_PLAYABLE_WRITTEN: dict[str, tuple[int, int]] = {
    "flute": (60, 96), "piano": (21, 108), "alto saxophone": (58, 89), "tenor saxophone": (58, 89), "soprano saxophone": (58, 89),
    "baritone saxophone": (58, 89), "trumpet": (54, 84), "clarinet": (52, 96),
}


def playable_written_range(notation_instrument: str) -> tuple[int, int] | None:
    return _PLAYABLE_WRITTEN.get(_clean(notation_instrument).lower())


def written_window(notation_instrument: str, profile_low: int, profile_high: int) -> tuple[int, int]:
    """The written window a line is built to: the app's profile window inside the instrument's playable written range."""
    rng = playable_written_range(notation_instrument)
    if rng is None:
        return int(profile_low), int(profile_high)
    return max(int(profile_low), rng[0]), min(int(profile_high), rng[1])


def exact_offset(notation_instrument: str, semitones_mod12: int) -> int | None:
    """Written minus sounding semitones for this instrument, or None when it cannot be verified: an instrument with no entry, or one
    whose pitch-class offset disagrees with the app's own transposition (``written_music_context``)."""
    key = _clean(notation_instrument).lower()
    offset = _OFFSETS.get(key)
    if offset is None:
        return None
    if offset % 12 != int(semitones_mod12) % 12:
        return None
    return offset


def midi_of(note: str, octave: int) -> int:
    from music_theory import midi_from_spelled_note

    return int(midi_from_spelled_note(note, octave=octave))


def octave_for(note: str, midi: int) -> int:
    for octave in range(-1, 10):
        if midi_of(note, octave) == midi:
            return octave
    raise ValueError(f"{note} cannot sit at midi {midi}")


def transpose_spelled(note: str, semitones: int) -> str:
    """Respell ``note`` ``semitones`` up (any octave), keeping the interval's letter distance where the pitch class allows."""
    text = _clean(note)
    pc = (pc_of(text) + semitones) % 12
    # letter distance of the interval class: the standard names for the instrument transpositions
    steps = {0: 0, 2: 1, 9: 5, 3: 2, 7: 4, 5: 3, 4: 2, 10: 6, 11: 6, 1: 1, 6: 3, 8: 5}[semitones % 12]
    try:
        return _spell(_LETTERS.index(text[0].upper()) + steps, pc)
    except ValueError:
        from music_theory import spell_note_in_key

        return spell_note_in_key(pc, "C")


def exact_written_events(events: Any, offset: int, chord_fn: Any = None) -> list[Any]:
    """The same events written ``offset`` semitones above their sounding pitch, to the exact octave. ``chord_fn`` maps a concert chord
    symbol to the symbol printed above the written staff."""
    from dataclasses import replace

    out = []
    for ev in events:
        if not _clean(ev.spelled) or str(ev.duration or "").lower().startswith("rest"):
            out.append(replace(ev, domain="written", chord=chord_fn(ev.chord) if (chord_fn and ev.chord) else ev.chord))
            continue
        written_midi = midi_of(ev.spelled, int(ev.octave)) + offset
        spelled = transpose_spelled(ev.spelled, offset)
        out.append(replace(ev, spelled=spelled, octave=octave_for(spelled, written_midi), pitch_class=pc_of(spelled), domain="written",
                           chord=chord_fn(ev.chord) if (chord_fn and ev.chord) else ev.chord))
    return out
