"""R11 SBIKEY: Song-Based Improvisation lanes keep their own Practice Keys.

Human report: with Perfect (G/G) globally active, previewing Custom (C, then D)
in SBI and switching lanes left Perfect at C or D on "Active song", and the
Composition lane showed Custom's D -- while the Composition lane itself was
still the "not available" stub.

Live trace (real browser) found two first writers sharing one mistake -- the
lanes had no Practice-Key authority of their own, so the visible sidebar key
was read back as the next lane's key:

* Custom D -> Composition: ``prepare_sbi_custom_sidebar_display_key`` kept
  running on the Composition lane (sticky ``_sbi_custom_sidebar_overlay``) and
  pushed Custom's D into ``display_key``; the Composition lane rendered through
  the shared ``display_key`` widget.
* Composition -> Active song: ``reconcile_catalog_practice_key_owner`` adopted
  the lane's live key / the Composition-scoped ``_pk_user_commit_token`` as
  Perfect's Practice Key and wrote it into Perfect's own store.

Lane model now: Active song -> global owner's own store; Custom -> Custom's own
store (``display_key_sbi_custom``); Composition -> the Composition UUID store
(``display_key_sbi_composition``). A lane switch is never a global activation.
"""

from __future__ import annotations

import unittest

from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base

PERFECT_PICK_TITLE = "Perfect — Ed Sheeran"


class _LaneBase(_Base):
    def perfect_with_composition_in_library(self):
        """Perfect globally active (G/G); My Composition exists but is not active."""
        session = self.new_session()
        comp_pick, _doc = self.activate_composition(session)
        perfect = self.activate_catalog(session, *PERFECT)
        self.populate_catalog_material(session)
        self.assertEqual(self.owner(session), "catalog")
        self.custom_pick = self._load_custom(session)
        self.enter_sbi(session)
        return session, perfect, comp_pick

    def _load_custom(self, session: dict) -> str:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for

        active = {
            "id": "my-prog-1", "name": "My Progression",
            "original_key_center": "C", "user_locked_home_key": True,
            "original_sections": {"Verse": [{"chord": c, "bars": 1} for c in ("C", "F")]},
            "bpm": 100,
        }
        session[CPL_ACTIVE_KEY] = active
        session["cpl_saved_progressions"] = {"My Progression": active}
        pick = custom_pick_key_for(active)
        session["_last_custom_song_state"] = {
            "active": active, "pick_key": pick,
            "name": "My Progression", "custom_home_key": "C",
        }
        return pick

    def enter_sbi(self, session: dict) -> None:
        self.enter_creative(session)
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Song-Based Improvisation"

    def click_lane(self, session: dict, lane: str) -> None:
        """The SBI source radio's production on_change + pre-widget flush."""
        from songs.music_source import set_catalog_source, set_custom_source
        from studio_page_state import apply_improv_song_source, flush_pending_improv_song_source

        apply_improv_song_source(
            session, lane,
            set_catalog_source=set_catalog_source,
            set_custom_source=set_custom_source,
            widget_safe=True,
        )
        flush_pending_improv_song_source(session)
        session["improv_song_source"] = lane

    def custom_lane_edit(self, session: dict, key: str) -> None:
        """Custom lane edit lands on My Progression's own store (as observed live),
        and its sidebar preparer leaves the key in the shared display_key."""
        from songs.practice_key_state import mark_practice_key_user_override, set_practice_concert_key

        set_practice_concert_key(session, key, pick_key=self.custom_pick)
        mark_practice_key_user_override(session, self.custom_pick)
        session["display_key"] = key
        session["concert_key"] = key

    def store(self, session: dict, pick: str) -> str:
        from songs.practice_key_state import get_practice_concert_key

        return str(get_practice_concert_key(session, pick, default="") or "")

    def reconcile_active(self, session: dict) -> str:
        from music_workflow_song_practice import reconcile_catalog_practice_key_owner

        return reconcile_catalog_practice_key_owner(session)


class TestLaneSelection(_LaneBase):
    def test_lane_is_only_selected_on_the_sbi_surface(self) -> None:
        from sbi_lane_practice_key import foreign_sbi_lane, selected_sbi_lane

        session, _p, _c = self.perfect_with_composition_in_library()
        self.click_lane(session, "Composition")
        self.assertEqual(selected_sbi_lane(session), "Composition")
        self.assertEqual(foreign_sbi_lane(session), "Composition")
        session["improv_intelligence_tab"] = "Missions"
        self.assertEqual(selected_sbi_lane(session), "")
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Style Jam Mode"
        self.assertEqual(selected_sbi_lane(session), "")

    def test_lane_matching_the_global_owner_is_not_foreign(self) -> None:
        from sbi_lane_practice_key import foreign_sbi_lane

        session = self.new_session()
        self.activate_composition(session)
        self.enter_sbi(session)
        self.click_lane(session, "Composition")
        self.assertEqual(self.owner(session), "composition")
        self.assertEqual(foreign_sbi_lane(session), "")


class TestSbiKeyMatrix(_LaneBase):
    """SBIKEY1-10 in the human click order."""

    def test_sbikey2_5_custom_d_does_not_leak_into_composition(self) -> None:
        from sbi_lane_practice_key import (
            COMPOSITION_LANE_WIDGET, composition_lane_keys, prepare_composition_lane_sidebar,
        )

        session, perfect, comp = self.perfect_with_composition_in_library()
        self.click_lane(session, "Custom progression")
        self.custom_lane_edit(session, "D")                       # SBIKEY3
        self.click_lane(session, "Composition")                   # SBIKEY5

        self.assertEqual(composition_lane_keys(session), (comp, "C", "C"))
        _opts, original = prepare_composition_lane_sidebar(session)
        self.assertEqual(original, "C")
        self.assertEqual(session.get(COMPOSITION_LANE_WIDGET), "C",
                         "Custom's D leaked into the Composition lane")
        self.assertEqual(self.store(session, comp), "")
        self.assertEqual(self.store(session, perfect), "G")

    def test_sbikey6_composition_eb_stays_in_composition(self) -> None:
        from sbi_lane_practice_key import commit_composition_lane_practice_key, composition_lane_keys

        session, perfect, comp = self.perfect_with_composition_in_library()
        self.click_lane(session, "Custom progression")
        self.custom_lane_edit(session, "D")
        self.click_lane(session, "Composition")
        commit_composition_lane_practice_key(session, "Eb")

        self.assertEqual(composition_lane_keys(session), (comp, "C", "Eb"))
        self.assertEqual(self.store(session, self.custom_pick), "D", "Custom keeps its own D")
        self.assertEqual(self.store(session, perfect), "G")

        self.click_lane(session, "Custom progression")            # SBIKEY6: back to Custom
        self.assertEqual(self.store(session, self.custom_pick), "D")
        self.assertEqual(composition_lane_keys(session)[2], "Eb")

    def test_sbikey4_7_lane_keys_never_become_perfects(self) -> None:
        """The first bad writer: reconcile adopted the lane's key for Perfect."""
        from sbi_lane_practice_key import commit_composition_lane_practice_key
        from composition_songs_bridge import hydrate_composition_practice_key

        session, perfect, comp = self.perfect_with_composition_in_library()
        self.click_lane(session, "Custom progression")
        self.custom_lane_edit(session, "D")
        self.click_lane(session, "Composition")
        commit_composition_lane_practice_key(session, "Eb")
        # What a Composition hydrate leaves behind: lane output in display_key and
        # a Composition-scoped commit token.
        hydrate_composition_practice_key(session, "Eb")
        self.assertEqual(session.get("_pk_user_commit_pick"), comp)

        # While the Composition lane is on screen, Perfect is read, not rewritten.
        self.assertEqual(self.reconcile_active(session), "G")
        self.assertEqual(self.store(session, perfect), "G")

        self.click_lane(session, "Active song")                   # SBIKEY7
        session["display_key"] = "Eb"  # leftover lane output, not Perfect's authority
        session["concert_key"] = "Eb"
        self.assertEqual(self.reconcile_active(session), "G",
                         "a Composition-scoped commit token became Perfect's key")
        self.assertEqual(self.store(session, perfect), "G")

    def test_sbikey8_repeated_switching_keeps_each_lane(self) -> None:
        from sbi_lane_practice_key import commit_composition_lane_practice_key, composition_lane_keys

        session, perfect, comp = self.perfect_with_composition_in_library()
        self.click_lane(session, "Custom progression")
        self.custom_lane_edit(session, "D")
        self.click_lane(session, "Composition")
        commit_composition_lane_practice_key(session, "Eb")
        for _ in range(3):
            for lane in ("Custom progression", "Active song", "Composition", "Active song"):
                self.click_lane(session, lane)
                self.reconcile_active(session)
                self.assertEqual(self.store(session, perfect), "G", lane)
                self.assertEqual(self.store(session, self.custom_pick), "D", lane)
                self.assertEqual(composition_lane_keys(session)[2], "Eb", lane)

    def test_sbikey9_10_leaving_and_reentering_creative(self) -> None:
        from sbi_lane_practice_key import commit_composition_lane_practice_key

        session, perfect, _comp = self.perfect_with_composition_in_library()
        self.click_lane(session, "Custom progression")
        self.custom_lane_edit(session, "D")
        self.click_lane(session, "Composition")
        commit_composition_lane_practice_key(session, "Eb")

        self.goto(session, "practice")                            # SBIKEY9
        self.reconcile_active(session)
        self.assertEqual(self.owner(session), "catalog")
        self.assertEqual(self.store(session, perfect), "G")
        self.assertEqual(self.original_key(session), "G")

        self.assertEqual(self.enter_creative(session), "Active song")   # SBIKEY10
        self.assertEqual(self.store(session, perfect), "G")


class TestCompositionSbiIsReal(_LaneBase):
    def test_composition_lane_shows_my_composition_not_the_stub(self) -> None:
        from source_session_state import resolve_composition_sbi_preview

        session, _perfect, _comp = self.perfect_with_composition_in_library()
        self.click_lane(session, "Composition")
        preview = resolve_composition_sbi_preview(session)
        self.assertTrue(preview["available"])
        self.assertEqual(preview["title"], "My Composition")
        self.assertEqual((preview["original_key"], preview["display_key"]), ("C", "C"))
        flat = [c for chords in preview["sections"].values() for c in chords]
        self.assertEqual(set(flat), {"C", "Am", "F", "G"})
        self.assertNotIn("D/F#", flat, "Perfect's material must not stand in")

    def test_composition_lane_projects_at_its_own_key(self) -> None:
        from sbi_lane_practice_key import commit_composition_lane_practice_key
        from source_session_state import resolve_composition_sbi_preview

        session, _perfect, _comp = self.perfect_with_composition_in_library()
        self.click_lane(session, "Composition")
        commit_composition_lane_practice_key(session, "Eb")
        preview = resolve_composition_sbi_preview(session)
        self.assertEqual(preview["display_key"], "Eb")
        flat = [c for chords in preview["sections"].values() for c in chords]
        self.assertEqual(set(flat), {"Eb", "Cm", "Ab", "Bb"})


if __name__ == "__main__":
    unittest.main()
