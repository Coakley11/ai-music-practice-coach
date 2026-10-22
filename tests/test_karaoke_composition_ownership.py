"""Composition Karaoke must not steal or surrender Now Editing.

Now Editing is the global source. Now Singing is the playback cursor.
Playing a Composition must not activate it. A Composition that is Now
Editing must not reclaim Catalog or Custom playback.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import karaoke_mode as km
from backing_source_navigation import (
    bind_karaoke_singing_composition_backing,
    karaoke_blocks_composition_reclaim,
    karaoke_singing_composition_pick,
    open_backing_for_practice_source,
)
from composition_document import apply_section_chords, new_composition_document, parse_chord_paste
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library
from composition_songs_bridge import composition_pick_key_for, find_composition_document
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
    _build_composition_chart_bundle,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


def _doc(title: str, song_id: str, key: str = "C") -> dict:
    doc = new_composition_document(title=title)
    doc["id"] = song_id
    doc["global"]["original_key_center"] = key
    doc["global"]["bpm"] = 100
    order = list((doc.get("form") or {}).get("section_order") or [])
    if order:
        apply_section_chords(doc, order[0], parse_chord_paste("C Am F G"))
    return doc


def _ss(**extra) -> dict:
    ss = {
        "instrument": "Voice",
        "karaoke_queue": [],
        COMPOSER_LIBRARY_KEY: {},
        "practice_key_by_source": {},
        "display_key": "A",
        "concert_key": "A",
    }
    ss.update(extra)
    return ss


def _catalog_editing(ss: dict, pick: str = "Pop\x1fShallow — Lady Gaga", title: str = "Shallow") -> None:
    ss[ACTIVE_CATALOG_PICK_KEY] = pick
    ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
    ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_CATALOG
    ss[SELECTED_SONG_STATE_KEY] = {
        "pick_key": pick,
        "title": title,
        "source": SOURCE_CATALOG,
        "key": "G",
    }
    ss["active_song_state"] = {"pick_key": pick, "music_source": SOURCE_CATALOG}


class TestCompositionNowSingingDoesNotActivate(unittest.TestCase):
    def test_singing_composition_does_not_mutate_catalog_now_editing(self) -> None:
        doc = _doc("My Composition", "comp-sing")
        ss = _ss()
        save_document_to_library(ss, doc)
        _catalog_editing(ss)
        pick = composition_pick_key_for(doc)
        km.add_to_queue(ss, pick, title="My Composition", practice_key="C")
        km.start_session(ss)
        before_pick = ss[ACTIVE_CATALOG_PICK_KEY]
        before_sel = dict(ss[SELECTED_SONG_STATE_KEY])
        before_display = ss["display_key"]

        ctx = open_backing_for_practice_source(ss, st_like=SimpleNamespace(session_state=ss))

        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], before_pick)
        self.assertEqual(ss[SELECTED_SONG_STATE_KEY]["pick_key"], before_sel["pick_key"])
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CATALOG)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CATALOG)
        self.assertEqual(ss["display_key"], before_display)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "composition_song")
        self.assertEqual(ctx.bound_pick_key, pick)
        self.assertEqual(karaoke_singing_composition_pick(ss), pick)
        self.assertTrue(karaoke_blocks_composition_reclaim(ss))

    def test_chart_resolves_without_global_activation(self) -> None:
        doc = _doc("My Composition", "comp-chart")
        ss = _ss()
        save_document_to_library(ss, doc)
        _catalog_editing(ss)
        pick = composition_pick_key_for(doc)
        km.add_to_queue(ss, pick, title="My Composition", practice_key="C")
        km.start_session(ss)
        found = find_composition_document(ss, pick)
        self.assertIsNotNone(found)

        def _transpose(song_data, display_key):
            return song_data.get("sections") or {}

        bundle = _build_composition_chart_bundle(
            ss,
            display_key="C",
            transpose_sections=_transpose,
            doc=found,
        )
        ctx = bind_karaoke_singing_composition_backing(ss)
        self.assertEqual(bundle["song"], "My Composition")
        self.assertEqual(bundle["original_key"], "C")
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], "Pop\x1fShallow — Lady Gaga")
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CATALOG)
        self.assertEqual(ss["display_key"], "A")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.bound_pick_key, pick)


class TestCompositionNowEditingDoesNotReclaim(unittest.TestCase):
    def _composition_editing(self, ss: dict, doc: dict) -> str:
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        ss[ACTIVE_CATALOG_PICK_KEY] = pick
        ss[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_COMPOSITION
        ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY] = SOURCE_COMPOSITION
        ss[SELECTED_SONG_STATE_KEY] = {
            "pick_key": pick,
            "title": "Composition A",
            "source": SOURCE_COMPOSITION,
            "is_composition": True,
            "key": "C",
        }
        ss["active_song_state"] = {"pick_key": pick, "music_source": SOURCE_COMPOSITION}
        return pick

    def test_catalog_singing_keeps_composition_now_editing(self) -> None:
        doc = _doc("Composition A", "comp-a")
        ss = _ss()
        editing = self._composition_editing(ss, doc)
        catalog = "Pop\x1fPerfect — Ed Sheeran"
        km.add_to_queue(ss, catalog, title="Perfect", practice_key="A")
        km.start_session(ss)

        ctx = open_backing_for_practice_source(ss, st_like=SimpleNamespace(session_state=ss))

        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], editing)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_COMPOSITION)
        self.assertEqual(ss["display_key"], "A")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.bound_pick_key, catalog)
        self.assertTrue(karaoke_blocks_composition_reclaim(ss))

    def test_custom_singing_is_not_reclaimed(self) -> None:
        doc = _doc("Composition A", "comp-a2")
        ss = _ss()
        editing = self._composition_editing(ss, doc)
        custom = {
            "id": "blues-fm",
            "name": "Blues in F minor",
            "original_key_center": "Fm",
            "original_sections": {
                "Verse": [{"chord": "Fm", "bars": 4}, {"chord": "Bbm", "bars": 4}],
            },
            "bpm": 100,
        }
        ss["cpl_saved_progressions"] = {custom["name"]: custom}
        custom_pick = "custom::blues-fm"
        km.add_to_queue(ss, custom_pick, title="Blues in F minor", practice_key="Fm")
        km.start_session(ss)

        ctx = open_backing_for_practice_source(ss, st_like=SimpleNamespace(session_state=ss))

        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], editing)
        self.assertNotEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(ss["display_key"], "A")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.bound_pick_key, custom_pick)
        self.assertEqual(ctx.concert_key, "Fm")

    def test_other_composition_singing_does_not_replace_now_editing(self) -> None:
        editing_doc = _doc("Composition A", "comp-a3")
        singing_doc = _doc("Composition B", "comp-b", key="D")
        ss = _ss()
        editing = self._composition_editing(ss, editing_doc)
        save_document_to_library(ss, singing_doc)
        singing = composition_pick_key_for(singing_doc)
        km.add_to_queue(ss, singing, title="Composition B", practice_key="D")
        km.start_session(ss)

        ctx = open_backing_for_practice_source(ss, st_like=SimpleNamespace(session_state=ss))

        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], editing)
        self.assertEqual(ss[SELECTED_SONG_STATE_KEY]["title"], "Composition A")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.bound_pick_key, singing)
        self.assertEqual(ctx.song_title, "Composition B")
        self.assertEqual(ctx.concert_key, "D")


if __name__ == "__main__":
    unittest.main()
