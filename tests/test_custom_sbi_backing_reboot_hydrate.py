"""Unit proofs: Custom SBI Backing must not fall through to Catalog on reboot hydrate."""

from __future__ import annotations

import unittest


class CustomSbiBackingRebootHydrateTests(unittest.TestCase):
    def _custom_sbi_session(self) -> dict:
        from custom_progression_lab import CPL_ACTIVE_KEY

        shape = "Pop\x1fShape of You — Ed Sheeran"
        return {
            "studio_page": "backing",
            "active_catalog_pick_key": shape,
            "selected_song": {"title": "Shape of You — Ed Sheeran", "pick_key": shape},
            "display_key": "E",
            "concert_key": "E",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Entry & Jam",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "creative_workspace_state": {
                "improv_entry_mode": "Song-Based Improvisation",
                "improv_intelligence_tab": "Entry & Jam",
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
            },
            "_backing_open_intent": "restore_last",
            "_backing_explicit_handoff_source": "song_improv",
            "backing_context": {
                "source": "song_improv",
                "source_label": "Song-Based Improvisation",
                "song_title": "Trial Song",
                "active_song_id": "custom::trial-song",
                "bound_pick_key": "custom::trial-song",
                "custom_revision_id": "trial-rev-1",
                "key": "E",
                "display_key": "E",
                "concert_key": "E",
                "bpm": 113,
                "style": "Blues",
                "groove": "",
                "scope": "Full song",
                "loops": 2,
                "progression": ["E", "A", "B"],
                "progression_label": "Trial Song",
                "entry_mode": "Song-Based Improvisation",
                "mode_label": "Song-Based Improvisation",
            },
            "practice_key_by_source": {"custom::trial-song": "E"},
            CPL_ACTIVE_KEY: {
                "id": "trial-rev-1",
                "name": "Trial Song",
                "original_key_center": "C",
                "bpm": 113,
                "progression_style": "Blues",
                "original_sections": {"A": ["E", "A", "B"]},
            },
        }

    def test_nested_sbi_override_beats_stale_catalog_ctx(self) -> None:
        from backing_context import (
            catalog_or_custom_backing_is_authoritative,
            creative_nested_backing_should_override_catalog,
        )

        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Entry & Jam",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "creative_workspace_state": {
                "improv_entry_mode": "Song-Based Improvisation",
                "improv_intelligence_tab": "Entry & Jam",
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
            },
            "backing_context": {
                "source": "regular_song",
                "song_title": "Shape of You",
            },
        }
        self.assertTrue(creative_nested_backing_should_override_catalog(session))
        self.assertFalse(catalog_or_custom_backing_is_authoritative(session))

    def test_custom_sbi_valid_despite_catalog_global_active(self) -> None:
        from backing_context import (
            ctx_is_stale_creative_for_practice,
            get_backing_context,
            is_backing_context_valid,
        )

        session = self._custom_sbi_session()
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertTrue(is_backing_context_valid(session, ctx))
        self.assertFalse(ctx_is_stale_creative_for_practice(session, ctx))

    def test_hydrate_keeps_custom_sbi_over_catalog_global_active(self) -> None:
        from backing_context import (
            get_backing_context,
            hydrate_backing_context_after_restore,
            reconcile_backing_context_on_backing_page,
        )
        from backing_source_navigation import hydrate_backing_source_for_page

        session = self._custom_sbi_session()
        hydrate_backing_context_after_restore(session)
        hydrate_backing_source_for_page(session)
        reconcile_backing_context_on_backing_page(session)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(str(getattr(ctx, "source", "") or ""), "song_improv")
        self.assertIn("Trial", str(getattr(ctx, "song_title", "") or ""))
        self.assertEqual(int(getattr(ctx, "bpm", 0) or 0), 113)
        self.assertEqual(str(getattr(ctx, "style", "") or ""), "Blues")

    def test_mission_backing_not_stale_under_catalog_global_active(self) -> None:
        from backing_context import (
            ctx_is_stale_creative_for_practice,
            get_backing_context,
            is_backing_context_valid,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            "studio_page": "backing",
            "active_catalog_pick_key": shape,
            "improv_entry_mode": "Mission Mode",
            "improv_intelligence_tab": "Missions",
            "improv_active_mission": "mission-1",
            "_backing_explicit_handoff_source": "mission",
            "backing_context": {
                "source": "mission",
                "source_label": "Mission",
                "song_title": "Shape of You",
                "active_song_id": shape,
                "bound_pick_key": shape,
                "mission_id": "mission-1",
                "key": "Ab",
                "display_key": "Ab",
                "concert_key": "Ab",
                "bpm": 96,
                "style": "",
                "groove": "",
            },
        }
        ctx = get_backing_context(session)
        self.assertTrue(is_backing_context_valid(session, ctx))
        self.assertFalse(ctx_is_stale_creative_for_practice(session, ctx))


if __name__ == "__main__":
    unittest.main()
