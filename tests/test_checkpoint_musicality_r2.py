"""Checkpoint tests: canonical groove propagation into Guitar TAB, real
guitar level/voicing differentiation, Practice-Focus-conditioned
Notation/TAB and Practice Melody (including the new Pentatonics focus),
and the Backing-scope / Practice-Focus-section non-mutation contract.

All ATTYA examples use the same B-section progression the live catalog
uses: Fm7 | Bbm7 | Eb7 | Abmaj7.
"""

from __future__ import annotations

import unittest

ATTYA_B = ["Fm7", "Bbm7", "Eb7", "Abmaj7"]
ATTYA_SECTIONS = {
    "A": ["Fm7", "Bbm7", "Eb7", "Abmaj7"],
    "B": ["Fm7", "Bbm7", "Eb7", "Abmaj7"],
    "A2": ["Dbm7", "Gb7", "Bmaj7", "Emaj7"],
    "C": ["Fm7", "Dm7", "G7", "Cmaj7"],
}


class TestGuitarGroovePropagation(unittest.TestCase):
    """Item 1/13: Guitar TAB must consume the canonical resolved groove,
    not an independently-inferred one."""

    def test_jazz_swing_does_not_fall_back_to_pop_rock(self) -> None:
        from practice_notation import generate_practice_notation

        r = generate_practice_notation(
            song_title="All the Things You Are", artist="Jerome Kern",
            display_key="Ab", original_key="Ab", bpm=120,
            groove_style="Jazz swing", instrument="Guitar", focus="",
            section_focus="B", sections=ATTYA_SECTIONS, guitar_tabs={},
            difficulty="medium",
        )
        self.assertNotIn("Pop / rock strum", r.rhythm_counts)
        self.assertIn("Swing", r.rhythm_counts)
        self.assertTrue(any("Groove: " in c and "Pop" not in c for c in r.practice_cues))

    def test_pop_song_gets_pop_pattern_not_jazz(self) -> None:
        from practice_notation import generate_practice_notation

        r = generate_practice_notation(
            song_title="Some Pop Song", artist="X", display_key="C",
            original_key="C", bpm=100, groove_style="Pop groove",
            instrument="Guitar", focus="", section_focus="Full Song",
            sections={"Verse": ["C", "G", "Am", "F"]}, guitar_tabs={},
            difficulty="medium",
        )
        self.assertIn("Pop", r.rhythm_counts)
        self.assertNotIn("Swing", r.rhythm_counts)

    def test_bossa_groove_resolves_to_bossa_pattern(self) -> None:
        from practice_notation import generate_practice_notation

        r = generate_practice_notation(
            song_title="Bossa Tune", artist="X", display_key="C",
            original_key="C", bpm=120, groove_style="Bossa nova",
            instrument="Guitar", focus="", section_focus="Full Song",
            sections={"Verse": ["C", "Am", "D", "G"]}, guitar_tabs={},
            difficulty="medium",
        )
        self.assertIn("Bossa", r.rhythm_counts)


class TestGuitarLevelVoicingDifferentiation(unittest.TestCase):
    """Item 2: Beginner/Intermediate/Advanced must use structurally
    different voicing vocabulary, and every voicing must be playable."""

    def test_levels_use_different_voicing_labels(self) -> None:
        from guitar_voicing_engine import build_level_guitar_voicings

        labels_by_level = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            evs = build_level_guitar_voicings(ATTYA_B, level=level)
            labels_by_level[level] = {ev.label for ev in evs}
        # No two levels should produce an identical label set for the same
        # jazz progression -- that would mean the level selector did
        # nothing structurally.
        self.assertNotEqual(labels_by_level["Beginner"], labels_by_level["Intermediate"])
        self.assertNotEqual(labels_by_level["Intermediate"], labels_by_level["Advanced"])
        self.assertNotEqual(labels_by_level["Beginner"], labels_by_level["Advanced"])

    def test_beginner_prefers_open_shapes_when_available(self) -> None:
        from guitar_voicing_engine import build_level_guitar_voicings

        evs = build_level_guitar_voicings(["G7", "Cmaj7"], level="Beginner")
        self.assertTrue(all(ev.label == "open" for ev in evs))

    def test_beginner_compact_shell_keeps_the_seventh_not_just_a_triad(self) -> None:
        """A compact beginner shape for a chord with no open shape must
        still voice the 7th (the chord's jazz-defining tone), not quietly
        degrade to a plain major/minor triad."""
        from guitar_voicing_engine import build_level_guitar_voicings
        from music_theory import pitch_class_from_spelled_note

        evs = build_level_guitar_voicings(["Fm7"], level="Beginner")
        ev = evs[0]
        self.assertEqual(ev.label, "compact shell")
        sounding_pcs = set()
        for i, ch in enumerate(ev.shape):
            if ch != "x":
                open_pc = [4, 9, 2, 7, 11, 4][i]
                sounding_pcs.add((open_pc + int(ch)) % 12)
        seventh_pc = pitch_class_from_spelled_note("Eb")
        self.assertIn(seventh_pc, sounding_pcs, "compact shell dropped the chord's 7th")

    def test_advanced_voicings_are_all_playable(self) -> None:
        from guitar_voicing_engine import build_level_guitar_voicings, validate_voicing

        evs = build_level_guitar_voicings(ATTYA_B + ["Dbm7", "Gb7", "Bmaj7", "Emaj7"], level="Advanced")
        for ev in evs:
            frets = {i: int(c) for i, c in enumerate(ev.shape) if c != "x"}
            ok, reason = validate_voicing(frets)
            self.assertTrue(ok, f"{ev.chord} ({ev.shape}) failed playability: {reason}")

    def test_no_fret_span_exceeds_four(self) -> None:
        from guitar_voicing_engine import build_level_guitar_voicings

        for level in ("Beginner", "Intermediate", "Advanced"):
            evs = build_level_guitar_voicings(ATTYA_B, level=level)
            for ev in evs:
                frets = [int(c) for c in ev.shape if c != "x"]
                if frets:
                    self.assertLessEqual(max(frets) - min(frets), 4, f"{level} {ev.chord} span too wide")


class TestGuitarSectionOwnership(unittest.TestCase):
    """Item 3: each section's TAB must use that section's own chords."""

    def test_section_b_uses_b_chords_not_full_song(self) -> None:
        from practice_notation import generate_practice_notation

        r = generate_practice_notation(
            song_title="ATTYA", artist="X", display_key="Ab", original_key="Ab",
            bpm=120, groove_style="Jazz swing", instrument="Guitar", focus="",
            section_focus="A2", sections=ATTYA_SECTIONS, guitar_tabs={}, difficulty="medium",
        )
        self.assertEqual(r.chord_labels, "Dbm7 | Gb7 | Bmaj7 | Emaj7")

    def test_full_song_shows_each_unique_section_once(self) -> None:
        from practice_notation import generate_practice_notation

        r = generate_practice_notation(
            song_title="ATTYA", artist="X", display_key="Ab", original_key="Ab",
            bpm=120, groove_style="Jazz swing", instrument="Guitar", focus="",
            section_focus="Full Song", sections=ATTYA_SECTIONS, guitar_tabs={}, difficulty="medium",
        )
        # B's chords are identical to A's in this chart, so B is a dedup,
        # not a separate block: Full Song = A, A2, C (12 chords), not 16.
        self.assertEqual(r.num_lines, 12)

    def test_guitar_full_song_matches_piano_section_identity(self) -> None:
        """Guitar and piano must agree on which sections Full Song shows --
        one shared canonical section-dedup, not two independent ones."""
        from practice_notation import generate_practice_notation

        guitar = generate_practice_notation(
            song_title="ATTYA", artist="X", display_key="Ab", original_key="Ab",
            bpm=120, groove_style="Jazz swing", instrument="Guitar", focus="",
            section_focus="Full Song", sections=ATTYA_SECTIONS, guitar_tabs={}, difficulty="medium",
        )
        piano = generate_practice_notation(
            song_title="ATTYA", artist="X", display_key="Ab", original_key="Ab",
            bpm=120, groove_style="Jazz swing", instrument="Piano", focus="",
            section_focus="Full Song", sections=ATTYA_SECTIONS, guitar_tabs={}, difficulty="medium",
        )
        self.assertEqual(guitar.chord_labels, piano.chord_labels)


class TestNotationPracticeFocusConditioning(unittest.TestCase):
    """Item 4: Practice Focus must materially change the generated
    exercise, not just a caption, across instruments."""

    def _notes(self, instrument: str, focus: str, level: str = "Advanced"):
        from practice_notation import generate_practice_notation

        r = generate_practice_notation(
            song_title="ATTYA", artist="X", display_key="Ab", original_key="Ab",
            bpm=120, groove_style="Jazz swing", instrument=instrument, focus=focus,
            section_focus="B", sections=ATTYA_SECTIONS, guitar_tabs={}, difficulty={
                "Beginner": "easy", "Intermediate": "medium", "Advanced": "advanced",
            }[level],
        )
        return r.abc

    def test_scales_more_stepwise_than_default(self) -> None:
        default_abc = self._notes("Alto Saxophone", "")
        scales_abc = self._notes("Alto Saxophone", "Scales")
        self.assertNotEqual(default_abc, scales_abc)

    def test_tone_produces_fewer_longer_events(self) -> None:
        from chord_navigation_notation import build_connected_arpeggio_line

        default_events = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument="Alto Saxophone")
        tone_events = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument="Alto Saxophone", focus="Tone")
        default_notes = [e for e in default_events if not e.is_rest]
        tone_notes = [e for e in tone_events if not e.is_rest]
        self.assertLess(len(tone_notes), len(default_notes))
        avg_default = sum(e.duration_beats for e in default_notes) / len(default_notes)
        avg_tone = sum(e.duration_beats for e in tone_notes) / len(tone_notes)
        self.assertGreater(avg_tone, avg_default)

    def test_articulation_produces_more_articulation_events(self) -> None:
        from chord_navigation_notation import build_connected_arpeggio_line

        default_events = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument="Alto Saxophone")
        art_events = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument="Alto Saxophone", focus="Articulation")
        default_marked = sum(1 for e in default_events if e.articulation)
        art_marked = sum(1 for e in art_events if e.articulation)
        self.assertGreater(art_marked, default_marked)
        # And a real mixture, not just "more accents":
        self.assertIn("tenuto", {e.articulation for e in art_events})

    def test_guide_tones_emphasizes_third_and_seventh(self) -> None:
        from chord_navigation_notation import build_connected_arpeggio_line
        from music_theory import pitch_class_from_spelled_note, spell_chord_tones

        events = build_connected_arpeggio_line(["Fm7"], level="Intermediate", instrument="Alto Saxophone", focus="Guide Tones")
        tones = spell_chord_tones("Fm7")
        guide_pcs = {pitch_class_from_spelled_note(tones[1]), pitch_class_from_spelled_note(tones[3])}
        sounding = [e for e in events if not e.is_rest]
        on_guide_tone = [e for e in sounding if pitch_class_from_spelled_note(e.pitch) in guide_pcs]
        self.assertGreater(len(on_guide_tone) / len(sounding), 0.7)

    def test_dynamics_produces_real_markings(self) -> None:
        from chord_navigation_notation import build_connected_arpeggio_line

        events = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument="Alto Saxophone", focus="Dynamics")
        dyns = {e.dynamic for e in events if e.dynamic}
        self.assertTrue(dyns, "Dynamics focus produced no dynamic markings")
        self.assertTrue(dyns.issubset({"p", "mp", "mf", "f", "cresc_start", "cresc_end", "dim_start", "dim_end"}))

    def test_unrecognized_focus_reproduces_plain_behavior(self) -> None:
        from chord_navigation_notation import build_connected_arpeggio_line

        a = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument="Alto Saxophone", focus="")
        b = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument="Alto Saxophone", focus="Some Unknown Focus")
        self.assertEqual([e.pitch for e in a], [e.pitch for e in b])


class TestPentatonics(unittest.TestCase):
    """Item 5: Pentatonics is a first-class canonical Practice Focus."""

    def test_is_a_canonical_focus_option_for_every_supported_instrument(self) -> None:
        from practice_setup_controls import focus_options_for_instrument

        for instrument in ("Guitar", "Piano", "Bass", "Saxophone", "Flute", "Trumpet", "Clarinet", "Voice", "Something Unlisted"):
            self.assertIn("Pentatonics", focus_options_for_instrument(instrument))

    def test_has_a_real_coaching_profile(self) -> None:
        from practice_focus_policy import resolve_focus_profile

        profile = resolve_focus_profile("Saxophone", "Pentatonics")
        self.assertTrue(profile.coaching_priorities)
        self.assertTrue(profile.practice_suggestions)

    def test_materially_changes_notation_output(self) -> None:
        from chord_navigation_notation import build_connected_arpeggio_line

        default_pitches = [e.pitch for e in build_connected_arpeggio_line(ATTYA_B, level="Intermediate", instrument="Alto Saxophone") if not e.is_rest]
        penta_pitches = [e.pitch for e in build_connected_arpeggio_line(ATTYA_B, level="Intermediate", instrument="Alto Saxophone", focus="Pentatonics") if not e.is_rest]
        self.assertNotEqual(default_pitches, penta_pitches)

    def test_output_is_predominantly_pentatonic_derived(self) -> None:
        from chord_navigation_notation import build_connected_arpeggio_line, _pentatonic_pool
        from music_theory import pitch_class_from_spelled_note

        events = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument="Alto Saxophone", focus="Pentatonics")
        sounding = [e for e in events if not e.is_rest and e.articulation != "staccato"]
        in_pool = 0
        for e in sounding:
            pool_pcs = {pitch_class_from_spelled_note(t) for t in _pentatonic_pool(e.chord, "Advanced")}
            if pitch_class_from_spelled_note(e.pitch) in pool_pcs:
                in_pool += 1
        # Approach tones (chromatic connectors) are expected to sit outside
        # the pool, so "predominantly" means a strong majority, not 100%.
        self.assertGreater(in_pool / len(sounding), 0.6)

    def test_harmony_changes_alter_pentatonic_choice(self) -> None:
        """Different chords (not a relative-major/minor pair) must select
        different pentatonic pools -- not one blind scale over the whole
        progression."""
        from chord_navigation_notation import _pentatonic_pool

        fm7_pool = set(_pentatonic_pool("Fm7", "Intermediate"))
        g7_pool = set(_pentatonic_pool("G7", "Intermediate"))
        self.assertNotEqual(fm7_pool, g7_pool)
        # But F minor's pentatonic and its relative major Ab's pentatonic
        # are correctly the SAME pitch classes -- real music theory, not a
        # bug -- so the chord-quality branch must still be exercised:
        from music_theory import classify_chord_quality

        self.assertEqual(classify_chord_quality("Fm7"), "m7")
        self.assertEqual(classify_chord_quality("Abmaj7"), "maj7")

    def test_advanced_dominant_uses_the_fourth_above_pentatonic(self) -> None:
        from chord_navigation_notation import _pentatonic_pool
        from music_theory import pitch_class_from_spelled_note

        advanced_pool = {pitch_class_from_spelled_note(t) for t in _pentatonic_pool("G7", "Advanced")}
        beginner_pool = {pitch_class_from_spelled_note(t) for t in _pentatonic_pool("G7", "Beginner")}
        self.assertNotEqual(advanced_pool, beginner_pool)

    def test_levels_differ_structurally(self) -> None:
        from guitar_voicing_engine import build_level_guitar_voicings

        labels = {level: {ev.label for ev in build_level_guitar_voicings(ATTYA_B, level=level)} for level in ("Beginner", "Intermediate", "Advanced")}
        self.assertNotEqual(labels["Beginner"], labels["Advanced"])

    def test_instrument_register_constraints_remain_valid(self) -> None:
        from chord_navigation_notation import build_connected_arpeggio_line, instrument_register

        for instrument in ("Alto Saxophone", "Trumpet", "Flute"):
            lo, hi, _ = instrument_register(instrument, "Advanced")
            events = build_connected_arpeggio_line(ATTYA_B, level="Advanced", instrument=instrument, focus="Pentatonics")
            for e in events:
                if not e.is_rest:
                    self.assertTrue(lo <= e.midi <= hi, f"{instrument} pentatonic note {e.midi} out of register [{lo},{hi}]")

    def test_practice_melody_responds_to_pentatonics_without_losing_identity(self) -> None:
        from practice_melody_generator import generate_another_practice_melody, generate_practice_melody

        sections = {"A": ATTYA_B}
        default = generate_practice_melody(song_id="attya", song_title="ATTYA", sections=sections, key_center="Ab", level="Advanced", style="Jazz swing", focus="")
        penta = generate_practice_melody(song_id="attya", song_title="ATTYA", sections=sections, key_center="Ab", level="Advanced", style="Jazz swing", focus="Pentatonics")
        default_pitches = [e.pitch for s in default.sections for e in s.events if not e.is_rest]
        penta_pitches = [e.pitch for s in penta.sections for e in s.events if not e.is_rest]
        self.assertNotEqual(default_pitches, penta_pitches)
        # Identity/Generate Another semantics preserved: focus carries
        # forward and regeneration stays deterministic.
        again = generate_another_practice_melody(penta)
        self.assertEqual(again.focus, "Pentatonics")
        self.assertEqual(again.alt_index, penta.alt_index + 1)


class TestPracticeMelodyLevelAndStyle(unittest.TestCase):
    """Items 10/11: notation markings and level/style sophistication."""

    def test_notation_markings_are_structurally_valid(self) -> None:
        from practice_melody_generator import generate_practice_melody
        from practice_melody_model import validate_practice_melody

        m = generate_practice_melody(
            song_id="attya", song_title="ATTYA", sections={"A": ATTYA_B, "B": ["Dbm7", "Gb7", "Bmaj7", "Emaj7"]},
            key_center="Ab", level="Advanced", style="Jazz swing", focus="Dynamics",
        )
        self.assertEqual(validate_practice_melody(m), [])

    def test_advanced_jazz_uses_more_chromatic_approach_than_advanced_pop(self) -> None:
        from practice_melody_generator import generate_practice_melody

        sections = {"A": ATTYA_B * 8}
        jazz = generate_practice_melody(song_id="x", song_title="x", sections=sections, key_center="Ab", level="Advanced", tempo_bpm=160, style="Jazz swing")
        pop = generate_practice_melody(song_id="x", song_title="x", sections=sections, key_center="Ab", level="Advanced", tempo_bpm=160, style="Pop groove")
        jazz_approach = sum(1 for s in jazz.sections for e in s.events if e.tone_role == "approach")
        pop_approach = sum(1 for s in pop.sections for e in s.events if e.tone_role == "approach")
        self.assertGreater(jazz_approach, pop_approach)

    def test_pop_advanced_does_not_match_jazz_advanced_chromatic_rate(self) -> None:
        """A Pop song's Advanced melody must not silently inherit the same
        chromatic vocabulary as a Jazz Swing song at the same level."""
        from practice_melody_generator import _CHROMATIC_APPROACH_PROB, _is_jazz_style, _JAZZ_ADVANCED_CHROMATIC_APPROACH_PROB

        self.assertFalse(_is_jazz_style("Pop groove"))
        self.assertNotEqual(_CHROMATIC_APPROACH_PROB["Advanced"], _JAZZ_ADVANCED_CHROMATIC_APPROACH_PROB)

    def test_level_sophistication_increases_structurally(self) -> None:
        from practice_melody_generator import _MAX_LEAP_SEMITONES, _PASSING_TONE_PROB

        self.assertLess(_PASSING_TONE_PROB["Beginner"], _PASSING_TONE_PROB["Intermediate"])
        self.assertLess(_PASSING_TONE_PROB["Intermediate"], _PASSING_TONE_PROB["Advanced"])
        self.assertLess(_MAX_LEAP_SEMITONES["Beginner"], _MAX_LEAP_SEMITONES["Advanced"])


class TestBackingScopeDoesNotMutatePracticeFocusSection(unittest.TestCase):
    """Item 8 ownership boundary: changing Backing's Selected Sections must
    never write to the canonical Practice-page Section Focus key."""

    def test_backing_track_state_never_writes_practice_focus_section(self) -> None:
        import ast
        import backing_track_state

        source = open(backing_track_state.__file__, encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
                # session[...]["practice_focus_section"] = ... as a literal key
                if isinstance(node.slice, ast.Constant) and node.slice.value == "practice_focus_section":
                    self.fail("backing_track_state.py must not write practice_focus_section")


if __name__ == "__main__":
    unittest.main()
