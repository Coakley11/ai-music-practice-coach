"""Upload song identity must follow Catalog / Custom / Composition ownership."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from recording_analysis_context import (
    ANALYSIS_IDENTITY_LOCKED_KEY,
    ANALYSIS_SONG_SOURCE_ID_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_SONG_SOURCE_TYPE_KEY,
    SONG_SOURCE_CATALOG,
    SONG_SOURCE_COMPOSED,
    SONG_SOURCE_CUSTOM,
    resolve_active_song_source,
    seed_session_setup_from_active,
)


GRAVITY_PICK = "Pop\x1fGravity — John Mayer"


class TestUploadFollowsActiveSourceOwnership(unittest.TestCase):
    def test_resolve_composition_without_composition_studio_page(self) -> None:
        from composition_songs_bridge import (
            commit_composition_active_song,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from songs.music_source import SOURCE_COMPOSITION, commit_explicit_music_source_choice

        ss: dict = {
            "studio_page": "analysis",
            "instrument": "Piano",
            "display_key": "C",
            "composer_saved_compositions": {},
            # Stale catalog leftovers must not win.
            "analysis_song_source_type": SONG_SOURCE_CATALOG,
            "analysis_song_source_name": "Gravity",
            "analysis_song_source_id": GRAVITY_PICK,
            "selected_song": {
                "pick_key": GRAVITY_PICK,
                "title": "Gravity",
                "artist": "John Mayer",
            },
        }
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        commit_explicit_music_source_choice(ss, SOURCE_COMPOSITION, clear_composition_oneshots=False)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _s: None)
        resolved = resolve_active_song_source(ss)
        self.assertEqual(resolved["song_source_type"], SONG_SOURCE_COMPOSED)
        self.assertEqual(resolved["song_source_name"], "My Composition")
        self.assertNotEqual(resolved["song_source_name"], "Gravity")

    def test_seed_resyncs_when_owner_changes_from_catalog_to_custom(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import (
            SOURCE_CUSTOM,
            commit_explicit_music_source_choice,
            set_custom_source,
        )

        ss: dict = {
            "studio_page": "analysis",
            "instrument": "Piano",
            "display_key": "D",
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_CATALOG,
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Gravity",
            ANALYSIS_SONG_SOURCE_ID_KEY: GRAVITY_PICK,
            "_analysis_active_song_seed_sig": f"{SONG_SOURCE_CATALOG}|{GRAVITY_PICK}|Gravity",
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "My Progression",
                "artist": "Custom",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
            },
            "active_catalog_pick_key": "custom::trial-1",
        }
        commit_explicit_music_source_choice(ss, SOURCE_CUSTOM)
        set_custom_source(ss)
        seed_session_setup_from_active(ss)
        self.assertEqual(ss.get(ANALYSIS_SONG_SOURCE_TYPE_KEY), SONG_SOURCE_CUSTOM)
        self.assertEqual(ss.get(ANALYSIS_SONG_SOURCE_NAME_KEY), "My Progression")
        self.assertTrue(str(ss.get(ANALYSIS_SONG_SOURCE_ID_KEY) or "").startswith("custom::"))

    def test_seed_resyncs_catalog_gravity_after_composition(self) -> None:
        from songs.music_source import (
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            commit_explicit_music_source_choice,
            set_catalog_source,
        )

        ss: dict = {
            "studio_page": "analysis",
            "instrument": "Piano",
            "display_key": "G",
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_COMPOSED,
            ANALYSIS_SONG_SOURCE_NAME_KEY: "My Composition",
            ANALYSIS_SONG_SOURCE_ID_KEY: "f4bf4a14-784d-464f-8394-7b7fcaaa29e3",
            "_analysis_active_song_seed_sig": f"{SONG_SOURCE_COMPOSED}|doc|My Composition",
            "active_catalog_pick_key": GRAVITY_PICK,
            "selected_song": {
                "pick_key": GRAVITY_PICK,
                "title": "Gravity",
                "artist": "John Mayer",
                "key": "G",
            },
            "active_song_state": {
                "pick_key": GRAVITY_PICK,
                "music_source": SOURCE_CATALOG,
                "selected_song": {
                    "pick_key": GRAVITY_PICK,
                    "title": "Gravity",
                    "artist": "John Mayer",
                    "key": "G",
                },
                "display_key": "G",
            },
        }
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        set_catalog_source(ss)
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        seed_session_setup_from_active(ss)
        self.assertEqual(ss.get(ANALYSIS_SONG_SOURCE_TYPE_KEY), SONG_SOURCE_CATALOG)
        self.assertEqual(ss.get(ANALYSIS_SONG_SOURCE_NAME_KEY), "Gravity")
        self.assertEqual(ss.get(ANALYSIS_SONG_SOURCE_ID_KEY), GRAVITY_PICK)

    def test_mission_lock_blocks_owner_resync(self) -> None:
        ss: dict = {
            "studio_page": "analysis",
            ANALYSIS_IDENTITY_LOCKED_KEY: True,
            "_mission_upload_analysis_handoff": True,
            ANALYSIS_SONG_SOURCE_TYPE_KEY: SONG_SOURCE_COMPOSED,
            ANALYSIS_SONG_SOURCE_NAME_KEY: "Mission Piece",
            ANALYSIS_SONG_SOURCE_ID_KEY: "mission-doc",
            "_analysis_active_song_seed_sig": f"{SONG_SOURCE_COMPOSED}|mission-doc|Mission Piece",
            "active_catalog_pick_key": GRAVITY_PICK,
            "selected_song": {
                "pick_key": GRAVITY_PICK,
                "title": "Gravity",
                "artist": "John Mayer",
            },
            "active_song_state": {
                "pick_key": GRAVITY_PICK,
                "music_source": "catalog_song",
            },
        }
        seed_session_setup_from_active(ss)
        self.assertEqual(ss.get(ANALYSIS_SONG_SOURCE_NAME_KEY), "Mission Piece")
        self.assertEqual(ss.get(ANALYSIS_SONG_SOURCE_TYPE_KEY), SONG_SOURCE_COMPOSED)

    def test_off_songs_stale_catalog_radio_does_not_steal_composition(self) -> None:
        """Upload/Creative must not treat a dormant Catalog radio as a live leave."""
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            PENDING_CATALOG_FROM_PICKER_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SOURCE_CATALOG,
            SOURCE_COMPOSITION,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_picker_music_source,
            song_picker_composition_option_label,
        )

        ss: dict = {
            "studio_page": "analysis",
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_COMPOSITION,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
            "active_catalog_pick_key": "composition::doc-1",
            "selected_song": {
                "pick_key": "composition::doc-1",
                "title": "My Composition",
                "artist": "Composition",
            },
        }
        reconcile_picker_music_source(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_COMPOSITION)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_COMPOSITION)
        self.assertNotEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CATALOG)
        self.assertNotIn(USER_CATALOG_SOURCE_CHOICE_KEY, ss)
        self.assertFalse(bool(ss.get(PENDING_CATALOG_FROM_PICKER_KEY)))
        self.assertEqual(
            ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY),
            song_picker_composition_option_label(),
        )

    def test_off_songs_stale_catalog_radio_does_not_steal_custom(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            PENDING_CATALOG_FROM_PICKER_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CUSTOM,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_picker_music_source,
        )

        ss: dict = {
            "studio_page": "creative",
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
            "active_catalog_pick_key": "custom::trial-1",
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "My Progression",
                "original_key_center": "D",
            },
        }
        reconcile_picker_music_source(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CUSTOM)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertNotIn(USER_CATALOG_SOURCE_CHOICE_KEY, ss)
        self.assertFalse(bool(ss.get(PENDING_CATALOG_FROM_PICKER_KEY)))
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)

    def test_catalog_upload_songs_roundtrip_keeps_catalog_despite_lagging_active(self) -> None:
        """Catalog → Upload → Songs must not commit Composition from lagging ACTIVE."""
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SOURCE_CATALOG,
            SOURCE_COMPOSITION,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_picker_music_source,
            song_picker_composition_option_label,
        )

        ss: dict = {
            "studio_page": "analysis",
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,  # lagging
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
            "active_catalog_pick_key": GRAVITY_PICK,
            "selected_song": {
                "pick_key": GRAVITY_PICK,
                "title": "Gravity",
                "artist": "John Mayer",
                "key": "G",
            },
            "composer_active_document": {
                "id": "f4bf4a14-784d-464f-8394-7b7fcaaa29e3",
                "title": "My Composition",
            },
            "display_key": "G",
        }
        reconcile_picker_music_source(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CATALOG)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertTrue(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertNotEqual(
            ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY),
            song_picker_composition_option_label(),
        )
        # Return to Songs — live Catalog radio must not flip to Composition.
        ss["studio_page"] = "picker"
        reconcile_picker_music_source(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CATALOG)
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertNotEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_COMPOSITION)
        resolved = resolve_active_song_source(ss)
        self.assertEqual(resolved["song_source_type"], SONG_SOURCE_CATALOG)
        self.assertEqual(resolved["song_source_name"], "Gravity")

    def test_custom_upload_songs_roundtrip_keeps_custom_despite_lagging_active(self) -> None:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_COMPOSITION,
            SOURCE_CUSTOM,
            reconcile_picker_music_source,
            song_picker_composition_option_label,
            sync_song_picker_source_widget,
        )

        ss: dict = {
            "studio_page": "analysis",
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,  # lagging
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::trial-1",
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "My Progression",
                "artist": "Custom",
                "original_key_center": "D",
            },
            "display_key": "D",
        }
        sync_song_picker_source_widget(ss, force=True)
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertNotEqual(
            ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY),
            song_picker_composition_option_label(),
        )
        reconcile_picker_music_source(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CUSTOM)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        ss["studio_page"] = "picker"
        reconcile_picker_music_source(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CUSTOM)
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        resolved = resolve_active_song_source(ss)
        self.assertEqual(resolved["song_source_type"], SONG_SOURCE_CUSTOM)
        self.assertEqual(resolved["song_source_name"], "My Progression")

    def test_songs_remount_stale_composition_radio_does_not_steal_custom(self) -> None:
        """Upload→Songs remount with leftover Composition radio must keep Custom."""
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_COMPOSITION,
            SOURCE_CUSTOM,
            reconcile_music_picker_source_widget,
            reconcile_picker_music_source,
            song_picker_composition_option_label,
            sync_song_picker_source_widget,
        )

        ss: dict = {
            "studio_page": "analysis",
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            # Stale radio leftover from prior Composition session / remount.
            SONG_PICKER_ACTIVE_SOURCE_KEY: song_picker_composition_option_label(),
            "active_catalog_pick_key": "custom::trial-1",
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "My Progression",
                "artist": "Custom",
                "original_key_center": "D",
            },
            "display_key": "D",
            "concert_key": "D",
        }
        # Off-Songs: align dormant radio from ownership (must not commit Composition).
        reconcile_picker_music_source(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CUSTOM)
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)

        # Reintroduce stale Composition radio as Songs remount would, then reconcile.
        ss["studio_page"] = "picker"
        ss[SONG_PICKER_ACTIVE_SOURCE_KEY] = song_picker_composition_option_label()
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION  # lagging ACTIVE
        sync_song_picker_source_widget(ss, force=True)
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        reconcile_picker_music_source(ss)
        reconcile_music_picker_source_widget(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CUSTOM)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertNotEqual(
            ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY),
            song_picker_composition_option_label(),
        )
        resolved = resolve_active_song_source(ss)
        self.assertEqual(resolved["song_source_type"], SONG_SOURCE_CUSTOM)

    def test_songs_remount_stale_composition_radio_does_not_steal_catalog_say(self) -> None:
        """Catalog Say leave + remount must keep Catalog and not paint Composition."""
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SOURCE_CATALOG,
            SOURCE_COMPOSITION,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_music_picker_source_widget,
            reconcile_picker_music_source,
            song_picker_composition_option_label,
            sync_song_picker_source_widget,
        )

        say_pick = "Pop\x1fSay — John Mayer"
        ss: dict = {
            "studio_page": "picker",
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            SONG_PICKER_ACTIVE_SOURCE_KEY: song_picker_composition_option_label(),
            "active_catalog_pick_key": say_pick,
            "selected_song": {
                "pick_key": say_pick,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
            "display_key": "G",
            "concert_key": "G",
            "original_key": "G",
        }
        sync_song_picker_source_widget(ss, force=True)
        reconcile_picker_music_source(ss)
        reconcile_music_picker_source_widget(ss)
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CATALOG)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertEqual(ss.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertNotEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_COMPOSITION)
        self.assertEqual(str(ss.get("display_key") or ""), "G")
        resolved = resolve_active_song_source(ss)
        self.assertEqual(resolved["song_source_type"], SONG_SOURCE_CATALOG)
        self.assertEqual(resolved["song_source_name"], "Say")

    def test_catalog_song_pick_resets_practice_key_to_document_original(self) -> None:
        """Explicit Say selection resets practice key to G (not Composition C)."""
        from types import SimpleNamespace

        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SOURCE_CATALOG,
            SOURCE_COMPOSITION,
            commit_catalog_active_song,
        )
        from songs.practice_key_state import get_practice_concert_key

        say_pick = "Pop\x1fSay — John Mayer"
        ss: dict = {
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_COMPOSITION,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::prior",
            "display_key": "C",
            "concert_key": "C",
            "practice_key_by_source": {
                "composition::prior": "Db",
                say_pick: "C",  # poisoned from prior Composition bleed
            },
        }
        st = SimpleNamespace(session_state=ss)
        commit_catalog_active_song(
            st,
            pick_key=say_pick,
            selected_song={
                "pick_key": say_pick,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
            original_key="G",
            display_key="G",
            invalidate_backing=lambda _s: None,
            reason="song_pick",
        )
        self.assertEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CATALOG)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertEqual(str(ss.get("display_key") or ""), "G")
        self.assertEqual(str(ss.get("concert_key") or ""), "G")
        # Explicit switch clears any poisoned saved practice key for this pick.
        self.assertNotEqual(get_practice_concert_key(ss, pick_key=say_pick), "C")
        self.assertNotEqual(
            (ss.get("practice_key_by_source") or {}).get(say_pick),
            "C",
        )


if __name__ == "__main__":
    unittest.main()
