"""Phrase & Motif Auto / Musical draws from the C1 pattern vocabulary (Slice C2)."""

from __future__ import annotations

import json
import random
import unittest
from pathlib import Path

from improvisation_motif import (
    PATTERN_SEED_NONCE_KEY,
    cycle_motif_rhythm,
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
    stable_pattern_seed,
    sync_motif_midi,
)
from tests.abc_pitch_decoder import abc_bar_totals, decode_abc_midis

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
    def test_auto_output_is_the_seed_developed(self) -> None:
        """C3.1: Auto realizes the student's motif developed, not a vocabulary cell."""
        for key, chord in CONTEXTS:
            for seed in (1, 2, 3):
                m = _motif(key, chord, "Advanced")
                p = build_phrase_pattern(
                    m, key_center=key, pattern_type="auto", level="Advanced", pattern_seed=seed
                )
                self.assertEqual(p["pattern_type"], "auto")
                self.assertTrue(p["is_pattern"])
                self.assertEqual(p["cells"][0], list(m["notes"]), (key, chord, seed))
                self.assertEqual(p["source_motif_notes"], list(m["notes"]))
                self.assertTrue(p["pattern_development"], (key, chord, seed))
                self.assertEqual(p["pattern_difficulty"], "Advanced")

    def test_motif_shape_matches_existing_pipeline(self) -> None:
        m = _motif("C", "G7", "Intermediate")
        p = build_phrase_pattern(
            m, key_center="C", pattern_type="auto", level="Intermediate", pattern_seed=4
        )
        size = len(m["notes"])
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

    def test_every_bar_is_full(self) -> None:
        # C3: rhythm comes from melodic_rhythm_engine, which may spread a cell over
        # more than one bar (5-/6-note cells) — check real bars in the notation.
        from melodic_rhythm_engine import parse_meter

        for key, chord in CONTEXTS:
            for seed in range(1, 6):
                p = _auto(key, chord, "Advanced", seed)
                abc = build_motif_abc(p, key_center=key)
                bar = parse_meter(p["meter"]).bar
                totals = abc_bar_totals(abc)
                self.assertTrue(totals and all(t == bar for t in totals), (key, chord, p["pattern_family"], totals))
                self.assertEqual(decode_abc_midis(abc), p["midi"], (key, chord, p["pattern_family"]))


class TestDifficulty(unittest.TestCase):
    """C3.1: the vocabulary lives on the *seed* motif, not on Build.

    Build develops whatever motif the student chose, so level-appropriate
    vocabulary is asserted where it is now produced — ``vocabulary_seed_motif``.
    """

    def _families(self, level: str) -> list:
        from improvisation_motif import vocabulary_seed_motif

        out = []
        for key, chord in CONTEXTS:
            for seed in range(1, 9):
                s = vocabulary_seed_motif(chord, key_center=key, level=level, seed=seed)
                if s and s.get("motif_vocabulary_family"):
                    out.append(get_family(s["motif_vocabulary_family"]))
        return out

    def test_beginner_is_simple_and_diatonic(self) -> None:
        fams = self._families("Beginner")
        self.assertTrue(fams)
        self.assertTrue(all(f.difficulty == "Beginner" for f in fams))
        self.assertTrue(all(f.chromatic == "none" for f in fams))
        self.assertTrue(all(f.category not in CHROMATIC_CATEGORIES for f in fams))

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

    def test_beginner_build_output_stays_in_the_key(self) -> None:
        """The reported human-test failure: Beginner must not go outside the key."""
        from improvisation_motif import _parse_key_scale, _pc_of_note, chord_tone_names

        for key, chord in CONTEXTS:
            _mode, diatonic = _parse_key_scale(key)
            allowed = set(diatonic) | {
                _pc_of_note(t) for t in chord_tone_names(chord, reference_key=key)
            }
            for seed in range(1, 6):
                p = _auto(key, chord, "Beginner", seed)
                outside = sorted({n for n in p["notes"] if _pc_of_note(n) not in allowed})
                self.assertFalse(outside, (key, chord, seed, outside))

    def test_difficulty_rises_with_level(self) -> None:
        mean = {
            lvl: sum(DIFFICULTIES.index(f.difficulty) for f in self._families(lvl))
            / max(1, len(self._families(lvl)))
            for lvl in DIFFICULTIES
        }
        self.assertLess(mean["Beginner"], mean["Intermediate"])
        self.assertLess(mean["Intermediate"], mean["Advanced"])


class TestBuildDevelopsTheChosenSeed(unittest.TestCase):
    """C3.1 supersedes C2.1: Build develops the student's motif, it is not a new idea.

    The old contract advanced a level-scoped idea counter on every Build press and
    let the vocabulary engine replace the opening cell. Human testing rejected that
    UX — "New motif" is the action that changes the idea; Build develops it.
    """

    def test_build_keeps_the_seed_as_the_opening_cell(self) -> None:
        for key, chord in CONTEXTS:
            for level in DIFFICULTIES:
                m = _motif(key, chord, level)
                p = build_phrase_pattern(
                    m, key_center=key, pattern_type="auto", level=level,
                    pattern_seed=stable_pattern_seed(m),
                )
                self.assertEqual(p["cells"][0], list(m["notes"]), (key, chord, level))

    def test_repeated_build_never_changes_the_seed_or_the_pattern(self) -> None:
        for key, chord in CONTEXTS:
            for level in DIFFICULTIES:
                m = _motif(key, chord, level)
                seen = {
                    tuple(
                        build_phrase_pattern(
                            m, key_center=key, pattern_type="auto", level=level,
                            pattern_seed=stable_pattern_seed(m),
                        )["midi"]
                    )
                    for _ in range(4)
                }
                self.assertEqual(len(seen), 1, (key, chord, level))

    def test_build_is_deterministic_for_the_same_seed_motif(self) -> None:
        for key, chord in CONTEXTS:
            for level in DIFFICULTIES:
                m = _motif(key, chord, level)
                a = build_phrase_pattern(m, key_center=key, pattern_type="auto", level=level)
                b = build_phrase_pattern(m, key_center=key, pattern_type="auto", level=level)
                self.assertEqual(_pitch_state(a), _pitch_state(b), (key, chord, level))

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
                m = _motif(key, chord, "Advanced")
                p = build_phrase_pattern(
                    m, key_center=key, pattern_type="auto", level="Advanced",
                    length=length, pattern_seed=3,
                )
                size = len(m["notes"])  # C3.1: the cell is the seed motif
                self.assertEqual(p["pattern_length"], length)
                self.assertEqual(len(p["cells"]), length)
                self.assertEqual(len(p["notes"]), length * size)
                self.assertEqual(p["cells"][0], list(m["notes"]))

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

    def test_lowering_level_redevelops_the_same_seed_more_simply(self) -> None:
        """C3.1: level changes the development vocabulary, never the seed."""
        from improvisation_motif import _parse_key_scale, _pc_of_note, chord_tone_names

        p = _auto("C", "G7", "Advanced", 3)
        seed_cell = list(p["cells"][0])
        q = rebuild_phrase_pattern(p, key_center="C", pattern_type="auto", level="Beginner")
        self.assertEqual(q["cells"][0], seed_cell)
        self.assertEqual(q["pattern_development"], "diatonic step sequence")
        # Beginner development must not add notes outside the key beyond the seed.
        _mode, diatonic = _parse_key_scale("C")
        allowed = set(diatonic) | {_pc_of_note(t) for t in chord_tone_names("G7", reference_key="C")}
        allowed |= {_pc_of_note(n) for n in seed_cell}
        outside = sorted({n for n in q["notes"] if _pc_of_note(n) not in allowed})
        self.assertFalse(outside, outside)


class TestSeedAndNewIdeas(unittest.TestCase):
    def test_same_seed_same_pattern(self) -> None:
        for key, chord in CONTEXTS:
            self.assertEqual(_pitch_state(_auto(key, chord, "Advanced", 7)), _pitch_state(_auto(key, chord, "Advanced", 7)))

    def test_new_seed_motifs_give_new_valid_ideas(self) -> None:
        """C3.1: variety comes from New motif (seed), not from pressing Build."""
        from improvisation_motif import vocabulary_seed_motif

        for key, chord in (("C", "G7"), ("Dm", "A7"), ("Eb", "Bb7")):
            seeds = [
                vocabulary_seed_motif(chord, key_center=key, level="Advanced", seed=s)
                for s in range(1, 9)
            ]
            seeds = [s for s in seeds if s]
            outs = {tuple(s["midi"]) for s in seeds}
            fams = {s["motif_vocabulary_family"] for s in seeds}
            self.assertGreaterEqual(len(outs), 5, key)
            self.assertGreaterEqual(len(fams), 3, key)
            # Each new seed becomes the opening cell of its built pattern.
            for s in seeds[:3]:
                p = build_phrase_pattern(
                    {**s, "chord": chord}, key_center=key, pattern_type="auto", level="Advanced"
                )
                self.assertEqual(p["cells"][0], list(s["notes"]))

    def test_next_pattern_seed_advances_session_counter(self) -> None:
        session: dict = {}
        self.assertEqual([next_pattern_seed(session) for _ in range(3)], [1, 2, 3])
        self.assertEqual(session[PATTERN_SEED_NONCE_KEY], 3)
        self.assertEqual(next_pattern_seed(None), 0)


class TestChangeRhythmPreservesPitches(unittest.TestCase):
    FAMILIES = ("lower_approach_arpeggio", "enclosure_classic", "enclosure_four_note", "bebop_run_to_enclosure",
                "upper_approach_cell", "arpeggio_135", "perm_1324")

    def _pattern_for(self, family: str, key: str, chord: str) -> dict:
        """C3.1: the family names the *seed* cell; Build develops it."""
        from improvisation_motif import vocabulary_seed_motif
        from melodic_pattern_engine import generate_pattern

        fam = get_family(family)
        realized = generate_pattern(fam, key=key, chord=chord, direction="ascending", length=1, seed=1)
        cell = realized.cells[0]
        seed_motif = {
            "chord": chord,
            "notes": [n.name for n in cell],
            "midi": [int(n.midi) for n in cell],
            "motif_vocabulary_family": fam.id,
            "motif_vocabulary_name": fam.name,
        }
        del vocabulary_seed_motif  # drawn explicitly above for a deterministic family
        return build_phrase_pattern(
            seed_motif, key_center=key, pattern_type="auto", level="Advanced", pattern_seed=1
        )

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
        # C3.1: Build develops the chosen motif — it must not advance the idea counter.
        self.assertIn("pattern_seed=stable_pattern_seed(motif)", src)
        self.assertNotIn("pattern_seed=next_pattern_seed(", src)
        self.assertIn("'Pattern: {html.escape(str(motif.get(\"pattern_family_name\")", src)

    def test_card_label_is_human_readable(self) -> None:
        for fam in PATTERN_FAMILIES.values():
            self.assertNotIn("_", fam.name, fam.id)


if __name__ == "__main__":
    unittest.main()
