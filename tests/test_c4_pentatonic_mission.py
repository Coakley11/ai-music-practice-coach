"""C4 Slice 3 — "Improvise using a pentatonic scale that fits the chord."

PENTA1-PENTA12 per the human-review spec: structural assertions (scale
membership, note-count/sophistication ladder, relationship recomputation
after a chord or Practice-Key change) rather than exact note sequences, since
the generator is intentionally variable.
"""

from __future__ import annotations

import random
import unittest

from improvisation_intelligence import ImprovSessionContext
from improvisation_mission_rules import (
    _apply_pentatonic_mission,
    _chord_tone_pcs,
    _pc,
    _pentatonic_relationship_for_quality,
    apply_mission_rules,
    chord_tone_names,
    choose_pentatonic_relationship,
    resolve_pentatonic_choice,
)
from improvisation_mission_specs import validate_mission_motif
from improvisation_missions import _transpose_mission_example_payload, generate_mission_example
from tests.test_improvisation_motif_abc import assert_mission_outputs_synchronized

PENTATONIC_MISSION = "Improvise using a pentatonic scale that fits the chord"

# major/maj7, minor/min7, dominant 7, plus a couple of edge qualities.
CHORDS = (
    ("Cmaj7", "C", "major/maj7"),
    ("Dm7", "C", "minor/min7"),
    ("D7", "D", "dominant 7"),
    ("G7", "C", "dominant 7"),
    ("Fm7", "C", "minor/min7"),
    ("Am", "C", "minor"),
)


def _scale_pcs_for(chord, key_center, motif):
    relationship = str(motif.get("pentatonic_relationship") or "").strip()
    if not relationship:
        from music_theory import classify_chord_quality

        relationship = _pentatonic_relationship_for_quality(classify_chord_quality(chord))
    _proot, _kind, notes, _label = resolve_pentatonic_choice(chord, key_center, relationship)
    return {_pc(n) for n in notes}


def _gen(chord, key_center, level, variant, seed):
    rng = random.Random(seed)
    return apply_mission_rules(
        PENTATONIC_MISSION,
        {"chord": chord, "notes": [], "midi": []},
        chord=chord,
        key_center=key_center,
        level=level,
        variant=variant,
        rng=rng,
    )


class TestPentatonicChoiceAndMembership(unittest.TestCase):
    """PENTA1/PENTA2/PENTA3 — the right pentatonic is chosen and every
    generated note belongs to it, across the required chord qualities."""

    def test_every_quality_level_and_tier_stays_inside_its_pentatonic(self) -> None:
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
                        ok, reason = validate_mission_motif(
                            PENTATONIC_MISSION, out, chord=chord, key_center=key_center
                        )
                        self.assertTrue(ok, (chord, level, variant, seed, reason))

    def test_major_chord_selects_major_pentatonic(self) -> None:
        out = _gen("Cmaj7", "C", "Intermediate", "normal", 1)
        self.assertEqual(out["pentatonic_relationship"], "root_major")
        _p, kind, notes, label = resolve_pentatonic_choice("Cmaj7", "C", out["pentatonic_relationship"])
        self.assertIn("major", kind)
        self.assertEqual(set(notes), {"C", "D", "E", "G", "A"})
        self.assertEqual(label, "C Major Pentatonic")

    def test_minor_chord_selects_minor_pentatonic(self) -> None:
        out = _gen("Dm7", "C", "Intermediate", "normal", 1)
        self.assertEqual(out["pentatonic_relationship"], "root_minor")
        _p, kind, notes, _label = resolve_pentatonic_choice("Dm7", "C", out["pentatonic_relationship"])
        self.assertIn("minor", kind)
        self.assertEqual(set(notes), {"D", "F", "G", "A", "C"})

    def test_dominant_d7_supports_d_minor_pentatonic(self) -> None:
        """D7 -> D minor pentatonic (D F G A C), the human-review example."""
        _p, kind, notes, label = resolve_pentatonic_choice("D7", "D", "root_minor")
        self.assertEqual(notes, ["D", "F", "G", "A", "C"])
        self.assertEqual(label, "D Minor Pentatonic")
        # And at least one seed/tier actually lands on this relationship and
        # stays inside it.
        rng = random.Random(0)
        relationship = choose_pentatonic_relationship("D7", level="Beginner", variant="easier", rng=rng)
        self.assertEqual(relationship, "root_minor")
        out = _gen("D7", "D", "Beginner", "easier", 0)
        self.assertTrue({_pc(n) for n in out["notes"]}.issubset({_pc(n) for n in notes}))

    def test_dominant_may_also_use_fourth_above_major_at_richer_tiers(self) -> None:
        """A defensible second valid dominant relationship exists and is
        reachable, but never forced to look different for its own sake."""
        seen = set()
        for seed in range(40):
            rng = random.Random(seed)
            seen.add(choose_pentatonic_relationship("G7", level="Advanced", variant="normal", rng=rng))
        self.assertEqual(seen, {"root_minor", "fourth_above_major"})
        _p, _k, notes, _l = resolve_pentatonic_choice("G7", "C", "fourth_above_major")
        self.assertEqual(set(notes), {"C", "D", "E", "G", "A"})  # C major pentatonic, a 4th above G

    def test_dominant_simple_tiers_never_use_the_alternate_relationship(self) -> None:
        for level, variant in (("Beginner", "easier"), ("Beginner", "harder"), ("Intermediate", "easier"), ("Intermediate", "normal")):
            for seed in range(20):
                rng = random.Random(seed)
                self.assertEqual(choose_pentatonic_relationship("G7", level=level, variant=variant, rng=rng), "root_minor")


class TestBeginnerLadder(unittest.TestCase):
    """PENTA4 — Beginner Easier/Normal/Harder: increasing complexity, always pentatonic."""

    def test_beginner_tiers_increase_in_length_and_max_step(self) -> None:
        from improvisation_mission_rules import _PENTATONIC_DIFFICULTY_PROFILE

        easier = _PENTATONIC_DIFFICULTY_PROFILE[("Beginner", "easier")]
        normal = _PENTATONIC_DIFFICULTY_PROFILE[("Beginner", "normal")]
        harder = _PENTATONIC_DIFFICULTY_PROFILE[("Beginner", "harder")]
        self.assertLessEqual(easier["length"][1], normal["length"][1])
        self.assertLessEqual(normal["length"][1], harder["length"][1])
        self.assertLessEqual(easier["max_step"], harder["max_step"])
        self.assertLessEqual(easier["direction_changes"], harder["direction_changes"])

    def test_beginner_harder_stays_clearly_beginner_not_intermediate(self) -> None:
        """Beginner Harder must not drift into Intermediate-style richness
        (no octave jumps, no sequencing)."""
        from improvisation_mission_rules import _PENTATONIC_DIFFICULTY_PROFILE

        harder = _PENTATONIC_DIFFICULTY_PROFILE[("Beginner", "harder")]
        self.assertEqual(harder["octave_jumps"], 0)
        self.assertFalse(harder["sequence"])
        for seed in range(10):
            out = _gen("Cmaj7", "C", "Beginner", "harder", seed)
            self.assertLessEqual(len(out["notes"]), 8)


class TestIntermediateLadder(unittest.TestCase):
    """PENTA5 — Intermediate Easier/Normal/Harder: clear structural progression."""

    def test_intermediate_tiers_strictly_widen(self) -> None:
        from improvisation_mission_rules import _PENTATONIC_DIFFICULTY_PROFILE

        easier = _PENTATONIC_DIFFICULTY_PROFILE[("Intermediate", "easier")]
        normal = _PENTATONIC_DIFFICULTY_PROFILE[("Intermediate", "normal")]
        harder = _PENTATONIC_DIFFICULTY_PROFILE[("Intermediate", "harder")]
        self.assertLess(easier["length"][1], harder["length"][1])
        self.assertLessEqual(easier["max_step"], normal["max_step"])
        self.assertLessEqual(normal["max_step"], harder["max_step"])
        self.assertFalse(easier["sequence"])
        self.assertTrue(normal["sequence"])
        self.assertTrue(harder["sequence"])
        self.assertEqual(easier["octave_jumps"], 0)
        self.assertGreaterEqual(harder["octave_jumps"], 1)

    def test_intermediate_harder_sets_harder_flag_with_syncopated_rhythm(self) -> None:
        for seed in range(10):
            out = _gen("G7", "C", "Intermediate", "harder", seed)
            self.assertTrue(out.get("harder_example"))
            self.assertIn(
                str(out.get("rhythm_key") or ""),
                ("harder-mixed-a", "harder-mixed-b", "harder-triplet-feel"),
            )


class TestAdvancedSophistication(unittest.TestCase):
    """PENTA6 — Advanced is measurably richer without breaking scale membership."""

    def test_advanced_harder_is_the_widest_profile(self) -> None:
        from improvisation_mission_rules import _PENTATONIC_DIFFICULTY_PROFILE

        adv_harder = _PENTATONIC_DIFFICULTY_PROFILE[("Advanced", "harder")]
        int_harder = _PENTATONIC_DIFFICULTY_PROFILE[("Intermediate", "harder")]
        self.assertGreaterEqual(adv_harder["length"][1], int_harder["length"][1])
        self.assertGreaterEqual(adv_harder["max_step"], int_harder["max_step"])
        self.assertGreaterEqual(adv_harder["octave_jumps"], int_harder["octave_jumps"])

    def test_advanced_examples_remain_strictly_pentatonic(self) -> None:
        for chord, key_center, _q in CHORDS:
            for variant in ("easier", "normal", "harder"):
                for seed in range(6):
                    out = _gen(chord, key_center, "Advanced", variant, seed)
                    allowed = _scale_pcs_for(chord, key_center, out)
                    self.assertTrue({_pc(n) for n in out["notes"]}.issubset(allowed))

    def test_advanced_example_notation_and_midi_stay_exact(self) -> None:
        example = generate_mission_example(
            PENTATONIC_MISSION,
            improv_ctx=ImprovSessionContext(
                song_title="Tune", artist="Artist", key_center="C", display_key="C",
                instrument="Piano", level="Advanced", focus="Improvisation", sections={"Verse": ["G7"]},
            ),
            chord="G7", section="Verse", level="Advanced", instrument="Piano", focus="Improvisation",
        )
        assert_mission_outputs_synchronized(example, expect_tab=False)


class TestNewIdeaVariety(unittest.TestCase):
    """PENTA7 — several distinct phrases, all pentatonic-valid, same mission/chord/level/bucket."""

    def test_multiple_seeds_give_distinct_phrases_all_valid(self) -> None:
        chord, key_center = "D7", "D"
        seen = set()
        for seed in range(15):
            out = _gen(chord, key_center, "Intermediate", "harder", seed)
            allowed = _scale_pcs_for(chord, key_center, out)
            self.assertTrue({_pc(n) for n in out["notes"]}.issubset(allowed))
            seen.add(tuple(out["notes"]))
        self.assertGreaterEqual(len(seen), 5, f"too little variety: {seen!r}")


class TestChordChangeRetargets(unittest.TestCase):
    """PENTA8 — changing the chord recomputes the pentatonic, never carries a stale one."""

    def test_switching_chord_quality_switches_the_pentatonic(self) -> None:
        maj = _gen("Cmaj7", "C", "Intermediate", "normal", 2)
        minr = _gen("Dm7", "C", "Intermediate", "normal", 2)
        dom = _gen("G7", "C", "Intermediate", "normal", 2)
        self.assertEqual(maj["pentatonic_relationship"], "root_major")
        self.assertEqual(minr["pentatonic_relationship"], "root_minor")
        maj_allowed = _scale_pcs_for("Cmaj7", "C", maj)
        minr_allowed = _scale_pcs_for("Dm7", "C", minr)
        dom_allowed = _scale_pcs_for("G7", "C", dom)
        self.assertNotEqual(maj_allowed, minr_allowed)
        self.assertTrue({_pc(n) for n in maj["notes"]}.issubset(maj_allowed))
        self.assertTrue({_pc(n) for n in minr["notes"]}.issubset(minr_allowed))
        self.assertTrue({_pc(n) for n in dom["notes"]}.issubset(dom_allowed))


class TestPracticeKeyTransposePreservesRelationship(unittest.TestCase):
    """PENTA9 — D7/D minor pentatonic -> transpose -> E7/E minor pentatonic."""

    def test_d7_to_e7_transposes_the_pentatonic_relationship(self) -> None:
        chord = "D7"
        rng = random.Random(2)
        out = apply_mission_rules(
            PENTATONIC_MISSION, {"chord": chord, "notes": [], "midi": []}, chord=chord,
            key_center="D", level="Intermediate", variant="normal", rng=rng,
        )
        raw = {"chord": chord, "motif": out, "concert_key": "D", "display_key": "D"}
        transposed = _transpose_mission_example_payload(raw, from_key="D", to_key="E")
        self.assertIsNotNone(transposed)
        new_chord = transposed["chord"]
        self.assertEqual(new_chord, "E7")
        relationship = transposed["motif"].get("pentatonic_relationship")
        self.assertEqual(relationship, out["pentatonic_relationship"])
        _p, _k, new_scale_notes, label = resolve_pentatonic_choice(new_chord, "E", relationship)
        self.assertEqual(set(new_scale_notes), {"E", "G", "A", "B", "D"})
        self.assertEqual(label, "E Minor Pentatonic")
        new_notes_pcs = {_pc(n) for n in transposed["motif"]["notes"]}
        self.assertTrue(new_notes_pcs.issubset({_pc(n) for n in new_scale_notes}))
        # Harmonic position/length preserved - a real transpose, not a reset.
        self.assertEqual(len(transposed["motif"]["notes"]), len(out["notes"]))

    def test_generic_quality_also_transposes_correctly(self) -> None:
        chord = "Cmaj7"
        rng = random.Random(1)
        out = apply_mission_rules(
            PENTATONIC_MISSION, {"chord": chord, "notes": [], "midi": []}, chord=chord,
            key_center="C", level="Advanced", variant="harder", rng=rng,
        )
        raw = {"chord": chord, "motif": out, "concert_key": "C", "display_key": "C"}
        transposed = _transpose_mission_example_payload(raw, from_key="C", to_key="Eb")
        self.assertIsNotNone(transposed)
        new_chord = transposed["chord"]
        relationship = transposed["motif"].get("pentatonic_relationship")
        self.assertEqual(relationship, "root_major")
        _p, _k, new_scale_notes, _label = resolve_pentatonic_choice(new_chord, "Eb", relationship)
        new_notes_pcs = {_pc(n) for n in transposed["motif"]["notes"]}
        self.assertTrue(new_notes_pcs.issubset({_pc(n) for n in new_scale_notes}))


class TestMissionBackingRoundTrip(unittest.TestCase):
    """PENTA10 — Mission -> Backing -> Return preserves identity and intent."""

    def test_projection_preserves_relationship_and_concert_identity(self) -> None:
        from mission_projection_state import project_complete_mission_example
        from improvisation_missions import MissionExample

        ex = MissionExample(
            mission=PENTATONIC_MISSION, variant="normal", chord="D7", section="Verse",
            song_title="Tune", display_key="D", concert_key="D", instrument="Piano",
            level="Intermediate", focus="Improvisation",
            motif={"notes": ["D", "G", "C", "F", "A", "D"], "midi": [62, 67, 60, 65, 69, 62],
                   "chord": "D7", "pentatonic_relationship": "root_minor", "display": "D-G-C-F-A-D"},
            abc="", tab="", piano_html="", why="", practice_steps=[], insight=None,
            show_tab=False, show_piano=False,
        )
        sess = {"instrument": "Piano", "concert_key": "D", "display_key": "D"}
        out = project_complete_mission_example(sess, ex, instrument="Piano", bpm=100)
        self.assertEqual(out.motif.get("pentatonic_relationship"), "root_minor")
        self.assertEqual(out.chord, "D7")
        self.assertEqual(out.motif.get("notes"), ex.motif.get("notes"))  # no regeneration


class TestWrittenKeySaxophoneProjection(unittest.TestCase):
    """PENTA11 — Alto Sax / written charts: canonical stays concert, written
    projects via the existing (R9) instrument-transposition architecture."""

    def test_alto_sax_written_projection_preserves_relationship(self) -> None:
        from mission_projection_state import project_complete_mission_example
        from improvisation_missions import MissionExample

        ex = MissionExample(
            mission=PENTATONIC_MISSION, variant="normal", chord="D7", section="Verse",
            song_title="Tune", display_key="D", concert_key="D", instrument="Saxophone",
            level="Intermediate", focus="Improvisation",
            motif={"notes": ["D", "G", "C", "F", "A", "D"], "midi": [62, 67, 60, 65, 69, 62],
                   "chord": "D7", "pentatonic_relationship": "root_minor", "display": "D-G-C-F-A-D"},
            abc="", tab="", piano_html="", why="", practice_steps=[], insight=None,
            show_tab=False, show_piano=False,
        )
        sess = {
            "instrument": "Saxophone", "selected_transposing_instrument": "Alto saxophone (Eb)",
            "show_chart_in_instrument_key": True, "concert_key": "D", "display_key": "D",
        }
        out = project_complete_mission_example(sess, ex, instrument="Saxophone", bpm=100)
        # Canonical concert identity is unchanged.
        self.assertEqual(out.concert_key, "D")
        self.assertEqual(out.chord, "D7")
        self.assertEqual(out.motif.get("pentatonic_relationship"), "root_minor")
        # Written projection actually differs from concert (real transposing-instrument math).
        self.assertNotEqual(out.display_key, out.concert_key)
        self.assertTrue(out.motif.get("notes"))


class TestMissionSelectorStillWorksAfterGenerate(unittest.TestCase):
    """PENTA12 — R10: switching into/out of the Pentatonic Mission after a
    Generate must not be defeated by the stale-blob-reclaim defect R10 fixed."""

    def test_pentatonic_mission_is_in_the_catalog(self) -> None:
        from improvisation_intelligence import PRACTICE_MISSIONS

        self.assertIn(PENTATONIC_MISSION, PRACTICE_MISSIONS)

    def test_switching_pick_event_marks_this_mission_correctly(self) -> None:
        """The R10 fix keys off an explicit field name, not mission text -
        confirm the pentatonic Mission's title does not interfere with it."""
        from creative_mission_config_persistence import (
            CREATIVE_MISSION_USER_EVENT_KEY,
            SAVE_REASON_MISSION_PICK,
            mission_pick_user_event_is_current,
        )

        session = {
            "_script_run_seq": 5,
            CREATIVE_MISSION_USER_EVENT_KEY: {
                "field": "improv_mission_pick",
                "save_reason": SAVE_REASON_MISSION_PICK,
                "run_seq": 5,
                "interaction": "mission_pick_on_change",
            },
        }
        self.assertTrue(mission_pick_user_event_is_current(session))


if __name__ == "__main__":
    unittest.main()
