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


if __name__ == "__main__":
    unittest.main()
