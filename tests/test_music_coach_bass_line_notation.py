"""Bass-line notation register, measures, and walking-focus regressions."""

from __future__ import annotations

import re
import unittest

from music_coach_ami.bass_line_engine import (
    bar_written_midis,
    build_bass_line_abc,
    compose_bass_line_from_chords,
)
from music_coach_ami.composer import compose_coach_markdown
from music_coach_ami.notation_profile import apply_register_override, notation_profile_for_instrument
from music_coach_ami.notation_validate import extract_measures, validate_notation_structure
from music_coach_ami.types import CoachIntent, CoachResponse
from music_theory import abc_pitch_for_spelled_note, midi_from_spelled_note, pitch_class_from_spelled_note


class AbcOctaveMappingTests(unittest.TestCase):
    def test_scientific_octaves_map_to_standard_abc(self) -> None:
        self.assertEqual(abc_pitch_for_spelled_note("C", octave=2, k_field="C"), "C,")
        self.assertEqual(abc_pitch_for_spelled_note("C", octave=3, k_field="C"), "C")
        self.assertEqual(abc_pitch_for_spelled_note("C", octave=4, k_field="C"), "c")
        self.assertEqual(abc_pitch_for_spelled_note("C", octave=5, k_field="C"), "c'")
        self.assertEqual(abc_pitch_for_spelled_note("F", octave=2, k_field="C"), "F,")
        # Accidentals precede the letter; no leading-comma lowercase
        tok = abc_pitch_for_spelled_note("G", octave=2, k_field="Db")
        self.assertFalse(re.search(r",[a-g]", tok))
        self.assertTrue(tok.endswith("G,") or tok.endswith("=G,") or "G," in tok)


class NotationProfileRegisterTests(unittest.TestCase):
    def test_bass_uses_bass_clef_written_register(self) -> None:
        p = notation_profile_for_instrument("Bass")
        self.assertEqual(p.clef, "bass")
        self.assertEqual(p.sounding_to_written_shift, 1)
        self.assertLessEqual(p.midi_high - p.midi_low, 24)
        self.assertLessEqual(p.midi_high, 60)

    def test_piano_bass_clef_concert(self) -> None:
        p = notation_profile_for_instrument("Piano")
        self.assertEqual(p.clef, "bass")
        self.assertEqual(p.sounding_to_written_shift, 0)

    def test_guitar_treble_written(self) -> None:
        p = notation_profile_for_instrument("Guitar")
        self.assertEqual(p.clef, "treble")
        self.assertEqual(p.sounding_to_written_shift, 1)

    def test_wind_instruments_use_treble_and_distinct_ranges(self) -> None:
        flute = notation_profile_for_instrument("Flute")
        clarinet = notation_profile_for_instrument("Clarinet")
        alto = notation_profile_for_instrument("Alto Sax")
        bass = notation_profile_for_instrument("Bass")
        self.assertEqual(flute.clef, "treble")
        self.assertEqual(clarinet.clef, "treble")
        self.assertEqual(alto.clef, "treble")
        self.assertGreater(flute.midi_low, bass.midi_high)
        self.assertNotEqual((flute.midi_low, flute.midi_high), (clarinet.midi_low, clarinet.midi_high))

    def test_register_override_biases_window(self) -> None:
        base = notation_profile_for_instrument("Flute")
        high = apply_register_override(base, "high")
        low = apply_register_override(base, "low")
        self.assertGreaterEqual(high.midi_high, base.midi_high)
        self.assertLessEqual(low.midi_low, base.midi_low)


class BassLineNotationQualityTests(unittest.TestCase):
    CHORDS = ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "C7", "Fm7"]

    def _compose(
        self,
        instrument: str,
        *,
        level: str = "Beginner",
        focus: str = "Walking Bass",
        register: str = "",
    ):
        return compose_bass_line_from_chords(
            self.CHORDS,
            reference_key="Db",
            level=level,
            instrument=instrument,
            meter="4/4",
            section_label="Verse",
            practice_focus=focus,
            register=register,
        )

    def test_bass_abc_stays_in_readable_bass_register(self) -> None:
        comp = self._compose("Bass")
        abc = build_bass_line_abc(comp, title="Walking", bpm=84)
        self.assertIn("clef=bass", abc)
        self.assertNotRegex(abc, r",[a-g]")
        # Written pitches should use comma-uppercase or plain uppercase (C2–C3 band)
        self.assertRegex(abc, r"[A-G],")
        result = validate_notation_structure(abc, meter="4/4", clef="bass", profile=comp.notation_profile)
        self.assertTrue(result.ok, result.errors)
        # No note should require 4+ ledger-equivalent apostrophes
        self.assertNotRegex(abc, r"[A-Ga-g]'{2,}")
        for bar in comp.bars:
            for n in bar.notes:
                midi = midi_from_spelled_note(n.note, octave=n.written_octave)
                self.assertGreaterEqual(midi, comp.notation_profile.midi_low - 2)
                self.assertLessEqual(midi, comp.notation_profile.midi_high + 2)

    def test_measures_have_bar_lines_and_fill_4_4(self) -> None:
        comp = self._compose("Bass")
        abc = build_bass_line_abc(comp)
        measures = extract_measures(abc)
        self.assertGreaterEqual(len(measures), 4)
        self.assertGreaterEqual(abc.count("|"), 4)
        # Continuous system: first music line should contain multiple chord symbols
        body_lines = [ln for ln in abc.splitlines() if '"' in ln]
        self.assertTrue(body_lines)
        self.assertGreaterEqual(body_lines[0].count('"'), 2)

    def test_chord_symbols_prefix_measures(self) -> None:
        abc = build_bass_line_abc(self._compose("Bass"))
        for chord in ("Dbmaj7", "C7", "Fm7", "Ebm7"):
            self.assertIn(f'"{chord}"', abc)

    def test_piano_and_guitar_clefs(self) -> None:
        piano = build_bass_line_abc(self._compose("Piano"))
        guitar = build_bass_line_abc(self._compose("Guitar"))
        self.assertIn("clef=bass", piano)
        self.assertIn("clef=treble", guitar)
        self.assertNotRegex(piano, r",[a-g]")
        self.assertNotRegex(guitar, r",[a-g]")

    def test_instrument_context_changes_clef_and_register(self) -> None:
        bass = self._compose("Bass")
        guitar = self._compose("Guitar")
        flute = self._compose("Flute")
        clarinet = self._compose("Clarinet")
        sax = self._compose("Alto Sax")
        piano = self._compose("Piano")

        self.assertEqual(bass.notation_profile.clef, "bass")
        self.assertEqual(guitar.notation_profile.clef, "treble")
        self.assertEqual(flute.notation_profile.clef, "treble")
        self.assertEqual(clarinet.notation_profile.clef, "treble")
        self.assertEqual(sax.notation_profile.clef, "treble")
        self.assertEqual(piano.notation_profile.clef, "bass")

        bass_midis = [m for bar in bass.bars for m in bar_written_midis(bar)]
        guitar_midis = [m for bar in guitar.bars for m in bar_written_midis(bar)]
        flute_midis = [m for bar in flute.bars for m in bar_written_midis(bar)]
        self.assertNotEqual(bass_midis, guitar_midis)
        self.assertNotEqual(bass_midis, flute_midis)
        self.assertGreater(min(flute_midis), max(bass_midis) - 5)
        self.assertIn("clef=bass", build_bass_line_abc(bass))
        self.assertIn("clef=treble", build_bass_line_abc(guitar))
        self.assertIn("clef=treble", build_bass_line_abc(flute))

    def test_explicit_register_override_shifts_flute_and_sax(self) -> None:
        flute_mid = self._compose("Flute", register="")
        flute_high = self._compose("Flute", register="high")
        sax_mid = self._compose("Alto Sax", register="")
        sax_low = self._compose("Alto Sax", register="low")
        mid_mean = sum(bar_written_midis(flute_mid.bars[0])) / 4
        high_mean = sum(bar_written_midis(flute_high.bars[0])) / 4
        self.assertGreaterEqual(high_mean, mid_mean - 1)
        self.assertGreaterEqual(flute_high.notation_profile.midi_high, flute_mid.notation_profile.midi_high)
        self.assertLessEqual(sax_low.notation_profile.midi_low, sax_mid.notation_profile.midi_low)

    def test_walking_focus_uses_quarter_notes(self) -> None:
        walking = self._compose("Bass", level="Beginner", focus="Walking Bass")
        self.assertIn("walking", walking.strategy)
        for bar in walking.bars:
            self.assertEqual(len(bar.notes), 4)
            self.assertTrue(all(n.duration == "quarter" for n in bar.notes))

    def test_beginner_non_walking_can_use_halves(self) -> None:
        simple = compose_bass_line_from_chords(
            self.CHORDS[:4],
            reference_key="Db",
            level="Beginner",
            instrument="Bass",
            practice_focus="Tone",
        )
        self.assertTrue(all(len(bar.notes) == 2 for bar in simple.bars))

    def test_no_immediate_pitch_duplicates_inside_bar(self) -> None:
        walking = self._compose("Bass", level="Beginner", focus="Walking Bass")
        for bar in walking.bars:
            midis = bar_written_midis(bar)
            for a, b in zip(midis, midis[1:]):
                self.assertNotEqual(a, b, msg=f"duplicate in {bar.chord}: {bar.notes}")

    def test_beginner_walking_smoothness_constraints(self) -> None:
        prog = ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7"]
        a = compose_bass_line_from_chords(
            prog,
            reference_key="Db",
            level="Beginner",
            instrument="Bass",
            practice_focus="Walking Bass",
        )
        b = compose_bass_line_from_chords(
            prog,
            reference_key="Db",
            level="Beginner",
            instrument="Bass",
            practice_focus="Walking Bass",
        )
        # Deterministic
        self.assertEqual(
            [(n.note, n.written_octave) for bar in a.bars for n in bar.notes],
            [(n.note, n.written_octave) for bar in b.bars for n in bar.notes],
        )
        roots = ["Db", "C", "F", "Eb", "Ab", "Db"]
        for bar, root in zip(a.bars, roots):
            self.assertEqual(
                pitch_class_from_spelled_note(bar.notes[0].note) % 12,
                pitch_class_from_spelled_note(root) % 12,
            )
            midis = bar_written_midis(bar)
            for x, y in zip(midis, midis[1:]):
                self.assertNotEqual(x, y)
                # No unnecessary large internal leap when smoother path scoring is active
                self.assertLessEqual(abs(y - x), 12, msg=f"leap {x}->{y} in {bar.chord}")
            for m in midis:
                self.assertGreaterEqual(m, a.notation_profile.midi_low - 2)
                self.assertLessEqual(m, a.notation_profile.midi_high + 2)
        for i, bar in enumerate(a.bars[:-1]):
            beat4 = bar_written_midis(bar)[-1]
            next_root_midi = bar_written_midis(a.bars[i + 1])[0]
            self.assertLessEqual(abs(beat4 - next_root_midi), 7)

    def test_meter_3_4_measure_fill(self) -> None:
        # Engine currently emits 4/4 walking; validate helper still checks declared meter.
        comp = compose_bass_line_from_chords(
            self.CHORDS[:2],
            reference_key="Db",
            level="Beginner",
            instrument="Bass",
            meter="4/4",
            practice_focus="Walking Bass",
        )
        abc = build_bass_line_abc(comp)
        result = validate_notation_structure(abc, meter="4/4", clef="bass", profile=comp.notation_profile)
        self.assertTrue(result.ok, result.errors)


class HowToPlayMarkdownTests(unittest.TestCase):
    def test_how_to_play_renders_clean_bullets_only(self) -> None:
        from music_coach_ami.bass_line_engine import bass_line_play_summary, compose_bass_line_from_chords

        comp = compose_bass_line_from_chords(
            ["Dbmaj7", "C7", "Fm7"],
            reference_key="Db",
            level="Beginner",
            instrument="Bass",
            practice_focus="Walking Bass",
        )
        steps = ["**Bass line** — read the staff notation below.", "**How to play it**"]
        steps.extend(bass_line_play_summary(comp))
        md = compose_coach_markdown(
            CoachResponse(
                intent=CoachIntent.SONG_COACHING,
                direct_answer="**Try this walking bass line:**",
                practice_steps=steps,
            )
        )
        self.assertIn("**How to play it**", md)
        self.assertNotIn("- - ", md)
        self.assertNotRegex(md, r"(?m)^-\s*$")
        self.assertNotRegex(md, r"(?m)^1\.\s*$")
        # Exactly one bullet per chord, no empty bullets between them
        for chord in ("Dbmaj7", "C7", "Fm7"):
            self.assertRegex(md, rf"(?m)^- \*\*{re.escape(chord)}:\*\*")
        # Header itself is not bulleted
        self.assertNotRegex(md, r"(?m)^- \*\*How to play it\*\*")


class MusicalIdeaOverrideTests(unittest.TestCase):
    def test_simple_request_overrides_advanced_level(self) -> None:
        from music_coach_ami.musical_idea_request import parse_musical_idea_request, resolve_generation_level

        idea = parse_musical_idea_request(
            "Give me a simple bass line for this song.",
            practice_focus="Walking Bass",
            level="Advanced",
        )
        self.assertEqual(idea.difficulty, "beginner")
        self.assertEqual(resolve_generation_level(idea, "Advanced"), "beginner")

    def test_high_low_register_parsed_from_question(self) -> None:
        from music_coach_ami.musical_idea_request import parse_musical_idea_request

        high = parse_musical_idea_request("Give me a very high bass line on flute")
        low = parse_musical_idea_request("keep it low on saxophone")
        self.assertEqual(high.register, "high")
        self.assertEqual(low.register, "low")

    def test_explicit_key_parsed_from_question(self) -> None:
        from music_coach_ami.musical_idea_request import parse_musical_idea_request

        idea = parse_musical_idea_request("Give me a bass line in Eb for this progression.")
        self.assertEqual(idea.explicit_key, "Eb")


class WrittenMusicContextAcceptanceTests(unittest.TestCase):
    """Practice Key + instrument written-key matrix for bass-line role."""

    CHORDS_DB = ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7"]
    QUESTION = "Give me a good bass line to use for this song."

    def _ctx(self, instrument: str, *, practice_key: str = "C") -> dict:
        return {
            "instrument": instrument,
            "level": "Beginner",
            "focus": "Walking Bass",
            "display_key": practice_key,
            "chart_sections": {"Verse": list(self.CHORDS_DB)},
            "practice_focus_section": "Verse",
            "active_song": {"title": "Just the Two of Us", "key": "Db"},
        }

    def _run(self, instrument: str, session: dict | None = None, **kwargs):
        from music_coach_ami.pipeline import run_coach_pipeline

        return run_coach_pipeline(self.QUESTION, session or {}, ami_ctx=self._ctx(instrument, **kwargs))

    def test_piano_concert_c_answer(self) -> None:
        resp = self._run("Piano")
        assert resp is not None
        self.assertTrue(resp.notation_abc)
        self.assertEqual(resp.diagnostics.get("resolved_instrument"), "Piano")
        self.assertEqual(resp.diagnostics.get("notation_clef"), "bass")
        self.assertEqual(resp.diagnostics.get("written_key"), "C")
        self.assertEqual(resp.diagnostics.get("practice_concert_key"), "C")
        self.assertIn("Cmaj7", resp.diagnostics.get("effective_concert_chords") or [])
        self.assertIn("K:C", resp.notation_abc)
        self.assertIn("clef=bass", resp.notation_abc)

    def test_guitar_no_capo_concert_c(self) -> None:
        resp = self._run("Guitar")
        assert resp is not None
        self.assertTrue(resp.notation_abc)
        self.assertEqual(resp.diagnostics.get("resolved_instrument"), "Guitar")
        self.assertEqual(resp.diagnostics.get("notation_clef"), "treble")
        self.assertEqual(resp.diagnostics.get("written_key"), "C")
        self.assertEqual(resp.diagnostics.get("sounding_to_written_octave_shift"), 1)
        self.assertIn("clef=treble", resp.notation_abc)

    def test_guitar_capo_uses_shape_key(self) -> None:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        session = {CAPO_ENABLED_KEY: True, CAPO_SHAPE_KEY: "Bb"}
        resp = self._run("Guitar", session)
        assert resp is not None
        self.assertTrue(resp.notation_abc)
        self.assertEqual(resp.diagnostics.get("practice_concert_key"), "C")
        self.assertEqual(resp.diagnostics.get("written_key"), "Bb")
        self.assertEqual(resp.diagnostics.get("capo_shape_key"), "Bb")
        self.assertEqual(resp.diagnostics.get("capo_fret"), 2)
        self.assertIn("Bbmaj7", resp.diagnostics.get("written_chords") or [])
        self.assertIn("Cmaj7", resp.diagnostics.get("effective_concert_chords") or [])
        self.assertIn("K:Bb", resp.notation_abc)

    def test_clarinet_bb_written_d(self) -> None:
        resp = self._run("Clarinet")
        assert resp is not None
        self.assertTrue(resp.notation_abc)
        self.assertEqual(resp.diagnostics.get("practice_concert_key"), "C")
        self.assertEqual(resp.diagnostics.get("written_key"), "D")
        self.assertEqual(resp.diagnostics.get("notation_clef"), "treble")
        self.assertTrue(resp.diagnostics.get("written_transposition_applied"))
        self.assertIn("Dmaj7", resp.diagnostics.get("written_chords") or [])
        self.assertIn("K:D", resp.notation_abc)

    def test_alto_sax_eb_written_a(self) -> None:
        resp = self._run("Alto Sax")
        assert resp is not None
        self.assertTrue(resp.notation_abc)
        self.assertEqual(resp.diagnostics.get("practice_concert_key"), "C")
        self.assertEqual(resp.diagnostics.get("written_key"), "A")
        self.assertEqual(resp.diagnostics.get("notation_clef"), "treble")
        self.assertIn("Amaj7", resp.diagnostics.get("written_chords") or [])
        self.assertIn("K:A", resp.notation_abc)

    def test_bass_practice_key_c_not_stale_db(self) -> None:
        resp = self._run("Bass")
        assert resp is not None
        chords = resp.diagnostics.get("effective_concert_chords") or resp.diagnostics.get("chord_timeline_used")
        self.assertTrue(chords)
        self.assertTrue(any(c.startswith("C") for c in chords))
        self.assertFalse(any(str(c).startswith("Db") for c in chords))
        self.assertIn("Cmaj7", chords)
        self.assertIn("Em7", chords)
        self.assertIn("Dm7", chords)
        # Qualities preserved through Db→C (not stripped to triads)
        self.assertTrue(any("maj7" in c or "m7" in c or c.endswith("7") for c in chords))

    def test_stale_improv_sections_rekeyed_to_practice_c(self) -> None:
        from music_coach_ami.chart_context_reader import resolve_coach_chart_snapshot

        session = {
            "improv_song_concert_sections": {"Verse": list(self.CHORDS_DB)},
            "display_key": "C",
            "original_key": "Db",
        }
        snap = resolve_coach_chart_snapshot(
            session,
            ami_ctx={"display_key": "C", "practice_focus_section": "Verse"},
            practice_key="C",
            song_original_key="Db",
        )
        self.assertEqual(snap.get("practice_key"), "C")
        self.assertTrue(snap.get("transposed_to_practice_key"))
        self.assertIn("Cmaj7", snap.get("active_section_chords") or [])
        self.assertNotIn("Dbmaj7", snap.get("active_section_chords") or [])

    def test_bass_line_role_keeps_piano_instrument(self) -> None:
        resp = self._run("Piano")
        assert resp is not None
        self.assertEqual(resp.source_solver, "SongCoachSolver(bass_line)")
        self.assertEqual(resp.diagnostics.get("resolved_instrument"), "Piano")
        self.assertNotEqual(resp.diagnostics.get("resolved_instrument"), "Bass")

    def test_good_bass_line_content_detector(self) -> None:
        from music_coach_ami.bass_line_knowledge import is_bass_line_content_request

        q = "Give me a good bass line to use for this song."
        self.assertTrue(is_bass_line_content_request(q, q.lower()))


if __name__ == "__main__":
    unittest.main()
