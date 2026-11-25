"""Android retest 2026-11-24, browser check C3: Style Jam generated at 112 BPM came back at 100 after
"back to the song" from the jam's Backing card, a reload on the song's Backing, and returning to Creative.

Traced: leaving the jam's Backing for the song's releases Creative's widgets (Style Jam's controls and style meta are
popped). The Mission / Song-Based song-default sync then wrote a style meta with the song's defaults and no
entry_mode ({"bpm": 100, "groove": "Auto", "style": "Song Default"}); it was saved with the Creative copy and restored
on reload. Style Jam's controls were restored correctly (112 / Light), but activating Style Jam rebuilt its record
through the legacy adapter, which took any meta without an entry_mode as Style Jam's own: the record, and then the
controls, became 100 / Auto.

A meta no mode stamped is not Style Jam's: its own controls win, the meta only fills what is missing.
"""

from __future__ import annotations

import unittest

from music_workflow_compatibility import build_workflow_blob_from_legacy

CONTROLS = {"improv_style": "Bossa Nova", "improv_style_bpm": 112, "improv_groove": "Light", "improv_mood": "Dreamy",
            "improv_style_key": "D"}
SONG_DEFAULTS_META = {"bpm": 100, "groove": "Auto", "style": "Song Default", "meter": "4/4"}


def _record(**session) -> tuple:
    b = build_workflow_blob_from_legacy(dict(session), "style_jam")
    return b.tempo_bpm, b.groove, b.mood


class StyleJamRecordTempoOwnerTests(unittest.TestCase):
    def test_an_unstamped_song_default_meta_never_becomes_style_jams_tempo(self) -> None:
        self.assertEqual(_record(**CONTROLS, improv_style_meta=dict(SONG_DEFAULTS_META)), (112, "Light", "Dreamy"))

    def test_style_jams_own_meta_still_sets_its_record(self) -> None:
        meta = {"bpm": 108, "groove": "Medium", "mood": "Bright", "entry_mode": "Style Jam Mode"}
        self.assertEqual(_record(**CONTROLS, improv_style_meta=meta), (108, "Medium", "Bright"))

    def test_another_modes_meta_is_still_not_style_jams(self) -> None:
        meta = {"bpm": 100, "groove": "Auto", "entry_mode": "Song-Based Improvisation"}
        self.assertEqual(_record(**CONTROLS, improv_style_meta=meta), (112, "Light", "Dreamy"))

    def test_without_its_controls_an_older_unstamped_meta_still_gives_the_record_its_values(self) -> None:
        self.assertEqual(_record(improv_style_meta={"bpm": 96, "groove": "Light", "mood": "Bright"}), (96, "Light", "Bright"))


if __name__ == "__main__":
    unittest.main()
