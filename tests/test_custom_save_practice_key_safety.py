"""P0c safety net: no Practice Key state seen in production may change a SAVED song's id, title, Original Key or canonical chords.

Production snapshot after recovery showed per-song Practice Key map / override list drift (Trial D -> C, phantom entries back,
last-Custom memory Trial with Practice Key Fm). These tests put the real session in those states and press the REAL Save callback
(cpl_on_save_library_callback) through the real restore/render sequence; the saved library must stay byte-for-byte canonical.
"""
from __future__ import annotations

import copy
import types
import unittest
from unittest import mock

import custom_progression_lab as L
from songs import state as S

TRIAL_ID = "4c866688-ac33-4a9a-808a-3d00c9b831f4"
BLUES_ID = "a19ddf53-553d-4291-9665-7176b3bab483"
PHANTOM_ID = "e8b24e91-de42-488b-b8dc-6bda11870459"
BLUES_VERSE = [("Fm6", 2), ("Db7", 1), ("C7", 1), ("Fm6", 2), ("Db7:3|G7:1", 1), ("C7:2|Bbm7:2", 1), ("Fm7", 1), ("Bb7", 1), ("Fm7", 1), ("C7", 1)]


def _song(sid, name, key, entries, style, bpm):
    return {"id": sid, "name": name, "artist": "SYN", "original_key_center": key, "user_locked_home_key": True, "bpm": bpm, "loops": 2,
            "time_signature": "4/4", "progression_style": style, "groove_style": "Auto",
            "original_sections": {"Verse": [{"bars": b, "chord": c} for c, b in entries]}, "section_labels": {}, "lyrics_by_section": {},
            "created_at": 1.0, "updated_at": 2.0}


def _world():
    t = _song(TRIAL_ID, "Trial Song", "D", [("D", 1), ("Bm", 1), ("A", 1), ("G", 1)], "Pop", 100)
    b = _song(BLUES_ID, "Blues in F minor", "Fm", BLUES_VERSE, "Blues", 110)
    store = {t["name"]: t, b["name"]: b}
    ss = {"studio_page": "custom", L.CPL_SAVED_KEY: store}
    return store, copy.deepcopy(store), ss


def _canon(store):
    return {k: (v["id"], v["name"], v["original_key_center"], v["progression_style"], v["bpm"],
                [(c["chord"], c["bars"]) for s in v["original_sections"].values() for c in s]) for k, v in store.items()}


# The Practice Key states observed in the post-recovery workspace (and the P0c bug's Fm).
POISON = {
    "practice_key_by_source": {
        "custom::" + TRIAL_ID: "C", "custom::" + BLUES_ID: "Fm", "custom::" + PHANTOM_ID: "Fm", "custom::Blues in F minor": "Fm",
        "custom::My Progression": "Fm", "composition::c08db828-aee4-4a66-9d66-c805c57b9c43": "C",
    },
    "practice_key_user_override_picks": ["custom::" + TRIAL_ID, "custom::" + BLUES_ID, "custom::" + PHANTOM_ID, "custom::Blues in F minor",
                                         "custom::My Progression"],
    "_pk_user_commit_token": "C",
    "_backing_pk_control_owner": "composition",
    "display_key_custom_backing": "Em",
    "display_key_sbi_custom": "Fm",
    "_creative_visit_practice_key": "C",
    L.CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET: "Fm",
    "cpl_last_display_key": "C",
    "display_key": "C",
    "concert_key": "C",
    "_pending_display_key": "C",
}


def _press_save(ss):
    import streamlit

    with mock.patch.object(streamlit, "session_state", ss), mock.patch(
        "songs.music_source.clear_cpl_intentional_new_song", lambda *_a, **_k: None
    ), mock.patch("custom_song_library.cloud_song_state", return_value={"valid": True, "version": 2.0}), mock.patch(
        "custom_song_library.upsert_custom_song_to_cloud", return_value=(True, "k", None)
    ):
        L.cpl_on_save_library_callback()


def _load(ss, store, name):
    L.apply_cpl_session_progression(ss, L.load_saved_progression(store, name), reset_display_key=True)


def _run(ss, persisted_pick):
    st = types.SimpleNamespace(session_state=ss)
    S.apply_saved_custom_pick_key_context(st, persisted_pick, {}, song_picker_catalog={})
    L.apply_pending_custom_original_key(ss, L.cpl_active_from_session(ss))
    return L.sync_cpl_draft_widgets_to_active(ss, L.cpl_active_from_session(ss))


class TestPracticeKeyStatesCannotCorruptASavedSong(unittest.TestCase):
    def _case(self, name, persisted_pick, extra=None):
        store, golden, ss = _world()
        ss.update(copy.deepcopy(POISON))
        ss.update(extra or {})
        _load(ss, store, name)
        _run(ss, persisted_pick)
        _press_save(ss)
        self.assertEqual(_canon(store), _canon(golden), "saved songs changed after Save in a poisoned Practice Key state")
        return store, golden, ss

    def test_trial_with_every_poisoned_practice_key_state(self) -> None:
        self._case("Trial Song", "custom::" + TRIAL_ID)

    def test_blues_with_every_poisoned_practice_key_state(self) -> None:
        self._case("Blues in F minor", "custom::" + BLUES_ID)

    def test_load_trial_while_the_persisted_pick_is_blues_and_poisoned(self) -> None:
        self._case("Trial Song", "custom::" + BLUES_ID)

    def test_load_blues_while_the_persisted_pick_is_the_phantom(self) -> None:
        self._case("Blues in F minor", "custom::" + PHANTOM_ID)

    def test_last_custom_memory_with_a_foreign_practice_key(self) -> None:
        # production: Trial remembered with home key D but Practice Key Fm
        mem = {"_last_custom_song_state": {"name": "Trial Song", "pick_key": "custom::" + TRIAL_ID, "practice_key": "Fm", "custom_home_key": "D"}}
        self._case("Trial Song", "custom::" + TRIAL_ID, mem)

    def test_practice_key_never_changes_the_draft_chords_or_key(self) -> None:
        store, golden, ss = _world()
        ss.update(copy.deepcopy(POISON))
        _load(ss, store, "Trial Song")
        for _ in range(3):
            act = _run(ss, "custom::" + TRIAL_ID)
        self.assertEqual(act["original_key_center"], "D")
        self.assertEqual([c["chord"] for s in act["original_sections"].values() for c in s], ["D", "Bm", "A", "G"])
        self.assertEqual(act["id"], TRIAL_ID)
        self.assertEqual(act["name"], "Trial Song")


class TestBackingPracticeKeyCommitOnACustomSong(unittest.TestCase):
    """A Backing Practice Key commit while a Custom song is the working song (production: Trial's key became C, token C at 06:22:58).

    Measured: a STALE Composition owner stamp is not honoured - the owner resolves to the live source (custom), so the commit lands on
    the Custom song's OWN per-song Practice Key (a legitimate user-style choice, or a widget remount to the default C). It cannot reach
    another song, and it must never reach the saved record.
    """

    def test_a_stale_composition_owner_resolves_to_the_live_custom_song(self) -> None:
        from backing_practice_key_control import resolve_backing_pk_control_owner

        store, golden, ss = _world()
        _load(ss, store, "Trial Song")
        ss["_backing_pk_control_owner"] = "composition"
        self.assertEqual(resolve_backing_pk_control_owner(ss), "custom")

    def test_the_commit_touches_only_the_active_custom_songs_practice_key_and_never_the_saved_record(self) -> None:
        from backing_practice_key_control import commit_backing_practice_key

        store, golden, ss = _world()
        _load(ss, store, "Trial Song")
        ss["practice_key_by_source"] = {"custom::" + TRIAL_ID: "D", "custom::" + BLUES_ID: "Fm", "composition::c08": "C"}
        ss["_backing_pk_control_owner"] = "composition"
        commit_backing_practice_key(ss, "C")
        pk = ss["practice_key_by_source"]
        self.assertEqual(pk.get("custom::" + BLUES_ID), "Fm")
        self.assertEqual(pk.get("composition::c08"), "C")
        act = _run(ss, "custom::" + TRIAL_ID)
        self.assertEqual((act["id"], act["name"], act["original_key_center"]), (TRIAL_ID, "Trial Song", "D"))
        _press_save(ss)
        self.assertEqual(_canon(store), _canon(golden))


if __name__ == "__main__":
    unittest.main()
