"""MC3 — Multi-chord Missions on a HarmonicSpan: availability, generation, validation, state."""

from __future__ import annotations

import collections
import logging
import statistics
import unittest
from unittest.mock import patch

from harmonic_span_analyzer import analyze_harmonic_spans
from improvisation_motif import (
    build_motif_abc,
    midi_from_guitar_position,
    motif_guitar_tab_placements,
    section_harmony_rows,
)
from melodic_pattern_engine import build_context
from mission_span_engine import (
    MISSIONS_BY_ID,
    SINGLE_CHORD_CLASSIFICATION,
    SPAN_MISSIONS,
    available_span_missions,
    common_collection,
    generate_mission_span_example,
    materially_different,
    unavailable_reason,
    validate_mission_line,
)
from span_motif_engine import note_chord_assignment, project_span_motif
from tests.abc_pitch_decoder import decode_abc_midis

logging.disable(logging.CRITICAL)

LEVELS = ("Beginner", "Intermediate", "Advanced")
_SPANS: dict = {}


def span(chords, key, raw=None):
    k = (tuple(chords), key, tuple(raw or ()))
    if k not in _SPANS:
        rows = section_harmony_rows({"A": raw or chords}, section_names=["A"])
        _SPANS[k] = next(
            s for s in analyze_harmonic_spans(rows, key_center=key, length=len(chords), source_id="t", include_weak=True)
            if list(s.chords) == chords
        )
    return _SPANS[k]


def iivi():
    return span(["Gm7", "C7", "Fmaj7"], "F", ["Gm7", "C7", "Fmaj7", "Fmaj7"])


def minor_iivi():
    return span(["Bm7b5", "E7", "Am"], "Am")


def subv():
    return span(["Gm7", "Gb7", "Fmaj7"], "F")


def pop_pair():
    return span(["G", "C"], "G")


def vamp():
    return span(["Am7", "D7"], "G", ["Am7", "D7", "Am7", "D7"])


def ex(mission, sp, level, variant="normal", style="jazz", **kw):
    return generate_mission_span_example(mission, sp, level=level, variant=variant, style=style, **kw)


def outside_notes(e, key):
    m = e["motif"]
    return [
        x for x, ci in zip(m["midi"], m["note_chord_index"])
        if x % 12 not in build_context(key, m["chord_timeline"][ci]["chord"]).scale_pcs
    ]


class TestCatalogAndClassification(unittest.TestCase):
    def test_every_existing_mission_is_classified(self) -> None:
        from improvisation_intelligence import PRACTICE_MISSIONS

        self.assertEqual(set(SINGLE_CHORD_CLASSIFICATION), set(PRACTICE_MISSIONS))
        self.assertEqual(set(SINGLE_CHORD_CLASSIFICATION.values()), {"single_chord_only", "span_compatible", "span_specific"})
        realized = {label for m in SPAN_MISSIONS for label in m.realizes} | {m.label for m in SPAN_MISSIONS}
        for label, kind in SINGLE_CHORD_CLASSIFICATION.items():
            if kind == "single_chord_only":
                self.assertNotIn(label, realized, label)
            else:
                self.assertIn(label, realized, label)

    def test_new_multichord_missions_exist(self) -> None:
        for mid in ("guide_tone_voice_leading", "target_each_change", "motif_through_changes", "common_tone_voice_leading",
                    "approach_next_chord", "enclose_next_target", "ii_v_i_resolution", "one_common_scale",
                    "dominant_tension_resolution"):
            self.assertIn(mid, MISSIONS_BY_ID)


class TestAvailability(unittest.TestCase):
    def ids(self, sp, level, style="jazz"):
        return {m.id for m in available_span_missions(sp, level=level, style=style)}

    def test_impossible_missions_are_hidden(self) -> None:
        self.assertNotIn("ii_v_i_resolution", self.ids(pop_pair(), "Intermediate", "pop"))
        self.assertNotIn("dominant_tension_resolution", self.ids(pop_pair(), "Advanced", "pop"))
        self.assertNotIn("guide_tone_voice_leading", self.ids(pop_pair(), "Intermediate", "pop"))  # triads: no 7ths
        self.assertNotIn("one_common_scale", self.ids(subv(), "Advanced"))
        chromatic = span(["Cmaj7", "Ebmaj7", "Abmaj7"], "C")
        self.assertNotIn("one_common_scale", self.ids(chromatic, "Advanced"))
        self.assertTrue(unavailable_reason("one_common_scale", chromatic, level="Advanced"))
        self.assertNotIn("bebop_line", self.ids(iivi(), "Advanced", "pop"))
        self.assertNotIn("ii_v_i_resolution", self.ids(vamp(), "Advanced"))

    def test_real_contexts_offer_their_missions(self) -> None:
        self.assertIn("ii_v_i_resolution", self.ids(iivi(), "Beginner"))
        self.assertIn("ii_v_i_resolution", self.ids(minor_iivi(), "Intermediate"))
        self.assertIn("dominant_tension_resolution", self.ids(subv(), "Intermediate"))
        self.assertIn("one_common_scale", self.ids(iivi(), "Beginner"))
        self.assertEqual(common_collection(iivi())[0], "F major")
        self.assertEqual(common_collection(minor_iivi())[0], "A harmonic minor")
        beginner_pop = self.ids(pop_pair(), "Beginner", "pop")
        self.assertTrue({"target_each_change", "motif_through_changes", "common_tone_voice_leading", "one_common_scale"} <= beginner_pop)

    def test_level_gating(self) -> None:
        beg = self.ids(iivi(), "Beginner")
        self.assertFalse(beg & {"dominant_tension_resolution", "bebop_line", "syncopated_phrase"})
        with self.assertRaises(ValueError):
            ex("dominant_tension_resolution", iivi(), "Beginner")


class TestMajorTwoFiveOne(unittest.TestCase):
    MISSIONS = ("guide_tone_voice_leading", "target_each_change", "motif_through_changes", "approach_next_chord",
                "enclose_next_target", "ii_v_i_resolution", "one_common_scale", "dominant_tension_resolution")

    def test_every_mission_is_valid_at_every_level_and_difficulty(self) -> None:
        for mid in self.MISSIONS:
            for level in LEVELS:
                if unavailable_reason(mid, iivi(), level=level, style="jazz"):
                    continue
                for variant in ("easier", "normal", "harder"):
                    e = ex(mid, iivi(), level, variant)
                    self.assertTrue(e["valid"], (mid, level, variant, e["problems"], e["motif"]["notes"]))
                    self.assertEqual(e["span_id"], iivi().span_id)
                    self.assertEqual(note_chord_assignment(e["motif"]), e["motif"]["note_chord_index"])

    def test_guide_tones_show_the_seven_to_three(self) -> None:
        for level in LEVELS:
            e = ex("guide_tone_voice_leading", iivi(), level)
            texts = [ev["text"] for ev in e["evidence"] if ev["where"] == "C7 → Fmaj7"]
            self.assertTrue(any("7th resolves to 3rd" in t for t in texts), texts)
            m = e["motif"]
            for t in m["chord_timeline"]:
                ctx = build_context("F", t["chord"])
                role = ctx.role_of(m["midi"][t["first_note"]] % 12)
                self.assertIn(role, ("3", "7"), (level, m["notes"]))

    def test_target_roles_follow_level(self) -> None:
        for level, allowed in (("Beginner", {"R", "3", "5"}), ("Intermediate", {"3", "7"}), ("Advanced", {"3", "7"})):
            for idea in range(3):
                m = ex("target_each_change", iivi(), level, idea=idea)["motif"]
                for t in m["chord_timeline"]:
                    role = build_context("F", t["chord"]).role_of(m["midi"][t["first_note"]] % 12)
                    self.assertIn(role, allowed, (level, m["notes"]))

    def test_approach_and_enclosure_by_level(self) -> None:
        beg = ex("approach_next_chord", iivi(), "Beginner")
        self.assertFalse(outside_notes(beg, "F"), beg["motif"]["notes"])
        inter = ex("approach_next_chord", iivi(), "Intermediate")["motif"]
        for c in inter["change_indices"]:
            self.assertEqual(abs(inter["midi"][c] - inter["midi"][c - 1]), 1, inter["notes"])
        for level in LEVELS:
            m = ex("enclose_next_target", iivi(), level)["motif"]
            for c in m["change_indices"]:
                a, b, t = m["midi"][c - 2], m["midi"][c - 1], m["midi"][c]
                self.assertLess((a - t) * (b - t), 0, (level, m["notes"]))
                self.assertLessEqual(max(abs(a - t), abs(b - t)), 2)

    def test_ii_v_i_resolves_and_advanced_colours_the_dominant(self) -> None:
        for level in LEVELS:
            m = ex("ii_v_i_resolution", iivi(), level)["motif"]
            self.assertIn(m["midi"][-1] % 12, {5, 9}, (level, m["notes"]))  # F or A
        adv = ex("ii_v_i_resolution", iivi(), "Advanced")
        colours = {c["chord"]: c["color"] for c in adv["motif"]["advanced_colors"]}
        self.assertIn(colours.get("C7"), ("altered", "diminished", "whole_tone"))
        self.assertTrue(any(ev["check"] == "dominant colour" for ev in adv["evidence"]))
        beg = ex("ii_v_i_resolution", iivi(), "Beginner")
        self.assertFalse(outside_notes(beg, "F"))

    def test_common_scale_is_named_and_obeyed(self) -> None:
        for level in LEVELS:
            e = ex("one_common_scale", iivi(), level, variant="harder")
            self.assertEqual(e["common_scale"]["name"], "F major")
            self.assertEqual(e["common_scale"]["notes"], ["F", "G", "A", "B♭", "C", "D", "E"])
            self.assertTrue({x % 12 for x in e["motif"]["midi"]} <= {5, 7, 9, 10, 0, 2, 4}, e["motif"]["notes"])


class TestMinorAndTritoneSub(unittest.TestCase):
    def test_minor_ii_v_i(self) -> None:
        for level in ("Intermediate", "Advanced"):
            for mid in ("ii_v_i_resolution", "guide_tone_voice_leading", "dominant_tension_resolution"):
                e = ex(mid, minor_iivi(), level)
                self.assertTrue(e["valid"], (mid, level, e["problems"]))
            m = ex("ii_v_i_resolution", minor_iivi(), level)["motif"]
            self.assertIn(m["midi"][-1] % 12, {9, 0}, m["notes"])  # A or C: the minor tonic
        adv = ex("dominant_tension_resolution", minor_iivi(), "Advanced")
        e7 = [c for c in adv["motif"]["advanced_colors"] if c["chord"] == "E7"]
        self.assertTrue(e7 and e7[0]["color"] in ("altered", "diminished", "whole_tone"))
        m = adv["motif"]
        c = m["change_indices"][-1]
        self.assertLessEqual(abs(m["midi"][c] - m["midi"][c - 1]), 2)
        self.assertIn(m["midi"][c] % 12, build_context("Am", "Am").chord_pcs)

    def test_tritone_sub_uses_lydian_dominant_and_resolves_into_f(self) -> None:
        e = ex("dominant_tension_resolution", subv(), "Advanced")
        self.assertTrue(e["valid"], e["problems"])
        colours = {c["chord"]: c["color"] for c in e["motif"]["advanced_colors"]}
        self.assertEqual(colours.get("Gb7"), "lydian_dominant")
        m = e["motif"]
        c = m["change_indices"][-1]
        self.assertIn(m["midi"][c] % 12, build_context("F", "Fmaj7").chord_pcs)
        self.assertTrue(ex("dominant_tension_resolution", subv(), "Intermediate")["valid"])


class TestPopAndVamp(unittest.TestCase):
    NON_CHROMATIC = ("target_each_change", "motif_through_changes", "common_tone_voice_leading", "one_common_scale",
                     "chord_tones_each_chord", "pentatonic_per_chord", "scalar_runs")

    def test_pop_pair_is_regular_and_diatonic(self) -> None:
        for level in LEVELS:
            for mid in self.NON_CHROMATIC:
                for idea in range(2):
                    e = ex(mid, pop_pair(), level, style="pop", idea=idea)
                    self.assertTrue(e["valid"], (mid, level, e["problems"]))
                    prof = e["motif"]["rhythm_profile"]
                    self.assertLessEqual(prof["syncopation"], 0.0 if level == "Beginner" else 0.25, (mid, level))
                    self.assertEqual(prof["triplets"], 0.0, (mid, level))
                    self.assertFalse(outside_notes(e, "G"), (mid, level, e["motif"]["notes"]))

    def test_vamp_motif_uses_repetition_and_no_fake_cadence(self) -> None:
        for level in LEVELS:
            e = ex("motif_through_changes", vamp(), level)
            self.assertTrue(e["valid"], e["problems"])
            m = e["motif"]
            self.assertNotEqual(m["midi"][-1] % 12, 7, ("a ii–V vamp must not land on an absent G", m["notes"]))


class TestDifficultyAndIdeas(unittest.TestCase):
    def test_easier_normal_harder_within_the_level(self) -> None:
        for sp, style in ((iivi(), "jazz"), (pop_pair(), "pop")):
            for level in LEVELS:
                for m in available_span_missions(sp, level=level, style=style):
                    n = {v: len(ex(m.id, sp, level, v, style=style)["motif"]["midi"]) for v in ("easier", "normal", "harder")}
                    self.assertLessEqual(n["easier"], n["normal"], (m.id, level, n))
                    self.assertLess(n["normal"], n["harder"], (m.id, level, n))

    def test_harder_never_escapes_the_level(self) -> None:
        for m in available_span_missions(iivi(), level="Beginner", style="jazz"):
            e = ex(m.id, iivi(), "Beginner", "harder")
            prof = e["motif"]["rhythm_profile"]
            self.assertEqual((prof["syncopation"], prof["triplets"], prof["sixteenths"]), (0, 0, 0), m.id)
            self.assertFalse(outside_notes(e, "F"), (m.id, e["motif"]["notes"]))
        for m in available_span_missions(iivi(), level="Intermediate", style="jazz"):
            self.assertFalse(ex(m.id, iivi(), "Intermediate", "harder")["motif"]["advanced_colors"], m.id)

    def test_new_ideas_are_distinct_valid_and_keep_the_context(self) -> None:
        for mid in ("guide_tone_voice_leading", "motif_through_changes", "enclose_next_target", "target_each_change"):
            seen = []
            for idea in range(4):
                e = ex(mid, iivi(), "Intermediate", idea=idea, avoid=seen)
                self.assertTrue(e["valid"], (mid, idea, e["problems"]))
                self.assertEqual((e["mission_id"], e["span_id"], e["difficulty"], e["level"]),
                                 (mid, iivi().span_id, "normal", "Intermediate"))
                for prior in seen:
                    self.assertTrue(materially_different(e["motif"], prior["motif"]), (mid, idea))
                seen.append(e)


class TestValidatorsRejectBadLines(unittest.TestCase):
    def _mutate(self, e, index, delta):
        m = dict(e["motif"])
        midi = list(m["midi"])
        midi[index] += delta
        m["midi"] = midi
        m["notes"] = list(m["notes"])
        return m

    def test_wrong_target_role_is_rejected(self) -> None:
        e = ex("guide_tone_voice_leading", iivi(), "Intermediate")
        t = e["motif"]["chord_timeline"][2]["first_note"]  # Fmaj7 lands on A (3rd)
        bad = self._mutate(e, t, -4)  # → F, the root
        self.assertFalse(validate_mission_line("guide_tone_voice_leading", bad, iivi(), level="Intermediate").valid)

    def test_broken_enclosure_and_approach_are_rejected(self) -> None:
        e = ex("enclose_next_target", iivi(), "Intermediate")
        c = e["motif"]["change_indices"][0]
        m = e["motif"]
        same_side = self._mutate(e, c - 2, 2 * (m["midi"][c] - m["midi"][c - 2]))
        self.assertFalse(validate_mission_line("enclose_next_target", same_side, iivi(), level="Intermediate").valid)
        a = ex("approach_next_chord", iivi(), "Intermediate")
        c = a["motif"]["change_indices"][0]
        whole_step = self._mutate(a, c - 1, a["motif"]["midi"][c - 1] - a["motif"]["midi"][c])
        self.assertFalse(validate_mission_line("approach_next_chord", whole_step, iivi(), level="Intermediate").valid)

    def test_unstable_ending_and_outside_note_are_rejected(self) -> None:
        e = ex("ii_v_i_resolution", iivi(), "Intermediate")
        last = len(e["motif"]["midi"]) - 1
        m = dict(e["motif"])
        midi = list(m["midi"])
        midi[last] = midi[last] - midi[last] % 12 + 0  # C: the 5th of F
        m["midi"] = midi
        self.assertFalse(validate_mission_line("ii_v_i_resolution", m, iivi(), level="Intermediate").valid)
        cs = ex("one_common_scale", iivi(), "Intermediate")
        m = dict(cs["motif"])
        midi = list(m["midi"])
        midi[1] = midi[1] - midi[1] % 12 + 11  # B natural is not in F major
        m["midi"] = midi
        self.assertFalse(validate_mission_line("one_common_scale", m, iivi(), level="Intermediate").valid)


class TestExplanationsAndNotation(unittest.TestCase):
    def test_evidence_matches_the_notes_and_survives_written_projection(self) -> None:
        e = ex("guide_tone_voice_leading", iivi(), "Intermediate")
        m = e["motif"]
        for ev in e["evidence"]:
            if ev["check"] == "lands on 3rd/7th":
                name = ev["text"].split(" (")[0]
                idx = m["chord_timeline"][[t["chord"] for t in m["chord_timeline"]].index(ev["where"])]["first_note"]
                self.assertEqual(name, m["notes"][idx].replace("b", "♭"))
        alto = project_span_motif(m, semitones=9, chart_key="D",
                                  project_chord=lambda c: {"Gm7": "Em7", "C7": "A7", "Fmaj7": "Dmaj7"}[c])
        rep = validate_mission_line("guide_tone_voice_leading", alto, iivi(), level="Intermediate", key="D",
                                    chords=["Em7", "A7", "Dmaj7"])
        self.assertTrue(rep.valid)
        self.assertTrue(any("A7 → Dmaj7" == ev["where"] and "G (7th of A7) → F♯ (3rd of Dmaj7)" in ev["text"]
                            for ev in rep.evidence()), rep.evidence())
        cs = common_collection(iivi(), key="D")
        self.assertEqual(cs[0], "D major")

    def test_abc_and_tab_are_exact(self) -> None:
        for mid in ("guide_tone_voice_leading", "enclose_next_target", "ii_v_i_resolution", "syncopated_phrase"):
            for variant in ("normal", "harder"):
                m = ex(mid, iivi(), "Advanced", variant)["motif"]
                self.assertEqual(decode_abc_midis(build_motif_abc(m, key_center="F", bpm=100)), m["midi"])
                bass = build_motif_abc(m, key_center="F", bpm=100, clef="bass")
                self.assertIn("clef=bass", bass)
                self.assertEqual(decode_abc_midis(bass), m["midi"])
                self.assertEqual([midi_from_guitar_position(s, f) for s, f in motif_guitar_tab_placements(m)], m["midi"])


class TestFocusStyleAndHandoff(unittest.TestCase):
    def test_mission_wins_but_focus_still_shapes_the_line(self) -> None:
        plain = [ex("guide_tone_voice_leading", iivi(), "Intermediate", idea=i) for i in range(6)]
        sync = [ex("guide_tone_voice_leading", iivi(), "Intermediate", idea=i, focus="Syncopation") for i in range(6)]
        for e in sync:
            self.assertTrue(e["valid"])
        self.assertGreater(statistics.mean(e["motif"]["rhythm_profile"]["syncopation"] for e in sync),
                           statistics.mean(e["motif"]["rhythm_profile"]["syncopation"] for e in plain))

    def test_style_controls_syncopation(self) -> None:
        from melodic_rhythm_engine import events_from_json

        def per_bar(e):
            counts = collections.Counter()
            for ev in events_from_json(e["motif"]["rhythm_events"]):
                if not ev.rest and ev.onset % 1 != 0 and ev.onset + ev.duration > ev.onset - ev.onset % 1 + 1:
                    counts[int(ev.onset // 4)] += 1
            return counts

        jazz = [ex("syncopated_phrase", iivi(), "Intermediate", idea=i) for i in range(5)]
        ballad = [ex("syncopated_phrase", span(["C", "Am", "F"], "C"), "Intermediate", style="ballad", idea=i) for i in range(5)]
        for e in jazz + ballad:
            self.assertTrue(e["valid"], e["problems"])
        for e in ballad:
            self.assertLessEqual(max(per_bar(e).values()), 1, e["motif"]["rhythm"])  # restrained: one entry per bar
        self.assertGreaterEqual(statistics.mean(sum(per_bar(e).values()) for e in jazz),
                                statistics.mean(sum(per_bar(e).values()) for e in ballad))

    def test_handoff_payload_carries_what_mission_backing_needs(self) -> None:
        e = ex("enclose_next_target", iivi(), "Intermediate")
        h = e["handoff"]
        for key in ("mission_id", "span_id", "chord_timeline", "example_id", "note_chord_index", "loop_bars", "meter",
                    "practice_key"):
            self.assertIn(key, h)
        self.assertEqual(h["loop_bars"], 4)
        self.assertEqual(h["note_chord_index"], e["motif"]["note_chord_index"])


class TestSpanMissionState(unittest.TestCase):
    def test_intent_state_machine_resets_on_context(self) -> None:
        from mission_span_ui import span_mission_intent

        st = {}
        self.assertEqual(span_mission_intent(st, context="a|s|Intermediate", intent="generate"), ("normal", 0))
        self.assertEqual(span_mission_intent(st, context="a|s|Intermediate", intent="harder"), ("harder", 0))
        self.assertEqual(span_mission_intent(st, context="a|s|Intermediate", intent="harder"), ("harder", 1))
        self.assertEqual(span_mission_intent(st, context="a|s|Intermediate", intent="new"), ("harder", 2))
        self.assertEqual(span_mission_intent(st, context="a|s|Advanced", intent="generate"), ("normal", 0))  # Level change
        self.assertEqual(span_mission_intent(st, context="a|s|Advanced", intent="easier"), ("easier", 0))
        self.assertEqual(span_mission_intent(st, context="a|s|Advanced", intent="easier"), ("easier", 1))
        self.assertEqual(span_mission_intent(st, context="b|s|Advanced", intent="generate"), ("normal", 0))  # Mission change

    def test_panel_uses_its_own_state_and_never_touches_single_chord_missions(self) -> None:
        from improvisation_intelligence import ImprovSessionContext
        from mission_span_ui import SPAN_MISSION_PICK_KEY, SPAN_MISSION_STATE_KEY, render_span_missions
        from tests.test_mc1_motif_span_selector_ui import _FakeSt

        sections = {"Outro": ["Gm7", "C7", "Fmaj7", "Fmaj7"]}
        ctx = ImprovSessionContext(song_title="I", artist="", key_center="F", display_key="F", instrument="Piano",
                                   level="Intermediate", focus="", sections=sections)
        single = {"notes": ["C"], "chord": "C7"}
        ss = {"improv_span_song_style": "jazz", "improv_mission_example": single,
              SPAN_MISSION_PICK_KEY: "guide_tone_voice_leading"}
        rows = section_harmony_rows(sections, section_names=list(sections))

        def run(clicks=(), level="Intermediate"):
            st = _FakeSt(ss)
            st.clicks = set(clicks)
            with patch("improvisation_motif.resolve_improv_section_rows", return_value=rows), \
                 patch("improvisation_intelligence_ui._coherent_improv_key_pair", return_value=("F", "F")), \
                 patch("improvisation_intelligence_ui._render_motif_sheet_music"):
                render_span_missions(st, session_state=ss, improv_ctx=ctx, scope="span3", level=level, instrument="Piano",
                                     focus="", bpm=120)
            return st

        run({"improv_span_mission_gen"})
        self.assertTrue(ss[SPAN_MISSION_STATE_KEY]["example"]["valid"])
        run({"improv_span_mission_harder"})
        self.assertEqual(ss[SPAN_MISSION_STATE_KEY]["bucket"], "harder")
        st = run(level="Advanced")  # Level change: back to Normal, no stale example
        self.assertNotIn("example", ss[SPAN_MISSION_STATE_KEY])
        self.assertTrue(any("Generate example" in t for t in st.text))
        self.assertEqual(ss["improv_mission_example"], single)  # single-chord Mission state untouched


class TestSingleChordMissionsUnchanged(unittest.TestCase):
    def test_single_chord_is_the_default_scope_and_the_catalog_is_unchanged(self) -> None:
        from improvisation_intelligence import PRACTICE_MISSIONS
        from mission_span_ui import render_mission_target_scope
        from tests.test_mc1_motif_span_selector_ui import _FakeSt

        ss: dict = {}
        self.assertEqual(render_mission_target_scope(_FakeSt(ss), ss), "single")
        self.assertEqual(len(PRACTICE_MISSIONS), 18)


if __name__ == "__main__":
    unittest.main()
