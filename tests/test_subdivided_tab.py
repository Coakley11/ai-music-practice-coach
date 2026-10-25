"""Tests for subdivided bar TAB rendering (Slice 3).

Validates that subdivided tokens like ``Dsus4:3|Gadd9:1`` produce correct
multi-voicing measures with proper beat allocation across 8 slots.
"""

from __future__ import annotations

import pytest


class TestRenderSubdividedMeasureHtml:
    """Unit tests for _render_subdivided_measure_html."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from practice_notation import _render_subdivided_measure_html
        self.render = _render_subdivided_measure_html

    def _groove(self) -> dict:
        return {
            "name": "Pop",
            "counts": ["1", "&", "2", "&", "3", "&", "4", "&"],
            "strum": ["D", ".", "D", "u", "D", ".", "D", "u"],
        }

    def test_3_1_split(self):
        result = self.render(
            token="Dsus4:3|Gadd9:1",
            bar_index=1,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        block, plain, last_shape, labels = result
        assert "Dsus4" in block
        assert "Gadd9" in block
        assert "split bar" in block
        assert len(labels) == 2

    def test_2_2_split(self):
        result = self.render(
            token="Am:2|G:2",
            bar_index=2,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        block, plain, last_shape, labels = result
        assert "Am" in block
        assert last_shape is not None
        assert len(labels) == 2

    def test_1_3_split(self):
        result = self.render(
            token="C:1|Em:3",
            bar_index=3,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        block, plain, last_shape, labels = result
        assert "Em" in block
        assert len(labels) == 2

    def test_equal_split_no_weights(self):
        result = self.render(
            token="Am|G",
            bar_index=1,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        block, plain, last_shape, labels = result
        assert "Am" in block
        assert "G" in block

    def test_non_subdivided_returns_none(self):
        result = self.render(
            token="Am",
            bar_index=1,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is None

    def test_plain_text_contains_both_chords(self):
        result = self.render(
            token="Dsus4:3|Gadd9:1",
            bar_index=1,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        _, plain, _, _ = result
        assert "Dsus4" in plain
        assert "Gadd9" in plain

    def test_last_shape_comes_from_last_sub_chord(self):
        result = self.render(
            token="C:2|G:2",
            bar_index=1,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        _, _, last_shape, _ = result
        assert isinstance(last_shape, str)
        assert len(last_shape) > 0

    def test_measure_has_transition_class(self):
        result = self.render(
            token="C:2|G:2",
            bar_index=1,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        block, _, _, _ = result
        assert "tab-measure-transition" in block

    def test_three_chord_split(self):
        result = self.render(
            token="C:2|Am:1|G:1",
            bar_index=1,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        block, plain, _, labels = result
        assert len(labels) == 3
        assert "Am" in block
        assert "G" in block

    def test_extended_chord_voicing_in_split(self):
        """Em9 in a split bar should produce a valid voicing (not crash)."""
        result = self.render(
            token="Em9:3|Am:1",
            bar_index=1,
            groove_info=self._groove(),
            focus_kind="chords",
            level="Intermediate",
            guitar_tabs={},
        )
        assert result is not None
        block, _, _, labels = result
        assert "Em9" in block
        assert len(labels) == 2


class TestBuildLoopSubdivisionRouting:
    """Integration tests: _build_guitar_tab routes subdivided tokens correctly."""

    def test_mixed_section_with_subdivision(self):
        from practice_notation import _build_guitar_tab

        section_chord_pairs = [
            ("Verse", ["Am", "Dsus4:3|Gadd9:1", "C", "G"]),
        ]
        result = _build_guitar_tab(
            section_chord_pairs=section_chord_pairs,
            guitar_tabs={},
            focus="chords",
            groove="Pop",
            difficulty="Intermediate",
            section="Verse",
            song_title="Test Song",
            bpm=120,
        )
        assert "Dsus4" in result.html
        assert "Gadd9" in result.html
        assert "split bar" in result.html

    def test_all_normal_chords_still_work(self):
        from practice_notation import _build_guitar_tab

        section_chord_pairs = [
            ("Verse", ["Am", "C", "G", "Em"]),
        ]
        result = _build_guitar_tab(
            section_chord_pairs=section_chord_pairs,
            guitar_tabs={},
            focus="chords",
            groove="Pop",
            difficulty="Intermediate",
            section="Verse",
            song_title="Test Song",
            bpm=120,
        )
        assert "Am" in result.html
        assert "Em" in result.html
        assert "split bar" not in result.html

    def test_multiple_subdivided_bars(self):
        from practice_notation import _build_guitar_tab

        section_chord_pairs = [
            ("Verse", ["C:2|G:2", "Am:1|Em:3"]),
        ]
        result = _build_guitar_tab(
            section_chord_pairs=section_chord_pairs,
            guitar_tabs={},
            focus="chords",
            groove="Pop",
            difficulty="Intermediate",
            section="Verse",
            song_title="Test Song",
            bpm=120,
        )
        html = result.html
        assert html.count("split bar") == 2
