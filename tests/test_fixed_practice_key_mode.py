"""Fixed practice key family mode."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from music_theory import relative_major_of_minor, relative_minor_of_major
from practice_key_mode import (
    FIXED_PRACTICE_KEY,
    MODE_FIXED,
    MODE_STANDARD,
    PRACTICE_KEY_MODE_KEY,
    apply_fixed_mode_target,
    fixed_key_family_label,
    fixed_key_family_options,
    fixed_key_family_summary_entry,
    on_practice_key_mode_change,
    practice_key_mode_label,
    resolve_fixed_practice_concert_key,
    resolve_practice_concert_key_for_song,
)
from song_catalog.catalog import format_pick_key
from songs.key_state import (
    IDENTITY_KEY,
    PENDING_DISPLAY_KEY,
    apply_display_key_for_active_song,
    invalidate_backing_cache,
    request_display_key,
    song_display_identity,
)
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    apply_pick_key,
    _LAST_PICK_KEY,
)

PK_PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")
PK_SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")
PK_SAY = format_pick_key("Pop", "Say — John Mayer")

CATALOG = {
    "Pop": {
        "Perfect — Ed Sheeran": {"title": "Perfect", "artist": "Ed Sheeran", "key": "G"},
        "Shape of You — Ed Sheeran": {"title": "Shape of You", "artist": "Ed Sheeran", "key": "Bm"},
        "Say — John Mayer": {"title": "Say", "artist": "John Mayer", "key": "Bb"},
    }
}


def _fake_st(session: dict | None = None):
    ss = session if session is not None else {}
    return MagicMock(session_state=ss)


class TestRelativeKeyFamily(unittest.TestCase):
    def test_practice_key_mode_labels(self) -> None:
        self.assertIn("original", practice_key_mode_label(MODE_STANDARD).lower())
        self.assertIn("key family", practice_key_mode_label(MODE_FIXED).lower())

    def test_fixed_key_family_labels(self) -> None:
        labels = [fixed_key_family_label(k) for k in fixed_key_family_options()]
        self.assertEqual(
            labels,
            [
                "C / A minor",
                "Db / Bb minor",
                "D / B minor",
                "Eb / C minor",
                "E / C# minor",
                "F / D minor",
                "Gb / Eb minor",
                "G / E minor",
                "Ab / F minor",
                "A / F# minor",
                "Bb / G minor",
                "B / G# minor",
            ],
        )

    def test_fixed_key_family_summary_only_when_enabled(self) -> None:
        self.assertEqual(fixed_key_family_summary_entry({PRACTICE_KEY_MODE_KEY: MODE_STANDARD}), "")
        self.assertEqual(
            fixed_key_family_summary_entry(
                {PRACTICE_KEY_MODE_KEY: MODE_FIXED, FIXED_PRACTICE_KEY: "C"}
            ),
            "Fixed Practice Key: C / A minor",
        )

    def test_relative_minor_of_d_major(self) -> None:
        self.assertEqual(relative_minor_of_major("D"), "Bm")

    def test_relative_major_of_b_minor(self) -> None:
        self.assertEqual(relative_major_of_minor("Bm"), "D")

    def test_relative_minor_of_c_major(self) -> None:
        self.assertEqual(relative_minor_of_major("C"), "Am")

    def test_relative_major_of_g_minor(self) -> None:
        self.assertEqual(relative_major_of_minor("Gm"), "Bb")


class TestFixedPracticeKeyResolution(unittest.TestCase):
    def test_d_major_family_major_songs(self) -> None:
        self.assertEqual(resolve_fixed_practice_concert_key("D", "G"), "D")
        self.assertEqual(resolve_fixed_practice_concert_key("D", "Bb"), "D")

    def test_d_major_family_minor_songs(self) -> None:
        self.assertEqual(resolve_fixed_practice_concert_key("D", "Bm"), "Bm")

    def test_c_major_family_minor_songs(self) -> None:
        self.assertEqual(resolve_fixed_practice_concert_key("C", "Bm"), "Am")

    def test_g_minor_family(self) -> None:
        self.assertEqual(resolve_fixed_practice_concert_key("Gm", "Bm"), "Gm")
        self.assertEqual(resolve_fixed_practice_concert_key("Gm", "G"), "Bb")


class TestSessionDictHelpers(unittest.TestCase):
    def test_request_display_key_writes_session_dict(self) -> None:
        session: dict = {}
        request_display_key(session, "D")
        self.assertEqual(session[PENDING_DISPLAY_KEY], "D")

    def test_invalidate_backing_cache_accepts_session_dict(self) -> None:
        session = {"_last_backing_wav": b"x", "current_chord_timeline": [1]}
        invalidate_backing_cache(session)
        self.assertNotIn("_last_backing_wav", session)
        self.assertNotIn("current_chord_timeline", session)

    def test_on_practice_key_mode_change_with_session_dict(self) -> None:
        session = {
            PRACTICE_KEY_MODE_KEY: MODE_FIXED,
            "display_key": "D",
        }
        on_practice_key_mode_change(session, original_key="G")
        self.assertEqual(session[FIXED_PRACTICE_KEY], "D")
        self.assertEqual(session[PENDING_DISPLAY_KEY], "D")


class TestFixedModeSongSwitch(unittest.TestCase):
    def test_apply_pick_key_keeps_family_across_songs(self) -> None:
        st = _fake_st(
            {
                PRACTICE_KEY_MODE_KEY: MODE_FIXED,
                FIXED_PRACTICE_KEY: "D",
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_PERFECT,
                    "title": "Perfect",
                    "artist": "Ed Sheeran",
                    "key": "G",
                },
                ACTIVE_CATALOG_PICK_KEY: PK_PERFECT,
                _LAST_PICK_KEY: PK_PERFECT,
                "display_key": "D",
                IDENTITY_KEY: song_display_identity(
                    "Perfect", "Ed Sheeran", "G", pick_key=PK_PERFECT
                ),
            }
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, skip_activity_log=True)
        self.assertEqual(st.session_state["display_key"], "Bm")
        self.assertEqual(st.session_state[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(st.session_state[FIXED_PRACTICE_KEY], "D")

        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SAY, CATALOG, skip_activity_log=True)
        self.assertEqual(st.session_state["display_key"], "D")
        self.assertEqual(st.session_state[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(st.session_state[FIXED_PRACTICE_KEY], "D")

    def test_c_family_stays_enabled_and_resolves_major_and_minor_song_switches(self) -> None:
        st = _fake_st(
            {
                PRACTICE_KEY_MODE_KEY: MODE_FIXED,
                FIXED_PRACTICE_KEY: "C",
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_PERFECT,
                    "title": "Perfect",
                    "artist": "Ed Sheeran",
                    "key": "G",
                },
                ACTIVE_CATALOG_PICK_KEY: PK_PERFECT,
                _LAST_PICK_KEY: PK_PERFECT,
                "display_key": "C",
                IDENTITY_KEY: song_display_identity(
                    "Perfect", "Ed Sheeran", "G", pick_key=PK_PERFECT
                ),
            }
        )

        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, skip_activity_log=True)
        self.assertEqual(st.session_state[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(st.session_state[FIXED_PRACTICE_KEY], "C")
        self.assertEqual(st.session_state["display_key"], "Am")

        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SAY, CATALOG, skip_activity_log=True)
        self.assertEqual(st.session_state[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(st.session_state[FIXED_PRACTICE_KEY], "C")
        self.assertEqual(st.session_state["display_key"], "C")

    def test_standard_mode_follows_song_key(self) -> None:
        st = _fake_st(
            {
                PRACTICE_KEY_MODE_KEY: MODE_STANDARD,
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_PERFECT,
                    "title": "Perfect",
                    "artist": "Ed Sheeran",
                    "key": "G",
                },
                ACTIVE_CATALOG_PICK_KEY: PK_PERFECT,
                _LAST_PICK_KEY: PK_PERFECT,
                "display_key": "D",
                IDENTITY_KEY: song_display_identity(
                    "Perfect", "Ed Sheeran", "G", pick_key=PK_PERFECT
                ),
            }
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SAY, CATALOG, skip_activity_log=True)
        self.assertEqual(st.session_state["display_key"], "Bb")

    def test_apply_display_key_for_active_song_uses_fixed_family(self) -> None:
        st = _fake_st(
            {
                PRACTICE_KEY_MODE_KEY: MODE_FIXED,
                FIXED_PRACTICE_KEY: "C",
                "display_key": "C",
            }
        )
        identity = song_display_identity("Shape of You", "Ed Sheeran", "Bm", pick_key=PK_SHAPE)
        apply_display_key_for_active_song(st, "Bm", identity)
        self.assertEqual(st.session_state["display_key"], "Am")

    def test_resolve_practice_concert_key_for_song_ignores_per_source_in_fixed_mode(
        self,
    ) -> None:
        session = {
            PRACTICE_KEY_MODE_KEY: MODE_FIXED,
            FIXED_PRACTICE_KEY: "D",
            "practice_key_by_source": {PK_PERFECT: "Eb"},
        }
        resolved = resolve_practice_concert_key_for_song(session, "G", pick_key=PK_PERFECT)
        self.assertEqual(resolved, "D")

    def test_apply_fixed_mode_target(self) -> None:
        session = {PRACTICE_KEY_MODE_KEY: MODE_FIXED, FIXED_PRACTICE_KEY: "D"}
        self.assertEqual(apply_fixed_mode_target(session, "G", "Bm"), "Bm")


if __name__ == "__main__":
    unittest.main()
