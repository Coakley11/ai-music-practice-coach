"""C4 Slice 2 — human-review follow-up: difficulty state machine, guide-tone
musicality, Advanced vocabulary richness, new Mission types, and the
Mission Backing round-trip persistence (data layer)."""

from __future__ import annotations

import unittest

from improvisation_intelligence import ImprovSessionContext
from improvisation_mission_rules import _chord_tone_pcs, _guide_third_seventh, _pc, apply_mission_rules, chord_tone_names
from improvisation_mission_specs import validate_mission_motif
from improvisation_missions import (
    generate_mission_example,
    generate_mission_example_distinct,
    load_mission_example,
    motif_material_fingerprint,
    resolve_mission_difficulty_intent,
    store_mission_example,
)
from improvisation_motif import sync_motif_midi
from tests.test_improvisation_motif_abc import assert_mission_outputs_synchronized

CHORD_TONE_MISSION = "Improvise using only chord tones"
GUIDE_TONE_MISSION = "Target only guide tones (3rds & 7ths)"
RESOLVE_BEAT1_MISSION = "Resolve every phrase on beat 1"
DOMINANT_TENSION_MISSION = "Create tension on dominant chords"
CHROMATIC_APPROACH_MISSION = "Approach a chord tone chromatically"
ENCLOSURE_MISSION = "Enclose a target chord tone before resolving"
TARGET_THIRD_MISSION = "Resolve convincingly to the chord's 3rd"
BEBOP_MISSION = "Create a bebop-style line"
NEW_MISSIONS = (CHROMATIC_APPROACH_MISSION, ENCLOSURE_MISSION, TARGET_THIRD_MISSION, BEBOP_MISSION)


def _ctx(level: str = "Advanced", instrument: str = "Piano") -> ImprovSessionContext:
    return ImprovSessionContext(
        song_title="Tune",
        artist="Artist",
        key_center="C",
        display_key="C",
        instrument=instrument,
        level=level,
        focus="Improvisation",
        sections={"Verse": ["Am7"]},
    )


class TestDefaultDifficultyIsMedium(unittest.TestCase):
    def test_fresh_context_defaults_to_normal_bucket(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            session: dict = {}
            bucket, idea = resolve_mission_difficulty_intent(
                session, mission=CHORD_TONE_MISSION, chord="Am7", level=level,
                song_title="Tune", intent="generate",
            )
            self.assertEqual(bucket, "normal")
            self.assertEqual(idea, 0)

    def test_new_context_resets_even_after_moving_to_harder(self) -> None:
        session: dict = {}
        resolve_mission_difficulty_intent(
            session, mission=CHORD_TONE_MISSION, chord="Am7", level="Intermediate",
            song_title="Tune", intent="harder",
        )
        bucket, idea = resolve_mission_difficulty_intent(
            session, mission=CHORD_TONE_MISSION, chord="Dm7", level="Intermediate",
            song_title="Tune", intent="generate",
        )
        self.assertEqual(bucket, "normal")
        self.assertEqual(idea, 0)


class TestEasierHarderNewReliability(unittest.TestCase):
    """Root cause: Easier/Harder had a 100%-deterministic seed (no nonce at
    all) so repeated presses returned the identical example, and New Idea
    unconditionally reset to the "normal" bucket regardless of where the
    student actually was. Both are fixed by resolve_mission_difficulty_intent
    + generalizing generate_mission_example_distinct's retry-until-different
    logic to every bucket."""

    def _press(self, session, mission, chord, level, song_title, intent, prior_motif):
        bucket, idea = resolve_mission_difficulty_intent(
            session, mission=mission, chord=chord, level=level, song_title=song_title, intent=intent,
        )
        ctx = _ctx(level=level)
        ex, retries, retried = generate_mission_example_distinct(
            mission, improv_ctx=ctx, chord=chord, section="Verse", level=level,
            instrument="Piano", focus="Improvisation", variant=bucket,
            session_state=session, nonce_override=idea,
            prior_material_fp=motif_material_fingerprint(prior_motif),
        )
        return bucket, idea, ex

    def test_harder_never_escalates_past_the_player_level(self) -> None:
        session: dict = {}
        prior = None
        buckets = []
        for _ in range(5):
            bucket, _idea, ex = self._press(
                session, CHORD_TONE_MISSION, "Am7", "Beginner", "Tune", "harder", prior
            )
            buckets.append(bucket)
            prior = ex.motif
        self.assertEqual(set(buckets), {"easier", "normal", "harder"} & set(buckets))
        # Never escalates to a 4th, "beyond harder" position.
        self.assertTrue(all(b in ("easier", "normal", "harder") for b in buckets))
        self.assertEqual(buckets[-1], "harder")

    def test_repeated_harder_presses_avoid_immediate_repeats(self) -> None:
        session: dict = {}
        prior = None
        seen = []
        for _ in range(4):
            _bucket, _idea, ex = self._press(
                session, CHORD_TONE_MISSION, "Am7", "Intermediate", "Tune", "harder", prior
            )
            mat = motif_material_fingerprint(ex.motif)
            if seen:
                self.assertNotEqual(mat, seen[-1], "two consecutive Harder presses returned the same example")
            seen.append(mat)
            prior = ex.motif

    def test_repeated_easier_presses_avoid_immediate_repeats_and_floor_correctly(self) -> None:
        session: dict = {}
        prior = None
        seen = []
        buckets = []
        for _ in range(5):
            bucket, _idea, ex = self._press(
                session, CHORD_TONE_MISSION, "Am7", "Advanced", "Tune", "easier", prior
            )
            buckets.append(bucket)
            mat = motif_material_fingerprint(ex.motif)
            if seen:
                self.assertNotEqual(mat, seen[-1])
            seen.append(mat)
            prior = ex.motif
        self.assertEqual(buckets[-1], "easier")  # floor, never below

    def test_new_idea_preserves_current_bucket_not_reset_to_normal(self) -> None:
        session: dict = {}
        prior = None
        bucket1, _idea1, ex1 = self._press(
            session, CHORD_TONE_MISSION, "Am7", "Intermediate", "Tune", "harder", prior
        )
        self.assertEqual(bucket1, "harder")
        bucket2, _idea2, ex2 = self._press(
            session, CHORD_TONE_MISSION, "Am7", "Intermediate", "Tune", "new", ex1.motif
        )
        # New Idea must stay at the bucket the student was just looking at.
        self.assertEqual(bucket2, "harder")
        self.assertNotEqual(
            motif_material_fingerprint(ex1.motif), motif_material_fingerprint(ex2.motif)
        )

    def test_every_press_still_validates(self) -> None:
        session: dict = {}
        prior = None
        for intent in ("harder", "harder", "new", "easier", "easier", "easier", "new"):
            _bucket, _idea, ex = self._press(
                session, GUIDE_TONE_MISSION, "Am7", "Advanced", "Tune", intent, prior
            )
            ok, reason = validate_mission_motif(GUIDE_TONE_MISSION, ex.motif, chord="Am7", key_center="C")
            self.assertTrue(ok, reason)
            prior = ex.motif


class TestGuideToneMusicality(unittest.TestCase):
    def test_bare_triad_chord_still_produces_two_distinct_guide_tones(self) -> None:
        """Live-review finding: a plain triad symbol ("G", no written 7th —
        extremely common in real songs) collapsed _guide_third_seventh to a
        single tone, so every level repeated one frozen pitch forever."""
        chord, key_center = "G", "G"
        guide_tones = _guide_third_seventh(chord, key_center=key_center)
        self.assertEqual(len(guide_tones), 2)
        self.assertEqual(len({_pc(g) for g in guide_tones}), 2)
        import random

        for level in ("Beginner", "Intermediate", "Advanced"):
            rng = random.Random(1)
            out = apply_mission_rules(
                GUIDE_TONE_MISSION, {"chord": chord, "notes": ["G"]}, chord=chord,
                key_center=key_center, level=level, variant="normal", rng=rng,
            )
            self.assertGreater(len({_pc(n) for n in out["notes"]}), 1, (level, out["notes"]))
            ok, reason = validate_mission_motif(GUIDE_TONE_MISSION, out, chord=chord, key_center=key_center)
            self.assertTrue(ok, reason)

    def test_only_legal_pitch_classes_at_every_level(self) -> None:
        chord, key_center = "Am7", "C"
        guide_pcs = {_pc(g) for g in _guide_third_seventh(chord, key_center=key_center)}
        for level in ("Beginner", "Intermediate", "Advanced"):
            import random

            rng = random.Random(5)
            out = apply_mission_rules(
                GUIDE_TONE_MISSION, {"chord": chord, "notes": ["A"]}, chord=chord,
                key_center=key_center, level=level, variant="normal", rng=rng,
            )
            pcs = {_pc(n) for n in out["notes"]}
            self.assertTrue(pcs.issubset(guide_pcs), (level, pcs))

    def test_intermediate_and_advanced_differ_from_beginner_in_shape(self) -> None:
        import random

        chord, key_center = "Am7", "C"
        shapes = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            rng = random.Random(1)
            out = apply_mission_rules(
                GUIDE_TONE_MISSION, {"chord": chord, "notes": ["A"]}, chord=chord,
                key_center=key_center, level=level, variant="normal", rng=rng,
            )
            shapes[level] = (tuple(out["notes"]), out.get("rhythm"))
        self.assertNotEqual(shapes["Beginner"], shapes["Intermediate"])
        self.assertNotEqual(shapes["Intermediate"], shapes["Advanced"])

    def test_advanced_guide_tone_rhythm_is_not_flat_quarters(self) -> None:
        import random

        chord, key_center = "Am7", "C"
        saw_non_quarter = False
        for seed in range(6):
            rng = random.Random(seed)
            out = apply_mission_rules(
                GUIDE_TONE_MISSION, {"chord": chord, "notes": ["A"]}, chord=chord,
                key_center=key_center, level="Advanced", variant="normal", rng=rng,
            )
            syms = out.get("rhythm_symbols") or []
            if any(s not in ("♩",) for s in syms):
                saw_non_quarter = True
        self.assertTrue(saw_non_quarter, "expected rhythmic variety from the shared rhythm engine")


class TestAdvancedVocabularyAccess(unittest.TestCase):
    def test_compatible_missions_can_reach_chromatic_vocabulary_at_advanced(self) -> None:
        import random

        key_center = "C"
        # Dominant tension needs an actual dominant-quality chord to engage
        # its tension branch at all; the others use the Am7 minor seventh.
        cases = {
            RESOLVE_BEAT1_MISSION: ("Am7", 1, 5),
            DOMINANT_TENSION_MISSION: ("G7", 0, 8),
            CHROMATIC_APPROACH_MISSION: ("Am7", 0, 6),
            BEBOP_MISSION: ("Am7", 0, 10),
        }
        for mission, (chord, start, length) in cases.items():
            allowed = _chord_tone_pcs(chord, key_center=key_center)
            saw_chromatic = False
            for seed in range(20):
                rng = random.Random(seed)
                out = apply_mission_rules(
                    mission, {"chord": chord, "notes": ["A"] * 6}, chord=chord,
                    key_center=key_center, level="Advanced", variant="normal", rng=rng,
                )
                pcs = {_pc(n) for n in (out["notes"] or [])[start:]}
                if not pcs.issubset(allowed):
                    saw_chromatic = True
                    break
            self.assertTrue(saw_chromatic, f"{mission} never showed chromatic vocabulary at Advanced")

    def test_chord_tones_only_mission_never_gains_illegal_notes_at_advanced(self) -> None:
        import random

        chord, key_center = "Am7", "C"
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        for seed in range(10):
            rng = random.Random(seed)
            out = apply_mission_rules(
                CHORD_TONE_MISSION, {"chord": chord, "notes": ["A"]}, chord=chord,
                key_center=key_center, level="Advanced", variant="normal", rng=rng,
            )
            pcs = {_pc(n) for n in out["notes"]}
            self.assertTrue(pcs.issubset(allowed))


class TestNewMissionTypes(unittest.TestCase):
    def test_each_new_mission_validates_at_every_level(self) -> None:
        import random

        chord, key_center = "Am7", "C"
        for mission in NEW_MISSIONS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                rng = random.Random(3)
                out = apply_mission_rules(
                    mission, {"chord": chord, "notes": ["A", "C", "E"]}, chord=chord,
                    key_center=key_center, level=level, variant="normal", rng=rng,
                )
                ok, reason = validate_mission_motif(mission, out, chord=chord, key_center=key_center)
                self.assertTrue(ok, (mission, level, reason))

    def test_target_third_mission_resolves_to_the_actual_third(self) -> None:
        import random

        chord, key_center = "Am7", "C"
        third_pc = _pc(chord_tone_names(chord, reference_key=key_center)[1])
        for level in ("Beginner", "Intermediate", "Advanced"):
            rng = random.Random(2)
            out = apply_mission_rules(
                TARGET_THIRD_MISSION, {"chord": chord, "notes": ["A"]}, chord=chord,
                key_center=key_center, level=level, variant="normal", rng=rng,
            )
            self.assertEqual(_pc(out["notes"][-1]), third_pc)

    def test_bebop_mission_advanced_richer_than_beginner(self) -> None:
        import random

        chord, key_center = "Am7", "C"
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        rng_b = random.Random(9)
        beginner = apply_mission_rules(
            BEBOP_MISSION, {"chord": chord, "notes": ["A"]}, chord=chord,
            key_center=key_center, level="Beginner", variant="normal", rng=rng_b,
        )
        self.assertTrue({_pc(n) for n in beginner["notes"]}.issubset(allowed))
        saw_chromatic = False
        for seed in range(15):
            rng_a = random.Random(seed)
            advanced = apply_mission_rules(
                BEBOP_MISSION, {"chord": chord, "notes": ["A"]}, chord=chord,
                key_center=key_center, level="Advanced", variant="normal", rng=rng_a,
            )
            if not ({_pc(n) for n in advanced["notes"]}).issubset(allowed):
                saw_chromatic = True
                break
        self.assertTrue(saw_chromatic)

    def test_new_missions_notation_and_midi_stay_exact(self) -> None:
        for mission in NEW_MISSIONS:
            example = generate_mission_example(
                mission, improv_ctx=_ctx(level="Advanced"), chord="Am7", section="Verse",
                level="Advanced", instrument="Piano", focus="Improvisation",
            )
            assert_mission_outputs_synchronized(example, expect_tab=False)


class TestMissionBackingRoundTripDataLayer(unittest.TestCase):
    """Mission example A -> (open Mission Backing happens elsewhere, out of
    scope) -> Return to Mission re-renders via load_mission_example. At the
    data layer, store/load must round-trip the exact artifact when the
    mission/chord/key context has not changed.

    This proves the persistence layer itself is correct. It does NOT prove
    the ownership/routing machinery around the real Backing round trip never
    clears this artifact first (see active_musical_workflow_envelope.py's
    VIOLATION_MISSION_EXAMPLE_OWNER_MISMATCH handling) — that lives in
    explicitly out-of-scope ownership code and was flagged, not changed,
    in this slice.
    """

    def test_store_then_load_preserves_exact_musical_content(self) -> None:
        ctx = _ctx(level="Advanced")
        session: dict = {}
        example_a = generate_mission_example(
            CHORD_TONE_MISSION, improv_ctx=ctx, chord="Am7", section="Verse",
            level="Advanced", instrument="Piano", focus="Improvisation",
            session_state=session,
        )
        store_mission_example(session, example_a, persist_artifact=False, interaction="test")
        fp_a = motif_material_fingerprint(example_a.motif)

        restored = load_mission_example(session, ctx)

        self.assertEqual(motif_material_fingerprint(restored.motif), fp_a)
        self.assertEqual(restored.motif.get("notes"), example_a.motif.get("notes"))
        self.assertEqual(restored.motif.get("midi"), example_a.motif.get("midi"))
        self.assertEqual(restored.motif.get("rhythm"), example_a.motif.get("rhythm"))
        self.assertEqual(restored.mission, example_a.mission)
        self.assertEqual(restored.chord, example_a.chord)

    def test_store_then_load_survives_an_intervening_difficulty_press(self) -> None:
        """Simulates: generate A, (open/return from Backing with no key
        change), then the student presses Harder — the *restore* step itself
        (before any new press) must still be exact."""
        ctx = _ctx(level="Advanced")
        session: dict = {}
        example_a = generate_mission_example(
            CHORD_TONE_MISSION, improv_ctx=ctx, chord="Am7", section="Verse",
            level="Advanced", instrument="Piano", focus="Improvisation",
            session_state=session,
        )
        store_mission_example(session, example_a, persist_artifact=False, interaction="test")
        fp_a = motif_material_fingerprint(example_a.motif)

        # Round trip (data layer) before any new button press.
        restored = load_mission_example(session, ctx)
        self.assertEqual(motif_material_fingerprint(restored.motif), fp_a)


if __name__ == "__main__":
    unittest.main()
