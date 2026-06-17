"""CPL sub-bar timing — no Streamlit widget key persistence regressions."""

from __future__ import annotations

import unittest

from chord_subdivisions import Subdivision, join_weighted_subdivisions
from custom_progression_lab import (
    CPL_TIMING_PANEL_FIX_ID,
    export_cpl_widget_state,
    import_cpl_widget_state,
    is_cpl_ephemeral_widget_key,
    purge_cpl_ephemeral_widget_keys,
)


class TestCplEphemeralWidgetKeys(unittest.TestCase):
    def test_timing_button_keys_are_ephemeral(self) -> None:
        for key in (
            "cpl_sub_half_Verse",
            "cpl_sub_thirds_Chorus",
            "cpl_sub_quarters_Bridge",
            "cpl_sub_push_Intro",
        ):
            self.assertTrue(is_cpl_ephemeral_widget_key(key), key)

    def test_pending_chord_keys_are_not_ephemeral(self) -> None:
        self.assertFalse(is_cpl_ephemeral_widget_key("cpl_pending_chord_Verse"))

    def test_legacy_blob_import_skips_timing_buttons(self) -> None:
        legacy = {
            "cpl_pending_chord_Verse": "G",
            "cpl_sub_half_Verse": True,
            "cpl_sub_thirds_Verse": False,
            "cpl_sub_quarters_Verse": False,
            "cpl_sub_push_Verse": False,
        }
        out: dict = {}
        import_cpl_widget_state(out, legacy)
        self.assertEqual(out.get("cpl_pending_chord_Verse"), "G")
        self.assertNotIn("cpl_sub_half_Verse", out)

    def test_purge_removes_restored_timing_button_keys(self) -> None:
        ss = {"cpl_sub_half_Verse": True, "cpl_pending_chord_Verse": "Am"}
        purge_cpl_ephemeral_widget_keys(ss)
        self.assertNotIn("cpl_sub_half_Verse", ss)
        self.assertEqual(ss["cpl_pending_chord_Verse"], "Am")

    def test_export_never_includes_timing_buttons(self) -> None:
        blob = export_cpl_widget_state(
            {
                "cpl_pending_chord_Verse": "C",
                "cpl_sub_half_Verse": True,
                "cpl_pick_practice_Verse_C": True,
            }
        )
        self.assertIn("cpl_pending_chord_Verse", blob)
        self.assertNotIn("cpl_sub_half_Verse", blob)
        self.assertNotIn("cpl_pick_practice_Verse_C", blob)

    def test_timing_fix_marker_present(self) -> None:
        self.assertIn("cpl-timing", CPL_TIMING_PANEL_FIX_ID)


class TestHalfBarTokenLogic(unittest.TestCase):
    def test_half_bar_token_format(self) -> None:
        token = join_weighted_subdivisions([
            Subdivision("C", 2.0, False),
            Subdivision("G", 2.0, False),
        ])
        self.assertEqual(token, "C:2|G:2")

    def test_push_token_format(self) -> None:
        token = join_weighted_subdivisions([
            Subdivision("C", 3.5, False),
            Subdivision("G", 0.5, True),
        ])
        self.assertIn("G:0.5p", token)


if __name__ == "__main__":
    unittest.main()
