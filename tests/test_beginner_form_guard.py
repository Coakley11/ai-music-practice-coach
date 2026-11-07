"""Catalog guard: a Beginner level must not silently lose a song's defining sections.

Rule (soft, with a ratchet).  For every effective catalog record, take the LAST
occurrence in the Advanced form of each guarded role - Chorus (incl. Refrain/Hook,
so the Final Chorus), Bridge, Solo/Instrumental, Outro/Coda/Ending - provided the
section is "cued" (it has an entry in ``lyric_cues``; records with no ``lyric_cues``
at all are checked on every section, since the form is their only evidence).  That
section must still be present in the Beginner form returned by
``chart_level_arrangement.resolve_level_chart`` unless the record

* declares ``extensions.full_form_levels`` containing "Beginner" (the supported
  per-song fix: Beginner keeps the form with simpler chords / fewer bars per repeat), or
* carries a documented ``extensions.beginner_form_note`` (a deliberate, explained
  simplification).

The global derivation (``select_beginner_section_names``) is NOT changed here.  The
records below are the offenders known on 2026-11-03 (base e812c09e): for each, the
guarded sections the global derivation currently drops at Beginner.  They are
documented, not endorsed - about 40 of them drop only the Bridge/Middle 8 and need a
product decision (derivation change vs per-song ``full_form_levels``).  The allow-list
is a ratchet: a listed song may not drop any section that is not listed for it, and a
song not listed may not drop any.  Entries become dead (and can be deleted) once a
song gets ``full_form_levels`` or a ``beginner_form_note``; a dead entry does not fail.
"""

from __future__ import annotations

import unittest

from beginner_arrangement import (
    ROLE_BRIDGE,
    ROLE_CHORUS,
    ROLE_OUTRO,
    ROLE_SOLO,
    classify_section_role,
)
from chart_level_arrangement import keeps_full_form, resolve_level_chart
from song_catalog.catalog import curated_song_records

GUARDED_ROLES = (ROLE_CHORUS, ROLE_BRIDGE, ROLE_SOLO, ROLE_OUTRO)

# "title|artist" -> guarded sections known to be dropped at Beginner on base e812c09e.
KNOWN_OFFENDERS: dict[str, tuple[str, ...]] = {
    'A Day in the Life|The Beatles': ('Orchestral Bridge',),
    'A Sky Full of Stars|Coldplay': ('Bridge',),
    'Across the Universe|The Beatles': ('Chorus 3',),
    'All You Need Is Love|The Beatles': ('Bridge',),
    'All of Me|John Legend': ('Bridge', 'Final Chorus'),
    'Am Yisrael Chai|Traditional': ('Refrain',),
    'Attention|Charlie Puth': ('Bridge', 'Final Chorus'),
    'Baby One More Time|Britney Spears': ('Final Chorus',),
    'Bad Habits|Ed Sheeran': ('Bridge',),
    'Beat It|Michael Jackson': ('Outro Chorus', 'Solo'),
    'Billie Jean|Michael Jackson': ('Bridge', 'Chorus (Extension)', 'Instrumental'),
    'Blue Bossa|Kenny Dorham': ('Solo',),
    'Breakaway|Kelly Clarkson': ('Bridge', 'Final Chorus', 'Instrumental', 'Outro'),
    "California Dreamin'|The Mamas & the Papas": ('Instrumental',),
    'Californication|Red Hot Chili Peppers': ('Guitar Solo',),
    'Careless Whisper|George Michael': ('Bridge',),
    'Castle on the Hill|Ed Sheeran': ('Bridge',),
    'Clocks|Coldplay': ('Bridge', 'Solo / Outro Riff'),
    'Come Together|The Beatles': ('Final Chorus', 'Instrumental 5'),
    'Complicated|Avril Lavigne': ('Repeat Final Chorus',),
    'Dance Monkey|Tones and I': ('Bridge', 'Final Chorus Repeat'),
    'Daughters|John Mayer': ('Bridge', 'Final Chorus', 'Instrumental Tag'),
    "Don't Stop Believin'|Journey": ('Guitar Solo / Interlude',),
    'Eleanor Rigby|The Beatles': ('Bridge',),
    'Every Breath You Take|The Police': ('Bridge',),
    'Fix You|Coldplay': ('Bridge (Build)',),
    'Girls Just Want to Have Fun|Cyndi Lauper': ('Bridge',),
    'Gravity|John Mayer': ('Chorus', 'Solo'),
    'Help!|The Beatles': ('Bridge',),
    'Here Comes the Sun|The Beatles': ('Bridge',),
    'Hey Jude|The Beatles': ('Bridge / Build',),
    'Hotel California|Eagles': ('Outro Solo',),
    'How Deep Is Your Love|Bee Gees': ('Bridge',),
    "How Far I'll Go|Disney · Moana": ('Final Chorus',),
    'I Want It That Way|Backstreet Boys': ('Bridge', 'Final Chorus Repeat'),
    "I Won't Say (I'm in Love)|Disney · Hercules": ('Ensemble Chorus',),
    "I'm Yours|Jason Mraz": ('Bridge', 'Final Chorus / Outro Build'),
    'Imagine|John Lennon': ('Bridge 3',),
    'In My Life|The Beatles': ('Piano Solo',),
    'Iris|Goo Goo Dolls': ('Coda', 'Final Chorus', 'Instrumental'),
    "Isn't She Lovely|Stevie Wonder": ('Solo Vamp',),
    'Just the Two of Us|Grover Washington Jr. / Bill Withers': ('Bridge', 'Solo'),
    'Just the Way You Are|Billy Joel': ('Bridge', 'Outro (Fade)', 'Refrain 4', 'Sax Solo'),
    'Kiss Me|Sixpence None the Richer': ('Chorus 3', 'Harmonica / Accordion'),
    'Let It Be|The Beatles': ('Solo',),
    'Love Story|Taylor Swift': ('Bridge', 'Final Chorus (Key Change)', 'Solo'),
    'Man in the Mirror|Michael Jackson': ('Final Chorus',),
    'Marry You|Bruno Mars': ('Bridge 2', 'Chorus 4'),
    'New York State of Mind|Billy Joel': ('Solo',),
    'Paradise|Coldplay': ('Bridge',),
    'Perfect|Ed Sheeran': ('Chorus 3',),
    'Photograph|Ed Sheeran': ('Bridge', 'Chorus 3'),
    'Piano Man|Billy Joel': ('Bridge 3', 'Chorus 3', 'Final Harmonica Outro'),
    'Say|John Mayer': ('Bridge', 'Final Chorus'),
    'Shallow|Lady Gaga / Bradley Cooper': ('Bridge',),
    'Shalom Aleichem|Traditional Jewish Sabbath Song': ('Instrumental',),
    'Shape of You|Ed Sheeran': ('Bridge', 'Final Chorus'),
    'Slow Dancing in a Burning Room|John Mayer': ('Solo',),
    'Something|The Beatles': ("Bridge (I Don't Want to Leave)", 'Guitar Solo (Verse Form)'),
    'Take Me Home, Country Roads|John Denver': ('Bridge',),
    'Take On Me|a-ha': ('Bridge',),
    'Take On Me (MTV Unplugged Version)|a-ha': ('Bridge', 'Final Chorus'),
    'The A Team|Ed Sheeran': ('Bridge',),
    'The Scientist|Coldplay': ('Instrumental 2',),
    'Thinking Out Loud|Ed Sheeran': ('Final Chorus', 'Instrumental'),
    'Turn the Lights Back On|Billy Joel': ('Bridge',),
    'Uptown Girl|Billy Joel': ('Bridge',),
    'Vienna|Billy Joel': ('Final Chorus', 'Instrumental'),
    'Viva La Vida|Coldplay': ('Bridge / Oh Section', 'Final Chorus'),
    'Waiting on the World to Change|John Mayer': ('Bridge',),
    'We Are the Champions|Queen': ('Final Chorus',),
    'While My Guitar Gently Weeps|The Beatles': ('Bridge',),
    'Why Georgia|John Mayer': ('Bridge', 'Final Chorus'),
    'Wonderwall|Oasis': ('Bridge 2', 'Final Chorus'),
    'Yellow|Coldplay': ('Bridge',),
    'Yerushalayim Shel Zahav|Traditional': ('Bridge',),
    'You Belong With Me|Taylor Swift': ('Bridge', 'Final Chorus'),
    "You've Got a Friend in Me|Randy Newman": ('Bridge',),
}


def dropped_guarded_sections(record: dict) -> list[str]:
    """Guarded last-occurrence sections present at Advanced but absent at Beginner."""
    cues = record.get("lyric_cues") or {}
    _view, advanced = resolve_level_chart(record, "Advanced")
    _view, beginner = resolve_level_chart(record, "Beginner")
    last_by_role: dict[str, str] = {}
    for name in advanced:
        role = classify_section_role(name)
        if role in GUARDED_ROLES:
            last_by_role[role] = name
    return sorted(
        name
        for name in last_by_role.values()
        if name not in beginner and (not cues or name in cues)
    )


def is_exempt(record: dict) -> bool:
    ext = record.get("extensions") or {}
    return keeps_full_form(record, "Beginner") or bool(str(ext.get("beginner_form_note") or "").strip())


def _key(record: dict) -> str:
    return f"{record['title']}|{record['artist']}"


class BeginnerFormGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = list(curated_song_records())

    def test_no_new_beginner_form_truncation(self):
        problems = []
        for rec in self.records:
            if is_exempt(rec):
                continue
            dropped = dropped_guarded_sections(rec)
            allowed = set(KNOWN_OFFENDERS.get(_key(rec), ()))
            new = [n for n in dropped if n not in allowed]
            if new:
                problems.append(f"{_key(rec)}: Beginner drops {new}")
        self.assertEqual(
            problems,
            [],
            "Beginner lost a cued Final Chorus/Bridge/Solo/Outro. Add "
            "extensions.full_form_levels=['Beginner', ...] (preferred) or a documented "
            "extensions.beginner_form_note; do not extend KNOWN_OFFENDERS.",
        )

    def test_known_offenders_name_real_records(self):
        keys = {_key(r) for r in self.records}
        self.assertEqual(sorted(k for k in KNOWN_OFFENDERS if k not in keys), [])

    def test_exemption_mechanisms_are_recognised(self):
        rec = {"title": "T", "artist": "A", "extensions": {"full_form_levels": ["Beginner"]}}
        self.assertTrue(is_exempt(rec))
        rec = {"title": "T", "artist": "A", "extensions": {"beginner_form_note": "intentional loop"}}
        self.assertTrue(is_exempt(rec))
        self.assertFalse(is_exempt({"title": "T", "artist": "A", "extensions": {"full_form_levels": ["Intermediate"]}}))

    def test_detector_flags_a_dropped_final_chorus(self):
        rec = {
            "title": "Synthetic", "artist": "Test", "key": "C", "genre": "Pop",
            "sections": {
                "Verse 1": ["C", "G", "Am", "F"], "Chorus 1": ["F", "C", "G", "C"],
                "Verse 2": ["C", "G", "Am", "F"], "Chorus 2": ["F", "C", "G", "C"],
                "Verse 3": ["C", "G", "Am", "F"], "Bridge": ["Am", "G", "F", "G"],
                "Final Chorus": ["F", "C", "G", "C"],
            },
            "lyric_cues": {"Bridge": ["x"], "Final Chorus": ["y"]},
            "extensions": {},
        }
        self.assertIn("Final Chorus", dropped_guarded_sections(rec))
        rec["extensions"] = {"full_form_levels": ["Beginner"]}
        self.assertTrue(is_exempt(rec))
        self.assertEqual(dropped_guarded_sections(rec), [])


if __name__ == "__main__":
    unittest.main()
