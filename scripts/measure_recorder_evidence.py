# -*- coding: utf-8 -*-
"""Measure the browser round's artefacts: real captured audio against the app's placement.

Reads what _browser_composition_recorder_accept.py saved and answers three separate questions,
deliberately kept apart so a pass cannot borrow confidence from another:

  1. Where are the notes in the audio the browser actually captured?  Measured independently
     with librosa's onset detector - not with the app's transcriber, and not from the authored
     fixture.
  2. Where did the app put them?  The real transcriber on those real bytes, handed the
     measured count-in exactly as the Studio page hands it over.
  3. Do those agree, and do they agree with the authored rhythm?  Intervals are compared
     because they are free of any coordinate-system question; absolute placement is compared
     separately, against the measured music_offset_sec, which is the whole claim of the
     shared clock.

Usage:  python scripts/measure_recorder_evidence.py [1440]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

OUT = SCRIPTS / "evidence-composition-recorder"
WIDTH = sys.argv[1] if len(sys.argv) > 1 else "1440"

BPM = 96
SPB = 60.0 / BPM
GROUND_TRUTH_INTERVALS = [1.0, 0.5, 0.25, 0.75, 1.5, 0.25, 0.25, 2.0]
# One sixteenth: the onset grid's own resolution. A disagreement inside it is the grid, not
# a misplacement; anything larger is a real one.
TOL_BEATS = 0.25


def measured_onsets(wav_path: Path) -> tuple[list[float], float]:
    """Onsets in seconds, measured from the audio envelope. Independent of the transcriber.

    An amplitude gate with hysteresis rather than librosa's spectral onset detector: on clean
    sustained tones the spectral detector fires again on vibrato and on releases (65 detections
    for 36 notes, measured), which would make this reference noisier than the thing it is meant
    to check. A note here is "the envelope rose through the on threshold after having fallen
    below the off threshold", which is what a note is in this audio.
    """
    import librosa

    y, sr = librosa.load(str(wav_path), sr=22050, mono=True)
    hop = 128
    rms = librosa.feature.rms(y=y, frame_length=512, hop_length=hop)[0]
    peak = float(rms.max() or 0.0)
    if peak <= 0:
        return [], float(len(y) / sr)
    env = rms / peak
    on_th, off_th, min_gap = 0.22, 0.10, 0.07
    onsets: list[float] = []
    armed = True
    for i, v in enumerate(env):
        if armed and v > on_th:
            # Backtrack to where the attack began, so the figure is the note's start and not
            # the moment it got loud.
            j = i
            while j > 0 and env[j - 1] > 0.5 * on_th:
                j -= 1
            t = float(librosa.frames_to_time(j, sr=sr, hop_length=hop))
            if not onsets or t - onsets[-1] >= min_gap:
                onsets.append(round(t, 4))
            armed = False
        elif not armed and v < off_th:
            armed = True
    return onsets, float(len(y) / sr)


def intervals(values: list[float]) -> list[float]:
    return [round(values[i + 1] - values[i], 3) for i in range(len(values) - 1)]


def longest_run(got: list[float], want: list[float], tol: float = 0.13) -> int:
    best = 0
    for start in range(max(1, len(got))):
        run = 0
        for k, w in enumerate(want):
            if start + k >= len(got) or abs(got[start + k] - w) > tol:
                break
            run += 1
        best = max(best, run)
    return best


def main() -> int:
    take = OUT / f"take-{WIDTH}.wav"
    timing_path = OUT / f"timing-{WIDTH}.json"
    if not take.exists() or not timing_path.exists():
        print(f"no artefacts for {WIDTH}px - run the browser script first")
        return 2
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    music_offset = timing.get("music_offset_sec")
    print(f"== take-{WIDTH}.wav  {take.stat().st_size} bytes")
    print(f"   measured music_offset_sec : {music_offset!r}")
    print(f"   measured count_in_sec     : {timing.get('count_in_sec')!r}")
    print(f"   dry_duration_sec          : {timing.get('dry_duration_sec')!r}")
    print(f"   device settings           : {timing.get('settings')!r}")
    if not isinstance(music_offset, (int, float)):
        print("   UNMEASURED: nothing downstream may claim an alignment")
        return 1

    onsets, dur = measured_onsets(take)
    beats_from_zero = [round((t - float(music_offset)) / SPB, 3) for t in onsets]
    print(f"\n-- 1. measured from the captured audio ({dur:.2f}s, {len(onsets)} onsets)")
    print(f"   onsets (s)        : {onsets[:16]}")
    print(f"   beats from zero   : {beats_from_zero[:16]}")
    print(f"   intervals (beats) : {intervals(beats_from_zero)[:15]}")
    run_audio = longest_run(intervals(beats_from_zero), GROUND_TRUTH_INTERVALS)
    print(f"   authored rhythm found in the captured audio: "
          f"{run_audio}/{len(GROUND_TRUTH_INTERVALS)} consecutive intervals")
    print("   (an envelope gate cannot separate two sixteenths whose releases overlap, so this")
    print("    reference is COARSER than the transcriber it checks: a short run here means the")
    print("    reference merged a pair, not that the audio lacks the rhythm. The pairing below")
    print("    is therefore measured-onset -> app-note, never the other way round.)")

    from composition_hum_transcription import transcribe_hum_audio

    # Exactly the decision the Studio page makes - not the raw count_in_sec field. Those are
    # different numbers: count_in_sec is how long the clicks lasted (2.5 s), while musical zero
    # sits at music_offset_sec (2.808 s), which adds the output and input latency measured in
    # this browser. Passing the former put every note half a beat out and looked like an app
    # defect; it was this script.
    from composition_recording_timing import count_in_sec_for_transcription

    decided = count_in_sec_for_transcription(
        timing, requested_sec=float(timing.get("count_in_sec") or 0.0)
    )
    print(f"   count-in handed to the transcriber: {decided['count_in_sec']!r} "
          f"(measured={decided['measured']}); raw count_in_sec field was "
          f"{timing.get('count_in_sec')!r}")
    res = transcribe_hum_audio(
        take.read_bytes(), bpm=BPM, meter="4/4", key="D",
        count_in_sec=float(decided["count_in_sec"] or 0.0),
        count_in_measured=bool(decided["measured"]),
    )
    notes = [e for e in (res.get("events") or []) if not e.get("is_rest")]
    app_beats = [round(float(e.get("beat") or 0.0), 3) for e in notes]
    print(f"\n-- 2. where the app put them ({len(notes)} notes)")
    print(f"   pitches           : {[str(e.get('pitch')) for e in notes][:16]}")
    print(f"   beats             : {app_beats[:16]}")
    print(f"   intervals (beats) : {intervals(app_beats)[:15]}")
    print(f"   count_in_applied={res.get('count_in_applied')} "
          f"count_in_measured={res.get('count_in_measured')} "
          f"first_note_sec={res.get('first_note_sec')}")
    run_app = longest_run(intervals(app_beats), GROUND_TRUTH_INTERVALS)
    print(f"   authored rhythm in the app's placement: "
          f"{run_app}/{len(GROUND_TRUTH_INTERVALS)} consecutive intervals")

    print("\n-- 3. do they agree")
    # Every onset the audio really has must have a transcribed note at that beat. Extra app
    # notes are not errors here: they are the ones the coarser reference could not separate.
    # The fake capture device plays throughout, so the count-in period contains notes too.
    # The transcriber is right to drop those: they happened before bar 1 beat 1. Comparing
    # them against transcribed notes would be marking it wrong for being right.
    in_music = [m for m in beats_from_zero if m >= -0.2]
    dropped = len(beats_from_zero) - len(in_music)
    print(f"   onsets before musical zero, correctly not transcribed: {dropped}")
    pairs: list[tuple[float, float, float]] = []
    for m in in_music:
        if not app_beats:
            break
        near = min(app_beats, key=lambda b: abs(b - m))
        pairs.append((round(m, 3), round(near, 3), round(near - m, 3)))
    worst = max((abs(d) for _, _, d in pairs), default=0.0)
    within = sum(1 for _, _, d in pairs if abs(d) <= TOL_BEATS)
    print(f"   measured beat -> nearest app note (first 12): {pairs[:12]}")
    print(f"   every measured onset has a note within one sixteenth: {within}/{len(pairs)}")
    print(f"   worst placement error: {worst:.3f} beats ({worst * SPB * 1000:.0f} ms)")
    print(f"   app notes the reference could not separate: {max(0, len(app_beats) - len(pairs))}")
    print(f"   notes transcribed from before musical zero: "
          f"{sum(1 for b in app_beats if b < -0.2)}")
    offbeat = [b for b in app_beats if abs(b - round(b)) > 0.05]
    print(f"   notes kept off the beat: {len(offbeat)} of {len(app_beats)}  {offbeat[:10]}")
    print(f"   nothing collapsed onto beat 0: {app_beats.count(0.0) <= 1}")

    mix = OUT / f"mix-{WIDTH}.wav"
    if mix.exists():
        import librosa

        y, sr = librosa.load(str(mix), sr=22050, mono=True)
        S = np.abs(librosa.stft(y, n_fft=2048))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        flute = float(S[(freqs > 520) & (freqs < 800)].mean())
        chords = float(S[(freqs > 80) & (freqs < 400)].mean())
        print(f"\n-- the app's mixed recording + chords ({len(y) / sr:.2f}s)")
        print(f"   energy 520-800 Hz (the recorded line): {flute:.4f}")
        print(f"   energy 80-400 Hz  (the accompaniment): {chords:.4f}")
        print(f"   both present: {flute > 1e-3 and chords > 1e-3}")

    # The verdict rests on the app's own placement against the captured audio. The reference's
    # authored-rhythm figure is reported, not asserted: it is the coarser instrument.
    ok = (
        run_app >= len(GROUND_TRUTH_INTERVALS)
        and bool(pairs)
        and within == len(pairs)
        and app_beats.count(0.0) <= 1
        and bool(offbeat)
    )
    print(f"\nVERDICT: {'PASS' if ok else 'REVIEW'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
