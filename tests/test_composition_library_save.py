"""Save to Composition Library — upsert, workspace mirror, Songs bridge, isolation."""

from __future__ import annotations

import copy
import time
import unittest

from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    playback_globals,
    section_melody_events,
)
from composition_melody_repeats import get_melody_repeats, set_section_melody_repeats
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_LIBRARY_KEY,
    COMPOSER_LAST_LIBRARY_SAVE_KEY,
    get_active_document,
    last_library_save_meta,
    library_save_success_message,
    list_library_documents,
    load_library_document,
    save_document_to_library,
    set_active_document,
)
from composition_songs_bridge import (
    composition_home_key,
    composition_id_from_pick_key,
    composition_pick_key_for,
    composition_selected_song_record,
    ensure_composition_library_hydrated,
    find_composition_document,
    list_composition_songs_for_picker,
)
from composition_workspace_state_persistence import (
    COMPOSITION_WORKSPACE_STATE_KEY,
    gather_composition_workspace_from_session,
)


def _partial_bossa_doc(*, title: str = "Library Test Song") -> dict:
    doc = bootstrap_from_vision(
        genre="Bossa",
        song_idea="Soft bossa library proof",
        title=title,
        mood="warm",
        energy="medium",
        key="G major",
        bpm=112,
        meter="4/4",
    )
    apply_structure_template(doc, "simple")
    secs = ordered_sections(doc)
    verse = secs[0]
    chorus = next(
        (
            s
            for s in secs
            if "Chorus" in str(s.get("label_variant") or s.get("label") or "")
        ),
        secs[-1],
    )
    apply_section_chords(doc, str(verse["id"]), parse_chord_paste("Gmaj7 Am7 D7 Gmaj7"))
    apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("Cmaj7 Bm7 E7 Am7"))
    apply_melody_events(
        doc,
        str(verse["id"]),
        [
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "A4", "midi": 69, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            {"pitch": "B4", "midi": 71, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
        ],
        replace=True,
    )
    set_section_melody_repeats(doc, str(verse["id"]), 2)
    # Leave lyrics/review incomplete — workflow stays mid-path.
    doc["status"] = "draft"
    return doc


class TestCompositionLibrarySave(unittest.TestCase):
    def test_first_save_creates_library_entry_and_message(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        sid = str(doc["id"])
        set_active_document(ss, doc, checkpoint=False)
        saved = save_document_to_library(ss, doc, force_disk=False)
        self.assertEqual(str(saved.get("id")), sid)
        self.assertIn(sid, ss[COMPOSER_LIBRARY_KEY])
        meta = last_library_save_meta(ss)
        self.assertTrue(meta.get("ok"))
        self.assertFalse(meta.get("is_update"))
        self.assertEqual(library_save_success_message(ss), "Saved to Composition Library.")

    def test_repeated_save_upserts_same_id_preserves_created_at(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        sid = str(doc["id"])
        created = str(doc.get("created_at") or "")
        set_active_document(ss, doc, checkpoint=False)
        first = save_document_to_library(ss, doc)
        time.sleep(0.02)
        doc2 = get_active_document(ss)
        assert doc2 is not None
        doc2["title"] = "Library Test Song (edited)"
        doc2["global"]["bpm"] = 118
        second = save_document_to_library(ss, doc2)
        self.assertEqual(str(second.get("id")), sid)
        self.assertEqual(len(ss[COMPOSER_LIBRARY_KEY]), 1)
        self.assertEqual(str(second.get("created_at") or ""), created or str(first.get("created_at")))
        self.assertNotEqual(str(second.get("updated_at") or ""), str(first.get("updated_at") or ""))
        meta = last_library_save_meta(ss)
        self.assertTrue(meta.get("is_update"))
        self.assertEqual(library_save_success_message(ss), "Composition Library updated.")

    def test_partial_draft_saves_without_lyrics_or_review(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc(title="Partial Draft")
        # Explicitly no lyrics lines / empty review.
        for sec in ordered_sections(doc):
            sec.setdefault("lyrics", {"intent": {}, "lines": [], "raw_text": ""})
        doc.pop("review", None)
        set_active_document(ss, doc, checkpoint=False)
        saved = save_document_to_library(ss, doc)
        self.assertEqual(saved.get("status"), "draft")
        self.assertTrue(last_library_save_meta(ss).get("ok"))
        verse = ordered_sections(saved)[0]
        self.assertTrue(section_melody_events(verse))
        self.assertEqual(get_melody_repeats(verse), 2)

    def test_persists_chords_melody_repeats_style_key_bpm(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        # Pass-specific style marker on melody intent.
        verse = ordered_sections(doc)[0]
        mel = verse.setdefault("melody", {})
        intent = mel.setdefault("intent", {})
        intent["feel"] = "laid-back"
        intent["style"] = "bossa"
        set_active_document(ss, doc, checkpoint=False)
        saved = save_document_to_library(ss, doc)
        pg = playback_globals(saved)
        self.assertEqual(pg["key_center"], "G")
        self.assertIn("major", str(pg.get("key_label") or "").lower())
        self.assertEqual(pg["bpm"], 112)
        self.assertEqual(str((saved.get("metadata") or {}).get("style") or ""), "Bossa")
        self.assertEqual(str((saved.get("global") or {}).get("original_mode_family") or ""), "major")
        v = ordered_sections(saved)[0]
        self.assertTrue(v.get("chords"))
        self.assertEqual(get_melody_repeats(v), 2)
        self.assertEqual(str(((v.get("melody") or {}).get("intent") or {}).get("feel")), "laid-back")

    def test_jewish_direction_persisted(self) -> None:
        ss: dict = {}
        doc = bootstrap_from_vision(
            genre="Jewish",
            song_idea="Nigun for library",
            title="Jewish Library Song",
            key="D minor",
            bpm=96,
            jewish_direction="Hasidic / dance",
        )
        apply_structure_template(doc, "simple")
        set_active_document(ss, doc, checkpoint=False)
        saved = save_document_to_library(ss, doc)
        self.assertEqual(
            str((saved.get("metadata") or {}).get("jewish_direction") or ""),
            "Hasidic / dance",
        )
        self.assertEqual(str((saved.get("global") or {}).get("original_mode_family") or ""), "minor")

    def test_session_library_mirrors_workspace_library(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        sid = str(doc["id"])
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        ws = ss.get(COMPOSITION_WORKSPACE_STATE_KEY)
        self.assertIsInstance(ws, dict)
        ws_lib = ws.get("library")
        self.assertIsInstance(ws_lib, dict)
        self.assertIn(sid, ws_lib)
        self.assertEqual(str(ws_lib[sid].get("title")), "Library Test Song")
        # gather path stays coherent
        gathered = gather_composition_workspace_from_session(ss)
        self.assertIn(sid, gathered.get("library") or {})

    def test_reload_restores_full_state(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        sid = str(doc["id"])
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        # Simulate leave + reopen
        ss.pop(COMPOSER_ACTIVE_KEY, None)
        loaded = load_library_document(ss, sid)
        self.assertIsNotNone(loaded)
        active = get_active_document(ss)
        assert active is not None
        self.assertEqual(str(active.get("id")), sid)
        self.assertEqual(str(active.get("title")), "Library Test Song")
        self.assertEqual(int((active.get("global") or {}).get("bpm") or 0), 112)
        self.assertEqual(get_melody_repeats(ordered_sections(active)[0]), 2)

    def test_songs_bridge_hydrates_from_workspace_not_only_snapshot(self) -> None:
        """Songs must find library entries via durable workspace when session lib is empty."""
        ss: dict = {}
        doc = _partial_bossa_doc(title="Hydrate Me")
        sid = str(doc["id"])
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        # Clear live session library + snapshots — leave only workspace blob.
        ws = copy.deepcopy(ss[COMPOSITION_WORKSPACE_STATE_KEY])
        fresh: dict = {COMPOSITION_WORKSPACE_STATE_KEY: ws}
        fresh.pop(COMPOSER_LIBRARY_KEY, None)
        fresh["_studio_page_snapshots"] = {}
        lib = ensure_composition_library_hydrated(fresh)
        self.assertIn(sid, lib)
        found = find_composition_document(fresh, f"composition::{sid}")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(str(found.get("title")), "Hydrate Me")

    def test_page_snapshot_recovery_still_works(self) -> None:
        doc = _partial_bossa_doc(title="Snap Recovery")
        sid = str(doc["id"])
        snap_lib = {sid: copy.deepcopy(doc)}
        fresh: dict = {
            COMPOSER_LIBRARY_KEY: {},
            COMPOSITION_WORKSPACE_STATE_KEY: {"schema_version": 1, "library": {}},
            "_studio_page_snapshots": {
                "composer": {COMPOSER_LIBRARY_KEY: snap_lib, COMPOSER_ACTIVE_KEY: copy.deepcopy(doc)}
            },
        }
        lib = ensure_composition_library_hydrated(fresh)
        self.assertIn(sid, lib)

    def test_songs_card_uses_original_key_not_practice_key(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        # Practice/display key drift must not rewrite card identity key.
        ss["display_key"] = "Db"
        ss["practice_key"] = "Db"
        card = composition_selected_song_record(ss[COMPOSER_LIBRARY_KEY][str(doc["id"])])
        self.assertEqual(card["key"], "G")
        self.assertEqual(card["title"], "Library Test Song")
        self.assertTrue(str(card["pick_key"]).startswith("composition::"))
        self.assertEqual(composition_id_from_pick_key(card["pick_key"]), str(doc["id"]))
        self.assertEqual(composition_home_key(doc), "G")

    def test_composition_pick_key_stable_across_saves(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        pk1 = composition_pick_key_for(doc)
        doc["global"]["bpm"] = 120
        save_document_to_library(ss, doc)
        rows = list_composition_songs_for_picker(ss)
        self.assertEqual(len(rows), 1)
        pk2 = composition_pick_key_for(rows[0])
        self.assertEqual(pk1, pk2)
        self.assertEqual(pk1, f"composition::{doc['id']}")

    def test_second_save_after_reopen_updates_same_document(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        sid = str(doc["id"])
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        load_library_document(ss, sid)
        active = get_active_document(ss)
        assert active is not None
        active["global"]["bpm"] = 118
        events = section_melody_events(ordered_sections(active)[0])
        if events:
            events[0]["pitch"] = "C5"
            events[0]["midi"] = 72
            apply_melody_events(active, str(ordered_sections(active)[0]["id"]), events, replace=True)
        save_document_to_library(ss, active)
        self.assertEqual(len(list_library_documents(ss)), 1)
        reloaded = ss[COMPOSER_LIBRARY_KEY][sid]
        self.assertEqual(int((reloaded.get("global") or {}).get("bpm") or 0), 118)
        self.assertEqual(section_melody_events(ordered_sections(reloaded)[0])[0]["pitch"], "C5")

    def test_workspace_isolation_between_session_dicts(self) -> None:
        """Two workspace session dicts must not share library entries."""
        a: dict = {}
        b: dict = {}
        doc_a = _partial_bossa_doc(title="Workspace A Song")
        doc_b = _partial_bossa_doc(title="Workspace B Song")
        set_active_document(a, doc_a, checkpoint=False)
        save_document_to_library(a, doc_a)
        set_active_document(b, doc_b, checkpoint=False)
        save_document_to_library(b, doc_b)
        titles_a = {str(d.get("title")) for d in list_library_documents(a)}
        titles_b = {str(d.get("title")) for d in list_library_documents(b)}
        self.assertIn("Workspace A Song", titles_a)
        self.assertNotIn("Workspace A Song", titles_b)
        self.assertIn("Workspace B Song", titles_b)
        self.assertNotIn("Workspace B Song", titles_a)
        # Hydration from each durable blob stays isolated.
        fresh_a = {COMPOSITION_WORKSPACE_STATE_KEY: copy.deepcopy(a[COMPOSITION_WORKSPACE_STATE_KEY])}
        fresh_b = {COMPOSITION_WORKSPACE_STATE_KEY: copy.deepcopy(b[COMPOSITION_WORKSPACE_STATE_KEY])}
        ensure_composition_library_hydrated(fresh_a)
        ensure_composition_library_hydrated(fresh_b)
        self.assertEqual(
            {str(d.get("title")) for d in list_library_documents(fresh_a)},
            {"Workspace A Song"},
        )
        self.assertEqual(
            {str(d.get("title")) for d in list_library_documents(fresh_b)},
            {"Workspace B Song"},
        )

    def test_save_after_key_bpm_change_stores_current_state(self) -> None:
        ss: dict = {}
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Transpose then save",
            title="Key Change Save",
            key="C major",
            bpm=100,
        )
        apply_structure_template(doc, "simple")
        apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C Am F G"))
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        active = get_active_document(ss)
        assert active is not None
        g = active.setdefault("global", {})
        g["original_key_center"] = "E"
        g["original_key_label"] = "E major"
        g["bpm"] = 118
        active["metadata"]["style"] = "Jazz"
        save_document_to_library(ss, active)
        saved = ss[COMPOSER_LIBRARY_KEY][str(active["id"])]
        self.assertEqual(str((saved.get("global") or {}).get("original_key_center")), "E")
        self.assertEqual(int((saved.get("global") or {}).get("bpm") or 0), 118)
        self.assertEqual(str((saved.get("metadata") or {}).get("style")), "Jazz")

    def test_missing_document_does_not_claim_success(self) -> None:
        ss: dict = {}
        out = save_document_to_library(ss, None)
        self.assertEqual(out, {})
        self.assertFalse(last_library_save_meta(ss).get("ok"))
        self.assertEqual(library_save_success_message(ss), "")
        self.assertNotIn(COMPOSER_LAST_LIBRARY_SAVE_KEY, {})  # meta exists on ss
        self.assertIn(COMPOSER_LAST_LIBRARY_SAVE_KEY, ss)

    def test_bridge_projects_full_section_payload(self) -> None:
        ss: dict = {}
        doc = _partial_bossa_doc()
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        found = find_composition_document(ss, composition_pick_key_for(doc))
        assert found is not None
        order = list((found.get("form") or {}).get("section_order") or [])
        self.assertGreaterEqual(len(order), 2)
        for sid in order:
            sec = ((found.get("form") or {}).get("sections") or {}).get(sid)
            self.assertIsInstance(sec, dict)


if __name__ == "__main__":
    unittest.main()
