"""Upload Analysis wiring to media catalog."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_upload_catalog import (
    apply_catalog_recording_to_session,
    build_upload_recording_fields,
    load_upload_recording_from_catalog,
    loaded_upload_recording_banner,
    migrate_legacy_upload_history,
    register_upload_analysis_in_catalog,
    save_upload_recording_with_notes,
)
from media_state import migrate_uploaded_recording, normalize_uploaded_recordings


class TestMediaUploadCatalog(unittest.TestCase):
    def _session(self) -> dict:
        return {
            "last_analysis_result": {
                "ok": True,
                "coach_summary": "Solid groove on Say",
                "scores": {"timing": 7, "tone": 8},
            },
            "last_analysis_source_label": "say_take1.wav",
            "analysis_recording_type": "Practice take",
            "active_song_title": "Say",
            "instrument": "Saxophone",
        }

    def test_build_upload_recording_fields(self) -> None:
        fields = build_upload_recording_fields(self._session())
        self.assertIsNotNone(fields)
        assert fields is not None
        self.assertEqual(fields.get("filename"), "say_take1.wav")
        self.assertEqual(fields.get("song"), "Say")
        self.assertIn("coach_summary", str(fields.get("analysis_summary") or {}))

    def test_register_analysis_in_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_upload_catalog.list_upload_history", return_value=([], None)):
                                row = register_upload_analysis_in_catalog(self._session(), st=None)
                                self.assertTrue(row.get("recording_id"))
                                self.assertTrue(path.exists())

    def test_migrate_legacy_upload_history(self) -> None:
        legacy_rows = [
            {
                "item_key": "upload_20260601_abcd",
                "title": "Legacy take",
                "payload": {
                    "workspace_id": "daniel",
                    "saved_at": "2026-06-01T10:00:00+00:00",
                    "title": "Say take",
                    "source_label": "legacy.wav",
                    "scores_summary": {"coach_summary": "Legacy coach note"},
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            ss: dict = {}
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_upload_catalog.list_upload_history", return_value=(legacy_rows, None)):
                                count = migrate_legacy_upload_history(st=ss)
            self.assertEqual(count, 1)
            self.assertTrue(ss.get("_media_upload_history_migrated"))
            data = json.loads(path.read_text(encoding="utf-8"))
            visible = normalize_uploaded_recordings(data.get("uploaded_recordings") or [])
            self.assertEqual(len(visible), 1)
            self.assertEqual(visible[0].get("legacy_item_key"), "upload_20260601_abcd")

    def test_apply_catalog_recording_to_session(self) -> None:
        rec = migrate_uploaded_recording(
            {
                "recording_id": "rec-1",
                "filename": "take.wav",
                "analysis_summary": {"ok": True, "coach_summary": "Loaded note"},
                "notes": "Gig prep",
            }
        )
        session: dict = {}
        ok, _msg = apply_catalog_recording_to_session(session, rec, st=None)
        self.assertTrue(ok)
        self.assertEqual(session["last_analysis_result"]["coach_summary"], "Loaded note")
        self.assertEqual(session.get("upload_history_loaded_notes"), "Gig prep")
        self.assertEqual(session.get("upload_history_save_notes"), "Gig prep")
        self.assertNotIn("last_analysis_audio", session)

    def test_save_with_notes_updates_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            session = self._session()
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_upload_catalog.list_upload_history", return_value=([], None)):
                                with patch(
                                    "media_upload_catalog._save_legacy_upload_history",
                                    return_value=(True, "legacy-key", ""),
                                ):
                                    ok, rid, _ = save_upload_recording_with_notes(
                                        session,
                                        title="My titled take",
                                        notes="Notes here",
                                        st=None,
                                    )
            self.assertTrue(ok)
            self.assertTrue(rid)
            data = json.loads(path.read_text(encoding="utf-8"))
            visible = normalize_uploaded_recordings(data.get("uploaded_recordings") or [])
            self.assertEqual(visible[0].get("notes"), "Notes here")

    def test_load_upload_from_catalog_restores_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            session = self._session()
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_upload_catalog.list_upload_history", return_value=([], None)):
                                with patch(
                                    "media_upload_catalog._save_legacy_upload_history",
                                    return_value=(True, "legacy-key", ""),
                                ):
                                    ok, rid, _ = save_upload_recording_with_notes(
                                        session,
                                        title="My titled take",
                                        notes="Rehearsal notes",
                                        st=None,
                                    )
                                    self.assertTrue(ok)
                                    fresh: dict = {}
                                    ok2, _ = load_upload_recording_from_catalog(fresh, rid, st=None)
                                    self.assertTrue(ok2)
                                    self.assertEqual(fresh.get("upload_history_save_notes"), "Rehearsal notes")
                                    banner = loaded_upload_recording_banner(fresh, st=None)
                                    self.assertIn("Loaded upload:", banner)
                                    self.assertIn("Rehearsal notes", banner)

    def test_upload_row_summary_does_not_repeat_filename(self) -> None:
        from media_upload_catalog import catalog_upload_row_summary

        row = {
            "title": "2026-05-31-214959714.wav",
            "playback_status": "playable",
            "payload": {
                "filename": "2026-05-31-214959714.wav",
                "song": "Annie's Song",
                "legacy_recording_type": "Practice take",
            },
        }
        summary = catalog_upload_row_summary(row)
        self.assertIn("Annie's Song", summary)
        self.assertIn("Practice take", summary)
        self.assertNotIn("2026-05-31", summary)

    def test_loaded_upload_banner_dedupes_song_and_instrument(self) -> None:
        from media_upload_catalog import loaded_upload_recording_banner

        rec = migrate_uploaded_recording(
            {
                "recording_id": "rec-banner",
                "filename": "2026-05-31-214959714.wav",
                "title": "2026-05-31-214959714.wav",
                "song": "Annie's song",
                "instrument": "Piano",
                "notes": "forest park",
                "playback_status": "playable",
                "analysis_summary": {"ok": True},
            }
        )
        session = {"upload_catalog_active_recording_id": "rec-banner"}
        with patch("media_upload_catalog.load_media_catalog", return_value={"uploaded_recordings": [rec]}):
            banner = loaded_upload_recording_banner(session, st=None)
        self.assertEqual(
            banner,
            "Loaded upload: 2026-05-31-214959714.wav · Annie's song · Playable · notes: forest park",
        )
        self.assertEqual(banner.count("Annie's song"), 1)
        self.assertNotIn("Piano", banner)

    def test_history_row_label_is_non_repetitive(self) -> None:
        from studio_history_ui import _compose_history_row_label

        row = {
            "title": "Project A backing",
            "updated_at": "2026-06-28T12:20:00+00:00",
            "payload": {
                "title": "Project A backing",
                "song": "Say",
                "updated_at": "2026-06-28T12:20:00+00:00",
            },
        }
        label = _compose_history_row_label(
            row,
            "2 playable · backing ready",
            item_type="multitrack_session",
        )
        self.assertEqual(label.count("Project A backing"), 1)
        self.assertIn("Say", label)
        self.assertIn("2 playable", label)
        self.assertIn("updated", label)
        self.assertNotIn("Project A backing · Say · Project A backing", label)


if __name__ == "__main__":
    unittest.main()
