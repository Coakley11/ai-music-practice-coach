"""Karaoke Custom/Composition activation + Practice Key snapshot invariants."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock

import karaoke_mode as km
from composition_document import apply_section_chords, new_composition_document, parse_chord_paste
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library
from composition_songs_bridge import (
    SOURCE_COMPOSITION,
    activate_composition_by_pick_key,
    commit_composition_active_song,
    composition_pick_key_for,
    find_composition_document,
)
from songs.music_source import SOURCE_CUSTOM, custom_pick_key_for
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY, activate_active_song_by_pick_key


def _st(ss: dict) -> MagicMock:
    st = MagicMock()
    st.session_state = ss
    return st


def _ss(**extra) -> dict:
    ss: dict = {
        "instrument": "Voice",
        PRACTICE_KEY_BY_SOURCE_KEY: {},
        "karaoke_queue": [],
        "cpl_saved_progressions": {},
        COMPOSER_LIBRARY_KEY: {},
    }
    ss.update(extra)
    return ss


def _set_pk(ss: dict, key: str, pick_key: str) -> None:
    """Write directly to the per-song store, bypassing sidebar guards."""
    store = ss.setdefault(PRACTICE_KEY_BY_SOURCE_KEY, {})
    store[pick_key] = key


def _saved_custom(*, name: str = "My Custom Song", song_id: str = "cust-uuid-1", key: str = "C") -> dict:
    return {
        "id": song_id,
        "name": name,
        "artist": "Your progression",
        "original_key_center": key,
        "user_locked_home_key": True,
        "original_sections": {
            "Verse": [{"chord": "C", "bars": 2}, {"chord": "Am", "bars": 2}],
            "Chorus": [{"chord": "F", "bars": 2}, {"chord": "G", "bars": 2}],
        },
        "bpm": 100,
        "time_signature": "4/4",
        "progression_style": "Pop",
        "groove_style": "Auto",
    }


def _saved_composition(*, title: str = "Comp Song", song_id: str | None = None, key: str = "C") -> dict:
    doc = new_composition_document(title=title)
    if song_id:
        doc["id"] = song_id
    doc["global"]["original_key_center"] = key
    order = list((doc.get("form") or {}).get("section_order") or [])
    if order:
        apply_section_chords(doc, order[0], parse_chord_paste("C Am F G"))
    return doc


class TestCustomKaraokeActivation(unittest.TestCase):
    def test_activate_custom_by_pick_key_commits_ownership(self) -> None:
        custom = _saved_custom()
        pick = custom_pick_key_for(custom)
        ss = _ss(cpl_saved_progressions={custom["name"]: custom})
        st = _st(ss)
        result = activate_active_song_by_pick_key(st, pick, {})
        self.assertEqual(result.get("pick_key"), pick)
        self.assertEqual(ss.get(ACTIVE_CATALOG_PICK_KEY), pick)
        self.assertEqual(ss.get("active_music_source"), SOURCE_CUSTOM)
        self.assertEqual(ss.get("cpl_active_progression", {}).get("id"), custom["id"])

    def test_karaoke_custom_entries_keep_independent_keys(self) -> None:
        custom = _saved_custom()
        pick = custom_pick_key_for(custom)
        ss = _ss(cpl_saved_progressions={custom["name"]: custom})
        st = _st(ss)
        activate_active_song_by_pick_key(st, pick, {})
        _set_pk(ss, "Bb", pick)
        e1 = km.add_to_queue(ss, pick, title=custom["name"])
        _set_pk(ss, "D", pick)
        e2 = km.add_to_queue(ss, pick, title=custom["name"])
        self.assertEqual(e1["practice_key"], "Bb")
        self.assertEqual(e2["practice_key"], "D")
        self.assertEqual(e1["source"], "custom_progression")
        self.assertNotEqual(e1["entry_id"], e2["entry_id"])
        # Global key change must not rewrite entries
        _set_pk(ss, "G", pick)
        q = km.get_queue(ss)
        self.assertEqual([e["practice_key"] for e in q], ["Bb", "D"])

    def test_karaoke_session_applies_custom_entry_keys(self) -> None:
        custom = _saved_custom()
        pick = custom_pick_key_for(custom)
        ss = _ss(cpl_saved_progressions={custom["name"]: custom})
        st = _st(ss)
        activate_active_song_by_pick_key(st, pick, {})
        for k in ("C", "Eb"):
            _set_pk(ss, k, pick)
            km.add_to_queue(ss, pick)
        km.start_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "C")
        km.apply_entry_practice_key(ss)
        self.assertEqual(get_practice_concert_key(ss, pick), "C")
        km.advance_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "Eb")
        self.assertEqual(get_practice_concert_key(ss, pick), "Eb")


class TestCompositionSourceBridge(unittest.TestCase):
    def test_composition_pick_key_uuid(self) -> None:
        doc = _saved_composition(song_id="comp-uuid-9")
        self.assertEqual(composition_pick_key_for(doc), "composition::comp-uuid-9")

    def test_commit_composition_active_song(self) -> None:
        doc = _saved_composition(song_id="comp-uuid-2", key="Am")
        ss = _ss()
        st = _st(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
        pick = composition_pick_key_for(doc)
        self.assertEqual(ss.get(ACTIVE_CATALOG_PICK_KEY), pick)
        self.assertEqual(ss.get("active_music_source"), SOURCE_COMPOSITION)
        self.assertEqual(ss.get(SELECTED_SONG_STATE_KEY, {}).get("source"), SOURCE_COMPOSITION)
        found = find_composition_document(ss, pick)
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "comp-uuid-2")

    def test_karaoke_composition_duplicates_and_keys(self) -> None:
        doc = _saved_composition(song_id="comp-uuid-3", key="C")
        ss = _ss()
        st = _st(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
        pick = composition_pick_key_for(doc)
        _set_pk(ss, "C", pick)
        e1 = km.add_to_queue(ss, pick, title="Comp Song")
        _set_pk(ss, "D", pick)
        e2 = km.add_to_queue(ss, pick, title="Comp Song")
        self.assertEqual(e1["source"], "composition_song")
        self.assertEqual(e1["practice_key"], "C")
        self.assertEqual(e2["practice_key"], "D")
        self.assertEqual(e1["pick_key"], e2["pick_key"])
        self.assertNotEqual(e1["entry_id"], e2["entry_id"])

    def test_activate_composition_by_pick_key(self) -> None:
        doc = _saved_composition(song_id="comp-uuid-4")
        ss = _ss()
        save_document_to_library(ss, doc)
        st = _st(ss)
        ok = activate_composition_by_pick_key(st, "composition::comp-uuid-4")
        self.assertTrue(ok)
        self.assertEqual(ss.get(ACTIVE_CATALOG_PICK_KEY), "composition::comp-uuid-4")


class TestMixedQueueAndSessionPersist(unittest.TestCase):
    def test_mixed_source_queue_order(self) -> None:
        catalog = "Jazz\x1fAll the Things You Are — Jerome Kern"
        custom = _saved_custom(song_id="cust-mix")
        custom_pk = custom_pick_key_for(custom)
        comp = _saved_composition(song_id="comp-mix")
        comp_pk = composition_pick_key_for(comp)
        ss = _ss(cpl_saved_progressions={custom["name"]: custom})
        save_document_to_library(ss, comp)

        _set_pk(ss, "C", catalog)
        km.add_to_queue(ss, catalog, title="All the Things You Are")
        _set_pk(ss, "D", custom_pk)
        km.add_to_queue(ss, custom_pk, title=custom["name"])
        _set_pk(ss, "E", comp_pk)
        km.add_to_queue(ss, comp_pk, title="Comp Song")
        _set_pk(ss, "F", catalog)
        km.add_to_queue(ss, catalog, title="All the Things You Are")
        _set_pk(ss, "G", comp_pk)
        km.add_to_queue(ss, comp_pk, title="Comp Song")

        q = km.get_queue(ss)
        self.assertEqual(
            [(e["source"], e["practice_key"]) for e in q],
            [
                ("catalog_song", "C"),
                ("custom_progression", "D"),
                ("composition_song", "E"),
                ("catalog_song", "F"),
                ("composition_song", "G"),
            ],
        )
        self.assertEqual(len({e["entry_id"] for e in q}), 5)

    def test_refresh_preserves_mixed_queue(self) -> None:
        catalog = "Jazz\x1fBlue Bossa — Kenny Dorham"
        custom_pk = "custom::cust-refresh"
        comp_pk = "composition::comp-refresh"
        ss = _ss()
        _set_pk(ss, "Fm", catalog)
        km.add_to_queue(ss, catalog)
        _set_pk(ss, "Bb", custom_pk)
        km.add_to_queue(ss, custom_pk)
        _set_pk(ss, "C#m", comp_pk)
        km.add_to_queue(ss, comp_pk)
        blob = copy.deepcopy(ss[km.KARAOKE_QUEUE_KEY])
        restored = _ss(karaoke_queue=blob)
        q = km.get_queue(restored)
        self.assertEqual([e["practice_key"] for e in q], ["Fm", "Bb", "C#m"])
        self.assertEqual(
            [e["source"] for e in q],
            ["catalog_song", "custom_progression", "composition_song"],
        )

    def test_session_index_restores_safely(self) -> None:
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        ss = _ss()
        for k in ("C", "D", "E"):
            _set_pk(ss, k, pick)
            km.add_to_queue(ss, pick)
        km.start_session(ss)
        km.advance_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "D")
        # Simulate cold restore of queue + session pointer (not mid-audio)
        blob_q = copy.deepcopy(ss[km.KARAOKE_QUEUE_KEY])
        restored = _ss(
            karaoke_queue=blob_q,
            karaoke_session_active=True,
            karaoke_session_index=1,
            _karaoke_active_entry_id=ss.get(km.KARAOKE_ACTIVE_ENTRY_ID_KEY),
        )
        km.reconcile_karaoke_session_after_restore(restored)
        self.assertTrue(km.is_karaoke_session_active(restored))
        self.assertEqual(km.current_session_practice_key(restored), "D")
        self.assertEqual(km.KARAOKE_SESSION_RESUME_POLICY, "restart_entry_from_start")


class TestKeyProjectionInvariants(unittest.TestCase):
    def test_sharp_flat_major_minor_snapshots(self) -> None:
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        ss = _ss()
        for k in ("F#", "Bb", "Am", "C#m", "Eb"):
            _set_pk(ss, k, pick)
            km.add_to_queue(ss, pick)
        q = km.get_queue(ss)
        self.assertEqual([e["practice_key"] for e in q], ["F#", "Bb", "Am", "C#m", "Eb"])
        # Changing global practice key must not rewrite snapshots
        _set_pk(ss, "G", pick)
        self.assertEqual([e["practice_key"] for e in km.get_queue(ss)], ["F#", "Bb", "Am", "C#m", "Eb"])

    def test_written_shape_fields_do_not_own_entry_key(self) -> None:
        pick = "Jazz\x1fBlue Bossa — Kenny Dorham"
        ss = _ss(display_key="C", written_key="Bb", shape_key="G")
        _set_pk(ss, "Fm", pick)
        entry = km.add_to_queue(ss, pick)
        self.assertEqual(entry["practice_key"], "Fm")
        # Mutate projection surfaces after add
        ss["display_key"] = "D"
        ss["written_key"] = "A"
        ss["shape_key"] = "E"
        self.assertEqual(km.get_queue(ss)[0]["practice_key"], "Fm")
        km.start_session(ss)
        km.apply_entry_practice_key(ss)
        self.assertEqual(get_practice_concert_key(ss, pick), "Fm")


if __name__ == "__main__":
    unittest.main()
