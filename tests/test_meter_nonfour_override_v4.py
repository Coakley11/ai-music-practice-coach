"""Explicit NON-4/4 meter overrides survive the radio key being dropped (meter v4, F1).

While another page is shown Streamlit drops the ``backing_time_signature`` radio
key but the override flag/tag survive. ``gather_backing_filters`` then produced
``meter=None`` -> ``_normalize_filters`` stamped "4/4", and the save on the
Songs page ("music_source_switch") rewrote the blob to ``(4/4, True)``. "Load
Last Song" then saw an override equal to Photograph's own 4/4 (no effect) or,
for Piano Man 3/4 -> 6/8, a 4/4 override -- the choice was lost. A 4/4 override
only appeared to work because 4/4 is the fallback value.
"""

from __future__ import annotations

import unittest

from backing_track_state import (
    BACKING_STATE_KEY,
    commit_backing_state_from_session,
    gather_backing_filters,
)
from songs.meter_state import BACKING_METER_KEY, BACKING_METER_OVERRIDE_KEY, BACKING_METER_OVERRIDE_SONG_KEY
from tests.test_meter_override_v3 import PERFECT, PHOTO, PM, _hydrated, _load_song

CASES = (
    (PHOTO, "Photograph", "4/4", "3/4"),
    (PHOTO, "Photograph", "4/4", "2/4"),
    (PM, "Piano Man", "3/4", "6/8"),
    (PM, "Piano Man", "3/4", "4/4"),
    (PM, "Piano Man", "3/4", "12/8"),
    (PERFECT, "Perfect", "6/8", "3/4"),
    (PERFECT, "Perfect", "6/8", "4/4"),
)


def _off_page(session: dict) -> dict:
    """Streamlit dropped the radio key while the Songs page is shown."""
    session.pop(BACKING_METER_KEY, None)
    return session


class DroppedRadioKeyKeepsSavedMeter(unittest.TestCase):
    def test_gather_uses_saved_meter_when_radio_key_missing_and_override_true(self) -> None:
        for sid, _t, _d, chosen in CASES:
            with self.subTest(song=sid, chosen=chosen):
                session = _off_page(_hydrated(chosen, True, sid))
                f = gather_backing_filters(session)
                self.assertEqual((f["backing_time_signature"], f["backing_time_signature_override"]), (chosen, True))

    def test_missing_key_without_override_is_still_the_default(self) -> None:
        session = _off_page(_hydrated("4/4", False, ""))
        f = gather_backing_filters(session)
        self.assertEqual((f["backing_time_signature"], f["backing_time_signature_override"]), ("4/4", False))

    def test_autosave_off_page_keeps_the_blob(self) -> None:
        for sid, _t, _d, chosen in CASES:
            with self.subTest(song=sid, chosen=chosen):
                session = _off_page(_hydrated(chosen, True, sid))
                commit_backing_state_from_session(session, reason="music_source_switch")
                blob = session[BACKING_STATE_KEY]
                self.assertEqual(
                    (blob["backing_time_signature"], blob["backing_time_signature_override"], blob[BACKING_METER_OVERRIDE_SONG_KEY]),
                    (chosen, True, sid),
                )

    def test_load_last_song_after_leaving_backing_restores_any_meter(self) -> None:
        for sid, title, default, chosen in CASES:
            with self.subTest(song=sid, chosen=chosen):
                session = _off_page(_hydrated(chosen, True, sid))
                commit_backing_state_from_session(session, reason="music_source_switch")
                applied, override, song_default = _load_song(session, sync_id=sid, title=title, meter=default)
                self.assertEqual((applied, override, song_default), (chosen, True, default))
                self.assertEqual(session[BACKING_METER_KEY], chosen)
                self.assertTrue(session[BACKING_METER_OVERRIDE_KEY])
                self.assertEqual(session[BACKING_METER_OVERRIDE_SONG_KEY], sid)

    def test_other_song_still_does_not_inherit(self) -> None:
        session = _off_page(_hydrated("6/8", True, PM))
        commit_backing_state_from_session(session, reason="music_source_switch")
        applied, override, _ = _load_song(session, sync_id=PHOTO, title="Photograph", meter="4/4")
        self.assertEqual((applied, override), ("4/4", False))


if __name__ == "__main__":
    unittest.main()
