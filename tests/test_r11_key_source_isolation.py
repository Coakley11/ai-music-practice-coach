"""R11: Original Key vs Practice Key isolation across source switches.

Original Key and Practice Key have different authorities and are asserted
separately here -- a fix that copied one into the other would satisfy neither
matrix.

  Original Key  = the active source/song's canonical metadata.
  Practice Key  = that same source's own saved override, falling back to its
                  Original Key only when no override exists.

Reproductions behind these tests, confirmed by write-tracing:

KEY-A  Custom My Progression C/C -> explicit Catalog Say
       ``cpl_session_is_active`` still returned True because a stale
       ``explicit_music_source_choice`` of custom short-circuited ahead of its
       own "live Catalog pick outranks lagging Custom residue" guard. Any
       Practice-Key *read* then called ``ensure_custom_active_song_identity``,
       which re-stamped ``active_catalog_pick_key`` and ``selected_song`` back
       to the Custom song -- so Say showed Practice Key C, and later Original
       Key C once ``selected_song.key`` had been overwritten.

COMP   Say G/G -> activate Composition My Composition
       ``set_composition_source`` never cleared
       ``EXPLICIT_CATALOG_SELECTION_EPOCH_KEY`` (``set_custom_source`` does),
       so ``explicit_catalog_selection_is_authoritative`` stayed True for the
       rest of the session and Catalog kept outranking the active Composition:
       Creative and Missions resolved Say's 156 chords.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

SAY_TITLE = "Say — John Mayer"
SAY_ORIGINAL = "G"


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _say_pick() -> str:
    from song_catalog.catalog import format_pick_key

    return format_pick_key("Pop", SAY_TITLE)


def _my_progression(orig: str = "C", n: int = 4) -> dict:
    pool = ["C", "Am", "F", "G"]
    return {
        "id": "my-prog-1",
        "name": "My Progression",
        "original_key_center": orig,
        "user_locked_home_key": True,
        "original_sections": {
            "Intro": [], "Chorus": [], "Bridge": [], "Outro": [],
            "Verse": [{"chord": pool[i % 4], "bars": 1} for i in range(n)],
        },
        "bpm": 100,
    }


#: The canonical My Composition progression in its Original Key of C.
#: Human review established that My Composition has real chord material; the
#: reported ``G Em C D`` is exactly this progression projected into G
#: (C->G is +7: C->G, Am->Em, F->C, G->D), which is why the transposition was
#: coherent while the Practice-Key owner was not.
COMPOSITION_CHORDS_IN_C = ["C", "Am", "F", "G"]
COMPOSITION_CHORDS_IN_G = ["G", "Em", "C", "D"]


def _composition_doc(
    title: str = "My Composition",
    key: str = "C major",
    chords: str | None = "C Am F G",
) -> dict:
    """A Composition document. ``chords=None`` builds the chordless variant."""
    from composition_document import (
        apply_section_chords,
        apply_structure_template,
        bootstrap_from_vision,
        ordered_sections,
        parse_chord_paste,
    )

    doc = bootstrap_from_vision(
        genre="Pop", song_idea="key isolation", title=title, key=key, bpm=100
    )
    apply_structure_template(doc, "simple")
    if chords:
        apply_section_chords(
            doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste(chords)
        )
    return doc


class _SourceSwitchMixin:
    """Activation helpers that go through the canonical production entries."""

    def setUp(self) -> None:
        from song_catalog.catalog import load_song_catalog

        self.library, self.picker, _g, _r = load_song_catalog()

    # ---------- activations ----------

    def new_session(self) -> dict:
        from songs.music_source import ensure_song_picker_catalog

        session: dict = {"studio_page": "picker"}
        ensure_song_picker_catalog(session, self.picker)
        return session

    def activate_catalog_say(self, session: dict) -> str:
        """The explicit Songs-page Catalog pick.

        ``begin_explicit_catalog_selection`` is documented as required before
        ``set_catalog_source`` / ``apply_pick_key``; without it
        ``set_catalog_source`` deliberately refuses while Custom activation is
        authoritative.
        """
        from songs.music_source import (
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            begin_explicit_catalog_selection,
            set_catalog_source,
        )
        from songs.state import activate_active_song_by_pick_key

        pick = _say_pick()
        # An explicit Catalog pick happens through the Songs-page source radio,
        # so that widget reads Catalog. Several owner checks (for example
        # picker_composition_mode) read it directly.
        session[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        begin_explicit_catalog_selection(session)
        session["active_catalog_pick_key"] = pick
        set_catalog_source(session)
        activate_active_song_by_pick_key(
            _FakeSt(session), pick, self.picker,
            song_library=self.library, origin="user",
        )
        # A real activation lands with the song's own key as the live display
        # key; the headless path leaves these unset, and the Creative
        # progression sync needs a practice key to resolve against.
        sel = session.get("selected_song") or {}
        live = str(sel.get("key") or SAY_ORIGINAL)
        session["display_key"] = live
        session["concert_key"] = live
        return pick

    def activate_custom(self, session: dict, n: int = 4) -> str:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for
        from songs.state import activate_active_song_by_pick_key

        active = _my_progression(n=n)
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

    def load_custom_without_activating(self, session: dict, n: int = 4) -> str:
        """Make a Custom available for a temporary Creative preview only."""
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for

        active = _my_progression(n=n)
        session[CPL_ACTIVE_KEY] = active
        session["cpl_saved_progressions"] = {"My Progression": active}
        pick = custom_pick_key_for(active)
        session["_last_custom_song_state"] = {
            "active": active, "pick_key": pick,
            "name": "My Progression", "custom_home_key": "C",
        }
        return pick

    def activate_composition(
        self, session: dict, key: str = "C major", chords: str | None = "C Am F G"
    ) -> tuple[str, dict]:
        from composition_session_state import save_document_to_library, set_active_document
        from composition_songs_bridge import (
            activate_composition_song_from_library,
            composition_pick_key_for,
        )

        doc = _composition_doc(key=key, chords=chords)
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

    def preview_custom_in_creative(self, session: dict) -> str:
        from studio_page_state import (
            apply_improv_song_source,
            flush_pending_improv_song_source,
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

    # ---------- observations ----------

    def original_key(self, session: dict) -> str:
        """The resolver the sidebar / Songs card use for Original Key."""
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import display_key_context

        rec = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
        home, _ident = display_key_context(
            session, catalog_song_data=rec, cpl_active_key=CPL_ACTIVE_KEY
        )
        return str(home or "")

    def practice_key(self, session: dict) -> str:
        """What the sidebar Practice Key resolves to for the active source."""
        from sidebar_key_identity import resolve_sidebar_key_identity

        return str(resolve_sidebar_key_identity(session).selector_token or "")

    def saved_practice_key(self, session: dict, pick: str) -> str:
        from songs.practice_key_state import get_practice_concert_key

        return str(get_practice_concert_key(session, pick, default="") or "")

    def global_owner(self, session: dict) -> str:
        from source_session_state import global_music_source_owner

        return global_music_source_owner(session)

    def chord_count(self, session: dict) -> int:
        raw = session.get("improv_song_concert_sections")
        if not isinstance(raw, dict):
            return 0
        return sum(len(v) for v in raw.values() if isinstance(v, list))

    def title(self, session: dict) -> str:
        return str((session.get("selected_song") or {}).get("title") or "")

    def persist_and_reboot(self, session: dict) -> dict:
        """Write to disk and rebuild a session the way a process restart does."""
        from music_persistent_state import persist_music_disk_state, prepare_music_workspace

        persist_music_disk_state(_FakeSt(session))
        fresh: dict = {}
        prepare_music_workspace(
            _FakeSt(fresh),
            song_picker_catalog=self.picker,
            song_library=self.library,
        )
        return fresh


class TestKeyIsolationCustomToCatalog(_SourceSwitchMixin, unittest.TestCase):
    """KEY1-KEY3, KEY9, KEY10 -- the Custom <-> Catalog switch."""

    def test_key1_custom_to_say_restores_say_original_and_practice(self) -> None:
        session = self.new_session()
        custom_pick = self.activate_custom(session)
        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.practice_key(session), "C")

        self.activate_catalog_say(session)

        self.assertEqual(self.global_owner(session), "catalog")
        self.assertEqual(self.title(session), "Say")
        self.assertEqual(
            self.original_key(session), SAY_ORIGINAL,
            "Say's Original Key is immutable song metadata",
        )
        self.assertEqual(
            self.practice_key(session), SAY_ORIGINAL,
            "Say's Practice Key must come from Say's own saved state (falling "
            "back to its Original Key), not from My Progression's C",
        )
        self.assertEqual(
            self.saved_practice_key(session, custom_pick), "C",
            "Custom keeps its own saved Practice Key for when it is reactivated",
        )

    def test_key1_a_practice_key_read_does_not_reclaim_custom_identity(self) -> None:
        """The first wrong transition: a read re-stamped global identity."""
        from songs.practice_key_state import resolve_practice_source_pick

        session = self.new_session()
        self.activate_custom(session)
        say = self.activate_catalog_say(session)

        for _ in range(3):
            resolve_practice_source_pick(session)

        self.assertEqual(
            str(session.get("active_catalog_pick_key") or ""), say,
            "resolve_practice_source_pick -> ensure_custom_active_song_identity "
            "re-stamped the Custom pick over the explicit Catalog selection",
        )
        self.assertEqual(self.title(session), "Say")
        self.assertEqual(self.original_key(session), SAY_ORIGINAL)

    def test_key2_refresh_on_songs_keeps_say(self) -> None:
        session = self.new_session()
        self.activate_custom(session)
        self.activate_catalog_say(session)
        self.goto(session, "picker")
        # A refresh re-runs the read resolvers against the same session.
        for _ in range(2):
            self.original_key(session)
            self.practice_key(session)
        self.assertEqual(self.original_key(session), SAY_ORIGINAL)
        self.assertEqual(self.practice_key(session), SAY_ORIGINAL)

    def test_key3_reboot_on_songs_keeps_say(self) -> None:
        session = self.new_session()
        self.activate_custom(session)
        self.activate_catalog_say(session)
        self.goto(session, "picker")

        fresh = self.persist_and_reboot(session)
        self.assertEqual(self.title(fresh), "Say")
        self.assertEqual(self.original_key(fresh), SAY_ORIGINAL)
        self.assertEqual(self.practice_key(fresh), SAY_ORIGINAL)

    def test_key9_switching_back_to_custom_restores_custom_keys(self) -> None:
        session = self.new_session()
        self.activate_custom(session)
        self.activate_catalog_say(session)
        custom_pick = self.activate_custom(session)

        self.assertEqual(self.global_owner(session), "custom")
        self.assertEqual(
            self.original_key(session), "C",
            "Custom must not inherit Say's G",
        )
        self.assertEqual(self.practice_key(session), "C")
        self.assertEqual(self.saved_practice_key(session, custom_pick), "C")

    def test_key10_repeated_switching_does_not_contaminate(self) -> None:
        session = self.new_session()
        for _ in range(3):
            self.activate_custom(session)
            self.assertEqual(self.original_key(session), "C")
            self.assertEqual(self.practice_key(session), "C")

            self.activate_catalog_say(session)
            self.assertEqual(self.original_key(session), SAY_ORIGINAL)
            self.assertEqual(self.practice_key(session), SAY_ORIGINAL)

            self.enter_creative(session)
            self.load_custom_without_activating(session)
            self.preview_custom_in_creative(session)
            self.goto(session, "practice")
            self.assertEqual(
                self.global_owner(session), "catalog",
                "a temporary Creative preview must never become the owner",
            )
            self.assertEqual(self.original_key(session), SAY_ORIGINAL)


class TestKeyIsolationTemporaryCustomPreview(_SourceSwitchMixin, unittest.TestCase):
    """KEY4-KEY8 -- a Creative-local Custom preview must not touch Say's keys."""

    def _say_with_preview(self) -> dict:
        session = self.new_session()
        self.activate_catalog_say(session)
        self.enter_creative(session)
        self.load_custom_without_activating(session)
        self.preview_custom_in_creative(session)
        return session

    def test_key4_preview_leaves_say_persisted_keys_alone(self) -> None:
        session = self._say_with_preview()
        say = _say_pick()

        self.assertEqual(
            self.global_owner(session), "catalog",
            "the preview must not move the global owner",
        )
        self.assertEqual(
            self.title(session), "Say",
            "Say's active-song metadata must survive the preview",
        )
        self.assertEqual(
            self.original_key(session), SAY_ORIGINAL,
            "Say's persisted Original Key must remain G during the preview",
        )
        saved = self.saved_practice_key(session, say)
        self.assertIn(
            saved, ("", SAY_ORIGINAL),
            f"Say's saved Practice Key must not become Custom's C (got {saved!r})",
        )

    def test_key5_leaving_the_preview_for_missions_resolves_say(self) -> None:
        session = self._say_with_preview()
        self.goto(session, "creative")
        session["improv_intelligence_tab"] = "Missions"

        self.assertEqual(self.title(session), "Say")
        self.assertEqual(
            self.original_key(session), SAY_ORIGINAL,
            "Missions showed Original Key C because selected_song had been "
            "overwritten with the Custom record",
        )
        self.assertEqual(self.practice_key(session), SAY_ORIGINAL)

    def test_key6_refresh_on_missions_keeps_say(self) -> None:
        session = self._say_with_preview()
        self.goto(session, "creative")
        session["improv_intelligence_tab"] = "Missions"
        for _ in range(2):
            self.original_key(session)
            self.practice_key(session)
        self.assertEqual(self.original_key(session), SAY_ORIGINAL)
        self.assertEqual(self.practice_key(session), SAY_ORIGINAL)

    def test_key7_tab_round_trip_then_practice_keeps_say(self) -> None:
        session = self._say_with_preview()
        self.goto(session, "creative")
        for tab in ("Missions", "Live Coach", "Harmony Map", "Missions"):
            session["improv_intelligence_tab"] = tab
            self.assertEqual(self.original_key(session), SAY_ORIGINAL, f"tab {tab}")
        self.goto(session, "practice")
        self.assertEqual(self.original_key(session), SAY_ORIGINAL)
        self.assertEqual(self.practice_key(session), SAY_ORIGINAL)

    def test_key8_explicit_say_practice_key_survives_a_custom_preview(self) -> None:
        """Proves the two authorities are genuinely independent."""
        from songs.practice_key_state import set_practice_concert_key

        session = self.new_session()
        say = self.activate_catalog_say(session)
        set_practice_concert_key(
            session, "F", pick_key=say, commit_catalog_practice_key=True
        )
        self.assertEqual(self.saved_practice_key(session, say), "F")
        self.assertEqual(
            self.original_key(session), SAY_ORIGINAL,
            "changing the Practice Key must not move the Original Key",
        )

        self.enter_creative(session)
        self.load_custom_without_activating(session)
        self.preview_custom_in_creative(session)

        self.assertEqual(
            self.saved_practice_key(session, say), "F",
            "the Custom preview overwrote Say's saved Practice Key",
        )
        self.assertEqual(self.original_key(session), SAY_ORIGINAL)

        self.goto(session, "practice")
        self.assertEqual(self.original_key(session), SAY_ORIGINAL)
        self.assertEqual(self.saved_practice_key(session, say), "F")

        fresh = self.persist_and_reboot(session)
        self.assertEqual(self.original_key(fresh), SAY_ORIGINAL)
        self.assertEqual(
            self.saved_practice_key(fresh, say), "F",
            "G/F must survive a reboot",
        )


class TestCompositionSourceOwnership(_SourceSwitchMixin, unittest.TestCase):
    """COMP1-COMP10 -- Composition is a real source owner with real material."""

    def _say_then_composition(self) -> tuple[dict, str]:
        session = self.new_session()
        self.activate_catalog_say(session)
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        sync_song_improv_sections_to_practice_key(session)
        self.assertEqual(
            self.chord_count(session), 156,
            "precondition: Say's progression is loaded",
        )
        pick, _doc = self.activate_composition(session)
        return session, pick

    def test_comp1_activating_composition_owns_identity_and_keys(self) -> None:
        session, pick = self._say_then_composition()

        self.assertEqual(self.global_owner(session), "composition")
        self.assertEqual(self.title(session), "My Composition")
        self.assertEqual(
            self.original_key(session), "C",
            "Original Key comes from Composition metadata, never Say's G",
        )
        self.assertEqual(
            self.practice_key(session), "C",
            "Practice Key defaults to the Composition's Original Key",
        )
        self.assertEqual(self.saved_practice_key(session, pick), "C")

    def test_comp1_no_say_g_leaks_into_composition(self) -> None:
        session, _pick = self._say_then_composition()
        self.assertNotEqual(self.original_key(session), SAY_ORIGINAL)
        self.assertNotEqual(self.practice_key(session), SAY_ORIGINAL)

    def test_comp2_creative_opens_on_the_composition_lane(self) -> None:
        from source_session_state import creative_source_options_for_global_owner

        session, _pick = self._say_then_composition()
        lane = self.enter_creative(session)

        self.assertEqual(
            lane, "Composition",
            "Creative must not silently default to Custom or the Active song",
        )
        options = creative_source_options_for_global_owner(session)
        self.assertNotIn(
            "Active song", options,
            "a stale Catalog song must not be offered while Composition owns "
            "the app",
        )

    def test_comp3_missions_sees_no_stale_material(self) -> None:
        session, _pick = self._say_then_composition()
        self.enter_creative(session)
        session["improv_intelligence_tab"] = "Missions"

        self.assertEqual(
            self.chord_count(session), len(COMPOSITION_CHORDS_IN_C) * 2,
            "Missions must use the Composition's own progression, not Say's",
        )
        flat = [
            c
            for chords in (session.get("improv_song_concert_sections") or {}).values()
            for c in chords
        ]
        self.assertEqual(set(flat), set(COMPOSITION_CHORDS_IN_C))

    def test_comp3_mission_chord_map_is_empty(self) -> None:
        from creative_chord_selection_authority import _section_map_fallback_raw

        session, _pick = self._say_then_composition()
        self.enter_creative(session)
        mapped = _section_map_fallback_raw(session, ctx=None)
        flat = [c for _l, chords in mapped for c in chords]
        self.assertTrue(flat, "the Composition's chord map must be available")
        self.assertEqual(
            set(flat), set(COMPOSITION_CHORDS_IN_C),
            f"the chord map must be the Composition's own: {flat[:8]}",
        )

    def test_comp4_refresh_on_creative_keeps_composition(self) -> None:
        session, _pick = self._say_then_composition()
        self.enter_creative(session)
        from source_session_state import seed_creative_song_source_before_render

        for _ in range(2):
            seed_creative_song_source_before_render(session)
            self.original_key(session)
        self.assertEqual(self.global_owner(session), "composition")
        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.chord_count(session), len(COMPOSITION_CHORDS_IN_C) * 2)

    def test_comp5_refresh_on_missions_keeps_composition(self) -> None:
        session, _pick = self._say_then_composition()
        self.enter_creative(session)
        session["improv_intelligence_tab"] = "Missions"
        for _ in range(2):
            self.original_key(session)
            self.practice_key(session)
        self.assertEqual(self.title(session), "My Composition")
        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.practice_key(session), "C")
        self.assertEqual(self.chord_count(session), len(COMPOSITION_CHORDS_IN_C) * 2)

    def test_comp6_reboot_restores_composition(self) -> None:
        session, pick = self._say_then_composition()
        self.goto(session, "picker")
        fresh = self.persist_and_reboot(session)

        self.assertEqual(self.global_owner(fresh), "composition")
        self.assertEqual(self.title(fresh), "My Composition")
        self.assertEqual(self.original_key(fresh), "C")
        self.assertEqual(self.practice_key(fresh), "C")
        self.assertEqual(
            self.chord_count(fresh), len(COMPOSITION_CHORDS_IN_C) * 2,
            "a reboot must restore the Composition's own progression, never the "
            "previous Catalog one",
        )
        del pick

    def test_comp7_temporary_custom_preview_leaves_composition_intact(self) -> None:
        session, pick = self._say_then_composition()
        self.enter_creative(session)
        self.load_custom_without_activating(session)
        self.assertEqual(self.preview_custom_in_creative(session), "Custom progression")

        self.assertEqual(
            self.global_owner(session), "composition",
            "the preview must not become the global owner",
        )

        self.goto(session, "practice")
        self.assertEqual(self.global_owner(session), "composition")
        self.assertEqual(self.title(session), "My Composition")
        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.saved_practice_key(session, pick), "C")

    def test_comp8_composition_practice_key_override_is_independent(self) -> None:
        from songs.practice_key_state import set_practice_concert_key

        session, pick = self._say_then_composition()
        set_practice_concert_key(session, "D", pick_key=pick)
        self.assertEqual(self.saved_practice_key(session, pick), "D")
        self.assertEqual(
            self.original_key(session), "C",
            "the Composition Original Key must not follow its Practice Key",
        )

        self.enter_creative(session)
        self.load_custom_without_activating(session)
        self.preview_custom_in_creative(session)
        self.goto(session, "practice")

        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.saved_practice_key(session, pick), "D")

        fresh = self.persist_and_reboot(session)
        self.assertEqual(self.original_key(fresh), "C")
        self.assertEqual(self.saved_practice_key(fresh, pick), "D")

    def test_comp9_composition_to_catalog_restores_say(self) -> None:
        session, comp_pick = self._say_then_composition()
        self.activate_catalog_say(session)

        self.assertEqual(self.global_owner(session), "catalog")
        self.assertEqual(self.title(session), "Say")
        self.assertEqual(
            self.original_key(session), SAY_ORIGINAL,
            "Say must not inherit the Composition's C",
        )
        self.assertEqual(self.practice_key(session), SAY_ORIGINAL)
        # Leaving Composition ends its continuous Practice lifetime, matching
        # the documented Custom behaviour (switch_to_catalog_from_custom clears
        # the saved Custom Practice Key on a true leave). What matters here is
        # that nothing of the Composition's leaks into Say; COMP10 covers the
        # Composition resolving back to its own key on return.
        self.assertNotEqual(
            self.saved_practice_key(session, _say_pick()), "C",
            "the Composition's C must not become Say's saved Practice Key",
        )
        del comp_pick

    def test_comp10_catalog_back_to_composition_restores_composition(self) -> None:
        session, comp_pick = self._say_then_composition()
        self.activate_catalog_say(session)
        from composition_songs_bridge import activate_composition_song_from_library
        from composition_session_state import get_active_document

        doc = get_active_document(session)
        activate_composition_song_from_library(_FakeSt(session), str(doc["id"]))

        self.assertEqual(self.global_owner(session), "composition")
        self.assertEqual(self.original_key(session), "C")
        self.assertEqual(self.practice_key(session), "C")
        self.assertEqual(
            self.chord_count(session), len(COMPOSITION_CHORDS_IN_C) * 2,
            "returning to the Composition must restore its own chords, never "
            "carry Say's",
        )
        del comp_pick


class TestExplicitSourceEpochSymmetry(_SourceSwitchMixin, unittest.TestCase):
    """The newest explicit source activation must hold the authority flags.

    ``set_custom_source`` clears the explicit-Catalog epoch when Custom takes
    over. ``set_composition_source`` did not, so
    ``explicit_catalog_selection_is_authoritative`` stayed True for the rest of
    the session and every resolver that branches on it kept treating the
    previous Catalog song as authoritative over the active Composition.
    """

    def test_activating_composition_releases_catalog_authority(self) -> None:
        from songs.music_source import explicit_catalog_selection_is_authoritative

        session = self.new_session()
        self.activate_catalog_say(session)
        self.assertTrue(
            explicit_catalog_selection_is_authoritative(session),
            "precondition: the explicit Catalog pick is authoritative",
        )

        self.activate_composition(session)

        self.assertFalse(
            explicit_catalog_selection_is_authoritative(session),
            "an explicit Composition activation is newer than the Catalog pick "
            "and must release Catalog authority, the way Custom activation does",
        )

    def test_activating_custom_releases_catalog_authority(self) -> None:
        """The already-correct Custom side, pinned so the symmetry stays."""
        from songs.music_source import explicit_catalog_selection_is_authoritative

        session = self.new_session()
        self.activate_catalog_say(session)
        self.activate_custom(session)
        self.assertFalse(explicit_catalog_selection_is_authoritative(session))

    def test_explicit_catalog_pick_claims_the_explicit_source_choice(self) -> None:
        """Catalog never stamped its own explicit choice; the others did."""
        from songs.music_source import SOURCE_CATALOG, explicit_music_source_choice

        session = self.new_session()
        self.activate_custom(session)
        self.activate_catalog_say(session)
        self.assertEqual(
            explicit_music_source_choice(session), SOURCE_CATALOG,
            "a stale explicit_music_source_choice of custom kept Custom "
            "resolvers winning after the user picked a Catalog song",
        )


class TestCompositionSbiAvailabilityReflectsMaterial(
    _SourceSwitchMixin, unittest.TestCase
):
    """Availability reports real material, rather than a hardcoded False.

    Human review disproved the earlier assumption that Composition is always
    chordless, so the tests that enforced it are gone. ``composition_sbi_source_
    available`` used to ``return False`` unconditionally, which made a
    Composition that *does* carry a progression read as an unavailable,
    zero-chord source.
    """

    def test_available_when_the_composition_has_chords(self) -> None:
        from source_session_state import composition_sbi_source_available

        session = self.new_session()
        self.activate_composition(session)
        self.assertTrue(composition_sbi_source_available(session))

    def test_unavailable_when_the_composition_has_no_chords(self) -> None:
        from source_session_state import composition_sbi_source_available

        session = self.new_session()
        self.activate_composition(session, chords=None)
        self.assertFalse(
            composition_sbi_source_available(session),
            "a genuinely chordless Composition is still unavailable, and must "
            "not borrow another source's harmony to look usable",
        )

    def test_a_chordless_composition_stays_at_zero_chords(self) -> None:
        """Zero chords means zero chords, for Composition as for Custom."""
        session = self.new_session()
        self.activate_catalog_say(session)
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        sync_song_improv_sections_to_practice_key(session)
        self.assertEqual(self.chord_count(session), 156)

        self.activate_composition(session, chords=None)
        self.assertEqual(
            self.chord_count(session), 0,
            "a chordless Composition must not inherit Say's progression",
        )


if __name__ == "__main__":
    unittest.main()
