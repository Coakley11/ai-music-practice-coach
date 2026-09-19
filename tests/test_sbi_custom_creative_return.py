"""SBI Custom Backing → Creative return keeps Custom identity without conflict."""

from __future__ import annotations

import unittest

from backing_context import BackingContext
from backing_source_navigation import (
    backing_context_is_sbi_custom,
    restore_sbi_song_source_from_backing_context,
)
from music_workflow_activation import (
    activation_user_notice,
    activate_workflow_simple,
)
from music_workflow_compatibility import legacy_session_id_for_owner
from music_workflow_creative_nav import sync_workflow_for_creative_tab
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from source_session_state import get_sbi_preview_source


def _sbi_custom_session() -> dict:
    return {
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_song_source": "Custom progression",
        "sbi_preview_source": "Custom progression",
        "custom_progression_id": "trial-1",
        "cpl_active_id": "trial-1",
        "active_catalog_pick_key": "Pop\x1fShape of You",
        "song": "Shape of You",
        "display_key": "C",
        "concert_key": "C",
        "instrument": "Piano",
        "focus": "Dynamics",
        "cpl_active_progression": {
            "name": "My Progression",
            "id": "trial-1",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 4}]},
        },
    }


def _custom_ctx() -> BackingContext:
    return BackingContext(
        source="song_improv",
        source_label="Song-Based Improvisation",
        active_song_id="My Progression",
        song_title="My Progression",
        key="C",
        display_key="C",
        concert_key="C",
        bpm=100,
        style="Pop",
        groove="Auto",
        entry_mode="Song-Based Improvisation",
        sbi_source_owner="Custom progression",
        sbi_material_kind="custom",
    )


class TestSbiCustomCreativeReturn(unittest.TestCase):
    def test_material_kind_custom_is_enough_without_custom_prefix_id(self) -> None:
        ctx = _custom_ctx()
        self.assertTrue(backing_context_is_sbi_custom(ctx))

    def test_legacy_session_id_uses_custom_blob_id(self) -> None:
        session = _sbi_custom_session()
        sid = legacy_session_id_for_owner(session, "song_based_improvisation")
        self.assertTrue(str(sid).startswith("custom|"))
        self.assertNotEqual(sid, session["active_catalog_pick_key"])

    def test_restore_custom_source_before_activation_then_motif_has_no_conflict(self) -> None:
        session = _sbi_custom_session()
        # Simulate a catalog-follow leftover that used to steal Custom on return.
        session["improv_song_source"] = "Active song"
        session["sbi_preview_source"] = "Active song"
        ctx = _custom_ctx()
        restore_sbi_song_source_from_backing_context(session, ctx)
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

        custom_sid = legacy_session_id_for_owner(session, "song_based_improvisation")
        blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=custom_sid,
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(
                workflow_owner="song_based_improvisation",
                workflow_session_id=custom_sid,
            ),
            source="t",
        )
        result = activate_workflow_simple(
            session,
            "song_based_improvisation",
            activation_source="return_from_backing",
            return_route="creative",
        )
        self.assertTrue(result.ok)
        self.assertFalse(activation_user_notice(session))
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "song_based_improvisation")
        self.assertEqual(ptr.workflow_session_id, custom_sid)

        status = sync_workflow_for_creative_tab(session, "Phrase / Motif")
        self.assertEqual(status, "skipped")
        self.assertFalse(activation_user_notice(session))
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")
        self.assertEqual(session.get("focus"), "Dynamics")
        self.assertEqual(session.get("display_key"), "C")

    def test_follow_active_cannot_conflict_phrase_motif_after_custom_return(self) -> None:
        session = _sbi_custom_session()
        ctx = _custom_ctx()
        restore_sbi_song_source_from_backing_context(session, ctx)
        custom_sid = legacy_session_id_for_owner(session, "song_based_improvisation")
        blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=custom_sid,
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(
                workflow_owner="song_based_improvisation",
                workflow_session_id=custom_sid,
            ),
            source="t",
        )
        session["improv_song_source"] = "Active song"
        session["sbi_preview_source"] = "Active song"
        from backing_context import BACKING_CONTEXT_KEY

        session[BACKING_CONTEXT_KEY] = ctx.to_dict() if hasattr(ctx, "to_dict") else {
            "source": "song_improv",
            "sbi_material_kind": "custom",
            "sbi_source_owner": "Custom progression",
            "song_title": "My Progression",
            "active_song_id": "My Progression",
        }
        from backing_source_navigation import ensure_sbi_source_before_song_workflow

        ensure_sbi_source_before_song_workflow(session)
        result = activate_workflow_simple(
            session,
            "song_based_improvisation",
            activation_source="creative_tab_change",
            return_route="creative",
        )
        self.assertTrue(result.ok)
        self.assertFalse(activation_user_notice(session))
        status = sync_workflow_for_creative_tab(session, "Phrase / Motif")
        self.assertIn(status, {"skipped", "done", "queued"})
        self.assertFalse(activation_user_notice(session))
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

    def test_stale_mission_legacy_owner_does_not_abort_sbi_custom_return(self) -> None:
        """Leftover Missions owner vs song-based pointer must not abort Custom return."""
        from backing_context import BACKING_CONTEXT_KEY
        from backing_creative_return_route import apply_creative_return_route
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        session = _sbi_custom_session()
        catalog_sid = str(session["active_catalog_pick_key"])
        catalog_blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=catalog_sid,
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        )
        save_workflow_blob(session, catalog_blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(
                workflow_owner="song_based_improvisation",
                workflow_session_id=catalog_sid,
            ),
            source="t",
        )
        session[ACTIVE_WORKFLOW_OWNER_KEY] = "mission_jam"
        ctx = _custom_ctx()
        session[BACKING_CONTEXT_KEY] = {
            "source": "song_improv",
            "sbi_material_kind": "custom",
            "sbi_source_owner": "Custom progression",
            "song_title": "My Progression",
            "active_song_id": "My Progression",
        }
        apply_creative_return_route(
            session,
            {
                "intelligence_tab": "Entry & Jam",
                "entry_mode": "Song-Based Improvisation",
                "workflow_owner": "song_based_improvisation",
                "backing_source": "song_improv",
            },
            ctx=ctx,
        )
        self.assertFalse(activation_user_notice(session))
        self.assertEqual(session.get(ACTIVE_WORKFLOW_OWNER_KEY), "song_based_improvisation")
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "song_based_improvisation")
        self.assertTrue(str(ptr.workflow_session_id).startswith("custom|"))
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

        status = sync_workflow_for_creative_tab(session, "Phrase / Motif")
        self.assertIn(status, {"skipped", "done", "queued"})
        self.assertFalse(activation_user_notice(session))
        ptr_after = get_active_workflow_pointer(session)
        assert ptr_after is not None
        self.assertTrue(str(ptr_after.workflow_session_id).startswith("custom|"))

    def test_active_click_is_not_restored_from_stale_custom_backing_ctx(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            get_sbi_preview_source,
        )

        session = _sbi_custom_session()
        session["improv_song_source"] = "Active song"
        session["sbi_preview_source"] = "Active song"
        session["_pending_improv_song_source"] = "Active song"
        session[SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY] = True
        session["_restore_sbi_custom_source"] = False
        restore_sbi_song_source_from_backing_context(session, _custom_ctx())
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(get_sbi_preview_source(session), "Active song")
        self.assertFalse(session.get("_restore_sbi_custom_source"))

    def test_refresh_remount_keeps_persisted_active_over_stale_custom_ctx(self) -> None:
        """Custom→Active→refresh: seen is false; leftover Trial ctx must not restamp Custom."""
        from source_session_state import get_sbi_preview_source

        session = _sbi_custom_session()
        session["improv_song_source"] = "Active song"
        session["sbi_preview_source"] = "Active song"
        session["_last_improv_song_source"] = "Active song"
        session["_restore_sbi_custom_source"] = False
        session["_sbi_follow_active_widget_seen"] = False
        session.pop("_pending_improv_song_source", None)
        restore_sbi_song_source_from_backing_context(session, _custom_ctx())
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(get_sbi_preview_source(session), "Active song")
        self.assertNotEqual(session.get("_pending_improv_song_source"), "Custom progression")
        self.assertFalse(session.get("_restore_sbi_custom_source"))

    def test_mounted_custom_radio_still_restores_from_custom_ctx(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            get_sbi_preview_source,
        )

        session = _sbi_custom_session()
        session["improv_song_source"] = "Custom progression"
        session["sbi_preview_source"] = "Active song"
        session["_last_improv_song_source"] = "Active song"
        session["_restore_sbi_custom_source"] = False
        session[SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY] = True
        restore_sbi_song_source_from_backing_context(session, _custom_ctx())
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")
        self.assertEqual(session.get("improv_song_source"), "Custom progression")


if __name__ == "__main__":
    unittest.main()
