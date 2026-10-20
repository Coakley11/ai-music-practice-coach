"""Chord-aware enharmonic spelling after span motif projection."""

from __future__ import annotations

import copy
import logging
import unittest

from effective_practice_context import musician_facing_chord
from guitar_capo import shape_chart_key_for_concert
from harmonic_span_analyzer import analyze_harmonic_spans
from improvisation_motif import (
    build_motif_abc,
    midi_from_guitar_position,
    motif_guitar_tab_placements,
    section_harmony_rows,
)
from instrument_transposition import written_key_for_type
from mission_span_backing import key_change_semitones
from music_theory import (
    pitch_class_from_spelled_note,
    semitone_distance,
    spell_chord_tones,
    spell_note_in_key,
)
from span_motif_engine import generate_span_motif, project_span_motif
from span_motif_explain import spell_from_root, _COLOR_SPELLING
from tests.abc_pitch_decoder import decode_abc_midis

logging.disable(logging.CRITICAL)


def _span(chords: list[str], key: str):
    rows = section_harmony_rows({"A": chords}, section_names=["A"])
    found = analyze_harmonic_spans(
        rows, key_center=key, length=len(chords), source_id="t", include_weak=True
    )
    return next(s for s in found if list(s.chords) == chords)


def _pc(name: str) -> int:
    return pitch_class_from_spelled_note(name) % 12


def _motif(
    notes: list[str],
    midis: list[int],
    chords: list[str],
    indexes: list[int],
    *,
    kinds: list[str] | None = None,
    details: list[str] | None = None,
    colors: list[dict] | None = None,
    first_notes: list[int] | None = None,
) -> dict:
    timeline = []
    for i, chord in enumerate(chords):
        timeline.append({
            "chord": chord,
            "start": str(i * 4),
            "end": str((i + 1) * 4),
            "first_note": (first_notes or [0])[i] if first_notes else 0,
            "last_note": len(notes) - 1,
        })
    motif = {
        "notes": list(notes),
        "midi": list(midis),
        "display": " – ".join(notes),
        "chord": " → ".join(chords),
        "span_chords": list(chords),
        "span_motif": True,
        "note_chord_index": list(indexes),
        "chord_timeline": timeline,
        "bar_chord_symbols": list(chords),
        "key_center": "Am",
    }
    if kinds is not None:
        motif["note_kinds"] = list(kinds)
    if details is not None:
        motif["note_details"] = list(details)
    if colors is not None:
        motif["advanced_colors"] = list(colors)
    return motif


def _project(motif: dict, shift: int, chart: str, mapping: dict[str, str]) -> dict:
    return project_span_motif(
        motif,
        semitones=shift,
        chart_key=chart,
        project_chord=lambda chord: mapping.get(chord, chord),
    )


class TestPracticeKeySpelling(unittest.TestCase):
    def test_projected_d7_third_matches_direct_generation(self) -> None:
        shift = key_change_semitones("Am", "Gm")
        self.assertEqual(shift, -2)
        source = _motif(
            ["B", "G#", "A"],
            [71, 68, 69],
            ["Bm7b5", "E7", "Am"],
            [0, 1, 2],
            kinds=["target", "chord_tone", "target"],
            first_notes=[0, 1, 2],
        )
        original = copy.deepcopy(source)
        shown = _project(source, shift, "Gm", {"Bm7b5": "Am7b5", "E7": "D7", "Am": "Gm"})
        self.assertEqual(shown["notes"][1], "F#")
        self.assertNotEqual(shown["notes"][1], "Gb")
        self.assertEqual(shown["notes"][1], spell_chord_tones("D7")[1])
        self.assertEqual(shown["midi"][1], 66)
        self.assertEqual(shown["midi"][1] % 12, _pc("F#"))
        self.assertEqual(spell_note_in_key(6, "Gm"), "Gb")
        self.assertEqual([m - s for s, m in zip(source["midi"], shown["midi"])], [shift] * 3)
        self.assertEqual([t["chord"] for t in shown["chord_timeline"]], ["Bm7b5", "E7", "Am"])
        self.assertEqual(source, original)

        direct = _span(["Am7b5", "D7", "Gm"], "Gm")
        projected = _span(["Bm7b5", "E7", "Am"], "Am")
        mapping = dict(zip(projected.chords, direct.chords))
        direct_thirds = set()
        projected_thirds = set()
        for seed in range(8):
            made = generate_span_motif(direct, level="Intermediate", seed=seed, style="jazz", vocabulary="chord_tones")
            for name, midi, ci in zip(made["notes"], made["midi"], made["note_chord_index"]):
                if made["chord_timeline"][ci]["chord"] == "D7" and int(midi) % 12 == 6:
                    direct_thirds.add(name)
            moved = generate_span_motif(
                projected, level="Intermediate", seed=seed, style="jazz", vocabulary="chord_tones"
            )
            out = _project(moved, shift, "Gm", mapping)
            self.assertEqual([m - s for s, m in zip(moved["midi"], out["midi"])], [shift] * len(out["midi"]))
            for i, (name, midi, ci) in enumerate(zip(out["notes"], out["midi"], out["note_chord_index"])):
                self.assertEqual(_pc(name), int(midi) % 12, name)
                if moved["chord_timeline"][ci]["chord"] == "E7" and int(moved["midi"][i]) % 12 == 8:
                    projected_thirds.add(name)
        self.assertEqual(direct_thirds, {"F#"})
        self.assertEqual(projected_thirds, {"F#"})

    def test_secondary_dominant_and_other_chord_tones(self) -> None:
        a7 = _project(
            _motif(["D#"], [63], ["B7"], [0], kinds=["chord_tone"]),
            key_change_semitones("Am", "Gm"),
            "Gm",
            {"B7": "A7"},
        )
        self.assertEqual(a7["notes"], ["C#"])
        self.assertEqual(a7["notes"][0], spell_chord_tones("A7")[1])
        self.assertNotEqual(a7["notes"][0], spell_note_in_key(a7["midi"][0] % 12, "Gm"))

        e7 = _project(
            _motif(["A"], [69], ["F7"], [0], kinds=["chord_tone"]),
            -1,
            "Bb",
            {"F7": "E7"},
        )
        self.assertEqual(e7["notes"], ["G#"])
        self.assertEqual(e7["notes"][0], spell_chord_tones("E7")[1])
        self.assertEqual(spell_note_in_key(e7["midi"][0] % 12, "Bb"), "Ab")

        f7 = _project(
            _motif(["D"], [62], ["E7"], [0], kinds=["chord_tone"]),
            1,
            "Em",
            {"E7": "F7"},
        )
        self.assertEqual(f7["notes"], ["Eb"])
        self.assertEqual(f7["notes"][0], spell_chord_tones("F7")[3])
        self.assertEqual(spell_note_in_key(f7["midi"][0] % 12, "Em"), "D#")
        self.assertEqual(f7["midi"], [63])

        bb7 = _project(
            _motif(["C#"], [61], ["A7"], [0], kinds=["chord_tone"]),
            1,
            "F",
            {"A7": "Bb7"},
        )
        self.assertEqual(bb7["notes"], ["D"])
        self.assertEqual(bb7["notes"][0], spell_chord_tones("Bb7")[1])

    def test_chromatic_approach_and_enclosure_stay_sharp_below(self) -> None:
        approach = _project(
            _motif(
                ["D#", "E"],
                [63, 64],
                ["E7"],
                [0, 0],
                kinds=["connector", "target"],
                first_notes=[1],
            ),
            -2,
            "Gm",
            {"E7": "D7"},
        )
        self.assertEqual(approach["notes"], ["C#", "D"])
        self.assertEqual(approach["midi"], [61, 62])
        self.assertNotEqual(approach["notes"][0], "Db")

        enclosure = _project(
            _motif(
                ["D#", "F", "E"],
                [63, 65, 64],
                ["E7"],
                [0, 0, 0],
                kinds=["connector", "connector", "target"],
                details=["enclosure", "enclosure", "target"],
                first_notes=[2],
            ),
            -2,
            "Gm",
            {"E7": "D7"},
        )
        self.assertEqual(enclosure["notes"][0], "C#")
        self.assertEqual(enclosure["midi"], [61, 63, 62])
        self.assertEqual(_pc(enclosure["notes"][1]), 3)

    def test_altered_and_lydian_colour_use_chord_spelling(self) -> None:
        lydian = _project(
            _motif(
                ["A#"],
                [70],
                ["E7"],
                [0],
                kinds=["tension"],
                colors=[{"chord_index": 0, "chord": "E7", "color": "lydian_dominant"}],
            ),
            -2,
            "Gm",
            {"E7": "D7"},
        )
        expected = spell_from_root("D", _COLOR_SPELLING["lydian_dominant"])
        self.assertIn("G#", expected)
        self.assertEqual(lydian["notes"], ["G#"])
        self.assertEqual(spell_note_in_key(lydian["midi"][0] % 12, "Gm"), "Ab")

        altered = _project(
            _motif(
                ["A#"],
                [70],
                ["E7"],
                [0],
                kinds=["tension"],
                colors=[{"chord_index": 0, "chord": "E7", "color": "altered"}],
            ),
            -2,
            "Em",
            {"E7": "D7"},
        )
        self.assertIn("Ab", spell_from_root("D", _COLOR_SPELLING["altered"]))
        self.assertEqual(altered["notes"], ["Ab"])
        self.assertEqual(spell_note_in_key(altered["midi"][0] % 12, "Em"), "G#")
        self.assertEqual(altered["midi"], [68])

    def test_two_chord_three_chord_and_repeated_symbols(self) -> None:
        two = _span(["Bm7b5", "E7"], "Am")
        three = _span(["Bm7b5", "E7", "Am"], "Am")
        self.assertEqual(len(two.chords), 2)
        self.assertEqual(len(three.chords), 3)
        shift = key_change_semitones("Am", "Gm")
        for span, mapping in (
            (two, {"Bm7b5": "Am7b5", "E7": "D7"}),
            (three, {"Bm7b5": "Am7b5", "E7": "D7", "Am": "Gm"}),
        ):
            motif = generate_span_motif(span, level="Intermediate", seed=3, style="jazz")
            shown = _project(motif, shift, "Gm", mapping)
            self.assertEqual(shown["midi"], [m + shift for m in motif["midi"]])
            self.assertEqual(len(shown["notes"]), len(shown["midi"]))
            for name, midi in zip(shown["notes"], shown["midi"]):
                self.assertEqual(_pc(name), int(midi) % 12)

        repeated = _project(
            _motif(
                ["G#", "B", "G#"],
                [68, 71, 80],
                ["E7", "E7"],
                [0, 0, 1],
                kinds=["chord_tone", "chord_tone", "chord_tone"],
                first_notes=[0, 2],
            ),
            shift,
            "Gm",
            {"E7": "D7"},
        )
        self.assertEqual(repeated["notes"], ["F#", "A", "F#"])
        self.assertEqual([t["chord"] for t in repeated["chord_timeline"]], ["E7", "E7"])
        self.assertEqual(repeated["note_chord_index"], [0, 0, 1])


class TestInstrumentProjection(unittest.TestCase):
    def test_piano_and_guitar_keep_pitches_and_capo_spelling(self) -> None:
        span = _span(["Bm7b5", "E7", "Am"], "Am")
        motif = generate_span_motif(span, level="Intermediate", seed=4, style="jazz")
        shift = key_change_semitones("Am", "Gm")
        piano = _project(motif, shift, "Gm", {"Bm7b5": "Am7b5", "E7": "D7", "Am": "Gm"})
        self.assertEqual(piano["midi"], [m + shift for m in motif["midi"]])
        self.assertEqual(decode_abc_midis(build_motif_abc(piano, key_center="Gm", bpm=100)), piano["midi"])
        frets = motif_guitar_tab_placements(piano)
        self.assertEqual([midi_from_guitar_position(s, f) for s, f in frets], piano["midi"])

        concert = _motif(["F#"], [66], ["D7"], [0], kinds=["chord_tone"])
        shape = shape_chart_key_for_concert("Gm", "D")
        dist = semitone_distance("Gm", shape)
        capo = project_span_motif(
            concert,
            semitones=dist,
            chart_key=shape,
            project_chord=lambda chord: musician_facing_chord(chord, concert_key="Gm", chart_key=shape),
        )
        written = musician_facing_chord("D7", concert_key="Gm", chart_key=shape)
        self.assertEqual(capo["notes"][0], spell_chord_tones(written)[1])
        self.assertEqual(capo["notes"][0], "C#")
        self.assertEqual(spell_note_in_key(capo["midi"][0] % 12, shape), "Db")
        self.assertEqual(capo["midi"], [66 + dist])
        self.assertEqual(
            [midi_from_guitar_position(s, f) for s, f in motif_guitar_tab_placements(capo)],
            capo["midi"],
        )

    def test_transposing_instruments_keep_interval_and_chord_spelling(self) -> None:
        cases = (
            ("Alto saxophone (Eb)", "Ab7", 3),
            ("Tenor saxophone (Bb)", "Eb7", 3),
            ("Bb Clarinet", "Eb7", 3),
        )
        for instrument, source_chord, degree in cases:
            written_key = written_key_for_type("Gm", instrument)
            dist = semitone_distance("Gm", written_key)
            source_tone = spell_chord_tones(source_chord)[degree]
            midi = 60 + _pc(source_tone)
            shown = project_span_motif(
                _motif([source_tone], [midi], [source_chord], [0], kinds=["chord_tone"]),
                semitones=dist,
                chart_key=written_key,
                project_chord=lambda chord, key=written_key: musician_facing_chord(
                    chord, concert_key="Gm", chart_key=key
                ),
            )
            written_chord = musician_facing_chord(source_chord, concert_key="Gm", chart_key=written_key)
            functional = spell_chord_tones(written_chord)[degree]
            self.assertEqual(shown["midi"], [midi + dist])
            self.assertEqual(shown["notes"], [functional])
            self.assertEqual(functional, "Eb")
            self.assertEqual(spell_note_in_key(shown["midi"][0] % 12, written_key), "D#")
            self.assertEqual(
                decode_abc_midis(build_motif_abc(shown, key_center=written_key, bpm=100)),
                shown["midi"],
            )

        for instrument in ("Alto saxophone (Eb)", "Tenor saxophone (Bb)", "Bb Clarinet"):
            written_key = written_key_for_type("Gm", instrument)
            dist = semitone_distance("Gm", written_key)
            shown = project_span_motif(
                _motif(["F#"], [66], ["D7"], [0], kinds=["chord_tone"]),
                semitones=dist,
                chart_key=written_key,
                project_chord=lambda chord, key=written_key: musician_facing_chord(
                    chord, concert_key="Gm", chart_key=key
                ),
            )
            written_chord = musician_facing_chord("D7", concert_key="Gm", chart_key=written_key)
            self.assertEqual(shown["notes"][0], spell_chord_tones(written_chord)[1])
            self.assertEqual(shown["midi"], [66 + dist])
            self.assertEqual(_pc(shown["notes"][0]), shown["midi"][0] % 12)

    def test_zero_shift_does_not_respell(self) -> None:
        motif = _motif(["F#"], [66], ["D7"], [0])
        shown = project_span_motif(motif, semitones=0, chart_key="Gm", project_chord=lambda chord: chord)
        self.assertEqual(shown["notes"], ["F#"])
        self.assertEqual(shown["midi"], [66])
        self.assertIs(project_span_motif(motif, semitones=0, chart_key="Gm"), motif)


if __name__ == "__main__":
    unittest.main()
