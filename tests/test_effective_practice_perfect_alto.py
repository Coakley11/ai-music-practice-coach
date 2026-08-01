"""Perfect + fixed practice C + Alto written charts — effective key and DHA."""

from __future__ import annotations

import unittest

from deep_harmonic_analyzer import HarmonicAnalysisInput, build_deep_harmonic_lesson, single_progression_cycle
from effective_practice_context import build_effective_practice_context, verse_cycle_from_sections
from improvisation_intelligence import coaching_reference_key
from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY
from motif_engine import build_motif_notation_abc
from practice_key_mode import (
    FIXED_PRACTICE_KEY,
    FIXED_PRACTICE_KEY_FAMILY_ID,
    MODE_FIXED,
    PRACTICE_KEY_MODE_KEY,
    set_fixed_practice_key_family,
)


def _perfect_verse_sections() -> dict[str, list[str]]:
    cycle = ["G", "Em7", "Cadd9", "D/F#"]
    verse = cycle * 4
    return {"Verse 1": verse}


class EffectivePracticePerfectAltoTests(unittest.TestCase):
    def _session_fixed_c_alto_written(self) -> dict:
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session: dict = {
            PRACTICE_KEY_MODE_KEY: MODE_FIXED,
            "display_key": "C",
            "concert_key": "C",
            "instrument": "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
        }
        set_fixed_practice_key_family(session, "C|A")
        session[FIXED_PRACTICE_KEY] = "C"
        return session

    def test_concert_and_written_keys_and_progressions(self):
        session = self._session_fixed_c_alto_written()
        song_data = {"key": "G", "title": "Perfect", "artist": "Ed Sheeran", "sections": _perfect_verse_sections()}
        ctx = build_effective_practice_context(
            session,
            original_key="G",
            sections=_perfect_verse_sections(),
            instrument="Saxophone",
            song_data=song_data,
        )
        self.assertEqual(ctx.practice_concert_key, "C")
        self.assertEqual(ctx.chart_key, "A")
        self.assertEqual(ctx.coaching_reference_key, "A")

        concert_cycle = verse_cycle_from_sections(ctx.sections_concert)
        self.assertEqual(concert_cycle[:4], ["C", "Am7", "Fadd9", "G/B"])

        written_cycle = verse_cycle_from_sections(ctx.sections_chart)
        self.assertEqual(written_cycle[:4], ["A", "F#m7", "Dadd9", "E/G#"])

    def test_dha_character_uses_transposed_progression_not_original_g(self):
        session = self._session_fixed_c_alto_written()
        sections_chart = build_effective_practice_context(
            session,
            original_key="G",
            sections=_perfect_verse_sections(),
            instrument="Saxophone",
            song_data={"key": "G", "sections": _perfect_verse_sections()},
        ).sections_chart
        flat = []
        for _n, chs in sections_chart.items():
            flat.extend(chs)
        cycle = single_progression_cycle(flat)
        lesson = build_deep_harmonic_lesson(
            HarmonicAnalysisInput(
                song_title="Perfect",
                artist="Ed Sheeran",
                key_center="C",
                display_key="A",
                sections=sections_chart,
                section_order=list(sections_chart.keys()),
                instrument="Saxophone",
                level="Intermediate",
                focus="Improvisation",
                genre="Pop",
                progression_flat=cycle,
            )
        )
        cards = lesson.get("reference_cards") or []
        char = next(c for c in cards if c.get("kind") == "character")
        md = str(char.get("markdown") or "")
        self.assertNotIn("G–Em7–Cadd9–D/F#", md)
        self.assertTrue("A" in md or "F#m7" in md or "vi" in md.lower())

    def test_motif_abc_spells_sharps_in_written_a(self):
        from improvisation_motif import sync_motif_midi

        ref = coaching_reference_key(key_center="C", display_key="A")
        motif = sync_motif_midi(
            {
                "chord": "F#m7",
                "notes": ["C#4", "F#4", "G#4"],
                "rhythm": "q q q",
            }
        )
        abc = build_motif_notation_abc(motif, key_center=ref, bpm=100)
        self.assertIn("^C", abc)
        self.assertIn("^F", abc)
        self.assertNotIn("_d", abc.lower())


if __name__ == "__main__":
    unittest.main()
