"""Two catalog tempos that made the backing play at the wrong speed.

**Piano Man** stored ``default_bpm=88`` against ``time_signature="3/4"``. The
engine reads default_bpm as the quarter-note pulse (``songs.meter.meter_timing``
gives ``pulses_per_bar=3`` for 3/4), so 88 drove the waltz at roughly half
speed, and the 306-bar Advanced form came out at 10.4 minutes against a 5:39
record. Evidence: Tunebat lists the studio recording at 178 BPM with a 5:39
duration; a Musicnotes listing and Tomplay both give 3/4 and around 170; the
"about 60 BPM" on the piano/vocal edition is the bar pulse (60 bars a minute),
not the quarter note. 306 bars x 3 beats at 178 is 5:09, which is the record
minus its fade, so the form was already right and only the tempo was wrong.

**Billie Jean** carried no ``default_bpm`` at all, so it fell back to the
generic default. Tempo listings agree on ~117 BPM (118 and 125 are the
outliers) and Musicnotes prints the original published key as F# minor, which
the catalog already stored. Its chords are ``user_corrected_reference`` and are
not touched here.

Only ``extensions.default_bpm`` and the prose that quoted the old figure change.
``songs.chart_provenance._CHART_FIELDS`` is ``("sections", "chart_versions",
"section_order")``, so a tempo change cannot reclassify or rewrite a saved
chart, and no PRIOR_REVISIONS entry is needed. Nothing here is checked by ear.
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing


def rec(title, artist):
    return copy.deepcopy(
        next(r for r in curated_song_records() if r["title"] == title and r["artist"] == artist)
    )


def advanced_seconds(r):
    ext = r["extensions"]
    sig = r.get("time_signature") or ext.get("time_signature") or "4/4"
    _view, secs = resolve_level_chart(copy.deepcopy(r), "Advanced")
    bars = sum(len(v) for v in secs.values())
    return bars, bars * meter_timing(ext["default_bpm"], sig).bar_sec


class PianoManTempoTests(unittest.TestCase):
    def test_quarter_note_tempo_not_the_half_speed_value(self) -> None:
        r = rec("Piano Man", "Billy Joel")
        ext = r["extensions"]
        self.assertEqual(ext["time_signature"], "3/4")
        self.assertEqual(ext["default_bpm"], 178)
        self.assertNotEqual(ext["default_bpm"], 88)
        self.assertIn("178", ext["arrangement_notes"])
        self.assertNotIn("~88 BPM", ext["arrangement_notes"])

    def test_the_engine_reads_three_pulses_a_bar_for_this_song(self) -> None:
        # the whole point: 3/4 is not 4 beats a bar, so the tempo units matter
        self.assertEqual(meter_timing(178, "3/4").pulses_per_bar, 3)

    def test_advanced_form_now_lands_near_the_recording(self) -> None:
        bars, secs = advanced_seconds(rec("Piano Man", "Billy Joel"))
        self.assertEqual(bars, 306, "form must not change with the tempo")
        # 5:39 recording; the chart stops short of the fade, so allow 5:00-5:40
        self.assertGreater(secs, 300)
        self.assertLess(secs, 340)

    def test_form_and_key_are_untouched(self) -> None:
        r = rec("Piano Man", "Billy Joel")
        self.assertEqual(r["key"], "C")
        self.assertEqual(len(r.get("section_order") or r["sections"]), 21)


class BillieJeanTempoTests(unittest.TestCase):
    def test_tempo_is_present_and_is_117(self) -> None:
        ext = rec("Billie Jean", "Michael Jackson")["extensions"]
        self.assertEqual(ext["default_bpm"], 117)

    def test_key_meter_and_user_corrected_chords_are_untouched(self) -> None:
        r = rec("Billie Jean", "Michael Jackson")
        self.assertEqual(r["key"], "F#m")
        self.assertEqual(r.get("chart_status"), "user_corrected_reference")
        # 4/4 is the catalog default and what the notes assert
        sig = r.get("time_signature") or r["extensions"].get("time_signature") or "4/4"
        self.assertEqual(meter_timing(117, sig).pulses_per_bar, 4)
        _view, secs = resolve_level_chart(r, "Advanced")
        self.assertEqual(secs["Intro"], ["F#m9", "G#m7", "Amaj7", "G#m7"] * 2)
        self.assertEqual(secs["Bridge"][-1], "C#9")

    def test_skeleton_length_is_documented_not_silently_short(self) -> None:
        r = rec("Billie Jean", "Michael Jackson")
        bars, secs = advanced_seconds(r)
        self.assertEqual(bars, 86)
        self.assertLess(secs, 294)  # 4:54 record; the chart is a rehearsal skeleton
        self.assertIn("rehearsal skeleton", r["extensions"]["arrangement_notes"])


if __name__ == "__main__":
    unittest.main()
