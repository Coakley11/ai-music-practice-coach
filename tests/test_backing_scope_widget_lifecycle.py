"""Integration-style tests for backing playback scope widget + canonical reconcile order."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from backing_track_state import (
    BACKING_STATE_KEY,
    BACKING_USER_EDITS_ALLOWED_KEY,
    BACKING_WIDGETS_SEEDED_KEY,
    begin_backing_page_widget_phase,
    bind_backing_rendered_widgets_from_canonical,
    canonical_backing_filters,
    enable_backing_user_edits,
    gather_backing_filters,
    prepare_backing_page,
    reset_backing_playback_scope_to_full_song,
    sync_backing_scope_widgets_after_user_edit,
    write_canonical_backing_state,
)
from music_workflow_pending_creative_return import handle_return_to_creative_click
from song_improv_scope_authority import apply_song_improv_entry_defaults


def _stale_bridge_canonical_session() -> dict[str, Any]:
    session: dict[str, Any] = {
        "backing_track_scope": "Selected sections",
        "backing_track_single_section": "Bridge",
        "backing_track_multi_sections": ["Bridge"],
        "backing_quick_section": "Bridge",
        BACKING_WIDGETS_SEEDED_KEY: True,
    }
    write_canonical_backing_state(
        session,
        gather_backing_filters(session),
        reason="test_seed_stale",
        local_edit=False,
    )
    return session


class TestBackingScopeWidgetLifecycle(unittest.TestCase):
    def test_gather_respects_full_song_scope_over_stale_quick_section(self) -> None:
        session = {
            "backing_track_scope": "Full song",
            "backing_quick_section": "Bridge",
            "backing_track_multi_sections": ["Bridge"],
        }
        filters = gather_backing_filters(session)
        self.assertEqual(str(filters.get("backing_track_scope") or ""), "Full song")
        self.assertFalse(filters.get("backing_track_multi_sections"))

    def test_entry_default_updates_canonical_and_survives_prepare_and_bind(self) -> None:
        session = _stale_bridge_canonical_session()
        apply_song_improv_entry_defaults(session, source="test_entry")
        self.assertEqual(str(session.get("backing_track_scope") or ""), "Full song")
        canon = canonical_backing_filters(session) or {}
        self.assertEqual(str(canon.get("backing_track_scope") or ""), "Full song")

        begin_backing_page_widget_phase(session)
        prepare_backing_page(session)
        bind_backing_rendered_widgets_from_canonical(session, sync_id="test-song")
        self.assertEqual(str(session.get("backing_track_scope") or ""), "Full song")
        self.assertNotIn("backing_track_multi_sections", session)

    def test_user_full_song_edit_syncs_canonical_and_next_prepare_preserves(self) -> None:
        session = _stale_bridge_canonical_session()
        begin_backing_page_widget_phase(session)
        enable_backing_user_edits(session)
        session[BACKING_USER_EDITS_ALLOWED_KEY] = True
        session["backing_track_scope"] = "Full song"
        sync_backing_scope_widgets_after_user_edit(session)
        write_canonical_backing_state(
            session,
            gather_backing_filters(session),
            reason="test_user_full_song",
            local_edit=True,
        )
        session[BACKING_WIDGETS_SEEDED_KEY] = True
        begin_backing_page_widget_phase(session)
        prepare_backing_page(session)
        self.assertEqual(str(session.get("backing_track_scope") or ""), "Full song")
        self.assertNotIn("backing_track_multi_sections", session)
        blob = session.get(BACKING_STATE_KEY)
        self.assertIsInstance(blob, dict)
        assert isinstance(blob, dict)
        self.assertEqual(str(blob.get("backing_track_scope") or ""), "Full song")

    def test_reset_backing_playback_scope_to_full_song_clears_blob(self) -> None:
        session = _stale_bridge_canonical_session()
        reset_backing_playback_scope_to_full_song(session, source="catalog_song_change")
        blob = session.get(BACKING_STATE_KEY)
        self.assertIsInstance(blob, dict)
        assert isinstance(blob, dict)
        self.assertEqual(str(blob.get("backing_track_scope") or ""), "Full song")
        self.assertEqual(str(blob.get("backing_quick_section") or ""), "Full song")

    def test_return_to_creative_click_navigates_without_pre_widget_only(self) -> None:
        from backing_context import BackingContext, set_backing_context

        session: dict[str, Any] = {
            "studio_page": "backing",
            "improv_entry_mode": "Style Jam Mode",
        }
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Style Jam",
                active_song_id="jam",
                song_title="Jam",
                key="G",
                display_key="G",
                concert_key="G",
                bpm=120,
                style="Pop groove",
                groove="Pop groove",
                entry_mode="Style Jam Mode",
            ),
        )
        st_mock = mock.MagicMock()
        handle_return_to_creative_click(st_mock, session)
        self.assertEqual(str(session.get("studio_page") or ""), "creative")
        st_mock.rerun.assert_called()


if __name__ == "__main__":
    unittest.main()
