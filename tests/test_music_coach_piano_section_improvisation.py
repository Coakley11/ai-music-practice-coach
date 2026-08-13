"""Piano section improvisation / melody / accompaniment — first AMI slice."""

from __future__ import annotations

import unittest
from dataclasses import replace

from music_coach_ami.musical_idea_engine import (
    generate_piano_section_improvisation,
    infer_piano_role,
)
from music_coach_ami.musical_idea_knowledge import (
    extract_requested_section,
    is_musical_idea_content_request,
    resolve_chart_section,
)
from music_coach_ami.musical_idea_request import parse_musical_idea_request, resolve_musical_idea_request
from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami.router import CoachIntent, route_question


CHORUS = ["Abmaj7", "Fm7", "Dbmaj7", "Eb7"]
VERSE = ["Fm7", "Eb7", "Abmaj7", "Dbmaj7"]
PART_B = ["Bbm7", "Eb7", "Abmaj7", "F7"]


def _piano_ctx(sections: dict, *, level: str = "Beginner", key: str = "Ab") -> dict:
    return {
        "instrument": "Piano",
        "level": level,
        "focus": "Improvisation",
        "display_key": key,
        "coach_page": "practice",
        "chart_sections": sections,
        "practice_focus_section": "Verse",
        "active_song": {"title": "Acceptance Tune", "key": "Ab"},
    }


class PianoRequestModelTests(unittest.TestCase):
    def test_improvisation_over_chorus_parses(self) -> None:
        q = "Give me an improvisation over the chorus."
        idea = parse_musical_idea_request(q, default_object="lick")
        self.assertEqual(idea.object_type, "improvisation")
        self.assertTrue(idea.song_relative)
        self.assertEqual(extract_requested_section(q), "chorus")
        self.assertTrue(is_musical_idea_content_request(q, q.lower()))
        req = route_question(q, {"instrument": "Piano", "display_key": "Ab"})
        self.assertEqual(req.intent, CoachIntent.SCALE_PRACTICE)

    def test_right_hand_melody_over_verse(self) -> None:
        q = "Give me a simple right-hand melody over the verse."
        idea = parse_musical_idea_request(q, default_object="lick")
        self.assertEqual(idea.object_type, "melody")
        self.assertEqual(idea.piano_role, "right_hand")
        self.assertEqual(idea.difficulty, "beginner")
        self.assertEqual(extract_requested_section(q), "verse")

    def test_left_hand_part_b(self) -> None:
        q = "Give me a left-hand accompaniment for part B."
        idea = parse_musical_idea_request(q, default_object="lick")
        self.assertEqual(idea.object_type, "accompaniment")
        self.assertEqual(idea.piano_role, "left_hand")
        self.assertEqual(extract_requested_section(q), "b")

    def test_two_hand_chorus(self) -> None:
        q = "Give me a two-hand piano improvisation over the chorus."
        idea = parse_musical_idea_request(q, default_object="lick")
        self.assertEqual(idea.object_type, "improvisation")
        self.assertEqual(idea.piano_role, "both_hands")
        self.assertEqual(infer_piano_role(idea, q), "both_hands")


class PianoSectionHonestyTests(unittest.TestCase):
    def test_missing_chorus_lists_available(self) -> None:
        _, resp = run_coach_submit(
            "Give me an improvisation over the chorus.",
            {"instrument": "Piano", "display_key": "Ab", "level": "Beginner"},
            ami_ctx=_piano_ctx({"Verse": VERSE, "Bridge": PART_B}),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertIn("doesn't have a section labeled", resp.direct_answer)
        self.assertIn("Verse", resp.direct_answer)
        self.assertFalse(resp.notation_abc)

    def test_explicit_section_outranks_active(self) -> None:
        resolved = resolve_chart_section(
            "chorus",
            chart_sections={"Verse": VERSE, "Chorus": CHORUS},
            fallback_section="Verse",
            fallback_chords=VERSE,
        )
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["section"], "Chorus")
        self.assertEqual(resolved["chords"], CHORUS)


class PianoGenerationTests(unittest.TestCase):
    def test_rh_follows_chorus_chords_and_practice_key(self) -> None:
        idea = replace(
            resolve_musical_idea_request(
                "Give me an improvisation over the chorus.",
                default_object="improvisation",
                instrument="Piano",
                level="Beginner",
            ),
            bars=4,
            song_relative=True,
            piano_role="right_hand",
        )
        comp = generate_piano_section_improvisation(
            idea, CHORUS, reference_key="Ab", piano_role="right_hand"
        )
        self.assertEqual(comp.bars, 4)
        self.assertEqual(comp.notation_profile.clef, "treble")
        self.assertEqual(comp.tonic, "Ab")
        chords = [e.chord for e in comp.events if e.chord]
        self.assertEqual(chords[0], "Abmaj7")
        bar_chords = []
        for b in range(4):
            evs = [e for e in comp.events if e.bar_index == b]
            self.assertTrue(evs, msg=f"empty bar {b}")
            bar_chords.append(evs[0].chord)
        self.assertEqual(bar_chords, CHORUS)
        self.assertTrue(all(e.role == "rh" for e in comp.events))

    def test_lh_bass_clef_not_duplicate_of_rh(self) -> None:
        q = "Give me a left-hand accompaniment for part B."
        idea = resolve_musical_idea_request(
            q, default_object="accompaniment", instrument="Piano", level="Intermediate"
        )
        rh = generate_piano_section_improvisation(
            resolve_musical_idea_request(
                "Give me a right-hand improvisation over part B.",
                default_object="improvisation",
                instrument="Piano",
                level="Intermediate",
            ),
            PART_B,
            reference_key="Ab",
            piano_role="right_hand",
            question="Give me a right-hand improvisation over part B.",
        )
        lh = generate_piano_section_improvisation(
            idea, PART_B, reference_key="Ab", piano_role="left_hand", question=q
        )
        self.assertEqual(lh.notation_profile.clef, "bass")
        self.assertTrue(all(e.role == "lh" for e in lh.events))
        rh_notes = [(e.spelled, e.octave, e.bar_index) for e in rh.events]
        lh_notes = [(e.spelled, e.octave, e.bar_index) for e in lh.events]
        self.assertNotEqual(rh_notes, lh_notes)
        self.assertTrue(all(e.octave <= 3 for e in lh.events))

    def test_both_hands_grand_staff(self) -> None:
        from music_coach_ami.musical_idea_engine import composition_to_abc

        idea = resolve_musical_idea_request(
            "Give me a two-hand piano improvisation over the chorus.",
            default_object="improvisation",
            instrument="Piano",
            level="Intermediate",
        )
        comp = generate_piano_section_improvisation(
            idea,
            CHORUS,
            reference_key="Ab",
            piano_role="both_hands",
            question="Give me a two-hand piano improvisation over the chorus.",
        )
        self.assertEqual(comp.notation_profile.clef, "grand")
        rh = [e for e in comp.events if e.role == "rh"]
        lh = [e for e in comp.events if e.role == "lh"]
        self.assertTrue(rh and lh)
        self.assertNotEqual(
            [(e.spelled, e.octave) for e in rh],
            [(e.spelled, e.octave) for e in lh],
        )
        abc, diag = composition_to_abc(comp, title="Chorus two-hand", bpm=96)
        self.assertIn("clef=treble", abc)
        self.assertIn("clef=bass", abc)
        self.assertIn("%%score", abc)
        self.assertIn('"Abmaj7"', abc)
        self.assertIn("K:Ab", abc)
        self.assertTrue(diag.get("notation_validation_ok") or "missing" not in str(diag.get("notation_validation_errors")))

    def test_level_changes_density(self) -> None:
        beginner = generate_piano_section_improvisation(
            resolve_musical_idea_request(
                "Give me a simple improvisation over the chorus.",
                default_object="improvisation",
                instrument="Piano",
                level="Beginner",
            ),
            CHORUS,
            reference_key="Ab",
            piano_role="right_hand",
        )
        advanced = generate_piano_section_improvisation(
            resolve_musical_idea_request(
                "Give me an advanced jazz improvisation over the chorus.",
                default_object="improvisation",
                instrument="Piano",
                level="Advanced",
            ),
            CHORUS,
            reference_key="Ab",
            piano_role="right_hand",
        )
        self.assertGreater(len(advanced.events), len(beginner.events))
        self.assertIn("beginner", beginner.strategy)
        self.assertIn("advanced", advanced.strategy)

    def test_ab_spelling_stays_flat(self) -> None:
        idea = resolve_musical_idea_request(
            "Give me an improvisation over the chorus.",
            default_object="improvisation",
            instrument="Piano",
            level="Beginner",
        )
        comp = generate_piano_section_improvisation(
            idea, CHORUS, reference_key="Ab", piano_role="right_hand"
        )
        names = " ".join(e.spelled for e in comp.events)
        self.assertNotIn("G#", names)
        self.assertIn("Ab", " ".join(e.chord for e in comp.events if e.chord))


class PianoSubmitIntegrationTests(unittest.TestCase):
    def test_submit_chorus_improvisation(self) -> None:
        _, resp = run_coach_submit(
            "Give me an improvisation over the chorus.",
            {"instrument": "Piano", "display_key": "Ab", "level": "Beginner", "instrument_change_source": "sidebar"},
            ami_ctx=_piano_ctx({"Chorus": CHORUS, "Verse": VERSE}, key="Ab"),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertTrue(resp.notation_abc)
        self.assertEqual((resp.diagnostics or {}).get("resolved_section"), "Chorus")
        self.assertEqual((resp.diagnostics or {}).get("piano_role"), "right_hand")
        self.assertEqual((resp.diagnostics or {}).get("staff_assignment"), "treble")
        self.assertEqual((resp.diagnostics or {}).get("practice_concert_key"), "Ab")
        self.assertIn("Chorus", resp.direct_answer)
        self.assertIn("K:Ab", resp.notation_abc)
        self.assertIn('"Abmaj7"', resp.notation_abc)
        self.assertEqual(len((resp.diagnostics or {}).get("bars_with_events") or []), 4)

    def test_submit_two_hand_and_left_hand(self) -> None:
        _, both = run_coach_submit(
            "Give me a two-hand piano improvisation over the chorus.",
            {"instrument": "Piano", "display_key": "Ab", "level": "Intermediate", "instrument_change_source": "sidebar"},
            ami_ctx=_piano_ctx({"Chorus": CHORUS, "Verse": VERSE, "B": PART_B}, level="Intermediate"),
        )
        assert both is not None
        self.assertEqual((both.diagnostics or {}).get("piano_role"), "both_hands")
        self.assertIn("clef=treble", both.notation_abc or "")
        self.assertIn("clef=bass", both.notation_abc or "")
        self.assertIn("%%score", both.notation_abc or "")
        prose = "\n".join(both.practice_steps or [])
        self.assertIn("RH:", prose)
        self.assertIn("LH:", prose)
        self.assertNotIn("ScalePracticeSolver", both.composed_markdown())

        _, lh = run_coach_submit(
            "Give me a left-hand accompaniment for part B.",
            {"instrument": "Piano", "display_key": "Ab", "level": "Intermediate", "instrument_change_source": "sidebar"},
            ami_ctx=_piano_ctx({"Chorus": CHORUS, "Verse": VERSE, "B": PART_B}, level="Intermediate"),
        )
        assert lh is not None
        self.assertEqual((lh.diagnostics or {}).get("piano_role"), "left_hand")
        self.assertEqual((lh.diagnostics or {}).get("staff_assignment"), "bass")
        self.assertEqual((lh.diagnostics or {}).get("resolved_section"), "B")


if __name__ == "__main__":
    unittest.main()
