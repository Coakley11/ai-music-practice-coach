"""Media state schema, merge, tombstone, and AMI compact tests."""

from __future__ import annotations

import unittest

from media_state import (
    build_media_ami_payload_from_catalog,
    is_recording_tombstone,
    merge_catalog,
    merge_media_records,
    migrate_multitrack_session,
    migrate_uploaded_recording,
    normalize_multitrack_sessions,
    normalize_uploaded_recordings,
)


class TestMediaState(unittest.TestCase):
    def test_migrate_legacy_upload_history_row(self) -> None:
        row = migrate_uploaded_recording(
            {
                "payload": {
                    "workspace_id": "daniel",
                    "saved_at": "2026-06-20T12:00:00+00:00",
                    "title": "Say take 1",
                    "source_label": "say_take1.wav",
                    "recording_type": "Practice take",
                    "notes": "tone focus",
                    "scores_summary": {
                        "coach_summary": "Work on timing in the chorus",
                        "timing": 6,
                        "tone": 7,
                    },
                },
                "item_key": "upload_20260620T120000_abcd1234",
            }
        )
        self.assertTrue(row.get("recording_id"))
        self.assertEqual(row.get("filename"), "say_take1.wav")
        self.assertEqual(row.get("song"), "Say take 1")
        self.assertIn("timing", str(row.get("analysis_summary") or {}))

    def test_migrate_legacy_multitrack_history_row(self) -> None:
        row = migrate_multitrack_session(
            {
                "payload": {
                    "workspace_id": "daniel",
                    "saved_at": "2026-06-21T10:00:00+00:00",
                    "project_name": "Say — 2 layers",
                    "song_title": "Say",
                    "notes": "compare takes",
                    "tracks": [
                        {
                            "slot": "Sax / winds",
                            "layer_name": "Take 1",
                            "filename": "take1.wav",
                            "has_audio": True,
                            "volume": 1.0,
                        }
                    ],
                    "analysis_summary": {"coach_summary": "Layer balance needs work"},
                },
                "item_key": "mt_20260621T100000_efgh5678",
            }
        )
        self.assertTrue(row.get("multitrack_id"))
        self.assertEqual(row.get("song"), "Say")
        self.assertEqual(len(row.get("tracks") or []), 1)
        self.assertEqual(row["tracks"][0].get("name"), "Take 1")

    def test_merge_media_records_newer_wins(self) -> None:
        older = migrate_uploaded_recording(
            {
                "recording_id": "rec-1",
                "filename": "a.wav",
                "notes": "old",
                "updated_at": "2026-06-01T10:00:00+00:00",
            }
        )
        newer = migrate_uploaded_recording(
            {
                "recording_id": "rec-1",
                "filename": "a.wav",
                "notes": "new",
                "updated_at": "2026-06-02T10:00:00+00:00",
            }
        )
        merged = merge_media_records([older], [newer], migrate=migrate_uploaded_recording, id_key="recording_id")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].get("notes"), "new")

    def test_tombstone_hides_recording(self) -> None:
        visible = migrate_uploaded_recording(
            {
                "recording_id": "rec-del",
                "filename": "gone.wav",
                "updated_at": "2026-06-01T10:00:00+00:00",
            }
        )
        tomb = {
            "recording_id": "rec-del",
            "deleted": True,
            "updated_at": "2026-06-03T10:00:00+00:00",
        }
        rows = normalize_uploaded_recordings([visible, tomb])
        self.assertEqual(len(rows), 0)

    def test_tombstone_newer_than_visible_wins(self) -> None:
        visible = migrate_uploaded_recording(
            {
                "recording_id": "rec-x",
                "filename": "x.wav",
                "updated_at": "2026-06-05T10:00:00+00:00",
            }
        )
        tomb = {
            "recording_id": "rec-x",
            "deleted": True,
            "updated_at": "2026-06-06T10:00:00+00:00",
        }
        self.assertEqual(len(normalize_uploaded_recordings([visible, tomb])), 0)

    def test_phone_dell_upload_merge(self) -> None:
        phone = merge_catalog(
            {
                "workspace_id": "daniel",
                "uploaded_recordings": [
                    migrate_uploaded_recording(
                        {
                            "recording_id": "phone-only",
                            "filename": "phone.wav",
                            "updated_at": "2026-06-10T10:00:00+00:00",
                        }
                    )
                ],
                "multitrack_sessions": [],
            },
            {
                "workspace_id": "daniel",
                "uploaded_recordings": [
                    migrate_uploaded_recording(
                        {
                            "recording_id": "dell-only",
                            "filename": "dell.wav",
                            "updated_at": "2026-06-11T10:00:00+00:00",
                        }
                    )
                ],
                "multitrack_sessions": [],
            },
        )
        ids = {r.get("recording_id") for r in phone.get("uploaded_recordings") or []}
        self.assertIn("phone-only", ids)
        self.assertIn("dell-only", ids)

    def test_ami_payload_excludes_deleted(self) -> None:
        payload = build_media_ami_payload_from_catalog(
            {
                "uploaded_recordings": [
                    migrate_uploaded_recording(
                        {
                            "recording_id": "live",
                            "song": "Say",
                            "instrument": "Tenor Saxophone",
                            "updated_at": "2026-06-27T10:00:00+00:00",
                        }
                    ),
                    {"recording_id": "dead", "deleted": True, "updated_at": "2026-06-27T11:00:00+00:00"},
                ],
                "multitrack_sessions": [],
            },
            window_days=30,
        )
        self.assertEqual(len(payload.get("uploaded_recordings") or []), 1)
        self.assertEqual(payload["uploaded_recordings"][0].get("song"), "Say")
        self.assertNotIn("dead", {r.get("recording_id") for r in payload.get("uploaded_recordings") or []})


if __name__ == "__main__":
    unittest.main()
