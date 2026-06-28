"""Media catalog diagnostics (?dev=1)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_diagnostics import collect_media_catalog_stats
from media_persistence import add_uploaded_recording, load_media_catalog


class TestMediaDiagnostics(unittest.TestCase):
    def test_collect_stats_after_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_diagnostics._local_path", _fake_path):
                    with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                        with patch("media_diagnostics._resolve_workspace_id", lambda *, st=None: "daniel"):
                            with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                                with patch("media_diagnostics._load_cloud_catalog", lambda *, st=None: ({}, None)):
                                    with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                                        add_uploaded_recording(
                                            None,
                                            {
                                                "filename": "diag.wav",
                                                "song": "Say",
                                                "instrument": "Tenor Saxophone",
                                            },
                                        )
                                        stats = collect_media_catalog_stats(st=None)
                                        self.assertEqual(stats.get("visible_upload_count"), 1)
                                        self.assertEqual(stats.get("workspace_id"), "daniel")
                                        self.assertTrue(stats.get("deleted_hidden"))
                                        self.assertEqual(stats.get("last_upload_song"), "Say")

    def test_stats_survive_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_diagnostics._local_path", _fake_path):
                    with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                        with patch("media_diagnostics._resolve_workspace_id", lambda *, st=None: "daniel"):
                            with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                                with patch("media_diagnostics._load_cloud_catalog", lambda *, st=None: ({}, None)):
                                    with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                                        add_uploaded_recording(None, {"filename": "persist.wav", "song": "Autumn"})
                                        stats1 = collect_media_catalog_stats(st=None)
                                        catalog = load_media_catalog(st=None)
                                        stats2 = collect_media_catalog_stats(st=None)
                                        self.assertEqual(stats1.get("visible_upload_count"), 1)
                                        self.assertEqual(stats2.get("visible_upload_count"), 1)
                                        self.assertTrue(path.exists())
                                        self.assertEqual(
                                            len(catalog.get("uploaded_recordings") or []),
                                            1,
                                        )
