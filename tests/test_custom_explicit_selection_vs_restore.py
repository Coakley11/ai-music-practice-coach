"""P0b: a restore of a persisted Custom pick must not undo the song the user just selected on the Songs page.

Browser trace (synthetic): a new session whose last page was Backing (Blues active). Clicking the Trial row installed Trial, then
_finalize_music_workspace_restore -> apply_saved_custom_pick_key_context re-installed Blues from the persisted core pick in the SAME
run, leaving Trial's title / Original Key commit tokens on a Blues draft.
"""
from __future__ import annotations

import copy
import types
import unittest

import custom_progression_lab as L
from songs import music_source as M
from songs import state as S

TRIAL_ID = "11111111-0000-0000-0000-0000000000aa"
BLUES_ID = "22222222-0000-0000-0000-0000000000bb"


def _song(sid, name, key, chords):
    return {"id": sid, "name": name, "artist": "SYN", "original_key_center": key, "user_locked_home_key": True, "bpm": 100, "loops": 2,
            "time_signature": "4/4", "progression_style": "Pop", "groove_style": "Auto",
            "original_sections": {"Verse": [{"bars": 1, "chord": c} for c in chords]}, "section_labels": {}, "lyrics_by_section": {},
            "created_at": 1.0, "updated_at": 2.0}


def _world():
    t = _song(TRIAL_ID, "Smoke Trial", "D", ["D", "Bm", "A", "G"])
    b = _song(BLUES_ID, "Smoke Blues", "Fm", ["Fm", "Gm", "Ab", "Bbm"])
    store = {t["name"]: t, b["name"]: b}
    ss = {"studio_page": "picker", L.CPL_SAVED_KEY: store}
    return store, ss, types.SimpleNamespace(session_state=ss)


class TestExplicitSelectionOutranksARestore(unittest.TestCase):
    def test_a_restored_pick_for_another_song_does_not_undo_the_explicit_selection(self) -> None:
        store, ss, st = _world()
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "Smoke Blues"), reset_display_key=True)
        # the user taps the Trial row: the pending action is applied (stamps the explicit pick)
        ss[M.PENDING_CUSTOM_LIBRARY_ACTION_KEY] = {"action": "load", "name": "Smoke Trial"}
        M.apply_pending_custom_library_action_before_widgets(st, invalidate_backing=lambda *a, **k: None)
        self.assertEqual(L.cpl_active_from_session(ss)["id"], TRIAL_ID)
        self.assertEqual(ss[M.EXPLICIT_CUSTOM_APPLIED_PICK_KEY], "custom::" + TRIAL_ID)
        # the same run's workspace-restore finalisation replays the PERSISTED pick (Blues)
        applied = S.apply_saved_custom_pick_key_context(st, "custom::" + BLUES_ID, {}, song_picker_catalog={})
        self.assertFalse(applied)
        act = L.cpl_active_from_session(ss)
        self.assertEqual((act["id"], act["name"], act["original_key_center"]), (TRIAL_ID, "Smoke Trial", "D"))
        self.assertEqual(L.CPL_COMMIT_OWNER_ID_KEY in ss and ss[L.CPL_COMMIT_OWNER_ID_KEY], TRIAL_ID)

    def test_a_restore_of_the_same_song_still_applies(self) -> None:
        store, ss, st = _world()
        ss[M.PENDING_CUSTOM_LIBRARY_ACTION_KEY] = {"action": "load", "name": "Smoke Trial"}
        M.apply_pending_custom_library_action_before_widgets(st, invalidate_backing=lambda *a, **k: None)
        self.assertTrue(S.apply_saved_custom_pick_key_context(st, "custom::" + TRIAL_ID, {}, song_picker_catalog={}))

    def test_without_an_explicit_selection_a_restore_works_as_before(self) -> None:
        store, ss, st = _world()  # a fresh session: nothing was chosen yet
        self.assertTrue(S.apply_saved_custom_pick_key_context(st, "custom::" + BLUES_ID, {}, song_picker_catalog={}))
        self.assertEqual(L.cpl_active_from_session(ss)["id"], BLUES_ID)

    def test_the_latest_explicit_install_is_the_one_that_is_protected(self) -> None:
        store, ss, st = _world()
        ss[M.PENDING_CUSTOM_LIBRARY_ACTION_KEY] = {"action": "load", "name": "Smoke Trial"}
        M.apply_pending_custom_library_action_before_widgets(st, invalidate_backing=lambda *a, **k: None)
        # the user then loads Blues by another route (Load selected on the Custom page): THAT is now the explicit choice
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "Smoke Blues"), reset_display_key=True)
        self.assertEqual(ss[M.EXPLICIT_CUSTOM_APPLIED_PICK_KEY], "custom::" + BLUES_ID)
        self.assertFalse(S.apply_saved_custom_pick_key_context(st, "custom::" + TRIAL_ID, {}, song_picker_catalog={}))  # a restore of Trial is refused
        self.assertEqual(L.cpl_active_from_session(ss)["id"], BLUES_ID)
        self.assertTrue(S.apply_saved_custom_pick_key_context(st, "custom::" + BLUES_ID, {}, song_picker_catalog={}))  # a restore of Blues is fine


if __name__ == "__main__":
    unittest.main()
