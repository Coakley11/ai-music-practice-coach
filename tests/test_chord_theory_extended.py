"""Tests for extended chord spelling — 9th, 11th, 13th, and add chords.

Validates that _chord_letter_interval_spec and spell_chord_tones correctly
handle extended harmony without breaking existing triad and seventh-chord
behavior.
"""

from __future__ import annotations

import pytest
from music_theory import spell_chord_tones, pitch_class_from_spelled_note


class TestNinthChords:
    """The four screenshot chords plus other 9th variants."""

    def test_em9(self):
        tones = spell_chord_tones("Em9")
        assert tones == ["E", "G", "B", "D", "F#"]

    def test_gadd9(self):
        tones = spell_chord_tones("Gadd9")
        assert tones == ["G", "B", "D", "A"]

    def test_cmaj9(self):
        tones = spell_chord_tones("Cmaj9")
        assert tones == ["C", "E", "G", "B", "D"]

    def test_dsus4(self):
        tones = spell_chord_tones("Dsus4")
        assert tones == ["D", "G", "A"]

    def test_dominant_9(self):
        tones = spell_chord_tones("D9")
        assert tones == ["D", "F#", "A", "C", "E"]

    def test_dm9(self):
        tones = spell_chord_tones("Dm9")
        assert tones == ["D", "F", "A", "C", "E"]

    def test_cadd9(self):
        tones = spell_chord_tones("Cadd9")
        assert tones == ["C", "E", "G", "D"]

    def test_fsharp_m9(self):
        tones = spell_chord_tones("F#m9")
        assert tones[0] == "F#"
        assert len(tones) == 5

    def test_bbadd9(self):
        tones = spell_chord_tones("Bbadd9")
        assert tones[0] == "Bb"
        assert len(tones) == 4


class TestEleventhChords:
    def test_g11(self):
        tones = spell_chord_tones("G11")
        assert len(tones) == 6
        pcs = [pitch_class_from_spelled_note(t) for t in tones]
        assert 7 in pcs   # G root
        assert 11 in pcs  # B 3rd
        assert 2 in pcs   # D 5th
        assert 5 in pcs   # F b7
        assert 9 in pcs   # A 9th
        assert 0 in pcs   # C 11th

    def test_am11(self):
        tones = spell_chord_tones("Am11")
        assert len(tones) == 6


class TestThirteenthChords:
    def test_c13(self):
        tones = spell_chord_tones("C13")
        assert len(tones) == 6
        pcs = [pitch_class_from_spelled_note(t) for t in tones]
        assert 0 in pcs   # C root
        assert 4 in pcs   # E 3rd
        assert 7 in pcs   # G 5th
        assert 10 in pcs  # Bb b7
        assert 2 in pcs   # D 9th
        assert 9 in pcs   # A 13th

    def test_cmaj13(self):
        tones = spell_chord_tones("Cmaj13")
        assert len(tones) == 6


class TestExistingChordsUnchanged:
    """Existing triad and seventh chord behavior must be preserved."""

    @pytest.mark.parametrize("chord,expected", [
        ("C",     ["C", "E", "G"]),
        ("Am",    ["A", "C", "E"]),
        ("G7",    ["G", "B", "D", "F"]),
        ("Am7",   ["A", "C", "E", "G"]),
        ("Fmaj7", ["F", "A", "C", "E"]),
        ("Dm",    ["D", "F", "A"]),
        ("E",     ["E", "G#", "B"]),
        ("Bb",    ["Bb", "D", "F"]),
        ("F#m7",  ["F#", "A", "C#", "E"]),
        ("Bdim",  ["B", "D", "F"]),
        ("Caug",  ["C", "E", "G#"]),
        ("Dsus2", ["D", "E", "A"]),
        ("Gsus4", ["G", "C", "D"]),
    ])
    def test_unchanged(self, chord, expected):
        assert spell_chord_tones(chord) == expected


class TestToneCount:
    """Verify correct tone counts by chord type."""

    @pytest.mark.parametrize("chord,count", [
        ("C", 3),
        ("Am7", 4),
        ("Cadd9", 4),
        ("Em9", 5),
        ("Cmaj9", 5),
        ("D9", 5),
        ("G11", 6),
        ("C13", 6),
    ])
    def test_tone_count(self, chord, count):
        assert len(spell_chord_tones(chord)) == count


class TestAdd9VsNinth:
    """add9 has no 7th; 9th chords include the 7th."""

    def test_add9_has_no_seventh(self):
        tones = spell_chord_tones("Cadd9")
        pcs = {pitch_class_from_spelled_note(t) for t in tones}
        assert 10 not in pcs  # no Bb (dominant 7th)
        assert 11 not in pcs  # no B (major 7th)

    def test_9_has_dominant_seventh(self):
        tones = spell_chord_tones("C9")
        pcs = {pitch_class_from_spelled_note(t) for t in tones}
        assert 10 in pcs  # Bb (dominant 7th)

    def test_maj9_has_major_seventh(self):
        tones = spell_chord_tones("Cmaj9")
        pcs = {pitch_class_from_spelled_note(t) for t in tones}
        assert 11 in pcs  # B (major 7th)

    def test_m9_has_minor_seventh(self):
        tones = spell_chord_tones("Cm9")
        pcs = {pitch_class_from_spelled_note(t) for t in tones}
        assert 10 in pcs  # Bb (minor/dominant 7th)
        assert 3 in pcs   # Eb (minor 3rd)


class TestRootSpellingPreserved:
    """Sharp/flat root spelling from the chord symbol must be kept."""

    def test_fsharp_root(self):
        tones = spell_chord_tones("F#m9")
        assert tones[0] == "F#"

    def test_bb_root(self):
        tones = spell_chord_tones("Bb9")
        assert tones[0] == "Bb"

    def test_eb_root(self):
        tones = spell_chord_tones("Ebmaj9")
        assert tones[0] == "Eb"
