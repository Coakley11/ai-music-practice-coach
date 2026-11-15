"""Karaoke Part 3b: transposing a song for one evening must not change what it is saved in.

Part 3 stopped the retune rewriting the *setlist entry*. It left the other half of the same
gesture untouched, and that half was worse: the sidebar Practice Key control runs the karaoke
retune and then the ordinary durable commit (``songs/key_state.mark_display_key_changed`` ->
``set_practice_concert_key`` + ``mark_practice_key_user_override``). Measured on the branch
before this change, with Say's own saved Practice Key at D - the musician's earlier choice,
made outside karaoke - and Say queued in Bb:

    after the karaoke retune    saved(Say)='D'   entry='Bb'  sounding='Ab'
    after the durable commit    saved(Say)='Ab'  entry='Bb'  sounding='Ab'
    after End karaoke set       saved(Say)='Ab'  entry='Bb'  sounding=''

So D was gone, permanently, because the song was sung in Ab once.

The correction is a freeze at the write primitives, the same shape Fixed Key already uses
there: while the song being sung is under the performance's own key, its saved key cannot be
written. Nothing is written and repaired afterwards, so there is no stale value that could
later land on top of a newer legitimate choice.

``durable_commit`` below is a copy of what the real catalog lane does, so these tests fail if
the freeze is removed from either primitive.
"""

from __future__ import annotations

import time
import unittest

import karaoke_mode as km
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    PRACTICE_KEY_USER_OVERRIDE_PICKS_KEY,
    clear_practice_concert_key,
    karaoke_performance_locks_song_key,
    mark_practice_key_user_override,
    saved_practice_concert_key,
    set_practice_concert_key,
)

SAY = "Pop\x1fSay — John Mayer"
JTTOU = "Pop\x1fJust the Two of Us — Grover Washington Jr."
PERFECT = "Pop\x1fPerfect — Ed Sheeran"
ENTRY_KEYS = ((SAY, "Bb"), (JTTOU, "Db"), (PERFECT, "Ab"))


def durable_commit(session: dict, pick: str, token: str) -> None:
    """What ``songs/key_state.mark_display_key_changed`` does for a catalog song.

    Copied rather than called because the real one needs a Streamlit script run. The two
    primitives it ends in are the real ones, which is where the freeze lives.
    """
    session["display_key"] = token
    session["concert_key"] = token
    mark_practice_key_user_override(session, pick)
    session["_pk_explicit_restore_original"] = True
    set_practice_concert_key(
        session,
        token,
        pick_key=pick,
        allow_restore_original=True,
        commit_catalog_practice_key=True,
    )
    session["_pk_user_commit_token"] = token
    session["_pk_user_commit_pick"] = pick
    session["_pk_user_commit_at"] = time.time()


def performing_session(*, say_saved_key: str = "D") -> dict:
    """A set running on Say, whose own saved Practice Key is something else entirely."""
    session: dict = {"instrument": "Voice"}
    session[PRACTICE_KEY_BY_SOURCE_KEY] = {SAY: say_saved_key}
    session["active_catalog_pick_key"] = SAY
    session["selected_song"] = {"pick_key": SAY, "title": "Say", "artist": "John Mayer", "key": "C"}
    for pick, key in ENTRY_KEYS:
        km.add_to_queue(session, pick, practice_key=key)
    km.start_session(session)
    return session


def overridden(session: dict) -> set[str]:
    return {str(p) for p in (session.get(PRACTICE_KEY_USER_OVERRIDE_PICKS_KEY) or [])}


class TheReportedDefect(unittest.TestCase):
    """Say saved in D, queued in Bb, sung in Ab. D must still be D afterwards."""

    def setUp(self) -> None:
        self.session = performing_session()

    def test_the_song_starts_with_its_own_saved_key(self) -> None:
        self.assertEqual(saved_practice_concert_key(self.session, SAY), "D")

    def test_the_retune_alone_writes_nothing(self) -> None:
        km.retune_now_singing_entry(self.session, "Ab")
        self.assertEqual(saved_practice_concert_key(self.session, SAY), "D")

    def test_the_durable_half_of_the_gesture_is_refused(self) -> None:
        km.retune_now_singing_entry(self.session, "Ab")
        durable_commit(self.session, SAY, "Ab")
        self.assertEqual(saved_practice_concert_key(self.session, SAY), "D")

    def test_tonight_is_not_recorded_as_a_user_edit_of_the_song(self) -> None:
        """The override stamp is durable state: it tells a later source switch to keep the key."""
        km.retune_now_singing_entry(self.session, "Ab")
        durable_commit(self.session, SAY, "Ab")
        self.assertNotIn(SAY, overridden(self.session))

    def test_the_saved_key_survives_the_whole_set(self) -> None:
        km.retune_now_singing_entry(self.session, "Ab")
        durable_commit(self.session, SAY, "Ab")
        km.advance_session(self.session)
        km.advance_session(self.session)
        km.stop_session(self.session)
        self.assertEqual(saved_practice_concert_key(self.session, SAY), "D")

    def test_the_performance_still_sounds_in_tonights_key(self) -> None:
        """Refusing the durable write must not cost the musician the transposition."""
        km.retune_now_singing_entry(self.session, "Ab")
        durable_commit(self.session, SAY, "Ab")
        self.assertEqual(km.current_session_practice_key(self.session), "Ab")
        self.assertEqual(self.session["display_key"], "Ab")

    def test_the_setlist_entry_is_still_bb(self) -> None:
        km.retune_now_singing_entry(self.session, "Ab")
        durable_commit(self.session, SAY, "Ab")
        self.assertEqual(km.get_queue(self.session)[0]["practice_key"], "Bb")


class WhatMustStillPersist(unittest.TestCase):
    """The freeze is narrow. Deliberate key changes outside it are the musician's and keep."""

    def test_the_same_gesture_with_no_set_running(self) -> None:
        session: dict = {
            "instrument": "Voice",
            PRACTICE_KEY_BY_SOURCE_KEY: {SAY: "D"},
            "active_catalog_pick_key": SAY,
        }
        durable_commit(session, SAY, "E")
        self.assertEqual(saved_practice_concert_key(session, SAY), "E")
        self.assertIn(SAY, overridden(session))

    def test_another_songs_key_during_the_set(self) -> None:
        """Perfect is being edited on the Songs page while Say is being sung."""
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        durable_commit(session, PERFECT, "F")
        self.assertEqual(saved_practice_concert_key(session, PERFECT), "F")
        self.assertEqual(saved_practice_concert_key(session, SAY), "D")

    def test_the_song_being_sung_before_anyone_retunes_it(self) -> None:
        """Playing the set changes nothing about who owns the key. Only a retune does."""
        session = performing_session()
        self.assertFalse(karaoke_performance_locks_song_key(session, SAY))
        durable_commit(session, SAY, "E")
        self.assertEqual(saved_practice_concert_key(session, SAY), "E")

    def test_a_song_whose_turn_has_passed(self) -> None:
        """Say was retuned, then the set moved on. Say is no longer the performance's."""
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        km.advance_session(session)
        self.assertFalse(karaoke_performance_locks_song_key(session, SAY))
        durable_commit(session, SAY, "E")
        self.assertEqual(saved_practice_concert_key(session, SAY), "E")

    def test_the_freeze_lifts_when_the_set_ends(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        km.stop_session(session)
        self.assertFalse(karaoke_performance_locks_song_key(session, SAY))
        durable_commit(session, SAY, "Ab")
        self.assertEqual(
            saved_practice_concert_key(session, SAY), "Ab",
            "after the set, choosing Ab for Say is an ordinary deliberate choice",
        )

    def test_nothing_is_frozen_without_a_pick(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        self.assertFalse(karaoke_performance_locks_song_key(session, ""))


class TheSavedKeyCannotBeDeletedEither(unittest.TestCase):
    """Choosing the original key during a performance must not drop the key underneath it."""

    def setUp(self) -> None:
        self.session = performing_session()
        km.retune_now_singing_entry(self.session, "C")

    def test_an_ordinary_clear_is_refused(self) -> None:
        self.assertFalse(clear_practice_concert_key(self.session, SAY))
        self.assertEqual(saved_practice_concert_key(self.session, SAY), "D")

    def test_a_caller_that_means_it_still_gets_through(self) -> None:
        """``force=True`` is "discard the user's saved choice", which is nobody's accident."""
        self.assertTrue(clear_practice_concert_key(self.session, SAY, force=True))
        self.assertEqual(saved_practice_concert_key(self.session, SAY), "")


class LeavingKaraokeLeavesNothingBehind(unittest.TestCase):
    """Bullet 4: no unintended key change left in Backing, Practice or anywhere else."""

    def test_the_live_key_goes_back_to_the_songs_own(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        durable_commit(session, SAY, "Ab")
        self.assertEqual(session["display_key"], "Ab")
        km.stop_session(session)
        self.assertEqual(session["display_key"], "D")
        self.assertEqual(session["concert_key"], "D")

    def test_the_next_sidebar_render_is_asked_for_that_key(self) -> None:
        from songs.key_state import PENDING_DISPLAY_KEY

        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        durable_commit(session, SAY, "Ab")
        km.stop_session(session)
        self.assertEqual(str(session.get(PENDING_DISPLAY_KEY) or ""), "D")

    def test_a_newer_choice_is_not_overwritten(self) -> None:
        """The musician changed the live key again after the retune. That value is theirs."""
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        session["display_key"] = "F"
        session["concert_key"] = "F"
        km.stop_session(session)
        self.assertEqual(session["display_key"], "F")

    def test_the_release_is_silent_when_nothing_was_retuned(self) -> None:
        session = performing_session()
        session["display_key"] = "Bb"
        km.stop_session(session)
        self.assertEqual(session["display_key"], "Bb")

    def test_the_song_with_no_saved_key_of_its_own_falls_back_to_the_entry(self) -> None:
        session = performing_session()
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {}
        km.retune_now_singing_entry(session, "Ab")
        session["display_key"] = "Ab"
        km.stop_session(session)
        self.assertEqual(session["display_key"], "Bb", "the key the setlist says")


class TheRegisterOfRetunedEntries(unittest.TestCase):
    def test_a_retune_records_the_entry(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        ids = km.performance_retuned_entry_ids(session)
        self.assertEqual(ids, [km.get_queue(session)[0]["entry_id"]])

    def test_putting_the_key_back_does_not_hand_ownership_back(self) -> None:
        """The temporary key is lifted; the song's saved key is still not karaoke's to write.

        Otherwise choosing the entry's own Bb mid-performance would write Bb over the saved D -
        the same defect, one step further along.
        """
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        km.retune_now_singing_entry(session, "Bb")
        self.assertEqual(km.performance_keys(session), {})
        self.assertTrue(karaoke_performance_locks_song_key(session, SAY))
        durable_commit(session, SAY, "Bb")
        self.assertEqual(saved_practice_concert_key(session, SAY), "D")

    def test_each_entry_is_recorded_separately(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        km.advance_session(session)
        km.retune_now_singing_entry(session, "E")
        self.assertEqual(len(km.performance_retuned_entry_ids(session)), 2)

    def test_the_register_is_forgotten_with_the_set(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        km.stop_session(session)
        self.assertEqual(km.performance_retuned_entry_ids(session), [])

    def test_nonsense_is_tolerated(self) -> None:
        self.assertEqual(km.performance_retuned_entry_ids({}), [])
        self.assertEqual(km.performance_retuned_entry_ids({km.KARAOKE_PERFORMANCE_RETUNED_KEY: "x"}), [])
        km.note_performance_retune({}, "")  # no entry id, no crash


class NothingTemporaryIsPersisted(unittest.TestCase):
    """An interrupted set: a refresh must not bring tonight's key back, or the freeze with it."""

    def test_neither_session_key_is_in_the_persisted_set(self) -> None:
        import music_persistent_state as mps

        for state_key in (km.KARAOKE_PERFORMANCE_KEYS_KEY, km.KARAOKE_PERFORMANCE_RETUNED_KEY):
            with self.subTest(state_key=state_key):
                self.assertNotIn(state_key, mps._PERSIST_KEYS)
                self.assertNotIn(state_key, mps._LIST_KEYS)

    def test_both_are_underscore_scoped(self) -> None:
        """The convention in this file for "this run only"."""
        self.assertTrue(km.KARAOKE_PERFORMANCE_KEYS_KEY.startswith("_"))
        self.assertTrue(km.KARAOKE_PERFORMANCE_RETUNED_KEY.startswith("_"))

    def test_a_restored_set_sounds_in_the_saved_keys(self) -> None:
        """What a refresh mid-set actually leaves: the queue and the position, nothing temporary."""
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        restored = {
            "instrument": "Voice",
            PRACTICE_KEY_BY_SOURCE_KEY: dict(session[PRACTICE_KEY_BY_SOURCE_KEY]),
            km.KARAOKE_QUEUE_KEY: [dict(e) for e in km.get_queue(session)],
            km.KARAOKE_SESSION_ACTIVE_KEY: True,
            km.KARAOKE_SESSION_INDEX_KEY: 0,
        }
        self.assertEqual(km.current_session_practice_key(restored), "Bb")
        self.assertFalse(karaoke_performance_locks_song_key(restored, SAY))


class TheHelpersDoNotDisturbWhatTheyRead(unittest.TestCase):
    """Reruns and navigation call these constantly. A read must not be a write."""

    def test_asking_repeatedly_changes_nothing(self) -> None:
        session = performing_session()
        km.retune_now_singing_entry(session, "Ab")
        before = (
            dict(session[PRACTICE_KEY_BY_SOURCE_KEY]),
            [dict(e) for e in km.get_queue(session)],
            dict(km.performance_keys(session)),
        )
        for _ in range(5):
            karaoke_performance_locks_song_key(session, SAY)
            km.performance_song_pick(session)
            km.current_session_practice_key(session)
        self.assertEqual(
            (dict(session[PRACTICE_KEY_BY_SOURCE_KEY]),
             [dict(e) for e in km.get_queue(session)],
             dict(km.performance_keys(session))),
            before,
        )

    def test_an_active_session_with_an_empty_queue_does_not_recurse(self) -> None:
        """``get_queue`` reconciles, reconciliation stops the set, and the stop asks these
        helpers what the performance owns. Reading through ``get_queue`` here was a
        RecursionError in two existing tests."""
        session = {km.KARAOKE_SESSION_ACTIVE_KEY: True, km.KARAOKE_QUEUE_KEY: []}
        self.assertEqual(km.get_queue(session), [])
        self.assertFalse(karaoke_performance_locks_song_key(session, SAY))


class CustomAndCompositionAreProtectedToo(unittest.TestCase):
    def setUp(self) -> None:
        self.session: dict = {"instrument": "Voice"}
        self.session[PRACTICE_KEY_BY_SOURCE_KEY] = {"custom::am-1": "Am", "composition::doc-1": "F"}
        for pick, key in (("custom::am-1", "Am"), ("composition::doc-1", "F")):
            km.add_to_queue(self.session, pick, practice_key=key)
        km.start_session(self.session)

    def test_a_custom_progressions_saved_key_is_frozen(self) -> None:
        km.retune_now_singing_entry(self.session, "Cm")
        durable_commit(self.session, "custom::am-1", "Cm")
        self.assertEqual(saved_practice_concert_key(self.session, "custom::am-1"), "Am")

    def test_a_composition_songs_saved_key_is_frozen(self) -> None:
        km.advance_session(self.session)
        km.retune_now_singing_entry(self.session, "G")
        durable_commit(self.session, "composition::doc-1", "G")
        self.assertEqual(saved_practice_concert_key(self.session, "composition::doc-1"), "F")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
