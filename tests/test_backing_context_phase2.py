"""Phase 2 tests — Creative handoff wiring for backing_context."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import (
    BACKING_CONTEXT_KEY,
    PENDING_BACKING_CONTEXT_APPLY,
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
from custom_progression_lab import PENDING_BACKING_LOOPS, PENDING_BACKING_SCOPE
from songs.bpm_state import PENDING_BACKING_TRACK_BPM
from songs.key_state import PENDING_DISPLAY_KEY
from songs.playback_defaults import PENDING_BACKING_GROOVE


class TestBackingContextPhase2(unittest.TestCase):
    def test_apply_entry_jam_sets_bpm_and_scope(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_style": "Jazz Swing",
            "improv_style_meta": {"style": "Jazz Swing", "bpm": 90, "groove": "Medium"},
            "improv_style_key": "G",
        }
        ctx = build_entry_jam_context(session)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=False)
        self.assertEqual(session.get("backing_track_bpm"), 90)
        self.assertEqual(session.get("backing_groove_style"), "Jazz swing")

    def test_widget_safe_handoff_queues_pending_keys(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_style": "Jazz Swing",
            "improv_style_meta": {"style": "Jazz Swing", "bpm": 90, "groove": "Medium"},
            "improv_style_key": "G",
        }
        ctx = build_entry_jam_context(session)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=True)
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "G")
        self.assertEqual(session.get(PENDING_BACKING_TRACK_BPM), 90)
        self.assertEqual(session.get(PENDING_BACKING_GROOVE), "Jazz swing")
        self.assertEqual(session.get(PENDING_BACKING_LOOPS), 2)
        self.assertEqual(session.get(PENDING_BACKING_SCOPE), "Full song")
        self.assertTrue(session.get(PENDING_BACKING_CONTEXT_APPLY))
        self.assertNotIn("backing_track_bpm", session)

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

    def test_mission_context_survives_active_song_change(self) -> None:
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
        self.assertFalse(invalidate_if_song_changed(session))
        self.assertIsNotNone(get_backing_context(session))

    def test_custom_progression_invalidates_on_song_change(self) -> None:
        session = {
            "active_catalog_pick_key": "daughters|artist",
            BACKING_CONTEXT_KEY: {
                "source": "custom_progression",
                "source_label": "Custom progression",
                "active_song_id": "custom-rev-1",
                "song_title": "My progression",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 82,
                "style": "",
                "groove": "Pop groove",
                "bound_pick_key": "say|artist",
                "custom_revision_id": "custom-rev-1",
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
        self.assertIn("Concert G", banner)
        self.assertIn("82 BPM", banner)

    def test_reconcile_does_not_queue_rerun(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, reconcile_backing_context_on_backing_page

        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "F",
            "concert_key": "F",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Jazz Swing",
            "improv_style_key": "F",
            "improv_style_meta": {"style": "Jazz Swing", "bpm": 110, "groove": "Jazz swing"},
            "improv_generated_sections": {"Head (Jazz Swing)": ["Dm7", "G7", "Cmaj7"]},
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "say|artist",
                "song_title": "Jazz Swing",
                "key": "F",
                "display_key": "F",
                "concert_key": "F",
                "bpm": 110,
                "style": "Jazz Swing",
                "groove": "Jazz swing",
                "bound_pick_key": "say|artist",
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            reconcile_backing_context_on_backing_page(session, st_like=st_like)
        self.assertEqual(session.get("backing_track_bpm"), 110)
        self.assertNotIn(PENDING_BACKING_CONTEXT_APPLY, session)


if __name__ == "__main__":
    unittest.main()
