"""Fixed practice key family mode."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from music_theory import relative_major_of_minor, relative_minor_of_major
from practice_key_mode import (
    FIXED_PRACTICE_KEY,
    FIXED_PRACTICE_KEY_FAMILY_ID,
    MODE_FIXED,
    MODE_STANDARD,
    PRACTICE_KEY_MODE_KEY,
    PRACTICE_KEY_MODE_WIDGET_KEY,
    apply_fixed_mode_target,
    commit_practice_key_mode_widgets,
    family_option_id,
    fixed_key_family_label,
    fixed_key_family_label_for_session,
    fixed_key_family_options,
    fixed_key_family_summary_entry,
    fixed_practice_key_status_line,
    on_practice_key_mode_change,
    practice_key_mode_label,
    prepare_practice_key_mode_widgets,
    resolve_fixed_practice_concert_key,
    resolve_practice_concert_key_for_song,
    set_fixed_practice_key_family,
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
from songs.practice_key_state import resolve_practice_concert_key_for_pick
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    apply_pick_key,
    _LAST_PICK_KEY,
)

PK_PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")
PK_SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")
PK_SAY = format_pick_key("Pop", "Say — John Mayer")
PK_DAUGHTERS = format_pick_key("Pop", "Daughters — John Mayer")

CATALOG = {
    "Pop": {
        "Perfect — Ed Sheeran": {"title": "Perfect", "artist": "Ed Sheeran", "key": "G"},
        "Shape of You — Ed Sheeran": {"title": "Shape of You", "artist": "Ed Sheeran", "key": "Bm"},
        "Say — John Mayer": {"title": "Say", "artist": "John Mayer", "key": "Bb"},
        "Daughters — John Mayer": {"title": "Daughters", "artist": "John Mayer", "key": "D"},
    }
}


def _fake_st(session: dict | None = None):
    ss = session if session is not None else {}
    return MagicMock(session_state=ss)


def _fixed_session(
  family_major: str,
  family_minor: str,
  *,
  extra: dict | None = None,
) -> dict:
    option_id = family_option_id(family_major, family_minor)
    payload = {
        PRACTICE_KEY_MODE_KEY: MODE_FIXED,
        FIXED_PRACTICE_KEY_FAMILY_ID: option_id,
        FIXED_PRACTICE_KEY: family_major if family_major in {"C", "D", "E", "F", "G", "A", "B"} else family_major.replace("#", "").replace("b", ""),
        "practice_panel_fixed_practice_key": option_id,
    }
    if extra:
        payload.update(extra)
    set_fixed_practice_key_family(payload, option_id)
    return payload


class TestRelativeKeyFamily(unittest.TestCase):
    def test_practice_key_mode_labels(self) -> None:
        self.assertIn("original", practice_key_mode_label(MODE_STANDARD).lower())
        self.assertIn("key family", practice_key_mode_label(MODE_FIXED).lower())

    def test_fixed_key_family_labels_use_major_minor_wording(self) -> None:
        self.assertEqual(
            fixed_key_family_label(family_option_id("G", "E")),
            "G major / E minor",
        )
        self.assertEqual(
            fixed_key_family_label(family_option_id("C", "A")),
            "C major / A minor",
        )
        self.assertEqual(
            fixed_key_family_label(family_option_id("B", "Ab")),
            "B major / Ab minor",
        )

    def test_fixed_key_family_includes_enharmonic_choices(self) -> None:
        options = fixed_key_family_options()
        self.assertIn(family_option_id("C#", "A#"), options)
        self.assertIn(family_option_id("F#", "D#"), options)
        self.assertIn(family_option_id("G#", "F"), options)
        self.assertIn(family_option_id("A#", "G"), options)
        self.assertIn(family_option_id("D#", "C"), options)
        self.assertIn(family_option_id("B", "Ab"), options)
        self.assertIn(family_option_id("A", "Gb"), options)
        self.assertIn(family_option_id("E", "Db"), options)

    def test_fixed_key_family_summary_and_sidebar_preserve_spelling(self) -> None:
        session = _fixed_session("B", "Ab")
        self.assertEqual(
            fixed_key_family_summary_entry(session),
            "Fixed Practice Key: B major / Ab minor",
        )
        self.assertEqual(
            fixed_practice_key_status_line(session),
            "Practice Key Family: B major / Ab minor (fixed)",
        )
        self.assertEqual(
            fixed_key_family_label_for_session(session),
            "B major / Ab minor",
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

    def test_on_practice_key_mode_change_defaults_family_not_display_key(self) -> None:
        session = {
            PRACTICE_KEY_MODE_KEY: MODE_FIXED,
            "display_key": "D",
        }
        on_practice_key_mode_change(session, original_key="G")
        self.assertEqual(session[FIXED_PRACTICE_KEY], "C")
        self.assertEqual(session[FIXED_PRACTICE_KEY_FAMILY_ID], family_option_id("C", "A"))
        self.assertEqual(session[PENDING_DISPLAY_KEY], "C")


class _FakeSession(dict):
    @property
    def session_state(self):
        return self


class TestFixedModeCatalogLoad(unittest.TestCase):
    def test_daughters_in_d_major_resolves_to_g_when_fixed_g_family(self) -> None:
        st = _fake_st(
            _fixed_session(
                "G",
                "E",
                extra={
                    SELECTED_SONG_STATE_KEY: {
                        "pick_key": PK_PERFECT,
                        "title": "Perfect",
                        "artist": "Ed Sheeran",
                        "key": "G",
                    },
                    ACTIVE_CATALOG_PICK_KEY: PK_PERFECT,
                    _LAST_PICK_KEY: PK_PERFECT,
                    "display_key": "G",
                    IDENTITY_KEY: song_display_identity(
                        "Perfect", "Ed Sheeran", "G", pick_key=PK_PERFECT
                    ),
                },
            )
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_DAUGHTERS, CATALOG, skip_activity_log=True)
        self.assertEqual(st.session_state["display_key"], "G")
        self.assertEqual(st.session_state[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(
            st.session_state[FIXED_PRACTICE_KEY_FAMILY_ID],
            family_option_id("G", "E"),
        )

    def test_minor_song_resolves_to_relative_minor_side(self) -> None:
        session = _fixed_session("G", "E")
        resolved = resolve_practice_concert_key_for_song(session, "Bm", pick_key=PK_SHAPE)
        self.assertEqual(resolved, "Em")

    def test_resolve_practice_concert_key_for_pick_honors_fixed_mode(self) -> None:
        session = _fixed_session("G", "E", extra={"practice_key_by_source": {PK_DAUGHTERS: "D"}})
        resolved = resolve_practice_concert_key_for_pick(
            session,
            PK_DAUGHTERS,
            original_key="D",
        )
        self.assertEqual(resolved, "G")


class TestFixedModePersistence(unittest.TestCase):
    def test_prepare_and_commit_widget_keys(self) -> None:
        session = _fixed_session("C", "A")
        prepare_practice_key_mode_widgets(session, original_key="G")
        self.assertEqual(session[PRACTICE_KEY_MODE_WIDGET_KEY], MODE_FIXED)
        self.assertEqual(session["practice_panel_fixed_practice_key"], family_option_id("C", "A"))

        session[PRACTICE_KEY_MODE_WIDGET_KEY] = MODE_STANDARD
        commit_practice_key_mode_widgets(session)
        self.assertEqual(session[PRACTICE_KEY_MODE_KEY], MODE_STANDARD)

    def test_build_and_restore_roundtrip_keeps_fixed_mode(self) -> None:
        from music_persistent_state import apply_music_disk_state, build_music_disk_state

        source = _FakeSession(
            _fixed_session(
                "C",
                "A",
                extra={
                    "display_key": "C",
                    SELECTED_SONG_STATE_KEY: {
                        "pick_key": PK_PERFECT,
                        "title": "Perfect",
                        "artist": "Ed Sheeran",
                        "key": "G",
                    },
                    ACTIVE_CATALOG_PICK_KEY: PK_PERFECT,
                },
            )
        )
        blob = build_music_disk_state(source)
        self.assertEqual(blob["session"].get(PRACTICE_KEY_MODE_KEY), MODE_FIXED)
        self.assertEqual(blob["session"].get(FIXED_PRACTICE_KEY), "C")

        restored = _FakeSession({})
        apply_music_disk_state(
            restored,
            blob,
            song_picker_catalog=CATALOG,
            song_library=None,
            authoritative_restore=True,
        )
        self.assertEqual(restored[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(restored[FIXED_PRACTICE_KEY], "C")
        self.assertEqual(restored[PRACTICE_KEY_MODE_WIDGET_KEY], MODE_FIXED)

    def test_apply_music_disk_state_preserves_local_fixed_mode_on_stale_cloud(self) -> None:
        from music_persistent_state import apply_music_disk_state

        local = _fixed_session(
            "C",
            "A",
            extra={
                "display_key": "Am",
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_SHAPE,
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                },
                ACTIVE_CATALOG_PICK_KEY: PK_SHAPE,
            },
        )
        st = _fake_st(local)
        stale_cloud = {
            "core": {},
            "session": {
                "practice_key_mode": MODE_STANDARD,
                "display_key": "Bm",
            },
        }
        apply_music_disk_state(
            st,
            stale_cloud,
            song_picker_catalog=CATALOG,
            song_library=None,
            authoritative_restore=False,
        )
        self.assertEqual(st.session_state[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(st.session_state[FIXED_PRACTICE_KEY], "C")

    def test_music_active_song_cloud_drift_ignores_display_key_in_fixed_mode(self) -> None:
        from music_persistent_state import music_active_song_cloud_drift

        session = _fixed_session("C", "A", extra={"display_key": "Am"})
        cloud_state = {
            "core": {"display_key": "G"},
            "session": {"display_key": "G"},
            "active_song_state": {"display_key": "G"},
        }
        drift, detail = music_active_song_cloud_drift(
            _fake_st(session),
            cloud_state,
            None,
        )
        self.assertFalse(drift)
        self.assertEqual(detail, "")

    def test_song_switch_then_stale_cloud_keeps_fixed_mode(self) -> None:
        """Regression: catalog song change must not lose fixed mode on cloud resync."""
        from music_persistent_state import apply_music_disk_state

        st = _fake_st(
            _fixed_session(
                "C",
                "A",
                extra={
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
                },
            )
        )
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, skip_activity_log=True)
        self.assertEqual(st.session_state[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(st.session_state[FIXED_PRACTICE_KEY], "C")
        self.assertEqual(st.session_state["display_key"], "Am")

        stale_cloud = {
            "core": {"display_key": "G"},
            "session": {
                "practice_key_mode": MODE_STANDARD,
                "display_key": "G",
            },
        }
        apply_music_disk_state(
            st,
            stale_cloud,
            song_picker_catalog=CATALOG,
            song_library=None,
            authoritative_restore=False,
        )
        self.assertEqual(st.session_state[PRACTICE_KEY_MODE_KEY], MODE_FIXED)
        self.assertEqual(st.session_state[FIXED_PRACTICE_KEY], "C")
        prepare_practice_key_mode_widgets(st.session_state, original_key="Bm")
        self.assertEqual(
            practice_key_mode_label(st.session_state[PRACTICE_KEY_MODE_WIDGET_KEY]),
            practice_key_mode_label(MODE_FIXED),
        )
        self.assertEqual(
            st.session_state["practice_panel_fixed_practice_key"],
            family_option_id("C", "A"),
        )


class TestFixedModeSongSwitch(unittest.TestCase):
    def test_apply_pick_key_keeps_family_across_songs(self) -> None:
        st = _fake_st(
            _fixed_session(
                "D",
                "B",
                extra={
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
                },
            )
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
            _fixed_session(
                "C",
                "A",
                extra={
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
                },
            )
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
        st = _fake_st(_fixed_session("C", "A", extra={"display_key": "C"}))
        identity = song_display_identity("Shape of You", "Ed Sheeran", "Bm", pick_key=PK_SHAPE)
        apply_display_key_for_active_song(st, "Bm", identity)
        self.assertEqual(st.session_state["display_key"], "Am")

    def test_resolve_practice_concert_key_for_song_ignores_per_source_in_fixed_mode(
        self,
    ) -> None:
        session = _fixed_session(
            "D",
            "B",
            extra={"practice_key_by_source": {PK_PERFECT: "Eb"}},
        )
        resolved = resolve_practice_concert_key_for_song(session, "G", pick_key=PK_PERFECT)
        self.assertEqual(resolved, "D")

    def test_apply_fixed_mode_target(self) -> None:
        session = _fixed_session("D", "B")
        self.assertEqual(apply_fixed_mode_target(session, "G", "Bm"), "Bm")


if __name__ == "__main__":
    unittest.main()
