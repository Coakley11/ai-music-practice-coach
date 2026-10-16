"""The rendered backing sounds the chord the timeline shows, bar by bar.

Analyses the synthesized audio (pitch-class chroma above the kick drum) for
obvious progressions and checks each bar against the chord that the chord
timeline -- and therefore the UI highlight -- shows for that bar.
"""

from __future__ import annotations

import numpy as np
import pytest

import backing_audio as ba

_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10)}


def _templates() -> dict[str, np.ndarray]:
    out = {}
    for root in range(12):
        for q, iv in _QUAL.items():
            v = np.zeros(12)
            for i in iv:
                v[(root + i) % 12] = 1.0
            out[_NAMES[root] + q] = v / np.linalg.norm(v)
    return out


_T = _templates()


def _chroma(seg: np.ndarray, sr: int) -> np.ndarray:
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1.0 / sr)
    band = (freqs > 120) & (freqs < 2000)
    chroma = np.zeros(12)
    midi = np.rint(69 + 12 * np.log2(freqs[band] / 440.0)).astype(int) % 12
    np.add.at(chroma, midi, spec[band] ** 2)
    return chroma / (np.linalg.norm(chroma) + 1e-12)


def _heard(audio: np.ndarray, sr: int, bar_sec: float, bars: int) -> list[str]:
    out = []
    for i in range(bars):
        seg = audio[int((i + 0.15) * bar_sec * sr) : int((i + 0.9) * bar_sec * sr)]
        c = _chroma(seg, sr)
        out.append(max(_T, key=lambda k: float(np.dot(_T[k], c))))
    return out


@pytest.mark.parametrize(
    "prog,style,bpm,meter",
    [
        (["C", "F", "Dm", "G7"], "Pop groove", 100, "4/4"),
        (["C", "F", "Dm", "G7"], "Pop groove", 90, "3/4"),
        (["Cm", "Ab", "Eb", "Bb"], "Ballad", 72, "4/4"),
    ],
)
def test_each_bar_sounds_its_timeline_chord(prog, style, bpm, meter) -> None:
    events = [{"chord": c, "section": "Verse 1", "bar_in_section": i, "section_bars": len(prog)} for i, c in enumerate(prog)]
    audio, sr = ba.synthesize_chords_to_numpy(events, bpm=bpm, loops=2, style=style, song_title="T", time_signature=meter)
    bar = ba.meter_timing(bpm, meter).bar_sec
    heard = _heard(audio, sr, bar, len(prog) * 2)
    want = prog * 2
    for got, exp in zip(heard, want):
        # A G7 bar may read as its G triad; quality (major vs minor) must not flip.
        assert got == exp or (exp.endswith("7") and got == exp[:-1]), (heard, want)
    # Audio length = bars at this BPM/meter plus the fixed one-second tail, the
    # same bar grid the chord timeline uses.
    assert abs(len(audio) / sr - (len(want) * bar + 1.0)) < 0.05
