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


class TestDeferredPreviousCatalogRestore(unittest.TestCase):
    def test_queue_sets_pending_flag(self) -> None:
        from songs.music_source import (
            PENDING_PREVIOUS_CATALOG_RESTORE_KEY,
            queue_previous_catalog_restore,
        )

        st = _fake_st({})
        queue_previous_catalog_restore(st)
        self.assertTrue(st.session_state[PENDING_PREVIOUS_CATALOG_RESTORE_KEY])

    def test_apply_pending_restore_before_widgets(self) -> None:
        from songs.music_source import (
            LAST_CATALOG_STATE_KEY,
            PENDING_PREVIOUS_CATALOG_RESTORE_KEY,
            apply_pending_previous_catalog_restore_before_widgets,
            SOURCE_CATALOG,
        )

        st = _fake_st(
            {
                "active_music_source": SOURCE_CATALOG,
                ACTIVE_CATALOG_PICK_KEY: PK_OTHER,
                _LAST_PICK_KEY: PK_OTHER,
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_OTHER,
                    "title": "Song B",
                    "artist": "Artist B",
                    "key": "C",
                },
                LAST_CATALOG_STATE_KEY: {
                    "pick_key": PK_SAY,
                    "selected_song": {
                        "pick_key": PK_SAY,
                        "title": "Say",
                        "artist": "John Mayer",
                        "key": "G",
                    },
                    "original_key": "G",
                    "display_key": "Eb",
                },
                PENDING_PREVIOUS_CATALOG_RESTORE_KEY: True,
                "display_key": "C",
            }
        )
        with patch("songs.state.persist_music_local_state"):
            applied = apply_pending_previous_catalog_restore_before_widgets(
                st,
                song_picker_catalog=CATALOG,
                invalidate_backing=lambda _st: None,
            )
        self.assertTrue(applied)
        self.assertNotIn(PENDING_PREVIOUS_CATALOG_RESTORE_KEY, st.session_state)
        self.assertEqual(st.session_state[ACTIVE_CATALOG_PICK_KEY], PK_SAY)
        self.assertEqual(st.session_state["display_key"], "Eb")


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


class TestDisplayKeyCloudMerge(unittest.TestCase):
    def test_cloud_restore_display_key_wins_over_stale_session(self) -> None:
        from active_song_state import _merge_display_key_for_active_song, write_canonical_active_song_state
        from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY

        session = {
            "display_key": "G",
            "_cloud_workspace_restored_this_run": True,
            DISPLAY_KEY_OWNER_IDENTITY_KEY: f"pk::{PK_SAY}",
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
                "display_key": "Eb",
                "display_key_owner_identity": f"pk::{PK_SAY}",
                "selected_song": session[SELECTED_SONG_STATE_KEY],
            },
            reason="setup",
            mutate_display_key=False,
        )
        merged = _merge_display_key_for_active_song(
            session,
            {"display_key": "Eb", "music_source": "catalog_song"},
        )
        self.assertEqual(merged, "Eb")

    def test_resolve_picker_catalog_selection_recovers_stale_genre(self) -> None:
        from song_catalog.catalog import format_pick_key, resolve_picker_catalog_selection

        stale_key = format_pick_key("Stale Genre", "Say — John Mayer")
        genre, label, data = resolve_picker_catalog_selection(stale_key, CATALOG)
        self.assertEqual(genre, "Pop")
        self.assertEqual(label, "Say — John Mayer")
        self.assertEqual(data.get("title"), "Say")

    def test_resolve_picker_catalog_selection_falls_back_to_first_valid(self) -> None:
        from song_catalog.catalog import resolve_picker_catalog_selection

        genre, label, data = resolve_picker_catalog_selection("not-a-real-key", CATALOG)
        self.assertTrue(data)
        self.assertIn(genre, CATALOG)
        self.assertIn(label, CATALOG[genre])


PK_NYS = format_pick_key("Jazz", "New York State of Mind — Billy Joel")
PK_AUTUMN = format_pick_key("Jazz", "Autumn Leaves — Joseph Kosma")

JAZZ_CATALOG = {
    **CATALOG,
    "Jazz": {
        "New York State of Mind — Billy Joel": {
            "title": "New York State of Mind",
            "artist": "Billy Joel",
            "key": "C",
            "genre": "Jazz",
        },
        "Autumn Leaves — Joseph Kosma": {
            "title": "Autumn Leaves",
            "artist": "Joseph Kosma",
            "key": "G",
            "genre": "Jazz",
        },
    },
}


class TestFilteredCatalogSelectionIdentity(unittest.TestCase):
    def test_catalog_result_widget_key_uses_pick_key_not_index(self) -> None:
        from app_ui import catalog_result_widget_key

        first = catalog_result_widget_key(PK_NYS)
        second = catalog_result_widget_key(PK_AUTUMN)
        self.assertTrue(first.startswith("catalog_pick_result_"))
        self.assertTrue(second.startswith("catalog_pick_result_"))
        self.assertNotEqual(first, second)
        self.assertEqual(first, catalog_result_widget_key(PK_NYS))
        self.assertNotIn("row_0", first)
        self.assertNotIn("col_0", first)

    def test_filter_does_not_silently_select_first_visible_result(self) -> None:
        from songs.state import sync_matching_song_dropdown_before_widget

        st = _fake_st(
            {
                ACTIVE_CATALOG_PICK_KEY: PK_SAY,
                "matching_song_dropdown": PK_SAY,
            }
        )
        options = [PK_NYS, PK_AUTUMN]
        active = sync_matching_song_dropdown_before_widget(
            st,
            options,
            PK_NYS,
            song_picker_catalog=JAZZ_CATALOG,
        )
        self.assertEqual(active, PK_SAY)
        self.assertIn(PK_SAY, options)
        self.assertEqual(st.session_state["matching_song_dropdown"], PK_SAY)

    def test_filtered_result_click_applies_canonical_pick_key(self) -> None:
        st = _fake_st(
            {
                ACTIVE_CATALOG_PICK_KEY: PK_SAY,
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_SAY,
                    "title": "Say",
                    "artist": "John Mayer",
                    "key": "G",
                },
                _LAST_PICK_KEY: PK_SAY,
            }
        )
        with patch("songs.state.persist_music_local_state"):
            applied = apply_pick_key(st, PK_NYS, JAZZ_CATALOG)
        self.assertEqual(applied.get("title"), "New York State of Mind")
        self.assertEqual(st.session_state[ACTIVE_CATALOG_PICK_KEY], PK_NYS)
        self.assertEqual(st.session_state[SELECTED_SONG_STATE_KEY]["title"], "New York State of Mind")

    def test_render_catalog_grid_click_target_is_song_title(self) -> None:
        from app_ui import render_catalog_song_card_grid

        class _Col:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        st = MagicMock()
        st.columns.side_effect = lambda spec: [_Col() for _ in range(spec if isinstance(spec, int) else len(spec))]
        clicked: list[str] = []

        def _on_load(*, pick_key: str = "") -> None:
            clicked.append(pick_key)

        records = [
            {"title": "New York State of Mind", "artist": "Billy Joel", "genre": "Jazz", "key": "C"},
            {"title": "Autumn Leaves", "artist": "Joseph Kosma", "genre": "Jazz", "key": "G"},
        ]
        render_catalog_song_card_grid(
            st,
            records,
            active_pick_key=PK_SAY,
            song_meta_fn=lambda rec: rec,
            pick_key_for_record_fn=lambda rec: format_pick_key(
                rec["genre"], f"{rec['title']} — {rec['artist']}"
            ),
            on_load_pick_key=_on_load,
        )
        labels = [str(c.args[0]) for c in st.button.call_args_list if c.args]
        self.assertIn("New York State of Mind", labels)
        self.assertIn("Autumn Leaves", labels)
        keys = [str(c.kwargs.get("key") or "") for c in st.button.call_args_list]
        self.assertTrue(any("New_York_State_of_Mind" in k or "New York" in k for k in keys))
        self.assertFalse(any(k.startswith("catalog_card_load_0") for k in keys))
        nys_call = next(c for c in st.button.call_args_list if c.args and c.args[0] == "New York State of Mind")
        self.assertEqual(nys_call.kwargs.get("kwargs"), {"pick_key": PK_NYS})


if __name__ == "__main__":
    unittest.main()
