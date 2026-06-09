"""Backing durable filters must not be stored in page-local snapshots."""

from __future__ import annotations

from studio_page_persistence import capture_page_snapshot


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
    assert snap.get("_last_backing_wav") == b"audio"
