"""MC2 — one connected motif across a selected harmonic span."""

from __future__ import annotations

import logging
import unittest
from fractions import Fraction

from harmonic_span_analyzer import analyze_harmonic_spans
from improvisation_motif import (
    build_motif_abc,
    midi_from_guitar_position,
    motif_guitar_tab_placements,
    section_harmony_rows,
)
from melodic_pattern_engine import build_context
from melodic_rhythm_engine import events_from_json
from span_motif_engine import (
    build_span_exercise,
    chord_timeline,
    cycle_span_rhythm,
    generate_span_motif,
    note_chord_assignment,
    project_span_motif,
    voice_leading_cost,
)
from tests.abc_pitch_decoder import bar_chord_symbols, decode_abc_midis

logging.disable(logging.CRITICAL)

LEVELS = ("Beginner", "Intermediate", "Advanced")
C_MAJOR = {0, 2, 4, 5, 7, 9, 11}


def _span(chords: list[str], key: str, n: int | None = None, *, raw: list[str] | None = None):
    rows = section_harmony_rows({"A": raw or chords}, section_names=["A"])
    n = n or len(chords)
    spans = analyze_harmonic_spans(rows, key_center=key, length=n, source_id="t", include_weak=True)
    return next(s for s in spans if list(s.chords) == chords[:n])


def _segments(motif):
    notes, midis = motif["notes"], motif["midi"]
    return [
        (t["chord"], midis[t["first_note"] : t["last_note"] + 1], notes[t["first_note"] : t["last_note"] + 1])
        for t in motif["chord_timeline"]
    ]


def _max_leap(midis):
    return max((abs(a - b) for a, b in zip(midis, midis[1:])), default=0)


def _all_lengths(span, level, **kw):
    seed = generate_span_motif(span, level=level, **kw)
    return [seed, build_span_exercise(span, seed, length="standard"), build_span_exercise(span, seed, length="extended")]


class TestMajorTwoFiveOne(unittest.TestCase):
    SPAN = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.SPAN = _span(["Dm7", "G7", "Cmaj7"], "C")

    def test_beginner_is_diatonic_and_targets_chord_tones(self) -> None:
        for motif in _all_lengths(self.SPAN, "Beginner"):
            self.assertTrue({m % 12 for m in motif["midi"]} <= C_MAJOR, motif["notes"])
            self.assertEqual(motif["vocabulary_used"], ["chord_tone"])
            self.assertLessEqual(_max_leap(motif["midi"]), 7, motif["notes"])
            for t in motif["transition_targets"]:
                ctx = build_context("C", motif["chord_timeline"][t["chord_index"]]["chord"])
                self.assertIn(t["midi"] % 12, ctx.chord_pcs)
            self.assertIn(motif["midi"][-1] % 12, {0, 4, 7}, "ends on a stable tone of Cmaj7")

    def test_intermediate_guide_tones_and_controlled_approaches(self) -> None:
        for motif in _all_lengths(self.SPAN, "Intermediate"):
            self.assertEqual(motif["development_strategy"], "guide_tone_arc")
            roles = [t["role"] for t in motif["transition_targets"]]
            self.assertTrue(set(roles) <= {"3", "7", "R", "5"})
            self.assertGreaterEqual(sum(r in ("3", "7") for r in roles), len(roles) - 1, roles)
            changes = set(motif["change_indices"])
            for i, m in enumerate(motif["midi"]):
                ctx = build_context("C", motif["chord_timeline"][motif["note_chord_index"][i]]["chord"])
                if m % 12 not in ctx.scale_pcs:
                    # Chromatic notes only as approaches immediately into the next change.
                    self.assertTrue(i + 1 in changes or i + 2 in changes, (motif["notes"], i))
            for c in motif["change_indices"]:
                self.assertLessEqual(abs(motif["midi"][c] - motif["midi"][c - 1]), 2, motif["notes"])

    def test_advanced_tension_on_the_dominant_resolves_into_one(self) -> None:
        altered_seen = 0
        for seed in range(8):
            for motif in _all_lengths(self.SPAN, "Advanced", seed=seed):
                for chord, midis, _names in _segments(motif):
                    outside = [m for m in midis if m % 12 not in C_MAJOR]
                    if chord == "G7" and outside:
                        altered_seen += 1
                    if chord == "Dm7":
                        # Outside notes on ii only as approaches into the change.
                        self.assertLessEqual(len(outside), 2)
                for c in motif["change_indices"]:
                    self.assertLessEqual(abs(motif["midi"][c] - motif["midi"][c - 1]), 2, motif["notes"])
                self.assertIn(motif["midi"][-1] % 12, {0, 4, 7}, motif["notes"])
        self.assertGreater(altered_seen, 12, "Advanced V7 should usually carry altered tension")


class TestMinorTwoFiveOne(unittest.TestCase):
    def test_minor_resolution(self) -> None:
        span = _span(["Bm7b5", "E7", "Am"], "Am")
        a_harmonic = {9, 11, 0, 2, 4, 5, 8}
        for level in LEVELS:
            for motif in _all_lengths(span, level):
                self.assertIn(motif["midi"][-1] % 12, {9, 0}, (level, motif["notes"]))  # A or C
                e7 = [m for chord, midis, _n in _segments(motif) if chord == "E7" for m in midis]
                target = motif["transition_targets"][1]
                self.assertIn(target["midi"] % 12, {4, 8, 11, 2})
                if level == "Beginner":
                    self.assertTrue({m % 12 for m in motif["midi"]} <= a_harmonic | {7}, motif["notes"])
                    self.assertTrue(set(m % 12 for m in e7) <= {4, 8, 11, 2, 9, 0, 5}, motif["notes"])


class TestTritoneSub(unittest.TestCase):
    def test_subv_is_respected(self) -> None:
        span = _span(["Gm7", "Gb7", "Fmaj7"], "F")
        self.assertEqual(span.relationship, "ii_subV_I")
        gb7 = build_context("F", "Gb7")
        for level in LEVELS:
            for motif in _all_lengths(span, level):
                self.assertEqual(motif["development_strategy"], "chord_tone_sequence" if level == "Beginner" else "guide_tone_arc")
                for t in motif["transition_targets"]:
                    if motif["chord_timeline"][t["chord_index"]]["chord"] == "Gb7":
                        self.assertIn(t["midi"] % 12, gb7.chord_pcs)
                for c in motif["change_indices"]:
                    self.assertLessEqual(abs(motif["midi"][c] - motif["midi"][c - 1]), 2, motif["notes"])
                if level == "Advanced":
                    self.assertNotIn("altered", motif["vocabulary_used"])  # subV is lydian dominant


class TestTwoChordAndVamp(unittest.TestCase):
    def test_two_chord_pair(self) -> None:
        span = _span(["G", "C"], "G")
        for level in LEVELS:
            for motif in _all_lengths(span, level):
                chords = {motif["chord_timeline"][i]["chord"] for i in motif["note_chord_index"]}
                self.assertEqual(chords, {"G", "C"})
                self.assertLessEqual(_max_leap(motif["midi"]), 9, motif["notes"])
                self.assertIn(motif["midi"][-1] % 12, {0, 4, 7})

    def test_vamp_repeats_intentionally(self) -> None:
        span = _span(["Am7", "D7"], "G", raw=["Am7", "D7", "Am7", "D7"])
        self.assertTrue(span.repeated_vamp)
        for level in LEVELS:
            seed = generate_span_motif(span, level=level)
            self.assertEqual(seed["development_strategy"], "vamp_restatement")
            ext = build_span_exercise(span, seed, length="extended")
            segs = _segments(ext)
            self.assertEqual(segs[0][1], segs[2][1], "second pass restates the Am7 idea exactly")
            self.assertEqual(seed["span_seed"]["cell"], ext["span_seed"]["cell"])


class TestVoiceLeading(unittest.TestCase):
    def test_cost_prefers_steps_common_tones_and_guide_tones(self) -> None:
        g7 = build_context("C", "G7")
        c = build_context("C", "Cmaj7")
        self.assertLess(voice_leading_cost(60, "R", 61, "3", c), voice_leading_cost(60, "R", 72, "R", c))
        self.assertLess(voice_leading_cost(60, "R", 62, "R", c), voice_leading_cost(60, "R", 67, "5", c))
        self.assertGreater(voice_leading_cost(60, "R", 79, "5", c), 10)
        # 7th of G7 (F) falling to 3rd of Cmaj7 (E) beats leaping to the root.
        self.assertLess(voice_leading_cost(65, "7", 64, "3", c), voice_leading_cost(65, "7", 72, "R", c))
        del g7

    def test_generated_lines_avoid_unnecessary_leaps(self) -> None:
        spans = [_span(["Dm7", "G7", "Cmaj7"], "C"), _span(["Bm7b5", "E7", "Am"], "Am"), _span(["Gm7", "Gb7", "Fmaj7"], "F"),
                 _span(["Am7", "D7", "Gmaj7"], "G"), _span(["G", "C"], "G")]
        for span in spans:
            for level in LEVELS:
                for seed in range(5):
                    for motif in _all_lengths(span, level, seed=seed):
                        self.assertLessEqual(_max_leap(motif["midi"]), 9 if level != "Beginner" else 8, (span.chords, level, motif["notes"]))
                        # Target-to-target motion inside each pass (the answer pass of an
                        # extended exercise is voice-led from where the line actually is,
                        # which the note-to-note leap limit above already covers).
                        targets = [t["midi"] for t in motif["transition_targets"]]
                        size = len(span.chords)
                        moves = [
                            abs(targets[i] - targets[i - 1])
                            for i in range(1, len(targets))
                            if i % size != 0
                        ]
                        self.assertLessEqual(sum(moves) / len(moves), 4.5, (span.chords, level, targets))


class TestTimeline(unittest.TestCase):
    def test_every_note_is_on_the_right_chord_and_targets_land_on_downbeats(self) -> None:
        span = _span(["Gm7", "C7", "Fmaj7"], "F", raw=["Gm7", "C7", "Fmaj7", "Fmaj7"])
        timeline = chord_timeline(span)
        self.assertEqual([(s.chord, s.bars) for s in timeline], [("Gm7", 1), ("C7", 1), ("Fmaj7", 2)])
        for level in LEVELS:
            for motif in _all_lengths(span, level):
                self.assertEqual(note_chord_assignment(motif), motif["note_chord_index"])
                events = [e for e in events_from_json(motif["rhythm_events"]) if not e.rest]
                for slot, t in zip(motif["chord_timeline"], motif["transition_targets"]):
                    self.assertEqual(events[t["note_index"]].onset, Fraction(slot["start"]))
                    self.assertEqual(t["note_index"], slot["first_note"])
                self.assertEqual(motif["chord_timeline"][2]["bars"], 2)  # the held bar survives
                self.assertEqual(motif["rhythm_meta"]["bars"], sum(s["bars"] for s in motif["chord_timeline"]))

    def test_extended_timeline_repeats_the_span(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        ext = build_span_exercise(span, generate_span_motif(span, level="Intermediate"), length="extended")
        self.assertEqual([s["chord"] for s in ext["chord_timeline"]], ["Dm7", "G7", "Cmaj7"] * 2)
        self.assertEqual(ext["bar_chord_symbols"], ["Dm7", "G7", "Cmaj7"] * 2)


class TestDeterminismAndVariety(unittest.TestCase):
    def test_same_inputs_same_result_new_seed_different_valid_result(self) -> None:
        span = _span(["Am7", "D7", "Gmaj7"], "G")
        for level in LEVELS:
            a = generate_span_motif(span, level=level, seed=11)
            b = generate_span_motif(span, level=level, seed=11)
            self.assertEqual((a["notes"], a["midi"], a["rhythm_events"]), (b["notes"], b["midi"], b["rhythm_events"]))
            others = {tuple(generate_span_motif(span, level=level, seed=s)["midi"]) for s in range(12)}
            self.assertGreater(len(others), 3, level)
            built = build_span_exercise(span, a, length="standard")
            self.assertEqual(built["span_seed"], a["span_seed"])
            self.assertEqual([t["midi"] for t in built["transition_targets"]], [t["midi"] for t in a["transition_targets"]])


class TestLevelVocabulary(unittest.TestCase):
    def test_beginner_never_leaves_the_chord_scales(self) -> None:
        cases = [(["Dm7", "G7", "Cmaj7"], "C"), (["Cmaj7", "A7", "Dm7"], "C"), (["Gm7", "Gb7", "Fmaj7"], "F"), (["Bm7b5", "E7", "Am"], "Am")]
        for chords, key in cases:
            span = _span(chords, key)
            for seed in range(6):
                for motif in _all_lengths(span, "Beginner", seed=seed):
                    for i, m in enumerate(motif["midi"]):
                        ctx = build_context(key, motif["chord_timeline"][motif["note_chord_index"][i]]["chord"])
                        self.assertIn(m % 12, ctx.scale_pcs, (chords, motif["notes"], i))

    def test_advanced_is_richer_than_beginner(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        def outside(level):
            total = 0
            for seed in range(6):
                m = build_span_exercise(span, generate_span_motif(span, level=level, seed=seed), length="standard")
                total += sum(1 for x in m["midi"] if x % 12 not in C_MAJOR)
            return total
        self.assertEqual(outside("Beginner"), 0)
        self.assertGreater(outside("Advanced"), outside("Intermediate"))
        vocab = set()
        for seed in range(6):
            vocab |= set(generate_span_motif(span, level="Advanced", seed=seed)["vocabulary_used"])
        self.assertTrue({"altered", "enclosure"} <= vocab, vocab)


class TestRhythm(unittest.TestCase):
    def test_change_rhythm_keeps_pitches_and_harmony(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        for level in LEVELS:
            motif = build_span_exercise(span, generate_span_motif(span, level=level), length="standard")
            seen = {motif["rhythm_meta"]["id"]}
            cur = motif
            for _ in range(3):
                cur = cycle_span_rhythm(cur)
                self.assertEqual(cur["notes"], motif["notes"])
                self.assertEqual(cur["midi"], motif["midi"])
                self.assertEqual(cur["note_chord_index"], motif["note_chord_index"])
                self.assertEqual(cur["span_id"], motif["span_id"])
                self.assertEqual(note_chord_assignment(cur), motif["note_chord_index"])
                seen.add(cur["rhythm_meta"]["id"])
            self.assertGreater(len(seen), 1, level)


class TestNotationAndTab(unittest.TestCase):
    def test_abc_sounds_the_motif_and_marks_each_chord(self) -> None:
        span = _span(["Gm7", "C7", "Fmaj7"], "F", raw=["Gm7", "C7", "Fmaj7", "Fmaj7"])
        for level in LEVELS:
            for motif in _all_lengths(span, level):
                abc = build_motif_abc(motif, key_center="F", bpm=100)
                self.assertEqual(decode_abc_midis(abc), motif["midi"])
                bars = bar_chord_symbols(abc)
                expected = [[s] if s else [] for s in motif["bar_chord_symbols"]]
                self.assertEqual(bars, expected)
                self.assertEqual(bars[:4] if motif["span_length"] != "extended" else bars[:4], [["Gm7"], ["C7"], ["Fmaj7"], []])

    def test_bass_clef_and_written_projection(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        motif = build_span_exercise(span, generate_span_motif(span, level="Intermediate"), length="standard")
        bass = build_motif_abc(motif, key_center="C", bpm=100, clef="bass")
        self.assertIn("clef=bass", bass)
        self.assertEqual(decode_abc_midis(bass), motif["midi"])
        alto = project_span_motif(motif, semitones=9, chart_key="A", project_chord=lambda c: {"Dm7": "Bm7", "G7": "E7", "Cmaj7": "Amaj7"}[c])
        self.assertEqual(alto["midi"], [m + 9 for m in motif["midi"]])
        abc = build_motif_abc(alto, key_center="A", bpm=100)
        self.assertEqual(decode_abc_midis(abc), alto["midi"])
        self.assertEqual(bar_chord_symbols(abc), [["Bm7"], ["E7"], ["Amaj7"]])
        self.assertEqual(alto["note_chord_index"], motif["note_chord_index"])

    def test_guitar_tab_exact_pitch(self) -> None:
        span = _span(["Am7", "D7", "Gmaj7"], "G")
        for level in LEVELS:
            motif = build_span_exercise(span, generate_span_motif(span, level=level), length="standard")
            frets = motif_guitar_tab_placements(motif)
            self.assertEqual([midi_from_guitar_position(s, f) for s, f in frets], motif["midi"])


if __name__ == "__main__":
    unittest.main()
