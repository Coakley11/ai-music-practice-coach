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


if __name__ == "__main__":
    unittest.main()
