"""Motif ABC notation must include every note and rhythm from the motif dict."""

from __future__ import annotations

import re
import unittest

from improvisation_missions import generate_mission_example, rebuild_mission_outputs
from improvisation_intelligence import ImprovSessionContext
from improvisation_motif import (
    build_motif_abc,
    build_motif_notation_abc,
    motif_rhythm_symbols,
    sync_motif_midi,
)


def _abc_pitch_tokens(abc: str) -> list[str]:
    body = abc.split("K:", 1)[-1].strip()
    body = body.split("\n", 1)[-1] if "\n" in body else body
    body = re.sub(r"\|", " ", body)
    return re.findall(r"[\^_]?[A-Ga-g][',]*(?:/\d+)?(?:\d+)?", body)


def _tab_placement_count(motif: dict) -> int:
    """Same note count as TAB builder (one placement per motif note)."""
    midis = motif.get("midi") or []
    return len(midis)


def assert_mission_outputs_synchronized(example, *, expect_tab: bool = False) -> None:
    """All views must derive from example.motif (notes, rhythm, abc, tab, midi)."""
    motif = sync_motif_midi(dict(example.motif))
    notes = list(motif.get("notes") or [])
    syms = motif_rhythm_symbols(motif)
    rhythm_parts = str(motif.get("rhythm") or "").split()
    display_parts = [p.strip() for p in str(motif.get("display") or "").split(" – ")]

    assert len(notes) >= 1
    assert len(syms) == len(notes), (len(syms), len(notes))
    assert len(rhythm_parts) == len(notes), (len(rhythm_parts), len(notes))
    assert display_parts == notes, (display_parts, notes)
    assert len(motif.get("midi") or []) == len(notes)

    abc = example.abc or build_motif_notation_abc(motif, key_center=example.display_key)
    tokens = _abc_pitch_tokens(abc)
    assert len(tokens) == len(notes), (len(tokens), len(notes), abc)

    if expect_tab:
        assert example.tab
        assert _tab_placement_count(motif) == len(notes)
        assert "|" in example.tab

    # Mixed rhythm harder lines should not be all quarters
    if motif.get("harder_example"):
        assert any(s in ("♪", "♬") for s in syms)


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


class TestMotifOutputSynchronization(unittest.TestCase):
    """Regression: text, ABC, TAB, and midi stay tied to one motif object."""

    def _ctx(self, key: str, chord: str, inst: str = "Piano") -> ImprovSessionContext:
        return ImprovSessionContext(
            song_title="Verify",
            artist="Test",
            key_center=key,
            display_key=key,
            instrument=inst,
            level="Intermediate",
            focus="Improvisation",
            sections={"Chorus": [chord]},
        )

    def test_harder_sync_matrix(self) -> None:
        cases = [
            ("F#m", "Bm", "Piano", "Rhythm-first, note-second"),
            ("Eb", "Eb7", "Piano", "Target only guide tones (3rds & 7ths)"),
            ("G", "Am7", "Guitar", "Use only chord tones"),
            ("C", "Dm7", "Saxophone", "Five notes only"),
        ]
        for key, chord, inst, mission in cases:
            with self.subTest(key=key, chord=chord, inst=inst):
                ex = generate_mission_example(
                    mission,
                    improv_ctx=self._ctx(key, chord, inst),
                    chord=chord,
                    section="Chorus",
                    level="Beginner",
                    instrument=inst,
                    focus="Improvisation",
                    variant="harder",
                )
                assert_mission_outputs_synchronized(ex, expect_tab=(inst == "Guitar"))
                self.assertGreaterEqual(len(ex.motif.get("notes") or []), 12)
                self.assertIn("|", ex.abc)

    def test_rebuild_mission_outputs_idempotent(self) -> None:
        ctx = self._ctx("F#m", "Bm")
        ex = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Bm",
            section="Chorus",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            variant="harder",
        )
        out = rebuild_mission_outputs(
            ex.motif,
            chord="Bm",
            instrument="Guitar",
            key_center="F#m",
            bpm=82,
        )
        ex2 = ex
        ex2.motif = out["motif"]
        ex2.abc = out["abc"]
        ex2.tab = out["tab"]
        assert_mission_outputs_synchronized(ex2, expect_tab=True)

    def test_chromatic_notes_in_harder_phrase_abc(self) -> None:
        ctx = self._ctx("F#m", "Bm")
        ex = generate_mission_example(
            "Rhythm-first, note-second",
            improv_ctx=ctx,
            chord="Bm",
            section="Chorus",
            level="Advanced",
            instrument="Piano",
            focus="Improvisation",
            variant="harder",
            session_state={"improv_mission_new_nonce": 3},
        )
        notes = ex.motif.get("notes") or []
        abc = ex.abc
        if any("b" in str(n) and not str(n).endswith("#") for n in notes):
            self.assertRegex(abc, r"_[A-G]")
        if any("#" in str(n) for n in notes):
            self.assertRegex(abc, r"\^[A-G]")
        assert_mission_outputs_synchronized(ex)


if __name__ == "__main__":
    unittest.main()
