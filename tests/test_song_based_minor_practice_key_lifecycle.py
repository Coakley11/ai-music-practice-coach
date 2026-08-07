"""Song-Based catalog minor practice key — sidebar lifecycle (production paths)."""

from __future__ import annotations

import hashlib
import json
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from creative_lifecycle_harness_support import (
    HEVENU_PICK,
    harmony_map_focus_chord,
    mission_select_single_chord,
    restore_song_based_tab,
    run_song_based_minor_practice_key_harness_scenario,
    simulate_picker_to_creative_handoff,
)
from creative_key_sync import prepare_creative_sidebar_display_key
from music_theory import key_is_minor, split_key_center
from music_workflow_pending_song_practice_key_edit import (
    PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_TOKEN_KEY,
    consume_pending_song_practice_key_edit,
)
from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers
from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob
from song_practice_key_change_trace import collect_song_practice_key_snapshot
from tests.test_creative_catalog_handoff_picker import CATALOG, _stale_canonical_say_session

PK_SAY = next(k for k in CATALOG["Pop"] if "Say" in k)


def _hevenu_song_based_session() -> dict[str, Any]:
    session = _stale_canonical_say_session()
    simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=HEVENU_PICK)
    session["improv_entry_mode"] = "Song-Based Improvisation"
    session["improv_intelligence_tab"] = "Entry & Jam"
    return session


def _simulate_pre_widget_consume(session: dict[str, Any]) -> None:
    session.pop("_music_pre_widget_bootstrap_ran_this_run", None)
    run_pre_widget_application_consumers(session)


def _simulate_sidebar_key_change(session: dict[str, Any], new_key: str) -> None:
    import streamlit as st_mod

    from creative_key_sync import on_sidebar_practice_concert_key_change

    session["display_key"] = new_key
    session["_streamlit_widgets_locked_this_run"] = True
    prior = getattr(st_mod, "session_state", None)
    st_mod.session_state = session  # type: ignore[misc]
    try:
        with patch(
            "display_key_sidebar_save_pipeline.run_explicit_display_key_cloud_save",
            return_value=True,
        ):
            on_sidebar_practice_concert_key_change()
    finally:
        if prior is not None:
            st_mod.session_state = prior  # type: ignore[misc]
    session.pop("_streamlit_widgets_locked_this_run", None)
    session.pop("_music_pre_widget_bootstrap_ran_this_run", None)


def _simulate_next_run_prepare(session: dict[str, Any]) -> None:
    from music_persistent_state import prepare_canonical_music_page_state

    run_pre_widget_application_consumers(session)
    prepare_canonical_music_page_state(session, song_picker_catalog=CATALOG, force=True)
    st = MagicMock(session_state=session)
    prepare_creative_sidebar_display_key(st, session)


def _progression_fingerprint(session: dict[str, Any]) -> str:
    sections = session.get("improv_song_concert_sections") or {}
    if not isinstance(sections, dict):
        return ""
    payload = json.dumps({k: list(v) for k, v in sorted(sections.items())}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _section_structure(session: dict[str, Any]) -> dict[str, int]:
    sections = session.get("improv_song_concert_sections") or {}
    if not isinstance(sections, dict):
        return {}
    return {k: len(v) for k, v in sections.items() if isinstance(v, list)}


def _blob_section_structure(session: dict[str, Any]) -> dict[str, int]:
    ptr = get_active_workflow_pointer(session)
    if not ptr:
        return {}
    blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    if blob is None or not isinstance(blob.section_map, dict):
        return {}
    return {k: len(v) for k, v in blob.section_map.items() if isinstance(v, list)}


class TestSongBasedMinorPracticeKeyLifecycle(unittest.TestCase):
    def _song_blob(self, session: dict[str, Any]):
        ptr = get_active_workflow_pointer(session)
        if not ptr:
            return None
        return get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)

    def _assert_practice_minor(self, session: dict[str, Any], token: str) -> None:
        self.assertTrue(key_is_minor(token), f"expected minor token, got {token!r}")
        blob = self._song_blob(session)
        self.assertIsNotNone(blob)
        assert blob is not None
        self.assertEqual(str(blob.keys.practice_mode or "").lower(), "minor")
        pt, _pm = split_key_center(token)
        self.assertEqual(str(blob.keys.practice_tonic or "").upper(), pt.upper())
        self.assertEqual(str(blob.keys.original_mode or "").lower(), "minor")
        self.assertEqual(str(blob.keys.original_tonic or "").upper(), "D")

    def test_hevenu_options_are_minor_only(self) -> None:
        session = _hevenu_song_based_session()
        st = MagicMock(session_state=session)
        options = prepare_creative_sidebar_display_key(st, session)
        self.assertTrue(all(key_is_minor(k) for k in options))
        self.assertIn("Ebm", options)
        self.assertNotIn("Eb", options)

    def test_hevenu_dm_to_ebm_lifecycle(self) -> None:
        session = _hevenu_song_based_session()
        fp_dm = _progression_fingerprint(session)
        collect_song_practice_key_snapshot(session, phase="before_ebm")
        _simulate_sidebar_key_change(session, "Ebm")
        pending = session.get("_music_pending_song_practice_key_edit")
        self.assertIsInstance(pending, dict)
        self.assertEqual(str(pending.get("selected_key_token") or ""), "Ebm")
        _simulate_pre_widget_consume(session)
        self._assert_practice_minor(session, "Ebm")
        _simulate_next_run_prepare(session)
        self._assert_practice_minor(session, str(session.get("display_key") or ""))
        self.assertNotEqual(_progression_fingerprint(session), fp_dm)

    def test_hevenu_dm_to_em_and_bbm(self) -> None:
        for target in ("Em", "Bbm"):
            with self.subTest(target=target):
                session = _hevenu_song_based_session()
                _simulate_sidebar_key_change(session, target)
                _simulate_pre_widget_consume(session)
                _simulate_next_run_prepare(session)
                self._assert_practice_minor(session, target)

    def test_hevenu_switch_back_to_dm(self) -> None:
        session = _hevenu_song_based_session()
        _simulate_sidebar_key_change(session, "Ebm")
        _simulate_pre_widget_consume(session)
        _simulate_sidebar_key_change(session, "Dm")
        _simulate_pre_widget_consume(session)
        _simulate_next_run_prepare(session)
        self._assert_practice_minor(session, "Dm")

    def test_major_catalog_song_keeps_major_mode(self) -> None:
        session = _stale_canonical_say_session()
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=PK_SAY)
        session["improv_entry_mode"] = "Song-Based Improvisation"
        st = MagicMock(session_state=session)
        options = prepare_creative_sidebar_display_key(st, session)
        self.assertTrue(all(not key_is_minor(k) for k in options))
        _simulate_sidebar_key_change(session, "A")
        _simulate_pre_widget_consume(session)
        _simulate_next_run_prepare(session)
        blob = self._song_blob(session)
        assert blob is not None
        self.assertEqual(str(blob.keys.practice_mode or "").lower(), "major")

    def test_mission_harmony_refresh_retain_ebm(self) -> None:
        session = _hevenu_song_based_session()
        _simulate_sidebar_key_change(session, "Ebm")
        _simulate_pre_widget_consume(session)
        mission_select_single_chord(session, chord="Dm", section="Verse")
        restore_song_based_tab(session)
        self._assert_practice_minor(session, "Ebm")
        harmony_map_focus_chord(session, chord="Gm", section="Verse")
        restore_song_based_tab(session)
        self._assert_practice_minor(session, "Ebm")
        _simulate_next_run_prepare(session)
        self._assert_practice_minor(session, "Ebm")


class TestSongPracticeKeyIdempotencyAndBinding(unittest.TestCase):
    def test_consume_once_idempotent_rerun(self) -> None:
        session = _hevenu_song_based_session()
        _simulate_sidebar_key_change(session, "Ebm")
        pending = session.get("_music_pending_song_practice_key_edit")
        assert isinstance(pending, dict)
        token = str(pending.get("request_token") or "")
        fp_before = _progression_fingerprint(session)
        _simulate_pre_widget_consume(session)
        fp_after = _progression_fingerprint(session)
        self.assertNotEqual(fp_before, fp_after)
        phase2 = consume_pending_song_practice_key_edit(session)
        self.assertIn(phase2, {"skipped", "already_consumed"})
        self.assertEqual(_progression_fingerprint(session), fp_after)
        self.assertEqual(session.get(PENDING_SONG_PRACTICE_KEY_EDIT_CONSUMED_TOKEN_KEY), token)

    def test_same_key_no_double_transpose(self) -> None:
        session = _hevenu_song_based_session()
        _simulate_sidebar_key_change(session, "Ebm")
        _simulate_pre_widget_consume(session)
        fp = _progression_fingerprint(session)
        _simulate_sidebar_key_change(session, "Ebm")
        _simulate_pre_widget_consume(session)
        self.assertEqual(_progression_fingerprint(session), fp)

    def test_two_deliberate_changes_distinct_sequence(self) -> None:
        session = _hevenu_song_based_session()
        _simulate_sidebar_key_change(session, "Ebm")
        p1 = session.get("_music_pending_song_practice_key_edit")
        assert isinstance(p1, dict)
        seq1 = int(p1.get("request_seq") or 0)
        _simulate_pre_widget_consume(session)
        _simulate_sidebar_key_change(session, "Em")
        p2 = session.get("_music_pending_song_practice_key_edit")
        assert isinstance(p2, dict)
        seq2 = int(p2.get("request_seq") or 0)
        self.assertGreater(seq2, seq1)
        self.assertNotEqual(p1.get("request_token"), p2.get("request_token"))
        _simulate_pre_widget_consume(session)
        blob = get_workflow_blob(
            session,
            get_active_workflow_pointer(session).workflow_owner,
            get_active_workflow_pointer(session).workflow_session_id,
        )
        assert blob is not None
        self.assertEqual(str(blob.keys.practice_tonic or "").upper(), "E")

    def test_stale_pending_rejected_after_catalog_switch(self) -> None:
        session = _hevenu_song_based_session()
        _simulate_sidebar_key_change(session, "Ebm")
        self.assertIsNotNone(session.get("_music_pending_song_practice_key_edit"))
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=PK_SAY)
        self.assertIsNone(session.get("_music_pending_song_practice_key_edit"))
        diag = session.get("_music_pending_song_practice_key_edit_last_diag") or {}
        self.assertEqual(diag.get("failed_predicate"), "catalog_pick_mismatch")
        self.assertIn("Say", str(session.get("active_catalog_pick_key") or ""))

    def test_fingerprint_changes_once_per_valid_change(self) -> None:
        session = _hevenu_song_based_session()
        fp0 = _progression_fingerprint(session)
        _simulate_sidebar_key_change(session, "Ebm")
        _simulate_pre_widget_consume(session)
        fp1 = _progression_fingerprint(session)
        self.assertNotEqual(fp0, fp1)
        _simulate_sidebar_key_change(session, "Ebm")
        _simulate_pre_widget_consume(session)
        self.assertEqual(_progression_fingerprint(session), fp1)

    def test_refresh_after_ebm(self) -> None:
        session = _hevenu_song_based_session()
        _simulate_sidebar_key_change(session, "Ebm")
        _simulate_pre_widget_consume(session)
        _simulate_next_run_prepare(session)
        _simulate_next_run_prepare(session)
        self.assertEqual(str(session.get("display_key") or ""), "Ebm")
        ptr = get_active_workflow_pointer(session)
        assert ptr
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob
        self.assertEqual(str(blob.keys.practice_tonic or "").upper(), "EB")

    def test_full_production_harness_scenario(self) -> None:
        session: dict[str, Any] = {}
        outcome = run_song_based_minor_practice_key_harness_scenario(
            session,
            catalog=CATALOG,
            stale_say_session_factory=_stale_canonical_say_session,
            target_key="Ebm",
        )
        self.assertTrue(outcome.get("passed"), outcome)
        self.assertEqual(outcome.get("pre_widget"), "applied")
        self.assertTrue(outcome.get("pending_queued"))
        self.assertGreaterEqual(int(outcome.get("progression_chord_count") or 0), 4)
        self.assertGreaterEqual(int(outcome.get("blob_section_count") or 0), 1)
        ptr = get_active_workflow_pointer(session)
        assert ptr
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob
        self.assertEqual(str(blob.keys.practice_tonic or "").upper(), "EB")
        self.assertEqual(str(blob.keys.original_tonic or "").upper(), "D")


if __name__ == "__main__":
    unittest.main()
