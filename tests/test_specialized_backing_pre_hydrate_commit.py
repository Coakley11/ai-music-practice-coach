"""P7–P9: specialized Backing + play session must survive pre-hydrate catalog commit."""

from __future__ import annotations

import unittest
from types import SimpleNamespace


class SpecializedBackingPreHydrateCommitTests(unittest.TestCase):
    def _base(self, *, source: str, title: str, bound: str) -> dict:
        from backing_play_session import BACKING_PLAY_SESSION_KEY

        return {
            "studio_page": "backing",
            "active_catalog_pick_key": "Pop\x1fShape of You — Ed Sheeran",
            "display_key": "E",
            "concert_key": "E",
            "_backing_source_preference": "creative",
            "backing_context": {
                "source": source,
                "song_title": title,
                "active_song_id": bound,
                "bound_pick_key": bound,
                "bpm": 113,
                "style": "Blues",
                "scope": "Chorus",
                "meter": "3/4",
                "loops": 3,
                "key": "E",
                "display_key": "E",
                "concert_key": "E",
                "progression": ["E", "A", "B7"],
                "progression_label": title,
            },
            BACKING_PLAY_SESSION_KEY: {
                "play_session_id": "ps-special",
                "launch_id": "launch-special",
                "source_identity": f"creative:{source}:{bound}",
                "expired": False,
                "defaults": {
                    "bpm": 100,
                    "groove": "Pop",
                    "meter": "4/4",
                    "scope": "Full song",
                    "loops": 2,
                },
                "overrides": {
                    "bpm": 113,
                    "groove": "Blues",
                    "meter": "3/4",
                    "scope": "Chorus",
                    "loops": 3,
                },
            },
            "_backing_play_session_expired": False,
            "backing_track_bpm": 113,
            "backing_groove_style": "Blues",
        }

    def test_commit_does_not_expire_custom_sbi_play_session(self) -> None:
        from backing_context import get_backing_context
        from backing_play_session import get_backing_play_session
        from backing_source_navigation import commit_active_catalog_source_before_backing_hydrate

        session = self._base(
            source="song_improv",
            title="Trial Song",
            bound="custom::trial-song",
        )
        session["improv_song_source"] = "Custom progression"
        session["sbi_preview_source"] = "Custom progression"
        commit_active_catalog_source_before_backing_hydrate(
            session,
            st_like=SimpleNamespace(session_state=session),
            song_picker_catalog={},
            song_library={},
            invalidate_backing=lambda *_a, **_k: None,
        )
        ctx = get_backing_context(session)
        ps = get_backing_play_session(session) or {}
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "song_improv")
        self.assertEqual(int(ctx.bpm), 113)
        self.assertFalse(bool(ps.get("expired")))
        self.assertEqual(int((ps.get("overrides") or {}).get("bpm") or 0), 113)

    def test_intentional_creative_true_for_valid_specialized_ctx(self) -> None:
        from music_source_ownership import intentional_creative_backing_active

        session = self._base(
            source="song_improv",
            title="Trial Song",
            bound="custom::trial-song",
        )
        session["improv_song_source"] = "Custom progression"
        session["sbi_preview_source"] = "Custom progression"
        session["improv_entry_mode"] = "Song-Based Improvisation"
        self.assertTrue(intentional_creative_backing_active(session))


if __name__ == "__main__":
    unittest.main()
