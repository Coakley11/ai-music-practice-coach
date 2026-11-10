"""Does the ABC read back as the music it was built from?

Every other piano test reads the token this app wrote. abcjs reads the token the ABC
standard defines, and the two disagreed: ``music_theory.abc_pitch_for_spelled_note``
writes middle C as ``c``, which abcjs plays as the C above it. Fifty passing tests and a
browser screenshot both missed it, because a staff drawn an octave high still looks like
a staff.

So the decoder here is deliberately a *second implementation* - the ABC standard written
out, not the app's speller called again - pinned to what real abcjs 6.4.4 was measured to
do: ``C,`` is 48, ``C`` is 60, ``c`` is 72, and under ``K:G`` a bare ``f`` sounds F#.
``scripts/_proof_piano_grand_staff_abcjs.py`` runs the same comparison through abcjs
itself; this runs it in milliseconds.

The second class covers the other thing a reader sees above the staff: the chord symbols.
"""

from __future__ import annotations

import re
import unittest

from piano_grand_staff import (
    CHORD_LABEL_SEPARATOR,
    _bar_chord_labels,
    grand_staff_abc,
    hands_for_scale,
)

MAJOR_SCALE_PCS = [0, 2, 4, 5, 7, 9, 11]


class AbcDecoder:
    """The ABC pitch standard, written out once so the tests can read back what they wrote."""

    LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    SHARP_ORDER = "FCGDAEB"
    FLAT_ORDER = "BEADGCF"
    MAJOR_SHARPS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7}
    MAJOR_FLATS = {"F": 1, "Bb": 2, "Eb": 3, "Ab": 4, "Db": 5, "Gb": 6, "Cb": 7}
    RELATIVE_MAJOR = {
        "A": "C", "E": "G", "B": "D", "F#": "A", "C#": "E", "G#": "B",
        "D": "F", "G": "Bb", "C": "Eb", "F": "Ab", "Bb": "Db", "Eb": "Gb",
    }

    @classmethod
    def key_alterations(cls, k_field: str) -> dict:
        key = str(k_field or "C").strip()
        if key.endswith("m"):
            key = cls.RELATIVE_MAJOR.get(key[:-1], "C")
        sharps = cls.MAJOR_SHARPS.get(key)
        if sharps is not None:
            return {letter: 1 for letter in cls.SHARP_ORDER[:sharps]}
        return {letter: -1 for letter in cls.FLAT_ORDER[: cls.MAJOR_FLATS.get(key, 0)]}

    @classmethod
    def decode(cls, token: str, k_field: str) -> int:
        """MIDI number for one ABC pitch token, read the way abcjs reads it."""
        alter: int | None = None
        i = 0
        while i < len(token) and token[i] in "^_=":
            if token[i] == "=":
                alter = 0
            else:
                alter = (alter or 0) + (1 if token[i] == "^" else -1)
            i += 1
        letter = token[i]
        i += 1
        octave = 4 if letter.isupper() else 5
        while i < len(token) and token[i] in ",'":
            octave += 1 if token[i] == "'" else -1
            i += 1
        upper = letter.upper()
        if alter is None:
            alter = cls.key_alterations(k_field).get(upper, 0)
        return 12 * (octave + 1) + cls.LETTER_PC[upper] + alter

    @staticmethod
    def tokens(staff_line: str) -> list:
        """One voice's pitch tokens, with lengths, bar lines and annotations removed."""
        body = re.sub(r'"[^"]*"', " ", staff_line)
        body = body.replace("|", " ").replace("[", " ").replace("]", " ")
        return re.findall(r"[\^_=]*[A-Ga-g][,']*", body)

    @classmethod
    def pitches_of(cls, abc: str) -> list:
        k_field = abc.split("K:", 1)[1].split("\n", 1)[0].strip()
        treble = abc.split("V:1\n", 1)[1].split("\nV:2", 1)[0]
        bass = abc.split("V:2\n", 1)[1]
        return sorted(
            cls.decode(t, k_field) for t in cls.tokens(treble) + cls.tokens(bass)
        )


class TheDecoderMatchesRealAbcjs(unittest.TestCase):
    """Guards the guard. Each of these came off a live abcjs 6.4.4 run."""

    def test_octave_marks(self):
        self.assertEqual(AbcDecoder.decode("C,", "C"), 48)
        self.assertEqual(AbcDecoder.decode("C", "C"), 60)
        self.assertEqual(AbcDecoder.decode("c", "C"), 72)
        self.assertEqual(AbcDecoder.decode("c'", "C"), 84)

    def test_the_key_signature_applies_to_a_bare_letter(self):
        self.assertEqual(AbcDecoder.decode("f", "G"), 78)    # K:G sharpens it
        self.assertEqual(AbcDecoder.decode("=f", "G"), 77)   # unless told otherwise
        self.assertEqual(AbcDecoder.decode("b", "Bb"), 82)   # K:Bb flattens it
        self.assertEqual(AbcDecoder.decode("b", "Am"), 83)   # A minor carries nothing


class TheAbcReadsBackAsThePitchItWasGiven(unittest.TestCase):
    def test_every_pitch_in_the_exercise_span_reads_back_exactly(self):
        for key in ("C", "G", "Bb", "Am", "F#", "Eb", "Dm", "Ab", "D", "F"):
            for midi in range(36, 85):
                with self.subTest(key=key, midi=midi):
                    abc = grand_staff_abc([[[midi]]], key=key)
                    self.assertEqual(AbcDecoder.pitches_of(abc), [midi])

    def test_both_hands_of_a_voicing_read_back(self):
        for key in ("C", "G", "Bb", "Am", "Eb"):
            for voicing in ([48, 60, 64, 67], [36, 55, 59, 65, 72], [43, 47, 62, 77]):
                with self.subTest(key=key, voicing=voicing):
                    abc = grand_staff_abc([[list(voicing)]], key=key)
                    self.assertEqual(AbcDecoder.pitches_of(abc), sorted(voicing))

    def test_a_whole_scale_reads_back_in_both_hands(self):
        line = [60, 62, 64, 65, 67, 69, 71, 72]
        for motion in ("parallel", "contrary", "separate"):
            for key in ("C", "G", "Bb", "Am"):
                with self.subTest(motion=motion, key=key):
                    bars = [hands_for_scale(line, motion=motion, scale_pcs=MAJOR_SCALE_PCS)]
                    want = sorted(m for voicing in bars[0] for m in voicing)
                    self.assertEqual(
                        AbcDecoder.pitches_of(grand_staff_abc(bars, key=key)), want
                    )

    def test_middle_c_is_not_written_an_octave_high(self):
        """The regression itself, stated plainly."""
        self.assertEqual(AbcDecoder.pitches_of(grand_staff_abc([[[60]]], key="C")), [60])


class TheChordSymbolsAreChordSymbols(unittest.TestCase):
    """A chart cell carries timing; a score carries chord names.

    ``"Em:3.5|G:0.5p"`` is one bar of Em with a G pushed onto the last half beat. Printed
    verbatim above the staff it is unreadable, and ``chord_subdivisions.chord_names_label``
    states outright that the weight and push markers must never be shown on a score.
    """

    LINE = [60, 62, 64, 65, 67, 69, 71, 72]

    def abc_for(self, chords, line=None):
        bars = [hands_for_scale(line or self.LINE, motion="parallel")] * len(chords)
        return grand_staff_abc(bars, key="C", chords=chords)

    def annotations(self, abc):
        return re.findall(r'"([^"]*)"', abc)

    def test_no_timing_metadata_reaches_the_staff(self):
        for token in ("Em:3.5|G:0.5p", "C:2|G:2", "Fmaj7|Am7|C/D", "C:4",
                      "Dm7b5:1|G7alt:3", "Am7.hit"):
            with self.subTest(token=token):
                for label in self.annotations(self.abc_for([token])):
                    self.assertNotIn(":", label)
                    self.assertNotIn("|", label)
                    self.assertNotIn(".hit", label)

    def test_both_harmonies_of_a_split_measure_are_printed(self):
        self.assertEqual(self.annotations(self.abc_for(["Em:3.5|G:0.5p"])), ["Em", "G"])
        self.assertEqual(self.annotations(self.abc_for(["C:2|G:2"])), ["C", "G"])
        self.assertEqual(
            self.annotations(self.abc_for(["Fmaj7|Am7|C/D"])), ["Fmaj7", "Am7", "C/D"]
        )

    def test_each_harmony_sits_on_the_note_it_starts_on(self):
        """Timing is preserved by *placing* the symbol, never by printing the weight."""
        self.assertEqual(
            _bar_chord_labels("C:2|G:2", 8, 4.0), ["C", "", "", "", "G", "", "", ""]
        )
        self.assertEqual(
            _bar_chord_labels("Em:3.5|G:0.5p", 8, 4.0),
            ["Em", "", "", "", "", "", "", "G"],
        )
        self.assertEqual(_bar_chord_labels("C:1|Am:3", 4, 4.0), ["C", "Am", "", ""])

    def test_a_plain_chord_is_printed_once_and_unchanged(self):
        self.assertEqual(self.annotations(self.abc_for(["Cmaj7"])), ["Cmaj7"])
        self.assertEqual(self.annotations(self.abc_for(["C7alt"])), ["C7alt"])
        self.assertEqual(self.annotations(self.abc_for(["F#m7b5"])), ["F#m7b5"])

    def test_harmonies_too_close_to_separate_are_joined_not_dropped(self):
        got = _bar_chord_labels("C:0.5|G:0.25|Am:3.25", 4, 4.0)
        self.assertEqual(got[0], CHORD_LABEL_SEPARATOR.join(["C", "G", "Am"]))

    def test_an_empty_or_missing_chord_annotates_nothing(self):
        self.assertEqual(_bar_chord_labels("", 4, 4.0), [""] * 4)
        self.assertEqual(_bar_chord_labels(None, 4, 4.0), [""] * 4)
        self.assertEqual(self.annotations(grand_staff_abc([[[60]]], key="C")), [])

    def test_the_chart_token_itself_is_never_modified(self):
        """This module reads the chart; it must not rewrite it."""
        chords = ["Em:3.5|G:0.5p", "C:2|G:2"]
        before = list(chords)
        self.abc_for(chords)
        self.assertEqual(chords, before)

    def test_the_symbol_is_never_printed_on_the_bass_staff(self):
        abc = self.abc_for(["Em:3.5|G:0.5p"])
        self.assertEqual(self.annotations(abc.split("V:2\n", 1)[1]), [])


if __name__ == "__main__":
    unittest.main()
