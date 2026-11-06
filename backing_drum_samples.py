"""Recorded drum hits for the improved kit. Evaluation only: nothing uses this unless a pack is named.

A pack is a folder of mono FLAC hits with a ``manifest.json`` mapping each voice to its velocity layers,
softest first, each holding its round robins. Hits load on first use and stay cached for the process.
"""

from __future__ import annotations

import json
import os
import pathlib
from functools import lru_cache

import numpy as np

CYMBAL_VOICES = frozenset({"closed", "half", "three", "open", "pedal", "ride", "bell", "crash", "sizzle"})
# How much of each hit is level-matched to today's voice. A real cymbal keeps ringing after this.
_MATCH_SECONDS = {"closed": 0.04, "half": 0.09, "three": 0.09, "open": 0.09, "pedal": 0.14, "ride": 0.32, "bell": 0.32, "crash": 0.45, "sizzle": 0.45}


def pack_settings() -> tuple[str, str]:
    """(pack folder, mode), where mode is "cymbals" or "full". Empty when no pack is named."""
    folder = str(os.environ.get("MUSIC_DRUM_PACK_DIR") or "").strip()
    mode = str(os.environ.get("MUSIC_DRUM_PACK_MODE") or "full").strip().lower()
    return (folder, mode if mode in {"cymbals", "full"} else "full") if folder else ("", "")


@lru_cache(maxsize=4)
def _manifest(folder: str) -> dict[str, list[list[str]]]:
    return json.loads((pathlib.Path(folder) / "manifest.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1024)
def _load(folder: str, voice: str, name: str, sr: int) -> np.ndarray:
    import soundfile as sf

    x, file_sr = sf.read(str(pathlib.Path(folder) / name), dtype="float32", always_2d=False)
    if file_sr != sr:
        n = int(round(len(x) * sr / file_sr))
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    window = x[: max(1, int(_MATCH_SECONDS.get(voice, 10.0) * sr))]
    energy = float(np.sum(window.astype(np.float64) ** 2)) / sr
    return (x / np.sqrt(energy)).astype(np.float32) if energy > 0 else x


class SamplePack:
    def __init__(self, folder: str, mode: str = "full") -> None:
        self.folder = str(folder)
        self.mode = mode

    def has(self, voice: str) -> bool:
        if self.mode == "cymbals" and voice not in CYMBAL_VOICES:
            return False
        return bool(_manifest(self.folder).get(voice))

    def hit(self, voice: str, velocity: float, rr: int, sr: int) -> np.ndarray:
        """The recorded hit for this velocity. Louder layers sound harder as well as louder."""
        layers = _manifest(self.folder)[voice]
        index = int(round(min(1.0, max(0.0, float(velocity))) * (len(layers) - 1)))
        repeats = layers[index]
        return _load(self.folder, voice, repeats[abs(int(rr)) % len(repeats)], int(sr))
