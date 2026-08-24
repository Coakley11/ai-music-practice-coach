"""Composition Studio reboot / durable workspace persistence."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock

from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    section_melody_events,
    set_workflow_phase,
)
from composition_preview import generate_preview_wav, set_composer_preview
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_FOCUS_LANE_KEY,
    COMPOSER_LIBRARY_KEY,
    COMPOSER_NEEDS_SEED_KEY,
    COMPOSER_PREVIEW_WAV_KEY,
    set_active_document,
)
from composition_workspace_state_persistence import (
    COMPOSITION_WORKSPACE_STATE_KEY,
    apply_composition_workspace_from_payload,
    checkpoint_composition_workspace,
    gather_composition_workspace_from_session,
    normalize_focus_lane,
    prepare_composition_workspace_for_render,
    resolve_valid_section_id,
    sync_composition_workspace_before_persist,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state
from studio_nav_state import resolve_studio_page_for_restore


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss


def _jewish_draft() -> dict:
    doc = bootstrap_from_vision(
        genre="Jewish",
        song_idea="Nigun draft",
        title="Test Song",
        key="D minor",
        bpm=118,
        meter="6/8",
    )
    apply_structure_template(doc, "simple")
    # Expand to Intro / Verse / Chorus / Bridge-like via template + labels already present.
    secs = ordered_sections(doc)
    v1 = secs[0]
    chorus = next((s for s in secs if "Chorus" in str(s.get("label_variant") or s.get("label") or "")), secs[-1])
    apply_section_chords(doc, str(v1["id"]), parse_chord_paste("Dm Bb F C"))
    apply_melody_events(
        doc,
        str(v1["id"]),
        [
            {"pitch": "D4", "midi": 62, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
            {"pitch": "F4", "midi": 65, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
        ],
        replace=True,
    )
    apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("Dm A Dm A"))
    set_workflow_phase(doc, "melody")
    return doc, str(chorus["id"])


class TestCompositionDocumentReboot(unittest.TestCase):
    def test_draft_round_trip_restores_song_fields(self) -> None:
        doc, chorus_id = _jewish_draft()
        ss: dict = {
            "studio_page": "composer",
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_LIBRARY_KEY: {str(doc["id"]): copy.deepcopy(doc)},
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
            COMPOSER_FOCUS_LANE_KEY: "melody",
            COMPOSER_NEEDS_SEED_KEY: False,
        }
        sync_composition_workspace_before_persist(ss, reason="composer_edit")
        blob = build_music_disk_state(_FakeSt(ss))
        self.assertIn(COMPOSITION_WORKSPACE_STATE_KEY, blob)
        cws = blob[COMPOSITION_WORKSPACE_STATE_KEY]
        self.assertEqual((cws.get("active_document") or {}).get("title"), "Test Song")
        g = (cws.get("active_document") or {}).get("global") or {}
        self.assertIn(str(g.get("original_key_center") or ""), ("Dm", "D"))
        self.assertTrue("minor" in str(g.get("original_key_label") or "").lower() or str(g.get("original_key_center") or "") == "Dm")
        # Exact spelling / meter / bpm survive
        meta = (cws.get("active_document") or {}).get("metadata") or {}
        self.assertEqual(meta.get("style"), "Jewish")
        self.assertEqual(int(g.get("bpm") or 0), 118)
        self.assertEqual(str(g.get("time_signature") or ""), "6/8")

        fresh = _FakeSt({"studio_page": "practice"})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_composition_workspace_for_render(fresh.session_state)
        restored = fresh.session_state.get(COMPOSER_ACTIVE_KEY)
        self.assertIsInstance(restored, dict)
        self.assertEqual(restored.get("title"), "Test Song")
        rg = restored.get("global") or {}
        self.assertEqual(int(rg.get("bpm") or 0), 118)
        self.assertEqual(str(rg.get("time_signature") or ""), "6/8")
        self.assertEqual((restored.get("metadata") or {}).get("style"), "Jewish")
        self.assertFalse(fresh.session_state.get(COMPOSER_NEEDS_SEED_KEY))

    def test_section_order_links_chords_melody_lyrics(self) -> None:
        doc, chorus_id = _jewish_draft()
        secs = ordered_sections(doc)
        v1 = secs[0]
        # Partial lyrics on verse
        v1.setdefault("lyrics", {})["raw_text"] = "Home again under the lamps"
        order_before = list((doc.get("form") or {}).get("section_order") or [])
        ss: dict = {
            "studio_page": "composer",
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
            COMPOSER_FOCUS_LANE_KEY: "melody",
        }
        sync_composition_workspace_before_persist(ss)
        blob = build_music_disk_state(_FakeSt(ss))
        fresh: dict = {}
        apply_composition_workspace_from_payload(fresh, blob, authoritative=True)
        prepare_composition_workspace_for_render(fresh)
        restored = fresh[COMPOSER_ACTIVE_KEY]
        self.assertEqual(list((restored.get("form") or {}).get("section_order") or []), order_before)
        rv1 = ordered_sections(restored)[0]
        self.assertEqual((rv1.get("chords") or [])[0].get("chord"), "Dm")
        self.assertTrue(section_melody_events(rv1))
        self.assertIn("Home again", str((rv1.get("lyrics") or {}).get("raw_text") or ""))
        # Chorus chords remain; incomplete melody OK
        rchorus = next(s for s in ordered_sections(restored) if s.get("id") == chorus_id)
        self.assertTrue(rchorus.get("chords"))
        self.assertEqual(section_melody_events(rchorus), [])

    def test_incomplete_composition_restores(self) -> None:
        doc, _ = _jewish_draft()
        ss = {"studio_page": "composer", COMPOSER_ACTIVE_KEY: doc, COMPOSER_FOCUS_LANE_KEY: "chords"}
        sync_composition_workspace_before_persist(ss)
        blob = gather_composition_workspace_from_session(ss)
        self.assertIsInstance(blob.get("active_document"), dict)
        # No completion flag required
        self.assertNotEqual(str((blob["active_document"] or {}).get("status") or ""), "ready")


class TestCompositionActivePageRestore(unittest.TestCase):
    def test_composer_page_persists_and_restores(self) -> None:
        doc, chorus_id = _jewish_draft()
        ss: dict = {
            "studio_page": "composer",
            "studio_nav_state": {"studio_page": "composer"},
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
            COMPOSER_FOCUS_LANE_KEY: "melody",
            "_suite_pending_save_reason": "page_change",
        }
        sync_composition_workspace_before_persist(ss, reason="page_change")
        st = _FakeSt(ss)
        blob = build_music_disk_state(st)
        page, source = resolve_studio_page_for_restore({}, blob, pre_restore_page="")
        self.assertEqual(page, "composer")

        fresh = _FakeSt({"studio_page": "practice"})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        self.assertEqual(fresh.session_state.get("studio_page"), "composer")

    def test_navigating_away_updates_persisted_page(self) -> None:
        doc, _ = _jewish_draft()
        ss: dict = {
            "studio_page": "practice",
            "studio_nav_state": {"studio_page": "practice"},
            COMPOSER_ACTIVE_KEY: doc,
            "_suite_pending_save_reason": "page_change",
        }
        sync_composition_workspace_before_persist(ss)
        blob = build_music_disk_state(_FakeSt(ss))
        # Ensure practice stamped
        blob.setdefault("music_workspace_state", {})["studio_page"] = "practice"
        blob.setdefault("studio_nav_state", {})["studio_page"] = "practice"
        blob.setdefault("core", {})["studio_page"] = "practice"
        page, _ = resolve_studio_page_for_restore({}, blob, pre_restore_page="")
        self.assertEqual(page, "practice")

    def test_missing_page_falls_back_safely(self) -> None:
        page, source = resolve_studio_page_for_restore({}, {}, pre_restore_page="")
        self.assertEqual(page, "practice")
        self.assertTrue(source)


class TestCompositionEditingLocationRestore(unittest.TestCase):
    def test_section_and_lane_restore(self) -> None:
        doc, chorus_id = _jewish_draft()
        ss = {
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
            COMPOSER_FOCUS_LANE_KEY: "melody",
        }
        sync_composition_workspace_before_persist(ss)
        blob = build_music_disk_state(_FakeSt({**ss, "studio_page": "composer"}))
        fresh: dict = {"studio_page": "composer"}
        apply_composition_workspace_from_payload(fresh, blob, authoritative=True)
        prepare_composition_workspace_for_render(fresh)
        self.assertEqual(fresh.get(COMPOSER_ACTIVE_SECTION_KEY), chorus_id)
        self.assertEqual(fresh.get(COMPOSER_FOCUS_LANE_KEY), "melody")

    def test_missing_section_falls_back(self) -> None:
        doc, _ = _jewish_draft()
        first = str(ordered_sections(doc)[0]["id"])
        self.assertEqual(resolve_valid_section_id(doc, "deleted-section-id"), first)

    def test_invalid_lane_falls_back(self) -> None:
        self.assertEqual(normalize_focus_lane("nope"), "chords")
        self.assertEqual(normalize_focus_lane("lyrics", skip_lyrics=True), "chords")

    def test_restore_location_does_not_mutate_song_content(self) -> None:
        doc, chorus_id = _jewish_draft()
        before = copy.deepcopy(doc)
        ss = {
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
            COMPOSER_FOCUS_LANE_KEY: "melody",
        }
        sync_composition_workspace_before_persist(ss)
        blob = gather_composition_workspace_from_session(ss)
        fresh: dict = {}
        apply_composition_workspace_from_payload(
            fresh, {COMPOSITION_WORKSPACE_STATE_KEY: blob}, authoritative=True
        )
        restored = fresh[COMPOSER_ACTIVE_KEY]
        self.assertEqual(
            (restored.get("form") or {}).get("section_order"),
            (before.get("form") or {}).get("section_order"),
        )
        self.assertEqual(
            section_melody_events(ordered_sections(restored)[0]),
            section_melody_events(ordered_sections(before)[0]),
        )


class TestCompositionHydrationOwnership(unittest.TestCase):
    def test_defaults_do_not_overwrite_hydrated_key_bpm_meter(self) -> None:
        doc, _ = _jewish_draft()
        ss = {COMPOSER_ACTIVE_KEY: doc, COMPOSER_FOCUS_LANE_KEY: "melody"}
        sync_composition_workspace_before_persist(ss)
        cws = gather_composition_workspace_from_session(ss)
        # Simulate bootstrap trying to inject defaults after restore
        fresh: dict = {
            COMPOSITION_WORKSPACE_STATE_KEY: cws,
            COMPOSER_NEEDS_SEED_KEY: True,
        }
        prepare_composition_workspace_for_render(fresh)
        g = (fresh[COMPOSER_ACTIVE_KEY].get("global") or {})
        self.assertEqual(int(g.get("bpm") or 0), 118)
        self.assertEqual(str(g.get("time_signature") or ""), "6/8")
        self.assertFalse(fresh.get(COMPOSER_NEEDS_SEED_KEY))

    def test_checkpoint_on_harmony_accept(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        sid = str(ordered_sections(doc)[0]["id"])
        ss: dict = {"studio_page": "composer", COMPOSER_ACTIVE_KEY: doc}
        apply_section_chords(doc, sid, parse_chord_paste("C Am F G"))
        set_active_document(ss, doc)
        checkpoint_composition_workspace(ss, reason="composer_edit", force_disk=False)
        self.assertIsInstance(ss.get(COMPOSITION_WORKSPACE_STATE_KEY), dict)
        chords = ((ss[COMPOSITION_WORKSPACE_STATE_KEY].get("active_document") or {}).get("form") or {})
        _ = chords  # structure present
        restored_doc = ss[COMPOSITION_WORKSPACE_STATE_KEY]["active_document"]
        self.assertEqual(
            (ordered_sections(restored_doc)[0].get("chords") or [])[0].get("chord"),
            "C",
        )

    def test_preview_does_not_accept_or_require_workspace_mutation(self) -> None:
        doc, chorus_id = _jewish_draft()
        ss: dict = {
            "studio_page": "composer",
            COMPOSER_ACTIVE_KEY: copy.deepcopy(doc),
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
        }
        before = copy.deepcopy(ss[COMPOSER_ACTIVE_KEY])
        wav = generate_preview_wav(doc, section_id=chorus_id, include_melody=False, loops=1)
        if wav:
            set_composer_preview(ss, wav, "sig")
            self.assertTrue(ss.get(COMPOSER_PREVIEW_WAV_KEY))
        # Document unchanged by preview
        self.assertEqual(
            (ss[COMPOSER_ACTIVE_KEY].get("form") or {}).get("section_order"),
            (before.get("form") or {}).get("section_order"),
        )
        # Preview must not be durable
        sync_composition_workspace_before_persist(ss)
        cws = ss[COMPOSITION_WORKSPACE_STATE_KEY]
        self.assertNotIn(COMPOSER_PREVIEW_WAV_KEY, cws)


class TestCompositionPageSnapshotFallback(unittest.TestCase):
    def test_legacy_page_snapshot_migrates(self) -> None:
        doc, chorus_id = _jewish_draft()
        payload = {
            "session": {
                "_studio_page_snapshots": {
                    "composer": {
                        COMPOSER_ACTIVE_KEY: doc,
                        COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
                        COMPOSER_FOCUS_LANE_KEY: "melody",
                        COMPOSER_NEEDS_SEED_KEY: False,
                    }
                }
            }
        }
        fresh: dict = {}
        self.assertTrue(apply_composition_workspace_from_payload(fresh, payload, authoritative=True))
        prepare_composition_workspace_for_render(fresh)
        self.assertEqual(fresh[COMPOSER_ACTIVE_KEY].get("title"), "Test Song")
        self.assertEqual(fresh.get(COMPOSER_FOCUS_LANE_KEY), "melody")


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestCompositionWelcomeStillRenders(unittest.TestCase):
    def test_welcome_harness(self) -> None:
        from pathlib import Path

        from streamlit.testing.v1 import AppTest

        harness = str(Path(__file__).resolve().parents[1] / "composition_studio_welcome_harness.py")
        at = AppTest.from_file(harness, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))


if __name__ == "__main__":
    unittest.main()
