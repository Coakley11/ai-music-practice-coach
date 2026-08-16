"""Phase 2A: AMI + Practice page consume Practice Focus policy."""

from __future__ import annotations

import unittest

from music_coach_ami.pipeline import run_coach_pipeline
from music_coach_ami.router import CoachIntent, route_question
from practice_focus_coaching import (
    ami_focus_bucket,
    practice_page_focus_lines,
    practice_page_kind,
    should_prefer_policy_plan,
    timed_practice_blocks,
)
from practice_setup_globals import set_active_focus, set_active_instrument


def _ami(instrument: str, focus: str, *, song: str = "Shape of You", session: dict | None = None):
    ss = session if session is not None else {
        "instrument": instrument,
        "focus": focus,
        "level": "Intermediate",
    }
    ss.setdefault("instrument", instrument)
    ss.setdefault("focus", focus)
    ss.setdefault("level", "Intermediate")
    return run_coach_pipeline(
        "What should I practice today?",
        ss,
        ami_ctx={
            "instrument": instrument,
            "focus": focus,
            "level": "Intermediate",
            "active_song": {"title": song},
        },
    )


class TestPhase2AmiFocusPlans(unittest.TestCase):
    def test_guitar_strumming_vs_timing_vs_harmony(self) -> None:
        strum = _ami("Guitar", "Strumming")
        timing = _ami("Guitar", "Timing")
        harmony = _ami("Guitar", "Harmony")
        assert strum is not None and timing is not None and harmony is not None
        self.assertEqual(strum.intent, CoachIntent.PRACTICE_PLAN)
        s, t, h = (x.composed_markdown().lower() for x in (strum, timing, harmony))
        self.assertNotEqual(s, t)
        self.assertNotEqual(t, h)
        self.assertTrue("strum" in s or "groove" in s or "downstroke" in s)
        self.assertTrue("metronome" in t or "subdivision" in t or "rush" in t)
        self.assertTrue("chord tone" in h or "guide tone" in h or "voice" in h)
        self.assertNotIn("long tones", s)
        self.assertNotEqual(strum.practice_steps, timing.practice_steps)
        self.assertNotEqual(timing.practice_steps, harmony.practice_steps)

    def test_sax_tone_vs_articulation_vs_phrasing(self) -> None:
        tone = _ami("Saxophone", "Tone")
        artic = _ami("Saxophone", "Articulation")
        phrase = _ami("Saxophone", "Phrasing")
        assert tone is not None and artic is not None and phrase is not None
        to, ar, ph = (x.composed_markdown().lower() for x in (tone, artic, phrase))
        self.assertNotEqual(to, ar)
        self.assertNotEqual(ar, ph)
        self.assertTrue("long tone" in to or "embouchure" in to or "air" in to or "tone" in to)
        self.assertTrue("tongue" in ar or "articul" in ar or "attack" in ar)
        self.assertTrue("phrase" in ph or "space" in ph or "breath" in ph)
        self.assertNotEqual(tone.practice_steps, artic.practice_steps)

    def test_timed_routine_allocation_follows_focus(self) -> None:
        session = {"instrument": "Guitar", "focus": "Strumming", "level": "Intermediate"}
        strum = run_coach_pipeline(
            "Give me a 20-minute practice routine.",
            session,
            ami_ctx={"instrument": "Guitar", "focus": "Strumming", "level": "Intermediate"},
        )
        session["focus"] = "Tone"
        sax = run_coach_pipeline(
            "Give me a 20-minute practice routine.",
            {"instrument": "Saxophone", "focus": "Tone", "level": "Intermediate"},
            ami_ctx={"instrument": "Saxophone", "focus": "Tone", "level": "Intermediate"},
        )
        assert strum is not None and sax is not None
        self.assertEqual(strum.intent, CoachIntent.PRACTICE_PLAN)
        s = "\n".join(strum.practice_steps).lower()
        x = "\n".join(sax.practice_steps).lower()
        self.assertTrue("strum" in s or "pattern" in s or "accent" in s)
        self.assertTrue("long tone" in x or "tone" in x)
        self.assertNotEqual(s, x)

    def test_c_major_notes_not_hijacked_by_strumming(self) -> None:
        req = route_question(
            "What notes are in C major?",
            {"instrument": "Guitar", "focus": "Strumming"},
            ami_ctx={"instrument": "Guitar", "focus": "Strumming"},
        )
        self.assertEqual(req.intent, CoachIntent.THEORY_EXPLANATION)
        resp = run_coach_pipeline(
            "What notes are in C major?",
            {"instrument": "Guitar", "focus": "Strumming"},
            ami_ctx={"instrument": "Guitar", "focus": "Strumming"},
        )
        assert resp is not None
        text = resp.composed_markdown()
        low = text.lower()
        self.assertIn("c", low)
        self.assertIn("d", low)
        self.assertIn("e", low)
        self.assertIn("f", low)
        self.assertIn("g", low)
        self.assertIn("a", low)
        self.assertIn("b", low)
        self.assertNotIn("strumming", low)
        self.assertNotIn("downstroke", low)
        self.assertTrue(resp.diagnostics.get("practice_focus_not_applied"))

    def test_same_rerun_focus_change_updates_ami(self) -> None:
        session = {"instrument": "Guitar", "focus": "Strumming", "level": "Intermediate"}
        first = run_coach_pipeline(
            "What should I practice today?",
            session,
            ami_ctx={"instrument": "Guitar", "level": "Intermediate"},
        )
        set_active_focus(session, "Timing", source="test")
        second = run_coach_pipeline(
            "What should I practice today?",
            session,
            ami_ctx={"instrument": "Guitar", "level": "Intermediate"},
        )
        assert first is not None and second is not None
        self.assertNotEqual(first.composed_markdown(), second.composed_markdown())
        self.assertIn("strum", first.composed_markdown().lower())
        self.assertTrue(
            "metronome" in second.composed_markdown().lower()
            or "subdivision" in second.composed_markdown().lower()
        )

    def test_unknown_focus_does_not_crash(self) -> None:
        resp = _ami("Guitar", "Banana Technique")
        assert resp is not None
        self.assertEqual(resp.intent, CoachIntent.PRACTICE_PLAN)
        self.assertTrue(resp.composed_markdown().strip())

    def test_how_should_i_practice_this_song_is_practice_plan(self) -> None:
        req = route_question("How should I practice this song?", {"focus": "Strumming", "instrument": "Guitar"})
        self.assertEqual(req.intent, CoachIntent.PRACTICE_PLAN)

    def test_improve_and_backing_questions_are_practice_plan(self) -> None:
        improve = route_question("How can I improve?", {"focus": "Strumming", "instrument": "Guitar"})
        backing = route_question(
            "How should I use this backing track?",
            {"focus": "Strumming", "instrument": "Guitar"},
        )
        week = route_question("What should I focus on this week?", {"focus": "Timing", "instrument": "Guitar"})
        self.assertEqual(improve.intent, CoachIntent.PRACTICE_PLAN)
        self.assertEqual(backing.intent, CoachIntent.PRACTICE_PLAN)
        self.assertEqual(week.intent, CoachIntent.PRACTICE_PLAN)


class TestPhase2PracticePage(unittest.TestCase):
    def test_page_kinds_differ(self) -> None:
        self.assertEqual(practice_page_kind("Strumming"), "Rhythm")
        self.assertEqual(practice_page_kind("Timing"), "Timing")
        self.assertEqual(practice_page_kind("Harmony"), "Harmony")
        self.assertEqual(practice_page_kind("Tone"), "Tone")
        self.assertEqual(practice_page_kind("Articulation"), "Articulation")
        self.assertEqual(practice_page_kind("Phrasing"), "Phrasing")
        self.assertEqual(practice_page_kind("Completely Unknown Focus"), "Technique")

    def test_guitar_page_lines_change_with_focus(self) -> None:
        kwargs = {
            "first_chord": "Em",
            "second_chord": "C",
            "chord_path": "Em | C | G | D",
            "section_name": "Verse",
        }
        strum = "\n".join(practice_page_focus_lines("Guitar", "Strumming", **kwargs)).lower()
        timing = "\n".join(practice_page_focus_lines("Guitar", "Timing", **kwargs)).lower()
        harmony = "\n".join(practice_page_focus_lines("Guitar", "Harmony", **kwargs)).lower()
        self.assertNotEqual(strum, timing)
        self.assertNotEqual(timing, harmony)
        self.assertTrue("strum" in strum or "downstroke" in strum or "hand" in strum)
        self.assertTrue("isolate" in strum or "downstroke" in strum or "accent" in strum)
        self.assertTrue("metronome" in timing or "subdivision" in timing or "beat" in timing)
        self.assertTrue("chord tone" in harmony or "guide" in harmony or "voice" in harmony)
        self.assertIn("em", strum)
        self.assertIn("em", timing)

    def test_sax_page_lines_change_with_focus(self) -> None:
        kwargs = {
            "first_chord": "Gm",
            "second_chord": "C7",
            "chord_path": "Gm | C7 | F",
            "section_name": "Chorus",
        }
        tone = "\n".join(practice_page_focus_lines("Saxophone", "Tone", **kwargs)).lower()
        artic = "\n".join(practice_page_focus_lines("Saxophone", "Articulation", **kwargs)).lower()
        phrasing = "\n".join(practice_page_focus_lines("Saxophone", "Phrasing", **kwargs)).lower()
        self.assertNotEqual(tone, artic)
        self.assertNotEqual(artic, phrasing)
        self.assertTrue("long tone" in tone or "air" in tone or "embouchure" in tone)
        self.assertTrue("attack" in artic or "legato" in artic or "tongue" in artic)
        self.assertTrue("phrase" in phrasing or "space" in phrasing)

    def test_unknown_focus_falls_back_without_inventing_instrument_behavior(self) -> None:
        lines = practice_page_focus_lines("Saxophone", "Banana Technique")
        self.assertEqual(len(lines), 3)
        blob = "\n".join(lines).lower()
        self.assertNotIn("strumming", blob)
        self.assertNotIn("downstroke", blob)
        unknown = "\n".join(practice_page_focus_lines("Saxophone", "Qwertyxyz Custom")).lower()
        self.assertNotIn("strumming", unknown)
        self.assertNotIn("embouchure", unknown)
        self.assertIn("qwertyxyz custom", unknown)


class TestPhase2PolicyWiring(unittest.TestCase):
    def test_strumming_prefers_policy_plan(self) -> None:
        self.assertEqual(ami_focus_bucket("Strumming"), "rhythm_groove")
        self.assertTrue(should_prefer_policy_plan("Strumming"))
        self.assertFalse(should_prefer_policy_plan("Fingerstyle"))
        weights, details = timed_practice_blocks("Guitar", "Strumming", song="Shape of You")
        blob = " ".join(details.values()).lower()
        self.assertTrue("strum" in blob or "pattern" in blob)
        self.assertIn("isolated pattern", weights)

    def test_guitar_to_sax_fallback_unchanged(self) -> None:
        session = {"instrument": "Guitar", "focus": "Strumming", "level": "Intermediate"}
        set_active_instrument(session, "Saxophone", source="test")
        self.assertEqual(session["focus"], "Tone")


if __name__ == "__main__":
    unittest.main()
