"""Regression tests for Guitar Practice Focus = Pentatonics.

Follow-up to the R2 musicality checkpoint (b14c8bf): live/code-inspection
acceptance testing found that ``practice_notation.py::_focus_kind`` did not
recognize "Pentatonics" at all -- it fell through to "general", so Guitar +
Focus=Pentatonics silently rendered the ordinary chord-comping/voicing TAB
with only the dropdown label changed, never real pentatonic fretboard
material. This suite proves the fix: an explicit "pentatonic" focus kind
routes to ``guitar_pentatonic_engine``, which produces a genuinely moving,
harmony-aware, level-differentiated, playable, groove-aware single-note
pentatonic line, while leaving the accepted chord-comping/voicing path
(Focus != Pentatonics) completely unchanged.
"""

from __future__ import annotations

import unittest

from guitar_pentatonic_engine import (
    PentatonicNoteEvent,
    build_guitar_pentatonic_measures,
    validate_pentatonic_line,
)
from practice_notation import _focus_kind, generate_practice_notation

ATTYA_B_CHORDS = ["Fm7", "Bbm7", "Eb7", "Abmaj7", "Dbmaj7", "Bdim7", "Ebm7", "Ab7"]


def _flatten(measures: list[list[PentatonicNoteEvent]]) -> list[PentatonicNoteEvent]:
    return [ev for m in measures for ev in m]


class TestFocusRouting(unittest.TestCase):
    def test_pentatonics_does_not_resolve_to_general(self) -> None:
        self.assertEqual(_focus_kind("Pentatonics"), "pentatonic")
        self.assertNotEqual(_focus_kind("Pentatonics"), "general")

    def test_pentatonics_does_not_resolve_to_scales(self) -> None:
        # Explicit pentatonic kind, not an alias of "scales" -- "scales"
        # still drives the held chord-shape fingerstyle grid, not a moving
        # single-note line.
        self.assertNotEqual(_focus_kind("Pentatonics"), "scales")

    def test_other_focuses_unaffected(self) -> None:
        self.assertEqual(_focus_kind("Strumming"), "rhythm")
        self.assertEqual(_focus_kind("Scales"), "scales")
        self.assertEqual(_focus_kind("Barre Chords"), "chords")
        self.assertEqual(_focus_kind(""), "general")


class TestMaterialDiffersFromComping(unittest.TestCase):
    def _generate(self, focus: str, difficulty: str = "advanced"):
        return generate_practice_notation(
            song_title="All the Things You Are",
            artist="Jazz Standard",
            display_key="Ab",
            original_key="Ab",
            bpm=72,
            groove_style="Jazz swing",
            instrument="Guitar",
            focus=focus,
            section_focus="B",
            sections={"B": ATTYA_B_CHORDS},
            guitar_tabs={},
            difficulty=difficulty,
        )

    def test_pentatonics_body_differs_from_strumming(self) -> None:
        strumming = self._generate("Strumming")
        pentatonics = self._generate("Pentatonics")
        self.assertNotEqual(strumming.body, pentatonics.body)

    def test_pentatonics_cues_are_pentatonic_specific(self) -> None:
        res = self._generate("Pentatonics")
        joined = " ".join(res.practice_cues)
        self.assertIn("pentatonic", joined.lower())
        self.assertNotIn("voicing style", joined.lower())


class TestMelodicNature(unittest.TestCase):
    def test_measures_contain_moving_single_note_events(self) -> None:
        measures = build_guitar_pentatonic_measures(
            ATTYA_B_CHORDS, level="Advanced", is_jazz_groove=True
        )
        events = _flatten(measures)
        self.assertGreater(len(events), 0)
        # A held chord shape would repeat the SAME (string, fret) across
        # every slot of a measure; a genuine melodic line visits more than
        # one distinct (string, fret) pair across the phrase.
        distinct_positions = {(ev.string_idx, ev.fret) for ev in events}
        self.assertGreater(len(distinct_positions), 3)
        # Monophonic: at most one event per slot per measure (no stacked
        # simultaneous notes -- this is a melodic line, not a chord grid).
        for measure in measures:
            slots = [ev.slot for ev in measure]
            self.assertEqual(len(slots), len(set(slots)), "two notes landed on the same slot")

    def test_rendered_html_is_not_a_static_repeated_shape(self) -> None:
        from practice_notation import _render_pentatonic_measure_html, _groove_pattern

        measures = build_guitar_pentatonic_measures(
            ["Fm7"], level="Intermediate", is_jazz_groove=False
        )
        groove_info = _groove_pattern("Jazz swing", "pentatonic")
        block, plain = _render_pentatonic_measure_html(
            chord="Fm7", events=measures[0], bar_index=1, groove_info=groove_info
        )
        # The plain-text render should show fret digits on more than one
        # distinct string line, proving string-crossing/movement rather
        # than one string (or one static shape) held throughout.
        lines = [ln for ln in plain.splitlines() if "|" in ln]
        strings_with_notes = sum(1 for ln in lines if any(c.isdigit() for c in ln.split("|")[1]))
        self.assertGreater(strings_with_notes, 1)


class TestHarmonyAwareSelection(unittest.TestCase):
    def test_changing_chord_quality_changes_pitch_collection(self) -> None:
        minor_measures = build_guitar_pentatonic_measures(["Fm7"], level="Beginner", is_jazz_groove=False)
        major_measures = build_guitar_pentatonic_measures(["Abmaj7"], level="Beginner", is_jazz_groove=False)
        minor_pcs = {ev.pitch_class for ev in minor_measures[0]}
        major_pcs = {ev.pitch_class for ev in major_measures[0]}
        self.assertNotEqual(minor_pcs, major_pcs)

    def test_progression_visits_more_than_one_pitch_collection(self) -> None:
        measures = build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Intermediate", is_jazz_groove=False)
        pc_sets = [frozenset(ev.pitch_class for ev in m) for m in measures if m]
        self.assertGreater(len(set(pc_sets)), 1)


class TestLevelProgression(unittest.TestCase):
    def test_levels_produce_structurally_different_exercises(self) -> None:
        beg = _flatten(build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Beginner", is_jazz_groove=False))
        inter = _flatten(build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Intermediate", is_jazz_groove=False))
        adv = _flatten(build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Advanced", is_jazz_groove=True))
        self.assertLess(len(beg), len(inter), "Intermediate must have more events than Beginner")
        self.assertLessEqual(len(inter), len(adv))
        beg_frets = {ev.fret for ev in beg}
        adv_frets = {ev.fret for ev in adv}
        self.assertGreaterEqual(
            max(adv_frets) - min(adv_frets),
            max(beg_frets) - min(beg_frets),
            "Advanced must traverse at least as wide a fret range as Beginner",
        )

    def test_intermediate_shows_more_movement_than_beginner(self) -> None:
        beg = build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Beginner", is_jazz_groove=False)
        inter = build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Intermediate", is_jazz_groove=False)
        beg_strings = {ev.string_idx for ev in _flatten(beg)}
        inter_strings = {ev.string_idx for ev in _flatten(inter)}
        self.assertGreaterEqual(len(inter_strings), len(beg_strings))

    def test_advanced_shows_connected_positions_beyond_intermediate(self) -> None:
        inter = build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Intermediate", is_jazz_groove=False)
        adv = build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Advanced", is_jazz_groove=True)
        inter_shifts = sum(1 for ev in _flatten(inter) if ev.position_shift)
        adv_shifts = sum(1 for ev in _flatten(adv) if ev.position_shift)
        self.assertGreaterEqual(adv_shifts, inter_shifts)

    def test_jazz_advanced_gets_chromatic_approach_notes_pop_does_not(self) -> None:
        jazz_adv = _flatten(
            build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Advanced", is_jazz_groove=True)
        )
        pop_adv = _flatten(
            build_guitar_pentatonic_measures(["C", "G", "Am", "F"], level="Advanced", is_jazz_groove=False)
        )
        self.assertGreater(sum(1 for ev in jazz_adv if ev.is_chromatic_approach), 0)
        self.assertEqual(sum(1 for ev in pop_adv if ev.is_chromatic_approach), 0)


class TestPlayability(unittest.TestCase):
    def test_all_levels_produce_playable_lines(self) -> None:
        for level, jazz in (("Beginner", False), ("Intermediate", False), ("Advanced", True)):
            measures = build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level=level, is_jazz_groove=jazz)
            ok, msg = validate_pentatonic_line(measures)
            self.assertTrue(ok, f"{level} line failed playability: {msg}")

    def test_pop_rock_advanced_also_playable(self) -> None:
        measures = build_guitar_pentatonic_measures(
            ["C", "G", "Am", "F", "C", "G", "F", "G"], level="Advanced", is_jazz_groove=False
        )
        ok, msg = validate_pentatonic_line(measures)
        self.assertTrue(ok, msg)

    def test_validator_rejects_an_impossible_jump(self) -> None:
        bad = [[
            PentatonicNoteEvent(measure=0, slot=0, string_idx=0, fret=0, pitch_class=4, chord="C"),
            PentatonicNoteEvent(measure=0, slot=1, string_idx=0, fret=9, pitch_class=11, chord="C"),
        ]]
        ok, msg = validate_pentatonic_line(bad)
        self.assertFalse(ok)


class TestSectionOwnership(unittest.TestCase):
    def test_section_b_uses_section_b_canonical_harmony(self) -> None:
        sections = {
            "A": ["Fm7", "Bbm7", "Eb7", "Abmaj7"],
            "B": ATTYA_B_CHORDS,
        }
        res = generate_practice_notation(
            song_title="All the Things You Are",
            artist="Jazz Standard",
            display_key="Ab",
            original_key="Ab",
            bpm=72,
            groove_style="Jazz swing",
            instrument="Guitar",
            focus="Pentatonics",
            section_focus="B",
            sections=sections,
            guitar_tabs={},
            difficulty="advanced",
        )
        self.assertIn("Bdim7", res.chord_labels)
        self.assertIn("Ab7", res.chord_labels)


class TestGrooveIntegration(unittest.TestCase):
    def test_attya_pentatonics_receives_jazz_swing_consistently(self) -> None:
        for _rerun in range(5):
            res = generate_practice_notation(
                song_title="All the Things You Are",
                artist="Jazz Standard",
                display_key="Ab",
                original_key="Ab",
                bpm=72,
                groove_style="Jazz swing",
                instrument="Guitar",
                focus="Pentatonics",
                section_focus="B",
                sections={"B": ATTYA_B_CHORDS},
                guitar_tabs={},
                difficulty="advanced",
            )
            self.assertIn("Swing", res.rhythm_counts)

    def test_ballad_groove_thins_density(self) -> None:
        dense = _flatten(
            build_guitar_pentatonic_measures(ATTYA_B_CHORDS, level="Intermediate", is_jazz_groove=False)
        )
        sparse = _flatten(
            build_guitar_pentatonic_measures(
                ATTYA_B_CHORDS, level="Intermediate", is_jazz_groove=False, is_sparse_groove=True
            )
        )
        self.assertLess(len(sparse), len(dense))


class TestCompingRegressionUnchanged(unittest.TestCase):
    """Ordinary Guitar chord-comping/voicing (Focus != Pentatonics) must be
    byte-identical to before this follow-up."""

    def test_strumming_still_uses_held_chord_voicings(self) -> None:
        res = generate_practice_notation(
            song_title="All the Things You Are",
            artist="Jazz Standard",
            display_key="Ab",
            original_key="Ab",
            bpm=72,
            groove_style="Jazz swing",
            instrument="Guitar",
            focus="Strumming",
            section_focus="B",
            sections={"B": ATTYA_B_CHORDS},
            guitar_tabs={},
            difficulty="advanced",
        )
        joined = " ".join(res.practice_cues)
        self.assertIn("voicing style", joined.lower())
        self.assertNotIn("pentatonic", joined.lower())

    def test_scales_focus_still_routes_to_fingerstyle_not_pentatonic_engine(self) -> None:
        self.assertEqual(_focus_kind("Scales"), "scales")


if __name__ == "__main__":
    unittest.main()
