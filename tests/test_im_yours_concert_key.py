"""I'm Yours (Jason Mraz): stored in the recording's concert key, not as guitar capo shapes.

Evidence (secondary, no score copied): Secondary sources: several chord/tab sites list the recording in B major, played as G-D-Em-C shapes with a capo on fret 4 (Heartwood capo-4 chart, andyguitar, Ultimate-Guitar listings, ukulele sites); one dissenting low-quality guide says C.
Only the key/transposition changes: tempo, sections, bar counts and chord qualities are unchanged.  Nothing here is
verified by ear.
"""
from __future__ import annotations

import copy
import json
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from music_theory import transpose_sections_dict
from song_catalog.catalog import curated_song_records
from songs import chart_provenance as cp

TITLE, ARTIST = "I'm Yours", "Jason Mraz"
PICK = f"{TITLE}\x1f{ARTIST}"
OLD_KEY, NEW_KEY, OLD_REF, NEW_REF = "G", "B", "G", "B"
OLD = json.loads(r'''{
 "key": "G",
 "bpm": 75,
 "order": [
  "Intro",
  "Verse 1",
  "Chorus 1",
  "Verse 2",
  "Chorus 2",
  "Bridge",
  "Verse 3",
  "Final Chorus / Outro Build",
  "Outro"
 ],
 "sections": {
  "Intro": [
   "G",
   "D",
   "Em",
   "C"
  ],
  "Verse 1": [
   "G",
   "D",
   "Em",
   "C",
   "G",
   "D",
   "Em",
   "C"
  ],
  "Chorus 1": [
   "G",
   "D",
   "Em",
   "C",
   "G",
   "D",
   "Em",
   "C"
  ],
  "Verse 2": [
   "G",
   "D",
   "Em",
   "C",
   "G",
   "D",
   "Em",
   "C",
   "A7"
  ],
  "Chorus 2": [
   "G",
   "D|Dsus4",
   "Em",
   "C",
   "G",
   "D",
   "Em",
   "C"
  ],
  "Bridge": [
   "G",
   "D",
   "Em",
   "D",
   "C",
   "A7",
   "G|D/F#",
   "Em|D",
   "C",
   "A7"
  ],
  "Verse 3": [
   "G",
   "D",
   "Em",
   "C",
   "G",
   "D",
   "Em",
   "C"
  ],
  "Final Chorus / Outro Build": [
   "G",
   "D|Dsus4",
   "Em",
   "C",
   "G",
   "D",
   "Em",
   "C",
   "A7"
  ],
  "Outro": [
   "N.C.",
   "G",
   "D",
   "Em",
   "C",
   "G",
   "D",
   "Em",
   "C"
  ]
 },
 "chart_versions": {
  "Beginner": {
   "Intro": [
    "G",
    "D",
    "Em",
    "C"
   ],
   "Verse 1": [
    "G",
    "D",
    "Em",
    "C"
   ],
   "Chorus 1": [
    "G",
    "D",
    "Em",
    "C"
   ],
   "Verse 2": [
    "G",
    "D",
    "Em",
    "C",
    "A7"
   ],
   "Chorus 2": [
    "G",
    "D|Dsus4",
    "Em",
    "C"
   ],
   "Bridge": [
    "G",
    "D",
    "Em",
    "C",
    "A7",
    "G|D/F#",
    "Em|D",
    "C",
    "A7"
   ],
   "Verse 3": [
    "G",
    "D",
    "Em",
    "C"
   ],
   "Final Chorus / Outro Build": [
    "G",
    "D|Dsus4",
    "Em",
    "C",
    "A7"
   ],
   "Outro": [
    "N.C.",
    "G",
    "D",
    "Em",
    "C"
   ]
  },
  "Intermediate": {
   "Intro": [
    "G",
    "D",
    "Em",
    "C"
   ],
   "Verse 1": [
    "G",
    "D",
    "Em",
    "C",
    "G",
    "D",
    "Em",
    "C"
   ],
   "Chorus 1": [
    "G",
    "D",
    "Em",
    "C",
    "G",
    "D",
    "Em",
    "C"
   ],
   "Verse 2": [
    "G",
    "D",
    "Em",
    "C",
    "G",
    "D",
    "Em",
    "C",
    "A7"
   ],
   "Chorus 2": [
    "G",
    "D|Dsus4",
    "Em",
    "C",
    "G",
    "D",
    "Em",
    "C"
   ],
   "Bridge": [
    "G",
    "D",
    "Em",
    "D",
    "C",
    "A7",
    "G|D/F#",
    "Em|D",
    "C",
    "A7"
   ],
   "Verse 3": [
    "G",
    "D",
    "Em",
    "C",
    "G",
    "D",
    "Em",
    "C"
   ],
   "Final Chorus / Outro Build": [
    "G",
    "D|Dsus4",
    "Em",
    "C",
    "G",
    "D",
    "Em",
    "C",
    "A7"
   ],
   "Outro": [
    "N.C.",
    "G",
    "D",
    "Em",
    "C",
    "G",
    "D",
    "Em",
    "C"
   ]
  },
  "Advanced": {
   "Intro": [
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9"
   ],
   "Verse 1": [
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9",
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9"
   ],
   "Chorus 1": [
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9",
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9"
   ],
   "Verse 2": [
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9",
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9",
    "A7sus4"
   ],
   "Chorus 2": [
    "Gmaj7",
    "D|Dsus2",
    "Em7",
    "Cadd9",
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9"
   ],
   "Bridge": [
    "Gmaj7",
    "D",
    "Em7",
    "D",
    "Cadd9",
    "A7sus4",
    "Gmaj7|D/F#",
    "Em7|D",
    "Cadd9",
    "A7sus4"
   ],
   "Verse 3": [
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9",
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9"
   ],
   "Final Chorus / Outro Build": [
    "Gmaj7",
    "D|Dsus2",
    "Em7",
    "Cadd9",
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9",
    "A7sus4"
   ],
   "Outro": [
    "N.Cadd9.",
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9",
    "Gmaj7",
    "D",
    "Em7",
    "Cadd9"
   ]
  }
 }
}''')


def rec():
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == TITLE and r["artist"] == ARTIST))


class TestConcertKey(unittest.TestCase):
    def test_key_capo_tempo_and_form(self) -> None:
        r = rec()
        self.assertEqual(r["key"], NEW_KEY)
        ext = r["extensions"]
        self.assertIn("Capo 4", ext["capo_note"])
        self.assertEqual(ext["default_bpm"], OLD["bpm"])
        self.assertEqual(list(r.get("section_order") or r["sections"]), OLD["order"])
        self.assertEqual({n: len(c) for n, c in r["sections"].items()}, {n: len(c) for n, c in OLD["sections"].items()})

    def test_transposed_back_to_the_shapes_it_is_the_old_chart_exactly(self) -> None:
        r = rec()
        back = transpose_sections_dict(r["sections"], NEW_REF, OLD_REF)
        self.assertEqual(back, OLD["sections"])
        for level, secs in OLD["chart_versions"].items():
            self.assertEqual(transpose_sections_dict(r["chart_versions"][level], NEW_REF, OLD_REF), secs, level)

    def test_every_level_validates_with_unchanged_bar_counts(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, secs = resolve_level_chart(rec(), level)
            order = list(view.get("section_order") or secs)
            self.assertEqual(validate_chord_events(sections_dict_to_events({n: secs[n] for n in order})), [], level)

    def test_saved_copy_refreshes_with_its_key_user_edits_and_practice_key_untouched(self) -> None:
        new = rec()
        snap = {"title": TITLE, "artist": ARTIST, "pick_key": PICK, "key": OLD["key"], "sections": copy.deepcopy(OLD["sections"])}
        self.assertEqual(cp.classify_snapshot(snap, new, pick_key=PICK)[0], cp.REFRESH)
        out = cp.reconcile_snapshot(snap, new, pick_key=PICK)
        self.assertEqual((out["key"], out["sections"]), (NEW_KEY, new["sections"]))
        first = next(iter(OLD["sections"]))
        edited_cells = copy.deepcopy(OLD["sections"])
        edited_cells[first] = [edited_cells[first][0]] * len(edited_cells[first])
        edited = dict(snap, sections=edited_cells)
        kept = cp.reconcile_snapshot(edited, new, pick_key=PICK)
        self.assertEqual(kept["key"], OLD["key"])
        self.assertEqual(kept["sections"], edited_cells)
        session = {"selected_song": copy.deepcopy(snap), "display_key": "C", "concert_key": "C"}
        cp.heal_session_chart_copies(session, new, PICK, where="test")
        self.assertEqual((session["selected_song"]["key"], session["display_key"], session["concert_key"]), (NEW_KEY, "C", "C"))

    def test_practice_key_transposition_is_not_doubled(self) -> None:
        r = rec()
        once = transpose_sections_dict(r["sections"], NEW_REF, "C")
        twice_from_old = transpose_sections_dict(OLD["sections"], OLD_REF, "C")
        self.assertEqual(once, twice_from_old)

    def test_advanced_backing_length(self) -> None:
        import io
        import wave

        from backing_audio import generate_backing_track
        from songs.meter import meter_timing

        r = rec()
        view, secs = resolve_level_chart(r, "Advanced")
        chords = [c for n in view["section_order"] for c in secs[n]]
        bpm = OLD["bpm"]
        wav = generate_backing_track(chords, bpm=bpm, loops=1, style="Pop groove", level="Advanced", song_title=TITLE, song_artist=ARTIST)
        with wave.open(io.BytesIO(wav)) as w:
            dur = w.getnframes() / w.getframerate()
        self.assertAlmostEqual(dur, len(chords) * meter_timing(bpm, "4/4").bar_sec + 1.0, delta=0.3)


if __name__ == "__main__":
    unittest.main()
