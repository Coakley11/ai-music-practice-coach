"""Regression: workspace saves after generating Practice notation must stay JSON-serializable.

``practice_notation_result`` holds a live ``NotationResult``. It stays in session state
for the Practice panel, but it is a regenerable artifact and must never reach durable
page snapshots (saving one crashed the app with "NotationResult is not JSON
serializable" on the next Practice Key / capo change).
"""

from __future__ import annotations

import json

import pytest

from music_persistent_state import build_music_disk_state
from practice_notation import NotationResult, generate_practice_notation
from studio_page_persistence import (
    capture_page_snapshot,
    flush_current_page_snapshot,
    restore_page_snapshot,
    save_page_snapshot,
)

NOTATION_KEY = "practice_notation_result"


class _FakeSt:
    def __init__(self, session_state: dict) -> None:
        self.session_state = session_state


def _notation(instrument: str, display_key: str = "A") -> NotationResult:
    return generate_practice_notation(
        song_title="Say", artist="", display_key=display_key, original_key="G", bpm=90,
        groove_style="Ballad", instrument=instrument, focus="general", section_focus="Full Song",
        sections={"Verse": ["A", "D", "E", "F#m"]}, guitar_tabs={"G": "320003"}, difficulty="easy",
    )


def _practice_session(instrument: str = "Guitar") -> dict:
    return {
        "studio_page": "practice",
        "instrument": instrument,
        "display_key": "A",
        "practice_notation_difficulty": "easy",
        "practice_notation_sig": ("Say", instrument, "A"),
        "practice_focus_section": "Full Song",
        NOTATION_KEY: _notation(instrument),
    }


@pytest.mark.parametrize("instrument", ["Guitar", "Piano"])
def test_practice_snapshot_is_json_safe_and_omits_the_notation_object(instrument):
    ss = _practice_session(instrument)
    snap = capture_page_snapshot(ss, "practice")
    json.dumps(snap)
    assert NOTATION_KEY not in snap
    assert snap["practice_notation_difficulty"] == "easy"
    assert snap["practice_focus_section"] == "Full Song"
    assert isinstance(ss[NOTATION_KEY], NotationResult)


@pytest.mark.parametrize("instrument", ["Guitar", "Piano"])
def test_workspace_save_after_notation_generation_is_json_safe(instrument):
    ss = _practice_session(instrument)
    payload = build_music_disk_state(_FakeSt(ss))
    json.dumps(payload)  # plain dumps, as save_user_state does
    assert isinstance(ss[NOTATION_KEY], NotationResult)


def test_repeated_key_and_capo_saves_after_tab_generation():
    ss = _practice_session("Guitar")
    for key, capo in [("G", False), ("Bb", True), ("A", True), ("D", False), ("A", False)]:
        ss["display_key"] = key
        ss["guitar_capo_enabled"] = capo
        ss[NOTATION_KEY] = _notation("Guitar", key)
        flush_current_page_snapshot(ss)
        json.dumps(build_music_disk_state(_FakeSt(ss)))
    snaps = ss.get("_studio_page_snapshots") or {}
    assert NOTATION_KEY not in (snaps.get("practice") or {})


def test_generated_tab_survives_leaving_and_returning_to_practice():
    ss = _practice_session("Guitar")
    tab = ss[NOTATION_KEY]
    save_page_snapshot(ss, "practice")
    ss["studio_page"] = "backing"
    restore_page_snapshot(ss, "backing")
    save_page_snapshot(ss, "backing")
    ss["studio_page"] = "practice"
    restore_page_snapshot(ss, "practice")
    assert ss[NOTATION_KEY] is tab
    assert ss["practice_notation_difficulty"] == "easy"
