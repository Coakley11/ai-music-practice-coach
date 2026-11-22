"""Karaoke Set x Backing play session (user rules 2026-11-19, B1-B3).

Per entry (Start / Next / Previous / auto-advance): the entry's own groove and meter -- never the live Feel widget,
which still holds the previous entry's or Now Editing's -- and Full song. For the whole set: the repeat count
(1 at Start, carried, changed only by an explicit Loop Count change). End Set: ordinary Backing's Loop Count comes
back -- superseded 2026-11-20: End Set returns Now Editing as an ordinary song with its normal defaults (2
repeats, Full song, the song's own BPM / groove / meter), never the set's values or a pre-set override. Inside a
set a song change is the set's per-entry initialization, not the ordinary song-change reset.
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
    reset_backing_after_karaoke_set,
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

    def test_every_entry_starts_at_repeat_1_a_change_is_not_carried(self) -> None:
        # User rule 2026-11-21 (supersedes 2026-11-19's carried set count): a Repeat change is the sung
        # song's performance only; the next entry starts at Repeat 1.
        s = _ordinary()
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = True
        s[km.KARAOKE_SET_LOOPS_KEY] = km.KARAOKE_SET_LOOPS_DEFAULT
        with _entry("Pop"):
            self.assertEqual(_source_defaults_from_session(s)["loops"], 1)
            self.assertEqual(km.note_karaoke_set_loops(s, 2), 2)   # the singer's explicit Loop Count change
            self.assertEqual(_source_defaults_from_session(s)["loops"], 1)   # the next entry starts at 1

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


class EndSetGivesOrdinaryDefaults(unittest.TestCase):
    """User rule 2026-11-20 (replaces 'End Set restores the pre-set Loop Count')."""

    def _end_set(self, s: dict) -> None:
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = True
        s[km.KARAOKE_SET_LOOPS_KEY] = 1
        s["backing_track_loops"] = 1                     # performed with the set's count
        s[km.KARAOKE_SESSION_ACTIVE_KEY] = False         # stop_session drops the flag first ...
        s.pop(km.KARAOKE_SET_LOOPS_KEY, None)
        reset_backing_after_karaoke_set(s)               # ... then calls this

    def test_contaminated_start_ends_on_two_repeats_full_song_and_a_fresh_play_session(self) -> None:
        s = _ordinary(loops=3)                           # Jazz tune Now Editing, Jazz swing, Loop 3 before the set
        s[BACKING_STATE_KEY]["backing_track_scope"] = "Selected sections"
        self._end_set(s)
        self.assertEqual(s["_pending_backing_loops"], 2)          # never 1 (the set's) nor 3 (the pre-set value)
        self.assertEqual(s[BACKING_STATE_KEY]["backing_track_loops"], 2)
        self.assertEqual(s[BACKING_STATE_KEY]["backing_track_scope"], "Full song")
        self.assertTrue(s[BACKING_PLAY_SESSION_KEY].get("expired"))   # the next run starts the song's own session

    def test_the_fresh_session_takes_the_songs_own_groove_not_the_sets(self) -> None:
        s = _ordinary(loops=3, groove="Jazz swing")      # the Feel widget still holds the set's Jazz swing
        self._end_set(s)
        ctx = mock.Mock(source="regular_song", style="Rock", groove="", meter="4/4", bpm=138)
        with mock.patch("backing_context.get_backing_context", return_value=ctx):
            d = _source_defaults_from_session(s)
        self.assertEqual(d["groove"], normalize_groove_label("Rock"))
        self.assertEqual(d["loops"], 2)
        self.assertEqual(d["scope"], "Full song")

    def test_end_set_is_not_counted_again_as_a_song_change_on_the_next_run(self) -> None:
        s = _ordinary(loops=3)
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 9          # the set moved the active song
        self._end_set(s)
        self.assertEqual(s[BACKING_SETTINGS_ACTIVATION_EPOCH_KEY], 9)
        s.pop("_pending_backing_loops")
        self.assertFalse(follow_active_song_activation(s))
        self.assertNotIn("_pending_backing_loops", s)

    def test_now_editing_handed_back_afterwards_gets_the_same_ordinary_defaults(self) -> None:
        s = _ordinary(loops=3)
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 9
        self._end_set(s)
        s.pop("_pending_backing_loops")
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 10         # End Set gives Now Editing (Jazz tune) back
        s[ACTIVE_SONG_ACTIVATION_ID_KEY] = "pk::jazz tune"
        self.assertTrue(follow_active_song_activation(s))   # no pre-set adoption any more: an ordinary fresh start
        self.assertEqual(s["_pending_backing_loops"], 2)

    def test_retired_pre_set_loop_hooks_never_bring_a_pre_set_count_back(self) -> None:
        s = _ordinary(loops=3)
        snapshot_pre_set_loops(s)
        s["backing_track_loops"] = 1
        restore_pre_set_loops(s)
        self.assertNotIn("_pending_backing_loops", s)
        self.assertNotIn(KARAOKE_PRE_SET_LOOPS_KEY, s)
        self.assertNotIn(KARAOKE_POST_SET_ADOPT_KEY, s)

if __name__ == "__main__":
    unittest.main()
