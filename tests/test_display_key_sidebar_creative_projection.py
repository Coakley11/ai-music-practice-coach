"""Sidebar display key must survive Creative backing projection on next rerun."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from active_song_state import write_canonical_active_song_state
from backing_context import BACKING_CONTEXT_KEY, BackingContext
from creative_key_sync import prepare_backing_context_sidebar_display_key, user_sidebar_display_key_authoritative
from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY, mark_display_key_changed
from songs.music_source import ACTIVE_SONG_IDENTITY_KEY


class TestDisplayKeySidebarCreativeProjection(unittest.TestCase):
    def _session_dm_cloud_user_cm(self) -> dict[str, Any]:
        pick = "Traditional::Hevenu Shalom Aleichem"
        ss: dict[str, Any] = {
            "developer_mode": True,
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Song-Based Improvisation",
            "instrument": "Piano",
            "selected_transposing_instrument": "Alto saxophone (Eb)",
            "display_key": "Cm",
            "display_key_change_source": "sidebar_on_change",
            "active_catalog_pick_key": pick,
            "selected_song": {
                "title": "Hevenu Shalom Aleichem",
                "artist": "Traditional",
                "pick_key": pick,
                "key": "Cm",
            },
            ACTIVE_SONG_IDENTITY_KEY: pick,
            DISPLAY_KEY_OWNER_IDENTITY_KEY: pick,
            BACKING_CONTEXT_KEY: BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=pick,
                bound_pick_key=pick,
                song_title="Hevenu Shalom Aleichem",
                key="Cm",
                display_key="Dm",
                concert_key="Dm",
                bpm=100,
                style="",
                groove="",
                mission_id="test",
                progression=["Cm"],
                section="",
            ).to_dict(),
        }
        write_canonical_active_song_state(
            ss,
            {
                "pick_key": pick,
                "display_key": "Cm",
                "instrument": "Piano",
                "level": "Intermediate",
                "focus": "Melody",
                "selected_song": ss["selected_song"],
                "music_source": "catalog",
            },
            reason="test_setup",
            local_edit=False,
        )
        return ss

    def test_user_authoritative_detected_after_sidebar_change(self) -> None:
        ss = self._session_dm_cloud_user_cm()
        self.assertTrue(user_sidebar_display_key_authoritative(ss))

    def test_prepare_backing_context_preserves_cm_over_mission_dm(self) -> None:
        ss = self._session_dm_cloud_user_cm()
        st = MagicMock()
        st.session_state = ss
        options = prepare_backing_context_sidebar_display_key(st, ss)
        self.assertEqual(ss.get("display_key"), "Cm")
        self.assertIn("Cm", options)

    def test_dm_session_user_selects_cm_then_projection_preserves(self) -> None:
        """Regression: cloud/canonical Dm, user picks Cm on Creative Missions, projection must not revert."""
        pick = "Traditional::Hevenu Shalom Aleichem"
        ss: dict[str, Any] = {
            "developer_mode": True,
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Song-Based Improvisation",
            "instrument": "Piano",
            "display_key": "Dm",
            "active_catalog_pick_key": pick,
            "selected_song": {"pick_key": pick, "key": "Cm", "title": "Hevenu Shalom Aleichem"},
            ACTIVE_SONG_IDENTITY_KEY: pick,
            BACKING_CONTEXT_KEY: BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=pick,
                bound_pick_key=pick,
                song_title="Hevenu Shalom Aleichem",
                concert_key="Dm",
                display_key="Dm",
                key="Cm",
                style="",
                groove="",
                progression=["Cm", "G7"],
                bpm=100,
            ).to_dict(),
        }
        write_canonical_active_song_state(
            ss,
            {
                "pick_key": pick,
                "display_key": "Dm",
                "instrument": "Piano",
                "level": "Intermediate",
                "focus": "Melody",
                "selected_song": ss["selected_song"],
                "music_source": "catalog",
            },
            reason="test_dm_cloud",
            local_edit=False,
        )
        ss["display_key"] = "Cm"
        st = MagicMock()
        st.session_state = ss

        def _global_save(st_like: Any, *, reason: str = "") -> bool:
            from active_song_state import flush_global_control_edits

            flush_global_control_edits(st_like.session_state, reason=reason or "display_key_change")
            return True

        with unittest.mock.patch(
            "music_persistent_state.flush_global_control_edits_and_save",
            side_effect=_global_save,
        ):
            mark_display_key_changed(st)
        self.assertEqual(ss.get("display_key"), "Cm")
        self.assertEqual(ss.get("display_key_change_source"), "sidebar_on_change")
        options = prepare_backing_context_sidebar_display_key(st, ss)
        self.assertEqual(ss.get("display_key"), "Cm")
        self.assertIn("Cm", options)
        from active_song_state import canonical_active_song_context

        canon = canonical_active_song_context(ss)
        self.assertIsInstance(canon, dict)
        self.assertEqual(str(canon.get("display_key") or "").strip(), "Cm")

    def test_mark_display_key_changed_records_sidebar_source(self) -> None:
        ss: dict[str, Any] = {
            "display_key": "Cm",
            "instrument": "Piano",
            "active_catalog_pick_key": "Traditional::Hevenu Shalom Aleichem",
            "selected_song": {"pick_key": "Traditional::Hevenu Shalom Aleichem", "key": "Cm"},
        }
        st = MagicMock()
        st.session_state = ss
        with unittest.mock.patch(
            "music_persistent_state.flush_global_control_edits_and_save",
            return_value=True,
        ):
            mark_display_key_changed(st)
        self.assertEqual(ss.get("display_key_change_source"), "sidebar_on_change")

    def test_startup_fingerprint_allows_explicit_sidebar_display_key_save(self) -> None:
        from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY, should_suppress_music_workspace_save

        ss: dict[str, Any] = {
            STARTUP_FINGERPRINT_MATCHES_KEY: True,
            "display_key_change_source": "sidebar_on_change",
        }
        suppress, _why = should_suppress_music_workspace_save(ss, "display_key_change")
        self.assertFalse(suppress)


if __name__ == "__main__":
    unittest.main()
