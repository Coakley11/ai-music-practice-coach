"""Import smoke tests for Studio History cloud persistence."""

from __future__ import annotations

import importlib


def test_suite_storage_shim_imports() -> None:
    mod = importlib.import_module("suite_storage")
    assert callable(mod.load_saved_items)
    assert callable(mod.upsert_saved_item)


def test_studio_history_modules_import() -> None:
    for name in (
        "studio_history_cloud",
        "upload_history",
        "multitrack_history",
        "studio_history_ui",
        "studio_history_bootstrap",
    ):
        mod = importlib.import_module(name)
        assert mod is not None


def test_upload_history_list_does_not_require_missing_module(monkeypatch) -> None:
    from upload_history import list_upload_history

    monkeypatch.setattr("studio_history_cloud.cloud_enabled", lambda: True)
    monkeypatch.setattr(
        "suite_account.load_saved_items",
        lambda **kwargs: [],
    )
    rows, err = list_upload_history()
    assert rows == []
    assert err is None


def test_multitrack_history_list_does_not_require_missing_module(monkeypatch) -> None:
    from multitrack_history import list_multitrack_history

    monkeypatch.setattr("studio_history_cloud.cloud_enabled", lambda: True)
    monkeypatch.setattr(
        "suite_account.load_saved_items",
        lambda **kwargs: [],
    )
    rows, err = list_multitrack_history()
    assert rows == []
    assert err is None
