"""Melody projection (register), chord-label cleanup and note-level sync data."""

from __future__ import annotations

import unittest

from composition_melody_notation import build_section_score_model, chord_symbols_by_measure
from composition_melody_projection import (
    clef_for_instrument,
    melody_range_notice,
    project_melody_events,
    signed_semitone_delta,
    transpose_events,
)
from composition_playback_sync import build_composition_measure_sync_data
from practice_melody_sync import resolve_melody_measure_timing

_EVENTS = [
    {"pitch": "C5", "duration_beats": 1.0, "beat": 0.0},
    {"pitch": "rest", "duration_beats": 1.0, "beat": 1.0, "is_rest": True},
    {"pitch": "E5", "duration_beats": 2.0, "beat": 2.0},
    {"pitch": "G5", "duration_beats": 4.0, "beat": 4.0},
]


class TestKeyShiftKeepsRegister(unittest.TestCase):
    def test_practice_key_below_original_moves_down(self) -> None:
        self.assertEqual(signed_semitone_delta("E", "D"), -2)
        self.assertEqual(signed_semitone_delta("E", "Eb"), -1)

    def test_practice_key_above_original_moves_up(self) -> None:
        self.assertEqual(signed_semitone_delta("E", "F"), 1)
        self.assertEqual(signed_semitone_delta("E", "G"), 3)

    def test_same_key_is_zero_and_shift_is_at_most_a_tritone(self) -> None:
        self.assertEqual(signed_semitone_delta("E", "E"), 0)
        for orig in ("C", "E", "G#", "Bb", "Am"):
            for practice in ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"):
                self.assertTrue(-6 <= signed_semitone_delta(orig, practice) <= 6, (orig, practice))

    def test_projection_does_not_leap_an_octave_for_a_lower_key(self) -> None:
        out, key_shift, inst_shift = project_melody_events(
            _EVENTS, original_key="E", practice_key="D", instrument="Flute", session_state={}
        )
        self.assertEqual((key_shift, inst_shift), (-2, 0))
        self.assertEqual([e["pitch"] for e in out if e["pitch"] != "rest"], ["A#4", "D5", "F5"])


class TestWrittenPitchOnce(unittest.TestCase):
    def _pitches(self, instrument: str, transposing: str = "") -> list[str]:
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY as KEY

        ss = {KEY: transposing} if transposing else {}
        out, _, _ = project_melody_events(
            _EVENTS, original_key="E", practice_key="E", instrument=instrument, session_state=ss
        )
        return [e["pitch"] for e in out if e["pitch"] != "rest"]

    def test_concert_instruments_are_unchanged(self) -> None:
        for inst in ("Flute", "Piano", "Voice"):
            self.assertEqual(self._pitches(inst), ["C5", "E5", "G5"], inst)

    def test_bb_trumpet_is_a_major_second_higher(self) -> None:
        self.assertEqual(self._pitches("Trumpet"), ["D5", "F#5", "A5"])

    def test_eb_alto_is_a_major_sixth_higher(self) -> None:
        self.assertEqual(self._pitches("Saxophone", "Alto saxophone (Eb)"), ["A5", "C#6", "E6"])

    def test_bb_tenor_is_a_major_ninth_higher(self) -> None:
        self.assertEqual(self._pitches("Saxophone", "Tenor saxophone (Bb)"), ["D6", "F#6", "A6"])

    def test_rests_survive_and_input_is_not_mutated(self) -> None:
        original = [dict(e) for e in _EVENTS]
        out = transpose_events(_EVENTS, 5)
        self.assertEqual(_EVENTS, original)
        self.assertEqual(out[1]["pitch"], "rest")


class TestClefAndRange(unittest.TestCase):
    def test_clefs(self) -> None:
        self.assertEqual(clef_for_instrument("Bass"), "bass")
        self.assertEqual(clef_for_instrument("Guitar"), "treble-8")
        self.assertEqual(clef_for_instrument("Flute"), "treble")

    def test_clef_reaches_the_abc_key_line(self) -> None:
        model = build_section_score_model(
            events=_EVENTS, chords=["C", "F"], key="E", meter="4/4", bpm=90, clef="bass"
        )
        self.assertIn("clef=bass", model["abc"])

    def test_notice_reports_but_never_moves_pitches(self) -> None:
        out, _, _ = project_melody_events(
            _EVENTS, original_key="E", practice_key="E", instrument="Bass", session_state={}
        )
        self.assertIn("above the usual range", melody_range_notice(out, "Bass", {}))
        self.assertEqual([e["pitch"] for e in out if e["pitch"] != "rest"], ["C5", "E5", "G5"])

    def test_no_notice_inside_range(self) -> None:
        self.assertEqual(melody_range_notice(_EVENTS, "Flute", {}), "")


class TestChordLabelsAreMusicOnly(unittest.TestCase):
    def test_split_bar_encoding_never_reaches_the_score(self) -> None:
        events = [{"pitch": "E4", "duration_beats": 1.0} for _ in range(4)] + [
            {"pitch": "F4", "duration_beats": 0.5},
            {"pitch": "G4", "duration_beats": 3.5},
        ]
        model = build_section_score_model(
            events=events, chords=["C:3.5|Am:0.5p", "F"], key="C", meter="4/4", bpm=100
        )
        shown = " ".join(model["chord_labels"]) + model["abc"] + model["chord_strip_html"]
        for artifact in (":3.5", ":0.5", "0.5p", "|Am:"):
            self.assertNotIn(artifact, shown)
        self.assertIn("Am", shown)

    def test_labels_for_plain_chords_are_unchanged(self) -> None:
        self.assertEqual(chord_symbols_by_measure(["C", "Fm6/Ab", "G7"], measures=3), ["C", "Fm6/Ab", "G7"])

    def test_inner_chord_gets_its_own_onset(self) -> None:
        events = [{"pitch": "E4", "duration_beats": 0.5} for _ in range(8)]
        model = build_section_score_model(
            events=events, chords=["C:2|Am:2"], key="C", meter="4/4", bpm=100
        )
        self.assertIn('"C"', model["abc"])
        self.assertIn('"Am"', model["abc"])


class TestNoteLevelSyncData(unittest.TestCase):
    def test_offsets_describe_each_sounding_note(self) -> None:
        data = build_composition_measure_sync_data("Verse", _EVENTS, meter="4/4")
        self.assertEqual([d["bar_in_section"] for d in data], [1, 2])
        self.assertEqual(data[0]["note_offsets"], [[0.0, 0.25], [0.5, 0.5]])
        self.assertEqual(data[1]["note_offsets"], [[0.0, 1.0]])
        self.assertEqual(data[0]["note_end_index"] - data[0]["note_start_index"], 2)

    def test_offsets_ride_through_the_timeline_join(self) -> None:
        data = build_composition_measure_sync_data("Verse", _EVENTS, meter="4/4")
        timeline = [
            {"section": "Verse", "bar_in_section": 1, "absolute_bar": 0, "start_time": 0.0, "end_time": 2.0},
            {"section": "Verse", "bar_in_section": 2, "absolute_bar": 1, "start_time": 2.0, "end_time": 4.0},
            # a loop: bar 1 sounds again, later
            {"section": "Verse", "bar_in_section": 1, "absolute_bar": 2, "start_time": 4.0, "end_time": 6.0},
        ]
        windows = resolve_melody_measure_timing(data, timeline)
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[2]["notes"], [[0.0, 0.25], [0.5, 0.5]])
        self.assertEqual(windows[2]["start"], 4.0)

    def test_catalog_sync_rows_are_unchanged_without_offsets(self) -> None:
        entries = [{"section": "Verse", "bar_in_section": 1, "note_start_index": 0, "note_end_index": 2}]
        timeline = [{"section": "Verse", "bar_in_section": 1, "absolute_bar": 0, "start_time": 0.0, "end_time": 2.0}]
        self.assertNotIn("notes", resolve_melody_measure_timing(entries, timeline)[0])


class TestRenderAbcNoteHighlight(unittest.TestCase):
    def test_render_abc_ships_note_chord_and_lyric_highlighting(self) -> None:
        from pathlib import Path

        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        for needle in ("pm-current-note", "pm-current-chord", "pm-current-lyric", "highlightNote(match, t)", "abcjs-lyric"):
            self.assertIn(needle, src)


if __name__ == "__main__":
    unittest.main()
