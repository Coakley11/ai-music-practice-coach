"""Backing's temporary settings follow the active SONG, not the page (user spec 2026-11-19).

"Changing pages is not the same as changing songs." Same active song, leave Backing and come back: the temporary
BPM and repeat count are kept; Scope returns to Full Song. A different active song (active_song_transition's
activation epoch -- also back to an earlier song, also two songs in the same key): BPM is the song's own, repeats the
default, Scope Full Song. A rerun / refresh is never a song change. Key Cycling's own settings are the KC owner's
(tests/test_kc_position_and_sidebar_live.py); these are the Backing pieces (spec tests D-I).
"""
from __future__ import annotations

import unittest
from unittest import mock

from active_song_transition import ACTIVE_SONG_ACTIVATION_EPOCH_KEY, ACTIVE_SONG_ACTIVATION_ID_KEY, note_active_song_activation
from backing_context import BACKING_CONTEXT_KEY, BACKING_SESSION_LAUNCH_ID_BLOB_KEY
from backing_play_session import (
    BACKING_PLAY_SESSION_KEY,
    BACKING_SETTINGS_ACTIVATION_EPOCH_KEY,
    backing_play_session_has_override,
    capture_backing_play_session_overrides,
    expire_backing_play_session_on_page_exit,
    follow_active_song_activation,
    sync_backing_play_session_on_backing_page,
)
from songs.bpm_state import BPM_WIDGET_KEY

SHAPE = "shape of you|ed sheeran"


def _song_session(bpm: int = 82) -> dict:
    return {
        "studio_page": "backing",
        "song": "Shape of You",
        "active_catalog_pick_key": SHAPE,
        "display_key": "Dm",
        "concert_key": "Dm",
        "backing_track_bpm": bpm,
        BPM_WIDGET_KEY: bpm,
        "backing_groove_style": "Pop groove",
        "backing_time_signature": "4/4",
        "backing_track_scope": "Full song",
        "backing_track_multi_sections": [],
        "backing_track_loops": 2,
        ACTIVE_SONG_ACTIVATION_EPOCH_KEY: 3,
        BACKING_CONTEXT_KEY: {
            "source": "regular_song", "source_label": "Catalog song", "active_song_id": SHAPE, "song_title": "Shape of You",
            "key": "Dm", "display_key": "Dm", "concert_key": "Dm", "bpm": 82, "style": "Pop", "groove": "Pop groove",
            "meter": "4/4", "bound_pick_key": SHAPE, BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "launch-catalog",
        },
        BACKING_PLAY_SESSION_KEY: {
            "play_session_id": "ps-1", "launch_id": "launch-catalog", "source_identity": f"creative:regular_song:{SHAPE}",
            "expired": False,
            "defaults": {"bpm": 82, "groove": "Pop groove", "meter": "4/4", "scope": "Full song", "multi_sections": [], "loops": 2},
            "overrides": {},
        },
    }


def _tweak(session: dict) -> None:
    """The musician's temporary choices on Backing: 96 BPM, 4 repeats, Chorus only."""
    sync_backing_play_session_on_backing_page(session)
    session["backing_track_bpm"] = 96
    session[BPM_WIDGET_KEY] = 96
    session["backing_track_loops"] = 4
    session["backing_track_scope"] = "Selected sections"
    session["backing_track_multi_sections"] = ["Chorus 1"]
    capture_backing_play_session_overrides(session)


def _round_trip(session: dict, page: str = "multitrack") -> None:
    expire_backing_play_session_on_page_exit(session, previous_page="backing", new_page=page)
    session["studio_page"] = page
    session["studio_page"] = "backing"
    sync_backing_play_session_on_backing_page(session)


class SameSongAcrossPages(unittest.TestCase):
    def test_D_bpm_and_repeats_survive_a_page_round_trip(self) -> None:
        s = _song_session()
        _tweak(s)
        _round_trip(s)
        self.assertEqual(int(s["backing_track_bpm"]), 96)
        self.assertTrue(backing_play_session_has_override(s, "bpm"))
        self.assertEqual((s[BACKING_PLAY_SESSION_KEY].get("overrides") or {}).get("loops"), 4)
        self.assertEqual(int(s["backing_track_loops"]), 4)

    def test_F_scope_is_full_song_after_leaving_backing(self) -> None:
        s = _song_session()
        _tweak(s)
        self.assertEqual(s["backing_track_scope"], "Selected sections")
        expire_backing_play_session_on_page_exit(s, previous_page="backing", new_page="practice")
        self.assertEqual(s["backing_track_scope"], "Full song")
        self.assertEqual(s["_pending_backing_scope"], "Full song")
        self.assertNotIn("backing_track_multi_sections", s)
        ov = s[BACKING_PLAY_SESSION_KEY].get("overrides") or {}
        self.assertNotIn("scope", ov)
        self.assertNotIn("multi_sections", ov)
        s["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(s)
        self.assertEqual(s.get("backing_track_scope"), "Full song")
        self.assertEqual(int(s["backing_track_bpm"]), 96)  # only Scope reset

    def test_H_reruns_and_a_refresh_are_not_a_song_change(self) -> None:
        s = _song_session()
        _tweak(s)
        for _ in range(5):
            self.assertFalse(follow_active_song_activation(s))
            sync_backing_play_session_on_backing_page(s)
        # refresh: the persisted stamps come back unchanged
        restored = dict(s)
        sync_backing_play_session_on_backing_page(restored)
        self.assertEqual(int(restored["backing_track_bpm"]), 96)
        self.assertEqual(restored[BACKING_SETTINGS_ACTIVATION_EPOCH_KEY], 3)


class DifferentSongStartsFresh(unittest.TestCase):
    def test_E_and_G_a_new_song_activation_resets_bpm_repeats_and_scope(self) -> None:
        s = _song_session()
        _tweak(s)
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 4  # another song became active (on Backing or elsewhere)
        self.assertTrue(follow_active_song_activation(s))
        self.assertTrue(s[BACKING_PLAY_SESSION_KEY].get("expired"))
        self.assertFalse((s[BACKING_PLAY_SESSION_KEY].get("overrides") or {}))
        self.assertEqual(s["_pending_backing_loops"], 2)
        self.assertEqual(s["_pending_backing_scope"], "Full song")
        self.assertEqual(s["backing_track_scope"], "Full song")
        self.assertEqual(s[BACKING_SETTINGS_ACTIVATION_EPOCH_KEY], 4)
        self.assertFalse(follow_active_song_activation(s))  # once per activation

    def test_C_back_to_the_earlier_song_is_fresh_too(self) -> None:
        """Shape -> another song -> Shape without visiting Backing in between: Shape's old 96 / 4 are not restored."""
        s = _song_session()
        _tweak(s)
        expire_backing_play_session_on_page_exit(s, previous_page="backing", new_page="picker")
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 5  # two activations happened on Songs; the identity is Shape again
        s["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(s)
        self.assertFalse(backing_play_session_has_override(s, "bpm"))
        self.assertEqual(s["_pending_backing_loops"], 2)

    def test_I_two_songs_in_the_same_key_still_change(self) -> None:
        s = {"studio_page": "picker"}
        with mock.patch("songs.music_source.resolve_active_song_identity", side_effect=["pk::song a", "pk::song b"]), \
             mock.patch("active_song_transition.classify_active_song_transition", return_value="song"):
            note_active_song_activation(s)          # first stamp
            self.assertTrue(note_active_song_activation(s))  # B, same key as A -- still a different song
        self.assertEqual(s[ACTIVE_SONG_ACTIVATION_ID_KEY], "pk::song b")
        s.update(_song_session())
        s[ACTIVE_SONG_ACTIVATION_EPOCH_KEY] = 1
        s[BACKING_SETTINGS_ACTIVATION_EPOCH_KEY] = 0
        self.assertTrue(follow_active_song_activation(s))


class WorkflowBackingUnchanged(unittest.TestCase):
    def test_a_creative_jam_still_ends_its_backing_knobs_on_leave(self) -> None:
        s = _song_session()
        s[BACKING_CONTEXT_KEY]["source"] = "entry_jam"
        _tweak(s)
        expire_backing_play_session_on_page_exit(s, previous_page="backing", new_page="creative")
        self.assertTrue(s[BACKING_PLAY_SESSION_KEY].get("expired"))


if __name__ == "__main__":
    unittest.main()
