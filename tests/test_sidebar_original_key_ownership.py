"""The sidebar Song Original Key belongs to the song that owns the surface.

Live first wrong step: Blues Test (Composition, Original F) on Backing showed
"Song Original Key: D". A Custom song (Original D) had been previewed in Creative
Song-Based Improvisation earlier; its sticky ``_sbi_custom_sidebar_overlay`` and
``improv_song_source = "Custom progression"`` survived, and on Backing the preview
surface predicate answered True for any context, so a late caption layer put the
Custom's D over the Composition's F (and kept it across Play, Key Cycling and
reload). Guitar Shape / capo / Key Cycling never feed the Original Key.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUES_PICK = "composition::4e89e7cc-ab9c-406f-9431-9bedb8732a22"
CUSTOM_PICK = "custom::5ac71a1a-0000-4000-8000-000000000001"


def _stale_custom_preview_flags() -> dict:
    return {
        "_sbi_custom_sidebar_overlay": True,
        "improv_song_source": "Custom progression",
        "sbi_preview_source": "Custom progression",
    }


def _composition_backing() -> dict:
    return {
        "studio_page": "backing",
        "active_music_source": "composition_song",
        "active_catalog_pick_key": BLUES_PICK,
        "backing_context": {"source": "composition_song", "active_song_id": BLUES_PICK, "song_title": "Blues Test",
                            "key": "F", "display_key": "G", "concert_key": "G"},
        **_stale_custom_preview_flags(),
    }


class TestBackingPreviewSurface(unittest.TestCase):
    def test_stale_custom_preview_does_not_speak_for_composition_backing(self) -> None:
        from source_session_state import custom_sbi_owns_sidebar_practice_key, sbi_custom_preview_surface_displayed

        ss = _composition_backing()
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(ss))
        self.assertFalse(sbi_custom_preview_surface_displayed(ss))

    def test_custom_backing_still_owns_its_surface(self) -> None:
        from source_session_state import custom_sbi_owns_sidebar_practice_key, sbi_custom_preview_surface_displayed

        for ctx in (
            {"source": "custom_progression", "active_song_id": CUSTOM_PICK},
            {"source": "song_improv", "active_song_id": CUSTOM_PICK},
        ):
            ss = {"studio_page": "backing", "active_catalog_pick_key": CUSTOM_PICK, "backing_context": ctx,
                  **_stale_custom_preview_flags()}
            self.assertTrue(custom_sbi_owns_sidebar_practice_key(ss), ctx)
            self.assertTrue(sbi_custom_preview_surface_displayed(ss), ctx)

    def test_leaving_the_preview_clears_the_sticky_overlay_on_composition_backing(self) -> None:
        from source_session_state import clear_sbi_custom_sidebar_overlay_if_needed

        ss = _composition_backing()
        clear_sbi_custom_sidebar_overlay_if_needed(ss)
        self.assertFalse(ss.get("_sbi_custom_sidebar_overlay"))

    def test_creative_sbi_custom_preview_surface_unchanged(self) -> None:
        from source_session_state import sbi_custom_preview_surface_displayed

        ss = {"studio_page": "creative", "improv_intelligence_tab": "Entry & Jam",
              "improv_entry_mode": "Song-Based Improvisation", **_stale_custom_preview_flags()}
        self.assertTrue(sbi_custom_preview_surface_displayed(ss))


class TestCompositionOriginalKeyIsItsOwn(unittest.TestCase):
    def test_shape_capo_and_key_cycling_never_change_the_original_key(self) -> None:
        from composition_songs_bridge import composition_source_original_key

        doc = {"id": "4e89e7cc-ab9c-406f-9431-9bedb8732a22", "title": "Blues Test",
               "global": {"original_key_center": "F", "original_key_label": "F major"}}
        session = {
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "D",
            "guitar_capo_sounding_key": "Ab",
            "display_key": "G",
            "practice_key_by_source": {BLUES_PICK: "G"},
            "backing_key_cycle_active": True,
            "backing_key_cycle_temp_key": "Ab",
        }
        self.assertEqual(composition_source_original_key(doc), "F")
        for shape in ("C", "D", "E", "G"):
            session["guitar_capo_shape_key"] = shape
            self.assertEqual(composition_source_original_key(doc), "F", shape)


class TestCaptionLayersInSource(unittest.TestCase):
    def test_overlay_caption_guard_needs_the_preview_surface(self) -> None:
        src = ROOT.joinpath("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        guard = src[src.index("as _cap_sbi_fn") :][:900]
        self.assertIn("sbi_custom_preview_surface_displayed as _cap_surface_fn", guard)
        self.assertIn("and _cap_surface_fn(st.session_state)", guard)
        # The late SBI Custom caption override also waits for the surface.
        late = src[src.index("sbi_custom_preview_surface_displayed as _sbi_surface_shown3") :][:900]
        self.assertIn("if _sbi_surface_now3 and", late)


if __name__ == "__main__":
    unittest.main()
