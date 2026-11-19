"""P0d: a restored SBI Custom widget value is not a Practice Key edit.

Production (rev 2103 -> 2142): leftover display_key_sbi_custom / _sbi_custom_visit_pk = Fm (from Blues / the deleted phantom) were stamped onto
Trial Song's saved Practice Key (D) by sync_creative_workspace_before_persist on a save, and mirror_custom_practice_key_aliases then wrote the key
and a user-override flag onto every alias pick, including picks that no longer name a live song (phantom, "My Progression", title picks).
"""
from __future__ import annotations

import copy
import unittest
from unittest import mock

import custom_progression_lab as L
import source_session_state as SS
from creative_workspace_persistence import sync_creative_workspace_before_persist
from songs.music_source import LAST_CUSTOM_STATE_KEY

TRIAL_ID = "4c866688-ac33-4a9a-808a-3d00c9b831f4"
BLUES_ID = "a19ddf53-553d-4291-9665-7176b3bab483"
PHANTOM_ID = "e8b24e91-de42-488b-b8dc-6bda11870459"
TRIAL, BLUES, PHANTOM = ("custom::" + TRIAL_ID, "custom::" + BLUES_ID, "custom::" + PHANTOM_ID)
BLUES_VERSE = [("Fm6", 2), ("Db7", 1), ("C7", 1), ("Fm6", 2), ("Db7:3|G7:1", 1), ("C7:2|Bbm7:2", 1), ("Fm7", 1), ("Bb7", 1), ("Fm7", 1), ("C7", 1)]


def _song(sid, name, key, entries, style, bpm):
    return {"id": sid, "name": name, "artist": "SYN", "original_key_center": key, "user_locked_home_key": True, "bpm": bpm, "loops": 2,
            "time_signature": "4/4", "progression_style": style, "groove_style": "Auto",
            "original_sections": {"Verse": [{"bars": b, "chord": c} for c, b in entries]}, "section_labels": {}, "lyrics_by_section": {},
            "created_at": 1.0, "updated_at": 2.0}


def _library():
    t = _song(TRIAL_ID, "Trial Song", "D", [("D", 1), ("Bm", 1), ("A", 1), ("G", 1)], "Pop", 100)
    b = _song(BLUES_ID, "Blues in F minor", "Fm", BLUES_VERSE, "Blues", 110)
    return {t["name"]: t, b["name"]: b}


def _recovered_session(extra_picks=True):
    """Trial is the active Custom song with its own D; the SBI Custom lane is open and still holds the OLD song's Fm."""
    lib = _library()
    pk = {TRIAL: "D", BLUES: "Fm"}
    if extra_picks:  # what production showed: deleted phantom, title picks, generic shell
        pk.update({PHANTOM: "Fm", "custom::Blues in F minor": "Fm", "custom::My Progression": "Fm"})
    return {
        "studio_page": "creative", "active_music_source": "custom_progression", "active_catalog_pick_key": TRIAL,
        "improv_entry_mode": "Play Song-Based Improvisation", "improv_song_source": "Custom progression",
        "sbi_preview_source": "Custom progression", "_restore_sbi_custom_source": True, SS.SBI_CUSTOM_IDENTITY_PICK_KEY: TRIAL,
        "display_key_sbi_custom": "Fm", "_sbi_custom_visit_pk": "Fm", "_creative_visit_practice_key": "Fm", "_creative_visit_source": "sbi_custom",
        L.CPL_SAVED_KEY: lib, L.CPL_ACTIVE_KEY: copy.deepcopy(lib["Trial Song"]),
        LAST_CUSTOM_STATE_KEY: {"active": copy.deepcopy(_song(PHANTOM_ID, "Blues in F minor", "Fm", [("F", 1)], "Blues", 180)),
                                "pick_key": PHANTOM, "name": "Blues in F minor", "practice_key": "Fm", "custom_home_key": "Fm"},
        "practice_key_by_source": pk, "practice_key_user_override_picks": [],
    }


def _canon(lib):
    return {k: (v["id"], v["name"], v["original_key_center"], v["progression_style"], v["bpm"],
                [(c["chord"], c["bars"]) for s in v["original_sections"].values() for c in s]) for k, v in lib.items()}


class TestARestoredWidgetIsNotAnEdit(unittest.TestCase):
    def test_saves_do_not_promote_the_restored_fm_onto_trial(self) -> None:
        ss = _recovered_session()
        before_pk, before_ov, before_lib = copy.deepcopy(ss["practice_key_by_source"]), list(ss["practice_key_user_override_picks"]), _canon(ss[L.CPL_SAVED_KEY])
        for _ in range(4):  # every autosave / page-change save runs the creative sync
            sync_creative_workspace_before_persist(ss)
        self.assertEqual(ss["practice_key_by_source"], before_pk)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "D")
        self.assertEqual(ss["practice_key_user_override_picks"], before_ov)
        self.assertEqual(_canon(ss[L.CPL_SAVED_KEY]), before_lib)

    def test_no_phantom_or_unknown_pick_receives_a_key_or_override(self) -> None:
        ss = _recovered_session(extra_picks=False)
        sync_creative_workspace_before_persist(ss)
        self.assertEqual(set(ss["practice_key_by_source"]), {TRIAL, BLUES})
        self.assertEqual(ss["practice_key_user_override_picks"], [])

    def test_an_explicit_selection_for_this_song_still_persists(self) -> None:
        ss = _recovered_session()
        ss["display_key_sbi_custom"] = "F"  # the musician picks F in the SBI Custom Practice Key control (the widget callback)
        SS.record_sbi_custom_explicit_pk_edit(ss, "F")
        SS.persist_sbi_custom_practice_key_edit(ss, "F")
        sync_creative_workspace_before_persist(ss)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "F")
        self.assertIn(TRIAL, ss["practice_key_user_override_picks"])
        self.assertEqual(ss["practice_key_by_source"][BLUES], "Fm")  # nothing leaks onto the other song
        self.assertEqual(_canon(ss[L.CPL_SAVED_KEY]), _canon(_library()))  # Original Key / chords untouched
        # ... and a later save does not re-stamp it from a stale widget
        ss["display_key_sbi_custom"] = "Fm"
        sync_creative_workspace_before_persist(ss)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "F")

    def test_a_marker_for_another_song_is_discarded(self) -> None:
        ss = _recovered_session(extra_picks=False)
        ss[SS.SBI_CUSTOM_EXPLICIT_PK_EDIT_KEY] = {"song_id": BLUES_ID, "key": "Fm"}  # an edit made while Blues was on screen
        sync_creative_workspace_before_persist(ss)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "D")
        self.assertNotIn(SS.SBI_CUSTOM_EXPLICIT_PK_EDIT_KEY, ss)

    def test_a_marker_for_a_different_key_is_discarded(self) -> None:
        ss = _recovered_session(extra_picks=False)
        ss[SS.SBI_CUSTOM_EXPLICIT_PK_EDIT_KEY] = {"song_id": TRIAL_ID, "key": "F"}  # the control now holds a different, restored value
        sync_creative_workspace_before_persist(ss)
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "D")

    def test_a_marker_is_used_once(self) -> None:
        ss = _recovered_session(extra_picks=False)
        ss["display_key_sbi_custom"] = "F"
        SS.record_sbi_custom_explicit_pk_edit(ss, "F")
        self.assertTrue(SS.consume_sbi_custom_explicit_pk_edit(ss, "F"))
        self.assertFalse(SS.consume_sbi_custom_explicit_pk_edit(ss, "F"))

    def test_alternating_trial_and_blues_never_cross(self) -> None:
        ss = _recovered_session(extra_picks=False)
        for name, pick, key, new in (("Blues in F minor", BLUES, "Fm", "Gm"), ("Trial Song", TRIAL, "D", "E")):
            L.apply_cpl_session_progression(ss, L.load_saved_progression(ss[L.CPL_SAVED_KEY], name), reset_display_key=True)
            ss[SS.SBI_CUSTOM_IDENTITY_PICK_KEY] = pick
            ss["active_catalog_pick_key"] = pick
            ss["display_key_sbi_custom"] = "Fm" if name == "Trial Song" else "D"  # the OTHER song's value is still in the widget
            sync_creative_workspace_before_persist(ss)
            self.assertEqual(ss["practice_key_by_source"][pick], key, name)
            ss["display_key_sbi_custom"] = new
            SS.record_sbi_custom_explicit_pk_edit(ss, new)
            SS.persist_sbi_custom_practice_key_edit(ss, new)
            self.assertEqual(ss["practice_key_by_source"][pick], new)
        self.assertEqual(ss["practice_key_by_source"][BLUES], "Gm")
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "E")
        self.assertEqual(_canon(ss[L.CPL_SAVED_KEY]), _canon(_library()))


class TestAliasMirrorOnlyWritesProvenAliases(unittest.TestCase):
    def test_unknown_deleted_and_title_picks_are_skipped(self) -> None:
        ss = _recovered_session()
        before = copy.deepcopy(ss["practice_key_by_source"])
        SS.mirror_custom_practice_key_aliases(ss, "F", primary_pick=TRIAL)
        pk = ss["practice_key_by_source"]
        self.assertEqual(pk[TRIAL], "F")
        for other in (BLUES, PHANTOM, "custom::Blues in F minor", "custom::My Progression"):
            self.assertEqual(pk[other], before[other], other)
        self.assertNotIn(PHANTOM, ss["practice_key_user_override_picks"])
        self.assertNotIn("custom::My Progression", ss["practice_key_user_override_picks"])

    def test_a_title_pick_of_the_same_live_song_is_an_alias_when_unambiguous(self) -> None:
        ss = _recovered_session(extra_picks=False)
        self.assertTrue(SS._same_custom_song(ss, TRIAL, "custom::Trial Song"))
        self.assertFalse(SS._same_custom_song(ss, TRIAL, "custom::Blues in F minor"))

    def test_two_songs_with_one_title_are_ambiguous(self) -> None:
        ss = _recovered_session(extra_picks=False)
        twin = _song("99999999-0000-0000-0000-000000000001", "Trial Song", "G", [("G", 1)], "Pop", 90)
        ss[L.CPL_SAVED_KEY]["Trial Song (2)"] = twin
        ss[L.CPL_SAVED_KEY]["Trial Song (2)"]["name"] = "Trial Song"
        self.assertEqual(SS._known_custom_song_id(ss, "custom::Trial Song"), "")
        self.assertEqual(SS._known_custom_song_id(ss, TRIAL), TRIAL_ID)

    def test_a_pick_known_only_from_last_custom_memory_is_not_a_live_song(self) -> None:
        ss = _recovered_session(extra_picks=False)
        self.assertEqual(SS._known_custom_song_id(ss, PHANTOM), "")


class TestSaveCallbackAfterTheSyncStillCanonical(unittest.TestCase):
    def test_real_save_callback_keeps_ids_titles_keys_and_chords(self) -> None:
        import streamlit

        ss = _recovered_session()
        golden = _canon(ss[L.CPL_SAVED_KEY])
        for _ in range(3):
            sync_creative_workspace_before_persist(ss)
        with mock.patch.object(streamlit, "session_state", ss), mock.patch(
            "songs.music_source.clear_cpl_intentional_new_song", lambda *_a, **_k: None
        ), mock.patch("custom_song_library.cloud_song_state", return_value={"valid": True, "version": 2.0}), mock.patch(
            "custom_song_library.upsert_custom_song_to_cloud", return_value=(True, "k", None)
        ):
            L.cpl_on_save_library_callback()
        self.assertEqual(_canon(ss[L.CPL_SAVED_KEY]), golden)
        self.assertNotIn(PHANTOM_ID, str([v["id"] for v in ss[L.CPL_SAVED_KEY].values()]))
        self.assertEqual(ss["practice_key_by_source"][TRIAL], "D")


if __name__ == "__main__":
    unittest.main()
