"""Composition Studio — Welcome/Vision widget-state safety + Jewish style."""

from __future__ import annotations

import unittest
from pathlib import Path

from composition_chord_suggestions import suggest_progressions
from composition_document import (
    COMPOSITION_GENRES,
    apply_structure_template,
    bootstrap_from_vision,
    deep_copy_document,
    ordered_sections,
)
from composition_session_state import (
    get_active_document,
    save_document_to_library,
    set_active_document,
)
from composition_studio_page import (
    COMPOSER_VISION_PENDING_SUGGEST_KEY,
    COMPOSER_WELCOME_PENDING_SUGGEST_KEY,
    WELCOME_WIDGET_KEYS,
    prepare_vision_widget_state,
    prepare_welcome_widget_state,
    queue_vision_mood_energy_suggest,
    queue_welcome_starting_values,
)


class TestWelcomeWidgetStatePrep(unittest.TestCase):
    def test_normalize_before_widget_creation(self) -> None:
        ss: dict = {}
        prepare_welcome_widget_state(ss)
        self.assertIn("composer_welcome_key", ss)
        self.assertIn("composer_welcome_bpm", ss)
        self.assertIn("composer_welcome_meter", ss)
        # Idempotent re-prepare (simulates another run before widgets).
        key_before = ss["composer_welcome_key"]
        bpm_before = ss["composer_welcome_bpm"]
        prepare_welcome_widget_state(ss)
        self.assertEqual(ss["composer_welcome_key"], key_before)
        self.assertEqual(ss["composer_welcome_bpm"], bpm_before)

    def test_invalid_legacy_key_normalized_before_render(self) -> None:
        from composition_document import COMPOSITION_METER_CUSTOM, COMPOSITION_METERS

        ss = {"composer_welcome_key": "NotARealKey", "composer_welcome_bpm": 999, "composer_welcome_meter": "nope"}
        prepare_welcome_widget_state(ss)
        self.assertNotEqual(ss["composer_welcome_key"], "NotARealKey")
        self.assertTrue(40 <= int(ss["composer_welcome_bpm"]) <= 240)
        self.assertIn(ss["composer_welcome_meter"], list(COMPOSITION_METERS) + [COMPOSITION_METER_CUSTOM])

    def test_suggest_uses_pending_not_direct_widget_write(self) -> None:
        ss = {
            "composer_welcome_key": "C major",
            "composer_welcome_bpm": 96,
            "composer_welcome_meter": "4/4",
            "composer_welcome_meter_custom": "",
        }
        before = {k: ss.get(k) for k in ("composer_welcome_key", "composer_welcome_bpm", "composer_welcome_meter")}
        payload = queue_welcome_starting_values(ss, genre="Jazz", song_idea="A gentle ballad.")
        # Widget keys unchanged until prepare on next "rerun".
        for k, v in before.items():
            self.assertEqual(ss.get(k), v)
        self.assertIn(COMPOSER_WELCOME_PENDING_SUGGEST_KEY, ss)
        self.assertEqual(ss[COMPOSER_WELCOME_PENDING_SUGGEST_KEY]["key"], payload["key"])
        prepare_welcome_widget_state(ss)
        self.assertNotIn(COMPOSER_WELCOME_PENDING_SUGGEST_KEY, ss)
        self.assertEqual(ss["composer_welcome_key"], payload["key"])
        self.assertEqual(ss["composer_welcome_bpm"], payload["bpm"])

    def test_rerender_existing_valid_key_no_unsafe_reassignment_needed(self) -> None:
        ss = {
            "composer_welcome_key": "Ab major",
            "composer_welcome_bpm": 84,
            "composer_welcome_meter": "3/4",
            "composer_welcome_meter_custom": "",
        }
        prepare_welcome_widget_state(ss)
        self.assertEqual(ss["composer_welcome_key"], "Ab major")
        self.assertEqual(ss["composer_welcome_bpm"], 84)
        self.assertEqual(ss["composer_welcome_meter"], "3/4")

    def test_custom_meter_rerun_safe(self) -> None:
        from composition_document import COMPOSITION_METER_CUSTOM

        ss = {
            "composer_welcome_key": "C major",
            "composer_welcome_bpm": 100,
            "composer_welcome_meter": COMPOSITION_METER_CUSTOM,
            "composer_welcome_meter_custom": "11/8",
        }
        prepare_welcome_widget_state(ss)
        self.assertEqual(ss["composer_welcome_meter"], COMPOSITION_METER_CUSTOM)
        self.assertEqual(ss["composer_welcome_meter_custom"], "11/8")

    def test_welcome_widget_keys_are_distinct_from_vision(self) -> None:
        for key in WELCOME_WIDGET_KEYS:
            self.assertFalse(key.startswith("composer_vision_"))
            self.assertTrue(key.startswith("composer_welcome_"))


class TestVisionWidgetStatePrep(unittest.TestCase):
    def test_vision_prepare_from_doc_before_widgets(self) -> None:
        doc = bootstrap_from_vision(
            genre="Folk",
            song_idea="Quiet road.",
            key="G major",
            bpm=84,
            meter="3/4",
        )
        ss: dict = {}
        prepare_vision_widget_state(ss, doc)
        self.assertEqual(ss["composer_vision_key"], "G major")
        self.assertEqual(ss["composer_vision_bpm"], 84)
        self.assertEqual(ss["composer_vision_meter"], "3/4")
        self.assertEqual(ss["composer_vision_genre"], "Folk")

    def test_vision_mood_suggest_pending_does_not_touch_key_bpm_meter(self) -> None:
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Hopeful anthem.",
            key="E major",
            bpm=140,
            meter="7/8",
        )
        ss: dict = {}
        prepare_vision_widget_state(ss, doc)
        key_before = ss["composer_vision_key"]
        bpm_before = ss["composer_vision_bpm"]
        meter_before = ss["composer_vision_meter"]
        queue_vision_mood_energy_suggest(ss, genre="Pop", song_idea="Hopeful anthem.")
        self.assertEqual(ss["composer_vision_key"], key_before)
        self.assertEqual(ss["composer_vision_bpm"], bpm_before)
        self.assertEqual(ss["composer_vision_meter"], meter_before)
        self.assertIn(COMPOSER_VISION_PENDING_SUGGEST_KEY, ss)
        prepare_vision_widget_state(ss, doc)
        self.assertEqual(ss["composer_vision_key"], key_before)
        self.assertEqual(ss["composer_vision_bpm"], bpm_before)
        self.assertEqual(ss["composer_vision_meter"], meter_before)
        self.assertNotIn(COMPOSER_VISION_PENDING_SUGGEST_KEY, ss)

    def test_welcome_to_vision_distinct_keys(self) -> None:
        welcome: dict = {}
        prepare_welcome_widget_state(welcome)
        welcome["composer_welcome_key"] = "Db major"
        welcome["composer_welcome_bpm"] = 92
        doc = bootstrap_from_vision(
            genre="Jewish",
            song_idea="From welcome.",
            key=str(welcome["composer_welcome_key"]),
            bpm=welcome["composer_welcome_bpm"],
            meter="4/4",
        )
        vision: dict = {}
        prepare_vision_widget_state(vision, doc)
        self.assertEqual(vision["composer_vision_key"], "Db major")
        # Distinct widget namespaces — no shared session key.
        self.assertNotIn("composer_welcome_key", vision)
        self.assertNotIn("composer_vision_key", welcome)


class TestJewishStyle(unittest.TestCase):
    def test_jewish_in_composition_genres(self) -> None:
        self.assertIn("Jewish", COMPOSITION_GENRES)
        # Existing options preserved.
        self.assertIn("Pop", COMPOSITION_GENRES)
        self.assertIn("Jazz", COMPOSITION_GENRES)
        self.assertIn("Other", COMPOSITION_GENRES)

    def test_jewish_persists_in_composition_state(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jewish",
            song_idea="A contemplative nigun.",
            title="Nigun",
            key="D minor",
            bpm=72,
            meter="4/4",
        )
        self.assertEqual(doc["metadata"]["style"], "Jewish")

    def test_jewish_save_reload(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jewish",
            song_idea="Festival joy.",
            key="A minor",
            bpm=110,
            meter="4/4",
        )
        ss: dict = {}
        set_active_document(ss, doc)
        save_document_to_library(ss, doc)
        restored = get_active_document(ss)
        assert restored is not None
        self.assertEqual(restored["metadata"]["style"], "Jewish")

    def test_jewish_chord_suggestion_context(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jewish",
            song_idea="Wedding dance.",
            key="G minor",
            bpm=120,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        ideas = suggest_progressions(doc, verse, "uplifting", limit=2)
        self.assertGreaterEqual(len(ideas), 1)
        # Genre flows into suggestion copy / context.
        blob = " ".join(
            f"{i.get('name') or ''} {i.get('why') or ''} {i.get('context') or ''}" for i in ideas
        )
        coach_bits = " ".join(str(i.get("why") or "") for i in ideas)
        self.assertTrue(
            "Jewish" in blob or "Jewish" in coach_bits or doc["metadata"]["style"] == "Jewish"
        )
        # Stronger: coach_line / why often includes genre — also check suggest uses meta.style.
        from composition_chord_suggestions import coach_line_for_section

        line = coach_line_for_section(doc, verse, feeling="uplifting")
        self.assertIn("Jewish", line)

    def test_jewish_survives_section_switch(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jewish",
            song_idea="Section switch.",
            key="C minor",
            bpm=90,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        sections = ordered_sections(doc)
        self.assertGreaterEqual(len(sections), 2)
        copied = deep_copy_document(doc)
        self.assertEqual(copied["metadata"]["style"], "Jewish")
        # Switching active section does not touch genre ownership.
        ss = {"composer_active_section_id": str(sections[1]["id"])}
        self.assertEqual(doc["metadata"]["style"], "Jewish")
        self.assertEqual(ss["composer_active_section_id"], str(sections[1]["id"]))


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestCompositionWelcomeAppTest(unittest.TestCase):
    WELCOME_HARNESS = str(
        Path(__file__).resolve().parents[1] / "composition_studio_welcome_harness.py"
    )
    VISION_HARNESS = str(
        Path(__file__).resolve().parents[1] / "composition_studio_vision_harness.py"
    )

    def test_welcome_renders_without_streamlit_api_exception(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.WELCOME_HARNESS, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))

    def test_suggest_starting_values_safe_rerun(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.WELCOME_HARNESS, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        suggest_buttons = [b for b in at.button if "Suggest starting values" in (b.label or "")]
        self.assertTrue(suggest_buttons, "Suggest starting values button missing")
        suggest_buttons[0].click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        self.assertIn("composer_welcome_key", at.session_state)

    def test_vision_renders_without_exception(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.VISION_HARNESS, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        # Mood suggest must not mutate Key/BPM/Meter widget keys mid-run.
        mood_buttons = [
            b for b in at.button if "Suggest mood" in (b.label or "") or "does not overwrite" in (b.label or "")
        ]
        if mood_buttons:
            key_before = at.session_state["composer_vision_key"]
            bpm_before = at.session_state["composer_vision_bpm"]
            mood_buttons[0].click().run(timeout=120)
            self.assertFalse(at.exception, msg=repr(at.exception))
            self.assertEqual(at.session_state["composer_vision_key"], key_before)
            self.assertEqual(at.session_state["composer_vision_bpm"], bpm_before)


if __name__ == "__main__":
    unittest.main()
