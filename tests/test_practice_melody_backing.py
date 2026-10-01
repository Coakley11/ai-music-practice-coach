"""Tests for the Practice Melody -> Backing handoff lifecycle
(practice_melody_backing.py) -- identity preservation, rerun stability,
stale-leak prevention, and deliberate handoff replacement, all without a
live Streamlit session (``session_state`` is a plain dict here).
"""

from __future__ import annotations

import unittest

from practice_melody_backing import (
    BACKING_MELODY_KEY,
    BACKING_MELODY_SONG_IDENTITY_KEY,
    PENDING_MELODY_KEY,
    begin_practice_melody_backing_handoff,
    clear_practice_melody_backing_state,
    consume_pending_practice_melody_handoff,
    resolve_active_backing_practice_melody,
)
from practice_melody_generator import generate_another_practice_melody, generate_practice_melody

_SECTIONS = {
    "Verse 1": ["G", "Em7", "Cadd9", "D"] * 2,
    "Chorus": ["C", "G", "Am7", "F"] * 2,
}


def _melody(song_id="cat::song-a", level="Intermediate", **overrides):
    kwargs = dict(
        song_id=song_id, song_title="Song A", sections=_SECTIONS,
        key_center="G", level=level, tempo_bpm=96.0, style="Pop",
    )
    kwargs.update(overrides)
    return generate_practice_melody(**kwargs)


class TestHandoffBasics(unittest.TestCase):
    def test_consume_with_matching_identity_activates_melody(self) -> None:
        session_state: dict = {}
        melody = _melody()
        begin_practice_melody_backing_handoff(session_state, melody=melody, song_identity="cat::song-a")
        resolved = consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        self.assertIs(resolved, melody)

    def test_pending_key_is_cleared_after_consumption(self) -> None:
        session_state: dict = {}
        melody = _melody()
        begin_practice_melody_backing_handoff(session_state, melody=melody, song_identity="cat::song-a")
        consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        self.assertNotIn(PENDING_MELODY_KEY, session_state)

    def test_no_pending_and_nothing_active_returns_none(self) -> None:
        session_state: dict = {}
        self.assertIsNone(
            consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        )


class TestStaleLeakPrevention(unittest.TestCase):
    def test_pending_handoff_for_a_different_song_than_backing_shows_is_dropped(self) -> None:
        """The user clicked 'Practice with Backing' for Song A, but then (in
        some race) Backing ends up rendering for Song B -- the handoff must
        not leak Song A's melody onto Song B."""
        session_state: dict = {}
        melody = _melody(song_id="cat::song-a")
        begin_practice_melody_backing_handoff(session_state, melody=melody, song_identity="cat::song-a")
        resolved = consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-b")
        self.assertIsNone(resolved)
        self.assertNotIn(BACKING_MELODY_KEY, session_state)

    def test_song_a_melody_never_appears_after_switching_to_song_b(self) -> None:
        session_state: dict = {}
        melody_a = _melody(song_id="cat::song-a")
        begin_practice_melody_backing_handoff(session_state, melody=melody_a, song_identity="cat::song-a")
        consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        self.assertIs(
            resolve_active_backing_practice_melody(session_state, current_song_identity="cat::song-a"),
            melody_a,
        )
        # Now the active song/source changes to Song B with no new handoff.
        resolved_for_b = resolve_active_backing_practice_melody(session_state, current_song_identity="cat::song-b")
        self.assertIsNone(resolved_for_b)
        self.assertNotIn(BACKING_MELODY_KEY, session_state)

    def test_switching_back_to_song_a_without_a_new_handoff_does_not_resurrect_it(self) -> None:
        session_state: dict = {}
        melody_a = _melody(song_id="cat::song-a")
        begin_practice_melody_backing_handoff(session_state, melody=melody_a, song_identity="cat::song-a")
        consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        resolve_active_backing_practice_melody(session_state, current_song_identity="cat::song-b")  # clears it
        still_none = resolve_active_backing_practice_melody(session_state, current_song_identity="cat::song-a")
        self.assertIsNone(still_none, "a cleared handoff must require an explicit new 'Practice with Backing' click")


class TestRerunStability(unittest.TestCase):
    def test_repeated_resolve_calls_return_the_same_object(self) -> None:
        session_state: dict = {}
        melody = _melody()
        begin_practice_melody_backing_handoff(session_state, melody=melody, song_identity="cat::song-a")
        consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        for _ in range(5):
            again = resolve_active_backing_practice_melody(session_state, current_song_identity="cat::song-a")
            self.assertIs(again, melody, "ordinary Backing reruns must not disturb the active melody")

    def test_consume_called_again_with_no_new_pending_is_also_stable(self) -> None:
        """Calling consume() on every Backing render (not just the first) is
        the intended usage -- it must be a no-op once the pending key is
        gone."""
        session_state: dict = {}
        melody = _melody()
        begin_practice_melody_backing_handoff(session_state, melody=melody, song_identity="cat::song-a")
        first = consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        second = consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        third = consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        self.assertIs(first, melody)
        self.assertIs(second, melody)
        self.assertIs(third, melody)


class TestGenerateAnotherAndSecondHandoff(unittest.TestCase):
    def test_generate_another_then_handoff_preserves_that_exact_alternate(self) -> None:
        baseline = _melody()
        alternate = generate_another_practice_melody(baseline)
        self.assertNotEqual(baseline.alt_index, alternate.alt_index)

        session_state: dict = {}
        begin_practice_melody_backing_handoff(session_state, melody=alternate, song_identity="cat::song-a")
        resolved = consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        self.assertIs(resolved, alternate)
        self.assertEqual(resolved.alt_index, alternate.alt_index)
        self.assertNotEqual(resolved.to_dict()["sections"], baseline.to_dict()["sections"])

    def test_second_handoff_deliberately_replaces_the_first(self) -> None:
        session_state: dict = {}
        first = _melody()
        second = generate_another_practice_melody(first)

        begin_practice_melody_backing_handoff(session_state, melody=first, song_identity="cat::song-a")
        consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        self.assertIs(
            resolve_active_backing_practice_melody(session_state, current_song_identity="cat::song-a"),
            first,
        )

        begin_practice_melody_backing_handoff(session_state, melody=second, song_identity="cat::song-a")
        resolved = consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        self.assertIs(resolved, second)
        self.assertIs(
            resolve_active_backing_practice_melody(session_state, current_song_identity="cat::song-a"),
            second,
        )


class TestSongSourceIdentityPreservation(unittest.TestCase):
    def test_catalog_to_custom_song_identity_strings_do_not_collide(self) -> None:
        session_state: dict = {}
        catalog_melody = _melody(song_id="cat::Song A|Artist|G")
        begin_practice_melody_backing_handoff(
            session_state, melody=catalog_melody, song_identity="cat::Song A|Artist|G"
        )
        resolved = consume_pending_practice_melody_handoff(
            session_state, current_song_identity="cpl::revision-123"
        )
        self.assertIsNone(resolved, "a Catalog handoff must not surface under a different Custom identity")


class TestClearHelper(unittest.TestCase):
    def test_clear_removes_only_its_own_keys(self) -> None:
        session_state: dict = {"unrelated": "keep-me"}
        melody = _melody()
        begin_practice_melody_backing_handoff(session_state, melody=melody, song_identity="cat::song-a")
        consume_pending_practice_melody_handoff(session_state, current_song_identity="cat::song-a")
        clear_practice_melody_backing_state(session_state)
        self.assertNotIn(BACKING_MELODY_KEY, session_state)
        self.assertNotIn(BACKING_MELODY_SONG_IDENTITY_KEY, session_state)
        self.assertNotIn(PENDING_MELODY_KEY, session_state)
        self.assertEqual(session_state["unrelated"], "keep-me")


if __name__ == "__main__":
    unittest.main()
