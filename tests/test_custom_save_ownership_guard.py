"""P0b: a Custom song's Original Key / name change only through the USER's deliberate action for THAT song.

Synthetic songs only. Reproduces the browser failure: Trial (D-Bm-A-G, D) saved while carrying another song's Practice
Key became F-Dm-C-Bb / Fm and took Blues' name, and its real content moved to a new id.
"""
from __future__ import annotations

import copy
import types
import unittest
import uuid
from unittest import mock

import custom_progression_lab as L

TRIAL_ID = "11111111-0000-0000-0000-0000000000aa"
BLUES_ID = "22222222-0000-0000-0000-0000000000bb"


def _song(sid, name, key, chords, bpm=100):
    return {"id": sid, "name": name, "artist": "SYN", "original_key_center": key, "user_locked_home_key": True, "bpm": bpm, "loops": 2,
            "time_signature": "4/4", "progression_style": "Pop", "groove_style": "Auto",
            "original_sections": {"Verse": [{"bars": 1, "chord": c} for c in chords]}, "section_labels": {}, "lyrics_by_section": {},
            "created_at": 1.0, "updated_at": 2.0}


def _world():
    t = _song(TRIAL_ID, "Smoke Trial", "D", ["D", "Bm", "A", "G"])
    b = _song(BLUES_ID, "Smoke Blues", "Fm", ["Fm", "Gm", "Ab", "Bbm"], bpm=110)
    store = {t["name"]: t, b["name"]: b}
    return store, copy.deepcopy(store)


def _canon(store):
    return {k: (v["id"], v["name"], v["original_key_center"], [c["chord"] for s in v["original_sections"].values() for c in s], v["bpm"]) for k, v in store.items()}


def _hybrid_draft(store):
    """What the browser produced: Trial's id, Blues' name and key, Trial's chords moved up three semitones."""
    d = L.load_saved_progression(store, "Smoke Trial")
    d["name"], d["original_key_center"] = "Smoke Blues", "Fm"
    d["original_sections"] = {"Verse": [{"bars": 1, "chord": c} for c in ["F", "Dm", "C", "Bb"]]}
    return d


class TestSaveRefusesInconsistentDrafts(unittest.TestCase):
    def test_the_exact_browser_corruption_is_refused_and_changes_nothing(self) -> None:
        store, golden = _world()
        d = _hybrid_draft(store)
        with mock.patch("custom_song_library.upsert_custom_song_to_cloud") as up:
            with self.assertRaises(L.InconsistentDraftRefused) as c:
                L.save_progression_named(store, d["name"], d, explicit_edits={"original_key": False, "name": False})
        self.assertIn("nothing was saved", str(c.exception))
        up.assert_not_called()
        self.assertEqual(_canon(store), _canon(golden))

    def test_also_refused_by_the_legacy_save_path_without_intent_flags(self) -> None:
        store, golden = _world()
        d = _hybrid_draft(store)
        with self.assertRaises(L.InconsistentDraftRefused):
            L.save_progression(store, d["name"], d)
        self.assertEqual(_canon(store), _canon(golden))

    def test_chords_moved_while_the_key_label_stayed_are_refused_too(self) -> None:
        store, golden = _world()
        d = L.load_saved_progression(store, "Smoke Trial")
        d["original_sections"] = {"Verse": [{"bars": 1, "chord": c} for c in ["F", "Dm", "C", "Bb"]]}  # key still D
        with self.assertRaises(L.InconsistentDraftRefused):
            L.save_progression_named(store, "Smoke Trial", d, explicit_edits={"original_key": False, "name": False})
        self.assertEqual(_canon(store), _canon(golden))

    def test_a_deliberate_original_key_change_still_works(self) -> None:
        store, _golden = _world()
        d = L.load_saved_progression(store, "Smoke Trial")
        d = L.set_original_key_center(d, "F")  # the user's explicit transposition
        L.save_progression_named(store, "Smoke Trial", d, explicit_edits={"original_key": True, "name": False})
        self.assertEqual(store["Smoke Trial"]["original_key_center"], "F")
        self.assertEqual([c["chord"] for c in store["Smoke Trial"]["original_sections"]["Verse"]][:2], ["F", "Dm"])
        self.assertEqual(store["Smoke Trial"]["id"], TRIAL_ID)
        self.assertEqual(_canon(store)["Smoke Blues"], _canon(_world()[0])["Smoke Blues"])

    def test_ordinary_chord_edits_need_no_intent_flag(self) -> None:
        store, _golden = _world()
        d = L.load_saved_progression(store, "Smoke Trial")
        d["original_sections"]["Verse"].append({"bars": 1, "chord": "E"})
        d["original_sections"]["Verse"][0]["chord"] = "Dmaj7"
        L.save_progression_named(store, "Smoke Trial", d, explicit_edits={"original_key": False, "name": False})
        self.assertEqual([c["chord"] for c in store["Smoke Trial"]["original_sections"]["Verse"]], ["Dmaj7", "Bm", "A", "G", "E"])

    def test_a_deliberate_rename_works_and_keeps_the_id(self) -> None:
        store, _golden = _world()
        d = L.load_saved_progression(store, "Smoke Trial")
        d["name"] = "Smoke Trial v2"
        L.save_progression_named(store, "Smoke Trial v2", d, explicit_edits={"original_key": False, "name": True})
        self.assertEqual(store["Smoke Trial v2"]["id"], TRIAL_ID)

    def test_a_rename_nobody_asked_for_is_refused(self) -> None:
        store, golden = _world()
        d = L.load_saved_progression(store, "Smoke Trial")
        d["name"] = "Smoke Blues"  # another song's title stamped on this one (duplicate name)
        with self.assertRaises(L.InconsistentDraftRefused):
            L.save_progression_named(store, "Smoke Blues", d, explicit_edits={"original_key": False, "name": False})
        self.assertEqual(_canon(store), _canon(golden))

    def test_a_new_song_and_legacy_callers_are_unaffected(self) -> None:
        store, _golden = _world()
        fresh = _song(str(uuid.uuid4()), "Brand New", "G", ["G", "C"])
        L.save_progression_named(store, "Brand New", fresh, explicit_edits={"original_key": False, "name": False})
        self.assertIn("Brand New", store)
        d = L.load_saved_progression(store, "Smoke Trial")
        d["bpm"] = 90
        L.save_progression(store, "Smoke Trial", d)  # same key, same name: fine
        self.assertEqual(store["Smoke Trial"]["bpm"], 90)

    def test_unlocked_drafts_that_auto_detect_their_key_are_not_blocked(self) -> None:
        store, _golden = _world()
        store["Smoke Trial"]["user_locked_home_key"] = False
        d = L.load_saved_progression(store, "Smoke Trial")
        d["original_key_center"] = "G"
        L.save_progression_named(store, "Smoke Trial", d, explicit_edits={"original_key": False, "name": False})
        self.assertEqual(store["Smoke Trial"]["original_key_center"], "G")


class TestRealSaveCallback(unittest.TestCase):
    """Through the real Save button callback, with the stale session state the browser produced."""

    def _run(self, ss):
        import streamlit

        with mock.patch.object(streamlit, "session_state", ss), mock.patch(
            "songs.music_source.clear_cpl_intentional_new_song", lambda *_a, **_k: None
        ), mock.patch("custom_song_library.cloud_song_state", return_value=None), mock.patch(
            "custom_song_library.upsert_custom_song_to_cloud", return_value=(False, "", "not_configured")
        ):
            L.cpl_on_save_library_callback()

    def _trial_session(self):
        store, golden = _world()
        ss = {"studio_page": "custom", L.CPL_SAVED_KEY: store}
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "Smoke Trial"), reset_display_key=True)
        return store, golden, ss

    def _stale_blues_tokens(self, ss):
        """The previous song's pending/commit tokens and widgets, as left behind by the half-applied handoff."""
        ss[L.PENDING_CPL_ORIGINAL_KEY] = "Fm"
        ss[L.CPL_ORIGINAL_KEY_COMMIT] = "Fm"
        ss[L.PENDING_CPL_TITLE] = "Smoke Blues"
        ss[L.CPL_TITLE_COMMIT] = "Smoke Blues"
        ss[L.CPL_COMMIT_OWNER_ID_KEY] = BLUES_ID
        ss[L.CPL_WIDGET_OWNER_ID_KEY] = BLUES_ID
        ss["cpl_title_input"], ss["cpl_name"], ss["cpl_original_key"] = "Smoke Blues", "Smoke Blues", "Fm"

    def test_stale_tokens_from_the_previous_song_cannot_rename_or_rekey_this_one(self) -> None:
        store, golden, ss = self._trial_session()
        self._stale_blues_tokens(ss)
        self._run(ss)
        self.assertEqual(_canon(store), _canon(golden), ss.get("_cpl_save_library_flash"))

    def test_a_hybrid_draft_in_the_session_never_changes_the_saved_song(self) -> None:
        store, golden, ss = self._trial_session()
        ss[L.CPL_ACTIVE_KEY] = _hybrid_draft(store)  # the draft itself is already mixed up
        ss[L.CPL_COMMIT_OWNER_ID_KEY] = TRIAL_ID
        ss[L.CPL_WIDGET_OWNER_ID_KEY] = TRIAL_ID
        ss.pop("cpl_title_input", None)
        ss.pop("cpl_name", None)
        ss.pop(L.CPL_TITLE_COMMIT, None)
        ss.pop(L.PENDING_CPL_TITLE, None)
        self._run(ss)
        # Either refused with a plain warning, or repaired to the song's own committed key; never saved as the mix.
        flash = ss.get("_cpl_save_library_flash")
        self.assertTrue(flash is True or str(flash).startswith(L.SAVE_REFUSED_FLASH_PREFIX), flash)
        self.assertEqual(_canon(store), _canon(golden))

    def test_the_hybrid_draft_with_no_trusted_tokens_is_refused_with_a_plain_warning(self) -> None:
        store, golden, ss = self._trial_session()
        ss[L.CPL_ACTIVE_KEY] = _hybrid_draft(store)
        for k in (L.PENDING_CPL_ORIGINAL_KEY, L.CPL_ORIGINAL_KEY_COMMIT, L.PENDING_CPL_TITLE, L.CPL_TITLE_COMMIT, "cpl_title_input", "cpl_name", "cpl_original_key"):
            ss.pop(k, None)
        ss[L.CPL_COMMIT_OWNER_ID_KEY] = TRIAL_ID
        ss[L.CPL_WIDGET_OWNER_ID_KEY] = TRIAL_ID
        self._run(ss)
        flash = str(ss.get("_cpl_save_library_flash"))
        self.assertTrue(flash.startswith(L.SAVE_REFUSED_FLASH_PREFIX), flash)
        self.assertEqual(_canon(store), _canon(golden))

    def test_the_users_own_key_chip_for_this_song_is_honoured(self) -> None:
        import streamlit

        store, golden, ss = self._trial_session()
        with mock.patch.object(streamlit, "session_state", ss):
            L.on_cpl_original_key_chip("F")  # the user taps F for Trial
        self.assertEqual(ss.get(L.CPL_EXPLICIT_KEY_EDIT_ID_KEY), TRIAL_ID)
        self._run(ss)
        self.assertEqual(store["Smoke Trial"]["original_key_center"], "F")
        self.assertEqual(store["Smoke Trial"]["id"], TRIAL_ID)
        self.assertEqual(_canon(store)["Smoke Blues"], _canon(golden)["Smoke Blues"])

    def test_an_explicit_key_choice_made_for_another_song_does_not_carry_over(self) -> None:
        store, golden, ss = self._trial_session()
        ss[L.CPL_EXPLICIT_KEY_EDIT_ID_KEY] = BLUES_ID  # intent was recorded for Blues
        ss[L.PENDING_CPL_ORIGINAL_KEY] = "Fm"
        ss[L.CPL_COMMIT_OWNER_ID_KEY] = BLUES_ID
        self._run(ss)
        self.assertEqual(_canon(store), _canon(golden))

    def test_switching_songs_clears_the_intent_markers(self) -> None:
        store, _golden, ss = self._trial_session()
        ss[L.CPL_EXPLICIT_KEY_EDIT_ID_KEY] = TRIAL_ID
        ss[L.CPL_EXPLICIT_RENAME_ID_KEY] = TRIAL_ID
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "Smoke Blues"), reset_display_key=True)
        self.assertNotIn(L.CPL_EXPLICIT_KEY_EDIT_ID_KEY, ss)
        self.assertNotIn(L.CPL_EXPLICIT_RENAME_ID_KEY, ss)
        self.assertEqual(ss[L.CPL_COMMIT_OWNER_ID_KEY], BLUES_ID)


if __name__ == "__main__":
    unittest.main()
