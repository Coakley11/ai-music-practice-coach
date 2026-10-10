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

    def test_beginner_tiers_increase_in_shape_richness_and_length(self) -> None:
        from improvisation_mission_rules import _PENTATONIC_VOCAB_PROFILE

        easier = _PENTATONIC_VOCAB_PROFILE[("Beginner", "easier")]
        normal = _PENTATONIC_VOCAB_PROFILE[("Beginner", "normal")]
        harder = _PENTATONIC_VOCAB_PROFILE[("Beginner", "harder")]
        self.assertLessEqual(len(easier["shapes"]), len(normal["shapes"]))
        self.assertLessEqual(len(normal["shapes"]), len(harder["shapes"]))

        def avg_len(level_tier_profile, n=20):
            lengths = []
            for seed in range(n):
                rng = random.Random(seed)
                from improvisation_mission_rules import _assemble_cell_phrase

                midis, _m, _s = _assemble_cell_phrase(
                    {0, 3, 5, 7, 10}, rng=rng, anchor_pc=0, chord_tone_pcs=set(),
                    shapes=level_tier_profile["shapes"], modes=level_tier_profile["modes"],
                    register_jumps=level_tier_profile.get("register_jumps", 0),
                )
                lengths.append(len(midis))
            return sum(lengths) / len(lengths)

        self.assertLessEqual(avg_len(easier), avg_len(harder))

    def test_beginner_harder_stays_clearly_beginner_not_intermediate(self) -> None:
        """Beginner Harder must not drift into Intermediate-style richness:
        only scalar/adjacent shapes, no register displacement, short phrases."""
        from improvisation_mission_rules import _PENTATONIC_VOCAB_PROFILE, _CELLS_SKIP, _CELLS_WIDE

        harder = _PENTATONIC_VOCAB_PROFILE[("Beginner", "harder")]
        self.assertEqual(harder.get("register_jumps", 0), 0)
        for shape in harder["shapes"]:
            self.assertTrue(all(abs(d) <= 1 for d in shape), shape)
            self.assertNotIn(shape, _CELLS_WIDE)
        for seed in range(10):
            out = _gen("Cmaj7", "C", "Beginner", "harder", seed)
            self.assertLessEqual(len(out["notes"]), 8)


class TestIntermediateLadder(unittest.TestCase):
    """PENTA5 — Intermediate Easier/Normal/Harder: clear structural progression."""

    def test_intermediate_tiers_use_cells_not_pure_scalar_motion(self) -> None:
        """Intermediate must stop being "scale practice": its shapes include
        skips (|delta| >= 2), and Harder's shape pool strictly includes
        Normal's plus wider shapes."""
        from improvisation_mission_rules import _PENTATONIC_VOCAB_PROFILE, _CELLS_SCALAR

        easier = _PENTATONIC_VOCAB_PROFILE[("Intermediate", "easier")]
        normal = _PENTATONIC_VOCAB_PROFILE[("Intermediate", "normal")]
        harder = _PENTATONIC_VOCAB_PROFILE[("Intermediate", "harder")]
        for tier in (easier, normal, harder):
            self.assertTrue(
                any(any(abs(d) >= 2 for d in shape) for shape in tier["shapes"]),
                "Intermediate must include skip shapes, not pure adjacent motion",
            )
        self.assertEqual(easier.get("register_jumps", 0), 0)
        self.assertGreaterEqual(harder.get("register_jumps", 0), 1)
        # Intermediate favors repeat/sequence (real cells/motifs), not single.
        self.assertNotIn("single", normal["modes"])
        self.assertNotIn("single", harder["modes"])

    def test_intermediate_harder_sets_harder_flag_with_syncopated_rhythm(self) -> None:
        for seed in range(10):
            out = _gen("G7", "C", "Intermediate", "harder", seed)
            self.assertTrue(out.get("harder_example"))
            self.assertEqual(out.get("rhythm_key"), "engine")


class TestAdvancedSophistication(unittest.TestCase):
    """PENTA6 — Advanced is measurably richer without breaking scale membership."""

    def test_advanced_harder_uses_the_widest_shapes_and_most_displacement(self) -> None:
        from improvisation_mission_rules import _PENTATONIC_VOCAB_PROFILE

        adv_harder = _PENTATONIC_VOCAB_PROFILE[("Advanced", "harder")]
        int_harder = _PENTATONIC_VOCAB_PROFILE[("Intermediate", "harder")]
        adv_max = max(abs(d) for shape in adv_harder["shapes"] for d in shape)
        int_max = max(abs(d) for shape in int_harder["shapes"] for d in shape)
        self.assertGreaterEqual(adv_max, int_max)
        self.assertGreaterEqual(adv_harder.get("register_jumps", 0), int_harder.get("register_jumps", 0))
        # Advanced favors motif development (sequence/chain), not bare singles.
        self.assertNotIn("single", adv_harder["modes"])

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


def _adjacent_step_fraction(notes, ordered_pcs):
    """Fraction of consecutive note-pairs that are ADJACENT members of the
    ordered pentatonic collection (cyclic index distance == 1) - i.e. plain
    scale-step motion. Low for a motif/cell-based phrase, high for a scale run."""
    if len(notes) < 2:
        return 0.0
    n = len(ordered_pcs)
    idx = {pc: i for i, pc in enumerate(ordered_pcs)}
    total = 0
    adjacent = 0
    for a, b in zip(notes, notes[1:]):
        pa, pb = _pc(a), _pc(b)
        if pa not in idx or pb not in idx:
            continue
        total += 1
        d = (idx[pb] - idx[pa]) % n
        if min(d, n - d) == 1:
            adjacent += 1
    return (adjacent / total) if total else 0.0


def _has_repeated_or_sequenced_cell(notes, ordered_pcs):
    """True when the pitch-class sequence contains either a literal repeated
    2/3-note cell, or the same index-delta shape recurring elsewhere in the
    phrase (a sequence - "repeat" and "sequence" assembly modes are not
    always back-to-back once register-jump/chord-tone-landing adjustments
    run, so this checks ANY two occurrences of a window, not just adjacent
    ones) - the motif-based constructions this Mission's refinement asks for."""
    pcs_list = [_pc(n) for n in notes]

    def _any_repeated_window(seq, k):
        seen = set()
        for i in range(len(seq) - k + 1):
            window = tuple(seq[i : i + k])
            if None in window:
                continue
            if window in seen:
                return True
            seen.add(window)
        return False

    for k in (2, 3):
        if _any_repeated_window(pcs_list, k):
            return True
    n = len(ordered_pcs)
    idx = {pc: i for i, pc in enumerate(ordered_pcs)}
    deltas = []
    for a, b in zip(pcs_list, pcs_list[1:]):
        if a not in idx or b not in idx:
            deltas.append(None)
            continue
        d = (idx[b] - idx[a]) % n
        if d > n // 2:
            d -= n
        deltas.append(d)
    for k in (2, 3):
        if _any_repeated_window(deltas, k):
            return True
    return False


class TestAvoidsExcessiveScalarMotion(unittest.TestCase):
    """Human-review musicality refinement: increasing difficulty must mean
    richer PENTATONIC VOCABULARY (cells, motifs, skips, sequences) - not
    "play farther up and down the scale". Measured structurally across a
    deterministic seed sweep, never pinned to one exact phrase."""

    def test_beginner_may_be_heavily_scalar(self) -> None:
        chord, key_center = "Cmaj7", "C"
        fracs = []
        for seed in range(40):
            out = _gen(chord, key_center, "Beginner", "normal", seed)
            relationship = out["pentatonic_relationship"]
            _p, _k, scale_notes, _l = resolve_pentatonic_choice(chord, key_center, relationship)
            ordered = [_pc(n) for n in scale_notes]
            fracs.append(_adjacent_step_fraction(out["notes"], ordered))
        self.assertGreater(sum(fracs) / len(fracs), 0.5)

    def test_intermediate_is_markedly_less_scalar_than_beginner(self) -> None:
        chord, key_center = "Cmaj7", "C"

        def avg_fraction(level):
            fracs = []
            for seed in range(40):
                out = _gen(chord, key_center, level, "normal", seed)
                relationship = out["pentatonic_relationship"]
                _p, _k, scale_notes, _l = resolve_pentatonic_choice(chord, key_center, relationship)
                ordered = [_pc(n) for n in scale_notes]
                fracs.append(_adjacent_step_fraction(out["notes"], ordered))
            return sum(fracs) / len(fracs)

        beginner_frac = avg_fraction("Beginner")
        intermediate_frac = avg_fraction("Intermediate")
        self.assertLess(intermediate_frac, beginner_frac)

    def test_advanced_shows_more_non_adjacent_movement_than_beginner(self) -> None:
        chord, key_center = "Cmaj7", "C"

        def avg_fraction(level):
            fracs = []
            for seed in range(40):
                out = _gen(chord, key_center, level, "normal", seed)
                relationship = out["pentatonic_relationship"]
                _p, _k, scale_notes, _l = resolve_pentatonic_choice(chord, key_center, relationship)
                ordered = [_pc(n) for n in scale_notes]
                fracs.append(_adjacent_step_fraction(out["notes"], ordered))
            return sum(fracs) / len(fracs)

        beginner_frac = avg_fraction("Beginner")
        advanced_frac = avg_fraction("Advanced")
        self.assertLess(advanced_frac, beginner_frac)

    def test_intermediate_and_advanced_show_repeated_or_sequenced_cells(self) -> None:
        """Repetition/sequencing must actually be present across a seed
        sweep - not banned by an "avoid repetition" heuristic."""
        chord, key_center = "Dm7", "C"
        for level in ("Intermediate", "Advanced"):
            seen = 0
            for seed in range(40):
                out = _gen(chord, key_center, level, "normal", seed)
                relationship = out["pentatonic_relationship"]
                _p, _k, scale_notes, _l = resolve_pentatonic_choice(chord, key_center, relationship)
                ordered = [_pc(n) for n in scale_notes]
                if _has_repeated_or_sequenced_cell(out["notes"], ordered):
                    seen += 1
            self.assertGreater(seen, 10, f"{level}: too little repeated/sequenced-cell evidence ({seen}/40)")

    def test_harder_is_not_merely_more_notes(self) -> None:
        """Harder must differ structurally (wider shapes / more register
        displacement / richer modes), not just by being a longer scale run -
        a long run would still show a HIGH adjacent-step fraction."""
        chord, key_center = "Cmaj7", "C"
        fracs = []
        for seed in range(40):
            out = _gen(chord, key_center, "Advanced", "harder", seed)
            relationship = out["pentatonic_relationship"]
            _p, _k, scale_notes, _l = resolve_pentatonic_choice(chord, key_center, relationship)
            ordered = [_pc(n) for n in scale_notes]
            fracs.append(_adjacent_step_fraction(out["notes"], ordered))
        self.assertLess(sum(fracs) / len(fracs), 0.5, "Advanced Harder reads as a scale run, not a motif")

    def test_rhythm_restrained_below_intermediate_harder(self) -> None:
        """Beginner and Intermediate Easier/Normal must show NO syncopated
        family - pitch/motif sophistication, not rhythm, does the work there."""
        chord, key_center = "Cmaj7", "C"
        for level, tier in (
            ("Beginner", "easier"), ("Beginner", "normal"), ("Beginner", "harder"),
            ("Intermediate", "easier"), ("Intermediate", "normal"),
        ):
            for seed in range(8):
                out = _gen(chord, key_center, level, tier, seed)
                families = set(out.get("rhythm_meta", {}).get("families") or [])
                self.assertNotIn("syncopated", families, f"{level}/{tier} seed={seed}: {families!r}")

    def test_rhythm_opens_up_from_intermediate_harder(self) -> None:
        chord, key_center = "Cmaj7", "C"
        for level, tier in (("Intermediate", "harder"), ("Advanced", "normal"), ("Advanced", "harder")):
            saw_syncopated = False
            for seed in range(15):
                out = _gen(chord, key_center, level, tier, seed)
                families = set(out.get("rhythm_meta", {}).get("families") or [])
                if "syncopated" in families:
                    saw_syncopated = True
                    break
            self.assertTrue(saw_syncopated, f"{level}/{tier}: syncopation never appeared in 15 seeds")


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
