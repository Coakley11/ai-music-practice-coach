"""Phase 2 tests — Creative handoff wiring for backing_context."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import (
    BACKING_CONTEXT_KEY,
    apply_backing_context_to_session,
    build_entry_jam_context,
    build_mission_context,
    compute_source_signature,
    format_backing_context_banner,
    get_backing_context,
    invalidate_if_song_changed,
    open_backing_from_creative,
    restore_regular_song_backing,
)


class TestBackingContextPhase2(unittest.TestCase):
    def test_apply_entry_jam_sets_bpm_and_scope(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_style_meta": {"style": "Jazz", "bpm": 90, "groove": "Medium"},
            "improv_style_key": "G",
        }
        ctx = build_entry_jam_context(session)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            apply_backing_context_to_session(session, ctx, st_like=st_like)
        self.assertEqual(session.get("backing_track_bpm"), 90)
        self.assertEqual(session.get("backing_groove_style"), "Medium")

    def test_open_backing_from_mission(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_active_mission": "ii–V–I drill",
            "improv_intelligence_tab": "Missions",
            "improv_mission_progression": ["Dm7", "G7", "Cmaj7"],
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = open_backing_from_creative(session, source="mission", st_like=st_like)
        self.assertEqual(ctx.source, "mission")
        self.assertEqual(get_backing_context(session).mission_id, "ii–V–I drill")

    def test_reopen_updates_signature_when_bpm_changes(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_style_meta": {"bpm": 82, "groove": "Medium"},
        }
        ctx1 = build_entry_jam_context(session)
        session["improv_style_meta"] = {"bpm": 95, "groove": "Medium"}
        ctx2 = build_entry_jam_context(session)
        self.assertNotEqual(compute_source_signature(ctx1), compute_source_signature(ctx2))

    def test_restore_regular_song_clears_creative_source(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "backing_track_bpm": 90,
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "say|artist",
                "song_title": "Say",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 90,
                "style": "Jazz",
                "groove": "Medium",
                "bound_pick_key": "say|artist",
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(get_backing_context(session).source, "regular_song")

    def test_invalidate_on_active_song_change(self) -> None:
        session = {
            "active_catalog_pick_key": "daughters|artist",
            BACKING_CONTEXT_KEY: {
                "source": "mission",
                "source_label": "Mission",
                "active_song_id": "say|artist",
                "song_title": "Say",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 82,
                "style": "",
                "groove": "Pop groove",
                "mission_id": "ii–V–I drill",
                "bound_pick_key": "say|artist",
            },
        }
        self.assertTrue(invalidate_if_song_changed(session))
        self.assertIsNone(get_backing_context(session))

    def test_banner_entry_jam(self) -> None:
        ctx = build_entry_jam_context(
            {
                "active_catalog_pick_key": "say|artist",
                "song": "Say",
                "display_key": "G",
                "improv_style_meta": {"bpm": 82, "groove": "Medium"},
            }
        )
        banner = format_backing_context_banner(ctx)
        self.assertIn("Entry & Jam", banner)
        self.assertIn("Say", banner)
        self.assertIn("82 BPM", banner)


if __name__ == "__main__":
    unittest.main()
