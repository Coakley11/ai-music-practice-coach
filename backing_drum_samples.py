"""Recorded drum hits for the kit. Used only while the kit is switched on.

A pack is a folder of mono FLAC hits with a ``manifest.json`` mapping each voice to its velocity layers,
softest first, each holding its round robins. A hit is decoded the first time it is played and kept in a
cache with a fixed memory limit, so memory follows what a song plays and not the size of the library.
"""

from __future__ import annotations

import json
import os
import pathlib
import threading
from collections import OrderedDict
from functools import lru_cache

import numpy as np

DEFAULT_PACK = pathlib.Path(__file__).resolve().parent / "assets" / "drum_kit"
CYMBAL_VOICES = frozenset({"closed", "half", "three", "open", "pedal", "ride", "bell", "crash", "sizzle"})
# How much of each hit is level-matched to today's voice. A real cymbal keeps ringing after this.
_MATCH_SECONDS = {"closed": 0.04, "half": 0.09, "three": 0.09, "open": 0.09, "pedal": 0.14, "ride": 0.32, "bell": 0.32, "crash": 0.45, "sizzle": 0.45}
# Harder styles push the drum recordings into gentle saturation, as a hard-hitting mix does.
_DRIVE = {"Rock groove": {"kick_close": 1.9, "snare_close": 1.7, "rimshot_close": 1.5, "tom_low": 1.3, "tom_high": 1.3}, "Funk groove": {"kick_close": 1.3, "snare_close": 1.25}}
# Funk's snare and kick stop sooner, so the syncopation stays clear.
_TIGHTEN = {"Funk groove": {"kick_close": 16.0, "snare_close": 9.0, "snare": 9.0}}


def cache_limit_bytes() -> int:
    try:
        return max(8, int(os.environ.get("MUSIC_SAMPLE_CACHE_MB") or 96)) * 1024 * 1024
    except ValueError:
        return 96 * 1024 * 1024


class _HitCache:
    """Least recently played hits go first. Safe for the app's background render threads."""

    def __init__(self) -> None:
        self._items: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._lock = threading.Lock()
        self.bytes = 0

    def get(self, key: tuple) -> np.ndarray | None:
        with self._lock:
            hit = self._items.get(key)
            if hit is not None:
                self._items.move_to_end(key)
            return hit

    def put(self, key: tuple, value: np.ndarray) -> None:
        with self._lock:
            if key in self._items:
                return
            self._items[key] = value
            self.bytes += int(value.nbytes)
            limit = cache_limit_bytes()
            while self.bytes > limit and len(self._items) > 1:
                _, old = self._items.popitem(last=False)
                self.bytes -= int(old.nbytes)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.bytes = 0


HITS = _HitCache()


def pack_settings() -> tuple[str, str]:
    """(pack folder, mode). The recorded kit is the default; ``MUSIC_DRUM_PACK_DIR=none`` uses the synthesized kit."""
    folder = str(os.environ.get("MUSIC_DRUM_PACK_DIR") or "").strip()
    if folder.lower() == "none":
        return "", ""
    mode = str(os.environ.get("MUSIC_DRUM_PACK_MODE") or "full").strip().lower()
    mode = mode if mode in {"cymbals", "full"} else "full"
    if folder:
        return folder, mode
    return (str(DEFAULT_PACK), mode) if (DEFAULT_PACK / "manifest.json").is_file() else ("", "")


@lru_cache(maxsize=4)
def _manifest(folder: str) -> dict[str, list[list[str]]]:
    return json.loads((pathlib.Path(folder) / "manifest.json").read_text(encoding="utf-8"))


def pack_token() -> str:
    """Names the pack's contents, so saved audio from another pack is never replayed as this one."""
    import hashlib

    folder, mode = pack_settings()
    if not folder:
        return "synth"
    return mode + "-" + hashlib.sha1((pathlib.Path(folder) / "manifest.json").read_bytes()).hexdigest()[:8]


def _shape(x: np.ndarray, voice: str, style: str, sr: int) -> np.ndarray:
    tighten = _TIGHTEN.get(style, {}).get(voice)
    if tighten:
        x = x * np.exp(-np.arange(len(x), dtype=np.float32) / sr * float(tighten)).astype(np.float32)
    drive = _DRIVE.get(style, {}).get(voice)
    if drive:
        peak = float(np.max(np.abs(x))) or 1.0
        x = (np.tanh(x / peak * float(drive)) * peak).astype(np.float32)
    if voice in {"ride", "bell"}:
        # A close stick transient would set the track's peak and pull the whole mix down: ease only the very top.
        ceiling = 5.0 * float(np.sqrt(np.mean(x[: int(0.3 * sr)].astype(np.float64) ** 2)))
        if ceiling > 0:
            x = (np.tanh(x / ceiling) * ceiling).astype(np.float32)
    return x


def _load(folder: str, voice: str, name: str, sr: int, style: str = "") -> np.ndarray:
    key = (folder, name, sr, style)
    hit = HITS.get(key)
    if hit is not None:
        return hit
    import soundfile as sf

    x, file_sr = sf.read(str(pathlib.Path(folder) / name), dtype="float32", always_2d=False)
    if file_sr != sr:
        n = int(round(len(x) * sr / file_sr))
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    x = _shape(x, voice, style, sr)
    window = x[: max(1, int(_MATCH_SECONDS.get(voice, 10.0) * sr))]
    energy = float(np.sum(window.astype(np.float64) ** 2)) / sr
    hit = (x / np.sqrt(energy)).astype(np.float32) if energy > 0 else x
    HITS.put(key, hit)
    return hit


class SamplePack:
    def __init__(self, folder: str, mode: str = "full") -> None:
        self.folder = str(folder)
        self.mode = mode

    def has(self, voice: str) -> bool:
        if self.mode == "cymbals" and voice not in CYMBAL_VOICES:
            return False
        return bool(_manifest(self.folder).get(voice))

    def hit(self, voice: str, velocity: float, rr: int, sr: int, style: str = "") -> np.ndarray:
        """The recorded hit for this velocity. Louder layers sound harder as well as louder."""
        layers = _manifest(self.folder)[voice]
        index = int(round(min(1.0, max(0.0, float(velocity))) * (len(layers) - 1)))
        repeats = layers[index]
        return _load(self.folder, voice, repeats[abs(int(rr)) % len(repeats)], int(sr), style)
