"""Display key resets when the active song changes."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from active_song_state import prepare_active_song_context, write_canonical_active_song_state
from song_catalog.catalog import format_pick_key
from songs.key_state import (
    IDENTITY_KEY,
    apply_display_key_for_active_song,
    song_display_identity,
)
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    apply_pick_key,
    _LAST_PICK_KEY,
)

PK_A = format_pick_key("Pop", "Song A — Artist A")
PK_B = format_pick_key("Pop", "Song B — Artist B")

CATALOG = {
    "Pop": {
        "Song A — Artist A": {"title": "Song A", "artist": "Artist A", "key": "G"},
        "Song B — Artist B": {"title": "Song B", "artist": "Artist B", "key": "C"},
    }
}


def _fake_st(session: dict | None = None):
    ss = session if session is not None else {}
    return MagicMock(session_state=ss)


class TestDisplayKeyActiveSongSync(unittest.TestCase):
    def test_apply_pick_key_resets_display_key_from_new_song(self) -> None:
        st = _fake_st(
            {
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_A,
                    "title": "Song A",
                    "artist": "Artist A",
                    "key": "G",
                },
                ACTIVE_CATALOG_PICK_KEY: PK_A,
                _LAST_PICK_KEY: PK_A,
                "display_key": "G",
                IDENTITY_KEY: song_display_identity("Song A", "Artist A", "G"),
            }
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_B, CATALOG, skip_activity_log=True)

        self.assertEqual(st.session_state["display_key"], "C")
        self.assertEqual(
            st.session_state[IDENTITY_KEY],
            song_display_identity("Song B", "Artist B", "C"),
        )

    def test_manual_override_preserved_until_song_changes(self) -> None:
        st = _fake_st({"display_key": "G"})
        identity = song_display_identity("Song A", "Artist A", "C")
        st.session_state[IDENTITY_KEY] = identity
        apply_display_key_for_active_song(st, "C", identity)
        st.session_state["display_key"] = "G"
        apply_display_key_for_active_song(st, "C", identity)
        self.assertEqual(st.session_state["display_key"], "G")

    def test_new_song_clears_prior_override(self) -> None:
        st = _fake_st(
            {
                "display_key": "G",
                IDENTITY_KEY: song_display_identity("Song A", "Artist A", "C"),
            }
        )
        new_identity = song_display_identity("Song B", "Artist B", "D")
        apply_display_key_for_active_song(st, "D", new_identity)
        self.assertEqual(st.session_state["display_key"], "D")

    def test_prepare_active_song_follows_live_pick_when_canonical_stale(self) -> None:
        session = {"display_key": "G"}
        write_canonical_active_song_state(
            session,
            {
                "pick_key": PK_A,
                "display_key": "G",
                "selected_song": {
                    "pick_key": PK_A,
                    "title": "Song A",
                    "artist": "Artist A",
                    "key": "G",
                },
            },
            reason="setup",
        )
        session[ACTIVE_CATALOG_PICK_KEY] = PK_B
        session[SELECTED_SONG_STATE_KEY] = {
            "pick_key": PK_B,
            "title": "Song B",
            "artist": "Artist B",
            "key": "C",
        }
        prepare_active_song_context(session)
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], PK_B)
        self.assertEqual(session.get("active_song_state", {}).get("pick_key"), PK_B)


if __name__ == "__main__":
    unittest.main()
