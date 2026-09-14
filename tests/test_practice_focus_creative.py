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


class _FakeSessionState:
    """Streamlit SessionState is mapping-like but not a dict."""

    def __init__(self, data: dict) -> None:
        object.__setattr__(self, "_data", dict(data))

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data


class TestLiveSessionStateIsAuthoritative(unittest.TestCase):
    def test_non_dict_session_state_follows_live_focus(self) -> None:
        raw = {
            "instrument": "Piano",
            "focus": "Voicings",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "song": "Shape of You",
            "selected_song": {"title": "Shape of You"},
            "cpl_active_progression": {
                "name": "My Progression",
                "id": "trial-live-1",
                "original_key_center": "C",
                "original_sections": {"Verse": [{"chord": "C", "bars": 4}]},
            },
        }
        session = _FakeSessionState(raw)
        self.assertNotIsInstance(session, dict)
        set_active_focus(session, "Dynamics")
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Dynamics", caption)
        self.assertNotIn("Voicings", caption)
        self.assertIn("My Progression", caption)
        self.assertNotIn("Catalog song", caption)
        ctx = resolve_creative_practice_focus(session)
        self.assertEqual(ctx["focus"], "Dynamics")
        self.assertEqual(ctx["identity"], "My Progression")

    def test_switching_focus_does_not_change_source_or_key(self) -> None:
        session = {
            "instrument": "Piano",
            "focus": "Voicings",
            "display_key": "C",
            "concert_key": "C",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "ii_selected_section": "Verse",
            "cpl_active_progression": {
                "name": "My Progression",
                "id": "trial-live-2",
                "original_key_center": "C",
                "original_sections": {"Verse": [{"chord": "C", "bars": 4}]},
            },
        }
        first = resolve_creative_practice_focus(session)
        set_active_focus(session, "Dynamics")
        second = resolve_creative_practice_focus(session)
        self.assertEqual(first["identity"], second["identity"])
        self.assertEqual(first["kind"], second["kind"])
        self.assertEqual(session.get("display_key"), "C")
        self.assertEqual(session.get("ii_selected_section"), "Verse")
        self.assertNotEqual(first["focus"], second["focus"])
        self.assertNotEqual(first["emphasis"], second["emphasis"])


class TestPracticeFocusGeneratedOutput(unittest.TestCase):
    def test_motif_coaching_changes_with_focus(self) -> None:
        from motif_engine import generate_musical_phrase

        voicings = {
            "instrument": "Piano",
            "focus": "Voicings",
        }
        dynamics = {
            "instrument": "Piano",
            "focus": "Dynamics",
        }
        set_active_focus(voicings, "Voicings")
        set_active_focus(dynamics, "Dynamics")
        a = generate_musical_phrase("C", key_center="C", level="Intermediate", session_state=voicings)
        b = generate_musical_phrase("C", key_center="C", level="Intermediate", session_state=dynamics)
        self.assertEqual(a.get("practice_focus"), "Voicings")
        self.assertEqual(b.get("practice_focus"), "Dynamics")
        self.assertIn("Voicings", str(a.get("practice_focus_coaching") or a.get("variation_prompt") or ""))
        self.assertIn("Dynamics", str(b.get("practice_focus_coaching") or b.get("variation_prompt") or ""))
        self.assertNotEqual(a.get("practice_focus_coaching"), b.get("practice_focus_coaching"))
        self.assertEqual(a.get("chord"), b.get("chord"))

    def test_mission_steps_include_current_focus(self) -> None:
        from improvisation_missions import _practice_steps

        voice = _practice_steps("Improvise using only chord tones", "Intermediate", "Piano", focus="Voicings")
        dyn = _practice_steps("Improvise using only chord tones", "Intermediate", "Piano", focus="Dynamics")
        self.assertTrue(any("Voicings" in s for s in voice))
        self.assertTrue(any("Dynamics" in s for s in dyn))
        self.assertNotEqual(voice[0], dyn[0])

    def test_piano_practice_mode_hint_follows_focus(self) -> None:
        from instrument_aware import instrument_practice_mode_hint

        session = {"instrument": "Piano", "focus": "Dynamics"}
        set_active_focus(session, "Dynamics")
        hint = instrument_practice_mode_hint("Piano", session)
        self.assertIn("Dynamics", hint)
        self.assertNotIn("Voicings · LH/RH", hint)

