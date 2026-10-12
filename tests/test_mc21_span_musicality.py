"""MC2.1 — level-aware span choices, song order, Practice Focus, style and musicality."""

from __future__ import annotations

import collections
import logging
import statistics
import unittest
from unittest.mock import patch

from harmonic_span_analyzer import (
    analyze_harmonic_spans,
    in_section_order,
    level_allows,
    recommended_span_ids,
    spans_for_level,
)
from improvisation_motif import section_harmony_rows
from melodic_pattern_engine import build_context
from span_motif_engine import (
    FAMILIES,
    build_span_exercise,
    family_weights,
    focus_preference,
    generate_span_motif,
    musicality,
    note_chord_assignment,
    song_style,
)

logging.disable(logging.CRITICAL)

LEVELS = ("Beginner", "Intermediate", "Advanced")
OUTSIDE_VOCAB = {"chromatic_approach", "enclosure", "altered", "diminished", "whole_tone", "lydian_dominant", "side_slip"}
IPANEMA = {
    "Intro": ["Gm7", "C7", "Gm7", "C7"],
    "A": ["Fmaj7", "G7", "Gm7", "Gb7", "Fmaj7", "Gb7"],
    "Outro": ["Gm7", "C7", "Fmaj7", "Fmaj7"],
}


def _rows(sections):
    return section_harmony_rows(sections, section_names=list(sections))


def _span(chords, key, *, raw=None):
    spans = analyze_harmonic_spans(_rows({"A": raw or chords}), key_center=key, length=len(chords), source_id="t", include_weak=True)
    return next(s for s in spans if list(s.chords) == chords)


def _built(span, level, seed, **kw):
    return build_span_exercise(span, generate_span_motif(span, level=level, seed=seed, **kw), length="standard")


class TestLevelEligibility(unittest.TestCase):
    def test_min_level_is_a_harmonic_property_not_a_score_cut(self) -> None:
        cases = {
            ("C", "F", "G"): ("C", "Beginner"),            # I–IV–V, diatonic
            ("Dm7", "G7", "Cmaj7"): ("C", "Beginner"),     # clear major ii–V–I
            ("Cmaj7", "A7", "Dm7"): ("C", "Intermediate"),  # secondary dominant (V/ii)
            ("Bm7b5", "E7", "Am"): ("Am", "Intermediate"),  # minor ii–V–i
            ("Gm7", "Gb7", "Fmaj7"): ("F", "Intermediate"),  # tritone sub resolving home
        }
        for chords, (key, want) in cases.items():
            span = _span(list(chords), key)
            self.assertEqual(span.min_level, want, (chords, span.relationship))
        chromatic = _span(["Cmaj7", "Ebmaj7", "Abmaj7"], "C")
        self.assertEqual(chromatic.min_level, "Advanced", chromatic.relationship)

    def test_beginner_sees_a_curated_subset_advanced_sees_everything(self) -> None:
        spans = analyze_harmonic_spans(_rows(IPANEMA), key_center="F", length=3, source_id="ip")
        beginner, intermediate, advanced = (spans_for_level(spans, lvl) for lvl in LEVELS)
        self.assertLess(len(beginner), len(intermediate))
        self.assertLessEqual(len(intermediate), len(advanced))
        self.assertEqual(len(advanced), len(spans))
        self.assertTrue(set(s.span_id for s in beginner) <= set(s.span_id for s in intermediate))
        rels = {s.relationship for s in beginner}
        self.assertIn("ii_V_I", rels)
        self.assertFalse(rels & {"ii_subV_I", "ii_subV", "subV_I", "secondary_dominant", "dominant_chain"}, rels)
        self.assertTrue(all(level_allows("Beginner", s.min_level) for s in beginner))
        # Same eligibility whatever the analyzer score: a low-ranked simple span stays in.
        self.assertEqual([s.span_id for s in beginner], [s.span_id for s in spans if s.min_level == "Beginner"])

    def test_section_order_not_score_order(self) -> None:
        spans = analyze_harmonic_spans(_rows(IPANEMA), key_center="F", length=3, source_id="ip")
        ordered = in_section_order(spans)
        keys = [(s.section_index, s.start_event) for s in ordered]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(ordered[0].section_label, "Intro")
        self.assertNotEqual([s.span_id for s in ordered], [s.span_id for s in spans], "score order differs from song order")
        top = recommended_span_ids(spans, 3)
        self.assertEqual(top, {s.span_id for s in spans[:3]})


class TestSelectorLevels(unittest.TestCase):
    def _labels(self, level):
        from improvisation_intelligence import ImprovSessionContext
        from improvisation_intelligence_ui import _render_motif_span_selector
        from tests.test_mc1_motif_span_selector_ui import _FakeSt

        ss = {"active_catalog_pick_key": "ipanema"}
        st = _FakeSt(ss)
        ctx = ImprovSessionContext(song_title="I", artist="", key_center="F", display_key="F", instrument="Piano",
                                   level=level, focus="Improvisation", sections={})
        with patch("improvisation_intelligence_ui._coherent_improv_key_pair", return_value=("F", "F")):
            _render_motif_span_selector(st, session_state=ss, improv_ctx=ctx, section_rows=_rows(IPANEMA), scope="span3", level=level)
        return st.options["improv_motif_span_pick_3"], st.selected["improv_motif_span_pick_3"]

    def test_picker_filters_by_level_and_lists_in_song_order(self) -> None:
        seen = {}
        for level in LEVELS:
            labels, selected = self._labels(level)
            seen[level] = labels
            sections = [lb.replace(" · ★ Recommended", "").rsplit(" · ", 1)[1] for lb in labels]
            self.assertEqual(sections, sorted(sections, key=["Intro", "A", "Outro"].index), (level, labels))
            self.assertTrue(selected.startswith("Gm7 → C7 → Fmaj7 · ii–V–I · Outro"), (level, selected))
            self.assertTrue(any("★ Recommended" in lb for lb in labels))
        self.assertLess(len(seen["Beginner"]), len(seen["Advanced"]))
        self.assertFalse(any("subV" in lb for lb in seen["Beginner"]))
        self.assertTrue(any("subV" in lb for lb in seen["Advanced"]))


class TestStyleAndFocusMapping(unittest.TestCase):
    def test_style_comes_from_song_metadata(self) -> None:
        self.assertEqual(song_style("Jazz"), "jazz")
        self.assertEqual(song_style("Jazz", groove="Bossa nova"), "bossa")
        self.assertEqual(song_style("Jazz", jazz_ballad=True), "jazz_ballad")
        self.assertEqual(song_style("Pop", groove="Ballad", bpm=75, tags=["Romantic Ballad"]), "ballad")
        self.assertEqual(song_style("Pop", groove="Pop groove", bpm=118), "pop")
        self.assertEqual(song_style("Rock", groove="Rock groove"), "rock")
        self.assertEqual(song_style("Funk", groove="Funk groove"), "funk")
        self.assertEqual(song_style(""), "default")

    def test_existing_focus_labels_map_onto_generation(self) -> None:
        expected = {
            "Guide Tones": "guide_tones", "Voice Leading": "guide_tones", "Voicings": "guide_tones",
            "Pentatonics": "pentatonic", "Scales": "scales", "Bebop Phrasing": "bebop",
            "Groove": "rhythm", "Syncopation": "rhythm", "Strumming": "rhythm",
            "Soloing": "motif", "Improvisation": "motif", "Triads": "chord_tones", "Harmony": "chord_tones",
            "Melody": "lyrical", "Tone": "neutral", "Breath Support": "neutral", "": "neutral",
        }
        for label, want in expected.items():
            self.assertEqual(focus_preference(label), want, label)

    def test_irrelevant_focus_degrades_to_level_and_style(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        self.assertEqual(
            family_weights(span, level="Intermediate", focus="Breath Support", style="jazz"),
            family_weights(span, level="Intermediate", focus="", style="jazz"),
        )


class TestFocusChangesTheIdea(unittest.TestCase):
    def _families(self, focus, level="Intermediate", n=16):
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        return collections.Counter(generate_span_motif(span, level=level, seed=500 + i, focus=focus)["strategy_family"] for i in range(n))

    def test_focus_steers_strategy_family(self) -> None:
        self.assertEqual(self._families("Pentatonics").most_common(1)[0][0], "pentatonic_cell")
        self.assertEqual(self._families("Guide Tones").most_common(1)[0][0], "guide_tone_line")
        self.assertEqual(self._families("Scales").most_common(1)[0][0], "scalar_fragment")
        self.assertEqual(self._families("Bebop Phrasing", level="Advanced").most_common(1)[0][0], "bebop_run")
        self.assertEqual(self._families("Groove").most_common(1)[0][0], "rhythmic_motif")

    def test_guide_tone_focus_targets_thirds_and_sevenths(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        roles = [t["role"] for i in range(8) for t in _built(span, "Intermediate", i, focus="Guide Tones")["transition_targets"]]
        self.assertGreaterEqual(sum(r in ("3", "7") for r in roles) / len(roles), 0.8, roles)

    def test_metadata_records_focus_and_style(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        m = generate_span_motif(span, level="Intermediate", seed=1, focus="Scales", style="jazz")
        self.assertEqual((m["focus"], m["focus_preference"], m["style"]), ("Scales", "scales", "jazz"))
        self.assertIn(m["strategy_family"], FAMILIES)
        built = build_span_exercise(span, m, length="standard")
        self.assertEqual(built["strategy_family"], m["strategy_family"], "Build develops the same idea")
        self.assertEqual((built["focus"], built["style"]), ("Scales", "jazz"))


class TestStyleShapesTheLine(unittest.TestCase):
    SPAN = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.SPAN = _span(["Gm7", "C7", "Fmaj7"], "F", raw=["Gm7", "C7", "Fmaj7", "Fmaj7"])

    def _profile(self, style, level, n=10):
        agg = collections.defaultdict(list)
        for i in range(n):
            b = _built(self.SPAN, level, 1000 + i, style=style)
            for k, v in b["rhythm_profile"].items():
                agg[k].append(v)
            agg["notes"].append(len(b["midi"]))
            agg["outside"].append(len(set(b["vocabulary_used"]) & OUTSIDE_VOCAB))
        return {k: statistics.mean(v) for k, v in agg.items()}

    def test_jazz_is_more_syncopated_and_triplet_rich_than_pop(self) -> None:
        jazz_i, pop_i = self._profile("jazz", "Intermediate"), self._profile("pop", "Intermediate")
        self.assertGreater(jazz_i["syncopation"], pop_i["syncopation"])
        self.assertGreater(jazz_i["outside"], pop_i["outside"])
        jazz_a, pop_a = self._profile("jazz", "Advanced"), self._profile("pop", "Advanced")
        self.assertGreater(jazz_a["triplets"], pop_a["triplets"])

    def test_ballad_has_more_space_than_jazz(self) -> None:
        for level in LEVELS:
            ballad, jazz = self._profile("ballad", level), self._profile("jazz", level)
            self.assertGreater(ballad["long"], jazz["long"], level)
            # Beginner density is already minimal for every style; above it ballads thin out.
            (self.assertLessEqual if level == "Beginner" else self.assertLess)(ballad["notes"], jazz["notes"], level)

    def test_build_always_develops_beyond_the_seed(self) -> None:
        for style in ("ballad", "jazz", "pop"):
            for level in LEVELS:
                for i in range(3):
                    seed = generate_span_motif(self.SPAN, level=level, seed=i, style=style)
                    built = build_span_exercise(self.SPAN, seed, length="standard")
                    self.assertGreater(len(built["midi"]), len(seed["midi"]), (style, level))
                    self.assertNotEqual(built["midi"], seed["midi"], (style, level))

    def test_pop_prefers_lyrical_and_pentatonic_families(self) -> None:
        pop = family_weights(self.SPAN, level="Intermediate", focus="", style="pop")
        jazz = family_weights(self.SPAN, level="Intermediate", focus="", style="jazz")
        self.assertGreater(pop["pentatonic_cell"] / jazz["pentatonic_cell"], 2)
        self.assertGreater(jazz["enclosure_line"] / pop["enclosure_line"], 2)


class TestLevelDifferences(unittest.TestCase):
    def test_beginner_rhythm_is_quarters_and_eighths(self) -> None:
        span = _span(["Gm7", "C7", "Fmaj7"], "F", raw=["Gm7", "C7", "Fmaj7", "Fmaj7"])
        for style in ("jazz", "pop", "ballad"):
            for i in range(6):
                prof = _built(span, "Beginner", i, style=style)["rhythm_profile"]
                self.assertEqual((prof["syncopation"], prof["triplets"], prof["sixteenths"]), (0, 0, 0), (style, prof))

    def test_beginner_jazz_stays_understandable(self) -> None:
        span = _span(["Gm7", "C7", "Fmaj7"], "F", raw=["Gm7", "C7", "Fmaj7", "Fmaj7"])
        for i in range(8):
            b = _built(span, "Beginner", i, style="jazz")
            self.assertFalse(set(b["vocabulary_used"]) & OUTSIDE_VOCAB, b["vocabulary_used"])
            for m, ci in zip(b["midi"], b["note_chord_index"]):
                self.assertIn(m % 12, build_context("F", b["chord_timeline"][ci]["chord"]).scale_pcs)

    def test_advanced_is_denser_and_richer(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        notes = {lvl: statistics.mean(len(_built(span, lvl, i)["midi"]) for i in range(6)) for lvl in LEVELS}
        self.assertLess(notes["Beginner"], notes["Intermediate"])
        self.assertLess(notes["Intermediate"], notes["Advanced"])
        adv_vocab = set().union(*(_built(span, "Advanced", i, style="jazz")["vocabulary_used"] for i in range(8)))
        self.assertTrue({"enclosure", "chromatic_approach"} & adv_vocab, adv_vocab)
        self.assertTrue({"altered", "diminished", "whole_tone"} & adv_vocab, adv_vocab)

    def test_level_families_are_gated(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        beginner = set(family_weights(span, level="Beginner", focus="Bebop Phrasing", style="jazz"))
        self.assertFalse(beginner & {"bebop_run", "enclosure_line", "intervallic_cell", "guide_tone_line"})
        self.assertGreaterEqual(len(beginner), 5, "Beginner gets several simple motif families")
        self.assertIn("bebop_run", family_weights(span, level="Advanced", focus="", style="jazz"))


class TestVarietyAndScalarMaterial(unittest.TestCase):
    def test_new_ideas_switch_families(self) -> None:
        span = _span(["Gm7", "C7", "Fmaj7"], "F", raw=["Gm7", "C7", "Fmaj7", "Fmaj7"])
        for style in ("jazz", "pop", "ballad"):
            for level in LEVELS:
                fams = {generate_span_motif(span, level=level, seed=900 + i, style=style)["strategy_family"] for i in range(8)}
                lines = {tuple(generate_span_motif(span, level=level, seed=900 + i, style=style)["midi"]) for i in range(8)}
                self.assertGreater(len(fams), 1, (style, level))
                self.assertGreater(len(lines), 4, (style, level))

    def test_ballad_seed_still_has_room_for_an_idea(self) -> None:
        span = _span(["C", "Am", "F"], "C")
        for level in LEVELS:
            seed = generate_span_motif(span, level=level, seed=3, style="ballad")
            for slot in seed["chord_timeline"][:-1]:
                self.assertGreaterEqual(slot["last_note"] - slot["first_note"] + 1, 3, (level, seed["notes"]))
            lines = {tuple(generate_span_motif(span, level=level, seed=40 + i, style="ballad")["midi"]) for i in range(6)}
            self.assertGreater(len(lines), 2, level)

    def test_scalar_material_follows_the_chord_timeline(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        for level in LEVELS:
            for i in range(4):
                b = _built(span, level, i, vocabulary="scalar_fragment")
                self.assertEqual(b["strategy_family"], "scalar_fragment")
                steps = [abs(a - c) for a, c in zip(b["midi"], b["midi"][1:])]
                self.assertGreaterEqual(sum(1 <= d <= 2 for d in steps) / len(steps), 0.6, b["notes"])
                self.assertEqual(note_chord_assignment(b), b["note_chord_index"])
                for t in b["transition_targets"]:
                    ctx = build_context("C", b["chord_timeline"][t["chord_index"]]["chord"])
                    self.assertIn(t["midi"] % 12, ctx.chord_pcs)


class TestHarmonicFunction(unittest.TestCase):
    def test_two_five_one_resolves_and_two_five_leads_forward(self) -> None:
        iivi = _span(["Dm7", "G7", "Cmaj7"], "C")
        two_five = _span(["Dm7", "G7"], "C", raw=["Dm7", "G7", "Em7", "A7"])
        self.assertEqual(two_five.relationship, "ii_V")
        for level in LEVELS:
            for i in range(5):
                b = _built(iivi, level, i)
                self.assertIn(b["midi"][-1] % 12, {0, 4, 7}, ("I settles", level, b["notes"]))
                for c in b["change_indices"]:
                    self.assertLessEqual(abs(b["midi"][c] - b["midi"][c - 1]), 2, b["notes"])
                f = _built(two_five, level, i)
                self.assertNotEqual(f["midi"][-1] % 12, 7, ("ii→V must not sound finished on G", level, f["notes"]))
                self.assertIn(f["midi"][-1] % 12, {11, 5, 2}, f["notes"])  # 3rd / 7th / 5th of G7

    def test_advanced_dominant_colour_is_from_the_harmony_and_resolves(self) -> None:
        iivi = _span(["Dm7", "G7", "Cmaj7"], "C")
        colours = collections.Counter()
        for i in range(12):
            b = _built(iivi, "Advanced", i, style="jazz")
            for c in b["advanced_colors"]:
                if c["chord"] == "G7":
                    colours[c["color"]] += 1
            # Whatever the colour, the line steps into the I chord.
            c_idx = b["change_indices"][1]
            self.assertLessEqual(abs(b["midi"][c_idx] - b["midi"][c_idx - 1]), 2, b["notes"])
            self.assertIn(b["midi"][c_idx] % 12, {0, 4, 7, 11})
        self.assertTrue(set(colours) <= {"altered", "diminished", "whole_tone"}, colours)
        self.assertGreater(sum(colours.values()), 6)
        subv = _span(["Gm7", "Gb7", "Fmaj7"], "F")
        sub_colours = {c["color"] for i in range(8) for c in _built(subv, "Advanced", i, style="jazz")["advanced_colors"] if c["chord"] == "Gb7"}
        self.assertEqual(sub_colours, {"lydian_dominant"})

    def test_non_resolving_dominant_gets_no_outside_colour(self) -> None:
        vamp = _span(["Gm7", "C7"], "F", raw=["Gm7", "C7", "Gm7", "C7"])
        for i in range(6):
            b = build_span_exercise(vamp, generate_span_motif(vamp, level="Advanced", seed=i, style="pop"), length="extended")
            for c in b["advanced_colors"]:
                self.assertNotEqual(c["chord"], "C7", "C7 → Gm7 is not a V–I: no altered colour")


class TestMusicalityGuardrails(unittest.TestCase):
    def test_score_penalizes_mechanical_lines(self) -> None:
        ctxs = [build_context("C", "Cmaj7")]
        idx = [0] * 8
        smooth = musicality([60, 62, 64, 65, 67, 65, 64, 62], idx, ctxs, level="Intermediate")
        zigzag = musicality([60, 64, 60, 64, 60, 64, 60, 64], idx, ctxs, level="Intermediate")
        repeats = musicality([60, 60, 62, 62, 64, 64, 65, 65], idx, ctxs, level="Intermediate")
        leaps = musicality([55, 67, 57, 69, 59, 71, 60, 72], idx, ctxs, level="Intermediate")
        roots = musicality([60, 72, 60, 64, 60, 72, 60, 67], idx, ctxs, level="Intermediate")
        for bad in (zigzag, repeats, leaps, roots):
            self.assertLess(bad["total"], smooth["total"])
        self.assertLess(zigzag["alternation"], 0)
        self.assertLess(repeats["repeats"], 0)
        self.assertLess(roots["root_abuse"], 0)

    def test_generated_lines_respect_guardrails(self) -> None:
        spans = [
            _span(["Gm7", "C7", "Fmaj7"], "F", raw=["Gm7", "C7", "Fmaj7", "Fmaj7"]),
            _span(["C", "Am", "F"], "C"),
            _span(["Gm7", "C7"], "F", raw=["Gm7", "C7", "Gm7", "C7"]),
            _span(["F", "Bb"], "F", raw=["F", "Bb", "C", "F"]),
        ]
        limits = {"Beginner": 7, "Intermediate": 9, "Advanced": 9}
        for span in spans:
            for style in ("jazz", "pop", "ballad"):
                for level in LEVELS:
                    for i in range(3):
                        seed = generate_span_motif(span, level=level, seed=i, style=style)
                        for m in (seed, build_span_exercise(span, seed, length="standard"), build_span_exercise(span, seed, length="extended")):
                            mids = m["midi"]
                            ctx = (span.chords, style, level, m["notes"])
                            self.assertLessEqual(max(abs(a - b) for a, b in zip(mids, mids[1:])), limits[level], ctx)
                            self.assertFalse(any(a == b for a, b in zip(mids, mids[1:])), ctx)
                            self.assertEqual(m["musicality"]["alternation"], 0, ctx)
                            self.assertEqual(note_chord_assignment(m), m["note_chord_index"])


if __name__ == "__main__":
    unittest.main()
