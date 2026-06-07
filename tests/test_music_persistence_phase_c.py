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
        "cpl_last_bars_Verse": [4, 4, 4, 4],
        "cpl_sub_half_Chorus": True,
        "cpl_pending_chord_Bridge": "G7",
    }
    blob = export_cpl_widget_state(ss)
    out = {}
    import_cpl_widget_state(out, blob)
    assert out["cpl_edit_section"] == "Chorus"
    assert out["cpl_pending_chord_Bridge"] == "G7"
    assert out["cpl_sub_half_Chorus"] is True


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
    assert restored.get("cpl_sub_half_Chorus") is True


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
