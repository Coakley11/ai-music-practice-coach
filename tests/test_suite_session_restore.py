"""Tests for suite local-state restore on startup."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from song_catalog import format_pick_key
from music_persistent_state import apply_music_disk_state
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    PENDING_DISPLAY_KEY,
    SELECTED_SONG_STATE_KEY,
    SUITE_LOCAL_STATE_RESTORED_KEY,
    build_music_local_state,
    restore_saved_app_state_once,
)


class _FakeSession(dict):
    @property
    def session_state(self):
        return self


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


def test_restore_runs_once_and_applies_saved_state(mini_catalog, tmp_path: Path):
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
    state_path = tmp_path / "music_user_state.json"
    state_path.write_text(
        json.dumps({"version": 1, "app": "music", "state": {"core": saved, "session": {}}}),
        encoding="utf-8",
    )

    st = _FakeSession({})

    with patch("suite_user_persistence.DATA_DIR", tmp_path):
        restore_saved_app_state_once(
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

    before = dict(st)
    with patch("suite_user_persistence.DATA_DIR", tmp_path):
        restore_saved_app_state_once(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )
    assert st == before


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


def test_restore_missing_song_shows_neutral_notice(mini_catalog, tmp_path: Path):
    song_picker_catalog, _song_library = mini_catalog
    saved = {
        "pick_key": "Jazz|Missing Song — Nobody",
        "song": "Missing Song",
        "artist": "Nobody",
    }
    state_path = tmp_path / "music_user_state.json"
    state_path.write_text(
        json.dumps({"version": 1, "app": "music", "state": {"core": saved, "session": {}}}),
        encoding="utf-8",
    )

    st = _FakeSession({})

    with patch("suite_user_persistence.DATA_DIR", tmp_path):
        restore_saved_app_state_once(
            st,
            song_picker_catalog=song_picker_catalog,
        )

    from songs.state import PICK_KEY_RECOVERY_NOTICE_KEY

    assert PICK_KEY_RECOVERY_NOTICE_KEY in st
    assert "no longer available" in st[PICK_KEY_RECOVERY_NOTICE_KEY]
