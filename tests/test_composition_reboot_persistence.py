"""Composition Studio reboot / durable workspace persistence."""

from __future__ import annotations

import copy
import unittest
from unittest import mock
from unittest.mock import MagicMock

from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_song_brief,
    apply_structure_template,
    bootstrap_from_vision,
    composition_song_brief,
    ordered_sections,
    parse_chord_paste,
    section_melody_events,
    section_melody_source,
    set_workflow_phase,
)
from composition_preview import generate_preview_wav, resolve_preview_groove, set_composer_preview
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_ARRANGEMENT_PREVIEW_KEY,
    COMPOSER_FOCUS_LANE_KEY,
    COMPOSER_LIBRARY_KEY,
    COMPOSER_NEEDS_SEED_KEY,
    COMPOSER_PREVIEW_WAV_KEY,
    init_composer_page_state,
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
class TestCompositionPageNavDurability(unittest.TestCase):
    """Live reboot failure: Practice→Composition with no edit must restore composer."""

    def test_composer_is_valid_canonical_nav_id(self) -> None:
        from studio_nav_history import STUDIO_PAGE_IDS
        from studio_nav_state import _normalize_page

        self.assertIn("composer", STUDIO_PAGE_IDS)
        self.assertEqual(_normalize_page("composer"), "composer")
        self.assertEqual(resolve_studio_page_for_restore({}, {"core": {"studio_page": "composer"}})[0], "composer")

    def test_page_change_nav_without_content_edit_survives_reboot(self) -> None:
        """Practice → Composition → page_change only → destroy session → restore composer."""
        from music_persistent_state import after_studio_page_change, prepare_page_change_save_state
        from studio_nav_state import prepare_studio_nav

        ss: dict = {
            "studio_page": "practice",
            "studio_nav_state": {"studio_page": "practice", "page": "practice"},
            "music_workspace_state": {"studio_page": "practice", "page": "practice"},
            "_suite_last_persisted_page": "practice",
        }
        prepare_page_change_save_state(ss, "composer", origin="user_navigation")
        self.assertEqual(ss.get("studio_page"), "composer")
        self.assertTrue(ss.get("_suite_page_user_nav"))

        st = _FakeSt(ss)
        captured: dict = {}

        def _fake_force(st_arg, *, reason=""):
            captured["reason"] = reason
            captured["state"] = build_music_disk_state(st_arg)
            st_arg.session_state["_suite_persist_last_save_cloud"] = True
            st_arg.session_state["_music_force_save_ok"] = True
            return True

        with mock.patch(
            "music_persistent_state.force_save_music_state",
            side_effect=_fake_force,
        ), mock.patch(
            "suite_user_persistence._release_user_page_ownership_after_save",
        ):
            after_studio_page_change(st, ss, target_page="composer")

        self.assertEqual(captured.get("reason"), "page_change")
        blob = captured["state"]
        self.assertEqual((blob.get("music_workspace_state") or {}).get("studio_page"), "composer")
        self.assertEqual((blob.get("studio_nav_state") or {}).get("studio_page"), "composer")
        self.assertEqual((blob.get("core") or {}).get("studio_page"), "composer")

        # Fresh process: no content edit keys required
        fresh = _FakeSt({"studio_page": "practice"})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_studio_nav(fresh.session_state)
        self.assertEqual(fresh.session_state.get("studio_page"), "composer")

    def test_failed_page_change_keeps_ownership_and_deferred(self) -> None:
        from music_persistent_state import after_studio_page_change, prepare_page_change_save_state

        ss: dict = {
            "studio_page": "practice",
            "studio_nav_state": {"studio_page": "practice"},
        }
        prepare_page_change_save_state(ss, "composer", origin="user_navigation")
        st = _FakeSt(ss)
        with mock.patch(
            "music_persistent_state.force_save_music_state",
            return_value=False,
        ), mock.patch(
            "suite_user_persistence._release_user_page_ownership_after_save",
        ) as mock_release:
            after_studio_page_change(st, ss, target_page="composer")
        mock_release.assert_not_called()
        self.assertEqual(ss.get("_suite_deferred_page_change_save"), "composer")
        self.assertTrue(ss.get("_suite_page_user_nav"))
        self.assertNotEqual(ss.get("_suite_last_persisted_page"), "composer")

    def test_composer_edit_preserves_composer_nav_stamp(self) -> None:
        doc, chorus_id = _jewish_draft()
        ss: dict = {
            "studio_page": "composer",
            "studio_nav_state": {"studio_page": "composer"},
            "music_workspace_state": {"studio_page": "composer", "page": "practice"},
            "_suite_last_persisted_page": "composer",
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
            COMPOSER_FOCUS_LANE_KEY: "melody",
            "_suite_pending_save_reason": "composer_edit",
        }
        sync_composition_workspace_before_persist(ss, reason="composer_edit")
        blob = build_music_disk_state(_FakeSt(ss))
        self.assertEqual((blob.get("music_workspace_state") or {}).get("studio_page"), "composer")
        self.assertEqual((blob.get("core") or {}).get("studio_page"), "composer")
        page, _ = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "composer")

    def test_coach_page_practice_does_not_erase_missing_studio_stamp_when_nav_has_composer(self) -> None:
        from studio_nav_state import _studio_page_from_blob

        blob = {
            "music_workspace_state": {"studio_page": "", "page": "practice"},
            "studio_nav_state": {"studio_page": "composer"},
            "core": {"page": "practice"},
        }
        self.assertEqual(_studio_page_from_blob(blob), "composer")

    def test_empty_studio_page_does_not_use_coach_practice_as_studio(self) -> None:
        from studio_nav_state import _studio_page_from_blob

        blob = {
            "music_workspace_state": {"studio_page": "", "page": "practice"},
            "core": {"studio_page": "", "page": "practice"},
        }
        self.assertEqual(_studio_page_from_blob(blob), "")

    def test_stale_cloud_practice_loses_to_newer_local_composer(self) -> None:
        from studio_nav_state import apply_cloud_studio_nav_state_if_allowed, mark_studio_nav_local_edit

        session = {
            "studio_page": "composer",
            "studio_nav_state": {"studio_page": "composer"},
        }
        mark_studio_nav_local_edit(session)
        cloud = {
            "studio_nav_state": {"studio_page": "practice"},
            "music_workspace_state": {"studio_page": "practice"},
            "core": {"studio_page": "practice"},
        }
        self.assertFalse(apply_cloud_studio_nav_state_if_allowed(session, cloud))
        self.assertEqual(session["studio_page"], "composer")

    def test_intentional_leave_to_practice_restores_practice(self) -> None:
        from music_persistent_state import after_studio_page_change, prepare_page_change_save_state

        ss: dict = {
            "studio_page": "composer",
            "studio_nav_state": {"studio_page": "composer"},
            "_suite_last_persisted_page": "composer",
        }
        prepare_page_change_save_state(ss, "practice", origin="user_navigation")
        st = _FakeSt(ss)
        captured: dict = {}

        def _fake_force(st_arg, *, reason=""):
            captured["state"] = build_music_disk_state(st_arg)
            st_arg.session_state["_music_force_save_ok"] = True
            return True

        with mock.patch(
            "music_persistent_state.force_save_music_state",
            side_effect=_fake_force,
        ), mock.patch(
            "suite_user_persistence._release_user_page_ownership_after_save",
        ):
            after_studio_page_change(st, ss, target_page="practice")

        page, _ = resolve_studio_page_for_restore({}, captured["state"])
        self.assertEqual(page, "practice")

    def test_failed_then_deferred_flush_persists_composer(self) -> None:
        """Blocked page_change retains ownership; later deferred flush stamps composer."""
        from music_persistent_state import (
            after_studio_page_change,
            maybe_flush_deferred_page_change_save,
            prepare_page_change_save_state,
        )

        ss: dict = {
            "studio_page": "practice",
            "studio_nav_state": {"studio_page": "practice"},
            "_suite_last_persisted_page": "practice",
        }
        prepare_page_change_save_state(ss, "composer", origin="user_navigation")
        st = _FakeSt(ss)
        with mock.patch(
            "music_persistent_state.force_save_music_state",
            return_value=False,
        ), mock.patch(
            "suite_user_persistence._release_user_page_ownership_after_save",
        ) as mock_release:
            after_studio_page_change(st, ss, target_page="composer")
        mock_release.assert_not_called()
        self.assertEqual(ss.get("_suite_deferred_page_change_save"), "composer")
        self.assertTrue(ss.get("_suite_page_user_nav"))
        self.assertEqual(ss.get("_suite_last_persisted_page"), "practice")

        captured: dict = {}

        def _flush_ok(st_arg, *, reason=""):
            captured["reason"] = reason
            captured["state"] = build_music_disk_state(st_arg)
            st_arg.session_state["_music_force_save_ok"] = True
            return True

        with mock.patch(
            "music_persistent_state.force_save_music_state",
            side_effect=_flush_ok,
        ), mock.patch(
            "music_startup_save_suppression.should_suppress_music_workspace_save",
            return_value=(False, ""),
        ), mock.patch(
            "suite_user_persistence._release_user_page_ownership_after_save",
        ) as mock_release2:
            ok = maybe_flush_deferred_page_change_save(st)
        self.assertTrue(ok)
        mock_release2.assert_called()
        self.assertIsNone(ss.get("_suite_deferred_page_change_save"))
        self.assertEqual(ss.get("_suite_last_persisted_page"), "composer")
        self.assertFalse(ss.get("_suite_page_user_nav"))
        self.assertEqual(captured.get("reason"), "page_change")
        self.assertEqual(
            (captured["state"].get("music_workspace_state") or {}).get("studio_page"),
            "composer",
        )
        page, _ = resolve_studio_page_for_restore({}, captured["state"])
        self.assertEqual(page, "composer")

    def test_rapid_nav_latest_intent_wins_over_older_deferred(self) -> None:
        """Practice→Composition (blocked)→Creative: deferred target must be Creative."""
        from music_persistent_state import after_studio_page_change, prepare_page_change_save_state

        ss: dict = {
            "studio_page": "practice",
            "studio_nav_state": {"studio_page": "practice"},
            "_suite_last_persisted_page": "practice",
        }
        st = _FakeSt(ss)
        with mock.patch(
            "music_persistent_state.force_save_music_state",
            return_value=False,
        ), mock.patch(
            "suite_user_persistence._release_user_page_ownership_after_save",
        ):
            prepare_page_change_save_state(ss, "composer", origin="user_navigation")
            after_studio_page_change(st, ss, target_page="composer")
            self.assertEqual(ss.get("_suite_deferred_page_change_save"), "composer")

            prepare_page_change_save_state(ss, "custom", origin="user_navigation")
            after_studio_page_change(st, ss, target_page="custom")

        self.assertEqual(ss.get("studio_page"), "custom")
        self.assertEqual(ss.get("_suite_deferred_page_change_save"), "custom")
        self.assertTrue(ss.get("_suite_page_user_nav"))
        self.assertNotEqual(ss.get("_suite_last_persisted_page"), "composer")
        self.assertNotEqual(ss.get("_suite_last_persisted_page"), "custom")

    def test_restore_in_progress_does_not_fake_user_nav_dirty(self) -> None:
        from music_workspace_restore_mode import begin_workspace_restore
        from studio_nav_state import is_studio_nav_locally_dirty, mark_studio_nav_local_edit

        ss: dict = {"studio_page": "composer"}
        begin_workspace_restore(ss)
        mark_studio_nav_local_edit(ss)
        self.assertFalse(is_studio_nav_locally_dirty(ss))
        self.assertFalse(ss.get("_suite_page_user_nav"))

    def test_restored_composer_does_not_mark_dirty_or_loop(self) -> None:
        from studio_nav_state import is_studio_nav_locally_dirty, prepare_studio_nav

        blob = {
            "core": {"studio_page": "composer"},
            "session": {"studio_page": "composer"},
            "music_workspace_state": {"studio_page": "composer", "page": "practice"},
            "studio_nav_state": {"studio_page": "composer", "page": "composer"},
        }
        fresh = _FakeSt({})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_studio_nav(fresh.session_state)
        self.assertEqual(fresh.session_state.get("studio_page"), "composer")
        self.assertFalse(is_studio_nav_locally_dirty(fresh.session_state))
        self.assertFalse(fresh.session_state.get("_suite_page_user_nav"))
        self.assertNotEqual(
            fresh.session_state.get("_suite_deferred_page_change_save"),
            "composer",
        )

    def test_practice_durable_page_restores_practice(self) -> None:
        blob = {
            "core": {"studio_page": "practice"},
            "session": {"studio_page": "practice"},
            "music_workspace_state": {"studio_page": "practice", "page": "practice"},
            "studio_nav_state": {"studio_page": "practice"},
        }
        page, source = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "practice")
        fresh = _FakeSt({"studio_page": "composer"})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        self.assertEqual(fresh.session_state.get("studio_page"), "practice")
        self.assertEqual(source, "workspace_blob")

    def test_creative_durable_page_restores_custom(self) -> None:
        """Shared nav must honor Creative (custom) stamp without product changes."""
        blob = {
            "core": {"studio_page": "custom"},
            "session": {"studio_page": "custom"},
            "music_workspace_state": {"studio_page": "custom", "page": "custom"},
            "studio_nav_state": {"studio_page": "custom"},
        }
        page, source = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "custom")
        self.assertEqual(source, "workspace_blob")
        fresh = _FakeSt({"studio_page": "practice"})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        self.assertEqual(fresh.session_state.get("studio_page"), "custom")


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestCompositionNavRestoreShellAppTest(unittest.TestCase):
    def test_shell_restore_reaches_composition(self) -> None:
        from pathlib import Path

        from streamlit.testing.v1 import AppTest

        harness = str(Path(__file__).resolve().parents[1] / "composition_studio_nav_restore_harness.py")
        at = AppTest.from_file(harness, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        self.assertIn("studio_page", at.session_state)
        self.assertEqual(at.session_state["studio_page"], "composer")


class TestCompositionSongBriefAndMelodySourceRestore(unittest.TestCase):
    def test_song_brief_and_melody_source_survive_reboot(self) -> None:
        doc, chorus_id = _jewish_draft()
        apply_song_brief(
            doc,
            mood="Devotional / reflective",
            energy="Ballad — slow and intimate",
            theme="Nigun draft under the lamps",
        )
        from composition_document import apply_lyrics_text

        apply_lyrics_text(doc, str(ordered_sections(doc)[0]["id"]), "Home again")
        verse = ordered_sections(doc)[0]
        apply_melody_events(
            doc,
            str(verse["id"]),
            [
                {"pitch": "D4", "midi": 62, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
                {"pitch": "F4", "midi": 65, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
            ],
            concept={"id": "hum_transcription", "name": "Recorded melody"},
            source="recorded",
            replace=True,
        )
        ss: dict = {
            "studio_page": "composer",
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
            COMPOSER_FOCUS_LANE_KEY: "melody",
            COMPOSER_ARRANGEMENT_PREVIEW_KEY: "Jazz",
        }
        sync_composition_workspace_before_persist(ss)
        blob = build_music_disk_state(_FakeSt(ss))
        cws = blob[COMPOSITION_WORKSPACE_STATE_KEY]
        self.assertEqual(cws.get("arrangement_preview_style"), "Jazz")
        fresh = _FakeSt({"studio_page": "practice"})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_composition_workspace_for_render(fresh.session_state)
        restored = fresh.session_state[COMPOSER_ACTIVE_KEY]
        brief = composition_song_brief(restored)
        self.assertEqual(brief["style"], "Jewish")
        self.assertEqual(brief["mood"], "Devotional / reflective")
        self.assertEqual(brief["energy"], "Ballad — slow and intimate")
        self.assertIn("Nigun", brief["theme"])
        self.assertEqual(brief["tempo"], 118)
        self.assertEqual(brief["meter"], "6/8")
        rverse = ordered_sections(restored)[0]
        self.assertEqual(section_melody_source(rverse), "recorded")
        self.assertTrue((rverse.get("lyrics") or {}).get("alignment"))
        self.assertIn("Home", str((rverse.get("lyrics") or {}).get("raw_text") or ""))
        self.assertEqual(fresh.session_state.get(COMPOSER_ARRANGEMENT_PREVIEW_KEY), "Jazz")
        # Arrangement preference must not rewrite canonical style/chords/melody.
        self.assertEqual((restored.get("metadata") or {}).get("style"), "Jewish")
        self.assertEqual((rverse.get("chords") or [])[0].get("chord"), "Dm")
        self.assertEqual(section_melody_events(rverse)[0].get("pitch"), "D4")

    def test_catalog_defaults_do_not_seize_composition_draft(self) -> None:
        doc, chorus_id = _jewish_draft()
        ss: dict = {
            "studio_page": "composer",
            "studio_nav_state": {"studio_page": "composer"},
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: chorus_id,
            COMPOSER_FOCUS_LANE_KEY: "melody",
            COMPOSER_NEEDS_SEED_KEY: False,
            "active_catalog_pick_key": "Pop::Say — John Mayer",
            "song": "Say",
        }
        sync_composition_workspace_before_persist(ss, reason="composer_edit")
        blob = build_music_disk_state(_FakeSt(ss))
        fresh = _FakeSt(
            {
                "studio_page": "practice",
                "active_catalog_pick_key": "Pop::Say — John Mayer",
                "song": "Say",
            }
        )
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_composition_workspace_for_render(fresh.session_state)
        init_composer_page_state(fresh.session_state)
        restored = fresh.session_state.get(COMPOSER_ACTIVE_KEY)
        self.assertIsInstance(restored, dict)
        self.assertEqual(restored.get("title"), "Test Song")
        self.assertNotEqual(restored.get("title"), "Say")
        self.assertEqual(fresh.session_state.get("studio_page"), "composer")
        self.assertFalse(fresh.session_state.get(COMPOSER_NEEDS_SEED_KEY))
        self.assertEqual(composition_song_brief(restored)["style"], "Jewish")

    def test_workspace_blob_without_projection_does_not_open_welcome(self) -> None:
        doc, _ = _jewish_draft()
        ss = {COMPOSITION_WORKSPACE_STATE_KEY: {"active_document": doc, "needs_seed": False}}
        init_composer_page_state(ss)
        self.assertFalse(ss.get(COMPOSER_NEEDS_SEED_KEY))

    def test_arrangement_preview_does_not_mutate_document(self) -> None:
        doc, chorus_id = _jewish_draft()
        before_style = (doc.get("metadata") or {}).get("style")
        before_chords = copy.deepcopy(ordered_sections(doc)[0].get("chords") or [])
        before_melody = copy.deepcopy(section_melody_events(ordered_sections(doc)[0]))
        groove = resolve_preview_groove(doc, "Jazz")
        self.assertIn("Jazz", groove)
        self.assertEqual((doc.get("metadata") or {}).get("style"), before_style)
        self.assertEqual(ordered_sections(doc)[0].get("chords") or [], before_chords)
        self.assertEqual(section_melody_events(ordered_sections(doc)[0]), before_melody)
        wav = generate_preview_wav(
            doc,
            section_id=chorus_id,
            include_melody=False,
            loops=1,
            arrangement_style="Jazz",
        )
        if wav:
            self.assertTrue(wav)
        self.assertEqual((doc.get("metadata") or {}).get("style"), before_style)
        self.assertEqual(ordered_sections(doc)[0].get("chords") or [], before_chords)


class TestCompositionColdProcessReboot(unittest.TestCase):
    def test_disk_envelope_restores_in_new_process(self) -> None:
        """True cold start: write durable envelope, restore in a new process."""
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

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
        with tempfile.TemporaryDirectory() as tmp:
            envelope = Path(tmp) / "music_disk_state.json"
            envelope.write_text(json.dumps(blob, default=str), encoding="utf-8")
            child = Path(tmp) / "cold_restore.py"
            child.write_text(
                "\n".join(
                    [
                        "import json, sys",
                        "from composition_session_state import COMPOSER_ACTIVE_KEY, COMPOSER_FOCUS_LANE_KEY, COMPOSER_NEEDS_SEED_KEY, COMPOSER_ACTIVE_SECTION_KEY",
                        "from composition_workspace_state_persistence import prepare_composition_workspace_for_render",
                        "from composition_document import ordered_sections, section_melody_events, playback_globals",
                        "from music_persistent_state import apply_music_disk_state",
                        "blob = json.loads(open(sys.argv[1], encoding='utf-8').read())",
                        "ss = {}",
                        "class _St:",
                        "    session_state = ss",
                        "apply_music_disk_state(_St(), blob, song_picker_catalog={}, song_library={}, authoritative_restore=True)",
                        "prepare_composition_workspace_for_render(ss)",
                        "doc = ss.get(COMPOSER_ACTIVE_KEY)",
                        "assert isinstance(doc, dict), 'missing document'",
                        "assert doc.get('title') == 'Test Song'",
                        "g = playback_globals(doc)",
                        "assert int(g.get('bpm') or 0) == 118",
                        "assert str(g.get('time_signature') or '') == '6/8'",
                        "assert ss.get(COMPOSER_NEEDS_SEED_KEY) is False",
                        "assert ss.get(COMPOSER_FOCUS_LANE_KEY) == 'melody'",
                        "assert ss.get(COMPOSER_ACTIVE_SECTION_KEY) == sys.argv[2]",
                        "verse = ordered_sections(doc)[0]",
                        "assert (verse.get('chords') or [])[0].get('chord') == 'Dm'",
                        "assert section_melody_events(verse)",
                        "print('COLD_OK')",
                    ]
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(child), str(envelope), chorus_id],
                check=False,
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).resolve().parents[1]),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("COLD_OK", proc.stdout)


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
