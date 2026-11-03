"""Staccato in ABC is a decoration written BEFORE the note (".c/2"). Written after ("c./2") abcjs attaches it to the next note and ignores the length.

Covers every writer that can emit staccato: the scale engine (ordinary scale exercises), the shared musical-idea writer (patterns/licks/warmups).
"""
from __future__ import annotations

import re
from fractions import Fraction

import pytest

from music_coach_ami import scale_engine as se
from music_coach_ami.claude_client import AnthropicTransport
from tests.test_ami_warmups import abc_beats, ask, session

_AFTER = re.compile(r"[A-Ga-gz][,']*\.")      # a dot directly after a note letter (with octave marks)


@pytest.fixture(autouse=True)
def _no_live_api(monkeypatch):
    monkeypatch.setattr(AnthropicTransport, "complete", lambda self, **kw: (_ for _ in ()).throw(AssertionError("LIVE API CALL")))


def _body(abc: str) -> str:
    return abc.split("K:", 1)[1].split("\n", 1)[1]


class TestScaleEngineStaccato:
    @pytest.mark.parametrize("note_value", ["quarter", "eighth", "sixteenth"])
    def test_every_staccato_note_has_its_dot_before_it_and_none_after(self, note_value):
        names = ["C", "D", "E", "F", "G", "A", "B", "C"]
        abc = se.build_abc_from_note_names(names, title="t", key_field="C", bpm=80, note_value=note_value, articulation="staccato",
                                           pitched=[(n, 4 if i < 7 else 5) for i, n in enumerate(names)])
        body = _body(abc)
        assert not _AFTER.search(body), body
        assert body.count(".") == 8, body

    def test_a_user_asking_for_a_staccato_scale_gets_the_dot_before_each_note_and_the_right_length(self):
        for q in ("Give me a staccato scale exercise in C on the flute", "Give me a C major scale with staccato eighth notes on the flute"):
            r = ask(session("Flute"), q)
            abc = r.notation_abc or ""
            assert "." in abc, q
            body = _body(abc)
            assert not _AFTER.search(body), (q, body[:200])
            assert abc.count(".") == len(re.findall(r"\.[_^=]*[A-Ga-g]", body)), q      # one dot per note, none left over


class TestSharedWriterStaccato:
    def test_the_idea_writer_puts_the_dot_before_the_note_and_keeps_its_length(self):
        from music_coach_ami.musical_idea_engine import MusicalEvent, MusicalIdeaComposition, composition_to_abc
        from music_coach_ami.notation_profile import notation_profile_for_instrument

        ev = [MusicalEvent("C", 5, "eighth", 0, 1.0, "staccato"), MusicalEvent("D", 5, "eighth", 0, 1.5, "staccato"),
              MusicalEvent("E", 5, "quarter", 0, 2.0, "staccato"), MusicalEvent("F", 5, "half", 0, 3.0, "")]
        comp = MusicalIdeaComposition(tuple(ev), "C", "4/4", 1, "pattern", "x", notation_profile_for_instrument("Flute"), tonic="C", tonality="major")
        abc, _ = composition_to_abc(comp, title="x", bpm=80)
        body = _body(abc)
        assert ".c/2 .d/2 .e" in body and not _AFTER.search(body), body
        assert abc_beats(abc) == Fraction(4)
