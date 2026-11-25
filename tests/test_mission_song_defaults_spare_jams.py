"""Android retest 2026-11-24: a Style Jam generated at 112 BPM came back at 100 after a reload.

Traced write by write in the real app (Composition song "Jazz tune" used in Song-Based Improvisation, then a Style
Jam Bossa Nova in D at 112 generated): on reload the session restored 112, then the Mission / Song-Based
hydration (hydrate_mission_practice_context_after_restore -> build_mission_practice_context ->
sync_mission_style_from_song) wrote the song's defaults into the jams' controls -- Style Jam's style, tempo and
groove ("Song Default", 100, "Auto"), the Generator's style, Backing's Feel. Style and groove were put back from
Style Jam's record later; the tempo was not (heading "... · 100 BPM", Backing card 100).

The song-default sync still seeds jam controls nobody has used; a jam holding its own generated progression keeps
its settings, and Backing keeps its Feel while it plays a jam. The Mission reads exactly the values it read before.
"""

from __future__ import annotations

import unittest
from unittest import mock

from improvisation_intelligence import generate_style_progression

STYLE_JAM_META = {"style": "Bossa Nova", "bpm": 112, "groove": "Light", "entry_mode": "Style Jam Mode"}


def _session(*, style_jam_generated: bool, generator_generated: bool = False, meta_mode: str = "Style Jam Mode") -> dict:
    s = {"improv_style": "Bossa Nova", "improv_style_bpm": 112, "improv_groove": "Light", "improv_style_meter": "4/4",
         "improv_jam_style": "Bossa Nova", "backing_groove_style": "Bossa nova", "improv_mood": "Dreamy",
         "improv_style_meta": dict(STYLE_JAM_META, entry_mode=meta_mode)}
    if style_jam_generated:
        s["improv_generated_sections"] = generate_style_progression(style="Bossa Nova", key_center="D", mood="Dreamy")
    if generator_generated:
        s["improv_jam_session"] = {"id": "g", "sections": {"A (Bossa Nova)": ["Dmaj7", "Em7"]}}
    return s


def _controls(s: dict) -> tuple:
    return s.get("improv_style"), s.get("improv_style_bpm"), s.get("improv_groove")


class MissionSongDefaultsSpareEstablishedJamsTests(unittest.TestCase):
    def test_a_generated_style_jam_keeps_its_tempo_style_and_groove(self) -> None:
        from mission_song_backing_style import sync_mission_style_from_song

        s = _session(style_jam_generated=True)
        sync_mission_style_from_song(s)
        self.assertEqual(_controls(s), ("Bossa Nova", 112, "Light"))
        self.assertEqual(s["improv_style_meta"], STYLE_JAM_META)

    def test_a_style_jam_nobody_generated_still_gets_the_songs_defaults(self) -> None:
        from mission_song_backing_style import sync_mission_style_from_song

        s = _session(style_jam_generated=False)
        sync_mission_style_from_song(s)
        self.assertEqual(_controls(s), ("Song Default", 100, "Auto"))

    def test_the_generators_own_jam_keeps_its_style(self) -> None:
        from mission_song_backing_style import sync_mission_style_from_song

        s = _session(style_jam_generated=False, generator_generated=True)
        sync_mission_style_from_song(s)
        self.assertEqual(s["improv_jam_style"], "Bossa Nova")
        s = _session(style_jam_generated=False)
        sync_mission_style_from_song(s)
        self.assertEqual(s["improv_jam_style"], "Song Default")

    def test_backing_keeps_its_feel_while_it_plays_a_jam(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from mission_song_backing_style import sync_mission_style_from_song

        s = _session(style_jam_generated=True)
        set_backing_context(s, BackingContext(
            source="entry_jam", source_label="Style Jam", active_song_id="creative:entry_jam:sj", song_title="Style Jam",
            entry_mode="Style Jam Mode", style="Bossa Nova", groove="Bossa nova", bpm=112, key="D", display_key="D",
            concert_key="D", progression=["Em7", "A7", "Dmaj7"]))
        sync_mission_style_from_song(s)
        self.assertEqual(s["backing_groove_style"], "Bossa nova")

    def test_an_explicit_use_song_style_still_applies_the_song(self) -> None:
        from mission_song_backing_style import use_song_style_for_mission_jam

        s = _session(style_jam_generated=True)
        use_song_style_for_mission_jam(s)
        self.assertEqual(_controls(s), ("Song Default", 100, "Auto"))

    def test_another_tools_meta_still_gets_the_songs_defaults(self) -> None:
        from mission_song_backing_style import sync_mission_style_from_song

        s = _session(style_jam_generated=True, meta_mode="Song-Based Improvisation")
        sync_mission_style_from_song(s)
        self.assertEqual(s["improv_style_meta"]["bpm"], 100)
        self.assertEqual(_controls(s), ("Bossa Nova", 112, "Light"))

    def test_the_mission_reads_the_same_tempo_style_and_groove_either_way(self) -> None:
        from backing_context import build_mission_context
        from mission_practice_context import build_mission_practice_context

        def mission(s: dict) -> tuple:
            c = build_mission_practice_context(s)
            return c.tempo_bpm, c.backing_style, c.backing_groove, c.meter

        def mission_backing(s: dict) -> tuple:
            b = build_mission_context(s)
            return b.bpm, b.groove, b.style

        before = _session(style_jam_generated=False)
        diag = mock.patch("mission_owner_contract._mission_handoff_diag")  # its debug file is written into the repo
        diag.start()
        self.addCleanup(diag.stop)
        for mode in ("Style Jam Mode", "Song-Based Improvisation"):
            after = _session(style_jam_generated=True, generator_generated=True, meta_mode=mode)
            self.assertEqual(mission(after), mission(_session(style_jam_generated=False)), mode)
            self.assertEqual(mission_backing(after), mission_backing(dict(before)), mode)
        self.assertEqual(mission(_session(style_jam_generated=False)), (100, "Song Default", "Auto", "4/4"))


if __name__ == "__main__":
    unittest.main()
