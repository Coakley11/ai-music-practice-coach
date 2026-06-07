"""Music persistence must flush to cloud on song/instrument changes."""

from __future__ import annotations

from unittest.mock import patch

from songs.state import persist_music_local_state


class _FakeSt:
    @property
    def session_state(self):
        return self._ss

    def __init__(self):
        self._ss = {"instrument": "Guitar"}


def test_persist_music_local_state_uses_autosave():
    st = _FakeSt()
    with patch("music_persistent_state.autosave_music_state") as autosave:
        persist_music_local_state(st)
        autosave.assert_called_once_with(st)
