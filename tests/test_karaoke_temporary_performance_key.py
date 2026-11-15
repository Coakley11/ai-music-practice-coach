"""Karaoke Part 3: a key change during a performance is temporary.

Say is saved in the setlist in Bb. The performance starts in Bb. A different singer wants it in Ab,
so the key is changed mid-performance - and the accompaniment and every chord display follow. The
saved setlist entry must still say Bb: tomorrow, or on the Songs page, or the next time that entry
is played, Bb is where it starts.

Before this, ``retune_now_singing_entry`` wrote the new key into the queue row and persisted it, so
one evening's transposition rewrote the setlist for good. Measured on dev: after retuning Say to Ab,
the saved entry read Ab and the setlist row read "Say · Ab".

The three songs here are the ones from the report: Say in Bb, Just the Two of Us in Db, Perfect in
Ab.
"""

from __future__ import annotations

import unittest

import karaoke_mode as km

SONGS = (
    ("Pop\x1fSay", "Bb"),
    ("Pop\x1fJust the Two of Us", "Db"),
    ("Pop\x1fPerfect", "Ab"),
)


def performing_session() -> dict:
    session: dict = {"instrument": "Voice"}
    for pick, key in SONGS:
        km.add_to_queue(session, pick, practice_key=key)
    km.start_session(session)
    return session


def saved_keys(session: dict) -> list[str]:
    return [str(e.get("practice_key") or "") for e in km.get_queue(session)]


class TheSetStartsInTheSavedKeys(unittest.TestCase):
    def setUp(self) -> None:
        self.session = performing_session()

    def test_each_entry_keeps_the_key_it_was_added_in(self) -> None:
        self.assertEqual(saved_keys(self.session), ["Bb", "Db", "Ab"])

    def test_the_first_song_sounds_in_its_own_saved_key(self) -> None:
        self.assertEqual(km.current_session_practice_key(self.session), "Bb")

    def test_nothing_is_in_a_temporary_key_to_begin_with(self) -> None:
        self.assertEqual(km.performance_keys(self.session), {})
        self.assertEqual(km.performance_key_for_entry(self.session), "")


class ChangingTheKeyMidPerformance(unittest.TestCase):
    def setUp(self) -> None:
        self.session = performing_session()
        self.result = km.retune_now_singing_entry(self.session, "Ab")

    def test_the_change_is_accepted(self) -> None:
        self.assertTrue(self.result.get("changed"))
        self.assertEqual(self.result.get("previous"), "Bb")
        self.assertEqual(self.result.get("to"), "Ab")

    def test_the_performance_sounds_in_the_new_key(self) -> None:
        self.assertEqual(km.current_session_practice_key(self.session), "Ab")

    def test_the_saved_entry_still_says_bb(self) -> None:
        """The whole point of Part 3."""
        self.assertEqual(saved_keys(self.session), ["Bb", "Db", "Ab"])

    def test_the_setlist_row_still_reads_bb(self) -> None:
        self.assertIn("Bb", km.entry_display_line(km.get_queue(self.session)[0]))
        self.assertNotIn("Ab", km.entry_display_line(km.get_queue(self.session)[0]))

    def test_the_now_editing_path_still_writes_the_saved_key(self) -> None:
        """``apply_entry_practice_key`` is the setlist-row click, not the performance.

        It writes the song's own Practice Key store so the editing surfaces follow the row, so
        the temporary key must not travel through it. What the performance sounds in is read
        from ``current_session_practice_key``, which does see the temporary key - asserted two
        tests above. This began life asserting "Ab", which was this slice's own defect.
        """
        self.assertEqual(km.apply_entry_practice_key(self.session), "Bb")
        from songs.practice_key_state import saved_practice_concert_key

        self.assertEqual(
            saved_practice_concert_key(self.session, km.get_queue(self.session)[0]["pick_key"]),
            "Bb",
        )

    def test_the_render_generation_moves_so_nothing_stale_survives(self) -> None:
        """A component keyed by the old generation would keep the old key's chart and player."""
        before = km.render_generation(performing_session())
        after = km.render_generation(self.session)
        self.assertNotEqual(before, after)
        self.assertIn("Ab", after)

    def test_only_the_song_being_sung_is_affected(self) -> None:
        self.assertEqual(list(km.performance_keys(self.session).values()), ["Ab"])

    def test_a_second_change_measures_from_the_key_it_is_in(self) -> None:
        """Not from the saved key, or the second change would transpose from the wrong place."""
        again = km.retune_now_singing_entry(self.session, "C")
        self.assertEqual(again.get("previous"), "Ab")
        self.assertEqual(km.current_session_practice_key(self.session), "C")
        self.assertEqual(saved_keys(self.session), ["Bb", "Db", "Ab"])

    def test_asking_for_the_key_it_is_already_in_changes_nothing(self) -> None:
        same = km.retune_now_singing_entry(self.session, "Ab")
        self.assertFalse(same.get("changed"))
        self.assertEqual(same.get("reason"), "already in key")

    def test_choosing_the_saved_key_again_lifts_the_temporary_one(self) -> None:
        back = km.retune_now_singing_entry(self.session, "Bb")
        self.assertTrue(back.get("changed"))
        self.assertEqual(km.current_session_practice_key(self.session), "Bb")
        self.assertEqual(km.performance_keys(self.session), {},
                         "a layer agreeing with the saved key is a leftover, not a state")


class TheNextSongLoadsItsOwnKey(unittest.TestCase):
    def setUp(self) -> None:
        self.session = performing_session()
        km.retune_now_singing_entry(self.session, "Ab")

    def test_advancing_lands_in_the_next_entrys_saved_key(self) -> None:
        km.advance_session(self.session)
        self.assertEqual(km.current_session_practice_key(self.session), "Db")

    def test_going_back_returns_to_the_temporary_key_of_the_song_being_sung(self) -> None:
        """The layer is keyed by entry, so stepping away and back does not lose the change."""
        km.advance_session(self.session)
        km.regress_session(self.session)
        self.assertEqual(km.current_session_practice_key(self.session), "Ab")

    def test_each_song_in_turn_sounds_in_its_own_key(self) -> None:
        heard = [km.current_session_practice_key(self.session)]
        for _ in range(2):
            km.advance_session(self.session)
            heard.append(km.current_session_practice_key(self.session))
        self.assertEqual(heard, ["Ab", "Db", "Ab"])

    def test_no_entry_inherits_another_entrys_temporary_key(self) -> None:
        km.advance_session(self.session)
        self.assertEqual(km.performance_key_for_entry(self.session), "")


class WhenTheSetEnds(unittest.TestCase):
    def setUp(self) -> None:
        self.session = performing_session()
        km.retune_now_singing_entry(self.session, "Ab")
        km.stop_session(self.session)

    def test_every_saved_key_is_as_it_was(self) -> None:
        self.assertEqual(saved_keys(self.session), ["Bb", "Db", "Ab"])

    def test_the_temporary_keys_are_forgotten(self) -> None:
        self.assertEqual(km.performance_keys(self.session), {})

    def test_the_next_performance_starts_from_the_saved_key(self) -> None:
        km.start_session(self.session)
        self.assertEqual(km.current_session_practice_key(self.session), "Bb")

    def test_the_setlist_itself_survives(self) -> None:
        """Ending a set is not deleting it."""
        self.assertEqual(len(km.get_queue(self.session)), 3)


class ARetuneOnlyHappensDuringAPerformance(unittest.TestCase):
    """The entry's key is frozen on purpose: reruns, hydration and navigation must not move it."""

    def test_nothing_happens_when_no_set_is_running(self) -> None:
        session: dict = {"instrument": "Voice"}
        for pick, key in SONGS:
            km.add_to_queue(session, pick, practice_key=key)
        result = km.retune_now_singing_entry(session, "Ab")
        self.assertFalse(result.get("changed"))
        self.assertEqual(result.get("reason"), "not performing")
        self.assertEqual(saved_keys(session), ["Bb", "Db", "Ab"])

    def test_nothing_happens_without_a_key(self) -> None:
        session = performing_session()
        for token in ("", "   "):
            with self.subTest(token=token):
                self.assertFalse(km.retune_now_singing_entry(session, token).get("changed"))
        self.assertEqual(km.performance_keys(session), {})


class AFailedRegenerationPutsThePerformanceBack(unittest.TestCase):
    def setUp(self) -> None:
        self.session = performing_session()
        km.retune_now_singing_entry(self.session, "C")
        km.retune_now_singing_entry(self.session, "Ab")

    def test_the_rollback_restores_the_previous_performance_key(self) -> None:
        out = km.rollback_now_singing_retune(self.session)
        self.assertTrue(out.get("restored"))
        self.assertEqual(km.current_session_practice_key(self.session), "C")

    def test_the_saved_entry_is_untouched_throughout(self) -> None:
        km.rollback_now_singing_retune(self.session)
        self.assertEqual(saved_keys(self.session), ["Bb", "Db", "Ab"])

    def test_rolling_back_to_the_saved_key_leaves_no_leftover_layer(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        km.rollback_now_singing_retune(session)
        self.assertEqual(km.current_session_practice_key(session), "Bb")
        self.assertEqual(km.performance_keys(session), {})

    def test_confirming_instead_keeps_the_performance_in_the_new_key(self) -> None:
        km.confirm_now_singing_retune(self.session)
        self.assertEqual(km.current_session_practice_key(self.session), "Ab")
        self.assertEqual(saved_keys(self.session), ["Bb", "Db", "Ab"])

    def test_nothing_pending_is_not_an_error(self) -> None:
        session = performing_session()
        out = km.rollback_now_singing_retune(session)
        self.assertFalse(out.get("restored"))
        self.assertEqual(out.get("reason"), "nothing pending")


class CustomAndCompositionEntriesBehaveTheSame(unittest.TestCase):
    """Part 3: "The same behavior must work for Custom Progressions and Composition Studio."""

    def setUp(self) -> None:
        self.session: dict = {"instrument": "Voice"}
        for pick, key in (("custom::am-1", "Am"), ("composition::doc-1", "F")):
            km.add_to_queue(self.session, pick, practice_key=key)
        km.start_session(self.session)

    def test_a_custom_entry_retunes_temporarily(self) -> None:
        self.assertEqual(km.current_session_practice_key(self.session), "Am")
        km.retune_now_singing_entry(self.session, "Cm")
        self.assertEqual(km.current_session_practice_key(self.session), "Cm")
        self.assertEqual(saved_keys(self.session), ["Am", "F"])

    def test_a_composition_entry_retunes_temporarily(self) -> None:
        km.advance_session(self.session)
        self.assertEqual(km.current_session_practice_key(self.session), "F")
        km.retune_now_singing_entry(self.session, "G")
        self.assertEqual(km.current_session_practice_key(self.session), "G")
        self.assertEqual(saved_keys(self.session), ["Am", "F"])

    def test_the_saved_keys_survive_the_set(self) -> None:
        km.retune_now_singing_entry(self.session, "Cm")
        km.stop_session(self.session)
        self.assertEqual(saved_keys(self.session), ["Am", "F"])


class TheSavedKeyIsStillReadableOnItsOwn(unittest.TestCase):
    def test_the_saved_key_helper_never_sees_the_layer(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        entry = km.get_queue(session)[0]
        self.assertEqual(km.entry_default_practice_key(entry), "Bb")
        self.assertEqual(km.effective_entry_practice_key(session, entry), "Ab")

    def test_an_entry_with_no_layer_reads_the_same_either_way(self) -> None:
        session = performing_session()
        entry = km.get_queue(session)[0]
        self.assertEqual(
            km.entry_default_practice_key(entry),
            km.effective_entry_practice_key(session, entry),
        )

    def test_the_helpers_tolerate_nonsense(self) -> None:
        self.assertEqual(km.entry_default_practice_key(None), "")
        self.assertEqual(km.effective_entry_practice_key({}, None), "")
        self.assertEqual(km.set_performance_key({}, "", "Ab"), "")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
