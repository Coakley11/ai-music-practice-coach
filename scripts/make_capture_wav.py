"""Build the microphone fixture Chromium will inject with --use-file-for-fake-audio-capture.

The ground truth is the set of *inter-onset intervals*, in beats, not absolute positions:
Chromium starts the fake capture device when getUserMedia opens, so the phase between this
file and the recorder's musical zero is not ours to choose. Intervals survive any phase, so
they are what the acceptance script checks - and the measured music_start_frame is what turns
them back into absolute beats.

Deliberately included: an off-beat eighth entry, a pair of repeated pitches with a real gap
between them (so a merge would be visible), a long rest, and a sixteenth-level entry.
"""
from __future__ import annotations

import math
import pathlib
import struct
import sys
import wave

RATE = 48000
BPM = 96.0
SPB = 60.0 / BPM           # 0.625 s per beat
PATTERN_BEATS = 8.0        # one instance, silence-padded, so it loops cleanly

# (onset in beats, midi, sounding length in beats)
NOTES: list[tuple[float, int, float]] = [
    (0.00, 74, 0.55),   # D5   - downbeat of the pattern
    (1.00, 69, 0.30),   # A4   - on the beat
    (1.50, 71, 0.20),   # B4   - off-beat eighth
    (1.75, 74, 0.20),   # D5   - sixteenth-level entry
    (2.50, 74, 0.35),   # D5   - REPEATED pitch, 0.4 beat gap = 250 ms > merge gap
    (4.00, 78, 0.30),   # F#5
    (4.25, 76, 0.20),   # E5   - sixteenth
    (4.50, 74, 0.60),   # D5
    # 1.5 beat rest
    (6.50, 69, 0.80),   # A4   - after the rest
]
INTERVALS = [round(NOTES[i + 1][0] - NOTES[i][0], 4) for i in range(len(NOTES) - 1)]


def tone(midi: int, seconds: float) -> list[float]:
    """A flute-ish tone: fundamental plus a weak second partial, soft attack and release."""
    freq = 440.0 * (2 ** ((midi - 69) / 12.0))
    n = int(seconds * RATE)
    out: list[float] = []
    atk = max(1, int(0.012 * RATE))
    rel = max(1, int(0.040 * RATE))
    for i in range(n):
        t = i / RATE
        env = 1.0
        if i < atk:
            env = i / atk
        elif i > n - rel:
            env = max(0.0, (n - i) / rel)
        # Slight vibrato keeps pyin from locking onto a dead-flat partial.
        vib = 1.0 + 0.004 * math.sin(2 * math.pi * 5.0 * t)
        s = math.sin(2 * math.pi * freq * vib * t) + 0.18 * math.sin(4 * math.pi * freq * vib * t)
        out.append(0.42 * env * s)
    return out


def build() -> bytes:
    total = int(PATTERN_BEATS * SPB * RATE)
    buf = [0.0] * total
    for onset_beats, midi, len_beats in NOTES:
        start = int(onset_beats * SPB * RATE)
        for j, v in enumerate(tone(midi, len_beats * SPB)):
            if start + j < total:
                buf[start + j] += v
    frames = b"".join(
        struct.pack("<h", max(-32768, min(32767, int(v * 32767)))) for v in buf
    )
    return frames


def main() -> int:
    dest = pathlib.Path(sys.argv[1])
    dest.parent.mkdir(parents=True, exist_ok=True)
    frames = build()
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    print(f"wrote {dest}  {len(frames) / 2 / RATE:.3f}s  {len(NOTES)} notes")
    print("ground-truth intervals (beats):", INTERVALS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
