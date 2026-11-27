"""A whole-section refinement must cover every bar the chords do.

The musician's report: a melody over D|Bm|G|A|D|Bm|G|A, refined with "Simplify it"
or "Make it more energetic", played the first bars with melody and the later bars as
chords with no melody at all. The cause was a re-lay of every event end-to-end from
beat 0 after notes were shortened or deleted, which made the melody shorter than the
section it belongs to.
"""

from __future__ import annotations

import unittest

from composition_melody_shape import (
    MELODY_REFINEMENTS,
    propose_melody_refinement,
    timeline_span,
)

BEATS_PER_BAR = 4.0
BARS = 8
SECTION_SPAN = BARS * BEATS_PER_BAR  # D|Bm|G|A|D|Bm|G|A in 4/4


def _melody_over_eight_bars() -> list[dict]:
    """One note per beat with real leaps, so every refinement has something to do."""
    shape = [62, 69, 64, 71, 66, 62, 74, 67]
    return [
        {
            "pitch": f"N{shape[b % len(shape)]}",
            "midi": shape[b % len(shape)],
            "duration_beats": 1.0,
            "beat": float(b),
        }
        for b in range(int(SECTION_SPAN))
    ]


def _one_note_per_bar() -> list[dict]:
    """What the generator actually produces for this progression at "simple"."""
    shape = [62, 66, 59, 64, 62, 66, 59, 64]
    return [
        {"pitch": f"N{m}", "midi": m, "duration_beats": 4.0, "beat": float(i * 4)}
        for i, m in enumerate(shape)
    ]


def _bars_with_notes(events: list[dict]) -> set[int]:
    bars: set[int] = set()
    for ev in events:
        if ev.get("is_rest"):
            continue
        start = float(ev.get("beat") or 0.0)
        stop = start + float(ev.get("duration_beats") or 0.0)
        bar = int(start // BEATS_PER_BAR)
        while bar * BEATS_PER_BAR < stop and bar < 64:
            bars.add(bar + 1)
            bar += 1
    return bars


class TestRefinementCoversTheWholeSection(unittest.TestCase):
    def test_every_refinement_leaves_a_note_in_every_bar(self) -> None:
        for source_name, source in (
            ("one note per beat", _melody_over_eight_bars()),
            ("one note per bar", _one_note_per_bar()),
        ):
            for rid, label, _ in MELODY_REFINEMENTS:
                result = propose_melody_refinement(source, rid, key="D major")
                if not result.get("ok") or result.get("unchanged"):
                    continue
                events = list(result.get("events") or [])
                covered = _bars_with_notes(events)
                missing = sorted(set(range(1, BARS + 1)) - covered)
                self.assertEqual(
                    missing,
                    [],
                    f"{label} on a {source_name} melody left bars {missing} "
                    f"with chords and no melody",
                )

    def test_no_refinement_runs_past_the_final_chord(self) -> None:
        source = _melody_over_eight_bars()
        for rid, label, _ in MELODY_REFINEMENTS:
            result = propose_melody_refinement(source, rid, key="D major")
            if not result.get("ok") or result.get("unchanged"):
                continue
            events = list(result.get("events") or [])
            self.assertLessEqual(
                timeline_span(events),
                SECTION_SPAN,
                f"{label} grew the melody past the section's last chord",
            )
            for ev in events:
                self.assertLess(
                    float(ev.get("beat") or 0.0),
                    SECTION_SPAN,
                    f"{label} placed a note after the section ended",
                )

    def test_refined_notes_never_overlap(self) -> None:
        """A melody is one voice: two notes sounding at once is not a melody."""
        source = _melody_over_eight_bars()
        for rid, label, _ in MELODY_REFINEMENTS:
            result = propose_melody_refinement(source, rid, key="D major")
            if not result.get("ok") or result.get("unchanged"):
                continue
            events = sorted(
                list(result.get("events") or []), key=lambda e: float(e.get("beat") or 0.0)
            )
            for earlier, later in zip(events, events[1:]):
                stop = float(earlier.get("beat") or 0.0) + float(
                    earlier.get("duration_beats") or 0.0
                )
                self.assertLessEqual(
                    round(stop, 4),
                    round(float(later.get("beat") or 0.0), 4),
                    f"{label} left two notes sounding at once",
                )

    def test_a_tiled_two_pass_melody_keeps_both_passes(self) -> None:
        from composition_melody_repeats import (
            detect_repeat_count,
            expand_melody_events_by_repeats,
        )

        pattern = _melody_over_eight_bars()[:16]  # four bars
        tiled = expand_melody_events_by_repeats(pattern, 2)
        self.assertEqual(detect_repeat_count(tiled), 2)
        for rid, label, _ in MELODY_REFINEMENTS:
            result = propose_melody_refinement(tiled, rid, key="D major")
            if not result.get("ok") or result.get("unchanged"):
                continue
            events = list(result.get("events") or [])
            self.assertEqual(
                detect_repeat_count(events),
                2,
                f"{label} lost a repeated pass's identity",
            )
            missing = sorted(set(range(1, BARS + 1)) - _bars_with_notes(events))
            self.assertEqual(missing, [], f"{label} emptied bars {missing} of pass two")


class TestRefinementsStillDoTheirJob(unittest.TestCase):
    """Coverage must not be bought by making the refinements do nothing."""

    def test_energetic_really_shortens_notes(self) -> None:
        source = _one_note_per_bar()
        result = propose_melody_refinement(source, "energetic", key="D major")
        self.assertTrue(result.get("ok"))
        before = [float(e["duration_beats"]) for e in source]
        after = [float(e["duration_beats"]) for e in result["events"]]
        self.assertLess(sum(after), sum(before), "notes did not get crisper")

    def test_simplify_removes_notes_and_lengthens_the_rest(self) -> None:
        source = _melody_over_eight_bars()
        result = propose_melody_refinement(source, "simplify", key="D major")
        self.assertTrue(result.get("ok"))
        events = list(result["events"])
        self.assertLess(len(events), len(source), "no notes were removed")
        longest_before = max(float(e["duration_beats"]) for e in source)
        longest_after = max(float(e["duration_beats"]) for e in events)
        self.assertGreater(
            longest_after, longest_before, "the notes left behind did not take up the space"
        )

    def test_emotional_sustains_the_peak_without_growing_the_phrase(self) -> None:
        source = _melody_over_eight_bars()
        result = propose_melody_refinement(source, "emotional", key="D major")
        self.assertTrue(result.get("ok"))
        events = list(result["events"])
        self.assertEqual(timeline_span(events), timeline_span(source))
        self.assertGreater(
            max(float(e["duration_beats"]) for e in events),
            max(float(e["duration_beats"]) for e in source),
            "no note was given longer to sing",
        )

    def test_emotional_still_works_when_the_peak_is_the_final_note(self) -> None:
        """A rising line ends on its highest note, and that note can still be sustained.

        Refusing to run past the last chord must not turn the refinement into a no-op:
        with nothing after it to borrow from, the peak starts earlier instead.
        """
        rising = [
            {"pitch": "N60", "midi": 60, "beat": 0.0, "duration_beats": 1.0},
            {"pitch": "N62", "midi": 62, "beat": 1.0, "duration_beats": 1.0},
            {"pitch": "N64", "midi": 64, "beat": 2.0, "duration_beats": 1.0},
            {"pitch": "N65", "midi": 65, "beat": 3.0, "duration_beats": 1.0},
            {"pitch": "N67", "midi": 67, "beat": 4.0, "duration_beats": 1.0},
        ]
        result = propose_melody_refinement(rising, "emotional", key="C major")
        self.assertTrue(result.get("ok"), "the refinement did nothing at all")
        self.assertFalse(result.get("unchanged"))
        events = list(result["events"])
        self.assertEqual(
            timeline_span(events), timeline_span(rising), "the phrase changed length"
        )
        peak = max(events, key=lambda e: int(e.get("midi") or 0))
        self.assertGreater(
            float(peak["duration_beats"]), 1.0, "the climax note was not sustained"
        )

    def test_rhythm_adds_a_note_without_shortening_the_section(self) -> None:
        source = _one_note_per_bar()
        result = propose_melody_refinement(source, "rhythm", key="D major")
        self.assertTrue(result.get("ok"))
        events = list(result["events"])
        self.assertGreater(len(events), len(source))
        self.assertEqual(timeline_span(events), timeline_span(source))


class TestTimelineSpan(unittest.TestCase):
    def test_span_is_the_last_notes_end(self) -> None:
        self.assertEqual(timeline_span(_one_note_per_bar()), 32.0)
        self.assertEqual(timeline_span([]), 0.0)
        self.assertEqual(timeline_span(None), 0.0)

    def test_span_ignores_malformed_rows(self) -> None:
        self.assertEqual(
            timeline_span([{"beat": 0.0, "duration_beats": 2.0}, "not an event", None]), 2.0
        )


class TestTheClosingNoteReachesTheFinalChord(unittest.TestCase):
    """The user's example: D | Bm | G | A | D | Bm | G | A must be sung to the end.

    Shortening notes is the point of "energetic" and of one "rhythm" branch, but doing it to
    the last note left the melody finishing three quarters of a beat before the chords did,
    across every concept. These pin the closing note to the section, for every generated
    starting point rather than one hand-written fixture.
    """

    CHORDS = ["D", "Bm", "G", "A", "D", "Bm", "G", "A"]
    TARGET = 32.0

    def _generated(self):
        from composition_melody_engine import CONCEPTS, build_concept_events

        for cid in CONCEPTS:
            yield cid, build_concept_events(cid, self.CHORDS, key="D", meter="4/4")

    def test_generation_already_covers_all_eight_bars(self) -> None:
        for cid, evs in self._generated():
            with self.subTest(concept=cid):
                self.assertAlmostEqual(timeline_span(evs), self.TARGET, places=2)

    def test_energetic_still_ends_on_the_last_chord(self) -> None:
        for cid, evs in self._generated():
            with self.subTest(concept=cid):
                out = propose_melody_refinement(evs, "energetic", key="D")["events"]
                self.assertAlmostEqual(timeline_span(out), self.TARGET, places=2)

    def test_every_refinement_ends_on_the_last_chord(self) -> None:
        for cid, evs in self._generated():
            for rid, _label, _why in MELODY_REFINEMENTS:
                out = propose_melody_refinement(evs, rid, key="D").get("events") or []
                if not out:
                    continue
                with self.subTest(concept=cid, refinement=rid):
                    # A refinement may add or split a note, which can land a quarter past the
                    # grid; it may never finish short of it.
                    self.assertGreaterEqual(timeline_span(out), self.TARGET - 0.01)

    def test_no_bar_is_left_without_a_note(self) -> None:
        for cid, evs in self._generated():
            for rid, _label, _why in MELODY_REFINEMENTS:
                out = propose_melody_refinement(evs, rid, key="D").get("events") or []
                if not out:
                    continue
                for bar in range(8):
                    lo, hi = bar * 4.0, (bar + 1) * 4.0
                    sounds = any(
                        not e.get("is_rest")
                        and float(e.get("beat") or 0) < hi
                        and float(e.get("beat") or 0) + float(e.get("duration_beats") or 0) > lo
                        for e in out
                    )
                    with self.subTest(concept=cid, refinement=rid, bar=bar + 1):
                        self.assertTrue(sounds, f"bar {bar + 1} has chords but no melody")

    def test_holding_the_last_note_does_not_move_any_onset(self) -> None:
        """The closing note is held, not re-timed, and nothing before it shifts."""
        for cid, evs in self._generated():
            before = [float(e.get("beat") or 0.0) for e in evs]
            out = propose_melody_refinement(evs, "energetic", key="D")["events"]
            with self.subTest(concept=cid):
                self.assertEqual([float(e.get("beat") or 0.0) for e in out], before)

    def test_energetic_still_shortens_the_notes_it_should(self) -> None:
        """Holding the last note must not quietly undo the refinement's purpose."""
        from composition_melody_engine import build_concept_events

        evs = build_concept_events("direct_line", self.CHORDS, key="D", meter="4/4")
        out = propose_melody_refinement(evs, "energetic", key="D")["events"]
        shorter = sum(
            1
            for a, b in zip(evs, out)
            if float(b.get("duration_beats") or 0) < float(a.get("duration_beats") or 0)
        )
        self.assertGreater(shorter, len(evs) // 2, "energetic stopped shortening notes")


class TestADeliberateEndingIsNotOverridden(unittest.TestCase):
    """Reaching the last chord must not mean singing through a rest that was asked for.

    Two different intentions that look similar in an event list: a melody that simply stops
    early (no row after the last note), and a melody that stops early and writes an explicit
    rest to close the section. Holding the closing note is right for the first and wrong for
    the second - the singer would breathe through the silence they put there.
    """

    SOUND_ENDS = 28.0
    SPAN = 32.0

    def _with_closing_rest(self):
        rows = [
            {"pitch": p, "midi": m, "beat": b, "duration_beats": 4.0, "is_rest": False}
            for b, (p, m) in enumerate(
                [("D5", 74), ("A4", 69), ("B4", 71), ("D5", 74),
                 ("F#5", 78), ("E5", 76), ("D5", 74)]
            )
            for b in [b * 4.0]
        ]
        rows.append(
            {"pitch": "rest", "midi": None, "beat": 28.0, "duration_beats": 4.0, "is_rest": True}
        )
        return rows

    def _stops_early(self):
        return [dict(e) for e in self._with_closing_rest() if not e["is_rest"]]

    def _last_sounding_end(self, events):
        return max(
            (float(e["beat"]) + float(e["duration_beats"]) for e in events if not e.get("is_rest")),
            default=0.0,
        )

    def test_an_explicit_closing_rest_survives_every_refinement(self) -> None:
        src = self._with_closing_rest()
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = propose_melody_refinement(src, rid, key="D").get("events") or []
            if not out:
                continue
            with self.subTest(refinement=rid):
                self.assertLessEqual(
                    self._last_sounding_end(out),
                    self.SOUND_ENDS + 0.01,
                    "a refinement sang through the closing rest",
                )
                self.assertTrue(
                    any(e.get("is_rest") for e in out), "the closing rest was deleted"
                )
                self.assertAlmostEqual(timeline_span(out), self.SPAN, places=2)

    def test_simplify_removes_notes_not_silences(self) -> None:
        src = self._with_closing_rest()
        out = propose_melody_refinement(src, "simplify", key="D")["events"]
        self.assertTrue(any(e.get("is_rest") for e in out))
        self.assertLess(
            len([e for e in out if not e.get("is_rest")]),
            len([e for e in src if not e.get("is_rest")]),
        )

    def test_a_melody_that_just_stops_early_keeps_its_own_ending(self) -> None:
        """No rest row means the melody's own length is the span: nothing to stretch to."""
        src = self._stops_early()
        self.assertAlmostEqual(timeline_span(src), self.SOUND_ENDS, places=2)
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = propose_melody_refinement(src, rid, key="D").get("events") or []
            if not out:
                continue
            with self.subTest(refinement=rid):
                self.assertLessEqual(self._last_sounding_end(out), self.SOUND_ENDS + 0.26)

    def test_an_internal_rest_is_not_sung_through(self) -> None:
        """A breath in the middle of the phrase is a decision too."""
        src = [
            {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 4.0, "is_rest": False},
            {"pitch": "rest", "midi": None, "beat": 4.0, "duration_beats": 4.0, "is_rest": True},
            {"pitch": "A4", "midi": 69, "beat": 8.0, "duration_beats": 4.0, "is_rest": False},
            {"pitch": "B4", "midi": 71, "beat": 12.0, "duration_beats": 4.0, "is_rest": False},
            {"pitch": "D5", "midi": 74, "beat": 16.0, "duration_beats": 4.0, "is_rest": False},
        ]
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = propose_melody_refinement(src, rid, key="D").get("events") or []
            if not out:
                continue
            first = next((e for e in out if not e.get("is_rest")), None)
            if first is None or float(first.get("beat") or 0.0) != 0.0:
                continue
            with self.subTest(refinement=rid):
                self.assertLessEqual(
                    float(first["beat"]) + float(first["duration_beats"]),
                    4.01,
                    "the opening note was stretched across the rest after it",
                )


if __name__ == "__main__":
    unittest.main()
