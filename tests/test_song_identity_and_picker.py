"""Regression tests for active-song identity reset and deferred catalog picks."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from active_song_state import flush_active_song_edits, write_canonical_active_song_state
from song_catalog.catalog import format_pick_key
from songs.key_state import IDENTITY_KEY, song_display_identity
from songs.music_source import (
    ACTIVE_SONG_IDENTITY_KEY,
    compute_active_song_identity,
    on_active_song_identity_changed,
)
from songs.playback_defaults import BACKING_GROOVE_KEY, BPM_WIDGET_KEY
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    PENDING_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    _LAST_PICK_KEY,
    apply_pending_catalog_pick_before_widgets,
    apply_pick_key,
    queue_pending_catalog_pick,
)

PK_SAY = format_pick_key("Pop", "Say — John Mayer")
PK_OTHER = format_pick_key("Pop", "Song B — Artist B")

CATALOG = {
    "Pop": {
        "Say — John Mayer": {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "genre": "Pop",
            "extensions": {"default_bpm": 82, "default_groove": "Pop groove"},
        },
        "Song B — Artist B": {
            "title": "Song B",
            "artist": "Artist B",
            "key": "C",
            "genre": "Pop",
        },
    }
}


def _fake_st(session: dict | None = None):
    ss = session if session is not None else {}
    return MagicMock(session_state=ss)


class TestDeferredCatalogPick(unittest.TestCase):
    def test_queue_pending_catalog_pick_sets_session_key(self) -> None:
        st = _fake_st({})
        queue_pending_catalog_pick(st, PK_SAY)
        self.assertEqual(st.session_state[PENDING_CATALOG_PICK_KEY], PK_SAY)

    def test_apply_pending_catalog_pick_before_widgets(self) -> None:
        st = _fake_st(
            {
                PENDING_CATALOG_PICK_KEY: PK_SAY,
                "display_key": "Eb",
                IDENTITY_KEY: song_display_identity("Custom", "Custom progression", "Eb"),
                ACTIVE_SONG_IDENTITY_KEY: "cpl::draft-1",
            }
        )
        with patch("songs.state.persist_music_local_state"):
            applied = apply_pending_catalog_pick_before_widgets(
                st,
                CATALOG,
                invalidate_backing=lambda _st: None,
            )
        self.assertTrue(applied)
        self.assertNotIn(PENDING_CATALOG_PICK_KEY, st.session_state)
        self.assertEqual(st.session_state[ACTIVE_CATALOG_PICK_KEY], PK_SAY)
        self.assertEqual(st.session_state["display_key"], "G")

    def test_apply_picker_catalog_filters_pattern_queues_not_persist(self) -> None:
        """Simulate render-time filter default: queue + rerun, never persist post-widget."""
        st = _fake_st({ACTIVE_CATALOG_PICK_KEY: PK_OTHER})
        queue_pending_catalog_pick(st, PK_SAY)
        self.assertEqual(st.session_state[PENDING_CATALOG_PICK_KEY], PK_SAY)
        with patch("songs.state.apply_pick_key") as mock_apply:
            apply_pending_catalog_pick_before_widgets(
                st,
                CATALOG,
                invalidate_backing=lambda _st: None,
            )
        mock_apply.assert_called_once()


class TestFlushDoesNotMutateDisplayKey(unittest.TestCase):
    def test_flush_preserves_widget_bound_display_key(self) -> None:
        session = {
            "display_key": "Eb",
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SAY,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
        }
        write_canonical_active_song_state(
            session,
            {
                "pick_key": PK_SAY,
                "display_key": "G",
                "selected_song": session[SELECTED_SONG_STATE_KEY],
            },
            reason="setup",
            mutate_display_key=False,
        )
        flush_active_song_edits(session, reason="song_edit")
        self.assertEqual(session["display_key"], "Eb")


class TestActiveSongIdentityChanged(unittest.TestCase):
    def test_custom_to_catalog_resets_display_bpm_groove(self) -> None:
        st = _fake_st(
            {
                "display_key": "Eb",
                IDENTITY_KEY: song_display_identity("Custom", "Custom progression", "Eb"),
                ACTIVE_SONG_IDENTITY_KEY: "cpl::draft-1",
                BPM_WIDGET_KEY: 115,
                BACKING_GROOVE_KEY: "Jazz swing",
            }
        )
        changed = on_active_song_identity_changed(
            st,
            pick_key=PK_SAY,
            title="Say",
            artist="John Mayer",
            original_key="G",
            is_custom=False,
            sync_id=f"pk::{PK_SAY}",
            default_bpm=82,
            default_groove="Pop groove",
            default_meter="4/4",
            display_key="G",
            invalidate_backing=lambda _st: None,
        )
        self.assertTrue(changed)
        self.assertEqual(st.session_state["display_key"], "G")
        self.assertEqual(int(st.session_state[BPM_WIDGET_KEY]), 82)
        self.assertEqual(st.session_state[BACKING_GROOVE_KEY], "Pop groove")

    def test_apply_pick_key_uses_identity_handler(self) -> None:
        st = _fake_st(
            {
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_OTHER,
                    "title": "Song B",
                    "artist": "Artist B",
                    "key": "C",
                },
                ACTIVE_CATALOG_PICK_KEY: PK_OTHER,
                _LAST_PICK_KEY: PK_OTHER,
                "display_key": "C",
                IDENTITY_KEY: song_display_identity("Song B", "Artist B", "C"),
                ACTIVE_SONG_IDENTITY_KEY: compute_active_song_identity(
                    pick_key=PK_OTHER,
                    title="Song B",
                    artist="Artist B",
                    original_key="C",
                ),
            }
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SAY, CATALOG, skip_activity_log=True)
        self.assertEqual(st.session_state["display_key"], "G")
        self.assertEqual(st.session_state[ACTIVE_CATALOG_PICK_KEY], PK_SAY)


if __name__ == "__main__":
    unittest.main()
