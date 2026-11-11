"""Issue 64 slice 4: the prompt renders the held question and nothing happens without it.

Driven through a small Streamlit double rather than the real app, because what needs
proving here is the wiring: that the question appears at all, that each button runs its
own action and only its own, that a failed save keeps the musician where they are, and
that a second press of the same button cannot act twice.
"""

from __future__ import annotations

import unittest

from multitrack_slots import MULTITRACK_SLOTS
from multitrack_switch_intent import (
    CHOICE_CANCEL,
    CHOICE_CONTINUE_EDITING,
    CHOICE_DISCARD,
    CHOICE_SAVE_AS_NEW,
    KIND_LOAD_PROJECT,
    KIND_NEW_PROJECT,
    KIND_PRACTICE_KEY,
    request_switch,
    switch_is_pending,
)
from multitrack_switch_prompt_ui import (
    APPLIER_KEYS,
    register_applier,
    render_switch_prompt,
)

SLOT = MULTITRACK_SLOTS[4]
WAV = b"RIFF" + bytes(2048)


class Rerun(Exception):
    """Stands in for st.rerun(), which raises to end the script run."""


class FakeSt:
    """Just enough Streamlit: buttons, messages, a container and a raising rerun."""

    def __init__(self, session_state, press=None):
        self.session_state = session_state
        self.press = press
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.captions: list[str] = []
        self.buttons: list[str] = []
        self.reran = False

    # -- containers ---------------------------------------------------------
    def container(self, *_a, **_k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    # -- output -------------------------------------------------------------
    def warning(self, text):
        self.warnings.append(str(text))

    def error(self, text):
        self.errors.append(str(text))

    def caption(self, text):
        self.captions.append(str(text))

    def button(self, label, **_k):
        self.buttons.append(str(label))
        return str(label) == self.press

    def rerun(self):
        self.reran = True
        raise Rerun()


def _render(state, press=None):
    st = FakeSt(state, press=press)
    try:
        rendered = render_switch_prompt(st, state, song_title="All the Things You Are")
    except Rerun:
        rendered = True
    return st, rendered


def unsaved_take(**over):
    state = {"mt_tracks": {SLOT: WAV}, "display_key": "Bb"}
    state.update(over)
    return state


class NothingRendersWhenNothingIsHeld(unittest.TestCase):
    def test_a_clean_session_renders_no_prompt(self):
        st, rendered = _render({"mt_tracks": {}})
        self.assertFalse(rendered)
        self.assertEqual(st.buttons, [])


class TheHeldQuestionRenders(unittest.TestCase):
    def setUp(self):
        self.state = unsaved_take()
        register_applier(self.state, KIND_PRACTICE_KEY, lambda: None)
        request_switch(self.state, kind=KIND_PRACTICE_KEY, target="E",
                       revert={"display_key": "Bb"})

    def test_the_heading_says_where_the_musician_was_going(self):
        st, rendered = _render(self.state)
        self.assertTrue(rendered)
        self.assertTrue(any("Practice Key" in w for w in st.warnings))
        self.assertTrue(any("**E**" in w for w in st.warnings))

    def test_every_offered_choice_gets_a_button(self):
        st, _ = _render(self.state)
        self.assertEqual(st.buttons, [CHOICE_SAVE_AS_NEW, CHOICE_CONTINUE_EDITING,
                                      CHOICE_DISCARD, CHOICE_CANCEL])

    def test_an_unsaved_take_is_not_offered_save_changes(self):
        st, _ = _render(self.state)
        self.assertNotIn("Save Changes", st.buttons)

    def test_the_question_survives_a_rerender(self):
        """A refresh must ask again, not drop the question and lose the take."""
        _render(self.state)
        st, rendered = _render(self.state)
        self.assertTrue(rendered)
        self.assertTrue(switch_is_pending(self.state))


class EachButtonDoesItsOwnThing(unittest.TestCase):
    def test_cancel_reverts_and_does_not_apply(self):
        state = unsaved_take(display_key="E")
        register_applier(state, KIND_PRACTICE_KEY,
                         lambda: self.fail("applied on Cancel"))
        request_switch(state, kind=KIND_PRACTICE_KEY, target="E",
                       revert={"display_key": "Bb"})
        st, _ = _render(state, press=CHOICE_CANCEL)
        self.assertEqual(state["display_key"], "Bb")
        self.assertFalse(switch_is_pending(state))
        self.assertTrue(st.reran)

    def test_continue_editing_keeps_the_recording(self):
        state = unsaved_take()
        register_applier(state, KIND_PRACTICE_KEY,
                         lambda: self.fail("applied on Continue Editing"))
        request_switch(state, kind=KIND_PRACTICE_KEY, target="E")
        _render(state, press=CHOICE_CONTINUE_EDITING)
        self.assertEqual(state["mt_tracks"][SLOT], WAV)

    def test_the_applier_runs_on_discard(self):
        state = unsaved_take()
        applied = []
        register_applier(state, KIND_NEW_PROJECT, lambda: applied.append(1))
        request_switch(state, kind=KIND_NEW_PROJECT)
        _render(state, press=CHOICE_DISCARD)
        self.assertEqual(applied, [1])
        self.assertFalse(switch_is_pending(state))

    def test_discard_clears_the_working_layers_but_asks_nothing_of_the_library(self):
        state = unsaved_take()
        state["mt_track_filenames"] = {}
        register_applier(state, KIND_NEW_PROJECT, lambda: None)
        request_switch(state, kind=KIND_NEW_PROJECT)
        _render(state, press=CHOICE_DISCARD)
        self.assertFalse(any(state["mt_tracks"].values()))
        self.assertFalse(switch_is_pending(state))

    def test_a_second_press_cannot_apply_twice(self):
        state = unsaved_take()
        applied = []
        register_applier(state, KIND_NEW_PROJECT, lambda: applied.append(1))
        request_switch(state, kind=KIND_NEW_PROJECT)
        _render(state, press=CHOICE_DISCARD)
        _render(state, press=CHOICE_DISCARD)       # nothing pending any more
        self.assertEqual(applied, [1])


class DiscardThrowsAwayOnlyTheUnsavedTake(unittest.TestCase):
    """The narrowest requirement in the issue, and the easiest to get wrong.

    Discard exists to drop the working take the musician just said they did not want.
    It must not reach the Project Library, the media catalog or any durable audio - a
    musician who clicks Discard to move on must not lose the project they saved an hour
    ago.
    """

    def _discarded(self, extra):
        from multitrack_switch_intent import KIND_NEW_PROJECT, request_switch

        state = {"mt_tracks": {SLOT: WAV}, "mt_track_filenames": {},
                 "display_key": "Bb"}
        state.update(extra)
        register_applier(state, KIND_NEW_PROJECT, lambda: None)
        request_switch(state, kind=KIND_NEW_PROJECT)
        _render(state, press=CHOICE_DISCARD)
        return state

    def test_the_media_catalog_cache_is_untouched(self):
        from media_persistence import _CATALOG_SESSION_KEY

        catalog = {"multitrack_sessions": [{"item_key": "mt-1", "title": "Bb flute"}]}
        state = self._discarded({_CATALOG_SESSION_KEY: catalog})
        self.assertEqual(state[_CATALOG_SESSION_KEY], catalog)

    def test_the_working_layers_are_cleared(self):
        state = self._discarded({})
        self.assertFalse(any(state["mt_tracks"].values()))

    def test_no_delete_is_wired_into_the_discard_path(self):
        """A source check, because a delete added here would be silent and final."""
        import inspect

        import multitrack_switch_prompt_ui as ui

        source = inspect.getsource(ui._discard_action)
        for forbidden in ("delete", "remove", "tombstone", "unlink", "rmtree"):
            self.assertNotIn(forbidden, source.lower(),
                             f"discard must not {forbidden} anything durable")

    def test_discard_leaves_the_workspace_genuinely_clean(self):
        """Otherwise the very next move asks the same question again.

        `reset_multitrack_working_session` leaves the prepared-backing stamp behind, and
        that stamp alone counts as saveable content - so without clearing it a discard
        would come back still "at risk".
        """
        from multitrack_work_state import work_is_at_risk

        state = self._discarded({"mt_backing_prepared_at": "2026-11-11T09:00:00Z"})
        self.assertFalse(work_is_at_risk(state))


class WithoutAWayToGoThereNothingIsOffered(unittest.TestCase):
    def test_a_missing_applier_leaves_only_the_stay_choices(self):
        """Offering Discard with nowhere to go would destroy a take for nothing."""
        state = unsaved_take()
        request_switch(state, kind=KIND_LOAD_PROJECT, target="Some project")
        st, _ = _render(state)
        self.assertEqual(st.buttons, [CHOICE_CONTINUE_EDITING, CHOICE_CANCEL])
        self.assertTrue(any("unchanged" in c for c in st.captions))

    def test_the_applier_key_is_per_kind(self):
        self.assertEqual(len(set(APPLIER_KEYS.values())), len(APPLIER_KEYS))
        self.assertNotIn("song", APPLIER_KEYS)     # a song move replays its own call


class AFailedSaveKeepsTheMusicianHere(unittest.TestCase):
    def test_a_save_that_fails_shows_the_reason_and_does_not_apply(self):
        import multitrack_switch_prompt_ui as ui

        state = unsaved_take()
        register_applier(state, KIND_NEW_PROJECT,
                         lambda: self.fail("applied after a failed save"))
        request_switch(state, kind=KIND_NEW_PROJECT)

        original = ui._save_action
        ui._save_action = lambda *a, **k: (lambda: (False, "Cloud storage unavailable"))
        try:
            st, _ = _render(state, press=CHOICE_SAVE_AS_NEW)
        finally:
            ui._save_action = original

        self.assertTrue(switch_is_pending(state))
        self.assertTrue(any("Cloud storage unavailable" in e for e in st.errors))
        self.assertEqual(state["mt_tracks"][SLOT], WAV)

    def test_the_error_is_shown_again_on_the_next_render(self):
        import multitrack_switch_prompt_ui as ui

        state = unsaved_take()
        register_applier(state, KIND_NEW_PROJECT, lambda: None)
        request_switch(state, kind=KIND_NEW_PROJECT)
        original = ui._save_action
        ui._save_action = lambda *a, **k: (lambda: (False, "Disk full"))
        try:
            _render(state, press=CHOICE_SAVE_AS_NEW)
        finally:
            ui._save_action = original
        st, _ = _render(state)
        self.assertTrue(any("Disk full" in e for e in st.errors))


if __name__ == "__main__":
    unittest.main()
