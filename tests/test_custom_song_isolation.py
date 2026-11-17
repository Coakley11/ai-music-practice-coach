"""P0: saved Custom songs must stay independent (no shared dicts, no stale-widget stamping, safe saves).

Synthetic songs only. The fingerprint reproduced here was seen in production: Trial Song (D-Bm-A-G, key D) ended up
named/keyed/styled like Blues in F minor with its chords transposed to F-Dm-C-Bb and its timestamps untouched.
"""
from __future__ import annotations

import copy
import types
import unittest
import uuid
from unittest import mock

import custom_progression_lab as L


def _song(name, key, chords, style="Pop", bpm=100, artist="SYN"):
    return {
        "id": str(uuid.uuid4()), "name": name, "artist": artist, "original_key_center": key,
        "user_locked_home_key": True, "bpm": bpm, "loops": 2, "time_signature": "4/4",
        "progression_style": style, "groove_style": "Auto",
        "original_sections": {"Verse": [{"bars": 1, "chord": c} for c in chords]},
        "section_labels": {}, "lyrics_by_section": {}, "created_at": 1.0, "updated_at": 2.0,
    }


def _chords(rec):
    return [c["chord"] for c in rec["original_sections"]["Verse"]]


def _canon(store):
    """Saved content that matters (ignores empty-section normalisation that ensure_original_structure adds)."""
    return {
        k: {f: v.get(f) for f in ("id", "name", "artist", "original_key_center", "bpm", "progression_style", "updated_at")}
        | {"chords": [c["chord"] for sec in v["original_sections"].values() for c in sec]}
        for k, v in store.items()
    }


def _world():
    a = _song("SYN Trial", "D", ["D", "Bm", "A", "G"], "Pop", 100, "SYN Cohen")
    b = _song("SYN Blues", "Fm", ["Fm6", "Db7", "C7", "Fm7"], "Blues", 110, "SYN Daniel")
    store = {a["name"]: a, b["name"]: b}
    ss = {"studio_page": "custom", L.CPL_SAVED_KEY: store}
    return a, b, store, copy.deepcopy(store), ss


class TestSharedRecordMutation(unittest.TestCase):
    def test_ensure_original_structure_is_the_root_aliasing_hazard(self) -> None:
        rec = _song("X", "D", ["D"])
        self.assertIs(L.ensure_original_structure(rec), rec)  # documents WHY installers must copy

    def test_load_saved_progression_returns_an_independent_copy(self) -> None:
        _a, _b, store, golden, _ss = _world()
        out = L.load_saved_progression(store, "SYN Trial")
        out["name"] = "CHANGED"
        out["original_sections"]["Verse"][0]["chord"] = "Z"
        self.assertEqual(_canon(store), _canon(golden))

    def test_cpl_active_from_session_detaches_a_stored_record(self) -> None:
        _a, _b, store, golden, ss = _world()
        ss[L.CPL_ACTIVE_KEY] = store["SYN Trial"]  # the pre-fix install: the record itself
        act = L.cpl_active_from_session(ss)
        self.assertIsNot(act, store["SYN Trial"])
        act["name"] = "CHANGED"
        act["original_sections"]["Verse"][0]["chord"] = "Z"
        self.assertEqual(_canon(store), _canon(golden))

    def test_sync_detaches_even_when_called_directly_with_the_record(self) -> None:
        _a, _b, store, golden, ss = _world()
        ss[L.CPL_ACTIVE_KEY] = store["SYN Trial"]
        ss["cpl_title_input"] = "Edited title"
        L.sync_cpl_draft_widgets_to_active(ss, store["SYN Trial"])
        self.assertEqual(_canon(store), _canon(golden))
        self.assertEqual(ss[L.CPL_ACTIVE_KEY]["name"], "Edited title")  # the explicit edit still reaches the DRAFT


class TestSongsPageRestoreSequence(unittest.TestCase):
    """The production fingerprint: Blues open -> Songs page restores Trial -> normal widget sync."""

    def _run(self, *, keep_aliasing=False):
        from songs import state as S

        a, b, store, golden, ss = _world()
        st = types.SimpleNamespace(session_state=ss)
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "SYN Blues"), reset_display_key=True)
        ok = S.apply_saved_custom_pick_key_context(st, "custom::" + a["id"], {}, song_picker_catalog={})
        self.assertTrue(ok)
        if keep_aliasing:
            # Re-create the OLD aliasing on purpose: the widget-owner guard must hold on its own.
            ss[L.CPL_ACTIVE_KEY] = store["SYN Trial"]
            with mock.patch.object(L, "_detached_draft", lambda _s, act: act):
                L.sync_cpl_draft_widgets_to_active(ss, ss[L.CPL_ACTIVE_KEY])
        else:
            L.sync_cpl_draft_widgets_to_active(ss, ss[L.CPL_ACTIVE_KEY])
        return a, b, store, golden, ss

    def test_trial_record_is_not_stamped_with_blues(self) -> None:
        a, _b, store, golden, _ss = self._run()
        self.assertEqual(_canon(store), _canon(golden))
        self.assertEqual(_chords(store["SYN Trial"]), ["D", "Bm", "A", "G"])
        self.assertEqual(store["SYN Trial"]["id"], a["id"])

    def test_stale_widgets_alone_cannot_stamp_another_song(self) -> None:
        _a, _b, store, golden, ss = self._run(keep_aliasing=True)
        self.assertEqual(_canon(store), _canon(golden))
        self.assertTrue(ss.get("_cpl_reseed_widgets_from_active"))

    def test_matching_widgets_still_apply_a_legitimate_edit(self) -> None:
        _a, _b, store, golden, ss = _world()
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "SYN Trial"), reset_display_key=True)
        ss["cpl_title_input"] = "SYN Trial renamed"
        ss["cpl_bpm_builder"] = 90
        act = L.sync_cpl_draft_widgets_to_active(ss, ss[L.CPL_ACTIVE_KEY])
        self.assertEqual((act["name"], act["bpm"]), ("SYN Trial renamed", 90))
        self.assertEqual(_canon(store), _canon(golden))  # nothing is saved until Save

    def test_explicit_original_key_change_still_transposes_the_draft_not_the_library(self) -> None:
        _a, _b, store, golden, ss = _world()
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "SYN Trial"), reset_display_key=True)
        ss["cpl_original_key"] = "F"
        act = L.sync_cpl_draft_widgets_to_active(ss, ss[L.CPL_ACTIVE_KEY])
        self.assertEqual(_chords(act)[:2], ["F", "Dm"])
        self.assertEqual(_canon(store), _canon(golden))

    def test_name_is_not_a_selector_when_two_songs_share_a_title(self) -> None:
        from songs import state as S

        _a, _b, store, _golden, ss = _world()
        store["SYN Trial"]["name"] = "SYN Blues"  # two records now answer to the same title
        st = types.SimpleNamespace(session_state=ss)
        S.apply_saved_custom_pick_key_context(st, "custom::SYN Blues", {}, song_picker_catalog={})
        self.assertNotIn(L.CPL_ACTIVE_KEY, ss)  # ambiguous title -> nothing chosen by name


class TestSaveSafeguards(unittest.TestCase):
    def test_save_from_a_loaded_draft_updates_only_that_record(self) -> None:
        a, _b, store, golden, _ss = _world()
        draft = L.load_saved_progression(store, "SYN Trial")
        draft["bpm"] = 90
        L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(store["SYN Trial"]["bpm"], 90)
        self.assertEqual(store["SYN Trial"]["id"], a["id"])
        self.assertEqual(store["SYN Blues"], golden["SYN Blues"])

    def test_stale_draft_is_refused_and_nothing_changes(self) -> None:
        _a, _b, store, _golden, _ss = _world()
        draft = L.load_saved_progression(store, "SYN Trial")
        store["SYN Trial"]["updated_at"] = 99.0  # changed elsewhere (another device / cloud merge)
        before = copy.deepcopy(store)
        with self.assertRaises(L.SongSaveConflict):
            L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(_canon(store), _canon(before))

    def test_a_draft_not_derived_from_the_owner_of_an_id_cannot_re_identify_it(self) -> None:
        _a, _b, store, golden, _ss = _world()
        draft = L.load_saved_progression(store, "SYN Trial")
        draft["name"] = "Totally New Name"
        draft["base_updated_at"] = 12345.0  # not the version of the record that owns this id
        with self.assertRaises(L.SongSaveConflict):
            L.save_progression_named(store, "Totally New Name", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(_canon(store), _canon(golden))

    def test_legitimate_rename_keeps_the_id_and_does_not_lose_the_old_title(self) -> None:
        a, _b, store, _golden, _ss = _world()
        orig_id = a["id"]
        draft = L.load_saved_progression(store, "SYN Trial")
        draft["name"] = "SYN Trial v2"
        L.save_progression_named(store, "SYN Trial v2", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(store["SYN Trial v2"]["id"], orig_id)
        self.assertIn("SYN Trial", store)
        self.assertEqual(len({v["id"] for v in store.values()}), len(store))
        self.assertEqual(_chords(store["SYN Trial v2"]), ["D", "Bm", "A", "G"])

    def test_picker_labels_never_look_alike(self) -> None:
        a, _b, store, _golden, _ss = _world()
        self.assertEqual(L.saved_progression_label(store, "SYN Trial"), "SYN Trial")
        store["SYN Trial"]["name"] = "SYN Blues"
        l1 = L.saved_progression_label(store, "SYN Trial")
        l2 = L.saved_progression_label(store, "SYN Blues")
        self.assertNotEqual(l1, l2)
        self.assertIn("#" + a["id"][:6], l1)


class TestLyricsTargetsById(unittest.TestCase):
    def test_lyrics_go_to_the_record_with_the_drafts_id_not_the_one_with_its_title(self) -> None:
        import songs.cpl_lyrics_runtime as R

        _a, _b, store, _golden, ss = _world()
        draft = copy.deepcopy(store["SYN Trial"])
        draft["name"] = "SYN Blues"  # a title that belongs to the OTHER saved song
        seen = {}
        with mock.patch.object(L, "save_progression", side_effect=lambda st, name, act, **kw: seen.setdefault("name", name)):
            R._persist_cpl_lyrics_library_copy(ss, draft)
        self.assertEqual(seen.get("name"), "SYN Trial")


if __name__ == "__main__":
    unittest.main()
