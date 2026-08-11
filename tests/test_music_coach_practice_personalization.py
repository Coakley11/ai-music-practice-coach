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

    def _bass_line_chart_ctx(
        self,
        *,
        instrument: str = "Guitar",
        level: str = "Intermediate",
        song: str = "Test Song",
        section: str = "Verse",
        display_key: str = "Ab",
        original_key: str = "Ab",
        chart_sections: dict[str, list[str]] | None = None,
    ) -> dict:
        sections = chart_sections or {
            "Verse": ["Fm7", "Bbm7", "Eb7", "Abmaj7"],
            "Chorus": ["Dbmaj7", "Eb7", "Fm7", "Bbm7"],
        }
        return {
            "instrument": instrument,
            "level": level,
            "display_key": display_key,
            "chart_sections": sections,
            "practice_focus_section": section,
            "active_song": {"title": song, "key": original_key},
        }

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
                instrument="Saxophone",
                level="Intermediate",
                song="The Girl from Ipanema",
                section="Full Song",
                log={
                    "session_count": 2,
                    "last_session_summary": {
                        "active_song": "The Girl from Ipanema",
                        "section_practiced": "Bridge",
                        "focus_area": "Phrasing",
                        "what_was_hard": "phrasing through the bridge",
                        "next_step": "practice the bridge slowly and shape each 2-bar phrase",
                    },
                },
            ),
        )
        assert resp is not None
        md = resp.composed_markdown()
        text = md.lower()
        self.assertIn("phrasing", text)
        self.assertIn("bridge", text)
        self.assertIn("ipanema", text)
        self.assertIn("why:", text)
        self.assertIn("slow 2-bar phrase shaping", text)
        self.assertTrue(resp.diagnostics.get("history_influenced_plan"))
        self.assertIn("unresolved_next_step", resp.diagnostics.get("history_signals_used_in_plan") or [])
        priority_line = md.split("\n")[0].lower()
        self.assertIn("phrasing and line shape", priority_line)
        self.assertIn("bridge", priority_line)
        self.assertNotIn("full song", priority_line)

    def test_priority_formatting_harmony_active_song(self) -> None:
        resp = run_coach_pipeline(
            "What should I work on today?",
            {},
            ami_ctx=self._ctx(
                instrument="Piano",
                level="Advanced",
                focus="Harmony",
                song="Say",
                section="Full Song",
            ),
        )
        assert resp is not None
        priority = resp.composed_markdown().split("\n")[0]
        self.assertIn("harmony and voicing across **Say**", priority)
        self.assertNotIn("Full Song", priority)
        self.assertNotIn(" and the ", priority)

    def test_priority_formatting_phrasing_active_song(self) -> None:
        resp = run_coach_pipeline(
            "What should I work on today?",
            {},
            ami_ctx=self._ctx(
                instrument="Saxophone",
                focus="Phrasing",
                song="The Girl from Ipanema",
            ),
        )
        assert resp is not None
        priority = resp.composed_markdown().split("\n")[0]
        self.assertIn("phrasing and line shape in **The Girl from Ipanema**", priority)

    def test_no_why_without_history_influence(self) -> None:
        resp = run_coach_pipeline(
            "What should I work on today?",
            {},
            ami_ctx=self._ctx(instrument="Piano", focus="Harmony", song="Say"),
        )
        assert resp is not None
        self.assertNotIn("**Why:**", resp.composed_markdown())
        self.assertFalse(resp.diagnostics.get("history_influenced_plan"))

    def test_fingerstyle_twenty_minute_specific_blocks(self) -> None:
        resp = run_coach_pipeline(
            "Give me a 20-minute fingerstyle session.",
            {},
            ami_ctx=self._ctx(
                instrument="Guitar",
                level="Intermediate",
                focus="Fingerstyle",
                song="Here Comes the Sun",
            ),
        )
        assert resp is not None
        steps = resp.practice_steps
        step_text = "\n".join(steps).lower()
        self.assertEqual(_sum_minutes(steps), 20)
        self.assertIn("thumb independence", step_text)
        self.assertIn("picking-pattern consistency", step_text)
        self.assertNotIn("technique / drills", step_text)
        self.assertEqual(resp.diagnostics.get("focus_profile"), "fingerstyle")
        listen = " ".join(resp.what_to_listen_for or []).lower()
        self.assertIn("bass pulse", listen)
        self.assertIn("melody", listen)

    def test_rhythm_session_differs_from_fingerstyle(self) -> None:
        fingerstyle = run_coach_pipeline(
            "Give me a 20-minute fingerstyle session.",
            {},
            ami_ctx=self._ctx(instrument="Guitar", level="Intermediate", focus="Fingerstyle"),
        )
        rhythm = run_coach_pipeline(
            "Give me a 20-minute rhythm session on guitar.",
            {},
            ami_ctx=self._ctx(instrument="Guitar", level="Intermediate"),
        )
        assert fingerstyle is not None and rhythm is not None
        fs_steps = "\n".join(fingerstyle.practice_steps).lower()
        rh_steps = "\n".join(rhythm.practice_steps).lower()
        self.assertIn("thumb independence", fs_steps)
        self.assertIn("metronome groove", rh_steps)
        self.assertNotIn("metronome groove", fs_steps)
        self.assertNotIn("thumb independence", rh_steps)

    def test_fingerstyle_history_thumb_pulse_specialization(self) -> None:
        resp = run_coach_pipeline(
            "What should I work on now?",
            {},
            ami_ctx=self._ctx(
                instrument="Guitar",
                level="Intermediate",
                focus="Fingerstyle",
                song="Here Comes the Sun",
                log={
                    "session_count": 3,
                    "repeated_challenge": "thumb loses steady pulse during chord changes",
                    "last_session_summary": {
                        "active_song": "Here Comes the Sun",
                        "focus_area": "Fingerstyle",
                        "what_was_hard": "thumb loses steady pulse during chord changes",
                    },
                },
            ),
        )
        assert resp is not None
        step_text = "\n".join(resp.practice_steps).lower()
        self.assertIn("isolated thumb pulse", step_text)
        self.assertIn("chord transitions with steady bass", step_text)
        self.assertNotIn("technique / drills", step_text)

    def test_bass_line_session_routes_and_specializes(self) -> None:
        resp = run_coach_pipeline(
            "Give me a bass line session for this song.",
            {},
            ami_ctx=self._ctx(
                instrument="Guitar",
                level="Intermediate",
                song="All the Things You Are",
            ),
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.PRACTICE_PLAN)
        self.assertIn("PracticePlanSolver", resp.source_solver)
        md = resp.composed_markdown()
        self.assertIn("bass-line development", md.lower())
        self.assertIn("All the Things You Are", md)
        self.assertEqual(resp.diagnostics.get("focus_profile"), "bass_line")
        self.assertEqual(resp.diagnostics.get("resolved_instrument"), "Guitar")
        step_text = "\n".join(resp.practice_steps).lower()
        self.assertTrue(
            any(p in step_text for p in ("bass-string root", "alternating bass", "connect roots"))
        )
        self.assertNotIn("technique / drills", step_text)
        listen = " ".join(resp.what_to_listen_for or []).lower()
        self.assertIn("chord changes", listen)

    def test_bass_line_twenty_minutes_exact(self) -> None:
        resp = run_coach_pipeline(
            "Give me a 20-minute bass line session for this song.",
            {},
            ami_ctx=self._ctx(
                instrument="Guitar",
                level="Intermediate",
                song="All the Things You Are",
            ),
        )
        assert resp is not None
        self.assertEqual(_sum_minutes(resp.practice_steps), 20)
        self.assertEqual(resp.diagnostics.get("focus_profile"), "bass_line")

    def test_bass_guitar_session_uses_bass_instrument_not_bass_line_focus(self) -> None:
        resp = run_coach_pipeline(
            "Give me a bass guitar practice session.",
            {},
            ami_ctx=self._ctx(
                instrument="Guitar",
                level="Intermediate",
                song="All the Things You Are",
            ),
        )
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("resolved_instrument"), "Bass")
        self.assertNotEqual(resp.diagnostics.get("focus_profile"), "bass_line")
        step_text = "\n".join(resp.practice_steps).lower()
        self.assertIn("groove", step_text)
        self.assertIn("root movement", step_text)

    def test_rhythm_session_includes_metronome_app_hint(self) -> None:
        resp = run_coach_pipeline(
            "Give me a 30-minute rhythm session on guitar.",
            {},
            ami_ctx=self._ctx(
                instrument="Guitar",
                level="Intermediate",
                song="Here Comes the Sun",
            ),
        )
        assert resp is not None
        md = resp.composed_markdown()
        self.assertIn("metronome groove", md.lower())
        self.assertIn("Practice tools → Metronome, Tuner & Tone", md)
        self.assertEqual(_sum_minutes(resp.practice_steps), 30)
        self.assertEqual(resp.diagnostics.get("focus_profile"), "timing")

    def test_fingerstyle_session_still_fingerstyle_profile(self) -> None:
        resp = run_coach_pipeline(
            "Give me a fingerstyle session.",
            {},
            ami_ctx=self._ctx(instrument="Guitar", level="Intermediate", focus="Fingerstyle"),
        )
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("focus_profile"), "fingerstyle")
        self.assertIn("thumb independence", "\n".join(resp.practice_steps).lower())

    def test_baseline_content_suggestion_not_practice_plan(self) -> None:
        ctx = self._bass_line_chart_ctx(
            instrument="Guitar",
            level="Intermediate",
            song="All the Things You Are",
        )
        ctx["active_song"]["progression_summary"] = "Fm7 | Bbm7 | Eb7 | Abmaj7"
        for question in (
            "Give me a baseline to use for this song.",
            "Give me a bassline to use for this song.",
            "Give me a bass-line to use for this song.",
        ):
            resp = run_coach_pipeline(question, {}, ami_ctx=ctx)
            assert resp is not None, question
            self.assertEqual(resp.intent, CoachIntent.SONG_COACHING)
            self.assertIn("SongCoachSolver(bass_line)", resp.source_solver)
            md = resp.composed_markdown()
            self.assertIn("Try this bass line", md)
            self.assertIn("All the Things You Are", md)
            self.assertNotIn("**8 min**", md)
            self.assertNotIn("PracticePlanSolver", resp.source_solver)
            self.assertTrue(resp.diagnostics.get("bass_line_content"))
            self.assertTrue(resp.diagnostics.get("notation_abc_present"))
            self.assertTrue(resp.notation_abc)
            self.assertIn("clef=treble", resp.notation_abc)
            if "baseline" in question:
                self.assertIn("baseline -> bass line", resp.diagnostics.get("normalized_phrases") or [])

    def test_baseline_content_uses_chord_context(self) -> None:
        resp = run_coach_pipeline(
            "Give me a baseline to use for this song.",
            {},
            ami_ctx={
                "instrument": "Guitar",
                "level": "Intermediate",
                "display_key": "Ab",
                "active_song": {
                    "title": "All the Things You Are",
                    "progression_summary": "Fm7 | Bbm7 | Eb7 | Abmaj7",
                },
            },
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertTrue(resp.diagnostics.get("chord_context_available"))
        self.assertTrue(resp.diagnostics.get("notation_abc_present"))
        self.assertIn("Fm7", text)
        self.assertIn("**Fm7:**", text)
        self.assertIn("K:Ab", resp.notation_abc)
        self.assertIn('"Fm7"', resp.notation_abc)

    def test_bass_line_notation_clef_by_instrument(self) -> None:
        question = "Give me a bass line to use for this song."
        expectations = {
            "Bass": "clef=bass",
            "Piano": "clef=bass",
            "Guitar": "clef=treble",
        }
        for instrument, clef_token in expectations.items():
            resp = run_coach_pipeline(
                question,
                {},
                ami_ctx=self._bass_line_chart_ctx(instrument=instrument),
            )
            assert resp is not None, instrument
            self.assertEqual(resp.diagnostics.get("notation_clef"), clef_token.split("=")[1])
            self.assertIn(clef_token, resp.notation_abc)
            self.assertTrue(resp.diagnostics.get("notation_abc_present"))

    def test_bass_line_practice_key_transposition(self) -> None:
        resp = run_coach_pipeline(
            "Give me a bass line to use for this song.",
            {},
            ami_ctx=self._bass_line_chart_ctx(
                instrument="Bass",
                display_key="Bb",
                original_key="Ab",
            ),
        )
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("practice_key"), "Bb")
        self.assertEqual(
            resp.diagnostics.get("chord_timeline_used"),
            ["Gm7", "Cm7", "F7", "Bbmaj7"],
        )
        self.assertIn("K:Bb", resp.notation_abc)
        self.assertIn('"Gm7"', resp.notation_abc)
        self.assertNotIn("K:Ab", resp.notation_abc)

    def test_bass_line_selected_section(self) -> None:
        resp = run_coach_pipeline(
            "Give me a bass line to use for this song.",
            {},
            ami_ctx=self._bass_line_chart_ctx(instrument="Bass", section="Chorus"),
        )
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("active_section"), "Chorus")
        self.assertEqual(
            resp.diagnostics.get("chord_timeline_used"),
            ["Dbmaj7", "Eb7", "Fm7", "Bbm7"],
        )
        self.assertIn("Chorus", resp.composed_markdown())
        self.assertIn('"Dbmaj7"', resp.notation_abc)

    def test_bass_line_fixture_chart_source(self) -> None:
        resp = run_coach_pipeline(
            "Give me a baseline to use for this song.",
            {},
            ami_ctx=self._bass_line_chart_ctx(instrument="Bass"),
        )
        assert resp is not None
        self.assertTrue(resp.diagnostics.get("chart_available"))
        self.assertEqual(resp.diagnostics.get("chart_source"), "ami_ctx.chart_sections")
        self.assertFalse(resp.diagnostics.get("fallback_reason"))

    def test_bass_line_no_chart_fallback(self) -> None:
        resp = run_coach_pipeline(
            "Give me a bass line to use for this song.",
            {},
            ami_ctx=self._ctx(instrument="Guitar", song="Mystery Song"),
        )
        assert resp is not None
        md = resp.composed_markdown().lower()
        self.assertIn("do not have the song's chord changes", md)
        self.assertFalse(resp.diagnostics.get("notation_abc_present"))
        self.assertEqual(resp.diagnostics.get("fallback_reason"), "no_trustworthy_active_chart")

    def test_bass_line_session_still_practice_plan(self) -> None:
        resp = run_coach_pipeline(
            "Give me a bass line session for this song.",
            {},
            ami_ctx=self._ctx(instrument="Guitar", level="Intermediate", song="All the Things You Are"),
        )
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.PRACTICE_PLAN)
        self.assertIn("PracticePlanSolver", resp.source_solver)
        self.assertEqual(resp.diagnostics.get("focus_profile"), "bass_line")

    def test_non_musical_baseline_not_bass_line(self) -> None:
        for question in (
            "What is my baseline practice time?",
            "Use yesterday as a baseline for comparison.",
        ):
            resp = run_coach_pipeline(question, {}, ami_ctx=self._ctx(instrument="Guitar"))
            if resp is not None:
                self.assertNotIn("SongCoachSolver(bass_line)", resp.source_solver)
                self.assertNotEqual(resp.diagnostics.get("focus_profile"), "bass_line")

    def test_explicit_articulation_sax_regression(self) -> None:
        resp = run_coach_pipeline(
            "Give me a 20-minute articulation session on the sax.",
            {},
            ami_ctx=self._ctx(
                instrument="Saxophone",
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
        self.assertIn("articulation", text)
        self.assertIn("single-note tonguing", text)
        self.assertTrue(resp.diagnostics.get("explicit_request_overrides_history"))
        self.assertNotIn("upper-register tone has come up", text)

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

    def test_daily_song_history_beats_active_song(self) -> None:
        resp = run_coach_pipeline(
            "What song should I practice today?",
            {},
            ami_ctx={
                "active_song": {"title": "The Girl from Ipanema"},
                "practice_log_summary": {
                    "session_count": 3,
                    "last_session_summary": {
                        "active_song": "Say",
                        "section_practiced": "Bridge",
                        "next_step": "work on bridge slowly",
                    },
                },
            },
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("Say", text)
        self.assertNotIn("The Girl from Ipanema", text.split("**Best choice today:**")[1].split("\n")[0])
        self.assertIn("RepertoireSolver(daily_continue)", resp.source_solver)
        self.assertTrue(resp.diagnostics.get("active_song_overridden"))

    def test_daily_song_active_fallback_without_history(self) -> None:
        resp = run_coach_pipeline(
            "What song should I practice today?",
            {},
            ami_ctx={"active_song": {"title": "The Girl from Ipanema"}},
        )
        assert resp is not None
        text = resp.composed_markdown()
        self.assertIn("The Girl from Ipanema", text)
        self.assertIn("RepertoireSolver(daily_active_song)", resp.source_solver)
        self.assertIn("already your active song", text.lower())

    def test_improv_song_question_still_improv(self) -> None:
        resp = run_coach_pipeline(
            "What song should I practice today to improve improvisation?",
            {},
        )
        assert resp is not None
        self.assertIn("goal_improv", resp.source_solver)


class CoachChartContextTransportTests(unittest.TestCase):
    @staticmethod
    def _two_of_us_catalog() -> tuple[str, dict, dict]:
        from song_catalog.catalog import format_pick_key

        label = "Just the Two of Us — Grover Washington Jr. / Bill Withers"
        pick_key = format_pick_key("Soul", label)
        sections = {
            "Verse": ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "C7", "Fm7"],
            "Chorus": ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "C7", "Fm7"],
        }
        row = {
            "title": "Just the Two of Us",
            "artist": "Grover Washington Jr. / Bill Withers",
            "genre": "Soul",
            "key": "Db",
            "sections": sections,
        }
        catalog = {"Soul": {label: row}}
        return pick_key, catalog, row

    def test_read_coach_context_resolves_pick_from_active_song_state(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY
        from music_coach_ami.context_reader import read_coach_context
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        pick_key, catalog, row = self._two_of_us_catalog()
        session = {
            ACTIVE_CATALOG_PICK_KEY: "",
            SELECTED_SONG_STATE_KEY: {
                "title": row["title"],
                "artist": row["artist"],
                "genre": row["genre"],
            },
            ACTIVE_SONG_STATE_KEY: {"pick_key": pick_key},
            "_reconcile_song_picker_catalog": catalog,
            "_reconcile_song_library": catalog,
            "display_key": "Db",
            "instrument": "Bass",
            "level": "Intermediate",
            "practice_focus_section": "Verse",
        }
        coach_ctx = read_coach_context(
            session,
            ami_ctx={
                "instrument": "Bass",
                "level": "Intermediate",
                "display_key": "Db",
                "practice_focus_section": "Verse",
                "active_song": {"title": row["title"], "artist": row["artist"]},
            },
        )
        snap = coach_ctx.extra.get("chart_snapshot") if isinstance(coach_ctx.extra, dict) else {}
        assert isinstance(snap, dict)
        self.assertEqual(coach_ctx.active_song_title, "Just the Two of Us")
        self.assertEqual(coach_ctx.active_song_pick_key, pick_key)
        self.assertTrue(snap.get("chart_available"))
        self.assertEqual(snap.get("resolved_pick_key"), pick_key)
        self.assertTrue(str(snap.get("chart_source") or "").startswith("catalog.resolve_catalog_song_for_chart"))
        self.assertGreaterEqual(int(snap.get("active_section_chord_count") or 0), 4)
        self.assertIn("Dbmaj7", snap.get("active_section_chords") or [])

    def test_read_coach_context_uses_improv_concert_sections(self) -> None:
        from music_coach_ami.context_reader import read_coach_context

        session = {
            "improv_song_concert_sections": {
                "Verse": ["Gm7", "Cm7", "F7", "Bbmaj7"],
            },
            "display_key": "Bb",
            "instrument": "Bass",
            "level": "Intermediate",
            "practice_focus_section": "Verse",
        }
        coach_ctx = read_coach_context(
            session,
            ami_ctx={
                "instrument": "Bass",
                "level": "Intermediate",
                "display_key": "Bb",
                "practice_focus_section": "Verse",
                "active_song": {"title": "Practice Song"},
            },
        )
        snap = coach_ctx.extra.get("chart_snapshot") if isinstance(coach_ctx.extra, dict) else {}
        assert isinstance(snap, dict)
        self.assertTrue(snap.get("chart_available"))
        self.assertEqual(snap.get("chart_source"), "session.improv_song_concert_sections")
        self.assertEqual(snap.get("active_section_chords"), ["Gm7", "Cm7", "F7", "Bbmaj7"])

    def test_live_shape_bass_line_notation_from_catalog_session(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        pick_key, catalog, row = self._two_of_us_catalog()
        session = {
            ACTIVE_CATALOG_PICK_KEY: "",
            SELECTED_SONG_STATE_KEY: {
                "title": row["title"],
                "artist": row["artist"],
                "genre": row["genre"],
            },
            ACTIVE_SONG_STATE_KEY: {"pick_key": pick_key},
            "_reconcile_song_picker_catalog": catalog,
            "_reconcile_song_library": catalog,
            "display_key": "Db",
            "instrument": "Bass",
            "level": "Intermediate",
            "practice_focus_section": "Verse",
        }
        resp = run_coach_pipeline(
            "Give me a good baseline to use for this song.",
            session,
            ami_ctx={
                "instrument": "Bass",
                "level": "Intermediate",
                "display_key": "Db",
                "practice_focus_section": "Verse",
                "active_song": {"title": row["title"], "artist": row["artist"]},
            },
        )
        assert resp is not None
        self.assertIn("SongCoachSolver(bass_line)", resp.source_solver)
        self.assertTrue(resp.diagnostics.get("notation_abc_present"))
        self.assertIn("clef=bass", resp.notation_abc)
        self.assertIn('"Dbmaj7"', resp.notation_abc)
        self.assertNotIn("do not have the song's chord changes", resp.composed_markdown().lower())


if __name__ == "__main__":
    unittest.main()
