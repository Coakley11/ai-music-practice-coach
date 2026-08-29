"""Karaoke setlist panel must not NameError when a session is active."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import karaoke_mode as km
from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, set_practice_concert_key


class _Button:
    def __bool__(self) -> bool:
        return False


class _Column:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Stage:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestKaraokeSetlistPanelSessionCaption(unittest.TestCase):
    def test_active_session_caption_uses_session_entry_pick_key(self) -> None:
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        ss = {
            "instrument": "Voice",
            PRACTICE_KEY_BY_SOURCE_KEY: {},
            "karaoke_queue": [],
            "selected_song": {"pick_key": pick, "title": "All the Things You Are"},
        }
        set_practice_concert_key(ss, "Ab", pick_key=pick)
        km.add_to_queue(ss, pick, title="All the Things You Are", artist="Jerome Kern")
        set_practice_concert_key(ss, "G", pick_key=pick)
        km.add_to_queue(ss, pick, title="All the Things You Are", artist="Jerome Kern")
        km.start_session(ss)
        self.assertTrue(km.is_karaoke_session_active(ss))

        st = MagicMock()
        st.session_state = ss
        st.container.return_value = _Stage()

        def _cols(spec, *args, **kwargs):
            try:
                n = len(spec)
            except TypeError:
                n = int(spec) if spec else 2
            return [_Column() for _ in range(max(2, n))]

        st.columns.side_effect = _cols
        st.button.return_value = False
        st.toggle.return_value = True
        st.slider.return_value = 5
        st.selectbox.return_value = "white"
        st.number_input.return_value = 1

        from karaoke_ui import render_karaoke_setlist_panel

        # Must not raise NameError on session_active_pk when session is active.
        render_karaoke_setlist_panel(
            st,
            record_for_pick_key=lambda *_a, **_k: None,
            all_records=[],
        )
        caption_texts = [
            str(c.args[0])
            for c in st.caption.call_args_list
            if c.args
        ]
        self.assertTrue(
            any("Karaoke set in progress" in t and "Now singing" in t for t in caption_texts),
            caption_texts,
        )


if __name__ == "__main__":
    unittest.main()
