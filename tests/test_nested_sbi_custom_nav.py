"""Unit proofs for nested Creative → SBI → Custom navigation ownership."""

from __future__ import annotations

import unittest
from types import SimpleNamespace


class NestedSbiCustomNavTests(unittest.TestCase):
    def test_custom_sbi_backing_returns_to_creative_not_top_level_custom(self) -> None:
        from backing_source_navigation import (
            return_to_source_button_label,
            target_page_for_backing_context,
        )

        ctx = SimpleNamespace(
            source="song_improv",
            custom_revision_id="rev-1",
            active_song_id="custom::trial-song",
        )
        self.assertEqual(target_page_for_backing_context(ctx), "creative")
        label = return_to_source_button_label(ctx)
        self.assertIn("Creative", label)
        self.assertNotIn("Custom Page", label)

    def test_true_custom_progression_backing_still_returns_to_custom_page(self) -> None:
        from backing_source_navigation import (
            return_to_source_button_label,
            target_page_for_backing_context,
        )

        ctx = SimpleNamespace(source="custom_progression")
        self.assertEqual(target_page_for_backing_context(ctx), "custom")
        self.assertIn("Custom Page", return_to_source_button_label(ctx))

    def test_sbi_preview_source_not_inferred_from_cpl_session(self) -> None:
        from source_session_state import get_sbi_preview_source

        session = {
            "active_music_source": "catalog",
            "active_catalog_pick_key": "pop\x1fShape of You",
            "song": "Shape of You",
            # Live CPL draft present (LAST_CUSTOM memory) must not flip SBI tab.
            "cpl_active_progression": {"name": "Trial Song", "original_key_center": "E"},
            "studio_page": "creative",
        }
        self.assertEqual(get_sbi_preview_source(session), "Active song")

    def test_sbi_preview_source_respects_explicit_custom_tab(self) -> None:
        from source_session_state import get_sbi_preview_source, set_sbi_preview_source

        session: dict = {"studio_page": "creative"}
        set_sbi_preview_source(session, "Custom progression")
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")
        self.assertEqual(session.get("studio_page"), "creative")

    def test_creative_workspace_persists_sbi_source_keys(self) -> None:
        from creative_workspace_persistence import CREATIVE_WORKSPACE_KEYS

        self.assertIn("improv_song_source", CREATIVE_WORKSPACE_KEYS)
        self.assertIn("sbi_preview_source", CREATIVE_WORKSPACE_KEYS)

    def test_set_sbi_preview_marks_creative_dirty(self) -> None:
        from improvisation_mission_persistence import MISSION_LOCAL_DIRTY_KEY
        from source_session_state import set_sbi_preview_source

        session: dict = {"studio_page": "creative"}
        set_sbi_preview_source(session, "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertTrue(bool(session.get(MISSION_LOCAL_DIRTY_KEY)))

    def test_project_canonical_restores_sbi_custom_source(self) -> None:
        from creative_tab_tool_persistence import project_creative_selectors_from_canonical
        from creative_workspace_state_persistence import CREATIVE_WORKSPACE_STATE_KEY

        session: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
                "improv_entry_mode": "Song-Based Improvisation",
                "improv_intelligence_tab": "Entry & Jam",
            }
        }
        project_creative_selectors_from_canonical(session, overwrite=True)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")

    def test_open_custom_lab_pending_restores_sbi_custom(self) -> None:
        from studio_page_state import PENDING_IMPROV_SONG_SOURCE, flush_pending_improv_song_source

        session = {
            "sbi_preview_source": "Custom progression",
            PENDING_IMPROV_SONG_SOURCE: "Custom progression",
            "improv_song_source": "Active song",
            "_sbi_song_source_hydrated": False,
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")

    def test_restore_flag_does_not_override_explicit_active_once_hydrated(self) -> None:
        from studio_page_state import flush_pending_improv_song_source

        session = {
            "sbi_preview_source": "Custom progression",
            "improv_song_source": "Active song",
            "_restore_sbi_custom_source": True,
            "_sbi_song_source_hydrated": True,
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(session.get("sbi_preview_source"), "Active song")

    def test_fresh_sbi_custom_preview_uses_original_not_shape(self) -> None:
        from source_session_state import resolve_sbi_preview, sync_custom_session
        from tests.test_custom_sbi_split_brain import _shape_contaminated_session

        session = _shape_contaminated_session()
        session.pop("_sbi_custom_visit_pk", None)
        sync_custom_session(session)
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("title"), "Trial Song")
        self.assertTrue(str(preview.get("display_key") or "").upper().startswith("D"))
        self.assertNotEqual(str(preview.get("display_key") or "").lower(), "bm")

    def test_creative_snapshot_does_not_reclaim_active_over_custom(self) -> None:
        from studio_page_persistence import apply_page_snapshot

        session = {
            "sbi_preview_source": "Custom progression",
            "improv_song_source": "Custom progression",
        }
        apply_page_snapshot(
            session,
            {
                "improv_song_source": "Active song",
                "sbi_preview_source": "Active song",
            },
        )
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")

    def test_canonical_overwrite_does_not_clobber_live_sbi_custom(self) -> None:
        from creative_tab_tool_persistence import project_creative_selectors_from_canonical
        from creative_workspace_state_persistence import CREATIVE_WORKSPACE_STATE_KEY

        session = {
            CREATIVE_WORKSPACE_STATE_KEY: {"improv_song_source": "Active song"},
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
        }
        project_creative_selectors_from_canonical(session, overwrite=True)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")

    def test_canonical_overwrite_forces_custom_onto_active_widget(self) -> None:
        from creative_tab_tool_persistence import project_creative_selectors_from_canonical
        from creative_workspace_state_persistence import CREATIVE_WORKSPACE_STATE_KEY

        session = {
            CREATIVE_WORKSPACE_STATE_KEY: {"improv_song_source": "Active song"},
            "improv_song_source": "Active song",
            "sbi_preview_source": "Custom progression",
            "_restore_sbi_custom_source": True,
        }
        project_creative_selectors_from_canonical(session, overwrite=True)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")


if __name__ == "__main__":
    unittest.main()
