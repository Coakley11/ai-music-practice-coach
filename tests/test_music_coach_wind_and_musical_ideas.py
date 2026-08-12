"""Wind-path + musical-idea (lick/pattern/phrase) regressions for Music Coach AMI."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


QUESTION = "Give me a good bass line for this song."
CHORDS_C = ["Cmaj9", "B7b9", "Em9", "Dm9", "G13"]


class WindInstrumentSubmitPathTests(unittest.TestCase):
    def _submit(self, ss: dict, *, instrument: str, key: str = "C", focus: str = "Tone", sax_type: str | None = None):
        from suite_analytical_question import (
            MUSIC_COACH_SUBMIT_DIAG_KEY,
            _AMI_COACH_SUBMIT_FEEDBACK_KEY,
            _execute_coach_question_submit,
        )
        from applied_math_return_insight import SESSION_PENDING_KEY

        ss["instrument"] = instrument
        ss["display_key"] = key
        ss["concert_key"] = key
        ss["instrument_change_source"] = "sidebar_on_change"
        if focus:
            ss["focus"] = focus
        if sax_type:
            ss["selected_transposing_instrument"] = sax_type
        st = MagicMock()
        st.session_state = ss
        st.rerun = MagicMock()
        ui = MagicMock()

        def extra():
            return {
                "coach_page": "practice",
                "display_key": key,
                "instrument": instrument,
                "level": ss.get("level", "Beginner"),
                "focus": ss.get("focus", focus),
                "chart_sections": {"Verse": list(CHORDS_C)},
                "chart_sections_key": key,
                "chart_sections_in_practice_key": True,
                "practice_focus_section": "Verse",
                "active_song": {
                    "title": "Just the Two of Us",
                    "key": "Db",
                    "pick_key": "just_the_two_of_us",
                },
                "pick_key": "just_the_two_of_us",
            }

        with patch("suite_analytical_question.submit_analytical_question") as mock_cc, patch(
            "applied_math_return_insight.store_applied_math_insight", return_value="ins"
        ), patch("applied_math_return_insight.stage_pending_insight"):
            out = _execute_coach_question_submit(
                st,
                ui,
                ss,
                question_raw=QUESTION,
                source_app="music",
                source_page="practice",
                page_suffix="practice",
                send_gen=int(ss.get("_ami_send_gen_music_practice") or 0),
                context_extra_builder=extra,
                developer_mode=True,
            )
        return out, ss.get(MUSIC_COACH_SUBMIT_DIAG_KEY) or {}, ss.get(SESSION_PENDING_KEY), mock_cc

    def test_guitar_to_flute_fresh_same_page(self) -> None:
        ss: dict = {
            "original_key": "Db",
            "level": "Beginner",
            "focus": "Walking Bass",
            "_ami_send_gen_music_practice": 0,
            "_ami_music_snapshot": {
                "practice_snapshot": {"instrument": "Guitar", "display_key": "B", "focus": "Walking Bass"}
            },
        }
        out_g, diag_g, pending_g, mock_g = self._submit(ss, instrument="Guitar", key="B", focus="Walking Bass")
        self.assertTrue(out_g.get("routed"))
        self.assertFalse(out_g.get("duplicate"))
        self.assertEqual(diag_g.get("result_path"), "routed_coach")
        self.assertIn("guitar", str(diag_g.get("selected_instrument") or "").lower())
        self.assertTrue(isinstance(pending_g, dict) and pending_g.get("notation_abc"))
        self.assertFalse(mock_g.called)

        out_f, diag_f, pending_f, mock_f = self._submit(ss, instrument="Flute", key="C", focus="Tone")
        self.assertEqual(ss.get("instrument"), "Flute")
        self.assertTrue(out_f.get("routed"))
        self.assertFalse(out_f.get("duplicate"))
        self.assertNotEqual(diag_f.get("semantic_fingerprint"), diag_g.get("semantic_fingerprint"))
        self.assertIn("instrument", diag_f.get("semantic_dimensions_changed") or [])
        self.assertEqual(diag_f.get("result_path"), "routed_coach")
        self.assertEqual(diag_f.get("solver"), "SongCoachSolver(bass_line)")
        ctx = diag_f.get("coach_context_used") or {}
        self.assertEqual(str(ctx.get("instrument") or ""), "Flute")
        self.assertTrue(isinstance(pending_f, dict))
        notation = str(pending_f.get("notation_abc") or "")
        self.assertIn("clef=treble", notation)
        self.assertIn("K:C", notation)
        self.assertFalse(mock_f.called)
        # Focus must not remain Walking Bass for Flute
        self.assertNotEqual(str(ss.get("focus") or "").lower(), "walking bass")

    def test_flute_to_saxophone_resolves_subtype(self) -> None:
        ss: dict = {
            "original_key": "Db",
            "level": "Beginner",
            "focus": "Tone",
            "_ami_send_gen_music_practice": 0,
        }
        out_f, diag_f, _, _ = self._submit(ss, instrument="Flute", key="C", focus="Tone")
        self.assertFalse(out_f.get("duplicate"))

        out_a, diag_a, pending_a, mock_a = self._submit(
            ss,
            instrument="Saxophone",
            key="C",
            focus="Tone",
            sax_type="Alto saxophone (Eb)",
        )
        self.assertEqual(ss.get("instrument"), "Saxophone")
        self.assertFalse(out_a.get("duplicate"))
        self.assertNotEqual(diag_a.get("semantic_fingerprint"), diag_f.get("semantic_fingerprint"))
        self.assertEqual(diag_a.get("result_path"), "routed_coach")
        self.assertFalse(mock_a.called)
        notation = str((pending_a or {}).get("notation_abc") or "")
        self.assertIn("clef=treble", notation)
        self.assertIn("K:A", notation)
        self.assertTrue(diag_a.get("transposing_subtype") or diag_a.get("written_key") or "A" in notation)

        out_t, diag_t, pending_t, _ = self._submit(
            ss,
            instrument="Saxophone",
            key="C",
            focus="Tone",
            sax_type="Tenor saxophone (Bb)",
        )
        self.assertFalse(out_t.get("duplicate"))
        self.assertNotEqual(diag_t.get("semantic_fingerprint"), diag_a.get("semantic_fingerprint"))
        notation_t = str((pending_t or {}).get("notation_abc") or "")
        self.assertIn("K:D", notation_t)


class DurationFingerprintSideTests(unittest.TestCase):
    def test_explicit_duration_outranks_saved_minutes(self) -> None:
        from music_coach_ami.semantic_fingerprint import music_coach_semantic_fingerprint

        ctx = {
            "instrument": "Flute",
            "level": "Beginner",
            "focus": "Tone",
            "display_key": "C",
            "practice_minutes": 30,
            "available_practice_minutes": 30,
        }
        a = music_coach_semantic_fingerprint("Give me a 10-minute practice phrase.", ctx)
        b = music_coach_semantic_fingerprint("Give me a 20-minute practice phrase.", ctx)
        self.assertNotEqual(a, b)


class MusicalIdeaVerticalSliceTests(unittest.TestCase):
    def test_harmonic_minor_pattern_bb(self) -> None:
        from music_coach_ami.pipeline import run_coach_submit
        from music_coach_ami.scale_engine import spell_scale_degrees_for_direction

        expected = spell_scale_degrees_for_direction("Bb", "harmonic minor", "ascending")
        self.assertEqual(expected[:7], ["Bb", "C", "Db", "Eb", "F", "Gb", "A"])

        session = {"instrument": "Flute", "level": "Intermediate", "focus": "Scales", "display_key": "C"}
        req, resp = run_coach_submit(
            "Give me a 4-bar descending harmonic minor pattern in Bb minor.",
            session,
            ami_ctx={"instrument": "Flute", "level": "Intermediate", "focus": "Scales", "coach_page": "practice"},
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertIn("musical_idea", resp.source_solver)
        self.assertTrue(resp.notation_abc)
        self.assertEqual(resp.diagnostics.get("bars_generated"), 4)
        self.assertIn("clef=treble", resp.notation_abc)
        self.assertIn("descending", str(resp.diagnostics.get("strategy") or resp.diagnostics.get("direction") or ""))
        self.assertEqual(resp.diagnostics.get("direction"), "descending")

    def test_lick_bars_and_tempo(self) -> None:
        from music_coach_ami.pipeline import run_coach_submit

        _, resp = run_coach_submit(
            "Give me a 2-bar intermediate lick in Bb minor at 140 BPM.",
            {"instrument": "Piano", "level": "Advanced", "focus": "Voicings"},
            ami_ctx={"instrument": "Piano", "level": "Advanced", "coach_page": "practice"},
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("bars_generated"), 2)
        self.assertEqual(resp.diagnostics.get("tempo_bpm"), 140)
        self.assertIn("Q:1/4=140", resp.notation_abc or "")

    def test_song_relative_phrase(self) -> None:
        from music_coach_ami.pipeline import run_coach_submit

        ami = {
            "instrument": "Guitar",
            "level": "Beginner",
            "focus": "Lead Guitar",
            "display_key": "C",
            "chart_sections": {"Verse": list(CHORDS_C)},
            "chart_sections_key": "C",
            "chart_sections_in_practice_key": True,
            "practice_focus_section": "Verse",
            "active_song": {"title": "Just the Two of Us", "key": "Db", "pick_key": "jttu"},
            "pick_key": "jttu",
            "coach_page": "practice",
        }
        _, resp = run_coach_submit(
            "Give me a 4-bar phrase over the current section.",
            {"instrument": "Guitar", "display_key": "C", "level": "Beginner"},
            ami_ctx=ami,
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertTrue(resp.notation_abc)
        self.assertEqual(resp.diagnostics.get("bars_generated"), 4)

    def test_cross_instrument_lick_fingerprints_differ(self) -> None:
        from music_coach_ami.semantic_fingerprint import music_coach_semantic_fingerprint

        q = "Give me a 4-bar intermediate lick in Bb minor."
        fps = {
            inst: music_coach_semantic_fingerprint(
                q, {"instrument": inst, "level": "Intermediate", "focus": "Tone", "display_key": "C"}
            )
            for inst in ("Piano", "Guitar", "Bass", "Flute", "Clarinet", "Saxophone", "Trumpet")
        }
        self.assertEqual(len(set(fps.values())), len(fps))

    def test_direction_and_difficulty_change_events(self) -> None:
        from music_coach_ami.musical_idea_engine import generate_lick, generate_scale_pattern
        from music_coach_ami.musical_idea_request import parse_musical_idea_request, resolve_musical_idea_request

        asc = resolve_musical_idea_request(
            "Give me a 4-bar ascending pattern in Bb harmonic minor.",
            default_object="pattern",
            instrument="Flute",
        )
        desc = resolve_musical_idea_request(
            "Give me a 4-bar descending pattern in Bb harmonic minor.",
            default_object="pattern",
            instrument="Flute",
        )
        self.assertEqual(asc.direction, "ascending")
        self.assertEqual(desc.direction, "descending")
        a = generate_scale_pattern(asc, notation_instrument="Flute")
        d = generate_scale_pattern(desc, notation_instrument="Flute")
        self.assertEqual(a.bars, 4)
        self.assertEqual(d.bars, 4)
        self.assertNotEqual([e.spelled for e in a.events[:6]], [e.spelled for e in d.events[:6]])

        easy = parse_musical_idea_request("Give me a very easy 4-bar lick in Bb minor.")
        hard = parse_musical_idea_request("Give me an advanced 4-bar lick in Bb minor.")
        self.assertEqual(easy.difficulty, "beginner")
        self.assertEqual(hard.difficulty, "advanced")
        e = generate_lick(
            resolve_musical_idea_request(
                "Give me a very easy 4-bar lick in Bb minor.",
                default_object="lick",
                instrument="Flute",
            ),
            notation_instrument="Flute",
        )
        h = generate_lick(
            resolve_musical_idea_request(
                "Give me an advanced 4-bar lick in Bb minor.",
                default_object="lick",
                instrument="Flute",
            ),
            notation_instrument="Flute",
        )
        self.assertNotEqual(e.strategy, h.strategy)
        self.assertNotEqual(len(e.events), 0)
        self.assertNotEqual(len(h.events), 0)


if __name__ == "__main__":
    unittest.main()
