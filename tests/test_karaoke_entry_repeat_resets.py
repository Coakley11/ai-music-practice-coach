"""User rule 2026-11-21: every Karaoke Set entry starts at Repeat 1, and a Repeat change is the current song's only.

Measured on dev f1e8941a (390 px, isolated data6): Blackbird opened the set at Repeat 2 (ordinary Backing's 2 left in
the Loop Count widget) and Next to Trial Song kept 2. The entry activation reset the scope, the BPM and the play
session but never the Loop Count widget, and the new play session read the stale 2 back as the singer's override.
"""
from __future__ import annotations

import unittest

import karaoke_mode as km
from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition


def _set_session(loops: int) -> dict:
    """A real three-song set, started (Shallow first), with the Loop Count widget at ``loops``."""
    from tests.test_karaoke_set_lifecycle import _new_set

    s = _new_set()
    km.start_session(s)
    s["backing_track_loops"] = loops
    s.pop("_pending_backing_loops", None)
    return s


class EveryEntryStartsAtRepeatOne(unittest.TestCase):
    def test_an_entry_activation_queues_repeat_one_for_the_widget(self) -> None:
        for loops in (2, 3, 1):
            s = _set_session(loops)
            _invalidate_stale_backing_for_karaoke_transition(s)
            self.assertEqual(s["_pending_backing_loops"], 1, loops)

    def test_repeat_two_on_one_song_does_not_reach_the_next(self) -> None:
        s = _set_session(1)
        s["backing_track_loops"] = 2                       # the singer's choice for this song
        self.assertEqual(km.note_karaoke_set_loops(s, 2), 2)
        self.assertEqual(km.karaoke_set_loops(s), 1)       # nothing set-wide
        _invalidate_stale_backing_for_karaoke_transition(s)   # Next / Previous / auto / loop back
        self.assertEqual(s["_pending_backing_loops"], 1)

    def test_scope_resets_with_it(self) -> None:
        s = _set_session(2)
        s["backing_track_scope"] = "Selected sections"
        _invalidate_stale_backing_for_karaoke_transition(s)
        self.assertEqual(s["_pending_backing_scope"], "Full song")


if __name__ == "__main__":
    unittest.main()
