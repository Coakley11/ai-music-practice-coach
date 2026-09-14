"""Practice Focus on Creative pages follows the current source, not a previous owner."""

from __future__ import annotations

import unittest

from practice_focus_creative import (
    creative_focus_matches_source,
    format_creative_practice_focus_caption,
    resolve_creative_practice_focus,
    resolve_creative_source_binding,
)
from practice_setup_globals import set_active_focus, set_active_instrument


class TestCreativePracticeFocusBinding(unittest.TestCase):
    def test_custom_does_not_keep_catalog_identity(self) -> None:
        session = {
            "instrument": "Piano",
            "focus": "Voicings",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "song": "Shape of You",
            "selected_song": {"title": "Shape of You", "artist": "Ed Sheeran"},
            "active_catalog_pick_key": "Pop\x1fShape of You",
            "cpl_active_progression": {
                "name": "My Progression",
                "id": "trial-focus-1",
                "original_key_center": "C#",
                "original_sections": {"Verse": [{"chord": "C#", "bars": 2}]},
            },
        }
        set_active_instrument(session, "Piano")
        set_active_focus(session, "Voicings")
        bind = resolve_creative_source_binding(session)
        self.assertEqual(bind["kind"], "custom")
        self.assertEqual(bind["identity"], "My Progression")
        self.assertNotEqual(bind["identity"], "Shape of You")
        ctx = resolve_creative_practice_focus(session)
        self.assertEqual(ctx["focus"], "Voicings")
        self.assertEqual(ctx["kind"], "custom")
        self.assertEqual(ctx["identity"], "My Progression")
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Voicings", caption)
        self.assertIn("My Progression", caption)
        self.assertNotIn("Shape of You", caption)
        self.assertTrue(
            creative_focus_matches_source(
                session, expected_kind="custom", expected_identity="My Progression"
            )
        )

    def test_style_jam_binding_is_not_catalog(self) -> None:
        session = {
            "instrument": "Piano",
            "focus": "Voicings",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Jazz Swing",
            "song": "Shape of You",
            "selected_song": {"title": "Shape of You"},
        }
        bind = resolve_creative_source_binding(session)
        self.assertEqual(bind["kind"], "entry_jam")
        self.assertEqual(bind["identity"], "Jazz Swing")
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Jazz Swing", caption)
        self.assertNotIn("Shape of You", caption)

    def test_switching_focus_changes_overlay_not_identity(self) -> None:
        session = {
            "instrument": "Guitar",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "song": "Shape of You",
            "selected_song": {"title": "Shape of You"},
        }
        set_active_instrument(session, "Guitar")
        set_active_focus(session, "Strumming")
        first = resolve_creative_practice_focus(session)
        set_active_focus(session, "Melody")
        second = resolve_creative_practice_focus(session)
        self.assertEqual(first["identity"], second["identity"])
        self.assertEqual(first["kind"], "catalog")
        self.assertNotEqual(first["focus"], second["focus"])
        self.assertNotEqual(first["emphasis"], second["emphasis"])

    def test_catalog_song_card_prose_is_not_used(self) -> None:
        session = {
            "instrument": "Piano",
            "focus": "Voicings",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "song": "Shape of You",
            "selected_song": {
                "title": "Shape of You",
                "practice_focus": "core chord changes · rhythm feel · clean transitions",
            },
            "cpl_active_progression": {
                "name": "Trial Song",
                "id": "trial-focus-2",
                "original_key_center": "E",
                "original_sections": {"A": [{"chord": "E", "bars": 4}]},
            },
        }
        caption = format_creative_practice_focus_caption(session)
        self.assertNotIn("core chord changes", caption)
        self.assertIn("Trial Song", caption)
        self.assertIn("Voicings", caption)
