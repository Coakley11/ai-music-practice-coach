"""A Composition keeps the Practice Key the musician chose across song switches.

Live first wrong step: Blues Test (Original F) with Practice G chosen in the
sidebar; switching to a Catalog song kept the saved G, but coming back to Blues
Test was a "true activation" and the source-switch reset cleared the saved G to
the Original F (the durable-override protection was catalog-only).
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from composition_document import apply_section_chords, new_composition_document, parse_chord_paste
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library, set_active_document
from composition_songs_bridge import (
    activate_composition_by_pick_key,
    commit_composition_owned_practice_key,
    composition_pick_key_for,
    composition_source_original_key,
    resolve_composition_canonical_keys,
)
from songs.practice_key_state import (
    COMPOSITION_PRACTICE_KEY_CHOICE_KEY,
    PRACTICE_KEY_BY_SOURCE_KEY,
    composition_practice_key_choice,
    get_practice_concert_key,
    mark_practice_key_user_override,
    reset_practice_key_to_original_on_source_switch,
    set_practice_concert_key,
)

ROOT = Path(__file__).resolve().parents[1]
SAY = "Pop\x1fSay — John Mayer"
CUSTOM = "custom::sac-trial"


def _st(ss: dict) -> MagicMock:
    st = MagicMock()
    st.session_state = ss
    return st


def _blues_test() -> dict:
    doc = new_composition_document(title="Blues Test")
    doc["id"] = "blues-test"
    doc["global"]["original_key_center"] = "F"
    order = list((doc.get("form") or {}).get("section_order") or [])
    apply_section_chords(doc, order[0], parse_chord_paste("F7 Bb7 F7 C7#5/F"))
    return doc


def _session_with_blues_test_g() -> tuple[dict, dict, str]:
    ss: dict = {
        "instrument": "Guitar",
        "studio_page": "picker",
        COMPOSER_LIBRARY_KEY: {},
        "composer_saved_compositions": {},
        PRACTICE_KEY_BY_SOURCE_KEY: {SAY: "G", CUSTOM: "D"},
    }
    doc = _blues_test()
    save_document_to_library(ss, doc)
    pick = composition_pick_key_for(doc)
    activate_composition_by_pick_key(_st(ss), pick)
    set_active_document(ss, doc)
    commit_composition_owned_practice_key(ss, "G")  # the musician picks G
    return ss, doc, pick


def _leave_to(ss: dict, pick: str, source: str) -> None:
    ss["active_catalog_pick_key"] = pick
    ss["active_music_source"] = source
    ss["explicit_music_source_choice"] = source


class TestChoiceIsRecorded(unittest.TestCase):
    def test_sidebar_commit_records_the_choice_and_keeps_original(self) -> None:
        ss, doc, pick = _session_with_blues_test_g()
        self.assertEqual(composition_practice_key_choice(ss, pick), "G")
        self.assertEqual(get_practice_concert_key(ss, pick), "G")
        self.assertEqual(composition_source_original_key(doc), "F")


class TestSurvivesSongSwitches(unittest.TestCase):
    def test_catalog_and_back_keeps_g(self) -> None:
        ss, doc, pick = _session_with_blues_test_g()
        _leave_to(ss, SAY, "catalog")
        activate_composition_by_pick_key(_st(ss), pick)
        orig, practice = resolve_composition_canonical_keys(ss)
        self.assertEqual((orig, practice), ("F", "G"))
        self.assertEqual(get_practice_concert_key(ss, SAY), "G")  # other song untouched

    def test_custom_and_back_keeps_g_and_custom_keeps_d(self) -> None:
        ss, doc, pick = _session_with_blues_test_g()
        _leave_to(ss, CUSTOM, "custom_progression")
        activate_composition_by_pick_key(_st(ss), pick)
        self.assertEqual(resolve_composition_canonical_keys(ss), ("F", "G"))
        self.assertEqual(get_practice_concert_key(ss, CUSTOM), "D")

    def test_recorded_choice_outranks_a_leftover_written_under_the_pick(self) -> None:
        ss, doc, pick = _session_with_blues_test_g()
        ss[PRACTICE_KEY_BY_SOURCE_KEY][pick] = "D"  # e.g. a Custom workspace leftover
        self.assertEqual(reset_practice_key_to_original_on_source_switch(ss, pick_key=pick, original_key="F"), "G")

    def test_never_chosen_composition_still_starts_at_original(self) -> None:
        ss: dict = {PRACTICE_KEY_BY_SOURCE_KEY: {"composition::x": "Bb"}}
        self.assertEqual(
            reset_practice_key_to_original_on_source_switch(ss, pick_key="composition::x", original_key="F"), "F")

    def test_shape_and_capo_do_not_touch_the_choice(self) -> None:
        ss, doc, pick = _session_with_blues_test_g()
        ss.update({"guitar_capo_enabled": True, "guitar_capo_shape_key": "D", "guitar_capo_sounding_key": "G"})
        _leave_to(ss, SAY, "catalog")
        activate_composition_by_pick_key(_st(ss), pick)
        self.assertEqual(resolve_composition_canonical_keys(ss), ("F", "G"))
        self.assertEqual(composition_source_original_key(doc), "F")


class TestClearPrimitive(unittest.TestCase):
    def test_ordinary_cleanup_keeps_or_restores_the_recorded_choice(self) -> None:
        from songs.practice_key_state import clear_practice_concert_key, record_composition_practice_key_choice

        ss: dict = {PRACTICE_KEY_BY_SOURCE_KEY: {"composition::bt": "F"}}
        record_composition_practice_key_choice(ss, "composition::bt", "G")
        self.assertFalse(clear_practice_concert_key(ss, "composition::bt"))
        self.assertEqual(get_practice_concert_key(ss, "composition::bt"), "G")

    def test_force_still_discards_it_and_unrecorded_composition_clears(self) -> None:
        from songs.practice_key_state import clear_practice_concert_key, record_composition_practice_key_choice

        ss: dict = {PRACTICE_KEY_BY_SOURCE_KEY: {"composition::bt": "G", "composition::other": "A"}}
        record_composition_practice_key_choice(ss, "composition::bt", "G")
        self.assertTrue(clear_practice_concert_key(ss, "composition::bt", force=True))
        self.assertTrue(clear_practice_concert_key(ss, "composition::other"))


class TestPersisted(unittest.TestCase):
    def test_choice_is_a_persisted_session_key(self) -> None:
        src = ROOT.joinpath("music_persistent_state.py").read_text(encoding="utf-8")
        block = src[src.index("_PERSIST_KEYS: tuple[str, ...] = ("):][:12000]
        self.assertIn(f'"{COMPOSITION_PRACTICE_KEY_CHOICE_KEY}"', block[: block.index(")\n")])


if __name__ == "__main__":
    unittest.main()
