"""Canonical Creative session persistence and restore."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import get_backing_context, open_backing_from_creative
from creative_session_state import (
    CREATIVE_SESSION_KEY,
    apply_creative_session_to_session,
    creative_session_is_active,
    get_creative_session,
    hydrate_creative_session_after_restore,
    resolve_creative_backing_sections,
    sync_creative_session_from_session,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state


def _style_jam_session(**overrides) -> dict:
    base = {
        "active_catalog_pick_key": "shape|edsheeran",
        "song": "Shape of You",
        "display_key": "Bm",
        "concert_key": "Bm",
        "improv_entry_mode": "Style Jam Mode",
        "improv_style": "Bossa Nova",
        "improv_style_key": "D",
        "improv_style_bpm": 82,
        "improv_mood": "Mellow",
        "improv_groove": "Medium",
        "improv_difficulty": "Intermediate",
        "improv_style_meta": {"style": "Bossa Nova", "bpm": 82, "groove": "Medium", "key": "D"},
        "improv_generated_sections": {"Head (Bossa Nova)": ["Dm7", "G7", "Cmaj7"]},
        "studio_page": "creative",
    }
    base.update(overrides)
    return base


class TestCreativeSessionState(unittest.TestCase):
    def test_sync_captures_entry_style_jam(self) -> None:
        session = _style_jam_session()
        sess = sync_creative_session_from_session(session)
        assert sess is not None
        self.assertEqual(sess.tool_type, "entry_style_jam")
        self.assertEqual(sess.concert_key, "D")
        self.assertIn("Head (Bossa Nova)", sess.sections)

    def test_apply_restores_entry_mode_and_sections(self) -> None:
        session = _style_jam_session()
        sess = sync_creative_session_from_session(session)
        assert sess is not None
        session.clear()
        apply_creative_session_to_session(session, sess)
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(session.get("improv_style_key"), "D")
        self.assertIn("Head (Bossa Nova)", session.get("improv_generated_sections", {}))

    def test_disk_roundtrip_preserves_style_jam_not_catalog(self) -> None:
        session = _style_jam_session()
        sync_creative_session_from_session(session)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        blob = build_music_disk_state(SimpleNamespace(session_state=session))
        restored: dict = {}
        st2 = SimpleNamespace(session_state=restored)
        apply_music_disk_state(st2, blob, song_picker_catalog={}, song_library={})
        self.assertIn(CREATIVE_SESSION_KEY, restored)
        self.assertTrue(creative_session_is_active(restored))
        self.assertEqual(restored.get("improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(restored.get("improv_style_key"), "D")
        ctx = get_backing_context(restored)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "entry_jam")

    def test_resolve_sections_for_playback(self) -> None:
        session = _style_jam_session(display_key="E", concert_key="E")
        sync_creative_session_from_session(session)
        sections = resolve_creative_backing_sections(session)
        self.assertIn("Head (Bossa Nova)", sections)
        flat = " ".join(sections["Head (Bossa Nova)"])
        self.assertIn("Em7", flat)

    def test_hydrate_reapplies_widgets(self) -> None:
        session = _style_jam_session()
        sess = sync_creative_session_from_session(session)
        assert sess is not None
        bare = {CREATIVE_SESSION_KEY: sess.to_dict()}
        self.assertTrue(hydrate_creative_session_after_restore(bare))
        self.assertEqual(bare.get("improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(bare.get("improv_style_key"), "D")


if __name__ == "__main__":
    unittest.main()
