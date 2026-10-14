"""Synthetic performance audio for MC4 tests and upload proofs (no external files).

``phrase_wav`` renders timed notes (beats at a BPM) as a plucked/blown tone with a few
harmonics and a short envelope, with optional leading silence, so transcription,
alignment and span scoring can be checked against known ground truth.
"""

from __future__ import annotations

import io
import wave
from typing import Sequence

import numpy as np

SR = 22050

NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name: str) -> int:
    """'Bb4' → 70, 'F#3' → 54."""
    letter = name[0].upper()
    rest = name[1:]
    acc = 0
    while rest and rest[0] in "#b♯♭":
        acc += 1 if rest[0] in "#♯" else -1
        rest = rest[1:]
    octave = int(rest or 4)
    return 12 * (octave + 1) + NOTE_PC[letter] + acc


def _tone(m: int, dur: float, *, amp: float = 0.35) -> np.ndarray:
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    f = 440.0 * 2 ** ((m - 69) / 12)
    wave_ = sum((0.6 ** k) * np.sin(2 * np.pi * f * (k + 1) * t) for k in range(4))
    attack = min(n, int(0.012 * SR))
    release = min(n, int(0.05 * SR))
    env = np.ones(n)
    if attack:
        env[:attack] = np.linspace(0, 1, attack)
    if release:
        env[-release:] = np.linspace(1, 0, release)
    env *= np.exp(-1.2 * t)  # gentle decay
    return (amp * wave_ * env).astype(np.float32)


def phrase_wav(
    notes: Sequence[tuple[str | int, float, float]],
    *,
    bpm: int = 100,
    lead_silence_sec: float = 0.0,
    tail_sec: float = 0.4,
    repeat: int = 1,
    loop_beats: float | None = None,
) -> bytes:
    """``notes``: (pitch, start_beat, beats). Repeats every ``loop_beats`` beats ``repeat`` times."""
    beat = 60.0 / bpm
    span_beats = loop_beats if loop_beats is not None else max(s + d for _p, s, d in notes)
    total = lead_silence_sec + repeat * span_beats * beat + tail_sec
    buf = np.zeros(int(total * SR) + 1, dtype=np.float32)
    for r in range(repeat):
        for pitch, start, dur in notes:
            m = midi(pitch) if isinstance(pitch, str) else int(pitch)
            t0 = lead_silence_sec + (r * span_beats + start) * beat
            tone = _tone(m, dur * beat * 0.92)
            i = int(t0 * SR)
            buf[i : i + tone.size] += tone[: max(0, buf.size - i)]
    peak = float(np.max(np.abs(buf))) or 1.0
    pcm = (buf / peak * 0.8 * 32767).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out.getvalue()


# Ground-truth phrases on the F-major ii–V–I (Gm7 → C7 → Fmaj7), one bar each, 4/4.
# Guide tones: Gm7 B♭(3) F(7) · C7 E(3) B♭(7) · Fmaj7 A(3) E(7).
II_V_I_GUIDE = [
    ("Bb4", 0, 1), ("A4", 1, 1), ("G4", 2, 1), ("F4", 3, 1),        # Gm7: 3rd … 7th
    ("Bb4", 4, 1), ("G4", 5, 1), ("E4", 6, 1), ("G4", 7, 1),        # C7: B♭ kept (3rd→7th), E
    ("A4", 8, 2), ("C5", 10, 1), ("A4", 11, 1),                     # Fmaj7: B♭ → A (7th → 3rd)
]
TWO_CHORD_TARGETS = [  # Gm7 → C7 (one bar each): chord tones, landing E (3rd) on beat 1 of C7
    ("G4", 0, 1), ("Bb4", 1, 1), ("D5", 2, 1), ("F4", 3, 1),
    ("E4", 4, 1), ("G4", 5, 1), ("Bb4", 6, 1), ("C5", 7, 1),
]
