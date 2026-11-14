"""Melody candidates: distinct identities, harmony-aware notes, honest descriptions, audit."""

from __future__ import annotations

import itertools
import unittest

from composition_melody_audit import (
    LABEL_CHORD_TONE,
    LABEL_CHROMATIC_APPROACH,
    audit_melody,
    audit_violations,
    chord_info,
    secondary_dominant_label,
)
from composition_melody_describe import (
    describe_melody_with_harmony,
    melody_features,
    question_answer_facts,
    verify_concept_claim,
)
from composition_melody_engine import CONCEPT_ORDER, CONCEPTS, build_concept_events, concepts_for_feel

PROGRESSIONS = [
    ("C", ["Cmaj7", "Fmaj7", "D7", "G7"], "4/4"),
    ("A minor", ["Am", "Dm", "E7", "Am"], "4/4"),
    ("G", ["G", "Em", "C", "D", "G", "Em", "C", "D"], "4/4"),
    ("Bb", ["Bbmaj7", "Gm7", "Cm7", "F7"], "4/4"),
    ("C", ["C", "G/B", "Am", "F"], "3/4"),
]
STYLES = ("simple", "complex")


def _pair_distance(a: list[dict], b: list[dict]) -> tuple[float, float]:
    """(pitch difference share, rhythm difference share) between two note lists."""

    def notes(ev):
        return [(round(e["beat"], 3), e.get("midi")) for e in ev]

    def rhythm(ev):
        return [(round(e["beat"], 3), round(e["duration_beats"], 3), bool(e.get("is_rest"))) for e in ev]

    na, nb = notes(a), notes(b)
    pitch_same = len(set(na) & set(nb)) / max(len(set(na) | set(nb)), 1)
    ra, rb = rhythm(a), rhythm(b)
    rhythm_same = len(set(ra) & set(rb)) / max(len(set(ra) | set(rb)), 1)
    return 1 - pitch_same, 1 - rhythm_same


class TestDistinctCandidates(unittest.TestCase):
    def test_every_pair_of_concepts_is_musically_different(self) -> None:
        for key, chords, meter in PROGRESSIONS:
            for style in STYLES:
                built = {c: build_concept_events(c, chords, key=key, meter=meter, style=style) for c in CONCEPT_ORDER}
                for a, b in itertools.combinations(CONCEPT_ORDER, 2):
                    pd, rd = _pair_distance(built[a], built[b])
                    self.assertGreater(pd, 0.3, f"{a}/{b} too similar in notes {key} {chords} {style}")
                    self.assertGreater(rd, 0.25, f"{a}/{b} too similar in rhythm {key} {chords} {style}")

    def test_user_reported_pair_direct_line_vs_offbeat(self) -> None:
        chords = ["Cmaj7", "Fmaj7", "D7", "G7"]
        d = build_concept_events("direct_line", chords, key="C")
        o = build_concept_events("offbeat_accent", chords, key="C")
        self.assertNotEqual([e["midi"] for e in d], [e["midi"] for e in o])
        self.assertNotEqual([e["duration_beats"] for e in d], [e["duration_beats"] for e in o])

    def test_suggested_set_has_unique_ids_and_signatures(self) -> None:
        from composition_chord_repeats import accept_full_progression
        from composition_document import (
            apply_structure_template,
            bootstrap_from_vision,
            ordered_sections,
            parse_chord_paste,
        )
        from composition_melody_suggestions import suggest_melody_concepts

        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="C", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        accept_full_progression(doc, str(verse["id"]), parse_chord_paste("Cmaj7 Fmaj7 D7 G7"), tiled=False)
        for feel in ("lyrical", "rhythmic", "smooth", "bold", "emotional", "energetic"):
            for style in STYLES:
                ideas = suggest_melody_concepts(doc, verse, feel, style, limit=3)
                self.assertEqual(len(ideas), 3, feel)
                self.assertEqual(len({i["id"] for i in ideas}), 3)
                self.assertEqual(len({i["name"] for i in ideas}), 3)
                for i, j in itertools.combinations(ideas, 2):
                    pd, rd = _pair_distance(i["events"], j["events"])
                    self.assertGreater(pd, 0.3)
                    self.assertGreater(rd, 0.25)
                    self.assertNotEqual(i["contour"], j["contour"])
                for i in ideas:  # concept name only: no stacked "Direct line - Question & answer"
                    self.assertEqual(i["name"], CONCEPTS[i["id"]]["name"])


class TestHarmonyAwareNotes(unittest.TestCase):
    def test_no_audit_violations_any_concept(self) -> None:
        for key, chords, meter in PROGRESSIONS:
            for style in STYLES:
                for cid in CONCEPT_ORDER:
                    ev = build_concept_events(cid, chords, key=key, meter=meter, style=style)
                    self.assertTrue(ev)
                    bad = audit_violations(audit_melody(ev, chords, key=key, meter=meter))
                    self.assertEqual(bad, [], f"{cid} {key} {chords} {style}: {bad}")

    def test_strong_beats_are_chord_tones(self) -> None:
        for key, chords, meter in PROGRESSIONS:
            for cid in CONCEPT_ORDER:
                ev = build_concept_events(cid, chords, key=key, meter=meter, style="simple")
                for r in audit_melody(ev, chords, key=key, meter=meter):
                    if r["strong"] and r["label"] != "rest":
                        self.assertEqual(r["label"], LABEL_CHORD_TONE, (cid, r))

    def test_no_fsharp_over_fmaj7_and_d7_third_resolves(self) -> None:
        chords = ["Cmaj7", "Fmaj7", "D7", "G7"]
        for style in STYLES:
            for cid in CONCEPT_ORDER:
                ev = build_concept_events(cid, chords, key="C", style=style)
                rows = audit_melody(ev, chords, key="C")
                for r in rows:
                    if r["chord"] == "Fmaj7" and r["label"] != "rest":
                        self.assertNotEqual(r["midi"] % 12, 6, f"F#/Gb over Fmaj7 in {cid}: {r}")
                    if r["chord"] == "D7" and r["midi"] is not None and r["midi"] % 12 == 6:
                        self.assertEqual(r["label"], LABEL_CHORD_TONE)  # F# = 3rd of D7
                        self.assertIn("3rd of D7", r["function"])
                        self.assertTrue(r["resolved"], r)
                        nxt = rows[r["index"] + 1] if r["index"] + 1 < len(rows) else None
                        if nxt and nxt["label"] != "rest":
                            self.assertEqual(nxt["midi"] - r["midi"], 1, "F# must step up to G")

    def test_chromatic_notes_are_resolved_approach_tones(self) -> None:
        count = 0
        for key, chords, meter in PROGRESSIONS:
            for cid in CONCEPT_ORDER:
                ev = build_concept_events(cid, chords, key=key, meter=meter, style="complex")
                rows = audit_melody(ev, chords, key=key, meter=meter)
                for r in rows:
                    if r["chromatic"] and r["label"] != LABEL_CHORD_TONE:
                        count += 1
                        self.assertEqual(r["label"], LABEL_CHROMATIC_APPROACH, r)
                        self.assertTrue(r["resolved"])
                        nxt = rows[r["index"] + 1]
                        self.assertEqual(abs(nxt["midi"] - r["midi"]), 1)
                        self.assertEqual(nxt["label"], LABEL_CHORD_TONE)
        self.assertGreater(count, 0, "complex style should use some deliberate chromatic approach tones")

    def test_simple_style_has_no_chromatic_non_chord_tones(self) -> None:
        for key, chords, meter in PROGRESSIONS[:2]:
            for cid in CONCEPT_ORDER:
                ev = build_concept_events(cid, chords, key=key, meter=meter, style="simple")
                for r in audit_melody(ev, chords, key=key, meter=meter):
                    if r["chromatic"]:  # only a chord's own accidental (e.g. the 3rd of E7 in A minor)
                        self.assertEqual(r["label"], LABEL_CHORD_TONE)

    def test_audit_flags_the_reported_bad_note(self) -> None:
        # F# held on the downbeat of Fmaj7 with no resolution is exactly what the audit must flag.
        ev = [
            {"pitch": "C4", "midi": 60, "beat": 0, "duration_beats": 4},
            {"pitch": "F#4", "midi": 66, "beat": 4, "duration_beats": 4},
            {"pitch": "E4", "midi": 64, "beat": 8, "duration_beats": 4},
        ]
        bad = audit_violations(audit_melody(ev, ["Cmaj7", "Fmaj7", "D7"], key="C"))
        self.assertTrue(any("F#4" in b and "Fmaj7" in b for b in bad), bad)

    def test_secondary_dominant_and_spelling(self) -> None:
        self.assertEqual(secondary_dominant_label(chord_info("D7", "C"), "C"), "V7/V")
        self.assertEqual(secondary_dominant_label(chord_info("G7", "C"), "C"), "V7")
        self.assertEqual(secondary_dominant_label(chord_info("A7", "C"), "C"), "V7/ii")
        self.assertEqual(chord_info("D7", "C").name_for_pc(6), "F#")

    def test_stays_in_range_and_covers_every_bar(self) -> None:
        for key, chords, meter in PROGRESSIONS:
            for cid in CONCEPT_ORDER:
                ev = build_concept_events(cid, chords, key=key, meter=meter, range_midi=(55, 79))
                for e in ev:
                    if e.get("midi") is not None:
                        self.assertTrue(53 <= e["midi"] <= 81, (cid, e))
                end = max(e["beat"] + e["duration_beats"] for e in ev)
                self.assertAlmostEqual(end, len(chords) * (3 if meter == "3/4" else 4), places=3)
                cur = 0.0
                for e in ev:  # contiguous, non-overlapping timeline
                    self.assertAlmostEqual(e["beat"], cur, places=3)
                    cur += e["duration_beats"]


class TestDescriptionsMatchNotes(unittest.TestCase):
    def test_every_concept_claim_verified(self) -> None:
        for key, chords, meter in PROGRESSIONS[:4]:
            for style in STYLES:
                for cid in CONCEPT_ORDER:
                    ev = build_concept_events(cid, chords, key=key, meter=meter, style=style)
                    ok, why = verify_concept_claim(cid, ev, chords, key=key, meter=meter)
                    self.assertTrue(ok, f"{cid} {key} {chords} {style}: {why}")

    def test_offbeat_accent_has_accented_offbeats_in_notation_and_audio_events(self) -> None:
        from composition_melody_notation import build_abc_from_melody_events

        chords = ["Cmaj7", "Fmaj7", "D7", "G7"]
        ev = build_concept_events("offbeat_accent", chords, key="C")
        f = melody_features(ev, chords, key="C")
        self.assertGreaterEqual(f["accented_offbeat_attacks"], 4)
        abc = build_abc_from_melody_events(ev, key="C", meter="4/4", chords=chords, title="")
        self.assertEqual(abc.count("!>!"), f["accented_offbeat_attacks"])  # notation shows the accents
        text = describe_melody_with_harmony(ev, chords, key="C", concept_id="offbeat_accent")
        self.assertIn(f"{f['accented_offbeat_attacks']} of {f['attacks']} attacks are accented off-beats", text)
        # playback events: the same events drive the synth; off-beat starts are not on integer beats
        offbeat_starts = [e["beat"] for e in ev if not e.get("is_rest") and e["beat"] % 1]
        self.assertEqual(len(offbeat_starts), f["offbeat_attacks"])

    def test_question_answer_phrases(self) -> None:
        chords = ["Cmaj7", "Fmaj7", "D7", "G7"]
        ev = build_concept_events("question_answer", chords, key="C")
        qa = question_answer_facts(ev, chords, key="C")
        self.assertTrue(qa["ok"], qa)
        self.assertNotEqual(qa["q_end_pc"], 0)  # question ends away from the tonic
        self.assertEqual(qa["q_bars"], qa["a_bars"])  # comparable length
        self.assertTrue(qa["a_resolves"])
        self.assertTrue(any(e.get("is_rest") for e in ev))  # a breath between question and answer
        text = describe_melody_with_harmony(ev, chords, key="C", concept_id="question_answer")
        self.assertIn(f"ends open on {qa['q_end']}", text)
        self.assertIn(f"settles on {qa['a_end']}", text)

    def test_direct_line_is_mostly_stepwise_and_directional(self) -> None:
        chords = ["Cmaj7", "Fmaj7", "D7", "G7"]
        f = melody_features(build_concept_events("direct_line", chords, key="C"), chords, key="C")
        self.assertGreaterEqual(f["stepwise_share"], 0.6)
        self.assertGreaterEqual(max(f["up_share"], f["down_share"]), 0.5)

    def test_description_has_no_claim_the_notes_do_not_support(self) -> None:
        chords = ["Cmaj7", "Fmaj7", "D7", "G7"]
        ev = build_concept_events("direct_line", chords, key="C")
        text = describe_melody_with_harmony(ev, chords, key="C", concept_id="direct_line")
        self.assertNotIn("accented", text)
        self.assertNotIn("question", text)
        self.assertFalse(verify_concept_claim("offbeat_accent", ev, chords, key="C")[0])
        self.assertFalse(verify_concept_claim("sighing_descent", ev, chords, key="C")[0])

    def test_feel_maps_to_three_distinct_concepts(self) -> None:
        for feel in ("smooth", "bold", "lyrical", "rhythmic", "emotional", "energetic"):
            ids = concepts_for_feel(feel, limit=3)
            self.assertEqual(len(set(ids)), 3)


if __name__ == "__main__":
    unittest.main()
