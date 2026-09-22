"""Phase D: Composition Practice Key ownership, Studio identity, Custom Original Key."""

from __future__ import annotations

import unittest
from pathlib import Path

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_session_state import (
    COMPOSER_LIBRARY_KEY,
    get_active_document,
    list_library_documents,
    save_document_to_library,
    set_active_document,
)
from composition_songs_bridge import (
    activate_composition_by_pick_key,
    commit_composition_active_song,
    commit_composition_owned_practice_key,
    composition_home_key,
    composition_pick_key_for,
    ensure_generic_composition_document,
    resolve_composition_canonical_keys,
)
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
)
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _c_doc(title: str = "My Composition") -> dict:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="phase d",
        title=title,
        key="C major",
        bpm=96,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C Am F G"))
    return doc


def _second_doc(title: str = "Second Composition") -> dict:
    doc = bootstrap_from_vision(
        genre="Rock",
        song_idea="phase d second",
        title=title,
        key="G major",
        bpm=110,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("G Em C D"))
    return doc


class PhaseD1CompositionPracticeKey(unittest.TestCase):
    def test_new_composition_practice_equals_original_not_catalog_g(self) -> None:
        ss: dict = {
            "display_key": "G",
            "concert_key": "G",
            "active_catalog_pick_key": "Pop\x1fPerfect — Ed Sheeran",
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            PRACTICE_KEY_BY_SOURCE_KEY: {"Pop\x1fPerfect — Ed Sheeran": "G"},
            "active_song_state": {
                "pick_key": "Pop\x1fPerfect — Ed Sheeran",
                "display_key": "G",
            },
        }
        st = _FakeSt(ss)
        doc = ensure_generic_composition_document(ss)
        self.assertEqual(composition_home_key(doc), "C")
        commit_composition_active_song(st, doc, reset_practice_to_original=True)
        home, practice = resolve_composition_canonical_keys(ss, doc)
        self.assertEqual(home, "C")
        self.assertEqual(practice, "C")
        self.assertNotEqual(practice, "G")
        pick = composition_pick_key_for(doc)
        self.assertTrue(pick.startswith("composition::"), pick)
        # No UUID-scoped override yet → store may be empty or C, never G.
        saved = str(get_practice_concert_key(ss, pick, default="") or "").strip()
        self.assertIn(saved, {"", "C"})

    def test_practice_c_to_f_keeps_original_c_and_uuid_store(self) -> None:
        ss: dict = {}
        st = _FakeSt(ss)
        doc = _c_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(st, doc, reset_practice_to_original=True)
        pick = composition_pick_key_for(doc)
        commit_composition_owned_practice_key(ss, "F")
        home, practice = resolve_composition_canonical_keys(ss, doc)
        self.assertEqual(home, "C")
        self.assertEqual(practice, "F")
        self.assertEqual(get_practice_concert_key(ss, pick), "F")
        authored = str((ss[COMPOSER_LIBRARY_KEY][str(doc["id"])].get("global") or {}).get("original_key_center") or "")
        self.assertEqual(authored, "C")
        self.assertEqual(composition_home_key(ss[COMPOSER_LIBRARY_KEY][str(doc["id"])]), "C")

    def test_second_composition_independent_practice_keys(self) -> None:
        ss: dict = {}
        st = _FakeSt(ss)
        a = _c_doc("My Composition")
        b = _second_doc()
        set_active_document(ss, a, checkpoint=False)
        save_document_to_library(ss, a)
        commit_composition_active_song(st, a, reset_practice_to_original=True)
        pick_a = composition_pick_key_for(a)
        set_practice_concert_key(ss, "F", pick_key=pick_a, allow_restore_original=True, commit_catalog_practice_key=True)

        set_active_document(ss, b, checkpoint=False)
        save_document_to_library(ss, b)
        commit_composition_active_song(st, b, reset_practice_to_original=True)
        pick_b = composition_pick_key_for(b)
        home_b, practice_b = resolve_composition_canonical_keys(ss, b)
        self.assertEqual(home_b, "G")
        self.assertEqual(practice_b, "G")
        self.assertEqual(get_practice_concert_key(ss, pick_a), "F")
        self.assertNotEqual(get_practice_concert_key(ss, pick_b) or "G", "F")

        activate_composition_by_pick_key(st, pick_a)
        home_a, practice_a = resolve_composition_canonical_keys(ss, a)
        self.assertEqual(home_a, "C")
        self.assertEqual(practice_a, "F")

    def test_catalog_display_key_does_not_seed_composition_card(self) -> None:
        from songs.key_state import get_authoritative_display_key

        ss: dict = {
            "display_key": "G",
            "concert_key": "G",
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
        }
        st = _FakeSt(ss)
        doc = _c_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(st, doc, reset_practice_to_original=True)
        # Pollute live keys again as if Perfect G leaked.
        ss["display_key"] = "G"
        ss["concert_key"] = "G"
        auth = get_authoritative_display_key(ss, original_key="C")
        self.assertEqual(auth, "C")

    def test_hydrate_composition_practice_key_exists_and_queues(self) -> None:
        from composition_songs_bridge import hydrate_composition_practice_key

        ss: dict = {"display_key": "C", "concert_key": "C"}
        st = _FakeSt(ss)
        doc = _c_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(st, doc, reset_practice_to_original=True)
        hydrate_composition_practice_key(ss, "F")
        self.assertEqual(ss.get("concert_key"), "F")
        pending = str(ss.get("_pending_display_key") or ss.get("display_key") or "").strip()
        self.assertEqual(pending, "F")

    def test_capo_sounding_follows_composition_practice_not_catalog_g(self) -> None:
        from guitar_capo import live_capo_shape_source_id, owner_guitar_concert_key

        ss: dict = {
            "display_key": "G",
            "concert_key": "G",
            "active_catalog_pick_key": "Pop\x1fPerfect — Ed Sheeran",
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            PRACTICE_KEY_BY_SOURCE_KEY: {"Pop\x1fPerfect — Ed Sheeran": "G"},
            "studio_page": "picker",
            "instrument": "Guitar",
        }
        st = _FakeSt(ss)
        doc = _c_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(st, doc, reset_practice_to_original=True)
        commit_composition_owned_practice_key(ss, "F")
        # Lag Catalog pick while Composition owns the song — Capo must still follow UUID F.
        ss["active_catalog_pick_key"] = "Pop\x1fPerfect — Ed Sheeran"
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
        live = live_capo_shape_source_id(ss)
        self.assertTrue(str(live).startswith("composition::"), live)
        self.assertEqual(owner_guitar_concert_key(ss, fallback="G"), "F")


class PhaseD2StudioIdentity(unittest.TestCase):
    def test_identity_header_from_loaded_document(self) -> None:
        from composition_studio_page import _composition_identity_header

        doc = _c_doc("My Composition")
        header = _composition_identity_header(doc)
        self.assertIn("My Composition", header)
        self.assertIn("Pop", header)
        self.assertRegex(header, r"C\s+major", header)

    def test_library_active_uuid_singular(self) -> None:
        from composition_session_state import load_library_document

        ss: dict = {}
        a = _c_doc("My Composition")
        b = _second_doc()
        set_active_document(ss, a, checkpoint=False)
        save_document_to_library(ss, a)
        save_document_to_library(ss, b)
        id_a = str(a.get("id") or "")
        id_b = str(b.get("id") or "")
        self.assertNotEqual(id_a, id_b)
        # Saving B installs B as active (same handoff as library Open).
        self.assertEqual(str((get_active_document(ss) or {}).get("id") or ""), id_b)
        loaded_a = load_library_document(ss, id_a)
        self.assertIsInstance(loaded_a, dict)
        active = get_active_document(ss)
        self.assertEqual(str((active or {}).get("id") or ""), id_a)
        rows = list_library_documents(ss)
        self.assertEqual(sum(1 for r in rows if str(r.get("id") or "") == id_a), 1)
        self.assertEqual(sum(1 for r in rows if str(r.get("id") or "") == id_b), 1)

    def test_resave_same_uuid_no_duplicate(self) -> None:
        ss: dict = {}
        doc = _c_doc("My Composition")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        uid = str(doc.get("id") or "")
        doc["title"] = "My Composition"
        save_document_to_library(ss, doc)
        rows = [r for r in list_library_documents(ss) if str(r.get("id") or "") == uid]
        self.assertEqual(len(rows), 1)
        titles = [str(r.get("title") or "") for r in list_library_documents(ss)]
        self.assertEqual(titles.count("My Composition"), 1)


class PhaseD3CustomOriginalKey(unittest.TestCase):
    def test_quick_key_grid_removed_from_cpl_page(self) -> None:
        text = Path("cpl_page_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("cpl_orig_chip_", text)
        self.assertNotIn("CPL_QUICK_ORIGINAL_MAJORS", text)
        self.assertIn("Choose the Original Key, then Save to library.", text)
        self.assertIn('feature_label("original_key", "Original Key")', text)


if __name__ == "__main__":
    unittest.main()
