"""R11: zero-chord ownership, Composition as a real SBI source, Backing owner.

Three rules, each reproduced before being fixed:

1. An authoritative source with zero chords stays at zero chords. The Missions
   resolver reached its material through ``_catalog_sections_from_session``, an
   unguarded cascade (improv_song_concert_sections -> home_sections ->
   ctx.sections -> progression_flat). ``home_sections`` keeps the last Catalog
   song's chart, so an empty Custom progression kept serving Perfect's chords --
   and ``resolve_missions_section_map`` then relabelled that Catalog material
   "custom_song_sections".

2. Composition is a real source with real material. Human review disproved the
   earlier "Composition is always chordless" assumption:
   ``composition_sbi_source_available`` was a hardcoded False, so a Composition
   that does carry a progression read as unavailable and zero-chord.

3. The Backing session owner is the workflow that launched it.
   ``open_backing_for_practice_source`` rebuilt Composition Backing over an
   explicit Creative handoff because its reclaim keyed off
   ``composition_song_is_active`` -- the GLOBAL owner.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

#: My Composition's canonical progression, in its Original Key of C. The
#: reported ``G Em C D`` is exactly this at Practice Key G (C->G is +7), which
#: is why the projection was coherent while its Practice-Key owner was not.
COMP_IN_C = ["C", "Am", "F", "G"]
COMP_IN_G = ["G", "Em", "C", "D"]

PERFECT = ("Pop", "Perfect — Ed Sheeran")


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        from song_catalog.catalog import load_song_catalog

        self.library, self.picker, _g, _r = load_song_catalog()

    # ---------- construction ----------

    def new_session(self) -> dict:
        from songs.music_source import ensure_song_picker_catalog

        session: dict = {"studio_page": "picker"}
        ensure_song_picker_catalog(session, self.picker)
        return session

    def activate_catalog(self, session: dict, genre: str, title: str) -> str:
        from song_catalog.catalog import format_pick_key
        from songs.music_source import (
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            begin_explicit_catalog_selection,
            set_catalog_source,
        )
        from songs.state import activate_active_song_by_pick_key

        pick = format_pick_key(genre, title)
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        begin_explicit_catalog_selection(session)
        session["active_catalog_pick_key"] = pick
        set_catalog_source(session)
        activate_active_song_by_pick_key(
            _FakeSt(session), pick, self.picker,
            song_library=self.library, origin="user",
        )
        key = str((session.get("selected_song") or {}).get("key") or "C")
        session["display_key"] = key
        session["concert_key"] = key
        session.setdefault("original_key", key)
        return pick

    def populate_catalog_material(self, session: dict) -> int:
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        sync_song_improv_sections_to_practice_key(session)
        return self.chord_count(session)

    def activate_empty_custom(self, session: dict) -> str:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for
        from songs.state import activate_active_song_by_pick_key

        active = {
            "id": "my-prog-empty", "name": "My Progression",
            "original_key_center": "C", "user_locked_home_key": True,
            "original_sections": {
                "Intro": [], "Verse": [], "Chorus": [], "Bridge": [], "Outro": [],
            },
            "bpm": 100,
        }
        session[CPL_ACTIVE_KEY] = active
        session["cpl_saved_progressions"] = {"My Progression": active}
        pick = custom_pick_key_for(active)
        session["_last_custom_song_state"] = {
            "active": active, "pick_key": pick,
            "name": "My Progression", "custom_home_key": "C",
        }
        activate_active_song_by_pick_key(
            _FakeSt(session), pick, self.picker,
            song_library=self.library, origin="user",
        )
        return pick

    def give_custom_chords(self, session: dict, chords=("C", "Am", "F", "G")) -> str:
        """EMPTY8: My Progression later gets real chords."""
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for
        from songs.state import activate_active_song_by_pick_key

        active = dict(session.get(CPL_ACTIVE_KEY) or {})
        active["original_sections"] = {
            "Intro": [], "Chorus": [], "Bridge": [], "Outro": [],
            "Verse": [{"chord": c, "bars": 1} for c in chords],
        }
        session[CPL_ACTIVE_KEY] = active
        session["cpl_saved_progressions"] = {"My Progression": active}
        pick = custom_pick_key_for(active)
        session["_last_custom_song_state"] = {
            "active": active, "pick_key": pick,
            "name": "My Progression", "custom_home_key": "C",
        }
        activate_active_song_by_pick_key(
            _FakeSt(session), pick, self.picker,
            song_library=self.library, origin="user",
        )
        return pick

    def activate_composition(self, session: dict, chords: str | None = "C Am F G"):
        from composition_document import (
            apply_section_chords, apply_structure_template, bootstrap_from_vision,
            ordered_sections, parse_chord_paste,
        )
        from composition_session_state import save_document_to_library, set_active_document
        from composition_songs_bridge import (
            activate_composition_song_from_library, composition_pick_key_for,
        )

        doc = bootstrap_from_vision(
            genre="Pop", song_idea="comp sbi", title="My Composition",
            key="C major", bpm=100,
        )
        apply_structure_template(doc, "simple")
        if chords:
            apply_section_chords(
                doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste(chords)
            )
        set_active_document(session, doc, checkpoint=False)
        save_document_to_library(session, doc)
        activate_composition_song_from_library(_FakeSt(session), str(doc["id"]))
        return composition_pick_key_for(doc), doc

    # ---------- navigation ----------

    def goto(self, session: dict, page: str) -> None:
        from studio_page_persistence import handle_studio_page_transition

        session["studio_page"] = page
        handle_studio_page_transition(session)

    def enter_creative(self, session: dict) -> str:
        from source_session_state import seed_creative_song_source_before_render

        self.goto(session, "creative")
        return seed_creative_song_source_before_render(session)

    def open_tab(self, session: dict, tab: str) -> None:
        session["improv_intelligence_tab"] = tab

    # ---------- observations ----------

    def chord_count(self, session: dict) -> int:
        raw = session.get("improv_song_concert_sections")
        if not isinstance(raw, dict):
            return 0
        return sum(len(v) for v in raw.values() if isinstance(v, list))

    def _ctx(self):
        return SimpleNamespace(sections={}, section_order=None, progression_flat=[])

    def missions_map(self, session: dict):
        from mission_workflow_context import resolve_missions_section_map

        mapped, owner = resolve_missions_section_map(session, self._ctx())
        return [c for _l, chords in (mapped or []) for c in chords], owner

    def chord_map(self, session: dict):
        from creative_chord_selection_authority import _section_map_fallback_raw

        mapped = _section_map_fallback_raw(session, self._ctx())
        return [c for _l, chords in (mapped or []) for c in chords]

    def focus_map(self, session: dict):
        from creative_chord_selection_authority import deduped_section_map_for_focus

        mapped = deduped_section_map_for_focus(session, self._ctx())
        return [c for _l, chords in (mapped or []) for c in chords]

    def original_key(self, session: dict) -> str:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import display_key_context

        rec = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
        home, _ident = display_key_context(
            session, catalog_song_data=rec, cpl_active_key=CPL_ACTIVE_KEY
        )
        return str(home or "")

    def practice_key(self, session: dict) -> str:
        from sidebar_key_identity import resolve_sidebar_key_identity

        return str(resolve_sidebar_key_identity(session).selector_token or "")

    def owner(self, session: dict) -> str:
        from source_session_state import global_music_source_owner

        return global_music_source_owner(session)

    def reboot(self, session: dict) -> dict:
        from music_persistent_state import persist_music_disk_state, prepare_music_workspace

        persist_music_disk_state(_FakeSt(session))
        fresh: dict = {}
        prepare_music_workspace(
            _FakeSt(fresh),
            song_picker_catalog=self.picker, song_library=self.library,
        )
        return fresh


class TestZeroChordCustomNeverBorrowsCatalog(_Base):
    """EMPTY1-EMPTY10."""

    def _perfect_then_empty_custom(self) -> dict:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        loaded = self.populate_catalog_material(session)
        self.assertGreater(
            loaded, 0, "precondition: Perfect's progression must be loaded"
        )
        self.perfect_chords = loaded
        self.activate_empty_custom(session)
        return session

    def test_empty1_missions_shows_no_catalog_chords(self) -> None:
        session = self._perfect_then_empty_custom()
        self.enter_creative(session)
        self.open_tab(session, "Missions")

        flat, owner = self.missions_map(session)
        self.assertEqual(
            flat, [],
            f"Missions served the Catalog progression for an empty Custom "
            f"source (owner reported {owner!r})",
        )
        self.assertNotIn("catalog", owner)
        self.assertEqual(self.chord_count(session), 0)
        self.assertEqual(self.owner(session), "custom")
        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.practice_key(session), "C")

    def test_empty1_home_sections_is_the_stale_holder(self) -> None:
        """Pin the mechanism: home_sections is what the cascade reached."""
        session = self._perfect_then_empty_custom()
        session["home_sections"] = {"A": list(COMP_IN_C)}
        self.enter_creative(session)
        self.open_tab(session, "Missions")
        flat, _owner = self.missions_map(session)
        self.assertEqual(
            flat, [],
            "the Missions resolver still reaches home_sections while Custom owns "
            "the material",
        )

    def test_empty1_chord_map_fallback_cannot_reach_home_sections(self) -> None:
        """The Creative chord-map / focus cascade reads home_sections too."""
        session = self._perfect_then_empty_custom()
        session["home_sections"] = {"A": list(COMP_IN_C)}
        self.enter_creative(session)
        self.assertEqual(
            self.chord_map(session), [],
            "the chord-map fallback reached home_sections while Custom owned "
            "the material",
        )
        self.assertEqual(self.focus_map(session), [])

    def test_empty2_refresh_keeps_the_empty_custom(self) -> None:
        session = self._perfect_then_empty_custom()
        self.enter_creative(session)
        self.open_tab(session, "Missions")
        for _ in range(2):
            self.missions_map(session)
            self.original_key(session)
        self.assertEqual(self.missions_map(session)[0], [])
        self.assertEqual(self.chord_count(session), 0)

    def test_empty3_4_5_other_creative_tools_are_empty(self) -> None:
        """Live Coach, Harmony Map and Phrase / Motif."""
        session = self._perfect_then_empty_custom()
        self.enter_creative(session)
        for tab in ("Live Coach", "Harmony Map", "Phrase / Motif"):
            self.open_tab(session, tab)
            self.assertEqual(
                self.chord_map(session), [], f"{tab}: stale chord map"
            )
            self.assertEqual(
                self.focus_map(session), [], f"{tab}: stale focus map"
            )

    def test_empty6_sbi_shows_my_progression_with_zero_chords(self) -> None:
        session = self._perfect_then_empty_custom()
        lane = self.enter_creative(session)
        self.assertEqual(lane, "Custom progression")
        self.assertEqual(self.chord_count(session), 0)
        self.assertEqual(
            str((session.get("selected_song") or {}).get("title") or ""),
            "My Progression",
        )

    def test_empty7_reboot_keeps_custom_authoritative_and_empty(self) -> None:
        session = self._perfect_then_empty_custom()
        self.enter_creative(session)
        fresh = self.reboot(session)
        self.assertEqual(self.owner(fresh), "custom")
        self.assertEqual(self.chord_count(fresh), 0)
        self.assertEqual(self.missions_map(fresh)[0], [])

    def test_empty8_custom_chords_become_available_once_added(self) -> None:
        session = self._perfect_then_empty_custom()
        self.enter_creative(session)
        self.assertEqual(self.missions_map(session)[0], [])

        self.give_custom_chords(session)
        from workflow_musical_authority import refresh_custom_improv_concert_sections

        refresh_custom_improv_concert_sections(session)
        flat, owner = self.missions_map(session)
        self.assertEqual(
            set(flat), set(COMP_IN_C),
            "once My Progression has chords they must be the material",
        )
        self.assertIn("custom", owner)

    def test_empty9_switching_back_to_catalog_restores_its_chords(self) -> None:
        session = self._perfect_then_empty_custom()
        self.activate_catalog(session, *PERFECT)
        self.populate_catalog_material(session)
        flat, owner = self.missions_map(session)
        self.assertGreater(
            len(flat), 0,
            "Perfect's own chords must return once Catalog is actually active",
        )
        self.assertIn("catalog", owner)

    def test_empty10_returning_to_empty_custom_is_empty_again(self) -> None:
        session = self._perfect_then_empty_custom()
        self.activate_catalog(session, *PERFECT)
        self.populate_catalog_material(session)
        self.activate_empty_custom(session)
        self.assertEqual(self.missions_map(session)[0], [])
        self.assertEqual(self.chord_count(session), 0)


class TestCompositionPracticeKeyOwnership(_Base):
    """COMPK1-COMPK7."""

    def _catalog_g_then_composition(self):
        from songs.practice_key_state import set_practice_concert_key

        session = self.new_session()
        say = self.activate_catalog(session, "Pop", "Say — John Mayer")
        set_practice_concert_key(
            session, "G", pick_key=say, commit_catalog_practice_key=True
        )
        self.populate_catalog_material(session)
        pick, doc = self.activate_composition(session)
        return session, pick, doc

    def test_compk1_activation_initializes_practice_to_original_c(self) -> None:
        from composition_songs_bridge import resolve_composition_canonical_keys
        from songs.practice_key_state import get_practice_concert_key

        session, pick, doc = self._catalog_g_then_composition()
        home, practice = resolve_composition_canonical_keys(session, doc)
        self.assertEqual(home, "C")
        self.assertEqual(
            practice, "C",
            "no Composition override exists, so Practice initializes from "
            "Original C -- never the Catalog song's G",
        )
        self.assertEqual(get_practice_concert_key(session, pick, default=""), "C")
        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.practice_key(session), "C")

    def test_compk2_creative_keeps_the_c_context(self) -> None:
        session, _pick, _doc = self._catalog_g_then_composition()
        lane = self.enter_creative(session)
        self.assertEqual(lane, "Composition")
        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.practice_key(session), "C")

    def test_compk3_missions_projects_the_composition_in_c(self) -> None:
        session, _pick, _doc = self._catalog_g_then_composition()
        self.enter_creative(session)
        self.open_tab(session, "Missions")

        flat, owner = self.missions_map(session)
        self.assertEqual(
            set(flat), set(COMP_IN_C),
            f"Missions must show the Composition in C, got {flat}",
        )
        self.assertIn("composition", owner)
        self.assertNotIn(
            "Em", flat,
            "Em belongs to the G projection and must not appear while Practice "
            "is C",
        )

    def test_compk4_refresh_on_missions_keeps_c(self) -> None:
        session, _pick, _doc = self._catalog_g_then_composition()
        self.enter_creative(session)
        self.open_tab(session, "Missions")
        for _ in range(2):
            self.missions_map(session)
            self.practice_key(session)
        self.assertEqual(set(self.missions_map(session)[0]), set(COMP_IN_C))
        self.assertEqual(self.practice_key(session), "C")

    def test_compk5_reboot_keeps_c(self) -> None:
        session, pick, _doc = self._catalog_g_then_composition()
        self.enter_creative(session)
        fresh = self.reboot(session)
        from songs.practice_key_state import get_practice_concert_key

        self.assertEqual(self.owner(fresh), "composition")
        self.assertEqual(self.original_key(fresh), "C")
        self.assertEqual(get_practice_concert_key(fresh, pick, default=""), "C")
        self.assertEqual(set(self.missions_map(fresh)[0]), set(COMP_IN_C))

    def test_compk6_explicit_g_transposes_legitimately(self) -> None:
        """The G projection is valid -- when the musician asks for it."""
        from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
        from workflow_musical_authority import refresh_composition_improv_concert_sections

        session, pick, _doc = self._catalog_g_then_composition()
        self.enter_creative(session)
        # A genuine sidebar commit; the bare setter is refused on Missions,
        # where mission_owns_left_panel_key guards the per-pick store.
        set_practice_concert_key(
            session, "G", pick_key=pick, commit_catalog_practice_key=True
        )
        session["display_key"] = "G"
        session["concert_key"] = "G"
        refresh_composition_improv_concert_sections(session)

        self.assertEqual(get_practice_concert_key(session, pick, default=""), "G")
        self.assertEqual(
            self.original_key(session), "C",
            "the Original Key must not follow the Practice Key",
        )
        self.open_tab(session, "Missions")
        self.assertEqual(
            set(self.missions_map(session)[0]), set(COMP_IN_G),
            "an explicit Practice Key of G must transpose the Composition",
        )

        fresh = self.reboot(session)
        self.assertEqual(self.original_key(fresh), "C")
        self.assertEqual(get_practice_concert_key(fresh, pick, default=""), "G")

    def test_compk7_setting_it_back_to_c_restores_the_c_projection(self) -> None:
        from songs.practice_key_state import set_practice_concert_key
        from workflow_musical_authority import refresh_composition_improv_concert_sections

        session, pick, _doc = self._catalog_g_then_composition()
        self.enter_creative(session)
        set_practice_concert_key(
            session, "G", pick_key=pick, commit_catalog_practice_key=True
        )
        refresh_composition_improv_concert_sections(session)
        # Returning to the Original Key is a deliberate restore, which the
        # per-pick store requires to be stated explicitly (same contract the
        # Composition Practice-Key card uses).
        set_practice_concert_key(
            session, "C", pick_key=pick,
            commit_catalog_practice_key=True, allow_restore_original=True,
        )
        session["display_key"] = "C"
        session["concert_key"] = "C"
        refresh_composition_improv_concert_sections(session)

        self.assertEqual(set(self.missions_map(session)[0]), set(COMP_IN_C))
        self.assertEqual(self.original_key(session), "C")


class TestCompositionAsAnSbiSource(_Base):
    """COMP11-COMP16."""

    def test_comp11_sbi_defaults_to_composition(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.populate_catalog_material(session)
        self.activate_composition(session)
        self.assertEqual(
            self.enter_creative(session), "Composition",
            "entering SBI must select Composition automatically",
        )

    def test_comp12_sbi_shows_the_real_composition_chords(self) -> None:
        from source_session_state import composition_sbi_source_available

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.populate_catalog_material(session)
        self.activate_composition(session)
        self.enter_creative(session)

        self.assertTrue(composition_sbi_source_available(session))
        self.assertEqual(set(self.chord_map(session)), set(COMP_IN_C))
        self.assertEqual(
            self.chord_count(session), len(COMP_IN_C) * 2,
            "no Custom or Catalog substitution",
        )

    def test_comp13_temporary_custom_keeps_global_composition(self) -> None:
        from studio_page_state import (
            apply_improv_song_source, flush_pending_improv_song_source,
        )
        from songs.music_source import set_catalog_source, set_custom_source

        session = self.new_session()
        self.activate_composition(session)
        self.enter_creative(session)
        self.activate_empty_custom_blob(session)
        apply_improv_song_source(
            session, "Custom progression",
            set_catalog_source=set_catalog_source,
            set_custom_source=set_custom_source,
            widget_safe=True,
        )
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(self.owner(session), "composition")

    def activate_empty_custom_blob(self, session: dict) -> None:
        """Make a Custom available for preview without activating it globally."""
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for

        active = {
            "id": "my-prog-1", "name": "My Progression",
            "original_key_center": "C", "user_locked_home_key": True,
            "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
            "bpm": 100,
        }
        session[CPL_ACTIVE_KEY] = active
        session["cpl_saved_progressions"] = {"My Progression": active}
        pick = custom_pick_key_for(active)
        session["_last_custom_song_state"] = {
            "active": active, "pick_key": pick,
            "name": "My Progression", "custom_home_key": "C",
        }

    def test_comp14_re_entry_selects_composition_again(self) -> None:
        session = self.new_session()
        self.activate_composition(session)
        self.enter_creative(session)
        self.activate_empty_custom_blob(session)
        from studio_page_state import (
            apply_improv_song_source, flush_pending_improv_song_source,
        )
        from songs.music_source import set_catalog_source, set_custom_source

        apply_improv_song_source(
            session, "Custom progression",
            set_catalog_source=set_catalog_source,
            set_custom_source=set_custom_source,
            widget_safe=True,
        )
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.goto(session, "practice")
        self.assertEqual(self.owner(session), "composition")
        self.assertEqual(self.enter_creative(session), "Composition")

    def test_comp14b_stale_creative_snapshot_cannot_undo_re_entry(self) -> None:
        """Live O5: a Catalog-era Creative snapshot replayed "Active song" on re-entry.

        The canonical Creative session restored from disk still said "Active
        song"; hydrate_creative_session_for_page projected it onto the widget
        (queued as a pending hydrate because the sidebar had locked widgets)
        after the entry reset had already chosen Composition.
        """
        from creative_session_state import (
            CreativeSession, get_creative_session, hydrate_creative_session_for_page,
            set_creative_session,
        )

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.populate_catalog_material(session)
        set_creative_session(session, CreativeSession(
            session_id="catalog-era", tool_type="song_based_improvisation",
            entry_mode="Song-Based Improvisation", song_source="Active song",
        ))
        self.activate_composition(session)
        self.goto(session, "practice")
        self.assertEqual(self.enter_creative(session), "Composition")
        self.assertEqual(get_creative_session(session).song_source, "Composition")

        session["_streamlit_widgets_locked_this_run"] = True
        hydrate_creative_session_for_page(session)
        from session_widget_safe import apply_pending_widget_hydrates

        session.pop("_streamlit_widgets_locked_this_run", None)
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("improv_song_source"), "Composition")
        self.assertNotEqual(session.get("_pending_widget_improv_song_source"), "Active song")

    def test_comp15_missions_uses_the_composition_chords(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.populate_catalog_material(session)
        self.activate_composition(session)
        self.enter_creative(session)
        self.open_tab(session, "Missions")
        flat, owner = self.missions_map(session)
        self.assertEqual(set(flat), set(COMP_IN_C))
        self.assertIn("composition", owner)

    def test_comp16_practice_key_projection_round_trip(self) -> None:
        from songs.practice_key_state import set_practice_concert_key
        from workflow_musical_authority import refresh_composition_improv_concert_sections

        session = self.new_session()
        pick, _doc = self.activate_composition(session)
        self.enter_creative(session)
        self.assertEqual(set(self.chord_map(session)), set(COMP_IN_C))

        for key, expected in (("G", COMP_IN_G), ("C", COMP_IN_C)):
            set_practice_concert_key(
                session, key, pick_key=pick,
                commit_catalog_practice_key=True,
                # Back to the Original Key is a deliberate restore.
                allow_restore_original=(key == "C"),
            )
            session["display_key"] = key
            session["concert_key"] = key
            refresh_composition_improv_concert_sections(session)
            self.assertEqual(
                set(self.chord_map(session)), set(expected),
                f"Practice Key {key} projection",
            )
            self.assertEqual(self.original_key(session), "C")


class TestMissionChordOnComposition(_Base):
    """MCH on Composition material -- the selection must persist."""

    def _composition_missions(self):
        session = self.new_session()
        pick, _doc = self.activate_composition(session)
        self.enter_creative(session)
        self.open_tab(session, "Missions")
        session["improv_active_mission"] = "pentatonic_target"
        session["improv_mission_new_nonce"] = "nonce-1"
        mapped = []
        from mission_workflow_context import resolve_missions_section_map

        raw, _owner = resolve_missions_section_map(session, self._ctx())
        mapped = [(str(a), list(b)) for a, b in (raw or [])]
        session["_improv_mission_section_map"] = mapped
        return session, pick, mapped

    def test_mch_selection_on_composition_survives_perturbations(self) -> None:
        from creative_chord_selection_authority import (
            read_authoritative_mission_chord_selection,
            write_authoritative_chord_selection,
        )

        session, _pick, section_map = self._composition_missions()
        self.assertTrue(section_map, "the Composition chord map must be present")
        label, chords = section_map[0]
        self.assertGreaterEqual(len(chords), 3)
        target = chords[2]  # a non-first chord

        write_authoritative_chord_selection(
            session, section_map, chord_symbol=target, section_label=label
        )
        sym, _sec, _idx = read_authoritative_mission_chord_selection(
            session, section_map
        )
        self.assertEqual(sym, target)

        # Generate / New Idea / Mission type / difficulty churn.
        for key, value in (
            ("improv_mission_new_nonce", "nonce-2"),
            ("improv_mission_workspace_updated_at", "t2"),
            ("improv_active_mission", "blues_phrase"),
            ("improv_mission_level_override", "harder"),
        ):
            session[key] = value
            sym, _sec, _idx = read_authoritative_mission_chord_selection(
                session, section_map
            )
            self.assertEqual(sym, target, f"selection lost after {key} churn")

    def test_mch_selection_on_composition_survives_a_reboot(self) -> None:
        from creative_chord_selection_authority import (
            read_authoritative_mission_chord_selection,
            write_authoritative_chord_selection,
        )

        session, _pick, section_map = self._composition_missions()
        label, chords = section_map[0]
        target = chords[2]
        write_authoritative_chord_selection(
            session, section_map, chord_symbol=target, section_label=label
        )

        fresh = self.reboot(session)
        fresh["_improv_mission_section_map"] = section_map
        sym, _sec, _idx = read_authoritative_mission_chord_selection(
            fresh, section_map
        )
        self.assertEqual(
            sym, target,
            "the selected Composition chord must survive a full reboot",
        )

    def test_mch_blob_cannot_overwrite_a_composition_selection(self) -> None:
        from creative_chord_selection_authority import write_authoritative_chord_selection
        from music_workflow_legacy_projection import restore_workflow_blob_to_session
        from music_workflow_state_store import WorkflowStateBlob

        session, _pick, section_map = self._composition_missions()
        label, chords = section_map[0]
        target = chords[2]
        write_authoritative_chord_selection(
            session, section_map, chord_symbol=target, section_label=label
        )

        blob = WorkflowStateBlob(workflow_owner="mission_jam", workflow_session_id="w1")
        blob.selected_chord_symbol = chords[0]
        blob.selected_section = label
        blob.selected_chord_index = 0
        blob.mission_type = "pentatonic_target"
        restore_workflow_blob_to_session(session, blob)

        self.assertEqual(session.get("ii_selected_chord"), target)


class TestBackingSessionOwner(_Base):
    """BKH1-BKH5 -- the launching workflow owns the Backing session."""

    STYLE_SECTIONS = {"Jazz Swing · A": ["Emaj7", "C#m7", "F#m7", "B7"]}
    JAM_SECTIONS = {"Latin Fusion · A": ["Amaj7", "F#m7", "Bm7", "E7"]}

    def _composition_global(self) -> dict:
        session = self.new_session()
        self.activate_catalog(session, "Pop", "Say — John Mayer")
        self.populate_catalog_material(session)
        self.activate_composition(session)
        return session

    def _backing_source(self, session: dict) -> str:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        return str(getattr(ctx, "source", "") or "") if ctx is not None else ""

    def _backing_progression(self, session: dict) -> list[str]:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        return list(getattr(ctx, "progression", None) or []) if ctx is not None else []

    def seed_style_jam(self, session: dict) -> None:
        from music_workflow_generated_session import commit_style_jam_generation

        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Style-Based Jam"
        session["improv_style"] = "Jazz Swing"
        session["improv_style_key"] = "E"
        session["improv_style_bpm"] = 120
        session["improv_generated_sections"] = dict(self.STYLE_SECTIONS)
        commit_style_jam_generation(
            session, key_center="E", style="Jazz Swing",
            section_map=dict(self.STYLE_SECTIONS),
            mood="Bright", groove="Light", tempo_bpm=120, new_session=True,
        )

    def seed_jam_generator(self, session: dict) -> None:
        from music_workflow_generated_session import commit_jam_session_generation

        session["improv_intelligence_tab"] = "Jam Session Generator"
        session["improv_jam_style"] = "Latin Fusion"
        session["improv_jam_key"] = "A"
        session["improv_jam_bpm"] = 104
        jam = {
            "style": "Latin Fusion", "key_center": "A", "bpm": 104,
            "sections": dict(self.JAM_SECTIONS),
        }
        session["improv_jam_session"] = jam
        session["improv_generated_sections"] = dict(self.JAM_SECTIONS)
        commit_jam_session_generation(
            session, jam, key_center="A", style="Latin Fusion", new_session=True
        )

    def test_bkh1_direct_composition_backing(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source

        session = self._composition_global()
        self.goto(session, "backing")
        open_backing_for_practice_source(session, st_like=_FakeSt(session))
        self.assertEqual(self._backing_source(session), "composition_song")

    def test_bkh2_entry_style_jam_owns_backing(self) -> None:
        from backing_context import open_backing_from_creative
        from backing_source_navigation import open_backing_for_practice_source

        session = self._composition_global()
        self.goto(session, "creative")
        self.seed_style_jam(session)
        open_backing_from_creative(session, source="entry_jam", st_like=_FakeSt(session))
        self.assertEqual(self._backing_source(session), "entry_jam")

        # The Backing page's Practice-source opener runs on render.
        open_backing_for_practice_source(session, st_like=_FakeSt(session))
        self.assertEqual(
            self._backing_source(session), "entry_jam",
            "global Composition reclaimed the Backing session from the jam",
        )
        self.assertEqual(
            self._backing_progression(session)[:4],
            self.STYLE_SECTIONS["Jazz Swing · A"],
            "the jam's own progression must own the Backing session",
        )

    def test_bkh3_jam_session_generator_owns_backing(self) -> None:
        from backing_context import open_backing_from_creative
        from backing_source_navigation import open_backing_for_practice_source

        session = self._composition_global()
        self.goto(session, "creative")
        self.seed_jam_generator(session)
        open_backing_from_creative(session, source="entry_jam", st_like=_FakeSt(session))
        open_backing_for_practice_source(session, st_like=_FakeSt(session))

        self.assertEqual(self._backing_source(session), "entry_jam")
        self.assertEqual(
            self._backing_progression(session)[:4],
            self.JAM_SECTIONS["Latin Fusion · A"],
        )

    def test_bkh4_custom_sbi_handoff_owns_backing(self) -> None:
        from backing_context import open_backing_from_creative
        from backing_source_navigation import open_backing_for_practice_source

        session = self._composition_global()
        self.goto(session, "creative")
        open_backing_from_creative(session, source="song_improv", st_like=_FakeSt(session))
        open_backing_for_practice_source(session, st_like=_FakeSt(session))
        self.assertEqual(self._backing_source(session), "song_improv")

    def test_bkh5_global_composition_survives_the_temporary_backing(self) -> None:
        from backing_context import open_backing_from_creative
        from backing_source_navigation import open_backing_for_practice_source

        session = self._composition_global()
        self.goto(session, "creative")
        self.seed_style_jam(session)
        open_backing_from_creative(session, source="entry_jam", st_like=_FakeSt(session))
        open_backing_for_practice_source(session, st_like=_FakeSt(session))

        for page in ("practice", "picker"):
            self.goto(session, page)
            self.assertEqual(
                self.owner(session), "composition",
                f"the temporary Backing owner became the global source on {page}",
            )
        self.assertEqual(
            str((session.get("selected_song") or {}).get("title") or ""),
            "My Composition",
        )


class TestLiveFoundPreWidgetWriters(_Base):
    """First incorrect writers found by driving the real app in a browser.

    Each ran in the pre-widget bootstrap, before the Creative-entry reset to the
    global owner, so headless entry-level tests had not reached them.
    """

    def test_restore_active_catalog_lane_is_skipped_while_custom_owns(self) -> None:
        """Perfect's 102 chords were re-installed into an empty Custom's lanes."""
        from source_session_state import (
            SBI_PREVIEW_SOURCE_KEY,
            restore_sbi_active_catalog_identity_before_widgets,
        )

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.populate_catalog_material(session)
        self.activate_empty_custom(session)
        session["home_sections"] = {}
        session["improv_song_concert_sections"] = {}
        # Leaving the Catalog song leaves the SBI lane on its "Active song" default.
        session[SBI_PREVIEW_SOURCE_KEY] = "Active song"
        session["improv_song_source"] = "Active song"
        session["studio_page"] = "creative"

        self.assertEqual(self.owner(session), "custom")
        self.assertEqual(restore_sbi_active_catalog_identity_before_widgets(session), "")
        self.assertEqual(self.owner(session), "custom")
        self.assertEqual(session.get("home_sections"), {})
        self.assertEqual(self.chord_count(session), 0)
        self.assertEqual(self.original_key(session), "C")

    def test_preview_surface_is_only_entry_and_jam_song_based(self) -> None:
        """The Custom preview overlay must not paint other Creative tabs."""
        from source_session_state import sbi_custom_preview_surface_displayed as shown

        def s(page, tab="", mode=""):
            return {
                "studio_page": page,
                "improv_intelligence_tab": tab,
                "improv_entry_mode": mode,
            }

        self.assertTrue(shown(s("creative", "Entry & Jam", "Song-Based Improvisation")))
        self.assertTrue(shown(s("creative", "", "")))
        # Backing: only a Custom-bound Backing context is the preview surface.
        self.assertFalse(shown(s("backing")))
        self.assertTrue(shown({**s("backing"), "backing_context": {"source": "custom_progression"}}))
        self.assertFalse(shown({**s("backing"), "backing_context": {"source": "composition_song"},
                                "_sbi_custom_sidebar_overlay": True,
                                "improv_song_source": "Custom progression"}))
        for tab in ("Missions", "Live Coach", "Harmony Map", "Deep Harmony", "Phrase / Motif"):
            self.assertFalse(shown(s("creative", tab, "Song-Based Improvisation")), tab)
        self.assertFalse(shown(s("creative", "Entry & Jam", "Style Jam Mode")))
        self.assertFalse(shown(s("practice")))
        self.assertFalse(shown(s("picker")))

    def test_custom_only_click_does_not_count_composition(self) -> None:
        from source_session_state import (
            EXPLICIT_SBI_SOURCE_CLICK_KEY,
            SBI_RADIO_ON_CHANGE_THIS_RUN_KEY,
            genuine_sbi_custom_click,
            genuine_sbi_custom_only_click,
        )

        for key in ("_pending_improv_song_source", EXPLICIT_SBI_SOURCE_CLICK_KEY,
                    SBI_RADIO_ON_CHANGE_THIS_RUN_KEY):
            comp = {key: "Composition"}
            custom = {key: "Custom progression"}
            self.assertFalse(genuine_sbi_custom_only_click(comp), key)
            self.assertTrue(genuine_sbi_custom_only_click(custom), key)
        # The broader predicate keeps its existing meaning.
        self.assertTrue(genuine_sbi_custom_click({SBI_RADIO_ON_CHANGE_THIS_RUN_KEY: "Composition"}))

    def test_composition_owner_does_not_install_leftover_custom(self) -> None:
        """Entering SBI under Composition flipped the source to Custom.

        The Custom overlay then committed My Progression's key onto the
        Composition's own Practice Key, so D / Eb reverted to C on the next tab.
        """
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            SBI_PREVIEW_SOURCE_KEY,
            install_sbi_custom_identity_before_widgets,
        )

        session = self.new_session()
        self.activate_composition(session)
        self.activate_empty_custom_blob(session)
        session["studio_page"] = "creative"
        # Leftovers from an earlier Custom preview / restore.
        session[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        session[SBI_PREVIEW_SOURCE_KEY] = "Custom progression"
        session["improv_song_source"] = "Composition"

        self.assertEqual(self.owner(session), "composition")
        self.assertFalse(install_sbi_custom_identity_before_widgets(session))
        self.assertEqual(session.get("improv_song_source"), "Composition")
        self.assertEqual(self.owner(session), "composition")

    activate_empty_custom_blob = TestCompositionAsAnSbiSource.activate_empty_custom_blob


if __name__ == "__main__":
    unittest.main()
