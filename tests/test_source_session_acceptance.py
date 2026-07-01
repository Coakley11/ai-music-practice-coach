"""Acceptance tests for source-session bucket model (Creative/SBI/practice key)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from song_catalog.catalog import format_pick_key
from songs.key_state import apply_display_key_for_active_song, song_display_identity
from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY
from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY
from source_session_state import (
    CATALOG_SESSION_KEY,
    CUSTOM_SESSION_KEY,
    SBI_PREVIEW_SOURCE_KEY,
    resolve_sbi_preview,
    set_sbi_preview_source,
)
from studio_page_state import (
    apply_improv_song_source,
    ensure_improv_entry_mode_restored,
    resolve_improv_song_preview,
    resolve_improv_song_source,
    sync_improv_song_source_for_handoff,
)


def _shape_pick() -> str:
    return format_pick_key("Pop", "Shape of You")


def _shape_catalog_session() -> dict:
    pick = _shape_pick()
    return {
        "pick_key": pick,
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": pick,
        },
        "original_key": "Bm",
        "display_key": "Bm",
    }


class TestAcceptancePracticeKeyRefresh(unittest.TestCase):
    """1. Shape Bm → Am → refresh → stays Am."""

    def test_same_song_refresh_preserves_practice_key(self) -> None:
        pick = _shape_pick()
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Am"},
        }
        st = SimpleNamespace(session_state=session)
        identity = song_display_identity("Shape of You", "Ed Sheeran", "Bm", pick_key=pick)
        apply_display_key_for_active_song(st, "Bm", identity)
        self.assertEqual(session.get("display_key"), "Am")


class TestAcceptanceCreativeModeRefresh(unittest.TestCase):
    """2–3. Style Jam / Jam Session settings survive refresh."""

    def test_style_jam_mode_survives_refresh(self) -> None:
        from creative_session_state import CREATIVE_SESSION_KEY, CreativeSession, get_creative_session

        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "E",
            "improv_style": "Bossa Nova",
            "improv_mood": "Mellow",
            CREATIVE_SESSION_KEY: CreativeSession(
                session_id="test-style-jam",
                tool_type="entry_style_jam",
                entry_mode="Style Jam Mode",
                concert_key="E",
                display_key="E",
                style="Bossa Nova",
                mood="Mellow",
            ).to_dict(),
        }
        entry = ensure_improv_entry_mode_restored(session)
        self.assertEqual(entry, "Style Jam Mode")
        sess = get_creative_session(session)
        self.assertIsNotNone(sess)
        assert sess is not None
        self.assertEqual(sess.entry_mode, "Style Jam Mode")
        self.assertEqual(sess.concert_key, "E")

    def test_jam_session_generator_survives_refresh(self) -> None:
        from creative_session_state import CREATIVE_SESSION_KEY, CreativeSession

        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "Eb",
            "improv_jam_style": "Blues",
            "improv_jam_mood": "Dark",
            "improv_jam_session": {"sections": {"Jam": ["Eb7", "Ab7"]}},
            CREATIVE_SESSION_KEY: CreativeSession(
                session_id="test-jam-session",
                tool_type="jam_session_generator",
                entry_mode="Jam Session Generator",
                concert_key="Eb",
                display_key="Eb",
                style="Blues",
                mood="Dark",
                sections={"Jam": ["Eb7", "Ab7"]},
            ).to_dict(),
        }
        entry = ensure_improv_entry_mode_restored(session)
        self.assertEqual(entry, "Jam Session Generator")
        self.assertEqual(session.get("improv_jam_key"), "Eb")
        self.assertEqual(session.get("improv_jam_style"), "Blues")
        self.assertEqual(session.get("improv_jam_mood"), "Dark")


class TestAcceptanceSbiPreviewIsolation(unittest.TestCase):
    """4–7. SBI preview never mixes catalog/custom identities."""

    def _mixed_global_session(self) -> dict:
        pick = _shape_pick()
        return {
            "improv_song_source": "Active song",
            SBI_PREVIEW_SOURCE_KEY: "Active song",
            "active_catalog_pick_key": "custom::trial-1",
            "selected_song": {"title": "Trial Song", "key": "D", "pick_key": "custom::trial-1"},
            "display_key": "E",
            CATALOG_BEFORE_CUSTOM_KEY: _shape_catalog_session(),
            CATALOG_SESSION_KEY: _shape_catalog_session(),
            CUSTOM_SESSION_KEY: {
                "pick_key": "custom::trial-1",
                "title": "Trial Song",
                "artist": "Custom progression",
                "original_key": "D",
                "display_key": "E",
                "sections": {"Verse": ["E", "B", "C#m", "A"]},
            },
            PRACTICE_KEY_BY_SOURCE_KEY: {
                pick: "Am",
                "custom::trial-1": "E",
            },
        }

    def test_sbi_active_song_shows_shape_title_key(self) -> None:
        preview = resolve_sbi_preview(self._mixed_global_session())
        self.assertEqual(preview["title"], "Shape of You")
        self.assertEqual(preview["display_key"], "Am")
        self.assertEqual(preview["source"], "Active song")

    def test_sbi_custom_shows_trial_song_identity(self) -> None:
        session = self._mixed_global_session()
        set_sbi_preview_source(session, "Custom progression")
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview["title"], "Trial Song")
        self.assertEqual(preview["display_key"], "E")
        self.assertEqual(preview["sections"], {"Verse": ["E", "B", "C#m", "A"]})

    def test_switch_back_to_active_song_restores_shape(self) -> None:
        session = self._mixed_global_session()
        set_sbi_preview_source(session, "Custom progression")
        self.assertEqual(resolve_sbi_preview(session)["title"], "Trial Song")
        set_sbi_preview_source(session, "Active song")
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview["title"], "Shape of You")
        self.assertEqual(preview["display_key"], "Am")

    def test_no_mixed_title_and_custom_progression(self) -> None:
        session = self._mixed_global_session()
        preview = resolve_improv_song_preview(session)
        self.assertEqual(preview["title"], "Shape of You")
        self.assertNotEqual(preview["title"], "Trial Song")
        self.assertEqual(preview["display_key"], "Am")
        self.assertNotIn("Trial Song", str(preview.get("sections", {})))

    def test_preview_toggle_does_not_mutate_global_ownership(self) -> None:
        session = self._mixed_global_session()
        apply_improv_song_source(
            session,
            "Custom progression",
            set_catalog_source=lambda _s: None,
            set_custom_source=lambda _s: None,
            widget_safe=True,
        )
        self.assertEqual(session["active_catalog_pick_key"], "custom::trial-1")
        self.assertEqual(session["selected_song"]["title"], "Trial Song")
        self.assertEqual(resolve_improv_song_source(session), "Custom progression")

    def test_handoff_back_to_active_restores_catalog(self) -> None:
        from songs.music_source import SOURCE_CATALOG

        session = self._mixed_global_session()
        set_sbi_preview_source(session, "Active song")

        def _set_catalog(ss: dict) -> None:
            ss["active_music_source"] = SOURCE_CATALOG

        sync_improv_song_source_for_handoff(
            session,
            "Active song",
            set_catalog_source=_set_catalog,
            set_custom_source=lambda _s: None,
        )
        self.assertEqual(session["active_catalog_pick_key"], _shape_pick())
        self.assertEqual(session["song"], "Shape of You")


if __name__ == "__main__":
    unittest.main()
