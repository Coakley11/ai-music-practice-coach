"""Creative workspace cloud keys + piano keyboard spelling."""

from __future__ import annotations

from music_persistent_state import _PERSIST_KEYS, build_music_disk_state
from tests.test_studio_page_refresh_persistence import _FakeSessionState, _FakeSt


def test_creative_workspace_keys_in_persist() -> None:
    for key in (
        "harmony_map_chord",
        "improv_motif",
        "improv_motif_abc",
        "deep_harmony_lesson_step",
        "improv_deep_harmony_dha_section_idx",
    ):
        assert key in _PERSIST_KEYS


def test_disk_includes_phrase_motif_blob() -> None:
    ss = _FakeSessionState(
        {
            "studio_page": "creative",
            "improv_intelligence_tab": "Phrase / Motif",
            "improv_motif": {"chord": "Gm7", "notes": ["G", "Bb", "D"], "display": "G – Bb – D"},
            "improv_motif_abc": "X:1\nT:Motif",
            "harmony_map_chord": "C7",
        }
    )
    disk = build_music_disk_state(_FakeSt(ss))
    session_extra = disk.get("session") or {}
    assert session_extra.get("improv_motif", {}).get("notes") == ["G", "Bb", "D"]
    assert "X:1" in str(session_extra.get("improv_motif_abc") or "")


def test_sync_creative_workspace_stamps_updated_at() -> None:
    from creative_workspace_persistence import sync_creative_workspace_before_persist
    from improvisation_mission_persistence import MISSION_WORKSPACE_UPDATED_AT_KEY

    ss = {"studio_page": "creative", "improv_motif": {"notes": ["C"]}, "harmony_map_chord": "C"}
    sync_creative_workspace_before_persist(ss)
    assert ss.get(MISSION_WORKSPACE_UPDATED_AT_KEY)
