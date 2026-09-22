"""Regressions for origin/dev Missions / owner-key stabilization."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from music_theory import coerce_key_to_mode, display_key_options, transpose_chord
from song_catalog.catalog import format_pick_key
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)


SLOW = format_pick_key("Pop", "Slow Dancing in a Burning Room — John Mayer")
PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")


def _slow_session(**extra) -> dict:
    session = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "creative_improv_intelligence_tab": "Missions",
        "improv_entry_mode": "Song-Based Improvisation",
        "active_catalog_pick_key": SLOW,
        "active_music_source": "catalog",
        "selected_song": {
            "title": "Slow Dancing in a Burning Room",
            "artist": "John Mayer",
            "key": "C#m",
            "pick_key": SLOW,
        },
        "original_key": "C#m",
        "display_key": "C#m",
        "concert_key": "C#m",
        PRACTICE_KEY_BY_SOURCE_KEY: {},
    }
    session.update(extra)
    return session


class CSharpMinorNotCMinorTests(unittest.TestCase):
    def test_options_keep_c_sharp_minor(self) -> None:
        opts = display_key_options("C#m")
        self.assertIn("C#m", opts)
        self.assertNotEqual(opts[0], "Cm")

    def test_coerce_does_not_strip_sharp(self) -> None:
        self.assertEqual(coerce_key_to_mode("C#m", "minor"), "C#m")
        self.assertEqual(coerce_key_to_mode("D#m", "minor"), "D#m")
        self.assertEqual(coerce_key_to_mode("Em", "minor"), "Em")

    def test_missions_initial_pk_uses_original_not_leftover_cm(self) -> None:
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        session = _slow_session(display_key="Cm", concert_key="Cm")
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(token, "C#m")
        self.assertNotEqual(str(session.get("display_key") or session.get("concert_key")), "Cm")


class MissionPracticeKeyCommitTests(unittest.TestCase):
    def test_mission_sidebar_commit_writes_pick_store_atomically(self) -> None:
        from creative_key_sync import (
            canonical_mission_practice_key,
            commit_mission_sidebar_practice_key,
            prepare_mission_backing_practice_key_widget,
        )
        from music_theory import display_key_options
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        session = _slow_session(display_key_mission_backing="D#m")
        committed = commit_mission_sidebar_practice_key(session, "D#m")
        self.assertEqual(committed, "D#m")
        self.assertEqual(get_practice_concert_key(session, SLOW), "D#m")
        self.assertEqual(session.get("_pk_user_commit_token"), "D#m")
        self.assertEqual(session.get("_pk_user_commit_pick"), SLOW)
        self.assertEqual(canonical_mission_practice_key(session), "D#m")
        self.assertNotEqual(session.get("original_key"), "D#m")
        self.assertEqual(session.get("original_key"), "C#m")

        session["display_key"] = "C#m"
        session["concert_key"] = "C#m"
        opts = display_key_options("C#m")
        want = prepare_mission_backing_practice_key_widget(session, options=opts)
        self.assertEqual(want, "D#m")
        self.assertEqual(session.get("display_key_mission_backing"), "D#m")
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(token, "D#m")
        self.assertEqual(get_practice_concert_key(session, SLOW), "D#m")

    def test_mark_display_key_changed_reads_mission_widget_not_stale_display_key(self) -> None:
        from songs.key_state import mark_display_key_changed

        session = _slow_session()
        session["display_key"] = "C#m"
        session["concert_key"] = "C#m"
        session["display_key_mission_backing"] = "D#m"
        st_like = SimpleNamespace(session_state=session)
        mark_display_key_changed(st_like)
        self.assertEqual(get_practice_concert_key(session, SLOW), "D#m")
        self.assertEqual(session.get("_pk_user_commit_token"), "D#m")
        self.assertEqual(session.get("_pk_user_commit_pick"), SLOW)

    def test_slow_dancing_open_stays_original_csharp_without_user_commit(self) -> None:
        from creative_key_sync import (
            canonical_mission_practice_key,
            prepare_mission_backing_practice_key_widget,
        )
        from music_theory import display_key_options
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        session = _slow_session()
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(token, "C#m")
        self.assertEqual(canonical_mission_practice_key(session) or token, "C#m")
        want = prepare_mission_backing_practice_key_widget(
            session, options=display_key_options("C#m")
        )
        self.assertEqual(want, "C#m")
        self.assertEqual(session.get("original_key"), "C#m")

    def test_prepare_does_not_reset_user_dsharp_to_original(self) -> None:
        from creative_key_sync import prepare_mission_backing_practice_key_widget
        from music_theory import display_key_options

        session = _slow_session(
            display_key_mission_backing="D#m",
            improv_mission_concert_key="C#m",
            _pk_user_commit_token="D#m",
            _pk_user_commit_pick=SLOW,
        )
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {SLOW: "D#m"}
        want = prepare_mission_backing_practice_key_widget(
            session, options=display_key_options("C#m")
        )
        self.assertEqual(want, "D#m")
        self.assertEqual(session.get("display_key_mission_backing"), "D#m")
        self.assertEqual(session.get("original_key"), "C#m")

    def test_user_dsharp_and_e_minor_outrank_original_hydrate(self) -> None:
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        session = _slow_session()
        set_practice_concert_key(
            session,
            "D#m",
            pick_key=SLOW,
            allow_restore_original=True,
            commit_catalog_practice_key=True,
        )
        session["_pk_user_commit_token"] = "D#m"
        session["_pk_user_commit_pick"] = SLOW
        session["display_key"] = "D#m"
        session["concert_key"] = "D#m"
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(token, "D#m")
        self.assertEqual(get_practice_concert_key(session, SLOW), "D#m")

        session["_pk_user_commit_token"] = "Em"
        session["display_key"] = "Em"
        session["concert_key"] = "Em"
        set_practice_concert_key(
            session,
            "Em",
            pick_key=SLOW,
            allow_restore_original=True,
            commit_catalog_practice_key=True,
        )
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(token, "Em")
        self.assertEqual(get_practice_concert_key(session, SLOW), "Em")

    def test_perfect_e_major_commits_from_missions(self) -> None:
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        session = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "creative_improv_intelligence_tab": "Missions",
            "active_catalog_pick_key": PERFECT,
            "selected_song": {"title": "Perfect", "artist": "Ed Sheeran", "key": "G", "pick_key": PERFECT},
            "original_key": "G",
            "display_key": "E",
            "concert_key": "E",
            PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT: "Eb"},
            "_pk_user_commit_token": "E",
            "_pk_user_commit_pick": PERFECT,
        }
        set_practice_concert_key(
            session,
            "E",
            pick_key=PERFECT,
            allow_restore_original=True,
            commit_catalog_practice_key=True,
        )
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(get_practice_concert_key(session, PERFECT), "E")
        self.assertIn(token, {"E", "Eb"})
        self.assertEqual(str(session.get("_pk_user_commit_token")), "E")

    def test_user_commit_outranks_live_original_before_widget_updates(self) -> None:
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        session = _slow_session()
        session["_pk_user_commit_token"] = "D#m"
        session["_pk_user_commit_pick"] = SLOW
        session["display_key"] = "C#m"
        session["concert_key"] = "C#m"
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(token, "D#m")
        pending = str(session.get("_pending_display_key") or session.get("display_key") or "")
        self.assertTrue(pending.startswith("D#") or token == "D#m", pending)

    def test_apply_display_key_keeps_user_commit_over_original(self) -> None:
        from songs.key_state import IDENTITY_KEY, apply_display_key_for_active_song, song_display_identity

        session = _slow_session()
        session["_pk_user_commit_token"] = "D#m"
        session["_pk_user_commit_pick"] = SLOW
        session["display_key"] = "D#m"
        session["concert_key"] = "D#m"
        ident = song_display_identity(
            "Slow Dancing in a Burning Room",
            "John Mayer",
            "C#m",
            pick_key=SLOW,
        )
        session[IDENTITY_KEY] = ident
        st_like = SimpleNamespace(session_state=session)
        apply_display_key_for_active_song(st_like, "C#m", ident)
        live = str(session.get("display_key") or session.get("_pending_display_key") or "")
        self.assertTrue(live.startswith("D#"), live)


class MinorTransposeTests(unittest.TestCase):
    def test_slow_dancing_family_transposes(self) -> None:
        progression = ["C#m", "A", "E", "B"]
        dsharp = [transpose_chord(ch, 2, reference_key="D#m") for ch in progression]
        em = [transpose_chord(ch, 3, reference_key="Em") for ch in progression]
        self.assertEqual(dsharp, ["D#m", "B", "F#", "C#"])
        self.assertEqual(em, ["Em", "C", "G", "D"])


class MissionChordCallbackTests(unittest.TestCase):
    def test_handle_user_mission_target_selection_updates_target(self) -> None:
        from creative_mission_config_persistence import handle_user_mission_target_selection

        session = _slow_session(
            improv_active_mission="Resolve every phrase on beat 1",
            ii_selected_chord="C#m",
            ii_selected_section="Verse",
            ii_selected_chord_index=0,
            improv_mission_chord_options=["C#m", "A", "E", "B"],
        )
        handle_user_mission_target_selection(
            session,
            chord="A",
            section="Chorus",
            chord_index=5,
            chord_label="Chorus · A",
            button_key="ii_chord_tile_chorus_5_A",
        )
        self.assertEqual(session.get("ii_selected_chord"), "A")
        self.assertEqual(session.get("ii_selected_section"), "Chorus")
        self.assertEqual(int(session.get("ii_selected_chord_index") or -1), 5)
        auth = session.get("_mission_chord_click_authority") or {}
        self.assertEqual(auth.get("chord"), "A")
        self.assertEqual(str(session.get("display_key")), "C#m")

    def test_mission_backing_consume_heals_leftover_legacy_owner(self) -> None:
        from music_workflow_activation import activate_workflow_simple
        from music_workflow_state_store import (
            ActiveWorkflowPointer,
            KeyAuthority,
            WorkflowStateBlob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        session = _slow_session(
            display_key="Em",
            concert_key="Em",
            ii_selected_chord="Em",
            ii_selected_section="Chorus",
            song="Slow Dancing in a Burning Room",
        )
        session[ACTIVE_WORKFLOW_OWNER_KEY] = "mission_jam"
        song_blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=SLOW,
            source_type="catalog",
            song_id=SLOW,
            keys=KeyAuthority(
                original_tonic="C#",
                original_mode="minor",
                practice_tonic="E",
                practice_mode="minor",
                key_owner="song_based_improvisation",
            ),
        )
        save_workflow_blob(session, song_blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(
                workflow_owner="song_based_improvisation",
                workflow_session_id=SLOW,
                context_revision=1,
                activation_source="test",
            ),
            source="test",
        )
        result = activate_workflow_simple(
            session,
            "mission_jam",
            activation_source="pending_backing_consume",
            page_route="backing",
            return_route="creative",
            navigation_intent="backing_open",
            persist_policy="durable_handoff",
        )
        self.assertTrue(
            result.ok,
            msg=f"{result.error_code} {result.trace.get('canonical_identity_violations')}",
        )


class MissionReturnRejectsPerfectTests(unittest.TestCase):
    def test_return_restores_slow_dancing_pick_not_perfect(self) -> None:
        from mission_backing_alignment import build_mission_backing_alignment_payload
        from music_workflow_pending_mission_return import _apply_return_destination_session_fields

        session = _slow_session(
            studio_page="backing",
            improv_active_mission="Resolve every phrase on beat 1",
            ii_selected_chord="C#m",
            ii_selected_section="Verse",
            ii_selected_chord_index=0,
        )
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {PERFECT: "C", SLOW: "C#m"}
        dest = build_mission_backing_alignment_payload(
            session,
            mission="Resolve every phrase on beat 1",
            cur_chord="C#m",
            section_label="Verse",
            chord_idx=0,
            song_title="Slow Dancing in a Burning Room",
            song_pick_key=SLOW,
            concert_key="C#m",
            display_key="C#m",
        )
        session["active_catalog_pick_key"] = PERFECT
        session["selected_song"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "key": "G",
            "pick_key": PERFECT,
        }
        session["display_key"] = "C"
        _apply_return_destination_session_fields(session, dest)
        self.assertEqual(str(session.get("active_catalog_pick_key")), SLOW)
        selected = session.get("selected_song") or {}
        self.assertNotEqual(str(selected.get("title") or ""), "Perfect")
        self.assertIn("Slow Dancing", str(selected.get("title") or dest.get("song_title") or ""))
        self.assertEqual(str(dest.get("catalog_song_id") or dest.get("song_pick_key")), SLOW)
        self.assertEqual(str(dest.get("creative_tab") or ""), "Missions")
        self.assertEqual(str(session.get("ii_selected_section")), "Verse")
        self.assertEqual(str(session.get("ii_selected_chord")), "C#m")
        self.assertNotEqual(str(get_practice_concert_key(session, SLOW) or ""), "C")


class MissionChordWidgetIdentityTests(unittest.TestCase):
    def test_source_id_uses_catalog_pick_not_title(self) -> None:
        from improvisation_intelligence_ui import _improv_source_id
        from improvisation_intelligence import ImprovSessionContext

        session = _slow_session()
        ctx = ImprovSessionContext(
            song_title="Perfect",
            artist="Ed Sheeran",
            key_center="G",
            display_key="C",
            instrument="Piano",
            level="Beginner",
            focus="Harmony",
            sections={"Verse": ["G"]},
        )
        sid = _improv_source_id(session, ctx)
        from improvisation_intelligence_ui import _safe_widget_key_part

        self.assertEqual(sid, _safe_widget_key_part(SLOW))
        self.assertNotIn("Perfect", sid)


class ChangeRhythmAndMeterTests(unittest.TestCase):
    def test_five_quarters_split_across_two_4_4_measures(self) -> None:
        from improvisation_motif import abc_body_measures, abc_measure_beats, build_motif_abc

        motif = {
            "chord": "Cm7",
            "notes": ["C", "Eb", "G", "Bb", "C"],
            "midi": [60, 63, 67, 70, 72],
            "meter": "4/4",
            "rhythm_symbols": ["♩", "♩", "♩", "♩", "♩"],
            "rhythm": "♩ ♩ ♩ ♩ ♩",
        }
        abc = build_motif_abc(motif, key_center="Cm", title="Mission")
        measures = abc_body_measures(abc)
        self.assertGreaterEqual(len(measures), 2)
        self.assertAlmostEqual(abc_measure_beats(measures[0]), 4.0, places=2)
        self.assertLessEqual(abc_measure_beats(measures[1]), 4.0)
        self.assertGreaterEqual(abc_measure_beats(measures[1]), 1.0)

    def test_change_rhythm_keeps_pitches_and_changes_durations(self) -> None:
        from improvisation_motif import cycle_motif_rhythm

        motif = {
            "chord": "Cm7",
            "notes": ["C", "Eb", "G", "Bb", "C"],
            "midi": [60, 63, 67, 70, 72],
            "meter": "4/4",
            "rhythm_symbols": ["♩", "♩", "♩", "♩", "♩"],
            "rhythm": "♩ ♩ ♩ ♩ ♩",
        }
        out = cycle_motif_rhythm(motif, meter="4/4")
        self.assertEqual(list(out.get("notes") or []), motif["notes"])
        self.assertNotEqual(list(out.get("rhythm_symbols") or []), ["♩", "♩", "♩", "♩", "♩"])

    def test_cycle_six_quarters_changes_durations(self) -> None:
        from improvisation_motif import cycle_motif_rhythm

        motif = {
            "chord": "Em",
            "notes": ["G", "E", "G", "B", "G", "G"],
            "midi": [67, 64, 67, 71, 67, 67],
            "meter": "4/4",
            "rhythm_symbols": ["♩", "♩", "♩", "♩", "♩", "♩"],
            "rhythm": "♩ ♩ ♩ ♩ ♩ ♩",
        }
        out = cycle_motif_rhythm(motif, meter="4/4")
        self.assertEqual(list(out.get("notes") or []), motif["notes"])
        self.assertNotEqual(list(out.get("rhythm_symbols") or []), ["♩", "♩", "♩", "♩", "♩", "♩"])


class GenerateAfterMissionReturnTests(unittest.TestCase):
    def test_artist_suffix_does_not_hide_generated_example(self) -> None:
        from improvisation_intelligence import ImprovSessionContext
        from improvisation_intelligence_ui import _example_matches_active_context
        from improvisation_missions import generate_mission_example

        ctx = ImprovSessionContext(
            song_title="Slow Dancing in a Burning Room",
            artist="John Mayer",
            key_center="Em",
            display_key="Em",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["Em", "G", "D", "C"]},
        )
        example = generate_mission_example(
            "Resolve every phrase on beat 1",
            improv_ctx=ctx,
            chord="Em",
            section="Verse",
            level="Intermediate",
            instrument="Piano",
            focus="Improvisation",
        )
        self.assertTrue(list((example.motif or {}).get("notes") or []))
        self.assertTrue(str((example.motif or {}).get("rhythm") or "").strip())
        self.assertTrue(
            _example_matches_active_context(
                example,
                mission="Resolve every phrase on beat 1",
                cur_chord="Em",
                section_label="Verse",
                song_title="Slow Dancing in a Burning Room — John Mayer",
            )
        )

    def test_generate_after_return_fields_keeps_canonical_phrase(self) -> None:
        from improvisation_intelligence import ImprovSessionContext
        from improvisation_intelligence_ui import (
            _run_mission_example_generate,
            _stash_missions_generate_context,
        )
        from improvisation_missions import MISSION_EXAMPLE_KEY
        from music_workflow_pending_mission_return import _apply_return_destination_session_fields

        session = _slow_session(
            display_key="Em",
            concert_key="Em",
            song="Slow Dancing in a Burning Room",
            artist="John Mayer",
            improv_active_mission="Resolve every phrase on beat 1",
            improv_mission_pick="Resolve every phrase on beat 1",
            ii_selected_chord="Em",
            ii_selected_section="Verse",
            ii_selected_chord_index=0,
            home_sections={"Verse": ["Em", "G", "D", "C"]},
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
        )
        dest = {
            "mission_id": "Resolve every phrase on beat 1",
            "destination_page": "creative",
            "creative_tab": "Missions",
            "song_pick_key": SLOW,
            "song_title": "Slow Dancing in a Burning Room",
            "section_label": "Verse",
            "chord_symbol": "Em",
            "chord_index": 0,
            "display_key": "Em",
            "concert_key": "Em",
            "original_key": "C#m",
        }
        _apply_return_destination_session_fields(session, dest)
        ctx = ImprovSessionContext(
            song_title="Slow Dancing in a Burning Room",
            artist="John Mayer",
            key_center="Em",
            display_key="Em",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["Em", "G", "D", "C"]},
        )
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=[("Verse", ["Em", "G", "D", "C"])],
            mission="Resolve every phrase on beat 1",
            cur_chord="Em",
            section_label="Verse",
            chord_idx=0,
            live_inst="Piano",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=100,
        )
        _run_mission_example_generate(session, "normal")
        raw = session.get(MISSION_EXAMPLE_KEY)
        self.assertIsInstance(raw, dict)
        motif = (raw or {}).get("motif") or {}
        notes = list(motif.get("notes") or [])
        rhythm = str(motif.get("rhythm") or "")
        self.assertGreaterEqual(len(notes), 5, msg=f"diag={session.get('_mission_example_gen_diag')}")
        self.assertTrue(rhythm.strip())
        self.assertEqual(str(raw.get("chord") or ""), "Em")
        self.assertEqual(str(raw.get("section") or ""), "Verse")
        self.assertEqual(str(session.get("improv_mission_pick") or ""), "Resolve every phrase on beat 1")

    def test_beat1_generate_is_five_quarters_split_across_bars(self) -> None:
        from improvisation_intelligence import ImprovSessionContext
        from improvisation_missions import generate_mission_example
        from improvisation_motif import abc_body_measures, abc_measure_beats

        ctx = ImprovSessionContext(
            song_title="Slow Dancing in a Burning Room",
            artist="John Mayer",
            key_center="Em",
            display_key="Em",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["Em"]},
        )
        example = generate_mission_example(
            "Resolve every phrase on beat 1",
            improv_ctx=ctx,
            chord="Em",
            section="Verse",
            level="Intermediate",
            instrument="Piano",
            focus="Improvisation",
        )
        notes = list((example.motif or {}).get("notes") or [])
        symbols = list((example.motif or {}).get("rhythm_symbols") or [])
        self.assertEqual(len(notes), 5)
        self.assertEqual(symbols, ["♩", "♩", "♩", "♩", "♩"])
        self.assertTrue(str(example.abc or "").startswith("X:1"))
        measures = abc_body_measures(example.abc)
        self.assertGreaterEqual(len(measures), 2)
        self.assertAlmostEqual(abc_measure_beats(measures[0]), 4.0, places=2)
        self.assertAlmostEqual(abc_measure_beats(measures[1]), 4.0, places=2)


class ReturnToMissionIconTests(unittest.TestCase):
    def test_label_uses_flag_icon(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from backing_nav_actions import build_backing_nav_actions
        from music_feature_icons import FEATURE_ICONS

        session = _slow_session(studio_page="backing")
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            song_title="Slow Dancing in a Burning Room",
            active_song_id=SLOW,
            bound_pick_key=SLOW,
            mission_id="Resolve every phrase on beat 1",
            key="C#m",
            display_key="C#m",
            concert_key="C#m",
            bpm=96,
            style="",
            groove="",
        )
        set_backing_context(session, ctx)
        actions, _ = build_backing_nav_actions(session)
        labels = [a.label for a in actions if a.action_id == "return_mission"]
        self.assertTrue(labels)
        self.assertTrue(any("Return to Mission" in lab for lab in labels))
        self.assertTrue(any(FEATURE_ICONS["mission"] in lab for lab in labels))

    def test_return_destination_keeps_slow_dancing_em_chord(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from mission_return_destination import (
            MISSION_CANONICAL_RETURN_DESTINATION_KEY,
            peek_mission_return_destination,
            recover_mission_return_destination_from_backing_session,
            seal_mission_return_destination,
        )

        session = _slow_session(
            studio_page="backing",
            display_key="Em",
            concert_key="Em",
            ii_selected_chord="G",
            ii_selected_section="Chorus",
            improv_active_mission="Resolve every phrase on beat 1",
        )
        dest = {
            "mission_id": "Resolve every phrase on beat 1",
            "destination_page": "creative",
            "creative_tab": "Missions",
            "song_pick_key": SLOW,
            "section_label": "Chorus",
            "chord_symbol": "G",
            "display_key": "Em",
            "concert_key": "Em",
        }
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            song_title="Slow Dancing in a Burning Room",
            active_song_id=SLOW,
            bound_pick_key=SLOW,
            mission_id="Resolve every phrase on beat 1",
            key="Em",
            display_key="Em",
            concert_key="Em",
            bpm=96,
            style="",
            groove="",
        )
        set_backing_context(session, ctx)
        seal_mission_return_destination(session, dest)
        live = peek_mission_return_destination(session)
        self.assertIsNotNone(live)
        assert live is not None
        self.assertEqual(live.get("song_pick_key"), SLOW)
        self.assertEqual(live.get("display_key"), "Em")
        self.assertEqual(live.get("chord_symbol"), "G")
        self.assertEqual(live.get("section_label"), "Chorus")
        self.assertNotIn("Perfect", str(live))
        session.pop(MISSION_CANONICAL_RETURN_DESTINATION_KEY, None)
        recovered = recover_mission_return_destination_from_backing_session(session)
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertEqual(recovered.get("song_pick_key"), SLOW)
        self.assertEqual(str(recovered.get("display_key") or recovered.get("concert_key")), "Em")
        self.assertNotIn("Perfect", str(recovered))



class CustomQuickKeyRemovedTests(unittest.TestCase):
    def test_cpl_page_has_no_quick_major_grid(self) -> None:
        from pathlib import Path

        text = Path("cpl_page_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("cpl_orig_chip_", text)
        self.assertIn("Choose the Original Key, then Save to library.", text)


if __name__ == "__main__":
    unittest.main()
