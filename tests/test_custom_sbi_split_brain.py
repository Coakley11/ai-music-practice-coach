"""Reproduce human screenshot split-brain: LAST_CUSTOM vs My Progression / Shape PK."""

from __future__ import annotations

import unittest

from backing_context import build_song_improv_context, sections_dict_from_backing_context
from backing_musical_state import _resolve_creative_practice_concert_key
from custom_progression_lab import default_active_progression
from songs.music_source import (
    LAST_CUSTOM_STATE_KEY,
    SOURCE_CATALOG,
    ensure_custom_progression_for_backing,
    install_last_custom_into_live_cpl,
)
from source_session_state import resolve_sbi_preview, sync_custom_session


def _trial_active() -> dict:
    return {
        "id": "trial-1",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Intro": [],
            "Verse": [
                {"chord": "Em", "bars": 1},
                {"chord": "Em", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
            ],
            "Pre-Chorus": [],
            "Chorus": [],
            "Bridge": [],
            "Solo": [],
            "Outro": [],
        },
        "bpm": 100,
        "progression_style": "Pop",
        "groove_style": "Pop",
    }


def _shape_contaminated_session() -> dict:
    """Global Active = Shape Dm; live CPL = empty My Progression; LAST_CUSTOM = Trial D."""
    shell = default_active_progression()
    trial = _trial_active()
    return {
        "active_music_source": SOURCE_CATALOG,
        "active_catalog_pick_key": "Pop\x1fShape of You",
        "song": "Shape of You",
        "display_key": "Dm",
        "concert_key": "Dm",
        "selected_song": {
            "title": "Shape of You",
            "key": "Bm",
            "pick_key": "Pop\x1fShape of You",
        },
        "practice_key_by_source": {
            "Pop\x1fShape of You": "Dm",
        },
        "cpl_active_progression": shell,
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": "custom::trial-1",
            "custom_home_key": "D",
            "active": trial,
        },
        "sbi_preview_source": "Custom progression",
        "improv_entry_mode": "Song-Based Improvisation",
        "studio_page": "backing",
        "improv_song_source": "Custom progression",
    }


class TestScreenshotSplitBrain(unittest.TestCase):
    def test_ensure_installs_trial_over_my_progression_shell(self) -> None:
        session = _shape_contaminated_session()
        ensure_custom_progression_for_backing(session, promote_to_global_active=False)
        active = session.get("cpl_active_progression") or {}
        self.assertEqual(str(active.get("name") or ""), "Trial Song")
        self.assertNotEqual(str(active.get("name") or ""), "My Progression")

    def test_custom_sbi_backing_ctx_is_trial_d_not_my_progression(self) -> None:
        session = _shape_contaminated_session()
        ctx = build_song_improv_context(session)
        self.assertEqual(ctx.source, "song_improv")
        self.assertEqual(ctx.song_title, "Trial Song")
        self.assertNotIn("My Progression", ctx.song_title)
        # Original / home is D major — not Shape Dm and not C minor.
        self.assertTrue(str(ctx.key or "").startswith("D"), msg=ctx.key)
        self.assertNotEqual(str(ctx.concert_key or "").lower(), "dm")
        self.assertNotEqual(str(ctx.concert_key or "").lower(), "cm")
        # Progression must be Trial material (at Original D: Em Em D D).
        prog = [str(c) for c in (ctx.progression or [])]
        self.assertEqual(prog[:4], ["Em", "Em", "D", "D"])

    def test_practice_key_owner_is_custom_not_shape_dm(self) -> None:
        session = _shape_contaminated_session()
        ctx = build_song_improv_context(session)
        practice = _resolve_creative_practice_concert_key(
            session, creative=ctx, major_jam=False
        )
        # Must not inherit Shape Dm.
        self.assertNotEqual(str(practice or "").lower(), "dm")
        # Fresh Trial sticky absent → Original D major.
        self.assertTrue(str(practice or "").upper().startswith("D"), msg=practice)
        self.assertFalse(str(practice or "").lower().endswith("m") and "dm" in str(practice).lower())

    def test_sections_do_not_pull_catalog_shape(self) -> None:
        session = _shape_contaminated_session()
        ctx = build_song_improv_context(session)
        sections = sections_dict_from_backing_context(session, ctx)
        flat = [c for chs in sections.values() for c in chs]
        self.assertTrue(flat)
        # Shape of You charts must not replace Trial Em/D material.
        joined = " ".join(flat)
        self.assertIn("Em", joined)
        self.assertIn("D", joined)

    def test_sbi_preview_resolves_trial_not_shell(self) -> None:
        session = _shape_contaminated_session()
        sync_custom_session(session)
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("source"), "Custom progression")
        self.assertEqual(preview.get("title"), "Trial Song")
        self.assertTrue(str(preview.get("original_key") or "").startswith("D"))
        self.assertNotEqual(str(preview.get("display_key") or "").lower(), "dm")

    def test_custom_page_seal_does_not_overwrite_catalog_sticky(self) -> None:
        """Entering Custom must not stamp Custom live E onto Shape sticky Dm."""
        from custom_progression_lab import prepare_custom_workspace_sidebar_display_key
        from songs.practice_key_state import get_practice_concert_key

        session = _shape_contaminated_session()
        install_last_custom_into_live_cpl(session)
        session["studio_page"] = "custom"
        session["display_key"] = "E"
        session["concert_key"] = "E"
        session["practice_key_by_source"]["Pop\x1fShape of You"] = "Dm"

        class _St:
            session_state = session

        prepare_custom_workspace_sidebar_display_key(_St(), session)
        shape_sticky = get_practice_concert_key(session, "Pop\x1fShape of You")
        self.assertEqual(str(shape_sticky or "").lower(), "dm")

    def test_sbi_custom_rejects_shape_dm_sticky_bleed(self) -> None:
        """Trial D major must not project Shape Dm as SBI Custom Practice Key."""
        from source_session_state import prepare_sbi_custom_sidebar_display_key

        session = _shape_contaminated_session()
        install_last_custom_into_live_cpl(session)
        trial_pick = "custom::trial-1"
        session["practice_key_by_source"][trial_pick] = "Dm"
        session["display_key"] = "Dm"
        session["concert_key"] = "Dm"
        session["studio_page"] = "creative"
        session["sbi_preview_source"] = "Custom progression"

        class _St:
            session_state = session

        prepare_sbi_custom_sidebar_display_key(_St(), session)
        self.assertTrue(str(session.get("display_key") or "").upper().startswith("D"))
        self.assertNotIn(str(session.get("display_key") or "").lower(), {"dm", "d minor"})

    def test_clear_overlay_restores_sealed_catalog_after_custom_e(self) -> None:
        """Leave Custom SBI after PK→E must restore sealed Shape Dm, not keep E."""
        from source_session_state import (
            clear_sbi_custom_sidebar_overlay_if_needed,
            prepare_sbi_custom_sidebar_display_key,
        )
        from songs.practice_key_state import get_practice_concert_key

        session = _shape_contaminated_session()
        install_last_custom_into_live_cpl(session)
        shape = str(session.get("active_catalog_pick_key") or "")
        session["practice_key_by_source"][shape] = "Dm"
        session["studio_page"] = "creative"
        session["sbi_preview_source"] = "Custom progression"
        session["display_key"] = "Dm"
        session["concert_key"] = "Dm"

        class _St:
            session_state = session

        prepare_sbi_custom_sidebar_display_key(_St(), session)
        self.assertEqual(session.get("_sbi_custom_sealed_catalog_pk"), "Dm")
        self.assertEqual(session.get("_sbi_custom_sealed_catalog_pick"), shape)
        # Simulate Custom SBI Backing PK → E (custom sticky only).
        session["studio_page"] = "backing"
        session["display_key"] = "E"
        session["concert_key"] = "E"
        session["practice_key_by_source"]["custom::trial-1"] = "E"
        # Poison catalog sticky the way Streamlit remount sometimes did.
        session["practice_key_by_source"][shape] = "E"
        session["studio_page"] = "songs"
        clear_sbi_custom_sidebar_overlay_if_needed(session)
        self.assertEqual(get_practice_concert_key(session, shape), "Dm")
        self.assertEqual(session.get("display_key"), "Dm")
        self.assertEqual(session.get("practice_key_by_source").get("custom::trial-1"), "E")
        # Seal retained — refuse remount bleed of Custom E onto Shape.
        self.assertEqual(session.get("_sbi_custom_sealed_catalog_pk"), "Dm")
        from songs.practice_key_state import set_practice_concert_key

        set_practice_concert_key(session, "E", pick_key=shape)
        self.assertEqual(get_practice_concert_key(session, shape), "Dm")

    def test_clear_overlay_keeps_custom_on_backing(self) -> None:
        """Open Custom SBI Backing must not restore Shape Dm into live PK."""
        from backing_context import set_backing_context
        from source_session_state import clear_sbi_custom_sidebar_overlay_if_needed

        session = _shape_contaminated_session()
        install_last_custom_into_live_cpl(session)
        set_backing_context(session, build_song_improv_context(session))
        session["studio_page"] = "backing"
        session["sbi_preview_source"] = "Custom progression"
        session["_sbi_custom_sidebar_overlay"] = True
        session["display_key"] = "D"
        session["concert_key"] = "D"
        session["practice_key_by_source"]["custom::trial-1"] = "D"
        clear_sbi_custom_sidebar_overlay_if_needed(session)
        self.assertTrue(session.get("_sbi_custom_sidebar_overlay"))
        self.assertEqual(session.get("display_key"), "D")
        self.assertNotEqual(str(session.get("display_key") or "").lower(), "dm")

    def test_prepare_sbi_custom_on_backing_rejects_shape_dm(self) -> None:
        from backing_context import set_backing_context
        from source_session_state import prepare_sbi_custom_sidebar_display_key

        session = _shape_contaminated_session()
        install_last_custom_into_live_cpl(session)
        set_backing_context(session, build_song_improv_context(session))
        session["studio_page"] = "backing"
        session["sbi_preview_source"] = "Custom progression"
        session["display_key"] = "Dm"
        session["concert_key"] = "Dm"
        session["practice_key_by_source"]["custom::trial-1"] = "Dm"

        class _St:
            session_state = session

        prepare_sbi_custom_sidebar_display_key(_St(), session)
        self.assertTrue(str(session.get("display_key") or "").upper().startswith("D"))
        self.assertNotIn(str(session.get("display_key") or "").lower(), {"dm", "d minor"})

    def test_sync_custom_session_expands_entry_dicts_to_symbols(self) -> None:
        session = _shape_contaminated_session()
        install_last_custom_into_live_cpl(session)
        blob = sync_custom_session(session)
        self.assertIsNotNone(blob)
        verse = (blob or {}).get("sections", {}).get("Verse") or []
        self.assertEqual(verse[:4], ["Em", "Em", "D", "D"])
        self.assertNotIn("{'chord'", " ".join(verse))

    def test_install_last_custom_helper(self) -> None:
        session = _shape_contaminated_session()
        ok = install_last_custom_into_live_cpl(session)
        self.assertTrue(ok)
        self.assertEqual(session["cpl_active_progression"]["name"], "Trial Song")

    def test_new_song_blank_not_clobbered_by_last_custom(self) -> None:
        from custom_progression_lab import apply_cpl_session_progression, start_new_progression
        from songs.music_source import mark_cpl_intentional_new_song

        session = _shape_contaminated_session()
        mark_cpl_intentional_new_song(session)
        apply_cpl_session_progression(session, start_new_progression(), reset_display_key=True)
        ok = install_last_custom_into_live_cpl(session)
        self.assertFalse(ok)
        live = session["cpl_active_progression"]
        self.assertIn(str(live.get("name") or ""), {"My Progression", "My progression"})
        # No Em/D from LAST_CUSTOM Trial
        blob = str(live.get("original_sections") or {})
        self.assertNotIn("Em", blob)

    def test_chordless_matching_title_healed_from_last_custom(self) -> None:
        session = _shape_contaminated_session()
        # Simulate SBI "Trial Song · 0 chords" while LAST_CUSTOM has the bars.
        empty_trial = dict(session["cpl_active_progression"])
        empty_trial["original_sections"] = {"Verse": [], "Chorus": []}
        empty_trial["sections"] = {"Verse": [], "Chorus": []}
        session["cpl_active_progression"] = empty_trial
        ok = install_last_custom_into_live_cpl(session)
        self.assertTrue(ok)
        live = session["cpl_active_progression"]
        self.assertEqual(live["name"], "Trial Song")
        verse = (live.get("original_sections") or {}).get("Verse") or []
        self.assertGreaterEqual(len(verse), 2)

    def test_custom_ga_stale_say_cache_does_not_bleed_into_sbi(self) -> None:
        """Trial Song GA must not show Say progression from improv_song_concert_sections."""
        from improvisation_motif import concert_song_sections_from_session, resolve_improv_sections
        from songs.music_source import SOURCE_CUSTOM, set_custom_source
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        trial = _trial_active()
        say_sections = {
            "Verse": ["G", "Em", "C", "D", "G", "Em", "C", "D"] * 4,
            "Chorus": ["G", "D", "Em", "C"] * 3,
        }
        session = {
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::trial-1",
            "song": "Trial Song",
            "display_key": "D",
            "concert_key": "D",
            "cpl_active_progression": trial,
            "selected_song": {
                "title": "Trial Song",
                "key": "D",
                "pick_key": "custom::trial-1",
            },
            "practice_key_by_source": {"custom::trial-1": "D"},
            "improv_song_concert_sections": say_sections,
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
        }
        set_custom_source(session)
        synced = sync_song_improv_sections_to_practice_key(session)
        flat_sync = [c for chs in synced.values() for c in chs]
        self.assertEqual(flat_sync[:4], ["Em", "Em", "D", "D"])
        concert = concert_song_sections_from_session(session)
        flat = [c for chs in (concert or {}).values() for c in chs]
        self.assertEqual(flat[:4], ["Em", "Em", "D", "D"])
        self.assertLess(len(flat), 20)
        preview = resolve_sbi_preview(session)
        prev_flat = [c for chs in (preview.get("sections") or {}).values() for c in chs]
        self.assertEqual(prev_flat[:4], ["Em", "Em", "D", "D"])
        class _Ctx:
            sections = {}
            progression_flat = []
            section_order = []

        mapped = resolve_improv_sections(session, _Ctx())
        mission_flat = [c for _s, chs in mapped for c in chs]
        self.assertIn("Em", mission_flat)
        self.assertIn("D", mission_flat)
        self.assertLess(len(mission_flat), 12)
        self.assertNotEqual(mission_flat[0], "G")


if __name__ == "__main__":
    unittest.main()
