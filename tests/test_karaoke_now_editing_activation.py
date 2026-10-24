"""Karaoke Now Editing: a setlist row (and Add Lyrics) activates the whole song.

Measured: the red NOW EDITING row read "Blues in F minor · Fm" while the sidebar
showed the Blues title over Autumn Leaves' Original Key Bm and Shallow's
Practice Key G. The setlist button activated the entry mid-script; for a Custom
song that writes the sidebar's ``display_key`` after the widget had mounted,
Streamlit raised, and the swallowed error left half an activation (title and
custom choice moved; catalog pick, original key and Practice Key did not).
"""

from __future__ import annotations

import unittest
from pathlib import Path

_APP = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


class _MountedWidgetSession(dict):
    """Session that refuses writes to keys whose widgets already rendered."""

    def __init__(self, *args, mounted=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.mounted = set(mounted)

    def __setitem__(self, key, value):
        if key in self.mounted:
            raise RuntimeError(f"{key} cannot be modified after its widget is instantiated")
        super().__setitem__(key, value)


class SetlistRowActivationTests(unittest.TestCase):
    def test_row_click_queues_the_entry_instead_of_activating_mid_script(self) -> None:
        i = _APP.index("def _on_select_setlist_entry(")
        body = _APP[i : _APP.index("render_karaoke_setlist_panel(", i)]
        self.assertIn("PENDING_KARAOKE_ENTRY_ACTIVATION_KEY", body)
        self.assertNotIn("_activate_karaoke_entry(", body)

    def test_queued_activation_runs_before_the_sidebar_practice_key_widget(self) -> None:
        consumer = _APP.index("_pending_entry_activation = st.session_state.pop(km.PENDING_KARAOKE_ENTRY_ACTIVATION_KEY")
        lyrics = _APP.index("_pending_lyrics_nav = st.session_state.pop(")
        widget = _APP.index('_pk_widget_key = "display_key"')
        self.assertLess(consumer, widget)
        self.assertLess(lyrics, widget)
        block = _APP[consumer : consumer + 400]
        self.assertIn("_activate_karaoke_entry(_pending_entry_activation)", block)
        self.assertIn('"Lyrics & Cues"', block)

    def test_the_activation_is_defined_before_its_pre_widget_consumers(self) -> None:
        self.assertLess(
            _APP.index("def _activate_karaoke_entry("),
            _APP.index("_pending_entry_activation = st.session_state.pop("),
        )

    def test_a_mounted_display_key_refuses_the_custom_write(self) -> None:
        """The hazard the deferral avoids: the same write on a mounted widget raises."""
        session = _MountedWidgetSession(mounted={"display_key"})
        with self.assertRaises(RuntimeError):
            session["display_key"] = "Fm"
        session["concert_key"] = "Fm"
        self.assertEqual(session["concert_key"], "Fm")


class AddLyricsEditingHandoffTests(unittest.TestCase):
    def _lyrics_block(self) -> str:
        start = _APP.index("_pending_lyrics_nav = st.session_state.pop(")
        return _APP[start : _APP.index("_KR_GLOBAL_BASELINE", start)]

    def test_add_lyrics_uses_the_setlist_activation_at_the_songs_own_key(self) -> None:
        block = self._lyrics_block()
        self.assertIn("_activate_karaoke_entry(", block)
        self.assertIn("apply_entry_key=False", block)
        # No raw pick writes ahead of the activation: they split the identity
        # when the custom-owns guard then refused the switch.
        self.assertNotIn("st.session_state[ACTIVE_CATALOG_PICK_KEY] = _pln_pk", block)

    def test_add_lyrics_navigates_to_songs_and_opens_the_lyrics_editor(self) -> None:
        block = self._lyrics_block()
        self.assertIn("_pln_navigate(st.session_state, _pln_page)", block)
        self.assertIn('open_picker_editor(st.session_state, "Lyrics & Cues")', block)
        self.assertIn("set_pending_anchor(st.session_state, ANCHOR_LYRICS_EDITOR)", block)

    def test_entry_key_is_only_applied_for_a_row_click(self) -> None:
        fn = _APP[_APP.index("def _activate_karaoke_entry("):]
        fn = fn[: fn.index("\n# === ")]
        self.assertIn("apply_entry_key: bool = True", fn)
        self.assertIn("km.commit_entry_practice_key(st.session_state, row) if apply_entry_key else", fn)


if __name__ == "__main__":
    unittest.main()
