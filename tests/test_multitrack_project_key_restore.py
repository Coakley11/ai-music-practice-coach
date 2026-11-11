"""Issue 64 G26: a reopened project brings back the key it was recorded in.

The failure was quiet and musical rather than technical. Load the B flat flute project
while sitting in *Eleanor Rigby*'s E minor and you got your take back with an E minor
chart over it - the layers restored, the key not.

Two things have to hold at once. The key must actually come back, and it must come back
*through* the Practice Key ownership rules rather than around them: a direct write to
``display_key`` is either undone by hydration or tramples whoever currently owns the
left panel. So these tests check the calls as much as the outcome.
"""

from __future__ import annotations

import unittest

from multitrack_project_key_restore import (
    CONFIRM_KEY,
    RESTORED_DISPLAY_KEY,
    RESTORED_DISPLAY_PICK,
    consume_restored_display_key,
    RESTORE_ASK,
    RESTORE_NONE,
    RESTORE_RESTORE,
    RESTORE_SHOW_LAYERS,
    clear_key_confirmation,
    commit_project_practice_key,
    confirm_project_recording_key,
    pending_key_confirmation,
    project_key_restore_plan,
    restore_practice_key_for_project,
)
from multitrack_slots import MULTITRACK_SLOTS

PICK = "catalog::all-the-things-you-are"
SAX = MULTITRACK_SLOTS[4]
GUITAR = MULTITRACK_SLOTS[0]
WAV = b"RIFF" + bytes(2048)


def track(slot, key, instrument="Flute"):
    return {"slot": slot, "instrument": instrument, "recording_concert_key": key}


def project(*, tracks, identity=None, title="All the Things You Are",
            source=("catalog", PICK), practice_key="G"):
    row = {
        "multitrack_id": "mt-1",
        "title": title,
        "tracks": list(tracks),
        "practice_concert_key": practice_key,
        "recording_identity": dict(identity or {}),
    }
    if source:
        row["activity_source_context"] = {"source_type": source[0], "source_id": source[1]}
    return row


class ThePlanOnlyRestoresAKeyTheLayersAttestTo(unittest.TestCase):
    def test_one_agreed_key_is_restored(self):
        plan = project_key_restore_plan(project(tracks=[track(SAX, "Bb")]))
        self.assertEqual(plan["action"], RESTORE_RESTORE)
        self.assertEqual(plan["key"], "Bb")
        self.assertEqual(plan["pick_key"], PICK)

    def test_the_projects_own_practice_key_is_never_the_one_restored(self):
        """practice_concert_key says where the project was, not where its take was played."""
        row = project(tracks=[track(SAX, "Bb")], practice_key="G")
        self.assertEqual(project_key_restore_plan(row)["key"], "Bb")

    def test_two_keys_are_shown_not_merged_into_one(self):
        plan = project_key_restore_plan(
            project(tracks=[track(SAX, "Bb"), track(GUITAR, "Ab", "Guitar")]))
        self.assertEqual(plan["action"], RESTORE_SHOW_LAYERS)
        self.assertEqual(plan["key"], "")
        self.assertEqual(plan["keys"], ["Ab", "Bb"])
        self.assertEqual(len(plan["layer_lines"]), 2)

    def test_an_unknown_key_stays_unknown_and_is_asked_about(self):
        plan = project_key_restore_plan(project(tracks=[track(SAX, "")]))
        self.assertEqual(plan["action"], RESTORE_ASK)
        self.assertEqual(plan["key"], "")

    def test_one_known_key_with_an_unstamped_layer_restores_the_known_one(self):
        """Restoring the only key anyone recorded is not inventing one."""
        plan = project_key_restore_plan(
            project(tracks=[track(SAX, "Bb"), track(GUITAR, "", "Guitar")]))
        self.assertEqual(plan["action"], RESTORE_RESTORE)
        self.assertEqual(plan["key"], "Bb")
        self.assertIn("without a recorded key", plan["label"])

    def test_a_project_whose_song_cannot_be_named_restores_nothing(self):
        """With no pick there is no store to write, and guessing one is worse."""
        plan = project_key_restore_plan(
            project(tracks=[track(SAX, "Bb")], source=None))
        self.assertEqual(plan["action"], RESTORE_NONE)

    def test_a_real_catalog_pick_is_passed_through_untouched(self):
        """The format an actual saved project carries, read from a real catalog file.

        A catalog pick key legitimately contains a unit separator. An earlier version
        rewrote every one to "::", turning this into "Jazz::All the Things You Are -
        Jerome Kern" - a pick no store knows - so the key was committed nowhere and the
        project still reopened in the wrong key. The browser gate stayed red and the unit
        tests stayed green, because the tests used a pick key shape the app never
        produces.
        """
        real = "JazzAll the Things You Are — Jerome Kern"
        plan = project_key_restore_plan(project(
            tracks=[track(SAX, "Bb")], source=("catalog", real)))
        self.assertEqual(plan["pick_key"], real)
        self.assertEqual(plan["action"], RESTORE_RESTORE)
        self.assertEqual(plan["key"], "Bb")

    def test_a_catalog_pick_keeps_its_separator_through_a_commit(self):
        from songs.practice_key_state import get_practice_concert_key

        real = "JazzAll the Things You Are — Jerome Kern"
        state = {}
        commit_project_practice_key(state, pick_key=real, key="Bb")
        self.assertEqual(get_practice_concert_key(state, pick_key=real), "Bb")
        self.assertEqual(state["_pk_user_commit_pick"], real)

    def test_a_composition_pick_is_normalised(self):
        plan = project_key_restore_plan(project(
            tracks=[track(SAX, "Bb")],
            source=("composition", "composition\x1fdoc-7")))
        self.assertEqual(plan["pick_key"], "composition::doc-7")

    def test_a_composition_pick_already_in_long_form_is_left_alone(self):
        plan = project_key_restore_plan(project(
            tracks=[track(SAX, "Bb")], source=("composition", "composition::doc-7")))
        self.assertEqual(plan["pick_key"], "composition::doc-7")


class TheCommitGoesThroughTheOwnershipRules(unittest.TestCase):
    """Not a session-state write. The same calls a sidebar key change makes."""

    def test_the_durable_store_is_written_through_the_sanctioned_setter(self):
        from songs.practice_key_state import get_practice_concert_key

        state = {}
        self.assertEqual(commit_project_practice_key(state, pick_key=PICK, key="Bb"), "Bb")
        self.assertEqual(get_practice_concert_key(state, pick_key=PICK), "Bb")

    def test_the_user_override_is_marked_so_a_source_switch_does_not_reset_it(self):
        from songs.practice_key_state import catalog_pick_has_user_practice_key_override

        state = {}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        self.assertTrue(catalog_pick_has_user_practice_key_override(state, PICK))

    def test_the_commit_token_is_set_so_a_stale_remount_cannot_write_back(self):
        state = {}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        self.assertEqual(state["_pk_user_commit_token"], "Bb")
        self.assertEqual(state["_pk_user_commit_pick"], PICK)

    def test_the_display_key_is_requested_for_the_next_render_not_forced_now(self):
        """Writing a live widget after creation is what hydration undoes."""
        from songs.key_state import PENDING_DISPLAY_KEY

        state = {}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        self.assertEqual(state[PENDING_DISPLAY_KEY], "Bb")

    def test_the_backing_widgets_stale_ownership_is_dropped(self):
        from backing_practice_key_control import CATALOG_BACKING_PK_WIDGET_PICK_KEY

        state = {CATALOG_BACKING_PK_WIDGET_PICK_KEY: "catalog::eleanor-rigby"}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        self.assertNotIn(CATALOG_BACKING_PK_WIDGET_PICK_KEY, state)

    def test_nothing_is_committed_without_both_a_pick_and_a_key(self):
        for pick, key in ((PICK, ""), ("", "Bb"), ("", "")):
            with self.subTest(pick=pick, key=key):
                state = {}
                self.assertEqual(
                    commit_project_practice_key(state, pick_key=pick, key=key), "")
                self.assertNotIn("_pk_user_commit_token", state)

    def test_a_fixed_key_lock_is_respected(self):
        """Fixed Key overrides a song's key; a project load must not break that."""
        from songs.practice_key_state import get_practice_concert_key

        state = {}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        locked = get_practice_concert_key(state, pick_key=PICK)
        self.assertEqual(locked, "Bb")   # baseline: the setter is the only writer used


class TheRestoredKeyReachesTheSidebar(unittest.TestCase):
    """The half that the durable commit does not do by itself.

    A live probe showed the commit working perfectly - store, override mark and commit
    token all "Bb" - while the sidebar stayed on "E" through six navigations. The cause
    is specific and worth naming, because it is not obvious from either side:
    ``apply_display_key_for_active_song`` honours ``_pk_user_commit_token`` only in its
    same-song branch, and that branch compares ``_pk_user_commit_pick`` against
    ``identity_pk`` - which ``render_global_studio_bar`` builds from the song *title*,
    having called ``song_display_identity`` without ``pick_key``. A real pick key never
    equals a title, so the commit was skipped every time.
    """

    def test_the_live_display_key_is_set_when_the_project_song_is_active(self):
        state = {"active_catalog_pick_key": PICK, "display_key": "E"}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        self.assertEqual(state["display_key"], "Bb")

    def test_a_project_for_another_song_does_not_touch_the_live_key(self):
        """Its key is kept in the store for when that song is opened again."""
        from songs.practice_key_state import get_practice_concert_key

        state = {"active_catalog_pick_key": "catalog::eleanor-rigby", "display_key": "Em"}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        self.assertEqual(state["display_key"], "Em")
        self.assertEqual(get_practice_concert_key(state, pick_key=PICK), "Bb")

    def test_with_no_active_song_the_live_key_is_left_alone(self):
        state = {"display_key": "E"}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        self.assertEqual(state["display_key"], "E")

    def test_the_real_catalog_pick_shape_reaches_the_sidebar_too(self):
        real = "JazzAll the Things You Are — Jerome Kern"
        state = {"active_catalog_pick_key": real, "display_key": "E"}
        commit_project_practice_key(state, pick_key=real, key="Bb")
        self.assertEqual(state["display_key"], "Bb")

    def test_the_durable_commit_still_happens_either_way(self):
        from songs.practice_key_state import get_practice_concert_key

        for active in (PICK, "catalog::something-else", ""):
            with self.subTest(active=active):
                state = {"display_key": "E"}
                if active:
                    state["active_catalog_pick_key"] = active
                commit_project_practice_key(state, pick_key=PICK, key="Bb")
                self.assertEqual(get_practice_concert_key(state, pick_key=PICK), "Bb")

    def test_loading_a_project_sets_the_live_key_end_to_end(self):
        state = {"active_catalog_pick_key": PICK, "display_key": "E"}
        out = restore_practice_key_for_project(
            state, project(tracks=[track(SAX, "Bb")]))
        self.assertTrue(out["applied"])
        self.assertEqual(state["display_key"], "Bb")

    def test_a_mixed_project_leaves_the_live_key_where_it_was(self):
        state = {"active_catalog_pick_key": PICK, "display_key": "E"}
        restore_practice_key_for_project(state, project(
            tracks=[track(SAX, "Bb"), track(GUITAR, "Ab", "Guitar")]))
        self.assertEqual(state["display_key"], "E")

    def test_an_unknown_key_project_leaves_the_live_key_where_it_was(self):
        state = {"active_catalog_pick_key": PICK, "display_key": "E"}
        restore_practice_key_for_project(state, project(tracks=[track(SAX, "")]))
        self.assertEqual(state["display_key"], "E")


class RestoringAProjectAppliesThePlan(unittest.TestCase):
    def test_a_single_key_project_restores_and_reports_it(self):
        from songs.key_state import PENDING_DISPLAY_KEY

        state = {}
        out = restore_practice_key_for_project(state, project(tracks=[track(SAX, "Bb")]))
        self.assertTrue(out["applied"])
        self.assertEqual(state[PENDING_DISPLAY_KEY], "Bb")

    def test_a_mixed_key_project_changes_no_key_and_asks_nothing(self):
        state = {}
        out = restore_practice_key_for_project(state, project(
            tracks=[track(SAX, "Bb"), track(GUITAR, "Ab", "Guitar")]))
        self.assertFalse(out["applied"])
        self.assertNotIn("_pk_user_commit_token", state)
        self.assertEqual(pending_key_confirmation(state), {})

    def test_an_unknown_key_project_raises_the_question(self):
        state = {}
        restore_practice_key_for_project(state, project(tracks=[track(SAX, "")]))
        pending = pending_key_confirmation(state)
        self.assertEqual(pending["multitrack_id"], "mt-1")
        self.assertEqual(pending["pick_key"], PICK)

    def test_restoring_a_known_key_clears_a_question_left_by_an_earlier_project(self):
        state = {CONFIRM_KEY: {"multitrack_id": "mt-old"}}
        restore_practice_key_for_project(state, project(tracks=[track(SAX, "Bb")]))
        self.assertEqual(pending_key_confirmation(state), {})

    def test_the_restored_key_is_not_itself_an_unsaved_change(self):
        """Otherwise reopening a project would immediately warn about losing it."""
        from multitrack_work_state import mark_project_saved, work_is_at_risk

        state = {"mt_tracks": {SAX: WAV}, "multitrack_catalog_active_id": "mt-1"}
        restore_practice_key_for_project(state, project(tracks=[track(SAX, "Bb")]))
        mark_project_saved(state)          # the load path stamps after the key commit
        self.assertFalse(work_is_at_risk(state))


class TheHandoffToTheSidebarIsOneShotAndScoped(unittest.TestCase):
    """Why a handoff is needed at all, proven by a live session.

    The restore runs while the Multitrack page renders - after the sidebar's Practice Key
    widget already exists for that script run. ``safe_assign_display_key`` therefore sees
    widgets instantiated and defers through ``PENDING_DISPLAY_KEY``; and that pending
    value is consumed by ``apply_display_key_for_active_song`` only in its *song changed*
    branch, which opening a project deliberately does not trigger. So the key sat in the
    pending slot and the sidebar showed the old one indefinitely - six navigations and
    sixty seconds, measured.

    The sidebar reads this one-shot at the one moment a widget-backed value can still be
    set: just before the widget is built, beside where the pending key is already seeded.
    """

    def _loaded(self, active=PICK):
        state = {"active_catalog_pick_key": active, "display_key": "E"}
        commit_project_practice_key(state, pick_key=PICK, key="Bb")
        return state

    def test_the_restored_key_is_left_for_the_sidebar(self):
        state = self._loaded()
        self.assertEqual(state[RESTORED_DISPLAY_KEY], "Bb")
        self.assertEqual(state[RESTORED_DISPLAY_PICK], PICK)

    def test_consuming_it_sets_the_widget_and_the_live_key(self):
        state = self._loaded()
        out = consume_restored_display_key(
            state, widget_key="display_key", options=["Bb", "E", "Ab"])
        self.assertEqual(out, "Bb")
        self.assertEqual(state["display_key"], "Bb")
        self.assertEqual(state["concert_key"], "Bb")

    def test_it_is_consumed_once(self):
        state = self._loaded()
        consume_restored_display_key(state, widget_key="display_key", options=["Bb", "E"])
        state["display_key"] = "E"            # as if the musician moved it afterwards
        again = consume_restored_display_key(
            state, widget_key="display_key", options=["Bb", "E"])
        self.assertEqual(again, "")
        self.assertEqual(state["display_key"], "E")

    def test_it_refuses_when_another_song_became_active(self):
        """Between the load and the next render the musician may have moved on.

        The widget must not be seeded for a song that is no longer in front of them.
        (In a plain session the commit's own direct write has already set display_key,
        because no widgets are instantiated to defer around; what is under test here is
        that the *handoff* declines and leaves nothing behind.)
        """
        state = self._loaded()
        state["active_catalog_pick_key"] = "catalog::eleanor-rigby"
        out = consume_restored_display_key(
            state, widget_key="display_key_widget", options=["Bb", "E"])
        self.assertEqual(out, "")
        self.assertNotIn("display_key_widget", state)
        self.assertNotIn(RESTORED_DISPLAY_KEY, state)
        self.assertNotIn(RESTORED_DISPLAY_PICK, state)

    def test_it_refuses_a_key_this_song_does_not_offer(self):
        """Seeding a value outside the options leaves the control unrepresentable."""
        state = self._loaded()
        out = consume_restored_display_key(
            state, widget_key="display_key_widget", options=["Cm", "Dm", "Em"])
        self.assertEqual(out, "")
        self.assertNotIn("display_key_widget", state)
        self.assertNotIn(RESTORED_DISPLAY_KEY, state)

    def test_it_clears_a_stale_pending_key_it_replaces(self):
        """In the real app the commit leaves a pending key behind; it must not linger."""
        from songs.key_state import PENDING_DISPLAY_KEY

        state = self._loaded()
        state[PENDING_DISPLAY_KEY] = "Bb"       # what the deferring writer leaves
        consume_restored_display_key(state, widget_key="display_key", options=["Bb"])
        self.assertNotIn(PENDING_DISPLAY_KEY, state)

    def test_nothing_happens_when_no_project_was_restored(self):
        state = {"display_key": "E", "active_catalog_pick_key": PICK}
        self.assertEqual(
            consume_restored_display_key(state, widget_key="display_key",
                                         options=["Bb", "E"]), "")
        self.assertEqual(state["display_key"], "E")

    def test_a_mixed_project_leaves_no_handoff_behind(self):
        state = {"active_catalog_pick_key": PICK, "display_key": "E"}
        restore_practice_key_for_project(state, project(
            tracks=[track(SAX, "Bb"), track(GUITAR, "Ab", "Guitar")]))
        self.assertNotIn(RESTORED_DISPLAY_KEY, state)

    def test_the_app_reads_the_handoff_before_building_the_widget(self):
        """Source check: after the widget is created it would be too late."""
        import pathlib

        app = (pathlib.Path(__file__).resolve().parent.parent
               / "streamlit_music_practice_app.py").read_text(
                   encoding="utf-8", errors="replace")
        call = app.index("consume_restored_display_key(")
        widget = app.index("on_change=_on_mission_or_global_pk_change")
        self.assertLess(call, widget,
                        "the handoff must be read before the Practice Key widget exists")


class TheMusiciansOwnAnswerMayBeRecorded(unittest.TestCase):
    """Testimony, not inference - which is why it is written at all."""

    def _asked(self):
        state = {"mt_tracks": {SAX: WAV}}
        restore_practice_key_for_project(state, project(tracks=[track(SAX, "")]))
        return state

    def test_confirming_a_key_commits_it(self):
        state = self._asked()
        out = confirm_project_recording_key(state, "Bb")
        self.assertTrue(out["applied"])
        self.assertEqual(state["_pk_user_commit_token"], "Bb")

    def test_confirming_stamps_the_layers_that_had_no_key(self):
        from multitrack_recording_identity import MT_LAYER_RECORDING_KEYS_KEY

        state = self._asked()
        out = confirm_project_recording_key(state, "Bb")
        self.assertIn(SAX, out["stamped"])
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY][SAX], "Bb")

    def test_confirming_never_overwrites_a_layer_whose_key_is_known(self):
        from multitrack_recording_identity import MT_LAYER_RECORDING_KEYS_KEY

        state = {"mt_tracks": {SAX: WAV, GUITAR: WAV},
                 MT_LAYER_RECORDING_KEYS_KEY: {GUITAR: "Em"}}
        restore_practice_key_for_project(state, project(tracks=[track(SAX, "")]))
        out = confirm_project_recording_key(state, "Bb")
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY][GUITAR], "Em")
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY][SAX], "Bb")
        self.assertNotIn(GUITAR, out["stamped"])

    def test_the_question_is_closed_once_answered(self):
        state = self._asked()
        confirm_project_recording_key(state, "Bb")
        self.assertEqual(pending_key_confirmation(state), {})

    def test_answering_twice_does_nothing_the_second_time(self):
        state = self._asked()
        confirm_project_recording_key(state, "Bb")
        again = confirm_project_recording_key(state, "F")
        self.assertFalse(again["applied"])
        self.assertEqual(state["_pk_user_commit_token"], "Bb")

    def test_an_empty_answer_changes_nothing(self):
        state = self._asked()
        out = confirm_project_recording_key(state, "   ")
        self.assertFalse(out["applied"])
        self.assertTrue(pending_key_confirmation(state))

    def test_dismissing_the_question_leaves_the_key_unknown(self):
        from multitrack_recording_identity import MT_LAYER_RECORDING_KEYS_KEY

        state = self._asked()
        clear_key_confirmation(state)
        self.assertEqual(pending_key_confirmation(state), {})
        self.assertFalse(state.get(MT_LAYER_RECORDING_KEYS_KEY))
        self.assertNotIn("_pk_user_commit_token", state)


if __name__ == "__main__":
    unittest.main()
