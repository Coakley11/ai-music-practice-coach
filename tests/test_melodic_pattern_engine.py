"""Melodic pattern vocabulary: musical correctness, portability, determinism, pipeline safety."""

from __future__ import annotations

import unittest

from melodic_pattern_engine import (
    DIFFICULTIES,
    PATTERN_FAMILIES,
    PatternResult,
    _realize_cell,
    build_context,
    eligible_families,
    family_supports,
    generate_auto_pattern,
    generate_pattern,
    get_family,
    list_families,
    validate_pattern,
)
from music_theory import NOTE_TO_MIDI, pitch_class_from_spelled_note

# Key, a dominant 7th that is V7 of that key, and a diatonic ii/iv chord.
KEYS: list[tuple[str, str, str]] = [
    ("C", "G7", "Dm7"),
    ("Bm", "F#7", "Em7"),
    ("Dm", "A7", "Gm7"),
    ("Db", "Ab7", "Ebm7"),  # accidental-heavy flat key
    ("F#", "C#7", "G#m7"),  # accidental-heavy sharp key (E# must stay pipeline-safe)
    ("Ebm", "Bb7", "Abm7"),
]


def _all_notes(r: PatternResult):
    return [n for cell in r.cells for n in cell]


def _scale_index(ctx, midi: int) -> int:
    """Absolute ladder position of ``midi`` on the chord-scale (octave-aware)."""
    pcs = sorted(ctx.scale_pcs)
    octave, pc = divmod(midi, 12)
    return octave * len(pcs) + pcs.index(pc)


def _assert_valid(tc: unittest.TestCase, r: PatternResult) -> None:
    tc.assertEqual(validate_pattern(r), [], f"{r.family.id} {r.context.key}/{r.context.chord}: {r.display()}")


class TestHarmonicContext(unittest.TestCase):
    def test_key_scales(self) -> None:
        self.assertEqual(build_context("C").scale_names, ("C", "D", "E", "F", "G", "A", "B"))
        self.assertEqual(build_context("Bm").key_names, ("B", "C#", "D", "E", "F#", "G", "A"))
        self.assertEqual(build_context("Dm").key_names, ("D", "E", "F", "G", "A", "Bb", "C"))

    def test_default_chord_is_tonic_seventh(self) -> None:
        self.assertEqual(build_context("Eb").chord, "Ebmaj7")
        self.assertEqual(build_context("Bm").chord, "Bm7")

    def test_secondary_and_minor_dominants_alter_the_key_scale(self) -> None:
        # V7 in minor → leading tone replaces the subtonic (harmonic-minor colour).
        cm_g7 = build_context("Cm", "G7")
        self.assertIn(11, cm_g7.scale_pcs)
        self.assertNotIn(10, cm_g7.scale_pcs)
        # V7/V in C major → F# replaces F.
        c_d7 = build_context("C", "D7")
        self.assertIn(6, c_d7.scale_pcs)
        self.assertNotIn(5, c_d7.scale_pcs)

    def test_non_diatonic_root_uses_quality_mode(self) -> None:
        ctx = build_context("C", "Bb7")  # Bb mixolydian
        self.assertEqual(set(ctx.scale_pcs), {10, 0, 2, 3, 5, 7, 8})

    def test_every_spelling_is_pipeline_safe(self) -> None:
        for key, dom, other in KEYS:
            for chord in (None, dom, other):
                ctx = build_context(key, chord)
                for name in ctx.scale_names + ctx.chord_names + ctx.key_names:
                    self.assertIn(name, NOTE_TO_MIDI, (key, chord, name))


class TestRegistry(unittest.TestCase):
    def test_categories_and_difficulties_covered(self) -> None:
        cats = {f.category for f in PATTERN_FAMILIES.values()}
        for required in (
            "scalar", "interval", "chord_tone", "chromatic_approach",
            "enclosure", "arpeggio_scale", "bebop",
        ):
            self.assertIn(required, cats)
        for level in DIFFICULTIES:
            self.assertTrue(list_families(difficulty=level), level)

    def test_beginner_families_are_diatonic(self) -> None:
        for fam in list_families(difficulty="Beginner"):
            self.assertEqual(fam.chromatic, "none", fam.id)

    def test_ornament_tokens_name_a_real_target(self) -> None:
        for fam in PATTERN_FAMILIES.values():
            for i, tok in enumerate(fam.cell + fam.cell_desc):
                if tok[0] in ("N", "D", "P"):
                    self.assertLess(tok[1], len(fam.cell), fam.id)
                    self.assertNotEqual(tok[1], i % max(1, len(fam.cell)), fam.id)


class TestScalar(unittest.TestCase):
    def test_scale_1234_degrees_and_sequence_ascending(self) -> None:
        r = generate_pattern("scale_1234", key="C", length=4)
        ctx = r.context
        prev_start = None
        for cell in r.cells:
            idx = [_scale_index(ctx, n.midi) for n in cell]
            first = idx[0]
            self.assertEqual([i - first for i in idx], [0, 1, 2, 3])
            if prev_start is not None:
                self.assertEqual(first - prev_start, 1, "cells step up one scale degree")
            prev_start = first

    def test_scale_1234_descending_mirrors(self) -> None:
        r = generate_pattern("scale_1234", key="C", direction="descending", length=4)
        ctx = r.context
        starts = []
        for cell in r.cells:
            idx = [_scale_index(ctx, n.midi) for n in cell]
            self.assertEqual([i - idx[0] for i in idx], [0, -1, -2, -3])
            starts.append(idx[0])
        self.assertEqual([b - a for a, b in zip(starts, starts[1:])], [-1, -1, -1])

    def test_scale_1235_in_every_key(self) -> None:
        for key, _dom, _other in KEYS:
            r = generate_pattern("scale_1235", key=key, length=4)
            _assert_valid(self, r)
            for cell in r.cells:
                idx = [_scale_index(r.context, n.midi) for n in cell]
                self.assertEqual([i - idx[0] for i in idx], [0, 1, 2, 4], key)
                self.assertFalse(any(n.chromatic for n in cell), key)


class TestPermutations(unittest.TestCase):
    CONTOURS = {
        "perm_1324": [0, 2, 1, 3],
        "perm_1425": [0, 3, 1, 4],
        "perm_1526": [0, 4, 1, 5],
        "step_skip_1243": [0, 1, 3, 2],
        "thirds_pairs": [0, 2],
        "fourths_pairs": [0, 3],
    }

    def test_contours_preserved_both_directions(self) -> None:
        for fid, contour in self.CONTOURS.items():
            for key, _dom, _other in KEYS:
                for direction, sgn in (("ascending", 1), ("descending", -1)):
                    r = generate_pattern(fid, key=key, direction=direction, length=4)
                    _assert_valid(self, r)
                    for cell in r.cells:
                        idx = [_scale_index(r.context, n.midi) for n in cell]
                        self.assertEqual(
                            [i - idx[0] for i in idx],
                            [sgn * c for c in contour],
                            (fid, key, direction),
                        )


class TestChordTargeting(unittest.TestCase):
    def test_scale_into_chord_tone_lands_on_each_chord_tone(self) -> None:
        for key, dom, other in KEYS:
            for chord in (dom, other):
                r = generate_pattern("scale_into_chord_tone", key=key, chord=chord, length=4)
                _assert_valid(self, r)
                ctx = r.context
                landed = set()
                for cell in r.cells:
                    target = cell[3]
                    self.assertIn(target.midi % 12, ctx.chord_pcs, (key, chord))
                    self.assertEqual(target.function, "chord_tone")
                    landed.add(target.chord_role)
                self.assertGreaterEqual(len(landed), 3, (key, chord, landed))

    def test_guide_tone_targets_are_third_and_seventh(self) -> None:
        for key, dom, other in KEYS:
            for chord in (dom, other):
                r = generate_pattern("guide_tone_leap", key=key, chord=chord, length=4)
                _assert_valid(self, r)
                for cell in r.cells:
                    self.assertIn(cell[2].midi % 12, r.context.guide_pcs)
                    self.assertIn(cell[3].midi % 12, r.context.guide_pcs)
                    self.assertNotEqual(cell[2].midi % 12, cell[3].midi % 12)

    def test_consecutive_seeds_target_root_third_fifth_and_seventh(self) -> None:
        for key, dom, _other in KEYS:
            roles = {
                generate_pattern("scale_into_chord_tone", key=key, chord=dom, length=1, seed=s).cells[0][3].chord_role
                for s in range(4)
            }
            self.assertEqual(roles, {"R", "3", "5", "7"}, key)


class TestChromaticApproach(unittest.TestCase):
    FAMILIES = (
        ("lower_approach_arpeggio", -1),
        ("upper_approach_cell", +1),
        ("double_approach_below", -1),
        ("double_approach_above", +1),
    )

    def test_approach_resolves_by_half_step_to_its_target(self) -> None:
        for fid, side in self.FAMILIES:
            fam = get_family(fid)
            for key, dom, other in KEYS:
                for chord in (dom, other):
                    try:
                        r = generate_pattern(fid, key=key, chord=chord, length=4)
                    except ValueError:
                        continue
                    _assert_valid(self, r)
                    for cell in r.cells:
                        t = fam.target_index
                        target = cell[t]
                        self.assertTrue(target.chord_role, (fid, key, chord))
                        last = cell[t - 1]
                        self.assertEqual(last.target, t)
                        self.assertEqual(last.midi - target.midi, side, (fid, key, chord))

    def test_required_families_produce_genuine_chromaticism(self) -> None:
        for fam in PATTERN_FAMILIES.values():
            if fam.chromatic != "required":
                continue
            ctx_ok = False
            for key, dom, _other in KEYS:
                try:
                    r = generate_pattern(fam, key=key, chord=dom, length=4)
                except ValueError:
                    continue
                ctx_ok = True
                chrom = [n for n in _all_notes(r) if n.chromatic]
                self.assertTrue(chrom, (fam.id, key))
            self.assertTrue(ctx_ok, f"{fam.id} realizable in at least one key")

    def test_every_chromatic_note_has_a_target_that_follows(self) -> None:
        for fam in PATTERN_FAMILIES.values():
            if fam.sequence == "real":
                continue
            for key, dom, other in KEYS:
                try:
                    r = generate_pattern(fam, key=key, chord=dom, length=4)
                except ValueError:
                    continue
                for cell in r.cells:
                    for i, n in enumerate(cell):
                        if n.chromatic:
                            self.assertIsNotNone(n.target, (fam.id, key, r.display()))
                            self.assertGreater(n.target, i)
                            self.assertLessEqual(abs(n.midi - cell[n.target].midi), 2)

    def test_chromatic_run_is_a_half_step_chain(self) -> None:
        for direction, sgn in (("ascending", 1), ("descending", -1)):
            r = generate_pattern("chromatic_run_to_target", key="C", chord="G7", direction=direction, length=4)
            _assert_valid(self, r)
            for cell in r.cells:
                steps = [b.midi - a.midi for a, b in zip(cell, cell[1:])]
                self.assertEqual(steps, [sgn, sgn, sgn], direction)
                self.assertTrue(cell[3].chord_role)

    def test_known_example_g7_lower_approach(self) -> None:
        ctx = build_context("C", "G7")
        cell = _realize_cell(get_family("lower_approach_arpeggio"), ctx, 67, 1)
        self.assertEqual([n.name for n in cell], ["G", "B", "C#", "D"])
        self.assertEqual([n.midi for n in cell], [67, 71, 73, 74])


class TestEnclosure(unittest.TestCase):
    def test_enclosures_surround_and_resolve(self) -> None:
        for fam in list_families(category="enclosure"):
            for key, dom, other in KEYS:
                for chord in (dom, other):
                    try:
                        r = generate_pattern(fam, key=key, chord=chord, length=4)
                    except ValueError:
                        continue
                    _assert_valid(self, r)
                    t = fam.target_index
                    for cell in r.cells:
                        target = cell[t]
                        self.assertTrue(target.chord_role, (fam.id, key, chord))
                        orn = [n.midi for n in cell if n.target == t]
                        self.assertTrue(any(m > target.midi for m in orn), (fam.id, key, r.display()))
                        self.assertTrue(any(m < target.midi for m in orn), (fam.id, key, r.display()))
                        self.assertLessEqual(abs(cell[t - 1].midi - target.midi), 2)

    def test_known_example_classic_enclosure_of_e(self) -> None:
        ctx = build_context("C")
        cell = _realize_cell(get_family("enclosure_classic"), ctx, 64, 1)
        self.assertEqual([n.name for n in cell], ["F", "D#", "E", "G"])


class TestBebop(unittest.TestCase):
    def test_bebop_run_places_frame_tones_on_the_beat(self) -> None:
        for key, dom, other in KEYS:
            for chord in (dom, other, None):
                for direction in ("ascending", "descending"):
                    r = generate_pattern("bebop_scale_run", key=key, chord=chord, direction=direction, length=2)
                    _assert_valid(self, r)
                    frame = set(r.context.bebop_frame_pcs)
                    for cell in r.cells:
                        for i in range(0, len(cell), 2):
                            self.assertIn(cell[i].midi % 12, frame, (key, chord, direction, r.display()))

    def test_passing_tones_are_chromatic_between_neighbours(self) -> None:
        for fid in ("bebop_scale_run", "bebop_run_to_enclosure", "bebop_passing_descent"):
            for key, dom, _other in KEYS:
                try:
                    r = generate_pattern(fid, key=key, chord=dom, direction="descending", length=4)
                except ValueError:
                    continue
                for cell in r.cells:
                    for i, n in enumerate(cell):
                        if n.function != "passing":
                            continue
                        self.assertTrue(n.chromatic, (fid, key))
                        prev, nxt = cell[i - 1].midi, cell[n.target].midi
                        self.assertEqual(n.target, i + 1)
                        self.assertTrue(min(prev, nxt) < n.midi < max(prev, nxt), (fid, key))
                        self.assertEqual(abs(n.midi - nxt), 1)

    def test_known_dominant_bebop_descent(self) -> None:
        ctx = build_context("C", "G7")
        cell = _realize_cell(get_family("bebop_scale_run"), ctx, 79, -1)
        self.assertEqual([n.name for n in cell], ["G", "F#", "F", "E", "D", "C", "B", "A"])

    def test_bebop_is_structured_not_random_chromaticism(self) -> None:
        for fid in ("bebop_scale_run", "bebop_run_to_enclosure", "bebop_passing_descent"):
            r = generate_pattern(fid, key="C", chord="G7", direction="descending", length=4)
            for cell in r.cells:
                chrom = [n for n in cell if n.chromatic]
                structural = [n for n in cell if n.function == "chord_tone"]
                self.assertLessEqual(len(chrom), len(cell) // 2, fid)
                self.assertGreaterEqual(len(structural), 2, fid)
                self.assertTrue(all(n.target is not None for n in chrom), fid)

    def test_run_to_enclosure_ends_enclosing_a_chord_tone(self) -> None:
        for key, dom, _other in KEYS:
            r = generate_pattern("bebop_run_to_enclosure", key=key, chord=dom, direction="descending", length=2)
            for cell in r.cells:
                target = cell[-1]
                self.assertTrue(target.chord_role, key)
                pair = [cell[-3].midi, cell[-2].midi]
                self.assertTrue(min(pair) < target.midi < max(pair), (key, r.display()))


class TestKeyPortability(unittest.TestCase):
    def test_every_family_valid_across_keys_directions_and_lengths(self) -> None:
        realized = {f.id: 0 for f in PATTERN_FAMILIES.values()}
        for fam in PATTERN_FAMILIES.values():
            for key, dom, other in KEYS:
                for chord in (None, dom, other):
                    ctx = build_context(key, chord)
                    for direction in ("ascending", "descending"):
                        if not family_supports(fam, ctx, direction):
                            continue
                        for length in (8, 16):
                            try:
                                r = generate_pattern(fam, key=key, chord=chord, direction=direction, length=length)
                            except ValueError:
                                continue
                            _assert_valid(self, r)
                            self.assertEqual(len(r.cells), length)
                            realized[fam.id] += 1
        self.assertEqual([fid for fid, n in realized.items() if n == 0], [])

    def test_minor_v7_passing_descent_is_declined_not_faked(self) -> None:
        # Harmonic minor leaves no room for a chromatic passing tone below either guide tone.
        with self.assertRaises(ValueError):
            generate_pattern("bebop_passing_descent", key="Cm", chord="G7")


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_pattern(self) -> None:
        for fid in ("enclosure_classic", "bebop_run_to_enclosure", "perm_1425"):
            a = generate_pattern(fid, key="Bm", chord="F#7", seed=7)
            b = generate_pattern(fid, key="Bm", chord="F#7", seed=7)
            self.assertEqual((a.notes, a.midi), (b.notes, b.midi))
        a = generate_auto_pattern(key="Dm", chord="A7", difficulty="Advanced", seed=11)
        b = generate_auto_pattern(key="Dm", chord="A7", difficulty="Advanced", seed=11)
        self.assertEqual((a.family.id, a.notes, a.midi), (b.family.id, b.notes, b.midi))

    def test_different_seeds_vary_and_stay_valid(self) -> None:
        outs = set()
        fams = set()
        for seed in range(24):
            r = generate_auto_pattern(key="C", chord="G7", difficulty="Advanced", length=8, seed=seed)
            _assert_valid(self, r)
            outs.add(tuple(r.midi))
            fams.add(r.family.id)
        self.assertGreaterEqual(len(outs), 6)
        self.assertGreaterEqual(len(fams), 5)

    def test_start_role_varies_with_seed(self) -> None:
        starts = {generate_pattern("enclosure_classic", key="C", chord="G7", seed=s).cells[0][2].chord_role for s in range(10)}
        self.assertGreaterEqual(len(starts), 2)


class TestAutoMusical(unittest.TestCase):
    def test_beginner_auto_is_diatonic_and_beginner(self) -> None:
        for seed in range(15):
            r = generate_auto_pattern(key="Bm", difficulty="Beginner", seed=seed)
            self.assertEqual(r.family.difficulty, "Beginner")
            self.assertFalse(any(n.chromatic for n in _all_notes(r)), r.display())

    def test_chromatic_none_excludes_chromatic_vocabulary(self) -> None:
        for seed in range(15):
            r = generate_auto_pattern(key="C", chord="G7", difficulty="Advanced", chromatic="none", seed=seed)
            self.assertFalse(any(n.chromatic for n in _all_notes(r)), r.display())

    def test_advanced_auto_mixes_diatonic_and_chromatic(self) -> None:
        kinds = set()
        for seed in range(30):
            r = generate_auto_pattern(key="C", chord="G7", difficulty="Advanced", seed=seed)
            kinds.add(r.family.chromatic != "none")
        self.assertEqual(kinds, {True, False})

    def test_eligibility_respects_quality_requirements(self) -> None:
        ids = {f.id for f, _w in eligible_families(key="C", chord="C", difficulty="Advanced")}
        self.assertNotIn("guide_tone_leap", ids)  # triad has no 7th
        ids7 = {f.id for f, _w in eligible_families(key="C", chord="G7", difficulty="Advanced")}
        self.assertIn("guide_tone_leap", ids7)


# --------------------------------------------------------------------------- pipeline

def _pipeline_motif(r: PatternResult) -> dict:
    motif = r.to_motif_fields()
    motif["rhythm_symbols"] = ["♪"] * len(motif["notes"])
    motif["rhythm_key"] = "measure-cell"
    motif["meter"] = "4/4"
    return motif


def _pipeline_samples() -> list[PatternResult]:
    return [
        generate_pattern("scale_1235", key="C", length=8),
        generate_pattern("perm_1425", key="Bm", direction="descending", length=8),
        generate_pattern("lower_approach_arpeggio", key="C", chord="G7", length=8),
        generate_pattern("enclosure_classic", key="Dm", chord="Dm7", length=8),
        generate_pattern("bebop_run_to_enclosure", key="Eb", chord="Bb7", direction="descending", length=4),
        generate_pattern("chromatic_sequence_1235", key="F#", length=8),
        generate_pattern("arpeggio_up_scale_down", key="Db", length=8),
    ]


class TestPipelineSafety(unittest.TestCase):
    def test_sync_motif_midi_preserves_planned_register(self) -> None:
        from improvisation_motif import _shift_phrase_into_bounds, sync_motif_midi

        for r in _pipeline_samples():
            motif = _pipeline_motif(r)
            synced = sync_motif_midi(dict(motif))
            self.assertEqual(synced["midi"], r.midi, r.family.id)
            self.assertEqual(synced["notes"], r.notes, r.family.id)
            self.assertEqual(_shift_phrase_into_bounds(list(r.midi)), r.midi, r.family.id)

    def test_pitch_classes_match_names(self) -> None:
        for r in _pipeline_samples():
            for n in _all_notes(r):
                self.assertEqual(pitch_class_from_spelled_note(n.name), n.midi % 12)

    def test_no_octave_jumps(self) -> None:
        for r in _pipeline_samples():
            leaps = [abs(b - a) for a, b in zip(r.midi, r.midi[1:])]
            self.assertLessEqual(max(leaps), 12, (r.family.id, r.display()))

    def test_abc_measures_and_sounding_pitches(self) -> None:
        from improvisation_motif import abc_body_measures, abc_measure_beats, build_motif_abc
        from tests.abc_pitch_decoder import decode_abc_midis

        for r in _pipeline_samples():
            abc = build_motif_abc(_pipeline_motif(r), key_center=r.context.key)
            measures = abc_body_measures(abc)
            for m in measures[:-1]:
                self.assertAlmostEqual(abc_measure_beats(m), 4.0, msg=(r.family.id, m))
            self.assertEqual(decode_abc_midis(abc), r.midi, (r.family.id, abc))

    def test_guitar_tab_exact_pitch(self) -> None:
        from improvisation_motif import (
            build_motif_guitar_tab,
            midi_from_guitar_position,
            motif_guitar_tab_midis,
            motif_guitar_tab_placements,
        )

        for r in _pipeline_samples():
            motif = _pipeline_motif(r)
            self.assertEqual(motif_guitar_tab_midis(motif), r.midi, r.family.id)
            placements = motif_guitar_tab_placements(motif)
            self.assertEqual([midi_from_guitar_position(si, fr) for si, fr in placements], r.midi)
            self.assertNotIn("unavailable", build_motif_guitar_tab(motif))


class TestNotationRegressions(unittest.TestCase):
    """``build_motif_abc`` defects surfaced by chromatic vocabulary in C1, fixed in C1.5."""

    def test_below_middle_c_uses_standard_abc_octave_marks(self) -> None:
        from improvisation_motif import _note_name_to_abc_pitch

        self.assertEqual(_note_name_to_abc_pitch("A", octave=3), "A,")

    def test_natural_against_key_signature_gets_natural_sign(self) -> None:
        from improvisation_motif import build_motif_abc

        # F major: approach to C from below is B natural; K:F would otherwise render Bb.
        r = generate_pattern("lower_approach_arpeggio", key="F", length=1, seed=0)
        cell = r.cells[0]
        assert any(n.name == "B" for n in cell), r.display()
        abc = build_motif_abc(_pipeline_motif(r), key_center="F")
        self.assertIn("=B", abc)


if __name__ == "__main__":
    unittest.main()
