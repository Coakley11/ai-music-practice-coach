"""Song-Aware Coaching S2 — the coaching plan engine (song_coach_plan)."""

from __future__ import annotations

import copy
import dataclasses
import json
import unittest
from functools import lru_cache

from music_theory import transpose_sections_dict
from song_coach_context import SOURCE_CATALOG, SOURCE_CUSTOM, build_song_coach_context
from song_coach_harmony import CADENCE_ENDINGS, HOLDABLE, chord_facts, note_use, signed_motion
from song_coach_plan import (
    BASIS_HARMONY,
    BASIS_PRACTICE,
    BASIS_STYLE,
    BEGINNER_JARGON,
    FOCUSES,
    FOCUS_CHORD_TONE,
    FOCUS_MELODIC,
    FOCUS_MOTIF,
    FOCUS_RHYTHMIC,
    FORBIDDEN_CLAIMS,
    KIND_CONNECT,
    KIND_IDEA,
    KIND_MOMENT,
    KIND_RHYTHM,
    KIND_ROADMAP,
    LEVELS,
    CoachingPlan,
    Line,
    build_coaching_plan,
    default_coaching_focus,
    normalize_focus,
    normalize_level,
    plan_text,
    validate_plan,
)
from song_coach_scope import build_scope, coach_sections, suggested_ranges


@lru_cache(maxsize=None)
def _record(title: str) -> dict:
    from song_catalog.catalog import curated_song_records

    return next(r for r in curated_song_records() if r["title"] == title)


def _catalog(title: str, key: str | None = None, style: str = "default", instrument: str = "Piano"):
    rec = copy.deepcopy(_record(title))
    concert = key or rec["key"]
    return build_song_coach_context(
        identity=f"catalog|{title}", source_kind=SOURCE_CATALOG,
        concert_sections=transpose_sections_dict(rec["sections"], rec["key"], concert), concert_key=concert,
        section_order=rec.get("section_order"), record=rec, reference_sections=rec["sections"], reference_key=rec["key"],
        style=style, instrument=instrument, meter=(rec.get("extensions") or {}).get("time_signature") or "4/4",
    )


def _custom(sections: dict, key: str, style: str = "default", meter: str = "4/4", instrument: str = "Saxophone"):
    return build_song_coach_context(identity="custom|custom::t", source_kind=SOURCE_CUSTOM, concert_sections=sections,
                                    concert_key=key, style=style, meter=meter, instrument=instrument)


BLUES = {"Blues": ["C7", "F7", "C7", "C7", "F7", "F7", "C7", "C7", "G7", "F7", "C7", "G7"]}
SPLIT = {"Verse": ["C:2|G:2", "Am", "Em:3.5|D:0.5p", "D", "N.C.", "G.hit", "C", "C"]}
VAMP = {"Vamp": ["Dm7"] * 8}

# (name, context factory, section id, start, end)
CASES = {
    "perfect": (lambda: _catalog("Perfect", style="ballad"), "verse-1", 1, 8),
    "ipanema": (lambda: _catalog("The Girl from Ipanema", style="bossa"), "a-section", None, None),
    "hotel": (lambda: _catalog("Hotel California", style="rock"), "verse-1a", 1, 8),
    "autumn": (lambda: _catalog("Autumn Leaves", style="jazz"), "verse-1", None, None),
    "blues": (lambda: _custom(BLUES, "C", style="blues"), "blues", None, None),
    "vamp": (lambda: _custom(VAMP, "Dm", style="funk"), "vamp", None, None),
    "split": (lambda: _custom(SPLIT, "G", style="pop"), "verse", None, None),
}


@lru_cache(maxsize=None)
def _case(name: str):
    factory, sid, start, end = CASES[name]
    ctx = factory()
    return ctx, build_scope(ctx, sid, start, end)


@lru_cache(maxsize=None)
def _plan(name: str, level: str = "Intermediate", focus: str = FOCUS_MOTIF) -> CoachingPlan:
    ctx, scope = _case(name)
    return build_coaching_plan(ctx, scope, level=level, focus=focus)


def _texts(plan: CoachingPlan) -> list[str]:
    return [ln.render() for ln in plan.all_lines()]


def _templates(plan: CoachingPlan) -> set[str]:
    return {ln.template for ch in plan.challenges for ln in ch.steps}


class TestCasesValidate(unittest.TestCase):
    def test_every_listed_case_validates_at_every_level_and_focus(self) -> None:
        for name in CASES:
            _ctx, scope = _case(name)
            for level in LEVELS:
                for focus in FOCUSES:
                    plan = _plan(name, level, focus)
                    self.assertEqual(validate_plan(plan, scope), [], (name, level, focus))
                    self.assertGreaterEqual(len(plan.challenges), 3, (name, level, focus))
                    self.assertLessEqual(len(plan.challenges), 6, (name, level, focus))
                    self.assertEqual(plan.challenges[0].kind, KIND_IDEA)
                    self.assertEqual(plan.challenges[-1].kind, KIND_ROADMAP)

    def test_endings_follow_the_chart(self) -> None:
        expected = {
            "perfect": "open_on_dominant",
            "ipanema": "open",
            "hotel": "open_on_dominant",
            "autumn": "authentic_cadence",
            "blues": "open_on_dominant",
            "vamp": "lands_home",
            "split": "open",
        }
        for name, kind in expected.items():
            self.assertEqual(_plan(name).ending, kind, name)

    def test_cadence_language_only_when_the_chart_has_one(self) -> None:
        for name in CASES:
            for level in LEVELS:
                plan = _plan(name, level, FOCUS_MELODIC)
                if any("cadence" in t.lower() for t in _texts(plan)):
                    self.assertIn(plan.ending, CADENCE_ENDINGS, (name, level))
        self.assertTrue(any("V–I cadence" in t for t in _texts(_plan("autumn", "Intermediate", FOCUS_MELODIC))))
        perfect = " ".join(_texts(_plan("perfect", "Beginner", FOCUS_MELODIC)))
        self.assertIn("let it hang", perfect)
        self.assertNotIn("comes home", perfect)


class TestSongSpecificCoaching(unittest.TestCase):
    def test_perfect_reads_cadd9_as_a_major_chord_with_a_ninth(self) -> None:
        plan = _plan("perfect", "Advanced", FOCUS_MELODIC)
        self.assertIn("Cadd9: not a dominant chord (no ♭7)", plan.reading_notes)
        connect = [c for c in _plan("perfect", "Beginner", FOCUS_MELODIC).challenges if c.kind == KIND_CONNECT]
        self.assertEqual(connect[0].chords, ("G", "Em7"))
        self.assertIn("G changes to Em7", connect[0].steps[0].render())

    def test_ipanema_follows_the_ii_subv_i(self) -> None:
        plan = _plan("ipanema", "Advanced", FOCUS_CHORD_TONE)
        line = next(c for c in plan.challenges if c.title == "Connect a chord sequence")
        self.assertEqual(line.chords, ("Gm7", "Gb7", "Fmaj7"))
        self.assertEqual([t.name for t in line.targets], ["D", "Db", "C"])
        self.assertTrue(any("ii–subV–I" in ln.render() for ln in line.steps))
        moment = next(c for c in plan.challenges if c.kind == KIND_MOMENT)
        self.assertIn("G7 brings in B", moment.steps[0].render())

    def test_autumn_leaves_seven_to_three(self) -> None:
        plan = _plan("autumn", "Intermediate", FOCUS_CHORD_TONE)
        connect = next(c for c in plan.challenges if c.kind == KIND_CONNECT)
        self.assertIn("move D → C#, down a half step: the 7th of Em7 becomes the 3rd of A7", connect.steps[1].render())
        guide = next(c for c in plan.challenges if c.title == "Connect through every change")
        self.assertIn("G → G → F# → F# → E → E → D", guide.steps[0].render())

    def test_blues_is_described_as_a_blues(self) -> None:
        plan = _plan("blues", "Beginner", FOCUS_MELODIC)
        text = " ".join(_texts(plan))
        self.assertEqual(plan.material.name, "C minor pentatonic")
        self.assertIn("the typical blues sound", text)
        self.assertNotIn("Outside the key of C", text)
        self.assertEqual([r.role for r in plan.roadmap], ["statement", "variation", "ending"])

    def test_vamp_and_breaks(self) -> None:
        vamp = _plan("vamp", "Intermediate", FOCUS_RHYTHMIC)
        self.assertFalse(any(c.kind == KIND_CONNECT for c in vamp.challenges))
        self.assertTrue(any("move the idea around the bar" in t for t in _texts(vamp)))
        split = _plan("split", "Advanced", FOCUS_MOTIF)
        brk = next(c for c in split.challenges if c.kind == KIND_MOMENT)
        self.assertEqual(brk.title, "Fill the break")
        self.assertIn("Bar 5 has no chord", brk.steps[0].render())
        self.assertTrue(any("the 'and' of beat 4 of bar 3" in t for t in _texts(split)))
        self.assertTrue(any("In bar 1, on beat 3, C changes to G" in t for t in _texts(split)))

    def test_roadmap_covers_every_bar_in_phrases(self) -> None:
        for name in CASES:
            plan = _plan(name, "Intermediate", FOCUS_MELODIC)
            rows = plan.roadmap
            self.assertEqual(rows[0].start_bar, plan.start_bar)
            self.assertEqual(rows[-1].end_bar, plan.end_bar)
            for a, b in zip(rows, rows[1:]):
                self.assertEqual(b.start_bar, a.end_bar + 1, name)


class TestContinuity(unittest.TestCase):
    def test_connect_challenges_follow_the_roadmap_line(self) -> None:
        for name in CASES:
            for focus in FOCUSES:
                plan = _plan(name, "Intermediate", focus)
                line = {(a.chord, a.pc) for a in plan.anchors}
                for ch in plan.challenges:
                    if ch.kind == KIND_CONNECT and ch.title != "Connect a chord sequence":
                        self.assertIn((ch.targets[0].chord, ch.targets[0].pc), line, (name, focus))

    def test_one_line_moves_by_small_steps(self) -> None:
        for name in ("perfect", "autumn", "ipanema", "blues"):
            plan = _plan(name, "Intermediate", FOCUS_MOTIF)
            moves = [abs(signed_motion(a.pc, b.pc)) for a, b in zip(plan.anchors, plan.anchors[1:])]
            self.assertLessEqual(sum(moves) / len(moves), 2.5, (name, moves))

    def test_targets_are_landing_notes(self) -> None:
        for name in CASES:
            for level in LEVELS:
                plan = _plan(name, level, FOCUS_CHORD_TONE)
                for ch in plan.challenges:
                    for t in ch.targets:
                        use = note_use(chord_facts(t.chord), t.pc, key=plan.key, style=plan.style)
                        self.assertIn(use.category, HOLDABLE, (name, level, ch.kind, t))

    def test_rhythm_identity_is_carried(self) -> None:
        plan = _plan("perfect", "Intermediate", FOCUS_RHYTHMIC)
        texts = _texts(plan)
        self.assertTrue(any("Keep your rhythm exactly the same" in t for t in texts))
        self.assertIsNotNone(plan.rhythm)


class TestPersonalization(unittest.TestCase):
    def test_levels_change_the_coaching(self) -> None:
        for name in ("perfect", "ipanema", "autumn"):
            beg, inter, adv = (_plan(name, lv, FOCUS_CHORD_TONE) for lv in LEVELS)
            self.assertNotEqual(_templates(beg), _templates(inter), name)
            self.assertNotEqual(_templates(inter), _templates(adv), name)
            idea_notes = [len(p.challenges[0].steps[0].notes) for p in (beg, inter, adv)]
            self.assertLessEqual(idea_notes[0], 3, name)
            self.assertLessEqual(idea_notes[0], idea_notes[2], name)
        self.assertTrue(any(c.kind == KIND_RHYTHM for c in _plan("autumn", "Beginner", FOCUS_CHORD_TONE).challenges))
        adv = " ".join(_texts(_plan("ipanema", "Advanced", FOCUS_CHORD_TONE)))
        self.assertIn("chromatic approach", adv)

    def test_beginner_text_avoids_advanced_theory(self) -> None:
        for name in CASES:
            for focus in FOCUSES:
                for text in _texts(_plan(name, "Beginner", focus)):
                    self.assertIsNone(BEGINNER_JARGON.search(text), (name, focus, text))

    def test_focuses_change_the_exercises_not_just_titles(self) -> None:
        for name in ("perfect", "autumn", "blues"):
            plans = {f: _plan(name, "Intermediate", f) for f in FOCUSES}
            templates = {f: _templates(p) for f, p in plans.items()}
            for a in FOCUSES:
                for b in FOCUSES:
                    if a < b:
                        self.assertNotEqual(templates[a], templates[b], (name, a, b))
            self.assertEqual(plans[FOCUS_CHORD_TONE].material.name, "Chord tones")
            self.assertTrue(any("Call and response" in t for t in _texts(plans[FOCUS_RHYTHMIC])))
            self.assertTrue(any("This is your motif" in t for t in _texts(plans[FOCUS_MOTIF])))
            self.assertTrue(any("rise to" in t for t in _texts(plans[FOCUS_MELODIC])))

    def test_default_focus_never_needs_writing_back(self) -> None:
        self.assertEqual(default_coaching_focus("Pentatonics"), FOCUS_MELODIC)
        self.assertEqual(default_coaching_focus("Guide Tones"), FOCUS_CHORD_TONE)
        self.assertEqual(default_coaching_focus("Voicings"), FOCUS_CHORD_TONE)
        self.assertEqual(default_coaching_focus("Syncopation"), FOCUS_RHYTHMIC)
        self.assertEqual(default_coaching_focus("Groove"), FOCUS_RHYTHMIC)
        self.assertEqual(default_coaching_focus("Soloing"), FOCUS_MOTIF)
        self.assertEqual(default_coaching_focus("Tone"), FOCUS_MELODIC)
        self.assertEqual(default_coaching_focus(""), FOCUS_MELODIC)
        self.assertEqual(normalize_focus("Chord-Tone Connections"), FOCUS_CHORD_TONE)
        self.assertEqual(normalize_focus("rhythmic_development"), FOCUS_RHYTHMIC)
        self.assertEqual(normalize_level("advanced"), "Advanced")
        self.assertEqual(normalize_level("expert"), "Intermediate")


class TestMaterial(unittest.TestCase):
    def test_scale_recommendations_are_justified_against_the_chords(self) -> None:
        perfect = _plan("perfect", "Beginner", FOCUS_MELODIC)
        self.assertEqual(perfect.material.name, "G major pentatonic")
        self.assertEqual(perfect.material.verdict, "fits_with_care")
        self.assertTrue(any("no F# (the chord's 3rd)" in ln.render() for ln in perfect.material.lines))
        self.assertTrue(any(ln.basis == BASIS_STYLE for ln in perfect.material.lines))

    def test_no_generic_pentatonic_where_it_clashes(self) -> None:
        plan = _plan("ipanema", "Intermediate", FOCUS_MELODIC)
        self.assertNotIn("pentatonic", plan.material.name)
        self.assertTrue(any("doesn't fit everywhere" in ln.render() for ln in plan.material.lines))

    def test_pentatonic_is_not_offered_everywhere(self) -> None:
        from song_catalog.catalog import curated_song_records

        names = set()
        for i, rec in enumerate(curated_song_records()[:40]):
            ctx = _catalog(rec["title"])
            sec = coach_sections(ctx)[min(1, len(coach_sections(ctx)) - 1)]
            start, end = suggested_ranges(sec)[0]
            scope = build_scope(ctx, sec.section_id, start, end)
            names.add(build_coaching_plan(ctx, scope, level="Intermediate", focus=FOCUS_MELODIC).material.name)
        self.assertTrue(any("pentatonic" not in n for n in names), names)
        self.assertTrue(any("pentatonic" in n for n in names), names)


class TestTruthfulness(unittest.TestCase):
    def test_no_claims_about_melody_recording_or_performance(self) -> None:
        for name in CASES:
            for level in LEVELS:
                for focus in FOCUSES:
                    plan = _plan(name, level, focus)
                    for text in _texts(plan):
                        self.assertIsNone(FORBIDDEN_CLAIMS.search(text), (name, text))
                    self.assertNotIn("melody", plan.chart_note.replace("does not know the song's melody", "").lower())

    def test_validator_catches_invented_claims(self) -> None:
        ctx, scope = _case("perfect")
        plan = _plan("perfect", "Intermediate", FOCUS_MELODIC)
        bad = dataclasses.replace(plan, summary=plan.summary + (Line(BASIS_PRACTICE, "Copy the original solo from the recording."),))
        self.assertTrue(any("melody knowledge" in p for p in validate_plan(bad, scope)))
        connect = next(c for c in plan.challenges if c.kind == KIND_CONNECT)
        move = next(ln for ln in connect.steps if any(cl.kind == "move" for cl in ln.claims))
        wrong_claims = tuple(dataclasses.replace(cl, number=cl.number + 3) if cl.kind == "move" else cl for cl in move.claims)
        tampered_line = dataclasses.replace(move, claims=wrong_claims)
        steps = tuple(tampered_line if ln is move else ln for ln in connect.steps)
        tampered = dataclasses.replace(
            plan, challenges=tuple(dataclasses.replace(c, steps=steps) if c is connect else c for c in plan.challenges)
        )
        self.assertTrue(any("move distance" in p for p in validate_plan(tampered, scope)))
        clash_target = dataclasses.replace(connect.targets[0], pc=(connect.targets[0].pc + 1) % 12)
        bad_target = dataclasses.replace(
            plan, challenges=tuple(dataclasses.replace(c, targets=(clash_target,)) if c is connect else c for c in plan.challenges)
        )
        self.assertTrue(validate_plan(bad_target, scope))

    def test_every_line_has_a_basis_and_style_lines_name_no_chart_notes(self) -> None:
        for name in CASES:
            for line in _plan(name, "Advanced", FOCUS_MELODIC).all_lines():
                self.assertIn(line.basis, (BASIS_HARMONY, BASIS_STYLE, BASIS_PRACTICE))
                if line.basis == BASIS_STYLE:
                    self.assertEqual(line.notes, ())

    def test_chart_confidence_travels_with_the_plan(self) -> None:
        self.assertEqual(_plan("perfect").chart_label, "Verified chord chart")
        self.assertEqual(_plan("ipanema").chart_label, "Simplified practice chart")
        self.assertEqual(_plan("blues").chart_label, "Your own progression")


class TestIdentityAndJson(unittest.TestCase):
    def test_deterministic_with_stable_ids(self) -> None:
        ctx, scope = _case("autumn")
        a = build_coaching_plan(ctx, scope, level="Advanced", focus=FOCUS_MOTIF)
        b = build_coaching_plan(ctx, scope, level="Advanced", focus=FOCUS_MOTIF)
        self.assertEqual(a, b)
        self.assertEqual(len(a.plan_id), 16)
        ids = {build_coaching_plan(ctx, scope, level=lv, focus=f).plan_id for lv in LEVELS for f in FOCUSES}
        self.assertEqual(len(ids), 12)
        self.assertNotEqual(a.plan_id, build_coaching_plan(ctx, scope, level="Advanced", focus=FOCUS_MOTIF, style="ballad").plan_id)
        self.assertNotEqual(a.plan_id, build_coaching_plan(ctx, scope, level="Advanced", focus=FOCUS_MOTIF, instrument="Saxophone").plan_id)
        self.assertEqual(
            build_coaching_plan(ctx, scope, level="Advanced", focus=FOCUS_MOTIF, instrument="Alto Saxophone").plan_id,
            build_coaching_plan(ctx, scope, level="Advanced", focus=FOCUS_MOTIF, instrument="Tenor Saxophone").plan_id,
        )
        moved_ctx = _catalog("Autumn Leaves", key="Am", style="jazz")
        moved = build_coaching_plan(moved_ctx, build_scope(moved_ctx, "verse-1"), level="Advanced", focus=FOCUS_MOTIF)
        self.assertNotEqual(a.plan_id, moved.plan_id)

    def test_json_round_trip(self) -> None:
        for name in CASES:
            for focus in FOCUSES:
                plan = _plan(name, "Advanced", focus)
                again = CoachingPlan.from_dict(json.loads(json.dumps(plan.to_dict())))
                self.assertEqual(again, plan, (name, focus))
                self.assertEqual(plan_text(again), plan_text(plan))

    def test_render_takes_a_projection(self) -> None:
        plan = _plan("perfect", "Intermediate", FOCUS_MELODIC)
        from music_theory import spell_note_in_key, transpose_chord

        def written(n):  # alto sax: written a major 6th above concert
            return spell_note_in_key((n.pc + 9) % 12, "E")

        def chart(c):
            return transpose_chord(c, 9, reference_key="E")

        concert = plan.challenges[1].steps[1].render()
        projected = plan.challenges[1].steps[1].render(note=written, chord=chart)
        self.assertNotEqual(concert, projected)
        self.assertNotIn("{", projected)

    def test_guards(self) -> None:
        ctx, scope = _case("perfect")
        other_ctx, _ = _case("autumn")
        with self.assertRaises(ValueError):
            build_coaching_plan(other_ctx, scope, level="Beginner", focus=FOCUS_MELODIC)
        dead = build_song_coach_context(identity="", source_kind=SOURCE_CATALOG, concert_sections={}, concert_key="C")
        with self.assertRaises(ValueError):
            build_coaching_plan(dead, scope, level="Beginner", focus=FOCUS_MELODIC)


class TestExamplesAgainstTheChart(unittest.TestCase):
    """The three reported examples, checked against the raw catalog bars (not the S1 scope)."""

    EXAMPLES = (
        ("Perfect", "Verse 1", 1, 8, "perfect", "Beginner", FOCUS_MELODIC, "open_on_dominant"),
        ("The Girl from Ipanema", "A Section", 1, 8, "ipanema", "Advanced", FOCUS_CHORD_TONE, "open"),
        ("Hotel California", "Verse 1a", 1, 8, "hotel", "Intermediate", FOCUS_MOTIF, "open_on_dominant"),
    )

    def test_bars_changes_landing_notes_and_endings(self) -> None:
        from song_coach_plan import _o_chord_tones, _o_function_root, _o_pc

        for title, section, start, end, case, level, focus, ending in self.EXAMPLES:
            raw = _record(title)["sections"].get(section) or next(
                v for k, v in _record(title)["sections"].items() if k.lower() == section.lower()
            )
            bars = list(raw[start - 1 : end])
            changes = {i + start: (bars[i - 1], bars[i]) for i in range(1, len(bars)) if bars[i] != bars[i - 1]}
            plan = _plan(case, level, focus)
            self.assertEqual((plan.start_bar, plan.end_bar), (start, end), title)
            for ch in plan.challenges:
                for ln in ch.steps:
                    for cl in ln.claims:
                        if cl.kind == "change_at":
                            self.assertIn(cl.number, changes, (title, ln.render()))
                            self.assertEqual(changes[cl.number], (cl.chord, cl.other_chord), (title, ln.render()))
            self.assertEqual([a.chord for a in plan.anchors],
                             [c for i, c in enumerate(bars) if i == 0 or c != bars[i - 1]], title)
            for a in plan.anchors:
                self.assertIn(a.pc, _o_chord_tones(a.chord), (title, a))
                self.assertEqual(_o_pc(a.name), a.pc, (title, a))
            self.assertEqual(plan.ending, ending, title)
            key = _record(title)["key"]
            self.assertEqual((_o_function_root(bars[-1]) - _o_pc(key.rstrip("m"))) % 12 == 7, ending == "open_on_dominant", title)


class TestValidatorIndependence(unittest.TestCase):
    """The validator re-derives facts without the generator's chord reader."""

    def _perfect(self):
        ctx, scope = _case("perfect")
        return scope, _plan("perfect", "Intermediate", FOCUS_MELODIC)

    def _with_line(self, plan: CoachingPlan, line: Line) -> CoachingPlan:
        return dataclasses.replace(plan, summary=plan.summary + (line,))

    def test_a_corrupted_chord_reader_cannot_vouch_for_itself(self) -> None:
        from unittest import mock

        import song_coach_plan as engine
        from song_coach_plan import Claim, NoteRef

        scope, plan = self._perfect()
        wrong = NoteRef(10, "Bb", "7th", "Cadd9", "chord_tone")  # Cadd9 has no ♭7
        line = Line(BASIS_HARMONY, "{n0} is the 7th of {c0}.", (wrong,), ("Cadd9",),
                    (Claim("note", chord="Cadd9", pc=10, role="7th", value="chord_tone"),))

        def corrupt(sym):  # a reader that wrongly reads add9 chords as dominant 7ths
            return chord_facts("C7") if sym == "Cadd9" else chord_facts(sym)

        with mock.patch.object(engine, "chord_facts", corrupt):
            problems = validate_plan(self._with_line(plan, line), scope)
        self.assertTrue(any("independent check: Bb is not stated by Cadd9" in p for p in problems), problems)

    def test_wrong_motion_words_are_caught_from_the_notes(self) -> None:
        from song_coach_plan import Claim, NoteRef

        scope, plan = self._perfect()
        a, b = NoteRef(7, "G", "5th", "Cadd9", "chord_tone"), NoteRef(6, "F#", "3rd", "D/F#", "chord_tone")
        claim = Claim("move", chord="Cadd9", pc=7, other_chord="D/F#", other_pc=6, number=-1)
        line = Line(BASIS_HARMONY, "Move {n0} → {n1}, up a half step: the 5th of {c0} becomes the 3rd of {c1}.",
                    (a, b), ("Cadd9", "D/F#"), (claim,))
        problems = validate_plan(self._with_line(plan, line), scope)
        self.assertTrue(any("moves the other way" in p for p in problems), problems)
        leap = Line(BASIS_HARMONY, "Move {n0} → {n1}, down a whole step: the 5th of {c0} becomes the 3rd of {c1}.",
                    (a, b), ("Cadd9", "D/F#"), (claim,))
        self.assertTrue(any("is a half step" in p for p in validate_plan(self._with_line(plan, leap), scope)))

    def test_role_words_must_be_true_of_the_named_notes(self) -> None:
        from song_coach_plan import NoteRef

        scope, plan = self._perfect()
        g = NoteRef(7, "G", "minor 3rd", "Em7", "chord_tone")
        line = Line(BASIS_HARMONY, "{n0} is the 3rd of {c0}.", (g,), ("Em7",))
        problems = validate_plan(self._with_line(plan, line), scope)
        self.assertTrue(any("no note in the line is the 3rd of Em7" in p for p in problems), problems)
        misnamed = NoteRef(7, "F##", "minor 3rd", "Em7", "chord_tone")
        self.assertTrue(any("independent check" in p for p in validate_plan(
            self._with_line(plan, Line(BASIS_HARMONY, "{n0}.", (misnamed,), ("Em7",))), scope)))

    def test_endings_are_checked_from_function_roots(self) -> None:
        from song_coach_plan import Claim

        scope, plan = self._perfect()
        fake = Line(BASIS_HARMONY, "The section closes with a V–I cadence into {c0}.", (), ("D/F#",),
                    (Claim("ending", value="authentic_cadence", chord="D/F#"),))
        problems = validate_plan(self._with_line(plan, fake), scope)
        self.assertTrue(any("independent check: ending authentic_cadence" in p for p in problems), problems)
        v = Line(BASIS_HARMONY, "These bars end on {c0} — the V chord, unresolved.", (), ("Em7",),
                 (Claim("ending", value="open_on_dominant", chord="Em7"),))
        self.assertFalse([p for p in validate_plan(self._with_line(plan, v), scope) if "'the V chord'" in p])

    def test_slash_chord_guidance_never_calls_the_bass_the_root(self) -> None:
        ctx = _custom({"A": ["Dm7", "Dm7", "F/G", "F/G", "C", "C", "C/E", "F"]}, "C", style="pop")
        scope = build_scope(ctx, "a")
        for level in LEVELS:
            for focus in FOCUSES:
                plan = build_coaching_plan(ctx, scope, level=level, focus=focus)
                self.assertEqual(validate_plan(plan, scope), [], (level, focus))
                for ln in plan.all_lines():
                    for n in ln.notes:
                        if n.role == "root":
                            self.assertEqual(n.pc, chord_facts(n.chord).root_pc, (n, ln.render()))
                    self.assertNotIn("the root of F/G" if any(n.name == "G" and n.chord == "F/G" and n.role == "root" for n in ln.notes) else "\x00", ln.render())


class TestCatalogSample(unittest.TestCase):
    def test_a_rotating_sample_of_every_catalog_song_validates(self) -> None:
        from song_catalog.catalog import curated_song_records

        combos = [(lv, f) for lv in LEVELS for f in FOCUSES]
        checked = 0
        for i, rec in enumerate(curated_song_records()):
            ctx = _catalog(rec["title"])
            if not ctx.available:
                continue
            for j, sec in enumerate(coach_sections(ctx)):
                start, end = suggested_ranges(sec)[0]
                try:
                    scope = build_scope(ctx, sec.section_id, start, end)
                except Exception:
                    continue
                level, focus = combos[(i + j) % len(combos)]
                plan = build_coaching_plan(ctx, scope, level=level, focus=focus)
                self.assertEqual(validate_plan(plan, scope), [], (rec["title"], sec.label, level, focus))
                checked += 1
        self.assertGreater(checked, 500)


if __name__ == "__main__":
    unittest.main()
