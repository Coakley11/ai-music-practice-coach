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

    def test_sax_subtype_matrix_fingerprints(self) -> None:
        ss: dict = {"original_key": "Ab", "level": "Beginner", "focus": "Tone", "_ami_send_gen_music_practice": 0}
        fps = []
        keys = []
        for sax in (
            "Alto saxophone (Eb)",
            "Tenor saxophone (Bb)",
            "Soprano saxophone (Bb)",
            "Baritone saxophone (Eb)",
        ):
            _, diag, pending, _ = self._submit(ss, instrument="Saxophone", key="Ab", focus="Tone", sax_type=sax)
            self.assertFalse(diag.get("duplicate"))
            fps.append(diag.get("semantic_fingerprint"))
            keys.append(str((pending or {}).get("notation_abc") or ""))
        self.assertEqual(len(set(fps)), 4)
        self.assertIn("K:F", keys[0])  # Alto Ab → F
        self.assertIn("K:Bb", keys[1])  # Tenor Ab → Bb
        self.assertIn("K:Bb", keys[2])  # Soprano Ab → Bb


class SaxWrittenKeyControlPathTests(unittest.TestCase):
    def test_rehydrate_does_not_clobber_live_tenor_or_checkbox(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY, flush_active_song_edits, rehydrate_transposing_sidebar_from_canonical
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )

        session = {
            "instrument": "Saxophone",
            "display_key": "Ab",
            "concert_key": "Ab",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            CHART_IN_INSTRUMENT_KEY_KEY: False,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Alto Saxophone",
            ACTIVE_SONG_STATE_KEY: {
                "pick_key": "all_the_things",
                "instrument": "Saxophone",
                "display_key": "Ab",
                SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
                CHART_IN_INSTRUMENT_KEY_KEY: False,
                WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            },
        }
        # Normalize legacy display-name anchor without clearing checkbox.
        sync_written_key_instrument_anchor(session, "Saxophone")
        self.assertEqual(session.get(CHART_IN_INSTRUMENT_KEY_KEY), False)
        self.assertEqual(session.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY), "Saxophone")

        # User picks Tenor + written charts — live widget values must survive rehydrate.
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Tenor saxophone (Bb)"
        session[CHART_IN_INSTRUMENT_KEY_KEY] = True
        flush_active_song_edits(session, reason="song_edit")
        meta = session.get(ACTIVE_SONG_STATE_KEY) or {}
        self.assertEqual(meta.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY), "Tenor saxophone (Bb)")
        self.assertTrue(meta.get(CHART_IN_INSTRUMENT_KEY_KEY))

        # Simulate next rerun: stale code used to overwrite Tenor→Alto here.
        rehydrate_transposing_sidebar_from_canonical(session)
        self.assertEqual(session.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY), "Tenor saxophone (Bb)")
        self.assertTrue(session.get(CHART_IN_INSTRUMENT_KEY_KEY))

        # Seed path still works when keys are missing.
        bare = {
            ACTIVE_SONG_STATE_KEY: {
                SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Soprano saxophone (Bb)",
                CHART_IN_INSTRUMENT_KEY_KEY: True,
            }
        }
        rehydrate_transposing_sidebar_from_canonical(bare)
        self.assertEqual(bare.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY), "Soprano saxophone (Bb)")
        self.assertTrue(bare.get(CHART_IN_INSTRUMENT_KEY_KEY))


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
    def test_d_harmonic_minor_eight_bar_ascending(self) -> None:
        from music_coach_ami.musical_idea_engine import (
            authoritative_scale_degrees,
            cell_anchor_midis,
            composition_to_abc,
            generate_scale_pattern,
        )
        from music_coach_ami.musical_idea_request import resolve_musical_idea_request

        scale = authoritative_scale_degrees("D", "harmonic minor")
        self.assertEqual(scale, ["D", "E", "F", "G", "A", "Bb", "C#"])

        idea = resolve_musical_idea_request(
            "Give me an 8-bar ascending eighth-note pattern in D harmonic minor at 90 BPM.",
            default_object="pattern",
            instrument="Flute",
        )
        self.assertEqual(idea.object_type, "pattern")
        self.assertEqual(idea.bars, 8)
        self.assertEqual(idea.tempo_bpm, 90)
        self.assertEqual(idea.rhythm, "eighth")
        self.assertEqual(idea.explicit_key, "D")
        self.assertEqual(idea.tonality, "harmonic minor")
        self.assertEqual(idea.direction, "ascending")

        comp = generate_scale_pattern(idea, notation_instrument="Flute")
        self.assertEqual(comp.bars, 8)
        self.assertEqual(list(comp.scale_spelling), scale)
        self.assertNotIn("A#", comp.scale_spelling)
        self.assertIn("C#", [e.spelled for e in comp.events])
        self.assertTrue(comp.validation_ok, comp.validation_errors)

        anchors = cell_anchor_midis(comp)
        self.assertGreaterEqual(len(anchors), 4)
        wrap = next((i for i in range(1, len(anchors)) if anchors[i] + 1 < anchors[i - 1]), None)
        end = wrap if wrap is not None else len(anchors)
        for i in range(1, end):
            self.assertGreaterEqual(anchors[i], anchors[i - 1] - 1)

        # No modulo replay of early bars: later spellings continue the sequence.
        early = [e.spelled for e in comp.events if e.bar_index < 2]
        late = [e.spelled for e in comp.events if e.bar_index >= 5]
        self.assertNotEqual(early, late[: len(early)])

        midis = []
        from music_coach_ami.musical_idea_engine import _midi

        for e in comp.events:
            midis.append(_midi(e.spelled, e.octave))
        self.assertLessEqual(max(midis), 90)
        self.assertGreaterEqual(min(midis), 67)

        abc, diag = composition_to_abc(comp, title="D harm", bpm=90)
        self.assertIn("K:Dm", diag.get("abc_key_field") or "")
        self.assertTrue(diag.get("notation_validation_ok"), diag)
        self.assertIn("Q:1/4=90", abc)

    def test_bb_harmonic_minor_scale_and_abc(self) -> None:
        from music_coach_ami.musical_idea_engine import (
            authoritative_scale_degrees,
            composition_to_abc,
            generate_scale_pattern,
        )
        from music_coach_ami.musical_idea_request import resolve_musical_idea_request
        from music_coach_ami.pipeline import run_coach_submit

        expected = authoritative_scale_degrees("Bb", "harmonic minor")
        self.assertEqual(expected, ["Bb", "C", "Db", "Eb", "F", "Gb", "A"])

        idea = resolve_musical_idea_request(
            "Give me a 4-bar harmonic minor pattern in Bb minor.",
            default_object="pattern",
            instrument="Flute",
        )
        comp = generate_scale_pattern(idea, notation_instrument="Flute")
        self.assertEqual(list(comp.scale_spelling), expected)
        self.assertNotIn("A#", list(comp.scale_spelling) + [e.spelled for e in comp.events])
        abc, diag = composition_to_abc(comp, title="Bb", bpm=96)
        self.assertIn("K:Bbm", diag.get("abc_key_field") or "")
        self.assertTrue(diag.get("notation_validation_ok"))

        _, resp = run_coach_submit(
            "Give me a harmonic minor pattern in Bb minor.",
            {"instrument": "Flute", "level": "Intermediate", "focus": "Scales", "display_key": "C"},
            ami_ctx={"instrument": "Flute", "level": "Intermediate", "focus": "Scales", "coach_page": "practice"},
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertIn("musical_idea", resp.source_solver)
        self.assertEqual(resp.diagnostics.get("scale_spelling"), expected)

    def test_descending_a_harmonic_minor(self) -> None:
        from music_coach_ami.musical_idea_engine import (
            authoritative_scale_degrees,
            cell_anchor_midis,
            generate_scale_pattern,
        )
        from music_coach_ami.musical_idea_request import resolve_musical_idea_request

        self.assertEqual(
            authoritative_scale_degrees("A", "harmonic minor"),
            ["A", "B", "C", "D", "E", "F", "G#"],
        )
        idea = resolve_musical_idea_request(
            "Give me a 4-bar descending harmonic minor pattern in A minor.",
            default_object="pattern",
            instrument="Flute",
        )
        self.assertEqual(idea.direction, "descending")
        comp = generate_scale_pattern(idea, notation_instrument="Flute")
        self.assertTrue(comp.validation_ok, comp.validation_errors)
        anchors = cell_anchor_midis(comp)
        wrap = next((i for i in range(1, len(anchors)) if anchors[i] > anchors[i - 1] + 1), None)
        end = wrap if wrap is not None else len(anchors)
        for i in range(1, end):
            self.assertLessEqual(anchors[i], anchors[i - 1] + 1)

    def test_flute_default_vs_high_register(self) -> None:
        from music_coach_ami.musical_idea_engine import _midi, generate_scale_pattern
        from music_coach_ami.musical_idea_request import resolve_musical_idea_request

        default = generate_scale_pattern(
            resolve_musical_idea_request(
                "Give me a harmonic minor pattern in Bb minor.",
                default_object="pattern",
                instrument="Flute",
            ),
            notation_instrument="Flute",
        )
        high = generate_scale_pattern(
            resolve_musical_idea_request(
                "Give me a high-register harmonic minor pattern in Bb minor.",
                default_object="pattern",
                instrument="Flute",
            ),
            notation_instrument="Flute",
        )
        d_mid = [_midi(e.spelled, e.octave) for e in default.events]
        h_mid = [_midi(e.spelled, e.octave) for e in high.events]
        self.assertLessEqual(max(d_mid), 90)
        self.assertGreater(sum(h_mid) / len(h_mid), sum(d_mid) / len(d_mid))

    def test_c_minor_lick_written_label_for_alto(self) -> None:
        from music_coach_ami.pipeline import run_coach_submit

        session = {
            "instrument": "Saxophone",
            "selected_transposing_instrument": "Alto saxophone (Eb)",
            "level": "Beginner",
            "focus": "Tone",
            "display_key": "C",
        }
        _, resp = run_coach_submit(
            "Give me a very easy 4-bar lick in C minor.",
            session,
            ami_ctx={
                "instrument": "Saxophone",
                "level": "Beginner",
                "focus": "Tone",
                "display_key": "C",
                "coach_page": "practice",
                "selected_transposing_instrument": "Alto saxophone (Eb)",
            },
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        text = f"{resp.direct_answer}\n" + "\n".join(resp.practice_steps or [])
        self.assertIn("Concert", text)
        self.assertIn("written", text.lower())
        self.assertTrue("A" in text)
        self.assertIn("K:Am", resp.notation_abc or "")
        midis = resp.diagnostics.get("written_midi_range_used") or [0, 99]
        self.assertLessEqual(midis[1] - midis[0], 24)

    def test_chorus_section_explicit(self) -> None:
        from music_coach_ami.pipeline import run_coach_submit

        _, missing = run_coach_submit(
            "Give me a 4-bar phrase over the chorus.",
            {"instrument": "Guitar", "display_key": "C", "level": "Beginner"},
            ami_ctx={
                "instrument": "Guitar",
                "display_key": "C",
                "chart_sections": {"A": ["C", "G"], "B": ["Am", "F"]},
                "practice_focus_section": "A",
                "coach_page": "practice",
            },
        )
        self.assertIsNotNone(missing)
        assert missing is not None
        self.assertIn("doesn't have a section labeled", missing.direct_answer)

        _, hit = run_coach_submit(
            "Give me a 4-bar phrase over the chorus.",
            {"instrument": "Guitar", "display_key": "C", "level": "Beginner"},
            ami_ctx={
                "instrument": "Guitar",
                "display_key": "C",
                "chart_sections": {"Chorus": ["F", "G", "C", "Am"], "Verse": ["Dm"]},
                "practice_focus_section": "Verse",
                "coach_page": "practice",
            },
        )
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual((hit.diagnostics.get("section_resolution") or {}).get("section"), "Chorus")
        self.assertIn("Chorus", hit.direct_answer)

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


class WrittenDomainSongRelativeTests(unittest.TestCase):
    def test_part_b_explicit_over_active_a(self) -> None:
        from music_coach_ami.musical_idea_knowledge import extract_requested_section
        from music_coach_ami.pipeline import run_coach_submit

        self.assertEqual(extract_requested_section("Give me a 4-bar phrase over part B."), "b")
        _, resp = run_coach_submit(
            "Give me a 4-bar phrase over part B.",
            {"instrument": "Guitar", "display_key": "C", "level": "Beginner"},
            ami_ctx={
                "instrument": "Guitar",
                "display_key": "C",
                "chart_sections": {"A": ["C", "G"], "B": ["Am", "F", "G", "C"]},
                "practice_focus_section": "A",
                "coach_page": "practice",
            },
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        sec = resp.diagnostics.get("section_resolution") or {}
        self.assertEqual(sec.get("section"), "B")
        self.assertIn("B", resp.direct_answer)
        self.assertNotIn("over A", (resp.direct_answer or "").lower())
        self.assertEqual(resp.diagnostics.get("bars_with_events"), [0, 1, 2, 3])

    def test_verse_alias_preserves_lick_object(self) -> None:
        from music_coach_ami.pipeline import run_coach_submit

        _, resp = run_coach_submit(
            "Give me a 4-bar lick over the verse.",
            {
                "instrument": "Clarinet",
                "display_key": "G",
                "level": "Beginner",
                "selected_transposing_instrument": "Bb Clarinet",
            },
            ami_ctx={
                "instrument": "Clarinet",
                "display_key": "G",
                "practice_key": "G",
                "chart_sections": {"Verse 1": ["G6", "Em7", "C", "D"], "Chorus": ["G"]},
                "chart_sections_in_practice_key": True,
                "practice_focus_section": "Chorus",
                "coach_page": "practice",
                "selected_transposing_instrument": "Bb Clarinet",
            },
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual(resp.diagnostics.get("musical_object"), "lick")
        self.assertEqual((resp.diagnostics.get("section_resolution") or {}).get("section"), "Verse 1")
        self.assertIn("lick", (resp.direct_answer or "").lower())
        self.assertNotIn("phrase over", (resp.direct_answer or "").lower())
        self.assertEqual(resp.diagnostics.get("bars_with_events_count"), 4)

    def test_written_chords_match_notes_for_bb_clarinet(self) -> None:
        import re

        from dataclasses import replace

        from music_coach_ami.musical_idea_engine import (
            composition_to_abc,
            generate_idea_over_chords,
            play_summary,
        )
        from music_coach_ami.musical_idea_knowledge import _transpose_composition_preserving_degrees
        from music_coach_ami.musical_idea_request import resolve_musical_idea_request
        from music_coach_ami.notation_profile import notation_profile_for_instrument
        from music_theory import transpose_chord

        concert = ["G6", "C7b9", "Bbmaj9", "G/B"]
        expected_written = [transpose_chord(c, 2, reference_key="G") for c in concert]
        self.assertEqual(expected_written, ["A6", "D7b9", "Cmaj9", "A/C#"])

        idea = resolve_musical_idea_request(
            "Give me a 4-bar phrase over the verse.",
            default_object="phrase",
            instrument="Clarinet",
        )
        idea = replace(idea, bars=4, song_relative=True)
        comp = generate_idea_over_chords(
            idea,
            concert,
            notation_instrument="Bb Clarinet",
            reference_key="G",
            object_type="phrase",
        )
        self.assertEqual(sorted({e.bar_index for e in comp.events}), [0, 1, 2, 3])
        written = _transpose_composition_preserving_degrees(
            comp,
            "A",
            2,
            notation_profile_for_instrument("Bb Clarinet"),
            concert_key="G",
        )
        bar_chords = []
        for bar_i in range(4):
            evs = [e for e in written.events if e.bar_index == bar_i]
            self.assertTrue(evs)
            self.assertTrue(all(e.domain == "written" for e in evs))
            self.assertEqual(evs[0].chord, expected_written[bar_i])
            bar_chords.append(evs[0].chord)
        summary = "\n".join(play_summary(written))
        for wc in expected_written:
            self.assertIn(f"({wc})", summary)
            self.assertNotIn("(G6)", summary)
        abc, diag = composition_to_abc(written, title="Written Phrase", bpm=96)
        abc_chords = re.findall(r'"([^"]+)"', abc)
        self.assertEqual(abc_chords, expected_written)
        self.assertIn("K:A", diag.get("abc_key_field") or "")

    def test_harmony_timeline_and_bar_fill_counts(self) -> None:
        from music_coach_ami.musical_idea_engine import expand_harmony_timeline, generate_idea_over_chords
        from music_coach_ami.musical_idea_request import resolve_musical_idea_request

        self.assertEqual(expand_harmony_timeline(["G6"], 4), ["G6", "G6", "G6", "G6"])
        self.assertEqual(expand_harmony_timeline(["G6", "Em7"], 4), ["G6", "Em7", "G6", "Em7"])
        for bars in (2, 4, 8):
            idea = resolve_musical_idea_request(
                f"Give me a {bars}-bar phrase over the verse.",
                default_object="phrase",
                instrument="Guitar",
            )
            comp = generate_idea_over_chords(
                idea,
                ["G6"],
                notation_instrument="Guitar",
                reference_key="G",
                object_type="phrase",
            )
            self.assertEqual(comp.bars, bars)
            self.assertEqual(sorted({e.bar_index for e in comp.events}), list(range(bars)))

    def test_missing_chorus_still_honest(self) -> None:
        from music_coach_ami.pipeline import run_coach_submit

        _, missing = run_coach_submit(
            "Give me a 4-bar phrase over the chorus.",
            {"instrument": "Guitar", "display_key": "C", "level": "Beginner"},
            ami_ctx={
                "instrument": "Guitar",
                "display_key": "C",
                "chart_sections": {"A": ["C", "G"], "B": ["Am", "F"]},
                "practice_focus_section": "A",
                "coach_page": "practice",
            },
        )
        self.assertIsNotNone(missing)
        assert missing is not None
        self.assertIn("doesn't have a section labeled", missing.direct_answer)


if __name__ == "__main__":
    unittest.main()
