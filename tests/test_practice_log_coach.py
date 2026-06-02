"""Phase B practice log coach copy."""

from __future__ import annotations

from practice_log_coach import (
    build_practice_log_coach_view,
    describe_practice_session,
)


def test_describe_practice_session_includes_song_minutes_instrument_and_notes():
    text = describe_practice_session(
        {
            "song": "Perfect",
            "minutes": 25,
            "instrument": "Piano",
            "focus": "Chord Transitions",
            "practice": "Worked on chorus handoff and timing.",
        }
    )
    assert "Perfect" in text
    assert "25" in text
    assert "Piano" in text
    assert "chorus" in text.lower() or "Chord" in text


def test_build_coach_view_improvement_notes_from_history():
    logs = [
        {
            "date": "2026-06-01",
            "song": "Perfect",
            "artist": "Ed Sheeran",
            "instrument": "Piano",
            "minutes": 20,
            "focus": "Chord Transitions",
            "practice": "Chorus transitions",
            "rating": 7,
        },
        {
            "date": "2026-05-28",
            "song": "Perfect",
            "artist": "Ed Sheeran",
            "instrument": "Piano",
            "minutes": 22,
            "focus": "Chord Transitions",
            "practice": "Verse to chorus",
            "rating": 6,
        },
        {
            "date": "2026-05-25",
            "song": "Perfect",
            "artist": "Ed Sheeran",
            "instrument": "Piano",
            "minutes": 18,
            "practice": "Full run",
            "rating": 7,
        },
    ]
    view = build_practice_log_coach_view(logs, analysis_history=[])
    assert view.practice_summary
    assert view.improvement_notes
    assert any("Perfect" in line for line in view.improvement_notes)
    assert view.recommended_next_session
