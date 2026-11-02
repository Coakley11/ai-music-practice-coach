"""Issue 2: the melody that is actually synthesised sounds the transposed pitch."""

from __future__ import annotations

import unittest

import numpy as np

from composition_document import new_composition_document
from composition_melody_projection import project_melody_events
from composition_preview import _midi_to_hz, _wav_to_mono_floats, generate_preview_wav


def _midi(token: str) -> int:
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    letter, rest = token[0], token[1:]
    octave = int(rest[-1])
    acc = rest[:-1].count("#") - rest[:-1].count("b")
    return 12 * (octave + 1) + names[letter] + acc


def _centroid(samples: np.ndarray, sr: int) -> float:
    """Spectral centroid of the 150-1100 Hz band. The synth adds vibrato and reverb, so a narrow
    peak is noisy, but the centroid rises monotonically with the played pitch."""
    spec = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    freqs = np.fft.rfftfreq(len(samples), 1.0 / sr)
    band = (freqs > 150) & (freqs < 1100)
    return float((freqs[band] * spec[band]).sum() / spec[band].sum())


def _render(events: list[dict]) -> tuple[np.ndarray, int]:
    doc = new_composition_document(title="Audio")
    wav = generate_preview_wav(doc, include_melody=True, melody_override=events, loops=1)
    assert wav, "no audio rendered"
    samples, sr = _wav_to_mono_floats(wav)
    return np.asarray(samples, dtype=float), int(sr)


class TestMelodyAudioPitch(unittest.TestCase):
    def test_higher_pitches_synthesise_higher(self) -> None:
        cents = [_centroid(*_render([{"pitch": t, "duration_beats": 4.0, "beat": 0.0}])) for t in ("C4", "D4", "Eb4", "E4", "G4", "B4")]
        self.assertEqual(cents, sorted(cents))

    def test_the_projected_melody_sounds_exactly_like_the_expected_pitch(self) -> None:
        src = [{"pitch": "E4", "duration_beats": 4.0, "beat": 0.0}]
        for key, expected in (("D", "D4"), ("Eb", "Eb4"), ("G", "G4"), ("C", "C4"), ("F", "F4")):
            with self.subTest(key=key):
                out, _, _ = project_melody_events(src, original_key="E", practice_key=key, instrument="Piano", session_state={})
                got = _centroid(*_render(out))
                want = _centroid(*_render([{"pitch": expected, "duration_beats": 4.0, "beat": 0.0}]))
                self.assertAlmostEqual(got / want, 1.0, delta=0.004)
                original = _centroid(*_render(src))
                self.assertNotAlmostEqual(got / original, 1.0, delta=0.008)

    def test_the_original_melody_data_is_not_rewritten_by_projection(self) -> None:
        src = [{"pitch": "E4", "duration_beats": 4.0, "beat": 0.0}]
        project_melody_events(src, original_key="E", practice_key="D", instrument="Piano", session_state={})
        self.assertEqual(src[0]["pitch"], "E4")


if __name__ == "__main__":
    unittest.main()
