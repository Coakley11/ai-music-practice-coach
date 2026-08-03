"""Item 4 passive startup audit — hard refresh must not false-positive autosave violations."""

from __future__ import annotations

import copy
import unittest
from typing import Any
from unittest.mock import patch

from creative_context_snapshot_persistence import (
    CREATIVE_CONTEXT_DIAG_KEY,
    CREATIVE_CONTEXT_HYDRATED_SNAPSHOT_KEY,
    CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY,
    SAVE_REASON_CONTEXT_SECTION,
    VIOLATION_PASSIVE_CONTEXT_STARTUP_WRITE,
    collect_creative_context_snapshot_diagnostics,
    context_violations_for_current_run,
    handle_user_harmony_map_context_change,
    note_passive_context_persist,
    snapshot_hydrated_context,
)
from creative_session_state import CreativeSession, set_creative_session
from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    default_creative_workspace_state,
    sync_creative_workspace_state_before_persist,
)


def _revision315_workspace() -> dict[str, Any]:
    cs = {
        "session_id": "abc123",
        "tool_type": "song_based_improvisation",
        "entry_mode": "Song-Based Improvisation",
        "display_key": "Cm",
        "concert_key": "Cm",
        "instrument": "Piano",
        "updated_at": "2026-08-03T12:00:00+00:00",
        "signature": "deadbeefcafebabe",
        "sections": {"Melody A": ["Ab", "G7"]},
        "intelligence_tab": "Missions",
    }
    return {
        **default_creative_workspace_state(),
        "harmony_map_section": "Melody A",
        "harmony_map_chord": "G7",
        "creative_session": copy.deepcopy(cs),
        "ii_selected_section": "Melody A",
        "ii_selected_chord_index": 3,
        "ii_selected_chord": "Ab",
        "ii_selected_chord_label": "Melody A · Ab",
    }


class TestItem4PassiveStartupAudit(unittest.TestCase):
    def test_hard_refresh_autosave_no_violation_when_only_volatile_creative_session_diff(self) -> None:
        ws = _revision315_workspace()
        ss: dict[str, Any] = {
            "_script_run_seq": 42,
            CREATIVE_WORKSPACE_STATE_KEY: copy.deepcopy(ws),
            "display_key": "Cm",
            "instrument": "Piano",
            "level": "Beginner",
            "focus": "Left-Hand Patterns",
        }
        snapshot_hydrated_context(ss, source="network")
        session_cs = copy.deepcopy(ws["creative_session"])
        session_cs.pop("instrument", None)
        session_cs["updated_at"] = "2026-08-03T15:00:00+00:00"
        ss["creative_session"] = session_cs
        ss["harmony_map_section"] = "Melody A"
        ss["harmony_map_chord"] = "G7"
        sync_creative_workspace_state_before_persist(ss, reason="autosave")
        violations = context_violations_for_current_run(ss)
        codes = [v.get("code") for v in violations]
        self.assertNotIn(VIOLATION_PASSIVE_CONTEXT_STARTUP_WRITE, codes)
        self.assertEqual(codes, [])

    def test_only_updated_at_change_on_set_creative_session_preserves_timestamp(self) -> None:
        ss: dict[str, Any] = {}
        sess = CreativeSession(
            session_id="x",
            tool_type="song_based_improvisation",
            entry_mode="Song-Based Improvisation",
            display_key="Cm",
            concert_key="Cm",
            updated_at="2026-08-03T12:00:00+00:00",
        )
        set_creative_session(ss, sess)
        first_at = ss["creative_session"]["updated_at"]
        sess2 = CreativeSession.from_dict(ss["creative_session"])
        assert sess2 is not None
        set_creative_session(ss, sess2)
        self.assertEqual(ss["creative_session"]["updated_at"], first_at)

    def test_sticky_save_diag_does_not_leak_old_violations_into_new_run(self) -> None:
        ss: dict[str, Any] = {
            "_script_run_seq": 99,
            CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY: {
                "payload_revision": 315,
                "save_reason": SAVE_REASON_CONTEXT_SECTION,
            },
            CREATIVE_CONTEXT_DIAG_KEY: {
                "violations": [
                    {
                        "code": VIOLATION_PASSIVE_CONTEXT_STARTUP_WRITE,
                        "detail": "key=creative_session|reason=autosave",
                        "run_seq": 5,
                    }
                ],
            },
        }
        diag = collect_creative_context_snapshot_diagnostics(ss)
        self.assertEqual(diag["payload_revision"], 315)
        self.assertEqual(diag["violations"], [])

    def test_real_harmony_map_click_still_records_explicit_save_reason(self) -> None:
        ss: dict[str, Any] = {
            "_script_run_seq": 7,
            "display_key": "Cm",
            CREATIVE_WORKSPACE_STATE_KEY: _revision315_workspace(),
        }
        with patch("music_persistent_state.force_save_music_state", return_value=True):
            handle_user_harmony_map_context_change(ss, section="Melody A", chord="G7")
        last = ss.get(CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY) or {}
        self.assertEqual(last.get("save_reason"), SAVE_REASON_CONTEXT_SECTION)

    def test_note_passive_autosave_semantic_drift_without_gather_emits_no_violation(self) -> None:
        ws = _revision315_workspace()
        ss: dict[str, Any] = {
            "_script_run_seq": 1,
            CREATIVE_WORKSPACE_STATE_KEY: copy.deepcopy(ws),
            CREATIVE_CONTEXT_HYDRATED_SNAPSHOT_KEY: {
                "creative_session": copy.deepcopy(ws["creative_session"]),
            },
        }
        ss["creative_session"] = {"tool_type": "mission", "entry_mode": "Song-Based Improvisation"}
        note_passive_context_persist(ss, reason="autosave")
        self.assertEqual(context_violations_for_current_run(ss), [])


if __name__ == "__main__":
    unittest.main()
