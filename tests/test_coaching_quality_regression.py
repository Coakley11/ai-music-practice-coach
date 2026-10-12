"""Regression tests for coaching quality improvements.

Verifies that practice plans and section coaching are genuinely differentiated
by skill level, practice focus, and instrument — and that note spelling is
musician-friendly.
"""

from __future__ import annotations

import re

import pytest

from music_theory import friendly_note_name, friendly_note_names


# ---------------------------------------------------------------------------
# Note spelling: B# → C, E# → F, Cb → B, Fb → E
# ---------------------------------------------------------------------------

class TestFriendlyNoteSpelling:
    def test_b_sharp_becomes_c(self):
        assert friendly_note_name("B#") == "C"

    def test_e_sharp_becomes_f(self):
        assert friendly_note_name("E#") == "F"

    def test_cb_becomes_b(self):
        assert friendly_note_name("Cb") == "B"

    def test_fb_becomes_e(self):
        assert friendly_note_name("Fb") == "E"

    def test_normal_notes_unchanged(self):
        for note in ("C", "D", "E", "F", "G", "A", "B", "Bb", "F#", "Ab", "C#"):
            assert friendly_note_name(note) == note

    def test_empty_passthrough(self):
        assert friendly_note_name("") == ""

    def test_batch_friendly_names(self):
        result = friendly_note_names(["B#", "E#", "Cb", "Fb", "C", "D"])
        assert result == ["C", "F", "B", "E", "C", "D"]


# ---------------------------------------------------------------------------
# Focus bucket routing: verify UI focus names map correctly
# ---------------------------------------------------------------------------

class TestFocusBucketRouting:
    @pytest.fixture(autouse=True)
    def _import(self):
        from music_coach_ami.practice_plan_knowledge import _focus_bucket
        self._focus_bucket = _focus_bucket

    @pytest.mark.parametrize("focus,expected", [
        ("Pentatonics", "pentatonics"),
        ("Scales", "pentatonics"),
        ("Guide Tones", "guide_tones"),
        ("Bebop Phrasing", "bebop_phrasing"),
        ("Tone", "tone"),
        ("Articulation", "articulation"),
        ("Rhythm", "timing"),
        ("Dynamics", "dynamics"),
        ("Strumming", "guitar_rhythm"),
        ("Barre Chords", "guitar_rhythm"),
        ("Comping", "harmony"),
        ("Voice Leading", "harmony"),
        ("Voicings", "harmony"),
        ("Inversions", "harmony"),
        ("Soloing", "improvisation"),
        ("Lead Guitar", "improvisation"),
        ("Breath Support", "breath_endurance"),
        ("Endurance", "breath_endurance"),
        ("Range", "breath_endurance"),
        ("Ear Training", "ear_training"),
        ("Pitch Accuracy", "ear_training"),
        ("Syncopation", "timing"),
        ("Groove", "timing"),
        ("Fingerstyle", "fingerstyle"),
        ("Walking Bass", "bass_line"),
        ("Phrasing", "phrasing"),
    ])
    def test_focus_maps_to_correct_bucket(self, focus, expected):
        assert self._focus_bucket(focus) == expected

    def test_general_fallback(self):
        assert self._focus_bucket("") == "general"


# ---------------------------------------------------------------------------
# Practice plan block generation: verify focus-specific content
# ---------------------------------------------------------------------------

class TestPentatonicBlocks:
    @pytest.fixture(autouse=True)
    def _import(self):
        from music_coach_ami.practice_plan_knowledge import _pentatonic_blocks
        self._pentatonic_blocks = _pentatonic_blocks

    def test_beginner_mentions_pentatonic_scale(self):
        weights, details = self._pentatonic_blocks(
            family="wind", level="Beginner", instrument="Saxophone",
            song="Satin Doll", section="Verse",
        )
        all_text = " ".join(details.values()).lower()
        assert "pentatonic" in all_text
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_advanced_mentions_superimposition(self):
        weights, details = self._pentatonic_blocks(
            family="wind", level="Advanced", instrument="Saxophone",
            song="Satin Doll", section="Verse",
        )
        all_text = " ".join(details.values()).lower()
        assert "superimpos" in all_text or "different pentatonic" in all_text

    def test_intermediate_vs_beginner_different_content(self):
        _, details_beg = self._pentatonic_blocks(
            family="fretted", level="Beginner", instrument="Guitar",
            song="Test", section="",
        )
        _, details_int = self._pentatonic_blocks(
            family="fretted", level="Intermediate", instrument="Guitar",
            song="Test", section="",
        )
        assert set(details_beg.keys()) != set(details_int.keys())


class TestGuideToneBlocks:
    @pytest.fixture(autouse=True)
    def _import(self):
        from music_coach_ami.practice_plan_knowledge import _guide_tone_blocks
        self._guide_tone_blocks = _guide_tone_blocks

    def test_beginner_mentions_3rds_and_7ths(self):
        weights, details = self._guide_tone_blocks(
            family="wind", level="Beginner", instrument="Saxophone",
            song="Satin Doll", section="A Section",
        )
        all_text = " ".join(details.values()).lower()
        assert "3rd" in all_text
        assert "7th" in all_text

    def test_advanced_mentions_embellishment(self):
        _, details = self._guide_tone_blocks(
            family="keyboard", level="Advanced", instrument="Piano",
            song="All of Me", section="",
        )
        all_text = " ".join(details.values()).lower()
        assert "embellish" in all_text or "enclosure" in all_text

    def test_keyboard_specific_left_hand_reference(self):
        _, details = self._guide_tone_blocks(
            family="keyboard", level="Beginner", instrument="Piano",
            song="Test", section="",
        )
        all_text = " ".join(details.values()).lower()
        assert "left hand" in all_text or "right hand" in all_text


class TestBebopPhrasingBlocks:
    @pytest.fixture(autouse=True)
    def _import(self):
        from music_coach_ami.practice_plan_knowledge import _bebop_phrasing_blocks
        self._bebop = _bebop_phrasing_blocks

    def test_beginner_mentions_chromatic_passing(self):
        _, details = self._bebop(
            family="wind", level="Beginner", instrument="Saxophone",
            song="Autumn Leaves", section="",
        )
        all_text = " ".join(details.values()).lower()
        assert "chromatic" in all_text

    def test_advanced_mentions_enclosures(self):
        _, details = self._bebop(
            family="wind", level="Advanced", instrument="Saxophone",
            song="Autumn Leaves", section="",
        )
        all_text = " ".join(details.values()).lower()
        assert "enclosure" in all_text


# ---------------------------------------------------------------------------
# Section coaching: focus overlay must appear in output
# ---------------------------------------------------------------------------

class TestSectionCoachingFocusOverlay:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import section_coaching_html
        self._coaching = section_coaching_html

    def _get(self, focus, instrument="Saxophone", level="Intermediate"):
        return self._coaching(
            section_name="Verse",
            instrument=instrument,
            level=level,
            groove_style="Swing",
            bpm=120,
            chords=["Dm7", "G7", "Cmaj7"],
            focus=focus,
        )

    def test_pentatonic_focus_mentions_pentatonic(self):
        result = self._get("Pentatonics")
        assert "pentatonic" in result.lower()

    def test_guide_tone_focus_mentions_3rd_7th(self):
        result = self._get("Guide Tones")
        assert "3rd" in result or "7th" in result

    def test_tone_focus_mentions_tone(self):
        result = self._get("Tone")
        assert "tone" in result.lower()

    def test_articulation_focus_mentions_tongue(self):
        result = self._get("Articulation")
        low = result.lower()
        assert "tongue" in low or "articulation" in low or "attack" in low

    def test_rhythm_focus_mentions_groove(self):
        result = self._get("Rhythm")
        low = result.lower()
        assert "metronome" in low or "groove" in low or "beat" in low or "syncopat" in low

    def test_no_focus_no_overlay(self):
        result = self._get("")
        assert "pentatonic" not in result.lower()
        assert "guide tone" not in result.lower()

    def test_piano_tone_focus_mentions_touch(self):
        result = self._get("Tone", instrument="Piano")
        assert "touch" in result.lower() or "tone" in result.lower()

    def test_guitar_articulation_focus(self):
        result = self._get("Articulation", instrument="Guitar")
        low = result.lower()
        assert "picking" in low or "pluck" in low or "hammer" in low or "attack" in low


# ---------------------------------------------------------------------------
# Skill-level differentiation in section coaching
# ---------------------------------------------------------------------------

class TestSectionCoachingLevelDifferentiation:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import section_coaching_html
        self._coaching = section_coaching_html

    def _get(self, level, instrument="Saxophone"):
        return self._coaching(
            section_name="Verse",
            instrument=instrument,
            level=level,
            groove_style="Swing",
            bpm=120,
            chords=["Dm7", "G7", "Cmaj7"],
        )

    def test_beginner_and_advanced_are_different(self):
        beg = self._get("Beginner")
        adv = self._get("Advanced")
        assert beg != adv

    def test_beginner_saxophone_mentions_basics(self):
        result = self._get("Beginner")
        low = result.lower()
        assert "long tone" in low or "quarter-note" in low or "chord root" in low

    def test_advanced_saxophone_mentions_phrasing(self):
        result = self._get("Advanced")
        low = result.lower()
        assert "phrase" in low or "articulation" in low or "dynamic" in low

    def test_beginner_piano_mentions_root(self):
        result = self._get("Beginner", instrument="Piano")
        assert "root" in result.lower()

    def test_advanced_piano_mentions_voice(self):
        result = self._get("Advanced", instrument="Piano")
        low = result.lower()
        assert "voice" in low or "melody" in low

    def test_beginner_guitar_mentions_strum(self):
        result = self._get("Beginner", instrument="Guitar")
        assert "strum" in result.lower()

    def test_all_three_levels_produce_different_text(self):
        beg = self._get("Beginner", instrument="Piano")
        inter = self._get("Intermediate", instrument="Piano")
        adv = self._get("Advanced", instrument="Piano")
        assert len({beg, inter, adv}) == 3


# ---------------------------------------------------------------------------
# Practice plan timing: block minutes always sum to requested total
# ---------------------------------------------------------------------------

class TestPracticePlanTimingConsistency:
    @pytest.fixture(autouse=True)
    def _import(self):
        from music_coach_ami.practice_plan_knowledge import _allocate
        self._allocate = _allocate

    @pytest.mark.parametrize("total", [15, 20, 30, 45, 60, 90])
    def test_allocation_sums_to_total(self, total):
        weights = {
            "warm-up": 0.15,
            "main work": 0.40,
            "application": 0.30,
            "review": 0.15,
        }
        result = self._allocate(total, weights)
        assert sum(result.values()) == total

    def test_allocation_no_zero_blocks(self):
        result = self._allocate(30, {
            "a": 0.30, "b": 0.25, "c": 0.25, "d": 0.10, "e": 0.10,
        })
        for v in result.values():
            assert v >= 1


# ---------------------------------------------------------------------------
# Instrument specificity: different instruments get different coaching
# ---------------------------------------------------------------------------

class TestInstrumentSpecificCoaching:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import section_coaching_html
        self._coaching = section_coaching_html

    def _get(self, instrument, focus=""):
        return self._coaching(
            section_name="Chorus",
            instrument=instrument,
            level="Intermediate",
            groove_style="Pop groove",
            bpm=120,
            chords=["C", "G", "Am", "F"],
            focus=focus,
        )

    def test_saxophone_and_piano_different(self):
        sax = self._get("Saxophone")
        piano = self._get("Piano")
        assert sax != piano

    def test_guitar_and_bass_different(self):
        guitar = self._get("Guitar")
        bass = self._get("Bass")
        assert guitar != bass

    def test_saxophone_tone_focus_specific(self):
        result = self._get("Saxophone", focus="Tone")
        low = result.lower()
        assert "air" in low or "tone" in low or "register" in low

    def test_piano_guide_tones_specific(self):
        result = self._get("Piano", focus="Guide Tones")
        low = result.lower()
        assert "3rd" in low or "7th" in low


# ---------------------------------------------------------------------------
# Cross-focus regression: the same song with different focuses produces
# different practice content
# ---------------------------------------------------------------------------

class TestCrossFocusVariation:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import section_coaching_html
        self._coaching = section_coaching_html

    def _get(self, focus):
        return self._coaching(
            section_name="Verse",
            instrument="Saxophone",
            level="Intermediate",
            groove_style="Swing",
            bpm=120,
            chords=["Dm7", "G7", "Cmaj7", "Am7"],
            focus=focus,
        )

    def test_pentatonics_vs_guide_tones(self):
        pent = self._get("Pentatonics")
        guide = self._get("Guide Tones")
        assert pent != guide
        assert "pentatonic" in pent.lower()
        assert "3rd" in guide or "7th" in guide

    def test_tone_vs_rhythm(self):
        tone = self._get("Tone")
        rhythm = self._get("Rhythm")
        assert tone != rhythm

    def test_articulation_vs_dynamics(self):
        artic = self._get("Articulation")
        dyn = self._get("Dynamics")
        assert artic != dyn


# ---------------------------------------------------------------------------
# Friendly chord spelling in coaching output
# ---------------------------------------------------------------------------

class TestFriendlyChordSpelling:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import _friendly_chord
        self._friendly_chord = _friendly_chord

    def test_b_sharp_root(self):
        assert self._friendly_chord("B#maj7") == "Cmaj7"

    def test_e_sharp_root(self):
        assert self._friendly_chord("E#7") == "F7"

    def test_cb_root(self):
        assert self._friendly_chord("Cb") == "B"

    def test_fb_root(self):
        assert self._friendly_chord("Fbm7") == "Em7"

    def test_normal_chord_unchanged(self):
        assert self._friendly_chord("Dm7") == "Dm7"
        assert self._friendly_chord("G7") == "G7"
        assert self._friendly_chord("Bbmaj7") == "Bbmaj7"


# ---------------------------------------------------------------------------
# Curated profile bypass: focus overlay must still appear
# ---------------------------------------------------------------------------

class TestCuratedProfileFocusOverlay:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import section_coaching_html
        self._coaching = section_coaching_html

    def test_curated_song_with_focus_includes_overlay(self):
        from song_performance_profiles import CURATED_PERFORMANCE
        if not CURATED_PERFORMANCE:
            pytest.skip("No curated profiles to test")
        first_key = next(iter(CURATED_PERFORMANCE))
        title = first_key.replace("_", " ").title()
        result = self._coaching(
            section_name="Verse",
            instrument="Saxophone",
            level="Intermediate",
            groove_style="Pop groove",
            bpm=120,
            chords=["C", "G", "Am", "F"],
            focus="Pentatonics",
            title=title,
        )
        assert "pentatonic" in result.lower()


# ---------------------------------------------------------------------------
# Focus practice line for Practice Coach markdown
# ---------------------------------------------------------------------------

class TestFocusPracticeLine:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import _focus_practice_line
        self._focus_line = _focus_practice_line

    def test_pentatonic_beginner(self):
        result = self._focus_line("Pentatonics", "Saxophone", "Beginner")
        assert "pentatonic" in result.lower()
        assert "Today's focus" in result

    def test_guide_tones_advanced(self):
        result = self._focus_line("Guide Tones", "Piano", "Advanced")
        assert "guide-tone" in result.lower() or "guide tone" in result.lower()

    def test_tone_saxophone(self):
        result = self._focus_line("Tone", "Saxophone", "Intermediate")
        assert "tone" in result.lower()

    def test_rhythm_intermediate(self):
        result = self._focus_line("Rhythm", "Guitar", "Intermediate")
        assert "metronome" in result.lower() or "groove" in result.lower()

    def test_empty_focus_returns_empty(self):
        result = self._focus_line("", "Saxophone", "Intermediate")
        assert result == ""

    def test_dynamics_beginner(self):
        result = self._focus_line("Dynamics", "Piano", "Beginner")
        assert "dynamic" in result.lower()

    def test_bebop_advanced(self):
        result = self._focus_line("Bebop Phrasing", "Saxophone", "Advanced")
        assert "bebop" in result.lower()

    def test_ear_training(self):
        result = self._focus_line("Ear Training", "Guitar", "Intermediate")
        assert "ear" in result.lower()

    def test_walking_bass(self):
        result = self._focus_line("Walking Bass", "Bass", "Intermediate")
        assert "walking" in result.lower()


# ---------------------------------------------------------------------------
# Phase 2: Concrete chord-tone content in guide-tone utilities
# ---------------------------------------------------------------------------

class TestGuideToneUtilities:
    @pytest.fixture(autouse=True)
    def _import(self):
        from music_theory import guide_tones_for_chord, guide_tone_voice_leading
        self._gt = guide_tones_for_chord
        self._vl = guide_tone_voice_leading

    def test_dm7_guide_tones(self):
        root, third, seventh = self._gt("Dm7")
        assert root == "D"
        assert third == "F"
        assert seventh == "C"

    def test_g7_guide_tones(self):
        root, third, seventh = self._gt("G7")
        assert root == "G"
        assert third == "B"
        assert seventh == "F"

    def test_cmaj7_guide_tones(self):
        root, third, seventh = self._gt("Cmaj7")
        assert root == "C"
        assert third == "E"
        assert seventh == "B"

    def test_triad_has_empty_seventh(self):
        root, third, seventh = self._gt("C")
        assert root == "C"
        assert third == "E"
        assert seventh == ""

    def test_friendly_spelling_applied(self):
        root, third, seventh = self._gt("B#m7")
        assert root == "C"

    def test_voice_leading_chain(self):
        result = self._vl(["Dm7", "G7", "Cmaj7"])
        assert len(result) == 3
        assert result[0]["voice_lead"] == ""
        assert result[1]["voice_lead"] == "C -> B"
        assert result[2]["voice_lead"] == "F -> E"

    def test_voice_leading_empty_list(self):
        assert self._vl([]) == []


# ---------------------------------------------------------------------------
# Phase 2: Section coaching overlay with chord-specific content
# ---------------------------------------------------------------------------

class TestOverlayChordContent:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import section_coaching_html
        self._html = section_coaching_html

    def _overlay(self, focus, level="Intermediate", chords=None):
        return self._html(
            section_name="A Section",
            instrument="Saxophone",
            level=level,
            groove_style="Swing",
            bpm=120,
            chords=chords or ["Dm7", "G7", "Cmaj7"],
            focus=focus,
            title="Test Song",
        )

    def test_guide_tones_beginner_has_note_names(self):
        text = self._overlay("Guide Tones", level="Beginner")
        assert "F" in text and "C" in text

    def test_guide_tones_intermediate_has_voice_leading(self):
        text = self._overlay("Guide Tones", level="Intermediate")
        assert "->" in text

    def test_guide_tones_advanced_has_enclosures(self):
        text = self._overlay("Guide Tones", level="Advanced")
        assert "enclosure" in text.lower() or "chromatic" in text.lower()

    def test_pentatonics_has_root_names(self):
        text = self._overlay("Pentatonics")
        assert "D" in text or "root" in text.lower()

    def test_bebop_has_guide_tone_targets(self):
        text = self._overlay("Bebop Phrasing")
        assert "Dm7" in text or "guide tone" in text.lower() or "3rd" in text.lower()

    def test_three_levels_produce_different_guide_tone_text(self):
        beg = self._overlay("Guide Tones", level="Beginner")
        mid = self._overlay("Guide Tones", level="Intermediate")
        adv = self._overlay("Guide Tones", level="Advanced")
        assert len({beg, mid, adv}) == 3


# ---------------------------------------------------------------------------
# Phase 3: Curated coaching must not leak to wrong instruments
# ---------------------------------------------------------------------------

class TestCuratedCoachingInstrumentMatch:
    """Curated song lessons (e.g. Perfect/piano) must not leak to other instruments."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import section_coaching_html
        self._html = section_coaching_html

    def _coaching(self, instrument, **kw):
        defaults = dict(
            section_name="Verse", level="Intermediate",
            groove_style="Pop groove", bpm=120,
            chords=["G", "Em", "C", "D"], focus="", title="Perfect",
        )
        defaults.update(kw)
        defaults["instrument"] = instrument
        return self._html(**defaults)

    def test_voice_no_piano_text(self):
        text = self._coaching("Voice")
        assert "broken chord" not in text.lower()
        assert "roll" not in text.lower().split(".")[0]

    def test_voice_gets_voice_advice(self):
        text = self._coaching("Voice")
        assert "lyric" in text.lower() or "breath" in text.lower() or "vowel" in text.lower()

    def test_saxophone_no_piano_text(self):
        text = self._coaching("Saxophone")
        assert "broken chord" not in text.lower()
        assert "left hand" not in text.lower()

    def test_saxophone_gets_wind_advice(self):
        text = self._coaching("Saxophone")
        assert "phrase" in text.lower() or "tonguing" in text.lower() or "air" in text.lower()

    def test_bass_no_piano_text(self):
        text = self._coaching("Bass")
        assert "broken chord" not in text.lower()

    def test_piano_keeps_curated(self):
        text = self._coaching("Piano")
        assert "broken chord" in text.lower() or "roll" in text.lower()

    def test_guitar_keeps_curated(self):
        text = self._coaching("Guitar")
        assert "bass" in text.lower() or "accent" in text.lower() or "fingerpick" in text.lower()

    def test_voice_breath_focus_has_content(self):
        text = self._coaching("Voice", focus="Breath Support")
        assert "breath" in text.lower()

    def test_voice_breath_practice_line(self):
        from musician_coaching import _focus_practice_line
        line = _focus_practice_line("Breath Support", "Voice", "Intermediate")
        assert "Breath" in line
        assert len(line) > 20


# ---------------------------------------------------------------------------
# Phase 2: Practice Coach focus line with chord data
# ---------------------------------------------------------------------------

class TestFocusLineWithChords:
    @pytest.fixture(autouse=True)
    def _import(self):
        from musician_coaching import _focus_practice_line
        self._line = _focus_practice_line

    def test_guide_tones_beginner_with_chords(self):
        result = self._line("Guide Tones", "Saxophone", "Beginner",
                            chords=["Dm7", "G7", "Cmaj7"])
        assert "Dm7: F and C" in result
        assert "C -> B" in result

    def test_guide_tones_intermediate_with_chords(self):
        result = self._line("Guide Tones", "Saxophone", "Intermediate",
                            chords=["Dm7", "G7", "Cmaj7"])
        assert "Guide tones:" in result
        assert "Start with:" in result

    def test_guide_tones_advanced_with_chords(self):
        result = self._line("Guide Tones", "Saxophone", "Advanced",
                            chords=["Dm7", "G7", "Cmaj7"])
        assert "Voice-leading path:" in result

    def test_pentatonics_with_chords_shows_roots(self):
        result = self._line("Pentatonics", "Saxophone", "Intermediate",
                            chords=["Dm7", "G7", "Cmaj7"])
        assert "Chord roots:" in result
        assert "D" in result

    def test_bebop_with_chords_shows_targets(self):
        result = self._line("Bebop Phrasing", "Saxophone", "Intermediate",
                            chords=["Dm7", "G7", "Cmaj7"])
        assert "Target:" in result or "guide tone" in result.lower()

    def test_no_chords_still_works(self):
        result = self._line("Guide Tones", "Saxophone", "Beginner")
        assert "Guide Tones" in result
        assert "Dm7" not in result

    def test_tone_focus_unchanged_by_chords(self):
        without = self._line("Tone", "Saxophone", "Intermediate")
        with_ch = self._line("Tone", "Saxophone", "Intermediate",
                             chords=["Dm7", "G7"])
        assert without == with_ch


# ---------------------------------------------------------------------------
# Phase 2: Practice plan blocks with chord data
# ---------------------------------------------------------------------------

class TestPracticePlanWithChords:
    @pytest.fixture(autouse=True)
    def _import(self):
        from music_coach_ami.practice_plan_knowledge import (
            _guide_tone_blocks, _pentatonic_blocks, _bebop_phrasing_blocks,
        )
        self._gt_blocks = _guide_tone_blocks
        self._pent_blocks = _pentatonic_blocks
        self._bebop_blocks = _bebop_phrasing_blocks

    def test_guide_tone_blocks_with_chords_have_note_names(self):
        _, details = self._gt_blocks(
            family="wind", level="Intermediate", instrument="Saxophone",
            song="Satin Doll", section="A Section",
            chords=["Dm7", "G7", "Cmaj7"],
        )
        all_text = " ".join(details.values())
        assert "F" in all_text
        assert "C" in all_text
        assert "->" in all_text

    def test_guide_tone_blocks_beginner_simpler(self):
        _, det_beg = self._gt_blocks(
            family="wind", level="Beginner", instrument="Saxophone",
            song="Test", section="A",
            chords=["Dm7", "G7"],
        )
        _, det_adv = self._gt_blocks(
            family="wind", level="Advanced", instrument="Saxophone",
            song="Test", section="A",
            chords=["Dm7", "G7"],
        )
        text_beg = " ".join(det_beg.values()).lower()
        text_adv = " ".join(det_adv.values()).lower()
        assert "whole note" in text_beg or "hold" in text_beg
        assert "enclosure" in text_adv or "embellish" in text_adv

    def test_pentatonic_blocks_with_chords_have_roots(self):
        _, details = self._pent_blocks(
            family="wind", level="Intermediate", instrument="Saxophone",
            song="Satin Doll", section="A Section",
            chords=["Dm7", "G7", "Em7", "A7"],
        )
        all_text = " ".join(details.values())
        assert "D" in all_text or "root" in all_text.lower()

    def test_bebop_blocks_with_chords_have_guide_tones(self):
        _, details = self._bebop_blocks(
            family="wind", level="Intermediate", instrument="Saxophone",
            song="Satin Doll", section="A Section",
            chords=["Dm7", "G7", "Cmaj7"],
        )
        all_text = " ".join(details.values())
        assert "F" in all_text or "3rd" in all_text.lower()

    def test_blocks_without_chords_still_work(self):
        weights, details = self._gt_blocks(
            family="wind", level="Intermediate", instrument="Saxophone",
            song="Test", section="",
        )
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
        assert len(details) > 0


# ---------------------------------------------------------------------------
# Phase 2: Progress checks reference actual chords
# ---------------------------------------------------------------------------

class TestProgressChecksWithChords:
    @pytest.fixture(autouse=True)
    def _import(self):
        from music_coach_ami.practice_plan_knowledge import _focus_listen_and_progression
        self._listen = _focus_listen_and_progression

    def test_guide_tones_listen_mentions_chords(self):
        listen, _ = self._listen("guide_tones", chords=["Dm7", "G7"])
        all_text = " ".join(listen)
        assert "Dm7" in all_text or "G7" in all_text

    def test_pentatonics_listen_mentions_chords(self):
        listen, _ = self._listen("pentatonics", chords=["Dm7", "G7"])
        all_text = " ".join(listen)
        assert "Dm7" in all_text or "G7" in all_text

    def test_bebop_listen_mentions_chords(self):
        listen, _ = self._listen("bebop_phrasing", chords=["Dm7", "G7"])
        all_text = " ".join(listen)
        assert "Dm7" in all_text or "G7" in all_text

    def test_no_chords_still_works(self):
        listen, progression = self._listen("guide_tones")
        assert len(listen) > 0
        assert len(progression) > 0


# ---------------------------------------------------------------------------
# Phase 3: Session exercise (song_practice_plan) via AST-extracted functions
# ---------------------------------------------------------------------------

def _load_session_exercise_fn():
    """Extract song_practice_plan and its dependencies from the app source."""
    import ast, types as _types

    app_path = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "streamlit_music_practice_app.py"
    )
    source = app_path.read_text(encoding="utf-8")
    source_lines = source.splitlines(keepends=True)
    tree = ast.parse(source)

    top_funcs = [
        n for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    func_src = {}
    for node in top_funcs:
        func_src[node.name] = "".join(source_lines[node.lineno - 1 : node.end_lineno])

    ns = {"__builtins__": __builtins__}
    exec("import html, re, math", ns)
    exec(
        "from music_theory import spell_chord_tones, friendly_note_name, "
        "guide_tones_for_chord, guide_tone_voice_leading",
        ns,
    )
    try:
        exec("from backing_audio import bass_note, chord_notes", ns)
    except ImportError:
        ns["bass_note"] = lambda c: 60
        ns["chord_notes"] = lambda c: [60, 64, 67, 70]
    try:
        exec("from improvisation_motif import chord_tone_names as _lib_chord_tone_names", ns)
    except Exception:
        ns["_lib_chord_tone_names"] = lambda c: "root - 3rd - 5th"

    ns["st"] = _types.SimpleNamespace(session_state={"backing_track_bpm": 120})
    ns["default_time_signature"] = lambda song, sections: "4/4"

    for node in top_funcs:
        try:
            exec(func_src[node.name], ns)
        except Exception:
            pass
    # Retry skipped
    for node in top_funcs:
        if node.name not in ns:
            try:
                exec(func_src[node.name], ns)
            except Exception:
                pass

    ns["default_time_signature"] = lambda song, sections: "4/4"
    ns["_resolve_groove_override"] = lambda g: g or "Swing"

    return ns["song_practice_plan"], ns.get("_focus_area"), ns.get("_vl_text_for_drills")


_session_fn, _focus_area_fn, _vl_fn = _load_session_exercise_fn()

SATIN_DOLL_A = ["Dm7", "G7", "Dm7", "G7", "Em7", "A7", "Em7", "A7"]


class TestSessionExerciseFocusArea:
    """_focus_area routes UI focus names to specific drill categories."""

    def test_guide_tones(self):
        assert _focus_area_fn("Guide Tones") == "Guide Tones"

    def test_pentatonics(self):
        assert _focus_area_fn("Pentatonics") == "Pentatonics"

    def test_bebop(self):
        assert _focus_area_fn("Bebop Phrasing") == "Bebop"

    def test_tone(self):
        assert _focus_area_fn("Tone") == "Tone"

    def test_articulation(self):
        assert _focus_area_fn("Articulation") == "Articulation"

    def test_breath(self):
        assert _focus_area_fn("Breath Support") == "Breath"

    def test_strumming(self):
        assert _focus_area_fn("Strumming") == "Rhythm"

    def test_dynamics(self):
        assert _focus_area_fn("Dynamics") == "Dynamics"

    def test_voicings(self):
        assert _focus_area_fn("Voicings") == "Harmony"

    def test_soloing(self):
        assert _focus_area_fn("Soloing") == "Improvisation"

    def test_ear_training(self):
        assert _focus_area_fn("Ear Training") == "Ear Training"

    def test_fingerstyle(self):
        assert _focus_area_fn("Fingerstyle") == "Technique"


class TestSessionExerciseVoiceLeading:
    """_vl_text_for_drills produces concrete guide-tone data."""

    def test_gt_list_populated(self):
        vl = _vl_fn(SATIN_DOLL_A, 4)
        assert vl.get("gt_list")
        assert "Dm7" in vl["gt_list"]

    def test_gt_list_has_intervals(self):
        vl = _vl_fn(SATIN_DOLL_A, 4)
        assert "3rd" in vl["gt_list"]
        assert "7th" in vl["gt_list"]

    def test_voice_leading_populated(self):
        vl = _vl_fn(SATIN_DOLL_A, 4)
        assert vl.get("first_vl")
        assert "->" in vl["first_vl"]

    def test_root_list_populated(self):
        vl = _vl_fn(SATIN_DOLL_A, 4)
        assert vl.get("root_list")
        assert "D" in vl["root_list"]

    def test_empty_chords(self):
        vl = _vl_fn([], 4)
        assert vl == {}


class TestSessionExerciseGuideTones:
    """Session exercise with Guide Tones focus produces concrete content."""

    @staticmethod
    def _exercise(level, chords=None):
        return _session_fn(
            "Satin Doll",
            {"A Section": chords or SATIN_DOLL_A},
            "Saxophone", level, "Guide Tones", 0, minutes=30,
        )

    def test_beginner_has_guide_tone_content(self):
        ex = self._exercise("Beginner")
        assert "3rd" in ex or "7th" in ex or "guide" in ex.lower()

    def test_beginner_has_note_names(self):
        ex = self._exercise("Beginner")
        assert any(n in ex for n in ("F", "C", "B"))

    def test_intermediate_has_voice_leading(self):
        ex = self._exercise("Intermediate")
        assert "->" in ex or "resolve" in ex.lower()

    def test_advanced_different_from_beginner(self):
        beg = self._exercise("Beginner")
        adv = self._exercise("Advanced")
        assert beg != adv

    def test_all_three_levels_unique(self):
        exercises = {self._exercise(lv) for lv in ("Beginner", "Intermediate", "Advanced")}
        assert len(exercises) == 3

    def test_has_chord_references(self):
        ex = self._exercise("Intermediate")
        assert "Dm7" in ex


class TestSessionExercisePentatonics:
    """Session exercise with Pentatonics focus."""

    def test_pentatonic_content(self):
        ex = _session_fn(
            "Satin Doll", {"A Section": SATIN_DOLL_A},
            "Saxophone", "Intermediate", "Pentatonics", 0, minutes=30,
        )
        assert "pentatonic" in ex.lower()

    def test_has_root_names(self):
        ex = _session_fn(
            "Satin Doll", {"A Section": SATIN_DOLL_A},
            "Saxophone", "Intermediate", "Pentatonics", 0, minutes=30,
        )
        assert "D" in ex


class TestSessionExerciseTone:
    """Session exercise with Tone focus."""

    def test_tone_content(self):
        ex = _session_fn(
            "Satin Doll", {"Bridge": ["Gm7", "C7", "Fmaj7"]},
            "Saxophone", "Intermediate", "Tone", 0, minutes=30,
        )
        low = ex.lower()
        assert "tone" in low or "sustain" in low or "centered" in low

    def test_has_chord_tones(self):
        ex = _session_fn(
            "Satin Doll", {"Bridge": ["Gm7", "C7", "Fmaj7"]},
            "Saxophone", "Intermediate", "Tone", 0, minutes=30,
        )
        assert "Gm7" in ex


class TestSessionExerciseBreath:
    """Session exercise with Breath focus for voice."""

    def test_breath_content(self):
        ex = _session_fn(
            "Perfect", {"Verse": ["G", "Em", "C", "D"]},
            "Voice", "Intermediate", "Breath Support", 0, minutes=30,
        )
        assert "breath" in ex.lower()


class TestSessionExerciseEdgeCases:
    """Edge cases for Session exercise."""

    def test_no_chords_graceful(self):
        ex = _session_fn(
            "Unknown Song", {}, "Saxophone", "Intermediate", "Guide Tones", 0, minutes=30,
        )
        assert len(ex.strip()) > 20

    def test_guitar_strumming(self):
        ex = _session_fn(
            "Perfect", {"Verse": ["G", "Em", "C", "D"]},
            "Guitar", "Beginner", "Strumming", 0, minutes=30,
        )
        low = ex.lower()
        assert "strum" in low or "bass" in low or "accent" in low or "guitar" in low

    def test_piano_pentatonics(self):
        ex = _session_fn(
            "All of Me", {"Verse": ["Cmaj7", "C7", "Fmaj7", "Fm7"]},
            "Piano", "Advanced", "Pentatonics", 0, minutes=30,
        )
        assert "pentatonic" in ex.lower()
