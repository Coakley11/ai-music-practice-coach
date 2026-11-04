"""Song-Aware Coaching S4 — generated example phrases (pure: generation, validation, projection, state).

Musical checks use an *independent* oracle: each note's chord is found from its onset time
against the scope's harmony events (not from the generator's own chord timeline), and judged
with the coaching chord reader.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import unittest
from fractions import Fraction
from functools import lru_cache
from song_coach_context import SOURCE_COMPOSITION, build_song_coach_context
from song_coach_examples import (
    DENSITY_CAP,
    EXAMPLE_VERSION,
    EXPAND_DENSITY_CAP,
    LIMIT_EXPAND_RANGE,
    LIMIT_UNAVAILABLE,
    SAX_OCTAVE_NOTE,
    SAX_WRITTEN_RANGE,
    breathless_bars,
    note_density,
    with_breaths,
    written_semitones,
    LIMIT_PICKUP,
    LIMIT_TIMING,
    LIMIT_VAMP,
    build_example,
    continuity,
    example_seed_value,
    segment_notation,
    seed_motif,
    validate_motif,
)
from song_coach_harmony import HOLDABLE, chord_facts, note_use
from song_coach_plan import (
    BEGINNER_JARGON,
    FOCUS_CHORD_TONE,
    FOCUS_LABELS,
    FOCUS_MELODIC,
    FOCUS_MOTIF,
    FOCUS_RHYTHMIC,
    FORBIDDEN_CLAIMS,
    build_coaching_plan,
)
from song_coach_scope import build_scope
from song_coach_state import (
    EXAMPLE_CACHE_KEY,
    NOTICE_CHART_CHANGED,
    SONG_COACH_STATE_KEY,
    CoachState,
    Selection,
    build_plan_for,
    example_for,
    reconcile,
    with_built_plan,
    with_example,
    with_new_example_idea,
)
from tests.abc_pitch_decoder import abc_bar_totals, bar_chord_symbols, decode_abc_midis
from tests.test_song_coach_plan import CASES, _case

LEVELS = ("Beginner", "Intermediate", "Advanced")
SONGS = ("perfect", "ipanema", "hotel", "autumn", "blues", "composition")
SAVE_REQUESTS: list[str] = []
_SAVE_PATCH = None


def setUpModule() -> None:
    """Never write a workspace to disk from unit tests: record the save request instead."""
    global _SAVE_PATCH
    from unittest import mock

    _SAVE_PATCH = mock.patch(
        "creative_context_snapshot_persistence.request_context_cloud_save",
        side_effect=lambda session, *, save_reason: SAVE_REQUESTS.append(save_reason) or True,
    )
    _SAVE_PATCH.start()


def tearDownModule() -> None:
    if _SAVE_PATCH is not None:
        _SAVE_PATCH.stop()


# --------------------------------------------------------------------------- fixtures


def _composition_ctx():
    """The real Composition source's starter ("My Composition", C Am F G), read by the S1 adapter."""
    from composition_document import new_composition_document
    from song_coach_context import composition_reference_chart

    doc = new_composition_document(title="My Composition")
    doc["global"]["original_key_center"] = "C"
    first = doc["form"]["section_order"][0]
    doc["form"]["sections"][first]["chords"] = [{"chord": c, "bars": 1} for c in ("C", "Am", "F", "G", "C", "Am", "F", "G")]
    reference, key, record = composition_reference_chart(doc)
    return build_song_coach_context(
        identity=f"composition|composition::{doc['id']}", source_kind=SOURCE_COMPOSITION, concert_sections=reference,
        concert_key=key, record=record, style="pop", instrument="Piano", meter="4/4",
    )


@lru_cache(maxsize=None)
def _scope(name: str):
    if name == "composition":
        from song_coach_scope import coach_sections

        ctx = _composition_ctx()
        return ctx, build_scope(ctx, coach_sections(ctx)[0].section_id)
    return _case(name)


@lru_cache(maxsize=None)
def _plan(name: str, level: str = "Intermediate", focus: str = FOCUS_MOTIF, instrument: str = ""):
    ctx, scope = _scope(name)
    return build_coaching_plan(ctx, scope, level=level, focus=focus, instrument=instrument or None)


@lru_cache(maxsize=None)
def _examples(name: str, level: str = "Intermediate", focus: str = FOCUS_MOTIF, nonce: int = 0):
    plan = _plan(name, level, focus)
    _ctx, scope = _scope(name)
    return tuple(build_example(plan, scope, i, nonce=nonce) for i in range(len(plan.challenges)))


def _kind(name: str, kind: str, **kw):
    plan = _plan(name, kw.get("level", "Intermediate"), kw.get("focus", FOCUS_MOTIF))
    exs = _examples(name, kw.get("level", "Intermediate"), kw.get("focus", FOCUS_MOTIF))
    return next(((plan.challenges[i], ex) for i, ex in enumerate(exs) if ex.kind == kind), (None, None))


def _quarters_per_bar(meter: str) -> Fraction:
    num, den = meter.split("/")
    return Fraction(int(num) * 4, int(den))


def _link_for(scope, seg):
    return next(l for l in scope.chain if (l.start_bar, l.end_bar, tuple(l.chords)) == (seg.start_bar, seg.end_bar, seg.chords))


def _oracle(scope, seg, meter: str, key: str, style: str) -> list[str]:
    """Independent note check: chord at each note's onset from the scope's harmony events."""
    link = _link_for(scope, seg)
    evs = scope.events[link.first_event: link.last_event + 1]
    origin = Fraction(evs[0].start_beat).limit_denominator(64)
    bpb = Fraction(scope.beats_per_bar).limit_denominator(64)
    window_bars = link.end_bar - link.start_bar + 1
    qpb = _quarters_per_bar(meter)
    regions = [((Fraction(e.start_beat).limit_denominator(64) - origin) / bpb,
                (Fraction(e.start_beat + e.beats).limit_denominator(64) - origin) / bpb, e.chord) for e in evs]
    t = Fraction(0)
    notes = []  # (bar position within the window, chord, midi)
    midis = [int(m) for m in seg.motif["midi"]]
    for ev in seg.motif["rhythm_events"]:
        if not ev.get("rest"):
            pos = (t / qpb) % window_bars
            chord = next(c for a, b, c in regions if a <= pos < b)
            notes.append((pos, chord, midis[len(notes)]))
        t += Fraction(str(ev["dur"]))
    problems = []
    assert len(notes) == len(midis), "every pitch has a rhythm event"
    for i, (pos, chord, m) in enumerate(notes):
        use = note_use(chord_facts(chord), m % 12, key=key, style=style)
        arrival = i == 0 or notes[i - 1][1] != chord
        strong = pos.denominator == 1 or arrival or i == len(notes) - 1
        if use.category in HOLDABLE:
            continue
        if strong:
            problems.append(f"note {i} ({m}) is {use.category} on a strong point over {chord}")
        elif i + 1 >= len(notes) or abs(notes[i + 1][2] - m) > 2:
            problems.append(f"note {i} ({m}) {use.category} over {chord} does not step on")
    return problems


# --------------------------------------------------------------------------- notes against chords


class TestNotesFitTheChanges(unittest.TestCase):
    def test_every_example_note_fits_its_chord_by_an_independent_check(self) -> None:
        checked = 0
        for name in SONGS:
            ctx, scope = _scope(name)
            for level in LEVELS:
                for focus in FOCUS_LABELS:
                    plan = _plan(name, level, focus)
                    for ex in _examples(name, level, focus):
                        for seg in ex.segments:
                            if seg.label == "Developed" and len(seg.motif["chord_timeline"]) > len(seg.chords):
                                pass  # an extended development plays the window twice: the oracle wraps
                            with self.subTest(song=name, level=level, focus=focus, kind=ex.kind, seg=seg.label):
                                self.assertEqual(_oracle(scope, seg, plan.meter, plan.key, plan.style), [])
                                checked += 1
        self.assertGreater(checked, 300)

    def test_spelling_and_pitch_agree(self) -> None:
        from song_coach_harmony import pc_of

        for name in ("perfect", "ipanema", "hotel"):
            for ex in _examples(name):
                for seg in ex.segments:
                    for n, m in zip(seg.motif["notes"], seg.motif["midi"]):
                        self.assertEqual(pc_of(n), int(m) % 12, (name, ex.kind, n, m))

    def test_validator_rejects_a_wrong_note_and_a_wrong_chord_window(self) -> None:
        plan = _plan("perfect")
        _ctx, scope = _scope("perfect")
        seed, link, _ = seed_motif(plan, scope, nonce=0, instrument=plan.instrument)
        self.assertEqual(validate_motif(seed, link, key=plan.key, style=plan.style), [])
        bad = copy.deepcopy(seed)
        first_em = int(bad["chord_timeline"][1]["first_note"])  # the note that lands on Em7
        bad["midi"][first_em] = 61  # C# lands on Em7: not holdable
        bad["notes"][first_em] = "C#"
        self.assertTrue(validate_motif(bad, link, key=plan.key, style=plan.style))
        self.assertTrue(validate_motif(seed, scope.chain[1], key=plan.key, style=plan.style))

    def test_the_special_moment_features_its_outside_note(self) -> None:
        for level in LEVELS:
            ch, ex = _kind("ipanema", "moment", level=level, focus=FOCUS_MELODIC)
            self.assertIsNotNone(ex)
            if not ex.available:
                continue
            target = ch.targets[0]
            seg = ex.segments[0]
            ctx, scope = _scope("ipanema")
            link = _link_for(scope, seg)
            slot = next(t for t in seg.motif["chord_timeline"] if t["chord"] == target.chord)
            sounding = [int(m) % 12 for m in seg.motif["midi"][slot["first_note"]: slot["last_note"] + 1]]
            self.assertIn(target.pc, sounding, level)
            self.assertIn(target.chord, link.chords)

    def test_repeated_sequences_with_different_lengths_stay_consistent(self) -> None:
        """C7–F7 twice with different lengths (1+1 bars, then 2+4): span bars, example timing,
        practice bars and the coaching text's bar numbers all follow the chart."""
        from song_coach_context import SOURCE_CUSTOM

        sections = {"Blues": ["C7", "F7", "C7", "C7", "F7", "F7", "F7", "F7", "G7", "F7", "C7", "G7"]}
        ctx = build_song_coach_context(identity="custom|custom::repeat", source_kind=SOURCE_CUSTOM,
                                       concert_sections=sections, concert_key="C", style="blues", meter="4/4",
                                       instrument="Piano")
        scope = build_scope(ctx, "blues")
        bpb = scope.beats_per_bar
        windows = [l for l in scope.chain if l.chords == ("C7", "F7")]
        self.assertEqual(len(windows), 2)
        lengths = []
        for link in scope.chain:
            evs = scope.events[link.first_event: link.last_event + 1]
            own = [int(round(e.beats / bpb)) for e in evs]
            if link.span is not None:
                self.assertEqual([e.bars for e in link.span.raw_events], own, link)
            if link.chords == ("C7", "F7"):
                lengths.append(own)
        self.assertEqual(lengths, [[1, 1], [2, 4]])
        for level in LEVELS:
            plan = build_coaching_plan(ctx, scope, level=level, focus=FOCUS_MOTIF)
            for i, ch in enumerate(plan.challenges):
                self.assertTrue(scope.start_bar <= ch.loop_start <= ch.loop_end <= scope.end_bar)
                ex = build_example(plan, scope, i)
                for seg in ex.segments:
                    link = _link_for(scope, seg)
                    evs = scope.events[link.first_event: link.last_event + 1]
                    own = [int(round(e.beats / bpb)) for e in evs]
                    timeline = [t["bars"] for t in seg.motif["chord_timeline"]]
                    if seg.label in ("Developed",) and len(timeline) > len(own):
                        own = own * (len(timeline) // len(own))
                    self.assertEqual(timeline, own, (level, ch.kind, seg.label))
                    self.assertEqual(_oracle(scope, seg, plan.meter, plan.key, plan.style), [])
            starts = {(e.chord, e.start_bar) for e in scope.events}
            for line in plan.all_lines():
                for claim in line.claims:
                    if claim.kind == "change_at":
                        self.assertIn((claim.other_chord, claim.number), starts, line.render())
            for row in plan.roadmap:
                in_rows = {e.chord for e in scope.events if row.start_bar <= e.start_bar <= row.end_bar}
                self.assertTrue(set(row.chords) <= in_rows | {e.chord for e in scope.events}, row)

    def test_repeated_progressions_keep_their_own_bar_lengths(self) -> None:
        """S1 fix: MC1 analyses a chord sequence once; the 2nd C7–F7 of a blues lasts 4 bars."""
        _ctx, scope = _scope("blues")
        for link in scope.chain:
            if link.span is None:
                continue
            bars = [e.bars for e in link.span.raw_events]
            self.assertEqual(sum(bars), link.end_bar - link.start_bar + 1, link)
            self.assertEqual(tuple(link.span.chords), link.chords)
        ids = [l.span.span_id for l in scope.chain if l.span is not None]
        self.assertEqual(len(ids), len(set(ids)))


# --------------------------------------------------------------------------- one idea, developed


def _onsets(motif) -> list[str]:
    return [e["on"] for e in motif["rhythm_events"] if not e.get("rest")]


def _assert_development(case, ex) -> None:
    """Each Expand development keeps the idea recognisable in its own, measurable way."""
    carried, developed = ex.segments[0].motif, ex.segments[1].motif
    a, b = [int(m) for m in carried["midi"]], [int(m) for m in developed["midi"]]
    kind = ex.continuity["development"]
    if kind == "filled":  # MC2 one-pass development: the idea's notes, in order, plus new ones
        kept = [m for m, o in zip(b, developed["seed_note_origin"]) if o is not None]
        case.assertEqual(kept[: len(a)], a, "development keeps the idea's notes in order")
        case.assertGreater(len(b), len(a))
    elif kind == "answer":  # call and answer: the idea's opening states the call, then a second pass
        opening = int(carried["chord_timeline"][0]["last_note"]) + 1
        kept = [m for m, o in zip(b, developed["seed_note_origin"]) if o is not None]
        case.assertEqual(kept[:opening], a[:opening], "the call opens with the idea")
        case.assertEqual(len(developed["chord_timeline"]), 2 * len(carried["chord_timeline"]))
    elif kind == "higher":  # same rhythm, new notes, higher high point
        case.assertEqual(_onsets(developed), _onsets(carried))
        case.assertEqual(developed["span_seed"]["rhythm_cell"], carried["span_seed"]["rhythm_cell"])
        case.assertGreater(max(b), max(a))
    else:  # sequence / climb / descend / register: every note moves the same way, same rhythm
        case.assertEqual(_onsets(developed), _onsets(carried))
        moves = [y - x for x, y in zip(a, b)]
        case.assertEqual(len(a), len(b))
        if kind == "descend":
            case.assertTrue(all(m < 0 for m in moves), moves)
        elif kind == "register":
            case.assertIn(set(moves), ({12}, {-12}))
        else:
            case.assertTrue(all(m > 0 for m in moves), moves)


class TestMotifIdentity(unittest.TestCase):
    def test_idea_rhythm_connect_expand_grow_one_seed(self) -> None:
        for name in ("perfect", "ipanema", "hotel", "autumn", "blues", "composition"):
            plan = _plan(name, "Intermediate", FOCUS_RHYTHMIC)
            _ctx, scope = _scope(name)
            seed, seed_link, _ = seed_motif(plan, scope, nonce=0, instrument=plan.instrument)
            exs = _examples(name, "Intermediate", FOCUS_RHYTHMIC)
            by_kind = {}
            for ex in exs:
                by_kind.setdefault(ex.kind, ex)
            with self.subTest(song=name):
                idea = by_kind["idea"].segments[0].motif
                self.assertEqual(idea["midi"], seed["midi"])
                rhythm = by_kind["rhythm"]
                self.assertTrue(rhythm.available)
                varied = rhythm.segments[1].motif
                self.assertEqual(varied["midi"], seed["midi"], "Rhythm keeps the pitches")
                self.assertNotEqual(_onsets(varied), _onsets(seed), "…and changes the rhythm")
                for ex in exs:
                    if ex.kind in ("connect", "expand", "roadmap") and ex.available:
                        for seg in ex.segments:
                            if seg.label == "Developed":
                                continue
                            s = seg.motif["span_seed"]
                            self.assertEqual(s["rhythm_cell"], seed["span_seed"]["rhythm_cell"], (ex.kind, seg.label))
                            self.assertEqual(s["seed"], seed["span_seed"]["seed"], (ex.kind, seg.label))
                expand = by_kind.get("expand")
                if expand is not None and expand.available:
                    _assert_development(self, expand)

    def test_connect_carries_into_the_next_window(self) -> None:
        _ch, ex = next((c, e) for c, e in zip(_plan("perfect").challenges, _examples("perfect"))
                       if e.kind == "connect" and e.segments and e.segments[0].start_bar == 5)
        self.assertTrue(ex.continuity["same_rhythm_cell"])
        self.assertEqual(ex.segments[0].chords, ("Cadd9", "D/F#"))

    def test_roadmap_travels_window_by_window(self) -> None:
        for name, windows in (("perfect", 2), ("ipanema", 2), ("autumn", 3), ("blues", 4)):
            _ch, ex = _kind(name, "roadmap")
            self.assertTrue(ex.available, name)
            self.assertEqual(len(ex.segments), windows, name)
            self.assertTrue(ex.continuity["same_rhythm_cell"], name)
            starts = [s.start_bar for s in ex.segments]
            self.assertEqual(starts, sorted(starts))
            self.assertIn("practice sketch", ex.caption)


# --------------------------------------------------------------------------- deterministic, stable identity


class TestDeterminism(unittest.TestCase):
    def _phrases(self, exs):
        return [[(s.motif["midi"], s.motif["rhythm_events"]) for s in ex.segments] for ex in exs]

    def test_same_inputs_same_examples(self) -> None:
        for name in ("perfect", "hotel"):
            plan = _plan(name)
            _ctx, scope = _scope(name)
            again = [build_example(plan, scope, i) for i in range(len(plan.challenges))]
            self.assertEqual(self._phrases(again), self._phrases(_examples(name)))

    def test_seed_value_is_stable(self) -> None:
        self.assertEqual(example_seed_value("abc", 0), example_seed_value("abc", 0))
        self.assertNotEqual(example_seed_value("abc", 0), example_seed_value("abc", 1))
        self.assertNotEqual(example_seed_value("abc", 0), example_seed_value("abd", 0))
        self.assertEqual(EXAMPLE_VERSION, "s4.2")

    def test_a_new_idea_changes_every_example_together(self) -> None:
        first, second = _examples("perfect", nonce=0), _examples("perfect", nonce=1)
        self.assertNotEqual(first[0].segments[0].motif["midi"], second[0].segments[0].motif["midi"])
        seed2 = second[0].segments[0].motif
        for ex in second:
            for seg in ex.segments:
                if seg.label != "Developed":
                    self.assertEqual(seg.motif["span_seed"]["seed"], seed2["span_seed"]["seed"])

    def test_instrument_change_keeps_the_example(self) -> None:
        """The UI seeds from the stored plan id and built instrument, never the live ones."""
        sax, piano = _plan("perfect", instrument="Saxophone"), _plan("perfect", instrument="Piano")
        _ctx, scope = _scope("perfect")
        self.assertNotEqual(sax.plan_id, piano.plan_id, "the live plan's id follows the instrument family")
        a = build_example(sax, scope, 0, instrument="Saxophone", plan_key=sax.plan_id)
        b = build_example(piano, scope, 0, instrument="Saxophone", plan_key=sax.plan_id)
        self.assertEqual(a.segments[0].motif["midi"], b.segments[0].motif["midi"])


# --------------------------------------------------------------------------- levels


class TestLevels(unittest.TestCase):
    def test_beginner_rhythms_are_plain(self) -> None:
        for name in SONGS:
            for focus in FOCUS_LABELS:
                plan = _plan(name, "Beginner", focus)
                _ctx, scope = _scope(name)
                seed, _l, _ = seed_motif(plan, scope, nonce=0, instrument=plan.instrument)
                cells = seed["span_seed"]["rhythm_cell"]
                with self.subTest(song=name, focus=focus):
                    self.assertFalse(any(c.startswith(("trip", "e_q_e", "e_qd")) for c in cells), cells)
                    self.assertFalse(any(e.get("tup") or e.get("ts") for e in seed["rhythm_events"]))

    def test_beginner_never_has_shorter_notes_than_advanced(self) -> None:
        for name in SONGS:
            for focus in FOCUS_LABELS:
                shortest = {}
                for level in ("Beginner", "Advanced"):
                    plan = _plan(name, level, focus)
                    _ctx, scope = _scope(name)
                    seed, _l, _ = seed_motif(plan, scope, nonce=0, instrument=plan.instrument)
                    shortest[level] = min(Fraction(str(e["dur"])) for e in seed["rhythm_events"] if not e.get("rest"))
                self.assertGreaterEqual(shortest["Beginner"], shortest["Advanced"], (name, focus))

    def test_expand_develops_the_idea_at_every_level(self) -> None:
        kinds = {level: set() for level in LEVELS}
        for name in SONGS:
            for focus in FOCUS_LABELS:
                for level in LEVELS:
                    _ch, ex = _kind(name, "expand", level=level, focus=focus)
                    if ex is None or not ex.available:
                        continue
                    kind = ex.continuity["development"]
                    kinds[level].add(kind)
                    with self.subTest(song=name, focus=focus, level=level):
                        _assert_development(self, ex)
                        self.assertLessEqual(note_density(ex.segments[1].motif), EXPAND_DENSITY_CAP[level])
                        if level != "Advanced":
                            self.assertNotEqual(kind, "answer", "call and answer is the Advanced development")
                        if focus == FOCUS_MELODIC:  # the challenge asks for a higher point
                            self.assertNotEqual(kind, "descend")
                            self.assertGreater(max(ex.segments[1].motif["midi"]), max(ex.segments[0].motif["midi"]))
                        if kind == "filled":  # never "just more notes"
                            self.assertGreater(max(ex.segments[1].motif["midi"]), max(ex.segments[0].motif["midi"]))
        self.assertIn("answer", kinds["Advanced"])
        self.assertIn("higher", kinds["Beginner"])

    def test_examples_get_busier_with_level(self) -> None:
        mean = {}
        for level in LEVELS:
            values = [note_density(seed_motif(_plan(n, level, f), _scope(n)[1], nonce=0, instrument="Piano")[0])
                      for n in SONGS for f in FOCUS_LABELS]
            mean[level] = sum(values) / len(values)
        self.assertLess(mean["Beginner"], mean["Intermediate"])
        self.assertLess(mean["Intermediate"], mean["Advanced"])

    def test_beginner_wording_has_no_jargon(self) -> None:
        for name in SONGS:
            for focus in FOCUS_LABELS:
                for ex in _examples(name, "Beginner", focus):
                    self.assertIsNone(BEGINNER_JARGON.search(ex.caption + " " + ex.limitation), (name, ex.caption))


# --------------------------------------------------------------------------- notation and instruments


INSTRUMENTS = (  # (instrument, transposing type, written key at concert G, true written interval)
    ("Saxophone", "Alto saxophone (Eb)", "E", 9),
    ("Saxophone", "Tenor saxophone (Bb)", "A", 14),
    ("Saxophone", "Baritone saxophone (Eb)", "E", 21),
    ("Trumpet", "Bb Trumpet", "A", 2),
    ("Clarinet", "Bb Clarinet", "A", 2),
    ("Piano", "", "G", 0),
    ("Guitar", "", "G", 0),
)


class TestNotation(unittest.TestCase):
    def _project(self, chart):
        from effective_practice_context import musician_facing_chord

        return lambda c: musician_facing_chord(c, concert_key="G", chart_key=chart)

    def test_written_interval_contract(self) -> None:
        """The shared engine's pitch-class shift, plus the octave a tenor / baritone sax reads."""
        from instrument_transposition import semitone_steps_for_label

        for _instrument, kind, chart, interval in INSTRUMENTS:
            self.assertEqual(written_semitones("G", chart, kind), interval, kind)
            if kind:
                self.assertEqual(semitone_steps_for_label(kind), interval % 12, "shared engine unchanged")
        self.assertEqual(written_semitones("G", "G", "Tenor saxophone (Bb)"), 0, "concert charts stay concert")

    def test_instrument_projection_for_display_only(self) -> None:
        from instrument_transposition import written_key_for_type

        lo, hi = SAX_WRITTEN_RANGE
        for song in ("perfect", "ipanema", "hotel"):
            plan = _plan(song)
            seg = _examples(song)[0].segments[0]
            concert = [int(m) for m in seg.motif["midi"]]
            before = copy.deepcopy(seg.motif)
            for instrument, kind, _chart, interval in INSTRUMENTS:
                chart = written_key_for_type(plan.key, kind) if kind else plan.key
                with self.subTest(song=song, instrument=kind or instrument):
                    n = segment_notation(seg, concert_key=plan.key, chart_key=chart, project_chord=None,
                                         instrument=instrument, bpm=63, title=seg.label, transposing_type=kind)
                    expected = interval
                    if "saxophone" in kind.lower():
                        while max(concert) + expected > hi and min(concert) + expected - 12 >= lo:
                            expected -= 12
                    self.assertEqual(n.shift, expected)
                    self.assertEqual(bool(n.note), expected != interval)
                    if n.note:
                        self.assertEqual(n.note, SAX_OCTAVE_NOTE)
                    self.assertEqual(decode_abc_midis(n.abc), [m + expected for m in concert])
                    self.assertIn(f"K:{chart}", n.abc)
                    self.assertIn(f"M:{plan.meter}", n.abc)
                    self.assertEqual(bool(n.tab), instrument == "Guitar")
            self.assertEqual(seg.motif, before, "display projection never changes the concert example")

    def test_tenor_reads_a_major_ninth_above_concert(self) -> None:
        """Ipanema's idea sits low enough that the tenor reads it at the true written octave."""
        from effective_practice_context import musician_facing_chord

        plan = _plan("ipanema")
        seg = _examples("ipanema")[0].segments[0]
        n = segment_notation(seg, concert_key="F", chart_key="G", transposing_type="Tenor saxophone (Bb)",
                             instrument="Saxophone",
                             project_chord=lambda c: musician_facing_chord(c, concert_key="F", chart_key="G"))
        self.assertEqual(n.shift, 14)
        self.assertEqual(decode_abc_midis(n.abc), [int(m) + 14 for m in seg.motif["midi"]])
        self.assertEqual(n.chords, ("Gmaj7", "A7"))
        self.assertEqual(plan.key, "F")

    def test_bars_add_up_in_every_meter(self) -> None:
        for name, bar in (("perfect", Fraction(3)), ("ipanema", Fraction(4)), ("hotel", Fraction(4)), ("composition", Fraction(4))):
            plan = _plan(name)
            for ex in _examples(name):
                for seg in ex.segments:
                    n = segment_notation(seg, concert_key=plan.key, instrument="Piano")
                    with self.subTest(song=name, kind=ex.kind, seg=seg.label):
                        self.assertIn(f"M:{plan.meter}", n.abc)
                        totals = abc_bar_totals(n.abc)
                        self.assertTrue(totals and all(t == bar for t in totals), totals)
                        bars = len(seg.motif["chord_timeline"]) and sum(t["bars"] for t in seg.motif["chord_timeline"])
                        self.assertEqual(len(totals), bars)
                        self.assertEqual(decode_abc_midis(n.abc), [int(m) for m in seg.motif["midi"]])


# --------------------------------------------------------------------------- phrasing and reliability


class TestPhrasing(unittest.TestCase):
    def test_every_example_leaves_room_to_breathe(self) -> None:
        for name in SONGS:
            for level in LEVELS:
                for focus in FOCUS_LABELS:
                    for ex in _examples(name, level, focus):
                        for seg in ex.segments:
                            with self.subTest(song=name, level=level, focus=focus, kind=ex.kind, seg=seg.label):
                                self.assertLessEqual(breathless_bars(seg.motif), Fraction(5, 2))

    def test_beginner_phrases_are_short_and_calm(self) -> None:
        within = total = 0
        for name in SONGS:
            for focus in FOCUS_LABELS:
                for ex in _examples(name, "Beginner", focus):
                    for seg in ex.segments:
                        d = note_density(seg.motif)
                        self.assertLessEqual(d, Fraction(1), (name, focus, ex.kind, seg.label))
                        total += 1
                        within += d <= DENSITY_CAP["Beginner"] * Fraction(5, 4)
        self.assertGreaterEqual(within / total, 0.9)

    def test_breaths_change_only_note_lengths(self) -> None:
        plan = _plan("hotel", "Beginner", FOCUS_MELODIC)
        _ctx, scope = _scope("hotel")
        seed, link, _ = seed_motif(plan, scope, nonce=0, instrument=plan.instrument)
        phrased = with_breaths(seed)
        rests = [e for e in phrased["rhythm_events"] if e.get("rest")]
        self.assertTrue(rests, "an 8-bar idea gets breaths")
        self.assertEqual(_onsets(phrased), _onsets(seed))
        self.assertEqual(phrased["midi"], seed["midi"])
        total = lambda m: sum(Fraction(str(e["dur"])) for e in m["rhythm_events"])  # noqa: E731
        self.assertEqual(total(phrased), total(seed))
        self.assertEqual(phrased["rhythm_events"][-1], seed["rhythm_events"][-1], "the final note is never cut")
        self.assertEqual(validate_motif(phrased, link, key=plan.key, style=plan.style), [])
        self.assertLessEqual(breathless_bars(phrased), breathless_bars(seed))
        self.assertEqual(seed, seed_motif(plan, scope, nonce=0, instrument=plan.instrument)[0], "input untouched")

    def test_rhythm_examples_keep_the_melody(self) -> None:
        for name in SONGS:
            for level in LEVELS:
                _ch, ex = _kind(name, "rhythm", level=level, focus=FOCUS_RHYTHMIC)
                if ex is None or not ex.available:
                    continue
                first, second = ex.segments[0].motif, ex.segments[1].motif
                self.assertEqual(first["midi"], second["midi"], (name, level))
                self.assertNotEqual(_onsets(first), _onsets(second), (name, level))

    def test_failure_rate_and_honest_limitations(self) -> None:
        failed = total = 0
        for name in SONGS:
            for level in LEVELS:
                for focus in FOCUS_LABELS:
                    for ex in _examples(name, level, focus):
                        total += 1
                        if not ex.available:
                            failed += 1
                            self.assertIn(ex.limitation, (LIMIT_UNAVAILABLE, LIMIT_EXPAND_RANGE), (name, level, focus, ex.kind))
        self.assertLessEqual(failed / total, 0.015, (failed, total))


# --------------------------------------------------------------------------- limitations and honesty


class TestLimitations(unittest.TestCase):
    def test_a_one_chord_vamp_says_why_there_is_no_example(self) -> None:
        for ex in _examples("vamp"):
            self.assertFalse(ex.available)
            self.assertEqual(ex.limitation, LIMIT_VAMP)

    def test_mid_bar_changes_and_pickups_are_explained_not_notated(self) -> None:
        plan = _plan("split", "Intermediate", FOCUS_MOTIF)
        exs = _examples("split", "Intermediate", FOCUS_MOTIF)
        _ctx, scope = _scope("split")
        exact = [l for l in scope.chain if l.exact_bar_timing]
        for ch, ex in zip(plan.challenges, exs):
            for seg in ex.segments:
                self.assertTrue(_link_for(scope, seg).exact_bar_timing, "never notates a split bar")
            if ch.kind == "connect" and not ex.available:
                self.assertEqual(ex.limitation, LIMIT_TIMING)
            if ch.kind == "moment":
                self.assertEqual(ex.limitation, LIMIT_PICKUP)
            if ch.kind == "idea":
                self.assertTrue(ex.available)
                self.assertEqual(ex.segments[0].start_bar, exact[0].start_bar)
                self.assertIn(f"bars {exact[0].start_bar}–{exact[0].end_bar}", ex.limitation)

    def test_an_anticipation_challenge_admits_the_example_lands_on_the_bar(self) -> None:
        found = 0
        for name in ("perfect", "ipanema", "autumn"):
            ch, ex = _kind(name, "expand", level="Intermediate", focus=FOCUS_RHYTHMIC)
            if ex is not None and ex.available and any(c.kind == "change_at" for ln in ch.lines for c in ln.claims):
                self.assertIn("can't show anticipations", ex.limitation)
                found += 1
        self.assertGreater(found, 0)

    def test_captions_never_claim_the_songs_melody(self) -> None:
        for name in SONGS:
            for level in LEVELS:
                for focus in FOCUS_LABELS:
                    for ex in _examples(name, level, focus):
                        text = f"{ex.caption} {ex.limitation} " + " ".join(s.label for s in ex.segments)
                        self.assertIsNone(FORBIDDEN_CLAIMS.search(text), (name, text))
                        self.assertTrue(ex.available or ex.limitation, (name, ex.kind))

    def test_expand_caption_describes_only_what_changed(self) -> None:
        for name in SONGS:
            for level in LEVELS:
                for focus in FOCUS_LABELS:
                    _ch, ex = _kind(name, "expand", level=level, focus=focus)
                    if ex is None or not ex.available:
                        continue
                    a, b = ex.segments[0].motif["midi"], ex.segments[1].motif["midi"]
                    with self.subTest(song=name, level=level, focus=focus):
                        self.assertEqual("higher" in ex.caption, max(b) > max(a), ex.caption)
                        twice = len(ex.segments[1].motif["chord_timeline"]) > len(ex.segments[0].motif["chord_timeline"])
                        self.assertEqual("plays twice" in ex.caption, twice)
                        self.assertNotIn("passing or neighbour", ex.caption)


# --------------------------------------------------------------------------- state: never stale


def _built_session(name: str = "perfect", instrument: str = "Piano"):
    ctx, _scope_ = _scope(name)
    ctx = dataclasses.replace(ctx, instrument=instrument)
    level, focus = "Intermediate", FOCUS_MOTIF
    rec = reconcile({}, ctx, level=level, focus=focus)
    plan, scope = build_plan_for(ctx, rec.state.draft)
    state = with_built_plan(rec.state, plan)
    return {SONG_COACH_STATE_KEY: state.to_dict()}, ctx, state, plan, scope


class TestExampleState(unittest.TestCase):
    def test_example_choices_round_trip_and_old_records_load(self) -> None:
        state = with_new_example_idea(with_example(with_example(CoachState(identity="x"), 2, True), 0, True))
        self.assertEqual((state.examples, state.example_nonce), ((0, 2), 1))
        raw = json.loads(json.dumps(state.to_dict()))
        self.assertEqual(CoachState.from_dict(raw), state)
        self.assertEqual(with_example(state, 2, False).examples, (0,))
        legacy = {k: v for k, v in state.to_dict().items() if k not in ("examples", "example_nonce")}
        old = CoachState.from_dict(legacy)
        self.assertEqual((old.examples, old.example_nonce), ((), 0))

    def test_rebuilding_the_plan_hides_examples_and_resets_the_idea(self) -> None:
        session, ctx, state, plan, _scope_ = _built_session()
        shown = with_new_example_idea(with_example(state, 0, True))
        rebuilt = with_built_plan(shown, plan)
        self.assertEqual((rebuilt.examples, rebuilt.example_nonce), ((), 0))

    def test_examples_survive_reruns_but_not_a_chart_or_key_change(self) -> None:
        session, ctx, state, plan, _scope_ = _built_session()
        shown = with_new_example_idea(with_example(state, 1, True))
        session[SONG_COACH_STATE_KEY] = shown.to_dict()
        rec = reconcile(session, ctx, level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual((rec.state.examples, rec.state.example_nonce), ((1,), 1))
        changed = dataclasses.replace(ctx, fingerprint="another-chart")
        rec = reconcile(session, changed, level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual(rec.notice, NOTICE_CHART_CHANGED)
        self.assertEqual((rec.state.examples, rec.state.example_nonce, rec.state.plan_id), ((), 0, ""))
        other = dataclasses.replace(ctx, identity="catalog|Other")
        rec = reconcile(session, other, level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual(rec.state.examples, ())

    def test_example_cache_follows_the_plan_and_the_built_instrument(self) -> None:
        session, ctx, state, plan, scope = _built_session(instrument="Saxophone")
        self.assertEqual(state.instrument, "Saxophone")
        shown = with_example(state, 0, True)
        first = example_for(session, shown, plan, scope, 0)
        self.assertIs(example_for(session, shown, plan, scope, 0), first, "cached for reruns")
        piano_plan, _ = build_plan_for(dataclasses.replace(ctx, instrument="Piano"), state.built)
        self.assertNotEqual(piano_plan.plan_id, plan.plan_id)
        session.pop(EXAMPLE_CACHE_KEY)
        again = example_for(session, shown, piano_plan, scope, 0)
        self.assertEqual(again.segments[0].motif["midi"], first.segments[0].motif["midi"], "same phrase after an instrument change")
        other = dataclasses.replace(shown, plan_id="another-plan")
        example_for(session, other, plan, scope, 0)
        self.assertEqual(session[EXAMPLE_CACHE_KEY]["plan_id"], "another-plan", "a new plan drops old examples")
        self.assertEqual(len([k for k in session[EXAMPLE_CACHE_KEY] if k != "plan_id"]), 1)

    def test_show_and_new_idea_are_user_actions_through_the_save_path(self) -> None:
        from song_coach_ui import on_example, on_example_new

        session, ctx, state, plan, scope = _built_session()
        SAVE_REQUESTS.clear()
        on_example(session, ctx, 1)
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]).examples, (1,))
        on_example_new(session, ctx)
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]).example_nonce, 1)
        on_example(session, ctx, 1)
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]).examples, ())
        self.assertEqual(len(SAVE_REQUESTS), 3)
        self.assertEqual(session["_song_coach_last_commit"]["interaction"], "example")


class TestCoverage(unittest.TestCase):
    def test_required_songs_and_sources_produce_examples(self) -> None:
        for name in ("perfect", "ipanema", "hotel", "blues", "composition"):
            exs = _examples(name)
            available = [ex.kind for ex in exs if ex.available]
            with self.subTest(song=name):
                self.assertIn("idea", available)
                self.assertGreaterEqual(len(available), len(exs) - 1)
        ctx, _ = _scope("composition")
        self.assertEqual(ctx.source_kind, SOURCE_COMPOSITION)
        self.assertIn("C", ctx.sections[0][1])


if __name__ == "__main__":
    unittest.main()
