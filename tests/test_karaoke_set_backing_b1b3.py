"""Karaoke Set x Backing play session (user rules 2026-11-19, B1-B3).

Per entry (Start / Next / Previous / auto-advance): the entry's own groove and meter -- never the live Feel widget,
which still holds the previous entry's or Now Editing's -- and Full song. For the whole set: the repeat count
(1 at Start, carried, changed only by an explicit Loop Count change). End Set: ordinary Backing's Loop Count comes
back. Inside a set a song change is the set's per-entry initialization, not the ordinary song-change reset; End
Set handing Now Editing back is not a new song either.
"""
from __future__ import annotations

import unittest
from unittest import mock

import karaoke_mode as km
from active_song_transition import ACTIVE_SONG_ACTIVATION_EPOCH_KEY, ACTIVE_SONG_ACTIVATION_ID_KEY
from backing_play_session import (
    BACKING_PLAY_SESSION_KEY,
    BACKING_SETTINGS_ACTIVATION_EPOCH_KEY,
    _source_defaults_from_session,
    follow_active_song_activation,
)
from songs.playback_defaults import normalize_groove_label
from backing_track_state import (
    BACKING_STATE_KEY,
    KARAOKE_POST_SET_ADOPT_KEY,
    KARAOKE_PRE_SET_LOOPS_KEY,
    restore_pre_set_loops,
    snapshot_pre_set_loops,
)


def _ordinary(loops: int = 3, groove: str = "Jazz swing") -> dict:
    """Now Editing a jazz tune in ordinary Backing: Feel Jazz swing, Loop Count 3 (the acceptance's pre-set step)."""
    return {
        "instrument": "Voice",
        "studio_page": "backing",
        "backing_groove_style": groove,
        "backing_track_loops": loops,
        BACKING_STATE_KEY: {"backing_track_loops": loops, "backing_track_scope": "Full song"},
        ACTIVE_SONG_ACTIVATION_EPOCH_KEY: 7,
        ACTIVE_SONG_ACTIVATION_ID_KEY: "pk::jazz tune",
        BACKING_SETTINGS_ACTIVATION_EPOCH_KEY: 7,
        BACKING_PLAY_SESSION_KEY: {
            "play_session_id": "ps-0", "source_identity": "creative:regular_song:jazz tune", "expired": False,
            "defaults": {"bpm": 120, "groove": "Jazz swing", "meter": "4/4", "loops": 2}, "overrides": {"loops": loops},
        },
    }


def _entry(groove: str, meter: str = "4/4"):
    return mock.patch.multiple(
        km,
        resolve_karaoke_entry_groove=mock.Mock(return_value=groove),
        resolve_karaoke_entry_meter=mock.Mock(return_value=meter),
    )


class SetDefaultsPerEntry(unittest.TestCase):
    def test_entry_groove_and_meter_never_the_live_feel_widget(self) -> None:
        s = _ordinary()
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = True
        s[km.KARAOKE_SET_LOOPS_KEY] = 1
        with _entry("Pop", "4/4"):
            d = _source_defaults_from_session(s)
        self.assertEqual(d["groove"], normalize_groove_label("Pop"))   # not the Jazz swing left in the Feel widget
        self.assertNotEqual(d["groove"], normalize_groove_label("Jazz swing"))
        self.assertEqual(d["scope"], "Full song")
        with _entry("Bossa nova", "4/4"):
            self.assertEqual(_source_defaults_from_session(s)["groove"], normalize_groove_label("Bossa nova"))
        with _entry("Waltz", "3/4"):
            self.assertEqual(_source_defaults_from_session(s)["meter"], "3/4")

    def test_repeat_1_at_start_then_the_sets_count_is_carried(self) -> None:
        s = _ordinary()
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = True
        s[km.KARAOKE_SET_LOOPS_KEY] = km.KARAOKE_SET_LOOPS_DEFAULT
        with _entry("Pop"):
            self.assertEqual(_source_defaults_from_session(s)["loops"], 1)
            km.note_karaoke_set_loops(s, 2)            # the singer's explicit Loop Count change
            self.assertEqual(_source_defaults_from_session(s)["loops"], 2)   # the next entry starts at 2

    def test_outside_a_set_nothing_changes(self) -> None:
        s = _ordinary()
        with _entry("Pop"):
            d = _source_defaults_from_session(s)
        self.assertEqual(d["loops"], 2)
        self.assertEqual(d["groove"], normalize_groove_label("Jazz swing"))
        self.assertEqual(km.note_karaoke_set_loops(s, 5), 0)  # no-op outside a set
        self.assertNotIn(km.KARAOKE_SET_LOOPS_KEY, s)

    def test_a_set_on_another_instrument_is_not_a_karaoke_performance(self) -> None:
        s = _ordinary()
        s["instrument"] = "Alto Sax"
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = True
        s[km.KARAOKE_SET_LOOPS_KEY] = 1
        with _entry("Pop"):
            self.assertEqual(_source_defaults_from_session(s)["loops"], 2)


class SongChangeInsideASet(unittest.TestCase):
    def test_the_set_owns_a_song_change(self) -> None:
        s = _ordinary()
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = True
        s[km.KARAOKE_SET_LOOPS_KEY] = 2
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 8           # a Custom entry became active
        self.assertFalse(follow_active_song_activation(s))
        self.assertEqual(s[BACKING_SETTINGS_ACTIVATION_EPOCH_KEY], 8)   # adopted
        self.assertFalse(s[BACKING_PLAY_SESSION_KEY].get("expired"))
        self.assertNotIn("_pending_backing_loops", s)   # Backing's 2 never lands over the set's count

    def test_ordinary_song_change_still_resets(self) -> None:
        s = _ordinary()
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 8
        self.assertTrue(follow_active_song_activation(s))
        self.assertEqual(s["_pending_backing_loops"], 2)


class EndSetGivesTheLoopCountBack(unittest.TestCase):
    def _run_set(self, s: dict) -> None:
        snapshot_pre_set_loops(s)
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = True
        s[km.KARAOKE_SET_LOOPS_KEY] = 1
        s["backing_track_loops"] = 2                     # performed with the set's count, changed to 2
        snapshot_pre_set_loops(s)                        # a second call never overwrites the first snapshot
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = False
        s.pop(km.KARAOKE_SET_LOOPS_KEY, None)
        restore_pre_set_loops(s)

    def test_loop_count_3_comes_back(self) -> None:
        s = _ordinary(loops=3)
        self._run_set(s)
        self.assertEqual(s["_pending_backing_loops"], 3)
        self.assertEqual(s[BACKING_STATE_KEY]["backing_track_loops"], 3)
        self.assertEqual(s[BACKING_PLAY_SESSION_KEY]["overrides"].get("loops"), 3)
        self.assertNotIn(KARAOKE_PRE_SET_LOOPS_KEY, s)
        restore_pre_set_loops(s)                         # twice: safe
        self.assertEqual(s["_pending_backing_loops"], 3)

    def test_now_editing_given_back_is_not_a_new_song(self) -> None:
        s = _ordinary(loops=3)
        self._run_set(s)
        s.pop("_pending_backing_loops")
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 9          # the set moved the active song; End Set restores Jazz tune
        s[ACTIVE_SONG_ACTIVATION_ID_KEY] = "pk::jazz tune"
        self.assertFalse(follow_active_song_activation(s))
        self.assertNotIn("_pending_backing_loops", s)
        self.assertNotIn(KARAOKE_POST_SET_ADOPT_KEY, s)  # consumed once
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 10         # later: a real pick of the same song is a fresh start again
        self.assertTrue(follow_active_song_activation(s))

    def test_end_set_on_a_different_song_still_resets(self) -> None:
        s = _ordinary(loops=3)
        self._run_set(s)
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 9
        s[ACTIVE_SONG_ACTIVATION_ID_KEY] = "pk::trial song"
        self.assertTrue(follow_active_song_activation(s))


if __name__ == "__main__":
    unittest.main()
