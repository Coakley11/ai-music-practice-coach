"""P0c: Custom page > Load saved or demo charts > Load selected must REPLACE the working song, never transpose the previous one.

Browser trace (synthetic, deployed 77c9d1a6, new session): Trial active, Load selected Blues -> the click installed Blues, then in the next run
_finalize_music_workspace_restore -> apply_saved_custom_pick_key_context re-installed the persisted pick (Trial) and apply_pending_custom_original_key
applied the Original Key written for Blues (Fm) to the Trial draft: D-Bm-A-G became F-Dm-C-Bb under Trial's id. The reverse direction is the same bug.
"""
from __future__ import annotations

import copy
import types
import unittest

import custom_progression_lab as L
from songs import state as S

TRIAL_ID = "11111111-0000-0000-0000-0000000000aa"
BLUES_ID = "22222222-0000-0000-0000-0000000000bb"
BLUES_VERSE = [("Fm6", 2), ("Db7", 1), ("C7", 1), ("Fm6", 2), ("Db7:3|G7:1", 1), ("C7:2|Bbm7:2", 1), ("Fm7", 1), ("Bb7", 1), ("Fm7", 1), ("C7", 1)]


def _song(sid, name, key, entries, style, bpm):
    return {"id": sid, "name": name, "artist": "SYN", "original_key_center": key, "user_locked_home_key": True, "bpm": bpm, "loops": 2,
            "time_signature": "4/4", "progression_style": style, "groove_style": "Auto",
            "original_sections": {"Verse": [{"bars": b, "chord": c} for c, b in entries]}, "section_labels": {}, "lyrics_by_section": {},
            "created_at": 1.0, "updated_at": 2.0}


def _world():
    t = _song(TRIAL_ID, "Smoke Trial", "D", [("D", 1), ("Bm", 1), ("A", 1), ("G", 1)], "Pop", 100)
    b = _song(BLUES_ID, "Smoke Blues", "Fm", BLUES_VERSE, "Blues", 110)
    store = {t["name"]: t, b["name"]: b}
    ss = {"studio_page": "custom", L.CPL_SAVED_KEY: store}
    return store, copy.deepcopy(store), ss, types.SimpleNamespace(session_state=ss)


def _canon(rec):
    return (rec["id"], rec["name"], rec["original_key_center"], rec["progression_style"], rec["bpm"],
            [(c["chord"], c["bars"]) for s in rec["original_sections"].values() for c in s])


def _load_selected(ss, store, name):
    """What the Load selected button does (cpl_page_ui): a COPY of the saved song is installed as the working draft."""
    L.apply_cpl_session_progression(ss, L.load_saved_progression(store, name), reset_display_key=True)


def _next_run(ss, st, persisted_pick):
    """The next script run: workspace-restore finalisation replays the PERSISTED pick, then the Custom page renders."""
    S.apply_saved_custom_pick_key_context(st, persisted_pick, {}, song_picker_catalog={})
    act = L.cpl_active_from_session(ss)
    L.apply_pending_custom_original_key(ss, act)  # cpl_page_ui.py:986
    return L.sync_cpl_draft_widgets_to_active(ss, L.cpl_active_from_session(ss))  # the page's widget -> draft sync


class TestLoadSelectedReplacesTheWorkingSong(unittest.TestCase):
    def _both(self, start, target, persisted_pick):
        store, golden, ss, st = _world()
        _load_selected(ss, store, start)
        _load_selected(ss, store, target)  # the click
        act = _next_run(ss, st, persisted_pick)  # the run after st.rerun()
        return store, golden, ss, act

    def test_trial_active_then_load_blues_even_with_a_stale_persisted_trial_pick(self) -> None:
        store, golden, ss, act = self._both("Smoke Trial", "Smoke Blues", "custom::" + TRIAL_ID)
        self.assertEqual(_canon(act), _canon(golden["Smoke Blues"]))
        self.assertEqual(len([c for s in act["original_sections"].values() for c in s]), 10)
        self.assertEqual({k: _canon(v) for k, v in store.items()}, {k: _canon(v) for k, v in golden.items()})

    def test_blues_active_then_load_trial_even_with_a_stale_persisted_blues_pick(self) -> None:
        store, golden, ss, act = self._both("Smoke Blues", "Smoke Trial", "custom::" + BLUES_ID)
        self.assertEqual(_canon(act), _canon(golden["Smoke Trial"]))
        self.assertEqual({k: _canon(v) for k, v in store.items()}, {k: _canon(v) for k, v in golden.items()})

    def test_alternating_repeatedly_never_mixes_identity_key_or_chords(self) -> None:
        store, golden, ss, st = _world()
        stale = "custom::" + TRIAL_ID
        for i in range(6):
            for name in ("Smoke Trial", "Smoke Blues"):
                _load_selected(ss, store, name)
                act = _next_run(ss, st, stale)
                self.assertEqual(_canon(act), _canon(golden[name]), "cycle %d %s" % (i, name))
                stale = "custom::" + (BLUES_ID if name == "Smoke Trial" else TRIAL_ID)  # the persisted pick is always the OTHER song
        self.assertEqual({k: _canon(v) for k, v in store.items()}, {k: _canon(v) for k, v in golden.items()})


class TestOriginalKeyTokensBelongToTheirSong(unittest.TestCase):
    def test_a_pending_key_and_key_box_written_for_another_song_are_ignored(self) -> None:
        store, golden, ss, st = _world()
        _load_selected(ss, store, "Smoke Trial")
        ss[L.PENDING_CPL_ORIGINAL_KEY] = "Fm"
        ss[L.CPL_ORIGINAL_KEY_COMMIT] = "Fm"
        ss["cpl_original_key"] = "Fm"
        ss[L.CPL_COMMIT_OWNER_ID_KEY] = BLUES_ID
        ss[L.CPL_WIDGET_OWNER_ID_KEY] = BLUES_ID
        act = L.apply_pending_custom_original_key(ss, L.cpl_active_from_session(ss))
        self.assertEqual(_canon(act), _canon(golden["Smoke Trial"]))

    def test_tokens_written_for_this_song_still_apply(self) -> None:
        store, golden, ss, st = _world()
        _load_selected(ss, store, "Smoke Trial")
        ss[L.PENDING_CPL_ORIGINAL_KEY] = "F"
        ss[L.CPL_ORIGINAL_KEY_COMMIT] = "F"
        ss["cpl_original_key"] = "F"
        ss[L.CPL_COMMIT_OWNER_ID_KEY] = TRIAL_ID
        ss[L.CPL_WIDGET_OWNER_ID_KEY] = TRIAL_ID
        act = L.apply_pending_custom_original_key(ss, L.cpl_active_from_session(ss))
        self.assertEqual(act["original_key_center"], "F")
        self.assertEqual([c["chord"] for c in act["original_sections"]["Verse"]][:2], ["F", "Dm"])

    def test_the_users_own_key_chip_still_transposes_the_song_they_are_editing(self) -> None:
        import streamlit
        from unittest import mock

        store, golden, ss, st = _world()
        _load_selected(ss, store, "Smoke Trial")
        with mock.patch.object(streamlit, "session_state", ss):
            L.on_cpl_original_key_chip("F")
        self.assertEqual(ss[L.CPL_EXPLICIT_KEY_EDIT_ID_KEY], TRIAL_ID)
        self.assertEqual(L.cpl_active_from_session(ss)["original_key_center"], "F")

    def test_every_explicit_install_records_the_chosen_song(self) -> None:
        store, golden, ss, st = _world()
        _load_selected(ss, store, "Smoke Blues")
        self.assertEqual(ss[L.CPL_EXPLICIT_APPLIED_PICK_KEY], "custom::" + BLUES_ID)


if __name__ == "__main__":
    unittest.main()
