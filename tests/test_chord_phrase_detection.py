"""Tests for chord_phrase_detection — shared phrase grouping logic."""

from __future__ import annotations

import pytest
from chord_phrase_detection import PhraseGroup, detect_chord_phrases, phrase_boundary_set


class TestShortSections:
    """Sections ≤ 4 bars should be a single ungrouped phrase."""

    def test_single_bar(self):
        result = detect_chord_phrases(["C"])
        assert len(result) == 1
        assert result[0] == PhraseGroup(start=0, length=1, label="", repeat_of=None)

    def test_four_bars(self):
        result = detect_chord_phrases(["G", "Am", "C", "D"])
        assert len(result) == 1
        assert result[0].length == 4

    def test_empty(self):
        result = detect_chord_phrases([])
        assert len(result) == 1
        assert result[0].length == 0


class TestAllSameChords:
    """All-identical bars should be one phrase, never split into repeats."""

    def test_eight_identical(self):
        result = detect_chord_phrases(["G"] * 8)
        assert len(result) == 1
        assert result[0].length == 8

    def test_sixteen_identical(self):
        result = detect_chord_phrases(["Em"] * 16)
        assert len(result) == 1
        assert result[0].length == 16


class TestClear4BarRepeat:
    """The most common pattern: a 4-chord sequence repeated N times."""

    def test_4bar_repeated_twice(self):
        chords = ["Bm", "Em", "G", "A"] * 2
        result = detect_chord_phrases(chords)
        assert len(result) == 2
        assert result[0].start == 0
        assert result[0].length == 4
        assert result[0].repeat_of is None
        assert result[1].start == 4
        assert result[1].length == 4
        assert result[1].repeat_of == 0
        assert "repeat" in result[1].label

    def test_4bar_repeated_four_times(self):
        chords = ["Bm", "Em", "G", "A"] * 4
        result = detect_chord_phrases(chords)
        assert len(result) == 4
        assert result[0].repeat_of is None
        assert all(r.repeat_of == 0 for r in result[1:])

    def test_boundary_set(self):
        chords = ["Bm", "Em", "G", "A"] * 4
        result = detect_chord_phrases(chords)
        boundaries = phrase_boundary_set(result)
        assert boundaries == {4, 8, 12}


class TestTwoDistinctPhrases:
    """Two different 4-bar phrases with no repetition."""

    def test_no_repeat_means_no_grouping(self):
        """Without a repeated pattern, 8 bars stays as one phrase."""
        chords = ["C", "Am", "F", "G", "Dm", "Em", "Bb", "C"]
        result = detect_chord_phrases(chords)
        assert len(result) == 1
        assert result[0].length == 8

    def test_abab_pattern(self):
        """A-B-A-B should detect the 4-bar A and B phrases as repeats."""
        phrase_a = ["C", "Am", "F", "G"]
        phrase_b = ["Dm", "Em", "Bb", "C"]
        chords = phrase_a + phrase_b + phrase_a + phrase_b
        result = detect_chord_phrases(chords)
        assert len(result) == 4
        assert result[2].repeat_of == 0
        assert result[3].repeat_of == 1


class TestEightBarPhrases:
    """8-bar phrase repeated."""

    def test_8bar_with_internal_4bar_structure(self):
        """An 8-bar phrase with internal 4-bar sub-phrases: the 4-bar
        grouping is preferred since it reveals more structure."""
        phrase = ["G", "G", "Em7", "Em7", "Cadd9", "Cadd9", "D/F#", "D/F#"]
        chords = phrase * 2
        result = detect_chord_phrases(chords)
        assert len(result) == 4
        assert all(g.length == 4 for g in result)
        assert result[2].repeat_of == 0
        assert result[3].repeat_of == 1

    def test_true_8bar_repeat_when_4bar_has_no_match(self):
        """When 4-bar doesn't produce repeats, 8-bar is used."""
        # 5 distinct 4-bar phrases — no 4-bar repeat, but 10-bar halves repeat
        phrase = ["C", "Am", "F", "G", "Dm", "Em", "Bb", "A7", "Eb", "Db"]
        chords = phrase * 2
        result = detect_chord_phrases(chords)
        # Falls back to half-section (10) since no 4 or 8-bar repeat
        assert any(g.repeat_of is not None for g in result)


class TestOddLengthSections:
    """Sections with non-power-of-2 lengths."""

    def test_nine_bars_no_repeat(self):
        chords = ["C", "D", "Em", "F", "G", "Am", "Bm", "C", "D"]
        result = detect_chord_phrases(chords)
        # No clear repeat — should be single group or conservative grouping
        assert sum(g.length for g in result) == 9

    def test_twelve_bars_three_repeating_4bar(self):
        chords = ["E7", "E7", "A7", "E7"] * 3
        result = detect_chord_phrases(chords)
        assert len(result) == 3
        assert all(g.length == 4 for g in result)


class TestSubdividedBars:
    """Subdivided bar tokens treated as single bars."""

    def test_subdivided_bars_as_single_unit(self):
        chords = ["Dsus4:3|Gadd9:1", "Em", "Dsus4:3|Gadd9:1", "Em",
                   "Dsus4:3|Gadd9:1", "Em", "Dsus4:3|Gadd9:1", "Em"]
        result = detect_chord_phrases(chords)
        assert sum(g.length for g in result) == 8


class TestRemainder:
    """Sections where bars don't evenly divide into phrase lengths."""

    def test_ten_bars_with_4bar_repeats_and_remainder(self):
        chords = ["C", "Am", "F", "G"] * 2 + ["C", "G"]
        result = detect_chord_phrases(chords)
        total = sum(g.length for g in result)
        assert total == 10
        assert result[0].length == 4
        assert result[1].length == 4
        assert result[1].repeat_of == 0


class TestCoverageInvariant:
    """Every bar must be covered by exactly one phrase group."""

    @pytest.mark.parametrize("chords", [
        ["C"] * 8,
        ["Bm", "Em", "G", "A"] * 3,
        ["C", "Am", "F", "G", "Dm", "Em"],
        ["Am", "Dm", "G", "C", "Am", "Dm", "G", "C", "F"],
        [],
        ["C"],
    ])
    def test_full_coverage(self, chords):
        result = detect_chord_phrases(chords)
        covered = set()
        for pg in result:
            for i in range(pg.start, pg.start + pg.length):
                assert i not in covered, f"Bar {i} covered twice"
                covered.add(i)
        assert covered == set(range(len(chords)))


class TestPhraseLabels:
    def test_labels_use_letters(self):
        chords = ["C", "Am", "F", "G", "Dm", "Em", "Bb", "C"]
        result = detect_chord_phrases(chords)
        labels = [g.label for g in result if g.label and "repeat" not in g.label]
        for label in labels:
            assert label.startswith("Phrase ")
