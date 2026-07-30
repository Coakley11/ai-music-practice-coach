"""Motif ABC notation must include every note and rhythm from the motif dict."""

from __future__ import annotations

import re
import unittest

from improvisation_missions import generate_mission_example
from improvisation_intelligence import ImprovSessionContext
from improvisation_motif import build_motif_abc, build_motif_notation_abc, sync_motif_midi


def _abc_pitch_tokens(abc: str) -> list[str]:
    body = abc.split("K:", 1)[-1].strip()
    body = body.split("\n", 1)[-1] if "\n" in body else body
    body = re.sub(r"\|", " ", body)
    return re.findall(r"[\^_]?[A-Ga-g][',]*(?:/\d+)?(?:\d+)?", body)


class TestMotifAbcFullPhrase(unittest.TestCase):
    def test_harder_example_abc_has_all_notes(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Say",
            artist="Artist",
            key_center="F#m",
            display_key="F#m",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["Bm"]},
        )
        example = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Bm",
            section="Verse",
            level="Intermediate",
            instrument="Piano",
            focus="Improvisation",
            variant="harder",
        )
        notes = list(example.motif.get("notes") or [])
        self.assertGreaterEqual(len(notes), 12)
        abc = example.abc
        tokens = _abc_pitch_tokens(abc)
        self.assertEqual(len(tokens), len(notes))

    def test_bb_spelled_in_abc(self) -> None:
        motif = sync_motif_midi(
            {
                "chord": "Bm",
                "notes": ["F#", "A", "Bb", "B"],
                "rhythm": "♩ ♪ ♪ ♩",
                "rhythm_key": "quarter-eighth-eighth",
            }
        )
        abc = build_motif_notation_abc(motif, key_center="F#m", bpm=82)
        self.assertIn("_B", abc)
        self.assertEqual(len(_abc_pitch_tokens(abc)), 4)

    def test_rhythm_symbols_match_note_count(self) -> None:
        ctx = ImprovSessionContext(
            song_title="T",
            artist="A",
            key_center="C",
            display_key="C",
            instrument="Guitar",
            level="Advanced",
            focus="X",
            sections={"V": ["Am7"]},
        )
        ex = generate_mission_example(
            "Use only chord tones",
            improv_ctx=ctx,
            chord="Am7",
            section="V",
            level="Beginner",
            instrument="Guitar",
            focus="X",
            variant="harder",
        )
        syms = ex.motif.get("rhythm_symbols") or str(ex.motif.get("rhythm") or "").split()
        notes = ex.motif.get("notes") or []
        self.assertEqual(len(syms), len(notes))
        abc = build_motif_abc(ex.motif, key_center="C", bpm=100)
        self.assertEqual(len(_abc_pitch_tokens(abc)), len(notes))


if __name__ == "__main__":
    unittest.main()
