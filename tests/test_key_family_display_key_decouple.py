"""Fixed key family must not follow display-key / written-key side effects."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from practice_key_mode import (
    FIXED_PRACTICE_KEY_FAMILY_ID,
    MODE_FIXED,
    family_option_id,
    on_fixed_practice_concert_key_change,
    resolve_family_option_id,
    resolve_fixed_practice_concert_key_for_session,
    set_fixed_practice_key_family,
    set_practice_key_mode,
)
from songs.key_state import mark_display_key_changed


def _fixed_c_a(session: dict) -> None:
    set_practice_key_mode(session, MODE_FIXED)
    set_fixed_practice_key_family(session, family_option_id("C", "A"))


class TestDisplayKeyDoesNotRewriteFamily(unittest.TestCase):
    def test_on_fixed_practice_concert_key_change_is_noop(self) -> None:
        session: dict = {}
        _fixed_c_a(session)
        on_fixed_practice_concert_key_change(session, "D#")
        self.assertEqual(session[FIXED_PRACTICE_KEY_FAMILY_ID], family_option_id("C", "A"))

    def test_mark_display_key_changed_keeps_family(self) -> None:
        st = MagicMock()
        st.session_state = {
            "practice_key_mode": MODE_FIXED,
            FIXED_PRACTICE_KEY_FAMILY_ID: family_option_id("C", "A"),
            "practice_panel_fixed_practice_key": family_option_id("C", "A"),
            "display_key": "D#",
        }
        mark_display_key_changed(st)
        self.assertEqual(
            st.session_state[FIXED_PRACTICE_KEY_FAMILY_ID],
            family_option_id("C", "A"),
        )

    def test_resolve_session_does_not_mutate_family(self) -> None:
        session: dict = {}
        _fixed_c_a(session)
        before = session[FIXED_PRACTICE_KEY_FAMILY_ID]
        self.assertEqual(resolve_fixed_practice_concert_key_for_session(session, "G"), "C")
        self.assertEqual(resolve_fixed_practice_concert_key_for_session(session, "Am"), "Am")
        self.assertEqual(session[FIXED_PRACTICE_KEY_FAMILY_ID], before)
        self.assertEqual(resolve_family_option_id(session), family_option_id("C", "A"))


class TestNormalizeLegacyFamilyLabel(unittest.TestCase):
    def test_resolve_accepts_major_minor_label(self) -> None:
        from practice_key_mode import normalize_stored_family_option_id

        session = {
            "practice_key_mode": MODE_FIXED,
            "fixed_practice_key_family_id": "C major/A minor",
        }
        norm = normalize_stored_family_option_id(session["fixed_practice_key_family_id"])
        self.assertEqual(norm, family_option_id("C", "A"))


if __name__ == "__main__":
    unittest.main()
