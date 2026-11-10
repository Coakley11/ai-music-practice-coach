"""Chord Tone Hints by level: the notes under a chord name, spelled from the chord's structure.

Rules (agreed with the user): Beginner names every non-root chord tone, lowest first, names
only. Intermediate names up to three with degrees: alterations, 7th or 6th, 3rd, highest
extension. Advanced names up to four: alterations, extensions, 7th or 6th; the 3rd only on 7#9
and m(maj7). Plain triads get none above Beginner. A split bar has one tone per chord above
Beginner. Also pins the shared-parser fixes behind them (music_theory / chord_facts): 7(#11)
and 7#9 no longer gain a natural 9th / 11th, diminished tones keep their letters (Cdim7: Bbb),
and Cb / Fb / E# / B# roots spell.
"""
from __future__ import annotations

import re

import pytest

from chord_tone_hints import (
    CHORD_TONE_HINTS_KEY,
    HINTS_STYLE,
    apply_chord_tone_hints,
    hints_enabled,
    hints_level,
    hint_row_html,
    is_altered_dominant,
    normalize_level,
    pretty_note,
    sheet_with_chord_tone_hints,
    strip_chord_tone_hints,
    tone_hints,
)


def _t(symbol, **kw):
    return ", ".join(h.text() for h in tone_hints(symbol, **kw))


def _names(symbol, **kw):
    return " ".join(h.name for h in tone_hints(symbol, level="Beginner", **kw))


# The table the user approved on 2026-11-05: (symbol, Beginner, Intermediate, Advanced).
APPROVED = [
    ("A", "C♯ E", "", ""),
    ("Am", "C E", "", ""),
    ("A7", "C♯ E G", "C♯ (3), G (♭7)", "G (♭7)"),
    ("Am7", "C E G", "C (♭3), G (♭7)", "G (♭7)"),
    ("Amaj7", "C♯ E G♯", "C♯ (3), G♯ (7)", "G♯ (7)"),
    ("Am7b5", "C E♭ G", "C (♭3), E♭ (♭5), G (♭7)", "E♭ (♭5), G (♭7)"),
    ("Adim7", "C E♭ G♭", "C (♭3), E♭ (♭5), G♭ (𝄫7)", "E♭ (♭5), G♭ (𝄫7)"),
    ("Aaug", "C♯ E♯", "E♯ (♯5)", "E♯ (♯5)"),
    ("A9", "C♯ E G B", "C♯ (3), G (♭7), B (9)", "G (♭7), B (9)"),
    ("A13", "C♯ E G B F♯", "C♯ (3), G (♭7), F♯ (13)", "G (♭7), B (9), F♯ (13)"),
    ("A7b9", "C♯ E G B♭", "C♯ (3), G (♭7), B♭ (♭9)", "G (♭7), B♭ (♭9)"),
    ("A7#9", "C♯ E G B♯", "C♯ (3), G (♭7), B♯ (♯9)", "C♯ (3), G (♭7), B♯ (♯9)"),
    ("A7b9#11", "C♯ E G B♭ D♯", "G (♭7), B♭ (♭9), D♯ (♯11)", "G (♭7), B♭ (♭9), D♯ (♯11)"),
]


@pytest.mark.parametrize("symbol, beginner, intermediate, advanced", APPROVED)
def test_the_approved_table(symbol, beginner, intermediate, advanced) -> None:
    assert _names(symbol) == beginner
    assert _t(symbol, level="Intermediate") == intermediate
    assert _t(symbol, level="Advanced") == advanced


@pytest.mark.parametrize(
    "symbol, names",
    [
        ("A7", "C♯ E G"), ("C#7", "E♯ G♯ B"), ("Aaug", "C♯ E♯"),   # the chord's letters, not the key's
        ("Db7", "F A♭ C♭"), ("Abm7b5", "C♭ E𝄫 G♭"), ("F#m7", "A C♯ E"),
        ("Fm9", "A♭ C E♭ G"), ("Gmaj7", "B D F♯"),
    ],
)
def test_beginner_spells_from_the_chord_not_the_key(symbol, names) -> None:
    assert _names(symbol) == names


def test_beginner_invents_nothing_and_keeps_every_stated_tone() -> None:
    assert _names("A") == "C♯ E"                          # no 7th unless the symbol says so
    assert _names("A9") == "C♯ E G B"                     # the 9th when present
    assert _names("A6") == "C♯ E F♯"
    assert _names("A6/9") == "C♯ E F♯ B"
    assert _names("Aadd9") == "C♯ E B"
    assert _names("Asus4") == "D E"                        # no 3rd in a suspension
    assert _names("A7sus4") == "D E G"
    assert _names("A5") == "E"
    assert _names("Am11") == "C E G B D"
    assert _names("A13#11") == "C♯ E G B D♯ F♯"


@pytest.mark.parametrize(
    "symbol, names, intermediate, advanced",
    [
        ("A7b5", "C♯ E♭ G", "C♯ (3), E♭ (♭5), G (♭7)", "E♭ (♭5), G (♭7)"),
        ("A7#5", "C♯ E♯ G", "C♯ (3), E♯ (♯5), G (♭7)", "E♯ (♯5), G (♭7)"),
        ("Am7#5", "C E♯ G", "C (♭3), E♯ (♯5), G (♭7)", "E♯ (♯5), G (♭7)"),
        ("Amaj7#5", "C♯ E♯ G♯", "C♯ (3), E♯ (♯5), G♯ (7)", "E♯ (♯5), G♯ (7)"),
    ],
)
def test_an_altered_fifth_replaces_the_natural_fifth(symbol, names, intermediate, advanced) -> None:
    assert _names(symbol) == names
    assert _t(symbol, level="Intermediate") == intermediate
    assert _t(symbol, level="Advanced") == advanced


def test_an_eleventh_is_an_extension_even_when_the_reader_says_fourth() -> None:
    assert _names("A11") == "C♯ E G B D"
    assert _t("A11", level="Intermediate") == "C♯ (3), G (♭7), D (11)"
    assert _t("A11", level="Advanced") == "G (♭7), B (9), D (11)"
    assert _t("Am11", level="Intermediate") == "C (♭3), G (♭7), D (11)"
    assert _t("Am11", level="Advanced") == "G (♭7), B (9), D (11)"
    assert _t("Cadd11", level="Advanced") == "F (11)"


def test_a_suspension_stays_a_fourth_and_is_named_at_every_level() -> None:
    for level in ("Intermediate", "Advanced"):
        assert _t("Asus4", level=level) == "D (4)"
        assert _t("Asus2", level=level) == "B (2)"
        assert _t("A7sus4", level=level) == "D (4), G (♭7)"
        assert _t("A9sus4", level=level) == "D (4), G (♭7), B (9)"


def test_seven_alt_names_only_what_the_symbol_implies_plus_a_marker() -> None:
    assert is_altered_dominant("A7alt") and not is_altered_dominant("A7") and not is_altered_dominant("Am7")
    assert _names("A7alt") == "C♯ G"                       # no invented b9, #9, b13, nor a natural 5th
    assert _t("A7alt", level="Intermediate") == "C♯ (3), G (♭7)"
    assert _t("A7alt", level="Advanced") == "G (♭7)"
    assert tone_hints("A7alt", level="Intermediate", single=True) == ()   # a split bar: the marker alone
    assert ">alt</span>" in hint_row_html("A7alt", level="Beginner")
    assert ">alt</span>" in hint_row_html("A7alt", level="Intermediate")
    assert ">alt</span>" in hint_row_html("A7alt", level="Advanced")
    assert "alt" not in hint_row_html("A7", level="Advanced")


def test_order_and_limits() -> None:
    assert _t("A6", level="Intermediate") == "C♯ (3), F♯ (6)"
    assert _t("A6", level="Advanced") == "F♯ (6)"
    assert _t("A6/9", level="Intermediate") == "C♯ (3), F♯ (6), B (9)"
    assert _t("Am(maj7)", level="Intermediate") == _t("Am(maj7)", level="Advanced") == "C (♭3), G♯ (7)"
    assert _t("Cm(maj7)", level="Advanced") == _t("CmMaj7", level="Advanced") == "E♭ (♭3), B (7)"
    assert _t("Adim", level="Intermediate") == _t("Adim", level="Advanced") == "E♭ (♭5)"
    assert _t("Aadd9", level="Intermediate") == "B (9)"     # no 7th or 6th: no guide-tone 3rd
    assert _t("Adim(maj7)", level="Beginner") == "C (♭3), E♭ (♭5), G♯ (7)"   # a major 7th, not bb7
    # Highest extension at Intermediate; all of them, up to four, at Advanced.
    assert _t("Am13", level="Intermediate") == "C (♭3), G (♭7), F♯ (13)"
    assert _t("Am13", level="Advanced") == "G (♭7), B (9), D (11), F♯ (13)"
    assert _t("A13#11", level="Advanced") == "G (♭7), B (9), D♯ (♯11), F♯ (13)"
    # A 7#9 keeps its 3rd however many other alterations it has.
    assert "C♯ (3)" in _t("A7#9b13", level="Intermediate") and "C♯ (3)" in _t("A7#9b13", level="Advanced")
    for sym in ("C13#11", "C7(b9,#9,#11,b13)", "Cm13", "C9sus4", "Cdim7"):
        assert 1 <= len(tone_hints(sym, level="Intermediate")) <= 3
        assert 1 <= len(tone_hints(sym, level="Advanced")) <= 4


@pytest.mark.parametrize(
    "symbol, beginner, intermediate",
    [
        ("A/C#", "C♯ E", ""), ("D/F#", "F♯ A", ""),            # a chord tone in the bass, once
        ("A/D", "C♯ E", ""), ("C/D", "E G", ""),               # a bass outside the chord is not added
        ("Fm7/Bb", "A♭ C E♭", "A♭ (♭3), E♭ (♭7)"),
        ("G7/F", "B D F", "B (3), F (♭7)"),                     # the 7th in the bass is still the 7th
    ],
)
def test_slash_chords(symbol, beginner, intermediate) -> None:
    assert _names(symbol) == beginner
    assert _t(symbol, level="Intermediate") == intermediate


@pytest.mark.parametrize("symbol", ["C", "Cm", "F#", "Bbm", "C5", "C/E", "D/F#", "Bm.hit"])
def test_plain_triads_get_none_above_beginner(symbol) -> None:
    assert tone_hints(symbol, level="Intermediate") == ()
    assert tone_hints(symbol, level="Advanced") == ()
    assert tone_hints(symbol, level="Beginner")


@pytest.mark.parametrize("symbol", ["N.C.", "%", "", "…"])
@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
def test_non_chords_get_none(symbol, level) -> None:
    assert tone_hints(symbol, level=level) == ()


def test_a_split_bar_has_one_tone_above_beginner_and_the_full_list_at_beginner() -> None:
    for level in ("Intermediate", "Advanced"):
        for sym in ("C13#11", "C7(b9,#9,#11,b13)", "Cm11", "C9sus4"):
            assert len(tone_hints(sym, level=level, single=True)) == 1
        # The single tone is the most defining one.
        assert _t("Fm9", level=level, single=True) == "G (9)"
        assert _t("C7(b9)", level=level, single=True) == "D♭ (♭9)"
        assert _t("Gmaj7", level=level, single=True) == "F♯ (7)"
        assert _t("Csus4", level=level, single=True) == "F (4)"
        assert _t("Cdim7", level=level, single=True) == "B𝄫 (𝄫7)"
    assert _names("Fm9", single=True) == "A♭ C E♭ G"


def test_level_values() -> None:
    assert normalize_level("Beginner") == "Beginner" and normalize_level("advanced") == "Advanced"
    assert normalize_level("") == normalize_level(None) == normalize_level("Expert") == "Intermediate"
    assert hints_level({"level": "Advanced"}) == "Advanced"
    assert hints_level({}) == hints_level(None) == "Intermediate"


def test_unusual_spellings_say_what_they_sound_like() -> None:
    by = {h.name: h.sounds for h in tone_hints("Cdim7") + tone_hints("E7#9") + tone_hints("Gb7(b9)") + tone_hints("Db13")}
    assert by["B𝄫"] == "A" and by["F𝄪"] == "G" and by["A𝄫"] == "G" and by["C♭"] == "B"
    assert by["G♭"] == ""  # ordinary spellings carry no note
    assert "sounds F" in hint_row_html("C#7", level="Beginner")   # E♯, at Beginner too


@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
def test_hints_follow_the_letter_in_every_key(level) -> None:
    """In all 15 spelled keys, every hint sits on the letter its interval names."""
    letters = "CDEFGAB"
    steps = {"2": 1, "♭3": 2, "3": 2, "4": 3, "5": 4, "♭5": 4, "♯5": 4, "6": 5, "𝄫7": 6, "♭7": 6, "7": 6,
             "♭9": 1, "9": 1, "♯9": 1, "11": 3, "♯11": 3, "♭13": 5, "13": 5}
    for root in ("C", "G", "D", "A", "E", "B", "F#", "C#", "F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"):
        for quality in ("", "m", "7", "7(b9)", "m9", "m11", "maj7#11", "dim7", "m7b5", "13", "7#9", "6/9", "7sus4", "aug", "7#5"):
            for h in tone_hints(root + quality, level=level):
                want = letters[(letters.index(root[0]) + steps[h.label]) % 7]
                assert h.name[0] == want, (root + quality, h)


def test_beginner_lists_have_no_root_bass_or_repeats() -> None:
    for sym in ("A", "A7", "A13#11", "A11", "A7b5", "Am11", "Fm7/Bb", "C/D", "A/C#", "Cdim7", "Caug", "C6/9"):
        names = [h.name for h in tone_hints(sym, level="Beginner")]
        assert len(names) == len(set(names)), sym
        assert sym[0] not in [n[0] for n in names if n == sym[0]], sym
    assert "B♭" not in _names("Fm7/Bb") and "D" not in _names("C/D")


def test_hints_follow_transposition() -> None:
    """A transposed chart's symbols carry their own spelled hints (Key Cycling / Written)."""
    from music_theory import transpose_chord

    for sym, semis, key in (("C7(b9)", 2, "D"), ("Fm9", -3, "Ab"), ("Gmaj7", 5, "F"), ("A7(#11)", 1, "Bb"),
                            ("Bb13", 2, "C"), ("Ebm9", 3, "Gb")):
        moved = transpose_chord(sym, semis, reference_key=key)
        hs = tone_hints(moved)
        assert hs and all(h.name for h in hs), (moved, hs)
    assert _t(transpose_chord("C7(b9)", 2, reference_key="D")) == "F♯ (3), C (♭7), E♭ (♭9)"   # D7(b9)
    assert _names(transpose_chord("Ebm9", 3, reference_key="Gb")) == "B𝄫 D♭ F♭ A♭"           # Gbm9: Fb, not E


def test_a_capo_chart_names_the_sounding_chord() -> None:
    """The cell shows the shape; capo 2 turns a G shape into A, and the hints say so."""
    grid = "<div class='chord-symbol'>G7</div>"
    on = apply_chord_tone_hints(grid, True, level="Beginner", sounding_steps=2, reference_key="A")
    assert ">C♯<" in on and ">G<" in on and ">B<" not in on   # A7, not G7
    assert re.findall(r"<div class='chord-symbol'>(.*?)</div>", on) == ["G7"]   # the shape is still shown
    split = "<div class='chord-symbol'><span class='sub-chord' style='flex:1'>G7</span></div>"
    assert ">G (♭7)<" in hint_row_html(split, level="Advanced", sounding_steps=2, reference_key="A")
    assert hint_row_html("N.C.", sounding_steps=2) == "<div class='chord-tone-hints'>&nbsp;</div>"


def test_a_backing_sheet_with_shapes_keeps_hints_on_the_concert_cell() -> None:
    from songs.backing_chart import chart_grid_html

    grid = chart_grid_html(["A7"], section_name="Verse", shape_chords=["G7"])
    sheet = sheet_with_chord_tone_hints(grid, level="Beginner")
    assert "G7 shape" in sheet and ">C♯<" in sheet and ">B<" not in sheet


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
    assert "E (3), B♭ (♭7), D♭ (♭9)" in re.sub(r"<[^>]+>", "", on)
    assert "F (♭7)" in on                                            # hit bar: its chord's hints
    split = re.search(r"<div class='chord-tone-hints split'.*?</div>", on).group(0)
    assert "G (9)" in split and "B𝄫 (𝄫7)" in split and split.count("class='cth'") == 2
    assert "sounds A" in split
    # Idempotent; off restores the grid exactly.
    assert apply_chord_tone_hints(on, True) == on
    assert apply_chord_tone_hints(sheet_with_chord_tone_hints(grid), True) == on
    assert apply_chord_tone_hints(on, False) == grid
    assert apply_chord_tone_hints(grid, False) == grid


def test_lines_wrap_between_tones_so_nothing_is_hidden_on_a_phone() -> None:
    on = apply_chord_tone_hints(_grid(CELL.format(bar=1, sym="C13#11", extra="")), True, level="Beginner")
    assert on.count("<style data-cth='page'>") == 1                    # one rule block per grid
    rule = re.search(r"\.chord-tone-hints\{([^}]*)\}", HINTS_STYLE).group(1)
    assert "white-space:normal" in rule and "ellipsis" not in rule and "min-height" in rule
    assert ".chord-tone-hints .cth{white-space:nowrap;}" in HINTS_STYLE  # never inside "C♯ (3)"
    # Between the spans there is a space a line can break at.
    assert re.sub(r"<[^>]+>", "", hint_row_html("C13#11", level="Beginner")) == "E G B♭ D F♯ A"
    assert re.sub(r"<[^>]+>", "", hint_row_html("C9", level="Intermediate")) == "E (3), B♭ (♭7), D (9)"


def test_a_beginner_split_bar_wraps_too() -> None:
    from songs.backing_chart import chart_grid_html

    grid = chart_grid_html(["Fm9:2|Cdim7:2"], section_name="Verse")
    full = re.search(r"<div class='chord-tone-hints[^']*'.*?</div>", apply_chord_tone_hints(grid, True, level="Beginner")).group(0)
    assert "split full" in full and full.count("class='cth'") == 7   # A♭ C E♭ G + E♭ G♭ B𝄫
    assert ".chord-tone-hints.split.full>span{overflow:visible;white-space:normal;}" in HINTS_STYLE
    one = re.search(r"<div class='chord-tone-hints[^']*'.*?</div>", apply_chord_tone_hints(grid, True, level="Advanced")).group(0)
    assert "split full" not in one and one.count("class='cth'") == 2


def test_a_level_change_rebuilds_a_finished_chart() -> None:
    grid = _grid(CELL.format(bar=1, sym="A7", extra=""))
    beg = sheet_with_chord_tone_hints(grid, level="Beginner")
    adv = sheet_with_chord_tone_hints(beg, level="Advanced")
    assert ">C♯<" in beg and ">G<" in beg
    assert ">G (♭7)<" in adv and ">C♯<" not in adv
    assert adv == sheet_with_chord_tone_hints(grid, level="Advanced")   # no trace of the old level


def test_lead_sheets_carry_hidden_lines_the_page_toggles() -> None:
    """Toggling never re-renders the sheet (that re-created its audio player and stopped the music)."""
    grid = _grid(CELL.format(bar=1, sym="C7(b9)", extra=""), CELL.format(bar=2, sym="Fm9", extra=""))
    sheet = sheet_with_chord_tone_hints(grid)
    assert ">B♭ (♭7)<" in sheet and ">D♭ (♭9)<" in sheet and ">G (9)<" in sheet
    # Hidden unless the sheet's document carries data-cth='1'; hidden lines take no space.
    assert "html:not([data-cth='1']) .chord-tone-hints{display:none !important;}" in sheet
    assert "window.parent.__cthOn" in sheet                              # a remounted sheet follows at load
    assert sheet_with_chord_tone_hints(sheet) == sheet                  # idempotent
    assert strip_chord_tone_hints(sheet) == grid
    assert sheet_with_chord_tone_hints(grid, available=False) == grid   # Karaoke: unchanged
    # The channel keeps open sheets on the saved choice; a click not yet saved wins.
    import pathlib
    channel = (pathlib.Path(__file__).resolve().parents[1] / "chord_tone_hints_component" / "index.html").read_text(encoding="utf-8")
    assert 'setAttribute("data-cth", "1")' in channel and 'removeAttribute("data-cth")' in channel
    assert "live-chart-root" in channel and "setInterval(apply, 500)" in channel
    assert "P.__cthPending === saved" in channel and "P.__cthSave = function" in channel
    assert "streamlit:setComponentValue" in channel and 'setFrameHeight", { height: 0 }' in channel


def test_player_switch() -> None:
    from chord_tone_hints import player_switch_html

    html_ = player_switch_html()
    assert "role='switch'" in html_ and ">Chord Tone Hints<" in html_
    # Its look follows the sheet's attribute; a click flips it here, at once, and hands the
    # choice to the channel (one quiet re-run saves it; the player is not re-rendered).
    assert "html[data-cth='1'] .cth-track" in html_
    assert "root.setAttribute('data-cth','1')" in html_ and "root.removeAttribute('data-cth')" in html_
    assert "P.__cthSave(on)" in html_
    assert "history.replaceState" not in html_ and "aria-checked" in html_ and "focus-visible" in html_


def test_switch_choice_is_taken_once_per_click() -> None:
    from chord_tone_hints import CTH_CHANNEL_KEY, take_switch_choice

    session: dict = {}
    session[CTH_CHANNEL_KEY] = {"on": True, "nonce": 1, "session": "s1"}
    assert take_switch_choice(session) is True and session[CHORD_TONE_HINTS_KEY] is True
    assert take_switch_choice(session) is None                    # the same click, not again
    session[CHORD_TONE_HINTS_KEY] = False                          # e.g. the Practice checkbox
    assert take_switch_choice(session) is None                    # an old click never overrides it
    session[CTH_CHANNEL_KEY] = {"on": True, "nonce": 2, "session": "s1"}
    assert take_switch_choice(session) is True
    session[CTH_CHANNEL_KEY] = {"on": True, "nonce": 3, "session": "s1"}
    assert take_switch_choice(session) is None                    # already on: no save
    assert take_switch_choice({CTH_CHANNEL_KEY: None}) is None
    assert take_switch_choice({CTH_CHANNEL_KEY: {"on": True}}) is None


def test_key_cycle_sheets_carry_their_own_keys_hints() -> None:
    from backing_key_cycle_handoff import build_cycle_lead_sheet_html

    song = {"title": "T", "key": "C", "sections": {"A": ["C7(b9)", "Fm9"]}}
    kw = dict(sounding_key="D", sections={"A": ["D7(b9)", "Gm9"]}, song_name="T", song_data=song)
    sheet = build_cycle_lead_sheet_html(session={}, **kw)
    assert ">C (♭7)<" in sheet and ">E♭ (♭9)<" in sheet and ">A (9)<" in sheet      # D7(b9), Gm9
    assert "html:not([data-cth='1'])" in sheet                            # hidden until the page shows them
    beginner = build_cycle_lead_sheet_html(session={}, level="Beginner", **kw)
    assert ">F♯<" in beginner and ">B♭<" in beginner                       # D7(b9) has F♯, Gm9 has B♭


def test_a_level_change_refreshes_prepared_key_cycling_sheets() -> None:
    """Prepared sheets wait in the session; the one the player gets carries today's level."""
    from unittest import mock

    import backing_key_cycle as kc
    from backing_key_cycle_handoff import build_cycle_lead_sheet_html

    song = {"title": "T", "key": "C", "sections": {"A": ["C7"]}}
    sheet = build_cycle_lead_sheet_html(
        session={}, sounding_key="D", sections={"A": ["D7"]}, song_name="T", song_data=song, level="Beginner"
    )
    assert ">F♯<" in sheet and ">C (♭7)<" not in sheet
    session = {"level": "Advanced", kc.BACKING_KEY_CYCLE_PREPARED_KEY: {"D": {"chart_html": sheet}}}
    with mock.patch.object(kc, "_prepared_entry_current", return_value=True):
        now = kc.prepared_cycle_chart_html(session, "D")
        assert ">C (♭7)<" in now and ">F♯<" not in now
        session["level"] = "Beginner"
        assert kc.prepared_cycle_chart_html(session, "D") == sheet.strip()
        # A sheet with no hint lines (Karaoke) stays as it was.
        session[kc.BACKING_KEY_CYCLE_PREPARED_KEY]["D"]["chart_html"] = "<div class='chord-symbol'>D7</div>"
        assert kc.prepared_cycle_chart_html(session, "D") == "<div class='chord-symbol'>D7</div>"


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
