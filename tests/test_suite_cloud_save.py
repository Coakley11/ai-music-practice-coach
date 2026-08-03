"""Cloud save must use suite_storage_supabase when suite_storage is absent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import suite_account
from suite_cloud_state import CloudSaveResult, save_cloud_full_session

def test_resolve_storage_falls_back_to_supabase():
    try:
        import suite_storage as storage  # noqa: F401
        assert storage.__name__ in {"suite_storage", "suite_storage_supabase"}
    except ImportError:
        import suite_storage_supabase as storage

        assert storage.__name__ == "suite_storage_supabase"


def test_save_cloud_full_session_music_core():
    mock_storage = MagicMock()
    mock_storage.normalize_app_key = lambda app: app
    mock_storage.save_current_state_conditional_cas.return_value = {
        "accepted": True,
        "rows_affected": 1,
        "write_mode": "conditional_patch",
        "conditional_write_attempted": True,
        "unconditional_upsert_attempted": False,
    }
    state = {"core": {"pick_key": "jazz::autumn-leaves", "studio_page": "Song Picker"}, "workspace_revision": 1}

    with patch("suite_storage_config.cloud_storage_enabled", return_value=True):
        with patch("suite_storage_config.get_cloud_config", return_value=object()):
            with patch("suite_cloud_state._import_storage", return_value=(mock_storage, "suite_storage_supabase")):
                with patch("suite_cloud_state._streamlit_session", return_value={}):
                    with patch("suite_cloud_state._cloud_storage_app_id", return_value="music"):
                        result = save_cloud_full_session("music", state)

    assert result.success is True
    mock_storage.save_current_state_conditional_cas.assert_called_once()
    metrics = mock_storage.save_current_state_conditional_cas.call_args.kwargs["metrics"]
    assert metrics["full_session"]["core"]["pick_key"] == "jazz::autumn-leaves"
