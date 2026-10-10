"""C4 — "Improvise using a blues scale that fits the chord."

BLUES1-BLUES12 per the human-review spec: structural assertions, never one
exact note sequence, since the generator is intentionally variable.
"""

from __future__ import annotations

import random
import unittest

from improvisation_intelligence import ImprovSessionContext
from improvisation_mission_rules import (
    _blues_relationship_for_quality,
    _chord_tone_pcs,
    _pc,
    apply_mission_rules,
    choose_blues_relationship,
    resolve_blues_choice,
)
from improvisation_mission_specs import validate_mission_motif
from improvisation_missions import _transpose_mission_example_payload, generate_mission_example
from tests.test_improvisation_motif_abc import assert_mission_outputs_synchronized

BLUES_MISSION = "Improvise using a blues scale that fits the chord"

CHORDS = (
    ("Cmaj7", "C", "major/maj7"),
    ("Dm7", "C", "minor/min7"),
    ("D7", "D", "dominant 7"),
    ("G7", "C", "dominant 7"),
    ("Fm7", "C", "minor/min7"),
)


def _scale_pcs_for(chord, key_center, motif):
    relationship = str(motif.get("pentatonic_relationship") or "").strip()
    if not relationship:
        from music_theory import classify_chord_quality

        relationship = _blues_relationship_for_quality(classify_chord_quality(chord))
    _p, _k, notes, _l, _b = resolve_blues_choice(chord, key_center, relationship)
    return {_pc(n) for n in notes}


def _gen(chord, key_center, level, variant, seed):
    rng = random.Random(seed)
    return apply_mission_rules(
        BLUES_MISSION, {"chord": chord, "notes": [], "midi": []}, chord=chord,
        key_center=key_center, level=level, variant=variant, rng=rng,
    )


class TestBluesChoiceAndMembership(unittest.TestCase):
    """BLUES1/BLUES2 — the right blues collection is chosen, every note belongs to it."""

    def test_dominant_d7_resolves_to_d_blues_collection(self) -> None:
        """BLUES1 — D7 -> D F G Ab A C, the human-review example."""
        root, kind, notes, label, blue = resolve_blues_choice("D7", "D", "root_minor_blues")
        self.assertEqual(root, "D")
        self.assertEqual(kind, "minor blues")
        self.assertEqual(notes, ["D", "F", "G", "Ab", "A", "C"])
        self.assertEqual(label, "D Blues Scale")
        self.assertEqual(blue, "Ab")

    def test_every_quality_level_and_tier_stays_inside_its_blues_scale(self) -> None:
        for chord, key_center, quality in CHORDS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                for variant in ("easier", "normal", "harder"):
                    for seed in range(6):
                        out = _gen(chord, key_center, level, variant, seed)
                        notes = out["notes"]
                        self.assertTrue(notes, (chord, level, variant, seed))
                        allowed = _scale_pcs_for(chord, key_center, out)
                        got = {_pc(n) for n in notes}
                        self.assertTrue(
                            got.issubset(allowed),
                            f"{quality} {chord} {level}/{variant} seed={seed}: {notes!r} not subset of {allowed!r}",
                        )
                        ok, reason = validate_mission_motif(BLUES_MISSION, out, chord=chord, key_center=key_center)
                        self.assertTrue(ok, (chord, level, variant, seed, reason))

    def test_major_chord_uses_major_blues(self) -> None:
        relationship = choose_blues_relationship("Cmaj7", level="Intermediate", variant="normal")
        self.assertEqual(relationship, "root_major_blues")
        _p, kind, notes, _l, _b = resolve_blues_choice("Cmaj7", "C", relationship)
        self.assertEqual(kind, "major blues")
        self.assertEqual(set(notes), {"C", "D", "Eb", "E", "G", "A"})


class TestBlueNoteAppears(unittest.TestCase):
    """BLUES3 — the blue note actually shows up often enough to be recognizable."""

    def test_blue_note_appears_in_a_meaningful_proportion_of_examples(self) -> None:
        chord, key_center = "D7", "D"
        _p, _k, _notes, _l, blue = resolve_blues_choice(chord, key_center, "root_minor_blues")
        blue_pc = _pc(blue)
        seen = 0
        total = 40
        for seed in range(total):
            out = _gen(chord, key_center, "Intermediate", "normal", seed)
            if blue_pc in {_pc(n) for n in out["notes"]}:
                seen += 1
        self.assertGreater(seen, 10, f"blue note only appeared {seen}/{total} times")
        self.assertLess(seen, total, "blue note on literally every seed is not required")

    def test_mission_is_not_indistinguishable_from_plain_pentatonic(self) -> None:
        """At least some examples must contain a note outside the plain
        pentatonic subset (i.e. the blue note), proving the Mission is
        recognizably different from Pentatonic, not a relabeling of it."""
        from improvisation_mission_rules import resolve_pentatonic_choice

        chord, key_center = "D7", "D"
        _p, _k, pent_notes, _l = resolve_pentatonic_choice(chord, key_center, "root_minor")
        pent_pcs = {_pc(n) for n in pent_notes}
        saw_blue_note_use = False
        for seed in range(30):
            out = _gen(chord, key_center, "Intermediate", "normal", seed)
            got = {_pc(n) for n in out["notes"]}
            if not got.issubset(pent_pcs):
                saw_blue_note_use = True
                break
        self.assertTrue(saw_blue_note_use)


class TestBeginnerIsShortAndSimple(unittest.TestCase):
    """BLUES4 — Beginner stays short/simple."""

    def test_beginner_examples_are_short(self) -> None:
        chord, key_center = "D7", "D"
        for variant in ("easier", "normal", "harder"):
            for seed in range(10):
                out = _gen(chord, key_center, "Beginner", variant, seed)
                self.assertLessEqual(len(out["notes"]), 8, (variant, seed, out["notes"]))


class TestIntermediateMotifBehavior(unittest.TestCase):
    """BLUES5 — Intermediate shows more motif/cell behavior than Beginner."""

    def test_intermediate_uses_skip_shapes(self) -> None:
        from improvisation_mission_rules import _PENTATONIC_VOCAB_PROFILE

        normal = _PENTATONIC_VOCAB_PROFILE[("Intermediate", "normal")]
        self.assertTrue(any(any(abs(d) >= 2 for d in shape) for shape in normal["shapes"]))
        self.assertNotIn("single", normal["modes"])


class TestAdvancedMoreIntervallic(unittest.TestCase):
    """BLUES6 — Advanced shows more intervallic/motivic behavior."""

    def test_advanced_remains_valid_and_uses_wider_shapes_than_beginner(self) -> None:
        from improvisation_mission_rules import _PENTATONIC_VOCAB_PROFILE

        beginner = _PENTATONIC_VOCAB_PROFILE[("Beginner", "normal")]
        advanced = _PENTATONIC_VOCAB_PROFILE[("Advanced", "normal")]
        b_max = max(abs(d) for shape in beginner["shapes"] for d in shape)
        a_max = max(abs(d) for shape in advanced["shapes"] for d in shape)
        self.assertGreater(a_max, b_max)

    def test_advanced_notation_and_midi_stay_exact(self) -> None:
        example = generate_mission_example(
            BLUES_MISSION,
            improv_ctx=ImprovSessionContext(
                song_title="Tune", artist="Artist", key_center="D", display_key="D",
                instrument="Piano", level="Advanced", focus="Improvisation", sections={"Verse": ["D7"]},
            ),
            chord="D7", section="Verse", level="Advanced", instrument="Piano", focus="Improvisation",
        )
        assert_mission_outputs_synchronized(example, expect_tab=False)


class TestNewIdeaVariety(unittest.TestCase):
    """BLUES7 — New Idea yields different valid blues phrases."""

    def test_multiple_seeds_give_distinct_valid_phrases(self) -> None:
        chord, key_center = "D7", "D"
        seen = set()
        for seed in range(15):
            out = _gen(chord, key_center, "Intermediate", "normal", seed)
            allowed = _scale_pcs_for(chord, key_center, out)
            self.assertTrue({_pc(n) for n in out["notes"]}.issubset(allowed))
            seen.add(tuple(out["notes"]))
        self.assertGreaterEqual(len(seen), 5, f"too little variety: {seen!r}")


class TestChordChangeRetargets(unittest.TestCase):
    """BLUES8 — chord change recomputes the correct blues relationship."""

    def test_switching_chord_quality_switches_the_blues_scale(self) -> None:
        maj = _gen("Cmaj7", "C", "Intermediate", "normal", 2)
        dom = _gen("G7", "C", "Intermediate", "normal", 2)
        self.assertEqual(maj["pentatonic_relationship"], "root_major_blues")
        self.assertEqual(dom["pentatonic_relationship"], "root_minor_blues")
        maj_allowed = _scale_pcs_for("Cmaj7", "C", maj)
        dom_allowed = _scale_pcs_for("G7", "C", dom)
        self.assertNotEqual(maj_allowed, dom_allowed)


class TestPracticeKeyTranspose(unittest.TestCase):
    """BLUES9 — D7/D blues -> transpose -> E7/E blues."""

    def test_d7_to_e7_transposes_the_blues_relationship(self) -> None:
        chord = "D7"
        rng = random.Random(2)
        out = apply_mission_rules(
            BLUES_MISSION, {"chord": chord, "notes": [], "midi": []}, chord=chord,
            key_center="D", level="Intermediate", variant="normal", rng=rng,
        )
        raw = {"chord": chord, "motif": out, "concert_key": "D", "display_key": "D"}
        transposed = _transpose_mission_example_payload(raw, from_key="D", to_key="E")
        self.assertIsNotNone(transposed)
        new_chord = transposed["chord"]
        self.assertEqual(new_chord, "E7")
        relationship = transposed["motif"].get("pentatonic_relationship")
        self.assertEqual(relationship, "root_minor_blues")
        _p, _k, new_scale_notes, label, blue = resolve_blues_choice(new_chord, "E", relationship)
        self.assertEqual(set(new_scale_notes), {"E", "G", "A", "Bb", "B", "D"})
        self.assertEqual(label, "E Blues Scale")
        self.assertEqual(blue, "Bb")
        new_notes_pcs = {_pc(n) for n in transposed["motif"]["notes"]}
        self.assertTrue(new_notes_pcs.issubset({_pc(n) for n in new_scale_notes}))


class TestMissionBackingRoundTrip(unittest.TestCase):
    """BLUES10 — Mission Backing lifecycle survives."""

    def test_projection_preserves_relationship_and_concert_identity(self) -> None:
        from mission_projection_state import project_complete_mission_example
        from improvisation_missions import MissionExample

        ex = MissionExample(
            mission=BLUES_MISSION, variant="normal", chord="D7", section="Verse",
            song_title="Tune", display_key="D", concert_key="D", instrument="Piano",
            level="Intermediate", focus="Improvisation",
            motif={"notes": ["D", "F", "Ab", "D"], "midi": [62, 65, 68, 62],
                   "chord": "D7", "pentatonic_relationship": "root_minor_blues", "display": "D-F-Ab-D"},
            abc="", tab="", piano_html="", why="", practice_steps=[], insight=None,
            show_tab=False, show_piano=False,
        )
        sess = {"instrument": "Piano", "concert_key": "D", "display_key": "D"}
        out = project_complete_mission_example(sess, ex, instrument="Piano", bpm=100)
        self.assertEqual(out.motif.get("pentatonic_relationship"), "root_minor_blues")
        self.assertEqual(out.chord, "D7")
        self.assertEqual(
            [_pc(n) for n in out.motif.get("notes")],
            [_pc(n) for n in ex.motif.get("notes")],
        )


class TestWrittenKeySaxophoneProjection(unittest.TestCase):
    """BLUES11 — written-key saxophone projection works."""

    def test_alto_sax_written_projection_preserves_relationship(self) -> None:
        from mission_projection_state import project_complete_mission_example
        from improvisation_missions import MissionExample

        ex = MissionExample(
            mission=BLUES_MISSION, variant="normal", chord="D7", section="Verse",
            song_title="Tune", display_key="D", concert_key="D", instrument="Saxophone",
            level="Intermediate", focus="Improvisation",
            motif={"notes": ["D", "F", "Ab", "D"], "midi": [62, 65, 68, 62],
                   "chord": "D7", "pentatonic_relationship": "root_minor_blues", "display": "D-F-Ab-D"},
            abc="", tab="", piano_html="", why="", practice_steps=[], insight=None,
            show_tab=False, show_piano=False,
        )
        sess = {
            "instrument": "Saxophone", "selected_transposing_instrument": "Alto saxophone (Eb)",
            "show_chart_in_instrument_key": True, "concert_key": "D", "display_key": "D",
        }
        out = project_complete_mission_example(sess, ex, instrument="Saxophone", bpm=100)
        self.assertEqual(out.concert_key, "D")
        self.assertEqual(out.chord, "D7")
        self.assertEqual(out.motif.get("pentatonic_relationship"), "root_minor_blues")
        self.assertNotEqual(out.display_key, out.concert_key)
        self.assertTrue(out.motif.get("notes"))


class TestMissionSelectorStillWorks(unittest.TestCase):
    """BLUES12 — R10 selector switching works."""

    def test_blues_mission_is_in_the_catalog(self) -> None:
        from improvisation_intelligence import PRACTICE_MISSIONS

        self.assertIn(BLUES_MISSION, PRACTICE_MISSIONS)


if __name__ == "__main__":
    unittest.main()
