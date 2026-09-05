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


def _lock_widgets(session: dict) -> None:
    from music_restore_phase import STREAMLIT_WIDGETS_LOCKED_KEY, complete_music_restore_phase

    complete_music_restore_phase(session)
    session[STREAMLIT_WIDGETS_LOCKED_KEY] = True


class TestSessionWidgetSafe(unittest.TestCase):
    def test_widgets_not_locked_from_display_key_alone(self) -> None:
        session = {"display_key": "C"}
        _lock_widgets(session)
        session.pop("_streamlit_widgets_locked_this_run", None)
        self.assertFalse(widgets_likely_instantiated(session))

    def test_widgets_likely_instantiated_when_lock_flag_set(self) -> None:
        session = {"display_key": "C"}
        _lock_widgets(session)
        self.assertTrue(widgets_likely_instantiated(session))

    def test_safe_assign_display_key_writes_directly_before_widgets(self) -> None:
        session = {"display_key": "C"}
        safe_assign_display_key(session, "D", widget_safe=True)
        self.assertEqual(session.get("display_key"), "D")
        self.assertNotIn(PENDING_DISPLAY_KEY, session)
        self.assertEqual(session.get("concert_key"), "D")

    def test_safe_assign_display_key_queues_pending_when_widget_locked(self) -> None:
        session = {"display_key": "C"}
        _lock_widgets(session)
        safe_assign_display_key(session, "D", widget_safe=True)
        self.assertEqual(session.get("display_key"), "C")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "D")
        self.assertEqual(session.get("concert_key"), "D")

    def test_safe_assign_display_key_refuses_unsafe_write_when_locked(self) -> None:
        session = {"display_key": "D", "concert_key": "D"}
        _lock_widgets(session)
        safe_assign_display_key(session, "G", widget_safe=False)
        self.assertEqual(session.get("display_key"), "D")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "G")
        self.assertEqual(session.get("concert_key"), "G")

    def test_reconcile_practice_key_fields_writes_directly_before_widgets(self) -> None:
        session = {"display_key": "D", "concert_key": "D", PENDING_DISPLAY_KEY: "G"}
        reconcile_practice_key_fields(session, authoritative="E")
        self.assertEqual(session.get("display_key"), "E")
        self.assertNotIn(PENDING_DISPLAY_KEY, session)
        self.assertEqual(session.get("concert_key"), "E")

    def test_reconcile_practice_key_fields_queues_pending_when_locked(self) -> None:
        session = {"display_key": "D", "concert_key": "D", PENDING_DISPLAY_KEY: "G"}
        _lock_widgets(session)
        reconcile_practice_key_fields(session, authoritative="E")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "E")
        self.assertEqual(session.get("concert_key"), "E")

    def test_song_picker_source_queues_pending_when_widget_locked(self) -> None:
        from session_widget_safe import PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, safe_session_assign

        session = {
            "song_picker_active_source": "Use Catalog Song Backing",
            "display_key": "E",
        }
        _lock_widgets(session)
        safe_session_assign(session, "song_picker_active_source", "Use Custom Progression Backing", widget_safe=True)
        self.assertEqual(session.get("song_picker_active_source"), "Use Catalog Song Backing")
        self.assertEqual(
            session.get(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY),
            "Use Custom Progression Backing",
        )

    def test_safe_session_assign_queues_improv_entry_mode(self) -> None:
        session = {"display_key": "C", "improv_entry_mode": "Style Jam Mode"}
        _lock_widgets(session)
        safe_session_assign(session, "improv_entry_mode", "Jam Session Generator", widget_safe=True)
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(session.get("_pending_improv_entry_mode"), "Jam Session Generator")

    def test_safe_session_assign_queues_transposing_instrument_when_locked(self) -> None:
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
        from session_widget_safe import PENDING_TRANSPOSING_INSTRUMENT_KEY, PENDING_WIDGET_ASSIGN_DIAG_KEY

        session = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)"}
        _lock_widgets(session)
        safe_session_assign(session, SELECTED_TRANSPOSING_INSTRUMENT_KEY, "Tenor saxophone (Bb)", widget_safe=True)
        self.assertEqual(session.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY), "Alto saxophone (Eb)")
        self.assertEqual(session.get(PENDING_TRANSPOSING_INSTRUMENT_KEY), "Tenor saxophone (Bb)")
        diag = session.get(PENDING_WIDGET_ASSIGN_DIAG_KEY) or {}
        self.assertEqual(diag.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY, {}).get("pending_key"), PENDING_TRANSPOSING_INSTRUMENT_KEY)

    def test_safe_session_assign_queues_unknown_widget_key_when_locked(self) -> None:
        from session_widget_safe import PENDING_WIDGET_ASSIGN_DIAG_KEY

        session = {"custom_widget_key": "old"}
        _lock_widgets(session)
        safe_session_assign(session, "custom_widget_key", "new", widget_safe=True)
        self.assertEqual(session.get("custom_widget_key"), "old")
        self.assertEqual(session.get("_pending_widget_custom_widget_key"), "new")
        diag = session.get(PENDING_WIDGET_ASSIGN_DIAG_KEY) or {}
        self.assertIn("custom_widget_key", diag)

    def test_hydrate_creative_session_for_page_does_not_mutate_display_key(self) -> None:
        session = _style_jam_session(display_key="Bm", concert_key="Bm")
        sync_creative_session_from_session(session)
        _lock_widgets(session)
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

    def test_apply_pending_picker_drops_reclaim_keeps_catalog_bounce(self) -> None:
        """Lagging Catalog/Composition reclaim must not snap leave radios.

        Catalog→Composition pending must still apply (Catalog bounce mid-leave).
        """
        from songs.music_source import (
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            song_picker_composition_option_label,
        )

        comp = song_picker_composition_option_label()

        # Composition ensure must not reclaim over live Custom.
        session = {
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY: comp,
        }
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CUSTOM)
        self.assertNotIn(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, session)

        # Catalog seed must not reclaim over live Custom.
        session = {
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
        }
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CUSTOM)
        self.assertNotIn(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, session)

        # Catalog seed must not reclaim over live Composition.
        session = {
            "song_picker_active_source": comp,
            PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
        }
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("song_picker_active_source"), comp)
        self.assertNotIn(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, session)

        # Catalog bounce: pending Composition may replace live Catalog.
        session = {
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY: comp,
        }
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("song_picker_active_source"), comp)
        self.assertNotIn(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY, session)

    def test_apply_pending_when_locked_keeps_display_key_pending(self) -> None:
        session = {"display_key": "G", "concert_key": "G", PENDING_DISPLAY_KEY: "F"}
        _lock_widgets(session)
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("display_key"), "G")
        self.assertEqual(session.get("concert_key"), "F")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "F")

    def test_apply_pending_before_widgets_writes_display_key(self) -> None:
        session = {"display_key": "G", "concert_key": "G", PENDING_DISPLAY_KEY: "F"}
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("display_key"), "F")
        self.assertEqual(session.get("concert_key"), "F")
        self.assertNotIn(PENDING_DISPLAY_KEY, session)

    def test_apply_pending_when_locked_keeps_entry_mode_pending(self) -> None:
        session = {
            "display_key": "G",
            "improv_entry_mode": "Song-Based Improvisation",
            PENDING_IMPROV_ENTRY_MODE_KEY: "Style Jam Mode",
        }
        _lock_widgets(session)
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("improv_entry_mode"), "Song-Based Improvisation")
        self.assertEqual(session.get(PENDING_IMPROV_ENTRY_MODE_KEY), "Style Jam Mode")

    def test_sync_live_keys_queues_improv_style_key_when_widget_locked(self) -> None:
        from backing_context import build_entry_jam_context, set_backing_context, sync_live_keys_from_backing_context
        from session_widget_safe import PENDING_IMPROV_STYLE_KEY

        session = _style_jam_session(display_key="G", concert_key="G", improv_style_key="G")
        _lock_widgets(session)
        ctx = build_entry_jam_context({**session, "improv_style_key": "F"})
        set_backing_context(session, ctx)
        sync_live_keys_from_backing_context(session)
        self.assertEqual(session.get("concert_key"), "F")
        self.assertEqual(session.get("improv_style_key"), "G")
        self.assertEqual(session.get(PENDING_IMPROV_STYLE_KEY), "F")


if __name__ == "__main__":
    unittest.main()
