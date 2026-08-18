"""Pass 7: Missions concert vs chart vs selected chord vs example spelling."""

from __future__ import annotations

import unittest

from creative_chord_selection_authority import resolve_authoritative_chord_selection
from effective_practice_context import musician_facing_chart_key, musician_facing_chord
from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY
from improvisation_intelligence import ImprovSessionContext
from improvisation_missions import generate_mission_example, refresh_mission_example
from mission_projection_state import (
    example_needs_chart_reproject,
    resolve_mission_projection_state,
)
from music_workflow_mutation import mutate_mission_chord_selection


SHAPE_VERSE = [("Verse 1", ["Dm", "Gm", "Bb", "C"])]


def _shape_of_you_guitar_session(**extra):
    session = {
        "display_key": "Dm",
        "concert_key": "Dm",
        "instrument": "Guitar",
        "song": "Shape of You",
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "D#",
        "ii_selected_chord": "F#m",
        "ii_selected_section": "Verse 1",
        "ii_selected_chord_index": 0,
        "improv_song_concert_sections": {"Verse 1": ["Dm", "Gm", "Bb", "C"]},
        "home_sections": {"Verse 1": ["C#m", "F#m", "A", "B"]},
    }
    session.update(extra)
    return session


class TestMissionProjectionOwnership(unittest.TestCase):
    def test_stale_fsharp_symbol_does_not_override_index_zero_dsharp(self):
        session = _shape_of_you_guitar_session()
        state = resolve_mission_projection_state(
            session, section_map=SHAPE_VERSE, fallback_key="Dm"
        )
        self.assertEqual(state.concert_key, "Dm")
        self.assertEqual(state.chart_key, "D#m")
        self.assertEqual(state.concert_chord, "Dm")
        self.assertEqual(state.display_chord, "D#m")
        self.assertEqual(state.chord_index, 0)
        self.assertNotIn("F#", state.display_chord)
        self.assertEqual(session.get("ii_selected_chord"), "Dm")

    def test_tile_label_and_selected_label_agree(self):
        session = _shape_of_you_guitar_session()
        concert, chart = "Dm", musician_facing_chart_key(session, "Dm")
        self.assertEqual(chart, "D#m")
        tile = musician_facing_chord("Dm", concert_key=concert, chart_key=chart)
        state = resolve_mission_projection_state(
            session, section_map=SHAPE_VERSE, fallback_key="Dm"
        )
        self.assertEqual(tile, state.display_chord)
        self.assertEqual(tile, "D#m")

    def test_chord_selection_does_not_mutate_practice_key(self):
        session = _shape_of_you_guitar_session()
        before = session["display_key"]
        mutate_mission_chord_selection(
            session,
            chord="Bb",
            section="Verse 1",
            chord_index=2,
            chord_label="Verse 1 · Bb",
        )
        self.assertEqual(str(session.get("display_key") or ""), before)
        self.assertEqual(str(session.get("concert_key") or ""), "Dm")

    def test_index_prefers_map_slot_over_original_symbol(self):
        session = _shape_of_you_guitar_session()
        ch, sec, idx = resolve_authoritative_chord_selection(session, SHAPE_VERSE)
        self.assertEqual(idx, 0)
        self.assertEqual(ch, "Dm")
        self.assertEqual(sec, "Verse 1")


class TestMissionExampleChartSpelling(unittest.TestCase):
    def _ctx(self) -> ImprovSessionContext:
        return ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center="Dm",
            display_key="D#m",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse 1": ["Dm", "Gm", "Bb", "C"]},
            bpm=96,
        )

    def test_generate_example_heading_and_tones_use_dsharp_not_d_minor(self):
        ctx = self._ctx()
        example = generate_mission_example(
            "Improvise using only chord tones",
            improv_ctx=ctx,
            chord="Dm",
            section="Verse 1",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            bpm=96,
        )
        self.assertEqual(str((example.motif or {}).get("_concert_chord") or ""), "Dm")
        self.assertEqual(str((example.motif or {}).get("chord") or ""), "D#m")
        self.assertEqual(str(example.insight.chord or ""), "D#m")
        self.assertIn("— D#m", example.abc)
        self.assertNotIn("— Dm", example.abc)
        tones = " ".join(example.insight.chord_tones)
        self.assertTrue(any(t in tones for t in ("D#", "Eb")))
        self.assertTrue(
            any("d# dorian" in s.lower() or "eb dorian" in s.lower() for s in example.insight.scales)
        )

    def test_refresh_reprojects_example_when_shape_chart_changes(self):
        ctx = self._ctx()
        example = generate_mission_example(
            "Improvise using only chord tones",
            improv_ctx=ctx,
            chord="Dm",
            section="Verse 1",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            bpm=96,
        )
        example.display_key = "Em"
        refreshed = refresh_mission_example(
            example, instrument="Guitar", bpm=96, song_concert_key="Dm"
        )
        self.assertEqual(str((refreshed.motif or {}).get("_concert_chord") or ""), "Dm")
        self.assertEqual(str((refreshed.motif or {}).get("chord") or ""), "Em")
        self.assertIn("— Em", refreshed.abc)
        self.assertEqual(str(refreshed.insight.chord or ""), "Em")

    def test_stale_d_minor_example_needs_reproject_for_dsharp_chart(self):
        from improvisation_missions import ChordCoachInsight, MissionExample

        session = _shape_of_you_guitar_session()
        state = resolve_mission_projection_state(
            session, section_map=SHAPE_VERSE, fallback_key="Dm"
        )
        example = MissionExample(
            mission="Improvise using only chord tones",
            variant="normal",
            chord="Dm",
            section="Verse 1",
            song_title="Shape of You",
            display_key="Dm",
            concert_key="Dm",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            motif={
                "notes": ["D", "F", "A"],
                "display": "D – F – A",
                "chord": "Dm",
                "_concert_chord": "Dm",
                "_concert_notes": ["D", "F", "A"],
                "_projected_display_key": "Dm",
            },
            abc="T:Mission: Improvise using only chord tones — Dm",
            tab="",
            piano_html="",
            why="",
            practice_steps=[],
            insight=ChordCoachInsight(
                chord="Dm",
                scales=["D dorian"],
                scale_suggestions=[],
                chord_tones=["D", "F", "A"],
                tensions=[],
                avoid_notes=[],
                target_notes=[],
                motif_idea="",
                resolve_hint="",
                instrument_tips=[],
            ),
            show_tab=True,
            show_piano=False,
        )
        self.assertTrue(example_needs_chart_reproject(example, state))


class TestBackingPracticeKeyLiveHonored(unittest.TestCase):
    def test_mission_backing_keeps_live_practice_key_without_sidebar_source(self):
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import prepare_backing_context_sidebar_display_key

        session = {
            "display_key": "Fm",
            "concert_key": "Fm",
            "studio_page": "backing",
            "instrument": "Guitar",
            "improv_intelligence_tab": "Missions",
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id="mission",
                song_title="Shape of You",
                key="Dm",
                display_key="Dm",
                concert_key="Dm",
                style="Pop",
                groove="Pop",
                meter="4/4",
                bpm=96,
                progression=["Dm"],
                progression_label="Dm",
                section="Verse 1",
                source_signature="mission-sig",
            ),
        )
        st = type("S", (), {"session_state": session})()
        options = prepare_backing_context_sidebar_display_key(st, session)
        self.assertIn("Fm", options)
        self.assertEqual(session.get("display_key"), "Fm")


class TestEnsureSheetMusicKeepsChartProjection(unittest.TestCase):
    def test_ensure_does_not_collapse_dsharp_insight_to_d_minor(self):
        from improvisation_missions import (
            ensure_mission_sheet_music_authority,
            load_mission_example,
            store_mission_example,
        )

        ctx = ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center="Dm",
            display_key="D#m",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse 1": ["Dm", "Gm", "Bb", "C"]},
            bpm=96,
        )
        example = generate_mission_example(
            "Improvise using only chord tones",
            improv_ctx=ctx,
            chord="Dm",
            section="Verse 1",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            bpm=96,
        )
        session = _shape_of_you_guitar_session()
        store_mission_example(session, example)
        loaded = load_mission_example(session, ctx)
        self.assertIsNotNone(loaded)
        session["_mission_notation_staff_version"] = 0
        out = ensure_mission_sheet_music_authority(
            session, loaded, improv_ctx=ctx, instrument="Guitar", bpm=96
        )
        self.assertEqual(str(out.insight.chord or ""), "D#m")
        tones = " ".join(out.insight.chord_tones)
        self.assertTrue(any(t in tones for t in ("D#", "Eb")))
        self.assertNotEqual(list(out.insight.chord_tones[:3]), ["D", "F", "A"])
        joined_scales = " ".join(out.insight.scales).lower()
        self.assertTrue("d#" in joined_scales or "eb" in joined_scales or "d♯" in joined_scales)
        self.assertNotIn("— Dm", out.abc)
        self.assertIn("— D#m", out.abc)

    def test_generate_for_bb_uses_b_display_not_dsharp(self):
        ctx = ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center="Dm",
            display_key="D#m",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse 1": ["Dm", "Gm", "Bb", "C"]},
            bpm=96,
        )
        example = generate_mission_example(
            "Improvise using only chord tones",
            improv_ctx=ctx,
            chord="Bb",
            section="Verse 1",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            bpm=96,
        )
        self.assertEqual(str((example.motif or {}).get("_concert_chord") or ""), "Bb")
        self.assertEqual(str((example.motif or {}).get("chord") or ""), "B")
        self.assertEqual(str(example.insight.chord or ""), "B")
        self.assertTrue(
            "— B" in (example.abc or "") and "— Bb" not in (example.abc or ""),
            example.abc[:240],
        )
        self.assertNotIn("— D#m", example.abc)
        self.assertNotIn("— Dm", example.abc)


class TestBackingSliderSyncIdStableAcrossBpm(unittest.TestCase):
    def test_sbi_sync_id_does_not_include_bpm_or_signature(self):
        from backing_context import BackingContext, backing_page_sync_id, set_backing_context

        session = {
            "display_key": "Dm",
            "concert_key": "Dm",
            "studio_page": "backing",
        }
        ctx96 = BackingContext(
            source="song_improv",
            source_label="Song-Based Improvisation",
            active_song_id="shape-of-you",
            bound_pick_key="shape-of-you",
            song_title="Shape of You",
            key="Dm",
            display_key="Dm",
            concert_key="Dm",
            style="Pop",
            groove="Pop",
            meter="4/4",
            bpm=96,
            progression=["Dm", "Gm"],
            progression_label="Dm – Gm",
            section="Verse 1",
            entry_mode="Song-Based Improvisation",
        )
        set_backing_context(session, ctx96)
        id_96 = backing_page_sync_id(session, song_sync_id="shape-of-you")
        ctx118 = BackingContext(
            source="song_improv",
            source_label="Song-Based Improvisation",
            active_song_id="shape-of-you",
            bound_pick_key="shape-of-you",
            song_title="Shape of You",
            key="Dm",
            display_key="Dm",
            concert_key="Dm",
            style="Pop",
            groove="Pop",
            meter="4/4",
            bpm=118,
            progression=["Dm", "Gm"],
            progression_label="Dm – Gm",
            section="Verse 1",
            entry_mode="Song-Based Improvisation",
        )
        set_backing_context(session, ctx118)
        id_118 = backing_page_sync_id(session, song_sync_id="shape-of-you")
        self.assertEqual(id_96, id_118)
        self.assertNotIn(str(ctx96.source_signature), id_96)
        self.assertNotIn("96", id_96.split(":")[-1])
        self.assertNotIn("118", id_118.split(":")[-1])
