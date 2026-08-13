"""Live acceptance fixes for Piano-first section improvisation (written spelling + object types)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from improvisation_motif import chord_tone_names
from music_coach_ami.musical_idea_engine import play_summary
from music_coach_ami.musical_idea_knowledge import format_section_display_label
from music_coach_ami.pipeline import run_coach_submit
from music_theory import spell_chord_tones, transpose_chord


PART_A_CONCERT_C = ["Am7", "B7", "Emaj7", "Am7", "Am7", "B7", "Emaj7", "Am7"]
VERSE_EB = ["Fm7", "B7b9", "Ebm7", "Ab7", "Dbmaj7", "B7b9", "Ebmaj7", "Bb7"]


def _alto_ctx(sections: dict, *, key: str = "C", level: str = "Beginner") -> dict:
    return {
        "instrument": "Alto Sax",
        "level": level,
        "focus": "Improvisation",
        "display_key": key,
        "practice_key": key,
        "coach_page": "practice",
        "chart_sections": sections,
        "chart_sections_in_practice_key": True,
        "practice_focus_section": next(iter(sections), ""),
        "selected_transposing_instrument": "Alto saxophone (Eb)",
        "active_song": {"title": "Acceptance Tune", "key": key},
    }


def _alto_session(*, key: str = "C") -> dict:
    return {
        "instrument": "Alto Sax",
        "display_key": key,
        "level": "Beginner",
        "selected_transposing_instrument": "Alto saxophone (Eb)",
        "instrument_change_source": "sidebar",
    }


class WrittenDomainSpellingTests(unittest.TestCase):
    def test_alto_written_a_spells_fsharp_not_gb(self) -> None:
        self.assertEqual(transpose_chord("Am7", 9, reference_key="A"), "F#m7")
        self.assertEqual(transpose_chord("B7", 9, reference_key="A"), "G#7")
        self.assertEqual(transpose_chord("Emaj7", 9, reference_key="A"), "C#maj7")
        self.assertNotEqual(transpose_chord("Am7", 9, reference_key="C"), "F#m7")

    def test_alto_melody_over_part_a_written_chords_match_notes(self) -> None:
        _, resp = run_coach_submit(
            "Give me a simple melody to play over part A.",
            _alto_session(key="C"),
            ami_ctx=_alto_ctx({"A": PART_A_CONCERT_C, "B": ["Em7", "A7"]}, key="C"),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        written = list(resp.diagnostics.get("harmonic_timeline_written") or [])
        self.assertTrue(written)
        self.assertIn("F#m7", written)
        self.assertNotIn("Gbm7", written)
        self.assertTrue(any(c.startswith("G#") for c in written))
        self.assertFalse(any(c.startswith("Ab") for c in written))
        self.assertTrue(any(c.startswith("C#") for c in written))
        self.assertFalse(any(c.startswith("Db") for c in written))
        abc = resp.notation_abc or ""
        self.assertIn('"F#m7"', abc)
        self.assertNotIn('"Gbm7"', abc)
        self.assertNotIn('"Ab7"', abc)
        self.assertNotIn('"Dbmaj7"', abc)
        prose = "\n".join(resp.practice_steps or [])
        fsharp_tones = set(spell_chord_tones("F#m7")[:3])
        self.assertTrue(fsharp_tones.intersection(prose.split()) or "F#" in prose)

    def test_b7b9_chord_local_spelling_not_key_flats(self) -> None:
        tones = chord_tone_names("B7b9", reference_key="Eb")
        joined = " ".join(tones)
        self.assertIn("D#", joined)
        self.assertIn("F#", joined)
        self.assertNotIn("Eb", joined)
        self.assertNotIn("Gb", joined)

        _, resp = run_coach_submit(
            "Give me an intermediate jazz improvisation over the verse.",
            {"instrument": "Piano", "display_key": "Eb", "level": "Intermediate", "instrument_change_source": "sidebar"},
            ami_ctx={
                "instrument": "Piano",
                "level": "Intermediate",
                "display_key": "Eb",
                "practice_key": "Eb",
                "coach_page": "practice",
                "chart_sections": {"Verse": VERSE_EB},
                "chart_sections_in_practice_key": True,
                "practice_focus_section": "Verse",
                "active_song": {"title": "Acceptance Tune", "key": "Eb"},
            },
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        b7_notes = []
        for step in resp.practice_steps or []:
            if "B7" in step:
                b7_notes.append(step)
        b7_blob = " ".join(b7_notes)
        if b7_blob:
            self.assertIn("D#", b7_blob)
            self.assertIn("F#", b7_blob)
            self.assertNotIn(" Gb", f" {b7_blob}")


class ObjectTypeAndSectionLabelTests(unittest.TestCase):
    def test_format_part_a_not_bare_letter(self) -> None:
        self.assertEqual(format_section_display_label("A"), "Part A")
        self.assertEqual(format_section_display_label("b"), "Part B")
        self.assertEqual(format_section_display_label("Part A"), "Part A")
        self.assertEqual(format_section_display_label("Verse"), "Verse")

    def test_requested_melody_stays_melody(self) -> None:
        _, resp = run_coach_submit(
            "Give me a simple melody to play over part A.",
            {"instrument": "Piano", "display_key": "C", "level": "Beginner", "instrument_change_source": "sidebar"},
            ami_ctx={
                "instrument": "Piano",
                "level": "Beginner",
                "display_key": "C",
                "practice_key": "C",
                "coach_page": "practice",
                "chart_sections": {"A": PART_A_CONCERT_C, "B": ["G7", "C"]},
                "chart_sections_in_practice_key": True,
                "practice_focus_section": "A",
                "active_song": {"title": "Acceptance Tune", "key": "C"},
            },
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("requested_object"), "melody")
        self.assertEqual(resp.diagnostics.get("resolved_object"), "melody")
        self.assertIn("melody", (resp.direct_answer or "").lower())
        self.assertNotIn("phrase", (resp.direct_answer or "").lower())
        self.assertIn("Melody", "\n".join(resp.practice_steps or []))
        self.assertIn("Part A", resp.direct_answer)
        self.assertIn("Part A", resp.notation_abc or "")
        self.assertNotRegex(resp.notation_abc or "", r"Over A(?:\s|$)")

    def test_requested_improvisation_stays_improvisation_on_piano(self) -> None:
        _, resp = run_coach_submit(
            "Give me an improvisation over part A.",
            {"instrument": "Piano", "display_key": "C", "level": "Beginner", "instrument_change_source": "sidebar"},
            ami_ctx={
                "instrument": "Piano",
                "level": "Beginner",
                "display_key": "C",
                "practice_key": "C",
                "coach_page": "practice",
                "chart_sections": {"A": PART_A_CONCERT_C},
                "chart_sections_in_practice_key": True,
                "practice_focus_section": "A",
                "active_song": {"title": "Acceptance Tune", "key": "C"},
            },
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("requested_object"), "improvisation")
        self.assertEqual(resp.diagnostics.get("resolved_object"), "improvisation")
        self.assertIn("improvisation", (resp.direct_answer or "").lower())
        self.assertNotIn("lick", (resp.direct_answer or "").lower())
        self.assertIn("Part A", resp.notation_abc or "")

    def test_alto_improvisation_does_not_silently_become_lick(self) -> None:
        _, resp = run_coach_submit(
            "Give me an intermediate jazz improvisation over the verse.",
            _alto_session(key="Eb"),
            ami_ctx=_alto_ctx({"Verse": VERSE_EB, "Chorus": ["Ebmaj7"]}, key="Eb", level="Intermediate"),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("requested_object"), "improvisation")
        self.assertEqual(resp.diagnostics.get("resolved_object"), "improvisation")
        self.assertIn("improvisation", (resp.direct_answer or "").lower())
        self.assertNotIn("lick", (resp.direct_answer or "").lower())

    def test_alto_melody_does_not_silently_become_phrase(self) -> None:
        _, resp = run_coach_submit(
            "Give me a simple melody to play over part A.",
            _alto_session(key="C"),
            ami_ctx=_alto_ctx({"A": PART_A_CONCERT_C}, key="C"),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("requested_object"), "melody")
        self.assertEqual(resp.diagnostics.get("resolved_object"), "melody")
        self.assertIn("melody", (resp.direct_answer or "").lower())
        self.assertNotIn("phrase", (resp.direct_answer or "").lower())


class Dim7AndTwoHandAndDiagnosticsTests(unittest.TestCase):
    def test_ebdim7_piano_lh_does_not_use_bb_as_dim_fifth(self) -> None:
        _, resp = run_coach_submit(
            "Give me a left-hand accompaniment for part A.",
            {"instrument": "Piano", "display_key": "Eb", "level": "Intermediate", "instrument_change_source": "sidebar"},
            ami_ctx={
                "instrument": "Piano",
                "level": "Intermediate",
                "display_key": "Eb",
                "practice_key": "Eb",
                "coach_page": "practice",
                "chart_sections": {
                    "A": ["Ebmaj7", "Cm7", "Fm7", "Bb7", "Ebmaj7", "Ebdim7", "Fm7", "Bb7"],
                },
                "chart_sections_in_practice_key": True,
                "practice_focus_section": "A",
                "active_song": {"title": "Acceptance Tune", "key": "Eb"},
            },
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        tones = chord_tone_names("Ebdim7")
        self.assertNotIn("Bb", tones)
        prose = "\n".join(resp.practice_steps or [])
        for line in prose.splitlines():
            if "Ebdim7" not in line:
                continue
            self.assertNotRegex(line, r"\bBb\b")

    def test_two_hand_prose_separates_rh_lh_from_event_roles(self) -> None:
        from music_coach_ami.musical_idea_engine import generate_piano_section_improvisation
        from music_coach_ami.musical_idea_request import resolve_musical_idea_request

        q = "Give me a two-hand piano improvisation over the verse."
        idea = resolve_musical_idea_request(
            q, default_object="improvisation", instrument="Piano", level="Intermediate"
        )
        comp = generate_piano_section_improvisation(
            idea,
            ["Cmaj9", "Am7", "Dm7", "G7"],
            reference_key="C",
            piano_role="both_hands",
            question=q,
        )
        summary = play_summary(comp)
        blob = "\n".join(summary)
        self.assertIn("RH:", blob)
        self.assertIn("LH:", blob)
        self.assertTrue(any(e.role == "rh" for e in comp.events))
        self.assertTrue(any(e.role == "lh" for e in comp.events))
        rh_notes = [e.spelled for e in comp.events if e.role == "rh" and e.bar_index == 0][:8]
        lh_notes = [e.spelled for e in comp.events if e.role == "lh" and e.bar_index == 0][:8]
        self.assertIn(" ".join(rh_notes), blob)
        self.assertIn(" ".join(lh_notes), blob)

    def test_normal_user_response_hides_solver_name(self) -> None:
        _, resp = run_coach_submit(
            "Give me a simple melody to play over part A.",
            {"instrument": "Piano", "display_key": "C", "level": "Beginner", "instrument_change_source": "sidebar"},
            ami_ctx={
                "instrument": "Piano",
                "level": "Beginner",
                "display_key": "C",
                "practice_key": "C",
                "coach_page": "practice",
                "chart_sections": {"A": PART_A_CONCERT_C},
                "chart_sections_in_practice_key": True,
                "practice_focus_section": "A",
                "active_song": {"title": "Acceptance Tune", "key": "C"},
            },
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        md = resp.composed_markdown()
        self.assertNotIn("ScalePracticeSolver", md)
        self.assertNotIn("musical_idea", md)
        self.assertNotIn("Router confidence", md)

        from applied_math_return_insight import render_suite_applied_math_insight_for_page
        from music_coach_ami.submit_diagnostics import build_music_coach_submit_diagnostics
        from music_coach_ami.submit_integration import stage_routed_music_coach_insight

        st = MagicMock()
        ss: dict = {"studio_page": "practice", "_ami_submit_render_insight_this_run": True}
        st.session_state = ss
        req, _ = run_coach_submit(
            "Give me a simple melody to play over part A.",
            {"instrument": "Piano", "display_key": "C", "level": "Beginner"},
            ami_ctx={
                "instrument": "Piano",
                "level": "Beginner",
                "display_key": "C",
                "coach_page": "practice",
                "chart_sections": {"A": PART_A_CONCERT_C},
                "practice_focus_section": "A",
            },
        )
        diag = build_music_coach_submit_diagnostics(req, resp, result_path="routed_coach")
        markdown_calls: list[str] = []
        captions: list[str] = []

        def _markdown(text: str, *args, **kwargs) -> None:
            markdown_calls.append(str(text))

        st.markdown = _markdown
        st.caption = lambda text, *a, **k: captions.append(str(text))
        st.container = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=st), __exit__=MagicMock()))
        st.columns = MagicMock(return_value=(st, st))
        st.button = MagicMock(return_value=False)
        st.code = MagicMock()
        st.expander = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=st), __exit__=MagicMock()))
        st.json = MagicMock()
        with patch(
            "applied_math_return_insight.store_applied_math_insight",
            return_value="ins-acc",
        ), patch("applied_math_return_insight.stage_pending_insight"):
            stage_routed_music_coach_insight(
                st,
                ss,
                question="Give me a simple melody to play over part A.",
                source_page="practice",
                coach_req=req,
                coach_resp=resp,
                diagnostics=diag,
                question_id="q-acc",
            )
        with patch("streamlit.components.v1.html"), patch(
            "music_persistence_trace.music_developer_mode", return_value=False
        ):
            render_suite_applied_math_insight_for_page(st, source_app="music", source_page="practice")
        joined = "\n".join(markdown_calls + captions)
        self.assertNotIn("ScalePracticeSolver", joined)
        self.assertNotIn("Router confidence", joined)
        self.assertNotIn("Assumptions:", joined)


if __name__ == "__main__":
    unittest.main()
