"""Guitar TAB fingerings preserve absolute MIDI and prefer playable paths."""

from __future__ import annotations

import unittest

from improvisation_motif import (
    _GUITAR_MIDI_HI,
    _GUITAR_MIDI_LO,
    _naive_guitar_fingering,
    build_motif_guitar_tab,
    guitar_fingering_path_cost,
    guitar_positions_for_midi,
    midi_from_guitar_position,
    motif_guitar_tab_midis,
    motif_guitar_tab_placements,
    optimize_guitar_fingering,
    sync_motif_midi,
)
from improvisation_intelligence import ImprovSessionContext
from improvisation_missions import generate_mission_example
from motif_engine import generate_motif_for_chord, generate_motif_with_variant


def _assert_exact_pitch_path(midis: list[int], placements: list[tuple[int, int]]) -> None:
    assert len(placements) == len(midis)
    for midi, (si, fr) in zip(midis, placements):
        assert midi_from_guitar_position(si, fr) == int(midi), (
            midi,
            si,
            fr,
            midi_from_guitar_position(si, fr),
        )


class TestGuitarPositionExactPitch(unittest.TestCase):
    def test_round_trip_every_open_string(self) -> None:
        from improvisation_motif import _GUITAR_OPEN

        for si, open_m in enumerate(_GUITAR_OPEN):
            self.assertEqual(midi_from_guitar_position(si, 0), open_m)
            self.assertIn((si, 0), guitar_positions_for_midi(open_m))

    def test_multiple_positions_same_absolute_pitch(self) -> None:
        # E4 = MIDI 64: open high e, fret 5 on B, fret 9 on G, …
        opts = guitar_positions_for_midi(64)
        self.assertGreaterEqual(len(opts), 2)
        for si, fr in opts:
            self.assertEqual(midi_from_guitar_position(si, fr), 64)

    def test_out_of_range_has_no_positions(self) -> None:
        self.assertEqual(guitar_positions_for_midi(_GUITAR_MIDI_LO - 1), [])
        self.assertEqual(guitar_positions_for_midi(_GUITAR_MIDI_HI + 1), [])

    def test_build_tab_reports_unplayable_without_octave_lie(self) -> None:
        # After sync keeps pitch classes, a still-unplayable absolute pitch must not
        # be octave-substituted into a fake fretting.
        tab = build_motif_guitar_tab(
            {
                "notes": ["C", "E"],
                "midi": [60, _GUITAR_MIDI_HI + 7],
                "chord": "C",
            }
        )
        self.assertIn("unavailable", tab.lower())
        self.assertIn(str(_GUITAR_MIDI_HI + 7), tab)
    def test_optimize_refuses_silent_octave_shift(self) -> None:
        with self.assertRaises(ValueError):
            optimize_guitar_fingering([_GUITAR_MIDI_LO - 1])


class TestSequenceFingeringOptimization(unittest.TestCase):
    def test_preserves_count_and_midi_for_bm_low_motif(self) -> None:
        # B3–D4–F#4–B3–A3–F#3 — classic low Bm color (absolute pitches).
        midis = [59, 62, 66, 59, 57, 54]
        path = optimize_guitar_fingering(midis)
        _assert_exact_pitch_path(midis, path)
        frets = [fr for _si, fr in path]
        self.assertTrue(max(frets) <= 9, frets)

    def test_ascending_and_descending_preserve_octave(self) -> None:
        ascending = list(range(55, 67))  # G3 → F#4
        descending = list(reversed(ascending))
        for seq in (ascending, descending):
            path = optimize_guitar_fingering(seq)
            _assert_exact_pitch_path(seq, path)

    def test_chromatic_accidentals_exact_midi(self) -> None:
        # C4, C#4, D4, Eb4, E4
        midis = [60, 61, 62, 63, 64]
        path = optimize_guitar_fingering(midis)
        _assert_exact_pitch_path(midis, path)

    def test_repeated_notes_may_reuse_same_seat(self) -> None:
        midis = [64, 64, 64, 67, 64]
        path = optimize_guitar_fingering(midis)
        _assert_exact_pitch_path(midis, path)
        # First three are identical absolute pitch — optimizer may stay put.
        self.assertEqual(path[0], path[1])
        self.assertEqual(path[1], path[2])

    def test_beats_naive_unique_seat_jumps(self) -> None:
        # Exhaust low seats for pitches that share preferred low-fret options.
        # Naive unique-seat greedy climbs to high frets; DP may reuse seats.
        midis = [64, 66, 67, 69, 71, 72, 64, 66, 67, 69, 71, 72]
        naive = _naive_guitar_fingering(midis)
        opt = optimize_guitar_fingering(midis)
        _assert_exact_pitch_path(midis, naive)
        _assert_exact_pitch_path(midis, opt)
        self.assertLessEqual(
            guitar_fingering_path_cost(opt),
            guitar_fingering_path_cost(naive),
        )
        self.assertLessEqual(max(fr for _si, fr in opt), max(fr for _si, fr in naive))

    def test_smoother_than_greedy_when_local_choice_creates_jump(self) -> None:
        # A4 (69) then B3 (59): greedy may leave hand high; DP should prefer
        # a compact A then nearby B (or vice versa) without octave change.
        midis = [57, 59, 62, 64, 69, 59, 57]
        naive = _naive_guitar_fingering(midis)
        opt = optimize_guitar_fingering(midis)
        _assert_exact_pitch_path(midis, opt)
        self.assertLessEqual(
            guitar_fingering_path_cost(opt),
            guitar_fingering_path_cost(naive) + 1e-9,
        )
        # No gratuitous 11–13 style leap when compact exact seats exist.
        jumps = [
            abs(opt[i][1] - opt[i - 1][1]) for i in range(1, len(opt))
        ]
        self.assertTrue(all(j <= 7 for j in jumps), jumps)


class TestMotifTabSheetSync(unittest.TestCase):
    def test_tab_round_trip_matches_motif_midi(self) -> None:
        motif = sync_motif_midi(
            {
                "chord": "Bm",
                "notes": ["B", "D", "F#", "A", "B", "F#", "D", "B"],
                "rhythm": "♩ ♪ ♪ ♩ ♪ ♪ ♩ ♩",
            }
        )
        midis = motif_guitar_tab_midis(motif)
        placements = motif_guitar_tab_placements(motif)
        self.assertEqual(len(placements), len(midis))
        _assert_exact_pitch_path(midis, placements)
        tab = build_motif_guitar_tab(motif)
        self.assertIn("|", tab)
        self.assertEqual(len(tab.splitlines()), 6)

    def test_generated_guitar_motif_tab_matches_midi(self) -> None:
        motif = generate_motif_for_chord(
            "Bm",
            key_center="F#m",
            level="Intermediate",
        )
        motif = sync_motif_midi(motif)
        midis = motif_guitar_tab_midis(motif)
        placements = motif_guitar_tab_placements(motif)
        self.assertEqual(len(placements), len(list(motif.get("notes") or [])))
        _assert_exact_pitch_path(midis, placements)

    def test_auto_musical_variant_preserves_pitches(self) -> None:
        # Harder / new-idea paths include skips and wider leaps.
        for variant in ("normal", "harder", "new"):
            with self.subTest(variant=variant):
                motif = generate_motif_with_variant(
                    "Am7",
                    key_center="C",
                    level="Intermediate",
                    variant=variant,
                )
                midis = motif_guitar_tab_midis(motif)
                placements = motif_guitar_tab_placements(motif)
                _assert_exact_pitch_path(midis, placements)

    def test_mission_guitar_tab_exact_midi(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Say",
            artist="John Mayer",
            key_center="F#m",
            display_key="F#m",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["Bm"]},
        )
        ex = generate_mission_example(
            "Use only chord tones",
            improv_ctx=ctx,
            chord="Bm",
            section="Verse",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            variant="base",
        )
        midis = motif_guitar_tab_midis(ex.motif)
        placements = motif_guitar_tab_placements(ex.motif)
        _assert_exact_pitch_path(midis, placements)
        if ex.tab:
            self.assertEqual(len(placements), len(midis))


class TestNoAccidentalTransposition(unittest.TestCase):
    def test_lower_b_stays_lower_b(self) -> None:
        # B3 (59) must not become B4 (71).
        midis = [59, 62, 59, 54]
        path = optimize_guitar_fingering(midis)
        self.assertEqual([midi_from_guitar_position(*p) for p in path], midis)
        self.assertNotIn(71, [midi_from_guitar_position(*p) for p in path])


if __name__ == "__main__":
    unittest.main()
