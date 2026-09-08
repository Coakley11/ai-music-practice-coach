"""SBI Custom Practice Key must write LAST_CUSTOM pick, not Global Active catalog."""
from __future__ import annotations

import unittest

from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import (
    get_practice_concert_key,
    resolve_settings_pick_for_write,
    set_practice_concert_key,
)


class TestSbiCustomPracticeKeyOwner(unittest.TestCase):
    def test_custom_sbi_backing_pk_does_not_contaminate_catalog(self) -> None:
        shape = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_catalog_pick_key": shape,
            "practice_key_by_source": {shape: "Dbm"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "active": {
                    "id": "trial-sbi-1",
                    "name": "Trial Song",
                    "original_key_center": "C",
                },
            },
        }
        write_pick = resolve_settings_pick_for_write(session)
        self.assertTrue(str(write_pick).startswith("custom::"), write_pick)
        set_practice_concert_key(session, "Eb")
        self.assertEqual(get_practice_concert_key(session, shape), "Dbm")
        self.assertEqual(get_practice_concert_key(session, write_pick), "Eb")

    def test_songs_page_sidebar_pk_persists_catalog_sticky(self) -> None:
        """Songs (non-Creative) Practice Key change must stick on the catalog pick."""
        from creative_key_sync import sync_sidebar_creative_concert_key

        shape = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            "studio_page": "songs",
            "display_key": "Dm",
            "concert_key": "Bm",
            "active_catalog_pick_key": shape,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": shape},
            "practice_key_by_source": {shape: "Bm"},
            "improv_intelligence_tab": "",
            "improv_entry_mode": "",
        }
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(get_practice_concert_key(session, shape), "Dm")
        self.assertEqual(session.get("concert_key"), "Dm")

    def test_reconcile_rejects_custom_live_bleed_onto_catalog(self) -> None:
        from music_workflow_song_practice import reconcile_catalog_practice_key_owner

        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"
        session = {
            "studio_page": "songs",
            "display_key": "E",  # leftover Custom / Backing live
            "concert_key": "E",
            "active_catalog_pick_key": shape,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": shape},
            "practice_key_by_source": {shape: "Dm", custom: "E"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "custom_home_key": "D",
                "active": {"id": "trial-1", "name": "Trial Song", "original_key_center": "D"},
            },
        }
        chosen = reconcile_catalog_practice_key_owner(session, source="test_bleed")
        self.assertEqual(chosen, "Dm")
        self.assertEqual(get_practice_concert_key(session, shape), "Dm")

    def test_on_global_display_key_change_does_not_write_catalog_during_sbi_custom(self) -> None:
        from custom_progression_lab import on_global_display_key_change

        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"
        session = {
            "studio_page": "creative",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "improv_entry_mode": "Song-Based Improvisation",
            "active_catalog_pick_key": shape,
            "practice_key_by_source": {shape: "Dm", custom: "D"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "custom_home_key": "D",
                "active": {"id": "trial-1", "name": "Trial Song", "original_key_center": "D"},
            },
        }
        on_global_display_key_change(session, "Eb")
        self.assertEqual(get_practice_concert_key(session, shape), "Dm")
        # Creative CASE B: visit PK must not mutate LAST_CUSTOM.
        self.assertEqual(get_practice_concert_key(session, custom), "D")

    def test_case_b_creative_sbi_c_does_not_write_last_custom_cm(self) -> None:
        """Shape/Bm GA + Trial/D: SBI Custom C stays visit-only C major, not LAST_CUSTOM Cm."""
        from creative_key_sync import sync_sidebar_creative_concert_key
        from songs.key_state import normalize_sidebar_display_key
        from source_session_state import (
            coerce_token_to_custom_home_mode,
            sbi_custom_visit_is_local_only,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_music_source": "catalog",
            "active_catalog_pick_key": shape,
            "display_key": "C",
            "concert_key": "D",
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": shape},
            "practice_key_by_source": {shape: "Bm", custom: "D"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "custom_home_key": "D",
                "active": {
                    "id": "trial-1",
                    "name": "Trial Song",
                    "original_key_center": "D",
                },
            },
        }
        self.assertTrue(sbi_custom_visit_is_local_only(session))
        self.assertEqual(normalize_sidebar_display_key(session, "C"), "C")
        self.assertEqual(coerce_token_to_custom_home_mode(session, "C"), "C")
        self.assertNotEqual(coerce_token_to_custom_home_mode(session, "C"), "Cm")
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(get_practice_concert_key(session, custom), "D")
        self.assertEqual(get_practice_concert_key(session, shape), "Bm")
        self.assertEqual(str(session.get("_sbi_custom_visit_pk") or ""), "C")
        self.assertNotEqual(str(session.get("display_key") or "").lower(), "cm")
        self.assertNotEqual(str(session.get("cpl_last_display_key") or "").lower(), "cm")

    def test_open_custom_lab_after_sbi_c_restores_d_not_cm(self) -> None:
        """CASE B visit C must not seed Custom Lab as C minor; home D wins."""
        from types import SimpleNamespace

        from custom_progression_lab import (
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET,
            prepare_custom_workspace_sidebar_display_key,
            start_new_progression,
            apply_cpl_session_progression,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"
        session = {
            "studio_page": "custom",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_music_source": "catalog",
            "active_catalog_pick_key": shape,
            "display_key": "C",
            "concert_key": "C",
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": shape},
            "practice_key_by_source": {shape: "Bm", custom: "D"},
            "_sbi_custom_last_visit_pk": "C",
            CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET: "C",
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "custom_home_key": "D",
                "active": {
                    "id": "trial-1",
                    "name": "Trial Song",
                    "original_key_center": "D",
                },
            },
        }
        song = start_new_progression()
        song["id"] = "trial-1"
        song["name"] = "Trial Song"
        song["original_key_center"] = "D"
        song["user_locked_home_key"] = True
        apply_cpl_session_progression(session, song, reset_display_key=False)
        session["practice_key_by_source"][custom] = "D"
        session["_cpl_force_pk_to_home"] = "D"
        st = SimpleNamespace(session_state=session)
        prepare_custom_workspace_sidebar_display_key(st, session)
        pk = str(
            session.get(CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET)
            or session.get("display_key")
            or ""
        )
        self.assertTrue(pk.startswith("D"), pk)
        self.assertNotEqual(pk.lower(), "cm")
        self.assertEqual(get_practice_concert_key(session, custom), "D")
        self.assertEqual(get_practice_concert_key(session, shape), "Bm")

    def test_custom_page_pk_edit_still_persists_last_custom(self) -> None:
        """Ordinary Custom-page Practice Key edits outside CASE B still persist."""
        from custom_progression_lab import (
            apply_cpl_session_progression,
            start_new_progression,
            sync_custom_workspace_practice_key,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"
        session = {
            "studio_page": "custom",
            "active_music_source": "catalog",
            "active_catalog_pick_key": shape,
            "practice_key_by_source": {shape: "Bm", custom: "D"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "custom_home_key": "D",
                "active": {"id": "trial-1", "name": "Trial Song", "original_key_center": "D"},
            },
        }
        song = start_new_progression()
        song["id"] = "trial-1"
        song["name"] = "Trial Song"
        song["original_key_center"] = "D"
        song["user_locked_home_key"] = True
        apply_cpl_session_progression(session, song, reset_display_key=False)
        sync_custom_workspace_practice_key(session, practice_key="E", active=song)
        self.assertEqual(get_practice_concert_key(session, custom), "E")
        self.assertEqual(get_practice_concert_key(session, shape), "Bm")

    def test_case_a_sbi_custom_pk_still_writes_last_custom(self) -> None:
        """When Custom is Global Active, SBI Custom PK still updates LAST_CUSTOM."""
        from creative_key_sync import sync_sidebar_creative_concert_key
        from songs.music_source import SOURCE_CUSTOM
        from source_session_state import sbi_custom_visit_is_local_only

        custom = "custom::trial-1"
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": custom,
            "display_key": "E",
            "concert_key": "D",
            "practice_key_by_source": {custom: "D"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "custom_home_key": "D",
                "active": {"id": "trial-1", "name": "Trial Song", "original_key_center": "D"},
            },
        }
        self.assertFalse(sbi_custom_visit_is_local_only(session))
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(get_practice_concert_key(session, custom), "E")

    def test_catalog_does_not_own_sidebar_when_sbi_custom(self) -> None:
        from musical_context_authority import catalog_song_should_own_sidebar_practice_key

        shape = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_catalog_pick_key": shape,
            "display_key": "Dm",
            "practice_key_by_source": {shape: "Dm"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "active": {
                    "id": "trial-sbi-1",
                    "name": "Trial Song",
                    "original_key_center": "D",
                },
            },
        }
        self.assertFalse(catalog_song_should_own_sidebar_practice_key(session))

    def test_custom_sbi_song_improv_backing_write_not_catalog(self) -> None:
        """song_improv + custom:: bound pick must not write Shape sticky."""
        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"

        class _Ctx:
            source = "song_improv"
            bound_pick_key = custom
            active_song_id = custom

        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_catalog_pick_key": shape,
            "practice_key_by_source": {shape: "Dm", custom: "D"},
            "backing_context": _Ctx(),
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "active": {
                    "id": "trial-1",
                    "name": "Trial Song",
                    "original_key_center": "D",
                },
            },
        }
        # Patch get_backing_context via session key if helpers use it — prefer monkey via module
        import backing_context as bc

        prev = getattr(bc, "get_backing_context", None)

        def _fake_ctx(s):
            return _Ctx()

        bc.get_backing_context = _fake_ctx  # type: ignore[assignment]
        try:
            write_pick = resolve_settings_pick_for_write(session)
            self.assertEqual(write_pick, custom)
            set_practice_concert_key(session, "E")
            self.assertEqual(get_practice_concert_key(session, shape), "Dm")
            self.assertEqual(get_practice_concert_key(session, custom), "E")
        finally:
            if prev is not None:
                bc.get_backing_context = prev

    def test_prepare_sbi_custom_sidebar_uses_custom_home_not_shape_dm(self) -> None:
        from source_session_state import prepare_sbi_custom_sidebar_display_key

        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"

        class _St:
            session_state: dict = {}

        st = _St()
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_catalog_pick_key": shape,
            "display_key": "Dm",
            "concert_key": "Dm",
            "practice_key_by_source": {shape: "Dm", custom: "D"},
            "cpl_active_progression": {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"A": ["Em", "Em", "D", "D"]},
            },
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "active": {
                    "id": "trial-1",
                    "name": "Trial Song",
                    "original_key_center": "D",
                    "original_sections": {"A": ["Em", "Em", "D", "D"]},
                },
            },
        }
        st.session_state = session
        options = prepare_sbi_custom_sidebar_display_key(st, session)
        self.assertIn("D", options)
        self.assertEqual(session.get("display_key"), "D")
        self.assertEqual(get_practice_concert_key(session, shape), "Dm")

    def test_case_a_active_custom_sbi_custom_uses_active_practice_key(self) -> None:
        """Trial Global Active at C → SBI Custom must show C, not Original D."""
        from songs.music_source import SOURCE_CUSTOM
        from source_session_state import (
            prepare_sbi_custom_sidebar_display_key,
            resolve_sbi_preview,
            sbi_custom_identity_is_global_active,
        )

        custom = "custom::trial-1"

        class _St:
            session_state: dict = {}

        st = _St()
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": custom,
            "display_key": "C",
            "concert_key": "C",
            "practice_key_by_source": {custom: "C"},
            "cpl_active_progression": {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {
                    "Verse": [
                        {"chord": "Em", "bars": 1},
                        {"chord": "Em", "bars": 1},
                        {"chord": "D", "bars": 1},
                        {"chord": "D", "bars": 1},
                    ]
                },
            },
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "active": {
                    "id": "trial-1",
                    "name": "Trial Song",
                    "original_key_center": "D",
                    "original_sections": {
                        "Verse": [
                            {"chord": "Em", "bars": 1},
                            {"chord": "Em", "bars": 1},
                            {"chord": "D", "bars": 1},
                            {"chord": "D", "bars": 1},
                        ]
                    },
                },
            },
        }
        st.session_state = session
        self.assertTrue(sbi_custom_identity_is_global_active(session))
        prepare_sbi_custom_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "C")
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("display_key"), "C")
        joined = " ".join(
            " ".join(chords) for chords in (preview.get("sections") or {}).values()
        )
        self.assertIn("Dm", joined)
        self.assertIn("C", joined)
        self.assertNotIn("Em", joined)

    def test_case_b_non_active_custom_sbi_uses_original_lifecycle(self) -> None:
        """Shape Global Active + LAST_CUSTOM Trial → SBI Custom starts at Original D."""
        from songs.music_source import SOURCE_CATALOG
        from source_session_state import (
            prepare_sbi_custom_sidebar_display_key,
            resolve_sbi_preview,
            sbi_custom_identity_is_global_active,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"

        class _St:
            session_state: dict = {}

        st = _St()
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": shape,
            "display_key": "Bm",
            "concert_key": "Bm",
            "practice_key_by_source": {shape: "Bm", custom: "D"},
            "cpl_active_progression": {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"A": ["Em", "Em", "D", "D"]},
            },
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "active": {
                    "id": "trial-1",
                    "name": "Trial Song",
                    "original_key_center": "D",
                    "original_sections": {"A": ["Em", "Em", "D", "D"]},
                },
            },
        }
        st.session_state = session
        self.assertFalse(sbi_custom_identity_is_global_active(session))
        prepare_sbi_custom_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "D")
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("display_key"), "D")
        self.assertEqual(get_practice_concert_key(session, shape), "Bm")

    def test_case_b_ignores_prior_active_custom_sticky_c(self) -> None:
        """After Shape is Global Active, leftover Trial sticky C must not win over Original D."""
        from songs.music_source import SOURCE_CATALOG
        from source_session_state import prepare_sbi_custom_sidebar_display_key, resolve_sbi_preview

        shape = "Pop\x1fShape of You — Ed Sheeran"
        custom = "custom::trial-1"

        class _St:
            session_state: dict = {}

        st = _St()
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": shape,
            "display_key": "Bm",
            "concert_key": "Bm",
            "practice_key_by_source": {shape: "Bm", custom: "C"},
            "cpl_active_progression": {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {
                    "Verse": [
                        {"chord": "Em", "bars": 1},
                        {"chord": "Em", "bars": 1},
                        {"chord": "D", "bars": 1},
                        {"chord": "D", "bars": 1},
                    ]
                },
            },
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": custom,
                "active": {
                    "id": "trial-1",
                    "name": "Trial Song",
                    "original_key_center": "D",
                },
            },
        }
        st.session_state = session
        prepare_sbi_custom_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "D")
        self.assertEqual(resolve_sbi_preview(session).get("display_key"), "D")

    def test_case_a_mismatched_last_custom_pick_does_not_reset_active_pk(self) -> None:
        """Active Custom PK C must not be reset to Original D by a LAST_CUSTOM pick mismatch."""
        from songs.music_source import SOURCE_CUSTOM
        from source_session_state import (
            prepare_sbi_custom_sidebar_display_key,
            sbi_custom_identity_is_global_active,
        )

        custom_ga = "custom::trial-live"
        last_custom = "custom::trial-stale"

        class _St:
            session_state: dict = {}

        st = _St()
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": custom_ga,
            "display_key": "C",
            "concert_key": "C",
            "practice_key_by_source": {custom_ga: "C", last_custom: "D"},
            "cpl_active_progression": {
                "id": "trial-live",
                "name": "Trial Song",
                "original_key_center": "D",
            },
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": last_custom,
                "active": {
                    "id": "trial-stale",
                    "name": "Trial Song",
                    "original_key_center": "D",
                },
            },
        }
        st.session_state = session
        self.assertTrue(sbi_custom_identity_is_global_active(session))
        prepare_sbi_custom_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "C")


if __name__ == "__main__":
    unittest.main()
