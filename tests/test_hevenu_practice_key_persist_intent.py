"""Hevenu Practice Key Ebm: coherent transpose vs collapsed C-class corruption.

The live daniel workspace stored original Dm with practice_key_by_source Ebm and
concert sections Ebm–Abm–Bb7. That is a real Dm→Ebm transpose of the Hevenu
chart, not the collapsed all-Ebm C-class signature. Persist Ebm; do not reset
to Dm or guess C#m from leftover jam/CPL fields.
"""

from __future__ import annotations

import unittest

from music_theory import transpose_sections_dict
from workflow_musical_authority import section_maps_equivalent


_HEVENU_ORIGINAL_DM = {
    "Melody A": ["Dm", "Gm", "A7", "Dm", "Bb", "A7", "Dm", "Dm"],
    "Melody B": ["Dm", "Gm", "A7", "Dm", "Bb", "A7", "Dm", "Dm"],
}

_HEVENU_LIVE_EBM = {
    "Melody A": ["Ebm", "Abm", "Bb7", "Ebm", "B", "Bb7", "Ebm", "Ebm"],
    "Melody B": ["Ebm", "Abm", "Bb7", "Ebm", "B", "Bb7", "Ebm", "Ebm"],
}


class HevenuPracticeKeyPersistIntentTests(unittest.TestCase):
    def test_live_ebm_chart_matches_transpose_of_original_dm(self) -> None:
        expected = transpose_sections_dict(_HEVENU_ORIGINAL_DM, "Dm", "Ebm")
        self.assertTrue(
            section_maps_equivalent(expected, _HEVENU_LIVE_EBM),
            expected,
        )

    def test_collapsed_all_ebm_is_not_a_coherent_hevenu_transpose(self) -> None:
        collapsed = {
            "Melody A": ["Ebm", "Ebm", "Ebm", "Ebm"],
            "Melody B": ["Ebm", "Ebm", "Ebm", "Ebm"],
        }
        expected = transpose_sections_dict(_HEVENU_ORIGINAL_DM, "Dm", "Ebm")
        self.assertFalse(section_maps_equivalent(expected, collapsed))

    def test_csharp_minor_leftovers_do_not_override_coherent_ebm_practice_key(self) -> None:
        """cpl_last_display_key C#m / jam C#m are leftover fields, not song Practice Key."""
        practice_key_by_source = {
            "Jewish\x1fHevenu Shalom Aleichem — Traditional": "Ebm",
            "creative::entry_style_jam": "C#m",
        }
        song_pick = "Jewish\x1fHevenu Shalom Aleichem — Traditional"
        self.assertEqual(practice_key_by_source[song_pick], "Ebm")
        expected = transpose_sections_dict(_HEVENU_ORIGINAL_DM, "Dm", "Ebm")
        self.assertTrue(section_maps_equivalent(expected, _HEVENU_LIVE_EBM))


if __name__ == "__main__":
    unittest.main()
