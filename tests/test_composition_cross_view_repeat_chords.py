"""Chord symbols cover every repeated melody pass in all four score views (2026-11-19).

build_section_score_model is the one builder behind the Composition staff, Practice, Backing and Creative/SBI.
With a melody repeated x2-x4 the section's own progression covers only the first pass, and the measure labels
padded the rest by holding the LAST chord: a D-Bm-G-A verse printed "D Bm G A A A A A" over a x2 melody, and the
ABC carried chord marks for the first pass only.

The builder now cycles the progression over the melody's span (Commit C's harmony_covering_melody) before the bar
count is derived from it. Render-time only: the saved section keeps its canonical progression, so Backing section
length, loops and generator input are unchanged.
"""

import copy
import re
import unittest

from composition_melody_notation import build_section_score_model, chord_symbols_by_measure


def _events(bars: int, *, beats_per_bar: float = 4.0, passes: int = 1) -> list[dict]:
    """One whole-bar note per bar, tiled `passes` times with repeat markers."""
    one = [
        {"pitch": p, "duration_beats": beats_per_bar, "beat": i * beats_per_bar}
        for i, p in enumerate(["D4", "F#4", "A4", "G4"] * 4)
    ][:bars]
    out: list[dict] = []
    span = bars * beats_per_bar
    for r in range(passes):
        for ev in one:
            row = dict(ev)
            row["beat"] = float(ev["beat"]) + r * span
            row["repeat_index"] = r
            row["pass_index"] = r
            out.append(row)
    return out


def _entries(*pairs: tuple[str, int]) -> list[dict]:
    return [{"chord": c, "bars": b} for c, b in pairs]


def _abc_chords(abc: str) -> list[str]:
    return [t.strip('"') for t in re.findall(r'"[^"]+"', abc)]


def _model(events, chords, *, meter="4/4", key="D"):
    return build_section_score_model(events=events, chords=chords, key=key, meter=meter, bpm=100)


class TestRepeatedMelodyCoverage(unittest.TestCase):
    def test_x2_melody_repeats_the_progression_instead_of_holding_the_last_chord(self) -> None:
        chords = _entries(("D", 1), ("Bm", 1), ("G", 1), ("A", 1))
        events = _events(4, passes=2)
        self.assertEqual(  # the old behaviour, still what the raw measure labeller does on its own
            chord_symbols_by_measure(chords, meter="4/4", measures=8),
            ["D", "Bm", "G", "A", "A", "A", "A", "A"],
        )
        model = _model(events, chords)
        self.assertEqual(model["measures"], 8)
        self.assertEqual(model["chord_labels"], ["D", "Bm", "G", "A", "D", "Bm", "G", "A"])
        self.assertEqual(_abc_chords(model["abc"]), ["D", "Bm", "G", "A", "D", "Bm", "G", "A"])

    def test_x3_melody_covers_every_pass(self) -> None:
        model = _model(_events(2, passes=3), _entries(("C", 1), ("G", 1)))
        self.assertEqual(model["measures"], 6)
        self.assertEqual(model["chord_labels"], ["C", "G", "C", "G", "C", "G"])

    def test_already_covering_chords_are_not_duplicated(self) -> None:
        chords = _entries(*[(c, 1) for c in ("D", "Bm", "G", "A", "D", "Bm", "G", "A")])
        model = _model(_events(4, passes=2), chords)
        self.assertEqual(model["measures"], 8)
        self.assertEqual(model["chord_labels"], ["D", "Bm", "G", "A", "D", "Bm", "G", "A"])
        self.assertEqual(len(_abc_chords(model["abc"])), 8)

    def test_a_progression_longer_than_the_melody_is_left_alone(self) -> None:
        """Commit-era behaviour: the full accepted progression still shows past the melody's end."""
        chords = _entries(*[(c, 1) for c in ("D", "Bm", "G", "A", "F#m", "E")])
        model = _model(_events(4, passes=1), chords)
        self.assertEqual(model["measures"], 6)
        self.assertEqual(model["chord_labels"], ["D", "Bm", "G", "A", "F#m", "E"])

    def test_single_pass_melody_is_unchanged(self) -> None:
        chords = _entries(("D", 1), ("Bm", 1), ("G", 1), ("A", 1))
        model = _model(_events(4, passes=1), chords)
        self.assertEqual(model["chord_labels"], ["D", "Bm", "G", "A"])
        self.assertEqual(model["measures"], 4)

    def test_chords_only_section_without_a_melody_is_unchanged(self) -> None:
        chords = _entries(("D", 1), ("Bm", 1))
        model = _model([], chords)
        self.assertEqual(model["chord_labels"], ["D", "Bm"])
        self.assertFalse(model["has_melody"])


class TestMeterAndDuration(unittest.TestCase):
    def test_three_four(self) -> None:
        model = _model(_events(2, beats_per_bar=3.0, passes=2), _entries(("C", 1), ("F", 1)), meter="3/4", key="C")
        self.assertEqual(model["measures"], 4)
        self.assertEqual(model["chord_labels"], ["C", "F", "C", "F"])

    def test_six_eight(self) -> None:
        model = _model(_events(2, beats_per_bar=6.0, passes=2), _entries(("C", 1), ("G", 1)), meter="6/8", key="C")
        self.assertEqual(model["measures"], 4)
        self.assertEqual(model["chord_labels"], ["C", "G", "C", "G"])

    def test_multi_bar_chords_keep_their_length(self) -> None:
        chords = _entries(("D", 2), ("G", 2))
        model = _model(_events(4, passes=2), chords)
        self.assertEqual(model["measures"], 8)
        self.assertEqual(model["chord_labels"], ["D", "D", "G", "G", "D", "D", "G", "G"])

    def test_the_last_cycled_chord_is_trimmed_at_the_final_bar(self) -> None:
        """6-bar melody over D(2) G(2): the third entry may only fill the 2 bars that are left... and here 2 fit."""
        chords = _entries(("D", 2), ("G", 2))
        model = _model(_events(3, passes=2), chords)  # 6 bars
        self.assertEqual(model["measures"], 6)
        self.assertEqual(model["chord_labels"], ["D", "D", "G", "G", "D", "D"])

    def test_a_trimmed_entry_never_overruns_the_melody(self) -> None:
        """5-bar melody over D(2) G(2): the cycled D must be cut to one bar, not two."""
        chords = _entries(("D", 2), ("G", 2))
        model = _model(_events(5, passes=1), chords)
        self.assertEqual(model["measures"], 5)
        self.assertEqual(model["chord_labels"], ["D", "D", "G", "G", "D"])


class TestRepeatBarsAndCanonicalData(unittest.TestCase):
    def test_percent_repeat_entries_survive(self) -> None:
        chords = [{"chord": "D", "bars": 1}, {"repeat": True, "bars": 1}]
        model = _model(_events(2, passes=2), chords)
        self.assertEqual(model["measures"], 4)
        self.assertEqual(len(model["chord_labels"]), 4)
        self.assertEqual(model["chord_labels"][0], "D")
        self.assertEqual(model["chord_labels"][0], model["chord_labels"][2])

    def test_the_saved_progression_is_never_mutated(self) -> None:
        chords = _entries(("D", 2), ("G", 2))
        before = copy.deepcopy(chords)
        events = _events(4, passes=2)
        events_before = copy.deepcopy(events)
        _model(events, chords)
        self.assertEqual(chords, before)  # same objects, same bar counts: Backing's input is untouched
        self.assertEqual(events, events_before)

    def test_plain_symbol_lists_work_too(self) -> None:
        model = _model(_events(2, passes=2), ["C", "G"])
        self.assertEqual(model["chord_labels"], ["C", "G", "C", "G"])

    def test_covering_twice_changes_nothing(self) -> None:
        """The Composition staff already covers before calling (Commit C); the builder's own pass must be a no-op."""
        from composition_melody_preview import harmony_covering_melody

        chords = _entries(("D", 1), ("Bm", 1), ("G", 1), ("A", 1))
        events = _events(4, passes=2)
        once = _model(events, chords)
        pre = list(harmony_covering_melody(chords, events, meter="4/4"))
        twice = _model(events, pre)
        self.assertEqual(once["chord_labels"], twice["chord_labels"])
        self.assertEqual(once["abc"], twice["abc"])
        self.assertEqual(once["chord_strip_html"], twice["chord_strip_html"])


class TestEveryCallerUsesTheSameBuilder(unittest.TestCase):
    def test_the_four_render_callers_are_the_only_ones(self) -> None:
        """If a new caller appears, this test points at it so coverage is reviewed for that view too."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        callers = {
            p.name
            for p in root.glob("*.py")
            if "build_section_score_model" in p.read_text(encoding="utf-8", errors="ignore")
        }
        self.assertEqual(
            callers,
            {
                "composition_melody_notation.py",  # the builder itself
                "composition_studio_page.py",  # Composition staff
                "improvisation_intelligence_ui.py",  # Creative / SBI
                "streamlit_music_practice_app.py",  # Practice + Backing
            },
        )


if __name__ == "__main__":
    unittest.main()
