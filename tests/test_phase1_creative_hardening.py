"""Phase 1 hardening — Creative page restore and global controls."""

from __future__ import annotations

import unittest

from creative_workspace_state_persistence import (
    CREATIVE_SESSION_KEY,
    CREATIVE_WORKSPACE_RESTORED_KEY,
    CREATIVE_WORKSPACE_STATE_KEY,
    apply_creative_workspace_to_session,
    default_creative_workspace_state,
    prepare_creative_workspace_for_render,
)
from improvisation_motif import chord_tone_names
from music_theory import spell_chord_tones
from studio_nav_state import STUDIO_NAV_STATE_KEY, prepare_studio_nav


class TestCreativePageRestore(unittest.TestCase):
    def test_canonical_creative_wins_over_stale_practice_default(self) -> None:
        ss: dict = {
            "studio_page": "practice",
            STUDIO_NAV_STATE_KEY: {"studio_page": "creative", "page": "creative"},
            "_suite_page_overwrite_source": "workspace_blob",
        }
        page = prepare_studio_nav(ss)
        self.assertEqual(page, "creative")
        self.assertEqual(ss.get("studio_page"), "creative")


class TestGlobalControlsCreativeIsolation(unittest.TestCase):
    def test_creative_restore_does_not_clobber_instrument(self) -> None:
        blob = {
            **default_creative_workspace_state(),
            CREATIVE_SESSION_KEY: {"instrument": "Saxophone", "tool_type": "mission", "entry_mode": "x"},
            "improv_intelligence_tab": "Missions",
        }
        ss: dict = {"instrument": "Piano", "level": "Intermediate", "focus": "Rhythm"}
        apply_creative_workspace_to_session(ss, blob, source="cloud_restore")
        self.assertTrue(ss.get(CREATIVE_WORKSPACE_RESTORED_KEY))
        prepare_creative_workspace_for_render(ss)
        self.assertEqual(ss.get("instrument"), "Piano")
        self.assertEqual(ss.get("improv_intelligence_tab"), "Missions")
        self.assertFalse(ss.get(CREATIVE_WORKSPACE_RESTORED_KEY))

    def test_prepare_active_song_does_not_reproject_globals_after_restore_gate(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY, prepare_active_song_context
        from music_restore_phase import mark_global_controls_restore_projection_complete

        ss: dict = {
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "Rhythm",
            ACTIVE_SONG_STATE_KEY: {
                "instrument": "Saxophone",
                "level": "Advanced",
                "focus": "Tone",
                "pick_key": "pop::test",
            },
            "_cloud_workspace_restored_this_run": True,
        }
        mark_global_controls_restore_projection_complete(ss)
        prepare_active_song_context(ss)
        self.assertEqual(ss.get("instrument"), "Piano")
        self.assertEqual(ss.get("level"), "Intermediate")
        self.assertEqual(ss.get("focus"), "Rhythm")


class TestCreativePageRefreshFromPayload(unittest.TestCase):
    def test_hydrated_creative_page_survives_prepare_studio_nav(self) -> None:
        ss: dict = {
            "studio_page": "practice",
            "_music_hydrated_studio_page": "creative",
            "studio_nav_state": {"studio_page": "creative", "page": "creative"},
            "_suite_page_overwrite_source": "workspace_blob",
        }
        from music_restore_phase import mark_studio_page_restore_projection_complete

        mark_studio_page_restore_projection_complete(ss)
        page = prepare_studio_nav(ss)
        self.assertEqual(page, "creative")
        self.assertEqual(ss.get("studio_page"), "creative")


class TestChordSpelling(unittest.TestCase):
    def test_e_major_in_a_minor(self) -> None:
        self.assertEqual(chord_tone_names("E", reference_key="Am")[:3], ["E", "G#", "B"])
        self.assertEqual(spell_chord_tones("E", reference_key="Am")[:3], ["E", "G#", "B"])

    def test_e7_in_a_minor(self) -> None:
        tones = chord_tone_names("E7", reference_key="Am")
        self.assertEqual(tones[:4], ["E", "G#", "B", "D"])

    def test_eb_major_retains_flats(self) -> None:
        self.assertEqual(spell_chord_tones("Eb", reference_key="Eb")[:3], ["Eb", "G", "Bb"])

    def test_am_harmonic_minor_g_sharp(self) -> None:
        from improvisation_intelligence import spell_scale_notes

        notes = spell_scale_notes("A", "harmonic_minor", "Am")
        self.assertIn("G#", notes)
        self.assertNotIn("Ab", notes)


if __name__ == "__main__":
    unittest.main()
