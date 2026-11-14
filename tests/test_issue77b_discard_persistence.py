"""Issue 77B: a discarded take stays discarded, and only a discard moves the musician's position.

The defect these pin, in the order it happened:

1. a take lands and the page saves, which caches an encoded copy of every layer in
   ``_mt_tracks_persist_blob``;
2. Discard empties the slot and saves again - but that save skips the whole ``mt_tracks`` key while
   no layer holds audio, so the cached copy still holds the take;
3. the Multitrack page calls ``restore_multitrack_layers_from_workspace`` on every render, which
   reads "no layers" as "needs hydrating" and decodes the cached take straight back.

``test_the_whole_defect_end_to_end`` walks exactly that sequence through the real functions, and is
the test that would have caught this.

The skip in step 2 is deliberate protection: a session that is momentarily empty while a workspace
loads must never write an empty layer map over real recordings. So these tests also pin the
distinction that makes both behaviours possible at once - an intentional deletion is saved, an
incomplete restoration is not.
"""

from __future__ import annotations

import unittest


GUITAR = "Guitar"
SAX = "Sax / winds"
SLOTS = (GUITAR, "Bass", "Piano / Keys", "Vocals", SAX, "Extra layer")
GUITAR_AUDIO = b"RIFF-guitar" + b"\x01" * 600
SAX_AUDIO = b"RIFF-sax" + b"\x02" * 600


def session_with(*slots_with_audio: str) -> dict:
    """A session shaped like the Multitrack page's, with a cached blob as a save would leave it."""
    from multitrack_session_persistence import encode_mt_tracks_for_persist

    audio = {GUITAR: GUITAR_AUDIO, SAX: SAX_AUDIO}
    ss: dict = {
        "studio_page": "multitrack",
        "mt_tracks": {s: (audio[s] if s in slots_with_audio else None) for s in SLOTS},
        "mt_track_filenames": {s: f"{s.lower()}.wav" for s in SLOTS},
        "active_song_title": "All The Things You Are",
    }
    encoded, _ = encode_mt_tracks_for_persist(ss["mt_tracks"])
    ss["_mt_tracks_persist_blob"] = encoded
    ss["_studio_page_snapshots"] = {"multitrack": {"mt_tracks": dict(encoded)}}
    return ss


class TheCachesAreClearedForOneSlotOnly(unittest.TestCase):
    def test_the_named_slot_is_blanked_in_every_cache(self) -> None:
        from multitrack_take_removal import clear_slot_from_caches

        ss = session_with(GUITAR, SAX)
        touched = clear_slot_from_caches(ss, SAX)
        self.assertTrue(touched["persist_blob"])
        self.assertTrue(touched["page_snapshot"])
        self.assertIsNone(ss["_mt_tracks_persist_blob"][SAX])
        self.assertIsNone(ss["_studio_page_snapshots"]["multitrack"]["mt_tracks"][SAX])

    def test_the_other_layers_cached_audio_is_untouched(self) -> None:
        from multitrack_session_persistence import decode_mt_tracks_from_persist
        from multitrack_take_removal import clear_slot_from_caches

        ss = session_with(GUITAR, SAX)
        clear_slot_from_caches(ss, SAX)
        back = decode_mt_tracks_from_persist(ss["_mt_tracks_persist_blob"])
        self.assertEqual(back[GUITAR], GUITAR_AUDIO, "another layer's cached audio changed")
        snap = decode_mt_tracks_from_persist(
            ss["_studio_page_snapshots"]["multitrack"]["mt_tracks"]
        )
        self.assertEqual(snap[GUITAR], GUITAR_AUDIO)

    def test_a_session_without_caches_is_handled(self) -> None:
        from multitrack_take_removal import clear_slot_from_caches

        touched = clear_slot_from_caches({}, SAX)
        self.assertFalse(touched["persist_blob"])
        self.assertFalse(touched["page_snapshot"])


class RemoveTakeDoesTheWholeLifecycle(unittest.TestCase):
    def test_it_empties_the_slot_clears_timing_and_asks_for_one_reset(self) -> None:
        from multitrack_live_recorder import TAKE_TIMING_KEY
        from multitrack_take_removal import position_reset_token, remove_take

        ss = session_with(SAX)
        ss[TAKE_TIMING_KEY] = {SAX: {"source": "shared-clock", "sample_rate": 48000}}
        before = position_reset_token(ss)

        report = remove_take(ss, SAX, slots=SLOTS)

        self.assertTrue(report["removed"])
        self.assertIsNone(ss["mt_tracks"][SAX])
        self.assertNotIn(SAX, ss[TAKE_TIMING_KEY], "the take's timing outlived the take")
        self.assertTrue(report["timing_cleared"])
        self.assertEqual(position_reset_token(ss), before + 1)
        self.assertTrue(report["deliberately_empty"])

    def test_a_press_that_removes_nothing_moves_nothing(self) -> None:
        """No take in the slot: no reset token, no deliberate-empty marker, no rewind."""
        from multitrack_take_removal import (
            layers_deliberately_empty,
            position_reset_token,
            remove_take,
        )

        ss = session_with(GUITAR)
        before = position_reset_token(ss)
        report = remove_take(ss, SAX, slots=SLOTS)
        self.assertFalse(report["removed"])
        self.assertEqual(position_reset_token(ss), before, "an empty slot rewound the music")
        self.assertFalse(layers_deliberately_empty(ss))
        self.assertEqual(ss["mt_tracks"][GUITAR], GUITAR_AUDIO)

    def test_removing_one_of_two_layers_is_not_an_empty_project(self) -> None:
        from multitrack_take_removal import layers_deliberately_empty, remove_take

        ss = session_with(GUITAR, SAX)
        report = remove_take(ss, SAX, slots=SLOTS)
        self.assertTrue(report["removed"])
        self.assertFalse(report["deliberately_empty"])
        self.assertFalse(layers_deliberately_empty(ss))
        self.assertEqual(ss["mt_tracks"][GUITAR], GUITAR_AUDIO, "the other layer was affected")


class TheWholeDefect(unittest.TestCase):
    """The reproduction, through the real save-cache and the real restore."""

    def test_the_whole_defect_end_to_end(self) -> None:
        from multitrack_session_persistence import restore_multitrack_layers_from_workspace
        from multitrack_take_removal import remove_take

        ss = session_with(SAX)                       # a take landed, and the save cached it
        self.assertEqual(ss["mt_tracks"][SAX], SAX_AUDIO)

        remove_take(ss, SAX, slots=SLOTS)            # the musician presses Discard take
        self.assertIsNone(ss["mt_tracks"][SAX])

        restored = restore_multitrack_layers_from_workspace(ss)   # the very next render

        self.assertIsNone(
            ss["mt_tracks"][SAX],
            "the discarded take came back from a cache - this is the Issue 77B defect",
        )
        self.assertFalse(restored and bool(ss["mt_tracks"][SAX]))

    def test_without_the_fix_the_take_would_return(self) -> None:
        """Shows the restore really is the thing that resurrects it, so the test above has teeth."""
        from multitrack_session_persistence import restore_multitrack_layers_from_workspace
        from multitrack_takes import discard_take

        ss = session_with(SAX)
        discard_take(ss, SAX)                        # the old behaviour: live state only
        restore_multitrack_layers_from_workspace(ss)
        self.assertEqual(
            ss["mt_tracks"][SAX], SAX_AUDIO,
            "if this no longer resurrects the take, the end-to-end test above proves nothing",
        )

    def test_a_saved_layer_survives_discarding_an_unsaved_take(self) -> None:
        """The user's own case: save guitar, record sax, discard the sax take."""
        from multitrack_session_persistence import restore_multitrack_layers_from_workspace
        from multitrack_take_removal import remove_take
        from multitrack_takes import is_take_saved, mark_take_saved

        ss = session_with(GUITAR, SAX)
        mark_take_saved(ss, GUITAR)

        remove_take(ss, SAX, slots=SLOTS)
        restore_multitrack_layers_from_workspace(ss)

        self.assertIsNone(ss["mt_tracks"][SAX])
        self.assertEqual(ss["mt_tracks"][GUITAR], GUITAR_AUDIO, "bytes of another layer changed")
        self.assertTrue(is_take_saved(ss, GUITAR), "the saved layer lost its saved state")


class IntentionalDeletionVersusIncompleteRestore(unittest.TestCase):
    def test_an_empty_session_that_nobody_emptied_is_not_saved_as_empty(self) -> None:
        """The protection that already existed, kept: a half-restored session writes nothing."""
        from multitrack_take_removal import should_persist_empty_layer_map

        ss = {"mt_tracks": {s: None for s in SLOTS}}
        self.assertFalse(should_persist_empty_layer_map(ss, 0))

    def test_an_emptied_project_is_saved_as_empty(self) -> None:
        from multitrack_take_removal import remove_take, should_persist_empty_layer_map

        ss = session_with(SAX)
        remove_take(ss, SAX, slots=SLOTS)
        self.assertTrue(should_persist_empty_layer_map(ss, 0))

    def test_layers_present_always_save(self) -> None:
        from multitrack_take_removal import should_persist_empty_layer_map

        self.assertTrue(should_persist_empty_layer_map({}, 2))

    def test_audio_arriving_cancels_the_marker(self) -> None:
        from multitrack_take_removal import (
            clear_deliberately_empty,
            layers_deliberately_empty,
            remove_take,
        )

        ss = session_with(SAX)
        remove_take(ss, SAX, slots=SLOTS)
        self.assertTrue(layers_deliberately_empty(ss))
        clear_deliberately_empty(ss)
        self.assertFalse(
            layers_deliberately_empty(ss),
            "a new take must restore the protection against empty saves",
        )

    def test_the_real_save_records_a_deliberate_deletion_and_skips_an_accidental_one(self) -> None:
        """Through build_music_disk_state itself, which is where the skip lives."""
        import music_persistent_state as mps
        from multitrack_session_persistence import count_mt_layers, decode_mt_tracks_from_persist
        from multitrack_take_removal import remove_take

        class FakeSt:
            def __init__(self, ss):
                self.session_state = ss

        # (a) deliberate: the musician discarded the only take
        deliberate = session_with(SAX)
        remove_take(deliberate, SAX, slots=SLOTS)
        payload = mps.build_music_disk_state(FakeSt(deliberate))
        sess = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        self.assertIn("mt_tracks", sess, "an intended empty project was not saved as empty")
        self.assertEqual(count_mt_layers(decode_mt_tracks_from_persist(sess["mt_tracks"])), 0)

        # (b) accidental: an empty session nobody emptied (a restore in progress)
        accidental = {
            "studio_page": "multitrack",
            "mt_tracks": {s: None for s in SLOTS},
            "mt_track_filenames": {s: f"{s.lower()}.wav" for s in SLOTS},
            "active_song_title": "All The Things You Are",
        }
        payload2 = mps.build_music_disk_state(FakeSt(accidental))
        sess2 = payload2.get("session") if isinstance(payload2.get("session"), dict) else {}
        self.assertNotIn(
            "mt_tracks", sess2,
            "an empty layer map was written for a session that was merely not hydrated yet",
        )


class RemovingALayerIsNotRemovingAProject(unittest.TestCase):
    """Deleting one layer from the working project must not reach the saved project or its files."""

    def test_the_active_project_identity_and_rows_are_untouched(self) -> None:
        from multitrack_take_removal import remove_take

        ss = session_with(GUITAR, SAX)
        ss["multitrack_catalog_active_id"] = "mt-2026-11-14"
        ss["_last_catalog_multitrack_id"] = "mt-2026-11-14"
        ss["mt_history_save_name"] = "Thursday session"
        ss["mt_history_save_notes"] = "guitar + sax"
        rows = [{"multitrack_id": "mt-2026-11-14", "tracks": [{"slot": SAX, "has_audio": True}]}]
        ss["media_catalog"] = {"multitrack_sessions": rows}

        remove_take(ss, SAX, slots=SLOTS)

        self.assertEqual(ss["multitrack_catalog_active_id"], "mt-2026-11-14")
        self.assertEqual(ss["_last_catalog_multitrack_id"], "mt-2026-11-14")
        self.assertEqual(ss["mt_history_save_name"], "Thursday session")
        self.assertEqual(ss["mt_history_save_notes"], "guitar + sax")
        self.assertEqual(
            ss["media_catalog"]["multitrack_sessions"], rows,
            "removing a layer from the working session altered a saved project row",
        )

    def test_deleting_a_saved_layer_leaves_the_other_saved_layer_alone(self) -> None:
        from multitrack_take_removal import remove_take
        from multitrack_takes import is_take_saved, mark_take_saved

        ss = session_with(GUITAR, SAX)
        mark_take_saved(ss, GUITAR)
        mark_take_saved(ss, SAX)

        remove_take(ss, SAX, slots=SLOTS)

        self.assertIsNone(ss["mt_tracks"][SAX])
        self.assertFalse(is_take_saved(ss, SAX), "the deleted layer still claims to be saved")
        self.assertEqual(ss["mt_tracks"][GUITAR], GUITAR_AUDIO)
        self.assertTrue(is_take_saved(ss, GUITAR))

    def test_the_mix_and_backing_are_not_removed_by_a_layer_removal(self) -> None:
        """A layer going does not take the prepared backing or an existing mix with it."""
        from multitrack_take_removal import remove_take

        ss = session_with(GUITAR, SAX)
        ss["multitrack_backing_music_wav"] = b"RIFF-backing" + b"\x05" * 600
        ss["mixed_track_wav"] = b"RIFF-mix" + b"\x06" * 600

        remove_take(ss, SAX, slots=SLOTS)

        self.assertTrue(ss["multitrack_backing_music_wav"])
        self.assertTrue(ss["mixed_track_wav"])


class ThePositionMovesOnlyWhenAsked(unittest.TestCase):
    def test_a_position_belongs_to_one_song_project_and_scope(self) -> None:
        from multitrack_take_removal import position_context

        a = position_context({"active_song_title": "Blue Bossa", "mt_playback_scope": "Full song"})
        b = position_context({"active_song_title": "Autumn Leaves", "mt_playback_scope": "Full song"})
        c = position_context({
            "active_song_title": "Blue Bossa", "mt_playback_scope": "Free layering (no backing)"
        })
        d = position_context({
            "active_song_title": "Blue Bossa", "mt_playback_scope": "Full song",
            "multitrack_catalog_active_id": "mt-77",
        })
        self.assertNotEqual(a, b, "a position would leak between songs")
        self.assertNotEqual(a, c, "a position would leak across playback scopes")
        self.assertNotEqual(a, d, "a position would leak between projects")
        self.assertTrue(position_context({}))

    def test_only_a_real_removal_advances_the_token(self) -> None:
        from multitrack_take_removal import position_reset_token, remove_take, request_position_reset

        ss = session_with(GUITAR, SAX)
        start = position_reset_token(ss)
        # the sort of thing an ordinary rerun does: read state, touch mixer values
        ss["mt_vol_Guitar"] = 0.8
        ss["mt_mute_Guitar"] = True
        ss["_mt_backing_playback_status"] = "playable"
        self.assertEqual(position_reset_token(ss), start, "an ordinary change rewound the music")
        remove_take(ss, SAX, slots=SLOTS)
        self.assertEqual(position_reset_token(ss), start + 1)
        request_position_reset(ss)
        self.assertEqual(position_reset_token(ss), start + 2)


class TheBrowserSideContract(unittest.TestCase):
    """Read from the source: the transport and the strips must honour the token and the paused clock."""

    @classmethod
    def setUpClass(cls) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        cls.app = (root / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        cls.strip = (root / "multitrack_layer_chords.py").read_text(encoding="utf-8")

    def test_the_transport_remembers_its_position_against_the_token(self) -> None:
        self.assertIn('const POS_KEY = "mtpos::"', self.app)
        self.assertIn("String(saved.token) !== POS_TOKEN", self.app)
        self.assertIn("function restorePosition()", self.app)
        self.assertIn("restorePosition();", self.app)

    def test_the_transport_publishes_a_restored_position_as_not_playing(self) -> None:
        """Restoring a position must never look like playback, and must clear the stale clock."""
        self.assertIn("mtPublishClock(t, false)", self.app)
        self.assertIn("mtPublishClock(0, false)", self.app)

    def test_stop_forgets_the_remembered_position(self) -> None:
        self.assertIn("forgetPosition();", self.app)

    def test_the_position_is_passed_in_with_its_context_and_token(self) -> None:
        self.assertIn('"positionContext"', self.app)
        self.assertIn('"positionToken"', self.app)
        self.assertIn("position_context=_mt_position_context()", self.app)
        self.assertIn("position_token=_mt_position_token()", self.app)

    def test_the_chord_strip_positions_itself_on_a_paused_clock(self) -> None:
        self.assertIn("if (!c.playing && ct <= 0) idx = 0;", self.strip)
        self.assertNotIn('state.textContent = "paused";\n', self.strip)

    def test_the_discard_handler_uses_the_whole_lifecycle(self) -> None:
        self.assertIn("from multitrack_take_removal import remove_take as _mt_remove_take", self.app)

    def test_the_save_consults_the_deliberate_marker(self) -> None:
        from pathlib import Path

        mps = (Path(__file__).resolve().parents[1] / "music_persistent_state.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("should_persist_empty_layer_map", mps)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
