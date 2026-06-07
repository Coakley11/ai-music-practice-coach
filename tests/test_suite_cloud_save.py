"""Cloud save must use suite_storage_supabase when suite_storage is absent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import suite_account
from suite_cloud_state import CloudSaveResult, save_cloud_full_session


def test_resolve_storage_falls_back_to_supabase():
    storage = suite_account._resolve_storage()
    assert storage.__name__ in {"suite_storage", "suite_storage_supabase"}


def test_save_cloud_full_session_music_core():
    mock_storage = MagicMock()
    mock_storage.normalize_app_key = lambda app: app
    state = {"core": {"pick_key": "jazz::autumn-leaves", "studio_page": "Song Picker"}}

    with patch("suite_storage_config.cloud_storage_enabled", return_value=True):
        with patch("suite_cloud_state._import_storage", return_value=(mock_storage, "suite_storage_supabase")):
            result = save_cloud_full_session("music", state)

    assert result.success is True
    metrics = mock_storage.save_current_state.call_args.kwargs["metrics"]
    assert metrics["full_session"]["core"]["pick_key"] == "jazz::autumn-leaves"
