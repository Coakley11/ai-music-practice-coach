"""Issue 85: Mission Practice on Backing follows the instrument selected now.

Owner report 2026-11-22 (Blackbird): a lick sent to Backing with Guitar, then Alto Saxophone selected; the
summary still said Guitar and the Guitar TAB stayed. Display only: the stored lick must not change.
"""
from __future__ import annotations

import copy
import re
from contextlib import nullcontext
from unittest import mock

import pytest

import improvisation_intelligence_ui as ui
from improvisation_missions import MISSION_PRACTICE_LICK_KEY
from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

ALTO, TENOR, SOPRANO = "Alto saxophone (Eb)", "Tenor saxophone (Bb)", "Soprano saxophone (Bb)"


class _St:
    def __init__(self):
        self.lines, self.code_blocks = [], []

    def markdown(self, text, **_k):
        self.lines.append(str(text))

    def caption(self, text, **_k):
        self.lines.append(str(text))

    def code(self, text, **_k):
        self.code_blocks.append(str(text))

    def columns(self, spec, **_k):
        return [nullcontext() for _ in spec]

    def button(self, *_a, **_k):
        return False


def _session(instrument: str, transposing: str = "", **extra) -> dict:
    """A C# chord-tone lick on A#m7b5 that was sent to Backing while Guitar was selected."""
    ss = {
        "studio_page": "backing", "instrument": instrument, "level": "Intermediate",
        "improv_mission_concert_key": "C#", "display_key": "C#", "concert_key": "C#",
        MISSION_PRACTICE_LICK_KEY: {
            "mission_title": "Improvise using only chord tones", "instrument": "Guitar", "bpm": 96,
            "level": "Intermediate", "key_center": "C#", "chord": "A#m7b5", "_concert_chord": "A#m7b5",
            "song_title": "Blackbird", "section_label": "Verse", "tab": "STORED GUITAR TAB",
            "motif": {"notes": ["A#", "C#", "E", "G#"], "midi": [70, 73, 76, 80], "rhythm": "q q q q",
                      "chord": "A#m7b5", "_concert_chord": "A#m7b5",
                      "_concert_notes": ["A#", "C#", "E", "G#"], "_projected_display_key": "C#"},
        },
    }
    if transposing:
        ss[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = transposing
        ss["show_chart_in_instrument_key"] = True
    ss.update(extra)
    return ss


def _draw(ss: dict):
    st = _St()
    sheets: list[str] = []
    with mock.patch("backing_session_route.mission_backing_ui_allowed", return_value=True), \
         mock.patch.object(ui, "_render_motif_sheet_music", lambda _st, abc, **_k: sheets.append(str(abc))):
        ui.render_mission_practice_lick_on_backing(st, ss, applied_bpm=96)
    text = "\n".join(st.lines)
    chord = re.search(r"<strong>Chord</strong> (.*?) ·", text)
    inst = re.search(r"<strong>Instrument</strong> (.*?) ·", text)
    return {"inst": inst and inst.group(1), "chord": chord and chord.group(1), "text": text,
            "tab": bool(st.code_blocks), "abc": sheets[0] if sheets else ""}


@pytest.mark.parametrize("instrument, transposing, tab", [
    ("Guitar", "", True), ("Saxophone", ALTO, False), ("Saxophone", TENOR, False),
    ("Saxophone", SOPRANO, False), ("Flute", "", False), ("Piano", "", False),
])
def test_summary_and_tab_follow_the_selected_instrument(instrument, transposing, tab):
    seen = _draw(_session(instrument, transposing))
    assert seen["inst"] == instrument
    assert seen["tab"] is tab
    assert ("Guitar TAB" in seen["text"]) is tab
    assert seen["abc"], "the sheet music is still drawn"


def test_switching_back_to_guitar_brings_the_tab_back_and_never_changes_the_stored_lick():
    ss = _session("Guitar")
    before = copy.deepcopy(ss[MISSION_PRACTICE_LICK_KEY])
    for instrument, tab in (("Guitar", True), ("Flute", False), ("Guitar", True)):
        ss["instrument"] = instrument
        assert _draw(ss)["tab"] is tab
    assert ss[MISSION_PRACTICE_LICK_KEY] == before


@pytest.mark.parametrize("transposing, chord_root, key", [
    (ALTO, "G", ("A#", "Bb")), (TENOR, "C", ("D#", "Eb")), (SOPRANO, "C", ("D#", "Eb")),
])
def test_saxophones_read_their_own_written_chord(transposing, chord_root, key):
    """Concert A#m7b5 is written Gm7b5 for an E-flat alto, Cm7b5 for a B-flat tenor or soprano."""
    seen = _draw(_session("Saxophone", transposing))
    assert re.match(rf"{chord_root}(m7b5|m7♭5|ø)", seen["chord"]), seen["chord"]


@pytest.mark.parametrize("instrument", ["Flute", "Guitar"])
def test_concert_instruments_keep_the_concert_chord(instrument):
    assert re.match(r"(A#|A♯|Bb|B♭)(m7b5|m7♭5|ø)", _draw(_session(instrument))["chord"])


def test_no_selected_instrument_falls_back_to_the_stored_one():
    ss = _session("Guitar")
    ss.pop("instrument")
    assert _draw(ss)["inst"] == "Guitar"
