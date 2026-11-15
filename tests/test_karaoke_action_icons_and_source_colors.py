"""Karaoke Group A: the transport buttons say what they do, and a row says where it came from.

Part 6. "End Karaoke Set" read as a heading - a label saying where the set ends rather than a
button that stops it - and Clear Setlist carried nothing at all, so the two most consequential
controls on the panel were the two with no symbol. Start wore the karaoke microphone, which names
the feature the panel already names, not the act of starting. Ending a set and throwing the setlist
away must never look alike, and ending must not delete anything.

Part 7. A setlist can hold three different kinds of material - a published Catalog song, a Custom
Progression that may be four chords with no lyrics or form, and a Composition Studio song with its
own melody and words - and they looked identical. The colour comes from the entry's stored
``source``, never from its title, so a Catalog song called "A Minor Progression" is not painted
green. Catalog is red inside Karaoke and purple everywhere else on purpose: Karaoke's whole stage is
that purple, so a purple row would read as "this is Karaoke" rather than "this came from the
Catalog". The source name is also spelled out on every row, so the distinction never depends on
seeing colour.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import karaoke_mode as km
import karaoke_ui
from karaoke_ui import _entry_source_style
from music_feature_icons import ACTION_ICONS, semantic_action_icon
from songs.music_source import SOURCE_CATALOG, SOURCE_COMPOSITION, SOURCE_CUSTOM

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "karaoke_ui.py"
CSS = ROOT / "app_ui.py"


class TheTransportVerbsExist(unittest.TestCase):
    def test_stop_next_and_previous_have_icons(self) -> None:
        for verb in ("stop", "next", "previous"):
            with self.subTest(verb=verb):
                self.assertTrue(semantic_action_icon(verb), verb)

    def test_stop_is_the_apps_own_transport_square(self) -> None:
        from music_feature_icons import FEATURE_ICONS

        self.assertEqual(semantic_action_icon("stop"), FEATURE_ICONS["action_stop"])

    def test_ending_a_set_never_looks_like_deleting_it(self) -> None:
        """The whole point of Part 6: Stop and Clear must not be confusable."""
        self.assertNotEqual(semantic_action_icon("stop"), semantic_action_icon("delete"))

    def test_next_and_previous_are_the_glyphs_the_player_already_printed(self) -> None:
        self.assertEqual(semantic_action_icon("next"), "⏭")
        self.assertEqual(semantic_action_icon("previous"), "⏮")

    def test_play_and_stop_are_a_pair_not_a_repetition(self) -> None:
        self.assertNotEqual(semantic_action_icon("play"), semantic_action_icon("stop"))


class TheKaraokeButtonsUseTheSharedMap(unittest.TestCase):
    CASES = (
        ("play", "start_session_button"),
        ("stop", "stop_session_button"),
        ("delete", "Clear Setlist"),
        ("previous", " Previous song"),
        ("next", "KARAOKE_SKIP_BUTTON_TEXT"),
        ("stop", "End karaoke set"),
    )

    def setUp(self) -> None:
        self.src = UI.read_text(encoding="utf-8")

    def test_each_button_goes_through_action_label(self) -> None:
        for verb, needle in self.CASES:
            with self.subTest(verb=verb, needle=needle):
                # The label may be a literal or a call - km.voice_wording(...) - so the
                # pattern allows anything up to the needle on the same logical argument.
                pattern = re.compile(
                    r'action_label\(\s*"' + verb + r'"\s*,\s*[^\n]*'
                    + re.escape(needle)
                )
                self.assertRegex(self.src, pattern)

    def test_start_no_longer_wears_the_feature_microphone(self) -> None:
        self.assertNotIn(
            'feature_label("karaoke", km.voice_wording("start_session_button"', self.src
        )

    def test_the_player_no_longer_hardcodes_its_transport_glyphs(self) -> None:
        """One place defines them, so the setlist and the player cannot drift apart."""
        self.assertNotIn('"\\u23EE  Previous song"', self.src)
        self.assertNotIn('f"\\u23ED  {KARAOKE_SKIP_BUTTON_TEXT}"', self.src)


class EndingASetKeepsTheSetlist(unittest.TestCase):
    """Part 6: ending a performance must not delete what the singer saved."""

    def setUp(self) -> None:
        self.session: dict = {}
        for pick in ("Pop\x1fSay", "custom::am-1", "composition::doc-1"):
            km.add_to_queue(self.session, pick, practice_key="Bb")
        self.before = list(km.get_queue(self.session))

    def test_the_queue_is_not_empty_to_begin_with(self) -> None:
        self.assertEqual(len(self.before), 3)

    def test_ending_the_set_leaves_every_entry_in_place(self) -> None:
        karaoke_ui.end_karaoke_set(self.session)
        after = list(km.get_queue(self.session))
        self.assertEqual(
            [e.get("pick_key") for e in after], [e.get("pick_key") for e in self.before]
        )

    def test_ending_the_set_keeps_each_entrys_saved_key(self) -> None:
        karaoke_ui.end_karaoke_set(self.session)
        for entry in km.get_queue(self.session):
            with self.subTest(pick=entry.get("pick_key")):
                self.assertEqual(str(entry.get("practice_key") or ""), "Bb")

    def test_only_clearing_clears(self) -> None:
        km.clear_queue(self.session)
        self.assertEqual(list(km.get_queue(self.session)), [])


class ARowSaysWhereItCameFrom(unittest.TestCase):
    def test_each_source_has_its_own_class_and_name(self) -> None:
        self.assertEqual(
            _entry_source_style({"source": SOURCE_CATALOG}), ("src-catalog", "Catalog")
        )
        self.assertEqual(
            _entry_source_style({"source": SOURCE_CUSTOM}), ("src-custom", "Custom")
        )
        self.assertEqual(
            _entry_source_style({"source": SOURCE_COMPOSITION}),
            ("src-composition", "Composition"),
        )

    def test_the_three_are_all_different(self) -> None:
        styles = {
            _entry_source_style({"source": s})
            for s in (SOURCE_CATALOG, SOURCE_CUSTOM, SOURCE_COMPOSITION)
        }
        self.assertEqual(len(styles), 3)

    def test_the_title_never_decides_the_colour(self) -> None:
        """A Catalog song named like a progression is still a Catalog song."""
        entry = {
            "source": SOURCE_CATALOG,
            "pick_key": "Pop\x1fA Minor Progression",
            "title": "A Minor Progression",
        }
        self.assertEqual(_entry_source_style(entry), ("src-catalog", "Catalog"))

    def test_an_entry_saved_before_source_existed_is_still_right(self) -> None:
        """The field is re-derived from the pick key rather than defaulted to Catalog."""
        self.assertEqual(
            _entry_source_style({"pick_key": "custom::am-1"}), ("src-custom", "Custom")
        )
        self.assertEqual(
            _entry_source_style({"pick_key": "composition::doc-1"}),
            ("src-composition", "Composition"),
        )
        self.assertEqual(
            _entry_source_style({"pick_key": "Pop\x1fSay"}), ("src-catalog", "Catalog")
        )

    def test_an_unrecognised_source_falls_back_to_the_pick_key(self) -> None:
        self.assertEqual(
            _entry_source_style({"source": "nonsense", "pick_key": "custom::am-1"}),
            ("src-custom", "Custom"),
        )

    def test_nothing_at_all_is_not_an_error(self) -> None:
        self.assertEqual(_entry_source_style(None), ("", ""))
        self.assertEqual(_entry_source_style({}), ("", ""))

    def test_a_real_queue_entry_carries_its_source(self) -> None:
        session: dict = {}
        km.add_to_queue(session, "custom::am-1", practice_key="Am")
        entry = km.get_queue(session)[0]
        self.assertEqual(_entry_source_style(entry), ("src-custom", "Custom"))


class TheRowRendersBothTheColourAndTheName(unittest.TestCase):
    def setUp(self) -> None:
        self.src = UI.read_text(encoding="utf-8")

    def test_the_source_name_is_rendered_not_only_the_class(self) -> None:
        self.assertIn('class="ui-karaoke-row-source', self.src)
        self.assertIn("html.escape(source_name)", self.src)

    def test_the_row_and_the_marker_both_carry_the_source_class(self) -> None:
        self.assertRegex(self.src, r'ui-karaoke-pick-wrap \{wrap_state\} \{source_cls\}')
        self.assertRegex(self.src, r'ui-karaoke-row-marker \{marker_cls\} \{source_cls\}')

    def test_the_source_is_exposed_as_data_for_assistive_tools_and_tests(self) -> None:
        self.assertIn('data-source="', self.src)


class TheStylesheetHasAllThree(unittest.TestCase):
    def setUp(self) -> None:
        self.css = CSS.read_text(encoding="utf-8")

    def test_each_source_colours_the_editing_row(self) -> None:
        for cls in ("src-catalog", "src-custom", "src-composition"):
            with self.subTest(cls=cls):
                self.assertIn(
                    ".ui-karaoke-pick-wrap.is-editing.%s + div .stButton > button" % cls,
                    self.css,
                )

    def test_each_source_colours_the_now_editing_marker(self) -> None:
        for cls in ("src-catalog", "src-custom", "src-composition"):
            with self.subTest(cls=cls):
                self.assertIn(".ui-karaoke-row-marker.marker-editing.%s" % cls, self.css)

    def test_the_source_chip_is_styled_for_each(self) -> None:
        for cls in ("src-catalog", "src-custom", "src-composition"):
            with self.subTest(cls=cls):
                self.assertIn(".ui-karaoke-row-source.%s" % cls, self.css)

    def test_now_singing_keeps_its_one_unmistakable_treatment(self) -> None:
        """On stage the row must answer "which song is playing", not "where is it from"."""
        self.assertIn(".ui-karaoke-pick-wrap.is-singing + div .stButton > button", self.css)
        self.assertNotIn(".ui-karaoke-pick-wrap.is-singing.src-catalog", self.css)

    def test_every_source_row_keeps_white_text(self) -> None:
        """Legibility is not optional on black or on red."""
        for cls in ("src-catalog", "src-custom", "src-composition"):
            with self.subTest(cls=cls):
                start = self.css.index(
                    ".ui-karaoke-pick-wrap.is-editing.%s + div .stButton > button" % cls
                )
                block = self.css[start : self.css.index("}", start)]
                self.assertIn("color: #ffffff", block)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
