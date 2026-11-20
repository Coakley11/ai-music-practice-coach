"""Plain-English melody directions actually shape the suggestions (2026-11-19).

Before: when a section had chords (the normal case) only four of the ten parsed directions reached the generator,
and register and interval size were not recognised at all -- "high register with larger leaps" and "smooth,
stepwise melody in a low register" produced identical suggestions.

Now: every parsed direction is forwarded, and four new families (high register, low register, larger leaps,
stepwise) steer the existing note chooser through its own knobs -- the melody's centre, the leap allowance and the
contour target. No new generation path, and nothing here may leave the instrument range or break the harmony
rules.
"""

import copy
import unittest

from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_melody_audit import audit_melody, audit_violations
from composition_melody_suggestions import _event_midi, suggest_melody_concepts

PROGS = ("C Am F G", "C F G C", "Am F C G")
RANGE = (55, 79)


def _doc(prog: str, key: str = "C"):
    doc = bootstrap_from_vision(genre="Pop", song_idea="Direction tests.")
    apply_structure_template(doc, "simple")
    doc.setdefault("global", {}).update({"original_key_center": key, "original_key_label": f"{key} major"})
    sec = ordered_sections(doc)[0]
    apply_section_chords(doc, str(sec["id"]), parse_chord_paste(prog))
    return doc, next(s for s in ordered_sections(doc) if str(s["id"]) == str(sec["id"]))


def _ask(prog: str, remember: str = "", *, feel: str = "lyrical", style: str = "simple", rng=RANGE, key: str = "C"):
    doc, sec = _doc(prog, key)
    return suggest_melody_concepts(doc, sec, feel, style, limit=3, remember=remember, range_midi=rng)


def _notes(cand: dict) -> list[int]:
    evs = [
        e
        for e in cand.get("events") or []
        if not (e.get("is_rest") or str(e.get("pitch") or "").lower() == "rest")
    ]
    return [_event_midi(e) for e in evs]


def _all_notes(cands: list[dict]) -> list[int]:
    return [m for c in cands for m in _notes(c)]


def _mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _mean_interval(cands: list[dict]) -> float:
    ivs: list[int] = []
    for c in cands:
        ms = _notes(c)
        ivs += [abs(ms[i + 1] - ms[i]) for i in range(len(ms) - 1)]
    return _mean(ivs)


class TestTheOwnersExample(unittest.TestCase):
    def test_high_and_leaping_is_higher_and_more_intervallic_than_low_and_stepwise(self) -> None:
        for prog in PROGS:
            hi = _ask(prog, "high register with larger leaps")
            lo = _ask(prog, "smooth, stepwise melody in a low register")
            self.assertTrue(hi and lo, prog)
            with self.subTest(prog=prog):
                self.assertGreater(_mean(_all_notes(hi)) - _mean(_all_notes(lo)), 5.0)
                self.assertGreater(_mean_interval(hi) - _mean_interval(lo), 1.0)
                self.assertGreater(max(_all_notes(hi)), max(_all_notes(lo)))

    def test_register_alone_moves_the_line_without_touching_interval_size(self) -> None:
        base = _ask("C Am F G")
        high = _ask("C Am F G", "sing high in the upper range")
        low = _ask("C Am F G", "keep it in a low register")
        self.assertGreater(_mean(_all_notes(high)), _mean(_all_notes(base)) + 3.0)
        self.assertLess(_mean(_all_notes(low)), _mean(_all_notes(base)) - 1.0)
        self.assertLess(abs(_mean_interval(high) - _mean_interval(base)), 2.0)


class TestPreviouslyDroppedDirections(unittest.TestCase):
    """rising / peak near the end / intense second half / hook / rhythmic never reached the generator.

    The three shape directions are measured style by style -- the same melody style with and without the
    direction -- because the directions also reorder which styles are offered, and comparing a climbing style
    against a descending one would measure the reordering instead of the shape.
    """

    STYLES = (
        "direct_line", "question_answer", "offbeat_accent", "expressive_arch",
        "groove_pocket", "forward_climb", "sighing_descent", "motif_hook",
    )

    def _engine(self, cid: str, text: str, prog: str = "C Am F G") -> list[int]:
        from composition_melody_engine import build_concept_events
        from composition_melody_suggestions import _intent_flags, _intent_from_flags

        intent = _intent_from_flags(_intent_flags(text, ""), {})
        events = build_concept_events(
            cid, prog.split(), key="C", meter="4/4", style="simple", feel="lyrical", intent=intent,
            range_midi=RANGE,
        )
        return [_event_midi(e) for e in events if not e.get("is_rest")]

    def _halves(self, ms: list[int]) -> tuple[float, float]:
        half = len(ms) // 2
        return _mean(ms[:half]), _mean(ms[half:])

    def test_rising_ends_higher_than_it_starts(self) -> None:
        for cid in self.STYLES:
            with self.subTest(cid=cid):
                base_a, base_b = self._halves(self._engine(cid, ""))
                ask_a, ask_b = self._halves(self._engine(cid, "rising line that builds up"))
                self.assertGreater(ask_b - ask_a, base_b - base_a)

    def test_peak_near_the_end_puts_the_top_note_late(self) -> None:
        # "Sighing descent" is a falling gesture by definition; its own contour drops 11 semitones across the
        # phrase, so a late-peak direction cannot outvote it. Every other style responds.
        for cid in self.STYLES:
            if cid == "sighing_descent":
                continue
            with self.subTest(cid=cid):
                ms = self._engine(cid, "peaks near the end")
                self.assertGreaterEqual(ms.index(max(ms)) / (len(ms) - 1), 0.5)

    def test_more_intense_second_half_raises_the_second_half(self) -> None:
        # "Direct line" already climbs to the top of what its own step size allows, so it is the one style that
        # cannot lift its second half further; the other seven do.
        lifted = 0
        for cid in self.STYLES:
            _, base_b = self._halves(self._engine(cid, ""))
            _, ask_b = self._halves(self._engine(cid, "more intense second half"))
            if ask_b > base_b + 1.0:
                lifted += 1
        self.assertGreaterEqual(lifted, len(self.STYLES) - 1)

    def test_each_shape_direction_changes_what_the_user_is_offered(self) -> None:
        plain = [(c["id"], _notes(c)) for c in _ask("C Am F G")]
        for text in ("rising line that builds up", "peaks near the end", "more intense second half",
                     "a memorable hook that repeats", "rhythmic and syncopated"):
            with self.subTest(text=text):
                self.assertNotEqual([(c["id"], _notes(c)) for c in _ask("C Am F G", text)], plain)

    def test_a_hook_brings_the_motif_style_first(self) -> None:
        ids = [c["id"] for c in _ask("C Am F G", "a memorable hook that repeats")]
        self.assertIn("motif_hook", ids)
        self.assertEqual(ids[0], "motif_hook")

    def test_rhythmic_offers_a_groove_style_with_an_off_beat_onset(self) -> None:
        cands = _ask("C Am F G", "rhythmic and syncopated")
        ids = [c["id"] for c in cands]
        self.assertTrue({"groove_pocket", "offbeat_accent"} & set(ids), ids)
        offbeat = [
            c
            for c in cands
            if any(abs(float(e.get("beat") or 0.0) % 1.0) > 1e-6 for e in c.get("events") or [])
        ]
        self.assertTrue(offbeat, "no candidate starts a note off the beat")

    def test_the_four_directions_that_already_worked_still_do(self) -> None:
        held = _ask("C Am F G", "hold the last note")
        self.assertTrue(held)
        for c in held:
            evs = [e for e in c.get("events") or [] if not e.get("is_rest")]
            self.assertGreaterEqual(float(evs[-1].get("duration_beats") or 0), 2.0)
        narrow = _all_notes(_ask("C Am F G", "comfortable and singable"))
        self.assertTrue(min(narrow) >= 60 and max(narrow) <= 76, (min(narrow), max(narrow)))
        spaced = _ask("C Am F G", "leave a little space")
        self.assertTrue(
            any(
                any(e.get("is_rest") or str(e.get("pitch") or "").lower() == "rest" for e in c.get("events") or [])
                for c in spaced
            )
        )


class TestNoDirectionIsUnchanged(unittest.TestCase):
    """375 cases (5 progressions x 5 feels x 3 styles x the 5 pre-existing direction sets) were compared
    event for event against the implementation before this change: all identical. These pin the result."""

    PINNED = [
        ("question_answer", [60, 57, 55, 57, 60, 62, 64, 65, 62, 60, 62, 59, 57, 55]),
        ("direct_line", [60, 62, 64, 62, 60, 62, 64, 62, 65, 67, 69, 67, 71, 69, 67]),
        ("sighing_descent", [67, 65, 64, 62, 60, 62, 64, 62, 60, 59, 57, 55, 59, 57, 55]),
    ]

    def test_no_direction_returns_the_same_styles_and_pitches(self) -> None:
        self.assertEqual([(c["id"], _notes(c)) for c in _ask("C Am F G")], self.PINNED)

    def test_empty_directions_are_deterministic(self) -> None:
        a = _ask("C F G C")
        b = _ask("C F G C")
        self.assertEqual([(c["id"], _notes(c)) for c in a], [(c["id"], _notes(c)) for c in b])

    def test_an_unrecognised_sentence_changes_nothing(self) -> None:
        plain = [(c["id"], _notes(c)) for c in _ask("C Am F G")]
        odd = [(c["id"], _notes(c)) for c in _ask("C Am F G", "something about the weather on tuesday")]
        self.assertEqual(plain, odd)


class TestInvariants(unittest.TestCase):
    DIRECTIONS = (
        "",
        "high register with larger leaps",
        "smooth, stepwise melody in a low register",
        "rising line that builds up",
        "peaks near the end",
        "more intense second half",
        "a memorable hook that repeats",
        "rhythmic and syncopated",
        "hold the last note",
        "comfortable and singable",
    )

    def test_every_note_stays_inside_the_instrument_range(self) -> None:
        for rng in ((55, 79), (60, 72), (48, 60), (72, 84)):
            for text in self.DIRECTIONS:
                with self.subTest(rng=rng, text=text):
                    notes = _all_notes(_ask("C Am F G", text, rng=rng))
                    self.assertTrue(notes)
                    self.assertGreaterEqual(min(notes), rng[0])
                    self.assertLessEqual(max(notes), rng[1])

    def test_harmony_rules_still_hold(self) -> None:
        chords = ["C", "Am", "F", "G"]
        for text in self.DIRECTIONS:
            for c in _ask("C Am F G", text):
                with self.subTest(text=text, cid=c["id"]):
                    rows = audit_melody(list(c.get("events") or []), chords, key="C", meter="4/4")
                    self.assertEqual(audit_violations(rows), [])

    def test_first_and_last_notes_are_chord_tones(self) -> None:
        from composition_melody_audit import LABEL_CHORD_TONE, LABEL_REST

        for text in self.DIRECTIONS:
            for c in _ask("C Am F G", text):
                rows = [
                    r
                    for r in audit_melody(list(c.get("events") or []), ["C", "Am", "F", "G"], key="C")
                    if r["label"] != LABEL_REST
                ]
                with self.subTest(text=text, cid=c["id"]):
                    self.assertEqual(rows[0]["label"], LABEL_CHORD_TONE)
                    self.assertEqual(rows[-1]["label"], LABEL_CHORD_TONE)

    def test_the_phrase_length_does_not_change_with_directions(self) -> None:
        def span(cands):
            return sorted(
                round(sum(float(e.get("duration_beats") or 0) for e in c.get("events") or []), 3) for c in cands
            )

        base = span(_ask("C Am F G"))
        for text in self.DIRECTIONS[1:]:
            with self.subTest(text=text):
                self.assertEqual(span(_ask("C Am F G", text)), base)

    def test_asking_for_suggestions_never_touches_the_song(self) -> None:
        doc, sec = _doc("C Am F G")
        before = copy.deepcopy(doc)
        for text in self.DIRECTIONS:
            suggest_melody_concepts(doc, sec, "lyrical", "simple", limit=3, remember=text, range_midi=RANGE)
        self.assertEqual(doc, before)  # no accepted melody, no saved section, nothing to re-save


class TestContradictions(unittest.TestCase):
    def test_both_registers_at_once_behaves_like_neither(self) -> None:
        plain = [(c["id"], _notes(c)) for c in _ask("C Am F G")]
        both = [(c["id"], _notes(c)) for c in _ask("C Am F G", "high register but also a low register")]
        self.assertEqual(plain, both)

    def test_smooth_and_leaping_at_once_behaves_like_neither(self) -> None:
        plain = [(c["id"], _notes(c)) for c in _ask("C Am F G")]
        both = [(c["id"], _notes(c)) for c in _ask("C Am F G", "smooth stepwise line with larger leaps")]
        self.assertEqual(plain, both)

    def test_an_impossible_register_request_stays_in_range(self) -> None:
        """A one-octave window with "sing high" cannot go above the window."""
        notes = _all_notes(_ask("C Am F G", "sing high in the upper range", rng=(60, 72)))
        self.assertTrue(notes)
        self.assertLessEqual(max(notes), 72)
        self.assertGreaterEqual(min(notes), 60)

    def test_high_register_with_a_comfortable_range_respects_the_narrower_window(self) -> None:
        notes = _all_notes(_ask("C Am F G", "sing high but comfortable and singable"))
        self.assertLessEqual(max(notes), 76)
        self.assertGreaterEqual(min(notes), 60)


if __name__ == "__main__":
    unittest.main()
