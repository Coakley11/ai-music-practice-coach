"""Multitrack workspace refresh persistence and post-restore editability."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_multitrack_catalog import (
    apply_pending_multitrack_catalog_load,
    load_multitrack_project_from_catalog,
    queue_multitrack_project_catalog_load,
    save_multitrack_session_with_notes,
)
from music_restore_phase import complete_music_restore_phase, mark_page_snapshot_hydrated
from multitrack_slots import MULTITRACK_SLOTS
from studio_page_persistence import (
    capture_page_snapshot,
    flush_current_page_snapshot,
    reset_page_snapshot_tracker,
    restore_current_page_snapshot_if_needed,
)


def _empty_mt_session(**extra) -> dict:
    base = {
        "studio_page": "multitrack",
        "mt_tracks": {slot: None for slot in MULTITRACK_SLOTS},
    }
    base.update(extra)
    return base


class TestMultitrackWorkspaceEditability(unittest.TestCase):
    def test_refresh_restores_bpm_groove_sections(self) -> None:
        snap = capture_page_snapshot(
            {
                "studio_page": "multitrack",
                "multitrack_bpm": 132,
                "mt_groove_style": "Jazz swing",
                "mt_section_loops": 2,
                "mt_playback_scope": "Multiple sections",
                "mt_multi_sections": ["Verse", "Chorus"],
            },
            "multitrack",
        )
        ss = _empty_mt_session(
            _studio_page_snapshots={"multitrack": snap},
            multitrack_bpm=100,
            mt_groove_style="Auto",
        )
        complete_music_restore_phase(ss)
        reset_page_snapshot_tracker(ss)
        restore_current_page_snapshot_if_needed(ss)
        mark_page_snapshot_hydrated(ss, "multitrack")
        self.assertEqual(ss.get("multitrack_bpm"), 132)
        self.assertEqual(ss.get("mt_groove_style"), "Jazz swing")
        self.assertEqual(ss.get("mt_section_loops"), 2)
        self.assertEqual(ss.get("mt_multi_sections"), ["Verse", "Chorus"])

    def test_editability_after_restore_bpm_sticks_on_rerun(self) -> None:
        snap = capture_page_snapshot(
            {"studio_page": "multitrack", "multitrack_bpm": 120},
            "multitrack",
        )
        ss = _empty_mt_session(
            _studio_page_snapshots={"multitrack": snap},
            _studio_active_page_id="multitrack",
        )
        complete_music_restore_phase(ss)
        reset_page_snapshot_tracker(ss)
        restore_current_page_snapshot_if_needed(ss)
        ss["_studio_active_page_id"] = "multitrack"
        self.assertEqual(ss.get("multitrack_bpm"), 120)

        ss["multitrack_bpm"] = 135
        restore_current_page_snapshot_if_needed(ss)
        self.assertEqual(ss.get("multitrack_bpm"), 135)

    def test_flush_then_refresh_restores_latest_edited_values(self) -> None:
        ss = _empty_mt_session(
            multitrack_bpm=132,
            mt_groove_style="Jazz swing",
            mt_section_loops=2,
        )
        flush_current_page_snapshot(ss)
        ss["multitrack_bpm"] = 100
        ss["mt_groove_style"] = "Auto"
        complete_music_restore_phase(ss)
        reset_page_snapshot_tracker(ss)
        restore_current_page_snapshot_if_needed(ss)
        self.assertEqual(ss.get("multitrack_bpm"), 132)
        self.assertEqual(ss.get("mt_groove_style"), "Jazz swing")
        self.assertEqual(ss.get("mt_section_loops"), 2)

    def test_loaded_project_edits_stick_after_hydration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            session = {
                "mt_tracks": {slot: (b"guitar" if slot == "Guitar" else None) for slot in MULTITRACK_SLOTS},
                "mt_track_filenames": {"Guitar": "guitar.wav"},
                "multitrack_bpm": 110,
                "mt_groove_style": "Pop groove",
            }
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            ok, mid, err = save_multitrack_session_with_notes(
                                session,
                                project_name="Project C",
                                notes="Notes C",
                                song_title="Say",
                            )
                            self.assertTrue(ok, err)
                            working = _empty_mt_session(
                                multitrack_bpm=100,
                                mt_groove_style="Auto",
                                mt_history_save_notes="Stale",
                            )
                            queue_multitrack_project_catalog_load(
                                working,
                                mid,
                                clicked_meta={"clicked_project_title": "Project C"},
                            )
                            ok_load, msg = apply_pending_multitrack_catalog_load(working, st=None)
                            self.assertTrue(ok_load, msg)
                            mark_page_snapshot_hydrated(working, "multitrack")
                            complete_music_restore_phase(working)

                            working["multitrack_bpm"] = 135
                            working["mt_groove_style"] = "Rock groove"
                            working["mt_history_save_notes"] = "Edited notes"
                            restore_current_page_snapshot_if_needed(working)
                            self.assertEqual(working.get("multitrack_bpm"), 135)
                            self.assertEqual(working.get("mt_groove_style"), "Rock groove")
                            self.assertEqual(working.get("mt_history_save_notes"), "Edited notes")

    def test_active_song_defaults_do_not_overwrite_after_hydration(self) -> None:
        snap = capture_page_snapshot(
            {
                "studio_page": "multitrack",
                "multitrack_bpm": 128,
                "mt_time_signature": "3/4",
                "multitrack_catalog_active_id": "proj-loaded",
            },
            "multitrack",
        )
        ss = _empty_mt_session(
            _studio_page_snapshots={"multitrack": snap},
            bpm=90,
        )
        complete_music_restore_phase(ss)
        reset_page_snapshot_tracker(ss)
        restore_current_page_snapshot_if_needed(ss)
        mark_page_snapshot_hydrated(ss, "multitrack")
        self.assertEqual(ss.get("multitrack_bpm"), 128)
        self.assertEqual(ss.get("mt_time_signature"), "3/4")
        self.assertEqual(ss.get("multitrack_catalog_active_id"), "proj-loaded")

        restore_current_page_snapshot_if_needed(ss)
        self.assertEqual(ss.get("multitrack_bpm"), 128)
        self.assertEqual(ss.get("mt_time_signature"), "3/4")

    def test_selected_sections_backing_uses_song_order_only(self) -> None:
        from streamlit_music_practice_app import chord_events_for_selected_sections

        sections = {
            "Intro": ["C"],
            "Verse": ["Am", "Dm"],
            "Chorus": ["G", "Em"],
            "Bridge": ["F"],
        }
        events = chord_events_for_selected_sections(sections, ["Verse", "Chorus"])
        section_names = [ev["section"] for ev in events]
        self.assertEqual(section_names, ["Verse", "Verse", "Chorus", "Chorus"])
        self.assertNotIn("Intro", section_names)
        self.assertNotIn("Bridge", section_names)


if __name__ == "__main__":
    unittest.main()
