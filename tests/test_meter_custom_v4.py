"""Custom songs use their own document meter in every Backing path (meter v4, F2).

Regression from meter v3: the play-session source default for a Custom song was
the transport "4/4", and once v3 stopped treating ``meter != default`` as an
override, the reset widgets / canonical blob were seeded with 4/4 for a 3/4 or
6/8 Custom song (badge 4/4, audio 20.2 s instead of 15.4 s for 8 bars @ 100).
"""

from __future__ import annotations

import types
import unittest

import backing_play_session as bps
from backing_context import build_custom_progression_context  # noqa: F401  (import check)
from custom_progression_lab import CPL_ACTIVE_KEY, default_active_progression
from songs.meter_state import (
    BACKING_METER_KEY,
    BACKING_METER_OVERRIDE_KEY,
    apply_backing_meter_for_song,
)
from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CUSTOM


def _custom_session(meter: str, name: str = "Waltz") -> dict:
    active = default_active_progression()
    active.update({"name": name, "time_signature": meter, "bpm": 100, "id": f"rev-{name}"})
    return {ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM, CPL_ACTIVE_KEY: active, "_canonical_active_backing_song_id": f"custom::{name}"}


class CustomSourceDefaultMeter(unittest.TestCase):
    def test_source_default_is_the_document_meter(self) -> None:
        for meter in ("3/4", "6/8", "2/4", "12/8", "4/4"):
            with self.subTest(meter=meter):
                self.assertEqual(bps._source_defaults_from_session(_custom_session(meter))["meter"], meter)

    def test_projecting_defaults_to_widgets_keeps_the_document_meter(self) -> None:
        for meter in ("3/4", "6/8"):
            with self.subTest(meter=meter):
                session = _custom_session(meter)
                bps._apply_defaults_to_widgets(session, bps._source_defaults_from_session(session))
                self.assertEqual(session[BACKING_METER_KEY], meter)
                self.assertFalse(session.get(BACKING_METER_OVERRIDE_KEY))

    def test_custom_is_not_a_fake_override_and_explicit_choice_is(self) -> None:
        session = _custom_session("3/4")
        session[BACKING_METER_KEY] = "3/4"
        session[BACKING_METER_OVERRIDE_KEY] = False
        bps.capture_backing_play_session_overrides(session, bpm=100)
        ov = bps.get_backing_play_session(session)["overrides"]
        self.assertNotIn("meter", ov)
        session[BACKING_METER_KEY] = "4/4"
        session[BACKING_METER_OVERRIDE_KEY] = True
        bps.capture_backing_play_session_overrides(session, bpm=100)
        ov = bps.get_backing_play_session(session)["overrides"]
        self.assertEqual((ov.get("meter"), ov.get("meter_override")), ("4/4", True))

    def test_catalog_song_after_custom_does_not_inherit_custom_meter(self) -> None:
        session = _custom_session("3/4")
        session[ACTIVE_MUSIC_SOURCE_KEY] = "catalog"
        session["active_catalog_pick_key"] = "PopPhotograph"
        self.assertEqual(bps._source_defaults_from_session(session)["meter"], "4/4")


class CustomContextMeter(unittest.TestCase):
    def test_apply_for_song_uses_document_meter_and_switch_resets(self) -> None:
        session: dict = {}
        st = types.SimpleNamespace(session_state=session)
        self.assertEqual(apply_backing_meter_for_song(st, song_id="custom::Waltz", default_time_signature="3/4")[:2], ("3/4", False))
        self.assertEqual(apply_backing_meter_for_song(st, song_id="pk::photo", default_time_signature="4/4")[:2], ("4/4", False))
        self.assertEqual(apply_backing_meter_for_song(st, song_id="custom::Jig", default_time_signature="6/8")[:2], ("6/8", False))


if __name__ == "__main__":
    unittest.main()
