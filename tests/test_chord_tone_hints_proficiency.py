"""Chord Tone Hints by proficiency (user, 2026-11-10): Beginner learns the whole chord, Intermediate
the guide tones that define the harmony, Advanced the colours, alterations and voice leading.

Pins the user's own examples and the distinction among the three levels for ordinary triads,
seventh chords, suspensions, altered dominants and extended chords; the voice-leading mark on
real chart markup; and that Practice charts, Backing sheets, capo charts and written-pitch charts
all derive their hints from the chord they display.
"""
from __future__ import annotations

import re

import pytest

from chord_tone_hints import (
    apply_chord_tone_hints,
    sheet_with_chord_tone_hints,
    tone_hints,
    voice_leading,
)


def _t(symbol, level, **kw):
    return ", ".join(h.text() for h in tone_hints(symbol, level=level, **kw))


def _names(symbol, level="Beginner"):
    return " ".join(h.name for h in tone_hints(symbol, level=level))


def _text(html_):
    return re.sub(r"<[^>]+>", "", html_)


def _lines(chart_html):
    """The visible text of each hint line, in chart order."""
    import html as _html

    return [_html.unescape(_text(m)).replace("\xa0", "").strip()
            for m in re.findall(r"<div class='chord-tone-hints[^']*'[^>]*>(.*?)</div>", chart_html, re.S)]


# ------------------------------------------------------------ the user's examples, level by level

@pytest.mark.parametrize(
    "symbol, names",
    [("C", "E G"), ("Am", "C E"), ("A7", "C♯ E G"), ("Cmaj7", "E G B"), ("Dm7", "F A C"), ("G9", "B D F A")],
)
def test_beginner_examples(symbol, names) -> None:
    assert _names(symbol) == names


def test_beginner_is_not_cut_to_three_tones() -> None:
    assert _names("G9") == "B D F A"
    assert _names("A13") == "C♯ E G B F♯"
    assert _names("A7b9#11") == "C♯ E G B♭ D♯"


@pytest.mark.parametrize(
    "symbol, intermediate",
    [
        ("C", "E (3)"), ("Cm", "E♭ (♭3)"),
        ("A7", "C♯ (3), G (♭7)"), ("Cmaj7", "E (3), B (7)"), ("Dm7", "F (♭3), C (♭7)"),
        ("A7b9", "C♯ (3), G (♭7), B♭ (♭9)"),
        ("A7b9#11", "C♯ (3), G (♭7), B♭ (♭9)"),   # the altered 9th is the most characteristic alteration
        ("C7#5", "E (3), G♯ (♯5), B♭ (♭7)"),
    ],
)
def test_intermediate_examples(symbol, intermediate) -> None:
    assert _t(symbol, "Intermediate") == intermediate


def test_intermediate_keeps_the_third_and_seventh_and_stays_near_three() -> None:
    for sym in ("A7", "Am7", "Amaj7", "A9", "A13", "A7b9", "A7#9", "A7b5", "A7#5", "A7#11", "A7b13",
                "A7b9#11", "C7b9#5", "C7(b9,#9,#11,b13)", "Am7b5", "Adim7"):
        hs = tone_hints(sym, level="Intermediate")
        labels = {h.label for h in hs}
        assert 2 <= len(hs) <= 3, (sym, hs)
        assert labels & {"3", "♭3"} and labels & {"♭7", "7", "𝄫7"}, (sym, hs)


def test_without_a_seventh_intermediate_names_the_third_and_what_defines_the_chord() -> None:
    assert _t("Aaug", "Intermediate") == "C♯ (3), E♯ (♯5)"
    assert _t("Bdim", "Intermediate") == "D (♭3), F (♭5)"
    assert _t("Cadd9", "Intermediate") == "E (3), D (9)"
    assert _t("C6", "Intermediate") == "E (3), A (6)"


@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
def test_a_suspension_is_never_given_the_third_it_replaces(level) -> None:
    for sym, sus in (("Asus4", "D"), ("Asus2", "B"), ("A7sus4", "D")):
        names = [h.name for h in tone_hints(sym, level=level)]
        assert sus in names and "C♯" not in names and "C" not in names, (sym, level, names)
    assert _t("Asus4", "Intermediate") == "D (4)"


def test_advanced_examples() -> None:
    # Colours first: the alterations of A7(b9#11) with the 7th, not the Intermediate guide tones.
    assert _t("A7b9#11", "Advanced") == "G (♭7), B♭ (♭9), D♯ (♯11)"
    assert _t("A13", "Advanced") == "G (♭7), B (9), F♯ (13)"
    assert _t("A7b5", "Advanced") == "E♭ (♭5), G (♭7)"
    assert _t("C7b9#5", "Advanced") == "G♯ (♯5), B♭ (♭7), D♭ (♭9)"
    # The 3rd where the other notes would hide the quality.
    assert _t("A7#9", "Advanced") == "C♯ (3), G (♭7), B♯ (♯9)"
    assert _t("AmMaj7", "Advanced") == "C (♭3), G♯ (7)"


def test_the_levels_differ_on_every_kind_of_chord() -> None:
    for sym in ("C", "A7", "Asus4", "A7b9#11", "A13", "C7b9#5", "Cadd9"):
        b, i, a = (_t(sym, lv) for lv in ("Beginner", "Intermediate", "Advanced"))
        assert b != i or sym == "Asus4", (sym, b, i)     # Beginner: the whole chord
        if sym not in ("Asus4",):
            assert i != a, (sym, i, a)                    # Advanced is not Intermediate again


def test_no_alteration_or_extension_is_invented() -> None:
    for level in ("Beginner", "Intermediate", "Advanced"):
        for sym in ("A7", "Cmaj7", "Dm7", "C", "Am"):
            labels = {h.label for h in tone_hints(sym, level=level)}
            assert not labels & {"♭9", "♯9", "9", "♯11", "11", "♭13", "13", "♭5", "♯5"}, (sym, level, labels)
        # 7alt: the player chooses the altered tensions; none is listed as if the symbol required it.
        labels = {h.label for h in tone_hints("A7alt", level=level)}
        assert not labels & {"♭9", "♯9", "♭13", "5"}, (level, labels)


# ------------------------------------------------------------ spelling

@pytest.mark.parametrize(
    "symbol, beginner, intermediate",
    [
        ("A7", "C♯ E G", "C♯ (3), G (♭7)"),
        ("C7b9", "E G B♭ D♭", "E (3), B♭ (♭7), D♭ (♭9)"),
        ("F#7", "A♯ C♯ E", "A♯ (3), E (♭7)"),
        ("Bbmaj7", "D F A", "D (3), A (7)"),
        ("Gb7", "B♭ D♭ F♭", "B♭ (3), F♭ (♭7)"),
    ],
)
def test_spelling_follows_the_chord(symbol, beginner, intermediate) -> None:
    assert _names(symbol) == beginner
    assert _t(symbol, "Intermediate") == intermediate


# ------------------------------------------------------------ voice leading (Advanced)

@pytest.mark.parametrize(
    "here, there, frm, to, label",
    [
        ("Dm7", "G7", "C", "B", "3"),        # ii -> V
        ("G7", "Cmaj7", "F", "E", "3"),      # V -> I
        ("G7", "C", "F", "E", "3"),          # into a triad
        ("A7", "Dm7", "G", "F", "♭3"),
        ("A7", "D", "G", "F♯", "3"),         # spelled by the next chord
        ("Db7", "Gbmaj7", "C♭", "B♭", "3"),
        ("Cmaj7", "Fmaj7", "B", "A", "3"),   # a whole step down
        ("Bm7b5", "E7", "A", "G♯", "3"),
    ],
)
def test_the_seventh_steps_down_to_the_next_third(here, there, frm, to, label) -> None:
    vl = voice_leading(here, there)
    assert vl is not None and (vl.from_name, vl.to_name, vl.to_label) == (frm, to, label)


@pytest.mark.parametrize(
    "here, there",
    [("A7", "A7"), ("C", "G7"), ("Cmaj7", "Am7"), ("G7", "N.C."), ("G7", "%"), ("G7", ""), ("Dm7", "Gsus4")],
)
def test_no_voice_leading_without_a_step_down_to_a_third(here, there) -> None:
    assert voice_leading(here, there) is None


def test_voice_leading_on_a_real_chart_only_at_advanced() -> None:
    from songs.backing_chart import chart_grid_html

    grid = chart_grid_html(["Dm7", "G7", "Cmaj7", "Cmaj7"], section_name="A")   # the 4th bar is drawn "%"
    adv = _lines(apply_chord_tone_hints(grid, True, level="Advanced"))
    assert adv == ["C (♭7)↘B", "F (♭7)↘E", "B (7)", ""]   # the last chord has nowhere to go
    for level in ("Beginner", "Intermediate"):
        assert "↘" not in _text(apply_chord_tone_hints(grid, True, level=level))


def test_voice_leading_waits_for_the_chord_change() -> None:
    from songs.backing_chart import chart_grid_html

    # The chart draws the held bar as "%": the arrow sits on the written A7, the repeat has no line.
    grid = chart_grid_html(["A7", "A7", "D"], section_name="A")
    assert _lines(apply_chord_tone_hints(grid, True, level="Advanced")) == ["G (♭7)↘F♯", "", ""]
    # A sheet that writes the chord out each bar: only the bar before the change leads.
    cells = "".join(f"<div class='chord-symbol'>{c}</div>" for c in ("A7", "A7", "D"))
    assert _lines(apply_chord_tone_hints(cells, True, level="Advanced")) == ["G (♭7)", "G (♭7)↘F♯", ""]


def test_voice_leading_says_where_it_goes_on_hover_and_keeps_its_tone_whole() -> None:
    from songs.backing_chart import chart_grid_html

    on = apply_chord_tone_hints(chart_grid_html(["Dm7", "G7"], section_name="A"), True, level="Advanced")
    span = re.search(r"<span class='cth cth-vl'[^>]*>[^<]*</span>", on).group(0)
    assert "moves down to B, the 3rd of G7" in span and ">C (♭7)↘B<" in span
    assert ".chord-tone-hints .cth{white-space:nowrap;}" in on   # the arrow never wraps away from its tone


def test_a_split_bar_has_no_room_for_an_arrow() -> None:
    from songs.backing_chart import chart_grid_html

    on = apply_chord_tone_hints(chart_grid_html(["Dm7:2|G7:2", "Cmaj7"], section_name="A"), True, level="Advanced")
    lines = _lines(on)
    assert "cth-vl" not in on and "↘" not in lines[0]
    assert lines[1] == "B (7)"


def test_a_capo_chart_leads_into_the_sounding_next_chord() -> None:
    from songs.backing_chart import chart_grid_html

    # Capo 2: the cells show G7 -> C shapes; A7 -> D sounds.
    grid = chart_grid_html(["G7", "C"], section_name="A")
    on = apply_chord_tone_hints(grid, True, level="Advanced", sounding_steps=2, reference_key="D")
    assert _lines(on)[0] == "G (♭7)↘F♯"


# ------------------------------------------------------------ one rule everywhere

@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
def test_practice_charts_and_backing_sheets_show_the_same_hints(level) -> None:
    from songs.backing_chart import chart_grid_html

    grid = chart_grid_html(["Dm7", "G7", "Cmaj7", "A7b9#11", "Dm7:2|G7:2", "C"], section_name="A")
    practice = apply_chord_tone_hints(grid, True, level=level)      # Practice re-renders with this
    sheet = sheet_with_chord_tone_hints(grid, level=level)          # Backing / Key Cycling sheets
    assert _lines(practice) == _lines(sheet)


def test_a_written_pitch_chart_gets_written_pitch_hints() -> None:
    """An alto saxophone reads the chart a major 6th up; the hints follow the written chords."""
    from music_theory import transpose_chord
    from songs.backing_chart import chart_grid_html

    concert = ["Bbmaj7", "Cm7", "F7"]
    written = [transpose_chord(c, 9, reference_key="G") for c in concert]
    assert written == ["Gmaj7", "Am7", "D7"]
    lines = _lines(apply_chord_tone_hints(chart_grid_html(written, section_name="A"), True, level="Intermediate"))
    assert lines == ["B (3), F♯ (7)", "C (♭3), G (♭7)", "F♯ (3), C (♭7)"]
    assert "D (3)" not in " ".join(lines)   # never the concert Bbmaj7's 3rd under a written Gmaj7
