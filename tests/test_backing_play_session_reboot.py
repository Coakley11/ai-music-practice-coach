"""Play-session transport must survive refresh/reboot; remint only after true leave."""

from __future__ import annotations

import unittest


SHAPE = "Pop\x1fShape of You — Ed Sheeran"
TRIAL = "custom::trial-song"


def _chords() -> list[dict]:
    return [{"symbol": "E"}, {"symbol": "A"}, {"symbol": "B7"}]


def _custom_sbi_session(*, with_overrides: bool = True, expired: bool = False) -> dict:
    from backing_play_session import BACKING_PLAY_SESSION_KEY

    overrides = (
        {"bpm": 113, "groove": "Blues", "scope": "Chorus", "loops": 3, "meter": "3/4"}
        if with_overrides and not expired
        else {}
    )
    return {
        "studio_page": "backing",
        "active_catalog_pick_key": SHAPE,
        "display_key": "E",
        "concert_key": "E",
        "improv_song_source": "Custom progression",
        "sbi_preview_source": "Custom progression",
        "improv_entry_mode": "Song-Based Improvisation",
        "backing_context": {
            "source": "song_improv",
            "source_label": "Song-Based Improvisation",
            "song_title": "Trial Song",
            "active_song_id": TRIAL,
            "bound_pick_key": TRIAL,
            "custom_revision_id": "trial-rev-1",
            "key": "E",
            "display_key": "E",
            "concert_key": "E",
            "bpm": 113 if with_overrides else 100,
            "style": "Blues" if with_overrides else "Pop",
            "groove": "",
            "meter": "3/4" if with_overrides else "4/4",
            "scope": "Chorus" if with_overrides else "Full song",
            "loops": 3 if with_overrides else 2,
            "progression": ["E", "A", "B7"],
            "progression_label": "Trial Song",
            "entry_mode": "Song-Based Improvisation",
            "mode_label": "Song-Based Improvisation",
        },
        BACKING_PLAY_SESSION_KEY: {
            "play_session_id": "ps-unit-1",
            "launch_id": "launch-unit-1",
            "source_identity": f"creative:song_improv:{TRIAL}",
            "expired": expired,
            "defaults": {
                "bpm": 100,
                "groove": "Pop",
                "meter": "4/4",
                "scope": "Full song",
                "loops": 2,
            },
            "overrides": overrides,
            "current_bpm_lock": 113 if with_overrides and not expired else 0,
        },
        "_backing_play_session_expired": expired,
        "backing_track_bpm": 113 if with_overrides and not expired else 100,
        "backing_groove_style": "Blues" if with_overrides and not expired else "Pop",
        "backing_track_scope": "Chorus" if with_overrides and not expired else "Full song",
        "backing_track_loops": 3 if with_overrides and not expired else 2,
        "cpl_active_progression": {
            "id": "trial-rev-1",
            "name": "Trial Song",
            "original_key_center": "C",
            "bpm": 100,
            "progression_style": "Pop",
            "original_sections": {"A": _chords(), "Chorus": _chords()},
        },
    }


class BackingPlaySessionRebootTests(unittest.TestCase):
    def test_refresh_keeps_play_session_bpm_style_over_cpl_defaults(self) -> None:
        from backing_context import refresh_backing_context_from_session

        session = _custom_sbi_session(with_overrides=True)
        refreshed = refresh_backing_context_from_session(session)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(int(refreshed.bpm), 113)
        self.assertEqual(str(refreshed.style), "Blues")
        self.assertEqual(str(refreshed.scope), "Chorus")
        self.assertEqual(int(refreshed.loops), 3)
        self.assertEqual(str(getattr(refreshed, "meter", "") or ""), "3/4")

    def test_expire_then_refresh_returns_source_defaults(self) -> None:
        from backing_context import refresh_backing_context_from_session
        from backing_play_session import expire_backing_play_session

        session = _custom_sbi_session(with_overrides=True)
        expire_backing_play_session(session)
        refreshed = refresh_backing_context_from_session(session)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(int(refreshed.bpm), 100)
        self.assertEqual(str(refreshed.style), "Pop")

    def test_recover_overrides_from_sealed_ctx_when_bag_empty(self) -> None:
        from backing_context import get_backing_context, refresh_backing_context_from_session
        from backing_play_session import (
            BACKING_PLAY_SESSION_KEY,
            recover_play_session_overrides_from_backing_context,
            sync_backing_play_session_on_backing_page,
        )

        session = _custom_sbi_session(with_overrides=True)
        # Empty bag after remint, but sealed ctx still holds visit transport.
        session[BACKING_PLAY_SESSION_KEY] = {
            "play_session_id": "reminted",
            "launch_id": "L",
            "source_identity": f"creative:song_improv:{TRIAL}",
            "expired": False,
            "defaults": {
                "bpm": 100,
                "groove": "Pop",
                "meter": "4/4",
                "scope": "Full song",
                "loops": 2,
            },
            "overrides": {},
        }
        ctx = get_backing_context(session)
        assert ctx is not None
        self.assertEqual(int(ctx.bpm), 113)
        recovered = recover_play_session_overrides_from_backing_context(session)
        assert recovered is not None
        self.assertEqual(int((recovered.get("overrides") or {}).get("bpm") or 0), 113)
        self.assertEqual(str((recovered.get("overrides") or {}).get("groove") or ""), "Blues")
        sync_backing_play_session_on_backing_page(session)
        refreshed = refresh_backing_context_from_session(session)
        assert refreshed is not None
        self.assertEqual(int(refreshed.bpm), 113)
        self.assertEqual(str(refreshed.style), "Blues")

    def test_page_snapshot_does_not_clobber_specialized_play_session(self) -> None:
        from studio_page_persistence import apply_page_snapshot

        session = _custom_sbi_session(with_overrides=True)
        stale_snap = {
            "backing_context": {
                "source": "regular_song",
                "song_title": "Shape of You — Ed Sheeran",
                "bpm": 100,
                "style": "Pop",
                "scope": "Full song",
                "meter": "4/4",
                "loops": 2,
            },
            "backing_track_bpm": 100,
            "backing_groove_style": "Pop",
        }
        apply_page_snapshot(session, stale_snap)
        ctx = session.get("backing_context") or {}
        self.assertEqual(str(ctx.get("source") or ""), "song_improv")
        self.assertEqual(int(ctx.get("bpm") or 0), 113)
        self.assertEqual(str(ctx.get("style") or ""), "Blues")

        same_source_remint = {
            "backing_context": {
                **dict(ctx),
                "bpm": 100,
                "style": "Pop",
                "scope": "Full song",
                "meter": "4/4",
                "loops": 2,
            }
        }
        apply_page_snapshot(session, same_source_remint)
        ctx2 = session.get("backing_context") or {}
        self.assertEqual(int(ctx2.get("bpm") or 0), 113)
        self.assertEqual(str(ctx2.get("style") or ""), "Blues")

    def test_default_echo_groove_does_not_block_sealed_transport_recover(self) -> None:
        """Live reboot residue: overrides={groove: Pop} must not block 113/Blues recover."""
        from types import SimpleNamespace

        from backing_play_session import (
            BACKING_PLAY_SESSION_KEY,
            apply_current_play_session_to_backing_context,
            recover_play_session_overrides_from_backing_context,
        )

        session = _custom_sbi_session(with_overrides=True)
        session[BACKING_PLAY_SESSION_KEY] = {
            "play_session_id": "echo",
            "launch_id": "L",
            "source_identity": f"creative:song_improv:{TRIAL}",
            "expired": False,
            "defaults": {
                "bpm": 100,
                "groove": "Pop",
                "meter": "4/4",
                "scope": "Full song",
                "loops": 2,
            },
            # Source-default echo only — must not count as a real Current session.
            "overrides": {"groove": "Pop"},
        }
        recovered = recover_play_session_overrides_from_backing_context(session)
        assert recovered is not None
        ov = recovered.get("overrides") or {}
        self.assertEqual(int(ov.get("bpm") or 0), 113)
        self.assertEqual(str(ov.get("groove") or ""), "Blues")
        self.assertEqual(str(ov.get("scope") or ""), "Chorus")

        previous = SimpleNamespace(
            source="song_improv",
            bpm=113,
            style="Blues",
            groove="",
            meter="3/4",
            scope="Chorus",
            loops=3,
            sections=None,
            section="",
        )
        rebuilt = SimpleNamespace(
            source="song_improv",
            bpm=100,
            style="Pop",
            groove="Pop",
            meter="4/4",
            scope="Full song",
            loops=2,
            sections=None,
            section="",
        )
        stamped = apply_current_play_session_to_backing_context(
            session, rebuilt, previous=previous
        )
        self.assertEqual(int(stamped.bpm), 113)
        self.assertEqual(str(stamped.style), "Blues")
        self.assertEqual(str(stamped.scope), "Chorus")
        self.assertEqual(str(stamped.meter), "3/4")
        self.assertEqual(int(stamped.loops), 3)


if __name__ == "__main__":
    unittest.main()
