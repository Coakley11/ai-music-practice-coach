"""Practice-plan personalization and insight status copy tests."""

from __future__ import annotations

import re
import unittest

from music_coach_ami.pipeline import run_coach_pipeline
from music_coach_ami.router import CoachIntent, route_question


def _sum_minutes(steps: list[str]) -> int:
    total = 0
    for step in steps:
        m = re.search(r"\*\*(\d+)\s*min\*\*", step)
        if m:
            total += int(m.group(1))
    return total


class InsightStatusCopyTests(unittest.TestCase):
    def test_no_ready_below_in_repo(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        hits: list[str] = []
        for path in root.rglob("*.py"):
            if "test_" in path.name or ".pytest_cache" in str(path):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "Music Coach insight is ready below." in text:
                hits.append(str(path.relative_to(root)))
        self.assertEqual(hits, [])

    def test_ready_on_this_page_present(self) -> None:
        from pathlib import Path

        text = Path(__file__).resolve().parents[1].joinpath("suite_analytical_question.py").read_text(encoding="utf-8")
        self.assertIn("Music Coach insight is ready on this page.", text)


class PracticePlanPersonalizationTests(unittest.TestCase):
    def _ctx(
        self,
        *,
        instrument: str = "",
        level: str = "",
        focus: str = "",
        log: dict | None = None,
        song: str = "",
        section: str = "",
    ) -> dict:
        ami: dict = {}
        if instrument:
            ami["instrument"] = instrument
        if level:
            ami["level"] = level
        if focus:
            ami["focus"] = focus
        if log:
            ami["practice_log_summary"] = log
        if song:
            ami["active_song"] = {"title": song}
        if section:
            ami["practice_focus_section"] = section
        return ami

    def test_flute_tone_history_personalized(self) -> None:
        resp = run_coach_pipeline(
            "What should I practice today?",
            {},
            ami_ctx=self._ctx(
                instrument="Flute",
                level="Intermediate",
                focus="Tone",
                song="Autumn Leaves",
                log={
                    "session_count": 4,
                    "repeated_challenge": "upper register thin",
                    "last_session_summary": {
                        "active_song": "Autumn Leaves",
                        "focus_area": "Tone",
                        "what_was_hard": "upper register thin",
                    },
                },
            ),
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.PRACTICE_PLAN)
        text = resp.composed_markdown().lower()
        self.assertIn("flute", text)
        self.assertIn("tone", text)
        self.assertIn("register", text)
        self.assertTrue(resp.diagnostics.get("practice_history_available"))

    def test_piano_harmony_thirty_minutes(self) -> None:
        resp = run_coach_pipeline(
            "Give me a 30-minute practice routine.",
            {},
            ami_ctx=self._ctx(
                instrument="Piano",
                level="Advanced",
                focus="Harmony",
                log={
                    "session_count": 3,
                    "repeated_challenge": "voicing transitions",
                    "last_session_summary": {"focus_area": "Harmony", "what_was_hard": "voicing transitions"},
                },
            ),
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.PRACTICE_PLAN)
        steps = resp.practice_steps
        if steps:
            self.assertEqual(_sum_minutes(steps), 30)
        text = resp.composed_markdown().lower()
        self.assertIn("piano", text)
        self.assertTrue("voicing" in text or "harmony" in text)
        self.assertNotIn("long tones", text)

    def test_explicit_articulation_overrides_history(self) -> None:
        resp = run_coach_pipeline(
            "Give me a 20-minute articulation practice session on flute.",
            {},
            ami_ctx=self._ctx(
                instrument="Flute",
                level="Intermediate",
                focus="Tone",
                log={
                    "session_count": 5,
                    "repeated_challenge": "tone in upper register",
                    "last_session_summary": {"next_step": "work on tone slowly"},
                },
            ),
        )
        assert resp is not None
        text = resp.composed_markdown().lower()
        self.assertEqual(_sum_minutes(resp.practice_steps), 20)
        self.assertIn("articulation", resp.composed_markdown().lower())
        self.assertTrue(resp.diagnostics.get("explicit_request_overrides_history"))

    def test_history_bridge_next_step(self) -> None:
        resp = run_coach_pipeline(
            "What should I work on today?",
            {},
            ami_ctx=self._ctx(
                instrument="Flute",
                level="Intermediate",
                log={
                    "session_count": 2,
                    "last_session_summary": {
                        "active_song": "Blue Bossa",
                        "next_step": "Next time: work on bridge slowly",
                        "section_practiced": "Bridge",
                    },
                },
            ),
        )
        assert resp is not None
        text = resp.composed_markdown().lower()
        self.assertIn("bridge", text)
        self.assertIn("why:", text)

    def test_no_history_fallback(self) -> None:
        resp = run_coach_pipeline(
            "What should I practice today?",
            {},
            ami_ctx=self._ctx(instrument="Flute", level="Intermediate", focus="Tone"),
        )
        assert resp is not None
        text = resp.composed_markdown().lower()
        self.assertIn("flute", text)
        self.assertNotIn("your history shows", text)
        self.assertFalse(resp.diagnostics.get("practice_history_available"))

    def test_practice_plan_routing(self) -> None:
        self.assertEqual(
            route_question("What should I practice today?", {}).intent,
            CoachIntent.PRACTICE_PLAN,
        )


class RepertoirePersonalizationTests(unittest.TestCase):
    def test_daily_song_not_auto_improv_mode(self) -> None:
        resp = run_coach_pipeline("What song should I practice today?", {})
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.REPERTOIRE_RECOMMENDATION)
        self.assertNotIn("goal_improv_singular", resp.source_solver)

    def test_daily_song_uses_history(self) -> None:
        resp = run_coach_pipeline(
            "What song should I practice today?",
            {},
            ami_ctx={
                "practice_log_summary": {
                    "session_count": 2,
                    "last_session_summary": {
                        "active_song": "Autumn Leaves",
                        "next_step": "Next time: work on bridge slowly",
                    },
                },
            },
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Autumn Leaves", text)
        self.assertIn("RepertoireSolver(daily_continue)", resp.source_solver)

    def test_improv_song_question_still_improv(self) -> None:
        resp = run_coach_pipeline(
            "What song should I practice today to improve improvisation?",
            {},
        )
        assert resp is not None
        self.assertIn("goal_improv", resp.source_solver)


if __name__ == "__main__":
    unittest.main()
