"""AMI Slice 3: articulation and dynamics are structured, canonical properties of a GeneratedExercise."""

from __future__ import annotations

import json
import unittest

from improvisation_motif import build_motif_abc
from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY, SELECTED_TRANSPOSING_INSTRUMENT_KEY
from music_coach_ami.exercise_expression import (
    ABC_CAPABILITY,
    LEVELS,
    apply_expression,
    expression_abc,
    has_rules,
    merge_requests,
    note_onsets,
    parse_expression,
    role_indices,
    summary_lines,
    vary_request,
)
from music_coach_ami.exercise_model import ActiveContext, ExerciseIntent, GeneratedExercise
from tests.test_ami_exercise_followups import Conv


def rules(question):
    r = parse_expression(question)
    return r["articulation"], r["dynamics"], r


def exercise(chord_roles, *, notes=None, midi=None, meter="4/4", onsets=None):
    """A hand-built canonical exercise (quarter notes unless onsets are given) for deterministic rule tests."""
    n = len(chord_roles)
    notes = notes or ["C"] * n
    midi = midi or [60 + i for i in range(n)]
    onsets = onsets or list(range(n))
    events = [{"on": str(o), "dur": "1", "w": "1", "rest": False, "tup": None, "ts": False, "n": i} for i, o in enumerate(onsets)]
    return GeneratedExercise(
        id="t", intent=ExerciseIntent(), context=ActiveContext(), engine="test", vocabulary="pentatonic", notes=notes, midi=midi,
        rhythm_events=events, meter=meter, bars=max(1, int(max(onsets) // 4) + 1), chord_roles=list(chord_roles),
        roles=["1"] * n, chord_assignment=[0] * n, chords=["Am7"], articulation=[""] * n, dynamics=[""] * n,
        accents=[False] * n, slur_groups=[0] * n, chord="Am7",
    )


class TestArticulationParser(unittest.TestCase):
    def test_global_and_grouped_articulation(self) -> None:
        self.assertEqual(rules("Make it staccato")[0], [{"rule": "all", "art": "staccato"}])
        self.assertEqual(rules("Slur every two notes")[0], [{"rule": "slur_groups", "size": 2}])
        self.assertEqual(rules("Slur each pair")[0], [{"rule": "slur_groups", "size": 2}])
        self.assertEqual(rules("Use slurs over each four-note group")[0], [{"rule": "slur_groups", "size": 4}])
        self.assertEqual(rules("Make it legato")[0], [{"rule": "legato"}])
        self.assertEqual(rules("Accent every third note")[0], [{"rule": "every_nth", "n": 3, "mark": "accent"}])
        self.assertEqual(rules("Accent beat 1")[0], [{"rule": "beat", "beat": 1, "mark": "accent"}])
        self.assertEqual(rules("Alternate tongued and slurred notes")[0], [{"rule": "alternate"}])

    def test_role_aware_phrases(self) -> None:
        self.assertEqual(rules("Accent the guide tones")[0], [{"rule": "role", "role": "guide_tone", "mark": "accent"}])
        art, dyn, _ = rules("Make the approach notes light and accent the target notes")
        self.assertIn({"rule": "role", "role": "approach", "mark": "staccato"}, art)
        self.assertIn({"rule": "role", "role": "target", "mark": "accent"}, art)
        self.assertIn({"rule": "role_delta", "role": "approach", "delta": -1}, dyn)
        art, _d, _ = rules("Slur each pair and accent the guide-tone destinations")
        self.assertIn({"rule": "role", "role": "guide_tone&destination", "mark": "accent"}, art)
        self.assertIn({"rule": "slur_groups", "size": 2}, art)
        art, _d, _ = rules("with staccato approach notes")
        self.assertEqual(art, [{"rule": "role", "role": "approach", "mark": "staccato"}])         # not also staccato everywhere

    def test_variety_and_additive_requests(self) -> None:
        self.assertEqual(rules("Give me the same pattern with different articulation")[2]["vary"], "articulation")
        self.assertEqual(rules("Give me another dynamic shape")[2]["vary"], "dynamics")
        self.assertEqual(rules("Add accents to the guide tones")[2]["mode"], "add")
        self.assertEqual(rules("Make it staccato")[2]["mode"], "replace")

    def test_non_expression_text_has_no_rules(self) -> None:
        for q in ("What is a pentatonic scale in F", "Give me an A minor pentatonic line", "Move it up", "Another one"):
            self.assertFalse(has_rules(parse_expression(q)), q)


class TestDynamicsParser(unittest.TestCase):
    def test_levels_ramps_and_hairpins(self) -> None:
        self.assertEqual(rules("Start piano and end forte")[1], [{"rule": "ramp", "from": "p", "to": "f"}])
        self.assertEqual(rules("starting p and crescendo to f")[1], [{"rule": "ramp", "from": "p", "to": "f"}])
        self.assertEqual(rules("starting mp and crescendo to f")[1], [{"rule": "ramp", "from": "mp", "to": "f"}])
        self.assertEqual(rules("Crescendo through the phrase")[1], [{"rule": "hairpin", "dir": "crescendo"}])
        self.assertEqual(rules("Make it diminuendo instead")[1], [{"rule": "hairpin", "dir": "diminuendo"}])
        self.assertEqual(rules("crescendo to ff")[1], [{"rule": "ramp", "from": "mf", "to": "ff"}])

    def test_bars_and_role_levels(self) -> None:
        self.assertEqual(rules("Make the first bar mp and the second bar f")[1], [{"rule": "bars", "levels": ["mp", "f"]}])
        dyn = rules("Make the tension note louder and the resolution softer")[1]
        self.assertEqual(dyn, [{"rule": "role_delta", "role": "tension", "delta": 1}, {"rule": "role_delta", "role": "resolution", "delta": -1}])

    def test_combined_request(self) -> None:
        art, dyn, _ = rules("Give me an A minor pentatonic line, staccato, starting mp and crescendo to f")
        self.assertEqual(art, [{"rule": "all", "art": "staccato"}])
        self.assertEqual(dyn, [{"rule": "ramp", "from": "mp", "to": "f"}])


class TestStructuredExpression(unittest.TestCase):
    def test_slur_groups_are_pairs_with_an_unslurred_remainder(self) -> None:
        ex = exercise(["R"] * 5)
        apply_expression(ex, parse_expression("slur every two notes"))
        self.assertEqual(ex.slur_groups, [1, 1, 2, 2, 0])
        ex3 = exercise(["R"] * 6)
        apply_expression(ex3, parse_expression("slur every three notes"))
        self.assertEqual(ex3.slur_groups, [1, 1, 1, 2, 2, 2])

    def test_legato_slurs_each_bar_and_alternate_pairs_tongue_then_slur(self) -> None:
        ex = exercise(["R"] * 8, onsets=[0, 1, 2, 3, 4, 5, 6, 7])
        apply_expression(ex, parse_expression("make it legato"))
        self.assertEqual(ex.slur_groups, [1, 1, 1, 1, 2, 2, 2, 2])
        ex2 = exercise(["R"] * 6)
        apply_expression(ex2, parse_expression("alternate tongued and slurred notes"))
        self.assertEqual(ex2.slur_groups, [0, 0, 1, 1, 0, 0])
        self.assertEqual(ex2.articulation, ["tongued", "tongued", "", "", "tongued", "tongued"])

    def test_positional_rules_use_the_rhythm(self) -> None:
        ex = exercise(["R"] * 6, onsets=[0, 1, 2, 3, 4, 6])
        apply_expression(ex, parse_expression("accent beat 1"))
        self.assertEqual(ex.accents, [True, False, False, False, True, False])          # onsets 0 and 4 start a bar
        apply_expression(ex, parse_expression("accent every third note"))
        self.assertEqual(ex.accents, [False, False, True, False, False, True])
        self.assertEqual(note_onsets(ex)[5], 6)

    def test_role_aware_accents_use_chord_roles_not_note_names(self) -> None:
        ex = exercise(["R", "", "3", "5", "7", ""], notes=["X"] * 6)               # note names are meaningless here
        apply_expression(ex, parse_expression("accent the guide tones"))
        self.assertEqual(ex.accents, [False, False, True, False, True, False])
        self.assertEqual(ex.expression["roles_used"], {"guide tones": 2})
        self.assertEqual(role_indices(ex, "chord_tone"), [0, 2, 3, 4])
        self.assertEqual(role_indices(ex, "tension"), [1, 5])
        self.assertEqual(role_indices(ex, "approach"), [1])                         # tension note one step from a chord tone
        self.assertEqual(role_indices(ex, "resolution"), [2])
        self.assertEqual(role_indices(ex, "destination"), [3, 5])                   # last note of each bar

    def test_approach_and_target_with_light_approach_notes(self) -> None:
        ex = exercise(["R", "", "3", "", "5"], midi=[60, 61, 64, 66, 67])
        apply_expression(ex, parse_expression("make the approach notes light and accent the target notes"))
        self.assertEqual(ex.articulation[1], "")                                    # 61 -> 64 is a leap, so not an approach note
        self.assertEqual(ex.articulation[3], "staccato")                            # 66 -> 67 is a step into a chord tone
        self.assertTrue(ex.accents[0] and ex.accents[2] and ex.accents[4])
        self.assertEqual(ex.dynamics[3], "mp")                                      # "light" also softens one step from mf
        self.assertEqual(ex.dynamics[2], "mf")

    def test_a_role_that_matches_nothing_is_reported_not_invented(self) -> None:
        ex = exercise(["R", "5", "R", "5"])
        apply_expression(ex, parse_expression("staccato approach notes"))
        self.assertEqual(ex.articulation, [""] * 4)
        self.assertEqual(ex.expression["unmatched"], ["approach notes"])
        self.assertIn("none in this line", ex.expression["summary"]["articulation"])
        self.assertTrue(any("No approach notes" in line for line in summary_lines(ex)))

    def test_dynamic_curves(self) -> None:
        ex = exercise(["R"] * 5)
        apply_expression(ex, parse_expression("start p and crescendo to f"))
        self.assertEqual(ex.dynamics, ["p", "mp", "mp", "mf", "f"])
        self.assertEqual([m["type"] for m in ex.dynamic_marks], ["level", "hairpin", "level"])
        self.assertEqual(ex.dynamic_marks[1], {"type": "hairpin", "dir": "crescendo", "start": 0, "end": 4, "from": "p", "to": "f"})
        apply_expression(ex, parse_expression("diminuendo"))
        self.assertEqual((ex.dynamics[0], ex.dynamics[-1]), ("f", "mp"))
        levels = [LEVELS.index(x) for x in ex.dynamics]
        self.assertEqual(levels, sorted(levels, reverse=True))
        ex2 = exercise(["R"] * 6, onsets=[0, 1, 2, 4, 5, 6])
        apply_expression(ex2, parse_expression("first bar mp and second bar f"))
        self.assertEqual(ex2.dynamics, ["mp", "mp", "mp", "f", "f", "f"])
        self.assertEqual([(m["at"], m["level"]) for m in ex2.dynamic_marks], [(0, "mp"), (3, "f")])

    def test_tension_and_resolution_levels(self) -> None:
        ex = exercise(["R", "", "R", "", "5"], midi=[60, 61, 64, 66, 67])
        apply_expression(ex, parse_expression("make the tension note louder and the resolution softer"))
        self.assertEqual(ex.dynamics[1], "f")                                       # tension: mf + 1
        self.assertEqual(ex.dynamics[2], "mp")                                      # resolution: mf - 1
        self.assertEqual(ex.dynamics[0], "mf")

    def test_combined_articulation_and_dynamics_is_one_coherent_object(self) -> None:
        ex = exercise(["R", "3", "5", "7"])
        apply_expression(ex, parse_expression("staccato, starting mp and crescendo to f, accent beat 1"))
        self.assertEqual(ex.articulation, ["staccato"] * 4)
        self.assertEqual(ex.accents, [True, False, False, False])
        self.assertEqual((ex.dynamics[0], ex.dynamics[-1]), ("mp", "f"))
        for field in (ex.articulation, ex.accents, ex.slur_groups, ex.dynamics):
            self.assertEqual(len(field), 4)
        json.dumps(ex.to_dict())

    def test_merge_and_vary_are_deterministic(self) -> None:
        parent = parse_expression("staccato, crescendo")
        replaced = merge_requests(parent, parse_expression("make it legato"))
        self.assertEqual(replaced["articulation"], [{"rule": "legato"}])
        self.assertEqual(replaced["dynamics"], parent["dynamics"])                  # dynamics untouched
        added = merge_requests(parse_expression("staccato"), parse_expression("add accents to the guide tones"))
        self.assertEqual(len(added["articulation"]), 2)
        self.assertEqual(vary_request(parent, "articulation", 3), vary_request(parent, "articulation", 3))
        self.assertNotEqual(vary_request(parent, "articulation", 3)["articulation"], parent["articulation"])
        self.assertNotEqual(vary_request(parent, "dynamics", 0)["dynamics"], parent["dynamics"])


class TestNotation(unittest.TestCase):
    def test_every_marking_has_an_abc_form(self) -> None:
        ex = exercise(["R"] * 6)
        apply_expression(ex, parse_expression("start p and crescendo to f, accent every third note, slur each pair"))
        abc = expression_abc(ex)
        self.assertEqual(abc["slur_open"], [True, False, True, False, True, False])
        self.assertEqual(abc["slur_close"], [False, True, False, True, False, True])
        self.assertEqual(abc["pre"][0], "!p!!crescendo(!")
        self.assertEqual(abc["pre"][5], "!crescendo)!!f!!accent!")
        self.assertIn("!accent!", abc["pre"][2])
        ex2 = exercise(["R"] * 3)
        apply_expression(ex2, parse_expression("make it staccato"))
        self.assertEqual(expression_abc(ex2)["pre"], [".", ".", "."])                 # the dot form: !staccato! warns in abcjs
        ex3 = exercise(["R"] * 4)
        apply_expression(ex3, parse_expression("alternate tongued and slurred notes"))
        self.assertEqual(expression_abc(ex3)["slur_open"], [False, False, True, False])      # tongued = no glyph
        self.assertTrue(any("no symbol" in line for line in summary_lines(ex3)))

    def test_the_shared_abc_builder_is_unchanged_without_expression(self) -> None:
        motif = {"chord": "Am7", "notes": ["A", "C", "E", "G"], "midi": [69, 72, 76, 79], "rhythm_symbols": ["♩"] * 4, "meter": "4/4"}
        plain = build_motif_abc(dict(motif), key_center="Am", bpm=96, title="t", clef="treble")
        self.assertEqual(plain, build_motif_abc(dict(motif, expression_abc={}), key_center="Am", bpm=96, title="t", clef="treble"))
        marked = build_motif_abc(dict(motif, expression_abc={"pre": ["!p!", "", "", ""], "slur_open": [True, False, False, False],
                                                             "slur_close": [False, True, False, False]}),
                                 key_center="Am", bpm=96, title="t", clef="treble")
        self.assertIn("(!p!A", marked)
        self.assertIn("C')", marked.replace(" ", ""))

    def test_capability_audit_is_explicit_about_playback(self) -> None:
        self.assertEqual(ABC_CAPABILITY["playback"]["ami_card"].split(" ")[0], "none")
        self.assertEqual(ABC_CAPABILITY["playback"]["abcjs_synth_if_a_player_were_added"]["staccato"], "no audible change")
        self.assertIn("raises velocity", ABC_CAPABILITY["playback"]["abcjs_synth_if_a_player_were_added"]["accent"])


class TestRequestsEndToEnd(unittest.TestCase):
    def test_new_requests_carry_structured_expression(self) -> None:
        c = Conv()
        ex = c.ask("Give me an A minor pentatonic line, staccato, starting mp and crescendo to f.")
        n = len(ex["notes"])
        self.assertEqual(ex["articulation"], ["staccato"] * n)
        self.assertEqual((ex["dynamics"][0], ex["dynamics"][-1]), ("mp", "f"))
        self.assertEqual(ex["dynamic_marks"][1]["dir"], "crescendo")
        self.assertIn(".A", c.resp.notation_abc.replace(" ", ""))
        self.assertIn("!crescendo(!", c.resp.notation_abc)
        self.assertIn("**Articulation:** staccato", c.resp.direct_answer)
        self.assertIn("**Dynamics:** mp → f crescendo", c.resp.direct_answer)
        self.assertEqual(ex["expression"]["source"], {"articulation": "explicit", "dynamics": "explicit"})

    def test_guide_tone_exercise_with_slurs_and_accented_destinations(self) -> None:
        c = Conv()
        ex = c.ask("Give me a guide-tone exercise over E7. Slur each pair and accent the guide-tone destinations.")
        self.assertTrue(any(ex["accents"]))
        self.assertTrue(any(ex["slur_groups"]))
        self.assertTrue(all(ex["chord_roles"][i] in ("3", "7") for i, a in enumerate(ex["accents"]) if a))
        self.assertIn("accent on guide-tone destinations", ex["expression"]["summary"]["articulation"])
        self.assertIn("two-note slurs", ex["expression"]["summary"]["articulation"])

    def test_blues_with_both_thirds_staccato_approach_notes_and_crescendo(self) -> None:
        c = Conv()
        ex = c.ask("Give me a C major blues line using the flat 3rd and natural 3rd, with staccato approach notes and a crescendo.")
        self.assertTrue(ex["explanation_facts"]["both_thirds_present"])
        self.assertIn("b3", ex["roles"])
        self.assertIn("3", ex["roles"])
        self.assertEqual(ex["dynamic_marks"][1]["dir"], "crescendo")
        approach = [i for i, a in enumerate(ex["articulation"]) if a == "staccato"]
        self.assertEqual(sorted(approach), sorted(role_indices(GeneratedExercise.from_dict(ex), "approach")))
        self.assertEqual(ex["expression"]["unmatched"], [])


class TestExpressionFollowUps(unittest.TestCase):
    def setUp(self) -> None:
        self.c = Conv()
        self.base = self.c.ask("Give me an A minor pentatonic line")

    def same_music(self, ex):
        self.assertEqual((ex["notes"], ex["midi"]), (self.base["notes"], self.base["midi"]))
        self.assertEqual(ex["rhythm_events"], self.base["rhythm_events"])
        self.assertEqual((ex["vocabulary"], ex["chord"], ex["collection_label"]), (self.base["vocabulary"], self.base["chord"], self.base["collection_label"]))
        self.assertEqual(ex["context"]["concert_key"], self.base["context"]["concert_key"])

    def test_make_it_staccato_changes_only_the_expression(self) -> None:
        ex = self.c.ask("Make it staccato.")
        self.assertFalse(self.c.failed)
        self.same_music(ex)
        self.assertEqual(ex["articulation"], ["staccato"] * len(ex["notes"]))
        self.assertEqual(ex["transform"]["kind"], "expression")
        self.assertEqual(ex["transform"]["changed"], ["articulation"])
        self.assertIn("notes", ex["transform"]["inherited"])
        self.assertIn("rhythm", ex["transform"]["inherited"])
        self.assertEqual(ex["parent_id"], self.base["id"])

    def test_legato_instead_replaces_and_a_crescendo_adds_a_dimension(self) -> None:
        self.c.ask("Make it staccato")
        legato = self.c.ask("Make it legato instead")
        self.assertEqual(set(legato["articulation"]), {""})                           # staccato gone
        self.assertTrue(any(legato["slur_groups"]))
        cresc = self.c.ask("Give it a crescendo")
        self.assertEqual(cresc["slur_groups"], legato["slur_groups"])                  # articulation kept
        self.assertEqual(cresc["dynamic_marks"][1]["dir"], "crescendo")
        self.assertEqual(cresc["transform"]["changed"], ["dynamics"])
        self.assertEqual(cresc["transform"]["expression"]["articulation_source"], "inherited")
        self.assertEqual(cresc["transform"]["expression"]["dynamics_source"], "explicit")

    def test_same_notes_and_rhythm_but_legato(self) -> None:
        ex = self.c.ask("Same notes and rhythm, but make it legato.")
        self.same_music(ex)
        self.assertTrue(any(ex["slur_groups"]))

    def test_add_accents_to_the_guide_tones_is_additive(self) -> None:
        c = Conv()
        base = c.ask("Give me a guide-tone pattern over E7, staccato")
        ex = c.ask("Add accents to the guide tones")
        self.assertEqual(ex["articulation"], ["staccato"] * len(ex["notes"]))          # kept
        self.assertTrue(all(ex["accents"]))                                             # added (every note is a guide tone)
        self.assertEqual(ex["midi"], base["midi"])

    def test_different_articulation_and_another_dynamic_shape_keep_pitches_and_rhythm(self) -> None:
        a = self.c.ask("Make it staccato")
        b = self.c.ask("Give me the same pattern with different articulation")
        self.same_music(b)
        self.assertNotEqual((b["articulation"], b["accents"], b["slur_groups"]), (a["articulation"], a["accents"], a["slur_groups"]))
        self.assertEqual(b["transform"]["changed"], ["articulation"])
        c1 = self.c.ask("Add a crescendo")
        c2 = self.c.ask("Give me another dynamic shape")
        self.same_music(c2)
        self.assertNotEqual(c2["dynamic_marks"], c1["dynamic_marks"])
        self.assertEqual(c2["transform"]["changed"], ["dynamics"])
        self.assertEqual(c2["articulation"], b["articulation"])                         # articulation untouched by a dynamics change

    def test_diminuendo_instead_keeps_notes_and_rhythm(self) -> None:
        self.c.ask("Give me a crescendo")
        ex = self.c.ask("Keep the notes and rhythm but make it diminuendo instead")
        self.same_music(ex)
        self.assertEqual(ex["dynamic_marks"][1]["dir"], "diminuendo")

    def test_a_pure_expression_follow_up_is_deterministic(self) -> None:
        other = Conv()
        other.ask("Give me an A minor pentatonic line")
        for q in ("Make it staccato", "Give me another dynamic shape", "Give me the same pattern with different articulation"):
            a, b = self.c.ask(q), other.ask(q)
            self.assertEqual((a["id"], a["articulation"], a["dynamics"], a["slur_groups"]), (b["id"], b["articulation"], b["dynamics"], b["slur_groups"]), q)


class TestExpressionAcrossTransforms(unittest.TestCase):
    def setUp(self) -> None:
        self.c = Conv()
        self.c.ask("Give me an A minor pentatonic line, slur every two notes, starting p and crescendo to f.")
        self.base = self.c.stored

    def expr_of(self, ex):
        return (ex["articulation"], ex["accents"], ex["slur_groups"], ex["dynamics"], ex["dynamic_marks"])

    def test_move_up_and_down_preserve_the_expression_while_the_pitches_change(self) -> None:
        up = self.c.ask("Move it up")
        self.assertNotEqual(up["midi"], self.base["midi"])
        self.assertEqual(self.expr_of(up), self.expr_of(self.base))
        self.assertEqual(up["expression"]["attached_by"], "note_index")
        self.assertEqual(up["transform"]["expression"]["how"], "carried by note position")
        down = self.c.ask("Move it down")
        self.assertEqual(down["midi"], self.base["midi"])
        self.assertEqual(self.expr_of(down), self.expr_of(self.base))
        self.assertEqual(expression_abc(GeneratedExercise.from_dict(down)), expression_abc(GeneratedExercise.from_dict(self.base)))

    def test_move_with_a_new_marking_applies_it(self) -> None:
        ex = self.c.ask("Move it up but keep it staccato")
        self.assertEqual(ex["articulation"], ["staccato"] * len(ex["notes"]))
        self.assertEqual(ex["dynamics"], self.base["dynamics"])                          # dynamics inherited

    def test_same_notes_new_rhythm_keeps_note_attached_marks(self) -> None:
        ex = self.c.ask("Keep the notes but change the rhythm")
        self.assertEqual(ex["midi"], self.base["midi"])
        self.assertNotEqual(ex["rhythm_events"], self.base["rhythm_events"])
        self.assertEqual(self.expr_of(ex), self.expr_of(self.base))                      # slur groups and the ramp follow the notes

    def test_beat_position_rules_are_re_evaluated_when_the_rhythm_changes(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line, accent beat 1")
        before = c.stored
        ex = c.ask("Keep the notes but change the rhythm")
        onsets = note_onsets(GeneratedExercise.from_dict(ex))
        bar = 4
        self.assertEqual([i for i, a in enumerate(ex["accents"]) if a], [i for i, o in enumerate(onsets) if o % bar == 0])
        self.assertEqual(ex["midi"], before["midi"])

    def test_same_rhythm_new_notes_re_applies_the_request(self) -> None:
        ex = self.c.ask("Keep the rhythm but change the notes")
        self.assertEqual(ex["rhythm_events"], self.base["rhythm_events"])
        self.assertNotEqual(ex["midi"], self.base["midi"])
        self.assertEqual(self.expr_of(ex), self.expr_of(self.base))                      # same count, same rules -> same marks
        self.assertEqual(ex["expression"]["request"], self.base["expression"]["request"])

    def test_easier_and_harder_keep_the_explicit_request(self) -> None:
        ex = self.c.ask("Make it harder")
        self.assertEqual(ex["expression"]["request"]["articulation"], [{"rule": "slur_groups", "size": 2}])
        self.assertEqual(ex["dynamics"][0], "p")
        self.assertEqual(ex["dynamics"][-1], "f")
        self.assertEqual(len(ex["slur_groups"]), len(ex["notes"]))

    def test_another_one_keeps_the_request_on_new_notes(self) -> None:
        ex = self.c.ask("Another one")
        self.assertNotEqual(ex["midi"], self.base["midi"])
        self.assertEqual(ex["expression"]["request"], self.base["expression"]["request"])
        self.assertEqual(ex["transform"]["expression"]["articulation_source"], "inherited")

    def test_sequence_extends_the_request_over_both_statements(self) -> None:
        ex = self.c.ask("Sequence it upward")
        n = len(self.base["notes"])
        self.assertEqual(len(ex["notes"]), 2 * n)
        self.assertEqual(len(ex["slur_groups"]), 2 * n)
        self.assertEqual((ex["dynamics"][0], ex["dynamics"][-1]), ("p", "f"))

    def test_provenance_explains_the_expression(self) -> None:
        ex = self.c.ask("Add accents to the guide tones")
        meta = ex["transform"]["expression"]
        self.assertEqual((meta["articulation_source"], meta["dynamics_source"]), ("explicit", "inherited"))
        self.assertTrue(meta["roles_used"])
        self.assertIn("accent on guide tones", meta["summary"]["articulation"])
        self.assertTrue(meta["dynamic_map"]["levels"])
        self.assertTrue(meta["capability"]["playback"].startswith("none"))
        self.assertEqual(ex["parent_id"], self.base["id"])


class TestWrittenKeyInvariance(unittest.TestCase):
    REQUEST = "Give me an A minor pentatonic line, accent every third note, slur each pair, starting p and crescendo to f."

    def test_expression_is_invariant_under_the_written_projection(self) -> None:
        concert = Conv().ask(self.REQUEST)
        for inst, subtype in (("Clarinet", "Bb Clarinet"), ("Saxophone", "Alto saxophone (Eb)")):
            c = Conv(instrument=inst, **{CHART_IN_INSTRUMENT_KEY_KEY: True, SELECTED_TRANSPOSING_INSTRUMENT_KEY: subtype})
            ex = c.ask(self.REQUEST)
            self.assertTrue(ex["written"]["applied"], inst)
            self.assertEqual(ex["midi"], concert["midi"], inst)                            # concert pitches identical
            for field in ("articulation", "accents", "slur_groups", "dynamics", "dynamic_marks"):
                self.assertEqual(ex[field], concert[field], (inst, field))
            self.assertNotEqual(ex["written"]["midi"], ex["midi"])
            # the accented note is the same note, just transposed
            i = ex["accents"].index(True)
            self.assertEqual(ex["written"]["midi"][i] % 12, (ex["midi"][i] + ex["written"]["semitones"]) % 12)
            abc = c.resp.notation_abc
            self.assertIn("!accent!", abc)
            self.assertIn("!crescendo(!", abc)

    def test_a_move_on_a_transposing_instrument_keeps_the_markings_on_the_same_notes(self) -> None:
        c = Conv(instrument="Clarinet", **{CHART_IN_INSTRUMENT_KEY_KEY: True, SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Bb Clarinet"})
        base = c.ask(self.REQUEST)
        up = c.ask("Move it up")
        for field in ("articulation", "accents", "slur_groups", "dynamics"):
            self.assertEqual(up[field], base[field], field)
        self.assertEqual(up["written"]["key"], "Bm")
        self.assertIn("K:Bm", c.resp.notation_abc)


class TestLegacyPathsUntouched(unittest.TestCase):
    def test_old_ami_generators_never_see_expression(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic pattern.")
        self.assertNotIn("exercise_bridge", c.diag)
        self.assertNotIn("!accent!", c.resp.notation_abc)

    def test_an_expression_follow_up_with_no_exercise_is_explained(self) -> None:
        c = Conv()
        c.ask("Make it staccato")
        self.assertTrue(c.failed)
        self.assertEqual(c.diag["exercise_followup_failure_reason"], "no_prior_exercise")

    def test_unrelated_questions_that_mention_dynamics_are_not_follow_ups(self) -> None:
        c = Conv()
        c.ask("Give me an A minor pentatonic line")
        c.ask("What does crescendo mean?")
        self.assertFalse(c.diag.get("exercise_followup"))


if __name__ == "__main__":
    unittest.main()
