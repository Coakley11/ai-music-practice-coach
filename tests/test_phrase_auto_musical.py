"""Phrase & Motif Auto / Musical draws from the C1 pattern vocabulary (Slice C2)."""

from __future__ import annotations

import json
import random
import unittest
from pathlib import Path

from improvisation_motif import (
    PATTERN_SEED_NONCE_KEY,
    _beats_per_bar,
    _rhythm_symbol_beats,
    cycle_motif_rhythm,
    motif_measure_cells,
)
from melodic_pattern_engine import DIFFICULTIES, PATTERN_FAMILIES, generate_pattern, get_family
from motif_engine import (
    build_motif_abc,
    build_motif_pattern,
    build_phrase_pattern,
    generate_motif_for_chord,
    midi_from_guitar_position,
    motif_guitar_tab_midis,
    motif_guitar_tab_placements,
    next_pattern_seed,
    rebuild_phrase_pattern,
    sync_motif_midi,
)
from tests.abc_pitch_decoder import decode_abc_midis

CONTEXTS = [
    ("C", "C"), ("C", "G7"), ("Bm", "Bm7"), ("Bm", "F#7"), ("Dm", "A7"), ("Dm", "Dm7"),
    ("Eb", "Bb7"), ("F#", "C#7"), ("Ebm", "Bb7"),
]
CHROMATIC_CATEGORIES = {"chromatic_approach", "enclosure", "bebop", "chromatic_sequence"}


def _motif(key: str, chord: str, level: str = "Intermediate") -> dict:
    m = generate_motif_for_chord(chord, key_center=key, level=level, rng=random.Random(2))
    m["chord"] = chord
    return m


def _auto(key: str, chord: str, level: str, seed: int, direction: str = "ascending", length: int = 8) -> dict:
    return build_phrase_pattern(
        _motif(key, chord, level), key_center=key, pattern_type="auto",
        direction=direction, length=length, level=level, pattern_seed=seed,
    )


def _pitch_state(m: dict) -> tuple:
    return (
        list(m["notes"]), list(m["midi"]), [list(c) for c in m["cells"]],
        m.get("pattern_family"), m.get("pattern_seed"), m.get("chord"), m.get("pattern_chord_context"),
    )


class TestAutoUsesVocabulary(unittest.TestCase):
    def test_auto_output_is_a_realized_vocabulary_pattern(self) -> None:
        for key, chord in CONTEXTS:
            for seed in (1, 2, 3):
                p = _auto(key, chord, "Advanced", seed)
                fam = get_family(p["pattern_family"])
                self.assertEqual(p["pattern_type"], "auto")
                self.assertTrue(p["is_pattern"])
                self.assertEqual(p["pattern_family_name"], fam.name)
                self.assertEqual(p["pattern_difficulty"], fam.difficulty)
                again = generate_pattern(
                    fam, key=key, chord=p["pattern_chord_context"], direction="ascending", length=8,
                    seed=p["pattern_seed"],
                )
                self.assertEqual(p["midi"], again.midi, (key, chord, seed))
                self.assertEqual(p["notes"], again.notes)

    def test_motif_shape_matches_existing_pipeline(self) -> None:
        p = _auto("C", "G7", "Intermediate", 4)
        size = get_family(p["pattern_family"]).size
        self.assertEqual(len(p["cells"]), 8)
        self.assertTrue(all(len(c) == size for c in p["cells"]))
        self.assertEqual(p["base_motif_notes"], p["cells"][0])
        self.assertEqual(len(p["rhythm_symbols"]), len(p["notes"]))
        self.assertEqual(sync_motif_midi(dict(p))["midi"], p["midi"])
        json.dumps(p)  # persistable as a workspace artifact

    def test_source_motif_is_kept_and_not_a_pattern(self) -> None:
        m = _motif("C", "G7")
        p = build_phrase_pattern(m, key_center="C", pattern_type="auto", level="Intermediate", pattern_seed=1)
        src = p["pattern_source_motif"]
        self.assertEqual(src["notes"], m["notes"])
        self.assertNotIn("is_pattern", src)

    def test_every_measure_is_full(self) -> None:
        for key, chord in CONTEXTS:
            for seed in range(1, 6):
                p = _auto(key, chord, "Advanced", seed)
                beats = _beats_per_bar(p["meter"])
                for _notes, syms in motif_measure_cells(p):
                    self.assertAlmostEqual(_rhythm_symbol_beats(syms), beats, msg=(key, chord, p["pattern_family"]))


class TestDifficulty(unittest.TestCase):
    def _families(self, level: str) -> list:
        return [
            get_family(_auto(key, chord, level, seed)["pattern_family"])
            for key, chord in CONTEXTS
            for seed in range(1, 9)
        ]

    def test_beginner_is_simple_and_diatonic(self) -> None:
        fams = self._families("Beginner")
        self.assertTrue(all(f.difficulty == "Beginner" for f in fams))
        self.assertTrue(all(f.chromatic == "none" for f in fams))
        for key, chord in CONTEXTS:
            for seed in range(1, 6):
                p = _auto(key, chord, "Beginner", seed)
                fam = get_family(p["pattern_family"])
                self.assertNotIn(fam.category, CHROMATIC_CATEGORIES)

    def test_intermediate_varies_across_categories(self) -> None:
        fams = self._families("Intermediate")
        self.assertTrue(all(f.difficulty in ("Beginner", "Intermediate") for f in fams))
        cats = {f.category for f in fams}
        self.assertGreaterEqual(len(cats), 4, cats)
        self.assertTrue(cats & {"chromatic_approach", "enclosure"}, cats)
        self.assertGreater(sum(f.difficulty == "Intermediate" for f in fams), len(fams) // 2)

    def test_advanced_reaches_chromatic_vocabulary_but_not_always(self) -> None:
        fams = self._families("Advanced")
        cats = {f.category for f in fams}
        self.assertTrue({"bebop", "enclosure", "chromatic_approach"} <= cats, cats)
        self.assertTrue(any(f.chromatic == "none" for f in fams))
        self.assertGreater(sum(f.difficulty == "Advanced" for f in fams), len(fams) // 3)

    def test_difficulty_rises_with_level(self) -> None:
        mean = {
            lvl: sum(DIFFICULTIES.index(f.difficulty) for f in self._families(lvl)) / (len(CONTEXTS) * 8)
            for lvl in DIFFICULTIES
        }
        self.assertLess(mean["Beginner"], mean["Intermediate"])
        self.assertLess(mean["Intermediate"], mean["Advanced"])


class TestFirstIdeaMatchesSelectedLevel(unittest.TestCase):
    """C2.1: a fresh first Auto idea at a level demonstrates that level (seed == 1)."""

    def test_first_idea_is_exactly_the_selected_level(self) -> None:
        for key, chord in CONTEXTS:
            for level in DIFFICULTIES:
                p = _auto(key, chord, level, seed=1)
                fam = get_family(p["pattern_family"])
                self.assertEqual(fam.difficulty, level, (key, chord, level, fam.name))

    def test_reported_regression_g_major_advanced(self) -> None:
        # The exact case that motivated C2.1: first Advanced idea on G was
        # deterministically "Scale turn 1-2-3-2 · Beginner".
        p = _auto("G", "G", "Advanced", seed=1)
        fam = get_family(p["pattern_family"])
        self.assertEqual(fam.difficulty, "Advanced", fam.name)

    def test_first_idea_is_still_deterministic(self) -> None:
        for key, chord in CONTEXTS:
            for level in DIFFICULTIES:
                a = _auto(key, chord, level, seed=1)
                b = _auto(key, chord, level, seed=1)
                self.assertEqual(_pitch_state(a), _pitch_state(b), (key, chord, level))

    def test_only_the_first_idea_is_forced_later_ideas_keep_the_healthy_mix(self) -> None:
        for key, chord in CONTEXTS:
            fams = [get_family(_auto(key, chord, "Advanced", seed)["pattern_family"]) for seed in range(1, 17)]
            self.assertEqual(fams[0].difficulty, "Advanced", (key, chord))
            later = fams[1:]
            difficulties = {f.difficulty for f in later}
            self.assertGreaterEqual(len(difficulties), 2, (key, chord, [f.difficulty for f in later]))
            self.assertFalse(all(f.difficulty == "Advanced" for f in later), (key, chord))
            self.assertTrue(any(f.difficulty == "Advanced" for f in later), (key, chord))

    def test_beginner_first_idea_stays_simple_and_diatonic(self) -> None:
        # Beginner already has no lower level to draw from — confirm forcing didn't
        # change that (or accidentally restrict to a narrower slice of Beginner).
        fams = {get_family(_auto(key, chord, "Beginner", seed=1)["pattern_family"]).name for key, chord in CONTEXTS}
        self.assertGreater(len(fams), 1, fams)

    def test_a_kept_family_direction_or_length_change_is_not_treated_as_first_idea(self) -> None:
        # Rebuilds pass the *kept* family_id, so the seed==1 special case must not
        # fire there even when the original idea happened to be built at seed 1.
        p = _auto("G", "G", "Intermediate", seed=1)
        fam_before = p["pattern_family"]
        d = rebuild_phrase_pattern(p, key_center="G", pattern_type="auto", direction="descending", level="Intermediate")
        self.assertEqual(d["pattern_family"], fam_before)

    def test_session_level_scoped_seed_forces_first_idea_per_level(self) -> None:
        session: dict = {}
        # Simulate: build once at Advanced, switch to Beginner, switch back to Advanced.
        seed_adv1 = next_pattern_seed(session, level="Advanced")
        self.assertEqual(seed_adv1, 1)
        p1 = _auto("G", "G", "Advanced", seed_adv1)
        self.assertEqual(get_family(p1["pattern_family"]).difficulty, "Advanced")

        seed_beg1 = next_pattern_seed(session, level="Beginner")
        self.assertEqual(seed_beg1, 1)  # Beginner's own counter, independently first
        p2 = _auto("G", "G", "Beginner", seed_beg1)
        self.assertEqual(get_family(p2["pattern_family"]).difficulty, "Beginner")

        seed_adv2 = next_pattern_seed(session, level="Advanced")
        self.assertEqual(seed_adv2, 2)  # not first anymore — normal weighted mix applies
        p3 = _auto("G", "G", "Advanced", seed_adv2)
        self.assertEqual(_pitch_state(p3), _pitch_state(_auto("G", "G", "Advanced", 2)))

    def test_next_pattern_seed_without_level_is_unchanged(self) -> None:
        session: dict = {}
        self.assertEqual([next_pattern_seed(session) for _ in range(3)], [1, 2, 3])


class TestDirectionAndLength(unittest.TestCase):
    def test_direction_is_honoured(self) -> None:
        for key, chord in CONTEXTS:
            for seed in range(1, 5):
                for direction, sign in (("ascending", 1), ("descending", -1)):
                    p = _auto(key, chord, "Advanced", seed, direction=direction)
                    self.assertEqual(p["pattern_direction"], direction)
                    c0, c1 = p["cells"][0], p["cells"][1]
                    m0 = sum(p["midi"][: len(c0)]) / len(c0)
                    m1 = sum(p["midi"][len(c0) : len(c0) + len(c1)]) / len(c1)
                    self.assertGreater(sign * (m1 - m0), 0, (key, chord, p["pattern_family"], direction))

    def test_lengths(self) -> None:
        for length in (8, 12, 16):
            for key, chord in CONTEXTS:
                p = _auto(key, chord, "Advanced", 3, length=length)
                size = get_family(p["pattern_family"]).size
                self.assertEqual(p["pattern_length"], length)
                self.assertEqual(len(p["cells"]), length)
                self.assertEqual(len(p["notes"]), length * size)

    def test_direction_change_keeps_family_and_usually_the_opening(self) -> None:
        total = same_start = 0
        for key, chord in CONTEXTS:
            for seed in range(1, 9):
                p = _auto(key, chord, "Advanced", seed)
                d = rebuild_phrase_pattern(p, key_center=key, pattern_type="auto", direction="descending", level="Advanced")
                self.assertEqual(d["pattern_family"], p["pattern_family"], (key, chord))
                self.assertEqual(d["pattern_direction"], "descending")
                total += 1
                # Best effort: some ornament-led cells cannot start the same way descending.
                same_start += d["midi"][0] % 12 == p["midi"][0] % 12
                back = rebuild_phrase_pattern(d, key_center=key, pattern_type="auto", direction="ascending", level="Advanced")
                self.assertEqual(back["pattern_family"], p["pattern_family"])
        # C2.1 forces seed 1 to an exact-Advanced family per context (9 of these 72
        # cases), which skews this sample toward enclosure/chromatic_approach/bebop
        # families more likely to need a different start when direction reverses —
        # family preservation (asserted above) still holds every time.
        self.assertGreaterEqual(same_start / total, 0.70, (same_start, total))

    def test_length_change_keeps_family_and_usually_the_opening(self) -> None:
        total = same_open = 0
        for key, chord in CONTEXTS:
            for seed in range(1, 9):
                p = _auto(key, chord, "Advanced", seed)
                for length in (12, 16, 8):
                    q = rebuild_phrase_pattern(p, key_center=key, pattern_type="auto", length=length, level="Advanced")
                    self.assertEqual(q["pattern_family"], p["pattern_family"], (key, chord, length))
                    self.assertEqual(len(q["cells"]), length)
                    total += 1
                    # A long run may need another start to keep its direction inside the register.
                    same_open += [m % 12 for m in q["base_motif_midi"]] == [m % 12 for m in p["base_motif_midi"]]
                    p = q
        self.assertGreaterEqual(same_open / total, 0.9, (same_open, total))

    def test_apply_without_changes_is_identity(self) -> None:
        p = _auto("Bm", "F#7", "Advanced", 5)
        q = rebuild_phrase_pattern(p, key_center="Bm", pattern_type="auto", level="Advanced")
        self.assertEqual(_pitch_state(q), _pitch_state(p))

    def test_lowering_level_below_family_picks_eligible_family(self) -> None:
        for seed in range(1, 12):
            p = _auto("C", "G7", "Advanced", seed)
            if get_family(p["pattern_family"]).difficulty != "Advanced":
                continue
            q = rebuild_phrase_pattern(p, key_center="C", pattern_type="auto", level="Beginner")
            self.assertEqual(get_family(q["pattern_family"]).difficulty, "Beginner")
            return
        self.fail("no Advanced family chosen in 11 seeds")


class TestSeedAndNewIdeas(unittest.TestCase):
    def test_same_seed_same_pattern(self) -> None:
        for key, chord in CONTEXTS:
            self.assertEqual(_pitch_state(_auto(key, chord, "Advanced", 7)), _pitch_state(_auto(key, chord, "Advanced", 7)))

    def test_new_seeds_give_new_valid_ideas(self) -> None:
        for key, chord in (("C", "G7"), ("Dm", "A7"), ("Eb", "Bb7")):
            outs = {tuple(_auto(key, chord, "Advanced", s)["midi"]) for s in range(1, 9)}
            fams = {_auto(key, chord, "Advanced", s)["pattern_family"] for s in range(1, 9)}
            self.assertGreaterEqual(len(outs), 6, key)
            self.assertGreaterEqual(len(fams), 4, key)

    def test_next_pattern_seed_advances_session_counter(self) -> None:
        session: dict = {}
        self.assertEqual([next_pattern_seed(session) for _ in range(3)], [1, 2, 3])
        self.assertEqual(session[PATTERN_SEED_NONCE_KEY], 3)
        self.assertEqual(next_pattern_seed(None), 0)


class TestChangeRhythmPreservesPitches(unittest.TestCase):
    FAMILIES = ("lower_approach_arpeggio", "enclosure_classic", "enclosure_four_note", "bebop_run_to_enclosure",
                "upper_approach_cell", "arpeggio_135", "perm_1324")

    def _pattern_for(self, family: str, key: str, chord: str) -> dict:
        m = _motif(key, chord, "Advanced")
        p = build_phrase_pattern(m, key_center=key, pattern_type="auto", level="Advanced", pattern_seed=1)
        # Pin the family (Auto picks by seed; rebuild keeps a requested family).
        p["pattern_family"] = family
        return rebuild_phrase_pattern(p, key_center=key, pattern_type="auto", level="Advanced")

    def test_change_rhythm_changes_only_rhythm(self) -> None:
        changed = 0
        for family in self.FAMILIES:
            for key, chord in (("C", "G7"), ("Dm", "A7"), ("F#", "C#7")):
                p = self._pattern_for(family, key, chord)
                self.assertEqual(p["pattern_family"], family)
                before = _pitch_state(p)
                r = cycle_motif_rhythm(p)
                self.assertEqual(_pitch_state(r), before, (family, key))
                self.assertEqual(r["pattern_family_name"], p["pattern_family_name"])
                self.assertEqual(decode_abc_midis(build_motif_abc(r, key_center=key)), p["midi"])
                changed += r["rhythm_symbols"] != p["rhythm_symbols"]
                # A later Apply keeps the new rhythm and the pitches.
                q = rebuild_phrase_pattern(r, key_center=key, pattern_type="auto", level="Advanced")
                self.assertEqual(_pitch_state(q), before)
                self.assertEqual(q["cell_rhythm_symbols"], r["cell_rhythm_symbols"])
        self.assertGreater(changed, 10)


class TestNotationAndTab(unittest.TestCase):
    def test_sheet_music_sounds_the_pattern(self) -> None:
        for key, chord in CONTEXTS:
            for level in DIFFICULTIES:
                for seed in range(1, 5):
                    for direction in ("ascending", "descending"):
                        p = _auto(key, chord, level, seed, direction=direction)
                        abc = build_motif_abc(p, key_center=key)
                        self.assertEqual(decode_abc_midis(abc), p["midi"], (key, chord, p["pattern_family"]))

    def test_guitar_tab_exact_pitch(self) -> None:
        for key, chord in CONTEXTS:
            for seed in range(1, 5):
                p = _auto(key, chord, "Advanced", seed)
                self.assertEqual(motif_guitar_tab_midis(p), p["midi"])
                placements = motif_guitar_tab_placements(p)
                self.assertEqual([midi_from_guitar_position(s, f) for s, f in placements], p["midi"])


class TestExplicitTypesUnchanged(unittest.TestCase):
    def test_explicit_types_match_legacy_builder(self) -> None:
        for key, chord in CONTEXTS:
            m = _motif(key, chord)
            for ptype in ("scalar", "thirds", "fourths", "pentatonic"):
                for direction in ("ascending", "descending"):
                    new = build_phrase_pattern(m, key_center=key, pattern_type=ptype, direction=direction, level="Advanced")
                    old = build_motif_pattern(m, key_center=key, pattern_type=ptype, direction=direction)
                    self.assertEqual((new["notes"], new["midi"]), (old["notes"], old["midi"]), (key, ptype))
                    self.assertNotIn("pattern_family", new)

    def test_leaving_auto_rebuilds_from_the_users_motif(self) -> None:
        m = _motif("C", "G7")
        p = build_phrase_pattern(m, key_center="C", pattern_type="auto", level="Advanced", pattern_seed=3)
        t = rebuild_phrase_pattern(p, key_center="C", pattern_type="thirds", level="Advanced")
        legacy = build_motif_pattern(m, key_center="C", pattern_type="thirds", length=8)
        self.assertEqual((t["notes"], t["midi"]), (legacy["notes"], legacy["midi"]))
        self.assertNotIn("pattern_family", t)
        b = build_phrase_pattern(p, key_center="C", pattern_type="fourths", level="Advanced")
        self.assertEqual(b["base_motif_notes"], m["notes"])


class TestPhraseMotifUiWiring(unittest.TestCase):
    def test_ui_routes_patterns_through_the_facade(self) -> None:
        src = Path("improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("build_motif_pattern(", src)
        self.assertNotIn("rebuild_motif_pattern(", src)
        self.assertEqual(src.count("rebuild_phrase_pattern("), 2)
        self.assertEqual(src.count("build_phrase_pattern(") - src.count("rebuild_phrase_pattern("), 1)
        # Level-scoped (C2.1) so a student's first idea at each level is exact-level.
        self.assertIn("pattern_seed=next_pattern_seed(session_state, level=level)", src)
        self.assertIn("'Pattern: {html.escape(str(motif.get(\"pattern_family_name\")", src)

    def test_card_label_is_human_readable(self) -> None:
        for fam in PATTERN_FAMILIES.values():
            self.assertNotIn("_", fam.name, fam.id)


if __name__ == "__main__":
    unittest.main()
