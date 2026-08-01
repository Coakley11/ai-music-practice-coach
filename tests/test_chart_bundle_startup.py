"""Bounded chart bundle startup recovery."""

from __future__ import annotations

import unittest

from music_theory import transpose_sections
from song_catalog.catalog import format_pick_key
from songs.chart_bundle_startup import (
    CHART_BUNDLE_RECOVERY_MAX,
    chart_bundle_recovery_exhausted,
    clear_chart_bundle_recovery_state,
    prepare_catalog_song_for_chart_bundle,
    run_chart_bundle_automatic_recovery,
)
from songs.music_source import build_active_chart_bundle_for_app
from songs.state import ACTIVE_CATALOG_PICK_KEY, get_song_context


def _mini_catalog() -> dict:
    return {
        "Pop": {
            "Perfect — Ed Sheeran": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "key": "G",
                "sections": {"Verse 1": ["G", "Em7", "Cadd9", "D/F#"]},
            },
        }
    }


class _FakeSt:
    def __init__(self, session_state: dict) -> None:
        self.session_state = session_state


class ChartBundleStartupRecoveryTests(unittest.TestCase):
    def test_prepare_hydrates_partial_selected_song_from_cloud_pick(self) -> None:
        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        st = _FakeSt(
            {
                ACTIVE_CATALOG_PICK_KEY: "",
                "selected_song": {
                    "title": "Perfect",
                    "artist": "Ed Sheeran",
                    "genre": "Pop",
                    "sections": {"Verse 1": ["G"]},
                },
                "active_song_state": {"pick_key": perfect_pk},
                "_suite_last_cloud_fetch_payload": {"core": {"pick_key": perfect_pk}},
            }
        )
        g, title, data = prepare_catalog_song_for_chart_bundle(
            st,
            "Pop",
            "Perfect",
            dict(st.session_state["selected_song"]),
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        self.assertEqual(data.get("key"), "G")
        self.assertEqual(str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or ""), perfect_pk)
        self.assertTrue(g)
        self.assertTrue(title)

    def test_automatic_recovery_bounded_then_exhausted(self) -> None:
        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        session = {
            ACTIVE_CATALOG_PICK_KEY: "",
            "selected_song": {"title": "Perfect", "sections": {"Verse 1": ["G"]}},
            "active_song_state": {"pick_key": perfect_pk},
        }
        st = _FakeSt(session)
        self.assertTrue(
            run_chart_bundle_automatic_recovery(
                st, song_picker_catalog=catalog, song_library=catalog
            )
        )
        self.assertTrue(
            run_chart_bundle_automatic_recovery(
                st, song_picker_catalog=catalog, song_library=catalog
            )
        )
        self.assertTrue(chart_bundle_recovery_exhausted(session))
        self.assertFalse(
            run_chart_bundle_automatic_recovery(
                st, song_picker_catalog=catalog, song_library=catalog
            )
        )
        self.assertEqual(int(session.get("_chart_bundle_recovery_attempts") or 0), CHART_BUNDLE_RECOVERY_MAX)

    def test_startup_partial_session_builds_after_prepare(self) -> None:
        from chart_level_arrangement import sections_for_level as _sections_for_level

        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        st = _FakeSt(
            {
                ACTIVE_CATALOG_PICK_KEY: "",
                "selected_song": {
                    "title": "Perfect",
                    "sections": {"Verse 1": ["G", "Em7"]},
                },
                "active_song_state": {"pick_key": perfect_pk},
            }
        )
        partial = dict(st.session_state["selected_song"])
        g, title, data = prepare_catalog_song_for_chart_bundle(
            st,
            "Pop",
            "Perfect",
            partial,
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        bundle = build_active_chart_bundle_for_app(
            st.session_state,
            catalog_genre=g,
            catalog_song=title,
            catalog_song_data=data,
            level="Advanced",
            display_key="C",
            cpl_active_key="cpl_active_progression",
            sections_for_level=_sections_for_level,
            transpose_sections=transpose_sections,
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        self.assertEqual(bundle["original_key"], "G")
        self.assertNotEqual(format_pick_key("Pop", "Say — Artist"), perfect_pk)
        clear_chart_bundle_recovery_state(st.session_state)

    def test_get_song_context_after_reconcile_not_say_fallback(self) -> None:
        catalog = _mini_catalog()
        say_pk = format_pick_key("Pop", "Say — Artist")
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        self.assertNotEqual(say_pk, perfect_pk)
        st = _FakeSt(
            {
                ACTIVE_CATALOG_PICK_KEY: "",
                "selected_song": {"title": "Perfect", "sections": {"Verse 1": ["G"]}},
                "active_song_state": {"pick_key": perfect_pk},
                "_music_workspace_blob_hydrated": True,
            }
        )
        prepare_catalog_song_for_chart_bundle(
            st,
            "Pop",
            "Perfect",
            dict(st.session_state["selected_song"]),
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        _g, _t, data = get_song_context(
            st,
            song_library=catalog,
            song_picker_catalog=catalog,
        )
        self.assertEqual(data.get("key"), "G")
        self.assertEqual(str(st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or ""), perfect_pk)


if __name__ == "__main__":
    unittest.main()
