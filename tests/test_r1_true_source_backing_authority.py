"""R1: true source activation + Backing authority (Catalog / Custom / Composition)."""

from __future__ import annotations

import unittest

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_session_state import save_document_to_library, set_active_document
from composition_songs_bridge import (
    composition_home_key,
    composition_pick_key_for,
    commit_composition_active_song,
)
from song_catalog.catalog import format_pick_key
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    LAST_CUSTOM_STATE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    commit_catalog_active_song,
    commit_custom_active_song,
    set_custom_source,
)
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)
from source_session_state import EXPLICIT_SBI_SOURCE_CLICK_KEY, set_sbi_preview_source


HOTEL = format_pick_key("Rock", "Hotel California — Eagles")
TRIAL_ID = "trial-r1-authority"
TRIAL_PICK = f"custom::{TRIAL_ID}"


class _FakeSt:
    def __init__(self, ss: dict) -> None:
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _hotel_catalog_session(*, practice: str = "A#m") -> dict:
    return {
        "studio_page": "picker",
        "instrument": "Guitar",
        "selected_song": {
            "title": "Hotel California",
            "artist": "Eagles",
            "genre": "Rock",
            "key": "Bm",
            "pick_key": HOTEL,
        },
        "active_catalog_pick_key": HOTEL,
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        "original_key": "Bm",
        "display_key": practice,
        "concert_key": practice,
        PRACTICE_KEY_BY_SOURCE_KEY: {HOTEL: practice},
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": {
                "id": TRIAL_ID,
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 4}]},
                "bpm": 100,
            },
        },
        "cpl_active_progression": {
            "id": TRIAL_ID,
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"Verse": [{"chord": "D", "bars": 4}]},
            "bpm": 100,
        },
    }


def _cs_doc(*, key: str = "C# major", title: str = "My Composition") -> dict:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="r1 composition",
        title=title,
        key=key,
        bpm=96,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(
        doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C# F# G#")
    )
    return doc


class TestCatalogToCustomFreshActivation(unittest.TestCase):
    def test_hub_pre_stamp_does_not_leak_catalog_practice_into_trial(self) -> None:
        """First wrong transition: set_custom_source before commit skipped leave-Catalog seal."""
        ss = _hotel_catalog_session(practice="A#m")
        set_practice_concert_key(ss, "A#m", pick_key=HOTEL, allow_restore_original=True)
        # Custom hub currently stamps SOURCE_CUSTOM before commit.
        set_custom_source(ss)
        commit_custom_active_song(
            _FakeSt(ss),
            dict(ss["cpl_active_progression"]),
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=False,
        )
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_CUSTOM)
        self.assertEqual(str(ss.get("original_key") or ss.get("selected_song", {}).get("key") or ""), "D")
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertEqual(str(ss.get("concert_key") or ""), "D")
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK) or "D", "D")
        self.assertNotEqual(str(ss.get("display_key") or ""), "A#m")

    def test_radio_reset_flag_still_seals_original_d(self) -> None:
        ss = _hotel_catalog_session(practice="A#m")
        commit_custom_active_song(
            _FakeSt(ss),
            dict(ss["cpl_active_progression"]),
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK) or "D", "D")


class TestCustomToCompositionFreshActivation(unittest.TestCase):
    def test_composition_starts_at_original_not_trial_d(self) -> None:
        ss = _hotel_catalog_session(practice="A#m")
        commit_custom_active_song(
            _FakeSt(ss),
            dict(ss["cpl_active_progression"]),
            invalidate_backing=lambda *_a, **_k: None,
            reset_practice_to_original=True,
        )
        set_practice_concert_key(ss, "D", pick_key=TRIAL_PICK, allow_restore_original=True)
        ss["display_key"] = "D"
        doc = _cs_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=True
        )
        home = composition_home_key(doc)
        pick = composition_pick_key_for(doc)
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_COMPOSITION)
        self.assertEqual(str(ss.get("display_key") or ""), home)
        self.assertEqual(get_practice_concert_key(ss, pick) or home, home)
        self.assertNotEqual(str(ss.get("display_key") or ""), "D")


class TestBackingFollowsTrueSource(unittest.TestCase):
    def test_composition_backing_ignores_cpl_leftover_and_stale_catalog_ctx(self) -> None:
        ss = _hotel_catalog_session(practice="Bm")
        doc = _cs_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=True
        )
        home = composition_home_key(doc)
        set_practice_concert_key(ss, home, pick_key=composition_pick_key_for(doc))
        ss["display_key"] = home
        ss["concert_key"] = home
        # Leftovers that previously stole Catalog/Custom backing.
        ss["cpl_active"] = True
        from backing_context import BackingContext, set_backing_context

        set_backing_context(
            ss,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id=HOTEL,
                song_title="Hotel California",
                key="Bm",
                display_key="Bm",
                concert_key="Bm",
                bpm=96,
                style="",
                groove="Auto",
                scope="Full song",
                loops=2,
                progression=["Bm", "F#", "A", "E"],
                progression_label="Hotel California",
                loop=True,
                custom_revision_id=None,
                bound_pick_key=HOTEL,
            ),
        )
        from backing_source_navigation import initialize_active_source_backing_after_restore_miss
        from backing_context import get_backing_context

        initialize_active_source_backing_after_restore_miss(ss, st_like=_FakeSt(ss))
        ctx = get_backing_context(ss)
        self.assertEqual(getattr(ctx, "source", ""), "composition_song")
        self.assertEqual(str(getattr(ctx, "concert_key", "") or ""), home)
        self.assertNotIn("Hotel", str(getattr(ctx, "song_title", "") or ""))
        self.assertEqual(str(ss.get("display_key") or ""), home)

    def test_catalog_pre_hydrate_does_not_rewrite_composition_pick(self) -> None:
        ss = _hotel_catalog_session(practice="Bm")
        doc = _cs_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=True
        )
        comp_pick = composition_pick_key_for(doc)
        from backing_source_navigation import commit_active_catalog_source_before_backing_hydrate

        commit_active_catalog_source_before_backing_hydrate(ss, st_like=_FakeSt(ss))
        self.assertEqual(str(ss.get("active_catalog_pick_key") or ""), comp_pick)
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_COMPOSITION)

    def test_align_live_pick_does_not_overwrite_composition_with_stale_catalog_selected(self) -> None:
        """R1 live defect: Backing remount rewrote composition:: from leftover Say selected_song."""
        ss = _hotel_catalog_session(practice="Bm")
        doc = _cs_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=True
        )
        comp_pick = composition_pick_key_for(doc)
        # Stale Catalog selected_song.pick_key lag (Say/Hotel) after Composition commit.
        ss["selected_song"] = {
            "title": "My Composition",
            "artist": "Composition",
            "pick_key": HOTEL,
            "key": "C#",
        }
        from backing_source_navigation import (
            _align_live_catalog_pick_to_selected_song,
            hydrate_backing_source_for_page,
            mark_generic_catalog_backing_entry,
        )
        from backing_context import get_backing_context

        _align_live_catalog_pick_to_selected_song(ss)
        self.assertEqual(str(ss.get("active_catalog_pick_key") or ""), comp_pick)
        mark_generic_catalog_backing_entry(ss)
        hydrate_backing_source_for_page(ss, st_like=_FakeSt(ss))
        self.assertEqual(str(ss.get("active_catalog_pick_key") or ""), comp_pick)
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_COMPOSITION)
        ctx = get_backing_context(ss)
        self.assertEqual(getattr(ctx, "source", ""), "composition_song")


class TestExplicitUseBackingCommitsSource(unittest.TestCase):
    def test_use_catalog_from_composition_commits_catalog(self) -> None:
        ss = _hotel_catalog_session(practice="A#m")
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=HOTEL,
            selected_song=dict(ss["selected_song"]),
            original_key="Bm",
            display_key="A#m",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        doc = _cs_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=True
        )
        from songs.music_source import switch_to_catalog_from_custom
        from backing_context import get_backing_context, restore_regular_song_backing

        ok = switch_to_catalog_from_custom(
            _FakeSt(ss),
            song_picker_catalog={
                "Rock": {
                    "Hotel California — Eagles": {
                        "title": "Hotel California",
                        "artist": "Eagles",
                        "key": "Bm",
                        "sections": {"Verse": ["Bm", "F#"]},
                    }
                }
            },
            song_library=None,
            invalidate_backing=lambda *_a, **_k: None,
            force=True,
        )
        self.assertTrue(ok)
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        restore_regular_song_backing(ss, st_like=_FakeSt(ss))
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_CATALOG)
        ctx = get_backing_context(ss)
        self.assertEqual(getattr(ctx, "source", ""), "regular_song")
        self.assertNotEqual(getattr(ctx, "source", ""), "composition_song")

    def test_use_custom_from_catalog_commits_custom_at_original(self) -> None:
        ss = _hotel_catalog_session(practice="A#m")
        from backing_context import get_backing_context, restore_custom_song_backing

        restore_custom_song_backing(ss, st_like=_FakeSt(ss))
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_CUSTOM)
        ctx = get_backing_context(ss)
        self.assertEqual(getattr(ctx, "source", ""), "custom_progression")
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertNotEqual(str(ss.get("display_key") or ""), "A#m")


class TestTemporaryCreativeDoesNotCommitTrueSource(unittest.TestCase):
    def test_custom_sbi_preview_keeps_hotel_practice(self) -> None:
        from music_source_ownership import maybe_reset_practice_key_on_source_activation

        ss = _hotel_catalog_session(practice="A#m")
        set_practice_concert_key(ss, "A#m", pick_key=HOTEL, allow_restore_original=True)
        ss[EXPLICIT_SBI_SOURCE_CLICK_KEY] = "Custom progression"
        set_sbi_preview_source(ss, "Custom progression")
        self.assertFalse(maybe_reset_practice_key_on_source_activation(ss, surface="sbi_custom"))
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_CATALOG)
        self.assertEqual(get_practice_concert_key(ss, HOTEL), "A#m")
        self.assertEqual(str(ss.get("display_key") or ""), "A#m")


class TestSidebarCardBackingPracticeAgreement(unittest.TestCase):
    def test_composition_canonical_practice_matches_backing_ctx(self) -> None:
        ss: dict = {}
        doc = _cs_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=True
        )
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "D", pick_key=pick, allow_restore_original=True)
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        from backing_source_navigation import open_backing_for_practice_source
        from backing_context import get_backing_context

        ctx = open_backing_for_practice_source(ss, st_like=_FakeSt(ss))
        self.assertEqual(getattr(ctx, "source", ""), "composition_song")
        self.assertEqual(str(getattr(ctx, "concert_key", "") or ""), "D")
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        self.assertEqual(get_practice_concert_key(ss, pick), "D")
        live = get_backing_context(ss)
        self.assertEqual(str(getattr(live, "concert_key", "") or ""), "D")


if __name__ == "__main__":
    unittest.main()
