"""Chart bundle must resolve canonical original key before transposing sections."""

from __future__ import annotations

import unittest
from unittest import mock

from music_theory import (
    MissingOriginalSongKeyError,
    chart_bundle_cache_signature,
    transpose_sections,
)
from song_catalog.catalog import format_pick_key
from songs.music_source import (
    build_active_chart_bundle,
    build_active_chart_bundle_for_app,
    resolve_catalog_song_for_chart,
)
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
            "Say — Artist": {
                "title": "Say",
                "artist": "Artist",
                "key": "C",
                "sections": {"Verse": ["C", "G"]},
            },
        }
    }


class ChartSongKeyResolverTests(unittest.TestCase):
    def test_normal_catalog_bundle_has_key(self) -> None:
        catalog = _mini_catalog()
        song_data = dict(catalog["Pop"]["Perfect — Ed Sheeran"])
        bundle = build_active_chart_bundle(
            {ACTIVE_CATALOG_PICK_KEY: format_pick_key("Pop", "Perfect — Ed Sheeran")},
            catalog_genre="Pop",
            catalog_song="Perfect — Ed Sheeran",
            catalog_song_data=song_data,
            level="Advanced",
            display_key="C",
            cpl_active_key="cpl_active_progression",
            sections_for_level=lambda data, _lvl: dict(data.get("sections") or {}),
            transpose_sections=transpose_sections,
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        self.assertEqual(bundle["original_key"], "G")
        self.assertEqual(bundle["sections"]["Verse 1"][0], "C")

    def test_partial_selected_song_sections_without_key_hydrates_from_pick(self) -> None:
        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        partial = {
            "pick_key": perfect_pk,
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "sections": {"Verse 1": ["G", "Em7"]},
        }
        merged, original = resolve_catalog_song_for_chart(
            {
                ACTIVE_CATALOG_PICK_KEY: perfect_pk,
                "selected_song": partial,
            },
            partial,
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        self.assertEqual(original, "G")
        self.assertEqual(merged["key"], "G")

    def test_partial_without_key_or_pick_raises_domain_error(self) -> None:
        partial = {"title": "Perfect", "sections": {"Verse": ["G"]}}
        session: dict = {"selected_song": partial}
        with self.assertRaises(MissingOriginalSongKeyError):
            resolve_catalog_song_for_chart(
                session,
                partial,
                song_picker_catalog=_mini_catalog(),
                song_library=_mini_catalog(),
            )
        self.assertIn("_chart_song_resolve_diag", session)

    def test_canonical_original_key_field_not_key(self) -> None:
        from music_theory import resolve_original_song_key

        self.assertEqual(resolve_original_song_key({"original_key": "Eb"}), "Eb")

    def test_resolve_from_catalog_session_when_picker_row_lacks_key(self) -> None:
        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        partial = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "sections": {"Verse 1": ["G"]},
        }
        picker_row = dict(catalog["Pop"]["Perfect — Ed Sheeran"])
        picker_row.pop("key", None)
        catalog_no_key = {"Pop": {"Perfect — Ed Sheeran": picker_row}}
        session = {
            ACTIVE_CATALOG_PICK_KEY: perfect_pk,
            "selected_song": partial,
            "catalog_session": {"pick_key": perfect_pk, "original_key": "G"},
        }
        _merged, original = resolve_catalog_song_for_chart(
            session,
            partial,
            song_picker_catalog=catalog_no_key,
            song_library=catalog_no_key,
        )
        self.assertEqual(original, "G")

    def test_stale_pick_title_genre_fallback(self) -> None:
        catalog = _mini_catalog()
        session = {
            ACTIVE_CATALOG_PICK_KEY: "Pop|Stale Label",
            "selected_song": {"title": "Perfect", "artist": "Ed Sheeran", "genre": "Pop"},
        }
        _merged, original = resolve_catalog_song_for_chart(
            session,
            {},
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        self.assertEqual(original, "G")

    def test_deferred_restore_context_does_not_return_sections_only_without_key(self) -> None:
        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        st = type("St", (), {})()
        st.session_state = {
            ACTIVE_CATALOG_PICK_KEY: "",
            "selected_song": {
                "pick_key": perfect_pk,
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "sections": {"Verse 1": ["G"]},
            },
            "_music_workspace_blob_hydrated": False,
            "_suite_persist_restore_applied": True,
        }

        class _FakeSt:
            session_state = st.session_state

        with mock.patch(
            "music_restore_phase.authoritative_restore_in_progress",
            return_value=True,
        ), mock.patch(
            "music_restore_phase.music_restore_phase_complete",
            return_value=False,
        ):
            ctx = get_song_context(
                _FakeSt(),
                song_library=catalog,
                song_picker_catalog=catalog,
            )
        self.assertIsNotNone(ctx)
        _genre, _title, data = ctx
        self.assertEqual(data.get("key"), "G")

    def test_perfect_fixed_practice_c_transposes_from_g_not_c(self) -> None:
        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        partial_overlay = {
            "title": "Perfect",
            "sections": {"Verse 1": ["G", "Em7"]},
        }
        bundle = build_active_chart_bundle(
            {
                ACTIVE_CATALOG_PICK_KEY: perfect_pk,
                "selected_song": {"pick_key": perfect_pk, **partial_overlay},
            },
            catalog_genre="Pop",
            catalog_song="Perfect",
            catalog_song_data=partial_overlay,
            level="Advanced",
            display_key="C",
            cpl_active_key="cpl_active",
            sections_for_level=lambda data, _lvl: dict(data.get("sections") or {}),
            transpose_sections=transpose_sections,
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        self.assertEqual(bundle["original_key"], "G")
        self.assertEqual(bundle["sections"]["Verse 1"][0], "C")

    def test_custom_progression_missing_key_center_still_has_home_key(self) -> None:
        from songs.music_source import SOURCE_CUSTOM

        active = {
            "name": "My prog",
            "original_sections": {"A": {"chords": ["C", "G"]}},
            "original_key_center": "D",
        }
        bundle = build_active_chart_bundle(
            {
                "active_music_source": SOURCE_CUSTOM,
                "cpl_active_progression": active,
            },
            catalog_genre="Pop",
            catalog_song="Stale",
            catalog_song_data={"key": "G", "sections": {}},
            level="Advanced",
            display_key="F",
            cpl_active_key="cpl_active_progression",
            sections_for_level=lambda data, _lvl: dict(data.get("sections") or {}),
            transpose_sections=transpose_sections,
        )
        self.assertEqual(bundle["original_key"], "D")

    def test_custom_without_key_center_raises_domain_error(self) -> None:
        from songs.music_source import SOURCE_CUSTOM

        active = {"name": "My prog", "original_sections": {"A": {"chords": ["C"]}}}
        session = {
            "active_music_source": SOURCE_CUSTOM,
            "cpl_active_progression": active,
        }
        with mock.patch("songs.music_source.custom_original_key", return_value=""):
            with self.assertRaises(MissingOriginalSongKeyError):
                build_active_chart_bundle(
                    session,
                    catalog_genre="Pop",
                    catalog_song="X",
                    catalog_song_data={"sections": {}},
                    level="Advanced",
                    display_key="C",
                    cpl_active_key="cpl_active_progression",
                    sections_for_level=lambda data, _lvl: dict(data.get("sections") or {}),
                    transpose_sections=transpose_sections,
                )


    def test_startup_partial_selected_song_cloud_pick_builds_via_cache(self) -> None:
        """Reproduces deploy failure: sections-only selected_song, empty live pick, cloud identity."""
        from studio_cache import session_cache_get_or_set

        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        session: dict = {
            ACTIVE_CATALOG_PICK_KEY: "",
            "selected_song": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "sections": {"Verse 1": ["G", "Em7"]},
            },
            "active_song_state": {"pick_key": perfect_pk},
            "_music_workspace_blob_hydrated": True,
            "_music_startup_restore_finalized": True,
            "_music_active_pick_key_reconciled": False,
        }
        partial_overlay = dict(session["selected_song"])
        sig_before = (
            "",
            chart_bundle_cache_signature(
                session,
                partial_overlay,
                song_picker_catalog=catalog,
            ),
            "catalog",
        )

        def _factory() -> dict:
            return build_active_chart_bundle(
                session,
                catalog_genre="Pop",
                catalog_song="Perfect",
                catalog_song_data=partial_overlay,
                level="Advanced",
                display_key="C",
                cpl_active_key="cpl_active",
                sections_for_level=lambda data, _lvl: dict(data.get("sections") or {}),
                transpose_sections=transpose_sections,
                song_picker_catalog=catalog,
                song_library=catalog,
            )

        bundle = session_cache_get_or_set(session, "chart_bundle", sig_before, _factory)
        self.assertEqual(bundle["original_key"], "G")
        self.assertEqual(bundle["sections"]["Verse 1"][0], "C")

        session[ACTIVE_CATALOG_PICK_KEY] = perfect_pk
        session["_music_active_pick_key_reconciled"] = True
        sig_after = (
            perfect_pk,
            chart_bundle_cache_signature(
                session,
                partial_overlay,
                song_picker_catalog=catalog,
            ),
            "catalog",
        )
        self.assertNotEqual(sig_before, sig_after)
        bundle2 = session_cache_get_or_set(session, "chart_bundle", sig_after, _factory)
        self.assertEqual(bundle2["original_key"], "G")

    def test_factory_style_call_via_build_active_chart_bundle_for_app(self) -> None:
        from chart_level_arrangement import sections_for_level as _sections_for_level

        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        session: dict = {
            ACTIVE_CATALOG_PICK_KEY: "",
            "selected_song": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "sections": {"Verse 1": ["G", "Em7"]},
            },
            "active_song_state": {"pick_key": perfect_pk},
        }
        partial = dict(session["selected_song"])
        bundle = build_active_chart_bundle_for_app(
            session,
            catalog_genre="Pop",
            catalog_song="Perfect",
            catalog_song_data=partial,
            level="Advanced",
            display_key="C",
            cpl_active_key="cpl_active_progression",
            sections_for_level=_sections_for_level,
            transpose_sections=transpose_sections,
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        self.assertEqual(bundle["original_key"], "G")
        self.assertIn("_reconcile_song_library", session)
        self.assertIn("_catalog_backup_library", session)


if __name__ == "__main__":
    unittest.main()
