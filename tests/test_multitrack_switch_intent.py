"""Issue 64 slice 4: a navigation request held still until it is answered.

The scenario under test is the one that loses work. A flute take exists and has never
been saved. The musician reaches for the Practice Key, or another song, or Load Project.
Streamlit has already moved the widget by the time any code runs, so the question is not
"can we detect this" but "can we hold it, and put it back if they say no".
"""

from __future__ import annotations

import unittest

from multitrack_slots import MULTITRACK_SLOTS
from multitrack_switch_intent import (
    CHOICE_CANCEL,
    CHOICE_CONTINUE_EDITING,
    CHOICE_DISCARD,
    CHOICE_SAVE_AS_NEW,
    CHOICE_SAVE_CHANGES,
    KIND_LOAD_PROJECT,
    KIND_NEW_PROJECT,
    KIND_PRACTICE_KEY,
    KIND_SONG,
    PENDING_KEY,
    clear_pending,
    describe_pending,
    pending_switch,
    request_switch,
    resolve_choice,
    switch_is_pending,
)
from multitrack_work_state import mark_project_saved

SLOT = MULTITRACK_SLOTS[4]
OTHER = MULTITRACK_SLOTS[0]
WAV = b"RIFF" + bytes(2048)


def clean():
    return {"mt_tracks": {}, "display_key": "Bb"}


def unsaved_take():
    return {"mt_tracks": {SLOT: WAV}, "display_key": "Bb"}


def saved_project():
    state = {"mt_tracks": {SLOT: WAV}, "display_key": "Bb",
             "multitrack_catalog_active_id": "mt-1"}
    mark_project_saved(state)
    return state


def changed_project():
    state = saved_project()
    state["mt_tracks"][OTHER] = WAV
    return state


class ACleanWorkspaceIsNeverInterrupted(unittest.TestCase):
    def test_a_song_change_proceeds_at_once(self):
        state = clean()
        asked = request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        self.assertTrue(asked["allowed"])
        self.assertFalse(asked["pending"])
        self.assertFalse(switch_is_pending(state))

    def test_a_saved_project_proceeds_at_once(self):
        state = saved_project()
        self.assertTrue(request_switch(state, kind=KIND_SONG, target="x")["allowed"])
        self.assertNotIn(PENDING_KEY, state)

    def test_a_key_change_on_a_clean_workspace_proceeds(self):
        state = clean()
        self.assertTrue(
            request_switch(state, kind=KIND_PRACTICE_KEY, target="Eb")["allowed"])


class WorkAtRiskHoldsTheRequest(unittest.TestCase):
    def test_an_unsaved_take_holds_a_song_change(self):
        state = unsaved_take()
        asked = request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        self.assertFalse(asked["allowed"])
        self.assertTrue(switch_is_pending(state))
        self.assertEqual(pending_switch(state)["target"], "Eleanor Rigby")

    def test_the_held_request_remembers_what_to_put_back(self):
        state = unsaved_take()
        request_switch(state, kind=KIND_PRACTICE_KEY, target="Eb",
                       revert={"display_key": "Bb"})
        self.assertEqual(pending_switch(state)["revert"], {"display_key": "Bb"})

    def test_a_changed_project_holds_a_project_load(self):
        state = changed_project()
        asked = request_switch(state, kind=KIND_LOAD_PROJECT, target="Rigby E minor",
                               payload={"item_key": "mt-2"})
        self.assertFalse(asked["allowed"])
        self.assertIn(CHOICE_SAVE_CHANGES, asked["choices"])
        self.assertEqual(pending_switch(state)["payload"], {"item_key": "mt-2"})

    def test_the_prompt_names_the_destination(self):
        state = unsaved_take()
        request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        prompt = describe_pending(state)
        self.assertIn("Eleanor Rigby", prompt["heading"])
        self.assertIn("never been saved", prompt["message"])

    def test_the_prompt_for_a_key_change_says_so(self):
        state = unsaved_take()
        request_switch(state, kind=KIND_PRACTICE_KEY, target="Eb")
        self.assertIn("Practice Key", describe_pending(state)["heading"])

    def test_the_prompt_for_a_new_project_says_so(self):
        state = unsaved_take()
        request_switch(state, kind=KIND_NEW_PROJECT)
        self.assertIn("new project", describe_pending(state)["heading"])

    def test_no_prompt_when_nothing_is_pending(self):
        self.assertEqual(describe_pending(clean()), {})


class CancelChangesNothing(unittest.TestCase):
    def test_cancel_puts_the_widget_back(self):
        state = unsaved_take()
        state["display_key"] = "Eb"                     # Streamlit already moved it
        request_switch(state, kind=KIND_PRACTICE_KEY, target="Eb",
                       revert={"display_key": "Bb"})
        outcome = resolve_choice(state, CHOICE_CANCEL)
        self.assertEqual(outcome["status"], "stayed")
        self.assertFalse(outcome["switched"])
        self.assertEqual(state["display_key"], "Bb")

    def test_cancel_leaves_the_recording_untouched(self):
        state = unsaved_take()
        before = dict(state["mt_tracks"])
        request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        resolve_choice(state, CHOICE_CANCEL, apply_switch=self.fail)
        self.assertEqual(state["mt_tracks"], before)
        self.assertFalse(switch_is_pending(state))

    def test_cancel_never_runs_the_navigation(self):
        state = unsaved_take()
        request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        resolve_choice(state, CHOICE_CANCEL,
                       apply_switch=lambda: self.fail("navigated on Cancel"))

    def test_cancel_preserves_the_open_project_and_mixer(self):
        state = changed_project()
        state[f"mt_vol_{SLOT}"] = 0.4
        request_switch(state, kind=KIND_LOAD_PROJECT, target="another")
        resolve_choice(state, CHOICE_CANCEL)
        self.assertEqual(state["multitrack_catalog_active_id"], "mt-1")
        self.assertEqual(state[f"mt_vol_{SLOT}"], 0.4)
        self.assertEqual(sorted(state["mt_tracks"]), sorted([SLOT, OTHER]))

    def test_continue_editing_behaves_like_cancel_but_is_reported_separately(self):
        state = unsaved_take()
        state["display_key"] = "Eb"
        request_switch(state, kind=KIND_PRACTICE_KEY, target="Eb",
                       revert={"display_key": "Bb"})
        outcome = resolve_choice(state, CHOICE_CONTINUE_EDITING,
                                 apply_switch=lambda: self.fail("navigated"))
        self.assertEqual(outcome["choice"], CHOICE_CONTINUE_EDITING)
        self.assertEqual(state["display_key"], "Bb")


class SavingComesBeforeMoving(unittest.TestCase):
    def test_save_changes_then_navigates(self):
        state = changed_project()
        order = []
        request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        outcome = resolve_choice(
            state, CHOICE_SAVE_CHANGES,
            save_changes=lambda: order.append("saved"),
            apply_switch=lambda: order.append("navigated"))
        self.assertEqual(outcome["status"], "switched")
        self.assertEqual(order, ["saved", "navigated"])

    def test_a_failed_save_does_not_navigate(self):
        state = changed_project()
        request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        outcome = resolve_choice(
            state, CHOICE_SAVE_CHANGES,
            save_changes=lambda: (False, "Cloud storage unavailable"),
            apply_switch=lambda: self.fail("navigated after a failed save"))
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("Cloud storage unavailable", outcome["error"])

    def test_a_failed_save_keeps_the_request_open_so_the_musician_is_asked_again(self):
        state = changed_project()
        request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        resolve_choice(state, CHOICE_SAVE_CHANGES,
                       save_changes=lambda: False, apply_switch=self.fail)
        self.assertTrue(switch_is_pending(state))
        self.assertTrue(pending_switch(state)["error"])
        self.assertEqual(pending_switch(state)["target"], "Eleanor Rigby")

    def test_a_raising_save_is_a_failed_save(self):
        state = changed_project()
        request_switch(state, kind=KIND_SONG, target="x")
        outcome = resolve_choice(
            state, CHOICE_SAVE_CHANGES,
            save_changes=lambda: (_ for _ in ()).throw(RuntimeError("disk full")),
            apply_switch=lambda: self.fail("navigated after a raising save"))
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("disk full", outcome["error"])

    def test_retrying_after_a_failed_save_can_succeed(self):
        state = changed_project()
        request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        resolve_choice(state, CHOICE_SAVE_CHANGES, save_changes=lambda: False)
        outcome = resolve_choice(state, CHOICE_SAVE_CHANGES,
                                 save_changes=lambda: True,
                                 apply_switch=lambda: None)
        self.assertEqual(outcome["status"], "switched")
        self.assertFalse(switch_is_pending(state))

    def test_save_as_new_is_a_separate_action(self):
        state = changed_project()
        calls = []
        request_switch(state, kind=KIND_SONG, target="x")
        resolve_choice(state, CHOICE_SAVE_AS_NEW,
                       save_changes=lambda: calls.append("changes"),
                       save_as_new=lambda: calls.append("new"),
                       apply_switch=lambda: None)
        self.assertEqual(calls, ["new"])

    def test_an_unsaved_take_is_not_offered_save_changes(self):
        """There is no project to save *into* yet, so the choice would be a lie."""
        state = unsaved_take()
        asked = request_switch(state, kind=KIND_SONG, target="x")
        self.assertNotIn(CHOICE_SAVE_CHANGES, asked["choices"])
        self.assertIn(CHOICE_SAVE_AS_NEW, asked["choices"])

    def test_a_choice_with_no_action_wired_fails_rather_than_navigating(self):
        state = changed_project()
        request_switch(state, kind=KIND_SONG, target="x")
        outcome = resolve_choice(state, CHOICE_SAVE_CHANGES,
                                 apply_switch=lambda: self.fail("navigated"))
        self.assertEqual(outcome["status"], "failed")
        self.assertTrue(switch_is_pending(state))

    def test_a_failed_navigation_also_keeps_the_request_open(self):
        state = changed_project()
        request_switch(state, kind=KIND_SONG, target="x")
        outcome = resolve_choice(state, CHOICE_SAVE_CHANGES,
                                 save_changes=lambda: True,
                                 apply_switch=lambda: (False, "song not found"))
        self.assertEqual(outcome["status"], "failed")
        self.assertIn("song not found", outcome["error"])


class DiscardIsDeliberateAndNarrow(unittest.TestCase):
    def test_discard_runs_the_discard_then_navigates(self):
        state = unsaved_take()
        order = []
        request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        outcome = resolve_choice(state, CHOICE_DISCARD,
                                 discard=lambda: order.append("discarded"),
                                 apply_switch=lambda: order.append("navigated"))
        self.assertEqual(outcome["status"], "switched")
        self.assertEqual(order, ["discarded", "navigated"])

    def test_a_failed_discard_does_not_navigate(self):
        state = unsaved_take()
        request_switch(state, kind=KIND_SONG, target="x")
        outcome = resolve_choice(state, CHOICE_DISCARD,
                                 discard=lambda: False,
                                 apply_switch=lambda: self.fail("navigated"))
        self.assertEqual(outcome["status"], "failed")

    def test_discard_without_a_discard_action_does_not_navigate(self):
        """Nothing may be thrown away by a navigation that merely forgot to wire it."""
        state = unsaved_take()
        request_switch(state, kind=KIND_SONG, target="x")
        outcome = resolve_choice(state, CHOICE_DISCARD,
                                 apply_switch=lambda: self.fail("navigated"))
        self.assertEqual(outcome["status"], "failed")


class OneAnswerOnlyOnce(unittest.TestCase):
    def test_a_second_click_does_nothing(self):
        state = changed_project()
        saves = []
        request_switch(state, kind=KIND_SONG, target="x")
        first = resolve_choice(state, CHOICE_SAVE_CHANGES,
                               save_changes=lambda: saves.append(1),
                               apply_switch=lambda: None)
        second = resolve_choice(state, CHOICE_SAVE_CHANGES,
                                save_changes=lambda: saves.append(2),
                                apply_switch=lambda: self.fail("navigated twice"))
        self.assertEqual(first["status"], "switched")
        self.assertEqual(second["status"], "stale")
        self.assertEqual(saves, [1])

    def test_a_double_discard_discards_once(self):
        state = unsaved_take()
        calls = []
        request_switch(state, kind=KIND_SONG, target="x")
        resolve_choice(state, CHOICE_DISCARD, discard=lambda: calls.append(1),
                       apply_switch=lambda: None)
        resolve_choice(state, CHOICE_DISCARD, discard=lambda: calls.append(2),
                       apply_switch=lambda: None)
        self.assertEqual(calls, [1])

    def test_answering_after_a_refresh_cleared_the_request_does_nothing(self):
        state = unsaved_take()
        request_switch(state, kind=KIND_SONG, target="x")
        clear_pending(state)                       # a refresh, a page change, a rerun
        outcome = resolve_choice(state, CHOICE_DISCARD,
                                 discard=lambda: self.fail("discarded after refresh"),
                                 apply_switch=lambda: self.fail("navigated"))
        self.assertEqual(outcome["status"], "stale")

    def test_each_held_request_gets_its_own_token(self):
        state = unsaved_take()
        first = request_switch(state, kind=KIND_SONG, target="a")["token"]
        clear_pending(state)
        second = request_switch(state, kind=KIND_SONG, target="b")["token"]
        self.assertNotEqual(first, second)

    def test_a_retry_token_differs_from_the_failed_one(self):
        state = changed_project()
        first = request_switch(state, kind=KIND_SONG, target="x")["token"]
        resolve_choice(state, CHOICE_SAVE_CHANGES, save_changes=lambda: False)
        self.assertNotEqual(pending_switch(state)["token"], first)


class TheFluteTakeSequence(unittest.TestCase):
    """The user's own scenario, end to end, as state transitions."""

    def test_recording_then_reaching_for_another_song_is_held_and_saved_first(self):
        state = unsaved_take()                            # flute take, never saved
        asked = request_switch(state, kind=KIND_SONG, target="Eleanor Rigby")
        self.assertFalse(asked["allowed"])

        saved = {}

        def save_as_new():
            saved["id"] = "mt-attya-bb"
            state["multitrack_catalog_active_id"] = "mt-attya-bb"
            mark_project_saved(state)

        navigated = {}
        outcome = resolve_choice(state, CHOICE_SAVE_AS_NEW,
                                 save_as_new=save_as_new,
                                 apply_switch=lambda: navigated.setdefault("to", "Rigby"))
        self.assertEqual(outcome["status"], "switched")
        self.assertEqual(saved["id"], "mt-attya-bb")
        self.assertEqual(navigated["to"], "Rigby")

        # And the next move costs nothing, because the work is on disk.
        self.assertTrue(request_switch(state, kind=KIND_SONG, target="x")["allowed"])

    def test_changing_the_key_under_an_unsaved_take_is_held(self):
        """A key change must not quietly re-point a take recorded in another key."""
        state = unsaved_take()
        state["display_key"] = "E"                        # the widget already moved
        asked = request_switch(state, kind=KIND_PRACTICE_KEY, target="E",
                               revert={"display_key": "Bb"})
        self.assertFalse(asked["allowed"])
        resolve_choice(state, CHOICE_CANCEL)
        self.assertEqual(state["display_key"], "Bb")


if __name__ == "__main__":
    unittest.main()
