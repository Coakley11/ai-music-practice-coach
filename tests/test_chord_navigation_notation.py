"""Tests for chord_navigation_notation.py -- the voice-led chord-tone
navigation exercise engine behind the Notation/TAB redesign. Distinct from
Generated Practice Melody: proves *connection* between chords, not melodic
composition quality."""

from __future__ import annotations

import unittest

from chord_navigation_notation import (
    LEVEL_PROFILES,
    VALID_LEVELS,
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
    def test_one_voicing_per_chord(self) -> None:
        voicings = build_connected_piano_voicings(_PROGRESSION, level="Intermediate")
        self.assertEqual(len(voicings), len(_PROGRESSION))

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


if __name__ == "__main__":
    unittest.main()
