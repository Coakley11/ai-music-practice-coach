# Tenor saxophone

Tenor saxophone from the Versilian Community Sample Library (`sgossner/VCSL`, commit `c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e`),
`Aerophones/Reed Aerophones/Tenor Saxophone`. The file names credit the player only as "Brett" (`BrettTenor_*`); the library
does not name the instrument model or microphones. Released under CC0: see `LICENSE` (the library's own `LICENSE` text, unchanged; the same text as `grand_piano/LICENSE`).
Commercial use is allowed, with no royalties and no credit required.

Two articulations, concert pitch Ab2-E5 (MIDI 44-76, the tenor's normal range, written Bb3-F#6). The altissimo notes VCSL also has
(F5 and up) are left out.

* `sus_<midi>_v3.flac` - Non-Vibrato, the louder (`vl3`) of the two recorded layers, one take, every whole tone (17 notes).
* `stac_<midi>_v<1|2>.flac` - Staccato, soft (`vl1`) and loud (`vl2`) layers, one take each, 17 notes with gaps of up to three
  semitones; the bottom three notes have only the loud layer.

Made by `tools/prepare_tenor_sax_pack.py` from the 48 kHz / 24-bit stereo originals: the right microphone only (the spaced pair is
barely correlated, so a mono sum comb-filters), resampled to 44.1 kHz, started 4 ms before the onset with a 3 ms fade-in, a sustain's attack held to at most
3 dB over its body (only the accented A#2 changes audibly), sustains
cut to 2.5 s from the onset with a 0.30 s fade-out, staccato notes cut below -60 dB with a 25 ms fade-out, normalised and written as
mono 16-bit FLAC. Each note's pitch was measured against its name (VCSL names middle C as C3); `cents` and the loudness-evening
`gain` are in `manifest.json`, with each take's source file. No other processing.

Played by `backing_horns.py`, only when `MUSIC_HORNS` is switched on.
