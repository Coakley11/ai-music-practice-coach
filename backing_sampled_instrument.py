"""A pitched instrument played from recordings. Holds no audio of its own: see ``backing_sample_cache``.

A pack is a folder with ``manifest.json`` and mono FLAC notes::

    {"sr": 44100, "zones": [{"key": 38, "layers": [
        {"velocity": 0.6, "takes": [{"file": "d2_m_a.flac", "cents": -3.1, "gain": 1.2}, ...]}, ...]}, ...]}

Layers run softest first. ``cents`` is how far the recording sits from the zone's key and is
corrected on playback; ``gain`` evens the takes out, so a zone's layers differ by what was played.
"""

from __future__ import annotations

import json
import pathlib
import zlib
from functools import lru_cache

import numpy as np

import backing_sample_cache as _cache


@lru_cache(maxsize=8)
def _release_curve(n: int) -> np.ndarray:
    return np.exp(-3.0 * np.arange(n, dtype=np.float32) / max(1, n)).astype(np.float32)


class SampledInstrument:
    def __init__(self, folder: str | pathlib.Path) -> None:
        self.folder = pathlib.Path(folder)
        manifest = json.loads((self.folder / "manifest.json").read_text(encoding="utf-8"))
        self.sr = int(manifest["sr"])
        self.zones = sorted(manifest["zones"], key=lambda z: z["key"])
        self.manifest = manifest
        self.dead = list(manifest.get("dead", []))  # unpitched strokes, for instruments that have them
        self.variants: dict = {}  # articulations made from a recording, e.g. a palm mute: name -> fn(int16 audio, sr)
        self._keys = np.array([z["key"] for z in self.zones])

    def _zone(self, midi: int) -> dict:
        return self.zones[int(np.argmin(np.abs(self._keys - midi)))]

    def _take(self, zone: dict, velocity: float, seed: str, avoid: dict | None) -> dict:
        """The layer nearest ``velocity``, nudged by a little human unevenness, the same every time for a seed."""
        roll = zlib.crc32(seed.encode("utf-8"))
        v = float(velocity) + ((roll % 1000) / 1000.0 - 0.5) * 0.12
        layer = min(zone["layers"], key=lambda la: abs(la["velocity"] - v))
        takes = layer["takes"]
        i = (roll >> 10) % len(takes)
        if avoid is not None and len(takes) > 1:
            slot = (zone["key"], layer["velocity"])
            if avoid.get(slot) == i:  # the same recording twice in a row gives the game away
                i = (i + 1) % len(takes)
            avoid[slot] = i
        return takes[i]

    def _audio(self, name: str, variant: str | None = None) -> np.ndarray:
        key = (str(self.folder), name, variant)
        x = _cache.SHARED.get(key)
        if x is None:
            if variant is not None:
                x = self.variants[variant](self._audio(name), self.sr)
            else:
                import soundfile as sf

                x, _sr = sf.read(str(self.folder / name), dtype="int16", always_2d=False)
            _cache.SHARED.put(key, x)
        return x

    def add_note(
        self,
        bus: np.ndarray,
        sr: int,
        start_sec: float,
        held_sec: float,
        midi: int,
        gain: float,
        velocity: float,
        seed: str,
        avoid: dict | None = None,
        release_sec: float = 0.055,
        *,
        variant: str | None = None,
        offset_sec: float = 0.0,
        detune_cents: float = 0.0,
    ) -> None:
        """Mix one note into ``bus``, stopped ``held_sec`` in. Only the audio it uses is resampled."""
        start = int(max(0.0, start_sec) * sr)
        if gain <= 0.0 or start >= len(bus):
            return
        zone = self._zone(int(midi))
        take = self._take(zone, velocity, seed, avoid)
        x = self._audio(take["file"], variant)
        ratio = 2.0 ** ((int(midi) - zone["key"] + (detune_cents - float(take.get("cents", 0.0))) / 100.0) / 12.0) * self.sr / sr
        first = int(offset_sec * self.sr)
        held_n = max(1, int(max(0.02, held_sec) * sr))
        release_n = int(release_sec * sr)
        n = min(held_n + release_n, int((len(x) - 1 - first) / ratio), len(bus) - start)
        if n <= 0:
            return
        pos = first + np.arange(n, dtype=np.float64) * ratio
        i0 = pos.astype(np.int64)
        frac = (pos - i0).astype(np.float32)
        a = x[i0].astype(np.float32)
        seg = (a + (x[i0 + 1].astype(np.float32) - a) * frac) / 32768.0
        if n > held_n:
            seg[held_n:] *= _release_curve(release_n)[: n - held_n]
        bus[start : start + n] += seg * float(take.get("gain", 1.0)) * gain
