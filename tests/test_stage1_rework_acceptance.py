"""Stage 1 rework: regressions found in manual browser acceptance of 64023a38."""

from __future__ import annotations

import inspect
import re
import unittest
from unittest import mock

from composition_document import bootstrap_from_vision

SAY = "Pop\x1fSay — John Mayer"


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


class _CaptureSt:
    def __init__(self) -> None:
        self.out: list[str] = []

    def markdown(self, text: str, **_kwargs) -> None:
        self.out.append(text)


def _blues_session() -> tuple[dict, dict]:
    from composition_session_state import set_active_document
    from composition_songs_bridge import commit_composition_active_song
    from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY, SOURCE_COMPOSITION

    doc = bootstrap_from_vision(
        genre="Blues", song_idea="rain", key="F major", bpm=96, meter="4/4", title="Blues Test"
    )
    ss: dict = {ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION}
    set_active_document(ss, doc, checkpoint=False)
    commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
    return ss, doc


class TestCatalogKeyOwnershipOnSongSwitch(unittest.TestCase):
    """A catalog song without its own saved key must not inherit the previous song's key."""

    def _catalog(self, **extra) -> dict:
        ss = {
            "active_catalog_pick_key": SAY,
            "active_music_source": "catalog_song",
            "display_key": "F",
            "concert_key": "F",
        }
        ss.update(extra)
        return ss

    def test_leftover_live_key_from_previous_source_is_not_adopted(self):
        from songs.key_state import get_authoritative_display_key

        self.assertEqual(get_authoritative_display_key(self._catalog(), original_key="G"), "G")

    def test_song_own_saved_practice_key_is_preserved(self):
        from songs.key_state import get_authoritative_display_key

        ss = self._catalog(practice_key_by_source={SAY: "F"})
        self.assertEqual(get_authoritative_display_key(ss, original_key="G"), "F")

    def test_explicit_commit_for_this_song_is_kept(self):
        from songs.key_state import get_authoritative_display_key

        ss = self._catalog(_pk_user_commit_pick=SAY, _pk_user_commit_token="F")
        self.assertEqual(get_authoritative_display_key(ss, original_key="G"), "F")


class TestSbiCompositionStyle(unittest.TestCase):
    """SBI Backing for a Blues composition must select the Blues groove, not Pop."""

    def test_style_groove_helper_reads_composition(self):
        from backing_context import _composition_style_groove_for_pick
        from composition_songs_bridge import composition_pick_key_for

        ss, doc = _blues_session()
        self.assertEqual(
            _composition_style_groove_for_pick(ss, composition_pick_key_for(doc)),
            ("Blues", "Blues groove"),
        )
        self.assertEqual(_composition_style_groove_for_pick(ss, SAY), ("", ""))

    def test_active_song_lane_uses_blues_groove(self):
        from backing_context import _backing_groove_style_from_ctx, build_song_improv_context

        ss, _doc = _blues_session()
        ss["backing_groove_style"] = "Pop groove"
        ctx = build_song_improv_context(ss)
        self.assertEqual(ctx.style, "Blues")
        self.assertEqual(_backing_groove_style_from_ctx(ctx), "Blues groove")

    def test_composition_lane_uses_blues_groove(self):
        from backing_context import _backing_groove_style_from_ctx, build_song_improv_context
        from composition_songs_bridge import composition_pick_key_for

        ss, doc = _blues_session()
        ss["backing_groove_style"] = "Pop groove"
        ss["improv_song_source"] = "Composition"
        ss["sbi_preview_source"] = "Composition"
        lane = {
            "title": "Blues Test",
            "original_key": "F",
            "display_key": "G",
            "pick_key": composition_pick_key_for(doc),
            "sections": {"Verse": ["G7", "C7", "G7", "D7"]},
        }
        with mock.patch("sbi_lane_practice_key.composition_lane_preview", return_value=lane), mock.patch(
            "source_session_state.composition_sbi_source_available", return_value=True
        ):
            ctx = build_song_improv_context(ss)
        self.assertEqual(ctx.concert_key, "G")
        self.assertEqual(ctx.style, "Blues")
        self.assertEqual(_backing_groove_style_from_ctx(ctx), "Blues groove")


class TestGuitarCapoOwnerAndShapes(unittest.TestCase):
    def _jam_left_on_creative(self, page: str) -> dict:
        return {
            "studio_page": page,
            "improv_entry_mode": "Jam Session Generator",
            "improv_intelligence_tab": "",
            "active_catalog_pick_key": SAY,
            "improv_jam_key": "C",
            "practice_key_by_source": {SAY: "F"},
        }

    def test_songs_page_capo_follows_song_not_leftover_jam(self):
        from guitar_capo import live_capo_shape_source_id, owner_guitar_concert_key

        ss = self._jam_left_on_creative("picker")
        self.assertEqual(live_capo_shape_source_id(ss), SAY)
        self.assertEqual(owner_guitar_concert_key(ss, fallback="F"), "F")

    def test_jam_owns_capo_while_on_creative(self):
        from guitar_capo import live_capo_shape_source_id

        self.assertTrue(live_capo_shape_source_id(self._jam_left_on_creative("creative")).startswith("generated::jam"))

    def test_concert_g_shape_c_is_capo_7_and_follows_cycle(self):
        from guitar_capo import capo_fret_for_shape, shape_chart_key_for_concert

        self.assertEqual(capo_fret_for_shape("G", "C"), 7)
        self.assertEqual(capo_fret_for_shape("F#", "C"), 6)
        self.assertEqual(capo_fret_for_shape("F", "C"), 5)
        self.assertEqual(shape_chart_key_for_concert("G", "C"), shape_chart_key_for_concert("F", "C"))

    def test_creative_preview_labels_guitar_shape_progression(self):
        from creative_key_sync import render_creative_progression_block

        ss = {"instrument": "Guitar", "guitar_capo_enabled": True, "guitar_capo_shape_key": "C", "display_key": "G"}
        st = _CaptureSt()
        render_creative_progression_block(st, ss, {"Verse": ["G7", "C7", "D7"]}, concert_key="G")
        text = "\n".join(st.out)
        self.assertIn("Practice concert key: <strong>G</strong>", text)
        self.assertIn("Concert Practice Key Progression:</strong> G7 · C7 · D7", text)
        self.assertIn("Guitar Shape Progression (C shapes, capo 7):</strong> C7 · F7 · G7", text)
        self.assertNotIn("Written Key Progression", text)


class TestGuitarInstrumentEntry(unittest.TestCase):
    def test_entering_guitar_starts_with_capo_off(self):
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            CAPO_ENABLED_WIDGET_KEY,
            reset_capo_on_guitar_entry,
        )

        ss = {
            CAPO_ENABLED_KEY: True,
            CAPO_ENABLED_WIDGET_KEY: True,
            "_pending_capo_enabled_widget": True,
            "active_song_state": {CAPO_ENABLED_KEY: True, "guitar_capo_shape_key": "C"},
        }
        reset_capo_on_guitar_entry(ss)
        self.assertFalse(ss[CAPO_ENABLED_KEY])
        self.assertFalse(ss[CAPO_ENABLED_WIDGET_KEY])
        self.assertNotIn("_pending_capo_enabled_widget", ss)
        self.assertFalse(ss["active_song_state"][CAPO_ENABLED_KEY])
        # Same marker a manual Off sets, so the saved-meta restore guard cannot re-enable it.
        self.assertTrue(ss["_capo_genuine_user_off"])

    def test_instrument_change_handler_source(self):
        from pathlib import Path

        src = Path(__file__).resolve().parents[1].joinpath("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        start = src.index("def _on_global_instrument_change")
        body = src[start : src.index("def _on_global_focus_change")]
        self.assertIn('if str(new_value) == "Guitar":', body)
        self.assertIn("reset_capo_on_guitar_entry(st.session_state)", body)


class TestWrittenChartsIconEverywhere(unittest.TestCase):
    def test_charts_field_uses_written_icon(self):
        from music_feature_icons import semantic_field_icon

        self.assertEqual(semantic_field_icon("charts"), "📝")

    def test_charts_label_never_uses_guitar_or_chart_glyph(self):
        from backing_context_ui import chart_badge_semantic_field

        self.assertEqual(chart_badge_semantic_field("Charts in", "shape"), "charts")
        self.assertEqual(chart_badge_semantic_field("Charts", "concert"), "charts")
        self.assertEqual(chart_badge_semantic_field("Shape Key", "shape"), "shape_key")
        self.assertEqual(chart_badge_semantic_field("Written key", "written"), "written_key")

    def test_backing_chart_header_and_active_song_card(self):
        import backing_display
        from songs import backing_chart

        self.assertTrue("📝 Charts in" in inspect.getsource(backing_chart), "backing chart header icon")
        self.assertTrue(
            "📝 Charts in" in inspect.getsource(backing_display.render_backing_active_song_card),
            "active song card charts icon",
        )


class TestSongAwareCoachingNav(unittest.TestCase):
    def test_icon_is_distinct(self):
        from music_feature_icons import FEATURE_ICONS, feature_label

        glyph = FEATURE_ICONS["song_aware_coaching"]
        others = [v for k, v in FEATURE_ICONS.items() if k != "song_aware_coaching"]
        self.assertNotIn(glyph, others)
        self.assertEqual(feature_label("song_aware_coaching", "Song-Aware Coaching"), f"{glyph} Song-Aware Coaching")

    def test_composition_studio_button_renamed_route_kept(self):
        import composition_studio_page

        src = inspect.getsource(composition_studio_page)
        self.assertNotIn('nav_icon_button_label("creative") + " Jam"', src)
        self.assertIn('"song_aware_coaching", "Song-Aware Coaching"', src)
        self.assertIn('key="composer_nav_jam"', src)
        self.assertIn('request_creative_entry_mode(session_state, "Style Jam Mode"', src)

    def test_entry_mode_request_survives_creative_restore(self):
        from creative_tab_tool_persistence import canonical_creative_selector_value
        from studio_page_state import ensure_improv_entry_mode_restored, request_creative_entry_mode

        ss: dict = {"improv_entry_mode": "Jam Session Generator", "studio_page": "creative"}
        request_creative_entry_mode(ss, "Style Jam Mode", reason="test")
        self.assertEqual(canonical_creative_selector_value(ss, "improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(ensure_improv_entry_mode_restored(ss), "Style Jam Mode")

    def test_song_card_action_row_has_button(self):
        from pathlib import Path

        src = Path(__file__).resolve().parents[1].joinpath("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        start = src.index("def _render_songs_hub_nav_actions")
        body = src[start : src.index("def _song_card_guidance_html")]
        self.assertIn('feature_label("song_aware_coaching", "Song-Aware Coaching")', body)
        self.assertIn('key=f"{key_prefix}_song_aware_coaching"', body)
        flat = re.sub(r"\(\s+", "(", body)  # dev wraps the call over several lines
        self.assertIn('request_creative_entry_mode(st.session_state, "Style Jam Mode"', flat)
        self.assertIn('_picker_navigate("creative")', body)


if __name__ == "__main__":
    unittest.main()
