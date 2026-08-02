"""Canonical fingerprint normalization (Phase 0 Category A)."""

from __future__ import annotations

import unittest

from music_workspace_canonical_fingerprint import (
    diff_canonical_paths,
    workspace_canonical_content_fingerprint,
)


class CanonicalFingerprintNormalizationTests(unittest.TestCase):
    def test_noise_fields_do_not_affect_fingerprint(self) -> None:
        base = {
            "active_song_state": {
                "instrument": "Saxophone",
                "music_source": "catalog",
                "guitar_capo_shape_key": "G",
                "last_write_reason": "song_edit",
                "selected_song": {"title": "Song", "label": "Song — display"},
            },
            "backing_track_state": {
                "backing_track_bpm": 92,
                "backing_groove_style": "swing",
                "backing_transport_status": "playing",
                "last_write_reason": "backing_edit",
            },
            "practice_state": {
                "practice_minutes": 25,
                "practice_groove_style": "bossa",
                "last_write_reason": "practice_edit",
            },
            "practice_workspace_state": {"updated_at": "2026-01-02T00:00:00Z", "focus": "Tone"},
            "music_workspace_state": {
                "studio_page": "practice",
                "active_song": {"source_type": "catalog", "music_source": "catalog"},
                "backing_filters": {
                    "backing_track_bpm": 92,
                    "backing_groove_style": "swing",
                    "backing_transport_status": "stopped",
                },
                "practice_filters": {
                    "practice_minutes": 25,
                    "practice_groove_style": "bossa",
                },
            },
        }
        clean = {
            "active_song_state": {
                "instrument": "Saxophone",
                "music_source": "catalog",
                "selected_song": {"title": "Song"},
            },
            "backing_track_state": {
                "backing_track_bpm": 92,
                "backing_groove_style": "swing",
            },
            "practice_state": {
                "practice_minutes": 25,
                "practice_groove_style": "bossa",
            },
            "practice_workspace_state": {"focus": "Tone"},
            "music_workspace_state": {
                "studio_page": "practice",
                "active_song": {"music_source": "catalog"},
                "backing_filters": {
                    "backing_track_bpm": 92,
                    "backing_groove_style": "swing",
                },
                "practice_filters": {
                    "practice_minutes": 25,
                    "practice_groove_style": "bossa",
                },
            },
        }
        self.assertEqual(
            workspace_canonical_content_fingerprint(base),
            workspace_canonical_content_fingerprint(clean),
        )

    def test_display_key_owner_and_mission_updated_at_ignored(self) -> None:
        a = {
            "active_song_state": {
                "instrument": "Piano",
                "display_key": "C",
                "display_key_owner_identity": "owner-a",
            },
            "creative_workspace_state": {
                "improv_mission_workspace_updated_at": "2026-01-01T00:00:00Z",
            },
            "music_workspace_state": {
                "studio_page": "backing",
                "creative_workspace_state": {
                    "improv_mission_workspace_updated_at": "2026-01-02T00:00:00Z",
                },
            },
        }
        b = {
            "active_song_state": {
                "instrument": "Piano",
                "display_key": "C",
            },
            "creative_workspace_state": {},
            "music_workspace_state": {
                "studio_page": "backing",
                "creative_workspace_state": {},
            },
        }
        self.assertEqual(workspace_canonical_content_fingerprint(a), workspace_canonical_content_fingerprint(b))


if __name__ == "__main__":
    unittest.main()
