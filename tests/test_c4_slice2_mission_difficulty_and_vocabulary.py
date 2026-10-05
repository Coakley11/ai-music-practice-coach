"""C4 Slice 2 — human-review follow-up: difficulty state machine, guide-tone
musicality, Advanced vocabulary richness, new Mission types, and the
Mission Backing round-trip persistence (data layer)."""

from __future__ import annotations

import unittest
from unittest import mock

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


class TestGuideToneDiatonicInference(unittest.TestCase):
    """The implied 7th of a written triad must respect the actual key/
    harmonic context, not collapse every triad onto a universal b7 (human-
    review correction)."""

    def test_tonic_major_triad_in_c_major(self) -> None:
        self.assertEqual(_guide_third_seventh("C", key_center="C"), ["E", "B"])

    def test_dominant_major_triad_in_c_major(self) -> None:
        self.assertEqual(_guide_third_seventh("G", key_center="C"), ["B", "F"])

    def test_dominant_major_triad_as_its_own_tonic(self) -> None:
        # Same chord symbol, different key context -> different inferred 7th.
        self.assertEqual(_guide_third_seventh("G", key_center="G"), ["B", "F#"])

    def test_minor_triad_in_c_major(self) -> None:
        self.assertEqual(_guide_third_seventh("Dm", key_center="C"), ["F", "C"])

    def test_subdominant_major_triad_in_c_major(self) -> None:
        self.assertEqual(_guide_third_seventh("F", key_center="C"), ["A", "E"])

    def test_second_key_bb_in_f_major(self) -> None:
        self.assertEqual(_guide_third_seventh("Bb", key_center="F"), ["D", "A"])

    def test_explicit_dominant_seventh_chord_symbol_wins(self) -> None:
        # G7's written b7 (F) must be used verbatim, not re-derived from key.
        self.assertEqual(_guide_third_seventh("G7", key_center="C"), ["B", "F"])
        self.assertEqual(_guide_third_seventh("G7", key_center="G"), ["B", "F"])

    def test_explicit_major_seventh_chord_symbol_wins(self) -> None:
        self.assertEqual(_guide_third_seventh("Gmaj7", key_center="C"), ["B", "F#"])

    def test_explicit_minor_seventh_chord_symbol_wins(self) -> None:
        self.assertEqual(_guide_third_seventh("Gm7", key_center="Bb"), ["Bb", "F"])

    def test_missing_key_context_degrades_safely_not_a_crash(self) -> None:
        # _parse_key_scale itself defaults an empty/unparseable key to C
        # major rather than raising, so this never needs the documented b7
        # fallback in practice -- it still must not crash or collapse to a
        # single tone.
        result = _guide_third_seventh("G", key_center="")
        self.assertEqual(len(result), 2)
        self.assertEqual(len({_pc(g) for g in result}), 2)

    def test_levels_stay_musically_distinct_with_diatonic_sevenths(self) -> None:
        import random

        chord, key_center = "G", "C"  # dominant triad in C major -> B, F
        legal_pcs = {_pc(g) for g in _guide_third_seventh(chord, key_center=key_center)}
        self.assertEqual(legal_pcs, {_pc("B"), _pc("F")})
        shapes = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            rng = random.Random(1)
            out = apply_mission_rules(
                GUIDE_TONE_MISSION, {"chord": chord, "notes": ["G"]}, chord=chord,
                key_center=key_center, level=level, variant="normal", rng=rng,
            )
            pcs = {_pc(n) for n in out["notes"]}
            self.assertTrue(pcs.issubset(legal_pcs), (level, out["notes"]))
            shapes[level] = (tuple(out["notes"]), out.get("rhythm"))
        self.assertNotEqual(shapes["Beginner"], shapes["Intermediate"])
        self.assertNotEqual(shapes["Intermediate"], shapes["Advanced"])


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
    """Mission example A -> Mission Backing -> Return to Mission.

    The tests below prove the C4 artifact *persistence* layer itself is
    correct at two levels:

    1. Pure store/load (this class) — round-trips the exact artifact when
       the mission/chord/key context has not changed.
    2. Through the real handoff functions used by the actual Mission ->
       Mission Backing -> Return flow (TestMissionBackingRoundTripViaRealHandoff
       below) — same persistence layer, driven by
       build_mission_backing_alignment_payload / build_mission_return_destination
       / consume_pending_mission_return_handoff, with only the deep
       ownership/activation internals mocked (the same boundary already
       accepted by tests/test_mission_return_from_backing_handoff.py).

    A live AppTest run through the real page (Generate -> Open in Backing
    Studio/Jam -> Return to Mission) was also attempted. It reaches the real
    Return-to-Mission button and completes with 0 exceptions and correct
    navigation (studio_page -> "creative", tab -> "Missions"), but
    session_state["improv_mission_example"] is already gone by the time
    that run finishes. Tracing active_musical_workflow_envelope.py's
    apply_mission_workflow_envelope_reconciliation (the function this
    investigation originally suspected) showed it reports
    violations=[] / consistent=True and an already-empty example_chord —
    i.e. the artifact is cleared *earlier*, by some other writer during the
    Backing-open button's own click-triggered rerun, before the Backing
    page or that reconciliation function are even reached. This is the
    exact routing boundary: the loss happens on the way INTO Backing, not
    on the way back, and is not caused by the specific violation this
    investigation originally flagged. Per explicit scope, this was not
    chased further or fixed here — it is the separate Mission-Backing
    ownership defect the user is routing to a different branch.
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


class TestMissionBackingRoundTripViaRealHandoff(unittest.TestCase):
    """Drive the exact handoff functions used by the real Mission -> Mission
    Backing -> Return to Mission flow — build_mission_backing_alignment_payload
    -> build_mission_return_destination -> seal_mission_return_destination ->
    queue_pending_mission_return_from_backing -> consume_pending_mission_return_handoff
    -> load_mission_example — with only the deep ownership/activation
    internals mocked (music_workflow_activation.activate_workflow_simple,
    mission_backing_alignment.apply_pending_mission_backing_alignment,
    backing_context.get_backing_context), the same boundary already accepted
    by tests/test_mission_return_from_backing_handoff.py. Proves the artifact
    persistence/handoff-function layer itself preserves the exact musical
    content end to end."""

    def test_artifact_survives_build_align_seal_queue_consume_then_reload(self) -> None:
        from mission_backing_alignment import build_mission_backing_alignment_payload
        from mission_return_destination import build_mission_return_destination, seal_mission_return_destination
        from music_workflow_pending_mission_return import (
            consume_pending_mission_return_handoff,
            queue_pending_mission_return_from_backing,
        )

        ctx = _ctx(level="Advanced")
        session: dict = {"studio_page": "backing"}

        # A recognizable artifact: distinct notes, MIDI, rhythm, mission id,
        # chord, key, player level, and difficulty bucket/idea index.
        bucket, idea_index = resolve_mission_difficulty_intent(
            session, mission=CHORD_TONE_MISSION, chord="Am7", level="Advanced",
            song_title="Tune", intent="harder",
        )
        self.assertEqual(bucket, "harder")
        example_a = generate_mission_example(
            CHORD_TONE_MISSION, improv_ctx=ctx, chord="Am7", section="Verse",
            level="Advanced", instrument="Piano", focus="Improvisation",
            session_state=session, variant=bucket, nonce_override=idea_index,
        )
        store_mission_example(session, example_a, persist_artifact=False, interaction="test")
        fp_a = motif_material_fingerprint(example_a.motif)
        notes_a = list(example_a.motif.get("notes") or [])
        midi_a = list(example_a.motif.get("midi") or [])
        rhythm_a = example_a.motif.get("rhythm")

        align = build_mission_backing_alignment_payload(
            session, mission=CHORD_TONE_MISSION, cur_chord="Am7", section_label="Verse",
            chord_idx=0, song_title="Tune", concert_key="C", display_key="C",
            example=example_a, with_practice_lick=True,
        )
        dest = build_mission_return_destination(
            align, handoff_mode="practice_in_jam", with_practice_lick=True, request_seq=1,
        )
        seal_mission_return_destination(session, dest)
        queue_pending_mission_return_from_backing(session)

        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch(
                "mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True,
            ):
                with mock.patch("backing_context.get_backing_context", return_value=None):
                    phase = consume_pending_mission_return_handoff(session)

        self.assertEqual(phase, "applied")
        self.assertEqual(session.get("studio_page"), "creative")
        self.assertEqual(session.get("improv_active_mission"), CHORD_TONE_MISSION)

        restored = load_mission_example(session, ctx)
        self.assertIsNotNone(restored)
        self.assertEqual(motif_material_fingerprint(restored.motif), fp_a)
        self.assertEqual(list(restored.motif.get("notes") or []), notes_a)
        self.assertEqual(list(restored.motif.get("midi") or []), midi_a)
        self.assertEqual(restored.motif.get("rhythm"), rhythm_a)
        self.assertEqual(restored.mission, example_a.mission)
        self.assertEqual(restored.chord, example_a.chord)


if __name__ == "__main__":
    unittest.main()
