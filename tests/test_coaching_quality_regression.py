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
