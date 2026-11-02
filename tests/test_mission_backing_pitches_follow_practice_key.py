"""Issue 8: a Mission's Backing Track sounds the Mission's chords at the live Practice Key.

Checked on the synthesized audio itself (chroma of the rendered waveform), not on chord labels.
"""

from __future__ import annotations

import unittest

import numpy as np

from backing_audio import synthesize_chords_to_numpy
from mission_span_backing import span_concert_chords
from music_theory import CHROMATIC, normalize_root, split_chord

NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
TONES = {"m7": (0, 3, 7, 10), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11)}
PAYLOAD = {
    "practice_key": "C",
    "timeline": [{"chord": "Dm7", "bars": 2}, {"chord": "G7", "bars": 2}, {"chord": "Cmaj7", "bars": 4}],
}


def _pc(root: str) -> int:
    return CHROMATIC.index(normalize_root(root))


def _chroma(chord: str) -> np.ndarray:
    audio, sr = synthesize_chords_to_numpy([chord], bpm=60, loops=1, style="Pop groove")
    a = np.asarray(audio, dtype=float)
    if a.ndim > 1:
        a = a.mean(axis=1)
    power = np.abs(np.fft.rfft(a * np.hanning(len(a)))) ** 2
    freqs = np.fft.rfftfreq(len(a), 1.0 / sr)
    c = np.zeros(12)
    for fr, p in zip(freqs, power):
        if 60 < fr < 1200:
            c[round(69 + 12 * np.log2(fr / 440.0)) % 12] += p
    return c / c.sum()


class TestMissionBackingPitches(unittest.TestCase):
    def _check(self, target_key: str) -> list[str]:
        shift = (_pc(target_key) - _pc("C")) % 12
        sounded = []
        for (chord, _bars), src in zip(span_concert_chords(PAYLOAD, target_key), PAYLOAD["timeline"]):
            root, suffix = split_chord(chord)
            src_root, src_suffix = split_chord(src["chord"])
            self.assertEqual(suffix, src_suffix, f"{target_key}: quality changed {src['chord']}->{chord}")
            self.assertEqual(_pc(root), (_pc(src_root) + shift) % 12, f"{target_key}: {chord}")
            want = {(_pc(root) + t) % 12 for t in TONES[suffix]}
            c = _chroma(chord)
            self.assertGreater(sum(c[i] for i in want), 0.85, f"{target_key}: {chord} audio is not that chord")
            self.assertIn(_pc(root), set(np.argsort(c)[::-1][:3].tolist()), f"{target_key}: {chord} root not audible")
            sounded.append(chord)
        return sounded

    def test_bb_practice_key_sounds_cm7_f7_bbmaj7(self) -> None:
        self.assertEqual(self._check("Bb"), ["Cm7", "F7", "Bbmaj7"])

    def test_every_practice_key_sounds_the_transposed_progression(self) -> None:
        for key in NAMES:
            self._check(key)

    def test_home_key_is_unchanged(self) -> None:
        self.assertEqual(self._check("C"), ["Dm7", "G7", "Cmaj7"])


if __name__ == "__main__":
    unittest.main()
