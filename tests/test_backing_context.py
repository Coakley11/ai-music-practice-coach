"""Unit tests for canonical backing_context (Phase 1)."""

from __future__ import annotations

import unittest

from backing_context import (
    BACKING_CONTEXT_KEY,
    BackingContext,
    build_custom_progression_context,
    build_entry_jam_context,
    build_mission_context,
    build_regular_song_context,
    clear_backing_context,
    compute_source_signature,
    context_is_stale,
    get_backing_context,
    invalidate_if_song_changed,
    is_backing_context_valid,
    set_backing_context,
)


class TestBackingContext(unittest.TestCase):
    def test_regular_song_context_shape(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "concert_key": "G",
            "backing_track_bpm": 82,
            "backing_groove_style": "Pop groove",
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
        }
        ctx = build_regular_song_context(session)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.song_title, "Say")
        self.assertEqual(ctx.bpm, 82)
        self.assertEqual(ctx.bound_pick_key, "say|artist")
        self.assertTrue(ctx.source_signature)

    def test_entry_jam_context_from_style_meta(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_meta": {"style": "Jazz", "bpm": 90, "groove": "Medium"},
            "improv_style_key": "Dm",
            "improv_generated_sections": {"Verse (Jazz)": ["Dm7", "G7", "Cmaj7"]},
        }
        ctx = build_entry_jam_context(session)
        self.assertEqual(ctx.source, "entry_jam")
        self.assertEqual(ctx.bpm, 90)
        self.assertEqual(ctx.groove, "Medium")
        self.assertIn("Dm7", ctx.progression)

    def test_mission_context_carries_mission_id(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_active_mission": "ii–V–I drill",
            "II_SELECTED_SECTION": "Verse",
            "improv_mission_progression": ["Dm7", "G7", "Cmaj7"],
        }
        ctx = build_mission_context(session)
        self.assertEqual(ctx.source, "mission")
        self.assertEqual(ctx.mission_id, "ii–V–I drill")
        self.assertEqual(ctx.section, "Verse")
        self.assertEqual(ctx.scope, "Single section")

    def test_custom_progression_context(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "cpl_active_progression": {
                "name": "My Vamp",
                "id": "rev-abc",
                "original_key_center": "G",
                "bpm": 88,
                "loops": 3,
                "original_sections": {
                    "Verse": [{"chord": "Gmaj7", "bars": 1}, {"chord": "Em7", "bars": 1}],
                    "Chorus": [],
                    "Bridge": [],
                    "Intro": [],
                    "Outro": [],
                },
            },
        }
        ctx = build_custom_progression_context(session)
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.custom_revision_id, "rev-abc")
        self.assertIn("Gmaj7", ctx.progression)
        self.assertEqual(ctx.bpm, 88)

    def test_signature_changes_when_bpm_changes(self) -> None:
        base = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="say",
            song_title="Say",
            key="G",
            display_key="G",
            concert_key="G",
            bpm=82,
            style="Pop",
            groove="Medium",
            bound_pick_key="say",
        )
        changed = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="say",
            song_title="Say",
            key="G",
            display_key="G",
            concert_key="G",
            bpm=90,
            style="Pop",
            groove="Medium",
            bound_pick_key="say",
        )
        self.assertNotEqual(compute_source_signature(base), compute_source_signature(changed))

    def test_signature_changes_when_progression_changes(self) -> None:
        a = BackingContext(
            source="custom_progression",
            source_label="Custom progression",
            active_song_id="rev-1",
            song_title="Vamp",
            key="G",
            display_key="G",
            concert_key="G",
            bpm=80,
            style="",
            groove="Pop groove",
            progression=["Gmaj7", "Em7"],
            bound_pick_key="say",
        )
        b = BackingContext(
            source="custom_progression",
            source_label="Custom progression",
            active_song_id="rev-1",
            song_title="Vamp",
            key="G",
            display_key="G",
            concert_key="G",
            bpm=80,
            style="",
            groove="Pop groove",
            progression=["Gmaj7", "Am7"],
            bound_pick_key="say",
        )
        self.assertNotEqual(compute_source_signature(a), compute_source_signature(b))

    def test_entry_jam_survives_active_song_change(self) -> None:
        session: dict = {
            "active_catalog_pick_key": "daughters|artist",
            "backing_context": {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "say|artist",
                "song_title": "Say",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 82,
                "style": "Pop",
                "groove": "Medium",
                "bound_pick_key": "say|artist",
            },
        }
        ctx = get_backing_context(session)
        assert ctx is not None
        self.assertTrue(is_backing_context_valid(session, ctx))
        self.assertFalse(invalidate_if_song_changed(session))
        self.assertIsNotNone(get_backing_context(session))

    def test_mission_invalid_when_mission_changes(self) -> None:
        session: dict = {
            "active_catalog_pick_key": "say|artist",
            "improv_active_mission": "New mission",
        }
        ctx = build_mission_context(session)
        ctx.mission_id = "Old mission"
        ctx.bound_pick_key = "say|artist"
        set_backing_context(session, ctx)
        self.assertFalse(is_backing_context_valid(session))
        self.assertTrue(context_is_stale(session))

    def test_set_and_clear_context(self) -> None:
        session: dict = {"active_catalog_pick_key": "say|artist", "song": "Say", "display_key": "G"}
        ctx = build_regular_song_context(session)
        set_backing_context(session, ctx)
        self.assertIn(BACKING_CONTEXT_KEY, session)
        clear_backing_context(session)
        self.assertNotIn(BACKING_CONTEXT_KEY, session)

    def test_round_trip_dict(self) -> None:
        ctx = build_regular_song_context({"active_catalog_pick_key": "x", "song": "Say", "display_key": "G"})
        restored = BackingContext.from_dict(ctx.to_dict())
        assert restored is not None
        self.assertEqual(restored.source, "regular_song")
        self.assertEqual(restored.song_title, "Say")


if __name__ == "__main__":
    unittest.main()
