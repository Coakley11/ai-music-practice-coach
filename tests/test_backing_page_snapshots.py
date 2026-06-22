"""Backing durable filters must not be stored in page-local snapshots."""

from __future__ import annotations

from studio_page_persistence import apply_page_snapshot, capture_page_snapshot


def test_backing_snapshot_excludes_durable_scope_and_loops() -> None:
    session = {
        "backing_track_scope": "Single section",
        "backing_track_loops": 1,
        "backing_track_single_section": "Chorus",
        "backing_track_multi_sections": ["Verse"],
        "backing_quick_section": "Chorus",
        "_last_backing_wav": b"audio",
    }
    snap = capture_page_snapshot(session, "backing")
    assert "backing_track_scope" not in snap
    assert "backing_track_loops" not in snap
    assert "backing_track_single_section" not in snap
    assert "backing_track_multi_sections" not in snap
    assert "backing_quick_section" not in snap
    restored: dict = {}
    apply_page_snapshot(restored, snap)
    assert restored.get("_last_backing_wav") == b"audio"


def test_legacy_snapshot_restore_strips_durable_backing_keys() -> None:
    from studio_page_persistence import apply_page_snapshot

    session = {
        "backing_track_loops": 1,
        "backing_track_scope": "Single section",
        "instrument": "Piano",
    }
    legacy = {
        "backing_track_loops": 2,
        "backing_track_scope": "Full song",
        "backing_quick_section": "Full song",
        "_last_backing_wav": b"audio",
    }
    apply_page_snapshot(session, legacy)
    assert session["backing_track_loops"] == 1
    assert session["backing_track_scope"] == "Single section"
    assert session.get("_last_backing_wav") == b"audio"
