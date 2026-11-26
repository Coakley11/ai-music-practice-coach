"""Uploaded Melodies Slice 3: the references chosen for a song survive navigation and an app restart."""
from __future__ import annotations

import copy
import os
import tempfile

os.environ.setdefault("SUITE_AUTH_ENABLED", "0")
os.environ.setdefault("MUSIC_APP_DATA_DIR", tempfile.mkdtemp(prefix="um_sel_"))

import backing_melody_modes as bmm
import music_persistent_state as mps

KEY = bmm.SELECTED_REFERENCES_KEY
SAVED = {"catalog|Pop|Shallow": ["a", "c"], "custom|custom::song-a": ["z"]}


class _St:
    def __init__(self, session):
        self.session_state = session


def _apply(session, value, *, authoritative):
    mps.apply_music_disk_state(_St(session), {"core": {}, "session": {KEY: copy.deepcopy(value)}},
                               song_picker_catalog={}, song_library={}, authoritative_restore=authoritative)
    return session


def test_the_choice_is_saved_with_the_workspace():
    assert KEY in mps._PERSIST_KEYS


def test_a_restart_brings_back_each_songs_own_choice():
    for authoritative in (True, False):
        s = _apply({}, SAVED, authoritative=authoritative)
        assert bmm.selected_reference_ids(s, "catalog|Pop|Shallow", ["a", "b", "c"]) == ["a", "c"]
        assert bmm.selected_reference_ids(s, "custom|custom::song-a", ["z"]) == ["z"]
        assert bmm.selected_reference_ids(s, "custom|custom::song-b", ["a", "z"]) == []


def test_an_older_save_applied_mid_session_never_replaces_this_tabs_choice():
    s = {KEY: {"catalog|Pop|Shallow": ["b"]}}
    _apply(s, SAVED, authoritative=False)
    assert s[KEY] == {"catalog|Pop|Shallow": ["b"]}


def test_a_deleted_reference_is_not_shown_after_a_restart():
    s = _apply({}, SAVED, authoritative=True)
    assert bmm.selected_reference_ids(s, "catalog|Pop|Shallow", ["a"]) == ["a"]


def test_a_damaged_value_is_ignored():
    for bad in (None, [], "a", 3):
        s = _apply({}, bad, authoritative=True)
        assert bmm.selected_reference_ids(s, "catalog|Pop|Shallow", ["a"]) == []


def test_a_restored_choice_changes_only_itself_not_mode_or_panels():
    s = _apply({}, SAVED, authoritative=True)
    assert bmm.melody_mode(s) == bmm.MODE_PRACTICE
    assert bmm.panels_open_from_practice(s, "catalog|Pop|Shallow") == set()
