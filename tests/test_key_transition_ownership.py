"""Key ownership: practice→backing preserve vs creative→catalog reset."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import BACKING_CONTEXT_KEY, get_backing_context, restore_regular_song_backing
from backing_source_navigation import (
    BACKING_INTENT_FROM_PRACTICE,
    BACKING_INTENT_FROM_SONG_TO_BACKING,
    hydrate_backing_source_for_page,
    hydrate_picker_source_for_page,
    open_backing_for_practice_source,
    set_backing_open_intent,
    set_key_transition_intent,
)
from creative_key_sync import should_use_live_practice_key_sidebar
from creative_session_state import creative_session_is_active, get_creative_session
from music_source_ownership import activate_catalog_ownership


class TestKeyTransitionOwnership(unittest.TestCase):
    def _photograph_session(self, *, practice_key: str = "E") -> dict:
        return {
            "active_catalog_pick_key": "photo|artist",
            "selected_song": {"title": "Photograph", "key": "E", "pick_key": "photo|artist", "bpm": 108},
            "song": "Photograph",
            "display_key": practice_key,
            "concert_key": practice_key,
            "user_catalog_source_choice": True,
            "active_music_source": "catalog",
            "instrument": "Guitar",
            "backing_track_bpm": 108,
            "backing_groove_style": "Pop groove",
        }

    def test_practice_to_backing_preserves_changed_practice_key(self) -> None:
        session = self._photograph_session(practice_key="F#")
        st_like = SimpleNamespace(session_state=session)
        set_key_transition_intent(session, BACKING_INTENT_FROM_SONG_TO_BACKING)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = open_backing_for_practice_source(session, st_like=st_like)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(session.get("display_key"), "F#")
        self.assertEqual(session.get("concert_key"), "F#")
        self.assertEqual(getattr(ctx, "concert_key", None), "F#")

    def test_activate_catalog_ownership_preserve_practice_key(self) -> None:
        session = self._photograph_session(practice_key="F#")
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = activate_catalog_ownership(session, st_like=st_like, preserve_practice_key=True)
        self.assertIsNotNone(ctx)
        self.assertEqual(session.get("display_key"), "F#")
        self.assertEqual(session.get("concert_key"), "F#")

    def test_jam_session_to_catalog_resets_to_original_key(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "selected_song": {"title": "Say", "key": "G", "pick_key": "say|artist", "bpm": 98},
            "song": "Say",
            "display_key": "D",
            "concert_key": "D",
            "user_catalog_source_choice": True,
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "D",
            "improv_jam_session": {"sections": {"A": ["Dmaj7", "Gmaj7"]}},
            "creative_session": {
                "tool_type": "jam_session_generator",
                "entry_mode": "Jam Session Generator",
                "concert_key": "D",
                "display_key": "Eb",
                "sections": {"A": ["Dmaj7", "Gmaj7"]},
            },
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "entry_mode": "Jam Session Generator",
                "active_song_id": "jam",
                "song_title": "Jam Session",
                "key": "D",
                "display_key": "D",
                "concert_key": "D",
                "bpm": 120,
                "style": "Bossa Nova",
                "groove": "Medium",
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(session.get("display_key"), "G")
        self.assertEqual(session.get("concert_key"), "G")
        self.assertEqual(ctx.song_title, "Say")
        self.assertFalse(creative_session_is_active(session))
        self.assertIsNotNone(get_creative_session(session))
        diag = session.get("_key_transition_diag") or session.get("_catalog_backing_restore_diag") or {}
        self.assertEqual(str(diag.get("catalog_original_key") or ""), "G")
        self.assertEqual(str(diag.get("catalog_target_key") or ""), "G")

    def test_should_not_use_live_practice_key_for_catalog_backing(self) -> None:
        session = {
            "studio_page": "backing",
            "user_catalog_source_choice": True,
            BACKING_CONTEXT_KEY: {
                "source": "regular_song",
                "song_title": "Say",
                "key": "G",
                "concert_key": "G",
                "display_key": "G",
                "bpm": 98,
                "groove": "Medium",
            },
        }
        self.assertFalse(should_use_live_practice_key_sidebar(session))

    def test_from_practice_intent_sets_song_to_backing_transition(self) -> None:
        session = self._photograph_session(practice_key="Bm")
        set_backing_open_intent(session, BACKING_INTENT_FROM_PRACTICE)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            hydrate_backing_source_for_page(session, st_like=st_like)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(session.get("display_key"), "Bm")

    def test_creative_to_picker_resets_catalog_original_key(self) -> None:
        from backing_context import BACKING_PREF_CREATIVE, get_backing_source_preference
        from backing_source_navigation import hydrate_picker_source_for_page

        shape_pick = "Pop::Shape of You"
        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": shape_pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": shape_pick, "bpm": 96},
            "song": "Shape of You",
            "display_key": "F#",
            "concert_key": "F#",
            "user_catalog_source_choice": True,
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "F#",
            "improv_generated_sections": {"Style Jam": ["F#maj7", "Bmaj7"]},
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "jam",
                "song_title": "Style Jam",
                "key": "F#",
                "display_key": "F#",
                "concert_key": "F#",
                "bpm": 120,
                "style": "Bossa Nova",
                "groove": "Medium",
            },
        }
        try:
            from backing_context import set_backing_source_preference

            set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        except ImportError:
            pass
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            hydrate_picker_source_for_page(session, st_like=st_like)
        self.assertEqual(session.get("display_key"), "Bm")
        self.assertEqual(session.get("concert_key"), "Bm")
        try:
            self.assertNotEqual(get_backing_source_preference(session), BACKING_PREF_CREATIVE)
        except ImportError:
            pass

    def test_use_catalog_backing_restores_pre_creative_song_not_last_catalog_snapshot(self) -> None:
        from backing_context import restore_regular_song_backing
        from songs.music_source import LAST_CATALOG_STATE_KEY

        in_my_life_pick = "Pop::In My Life"
        say_pick = "Pop::Say"
        session = {
            "active_catalog_pick_key": in_my_life_pick,
            "selected_song": {"title": "In My Life", "key": "A", "pick_key": in_my_life_pick, "bpm": 100},
            "song": "In My Life",
            "display_key": "Eb",
            "concert_key": "Eb",
            "user_catalog_source_choice": True,
            "backing_track_bpm": 82,
            LAST_CATALOG_STATE_KEY: {
                "pick_key": say_pick,
                "selected_song": {"title": "Say", "key": "G", "pick_key": say_pick, "bpm": 82},
                "original_key": "G",
                "display_key": "G",
            },
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "Eb",
            "improv_jam_bpm": 82,
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "entry_mode": "Jam Session Generator",
                "active_song_id": "jam",
                "song_title": "Jam Session",
                "key": "Eb",
                "display_key": "Eb",
                "concert_key": "Eb",
                "bpm": 82,
                "style": "Blues",
                "groove": "Medium",
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.song_title, "In My Life")
        self.assertEqual(session.get("display_key"), "A")
        self.assertEqual(session.get("concert_key"), "A")
        self.assertEqual(getattr(ctx, "concert_key", None), "A")
        self.assertNotEqual(str(session.get("song") or ""), "Say")

    def test_catalog_rebuild_forces_bpm_when_sync_id_unchanged(self) -> None:
        from music_source_ownership import rebuild_catalog_backing_from_canonical_pick
        from songs.playback_defaults import _CANONICAL_BACKING_ID_KEY, active_song_sync_id, playback_song_id

        in_my_life_pick = "Pop::In My Life"
        pid = playback_song_id(is_custom=False, song_title="In My Life", song_artist="The Beatles")
        sync_id = active_song_sync_id(pick_key=in_my_life_pick, playback_song_id=pid, is_custom=False)
        session = {
            "active_catalog_pick_key": in_my_life_pick,
            "selected_song": {"title": "In My Life", "key": "A", "pick_key": in_my_life_pick, "bpm": 100},
            "song": "In My Life",
            "display_key": "A",
            "concert_key": "A",
            "user_catalog_source_choice": True,
            "backing_track_bpm": 82,
            "bpm": 82,
            _CANONICAL_BACKING_ID_KEY: sync_id,
            "last_backing_defaults_song_id": sync_id,
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = rebuild_catalog_backing_from_canonical_pick(
                session,
                st_like=st_like,
                pick_key=in_my_life_pick,
                reset_to_original=True,
            )
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(int(ctx.bpm or 0), 100)
        self.assertEqual(int(session.get("backing_track_bpm") or session.get("bpm") or 0), 100)
        self.assertEqual(int(session.get("catalog_rebuild_result_bpm") or 0), 100)


if __name__ == "__main__":
    unittest.main()
