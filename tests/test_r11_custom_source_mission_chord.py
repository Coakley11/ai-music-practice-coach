"""R11: Custom Progression source ownership + Mission chord selection authority.

Every test here was written against a reproduction trace and fails on the
starting ``origin/dev`` (caaaaa04). They assert observable state that the
musician-facing surfaces read, not that particular lines of code exist.

DEFECT 2 (Custom source leak) reproduction, confirmed by trace:
  activate Catalog Satin Doll / C  ->  navigate Creative  ->  activate
  Custom Progression / Trial Song (Original Key D, zero chords)

  Ownership resolved correctly (``custom_owns_active_song_material`` True,
  snapshot = custom / Trial Song / D / 0 chords) while three session globals
  kept Catalog's values:
    * ``improv_song_concert_sections``  = Satin Doll's 5 sections / 36 chords
    * ``improv_song_source``            = "Active song"
    * sidebar Practice Key              = C (Satin Doll's), not D

DEFECT 1 (Mission chord) reproduction, confirmed by trace:
  an explicit chord click seals the session, but the workflow blob commit is
  deferred whenever the active pointer is not ``mission_jam``; the next
  ``restore_workflow_blob_to_session`` then projects the blob's OLDER chord
  back over the musician's selection.
"""

from __future__ import annotations

import copy
import unittest

from song_catalog.catalog import format_pick_key

SATIN_PICK = format_pick_key("Jazz", "Satin Doll — Duke Ellington")

MISSION_SECTIONS = {
    "A": ["Dm7", "G7", "Em7", "A7"],
    "B (Bridge)": ["Gm7", "C7", "Fmaj7", "Fmaj7"],
}


def _mission_section_map() -> list[tuple[str, list[str]]]:
    return [(k, list(v)) for k, v in MISSION_SECTIONS.items()]


def _trial_active(n_chords: int = 0) -> dict:
    """Trial Song: Original Key D. ``n_chords=0`` is the reported empty case.

    ``user_locked_home_key`` mirrors a musician who typed an Original Key, so
    the saved D is authoritative rather than inferred from chord analysis.
    """
    pool = ["D", "A", "Bm", "G"]
    verse = [{"chord": pool[i % len(pool)], "bars": 1} for i in range(n_chords)]
    return {
        "id": "trial-rev-1",
        "name": "Trial Song",
        "original_key_center": "D",
        "user_locked_home_key": True,
        "original_sections": {
            "Intro": [], "Verse": verse, "Chorus": [], "Bridge": [], "Outro": [],
        },
        "bpm": 96,
    }


def _chord_count(sections) -> int:
    if not isinstance(sections, dict):
        return 0
    return sum(len(v) for v in sections.values() if isinstance(v, list))


class _CustomSourceReproMixin:
    """Builds the exact reported Catalog -> Creative -> Custom sequence."""

    def _catalog_session(self) -> dict:
        from song_catalog.catalog import load_song_catalog
        from songs.music_source import ensure_song_picker_catalog, set_catalog_source
        from songs.state import activate_active_song_by_pick_key
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key
        from types import SimpleNamespace

        library, picker, _genres, _records = load_song_catalog()
        session: dict = {"studio_page": "picker", "active_catalog_pick_key": SATIN_PICK}
        ensure_song_picker_catalog(session, picker)
        set_catalog_source(session)
        activate_active_song_by_pick_key(
            SimpleNamespace(session_state=session), SATIN_PICK,
            picker, song_library=library, origin="user",
        )
        sel = session.get("selected_song") or {}
        key = str(sel.get("key") or "C")
        session.setdefault("original_key", key)
        session["display_key"] = session.get("display_key") or key
        session["concert_key"] = session.get("concert_key") or key
        sync_song_improv_sections_to_practice_key(session)
        return session

    def _activate_custom(self, session: dict, n_chords: int = 0) -> str:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for, set_custom_source

        active = _trial_active(n_chords)
        session[CPL_ACTIVE_KEY] = active
        pick = custom_pick_key_for(active)
        session["_last_custom_song_state"] = {
            "active": active, "pick_key": pick,
            "name": "Trial Song", "custom_home_key": "D",
        }
        set_custom_source(session)
        return pick


class TestCatalogBaselineIsTheLeakSource(unittest.TestCase):
    """Anchor the reported 36 chords to Satin Doll, so later counts mean something."""

    def test_satin_doll_has_thirty_six_chords(self) -> None:
        from song_catalog.catalog import load_song_catalog

        _lib, picker, _g, _r = load_song_catalog()
        rec = picker["Jazz"]["Satin Doll — Duke Ellington"]
        self.assertEqual(str(rec.get("key") or ""), "C")
        self.assertEqual(
            _chord_count(rec.get("sections")), 36,
            "the reported '36 chords' is Satin Doll's chart; if this record "
            "changes, the leak assertions below need re-anchoring",
        )


class TestCustomOwnsProgression(_CustomSourceReproMixin, unittest.TestCase):
    """CUST: Custom owns the progression; Catalog material must not survive."""

    def test_catalog_baseline_populates_thirty_six_chords(self) -> None:
        """Guard the fixture: the leak is only meaningful if Catalog loaded."""
        session = self._catalog_session()
        self.assertEqual(_chord_count(session.get("improv_song_concert_sections")), 36)

    def test_cust1_empty_custom_does_not_inherit_catalog_progression(self) -> None:
        """Zero-chord Trial Song must read 0 chords, not Satin Doll's 36."""
        session = self._catalog_session()
        self.assertEqual(_chord_count(session.get("improv_song_concert_sections")), 36)

        self._activate_custom(session, n_chords=0)

        from workflow_musical_authority import custom_owns_active_song_material

        self.assertTrue(custom_owns_active_song_material(session))
        self.assertEqual(
            _chord_count(session.get("improv_song_concert_sections")), 0,
            "Custom Progression is authoritative with an empty progression, so "
            "no Creative surface may still see the previous Catalog chords",
        )

    def test_cust1_empty_custom_survives_a_creative_resync(self) -> None:
        """The Creative page's own sync must not restore the Catalog map."""
        session = self._catalog_session()
        self._activate_custom(session, n_chords=0)

        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        sync_song_improv_sections_to_practice_key(session)
        self.assertEqual(
            _chord_count(session.get("improv_song_concert_sections")), 0,
            "sync_song_improv_sections_to_practice_key returned empty for Custom "
            "but left the stale Catalog sections in session",
        )

    def test_cust2_non_empty_custom_replaces_catalog_progression(self) -> None:
        session = self._catalog_session()
        self._activate_custom(session, n_chords=2)
        secs = session.get("improv_song_concert_sections") or {}
        self.assertEqual(_chord_count(secs), 2)
        self.assertNotIn("A2", secs)
        self.assertNotIn("Turnaround", secs)

    def test_cust3_mission_chord_map_sees_no_catalog_chords(self) -> None:
        """Harmony / Missions / Motif must not consume the last Catalog map."""
        session = self._catalog_session()
        self._activate_custom(session, n_chords=0)

        from creative_chord_selection_authority import _section_map_fallback_raw

        mapped = _section_map_fallback_raw(session, ctx=None)
        flat = [ch for _label, chords in mapped for ch in chords]
        self.assertEqual(
            flat, [],
            "the Creative chord map fell back to the Catalog progression while "
            f"Custom was authoritative: {flat}",
        )


class TestEmptyCustomClearsStaleChord(_CustomSourceReproMixin, unittest.TestCase):
    """CUST: an empty Custom owner leaves no Catalog chord selected."""

    def _select_a_catalog_chord(self, session: dict) -> str:
        from creative_chord_selection_authority import write_authoritative_chord_selection

        session["improv_intelligence_tab"] = "Missions"
        session["improv_active_mission"] = "pentatonic_target"
        secs = session.get("improv_song_concert_sections") or {}
        section_map = [(k, list(v)) for k, v in secs.items()]
        session["_improv_mission_section_map"] = section_map
        label, chords = section_map[0]
        write_authoritative_chord_selection(
            session, section_map, chord_symbol=chords[2], section_label=label
        )
        return chords[2]

    def test_cust9_empty_custom_clears_the_catalog_chord_selection(self) -> None:
        from workflow_musical_authority import refresh_custom_improv_concert_sections

        session = self._catalog_session()
        chord = self._select_a_catalog_chord(session)
        self.assertEqual(session.get("ii_selected_chord"), chord)

        self._activate_custom(session, n_chords=0)
        refresh_custom_improv_concert_sections(session)

        self.assertEqual(
            str(session.get("ii_selected_chord") or ""), "",
            f"the Catalog chord {chord!r} stayed selected after an empty Custom "
            "progression became authoritative, so Mission generation would "
            "still receive Catalog material",
        )
        self.assertNotIn("_mission_chord_click_authority", session)
        self.assertNotIn("_mission_chord_snapshot", session)

    def test_cust9_non_empty_custom_keeps_its_own_selection(self) -> None:
        """Only a chord-less owner clears; Practice-Key retarget must not lose one."""
        from creative_chord_selection_authority import write_authoritative_chord_selection
        from workflow_musical_authority import refresh_custom_improv_concert_sections

        session = self._catalog_session()
        self._activate_custom(session, n_chords=4)
        secs = session.get("improv_song_concert_sections") or {}
        section_map = [(k, list(v)) for k, v in secs.items()]
        self.assertTrue(section_map, "precondition: the Custom song has chords")
        label, chords = section_map[0]
        write_authoritative_chord_selection(
            session, section_map, chord_symbol=chords[0], section_label=label
        )

        refresh_custom_improv_concert_sections(session)
        self.assertEqual(session.get("ii_selected_chord"), chords[0])


class TestCustomOwnsSourceLabel(_CustomSourceReproMixin, unittest.TestCase):
    """CUST: the Creative source label must name Custom, not the Active song."""

    def _first_creative_entry(self, session: dict) -> None:
        """The once-per-session Creative init.

        ``ensure_creative_improv_initialized`` guards this with a one-shot
        ``_page_initialized::creative_improv`` flag that is never cleared, so it
        cannot be what fixes a source switch made after Creative was first
        opened. The per-render seed below is the load-bearing path.
        """
        from studio_page_state import init_improvisation_state
        from songs.music_source import custom_progression_is_active

        session["studio_page"] = "creative"
        init_improvisation_state(
            session, is_custom_active=custom_progression_is_active(session)
        )

    def _render_song_source_radio(self, session: dict) -> str:
        """The value the Song source radio takes on this render.

        ``improvisation_intelligence_ui`` calls
        ``seed_sbi_custom_radio_before_render`` immediately before
        ``st.radio(..., key="improv_song_source")``, so whatever this leaves in
        ``improv_song_source`` is what the radio shows and what the source card
        branches on.
        """
        from source_session_state import seed_sbi_custom_radio_before_render

        session["studio_page"] = "creative"
        seed_sbi_custom_radio_before_render(session)
        return str(session.get("improv_song_source") or "")

    def test_cust4_radio_names_custom_after_switching_from_catalog(self) -> None:
        """The reported path: Creative was already open before Custom activated."""
        session = self._catalog_session()
        self._first_creative_entry(session)
        self.assertEqual(
            self._render_song_source_radio(session), "Active song",
            "precondition: the Catalog session leaves the SBI preview on "
            "'Active song'",
        )

        self._activate_custom(session, n_chords=0)

        self.assertEqual(
            self._render_song_source_radio(session), "Custom progression",
            "the Creative source card rendered 'Active song · Song Selection' "
            "because the per-render seed forced the leftover 'Active song' "
            "preview over Global Active Custom",
        )

    def test_cust4_label_is_custom_for_a_non_empty_progression_too(self) -> None:
        session = self._catalog_session()
        self._first_creative_entry(session)
        self._activate_custom(session, n_chords=3)
        self.assertEqual(
            self._render_song_source_radio(session), "Custom progression"
        )

    def test_cust4_first_creative_entry_also_names_custom(self) -> None:
        session = self._catalog_session()
        self._activate_custom(session, n_chords=0)
        self._first_creative_entry(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")

    def test_cust4_a_deliberate_sbi_active_choice_is_preserved(self) -> None:
        """Regression: choosing 'Active song' in SBI must still stick."""
        from source_session_state import stamp_sbi_active_leave_intent

        session = self._catalog_session()
        self._activate_custom(session, n_chords=2)
        # The musician deliberately switches the SBI source back to Active song.
        stamp_sbi_active_leave_intent(session)
        session["sbi_preview_source"] = "Active song"
        session["improv_song_source"] = "Active song"
        self.assertEqual(
            self._render_song_source_radio(session), "Active song",
            "a deliberate SBI 'Active song' selection must not be overridden "
            "by Global Active Custom",
        )

    def test_cust4_catalog_active_still_names_the_active_song(self) -> None:
        """Regression: Catalog Global Active must keep the Active song source."""
        session = self._catalog_session()
        self.assertEqual(self._render_song_source_radio(session), "Active song")


class TestCustomOwnsPracticeKey(_CustomSourceReproMixin, unittest.TestCase):
    """CUST: Original Key D; absent a saved override the Practice Key is D."""

    def test_cust5_activation_initializes_practice_key_to_saved_original(self) -> None:
        session = self._catalog_session()
        self._activate_custom(session, n_chords=0)

        from creative_source_ownership_contract import resolve_custom_saved_original_key

        self.assertEqual(resolve_custom_saved_original_key(session), "D")
        self.assertEqual(session.get("display_key"), "D")
        self.assertEqual(session.get("concert_key"), "D")

    def test_cust5_practice_key_seed_ignores_inferred_tonal_center(self) -> None:
        """A saved Original Key of D must not be replaced by chord analysis.

        With chords [D, A] the inferred tonal centre is A; Trial Song's saved
        Original Key is still D, and activation must initialize D.
        """
        session = self._catalog_session()
        self._activate_custom(session, n_chords=2)
        self.assertEqual(
            session.get("display_key"), "D",
            "activation seeded the Practice Key from the inferred tonal centre "
            "instead of Trial Song's saved Original Key D",
        )

    def test_cust6_stale_catalog_key_does_not_beat_custom_identity(self) -> None:
        """The reported sidebar C: leaked, not saved.

        Signature from the trace -- when C is legitimately saved the sidebar
        identity TOKEN is itself C; when it leaks, the token is D while the
        written key is C.
        """
        from sidebar_key_identity import (
            prime_sidebar_practice_key_from_identity,
            resolve_sidebar_key_identity,
        )

        session = self._catalog_session()
        pick = self._activate_custom(session, n_chords=0)
        # Catalog's C is still the live key when the sidebar renders.
        session["studio_page"] = "creative"
        session["display_key"] = "C"
        session["concert_key"] = "C"

        ident = resolve_sidebar_key_identity(session)
        self.assertEqual(ident.owner, "custom_progression")
        self.assertEqual(
            ident.selector_token, "D",
            "precondition: no Custom Practice Key is saved, so the identity "
            "token must be Trial Song's Original Key D",
        )

        prime_sidebar_practice_key_from_identity(session, st=None)

        self.assertEqual(
            session.get("concert_key"), "D",
            "the stale Catalog Practice Key C outranked the Custom identity "
            "token D (prime_sidebar_practice_key_from_identity protected the "
            "live key without checking which source it belonged to)",
        )
        del pick

    def test_cust7_a_genuinely_saved_custom_practice_key_is_honoured(self) -> None:
        """The narrowed guard must not break a real saved Custom override."""
        from sidebar_key_identity import (
            prime_sidebar_practice_key_from_identity,
            resolve_sidebar_key_identity,
        )
        from songs.practice_key_state import set_practice_concert_key

        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for

        session = self._catalog_session()
        # Trial Song already carries a saved Practice Key of F from earlier work,
        # which activation must restore instead of resetting to Original D.
        pick = custom_pick_key_for(_trial_active(0))
        set_practice_concert_key(session, "F", pick_key=pick)
        self.assertEqual(
            dict(session.get("practice_key_by_source") or {}).get(pick), "F",
            "precondition: the saved Custom Practice Key is stored",
        )

        self._activate_custom(session, n_chords=0)
        session["studio_page"] = "creative"
        del CPL_ACTIVE_KEY

        self.assertEqual(
            session.get("display_key"), "F",
            "activation reset the Practice Key to the Original Key and "
            "discarded Trial Song's saved override",
        )

        ident = resolve_sidebar_key_identity(session)
        self.assertEqual(
            ident.selector_token, "F",
            "a saved Custom Practice Key must become the sidebar identity token",
        )

        prime_sidebar_practice_key_from_identity(session, st=None)
        self.assertEqual(
            session.get("concert_key"), "F",
            "the narrowed foreign-key guard must not discard a genuinely saved "
            "Custom Practice Key",
        )

    def test_cust8_catalog_practice_key_still_wins_on_a_catalog_surface(self) -> None:
        """Regression: the Catalog sticky must keep beating a stale blob token."""
        from sidebar_key_identity import prime_sidebar_practice_key_from_identity
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        session = self._catalog_session()
        session["studio_page"] = "picker"
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {SATIN_PICK: "Eb"}
        session["display_key"] = "Eb"
        session["concert_key"] = "Eb"

        prime_sidebar_practice_key_from_identity(session, st=None)
        self.assertEqual(
            session.get("concert_key"), "Eb",
            "a saved Catalog Practice Key must survive the sidebar primer",
        )


class TestMissionChordBeatsStaleWorkflowBlob(unittest.TestCase):
    """MCH: the newest explicit selection outranks the workflow blob.

    ``mutate_mission_chord_selection`` defers the blob commit whenever the
    active workflow pointer is not ``mission_jam`` (it returns
    ``CHORD_OWNER_ACTIVATE_DEFERRED`` with ``ok=True``), so the blob keeps the
    previous chord while the session holds the new one. The blob projection
    then wrote the old chord back.
    """

    def _mission_session(self, tab: str = "Missions") -> dict:
        return {
            "studio_page": "creative",
            "improv_intelligence_tab": tab,
            "active_catalog_pick_key": SATIN_PICK,
            "selected_song": {
                "pick_key": SATIN_PICK, "title": "Satin Doll", "key": "C",
                "genre": "Jazz", "sections": copy.deepcopy(MISSION_SECTIONS),
            },
            "song": "Satin Doll",
            "home_sections": copy.deepcopy(MISSION_SECTIONS),
            "improv_song_concert_sections": copy.deepcopy(MISSION_SECTIONS),
            "original_key": "C", "display_key": "C", "concert_key": "C",
            "improv_active_mission": "pentatonic_target",
            "improv_mission_new_nonce": "nonce-1",
            "_improv_mission_section_map": _mission_section_map(),
        }

    def _stale_blob(self, chord: str = "Dm7", section: str = "A", index: int = 0):
        from music_workflow_state_store import WorkflowStateBlob

        blob = WorkflowStateBlob(workflow_owner="mission_jam", workflow_session_id="w1")
        blob.selected_chord_symbol = chord
        blob.selected_section = section
        blob.selected_chord_index = index
        blob.mission_type = "pentatonic_target"
        return blob

    def test_mch1_blob_projection_keeps_the_newest_click(self) -> None:
        from creative_chord_selection_authority import write_authoritative_chord_selection
        from music_workflow_legacy_projection import restore_workflow_blob_to_session

        session = self._mission_session()
        write_authoritative_chord_selection(
            session, _mission_section_map(), chord_symbol="A7", section_label="A"
        )
        self.assertEqual(session.get("ii_selected_chord"), "A7")

        restore_workflow_blob_to_session(session, self._stale_blob("Dm7"))

        self.assertEqual(
            session.get("ii_selected_chord"), "A7",
            "the stale workflow blob chord overwrote the musician's newer "
            "selection; surfaces bound to ii_selected_chord show the old chord",
        )
        self.assertEqual(session.get("ii_selected_section"), "A")
        self.assertEqual(int(session.get("ii_selected_chord_index") or -1), 3)

    def test_mch1_holds_when_no_snapshot_was_sealed(self) -> None:
        """Off the Missions surface no snapshot is sealed, so the session key
        is the only record of the click and must not be clobbered."""
        from creative_chord_selection_authority import (
            MISSION_CHORD_SNAPSHOT_KEY,
            write_authoritative_chord_selection,
        )
        from music_workflow_legacy_projection import restore_workflow_blob_to_session

        session = self._mission_session(tab="Live Coach")
        session.pop("improv_active_mission", None)
        write_authoritative_chord_selection(
            session, _mission_section_map(), chord_symbol="A7", section_label="A"
        )
        self.assertNotIn(MISSION_CHORD_SNAPSHOT_KEY, session)

        restore_workflow_blob_to_session(session, self._stale_blob("Dm7"))
        self.assertEqual(session.get("ii_selected_chord"), "A7")

    def test_mch2_reselection_replaces_the_previous_chord_everywhere(self) -> None:
        from creative_chord_selection_authority import (
            read_authoritative_mission_chord_selection,
            write_authoritative_chord_selection,
        )
        from music_workflow_legacy_projection import restore_workflow_blob_to_session

        session = self._mission_session()
        write_authoritative_chord_selection(
            session, _mission_section_map(), chord_symbol="Em7", section_label="A"
        )
        write_authoritative_chord_selection(
            session, _mission_section_map(), chord_symbol="Gm7",
            section_label="B (Bridge)",
        )
        restore_workflow_blob_to_session(session, self._stale_blob("Em7"))

        self.assertEqual(session.get("ii_selected_chord"), "Gm7")
        sym, sec, _idx = read_authoritative_mission_chord_selection(
            session, _mission_section_map()
        )
        self.assertEqual(sym, "Gm7")
        self.assertEqual(sec, "B (Bridge)")

    def test_mch3_blob_still_restores_when_there_is_no_explicit_selection(self) -> None:
        """Without a newer click the blob remains the restore authority."""
        from music_workflow_legacy_projection import restore_workflow_blob_to_session

        session = self._mission_session()
        session.pop("ii_selected_chord", None)
        session.pop("_mission_chord_click_authority", None)

        restore_workflow_blob_to_session(session, self._stale_blob("Dm7"))
        self.assertEqual(
            session.get("ii_selected_chord"), "Dm7",
            "refresh / reboot restore must still project the stored chord when "
            "the musician has not selected a newer one",
        )

    def test_mch4_blob_wins_for_a_different_mission(self) -> None:
        """A click belonging to another Mission must not block this restore."""
        from creative_chord_selection_authority import write_authoritative_chord_selection
        from music_workflow_legacy_projection import restore_workflow_blob_to_session

        session = self._mission_session()
        write_authoritative_chord_selection(
            session, _mission_section_map(), chord_symbol="A7", section_label="A"
        )
        # The musician then switched Mission; the click belongs to the old one.
        session["improv_active_mission"] = "blues_phrase"
        blob = self._stale_blob("Dm7")
        blob.mission_type = "blues_phrase"
        blob.mission_id = "blues_phrase"

        restore_workflow_blob_to_session(session, blob)
        self.assertEqual(session.get("ii_selected_chord"), "Dm7")

    def test_mch5_blob_wins_for_a_different_source_song(self) -> None:
        from creative_chord_selection_authority import write_authoritative_chord_selection
        from music_workflow_legacy_projection import restore_workflow_blob_to_session

        session = self._mission_session()
        write_authoritative_chord_selection(
            session, _mission_section_map(), chord_symbol="A7", section_label="A"
        )
        # Active song changed, so the click no longer describes this source.
        session["active_catalog_pick_key"] = format_pick_key("Pop", "Say — John Mayer")

        restore_workflow_blob_to_session(session, self._stale_blob("Dm7"))
        self.assertEqual(session.get("ii_selected_chord"), "Dm7")


class TestCreativePageRuntimeSmoke(unittest.TestCase):
    """Execute the app script on the pages these fixes changed.

    Unit tests exercise the resolvers directly. Streamlit only runs the app
    script when a session connects, so an exception on the Creative render path
    reaches the musician and not any assertion above -- which is how an
    undefined name previously reached the browser. AppTest runs the script the
    way a session does.
    """

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("streamlit AppTest unavailable")
        import os
        from pathlib import Path

        cls._app = str(
            Path(__file__).resolve().parent.parent / "streamlit_music_practice_app.py"
        )
        os.environ.setdefault(
            "MUSIC_APP_DATA_DIR",
            str(Path(cls._app).parent / "_runtime_r11_smoke"),
        )

    def _run(self, **state):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self._app, default_timeout=600)
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        if at.exception:
            msgs = [str(getattr(exc, "value", exc)) for exc in at.exception]
            self.fail("app script raised:\n  " + "\n  ".join(msgs))
        return at

    def test_creative_page_runs(self) -> None:
        self._run(studio_page="creative")

    def test_creative_page_runs_with_custom_active(self) -> None:
        from songs.music_source import SOURCE_CUSTOM, custom_pick_key_for
        from custom_progression_lab import CPL_ACTIVE_KEY

        active = _trial_active(0)
        pick = custom_pick_key_for(active)
        self._run(
            studio_page="creative",
            active_music_source=SOURCE_CUSTOM,
            active_catalog_pick_key=pick,
            **{
                CPL_ACTIVE_KEY: active,
                "_last_custom_song_state": {
                    "active": active, "pick_key": pick,
                    "name": "Trial Song", "custom_home_key": "D",
                },
            },
        )

    def test_creative_missions_tab_runs_with_custom_active(self) -> None:
        from songs.music_source import SOURCE_CUSTOM, custom_pick_key_for
        from custom_progression_lab import CPL_ACTIVE_KEY

        active = _trial_active(0)
        pick = custom_pick_key_for(active)
        self._run(
            studio_page="creative",
            improv_intelligence_tab="Missions",
            active_music_source=SOURCE_CUSTOM,
            active_catalog_pick_key=pick,
            **{CPL_ACTIVE_KEY: active},
        )


if __name__ == "__main__":
    unittest.main()
