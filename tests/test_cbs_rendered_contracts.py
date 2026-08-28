"""Lock the live-QA mixed-state strings that helper tests previously missed."""

from __future__ import annotations

import unittest

from cbs_rendered_contracts import (
    backing_must_be_trial_custom,
    catalog_shape_backing_banner,
    finished_main_has_songs_and_practice,
    mixed_state_failures,
    trial_preview_shows_shape_practice_key,
)


DANIEL_CUSTOM_FINISH = """
Trial Song
Original key D major · Practice / Concert Key B minor
Em Em D D
ACTIVE SONG
Shape of You — Ed Sheeran
Song Original Key: Bm
Practice / Concert Key Bm
Set as Active Song
Backing
"""

DANIEL_CUSTOM_BACKING = """
Backing source: Catalog song · Shape of You · Bm · 100 BPM
ACTIVE SONG · BACKING TRACK
Shape of You — Ed Sheeran · Catalog song
Original Key: Bm
Practice / Concert Key: Bm
Return to Song Catalog
Trial Song — Your progression
Trial Song · Custom
Song Original Key: Bm
Practice / Concert Key D
"""


class TestCbsRenderedContracts(unittest.TestCase):
    def test_finish_preview_bm_is_a_failure(self) -> None:
        self.assertTrue(trial_preview_shows_shape_practice_key(DANIEL_CUSTOM_FINISH))
        errs = mixed_state_failures(body=DANIEL_CUSTOM_FINISH, main=DANIEL_CUSTOM_FINISH, surface="custom_page")
        self.assertTrue(errs)

    def test_catalog_backing_from_trial_is_a_failure(self) -> None:
        self.assertTrue(catalog_shape_backing_banner(DANIEL_CUSTOM_BACKING))
        self.assertTrue(backing_must_be_trial_custom(DANIEL_CUSTOM_BACKING))
        errs = mixed_state_failures(
            body=DANIEL_CUSTOM_BACKING,
            main=DANIEL_CUSTOM_BACKING,
            sidebar="Trial Song — Your progression\nTrial Song · Custom\nSong Original Key: Bm",
            surface="custom_backing",
        )
        self.assertTrue(any("Catalog song" in e or "Return to Song Catalog" in e or "sidebar" in e.lower() for e in errs))

    def test_healthy_trial_backing_passes(self) -> None:
        healthy = """
        Backing source: Custom progression · Trial Song · D · 100 BPM
        BLUE_CARD source=custom_progression title=Trial Song original=D pk=D
        Return to Custom Page
        SIDEBAR_TITLE Trial Song
        SIDEBAR_ORIGINAL D
        SIDEBAR_PK D
        """
        self.assertEqual(backing_must_be_trial_custom(healthy), [])
        self.assertEqual(
            mixed_state_failures(body=healthy, main=healthy, sidebar=healthy, surface="custom_backing"),
            [],
        )

    def test_finished_buttons_require_songs_and_practice(self) -> None:
        self.assertFalse(finished_main_has_songs_and_practice(["Set as Active Song", "Backing"]))
        self.assertTrue(
            finished_main_has_songs_and_practice(["🎼 Songs", "🎯 Practice", "Set as Active Song", "🎧 Backing"])
        )


if __name__ == "__main__":
    unittest.main()
