"""Human-acceptance music-theory and owner-isolation regressions."""

from __future__ import annotations

import unittest

from backing_key_cycle import (
    apply_backing_key_cycle,
    cycle_concert_practice_key,
    default_spelling_prefs,
)
from improvisation_motif import (
    _max_leap,
    _shift_phrase_into_bounds,
    build_motif_pattern,
    generate_motif_for_chord,
    transform_motif,
)
from instrument_transposition import written_key_for_type
from mission_projection_state import display_chord_from_concert
from music_theory import split_key_center
from song_catalog.catalog import format_pick_key


SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")


class TestDiatonicSequence(unittest.TestCase):
    def test_sequence_down_d_minor_one_degree(self) -> None:
        motif = {
            "chord": "Dm",
            "notes": ["D", "F", "A"],
            "midi": [62, 65, 69],
        }
        out = transform_motif(motif, "sequence_down", key_center="Dm")
        self.assertEqual(out["notes"], ["C", "E", "G"])
        midis = [int(m) for m in out["midi"]]
        self.assertEqual(len(midis), 3)
        for a, b in zip(midis, midis[1:]):
            self.assertLess(b, a + 12)
        # Whole contour moved down — no isolated octave wrap.
        self.assertEqual([m - midis[0] for m in midis], [0, 4, 7])

    def test_sequence_up_d_minor_one_degree(self) -> None:
        motif = {
            "chord": "Dm",
            "notes": ["D", "F", "A"],
            "midi": [62, 65, 69],
        }
        out = transform_motif(motif, "sequence_up", key_center="Dm")
        self.assertEqual(out["notes"], ["E", "G", "Bb"])
        midis = [int(m) for m in out["midi"]]
        self.assertEqual([m - midis[0] for m in midis], [0, 3, 6])

    def test_sequence_up_c_major_one_degree(self) -> None:
        motif = {"chord": "C", "notes": ["C", "E", "G"], "midi": [60, 64, 67]}
        out = transform_motif(motif, "sequence_up", key_center="C")
        self.assertEqual(out["notes"], ["D", "F", "A"])

    def test_sequence_down_c_major_one_degree(self) -> None:
        motif = {"chord": "C", "notes": ["C", "E", "G"], "midi": [60, 64, 67]}
        out = transform_motif(motif, "sequence_down", key_center="C")
        self.assertEqual(out["notes"], ["B", "D", "F"])
        midis = [int(m) for m in out["midi"]]
        self.assertLess(midis[0], 60)  # B below C, not B an octave up


class TestOctavePolicy(unittest.TestCase):
    def test_whole_phrase_shift_not_individual_wrap(self) -> None:
        too_low = [41, 38, 36, 34]  # below F3
        shifted = _shift_phrase_into_bounds(too_low)
        self.assertGreaterEqual(min(shifted), 53)
        self.assertEqual([b - a for a, b in zip(too_low, too_low[1:])], [b - a for a, b in zip(shifted, shifted[1:])])

    def test_descending_pattern_no_mid_phrase_octave_jump(self) -> None:
        motif = {
            "chord": "F",
            "notes": ["F", "G", "A", "C"],
            "midi": [65, 67, 69, 72],
        }
        pat = build_motif_pattern(
            motif,
            key_center="F",
            pattern_type="diatonic",
            direction="descending",
            length=8,
        )
        self.assertEqual(pat.get("pattern_direction"), "descending")
        self.assertEqual(pat["cells"][0], ["F", "G", "A", "C"])
        self.assertEqual(pat["cells"][1][0], "E")
        midis = [int(m) for m in pat.get("midi") or []]
        cell_len = 4
        for i in range(1, 8):
            prev = midis[(i - 1) * cell_len]
            cur = midis[i * cell_len]
            self.assertLess(cur, prev, msg=f"cell start {i}: {prev} -> {cur}")
        leaps = [midis[i] - midis[i - 1] for i in range(1, len(midis))]
        self.assertFalse(any(leap >= 11 for leap in leaps), msg=leaps)

    def test_generated_motif_no_isolated_octave_restart(self) -> None:
        motif = generate_motif_for_chord("F", key_center="F", level="Intermediate")
        midis = [int(m) for m in motif.get("midi") or []]
        self.assertEqual(len(midis), len(motif.get("notes") or []))
        self.assertLessEqual(_max_leap(midis), 12)


class TestConcertWrittenProjection(unittest.TestCase):
    def test_alto_cm_writes_am(self) -> None:
        self.assertEqual(written_key_for_type("Cm", "Alto saxophone (Eb)"), "Am")

    def test_concert_dm_written_bm_for_cm_to_am(self) -> None:
        shown = display_chord_from_concert("Dm", concert_key="Cm", chart_key="Am")
        self.assertEqual(shown, "Bm")

    def test_written_off_keeps_concert_chord(self) -> None:
        shown = display_chord_from_concert("Dm", concert_key="Cm", chart_key="Cm")
        self.assertEqual(shown, "Dm")


class TestKeyCycle(unittest.TestCase):
    def test_semitone_up_preserves_minor(self) -> None:
        prefs = default_spelling_prefs()
        self.assertEqual(cycle_concert_practice_key("C", semitones=1, spelling_prefs=prefs), "Db")
        self.assertEqual(cycle_concert_practice_key("Cm", semitones=1, spelling_prefs=prefs), "Dbm")

    def test_whole_tone_up_and_down(self) -> None:
        prefs = default_spelling_prefs()
        self.assertEqual(cycle_concert_practice_key("C", semitones=2, spelling_prefs=prefs), "D")
        self.assertEqual(cycle_concert_practice_key("C", semitones=-2, spelling_prefs=prefs), "Bb")

    def test_user_spelling_c_sharp_not_normalized_to_db(self) -> None:
        prefs = default_spelling_prefs()
        prefs["C#/Db"] = "C#"
        self.assertEqual(cycle_concert_practice_key("C", semitones=1, spelling_prefs=prefs), "C#")
        self.assertEqual(cycle_concert_practice_key("Cm", semitones=1, spelling_prefs=prefs), "C#m")

    def test_jam_cycle_does_not_mutate_catalog_shape(self) -> None:
        from backing_context import BackingContext, set_backing_context

        session = {
            "studio_page": "backing",
            "display_key": "F",
            "concert_key": "F",
            "improv_style_key": "F",
            "improv_entry_mode": "Style Jam Mode",
            "active_catalog_pick_key": SHAPE_PICK,
            "practice_key_by_source": {SHAPE_PICK: "Cm"},
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": SHAPE_PICK},
        }
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Entry Style Jam",
                active_song_id="jam-test",
                entry_mode="Style Jam Mode",
                song_title="Style Jam",
                key="F",
                display_key="F",
                concert_key="F",
                bpm=100,
                style="Pop",
                groove="Pop groove",
            ),
        )
        apply_backing_key_cycle(session, semitones=1)
        self.assertEqual(session.get("practice_key_by_source", {}).get(SHAPE_PICK), "Cm")
        _, mode = split_key_center(str(session.get("improv_style_key") or session.get("display_key") or ""))
        self.assertEqual(mode, "major")


class TestSongPracticeModeHeal(unittest.TestCase):
    def test_blob_default_major_does_not_win_over_live_minor(self) -> None:
        from music_workflow_song_practice import resolve_song_practice_key_token
        from music_workflow_state_store import KeyAuthority, WorkflowStateBlob, save_workflow_blob

        session = {
            "active_catalog_pick_key": SHAPE_PICK,
            "display_key": "Cm",
            "concert_key": "Cm",
        }
        blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=SHAPE_PICK,
            source_type="catalog",
            song_id=SHAPE_PICK,
            keys=KeyAuthority(
                original_tonic="C",
                original_mode="major",
                practice_tonic="C",
                practice_mode="major",
                key_owner="song_based_improvisation",
            ),
        )
        save_workflow_blob(session, blob, source="test")
        self.assertEqual(resolve_song_practice_key_token(session), "Cm")


class TestStyleJamLeftoverJamKey(unittest.TestCase):
    def test_style_jam_f_is_not_stolen_by_leftover_jam_generator_eb(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import creative_entry_concert_key, prepare_creative_sidebar_display_key
        from types import SimpleNamespace

        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "F",
            "improv_jam_key": "Eb",
            "display_key": "Eb",
            "concert_key": "Eb",
        }
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Entry Style Jam",
                active_song_id="jam-style",
                entry_mode="Style Jam Mode",
                song_title="Style Jam",
                key="F",
                display_key="F",
                concert_key="F",
                bpm=100,
                style="Pop",
                groove="Pop groove",
            ),
        )
        self.assertEqual(creative_entry_concert_key(session), "F")
        st = SimpleNamespace(session_state=session)
        prepare_creative_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "F")
        self.assertEqual(session.get("improv_style_key"), "F")

    def test_jam_backing_refresh_does_not_restore_custom_d(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import prepare_backing_context_sidebar_display_key
        from types import SimpleNamespace

        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "F",
            "display_key": "D",
            "concert_key": "D",
            "active_catalog_pick_key": SHAPE_PICK,
            "practice_key_by_source": {SHAPE_PICK: "Cm"},
        }
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Entry Style Jam",
                active_song_id="jam-style",
                entry_mode="Style Jam Mode",
                song_title="Style Jam",
                key="F",
                display_key="F",
                concert_key="F",
                bpm=110,
                style="Bossa Nova",
                groove="Bossa nova",
            ),
        )
        st = SimpleNamespace(session_state=session)
        prepare_backing_context_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "F")
        self.assertEqual(session.get("improv_style_key"), "F")
        self.assertNotEqual(session.get("display_key"), "D")


class TestMissionsSavedCatalogKey(unittest.TestCase):
    def test_saved_cm_wins_over_live_original_bm(self) -> None:
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated
        from songs.practice_key_state import set_practice_concert_key

        session = {
            "studio_page": "creative",
            "active_catalog_pick_key": SHAPE_PICK,
            "display_key": "Bm",
            "concert_key": "Bm",
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": SHAPE_PICK},
        }
        set_practice_concert_key(session, "Cm", pick_key=SHAPE_PICK)
        session["improv_intelligence_tab"] = "Missions"
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertNotEqual(session.get("display_key"), "Bm")
        self.assertTrue(
            str(session.get("display_key") or token or "").replace(" ", "").lower().startswith("cm")
            or str(session.get("display_key") or "").lower().startswith("c min")
        )


class TestCustomBackingBpmSyncId(unittest.TestCase):
    def test_custom_sync_id_prefers_stable_pick_not_revision(self) -> None:
        from backing_context import BackingContext, backing_page_sync_id, set_backing_context

        session = {"studio_page": "backing"}
        set_backing_context(
            session,
            BackingContext(
                source="custom_progression",
                source_label="Custom",
                active_song_id="custom::trial",
                bound_pick_key="custom::trial",
                custom_revision_id="rev-changes-every-save",
                song_title="Trial Song",
                key="D",
                display_key="E",
                concert_key="E",
                bpm=100,
                style="Pop",
                groove="Pop groove",
            ),
        )
        sid = backing_page_sync_id(session, song_sync_id="catalog-shape")
        self.assertTrue(str(sid).startswith("custom:"))
        self.assertIn("trial", sid)
        self.assertNotIn("rev-changes-every-save", sid)


class TestSbiCustomToActiveRestore(unittest.TestCase):
    def test_switching_to_active_restores_saved_catalog_pk(self) -> None:
        from studio_page_state import apply_improv_song_source

        session = {
            "display_key": "Eb",
            "concert_key": "Eb",
            "_sbi_custom_visit_pk": "Eb",
            "active_catalog_pick_key": SHAPE_PICK,
            "practice_key_by_source": {SHAPE_PICK: "Cm"},
            "sbi_preview_source": "Custom progression",
        }
        apply_improv_song_source(
            session,
            "Active song",
            set_catalog_source=lambda s: None,
            set_custom_source=lambda s: None,
        )
        self.assertEqual(session.get("display_key"), "Cm")
        self.assertIsNone(session.get("_sbi_custom_visit_pk"))


class TestMissionChordNotDSharpWhenConcertDm(unittest.TestCase):
    def test_stale_dsharp_selected_falls_back_to_map_dm(self) -> None:
        from mission_projection_state import resolve_mission_projection_state

        session = {
            "display_key": "Cm",
            "concert_key": "Cm",
            "ii_selected_chord": "D#m",
            "ii_selected_chord_index": 0,
            "ii_selected_section": "A",
            "show_chart_in_instrument_key": False,
        }
        state = resolve_mission_projection_state(
            session,
            section_map=[("A", ["Dm", "G", "Cm"])],
            fallback_key="Cm",
        )
        self.assertEqual(state.concert_chord, "Dm")
        self.assertNotEqual(state.display_chord, "D#m")
        self.assertNotEqual(state.concert_chord, "Bm")


class TestDescendingAbcRegister(unittest.TestCase):
    def test_f_descending_pattern_abc_follows_midi_octaves(self) -> None:
        from improvisation_motif import build_motif_abc

        motif = {
            "chord": "F",
            "notes": ["F", "G", "A", "C"],
            "midi": [65, 67, 69, 72],
        }
        pat = build_motif_pattern(
            motif,
            key_center="F",
            pattern_type="diatonic",
            direction="descending",
            length=8,
        )
        abc = build_motif_abc(pat, key_center="F", bpm=100, title="Motif")
        midis = [int(m) for m in pat.get("midi") or []]
        cell_len = 4
        for i in range(1, 8):
            self.assertLess(midis[i * cell_len], midis[(i - 1) * cell_len])
        leaps = [midis[i] - midis[i - 1] for i in range(1, len(midis))]
        self.assertFalse(any(leap >= 11 for leap in leaps), msg=leaps)
        self.assertIn("T:Motif", abc)


class TestReturnCustomRestoreSignature(unittest.TestCase):
    def test_restore_last_custom_requires_st_and_invalidate(self) -> None:
        import inspect

        from songs.music_source import restore_last_custom_active_song

        params = inspect.signature(restore_last_custom_active_song).parameters
        self.assertIn("invalidate_backing", params)


if __name__ == "__main__":
    unittest.main()
