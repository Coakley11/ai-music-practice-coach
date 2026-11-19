"""Melody suggestion cards: the card being auditioned says "Previewing"; the accepted card says "Active"; never both."""
from __future__ import annotations

import unittest
from unittest import mock

import composition_studio_page as page
from composition_document import bootstrap_from_vision, apply_structure_template, ordered_sections


def _render(ss, doc, sid, concept, *, is_active=False):
    fake_st = mock.MagicMock()
    fake_st.columns.return_value = [mock.MagicMock(), mock.MagicMock()]
    fake_st.button.return_value = False
    header = mock.MagicMock()
    fake_st.empty.return_value = header
    with mock.patch.object(page, "st", fake_st), mock.patch.object(page, "_attach_synced_score_preview", return_value=True):
        page._render_melody_concept_card(ss, doc, sid, concept, prefix="p", is_active=is_active)
    return header.markdown.call_args.args[0]


class TestMelodyCardStates(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(self.doc, "simple")
        self.sid = str(ordered_sections(self.doc)[0]["id"])
        self.concept = {"id": "idea1", "name": "Rising hook", "contour": "up", "events": [{"pitch": "D4", "duration_beats": 1.0}]}

    def test_card_whose_preview_is_mounted_says_previewing(self) -> None:
        ss = {page.COMPOSER_PREVIEW_WAV_KEY: b"RIFF", "composer_preview_slot": f"melody:{self.sid}:idea1"}
        html_out = _render(ss, self.doc, self.sid, self.concept)
        self.assertIn("Previewing", html_out)
        self.assertIn('data-composer-previewing="1"', html_out)

    def test_other_cards_and_the_accepted_card_do_not(self) -> None:
        ss = {page.COMPOSER_PREVIEW_WAV_KEY: b"RIFF", "composer_preview_slot": f"melody:{self.sid}:other"}
        self.assertNotIn("Previewing", _render(ss, self.doc, self.sid, self.concept))
        ss = {page.COMPOSER_PREVIEW_WAV_KEY: b"RIFF", "composer_preview_slot": f"melody:{self.sid}:idea1"}
        active = _render(ss, self.doc, self.sid, self.concept, is_active=True)
        self.assertNotIn("Previewing", active)
        self.assertIn("Active", active)

    def test_no_armed_audio_means_not_previewing(self) -> None:
        ss = {"composer_preview_slot": f"melody:{self.sid}:idea1"}
        self.assertNotIn("Previewing", _render(ss, self.doc, self.sid, self.concept))

    def test_title_staff_and_controls_share_one_keyed_card(self) -> None:
        # The bordered header used to hold only the title; the staff and buttons sat outside the ACTIVE frame on desktop.
        fake_st = mock.MagicMock()
        fake_st.columns.return_value = [mock.MagicMock(), mock.MagicMock()]
        fake_st.button.return_value = False
        with mock.patch.object(page, "st", fake_st), mock.patch.object(page, "_attach_synced_score_preview", return_value=True):
            page._render_melody_concept_card({}, self.doc, self.sid, self.concept, prefix="p", is_active=True)
        names = [c[0] for c in fake_st.mock_calls]
        self.assertEqual(fake_st.container.call_args_list[0], mock.call(key="composer_mel_card_p_idea1"))
        opened = names.index("container().__enter__")
        closed = names.index("container().__exit__", opened)
        for inner in ("empty", "columns", "button"):
            idx = names.index(inner)
            self.assertTrue(opened < idx < closed, inner)

    def test_card_frames_follow_active_and_previewing_markers(self) -> None:
        from pathlib import Path

        src = Path(page.__file__).read_text(encoding="utf-8")
        self.assertIn('[class*="st-key-composer_mel_card_"]:has([data-composer-active-melody="1"])', src)
        self.assertIn('[class*="st-key-composer_mel_card_"]:has([data-composer-previewing="1"])', src)


if __name__ == "__main__":
    unittest.main()
