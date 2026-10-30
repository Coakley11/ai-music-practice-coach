"""Song-Aware Coaching S2 — harmonic facts read from the charted chords (song_coach_harmony)."""

from __future__ import annotations

import unittest

from song_coach_context import SOURCE_CUSTOM, build_song_coach_context
from song_coach_harmony import (
    CHORD_TONE,
    CLASH,
    COLOUR,
    ENDING_AUTHENTIC,
    ENDING_DECEPTIVE,
    ENDING_HALF,
    ENDING_HOME,
    ENDING_LEADS_ON,
    ENDING_LOOPS,
    ENDING_MID,
    ENDING_OPEN,
    ENDING_PLAGAL,
    EXTENSION,
    FAMILY_DIM,
    FAMILY_DOMINANT,
    FAMILY_HALF_DIM,
    FAMILY_MAJOR,
    FAMILY_MINOR,
    FAMILY_POWER,
    FAMILY_SUS,
    PASSING,
    TENSION,
    anchor_line,
    change_facts,
    check_collection,
    chord_facts,
    classify_ending,
    key_pentatonic,
    note_use,
    outside_tones,
    section_profile,
)
from song_coach_scope import build_scope, coach_sections


def _names(sym: str) -> dict[str, str]:
    return {t.role: t.name for t in chord_facts(sym).tones}


def _pcs(sym: str) -> set[int]:
    return set(chord_facts(sym).charted_pcs)


class TestChordReading(unittest.TestCase):
    def test_plain_chords_agree_with_the_canonical_speller(self) -> None:
        for sym in ("C", "Cm", "C7", "Cmaj7", "Cm7", "Csus4", "Csus2", "Cm7b5", "Cdim", "Caug", "D/F#", "G7/B", "Em7", "Bbmaj7"):
            f = chord_facts(sym)
            self.assertTrue(f.canonical_agrees, (sym, f.reading_notes))
            self.assertEqual(set(f.canonical_pcs), set(f.stable_pcs), sym)

    def test_added_notes_are_not_dominant_chords(self) -> None:
        f = chord_facts("Cadd9")
        self.assertEqual(f.family, FAMILY_MAJOR)
        self.assertEqual(f.canonical_quality, "dom")  # the shared classifier's reading, recorded
        self.assertEqual(_names("Cadd9"), {"root": "C", "3rd": "E", "5th": "G", "9th": "D"})
        self.assertEqual([t.kind for t in f.tones if t.role == "9th"], [EXTENSION])
        self.assertIn("not a dominant chord (no ♭7)", f.reading_notes)
        self.assertEqual(chord_facts("Dadd11").family, FAMILY_MAJOR)
        self.assertEqual(_names("Fmadd9")["9th"], "G")

    def test_extended_chords_keep_their_seventh(self) -> None:
        self.assertEqual(_names("C9"), {"root": "C", "3rd": "E", "5th": "G", "7th": "Bb", "9th": "D"})
        self.assertEqual(chord_facts("C9").family, FAMILY_DOMINANT)
        self.assertEqual(_names("Cmaj9")["major 7th"], "B")
        self.assertEqual(_names("Cm9")["7th"], "Bb")
        self.assertEqual({_names("G13")[r] for r in ("7th", "9th", "13th")}, {"F", "A", "E"})
        self.assertEqual(_names("A7sus4"), {"root": "A", "4th": "D", "5th": "E", "7th": "G"})
        self.assertEqual(chord_facts("A7sus4").family, FAMILY_SUS)

    def test_sixth_power_minor_major_and_altered_chords(self) -> None:
        self.assertEqual(_names("C6")["6th"], "A")
        self.assertEqual(_pcs("C6/9"), {0, 4, 7, 9, 2})
        self.assertEqual(chord_facts("C5").family, FAMILY_POWER)
        self.assertEqual(chord_facts("C5").stable_pcs, frozenset({0, 7}))
        mm = chord_facts("Cm(maj7)")
        self.assertEqual((mm.family, mm.third.name, mm.seventh.name), (FAMILY_MINOR, "Eb", "B"))
        self.assertEqual(chord_facts("Cm7b5").family, FAMILY_HALF_DIM)
        # The diminished 7th sits on the 7th's letter: Bbb (sounds A), as music theory spells it.
        self.assertEqual(_names("Cdim7")["°7th"], "Bbb")
        self.assertEqual(chord_facts("Cdim7").family, FAMILY_DIM)
        self.assertEqual(_names("C7#9")["♯9"], "D#")
        self.assertTrue({1, 3, 8} <= _pcs("C7alt"))
        self.assertEqual(chord_facts("D/F#").bass, "F#")

    def test_minor_major_seventh_spellings(self) -> None:
        for sym in ("Cm(maj7)", "CmM7", "Cm(M7)", "Cmmaj7"):
            f = chord_facts(sym)
            self.assertEqual(f.charted_pcs, frozenset({0, 3, 7, 11}), sym)  # never both B♭ and B
            self.assertEqual(f.family, FAMILY_MINOR, sym)

    def test_extended_and_altered_dominants(self) -> None:
        for sym in ("C9", "C13", "C7#9", "C7b9", "C7alt", "C7b13", "Bb13", "G7/B"):
            f = chord_facts(sym)
            self.assertEqual(f.family, FAMILY_DOMINANT, sym)
            self.assertEqual(f.seventh.role, "7th", sym)
            self.assertEqual(f.third.role, "3rd", sym)
        self.assertEqual({t.role for t in chord_facts("C7alt").extensions}, {"♭9", "♯9", "♭13"})

    def test_suspended_chords(self) -> None:
        for sym, tones in (("Csus2", {0, 2, 7}), ("Csus4", {0, 5, 7}), ("C7sus4", {0, 5, 7, 10}), ("A7sus", {9, 2, 4, 7}),
                           ("B9sus", {11, 4, 6, 9, 1}), ("Eb7sus4", {3, 8, 10, 1})):
            f = chord_facts(sym)
            self.assertEqual(f.family, FAMILY_SUS, sym)
            self.assertFalse(f.has_third, sym)
            self.assertEqual(set(f.charted_pcs), tones, sym)

    def test_slash_chords_keep_root_bass_and_function_distinct(self) -> None:
        inv = chord_facts("D/F#")
        self.assertEqual((inv.root, inv.bass, inv.fn_root_pc, inv.tone("root").name), ("D", "F#", 2, "D"))
        self.assertEqual(inv.tone_for_pc(6).role, "3rd")  # the bass F# is the 3rd, never the root
        g7 = chord_facts("G/F")
        self.assertEqual((g7.family, g7.seventh.name), (FAMILY_DOMINANT, "F"))
        self.assertEqual(chord_facts("Am/G").seventh.name, "G")
        self.assertEqual(chord_facts("C/B").seventh.role, "major 7th")
        for sym, fn_root, fn_family in (("F/G", 7, FAMILY_SUS), ("C/D", 2, FAMILY_SUS), ("Gm7/C", 0, FAMILY_SUS),
                                        ("C/F", 5, FAMILY_MAJOR), ("Bb/G", 7, FAMILY_MINOR)):
            f = chord_facts(sym)
            self.assertEqual((f.fn_root_pc, f.fn_family), (fn_root, fn_family), sym)
            self.assertEqual(f.tone("root").name, sym.split("/")[0][:2].rstrip("m7"), sym)
            self.assertEqual(f.tone("bass").name, sym.split("/")[1], sym)
        respelled = chord_facts("G#/G")  # a sharp-key respelling of Ab/G keeps the chart's bass name
        self.assertEqual((respelled.tone_for_pc(7).name, respelled.tone_for_pc(7).role), ("G", "bass"))

    def test_spelling_follows_the_root(self) -> None:
        self.assertEqual(_names("Gb7")["7th"], "Fb")  # the ♭7 above G♭ is spelled on F
        self.assertEqual(_names("Abadd9"), {"root": "Ab", "3rd": "C", "5th": "Eb", "9th": "Bb"})
        self.assertEqual(_names("F#9")["9th"], "G#")
        self.assertEqual(_names("Bb9")["7th"], "Ab")
        self.assertEqual(_names("Ebadd9/G")["root"], "Eb")
        self.assertEqual(chord_facts("Ebadd9/G").bass, "G")
        for sym in ("Abadd9", "Bb9", "Ebmaj7", "Dbm7", "Gb7", "Abm(maj7)"):
            self.assertEqual(chord_facts(sym).root, sym[:2], sym)  # never G#, A#, D#, C#, F#

    def test_no_chord_and_unreadable(self) -> None:
        self.assertIsNone(chord_facts("N.C."))
        self.assertIsNone(chord_facts(""))
        weird = chord_facts("Cmi7")
        self.assertIsNotNone(weird)
        self.assertIn("canonical chord tones used", " ".join(weird.reading_notes))

    def test_every_catalog_symbol_reads_and_only_adds_to_the_canonical_tones(self) -> None:
        from song_catalog.catalog import curated_song_records
        from song_coach_scope import harmony_events

        seen = set()
        for rec in curated_song_records():
            for bars in rec["sections"].values():
                for e in harmony_events(bars):
                    if e.no_chord or e.chord in seen:
                        continue
                    seen.add(e.chord)
                    f = chord_facts(e.chord)
                    self.assertIsNotNone(f, e.chord)
                    dropped = set(f.canonical_pcs) - set(f.charted_pcs)
                    if dropped:  # only the documented corrections: a 3rd the symbol rules out
                        self.assertTrue(f.family in (FAMILY_POWER, FAMILY_SUS, FAMILY_MINOR), (e.chord, dropped))
                        self.assertTrue(all((pc - f.root_pc) % 12 in (3, 4) for pc in dropped), e.chord)
        self.assertGreater(len(seen), 150)


class TestNoteUse(unittest.TestCase):
    def cat(self, chord: str, note: str, key: str = "C", style: str = "default") -> str:
        from song_coach_harmony import pc_of

        return note_use(chord_facts(chord), pc_of(note), key=key, style=style).category

    def test_categories_over_a_major_chord(self) -> None:
        self.assertEqual(self.cat("C", "E"), CHORD_TONE)
        self.assertEqual(self.cat("C", "D"), COLOUR)
        self.assertEqual(self.cat("C", "A"), COLOUR)
        self.assertEqual(self.cat("C", "F"), PASSING)
        self.assertEqual(self.cat("C", "F#"), TENSION)
        self.assertEqual(self.cat("C", "Eb"), CLASH)
        self.assertEqual(self.cat("C", "Db"), CLASH)
        self.assertEqual(self.cat("Cadd9", "D"), EXTENSION)

    def test_dominant_tensions_are_choices_not_errors(self) -> None:
        for note in ("Ab", "A#", "C#"):
            self.assertEqual(self.cat("G7", note), TENSION, note)
        self.assertEqual(self.cat("G7", "E"), COLOUR)
        self.assertEqual(self.cat("G7", "C"), PASSING)
        self.assertEqual(self.cat("G7", "F#"), CLASH)  # major 7th against the chord's ♭7

    def test_minor_and_blues(self) -> None:
        self.assertEqual(self.cat("Am", "D"), COLOUR)
        self.assertEqual(self.cat("Am", "F"), PASSING)
        self.assertEqual(self.cat("Am", "C#"), CLASH)
        self.assertEqual(self.cat("C", "Eb", style="blues"), TENSION)
        self.assertEqual(self.cat("C7", "Eb", style="blues"), TENSION)

    def test_outside_tones(self) -> None:
        self.assertEqual([t.name for t in outside_tones(chord_facts("E7"), key="C")], ["G#"])
        self.assertEqual(outside_tones(chord_facts("Am7"), key="C"), ())
        self.assertEqual(outside_tones(chord_facts("F#7"), key="Bm"), ())  # harmonic-minor V


class TestCollections(unittest.TestCase):
    def test_a_missing_third_is_care_not_a_clash(self) -> None:
        name, pent = key_pentatonic("C")
        check = check_collection(name, pent, [chord_facts(c) for c in ("C", "Am", "F", "G")], key="C")
        self.assertTrue(check.usable)
        g = next(f for f in check.fits if f.chord == "G")
        self.assertEqual((g.verdict, g.missing_third), ("fits_with_care", "B"))
        self.assertEqual(check.verdict, "fits_with_care")

    def test_a_real_clash_is_rejected(self) -> None:
        name, pent = key_pentatonic("C")
        check = check_collection(name, pent, [chord_facts(c) for c in ("C", "E7", "Am")], key="C")
        self.assertEqual(check.verdict, "clashes")
        e7 = next(f for f in check.fits if f.chord == "E7")
        self.assertEqual([u.name for u in e7.clash], ["G"])  # the ♯9 against the band's G♯

    def test_the_same_tension_is_colour_in_a_jazz_or_blues_style(self) -> None:
        name, pent = key_pentatonic("C")
        check = check_collection(name, pent, [chord_facts(c) for c in ("C", "E7", "Am")], key="C", style="jazz")
        e7 = next(f for f in check.fits if f.chord == "E7")
        self.assertEqual((e7.verdict, [u.role for u in e7.tension]), ("fits_with_care", ["♯9"]))

    def test_clean_fit(self) -> None:
        check = check_collection("D minor pentatonic", (2, 5, 7, 9, 0), [chord_facts("Dm7")], key="Dm")
        self.assertEqual(check.verdict, "fits")


class TestChanges(unittest.TestCase):
    def test_common_tones_and_moves(self) -> None:
        ch = change_facts(chord_facts("G"), chord_facts("Em7"), at_bar=3)
        self.assertEqual({m.from_tone.name for m in ch.common}, {"G", "B"})
        res = change_facts(chord_facts("Em7"), chord_facts("A7"), at_bar=2)
        guide = [m for m in res.moves if m.guide_resolution]
        self.assertEqual([(m.from_tone.name, m.to_tone.name, m.semitones) for m in guide], [("D", "C#", -1)])

    def test_anchor_line_is_smooth_and_deterministic(self) -> None:
        facts = [chord_facts(c) for c in ("Em7", "A7", "Dmaj7", "Gmaj7", "C#m7b5", "F#7", "Bm")]
        line = anchor_line(facts, roles=("3", "7"))
        self.assertEqual([t.name for t in line], ["G", "G", "F#", "F#", "E", "E", "D"])
        self.assertEqual(line, anchor_line(list(facts), roles=("3", "7")))


class TestEndings(unittest.TestCase):
    def end(self, chords, key="C", following=None, loops=False, whole=True) -> str:
        fol = chord_facts(following) if following else None
        return classify_ending([chord_facts(c) for c in chords], key=key, following=fol, loops=loops, whole_section=whole).kind

    def test_cadences_only_when_the_chords_support_them(self) -> None:
        self.assertEqual(self.end(["Dm7", "G7", "C"]), ENDING_AUTHENTIC)
        self.assertEqual(self.end(["F", "C"]), ENDING_PLAGAL)
        self.assertEqual(self.end(["C", "F", "G"]), ENDING_HALF)
        self.assertEqual(self.end(["Dm", "G7", "Am"]), ENDING_DECEPTIVE)
        self.assertEqual(self.end(["Am", "C"]), ENDING_HOME)
        self.assertEqual(self.end(["C#m7b5", "F#7", "Bm"], key="Bm"), ENDING_AUTHENTIC)
        self.assertEqual(self.end(["Gm7", "Gb7", "Fmaj7"], key="F"), ENDING_AUTHENTIC)  # tritone substitute

    def test_slash_chord_functions_drive_endings(self) -> None:
        self.assertEqual(self.end(["Dm7", "F/G", "C"]), ENDING_AUTHENTIC)  # F/G is a suspended V, not IV
        self.assertEqual(self.end(["C", "Am", "F/G"]), ENDING_HALF)
        self.assertEqual(self.end(["C", "G/F", "C/E"]), ENDING_AUTHENTIC)
        self.assertEqual(self.end(["D", "G", "Dsus2"], key="Dm"), "home_note_colour")

    def test_open_looping_and_leading_endings(self) -> None:
        self.assertEqual(self.end(["C", "Am", "F"]), ENDING_OPEN)
        self.assertEqual(self.end(["C", "Am", "F"], loops=True), ENDING_LOOPS)
        self.assertEqual(self.end(["C", "A7"], following="Dm"), ENDING_LEADS_ON)
        self.assertEqual(self.end(["C", "Am"], following="F", whole=False), ENDING_MID)
        self.assertEqual(self.end(["Fmaj7", "Gb7"], key="F", following="Gbmaj7"), ENDING_OPEN)


class TestProfile(unittest.TestCase):
    def test_profile_of_a_split_bar_progression(self) -> None:
        ctx = build_song_coach_context(identity="custom|t", source_kind=SOURCE_CUSTOM, concert_key="G",
                                       concert_sections={"Verse": ["C:2|G:2", "Am", "N.C.", "D", "D"]})
        scope = build_scope(ctx, coach_sections(ctx)[0].section_id)
        p = section_profile(scope, key="G")
        self.assertFalse(p.exact_timing)
        self.assertTrue(p.has_no_chord)
        self.assertEqual(p.changes, 4)
        self.assertEqual(p.ending.kind, ENDING_HALF)

    def test_harmonic_rhythm_classes(self) -> None:
        for bars, expected in ((["C", "C", "G", "G"], "slow"), (["C", "G", "Am", "F"], "steady"), (["C:2|G:2", "Am:2|F:2"], "quick")):
            ctx = build_song_coach_context(identity="custom|t", source_kind=SOURCE_CUSTOM, concert_sections={"A": bars}, concert_key="C")
            scope = build_scope(ctx, "a")
            self.assertEqual(section_profile(scope, key="C").harmonic_rhythm, expected, bars)


if __name__ == "__main__":
    unittest.main()
