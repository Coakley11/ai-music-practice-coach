"""Upload Analysis history UI and save/update behavior."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_upload_catalog import (
    active_catalog_recording_id,
    build_upload_recording_fields,
    save_upload_recording_with_notes,
)
from studio_history_ui import upload_recording_detail_lines
from upload_analysis_modes import (
    MULTITRACK_RECORDING,
    MULTITRACK_RECORDING_LEGACY,
    WORKFLOW_OPTIONS,
    is_multitrack_workflow,
    normalize_analysis_workflow,
)


class TestUploadAnalysisHistoryUi(unittest.TestCase):
    def test_detail_lines_show_song_before_notes(self) -> None:
        row = {
            "title": "say export1.wav",
            "updated_at": "2026-06-28T12:00:00+00:00",
            "payload": {
                "song": "Say",
                "notes": "Forest park rehearsal",
                "legacy_recording_type": "Multitrack mix",
                "source": "multitrack_export",
                "saved_at": "2026-06-28T12:00:00+00:00",
            },
        }
        lines = upload_recording_detail_lines(row)
        self.assertGreaterEqual(len(lines), 2)
        self.assertIn("Song / Title", lines[0])
        self.assertIn("Notes", lines[1])
        joined = "\n".join(lines)
        self.assertNotIn("Instrument", joined)

    def test_build_fields_do_not_copy_global_instrument(self) -> None:
        fields = build_upload_recording_fields(
            {
                "last_analysis_result": {"ok": True, "coach_summary": "Good take"},
                "instrument": "Alto Saxophone",
                "active_song_title": "Say",
            }
        )
        self.assertIsNotNone(fields)
        assert fields is not None
        self.assertEqual(fields.get("instrument"), "")
        self.assertEqual(fields.get("instrument_family"), "")

    def test_update_loaded_analysis_reuses_recording_id(self) -> None:
        session = {
            "last_analysis_result": {"ok": True, "coach_summary": "Take one"},
            "upload_catalog_active_recording_id": "rec-existing",
            "analysis_recording_type": "Practice take",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"
            path.write_text(
                json.dumps(
                    {
                        "uploaded_recordings": [
                            {
                                "recording_id": "rec-existing",
                                "filename": "Old title",
                                "song": "Old title",
                                "analysis_summary": {"ok": True},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def _fake_path(*, st=None):
                return path

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
                                        title="Updated title",
                                        notes="Updated notes",
                                        st=None,
                                        save_mode="update",
                                    )
            self.assertTrue(ok)
            self.assertEqual(rid, "rec-existing")
            catalog = json.loads(path.read_text(encoding="utf-8"))
            rows = catalog.get("uploaded_recordings") or []
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("recording_id"), "rec-existing")
            self.assertEqual(rows[0].get("song"), "Updated title")
            self.assertEqual(rows[0].get("notes"), "Updated notes")

    def test_save_as_new_copy_creates_second_record(self) -> None:
        session = {
            "last_analysis_result": {"ok": True, "coach_summary": "Take one"},
            "upload_catalog_active_recording_id": "rec-existing",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"
            path.write_text(
                json.dumps(
                    {
                        "uploaded_recordings": [
                            {
                                "recording_id": "rec-existing",
                                "filename": "Original",
                                "analysis_summary": {"ok": True},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def _fake_path(*, st=None):
                return path

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
                                        title="Copy title",
                                        notes="Copy notes",
                                        st=None,
                                        save_mode="new",
                                    )
            self.assertTrue(ok)
            self.assertNotEqual(rid, "rec-existing")
            catalog = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(catalog.get("uploaded_recordings") or []), 2)

    def test_workflow_label_multitrack_recording(self) -> None:
        self.assertIn(MULTITRACK_RECORDING, WORKFLOW_OPTIONS)
        self.assertNotIn(MULTITRACK_RECORDING_LEGACY, WORKFLOW_OPTIONS)
        root = Path(__file__).resolve().parents[1]
        app_source = (root / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        modes_source = (root / "upload_analysis_modes.py").read_text(encoding="utf-8")
        self.assertIn("upload_analysis_modes", app_source)
        self.assertIn("WORKFLOW_OPTIONS", app_source)
        self.assertIn("Multitrack recording", modes_source)
        self.assertNotIn("Multitrack comparison", app_source)

    def test_legacy_workflow_value_maps_forward(self) -> None:
        session = {"analysis_mode": MULTITRACK_RECORDING_LEGACY}
        normalize_analysis_workflow(session)
        self.assertEqual(session["analysis_mode"], MULTITRACK_RECORDING)
        self.assertTrue(is_multitrack_workflow(session))

    def test_upload_history_ui_save_changes_wiring(self) -> None:
        ui_source = (
            Path(__file__).resolve().parents[1] / "studio_history_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Save Changes", ui_source)
        self.assertIn("Save as New Copy", ui_source)
        self.assertIn("Update saved analysis", ui_source)
        self.assertNotIn("Instrument", ui_source)

    def test_active_catalog_recording_id_prefers_loaded_marker(self) -> None:
        session = {
            "upload_catalog_active_recording_id": "rec-1",
            "upload_hist_active_item": "rec-1",
        }
        self.assertEqual(active_catalog_recording_id(session), "rec-1")


if __name__ == "__main__":
    unittest.main()
