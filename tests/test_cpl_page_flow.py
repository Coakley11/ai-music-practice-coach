"""Custom Progression Lab — page-flow and draft persistence pipeline."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    CPL_BUILDER_VERSION,
    cpl_active_from_session,
    cpl_apply_chord_with_bars_to_session,
    cpl_apply_pending_chord_to_section,
    cpl_apply_chord_with_bars_to_session,
    cpl_draft_chord_count,
    cpl_draft_written_key,
    cpl_page_end_save_should_preserve_sections,
    cpl_save_draft,
    cpl_section_progression_view,
    cpl_set_pending_chord,
    cpl_whole_song_progression_view,
    default_active_progression,
    ensure_all_cpl_sections,
    ensure_cpl_widget_keys_initialized,
    filled_section_names,
    migrate_cpl_builder_version,
    persist_cpl_draft_state,
    reset_cpl_widget_initialization,
    seed_cpl_draft_widgets_from_active,
    sync_cpl_draft_widgets_to_active,
)


class TestCplPageFlow(unittest.TestCase):
    def _session_with_draft(self) -> dict:
        active = default_active_progression()
        active["name"] = "My Progression"
        active["artist"] = "Daniel"
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        active["progression_style"] = "Pop"
        active["time_signature"] = "4/4"
        active["bpm"] = 100
        return {
            CPL_ACTIVE_KEY: active,
            "cpl_builder_version": CPL_BUILDER_VERSION,
            "cpl_edit_section": "Verse",
        }

    def test_add_chord_and_bars_updates_section_and_display(self) -> None:
        session = self._session_with_draft()
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
        )
        view = cpl_section_progression_view(active, section_name="Verse", preview_key="C")
        self.assertEqual(view["native_rows"], [("C", 4)])
        self.assertTrue(view["show_panel"])

    def test_first_chord_save_does_not_auto_infer_written_key(self) -> None:
        session = self._session_with_draft()
        session[CPL_ACTIVE_KEY]["user_locked_home_key"] = False
        session[CPL_ACTIVE_KEY]["original_key_center"] = "C"
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
        )
        self.assertEqual(cpl_draft_written_key(active), "C")

    def test_multiple_sections_whole_song_display(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        home = ensure_all_cpl_sections(active["original_sections"])
        home["Verse"] = [{"chord": "C", "bars": 4}, {"chord": "Am", "bars": 4}]
        home["Chorus"] = [{"chord": "F", "bars": 4}, {"chord": "G", "bars": 4}]
        active = cpl_save_draft(session, active, home, persist=False)
        whole = cpl_whole_song_progression_view(active, "C")
        self.assertTrue(whole["has_any"])
        self.assertEqual(len(whole["sections"]), 2)
        self.assertIn("C — 4 bars", whole["sections"][0]["line"])
        self.assertIn("F — 4 bars", whole["sections"][1]["line"])

    def test_undo_last_chord_flow(self) -> None:
        session = self._session_with_draft()
        active = cpl_apply_pending_chord_to_section(
            cpl_active_from_session(session),
            section_name="Verse",
            pending_chord="C",
            bars=2,
        )
        active = cpl_apply_pending_chord_to_section(
            active,
            section_name="Verse",
            pending_chord="G",
            bars=2,
        )
        home = ensure_all_cpl_sections(active["original_sections"])
        home["Verse"].pop()
        active = cpl_save_draft(session, active, home, persist=False)
        view = cpl_section_progression_view(active, section_name="Verse", preview_key="C")
        self.assertEqual(view["native_rows"], [("C", 2)])

    def test_clear_section_flow(self) -> None:
        from custom_progression_lab import cpl_clear_current_section

        session = self._session_with_draft()
        session["cpl_edit_section"] = "Verse"
        cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
        )
        cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Chorus",
            chord="G",
            bars=4,
        )
        active = cpl_clear_current_section(session, section_name="Verse")
        view = cpl_section_progression_view(active, section_name="Verse", preview_key="C")
        self.assertFalse(view["has_chords"])
        chorus = cpl_section_progression_view(active, section_name="Chorus", preview_key="C")
        self.assertEqual(chorus["native_rows"], [("G", 4)])

    def test_finish_enabled_only_when_progression_exists(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        home = ensure_all_cpl_sections(active["original_sections"])
        self.assertFalse(filled_section_names(home))
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
        )
        home = ensure_all_cpl_sections(active["original_sections"])
        self.assertTrue(filled_section_names(home))

    def test_metadata_widgets_sync_into_draft(self) -> None:
        session = self._session_with_draft()
        session.update({
            "cpl_title_input": "Test Song",
            "cpl_artist_input": "Daniel",
            "cpl_style_early": "Soul/R&B",
            "cpl_time_signature": "3/4",
            "cpl_bpm_builder": 100,
            "cpl_original_key": "G",
        })
        active = sync_cpl_draft_widgets_to_active(session, cpl_active_from_session(session))
        self.assertEqual(active["name"], "Test Song")
        self.assertEqual(active["artist"], "Daniel")
        self.assertEqual(active["progression_style"], "Soul/R&B")
        self.assertEqual(active["time_signature"], "3/4")
        self.assertEqual(active["bpm"], 100)
        self.assertEqual(cpl_draft_written_key(active), "G")

    def test_seed_widgets_from_active_for_cross_device_restore(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        active["name"] = "Cloud Song"
        active["artist"] = "Phone User"
        active["bpm"] = 92
        active["progression_style"] = "Jazz"
        active["time_signature"] = "6/8"
        active["original_key_center"] = "D"
        session[CPL_ACTIVE_KEY] = active
        seed_cpl_draft_widgets_from_active(session, active, force=True)
        self.assertEqual(session["cpl_title_input"], "Cloud Song")
        self.assertEqual(session["cpl_artist_input"], "Phone User")
        self.assertEqual(session["cpl_bpm_builder"], 92)
        self.assertEqual(session["cpl_style_early"], "Jazz")
        self.assertEqual(session["cpl_time_signature"], "6/8")
        self.assertEqual(session["cpl_original_key"], "D")

    def test_save_draft_persists_to_cloud(self) -> None:
        session = self._session_with_draft()
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
        )
        st = SimpleNamespace(session_state=session)
        with patch("custom_progression_lab.persist_cpl_draft_state") as persist:
            cpl_save_draft(session, active, persist=True, st=st)
            persist.assert_called_once_with(st)

    def test_page_end_save_does_not_drop_new_chords(self) -> None:
        session = self._session_with_draft()
        stale = ensure_all_cpl_sections(cpl_active_from_session(session)["original_sections"])
        cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
        )
        self.assertTrue(
            cpl_page_end_save_should_preserve_sections(session, sections_snapshot=stale)
        )

    def test_builder_version_migration_preserves_existing_draft(self) -> None:
        session = self._session_with_draft()
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="Am",
            bars=2,
        )
        session[CPL_ACTIVE_KEY] = active
        session["cpl_builder_version"] = CPL_BUILDER_VERSION - 1
        migrate_cpl_builder_version(session)
        restored = cpl_active_from_session(session)
        view = cpl_section_progression_view(restored, section_name="Verse", preview_key="C")
        self.assertEqual(view["native_rows"], [("Am", 2)])
        self.assertEqual(session["cpl_builder_version"], CPL_BUILDER_VERSION)

    def test_cloud_payload_roundtrip_keeps_sections(self) -> None:
        session = self._session_with_draft()
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
        )
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Chorus",
            chord="G",
            bars=4,
        )
        payload = copy.deepcopy(session[CPL_ACTIVE_KEY])
        other = {CPL_ACTIVE_KEY: payload}
        whole = cpl_whole_song_progression_view(cpl_active_from_session(other), "C")
        self.assertTrue(whole["has_any"])
        self.assertEqual(len(whole["sections"]), 2)

    def test_full_example_flow_metadata_and_chords(self) -> None:
        session = self._session_with_draft()
        session.update({
            "cpl_title_input": "Test Song",
            "cpl_artist_input": "Daniel",
            "cpl_style_early": "Pop",
            "cpl_time_signature": "3/4",
            "cpl_bpm_builder": 100,
            "cpl_original_key": "C",
        })
        active = sync_cpl_draft_widgets_to_active(session, cpl_active_from_session(session))
        active = cpl_save_draft(session, active, persist=False)
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
        )
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="Am",
            bars=4,
        )
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Chorus",
            chord="F",
            bars=4,
        )
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Chorus",
            chord="G",
            bars=4,
        )
        active = sync_cpl_draft_widgets_to_active(session, active)
        active = cpl_save_draft(session, active, persist=False)
        self.assertEqual(active["name"], "Test Song")
        self.assertEqual(active["time_signature"], "3/4")
        section = cpl_section_progression_view(active, section_name="Verse", preview_key="C")
        whole = cpl_whole_song_progression_view(active, "C")
        self.assertEqual(len(section["native_rows"]), 2)
        self.assertEqual(len(whole["sections"]), 2)

    def test_widget_init_seeds_once_and_preserves_user_edits(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        ensure_cpl_widget_keys_initialized(session, active)
        session["cpl_bpm_builder"] = 120
        session["cpl_artist_input"] = "Edited Artist"
        ensure_cpl_widget_keys_initialized(session, active)
        self.assertEqual(session["cpl_bpm_builder"], 120)
        self.assertEqual(session["cpl_artist_input"], "Edited Artist")

    def test_widget_reset_allows_reseed_from_active(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        ensure_cpl_widget_keys_initialized(session, active)
        session["cpl_bpm_builder"] = 120
        active["bpm"] = 88
        session[CPL_ACTIVE_KEY] = active
        reset_cpl_widget_initialization(session)
        ensure_cpl_widget_keys_initialized(session, active, force=True)
        self.assertEqual(session["cpl_bpm_builder"], 88)

    def test_widget_init_respects_cloud_restored_widget_values(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        active["bpm"] = 80
        active["artist"] = "Stale Artist"
        session[CPL_ACTIVE_KEY] = active
        session["cpl_bpm_builder"] = 120
        session["cpl_artist_input"] = "Cloud Artist"
        synced = ensure_cpl_widget_keys_initialized(session, active, force=False)
        self.assertEqual(session["cpl_bpm_builder"], 120)
        self.assertEqual(session["cpl_artist_input"], "Cloud Artist")
        self.assertEqual(synced["bpm"], 120)
        self.assertEqual(synced["artist"], "Cloud Artist")

    def test_persist_bypasses_post_restore_autosave_block(self) -> None:
        from unittest.mock import patch

        session = self._session_with_draft()
        session.update({
            "cpl_title_input": "Trial Song",
            "cpl_bpm_builder": 100,
            "cpl_time_signature": "3/4",
            "cpl_original_key": "C",
        })
        session["_suite_autosave_blocked::music"] = True
        st = SimpleNamespace(session_state=session)
        with patch(
            "music_persistent_state.flush_active_song_edits_and_save",
            return_value=True,
        ) as flush:
            ok = persist_cpl_draft_state(st)
        flush.assert_called_once_with(st, reason="cpl_draft_edit")
        self.assertTrue(ok)
        self.assertTrue(session.get("_cpl_last_persist_ok"))

    def test_metadata_sync_save_preserves_existing_chords(self) -> None:
        session = self._session_with_draft()
        ensure_cpl_widget_keys_initialized(session, cpl_active_from_session(session))
        cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
            persist=False,
        )
        session.update({
            "cpl_bpm_builder": 100,
            "cpl_time_signature": "3/4",
            "cpl_original_key": "C",
        })
        home_before = ensure_all_cpl_sections(
            cpl_active_from_session(session).get("original_sections")
        )
        active = sync_cpl_draft_widgets_to_active(session, cpl_active_from_session(session))
        active = cpl_save_draft(session, active, home_before, persist=False)
        view = cpl_section_progression_view(active, section_name="Verse", preview_key="C")
        self.assertEqual(view["native_rows"], [("C", 4)])
        self.assertEqual(cpl_draft_chord_count(active), 1)

    def test_pick_chord_then_bars_page_flow(self) -> None:
        session = self._session_with_draft()
        ensure_cpl_widget_keys_initialized(session, cpl_active_from_session(session))
        session["cpl_edit_section"] = "Verse"
        cpl_set_pending_chord(session, section="Verse", chord="C")
        session["cpl_last_bars_Verse"] = 4
        active = cpl_apply_chord_with_bars_to_session(
            session,
            section_name="Verse",
            chord="C",
            bars=4,
            persist=False,
        )
        whole = cpl_whole_song_progression_view(active, "C")
        self.assertTrue(whole["has_any"])
        self.assertEqual(whole["sections"][0]["name"], "Verse")
        self.assertIn("C", whole["sections"][0]["line"])


if __name__ == "__main__":
    unittest.main()
