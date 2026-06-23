"""Phase C — Music persistence: CPL widgets, cloud restore pick, scenario blob."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_progression_lab import export_cpl_widget_state, import_cpl_widget_state
from music_persistent_state import apply_music_disk_state, build_music_disk_state
from song_catalog import format_pick_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, PENDING_DISPLAY_KEY, build_music_local_state
from suite_cloud_state import pick_restore_session


@pytest.fixture
def lights_catalog():
    label = "Turn the Lights Back On — Billy Joel"
    pick_key = format_pick_key("Pop", label)
    song_picker_catalog = {
        "Pop": {
            label: {
                "title": "Turn the Lights Back On",
                "artist": "Billy Joel",
                "key": "C",
            }
        }
    }
    song_library = {"Pop": {"Turn the Lights Back On": song_picker_catalog["Pop"][label]}}
    return pick_key, song_picker_catalog, song_library


class _FakeSession(dict):
    @property
    def session_state(self):
        return self


def test_cpl_widget_state_round_trip():
    ss = {
        "cpl_edit_section": "Chorus",
        "cpl_finished": True,
        "cpl_last_bars_Verse": 4,
        "cpl_sub_half_Chorus": True,
        "cpl_pending_chord_Bridge": "G7",
    }
    blob = export_cpl_widget_state(ss)
    assert "cpl_sub_half_Chorus" not in blob
    out = {}
    import_cpl_widget_state(out, blob)
    assert out["cpl_edit_section"] == "Chorus"
    assert out["cpl_pending_chord_Bridge"] == "G7"
    assert "cpl_sub_half_Chorus" not in out


def test_turn_the_lights_back_on_scenario_blob(lights_catalog):
    pick_key, song_picker_catalog, song_library = lights_catalog
    st = _FakeSession(
        {
            ACTIVE_CATALOG_PICK_KEY: pick_key,
            "selected_song": {
                "pick_key": pick_key,
                "title": "Turn the Lights Back On",
                "artist": "Billy Joel",
            },
            "instrument": "Guitar",
            "display_key": "D Major",
            "studio_page": "backing",
            "backing_track_scope": "section",
            "backing_track_single_section": "Chorus",
            "practice_focus_section": "Chorus",
            "cpl_edit_section": "Chorus",
            "cpl_sub_half_Chorus": True,
        }
    )
    blob = build_music_disk_state(st)
    core = blob["core"]
    assert core["song"] == "Turn the Lights Back On"
    assert core["instrument"] == "Guitar"
    assert core["display_key"] == "D Major"
    assert core["studio_page"] == "backing"
    assert blob["session"]["backing_track_single_section"] == "Chorus"
    assert "_cpl_widget_state" in blob["session"]

    restored = _FakeSession({})
    apply_music_disk_state(
        restored,
        blob,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    assert restored[ACTIVE_CATALOG_PICK_KEY] == pick_key
    assert restored["instrument"] == "Guitar"
    assert restored["studio_page"] == "backing"
    assert restored[PENDING_DISPLAY_KEY] == "D Major"
    assert restored["backing_track_single_section"] == "Chorus"
    assert restored.get("cpl_sub_half_Chorus") is None


def test_pick_restore_session_prefers_newer_disk_when_cloud_first():
    disk = {"core": {"display_key": "C#m"}}
    cloud = {"core": {"display_key": "Bm"}}
    picked = pick_restore_session(
        cloud,
        "2026-06-07T12:00:00+00:00",
        disk,
        "2026-06-08T12:00:00+00:00",
        cloud_first=True,
    )
    assert picked.source == "disk"
    assert picked.state["core"]["display_key"] == "C#m"


def test_pick_restore_session_prefers_newer_cloud():
    disk = {"core": {"song": "disk"}}
    cloud = {"core": {"song": "cloud"}}
    picked = pick_restore_session(cloud, "2026-06-08T12:00:00+00:00", disk, "2026-06-07T12:00:00+00:00")
    assert picked.source == "cloud"
    assert picked.state["core"]["song"] == "cloud"


def test_pick_restore_session_keeps_disk_when_local_dirty():
    disk = {"core": {"song": "disk"}}
    cloud = {"core": {"song": "cloud"}}
    picked = pick_restore_session(
        cloud,
        "2026-06-08T12:00:00+00:00",
        disk,
        "2026-06-07T12:00:00+00:00",
        local_dirty=True,
    )
    assert picked.source == "disk"


@pytest.fixture
def non_core_catalog():
    """Catalog song without trusted_core — highest-risk persistence case."""
    label = "Blue Moon — Rodgers & Hart"
    pick_key = format_pick_key("Jazz", label)
    song_picker_catalog = {
        "Jazz": {
            label: {
                "title": "Blue Moon",
                "artist": "Rodgers & Hart",
                "key": "C",
                "chart_status": "user_verified",
            }
        }
    }
    song_library = {"Jazz": {"Blue Moon": song_picker_catalog["Jazz"][label]}}
    return pick_key, song_picker_catalog, song_library


def test_non_core_song_scenario_blob(non_core_catalog):
    pick_key, song_picker_catalog, song_library = non_core_catalog
    st = _FakeSession(
        {
            ACTIVE_CATALOG_PICK_KEY: pick_key,
            "selected_song": {
                "pick_key": pick_key,
                "title": "Blue Moon",
                "artist": "Rodgers & Hart",
            },
            "instrument": "Piano",
            "display_key": "F Major",
            "studio_page": "backing",
            "backing_track_scope": "section",
            "backing_track_single_section": "Verse",
            "backing_track_bpm": 92,
            "chart_library_mode": "core",
        }
    )
    blob = build_music_disk_state(st)
    core = blob["core"]
    assert core["song"] == "Blue Moon"
    assert core["pick_key"] == pick_key
    assert core["instrument"] == "Piano"
    assert core["display_key"] == "F Major"
    assert core["studio_page"] == "backing"

    restored = _FakeSession({})
    apply_music_disk_state(
        restored,
        blob,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )
    from songs.state import SUITE_LOCAL_STATE_RESTORED_KEY

    assert restored[ACTIVE_CATALOG_PICK_KEY] == pick_key
    assert restored["instrument"] == "Piano"
    assert restored[PENDING_DISPLAY_KEY] == "F Major"
    assert restored["studio_page"] == "backing"
    assert restored["backing_track_single_section"] == "Verse"
    assert restored.get(SUITE_LOCAL_STATE_RESTORED_KEY) is True
    sel = restored.get("selected_song") or {}
    assert sel.get("title") == "Blue Moon"


def test_non_core_restore_failure_does_not_set_restored_flag(non_core_catalog):
    pick_key, song_picker_catalog, song_library = non_core_catalog
    blob = {
        "core": {
            "song": "Blue Moon",
            "artist": "Rodgers & Hart",
            "pick_key": pick_key,
            "instrument": "Piano",
        },
        "session": {},
    }
    restored = _FakeSession({})
    empty_catalog: dict = {}
    apply_music_disk_state(
        restored,
        blob,
        song_picker_catalog=empty_catalog,
        song_library={},
    )
    from songs.state import SUITE_LOCAL_STATE_RESTORED_KEY

    assert restored.get(SUITE_LOCAL_STATE_RESTORED_KEY) is None
    assert restored.get(ACTIVE_CATALOG_PICK_KEY) is None
