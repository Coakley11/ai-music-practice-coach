"""The coach's ABC notation must display exactly the pitches AMI stored: accidentals are absolute and last to the bar line (same pitch, same octave).

The writer used to emit every note relative to the key signature only. A note that relied on the key signature after an explicit natural / sharp / flat
earlier in the same bar was therefore displayed one semitone off (``=e'`` then ``e'`` for E-flat in C minor), and a note one step against the key signature
(E-sharp in a flat key, F-flat in a sharp key) came out as a double accidental. These tests read the ABC back with an independent reader that follows the ABC
rules and compare it note for note with what was stored:

* the rule itself, on named cases (E-flat, E-natural, E-sharp, double accidentals, other octaves, a new bar);
* a seeded property test over every major and minor key signature, all five alterations, four octaves and many bars;
* byte-for-byte preservation: wherever the previous writer was already right, the output is identical to it;
* real scale-pattern exercises (both kinds, the M1c recipes that add chromatic notes) on every supported instrument, transposing ones included.

The octave: the coach writes scientific C4 as ABC ``c`` (standard ABC reads ``c`` as C5), a separate, known convention that this fix deliberately does not touch.
The reader below applies the writer's own octave convention so that these tests judge accidentals only.
"""

from __future__ import annotations

import random
import re

import pytest

from music_coach_ami import conversation_state as cs
from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.musical_idea_engine import MusicalEvent, MusicalIdeaComposition, _abc_pitch_in_bar, composition_to_abc
from music_coach_ami.notation_profile import notation_profile_for_instrument
from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami.scale_engine import _abc_key_field, _note_to_abc
from tests.test_ami_scale_pattern_recipe import ASK, ASK_CHORDS, _no_live_api, begin, ctx  # noqa: F401  (autouse guard re-exported)

WRITER_OCTAVE_OFFSET = -12          # the writer's current octave convention (see the module docstring); not changed here
NOTE = re.compile(r'(?P<chord>"[^"]*")?(?P<deco>(?:!>!|!tenuto!|\.)*)(?P<acc>\^\^|__|[_^=])?(?P<note>[A-Ga-gz])(?P<oct>[,\']*)(?P<dur>\d*(?:/\d*)?)')
BASE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJORS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7, "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
SHARP_ORDER, FLAT_ORDER = "fcgdaeb", "beadgcf"
ALTER_NAME = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}


def _pc(tonic: str) -> int:
    return (PC[tonic[0]] + (1 if tonic.endswith("#") else -1 if tonic.endswith("b") else 0)) % 12


MINORS = {"A": 0, "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5, "D#": 6, "A#": 7, "D": -1, "G": -2, "C": -3, "F": -4, "Bb": -5, "Eb": -6, "Ab": -7}
MODE_FROM_MAJOR = {"dor": 10, "dorian": 10, "phr": 8, "phrygian": 8, "lyd": 7, "lydian": 7, "mix": 5, "mixolydian": 5, "loc": 1, "locrian": 1}


def key_signature(abc: str) -> dict[str, int]:
    """The key signature of the tune's K: line, from the spelled tonic (so F-sharp major is six sharps, G-flat major six flats)."""
    m = re.search(r"^K:\s*([A-G][#b]?)\s*(m|min|minor|dor|dorian|mix|mixolydian|lyd|lydian|phr|phrygian|loc|locrian|maj|major)?", abc, re.M)
    tonic, mode = m.group(1), (m.group(2) or "").lower()
    if mode in ("", "maj", "major"):
        n = MAJORS[tonic]
    elif mode in ("m", "min", "minor"):
        n = MINORS[tonic]
    else:                                                  # a church mode: the signature of its relative major, named by the nearest flat/sharp spelling
        pc = (_pc(tonic) + MODE_FROM_MAJOR[mode]) % 12
        n = MAJORS[next(k for k in ("C", "G", "D", "A", "E", "B", "F", "Bb", "Eb", "Ab", "Db", "Gb") if _pc(k) == pc)]
    return {(SHARP_ORDER if n > 0 else FLAT_ORDER)[i]: (1 if n > 0 else -1) for i in range(abs(n))}


def read_abc(abc: str, octave_offset: int = WRITER_OCTAVE_OFFSET) -> list[int]:
    """Midi numbers of the pitched notes under the ABC rules: absolute accidentals that last to the bar line for the same letter and octave."""
    sig = key_signature(abc)
    body = " ".join(line for line in abc.splitlines() if line and not re.match(r"^[A-Za-z]:", line))
    if re.search(r"\^{3,}|_{3,}|\^[_=]|_[\^=]|=[\^_=]|\^\^[_=]|__[\^=]", body):
        raise ValueError("malformed accidental (ABC has only ^, ^^, _, __ and =)")
    out: list[int] = []
    for bar in body.split("|"):
        memo: dict[tuple[str, int], int] = {}
        for m in NOTE.finditer(bar):
            if m.group("note") == "z":
                continue
            letter = m.group("note").lower()
            octv = (5 if m.group("note").islower() else 4) + m.group("oct").count("'") - m.group("oct").count(",")
            if m.group("acc"):
                memo[(letter, octv)] = {"^": 1, "_": -1, "=": 0, "^^": 2, "__": -2}[m.group("acc")]
            out.append(12 * (octv + 1) + BASE[letter] + memo.get((letter, octv), sig.get(letter, 0)) + octave_offset)
    return out


def midi(spelled: str, octave: int) -> int:
    return sph.midi_of(spelled, int(octave))


# ---------------------------------------------------------------- the rule on named cases
@pytest.mark.parametrize("key, seq, expected", [
    # E-flat is in the key signature of C minor: a natural, then the flat again, then the flat in force
    ("Cm", [("E", 5), ("Eb", 5), ("Eb", 5)], ["=e'", "_e'", "e'"]),
    ("Cm", [("Eb", 5), ("E", 5), ("E", 5), ("Eb", 5)], ["e'", "=e'", "=e'", "_e'"]),         # the 2nd natural is kept (legacy), the final flat is re-marked
    ("Cm", [("E", 5), ("E", 4), ("Eb", 4)], ["=e'", "=e", "_e"]),                              # a different octave is a different pitch
    ("C", [("E", 5), ("Eb", 5), ("E", 5)], ["e'", "_e'", "=e'"]),                              # E-natural after a flat in a key with no E accidental
    ("C", [("E#", 5), ("E", 5), ("E#", 5)], ["^e'", "=e'", "^e'"]),
    ("Cm", [("E#", 5)], ["^e'"]),                                                              # E-sharp against a flat key signature: a sharp, not a double sharp
    ("G", [("Fb", 5)], ["_f'"]),                                                               # F-flat against F-sharp in the key signature: a flat, not a double flat
    ("G", [("F#", 5), ("F", 5), ("F#", 5)], ["f'", "=f'", "^f'"]),
    ("D", [("F#", 5), ("C#", 5), ("C", 5), ("C#", 5)], ["f'", "c'", "=c'", "^c'"]),
    ("Eb", [("A", 5), ("Ab", 5), ("A", 5)], ["=a'", "_a'", "=a'"]),                           # E-flat major has A-flat: the natural, then the flat re-marked
    ("C", [("F##", 5), ("F", 5)], ["^^f'", "=f'"]),
    ("C", [("Bbb", 4), ("Bb", 4), ("B", 4)], ["__b", "_b", "=b"]),
])
def test_named_cases(key, seq, expected):
    key_field = _abc_key_field(key.rstrip("m"), "natural minor" if key.endswith("m") else "major")
    state: dict = {}
    got = [_abc_pitch_in_bar(n, o, key_field, state) for n, o in seq]
    assert got == expected, (key, seq)
    # and the tokens, read back as one bar, are the stored pitches
    abc = f"X:1\nK:{key_field}\n" + " ".join(got) + " |"
    assert read_abc(abc) == [midi(n, o) for n, o in seq]


def test_a_new_bar_returns_to_the_key_signature():
    st: dict = {}
    assert _abc_pitch_in_bar("E", 5, "Cm", st) == "=e'"
    st.clear()
    assert _abc_pitch_in_bar("Eb", 5, "Cm", st) == "e'"


# ---------------------------------------------------------------- property test: every key, every alteration
def _keys() -> list[tuple[str, str]]:
    majors = ["C", "G", "D", "A", "E", "B", "F#", "C#", "F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"]
    minors = ["A", "E", "B", "F#", "C#", "G#", "D#", "A#", "D", "G", "C", "F", "Bb", "Eb", "Ab"]
    return [(k, "major") for k in majors] + [(k, "natural minor") for k in minors]


def _spelled(rng: random.Random) -> str:
    return rng.choice("ABCDEFG") + ALTER_NAME[rng.choices([-2, -1, 0, 1, 2], weights=[1, 4, 8, 4, 1])[0]]


def _bar(rng: random.Random, n: int = 8) -> list[tuple[str, int]]:
    return [(_spelled(rng), rng.choice([3, 4, 5, 6])) for _ in range(n)]


@pytest.mark.parametrize("tonic, tonality", _keys())
def test_every_key_reads_back_as_stored_and_stays_identical_where_it_was_right(tonic, tonality):
    rng = random.Random(f"{tonic}-{tonality}")
    key_field = _abc_key_field(tonic, tonality)
    kept = changed = 0
    for _ in range(60):
        seq = _bar(rng)
        stored = [midi(n, o) for n, o in seq]
        legacy = [_note_to_abc(n, o, key_field=key_field) for n, o in seq]
        state: dict = {}
        new = [_abc_pitch_in_bar(n, o, key_field, state) for n, o in seq]
        header = f"X:1\nK:{key_field}\n"
        assert read_abc(header + " ".join(new) + " |") == stored, (tonic, tonality, seq, new)
        try:
            legacy_right = read_abc(header + " ".join(legacy) + " |") == stored
        except ValueError:
            legacy_right = False                          # the previous writer produced invalid ABC (for example a triple sharp)
        if legacy_right:
            assert new == legacy, ("an answer that was already right changed", tonic, tonality, seq, legacy, new)
            kept += 1
        else:
            changed += 1
    assert kept + changed == 60


def _composition(seq_by_bar: list[list[tuple[str, int]]], tonic: str, tonality: str) -> MusicalIdeaComposition:
    events = [MusicalEvent(spelled=n, octave=o, duration="eighth", bar_index=b, beat=i * 0.5) for b, bar in enumerate(seq_by_bar) for i, (n, o) in enumerate(bar)]
    return MusicalIdeaComposition(events=tuple(events), reference_key=tonic, meter="4/4", bars=len(seq_by_bar), object_type="pattern", style="test",
                                  notation_profile=notation_profile_for_instrument("Flute"), tonic=tonic, tonality=tonality)


@pytest.mark.parametrize("tonic, tonality", [("C", "minor"), ("G", "major"), ("Eb", "major"), ("F#", "major"), ("D", "minor"), ("Bb", "minor")])
def test_the_real_writer_reads_back_as_stored_across_bars(tonic, tonality):
    """The whole writer (beaming, chords, bar lines), not just the helper: accidentals reset at each bar line and never leak across it."""
    rng = random.Random(f"writer-{tonic}-{tonality}")
    bars = [_bar(rng) for _ in range(12)]
    abc, _diag = composition_to_abc(_composition(bars, tonic, tonality), title="t", bpm=100)
    assert read_abc(abc) == [midi(n, o) for bar in bars for n, o in bar]


# ---------------------------------------------------------------- real exercises, every supported instrument
SAXES = {"Alto": "Alto saxophone (Eb)", "Tenor": "Tenor saxophone (Bb)", "Soprano": "Soprano saxophone (Bb)"}
INSTRUMENTS = ["Flute", "Piano", "Alto", "Tenor", "Soprano", "Trumpet", "Clarinet"]
RECIPES = [None, "Change it to fourths", "Add chromatic approaches", "Make the rhythm more syncopated", "Add anticipations of the next chord", "Make it more advanced"]


def _stored_written(ex: dict) -> list[int]:
    return [midi(e["spelled"], int(e["octave"])) for e in ex["provenance"]["written_events"]
            if str(e["spelled"] or "").strip() and not str(e["duration"]).startswith("rest")]


@pytest.mark.parametrize("name", INSTRUMENTS)
@pytest.mark.parametrize("q", [ASK, ASK_CHORDS])
def test_real_exercises_show_the_stored_pitches(name, q):
    inst = {"Alto": "Alto Saxophone", "Tenor": "Tenor Saxophone", "Soprano": "Soprano Saxophone"}.get(name, name)
    s, _resp, _ = begin(q, name)
    for step in RECIPES:
        if step:
            run_coach_submit(step, s, ami_ctx=ctx(instrument=inst))
        ver = cs.current_version(s)
        assert read_abc(ver["abc"]) == _stored_written(ver["exercise"]), (name, q[:32], step)


# ---------------------------------------------------------------- the writer's key-signature table agrees with the K: line an ABC reader will use
@pytest.mark.parametrize("tonic, tonality", _keys())
def test_the_writers_key_table_matches_the_abc_key_signature(tonic, tonality):
    from music_theory import abc_key_signature_letter_alterations

    k_field = _abc_key_field(tonic, tonality)
    table = {letter.lower(): alter for letter, alter in abc_key_signature_letter_alterations(k_field).items() if alter}
    assert table == key_signature(f"K:{k_field}\n"), (k_field, table)
