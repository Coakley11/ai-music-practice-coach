"""Mission pending Upload Analysis envelope persistence."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from mission_pending_upload_analysis import (
    PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY,
    audio_fingerprint,
    build_pending_upload_envelope,
    merge_envelope_revisions,
)
from mission_pending_upload_persistence import (
    apply_pending_upload_envelope_to_session,
    clear_prepared_mission_upload,
    persist_mission_pending_upload_handoff,
)
from mission_upload_handoff import handoff_mission_take_to_upload_analysis


def _tone_wav() -> bytes:
    import struct

    pcm = b"\x00\x01" * 200
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        44100,
        88200,
        2,
        16,
        b"data",
        len(pcm),
    )
    return header + pcm


class TestMissionPendingUploadPersistence(unittest.TestCase):
    def test_handoff_persists_envelope_and_dedupes_audio(self) -> None:
        session: dict[str, Any] = {
            "improv_active_mission": "Develop one motif",
            "ii_selected_chord": "Em",
            "ii_selected_chord_index": 0,
            "improv_ai_metric_ids": ["chord_tone_targeting"],
            "creative_workspace_state": {"schema_version": 1},
        }
        wav = _tone_wav()
        store_calls: list[int] = []

        def _fake_persist(_st, _rid, audio, **kwargs):
            store_calls.append(len(audio))
            return {
                "ok": True,
                "storage_ref": "supabase://music-media/u/ws/t.wav",
                "local_path": "media/recordings/x.wav",
                "playback_status": "playable",
            }

        with patch("media_storage.persist_recording_audio", side_effect=_fake_persist):
            handoff_mission_take_to_upload_analysis(
                session, audio_bytes=wav, filename="t.wav", source="live"
            )
            self.assertEqual(len(store_calls), 1)
            handoff_mission_take_to_upload_analysis(
                session, audio_bytes=wav, filename="t.wav", source="live"
            )
            self.assertEqual(len(store_calls), 1)
        env = session.get(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY)
        self.assertIsInstance(env, dict)
        self.assertEqual(env.get("analysis_status"), "prepared")
        self.assertEqual((env.get("dry_audio") or {}).get("fingerprint"), audio_fingerprint(wav))

    def test_stale_envelope_not_overwritten(self) -> None:
        old = {"take_id": "a", "handoff_revision": 5, "dry_audio": {"fingerprint": "x"}}
        new = {"take_id": "b", "handoff_revision": 3, "dry_audio": {"fingerprint": "y"}}
        merged, ok = merge_envelope_revisions(old, new)
        self.assertFalse(ok)
        self.assertEqual(merged["take_id"], "a")

    def test_apply_hydrates_prepared_upload(self) -> None:
        session: dict[str, Any] = {
            PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: {
                "take_id": "tid",
                "handoff_revision": 2,
                "analysis_status": "prepared",
                "source": "mission_live_recording",
                "dry_audio": {
                    "recording_id": "tid",
                    "fingerprint": "abc",
                    "local_path": "media/recordings/tid.wav",
                },
                "metrics": {"effective_metric_ids": ["chord_tone_targeting"]},
                "evaluation_criteria": {"custom_goal": "focus"},
            }
        }
        wav = _tone_wav()
        with patch(
            "media_storage.load_recording_audio",
            return_value=(wav, ""),
        ):
            diag = apply_pending_upload_envelope_to_session(session, source="test")
        self.assertTrue(diag.get("restored"))
        self.assertIsNotNone(session.get("_analysis_prepared_upload"))
        self.assertEqual(session.get("analysis_custom_goal"), "focus")

    def test_clear_removes_pending(self) -> None:
        session: dict[str, Any] = {
            PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: {"take_id": "x", "analysis_status": "prepared"},
            "_analysis_prepared_upload": object(),
        }
        clear_prepared_mission_upload(session)
        self.assertNotIn(PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY, session)


if __name__ == "__main__":
    unittest.main()
