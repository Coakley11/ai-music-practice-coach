"""One melody per song / jam and setting: projected for key, instrument and tempo; composed only when asked.

User, 2026-11-25 (sections 9-11): Generate Another, style and focus changes, instrument refitting, Key Cycling, reload,
kept melodies -- the same for Catalog, Custom, Composition and both jams (they only differ in identity and chords).
"""

from __future__ import annotations

import json

import pytest

import practice_melody_library as library
from chord_scale_selection import chord_scale_pcs
from music_theory import pitch_class_from_spelled_note, spell_chord_tones, transpose_sections_dict
from practice_melody_model import validate_practice_melody
from practice_melody_notation import practice_melody_full_song_abc
from practice_melody_session import instrument_register_args

JAZZ_D = {"Head": ["Em7", "A7", "Dmaj7", "B7", "Em7", "A7", "Dmaj7", "Dmaj7"], "Bridge": ["Gm7", "C7", "F#m7", "B7", "Em7", "A7", "D6", "D6"]}


def _get(session, *, sections=JAZZ_D, key="D", shown="", style="Jazz swing", level="Intermediate", focus="", tempo=120, identity="jam::x",
         instrument="", offset=0, **kw):
    return library.resolve(
        session, identity=identity, title="Jam Session Generator", sections=sections, section_order=list(sections), sections_key=key,
        key_center=shown, level=level, tempo_bpm=tempo, style=style, focus=focus, instrument=instrument, written_offset=offset, **kw,
    )


def _midis(m):
    return [e.midi for s in m.sections for e in s.events if not e.is_rest]


def _line(m):
    return [(s.section_id, e.measure, e.beat, e.duration_beats, e.midi) for s in m.sections for e in s.events]


def _rhythm(m):
    return [x[:4] for x in _line(m)]


def _chords(m):
    return [c for s in m.sections for c in s.chords]


def _pcs(chord):
    return {pitch_class_from_spelled_note(t) % 12 for t in spell_chord_tones(chord)}


# --- what composes, what does not ---------------------------------------------------------------------


def test_reopening_reruns_tempo_and_reload_never_change_a_note():
    s = {}
    first = _get(s)
    assert _line(_get(s)) == _line(first) and _line(_get(s, tempo=66)) == _line(first) == _line(_get(s, tempo=180))
    assert _get(s, tempo=66).tempo_bpm == 66
    reloaded = {library.LIBRARY_KEY: json.loads(json.dumps(s[library.LIBRARY_KEY]))}  # a new browser session
    assert _line(_get(reloaded)) == _line(first)


def test_generate_another_is_another_melody_over_the_same_harmony():
    s = {}
    seen = [_get(s)] + [_get(s, another=True) for _ in range(5)]
    assert len({str(_line(m)) for m in seen}) == 6 and len({str(_rhythm(m)) for m in seen}) >= 5
    for m in seen:
        assert _chords(m) == [c for chs in JAZZ_D.values() for c in chs] and validate_practice_melody(m) == []
        a, b = {x[1:] for x in _line(m)}, {x[1:] for x in _line(seen[0])}
        assert m is seen[0] or len(a & b) / len(a) < 0.5
    assert library.alternatives(s, "jam::x", library.recipe_for("Intermediate", "Jazz swing", "", (4, 4))) == (5, 6)


def test_previous_alternatives_come_back():
    s = {}
    first, second = _get(s), _get(s, another=True)
    assert _line(_get(s, step=-1)) == _line(first) == _line(_get(s, step=-1))
    assert _line(_get(s, step=1)) == _line(second) == _line(_get(s))


def test_a_groove_change_gets_its_own_melody_and_going_back_returns_the_earlier_one():
    s = {}
    _get(s)
    swing = _get(s, another=True)
    bossa = _get(s, style="Bossa nova")
    rock = _get(s, style="Rock")
    assert len({str(_rhythm(m)) for m in (swing, bossa, rock)}) == 3
    off = lambda m: sum(1 for x in _line(m) if x[4] and x[2] % 1 and x[3] >= 1)  # noqa: E731
    assert off(bossa) > off(rock)
    assert _chords(bossa) == _chords(swing)
    assert _line(_get(s)) == _line(swing)


def test_focus_marks_or_recomposes_as_its_purpose_needs():
    s = {}
    plain = _get(s)
    articulated, dynamic = _get(s, focus="Articulation"), _get(s, focus="Dynamics")
    assert _line(articulated) == _line(plain) == _line(dynamic)
    marks = lambda m: [(e.articulation, e.slur, e.dynamic) for x in m.sections for e in x.events]  # noqa: E731
    assert len({str(marks(m)) for m in (plain, articulated, dynamic)}) == 3
    assert _line(_get(s, focus="Pentatonics")) != _line(plain)
    assert _line(_get(s)) == _line(plain)


def test_each_song_or_jam_has_its_own():
    s = {}
    a, b = _get(s, identity="jam::a"), _get(s, identity="pk::Pop::Perfect")
    assert _line(a) != _line(b)
    _get(s, identity="jam::a", another=True)
    assert _line(_get(s, identity="pk::Pop::Perfect")) == _line(b)


def test_no_chords_no_melody():
    assert _get({}, sections={}) is None


# --- keys -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["E", "B", "C", "Ab", "F#"])
def test_a_key_change_transposes_the_same_melody(key):
    s = {}
    home = _get(s)
    moved = _get(s, sections=transpose_sections_dict(JAZZ_D, "D", key), key=key)
    steps = {a - b for a, b in zip(_midis(moved), _midis(home))}
    assert len(steps) == 1 and moved.key_center == key and moved.melody_id == home.melody_id
    assert _rhythm(moved) == _rhythm(home)
    for sec in moved.sections:
        for e in sec.events:
            if e.midi is not None:
                assert pitch_class_from_spelled_note(e.pitch) % 12 == e.midi % 12
    assert _line(_get(s)) == _line(home)


def test_concert_d_reads_e_for_tenor_and_b_for_alto():
    s = {}
    concert = _get(s)
    tenor, alto = _get(s, shown="E"), _get(s, shown="B")
    assert {(a - b) % 12 for a, b in zip(_midis(tenor), _midis(concert))} == {2}
    assert {(a - b) % 12 for a, b in zip(_midis(alto), _midis(concert))} == {9}
    assert _chords(tenor)[:3] == ["F#m7", "B7", "Emaj7"] and _chords(alto)[:3] == ["C#m7", "F#7", "Bmaj7"]
    assert "K:E" in practice_melody_full_song_abc(tenor) and "K:B" in practice_melody_full_song_abc(alto)


def test_key_cycling_laps_never_compose_or_drift():
    s = {}
    start = _get(s)
    before = json.dumps(s[library.LIBRARY_KEY])
    for _ in range(3):
        for key in ("D", "G", "C", "F", "Bb", "Eb", "Ab", "Db", "F#", "B", "E", "A"):
            m = _get(s, shown=key)
            steps = {a - b for a, b in zip(_midis(m), _midis(start))}
            assert len(steps) == 1 and abs(steps.pop()) <= 6 and _rhythm(m) == _rhythm(start)
    assert json.dumps(s[library.LIBRARY_KEY]) == before and _line(_get(s)) == _line(start)


def test_guitar_shapes_stay_while_the_key_cycles():
    s = {}
    shape = _get(s, shown="A", instrument="Guitar")  # concert D fingered as A shapes
    assert _chords(shape)[:3] == ["Bm7", "E7", "Amaj7"]
    for concert in ("E", "F#", "G"):
        again = _get(s, sections=transpose_sections_dict(JAZZ_D, "D", concert), key=concert, shown="A", instrument="Guitar")
        assert _line(again) == _line(shape) and _chords(again) == _chords(shape)


# --- instruments --------------------------------------------------------------------------------------

PLAYERS = {
    "Flute": "treble",
    "Alto saxophone (Eb)": "treble",
    "Tenor saxophone (Bb)": "treble",
    "Soprano saxophone (Bb)": "treble",
    "Baritone saxophone (Eb)": "treble",
    "Clarinet": "treble",
    "Trumpet": "treble",
    "Trombone": "bass",
    "Bass": "bass",
    "Guitar": "treble-8",
    "Piano": "treble",
}
STYLES = ["Jazz swing", "Bossa nova", "Samba", "Rock", "Pop", "Ballad"]


@pytest.mark.parametrize("instrument", list(PLAYERS))
@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
def test_every_instrument_reads_its_own_clef_and_register(instrument, level):
    low, high = library.display_register(instrument, level)
    for style in STYLES:
        for key in ("D", "Ab", "F#"):
            m = _get({}, sections=transpose_sections_dict(JAZZ_D, "D", key), key=key, style=style, level=level, instrument=instrument)
            notes = _midis(m)
            assert min(notes) >= low and max(notes) <= high + 2, (style, key, min(notes), max(notes), low, high)
            assert validate_practice_melody(m) == []
    assert library.melody_clef(instrument) == PLAYERS[instrument]
    if PLAYERS[instrument] != "treble":
        assert f"clef={PLAYERS[instrument]}" in practice_melody_full_song_abc(m, clef=library.melody_clef(instrument))


def test_changing_instrument_keeps_the_tune():
    s = {}
    plain = _get(s)
    for instrument in PLAYERS:
        m = _get(s, instrument=instrument)
        assert _rhythm(m) == _rhythm(plain), instrument
        assert [x % 12 for x in _midis(m)] == [x % 12 for x in _midis(plain)], instrument
        assert _chords(m) == _chords(plain) and m.key_center == "D"
    assert _line(_get(s)) == _line(plain)


def test_the_written_saxophone_register_is_used_in_written_charts():
    from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY, SELECTED_TRANSPOSING_INSTRUMENT_KEY

    s = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Baritone saxophone (Eb)", CHART_IN_INSTRUMENT_KEY_KEY: True}
    args = instrument_register_args(s, "Saxophone")
    low, high = library.display_register(args["instrument"], "Beginner", args["written_offset"])
    m = _get(s, shown="B", instrument=args["instrument"], offset=args["written_offset"], level="Beginner")
    assert min(_midis(m)) >= low >= 58 and max(_midis(m)) <= high + 2 <= 83  # never living in the altissimo


@pytest.mark.parametrize("instrument", ["Flute", "Baritone saxophone (Eb)", "Bass", "Guitar"])
def test_the_notes_still_fit_the_chords_after_refitting(instrument):
    for style in STYLES:
        m = _get({}, style=style, instrument=instrument)
        for sec in m.sections:
            for e in sec.events:
                if e.tone_role == "chord_tone":
                    assert e.midi % 12 in _pcs(e.chord)
                elif e.tone_role == "passing":
                    assert e.midi % 12 in set(chord_scale_pcs(e.chord, "D", style=style)) | _pcs(e.chord)


# --- kept melodies ------------------------------------------------------------------------------------


def _keep(s, m, sections=JAZZ_D, key="D"):
    return library.keep(s, "jam::x", m, sections=sections, section_order=list(sections), sections_key=key)


def test_a_kept_melody_survives_style_focus_level_and_more_alternatives():
    s = {}
    mine = _get(s, another=True)
    kept = _keep(s, mine)
    assert _keep(s, mine) == kept and len(library.kept_melodies(s, "jam::x")) == 1
    for kw in ({"style": "Rock"}, {"focus": "Pentatonics"}, {"level": "Advanced"}):
        _get(s, **kw)
    for _ in range(40):
        _get(s, another=True)
    library.view_kept(s, "jam::x", kept)
    assert _line(_get(s)) == _line(mine)
    assert _line(_get(s, style="Rock")) == _line(mine)  # chosen: it stays whatever the groove is
    s2 = {library.LIBRARY_KEY: json.loads(json.dumps(s[library.LIBRARY_KEY]))}
    assert _line(_get(s2)) == _line(mine)
    in_e = _get(s, sections=transpose_sections_dict(JAZZ_D, "D", "E"), key="E")
    assert {a - b for a, b in zip(_midis(in_e), _midis(mine))} == {2}
    _get(s, another=True)
    assert library.viewing(s, "jam::x") == "" and len(library.kept_melodies(s, "jam::x")) == 1


def test_a_changed_progression_never_silently_wears_the_old_melody():
    s = {}
    mine = _get(s)
    kept = _keep(s, mine)
    changed = {**JAZZ_D, "Bridge": ["Bbmaj7", "Eb7", "Abmaj7", "Db7", "Em7", "A7", "D6", "D6"]}
    new = _get(s, sections=changed)
    assert _chords(new) == [c for chs in changed.values() for c in chs]
    for sec in new.sections:
        for e in sec.events:
            if e.tone_role == "chord_tone":
                assert e.midi % 12 in _pcs(e.chord)
    row = library.kept_melodies(s, "jam::x")[0]
    assert library.fits(row, JAZZ_D, list(JAZZ_D), "D") and not library.fits(row, changed, list(changed), "D")
    assert library.fits(row, transpose_sections_dict(JAZZ_D, "D", "F"), list(JAZZ_D), "F")  # only a key change
    library.view_kept(s, "jam::x", kept)
    assert _chords(_get(s, sections=changed)) == _chords(mine)  # shown with its own chords


def test_the_store_stays_small():
    s = {}
    for i in range(80):
        m = _get(s, identity=f"jam::{i}")
    for _ in range(30):
        m = _get(s, identity="jam::79", another=True)
        library.keep(s, "jam::79", m, sections=JAZZ_D, section_order=list(JAZZ_D), sections_key="D")
    assert len(s[library.LIBRARY_KEY]) <= 31 and len(json.dumps(s[library.LIBRARY_KEY])) < 120_000


def test_it_is_saved_with_the_session():
    import music_persistent_state as mps

    assert "practice_melody_library" in mps._PERSIST_KEYS and "_backing_melody_panels_open" in mps._PERSIST_KEYS
