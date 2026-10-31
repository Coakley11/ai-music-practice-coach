"""A tapped Custom library row must activate even when an older Catalog pick is on record."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from custom_progression_lab import CPL_SAVED_KEY, save_progression
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    EXPLICIT_CATALOG_SELECTION_EPOCH_KEY,
    EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY,
    PENDING_CUSTOM_LIBRARY_ACTION_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    apply_pending_custom_library_action_before_widgets,
    queue_custom_library_action,
)


def _session_after_catalog_pick() -> tuple[dict, MagicMock]:
    saved: dict = {}
    save_progression(
        saved,
        "Row Song",
        {
            "id": "row-1",
            "name": "Row Song",
            "original_key_center": "C",
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}, {"chord": "Am", "bars": 1}]},
        },
    )
    session: dict = {
        CPL_SAVED_KEY: saved,
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        EXPLICIT_CATALOG_SELECTION_EPOCH_KEY: 200.0,
        EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY: 100.0,
        "instrument": "Piano",
    }
    st = MagicMock()
    st.session_state = session
    return session, st


class TestCustomRowActivation(unittest.TestCase):
    def test_stale_queue_is_still_discarded(self) -> None:
        session, st = _session_after_catalog_pick()
        queue_custom_library_action(st, name="Row Song", action="activate")
        applied = apply_pending_custom_library_action_before_widgets(st, invalidate_backing=lambda _s: None)
        self.assertFalse(applied)
        self.assertNotIn(PENDING_CUSTOM_LIBRARY_ACTION_KEY, session)
        self.assertEqual(session[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CATALOG)

    def test_tapped_row_activates_despite_older_catalog_epoch(self) -> None:
        session, st = _session_after_catalog_pick()
        queue_custom_library_action(st, name="Row Song", action="activate", explicit=True)
        applied = apply_pending_custom_library_action_before_widgets(st, invalidate_backing=lambda _s: None)
        self.assertTrue(applied)
        self.assertEqual(session[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CUSTOM)
        self.assertNotIn(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY, session)
        self.assertEqual(session["cpl_active_progression"]["name"], "Row Song")


if __name__ == "__main__":
    unittest.main()
