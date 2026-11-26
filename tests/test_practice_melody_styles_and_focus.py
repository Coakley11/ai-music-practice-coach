"""A Practice Melody is written in its style and for its Practice Focus -- not one tune with another label.

User, 2026-11-25. Measured on the notes themselves, over several melodies per case.
"""

from __future__ import annotations

import pytest

from composition_melody_notation import build_abc_from_melody_events
from music_theory import spell_chord_tones, pitch_class_from_spelled_note
from practice_melody_composer import focus_intent, note_intent, pentatonic_pcs, style_family
from practice_melody_generator import generate_practice_melody
from practice_melody_model import validate_practice_melody
from practice_melody_notation import practice_melody_full_song_abc

JAZZ = {"Head": ["Dm7", "G7", "Cmaj7", "A7"] * 2, "Bridge": ["Fmaj7", "Fm7", "Em7", "A7", "Dm7", "G7", "C6", "C6"]}
POP = {"Verse": ["C", "Am", "F", "G"] * 2, "Chorus": ["F", "G", "C", "Am", "F", "G", "C", "C"]}


def _make(style, sections=JAZZ, focus="", level="Intermediate", i=0, **kw):
    return generate_practice_melody(
        song_id=f"s{i}", song_title="t", sections=sections, key_center="C", level=level, tempo_bpm=120, style=style, focus=focus, **kw
    )


def _notes(m):
    return [e for s in m.sections for e in s.events if not e.is_rest]


def _pcs(chord):
    return {pitch_class_from_spelled_note(t) % 12 for t in spell_chord_tones(chord)}


def _stats(style, sections=JAZZ, focus="", level="Intermediate"):
    notes, rest, bars, steps, pairs = [], 0.0, 0, 0, 0
    for i in range(8):
        m = _make(style, sections, focus, level, i)
        assert validate_practice_melody(m) == []
        for s in m.sections:
            bars += s.measures
            rest += sum(e.duration_beats for e in s.events if e.is_rest)
            own = [e for e in s.events if not e.is_rest]
            notes += own
            for a, b in zip(own, own[1:]):
                pairs += 1
                steps += abs(a.midi - b.midi) <= 2
    n = len(notes)
    return {
        "per_bar": n / bars,
        "syncopated": sum(1 for e in notes if e.beat % 1 and e.duration_beats >= 1) / n,
        "rest": rest / bars,
        "steps": steps / pairs,
        "chord": sum(e.midi % 12 in _pcs(e.chord) for e in notes) / n,
        "slurs": sum(e.slur == "start" for e in notes) / bars,
        "staccato": sum(e.articulation == "staccato" for e in notes) / bars,
        "approach": sum(e.tone_role == "approach" for e in notes) / bars,
    }


def test_every_style_has_its_own_language():
    swing, bossa, samba, rock, pop, ballad, funk = (
        _stats(s, JAZZ if s in {"Jazz swing", "Bossa nova", "Samba"} else POP)
        for s in ("Jazz swing", "Bossa nova", "Samba", "Rock", "Pop", "Ballad", "Funk")
    )
    assert bossa["syncopated"] > 4 * pop["syncopated"] and samba["syncopated"] > 3 * rock["syncopated"] + 0.1
    assert ballad["per_bar"] < pop["per_bar"] < rock["per_bar"] < samba["per_bar"] + 0.5
    assert bossa["per_bar"] < swing["per_bar"]  # relaxed, with space
    assert funk["rest"] > 2 * rock["rest"] and funk["staccato"] > 1
    assert ballad["slurs"] > 0.6 and rock["slurs"] == 0
    assert swing["approach"] > 3 * max(pop["approach"], 0.005)


def test_the_same_song_in_another_style_is_another_melody():
    lines = {s: [(e.measure, e.beat, e.midi) for e in _notes(_make(s))] for s in ("Jazz swing", "Bossa nova", "Samba", "Rock", "Ballad")}
    assert len({str(v) for v in lines.values()}) == 5


def test_focus_decides_the_material():
    plain = _stats("Jazz swing")
    assert _stats("Jazz swing", focus="Scales")["steps"] > plain["steps"] + 0.15
    assert _stats("Jazz swing", focus="Tone")["per_bar"] < 0.5 * plain["per_bar"]
    assert _stats("Jazz swing", focus="Triads")["chord"] > plain["chord"]
    assert _stats("Jazz swing", focus="Breath Support")["rest"] > plain["rest"]
    assert _stats("Pop", POP, focus="Rhythm")["syncopated"] > 2 * _stats("Pop", POP)["syncopated"]


def test_jazz_swing_with_pentatonics_is_pentatonic_and_still_swings_over_the_changes():
    notes = [e for i in range(6) for e in _notes(_make("Jazz swing", focus="Pentatonics", i=i))]
    inside = sum(e.midi % 12 in set(pentatonic_pcs(e.chord)) for e in notes) / len(notes)
    assert inside > 0.75
    stats = _stats("Jazz swing", focus="Pentatonics")
    assert stats["chord"] > 0.7 and abs(stats["per_bar"] - _stats("Jazz swing")["per_bar"]) < 0.8
    assert sum(bool(e.beat % 1) for e in notes) / len(notes) > 0.3


@pytest.mark.parametrize("focus", ["Articulation", "Dynamics"])
def test_articulation_and_dynamics_mark_the_same_notes(focus):
    plain, marked = _make("Jazz swing"), _make("Jazz swing", focus=focus)
    line = lambda m: [(e.measure, e.beat, e.duration_beats, e.midi) for s in m.sections for e in s.events]  # noqa: E731
    assert line(plain) == line(marked)
    marks = [(e.articulation, e.slur, e.dynamic) for e in _notes(marked)]
    assert marks != [(e.articulation, e.slur, e.dynamic) for e in _notes(plain)]
    if focus == "Articulation":
        assert {"accent", "staccato", "tenuto"} <= {a for a, _s, _d in marks} and any(s for _a, s, _d in marks)
    else:
        assert len({d for _a, _s, d in marks if d}) >= 3


def test_a_phrase_states_a_motif_and_breathes():
    for i in range(6):
        m = _make("Jazz swing", i=i)
        for s in m.sections:
            rhythm = [tuple((e.beat, e.duration_beats, e.is_rest) for e in s.events if e.measure == b) for b in range(s.measures)]
            assert rhythm[0] in (rhythm[1], rhythm[2])  # the motif comes back inside its phrase
            assert any(e.is_rest or e.duration_beats >= 2 for e in s.events if e.measure == 3)  # and the phrase ends


def test_slurs_never_cross_a_rest_or_a_bar():
    for style in ("Jazz swing", "Bossa nova", "Samba", "Ballad", "Pop"):
        for focus in ("", "Articulation"):
            for s in _make(style, focus=focus, level="Advanced").sections:
                opened = None
                for e in s.events:
                    if e.slur == "start":
                        assert opened is None
                        opened = e
                    elif opened is not None and not e.slur:
                        assert not e.is_rest and e.measure == opened.measure
                    if opened is not None and e is not opened:
                        assert e.midi != last  # two equal notes under a slur would read as a tie
                    last = e.midi
                    if e.slur == "end":
                        assert opened is not None and e.measure == opened.measure
                        opened = None
                assert opened is None


@pytest.mark.parametrize("meter", [(4, 4), (3, 4), (2, 4), (5, 4), (6, 8), (9, 8), (12, 8)])
@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
def test_every_printed_bar_is_exactly_full(meter, level):
    import re

    m = _make("Pop", POP, level=level, meter=meter)
    assert validate_practice_melody(m) == []
    abc = practice_melody_full_song_abc(m)
    music = "".join(ln for ln in abc.split("\n") if not re.match(r"^[A-Z]:", ln))
    bars = [b for b in music.split("|") if b.strip()]
    want = meter[0] * (8 // meter[1])
    assert len(bars) == 16
    for bar in bars:
        bar = re.sub(r'"[^"]*"|![^!]*!', "", bar)
        got = sum(int(n or 1) for n in re.findall(r"[=^_]*[A-Ga-gz][,']*(\d*)", bar))
        assert got == want, (bar, got)
    assert build_abc_from_melody_events  # the app's own notation builder is what was read


def test_a_split_bar_is_composed_over_both_chords():
    m = _make("Jazz swing", {"A": ["Dm7|G7", "Cmaj7", "Am7|D7", "G6"]}, level="Advanced")
    chords = {e.chord for e in _notes(m)}
    assert "Dm7" in chords and not any("|" in c for c in chords)
    for e in _notes(m):
        if e.tone_role == "chord_tone":
            assert e.midi % 12 in _pcs(e.chord)


def test_no_chord_is_a_rest():
    m = _make("Pop", {"A": ["C", "N.C.", "F", "C"]})
    assert validate_practice_melody(m) == []
    assert all(e.is_rest for e in m.sections[0].events if e.measure == 1)


def test_labels_map_to_the_apps_own_styles_and_focuses():
    assert [style_family(s) for s in ("Jazz swing", "Bossa nova", "Samba", "Latin jazz", "Blues groove", "Funk", "Rock", "Ballad", "Pop", "Neo Soul", "Klezmer", "Auto")] == [
        "swing", "bossa", "samba", "latin", "blues", "funk", "rock", "ballad", "pop", "funk", "klezmer", "pop"]
    assert focus_intent("Breath Support") == "phrasing" and focus_intent("Bebop Phrasing") == "improvisation"
    assert note_intent("Articulation") == "" and note_intent("Guide Tones") == "guide_tones"
