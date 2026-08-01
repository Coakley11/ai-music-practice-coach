"""Mission state survives disk build + page refresh (cloud workspace keys)."""

from __future__ import annotations

from music_persistent_state import _PERSIST_KEYS, apply_music_disk_state, build_music_disk_state
from studio_page_persistence import (
    capture_page_snapshot,
    flush_current_page_snapshot,
    handle_studio_page_transition,
    restore_current_page_snapshot_if_needed,
)
from tests.test_studio_page_refresh_persistence import _FakeSessionState, _FakeSt


def test_mission_example_in_cloud_persist_keys() -> None:
    for key in (
        "improv_mission_example",
        "improv_mission_practice_lick",
        "ii_selected_chord",
        "improv_active_mission",
    ):
        assert key in _PERSIST_KEYS


def test_build_music_disk_state_includes_mission_example() -> None:
    motif = {"chord": "Em", "notes": ["E", "G", "B"], "display": "E – G – B", "rhythm": "♩ ♩ ♩"}
    example_blob = {
        "mission": "Rhythm-first, note-second",
        "variant": "harder",
        "chord": "Em",
        "section": "Chorus",
        "motif": motif,
        "abc": "X:1\nT:test",
        "tab": "",
        "piano_html": "",
        "why": "test",
        "practice_steps": [],
        "show_tab": False,
        "show_piano": False,
    }
    ss = _FakeSessionState(
        {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_active_mission": "Rhythm-first, note-second",
            "improv_mission_example": example_blob,
            "ii_selected_chord": "Em",
            "ii_selected_section": "Chorus",
            "instrument": "Guitar",
            "level": "Intermediate",
            "focus": "Improvisation",
        }
    )
    st = _FakeSt(ss)
    flush_current_page_snapshot(ss)
    disk = build_music_disk_state(st)
    session_extra = disk.get("session") or {}
    assert session_extra.get("improv_mission_example", {}).get("variant") == "harder"
    assert session_extra.get("ii_selected_chord") == "Em"


def test_refresh_restores_mission_example_on_creative_page() -> None:
    motif = {"notes": ["C", "E", "G"], "display": "C – E – G"}
    snap = capture_page_snapshot(
        {
            "studio_page": "creative",
            "improv_mission_example": {
                "mission": "Use only chord tones",
                "variant": "normal",
                "chord": "C",
                "section": "Verse",
                "motif": motif,
                "abc": "X:1",
                "tab": "",
                "piano_html": "",
                "why": "",
                "practice_steps": [],
                "show_tab": False,
                "show_piano": False,
            },
        },
        "creative",
    )
    ss = {
        "studio_page": "creative",
        "_studio_page_snapshots": {"creative": snap},
    }
    handle_studio_page_transition(ss)
    assert ss.get("improv_mission_example", {}).get("motif") == motif


def test_round_trip_mission_via_apply_music_disk_state() -> None:
    payload = {
        "motif": {"notes": ["D", "F#", "A"], "display": "D – F# – A"},
        "abc": "X:1",
        "bpm": 92,
        "groove": "Medium",
        "meter": "4/4",
        "example_variant": "easier",
        "chord": "D",
        "section_label": "Verse",
        "instrument": "Piano",
        "level": "Beginner",
    }
    ss = _FakeSessionState(
        {
            "studio_page": "backing",
            "improv_mission_practice_lick": payload,
            "backing_track_bpm": 92,
        }
    )
    st = _FakeSt(ss)
    disk = build_music_disk_state(st)
    fresh = _FakeSessionState({"studio_page": "backing"})
    st2 = _FakeSt(fresh)
    apply_music_disk_state(st2, disk, song_picker_catalog=None, song_library=None)
    restored = st2.session_state.get("improv_mission_practice_lick") or {}
    assert restored.get("example_variant") == "easier"
    assert restored.get("motif", {}).get("notes") == ["D", "F#", "A"]


def test_sync_stamps_workspace_updated_at() -> None:
    ss = {
        "improv_mission_example": {"motif": {"notes": ["C"]}, "variant": "normal"},
        "studio_page": "creative",
    }
    from improvisation_mission_persistence import (
        MISSION_WORKSPACE_UPDATED_AT_KEY,
        sync_mission_workspace_before_persist,
    )

    sync_mission_workspace_before_persist(ss)
    assert ss.get(MISSION_WORKSPACE_UPDATED_AT_KEY)


def test_music_mission_cloud_drift_detects_example_change() -> None:
    from improvisation_mission_persistence import (
        MISSION_WORKSPACE_UPDATED_AT_KEY,
        music_mission_cloud_drift,
    )

    local = {"improv_mission_example": {"variant": "normal", "motif": {"notes": ["C"]}}}
    cloud = {
        "session": {
            "improv_mission_example": {"variant": "harder", "motif": {"notes": ["C", "E", "G"]}},
            MISSION_WORKSPACE_UPDATED_AT_KEY: "2026-07-30T12:00:00+00:00",
        }
    }
    drift, detail = music_mission_cloud_drift({"session_state": local}, cloud, "2026-07-30T12:00:00+00:00")
    assert drift is True
    assert "mission" in detail or "creative_stamp" in detail


def test_apply_cloud_mission_overwrites_local_example() -> None:
    from improvisation_mission_persistence import (
        MISSION_WORKSPACE_UPDATED_AT_KEY,
        apply_cloud_mission_state_if_allowed,
    )

    session: dict = {
        "improv_mission_example": {"variant": "normal", "motif": {"notes": ["C"]}},
    }
    payload = {
        "session": {
            "improv_mission_example": {"variant": "harder", "motif": {"notes": ["C", "E", "G"]}},
            MISSION_WORKSPACE_UPDATED_AT_KEY: "2026-07-30T12:00:00+00:00",
            "improv_mission_practice_lick": {"bpm": 70, "motif": {"notes": ["C", "E", "G"]}},
        }
    }
    assert apply_cloud_mission_state_if_allowed(session, payload) is True
    assert session["improv_mission_example"]["variant"] == "harder"
    assert session["backing_track_bpm"] == 70


def test_backing_page_refresh_restores_practice_lick() -> None:
    lick = {
        "motif": {"notes": ["G", "B", "D"], "display": "G – B – D"},
        "abc": "X:1",
        "bpm": 80,
        "example_variant": "normal",
    }
    snap = capture_page_snapshot(
        {"studio_page": "backing", "improv_mission_practice_lick": lick, "backing_track_bpm": 80},
        "backing",
    )
    ss = {
        "studio_page": "backing",
        "_studio_page_snapshots": {"backing": snap},
    }
    restore_current_page_snapshot_if_needed(ss)
    assert ss.get("improv_mission_practice_lick", {}).get("bpm") == 80
