"""Suite disk persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from suite_user_persistence import (
    load_user_state,
    reset_user_state,
    save_user_state,
    state_file_path,
)


@pytest.fixture
def persist_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("suite_user_persistence.DATA_DIR", tmp_path)
    return tmp_path


def test_save_and_load_roundtrip(persist_dir):
    save_user_state("music", {"core": {"instrument": "Guitar"}, "session": {}})
    loaded, warn = load_user_state("music")
    assert warn is None
    assert loaded["core"]["instrument"] == "Guitar"


def test_missing_file_returns_empty(persist_dir):
    loaded, warn = load_user_state("investment")
    assert loaded == {}
    assert warn is None


def test_invalid_json_uses_defaults(persist_dir):
    path = state_file_path("baseball")
    path.write_text("{not json", encoding="utf-8")
    loaded, warn = load_user_state("baseball")
    assert loaded == {}


def test_reset_removes_file(persist_dir):
    save_user_state("nba", {"favorite_team": "Knicks"})
    assert state_file_path("nba").is_file()
    reset_user_state("nba")
    assert not state_file_path("nba").is_file()
