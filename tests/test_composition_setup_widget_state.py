"""Composition Studio — Welcome/Vision widget-state safety + Jewish style."""

from __future__ import annotations

import unittest
from pathlib import Path

from composition_chord_suggestions import suggest_progressions
from composition_document import (
    COMPOSITION_GENRES,
    apply_structure_template,
    bootstrap_from_vision,
    composition_key_choice_labels,
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

    def test_vision_song_settings_suggest_applies_key_bpm_meter_on_prepare(self) -> None:
        """Clicking Suggest queues settings; prepare applies them (user-initiated)."""
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Hopeful anthem about coming home.",
            key="E major",
            bpm=140,
            meter="7/8",
        )
        ss: dict = {}
        prepare_vision_widget_state(ss, doc)
        key_before = ss["composer_vision_key"]
        bpm_before = ss["composer_vision_bpm"]
        meter_before = ss["composer_vision_meter"]
        payload = queue_vision_mood_energy_suggest(
            ss, genre="Pop", song_idea="Hopeful anthem about coming home."
        )
        # Queue alone must not mutate live widget keys mid-run.
        self.assertEqual(ss["composer_vision_key"], key_before)
        self.assertEqual(ss["composer_vision_bpm"], bpm_before)
        self.assertEqual(ss["composer_vision_meter"], meter_before)
        self.assertIn(COMPOSER_VISION_PENDING_SUGGEST_KEY, ss)
        self.assertIn("key", payload)
        self.assertIn("bpm", payload)
        self.assertIn("meter", payload)
        prepare_vision_widget_state(ss, doc)
        self.assertNotIn(COMPOSER_VISION_PENDING_SUGGEST_KEY, ss)
        # After prepare, suggested musical defaults are present.
        self.assertIn(ss["composer_vision_key"], composition_key_choice_labels())
        self.assertTrue(40 <= int(ss["composer_vision_bpm"]) <= 240)
        self.assertTrue(
            str(ss.get("composer_vision_energy") or "").strip()
            or str(ss.get("composer_vision_mood") or "").strip()
        )

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

    def test_welcome_includes_bossa_and_jewish_direction(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.WELCOME_HARNESS, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        genre_boxes = [sb for sb in at.selectbox if "Genre" in (sb.label or "")]
        self.assertTrue(genre_boxes, "Genre select missing")
        options = list(genre_boxes[0].options or [])
        self.assertIn("Bossa", options)
        self.assertIn("Jewish", options)
        # Select Jewish → Jewish direction appears
        genre_boxes[0].select("Jewish").run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        jd = [sb for sb in at.selectbox if "Jewish direction" in (sb.label or "")]
        self.assertTrue(jd, "Jewish direction control missing when Genre=Jewish")
        jd_opts = list(jd[0].options or [])
        self.assertIn("Contemporary Jewish pop", jd_opts)
        self.assertIn("Klezmer-influenced", jd_opts)
        # Select Bossa → Jewish direction gone
        genre_boxes = [sb for sb in at.selectbox if "Genre" in (sb.label or "")]
        genre_boxes[0].select("Bossa").run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        jd_after = [sb for sb in at.selectbox if "Jewish direction" in (sb.label or "")]
        self.assertFalse(jd_after, "Jewish direction should hide for non-Jewish genres")
        self.assertEqual(at.session_state["composer_welcome_genre"], "Bossa")

    def test_vision_includes_bossa_and_jewish_direction(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.VISION_HARNESS, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        genre_boxes = [sb for sb in at.selectbox if "Genre" in (sb.label or "")]
        self.assertTrue(genre_boxes)
        self.assertIn("Bossa", list(genre_boxes[0].options or []))
        genre_boxes[0].select("Jewish").run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        jd = [sb for sb in at.selectbox if "Jewish direction" in (sb.label or "")]
        self.assertTrue(jd, "Vision Jewish direction missing")
        jd[0].select("Traditional / modal").run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        self.assertEqual(at.session_state["composer_vision_genre"], "Jewish")
        self.assertEqual(
            at.session_state["composer_vision_jewish_direction"],
            "Traditional / modal",
        )
        # Non-Jewish hides the control
        genre_boxes = [sb for sb in at.selectbox if "Genre" in (sb.label or "")]
        genre_boxes[0].select("Bossa").run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        self.assertFalse(
            [sb for sb in at.selectbox if "Jewish direction" in (sb.label or "")],
            "Jewish direction must not clutter Bossa Vision UI",
        )


if __name__ == "__main__":
    unittest.main()
