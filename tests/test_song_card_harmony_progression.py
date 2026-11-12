"""Issue 67: the Harmony summary must describe the progression the song has.

The defects these hold the card to, each measured on the real catalog before the
change:

* *The A Team*'s verse and chorus are both ``A E F#m D`` - I-V-vi-IV - and the card
  said "Diatonic harmony in A major built on E, A, D, F#m": the four commonest
  chords, in frequency order, starting on the dominant. The detector counted
  repetitions of a four-chord window *in the stored chart text*, and a chart
  stores one pass per section, so a genuine loop scored 2 against a threshold of 3.
* *Say* read ``B♭:2 - E♭:2p - Gm:2 - F:2p`` in its own key and ``D - G - Bm - A``
  when transposed, because the transposition path strips chart syntax and the
  identity path does not.
* *Shallow*'s ``Em:2|D:1.5|G:0.5`` is one measure of three chords; it became three
  members of a "four-chord loop" ending ``- G``, numerals ``vi-V-I-I``.
* *Hey Jude* was described by its four written-out Coda blocks (``F - E♭ - B♭ - F``),
  a chord (E♭) that appears in no verse or bridge.
"""

from __future__ import annotations

import re
import unittest

from song_card_guidance import (
    _bar_chords,
    _bar_period,
    _choose_progression,
    _is_main_section,
    _same_progression,
    _section_progression,
    _section_rank,
    analyze_song_harmony,
    build_song_card_guidance,
    expand_sections,
    section_bars,
)
from song_catalog.catalog import curated_song_records

#: Chart-only syntax attached to a chord symbol (prose has its own colons).
CHART_SYNTAX = re.compile(r"[A-G][#b♯♭]?[^\s,;.()]*(?::[0-9.]+|\|)")
CATALOG = {str(r.get("title") or ""): r for r in curated_song_records()}


def card(title: str, *, key: str | None = None, level: str = "Intermediate") -> str:
    record = CATALOG[title]
    pk = key or str(record.get("key") or "C")
    return str(build_song_card_guidance(
        record, level=level, instrument="Piano", focus="Chords & Harmony",
        practice_key=pk, chart_key=pk,
    ).get("harmony") or "")


class AChartCellIsNotAChord(unittest.TestCase):
    """Chart-only duration and push syntax never reaches a chord name."""

    def test_a_split_bar_becomes_its_chords(self):
        self.assertEqual(_bar_chords("Bb:2|Eb:2p"), ["Bb", "Eb"])

    def test_three_chords_in_one_bar_keep_their_order(self):
        self.assertEqual(_bar_chords("Em:2|D:1.5|G:0.5"), ["Em", "D", "G"])

    def test_harmony_survives_the_strip(self):
        for cell, want in (
            ("Bbsus4/C", ["Bbsus4/C"]),
            ("Dm7b5:2|G7b9:2p", ["Dm7b5", "G7b9"]),
            ("C/G", ["C/G"]),
            ("Abmaj7", ["Abmaj7"]),
            ("F#m11", ["F#m11"]),
        ):
            with self.subTest(cell=cell):
                self.assertEqual(_bar_chords(cell), want)

    def test_non_chord_cells_are_skipped(self):
        for cell in ("N.C.", "NC", "%", "-", ""):
            with self.subTest(cell=cell):
                self.assertEqual(_bar_chords(cell), [])

    def test_bars_keep_their_boundaries(self):
        bars = section_bars({"Verse": ["Bb:2|Eb:2p", "Gm:2|F:2p"]})
        self.assertEqual(bars, [("Verse", [["Bb", "Eb"], ["Gm", "F"]])])

    def test_expand_sections_still_gives_a_flat_stream(self):
        self.assertEqual(
            expand_sections({"Verse": ["Bb:2|Eb:2p", "Gm:2|F:2p"]}),
            [("Verse", ["Bb", "Eb", "Gm", "F"])],
        )


class TheRepeatingUnitIsCountedInBars(unittest.TestCase):
    def test_a_period_must_be_a_whole_number_of_bars(self):
        bars = [["Em", "D", "G"], ["G"], ["C"], ["G", "D"]] * 2
        self.assertEqual(_bar_period(bars), 4)

    def test_a_section_that_does_not_tile_is_its_own_period(self):
        bars = [["F"], ["C"], ["Bb"], ["F"], ["F7"]]
        self.assertEqual(_bar_period(bars), 5)

    def test_shallows_first_bar_is_not_three_loop_members(self):
        """The defect: Em:2 - D:1.5 - G:0.5 - G, numerals vi-V-I-I."""
        bars = [["Em", "D", "G"], ["G"], ["C"], ["G", "D"]] * 2
        prog = _section_progression(bars)
        self.assertEqual(prog.bars, 4, "the unit is four bars, not four chords")
        self.assertEqual(prog.chords, ("Em", "D", "G", "C", "G", "D"))
        self.assertTrue(prog.repeats_within_section)

    def test_consecutive_holds_are_one_harmonic_event(self):
        bars = [["Eadd9"], ["Eadd9"], ["C#m7"], ["C#m7"]] * 2
        prog = _section_progression(bars)
        self.assertEqual(prog.chords, ("Eadd9", "C#m7"))
        self.assertEqual(prog.bars, 4)


class SectionsAreWeighedByWhatTheyAreWorth(unittest.TestCase):
    def test_intro_outro_coda_and_tag_are_not_main_sections(self):
        for name in ("Intro", "Outro", "Coda 1", "Instrumental Tag", "Interlude", "Solo"):
            with self.subTest(name=name):
                self.assertFalse(_is_main_section(name))

    def test_verse_and_chorus_outrank_the_other_main_sections(self):
        self.assertEqual(_section_rank("Verse 1"), 0)
        self.assertEqual(_section_rank("Chorus 2"), 0)
        for name in ("Pre-Chorus 1", "Bridge", "Refrain 2", "A"):
            with self.subTest(name=name):
                self.assertEqual(_section_rank(name), 1)

    def test_a_coda_cannot_speak_for_the_song(self):
        rows = [
            ("Verse 1", [["F"], ["C"], ["Bb"], ["F"]]),
            ("Verse 2", [["F"], ["C"], ["Bb"], ["F"]]),
            ("Coda 1", [["F"], ["Eb"], ["Bb"], ["F"]] * 2),
            ("Coda 2", [["F"], ["Eb"], ["Bb"], ["F"]] * 2),
            ("Coda 3", [["F"], ["Eb"], ["Bb"], ["F"]] * 2),
        ]
        chosen = _choose_progression(rows)
        self.assertEqual(chosen.chords, ("F", "C", "Bb", "F"))
        self.assertEqual(chosen.sections, ("Verse 1", "Verse 2"))

    def test_a_coda_may_still_answer_when_nothing_else_repeats(self):
        """Explicitly labelled Coda-only material is not rejected outright."""
        rows = [("Coda", [["F"], ["Eb"], ["Bb"], ["F"]] * 2)]
        chosen = _choose_progression(rows)
        self.assertEqual(chosen.chords, ("F", "Eb", "Bb", "F"))
        self.assertFalse(chosen.main, "the card must know it is not a main section")

    def test_an_extra_tag_bar_is_the_same_progression(self):
        self.assertTrue(_same_progression(("Em", "D", "G", "C"), ("Em", "D", "G", "C", "D")))
        self.assertFalse(_same_progression(("Em", "D", "G", "C"), ("Am", "D", "G", "Em")))


class TheReportedProgressionIsOneTheSongPlays(unittest.TestCase):
    def test_the_a_team_is_named_as_i_v_vi_iv(self):
        facts = analyze_song_harmony(CATALOG["The A Team"])
        self.assertEqual(facts.loop, ("A", "E", "F#m", "D"))
        self.assertEqual(facts.loop_numerals, ("I", "V", "vi", "IV"))
        text = card("The A Team")
        self.assertIn("I–V–vi–IV", text)
        self.assertIn("A – E – F♯m – D", text)
        self.assertNotIn("built on", text)

    def test_castle_on_the_hill_is_named_as_i_iv_vi_v(self):
        facts = analyze_song_harmony(CATALOG["Castle on the Hill"])
        self.assertEqual(facts.loop, ("D", "G", "Bm", "A"))
        self.assertEqual(facts.loop_numerals, ("I", "IV", "vi", "V"))

    def test_say_reads_as_clean_chords_in_its_own_key(self):
        text = card("Say", key="Bb")
        self.assertIn("B♭ – E♭ – Gm – F", text)
        self.assertIsNone(CHART_SYNTAX.search(text), text)

    def test_shape_of_you_loses_its_push_marks(self):
        facts = analyze_song_harmony(CATALOG["Shape of You"])
        self.assertEqual(facts.loop, ("Bm", "Em", "G", "A"))

    def test_hey_jude_is_described_by_its_verse_not_its_coda(self):
        facts = analyze_song_harmony(CATALOG["Hey Jude"])
        self.assertTrue(all(_is_main_section(n) for n in facts.loop_sections),
                        f"credited to {facts.loop_sections}")
        self.assertNotIn("Eb", facts.loop, "E flat is Coda-only material")
        text = card("Hey Jude", key="F")
        self.assertIn("8-bar progression", text)
        self.assertNotIn("E♭", text)

    def test_daughters_keeps_the_chorus_form_it_really_repeats(self):
        """16 occurrences against the verse form's 12 - the old answer was right."""
        facts = analyze_song_harmony(CATALOG["Daughters"])
        self.assertIn("E7", facts.loop)

    def test_photograph_is_credited_to_a_section_that_plays_it(self):
        facts = analyze_song_harmony(CATALOG["Photograph"])
        rows = dict(section_bars(CATALOG["Photograph"]["sections"]))
        for name in facts.loop_sections:
            with self.subTest(section=name):
                prog = _section_progression(rows[name])
                self.assertTrue(_same_progression(prog.chords, facts.loop))

    def test_a_rotation_is_called_a_rotation(self):
        facts = analyze_song_harmony(CATALOG["Photograph"])
        self.assertTrue(facts.loop_rotated_sections)
        text = card("Photograph", key="E")
        self.assertIn("same chords in another order", text)


class LongerAndChangingHarmonyIsNotForcedIntoFourChords(unittest.TestCase):
    def test_autumn_leaves_is_not_given_a_pop_loop(self):
        text = card("Autumn Leaves")
        self.assertNotIn("four chords", text)
        self.assertIn("ii–V", text)

    def test_hey_jude_is_described_by_its_length(self):
        facts = analyze_song_harmony(CATALOG["Hey Jude"])
        self.assertEqual(facts.loop_bars, 8)
        self.assertEqual(facts.character, "progression")

    def test_shallow_is_a_four_bar_progression_not_a_four_chord_loop(self):
        facts = analyze_song_harmony(CATALOG["Shallow"])
        self.assertEqual(facts.loop_bars, 4)
        self.assertEqual(len(facts.loop), 6)
        text = card("Shallow", key="G")
        self.assertIn("four-bar progression", text)
        self.assertNotIn("vi–V–I–I", text)

    def test_contrasting_sections_are_named(self):
        text = card("Shallow", key="G")
        self.assertIn("move differently", text)

    def test_a_shared_progression_is_not_called_a_continuous_loop(self):
        """The verse and chorus each play it once: shared, not looping."""
        facts = analyze_song_harmony(CATALOG["The A Team"])
        self.assertFalse(facts.loop_repeats_within_section)
        text = card("The A Team")
        self.assertIn("shared by", text)
        self.assertNotIn("repeating", text)

    def test_a_genuine_loop_is_called_one(self):
        facts = analyze_song_harmony(CATALOG["Say"])
        self.assertTrue(facts.loop_repeats_within_section)
        self.assertIn("loop", card("Say", key="Bb"))


class NumeralsAndNamesDescribeTheSameProgression(unittest.TestCase):
    SONGS = ("The A Team", "Castle on the Hill", "Say", "Shape of You",
             "Hey Jude", "Photograph", "Shallow")

    def test_one_numeral_per_chord(self):
        for title in self.SONGS:
            with self.subTest(song=title):
                facts = analyze_song_harmony(CATALOG[title])
                self.assertEqual(len(facts.loop), len(facts.loop_numerals))
                self.assertNotIn("?", facts.loop_numerals)

    def test_numerals_do_not_move_with_the_practice_key(self):
        """The numerals come from the song's own key, so every Practice Key
        prints the same ones - the Advanced card is the one that shows them."""
        for title in self.SONGS:
            with self.subTest(song=title):
                facts = analyze_song_harmony(CATALOG[title])
                if facts.character not in ("loop", "progression"):
                    continue
                romans = "–".join(facts.loop_numerals).replace("b", "♭")
                for key in ("C", "F#"):
                    with self.subTest(key=key):
                        self.assertIn(romans, card(title, key=key, level="Advanced"))

    def test_the_names_do_move_with_the_practice_key(self):
        first = card("The A Team", key="A")
        moved = card("The A Team", key="C")
        self.assertIn("A – E – F♯m – D", first)
        self.assertIn("C – G – Am – F", moved)
        self.assertIn("I–V–vi–IV", first)
        self.assertIn("I–V–vi–IV", moved)

    def test_no_chart_syntax_in_any_key_or_level(self):
        for title in self.SONGS:
            for key in ("C", "Eb", "A", None):
                for level in ("Beginner", "Intermediate", "Advanced"):
                    with self.subTest(song=title, key=key, level=level):
                        text = card(title, key=key, level=level)
                        self.assertIsNone(CHART_SYNTAX.search(text), text)


class CustomAndCompositionRecordsGoThroughTheSamePath(unittest.TestCase):
    CUSTOM = {
        "title": "My Progression",
        "key": "C",
        "sections": {
            "Verse": ["C:2|Am:2p", "F:2|G:2p", "C:2|Am:2p", "F:2|G:2p"],
            "Chorus": ["C:2|Am:2p", "F:2|G:2p", "C:2|Am:2p", "F:2|G:2p"],
        },
    }
    COMPOSITION = {
        "title": "My Song",
        "key": "Eb",
        "sections": {
            "Verse 1": ["Ebmaj7", "Cm7", "Fm7", "Bb7"] * 2,
            "Bridge": ["Abmaj7", "Db7", "Ebmaj7", "Bb7sus4"],
        },
    }

    def test_a_custom_progression_with_split_bars_reads_cleanly(self):
        facts = analyze_song_harmony(self.CUSTOM)
        self.assertEqual(facts.loop, ("C", "Am", "F", "G"))
        self.assertEqual(facts.loop_numerals, ("I", "vi", "IV", "V"))
        text = str(build_song_card_guidance(
            self.CUSTOM, level="Intermediate", instrument="Piano",
            focus="Chords & Harmony", practice_key="C", chart_key="C",
        ).get("harmony") or "")
        self.assertIsNone(CHART_SYNTAX.search(text), text)
        self.assertIn("C – Am – F – G", text)

    def test_a_composition_names_its_own_recurring_progression(self):
        facts = analyze_song_harmony(self.COMPOSITION)
        self.assertEqual(facts.loop, ("Ebmaj7", "Cm7", "Fm7", "Bb7"))
        self.assertEqual(facts.loop_sections, ("Verse 1",))
        self.assertTrue(facts.loop_repeats_within_section)

    def test_a_record_with_no_sections_says_so(self):
        text = str(build_song_card_guidance(
            {"title": "Empty", "key": "C", "sections": {}}, level="Intermediate",
            instrument="Piano", focus="Chords & Harmony", practice_key="C", chart_key="C",
        ).get("harmony") or "")
        self.assertIn("chord chart", text)


class EveryCatalogSongPassesTheSameChecks(unittest.TestCase):
    """The survey in scripts/_audit_i67_harmony_loops.py, as a gate."""

    def test_no_reported_progression_is_absent_from_its_own_section(self):
        for record in curated_song_records():
            facts = analyze_song_harmony(record)
            if not facts.loop:
                continue
            rows = dict(section_bars(record.get("sections") or {}))
            credited = [n for n in facts.loop_sections if n in rows]
            if not credited:
                continue
            with self.subTest(song=record.get("title")):
                ok = []
                for name in credited:
                    prog = _section_progression(rows[name])
                    ok.append(bool(prog) and _same_progression(prog.chords, facts.loop))
                self.assertTrue(any(ok), f"{facts.loop} not played by {credited}")

    def test_a_main_section_is_credited_whenever_one_was_available(self):
        for record in curated_song_records():
            facts = analyze_song_harmony(record)
            if not facts.loop or not facts.loop_from_main_section:
                continue
            with self.subTest(song=record.get("title")):
                self.assertTrue(
                    any(_is_main_section(n) for n in facts.loop_sections),
                    f"credited only to {facts.loop_sections}",
                )


if __name__ == "__main__":
    unittest.main()
