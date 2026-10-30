"""Chord Tone Hints: characteristic chord tones, spelled, under the chord name.

Rules (agreed with the user): name what a symbol adds beyond its plain triad --
6ths, 7ths, 9/11/13, suspensions, altered 5ths and altered extensions -- on
their own letters, at most three (one per chord in a split bar); plain triads get
none; the 3rd only where the other tones suggest the opposite quality (7#9,
m(maj7)). Also pins the shared-parser fixes behind them (music_theory /
chord_facts): 7(#11) and 7#9 no longer gain a natural 9th / 11th, diminished
tones keep their letters (Cdim7: Bbb), and Cb / Fb / E# / B# roots spell.
"""
from __future__ import annotations

import re

import pytest

from chord_tone_hints import (
    CHORD_TONE_HINTS_KEY,
    HINTS_STYLE,
    apply_chord_tone_hints,
    hints_enabled,
    pretty_note,
    sheet_with_chord_tone_hints,
    strip_chord_tone_hints,
    toggle_script_html,
    tone_hints,
)


def _t(symbol, **kw):
    return ", ".join(h.text() for h in tone_hints(symbol, **kw))


@pytest.mark.parametrize(
    "symbol, expected",
    [
        # The user's examples (E♭m9 under the agreed rule: no 3rd on a plain minor 9th).
        ("C7(b9)", "B♭ (♭7), D♭ (♭9)"),
        ("Fm9", "E♭ (♭7), G (9)"),
        ("Dm6", "B (6)"),
        ("Gmaj7", "F♯ (7)"),
        ("A7(#11)", "G (♭7), D♯ (♯11)"),
        ("Ebm9", "D♭ (♭7), F (9)"),
        # Sevenths / sixths / extensions.
        ("C7", "B♭ (♭7)"), ("Dm7", "C (♭7)"), ("Abmaj7", "G (7)"), ("F#m7", "E (♭7)"),
        ("C6", "A (6)"), ("C6/9", "A (6), D (9)"), ("Cadd9", "D (9)"), ("Cmaj9", "B (7), D (9)"),
        ("C9", "B♭ (♭7), D (9)"), ("Cm11", "B♭ (♭7), D (9), F (11)"),
        ("C13", "B♭ (♭7), D (9), A (13)"), ("Db13", "C♭ (♭7), E♭ (9), B♭ (13)"),
        # Altered tones first when more than three qualify.
        ("C13#11", "D (9), F♯ (♯11), A (13)"), ("C7alt", "D♭ (♭9), D♯ (♯9), A♭ (♭13)"),
        ("D7(b9,#11)", "C (♭7), E♭ (♭9), G♯ (♯11)"), ("Cmaj7#11", "B (7), F♯ (♯11)"),
        # Altered fifths, diminished, half-diminished, augmented.
        ("Cdim", "G♭ (♭5)"), ("Cdim7", "G♭ (♭5), B𝄫 (𝄫7)"), ("Ebdim7", "B𝄫 (♭5), D𝄫 (𝄫7)"),
        ("Bm7b5", "F (♭5), A (♭7)"), ("Cm7b5", "G♭ (♭5), B♭ (♭7)"),
        ("Caug", "G♯ (♯5)"), ("C7#5", "G♯ (♯5), B♭ (♭7)"),
        # Suspensions.
        ("Csus4", "F (4)"), ("Csus2", "D (2)"), ("C7sus4", "F (4), B♭ (♭7)"), ("C9sus4", "F (4), B♭ (♭7), D (9)"),
        # The 3rd only where it settles the quality.
        ("E7#9", "G♯ (3), D (♭7), F𝄪 (♯9)"), ("Cm(maj7)", "E♭ (♭3), B (7)"), ("CmMaj7", "E♭ (♭3), B (7)"),
        # Slash chords: the chord's own tones; a 7th in the bass is still the 7th.
        ("G7/F", "F (♭7)"), ("Cmaj7/E", "B (7)"),
        # Prettified input (as some charts display it).
        ("B♭7", "A♭ (♭7)"),
    ],
)
def test_hints(symbol, expected) -> None:
    assert _t(symbol) == expected


@pytest.mark.parametrize("symbol", ["C", "Cm", "F#", "Bbm", "C5", "C/E", "D/F#", "N.C.", "%", "", "Bm.hit"])
def test_plain_triads_and_non_chords_get_none(symbol) -> None:
    assert tone_hints(symbol) == ()


def test_never_more_than_three_and_one_for_split_bars() -> None:
    for sym in ("C13#11", "C7alt", "C7(b9,#9,#11,b13)", "Cm11", "C9sus4"):
        assert 1 <= len(tone_hints(sym)) <= 3
        assert len(tone_hints(sym, max_tones=1)) == 1
    # The single tone is the most characteristic one.
    assert _t("Fm9", max_tones=1) == "G (9)"
    assert _t("C7(b9)", max_tones=1) == "D♭ (♭9)"
    assert _t("Gmaj7", max_tones=1) == "F♯ (7)"
    assert _t("Csus4", max_tones=1) == "F (4)"


def test_unusual_spellings_say_what_they_sound_like() -> None:
    by = {h.name: h.sounds for h in tone_hints("Cdim7") + tone_hints("E7#9") + tone_hints("Gb7(b9)") + tone_hints("Db13")}
    assert by["B𝄫"] == "A" and by["F𝄪"] == "G" and by["A𝄫"] == "G" and by["C♭"] == "B"
    assert by["G♭"] == ""  # ordinary spellings carry no note


def test_hints_follow_the_letter_in_every_key() -> None:
    """In all 15 spelled keys, every hint sits on the letter its interval names."""
    letters = "CDEFGAB"
    steps = {"2": 1, "♭3": 2, "3": 2, "4": 3, "♭5": 4, "♯5": 4, "6": 5, "𝄫7": 6, "♭7": 6, "7": 6,
             "♭9": 1, "9": 1, "♯9": 1, "11": 3, "♯11": 3, "♭13": 5, "13": 5}
    for root in ("C", "G", "D", "A", "E", "B", "F#", "C#", "F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"):
        for quality in ("7(b9)", "m9", "maj7#11", "dim7", "m7b5", "13", "7#9", "6/9", "7sus4", "aug"):
            for h in tone_hints(root + quality):
                want = letters[(letters.index(root[0]) + steps[h.label]) % 7]
                assert h.name[0] == want, (root + quality, h)


def test_hints_follow_transposition() -> None:
    """A transposed chart's symbols carry their own spelled hints (Key Cycling / Written)."""
    from music_theory import transpose_chord

    for sym, semis, key in (("C7(b9)", 2, "D"), ("Fm9", -3, "Ab"), ("Gmaj7", 5, "F"), ("A7(#11)", 1, "Bb"),
                            ("Bb13", 2, "C"), ("Ebm9", 3, "Gb")):
        moved = transpose_chord(sym, semis, reference_key=key)
        hs = tone_hints(moved)
        assert hs and all(h.name for h in hs), (moved, hs)
    assert _t(transpose_chord("C7(b9)", 2, reference_key="D")) == "C (♭7), E♭ (♭9)"   # D7(b9)
    assert _t(transpose_chord("Ebm9", 3, reference_key="Gb")) == "F♭ (♭7), A♭ (9)"   # Gbm9: Fb, not E


def test_shared_parser_fixes() -> None:
    from music_theory import spell_chord_tones
    from song_coach_harmony import chord_facts

    names = lambda sym: [t.name for t in chord_facts(sym).tones]  # noqa: E731
    assert names("A7(#11)") == ["A", "C#", "E", "G", "D#"]          # no stray B / D
    assert names("E7#9") == ["E", "G#", "B", "D", "F##"]            # no stray F#; #9 on its letter
    assert names("Cdim7") == ["C", "Eb", "Gb", "Bbb"]               # not A
    assert spell_chord_tones("A7(#11)") == ["A", "C#", "E", "G"]
    assert spell_chord_tones("E7#9") == ["E", "G#", "B", "D"]
    assert spell_chord_tones("Cb") == ["Cb", "Eb", "Gb"]            # Cb was spelled as C
    assert spell_chord_tones("Fbmaj7") == ["Fb", "Ab", "Cb", "Eb"]
    assert spell_chord_tones("C9") == ["C", "E", "G", "Bb", "D"]    # unaltered 9ths unchanged
    assert spell_chord_tones("G13") == ["G", "B", "D", "F", "A", "E"]
    assert spell_chord_tones("Cdim7") == ["C", "Eb", "Gb", "A"]     # the simplifying speller keeps its contract


def test_pretty_note() -> None:
    assert [pretty_note(n) for n in ("Bbb", "F##", "Eb", "C#", "G")] == ["B𝄫", "F𝄪", "E♭", "C♯", "G"]


CELL = "<div class='chord-cell live-chart-cell' data-section='A' data-bar='{bar}'><div class='bar-num'>Bar {bar}</div><div class='chord-symbol'>{sym}</div>{extra}</div>"


def _grid(*cells) -> str:
    return "<div class='lead-grid'>" + "".join(cells) + "</div>"


def test_apply_adds_one_line_per_cell_and_keeps_the_symbol_markup() -> None:
    from songs.backing_chart import chart_grid_html

    grid = chart_grid_html(["C7(b9)", "C7(b9)", "Fm9:2|Cdim7:2", "N.C.", "C", "Gm7.hit"], section_name="Verse")
    on = apply_chord_tone_hints(grid, True)
    # The chord-symbol divs (follow-along highlighting reads them) are untouched.
    assert re.findall(r"<div class='chord-symbol'>(.*?)</div>", on) == re.findall(
        r"<div class='chord-symbol'>(.*?)</div>", grid
    )
    rows = re.findall(r"<div class='chord-tone-hints[^']*'", on)
    assert len(rows) == grid.count("<div class='chord-symbol'>")   # every cell: same height
    assert "B♭ (♭7), D♭ (♭9)" in on and "F (♭7)" in on                 # hit bar: its chord's hints
    split = re.search(r"<div class='chord-tone-hints split'.*?</div>", on).group(0)
    assert "G (9)" in split and "B𝄫 (𝄫7)" in split and split.count("class='cth'") == 2
    assert "sounds A" in split
    # Idempotent; off restores the grid exactly.
    assert apply_chord_tone_hints(on, True) == on
    assert apply_chord_tone_hints(sheet_with_chord_tone_hints(grid), True) == on
    assert apply_chord_tone_hints(on, False) == grid
    assert apply_chord_tone_hints(grid, False) == grid


def test_lines_never_wrap() -> None:
    on = apply_chord_tone_hints(_grid(CELL.format(bar=1, sym="C13#11", extra="")), True)
    assert on.count("<style data-cth='page'>") == 1                    # one rule block per grid
    rule = re.search(r"\.chord-tone-hints\{([^}]*)\}", HINTS_STYLE).group(1)
    assert "white-space:nowrap" in rule and "text-overflow:ellipsis" in rule and "min-height" in rule


def test_lead_sheets_carry_hidden_lines_the_page_toggles() -> None:
    """Toggling never re-renders the sheet (that re-created its audio player and stopped the music)."""
    grid = _grid(CELL.format(bar=1, sym="C7(b9)", extra=""), CELL.format(bar=2, sym="Fm9", extra=""))
    sheet = sheet_with_chord_tone_hints(grid)
    assert "B♭ (♭7), D♭ (♭9)" in sheet and "E♭ (♭7), G (9)" in sheet
    # Hidden unless the sheet's document carries data-cth='1'; hidden lines take no space.
    assert "html:not([data-cth='1']) .chord-tone-hints{display:none !important;}" in sheet
    assert "window.parent.__cthOn" in sheet                              # a remounted sheet follows at load
    assert sheet_with_chord_tone_hints(sheet) == sheet                  # idempotent
    assert strip_chord_tone_hints(sheet) == grid
    assert sheet_with_chord_tone_hints(grid, available=False) == grid   # Karaoke: unchanged
    on, off = toggle_script_html(True), toggle_script_html(False)
    assert "const on=true" in on and "const on=false" in off
    assert "setAttribute('data-cth','1')" in on and "removeAttribute('data-cth')" in on
    assert "live-chart-root" in on and "setInterval(apply,500)" in on


def test_key_cycle_sheets_carry_their_own_keys_hints() -> None:
    from backing_key_cycle_handoff import build_cycle_lead_sheet_html

    song = {"title": "T", "key": "C", "sections": {"A": ["C7(b9)", "Fm9"]}}
    kw = dict(sounding_key="D", sections={"A": ["D7(b9)", "Gm9"]}, song_name="T", song_data=song)
    sheet = build_cycle_lead_sheet_html(session={}, **kw)
    assert "C (♭7), E♭ (♭9)" in sheet and "F (♭7), A (9)" in sheet      # D7(b9), Gm9
    assert "html:not([data-cth='1'])" in sheet                            # hidden until the page shows them


def test_preference_is_persisted_and_off_by_default() -> None:
    from music_persistent_state import _PERSIST_KEYS

    assert CHORD_TONE_HINTS_KEY in _PERSIST_KEYS
    assert hints_enabled({}) is False and hints_enabled(None) is False
    assert hints_enabled({CHORD_TONE_HINTS_KEY: True}) is True


def test_key_cycle_pending_blanking_hides_the_prior_keys_hints() -> None:
    import inspect

    import backing_key_cycle as kc

    src = inspect.getsource(kc)
    i = src.index("el.textContent = '…';")
    assert ".chord-tone-hints" in src[i:i + 400] and "visibility = 'hidden'" in src[i:i + 400]
