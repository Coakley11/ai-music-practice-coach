"""Composition original/home key must satisfy chart transpose (not Catalog/Custom)."""

from __future__ import annotations

import copy
import unittest

from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    section_melody_events,
)
from composition_session_state import (
    COMPOSER_LIBRARY_KEY,
    save_document_to_library,
    set_active_document,
)
from composition_songs_bridge import (
    composition_home_key,
    composition_pick_key_for,
    commit_composition_active_song,
    ensure_composition_library_hydrated,
)
from composition_workspace_state_persistence import COMPOSITION_WORKSPACE_STATE_KEY
from music_theory import MissingOriginalSongKeyError, transpose_chord
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    build_active_chart_bundle,
    composition_song_is_active,
)


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss


def _g_major_doc(*, title: str = "G Major Library Song") -> dict:
    doc = bootstrap_from_vision(
        genre="Bossa",
        song_idea="key contract",
        title=title,
        key="G major",
        bpm=112,
    )
    apply_structure_template(doc, "simple")
    v = ordered_sections(doc)[0]
    apply_section_chords(doc, str(v["id"]), parse_chord_paste("G C Em D"))
    apply_melody_events(
        doc,
        str(v["id"]),
        [
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "B4", "midi": 71, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ],
        replace=True,
    )
    return doc


def _a_minor_doc() -> dict:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="minor key contract",
        title="A Minor Library Song",
        key="A minor",
        bpm=96,
    )
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("Am Dm Em Am"))
    return doc


def _transpose_sections(song_data: dict, display_key: str) -> dict:
    """Minimal transpose for tests — chord symbols only."""
    from music_theory import semitone_distance

    home = str(song_data.get("key") or song_data.get("original_key") or "C")
    steps = semitone_distance(home, display_key)
    out: dict = {}
    for label, chords in (song_data.get("sections") or {}).items():
        if isinstance(chords, list):
            out[label] = [
                transpose_chord(str(c), steps, reference_key=home) if isinstance(c, str) else c
                for c in chords
            ]
        else:
            out[label] = chords
    return out


def _build(ss: dict, *, display_key: str = "G") -> dict:
    return build_active_chart_bundle(
        ss,
        catalog_genre="Pop",
        catalog_song="****",
        catalog_song_data={"title": "****", "genre": "Pop", "key": ""},
        level="Intermediate",
        display_key=display_key,
        cpl_active_key="cpl_active_progression",
        sections_for_level=lambda data, _level: dict(data.get("sections") or {}),
        transpose_sections=_transpose_sections,
    )


class TestCompositionChartOriginalKey(unittest.TestCase):
    def test_saved_composition_supplies_home_key_to_chart(self) -> None:
        ss: dict = {}
        doc = _g_major_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        bundle = _build(ss, display_key="G")
        self.assertEqual(bundle.get("source"), SOURCE_COMPOSITION)
        self.assertEqual(bundle.get("original_key"), "G")
        self.assertEqual((bundle.get("song_data") or {}).get("key"), "G")
        self.assertNotIn("_chart_song_resolve_diag", ss)

    def test_composition_pick_routes_even_when_catalog_stamps_linger(self) -> None:
        """composition:: pick must not fall through to Catalog missing-key path."""
        doc = _g_major_doc()
        ss: dict = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,  # stale
            "active_catalog_pick_key": composition_pick_key_for(doc),
            COMPOSER_LIBRARY_KEY: {str(doc["id"]): doc},
            "selected_song": {
                "pick_key": composition_pick_key_for(doc),
                "title": "G Major Library Song",
                "key": "G",
                "source": SOURCE_COMPOSITION,
                "is_composition": True,
                "composition_id": str(doc["id"]),
            },
            "display_key": "G",
        }
        # No USER_CATALOG / explicit catalog leave — pick identity wins.
        bundle = _build(ss, display_key="G")
        self.assertEqual(bundle.get("original_key"), "G")
        self.assertEqual(bundle.get("source"), SOURCE_COMPOSITION)

    def test_explicit_catalog_leave_still_uses_catalog_guard(self) -> None:
        """Catalog without a resolvable original key still raises (guard unchanged)."""
        from songs.catalog_song_resolution import resolve_catalog_song_for_chart

        partial = {"title": "****", "genre": "Pop", "sections": {"Verse": ["C"]}}
        session = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            "explicit_music_source_choice": SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "selected_song": partial,
        }
        with self.assertRaises(MissingOriginalSongKeyError):
            resolve_catalog_song_for_chart(
                session,
                partial,
                song_picker_catalog={"Pop": {}},
                song_library={"Pop": {}},
            )
        self.assertIn("_chart_song_resolve_diag", session)

    def test_custom_without_home_key_still_raises(self) -> None:
        from custom_progression_lab import default_active_progression
        from unittest import mock

        active = default_active_progression()
        active["id"] = "demo"
        active["name"] = "No Home"
        active["original_key_center"] = ""
        active["original_sections"] = {
            "Verse": [{"chord": "C", "beats": 4}, {"chord": "G", "beats": 4}],
        }
        ss: dict = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "explicit_music_source_choice": SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::demo",
            "cpl_active_progression": active,
            "display_key": "C",
            "song_picker_active_source": "Use Custom Progression / Create Your Own Song",
        }
        with mock.patch("songs.music_source.custom_original_key", return_value=""):
            with self.assertRaises(MissingOriginalSongKeyError):
                _build(ss, display_key="C")

    def test_practice_transpose_uses_composition_home_delta(self) -> None:
        ss: dict = {}
        doc = _g_major_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        # Saved document stays G; practice display A → chords transpose G→A.
        saved_chords_before = copy.deepcopy(
            ordered_sections(ss[COMPOSER_LIBRARY_KEY][str(doc["id"])])[0].get("chords")
        )
        bundle = _build(ss, display_key="A")
        self.assertEqual(bundle.get("original_key"), "G")
        # Level source stays at Composition home.
        home_sections = bundle.get("level_source_sections") or {}
        first_label = next(iter(home_sections))
        self.assertIn("G", str(home_sections[first_label]))
        sounding = bundle.get("sections") or {}
        sounding_first = next(iter(sounding.values()))
        self.assertTrue(any("A" == str(c) or str(c).startswith("A") for c in sounding_first))
        # Library document unchanged.
        after = ordered_sections(ss[COMPOSER_LIBRARY_KEY][str(doc["id"])])[0].get("chords")
        self.assertEqual(after, saved_chords_before)
        mel_before = section_melody_events(ordered_sections(doc)[0])
        mel_after = section_melody_events(
            ordered_sections(ss[COMPOSER_LIBRARY_KEY][str(doc["id"])])[0]
        )
        self.assertEqual(mel_after, mel_before)

    def test_minor_key_composition(self) -> None:
        ss: dict = {}
        doc = _a_minor_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        self.assertEqual(composition_home_key(doc), "Am")
        bundle = _build(ss, display_key="Am")
        self.assertEqual(bundle.get("original_key"), "Am")

    def test_workspace_hydration_supplies_key(self) -> None:
        ss: dict = {}
        doc = _g_major_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        fresh = {
            COMPOSITION_WORKSPACE_STATE_KEY: copy.deepcopy(ss[COMPOSITION_WORKSPACE_STATE_KEY]),
            "active_catalog_pick_key": composition_pick_key_for(doc),
            "selected_song": {
                "pick_key": composition_pick_key_for(doc),
                "is_composition": True,
                "source": SOURCE_COMPOSITION,
                "composition_id": str(doc["id"]),
                "title": "G Major Library Song",
            },
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "explicit_music_source_choice": SOURCE_COMPOSITION,
            "display_key": "G",
        }
        ensure_composition_library_hydrated(fresh)
        bundle = _build(fresh, display_key="G")
        self.assertEqual(bundle.get("original_key"), "G")

    def test_page_snapshot_hydration_supplies_key(self) -> None:
        doc = _g_major_doc()
        sid = str(doc["id"])
        fresh = {
            COMPOSER_LIBRARY_KEY: {},
            COMPOSITION_WORKSPACE_STATE_KEY: {"schema_version": 1, "library": {}},
            "_studio_page_snapshots": {
                "composer": {COMPOSER_LIBRARY_KEY: {sid: copy.deepcopy(doc)}}
            },
            "active_catalog_pick_key": f"composition::{sid}",
            "selected_song": {
                "pick_key": f"composition::{sid}",
                "is_composition": True,
                "source": SOURCE_COMPOSITION,
                "composition_id": sid,
            },
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "explicit_music_source_choice": SOURCE_COMPOSITION,
            "display_key": "G",
        }
        ensure_composition_library_hydrated(fresh)
        bundle = _build(fresh, display_key="G")
        self.assertEqual(bundle.get("original_key"), "G")

    def test_global_transpose_before_save_uses_new_canonical_key(self) -> None:
        ss: dict = {}
        doc = bootstrap_from_vision(
            genre="Pop", song_idea="x", title="E After Transpose", key="C major", bpm=100
        )
        apply_structure_template(doc, "simple")
        apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C Am F G"))
        # Composition Studio global key change updates canonical original fields.
        doc["global"]["original_key_center"] = "E"
        doc["global"]["original_key_label"] = "E major"
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        bundle = _build(ss, display_key="E")
        self.assertEqual(bundle.get("original_key"), "E")
        self.assertEqual(composition_home_key(ss[COMPOSER_LIBRARY_KEY][str(doc["id"])]), "E")

    def test_practice_key_does_not_mutate_saved_original(self) -> None:
        ss: dict = {}
        doc = _g_major_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
        ss["display_key"] = "Bb"
        ss["concert_key"] = "Bb"
        _build(ss, display_key="Bb")
        saved = ss[COMPOSER_LIBRARY_KEY][str(doc["id"])]
        self.assertEqual(composition_home_key(saved), "G")
        self.assertEqual(str((saved.get("global") or {}).get("original_key_center")), "G")


class TestCompositionSongsToChartStateTransition(unittest.TestCase):
    """Cross the Songs → composition:: → chart-gate boundary (live bug path)."""

    def test_library_activate_then_chart_with_stale_catalog_leave(self) -> None:
        from composition_songs_bridge import activate_composition_song_from_library
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss: dict = {
            # Stale Catalog leave stamps — the live failure mode after Songs→Composition.
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "explicit_music_source_choice": SOURCE_CATALOG,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: "catalog::Pop::Perfect",
            "selected_song": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "key": "",
                "pick_key": "catalog::Pop::Perfect",
                "source": SOURCE_CATALOG,
            },
            "display_key": "C",
            "song_picker_active_source": "🪶 Composition",
        }
        doc = _g_major_doc(title="Key Runtime Test")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)

        ok = activate_composition_song_from_library(_FakeSt(ss), str(doc["id"]))
        self.assertTrue(ok)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_COMPOSITION)
        self.assertTrue(str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("composition::"))
        self.assertFalse(bool(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY)))
        self.assertEqual(composition_home_key(doc), "G")

        bundle = _build(ss, display_key="G")
        self.assertEqual(bundle.get("source"), SOURCE_COMPOSITION)
        self.assertEqual(bundle.get("original_key"), "G")
        self.assertTrue(composition_song_is_active(ss))

    def test_pending_not_discarded_by_stale_user_catalog(self) -> None:
        from composition_songs_bridge import (
            PENDING_COMPOSITION_ACTIVE_SONG_KEY,
            apply_pending_composition_active_song_activation_before_widgets,
            queue_composition_active_song_activation,
        )
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss: dict = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "explicit_music_source_choice": SOURCE_CATALOG,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: "catalog::Pop::Perfect",
            "song_picker_active_source": "🪶 Composition",
        }
        doc = _g_major_doc(title="Pending Key Test")
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        queue_composition_active_song_activation(_FakeSt(ss), str(doc["id"]))
        self.assertTrue(ss.get("_composition_activation_from_songs_library"))
        ok = apply_pending_composition_active_song_activation_before_widgets(_FakeSt(ss))
        self.assertTrue(ok)
        self.assertFalse(ss.get(PENDING_COMPOSITION_ACTIVE_SONG_KEY))
        self.assertTrue(str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("composition::"))
        bundle = _build(ss, display_key="G")
        self.assertEqual(bundle.get("original_key"), "G")

    def test_songs_card_original_uses_composition_home_not_catalog_g(self) -> None:
        """Screenshot split: card read leftover Catalog G; sidebar/Backing used document C."""
        from composition_songs_bridge import composition_source_original_key
        from songs.music_source import resolve_active_song_keys

        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="home C",
            title="My Composition",
            key="C major",
            bpm=96,
        )
        apply_structure_template(doc, "simple")
        apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C Am F G"))
        set_active_document(ss := {}, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
        catalog_pick = "Pop\x1fSay — John Mayer"
        ss["active_catalog_pick_key"] = catalog_pick
        ss["selected_song"] = {"pick_key": catalog_pick, "key": "G", "title": "Say"}
        rec = {
            "pick_key": composition_pick_key_for(doc),
            "source": "Composition",
            "key": composition_source_original_key(doc),
            "title": "My Composition",
        }
        original, _display, _written = resolve_active_song_keys(ss, rec)
        self.assertEqual(composition_source_original_key(doc), "C")
        self.assertEqual(str((doc.get("global") or {}).get("original_key_center")), "C")
        self.assertEqual(original, "C")
        # Practice change must not rewrite home.
        doc["global"]["practice_key"] = "C#"
        self.assertEqual(composition_source_original_key(doc), "C")


if __name__ == "__main__":
    unittest.main()
