"""Slice 4 — unit-level polluted launch journeys (A–E) without browser chrome.

Each journey seeds unrelated memories, launches one owner, mutates Practice Key,
simulates refresh via envelope dict round-trip, and asserts coherent tuple.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from backing_owner_envelope import (
    BACKING_OWNER_ENVELOPE_KEY,
    OWNER_CATALOG,
    OWNER_COMPOSITION,
    OWNER_ENTRY_JAM,
    OWNER_MISSION,
    OWNER_SBI_CUSTOM,
    get_backing_owner_envelope,
    live_backing_owner,
    stamp_backing_owner_envelope,
    update_envelope_musical_state,
)
from composition_document import apply_section_chords, new_composition_document, parse_chord_paste
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library
from composition_songs_bridge import activate_composition_by_pick_key, composition_pick_key_for
from custom_progression_lab import CPL_ACTIVE_KEY
from mission_owner_contract import stamp_mission_backing_handoff
from music_source_ownership import rebuild_catalog_backing_from_canonical_pick
from song_catalog.catalog import format_pick_key
from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, set_practice_concert_key


PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL_PICK = "custom::trial-d"


def _st(ss: dict) -> MagicMock:
    st = MagicMock()
    st.session_state = ss
    return st


def _pollute(ss: dict) -> None:
    trial = {
        "id": "trial-d",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
        "bpm": 120,
    }
    ss.setdefault(CPL_ACTIVE_KEY, trial)
    ss.setdefault(
        LAST_CUSTOM_STATE_KEY,
        {"pick_key": TRIAL_PICK, "custom_home_key": "D", "active": trial},
    )
    ss.setdefault(
        "improv_jam_session",
        {"key": "Eb", "style": "Jewish Ballad", "bpm": 72, "progression": ["Eb"]},
    )
    ss.setdefault("_backing_explicit_handoff_source", "mission")
    ss.setdefault("improv_mission_backing_handoff", True)
    ss.setdefault(COMPOSER_LIBRARY_KEY, {})


def _refresh(ss: dict) -> None:
    raw = dict(ss.get(BACKING_OWNER_ENVELOPE_KEY) or {})
    ss.clear()
    ss[BACKING_OWNER_ENVELOPE_KEY] = raw


class Slice4JourneyACatalog(unittest.TestCase):
    def test_perfect_g_c(self) -> None:
        ss = {
            "instrument": "Piano",
            "active_catalog_pick_key": PERFECT_PICK,
            "selected_song": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "C"},
        }
        _pollute(ss)
        rebuild_catalog_backing_from_canonical_pick(
            ss, st_like=_st(ss), pick_key=PERFECT_PICK, practice_concert_key="C"
        )
        self.assertEqual(live_backing_owner(ss), OWNER_CATALOG)
        update_envelope_musical_state(ss, practice_key="E", sounding_key="E")
        self.assertEqual(live_backing_owner(ss), OWNER_CATALOG)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        identity = env.identity
        _refresh(ss)
        env2 = get_backing_owner_envelope(ss)
        assert env2 is not None
        self.assertEqual(env2.source, OWNER_CATALOG)
        self.assertEqual(env2.identity, identity)
        self.assertTrue(env2.practice_key.startswith("E"))
        self.assertEqual(env2.return_destination, OWNER_CATALOG)


class Slice4JourneyBSBICustom(unittest.TestCase):
    def test_trial_d_f(self) -> None:
        ss: dict = {
            "instrument": "Piano",
            "sbi_preview_source": "Custom progression",
            "_nested_custom_sbi_backing": True,
        }
        _pollute(ss)
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_SBI_CUSTOM,
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            progression=["F", "C"],
            return_destination=OWNER_SBI_CUSTOM,
        )
        update_envelope_musical_state(ss, practice_key="F#", sounding_key="F#")
        _refresh(ss)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertEqual(env.identity, TRIAL_PICK)
        self.assertTrue(env.practice_key.startswith("F#") or env.practice_key.startswith("Gb"))
        self.assertEqual(env.return_destination, OWNER_SBI_CUSTOM)
        self.assertNotEqual(env.source, OWNER_CATALOG)


class Slice4JourneyCJam(unittest.TestCase):
    def test_jam_ignores_trial(self) -> None:
        ss: dict = {"instrument": "Piano", "improv_entry_mode": "Jam Session Generator"}
        _pollute(ss)
        stamp_backing_owner_envelope(
            ss,
            source=OWNER_ENTRY_JAM,
            identity="live-funk",
            title="Live Funk Jam",
            original_key="A",
            practice_key="A",
            sounding_key="A",
            style="Funk",
            progression=["A7", "D7"],
            return_destination=OWNER_ENTRY_JAM,
            entry_mode="Jam Session Generator",
        )
        update_envelope_musical_state(ss, practice_key="Bb", sounding_key="Bb", shape_key="C")
        _refresh(ss)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_ENTRY_JAM)
        self.assertNotEqual(env.source, OWNER_SBI_CUSTOM)
        self.assertEqual(env.return_destination, OWNER_ENTRY_JAM)


class Slice4JourneyDMission(unittest.TestCase):
    def test_slice3_gate_f_g(self) -> None:
        ss = {
            "instrument": "Bb Clarinet",
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "active_music_source": "custom_progression",
            "active_catalog_pick_key": TRIAL_PICK,
            "display_key": "F",
            "concert_key": "F",
            "original_key": "D",
            "written_charts_enabled": True,
            PRACTICE_KEY_BY_SOURCE_KEY: {TRIAL_PICK: "F"},
            CPL_ACTIVE_KEY: {
                "id": "trial-d",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
            },
        }
        _pollute(ss)
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        self.assertEqual(live_backing_owner(ss), OWNER_MISSION)
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertTrue(env.practice_key.startswith("F"))
        self.assertTrue(env.sounding_key.startswith("F"))
        update_envelope_musical_state(ss, practice_key="E", sounding_key="E", written_key="F#")
        self.assertEqual(live_backing_owner(ss), OWNER_MISSION)
        _refresh(ss)
        env2 = get_backing_owner_envelope(ss)
        assert env2 is not None
        self.assertEqual(env2.source, OWNER_MISSION)
        self.assertEqual(env2.return_destination, OWNER_MISSION)


class Slice4JourneyEComposition(unittest.TestCase):
    def test_composition_uuid_survives_pk(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source

        ss: dict = {
            "instrument": "Piano",
            "studio_page": "songs",
            "active_catalog_pick_key": PERFECT_PICK,
            PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "G"},
            COMPOSER_LIBRARY_KEY: {},
        }
        _pollute(ss)
        doc = new_composition_document(title="Slice4 Comp")
        doc["id"] = "comp-csharp"
        doc["global"]["original_key_center"] = "C#"
        order = list((doc.get("form") or {}).get("section_order") or [])
        if order:
            apply_section_chords(doc, order[0], parse_chord_paste("C# G# B F#"))
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        set_practice_concert_key(ss, "C#", pick_key=pick, allow_restore_original=True)
        ss["_force_composition_backing_open"] = True
        open_backing_for_practice_source(ss, st_like=_st(ss))
        self.assertEqual(live_backing_owner(ss), OWNER_COMPOSITION)
        update_envelope_musical_state(ss, practice_key="E", sounding_key="E")
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION)
        self.assertIn("composition::", env.identity or pick)
        self.assertTrue(env.practice_key.startswith("E"))
        _refresh(ss)
        env2 = get_backing_owner_envelope(ss)
        assert env2 is not None
        self.assertEqual(env2.source, OWNER_COMPOSITION)
        self.assertEqual(env2.identity, env.identity)
        self.assertNotEqual(env2.source, OWNER_CATALOG)

    def test_commit_backing_pk_csharp_to_e_updates_envelope(self) -> None:
        """Journey E Case: commit_backing_practice_key C#→E keeps composition UUID/envelope."""
        from backing_practice_key_control import commit_backing_practice_key
        from backing_source_navigation import open_backing_for_practice_source
        from songs.practice_key_state import get_practice_concert_key

        ss: dict = {
            "instrument": "Piano",
            "studio_page": "songs",
            "active_catalog_pick_key": PERFECT_PICK,
            PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "G"},
            COMPOSER_LIBRARY_KEY: {},
        }
        _pollute(ss)
        doc = new_composition_document(title="Slice4 Comp")
        doc["id"] = "comp-csharp-e"
        doc["global"]["original_key_center"] = "C#"
        order = list((doc.get("form") or {}).get("section_order") or [])
        if order:
            apply_section_chords(doc, order[0], parse_chord_paste("C# G# B F#"))
        save_document_to_library(ss, doc)
        pick = composition_pick_key_for(doc)
        activate_composition_by_pick_key(_st(ss), pick)
        set_practice_concert_key(ss, "C#", pick_key=pick, allow_restore_original=True)
        ss["_force_composition_backing_open"] = True
        open_backing_for_practice_source(ss, st_like=_st(ss))
        env0 = get_backing_owner_envelope(ss)
        assert env0 is not None
        self.assertEqual(env0.source, OWNER_COMPOSITION)
        self.assertTrue(str(env0.practice_key or "").startswith("C") or "C#" in str(env0.practice_key))
        commit_backing_practice_key(ss, "E")
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.source, OWNER_COMPOSITION)
        self.assertEqual(env.identity, env0.identity)
        self.assertEqual(str(env.practice_key or ""), "E")
        self.assertEqual(str(env.sounding_key or ""), "E")
        self.assertEqual(get_practice_concert_key(ss, pick), "E")
        self.assertEqual(ss.get("_pk_user_commit_token"), "E")
        self.assertNotEqual(str(env.practice_key or ""), "G")


if __name__ == "__main__":
    unittest.main()
