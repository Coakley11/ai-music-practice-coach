"""Fixed key family enharmonic spelling must match user selection."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from practice_key_mode import (
    FIXED_PRACTICE_KEY,
    FIXED_PRACTICE_KEY_FAMILY_ID,
    FIXED_PRACTICE_KEY_FAMILY_SPELLING,
    MODE_FIXED,
    family_metadata,
    family_option_id,
    resolve_session_key_from_family,
    set_fixed_practice_key_family,
    set_practice_key_mode,
)
from session_key_context import resolve_effective_session_key_context, sync_effective_session_keys_before_render
from songs.key_state import get_authoritative_display_key, resolve_active_musical_key


class TestKeyFamilySpelling(unittest.TestCase):
    def test_eb_c_major_resolves_eb_not_d_sharp(self) -> None:
        opt = family_option_id("Eb", "C")
        self.assertEqual(resolve_session_key_from_family(opt, "major"), "Eb")
        self.assertNotEqual(resolve_session_key_from_family(opt, "major"), "D#")

    def test_eb_c_minor_resolves_cm(self) -> None:
        opt = family_option_id("Eb", "C")
        self.assertEqual(resolve_session_key_from_family(opt, "minor"), "Cm")

    def test_flat_families(self) -> None:
        cases = [
            (family_option_id("Bb", "G"), "major", "Bb"),
            (family_option_id("Ab", "F"), "major", "Ab"),
            (family_option_id("Db", "Bb"), "major", "Db"),
        ]
        for opt, mode, expected in cases:
            with self.subTest(opt=opt):
                self.assertEqual(resolve_session_key_from_family(opt, mode), expected)

    def test_sharp_family_retains_sharp_spelling(self) -> None:
        opt = family_option_id("F#", "D#")
        self.assertEqual(resolve_session_key_from_family(opt, "major"), "F#")
        self.assertEqual(resolve_session_key_from_family(opt, "minor"), "D#m")
        self.assertEqual(family_metadata(opt)["spelling_preference"], "sharp")

    def test_set_family_persists_spelling_not_normalized_anchor(self) -> None:
        session: dict = {}
        set_practice_key_mode(session, MODE_FIXED)
        set_fixed_practice_key_family(session, family_option_id("Eb", "C"))
        self.assertEqual(session[FIXED_PRACTICE_KEY_FAMILY_ID], "Eb|C")
        self.assertEqual(session[FIXED_PRACTICE_KEY], "Eb")
        self.assertEqual(session[FIXED_PRACTICE_KEY_FAMILY_SPELLING], "flat")

    def test_stale_d_sharp_session_syncs_to_eb(self) -> None:
        session = {
            "practice_key_mode": MODE_FIXED,
            "fixed_practice_key_family_id": "Eb|C",
            "fixed_practice_key": "D#",
            "display_key": "D#",
            "instrument": "Piano",
        }
        sync_effective_session_keys_before_render(session, original_key="G")
        self.assertEqual(session["display_key"], "Eb")
        self.assertEqual(session["concert_key"], "Eb")

    def test_chart_and_backing_targets_use_eb_concert(self) -> None:
        session = {
            "practice_key_mode": MODE_FIXED,
            "fixed_practice_key_family_id": "Eb|C",
            "display_key": "D#",
            "instrument": "Piano",
        }
        ctx = resolve_effective_session_key_context(session, original_key="G", apply_to_session=True)
        self.assertEqual(ctx.resolved_tonal_key, "Eb")
        self.assertEqual(ctx.backing_target_key, "Eb")
        musical = resolve_active_musical_key(session, instrument="Piano")
        self.assertEqual(musical.practice_concert_key, "Eb")

    def test_authoritative_display_eb(self) -> None:
        session = {
            "practice_key_mode": MODE_FIXED,
            "fixed_practice_key_family_id": "Eb|C",
            "display_key": "D#",
        }
        self.assertEqual(get_authoritative_display_key(session, original_key="G"), "Eb")

    def test_restore_preserves_eb_family_id(self) -> None:
        from music_persistent_state import apply_music_disk_state

        st = MagicMock()
        st.session_state = {"display_key": "D#"}
        blob = {
            "session": {
                "practice_key_mode": MODE_FIXED,
                "fixed_practice_key_family_id": "Eb|C",
                "fixed_practice_key": "Eb",
                "fixed_practice_key_family_spelling": "flat",
            },
        }
        apply_music_disk_state(st, blob, song_picker_catalog={}, song_library={}, authoritative_restore=True)
        self.assertEqual(st.session_state.get("fixed_practice_key_family_id"), "Eb|C")
        sync_effective_session_keys_before_render(st.session_state, original_key="G")
        self.assertEqual(st.session_state.get("display_key"), "Eb")


if __name__ == "__main__":
    unittest.main()
