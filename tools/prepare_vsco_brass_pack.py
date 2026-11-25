"""Build ``assets/instruments/trombone`` or ``assets/instruments/trumpet`` from VSCO 2 CE brass recordings.

usage: python -I tools/prepare_vsco_brass_pack.py {trombone|trumpet} RAW_DIR OUT_DIR

RAW_DIR holds the untouched VSCO 2 CE files (never committed), from ``sgossner/VSCO-2-CE`` (CC0):

* trombone (``Brass/OldTrombone``, a 1950s Olds Super tenor trombone):
  ``RAW_DIR/sus/Trombone_Sustain_<note>_v<3|4|5>_1.wav`` (``G3`` only has ``v2`` and ``v5``) and
  ``RAW_DIR/short/Trombone_Short_<note>_v<2|3>_1.wav``
* trumpet (``Brass/Trumpet``): ``RAW_DIR/sus/Sum_SHTrumpet_sus_<note>_v<1|3>_rr1.wav`` and
  ``RAW_DIR/stac/Sum_SHTrumpet_stac_<note>_v<1|2|3>_rr<1|2>.wav``

VSCO names notes with middle C = C3 (as VCSL does), so ``C3`` is MIDI 60. Every file's pitch is checked
twice before it is used: within half a semitone of its name (``measure_cents``), and not an octave away
(``octave_ok``: its period, found by YIN, is the named note's).

The processing is the tenor sax's (``tools/prepare_tenor_sax_pack.py``, whose helpers are reused): one
microphone channel, started 4 ms before the onset with a 3 ms fade-in, a sustain's attack held to 3 dB
over its body, sustains cut to 2.5 s from the onset with a 0.30 s fade-out, short notes cut below -60 dB
with a 25 ms fade-out, normalised to a 0.95 peak, mono 16-bit FLAC. The recordings are already 44.1 kHz,
so nothing is resampled. ``gain`` brings each recording to its layer's median loudness; one thing differs
from the tenor: a softer layer is kept at most ``MAX_LAYER_SPREAD_DB`` under its articulation's loudest
layer (the recorded p/f gap is 15-22 dB, which would jump out of a background when the dynamic changes),
so the layers differ mostly by tone, as a player's do inside a mix. The gaps are squeezed in proportion, so
three layers keep their order.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from prepare_tenor_sax_pack import (  # noqa: E402  (the tenor's own processing, unchanged)
    FADE_IN_SEC,
    NOTE,
    PEAK,
    PRE_ROLL_SEC,
    STAC_FADE_SEC,
    SUSTAIN_FADE_SEC,
    SUSTAIN_SEC,
    body_rms,
    ease_attack,
    measure_cents,
    onset_of,
)

SR = 44100
MAX_LAYER_SPREAD_DB = 8.0

# Per instrument: file name pattern (articulation word, note, octave, layer, take), sub-folders, the layers
# kept and their velocities, the microphone channel, and where it came from.
SPECS = {
    "trombone": dict(
        name=re.compile(r"Trombone_(Sustain|Short)_([A-G]#?)(\d)_v(\d)_(\d+)\.wav$"),
        folders={"sus": "sustain", "short": "staccato"},
        words={"Sustain": "sustain", "Short": "staccato"},
        # G3 (MIDI 67) was only recorded at v2 and v5: they stand in for v3 and v4 there.
        layers={("sustain", 3): 0.45, ("sustain", 4): 0.8, ("staccato", 2): 0.45, ("staccato", 3): 0.8},
        stand_in={("sustain", 2): 3, ("sustain", 5): 4},  # used only where the layer it stands in for is missing
        channel=1,
        source="Tenor trombone (a 1950s Olds Super), VSCO 2 Community Edition (Versilian Studios), CC0",
    ),
    "trumpet": dict(
        name=re.compile(r"Sum_SHTrumpet_(sus|stac)_([A-G]#?)(\d)_v(\d)_rr(\d+)\.wav$"),
        folders={"sus": "sustain", "stac": "staccato"},
        words={"sus": "sustain", "stac": "staccato"},
        layers={("sustain", 1): 0.45, ("sustain", 3): 0.8,
                ("staccato", 1): 0.3, ("staccato", 2): 0.55, ("staccato", 3): 0.85},
        stand_in={},
        channel=1,
        source="Trumpet, VSCO 2 Community Edition (Versilian Studios), CC0",
    ),
}


def vsco_midi(note: str, octave: str) -> int:
    return NOTE[note] + 12 * (int(octave) + 2)  # VSCO: C3 = middle C = MIDI 60


def octave_ok(x: np.ndarray, sr: int, midi: int, start: int, stop: int) -> bool:
    """The named pitch is the note's own period, not an octave either side (YIN: the shortest lag whose
    normalised difference dips under 0.25, searched from an octave and a bit above to an octave and a half below)."""
    f0 = 440.0 * 2.0 ** ((midi - 69) / 12.0)
    period = sr / f0
    lo, hi = max(2, int(period / 2.2)), int(period * 2.9) + 2
    frame = int(max(1024, 2 * period))
    votes = []
    for s in range(start, max(start + 1, stop - frame - hi), frame // 2):
        a = x[s : s + frame + hi]
        if len(a) < frame + hi:
            break
        d = np.array([np.sum((a[:frame] - a[t : t + frame]) ** 2) for t in range(hi)])
        cmnd = d[1:] * np.arange(1, hi) / np.maximum(np.cumsum(d[1:]), 1e-12)
        dips = [t for t in range(lo, hi - 2) if cmnd[t - 1] < 0.25 and cmnd[t - 1] <= cmnd[t - 2] and cmnd[t - 1] <= cmnd[t]]
        if dips:
            votes.append(abs(12 * np.log2(dips[0] / period)) < 0.5)
    return bool(votes) and float(np.mean(votes)) >= 0.6


def process(path: pathlib.Path, staccato: bool, channel: int) -> tuple[np.ndarray, int]:
    raw, sr = sf.read(str(path), dtype="float64", always_2d=True)
    if sr != SR:
        raise SystemExit(f"{path.name}: {sr} Hz, expected {SR}")
    x = raw[:, min(channel, raw.shape[1] - 1)]
    on = onset_of(x)
    first = max(0, on - int(PRE_ROLL_SEC * SR))
    x = x[first:].copy()
    on -= first
    if staccato:
        env = np.abs(x)
        loud = np.nonzero(env > env.max() * 10 ** (-60 / 20))[0]
        x = x[: int(loud[-1]) + 1]
        fade = min(int(STAC_FADE_SEC * SR), len(x) // 2)
    else:
        x = x[: on + int(SUSTAIN_SEC * SR)]
        fade = int(SUSTAIN_FADE_SEC * SR)
        x = ease_attack(x, on)
    n_in = int(FADE_IN_SEC * SR)
    x[:n_in] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(n_in) / n_in)
    x[-fade:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(1, fade + 1) / fade)
    x[0] = 0.0
    x[-1] = 0.0
    return x, on


def main(instrument: str, raw_dir: str, out_dir: str) -> None:
    spec = SPECS[instrument]
    raw, out = pathlib.Path(raw_dir), pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    found = []
    for sub in spec["folders"]:
        for p in sorted((raw / sub).glob("*.wav")):
            m = spec["name"].search(p.name)
            if m:
                found.append((p, m, spec["words"][m.group(1)], int(m.group(4)), vsco_midi(m.group(2), m.group(3))))
    have = {(art, vl, midi) for _p, _m, art, vl, midi in found if (art, vl) in spec["layers"]}
    notes = []
    for p, m, art, vl, midi in found:
        group = vl
        if (art, vl) not in spec["layers"]:
            group = spec["stand_in"].get((art, vl))
            if group is None or (art, group, midi) in have:
                continue
        short = art == "staccato"
        x, on = process(p, short, spec["channel"])
        a, b = on + int(0.06 * SR), on + int((0.3 if short else 1.6) * SR)
        cents = measure_cents(x, SR, midi, a, b)
        if abs(cents) > 50 or not octave_ok(x, SR, midi, a, min(b, len(x))):
            raise SystemExit(f"{p.name}: not MIDI {midi} (measured {cents:+.1f} cents, octave check)")
        rms = body_rms(x, SR, on, short)
        notes.append(dict(art=art, midi=midi, vl=vl, group=group, take=int(m.group(5)), src=p.name, x=x, on=on, rms=rms, cents=cents))
    # Each layer's median loudness, measured before normalising; an articulation's layers squeezed into MAX_LAYER_SPREAD_DB.
    target = {}
    for key in {(n["art"], n["group"]) for n in notes}:
        target[key] = float(np.median([n["rms"] for n in notes if (n["art"], n["group"]) == key]))
    for art in {k[0] for k in target}:
        db = {k: 20 * np.log10(v) for k, v in target.items() if k[0] == art}
        top, spread = max(db.values()), max(db.values()) - min(db.values())
        squeeze = min(1.0, MAX_LAYER_SPREAD_DB / spread) if spread > 0 else 1.0  # keeps the layers' order
        for k, d in db.items():
            target[k] = 10 ** ((top + (d - top) * squeeze) / 20)
    ref = max(target.values())
    manifest = {"sr": SR, "source": spec["source"], "range": [min(n["midi"] for n in notes), max(n["midi"] for n in notes)],
                "zones": [], "articulations": {"staccato": []}}
    zones = {"sustain": {}, "staccato": {}}
    for n in sorted(notes, key=lambda n: (n["art"], n["midi"], n["vl"], n["take"])):
        peak = float(np.abs(n["x"]).max())
        y = n["x"] * (PEAK / peak)
        name = f"{'sus' if n['art'] == 'sustain' else 'stac'}_{n['midi']}_v{n['vl']}" + (f"_r{n['take']}" if n["take"] > 1 else "") + ".flac"
        sf.write(str(out / name), y, SR, subtype="PCM_16", format="FLAC")
        g = (target[(n["art"], n["group"])] / ref) * 0.12 / (n["rms"] * PEAK / peak)
        take = {"file": name, "cents": round(n["cents"], 1), "gain": round(g, 4), "onset_sec": round(n["on"] / SR, 4),
                "seconds": round(len(y) / SR, 3), "source_file": n["src"]}
        zones[n["art"]].setdefault(n["midi"], {}).setdefault(spec["layers"][(n["art"], n["group"])], []).append(take)
    for art, dest in (("sustain", manifest["zones"]), ("staccato", manifest["articulations"]["staccato"])):
        for key in sorted(zones[art]):
            dest.append({"key": key, "layers": [{"velocity": v, "takes": zones[art][key][v]} for v in sorted(zones[art][key])]})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    for n in sorted(notes, key=lambda n: (n["art"], n["midi"], n["vl"], n["take"])):
        print(f"{n['art']:8s} {n['midi']:3d} v{n['vl']} t{n['take']} {n['cents']:+6.1f} c  rms {20 * np.log10(n['rms']):6.1f} dB  {n['src']}")
    print({f"{k[0]}/v{k[1]}": float(round(20 * np.log10(v / ref), 1)) for k, v in sorted(target.items())})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
