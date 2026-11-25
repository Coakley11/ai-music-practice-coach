"""Backing Engine 2.0, slice 3: Samba and Latin Jazz as grooves of their own.

Until now a Latin or Samba jam played through the Bossa nova groove (``normalize_groove_label`` maps
"latin" and "samba" to "Bossa nova"). This module holds the rhythm vocabulary of two new engine styles:

* ``SAMBA`` -- driving Brazilian samba in 4/4 written as two 2/4 samba bars per bar (the app's BPM is
  the quarter note): a surdo-style kick and bass (short "1", pickup on the "a", long accented "2"),
  sixteenth-note shaker on the closed hi-hat with the accent on the last sixteenth of each beat, and
  the partido-alto figure on the rim and in the piano. No Afro-Cuban clave.
* ``LATIN_JAZZ`` -- Afro-Cuban Latin jazz in straight eighths on a two-bar 2-3 son clave: cross-stick
  plays the clave, the hi-hat plays the cascara (the timbale shell pattern; a drum set substitutes the
  closed hat), the kick plays the tumbao's "and of 2" and 4, the bass plays a tumbao (the next chord's
  root anticipated on 4 and tied over the bar line) and the piano plays sparse syncopated comping,
  with a montuno only where the harmony suits one (``montuno_fits``).

Bossa nova keeps its own existing groove and is not changed here.

Everything is data plus small pure functions; ``backing_audio`` reads them only when a take's style is
one of ``LATIN_STYLES``, so every other style (and every catalog song) renders exactly as before.
``MUSIC_LATIN_GROOVES`` (default off) decides whether a Creative "Latin" / "Samba" jam is routed here
(``engine_style_for``); with it off nothing reaches these styles.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

SAMBA = "Samba"
LATIN_JAZZ = "Latin jazz"
LATIN_STYLES = frozenset({SAMBA, LATIN_JAZZ})
# Styles that must never carry an Afro-Cuban clave.
BRAZILIAN_STYLES = frozenset({SAMBA, "Bossa nova"})


def enabled() -> bool:
    """``MUSIC_LATIN_GROOVES`` on: Creative Latin / Samba jams play their own grooves (default off)."""
    return str(os.environ.get("MUSIC_LATIN_GROOVES") or "").strip().lower() in {"1", "true", "yes", "on"}


def engine_style_for(label: str) -> str | None:
    """The new engine style for a Creative / groove label, or None to keep today's mapping.

    Only when the switch is on. "Bossa" never maps here: Bossa nova stays Bossa nova.
    """
    if not enabled():
        return None
    low = str(label or "").strip().lower()
    if "bossa" in low:
        return None
    if "samba" in low:
        return SAMBA
    if "latin" in low:
        return LATIN_JAZZ
    return None


# --- Rhythms: beat offsets in a 4/4 bar (quarter = 1.0) ---------------------------------------------------

# Son clave, two bars. 2-3: the "2" side first (beats 2 and 3), then the "3" side (1, and of 2, 4).
SON_CLAVE_2_3 = ((1.0, 2.0), (0.0, 1.5, 3.0))
SON_CLAVE_3_2 = (SON_CLAVE_2_3[1], SON_CLAVE_2_3[0])
# Cascara (timbale shell) in eighths; each half lines up with the clave side it is played against.
#   3 side: X.X.XX.X     2 side: .XX.X.X.
CASCARA_3_SIDE = (0.0, 1.0, 2.0, 2.5, 3.5)
CASCARA_2_SIDE = (0.5, 1.0, 2.0, 3.0)
CASCARA_2_3 = (CASCARA_2_SIDE, CASCARA_3_SIDE)
# Tumbao: the bass (and the kick under it) on the "and" of 2 and on 4; beat 1 is left open.
TUMBAO_BEATS = (1.5, 3.0)

# Partido alto over two 2/4 bars (= one 4/4 bar here), sixteenth grid steps 0..15:
#   . x . . x . x . | x . x . . x . .   -> steps 1, 4, 6, 8, 10, 13
PARTIDO_ALTO_STEPS = (1, 4, 6, 8, 10, 13)
PARTIDO_ALTO = tuple(s * 0.25 for s in PARTIDO_ALTO_STEPS)
# Surdo-style samba kick: each 2/4 half is "1 . . a | 2 . . a" (the "a" pickups lead into the next beat).
SAMBA_KICK = (0.0, 0.75, 1.0, 1.75, 2.0, 2.75, 3.0, 3.75)
SIXTEENTHS = tuple(i * 0.25 for i in range(16))


def _frac(beat: float) -> float:
    return round(float(beat) % 1.0, 3)


def samba_kick_accent(beat: float) -> float:
    """Surdo shape: the samba "2" (beats 2 and 4 of the 4/4 bar) is the strong, open stroke."""
    b = round(float(beat), 3)
    if b in (1.0, 3.0):
        return 1.0
    if b in (0.0, 2.0):
        return 0.62
    return 0.42  # the "a" pickups


def samba_shaker_accent(beat: float) -> float:
    """Ganzá on the closed hat: accent on the last sixteenth of each beat, lighter elsewhere."""
    f = _frac(beat)
    return {0.0: 0.62, 0.25: 0.42, 0.5: 0.55, 0.75: 1.0}.get(f, 0.5)


def cascara_accent(beat: float) -> float:
    return 1.0 if _frac(beat) == 0.0 else 0.78


@dataclass(frozen=True)
class LatinBar:
    """One bar of a Latin groove: the grid the engine plays plus per-hit accents."""

    style: str
    side: int  # 0 or 1: which bar of the two-bar cycle
    grid: dict

    def hat_accent(self, beat: float) -> float:
        if self.style == SAMBA:
            return samba_shaker_accent(beat)
        return cascara_accent(beat)

    def kick_accent(self, beat: float) -> float:
        if self.style == SAMBA:
            return samba_kick_accent(beat)
        return 1.0 if round(float(beat), 3) == 3.0 else 0.8


def bar(style: str, bar_number: int, *, intensity: str = "Medium") -> LatinBar:
    """The grid for bar ``bar_number`` (0-based, counted from the start of the form) of ``style``.

    Keys match ``backing_audio``'s bar patterns (beat offsets in a 4/4 bar). ``intensity`` thins or fills
    the kit the way a drummer would: Light drops the kick pickups and half the shaker, Heavy adds the
    hi-hat on every eighth of the cascara's gaps (Latin jazz) or keeps every pickup (Samba).
    """
    side = int(bar_number) % 2
    light = str(intensity) == "Light"
    if style == SAMBA:
        kick = [b for b in SAMBA_KICK if not (light and _frac(b) == 0.75)]
        hats = [b for b in SIXTEENTHS if not (light and _frac(b) in (0.25, 0.5))]
        grid = {
            "kick_beats": kick,
            "snare_beats": [],
            "hat_beats": hats,
            "ghost_snare": [],
            "cross_stick": list(PARTIDO_ALTO),
            "bass_beats": [0.0, 0.75, 1.0, 2.0, 2.75, 3.0],
            "comp_beats": list(PARTIDO_ALTO),
            "comp_dur": 0.26,
            "hat_open_ands": [],
        }
        return LatinBar(style, side, grid)
    if style == LATIN_JAZZ:
        clave = list(SON_CLAVE_2_3[side])
        cascara = list(CASCARA_2_3[side])
        if str(intensity) == "Heavy":
            cascara = sorted(set(cascara) | {0.0, 1.0, 2.0, 3.0})
        grid = {
            "kick_beats": [3.0] if light else list(TUMBAO_BEATS),
            "snare_beats": [],
            "hat_beats": cascara,
            "ghost_snare": [],
            "cross_stick": clave,
            "bass_beats": list(TUMBAO_BEATS),
            "comp_beats": [0.0, 1.5, 3.5],
            "comp_dur": 0.36,
            "hat_open_ands": [],
        }
        return LatinBar(style, side, grid)
    raise ValueError(f"not a Latin groove: {style!r}")


def has_clave(style: str) -> bool:
    """Whether a style's groove carries the son clave (never Bossa nova or Samba)."""
    return style == LATIN_JAZZ


# --- Montuno: only where the harmony suits one ---------------------------------------------------------

_MONTUNO_QUALITIES = ("", "m", "7", "m7", "maj7", "6", "m6", "9", "m9")


def montuno_fits(chords_per_bar: list[list[str]], quality_of) -> bool:
    """A montuno suits a passage of at most two chords a bar, in plain qualities, that repeats.

    ``chords_per_bar`` is each bar's chord symbols; ``quality_of(symbol)`` returns its quality suffix
    ("m7", "7", "maj7", ...). Altered dominants, half-diminished and slash-heavy harmony get the sparse
    syncopated comping instead: a montuno's repeated figure would fight them.
    """
    if not chords_per_bar:
        return False
    for chords in chords_per_bar:
        if len(chords) > 2:
            return False
        for c in chords:
            if "/" in c or str(quality_of(c)) not in _MONTUNO_QUALITIES:
                return False
    distinct = {c for chords in chords_per_bar for c in chords}
    return len(distinct) <= 4
