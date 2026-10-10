"""MC1 — harmonic-span selector: contiguous, ranked, stable 2-/3-chord spans."""

from __future__ import annotations

import json
import logging
import unittest
from types import SimpleNamespace

from harmonic_span_analyzer import (
    SCOPE_SPAN2,
    SCOPE_SPAN3,
    analyze_harmonic_spans,
    progression_fingerprint,
    section_events,
    span_display_label,
)
from improvisation_motif import (
    dedupe_sections_for_display,
    resolve_improv_section_rows,
    resolve_improv_sections,
    section_and_chord_at_global_index,
    section_harmony_rows,
)
from music_theory import transpose_chord

logging.disable(logging.CRITICAL)


def _rows(*sections: tuple[str, list[str]]) -> list[tuple[str, list[str], list[str]]]:
    return section_harmony_rows(dict(sections), section_names=[name for name, _ in sections])


def _spans(rows, key: str, length: int, source: str = "song", **kw):
    return analyze_harmonic_spans(rows, key_center=key, length=length, source_id=source, **kw)


def _by_chords(spans):
    return {s.chords: s for s in spans}


class TestFunctionalRecognition(unittest.TestCase):
    def test_ii_v(self) -> None:
        spans = _by_chords(_spans(_rows(("Verse", ["Dm7", "G7", "Cmaj7"])), "C", 2))
        span = spans[("Dm7", "G7")]
        self.assertEqual(span.relationship, "ii_V")
        self.assertEqual(span.relationship_label, "ii–V")
        self.assertEqual(span.roman, ("ii", "V"))
        self.assertEqual(span.target_roman, "I")

    def test_v_i(self) -> None:
        span = _by_chords(_spans(_rows(("Verse", ["Dm7", "G7", "Cmaj7"])), "C", 2))[("G7", "Cmaj7")]
        self.assertEqual(span.relationship, "V_I")
        self.assertEqual(span.relationship_label, "V–I")
        self.assertEqual(span.target_chord, "Cmaj7")

    def test_ii_v_i(self) -> None:
        spans = _spans(_rows(("Verse", ["Dm7", "G7", "Cmaj7"])), "C", 3)
        self.assertEqual(spans[0].chords, ("Dm7", "G7", "Cmaj7"))
        self.assertEqual(spans[0].relationship, "ii_V_I")
        self.assertEqual(spans[0].relationship_label, "ii–V–I")
        self.assertIn("C major", spans[0].common_scales)

    def test_minor_ii_v_i_in_minor_key(self) -> None:
        span = _spans(_rows(("A", ["Bm7b5", "E7", "Am"])), "Am", 3)[0]
        self.assertEqual(span.relationship_label, "iiø–V–i")
        self.assertEqual(span.target_chord, "Am")
        self.assertIn("A harmonic minor", span.common_scales)

    def test_minor_ii_v_i_tonicizing_vi_in_major_key(self) -> None:
        span = _spans(_rows(("A", ["Bm7b5", "E7", "Am"])), "C", 3)[0]
        self.assertEqual(span.relationship_label, "iiø–V → vi")
        pair = _by_chords(_spans(_rows(("A", ["Bm7b5", "E7", "Am"])), "C", 2))[("Bm7b5", "E7")]
        self.assertEqual(pair.relationship_label, "iiø–V of vi")

    def test_ii_v_of_a_diatonic_minor_target_uses_the_keys_quality(self) -> None:
        pair = _by_chords(_spans(_rows(("Chorus", ["Fmaj7", "Em7", "A7", "Dm7"])), "C", 2))[("Em7", "A7")]
        self.assertEqual(pair.relationship_label, "ii–V of ii")

    def test_secondary_dominant(self) -> None:
        span = _by_chords(_spans(_rows(("A", ["Cmaj7", "A7", "Dm7", "G7"])), "C", 2))[("A7", "Dm7")]
        self.assertEqual(span.relationship, "secondary_dominant")
        self.assertEqual(span.relationship_label, "V/ii–ii")

    def test_dominant_chain_into_tonic(self) -> None:
        span = _by_chords(_spans(_rows(("A", ["D7", "G7", "C"])), "C", 3))[("D7", "G7", "C")]
        self.assertEqual(span.relationship_label, "V/V–V–I")

    def test_tritone_substitute_cadence(self) -> None:
        rows = _rows(("A", ["Fmaj7", "Gm7", "Gb7", "Fmaj7"]))
        three = _by_chords(_spans(rows, "F", 3))[("Gm7", "Gb7", "Fmaj7")]
        self.assertEqual(three.relationship_label, "ii–subV–I")
        self.assertEqual(three.roman, ("ii", "subV", "I"))
        two = _by_chords(_spans(rows, "F", 2))
        self.assertEqual(two[("Gm7", "Gb7")].relationship_label, "ii–subV")
        self.assertEqual(two[("Gb7", "Fmaj7")].relationship_label, "subV–I")

    def test_trailing_applied_dominant_is_explained_by_the_next_charted_chord(self) -> None:
        span = _by_chords(_spans(_rows(("Chorus", ["Fmaj7", "Em7", "A7", "Dm7"])), "C", 3))[("Fmaj7", "Em7", "A7")]
        self.assertEqual(span.relationship_label, "IV–iii–V/ii")
        self.assertTrue(span.roman_confident)


class TestRankingAndWeakSpans(unittest.TestCase):
    def test_ii_v_i_outranks_a_plain_diatonic_window(self) -> None:
        rows = _rows(("Verse", ["Cmaj7", "Am7", "Fmaj7", "Dm7", "G7", "Cmaj7"]))
        spans = _spans(rows, "C", 3)
        self.assertEqual(spans[0].chords, ("Dm7", "G7", "Cmaj7"))
        order = [s.chords for s in spans]
        self.assertLess(order.index(("Dm7", "G7", "Cmaj7")), order.index(("Cmaj7", "Am7", "Fmaj7")))

    def test_ordinary_diatonic_progression_is_not_called_ii_v_i(self) -> None:
        rows = _rows(("Verse", ["C", "Am", "F", "G"]))
        for length in (2, 3):
            spans = _spans(rows, "C", length)
            self.assertTrue(spans)
            for span in spans:
                self.assertNotIn(span.relationship, {"ii_V", "ii_V_I", "V_I"}, span)
                self.assertTrue(span.roman_confident, span)
        labels = {s.chords: s.relationship_label for s in _spans(rows, "C", 2)}
        self.assertEqual(labels[("F", "G")], "IV–V")
        self.assertEqual(labels[("C", "Am")], "I–vi")

    def test_weak_windows_are_hidden_when_enough_strong_ones_exist(self) -> None:
        rows = _rows(("A", ["Cmaj7", "Dm7", "G7", "Cmaj7", "F#7", "Cmaj7", "A7", "Dm7"]))
        shown = _spans(rows, "C", 2)
        everything = _spans(rows, "C", 2, include_weak=True)
        self.assertGreater(len(everything), len(shown))
        self.assertTrue(all(s.score >= 40 for s in shown))

    def test_weak_windows_still_shown_when_nothing_better_exists(self) -> None:
        spans = _spans(_rows(("A", ["C", "F#"])), "C", 2)
        self.assertEqual([s.chords for s in spans], [("C", "F#")])
        self.assertEqual(span_display_label(spans[0]), "C → F#")

    def test_ordering_is_deterministic(self) -> None:
        rows = _rows(
            ("Verse", ["Cmaj7", "Am7", "Dm7", "G7"]),
            ("Chorus", ["Fmaj7", "Em7", "A7", "Dm7", "G7", "Cmaj7"]),
        )
        for length in (2, 3):
            first = [s.span_id for s in _spans(rows, "C", length)]
            for _ in range(3):
                self.assertEqual([s.span_id for s in _spans(rows, "C", length)], first)


class TestContiguityRepeatsAndVamps(unittest.TestCase):
    def test_only_contiguous_windows_in_chart_order(self) -> None:
        chords = ["Am7", "D7", "Gmaj7", "Cmaj7"]
        rows = _rows(("Verse", chords))
        allowed2 = {tuple(chords[i : i + 2]) for i in range(3)}
        allowed3 = {tuple(chords[i : i + 3]) for i in range(2)}
        self.assertEqual({s.chords for s in _spans(rows, "G", 2, include_weak=True)}, allowed2)
        self.assertEqual({s.chords for s in _spans(rows, "G", 3, include_weak=True)}, allowed3)

    def test_repeated_bars_keep_their_duration(self) -> None:
        rows = _rows(("Verse", ["G", "G", "C", "D"]))
        self.assertEqual(rows[0][1], ["G", "C", "D"])  # chord map display collapses …
        self.assertEqual(rows[0][2], ["G", "G", "C", "D"])  # … but the raw chart survives
        span = _by_chords(_spans(rows, "G", 2))[("G", "C")]
        self.assertEqual([(e.chord, e.bars) for e in span.raw_events], [("G", 2), ("C", 1)])
        self.assertEqual((span.raw_start, span.raw_end), (0, 2))
        self.assertEqual(span.relationship_label, "I–IV")

    def test_repeated_vamp_is_recognized(self) -> None:
        rows = _rows(("Vamp", ["Am7", "D7", "Am7", "D7"]))
        self.assertEqual(rows[0][1], ["Am7", "D7"])
        spans = _spans(rows, "G", 2)
        top = spans[0]
        self.assertEqual(top.chords, ("Am7", "D7"))
        self.assertTrue(top.repeated_vamp)
        self.assertEqual(top.relationship_label, "ii–V vamp")
        self.assertEqual(top.occurrences, 2)
        self.assertFalse(_by_chords(spans)[("D7", "Am7")].repeated_vamp)

    def test_modal_vamp(self) -> None:
        top = _spans(_rows(("A", ["C", "Bb", "C", "Bb"])), "C", 2)[0]
        self.assertEqual(top.chords, ("C", "Bb"))
        self.assertEqual(top.relationship_label, "modal vamp")

    def test_no_chord_breaks_windows(self) -> None:
        spans = _spans(_rows(("A", ["C", "N.C.", "F", "G"])), "C", 2, include_weak=True)
        self.assertEqual([s.chords for s in spans], [("F", "G")])

    def test_display_indices_point_at_the_chord_map_tiles(self) -> None:
        rows = _rows(("Verse", ["Cmaj7", "Am7"]), ("Chorus", ["Am7", "D7", "Am7", "D7"]))
        section_map = [(label, clean) for label, clean, _raw in rows]
        for span in _spans(rows, "C", 2, include_weak=True):
            for chord, gidx in zip(span.chords, span.display_global_indices):
                label, tile = section_and_chord_at_global_index(section_map, gidx)
                self.assertEqual(tile, chord)
                self.assertEqual(label, span.section_label)

    def test_section_events(self) -> None:
        events = section_events(["Dm7", "Dm7", "G7", "", "Cmaj7", "Cmaj7", "Cmaj7"])
        self.assertEqual([(e.chord, e.bars, e.raw_index) for e in events], [("Dm7", 2, 0), ("G7", 1, 2), ("Cmaj7", 3, 4)])


class TestSectionBoundaries(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = _rows(("Verse", ["Cmaj7", "Am7", "Dm7"]), ("Chorus", ["G7", "Cmaj7", "Fmaj7"]))

    def test_default_spans_stay_inside_one_section(self) -> None:
        for length in (2, 3):
            for span in _spans(self.rows, "C", length, include_weak=True):
                self.assertFalse(span.cross_section)
                self.assertIn(span.section_label, {"Verse", "Chorus"})
        # Dm7 (end of Verse) → G7 (start of Chorus) is a real ii–V but crosses a boundary.
        self.assertNotIn(("Dm7", "G7"), {s.chords for s in _spans(self.rows, "C", 2, include_weak=True)})

    def test_cross_section_spans_are_opt_in_and_clearly_classified(self) -> None:
        spans = _by_chords(_spans(self.rows, "C", 2, allow_cross_section=True, include_weak=True))
        crossing = spans[("Dm7", "G7")]
        self.assertTrue(crossing.cross_section)
        self.assertEqual(crossing.section_label, "Verse → Chorus")
        self.assertTrue(crossing.span_id.endswith("|x"))
        inside = spans[("Cmaj7", "Am7")]
        self.assertFalse(inside.cross_section)

    def test_duplicate_section_blocks_do_not_duplicate_spans(self) -> None:
        sections = {"Verse": ["Dm7", "G7", "Cmaj7"], "Chorus": ["Fmaj7", "G7"], "Verse 2": ["Dm7", "G7", "Cmaj7"]}
        rows = section_harmony_rows(sections, section_names=list(sections))
        spans = _spans(rows, "C", 2, include_weak=True)
        self.assertEqual(len([s for s in spans if s.chords == ("Dm7", "G7")]), 1)
        self.assertEqual(_by_chords(spans)[("Dm7", "G7")].occurrences, 2)


class TestStableIdentity(unittest.TestCase):
    CHORDS = (("Verse", ["Cmaj7", "Am7", "Dm7", "G7"]), ("Chorus", ["Fmaj7", "Em7", "A7", "Dm7", "G7", "Cmaj7"]))

    def _transposed(self, steps: int, key: str):
        return _rows(*((name, [transpose_chord(c, steps, reference_key=key) for c in chords]) for name, chords in self.CHORDS))

    def test_practice_key_change_keeps_identity_and_order(self) -> None:
        base = _rows(*self.CHORDS)
        moved = self._transposed(2, "D")
        self.assertEqual(progression_fingerprint(base), progression_fingerprint(moved))
        for length in (2, 3):
            a = _spans(base, "C", length, source="pick-123")
            b = _spans(moved, "D", length, source="pick-123")
            self.assertEqual([s.span_id for s in a], [s.span_id for s in b])
            self.assertEqual([s.relationship_label for s in a], [s.relationship_label for s in b])
            self.assertEqual(
                [tuple(transpose_chord(c, 2, reference_key="D") for c in s.chords) for s in a],
                [s.chords for s in b],
            )

    def test_display_projection_changes_labels_not_identity(self) -> None:
        span = _spans(_rows(*self.CHORDS), "C", 3, source="pick")[0]
        self.assertEqual(span_display_label(span), "Dm7 → G7 → Cmaj7 · ii–V–I")
        written = span_display_label(span, project=lambda c: transpose_chord(c, 2, reference_key="D"))
        self.assertEqual(written, "Em7 → A7 → Dmaj7 · ii–V–I")
        self.assertEqual(span_display_label(span, include_section=True), "Dm7 → G7 → Cmaj7 · ii–V–I · Chorus")

    def test_different_song_or_progression_gets_different_ids(self) -> None:
        rows = _rows(*self.CHORDS)
        other = _rows(("Verse", ["Cmaj7", "Am7", "Dm7", "G7"]), ("Chorus", ["Fmaj7", "G7", "Cmaj7"]))
        a = {s.span_id for s in _spans(rows, "C", 2, source="custom")}
        b = {s.span_id for s in _spans(other, "C", 2, source="custom")}
        c = {s.span_id for s in _spans(rows, "C", 2, source="other-pick")}
        self.assertFalse(a & b)
        self.assertFalse(a & c)

    def test_span_record_is_json_ready_and_scoped(self) -> None:
        span = _spans(_rows(*self.CHORDS), "C", 3, source="pick")[0]
        self.assertEqual(span.scope, SCOPE_SPAN3)
        self.assertEqual(_spans(_rows(*self.CHORDS), "C", 2, source="pick")[0].scope, SCOPE_SPAN2)
        payload = json.loads(json.dumps(span.to_dict()))
        self.assertEqual(payload["chords"], list(span.chords))
        self.assertEqual(payload["length"], 3)

    def test_unsupported_length_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _spans(_rows(*self.CHORDS), "C", 4)


class TestSourceShapes(unittest.TestCase):
    def test_refactor_keeps_the_chord_map_identical(self) -> None:
        sections = {
            "Intro": ["Cmaj7", "Cmaj7"],
            "Verse": ["Dm7", "G7", "Cmaj7", "Cmaj7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
            "Chorus": ["Fmaj7", "G7", "Em7", "Am7"],
            "Verse 2": ["Dm7", "G7", "Cmaj7", "A7"],
            "Chorus 2": ["Fmaj7", "G7", "Em7", "Am7"],
        }
        rows = section_harmony_rows(sections, section_names=list(sections))
        self.assertEqual(dedupe_sections_for_display(sections, section_names=list(sections)), [(l, c) for l, c, _ in rows])

    def _ctx(self, **kw):
        base = dict(sections={}, section_order=[], progression_flat=[])
        base.update(kw)
        return SimpleNamespace(**base)

    def test_catalog_shape(self) -> None:
        sections = {"Verse": ["Am7", "D7", "Gmaj7", "Gmaj7"], "Chorus": ["Cmaj7", "Bm7", "Em7", "A7"]}
        rows = resolve_improv_section_rows({}, self._ctx(sections=sections, section_order=["Verse", "Chorus"]))
        self.assertEqual(resolve_improv_sections({}, self._ctx(sections=sections, section_order=["Verse", "Chorus"])), [(l, c) for l, c, _ in rows])
        top = _spans(rows, "G", 3)[0]
        self.assertEqual(top.chords, ("Am7", "D7", "Gmaj7"))
        self.assertEqual(top.relationship_label, "ii–V–I")

    def test_custom_flat_progression_shape(self) -> None:
        rows = resolve_improv_section_rows({}, self._ctx(progression_flat=["Gm7", "C7", "Fmaj7", "Fmaj7"]))
        self.assertEqual(rows, [("Progression", ["Gm7", "C7", "Fmaj7", "Fmaj7"], ["Gm7", "C7", "Fmaj7", "Fmaj7"])])
        top = _spans(rows, "F", 3)[0]
        self.assertEqual(top.relationship_label, "ii–V–I")
        self.assertEqual(top.raw_events[-1].bars, 2)

    def test_generated_and_composition_section_shapes(self) -> None:
        gen = {"Section A": ["Em7", "A7", "Dmaj7", "Bm7"], "Section B": ["Gmaj7", "A7", "Dmaj7"]}
        rows = resolve_improv_section_rows({"improv_generated_sections": gen}, self._ctx())
        labels = [s.relationship_label for s in _spans(rows, "D", 3)]
        self.assertIn("ii–V–I", labels)
        self.assertEqual({s.section_label for s in _spans(rows, "D", 2, include_weak=True)}, {r[0] for r in rows})

    def test_unparseable_or_empty_material_degrades_gracefully(self) -> None:
        self.assertEqual(_spans([], "C", 2), [])
        self.assertEqual(_spans(_rows(("A", ["C"])), "C", 2), [])
        self.assertEqual(_spans(_rows(("A", ["N.C.", "N.C."])), "C", 2), [])


class TestAnalysisKeyGuard(unittest.TestCase):
    IPANEMA = (("Intro", ["Gm7", "C7", "Gm7", "C7"]), ("A", ["Fmaj7", "G7", "Gm7", "Gb7", "Fmaj7", "Gb7"]))

    def test_chart_key_wins_over_a_key_that_leads_the_chart(self) -> None:
        from harmonic_span_analyzer import best_fitting_key

        self.assertEqual(best_fitting_key(_rows(*self.IPANEMA), ["G", "F"]), "F")

    def test_authoritative_key_kept_when_it_fits(self) -> None:
        from harmonic_span_analyzer import best_fitting_key

        rows = _rows(("A", ["Cmaj7", "A7", "Dm7", "G7", "Cmaj7"]))
        self.assertEqual(best_fitting_key(rows, ["C", "F"]), "C")  # secondary dominants do not re-key
        self.assertEqual(best_fitting_key(rows, ["C", "C"]), "C")
        self.assertEqual(best_fitting_key(rows, ["", None, "C"]), "C")
        self.assertEqual(best_fitting_key(rows, []), "C")

    def test_minor_key_candidate(self) -> None:
        from harmonic_span_analyzer import best_fitting_key

        rows = _rows(("A", ["Am", "Bm7b5", "E7", "Am", "Dm"]))
        self.assertEqual(best_fitting_key(rows, ["Am", "Bb"]), "Am")


class TestWholeCatalog(unittest.TestCase):
    """Every curated chart: contiguous, in-section, deterministic, never errors."""

    def test_invariants_hold_for_every_catalog_song(self) -> None:
        from song_catalog.catalog import curated_song_records

        songs = curated_song_records()
        self.assertGreater(len(songs), 50)
        found_ii_v_i = 0
        for record in songs:
            sections = record.get("sections") or {}
            rows = section_harmony_rows(sections, section_names=record.get("section_order") or list(sections))
            events = {i: [e.chord for e in section_events(raw)] for i, (_l, _d, raw) in enumerate(rows)}
            for length in (2, 3):
                spans = _spans(rows, record["key"], length, source=record["title"], include_weak=True)
                again = _spans(rows, record["key"], length, source=record["title"], include_weak=True)
                self.assertEqual([s.span_id for s in spans], [s.span_id for s in again], record["title"])
                self.assertEqual(len({s.span_id for s in spans}), len(spans), record["title"])
                for span in spans:
                    self.assertFalse(span.cross_section)
                    seq = events[span.section_index][span.start_event : span.end_event + 1]
                    self.assertEqual(tuple(seq), span.chords, (record["title"], span.span_id))
                    self.assertEqual(span.length, length)
                    found_ii_v_i += span.relationship == "ii_V_I"
        self.assertGreater(found_ii_v_i, 10)


if __name__ == "__main__":
    unittest.main()
