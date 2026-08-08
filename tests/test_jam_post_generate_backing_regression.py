"""Regression: jam blob authority vs stale legacy improv_jam_session + backing activation."""

from __future__ import annotations

import copy
import unittest
import uuid

from backing_context import creative_specialized_backing_handoff_ready, open_backing_from_creative
from creative_session_state import apply_creative_session_to_session, CreativeSession, hydrate_creative_session_for_page
from improv_jam_session_projection import jam_session_fingerprint, sync_improv_jam_session_from_active_blob
from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
from music_workflow_generated_session import commit_jam_session_generation
from music_workflow_state_store import KeyAuthority, WorkflowStateBlob, get_active_workflow_pointer, get_workflow_blob, save_workflow_blob
from musical_context_coherence import CreativeBackingHandoffBlocked, run_musical_context_coherence_checks


def _bossa_c() -> dict[str, list[str]]:
    return {"A": ["Dm7", "G7", "Cmaj7", "Cmaj7"], "B": ["Dm7", "G7", "Am7", "D7"]}


def _bossa_eb() -> dict[str, list[str]]:
    return {"A": ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"]}


class JamPostGenerateBackingRegressionTests(unittest.TestCase):
    def _seed_coherent_c_jam(self) -> tuple[dict, str]:
        sid = str(uuid.uuid4())
        jam = {
            "id": sid,
            "key": "C",
            "style": "Bossa Nova",
            "ensemble": "Jazz trio",
            "prompt": "**Jazz trio** in **C** · Bossa Nova · ~110 BPM · test.",
            "sections": copy.deepcopy(_bossa_c()),
        }
        session: dict = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Bossa Nova",
            "improv_jam_key": "C",
            "improv_jam_mood": "Bright",
            "improv_jam_session": copy.deepcopy(jam),
            "display_key": "C",
            "concert_key": "C",
            "studio_page": "creative",
        }
        commit_jam_session_generation(
            session,
            jam,
            key_center="C",
            style="Bossa Nova",
            new_session=True,
        )
        return session, sid

    def test_stale_eb_legacy_repaired_from_blob_on_sync(self) -> None:
        session, sid = self._seed_coherent_c_jam()
        session["improv_jam_session"] = {
            "id": sid,
            "key": "Eb",
            "prompt": "**Jazz trio** in **Eb**",
            "sections": copy.deepcopy(_bossa_eb()),
        }
        self.assertTrue(
            sync_improv_jam_session_from_active_blob(session, writer="test", phase="stale_inject")
        )
        fp = jam_session_fingerprint(session.get("improv_jam_session"))
        self.assertEqual(fp["key"], "C")
        self.assertEqual(fp["head"][:3], ["Dm7", "G7", "Cmaj7"])

    def test_apply_creative_session_does_not_revert_to_stale_eb(self) -> None:
        session, sid = self._seed_coherent_c_jam()
        session["improv_jam_session"] = {
            "id": sid,
            "key": "Eb",
            "sections": copy.deepcopy(_bossa_eb()),
        }
        stale_sess = CreativeSession(
            session_id="stale",
            tool_type="jam_session_generator",
            entry_mode="Jam Session Generator",
            concert_key="C",
            display_key="C",
            style="Bossa Nova",
            mood="Bright",
            bpm=110,
            sections=copy.deepcopy(_bossa_eb()),
        )
        apply_creative_session_to_session(session, stale_sess, widget_safe=False)
        fp = jam_session_fingerprint(session.get("improv_jam_session"))
        self.assertEqual(fp["head"][:3], ["Dm7", "G7", "Cmaj7"])

    def test_open_backing_preserves_workflow_session_uuid(self) -> None:
        session, _sid = self._seed_coherent_c_jam()
        ptr_before = get_active_workflow_pointer(session)
        assert ptr_before is not None
        sid_before = str(ptr_before.workflow_session_id or "")
        sync_improv_jam_session_from_active_blob(session, writer="test", phase="pre_backing")
        open_backing_from_creative(session, source="entry_jam")
        ptr = get_active_workflow_pointer(session)
        self.assertIsNotNone(ptr)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "jam_session_generator")
        self.assertEqual(str(ptr.workflow_session_id or ""), sid_before)
        self.assertNotEqual(ptr.workflow_session_id, "Bossa Nova")
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        self.assertIsNotNone(blob)
        assert blob is not None
        self.assertEqual(str(blob.keys.practice_tonic), "C")
        head = [c for sec in blob.section_map.values() for c in sec][:3]
        self.assertEqual(head, ["Dm7", "G7", "Cmaj7"])
        ok, reason = creative_specialized_backing_handoff_ready(session, creative_source="entry_jam")
        self.assertTrue(ok, reason)

    def test_activate_route_only_does_not_rebuild_blob_from_stale_legacy(self) -> None:
        session, sid = self._seed_coherent_c_jam()
        session["improv_jam_session"] = {
            "id": sid,
            "key": "Eb",
            "sections": copy.deepcopy(_bossa_eb()),
        }
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        sid = str(ptr.workflow_session_id or "")
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="jam_session_generator",
                target_session_id=sid,
                activation_source="open_backing_from_creative",
                page_route="backing",
                return_route="creative",
                navigation_intent="backing_open",
            ),
        )
        blob = get_workflow_blob(session, "jam_session_generator", sid)
        assert blob is not None
        head = [c for sec in blob.section_map.values() for c in sec][:3]
        self.assertEqual(head, ["Dm7", "G7", "Cmaj7"])

    def test_hybrid_blob_blocks_handoff_ready(self) -> None:
        session, _sid = self._seed_coherent_c_jam()
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        blob = get_workflow_blob(session, "jam_session_generator", str(ptr.workflow_session_id or ""))
        assert blob is not None
        blob.section_map = copy.deepcopy(_bossa_eb())
        save_workflow_blob(session, blob, source="test_hybrid")
        from musical_context_coherence import MUSICAL_CONTEXT_COHERENCE_BLOCK_KEY, record_coherence_handoff_block

        record_coherence_handoff_block(session, ["UNTRANSPOSED_GENERATED_ARTIFACT test"])
        ok, reason = creative_specialized_backing_handoff_ready(session, creative_source="entry_jam")
        self.assertFalse(ok)
        self.assertEqual(reason, "coherence_blocked")


if __name__ == "__main__":
    unittest.main()
