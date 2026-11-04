"""Load Last Song actually loads the previous song into the active song card.

The shortcut queues a restore that is applied before widgets. The Songs picker dropdown still shows the
song the musician was on, and that stale value used to be read as an uncommitted click and committed
straight back over the restore - the card never changed.
"""
import unittest

from songs.music_source import (
    PENDING_PREVIOUS_CATALOG_RESTORE_KEY,
    apply_pending_previous_catalog_restore_before_widgets,
    load_last_song_snapshot,
)
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    consume_uncommitted_catalog_dropdown,
)
from tests.test_r11_empty_and_composition_sbi import _Base, _FakeSt

A = ("Pop", "Perfect — Ed Sheeran")
B = ("Pop", "Say — John Mayer")


class TestLoadLastSong(_Base):
    def _two_songs(self):
        session = self.new_session()
        self.activate_catalog(session, *A)
        self.activate_catalog(session, *B)
        return session

    def _pick_options(self, session):
        from song_catalog.catalog import format_pick_key

        return [
            format_pick_key(g, t)
            for g, titles in self.picker.items()
            for t in titles
        ]

    def _click_load_last(self, session):
        snap = load_last_song_snapshot(session, on_catalog_page=True)
        self.assertIsNotNone(snap, "the shortcut must offer the previous song")
        session[PENDING_PREVIOUS_CATALOG_RESTORE_KEY] = dict(snap)
        return apply_pending_previous_catalog_restore_before_widgets(
            _FakeSt(session),
            song_picker_catalog=self.picker,
            song_library=self.library,
            invalidate_backing=lambda *a, **k: None,
        )

    def test_the_shortcut_offers_the_previous_distinct_song(self):
        session = self._two_songs()
        snap = load_last_song_snapshot(session, on_catalog_page=True)
        self.assertEqual((snap or {}).get("selected_song", {}).get("title"), "Perfect")

    def test_the_restore_changes_the_active_song(self):
        session = self._two_songs()
        self.assertTrue(self._click_load_last(session))
        self.assertIn("Perfect", str(session.get(ACTIVE_CATALOG_PICK_KEY)))

    def test_the_stale_picker_dropdown_does_not_undo_the_restore(self):
        """The regression: the dropdown still reads the song we just came FROM."""
        session = self._two_songs()
        session["matching_song_dropdown"] = str(session.get(ACTIVE_CATALOG_PICK_KEY))   # showing Say
        self.assertTrue(self._click_load_last(session))
        self.assertIn("Perfect", str(session.get(ACTIVE_CATALOG_PICK_KEY)))

        # ... now the picker renders and reconciles its dropdown.
        live = consume_uncommitted_catalog_dropdown(
            _FakeSt(session), self._pick_options(session), self.picker, song_library=self.library
        )
        self.assertIn("Perfect", live)
        self.assertIn("Perfect", str(session.get(ACTIVE_CATALOG_PICK_KEY)))

    def test_pressing_it_again_goes_back(self):
        session = self._two_songs()
        session["matching_song_dropdown"] = str(session.get(ACTIVE_CATALOG_PICK_KEY))
        self._click_load_last(session)
        consume_uncommitted_catalog_dropdown(
            _FakeSt(session), self._pick_options(session), self.picker, song_library=self.library
        )
        self.assertIn("Perfect", str(session.get(ACTIVE_CATALOG_PICK_KEY)))
        self._click_load_last(session)
        self.assertIn("Say", str(session.get(ACTIVE_CATALOG_PICK_KEY)))

    def test_the_identity_reconciler_does_not_revert_the_restore(self):
        """The real regression: the song we came FROM was still the 'explicitly committed' pick, so
        reconcile_active_song_identity synced the active song straight back to it."""
        from songs.state import EXPLICIT_CATALOG_PICK_COMMITTED_KEY, reconcile_active_song_identity

        session = self._two_songs()
        # Clicking a song in the Songs picker records it as the explicitly committed pick.
        session[EXPLICIT_CATALOG_PICK_COMMITTED_KEY] = str(session.get(ACTIVE_CATALOG_PICK_KEY))
        session["matching_song_dropdown"] = str(session.get(ACTIVE_CATALOG_PICK_KEY))
        self.assertIn("Say", str(session.get(EXPLICIT_CATALOG_PICK_COMMITTED_KEY)))
        self.assertTrue(self._click_load_last(session))
        self.assertIn("Perfect", str(session.get(ACTIVE_CATALOG_PICK_KEY)))
        # The restore must have taken ownership of the explicit-pick bookkeeping too.
        self.assertIn("Perfect", str(session.get(EXPLICIT_CATALOG_PICK_COMMITTED_KEY)))
        settled = reconcile_active_song_identity(session, self.picker)
        self.assertIn("Perfect", str(settled))
        self.assertIn("Perfect", str(session.get(ACTIVE_CATALOG_PICK_KEY)))

    def test_nothing_to_restore_is_a_no_op(self):
        session = self.new_session()
        self.activate_catalog(session, *A)
        self.assertIsNone(load_last_song_snapshot(session, on_catalog_page=True))
        before = str(session.get(ACTIVE_CATALOG_PICK_KEY))
        session[PENDING_PREVIOUS_CATALOG_RESTORE_KEY] = {"pick_key": ""}
        apply_pending_previous_catalog_restore_before_widgets(
            _FakeSt(session),
            song_picker_catalog=self.picker,
            song_library=self.library,
            invalidate_backing=lambda *a, **k: None,
        )
        self.assertEqual(str(session.get(ACTIVE_CATALOG_PICK_KEY)), before)


if __name__ == "__main__":
    unittest.main()
