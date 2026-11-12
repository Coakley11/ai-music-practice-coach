"""Heal The World: D/E is the right chord; its FINGERING was an A chord.

The catalog stores ``D/E`` in 66 chart cells across the three levels, and an
earlier audit flagged that as suspicious because the guitar fingering beside it
looked like an A chord. That inference had it backwards. D/E is correct and the
tablature was wrong.

**D/E is right.** Three independent published charts give D/E in exactly the
places ours does - ledutu.com (which also prints the fingering), chordsbase.com
and guitartabsexplorer.com - and all of them resolve it to A, as ours does. It
is also the only reading that makes harmonic sense: the song is in A, the verse
runs A - Bm7 - C#m7 - D/E, and D/E is IV over V, the suspended dominant that
drives back to the tonic. Read as an A chord the phrase would simply return to
the tonic in second inversion and lose that motion.

**The fingering was wrong.** ``"002220"`` sounds E-A-E-A-C#-E: an A major triad
over an E bass, i.e. A/E. It carries a C# and contains neither D nor F#. The
error mechanism is visible in the data - the song's A chord is ``"x02220"``, so
someone took the A shape, added the open low E for the bass, and labelled the
result D/E. It should have been the *D* shape over an E bass.

It is now ``"022232"``, the voicing the ledutu transcription prints:
E-B-E-A-D-F#. That adds B, the fifth of the E bass, so it sounds the full
E11 / E9sus4 colour; the engine's comp stays D-F#-A over E, the same chord with
the B left to the bass register.

**Nothing else changed, and nothing could.** The backing was already correct -
``bass_note("D/E")`` is E and ``chord_notes("D/E")`` is D-F#-A - so this fix
produces no audible change to playback; it corrects what a guitarist is shown.
``guitar_tabs`` is not one of ``chart_provenance._CHART_FIELDS``, so the change
cannot reclassify, refresh or overwrite a saved chart, and both chart
fingerprints are byte-identical to the previous revision. No chart cell, key,
tempo or level was touched.

Two further fingering mismatches in this same song were found by the same audit
and are deliberately NOT changed here, pending their own evidence:
``Bm7 = "x24202"`` omits the third (D), and ``F#/A# = "x476xx"`` sounds
C#-A-C# over a C# bass, which is not an F#/A# at all.

Not checked by ear.
"""
from __future__ import annotations

import copy
import unittest

from backing_audio import bass_note, chord_notes
from chart_level_arrangement import resolve_level_chart
from chord_events import section_chord_list_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records

TITLE = "Heal The World"
PC = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
OPEN = [40, 45, 50, 55, 59, 64]          # E2 A2 D3 G3 B3 E4, standard tuning


def sounding(tab):
    """The pitch classes a fingering actually sounds, low string to high."""
    out = []
    for i, ch in enumerate(str(tab)):
        if ch in "xX":
            continue
        out.append(OPEN[i] + int(ch, 16))
    return [PC[n % 12] for n in out]


def rec():
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == TITLE))


class TheStoredFingeringWasAnAChord(unittest.TestCase):
    def test_the_old_shape_sounded_a_major_over_e(self) -> None:
        """Documents the defect: 002220 is A/E, not D/E."""
        old = sounding("002220")
        self.assertEqual(old, ["E", "A", "E", "A", "C#", "E"])
        self.assertEqual(set(old), {"A", "C#", "E"})      # an A major triad
        self.assertNotIn("D", old)
        self.assertNotIn("F#", old)
        self.assertIn("C#", old, "the C# is what made it an A chord")

    def test_it_was_the_songs_a_shape_with_a_low_e_added(self) -> None:
        """The error mechanism, still visible in the data."""
        self.assertEqual(rec()["guitar_tabs"]["A"], "x02220")
        self.assertEqual(sounding("x02220"), ["A", "E", "A", "C#", "E"])
        # same fretting, with the muted 6th string opened
        self.assertEqual(set(sounding("002220")), set(sounding("x02220")))


class TheCorrectedFingeringIsADOverE(unittest.TestCase):
    def test_the_stored_shape_is_the_published_voicing(self) -> None:
        self.assertEqual(rec()["guitar_tabs"]["D/E"], "022232")

    def test_it_sounds_d_f_sharp_and_a_over_an_e_bass(self) -> None:
        got = sounding("022232")
        self.assertEqual(got, ["E", "B", "E", "A", "D", "F#"])
        self.assertEqual(got[0], "E", "the lowest string must give the E bass")
        for need in ("D", "F#", "A"):
            self.assertIn(need, got, f"D/E must contain {need}")
        self.assertNotIn("C#", got, "a C# would make it an A chord again")

    def test_the_added_b_is_the_fifth_of_the_bass_not_a_foreign_note(self) -> None:
        extra = set(sounding("022232")) - {"D", "F#", "A", "E"}
        self.assertEqual(extra, {"B"})
        # B is the fifth above the E bass: E + 7 semitones
        self.assertEqual(PC[(PC.index("E") + 7) % 12], "B")


class TheBackingWasAlreadyRight(unittest.TestCase):
    """So this fix changes what is shown, not what is heard."""

    def test_the_bass_generator_plays_e(self) -> None:
        self.assertEqual(PC[bass_note("D/E") % 12], "E")

    def test_the_accompaniment_keeps_d_f_sharp_and_a(self) -> None:
        comp = [PC[n % 12] for n in chord_notes("D/E")]
        self.assertEqual(comp, ["D", "F#", "A"])

    def test_d_over_e_is_not_voiced_as_an_a_chord(self) -> None:
        de = {PC[n % 12] for n in chord_notes("D/E")}
        ae = {PC[n % 12] for n in chord_notes("A/E")}
        self.assertNotEqual(de, ae)
        self.assertNotIn("C#", de)
        self.assertIn("C#", ae)

    def test_the_bass_is_the_slash_note_not_the_root(self) -> None:
        self.assertNotEqual(bass_note("D/E") % 12, bass_note("D") % 12)
        self.assertEqual(bass_note("D/E") % 12, PC.index("E"))


class TheHarmonyAndChartAreUntouched(unittest.TestCase):
    def test_the_verse_is_still_one_four_over_five_in_a(self) -> None:
        r = rec()
        self.assertEqual(r["key"], "A")
        self.assertEqual(r["sections"]["Verse 1"][:4], ["A", "Bm7", "C#m7", "D/E"])

    def test_inside_a_section_d_over_e_always_resolves_to_a(self) -> None:
        """The suspended dominant resolves, which is why it is D/E and not A.

        Stated per section rather than across the whole chart: inside a section
        D/E is followed by A, or held as a second bar of D/E, and by nothing
        else. Across a section boundary it hands over to whatever the next
        section opens on, which is a transition rather than a failed
        resolution - see the test below for those.
        """
        _v, adv = resolve_level_chart(rec(), "Advanced")
        seen = 0
        for name, cells in adv.items():
            flat = [p.split(":")[0] for c in cells for p in str(c).split("|")]
            for i, c in enumerate(flat[:-1]):
                if c != "D/E":
                    continue
                seen += 1
                self.assertIn(flat[i + 1], ("A", "D/E"),
                              f"{name} bar {i + 1}: D/E went to {flat[i + 1]!r}")
        self.assertGreaterEqual(seen, 15, "the chart should be full of D/E")

    def test_the_section_boundary_handovers_are_the_documented_ones(self) -> None:
        """A D/E at the end of a section leads into the next section's opening."""
        _v, adv = resolve_level_chart(rec(), "Advanced")
        order = [n for n in (rec().get("section_order") or adv) if n in adv]
        handovers = {}
        for a, b in zip(order, order[1:]):
            last = [p.split(":")[0] for p in str(adv[a][-1]).split("|")][-1]
            first = [p.split(":")[0] for p in str(adv[b][0]).split("|")][0]
            if last == "D/E":
                handovers[(a, b)] = first
        self.assertEqual(
            handovers,
            {("Verse 1", "Pre-Chorus 1"): "Bm7",
             ("Pre-Chorus 1", "Chorus 1"): "A",
             ("Chorus 1", "Verse 2"): "A",
             ("Verse 2", "Pre-Chorus 2"): "Bm7",
             ("Pre-Chorus 2", "Chorus 2"): "A",
             ("Chorus 2", "Bridge"): "G",
             ("Bridge", "Chorus 3"): "A",
             ("Chorus 3", "Modulation 1"): "B"},
        )

    def test_the_cell_counts_are_unchanged_at_every_level(self) -> None:
        want = {"Beginner": (66, 16), "Intermediate": (122, 22), "Advanced": (145, 28)}
        for level, (bars, de) in want.items():
            _v, secs = resolve_level_chart(rec(), level)
            self.assertEqual(sum(len(v) for v in secs.values()), bars, level)
            got = sum(1 for v in secs.values() for c in v
                      for p in str(c).split("|") if p.split(":")[0] == "D/E")
            self.assertEqual(got, de, f"{level}: D/E cell count changed")

    def test_every_level_still_validates(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, cells in secs.items():
                ev = section_chord_list_to_events(name, cells, time_signature="4/4")
                self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [],
                                 f"{level} {name}")

    def test_a_fingering_change_cannot_touch_a_saved_chart(self) -> None:
        """guitar_tabs is not part of what provenance calls 'the chart'."""
        from songs.chart_provenance import _CHART_FIELDS
        self.assertNotIn("guitar_tabs", _CHART_FIELDS)

    def test_the_chart_fingerprint_is_the_one_already_in_the_catalog(self) -> None:
        """Pinned so a later edit cannot change the chart under cover of a tab fix."""
        from songs.chart_provenance import chart_fingerprint, versions_fingerprint
        r = rec()
        self.assertEqual(chart_fingerprint(r["sections"]), "1c69a52e60a9fafd")
        self.assertEqual(versions_fingerprint(r.get("chart_versions")),
                         "09b5df48d3a65aa6")


class TransposingKeepsTheSlashChord(unittest.TestCase):
    def test_the_slash_bass_transposes_with_the_chord(self) -> None:
        from music_theory import semitone_distance, transpose_chord
        for to, want in (("C", "F/G"), ("Bb", "Eb/F"), ("F#", "B/C#")):
            got = transpose_chord("D/E", semitone_distance("A", to), reference_key=to)
            self.assertEqual(got, want, f"A -> {to}")

    def test_it_stays_four_over_five_in_the_new_key(self) -> None:
        from music_theory import semitone_distance, transpose_sections_dict
        out = transpose_sections_dict({"V": ["A", "Bm7", "C#m7", "D/E"]}, "A", "C")
        self.assertEqual(out["V"], ["C", "Dm7", "Em7", "F/G"])

    def test_a_practice_key_round_trip_loses_nothing(self) -> None:
        from music_theory import transpose_sections_dict
        start = {"V": ["A", "Bm7", "C#m7", "D/E"]}
        there = transpose_sections_dict(start, "A", "C")
        self.assertEqual(transpose_sections_dict(there, "C", "A"), start)


class TheTwoOtherMismatchesAreRecordedNotFixed(unittest.TestCase):
    """Found by the same audit; left alone pending their own evidence."""

    def test_bm7_still_omits_its_third(self) -> None:
        got = sounding(rec()["guitar_tabs"]["Bm7"])
        self.assertEqual(got, ["B", "F#", "A", "B", "F#"])
        self.assertNotIn("D", got, "if this is ever fixed, update this test")

    def test_f_sharp_over_a_sharp_is_still_wrong(self) -> None:
        got = sounding(rec()["guitar_tabs"]["F#/A#"])
        self.assertEqual(got, ["C#", "A", "C#"])
        self.assertNotIn("F#", got)
        self.assertNotIn("Bb", got)   # A# spelled Bb


if __name__ == "__main__":
    unittest.main()
