"""R11: Practice-Key convergence, Composition SBI keys, zero-chord Custom, index safety.

Matrices: COMKEY1-8, COMSBI1-8, EC1-9, IDX1-5, PC1-9.

Reproductions behind these tests:

* The explicit Practice-Key commit for a Catalog song was *dropped* while a
  temporary Custom SBI preview was open. ``set_practice_concert_key``'s
  isolation guard ("while Creative/Backing SBI is on Custom progression, never
  write the Global Active catalog sticky") exists to stop the preview's live key
  leaking into the catalog sticky -- an implicit write -- but it also swallowed
  ``commit_catalog_practice_key``, the musician deliberately setting that song's
  key. Perfect kept its old key with no feedback.

* ``sync_song_improv_sections_to_practice_key`` short-circuits on the workflow
  blob's ``section_map`` whenever ``_section_maps_same_song`` agrees, and that
  comparison is pitch-insensitive -- so a blob still at the previous Practice
  Key was served verbatim and the chord map only caught up after a refresh
  rebuilt it.

* ``improvisation_intelligence_ui._selected_chord`` ended with
  ``return chords[idx], idx if chords else 0``, which binds as
  ``chords[idx], (idx if chords else 0)``: the guard only protected the index,
  so ``chords[idx]`` raised IndexError on an empty progression. Zero-chord
  ownership made that reachable.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

PERFECT = ("Pop", "Perfect — Ed Sheeran")
PERFECT_ORIGINAL = "G"

COMP_IN_C = ["C", "Am", "F", "G"]


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
            SONG_PICKER_ACTIVE_SOURCE_KEY, SONG_PICKER_SOURCE_CATALOG,
            begin_explicit_catalog_selection, set_catalog_source,
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

    def load_custom(self, session: dict, chords=("C", "Am", "F", "G")) -> str:
        """Make My Progression available without activating it globally."""
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for

        active = {
            "id": "my-prog-1", "name": "My Progression",
            "original_key_center": "C", "user_locked_home_key": True,
            "original_sections": {
                "Intro": [], "Chorus": [], "Bridge": [], "Outro": [],
                "Verse": [{"chord": c, "bars": 1} for c in chords],
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
        return pick

    def activate_custom(self, session: dict, chords=()) -> str:
        from songs.state import activate_active_song_by_pick_key

        pick = self.load_custom(session, chords=chords)
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
            genre="Pop", song_idea="convergence", title="My Composition",
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

    # ---------- actions ----------

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

    def preview_custom(self, session: dict) -> str:
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
        return str(session.get("improv_song_source") or "")

    def set_practice(self, session: dict, pick: str, key: str, *, restore=False) -> None:
        """A deliberate Practice-Key commit through the production entry.

        A Composition goes through ``commit_composition_owned_practice_key``
        ("persist a Songs/sidebar Practice Key edit onto the loaded Composition
        UUID"), which stamps the ``_pk_user_commit_token`` that the per-pick
        store requires for a deliberate sticky -> sticky change. Reaching for
        the bare setter instead is what made a second change (D -> Eb) look
        refused.
        """
        from songs.practice_key_state import set_practice_concert_key

        if str(pick).startswith("composition::"):
            from composition_songs_bridge import (
                commit_composition_owned_practice_key,
                hydrate_composition_practice_key,
            )

            hydrate_composition_practice_key(session, key)
            commit_composition_owned_practice_key(session, key)
        else:
            set_practice_concert_key(
                session, key, pick_key=pick,
                commit_catalog_practice_key=True,
                allow_restore_original=restore,
            )
        session["display_key"] = key
        session["concert_key"] = key
        self.converge(session)

    def converge(self, session: dict) -> None:
        """Re-project the owning source's material, as a render pass does."""
        from workflow_musical_authority import (
            refresh_composition_improv_concert_sections,
            refresh_custom_improv_concert_sections,
            sync_song_improv_sections_to_practice_key,
        )

        refresh_composition_improv_concert_sections(session)
        refresh_custom_improv_concert_sections(session)
        sync_song_improv_sections_to_practice_key(session)

    # ---------- observations ----------

    def _ctx(self):
        return SimpleNamespace(sections={}, section_order=None, progression_flat=[])

    def chord_map(self, session: dict) -> list[str]:
        from creative_chord_selection_authority import _section_map_fallback_raw

        mapped = _section_map_fallback_raw(session, self._ctx())
        return [c for _l, chords in (mapped or []) for c in chords]

    def focus_map(self, session: dict) -> list[str]:
        from creative_chord_selection_authority import deduped_section_map_for_focus

        mapped = deduped_section_map_for_focus(session, self._ctx())
        return [c for _l, chords in (mapped or []) for c in chords]

    def missions_map(self, session: dict):
        from mission_workflow_context import resolve_missions_section_map

        mapped, owner = resolve_missions_section_map(session, self._ctx())
        return [c for _l, chords in (mapped or []) for c in chords], owner

    def original_key(self, session: dict) -> str:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import display_key_context

        rec = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
        home, _ident = display_key_context(
            session, catalog_song_data=rec, cpl_active_key=CPL_ACTIVE_KEY
        )
        return str(home or "")

    def saved_practice(self, session: dict, pick: str) -> str:
        from songs.practice_key_state import get_practice_concert_key

        return str(get_practice_concert_key(session, pick, default="") or "")

    def owner(self, session: dict) -> str:
        from source_session_state import global_music_source_owner

        return global_music_source_owner(session)

    def chord_count(self, session: dict) -> int:
        raw = session.get("improv_song_concert_sections")
        if not isinstance(raw, dict):
            return 0
        return sum(len(v) for v in raw.values() if isinstance(v, list))

    def root_of(self, chord: str) -> str:
        from music_theory import normalize_root, split_chord

        return normalize_root(split_chord(str(chord))[0])

    def assert_map_in_key(self, session: dict, key: str, label: str) -> None:
        flat = self.chord_map(session)
        self.assertTrue(flat, f"{label}: no chord map")
        self.assertEqual(
            self.root_of(flat[0]), self.root_of(key),
            f"{label}: chord map starts on {flat[0]!r}, expected the {key} "
            f"projection (map={flat[:6]})",
        )

    def reboot(self, session: dict) -> dict:
        from music_persistent_state import persist_music_disk_state, prepare_music_workspace

        persist_music_disk_state(_FakeSt(session))
        fresh: dict = {}
        prepare_music_workspace(
            _FakeSt(fresh),
            song_picker_catalog=self.picker, song_library=self.library,
        )
        return fresh


class TestCompositionKeyConvergence(_Base):
    """COMKEY1-COMKEY8 -- one Composition Practice Key across every surface."""

    CREATIVE_TABS = (
        "Missions", "Live Coach", "Harmony Map", "Deep Harmony", "Phrase / Motif",
    )

    def _composition(self):
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        pick, _doc = self.activate_composition(session)
        self.enter_creative(session)
        return session, pick

    def assert_everywhere(self, session: dict, key: str) -> None:
        """Every Creative surface must resolve the same Practice Key."""
        for tab in self.CREATIVE_TABS:
            self.open_tab(session, tab)
            self.assertEqual(
                self.original_key(session), "C",
                f"{tab}: Composition Original Key must stay C",
            )
            self.assert_map_in_key(session, key, tab)
            flat, owner = self.missions_map(session)
            self.assertTrue(flat, f"{tab}: Missions map empty")
            self.assertEqual(
                self.root_of(flat[0]), self.root_of(key), f"{tab}: Missions map"
            )
            self.assertIn("composition", owner, f"{tab}: owner {owner!r}")

    def test_comkey1_c_to_d(self) -> None:
        session, pick = self._composition()
        self.assert_map_in_key(session, "C", "initial")

        self.set_practice(session, pick, "D")
        self.assertEqual(self.saved_practice(session, pick), "D")
        self.assertEqual(self.original_key(session), "C")
        self.assert_map_in_key(session, "D", "after C->D")

    def test_comkey2_d_holds_across_every_creative_page(self) -> None:
        session, pick = self._composition()
        self.set_practice(session, pick, "D")
        self.assert_everywhere(session, "D")
        self.assertEqual(self.saved_practice(session, pick), "D")

    def test_comkey3_d_to_eb(self) -> None:
        session, pick = self._composition()
        self.set_practice(session, pick, "D")
        self.open_tab(session, "Live Coach")
        self.set_practice(session, pick, "Eb")
        self.assertEqual(self.saved_practice(session, pick), "Eb")
        self.assert_map_in_key(session, "Eb", "after D->Eb")

    def test_comkey4_eb_holds_across_every_creative_page(self) -> None:
        session, pick = self._composition()
        self.set_practice(session, pick, "D")
        self.set_practice(session, pick, "Eb")
        self.assert_everywhere(session, "Eb")

    def test_comkey5_refresh_keeps_eb(self) -> None:
        session, pick = self._composition()
        self.set_practice(session, pick, "Eb")
        for tab in self.CREATIVE_TABS:
            self.open_tab(session, tab)
            for _ in range(2):
                self.original_key(session)
                self.chord_map(session)
            self.assertEqual(self.saved_practice(session, pick), "Eb", tab)
            self.assert_map_in_key(session, "Eb", f"{tab} refresh")

    def test_comkey6_reboot_keeps_original_c_practice_eb(self) -> None:
        session, pick = self._composition()
        self.set_practice(session, pick, "Eb")
        fresh = self.reboot(session)
        self.assertEqual(self.owner(fresh), "composition")
        self.assertEqual(self.original_key(fresh), "C")
        self.assertEqual(self.saved_practice(fresh, pick), "Eb")
        self.converge(fresh)
        self.assert_map_in_key(fresh, "Eb", "after reboot")

    def test_comkey7_back_to_c(self) -> None:
        session, pick = self._composition()
        self.set_practice(session, pick, "Eb")
        self.set_practice(session, pick, "C", restore=True)
        self.assertEqual(self.saved_practice(session, pick), "C")
        self.assert_map_in_key(session, "C", "after Eb->C")
        self.assertEqual(self.original_key(session), "C")

    def test_comkey8_selected_position_survives_transposition(self) -> None:
        """R7/R8 semantics: position is preserved, not a literal old symbol."""
        from creative_chord_selection_authority import (
            read_authoritative_mission_chord_selection,
            write_authoritative_chord_selection,
        )

        session, pick = self._composition()
        self.open_tab(session, "Missions")
        session["improv_active_mission"] = "pentatonic_target"
        mapped, _owner = self.missions_map(session)
        section_map = [("Verse", list(COMP_IN_C))]
        session["_improv_mission_section_map"] = section_map
        del mapped

        write_authoritative_chord_selection(
            session, section_map, chord_symbol=COMP_IN_C[1], section_label="Verse"
        )
        _sym, _sec, idx_before = read_authoritative_mission_chord_selection(
            session, section_map
        )
        self.assertEqual(idx_before, 1)

        self.set_practice(session, pick, "D")
        new_map = [("Verse", [c for c in self.chord_map(session)[:4]])]
        _sym2, _sec2, idx_after = read_authoritative_mission_chord_selection(
            session, new_map
        )
        self.assertEqual(
            idx_after, 1,
            "the harmonic position must survive the key change rather than "
            "drifting to another occurrence of the old literal symbol",
        )


class TestCompositionSbiKeys(_Base):
    """COMSBI1-COMSBI8."""

    def _composition(self):
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        pick, _doc = self.activate_composition(session)
        return session, pick

    def test_comsbi1_sbi_selects_composition(self) -> None:
        session, _pick = self._composition()
        self.assertEqual(self.enter_creative(session), "Composition")

    def test_comsbi2_four_real_composition_chords(self) -> None:
        session, _pick = self._composition()
        self.enter_creative(session)
        flat = self.chord_map(session)
        self.assertEqual(set(flat), set(COMP_IN_C))
        self.assertEqual(len(set(flat)), 4)

    def test_comsbi3_and_4_card_follows_c_then_d_then_eb(self) -> None:
        session, pick = self._composition()
        self.enter_creative(session)
        for key in ("C", "D", "Eb"):
            self.set_practice(session, pick, key, restore=(key == "C"))
            self.assert_map_in_key(session, key, f"SBI card at {key}")
            self.assertEqual(self.original_key(session), "C")

    def test_comsbi5_and_6_custom_preview_then_back_to_composition(self) -> None:
        from source_session_state import creative_source_options_for_global_owner

        session, _pick = self._composition()
        self.enter_creative(session)
        self.load_custom(session)
        self.assertEqual(self.preview_custom(session), "Custom progression")
        self.assertEqual(self.owner(session), "composition")

        options = creative_source_options_for_global_owner(session)
        self.assertIn(
            "Composition", options,
            "Composition must remain selectable so the musician can come back",
        )
        # Clicking Composition again.
        from studio_page_state import (
            apply_improv_song_source, flush_pending_improv_song_source,
        )
        from songs.music_source import set_catalog_source, set_custom_source

        apply_improv_song_source(
            session, "Composition",
            set_catalog_source=set_catalog_source,
            set_custom_source=set_custom_source,
            widget_safe=True,
        )
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Composition")

    def test_comsbi7_re_entry_defaults_from_global_composition(self) -> None:
        session, _pick = self._composition()
        self.enter_creative(session)
        self.load_custom(session)
        self.preview_custom(session)
        self.goto(session, "practice")
        self.assertEqual(self.owner(session), "composition")
        self.assertEqual(self.enter_creative(session), "Composition")

    def test_comsbi8_written_key_projection_is_not_a_second_owner(self) -> None:
        """R9: the written projection must not own the Practice Key."""
        session, pick = self._composition()
        self.enter_creative(session)
        self.set_practice(session, pick, "D")
        before = self.saved_practice(session, pick)

        session["instrument"] = "Trumpet"
        session["chart_key_mode"] = "written"
        self.converge(session)

        self.assertEqual(
            self.saved_practice(session, pick), before,
            "turning on written charts must not rewrite the Composition's "
            "source-owned Practice Key",
        )
        self.assertEqual(self.original_key(session), "C")


class TestEmptyCustomNeverInheritsPerfect(_Base):
    """EC1-EC9."""

    TABS = ("Missions", "Live Coach", "Harmony Map", "Deep Harmony", "Phrase / Motif")

    def _perfect_then_empty_custom(self) -> dict:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.assertGreater(self.chord_count(session), 0, "Perfect must be loaded")
        self.activate_custom(session, chords=())
        return session

    def test_ec1_to_ec5_every_creative_tool_is_empty(self) -> None:
        session = self._perfect_then_empty_custom()
        self.enter_creative(session)
        for tab in self.TABS:
            self.open_tab(session, tab)
            flat, owner = self.missions_map(session)
            self.assertEqual(flat, [], f"{tab}: Missions map held {flat[:6]}")
            self.assertNotIn("catalog", owner, f"{tab}: owner {owner!r}")
            self.assertEqual(self.chord_map(session), [], f"{tab}: chord map")
            self.assertEqual(self.focus_map(session), [], f"{tab}: focus map")
        self.assertEqual(self.chord_count(session), 0)
        self.assertEqual(self.original_key(session), "C")

    def test_ec5_sbi_names_my_progression_with_zero_chords(self) -> None:
        session = self._perfect_then_empty_custom()
        self.assertEqual(self.enter_creative(session), "Custom progression")
        self.assertEqual(
            str((session.get("selected_song") or {}).get("title") or ""),
            "My Progression",
        )
        self.assertEqual(self.chord_count(session), 0)

    def test_ec6_refresh_stays_empty(self) -> None:
        session = self._perfect_then_empty_custom()
        self.enter_creative(session)
        self.open_tab(session, "Missions")
        for _ in range(3):
            self.converge(session)
            self.missions_map(session)
        self.assertEqual(self.missions_map(session)[0], [])
        self.assertEqual(self.chord_count(session), 0)

    def test_ec7_reboot_stays_empty(self) -> None:
        session = self._perfect_then_empty_custom()
        self.enter_creative(session)
        fresh = self.reboot(session)
        self.assertEqual(self.owner(fresh), "custom")
        self.converge(fresh)
        self.assertEqual(self.chord_count(fresh), 0)
        self.assertEqual(self.missions_map(fresh)[0], [])

    def test_ec8_switching_back_to_perfect_restores_its_chords(self) -> None:
        session = self._perfect_then_empty_custom()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        flat, owner = self.missions_map(session)
        self.assertGreater(len(flat), 0)
        self.assertIn("catalog", owner)
        self.assertEqual(self.original_key(session), PERFECT_ORIGINAL)

    def test_ec9_returning_to_empty_custom_is_empty_again(self) -> None:
        session = self._perfect_then_empty_custom()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.activate_custom(session, chords=())
        self.assertEqual(self.missions_map(session)[0], [])
        self.assertEqual(self.chord_count(session), 0)

    def test_no_stale_selected_chord_survives(self) -> None:
        from creative_chord_selection_authority import write_authoritative_chord_selection

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        flat = self.chord_map(session)
        write_authoritative_chord_selection(
            session, [("A", flat[:8])], chord_symbol=flat[2], section_label="A"
        )
        self.assertTrue(session.get("ii_selected_chord"))

        self.activate_custom(session, chords=())
        self.converge(session)
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "")


class TestSelectedChordIndexSafety(_Base):
    """IDX1-IDX5 -- the IndexError and cross-owner index contamination."""

    def _selected(self, session: dict, chords: list[str], section_map=None):
        from improvisation_intelligence_ui import _selected_chord

        return _selected_chord(session, chords, section_map)

    def test_idx1_empty_progression_does_not_raise(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        session["ii_selected_chord_index"] = 20
        session["ii_selected_chord"] = "Cadd9"

        self.activate_custom(session, chords=())
        self.converge(session)
        sym, idx = self._selected(session, [])
        self.assertEqual((sym, idx), ("", 0))

    def test_idx1_empty_progression_raised_before(self) -> None:
        """The precedence bug indexed an empty list unconditionally."""
        session = self.new_session()
        session["ii_selected_chord"] = "G"
        session["ii_selected_chord_index"] = 0
        sym, idx = self._selected(session, [])
        self.assertEqual((sym, idx), ("", 0))

    def test_idx2_long_to_four_chords_is_in_range(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        session["ii_selected_chord_index"] = 40
        session["ii_selected_chord"] = "Cadd9"

        self.activate_composition(session)
        self.converge(session)
        chords = list(COMP_IN_C)
        sym, idx = self._selected(session, chords)
        self.assertTrue(0 <= idx < len(chords), f"index {idx} out of range")
        self.assertIn(sym, chords)

    def test_idx3_zero_chord_custom_missions_is_clean(self) -> None:
        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        self.activate_custom(session, chords=())
        self.enter_creative(session)
        self.open_tab(session, "Missions")
        flat, _owner = self.missions_map(session)
        self.assertEqual(flat, [])
        sym, idx = self._selected(session, flat)
        self.assertEqual((sym, idx), ("", 0))

    def test_idx4_foreign_index_is_not_clamped_onto_a_short_progression(self) -> None:
        session = self.new_session()
        session["ii_selected_chord"] = "Cadd9"   # not on the new progression
        session["ii_selected_chord_index"] = 20
        chords = list(COMP_IN_C)
        sym, idx = self._selected(session, chords)
        self.assertTrue(0 <= idx < len(chords))
        self.assertEqual(
            idx, 0,
            "a foreign index must fall back to the safe default rather than "
            "clamping to the last chord and presenting it as the selection",
        )
        self.assertEqual(sym, chords[0])

    def test_idx5_returning_to_the_first_source_restores_its_position(self) -> None:
        """The MCH contract still owns per-source restore."""
        from creative_chord_selection_authority import (
            read_authoritative_mission_chord_selection,
            write_authoritative_chord_selection,
        )

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self.converge(session)
        flat = self.chord_map(session)
        section_map = [("A", flat[:8])]
        target = flat[3]
        write_authoritative_chord_selection(
            session, section_map, chord_symbol=target, section_label="A"
        )
        sym, _sec, idx = read_authoritative_mission_chord_selection(
            session, section_map
        )
        self.assertEqual(sym, target)
        self.assertEqual(idx, 3)


class TestCatalogPreviewIsolation(_Base):
    """PC1-PC9 -- temporary Custom SBI preview must not touch Perfect."""

    TABS = ("Missions", "Live Coach", "Harmony Map", "Deep Harmony", "Phrase / Motif")

    def _perfect(self):
        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self.converge(session)
        return session, pick

    def test_pc1_preview_opens_my_progression_at_its_own_key(self) -> None:
        session, pick = self._perfect()
        self.enter_creative(session)
        self.load_custom(session)
        # Stale residue from an older temporary preview must not be revived.
        session["_sbi_custom_visit_pk"] = "D"
        self.assertEqual(self.preview_custom(session), "Custom progression")

        self.assertEqual(
            self.owner(session), "catalog",
            "the preview must not become the global owner",
        )
        from creative_source_ownership_contract import resolve_custom_saved_original_key

        self.assertEqual(resolve_custom_saved_original_key(session), "C")
        self.assertEqual(
            self.original_key(session), PERFECT_ORIGINAL,
            "Perfect's Original Key must stay G during the preview",
        )
        del pick

    def test_pc2_leaving_the_preview_restores_perfect(self) -> None:
        session, pick = self._perfect()
        self.enter_creative(session)
        self.load_custom(session)
        self.preview_custom(session)
        self.goto(session, "creative")
        self.open_tab(session, "Missions")

        self.assertEqual(
            self.original_key(session), PERFECT_ORIGINAL,
            "Custom's Original C must not leak into Perfect",
        )
        self.assertEqual(
            str((session.get("selected_song") or {}).get("title") or ""), "Perfect"
        )
        del pick

    def test_pc3_explicit_eb_converges_without_a_refresh(self) -> None:
        session, pick = self._perfect()
        self.enter_creative(session)
        self.load_custom(session)
        self.preview_custom(session)
        self.goto(session, "creative")
        self.open_tab(session, "Missions")

        self.set_practice(session, pick, "Eb")

        self.assertEqual(
            self.saved_practice(session, pick), "Eb",
            "the explicit commit was dropped while a Custom preview was open",
        )
        self.assertEqual(self.original_key(session), PERFECT_ORIGINAL)
        self.assert_map_in_key(session, "Eb", "same-pass convergence")

    def test_pc4_and_pc5_every_creative_page_agrees(self) -> None:
        session, pick = self._perfect()
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        for tab in self.TABS:
            self.open_tab(session, tab)
            self.assertEqual(
                self.original_key(session), PERFECT_ORIGINAL, f"{tab}: Original"
            )
            self.assertEqual(self.saved_practice(session, pick), "Eb", f"{tab}: PK")
            self.assert_map_in_key(session, "Eb", tab)

    def test_pc6_refresh_keeps_g_eb(self) -> None:
        session, pick = self._perfect()
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        for _ in range(3):
            self.converge(session)
            self.original_key(session)
        self.assertEqual(self.original_key(session), PERFECT_ORIGINAL)
        self.assertEqual(self.saved_practice(session, pick), "Eb")
        self.assert_map_in_key(session, "Eb", "after refresh")

    def test_pc7_reboot_keeps_g_eb(self) -> None:
        session, pick = self._perfect()
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        fresh = self.reboot(session)
        self.assertEqual(self.original_key(fresh), PERFECT_ORIGINAL)
        self.assertEqual(self.saved_practice(fresh, pick), "Eb")

    def test_pc8_preview_after_eb_leaves_both_fields_alone(self) -> None:
        session, pick = self._perfect()
        self.enter_creative(session)
        self.set_practice(session, pick, "Eb")
        self.load_custom(session)
        self.preview_custom(session)
        self.goto(session, "practice")

        self.assertEqual(self.original_key(session), PERFECT_ORIGINAL)
        self.assertEqual(self.saved_practice(session, pick), "Eb")

    def test_pc9_repeated_preview_round_trips_do_not_contaminate(self) -> None:
        session, pick = self._perfect()
        self.set_practice(session, pick, "Eb")
        for _ in range(3):
            self.enter_creative(session)
            self.load_custom(session)
            self.preview_custom(session)
            self.goto(session, "practice")
            self.assertEqual(self.owner(session), "catalog")
            self.assertEqual(self.original_key(session), PERFECT_ORIGINAL)
            self.assertEqual(self.saved_practice(session, pick), "Eb")

    def test_original_key_is_never_projection_state(self) -> None:
        """Explicitly fails if Perfect's Original Key becomes C."""
        session, pick = self._perfect()
        self.assertEqual(self.original_key(session), PERFECT_ORIGINAL)

        self.enter_creative(session)
        self.load_custom(session)
        self.preview_custom(session)
        self.goto(session, "creative")
        self.open_tab(session, "Missions")
        self.set_practice(session, pick, "Eb")

        self.assertNotEqual(
            self.original_key(session), "C",
            "Perfect's Original Key became C after visiting Custom SBI",
        )
        self.assertEqual(self.original_key(session), PERFECT_ORIGINAL)


if __name__ == "__main__":
    unittest.main()
