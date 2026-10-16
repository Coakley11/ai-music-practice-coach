"""The bass sounds the chord being shown.

Live first wrong step: the last hit of every two-hit bar was a chromatic
approach to the next chord, held for half the bar -- F# under Dm (heard as D
major), Eb under F -- so the rendered harmony disagreed with the displayed chord.
"""

from __future__ import annotations

from backing_audio import _bass_motion_pitch, chord_notes


def _pcs(chord: str) -> set[int]:
    return {n % 12 for n in chord_notes(chord)}


def test_two_hit_bars_stay_on_chord_tones() -> None:
    for style in ("Pop groove", "Ballad", "Rock groove"):
        for chord, nxt in (("Dm", "G"), ("F", "Dm"), ("C", "F"), ("Cm", "Ab")):
            for slot in range(2):
                pitch = _bass_motion_pitch(chord, nxt, style, slot, 2)
                assert pitch % 12 in _pcs(chord), (style, chord, slot, pitch)


def test_walking_line_keeps_its_approach_note() -> None:
    # Four hits a bar: the last one is a short beat and may approach the next chord.
    pitch = _bass_motion_pitch("Dm", "G", "Jazz swing", 3, 4)
    assert pitch % 12 in {(7 - 1) % 12, (7 + 1) % 12}
