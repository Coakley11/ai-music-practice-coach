"""Song-Aware Coaching navigation: Songs, Custom and Composition entry points."""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _nav_row_source() -> str:
    src = ROOT.joinpath("streamlit_music_practice_app.py").read_text(encoding="utf-8")
    start = src.index("def _render_songs_hub_nav_actions")
    return src[start : src.index("def _song_card_guidance_html")]


class TestSongAwareCoachingLabel(unittest.TestCase):
    def test_icon_is_distinct(self):
        from music_feature_icons import FEATURE_ICONS, feature_label

        glyph = FEATURE_ICONS["song_aware_coaching"]
        others = [v for k, v in FEATURE_ICONS.items() if k != "song_aware_coaching"]
        self.assertNotIn(glyph, others)
        self.assertEqual(
            feature_label("song_aware_coaching", "Song-Aware Coaching"),
            f"{glyph} Song-Aware Coaching",
        )


class TestCreativeEntryModeRequest(unittest.TestCase):
    def test_request_beats_previously_saved_creative_mode(self):
        from creative_tab_tool_persistence import (
            canonical_creative_selector_value,
            commit_creative_selector_to_canonical,
        )
        from studio_page_state import ensure_improv_entry_mode_restored, request_creative_entry_mode

        ss: dict = {"studio_page": "creative"}
        commit_creative_selector_to_canonical(ss, "improv_entry_mode", "Jam Session Generator", reason="prior")
        commit_creative_selector_to_canonical(ss, "improv_intelligence_tab", "Theory", reason="prior")
        self.assertEqual(ensure_improv_entry_mode_restored(ss), "Jam Session Generator")

        request_creative_entry_mode(ss, "Style Jam Mode", reason="test")
        self.assertEqual(canonical_creative_selector_value(ss, "improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(canonical_creative_selector_value(ss, "improv_intelligence_tab"), "Entry & Jam")
        self.assertEqual(ensure_improv_entry_mode_restored(ss), "Style Jam Mode")
        self.assertEqual(ss["improv_entry_mode"], "Style Jam Mode")


class TestCustomGate(unittest.TestCase):
    def test_radio_alone_is_not_ready(self):
        from songs.music_source import custom_song_ready_for_coaching

        ss: dict = {"active_music_source": "custom_progression", "active_catalog_pick_key": ""}
        self.assertFalse(custom_song_ready_for_coaching(ss))

    @staticmethod
    def _committed(sections: dict) -> dict:
        return {
            "active_music_source": "custom_progression",
            "active_catalog_pick_key": "custom::abc123",
            "active_song_state": {"music_source": "custom_progression", "pick_key": "custom::abc123"},
            "cpl_active_progression": {"id": "abc123", "name": "Trial", "original_sections": sections},
        }

    def test_draft_loaded_without_set_active_is_not_ready(self):
        from songs.music_source import custom_song_ready_for_coaching

        ss = self._committed({"Verse": [{"chord": "D", "bars": 1}]})
        ss["cpl_active_progression"] = {"id": "other", "name": "Other", "original_sections": {"Verse": [{"chord": "E"}]}}
        self.assertFalse(custom_song_ready_for_coaching(ss))

    def test_committed_custom_with_chords_is_ready(self):
        from songs.music_source import custom_song_ready_for_coaching

        ss = self._committed({"Verse": [{"chord": "D", "bars": 1}, {"chord": "G", "bars": 1}]})
        self.assertTrue(custom_song_ready_for_coaching(ss))

    def test_auto_promoted_blank_progression_is_not_ready(self):
        from custom_progression_lab import default_active_progression
        from songs.music_source import custom_song_ready_for_coaching

        ss = self._committed(default_active_progression()["original_sections"])
        self.assertFalse(custom_song_ready_for_coaching(ss))

    def test_catalog_or_composition_owner_is_not_ready(self):
        from songs.music_source import custom_song_ready_for_coaching

        self.assertFalse(
            custom_song_ready_for_coaching(
                {"active_music_source": "catalog", "active_catalog_pick_key": "Pop\x1fSay — John Mayer"}
            )
        )
        self.assertFalse(
            custom_song_ready_for_coaching(
                {"active_music_source": "custom_progression", "active_catalog_pick_key": "composition::c1"}
            )
        )


class TestEntryPointsInSource(unittest.TestCase):
    def test_songs_hub_row_has_one_coaching_button(self):
        body = _nav_row_source()
        self.assertEqual(body.count('feature_label("song_aware_coaching", "Song-Aware Coaching")'), 1)
        self.assertIn('key=f"{key_prefix}_song_aware_coaching"', body)
        self.assertIn('"Style Jam Mode"', body)
        self.assertIn("request_creative_entry_mode(", body)
        self.assertIn('_picker_navigate("creative")', body)

    def test_custom_hub_gates_button_on_active_custom(self):
        src = ROOT.joinpath("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        start = src.index('key_prefix="custom_hub"')
        self.assertIn("show_song_aware_coaching=custom_song_ready_for_coaching(st.session_state)", src[start : start + 200])

    def test_custom_lab_button_gated_and_routes_to_style_jam(self):
        src = ROOT.joinpath("cpl_page_ui.py").read_text(encoding="utf-8")
        self.assertEqual(src.count('key="cpl_song_aware_coaching"'), 1)
        btn = src[src.index("_coaching_ready = custom_song_ready_for_coaching(st.session_state)") :][:500]
        self.assertIn("if _coaching_ready and st.button(", btn)
        self.assertIn("_open_song_aware_coaching()", btn)
        fn = src[src.index("def _open_song_aware_coaching") :][:600]
        self.assertIn('request_creative_entry_mode(st.session_state, "Style Jam Mode"', fn)
        self.assertIn('navigate_studio_page(st.session_state, "creative")', fn)

    def test_composition_studio_button_renamed_route_kept(self):
        import composition_studio_page

        src = inspect.getsource(composition_studio_page)
        self.assertNotIn('nav_icon_button_label("creative") + " Jam"', src)
        self.assertIn('key="composer_nav_jam"', src)
        jam = src[src.index('key="composer_nav_jam"') - 200 :][:700]
        self.assertIn('"song_aware_coaching", "Song-Aware Coaching"', jam)
        self.assertIn('request_creative_entry_mode(session_state, "Style Jam Mode"', jam)


if __name__ == "__main__":
    unittest.main()
