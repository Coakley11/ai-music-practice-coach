"""Suite disk persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from suite_user_persistence import (
    _SESSION_BANNER_KEY,
    clear_reset_confirm_state,
    execute_suite_reset,
    load_user_state,
    request_reset_confirm_state,
    reset_confirm_session_key,
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


def test_reset_confirm_state_request_and_clear():
    state: dict = {}
    request_reset_confirm_state(state, "music")
    assert state[reset_confirm_session_key("music")] is True
    clear_reset_confirm_state(state, "music")
    assert reset_confirm_session_key("music") not in state


def test_execute_suite_reset_clears_confirm_and_sets_banner(persist_dir):
    class _FakeSt:
        def __init__(self, session_state: dict):
            self.session_state = session_state

    state = {reset_confirm_session_key("music"): True}
    st = _FakeSt(state)
    called: list[str] = []

    def _on_reset(fake_st):
        called.append("reset")

    execute_suite_reset(st, "music", _on_reset)
    assert called == ["reset"]
    assert reset_confirm_session_key("music") not in st.session_state
    assert st.session_state[_SESSION_BANNER_KEY] == "Reset to defaults"
