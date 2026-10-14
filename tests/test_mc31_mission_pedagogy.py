"""MC3.1 — dynamic Practice Focus guidance, notation pedagogy, rhythm Mission, jazz colour and
endings, span presentation, responsive groups, span Backing handoff."""

from __future__ import annotations

import collections
import logging
import re
import unittest
from pathlib import Path

from harmonic_span_analyzer import analyze_harmonic_spans
from improvisation_motif import build_motif_abc
from mission_span_engine import MISSIONS_BY_ID, available_span_missions, generate_mission_span_example
from span_motif_engine import _ctx, generate_span_motif, rhythm_profile
from tests.abc_pitch_decoder import decode_abc_events, decode_abc_midis, note_markings

logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parents[1]


def span(chords, key, length=3):
    rows = [("A", list(chords) + ["A7"], list(chords) + ["A7"])]
    return analyze_harmonic_spans(rows, key_center=key, length=length, source_id="t")[0]


def iivi():
    return span(["Gm7", "C7", "Fmaj7"], "F")


def ex(mid, sp, level, variant="normal", *, style="jazz", idea=0, instrument="Alto Sax"):
    return generate_mission_span_example(MISSIONS_BY_ID[mid], sp, level=level, variant=variant, style=style,
                                         idea=idea, instrument=instrument)


# --------------------------------------------------------------------------- 1. focus helper


class TestDynamicFocusGuidance(unittest.TestCase):
    def setUp(self) -> None:
        from mission_focus_guidance import focus_guidance

        self.g = focus_guidance
        self.ch = ["Dm7", "G7", "Cmaj7"]

    def test_level_changes_the_language(self) -> None:
        beg = self.g(focus="Guide Tones", level="Beginner", instrument="Piano", style="jazz",
                     mission="Voice-lead the guide tones", scope="span3", chords=self.ch, relationship="ii_V_I")
        adv = self.g(focus="Guide Tones", level="Advanced", instrument="Piano", style="jazz",
                     mission="Voice-lead the guide tones", scope="span3", chords=self.ch, relationship="ii_V_I")
        self.assertIn("3rd and 7th", beg)
        self.assertIn("F & C", beg)  # Dm7's real guide tones
        self.assertNotIn("enclosure", beg.lower())
        self.assertIn("C → B into G7", adv)  # 7th → 3rd resolution, from the actual chords
        self.assertIn("enclosure", adv.lower())
        self.assertIn("G7", adv)  # altered colour only on the dominant, and only where it resolves

    def test_instrument_and_style_shape_the_line(self) -> None:
        kw = dict(focus="Guide Tones", level="Intermediate", style="jazz", mission="Target each chord change",
                  scope="span2", chords=["Dm7", "G7"], relationship="ii_V")
        self.assertIn("breath", self.g(instrument="Saxophone", **kw).lower())
        self.assertIn("position", self.g(instrument="Guitar", **kw).lower())
        self.assertIn("left hand", self.g(instrument="Piano", **kw).lower())
        jazz = self.g(focus="Strumming", level="Intermediate", instrument="Guitar", style="jazz", scope="single", chord="G7")
        pop = self.g(focus="Strumming", level="Intermediate", instrument="Guitar", style="pop", scope="single", chord="G")
        self.assertNotEqual(jazz, pop)
        self.assertIn("anticipation", jazz.lower())

    def test_mission_wins_over_focus(self) -> None:
        line = self.g(focus="Guide Tones", level="Intermediate", instrument="Guitar", style="jazz",
                      mission="Focus on rhythm over note choice", scope="span3", chords=self.ch, relationship="ii_V_I")
        self.assertIn("few pitches", line)
        self.assertIn("rhythm", line.lower())
        self.assertNotIn("decorate", line)

    def test_no_invented_function_and_concise(self) -> None:
        unknown = self.g(focus="Guide Tones", level="Advanced", instrument="Piano", style="pop",
                         mission="Target each chord change", scope="span2", chords=["C", "G"], relationship="")
        self.assertNotIn("ii", unknown)
        self.assertNotIn("7th", unknown)  # triads: talks about 3rds, not absent 7ths
        for focus in ("Guide Tones", "Articulation", "Dynamics", "Pentatonics", "Tone", "Walking Bass", "Ear Training"):
            for lvl in ("Beginner", "Intermediate", "Advanced"):
                line = self.g(focus=focus, level=lvl, instrument="Saxophone", style="jazz", mission="Target each chord change",
                              scope="span3", chords=self.ch, relationship="ii_V_I")
                self.assertLessEqual(len(re.findall(r"[.!?](\s|$)", line)), 3, line)
                self.assertLess(len(line), 330, line)

    def test_single_chord_scope_never_mentions_changes(self) -> None:
        line = self.g(focus="Guide Tones", level="Intermediate", instrument="Saxophone", style="jazz",
                      mission="Improvise using only chord tones", scope="single", chord="G7")
        self.assertIn("B and F", line)
        self.assertNotIn("each change", line)


# --------------------------------------------------------------------------- 5/6. notation


class TestExpressionInNotation(unittest.TestCase):
    def _abc(self, level, style, mission="target_each_change"):
        e = ex(mission, iivi(), level, style=style)
        m = e["motif"]
        return m, build_motif_abc(m, key_center="F", bpm=120, title="t")

    def test_articulation_marks_without_pitch_changes(self) -> None:
        from phrase_expression import apply_focus_expression

        for level in ("Beginner", "Intermediate", "Advanced"):
            for style in ("jazz", "pop", "ballad"):
                m, abc = self._abc(level, style)
                out, plan = apply_focus_expression(abc, m, focus="Articulation", level=level, instrument="Alto Sax", style=style)
                self.assertIsNotNone(plan, (level, style))
                self.assertEqual(decode_abc_midis(out), m["midi"])
                self.assertEqual([d for _m, d in decode_abc_events(out)], [d for _m, d in decode_abc_events(abc)])
                marks = note_markings(out)
                self.assertEqual(len(marks), len(m["midi"]))
                used = {d for mk in marks for d in mk["deco"]}
                self.assertTrue(used & {"!staccato!", "!accent!", "!tenuto!"} or any(mk["slur_open"] for mk in marks))
                self.assertTrue(used <= {"!staccato!", "!accent!", "!tenuto!"}, used)
                # Slurs pair up, cover ≥ 2 notes and never join two equal pitches (a tie lookalike).
                opens = [i for i, mk in enumerate(marks) if mk["slur_open"]]
                closes = [i for i, mk in enumerate(marks) if mk["slur_close"]]
                self.assertEqual(len(opens), len(closes))
                for a, b in zip(opens, closes):
                    self.assertLess(a, b)
                    self.assertFalse(b == a + 1 and m["midi"][a] == m["midi"][b])
                # The markings follow the generated phrase: they are the plan's notes, exactly.
                for i, mk in enumerate(marks):
                    self.assertEqual(set(mk["deco"]), set(plan.marks.get(i).deco if plan.marks.get(i) else []))

    def test_beginner_articulation_is_one_repeated_pattern(self) -> None:
        from phrase_expression import apply_focus_expression

        m, abc = self._abc("Beginner", "jazz")
        _out, plan = apply_focus_expression(abc, m, focus="Articulation", level="Beginner", instrument="Flute", style="jazz")
        self.assertIn("slur two", plan.summary)
        self.assertTrue(plan.slurs())

    def test_dynamics_form_a_phrase_contour(self) -> None:
        from phrase_expression import apply_focus_expression

        order = ["p", "mp", "mf", "f"]
        for level in ("Beginner", "Intermediate", "Advanced"):
            for style in ("jazz", "pop", "ballad"):
                m, abc = self._abc(level, style)
                out, plan = apply_focus_expression(abc, m, focus="Dynamics", level=level, instrument="Piano", style=style)
                self.assertEqual(decode_abc_midis(out), m["midi"])
                marks = note_markings(out)
                letters = [(i, d.strip("!")) for i, mk in enumerate(marks) for d in mk["deco"] if d.strip("!") in order]
                self.assertTrue(letters, (level, style))
                self.assertEqual(letters[0][0], 0, "the phrase opens with a dynamic")
                deco = [d for mk in marks for d in mk["deco"]]
                for kind in ("crescendo", "diminuendo"):
                    self.assertEqual(deco.count(f"!{kind}(!"), deco.count(f"!{kind})!"), deco)
                if level == "Beginner":
                    self.assertLessEqual(len(letters), 2)
                    self.assertNotIn("!crescendo(!", deco)
                else:
                    if max(m["midi"]) != m["midi"][0]:
                        self.assertIn("!crescendo(!", deco)  # the line grows toward its high point
                    # The loudest letter sits on the phrase's high point.
                    loud = max(letters, key=lambda t: order.index(t[1]))
                    self.assertEqual(m["midi"][loud[0]], max(m["midi"]))
                if style == "ballad":
                    self.assertNotIn("f", [l for _i, l in letters])
                self.assertLessEqual(len(letters), max(2, len(m["midi"]) // 3), "not cluttered")

    def test_no_markings_for_other_focuses_or_foreign_lines(self) -> None:
        from phrase_expression import apply_focus_expression

        m, abc = self._abc("Intermediate", "jazz")
        self.assertEqual(apply_focus_expression(abc, m, focus="Guide Tones", level="Intermediate", instrument="Sax")[0], abc)
        other = dict(m, midi=list(m["midi"])[:-1])
        self.assertEqual(apply_focus_expression(abc, other, focus="Dynamics", level="Intermediate", instrument="Sax")[0], abc)

    def test_mission_constraints_unchanged_by_focus_markings(self) -> None:
        from mission_span_engine import validate_mission_line
        from phrase_expression import apply_focus_expression

        e = ex("guide_tone_voice_leading", iivi(), "Intermediate")
        abc = build_motif_abc(e["motif"], key_center="F", bpm=110, title="t")
        out, _plan = apply_focus_expression(abc, e["motif"], focus="Articulation", level="Intermediate",
                                            instrument="Alto Sax", style="jazz")
        self.assertEqual(decode_abc_midis(out), e["motif"]["midi"])
        self.assertTrue(validate_mission_line(e["mission_id"], e["motif"], iivi(), level="Intermediate", style="jazz").valid)


# --------------------------------------------------------------------------- 7. rhythm Mission


def _distinct_per_chord(motif):
    tl = motif["chord_timeline"]
    return [len({m % 12 for m in motif["midi"][t["first_note"]: t["last_note"] + 1]}) for t in tl]


def _variety(motif):
    """Average distinct pitches per note, chord by chord (1.0 = every note different)."""
    tl = motif["chord_timeline"]
    ratios = []
    for t in tl:
        seg = motif["midi"][t["first_note"]: t["last_note"] + 1]
        ratios.append(len(set(seg)) / max(1, len(seg)))
    return sum(ratios) / len(ratios)


class TestRhythmMission(unittest.TestCase):
    def test_pitches_simpler_than_an_ordinary_mission(self) -> None:
        r_all, o_all = [], []
        for style in ("jazz", "pop", "ballad"):
            for level in ("Beginner", "Intermediate", "Advanced"):
                for idea in (0, 1, 2):
                    r = ex("rhythm_over_notes", iivi(), level, style=style, idea=idea)
                    o = ex("target_each_change", iivi(), level, style=style, idea=idea)
                    self.assertTrue(r["valid"], (style, level, idea, r["problems"]))
                    cap = 3 if level == "Beginner" else 4
                    self.assertTrue(all(n <= cap for n in _distinct_per_chord(r["motif"])), r["motif"]["display"])
                    # Pitch variety per note: never higher than an ordinary Mission, lower overall.
                    self.assertLessEqual(_variety(r["motif"]), _variety(o["motif"]), (style, level, idea))
                    r_all.append(_variety(r["motif"]))
                    o_all.append(_variety(o["motif"]))
                    self.assertTrue(any(ev["where"] == "pitches" for ev in r["evidence"]), r["evidence"])
        self.assertLess(sum(r_all) / len(r_all), sum(o_all) / len(o_all) - 0.2)

    def test_rhythm_carries_the_challenge_within_style(self) -> None:
        def lively(e):
            from melodic_rhythm_engine import events_from_json

            durs = {e.duration for e in events_from_json(e["motif"]["rhythm_events"]) if not e.rest}
            prof = rhythm_profile(e["motif"]["rhythm_events"], "4/4")
            return len(durs), prof

        for style in ("jazz", "pop", "ballad"):
            for level in ("Beginner", "Intermediate", "Advanced"):
                r = ex("rhythm_over_notes", iivi(), level, style=style)
                kinds, prof = lively(r)
                self.assertGreaterEqual(kinds, 2, (style, level, r["motif"]["rhythm"]))  # never plain quarters only
                if style == "ballad":
                    self.assertEqual(prof["syncopation"], 0.0, r["motif"]["rhythm"])
                if level == "Beginner":
                    self.assertEqual((prof["syncopation"], prof["triplets"], prof["sixteenths"]), (0, 0, 0))
        jazz = [rhythm_profile(ex("rhythm_over_notes", iivi(), lv, style="jazz", idea=i)["motif"]["rhythm_events"], "4/4")
                for lv in ("Intermediate", "Advanced") for i in range(3)]
        self.assertTrue(all(p["syncopation"] > 0 for p in jazz), jazz)

    def test_guide_tone_focus_still_lands_structural_notes(self) -> None:
        e = generate_mission_span_example(MISSIONS_BY_ID["rhythm_over_notes"], iivi(), level="Intermediate",
                                          style="jazz", focus="Guide Tones")
        self.assertTrue(e["valid"], e["problems"])
        for t in e["motif"]["chord_timeline"]:
            ctx = _ctx("F", t["chord"])
            self.assertIn(e["motif"]["midi"][t["first_note"]] % 12, ctx.chord_pcs)


# --------------------------------------------------------------------------- 8/9. jazz colour, endings


class TestJazzColourAndEndings(unittest.TestCase):
    def _motifs(self, level, style="jazz", seeds=16):
        for sp in (iivi(), span(["Dm7", "G7", "Cmaj7"], "C"), span(["Bm7b5", "E7", "Am7"], "Am")):
            for s in range(seeds):
                yield sp, generate_span_motif(sp, level=level, seed=s, style=style, instrument="Alto Sax")

    def test_advanced_colour_is_occasional_and_resolves(self) -> None:
        coloured = total = 0
        for sp, m in self._motifs("Advanced"):
            total += 1
            cols = m.get("advanced_colors") or []
            coloured += bool(cols)
            for c in cols:
                ctx = _ctx(sp.key_center, c["chord"])
                if c["color"] in ("altered", "diminished", "whole_tone"):
                    self.assertEqual(ctx.quality, "dom", c)
                if c["color"] == "lydian":
                    self.assertEqual(ctx.quality, "maj7", c)
                    self.assertNotIn((ctx.chord_pcs[0] + 6) % 12, ctx.scale_pcs)
            # Every outside note moves by step to its next note (it has a reason and a resolution);
            # inside a side-slip the borrowed fragment may continue outside before it steps back.
            slips = {c["chord_index"] for c in cols if c["color"] == "side_slip"}
            for k, kind in enumerate(m["note_kinds"]):
                if kind == "tension" and k + 1 < len(m["midi"]):
                    ci = m["note_chord_index"][k]
                    ctx = _ctx(sp.key_center, m["chord_timeline"][ci]["chord"])
                    if ci in slips and m["midi"][k + 1] % 12 not in ctx.scale_pcs:
                        continue
                    self.assertLessEqual(abs(m["midi"][k + 1] - m["midi"][k]), 2, m["display"])
        self.assertGreater(coloured, total * 0.2)
        self.assertLess(coloured, total * 0.9)

    def test_no_colour_outside_jazz_or_at_beginner(self) -> None:
        for sp, m in self._motifs("Beginner", seeds=6):
            self.assertFalse(m.get("advanced_colors"))
        for sp, m in self._motifs("Intermediate", style="pop", seeds=6):
            self.assertFalse(m.get("advanced_colors"))

    def test_explanations_name_outside_notes_precisely(self) -> None:
        from span_motif_explain import explain_span_motif, explanation_markdown

        seen = 0
        for sp, m in self._motifs("Advanced"):
            cols = {c["color"] for c in m.get("advanced_colors") or []} - {"side_slip"}
            if not cols:
                continue
            text = "\n".join(explanation_markdown(explain_span_motif(m, key=sp.key_center)))
            for line in text.splitlines():
                if "in the line:" in line and "side-slip" not in line:
                    seen += 1
                    inner = line.split("in the line:", 1)[1]
                    self.assertRegex(inner, r"= (♭9|♯9|♯11|♭13|13th|♭5|♯5|9th)")
        self.assertGreater(seen, 0)

    def test_extension_endings_sometimes_beginner_never(self) -> None:
        ext = {"9th", "6th", "13th", "11th", "major 7th", "7th"}
        from span_motif_explain import degree_label

        def endings(level, style="jazz"):
            out = collections.Counter()
            for sp, m in self._motifs(level, style=style):
                last_chord = m["chord_timeline"][-1]["chord"]
                out[degree_label(_ctx(sp.key_center, last_chord), m["midi"][-1] % 12)] += 1
            return out

        adv, inter, beg = endings("Advanced"), endings("Intermediate"), endings("Beginner")
        self.assertTrue(set(adv) & ext, adv)
        self.assertTrue(set(inter) & ext, inter)
        self.assertFalse({"9th", "6th", "13th", "11th"} & set(beg), beg)
        self.assertFalse({"9th", "6th", "13th", "11th"} & set(endings("Intermediate", style="pop")))

    def test_mission_resolution_beats_an_extension_ending(self) -> None:
        for idea in range(6):
            e = ex("resolve_to_third", iivi(), "Advanced", idea=idea)
            last = e["motif"]["chord_timeline"][-1]
            ctx = _ctx("F", last["chord"])
            self.assertIn(e["motif"]["midi"][-1] % 12, ctx.chord_pcs, e["motif"]["display"])
            self.assertTrue(e["valid"], e["problems"])


# --------------------------------------------------------------------------- 2/12/16. span display


class TestSpanPresentation(unittest.TestCase):
    def test_choice_keeps_everything_and_wraps(self) -> None:
        from span_choice_display import RECOMMENDED, span_card_html, span_choice, span_heading

        sp = span(["G#m7|C#7", "C#m7|F#7", "F#m7|B7"], "E")
        choice = span_choice(sp, include_section=True, recommended=True)
        self.assertEqual(choice.chords, "G#m7|C#7 → C#m7|F#7 → F#m7|B7")
        self.assertIn(RECOMMENDED, choice.meta)
        self.assertIn("A", choice.meta)  # section
        self.assertEqual(choice.label(), f"{choice.chords} · {choice.meta}")
        card = span_card_html(choice)
        self.assertIn('class="mc-span-chords"', card)
        self.assertIn('class="mc-span-meta"', card)
        self.assertIn("G#m7|C#7 → C#m7|F#7 → F#m7|B7", card)
        self.assertIn(RECOMMENDED, card)
        self.assertEqual(span_heading("ii–V–I", ["Dm7", "G7", "Cmaj7"]), "Span: ii–V–I")
        self.assertEqual(span_heading("", ["C", "Ab", "F"]), "Span: C → Ab → F")  # never invented
        css = __import__("creative_responsive_css").creative_responsive_css()
        self.assertIn("overflow-wrap: anywhere", css)

    def test_picker_label_format_unchanged(self) -> None:
        from harmonic_span_analyzer import span_display_label
        from span_choice_display import span_choice

        sp = iivi()
        self.assertEqual(span_choice(sp, include_section=True).label(), span_display_label(sp, include_section=True))


# --------------------------------------------------------------------------- 13/14/15. layout


class TestResponsiveLayout(unittest.TestCase):
    def test_every_button_group_is_a_phone_grid_and_keeps_its_buttons(self) -> None:
        from creative_responsive_css import BUTTON_GROUPS, creative_responsive_css

        css = creative_responsive_css()
        src = (ROOT / "improvisation_intelligence_ui.py").read_text(encoding="utf-8") + (
            ROOT / "mission_span_ui.py").read_text(encoding="utf-8")
        for group in BUTTON_GROUPS:
            self.assertIn(f".st-key-{group} [data-testid=\"stColumn\"]", css)
            self.assertIn(f'key="{group}"', src, group)
        expected = {
            "improv_mission_gen_actions": ("improv_mission_gen", "improv_mission_easier", "improv_mission_harder", "improv_mission_new"),
            "improv_mission_transforms": ("improv_mission_seq_up", "improv_mission_seq_down", "improv_mission_invert", "improv_mission_change_rhythm"),
            "improv_span_mission_actions": ("improv_span_mission_gen", "improv_span_mission_easier", "improv_span_mission_harder", "improv_span_mission_new"),
            "improv_span_motif_actions": ("improv_span_gen", "improv_span_new", "improv_span_easier", "improv_span_harder"),
        }
        for group, keys in expected.items():
            block = src.split(f'key="{group}"', 1)[1][:2600]
            for k in keys:
                self.assertIn(k, block, (group, k))
        self.assertIn("min-height: 2.75rem", css)  # comfortable touch targets
        self.assertIn("calc(50% - 0.45rem)", css)

    def test_title_drawn_as_wrapping_html_not_in_the_svg(self) -> None:
        import improvisation_intelligence_ui as ui

        abc = "X:1\nT:Mission: Create a phrase using a syncopated rhythm — Dm7\nM:4/4\nL:1/4\nK:C\nC D E F |"
        title, body = ui._split_abc_title(abc)
        self.assertEqual(title, "Mission: Create a phrase using a syncopated rhythm — Dm7")
        self.assertNotIn("T:", body)
        captured = {}

        class _C:
            @staticmethod
            def html(doc, height=None, scrolling=None):
                captured.update(doc=doc, height=height)

        orig = ui.components
        ui.components = _C
        try:
            ui._render_abc(None, abc, height=300)
        finally:
            ui.components = orig
        doc = captured["doc"]
        self.assertIn('<div class="abc-title">Mission: Create a phrase using a syncopated rhythm — Dm7</div>', doc)
        self.assertIn("overflow-wrap: anywhere", doc)
        self.assertIn("preferredMeasuresPerLine", doc)
        self.assertIn("overflow-x: hidden", doc)  # the frame never scrolls sideways
        self.assertNotIn("T:Mission", doc.split("renderAbc", 1)[1])
        self.assertGreaterEqual(captured["height"], 200)  # sized from the bar count


# --------------------------------------------------------------------------- 3. span Backing


class TestSpanMissionBacking(unittest.TestCase):
    def _session(self, **extra):
        s = {"instrument": "Piano", "concert_key": "F", "display_key": "F",
             "improv_mission_pick": "Improvise using only chord tones", "ii_selected_chord": "Gm7",
             "ii_selected_section": "A", "ii_selected_chord_index": 0}
        s.update(extra)
        return s

    def _start(self, s, lick=True):
        from mission_span_ui import start_span_mission_backing

        e = ex("target_each_change", iivi(), "Intermediate")
        e["handoff"]["practice_key"] = "F"
        start_span_mission_backing(s, example=e, heading="Span: ii–V–I", section_label="A", practice_key="F",
                                   with_practice_lick=lick, instrument="Piano", level="Intermediate", style="jazz",
                                   focus="Dynamics", bpm=120)
        return e

    def test_jam_goes_through_the_mission_handoff_and_loops_the_span(self) -> None:
        from backing_context import build_mission_context
        from music_workflow_mission_backing_click import peek_mission_backing_click_intent

        s = self._session()
        self._start(s)
        intent = peek_mission_backing_click_intent(s)
        self.assertEqual(intent["mission"], "Improvise using only chord tones")  # single-chord state, unchanged
        self.assertEqual(intent["cur_chord"], "Gm7")
        self.assertFalse(intent["with_practice_lick"])  # the span lick has its own payload
        self.assertTrue(s.get("improv_mission_backing_handoff"))  # Mission-owned handoff
        ctx = build_mission_context(s)
        self.assertEqual(ctx.source, "mission")
        self.assertEqual(ctx.scope, "Mission span")
        self.assertEqual(ctx.progression, ["Gm7", "C7", "Fmaj7"])
        self.assertEqual(ctx.mission_id, "Improvise using only chord tones")
        self.assertIn("Gm7 → C7 → Fmaj7", ctx.progression_label)
        self.assertEqual(s["ii_selected_chord"], "Gm7")  # Mission state isolation

    def test_written_key_projection_and_practice_key_follow(self) -> None:
        from mission_span_backing import active_span_backing, span_backing_progression

        s = self._session(instrument="Saxophone", saxophone_type="Alto saxophone (Eb)",
                          selected_transposing_instrument="Alto saxophone (Eb)", show_chart_in_instrument_key=True)
        self._start(s)
        payload = active_span_backing(s)
        self.assertEqual(span_backing_progression(s, payload, "F"), ["Em7", "A7", "Dmaj7"])  # alto charts in D
        self.assertEqual(span_backing_progression(s, payload, "G"), ["F#m7", "B7", "Emaj7"])  # Mission key moved to G

    def test_bars_repeat_in_the_loop(self) -> None:
        from mission_span_backing import span_backing_progression

        payload = {"active": True, "practice_key": "C", "timeline": [{"chord": "Dm7", "bars": 2}, {"chord": "G7", "bars": 1}]}
        self.assertEqual(span_backing_progression({"instrument": "Piano"}, payload, "C"), ["Dm7", "Dm7", "G7"])

    def test_one_chord_jam_clears_the_span(self) -> None:
        from mission_span_backing import SPAN_BACKING_KEY, SPAN_LICK_KEY, active_span_backing

        s = self._session()
        self._start(s)
        self.assertTrue(active_span_backing(s))
        self.assertIn(SPAN_LICK_KEY, s)
        src = (ROOT / "improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        block = src.split("def _mission_backing_on_click", 1)[1][:1200]
        self.assertIn("clear_span_backing(ss)", block)
        from mission_span_backing import clear_span_backing

        clear_span_backing(s)
        self.assertNotIn(SPAN_BACKING_KEY, s)
        self.assertNotIn(SPAN_LICK_KEY, s)

    def test_lick_payload_keeps_the_example_identity(self) -> None:
        from mission_span_backing import SPAN_LICK_KEY, active_span_backing

        s = self._session()
        e = self._start(s)
        lick = s[SPAN_LICK_KEY]
        self.assertEqual(lick["motif"]["midi"], e["motif"]["midi"])
        self.assertEqual(lick["example_id"], e["handoff"]["example_id"])
        self.assertEqual(active_span_backing(s)["span_id"], e["span_id"])
        s2 = self._session()
        self._start(s2, lick=False)
        self.assertNotIn(SPAN_LICK_KEY, s2)

    def test_example_follows_a_practice_key_change(self) -> None:
        from mission_span_ui import span_example_projection

        e = ex("target_each_change", iivi(), "Intermediate")
        e["handoff"]["practice_key"] = "F"
        moved = span(["Am7", "D7", "Gmaj7"], "G")
        shown, chords, abc_key, reread = span_example_projection(e, moved, concert_key="G", chart_key="G", project=lambda c: c)
        self.assertEqual(chords, ["Am7", "D7", "Gmaj7"])
        self.assertTrue(reread)
        self.assertEqual(abc_key, "G")
        self.assertEqual([b - a for a, b in zip(e["motif"]["midi"], shown["midi"])], [2] * len(shown["midi"]))
        self.assertEqual(decode_abc_midis(build_motif_abc(shown, key_center="G", bpm=100, title="t")), shown["midi"])


if __name__ == "__main__":
    unittest.main()
