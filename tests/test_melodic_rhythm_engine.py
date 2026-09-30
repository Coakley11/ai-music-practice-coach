"""Reusable melodic rhythm engine (Slice C3): meters, sizes, levels, targets, Change Rhythm, notation."""

from __future__ import annotations

import json
import unittest
from fractions import Fraction

from melodic_rhythm_engine import (
    FIGURES_BY_ID,
    LEVELS,
    next_rhythm,
    parse_meter,
    rhythm_candidates,
    validate_realization,
)
from tests.abc_pitch_decoder import abc_bar_totals, decode_abc_events, decode_abc_midis

METERS = ("4/4", "3/4", "6/8")
SIZES = (2, 3, 4, 5, 6, 8, 12, 16)
_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}
ADVANCED_ONLY = {f.id for f in FIGURES_BY_ID.values() if f.level == "Advanced"}


def _figure_ids(r) -> list[str]:
    return [f for bar in r.id.split(":", 2)[2].split("/") for f in bar.rstrip("~").split("+")]


class TestMeter(unittest.TestCase):
    def test_bar_lengths_and_pulses(self) -> None:
        self.assertEqual(parse_meter("4/4").bar, 4)
        self.assertEqual(parse_meter("3/4").bar, 3)
        m68 = parse_meter("6/8")
        self.assertEqual(m68.bar, 3)
        self.assertTrue(m68.compound)
        self.assertEqual(m68.beat, Fraction(3, 2))

    def test_metric_strength_hierarchy(self) -> None:
        m = parse_meter("4/4")
        s = m.strength
        self.assertGreater(s(Fraction(0)), s(Fraction(2)))
        self.assertGreater(s(Fraction(2)), s(Fraction(1)))
        self.assertEqual(s(Fraction(1)), s(Fraction(3)))
        self.assertGreater(s(Fraction(3)), s(Fraction(1, 2)))
        self.assertGreater(s(Fraction(1, 2)), s(Fraction(1, 4)))
        m3 = parse_meter("3/4")
        self.assertGreater(m3.strength(Fraction(0)), m3.strength(Fraction(1)))
        self.assertEqual(m3.strength(Fraction(1)), m3.strength(Fraction(2)))
        c = parse_meter("6/8")
        # Two dotted-quarter pulses: eighth position 4 (= 3/2 quarters) is the second strong beat.
        self.assertGreater(c.strength(Fraction(0)), c.strength(Fraction(3, 2)))
        self.assertGreater(c.strength(Fraction(3, 2)), c.strength(Fraction(1, 2)))
        self.assertGreater(c.strength(Fraction(3, 2)), c.strength(Fraction(1)))


class TestCandidatesAreValid(unittest.TestCase):
    def test_every_meter_size_and_level(self) -> None:
        for meter in METERS:
            bar = parse_meter(meter).bar
            for level in LEVELS:
                for n in SIZES:
                    for group in (None,) + ((n // 4,) if n in (12, 16) else ()):
                        cands = rhythm_candidates(n, meter=meter, level=level, group_size=group)
                        self.assertTrue(cands, (meter, level, n, group))
                        for r in cands:
                            self.assertEqual(validate_realization(r, n), [], (meter, level, n, group, r.id))
                            self.assertEqual(len(r.note_events), n)
                            self.assertEqual(r.total, bar * r.bars)

    def test_compound_meter_uses_compound_figures_only(self) -> None:
        for level in LEVELS:
            for n in (2, 3, 4, 5, 6, 8):
                for r in rhythm_candidates(n, meter="6/8", level=level):
                    ids = _figure_ids(r)
                    self.assertTrue(all(f.startswith("c_") for f in ids), (level, n, r.id))
                    # Each figure fills a dotted-quarter pulse (or the whole bar).
                    for f in ids:
                        self.assertIn(FIGURES_BY_ID[f].span, (Fraction(3, 2), Fraction(3)), f)

    def test_simple_meters_never_use_compound_figures(self) -> None:
        for meter in ("4/4", "3/4"):
            for r in rhythm_candidates(6, meter=meter, level="Advanced"):
                self.assertFalse(any(f.startswith("c_") for f in _figure_ids(r)), r.id)

    def test_twelve_and_sixteen_notes_span_bars_without_truncation(self) -> None:
        for meter in METERS:
            for level in LEVELS:
                for n in (12, 16):
                    r = rhythm_candidates(n, meter=meter, level=level)[0]
                    self.assertGreaterEqual(r.bars, 2, (meter, level, n))
                    self.assertEqual([e.note for e in r.note_events], list(range(n)))


class TestDifficulty(unittest.TestCase):
    def test_beginner_is_plain(self) -> None:
        for meter in METERS:
            for n in (2, 3, 4, 5, 6, 8, 12):
                for r in rhythm_candidates(n, meter=meter, level="Beginner"):
                    self.assertEqual(r.level, "Beginner", r.id)
                    self.assertTrue(set(r.families) <= {"straight", "compound"}, (r.id, r.families))
                    self.assertFalse(any(e.tuplet or e.rest for e in r.events), r.id)
                    self.assertTrue(all(e.duration >= Fraction(1, 2) for e in r.events), r.id)

    def test_intermediate_reaches_moderate_rhythms_only(self) -> None:
        fams: set[str] = set()
        for meter in METERS:
            for n in (3, 4, 5, 6):
                for r in rhythm_candidates(n, meter=meter, level="Intermediate"):
                    self.assertLessEqual(_RANK[r.level], 1, r.id)
                    self.assertFalse(ADVANCED_ONLY & set(_figure_ids(r)), r.id)
                    self.assertFalse(r.id.endswith("~") or "~/" in r.id, r.id)  # no displacement
                    fams |= set(r.families)
        self.assertTrue({"dotted", "syncopated", "triplet", "rest"} <= fams, fams)

    def test_advanced_is_richer_but_keeps_simpler_choices(self) -> None:
        levels: set[str] = set()
        advanced_figs: set[str] = set()
        for meter in METERS:
            for n in (3, 4, 5, 6):
                for r in rhythm_candidates(n, meter=meter, level="Advanced"):
                    levels.add(r.level)
                    advanced_figs |= ADVANCED_ONLY & set(_figure_ids(r))
        self.assertIn("Advanced", levels)
        self.assertTrue(levels & {"Beginner", "Intermediate"}, levels)
        self.assertTrue({"de_s", "trip_q", "c_duplet"} & advanced_figs, advanced_figs)

    def test_not_every_advanced_top_choice_is_advanced(self) -> None:
        tops = [rhythm_candidates(n, meter=m, level="Advanced")[0].level for m in METERS for n in (2, 3, 4, 5, 6, 8)]
        self.assertTrue(any(lvl != "Advanced" for lvl in tops), tops)


class TestDeterminismAndCycling(unittest.TestCase):
    def test_same_inputs_same_candidates(self) -> None:
        roles = ["chord_tone", "scale", "approach", "target", "chord_tone"]
        a = [r.id for r in rhythm_candidates(5, meter="4/4", level="Intermediate", roles=roles, seed=3)]
        b = [r.id for r in rhythm_candidates(5, meter="4/4", level="Intermediate", roles=roles, seed=3)]
        self.assertEqual(a, b)

    def test_next_rhythm_visits_every_candidate_then_wraps(self) -> None:
        for meter, n, level in (("4/4", 4, "Intermediate"), ("6/8", 6, "Advanced"), ("3/4", 5, "Beginner")):
            cands = rhythm_candidates(n, meter=meter, level=level)
            current = cands[0].id
            seen = [current]
            for _ in range(len(cands)):
                _i, r = next_rhythm(current, n, meter=meter, level=level)
                self.assertNotEqual(r.id, current)
                current = r.id
                seen.append(current)
            self.assertEqual(seen[-1], seen[0], (meter, n, level))  # deterministic wraparound
            self.assertEqual(len(set(seen[:-1])), len(cands))

    def test_candidates_are_distinct_rhythms(self) -> None:
        for meter in METERS:
            cands = rhythm_candidates(6, meter=meter, level="Advanced")
            sigs = [tuple((e.duration, e.rest, e.tuplet) for e in r.events) for r in cands]
            self.assertEqual(len(sigs), len(set(sigs)), meter)


class TestStrongBeatTargets(unittest.TestCase):
    CASES = {
        "chromatic run": ["approach", "approach", "approach", "target"],
        "enclosure": ["neighbor", "approach", "target", "chord_tone"],
        "lower approach": ["chord_tone", "chord_tone", "approach", "target"],
        "upper approach": ["chord_tone", "approach", "target", "chord_tone"],
        "double approach": ["approach", "approach", "target", "chord_tone"],
    }

    def test_target_lands_on_the_strongest_available_position(self) -> None:
        for meter in METERS:
            m = parse_meter(meter)
            for name, roles in self.CASES.items():
                ti = roles.index("target")
                for level in LEVELS:
                    cands = rhythm_candidates(4, meter=meter, level=level, roles=roles)
                    strengths = [m.strength(r.note_events[ti].onset % m.bar) for r in cands]
                    self.assertEqual(strengths[0], max(strengths), (meter, level, name, cands[0].id))

    def test_guide_tones_prefer_strong_beats(self) -> None:
        roles = ["scale", "scale", "guide_tone", "guide_tone"]
        for meter in METERS:
            m = parse_meter(meter)
            for level in LEVELS:
                cands = rhythm_candidates(4, meter=meter, level=level, roles=roles)

                def best_guide(r) -> float:
                    return max(m.strength(r.note_events[i].onset % m.bar) for i in (2, 3))

                self.assertEqual(best_guide(cands[0]), max(best_guide(r) for r in cands), (meter, level))

    def test_bebop_line_puts_structure_on_beats_not_passing_tones(self) -> None:
        from improvisation_motif import _pattern_note_roles
        from melodic_pattern_engine import generate_pattern

        m = parse_meter("4/4")
        for chord in ("G7", "Dm7"):
            # Some starting chord tones need no passing tone; use a line that has one.
            roles = next(
                r for r in (
                    _pattern_note_roles(generate_pattern(
                        "bebop_scale_run", key="C", chord=chord, direction="descending", length=1, seed=s,
                    ))
                    for s in range(8)
                ) if "passing" in r
            )
            r = rhythm_candidates(8, meter="4/4", level="Advanced", roles=roles)[0]
            strength = [m.strength(e.onset % m.bar) for e in r.note_events]
            structural = [s for s, role in zip(strength, roles) if role in ("chord_tone", "guide_tone", "target")]
            passing = [s for s, role in zip(strength, roles) if role == "passing"]
            self.assertTrue(passing, roles)
            self.assertGreater(sum(structural) / len(structural), max(passing), (chord, roles, r.id))

    def test_roles_change_the_ranking(self) -> None:
        roles = ["approach", "approach", "approach", "target"]
        with_roles = rhythm_candidates(4, meter="4/4", level="Beginner", roles=roles)[0].id
        without = rhythm_candidates(4, meter="4/4", level="Beginner")[0].id
        self.assertNotEqual(with_roles, without)


# --------------------------------------------------------------------------- Phrase / Motif integration


def _auto(key: str, chord: str, level: str, seed: int, *, meter: str = "4/4", direction: str = "ascending",
          length: int = 8) -> dict:
    from motif_engine import build_phrase_pattern

    return build_phrase_pattern(
        {"chord": chord, "notes": [], "meter": meter}, key_center=key, pattern_type="auto",
        direction=direction, length=length, level=level, pattern_seed=seed,
    )


def _pitch_state(m: dict) -> tuple:
    return (
        list(m["notes"]), list(m["midi"]), [list(c) for c in m["cells"]], m.get("pattern_family"),
        m.get("pattern_family_name"), m.get("pattern_difficulty"), m.get("pattern_seed"),
        m.get("pattern_direction"), m.get("pattern_length"), m.get("chord"), m.get("pattern_chord_context"),
        m.get("pattern_note_roles"), json.dumps(m.get("pattern_source_motif"), sort_keys=True),
    )


CONTEXTS = [("C", "G7"), ("Bm", "F#7"), ("Dm", "A7"), ("Eb", "Bb7"), ("F#", "C#7")]


class TestPhraseMotifRhythm(unittest.TestCase):
    def test_auto_patterns_carry_a_valid_engine_rhythm(self) -> None:
        from improvisation_motif import is_engine_rhythm, motif_rhythm_events

        for meter in METERS:
            bar = parse_meter(meter).bar
            for key, chord in CONTEXTS:
                for seed in (1, 2, 3):
                    p = _auto(key, chord, "Advanced", seed, meter=meter)
                    self.assertTrue(is_engine_rhythm(p), (meter, key, p["pattern_family"]))
                    events = motif_rhythm_events(p)
                    self.assertEqual(len([e for e in events if not e.rest]), len(p["notes"]))
                    self.assertEqual(sum((e.duration for e in events), Fraction(0)) % bar, 0)
                    self.assertEqual(len(p["rhythm_symbols"]), len(p["notes"]))
                    json.dumps(p)  # persistable

    def test_change_rhythm_changes_only_rhythm(self) -> None:
        from improvisation_motif import cycle_motif_rhythm

        for meter in METERS:
            for key, chord in CONTEXTS:
                p = _auto(key, chord, "Advanced", 2, meter=meter)
                before = _pitch_state(p)
                ids = [p["rhythm_meta"]["id"]]
                current = p
                for _ in range(5):
                    current = cycle_motif_rhythm(current)
                    self.assertEqual(_pitch_state(current), before, (meter, key))
                    self.assertEqual(current["last_transform"], "change_rhythm")
                    self.assertNotEqual(current["rhythm_meta"]["id"], ids[-1])
                    ids.append(current["rhythm_meta"]["id"])

    def test_change_rhythm_wraps_deterministically(self) -> None:
        from improvisation_motif import cycle_motif_rhythm

        p = _auto("C", "G7", "Intermediate", 1)
        count = p["rhythm_meta"]["count"]
        current = p
        for _ in range(count):
            current = cycle_motif_rhythm(current)
        self.assertEqual(current["rhythm_meta"]["id"], p["rhythm_meta"]["id"])
        self.assertEqual(current["rhythm_events"], p["rhythm_events"])

    def test_rerun_does_not_advance_rhythm(self) -> None:
        from improvisation_motif import sync_motif_midi

        p = _auto("Bm", "F#7", "Advanced", 4)
        again = sync_motif_midi(dict(p))
        self.assertEqual(again["rhythm_meta"], p["rhythm_meta"])
        self.assertEqual(again["rhythm_events"], p["rhythm_events"])

    def test_direction_and_length_rebuilds_keep_the_rhythm(self) -> None:
        from improvisation_motif import cycle_motif_rhythm
        from motif_engine import rebuild_phrase_pattern

        p = cycle_motif_rhythm(_auto("C", "G7", "Advanced", 3))
        rid = p["rhythm_meta"]["id"]
        d = rebuild_phrase_pattern(p, key_center="C", pattern_type="auto", direction="descending", level="Advanced")
        self.assertEqual(d["rhythm_meta"]["id"], rid)
        self.assertEqual(d["last_transform"], "change_rhythm")
        q = rebuild_phrase_pattern(d, key_center="C", pattern_type="auto", length=12, level="Advanced")
        self.assertEqual(q["rhythm_meta"]["id"], rid)

    def test_pitch_transforms_keep_the_rhythm(self) -> None:
        from motif_engine import transform_motif

        p = _auto("Dm", "A7", "Intermediate", 2)
        for op in ("sequence_up", "sequence_down", "invert"):
            t = transform_motif(p, op, key_center="Dm")
            self.assertEqual(t["rhythm_events"], p["rhythm_events"], op)
            self.assertEqual(len(t["notes"]), len(p["notes"]))

    def test_explicit_pattern_types_keep_legacy_rhythm(self) -> None:
        import random

        from improvisation_motif import is_engine_rhythm
        from motif_engine import build_phrase_pattern, generate_motif_for_chord

        m = generate_motif_for_chord("G7", key_center="C", level="Advanced", rng=random.Random(2))
        m["chord"] = "G7"
        for ptype in ("scalar", "thirds", "fourths", "pentatonic"):
            self.assertFalse(is_engine_rhythm(build_phrase_pattern(m, key_center="C", pattern_type=ptype)))


class TestFiveAndSixNoteFamilies(unittest.TestCase):
    def test_previously_excluded_families_are_now_chosen_and_valid(self) -> None:
        wanted = {"scale_12345": "Beginner", "arpeggio_approach_ninth": "Advanced"}
        found: dict[str, dict] = {}
        for fid, level in wanted.items():
            for key, chord in CONTEXTS + [("C", "C"), ("G", "G")]:
                for seed in range(1, 40):
                    p = _auto(key, chord, level, seed)
                    if p["pattern_family"] == fid:
                        found[fid] = (p, key)
                        break
                if fid in found:
                    break
        self.assertEqual(set(found), set(wanted), found.keys())
        for fid, (p, key) in found.items():
            from motif_engine import build_motif_abc

            abc = build_motif_abc(p, key_center=key)
            self.assertTrue(all(t == 4 for t in abc_bar_totals(abc)), (fid, abc_bar_totals(abc)))
            self.assertEqual(decode_abc_midis(abc), p["midi"], fid)


class TestNotationRoundTrip(unittest.TestCase):
    def _assert_round_trip(self, p: dict, key: str) -> None:
        from improvisation_motif import motif_rhythm_events
        from motif_engine import build_motif_abc

        abc = build_motif_abc(p, key_center=key)
        decoded = decode_abc_events(abc)
        events = motif_rhythm_events(p)
        self.assertEqual([m for m, _d in decoded if m is not None], p["midi"], abc)
        self.assertEqual([d for _m, d in decoded], [e.duration for e in events], abc)
        self.assertEqual([m is None for m, _d in decoded], [e.rest for e in events], abc)
        bar = parse_meter(p["meter"]).bar
        self.assertTrue(all(t == bar for t in abc_bar_totals(abc)), (abc_bar_totals(abc), abc))
        self.assertIn(f"M:{p['meter']}", abc)

    def test_round_trip_across_meters_levels_and_rhythm_changes(self) -> None:
        from improvisation_motif import cycle_motif_rhythm

        saw_tuplet = saw_rest = saw_dotted = False
        for meter in METERS:
            for key, chord in CONTEXTS:
                for level in LEVELS:
                    p = _auto(key, chord, level, 2, meter=meter)
                    for _ in range(4):
                        self._assert_round_trip(p, key)
                        events = p["rhythm_events"]
                        saw_tuplet |= any(e["tup"] for e in events)
                        saw_rest |= any(e["rest"] for e in events)
                        saw_dotted |= any(Fraction(e["w"]).numerator == 3 for e in events)
                        p = cycle_motif_rhythm(p)
        self.assertTrue(saw_tuplet and saw_rest and saw_dotted, (saw_tuplet, saw_rest, saw_dotted))


class TestGuitarTabAfterRhythmChanges(unittest.TestCase):
    def test_tab_pitches_identical(self) -> None:
        from improvisation_motif import cycle_motif_rhythm
        from motif_engine import midi_from_guitar_position, motif_guitar_tab_midis, motif_guitar_tab_placements

        for key, chord in CONTEXTS:
            p = _auto(key, chord, "Advanced", 5)
            first = motif_guitar_tab_placements(p)
            for _ in range(4):
                p = cycle_motif_rhythm(p)
                self.assertEqual(motif_guitar_tab_midis(p), p["midi"])
                placements = motif_guitar_tab_placements(p)
                self.assertEqual(placements, first)
                self.assertEqual([midi_from_guitar_position(s, f) for s, f in placements], p["midi"])


if __name__ == "__main__":
    unittest.main()
