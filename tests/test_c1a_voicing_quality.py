"""C1a voicing quality: root-bass frequency, slash-bass correctness, harmonic
coverage, playability, and level differentiation.

These tests measure the musical and physical quality of the new candidate-based
voicing engine and must pass on every build.
"""

from __future__ import annotations

import unittest

from guitar_voicing_engine import (
    GuitarVoicingEvent,
    build_level_guitar_voicings,
    validate_voicing,
    _parse_slash_bass,
    _chord_tone_pcs,
    _root_pc,
)
from music_theory import pitch_class_from_spelled_note, spell_chord_tones

OPEN_PC = [4, 9, 2, 7, 11, 4]  # E A D G B e
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def _sounding_pcs(shape: str) -> set[int]:
    pcs = set()
    for i, ch in enumerate(shape):
        if ch != "x":
            pcs.add((OPEN_PC[i] + int(ch)) % 12)
    return pcs


def _bass_pc(shape: str) -> int | None:
    for i, ch in enumerate(shape):
        if ch != "x":
            return (OPEN_PC[i] + int(ch)) % 12
    return None


def _n_sounding(shape: str) -> int:
    return sum(1 for ch in shape if ch != "x")


def _has_muted_inner(shape: str) -> bool:
    sounding = [i for i, ch in enumerate(shape) if ch != "x"]
    if len(sounding) < 2:
        return False
    for i in range(sounding[0] + 1, sounding[-1]):
        if shape[i] == "x":
            return True
    return False


# ---------------------------------------------------------------------------
# Slash bass parsing
# ---------------------------------------------------------------------------


class TestSlashBassParsing(unittest.TestCase):
    def test_simple_slash_chords(self) -> None:
        self.assertEqual(_parse_slash_bass("C/G"), pitch_class_from_spelled_note("G"))
        self.assertEqual(_parse_slash_bass("C/B"), pitch_class_from_spelled_note("B"))
        self.assertEqual(_parse_slash_bass("C/E"), pitch_class_from_spelled_note("E"))
        self.assertEqual(_parse_slash_bass("E/G#"), pitch_class_from_spelled_note("G#"))

    def test_no_slash(self) -> None:
        self.assertIsNone(_parse_slash_bass("Am"))
        self.assertIsNone(_parse_slash_bass("Cmaj7"))

    def test_flat_slash(self) -> None:
        self.assertEqual(_parse_slash_bass("Fm/Eb"), pitch_class_from_spelled_note("Eb"))


# ---------------------------------------------------------------------------
# Root bass frequency
# ---------------------------------------------------------------------------


class TestRootBassFrequency(unittest.TestCase):
    """Non-slash chords should have root in the bass most of the time."""

    COMMON_CHORDS = ["C", "G", "D", "Am", "F", "Em", "Dm", "A", "E", "Bm",
                     "Cmaj7", "Dm7", "Em7", "Am7", "Fmaj7", "G7",
                     "Fm7", "Bbmaj7", "Eb", "Ab", "Ebmaj7", "Abmaj7"]

    def _root_bass_rate(self, level: str) -> float:
        voicings = build_level_guitar_voicings(self.COMMON_CHORDS, level=level)
        root_count = 0
        for chord, ev in zip(self.COMMON_CHORDS, voicings):
            expected_root = _root_pc(chord)
            actual_bass = _bass_pc(ev.shape)
            if actual_bass == expected_root:
                root_count += 1
        return root_count / len(self.COMMON_CHORDS)

    def test_beginner_root_bass_above_80_percent(self) -> None:
        rate = self._root_bass_rate("Beginner")
        self.assertGreaterEqual(rate, 0.80, f"Beginner root-bass rate {rate:.0%} < 80%")

    def test_intermediate_root_bass_above_60_percent(self) -> None:
        rate = self._root_bass_rate("Intermediate")
        self.assertGreaterEqual(rate, 0.60, f"Intermediate root-bass rate {rate:.0%} < 60%")

    def test_advanced_root_bass_above_50_percent(self) -> None:
        rate = self._root_bass_rate("Advanced")
        self.assertGreaterEqual(rate, 0.50, f"Advanced root-bass rate {rate:.0%} < 50%")


# ---------------------------------------------------------------------------
# Slash bass correctness
# ---------------------------------------------------------------------------


class TestSlashBassCorrectness(unittest.TestCase):
    """Explicit slash-chord bass notes must be honored."""

    SLASH_CHORDS = ["C/G", "C/B", "C/E", "E/G#", "Am/G", "D/F#", "G/B"]

    def _check_slash_bass(self, level: str) -> list[str]:
        voicings = build_level_guitar_voicings(self.SLASH_CHORDS, level=level)
        failures = []
        for chord, ev in zip(self.SLASH_CHORDS, voicings):
            expected = _parse_slash_bass(chord)
            actual = _bass_pc(ev.shape)
            if actual != expected:
                failures.append(f"{chord}: expected bass pc={expected}, got {actual} (shape {ev.shape})")
        return failures

    def test_beginner_slash_bass(self) -> None:
        fails = self._check_slash_bass("Beginner")
        self.assertEqual(fails, [], f"Beginner slash-bass failures:\n" + "\n".join(fails))

    def test_intermediate_slash_bass(self) -> None:
        fails = self._check_slash_bass("Intermediate")
        self.assertEqual(fails, [], f"Intermediate slash-bass failures:\n" + "\n".join(fails))

    def test_advanced_slash_bass(self) -> None:
        fails = self._check_slash_bass("Advanced")
        self.assertEqual(fails, [], f"Advanced slash-bass failures:\n" + "\n".join(fails))


# ---------------------------------------------------------------------------
# Harmonic completeness
# ---------------------------------------------------------------------------


class TestHarmonicCompleteness(unittest.TestCase):
    """Voicings must contain at minimum the root and third (major/minor identity)."""

    TEST_CHORDS = ["C", "Am", "Dm7", "G7", "Cmaj7", "Fm7", "Bdim", "Ebmaj7",
                   "Em9", "Cmaj9", "Gadd9", "Am9"]

    def _check_has_root_and_third(self, level: str) -> list[str]:
        voicings = build_level_guitar_voicings(self.TEST_CHORDS, level=level)
        failures = []
        for chord, ev in zip(self.TEST_CHORDS, voicings):
            pcs = _chord_tone_pcs(chord)
            sounding = _sounding_pcs(ev.shape)
            if len(pcs) >= 2:
                root, third = pcs[0], pcs[1]
                if root not in sounding:
                    failures.append(f"{chord} [{level}] missing root (shape {ev.shape})")
                if third not in sounding:
                    failures.append(f"{chord} [{level}] missing third (shape {ev.shape})")
        return failures

    def test_beginner_has_root_and_third(self) -> None:
        fails = self._check_has_root_and_third("Beginner")
        self.assertEqual(fails, [], "\n".join(fails))

    def test_intermediate_has_root_and_third(self) -> None:
        fails = self._check_has_root_and_third("Intermediate")
        self.assertEqual(fails, [], "\n".join(fails))

    def test_advanced_has_root_and_third(self) -> None:
        fails = self._check_has_root_and_third("Advanced")
        self.assertEqual(fails, [], "\n".join(fails))


# ---------------------------------------------------------------------------
# Extension preservation (Advanced)
# ---------------------------------------------------------------------------


class TestExtensionPreservation(unittest.TestCase):
    """Advanced voicings must preserve defining extensions."""

    EXTENDED_CHORDS = ["Em9", "Cmaj9", "Am9"]

    def test_advanced_preserves_ninth(self) -> None:
        voicings = build_level_guitar_voicings(self.EXTENDED_CHORDS, level="Advanced")
        for chord, ev in zip(self.EXTENDED_CHORDS, voicings):
            pcs = _chord_tone_pcs(chord)
            if len(pcs) >= 5:
                ninth_pc = pcs[4]
                sounding = _sounding_pcs(ev.shape)
                self.assertIn(
                    ninth_pc, sounding,
                    f"{chord} Advanced: missing 9th (pc {ninth_pc}) in shape {ev.shape}"
                )


# ---------------------------------------------------------------------------
# Seventh chord integrity
# ---------------------------------------------------------------------------


class TestSeventhChordIntegrity(unittest.TestCase):
    """Seventh chords must voice their seventh at Intermediate and Advanced."""

    SEVENTH_CHORDS = ["Cmaj7", "Dm7", "G7", "Am7", "Fm7", "Bb7", "Ebmaj7"]

    def _check_seventh(self, level: str) -> list[str]:
        voicings = build_level_guitar_voicings(self.SEVENTH_CHORDS, level=level)
        failures = []
        for chord, ev in zip(self.SEVENTH_CHORDS, voicings):
            pcs = _chord_tone_pcs(chord)
            if len(pcs) >= 4:
                seventh = pcs[3]
                sounding = _sounding_pcs(ev.shape)
                if seventh not in sounding:
                    failures.append(f"{chord}: missing 7th (pc {seventh}) in shape {ev.shape}")
        return failures

    def test_intermediate_voices_seventh(self) -> None:
        fails = self._check_seventh("Intermediate")
        self.assertEqual(fails, [], "Intermediate:\n" + "\n".join(fails))

    def test_advanced_voices_seventh(self) -> None:
        fails = self._check_seventh("Advanced")
        self.assertEqual(fails, [], "Advanced:\n" + "\n".join(fails))


# ---------------------------------------------------------------------------
# Playability
# ---------------------------------------------------------------------------


class TestPlayability(unittest.TestCase):
    """All generated voicings must pass physical playability checks."""

    CHORDS = ["C", "Am", "Dm7", "G7", "Cmaj7", "Fm7", "Bdim", "Ebmaj7",
              "Em9", "C/G", "C/B", "E/G#", "Bb", "F", "Ab", "Gadd9"]

    def _check_playability(self, level: str) -> list[str]:
        max_span = {"Beginner": 3, "Intermediate": 4, "Advanced": 5}[level]
        voicings = build_level_guitar_voicings(self.CHORDS, level=level)
        failures = []
        for chord, ev in zip(self.CHORDS, voicings):
            frets = {}
            for i, ch in enumerate(ev.shape):
                if ch != "x":
                    frets[i] = int(ch)
            ok, reason = validate_voicing(frets, max_span=max_span)
            if not ok:
                failures.append(f"{chord} [{level}] {ev.shape}: {reason}")
        return failures

    def test_beginner_playable(self) -> None:
        fails = self._check_playability("Beginner")
        self.assertEqual(fails, [], "\n".join(fails))

    def test_intermediate_playable(self) -> None:
        fails = self._check_playability("Intermediate")
        self.assertEqual(fails, [], "\n".join(fails))

    def test_advanced_playable(self) -> None:
        fails = self._check_playability("Advanced")
        self.assertEqual(fails, [], "\n".join(fails))

    def test_no_muted_inner_strings(self) -> None:
        """Voicings should not have a muted string between two sounding ones."""
        for level in ("Beginner", "Intermediate", "Advanced"):
            voicings = build_level_guitar_voicings(self.CHORDS, level=level)
            for chord, ev in zip(self.CHORDS, voicings):
                self.assertFalse(
                    _has_muted_inner(ev.shape),
                    f"{chord} [{level}] {ev.shape} has muted inner string"
                )


# ---------------------------------------------------------------------------
# String count
# ---------------------------------------------------------------------------


class TestStringCount(unittest.TestCase):
    """Voicings should use an appropriate number of strings."""

    CHORDS = ["C", "G", "Am", "F", "Dm7", "Em", "A"]

    def test_beginner_at_least_4_strings(self) -> None:
        voicings = build_level_guitar_voicings(self.CHORDS, level="Beginner")
        for chord, ev in zip(self.CHORDS, voicings):
            n = _n_sounding(ev.shape)
            self.assertGreaterEqual(n, 4, f"Beginner {chord}: only {n} strings ({ev.shape})")

    def test_intermediate_at_least_4_strings(self) -> None:
        voicings = build_level_guitar_voicings(self.CHORDS, level="Intermediate")
        for chord, ev in zip(self.CHORDS, voicings):
            n = _n_sounding(ev.shape)
            self.assertGreaterEqual(n, 4, f"Intermediate {chord}: only {n} strings ({ev.shape})")


# ---------------------------------------------------------------------------
# Level differentiation
# ---------------------------------------------------------------------------


class TestLevelDifferentiation(unittest.TestCase):
    """Different levels should produce meaningfully different voicings."""

    def test_three_levels_produce_different_shapes_for_non_open_chords(self) -> None:
        chords = ["Fm7", "Bbmaj7", "Ebmaj7", "Abmaj7"]
        shapes = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            voicings = build_level_guitar_voicings(chords, level=level)
            shapes[level] = [ev.shape for ev in voicings]
        # At least 2 of the 3 levels must differ for a majority of chords.
        diff_count = 0
        for i in range(len(chords)):
            unique = len({shapes[l][i] for l in shapes})
            if unique >= 2:
                diff_count += 1
        self.assertGreaterEqual(diff_count, 2, "Too many chords have identical voicings across levels")


# ---------------------------------------------------------------------------
# Non-chord-tone check
# ---------------------------------------------------------------------------


class TestNoNonChordTones(unittest.TestCase):
    """Every sounding note must be a chord tone (or the slash bass)."""

    CHORDS = ["C", "Am", "G7", "Dm7", "F", "Bdim", "Ebmaj7", "Em9",
              "C/G", "C/B", "C/E", "E/G#"]

    def test_all_levels_sound_only_chord_tones(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            voicings = build_level_guitar_voicings(self.CHORDS, level=level)
            for chord, ev in zip(self.CHORDS, voicings):
                head = chord.split("/")[0]
                allowed = set(_chord_tone_pcs(head))
                slash = _parse_slash_bass(chord)
                if slash is not None:
                    allowed.add(slash)
                sounding = _sounding_pcs(ev.shape)
                bad = sounding - allowed
                self.assertFalse(
                    bad,
                    f"{chord} [{level}] {ev.shape}: non-chord PCs {bad}"
                )


# ---------------------------------------------------------------------------
# F-minor blues progression
# ---------------------------------------------------------------------------


class TestFMinorBluesProgression(unittest.TestCase):
    """F-minor blues should produce musically correct voicings."""

    FM_BLUES = ["Fm7", "Bbm7", "Fm7", "Cm7", "Bbm7", "Fm7"]

    def test_intermediate_all_have_root_bass(self) -> None:
        voicings = build_level_guitar_voicings(self.FM_BLUES, level="Intermediate")
        for chord, ev in zip(self.FM_BLUES, voicings):
            expected = _root_pc(chord)
            actual = _bass_pc(ev.shape)
            self.assertEqual(
                actual, expected,
                f"{chord}: bass pc {actual} != root {expected} (shape {ev.shape})"
            )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    """Voicings must be deterministic: same input -> same output."""

    def test_repeated_calls_identical(self) -> None:
        chords = ["C", "Am", "F", "G7", "Em9", "C/G", "Bdim"]
        for level in ("Beginner", "Intermediate", "Advanced"):
            v1 = [ev.shape for ev in build_level_guitar_voicings(chords, level=level)]
            v2 = [ev.shape for ev in build_level_guitar_voicings(chords, level=level)]
            self.assertEqual(v1, v2, f"{level} voicings are not deterministic")


if __name__ == "__main__":
    unittest.main()
