"""Two-run Missions render: Generate Example then New Idea must change visible material."""

from __future__ import annotations

import re
import unittest
from unittest import mock

from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import (
    _run_mission_example_generate,
    _tab_missions,
)
from improvisation_missions import (
    MISSION_EXAMPLE_GEN_DIAG_KEY,
    MISSION_EXAMPLE_FRESH_RUN_KEY,
)


class _ColumnStub:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def button(self, *a, **k):
        return False


class CapturingSt:
    def __init__(self) -> None:
        self.markdown_lines: list[str] = []

    def markdown(self, text, *a, **k):
        self.markdown_lines.append(str(text))

    def caption(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def code(self, *a, **k):
        pass

    def json(self, *a, **k):
        pass

    def rerun(self, *a, **k):
        pass

    def columns(self, n):
        return [_ColumnStub() for _ in range(n)]

    def selectbox(self, label, options, **k):
        idx = int(k.get("index") or 0)
        return options[idx]

    def checkbox(self, *a, **k):
        return bool(k.get("value", True))

    def button(self, *a, **k):
        return False

    def expander(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def notes_display(self) -> str | None:
        joined = "\n".join(self.markdown_lines)
        m = re.search(r"\*\*Notes:\*\* `([^`]+)`", joined)
        return m.group(1) if m else None

    def has_optional_example_block(self) -> bool:
        return any("Optional example (inspiration only)" in line for line in self.markdown_lines)


def _session() -> dict:
    return {
        "song": "Shape",
        "artist": "Artist",
        "display_key": "F#m",
        "concert_key": "F#m",
        "instrument": "Piano",
        "level": "Intermediate",
        "focus": "Improvisation",
        "improv_active_mission": "Improvise using only chord tones",
        "improv_mission_pick": "Improvise using only chord tones",
        "home_sections": {"Chorus": ["Em"]},
        "improv_mission_chord_options": ["Em"],
        "ii_selected_chord_index": 0,
        "ii_selected_chord": "Em",
        "ii_selected_section": "Chorus",
        "backing_track_bpm": 100,
        "_creative_selector_hydration_complete": True,
    }


def _ctx() -> ImprovSessionContext:
    return ImprovSessionContext(
        song_title="Shape",
        artist="Artist",
        key_center="F#m",
        display_key="F#m",
        instrument="Piano",
        level="Intermediate",
        focus="Improvisation",
        sections={"Chorus": ["Em"]},
        bpm=100,
        style_label="Pop",
        progression_flat=["Em"],
        section_order=["Chorus"],
    )


def _render_missions(session: dict) -> CapturingSt:
    st = CapturingSt()
    patches = [
        mock.patch(
            "practice_setup_controls.render_setup_quick_controls",
            return_value=("Piano", "Intermediate", "Improvisation"),
        ),
        mock.patch("improvisation_intelligence_ui._render_missions_route_dev_marker"),
        mock.patch("improvisation_intelligence_ui._render_section_chord_map"),
        mock.patch("improvisation_intelligence_ui._render_motif_sheet_music"),
        mock.patch("mission_upload_recording_ui.render_mission_recording_upload_expander"),
    ]
    for p in patches:
        p.start()
    try:
        _tab_missions(
            st,
            session_state=session,
            improv_ctx=_ctx(),
            bpm=100,
            on_open_backing=None,
            on_open_practice=None,
            on_open_analysis=None,
        )
    finally:
        for p in patches:
            p.stop()
    return st


class TestMissionsGenerateNewIdeaDoubleRender(unittest.TestCase):
    def test_generate_then_new_idea_changes_visible_notes(self) -> None:
        session = _session()

        _run_mission_example_generate(session, "normal")
        self.assertTrue(session.get(MISSION_EXAMPLE_GEN_DIAG_KEY, {}).get("callback_fired"))
        session[MISSION_EXAMPLE_FRESH_RUN_KEY] = True

        first = _render_missions(session)
        notes1 = first.notes_display()
        self.assertTrue(first.has_optional_example_block(), msg="Generate must render example block")
        self.assertTrue(notes1, msg="Generate must render Notes line")

        _run_mission_example_generate(session, "new")
        diag = session.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {}
        self.assertEqual(diag.get("callback"), "mission_example_generate_new")
        session[MISSION_EXAMPLE_FRESH_RUN_KEY] = True

        try:
            from creative_mission_artifact_persistence import project_mission_artifacts_from_canonical

            project_mission_artifacts_from_canonical(session, overwrite=True)
        except ImportError:
            pass

        second = _render_missions(session)
        notes2 = second.notes_display()
        self.assertTrue(notes2)
        self.assertNotEqual(notes1, notes2, msg="New Idea must change displayed note material")

    def test_fresh_run_skips_canonical_stomp_before_render(self) -> None:
        session = _session()
        _run_mission_example_generate(session, "normal")
        mat = (session.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {}).get("generated_material_fp")
        stale = {"motif": {"display": "STALE", "notes": ["C4"], "rhythm": "x"}}
        try:
            from creative_mission_artifact_persistence import (
                commit_mission_artifacts_to_canonical,
                project_mission_artifacts_from_canonical,
            )
            from improvisation_missions import MISSION_EXAMPLE_KEY

            commit_mission_artifacts_to_canonical(
                session,
                reason="creative_mission_example_change",
                values={MISSION_EXAMPLE_KEY: stale},
            )
        except ImportError:
            self.skipTest("persistence module unavailable")
        session[MISSION_EXAMPLE_FRESH_RUN_KEY] = True
        project_mission_artifacts_from_canonical(session, overwrite=True)
        self.assertNotEqual(
            (session.get("improv_mission_example") or {}).get("motif", {}).get("display"),
            "STALE",
        )
        self.assertEqual(
            (session.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {}).get("generated_material_fp"),
            mat,
        )


if __name__ == "__main__":
    unittest.main()
