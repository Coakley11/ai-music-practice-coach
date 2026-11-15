"""Karaoke Part 5: measure Just the Two of Us's harmonic timing in the accompaniment.

The reported progression is Dbmaj7 -> C7 -> Fm7 -> Ebm7 -> Ab7, and the assignment is explicit
that not every chord occupies a full measure and that the arrangement must be verified rather
than assumed.

What the catalog chart says today (every cell is one bar):

    Dbmaj7 | C7 | Fm7 | Ebm7 | Ab7 | Dbmaj7 | C7 | Fm7

That is a five-bar turnaround, and the eight-bar section therefore ends three bars into its
second pass - a loop that cannot close. The song's turnaround is four bars, with the ii and the
V sharing the last one:

    Dbmaj7 | C7 | Fm7 | Ebm7 Ab7

In Db major that is Imaj7 - VII7 - iii7 - ii7 V7, the ii-V arriving together in the fourth bar.

This probe does not argue from the labels. It renders the keys layer of both charts and reads
the chord back out of the audio per half bar, by chroma: the pitch-class energy of each window
is matched against the pitch classes of every candidate chord, so what it reports is what the
accompaniment plays, with no reference to the chart it came from.

Usage:
  python -X utf8 scripts/_probe_jttou_harmonic_timing.py [--render]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from chord_subdivisions import parse_subdivisions  # noqa: E402

BPM = 97
SR = 22050
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PC = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}

CURRENT = ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7", "C7", "Fm7"]
PROPOSED = ["Dbmaj7", "C7", "Fm7", "Ebm7:2|Ab7:2", "Dbmaj7", "C7", "Fm7", "Ebm7:2|Ab7:2"]

# Pitch classes of each chord that appears, for reading the audio back.
CHORD_PCS = {
    "Dbmaj7": ("Db", "F", "Ab", "C"),
    "C7": ("C", "E", "G", "Bb"),
    "Fm7": ("F", "Ab", "C", "Eb"),
    "Ebm7": ("Eb", "Gb", "Bb", "Db"),
    "Ab7": ("Ab", "C", "Eb", "Gb"),
}


def beat_map(tokens: list[str]) -> list[tuple[float, float, str]]:
    """(start beat, length in beats, chord) for a chart, four beats to the bar."""
    out: list[tuple[float, float, str]] = []
    cursor = 0.0
    for token in tokens:
        subs = parse_subdivisions(token, beats_per_bar=4.0)
        for s in subs:
            out.append((cursor, float(s.weight), s.chord))
            cursor += float(s.weight)
    return out


def show(label: str, tokens: list[str]) -> list[tuple[float, float, str]]:
    rows = beat_map(tokens)
    print(f"\n{label}")
    print(f"  {len(tokens)} bars, {sum(r[1] for r in rows):.0f} beats")
    for start, length, chord in rows:
        bar = int(start // 4) + 1
        beat = start % 4 + 1
        print(f"    bar {bar}  beat {beat:.0f}  {chord:<8} {length:.0f} beat(s)")
    return rows


def loop_closes(tokens: list[str]) -> str:
    """Does the section contain whole turnarounds, or does it stop mid-phrase?"""
    heads = [parse_subdivisions(t, beats_per_bar=4.0)[0].chord for t in tokens]
    try:
        period = heads.index(heads[0], 1)
    except ValueError:
        return "no repeat found"
    whole = len(tokens) / period
    return (f"turnaround is {period} bars; the {len(tokens)}-bar section holds {whole:.2f} of them"
            + ("" if abs(whole - round(whole)) < 1e-9 else "  <-- stops mid-turnaround"))


def chroma(block: np.ndarray) -> np.ndarray:
    if not block.size:
        return np.zeros(12)
    window = np.hanning(len(block))
    spec = np.abs(np.fft.rfft(block * window))
    freqs = np.fft.rfftfreq(len(block), 1.0 / SR)
    out = np.zeros(12)
    for f, mag in zip(freqs, spec):
        if f < 55.0 or f > 2200.0 or mag <= 0:
            continue
        midi = 69 + 12 * np.log2(f / 440.0)
        out[int(round(midi)) % 12] += mag
    norm = np.linalg.norm(out)
    return out / norm if norm else out


def best_chord(block: np.ndarray) -> tuple[str, float]:
    """Which of the candidate chords the audio in this window fits best."""
    c = chroma(block)
    scored = []
    for name, pcs in CHORD_PCS.items():
        mask = np.zeros(12)
        for p in pcs:
            mask[PC[p]] = 1.0
        n = np.linalg.norm(mask)
        scored.append((float(c @ (mask / n)) if n else 0.0, name))
    scored.sort(reverse=True)
    top, second = scored[0], scored[1]
    margin = (top[0] / second[0]) if second[0] else float("inf")
    return top[1], margin


def render(tokens: list[str]) -> np.ndarray:
    from backing_audio import synthesize_chords_to_numpy

    audio = synthesize_chords_to_numpy(
        tokens, bpm=BPM, loops=1, sr=SR, style="Soul groove", level="Intermediate",
        song_title="Just the Two of Us", song_artist="Grover Washington Jr. / Bill Withers",
        time_signature="4/4", layers=["keys"],
    )
    # The renderer hands back (samples, metadata); older callers took the array alone.
    if isinstance(audio, tuple) and audio:
        audio = audio[0]
    return np.asarray(audio, dtype=float).reshape(-1)


def read_back(label: str, tokens: list[str]) -> None:
    audio = render(tokens)
    beat_sec = 60.0 / BPM
    print(f"\n{label} - read back out of the rendered keys layer, one window per half bar")
    bars = len(tokens)
    for bar in range(bars):
        halves = []
        for half in (0, 1):
            start = int((bar * 4 + half * 2) * beat_sec * SR)
            end = int((bar * 4 + half * 2 + 2) * beat_sec * SR)
            block = audio[start:end]
            name, margin = best_chord(block)
            halves.append(f"{name}(x{margin:.2f})")
        print(f"    bar {bar + 1}: beats 1-2 {halves[0]:<16} beats 3-4 {halves[1]}")


def main() -> int:
    cur = show("CURRENT catalog chart (Verse / Chorus / Intro / Solo)", CURRENT)
    print(f"  {loop_closes(CURRENT)}")
    prop = show("PROPOSED chart - the ii and the V share the fourth bar", PROPOSED)
    print(f"  {loop_closes(PROPOSED)}")

    print("\nwhat changes, in beats")
    for name in ("Ebm7", "Ab7"):
        was = [r for r in cur if r[2] == name]
        now = [r for r in prop if r[2] == name]
        print(f"    {name:<7} was {was[0][1]:.0f} beat(s) starting at beat {was[0][0]:.0f}"
              f"   ->  now {now[0][1]:.0f} beat(s) starting at beat {now[0][0]:.0f}"
              f"  ({len(was)}x -> {len(now)}x per section)")
    total_cur = sum(r[1] for r in cur)
    total_prop = sum(r[1] for r in prop)
    print(f"    section length unchanged: {total_cur:.0f} beats -> {total_prop:.0f} beats "
          f"({len(CURRENT)} bars -> {len(PROPOSED)} bars)")

    if "--render" in sys.argv:
        read_back("CURRENT", CURRENT)
        read_back("PROPOSED", PROPOSED)
    else:
        print("\n(pass --render to read the chords back out of the audio)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
