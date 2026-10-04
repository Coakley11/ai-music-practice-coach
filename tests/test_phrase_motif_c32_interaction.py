"""C3.2 — Phrase / Motif interaction corrections.

Covers the three findings from the C3.1 human retest plus the Bass-clef request:

1. Change Rhythm must actually land on a different, level-appropriate rhythm.
2. Harder / New motif must keep producing new seed ideas.
3. Sequence Up / Down / Invert transform the short seed only — Build Motif
   Pattern is the sole action that expands a seed into an exercise.
4. Instrument = Bass notates in bass clef without moving any pitch.
"""
from __future__ import annotations

import unittest

from improvisation_motif import (
    MOTIF_MODE_PATTERN,
    MOTIF_MODE_SEED,
    _parse_key_scale,
    _pc_of_note,
    build_motif_notation_abc,
    chord_tone_names,
    cycle_motif_rhythm,
    generate_motif_with_variant,
    is_built_pattern,
    is_seed_motif,
    motif_mode,
    notation_clef_for_instrument,
    transform_motif,
)
from motif_engine import build_phrase_pattern, rebuild_phrase_pattern, stable_pattern_seed
from tests.abc_pitch_decoder import decode_abc_midis

LEVELS = ("Beginner", "Intermediate", "Advanced")
SEED_NOTES = ["G", "A", "B", "D"]


def _seed(notes=None, chord="C") -> dict:
    notes = list(notes or SEED_NOTES)
    base = {"C": 60, "D": 62, "E": 64, "F": 65, "G": 67, "A": 69, "B": 71}
    return {
        "chord": chord,
        "notes": notes,
        "midi": [base.get(n[0], 60) + (1 if n.endswith("#") else -1 if n.endswith("b") else 0) for n in notes],
        "rhythm_key": "quarter-quarter-quarter",
    }


def _build(motif, *, key="C", level="Beginner", direction="ascending", length=8, ptype="auto"):
    return build_phrase_pattern(
        motif, key_center=key, pattern_type=ptype, direction=direction,
        length=length, level=level, pattern_seed=stable_pattern_seed(motif),
    )


def _outside(notes, key: str, chord: str) -> list[str]:
    _mode, diatonic = _parse_key_scale(key)
    allowed = set(diatonic) | {
        _pc_of_note(t) for t in chord_tone_names(chord, reference_key=key) if str(t).strip()
    }
    return sorted({str(n) for n in notes if _pc_of_note(str(n)) not in allowed})


def _rhythm_level(motif: dict) -> str:
    meta = motif.get("rhythm_meta") or {}
    return str(meta.get("rhythm_level") or meta.get("level") or "")


class TestAChangeRhythmDiffers(unittest.TestCase):
    """A — Change Rhythm lands on a different rhythm, pitches untouched."""

    def _cases(self):
        for level in LEVELS:
            seed = generate_motif_with_variant("G7", key_center="C", level=level)
            seed["chord"] = "G7"
            yield level, "seed", seed
            yield level, "pattern", _build(seed, level=level)

    def test_successive_changes_differ_and_keep_pitches(self) -> None:
        for level, kind, motif in self._cases():
            notes, midi = list(motif["notes"]), list(motif.get("midi") or [])
            cur, seen = motif, []
            for step in range(6):
                nxt = cycle_motif_rhythm(cur, level=level)
                self.assertEqual(list(nxt["notes"]), notes, (level, kind, step))
                self.assertEqual(list(nxt.get("midi") or []), midi, (level, kind, step))
                self.assertNotEqual(
                    nxt.get("rhythm"), cur.get("rhythm"), (level, kind, step, nxt.get("rhythm"))
                )
                seen.append(nxt.get("rhythm"))
                cur = nxt
            self.assertGreater(len(set(seen)), 1, (level, kind))

    def test_change_rhythm_keeps_seed_and_development_metadata(self) -> None:
        for level in LEVELS:
            seed = generate_motif_with_variant("G7", key_center="C", level=level)
            seed["chord"] = "G7"
            p = _build(seed, level=level)
            before = (
                list(p["source_motif_notes"]), p["pattern_development"],
                p["pattern_direction"], p["pattern_length"], list(p["cells"][0]),
                p["chord"], motif_mode(p),
            )
            q = p
            for _ in range(4):
                q = cycle_motif_rhythm(q, level=level)
                after = (
                    list(q["source_motif_notes"]), q["pattern_development"],
                    q["pattern_direction"], q["pattern_length"], list(q["cells"][0]),
                    q["chord"], motif_mode(q),
                )
                self.assertEqual(after, before, level)

    def test_cycling_wraps_deterministically(self) -> None:
        seed = generate_motif_with_variant("G7", key_center="C", level="Intermediate")
        seed["chord"] = "G7"
        p = _build(seed, level="Intermediate")
        first, cur, ids = None, p, []
        for _ in range(40):
            cur = cycle_motif_rhythm(cur, level="Intermediate")
            rid = str((cur.get("rhythm_meta") or {}).get("id") or "")
            ids.append(rid)
            first = first or rid
        self.assertIn(first, ids[1:], "cycling never wrapped back to the first rhythm")


class TestBChangeRhythmLevel(unittest.TestCase):
    """B — the rhythm vocabulary follows the student's level."""

    def _levels_seen(self, level: str) -> set[str]:
        seed = generate_motif_with_variant("G7", key_center="C", level=level)
        seed["chord"] = "G7"
        cur = _build(seed, level=level)
        out: set[str] = set()
        for _ in range(12):
            cur = cycle_motif_rhythm(cur, level=level)
            lvl = _rhythm_level(cur)
            if lvl:
                out.add(lvl)
        return out

    def test_beginner_only_gets_beginner_rhythms(self) -> None:
        self.assertEqual(self._levels_seen("Beginner"), {"Beginner"})

    def test_intermediate_reaches_intermediate(self) -> None:
        seen = self._levels_seen("Intermediate")
        self.assertTrue(seen <= {"Beginner", "Intermediate"}, seen)
        self.assertIn("Intermediate", seen)

    def test_advanced_reaches_advanced_and_may_include_simpler(self) -> None:
        seen = self._levels_seen("Advanced")
        self.assertIn("Advanced", seen)
        self.assertTrue(seen <= set(LEVELS), seen)


class TestCRepeatedHarderMotif(unittest.TestCase):
    """C — Harder motif keeps producing new, level-appropriate seeds."""

    def test_repeated_harder_gives_new_ideas(self) -> None:
        for key, chord in (("C", "G7"), ("F", "Fmaj7")):
            for level in LEVELS:
                session: dict = {}
                seen: list[tuple[str, ...]] = []
                for _ in range(6):
                    m = generate_motif_with_variant(
                        chord, key_center=key, level=level, variant="harder", session_state=session
                    )
                    session["improv_motif"] = m
                    seen.append(tuple(m["notes"]))
                repeats = [a for a, b in zip(seen, seen[1:]) if a == b]
                self.assertFalse(repeats, (key, chord, level, seen))
                self.assertGreater(len(set(seen)), 2, (key, chord, level, seen))

    def test_beginner_harder_stays_diatonic(self) -> None:
        for key, chord in (("C", "G7"), ("F", "Fmaj7"), ("Am", "Am7")):
            session: dict = {}
            for _ in range(6):
                m = generate_motif_with_variant(
                    chord, key_center=key, level="Beginner", variant="harder", session_state=session
                )
                session["improv_motif"] = m
                self.assertFalse(_outside(m["notes"], key, chord), (key, chord, m["notes"]))

    def test_easier_and_harder_stay_in_seed_mode(self) -> None:
        for variant in ("easier", "harder", "new"):
            for level in LEVELS:
                session: dict = {}
                m = generate_motif_with_variant(
                    "G7", key_center="C", level=level, variant=variant, session_state=session
                )
                self.assertTrue(is_seed_motif(m), (variant, level))
                self.assertFalse(m.get("is_pattern"), (variant, level))


class TestDShortSeedTransforms(unittest.TestCase):
    """D — Sequence / Invert transform the seed and never expand it."""

    def test_transforms_keep_the_seed_short(self) -> None:
        for level in LEVELS:
            for op in ("sequence_up", "sequence_down", "invert"):
                t = transform_motif(_seed(), op, key_center="C", level=level)
                self.assertEqual(len(t["notes"]), len(SEED_NOTES), (level, op, t["notes"]))
                self.assertFalse(t.get("cells"), (level, op))
                self.assertFalse(t.get("is_pattern"), (level, op))
                self.assertTrue(is_seed_motif(t), (level, op))

    def test_transforms_never_reach_a_pattern_length(self) -> None:
        cur = _seed()
        for op in ("sequence_up", "sequence_up", "invert", "sequence_down"):
            cur = transform_motif(cur, op, key_center="C", level="Beginner")
            self.assertLess(len(cur["notes"]), 8, (op, cur["notes"]))

    def test_changing_type_direction_length_does_not_expand_a_seed(self) -> None:
        """Build is the sole expansion action."""
        for ptype in ("auto", "scalar", "thirds"):
            for direction in ("ascending", "descending"):
                for length in (8, 12, 16):
                    r = rebuild_phrase_pattern(
                        _seed(), key_center="C", pattern_type=ptype,
                        direction=direction, length=length, level="Beginner",
                    )
                    self.assertEqual(list(r["notes"]), SEED_NOTES, (ptype, direction, length))
                    self.assertTrue(is_seed_motif(r))

    def test_beginner_sequence_is_one_diatonic_step(self) -> None:
        up = transform_motif(_seed(["F", "A"], chord="F"), "sequence_up", key_center="F", level="Beginner")
        self.assertEqual(up["notes"], ["G", "Bb"])
        down = transform_motif(_seed(["F", "A"], chord="F"), "sequence_down", key_center="F", level="Beginner")
        self.assertEqual(down["notes"], ["E", "G"])


class TestEBuildAfterTransform(unittest.TestCase):
    """E — Build expands whatever the transformed seed now is."""

    def test_build_starts_from_the_transformed_seed(self) -> None:
        for op in ("sequence_up", "sequence_down", "invert"):
            t = transform_motif(_seed(), op, key_center="C", level="Beginner")
            for length in (8, 12, 16):
                p = _build(t, level="Beginner", length=length)
                self.assertEqual(p["cells"][0], list(t["notes"]), (op, length))
                self.assertEqual(len(p["cells"]), length)
                self.assertTrue(is_built_pattern(p))


class TestFSeedActionsAfterAPattern(unittest.TestCase):
    """F — a new idea after a full pattern returns to short seed mode."""

    def test_seed_actions_return_to_seed_mode(self) -> None:
        pattern = _build(_seed(), level="Intermediate", length=16)
        self.assertTrue(is_built_pattern(pattern))
        for variant in ("new", "easier", "harder"):
            session: dict = {"improv_motif": pattern}
            fresh = generate_motif_with_variant(
                "G7", key_center="C", level="Intermediate", variant=variant, session_state=session
            )
            self.assertTrue(is_seed_motif(fresh), variant)
            self.assertLess(len(fresh["notes"]), 16, variant)
            # transforming it keeps it short …
            t = transform_motif(fresh, "sequence_up", key_center="C", level="Intermediate")
            self.assertEqual(len(t["notes"]), len(fresh["notes"]), variant)
            self.assertTrue(is_seed_motif(t), variant)
            # … and Build then opens on that new seed.
            p = _build(t, level="Intermediate")
            self.assertEqual(p["cells"][0], list(t["notes"]), variant)


class TestModeModel(unittest.TestCase):
    """4 — seed vs built pattern is explicit, not inferred from note count."""

    def test_modes_are_declared(self) -> None:
        seed = _seed()
        built = _build(seed, level="Beginner")
        self.assertEqual(motif_mode(built), MOTIF_MODE_PATTERN)
        self.assertEqual(motif_mode(generate_motif_with_variant("G7", key_center="C")), MOTIF_MODE_SEED)

    def test_legacy_motifs_without_the_marker_still_resolve(self) -> None:
        self.assertEqual(motif_mode({"notes": ["C", "D"]}), MOTIF_MODE_SEED)
        self.assertEqual(motif_mode({"notes": ["C"], "is_pattern": True}), MOTIF_MODE_PATTERN)

    def test_a_long_seed_is_still_a_seed(self) -> None:
        """Note count alone must not promote an idea to a pattern."""
        long_seed = _seed(["C", "D", "E", "F", "G", "A", "B", "C"])
        self.assertTrue(is_seed_motif(long_seed))
        r = rebuild_phrase_pattern(long_seed, key_center="C", pattern_type="auto", length=16)
        self.assertEqual(len(r["notes"]), 8)


class TestBassClefNotation(unittest.TestCase):
    """Bass instrument notates in bass clef — display only, pitches unchanged."""

    def _k_field(self, abc: str) -> str:
        return next(ln for ln in abc.splitlines() if ln.startswith("K:"))

    def test_instrument_clef_mapping(self) -> None:
        self.assertEqual(notation_clef_for_instrument("Bass"), "bass")
        self.assertEqual(notation_clef_for_instrument("bass"), "bass")
        for other in ("Guitar", "Piano", "Saxophone", "Trumpet", "Voice", ""):
            self.assertEqual(notation_clef_for_instrument(other), "", other)

    def _objects(self):
        seed = generate_motif_with_variant("G7", key_center="C", level="Intermediate")
        seed["chord"] = "G7"
        built = _build(seed, level="Intermediate")
        return {
            "seed": seed,
            "built": built,
            "change_rhythm": cycle_motif_rhythm(built, level="Intermediate"),
            "sequence_up": transform_motif(built, "sequence_up", key_center="C", level="Intermediate"),
            "invert": transform_motif(seed, "invert", key_center="C", level="Intermediate"),
        }

    def test_bass_uses_bass_clef_everywhere(self) -> None:
        for name, obj in self._objects().items():
            abc = build_motif_notation_abc(obj, key_center="C", bpm=100, instrument="Bass")
            self.assertIn("clef=bass", self._k_field(abc), name)

    def test_other_instruments_keep_treble(self) -> None:
        for name, obj in self._objects().items():
            abc = build_motif_notation_abc(obj, key_center="C", bpm=100, instrument="Guitar")
            self.assertNotIn("clef=", self._k_field(abc), name)

    def test_clef_never_changes_the_pitches(self) -> None:
        for name, obj in self._objects().items():
            bass = build_motif_notation_abc(obj, key_center="C", bpm=100, instrument="Bass")
            treble = build_motif_notation_abc(obj, key_center="C", bpm=100, instrument="Guitar")
            self.assertEqual(decode_abc_midis(bass), list(obj["midi"]), name)
            self.assertEqual(decode_abc_midis(bass), decode_abc_midis(treble), name)


if __name__ == "__main__":
    unittest.main()
