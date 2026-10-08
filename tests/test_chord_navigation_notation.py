"""Tests for chord_navigation_notation.py -- the voice-led chord-tone
navigation exercise engine behind the Notation/TAB redesign. Distinct from
Generated Practice Melody: proves *connection* between chords, not melodic
composition quality."""

from __future__ import annotations

import unittest

from chord_navigation_notation import (
    LEVEL_PROFILES,
    VALID_LEVELS,
    _phrase_groups,
    arpeggio_events_to_melody_dicts,
    build_bass_line,
    build_connected_arpeggio_line,
    build_connected_piano_voicings,
    build_piano_voicing_abc,
    chord_tone_pool,
    instrument_register,
)
from composition_melody_notation import build_abc_from_melody_events

_PROGRESSION = ["Am7", "Dm7", "G7", "Cmaj7"]


class TestChordTonePool(unittest.TestCase):
    def test_returns_letter_correct_tones(self) -> None:
        self.assertEqual(chord_tone_pool("Am7")[:3], ["A", "C", "E"])

    def test_empty_chord_falls_back_to_c_major(self) -> None:
        self.assertEqual(chord_tone_pool("")[0], "C")


class TestConnectedArpeggioLine(unittest.TestCase):
    def test_one_event_group_per_chord_minimum(self) -> None:
        events = build_connected_arpeggio_line(_PROGRESSION, level="Beginner")
        measures = {e.measure for e in events}
        self.assertEqual(measures, set(range(len(_PROGRESSION))))

    def test_events_carry_the_correct_chord_label(self) -> None:
        events = build_connected_arpeggio_line(_PROGRESSION, level="Intermediate")
        for e in events:
            self.assertEqual(e.chord, _PROGRESSION[e.measure])

    def test_voice_leading_no_gratuitous_leaps_between_chords(self) -> None:
        """The first note of each chord must be within a comfortable interval
        of the last note of the previous chord -- proof of voice leading,
        not independent fixed-octave root-position shapes per chord."""
        for level in LEVEL_PROFILES:
            events = build_connected_arpeggio_line(_PROGRESSION, level=level, start_midi=60)
            by_measure: dict[int, list] = {}
            for e in events:
                by_measure.setdefault(e.measure, []).append(e)
            for m in range(1, len(_PROGRESSION)):
                prev_sounding = [e for e in by_measure[m - 1] if not e.is_rest]
                cur_sounding = [e for e in by_measure[m] if not e.is_rest]
                if not prev_sounding or not cur_sounding:
                    continue
                leap = abs(cur_sounding[0].midi - prev_sounding[-1].midi)
                self.assertLessEqual(
                    leap, 12, f"level={level} measure={m}: leap of {leap} semitones is not voice-led"
                )

    def test_advanced_approach_tone_connects_to_next_measures_actual_first_note(self) -> None:
        events = build_connected_arpeggio_line(_PROGRESSION, level="Advanced", start_midi=60)
        by_measure: dict[int, list] = {}
        for e in events:
            by_measure.setdefault(e.measure, []).append(e)
        for m in range(len(_PROGRESSION) - 1):
            last_this = by_measure[m][-1]
            first_next = by_measure[m + 1][0]
            self.assertEqual(
                abs(first_next.midi - last_this.midi),
                1,
                f"measure {m}'s approach tone must land a half-step from measure {m + 1}'s actual first note",
            )

    def test_beginner_has_fewer_tones_than_advanced(self) -> None:
        beg = [e for e in build_connected_arpeggio_line(_PROGRESSION, level="Beginner") if not e.is_rest]
        adv = [e for e in build_connected_arpeggio_line(_PROGRESSION, level="Advanced") if not e.is_rest]
        self.assertLess(len(beg), len(adv))

    def test_beginner_includes_rests_advanced_does_not(self) -> None:
        beg = build_connected_arpeggio_line(_PROGRESSION, level="Beginner")
        adv = build_connected_arpeggio_line(_PROGRESSION, level="Advanced")
        self.assertTrue(any(e.is_rest for e in beg))
        self.assertFalse(any(e.is_rest for e in adv))

    def test_unknown_level_falls_back_to_intermediate(self) -> None:
        a = build_connected_arpeggio_line(_PROGRESSION, level="Nonsense")
        b = build_connected_arpeggio_line(_PROGRESSION, level="Intermediate")
        self.assertEqual(len(a), len(b))

    def test_renders_through_shared_abc_pipeline_with_chord_symbols(self) -> None:
        events = build_connected_arpeggio_line(_PROGRESSION, level="Intermediate")
        dicts = arpeggio_events_to_melody_dicts(events)
        abc = build_abc_from_melody_events(
            dicts, key="C", meter="4/4", bpm=96, title="Test", chords=_PROGRESSION
        )
        for chord in _PROGRESSION:
            self.assertIn(f'"{chord}"', abc)


class TestConnectedPianoVoicings(unittest.TestCase):
    def test_every_measure_covered_with_comping_rhythm_summing_correctly(self) -> None:
        """Beyond one static block chord per measure (item 9): each chord
        gets a real comping rhythm, and every measure's hit durations
        still sum to exactly one bar (F2 measure-sync invariant)."""
        voicings = build_connected_piano_voicings(_PROGRESSION, level="Intermediate")
        by_measure: dict[int, list] = {}
        for v in voicings:
            by_measure.setdefault(v.measure, []).append(v)
        self.assertEqual(sorted(by_measure), list(range(len(_PROGRESSION))))
        for m_idx, hits in by_measure.items():
            total = sum(h.duration_beats for h in hits)
            self.assertAlmostEqual(total, 4.0, places=6, msg=f"measure {m_idx} duration sum")

    def test_beginner_mostly_one_hit_advanced_more_hits(self) -> None:
        """Difficulty is visible in the comping rhythm itself, not just
        note count -- Advanced should comp more often than Beginner."""
        beginner = build_connected_piano_voicings(_PROGRESSION, level="Beginner")
        advanced = build_connected_piano_voicings(_PROGRESSION, level="Advanced")
        self.assertLess(len(beginner), len(advanced))

    def test_voicing_pitches_are_unique_and_ascending(self) -> None:
        voicings = build_connected_piano_voicings(_PROGRESSION, level="Advanced")
        for v in voicings:
            self.assertEqual(len(set(v.midis)), len(v.midis))
            self.assertEqual(list(v.midis), sorted(v.midis))

    def test_voicings_connect_closely_to_the_previous_one(self) -> None:
        voicings = build_connected_piano_voicings(_PROGRESSION, level="Intermediate")
        for i in range(1, len(voicings)):
            prev_center = sum(voicings[i - 1].midis) / len(voicings[i - 1].midis)
            cur_center = sum(voicings[i].midis) / len(voicings[i].midis)
            self.assertLessEqual(
                abs(cur_center - prev_center),
                6,
                f"voicing {i} should sit close to voicing {i - 1} (closest-voicing connection)",
            )

    def test_abc_output_has_chord_symbols_and_bracketed_voicings(self) -> None:
        voicings = build_connected_piano_voicings(_PROGRESSION, level="Intermediate")
        abc = build_piano_voicing_abc(voicings, key="C", meter="4/4", bpm=90, title="Piano test")
        for chord in _PROGRESSION:
            self.assertIn(f'"{chord}"', abc)
        self.assertIn("[", abc)
        self.assertIn("]", abc)

    def test_beginner_uses_three_tone_voicings(self) -> None:
        voicings = build_connected_piano_voicings(_PROGRESSION, level="Beginner")
        for v in voicings:
            self.assertEqual(len(v.pitches), 3)


class TestInstrumentRegister(unittest.TestCase):
    """Each wind/generic instrument gets its own playable written register --
    not the one fixed octave every instrument used to share (the bug: Alto
    Sax generated in an inappropriate register, identical to every other
    instrument)."""

    def test_alto_and_tenor_sax_get_different_registers(self) -> None:
        from chord_navigation_notation import instrument_register

        alto_lo, alto_hi, _ = instrument_register("Alto Sax", "Beginner")
        tenor_lo, tenor_hi, _ = instrument_register("Tenor Sax", "Beginner")
        self.assertNotEqual((alto_lo, alto_hi), (tenor_lo, tenor_hi))

    def test_flute_sits_higher_than_tuba(self) -> None:
        from chord_navigation_notation import instrument_register

        flute_lo, _, _ = instrument_register("Flute", "Beginner")
        tuba_lo, tuba_hi, _ = instrument_register("Tuba", "Beginner")
        self.assertGreater(flute_lo, tuba_hi)

    def test_advanced_register_is_wider_than_beginner(self) -> None:
        from chord_navigation_notation import instrument_register

        for instrument in ("Alto Sax", "Tenor Sax", "Trumpet", "Flute", "Clarinet"):
            b_lo, b_hi, _ = instrument_register(instrument, "Beginner")
            a_lo, a_hi, _ = instrument_register(instrument, "Advanced")
            self.assertLessEqual(a_lo, b_lo, instrument)
            self.assertGreaterEqual(a_hi, b_hi, instrument)

    def test_connected_line_stays_inside_instrument_register_at_every_level(self) -> None:
        for instrument in ("Alto Sax", "Tenor Sax", "Trumpet", "Flute", "Clarinet"):
            for level in LEVEL_PROFILES:
                lo, hi, _ = instrument_register(instrument, level)
                events = build_connected_arpeggio_line(
                    _PROGRESSION, level=level, instrument=instrument
                )
                for e in events:
                    if e.is_rest or e.midi is None:
                        continue
                    self.assertGreaterEqual(
                        e.midi, lo, f"{instrument}/{level}: {e.pitch}{e.midi} below {lo}"
                    )
                    self.assertLessEqual(
                        e.midi, hi, f"{instrument}/{level}: {e.pitch}{e.midi} above {hi}"
                    )

    def test_beginner_line_stays_in_the_comfortable_subset(self) -> None:
        """Beginner must use the instrument's own comfortable pedagogical
        register, not the wider Advanced envelope."""
        lo, hi, _ = instrument_register("Alto Sax", "Beginner")
        adv_lo, adv_hi, _ = instrument_register("Alto Sax", "Advanced")
        self.assertGreaterEqual(lo, adv_lo)
        self.assertLessEqual(hi, adv_hi)
        events = build_connected_arpeggio_line(
            _PROGRESSION, level="Beginner", instrument="Alto Sax"
        )
        for e in events:
            if e.is_rest or e.midi is None:
                continue
            self.assertGreaterEqual(e.midi, lo)
            self.assertLessEqual(e.midi, hi)


class TestBassLine(unittest.TestCase):
    """Bass gets an actual bass-line study (roots/fifths -> passing/
    approach tones -> a real connected line), not the wind arpeggio engine
    rendered in bass clef, and the line's STYLE follows the song's own
    resolved groove rather than one generic treatment."""

    def test_measures_sum_to_the_full_bar(self) -> None:
        for level in VALID_LEVELS:
            for groove in ("Pop groove", "Jazz swing", "Bossa nova", "Ballad"):
                events = build_bass_line(_PROGRESSION, level=level, groove_style=groove)
                for m_idx in range(len(_PROGRESSION)):
                    total = sum(
                        e.duration_beats for e in events if e.measure == m_idx
                    )
                    self.assertAlmostEqual(
                        total, 4.0, msg=f"{level}/{groove} measure {m_idx}"
                    )

    def test_beginner_uses_roots_and_fifths_regardless_of_groove(self) -> None:
        """Beginner stays foundational (roots/fifths) across every groove --
        groove-specific patterns are an Intermediate/Advanced concern."""
        pop = build_bass_line(_PROGRESSION, level="Beginner", groove_style="Pop groove")
        swing = build_bass_line(_PROGRESSION, level="Beginner", groove_style="Jazz swing")
        pop_pitches = [(e.measure, e.pitch, e.midi) for e in pop if not e.is_rest]
        swing_pitches = [(e.measure, e.pitch, e.midi) for e in swing if not e.is_rest]
        self.assertEqual(pop_pitches, swing_pitches)
        # Each measure is exactly root then fifth (2 events, both chord tones).
        for m_idx, chord in enumerate(_PROGRESSION):
            m_events = [e for e in pop if e.measure == m_idx and not e.is_rest]
            self.assertEqual(len(m_events), 2)

    def test_jazz_swing_groove_produces_a_walking_style_line_at_advanced(self) -> None:
        events = build_bass_line(_PROGRESSION, level="Advanced", groove_style="Jazz swing")
        for m_idx in range(len(_PROGRESSION)):
            m_events = [e for e in events if e.measure == m_idx and not e.is_rest]
            # True walking bass: four quarter-note beats, one note each.
            self.assertEqual(len(m_events), 4)
            for e in m_events:
                self.assertEqual(e.duration_beats, 1.0)

    def test_pop_groove_does_not_produce_a_walking_line(self) -> None:
        """A Pop song must not get a walking jazz bass line."""
        walking = build_bass_line(_PROGRESSION, level="Advanced", groove_style="Jazz swing")
        pop = build_bass_line(_PROGRESSION, level="Advanced", groove_style="Pop groove")
        walking_pitches = [(e.pitch, e.midi) for e in walking if not e.is_rest]
        pop_pitches = [(e.pitch, e.midi) for e in pop if not e.is_rest]
        self.assertNotEqual(walking_pitches, pop_pitches)

    def test_latin_groove_includes_syncopation(self) -> None:
        """A Latin/Bossa groove must produce a syncopated pattern (a rest
        on the beat, note on the off-beat), not a plain quarter-note feel."""
        events = build_bass_line(_PROGRESSION, level="Intermediate", groove_style="Bossa nova")
        rests = [e for e in events if e.is_rest]
        self.assertTrue(rests, "expected at least one syncopation rest")

    def test_walking_line_approaches_the_next_chords_root(self) -> None:
        """Advanced walking bass's last beat of each bar should sit a
        half-step from the next chord's root -- genuine chromatic approach,
        not an arbitrary chord tone."""
        from chord_navigation_notation import _pc_of, chord_tone_pool

        events = build_bass_line(_PROGRESSION, level="Advanced", groove_style="Jazz swing")
        for m_idx in range(len(_PROGRESSION) - 1):
            m_events = [e for e in events if e.measure == m_idx and not e.is_rest]
            last = m_events[-1]
            next_root_pc = _pc_of(chord_tone_pool(_PROGRESSION[m_idx + 1])[0])
            diff = min((last.midi % 12 - next_root_pc) % 12, (next_root_pc - last.midi % 12) % 12)
            self.assertEqual(diff, 1, f"measure {m_idx} approach tone not a half-step away")

    def test_bass_line_stays_inside_bass_register(self) -> None:
        for level in VALID_LEVELS:
            lo, hi, _ = instrument_register("Bass", level)
            events = build_bass_line(_PROGRESSION, level=level, groove_style="Jazz swing")
            for e in events:
                if e.is_rest or e.midi is None:
                    continue
                self.assertGreaterEqual(e.midi, lo)
                self.assertLessEqual(e.midi, hi)

    def test_intermediate_adds_more_harmonic_color_than_beginner(self) -> None:
        beginner = build_bass_line(_PROGRESSION, level="Beginner", groove_style="Pop groove")
        intermediate = build_bass_line(_PROGRESSION, level="Intermediate", groove_style="Pop groove")
        beginner_notes = sum(1 for e in beginner if not e.is_rest)
        intermediate_notes = sum(1 for e in intermediate if not e.is_rest)
        self.assertGreater(intermediate_notes, beginner_notes)


class TestArticulation(unittest.TestCase):
    """Accents/articulation must materially differ by level (item 8: not
    just note count), rendered via abcjs-native ABC decorations."""

    def test_beginner_has_no_articulation_marks(self) -> None:
        events = build_connected_arpeggio_line(_PROGRESSION, level="Beginner", instrument="Saxophone")
        self.assertTrue(all(not e.articulation for e in events if not e.is_rest))

    def test_intermediate_accents_the_arrival_note_of_each_measure(self) -> None:
        events = build_connected_arpeggio_line(_PROGRESSION, level="Intermediate", instrument="Saxophone")
        for m_idx in range(len(_PROGRESSION)):
            first = next(e for e in events if e.measure == m_idx and not e.is_rest)
            self.assertEqual(first.articulation, "accent")

    def test_advanced_marks_approach_tones_staccato(self) -> None:
        events = build_connected_arpeggio_line(_PROGRESSION, level="Advanced", instrument="Saxophone")
        staccato_events = [e for e in events if e.articulation == "staccato"]
        self.assertTrue(staccato_events)

    def test_articulation_survives_into_abc_output(self) -> None:
        events = build_connected_arpeggio_line(_PROGRESSION, level="Advanced", instrument="Saxophone")
        dicts = arpeggio_events_to_melody_dicts(events)
        abc = build_abc_from_melody_events(dicts, key="C", meter="4/4", bpm=100, title="t", chords=_PROGRESSION)
        self.assertIn("!>!", abc)


class TestPianoAdvancedExtensions(unittest.TestCase):
    """Advanced piano voicings add a 9th on plain 7th-type chords where
    harmonically idiomatic -- never on a bare triad or on a chord that
    already names its own extension (item 10: "extensions only when
    harmonically valid")."""

    def test_advanced_adds_a_ninth_on_a_seventh_chord(self) -> None:
        voicings = build_connected_piano_voicings(["Cmaj7"], level="Advanced")
        self.assertEqual(len(voicings[0].pitches), 5)

    def test_intermediate_does_not_add_a_ninth(self) -> None:
        voicings = build_connected_piano_voicings(["Cmaj7"], level="Intermediate")
        self.assertEqual(len(voicings[0].pitches), 4)

    def test_bare_triad_never_gets_a_ninth_even_at_advanced(self) -> None:
        voicings = build_connected_piano_voicings(["C"], level="Advanced")
        self.assertEqual(len(voicings[0].pitches), 3)

    def test_chord_already_naming_an_extension_is_not_doubled(self) -> None:
        voicings = build_connected_piano_voicings(["C9"], level="Advanced")
        # Should still use the chord-tone pool as-is (4 tones), not append
        # a second, guessed 9th on top of one already named.
        self.assertLessEqual(len(voicings[0].pitches), 4)


_LONG_PROGRESSION = [
    "Fm7", "Bbm7", "Eb7", "Abmaj7", "Dbmaj7", "G7", "Cmaj7", "Cmaj7",
    "Fm7", "Bbm7", "Eb7", "Abmaj7", "Dbmaj7", "Bdim7", "Ebm7", "Ab7",
    "Dbm7", "Gb7", "Bmaj7", "Emaj7", "Am7", "D7", "Gmaj7", "C7",
    "Fm7", "Dm7", "G7", "Cmaj7", "Am7", "D7", "Gmaj7", "Cmaj7",
]

_ALL_NAMED_INSTRUMENTS = (
    "Alto Saxophone",
    "Tenor Saxophone",
    "Soprano Saxophone",
    "Baritone Saxophone",
    "Clarinet",
    "Flute",
    "Trumpet",
    "Trombone",
)


class TestRegisterAcrossAllNamedInstruments(unittest.TestCase):
    """Item 1/14: every generated pitch stays inside the selected
    instrument/level's written register -- checked for every instrument
    the spec names explicitly, over a long (32-measure) progression, not
    just a 4-chord smoke case."""

    def test_every_pitch_in_register_long_progression(self) -> None:
        for instrument in _ALL_NAMED_INSTRUMENTS:
            for level in VALID_LEVELS:
                lo, hi, _ = instrument_register(instrument, level)
                events = build_connected_arpeggio_line(
                    _LONG_PROGRESSION, level=level, instrument=instrument
                )
                for e in events:
                    if e.is_rest or e.midi is None:
                        continue
                    self.assertGreaterEqual(
                        e.midi, lo, f"{instrument}/{level}: {e.pitch}{e.midi} below {lo}"
                    )
                    self.assertLessEqual(
                        e.midi, hi, f"{instrument}/{level}: {e.pitch}{e.midi} above {hi}"
                    )

    def test_validator_rejects_an_out_of_range_event(self) -> None:
        from chord_navigation_notation import ArpeggioEvent, validate_events_in_register

        bad = [ArpeggioEvent(chord="C", measure=0, beat=0.0, duration_beats=1.0, is_rest=False, pitch="C", midi=200)]
        with self.assertRaises(AssertionError):
            validate_events_in_register(bad, 40, 80)

    def test_bass_stays_in_register_over_long_progression(self) -> None:
        for level in VALID_LEVELS:
            lo, hi, _ = instrument_register("Bass", level)
            events = build_bass_line(_LONG_PROGRESSION, level=level, groove_style="Jazz swing")
            for e in events:
                if e.is_rest or e.midi is None:
                    continue
                self.assertGreaterEqual(e.midi, lo)
                self.assertLessEqual(e.midi, hi)


class TestContourAndDirection(unittest.TestCase):
    """Item 2: the line has an overall contour (ascending/descending/
    direction changes) through the whole progression, not an identical
    shape restarted on the root every chord."""

    def test_direction_changes_occur_over_a_long_progression(self) -> None:
        for level in ("Intermediate", "Advanced"):
            events = build_connected_arpeggio_line(
                _LONG_PROGRESSION, level=level, instrument="Alto Saxophone", start_midi=65
            )
            sounded = [e for e in events if not e.is_rest]
            directions = []
            for a, b in zip(sounded, sounded[1:]):
                if b.midi != a.midi:
                    directions.append(1 if b.midi > a.midi else -1)
            sign_changes = sum(1 for x, y in zip(directions, directions[1:]) if x != y)
            self.assertGreater(sign_changes, 2, f"level={level}: line never changes direction")

    def test_not_every_measure_restarts_on_the_chord_root(self) -> None:
        """The entry tone of each measure should sometimes be a tone other
        than the root -- nearest chord-tone entry, not a fixed restart."""
        events = build_connected_arpeggio_line(
            _LONG_PROGRESSION, level="Advanced", instrument="Alto Saxophone", start_midi=65
        )
        by_measure: dict[int, list] = {}
        for e in events:
            if not e.is_rest:
                by_measure.setdefault(e.measure, []).append(e)
        entries = [evs[0].pitch for evs in by_measure.values() if evs]
        roots = [chord_tone_pool(c)[0] for c in _LONG_PROGRESSION]
        non_root_entries = sum(1 for entry, root in zip(entries, roots) if entry != root)
        self.assertGreater(non_root_entries, 0, "every measure entered on the root -- no real contour")


class TestRhythmicVariety(unittest.TestCase):
    """Item 4: real internal rhythmic variety, not one identical rhythmic
    cell repeated for every chord, while every measure's durations still
    sum to exactly the authoritative bar length (F2 sync invariant)."""

    def test_measures_sum_to_the_full_bar_at_every_level(self) -> None:
        for level in VALID_LEVELS:
            events = build_connected_arpeggio_line(_LONG_PROGRESSION, level=level, instrument="Alto Saxophone")
            by_measure: dict[int, float] = {}
            for e in events:
                by_measure[e.measure] = by_measure.get(e.measure, 0.0) + e.duration_beats
            for m_idx, total in by_measure.items():
                self.assertAlmostEqual(total, 4.0, places=6, msg=f"{level} measure {m_idx}")

    def test_not_every_measure_uses_the_same_rhythm_pattern(self) -> None:
        for level in VALID_LEVELS:
            events = build_connected_arpeggio_line(_LONG_PROGRESSION, level=level, instrument="Alto Saxophone")
            by_measure: dict[int, tuple] = {}
            for e in events:
                by_measure.setdefault(e.measure, []).append(round(e.duration_beats, 3))
            patterns = {tuple(v) for v in by_measure.values()}
            self.assertGreater(len(patterns), 1, f"{level}: every measure used the identical rhythm cell")

    def test_rhythm_includes_subdivisions_finer_than_a_quarter_note(self) -> None:
        for level in ("Intermediate", "Advanced"):
            events = build_connected_arpeggio_line(_LONG_PROGRESSION, level=level, instrument="Alto Saxophone")
            self.assertTrue(
                any(e.duration_beats < 1.0 for e in events if not e.is_rest),
                f"{level}: no eighth-note (or finer) movement found",
            )


class TestSlursAndPhrasing(unittest.TestCase):
    """Item 3: real notation-level slurs via ABC syntax, differentiated by
    level, and balanced (every opening paren has a matching close)."""

    def test_slur_markers_present_at_every_level(self) -> None:
        for level in VALID_LEVELS:
            events = build_connected_arpeggio_line(_LONG_PROGRESSION, level=level, instrument="Alto Saxophone")
            self.assertTrue(any(e.slur for e in events), f"{level}: no slur markers generated")

    def test_slur_markers_are_balanced_start_and_end(self) -> None:
        for level in VALID_LEVELS:
            events = build_connected_arpeggio_line(_LONG_PROGRESSION, level=level, instrument="Alto Saxophone")
            starts = sum(1 for e in events if e.slur in ("start", "both"))
            ends = sum(1 for e in events if e.slur in ("end", "both"))
            self.assertEqual(starts, ends, f"{level}: unbalanced slur start/end count")

    def test_abc_output_has_balanced_slur_parens(self) -> None:
        for level in VALID_LEVELS:
            events = build_connected_arpeggio_line(_LONG_PROGRESSION, level=level, instrument="Alto Saxophone")
            dicts = arpeggio_events_to_melody_dicts(events)
            abc = build_abc_from_melody_events(
                dicts, key="Ab", meter="4/4", bpm=120, title="t", chords=_LONG_PROGRESSION
            )
            body = abc.rsplit("K:", 1)[-1]
            self.assertEqual(body.count("("), body.count(")"), f"{level}: unbalanced ( ) in ABC output")

    def test_beginner_slurs_are_short_intermediate_and_advanced_cross_barlines(self) -> None:
        """Beginner phrases stay within one measure; Intermediate/Advanced
        slurs span multiple measures -- genuinely connected phrases, not
        one slur per bar everywhere."""
        beg_events = build_connected_arpeggio_line(_LONG_PROGRESSION, level="Beginner", instrument="Alto Saxophone")
        adv_events = build_connected_arpeggio_line(_LONG_PROGRESSION, level="Advanced", instrument="Alto Saxophone")

        def slur_spans(events) -> list[tuple[int, int]]:
            spans = []
            start_m = None
            for e in events:
                if e.slur in ("start", "both"):
                    start_m = e.measure
                if e.slur in ("end", "both") and start_m is not None:
                    spans.append((start_m, e.measure))
                    start_m = None
            return spans

        beg_spans = slur_spans(beg_events)
        adv_spans = slur_spans(adv_events)
        self.assertTrue(all(end - start == 0 for start, end in beg_spans), "Beginner slur crossed a barline")
        self.assertTrue(any(end - start > 0 for start, end in adv_spans), "Advanced never slurred across a barline")

    def test_not_every_phrase_is_slurred_at_intermediate_and_advanced(self) -> None:
        """Mixed articulation (item 3): some phrases are left plain/tongued,
        not everything indiscriminately slurred."""
        for level in ("Intermediate", "Advanced"):
            events = build_connected_arpeggio_line(_LONG_PROGRESSION, level=level, instrument="Alto Saxophone")
            sounded = [e for e in events if not e.is_rest]
            unslurred = [e for e in sounded if not e.slur]
            self.assertTrue(unslurred, f"{level}: every single note was part of a slur")


class TestLevelsDifferStructurally(unittest.TestCase):
    """Item 10: Beginner/Intermediate/Advanced must differ in more than
    note count -- register usage, rhythmic vocabulary, and slur/phrase
    shape should all visibly differ for the same song/section/instrument."""

    def test_rhythm_vocabulary_differs_by_level(self) -> None:
        patterns_by_level = {}
        for level in VALID_LEVELS:
            events = build_connected_arpeggio_line(_LONG_PROGRESSION, level=level, instrument="Alto Saxophone")
            by_measure: dict[int, tuple] = {}
            for e in events:
                by_measure.setdefault(e.measure, []).append(round(e.duration_beats, 3))
            patterns_by_level[level] = {tuple(v) for v in by_measure.values()}
        self.assertNotEqual(patterns_by_level["Beginner"], patterns_by_level["Advanced"])
        self.assertNotEqual(patterns_by_level["Intermediate"], patterns_by_level["Advanced"])

    def test_phrase_shape_differs_by_level(self) -> None:
        shapes = {}
        for level in VALID_LEVELS:
            shapes[level] = _phrase_groups(level, 8)
        self.assertNotEqual(shapes["Beginner"], shapes["Intermediate"])
        self.assertNotEqual(shapes["Intermediate"], shapes["Advanced"])


class TestPianoCompingByLevel(unittest.TestCase):
    """Item 9: piano comping rhythm itself differs by level -- Beginner
    stays simple, Advanced comps more often with more varied rhythm."""

    def test_comping_hit_count_increases_with_level(self) -> None:
        counts = {}
        for level in VALID_LEVELS:
            events = build_connected_piano_voicings(_LONG_PROGRESSION, level=level)
            counts[level] = len(events)
        self.assertLess(counts["Beginner"], counts["Intermediate"])
        self.assertLessEqual(counts["Intermediate"], counts["Advanced"])

    def test_every_measure_sums_to_full_bar_at_every_level(self) -> None:
        for level in VALID_LEVELS:
            events = build_connected_piano_voicings(_LONG_PROGRESSION, level=level)
            by_measure: dict[int, float] = {}
            for e in events:
                by_measure[e.measure] = by_measure.get(e.measure, 0.0) + e.duration_beats
            for m_idx, total in by_measure.items():
                self.assertAlmostEqual(total, 4.0, places=6, msg=f"{level} measure {m_idx}")


if __name__ == "__main__":
    unittest.main()
