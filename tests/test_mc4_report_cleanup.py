"""MC4 report cleanups: no literal markup in the coach report; chord-tone wording follows the evidence."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from markdown_it import MarkdownIt

from mission_analysis import _chord_tone_growth_line, _coach_result_fields
from mission_span_take_evaluation import _passing_or_outside, build_harmony, span_note_shares
from recording_analysis_ui import render_analysis_dashboard

SPAN_RESULT = {
    "aligned": True, "score": 100,
    "chord_detail": [
        {"chord": "C/E", "notes": 4, "chord_tone_pct": 100, "colour_tone_pct": 0, "passing_tone_pct": 0,
         "outside_tone_pct": 0, "colour_examples": []},
        {"chord": "G", "notes": 4, "chord_tone_pct": 75, "colour_tone_pct": 25, "passing_tone_pct": 0,
         "outside_tone_pct": 0, "colour_examples": ["A (9th)"]},
        {"chord": "C", "notes": 2, "chord_tone_pct": 50, "colour_tone_pct": 50, "passing_tone_pct": 0,
         "outside_tone_pct": 0, "colour_examples": ["B (major 7th)"]},
    ],
}


def _result(**kw: object) -> dict:
    result = {
        "ok": True, "coach_summary": "Solid take.", "biggest_issue": "tone", "next_focus": "Chord-tone targeting",
        "most_improved": "musicality", "instrument": "Flute", "duration": 6.6, "tempo": None,
        "reference_bpm": 126,
        "scores": {"timing": 87, "pitch": 71, "technique": 77, "groove": 82, "musicality": 94, "confidence": 74,
                   "tone": 66},
        "categories": {}, "practice_plan": ["Loop at 114 BPM."],
        "mission_evaluation_active": True, "overall_improv_score": 76, "span_mission": SPAN_RESULT,
        "mission_results": [{"id": "chord_tone_targeting", "label": "Chord-tone targeting", "score": 80,
                             "summary": "You hit the required targets.", "observed_evidence": ["chord tone accuracy ≈ 80/100"]}],
        "practice_focus_analysis": [{
            "focus": "Tone", "assessment": "66/100", "findings": ["Average spectral brightness ≈ 474 Hz."],
            "attribution_confidence": "Analysis uses the dry microphone take.",
            "went_well": "Recognizable tone centre.", "improve_to": "Stabilize sustains.", "drill": "Long tones.",
        }],
        "recording_type": "mission_live",
    }
    result.update(kw)
    return result


def _visible_markup(html: str) -> list[str]:
    """Tags that CommonMark (as Streamlit's markdown) would show as text or put in a code block."""
    rendered = MarkdownIt("commonmark", {"html": True}).render(html)
    problems = []
    for tag in ("strong", "span", "div", "ul", "li", "p", "details", "summary"):
        if f"&lt;{tag}" in rendered or f"&lt;/{tag}" in rendered:
            problems.append(tag)
    if "<pre>" in rendered or "<code>" in rendered:
        problems.append("code block")
    return problems


class TestNoLiteralMarkup(unittest.TestCase):
    def test_report_renders_without_literal_tags(self) -> None:
        # tempo=None leaves an empty pill slot — the case that turned the pills into a code block.
        for result in (_result(), _result(tempo=126.0), _result(target_layer="Flute", tempo=None)):
            html = render_analysis_dashboard(result)
            self.assertEqual(_visible_markup(html), [])
            self.assertIn("Mission vs. this score:", html)
            self.assertIn("What was detected", html)
            self.assertIn("ra-pill issue", html)

    def test_markdown_bold_in_summaries_is_rendered_not_shown(self) -> None:
        html = render_analysis_dashboard(_result(
            mission_coach_summary="Evaluated 1 criteria against **Let It Be** (C, Flute). **Chord-tone targeting**: 76%."))
        self.assertIn("<strong>Let It Be</strong>", html)
        self.assertNotIn("**", html)
        failed = render_analysis_dashboard({"ok": False, "message": "Requires **librosa** <b>x</b>."})
        self.assertIn("<strong>librosa</strong>", failed)
        self.assertIn("&lt;b&gt;", failed)

    def test_content_is_still_escaped(self) -> None:
        html = render_analysis_dashboard(_result(coach_summary="<script>alert(1)</script> & more"))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestChordToneWordingFollowsEvidence(unittest.TestCase):
    def test_colour_tones_are_not_called_outside(self) -> None:
        shares = span_note_shares(SPAN_RESULT)
        self.assertEqual(shares["chord"], 80.0)
        self.assertEqual(shares["colour"], 20.0)
        self.assertEqual(shares["outside"], 0.0)
        observation, advice = _chord_tone_growth_line(shares)
        self.assertEqual(observation, "You hit the required targets, and several other notes were stable colour "
                                      "tones rather than basic chord tones.")
        self.assertEqual(advice, "For clearer chord-tone targeting, place roots/3rds/5ths more deliberately on "
                                 "strong beats.")
        self.assertNotIn("outside", observation)
        # The observation is what went well; the advice is the growth edge (not both in one line).
        went_well, improve_to = _coach_result_fields(70, observation, advice + " Over Let It Be, sing each chord root.")
        self.assertEqual(went_well, observation)
        self.assertTrue(improve_to.startswith("For clearer chord-tone targeting"))

    def test_many_unsupported_notes_get_stronger_wording(self) -> None:
        observation, _advice = _chord_tone_growth_line(
            {"chord": 40, "colour": 10, "passing": 10, "outside": 40, "mission_score": 50})
        self.assertIn("Many notes sat outside the chord underneath", observation)
        went_well, improve_to = _coach_result_fields(45, observation, "Over Let It Be, sing each chord root.")
        self.assertNotEqual(went_well, observation)  # never presented as praise
        self.assertIn("sat outside", improve_to)

    def test_passing_notes_and_no_evidence(self) -> None:
        self.assertIn("passing or approach notes",
                      _chord_tone_growth_line({"chord": 60, "colour": 5, "passing": 30, "outside": 5, "mission_score": 67})[0])
        generic, _advice = _chord_tone_growth_line({})
        self.assertNotIn("outside the harmony", generic)
        self.assertIn("some may be passing, colour or tension tones", generic)

    def test_chromatic_approach_vs_outside(self) -> None:
        from mission_span_recording_context import build_timeline

        tl = build_timeline([{"chord": "C/E", "bars": 1}, {"chord": "G", "bars": 1}, {"chord": "C", "bars": 1}], meter="4/4")
        h = build_harmony({"practice_key": "C", "timeline": tl})
        ev = lambda midi, ci: SimpleNamespace(midi=midi, pc=midi % 12, chord_index=ci)  # noqa: E731
        self.assertEqual(_passing_or_outside(h, ev(73, 2), ev(74, 2)), "passing")   # C♯ → D (9th): approach
        self.assertEqual(_passing_or_outside(h, ev(73, 2), ev(81, 2)), "outside")   # C♯ leaping away
        self.assertEqual(_passing_or_outside(h, ev(73, 2), None), "outside")


if __name__ == "__main__":
    unittest.main()
