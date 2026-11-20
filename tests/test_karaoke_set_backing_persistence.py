"""Karaoke Set: Lead Sheet On / Off persists across the set; Playback Scope never overwrites ordinary Backing.

User rule 2026-11-18 (Tests B and D): a scope change while singing is that performance only, and ending the set
puts back the scope the user had in Backing; a Lead Sheet turned on during the set stays on for every following
song until the singer turns it off. The set model (start / advance / stop) is the Karaoke owner's; these are the
Backing pieces it calls (snapshot_pre_set_scope / restore_pre_set_scope) and the Lead Sheet choice it keeps.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import backing_track_state as bts

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def _in_set(active: bool = True):
    return mock.patch("karaoke_mode.is_karaoke_session_active", return_value=active)


class LeadSheetAcrossTheSet(unittest.TestCase):
    def test_outside_a_set_a_new_song_starts_with_the_sheet_closed(self) -> None:
        s = {"backing_lead_sheet_open": True, bts.KARAOKE_SET_LEAD_SHEET_OPEN_KEY: True}
        with _in_set(False):
            self.assertTrue(bts.initialize_backing_presentation(s, "song-b"))
        self.assertFalse(s["backing_lead_sheet_open"])

    def test_turned_on_during_the_set_every_following_song_opens_it(self) -> None:
        s = {"backing_lead_sheet_open": False}
        with _in_set():
            bts.initialize_backing_presentation(s, "song-a")
            self.assertFalse(s["backing_lead_sheet_open"])  # no choice yet: as before
            bts.note_karaoke_set_lead_sheet_choice(s, True)
            for song in ("song-b", "song-c"):
                s["backing_lead_sheet_open"] = False  # a new source's stale flag
                bts.initialize_backing_presentation(s, song)
                self.assertTrue(s["backing_lead_sheet_open"], song)
            # Turned off: stays off for the rest of the set.
            bts.note_karaoke_set_lead_sheet_choice(s, False)
            s["backing_lead_sheet_open"] = True
            bts.initialize_backing_presentation(s, "song-d")
            self.assertFalse(s["backing_lead_sheet_open"])

    def test_same_song_again_is_not_reinitialized(self) -> None:
        s = {}
        with _in_set():
            bts.note_karaoke_set_lead_sheet_choice(s, True)
            self.assertTrue(bts.initialize_backing_presentation(s, "song-a"))
            s["backing_lead_sheet_open"] = False
            self.assertFalse(bts.initialize_backing_presentation(s, "song-a"))
        self.assertFalse(s["backing_lead_sheet_open"])

    def test_the_choice_is_only_recorded_during_a_set(self) -> None:
        s = {}
        with _in_set(False):
            bts.note_karaoke_set_lead_sheet_choice(s, True)
            self.assertIsNone(bts.karaoke_set_lead_sheet_choice({bts.KARAOKE_SET_LEAD_SHEET_OPEN_KEY: True}))
        self.assertNotIn(bts.KARAOKE_SET_LEAD_SHEET_OPEN_KEY, s)

    def test_the_explicit_lead_sheet_controls_record_the_choice(self) -> None:
        setter = APP.split("    def _set_backing_lead_sheet_open(open_: bool) -> None:", 1)[1].split("\n    # The album-cover", 1)[0]
        self.assertIn("note_karaoke_set_lead_sheet_choice(st.session_state, bool(open_))", setter)
        card = APP.split("def _toggle_backing_lead_sheet_from_card(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("note_karaoke_set_lead_sheet_choice(st.session_state, on)", card)
        self.assertEqual(bts.KARAOKE_SET_LEAD_SHEET_OPEN_KEY, "_karaoke_set_lead_sheet_open")


class ScopeSnapshotRestore(unittest.TestCase):
    def _session(self) -> dict:
        from backing_play_session import BACKING_PLAY_SESSION_KEY

        return {
            "active_catalog_pick_key": "shallow|x",
            "backing_track_scope": "Selected sections",
            "backing_track_multi_sections": ["Verse 1", "Chorus 1"],
            "backing_track_single_section": "",
            "backing_quick_section": "Full song",
            bts.BACKING_STATE_KEY: {
                "backing_track_scope": "Selected sections",
                "backing_track_multi_sections": ["Verse 1", "Chorus 1"],
                "backing_track_single_section": "",
                "backing_quick_section": "Full song",
                "backing_track_bpm": 96,
            },
            BACKING_PLAY_SESSION_KEY: {"overrides": {"scope": "Selected sections", "multi_sections": ["Verse 1", "Chorus 1"], "bpm": 96}},
        }

    def _owner(self, sid: str = "sync-shallow"):
        return mock.patch.object(bts, "_scope_owner_id", return_value=sid)

    def test_the_retired_scope_snapshot_never_restores_a_pre_set_scope(self) -> None:
        """User rule 2026-11-20: End Set gives Full song (reset_backing_after_karaoke_set), not the pre-set scope.
        The old hooks stay importable for one release and only drop a leftover snapshot."""
        s = self._session()
        s[bts.KARAOKE_PRE_SET_SCOPE_KEY] = {"owner": "sync-shallow", "widgets": {"backing_track_scope": "Selected sections"}}
        with self._owner():
            bts.snapshot_pre_set_scope(s)
            bts.restore_pre_set_scope(s)
            bts.restore_pre_set_scope(s)
        self.assertNotIn(bts.KARAOKE_PRE_SET_SCOPE_KEY, s)
        self.assertNotIn("_pending_backing_scope", s)
        self.assertNotIn("_pending_backing_multi_sections", s)

if __name__ == "__main__":
    unittest.main()
