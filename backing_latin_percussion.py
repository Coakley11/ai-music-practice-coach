"""Backing Engine 2.0, slice 3: a recorded Latin percussionist next to the drummer.

The hits are real recordings (``assets/instruments/latin_percussion``, VCSL, CC0). The percussionist plays only
when ``MUSIC_LATIN_GROOVES`` is on (``backing_latin_grooves.enabled``), the pack is present and
``MUSIC_LATIN_PERCUSSION`` is not "0" (for A/B listening), and only in these styles:

* **Latin jazz** -- claves on the 2-3 son clave (the drum kit's cross-stick clave steps aside, so it is not
  doubled), a conga + tumba tumbao (heel-toe taps, the slap on 2, open tones on 4 and the "and" of 4) and, at Heavy
  intensity, the bongo bell (cowbell) on the beat. The drummer keeps the cascara.
* **Samba** -- the ganza (shaker) in sixteenths with the accent on the last sixteenth of each beat, the
  tamborim / pandeiro part on the partido-alto figure (played by the tambourine's jingles) and the agogo bells; they
  replace the drum kit's shaker-on-the-hi-hat and partido-alto rim. Light intensity drops the agogo and thins the
  shaker to eighths.
* **Bossa nova** -- only a quiet shaker in eighths under the existing Bossa groove (never a clave).

Every hit lands on the engine's own groove time; velocities pick the recording's layer, so a soft tap sounds
soft rather than just quieter. Pattern sources: standard teaching patterns (tumbao, son clave, samba ganza /
partido alto). The agogo figure is a common samba-school pattern and is flagged for listening.
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass

import numpy as np

import backing_latin_grooves as _lg

PACK = pathlib.Path(__file__).resolve().parent / "assets" / "instruments" / "latin_percussion"
BOSSA = "Bossa nova"
STYLES = frozenset({_lg.LATIN_JAZZ, _lg.SAMBA, BOSSA})

# Peak-free level of each voice at velocity 1 (hits are energy-normalised by the pack loader), set so the
# percussion sits under the kit: measured with the stem check in tests/test_backing_latin_percussion.py.
LEVEL = {
    "clave": 0.0062,
    "conga_open": 0.0105,
    "conga_muted": 0.0080,
    "tumba_open": 0.0110,
    "cowbell": 0.0052,
    "cowbell_muted": 0.0046,
    "shaker_down": 0.0036,
    "shaker_up": 0.0036,
    "tamb": 0.0050,
    "agogo_high": 0.0044,
    "agogo_low": 0.0044,
    "cabasa": 0.0030,
}
# Bossa's shaker is felt rather than heard.
BOSSA_SHAKER_LEVEL = 0.55
# Each style's percussion against its rhythm layer (drums + bass + percussion, before the mix is levelled), measured
# with the stem spy in tests/test_backing_latin_percussion.py: Samba's percussion drives the groove (about -10 dB),
# Latin jazz's congas and claves sit just under the kit (about -10 dB), Bossa's shaker stays in the background
# (about -22 dB).
STYLE_GAIN = {"Samba": 1.6, "Latin jazz": 1.33, "Bossa nova": 1.25}


def style_gain(style: str) -> float:
    return float(STYLE_GAIN.get(str(style), 1.0))


def enabled() -> bool:
    """The percussionist plays: the Latin grooves are on, the pack is present and it is not switched off."""
    if not _lg.enabled():
        return False
    if str(os.environ.get("MUSIC_LATIN_PERCUSSION") or "").strip().lower() in {"0", "false", "no", "off"}:
        return False
    return (PACK / "manifest.json").is_file()


def plays(style: str) -> bool:
    return enabled() and str(style) in STYLES


def replaced_kit_parts(style: str) -> tuple[str, ...]:
    """Drum-kit grid parts a real percussion part takes over (so nothing is played twice)."""
    if not plays(style):
        return ()
    if style == _lg.SAMBA:
        return ("hat_beats", "cross_stick")  # shaker -> ganza, partido-alto rim -> tamborim
    if style == _lg.LATIN_JAZZ:
        return ("cross_stick",)  # the claves play the clave
    return ()


@dataclass(frozen=True)
class PercHit:
    beat: float  # offset in the 4/4 bar, quarter = 1.0
    voice: str
    velocity: float  # 0..1: picks the recording's layer and scales its level


# --- Patterns (one 4/4 bar) --------------------------------------------------------------------------------

# Conga tumbao in eighths: heel, toe, slap, toe | heel, toe, open (conga), open (tumba).
_TUMBAO = (
    (0.0, "conga_muted", 0.22), (0.5, "conga_muted", 0.16), (1.0, "conga_muted", 0.92), (1.5, "conga_muted", 0.16),
    (2.0, "conga_muted", 0.22), (2.5, "conga_muted", 0.16), (3.0, "conga_open", 0.82), (3.5, "tumba_open", 0.86),
)
# Samba agogo over two 2/4 bars, sixteenth steps: H . L . . H . L | H . L . . H L .
_AGOGO_HIGH = (0, 5, 8, 13)
_AGOGO_LOW = (2, 7, 10, 14)


def bar_hits(style: str, bar_number: int, *, intensity: str = "Medium") -> list[PercHit]:
    """What the percussionist plays in bar ``bar_number`` (0-based from the start of the form)."""
    light = str(intensity) == "Light"
    heavy = str(intensity) == "Heavy"
    hits: list[PercHit] = []
    if style == _lg.LATIN_JAZZ:
        side = int(bar_number) % 2
        hits += [PercHit(b, "clave", 0.82) for b in _lg.SON_CLAVE_2_3[side]]
        for b, voice, vel in _TUMBAO:
            if light and voice == "conga_muted" and vel < 0.5:
                continue  # Light: the slap and the open tones only
            hits.append(PercHit(b, voice, vel))
        if heavy:
            hits += [PercHit(float(b), "cowbell", 0.85) for b in range(4)]
            hits += [PercHit(b + 0.5, "cowbell_muted", 0.5) for b in range(4)]
    elif style == _lg.SAMBA:
        for step in range(16):
            if light and step % 2:
                continue
            accent = step % 4 == 3
            hits.append(PercHit(step * 0.25, "shaker_up" if step % 2 else "shaker_down", 0.95 if accent else 0.45))
        hits += [PercHit(b, "tamb", 0.75) for b in _lg.PARTIDO_ALTO]
        if not light:
            hits += [PercHit(s * 0.25, "agogo_high", 0.7) for s in _AGOGO_HIGH]
            hits += [PercHit(s * 0.25, "agogo_low", 0.65) for s in _AGOGO_LOW]
    elif style == BOSSA:
        step = 1.0 if light else 0.5
        b = 0.0
        while b < 4.0:
            on_beat = b == int(b)
            hits.append(PercHit(b, "shaker_down" if on_beat else "shaker_up", (0.5 if on_beat else 0.34) * BOSSA_SHAKER_LEVEL))
            b += step
    return sorted(hits, key=lambda h: (h.beat, h.voice))


# --- Playing ---------------------------------------------------------------------------------------------

def _pack():
    import backing_drum_samples as _samples

    return _samples.SamplePack(str(PACK))


def play_bar(
    audio: np.ndarray,
    sr: int,
    hits: list[PercHit],
    place,
    *,
    touch: float = 1.0,
    intensity: float = 1.0,
    seed: int = 0,
) -> None:
    """Add ``hits`` to ``audio``. ``place(beat)`` returns the hit's start in seconds (the engine's groove time)."""
    if not hits:
        return
    pack = _pack()
    for i, h in enumerate(hits):
        if not pack.has(h.voice):
            continue
        vel = max(0.0, min(1.0, float(h.velocity) * float(touch)))
        rr = (int(seed) * 7 + i * 3 + int(h.beat * 8)) & 0xFFFF
        sample = pack.hit(h.voice, vel, rr, int(sr))
        start = int(float(place(h.beat)) * sr)
        if start < 0 or start >= len(audio):
            continue
        # A little variation, like a hand: +-6 % level, deterministic per hit.
        wobble = 1.0 + 0.06 * (((rr * 2654435761) & 0xFFFF) / 0xFFFF * 2.0 - 1.0)
        gain = LEVEL.get(h.voice, 0.004) * (0.35 + 0.65 * vel) * float(intensity) * wobble
        end = min(len(audio), start + len(sample))
        audio[start:end] += sample[: end - start] * gain


def renderer_tag() -> str:
    """Part of the take's identity: audio rendered with the percussionist is never replayed as without it."""
    if not enabled():
        return ""
    import hashlib

    return "+perc-" + hashlib.sha1((PACK / "manifest.json").read_bytes()).hexdigest()[:8]
