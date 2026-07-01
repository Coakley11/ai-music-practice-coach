"""Display key resets when the active song changes."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
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
            song_display_identity("Song B", "Artist B", "C", pick_key=PK_B),
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

    def test_identity_change_prefers_explicit_pending_key_over_stale_session_pending(
        self,
    ) -> None:
        from songs.key_state import PENDING_DISPLAY_KEY

        st = _fake_st(
            {
                "display_key": "Eb",
                PENDING_DISPLAY_KEY: "Eb",
                IDENTITY_KEY: song_display_identity("Custom", "Custom progression", "D"),
            }
        )
        new_identity = song_display_identity("Say", "Artist", "G")
        apply_display_key_for_active_song(
            st,
            "G",
            new_identity,
            pending_key="G",
        )
        self.assertEqual(st.session_state["display_key"], "G")

    def test_identity_change_uses_canonical_display_key_over_original(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        st = _fake_st(
            {
                ACTIVE_SONG_STATE_KEY: {
                    "pick_key": PK_A,
                    "display_key": "C#m",
                },
            }
        )
        new_identity = song_display_identity("Song A", "Artist A", "Bm", pick_key=PK_A)
        apply_display_key_for_active_song(st, "Bm", new_identity)
        self.assertEqual(st.session_state["display_key"], "C#m")

    def test_merge_display_key_prefers_canonical_without_identity_override(self) -> None:
        from active_song_state import _merge_display_key_for_active_song

        session = {"display_key": "Bm"}
        ctx = {"display_key": "C#m", "pick_key": "Pop::Song A — Artist A"}
        merged = _merge_display_key_for_active_song(session, ctx)
        self.assertEqual(merged, "C#m")

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


    def test_apply_pick_key_recovery_preserves_saved_display_key(self) -> None:
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        st = _fake_st(
            {
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_A,
                    "title": "Song A",
                    "artist": "Artist A",
                    "key": "Bm",
                },
            }
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(
                st,
                PK_A,
                CATALOG,
                skip_activity_log=True,
                origin="recovery",
                display_key_override="C#m",
            )

        self.assertEqual(st.session_state["display_key"], "C#m")
        self.assertNotIn(USER_CATALOG_SOURCE_CHOICE_KEY, st.session_state)

    def test_restore_previous_catalog_song_widget_safe_after_display_key_widget(
        self,
    ) -> None:
        """Load Last Song must not write locked display_key after sidebar widget exists."""
        from music_restore_phase import complete_music_restore_phase
        from songs.key_state import PENDING_DISPLAY_KEY
        from songs.music_source import LAST_CATALOG_STATE_KEY, restore_previous_catalog_song

        pk_day = format_pick_key("Rock", "Day Tripper — The Beatles")
        pk_say = format_pick_key("Pop", "Say — John Mayer")
        catalog = {
            "Rock": {
                "Day Tripper — The Beatles": {
                    "title": "Day Tripper",
                    "artist": "The Beatles",
                    "key": "E",
                    "genre": "Rock",
                },
            },
            "Pop": {
                "Say — John Mayer": {
                    "title": "Say",
                    "artist": "John Mayer",
                    "key": "G",
                    "genre": "Pop",
                },
            },
        }
        st = _fake_st(
            {
                ACTIVE_CATALOG_PICK_KEY: pk_say,
                _LAST_PICK_KEY: pk_say,
                "display_key": "G",
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": pk_say,
                    "title": "Say",
                    "artist": "John Mayer",
                    "key": "G",
                },
                LAST_CATALOG_STATE_KEY: {
                    "pick_key": pk_day,
                    "selected_song": {
                        "pick_key": pk_day,
                        "title": "Day Tripper",
                        "artist": "The Beatles",
                        "key": "E",
                    },
                    "original_key": "E",
                    "display_key": "E",
                },
            }
        )
        complete_music_restore_phase(st.session_state)
        with patch("songs.state.persist_music_local_state"):
            ok = restore_previous_catalog_song(
                st,
                song_picker_catalog=catalog,
                invalidate_backing=lambda _st: None,
            )
        self.assertTrue(ok)
        ss = st.session_state
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], pk_day)
        self.assertEqual(ss[SELECTED_SONG_STATE_KEY]["title"], "Day Tripper")
        self.assertEqual(ss["display_key"], "G")
        self.assertEqual(ss[PENDING_DISPLAY_KEY], "E")
        self.assertEqual(ss.get("concert_key"), "E")

    def test_apply_saved_music_context_restore_uses_core_display_key(self) -> None:
        from songs.key_state import PENDING_DISPLAY_KEY
        from songs.state import apply_saved_music_context

        st = _fake_st({})
        saved = {
            "pick_key": PK_A,
            "display_key": "C#m",
            "instrument": "Piano",
        }
        with patch("songs.state.persist_music_local_state"):
            ok = apply_saved_music_context(st, saved, song_picker_catalog=CATALOG)

        self.assertTrue(ok)
        self.assertEqual(st.session_state.get("display_key"), "C#m")
        self.assertEqual(st.session_state.get(PENDING_DISPLAY_KEY), "C#m")


    def test_switch_song_resets_display_key_to_new_original(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY
        from songs.music_source import ACTIVE_SONG_IDENTITY_KEY, compute_active_song_identity

        shape_owner = compute_active_song_identity(
            pick_key=PK_A,
            title="Song A",
            artist="Artist A",
            original_key="G",
        )
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
                "display_key": "C#m",
                IDENTITY_KEY: song_display_identity("Song A", "Artist A", "G", pick_key=PK_A),
                ACTIVE_SONG_IDENTITY_KEY: shape_owner,
                ACTIVE_SONG_STATE_KEY: {
                    "pick_key": PK_A,
                    "display_key": "C#m",
                },
            }
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_B, CATALOG, skip_activity_log=True)

        self.assertEqual(st.session_state["display_key"], "C")

    def test_switch_back_restores_per_song_display_key_override(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY
        from songs.music_source import ACTIVE_SONG_IDENTITY_KEY, compute_active_song_identity

        shape_owner = compute_active_song_identity(
            pick_key=PK_A,
            title="Song A",
            artist="Artist A",
            original_key="G",
        )
        st = _fake_st(
            {
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_B,
                    "title": "Song B",
                    "artist": "Artist B",
                    "key": "C",
                },
                ACTIVE_CATALOG_PICK_KEY: PK_B,
                _LAST_PICK_KEY: PK_B,
                "display_key": "C",
                ACTIVE_SONG_STATE_KEY: {
                    "pick_key": PK_A,
                    "display_key": "C#m",
                },
            }
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_A, CATALOG, skip_activity_log=True)

        self.assertEqual(st.session_state["display_key"], "C#m")

    def test_cpl_merge_preserves_sidebar_display_key_for_matching_identity(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY, _merge_display_key_for_active_song
        from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY
        from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY
        from songs.music_source import ACTIVE_SONG_IDENTITY_KEY, SOURCE_CUSTOM

        owner = "cpl::trial-1"
        session = {
            "display_key": "F",
            DISPLAY_KEY_CHANGE_SOURCE_KEY: "sidebar_on_change",
            DISPLAY_KEY_OWNER_IDENTITY_KEY: owner,
            ACTIVE_SONG_IDENTITY_KEY: owner,
            "active_catalog_pick_key": "custom::trial",
            "active_music_source": "custom_progression",
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "display_key": "G",
                "custom_home_key": "D",
                "pick_key": "custom::trial",
            },
        }
        ctx = {
            "music_source": SOURCE_CUSTOM,
            "display_key": "G",
            "custom_home_key": "D",
            "pick_key": "custom::trial",
        }
        merged = _merge_display_key_for_active_song(session, ctx, home_key="D")
        self.assertEqual(merged, "F")

    def test_cpl_merge_ignores_stale_catalog_display_key(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY, _merge_display_key_for_active_song
        from songs.music_source import SOURCE_CUSTOM

        session = {
            "display_key": "Eb",
            "active_catalog_pick_key": "custom::trial",
            "active_music_source": "custom_progression",
            ACTIVE_SONG_STATE_KEY: {
                "music_source": SOURCE_CUSTOM,
                "display_key": "Eb",
                "custom_home_key": "D",
                "pick_key": "pop::Other Song",
            },
        }
        ctx = {
            "music_source": SOURCE_CUSTOM,
            "display_key": "Eb",
            "custom_home_key": "D",
            "pick_key": "custom::trial",
        }
        merged = _merge_display_key_for_active_song(session, ctx, home_key="D")
        self.assertEqual(merged, "D")

    def test_canonical_push_preserves_user_display_key_override(self) -> None:
        from active_song_state import _push_resolved_display_key_to_session
        from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY
        from songs.music_source import ACTIVE_SONG_IDENTITY_KEY

        owner = "pk::pop::Trial"
        session = {
            "display_key": "F",
            DISPLAY_KEY_OWNER_IDENTITY_KEY: owner,
            ACTIVE_SONG_IDENTITY_KEY: owner,
            "active_catalog_pick_key": "pop::Trial",
        }
        ctx = {"display_key": "D", "pick_key": "pop::Trial"}
        _push_resolved_display_key_to_session(session, ctx)
        self.assertEqual(session["display_key"], "F")

    def test_mark_display_key_changed_sets_owner_before_save(self) -> None:
        from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY, mark_display_key_changed
        from songs.music_source import ACTIVE_SONG_IDENTITY_KEY

        st = SimpleNamespace(
            session_state={
                "display_key": "F",
                ACTIVE_SONG_IDENTITY_KEY: "pk::pop::Trial",
                "active_catalog_pick_key": "pop::Trial",
                "selected_song": {"pick_key": "pop::Trial", "title": "Trial", "key": "D"},
            }
        )
        with patch("music_persistent_state.flush_active_song_edits_and_save", return_value=False):
            with patch("songs.state.persist_music_local_state"):
                mark_display_key_changed(st)
        self.assertEqual(
            st.session_state.get(DISPLAY_KEY_OWNER_IDENTITY_KEY),
            "pk::pop::Trial",
        )


if __name__ == "__main__":
    unittest.main()
