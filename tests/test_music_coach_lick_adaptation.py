"""Lick adaptation, routing, length, and song/section identity guards."""

from __future__ import annotations

import unittest
from collections import Counter
from dataclasses import replace

from music_coach_ami.melodic_motion import (
    adapt_motif_to_harmony,
    bar_is_pitch_collapsed,
    contour_signs,
    motif_interval_shape,
)
from music_coach_ami.musical_idea_engine import generate_idea_over_chords, generate_lick_through_section
from music_coach_ami.musical_idea_knowledge import is_musical_idea_content_request
from music_coach_ami.musical_idea_request import resolve_musical_idea_request
from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami.router import route_question
from music_coach_ami.types import CoachIntent
from music_theory import midi_from_spelled_note


NYSOM_VERSE = [
    "C",
    "E7",
    "Am7",
    "Gm7|C7",
    "F",
    "A7",
    "Dm",
    "Bb9",
    "C",
    "E7/B",
    "Am7",
    "C/G",
    "F",
    "C/E",
    "D7",
    "C/F",
    "F/G",
    "Am",
    "D7",
    "Am",
    "G",
    "F/G",
]
NYSOM_CHORUS = [
    "Am7",
    "D7",
    "Gmaj7",
    "G",
    "Gm7",
    "C7",
    "Fmaj7",
    "Bm7",
    "E7",
    "Amaj7",
    "Am7",
    "D7",
    "Gmaj7",
    "Dm7",
    "F/G|G7",
]
POP_VERSE = ["C", "G", "Am", "F", "C", "G", "Am", "F"]


def _tenor_ctx(sections: dict, *, section: str, level: str = "Intermediate") -> dict:
    return {
        "instrument": "Tenor Sax",
        "level": level,
        "focus": "Improvisation",
        "display_key": "C",
        "practice_key": "C",
        "coach_page": "practice",
        "chart_sections": sections,
        "chart_sections_in_practice_key": True,
        "practice_focus_section": section,
        "selected_transposing_instrument": "Tenor saxophone (Bb)",
        "active_song": {"title": "New York State of Mind", "key": "C"},
    }


def _tenor_session() -> dict:
    return {
        "instrument": "Tenor Sax",
        "display_key": "C",
        "level": "Intermediate",
        "selected_transposing_instrument": "Tenor saxophone (Bb)",
        "instrument_change_source": "sidebar",
    }


def _event_dicts(composition) -> list[dict]:
    out: list[dict] = []
    for e in composition.events:
        rest = str(e.duration or "").lower().startswith("rest") or not str(e.spelled or "").strip()
        midi = 0 if rest else int(midi_from_spelled_note(e.spelled, octave=e.octave))
        out.append(
            {
                "spelled": e.spelled,
                "octave": e.octave,
                "duration": e.duration,
                "bar_index": e.bar_index,
                "beat": e.beat,
                "midi": midi,
                "chord": e.chord,
            }
        )
    return out


def _rising_falling_motif() -> list[dict]:
    notes = [
        ("A", 4, 0.0, "eighth"),
        ("C", 5, 0.5, "eighth"),
        ("E", 5, 1.0, "eighth"),
        ("D", 5, 1.5, "eighth"),
        ("C", 5, 2.0, "quarter"),
        ("B", 4, 3.0, "eighth"),
        ("A", 4, 3.5, "eighth"),
    ]
    out = []
    for spelled, octv, beat, dur in notes:
        midi = int(midi_from_spelled_note(spelled, octave=octv))
        out.append(
            {
                "spelled": spelled,
                "octave": octv,
                "duration": dur,
                "bar_index": 0,
                "beat": beat,
                "midi": midi,
                "chord": "Am7",
                "slur_group": 1,
                "articulation": ">" if beat == 0.0 else "",
            }
        )
    return out


class LickIntentRoutingTests(unittest.TestCase):
    def test_generate_lick_for_the_verse_is_musical_idea(self) -> None:
        q = "Generate a lick for the verse"
        self.assertTrue(is_musical_idea_content_request(q, q.lower()))
        req = route_question(q, {}, ami_ctx={"coach_page": "practice"})
        self.assertEqual(req.intent, CoachIntent.SCALE_PRACTICE)

    def test_give_me_lick_variants_route_to_generation(self) -> None:
        for q in (
            "give me a lick over the verse",
            "write a lick for the chorus",
            "make me a two-bar lick",
            "show me a lick for Part A",
            "give me an advanced lick over the bridge",
            "create a lick for the verse",
        ):
            with self.subTest(q=q):
                self.assertTrue(is_musical_idea_content_request(q, q.lower()))
                req = route_question(q, {}, ami_ctx={"coach_page": "practice"})
                self.assertEqual(req.intent, CoachIntent.SCALE_PRACTICE)

    def test_how_should_i_practice_the_verse_stays_coaching(self) -> None:
        q = "How should I practice the verse?"
        self.assertFalse(is_musical_idea_content_request(q, q.lower()))
        req = route_question(
            q,
            {},
            ami_ctx={
                "coach_page": "practice",
                "chart_sections": {"Verse 1": NYSOM_VERSE, "Chorus 1": NYSOM_CHORUS},
                "practice_focus_section": "Full Song",
                "active_song": {"title": "New York State of Mind", "key": "C"},
            },
        )
        self.assertEqual(req.intent, CoachIntent.SONG_COACHING)

    def test_generate_lick_for_verse_returns_lick_not_practice_advice(self) -> None:
        _, resp = run_coach_submit(
            "Generate a lick for the verse",
            _tenor_session(),
            ami_ctx=_tenor_ctx({"Verse 1": NYSOM_VERSE, "Chorus 1": NYSOM_CHORUS}, section="Full Song"),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual((resp.diagnostics or {}).get("resolved_object"), "lick")
        self.assertEqual((resp.diagnostics or {}).get("resolved_section"), "Verse 1")
        self.assertTrue(resp.notation_abc)
        md = resp.composed_markdown()
        self.assertIn("Verse 1", md)
        self.assertTrue("lick" in md.lower())
        self.assertIn("16-Bar Lick Over Verse 1", resp.notation_abc or "")
        self.assertNotIn("prioritize **Full Song** first", md)


class RequestedLengthTests(unittest.TestCase):
    def test_two_bar_lick_is_exactly_two_bars(self) -> None:
        idea = resolve_musical_idea_request(
            "Give me a two bar lick for the verse",
            default_object="lick",
            instrument="Tenor Sax",
            level="Intermediate",
        )
        self.assertEqual(idea.bars, 2)
        _, resp = run_coach_submit(
            "Give me a two bar lick for the verse",
            _tenor_session(),
            ami_ctx=_tenor_ctx({"Verse 1": NYSOM_VERSE, "Chorus 1": NYSOM_CHORUS}, section="Verse 1"),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual((resp.diagnostics or {}).get("bars_generated"), 2)
        self.assertEqual((resp.diagnostics or {}).get("resolved_object"), "lick")
        meta = (resp.diagnostics or {}).get("motif_meta") or {}
        self.assertEqual(meta.get("motif_bars"), 2)
        self.assertEqual(meta.get("output_bars"), 2)

    def test_advanced_four_bar_chorus_lick_is_four_bars(self) -> None:
        _, resp = run_coach_submit(
            "Give me an advanced 4-bar lick over the chorus",
            {**_tenor_session(), "level": "Advanced"},
            ami_ctx=_tenor_ctx(
                {"Verse 1": NYSOM_VERSE, "Chorus 1": NYSOM_CHORUS},
                section="Chorus 1",
                level="Advanced",
            ),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual((resp.diagnostics or {}).get("bars_generated"), 4)
        self.assertEqual((resp.diagnostics or {}).get("resolved_section"), "Chorus 1")
        meta = (resp.diagnostics or {}).get("motif_meta") or {}
        self.assertEqual(meta.get("output_bars"), 4)
        self.assertIn(meta.get("motif_bars"), (1, 2))
        self.assertLessEqual(int(meta.get("motif_bars") or 9), 2)


class MotifAdaptationQualityTests(unittest.TestCase):
    def test_crafted_rising_motif_keeps_contour_on_d7(self) -> None:
        core = _rising_falling_motif()
        src_signs = contour_signs(motif_interval_shape(core))
        self.assertIn(1, src_signs)
        self.assertIn(-1, src_signs)
        adapted = adapt_motif_to_harmony(
            core,
            ["D7"],
            bar_offset=0,
            reference_key="C",
            low=55,
            high=84,
            prefer=70,
        )
        self.assertFalse(bar_is_pitch_collapsed(adapted, 0))
        dst_signs = contour_signs(motif_interval_shape(adapted))
        self.assertEqual(src_signs, dst_signs)
        midis = [int(e["midi"]) for e in adapted if e.get("midi")]
        self.assertGreaterEqual(len(set(m % 12 for m in midis)), 3)

    def test_am7_d7_gmaj7_adaptation_does_not_collapse(self) -> None:
        idea = resolve_musical_idea_request(
            "Give me an 8-bar lick over part A.",
            default_object="lick",
            instrument="Tenor Sax",
            level="Intermediate",
        )
        idea = replace(idea, bars=8)
        lick = generate_lick_through_section(
            idea,
            ["Am7", "D7", "Gmaj7", "Cmaj7", "F#m7b5", "B7", "Em7", "A7"],
            notation_instrument="Tenor Sax",
            reference_key="C",
            song_title="Contour Tune",
            song_style="jazz",
        )
        events = _event_dicts(lick)
        collapsed = [i for i in range(8) if bar_is_pitch_collapsed(events, i)]
        self.assertEqual(collapsed, [], msg=f"collapsed bars={collapsed}")
        cells = Counter(e.cell_index for e in lick.events)
        self.assertGreaterEqual(len(cells), 3)
        shape = list((lick.motif_meta or {}).get("motif_interval_shape") or [])
        self.assertTrue(any(d != 0 for d in shape))

    def test_sixteen_bar_verse_lick_not_repeated_note_filler(self) -> None:
        idea = resolve_musical_idea_request(
            "Generate a lick for the verse",
            default_object="lick",
            instrument="Tenor Sax",
            level="Intermediate",
        )
        idea = replace(idea, bars=16, section="Verse 1")
        lick = generate_lick_through_section(
            idea,
            NYSOM_VERSE,
            notation_instrument="Tenor Sax",
            reference_key="C",
            song_title="New York State of Mind",
            song_style="jazz",
        )
        events = _event_dicts(lick)
        collapsed = [i for i in range(16) if bar_is_pitch_collapsed(events, i)]
        self.assertEqual(collapsed, [], msg=f"collapsed bars={collapsed}")
        self.assertEqual(lick.bars, 16)
        self.assertEqual((lick.motif_meta or {}).get("melody_source"), "none")


class VoiceLeadingAndHarmonyTests(unittest.TestCase):
    def test_voice_leading_across_chord_changes(self) -> None:
        idea = resolve_musical_idea_request(
            "Give me a 4-bar lick over the chorus",
            default_object="lick",
            instrument="Tenor Sax",
            level="Advanced",
        )
        idea = replace(idea, bars=4, difficulty="advanced")
        lick = generate_lick_through_section(
            idea,
            NYSOM_CHORUS[:4],
            notation_instrument="Tenor Sax",
            reference_key="C",
            song_title="New York State of Mind",
            song_style="jazz",
        )
        events = _event_dicts(lick)
        sounding = [e for e in events if e.get("midi")]
        leaps = [abs(sounding[i]["midi"] - sounding[i - 1]["midi"]) for i in range(1, len(sounding))]
        self.assertTrue(leaps)
        median = sorted(leaps)[len(leaps) // 2]
        self.assertLessEqual(median, 5)
        large = sum(1 for leap in leaps if leap >= 9)
        self.assertLessEqual(large, max(2, len(leaps) // 6))

    def test_notes_agree_with_destination_harmony(self) -> None:
        from music_coach_ami.melodic_motion import chord_vocabulary

        idea = resolve_musical_idea_request(
            "Give me a 4-bar lick over the chorus",
            default_object="lick",
            instrument="Tenor Sax",
            level="Intermediate",
        )
        idea = replace(idea, bars=4)
        lick = generate_lick_through_section(
            idea,
            NYSOM_CHORUS[:4],
            notation_instrument="Tenor Sax",
            reference_key="C",
            song_title="New York State of Mind",
            song_style="jazz",
        )
        legal = 0
        total = 0
        for e in lick.events:
            if str(e.duration or "").startswith("rest") or not e.spelled:
                continue
            total += 1
            vocab = chord_vocabulary(e.chord or "C", reference_key="C")
            pool = set()
            for n in list(vocab.get("chord_tones") or []) + list(vocab.get("scale") or []) + list(
                vocab.get("extensions") or []
            ):
                if n:
                    pool.add(n)
            if e.spelled in pool or e.tone_role in {"approach", "passing", "neighbor"}:
                legal += 1
        self.assertGreater(total, 0)
        self.assertGreaterEqual(legal / total, 0.75)


class SectionAndSongIdentityTests(unittest.TestCase):
    def test_verse_and_chorus_use_different_harmony(self) -> None:
        verse_idea = replace(
            resolve_musical_idea_request(
                "Give me a 4-bar lick for the verse",
                default_object="lick",
                instrument="Tenor Sax",
                level="Intermediate",
            ),
            bars=4,
            section="Verse 1",
        )
        chorus_idea = replace(
            resolve_musical_idea_request(
                "Give me a 4-bar lick over the chorus",
                default_object="lick",
                instrument="Tenor Sax",
                level="Intermediate",
            ),
            bars=4,
            section="Chorus 1",
        )
        verse = generate_lick_through_section(
            verse_idea,
            NYSOM_VERSE[:4],
            notation_instrument="Tenor Sax",
            reference_key="C",
            song_title="New York State of Mind",
            song_style="jazz",
        )
        chorus = generate_lick_through_section(
            chorus_idea,
            NYSOM_CHORUS[:4],
            notation_instrument="Tenor Sax",
            reference_key="C",
            song_title="New York State of Mind",
            song_style="jazz",
        )
        verse_chords = {e.chord.split("|")[0] for e in verse.events if e.chord}
        chorus_chords = {e.chord.split("|")[0] for e in chorus.events if e.chord}
        self.assertTrue(verse_chords.intersection({"C", "E7", "Am7"}))
        self.assertTrue(chorus_chords.intersection({"Am7", "D7", "Gmaj7"}))
        self.assertNotEqual(sorted(verse_chords), sorted(chorus_chords))

    def test_different_song_context_changes_output(self) -> None:
        idea = replace(
            resolve_musical_idea_request(
                "Give me a 4-bar lick for the verse",
                default_object="lick",
                instrument="Tenor Sax",
                level="Intermediate",
            ),
            bars=4,
            section="Verse",
        )
        nysom = generate_lick_through_section(
            idea,
            NYSOM_VERSE[:4],
            notation_instrument="Tenor Sax",
            reference_key="C",
            song_title="New York State of Mind",
            song_style="jazz",
        )
        pop = generate_lick_through_section(
            idea,
            POP_VERSE[:4],
            notation_instrument="Tenor Sax",
            reference_key="C",
            song_title="Let It Be",
            song_style="",
        )
        nysom_notes = [(e.spelled, e.octave, e.bar_index) for e in nysom.events if e.spelled]
        pop_notes = [(e.spelled, e.octave, e.bar_index) for e in pop.events if e.spelled]
        self.assertNotEqual(nysom_notes, pop_notes)
        self.assertNotEqual(
            list((nysom.motif_meta or {}).get("phrase_plan", {}).get("harmonic_digest") or []),
            list((pop.motif_meta or {}).get("phrase_plan", {}).get("harmonic_digest") or []),
        )


class ImprovisationPhraseContinuityTests(unittest.TestCase):
    def test_chorus_improvisation_is_through_composed_not_a_lick(self) -> None:
        idea = replace(
            resolve_musical_idea_request(
                "Give me an improvisation of the chorus",
                default_object="improvisation",
                instrument="Tenor Sax",
                level="Intermediate",
            ),
            bars=8,
            section="Chorus 1",
        )
        improv = generate_idea_over_chords(
            idea,
            NYSOM_CHORUS[:8],
            notation_instrument="Tenor Sax",
            reference_key="C",
            object_type="improvisation",
            song_title="New York State of Mind",
            song_style="jazz",
        )
        self.assertNotIn("lick_through_section", improv.strategy)
        self.assertIn("phrase_plan", improv.strategy)
        events = _event_dicts(improv)
        collapsed = [i for i in range(8) if bar_is_pitch_collapsed(events, i)]
        self.assertEqual(collapsed, [])
        sounding = [e for e in events if e.get("midi")]
        pcs = {e["midi"] % 12 for e in sounding}
        self.assertGreaterEqual(len(pcs), 5)
        bar_starts = []
        for bar in range(1, 8):
            prev = [e for e in sounding if e["bar_index"] == bar - 1]
            cur = [e for e in sounding if e["bar_index"] == bar]
            if prev and cur:
                bar_starts.append(abs(cur[0]["midi"] - prev[-1]["midi"]))
        if bar_starts:
            self.assertLessEqual(sorted(bar_starts)[len(bar_starts) // 2], 7)

    def test_live_improvisation_of_the_chorus_resolves_chorus(self) -> None:
        _, resp = run_coach_submit(
            "Give me an improvisation of the chorus",
            _tenor_session(),
            ami_ctx=_tenor_ctx({"Verse 1": NYSOM_VERSE, "Chorus 1": NYSOM_CHORUS}, section="Verse 1"),
        )
        self.assertIsNotNone(resp)
        assert resp is not None
        self.assertEqual((resp.diagnostics or {}).get("resolved_object"), "improvisation")
        self.assertEqual((resp.diagnostics or {}).get("resolved_section"), "Chorus 1")
        self.assertEqual((resp.diagnostics or {}).get("melody_source"), "none")


if __name__ == "__main__":
    unittest.main()
