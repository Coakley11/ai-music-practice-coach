"""Issue 19: the song-source icon comes from the canonical source identity."""

from __future__ import annotations

import unittest
from unittest import mock
from unittest.mock import MagicMock

import app_ui
from music_feature_icons import FEATURE_ICONS


def _composition_session() -> dict:
    from composition_document import apply_section_chords, new_composition_document, ordered_sections
    from composition_songs_bridge import commit_composition_active_song, set_composition_source

    doc = new_composition_document(title="My Composition")
    sid = str(ordered_sections(doc)[0]["id"])
    apply_section_chords(doc, sid, [{"chord": "E", "bars": 1}])
    ss: dict = {"instrument": "Piano", "composer_saved_compositions": {}, "display_key": "E"}
    st = MagicMock()
    st.session_state = ss
    set_composition_source(ss)
    commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
    return ss


class TestIconMapping(unittest.TestCase):
    def test_each_source_gets_its_own_icon(self) -> None:
        comp = app_ui.song_source_icon_parts("Composed Song")
        cust = app_ui.song_source_icon_parts("Custom Song")
        cat = app_ui.song_source_icon_parts("Catalog Song")
        self.assertIn(FEATURE_ICONS["composition"], comp[0])
        self.assertEqual(comp[1], "source-composition")
        self.assertIn(FEATURE_ICONS["custom"], cust[0])
        self.assertEqual(cust[1], "source-custom")
        self.assertEqual(cat[:2], ("\U0001f3b5", "source-catalog"))
        self.assertEqual(len({comp[0], cust[0], cat[0]}), 3)

    def test_unknown_or_empty_falls_back_to_catalog(self) -> None:
        self.assertEqual(app_ui.song_source_icon_parts("")[1], "source-catalog")
        self.assertEqual(app_ui.song_source_icon_parts("Other / Not a Song")[1], "source-catalog")


class TestBadgeFollowsTheActiveSource(unittest.TestCase):
    def test_a_real_active_composition_gets_the_quill_not_the_catalog_note(self) -> None:
        ss = _composition_session()
        icon, cls, title = app_ui._multitrack_active_source_badge_parts(ss)
        self.assertEqual(cls, "source-composition", (icon, title))
        self.assertIn(FEATURE_ICONS["composition"], icon)

    def test_the_badge_reads_the_resolvers_real_key(self) -> None:
        for resolved, want in (
            ({"song_source_type": "Composed Song"}, "source-composition"),
            ({"song_source_type": "Custom Song"}, "source-custom"),
            ({"song_source_type": "Catalog Song"}, "source-catalog"),
        ):
            with mock.patch("recording_analysis_context.resolve_active_song_source", return_value=resolved):
                self.assertEqual(app_ui._multitrack_active_source_badge_parts({})[1], want)

    def test_the_icon_ignores_the_song_title(self) -> None:
        with mock.patch(
            "recording_analysis_context.resolve_active_song_source",
            return_value={"song_source_type": "Catalog Song", "song_source_name": "My Composition"},
        ):
            self.assertEqual(app_ui._multitrack_active_source_badge_parts({})[1], "source-catalog")

    def test_switching_sources_changes_the_icon_without_touching_the_data(self) -> None:
        ss = _composition_session()
        before = dict(ss)
        first = app_ui._multitrack_active_source_badge_parts(ss)[1]
        with mock.patch("recording_analysis_context.resolve_active_song_source", return_value={"song_source_type": "Custom Song"}):
            second = app_ui._multitrack_active_source_badge_parts(ss)[1]
        third = app_ui._multitrack_active_source_badge_parts(ss)[1]
        self.assertEqual((first, second, third), ("source-composition", "source-custom", "source-composition"))
        self.assertEqual(ss.keys(), before.keys())


if __name__ == "__main__":
    unittest.main()
