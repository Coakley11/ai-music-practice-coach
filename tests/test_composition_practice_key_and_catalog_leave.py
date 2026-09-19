"""Composition Practice Key card + Composition→Catalog leave regressions."""

from __future__ import annotations

import unittest

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_session_state import (
    COMPOSER_LIBRARY_KEY,
    save_document_to_library,
    set_active_document,
)
from composition_songs_bridge import (
    PENDING_COMPOSITION_ACTIVE_SONG_KEY,
    activate_composition_song_from_library,
    composition_home_key,
    composition_pick_key_for,
    commit_composition_active_song,
    queue_composition_active_song_activation,
)
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    composition_song_is_active,
    ensure_composition_owns_active_song,
    music_picker_shows_composition_hub,
    on_song_picker_source_change,
)
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _g_doc(title: str = "Card Key Song") -> dict:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="practice key card",
        title=title,
        key="G major",
        bpm=100,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("G C Em D"))
    return doc


class TestCompositionPracticeKeyCard(unittest.TestCase):
    def test_force_ensure_preserves_practice_key_a(self) -> None:
        """force=True ownership repair must not wipe Practice Key A back to G."""
        ss: dict = {}
        doc = _g_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        ss["display_key"] = "A"
        ss["concert_key"] = "A"
        # Simulate ownership flap that chart-gate force-repairs.
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        ensure_composition_owns_active_song(_FakeSt(ss), force=True)
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        self.assertEqual(composition_home_key(ss[COMPOSER_LIBRARY_KEY][str(doc["id"])]), "G")
        self.assertEqual(str((ss[COMPOSER_LIBRARY_KEY][str(doc["id"])].get("global") or {}).get("original_key_center")), "G")

    def test_sticky_practice_key_for_composition_pick(self) -> None:
        ss: dict = {}
        doc = _g_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        # Deliberate sticky→sticky change requires explicit restore / oneshot
        # (same gate that blocks remount A→C / A→G corruption).
        set_practice_concert_key(ss, "Bb", pick_key=pick, allow_restore_original=True)
        self.assertEqual(get_practice_concert_key(ss, pick), "Bb")
        self.assertEqual(composition_home_key(doc), "G")


class TestCompositionCatalogLeave(unittest.TestCase):
    def test_explicit_catalog_clears_pending_and_hides_hub(self) -> None:
        ss: dict = {
            "song_picker_active_source": "🪶 Composition",
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "explicit_music_source_choice": SOURCE_COMPOSITION,
        }
        doc = _g_doc(title="Leave To Catalog")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        queue_composition_active_song_activation(_FakeSt(ss), str(doc["id"]))
        self.assertTrue(ss.get(PENDING_COMPOSITION_ACTIVE_SONG_KEY) or ss.get("_composition_activation_from_songs_library"))

        ss["song_picker_active_source"] = "Song Selection (catalog song)"
        on_song_picker_source_change(
            _FakeSt(ss),
            song_picker_catalog={"Pop": {}},
            song_library={"Pop": {}},
            invalidate_backing=lambda _s: None,
        )
        self.assertTrue(bool(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY)))
        self.assertEqual(ss.get("explicit_music_source_choice"), SOURCE_CATALOG)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertFalse(str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("composition::"))
        self.assertFalse(composition_song_is_active(ss))
        self.assertFalse(ss.get(PENDING_COMPOSITION_ACTIVE_SONG_KEY))
        self.assertFalse(ss.get("_composition_activation_from_songs_library"))
        self.assertFalse(music_picker_shows_composition_hub(ss))

    def test_stale_catalog_still_yields_to_composition_library_activate(self) -> None:
        """Prior fix: stale Catalog leave must not block Composition activate."""
        ss: dict = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "explicit_music_source_choice": SOURCE_CATALOG,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: "catalog::Pop::Perfect",
            "song_picker_active_source": "🪶 Composition",
        }
        doc = _g_doc(title="Stale Leave Still Works")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        ok = activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        self.assertTrue(ok)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_COMPOSITION)
        self.assertTrue(str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("composition::"))
        self.assertTrue(composition_song_is_active(ss))

    def test_explicit_custom_clears_composition_pending(self) -> None:
        ss: dict = {
            "song_picker_active_source": "🪶 Composition",
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "explicit_music_source_choice": SOURCE_COMPOSITION,
        }
        doc = _g_doc(title="Leave To Custom")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        queue_composition_active_song_activation(_FakeSt(ss), str(doc["id"]))
        ss["song_picker_active_source"] = "Use Custom Progression / Create Your Own Song"
        on_song_picker_source_change(
            _FakeSt(ss),
            song_picker_catalog={"Pop": {}},
            song_library={"Pop": {}},
            invalidate_backing=lambda _s: None,
        )
        self.assertEqual(ss.get("explicit_music_source_choice"), SOURCE_CUSTOM)
        self.assertFalse(ss.get(PENDING_COMPOSITION_ACTIVE_SONG_KEY))
        self.assertFalse(ss.get("_composition_activation_from_songs_library"))

    def test_catalog_composition_catalog_round_trip(self) -> None:
        """Fresh Catalog click after Composition must override; activate still works."""
        ss: dict = {
            "song_picker_active_source": "Song Selection (catalog song)",
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            "explicit_music_source_choice": SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            ACTIVE_CATALOG_PICK_KEY: "catalog::Pop::Perfect",
        }
        doc = _g_doc(title="Round Trip")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        # Catalog → Composition
        ss["song_picker_active_source"] = "🪶 Composition"
        ok = activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        self.assertTrue(ok)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_COMPOSITION)
        pick = str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "")
        self.assertTrue(pick.startswith("composition::"))
        set_practice_concert_key(ss, "A", pick_key=pick)
        # Composition → Catalog (explicit)
        ss["song_picker_active_source"] = "Song Selection (catalog song)"
        on_song_picker_source_change(
            _FakeSt(ss),
            song_picker_catalog={"Pop": {}},
            song_library={"Pop": {}},
            invalidate_backing=lambda _s: None,
        )
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertTrue(bool(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY)))
        self.assertFalse(composition_song_is_active(ss))
        # Explicit leave clears Composition sticky — return starts at home G.
        self.assertFalse(bool(get_practice_concert_key(ss, pick)))
        # Catalog → Composition again
        ss["song_picker_active_source"] = "🪶 Composition"
        ok2 = activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        self.assertTrue(ok2)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_COMPOSITION)
        self.assertEqual(
            get_practice_concert_key(ss, composition_pick_key_for(doc)) or "G",
            "G",
        )

    def test_composition_radio_from_catalog_resets_practice_to_home(self) -> None:
        """Catalog → Composition radio resets Practice to Original G (not old A)."""
        ss: dict = {}
        doc = _g_doc(title="Radio Reset PK")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        # Leave to Catalog (empty catalog ok after leave scrub).
        ss["song_picker_active_source"] = "Song Selection (catalog song)"
        on_song_picker_source_change(
            _FakeSt(ss),
            song_picker_catalog={"Pop": {}},
            song_library={"Pop": {}},
            invalidate_backing=lambda _s: None,
        )
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        # Return via Composition radio (no library re-click).
        ss["song_picker_active_source"] = "🪶 Composition"
        on_song_picker_source_change(
            _FakeSt(ss),
            song_picker_catalog={"Pop": {}},
            song_library={"Pop": {}},
            invalidate_backing=lambda _s: None,
        )
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_COMPOSITION)
        self.assertEqual(get_practice_concert_key(ss, pick) or "G", "G")
        self.assertEqual(str(ss.get("display_key") or ""), "G")

    def test_library_reactivate_from_catalog_resets_practice_to_home(self) -> None:
        """Catalog pick → re-select Composition library row resets Practice to G."""
        ss: dict = {}
        doc = _g_doc(title="Library Reactivate PK")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        ss[ACTIVE_CATALOG_PICK_KEY] = "catalog::Pop::Say"
        ss["explicit_music_source_choice"] = SOURCE_CATALOG
        ok = activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        self.assertTrue(ok)
        self.assertEqual(get_practice_concert_key(ss, pick) or "G", "G")
        self.assertEqual(composition_home_key(ss[COMPOSER_LIBRARY_KEY][str(doc["id"])]), "G")

    def test_catalog_apply_clears_composition_sticky(self) -> None:
        """apply_pick_key Catalog switch clears composition:: Practice sticky."""
        from songs.state import apply_pick_key

        ss: dict = {}
        doc = _g_doc(title="Sticky Cleared On Catalog")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        # Simulate Catalog song apply after Composition (prev=composition::).
        ss[ACTIVE_CATALOG_PICK_KEY] = pick
        catalog = {
            "Pop": {
                "Say — John Mayer": {
                    "title": "Say",
                    "artist": "John Mayer",
                    "key": "G",
                    "sections": {"Verse": ["G", "C"]},
                }
            }
        }
        # apply_pick_key needs streamlit-ish st
        apply_pick_key(
            _FakeSt(ss),
            "Pop\x1fSay — John Mayer",
            catalog,
            skip_activity_log=True,
            origin="user",
        )
        self.assertFalse(bool(get_practice_concert_key(ss, pick)))


if __name__ == "__main__":
    unittest.main()
