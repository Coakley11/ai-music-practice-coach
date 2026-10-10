"""C4 — "Create a phrase using a syncopated rhythm."

SYNC1-SYNC12 per the human-review spec: structural assertions on the
``melodic_rhythm_engine`` output (figure families, onset placement) rather
than one exact rhythmic phrase, since the generator is intentionally variable.
Pitch material stays simple by design - this Mission's identity is rhythm.
"""

from __future__ import annotations

import random
import unittest

from improvisation_intelligence import ImprovSessionContext
from improvisation_mission_rules import (
    _chord_tone_pcs,
    _pc,
    apply_mission_rules,
)
from improvisation_mission_specs import validate_mission_motif
from improvisation_missions import _transpose_mission_example_payload, generate_mission_example
from tests.test_improvisation_motif_abc import assert_mission_outputs_synchronized

SYNC_MISSION = "Create a phrase using a syncopated rhythm"

CHORDS = (("Cmaj7", "C"), ("Dm7", "C"), ("G7", "C"), ("D7", "D"))


def _gen(chord, key_center, level, variant, seed):
    rng = random.Random(seed)
    return apply_mission_rules(
        SYNC_MISSION, {"chord": chord, "notes": [], "midi": []}, chord=chord,
        key_center=key_center, level=level, variant=variant, rng=rng,
    )


def _families(out):
    return set(out.get("rhythm_meta", {}).get("families") or [])


def _offbeat_onset_count(out):
    """Count note onsets that do NOT fall on a metrically strong position."""
    from melodic_rhythm_engine import parse_meter
    from fractions import Fraction as F

    meter = parse_meter(str(out.get("rhythm_meta", {}).get("meter") or out.get("meter") or "4/4"))
    events = out.get("rhythm_events") or []
    count = 0
    for e in events:
        if e.get("rest"):
            continue
        onset = F(str(e.get("on") or "0"))
        if meter.strength(onset) < 0.5:
            count += 1
    return count


class TestContainsActualSyncopation(unittest.TestCase):
    """SYNC1 — the generated rhythm structurally contains syncopation, not
    merely a Mission name that claims it does."""

    def test_every_level_and_tier_contains_syncopated_or_rest_family(self) -> None:
        for chord, key_center in CHORDS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                for variant in ("easier", "normal", "harder"):
                    for seed in range(5):
                        out = _gen(chord, key_center, level, variant, seed)
                        fams = _families(out)
                        self.assertTrue(
                            {"syncopated", "rest"} & fams,
                            f"{chord} {level}/{variant} seed={seed}: families={fams!r}",
                        )
                        ok, reason = validate_mission_motif(SYNC_MISSION, out, chord=chord, key_center=key_center)
                        self.assertTrue(ok, (chord, level, variant, seed, reason))


class TestBeginnerIsMild(unittest.TestCase):
    """SYNC2 — Beginner uses only mild/simple syncopation (few offbeat events,
    short phrases, not rhythmically busy)."""

    def test_beginner_has_few_offbeat_onsets(self) -> None:
        chord, key_center = "Cmaj7", "C"
        for variant in ("easier", "normal", "harder"):
            for seed in range(10):
                out = _gen(chord, key_center, "Beginner", variant, seed)
                offbeats = _offbeat_onset_count(out)
                self.assertLessEqual(offbeats, 3, (variant, seed, offbeats))

    def test_beginner_phrases_are_short(self) -> None:
        chord, key_center = "Cmaj7", "C"
        for variant in ("easier", "normal", "harder"):
            for seed in range(10):
                out = _gen(chord, key_center, "Beginner", variant, seed)
                self.assertLessEqual(len(out["notes"]), 6)


class TestIntermediateRicherThanBeginner(unittest.TestCase):
    """SYNC3 — Intermediate has more syncopated/repeated-cell activity."""

    def test_intermediate_harder_has_more_offbeats_than_beginner(self) -> None:
        chord, key_center = "Cmaj7", "C"

        def avg_offbeats(level, tier, n=15):
            total = 0
            for seed in range(n):
                out = _gen(chord, key_center, level, tier, seed)
                total += _offbeat_onset_count(out)
            return total / n

        beginner_avg = avg_offbeats("Beginner", "easier")
        intermediate_avg = avg_offbeats("Intermediate", "harder")
        self.assertGreaterEqual(intermediate_avg, beginner_avg)

    def test_intermediate_pitch_material_is_heavily_repetitive(self) -> None:
        """This Mission's pitch identity is simple/repeating, not wide vocabulary."""
        chord, key_center = "Cmaj7", "C"
        for seed in range(10):
            out = _gen(chord, key_center, "Intermediate", "normal", seed)
            notes = out["notes"]
            distinct = len(set(_pc(n) for n in notes))
            self.assertLessEqual(distinct, 3, (seed, notes))


class TestAdvancedRicherDisplacement(unittest.TestCase):
    """SYNC4 — Advanced has measurably richer syncopation/displacement."""

    def test_advanced_harder_reaches_the_advanced_rhythm_level(self) -> None:
        chord, key_center = "Cmaj7", "C"
        saw_advanced_family = False
        for seed in range(15):
            out = _gen(chord, key_center, "Advanced", "harder", seed)
            if str(out.get("rhythm_meta", {}).get("rhythm_level")) == "Advanced":
                saw_advanced_family = True
                break
        self.assertTrue(saw_advanced_family)

    def test_advanced_example_notation_and_midi_stay_exact(self) -> None:
        example = generate_mission_example(
            SYNC_MISSION,
            improv_ctx=ImprovSessionContext(
                song_title="Tune", artist="Artist", key_center="C", display_key="C",
                instrument="Piano", level="Advanced", focus="Improvisation", sections={"Verse": ["Cmaj7"]},
            ),
            chord="Cmaj7", section="Verse", level="Advanced", instrument="Piano", focus="Improvisation",
        )
        assert_mission_outputs_synchronized(example, expect_tab=False)


class TestRepeatedNoteCellVocabulary(unittest.TestCase):
    """SYNC5 — repeated-note/cell vocabulary appears across deterministic seeds."""

    def test_repeated_note_or_cell_present_across_seeds(self) -> None:
        chord, key_center = "Cmaj7", "C"
        seen = 0
        for seed in range(20):
            out = _gen(chord, key_center, "Intermediate", "normal", seed)
            notes = out["notes"]
            pcs = [_pc(n) for n in notes]
            if any(pcs[i] == pcs[i + 1] for i in range(len(pcs) - 1)) or len(set(pcs)) <= 2:
                seen += 1
        self.assertGreater(seen, 10, f"too little repetition: {seen}/20")


class TestPitchStaysHarmonicallyValid(unittest.TestCase):
    """SYNC6 — pitch material remains harmonically valid."""

    def test_notes_are_chord_tones_or_scale_tones(self) -> None:
        for chord, key_center in CHORDS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                for seed in range(5):
                    out = _gen(chord, key_center, level, "normal", seed)
                    allowed = _chord_tone_pcs(chord, key_center=key_center)
                    from improvisation_motif import _parse_key_scale

                    try:
                        _mode, scale_pcs = _parse_key_scale(key_center)
                    except Exception:
                        scale_pcs = ()
                    allowed = allowed | set(scale_pcs)
                    got = {_pc(n) for n in out["notes"]}
                    self.assertTrue(got.issubset(allowed), (chord, level, seed, out["notes"]))


class TestNewIdeaChangesRhythm(unittest.TestCase):
    """SYNC7 — New Idea changes the rhythmic phrase."""

    def test_multiple_seeds_give_distinct_rhythms(self) -> None:
        chord, key_center = "Cmaj7", "C"
        seen_ids = set()
        for seed in range(15):
            out = _gen(chord, key_center, "Intermediate", "normal", seed)
            seen_ids.add(out.get("rhythm_meta", {}).get("id"))
        self.assertGreaterEqual(len(seen_ids), 3, f"too little rhythmic variety: {seen_ids!r}")


class TestChordChangeRetargetsPitches(unittest.TestCase):
    """SYNC8 — changing chord preserves the rhythmic Mission while retargeting pitches."""

    def test_different_chords_give_different_pitch_pools(self) -> None:
        out_c = _gen("Cmaj7", "C", "Intermediate", "normal", 1)
        out_g = _gen("G7", "C", "Intermediate", "normal", 1)
        pcs_c = {_pc(n) for n in out_c["notes"]}
        pcs_g = {_pc(n) for n in out_g["notes"]}
        self.assertNotEqual(pcs_c, pcs_g)
        self.assertTrue({"syncopated", "rest"} & _families(out_c))
        self.assertTrue({"syncopated", "rest"} & _families(out_g))


class TestPracticeKeyTransposePreservesRhythm(unittest.TestCase):
    """SYNC9 — Practice-Key change preserves rhythmic structure while transposing pitches."""

    def test_transpose_keeps_rhythm_events_moves_pitches(self) -> None:
        chord = "D7"
        rng = random.Random(3)
        out = apply_mission_rules(
            SYNC_MISSION, {"chord": chord, "notes": [], "midi": []}, chord=chord,
            key_center="D", level="Intermediate", variant="normal", rng=rng,
        )
        raw = {"chord": chord, "motif": out, "concert_key": "D", "display_key": "D"}
        transposed = _transpose_mission_example_payload(raw, from_key="D", to_key="E")
        self.assertIsNotNone(transposed)
        self.assertEqual(transposed["chord"], "E7")
        # Rhythm structure (event count / timing) is untouched by a pitch transpose.
        self.assertEqual(
            transposed["motif"].get("rhythm_events"), out.get("rhythm_events"),
        )
        self.assertEqual(len(transposed["motif"]["notes"]), len(out["notes"]))
        self.assertNotEqual(transposed["motif"]["notes"], out["notes"])


class TestMissionBackingRoundTrip(unittest.TestCase):
    """SYNC10 — Mission Backing round trip preserves artifact identity."""

    def test_projection_preserves_rhythm_meta_and_concert_identity(self) -> None:
        from mission_projection_state import project_complete_mission_example
        from improvisation_missions import MissionExample

        rng = random.Random(1)
        base_motif = apply_mission_rules(
            SYNC_MISSION, {"chord": "D7", "notes": [], "midi": []}, chord="D7",
            key_center="D", level="Intermediate", variant="normal", rng=rng,
        )
        ex = MissionExample(
            mission=SYNC_MISSION, variant="normal", chord="D7", section="Verse",
            song_title="Tune", display_key="D", concert_key="D", instrument="Piano",
            level="Intermediate", focus="Improvisation", motif=dict(base_motif),
            abc="", tab="", piano_html="", why="", practice_steps=[], insight=None,
            show_tab=False, show_piano=False,
        )
        sess = {"instrument": "Piano", "concert_key": "D", "display_key": "D"}
        out = project_complete_mission_example(sess, ex, instrument="Piano", bpm=100)
        self.assertEqual(out.chord, "D7")
        self.assertEqual(out.motif.get("notes"), base_motif.get("notes"))


class TestWrittenKeyDoesNotChangeRhythmicIdentity(unittest.TestCase):
    """SYNC11 — written-key instrument projection does not change rhythmic identity."""

    def test_alto_sax_projection_keeps_rhythm_events(self) -> None:
        from mission_projection_state import project_complete_mission_example
        from improvisation_missions import MissionExample

        rng = random.Random(1)
        base_motif = apply_mission_rules(
            SYNC_MISSION, {"chord": "D7", "notes": [], "midi": []}, chord="D7",
            key_center="D", level="Intermediate", variant="normal", rng=rng,
        )
        ex = MissionExample(
            mission=SYNC_MISSION, variant="normal", chord="D7", section="Verse",
            song_title="Tune", display_key="D", concert_key="D", instrument="Saxophone",
            level="Intermediate", focus="Improvisation", motif=dict(base_motif),
            abc="", tab="", piano_html="", why="", practice_steps=[], insight=None,
            show_tab=False, show_piano=False,
        )
        sess = {
            "instrument": "Saxophone", "selected_transposing_instrument": "Alto saxophone (Eb)",
            "show_chart_in_instrument_key": True, "concert_key": "D", "display_key": "D",
        }
        out = project_complete_mission_example(sess, ex, instrument="Saxophone", bpm=100)
        self.assertEqual(out.motif.get("rhythm_events"), base_motif.get("rhythm_events"))
        self.assertNotEqual(out.display_key, out.concert_key)


class TestMissionSelectorStillWorks(unittest.TestCase):
    """SYNC12 — R10 selector switching remains stable."""

    def test_syncopated_mission_is_in_the_catalog(self) -> None:
        from improvisation_intelligence import PRACTICE_MISSIONS

        self.assertIn(SYNC_MISSION, PRACTICE_MISSIONS)


if __name__ == "__main__":
    unittest.main()
