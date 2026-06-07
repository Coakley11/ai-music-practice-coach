"""Import smoke tests — Music cloud persistence must not fail on missing deps."""

from __future__ import annotations

import importlib
import py_compile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CLOUD_PERSISTENCE_MODULES = (
    "activity_time",
    "suite_storage_config",
    "suite_storage_supabase",
    "suite_cloud_state",
    "suite_user_persistence",
    "suite_activity_client",
    "suite_account",
    "music_persistent_state",
    "music_persistence_trace",
    "suite_deploy_probe",
    "music_sidebar_layout",
)

COMPILE_TARGETS = (
    "activity_time.py",
    "suite_storage_supabase.py",
    "suite_cloud_state.py",
    "suite_user_persistence.py",
    "suite_activity_client.py",
    "music_persistent_state.py",
    "music_sidebar_layout.py",
)


class TestMusicImportSmoke(unittest.TestCase):
    def test_cloud_persistence_import_smoke(self):
        for name in CLOUD_PERSISTENCE_MODULES:
            mod = importlib.import_module(name)
            self.assertIsNotNone(mod)

    def test_activity_time_exports(self):
        from activity_time import normalize_timestamp_iso, utc_now_iso

        ts = utc_now_iso()
        self.assertTrue(ts.endswith("Z"))
        self.assertEqual(normalize_timestamp_iso(ts), ts)

    def test_suite_storage_supabase_imports_activity_time(self):
        import suite_storage_supabase as storage

        self.assertTrue(callable(storage.save_current_state))
        self.assertTrue(callable(storage.load_current_states))

    def test_py_compile_cloud_persistence_modules(self):
        for rel in COMPILE_TARGETS:
            py_compile.compile(str(ROOT / rel), doraise=True)


if __name__ == "__main__":
    unittest.main()