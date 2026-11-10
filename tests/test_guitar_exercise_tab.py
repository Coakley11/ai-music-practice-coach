"""Slice 3 — the guitar gets real scale and arpeggio TAB.

The guitar already had a single-note TAB path (``guitar_pentatonic_engine``) and the renderer
to draw it, but no way to put a *given* line of pitches on the fretboard: that engine picks
its own notes from pitch classes, so it is free to choose whichever octave is convenient. A
scale study arrives as absolute MIDI and an octave is not negotiable, so these tests check
the mapping is by absolute pitch - every fret must sound exactly the note the shared engine
asked for - and that the fingering is one a guitarist would actually use.
"""

from __future__ import annotations

import unittest

from guitar_exercise_tab import (
    EXERCISE_MAX_FRET,
    OPEN_STRING_MIDI,
    build_guitar_exercise_measures,
    fret_for_midi_on_string,
    map_line_to_frets,
    playable_in_tab_range,
    positions_for_midi,
    validate_exercise_tab,
)
from practice_notation import generate_practice_notation

CHORDS = ["Am6", "C7", "B7", "Em6"]
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# A two-octave A Dorian line, the thing a position-playing guitarist fingers across strings.
LINE = [57, 59, 60, 62, 64, 66, 67, 69, 71, 72, 74, 76]


def _render(mode="scales", difficulty="medium", focus="Improvisation", chords=None, key="Am"):
    return generate_practice_notation(
        song_title="T", artist="", display_key=key, original_key=key, bpm=100,
        groove_style="Jazz swing", instrument="Guitar", focus=focus,
        section_focus=None, sections={"A": chords or CHORDS},
        difficulty=difficulty, exercise_mode=mode,
    )


class TheTuningIsTheRealOne(unittest.TestCase):
    def test_standard_tuning_low_to_high(self):
        self.assertEqual(OPEN_STRING_MIDI, (40, 45, 50, 55, 59, 64))  # E2 A2 D3 G3 B3 E4

    def test_it_is_the_same_tuning_the_backing_track_plays(self):
        """One retuning should never have to be remembered in two places."""
        from backing_rock_guitar import OPEN_STRINGS

        self.assertEqual(tuple(OPEN_STRING_MIDI), tuple(OPEN_STRINGS))

    def test_an_open_string_is_fret_zero(self):
        for s, midi in enumerate(OPEN_STRING_MIDI):
            with self.subTest(string=s):
                self.assertEqual(fret_for_midi_on_string(midi, s), 0)


class MappingIsByAbsolutePitch(unittest.TestCase):
    """The point of the module: C4 and C5 are different exercises."""

    def test_a_fret_sounds_exactly_the_requested_pitch(self):
        for midi in range(40, 77):
            for s, f in positions_for_midi(midi):
                with self.subTest(midi=midi, string=s, fret=f):
                    self.assertEqual(OPEN_STRING_MIDI[s] + f, midi)

    def test_two_octaves_of_the_same_pitch_class_get_different_frets(self):
        low = positions_for_midi(60)   # C4
        high = positions_for_midi(72)  # C5
        self.assertTrue(low and high)
        self.assertFalse(set(low) & set(high))

    def test_middle_c_is_where_a_guitarist_finds_it(self):
        """C4 = 5th fret of the G string, among others."""
        self.assertIn((3, 5), positions_for_midi(60))

    def test_a_pitch_below_the_guitar_is_not_invented(self):
        self.assertFalse(positions_for_midi(39))      # Eb2, below the low E
        self.assertFalse(playable_in_tab_range(39))

    def test_a_pitch_above_the_fret_ceiling_is_not_invented(self):
        self.assertFalse(positions_for_midi(64 + EXERCISE_MAX_FRET + 1))

    def test_a_wrong_string_returns_nothing_rather_than_a_negative_fret(self):
        self.assertIsNone(fret_for_midi_on_string(40, 5))   # E2 is not on the high e
        self.assertIsNone(fret_for_midi_on_string(60, 99))

    def test_an_unreachable_pitch_keeps_the_line_length_honest(self):
        """Reported as a gap, not quietly octave-shifted into a different exercise."""
        out = map_line_to_frets([39, 57, 200])
        self.assertEqual(len(out), 3)
        self.assertIsNone(out[0])
        self.assertIsNone(out[2])
        self.assertIsNotNone(out[1])


class TheFingeringIsPlayable(unittest.TestCase):
    def test_every_chosen_position_sounds_its_note(self):
        for pos, midi in zip(map_line_to_frets(LINE), LINE):
            with self.subTest(midi=midi):
                self.assertIsNotNone(pos)
                self.assertEqual(OPEN_STRING_MIDI[pos[0]] + pos[1], midi)

    def test_a_scale_crosses_strings_instead_of_running_up_one(self):
        """Minimising distance per note walks one string; nobody fingers a scale that way.

        What is minimised is hand *movement*, so the hand holds still and the line crosses
        strings - which is what playing in position means.
        """
        strings = {s for (s, _f) in map_line_to_frets(LINE, box_span=3)}
        self.assertGreaterEqual(len(strings), 3, "the line stayed on too few strings")

    def test_the_hand_stays_within_its_box(self):
        for span in (3, 5, 7):
            frets = [f for (_s, f) in map_line_to_frets(LINE, box_span=span) if f]
            with self.subTest(span=span):
                # Two octaves cannot fit one box, but it should take very few positions.
                self.assertLessEqual(max(frets) - min(frets), span * 2 + 1)

    def test_no_unplayable_same_string_stretch(self):
        from guitar_pentatonic_engine import MAX_SAME_STRING_JUMP

        prev = None
        for pos in map_line_to_frets(LINE):
            if prev and pos and prev[0] == pos[0]:
                self.assertLessEqual(abs(pos[1] - prev[1]), MAX_SAME_STRING_JUMP)
            prev = pos

    def test_the_playability_rules_are_the_pentatonic_engines_own(self):
        """One fretboard policy for every melodic guitar line, not a second copy."""
        import guitar_exercise_tab as g
        from guitar_pentatonic_engine import MAX_CONSECUTIVE_JUMP, MAX_SAME_STRING_JUMP

        self.assertIs(g.MAX_SAME_STRING_JUMP, MAX_SAME_STRING_JUMP)
        self.assertIs(g.MAX_CONSECUTIVE_JUMP, MAX_CONSECUTIVE_JUMP)

    def test_an_empty_line_is_safe(self):
        self.assertEqual(map_line_to_frets([]), [])

    def test_a_single_note_is_safe(self):
        self.assertEqual(len(map_line_to_frets([60])), 1)

    def test_every_generated_exercise_validates(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            for mode in ("scales", "arpeggios", "auto"):
                ms = build_guitar_exercise_measures(CHORDS, level=level, mode=mode)
                ok, why = validate_exercise_tab(ms)
                with self.subTest(level=level, mode=mode):
                    self.assertTrue(ok, why)

    def test_every_fret_is_on_the_neck(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            for ev in [e for m in build_guitar_exercise_measures(CHORDS, level=level) for e in m]:
                with self.subTest(level=level):
                    self.assertTrue(0 <= ev.fret <= EXERCISE_MAX_FRET)
                    self.assertTrue(0 <= ev.string_idx <= 5)

    def test_a_beginner_stays_down_the_neck(self):
        frets = [e.fret for m in build_guitar_exercise_measures(CHORDS, level="Beginner") for e in m]
        self.assertLessEqual(max(frets), 9, "a beginner study climbed too high")

    def test_shifts_are_marked_so_the_tab_can_show_them(self):
        ms = build_guitar_exercise_measures(CHORDS, level="Advanced", mode="arpeggios")
        self.assertTrue(all(hasattr(e, "position_shift") for m in ms for e in m))


class TheLevelCurveIsTheSharedOne(unittest.TestCase):
    def test_note_density_follows_notes_per_bar(self):
        from notation_exercise_patterns import NOTES_PER_BAR

        for level in ("Beginner", "Intermediate", "Advanced"):
            ms = build_guitar_exercise_measures(CHORDS, level=level)
            with self.subTest(level=level):
                self.assertEqual(len(ms[0]), NOTES_PER_BAR[level])

    def test_notes_land_on_the_shared_slot_grid(self):
        from guitar_pentatonic_engine import LEVEL_SLOTS

        for level in ("Beginner", "Intermediate", "Advanced"):
            ms = build_guitar_exercise_measures(CHORDS, level=level)
            with self.subTest(level=level):
                self.assertEqual(
                    sorted(e.slot for e in ms[0]), sorted(LEVEL_SLOTS[level])
                )

    def test_one_bar_per_chord(self):
        self.assertEqual(len(build_guitar_exercise_measures(CHORDS)), len(CHORDS))

    def test_an_unknown_level_does_not_crash(self):
        self.assertTrue(build_guitar_exercise_measures(CHORDS, level="Wizard"))

    def test_no_chords_is_safe(self):
        self.assertEqual(build_guitar_exercise_measures([]), [])


class TheHarmonyComesFromTheSharedEngine(unittest.TestCase):
    def test_am6_sounds_its_f_sharp_not_an_aeolian_g(self):
        """The same answer the wind instruments and the piano get for Am6."""
        pcs = {
            (OPEN_STRING_MIDI[e.string_idx] + e.fret) % 12
            for m in build_guitar_exercise_measures(["Am6"] * 4, level="Advanced")
            for e in m
        }
        self.assertIn(NAMES.index("F#"), pcs)

    def test_an_altered_dominant_does_not_sound_a_natural_fifth(self):
        pcs = {
            (OPEN_STRING_MIDI[e.string_idx] + e.fret) % 12
            for m in build_guitar_exercise_measures(["C7alt"] * 4, level="Advanced",
                                                    mode="arpeggios")
            for e in m
        }
        self.assertNotIn(NAMES.index("G"), pcs)

    def test_the_builder_decides_no_harmony_of_its_own(self):
        import inspect

        import guitar_exercise_tab as g

        src = inspect.getsource(g.build_guitar_exercise_measures)
        self.assertIn("build_exercise_midis", src)

    def test_nothing_offsets_for_a_capo_here(self):
        """Capo mode transposes the chart upstream; offsetting again would transpose twice."""
        import inspect

        import guitar_exercise_tab as g

        self.assertNotIn("capo_fret", inspect.getsource(g))


class ThePracticePageWiresItUp(unittest.TestCase):
    def test_all_three_modes_render_tab(self):
        for mode in ("auto", "arpeggios", "scales"):
            with self.subTest(mode=mode):
                self.assertEqual(_render(mode).format, "tab")

    def test_the_three_modes_are_musically_different(self):
        html = {m: _render(m).html for m in ("auto", "arpeggios", "scales")}
        self.assertEqual(len(set(html.values())), 3)

    def test_an_exercise_cue_names_the_study_and_its_shifts(self):
        cues = " ".join(_render("scales").practice_cues)
        self.assertIn("scale study", cues)
        cues = " ".join(_render("arpeggios").practice_cues)
        self.assertIn("arpeggio study", cues)

    def test_auto_keeps_the_chord_voicing_cue(self):
        self.assertIn("voicing style", " ".join(_render("auto").practice_cues))

    def test_an_explicit_mode_overrides_the_practice_focus(self):
        """The selector is the user saying which study they want."""
        scales = _render("scales", focus="Pentatonics")
        auto = _render("auto", focus="Pentatonics")
        self.assertNotEqual(scales.html, auto.html)
        self.assertIn("scale study", " ".join(scales.practice_cues))

    def test_the_tab_moves_across_the_fretboard(self):
        """A scale study must show movement, not one shape held for the bar."""
        bar = _render("scales").body.split("\n\n")[0]
        frets = {ch for line in bar.splitlines()[3:] for ch in line if ch.isdigit()}
        self.assertGreater(len(frets), 1)

    def test_guitar_is_no_longer_reported_as_unsupported(self):
        from practice_notation import (
            exercise_mode_supported,
            exercise_mode_unsupported_reason,
        )

        self.assertTrue(exercise_mode_supported("Guitar"))
        self.assertEqual(exercise_mode_unsupported_reason("Guitar"), "")

    def test_bass_is_still_deferred_and_says_so(self):
        from practice_notation import (
            exercise_mode_supported,
            exercise_mode_unsupported_reason,
        )

        self.assertFalse(exercise_mode_supported("Bass"))
        self.assertIn("walking bass line", exercise_mode_unsupported_reason("Bass"))

    def test_the_selector_agrees_with_whichever_builder_actually_runs(self):
        """Not a guess about the name: the same dispatch the router uses.

        "Bass Guitar" routes to the guitar builder, because the router has always matched
        "guitar" before "bass". That precedence is pre-existing and not changed here; what
        matters is that the selector reports the builder that really runs rather than
        deciding separately and contradicting it.
        """
        from practice_notation import exercise_mode_supported, notation_builder_kind

        self.assertEqual(notation_builder_kind("Bass Guitar"), "guitar")
        self.assertTrue(exercise_mode_supported("Bass Guitar"))
        self.assertEqual(notation_builder_kind("Bass"), "bass")
        self.assertFalse(exercise_mode_supported("Bass"))

    def test_the_key_reaches_the_exercise(self):
        """Proved with a chord whose scale the key actually decides.

        TAB prints fret numbers, not note names, so the key can only show up where it
        changes which scale is chosen. Over Am6 or a plain C7 it does not - those resolve
        the same in every key - so comparing those would pass for the wrong reason or fail
        for one. A C7b9 runs phrygian dominant in a minor key and half-whole diminished in
        a major one, so a difference here is the key reaching the exercise.
        """
        minor = _render("scales", chords=["C7b9"] * 4, key="Am").body
        major = _render("scales", chords=["C7b9"] * 4, key="C").body
        self.assertNotEqual(minor, major)

    def test_every_level_renders(self):
        for difficulty in ("easy", "medium", "advanced"):
            for mode in ("scales", "arpeggios"):
                with self.subTest(difficulty=difficulty, mode=mode):
                    self.assertTrue(_render(mode, difficulty).html)


if __name__ == "__main__":
    unittest.main()
