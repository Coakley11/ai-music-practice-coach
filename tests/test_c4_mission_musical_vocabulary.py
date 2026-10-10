"""C4 — Missions reuse the shared melodic pattern/rhythm vocabulary.

Covers the four migrated categories (chord-tone targeting, guide-tone
resolution, chromatic-approach/enclosure resolution, rhythm-focused) across
Beginner/Intermediate/Advanced, proving:

- the Mission objective always wins (validator + hand constraints still pass)
- Beginner stays on the plain, simple pool (no engine, no chromatic leakage)
- Intermediate/Advanced may draw richer shapes from melodic_pattern_engine /
  melodic_rhythm_engine, gated by the engine's own per-family difficulty
- generation is side-effect-free with respect to ownership/key state
"""

from __future__ import annotations

import random
import unittest

from improvisation_intelligence import ImprovSessionContext
from improvisation_missions import generate_mission_example
from improvisation_mission_rules import apply_mission_rules, _chord_tone_pcs, _guide_third_seventh, _pc
from improvisation_mission_specs import validate_mission_motif
from improvisation_motif import sync_motif_midi
from tests.test_improvisation_motif_abc import assert_mission_outputs_synchronized

CHORD_TONE_MISSION = "Improvise using only chord tones"
GUIDE_TONE_MISSION = "Target only guide tones (3rds & 7ths)"
RESOLVE_BEAT1_MISSION = "Resolve every phrase on beat 1"
RHYTHM_MISSION = "Focus on rhythm over note choice"


def _seed_motif() -> dict:
    return {
        "chord": "Am7",
        "notes": ["A", "C", "E"],
        "rhythm_symbols": ["quarter", "quarter", "quarter"],
        "rhythm_key": "quarter-quarter-quarter",
        "rhythm": "quarter quarter quarter",
    }


class TestBeginnerStaysSimple(unittest.TestCase):
    """Beginner must never see engine-sourced chromatic/outside vocabulary."""

    def test_chord_tone_mission_beginner_matches_plain_pool_contract(self) -> None:
        chord, key_center = "Am7", "C"
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        for seed in range(8):
            rng = random.Random(seed)
            out = apply_mission_rules(
                CHORD_TONE_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                level="Beginner", variant="normal", rng=rng,
            )
            pcs = {_pc(n) for n in out["notes"]}
            self.assertTrue(pcs.issubset(allowed), pcs)
            ok, reason = validate_mission_motif(CHORD_TONE_MISSION, out, chord=chord, key_center=key_center)
            self.assertTrue(ok, reason)

    def test_guide_tone_mission_beginner_stays_on_two_pitch_classes(self) -> None:
        chord, key_center = "Am7", "C"
        guide_pool = _guide_third_seventh(chord, key_center=key_center)
        guide_pcs = {_pc(g) for g in guide_pool}
        for seed in range(8):
            rng = random.Random(seed)
            out = apply_mission_rules(
                GUIDE_TONE_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                level="Beginner", variant="normal", rng=rng,
            )
            pcs = {_pc(n) for n in out["notes"]}
            self.assertTrue(pcs.issubset(guide_pcs), pcs)
            ok, reason = validate_mission_motif(GUIDE_TONE_MISSION, out, chord=chord, key_center=key_center)
            self.assertTrue(ok, reason)


class TestIntermediateAndAdvancedVocabulary(unittest.TestCase):
    """Shared-engine vocabulary may appear at Intermediate/Advanced, and the
    mission's hard constraint still wins regardless of which family is used."""

    def test_chord_tone_mission_intermediate_and_advanced_still_pure(self) -> None:
        chord, key_center = "Am7", "C"
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        for level in ("Intermediate", "Advanced"):
            for seed in range(10):
                rng = random.Random(seed)
                out = apply_mission_rules(
                    CHORD_TONE_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                    level=level, variant="normal", rng=rng,
                )
                pcs = {_pc(n) for n in out["notes"]}
                self.assertTrue(pcs.issubset(allowed), (level, seed, pcs))
                ok, reason = validate_mission_motif(CHORD_TONE_MISSION, out, chord=chord, key_center=key_center)
                self.assertTrue(ok, (level, seed, reason))

    def test_guide_tone_mission_intermediate_and_advanced_still_pure(self) -> None:
        chord, key_center = "Am7", "C"
        guide_pool = _guide_third_seventh(chord, key_center=key_center)
        guide_pcs = {_pc(g) for g in guide_pool}
        for level in ("Intermediate", "Advanced"):
            for seed in range(10):
                rng = random.Random(seed)
                out = apply_mission_rules(
                    GUIDE_TONE_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                    level=level, variant="normal", rng=rng,
                )
                pcs = {_pc(n) for n in out["notes"]}
                self.assertTrue(pcs.issubset(guide_pcs), (level, seed, pcs))
                ok, reason = validate_mission_motif(GUIDE_TONE_MISSION, out, chord=chord, key_center=key_center)
                self.assertTrue(ok, (level, seed, reason))

    def test_resolve_beat1_advanced_can_use_chromatic_approach_but_still_lands_root(self) -> None:
        chord, key_center = "Am7", "C"
        from improvisation_mission_rules import chord_tone_names

        root = chord_tone_names(chord, reference_key=key_center)[0]
        saw_chromatic_tail = False
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        for seed in range(30):
            rng = random.Random(seed)
            out = apply_mission_rules(
                RESOLVE_BEAT1_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                level="Advanced", variant="normal", rng=rng,
            )
            # Mission objective always wins: beat 1 (index 0) is always the root.
            self.assertEqual(out["notes"][0], root, (seed, out["notes"]))
            tail_pcs = {_pc(n) for n in out["notes"][1:]}
            if not tail_pcs.issubset(allowed):
                saw_chromatic_tail = True
        self.assertTrue(saw_chromatic_tail, "expected at least one Advanced seed to use chromatic-approach vocabulary")

    def test_resolve_beat1_beginner_and_intermediate_unaffected(self) -> None:
        chord, key_center = "Am7", "C"
        from improvisation_mission_rules import chord_tone_names

        root = chord_tone_names(chord, reference_key=key_center)[0]
        for level in ("Beginner", "Intermediate"):
            for seed in range(6):
                rng = random.Random(seed)
                out = apply_mission_rules(
                    RESOLVE_BEAT1_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                    level=level, variant="normal", rng=rng,
                )
                self.assertEqual(out["notes"][0], root)


class TestRhythmFocusedMission(unittest.TestCase):
    """Rhythm-focused mission: pitch stays a plain chord-tone pool at every
    level; only the rhythm draws from the shared rhythm engine."""

    def test_pitch_pool_unchanged_across_levels(self) -> None:
        chord, key_center = "Am7", "C"
        allowed = _chord_tone_pcs(chord, key_center=key_center)
        for level in ("Beginner", "Intermediate", "Advanced"):
            rng = random.Random(1)
            out = apply_mission_rules(
                RHYTHM_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                level=level, variant="normal", rng=rng,
            )
            pcs = {_pc(n) for n in out["notes"]}
            self.assertTrue(pcs.issubset(allowed), (level, pcs))
            self.assertEqual(len(out.get("rhythm_symbols") or []), len(out.get("notes") or []))

    def test_rhythm_varies_run_to_run_via_shared_engine(self) -> None:
        chord, key_center = "Am7", "C"
        rhythms = set()
        for seed in range(8):
            rng = random.Random(seed)
            out = apply_mission_rules(
                RHYTHM_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                level="Advanced", variant="normal", rng=rng,
            )
            rhythms.add(out.get("rhythm"))
        self.assertGreater(len(rhythms), 1, "expected rhythm variety from the shared rhythm engine")


class TestMissionCorrectnessAcrossContext(unittest.TestCase):
    """Chord/key changes retarget correctly; validator always gates output."""

    def test_switching_chord_retargets_chord_tone_mission(self) -> None:
        key_center = "C"
        for chord in ("Am7", "Dm7", "G7", "Cmaj7"):
            allowed = _chord_tone_pcs(chord, key_center=key_center)
            rng = random.Random(7)
            out = apply_mission_rules(
                CHORD_TONE_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                level="Advanced", variant="normal", rng=rng,
            )
            pcs = {_pc(n) for n in out["notes"]}
            self.assertTrue(pcs.issubset(allowed), (chord, pcs))
            ok, reason = validate_mission_motif(CHORD_TONE_MISSION, out, chord=chord, key_center=key_center)
            self.assertTrue(ok, (chord, reason))

    def test_switching_key_center_respects_new_key(self) -> None:
        chord = "Dm7"
        for key_center in ("C", "G", "D"):
            allowed = _chord_tone_pcs(chord, key_center=key_center)
            rng = random.Random(3)
            out = apply_mission_rules(
                CHORD_TONE_MISSION, _seed_motif(), chord=chord, key_center=key_center,
                level="Advanced", variant="normal", rng=rng,
            )
            pcs = {_pc(n) for n in out["notes"]}
            self.assertTrue(pcs.issubset(allowed), (key_center, pcs))


class TestPitchAndRenderFidelity(unittest.TestCase):
    """motif MIDI must equal notation-sounding MIDI through the real public
    generate_mission_example entry point, for every migrated mission."""

    def _ctx(self, *, instrument: str) -> ImprovSessionContext:
        return ImprovSessionContext(
            song_title="Test Song",
            artist="Artist",
            key_center="C",
            display_key="C",
            instrument=instrument,
            level="Advanced",
            focus="Improvisation",
            sections={"Verse": ["Am7"]},
        )

    def test_migrated_missions_stay_synchronized_piano(self) -> None:
        # RHYTHM_MISSION is checked separately below: apply_engine_rhythm's
        # motif["rhythm"] is a bar-grouped *display* string (matches the
        # already-accepted Phrase/Motif C3 engine-rhythm contract), not a
        # flat one-token-per-note string, so motif_rhythm_symbols() — not
        # motif["rhythm"].split() — is the correct per-note accessor there.
        for mission in (CHORD_TONE_MISSION, GUIDE_TONE_MISSION, RESOLVE_BEAT1_MISSION):
            for level in ("Beginner", "Intermediate", "Advanced"):
                example = generate_mission_example(
                    mission,
                    improv_ctx=self._ctx(instrument="Piano"),
                    chord="Am7",
                    section="Verse",
                    level=level,
                    instrument="Piano",
                    focus="Improvisation",
                )
                assert_mission_outputs_synchronized(example, expect_tab=False)

    def test_rhythm_mission_stays_synchronized_via_engine_rhythm_symbols(self) -> None:
        from improvisation_motif import motif_rhythm_symbols

        for level in ("Beginner", "Intermediate", "Advanced"):
            example = generate_mission_example(
                RHYTHM_MISSION,
                improv_ctx=self._ctx(instrument="Piano"),
                chord="Am7",
                section="Verse",
                level=level,
                instrument="Piano",
                focus="Improvisation",
            )
            motif = sync_motif_midi(dict(example.motif))
            notes = list(motif.get("notes") or [])
            syms = motif_rhythm_symbols(motif)
            self.assertEqual(len(syms), len(notes))
            self.assertEqual(len(motif.get("midi") or []), len(notes))
            abc = example.abc
            self.assertTrue(abc)
            self.assertIn("Mission", abc)

    def test_migrated_missions_stay_synchronized_guitar_tab(self) -> None:
        for mission in (CHORD_TONE_MISSION, GUIDE_TONE_MISSION):
            example = generate_mission_example(
                mission,
                improv_ctx=self._ctx(instrument="Guitar"),
                chord="Am7",
                section="Verse",
                level="Advanced",
                instrument="Guitar",
                focus="Improvisation",
            )
            assert_mission_outputs_synchronized(example, expect_tab=True)

    def test_bass_mission_uses_bass_clef_instrument_projection(self) -> None:
        example = generate_mission_example(
            CHORD_TONE_MISSION,
            improv_ctx=self._ctx(instrument="Bass"),
            chord="Am7",
            section="Verse",
            level="Advanced",
            instrument="Bass",
            focus="Improvisation",
        )
        self.assertEqual(example.instrument, "Bass")
        self.assertIn("clef=bass", example.abc)
        assert_mission_outputs_synchronized(example, expect_tab=False)

    def test_non_bass_mission_has_no_bass_clef(self) -> None:
        example = generate_mission_example(
            CHORD_TONE_MISSION,
            improv_ctx=self._ctx(instrument="Piano"),
            chord="Am7",
            section="Verse",
            level="Advanced",
            instrument="Piano",
            focus="Improvisation",
        )
        self.assertNotIn("clef=bass", example.abc)


class TestGenerationIsStateSafe(unittest.TestCase):
    """The musical-generation call must not mutate ownership/key state."""

    def _guarded_session(self) -> dict:
        return {
            "active_music_source": "catalog_song",
            "active_catalog_pick_key": "pk::Jazz\x1fAutumn Leaves",
            "display_key": "G",
            "concert_key": "G",
            "practice_key_by_source": {"pk::Jazz\x1fAutumn Leaves": "G"},
            "_backing_owner_envelope": {"source": "mission", "return_destination": "mission"},
            "studio_page": "creative",
        }

    def test_apply_mission_rules_does_not_touch_session(self) -> None:
        # apply_mission_rules takes no session at all — structurally side-effect
        # free with respect to ownership state; this documents that contract.
        import inspect

        params = inspect.signature(apply_mission_rules).parameters
        self.assertNotIn("session_state", params)
        self.assertNotIn("session", params)

    def test_generate_mission_example_with_session_state_preserves_ownership_fields(self) -> None:
        for mission in (CHORD_TONE_MISSION, GUIDE_TONE_MISSION, RESOLVE_BEAT1_MISSION, RHYTHM_MISSION):
            for level in ("Beginner", "Intermediate", "Advanced"):
                session = self._guarded_session()
                before = dict(session)
                generate_mission_example(
                    mission,
                    improv_ctx=self._ctx_for_session(),
                    chord="Am7",
                    section="Verse",
                    level=level,
                    instrument="Piano",
                    focus="Improvisation",
                    session_state=session,
                )
                for key in (
                    "active_music_source",
                    "active_catalog_pick_key",
                    "display_key",
                    "concert_key",
                    "practice_key_by_source",
                    "_backing_owner_envelope",
                    "studio_page",
                ):
                    self.assertEqual(session.get(key), before.get(key), (mission, level, key))

    def _ctx_for_session(self) -> ImprovSessionContext:
        return ImprovSessionContext(
            song_title="Autumn Leaves",
            artist="Artist",
            key_center="C",
            display_key="G",
            instrument="Piano",
            level="Advanced",
            focus="Improvisation",
            sections={"Verse": ["Am7"]},
        )


if __name__ == "__main__":
    unittest.main()
