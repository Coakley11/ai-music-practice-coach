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
    cpl_apply_pending_chord_to_section,
    cpl_page_end_save_should_preserve_sections,
    cpl_save_draft,
    cpl_section_progression_view,
    cpl_whole_song_progression_view,
    default_active_progression,
    ensure_all_cpl_sections,
    filled_section_names,
    migrate_cpl_builder_version,
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
        active = cpl_active_from_session(session)
        active = cpl_apply_pending_chord_to_section(
            active,
            section_name="Verse",
            pending_chord="C",
            bars=4,
        )
        session[CPL_ACTIVE_KEY] = active
        view = cpl_section_progression_view(active, section_name="Verse", preview_key="C")
        self.assertEqual(view["native_rows"], [("C", 4)])
        self.assertTrue(view["show_panel"])

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
        active = cpl_active_from_session(session)
        active = cpl_apply_pending_chord_to_section(active, section_name="Verse", pending_chord="C", bars=2)
        active = cpl_apply_pending_chord_to_section(active, section_name="Verse", pending_chord="G", bars=2)
        home = ensure_all_cpl_sections(active["original_sections"])
        home["Verse"].pop()
        active = cpl_save_draft(session, active, home, persist=False)
        view = cpl_section_progression_view(active, section_name="Verse", preview_key="C")
        self.assertEqual(view["native_rows"], [("C", 2)])

    def test_clear_section_flow(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        active = cpl_apply_pending_chord_to_section(active, section_name="Verse", pending_chord="C", bars=4)
        home = ensure_all_cpl_sections(active["original_sections"])
        home["Verse"] = []
        active = cpl_save_draft(session, active, home, persist=False)
        view = cpl_section_progression_view(active, section_name="Verse", preview_key="C")
        self.assertFalse(view["has_chords"])
        self.assertFalse(filled_section_names(home))

    def test_finish_enabled_only_when_progression_exists(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        home = ensure_all_cpl_sections(active["original_sections"])
        self.assertFalse(filled_section_names(home))
        active = cpl_apply_pending_chord_to_section(active, section_name="Verse", pending_chord="C", bars=4)
        home = ensure_all_cpl_sections(active["original_sections"])
        self.assertTrue(filled_section_names(home))

    def test_metadata_widgets_sync_into_draft(self) -> None:
        session = self._session_with_draft()
        session.update({
            "cpl_title_input": "My Ballad",
            "cpl_artist_input": "Daniel",
            "cpl_style_early": "Soul/R&B",
            "cpl_time_signature": "3/4",
            "cpl_bpm_builder": 88,
        })
        active = sync_cpl_draft_widgets_to_active(session, cpl_active_from_session(session))
        self.assertEqual(active["name"], "My Ballad")
        self.assertEqual(active["artist"], "Daniel")
        self.assertEqual(active["progression_style"], "Soul/R&B")
        self.assertEqual(active["time_signature"], "3/4")
        self.assertEqual(active["bpm"], 88)

    def test_seed_widgets_from_active_for_cross_device_restore(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        active["name"] = "Cloud Song"
        active["artist"] = "Phone User"
        active["bpm"] = 92
        active["progression_style"] = "Jazz"
        active["time_signature"] = "6/8"
        session[CPL_ACTIVE_KEY] = active
        seed_cpl_draft_widgets_from_active(session, active)
        self.assertEqual(session["cpl_title_input"], "Cloud Song")
        self.assertEqual(session["cpl_artist_input"], "Phone User")
        self.assertEqual(session["cpl_bpm_builder"], 92)
        self.assertEqual(session["cpl_style_early"], "Jazz")
        self.assertEqual(session["cpl_time_signature"], "6/8")

    def test_save_draft_persists_to_cloud(self) -> None:
        session = self._session_with_draft()
        active = cpl_active_from_session(session)
        active = cpl_apply_pending_chord_to_section(active, section_name="Verse", pending_chord="C", bars=4)
        st = SimpleNamespace(session_state=session)
        with patch("custom_progression_lab.persist_cpl_draft_state") as persist:
            cpl_save_draft(session, active, persist=True, st=st)
            persist.assert_called_once_with(st)

    def test_page_end_save_does_not_drop_new_chords(self) -> None:
        session = self._session_with_draft()
        stale = ensure_all_cpl_sections(cpl_active_from_session(session)["original_sections"])
        active = cpl_apply_pending_chord_to_section(
            cpl_active_from_session(session),
            section_name="Verse",
            pending_chord="C",
            bars=4,
        )
        session[CPL_ACTIVE_KEY] = active
        self.assertTrue(
            cpl_page_end_save_should_preserve_sections(session, sections_snapshot=stale)
        )

    def test_builder_version_migration_preserves_existing_draft(self) -> None:
        session = self._session_with_draft()
        active = cpl_apply_pending_chord_to_section(
            cpl_active_from_session(session),
            section_name="Verse",
            pending_chord="Am",
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
        active = cpl_apply_pending_chord_to_section(
            cpl_active_from_session(session),
            section_name="Verse",
            pending_chord="C",
            bars=4,
        )
        active = cpl_apply_pending_chord_to_section(
            active,
            section_name="Chorus",
            pending_chord="G",
            bars=4,
        )
        session[CPL_ACTIVE_KEY] = active
        payload = copy.deepcopy(session[CPL_ACTIVE_KEY])
        other = {CPL_ACTIVE_KEY: payload}
        whole = cpl_whole_song_progression_view(cpl_active_from_session(other), "C")
        self.assertTrue(whole["has_any"])
        self.assertEqual(len(whole["sections"]), 2)


if __name__ == "__main__":
    unittest.main()
