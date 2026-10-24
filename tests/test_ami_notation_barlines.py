"""AMI exercises that span several measures must show a barline at every measure boundary, on the staff and in the Guitar TAB,
and the user-facing AMI wording uses American English.

Measure boundaries come from the rhythm (time signature and note durations), never from chord names: the staff is checked by
summing the written durations between barlines, and the TAB by counting its notes between barlines against the staff's.
"""

from __future__ import annotations

import re
import unittest
from fractions import Fraction
from pathlib import Path

from improvisation_motif import build_motif_abc, build_motif_guitar_tab, motif_note_measures
from music_coach_ami.exercise_model import GeneratedExercise
from tests.test_ami_active_song_isolation import (
    activate_catalog,
    activate_custom,
    ask,
    fresh,
)

TWO = "Give me an enclosure exercise over the first two chords of the verse"
THREE = "Give me an enclosure exercise over the first three chords of the verse"
ONE = "Give me an enclosure exercise over the first chord of the verse"

def _beats(length: str) -> Fraction:
    """ABC length suffix (L:1/4) in beats: '' 1, '2' 2, '/2' or '/' one half, '3/2' one and a half."""
    if not length:
        return Fraction(1)
    if "/" not in length:
        return Fraction(int(length))
    num, _, den = length.partition("/")
    return Fraction(int(num or 1), int(den or 2))


def abc_body(abc: str) -> str:
    return abc.strip().splitlines()[-1]


def abc_bars(abc: str) -> list[list[tuple[str, Fraction]]]:
    """[[(token, beats), ...], ...] per measure, from the ABC music line (L:1/4)."""
    bars: list[list[tuple[str, Fraction]]] = [[]]
    for m in re.finditer(r'(?P<chord>"[^"]*")|(?P<bar>\|\]?)|(?P<note>[\^_=]*[A-Ga-gz][,\']*(?P<len>\d*/?\d*))', abc_body(abc)):
        if m.group("bar"):
            bars.append([])
        elif m.group("note"):
            beats = _beats(m.group("len"))
            bars[-1].append((m.group("note"), beats))
    return [b for b in bars if b]


def tab_rows(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if re.match(r"^[eBGDAE]\|", ln)]


def tab_note_counts(rows: list[str]) -> list[int]:
    """Notes (fret numbers) between the TAB's barlines, read across all six strings by column."""
    width = len(rows[0])
    counts: list[int] = []
    count = 0
    col = 2
    while col < width:
        ch = [r[col] for r in rows]
        if any(c == "|" for c in ch):
            counts.append(count)
            count = 0
            col += 1
            continue
        digits = [c for c in ch if c.isdigit()]
        if digits:
            count += 1
            col += max(len(re.match(r"\d+", r[col:]).group()) for r in rows if r[col].isdigit())
            continue
        col += 1
    return counts


def card_texts(resp) -> str:
    return "\n".join(str(x) for x in [*resp.practice_steps, resp.explanation, resp.direct_answer])


def guitar_session(song: str = "catalog"):
    s = fresh()
    s["instrument"] = "Guitar"
    activate_catalog(s)
    return s


class TestSpelling(unittest.TestCase):
    def test_the_single_chord_refusal_says_practice(self) -> None:
        from music_coach_ami.exercise_single import open_single_in_missions

        s = fresh()
        activate_custom(s)
        resp, ex = ask("Give me an enclosure exercise over Ebm7.", s)  # a chord the custom song does not have
        action = resp.diagnostics["open_in_missions"]
        result = open_single_in_missions(s, action)
        self.assertFalse(result["ok"])
        self.assertIn("is not one of this song's chords", result["message"])
        self.assertIn("Practice it from the card", result["message"])
        self.assertNotIn("Practise", result["message"])

    def test_the_message_source_uses_american_spelling(self) -> None:
        src = Path(__file__).resolve().parents[1] / "music_coach_ami" / "exercise_single.py"
        text = src.read_text(encoding="utf-8")
        self.assertIn("Practice it from the card, or ask for an exercise over one of the song's chords.", text)

    def test_ami_user_facing_text_has_no_british_practise(self) -> None:
        root = Path(__file__).resolve().parents[1] / "music_coach_ami"
        offenders = [p.name for p in root.glob("*.py") if re.search(r"[Pp]ractis(?:e|ed|es|ing)\b|recognisable|colours the", p.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])

    def test_a_generated_card_says_practice(self) -> None:
        s = guitar_session()
        resp, ex = ask(TWO, s)
        text = card_texts(resp)
        self.assertIn("To practice it over a backing track", text)
        self.assertNotIn("practise", text.lower())


class TestStaffBarlines(unittest.TestCase):
    def _check_staff(self, abc: str, bars_expected: int) -> list[list[tuple[str, Fraction]]]:
        bars = abc_bars(abc)
        self.assertEqual(len(bars), bars_expected, abc_body(abc))
        for i, bar in enumerate(bars):
            self.assertEqual(sum(b for _t, b in bar), 4, f"bar {i + 1} is not a full 4/4 measure: {abc_body(abc)}")
        self.assertTrue(abc_body(abc).rstrip().endswith("|"), "the line must end with a barline")
        self.assertEqual(abc_body(abc).count("|"), bars_expected, "a barline closes every measure, so one sits between each pair")
        return bars

    def test_two_chords_are_two_measures(self) -> None:
        for inst in ("Piano", "Guitar"):
            with self.subTest(instrument=inst):
                s = fresh()
                s["instrument"] = inst
                activate_catalog(s)
                resp, ex = ask(TWO, s)
                self.assertEqual(len(ex.chords), 2)
                self._check_staff(resp.notation_abc, 2)

    def test_three_chords_are_three_measures_with_a_chord_symbol_on_each_downbeat(self) -> None:
        for inst in ("Piano", "Guitar"):
            with self.subTest(instrument=inst):
                s = fresh()
                s["instrument"] = inst
                activate_catalog(s)
                resp, ex = ask(THREE, s)
                self._check_staff(resp.notation_abc, 3)
                body = abc_body(resp.notation_abc)
                self.assertEqual([c.strip('"') for c in re.findall(r'"[^"]*"', body)], list(ex.chords))
                for seg in [x.strip() for x in re.split(r"\|\]?", body) if x.strip()]:
                    self.assertTrue(seg.startswith('"'), f"chord symbol must sit on the measure's first note: {seg}")

    def test_a_single_chord_exercise_keeps_its_measures(self) -> None:
        s = guitar_session()
        resp, ex = ask(ONE, s)
        self._check_staff(resp.notation_abc, ex.bars)

    def test_a_chord_change_inside_a_measure_does_not_make_a_new_measure(self) -> None:
        # one 4/4 measure of four quarter notes carrying a chord symbol on beat 1 and another on beat 3
        motif = {"notes": ["C", "E", "G", "B"], "midi": [60, 64, 67, 71], "rhythm_symbols": ["♩"] * 4, "meter": "4/4",
                 "bar_chord_symbols": ["Cmaj7"]}
        abc = build_motif_abc(motif, key_center="C", bpm=96, title="t")
        self.assertEqual(len(abc_bars(abc)), 1)
        self.assertEqual(abc_body(abc).count("|"), 1)
        self.assertEqual(motif_note_measures(motif), [0, 0, 0, 0])

    def test_four_measures_in_the_shared_renderer(self) -> None:
        notes = ["C", "D", "E", "F", "G", "A", "B", "C", "D", "E", "F", "G", "A", "B", "C", "D"]
        midi = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83, 84, 86]
        motif = {"notes": notes, "midi": midi, "rhythm_symbols": ["♩"] * 16, "meter": "4/4"}
        abc = build_motif_abc(motif, key_center="C", bpm=96, title="t")
        bars = abc_bars(abc)
        self.assertEqual([len(b) for b in bars], [4, 4, 4, 4])
        self.assertEqual(motif_note_measures(motif), [0] * 4 + [1] * 4 + [2] * 4 + [3] * 4)
        tab = build_motif_guitar_tab(motif)
        self.assertEqual(tab_note_counts(tab_rows(tab)), [4, 4, 4, 4])

    def test_three_four_time_breaks_every_three_beats(self) -> None:
        motif = {"notes": ["C", "D", "E", "F", "G", "A"], "midi": [60, 62, 64, 65, 67, 69], "rhythm_symbols": ["♩"] * 6, "meter": "3/4"}
        self.assertEqual(motif_note_measures(motif), [0, 0, 0, 1, 1, 1])
        self.assertEqual(tab_note_counts(tab_rows(build_motif_guitar_tab(motif))), [3, 3])


class TestGuitarTab(unittest.TestCase):
    def _compare(self, resp, ex) -> None:
        staff = abc_bars(resp.notation_abc)
        rows = tab_rows(card_texts(resp))
        self.assertEqual(len(rows), 6, "a six-string TAB is shown")
        self.assertEqual(len({len(r) for r in rows}), 1, "all six strings are the same length")
        self.assertEqual(tab_note_counts(rows), [sum(1 for t, _b in bar if not t.startswith("z")) for bar in staff],
                         "TAB notes per measure equal the staff's notes per measure")
        for r in rows:
            self.assertTrue(r.endswith("|"))
            self.assertEqual(r.count("|"), len(staff) + 1, f"a barline at every measure boundary: {r}")
        cols = [{i for i, ch in enumerate(r) if ch == "|"} for r in rows]
        self.assertTrue(all(c == cols[0] for c in cols), "barlines line up in every string")

    def test_tab_and_staff_break_at_the_same_notes(self) -> None:
        for q in (TWO, THREE, ONE):
            with self.subTest(q=q):
                s = guitar_session()
                resp, ex = ask(q, s)
                self._compare(resp, ex)

    def test_the_tab_keeps_every_pitch(self) -> None:
        from improvisation_motif import motif_guitar_tab_midis, motif_guitar_tab_placements, midi_from_guitar_position

        s = guitar_session()
        resp, ex = ask(THREE, s)
        motif = resp.diagnostics["open_in_missions"]["example"]["motif"]
        self.assertEqual([midi_from_guitar_position(a, b) for a, b in motif_guitar_tab_placements(motif)], motif_guitar_tab_midis(motif))
        frets = [int(x) for x in re.findall(r"\d+", "".join(r[2:] for r in tab_rows(card_texts(resp))))]
        self.assertEqual(len(frets), len(motif["notes"]))

    def test_no_barline_characters_leak_into_pitch_data(self) -> None:
        s = guitar_session()
        resp, ex = ask(THREE, s)
        for field in (ex.notes, ex.chords):
            self.assertFalse(any("|" in str(x) for x in field))


class TestKeyChangeAndHandoff(unittest.TestCase):
    def test_barlines_survive_a_practice_key_change(self) -> None:
        for key in ("Bm", "Am", "F#m"):
            with self.subTest(key=key):
                s = guitar_session()
                s["display_key"] = s["concert_key"] = key
                resp, ex = ask(THREE, s)
                self.assertEqual(len(abc_bars(resp.notation_abc)), 3)
                self.assertEqual(len(tab_note_counts(tab_rows(card_texts(resp)))), 3)
                self.assertEqual(ex.context.concert_key, key)

    def test_missions_gets_the_same_measures_as_the_card(self) -> None:
        s = guitar_session()
        resp, ex = ask(THREE, s)
        action = resp.diagnostics["open_in_missions"]
        motif = action["example"]["motif"]
        missions_abc = build_motif_abc(motif, key_center=ex.context.span.get("key_center") or ex.context.concert_key, bpm=96, title="x")
        self.assertEqual(abc_body(missions_abc), abc_body(resp.notation_abc))
        self.assertEqual(abc_bars(missions_abc), abc_bars(resp.notation_abc))
        self.assertEqual(tab_rows(build_motif_guitar_tab(motif)), tab_rows(card_texts(resp)))

    def test_the_stored_exercise_keeps_its_measures(self) -> None:
        s = guitar_session()
        resp, ex = ask(THREE, s)
        again = GeneratedExercise.from_dict(resp.diagnostics["generated_exercise"])
        self.assertEqual(again.bars, ex.bars)
        self.assertEqual(motif_note_measures(resp.diagnostics["open_in_missions"]["example"]["motif"]), sorted(
            motif_note_measures(resp.diagnostics["open_in_missions"]["example"]["motif"])))


if __name__ == "__main__":
    unittest.main()
