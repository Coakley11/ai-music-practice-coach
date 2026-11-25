"""Build ``assets/instruments/tenor_sax`` from the VCSL tenor saxophone recordings.

usage: python -I tools/prepare_tenor_sax_pack.py RAW_DIR OUT_DIR

RAW_DIR holds the untouched VCSL files (never committed):

* ``RAW_DIR/stac/BrettTenor_Staccato_Main_<note>_vl<1|2>_rr<n>.wav``
* ``RAW_DIR/nv/BrettTenor_NV_Main_<note>_vl3_rr1.wav``

from ``sgossner/VCSL`` (CC0), ``Aerophones/Reed Aerophones/Tenor Saxophone/{Staccato,Non-Vibrato}``.
VCSL names notes with middle C = C3, so ``C3`` is MIDI 60; the measured pitch of every file is checked
against its name (within half a semitone) before it is used.

Each note: one microphone channel (the spaced pair is barely correlated, so a mono sum comb-filters),
resampled 48 kHz -> 44.1 kHz, started 4 ms before its onset with a 3 ms fade-in, a sustain's attack held
to 3 dB over its body (only the accented A#2 is changed audibly), sustains cut to 2.5 s from the onset
with a 0.30 s fade-out, staccato notes cut where they fall below -60 dB with a 25 ms
fade-out, normalised to a 0.95 peak and written as mono 16-bit FLAC. ``gain`` brings each recording
back to its layer's median loudness, so zones match each other and the layers keep the difference the
player made. ``cents`` is the measured pitch against the zone's key. Altissimo (above concert E5,
MIDI 76) is left out.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SR_OUT = 44100
CHANNEL = 1  # the right microphone: the slightly louder of the pair across the whole set
TOP = 76  # concert E5, the top of the tenor's normal range (written F#6)
SUSTAIN_SEC = 2.5
SUSTAIN_FADE_SEC = 0.30
STAC_FADE_SEC = 0.025
PRE_ROLL_SEC = 0.004
FADE_IN_SEC = 0.003
PEAK = 0.95
ATTACK_LIFT_DB = 3.0
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
NAME = re.compile(r"BrettTenor_(Staccato|NV)_Main_([A-G]#?)(\d)_vl(\d)_rr(\d+)\.wav$")
LAYER_VELOCITY = {("staccato", 1): 0.45, ("staccato", 2): 0.8, ("sustain", 3): 0.7}


def vcsl_midi(note: str, octave: str) -> int:
    return NOTE[note] + 12 * (int(octave) + 2)  # VCSL: C3 = middle C = MIDI 60


def measure_cents(x: np.ndarray, sr: int, midi: int, start: int, stop: int) -> float:
    """Median pitch of short frames, searched only within half a semitone of the expected note."""
    f_nom = 440.0 * 2.0 ** ((midi - 69) / 12.0)
    lo, hi = int(sr / (f_nom * 2 ** (0.5 / 12))), int(np.ceil(sr / (f_nom * 2 ** (-0.5 / 12))))
    frame = max(2048, 4 * hi)
    found = []
    for s in range(start, max(start + 1, stop - frame - hi), frame // 2):
        a = x[s : s + frame]
        if len(a) < frame:
            break
        a = a - a.mean()
        r = np.array([np.dot(a[: frame - hi], x[s + t : s + t + frame - hi] - x[s + t : s + t + frame - hi].mean()) for t in range(lo - 1, hi + 2)])
        k = int(np.argmax(r[1:-1])) + 1
        y0, y1, y2 = r[k - 1], r[k], r[k + 1]
        den = y0 - 2 * y1 + y2
        lag = (lo - 1 + k) + (0.5 * (y0 - y2) / den if den else 0.0)
        found.append(1200.0 * np.log2((sr / lag) / f_nom))
    if not found:
        raise ValueError("no pitch frames")
    return float(np.median(found))


def onset_of(x: np.ndarray) -> int:
    return int(np.argmax(np.abs(x) > np.abs(x).max() * 0.05))


def body_rms(x: np.ndarray, sr: int, on: int, staccato: bool) -> float:
    a, b = (on, on + int(0.25 * sr)) if staccato else (on + int(0.2 * sr), on + int(1.5 * sr))
    return float(np.sqrt(np.mean(x[a:b] ** 2)))


def ease_attack(x: np.ndarray, on: int) -> np.ndarray:
    """A sustain's first 0.3 s held to at most ATTACK_LIFT_DB over its body, so one accented recording
    does not stand out of a held background. Most notes are already under it and are not touched."""
    body = body_rms(x, SR_OUT, on, False)
    w = int(0.01 * SR_OUT)
    head = on + int(0.3 * SR_OUT)
    env = np.sqrt(np.convolve(x[:head] ** 2, np.ones(w) / w, mode="same")) + 1e-9
    g = np.minimum(1.0, body * 10 ** (ATTACK_LIFT_DB / 20) / env)
    g = np.convolve(np.pad(g, (w, w), mode="edge"), np.ones(2 * w) / (2 * w), mode="same")[w:-w]
    g[-w:] = np.linspace(g[-w], 1.0, w)  # back to unity where the steady note begins
    y = x.copy()
    y[:head] *= g
    return y


def process(path: pathlib.Path, staccato: bool) -> tuple[np.ndarray, int]:
    raw, sr = sf.read(str(path), dtype="float64", always_2d=True)
    x = resample_poly(raw[:, CHANNEL], SR_OUT, sr) if sr != SR_OUT else raw[:, CHANNEL]
    on = onset_of(x)
    first = max(0, on - int(PRE_ROLL_SEC * SR_OUT))
    x = x[first:].copy()
    on -= first
    if staccato:
        env = np.abs(x)
        loud = np.nonzero(env > env.max() * 10 ** (-60 / 20))[0]
        x = x[: int(loud[-1]) + 1]
        fade = min(int(STAC_FADE_SEC * SR_OUT), len(x) // 2)
    else:
        x = x[: on + int(SUSTAIN_SEC * SR_OUT)]
        fade = int(SUSTAIN_FADE_SEC * SR_OUT)
        x = ease_attack(x, on)
    n_in = int(FADE_IN_SEC * SR_OUT)
    x[:n_in] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(n_in) / n_in)
    x[-fade:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(1, fade + 1) / fade)
    x[0] = 0.0
    x[-1] = 0.0
    return x, on


def main(raw_dir: str, out_dir: str) -> None:
    raw, out = pathlib.Path(raw_dir), pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    notes = []
    for sub, art in (("stac", "staccato"), ("nv", "sustain")):
        for p in sorted((raw / sub).glob("*.wav")):
            m = NAME.search(p.name)
            if not m:
                continue
            midi = vcsl_midi(m.group(2), m.group(3))
            if midi > TOP:
                continue
            x, on = process(p, art == "staccato")
            cents = measure_cents(x, SR_OUT, midi, on + int(0.06 * SR_OUT), on + int((0.3 if art == "staccato" else 1.6) * SR_OUT))
            if abs(cents) > 50:
                raise SystemExit(f"{p.name}: measured {cents:+.1f} cents from MIDI {midi}")
            rms = body_rms(x, SR_OUT, on, art == "staccato")
            notes.append(dict(art=art, midi=midi, vl=int(m.group(4)), src=p.name, x=x, on=on, rms=rms, cents=cents))
    # Each layer's median loudness, measured before normalising: the zones are evened out to it.
    target = {}
    for key in {(n["art"], n["vl"]) for n in notes}:
        target[key] = float(np.median([n["rms"] for n in notes if (n["art"], n["vl"]) == key]))
    ref = max(target.values())
    manifest = {"sr": SR_OUT, "source": "Tenor saxophone (player credited as Brett in the file names), Versilian Community Sample Library, CC0",
                "range": [min(n["midi"] for n in notes), max(n["midi"] for n in notes)], "zones": [], "articulations": {"staccato": []}}
    zones = {"sustain": {}, "staccato": {}}
    for n in notes:
        peak = float(np.abs(n["x"]).max())
        y = n["x"] * (PEAK / peak)
        name = f"{'sus' if n['art'] == 'sustain' else 'stac'}_{n['midi']}_v{n['vl']}.flac"
        sf.write(str(out / name), y, SR_OUT, subtype="PCM_16", format="FLAC")
        # Played at gain g, the note's body comes out at its layer's median loudness, scaled so the
        # loudest layer's median sits at 0.12 RMS (peaks stay under 1).
        g = (target[(n["art"], n["vl"])] / ref) * 0.12 / (n["rms"] * PEAK / peak)
        take = {"file": name, "cents": round(n["cents"], 1), "gain": round(g, 4), "onset_sec": round(n["on"] / SR_OUT, 4),
                "seconds": round(len(y) / SR_OUT, 3), "source_file": n["src"]}
        zones[n["art"]].setdefault(n["midi"], {}).setdefault(LAYER_VELOCITY[(n["art"], n["vl"])], []).append(take)
    for art, dest in (("sustain", manifest["zones"]), ("staccato", manifest["articulations"]["staccato"])):
        for key in sorted(zones[art]):
            dest.append({"key": key, "layers": [{"velocity": v, "takes": zones[art][key][v]} for v in sorted(zones[art][key])]})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    for n in notes:
        print(f"{n['art']:8s} {n['midi']:3d} vl{n['vl']} {n['cents']:+6.1f} c  rms {n['rms']:.4f}  {n['src']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
