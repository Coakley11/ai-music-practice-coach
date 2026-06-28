"""Refresh persistence regression — practice log must survive session clear + reload."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from music_ami_context import gather_practice_ami_snapshot
from practice_log_ami import build_practice_log_ami_payload
from practice_log_state import add_practice_log_entry, load_entries


class TestPracticeLogRefreshPersistence(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._ws = "daniel"
        self._path = Path(self._tmpdir.name) / "workspaces" / self._ws / "practice_history.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

        def _fake_local_path(*, st=None):
            return self._path

        def _fake_resolve(*, st=None):
            return self._ws

        self._patches = [
            patch("practice_log_persistence._local_path", _fake_local_path),
            patch("practice_log_persistence._resolve_workspace_id", _fake_resolve),
            patch("practice_log_persistence._load_cloud_logs", lambda *, st=None: ([], None)),
            patch("studio_history_cloud.cloud_enabled", return_value=False),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()
        self._tmpdir.cleanup()

    def test_entry_survives_session_clear_and_reload(self) -> None:
        session: dict = {"_suite_active_workspace_id": self._ws, "studio_page": "log"}
        entry = add_practice_log_entry(
            session,
            {
                "active_song": "Autumn Leaves",
                "duration_minutes": 25,
                "instrument": "Tenor Sax",
                "notes": "Bridge timing",
                "what_was_hard": "rush at bar 8",
                "next_step": "loop bridge slowly",
            },
        )
        sid = str(entry.get("session_id") or "")
        self.assertTrue(sid)
        self.assertTrue(self._path.exists())
        on_disk = json.loads(self._path.read_text(encoding="utf-8"))
        self.assertTrue(any(str(row.get("session_id") or "") == sid for row in on_disk))

        trace = list(session.get("_practice_log_persist_trace") or [])
        save_trace = next((row for row in trace if row.get("phase") == "save"), {})
        self.assertTrue(save_trace.get("local_ok"))
        self.assertGreaterEqual(int(save_trace.get("local_write_count") or 0), 1)

        saved_session_id = sid
        session.clear()
        session["_suite_active_workspace_id"] = self._ws

        reloaded = load_entries(session)
        load_trace = next(
            (row for row in (session.get("_practice_log_persist_trace") or []) if row.get("phase") == "load"),
            {},
        )
        self.assertGreaterEqual(int(load_trace.get("visible_count") or 0), 1)
        self.assertTrue(any(str(row.get("session_id") or "") == saved_session_id for row in reloaded))

    def test_ami_payload_non_empty_after_reload(self) -> None:
        session: dict = {"_suite_active_workspace_id": self._ws, "studio_page": "log"}
        add_practice_log_entry(
            session,
            {"active_song": "Blue Bossa", "duration_minutes": 20, "instrument": "Piano"},
        )
        sid = session.get("_practice_log_last_save_workspace")
        session.clear()
        session["_suite_active_workspace_id"] = self._ws
        session["selected_song"] = {"title": "Blue Bossa", "pick_key": "jazz:blue"}

        entries = load_entries(session)
        payload = build_practice_log_ami_payload(session, entries=entries, window_days=14)
        snap = gather_practice_ami_snapshot(session)

        self.assertTrue(payload.get("recent_sessions"))
        self.assertIn("practice_log_summary", payload)
        self.assertTrue(snap.get("recent_practice_history"))
        self.assertIn("practice_log_ami_payload", snap)
        self.assertIsNotNone(sid)

    def test_workspace_change_reloads_from_new_path(self) -> None:
        guest_path = Path(self._tmpdir.name) / "workspaces" / "guest" / "practice_history.json"
        daniel_path = self._path
        paths = {"guest": guest_path, "daniel": daniel_path}

        def _fake_local_path(*, st=None):
            ws = "daniel"
            if st is not None and hasattr(st, "session_state"):
                ss = st.session_state
                if isinstance(ss, dict):
                    ws = str(ss.get("_suite_active_workspace_id") or "daniel")
            return paths.get(ws, daniel_path)

        def _fake_resolve(*, st=None):
            if st is not None and hasattr(st, "session_state"):
                ss = st.session_state
                if isinstance(ss, dict):
                    return str(ss.get("_suite_active_workspace_id") or "daniel")
            return "daniel"

        with patch("practice_log_persistence._local_path", _fake_local_path):
            with patch("practice_log_persistence._resolve_workspace_id", _fake_resolve):
                session: dict = {
                    "_suite_active_workspace_id": "daniel",
                    "_suite_workspace_initialized": True,
                    "studio_page": "log",
                }
                entry = add_practice_log_entry(
                    session,
                    {"active_song": "Workspace Song", "duration_minutes": 12, "instrument": "Guitar"},
                )
                sid = str(entry.get("session_id") or "")
                self.assertTrue(sid)
                self.assertTrue(daniel_path.is_file())

                session["_suite_active_workspace_id"] = "guest"
                empty = load_entries(session, force=True)
                self.assertFalse(any(str(row.get("session_id") or "") == sid for row in empty))

                session["_suite_active_workspace_id"] = "daniel"
                restored = load_entries(session, force=True)
                self.assertTrue(any(str(row.get("session_id") or "") == sid for row in restored))

    def test_deferred_load_when_workspace_becomes_ready(self) -> None:
        session: dict = {"studio_page": "log"}
        first = load_entries(session)
        self.assertEqual(first, [])
        self.assertTrue(session.get("_practice_log_deferred_empty_load"))

        session["_suite_active_workspace_id"] = self._ws
        session["_suite_workspace_initialized"] = True
        add_practice_log_entry(
            session,
            {"active_song": "Deferred WS", "duration_minutes": 18, "instrument": "Flute"},
        )
        session.clear()
        session["_suite_active_workspace_id"] = self._ws
        session["_suite_workspace_initialized"] = True

        reloaded = load_entries(session)
        self.assertGreaterEqual(len(reloaded), 1)
        self.assertFalse(session.get("_practice_log_deferred_empty_load"))


if __name__ == "__main__":
    unittest.main()
