"""Backing Engine 2.0: a Samba percussion section played like musicians in a room (MUSIC_SAMBA_ENSEMBLE).

Off by default; needs MUSIC_LATIN_GROOVES (the Samba groove) and the recorded pack
``assets/instruments/brazilian_percussion`` (VCSL, CC0; see its README for what each voice is and stands for).

One 4/4 bar of the app is two 2/4 samba bars; inside each 2/4 bar the samba "1" and "2" are quarter notes. The parts
answer each other the way a bateria does:

* **Surdos** -- the low surdo (primeira) plays the strong, open "2" and a hand-muted touch on "1"; the high surdo
  (segunda) answers with an open "1" and a muted "2". At the end of a four-bar phrase the primeira leads into the next
  "2" with a pickup; at Heavy intensity the high surdo adds the cortador's syncopations.
* **Pandeiro** -- continuous sixteenths: thumb on the skin (with its jingles), fingertip, heel (a ghost note) and the
  accented fingertip on the last sixteenth of the beat; an open bass tone on the samba "2".
* **Tamborim** -- the teleco-teco figure across the two 2/4 bars; at Heavy, a short call into the next phrase.
* **Agogo** -- two alternating high / low figures, so the bells phrase over two bars instead of looping one.
* **Ganza** -- sixteenths, down / up strokes, accented on the last sixteenth of each beat.

Feel, from research on samba microtiming (Naveda, Gouyon, Guedes and Leman, "Microtiming patterns and interactions with
musical properties in samba music", JNMR 40(3), 2011: the third and fourth semiquavers of a beat are anticipated, the
low drums sit slightly late on the first): the third sixteenth is played a little early, the fourth earlier, the
surdos a touch late. On top, every stroke gets a small deterministic human variation of time and strength, sized
per instrument; repeated strokes rotate through the recordings' round robins (never the same take twice in a row);
the velocity picks the recording's dynamic layer, so soft strokes sound soft rather than turned down. A hand-muted
surdo stroke is damped, not shortened by pitch; nothing is pitch-shifted. Each recording carries a small room (a short
early-reflection + decay tail), so the section sounds like players in one room, not dry loops.
"""

from __future__ import annotations

import os
import pathlib
import zlib
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

PACK = pathlib.Path(__file__).resolve().parent / "assets" / "instruments" / "brazilian_percussion"
# MUSIC_SAMBA_AUTHENTIC: recordings of the real instruments (Freesound, CC0 / CC BY; credits in the pack's CREDITS.md and
# ATTRIBUTION.json) replace the stand-ins: surdos, the pandeiro's skin and jingles, the tamborim. The agogo and ganza are
# already the real instruments; the pandeiro shake keeps the tambourine (no authentic recording of it was found).
AUTHENTIC_PACK = pathlib.Path(__file__).resolve().parent / "assets" / "instruments" / "samba_authentic"
AUTHENTIC_VOICES = {
    "surdo_low": "surdo_low_open", "surdo_high": "surdo_high_open",
    "pandeiro_skin_muted": "pandeiro_bass", "pandeiro_skin_open": "pandeiro_bass", "pandeiro_jingle": "pandeiro_jingle",
    "tamborim": "tamborim_muted",
}
_ON = {"1", "true", "yes", "on"}

# Microtiming, in beats (quarter notes): position of the sixteenth inside the beat -> offset.
SIXTEENTH_SHIFT = {0: 0.0, 1: 0.0, 2: -0.028, 3: -0.036}
SURDO_LATE = 0.012
# Human variation per instrument: (timing spread in beats, strength spread as a fraction)
HUMAN = {
    "surdo": (0.008, 0.06), "pandeiro": (0.006, 0.10), "tamborim": (0.008, 0.10), "agogo": (0.010, 0.08), "ganza": (0.007, 0.14),
}
# Level of each voice at full strength (hits are energy-normalised by the loader): the section's internal balance,
# scaled (SECTION_LEVEL) so the section sits about 9 LU under the music even without MUSIC_BAND_BALANCE.
SECTION_LEVEL = 0.66
LEVEL = {
    "surdo_low": 0.0225, "surdo_high": 0.0080,
    "pandeiro_skin_muted": 0.0058, "pandeiro_skin_open": 0.0064, "pandeiro_jingle": 0.0036, "pandeiro_shake": 0.0030,
    "tamborim": 0.0056, "agogo_high": 0.0036, "agogo_low": 0.0036, "ganza_down": 0.0037, "ganza_up": 0.0037,
}
MUTE_TAU_SEC = 0.07  # a hand on the surdo's head: the ring dies this fast after the stroke
ROOM_WET = 0.16  # the room's level against the dry stroke
ROOM_RT60 = 0.42
ROOM_HIGHPASS_HZ = 150.0


def enabled() -> bool:
    try:
        import backing_latin_grooves as _lg

        if not _lg.enabled():
            return False
    except ImportError:
        return False
    if str(os.environ.get("MUSIC_SAMBA_ENSEMBLE") or "").strip().lower() not in _ON:
        return False
    return (PACK / "manifest.json").is_file()


AUTHENTIC_FAMILIES = ("surdo", "pandeiro", "tamborim")


def authentic_families() -> frozenset[str]:
    """Which instruments use the real recordings: MUSIC_SAMBA_AUTHENTIC=1 (all three) or a list such as
    "surdo,tamborim", so each instrument can be adopted on its own. Needs the section on and the pack present."""
    raw = str(os.environ.get("MUSIC_SAMBA_AUTHENTIC") or "").strip().lower()
    if not raw or not enabled() or not (AUTHENTIC_PACK / "manifest.json").is_file():
        return frozenset()
    if raw in _ON or raw == "all":
        return frozenset(AUTHENTIC_FAMILIES)
    return frozenset(p.strip() for p in raw.split(",") if p.strip() in AUTHENTIC_FAMILIES)


def authentic() -> bool:
    """Any instrument uses the real recordings (MUSIC_SAMBA_AUTHENTIC)."""
    return bool(authentic_families())


def renderer_tag() -> str:
    if not enabled():
        return ""
    import hashlib

    tag = "+samba1-" + hashlib.sha1((PACK / "manifest.json").read_bytes()).hexdigest()[:8]
    fams = authentic_families()
    if fams:
        tag += "-auth-" + "".join(f[0] for f in AUTHENTIC_FAMILIES if f in fams) + "-"
        tag += hashlib.sha1((AUTHENTIC_PACK / "manifest.json").read_bytes()).hexdigest()[:8]
    return tag


@dataclass(frozen=True)
class Stroke:
    beat: float  # where it is written in the 4/4 bar (quarter = 1.0), before the feel is applied
    voice: str
    velocity: float
    muted: bool = False


def _family(voice: str) -> str:
    return voice.split("_", 1)[0]


def _hash01(*parts) -> float:
    return (zlib.crc32(repr(parts).encode()) & 0xFFFFFF) / float(0xFFFFFF)


# --- The parts (one 4/4 bar = two 2/4 samba bars; sixteenth steps 0..15) -------------------------------------
_TELECO_TECO = (0, 2, 5, 7, 9, 11, 14)
# The tamborim's second figure (a common samba variation), chosen for some four-bar phrases.
_TAMBORIM_VARIATION = (0, 3, 6, 8, 10, 12, 14)
_AGOGO = (
    ((0, 5, 8, 13), (2, 7, 10, 14)),  # high, low
    ((0, 3, 8, 11), (2, 6, 10, 14)),
    ((0, 5, 8, 12), (2, 6, 10, 15)),
)


def bar_strokes(
    bar_number: int,
    *,
    intensity: str = "Medium",
    bar_in_section: int | None = None,
    section_bars: int = 0,
    seed: int = 0,
) -> list[Stroke]:
    """One bar of the section. With ``bar_in_section`` / ``section_bars`` the players phrase with the song: the
    primeira marks a new section, the section's last bar is a call into the next (surdo sixteenths, the tamborim's
    call, pandeiro pushing, the agogo laying out for it), the tamborim and agogo choose their figures per four-bar
    phrase, and small deterministic variations (seeded by the song) keep repeated bars from being copies."""
    light, heavy = intensity == "Light", intensity == "Heavy"
    pos = (bar_in_section if bar_in_section is not None else int(bar_number)) % 4
    phrase_end = pos == 3
    section_end = bool(section_bars) and bar_in_section is not None and bar_in_section == section_bars - 1
    section_start = bar_in_section == 0 and int(bar_number) > 0
    phrase = (int(bar_number) - pos) // 4
    rnd = lambda tag: _hash01("var", seed, int(bar_number), tag)  # noqa: E731
    s: list[Stroke] = []
    for half in (0.0, 2.0):
        # Surdos: primeira (low) open on the "2", muted touch on the "1"; segunda (high) open "1", muted "2".
        s.append(Stroke(half + 1.0, "surdo_low", 0.92))
        if section_start and half == 0.0:
            s.append(Stroke(half, "surdo_low", 0.72))  # the primeira marks the new section
        else:
            s.append(Stroke(half, "surdo_low", 0.34, muted=True))
        s.append(Stroke(half, "surdo_high", 0.46))  # the segunda answers; the primeira's "2" leads
        if not light:
            s.append(Stroke(half + 1.0, "surdo_high", 0.30, muted=True))
            if rnd(("dobra", half)) < 0.22:
                s.append(Stroke(half + 0.5, "surdo_high", 0.26, muted=True))  # a light syncopation, now and then
        if (phrase_end or section_end) and half == 2.0:
            s.append(Stroke(half + 0.75, "surdo_low", 0.55))  # the pickup into the next phrase's "2"
        if heavy:
            s.append(Stroke(half + 0.5, "surdo_high", 0.42, muted=True))  # cortador syncopations
            s.append(Stroke(half + 1.75, "surdo_high", 0.48))
    if section_end and not light:
        # The call into the next section: the surdos in sixteenths on the last beat, growing.
        s += [Stroke(3.25, "surdo_high", 0.5), Stroke(3.5, "surdo_low", 0.7), Stroke(3.75, "surdo_high", 0.68)]
    open_three = rnd("pandeiro_open3") < 0.3
    displaced = rnd("pandeiro_accent") < 0.2
    for beat in range(4):
        for k in range(4):
            b = beat + k * 0.25
            push = section_end and beat == 3 and not light
            if k == 0:
                if beat % 2 == 1 or (beat == 2 and open_three):
                    s.append(Stroke(b, "pandeiro_skin_open", 0.62))  # the open bass tone on the samba "2"
                else:
                    s.append(Stroke(b, "pandeiro_skin_muted", 0.55))
                s.append(Stroke(b, "pandeiro_jingle", 0.34))
            elif k == 3:
                s.append(Stroke(b, "pandeiro_jingle", 0.62 if (displaced and beat == 2) else 0.78))
            elif not light:
                if displaced and beat == 2 and k == 2:
                    s.append(Stroke(b, "pandeiro_jingle", 0.6))  # the accent moved a sixteenth earlier
                else:
                    s.append(Stroke(b, "pandeiro_jingle", (0.48 if push else 0.30) if k == 1 else (0.5 if push else 0.18)))
            if not light or k % 2 == 0:
                arch = 0.92 + 0.1 * np.sin(np.pi * (pos + beat / 4 + 0.5) / 4)  # the ganza breathes over the phrase
                v = 0.88 if k == 3 else (0.5 if k == 0 else 0.36)
                s.append(Stroke(b, "ganza_up" if k % 2 else "ganza_down", float(min(1.0, v * arch * (1.12 if push else 1.0)))))
    if heavy:
        s += [Stroke(b + 0.5, "pandeiro_shake", 0.4) for b in (1.0, 3.0)]
    if not light:
        figure = _TAMBORIM_VARIATION if _hash01("tamborim_phrase", seed, phrase) < 0.3 else _TELECO_TECO
        call = section_end or (heavy and phrase_end)
        for i, step in enumerate(figure):
            if call and step >= 12:
                continue
            s.append(Stroke(step * 0.25, "tamborim", 0.66 if i in (0, 4) else 0.48))
        if call:
            s += [Stroke(3.0 + k * 0.25, "tamborim", 0.5 + 0.1 * k) for k in range(4)]  # the call, growing
        high, low = _AGOGO[(int(bar_number) + int(_hash01("agogo_phrase", seed, phrase) * 3)) % len(_AGOGO)]
        for st in high:
            if not (section_end and st >= 12):  # the bells lay out for the call
                s.append(Stroke(st * 0.25, "agogo_high", 0.7))
        for st in low:
            if not (section_end and st >= 12):
                s.append(Stroke(st * 0.25, "agogo_low", 0.62))
    return sorted(s, key=lambda x: (x.beat, x.voice))


def performed_beat(stroke: Stroke, bar_number: int) -> float:
    """Where the stroke is played: the samba feel (anticipated 3rd / 4th sixteenths, surdos a touch late) plus a
    small human variation, deterministic for the bar and stroke."""
    k = int(round((stroke.beat % 1.0) / 0.25)) % 4
    fam = _family(stroke.voice)
    shift = SIXTEENTH_SHIFT.get(k, 0.0) if fam != "surdo" else SURDO_LATE
    spread = HUMAN.get(fam, (0.006, 0.1))[0]
    return stroke.beat + shift + spread * (2 * _hash01("t", bar_number, stroke.beat, stroke.voice) - 1)


def performed_velocity(stroke: Stroke, bar_number: int) -> float:
    spread = HUMAN.get(_family(stroke.voice), (0.006, 0.1))[1]
    return float(np.clip(stroke.velocity * (1 + spread * (2 * _hash01("v", bar_number, stroke.beat, stroke.voice) - 1)), 0.05, 1.0))


# --- Sound ------------------------------------------------------------------------------------------------
@lru_cache(maxsize=4)
def _room_ir(sr: int) -> np.ndarray:
    """A small room: three early reflections and a short diffuse decay (deterministic)."""
    n = int(ROOM_RT60 * sr)
    rng = np.random.default_rng(2024)
    t = np.arange(n) / sr
    tail = rng.normal(0, 1, n) * np.exp(-6.91 * t / ROOM_RT60)
    # darker as it decays: a one-pole low-pass on the tail
    from scipy import signal

    tail = signal.lfilter([0.35], [1, -0.65], tail)
    tail[: int(0.012 * sr)] = 0.0
    ir = tail / (np.sqrt(np.sum(tail ** 2)) + 1e-12)
    for d, g in ((0.007, 0.5), (0.013, 0.35), (0.021, 0.25)):
        ir[int(d * sr)] += g
    return ir.astype(np.float32)


END_FADE_SEC = 0.15
END_STILL_RINGING_DB = -30.0


def natural_end(x: np.ndarray, sr: int) -> np.ndarray:
    """A recording that stops while still ringing (louder than -30 dB re its peak at the end) fades over its last
    150 ms (at most 30 % of it) instead of stopping, the way a drum's ring dies away; one that has decayed is untouched."""
    n = len(x)
    if n < int(0.05 * sr):
        return x
    env = np.convolve(np.abs(x), np.ones(441) / 441, mode="same")
    tail = float(env[-int(0.02 * sr): -int(0.005 * sr)].mean())
    if 20 * np.log10(tail / (float(env.max()) + 1e-12) + 1e-12) <= END_STILL_RINGING_DB:
        return x
    k = max(2, min(int(END_FADE_SEC * sr), int(0.3 * n)))
    out = x.copy()
    out[-k:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, k))).astype(out.dtype)
    return out


@lru_cache(maxsize=256)
def _stroke_audio(voice: str, layer_file: str, sr: int, muted: bool, pack: str = "") -> np.ndarray:
    import soundfile as sf
    from scipy import signal

    x, file_sr = sf.read(str((pathlib.Path(pack) if pack else PACK) / layer_file), dtype="float32", always_2d=False)
    if file_sr != sr:  # sample-rate conversion only (the pack is 44.1 kHz): never a pitch change
        n = int(round(len(x) * sr / file_sr))
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    energy = float(np.sum(x.astype(np.float64) ** 2)) / sr
    x = x / np.sqrt(energy) if energy > 0 else x
    x = natural_end(x, sr)
    if muted:
        t = np.arange(len(x)) / sr
        hold = 0.015
        x = x * np.where(t < hold, 1.0, np.exp(-(t - hold) / MUTE_TAU_SEC)).astype(np.float32)
        x = x[: int(min(len(x), (hold + 6 * MUTE_TAU_SEC) * sr))]
    wet = signal.fftconvolve(x, _room_ir(sr))[: len(x) + int(ROOM_RT60 * sr)]
    # The room's low end is what makes a percussion section muddy: its reflections are high-passed at 150 Hz, so the
    # surdos keep their own body and only the room's air is added.
    wet = signal.sosfilt(signal.butter(4, ROOM_HIGHPASS_HZ, "highpass", fs=sr, output="sos"), wet)
    out = np.zeros(len(wet), dtype=np.float32)
    out[: len(x)] += x
    out += ROOM_WET * wet.astype(np.float32)
    return out


@lru_cache(maxsize=4)
def _read_manifest(folder: str) -> dict:
    import json

    return json.loads((pathlib.Path(folder) / "manifest.json").read_text(encoding="utf-8"))


def _manifest() -> dict:
    return _read_manifest(str(PACK))


def _source(voice: str) -> tuple[str, list]:
    """(pack folder, layers) for a voice: the authentic recording when MUSIC_SAMBA_AUTHENTIC has one."""
    if voice in AUTHENTIC_VOICES and _family(voice) in authentic_families():
        layers = _read_manifest(str(AUTHENTIC_PACK)).get(AUTHENTIC_VOICES[voice])
        if layers:
            return str(AUTHENTIC_PACK), layers
    return "", _manifest().get(voice) or []


# The last take each recording family played into a given take buffer (bars are rendered one call at a time).
_LAST_TAKE: dict[tuple, str] = {}


def take_pool(layers: list, li: int, minimum: int = 3) -> list:
    """The takes a stroke at dynamic layer ``li`` rotates through: that layer's, widened to the neighbouring layers when it
    has fewer than ``minimum`` (a one-take layer -- VCSL's agogo -- would otherwise repeat the same recording every stroke)."""
    pool = list(layers[li])
    step = 1
    while len(pool) < minimum and (li - step >= 0 or li + step < len(layers)):
        for j in (li - step, li + step):
            if 0 <= j < len(layers):
                pool += [t for t in layers[j] if t not in pool]
        step += 1
    return pool


def play_bar(audio: np.ndarray, sr: int, bar_number: int, strokes: list[Stroke], beat_to_sec, *, intensity: float = 1.0) -> None:
    """Add the bar's strokes to ``audio``. ``beat_to_sec(beat)`` maps a (fractional) beat of this bar to seconds."""
    # How many strokes of each recording family this bar plays: the rotation continues from bar to bar, so the last
    # stroke of one bar and the first of the next are different takes too.
    def _key(voice):
        pack, _ = _source(voice)
        return (pack, AUTHENTIC_VOICES.get(voice, voice) if pack else voice)

    per_bar: dict[tuple, int] = {}
    for st in strokes:
        per_bar[_key(st.voice)] = per_bar.get(_key(st.voice), 0) + 1
    seen: dict[tuple, int] = {}
    for st in strokes:
        pack, layers = _source(st.voice)
        if not layers:
            continue
        vel = performed_velocity(st, bar_number)
        li = int(round(vel * (len(layers) - 1)))
        pool = take_pool(layers, li)
        key = _key(st.voice)  # voices sharing recordings rotate together
        n = seen.get(key, 0)
        seen[key] = n + 1
        idx = (bar_number * per_bar[key] + n) % len(pool)
        last = _LAST_TAKE.get((id(audio), key))
        if len(pool) > 1 and pool[idx] == last:  # a bar with an extra stroke (a pickup) shifts the count: step past it
            idx = (idx + 1) % len(pool)
        take = pool[idx]  # never the same take twice running
        if len(_LAST_TAKE) > 256:
            _LAST_TAKE.clear()
        _LAST_TAKE[(id(audio), key)] = take
        x = _stroke_audio(st.voice, take, int(sr), bool(st.muted), pack)
        start = int(float(beat_to_sec(performed_beat(st, bar_number))) * sr)
        if start < 0 or start >= len(audio):
            continue
        gain = SECTION_LEVEL * LEVEL.get(st.voice, 0.004) * (0.3 + 0.7 * vel) * float(intensity)
        end = min(len(audio), start + len(x))
        audio[start:end] += x[: end - start] * gain
