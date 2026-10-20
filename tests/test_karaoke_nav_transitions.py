"""Next / Previous / auto-advance change Now Singing only.

Destination source, Practice Key, BPM and lyrics come from the setlist entry.
A late outgoing render cannot install over the destination.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import karaoke_mode as km
from backing_source_navigation import bind_karaoke_performance_backing
from composition_document import apply_section_chords, new_composition_document, parse_chord_paste
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library
from composition_songs_bridge import composition_pick_key_for
from karaoke_ui import transition_karaoke_performance
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


def _doc(title: str, song_id: str, key: str, bpm: int, lyric: str = "") -> dict:
    doc = new_composition_document(title=title)
    doc["id"] = song_id
    doc["global"]["original_key_center"] = key
    doc["global"]["bpm"] = bpm
    order = list((doc.get("form") or {}).get("section_order") or [])
    if order:
        apply_section_chords(doc, order[0], parse_chord_paste("C Am F G"))
        if lyric:
            sec = ((doc.get("form") or {}).get("sections") or {}).get(order[0])
            if isinstance(sec, dict):
                sec["lyrics"] = {"raw_text": lyric, "lines": [lyric], "intent": {}}
    return doc


def _ss() -> dict:
    return {
        "instrument": "Voice",
        "karaoke_queue": [],
        COMPOSER_LIBRARY_KEY: {},
        "practice_key_by_source": {},
        "display_key": "Bb",
        "concert_key": "Bb",
        "backing_track_bpm": 82,
        "bpm": 82,
        ACTIVE_CATALOG_PICK_KEY: "Pop\x1fShallow — Lady Gaga",
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CATALOG,
        SELECTED_SONG_STATE_KEY: {
            "pick_key": "Pop\x1fShallow — Lady Gaga",
            "title": "Shallow",
            "artist": "Lady Gaga",
            "key": "G",
        },
    }


def _editing(ss: dict) -> dict:
    return {
        "pick": ss[ACTIVE_CATALOG_PICK_KEY],
        "source": ss[ACTIVE_MUSIC_SOURCE_KEY],
        "choice": ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY],
        "display": ss["display_key"],
        "selected": ss[SELECTED_SONG_STATE_KEY]["pick_key"],
    }


class _St:
    def __init__(self, session: dict) -> None:
        self.session_state = session


class TestTransitionAuthority(unittest.TestCase):
    def _queue(self) -> dict:
        ss = _ss()
        km.add_to_queue(ss, "Pop\x1fPerfect — Ed Sheeran", title="Perfect", practice_key="A", bpm=96)
        km.add_to_queue(ss, "custom::blues", title="Custom Blues", practice_key="Fm", bpm=120)
        km.add_to_queue(ss, "composition::comp-d", title="My Composition", practice_key="D", bpm=82)
        km.start_session(ss)
        return ss

    def test_next_previous_and_auto_move_now_singing_only(self) -> None:
        ss = self._queue()
        before = _editing(ss)
        st = _St(ss)

        self.assertEqual(transition_karaoke_performance(st, direction="next"), "custom::blues")
        self.assertEqual(ss["_karaoke_last_transition"], "next")
        self.assertEqual(km.current_session_practice_key(ss), "Fm")
        self.assertEqual(km.resolve_karaoke_entry_bpm(ss), 120)
        self.assertEqual(_editing(ss), before)

        self.assertEqual(transition_karaoke_performance(st, direction="auto"), "composition::comp-d")
        self.assertEqual(ss["_karaoke_last_transition"], "auto")
        self.assertEqual(km.current_session_practice_key(ss), "D")
        self.assertEqual(km.resolve_karaoke_entry_bpm(ss), 82)
        self.assertEqual(_editing(ss), before)

        self.assertEqual(transition_karaoke_performance(st, direction="previous"), "custom::blues")
        self.assertEqual(ss["_karaoke_last_transition"], "previous")
        self.assertEqual(km.current_session_practice_key(ss), "Fm")
        self.assertEqual(km.resolve_karaoke_entry_bpm(ss), 120)
        self.assertEqual(_editing(ss), before)

    def test_destination_bpm_beats_global_and_outgoing(self) -> None:
        ss = self._queue()
        ss["backing_track_bpm"] = 96
        ss[km.KARAOKE_TEMPO_RESET_PENDING_KEY] = True
        from backing_context import backing_page_transport_defaults

        bpm, _groove, _meter = backing_page_transport_defaults(ss)
        self.assertEqual(bpm, 96)
        transition_karaoke_performance(_St(ss), direction="next")
        self.assertTrue(ss.get(km.KARAOKE_TEMPO_RESET_PENDING_KEY))
        bpm, _groove, _meter = backing_page_transport_defaults(ss)
        self.assertEqual(bpm, 120)
        self.assertNotIn("backing_track_bpm", ss)

    def test_destination_lyrics_replace_outgoing(self) -> None:
        ss = _ss()
        doc = _doc("My Composition", "comp-ly", "D", 82, lyric="composition line")
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        km.add_to_queue(ss, "Pop\x1fShallow — Lady Gaga", title="Shallow", practice_key="G", bpm=96)
        km.add_to_queue(ss, pick, title="My Composition", practice_key="D", bpm=82)
        km.start_session(ss)
        outgoing, _cues = km.karaoke_display_lyrics(ss)
        self.assertNotIn("composition line", " ".join(outgoing.values()))
        transition_karaoke_performance(_St(ss), direction="next")
        section_lyrics, cues = km.karaoke_display_lyrics(ss)
        self.assertIn("composition line", " ".join(section_lyrics.values()))
        self.assertEqual(ss[SELECTED_SONG_STATE_KEY]["title"], "Shallow")
        km.add_to_queue(ss, "custom::empty", title="No Lyrics", practice_key="C", bpm=100)
        transition_karaoke_performance(_St(ss), direction="next")
        empty_sections, empty_cues = km.karaoke_display_lyrics(ss)
        self.assertEqual(empty_sections, {})
        self.assertEqual(empty_cues, {})

    def test_composition_destination_does_not_activate_or_reclaim(self) -> None:
        ss = _ss()
        editing = _doc("Editing Comp", "comp-edit", "C", 100)
        singing = _doc("Singing Comp", "comp-sing", "D", 82, lyric="sing me")
        save_document_to_library(ss, editing)
        save_document_to_library(ss, singing)
        edit_pick = composition_pick_key_for(editing)
        sing_pick = composition_pick_key_for(singing)
        ss[ACTIVE_CATALOG_PICK_KEY] = edit_pick
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
        ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_COMPOSITION
        ss[SELECTED_SONG_STATE_KEY] = {"pick_key": edit_pick, "title": "Editing Comp", "key": "C"}
        km.add_to_queue(ss, "Pop\x1fPerfect — Ed Sheeran", title="Perfect", practice_key="A", bpm=95)
        km.add_to_queue(ss, sing_pick, title="Singing Comp", practice_key="D", bpm=82)
        km.start_session(ss)
        before = _editing(ss)
        transition_karaoke_performance(_St(ss), direction="next")
        self.assertEqual(_editing(ss), before)
        ctx = bind_karaoke_performance_backing(ss)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "composition_song")
        self.assertEqual(ctx.bound_pick_key, sing_pick)
        self.assertEqual(ctx.concert_key, "D")
        self.assertEqual(ctx.bpm, 82)
        self.assertNotEqual(ss[ACTIVE_CATALOG_PICK_KEY], sing_pick)

    def test_stale_outgoing_render_cannot_install(self) -> None:
        ss = self._queue()
        started = km.now_singing_entry_id(ss)
        self.assertTrue(km.karaoke_take_install_allowed(ss, started))
        ss["_backing_wav_building_signature"] = ("outgoing",)
        ss["_last_backing_wav_path"] = "outgoing.wav"
        transition_karaoke_performance(_St(ss), direction="next")
        self.assertNotIn("_backing_wav_building_signature", ss)
        self.assertNotIn("_last_backing_wav_path", ss)
        self.assertFalse(km.karaoke_take_install_allowed(ss, started))
        self.assertTrue(km.karaoke_take_install_allowed(ss, km.now_singing_entry_id(ss)))

    def test_custom_entry_bpm_is_not_a_catalog_lookup(self) -> None:
        ss = _ss()
        ss["cpl_saved_progressions"] = {
            "Blues": {
                "id": "blues",
                "name": "Blues",
                "original_key_center": "Fm",
                "bpm": 120,
                "original_sections": {"Verse": [{"chord": "Fm", "bars": 4}]},
            }
        }
        km.add_to_queue(ss, "custom::blues", title="Blues", practice_key="Fm")
        km.start_session(ss)
        ss["backing_track_bpm"] = 82
        self.assertEqual(km.resolve_karaoke_entry_bpm(ss), 120)


if __name__ == "__main__":
    unittest.main()
