"""Tests for music_dev_ui gate."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from music_dev_ui import music_dev_mode_enabled


class _FakeSt:
    def __init__(self, session: dict | None = None, *, query: dict | None = None) -> None:
        self.session_state = dict(session or {})
        self.query_params = dict(query or {})


class TestMusicDevUi(unittest.TestCase):
    def test_dev_query_enables_mode(self) -> None:
        st = _FakeSt(query={"dev": "1"})
        with patch("suite_workspace.is_developer_mode_enabled", return_value=True):
            self.assertTrue(music_dev_mode_enabled(st=st))

    def test_normal_mode_disabled(self) -> None:
        st = _FakeSt()
        with patch("suite_workspace.is_developer_mode_enabled", return_value=False):
            self.assertFalse(music_dev_mode_enabled(st=st))


if __name__ == "__main__":
    unittest.main()
