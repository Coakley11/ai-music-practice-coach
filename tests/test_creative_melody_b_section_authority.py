"""Melody B / section+symbol chord authority and mission backing bootstrap."""

from __future__ import annotations

import copy
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from active_musical_workflow_envelope import apply_atomic_mission_chord_selection
from creative_chord_selection_authority import (
    authoritative_pair_matches_index,
    global_chord_index_for_section_chord,
    read_authoritative_mission_chord_selection,
    resolve_authoritative_chord_selection,
    write_authoritative_chord_selection,
)
from improvisation_intelligence_ui import (
    II_SELECTED_CHORD,
    II_SELECTED_CHORD_INDEX,
    II_SELECTED_SECTION,
    MISSIONS_GENERATE_CONTEXT_KEY,
    _apply_harmony_map_chord_selection,
    _ensure_chord_selection,
    _run_mission_example_generate,
    _selected_chord,
    _stash_missions_generate_context,
)
from improvisation_motif import flatten_section_map, global_chord_index, resolve_improv_sections
from music_workflow_mission_backing_click import (
    MISSION_BACKING_CLICK_INTENT_KEY,
    capture_mission_backing_click_intent,
    peek_mission_backing_click_intent,
)
from music_workflow_pre_widget_bootstrap import (
    PRE_WIDGET_BOOTSTRAP_RAN_KEY,
    run_pre_widget_application_consumers,
)


def _hevenu_sections() -> dict[str, list[str]]:
    return {
        "Melody A": ["C#m", "G#7", "C#m", "F#m", "B", "E", "A", "D"],
        "Melody B": ["C#m", "G#7", "C#m", "F#m", "B", "E", "A", "D"],
    }


def _hevenu_ctx() -> Any:
    from improvisation_intelligence import ImprovSessionContext

    sections = _hevenu_sections()
    flat = flatten_section_map(list(sections.items()))
    return ImprovSessionContext(
        song_title="Hevenu Shalom Aleichem",
        artist="Traditional",
        key_center="C#",
        display_key="C#",
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        sections=sections,
        bpm=72,
        style_label="",
        progression_flat=flat,
        section_order=list(sections.keys()),
    )


def _session_hevenu() -> dict[str, Any]:
    sections = _hevenu_sections()
    return {
        "song": "Hevenu Shalom Aleichem",
        "home_sections": copy.deepcopy(sections),
        "improv_song_concert_sections": copy.deepcopy(sections),
        "instrument": "Guitar",
        "level": "Intermediate",
        "focus": "Improvisation",
        "backing_track_bpm": 72,
        "improv_active_mission": "Target Chord Tones",
        "improv_mission_pick": "Target Chord Tones",
        "active_catalog_pick_key": "Jewish|Hevenu",
    }


class TestSectionSymbolAuthority(unittest.TestCase):
    def test_duplicate_symbol_melody_b_not_collapsed_to_melody_a(self) -> None:
        session = _session_hevenu()
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        chords = flatten_section_map(section_map)
        self.assertEqual(len(section_map), 2)

        g7_b = global_chord_index_for_section_chord(section_map, "Melody B", "G#7")
        self.assertIsNotNone(g7_b)
        assert g7_b is not None
        apply_atomic_mission_chord_selection(
            session,
            chord="G#7",
            section="Melody B",
            chord_index=g7_b,
            chord_label="Melody B · G#7",
            button_key="test_melody_b_g7",
        )
        session[II_SELECTED_CHORD_INDEX] = 1
        _ensure_chord_selection(session, chords, section_map)
        sym, sec, idx = resolve_authoritative_chord_selection(session, section_map)
        self.assertEqual(sym, "G#7")
        self.assertEqual(sec, "Melody B")
        self.assertEqual(idx, g7_b)
        self.assertTrue(
            authoritative_pair_matches_index(
                section_map, section_label=sec, chord_symbol=sym, chord_index=idx
            )
        )

    def test_harmony_melody_b_every_position_maps_to_clicked_symbol(self) -> None:
        session = _session_hevenu()
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        chords = flatten_section_map(section_map)
        melody_b = next(chs for label, chs in section_map if label == "Melody B")
        sec_i = next(i for i, (label, _) in enumerate(section_map) if label == "Melody B")

        for i, expected_ch in enumerate(melody_b):
            gidx = global_chord_index(section_map, sec_i, i)
            _apply_harmony_map_chord_selection(
                session,
                chord=expected_ch,
                section="Melody B",
                chord_index=gidx,
                button_key=f"hm_test_{i}_{expected_ch}",
            )
            _ensure_chord_selection(session, chords, section_map)
            sym, sec, idx = resolve_authoritative_chord_selection(session, section_map)
            self.assertEqual(expected_ch, sym, msg=f"position {i}")
            self.assertEqual("Melody B", sec, msg=f"position {i}")
            self.assertEqual(gidx, idx, msg=f"position {i}")

    def test_ensure_rejects_stale_index_same_symbol_different_section(self) -> None:
        session = _session_hevenu()
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        chords = flatten_section_map(section_map)
        write_authoritative_chord_selection(
            session, section_map, chord_symbol="C#m", section_label="Melody B", chord_index=99
        )
        session[II_SELECTED_CHORD_INDEX] = 0
        _ensure_chord_selection(session, chords, section_map)
        sym, sec, idx = resolve_authoritative_chord_selection(session, section_map)
        self.assertEqual("C#m", sym)
        self.assertEqual("Melody B", sec)
        self.assertNotEqual(0, idx)


class TestMissionsGenerateContext(unittest.TestCase):
    def test_generate_uses_session_authority_over_stale_snap(self) -> None:
        session = _session_hevenu()
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        chords = flatten_section_map(section_map)
        gidx_b = global_chord_index_for_section_chord(section_map, "Melody B", "F#m")
        assert gidx_b is not None
        write_authoritative_chord_selection(
            session, section_map, chord_symbol="F#m", section_label="Melody B", chord_index=gidx_b
        )
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=section_map,
            mission="Target Chord Tones",
            cur_chord="C#m",
            section_label="Melody A",
            chord_idx=0,
            live_inst="Guitar",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=72,
        )
        self.assertIn(MISSIONS_GENERATE_CONTEXT_KEY, session)

        captured: dict[str, Any] = {}

        def _fake_generate(*args: Any, **kwargs: Any) -> Any:
            captured["chord"] = kwargs.get("chord")
            captured["section"] = kwargs.get("section")
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
            _run_mission_example_generate(session, "normal")

        self.assertEqual(captured.get("chord"), "F#m")
        self.assertEqual(captured.get("section"), "Melody B")

    def test_chord_change_clears_generate_snap(self) -> None:
        session = _session_hevenu()
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        session[MISSIONS_GENERATE_CONTEXT_KEY] = {"cur_chord": "C#m", "section_label": "Melody A"}
        gidx = global_chord_index_for_section_chord(section_map, "Melody B", "G#7")
        assert gidx is not None
        apply_atomic_mission_chord_selection(
            session,
            chord="G#7",
            section="Melody B",
            chord_index=gidx,
            chord_label="Melody B · G#7",
            button_key="chg",
        )
        self.assertNotIn(MISSIONS_GENERATE_CONTEXT_KEY, session)


class TestMissionBackingBootstrap(unittest.TestCase):
    def test_pre_widget_applies_click_intent_before_consume(self) -> None:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "instrument": "Guitar",
            "backing_track_bpm": 100,
            "improv_groove": "Auto",
            "backing_time_signature": "4/4",
            "_script_run_seq": 1,
        }
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=False,
            mission="Target Chord Tones",
            cur_chord="G#7",
            section_label="Melody B",
            chord_idx=9,
            song_title="Hevenu",
            concert_key="C#",
            display_key="C#",
        )
        self.assertIsNotNone(peek_mission_backing_click_intent(session))

        st_mock = MagicMock()
        with patch(
            "music_workflow_pending_backing_handoff.consume_pending_backing_workflow_handoff",
            return_value="skipped",
        ) as consume_mock:
            with patch(
                "music_workflow_mission_backing_orchestration.prepare_deferred_mission_backing_handoff",
                return_value=True,
            ):
                phases = run_pre_widget_application_consumers(session, st=st_mock)

        self.assertIn(phases.get("mission_backing_click_intent"), ("applied", "failed"))
        self.assertIsNone(peek_mission_backing_click_intent(session))
        consume_mock.assert_called()
        session.pop(PRE_WIDGET_BOOTSTRAP_RAN_KEY, None)


class TestBackingAfterRepeatedChordChanges(unittest.TestCase):
    def test_backing_intent_uses_latest_authoritative_selection(self) -> None:
        session = _session_hevenu()
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        try:
            from creative_mission_config_persistence import IMPROV_MISSION_SECTION_MAP_SESSION_KEY

            session[IMPROV_MISSION_SECTION_MAP_SESSION_KEY] = section_map
        except ImportError:
            session["_improv_mission_section_map"] = section_map

        picks = [
            ("Melody A", "C#m"),
            ("Melody B", "G#7"),
            ("Melody B", "A"),
        ]
        for sec, ch in picks:
            gidx = global_chord_index_for_section_chord(section_map, sec, ch)
            assert gidx is not None
            apply_atomic_mission_chord_selection(
                session,
                chord=ch,
                section=sec,
                chord_index=gidx,
                chord_label=f"{sec} · {ch}",
                button_key=f"pick_{sec}_{ch}",
            )

        ch, sec, idx = read_authoritative_mission_chord_selection(session, section_map)
        self.assertEqual(ch, "A")
        self.assertEqual(sec, "Melody B")

        capture_mission_backing_click_intent(
            session,
            with_practice_lick=False,
            mission="Target Chord Tones",
            cur_chord=ch,
            section_label=sec,
            chord_idx=idx,
            song_title="Hevenu",
            concert_key="C#",
            display_key="C#",
        )
        intent = session.get(MISSION_BACKING_CLICK_INTENT_KEY)
        assert isinstance(intent, dict)
        self.assertEqual(intent.get("cur_chord"), "A")
        self.assertEqual(intent.get("section_label"), "Melody B")


if __name__ == "__main__":
    unittest.main()
