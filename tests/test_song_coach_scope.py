"""Song-Aware Coaching S1 — sections, bar ranges, harmonic timeline and span chain."""

from __future__ import annotations

import copy
import unittest

from music_theory import transpose_sections_dict
from song_coach_context import SOURCE_CATALOG, SOURCE_CUSTOM, build_song_coach_context
from song_coach_scope import (
    ERROR_BAD_RANGE,
    ERROR_CONTEXT_UNAVAILABLE,
    ERROR_NO_HARMONY,
    ERROR_TOO_LONG,
    ERROR_UNKNOWN_SECTION,
    MAX_SCOPE_BARS,
    ScopeError,
    build_scope,
    coach_sections,
    find_section,
    harmony_events,
    span_chain,
    suggested_ranges,
)


def _record(title: str) -> dict:
    from song_catalog.catalog import curated_song_records

    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == title))


def _catalog(title: str, key: str | None = None):
    rec = _record(title)
    concert = key or rec["key"]
    return build_song_coach_context(
        identity=f"catalog|{title}",
        source_kind=SOURCE_CATALOG,
        concert_sections=transpose_sections_dict(rec["sections"], rec["key"], concert),
        concert_key=concert,
        section_order=rec.get("section_order"),
        record=rec,
        reference_sections=rec["sections"],
        reference_key=rec["key"],
    )


def _custom(sections: dict, key: str, meter: str = "4/4"):
    return build_song_coach_context(
        identity="custom|custom::t", source_kind=SOURCE_CUSTOM, concert_sections=sections, concert_key=key, meter=meter
    )


def _scope(sections: dict, key: str, meter: str = "4/4", **kw):
    ctx = _custom(sections, key, meter)
    return build_scope(ctx, coach_sections(ctx)[0].section_id, **kw)


def _chain(scope):
    return [(link.chords, link.start_bar, link.end_bar) for link in scope.chain]


IPANEMA_A = ["Fmaj7", "Fmaj7", "G7", "G7", "Gm7", "Gb7", "Fmaj7", "Gb7"]


class TestSections(unittest.TestCase):
    def test_perfect_groups_identical_repeats(self) -> None:
        ctx = _catalog("Perfect")
        sections = coach_sections(ctx)
        self.assertEqual([s.label for s in sections], ["Intro", "Verse", "Chorus", "Outro"])
        verse = sections[1]
        self.assertEqual(verse.names, ("Verse 1", "Verse 2", "Verse 3", "Verse 4"))
        self.assertEqual((verse.occurrences, verse.bar_count), (4, 16))
        self.assertEqual(sections[2].names, ("Chorus 1", "Chorus 2", "Chorus 3"))
        # Intro and Outro share bars but are different parts of the form.
        self.assertEqual(sections[0].bars, sections[3].bars)
        self.assertEqual(len({s.section_id for s in sections}), 4)

    def test_same_name_with_different_harmony_keeps_its_own_entry(self) -> None:
        ctx = _custom({"Verse 1": ["C", "F", "G", "C"], "Verse 2": ["Am", "F", "G", "C"], "Verse 3": ["C", "F", "G", "C"]}, "C")
        sections = coach_sections(ctx)
        self.assertEqual([s.label for s in sections], ["Verse 1", "Verse 2"])
        self.assertEqual(sections[0].names, ("Verse 1", "Verse 3"))

    def test_ids_labels_and_lengths_survive_a_practice_key_change(self) -> None:
        home = coach_sections(_catalog("Perfect"))
        moved = coach_sections(_catalog("Perfect", key="Bb"))
        self.assertEqual(
            [(s.section_id, s.label, s.names, s.bar_count) for s in home],
            [(s.section_id, s.label, s.names, s.bar_count) for s in moved],
        )
        self.assertNotEqual(home[1].bars, moved[1].bars)
        self.assertEqual(moved[1].bars[0], "Bb")

    def test_unavailable_context_has_no_sections(self) -> None:
        ctx = build_song_coach_context(identity="", source_kind=SOURCE_CATALOG, concert_sections={"A": ["C"]}, concert_key="C")
        self.assertEqual(coach_sections(ctx), [])

    def test_suggested_ranges(self) -> None:
        verse = find_section(_catalog("Perfect"), "verse-1")
        self.assertEqual(suggested_ranges(verse), [(1, 8), (9, 16)])
        self.assertEqual(suggested_ranges(verse, phrase_bars=4), [(1, 4), (5, 8), (9, 12), (13, 16)])
        intro = find_section(_catalog("Perfect"), "intro")
        self.assertEqual(suggested_ranges(intro), [(1, 7)])
        long = find_section(_custom({"Solo": ["C"] * 20}, "C"), "solo")
        self.assertEqual(suggested_ranges(long), [(1, 8), (9, 16), (17, 20)])


class TestScopeSelection(unittest.TestCase):
    def test_bar_range_inside_a_section(self) -> None:
        ctx = _catalog("Perfect", key="A")
        scope = build_scope(ctx, "verse-1", 3, 6)
        self.assertEqual(scope.bars, ("F#m7", "F#m7", "Dadd9", "Dadd9"))
        self.assertEqual((scope.start_bar, scope.end_bar, scope.bar_count, scope.section_bar_count), (3, 6, 4, 16))
        self.assertFalse(scope.whole_section)
        self.assertEqual(scope.range_label, "Verse · bars 3–6")
        self.assertEqual(scope.key_center, "A")
        self.assertEqual(scope.names, ("Verse 1", "Verse 2", "Verse 3", "Verse 4"))
        self.assertTrue(scope.scope_id.startswith(ctx.fingerprint))

    def test_whole_section_default(self) -> None:
        scope = build_scope(_catalog("Perfect"), "chorus-1")
        self.assertTrue(scope.whole_section)
        self.assertEqual((scope.start_bar, scope.end_bar), (1, 8))
        self.assertEqual(scope.range_label, "Chorus · 8 bars")

    def test_scope_id_follows_song_key_and_range(self) -> None:
        a = build_scope(_catalog("Perfect"), "verse-1", 1, 8)
        self.assertEqual(a.scope_id, build_scope(_catalog("Perfect"), "verse-1", 1, 8).scope_id)
        self.assertNotEqual(a.scope_id, build_scope(_catalog("Perfect"), "verse-1", 9, 16).scope_id)
        self.assertNotEqual(a.scope_id, build_scope(_catalog("Perfect", key="A"), "verse-1", 1, 8).scope_id)

    def test_invalid_selections(self) -> None:
        ctx = _catalog("Perfect")
        cases = [
            (("nope",), ERROR_UNKNOWN_SECTION),
            (("chorus-1", 0, 4), ERROR_BAD_RANGE),
            (("chorus-1", 5, 9), ERROR_BAD_RANGE),
            (("chorus-1", 6, 3), ERROR_BAD_RANGE),
        ]
        for args, code in cases:
            with self.assertRaises(ScopeError) as err:
                build_scope(ctx, *args)
            self.assertEqual(err.exception.code, code, args)
        long_ctx = _custom({"Solo": ["C", "F"] * 12}, "C")
        with self.assertRaises(ScopeError) as err:
            build_scope(long_ctx, "solo")
        self.assertEqual(err.exception.code, ERROR_TOO_LONG)
        self.assertEqual(build_scope(long_ctx, "solo", 1, MAX_SCOPE_BARS).bar_count, MAX_SCOPE_BARS)
        rest_ctx = _custom({"Break": ["N.C.", "N.C."], "Verse": ["C", "G"]}, "C")
        with self.assertRaises(ScopeError) as err:
            build_scope(rest_ctx, "break")
        self.assertEqual(err.exception.code, ERROR_NO_HARMONY)
        dead = build_song_coach_context(identity="", source_kind=SOURCE_CATALOG, concert_sections={}, concert_key="C")
        with self.assertRaises(ScopeError) as err:
            build_scope(dead, "verse")
        self.assertEqual(err.exception.code, ERROR_CONTEXT_UNAVAILABLE)


class TestHarmonicTimeline(unittest.TestCase):
    def test_held_chords_are_one_event_with_their_length(self) -> None:
        scope = build_scope(_catalog("Perfect"), "verse-1", 1, 8)
        self.assertEqual(
            [(e.chord, e.start_beat, e.beats, e.start_bar) for e in scope.events],
            [("G", 0.0, 8.0, 1), ("Em7", 8.0, 8.0, 3), ("Cadd9", 16.0, 8.0, 5), ("D/F#", 24.0, 8.0, 7)],
        )
        r = scope.rhythm
        self.assertEqual((r.changes, r.distinct_chords, r.beats_per_change), (4, 4, 8.0))
        self.assertFalse(r.has_split_bars or r.has_pushes or r.has_no_chord)

    def test_split_bars_pushes_hits_and_no_chord(self) -> None:
        events = harmony_events(["C:2|G:2", "Am", "Em:3.5|D:0.5p", "D", "N.C.", "G.hit", "C"])
        self.assertEqual(
            [(e.chord, e.start_beat, e.beats, e.start_bar, e.beat_in_bar, e.push, e.no_chord) for e in events],
            [
                ("C", 0.0, 2.0, 1, 0.0, False, False),
                ("G", 2.0, 2.0, 1, 2.0, False, False),
                ("Am", 4.0, 4.0, 2, 0.0, False, False),
                ("Em", 8.0, 3.5, 3, 0.0, False, False),
                ("D", 11.5, 4.5, 3, 3.5, True, False),  # the anticipation joins bar 4's D
                ("", 16.0, 4.0, 5, 0.0, False, True),
                ("G", 20.0, 4.0, 6, 0.0, False, False),
                ("C", 24.0, 4.0, 7, 0.0, False, False),
            ],
        )

    def test_meter_sets_the_beat_count(self) -> None:
        self.assertEqual([e.beats for e in harmony_events(["C", "C", "G"], meter="3/4")], [6.0, 3.0])
        self.assertEqual([e.beats for e in harmony_events(["Am", "E7"], meter="6/8")], [6.0, 6.0])
        waltz = _scope({"A": ["C", "G", "C", "G"]}, "C", meter="3/4")
        self.assertEqual(waltz.beats_per_bar, 3.0)
        self.assertEqual(waltz.rhythm.cycle, ("C", "G"))

    def test_first_bar_offsets_bar_numbers(self) -> None:
        self.assertEqual([e.start_bar for e in harmony_events(["G", "Em7"], first_bar=9)], [9, 10])


class TestSpanChain(unittest.TestCase):
    def test_ipanema_keeps_the_ii_subv_i_together(self) -> None:
        scope = _scope({"A Section": IPANEMA_A}, "F")
        self.assertEqual(_chain(scope), [(("Fmaj7", "G7"), 1, 4), (("Gm7", "Gb7", "Fmaj7"), 5, 7), (("Gb7",), 8, 8)])
        self.assertEqual(scope.chain[1].span.relationship, "ii_subV_I")
        self.assertIsNone(scope.chain[2].span)

    def test_ii_v_i_then_ii_v_pairs(self) -> None:
        scope = _scope({"A": ["Dm7", "G7", "Cmaj7", "Cmaj7", "Am7", "D7", "Dm7", "G7"]}, "C")
        self.assertEqual(
            _chain(scope), [(("Dm7", "G7", "Cmaj7"), 1, 4), (("Am7", "D7"), 5, 6), (("Dm7", "G7"), 7, 8)]
        )
        self.assertEqual([link.span.relationship for link in scope.chain], ["ii_V_I", "ii_V", "ii_V"])

    def test_perfect_verse_pairs_its_changes(self) -> None:
        scope = build_scope(_catalog("Perfect"), "verse-1", 1, 8)
        self.assertEqual(_chain(scope), [(("G", "Em7"), 1, 4), (("Cadd9", "D/F#"), 5, 8)])
        self.assertTrue(all(link.exact_bar_timing for link in scope.chain))

    def test_no_chord_breaks_the_chain_and_split_bars_are_flagged(self) -> None:
        scope = _scope({"A": ["C:2|G:2", "Am", "Em:3.5|D:0.5p", "D", "N.C.", "G.hit", "C"]}, "G")
        chain = scope.chain
        self.assertTrue(all(link.end_bar < 5 or link.start_bar > 5 for link in chain))
        self.assertFalse(chain[0].exact_bar_timing)
        self.assertTrue(chain[-1].exact_bar_timing)
        self.assertEqual(chain[-1].chords, ("G", "C"))

    def test_single_chord_vamp(self) -> None:
        scope = _scope({"Vamp": ["Dm7"] * 4}, "Dm")
        self.assertEqual(_chain(scope), [(("Dm7",), 1, 4)])
        self.assertIsNone(scope.chain[0].span)

    def test_chain_covers_every_chord_once_in_order(self) -> None:
        for title in ("Perfect", "The Girl from Ipanema", "Autumn Leaves", "Hotel California"):
            ctx = _catalog(title)
            for section in coach_sections(ctx):
                for start, end in suggested_ranges(section):
                    try:
                        scope = build_scope(ctx, section.section_id, start, end)
                    except ScopeError as exc:
                        self.assertEqual(exc.code, ERROR_NO_HARMONY, (title, section.label))
                        continue
                    covered = [i for link in scope.chain for i in range(link.first_event, link.last_event + 1)]
                    harmonic = [i for i, e in enumerate(scope.events) if not e.no_chord]
                    self.assertEqual(covered, harmonic, (title, section.label))
                    for link in scope.chain:
                        self.assertEqual(link.chords, tuple(scope.events[i].chord for i in range(link.first_event, link.last_event + 1)))
                        self.assertTrue(start <= link.start_bar <= link.end_bar <= end, (title, link))
                        if link.span is not None:
                            self.assertEqual(tuple(link.span.chords), link.chords)

    def test_analysis_is_transposition_invariant(self) -> None:
        home = build_scope(_catalog("The Girl from Ipanema"), "a-section")
        moved = build_scope(_catalog("The Girl from Ipanema", key="Ab"), "a-section")
        self.assertEqual(
            [(link.start_bar, link.end_bar, link.length) for link in home.chain],
            [(link.start_bar, link.end_bar, link.length) for link in moved.chain],
        )
        self.assertEqual(
            [link.span.relationship if link.span else None for link in home.chain],
            [link.span.relationship if link.span else None for link in moved.chain],
        )

    def test_section_row_feeds_the_existing_mc1_analyzer(self) -> None:
        from harmonic_span_analyzer import analyze_harmonic_spans

        scope = _scope({"A Section": IPANEMA_A}, "F")
        label, display, raw = scope.section_row()
        self.assertEqual(raw, IPANEMA_A)
        spans = analyze_harmonic_spans([scope.section_row()], key_center="F", length=3)
        self.assertEqual(spans[0].relationship, "ii_subV_I")

    def test_span_chain_is_pure_and_deterministic(self) -> None:
        events = harmony_events(IPANEMA_A)
        a = span_chain(events, key_center="F")
        b = span_chain(list(events), key_center="F")
        self.assertEqual([(l.chords, l.start_bar, l.end_bar) for l in a], [(l.chords, l.start_bar, l.end_bar) for l in b])


class TestWholeCatalog(unittest.TestCase):
    def test_every_section_of_every_song_scopes(self) -> None:
        from song_catalog.catalog import curated_song_records

        scoped = 0
        for rec in curated_song_records():
            ctx = _catalog(rec["title"])
            if not ctx.available:
                continue
            for section in coach_sections(ctx):
                for start, end in suggested_ranges(section):
                    try:
                        scope = build_scope(ctx, section.section_id, start, end)
                    except ScopeError as exc:
                        self.assertEqual(exc.code, ERROR_NO_HARMONY, (rec["title"], section.label, start, end))
                        continue
                    self.assertLessEqual(scope.bar_count, MAX_SCOPE_BARS)
                    self.assertTrue(scope.chain, (rec["title"], section.label))
                    scoped += 1
        self.assertGreater(scoped, 300)


if __name__ == "__main__":
    unittest.main()
