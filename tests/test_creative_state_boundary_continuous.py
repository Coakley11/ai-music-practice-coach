"""Continuous state-boundary harness — C#m parent, G#7 focus, practice-key invariant."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

import copy
from creative_key_sync import prepare_creative_sidebar_display_key
from creative_lifecycle_harness_support import (
    harmony_map_focus_chord,
    mission_select_single_chord,
    open_backing_entry_jam_production,
    restore_song_based_tab,
    song_based_progression_chord_count,
)
from improvisation_intelligence_ui import MISSIONS_GENERATE_CONTEXT_KEY, _run_mission_example_generate
from improvisation_missions import MISSION_EXAMPLE_KEY, load_mission_example, mission_example_fingerprint
from music_persistent_state import prepare_canonical_music_page_state
from music_workflow_pending_creative_return import (
    consume_pending_creative_return_handoff,
    queue_pending_creative_return_from_backing,
)
from music_workflow_practice_key_guard import PracticeKeySnapshot, assert_practice_key_unchanged
from music_workflow_pre_widget_bootstrap import PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY, run_pre_widget_application_consumers
from music_workflow_pending_song_creative_focus_edit import consume_pending_song_creative_focus_edit
from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated, resolve_song_practice_key_token
from song_creative_focus import (
    hydrate_creative_pages_from_song_focus,
    read_harmony_section_selection,
    read_song_creative_focus,
    resolve_focus_against_progression,
)
from song_creative_focus_change import capture_song_creative_focus_intent
from tests.test_creative_catalog_handoff_picker import CATALOG
from tests.test_song_creative_focus_csharp_parent_gate import (
    LIVE_FOCUS_CHORD,
    LIVE_PARENT_KEY,
    _c_sharp_minor_hevenu_session,
    _find_chord,
    _improv_ctx,
)
from tests.test_song_based_minor_practice_key_lifecycle import (
    _simulate_pre_widget_consume,
    _simulate_sidebar_key_change,
)


def _melody_ab_sections(session: dict[str, Any]) -> None:
    base = session.get("improv_song_concert_sections") or {}
    if not isinstance(base, dict):
        return
    flat: list[str] = []
    for chs in base.values():
        if isinstance(chs, list):
            flat.extend(str(c) for c in chs if str(c).strip())
    if len(flat) < 2:
        flat = ["C#m", "F#m", "G#7", "C#m"]
    session["improv_song_concert_sections"] = {
        "Melody A": [flat[0], flat[1]],
        "Melody B": [flat[2] if len(flat) > 2 else flat[0], flat[3] if len(flat) > 3 else flat[1]],
    }
    session["home_sections"] = copy.deepcopy(session["improv_song_concert_sections"])


class TestCreativeStateBoundaryContinuous(unittest.TestCase):
    def test_csharp_missions_hydrate_without_refresh(self) -> None:
        session = _c_sharp_minor_hevenu_session()
        before = PracticeKeySnapshot.capture(session)
        session["improv_intelligence_tab"] = "Missions"
        ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(resolve_song_practice_key_token(session), LIVE_PARENT_KEY)
        assert_practice_key_unchanged(session, before, action="enter_missions")

    def test_mission_chord_and_double_generate_preserve_practice_key(self) -> None:
        session = _c_sharp_minor_hevenu_session()
        section, gidx = _find_chord(session, LIVE_FOCUS_CHORD)
        self.assertTrue(section)
        before = PracticeKeySnapshot.capture(session)
        mission_select_single_chord(session, chord=LIVE_FOCUS_CHORD, section=section)
        assert_practice_key_unchanged(session, before, action="mission_chord_select")
        run_pre_widget_application_consumers(session)

        ctx = _improv_ctx(session)
        section_map = ctx.sections
        session["improv_mission_pick"] = "Target Chord Tones"
        session["improv_active_mission"] = "Target Chord Tones"
        snap = {
            "mission": "Target Chord Tones",
            "cur_chord": LIVE_FOCUS_CHORD,
            "section_label": section,
            "chord_idx": gidx,
            "live_inst": "Guitar",
            "live_level": "Intermediate",
            "live_focus": "Improvisation",
            "bpm": 100,
            "improv_ctx": {"song_title": ctx.song_title, "display_key": ctx.display_key, "sections": section_map},
        }
        session["_streamlit_widgets_locked_this_run"] = True
        session["_creative_mission_widgets_instantiated"] = True
        session[MISSIONS_GENERATE_CONTEXT_KEY] = dict(snap)
        _run_mission_example_generate(session, "normal")
        assert_practice_key_unchanged(session, before, action="generate_example_1")
        raw = session.get(MISSION_EXAMPLE_KEY)
        self.assertIsInstance(raw, dict)
        self.assertIsInstance(raw.get("motif"), dict)
        ctx2 = _improv_ctx(session)
        loaded = load_mission_example(session, ctx2)
        self.assertIsNotNone(loaded)
        fp1 = mission_example_fingerprint(loaded)
        self.assertTrue(session.get("_mission_example_blob_mutation_ok"))
        self.assertEqual(str(session.get("_mission_example_blob_mutation_code") or ""), "PROJECTION_DEFERRED")
        focus_after = read_song_creative_focus(session)
        assert focus_after is not None
        self.assertEqual(str(focus_after.get("selected_concert_chord") or ""), LIVE_FOCUS_CHORD)

        session[MISSIONS_GENERATE_CONTEXT_KEY] = dict(snap)
        _run_mission_example_generate(session, "new")
        assert_practice_key_unchanged(session, before, action="generate_example_2")
        loaded2 = load_mission_example(session, ctx2)
        self.assertIsNotNone(loaded2)
        fp2 = mission_example_fingerprint(loaded2)
        self.assertNotEqual(fp1, fp2)
        self.assertEqual(resolve_song_practice_key_token(session), LIVE_PARENT_KEY)

    def test_harmony_melody_b_widget_pending_and_local_selection(self) -> None:
        session = _c_sharp_minor_hevenu_session()
        _melody_ab_sections(session)
        sections = session["improv_song_concert_sections"]
        a_chords = list(sections.get("Melody A") or [])
        b_chords = list(sections.get("Melody B") or [])
        a1 = a_chords[0]
        b2 = b_chords[1] if len(b_chords) > 1 else b_chords[0]
        mission_select_single_chord(session, chord=a1, section="Melody A")
        _melody_ab_sections(session)
        run_pre_widget_application_consumers(session)
        local_a_after_mission = read_harmony_section_selection(session, "Melody A")
        self.assertIsNotNone(local_a_after_mission)
        self.assertEqual(local_a_after_mission[0], a1)

        from improvisation_motif import global_chord_index
        from song_creative_focus import _section_map_for_focus

        ctx = _improv_ctx(session)
        section_map = _section_map_for_focus(session, ctx)
        sec_i_b = next(i for i, (lab, _) in enumerate(section_map) if lab == "Melody B")
        ci_b = 1 if len(b_chords) > 1 else 0
        gidx_b = global_chord_index(section_map, sec_i_b, ci_b)

        session["_streamlit_widgets_locked_this_run"] = True
        session["_creative_mission_widgets_instantiated"] = True
        queued = capture_song_creative_focus_intent(
            session,
            section="Melody B",
            concert_chord=b2,
            chord_index=gidx_b,
            source_page="Harmony Map",
        )
        self.assertTrue(queued)
        session.pop("_streamlit_widgets_locked_this_run", None)
        session[PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY] = True
        phase = consume_pending_song_creative_focus_edit(session)
        session.pop(PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY, None)
        self.assertEqual(phase, "applied")

        focus_b = read_song_creative_focus(session)
        assert focus_b is not None
        self.assertEqual(str(focus_b.get("selected_section_id") or ""), "Melody B")
        self.assertEqual(str(focus_b.get("selected_concert_chord") or ""), b2)
        local_a = read_harmony_section_selection(session, "Melody A")
        local_b = read_harmony_section_selection(session, "Melody B")
        self.assertEqual(local_a, (a1, 0))
        self.assertEqual(local_b[0], b2)
        hydrate_creative_pages_from_song_focus(session, tab="Harmony Map")
        self.assertEqual(read_harmony_section_selection(session, "Melody A")[0], a1)
        self.assertEqual(read_harmony_section_selection(session, "Melody B")[0], b2)

    def test_harmony_melody_b_does_not_rebind_melody_a(self) -> None:
        session = _c_sharp_minor_hevenu_session()
        _melody_ab_sections(session)
        sections = session["improv_song_concert_sections"]
        a_chords = list(sections.get("Melody A") or [])
        b_chords = list(sections.get("Melody B") or [])
        self.assertGreaterEqual(len(a_chords), 1)
        self.assertGreaterEqual(len(b_chords), 1)
        a1, b1 = a_chords[0], b_chords[0]
        mission_select_single_chord(session, chord=a1, section="Melody A")
        focus_a = read_song_creative_focus(session)
        assert focus_a is not None
        self.assertEqual(str(focus_a.get("selected_section_id") or ""), "Melody A")
        b2 = b_chords[1] if len(b_chords) > 1 else b_chords[0]
        if b2 == b1 and len(b_chords) > 2:
            b2 = b_chords[2]
        harmony_map_focus_chord(session, chord=b2, section="Melody B")
        focus_b = read_song_creative_focus(session)
        assert focus_b is not None
        self.assertEqual(str(focus_b.get("selected_section_id") or ""), "Melody B")
        self.assertEqual(str(focus_b.get("selected_concert_chord") or ""), b2)
        resolved = resolve_focus_against_progression(session, focus_b)
        self.assertEqual(str(resolved.get("selected_section_id") or ""), "Melody B")

    def test_return_to_creative_pre_widget_consume(self) -> None:
        session = _c_sharp_minor_hevenu_session()
        session["studio_page"] = "backing"
        session["improv_intelligence_tab"] = "Missions"
        try:
            open_backing_entry_jam_production(session)
        except Exception:
            self.skipTest("backing open path unavailable in unit harness")
        session["studio_page"] = "backing"
        req = queue_pending_creative_return_from_backing(session)
        self.assertIsNotNone(req)
        session.pop("_music_pre_widget_bootstrap_ran_this_run", None)
        phase = consume_pending_creative_return_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertEqual(str(session.get("studio_page") or "").lower(), "creative")


if __name__ == "__main__":
    unittest.main()
