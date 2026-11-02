"""The notation AMI hands to the renderer must read back as exactly the pitches AMI stored.

ABC accidentals are absolute and last to the end of the bar for the same pitch in the same octave. The writer used to emit each note relative to
the key signature only, so a note that relied on the key signature after an explicit natural (or sharp / flat) earlier in the same bar was
displayed one semitone off. These tests read the ABC back with an independent reader that follows the ABC rules and compare it, note for note,
with the stored written pitches — for every instrument, both kinds of pattern and the M1c recipes that add chromatic notes.
"""

from __future__ import annotations

import copy
import re

import pytest

from music_coach_ami import conversation_state as cs
from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.musical_idea_engine import _abc_pitch_in_bar
from tests.test_ami_m1b import NAMES, WORDS, source, say
from tests.test_ami_scale_pattern_recipe import ASK, ASK_CHORDS, _no_live_api  # noqa: F401

NOTE = re.compile(r'(?P<chord>"[^"]*")?(?P<deco>(?:!>!|!tenuto!|\.)*)(?P<acc>\^\^|__|[_^=])?(?P<note>[A-Ga-gz])(?P<oct>[,\']*)(?P<dur>\d*(?:/\d*)?)')
BASE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJORS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7, "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
SHARP_ORDER, FLAT_ORDER = "fcgdaeb", "beadgcf"


def _pc(tonic: str) -> int:
    return (PC[tonic[0]] + (1 if tonic.endswith("#") else -1 if tonic.endswith("b") else 0)) % 12


def key_signature(abc: str) -> dict[str, int]:
    m = re.search(r"^K:\s*([A-G][#b]?)\s*(m|min|minor)?", abc, re.M)
    pc = _pc(m.group(1)) if m else 0
    if m and m.group(2):
        pc = (pc + 3) % 12
    major = next(k for k in MAJORS if _pc(k) == pc and k in ("C", "G", "D", "A", "E", "B", "F", "Bb", "Eb", "Ab", "Db", "Gb"))
    n = MAJORS[major]
    return {(SHARP_ORDER if n > 0 else FLAT_ORDER)[i]: (1 if n > 0 else -1) for i in range(abs(n))}


# The coach writer compensates for abc_pitch_for_spelled_note's one-octave-high 'c' (COACH_ABC_OCTAVE_SHIFT = -1), so standard ABC reading (abcjs)
# gives exactly the stored pitch and no offset is needed.
WRITER_OCTAVE_OFFSET = 0


def read_abc(abc: str, octave_offset: int = WRITER_OCTAVE_OFFSET) -> list[int]:
    """Midi numbers of the pitched notes, following the ABC accidental rules (absolute accidentals, lasting to the bar line, per octave)."""
    sig = key_signature(abc)
    body = " ".join(line for line in abc.splitlines() if line and not re.match(r"^[A-Za-z]:", line))
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


def stored_written(ex: dict) -> list[int]:
    return [sph.midi_of(e["spelled"], int(e["octave"])) for e in ex["provenance"]["written_events"]
            if str(e["spelled"] or "").strip() and not str(e["duration"]).startswith("rest")]


# ---------------------------------------------------------------- the rule itself
def test_a_note_that_relies_on_the_key_signature_after_an_explicit_natural_is_marked_again():
    st: dict = {}
    assert _abc_pitch_in_bar("E", 5, "Cm", st) == "=e'"        # E natural against Eb in the key signature
    assert _abc_pitch_in_bar("Eb", 5, "Cm", st) == "_e'"       # the natural is still in force: the flat must be written
    assert _abc_pitch_in_bar("Eb", 5, "Cm", st) == "e'"        # now the flat is in force
    assert _abc_pitch_in_bar("E", 4, "Cm", st) == "=e"         # another octave is a different pitch
    st.clear()                                                  # a new bar: back to the key signature
    assert _abc_pitch_in_bar("Eb", 5, "Cm", st) == "e'"


def test_accidentals_are_absolute_not_relative_to_the_key_signature():
    assert _abc_pitch_in_bar("E#", 5, "Cm", {}) == "^e'"        # was "^^e'" (a double sharp)
    assert _abc_pitch_in_bar("Fb", 5, "G", {}) == "_f'"         # was "__f'"
    assert _abc_pitch_in_bar("F#", 5, "G", {}) == "f'"          # in the key signature already
    assert _abc_pitch_in_bar("F", 5, "G", {}) == "=f'"
    assert _abc_pitch_in_bar("F##", 5, "C", {}) == "^^f'"


# ---------------------------------------------------------------- every answer reads back as what was stored
RECIPES = [None, "Change it to fourths", "Add chromatic approaches", "Make the rhythm more syncopated", "Add anticipations of the next chord", "Make it more advanced"]


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("q", [ASK, ASK_CHORDS])
def test_the_staff_shows_the_stored_pitches(name, q):
    s = source(name, q)
    for step in RECIPES:
        if step:
            say(s, step, name)
        ver = cs.current_version(s)
        assert read_abc(ver["abc"]) == stored_written(ver["exercise"]), (name, q[:30], step)


@pytest.mark.parametrize("dst", ["Flute", "Alto", "Tenor", "Trumpet", "Piano"])
def test_the_staff_shows_the_stored_pitches_after_every_m1b_change(dst):
    s = source("Flute")
    say(s, "Add chromatic approaches")
    for q in (f"Make it suitable for {WORDS[dst]}", "Apply it to Section B", "Undo that", "Redo"):
        say(s, q)
        ver = cs.current_version(s)
        assert read_abc(ver["abc"]) == stored_written(ver["exercise"]), (dst, q)


def test_the_staff_is_drawn_at_the_stored_octave():
    s = source("Flute", ASK_CHORDS)
    ver = cs.current_version(s)
    assert read_abc(ver["abc"], octave_offset=0) == stored_written(ver["exercise"])
