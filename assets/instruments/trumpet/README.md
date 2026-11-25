# Trumpet

Trumpet from VS Chamber Orchestra 2: Community Edition (`sgossner/VSCO-2-CE`, commit
`440300901dfe9275fd84e0b7763af1f8443ae62e`), `Brass/Trumpet` (files `Sum_SHTrumpet_*`; the library does not say what `SH`
stands for, which trumpet was played, or who played it - an orchestral player, not a jazz one). The repository README
credits the library as "Recorded by Sam Gossner & Simon Dalzell; Sample Cutting by Elan Hickler/Soundemote". Released under
CC0: see `LICENSE` (the repository's own `LICENSE` text, unchanged). The library's `Readme.txt` also *asks* (it is not a
licence condition) that the samples are not sold directly and that Versilian Studios / Sam Gossner be credited where
applicable: this README is that credit.

Two articulations, concert pitch F3-C6 (MIDI 53-84):

* `sus_<midi>_v<1|3>.flac` - Sustain (straight, no vibrato), both recorded layers (`v1` soft, `v3` loud), one take, 10 notes
  three or four semitones apart, so a note between them is played up to two semitones from its recording.
* `stac_<midi>_v<1|2|3>[_r2].flac` - Staccato, all three recorded layers, two takes each (round robins 1 and 2), 11 notes
  (the same 10 plus F4).

Left out: the vibrato sustains (`susvib`) and the straight- and harmon-mute sustains.

Made by `tools/prepare_vsco_brass_pack.py trumpet` from the 44.1 kHz / 16-bit stereo originals with the tenor sax's
processing: the right channel only, started 4 ms before the onset with a 3 ms fade-in, a sustain's attack held to at most
3 dB over its body, sustains cut to 2.5 s from the onset with a 0.30 s fade-out, staccato notes cut below -60 dB with a 25 ms
fade-out, normalised and written as mono 16-bit FLAC. Nothing is resampled or pitch shifted. Each note's pitch was measured
against its name (VSCO names middle C as C3) and checked for the octave; `cents`, the loudness-evening `gain` (each
articulation's layers squeezed into 8 dB, keeping their order) and each take's source file are in `manifest.json`.

Each staccato take also has `attack_cents`: the pitch of its first 20-80 ms against the note, after its own
`cents` correction. Loud brass staccatos start flat (or, on a few trombone takes, sharp) and settle into tune; a
shot (`backing_horns`, `steady_attacks`) skips takes more than 30 cents off when its layer has a steadier one.
Measured 2026-11-25 by autocorrelation; the audio itself is unchanged.

Played by `backing_horns.py` (`instrument="trumpet"`), only when `MUSIC_HORNS` is switched on; no ensemble uses it yet.
