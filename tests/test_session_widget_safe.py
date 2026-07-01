"""Regression tests for widget-safe session hydration."""

from __future__ import annotations

import unittest

from creative_session_state import (
    apply_creative_session_to_session,
    hydrate_creative_session_for_page,
    sync_creative_session_from_session,
)
from session_widget_safe import (
    PENDING_DISPLAY_KEY,
    PENDING_IMPROV_ENTRY_MODE_KEY,
    PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY,
    apply_pending_widget_hydrates,
    reconcile_practice_key_fields,
    safe_assign_display_key,
    safe_session_assign,
    widgets_likely_instantiated,
)


def _style_jam_session(**overrides) -> dict:
    base = {
        "improv_entry_mode": "Style Jam Mode",
        "improv_style": "Bossa Nova",
        "improv_style_key": "D",
        "improv_style_bpm": 82,
        "improv_mood": "Mellow",
        "improv_groove": "Medium",
        "improv_difficulty": "Intermediate",
        "improv_generated_sections": {"Head (Bossa Nova)": ["Dm7", "G7", "Cmaj7"]},
    }
    base.update(overrides)
    return base


class TestSessionWidgetSafe(unittest.TestCase):
    def test_widgets_likely_instantiated_when_display_key_present(self) -> None:
        session = {"display_key": "C", "_music_restore_phase_complete": True}
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        self.assertTrue(widgets_likely_instantiated(session))

    def test_safe_assign_display_key_queues_pending_when_widget_locked(self) -> None:
        session = {"display_key": "C"}
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        safe_assign_display_key(session, "D", widget_safe=True)
        self.assertEqual(session.get("display_key"), "C")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "D")
        self.assertEqual(session.get("concert_key"), "D")

    def test_safe_assign_display_key_refuses_unsafe_write_when_locked(self) -> None:
        session = {"display_key": "D", "concert_key": "D"}
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        safe_assign_display_key(session, "G", widget_safe=False)
        self.assertEqual(session.get("display_key"), "D")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "G")
        self.assertEqual(session.get("concert_key"), "G")

    def test_reconcile_practice_key_fields_clears_stale_pending(self) -> None:
        session = {"display_key": "D", "concert_key": "D", PENDING_DISPLAY_KEY: "G"}
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        reconcile_practice_key_fields(session, authoritative="E")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "E")
        self.assertEqual(session.get("concert_key"), "E")

    def test_song_picker_source_queues_pending_when_widget_locked(self) -> None:
        from session_widget_safe import PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, safe_session_assign

        session = {
            "song_picker_active_source": "Use Catalog Song Backing",
            "display_key": "E",
        }
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        safe_session_assign(session, "song_picker_active_source", "Use Custom Progression Backing", widget_safe=True)
        self.assertEqual(session.get("song_picker_active_source"), "Use Catalog Song Backing")
        self.assertEqual(
            session.get(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY),
            "Use Custom Progression Backing",
        )

    def test_safe_session_assign_queues_improv_entry_mode(self) -> None:
        session = {"display_key": "C", "improv_entry_mode": "Style Jam Mode"}
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        safe_session_assign(session, "improv_entry_mode", "Jam Session Generator", widget_safe=True)
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(session.get("_pending_improv_entry_mode"), "Jam Session Generator")

    def test_hydrate_creative_session_for_page_does_not_mutate_display_key(self) -> None:
        session = _style_jam_session(display_key="Bm", concert_key="Bm")
        sync_creative_session_from_session(session)
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        hydrate_creative_session_for_page(session)
        self.assertEqual(session.get("display_key"), "Bm")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "D")
        self.assertEqual(session.get("improv_style_key"), "D")

    def test_apply_with_widget_safe_false_sets_display_key(self) -> None:
        session: dict = {}
        sess = sync_creative_session_from_session(_style_jam_session())
        assert sess is not None
        apply_creative_session_to_session(session, sess, widget_safe=False)
        self.assertEqual(session.get("display_key"), "D")

    def test_apply_pending_widget_hydrates_overwrites_stale_entry_mode(self) -> None:
        from session_widget_safe import PENDING_IMPROV_ENTRY_MODE_KEY

        session = {"improv_entry_mode": "Song-Based Improvisation"}
        session[PENDING_IMPROV_ENTRY_MODE_KEY] = "Style Jam Mode"
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")
        self.assertNotIn(PENDING_IMPROV_ENTRY_MODE_KEY, session)

    def test_sync_live_keys_queues_improv_style_key_when_widget_locked(self) -> None:
        from backing_context import build_entry_jam_context, set_backing_context, sync_live_keys_from_backing_context
        from session_widget_safe import PENDING_IMPROV_STYLE_KEY

        session = _style_jam_session(display_key="G", concert_key="G", improv_style_key="G")
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        ctx = build_entry_jam_context({**session, "improv_style_key": "F"})
        set_backing_context(session, ctx)
        sync_live_keys_from_backing_context(session)
        self.assertEqual(session.get("concert_key"), "F")
        self.assertEqual(session.get("improv_style_key"), "G")
        self.assertEqual(session.get(PENDING_IMPROV_STYLE_KEY), "F")


if __name__ == "__main__":
    unittest.main()
