"""Leave Missions → Catalog Backing must not stay blocked by stale mission_jam."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from backing_context import BackingContext, set_backing_context
from music_workflow_backing_mixed_context_guard import (
    MIXED_BACKING_MISSION_CATALOG,
    evaluate_backing_mixed_mission_catalog_context,
)
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    get_active_workflow_pointer,
    set_active_workflow_pointer,
)


def _mission_jam_session(**extra: Any) -> dict[str, Any]:
    session: dict[str, Any] = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "improv_mission_example": {"chord": "Em", "mission": "Rhythm-first, note-second"},
        # Stale after leaving Missions without Mission Backing — no typed handoff.
        "improv_mission_backing_handoff": False,
        "active_catalog_pick_key": "pop::Shape of You — Ed Sheeran",
        "display_key": "Bm",
        "concert_key": "Bm",
        "suite_workspace_id": "daniel",
    }
    session.update(extra)
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(
            workflow_owner="mission_jam",
            workflow_session_id="mission|catalog|shape",
            context_revision=1,
        ),
        source="test",
    )
    return session


class TestLeaveMissionsCatalogBacking(unittest.TestCase):
    def test_stale_mission_plus_catalog_context_still_blocked_before_ownership(self) -> None:
        session = _mission_jam_session(studio_page="backing")
        set_backing_context(
            session,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id="shape",
                song_title="Shape of You",
                key="Bm",
                display_key="Bm",
                concert_key="Bm",
                bpm=96,
                style="Pop",
                groove="Straight",
            ),
        )
        result = evaluate_backing_mixed_mission_catalog_context(session)
        self.assertTrue(result.blocked)
        self.assertEqual(result.code, MIXED_BACKING_MISSION_CATALOG)

    def test_catalog_rebuild_activates_regular_catalog_and_unblocks_guard(self) -> None:
        session = _mission_jam_session()
        fake_ctx = BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id="shape",
            bound_pick_key="pop::Shape of You — Ed Sheeran",
            song_title="Shape of You",
            key="Bm",
            display_key="Bm",
            concert_key="Bm",
            bpm=96,
            style="Pop",
            groove="Straight",
        )

        with mock.patch(
            "songs.music_source.resolve_catalog_song_for_pick",
            return_value=(
                {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "bpm": 96,
                    "genre": "Pop",
                },
                "Bm",
            ),
        ), mock.patch(
            "music_source_ownership._apply_catalog_transport_from_record",
            return_value=(96, "Straight", "4/4"),
        ), mock.patch(
            "music_source_ownership.build_regular_song_context",
            create=True,
        ):
            from music_source_ownership import rebuild_catalog_backing_from_canonical_pick

            with mock.patch(
                "backing_context.build_regular_song_context",
                return_value=fake_ctx,
            ), mock.patch(
                "backing_context.apply_backing_context_to_session",
            ), mock.patch(
                "backing_context.clear_backing_context",
            ), mock.patch(
                "backing_context.set_backing_source_preference",
            ), mock.patch(
                "songs.music_source.set_catalog_source",
            ), mock.patch(
                "songs.music_source._sync_catalog_session_surface_keys",
            ):
                ctx = rebuild_catalog_backing_from_canonical_pick(
                    session,
                    pick_key="pop::Shape of You — Ed Sheeran",
                )

        self.assertIsNotNone(ctx)
        ptr = get_active_workflow_pointer(session)
        self.assertIsNotNone(ptr)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "regular_catalog_backing")
        self.assertFalse(session.get("improv_mission_backing_handoff"))
        # Mission example may remain for Creative → Missions return.
        self.assertIsInstance(session.get("improv_mission_example"), dict)

        session["studio_page"] = "backing"
        set_backing_context(session, fake_ctx)
        result = evaluate_backing_mixed_mission_catalog_context(session)
        self.assertFalse(result.blocked)

    def test_mission_backing_context_not_blocked(self) -> None:
        session = _mission_jam_session(studio_page="backing")
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission jam",
                active_song_id="mission|shape",
                song_title="Mission",
                key="Em",
                display_key="Em",
                concert_key="Em",
                bpm=100,
                style="Pop",
                groove="Straight",
            ),
        )
        result = evaluate_backing_mixed_mission_catalog_context(session)
        self.assertFalse(result.blocked)

    def test_mission_ownership_open_keeps_mission_source(self) -> None:
        from music_source_ownership import activate_mission_ownership

        session = _mission_jam_session()
        mission_ctx = BackingContext(
            source="mission",
            source_label="Mission jam",
            active_song_id="mission|shape",
            song_title="Mission",
            key="Em",
            display_key="Em",
            concert_key="Em",
            bpm=100,
            style="Pop",
            groove="Straight",
        )
        with mock.patch(
            "backing_context.open_backing_from_creative",
            return_value=mission_ctx,
        ) as open_backing:
            ctx = activate_mission_ownership(session)
        open_backing.assert_called_once()
        args, kwargs = open_backing.call_args
        self.assertEqual(kwargs.get("source") or (args[1] if len(args) > 1 else None), "mission")
        self.assertEqual(ctx.source, "mission")


class TestCustomBackingAfterMission(unittest.TestCase):
    def test_restore_custom_activates_regular_custom_workflow(self) -> None:
        from backing_context import restore_custom_song_backing

        session = _mission_jam_session()
        custom_ctx = BackingContext(
            source="custom_progression",
            source_label="Custom",
            active_song_id="custom::1",
            song_title="My Progression",
            key="D",
            display_key="D",
            concert_key="D",
            bpm=100,
            style="Pop",
            groove="Straight",
        )
        with mock.patch(
            "backing_context.clear_backing_context",
        ), mock.patch(
            "backing_context._release_creative_backing_ownership",
        ), mock.patch(
            "songs.music_source.ensure_custom_progression_for_backing",
            return_value="D",
        ), mock.patch(
            "backing_context.build_custom_progression_context",
            return_value=custom_ctx,
        ), mock.patch(
            "backing_context.apply_backing_context_to_session",
        ), mock.patch(
            "backing_context.set_backing_source_preference",
        ), mock.patch(
            "studio_page_persistence.save_page_snapshot",
        ):
            ctx = restore_custom_song_backing(session)

        self.assertEqual(ctx.source, "custom_progression")
        ptr = get_active_workflow_pointer(session)
        self.assertIsNotNone(ptr)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "regular_custom_backing")
        session["studio_page"] = "backing"
        set_backing_context(session, custom_ctx)
        # Guard only targets regular_song mixes; custom must still not trip it.
        self.assertFalse(evaluate_backing_mixed_mission_catalog_context(session).blocked)


if __name__ == "__main__":
    unittest.main()
