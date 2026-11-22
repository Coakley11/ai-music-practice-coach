"""User rule 2026-11-21: every Karaoke entry starts at Repeat 1, whatever the song itself saves.

Measured on f7419c6f (390 px, Karaoke Set): Next to Trial Song - a Custom song saved with loops 2 - gave Repeat 2.
Its Backing context queued the song's own 2 after the entry activation had queued 1.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import karaoke_mode as km
from backing_context import _karaoke_entry_loops, apply_backing_context_to_session, build_entry_jam_context
from backing_play_session import BACKING_PLAY_SESSION_KEY
from custom_progression_lab import PENDING_BACKING_LOOPS


def _in_a_set(**extra) -> dict:
    """A real started three-song set (no queue = the set ends and End Set gives Backing's 2), plus a context."""
    from tests.test_karaoke_set_lifecycle import _new_set

    s = _new_set()
    km.start_session(s)
    s.update(_jam_session())
    s.update(extra)
    return s


def _jam_session(**extra) -> dict:
    s = {
        "active_catalog_pick_key": "say|artist", "song": "Say", "display_key": "F", "concert_key": "F",
        "improv_style": "Jazz Swing", "improv_style_meta": {"style": "Jazz Swing", "bpm": 90, "groove": "Medium"},
        "improv_style_key": "G",
    }
    s.update(extra)
    return s


def _apply(session: dict) -> dict:
    ctx = build_entry_jam_context(session)
    ctx.loops = 2                                  # the song's own saved Repeat (Trial Song's loops 2)
    with patch("backing_track_state.write_canonical_backing_state"):
        apply_backing_context_to_session(session, ctx, st_like=SimpleNamespace(session_state=session), widget_safe=True)
    return session


class TheEntryRepeatWins(unittest.TestCase):
    def test_outside_a_set_the_song_keeps_its_own_repeat(self) -> None:
        self.assertEqual(_apply(_jam_session()).get(PENDING_BACKING_LOOPS), 2)
        self.assertEqual(_karaoke_entry_loops({"instrument": "Voice"}, 3), 3)

    def test_a_new_karaoke_entry_starts_at_repeat_1(self) -> None:
        s = _in_a_set()
        s.pop(PENDING_BACKING_LOOPS, None)
        self.assertEqual(_apply(s).get(PENDING_BACKING_LOOPS), 1)

    def test_the_singers_repeat_for_this_performance_is_left_alone(self) -> None:
        s = _in_a_set()
        s.pop(PENDING_BACKING_LOOPS, None)
        s[BACKING_PLAY_SESSION_KEY] = {"play_session_id": "p", "expired": False,
                                      "defaults": {"loops": 1}, "overrides": {"loops": 2}}
        self.assertIsNone(_karaoke_entry_loops(s, 2))
        self.assertNotEqual(_apply(s).get(PENDING_BACKING_LOOPS), 1)

    def test_another_instrument_in_a_set_is_ordinary_backing(self) -> None:
        s = _jam_session(instrument="Alto Sax", **{km.KARAOKE_SESSION_ACTIVE_KEY: True, km.KARAOKE_SET_LOOPS_KEY: 1})
        self.assertEqual(_karaoke_entry_loops(s, 2), 2)


if __name__ == "__main__":
    unittest.main()
