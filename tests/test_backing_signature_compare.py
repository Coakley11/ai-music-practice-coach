"""A JSON-restored backing signature (nested lists) still matches the live tuple."""

from __future__ import annotations

import unittest

from songs.key_state import backing_signatures_equal


class SignatureCompareTests(unittest.TestCase):
    def test_json_restored_signature_matches_live_tuple(self) -> None:
        live = ("Perfect", "A", "Intermediate", "Pop groove", 95, "4/4", 2, ("Verse", "Chorus"), "Strong", False, (), 94, 94, 0, "arr_v3")
        restored = ["Perfect", "A", "Intermediate", "Pop groove", 95, "4/4", 2, ["Verse", "Chorus"], "Strong", False, [], 94, 94, 0, "arr_v3"]
        self.assertTrue(backing_signatures_equal(restored, live))
        self.assertFalse(backing_signatures_equal(restored, live[:-1] + ("arr_v3+strings",)))
        self.assertTrue(backing_signatures_equal(None, None))
        self.assertFalse(backing_signatures_equal(None, live))


if __name__ == "__main__":
    unittest.main()
