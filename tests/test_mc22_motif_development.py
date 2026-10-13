"""MC2.2 — rhythmic motif grammar, Build as development of the seed, style/focus phrasing,
and localized explanations that describe what the line actually does."""

from __future__ import annotations

import collections
import logging
import statistics
import unittest
from fractions import Fraction

from harmonic_span_analyzer import analyze_harmonic_spans
from improvisation_motif import build_motif_abc, section_harmony_rows
from melodic_pattern_engine import build_context
from melodic_rhythm_engine import RhythmEvent, events_from_json
from span_motif_engine import (
    _pentatonic,
    build_span_exercise,
    cycle_span_rhythm,
    generate_span_motif,
    motif_identity,
    note_chord_assignment,
    project_span_motif,
)
from span_motif_explain import degree_label, explain_span_motif, explanation_markdown, spell_from_root
from span_rhythm_grammar import (
    CELLS_44,
    bar_signatures,
    cell_info,
    rhythm_coherence,
)
from tests.abc_pitch_decoder import decode_abc_midis

logging.disable(logging.CRITICAL)

LEVELS = ("Beginner", "Intermediate", "Advanced")
F = Fraction


def _span(chords, key, *, raw=None):
    rows = section_harmony_rows({"A": raw or chords}, section_names=["A"])
    spans = analyze_harmonic_spans(rows, key_center=key, length=len(chords), source_id="t", include_weak=True)
    return next(s for s in spans if list(s.chords) == chords)


IIVI_F = None


def _iivi():
    global IIVI_F
    if IIVI_F is None:
        IIVI_F = _span(["Gm7", "C7", "Fmaj7"], "F", raw=["Gm7", "C7", "Fmaj7", "Fmaj7"])
    return IIVI_F


def _notes(m):
    return [e for e in events_from_json(m["rhythm_events"]) if not e.rest]


def _sigs(m):
    return bar_signatures(_notes(m), "4/4")


def _crosses(e):
    return e.onset % 1 != 0 and e.onset + e.duration > e.onset - e.onset % 1 + 1


class TestCells(unittest.TestCase):
    def test_every_curated_cell_is_a_valid_bar_opening_on_the_downbeat(self) -> None:
        for figs in CELLS_44:
            info = cell_info(figs)
            self.assertIsNotNone(info, figs)
            self.assertGreaterEqual(info.notes, 2)

    def test_coherence_rewards_a_repeated_cell_and_punishes_unrelated_bars(self) -> None:
        def bars(*cells):
            evs, pos, n = [], F(0), 0
            for cell in cells:
                for d in cell:
                    evs.append(RhythmEvent(pos, F(d), F(d), note=n))
                    pos += F(d)
                    n += 1
            return evs

        motif = rhythm_coherence(bars((1, 1, 2), (1, 1, 2), (1, 1, 2), (4,)), "4/4", style="pop")
        random_bars = rhythm_coherence(bars((2, 1, 1), (1, 1, 2), (F(1, 2), F(1, 2), 1, 2), (4,)), "4/4", style="pop")
        mid_long = rhythm_coherence(bars((1, 2, 1), (1, 2, 1), (1, 2, 1), (4,)), "4/4", style="pop")
        self.assertTrue(motif["singable"])
        self.assertGreater(motif["total"], random_bars["total"])
        self.assertFalse(random_bars["singable"])
        self.assertGreater(mid_long["unmotivated_long"], 0)
        self.assertGreater(motif["total"], mid_long["total"])


class TestSeedRhythmIsAMotif(unittest.TestCase):
    """The screenshot case: Beginner jazz Gm7 → C7 → Fmaj7 (Fmaj7 held two bars)."""

    def test_beginner_ii_v_i_states_and_repeats_one_cell_then_resolves(self) -> None:
        for i in range(12):
            m = generate_span_motif(_iivi(), level="Beginner", seed=i, style="jazz")
            sigs = _sigs(m)
            self.assertEqual(sigs[0], sigs[1], (i, m["rhythm"]))  # A A
            self.assertEqual(sigs[1], sigs[2], (i, m["rhythm"]))  # A A A (Beginner keeps it exact)
            evs = _notes(m)
            self.assertEqual(evs[-1].duration, 4, "held resolution on the final bar")
            coh = m["rhythm_coherence"]
            self.assertTrue(coh["singable"], (i, m["rhythm"], coh))
            self.assertEqual(coh["unmotivated_long"], 0)
            self.assertTrue(all(d in (F(1, 2), F(1), F(2), F(4)) for d in (e.duration for e in evs)), m["rhythm"])

    def test_intermediate_and_advanced_use_a_and_a_prime(self) -> None:
        for level in ("Intermediate", "Advanced"):
            for i in range(10):
                m = generate_span_motif(_iivi(), level=level, seed=i, style="jazz")
                roles = m["rhythm_plan"]["bar_roles"]
                self.assertEqual(roles[0], "statement")
                self.assertIn(roles[1], ("variation", "repeat"))
                sigs = _sigs(m)
                a = {x[0] for x in sigs[0]}
                # Every active bar keeps most of the cell's onsets (repeat or one small change).
                for b in (1, 2):
                    self.assertGreaterEqual(len(a & {x[0] for x in sigs[b]}) / len(a), 0.6, (level, i, m["rhythm"]))
                self.assertLessEqual(m["rhythm_coherence"]["distinct_bars"], 2, m["rhythm"])

    def test_cadence_comes_from_the_cells_opening(self) -> None:
        span = _span(["Dm7", "G7", "Cmaj7"], "C")
        for level in LEVELS:
            for i in range(8):
                m = generate_span_motif(span, level=level, seed=i, style="pop")
                sigs = _sigs(m)
                last, first = sigs[-1], sigs[0]
                self.assertGreaterEqual(last[-1][1], 1, "the phrase closes on a held value")
                self.assertEqual(last[0][0], first[0][0])
                self.assertEqual(last[0][1], first[0][1], (level, i, m["rhythm"]))  # same opening value

    def test_motif_focus_keeps_the_cell_exact(self) -> None:
        for i in range(8):
            m = generate_span_motif(_iivi(), level="Intermediate", seed=i, style="jazz", focus="Improvisation")
            sigs = _sigs(m)
            self.assertEqual(sigs[0], sigs[1], m["rhythm"])
            self.assertEqual(sigs[1], sigs[2], m["rhythm"])


class TestBuildDevelopsTheSeed(unittest.TestCase):
    def test_every_seed_note_survives_in_order_on_its_chord(self) -> None:
        for style in ("jazz", "pop", "ballad"):
            for level in LEVELS:
                for i in range(4):
                    seed = generate_span_motif(_iivi(), level=level, seed=i, style=style)
                    built = build_span_exercise(_iivi(), seed, length="standard")
                    kept = [(built["midi"][k], built["note_chord_index"][k]) for k in built["seed_note_indices"]]
                    self.assertEqual(kept, list(zip(seed["midi"], seed["note_chord_index"])), (style, level, i))
                    ident = built["motif_identity"]
                    self.assertEqual(ident["skeleton"], 1.0)
                    self.assertEqual(ident["opening"], 1.0)
                    self.assertGreaterEqual(ident["rhythm_cell"], 0.8, (style, level, i, seed["rhythm"], built["rhythm"]))
                    self.assertGreaterEqual(ident["total"], 0.8, (style, level, i, ident))

    def test_build_is_far_closer_to_its_seed_than_an_unrelated_phrase(self) -> None:
        builds, unrelated = [], []
        for level in LEVELS:
            for i in range(6):
                seed = generate_span_motif(_iivi(), level=level, seed=i, style="jazz")
                builds.append(build_span_exercise(_iivi(), seed, length="standard")["motif_identity"]["total"])
                other = build_span_exercise(_iivi(), generate_span_motif(_iivi(), level=level, seed=100 + i, style="jazz"))
                unrelated.append(motif_identity(seed, other)["total"])
        self.assertGreater(statistics.mean(builds), 0.9)
        self.assertGreater(statistics.mean(builds) - statistics.mean(unrelated), 0.3, (builds, unrelated))

    def test_repeated_seed_cells_are_developed_the_same_way(self) -> None:
        same = 0
        total = 0
        for style in ("jazz", "pop"):
            for i in range(10):
                seed = generate_span_motif(_iivi(), level="Beginner", seed=i, style=style)
                built = build_span_exercise(_iivi(), seed, length="standard")
                sigs = _sigs(built)
                total += 1
                same += sigs[0] == sigs[1] == sigs[2]
        self.assertGreaterEqual(same / total, 0.8, f"{same}/{total} builds keep the rhythmic repetition")

    def test_extended_returns_to_the_opening_and_answers(self) -> None:
        for level in LEVELS:
            for i in range(4):
                seed = generate_span_motif(_iivi(), level=level, seed=i, style="jazz")
                ext = build_span_exercise(_iivi(), seed, length="extended")
                tl = ext["chord_timeline"]
                seg = lambda k: ext["midi"][tl[k]["first_note"]: tl[k]["last_note"] + 1]  # noqa: E731
                self.assertEqual(seg(0), seg(3), "pass 2 restates the developed opening")
                seam = tl[3]["first_note"]
                self.assertLessEqual(abs(ext["midi"][seam] - ext["midi"][seam - 1]), 2)
                self.assertIn(ext["midi"][-1] % 12, {5, 9, 0})  # the answer still cadences on F
                self.assertEqual(len(ext["motif_identity"]["passes"]), 2)
                self.assertGreaterEqual(ext["motif_identity"]["total"], 0.8)
                self.assertEqual(note_chord_assignment(ext), ext["note_chord_index"])
                self.assertEqual(decode_abc_midis(build_motif_abc(ext, key_center="F", bpm=100)), ext["midi"])

    def test_build_uses_the_seed_as_shown_after_change_rhythm(self) -> None:
        seed = generate_span_motif(_iivi(), level="Intermediate", seed=3, style="jazz")
        changed = cycle_span_rhythm(seed)
        self.assertNotEqual(changed["rhythm_events"], seed["rhythm_events"])
        built = build_span_exercise(_iivi(), changed, length="standard")
        on = {e.onset for e in _notes(built)}
        self.assertTrue({e.onset for e in _notes(changed)} <= on | {e.onset + e.duration / 2 for e in _notes(changed)})
        self.assertEqual(motif_identity(changed, built)["skeleton"], 1.0)


class TestChangeRhythmStaysMotivic(unittest.TestCase):
    def test_bars_with_the_same_note_count_share_one_cell(self) -> None:
        for level in LEVELS:
            m = build_span_exercise(_iivi(), generate_span_motif(_iivi(), level=level, seed=2, style="pop"))
            cur = m
            for _ in range(3):
                cur = cycle_span_rhythm(cur)
                self.assertEqual(cur["midi"], m["midi"])
                self.assertEqual(note_chord_assignment(cur), m["note_chord_index"])
                counts = cur["rhythm_meta"]["bar_counts"]
                sigs = _sigs(cur)
                for a in range(len(counts) - 1):
                    for b in range(a + 1, len(counts) - 1):
                        if counts[a] == counts[b]:
                            self.assertEqual(sigs[a], sigs[b], (level, cur["rhythm"]))


class TestStyle(unittest.TestCase):
    def _agg(self, style, level, n=10, focus=""):
        agg = collections.defaultdict(list)
        span = _iivi()
        for i in range(n):
            seed = generate_span_motif(span, level=level, seed=50 + i, style=style, focus=focus)
            for m in (seed, build_span_exercise(span, seed)):
                for k, v in m["rhythm_profile"].items():
                    agg[k].append(v)
                outside = sum(
                    1 for x, ci in zip(m["midi"], m["note_chord_index"])
                    if x % 12 not in build_context("F", m["chord_timeline"][ci]["chord"]).scale_pcs
                )
                agg["outside"].append(outside / len(m["midi"]))
                agg["per_bar"].append(len(m["midi"]) / 4)
        return {k: statistics.mean(v) for k, v in agg.items()}

    def test_pop_is_far_less_syncopated_and_chromatic_than_jazz(self) -> None:
        for level in ("Intermediate", "Advanced"):
            pop, jazz = self._agg("pop", level), self._agg("jazz", level)
            self.assertLess(pop["syncopation"], 0.5 * jazz["syncopation"] + 1e-9, (level, pop, jazz))
            self.assertLessEqual(pop["outside"], jazz["outside"], level)
            self.assertEqual(pop["triplets"], 0.0, level)

    def test_pop_builds_add_no_chromatic_notes(self) -> None:
        for level in LEVELS:
            for i in range(6):
                seed = generate_span_motif(_iivi(), level=level, seed=i, style="pop")
                built = build_span_exercise(_iivi(), seed)
                for k, x in enumerate(built["midi"]):
                    if k in built["seed_note_indices"]:
                        continue
                    ctx = build_context("F", built["chord_timeline"][built["note_chord_index"][k]]["chord"])
                    self.assertIn(x % 12, ctx.scale_pcs, (level, i, built["notes"]))

    def test_ballad_has_space_and_no_busy_figures(self) -> None:
        for level in LEVELS:
            ballad, jazz = self._agg("ballad", level), self._agg("jazz", level)
            self.assertGreater(ballad["long"], jazz["long"], level)
            self.assertLessEqual(ballad["per_bar"], jazz["per_bar"], level)
            self.assertEqual(ballad["sixteenths"], 0.0)
            self.assertLess(ballad["syncopation"], 0.05)

    def test_jazz_syncopation_is_motivic_not_random(self) -> None:
        for i in range(10):
            m = generate_span_motif(_iivi(), level="Advanced", seed=i, style="jazz")
            sigs = _sigs(m)
            sync_bars = [b for b, s in enumerate(sigs[:-1]) if any(_crosses(RhythmEvent(o, d, d)) for o, d, *_ in s)]
            if sync_bars:
                # A syncopated cell recurs: it is the motif, not a one-off accent.
                self.assertGreaterEqual(len(sync_bars), 2, (i, m["rhythm"]))


class TestPracticeFocus(unittest.TestCase):
    def test_pentatonics_names_the_actual_collection(self) -> None:
        named = 0
        for i in range(10):
            m = generate_span_motif(_iivi(), level="Intermediate", seed=i, style="pop", focus="Pentatonics",
                                    vocabulary="pentatonic_cell")
            ex = explain_span_motif(m, key="F")
            for block in ex["chords"]:
                col = block["collection"]
                if col and col["kind"] == "pentatonic":
                    named += 1
                    ctx = build_context("F", m["chord_timeline"][block["index"]]["chord"])
                    self.assertEqual(set(col["pcs"]), set(_pentatonic(ctx)))
                    self.assertEqual(len(col["notes"]), 5)
                    for row in block["notes"]:
                        if row["function"] not in ("enclosure", "chromatic approach", "step into the change"):
                            self.assertIn(m["midi"][row["index"]] % 12, col["pcs"])
        self.assertGreater(named, 10)
        fmaj = build_context("F", "Fmaj7")
        names = [n for n in (fmaj.name_for_pc(p) for p in _pentatonic(fmaj))]
        self.assertEqual(sorted(names), sorted(["F", "G", "A", "C", "D"]))

    def test_guide_tone_focus_produces_guide_tone_voice_leading(self) -> None:
        kinds = collections.Counter()
        for i in range(10):
            m = build_span_exercise(_iivi(), generate_span_motif(_iivi(), level="Intermediate", seed=i, focus="Guide Tones"))
            for item in explain_span_motif(m, key="F")["voice_leading"]:
                kinds.update(item["kinds"])
        self.assertGreater(kinds["7→3"] + kinds["common_tone"], 10, kinds)

    def test_syncopation_focus_increases_syncopation_but_pop_stays_modest(self) -> None:
        jazz_plain, jazz_sync = self._sync("jazz", ""), self._sync("jazz", "Syncopation")
        pop_sync = self._sync("pop", "Syncopation")
        self.assertGreater(jazz_sync, jazz_plain)
        self.assertLess(pop_sync, jazz_sync)

    def _sync(self, style, focus):
        return statistics.mean(
            generate_span_motif(_iivi(), level="Intermediate", seed=200 + i, style=style, focus=focus)["rhythm_profile"]["syncopation"]
            for i in range(16)
        )

    def test_scales_focus_is_mostly_stepwise(self) -> None:
        for i in range(6):
            m = build_span_exercise(_iivi(), generate_span_motif(_iivi(), level="Intermediate", seed=i, focus="Scales",
                                                                 vocabulary="scalar_fragment"))
            steps = [abs(a - b) for a, b in zip(m["midi"], m["midi"][1:])]
            self.assertGreaterEqual(sum(1 <= d <= 2 for d in steps) / len(steps), 0.6, m["notes"])

    def test_focus_is_a_bias_not_an_override(self) -> None:
        # Beginner + Bebop stays diatonic and straight; harmony stays authoritative.
        for i in range(6):
            m = build_span_exercise(_iivi(), generate_span_motif(_iivi(), level="Beginner", seed=i, focus="Bebop Phrasing", style="jazz"))
            prof = m["rhythm_profile"]
            self.assertEqual((prof["syncopation"], prof["triplets"], prof["sixteenths"]), (0, 0, 0))
            for x, ci in zip(m["midi"], m["note_chord_index"]):
                self.assertIn(x % 12, build_context("F", m["chord_timeline"][ci]["chord"]).scale_pcs)


class TestExplanationsAreTrue(unittest.TestCase):
    """Every explanation claim is checked against the notes it describes."""

    def _cases(self):
        spans = [(_iivi(), "F"), (_span(["Dm7", "G7", "Cmaj7"], "C"), "C"), (_span(["Gm7", "Gb7", "Fmaj7"], "F"), "F"),
                 (_span(["Bm7b5", "E7", "Am"], "Am"), "Am")]
        for span, key in spans:
            for level in LEVELS:
                for i in range(3):
                    seed = generate_span_motif(span, level=level, seed=i, style="jazz")
                    yield key, seed, None
                    yield key, build_span_exercise(span, seed), seed
                    yield key, build_span_exercise(span, seed, length="extended"), seed

    def test_roles_collections_voice_leading_and_rhythm_claims_hold(self) -> None:
        for key, m, seed in self._cases():
            ex = explain_span_motif(m, key=key, seed_motif=seed)
            evs = _notes(m)
            for block in ex["chords"]:
                ctx = build_context(key, m["chord_timeline"][block["index"]]["chord"])
                for row in block["notes"]:
                    pc = m["midi"][row["index"]] % 12
                    self.assertEqual(row["role"], degree_label(ctx, pc))
                    if row["role"] in ("3rd", "7th", "root", "5th") and row["chord_tone"]:
                        self.assertIn(pc, ctx.chord_pcs)
                    if row["function"] == "enclosure":
                        t = next(k for k in range(row["index"] + 1, len(m["midi"]))
                                 if k in {s["first_note"] for s in m["chord_timeline"]})
                        self.assertLessEqual(abs(m["midi"][row["index"]] - m["midi"][t]), 2)
                    if row["function"] == "chromatic approach":
                        self.assertNotIn(pc, ctx.scale_pcs)
                col = block["collection"]
                if col and col["kind"] == "color":
                    self.assertTrue(block["evidence"], "a colour is named only with notes from it")
                    for k in range(m["chord_timeline"][block["index"]]["first_note"], m["chord_timeline"][block["index"]]["last_note"] + 1):
                        if pretty_name(m["notes"][k]) in block["evidence"]:
                            self.assertIn(m["midi"][k] % 12, col["pcs"])
                            self.assertNotIn(m["midi"][k] % 12, ctx.scale_pcs)
                if col and col["kind"] == "scale":
                    core = [r for r in block["notes"] if r["function"] not in ("enclosure", "chromatic approach")]
                    for r in core:
                        self.assertIn(m["midi"][r["index"]] % 12, col["pcs"], (block["chord"], col["name"], m["notes"]))
            for item in ex["voice_leading"]:
                a, b = m["midi"][item["from_index"]], m["midi"][item["to_index"]]
                if "chromatic_approach" in item["kinds"]:
                    self.assertEqual(abs(a - b), 1)
                if "common_tone" in item["kinds"]:
                    prev = build_context(key, m["chord_timeline"][item["from_chord"]]["chord"])
                    self.assertIn(b % 12, prev.chord_pcs)
            for r in ex["rhythm"]:
                if r["kind"] == "syncopation":
                    self.assertTrue(_crosses(evs[r["index"]]))
                if r["kind"] == "triplet":
                    self.assertIsNotNone(evs[r["index"]].tuplet)
                if r["kind"] == "long":
                    self.assertGreaterEqual(evs[r["index"]].duration, 2)

    def test_altered_and_lydian_dominant_are_spelled_from_the_chord_root(self) -> None:
        self.assertEqual(spell_from_root("C", ((0, 0), (1, 1), (3, 2), (4, 2), (6, 4), (8, 5), (10, 6))),
                         ["C", "Db", "Eb", "E", "Gb", "Ab", "Bb"])
        found = collections.Counter()
        for key, m, _seed in self._cases():
            for block in explain_span_motif(m, key=key)["chords"]:
                col = block["collection"]
                if col and col["kind"] == "color":
                    found[col["color"]] += 1
                    if col["color"] == "lydian_dominant":
                        self.assertEqual(col["notes"][:4], ["G♭", "A♭", "B♭", "C"])  # Gb7: Gb Ab Bb C …
        self.assertTrue({"altered", "diminished", "whole_tone"} & set(found), found)
        self.assertIn("lydian_dominant", found)

    def test_level_controls_detail(self) -> None:
        seed_b = generate_span_motif(_iivi(), level="Beginner", seed=1, style="jazz")
        seed_a = generate_span_motif(_iivi(), level="Advanced", seed=1, style="jazz")
        beg = sum(len(b.splitlines()) for b in explanation_markdown(explain_span_motif(seed_b, key="F")))
        adv = sum(len(b.splitlines()) for b in explanation_markdown(explain_span_motif(seed_a, key="F")))
        self.assertLess(beg, adv)
        self.assertLessEqual(beg, 22)

    def test_written_key_explanation_matches_the_written_notes(self) -> None:
        seed = generate_span_motif(_iivi(), level="Intermediate", seed=4, style="jazz")
        built = build_span_exercise(_iivi(), seed)
        alto = project_span_motif(built, semitones=9, chart_key="D",
                                  project_chord=lambda c: {"Gm7": "Em7", "C7": "A7", "Fmaj7": "Dmaj7"}[c])
        concert = explain_span_motif(built, key="F", seed_motif=seed)
        written = explain_span_motif(alto, key="D", chords=["Em7", "A7", "Dmaj7"], seed_motif=seed)
        self.assertEqual([b["chord"] for b in written["chords"]], ["Em7", "A7", "Dmaj7"])
        for cb, wb in zip(concert["chords"], written["chords"]):
            self.assertEqual([r["role"] for r in cb["notes"]], [r["role"] for r in wb["notes"]])
            self.assertEqual([r["function"] for r in cb["notes"]], [r["function"] for r in wb["notes"]])
            self.assertEqual([r["name"] for r in wb["notes"]], [pretty_name(alto["notes"][r["index"]]) for r in wb["notes"]])


class TestUiCard(unittest.TestCase):
    def test_build_card_marks_seed_notes_and_explains_locally(self) -> None:
        from tests.test_mc2_span_motif_ui import SPAN_MOTIF_STATE_KEY, _render

        ss: dict = {}
        _render(ss, {"improv_span_gen"})
        st = _render(ss, {"improv_span_build"})
        text = "\n".join(st.text)
        self.assertIn("Motif identity", text)
        self.assertIn("**Harmony & melody**", text)
        self.assertIn("**Voice leading**", text)
        self.assertIn("**Rhythm**", text)
        self.assertIn("**Where the seed is**", text)
        built = ss[SPAN_MOTIF_STATE_KEY]["current"]
        first = pretty_name(built["notes"][built["seed_note_indices"][0]])
        self.assertIn(f"**{first}**", text)
        self.assertNotIn("Vocabulary:", text)


def pretty_name(n: str) -> str:
    return n[:1] + n[1:].replace("#", "♯").replace("b", "♭")


if __name__ == "__main__":
    unittest.main()
