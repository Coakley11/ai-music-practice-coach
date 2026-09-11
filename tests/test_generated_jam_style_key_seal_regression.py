"""Regression A–D: generated Jam / Style Jam sealed concert key + backing handoff."""

from __future__ import annotations

import copy
import unittest

from backing_context import build_entry_jam_context
from generated_jam_key_context import (
    GENERATED_JAM_KEY_CONTEXT_KEY,
    deactivate_generated_jam_key_ownership,
    generated_jam_owns_practice_key,
)
from generated_workflow_artifact import (
    build_snapshot_from_session,
    detect_cross_owner_handoff_fields,
    seal_backing_handoff_snapshot_for_creative_open,
)
from improvisation_intelligence import flatten_sections, generate_style_progression
from music_workflow_generated_session import resolve_generated_concert_key_for_owner, seal_jam_session_musical_context
from music_workflow_mutation import update_active_practice_key
from music_workflow_pending_generated_progression import (
    consume_pending_generated_progression,
    queue_generated_progression_intent,
)
from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob


def _session(**extra: object) -> dict:
    base: dict = {"_suite_active_workspace_id": "daniel"}
    base.update(extra)
    return base


def _jam_creative_session(*, jam_key: str = "Eb", display_key: str = "Eb") -> dict:
    return {
        "studio_page": "creative",
        "improv_entry_mode": "Jam Session Generator",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_jam_key": jam_key,
        "improv_jam_style": "Jazz Swing",
        "improv_jam_mood": "Mellow",
        "improv_jam_bpm": 120,
        "improv_ensemble": "Jazz trio",
        "display_key": display_key,
        "concert_key": display_key,
    }


def _style_creative_session(*, style_key: str = "Eb") -> dict:
    return {
        "studio_page": "creative",
        "improv_entry_mode": "Style Jam Mode",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_style": "Jazz Swing",
        "improv_style_key": style_key,
        "improv_mood": "Mellow",
        "improv_difficulty": "Intermediate",
        "improv_style_bpm": 110,
        "display_key": style_key,
        "concert_key": style_key,
    }


class GeneratedJamStyleKeySealRegressionTests(unittest.TestCase):
    def test_a_jam_generator_request_c_sealed_context(self) -> None:
        session = _session(**_jam_creative_session(jam_key="C", display_key="Eb"))
        session["improv_jam_key"] = "C"
        queue_generated_progression_intent(session, owner="jam_session_generator")
        self.assertEqual(consume_pending_generated_progression(session), "done")

        jam = session.get("improv_jam_session") or {}
        self.assertIn("**C**", str(jam.get("prompt") or ""))
        self.assertEqual(str(jam.get("key") or ""), "C")
        flat = flatten_sections(jam.get("sections") or {})
        joined = " ".join(flat).upper()
        self.assertNotIn("EBMAJ7", joined)
        self.assertTrue(any("CMAJ7" in c.upper() or "CMAJ" in c.upper() for c in flat))

        self.assertEqual(str(session.get("improv_jam_key") or ""), "C")
        self.assertEqual(str(session.get("display_key") or ""), "Eb")
        ctx_raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY) or {}
        self.assertEqual(str(ctx_raw.get("practice_tonic") or ""), "C")

        ptr = get_active_workflow_pointer(session)
        self.assertIsNotNone(ptr)
        assert ptr is not None
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        self.assertIsNotNone(blob)
        assert blob is not None
        self.assertEqual(str(blob.keys.practice_tonic or ""), "C")

        session["improv_entry_mode"] = "Jam Session Generator"
        self.assertTrue(seal_backing_handoff_snapshot_for_creative_open(session))
        snap = build_snapshot_from_session(session, owner="jam_session_generator")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(str(snap.practice_tonic or ""), "C")
        self.assertNotIn("EBMAJ7", " ".join(snap.progression or []).upper())

    def test_b_style_jam_request_c_coherent_sections_and_backing(self) -> None:
        session = _session(**_style_creative_session(style_key="C"))
        queue_generated_progression_intent(session, owner="style_jam")
        self.assertEqual(consume_pending_generated_progression(session), "done")

        sections = session.get("improv_generated_sections") or {}
        flat = flatten_sections(sections)
        self.assertTrue(flat)
        self.assertNotIn("EBMAJ7", " ".join(flat).upper())
        self.assertEqual(str(session.get("display_key") or ""), "C")
        self.assertTrue(generated_jam_owns_practice_key(session))

        session["improv_entry_mode"] = "Style Jam Mode"
        self.assertTrue(seal_backing_handoff_snapshot_for_creative_open(session))
        snap = build_snapshot_from_session(session, owner="style_jam")
        self.assertIsNotNone(snap)
        assert snap is not None
        violations = detect_cross_owner_handoff_fields(session, snap)
        self.assertEqual(violations, [])
        ctx = build_entry_jam_context(session)
        self.assertEqual(str(ctx.concert_key or ""), "C")

    def test_c_key_change_c_to_d_rebuilds_progression(self) -> None:
        session = _session(**_style_creative_session(style_key="C"))
        queue_generated_progression_intent(session, owner="style_jam")
        consume_pending_generated_progression(session)
        before = copy.deepcopy(session.get("improv_generated_sections") or {})

        session["improv_style_key"] = "D"
        result = update_active_practice_key(session, "D", source="on_improv_style_key_change")
        self.assertTrue(result.ok)
        after = session.get("improv_generated_sections") or {}
        self.assertNotEqual(before, after)
        d_prog = generate_style_progression(style="Jazz Swing", key_center="D", mood="Mellow")
        self.assertEqual(
            flatten_sections(after)[:3],
            flatten_sections(d_prog)[:3],
        )

    def test_d_leave_generated_workflow_releases_jam_ownership(self) -> None:
        session = _session(**_jam_creative_session(jam_key="C", display_key="C"))
        queue_generated_progression_intent(session, owner="jam_session_generator")
        consume_pending_generated_progression(session)
        self.assertTrue(generated_jam_owns_practice_key(session))

        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_intelligence_tab"] = "Missions"
        session["display_key"] = "Dm"
        session["concert_key"] = "Dm"
        session["song_based_blob_practice_key"] = "Dm"
        deactivate_generated_jam_key_ownership(session, pre_widget=True)
        self.assertFalse(generated_jam_owns_practice_key(session))

    def test_resolve_key_honors_pending_jam_widget_over_stale_session(self) -> None:
        session = _session(**_jam_creative_session(jam_key="Eb", display_key="Eb"))
        session["improv_jam_key"] = "Eb"
        try:
            from creative_key_sync import PENDING_IMPROV_JAM_KEY

            session[PENDING_IMPROV_JAM_KEY] = "C"
        except ImportError:
            session["_pending_improv_jam_key"] = "C"
        self.assertEqual(resolve_generated_concert_key_for_owner(session, "jam_session_generator"), "C")

    def test_seal_jam_session_updates_prompt(self) -> None:
        jam = {
            "ensemble": "Jazz trio",
            "style": "Jazz Swing",
            "key": "Eb",
            "bpm": 120,
            "sections": {"A": ["Fm7", "Bb7", "Ebmaj7"]},
            "prompt": "**Jazz trio** in **Eb** · Jazz Swing · ~120 BPM · dark",
        }
        sealed = seal_jam_session_musical_context(jam, key_center="C", sections={"A": ["Dm7", "G7", "Cmaj7"]})
        self.assertIn("**C**", sealed["prompt"])
        self.assertEqual(sealed["key"], "C")


if __name__ == "__main__":
    unittest.main()
