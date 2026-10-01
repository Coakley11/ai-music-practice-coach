"""Tests for the Practice Melody session-state lifecycle policy
(practice_melody_session.py) -- identity keying, rerun stability, level/song
change handling, and Generate Another Melody, all without a live Streamlit
session (``session_state`` is a plain dict here).
"""

from __future__ import annotations

import unittest

from practice_melody_session import (
    ALT_INDEX_KEY,
    IDENTITY_KEY,
    RESULT_KEY,
    clear_practice_melody_state,
    resolve_practice_melody,
)

_SECTIONS = {
    "Verse 1": ["G", "Em7", "Cadd9", "D"] * 2,
    "Chorus": ["C", "G", "Am7", "F"] * 2,
}


def _resolve(session_state, *, song_identity="cat::Song A|Artist|G", level="Beginner", regenerate=False, **overrides):
    kwargs = dict(
        song_identity=song_identity,
        song_id_for_generation=song_identity,
        song_title="Song A",
        sections=_SECTIONS,
        section_order=list(_SECTIONS.keys()),
        key_center="G",
        level=level,
        tempo_bpm=96.0,
        style="Pop",
        regenerate=regenerate,
    )
    kwargs.update(overrides)
    return resolve_practice_melody(session_state, **kwargs)


class TestRerunStability(unittest.TestCase):
    def test_repeated_calls_with_unchanged_identity_return_the_same_object(self) -> None:
        session_state: dict = {}
        first = _resolve(session_state)
        for _ in range(5):
            again = _resolve(session_state)
            self.assertIs(again, first, "unrelated reruns must not regenerate the melody")

    def test_first_call_with_no_cache_generates_a_baseline_alt_zero(self) -> None:
        session_state: dict = {}
        melody = _resolve(session_state)
        self.assertEqual(melody.alt_index, 0)
        self.assertEqual(session_state[ALT_INDEX_KEY], 0)
        self.assertIs(session_state[RESULT_KEY], melody)


class TestGenerateAnother(unittest.TestCase):
    def test_regenerate_true_advances_alt_index_and_changes_output(self) -> None:
        session_state: dict = {}
        first = _resolve(session_state)
        second = _resolve(session_state, regenerate=True)
        self.assertEqual(second.alt_index, first.alt_index + 1)
        self.assertNotEqual(first.to_dict()["sections"], second.to_dict()["sections"])
        # Same song/level identity throughout.
        self.assertEqual(second.song_id, first.song_id)
        self.assertEqual(second.level, first.level)

    def test_regenerate_true_is_a_noop_without_a_prior_cached_melody_of_this_identity(self) -> None:
        # No cache yet -- "Generate Another" before anything exists should
        # still produce a usable (baseline) melody rather than erroring.
        session_state: dict = {}
        melody = _resolve(session_state, regenerate=True)
        self.assertEqual(melody.alt_index, 0)

    def test_repeated_calls_after_generate_another_stay_stable(self) -> None:
        session_state: dict = {}
        _resolve(session_state)
        alt = _resolve(session_state, regenerate=True)
        for _ in range(3):
            again = _resolve(session_state)
            self.assertIs(again, alt, "the alternate melody must persist across unrelated reruns too")


class TestKeyChangeTransposesNotRegenerates(unittest.TestCase):
    """Slice F1: a key change with song/level unchanged must transpose the
    existing composition, never regenerate a different one."""

    def test_key_change_preserves_melody_id_and_alt_index(self) -> None:
        session_state: dict = {}
        in_c = _resolve(session_state, key_center="C")
        in_d = _resolve(session_state, key_center="D")
        self.assertEqual(in_d.melody_id, in_c.melody_id)
        self.assertEqual(in_d.alt_index, in_c.alt_index)
        self.assertEqual(in_d.key_center, "D")
        self.assertNotEqual(in_d.key_center, in_c.key_center)

    def test_key_change_preserves_intervals(self) -> None:
        session_state: dict = {}
        in_c = _resolve(session_state, key_center="C")
        in_d = _resolve(session_state, key_center="D")

        def intervals(melody):
            midis = [e.midi for s in melody.sections for e in s.events if not e.is_rest]
            return [b - a for a, b in zip(midis, midis[1:])]

        self.assertEqual(intervals(in_c), intervals(in_d))

    def test_key_change_is_rerun_stable_once_applied(self) -> None:
        session_state: dict = {}
        _resolve(session_state, key_center="C")
        first_in_d = _resolve(session_state, key_center="D")
        second_in_d = _resolve(session_state, key_center="D")
        self.assertIs(second_in_d, first_in_d, "re-resolving at the same key must not re-transpose every rerun")

    def test_key_change_back_and_forth_round_trips(self) -> None:
        session_state: dict = {}
        in_c = _resolve(session_state, key_center="C")
        _resolve(session_state, key_center="D")
        back_in_c = _resolve(session_state, key_center="C")
        self.assertEqual(back_in_c.to_dict(), in_c.to_dict())

    def test_generate_another_then_key_change_preserves_the_alternate(self) -> None:
        session_state: dict = {}
        _resolve(session_state, key_center="C")
        alt = _resolve(session_state, key_center="C", regenerate=True)
        self.assertEqual(alt.alt_index, 1)
        transposed_alt = _resolve(session_state, key_center="D")
        self.assertEqual(transposed_alt.alt_index, 1)
        self.assertEqual(transposed_alt.melody_id, alt.melody_id)

    def test_key_change_does_not_affect_a_different_song(self) -> None:
        session_state: dict = {}
        _resolve(session_state, song_identity="cat::Song A|Artist|G", key_center="C")
        song_b = _resolve(session_state, song_identity="cat::Song B|Artist|D", key_center="D")
        self.assertEqual(song_b.alt_index, 0)
        self.assertEqual(song_b.key_center, "D")


class TestLevelChangePolicy(unittest.TestCase):
    def test_level_change_produces_a_fresh_baseline_matching_the_new_level(self) -> None:
        session_state: dict = {}
        beginner = _resolve(session_state, level="Beginner")
        # Simulate the user generating an alternate at Beginner first.
        beginner_alt = _resolve(session_state, level="Beginner", regenerate=True)
        self.assertEqual(beginner_alt.level, "Beginner")

        advanced = _resolve(session_state, level="Advanced")
        self.assertEqual(advanced.level, "Advanced")
        self.assertEqual(advanced.alt_index, 0, "a level change resolves to a fresh baseline, not a carried-over alt")
        self.assertNotEqual(advanced.to_dict()["sections"], beginner_alt.to_dict()["sections"])

    def test_after_level_change_the_old_level_melody_is_no_longer_reachable(self) -> None:
        session_state: dict = {}
        _resolve(session_state, level="Beginner")
        advanced = _resolve(session_state, level="Advanced")
        # A second call with no change must keep returning Advanced, not
        # silently resurrect Beginner.
        still_advanced = _resolve(session_state, level="Advanced")
        self.assertIs(still_advanced, advanced)
        self.assertEqual(still_advanced.level, "Advanced")

    def test_returning_to_a_previous_level_resolves_to_its_own_fresh_baseline(self) -> None:
        """Documents the chosen policy: returning to a level you'd already
        generated an alternate for does NOT resurrect that alternate -- it
        deterministically resolves to level's baseline again. This is the
        simpler, safer policy relative to caching a whole visit history."""
        session_state: dict = {}
        beginner_first = _resolve(session_state, level="Beginner")
        _resolve(session_state, level="Beginner", regenerate=True)  # now alt_index 1
        _resolve(session_state, level="Advanced")  # switch away
        beginner_again = _resolve(session_state, level="Beginner")  # switch back
        self.assertEqual(beginner_again.alt_index, 0)
        self.assertEqual(beginner_again.to_dict()["sections"], beginner_first.to_dict()["sections"])


class TestSongChangePolicy(unittest.TestCase):
    def test_song_change_produces_a_fresh_baseline_and_drops_the_old_song(self) -> None:
        session_state: dict = {}
        song_a = _resolve(session_state, song_identity="cat::Song A|Artist|G")
        song_b = _resolve(
            session_state,
            song_identity="cat::Song B|Artist|Am",
            key_center="Am",
        )
        self.assertNotEqual(song_a.song_id, song_b.song_id)
        self.assertEqual(song_b.alt_index, 0)

    def test_catalog_to_custom_and_back_does_not_leak(self) -> None:
        session_state: dict = {}
        catalog = _resolve(session_state, song_identity="cat::Song A|Artist|G")
        custom = _resolve(session_state, song_identity="cpl::revision-123")
        self.assertNotEqual(catalog.song_id, custom.song_id)
        self.assertIsNot(session_state[RESULT_KEY], catalog)
        back_to_catalog = _resolve(session_state, song_identity="cat::Song A|Artist|G")
        self.assertEqual(back_to_catalog.song_id, "cat::Song A|Artist|G")

    def test_identity_token_combines_song_and_level(self) -> None:
        session_state: dict = {}
        _resolve(session_state, song_identity="cat::Song A|Artist|G", level="Beginner")
        self.assertEqual(session_state[IDENTITY_KEY], "cat::Song A|Artist|G::Beginner")


class TestUnavailableSource(unittest.TestCase):
    def test_empty_sections_returns_none_and_clears_any_prior_cache(self) -> None:
        session_state: dict = {}
        _resolve(session_state)  # valid melody cached
        self.assertIn(RESULT_KEY, session_state)

        result = resolve_practice_melody(
            session_state,
            song_identity="cat::Unavailable|Artist|C",
            song_id_for_generation="cat::Unavailable|Artist|C",
            song_title="Unavailable",
            sections={},
            section_order=None,
            key_center="C",
            level="Beginner",
            tempo_bpm=100.0,
            style="",
        )
        self.assertIsNone(result)
        self.assertNotIn(RESULT_KEY, session_state)
        self.assertNotIn(IDENTITY_KEY, session_state)

    def test_none_sections_also_treated_as_unavailable(self) -> None:
        session_state: dict = {}
        result = resolve_practice_melody(
            session_state,
            song_identity="cat::X|Y|C",
            song_id_for_generation="cat::X|Y|C",
            song_title="X",
            sections=None,
            section_order=None,
            key_center="C",
            level="Beginner",
            tempo_bpm=100.0,
            style="",
        )
        self.assertIsNone(result)


class TestClearHelper(unittest.TestCase):
    def test_clear_practice_melody_state_removes_only_its_own_keys(self) -> None:
        session_state: dict = {"unrelated": "keep-me"}
        _resolve(session_state)
        clear_practice_melody_state(session_state)
        self.assertNotIn(RESULT_KEY, session_state)
        self.assertNotIn(IDENTITY_KEY, session_state)
        self.assertNotIn(ALT_INDEX_KEY, session_state)
        self.assertEqual(session_state["unrelated"], "keep-me")


if __name__ == "__main__":
    unittest.main()
