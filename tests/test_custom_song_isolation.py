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


class TestEmptyDraftCannotOverwriteAPopulatedSong(unittest.TestCase):
    """Blues lost its chords in production (empty sections, default 100 BPM). Whatever the trigger, a chordless
    draft must not silently replace a saved song that has chords - while a deliberate emptying still works."""

    def test_blank_default_shaped_draft_with_the_songs_id_is_refused(self) -> None:
        _a, b, store, golden, _ss = _world()
        blank = L.default_active_progression()
        blank.update({"id": b["id"], "name": b["name"], "artist": b["artist"], "original_key_center": "Fm",
                      "progression_style": "Blues"})
        with self.assertRaises(L.EmptyDraftOverwriteRefused):
            L.save_progression_named(store, b["name"], blank)
        with self.assertRaises(L.EmptyDraftOverwriteRefused):  # even with a matching version
            L.save_progression_named(store, b["name"], blank, expected_updated_at=b["updated_at"])
        self.assertEqual(_canon(store), _canon(golden))

    def test_blank_draft_that_only_shares_the_title_is_refused_too(self) -> None:
        _a, b, store, golden, _ss = _world()
        blank = L.default_active_progression()
        blank["name"] = b["name"]  # no id at all
        with self.assertRaises(L.EmptyDraftOverwriteRefused):
            L.save_progression_named(store, b["name"], blank)
        self.assertEqual(_canon(store), _canon(golden))

    def test_a_brand_new_empty_song_can_still_be_saved(self) -> None:
        _a, _b, store, _golden, _ss = _world()
        fresh = L.start_new_progression()
        fresh["name"] = "SYN Brand New"
        L.save_progression_named(store, "SYN Brand New", fresh)
        self.assertIn("SYN Brand New", store)

    def test_deliberately_emptying_a_song_is_allowed(self) -> None:
        _a, b, store, _golden, ss = _world()
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "SYN Blues"), reset_display_key=True)
        active = L.cpl_active_from_session(ss)
        L.cpl_save_draft(ss, active, {"Verse": []}, persist=False)  # the user removed every chord
        self.assertEqual(ss.get(L.USER_EMPTIED_SONG_ID_KEY), b["id"])
        draft = L.cpl_active_from_session(ss)
        L.save_progression_named(store, "SYN Blues", draft, expected_updated_at=draft["base_updated_at"], allow_empty=True)
        self.assertEqual(_chords(store["SYN Blues"]) if store["SYN Blues"]["original_sections"].get("Verse") else [], [])

    def test_switching_songs_forgets_the_emptied_marker(self) -> None:
        _a, _b, store, _golden, ss = _world()
        ss[L.USER_EMPTIED_SONG_ID_KEY] = "whatever"
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "SYN Trial"), reset_display_key=True)
        self.assertNotIn(L.USER_EMPTIED_SONG_ID_KEY, ss)

    def test_lyrics_save_never_replaces_saved_chords_with_an_empty_draft(self) -> None:
        import songs.cpl_lyrics_runtime as R

        _a, b, store, golden, ss = _world()
        blank = L.default_active_progression()
        blank.update({"id": b["id"], "name": b["name"]})
        blank["lyrics_by_section"] = {"Verse": "la"}
        R._persist_cpl_lyrics_library_copy(ss, blank)
        self.assertEqual(_canon(ss[L.CPL_SAVED_KEY]), _canon(golden))


class TestStaleSessionCannotOverwriteTheCloud(unittest.TestCase):
    """A tab opened before a repair holds an older copy. Its save must not overwrite a newer cloud row, nor bring back
    a row that was deleted elsewhere. An unreadable cloud never blocks an offline save."""

    def _draft(self, store):
        return L.load_saved_progression(store, "SYN Trial")

    def test_a_cloud_row_newer_than_the_draft_refuses_the_save(self) -> None:
        _a, _b, store, golden, _ss = _world()
        draft = self._draft(store)
        with mock.patch("custom_song_library.cloud_song_state", return_value={"valid": True, "version": draft["base_updated_at"] + 500}):
            with self.assertRaises(L.SongSaveConflict):
                L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(_canon(store), _canon(golden))

    def test_a_row_deleted_elsewhere_is_not_resurrected_by_a_stale_save(self) -> None:
        _a, _b, store, golden, _ss = _world()
        draft = self._draft(store)
        with mock.patch("custom_song_library.cloud_song_state", return_value={"valid": False, "version": 0.0}):
            with self.assertRaises(L.SongSaveConflict):
                L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(_canon(store), _canon(golden))

    def test_an_unchanged_cloud_row_allows_the_save(self) -> None:
        _a, _b, store, _golden, _ss = _world()
        draft = self._draft(store)
        draft["bpm"] = 90
        with mock.patch("custom_song_library.cloud_song_state", return_value={"valid": True, "version": draft["base_updated_at"]}):
            L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(store["SYN Trial"]["bpm"], 90)

    def test_an_unreadable_cloud_does_not_block_an_offline_save(self) -> None:
        _a, _b, store, _golden, _ss = _world()
        draft = self._draft(store)
        draft["bpm"] = 91
        with mock.patch("custom_song_library.cloud_song_state", side_effect=RuntimeError("down")):
            L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(store["SYN Trial"]["bpm"], 91)

    def test_cloud_song_state_reads_valid_and_version_and_tolerates_failure(self) -> None:
        import custom_song_library as lib

        row = {"valid": False, "updated_at": "x", "payload": {"progression": {"updated_at": 123.5}}}
        with mock.patch.object(lib, "cloud_enabled", return_value=True), mock.patch("suite_account.load_saved_item_state", return_value=row):
            self.assertEqual(lib.cloud_song_state("abc"), {"valid": False, "version": 123.5})
        with mock.patch.object(lib, "cloud_enabled", return_value=True), mock.patch("suite_account.load_saved_item_state", return_value=None):
            self.assertIsNone(lib.cloud_song_state("abc"))
        with mock.patch.object(lib, "cloud_enabled", return_value=True), mock.patch("suite_account.load_saved_item_state", side_effect=RuntimeError("x")):
            self.assertIsNone(lib.cloud_song_state("abc"))
        with mock.patch.object(lib, "cloud_enabled", return_value=False):
            self.assertIsNone(lib.cloud_song_state("abc"))


class TestDeletedSongIsNeverRevivedBySaving(unittest.TestCase):
    def test_a_draft_without_a_version_cannot_revive_a_deleted_cloud_song(self) -> None:
        _a, _b, store, golden, _ss = _world()
        phantom = L.load_saved_progression(store, "SYN Trial")
        phantom.pop("base_updated_at", None)  # e.g. an active draft restored from an old workspace blob
        with mock.patch("custom_song_library.cloud_song_state", return_value={"valid": False, "version": 0.0}):
            with self.assertRaises(L.SongSaveConflict):
                L.save_progression_named(store, "SYN Trial", phantom)
        self.assertEqual(_canon(store), _canon(golden))

    def test_a_brand_new_song_with_no_cloud_row_still_saves(self) -> None:
        _a, _b, store, _golden, _ss = _world()
        fresh = _song("SYN Fresh", "C", ["C", "G"])
        with mock.patch("custom_song_library.cloud_song_state", return_value=None):
            L.save_progression_named(store, "SYN Fresh", fresh)
        self.assertIn("SYN Fresh", store)


class TestOfflineSaveKeepsTheOldCloudBase(unittest.TestCase):
    """A save made while the cloud is unreachable looks newer by the clock but is derived from OLD content. Its
    cloud base must stay old, so a later reconnect cannot overwrite a newer cloud copy it never saw."""

    def test_cloud_hydration_marks_a_record_as_in_sync_at_its_own_version(self) -> None:
        import custom_song_library as lib

        rec = _song("SYN Trial", "D", ["D"], bpm=100)
        rec["updated_at"] = 500.0
        merged = lib._merge_progression_store({}, [{"payload": {"progression": rec}, "title": "SYN Trial"}])
        self.assertEqual(merged["SYN Trial"]["cloud_base_updated_at"], 500.0)

    def test_the_session_only_marker_is_never_sent_to_the_cloud(self) -> None:
        import custom_song_library as lib

        sent = {}
        rec = _song("SYN Trial", "D", ["D"])
        rec["cloud_base_updated_at"] = 5.0
        with mock.patch.object(lib, "cloud_enabled", return_value=True), mock.patch.object(
            lib, "cloud_storage_status", return_value={"durable": True, "state": "durable"}
        ), mock.patch.object(lib, "active_workspace_id", return_value="daniel"), mock.patch(
            "suite_account.remember_saved_item", side_effect=lambda *a, **k: sent.update(k) or {"write_mode": "upsert"}
        ):
            ok, _key, _err = lib.upsert_custom_song_to_cloud("SYN Trial", rec)
        self.assertTrue(ok)
        self.assertNotIn("cloud_base_updated_at", sent["payload"]["progression"])

    def test_a_failed_cloud_write_keeps_the_old_base_and_a_good_one_advances_it(self) -> None:
        _a, _b, store, _golden, _ss = _world()
        store["SYN Trial"]["cloud_base_updated_at"] = 2.0
        draft = L.load_saved_progression(store, "SYN Trial")
        draft["bpm"] = 70
        with mock.patch("custom_song_library.upsert_custom_song_to_cloud", return_value=(False, "", "offline")):
            L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(store["SYN Trial"]["cloud_base_updated_at"], 2.0)
        draft = L.load_saved_progression(store, "SYN Trial")
        draft["bpm"] = 71
        with mock.patch("custom_song_library.upsert_custom_song_to_cloud", return_value=(True, "k", None)):
            L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])
        self.assertEqual(store["SYN Trial"]["cloud_base_updated_at"], store["SYN Trial"]["updated_at"])

    def test_the_cloud_guard_uses_the_cloud_base_not_the_clock(self) -> None:
        _a, _b, store, golden, _ss = _world()
        store["SYN Trial"]["cloud_base_updated_at"] = 2.0
        store["SYN Trial"]["updated_at"] = 9999.0  # saved offline: looks newer than anything in the cloud
        draft = L.load_saved_progression(store, "SYN Trial")
        with mock.patch("custom_song_library.cloud_song_state", return_value={"valid": True, "version": 300.0}):
            with self.assertRaises(L.SongSaveConflict):
                L.save_progression_named(store, "SYN Trial", draft, expected_updated_at=draft["base_updated_at"])


class TestRefusedSaveIsSaidPlainlyThroughTheRealCallback(unittest.TestCase):
    """The Save button's callback: a protective refusal must show a clear warning and change NOTHING."""

    def _run_callback(self, ss):
        import streamlit

        with mock.patch.object(streamlit, "session_state", ss), mock.patch(
            "songs.music_source.clear_cpl_intentional_new_song", lambda *_a, **_k: None
        ):
            L.cpl_on_save_library_callback()

    def _session(self):
        _a, _b, store, golden, ss = _world()
        L.apply_cpl_session_progression(ss, L.load_saved_progression(store, "SYN Trial"), reset_display_key=True)
        return store, golden, ss

    def test_a_stale_cloud_conflict_shows_a_plain_warning_and_changes_nothing(self) -> None:
        store, golden, ss = self._session()
        ss["cpl_bpm_builder"] = 55  # the user edited something, then pressed Save
        with mock.patch("custom_song_library.cloud_song_state", return_value={"valid": True, "version": 10_000_000_000.0}), mock.patch(
            "custom_song_library.upsert_custom_song_to_cloud"
        ) as upload:
            self._run_callback(ss)
        flash = ss.get("_cpl_save_library_flash")
        self.assertTrue(str(flash).startswith(L.SAVE_REFUSED_FLASH_PREFIX), flash)
        self.assertIn("Nothing was sent to the cloud", str(flash))
        self.assertNotIn("SongSaveConflict(", str(flash))
        upload.assert_not_called()
        self.assertEqual(_canon(store), _canon(golden))  # the saved song is untouched

    def test_a_deleted_elsewhere_song_shows_a_plain_warning(self) -> None:
        store, golden, ss = self._session()
        with mock.patch("custom_song_library.cloud_song_state", return_value={"valid": False, "version": 0.0}), mock.patch(
            "custom_song_library.upsert_custom_song_to_cloud"
        ) as upload:
            self._run_callback(ss)
        self.assertIn("deleted elsewhere", str(ss.get("_cpl_save_library_flash")))
        upload.assert_not_called()
        self.assertEqual(_canon(store), _canon(golden))

    def test_an_ordinary_save_still_reports_success(self) -> None:
        store, _golden, ss = self._session()
        ss["cpl_bpm_builder"] = 66
        with mock.patch("custom_song_library.cloud_song_state", return_value=None), mock.patch(
            "custom_song_library.upsert_custom_song_to_cloud", return_value=(True, "k", None)
        ):
            self._run_callback(ss)
        self.assertIs(ss.get("_cpl_save_library_flash"), True)
        self.assertEqual(store["SYN Trial"]["bpm"], 66)


if __name__ == "__main__":
    unittest.main()
