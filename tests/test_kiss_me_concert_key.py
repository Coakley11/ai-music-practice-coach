"""Kiss Me (Sixpence None the Richer): stored in the recording's concert key, Eb major.

The chart stored open D shapes - D, Dmaj7, D7, G, Em, A, Bm - and labelled the
song D major. The reference table's own comment called it the "written key D",
which it is: those are the capo-1 shapes every tab site prints. So the catalog
sat a semitone below the record, and every transposing instrument, the written
notation and the backing played in the wrong key.

Evidence (secondary, no score copied):
  * Wikipedia's infobox for the song gives Eb major.
  * The Musicnotes sheet listing also gives Eb major.
  * An AcousticBrainz estimate for the track reports D# major at 85% confidence,
    the same pitch under a different spelling.
Transposing the stored D shapes up a semitone gives Eb / Ebmaj7 / Eb7 / Ab / Fm
/ Bb / Cm - I, Imaj7, I7, IV, ii, V and vi of Eb major - so the shapes are a
capo-1 reading, not the sounding key.

Only the key and the spelling change here: tempo (100), meter, sections, bar
counts and chord qualities are identical, which the pin below proves.

The FORM was corrected separately, in W21: the chart had been written at
half-bar granularity, so Advanced ran 176 bars = 7:02 at 100 BPM against a 3:30
album version. It is now 88 bars = 3:31. ``OLD`` below is kept as the genuine
pre-correction snapshot, because the saved-chart test needs a chart a user
could actually have stored; ``D_SHAPES`` is the *current* chart in its D
shapes, and the round-trip tests use that. Nothing here is checked by ear.
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

TITLE, ARTIST = "Kiss Me", "Sixpence None the Richer"
PICK = f"{TITLE}\x1f{ARTIST}"
OLD_KEY, NEW_KEY, OLD_REF, NEW_REF = "D", "Eb", "D", "Eb"
OLD = json.loads(r'''{
 "title": "Kiss Me",
 "artist": "Sixpence None the Richer",
 "key": "D",
 "bpm": 100,
 "order": [
  "Intro",
  "Verse 1",
  "Chorus 1",
  "Interlude",
  "Verse 2",
  "Chorus 2",
  "Harmonica / Accordion",
  "Guitar Section",
  "Chorus 3",
  "Outro"
 ],
 "sections": {
  "Intro": [
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7"
  ],
  "Verse 1": [
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "G",
   "G"
  ],
  "Chorus 1": [
   "Em",
   "A",
   "D",
   "Bm",
   "Em",
   "A",
   "D",
   "D7",
   "Em",
   "A",
   "D",
   "D/C#",
   "Bm7",
   "D/A",
   "Gmaj7",
   "Gmaj7",
   "Asus4",
   "A"
  ],
  "Interlude": [
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7"
  ],
  "Verse 2": [
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "G",
   "G"
  ],
  "Chorus 2": [
   "Em",
   "A",
   "D",
   "Bm",
   "Em",
   "A",
   "D",
   "D7",
   "Em",
   "A",
   "D",
   "D/C#",
   "Bm7",
   "D/A",
   "Gmaj7",
   "Gmaj7",
   "Asus4",
   "A"
  ],
  "Harmonica / Accordion": [
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7"
  ],
  "Guitar Section": [
   "Em",
   "A",
   "D",
   "Bm",
   "Em",
   "A",
   "D",
   "D7"
  ],
  "Chorus 3": [
   "Em",
   "A",
   "D",
   "Bm",
   "Em",
   "A",
   "D",
   "D7",
   "Em",
   "A",
   "D",
   "D/C#",
   "Bm7",
   "D/A",
   "Gmaj7",
   "Gmaj7",
   "Asus4",
   "A"
  ],
  "Outro": [
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D",
   "Dmaj7",
   "Dmaj7",
   "D7",
   "D7",
   "Dmaj7",
   "Dmaj7",
   "D",
   "D"
  ]
 },
 "chart_versions": {
  "Beginner": {
   "Intro": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D"
   ],
   "Verse 1": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "G",
    "G"
   ],
   "Chorus 1": [
    "Em",
    "A",
    "D",
    "Bm",
    "Em",
    "A",
    "D",
    "D",
    "Em",
    "A",
    "D",
    "D",
    "Bm",
    "D",
    "G",
    "G",
    "A",
    "A"
   ],
   "Interlude": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D"
   ],
   "Verse 2": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "G",
    "G"
   ],
   "Chorus 2": [
    "Em",
    "A",
    "D",
    "Bm",
    "Em",
    "A",
    "D",
    "D",
    "Em",
    "A",
    "D",
    "D",
    "Bm",
    "D",
    "G",
    "G",
    "A",
    "A"
   ],
   "Harmonica / Accordion": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D"
   ],
   "Guitar Section": [
    "Em",
    "A",
    "D",
    "Bm",
    "Em",
    "A",
    "D",
    "D"
   ],
   "Chorus 3": [
    "Em",
    "A",
    "D",
    "Bm",
    "Em",
    "A",
    "D",
    "D",
    "Em",
    "A",
    "D",
    "D",
    "Bm",
    "D",
    "G",
    "G",
    "A",
    "A"
   ],
   "Outro": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D"
   ]
  },
  "Intermediate": {
   "Intro": [
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7"
   ],
   "Verse 1": [
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "G",
    "G"
   ],
   "Chorus 1": [
    "Em",
    "A",
    "D",
    "Bm",
    "Em",
    "A",
    "D",
    "D7",
    "Em",
    "A",
    "D",
    "D/C#",
    "Bm7",
    "D/A",
    "Gmaj7",
    "Gmaj7",
    "Asus4",
    "A"
   ],
   "Interlude": [
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7"
   ],
   "Verse 2": [
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "G",
    "G"
   ],
   "Chorus 2": [
    "Em",
    "A",
    "D",
    "Bm",
    "Em",
    "A",
    "D",
    "D7",
    "Em",
    "A",
    "D",
    "D/C#",
    "Bm7",
    "D/A",
    "Gmaj7",
    "Gmaj7",
    "Asus4",
    "A"
   ],
   "Harmonica / Accordion": [
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7"
   ],
   "Guitar Section": [
    "Em",
    "A",
    "D",
    "Bm",
    "Em",
    "A",
    "D",
    "D7"
   ],
   "Chorus 3": [
    "Em",
    "A",
    "D",
    "Bm",
    "Em",
    "A",
    "D",
    "D7",
    "Em",
    "A",
    "D",
    "D/C#",
    "Bm7",
    "D/A",
    "Gmaj7",
    "Gmaj7",
    "Asus4",
    "A"
   ],
   "Outro": [
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D",
    "Dmaj7",
    "Dmaj7",
    "D7",
    "D7",
    "Dmaj7",
    "Dmaj7",
    "D",
    "D"
   ]
  },
  "Advanced": {
   "Intro": [
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9"
   ],
   "Verse 1": [
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Gadd9",
    "Gadd9"
   ],
   "Chorus 1": [
    "Em9",
    "Asus2",
    "Dadd9",
    "Bm9",
    "Em9",
    "Asus2",
    "Dadd9",
    "D9",
    "Em9",
    "Asus2",
    "Dadd9",
    "Dmaj7/C#",
    "Bm9",
    "Dadd9/A",
    "Gmaj9",
    "Gmaj9",
    "A7sus4",
    "Asus2"
   ],
   "Interlude": [
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9"
   ],
   "Verse 2": [
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Gadd9",
    "Gadd9"
   ],
   "Chorus 2": [
    "Em9",
    "Asus2",
    "Dadd9",
    "Bm9",
    "Em9",
    "Asus2",
    "Dadd9",
    "D9",
    "Em9",
    "Asus2",
    "Dadd9",
    "Dmaj7/C#",
    "Bm9",
    "Dadd9/A",
    "Gmaj9",
    "Gmaj9",
    "A7sus4",
    "Asus2"
   ],
   "Harmonica / Accordion": [
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9"
   ],
   "Guitar Section": [
    "Em9",
    "Asus2",
    "Dadd9",
    "Bm9",
    "Em9",
    "Asus2",
    "Dadd9",
    "D9"
   ],
   "Chorus 3": [
    "Em9",
    "Asus2",
    "Dadd9",
    "Bm9",
    "Em9",
    "Asus2",
    "Dadd9",
    "D9",
    "Em9",
    "Asus2",
    "Dadd9",
    "Dmaj7/C#",
    "Bm9",
    "Dadd9/A",
    "Gmaj9",
    "Gmaj9",
    "A7sus4",
    "Asus2"
   ],
   "Outro": [
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9",
    "Dmaj9",
    "Dmaj9",
    "D9",
    "D9",
    "Dmaj9",
    "Dmaj9",
    "Dadd9",
    "Dadd9"
   ]
  }
 }
}''')


# The current chart, transposed back to the D shapes it is authored in. This is
# what the Eb chart must round-trip to; OLD is the pre-W21 half-bar grid and is
# deliberately NOT updated, so the saved-copy test still exercises a real old
# chart.
D_SHAPES = json.loads(r'''{
 "sections": {
  "Intro": [
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7"
  ],
  "Verse 1": [
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D",
   "Dmaj7",
   "D7",
   "G"
  ],
  "Chorus 1": [
   "Em|A",
   "D|Bm",
   "Em|A",
   "D|D7",
   "Em|A",
   "D|D/C#",
   "Bm7|D/A",
   "Gmaj7",
   "Asus4|A"
  ],
  "Interlude": [
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7"
  ],
  "Verse 2": [
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D",
   "Dmaj7",
   "D7",
   "G"
  ],
  "Chorus 2": [
   "Em|A",
   "D|Bm",
   "Em|A",
   "D|D7",
   "Em|A",
   "D|D/C#",
   "Bm7|D/A",
   "Gmaj7",
   "Asus4|A"
  ],
  "Harmonica / Accordion": [
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7"
  ],
  "Guitar Section": [
   "Em|A",
   "D|Bm",
   "Em|A",
   "D|D7"
  ],
  "Chorus 3": [
   "Em|A",
   "D|Bm",
   "Em|A",
   "D|D7",
   "Em|A",
   "D|D/C#",
   "Bm7|D/A",
   "Gmaj7",
   "Asus4|A"
  ],
  "Outro": [
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D",
   "Dmaj7",
   "D7",
   "Dmaj7",
   "D"
  ]
 },
 "chart_versions": {
  "Beginner": {
   "Intro": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D"
   ],
   "Verse 1": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "G"
   ],
   "Chorus 1": [
    "Em|A",
    "D|Bm",
    "Em|A",
    "D|D",
    "Em|A",
    "D|D",
    "Bm|D",
    "G",
    "A|A"
   ],
   "Interlude": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D"
   ],
   "Verse 2": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "G"
   ],
   "Chorus 2": [
    "Em|A",
    "D|Bm",
    "Em|A",
    "D|D",
    "Em|A",
    "D|D",
    "Bm|D",
    "G",
    "A|A"
   ],
   "Harmonica / Accordion": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D"
   ],
   "Guitar Section": [
    "Em|A",
    "D|Bm",
    "Em|A",
    "D|D"
   ],
   "Chorus 3": [
    "Em|A",
    "D|Bm",
    "Em|A",
    "D|D",
    "Em|A",
    "D|D",
    "Bm|D",
    "G",
    "A|A"
   ],
   "Outro": [
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D",
    "D"
   ]
  },
  "Intermediate": {
   "Intro": [
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7"
   ],
   "Verse 1": [
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D",
    "Dmaj7",
    "D7",
    "G"
   ],
   "Chorus 1": [
    "Em|A",
    "D|Bm",
    "Em|A",
    "D|D7",
    "Em|A",
    "D|D/C#",
    "Bm7|D/A",
    "Gmaj7",
    "Asus4|A"
   ],
   "Interlude": [
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7"
   ],
   "Verse 2": [
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D",
    "Dmaj7",
    "D7",
    "G"
   ],
   "Chorus 2": [
    "Em|A",
    "D|Bm",
    "Em|A",
    "D|D7",
    "Em|A",
    "D|D/C#",
    "Bm7|D/A",
    "Gmaj7",
    "Asus4|A"
   ],
   "Harmonica / Accordion": [
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7"
   ],
   "Guitar Section": [
    "Em|A",
    "D|Bm",
    "Em|A",
    "D|D7"
   ],
   "Chorus 3": [
    "Em|A",
    "D|Bm",
    "Em|A",
    "D|D7",
    "Em|A",
    "D|D/C#",
    "Bm7|D/A",
    "Gmaj7",
    "Asus4|A"
   ],
   "Outro": [
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D",
    "Dmaj7",
    "D7",
    "Dmaj7",
    "D"
   ]
  },
  "Advanced": {
   "Intro": [
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9"
   ],
   "Verse 1": [
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9",
    "Dmaj9",
    "D9",
    "Gadd9"
   ],
   "Chorus 1": [
    "Em9|Asus2",
    "Dadd9|Bm9",
    "Em9|Asus2",
    "Dadd9|D9",
    "Em9|Asus2",
    "Dadd9|Dmaj7/C#",
    "Bm9|Dadd9/A",
    "Gmaj9",
    "A7sus4|Asus2"
   ],
   "Interlude": [
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9"
   ],
   "Verse 2": [
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9",
    "Dmaj9",
    "D9",
    "Gadd9"
   ],
   "Chorus 2": [
    "Em9|Asus2",
    "Dadd9|Bm9",
    "Em9|Asus2",
    "Dadd9|D9",
    "Em9|Asus2",
    "Dadd9|Dmaj7/C#",
    "Bm9|Dadd9/A",
    "Gmaj9",
    "A7sus4|Asus2"
   ],
   "Harmonica / Accordion": [
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9"
   ],
   "Guitar Section": [
    "Em9|Asus2",
    "Dadd9|Bm9",
    "Em9|Asus2",
    "Dadd9|D9"
   ],
   "Chorus 3": [
    "Em9|Asus2",
    "Dadd9|Bm9",
    "Em9|Asus2",
    "Dadd9|D9",
    "Em9|Asus2",
    "Dadd9|Dmaj7/C#",
    "Bm9|Dadd9/A",
    "Gmaj9",
    "A7sus4|Asus2"
   ],
   "Outro": [
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9",
    "Dmaj9",
    "D9",
    "Dmaj9",
    "Dadd9"
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
        self.assertEqual(ext["default_bpm"], OLD["bpm"])
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(list(r.get("section_order") or r["sections"]), OLD["order"])
        # The key correction did not change the form; W21's grid correction did.
        self.assertEqual(
            {n: len(c) for n, c in r["sections"].items()},
            {n: len(c) for n, c in D_SHAPES["sections"].items()},
        )

    def test_the_concert_progression_is_what_the_chart_plays(self) -> None:
        r = rec()
        secs = r["sections"]
        # intro/verse cycle: one bar each of I, Imaj7, I7, Imaj7
        self.assertEqual(secs["Intro"][:4], ["Eb", "Ebmaj7", "Eb7", "Ebmaj7"])
        # the verse turns to IV in its last bar
        self.assertEqual(secs["Verse 1"][-1], "Ab")
        # chorus is ii - V - I - vi, TWO chords to a bar
        self.assertEqual(secs["Chorus 1"][:2], ["Fm|Bb", "Eb|Cm"])
        self.assertEqual(secs["Chorus 1"][-1], "Bbsus4|Bb")
        # no D-shape spelling may survive at any level
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, got = resolve_level_chart(rec(), level)
            cells = [c for v in got.values() for c in v]
            for stale in ("D", "Dmaj7", "D7", "Dmaj9", "Dadd9", "G", "Gmaj7",
                          "Em", "Bm", "Bm7", "A", "Asus4", "D/C#", "D/A"):
                self.assertNotIn(stale, cells, f"{level}: stale capo spelling {stale}")

    def test_capo_metadata_reaches_the_record(self) -> None:
        ext = rec()["extensions"]
        self.assertEqual(ext["concert_key"], "Eb")
        self.assertEqual(ext["guitar_friendly_key"], "D")
        self.assertIn("Capo 1", ext["capo_note"])

    def test_guitar_tabs_are_relabelled_to_the_concert_chords(self) -> None:
        tabs = rec().get("guitar_tabs") or {}
        self.assertTrue(tabs, "Kiss Me should still carry fingerings")
        for stale in ("D", "Dmaj7", "D7", "G", "Em", "Bm", "A"):
            self.assertNotIn(stale, tabs, f"stale D-shape tab {stale}")
        for want in ("Eb", "Ebmaj7", "Eb7", "Ab", "Fm", "Bb", "Cm"):
            self.assertIn(want, tabs, f"missing concert fingering for {want}")

    def test_form_is_corrected_and_matches_the_recording(self) -> None:
        """Renamed from test_form_is_unchanged_and_its_length_gap_is_documented.

        That test pinned the defect (176 bars, "FORM NOT VERIFIED") on purpose,
        so that the gap could not be forgotten. W21 closed the gap, so the pin
        now asserts the corrected form instead of the documented defect.
        """
        r = rec()
        self.assertEqual(r["extensions"]["default_bpm"], 100)
        self.assertEqual(len(r.get("section_order") or r["sections"]), 10)
        _v, adv = resolve_level_chart(rec(), "Advanced")
        self.assertEqual(sum(len(v) for v in adv.values()), 88)
        notes = r["extensions"]["arrangement_notes"]
        self.assertNotIn("FORM NOT VERIFIED", notes)
        self.assertIn("FORM CORRECTED", notes)
        # 88 bars at 100 BPM is 3:31.2, against a 3:30 album version.
        from songs.meter import meter_timing
        self.assertAlmostEqual(88 * meter_timing(100, "4/4").bar_sec, 211.2, places=6)

    def test_transposed_back_to_the_shapes_it_is_the_old_chart_exactly(self) -> None:
        r = rec()
        self.assertEqual(
            transpose_sections_dict(r["sections"], NEW_REF, OLD_REF), D_SHAPES["sections"]
        )
        for level, secs in D_SHAPES["chart_versions"].items():
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
            transpose_sections_dict(D_SHAPES["sections"], OLD_REF, "C"),
        )


if __name__ == "__main__":
    unittest.main()
