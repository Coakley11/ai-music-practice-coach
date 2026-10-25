"""Guitar TAB C0 correctness: every note the TAB asks for must belong to the written chord.

Checks are made on actual sounding pitches parsed from both the copied (ASCII) TAB
and the visual (HTML) TAB, which must agree measure by measure.
"""

from __future__ import annotations

import re

import pytest

from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, build_capo_context
from guitar_voicing_engine import build_level_guitar_voicings, song_guitar_tabs_for_key
from music_theory import pitch_class_from_spelled_note, spell_chord_tones
from musician_coaching import musician_facing_chart_key
from practice_notation import GUITAR_SHAPES, _measure_beats, _frets_hi_to_lo, generate_practice_notation

OPEN_MIDI = {"e": 64, "B": 59, "G": 55, "D": 50, "A": 45, "E": 40}
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
DIFFICULTIES = ("easy", "medium", "advanced")

# Grips written for the song's original key (G major).
G_KEY_TABS = {"G": "320003", "C": "x32010", "D": "xx0232", "Em": "022000", "Am": "x02210"}


def chord_pcs(chord: str) -> set[int]:
    return {pitch_class_from_spelled_note(t) for t in spell_chord_tones(chord.split("/")[0]) if t}


def root_and_third(chord: str) -> set[int]:
    tones = spell_chord_tones(chord.split("/")[0])
    return {pitch_class_from_spelled_note(tones[0]), pitch_class_from_spelled_note(tones[1])}


def ascii_measures(body: str) -> list[tuple[str, dict[str, list[int | None]]]]:
    out = []
    for block in body.split("\n\n"):
        lines = block.splitlines()
        grid = {}
        for line in lines:
            m = re.match(r"^([eBGDAE])\|(.*)\|$", line)
            if m:
                cells = [m.group(2)[i : i + 7] for i in range(0, len(m.group(2)), 7)]
                grid[m.group(1)] = [int(c.strip("-")) if c.strip("-") else None for c in cells]
        out.append((lines[0].strip(), grid))
    return out


def html_measures(doc: str) -> list[dict[str, list[int | None]]]:
    out = []
    for chunk in re.split(r'<div class="tab-measure[ "]', doc)[1:]:
        grid = {}
        for lbl, track in re.findall(
            r'<span class="tab-str-label">([eBGDAE])</span><span class="tab-str-track">(.*?)</span></div>', chunk
        ):
            cells = re.findall(r'<span class="tab-beat[^"]*">([^<]*)</span>', track)
            grid[lbl] = [int(c) if c.isdigit() else None for c in cells]
        out.append(grid)
    return out


def sounding(grid: dict[str, list[int | None]], capo: int = 0) -> list[int]:
    return [OPEN_MIDI[lbl] + capo + f for lbl, frets in grid.items() for f in frets if f is not None]


def render(*, sections, original_key, display_key, tabs, difficulty, groove="Pop groove", focus="general"):
    res = generate_practice_notation(
        song_title="t", artist="", display_key=display_key, original_key=original_key, bpm=90,
        groove_style=groove, instrument="Guitar", focus=focus, section_focus="Full Song",
        sections=sections, guitar_tabs=tabs, difficulty=difficulty,
    )
    asc = ascii_measures(res.body)
    htm = html_measures(res.html)
    assert len(asc) == len(htm)
    for (_chord, a), h in zip(asc, htm):
        assert a == h, "copied TAB and visual TAB disagree"
    return asc


def assert_sounds_chord(asc, capo: int = 0, *, full: bool = True):
    for chord, grid in asc:
        pcs = {m % 12 for m in sounding(grid, capo)}
        assert pcs, f"{chord}: silent measure"
        outside = pcs - chord_pcs(chord)
        assert not outside, f"{chord}: sounds {sorted(NAMES[p] for p in outside)} outside the chord"
        if full:
            assert root_and_third(chord) <= pcs, f"{chord}: missing root or 3rd"


class TestSongTabsFollowPracticeKey:
    def test_helper_keeps_grips_only_in_their_own_key(self):
        assert song_guitar_tabs_for_key(G_KEY_TABS, "G", "G") == G_KEY_TABS
        assert song_guitar_tabs_for_key({"F#": "244322"}, "F#", "Gb") == {"F#": "244322"}
        assert song_guitar_tabs_for_key(G_KEY_TABS, "G", "A") == {}
        assert song_guitar_tabs_for_key(None, "G", "G") == {}

    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_g_to_a_sounds_the_transposed_chords(self, difficulty):
        asc = render(
            sections={"Verse": ["A", "D", "E", "F#m", "Bm"]}, original_key="G", display_key="A",
            tabs=G_KEY_TABS, difficulty=difficulty,
        )
        assert_sounds_chord(asc)

    def test_g_to_a_beginner_no_longer_plays_the_g_grip(self):
        asc = render(sections={"Verse": ["A"]}, original_key="G", display_key="A", tabs=G_KEY_TABS, difficulty="easy")
        _chord, grid = asc[0]
        pcs = {m % 12 for m in sounding(grid)}
        assert pitch_class_from_spelled_note("G") not in pcs
        assert pcs == chord_pcs("A")

    def test_original_key_keeps_the_songs_own_grips(self):
        asc = render(
            sections={"Verse": ["G", "C", "D", "Em"]}, original_key="G", display_key="G",
            tabs=G_KEY_TABS, difficulty="easy",
        )
        for chord, grid in asc:
            want = _frets_hi_to_lo(G_KEY_TABS[chord])
            for lbl, fret in zip(("e", "B", "G", "D", "A", "E"), want):
                expected = None if fret == "x" else int(fret)
                assert set(grid[lbl]) == {expected}, f"{chord} {lbl}"
        assert_sounds_chord(asc)

    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_song_without_supplied_grips_transposes_correctly(self, difficulty):
        asc = render(
            sections={"Verse": ["Bb", "Eb", "F", "Gm"]}, original_key="G", display_key="Bb",
            tabs={}, difficulty=difficulty,
        )
        assert_sounds_chord(asc)


class TestCapoRelativeShapes:
    def _capo_render(self, *, concert_key, shape_key, concert_sections, original_key):
        session = {CAPO_ENABLED_KEY: True, CAPO_SHAPE_KEY: shape_key}
        ctx = build_capo_context(session, concert_sections, concert_key=concert_key, instrument="Guitar")
        display_key = musician_facing_chart_key(
            chart_key=concert_key, instrument="Guitar", capo_enabled=True, shape_key=ctx.shape_key
        )
        asc = render(
            sections=ctx.shape_sections, original_key=original_key, display_key=display_key,
            tabs=G_KEY_TABS, difficulty="easy",
        )
        return ctx, asc

    def test_capo_shapes_in_original_key_keep_song_grips_and_sound_concert_chords(self):
        concert = {"Verse": ["Bb", "Eb", "F", "Gm"]}
        ctx, asc = self._capo_render(concert_key="Bb", shape_key="G", concert_sections=concert, original_key="G")
        assert ctx.capo_fret == 3
        for (shape_chord, grid), concert_chord in zip(asc, concert["Verse"]):
            lowest = _frets_hi_to_lo(G_KEY_TABS[shape_chord])
            assert [grid[lbl][0] for lbl in ("e", "B", "G", "D", "A", "E")] == [
                None if f == "x" else int(f) for f in lowest
            ]
            pcs = {m % 12 for m in sounding(grid, ctx.capo_fret)}
            assert pcs <= chord_pcs(concert_chord) and root_and_third(concert_chord) <= pcs

    def test_capo_shapes_in_another_key_do_not_reuse_original_grips(self):
        concert = {"Verse": ["C", "F", "G", "Am"]}
        ctx, asc = self._capo_render(concert_key="C", shape_key="A", concert_sections=concert, original_key="G")
        assert ctx.capo_fret == 3
        for (_shape_chord, grid), concert_chord in zip(asc, concert["Verse"]):
            pcs = {m % 12 for m in sounding(grid, ctx.capo_fret)}
            assert pcs <= chord_pcs(concert_chord) and root_and_third(concert_chord) <= pcs


class TestBuiltInShapes:
    def test_bdim_sounds_b_d_f(self):
        notes = [OPEN_MIDI[l] + int(f) for l, f in zip(("E", "A", "D", "G", "B", "e"), GUITAR_SHAPES["Bdim"]) if f != "x"]
        assert {n % 12 for n in notes} == chord_pcs("Bdim") == {11, 2, 5}

    @pytest.mark.parametrize("chord", sorted(GUITAR_SHAPES))
    def test_every_built_in_shape_sounds_only_its_chord(self, chord):
        shape = GUITAR_SHAPES[chord]
        notes = [OPEN_MIDI[l] + int(f) for l, f in zip(("E", "A", "D", "G", "B", "e"), shape) if f != "x"]
        pcs = {n % 12 for n in notes}
        assert pcs <= chord_pcs(chord), f"{chord} {shape} sounds {sorted(NAMES[p] for p in pcs - chord_pcs(chord))}"
        assert root_and_third(chord) <= pcs

    def test_beginner_bdim_bar(self):
        asc = render(sections={"Verse": ["Bdim"]}, original_key="C", display_key="C", tabs={}, difficulty="easy")
        assert_sounds_chord(asc)


BOSSA_PROGRESSION = ["C", "G", "D", "Am7", "Dm7", "Bb", "Cmaj7", "E", "F", "Bm7b5", "Fmaj7", "Em"]


class TestBossaBass:
    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    @pytest.mark.parametrize("focus", ["general", "rhythm"])
    def test_every_bossa_note_is_a_chord_tone_and_playable(self, difficulty, focus):
        asc = render(
            sections={"Verse": BOSSA_PROGRESSION}, original_key="C", display_key="C", tabs={},
            difficulty=difficulty, groove="Bossa nova", focus=focus,
        )
        for chord, grid in asc:
            pcs = {m % 12 for m in sounding(grid)}
            assert pcs <= chord_pcs(chord), f"{chord}: {sorted(NAMES[p] for p in pcs - chord_pcs(chord))}"
            fretted = [f for frets in grid.values() for f in frets if f]
            assert not fretted or max(fretted) - min(fretted) <= 4, f"{chord}: stretch {sorted(set(fretted))}"

    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_bass_on_beats_1_and_3_is_the_voicings_lowest_note(self, difficulty):
        level = {"easy": "Beginner", "medium": "Intermediate", "advanced": "Advanced"}[difficulty]
        voicings = build_level_guitar_voicings(BOSSA_PROGRESSION, level=level)
        asc = render(
            sections={"Verse": BOSSA_PROGRESSION}, original_key="C", display_key="C", tabs={},
            difficulty=difficulty, groove="Bossa nova",
        )
        for (chord, grid), ev in zip(asc, voicings):
            lowest = min(OPEN_MIDI[l] + int(f) for l, f in zip(("E", "A", "D", "G", "B", "e"), ev.shape) if f != "x")
            for slot in (0, 4):
                attacks = [OPEN_MIDI[l] + grid[l][slot] for l in grid if grid[l][slot] is not None]
                assert min(attacks) == lowest, f"{chord} slot {slot}"

    def test_open_c_alternates_root_and_fifth_without_open_e(self):
        b = _measure_beats(_frets_hi_to_lo("x32010"), {"pattern": "bossa"}, "rhythm")
        assert b["A"][0] == b["A"][4] == "3"  # C3
        assert b["E"][2] == b["E"][6] == "3"  # G2 (fifth below), not E2/F#2
        assert b["E"][0] is None and b["E"][4] is None

    def test_muted_low_strings_are_never_invented(self):
        b = _measure_beats(_frets_hi_to_lo("xx0232"), {"pattern": "bossa"}, "rhythm")
        assert all(f is None for f in b["E"])
        assert b["D"][0] == b["D"][4] == "0"  # D3 root
        assert b["A"][2] == b["A"][6] == "0"  # A2 fifth (open A is a chord tone)


class TestFingerstyleBass:
    @pytest.mark.parametrize(
        "shape,bass_label,bass_fret",
        [("xx0232", "D", "0"), ("xx000x", "D", "0"), ("x32010", "A", "3"), ("320003", "E", "3")],
    )
    def test_bass_uses_the_lowest_sounding_string(self, shape, bass_label, bass_fret):
        grip = _frets_hi_to_lo(shape)
        b = _measure_beats(grip, {"pattern": "fingerstyle"}, "general")
        assert b[bass_label][0] == b[bass_label][4] == bass_fret
        for lbl, fret in zip(("e", "B", "G", "D", "A", "E"), grip):
            if fret == "x":
                assert all(f is None for f in b[lbl]), f"muted {lbl} string was picked"

    @pytest.mark.parametrize("difficulty", DIFFICULTIES)
    def test_downbeats_always_sound_in_ballad_fingerstyle(self, difficulty):
        chords = ["D", "G", "C", "Em", "Am", "F", "Bm", "A7", "Dm7", "Gmaj7", "Em9", "Cmaj9"]
        asc = render(
            sections={"Verse": chords}, original_key="C", display_key="C", tabs={},
            difficulty=difficulty, groove="Ballad",
        )
        for chord, grid in asc:
            for slot in (0, 4):
                assert any(grid[l][slot] is not None for l in grid), f"{chord}: rest on slot {slot}"
            assert {m % 12 for m in sounding(grid)} <= chord_pcs(chord)
