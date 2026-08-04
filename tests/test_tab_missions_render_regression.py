"""Regression: _tab_missions must run load_mission_example + recording expander without UnboundLocalError."""

from __future__ import annotations

import inspect
import unittest
from unittest import mock

import improvisation_intelligence_ui as ui
from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import _run_mission_example_generate, _tab_missions
from improvisation_missions import MISSION_EXAMPLE_KEY, load_mission_example


class _ColumnStub:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def button(self, *a, **k):
        return False


class _StStub:
    def markdown(self, *a, **k):
        return None

    def caption(self, *a, **k):
        return None

    def info(self, *a, **k):
        return None

    def warning(self, *a, **k):
        return None

    def error(self, *a, **k):
        return None

    def code(self, *a, **k):
        return None

    def json(self, *a, **k):
        return None

    def rerun(self, *a, **k):
        return None

    def columns(self, n):
        return [_ColumnStub() for _ in range(n)]

    def selectbox(self, label, options, **k):
        idx = int(k.get("index") or 0)
        return options[idx]

    def checkbox(self, *a, **k):
        return bool(k.get("value", False))

    def button(self, *a, **k):
        return False

    def expander(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _improv_ctx() -> ImprovSessionContext:
    return ImprovSessionContext(
        song_title="Shape",
        artist="Artist",
        key_center="Em",
        display_key="Em",
        instrument="Piano",
        level="Intermediate",
        focus="Improvisation",
        sections={"Chorus": ["Em"]},
        bpm=100,
        style_label="Pop",
        progression_flat=["Em"],
        section_order=["Chorus"],
    )


def _base_session() -> dict:
    return {
        "song": "Shape",
        "artist": "Artist",
        "display_key": "Em",
        "concert_key": "Em",
        "instrument": "Piano",
        "level": "Intermediate",
        "focus": "Improvisation",
        "improv_active_mission": "Develop a Motif",
        "improv_mission_pick": "Develop a Motif",
        "home_sections": {"Chorus": ["Em"]},
        "improv_mission_chord_options": ["Em"],
        "ii_selected_chord_index": 0,
        "ii_selected_chord": "Em",
        "ii_selected_section": "Chorus",
        "backing_track_bpm": 100,
        "_creative_selector_hydration_complete": True,
    }


class TestTabMissionsRenderRegression(unittest.TestCase):
    def test_tab_missions_does_not_import_load_mission_example_locally(self) -> None:
        src = inspect.getsource(_tab_missions)
        self.assertNotRegex(
            src,
            r"from\s+improvisation_missions\s+import[^\n]*\bload_mission_example\b",
            msg="inner import shadows module-level load_mission_example",
        )

    def test_tab_missions_body_with_example_and_recording_expander(self) -> None:
        session = _base_session()
        _run_mission_example_generate(session, "normal")
        self.assertIsInstance(session.get(MISSION_EXAMPLE_KEY), dict)

        ctx = _improv_ctx()
        real_load = load_mission_example
        load_calls: list[tuple[dict, ImprovSessionContext]] = []

        def _track_load(ss, ic):
            load_calls.append((ss, ic))
            return real_load(ss, ic)

        expander_calls: list[tuple] = []

        def _track_expander(st, ss, **kwargs):
            expander_calls.append((st, ss, kwargs))

        st = _StStub()
        with mock.patch(
            "practice_setup_controls.render_setup_quick_controls",
            return_value=("Piano", "Intermediate", "Improvisation"),
        ), mock.patch.object(ui, "_render_missions_route_dev_marker"), mock.patch.object(
            ui, "_render_section_chord_map"
        ), mock.patch.object(
            ui, "_render_motif_sheet_music"
        ), mock.patch(
            "improvisation_intelligence_ui.load_mission_example",
            side_effect=_track_load,
        ), mock.patch(
            "mission_upload_recording_ui.render_mission_recording_upload_expander",
            side_effect=_track_expander,
        ):
            _tab_missions(
                st,
                session_state=session,
                improv_ctx=ctx,
                bpm=100,
                on_open_backing=None,
                on_open_practice=None,
                on_open_analysis=lambda: None,
            )

        self.assertGreaterEqual(len(load_calls), 1)
        self.assertEqual(len(expander_calls), 1)
        loaded = real_load(session, ctx)
        self.assertIsNotNone(loaded)


if __name__ == "__main__":
    unittest.main()
