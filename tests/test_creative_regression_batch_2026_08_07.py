"""Regression batch: jam key leak, page refresh, mission generate chord stability."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from creative_chord_selection_authority import (
    global_chord_index_for_section_chord,
    write_authoritative_chord_selection,
)
from creative_key_sync import entry_jam_practice_key_authority_active, resolve_creative_tab_practice_key_token
from improvisation_intelligence_ui import (
    MISSIONS_GENERATE_CONTEXT_KEY,
    _authoritative_practice_chart_key,
    _run_mission_example_generate,
    _stash_missions_generate_context,
)
from improvisation_motif import flatten_section_map, resolve_improv_sections
from music_persistent_state import begin_script_run_navigation_markers
from music_workflow_mutation import update_mission_example_on_blob
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    WorkflowStateBlob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from studio_nav_state import STUDIO_NAV_STATE_KEY, prepare_studio_nav


def _hevenu_session() -> dict[str, Any]:
    import copy

    sections = {
        "Melody A": ["C#m", "G#7", "C#m", "F#m", "B", "E", "A", "D"],
        "Melody B": ["C#m", "G#7", "Bb7", "F#m", "B", "E", "A", "D"],
    }
    return {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "display_key": "Dm",
        "concert_key": "Dm",
        "active_catalog_pick_key": "hevenu_shalom",
        "home_sections": copy.deepcopy(sections),
        "improv_song_concert_sections": copy.deepcopy(sections),
        "instrument": "Guitar",
        "level": "Intermediate",
        "focus": "Improvisation",
    }


def _hevenu_ctx() -> Any:
    from improvisation_intelligence import ImprovSessionContext

    sections = {
        "Melody A": ["C#m", "G#7", "C#m", "F#m", "B", "E", "A", "D"],
        "Melody B": ["C#m", "G#7", "Bb7", "F#m", "B", "E", "A", "D"],
    }
    flat = flatten_section_map(list(sections.items()))
    return ImprovSessionContext(
        song_title="Hevenu Shalom Aleichem",
        artist="Traditional",
        key_center="Dm",
        display_key="Dm",
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        sections=sections,
        bpm=72,
        style_label="",
        progression_flat=flat,
        section_order=list(sections.keys()),
    )


class JamKeyMissionLeakTests(unittest.TestCase):
    def test_missions_tab_reclaims_key_from_stale_jam_fields(self) -> None:
        session: dict = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "Eb",
            "display_key": "Dm",
            "concert_key": "Dm",
            "active_catalog_pick_key": "hevenu_shalom",
        }
        self.assertFalse(entry_jam_practice_key_authority_active(session))
        self.assertEqual(resolve_creative_tab_practice_key_token(session), "")
        chart_key = _authoritative_practice_chart_key(session, "Dm")
        self.assertEqual(chart_key, "Dm")


class PageRefreshPersistenceTests(unittest.TestCase):
    def test_hydrated_backing_wins_over_stale_canonical_after_run_boundary(self) -> None:
        session: dict = {
            "_script_run_seq": 20,
            "studio_page": "backing",
            "_music_hydrated_studio_page": "backing",
            "_music_studio_page_restore_projection_complete": True,
            "_suite_page_overwrite_source": "workspace_blob",
            STUDIO_NAV_STATE_KEY: {"studio_page": "practice", "page": "practice"},
        }
        begin_script_run_navigation_markers(session)
        session["_music_studio_page_restore_projection_complete"] = True
        page = prepare_studio_nav(session)
        self.assertEqual(page, "backing")
        self.assertEqual(session.get("studio_page"), "backing")

    def test_top_level_pages_survive_refresh_hydration_matrix(self) -> None:
        pages = ("practice", "picker", "backing", "log", "creative")
        for want in pages:
            with self.subTest(page=want):
                session: dict = {
                    "_script_run_seq": 2,
                    "studio_page": want,
                    "_music_hydrated_studio_page": want,
                    "_suite_page_overwrite_source": "workspace_blob",
                    STUDIO_NAV_STATE_KEY: {"studio_page": "practice", "page": "practice"},
                }
                begin_script_run_navigation_markers(session)
                session["_music_studio_page_restore_projection_complete"] = True
                got = prepare_studio_nav(session)
                self.assertEqual(got, want)
                self.assertEqual(session.get("studio_page"), want)


class MissionGenerateExampleStabilityTests(unittest.TestCase):
    def test_generate_example_does_not_walk_sealed_chord(self) -> None:
        session = _hevenu_session()
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        gidx = global_chord_index_for_section_chord(section_map, "Melody B", "Bb7")
        assert gidx is not None
        write_authoritative_chord_selection(
            session, section_map, chord_symbol="Bb7", section_label="Melody B", chord_index=gidx
        )
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=section_map,
            mission="Target Chord Tones",
            cur_chord="Bb7",
            section_label="Melody B",
            chord_idx=gidx,
            live_inst="Guitar",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=72,
        )

        def _fake_generate(*args: Any, **kwargs: Any) -> Any:
            from improvisation_missions import MissionExample

            return MissionExample(
                mission=str(kwargs.get("mission") or ""),
                variant="normal",
                chord=str(kwargs.get("chord") or ""),
                section=str(kwargs.get("section") or ""),
                song_title=ctx.song_title,
                display_key=ctx.display_key,
                instrument="Guitar",
                level="Intermediate",
                focus="Improvisation",
                motif={"display": "test", "notes": [], "rhythm": ""},
                abc="",
                tab="",
                piano_html="",
                why="test",
                practice_steps=[],
                insight=None,
                show_tab=False,
                show_piano=False,
            )

        with patch("improvisation_missions.generate_mission_example", side_effect=_fake_generate):
            for _ in range(3):
                _run_mission_example_generate(session, "normal")
        self.assertEqual(session.get("ii_selected_chord"), "Bb7")
        self.assertEqual(int(session.get("ii_selected_chord_index")), gidx)
        snap = session.get(MISSIONS_GENERATE_CONTEXT_KEY)
        self.assertIsInstance(snap, dict)
        assert isinstance(snap, dict)
        self.assertEqual(snap.get("cur_chord"), "Bb7")


class MissionExampleBlobIndexTests(unittest.TestCase):
    def test_example_save_preserves_chord_index_on_blob(self) -> None:
        session: dict = {
            "II_SELECTED_CHORD_INDEX": 4,
            "ii_selected_chord": "Bb7",
        }
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="m1"),
        )
        save_workflow_blob(
            session,
            WorkflowStateBlob(
                workflow_owner="mission_jam",
                workflow_session_id="m1",
                selected_chord_symbol="Bb7",
                selected_chord_index=4,
                selected_section="Melody B",
            ),
        )
        update_mission_example_on_blob(
            session,
            chord="Bb7",
            example_fingerprint="abc123",
            section="Melody B",
        )
        from music_workflow_state_store import get_workflow_blob

        blob = get_workflow_blob(session, "mission_jam", "m1")
        assert blob is not None
        self.assertEqual(blob.selected_chord_symbol, "Bb7")
        self.assertEqual(blob.selected_chord_index, 4)


class SidebarKeyAfterJamTests(unittest.TestCase):
    def test_missions_sidebar_uses_song_authority_not_stale_jam_blob(self) -> None:
        session: dict = {
            "improv_intelligence_tab": "Missions",
            "active_catalog_pick_key": "hevenu",
            "display_key": "Dm",
            "concert_key": "Eb",
        }
        from music_workflow_state_store import (
            ActiveWorkflowPointer,
            KeyAuthority,
            WorkflowStateBlob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )

        set_active_workflow_pointer(session, ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="m1"))
        save_workflow_blob(
            session,
            WorkflowStateBlob(
                workflow_owner="mission_jam",
                workflow_session_id="m1",
                keys=KeyAuthority(practice_tonic="Eb", practice_mode="major"),
            ),
        )
        from sidebar_key_identity import resolve_sidebar_key_identity

        class _PK:
            practice_tonic = "D"
            practice_mode = "minor"

        with unittest.mock.patch(
            "musical_context_authority.resolve_authoritative_practice_key",
            return_value=_PK(),
        ):
            ident = resolve_sidebar_key_identity(session)
        self.assertEqual(ident.selector_token.lower(), "dm")


class DurablePageAutosaveTests(unittest.TestCase):
    def test_autosave_prefers_live_practice_over_stale_last_persisted_creative(self) -> None:
        from music_persistent_state import _resolve_live_studio_page_for_save

        session: dict = {
            "studio_page": "practice",
            "_suite_last_persisted_page": "creative",
        }
        page, source = _resolve_live_studio_page_for_save(session, save_reason="autosave")
        self.assertEqual(page, "practice")
        self.assertEqual(source, "session_state.studio_page")

    def test_disk_round_trip_preserves_practice_studio_page(self) -> None:
        from unittest.mock import MagicMock

        from music_persistent_state import apply_music_disk_state, build_music_disk_state

        ss: dict = {"studio_page": "log", "instrument": "Guitar"}
        st = MagicMock()
        st.session_state = ss
        blob = build_music_disk_state(st)
        fresh: dict = {}
        st2 = MagicMock()
        st2.session_state = fresh
        apply_music_disk_state(st2, blob, song_picker_catalog={}, song_library={})
        self.assertEqual(str(fresh.get("studio_page") or ""), "log")


class MissionReturnChainTests(unittest.TestCase):
    def test_sealed_destinations_restore_exact_mission_abc(self) -> None:
        from mission_backing_alignment import build_mission_backing_alignment_payload
        from mission_return_destination import apply_sealed_mission_return_destination, build_mission_return_destination, seal_mission_return_destination

        def _dest(letter: str, chord: str) -> dict:
            align = build_mission_backing_alignment_payload(
                {},
                mission=f"Mission {letter}",
                cur_chord=chord,
                section_label="Melody B",
                chord_idx=2,
                song_title="Tune",
            )
            return build_mission_return_destination(align, handoff_mode="mission_backing", with_practice_lick=False, request_seq=1)

        session: dict = {"studio_page": "backing"}
        for letter, chord in (("A", "Bb7"), ("B", "F#m"), ("C", "C7")):
            seal_mission_return_destination(session, _dest(letter, chord))
            with unittest.mock.patch(
                "mission_backing_alignment.apply_pending_mission_backing_alignment",
                return_value=True,
            ):
                apply_sealed_mission_return_destination(session)
            self.assertEqual(session.get("improv_active_mission"), f"Mission {letter}")
            self.assertEqual(session.get("ii_selected_chord"), chord)


class SongBlobKeyAuthorityTests(unittest.TestCase):
    def test_missions_use_song_blob_not_stale_major_display(self) -> None:
        from musical_context_authority import resolve_authoritative_practice_key
        from music_workflow_state_store import KeyAuthority, WorkflowStateBlob, save_workflow_blob

        session: dict = {
            "improv_intelligence_tab": "Missions",
            "active_catalog_pick_key": "hevenu_shalom",
            "display_key": "C",
            "concert_key": "C",
            "studio_page": "creative",
        }
        save_workflow_blob(
            session,
            WorkflowStateBlob(
                workflow_owner="song_based_improvisation",
                workflow_session_id="hevenu_shalom",
                keys=KeyAuthority(practice_tonic="D", practice_mode="minor"),
            ),
        )
        pk = resolve_authoritative_practice_key(session)
        self.assertEqual(pk.practice_mode, "minor")
        self.assertEqual(pk.practice_key_token.lower(), "dm")
        self.assertEqual(pk.source, "song_based_blob_practice_key")


class MissionProgressionCollapseGuardTests(unittest.TestCase):
    def test_mission_chord_select_does_not_collapse_full_progression(self) -> None:
        import copy

        from active_musical_workflow_envelope import apply_atomic_mission_chord_selection
        from improvisation_motif import flatten_section_map, resolve_improv_sections
        from music_workflow_state_store import (
            ActiveWorkflowPointer,
            KeyAuthority,
            WorkflowStateBlob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )

        sections = {
            "Melody A": ["Cm", "G7", "Cm", "Fm", "Bb", "Eb", "Ab", "D"],
            "Melody B": ["Cm", "G7", "Bb7", "Fm", "Bb", "Eb", "Ab", "D"],
        }
        session: dict = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "active_catalog_pick_key": "hevenu_shalom",
            "song": "Hevenu Shalom Aleichem",
            "display_key": "Dm",
            "concert_key": "Dm",
            "improv_song_concert_sections": copy.deepcopy(sections),
            "home_sections": copy.deepcopy(sections),
            "improv_mission_progression": ["Cm"],
            "improv_mission_chord_options": ["Cm"],
        }
        save_workflow_blob(
            session,
            WorkflowStateBlob(
                workflow_owner="song_based_improvisation",
                workflow_session_id="hevenu_shalom",
                keys=KeyAuthority(practice_tonic="D", practice_mode="minor"),
                section_map=copy.deepcopy(sections),
            ),
        )
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="hevenu_shalom"),
        )
        save_workflow_blob(
            session,
            WorkflowStateBlob(
                workflow_owner="mission_jam",
                workflow_session_id="hevenu_shalom",
                keys=KeyAuthority(practice_tonic="D", practice_mode="minor"),
                section_map={"Melody A": ["Cm"]},
                selected_chord_symbol="Cm",
                selected_section="Melody A",
                selected_chord_index=0,
            ),
        )
        ctx = _hevenu_ctx()
        apply_atomic_mission_chord_selection(
            session,
            chord="Fm",
            section="Melody A",
            chord_index=3,
            chord_label="Melody A · Fm",
        )
        section_map = resolve_improv_sections(session, ctx)
        flat = flatten_section_map(section_map) if section_map else []
        self.assertGreater(len(flat), 1)
        self.assertIn("Fm", flat)
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "Fm")


class MissionGenerateAuthoritativeChordTests(unittest.TestCase):
    def test_generate_uses_authoritative_chord_over_stale_sealed_snap(self) -> None:
        session = _hevenu_session()
        session["improv_mission_pick"] = "Develop one motif for the entire solo"
        session["improv_active_mission"] = session["improv_mission_pick"]
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        gidx = global_chord_index_for_section_chord(section_map, "Melody A", "F#m")
        assert gidx is not None
        write_authoritative_chord_selection(
            session, section_map, chord_symbol="F#m", section_label="Melody A", chord_index=gidx
        )
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=section_map,
            mission=str(session["improv_mission_pick"]),
            cur_chord="C#m",
            section_label="Melody A",
            chord_idx=0,
            live_inst="Guitar",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=72,
        )
        seen: dict[str, str] = {}

        def _fake_generate(*args: Any, **kwargs: Any) -> Any:
            seen["chord"] = str(kwargs.get("chord") or "")
            from improvisation_missions import MissionExample

            return MissionExample(
                mission=str(kwargs.get("mission") or ""),
                variant="normal",
                chord=seen["chord"],
                section=str(kwargs.get("section") or ""),
                song_title=ctx.song_title,
                display_key=ctx.display_key,
                instrument="Guitar",
                level="Intermediate",
                focus="Improvisation",
                motif={"display": "test", "notes": [], "rhythm": ""},
                abc="",
                tab="",
                piano_html="",
                why="test",
                practice_steps=[],
                insight=None,
                show_tab=False,
                show_piano=False,
            )

        with patch("improvisation_missions.generate_mission_example", side_effect=_fake_generate):
            _run_mission_example_generate(session, "normal")
        self.assertEqual(seen.get("chord"), "F#m")


class GenericBackingEntryTests(unittest.TestCase):
    def test_generic_backing_entry_releases_mission_context(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from backing_source_navigation import hydrate_backing_source_for_page, mark_generic_catalog_backing_entry
        from music_source_ownership import intentional_creative_backing_active

        session: dict = {
            "studio_page": "backing",
            "active_catalog_pick_key": "Pop::Test",
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id="pick",
                song_title="T",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=100,
                style="Pop",
                groove="Straight",
                mission_id="Mission A",
            ),
        )
        mark_generic_catalog_backing_entry(session)
        with unittest.mock.patch("music_source_ownership.reconcile_source_ownership", return_value=True):
            hydrate_backing_source_for_page(session)
        self.assertFalse(intentional_creative_backing_active(session))


if __name__ == "__main__":
    unittest.main()
