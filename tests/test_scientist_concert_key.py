"""The Scientist (Coldplay): stored in the recording's concert key, F major.

The chart used to store ``Bm7 - G - D - Dsus2`` and label the song D minor. Those
are the capo-3 shapes tab sites print, so the catalog was a minor third below the
record: every transposing instrument, the written notation and the backing played
in the wrong key, and the stored "original key" was wrong as well.

Evidence (secondary, no score copied; the tonal centre was the open question):
  * Hooktheory's TheoryTab for the song gives the key as F major and names
    F / Bb / C as the I, IV and V chords.
  * A Pianote lead-sheet lesson gives the core progression as
    Dm7 - Bb - F - Fsus2 and notes that one more chord, C major, arrives only at
    the end. That is this chart, in F.
  * Spytunes numbers the intro/verse in F as Dm7 (vi) | Bb (IV) | F (I) | Fsus2,
    and the chorus as C (V), which is why a vi-start reads as D minor.
  * Chordify transcriptions list Bb / F / Dm / C and name the key F major.
No source found argues for D minor as the tonal centre. The loop merely begins on
vi, the same vi-start ambiguity as All of Me.

Only the key and transposition change here: tempo, sections, bar counts, chord
qualities and slash colours are identical, which is what the pin below proves.
Nothing here is verified by ear.
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

TITLE, ARTIST = "The Scientist", "Coldplay"
PICK = f"{TITLE}\x1f{ARTIST}"
OLD_KEY, NEW_KEY, OLD_REF, NEW_REF = "Dm", "F", "D", "F"
OLD = json.loads(r'''{
 "key": "Dm",
 "bpm": 73,
 "order": [
  "Intro",
  "Verse 1",
  "Chorus 1",
  "N.C. 1",
  "Instrumental 1",
  "Verse 2",
  "Chorus 2",
  "N.C. 2",
  "Instrumental 2",
  "Ending",
  "Final Tag"
 ],
 "sections": {
  "Intro": [
   "Bm7",
   "G",
   "D",
   "Dsus2",
   "Bm7",
   "G",
   "D",
   "Dsus2"
  ],
  "Verse 1": [
   "Bm7",
   "G",
   "D",
   "Dsus2",
   "Bm7",
   "G",
   "D",
   "Dsus2",
   "Bm7",
   "G",
   "D",
   "Dsus2",
   "Bm7",
   "G",
   "D",
   "Dsus2"
  ],
  "Chorus 1": [
   "G",
   "D",
   "Dsus2",
   "A/D",
   "D6/9",
   "A/E",
   "Asus4",
   "A"
  ],
  "N.C. 1": [
   "N.C."
  ],
  "Instrumental 1": [
   "D",
   "G",
   "D",
   "D|Dmaj7",
   "Bm7",
   "G",
   "D",
   "Dsus2"
  ],
  "Verse 2": [
   "Bm7",
   "G",
   "D",
   "Dsus2",
   "Bm7",
   "G",
   "D",
   "Dsus2",
   "Bm7",
   "G",
   "D",
   "Dsus2",
   "Bm7",
   "G",
   "D",
   "Dsus2/C#"
  ],
  "Chorus 2": [
   "G",
   "D",
   "Dsus2",
   "A/D",
   "D6/9",
   "A/E",
   "Asus4",
   "A"
  ],
  "N.C. 2": [
   "N.C."
  ],
  "Instrumental 2": [
   "D",
   "G",
   "D",
   "D"
  ],
  "Ending": [
   "Bm7",
   "G",
   "D",
   "D",
   "Bm7",
   "G",
   "D",
   "D",
   "Bm7",
   "G",
   "D",
   "D",
   "Bm7",
   "G",
   "D",
   "D"
  ],
  "Final Tag": [
   "Bm7",
   "G",
   "D"
  ]
 },
 "chart_versions": {
  "Beginner": {
   "Intro": [
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D"
   ],
   "Verse 1": [
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D"
   ],
   "Chorus 1": [
    "G",
    "D",
    "D",
    "A",
    "D",
    "A",
    "A",
    "A"
   ],
   "N.C. 1": [
    "N.C."
   ],
   "Instrumental 1": [
    "D",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D"
   ],
   "Verse 2": [
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D"
   ],
   "Chorus 2": [
    "G",
    "D",
    "D",
    "A",
    "D",
    "A",
    "A",
    "A"
   ],
   "N.C. 2": [
    "N.C."
   ],
   "Instrumental 2": [
    "D",
    "G",
    "D",
    "D"
   ],
   "Ending": [
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D",
    "Bm",
    "G",
    "D",
    "D"
   ],
   "Final Tag": [
    "Bm",
    "G",
    "D"
   ]
  },
  "Intermediate": {
   "Intro": [
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2"
   ],
   "Verse 1": [
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2"
   ],
   "Chorus 1": [
    "G",
    "D",
    "Dsus2",
    "A/D",
    "D6/9",
    "A/E",
    "Asus4",
    "A"
   ],
   "N.C. 1": [
    "N.C."
   ],
   "Instrumental 1": [
    "D",
    "G",
    "D",
    "D|Dmaj7",
    "Bm7",
    "G",
    "D",
    "Dsus2"
   ],
   "Verse 2": [
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2/C#"
   ],
   "Chorus 2": [
    "G",
    "D",
    "Dsus2",
    "A/D",
    "D6/9",
    "A/E",
    "Asus4",
    "A"
   ],
   "N.C. 2": [
    "N.C."
   ],
   "Instrumental 2": [
    "D",
    "G",
    "D",
    "D"
   ],
   "Ending": [
    "Bm7",
    "G",
    "D",
    "D",
    "Bm7",
    "G",
    "D",
    "D",
    "Bm7",
    "G",
    "D",
    "D",
    "Bm7",
    "G",
    "D",
    "D"
   ],
   "Final Tag": [
    "Bm7",
    "G",
    "D"
   ]
  },
  "Advanced": {
   "Intro": [
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2"
   ],
   "Verse 1": [
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2"
   ],
   "Chorus 1": [
    "G",
    "D",
    "Dsus2",
    "A/D",
    "D6/9",
    "A/E",
    "Asus4",
    "A"
   ],
   "N.C. 1": [
    "N.C."
   ],
   "Instrumental 1": [
    "D",
    "G",
    "D",
    "D|Dmaj7",
    "Bm7",
    "G",
    "D",
    "Dsus2"
   ],
   "Verse 2": [
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2",
    "Bm7",
    "G",
    "D",
    "Dsus2/C#"
   ],
   "Chorus 2": [
    "G",
    "D",
    "Dsus2",
    "A/D",
    "D6/9",
    "A/E",
    "Asus4",
    "A"
   ],
   "N.C. 2": [
    "N.C."
   ],
   "Instrumental 2": [
    "D",
    "G",
    "D",
    "D"
   ],
   "Ending": [
    "Bm7",
    "G",
    "D",
    "D",
    "Bm7",
    "G",
    "D",
    "D",
    "Bm7",
    "G",
    "D",
    "D",
    "Bm7",
    "G",
    "D",
    "D"
   ],
   "Final Tag": [
    "Bm7",
    "G",
    "D"
   ]
  }
 }
}''')


def rec():
    return copy.deepcopy(
        next(r for r in curated_song_records() if r["title"] == TITLE and r["artist"] == ARTIST)
    )


class TestConcertKey(unittest.TestCase):
    def test_key_capo_tempo_and_form(self) -> None:
        r = rec()
        self.assertEqual(r["key"], NEW_KEY)
        ext = r["extensions"]
        self.assertEqual(ext["concert_key"], "F")
        self.assertEqual(ext["guitar_friendly_key"], "D")
        self.assertIn("Capo 3", ext["capo_note"])
        self.assertEqual(ext["default_bpm"], OLD["bpm"])
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(list(r.get("section_order") or r["sections"]), OLD["order"])
        self.assertEqual(
            {n: len(c) for n, c in r["sections"].items()},
            {n: len(c) for n, c in OLD["sections"].items()},
        )

    def test_the_published_progression_is_what_the_chart_plays(self) -> None:
        r = rec()
        # Pianote / Spytunes verse loop, and the V chord that only shows up late.
        self.assertEqual(r["sections"]["Verse 1"][:4], ["Dm7", "Bb", "F", "Fsus2"])
        self.assertEqual(r["sections"]["Final Tag"], ["Dm7", "Bb", "F"])
        self.assertEqual(r["sections"]["Chorus 1"][-1], "C")
        flat = [c for v in r["sections"].values() for c in v]
        self.assertIn("C", flat)
        # no capo-3 shape spelling may survive at any level
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            cells = [c for v in secs.values() for c in v]
            for stale in ("Bm7", "Bm", "Dsus2", "D6/9", "A/D", "A/E", "Asus4", "Dsus2/C#"):
                self.assertNotIn(stale, cells, f"{level}: stale capo spelling {stale}")

    def test_transposed_back_to_the_shapes_it_is_the_old_chart_exactly(self) -> None:
        r = rec()
        self.assertEqual(transpose_sections_dict(r["sections"], NEW_REF, OLD_REF), OLD["sections"])
        for level, secs in OLD["chart_versions"].items():
            self.assertEqual(
                transpose_sections_dict(r["chart_versions"][level], NEW_REF, OLD_REF), secs, level
            )

    def test_every_level_validates_with_unchanged_bar_counts(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, secs = resolve_level_chart(rec(), level)
            order = list(view.get("section_order") or secs)
            self.assertEqual(
                validate_chord_events(sections_dict_to_events({n: secs[n] for n in order})), [], level
            )

    def test_saved_copy_refreshes_with_its_key_user_edits_and_practice_key_untouched(self) -> None:
        new = rec()
        snap = {
            "title": TITLE,
            "artist": ARTIST,
            "pick_key": PICK,
            "key": OLD["key"],
            "sections": copy.deepcopy(OLD["sections"]),
        }
        self.assertEqual(cp.classify_snapshot(snap, new, pick_key=PICK)[0], cp.REFRESH)
        out = cp.reconcile_snapshot(snap, new, pick_key=PICK)
        self.assertEqual((out["key"], out["sections"]), (NEW_KEY, new["sections"]))
        first = next(iter(OLD["sections"]))
        edited_cells = copy.deepcopy(OLD["sections"])
        edited_cells[first] = [edited_cells[first][0]] * len(edited_cells[first])
        kept = cp.reconcile_snapshot(dict(snap, sections=edited_cells), new, pick_key=PICK)
        self.assertEqual(kept["key"], OLD["key"])
        self.assertEqual(kept["sections"], edited_cells)
        session = {"selected_song": copy.deepcopy(snap), "display_key": "C", "concert_key": "C"}
        cp.heal_session_chart_copies(session, new, PICK, where="test")
        self.assertEqual(
            (session["selected_song"]["key"], session["display_key"], session["concert_key"]),
            (NEW_KEY, "C", "C"),
        )

    def test_practice_key_transposition_is_not_doubled(self) -> None:
        r = rec()
        self.assertEqual(
            transpose_sections_dict(r["sections"], NEW_REF, "C"),
            transpose_sections_dict(OLD["sections"], OLD_REF, "C"),
        )


if __name__ == "__main__":
    unittest.main()
