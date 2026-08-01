"""Tests for suite local-state restore on startup."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from song_catalog import format_pick_key
from music_persistent_state import apply_music_disk_state, restore_music_disk_state_once
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    PENDING_DISPLAY_KEY,
    SELECTED_SONG_STATE_KEY,
    SUITE_LOCAL_STATE_RESTORED_KEY,
    build_music_local_state,
)


class _FakeSession(dict):
    @property
    def session_state(self):
        return self


def _write_music_workspace_disk(tmp_path: Path, state: dict[str, Any]) -> Path:
    ws_dir = tmp_path / "workspaces" / "daniel"
    ws_dir.mkdir(parents=True, exist_ok=True)
    path = ws_dir / "music_user_state.json"
    path.write_text(
        json.dumps({"version": 1, "app": "music", "saved_at": "2026-01-01T00:00:00+00:00", "state": state}),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def isolated_music_persistence(tmp_path: Path, monkeypatch):
    """Route suite disk restore to tmp_path and ignore live cloud workspace."""
    import suite_user_persistence as sup
    import suite_workspace as sw

    monkeypatch.setattr(sup, "DATA_DIR", tmp_path)
    monkeypatch.setattr(sw, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def mini_catalog():
    song_picker_catalog = {
        "Jazz": {
            "Autumn Leaves — Joseph Kosma": {
                "title": "Autumn Leaves",
                "artist": "Joseph Kosma",
                "key": "G minor",
            }
        }
    }
    song_library = {
        "Jazz": {
            "Autumn Leaves": song_picker_catalog["Jazz"]["Autumn Leaves — Joseph Kosma"],
        }
    }
    return song_picker_catalog, song_library


def test_build_music_local_state_collects_globals(mini_catalog):
    st = _FakeSession(
        {
            SELECTED_SONG_STATE_KEY: {
                "pick_key": "Jazz|Autumn Leaves — Joseph Kosma",
                "title": "Autumn Leaves",
                "artist": "Joseph Kosma",
            },
            ACTIVE_CATALOG_PICK_KEY: "Jazz|Autumn Leaves — Joseph Kosma",
            "instrument": "Guitar",
            "focus": "Chords",
            "display_key": "A minor",
            "studio_page": "practice",
            "practice_focus_section": "Verse",
            "level": "Intermediate",
        }
    )
    snapshot = build_music_local_state(st)
    assert snapshot["song"] == "Autumn Leaves"
    assert snapshot["pick_key"] == "Jazz|Autumn Leaves — Joseph Kosma"
    assert snapshot["instrument"] == "Guitar"
    assert snapshot["focus"] == "Chords"
    assert snapshot["display_key"] == "A minor"
    assert snapshot["studio_page"] == "practice"
    assert snapshot["practice_focus_section"] == "Verse"


def test_restore_runs_once_and_applies_saved_state(mini_catalog, isolated_music_persistence, tmp_path: Path):
    song_picker_catalog, song_library = mini_catalog
    pick_key = format_pick_key("Jazz", "Autumn Leaves — Joseph Kosma")
    saved = {
        "pick_key": pick_key,
        "song": "Autumn Leaves",
        "artist": "Joseph Kosma",
        "instrument": "Saxophone",
        "focus": "Scales",
        "display_key": "E minor",
        "studio_page": "backing",
        "practice_focus_section": "Chorus",
        "level": "Advanced",
    }
    _write_music_workspace_disk(tmp_path, {"core": saved, "session": {}})

    st = _FakeSession({})

    with patch("suite_cloud_state.load_cloud_full_session", return_value=({}, None)):
        restore_music_disk_state_once(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    assert st[SUITE_LOCAL_STATE_RESTORED_KEY] is True
    assert st[ACTIVE_CATALOG_PICK_KEY] == pick_key
    assert st["instrument"] == "Saxophone"
    assert st["focus"] == "Scales"
    assert st["studio_page"] == "backing"
    assert st["practice_focus_section"] == "Chorus"
    assert st[PENDING_DISPLAY_KEY] == "E minor"

    before_functional = {
        k: v
        for k, v in st.items()
        if not str(k).startswith("_suite_") and not str(k).startswith("_cloud_")
    }
    with patch("suite_cloud_state.load_cloud_full_session", return_value=({}, None)):
        restore_music_disk_state_once(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )
    after_functional = {
        k: v
        for k, v in st.items()
        if not str(k).startswith("_suite_") and not str(k).startswith("_cloud_")
    }
    assert after_functional == before_functional


def test_apply_music_disk_state_restores_core_pick_key(mini_catalog):
    song_picker_catalog, song_library = mini_catalog
    pick_key = format_pick_key("Jazz", "Autumn Leaves — Joseph Kosma")
    st = _FakeSession({})
    payload = {
        "core": {
            "pick_key": pick_key,
            "song": "Autumn Leaves",
            "artist": "Joseph Kosma",
            "instrument": "Piano",
            "display_key": "Eb",
            "studio_page": "backing",
        },
        "session": {},
    }
    apply_music_disk_state(
        st,
        payload,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    assert st[ACTIVE_CATALOG_PICK_KEY] == pick_key
    assert st[SELECTED_SONG_STATE_KEY]["title"] == "Autumn Leaves"
    assert st["instrument"] == "Piano"
    assert st["studio_page"] == "backing"
    assert st[PENDING_DISPLAY_KEY] == "Eb"


def test_restore_missing_song_shows_neutral_notice(mini_catalog, isolated_music_persistence, tmp_path: Path):
    song_picker_catalog, song_library = mini_catalog
    saved = {
        "pick_key": "Jazz|Missing Song — Nobody",
        "song": "Missing Song",
        "artist": "Nobody",
    }
    _write_music_workspace_disk(tmp_path, {"core": saved, "session": {}})

    st = _FakeSession({})

    with patch("suite_cloud_state.load_cloud_full_session", return_value=({}, None)):
        restore_music_disk_state_once(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    from songs.state import PICK_KEY_RECOVERY_NOTICE_KEY

    assert PICK_KEY_RECOVERY_NOTICE_KEY in st
    assert "no longer available" in st[PICK_KEY_RECOVERY_NOTICE_KEY]
