"""One-off: extract backing audio helpers from main app."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src_lines = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8").splitlines(keepends=True)

header = '''"""Backing track synthesis and groove inference (no Streamlit UI)."""

from __future__ import annotations

import io
import wave

import numpy as np

from music_theory import NOTE_TO_MIDI, normalize_root, split_chord

try:
    from practice_studio import song_groove_seed
except ImportError:

    def song_groove_seed(title: str, artist: str = "") -> int:
        return 0


__all__ = [
    "chord_notes",
    "bass_note",
    "infer_groove_style",
    "synthesize_chords_to_numpy",
    "pcm16_wav_bytes_from_float",
    "generate_backing_track",
    "backing_bytes_to_float",
    "wav_bytes_from_float",
]


'''

ranges = [(576, 659), (3527, 4008)]
chunks = []
for a, b in ranges:
    chunks.append("".join(src_lines[a - 1 : b]))

(ROOT / "backing_audio.py").write_text(header + "\n".join(chunks), encoding="utf-8")
print("Wrote backing_audio.py")
