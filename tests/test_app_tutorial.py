"""Truth-based tests for the musician-facing tutorial (dev product surface)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from app_tutorial import (
    EXPLORE_MORE_IDS,
    QUICK_TOUR_IDS,
    TOTAL_STEPS,
    TUTORIAL_STEPS,
    _VALID_NAV_PAGE_IDS,
    close_tutorial,
    complete_tutorial,
    init_tutorial_state,
    open_tutorial,
    render_tutorial_walkthrough,
    step_index_for_page,
    tutorial_chapter_ids,
    tutorial_entry_visible,
    tutorial_nav_page_ids,
)
from practice_setup_controls import DEFAULT_INSTRUMENT_OPTIONS, FOCUS_OPTIONS_BY_INSTRUMENT
from practice_tools_ui import PRACTICE_TOOLS
from studio_page_state import IMPROV_ENTRY_MODES, IMPROV_TAB_NAMES


def _flatten_tutorial_text() -> str:
    chunks: list[str] = []
    for step in TUTORIAL_STEPS:
        for key in ("title", "summary", "try_this", "why", "script"):
            chunks.append(str(step.get(key) or ""))
        for bullet in step.get("bullets") or []:
            chunks.append(str(bullet))
        for q in step.get("questions") or []:
            chunks.append(str(q))
        for item in step.get("journey") or []:
            chunks.append(str(item))
        for card in step.get("cards") or []:
            chunks.append(str(card.get("title") or ""))
            chunks.append(str(card.get("body") or ""))
        for section in step.get("sections") or []:
            chunks.append(str(section.get("title") or ""))
            for bullet in section.get("bullets") or []:
                chunks.append(str(bullet))
    return "\n".join(chunks)


def _primary_text() -> str:
    """Visible first-screen copy only (no Learn more expanders)."""
    chunks: list[str] = []
    for step in TUTORIAL_STEPS:
        for key in ("title", "summary", "try_this", "why", "script"):
            chunks.append(str(step.get(key) or ""))
        for bullet in step.get("bullets") or []:
            chunks.append(str(bullet))
        for q in step.get("questions") or []:
            chunks.append(str(q))
        for item in step.get("journey") or []:
            chunks.append(str(item))
        for card in step.get("cards") or []:
            chunks.append(str(card.get("title") or ""))
            chunks.append(str(card.get("body") or ""))
    return "\n".join(chunks)


class TutorialStructureTests(unittest.TestCase):
    def test_chapter_count_and_ids_unique(self) -> None:
        ids = tutorial_chapter_ids()
        self.assertEqual(len(ids), TOTAL_STEPS)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(TOTAL_STEPS, 12)

    def test_quick_tour_then_explore_more(self) -> None:
        ids = tutorial_chapter_ids()
        self.assertEqual(tuple(ids[: len(QUICK_TOUR_IDS)]), QUICK_TOUR_IDS)
        self.assertEqual(tuple(ids[len(QUICK_TOUR_IDS) :]), EXPLORE_MORE_IDS)
        self.assertEqual(len(QUICK_TOUR_IDS), 8)
        self.assertIn("karaoke", EXPLORE_MORE_IDS)
        self.assertIn("creative", EXPLORE_MORE_IDS)

    def test_required_chapters_present(self) -> None:
        required = {
            "welcome",
            "setup",
            "music",
            "keys",
            "practice",
            "backing",
            "karaoke",
            "creative",
            "composer",
            "coach",
            "recording",
            "log",
            "saving",
            "which_tool",
        }
        self.assertTrue(required.issubset(set(tutorial_chapter_ids())))

    def test_nav_page_ids_are_valid_studio_pages(self) -> None:
        for page_id in tutorial_nav_page_ids():
            self.assertIn(page_id, _VALID_NAV_PAGE_IDS)

    def test_step_index_for_page_maps_known_pages(self) -> None:
        self.assertIsNotNone(step_index_for_page("picker"))
        self.assertIsNotNone(step_index_for_page("practice"))
        self.assertIsNotNone(step_index_for_page("creative"))
        self.assertIsNone(step_index_for_page("not_a_page"))

    def test_primary_steps_are_not_walls_of_text(self) -> None:
        for step in TUTORIAL_STEPS:
            bullets = list(step.get("bullets") or [])
            self.assertLessEqual(
                len(bullets),
                4,
                f"{step['id']} shows too many primary bullets",
            )


class TutorialContentTruthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _flatten_tutorial_text()
        cls.primary = _primary_text()

    def test_creative_tabs_named_match_app(self) -> None:
        for tab in IMPROV_TAB_NAMES:
            self.assertIn(tab, self.text, f"missing Creative tab: {tab}")

    def test_creative_entry_modes_named_match_app(self) -> None:
        for mode in IMPROV_ENTRY_MODES:
            self.assertIn(mode, self.text, f"missing Entry mode: {mode}")

    def test_practice_tools_named_match_app(self) -> None:
        for tool in PRACTICE_TOOLS:
            self.assertIn(tool.label, self.text, f"missing Practice tool: {tool.label}")

    def test_instruments_include_voice_and_winds(self) -> None:
        for name in ("Piano", "Guitar", "Bass", "Saxophone", "Flute", "Clarinet", "Voice"):
            self.assertIn(name, DEFAULT_INSTRUMENT_OPTIONS)
            self.assertIn(name, self.text)

    def test_voice_focus_options_mentioned(self) -> None:
        voice_focus = FOCUS_OPTIONS_BY_INSTRUMENT["Voice"]
        for focus in ("Breath Control", "Phrasing", "Pitch Accuracy"):
            self.assertIn(focus, voice_focus)
            self.assertIn(focus, self.text)

    def test_karaoke_path_and_vocal_performance_mode(self) -> None:
        self.assertIn("Karaoke Performance Setlist", self.text)
        self.assertIn("Vocal Performance Mode", self.text)
        self.assertIn("no separate", self.text.lower())

    def test_catalog_vs_custom_save_language(self) -> None:
        self.assertIn("Save corrected chart", self.text)
        self.assertIn("Save Lyrics & Cues", self.text)
        self.assertIn("Save to library", self.text)
        self.assertIn("Set as Active Song", self.text)
        self.assertIn("Load selected", self.text)
        self.assertIn("does not rewrite", self.text.lower())

    def test_keys_and_transposing_instruments(self) -> None:
        self.assertIn("Original Key", self.text)
        self.assertIn("Practice / Concert Key", self.text)
        self.assertIn("written key", self.text.lower())
        self.assertIn("Alto", self.text)
        self.assertIn("Tenor", self.text)
        self.assertIn("Capo", self.text)

    def test_upload_vs_multitrack_guidance(self) -> None:
        self.assertIn("Upload Analysis", self.text)
        self.assertIn("Multitrack", self.text)
        self.assertIn("one take", self.text.lower())
        self.assertIn("several parts", self.text.lower())

    def test_practice_log_actions(self) -> None:
        self.assertIn("Quick Save Practice Session", self.text)
        self.assertIn("Add Session Manually", self.text)
        self.assertIn("Analyze My Practice", self.text)
        self.assertIn("not every page auto-logs", self.text.lower())

    def test_ami_examples_are_musician_friendly(self) -> None:
        self.assertIn("What should I practice for 20 minutes today?", self.text)
        self.assertIn("Upload Analysis or Multitrack", self.text)
        self.assertNotIn("musical_idea_engine", self.text)
        self.assertNotIn("lick generator", self.text.lower())
        low = self.primary.lower()
        for banned in ("feature branch", "current dev", "solver", "canonical"):
            self.assertNotIn(banned, low)

    def test_no_developer_jargon(self) -> None:
        banned = (
            "session_state",
            "SSOT",
            "fingerprint",
            "JSON blob",
            "canonical object",
            "persistence blob",
            "solver registry",
            "feature branch",
            "source-of-truth",
        )
        low = self.text.lower()
        for term in banned:
            self.assertNotIn(term.lower(), low, f"developer jargon leaked: {term}")

    def test_no_obsolete_page_names(self) -> None:
        obsolete = (
            "Coach tab",
            "Timing tab",
            "AI Improvisation Metrics page",
            "Mission Upload Analysis page",
        )
        for name in obsolete:
            self.assertNotIn(name, self.text)

    def test_which_tool_includes_karaoke(self) -> None:
        which = next(s for s in TUTORIAL_STEPS if s["id"] == "which_tool")
        joined = " ".join(
            [str(c.get("title") or "") + " " + str(c.get("body") or "") for c in which.get("cards") or []]
        )
        self.assertIn("Voice", joined)
        self.assertIn("Karaoke", joined)

    def test_three_way_personalization_model(self) -> None:
        self.assertIn("Who are you playing as?", self.text)
        self.assertIn("How challenging should it be?", self.text)
        self.assertIn("What do you want to work on?", self.text)
        self.assertIn("Instrument", self.primary)
        self.assertIn("Level", self.primary)
        self.assertIn("Practice Focus", self.primary)

    def test_primary_copy_avoids_manual_tone(self) -> None:
        low = self.primary.lower()
        for phrase in (
            "valid studio page",
            "implementation",
            "subsystem",
            "domain resolution",
        ):
            self.assertNotIn(phrase, low)


class TutorialRenderAndStateTests(unittest.TestCase):
    def test_state_lifecycle(self) -> None:
        ss: dict[str, Any] = {}
        init_tutorial_state(ss)
        self.assertTrue(tutorial_entry_visible(ss))
        open_tutorial(ss, reset_step=True)
        self.assertTrue(ss["tutorial_open"])
        self.assertEqual(ss["tutorial_step"], 0)
        close_tutorial(ss)
        self.assertFalse(ss["tutorial_open"])
        self.assertTrue(tutorial_entry_visible(ss))
        complete_tutorial(ss)
        self.assertFalse(tutorial_entry_visible(ss))

    def test_render_all_chapters_without_crash(self) -> None:
        st = MagicMock()
        expander = MagicMock()
        expander.__enter__ = MagicMock(return_value=expander)
        expander.__exit__ = MagicMock(return_value=False)
        st.expander.return_value = expander

        def _columns(spec: Any, *args: Any, **kwargs: Any) -> list[Any]:
            n = len(spec) if isinstance(spec, (list, tuple)) else int(spec or 1)
            cols = []
            for _ in range(n):
                col = MagicMock()
                col.__enter__ = MagicMock(return_value=col)
                col.__exit__ = MagicMock(return_value=False)
                cols.append(col)
            return cols

        st.columns.side_effect = _columns
        st.button.return_value = False
        st.checkbox.return_value = False

        for i in range(TOTAL_STEPS):
            ss: dict[str, Any] = {
                "tutorial_dismissed": False,
                "tutorial_open": True,
                "tutorial_step": i,
            }
            render_tutorial_walkthrough(
                st,
                ss,
                rerun_fn=lambda: None,
                navigate_fn=lambda _pid: None,
            )
        self.assertGreaterEqual(st.markdown.call_count, TOTAL_STEPS)


if __name__ == "__main__":
    unittest.main()
