"""Behavioral coverage for Claude's first-run notification fix."""
from types import SimpleNamespace
from unittest.mock import patch

from songs.state import get_song_context, PICK_KEY_RECOVERY_NOTICE_KEY
from music_activity import log_studio_page_entered

CATALOG = {"Pop": {"First": {"title": "First", "key": "C", "sections": {}},
                   "Saved": {"title": "Saved", "key": "G", "sections": {}}}}


def test_new_home_seeds_default_quietly_and_keeps_it_on_rerun():
    state = {"studio_page": "home", "_music_restore_phase_complete": True,
             "_music_workspace_empty_confirmed": True}
    st = SimpleNamespace(session_state=state)
    with patch("songs.state.apply_pick_key") as commit:
        first = get_song_context(st, song_library=CATALOG, song_picker_catalog=CATALOG)
    assert first[:2] == ("Pop", "First")
    commit.assert_called_once()
    assert PICK_KEY_RECOVERY_NOTICE_KEY not in state


def test_returning_home_keeps_saved_song_and_practice_key():
    state = {"studio_page": "home", "_music_restore_phase_complete": True,
             "active_catalog_pick_key": "Pop\x1fSaved", "display_key": "F",
             "selected_song": {"title": "Saved", "pick_key": "Pop\x1fSaved", "key": "G"}}
    st = SimpleNamespace(session_state=state)
    for _ in range(2):
        result = get_song_context(st, song_library=CATALOG, song_picker_catalog=CATALOG)
        assert result[1] == "Saved"
        assert state["display_key"] == "F"
    assert PICK_KEY_RECOVERY_NOTICE_KEY not in state


def test_home_entry_never_reports_practice_or_other_activity():
    state = {"studio_page": "home", "song": "Saved", "display_key": "F"}
    before = dict(state)
    with patch("music_activity._record") as record, patch("music_activity.log_practice_session_started") as practice:
        log_studio_page_entered(SimpleNamespace(session_state=state), "home")
    record.assert_not_called()
    practice.assert_not_called()
    assert state == before

