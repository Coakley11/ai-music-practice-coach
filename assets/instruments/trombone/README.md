# Tenor trombone

Tenor trombone from VS Chamber Orchestra 2: Community Edition (`sgossner/VSCO-2-CE`, commit
`440300901dfe9275fd84e0b7763af1f8443ae62e`), `Brass/OldTrombone`. The folder's own `Notes.txt` says: "1950's Olds Super
tenor trombone. Unreleased sample set done as a test for VSCO 2. Phaselocked sustains. Tuned (I think...)". The repository
README credits the library as "Recorded by Sam Gossner & Simon Dalzell; Sample Cutting by Elan Hickler/Soundemote"; the
player is not named. Released under CC0: see `LICENSE` (the repository's own `LICENSE` text, unchanged). The library's
`Readme.txt` also *asks* (it is not a licence condition) that the samples are not sold directly and that Versilian Studios /
Sam Gossner be credited where applicable: this README is that credit.

Two articulations, concert pitch F2-G4 (MIDI 41-67; the upper middle of the trombone, no pedal tones, nothing above G4):

* `sus_<midi>_v<3|4>.flac` - Sustain, the `v3` (soft) and `v4` (loud) of the five recorded layers, one take, 16 notes a
  whole tone or a semitone apart. G4 (67) was only recorded at `v2` and `v5`, which stand in there (`sus_67_v2`,
  `sus_67_v5`).
* `stac_<midi>_v<2|3>[_r2].flac` - Short, the `v2` (soft) and `v3` (loud) of the three recorded layers, two takes each
  (round robins 1 and 2), 15 notes F2-F4 (no short G4).

Made by `tools/prepare_vsco_brass_pack.py trombone` from the 44.1 kHz / 24-bit stereo originals with the tenor sax's
processing: the right channel only, started 4 ms before the onset with a 3 ms fade-in, a sustain's attack held to at most
3 dB over its body, sustains cut to 2.5 s from the onset with a 0.30 s fade-out, short notes cut below -60 dB with a 25 ms
fade-out, normalised and written as mono 16-bit FLAC. Nothing is resampled or pitch shifted. Each note's pitch was measured
against its name (VSCO names middle C as C3) and checked for the octave; `cents`, the loudness-evening `gain` (the soft
layer kept within 8 dB of the loud one) and each take's source file are in `manifest.json`.

Each staccato take also has `attack_cents`: the pitch of its first 20-80 ms against the note, after its own
`cents` correction. Loud brass staccatos start flat (or, on a few trombone takes, sharp) and settle into tune; a
shot (`backing_horns`, `steady_attacks`) skips takes more than 30 cents off when its layer has a steadier one.
Measured 2026-11-25 by autocorrelation; the audio itself is unchanged.

Played by `backing_horns.py` (`instrument="trombone"`), only when `MUSIC_HORNS` is switched on; no ensemble uses it yet.
