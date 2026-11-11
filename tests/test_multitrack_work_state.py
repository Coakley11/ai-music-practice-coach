"""Issue 64 slice 4: four kinds of "my recording", only one safe to replace.

The failure this guards against is concrete: a musician records a flute take against
*All the Things You Are*, navigates to *Eleanor Rigby*, and the take is gone - or worse,
is still loaded and gets saved into the wrong song. So the question "is anything at
risk" has to be answerable before anything is replaced, and it has to be answerable
without trusting every widget to have remembered to set a flag.
"""

from __future__ import annotations

import unittest

from multitrack_slots import MULTITRACK_SLOTS
from multitrack_work_state import (
    WORK_LOADED_CHANGED,
    WORK_NONE,
    WORK_SAVED_PROJECT,
    WORK_UNSAVED_TAKE,
    WORK_STAMP_KEY,
    classify_work,
    describe_work,
    mark_project_saved,
    switch_guard,
    work_fingerprint,
    work_is_at_risk,
)

SLOT = MULTITRACK_SLOTS[4]          # "Sax / winds"
OTHER = MULTITRACK_SLOTS[0]         # "Guitar"
WAV = b"RIFF" + bytes(2048)
LONGER = b"RIFF" + bytes(4096)


def session(**over):
    state = {"mt_tracks": {}, "mt_backing_prepared_at": ""}
    state.update(over)
    return state


def recorded(slot=SLOT, audio=WAV, **over):
    state = session(mt_tracks={slot: audio})
    state.update(over)
    return state


class EachKindOfWorkIsRecognised(unittest.TestCase):
    def test_an_empty_session_has_nothing_at_risk(self):
        self.assertEqual(classify_work(session()), WORK_NONE)
        self.assertFalse(work_is_at_risk(session()))

    def test_a_take_that_was_never_saved_is_at_risk(self):
        state = recorded()
        self.assertEqual(classify_work(state), WORK_UNSAVED_TAKE)
        self.assertTrue(work_is_at_risk(state))

    def test_a_saved_project_that_matches_disk_is_not_at_risk(self):
        state = recorded(multitrack_catalog_active_id="mt-1")
        mark_project_saved(state)
        self.assertEqual(classify_work(state), WORK_SAVED_PROJECT)
        self.assertFalse(work_is_at_risk(state))

    def test_a_loaded_project_changed_since_is_at_risk(self):
        state = recorded(multitrack_catalog_active_id="mt-1")
        mark_project_saved(state)
        state["mt_tracks"][OTHER] = WAV          # an overdub
        self.assertEqual(classify_work(state), WORK_LOADED_CHANGED)
        self.assertTrue(work_is_at_risk(state))

    def test_an_open_project_with_no_stamp_is_assumed_changed(self):
        """A session that never saw the save cannot claim it matches."""
        state = recorded(multitrack_catalog_active_id="mt-1")
        self.assertNotIn(WORK_STAMP_KEY, state)
        self.assertEqual(classify_work(state), WORK_LOADED_CHANGED)

    def test_prepared_backing_alone_counts_as_work(self):
        state = session(mt_backing_prepared_at="2026-11-10T10:00:00+00:00")
        self.assertNotEqual(classify_work(state), WORK_NONE)


class TheFingerprintNoticesRealChanges(unittest.TestCase):
    def _changed(self, mutate):
        state = recorded(multitrack_catalog_active_id="mt-1")
        before = mark_project_saved(state)
        mutate(state)
        return before != work_fingerprint(state)

    def test_a_new_layer_changes_it(self):
        self.assertTrue(self._changed(
            lambda s: s["mt_tracks"].__setitem__(OTHER, WAV)))

    def test_rerecording_a_slot_changes_it(self):
        self.assertTrue(self._changed(
            lambda s: s["mt_tracks"].__setitem__(SLOT, LONGER)))

    def test_removing_a_layer_changes_it(self):
        self.assertTrue(self._changed(lambda s: s["mt_tracks"].pop(SLOT)))

    def test_a_mixer_move_changes_it(self):
        self.assertTrue(self._changed(
            lambda s: s.__setitem__(f"mt_vol_{SLOT}", 0.4)))

    def test_muting_a_layer_changes_it(self):
        self.assertTrue(self._changed(
            lambda s: s.__setitem__(f"mt_mute_{SLOT}", True)))

    def test_renaming_a_layer_changes_it(self):
        self.assertTrue(self._changed(
            lambda s: s.__setitem__(f"mt_name_{SLOT}", "Second take")))

    def test_choosing_a_different_layer_instrument_changes_it(self):
        self.assertTrue(self._changed(
            lambda s: s.__setitem__(f"mt_layer_instrument_{SLOT}", "Flute")))

    def test_preparing_backing_changes_it(self):
        self.assertTrue(self._changed(
            lambda s: s.__setitem__("mt_backing_prepared_at", "2026-11-10T00:00:00Z")))

    def test_opening_a_different_project_changes_it(self):
        self.assertTrue(self._changed(
            lambda s: s.__setitem__("multitrack_catalog_active_id", "mt-2")))

    def test_touching_nothing_leaves_it_alone(self):
        state = recorded(multitrack_catalog_active_id="mt-1")
        before = mark_project_saved(state)
        state["some_unrelated_widget"] = "anything"
        self.assertEqual(before, work_fingerprint(state))

    def test_saving_again_restamps_it(self):
        state = recorded(multitrack_catalog_active_id="mt-1")
        mark_project_saved(state)
        state["mt_tracks"][OTHER] = WAV
        self.assertEqual(classify_work(state), WORK_LOADED_CHANGED)
        mark_project_saved(state)
        self.assertEqual(classify_work(state), WORK_SAVED_PROJECT)


class TheGuardRefusesToLetWorkVanish(unittest.TestCase):
    def test_an_empty_session_may_be_replaced_without_asking(self):
        guard = switch_guard(session(), reason="song_change", target="Eleanor Rigby")
        self.assertTrue(guard["allowed"])
        self.assertEqual(guard["choices"], [])

    def test_an_unsaved_take_blocks_a_song_change(self):
        guard = switch_guard(recorded(), reason="song_change", target="Eleanor Rigby")
        self.assertFalse(guard["allowed"])
        self.assertIn("never been saved", guard["message"])
        self.assertEqual(guard["target"], "Eleanor Rigby")

    def test_an_unsaved_take_is_offered_save_continue_discard_cancel(self):
        choices = switch_guard(recorded())["choices"]
        self.assertEqual(choices,
                         ["Save as New Project", "Continue Editing", "Discard", "Cancel"])

    def test_a_changed_project_is_also_offered_save_changes(self):
        state = recorded(multitrack_catalog_active_id="mt-1")
        mark_project_saved(state)
        state["mt_tracks"][OTHER] = WAV
        choices = switch_guard(state)["choices"]
        self.assertIn("Save Changes", choices)
        self.assertIn("Save as New Project", choices)
        self.assertIn("Cancel", choices)

    def test_a_saved_project_may_be_replaced_without_asking(self):
        state = recorded(multitrack_catalog_active_id="mt-1")
        mark_project_saved(state)
        self.assertTrue(switch_guard(state)["allowed"])

    def test_the_guard_names_the_project_that_would_be_affected(self):
        state = recorded(multitrack_catalog_active_id="mt-7")
        mark_project_saved(state)
        state["mt_tracks"][OTHER] = WAV
        self.assertEqual(switch_guard(state)["project_id"], "mt-7")

    def test_an_unsaved_take_belongs_to_no_project(self):
        self.assertEqual(switch_guard(recorded())["project_id"], "")

    def test_describe_and_guard_agree(self):
        for state in (session(), recorded(),
                      recorded(multitrack_catalog_active_id="mt-1")):
            with self.subTest(state=classify_work(state)):
                self.assertEqual(describe_work(state)["at_risk"],
                                 not switch_guard(state)["allowed"])


class TheFlutetakeScenario(unittest.TestCase):
    """The user's own example, as a sequence."""

    def test_recording_then_switching_song_is_blocked_until_answered(self):
        state = recorded()                                   # flute take, never saved
        self.assertEqual(classify_work(state), WORK_UNSAVED_TAKE)
        guard = switch_guard(state, reason="song_change", target="Eleanor Rigby")
        self.assertFalse(guard["allowed"])

    def test_saving_first_then_switching_is_allowed(self):
        state = recorded(multitrack_catalog_active_id="mt-attya-bb")
        mark_project_saved(state)
        self.assertTrue(switch_guard(state, target="Eleanor Rigby")["allowed"])

    def test_overdubbing_after_a_load_makes_it_unsafe_again(self):
        state = recorded(multitrack_catalog_active_id="mt-attya-bb")
        mark_project_saved(state)
        state["mt_tracks"][OTHER] = WAV                      # the saxophone overdub
        guard = switch_guard(state, target="Eleanor Rigby")
        self.assertFalse(guard["allowed"])
        self.assertIn("not saved yet", guard["message"])


if __name__ == "__main__":
    unittest.main()
