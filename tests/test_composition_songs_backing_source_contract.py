"""Source-identity contract: Composition/Catalog Practice Key + Backing ownership.

Reproduces live 8524 failures:
  A) Composition Practice A wiped to home G on Songs↔Backing
  B) Catalog Shape of You opens Backing as Composition with Catalog's C minor
"""

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
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SONG_PICKER_ACTIVE_SOURCE_KEY,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    commit_catalog_active_song,
    commit_explicit_music_source_choice,
    song_picker_composition_option_label,
)
from songs.practice_key_state import (
    get_practice_concert_key,
    set_practice_concert_key,
)
from songs.key_state import note_display_key_change


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _g_doc(title: str = "Contract Song") -> dict:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="source contract",
        title=title,
        key="G major",
        bpm=100,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("G C Em D"))
    return doc


class TestCompositionPracticeKeySongsBacking(unittest.TestCase):
    def test_1_songs_to_backing_keeps_practice_a(self) -> None:
        ss: dict = {}
        doc = _g_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        ss["display_key"] = "A"
        ss["concert_key"] = "A"
        ss["studio_page"] = "picker"
        ss["_force_composition_backing_open"] = True

        from backing_source_navigation import open_backing_for_practice_source
        from backing_context import get_backing_context

        ctx = open_backing_for_practice_source(ss, st_like=_FakeSt(ss))
        self.assertIsNotNone(ctx)
        self.assertEqual(getattr(ctx, "source", ""), "composition_song")
        self.assertEqual(getattr(ctx, "concert_key", ""), "A")
        self.assertEqual(getattr(ctx, "key", ""), "G")
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        live = get_backing_context(ss)
        self.assertEqual(getattr(live, "concert_key", ""), "A")

    def test_2_backing_home_remount_does_not_wipe_sticky_a(self) -> None:
        """note_display_key_change remount with home G must not overwrite sticky A."""
        ss: dict = {}
        doc = _g_doc(title="Remount Guard")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)
        ss["display_key"] = "A"
        ss["concert_key"] = "A"
        ss["_last_app_display_key"] = "A"
        ss["studio_page"] = "backing"
        # Simulate Streamlit remount reseeding the widget to home G.
        ss["display_key"] = "G"
        note_display_key_change(_FakeSt(ss), "G")
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        self.assertEqual(composition_home_key(doc), "G")

    def test_3_catalog_shape_outranks_stale_composition_backing(self) -> None:
        """USER_CATALOG + catalog pick must open Catalog Backing even if radio lags."""
        ss: dict = {}
        doc = _g_doc(title="Leave Comp")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=pick)

        # Lagging Composition radio + stale force/stamp after Catalog leave.
        ss[SONG_PICKER_ACTIVE_SOURCE_KEY] = song_picker_composition_option_label()
        ss["_force_composition_backing_open"] = True
        ss["_practice_loop_backing"] = {"owner": "composition", "pick_key": pick}
        ss["active_song_state"] = {
            "music_source": SOURCE_COMPOSITION,
            "pick_key": pick,
        }

        # Catalog Shape selection identity + Practice C minor.
        shape_pick = "Pop\x1fShape of You"
        ss["active_catalog_pick_key"] = shape_pick
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        ss["display_key"] = "Cm"
        ss["concert_key"] = "Cm"
        set_practice_concert_key(ss, "Cm", pick_key=shape_pick)
        ss["selected_song"] = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "C#m",
            "pick_key": shape_pick,
        }
        ss["_reconcile_song_picker_catalog"] = {
            "Pop": {
                "Shape of You": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "C#m",
                    "sections": {"Verse": ["C#m", "F#m"]},
                }
            }
        }

        from backing_source_navigation import open_backing_for_practice_source
        from music_source_ownership import intended_practice_owner

        self.assertEqual(intended_practice_owner(ss), "catalog")
        ctx = open_backing_for_practice_source(ss, st_like=_FakeSt(ss))
        self.assertIsNotNone(ctx)
        self.assertEqual(getattr(ctx, "source", ""), "regular_song")
        title = str(getattr(ctx, "song_title", "") or "")
        self.assertIn("Shape", title)
        self.assertNotEqual(getattr(ctx, "source", ""), "composition_song")
        # Composition sticky preserved independently.
        self.assertEqual(get_practice_concert_key(ss, pick), "A")
        self.assertEqual(get_practice_concert_key(ss, shape_pick), "Cm")

    def test_4_song_switch_resets_practice_to_original(self) -> None:
        """Explicit Catalog/Composition selection resets Practice to home."""
        ss: dict = {}
        doc = _g_doc(title="Sticky Round Trip")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        comp_pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "A", pick_key=comp_pick)
        shape_pick = "Pop\x1fShape of You"
        shape_sel = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": shape_pick,
            "sections": {"Verse": ["Bm", "Em"]},
        }
        commit_catalog_active_song(
            _FakeSt(ss),
            pick_key=shape_pick,
            selected_song=shape_sel,
            original_key="Bm",
            display_key="A",
            invalidate_backing=lambda *_a, **_k: None,
            reason="catalog_pick",
        )
        self.assertEqual(str(ss.get("display_key") or ""), "Bm")
        self.assertFalse(bool(get_practice_concert_key(ss, comp_pick)))
        from composition_songs_bridge import activate_composition_by_pick_key

        activate_composition_by_pick_key(_FakeSt(ss), comp_pick)
        self.assertEqual(get_practice_concert_key(ss, comp_pick) or "G", "G")
        self.assertEqual(str(ss.get("display_key") or ""), "G")


if __name__ == "__main__":
    unittest.main()
