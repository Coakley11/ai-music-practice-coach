"""True Composition activation must init Practice to Original, not prior Catalog/Custom."""

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
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    SOURCE_COMPOSITION,
    ensure_composition_owns_active_song,
)
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)


DAUGHTERS = format_pick_key("Pop", "Daughters — John Mayer")
TRIAL = "custom::trial-comp-init"


class _FakeSt:
    def __init__(self, ss: dict) -> None:
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _sharp_doc():
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="sharp",
        title="My Composition",
        key="C# major",
        bpm=100,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(
        doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C# F# G#m B")
    )
    return doc


class TestCatalogToCompositionInitsOriginal(unittest.TestCase):
    def test_ensure_from_catalog_d_resets_to_csharp(self) -> None:
        ss: dict = {
            "studio_page": "picker",
            "instrument": "Guitar",
            "active_catalog_pick_key": DAUGHTERS,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            "selected_song": {
                "title": "Daughters",
                "artist": "John Mayer",
                "key": "D",
                "pick_key": DAUGHTERS,
            },
            "original_key": "D",
            "display_key": "D",
            "concert_key": "D",
            PRACTICE_KEY_BY_SOURCE_KEY: {DAUGHTERS: "D"},
            # Catalog just committed D — this refused Composition seal before the fix.
            "_pk_user_commit_token": "D",
            "_pk_user_commit_at": __import__("time").time(),
            "_composition_reset_practice_on_ensure": True,
        }
        doc = _sharp_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        # Stale prior Composition sticky must not win either.
        set_practice_concert_key(ss, "D", pick_key=pick, allow_restore_original=True)

        out = ensure_composition_owns_active_song(
            _FakeSt(ss), invalidate_backing=lambda *_a, **_k: None
        )
        self.assertIsNotNone(out)
        self.assertEqual(composition_home_key(doc), "C#")
        self.assertEqual(str(ss.get(ACTIVE_MUSIC_SOURCE_KEY) or ""), SOURCE_COMPOSITION)
        self.assertEqual(str(ss.get("display_key") or ""), "C#")
        self.assertEqual(str(ss.get("concert_key") or ""), "C#")
        self.assertEqual(get_practice_concert_key(ss, pick) or "C#", "C#")
        self.assertNotEqual(str(ss.get("display_key") or ""), "D")

    def test_commit_reset_seals_over_catalog_commit_token(self) -> None:
        ss: dict = {
            "display_key": "E",
            "concert_key": "E",
            "active_catalog_pick_key": DAUGHTERS,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            "_pk_user_commit_token": "E",
            "_pk_user_commit_at": __import__("time").time(),
        }
        doc = _sharp_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=True
        )
        self.assertEqual(str(ss.get("display_key") or ""), "C#")
        self.assertEqual(get_practice_concert_key(ss, pick) or "C#", "C#")
        self.assertNotEqual(ss.get("_pk_user_commit_token"), "E")


class TestCustomToCompositionInitsOriginal(unittest.TestCase):
    def test_ensure_from_custom_f_resets_to_csharp(self) -> None:
        ss: dict = {
            "studio_page": "picker",
            "instrument": "Guitar",
            "active_catalog_pick_key": TRIAL,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "display_key": "F",
            "concert_key": "F",
            "original_key": "D",
            PRACTICE_KEY_BY_SOURCE_KEY: {TRIAL: "F"},
            "_pk_user_commit_token": "F",
            "_pk_user_commit_at": __import__("time").time(),
            "cpl_active_progression": {
                "id": "trial-comp-init",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 4}]},
            },
        }
        doc = _sharp_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)

        ensure_composition_owns_active_song(
            _FakeSt(ss), invalidate_backing=lambda *_a, **_k: None
        )
        self.assertEqual(str(ss.get("display_key") or ""), "C#")
        self.assertEqual(get_practice_concert_key(ss, pick) or "C#", "C#")
        self.assertNotEqual(str(ss.get("display_key") or ""), "F")


class TestCompositionBackingUsesCanonicalPractice(unittest.TestCase):
    def test_backing_state_prefers_composition_home_over_foreign_display(self) -> None:
        from backing_context import BackingContext
        from backing_musical_state import resolve_current_backing_musical_state

        ss: dict = {
            "display_key": "D",
            "concert_key": "D",
            "active_catalog_pick_key": "composition::sharp",
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            PRACTICE_KEY_BY_SOURCE_KEY: {},  # empty sticky after clear-only reset
        }
        ctx = BackingContext(
            source="composition_song",
            source_label="Composition",
            active_song_id="composition::sharp",
            song_title="My Composition",
            key="C#",
            display_key="C#",
            concert_key="C#",
            bpm=100,
            style="Pop",
            groove="Straight",
            bound_pick_key="composition::sharp",
        )
        from backing_context import set_backing_context

        set_backing_context(ss, ctx)
        state = resolve_current_backing_musical_state(ss)
        self.assertEqual(str(state.practice_concert_key or ""), "C#")
        self.assertNotEqual(str(state.practice_concert_key or ""), "D")


class TestManualCompositionEditThenReactivate(unittest.TestCase):
    def test_manual_d_then_true_reactivate_resets_csharp(self) -> None:
        ss: dict = {
            "display_key": "C#",
            "concert_key": "C#",
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
        }
        doc = _sharp_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=True
        )
        set_practice_concert_key(ss, "D", pick_key=pick, allow_restore_original=True)
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        # Continuous same-pick remount keeps D
        commit_composition_active_song(
            _FakeSt(ss), doc, invalidate_backing=lambda *_a, **_k: None, reset_practice_to_original=False
        )
        self.assertEqual(str(ss.get("display_key") or ""), "D")
        # True leave to Catalog then reactivate
        ss["active_catalog_pick_key"] = DAUGHTERS
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
        ss["display_key"] = "D"
        ss["_pk_user_commit_token"] = "D"
        ss["_pk_user_commit_at"] = __import__("time").time()
        ensure_composition_owns_active_song(
            _FakeSt(ss), invalidate_backing=lambda *_a, **_k: None
        )
        self.assertEqual(str(ss.get("display_key") or ""), "C#")
        self.assertEqual(get_practice_concert_key(ss, pick) or "C#", "C#")


if __name__ == "__main__":
    unittest.main()
