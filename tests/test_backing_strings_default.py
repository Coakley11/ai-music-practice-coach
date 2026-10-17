"""Strings default on; an explicit choice is saved with the workspace."""

from __future__ import annotations

import unittest


class StringsChoicePersistenceTests(unittest.TestCase):
    def test_strings_choice_is_saved_with_the_workspace(self) -> None:
        from music_persistent_state import _PERSIST_KEYS

        self.assertIn("_backing_strings_on", _PERSIST_KEYS)


if __name__ == "__main__":
    unittest.main()
