"""Issue 69C: in a karaoke session two keys are in play, and they can disagree.

Reported from the phone. Practising *Say*, the Practice Concert Key moved to D major,
the chord tiles read ``Dsus4`` / ``Dsus4/E`` and the Current Chord read ``Csus4/D`` - a
C-root chord from the key the song had been in a moment earlier.

It is not a stale cache. The timeline's cache signature already carries a key. What is
actually going on is that an active karaoke session has **two** authorities:

* the **entry's own** ``practice_key``, frozen when the song was queued. It drives
  ``_audio_signature_key``, the karaoke chart that is re-asserted immediately before the
  arrangement is built, and therefore the chord-event timeline - so the Current and Next
  Chord, and what you hear;
* the **global Practice Concert Key**, which drives the sidebar and the chord tiles.

The entry's key is deliberately independent: writing a global key change into it would
re-key a song that is merely being *edited* in another key elsewhere. But the flow only
ever runs one way - ``apply_entry_practice_key`` pushes entry into session - so changing
the global key updates the tiles and leaves the performance where it was. Both displays
are then correct by their own rule and disagree on screen, which is what was
photographed.

These tests pin the divergence itself. They assert today's behaviour, so that whichever
way the product decides to resolve it, the decision is explicit and this file has to
change with it.
"""

from __future__ import annotations

import unittest

import karaoke_mode as km


def session_with_now_singing(entry_key: str, *, song="Say", artist="John Mayer"):
    """A session whose Now Singing entry was queued in ``entry_key``."""
    state: dict = {"instrument": "Voice"}
    entry = {
        "entry_id": "e1",
        "pick_key": f"Pop\u001f{song} — {artist}",
        "title": song,
        "artist": artist,
        "practice_key": entry_key,
        "play_count": 1,
    }
    state[km.KARAOKE_QUEUE_KEY] = [entry]
    state[km.KARAOKE_SESSION_ACTIVE_KEY] = True
    state[km.KARAOKE_SESSION_INDEX_KEY] = 0
    return state


class TheTwoAuthoritiesExist(unittest.TestCase):
    def test_the_entry_key_is_what_karaoke_reads(self):
        state = session_with_now_singing("C")
        self.assertTrue(km.is_voice_mode(state))
        self.assertTrue(km.is_karaoke_session_active(state))
        self.assertEqual(km.current_session_practice_key(state), "C")

    def test_the_store_alone_left_the_two_keys_disagreeing(self):
        """The reported symptom, reduced to its cause - and why a retune exists."""
        from songs.practice_key_state import set_practice_concert_key

        state = session_with_now_singing("C")
        pick = state[km.KARAOKE_QUEUE_KEY][0]["pick_key"]
        state["active_catalog_pick_key"] = pick

        set_practice_concert_key(state, "D", pick_key=pick,
                                 commit_catalog_practice_key=True)
        state["display_key"] = "D"

        # The tiles and sidebar now say D...
        self.assertEqual(state["display_key"], "D")
        # ...and the performance is still in C.
        self.assertEqual(km.current_session_practice_key(state), "C")

    def test_exactly_one_authorized_writer_moves_a_queued_entry_key(self):
        """The divergence is resolved, deliberately and in one place.

        This test began life asserting that *nothing* wrote a queued entry's
        practice_key - which was true, and was the defect: a musician changing the key
        mid-performance had no way to move it. It now names the single authorized
        writer, so a second one has to justify itself here.

        Scoped to modules that touch the karaoke queue. Unscoped, the same scan finds
        six assignments in Creative, Missions and workflow code, none of which is a
        queue entry.
        """
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parent.parent
        assign = re.compile(r"""\[["']practice_key["']\]\s*=""")
        writers = []
        for path in sorted(root.glob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if not re.search(r"KARAOKE_QUEUE_KEY|karaoke_mode|get_queue", text):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if assign.search(line):
                    writers.append(f"{path.name}:{n}")
        self.assertEqual(
            [w.split(":")[0] for w in writers], ["karaoke_mode.py", "karaoke_mode.py"],
            f"the only writers should be the retune and its rollback: {writers}",
        )

    def test_a_direct_store_write_still_does_not_move_the_performance(self):
        """Only the explicit sidebar gesture re-keys. The store itself must not.

        This is what keeps hydration, reruns, navigation and backing updates away from
        a live performance: they go through the Practice Key store, and the store has no
        route into the queue.
        """
        from songs.practice_key_state import set_practice_concert_key

        state = session_with_now_singing("C")
        pick = state[km.KARAOKE_QUEUE_KEY][0]["pick_key"]
        state["active_catalog_pick_key"] = pick
        set_practice_concert_key(state, "D", pick_key=pick,
                                 commit_catalog_practice_key=True)
        self.assertEqual(km.current_session_practice_key(state), "C")

    def test_the_explicit_retune_is_what_moves_it(self):
        state = session_with_now_singing("C")
        km.retune_now_singing_entry(state, "D")
        self.assertEqual(km.current_session_practice_key(state), "D")

    def test_applying_the_entry_key_moves_the_session_not_the_entry(self):
        state = session_with_now_singing("C")
        entry = km.current_session_entry(state)
        km.apply_entry_practice_key(state, entry)
        self.assertEqual(km.current_session_practice_key(state), "C")


class WhatTheChordsShouldBe(unittest.TestCase):
    """The arithmetic the screen was failing, stated once so it is not in doubt."""

    def test_the_reported_chord_transposes_as_the_user_said(self):
        from music_theory import semitone_distance, transpose_chord

        steps = semitone_distance("C", "D")
        self.assertEqual(steps, 2)
        self.assertEqual(transpose_chord("Csus4/D", steps, reference_key="D"),
                         "Dsus4/E")

    def test_a_slash_chord_moves_root_and_bass(self):
        from music_theory import transpose_chord

        self.assertEqual(transpose_chord("A/C#", 2, reference_key="D"), "B/D#")

    def test_the_engine_is_not_the_problem(self):
        """Every chord in the report transposes correctly on its own."""
        from music_theory import transpose_chord

        for src, want in (("Csus4", "Dsus4"), ("Csus4/D", "Dsus4/E"),
                          ("C", "D"), ("Am", "Bm"), ("F", "G")):
            with self.subTest(src=src):
                self.assertEqual(transpose_chord(src, 2, reference_key="D"), want)


if __name__ == "__main__":
    unittest.main()
