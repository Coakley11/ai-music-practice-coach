"""Songs source leave must release stale Mission→Upload recording identity lock."""

from __future__ import annotations

import unittest

from mission_upload_handoff import (
    MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY,
    handoff_mission_take_to_upload_analysis,
    release_stale_mission_upload_identity_on_songs_leave,
)
from recording_analysis_context import (
    ANALYSIS_IDENTITY_LOCKED_KEY,
    RECORDING_TYPE_PRACTICE,
    is_genuine_mission_upload_handoff,
)
from songs.music_source import (
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
    commit_explicit_music_source_choice,
)


class TestSongsLeaveReleasesMissionUploadLock(unittest.TestCase):
    def _handed_off_session(self) -> dict:
        session: dict = {
            "song": "Tune",
            "improv_active_mission": "Develop one motif",
            "improv_mission_pick": "Develop one motif",
            "improv_mission_chord_options": ["Ab7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Ab7",
            "improv_mission_evaluation_focus": "Melodic development",
            "analysis_ai_metric_ids": ["motif_development"],
            "analysis_mission_ids": ["motif_development"],
        }
        audio = b"RIFF" + b"\x00" * 40 + b"data" + b"\x00" * 100
        handoff_mission_take_to_upload_analysis(
            session,
            audio_bytes=audio,
            filename="take.wav",
            source="upload",
        )
        # Criteria selections the user kept on Upload — must survive Songs leave.
        session["analysis_ai_metric_ids"] = ["motif_development"]
        session["analysis_mission_ids"] = ["motif_development"]
        session[ANALYSIS_IDENTITY_LOCKED_KEY] = True
        from mission_pending_upload_persistence import PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY

        session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = {
            "analysis_status": "prepared",
            "take_id": "take-1",
        }
        return session

    def test_catalog_commit_clears_handoff_keeps_mission_criteria_ids(self) -> None:
        session = self._handed_off_session()
        self.assertTrue(is_genuine_mission_upload_handoff(session))
        metrics = list(session.get("analysis_ai_metric_ids") or [])
        mission_ids = list(session.get("analysis_mission_ids") or [])
        self.assertTrue(metrics)

        commit_explicit_music_source_choice(session, SOURCE_CATALOG)

        self.assertFalse(is_genuine_mission_upload_handoff(session))
        self.assertNotIn(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY, session)
        self.assertNotIn(ANALYSIS_IDENTITY_LOCKED_KEY, session)
        self.assertEqual(session.get("analysis_recording_type"), RECORDING_TYPE_PRACTICE)
        self.assertEqual(session.get("analysis_sync_creative_mission"), False)
        # Evaluation criteria selections survive; only the identity lock clears.
        self.assertEqual(session.get("analysis_ai_metric_ids"), metrics)
        self.assertEqual(session.get("analysis_mission_ids"), mission_ids)
        self.assertEqual(session.get("improv_active_mission"), "Develop one motif")
        from mission_pending_upload_persistence import PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY

        self.assertIsNone(session.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY))

    def test_custom_and_composition_commits_also_release(self) -> None:
        for source in (SOURCE_CUSTOM, SOURCE_COMPOSITION):
            session = self._handed_off_session()
            commit_explicit_music_source_choice(session, source)
            self.assertFalse(
                is_genuine_mission_upload_handoff(session),
                msg=f"expected unlock after {source}",
            )

    def test_direct_mission_handoff_still_locks(self) -> None:
        session: dict = {
            "improv_active_mission": "Develop one motif",
            "improv_mission_pick": "Develop one motif",
            "ii_selected_chord": "Ab7",
        }
        audio = b"RIFF" + b"\x00" * 40 + b"data" + b"\x00" * 100
        handoff_mission_take_to_upload_analysis(
            session,
            audio_bytes=audio,
            filename="take.wav",
            source="live",
        )
        self.assertTrue(is_genuine_mission_upload_handoff(session))
        self.assertEqual(session.get("analysis_recording_type"), "Mission Recording")
        # No Songs leave → lock remains.
        self.assertTrue(session.get(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY))

    def test_release_helper_idempotent(self) -> None:
        session = {"analysis_recording_type": "Mission Recording"}
        self.assertFalse(release_stale_mission_upload_identity_on_songs_leave(session))
        self.assertEqual(session.get("analysis_recording_type"), RECORDING_TYPE_PRACTICE)


if __name__ == "__main__":
    unittest.main()
