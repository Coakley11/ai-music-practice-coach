"""C4 musical-quality refinement — "Resolve convincingly to the chord's 3rd".

Human review found the generated examples too plain: the lead-in notes were a
disconnected pattern with the 3rd stapled on afterward rather than an actual
approach into it. These tests pin the fix at the structural level — approach
vocabulary, resolve-to-3rd correctness, chord-quality coverage, the
Intermediate Easier/Normal/Harder ladder, New Idea variety, chord-change
retargeting — never a single exact note sequence, since the generator is
intentionally variable.
"""

from __future__ import annotations

import random
import unittest

from improvisation_mission_rules import (
    _pattern_engine_target_notes,
    _pc,
    _simple_third_approach,
    apply_mission_rules,
    chord_tone_names,
)
from improvisation_mission_specs import validate_mission_motif

TARGET_THIRD_MISSION = "Resolve convincingly to the chord's 3rd"

# Major/maj7, minor/min7, dominant 7 — the chord-quality coverage the review asked for.
CHORDS = (
    ("Cmaj7", "C", "major/maj7"),
    ("Dm7", "C", "minor/min7"),
    ("G7", "C", "dominant 7"),
    ("Fm7", "C", "minor/min7"),
    ("E7", "C", "dominant 7"),
    ("Abmaj7", "C", "major/maj7"),
)


def _third_pc(chord: str, key_center: str) -> int:
    tones = chord_tone_names(chord, reference_key=key_center)
    return _pc(tones[1] if len(tones) >= 2 else tones[0])


def _generate(chord, key_center, level, variant, seed):
    rng = random.Random(seed)
    return apply_mission_rules(
        TARGET_THIRD_MISSION,
        {"chord": chord, "notes": [], "midi": []},
        chord=chord,
        key_center=key_center,
        level=level,
        variant=variant,
        rng=rng,
    )


class TestResolvesToTheActualThird(unittest.TestCase):
    """The hard contract — last note's pitch class is the chord's 3rd — must
    hold for every chord quality, level and difficulty tier. Never weakened."""

    def test_every_chord_quality_level_and_tier(self) -> None:
        for chord, key_center, quality in CHORDS:
            third_pc = _third_pc(chord, key_center)
            for level in ("Beginner", "Intermediate", "Advanced"):
                for variant in ("easier", "normal", "harder"):
                    for seed in range(5):
                        out = _generate(chord, key_center, level, variant, seed)
                        notes = out["notes"]
                        self.assertTrue(notes, (chord, level, variant, seed))
                        self.assertEqual(
                            _pc(notes[-1]),
                            third_pc,
                            f"{quality} {chord} {level}/{variant} seed={seed}: {notes!r}",
                        )
                        ok, reason = validate_mission_motif(
                            TARGET_THIRD_MISSION, out, chord=chord, key_center=key_center
                        )
                        self.assertTrue(ok, (chord, level, variant, seed, reason))

    def test_no_adjacent_duplicate_pitch_class_before_the_target(self) -> None:
        """Regression guard for the diatonic-neighbor off-by-one: the note
        right before the target must never collapse onto the target's own
        pitch class (that is a neighbor figure, not an approach)."""
        for chord, key_center, _quality in CHORDS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                for variant in ("easier", "normal", "harder"):
                    for seed in range(20):
                        out = _generate(chord, key_center, level, variant, seed)
                        notes = out["notes"]
                        if len(notes) >= 2:
                            self.assertNotEqual(
                                _pc(notes[-2]),
                                _pc(notes[-1]),
                                f"{chord} {level}/{variant} seed={seed}: {notes!r}",
                            )


class TestApproachIsConnectedNotStapledOn(unittest.TestCase):
    """The root-cause defect: the lead-in must belong to the SAME resolving
    cell as the target, not a disconnected pattern with the 3rd appended."""

    def test_forced_target_notes_always_end_on_the_requested_role(self) -> None:
        for chord, key_center, _quality in CHORDS:
            third_pc = _third_pc(chord, key_center)
            for difficulty in ("Intermediate", "Advanced"):
                for seed in range(10):
                    rng = random.Random(seed)
                    lead = _pattern_engine_target_notes(
                        chord,
                        key_center=key_center,
                        difficulty=difficulty,
                        rng=rng,
                        categories={"chromatic_approach", "enclosure"},
                        target_role="3",
                    )
                    if lead is not None:
                        self.assertEqual(_pc(lead[-1]), third_pc, (chord, difficulty, seed, lead))
                        # More than a bare target: there is an actual approach.
                        self.assertGreaterEqual(len(lead), 2, (chord, difficulty, seed, lead))

    def test_simple_approach_is_exactly_two_notes_ending_on_target(self) -> None:
        for target in ("E", "F", "B", "Ab", "G#", "C"):
            for key_center in ("C", "D", "Eb", "F#"):
                for seed in range(15):
                    rng = random.Random(seed)
                    notes = _simple_third_approach(target, key_center=key_center, rng=rng)
                    self.assertEqual(len(notes), 2)
                    self.assertEqual(notes[1], target)
                    self.assertNotEqual(_pc(notes[0]), _pc(notes[1]))


class TestIntermediateLadderIsStructurallyProgressive(unittest.TestCase):
    """Easier < Normal < Harder in vocabulary sophistication — measured by
    structural properties (note count, family richness), never one exact
    note sequence, since the generator is intentionally variable."""

    def test_easier_is_never_longer_than_normal_or_harder(self) -> None:
        chord, key_center = "Cmaj7", "C"
        for seed in range(15):
            easier = _generate(chord, key_center, "Intermediate", "easier", seed)
            normal = _generate(chord, key_center, "Intermediate", "normal", seed)
            harder = _generate(chord, key_center, "Intermediate", "harder", seed)
            self.assertLessEqual(len(easier["notes"]), len(normal["notes"]))
            self.assertLessEqual(len(normal["notes"]), len(harder["notes"]))

    def test_easier_never_uses_the_pattern_engine(self) -> None:
        """Easier is always the bespoke 2-note approach — never the engine,
        which is incapable of producing a 2-note resolving cell here."""
        chord, key_center = "Dm7", "C"
        for seed in range(20):
            out = _generate(chord, key_center, "Intermediate", "easier", seed)
            self.assertEqual(len(out["notes"]), 2)

    def test_harder_sets_the_harder_example_flag_and_displaces_rhythm(self) -> None:
        chord, key_center = "G7", "C"
        for seed in range(10):
            out = _generate(chord, key_center, "Intermediate", "harder", seed)
            self.assertTrue(out.get("harder_example"))
            self.assertIn(str(out.get("rhythm_key") or ""), ("harder-mixed-a", "harder-mixed-b", "harder-triplet-feel"))

    def test_harder_family_pool_is_a_strict_superset_of_normal(self) -> None:
        """Harder draws from every family Normal can plus the richer
        Advanced-tagged ones (double approach, four-note/double-chromatic
        enclosure, chromatic run) — never a narrower or unrelated pool."""
        from improvisation_mission_rules import eligible_families

        chord, key_center = "Cmaj7", "C"
        categories = {"chromatic_approach", "enclosure"}

        def _family_ids(difficulty):
            return {
                fam.id
                for fam, _w in eligible_families(key=key_center, chord=chord, difficulty=difficulty, chromatic="auto")
                if fam.category in categories
                and fam.builder is None
                and fam.target_index is not None
                and "3" in fam.start_roles
                and fam.target_index < len(fam.cell)
                and fam.cell[fam.target_index] == ("A", 0)
            }

        normal_pool = _family_ids("Intermediate")
        harder_pool = _family_ids("Advanced")
        self.assertTrue(normal_pool, "Normal pool must not be empty")
        self.assertTrue(harder_pool.issuperset(normal_pool))
        self.assertGreater(len(harder_pool), len(normal_pool))

    def test_advanced_easier_is_lighter_than_advanced_normal(self) -> None:
        chord, key_center = "E7", "C"
        for seed in range(10):
            easier = _generate(chord, key_center, "Advanced", "easier", seed)
            normal = _generate(chord, key_center, "Advanced", "normal", seed)
            self.assertLessEqual(len(easier["notes"]), len(normal["notes"]))


class TestNewIdeaVariety(unittest.TestCase):
    """Several New Idea presses (distinct seeds) must give genuinely
    different approaches while the target objective never changes."""

    def test_multiple_seeds_produce_distinct_approaches(self) -> None:
        chord, key_center = "Cmaj7", "C"
        third_pc = _third_pc(chord, key_center)
        seen = set()
        for seed in range(12):
            out = _generate(chord, key_center, "Intermediate", "harder", seed)
            notes = tuple(out["notes"])
            self.assertEqual(_pc(notes[-1]), third_pc)
            seen.add(notes)
        self.assertGreaterEqual(len(seen), 4, f"too little variety: {seen!r}")


class TestChordChangeRetargets(unittest.TestCase):
    """Changing the selected chord must retarget to the NEW chord's 3rd and
    the approach vocabulary must re-derive from the new chord, not linger on
    the old one's pitch classes."""

    def test_target_and_vocabulary_follow_the_chord(self) -> None:
        key_center = "C"
        for chord in ("Cmaj7", "Fm7", "E7", "Abmaj7"):
            third_pc = _third_pc(chord, key_center)
            rng = random.Random(3)
            out = apply_mission_rules(
                TARGET_THIRD_MISSION,
                {"chord": chord, "notes": [], "midi": []},
                chord=chord,
                key_center=key_center,
                level="Intermediate",
                variant="normal",
                rng=rng,
            )
            self.assertEqual(_pc(out["notes"][-1]), third_pc, chord)


class TestPracticeKeyTransposePreservesTarget(unittest.TestCase):
    """A Practice-Key change must transpose the whole approach, keeping the
    musical approach-to-3rd relationship (R7/R8 harmonic-position contract)."""

    def test_transposed_example_still_resolves_to_the_new_key_third(self) -> None:
        from improvisation_missions import _transpose_mission_example_payload
        from music_theory import semitone_distance, transpose_chord

        chord = "Cmaj7"
        rng = random.Random(5)
        out = apply_mission_rules(
            TARGET_THIRD_MISSION,
            {"chord": chord, "notes": [], "midi": []},
            chord=chord,
            key_center="C",
            level="Intermediate",
            variant="normal",
            rng=rng,
        )
        raw = {"chord": chord, "motif": out, "concert_key": "C", "display_key": "C"}
        transposed = _transpose_mission_example_payload(raw, from_key="C", to_key="D")
        self.assertIsNotNone(transposed)
        new_chord = transpose_chord(chord, semitone_distance("C", "D"), reference_key="D")
        new_third_pc = _third_pc(new_chord, "D")
        self.assertEqual(_pc(transposed["motif"]["notes"][-1]), new_third_pc)
        # Same number of notes — the approach shape itself survives the transpose.
        self.assertEqual(len(transposed["motif"]["notes"]), len(out["notes"]))


if __name__ == "__main__":
    unittest.main()
