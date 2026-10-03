"""C3.1 — Phrase / Motif seed ownership and level-scoped harmonic vocabulary.

Covers the two corrections human testing exposed:

1. Beginner must stay inside the ordinary diatonic collection (the reported case
   produced Gb / Ab / B natural / Db in an F-major context).
2. The generated motif is the canonical seed: Build develops it, it never
   replaces it. Only New / Easier / Harder motif and the pitch transforms change
   the seed.
"""
from __future__ import annotations

import unittest

from improvisation_motif import (
    _parse_key_scale,
    _pc_of_note,
    chord_tone_names,
    cycle_motif_rhythm,
    generate_motif_with_variant,
    transform_motif,
    vocabulary_seed_motif,
)
from motif_engine import (
    build_phrase_pattern,
    rebuild_phrase_pattern,
    stable_pattern_seed,
)

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
        motif,
        key_center=key,
        pattern_type=ptype,
        direction=direction,
        length=length,
        level=level,
        pattern_seed=stable_pattern_seed(motif),
    )


def _in_key_pcs(key: str, chord: str) -> set[int]:
    """The ordinary diatonic collection plus the chord's own tones."""
    _mode, diatonic = _parse_key_scale(key)
    allowed = set(diatonic)
    for t in chord_tone_names(chord, reference_key=key):
        if str(t).strip():
            allowed.add(_pc_of_note(t))
    return allowed


def _outside(notes, key: str, chord: str) -> list[str]:
    allowed = _in_key_pcs(key, chord)
    return sorted({str(n) for n in notes if str(n).strip() and _pc_of_note(str(n)) not in allowed})


class TestABeginnerHarmonicVocabulary(unittest.TestCase):
    """A — Beginner stays inside the key except for real chord tones."""

    CASES = [("F", "Fmaj7"), ("F", "F"), ("C", "C"), ("G", "G7"), ("Dm", "Dm7"), ("Am", "Am7")]

    def test_beginner_auto_build_stays_diatonic(self) -> None:
        for key, chord in self.CASES:
            motif = generate_motif_with_variant(chord, key_center=key, level="Beginner")
            motif["chord"] = chord
            for length in (8, 12, 16):
                for direction in ("ascending", "descending"):
                    p = _build(motif, key=key, level="Beginner", direction=direction, length=length)
                    self.assertFalse(
                        _outside(p["notes"], key, chord),
                        (key, chord, length, direction, _outside(p["notes"], key, chord)),
                    )

    def test_reported_case_fmaj7_has_no_outside_colour(self) -> None:
        """The exact human-test report: Beginner on Fmaj7 showed Gb/Ab/B/Db."""
        motif = generate_motif_with_variant("Fmaj7", key_center="F", level="Beginner")
        motif["chord"] = "Fmaj7"
        p = _build(motif, key="F", level="Beginner", length=16)
        banned = {"Gb", "F#", "Ab", "G#", "B", "Db", "C#", "Eb", "D#"}
        self.assertFalse(banned & set(p["notes"]), sorted(banned & set(p["notes"])))
        self.assertTrue(set(p["notes"]) <= {"F", "G", "A", "Bb", "C", "D", "E"}, sorted(set(p["notes"])))

    def test_beginner_sequence_up_down_stays_diatonic(self) -> None:
        for key, chord in self.CASES:
            motif = generate_motif_with_variant(chord, key_center=key, level="Beginner")
            motif["chord"] = chord
            built = _build(motif, key=key, level="Beginner")
            for target in (motif, built):
                for op in ("sequence_up", "sequence_down"):
                    t = transform_motif(target, op, key_center=key, level="Beginner")
                    self.assertFalse(
                        _outside(t["notes"], key, chord), (key, chord, op, t["notes"])
                    )

    def test_beginner_seed_motifs_are_diatonic(self) -> None:
        for key, chord in self.CASES:
            for variant in ("normal", "new", "easier", "harder"):
                session: dict = {}
                m = generate_motif_with_variant(
                    chord, key_center=key, level="Beginner", variant=variant, session_state=session
                )
                self.assertFalse(_outside(m["notes"], key, chord), (key, chord, variant, m["notes"]))


class TestBAdvancedStaysRich(unittest.TestCase):
    """B — Advanced keeps its chromatic / bebop / enclosure vocabulary."""

    def test_advanced_seed_vocabulary_covers_rich_categories(self) -> None:
        from melodic_pattern_engine import get_family

        cats: set[str] = set()
        for key, chord in (("F", "Fmaj7"), ("C", "G7"), ("Bb", "F7"), ("Dm", "A7")):
            for seed in range(1, 25):
                s = vocabulary_seed_motif(chord, key_center=key, level="Advanced", seed=seed)
                if s and s.get("motif_vocabulary_family"):
                    cats.add(get_family(s["motif_vocabulary_family"]).category)
        self.assertTrue({"bebop", "enclosure", "chromatic_approach"} <= cats, sorted(cats))

    def test_advanced_produces_outside_colour(self) -> None:
        found = False
        for key, chord in (("F", "Fmaj7"), ("C", "G7"), ("Bb", "F7")):
            for seed in range(1, 20):
                s = vocabulary_seed_motif(chord, key_center=key, level="Advanced", seed=seed)
                if s and _outside(s["notes"], key, chord):
                    found = True
                    break
        self.assertTrue(found, "Advanced seeds produced no chromatic colour")

    def test_advanced_development_can_leave_the_key(self) -> None:
        """I — Advanced Auto may sequence chromatically; the seed cell is intact."""
        motif = _seed()
        outside_seen = False
        for seed in range(0, 4):
            p = build_phrase_pattern(
                motif, key_center="C", pattern_type="auto", direction="ascending",
                length=8, level="Advanced", pattern_seed=seed,
            )
            self.assertEqual(p["cells"][0], SEED_NOTES, p["pattern_development"])
            if _outside(p["notes"], "C", "C"):
                outside_seen = True
        self.assertTrue(outside_seen, "Advanced development never left the key")

    def test_beginner_and_advanced_development_differ(self) -> None:
        motif = _seed()
        b = _build(motif, level="Beginner")
        a = build_phrase_pattern(
            motif, key_center="C", pattern_type="auto", length=8, level="Advanced", pattern_seed=1
        )
        self.assertNotEqual(b["pattern_development"], a["pattern_development"])


class TestCSeedPreservedAcrossLengths(unittest.TestCase):
    """C — the opening cell is still the seed at every length."""

    def test_lengths_keep_the_seed(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            for length in (8, 12, 16):
                p = _build(_seed(), level=level, length=length)
                self.assertEqual(p["cells"][0], SEED_NOTES, (level, length))
                self.assertEqual(p["source_motif_notes"], SEED_NOTES)
                self.assertEqual(len(p["cells"]), length)

    def test_explicit_types_keep_the_seed(self) -> None:
        for ptype in ("scalar", "thirds", "fourths"):
            p = _build(_seed(), level="Beginner", ptype=ptype)
            self.assertEqual(p["cells"][0], SEED_NOTES, ptype)

    def test_pentatonic_keeps_a_pentatonic_seed(self) -> None:
        """Pentatonic constrains to its collection by design, so use a seed that
        already lives there — a non-pentatonic note is snapped on purpose."""
        pent = ["G", "A", "C", "D"]  # inside C major pentatonic
        p = _build(_seed(pent), level="Beginner", ptype="pentatonic")
        self.assertEqual(p["cells"][0], pent)


class TestDRepeatedBuild(unittest.TestCase):
    """D — pressing Build again never silently changes the motif."""

    def test_repeated_build_is_stable(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            motif = _seed()
            results = [tuple(_build(motif, level=level)["midi"]) for _ in range(5)]
            self.assertEqual(len(set(results)), 1, level)

    def test_rebuilding_from_a_built_pattern_keeps_the_seed(self) -> None:
        p = _build(_seed(), level="Intermediate")
        for _ in range(3):
            p = rebuild_phrase_pattern(
                p, key_center="C", pattern_type="auto", direction="ascending",
                length=8, level="Intermediate",
            )
            self.assertEqual(p["cells"][0], SEED_NOTES)


class TestENewMotif(unittest.TestCase):
    """E — New motif changes the seed; the next Build opens on it."""

    def test_new_motif_changes_seed_and_build_follows(self) -> None:
        session: dict = {}
        first = generate_motif_with_variant(
            "G7", key_center="C", level="Advanced", variant="new", session_state=session
        )
        second = generate_motif_with_variant(
            "G7", key_center="C", level="Advanced", variant="new", session_state=session
        )
        self.assertNotEqual(list(first["notes"]), list(second["notes"]))
        for m in (first, second):
            m["chord"] = "G7"
            p = _build(m, level="Advanced")
            self.assertEqual(p["cells"][0], list(m["notes"]))


class TestFEasierHarder(unittest.TestCase):
    """F — Easier / Harder motif each become the new canonical seed."""

    def test_easier_and_harder_become_the_seed(self) -> None:
        for variant in ("easier", "harder"):
            for level in ("Beginner", "Intermediate", "Advanced"):
                session: dict = {}
                m = generate_motif_with_variant(
                    "G7", key_center="C", level=level, variant=variant, session_state=session
                )
                m["chord"] = "G7"
                self.assertTrue(m["notes"])
                p = _build(m, level=level)
                self.assertEqual(p["cells"][0], list(m["notes"]), (variant, level))
                self.assertEqual(p["source_motif_notes"], list(m["notes"]))


class TestGDirection(unittest.TestCase):
    """G — descending may relocate the opening cell by an octave, never rewrite it."""

    def test_ascending_keeps_the_seed_exactly(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            p = _build(_seed(), level=level, direction="ascending")
            self.assertEqual(p["cells"][0], SEED_NOTES, level)

    def test_descending_keeps_seed_pitch_classes(self) -> None:
        want = [_pc_of_note(n) for n in SEED_NOTES]
        for level in ("Beginner", "Intermediate", "Advanced"):
            p = _build(_seed(), level=level, direction="descending")
            got = [_pc_of_note(n) for n in p["cells"][0]]
            self.assertEqual(got, want, (level, p["cells"][0]))

    def test_descending_actually_descends(self) -> None:
        p = _build(_seed(), level="Beginner", direction="descending")
        c0 = len(p["cells"][0])
        first = sum(p["midi"][:c0]) / c0
        second = sum(p["midi"][c0 : c0 * 2]) / c0
        self.assertLess(second, first)


class TestHBeginnerSequenceSteps(unittest.TestCase):
    """H — Beginner Sequence Up/Down moves one diatonic degree, shape preserved."""

    def test_sequence_moves_one_scale_step(self) -> None:
        motif = _seed(["F", "A"], chord="F")
        up = transform_motif(motif, "sequence_up", key_center="F", level="Beginner")
        self.assertEqual(up["notes"], ["G", "Bb"])
        down = transform_motif(motif, "sequence_down", key_center="F", level="Beginner")
        self.assertEqual(down["notes"], ["E", "G"])

    def test_sequence_preserves_interval_shape(self) -> None:
        motif = _seed()
        before = [b - a for a, b in zip(motif["midi"], motif["midi"][1:])]
        for op in ("sequence_up", "sequence_down"):
            t = transform_motif(motif, op, key_center="C", level="Beginner")
            after = [b - a for a, b in zip(t["midi"], t["midi"][1:])]
            self.assertEqual(len(after), len(before))
            # Diatonic sequencing keeps the contour; thirds stay thirds (±1 semitone).
            for a, b in zip(before, after):
                self.assertEqual(a > 0, b > 0)
                self.assertLessEqual(abs(abs(a) - abs(b)), 1)

    def test_no_chromatic_substitution_at_beginner(self) -> None:
        for key, chord in (("F", "Fmaj7"), ("C", "C"), ("Am", "Am7")):
            m = generate_motif_with_variant(chord, key_center=key, level="Beginner")
            m["chord"] = chord
            for op in ("sequence_up", "sequence_down"):
                t = transform_motif(m, op, key_center=key, level="Beginner")
                self.assertFalse(_outside(t["notes"], key, chord), (key, op, t["notes"]))


class TestJInvert(unittest.TestCase):
    """J — Invert transforms the seed, and Build then opens on the transformed cell."""

    def test_invert_then_build_uses_the_inverted_seed(self) -> None:
        inv = transform_motif(_seed(), "invert", key_center="C", level="Beginner")
        self.assertEqual(inv["notes"], list(reversed(SEED_NOTES)))
        p = _build(inv, level="Beginner")
        self.assertEqual(p["cells"][0], list(reversed(SEED_NOTES)))

    def test_sequence_then_build_uses_the_sequenced_seed(self) -> None:
        up = transform_motif(_seed(), "sequence_up", key_center="C", level="Beginner")
        p = _build(up, level="Beginner")
        self.assertEqual(p["cells"][0], list(up["notes"]))


class TestKChangeRhythmPitchInvariant(unittest.TestCase):
    """K — the accepted C3 contract: Change Rhythm never moves a pitch."""

    def test_change_rhythm_keeps_every_pitch_and_the_seed(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            p = _build(_seed(), level=level)
            notes, midi = list(p["notes"]), list(p["midi"])
            cell0, seed_notes = list(p["cells"][0]), list(p["source_motif_notes"])
            rhythms = set()
            q = p
            for _ in range(5):
                q = cycle_motif_rhythm(q)
                self.assertEqual(list(q["notes"]), notes, level)
                self.assertEqual(list(q["midi"]), midi, level)
                self.assertEqual(list(q["cells"][0]), cell0, level)
                self.assertEqual(list(q["source_motif_notes"]), seed_notes, level)
                rhythms.add(tuple(q.get("rhythm_symbols") or ()))
            self.assertGreater(len(rhythms), 1, level)


class TestSourceIdentityMetadata(unittest.TestCase):
    """11 — a built pattern always knows which motif it came from."""

    def test_pattern_records_its_source_motif(self) -> None:
        motif = _seed()
        p = _build(motif, level="Intermediate")
        self.assertEqual(p["source_motif_notes"], SEED_NOTES)
        self.assertEqual(len(p["source_motif_midi"]), len(SEED_NOTES))
        self.assertTrue(p["pattern_development"])
        self.assertEqual(p["pattern_source_motif"]["notes"], SEED_NOTES)

    def test_source_identity_survives_direction_and_length_changes(self) -> None:
        p = _build(_seed(), level="Intermediate")
        for direction in ("ascending", "descending"):
            for length in (8, 12, 16):
                q = rebuild_phrase_pattern(
                    p, key_center="C", pattern_type="auto",
                    direction=direction, length=length, level="Intermediate",
                )
                self.assertEqual(q["source_motif_notes"], SEED_NOTES, (direction, length))


if __name__ == "__main__":
    unittest.main()
