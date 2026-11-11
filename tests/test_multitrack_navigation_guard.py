"""Issue 64 slice 4: telling a musician's song change apart from the app's own.

`commit_catalog_active_song` is the single door for both, so the guard has to be exact.
Guard a restore and the app loses its active song on every refresh; guard nothing and an
unsaved take is carried into the wrong song. The tests below pin both edges, because
getting this wrong in either direction is worse than not guarding at all.

They also check that a Practice Key change cannot rewrite the key a layer was recorded
in - the one thing that would quietly falsify a musician's own recording.
"""

from __future__ import annotations

import unittest

from multitrack_navigation_guard import (
    APPROVED_PICK_KEY,
    RESTORE_REASONS,
    USER_SELECTION_REASONS,
    approve_song_commit,
    hold_song_commit_if_needed,
    song_commit_is_user_selection,
)
from multitrack_slots import MULTITRACK_SLOTS
from multitrack_switch_intent import PENDING_KEY, pending_switch, switch_is_pending
from multitrack_work_state import mark_project_saved

SLOT = MULTITRACK_SLOTS[4]
WAV = b"RIFF" + bytes(2048)
PICK_A = "catalog::all-the-things-you-are"
PICK_B = "catalog::eleanor-rigby"


def session(*, pick=PICK_A, tracks=True):
    state = {"active_catalog_pick_key": pick}
    state["mt_tracks"] = {SLOT: WAV} if tracks else {}
    return state


class OnlyARealSelectionCounts(unittest.TestCase):
    def test_a_restore_is_not_a_selection(self):
        for reason in sorted(RESTORE_REASONS):
            with self.subTest(reason=reason):
                self.assertFalse(song_commit_is_user_selection(
                    session(), pick_key=PICK_B, reason=reason))

    def test_a_deliberate_pick_of_another_song_is_a_selection(self):
        for reason in sorted(USER_SELECTION_REASONS):
            with self.subTest(reason=reason):
                self.assertTrue(song_commit_is_user_selection(
                    session(), pick_key=PICK_B, reason=reason))

    def test_recommitting_the_same_song_is_not_a_selection(self):
        """A remount arrives with a selection reason and the song already active."""
        self.assertFalse(song_commit_is_user_selection(
            session(pick=PICK_A), pick_key=PICK_A, reason="song_pick"))

    def test_an_unknown_reason_is_not_treated_as_a_selection(self):
        self.assertFalse(song_commit_is_user_selection(
            session(), pick_key=PICK_B, reason="some_internal_resync"))

    def test_an_empty_reason_is_not_a_selection(self):
        self.assertFalse(song_commit_is_user_selection(
            session(), pick_key=PICK_B, reason=""))

    def test_the_first_activation_of_a_session_is_not_guarded(self):
        """With no song active yet there is nothing to move away from."""
        state = {"mt_tracks": {SLOT: WAV}}
        self.assertFalse(song_commit_is_user_selection(
            state, pick_key=PICK_B, reason="song_pick"))

    def test_whitespace_in_a_pick_does_not_make_it_a_different_song(self):
        self.assertFalse(song_commit_is_user_selection(
            session(pick=PICK_A), pick_key=f"  {PICK_A} ", reason="song_pick"))


class TheCommitIsHeldOnlyWhenWorkIsAtRisk(unittest.TestCase):
    def test_a_selection_with_an_unsaved_take_is_held(self):
        state = session()
        self.assertTrue(hold_song_commit_if_needed(
            state, pick_key=PICK_B, reason="song_pick", song_title="Eleanor Rigby"))
        self.assertTrue(switch_is_pending(state))
        self.assertEqual(pending_switch(state)["target"], "Eleanor Rigby")

    def test_a_selection_with_a_clean_workspace_is_not_held(self):
        state = session(tracks=False)
        self.assertFalse(hold_song_commit_if_needed(
            state, pick_key=PICK_B, reason="song_pick"))
        self.assertNotIn(PENDING_KEY, state)

    def test_a_selection_with_a_saved_project_is_not_held(self):
        state = session()
        state["multitrack_catalog_active_id"] = "mt-1"
        mark_project_saved(state)
        self.assertFalse(hold_song_commit_if_needed(
            state, pick_key=PICK_B, reason="song_pick"))

    def test_a_restore_is_never_held_even_with_an_unsaved_take(self):
        """Holding a restore would leave the session with no active song at all."""
        for reason in sorted(RESTORE_REASONS):
            with self.subTest(reason=reason):
                state = session()
                self.assertFalse(hold_song_commit_if_needed(
                    state, pick_key=PICK_B, reason=reason))
                self.assertNotIn(PENDING_KEY, state)

    def test_the_held_request_keeps_the_whole_call_for_replay(self):
        state = session()
        sentinel = object()
        hold_song_commit_if_needed(
            state, pick_key=PICK_B, reason="song_pick", song_title="Eleanor Rigby",
            replay={"st": sentinel, "pick_key": PICK_B, "reason": "song_pick"})
        payload = pending_switch(state)["payload"]
        self.assertEqual(payload["pick_key"], PICK_B)
        self.assertIs(payload["replay"]["st"], sentinel)

    def test_the_title_is_used_for_the_prompt_and_the_pick_as_a_fallback(self):
        state = session()
        hold_song_commit_if_needed(state, pick_key=PICK_B, reason="song_pick")
        self.assertEqual(pending_switch(state)["target"], PICK_B)


class ApprovalLetsExactlyOneCommitThrough(unittest.TestCase):
    def test_an_approved_pick_is_not_held(self):
        state = session()
        approve_song_commit(state, PICK_B)
        self.assertFalse(hold_song_commit_if_needed(
            state, pick_key=PICK_B, reason="song_pick"))

    def test_the_approval_is_consumed(self):
        state = session()
        approve_song_commit(state, PICK_B)
        hold_song_commit_if_needed(state, pick_key=PICK_B, reason="song_pick")
        self.assertNotIn(APPROVED_PICK_KEY, state)
        # A second commit of the same pick is held again.
        self.assertTrue(hold_song_commit_if_needed(
            state, pick_key=PICK_B, reason="song_pick"))

    def test_an_approval_for_one_song_does_not_cover_another(self):
        state = session()
        approve_song_commit(state, PICK_B)
        self.assertTrue(hold_song_commit_if_needed(
            state, pick_key="catalog::something-else", reason="song_pick"))
        self.assertEqual(state.get(APPROVED_PICK_KEY), PICK_B)


class OnlyOneQuestionAtATime(unittest.TestCase):
    def test_a_second_destination_does_not_replace_the_first(self):
        state = session()
        hold_song_commit_if_needed(state, pick_key=PICK_B, reason="song_pick",
                                   song_title="Eleanor Rigby")
        held = hold_song_commit_if_needed(state, pick_key="catalog::third",
                                          reason="song_pick", song_title="Third Song")
        self.assertTrue(held)                               # still not committed
        self.assertEqual(pending_switch(state)["target"], "Eleanor Rigby")


class APracticeKeyChangeCannotRewriteARecordedKey(unittest.TestCase):
    """The stamp belongs to the performance, not to the sidebar.

    `note_layer_recorded` is called at exactly one place - as a layer's audio is stored -
    so nothing in a key change can reach it. This pins that, because the day a second
    caller appears on a key-change path is the day a musician's Bb take starts claiming
    it was played in E.
    """

    def test_changing_the_practice_key_leaves_the_stamp_alone(self):
        from multitrack_recording_identity import (
            MT_LAYER_RECORDING_KEYS_KEY,
            layer_recording_keys,
            note_layer_recorded,
        )

        state = {"mt_tracks": {SLOT: WAV}, "display_key": "Bb", "concert_key": "Bb"}
        note_layer_recorded(state, SLOT, concert_key="Bb")
        self.assertEqual(layer_recording_keys(state)[SLOT], "Bb")

        state["display_key"] = "E"              # the musician moves the sidebar control
        state["concert_key"] = "E"
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY][SLOT], "Bb")

    def test_every_caller_of_the_stamp_is_a_place_the_key_is_actually_known(self):
        """The property that matters is *who* may stamp, not how many.

        Two callers are legitimate and both are listed here by name, so a third one
        arriving fails this test and has to justify itself:

        * the app storing audio - the layer is being recorded right now, so the key the
          musician is playing against is the key;
        * a musician answering "which key was this recorded in?" for a legacy project -
          their own account of what they played, which is testimony rather than
          inference.

        What must never appear is a Practice Key change path. A sidebar key change
        reaching this function is how a B flat take starts claiming it was played in E.
        """
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parent.parent
        allowed = {
            "streamlit_music_practice_app.py": "audio is being stored",
            "multitrack_project_key_restore.py": "the musician stated the key",
        }
        callers: dict[str, list[int]] = {}
        for path in root.glob("*.py"):
            if path.name == "multitrack_recording_identity.py":
                continue
            for n, line in enumerate(
                    path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if re.search(r"\bnote_layer_recorded\s*\(", line):
                    callers.setdefault(path.name, []).append(n)

        self.assertEqual(
            set(callers), set(allowed),
            f"note_layer_recorded callers changed: {callers}. A new one must be a place "
            f"the recording key is genuinely known, never a key-change path.",
        )

    def test_the_stamp_is_not_reachable_from_a_practice_key_change(self):
        """A key change must not be able to restamp a take, directly or nearby."""
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parent.parent
        text = (root / "multitrack_project_key_restore.py").read_text(
            encoding="utf-8", errors="replace")
        # The only function there that stamps is the one driven by the musician's answer.
        stamping_fns = []
        current = ""
        for line in text.splitlines():
            m = re.match(r"^def (\w+)", line)
            if m:
                current = m.group(1)
            if re.search(r"\bnote_layer_recorded\s*\(", line) and current:
                stamping_fns.append(current)
        self.assertEqual(sorted(set(stamping_fns)), ["confirm_project_recording_key"])

    def test_restoring_a_key_does_not_stamp_any_layer(self):
        """Reopening a project must not write keys onto its layers."""
        from multitrack_project_key_restore import restore_practice_key_for_project
        from multitrack_recording_identity import MT_LAYER_RECORDING_KEYS_KEY

        state = {"mt_tracks": {SLOT: WAV}}
        row = {
            "multitrack_id": "mt-1",
            "tracks": [{"slot": SLOT, "recording_concert_key": "Bb"}],
            "activity_source_context": {"source_type": "catalog", "source_id": PICK_A},
        }
        restore_practice_key_for_project(state, row)
        self.assertFalse(state.get(MT_LAYER_RECORDING_KEYS_KEY))


if __name__ == "__main__":
    unittest.main()
