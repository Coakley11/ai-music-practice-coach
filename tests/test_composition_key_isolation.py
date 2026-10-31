"""A Composition's key, mode and backing context come from its own identity.

Regression: with Fixed Practice Key on, an E major Composition resolved to the *minor* member
of the key family (e.g. F minor) while a Custom song in minor was still the live owner,
because the fixed-family mode was borrowed from the active owner instead of the Composition.
"""

from __future__ import annotations

import unittest

from tests import test_owner_key_identity_contract as T
from backing_context import build_composition_song_context
from composition_melody_projection import project_melody_events, signed_semitone_delta
from composition_session_state import save_document_to_library
from composition_songs_bridge import (
    activate_composition_by_pick_key,
    composition_pick_key_for,
    resolve_composition_canonical_keys,
)
from custom_progression_lab import CPL_ACTIVE_KEY
from practice_key_mode import (
    resolve_fixed_practice_concert_key_for_owner,
    set_fixed_practice_key_family,
    set_practice_key_mode,
)
from songs.practice_key_state import mark_practice_key_user_override, set_practice_concert_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


def _custom_minor_session(*, stale_selected: bool = True, empty_pick: bool = True) -> dict:
    ss = T._custom_d_session()
    ss[CPL_ACTIVE_KEY] = {
        "id": "fm-1",
        "name": "Fm Custom",
        "original_key_center": "Fm",
        "original_sections": {"Verse": [{"chord": "Fm", "bars": 1}, {"chord": "Db", "bars": 1}]},
        "bpm": 90,
        "time_signature": "4/4",
    }
    ss["display_key"] = "Fm"
    ss["concert_key"] = "Fm"
    if stale_selected:
        ss[SELECTED_SONG_STATE_KEY] = {"title": "Fm Custom", "key": "Fm", "original_key": "Fm", "pick_key": "custom::fm-1"}
    if empty_pick:
        ss[ACTIVE_CATALOG_PICK_KEY] = ""
    return ss


def _fixed(ss: dict, family: str) -> None:
    set_practice_key_mode(ss, "fixed")
    set_fixed_practice_key_family(ss, family)


class TestFixedFamilyUsesTheCompositionsOwnMode(unittest.TestCase):
    def _doc(self, ss: dict, key: str = "E") -> dict:
        doc = T._composition_in_key(key, title="My Composition", song_id=f"comp-{key.lower()}")
        save_document_to_library(ss, doc)
        return doc

    def test_owner_resolver_uses_the_given_songs_mode(self) -> None:
        ss: dict = {}
        _fixed(ss, "Ab|F")
        self.assertEqual(resolve_fixed_practice_concert_key_for_owner(ss, "E"), "Ab")
        self.assertEqual(resolve_fixed_practice_concert_key_for_owner(ss, "Am"), "Fm")

    def test_major_composition_is_never_resolved_to_a_minor_key_during_activation(self) -> None:
        for family, expected in (("F|D", "F"), ("Ab|F", "Ab"), ("Eb|C", "Eb")):
            for stale in (True, False):
                with self.subTest(family=family, stale=stale):
                    ss = _custom_minor_session(stale_selected=stale, empty_pick=stale)
                    _fixed(ss, family)
                    doc = self._doc(ss)
                    # BEFORE the Composition owns the session (hydration / handoff window)
                    self.assertEqual(resolve_composition_canonical_keys(ss, doc), ("E", expected))
                    activate_composition_by_pick_key(T._st(ss), composition_pick_key_for(doc))
                    ctx = build_composition_song_context(ss, doc=doc)
                    self.assertEqual((ctx.key, ctx.concert_key, ctx.display_key), ("E", expected, expected))

    def test_minor_composition_gets_the_minor_member(self) -> None:
        ss = _custom_minor_session()
        _fixed(ss, "Ab|F")
        doc = self._doc(ss, key="Am")
        self.assertEqual(resolve_composition_canonical_keys(ss, doc)[1], "Fm")

    def test_explicit_fixed_e_flat_major_is_fixed_and_everything_transposes_consistently(self) -> None:
        ss = _custom_minor_session()
        _fixed(ss, "Eb|C")
        doc = self._doc(ss)
        activate_composition_by_pick_key(T._st(ss), composition_pick_key_for(doc))
        ctx = build_composition_song_context(ss, doc=doc)
        self.assertEqual(ctx.concert_key, "Eb")
        # melody moves down a semitone (E -> Eb), staying in register
        self.assertEqual(signed_semitone_delta("E", ctx.concert_key), -1)
        events, key_shift, _inst = project_melody_events(
            [{"pitch": "G#4", "duration_beats": 1.0}, {"pitch": "E5", "duration_beats": 1.0}],
            original_key="E",
            practice_key=ctx.concert_key,
            instrument="Piano",
            session_state=ss,
        )
        self.assertEqual(key_shift, -1)
        self.assertEqual([e["pitch"] for e in events], ["G4", "D#5"])

    def test_fixed_key_survives_resolution_and_is_not_rewritten_by_the_custom_owner(self) -> None:
        ss = _custom_minor_session()
        _fixed(ss, "Eb|C")
        doc = self._doc(ss)
        first = resolve_composition_canonical_keys(ss, doc)
        for _ in range(3):
            self.assertEqual(resolve_composition_canonical_keys(ss, doc), first)
        self.assertEqual(ss["fixed_practice_key_family_id"], "Eb|C")


class TestActiveObjectIsTheComposition(unittest.TestCase):
    def test_session_level_mode_ignores_a_stale_custom_owner(self) -> None:
        from backing_context import build_custom_progression_context, set_backing_context
        from session_key_context import resolve_active_object_home_key, resolve_active_object_mode

        ss = _custom_minor_session()
        set_backing_context(ss, build_custom_progression_context(ss))  # stale Custom Backing context
        _fixed(ss, "Ab|F")
        doc = T._composition_in_key("E", title="My Composition", song_id="comp-e")
        save_document_to_library(ss, doc)
        activate_composition_by_pick_key(T._st(ss), composition_pick_key_for(doc))
        # leftovers appear again after activation (late hydration of old owner state)
        ss[SELECTED_SONG_STATE_KEY] = {"title": "Fm Custom", "key": "Fm", "pick_key": "custom::fm-1"}
        ss[ACTIVE_CATALOG_PICK_KEY] = ""
        self.assertEqual(resolve_active_object_home_key(ss, original_key=""), "E")
        self.assertEqual(resolve_active_object_mode(ss, original_key="E"), "major")


class TestStandardModeStaysOnTheCompositionsOwnKey(unittest.TestCase):
    def test_custom_minor_never_leaks_into_an_e_major_composition(self) -> None:
        ss = _custom_minor_session()
        # the user even set an explicit Practice Key on the Custom song
        set_practice_concert_key(ss, "Fm", pick_key="custom::fm-1", allow_restore_original=True)
        mark_practice_key_user_override(ss, "custom::fm-1")
        doc = T._composition_in_key("E", title="My Composition", song_id="comp-e")
        save_document_to_library(ss, doc)
        activate_composition_by_pick_key(T._st(ss), composition_pick_key_for(doc))
        ctx = build_composition_song_context(ss, doc=doc)
        self.assertEqual((ctx.key, ctx.concert_key, ctx.display_key), ("E", "E", "E"))
        self.assertEqual(resolve_composition_canonical_keys(ss, doc), ("E", "E"))

    def test_composition_custom_composition_round_trip_keeps_each_owners_key(self) -> None:
        ss = _custom_minor_session(stale_selected=False, empty_pick=False)
        doc = T._composition_in_key("E", title="My Composition", song_id="comp-e")
        save_document_to_library(ss, doc)
        st = T._st(ss)
        pick = composition_pick_key_for(doc)
        for _ in range(2):
            activate_composition_by_pick_key(st, pick)
            self.assertEqual(build_composition_song_context(ss, doc=doc).concert_key, "E")
            # back on the Custom song
            ss[CPL_ACTIVE_KEY]["original_key_center"] = "Fm"
            ss["display_key"] = "Fm"
            ss["concert_key"] = "Fm"
            self.assertEqual(ss[CPL_ACTIVE_KEY]["original_key_center"], "Fm")
        activate_composition_by_pick_key(st, pick)
        self.assertEqual(resolve_composition_canonical_keys(ss, doc), ("E", "E"))


if __name__ == "__main__":
    unittest.main()
