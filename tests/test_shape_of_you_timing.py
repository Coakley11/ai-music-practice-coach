"""Shape of You's authoritative timing: two chords per bar, Em and A pushed.

The record is written one chord per bar (736 beats, 184 bars). Every chord now
plays half as long (368 beats, 92 bars), and the Bm -> Em and G -> A changes
arrive an 8th early (``Bm:2|Em:2p``, ``G:2|A:2p``) on every loop.
"""

from __future__ import annotations

import unittest

from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from music_theory import transpose_sections_dict
from song_catalog.catalog import load_song_catalog


LOOP = ["Bm:2|Em:2p", "G:2|A:2p"]
ADVANCED_VERSE_LOOP = ["Bm7:2|Em7:2p", "Gmaj7:2|Asus2:2p"]
ADVANCED_CHORUS_LOOP = ["Bm7:2|Em7:2p", "Gmaj7:2|Aadd9:2p"]


def _shape_of_you() -> dict:
    _library, picker, *_ = load_song_catalog()
    for songs in picker.values():
        for label, data in songs.items():
            if label.startswith("Shape of You "):
                return data
    raise AssertionError("Shape of You missing from the catalog")


def _push_start(token: str, beat_seconds: float, push_offset_beats: float = 0.5) -> list[tuple[str, float]]:
    """Attack times within a bar, as the follow timeline / synth place them."""
    out, cursor = [], 0.0
    for sub in parse_subdivisions(token, beats_per_bar=4):
        start = cursor - (push_offset_beats if sub.push and cursor > 0 else 0.0)
        out.append((sub.chord, start * beat_seconds))
        cursor += sub.weight
    return out


class ShapeOfYouTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.song = _shape_of_you()
        cls.sections = cls.song["sections"]

    def test_form_is_halved(self) -> None:
        lengths = {name: len(bars) for name, bars in self.sections.items()}
        self.assertEqual(lengths, {
            "Verse 1": 8, "Pre-Chorus 1": 8, "Chorus 1": 16, "Verse 2": 8,
            "Pre-Chorus 2": 8, "Chorus 2": 16, "Bridge": 12, "Final Chorus": 16,
        })
        beats = sum(s.weight for bars in self.sections.values() for t in bars for s in parse_subdivisions(t))
        self.assertEqual(beats, 368.0)

    def test_every_loop_pushes_em_and_a(self) -> None:
        for name in ("Verse 1", "Pre-Chorus 1", "Chorus 1", "Verse 2", "Pre-Chorus 2", "Chorus 2", "Final Chorus"):
            self.assertEqual(self.sections[name], LOOP * (len(self.sections[name]) // 2), name)
        self.assertEqual(self.sections["Bridge"], ["N.C."] * 8 + LOOP * 2)

    def test_every_level_shares_the_timing(self) -> None:
        versions = self.song["chart_versions"]
        self.assertEqual(versions["Intermediate"], self.sections)
        self.assertEqual(versions["Beginner"]["Verse 1"], LOOP)
        self.assertEqual(versions["Beginner"]["Bridge"], ["N.C."] * 2 + LOOP)
        self.assertEqual(versions["Advanced"]["Verse 1"], ADVANCED_VERSE_LOOP * 4)
        self.assertEqual(versions["Advanced"]["Chorus 1"], ADVANCED_CHORUS_LOOP * 8)

    def test_beat_events_carry_the_push(self) -> None:
        events = sections_dict_to_events(self.sections, time_signature="4/4", section_order=list(self.sections))
        self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        first = [(e["chord"], e["beat"], e["duration_beats"], bool(e.get("push"))) for e in events[:4]]
        self.assertEqual(first, [("Bm", 1.0, 2.0, False), ("Em", 3.0, 2.0, True), ("G", 1.0, 2.0, False), ("A", 3.0, 2.0, True)])

    def test_pushed_chords_sound_on_the_and_of_two(self) -> None:
        beat = 60.0 / 96
        self.assertEqual(_push_start(LOOP[0], beat), [("Bm", 0.0), ("Em", 1.5 * beat)])
        self.assertEqual(_push_start(LOOP[1], beat), [("G", 0.0), ("A", 1.5 * beat)])

    def test_transposition_changes_pitch_only(self) -> None:
        moved = transpose_sections_dict({"Verse 1": LOOP}, "Bm", "C#m")["Verse 1"]
        self.assertEqual(moved, ["C#m:2|F#m:2p", "A:2|B:2p"])
        for token in moved:
            self.assertEqual([(s.weight, s.push) for s in parse_subdivisions(token)], [(2.0, False), (2.0, True)])

    def test_chord_readers_name_chords_not_chart_syntax(self) -> None:
        # The coach and the Creative chord map read the song as chords in order;
        # "Bm:2|Em:2p" reached them as one chord name and its barline split the notation.
        from chord_subdivisions import chord_stream
        from improvisation_motif import section_harmony_rows

        self.assertEqual(chord_stream(LOOP * 4), ["Bm", "Em", "G", "A"] * 4)
        self.assertEqual(chord_stream(["N.C.", "Bm.hit", "D"]), ["N.C.", "Bm.hit", "D"])
        rows = {label: (clean, raw) for label, clean, raw in section_harmony_rows(self.sections)}
        self.assertEqual(rows["Verse 1"], (["Bm", "Em", "G", "A"], ["Bm", "Em", "G", "A"] * 4))


if __name__ == "__main__":
    unittest.main()
