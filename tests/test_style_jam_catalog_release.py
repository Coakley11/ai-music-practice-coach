"""Style Jam C# must not contaminate an explicit catalog Shape activation."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from generated_jam_key_context import (
    GENERATED_JAM_KEY_CONTEXT_KEY,
    activate_generated_jam_key_ownership,
    generated_jam_owns_practice_key,
    release_generated_jam_key_for_catalog_surface,
)
from guitar_capo import shape_chart_key_for_concert, shape_chart_label_for_concert
from song_catalog.catalog import format_pick_key
from songs.music_source import begin_explicit_catalog_selection
from songs.practice_key_state import get_practice_concert_key
from songs.state import apply_explicit_catalog_dropdown_pick, apply_pick_key
from source_session_state import _catalog_display_key


PK_SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")

CATALOG = {
    "Pop": {
        "Shape of You — Ed Sheeran": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "sections": {"Verse": ["Bm", "Em", "G", "A"]},
        },
        "Perfect — Ed Sheeran": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "key": "G",
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        },
    }
}
PK_PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")


class TestStyleJamCatalogRelease(unittest.TestCase):
    def test_explicit_shape_pick_after_style_jam_c_sharp_is_b_minor(self) -> None:
        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": PK_SHAPE,
            "active_music_source": "catalog_song",
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "display_key": "C#",
            "concert_key": "C#",
            "improv_style_key": "C#",
            "improv_entry_mode": "Style Jam Mode",
            "_generated_jam_key_owner_active": True,
            "_backing_explicit_handoff_source": "entry_jam",
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "key_owner": "entry_jam",
                "practice_key_token": "C#",
                "practice_tonic": "C#",
                "practice_mode": "major",
                "entry_mode": "Style Jam Mode",
            },
            "practice_key_by_source": {PK_SHAPE: "Bm"},
            "_master_song_pick_key": PK_SHAPE,
        }
        activate_generated_jam_key_ownership(
            session, entry_mode="Style Jam Mode", practice_key="C#"
        )
        session["display_key"] = "C#"
        session["concert_key"] = "C#"
        session["studio_page"] = "picker"
        self.assertIn("C#", str(session.get("display_key") or ""))

        begin_explicit_catalog_selection(session)
        self.assertTrue(session.get("_explicit_catalog_fresh_activation"))
        self.assertNotEqual(session.get("_backing_explicit_handoff_source"), "entry_jam")
        self.assertFalse(generated_jam_owns_practice_key(session))

        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, persist=False, origin="user")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(str(session.get("concert_key") or ""), "Bm")
        saved = str(get_practice_concert_key(session, PK_SHAPE) or "")
        self.assertNotEqual(saved, "C#")

    def test_songs_landing_release_strips_jam_live_from_shape(self) -> None:
        session = {
            "studio_page": "songs",
            "active_catalog_pick_key": PK_SHAPE,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "key": "Bm",
            },
            "display_key": "C#",
            "concert_key": "C#",
            "improv_style_key": "C#",
            "improv_entry_mode": "Style Jam Mode",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "_generated_jam_key_owner_active": True,
            "_backing_explicit_handoff_source": "entry_jam",
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "key_owner": "entry_jam",
                "practice_key_token": "C#",
                "entry_mode": "Style Jam Mode",
            },
            "practice_key_by_source": {PK_SHAPE: "Bm"},
        }
        released = release_generated_jam_key_for_catalog_surface(session)
        self.assertTrue(released)
        live = str(session.get("display_key") or session.get("concert_key") or "")
        self.assertNotEqual(live, "C#")
        self.assertEqual(live, "Bm")
        self.assertEqual(session.get("improv_style_key"), "C#")
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(session.get("sbi_preview_source"), "Active song")

    def test_jam_snapshot_trial_d_does_not_become_shape_d_minor(self) -> None:
        session = {
            "studio_page": "songs",
            "active_catalog_pick_key": PK_SHAPE,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "key": "Bm",
            },
            "display_key": "C#",
            "concert_key": "C#",
            "improv_style_key": "C#",
            "improv_entry_mode": "Style Jam Mode",
            "_generated_jam_key_owner_active": True,
            "_song_practice_key_snapshot": {
                "display_key": "D",
                "concert_key": "D",
                "practice_concert_key": "D",
                "pick_key": PK_SHAPE,
            },
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "key_owner": "entry_jam",
                "practice_key_token": "C#",
                "entry_mode": "Style Jam Mode",
            },
            "practice_key_by_source": {PK_SHAPE: "Bm"},
        }
        self.assertTrue(release_generated_jam_key_for_catalog_surface(session))
        live = str(session.get("display_key") or session.get("concert_key") or "")
        self.assertEqual(live, "Bm")
        self.assertNotEqual(live, "D")
        self.assertNotEqual(live, "Dm")

    def test_catalog_display_key_rejects_jam_token(self) -> None:
        catalog = {
            "pick_key": PK_SHAPE,
            "original_key": "Bm",
            "selected_song": {"key": "Bm", "pick_key": PK_SHAPE},
        }
        session = {
            "active_catalog_pick_key": PK_SHAPE,
            "display_key": "C#",
            "concert_key": "C#",
            "improv_style_key": "C#",
            "practice_key_by_source": {PK_SHAPE: "Bm"},
        }
        self.assertEqual(_catalog_display_key(session, catalog), "Bm")

    def test_explicit_shape_keeps_sbi_on_active_through_backing_reset(self) -> None:
        from backing_context import reset_backing_on_active_song_change
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            get_sbi_preview_source,
        )
        from studio_page_state import apply_improv_song_source, flush_pending_improv_song_source, init_improvisation_state

        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": PK_SHAPE,
            "active_music_source": "catalog_song",
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "display_key": "C#",
            "concert_key": "C#",
            "improv_style_key": "C#",
            "improv_entry_mode": "Style Jam Mode",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "_restore_sbi_custom_source": True,
            "creative_workspace_state": {
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
            },
            "_generated_jam_key_owner_active": True,
            "_backing_explicit_handoff_source": "entry_jam",
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "key_owner": "entry_jam",
                "practice_key_token": "C#",
                "entry_mode": "Style Jam Mode",
            },
            "practice_key_by_source": {PK_SHAPE: "Bm"},
            "_master_song_pick_key": PK_SHAPE,
        }
        activate_generated_jam_key_ownership(
            session, entry_mode="Style Jam Mode", practice_key="C#"
        )
        session["display_key"] = "C#"
        session["concert_key"] = "C#"
        begin_explicit_catalog_selection(session)
        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, persist=False, origin="user")
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertTrue(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertEqual(get_sbi_preview_source(session), "Active song")
        self.assertEqual(
            (session.get("creative_workspace_state") or {}).get("improv_song_source"),
            "Active song",
        )

        reset_backing_on_active_song_change(
            session, new_pick_key=PK_SHAPE, practice_concert_key="Bm"
        )
        self.assertEqual(session.get("improv_song_source"), "Active song")

        session["sbi_preview_source"] = "Custom progression"
        session["improv_song_source"] = "Custom progression"
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertTrue(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        init_improvisation_state(session, is_custom_active=False)
        self.assertEqual(session.get("improv_song_source"), "Active song")

        apply_improv_song_source(
            session,
            "Custom progression",
            set_catalog_source=lambda *_a, **_k: None,
            set_custom_source=lambda *_a, **_k: None,
        )
        self.assertFalse(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

    def test_explicit_custom_radio_after_follow_bind_is_honored(self) -> None:
        """After Creative rendered Active, a Custom radio click must stick."""
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            get_sbi_preview_source,
        )
        from studio_page_state import flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY: True,
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Active song",
        }
        flush_pending_improv_song_source(session)
        self.assertFalse(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

    def test_explicit_custom_click_without_widget_seen_when_last_was_active(self) -> None:
        """Widget already committed Custom after Follow Active had bound Active."""
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            get_sbi_preview_source,
        )
        from studio_page_state import flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Active song",
        }
        flush_pending_improv_song_source(session)
        self.assertFalse(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

    def test_leftover_custom_without_widget_seen_still_healed(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            get_sbi_preview_source,
        )
        from studio_page_state import flush_pending_improv_song_source

        session = {
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "_last_improv_song_source": "Custom progression",
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(get_sbi_preview_source(session), "Active song")
        self.assertTrue(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))

    def test_project_does_not_overwrite_explicit_custom_click(self) -> None:
        from creative_tab_tool_persistence import project_creative_selectors_from_canonical
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
        )

        session = {
            "creative_workspace_state": {"improv_song_source": "Active song"},
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY: True,
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Active song",
        }
        project_creative_selectors_from_canonical(session, overwrite=True)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")

    def test_explicit_composition_click_after_follow_bind(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            get_sbi_preview_source,
        )
        from studio_page_state import flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY: True,
            "improv_song_source": "Composition",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Active song",
        }
        flush_pending_improv_song_source(session)
        self.assertFalse(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertEqual(session.get("improv_song_source"), "Composition")
        self.assertEqual(get_sbi_preview_source(session), "Composition")

    def test_active_custom_cycle_each_explicit_click_wins(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            get_sbi_preview_source,
        )
        from studio_page_state import apply_improv_song_source, flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY: True,
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Active song",
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(get_sbi_preview_source(session), "Active song")

        session["improv_song_source"] = "Custom progression"
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

        apply_improv_song_source(
            session,
            "Active song",
            set_catalog_source=lambda *_a, **_k: None,
            set_custom_source=lambda *_a, **_k: None,
        )
        session["improv_song_source"] = "Active song"
        flush_pending_improv_song_source(session)
        self.assertEqual(get_sbi_preview_source(session), "Active song")

        session["improv_song_source"] = "Custom progression"
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

    def test_stale_pending_custom_does_not_clobber_active_click(self) -> None:
        from source_session_state import get_sbi_preview_source
        from studio_page_state import PENDING_IMPROV_SONG_SOURCE, flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            "improv_song_source": "Active song",
            "sbi_preview_source": "Custom progression",
            PENDING_IMPROV_SONG_SOURCE: "Custom progression",
            "_last_improv_song_source": "Custom progression",
            "_sbi_song_source_hydrated": True,
            "_restore_sbi_custom_source": True,
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(get_sbi_preview_source(session), "Active song")

    def test_project_does_not_overwrite_explicit_active_click(self) -> None:
        from creative_tab_tool_persistence import project_creative_selectors_from_canonical

        session = {
            "creative_workspace_state": {"improv_song_source": "Custom progression"},
            "improv_song_source": "Active song",
            "sbi_preview_source": "Custom progression",
            "_last_improv_song_source": "Custom progression",
            "_sbi_song_source_hydrated": True,
            "_restore_sbi_custom_source": True,
        }
        project_creative_selectors_from_canonical(session, overwrite=True)
        self.assertEqual(session.get("improv_song_source"), "Active song")

    def test_pending_active_restores_after_snapshot_custom(self) -> None:
        from source_session_state import get_sbi_preview_source
        from studio_page_state import PENDING_IMPROV_SONG_SOURCE, flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Active song",
            PENDING_IMPROV_SONG_SOURCE: "Active song",
            "_last_improv_song_source": "Custom progression",
            "_sbi_song_source_hydrated": True,
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(get_sbi_preview_source(session), "Active song")

    def test_snapshot_does_not_restore_custom_over_active_click(self) -> None:
        from studio_page_persistence import apply_page_snapshot

        session = {
            "studio_page": "creative",
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Custom progression",
            "_sbi_song_source_hydrated": True,
            "_improv_song_source_user_touched": True,
        }
        apply_page_snapshot(
            session,
            {
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
            },
        )
        self.assertEqual(session.get("improv_song_source"), "Active song")

    def test_open_custom_lab_pending_outranks_follow_active(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            get_sbi_preview_source,
        )
        from studio_page_state import PENDING_IMPROV_SONG_SOURCE, flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            PENDING_IMPROV_SONG_SOURCE: "Custom progression",
            "improv_song_source": "Active song",
            "sbi_preview_source": "Custom progression",
            "_sbi_song_source_hydrated": False,
        }
        flush_pending_improv_song_source(session)
        self.assertFalse(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

    def test_shape_rejects_major_g_sticky_from_perfect(self) -> None:
        from music_theory import practice_key_inherits_source_mode
        from songs.key_state import get_authoritative_display_key
        from source_session_state import _catalog_display_key

        self.assertFalse(practice_key_inherits_source_mode("G", "Bm"))
        self.assertTrue(practice_key_inherits_source_mode("Dm", "Bm"))
        catalog = {
            "pick_key": PK_SHAPE,
            "original_key": "Bm",
            "selected_song": {"key": "Bm", "pick_key": PK_SHAPE, "title": "Shape of You"},
        }
        session = {
            "active_catalog_pick_key": PK_SHAPE,
            "display_key": "G",
            "concert_key": "G",
            "guitar_capo_sounding_key": "G",
            "practice_key_by_source": {PK_SHAPE: "G"},
            "selected_song": catalog["selected_song"],
        }
        self.assertEqual(_catalog_display_key(session, catalog), "Bm")
        self.assertEqual(
            get_authoritative_display_key(session, original_key="Bm", surface="test"),
            "Bm",
        )

    def test_jam_release_clears_same_mode_sticky_dm(self) -> None:
        """Shape sticky Dm must not survive Style Jam release (same minor family)."""
        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": PK_SHAPE,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "key": "Bm",
            },
            "display_key": "C#",
            "concert_key": "C#",
            "improv_style_key": "C#",
            "improv_entry_mode": "Style Jam Mode",
            "_generated_jam_key_owner_active": True,
            "_backing_explicit_handoff_source": "entry_jam",
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "key_owner": "entry_jam",
                "practice_key_token": "C#",
                "entry_mode": "Style Jam Mode",
            },
            "practice_key_by_source": {PK_SHAPE: "Dm"},
        }
        self.assertTrue(release_generated_jam_key_for_catalog_surface(session))
        live = str(session.get("display_key") or session.get("concert_key") or "")
        self.assertEqual(live, "Bm")
        self.assertEqual(str(get_practice_concert_key(session, PK_SHAPE) or ""), "Bm")
        self.assertTrue(session.get("_pending_catalog_fresh_activation_after_specialized"))

    def test_restore_apply_pick_does_not_consume_specialized_fresh_flag(self) -> None:
        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": PK_SHAPE,
            "_last_pick_key": PK_SHAPE,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "display_key": "Bm",
            "concert_key": "Bm",
            "_pending_catalog_fresh_activation_after_specialized": True,
            "_explicit_catalog_fresh_activation": True,
            "practice_key_by_source": {PK_SHAPE: "Bm"},
        }
        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, persist=False, origin="restore")
        self.assertTrue(session.get("_pending_catalog_fresh_activation_after_specialized"))
        self.assertTrue(session.get("_explicit_catalog_fresh_activation"))

    def test_explicit_same_pick_after_jam_uses_original_not_sticky_dm(self) -> None:
        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": PK_SHAPE,
            "_last_pick_key": PK_SHAPE,
            "active_music_source": "catalog_song",
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "display_key": "Dm",
            "concert_key": "Dm",
            "improv_entry_mode": "Style Jam Mode",
            "_generated_jam_key_owner_active": True,
            "_backing_explicit_handoff_source": "entry_jam",
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "key_owner": "entry_jam",
                "practice_key_token": "C#",
                "entry_mode": "Style Jam Mode",
            },
            "practice_key_by_source": {PK_SHAPE: "Dm"},
            "_master_song_pick_key": PK_SHAPE,
        }
        activate_generated_jam_key_ownership(
            session, entry_mode="Style Jam Mode", practice_key="C#"
        )
        session["display_key"] = "C#"
        begin_explicit_catalog_selection(session)
        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        with patch("songs.state.persist_music_local_state"):
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertNotEqual(str(session.get("display_key") or ""), "Dm")
        saved = str(get_practice_concert_key(session, PK_SHAPE) or "")
        self.assertNotEqual(saved, "Dm")
        self.assertFalse(session.get("_backing_released_specialized_context"))

    def test_perfect_then_explicit_shape_is_original_b_minor(self) -> None:
        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": PK_SHAPE,
            "_last_pick_key": PK_SHAPE,
            "active_music_source": "catalog_song",
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "display_key": "Dm",
            "concert_key": "Dm",
            "practice_key_by_source": {PK_SHAPE: "Dm"},
            "_master_song_pick_key": PK_SHAPE,
        }
        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        with patch("songs.state.persist_music_local_state"):
            apply_explicit_catalog_dropdown_pick(st, PK_PERFECT, CATALOG)
            self.assertEqual(str(session.get("display_key") or ""), "G")
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertNotEqual(str(session.get("display_key") or ""), "Dm")

    def test_same_source_shape_dm_sticky_without_other_owner(self) -> None:
        """While Shape stays Global Active, user Dm must remain sticky."""
        session = {
            "studio_page": "picker",
            "active_catalog_pick_key": PK_SHAPE,
            "_last_pick_key": PK_SHAPE,
            "active_music_source": "catalog_song",
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "display_key": "Dm",
            "concert_key": "Dm",
            "practice_key_by_source": {PK_SHAPE: "Dm"},
            "_master_song_pick_key": PK_SHAPE,
        }
        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, persist=False, origin="user")
        self.assertEqual(str(session.get("display_key") or ""), "Dm")
        self.assertEqual(str(get_practice_concert_key(session, PK_SHAPE) or ""), "Dm")

    def test_guitar_shape_c_inherits_shape_of_you_minor(self) -> None:
        self.assertEqual(shape_chart_key_for_concert("Bm", "C"), "Cm")
        self.assertEqual(shape_chart_label_for_concert("Bm", "C"), "C minor")
        self.assertNotIn("major", shape_chart_label_for_concert("Bm", "C").lower())


if __name__ == "__main__":
    unittest.main()
