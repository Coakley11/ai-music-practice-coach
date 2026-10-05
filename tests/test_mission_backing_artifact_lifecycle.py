"""Mission Backing open is navigation — it must not destroy the live Mission example."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from improvisation_missions import MISSION_EXAMPLE_KEY
from mission_backing_alignment import apply_pending_mission_backing_alignment, build_mission_backing_alignment_payload
from music_workflow_mission_backing_click import (
    apply_mission_backing_click_intent,
    capture_mission_backing_click_intent,
)
from music_workflow_mutation import mutate_mission_handoff_aligned
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    save_workflow_blob,
    set_active_workflow_pointer,
)


RECOGNIZABLE_NOTES = ["G", "Bb", "D", "F"]
RECOGNIZABLE_MIDI = [67, 70, 74, 77]
RECOGNIZABLE_RHYTHM = "quarter quarter quarter quarter"


def _example_payload(*, chord: str = "Gm", mission: str = "Outline chord tones", key: str = "G minor") -> dict[str, Any]:
    return {
        "mission": mission,
        "variant": "normal",
        "chord": chord,
        "section": "Verse",
        "concert_key": key,
        "display_key": key,
        "level": "Intermediate",
        "difficulty_bucket": "normal",
        "idea_index": 3,
        "seed": "mission-example-A",
        "vocab": "chord_tones",
        "development": "sequence",
        "motif": {
            "notes": list(RECOGNIZABLE_NOTES),
            "midi": list(RECOGNIZABLE_MIDI),
            "rhythm": RECOGNIZABLE_RHYTHM,
            "_concert_chord": chord,
        },
        "abc": "X:1",
        "tab": "",
        "piano_html": "",
        "why": "example A",
        "practice_steps": ["play the G"],
        "show_tab": False,
        "show_piano": True,
        "material_fp": "example-A-fp",
    }


def _polluted_session(*, example: dict[str, Any] | None = None) -> dict[str, Any]:
    """Leftover Entry Jam / Style / Catalog / Custom / Composition residue."""
    payload = example if example is not None else _example_payload()
    jam_blob = WorkflowStateBlob(
        workflow_owner="jam_session_generator",
        workflow_session_id="jam-stale",
        keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        selected_chord_symbol="C",
        selected_section="A",
        section_map={"A": ["C", "F", "G"]},
    )
    session: dict[str, Any] = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "improv_entry_mode": "Jam Session Generator",
        "improv_jam_session": {"id": "jam-stale", "title": "Stale jam"},
        "improv_style": "Pop groove",
        "active_catalog_pick_key": "Pop::Shape of You — Ed Sheeran",
        "explicit_music_source_choice": "catalog",
        "composition_active_song_id": "comp-stale",
        "instrument": "Piano",
        "level": "Intermediate",
        "backing_track_bpm": 100,
        "improv_groove": "Auto",
        "backing_time_signature": "4/4",
        "display_key": "G minor",
        "concert_key": "G minor",
        "original_key": "G minor",
        "improv_active_mission": "Outline chord tones",
        "improv_mission_pick": "Outline chord tones",
        "ii_selected_chord": "Gm",
        "ii_selected_section": "Verse",
        "ii_selected_chord_index": 0,
        "ii_selected_chord_label": "Verse · Gm",
        MISSION_EXAMPLE_KEY: copy.deepcopy(payload),
        "_streamlit_widgets_locked_this_run": True,
    }
    save_workflow_blob(session, jam_blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-stale"),
        source="test",
    )
    return session


def _assert_example_A(test: unittest.TestCase, raw: Any) -> None:
    test.assertIsInstance(raw, dict)
    assert isinstance(raw, dict)
    motif = raw.get("motif") if isinstance(raw.get("motif"), dict) else {}
    test.assertEqual(raw.get("mission"), "Outline chord tones")
    test.assertEqual(str(raw.get("chord") or ""), "Gm")
    test.assertEqual(motif.get("notes"), RECOGNIZABLE_NOTES)
    test.assertEqual(motif.get("midi"), RECOGNIZABLE_MIDI)
    test.assertEqual(motif.get("rhythm"), RECOGNIZABLE_RHYTHM)
    test.assertEqual(raw.get("seed"), "mission-example-A")
    test.assertEqual(raw.get("idea_index"), 3)
    test.assertEqual(raw.get("vocab"), "chord_tones")
    test.assertEqual(raw.get("development"), "sequence")


class TestMissionBackingArtifactLifecycle(unittest.TestCase):
    def test_alignment_does_not_call_chord_tile_handler(self) -> None:
        session = _polluted_session()
        align = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord="Gm",
            section_label="Verse",
            chord_idx=0,
            song_title="Song",
            concert_key="G minor",
            display_key="G minor",
            with_practice_lick=True,
        )
        with mock.patch(
            "creative_mission_config_persistence.handle_user_mission_target_selection"
        ) as tile:
            ok = apply_pending_mission_backing_alignment(session, align)
        self.assertTrue(ok)
        tile.assert_not_called()
        _assert_example_A(self, session.get(MISSION_EXAMPLE_KEY))
        self.assertEqual(session.get("ii_selected_chord"), "Gm")

    def test_handoff_aligned_preserves_example_when_jam_blob_is_active(self) -> None:
        session = _polluted_session()
        result = mutate_mission_handoff_aligned(
            session,
            mission="Outline chord tones",
            cur_chord="Gm",
            section_label="Verse",
            chord_idx=0,
            example=SimpleNamespace(chord="Gm"),
        )
        self.assertTrue(result.ok)
        _assert_example_A(self, session.get(MISSION_EXAMPLE_KEY))
        self.assertTrue(session.get("improv_mission_backing_handoff") in (None, True))

    def test_click_rerun_apply_keeps_example_and_mission_handoff_flag(self) -> None:
        session = _polluted_session()
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=True,
            mission="Outline chord tones",
            cur_chord="Gm",
            section_label="Verse",
            chord_idx=0,
            song_title="Song",
            concert_key="G minor",
            display_key="G minor",
        )
        self.assertTrue(session.get("improv_mission_backing_handoff"))
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
            ok = apply_mission_backing_click_intent(session, st_module=mock.Mock())
        self.assertTrue(ok)
        _assert_example_A(self, session.get(MISSION_EXAMPLE_KEY))
        self.assertTrue(session.get("improv_mission_backing_handoff"))
        self.assertEqual(str(session.get("_backing_explicit_handoff_source") or ""), "mission")

    def test_envelope_after_click_apply_still_sees_example_chord(self) -> None:
        from active_musical_workflow_envelope import apply_mission_workflow_envelope_reconciliation

        session = _polluted_session()
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=True,
            mission="Outline chord tones",
            cur_chord="Gm",
            section_label="Verse",
            chord_idx=0,
            song_title="Song",
            concert_key="G minor",
            display_key="G minor",
        )
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
            self.assertTrue(apply_mission_backing_click_intent(session, st_module=mock.Mock()))
        _assert_example_A(self, session.get(MISSION_EXAMPLE_KEY))
        apply_mission_workflow_envelope_reconciliation(session)
        _assert_example_A(self, session.get(MISSION_EXAMPLE_KEY))

    def test_chord_tile_still_clears_example_on_explicit_retarget(self) -> None:
        from creative_mission_config_persistence import handle_user_mission_target_selection

        session = _polluted_session()
        with mock.patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ):
            handle_user_mission_target_selection(
                session,
                chord="Cm",
                section="Chorus",
                chord_index=2,
                chord_label="Chorus · Cm",
                button_key="tile",
            )
        self.assertIsNone(session.get(MISSION_EXAMPLE_KEY))

    def test_polluted_pk_change_does_not_reclaim_jam_generator(self) -> None:
        from backing_owner_envelope import OWNER_MISSION, get_backing_owner_envelope, live_backing_owner
        from backing_practice_key_control import commit_backing_practice_key
        from mission_owner_contract import live_backing_owner_is_mission

        session = _polluted_session()
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=True,
            mission="Outline chord tones",
            cur_chord="Gm",
            section_label="Verse",
            chord_idx=0,
            song_title="Song",
            concert_key="G minor",
            display_key="G minor",
        )
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
            self.assertTrue(apply_mission_backing_click_intent(session, st_module=mock.Mock()))
        session["studio_page"] = "backing"
        session["backing_context"] = {
            "source": "mission",
            "source_label": "Mission Backing",
            "key": "G minor",
            "display_key": "G minor",
            "concert_key": "G minor",
            "entry_mode": "Jam Session Generator",
        }
        commit_backing_practice_key(session, "A minor")
        self.assertTrue(live_backing_owner_is_mission(session))
        self.assertEqual(live_backing_owner(session), OWNER_MISSION)
        env = get_backing_owner_envelope(session)
        self.assertIsNotNone(env)
        assert env is not None
        self.assertEqual(env.source, OWNER_MISSION)
        self.assertNotIn("Jam Session Generator", str(session.get("backing_context", {}).get("source_label") or ""))
        raw = session.get(MISSION_EXAMPLE_KEY)
        self.assertIsInstance(raw, dict)
        assert isinstance(raw, dict)
        self.assertEqual(raw.get("mission"), "Outline chord tones")
        self.assertEqual(raw.get("seed"), "mission-example-A")
        self.assertEqual(raw.get("vocab"), "chord_tones")
        # G minor → A minor may reproject the chord; ownership must stay Mission.
        self.assertIn(str(raw.get("chord") or ""), {"Gm", "Am"})
        motif = raw.get("motif") if isinstance(raw.get("motif"), dict) else {}
        self.assertTrue(motif.get("notes"))
        self.assertTrue(motif.get("midi") or motif.get("rhythm"))

    def test_stale_contexts_do_not_clear_example_on_mission_backing_open(self) -> None:
        leftovers = (
            {"improv_entry_mode": "Jam Session Generator"},
            {"improv_entry_mode": "Style Jam Mode", "improv_style": "Pop groove"},
            {"active_catalog_pick_key": "Pop::Shape of You — Ed Sheeran", "explicit_music_source_choice": "catalog"},
            {"explicit_music_source_choice": "custom", "active_catalog_pick_key": "custom::trial-d"},
            {"composition_active_song_id": "comp-stale", "_force_composition_backing_open": True},
        )
        for extra in leftovers:
            with self.subTest(extra=extra):
                session = _polluted_session()
                session.update(extra)
                capture_mission_backing_click_intent(
                    session,
                    with_practice_lick=True,
                    mission="Outline chord tones",
                    cur_chord="Gm",
                    section_label="Verse",
                    chord_idx=0,
                    song_title="Song",
                    concert_key="G minor",
                    display_key="G minor",
                )
                with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
                    self.assertTrue(apply_mission_backing_click_intent(session, st_module=mock.Mock()))
                _assert_example_A(self, session.get(MISSION_EXAMPLE_KEY))
                self.assertEqual(str(session.get("_backing_explicit_handoff_source") or ""), "mission")

    def test_return_destination_seal_still_has_example_A(self) -> None:
        from improvisation_intelligence import ImprovSessionContext
        from improvisation_missions import load_mission_example
        from mission_return_destination import build_mission_return_destination, seal_mission_return_destination
        from music_workflow_pending_backing_handoff import (
            arm_pending_backing_handoff_consume,
            consume_pending_backing_workflow_handoff,
            peek_pending_backing_workflow_handoff,
        )

        session = _polluted_session()
        capture_mission_backing_click_intent(
            session,
            with_practice_lick=True,
            mission="Outline chord tones",
            cur_chord="Gm",
            section_label="Verse",
            chord_idx=0,
            song_title="Song",
            concert_key="G minor",
            display_key="G minor",
        )
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
            self.assertTrue(apply_mission_backing_click_intent(session, st_module=mock.Mock()))
        pending = peek_pending_backing_workflow_handoff(session)
        self.assertIsInstance(pending, dict)
        arm_pending_backing_handoff_consume(session)
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("backing_context.open_backing_from_creative"):
                with mock.patch("mission_backing_handoff_persistence.arm_mission_backing_handoff_page_change"):
                    phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "applied")
        _assert_example_A(self, session.get(MISSION_EXAMPLE_KEY))
        dest = build_mission_return_destination(
            session.get("_mission_pending_backing_alignment")
            or build_mission_backing_alignment_payload(
                session,
                mission="Outline chord tones",
                cur_chord="Gm",
                section_label="Verse",
                chord_idx=0,
                song_title="Song",
                concert_key="G minor",
                display_key="G minor",
                with_practice_lick=True,
            ),
            handoff_mode="practice_in_jam",
            with_practice_lick=True,
        )
        seal_mission_return_destination(session, dest)
        ctx = ImprovSessionContext(
            song_title="Song",
            artist="",
            key_center="G minor",
            display_key="G minor",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={},
        )
        loaded = load_mission_example(session, ctx)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.mission, "Outline chord tones")
        self.assertEqual(loaded.chord, "Gm")
        motif = loaded.motif if isinstance(loaded.motif, dict) else {}
        self.assertEqual(motif.get("notes"), RECOGNIZABLE_NOTES)
        self.assertEqual(motif.get("midi"), RECOGNIZABLE_MIDI)


_HARNESS = '''
import streamlit as st
from improvisation_missions import MISSION_EXAMPLE_KEY
from music_workflow_mission_backing_click import (
    apply_mission_backing_click_intent,
    capture_mission_backing_click_intent,
    peek_mission_backing_click_intent,
)

ss = st.session_state
if MISSION_EXAMPLE_KEY not in ss:
    ss[MISSION_EXAMPLE_KEY] = {
        "mission": "Outline chord tones",
        "variant": "normal",
        "chord": "Gm",
        "section": "Verse",
        "concert_key": "G minor",
        "display_key": "G minor",
        "seed": "mission-example-A",
        "idea_index": 3,
        "vocab": "chord_tones",
        "development": "sequence",
        "motif": {
            "notes": ["G", "Bb", "D", "F"],
            "midi": [67, 70, 74, 77],
            "rhythm": "quarter quarter quarter quarter",
            "_concert_chord": "Gm",
        },
        "abc": "X:1",
        "tab": "",
        "piano_html": "",
        "why": "example A",
        "practice_steps": [],
        "show_tab": False,
        "show_piano": True,
    }
    ss["studio_page"] = "creative"
    ss["improv_intelligence_tab"] = "Missions"
    ss["improv_entry_mode"] = "Jam Session Generator"
    ss["instrument"] = "Piano"
    ss["backing_track_bpm"] = 100
    ss["improv_groove"] = "Auto"
    ss["backing_time_signature"] = "4/4"
    ss["improv_active_mission"] = "Outline chord tones"
    ss["ii_selected_chord"] = "Gm"
    ss["ii_selected_section"] = "Verse"
    ss["ii_selected_chord_index"] = 0

if peek_mission_backing_click_intent(ss):
    apply_mission_backing_click_intent(ss, st_module=st)

def _on_click():
    capture_mission_backing_click_intent(
        ss,
        with_practice_lick=True,
        mission="Outline chord tones",
        cur_chord="Gm",
        section_label="Verse",
        chord_idx=0,
        song_title="Song",
        concert_key="G minor",
        display_key="G minor",
    )

st.button("Mission Backing", key="improv_mission_over_backing_bottom", on_click=_on_click)
raw = ss.get(MISSION_EXAMPLE_KEY) if isinstance(ss.get(MISSION_EXAMPLE_KEY), dict) else {}
st.write("example_seed", raw.get("seed"))
st.write("example_notes", (raw.get("motif") or {}).get("notes") if isinstance(raw.get("motif"), dict) else None)
'''


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestMissionBackingArtifactAppTest(unittest.TestCase):
    def test_button_click_rerun_keeps_example_A(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_string(_HARNESS, default_timeout=60)
        at.run()
        btn = at.button(key="improv_mission_over_backing_bottom")
        btn.click().run()
        raw = at.session_state[MISSION_EXAMPLE_KEY]
        self.assertIsInstance(raw, dict)
        assert isinstance(raw, dict)
        self.assertEqual(raw.get("seed"), "mission-example-A")
        motif = raw.get("motif") if isinstance(raw.get("motif"), dict) else {}
        self.assertEqual(motif.get("notes"), RECOGNIZABLE_NOTES)
        self.assertEqual(motif.get("midi"), RECOGNIZABLE_MIDI)
        self.assertTrue(at.session_state["improv_mission_backing_handoff"])


if __name__ == "__main__":
    unittest.main()
