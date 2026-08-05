"""Mission example normalization — Practice-in-Jam pre-widget consume and key authority."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    MISSION_PRACTICE_LICK_KEY,
    MissionExample,
    _fallback_chord_insight,
    mission_example_for_display,
    store_mission_practice_lick_for_backing,
)
from mission_example_normalization import (
    ERROR_INVALID_SHAPE,
    ERROR_MISSING_MOTIF,
    MISSION_BACKING_EXAMPLE_ERROR_KEY,
    MISSION_EXAMPLE_NORMALIZE_DIAG_KEY,
    normalize_mission_example_for_display,
)
from music_workflow_mission_backing_click import (
    MISSION_BACKING_CLICK_INTENT_KEY,
    apply_mission_backing_click_intent,
    capture_mission_backing_click_intent,
    peek_mission_backing_click_intent,
)


def _motif_bb_dm() -> dict[str, Any]:
    return {
        "notes": ["Bb", "D", "F"],
        "rhythm": "quarter quarter quarter",
        "midi": [70, 74, 77],
        "chord": "Bb",
    }


def _session_example_dict(*, stale_display: str = "") -> dict[str, Any]:
    blob: dict[str, Any] = {
        "mission": "Outline chord tones",
        "variant": "normal",
        "chord": "Bb",
        "section": "A",
        "motif": _motif_bb_dm(),
        "abc": "",
        "tab": "",
        "piano_html": "",
        "why": "",
        "practice_steps": [],
        "show_tab": False,
        "show_piano": True,
        "material_fp": "fp1",
    }
    if stale_display:
        blob["display_key"] = stale_display
    return blob


def _typed_example(*, display_key: str = "Dm", concert_key: str = "Dm") -> MissionExample:
    return MissionExample(
        mission="Outline chord tones",
        variant="normal",
        chord="Bb",
        section="A",
        song_title="Song",
        display_key=display_key,
        concert_key=concert_key,
        instrument="Piano",
        level="Intermediate",
        focus="Improvisation",
        motif=_motif_bb_dm(),
        abc="",
        tab="",
        piano_html="",
        why="",
        practice_steps=[],
        insight=_fallback_chord_insight("Bb"),
        show_tab=False,
        show_piano=True,
    )


class TestNormalizeMissionExample(unittest.TestCase):
    def test_typed_mission_example_with_all_fields(self) -> None:
        ex = _typed_example()
        result = normalize_mission_example_for_display(
            ex,
            authoritative_concert_key="Dm",
            authoritative_display_key="Dm",
        )
        self.assertTrue(result.ok)
        assert result.example is not None
        self.assertEqual(result.example.display_key, "Dm")
        self.assertEqual(result.example.concert_key, "Dm")
        self.assertEqual(result.example.chord, "Bb")

    def test_session_dict_missing_legacy_display_key(self) -> None:
        session: dict[str, Any] = {"concert_key": "Dm", "display_key": "Dm", "instrument": "Piano"}
        result = normalize_mission_example_for_display(
            _session_example_dict(),
            session_state=session,
            authoritative_concert_key="Dm",
        )
        self.assertTrue(result.ok)
        assert result.example is not None
        self.assertEqual(result.example.display_key, "Dm")
        self.assertEqual(result.example.concert_key, "Dm")

    def test_stale_display_key_does_not_override_workflow(self) -> None:
        session: dict[str, Any] = {"concert_key": "Dm", "display_key": "Dm"}
        result = normalize_mission_example_for_display(
            _session_example_dict(stale_display="A"),
            session_state=session,
            authoritative_concert_key="Dm",
            authoritative_display_key="Dm",
        )
        self.assertTrue(result.ok)
        assert result.example is not None
        self.assertEqual(result.example.concert_key, "Dm")
        self.assertEqual(result.example.display_key, "Dm")
        out = mission_example_for_display(
            result.example,
            instrument="Piano",
            bpm=100,
            song_concert_key="Dm",
            session_state=session,
            authoritative_concert_key="Dm",
        )
        abc = str(out.abc or "").replace(" ", "")
        self.assertIn("K:d", abc)
        self.assertNotIn("K:A", abc)

    def test_invalid_shape_fails_closed(self) -> None:
        result = normalize_mission_example_for_display("not-an-example")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, ERROR_INVALID_SHAPE)

    def test_missing_motif_fails_closed(self) -> None:
        result = normalize_mission_example_for_display(
            {"chord": "Bb", "motif": {}},
            authoritative_concert_key="Dm",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, ERROR_MISSING_MOTIF)


class TestPracticeInJamPreWidgetConsume(unittest.TestCase):
    def test_apply_normalizes_dict_example_and_defers_handoff(self) -> None:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "instrument": "Piano",
            "backing_track_bpm": 100,
            "improv_groove": "Auto",
            "backing_time_signature": "4/4",
            MISSION_EXAMPLE_KEY: _session_example_dict(),
        }
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=True,
            mission="Outline chord tones",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="Song",
            concert_key="Dm",
            display_key="Dm",
        )
        with mock.patch(
            "music_workflow_mission_backing_orchestration.prepare_deferred_mission_backing_handoff",
            return_value=True,
        ) as defer:
            self.assertTrue(apply_mission_backing_click_intent(session, st_module=mock.Mock()))
            defer.assert_called_once()
        self.assertIsNone(peek_mission_backing_click_intent(session))
        self.assertIn(MISSION_PRACTICE_LICK_KEY, session)
        self.assertIn(MISSION_EXAMPLE_NORMALIZE_DIAG_KEY, session)

    def test_apply_fails_closed_without_navigation_on_bad_example(self) -> None:
        session: dict[str, Any] = {
            "instrument": "Piano",
            "backing_track_bpm": 100,
            MISSION_EXAMPLE_KEY: {"chord": "Bb", "motif": {}},
        }
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=True,
            mission="M",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="Song",
            concert_key="Dm",
            display_key="Dm",
        )
        with mock.patch(
            "music_workflow_mission_backing_orchestration.prepare_deferred_mission_backing_handoff",
            return_value=True,
        ) as defer:
            self.assertFalse(apply_mission_backing_click_intent(session, st_module=mock.Mock()))
            defer.assert_not_called()
        self.assertIsNone(peek_mission_backing_click_intent(session))
        self.assertIn(MISSION_BACKING_EXAMPLE_ERROR_KEY, session)
        from music_workflow_mission_backing_click import MISSION_BACKING_CLICK_APPLY_FAILURE_KEY

        self.assertIn(MISSION_BACKING_CLICK_APPLY_FAILURE_KEY, session)
        self.assertNotIn(MISSION_PRACTICE_LICK_KEY, session)

    def test_plain_mission_backing_without_lick_skips_normalize(self) -> None:
        session: dict[str, Any] = {"instrument": "Piano"}
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=False,
            mission="M",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="Song",
            concert_key="Dm",
            display_key="Dm",
        )
        with mock.patch(
            "music_workflow_mission_backing_orchestration.prepare_deferred_mission_backing_handoff",
            return_value=True,
        ) as defer:
            self.assertTrue(apply_mission_backing_click_intent(session, st_module=mock.Mock()))
            defer.assert_called_once()
        self.assertNotIn(MISSION_PRACTICE_LICK_KEY, session)


class TestStoreMissionPracticeLick(unittest.TestCase):
    def test_store_from_session_dict_returns_true(self) -> None:
        session: dict[str, Any] = {"instrument": "Piano", "level": "Intermediate"}
        ok = store_mission_practice_lick_for_backing(
            session,
            example=_session_example_dict(),
            mission_title="Outline chord tones",
            instrument="Piano",
            bpm=100,
            groove="Auto",
            meter="4/4",
            song_title="Song",
            section_label="A",
            persist_artifact=False,
            song_concert_key="Dm",
            song_display_key="Dm",
        )
        self.assertTrue(ok)
        lick = session.get(MISSION_PRACTICE_LICK_KEY)
        assert isinstance(lick, dict)
        self.assertEqual(lick.get("chord"), "Bb")
        self.assertEqual(lick.get("key_center"), "Dm")


if __name__ == "__main__":
    unittest.main()
