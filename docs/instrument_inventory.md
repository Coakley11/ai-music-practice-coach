# Backing instrument inventory

What the Backing engine can play from recordings today, and what the ensembles still miss. Written
2026-11-24 on `feature/horns-tenor-sax-20261124` (based on dev `3587e435`).

Every recorded instrument is switched on by the server's environment and falls back to the
synthesized sound when its switch is off or its pack is missing. Whether a switch is on in the
deployed Cloud app is set by its secrets; that is **not** checked here. `backing_sound_status` reports
what actually plays, from inside a running app.

## Recorded instruments in the repo

| | Grand piano | Double bass | Electric guitar | Drum kit | Tenor saxophone (new) |
|---|---|---|---|---|---|
| Folder | `assets/instruments/grand_piano` | `assets/instruments/double_bass` | `assets/instruments/electric_guitar` | `assets/drum_kit` | `assets/instruments/tenor_sax` |
| Source | Steinway B, close mic, no pedal, from the Versilian Community Sample Library (`sgossner/VCSL`) | 1958 Otto Rubner double bass, played and mapped by D. Smolken (`sfzinstruments/dsmolken.double-bass`) | Epiphone Emily the Strange, recorded direct, D. Smolken / Karoryfer (`sfzinstruments/karoryfer.emilyguitar`) | Virtuosity Drums, played by Austin McMahon, Versilian Studios + Karoryfer (`sfzinstruments/virtuosity_drums`) | VCSL tenor saxophone, player credited as "Brett" in the file names (`sgossner/VCSL` @ `c1ea7bcc`) |
| License | CC0 1.0 (`LICENSE` in the folder) | CC0 1.0 | CC0 1.0 | CC0 1.0 | CC0 1.0 (VCSL's own `LICENSE`, same text as the piano's) |
| Files / size | 36 FLAC, 3.9 MB | 71 FLAC, 3.9 MB | 124 FLAC, 7.1 MB | 321 FLAC, 9.6 MB | 48 FLAC, 2.9 MB |
| Format | mono 16-bit 44.1 kHz FLAC | same | same | same | same |
| Articulations | sustained notes, no pedal | pizzicato | sustained notes, 10 dead strokes, 6 string releases; palm mutes made at render time (`variants`) | 20 voices: closed / half / three-quarter / open / pedal hi-hat, ride, bell, crash, sizzle, kick, snare, rimshot, rim, buzz, muted, kick / snare / rimshot close mics, low and high tom | Non-Vibrato sustain (cut to 2.5 s, looped at render time), Staccato |
| Velocity layers x takes | 3 x 1 | 3 x 3 | 3 x 3 | 3-12 layers x 1-4 round robins | sustain 1 x 1 (VCSL `vl3`); staccato 2 x 1 (`vl1`, `vl2`; the lowest three notes only `vl2`) |
| Sampled range (zones) | E2-C6 (MIDI 40-84), 12 zones, major thirds | Eb1-E3 (MIDI 27-52), 8 zones | C#2-A4 (MIDI 37-69), 12 zones | unpitched | concert Ab2-E5 (MIDI 44-76), 17 zones each, whole tones (staccato gaps up to a minor third) |
| Played by | `backing_pianist.py` (`_grand`, via `backing_sampled_instrument.SampledInstrument`) | `backing_bass_voice.py` (`_double_bass`) | `backing_rock_guitar.py` (`_guitar`) + `backing_guitar_amp.py` | `backing_drum_kit.py` + `backing_drum_samples.py` (its own hit cache) | `backing_horns.py` (`_pack`, two `SampledInstrument` views) |
| Switch | `MUSIC_PIANO_V2=recorded` (`varied` = new comping on the synthesized piano) | `MUSIC_UPRIGHT_BASS=recorded` (`model` = plucked-string model) | `MUSIC_ROCK_GUITAR=recorded` | `MUSIC_DRUM_KIT_V2=1`; pack chosen by `MUSIC_DRUM_PACK_DIR` / `MUSIC_DRUM_PACK_MODE` | `MUSIC_HORNS=1` |
| Where it plays | every style that uses the pianist (`backing_audio`, when the plan lets keys play) | Jazz swing only | Rock groove only | every style | nowhere yet: no caller, no ensemble |
| Status | integrated, off by default in code | integrated, off by default | integrated, off by default | integrated, off by default | pack + renderer + part generator only; not wired into `generate_backing_track`, not offered in any UI |

Shared machinery: `backing_sampled_instrument.SampledInstrument` (manifest zones -> nearest zone,
velocity layer with a small seeded nudge, round-robin that avoids repeats, pitch shift by linear
interpolation, `cents` correction, `gain` evening) and `backing_sample_cache.SHARED` (one
LRU store of decoded audio, `MUSIC_SAMPLE_CACHE_MB`, default 96 MB). The drum kit keeps its own
equivalent cache in `backing_drum_samples`. Each module's `*_renderer_tag()` goes into saved audio's
signature so a take from another sound is never replayed as this one; `backing_horns.horns_renderer_tag()`
exists for the same purpose but is not part of any signature yet.

### The tenor saxophone in detail

* **Source files**: `https://github.com/sgossner/VCSL/tree/c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e/Aerophones/Reed%20Aerophones/Tenor%20Saxophone`
  - `Staccato/BrettTenor_Staccato_Main_<note>_vl<1|2>_rr<n>.wav` - 31 of the 40 (altissimo left out)
  - `Non-Vibrato/BrettTenor_NV_Main_<note>_vl3_rr1.wav` - 17 of the 46 (the `vl2` layer and altissimo left out)
  - Originals are 48 kHz / 24-bit stereo; downloaded to a scratch folder, never committed.
* **License evidence**: GitHub reports the VCSL repository license as `CC0-1.0`; the repository's
  `LICENSE` is the CC0 1.0 Universal legal code (copied unchanged into the pack); its README says
  "This collection is under a Creative Commons 0 license ... you can do whatever you want with these
  sounds (even make commercial software), no royalties, no credit, no special terms."
* **Note names**: VCSL names middle C `C3`. Every file's pitch was measured: the names hold (the
  lowest file, `G#1`, is 103.8 Hz = Ab2, the tenor's lowest concert note). The sustains measure within
  0.2 cents (VCSL tunes them); staccato within 9 cents, corrected by `cents` on playback.
* **Range**: the recordings run from concert Ab2 to E6. The tenor's normal range is written Bb3-F#6,
  sounding a major ninth lower, Ab2-E5 (MIDI 44-76); the pack keeps exactly that and
  `backing_horns.clamp_to_range` moves any note into it by octaves. Backgrounds sit in D3-Bb4.
* **Processing** (`tools/prepare_tenor_sax_pack.py`): the right microphone only (the spaced pair
  correlates at 0.3-0.5 and a mono sum lost about 2 dB to comb filtering), resampled to 44.1 kHz,
  4 ms pre-roll with a 3 ms fade-in, a sustain's attack held to 3 dB over its body (changes only the
  accented A#2 audibly), sustains cut to 2.5 s with a 0.30 s fade-out, staccato cut below -60 dB with a
  25 ms fade-out, normalised, 16-bit FLAC. `gain` evens each note to its layer's median loudness.
* **Not verified**: the instrument's make, the mouthpiece and the microphones (VCSL does not say);
  sound quality in a full mix has not been judged by ear - the demos were measured, not listened to.

## Trombone and trumpet (new, not in any ensemble)

Added later on the same branch. Both packs are CC0 from VS Chamber Orchestra 2: Community Edition
(`sgossner/VSCO-2-CE` @ `440300901dfe9275fd84e0b7763af1f8443ae62e`), built by `tools/prepare_vsco_brass_pack.py`
with the tenor's processing (one channel, 4 ms pre-roll, 3 ms fade-in, sustains 2.5 s, staccato cut below -60 dB,
16-bit mono FLAC, no resampling or pitch shifting) and played by `backing_horns.py` with `instrument="trombone"` /
`"trumpet"`, only when `MUSIC_HORNS` is on. Nothing calls them yet: no ensemble, no UI.

| | Trombone | Trumpet |
|---|---|---|
| Folder | `assets/instruments/trombone` | `assets/instruments/trumpet` |
| Source | `Brass/OldTrombone`: a 1950s Olds Super tenor trombone ("unreleased sample set done as a test for VSCO 2", per its `Notes.txt`); player not named | `Brass/Trumpet` (`Sum_SHTrumpet_*`); make and player not named; an orchestral player |
| Files / size | 92 FLAC, 3.9 MB | 86 FLAC, 5.1 MB |
| Sustain | 16 zones F2-G4 (MIDI 41-67), whole tones or semitones apart; layers `v3` (soft) and `v4` (loud) of 5 (`v2` / `v5` stand in at G4) | 10 zones F3-C6 (MIDI 53-84), 3-4 semitones apart; both layers (`v1`, `v3`), straight (no vibrato) |
| Staccato | `Short`: 15 zones F2-F4, layers `v2`, `v3` of 3, 2 round robins | 11 zones F3-C6, all 3 layers, 2 round robins |
| Left out | `v1`, `v2`, `v5` sustain layers, `Buzz`, `Fall`, `Vibrato`, the other round robins | `susvib`, straight- and harmon-mute sustains |
| Pitch | every file within 15 cents (corrected on playback), octave checked by YIN | within 23 cents, octave checked |
| Background register | C3-D4 (48-62) | C4-F5 (60-77) |

* **Velocity layers**: a softer layer is kept within 8 dB of its articulation's loudest (recorded gaps are 15-22 dB),
  so a change of dynamic changes tone more than level. `Horn.level` then sets each articulation so the default
  pads and hits are as loud as the tenor's.
* **Loops**: sustains held past 2.5 s loop from where the waveform matches the join (the trombone sustains are
  phase-locked), with a crossfade scaled for that match; worst level dip over 6 s held notes in the background
  registers: -4.5 dB (trombone), -3.5 dB (trumpet).
* **Two horns**: `backing_horns.section_voicing` / `render_section_background` - the top horn on a guide tone, the
  lower one a third, sixth or tenth under it, the least-moving pairs over the progression, neither on the root or
  the bass note.
* **License**: GitHub `CC0-1.0` for the repository, the `LICENSE` file is CC0 1.0 Universal (copied unchanged). The
  repository's `Readme.txt` also *asks* that the samples are not sold directly and that Versilian Studios / Sam Gossner
  be credited where applicable - a request, not a licence term; each pack's README carries the credit.
* **Not verified**: how either sounds in a full mix or to a jazz ear - the demos were measured, not listened to.

## Roadmap gaps and candidate sources

The ensembles (`backing_performance_plan.ENSEMBLES`) report what they miss in `EnsembleSpec.missing`:
"Jazz quartet" misses `horns`, "Latin quartet" misses `percussion`, "Neo-soul band" misses its
`guitar` renderer. `RENDERABLE_ROLES` is still `drums, bass, keys, guitar`. This slice leaves all of
that unchanged.

"Verified" below means: the license was read from the official repository on 2026-11-24 - GitHub's
license detection (which reads the repository's LICENSE file), plus the LICENSE text or README where
quoted. The samples themselves were not
downloaded or inspected unless stated. "Unverified" means no license could be confirmed from an
official page; do not use those until it is.

| Gap | Candidate | License | What is there |
|---|---|---|---|
| Tenor sax | VCSL `Aerophones/Reed Aerophones/Tenor Saxophone` | **CC0, verified** | Non-Vibrato (2 layers), Staccato (2 layers, round robins), Vibrato (1 take per note). **Used** (see above). |
| Alto sax | `sfzinstruments/karoryfer.weresax` | **CC0, verified** (GitHub `CC0-1.0`; LICENSE is CC0 1.0) | an alto saxophone, two mic positions; vibrato is synthesized by its SFZ (CC controls), so a sampler of our own would play it plain. Samples not inspected. |
| Baritone sax | `sfzinstruments/karoryfer.bear-sax` | **CC0, verified** (GitHub `CC0-1.0`; readme "Royalty-free for all commercial and non-commercial use") | a 1926 Conn baritone: sustain, marcato, staccato, subtone, growl. Samples not inspected. |
| Soprano / alto / tenor / baritone sax | `sfzinstruments/MTG.SoloSax` | **Unverified**: the SFZ repo is CC-BY-4.0, but its samples come from MTG packs on freesound.org whose per-sample licenses were not checked | trimmed, looped mono 48 kHz FLAC of all four saxes |
| Trumpet | `sgossner/VSCO-2-CE` `Brass/Trumpet` (Versilian, same family as VCSL) | **CC0, verified** (GitHub `CC0-1.0`; LICENSE is CC0 1.0) | `sus` (20 files), `stac` (66), `susvib`, straight-mute and harmon-mute sustains. An orchestral player, not a jazz one; untested for jazz backgrounds. **Packed** (`assets/instruments/trumpet`, see above). |
| Trombone | `sgossner/VSCO-2-CE` `Brass/Tenor Trombone` (+ `OldTrombone`: buzz, fall, short, sustain, vibrato) | **CC0, verified** | `sus` (31), `stac`, `vib`; `OldTrombone` is better sampled (16 sustain zones, 5 layers) and is the one **packed** (`assets/instruments/trombone`) |
| Tuba (as bass) | `sgossner/VSCO-2-CE` `Brass/Tuba` | **CC0, verified** | `sus` (23), `stac` (64 incl. round robins) |
| Tuba (as bass) | `sfzinstruments/karoryfer.war-tuba` | **CC0, verified** (GitHub `CC0-1.0`; readme royalty-free) | staccatissimo, staccato, sustain; one tuba (its duo/trio are transposed copies) |
| Acoustic steel guitar | `sfzinstruments/OvationGuitar` | **Unverified** (no license file detected; a GigaSampler conversion) | Ovation guitar |
| Nylon guitar | none found | - | No CC0 / verified nylon-string library was found in VCSL, VSCO 2 CE or `sfzinstruments`. Still open. |
| Archtop / hollow-body guitar (jazz, neo-soul) | `sfzinstruments/karoryfer.shinyguitar` (archtop), `karoryfer.black-and-green-guitars` (Gretsch Anniversary, Hofner Club) | **CC0, verified** (GitHub `CC0-1.0`) | electric archtop / hollow-bodies; candidates for the Neo-soul guitar |
| Funk guitar | `sfzinstruments/DamiensFunkyGuitar` | **Unverified** (no license file detected) | muted funk guitar |
| Recorded electric bass | `sfzinstruments/karoryfer.growlybass` (Squier Jazz Bass), `karoryfer.swagbass`, `karoryfer.fashionbass`, `karoryfer.big-little-bass` (readme says "CC-0 license"), `karoryfer.black-and-blue-basses`, `karoryfer.pastabass` (Squier Bass VI) | **CC0, verified** for each by GitHub `CC0-1.0` | bass guitars with release samples and noises; Growlybass is the plainest fit for Funk / Soul / Rock |
| Latin percussion | VCSL `Membranophones/Struck Membranophones/Bongos` (28 files, 6.8 MB raw: high/low hit, muted hit, roll) and `Conga` (34 files, 4.9 MB raw: conga, quinto, tumba, open and muffled hits); `Idiophones/Struck Idiophones`: Agogo Bells, Cabasa, Claves, Cowbells, Guiro, Shaker (small / large), Woodblock | **CC0, verified** (VCSL) | everything a Latin quartet needs except **timbales** (none found in VCSL or VSCO 2 CE) |
| Latin percussion | `sgossner/VSCO-2-CE` `Percussion`: Conga / Quinto / Tumba hits and taps, Claves, Cowbell, Guiro, Tambourine | **CC0, verified** | a second take on the same set |
| Cabasa | `sfzinstruments/kinwie.dim-cabasa` | CC-BY-4.0 (GitHub) - needs credit, not CC0 | 250 direct 24-bit 48 kHz samples |

## Recommended order

1. **Wire the tenor in behind its switch** (next slice): a `horns` role in `RENDERABLE_ROLES`, the
   Jazz quartet's `missing` emptied only when `MUSIC_HORNS` is on and the pack is present, the horn
   bus mixed under the soloist, `horns_renderer_tag()` in the saved-audio signature, then an ear check
   on real songs. Add the Non-Vibrato `vl2` layer (about 1.5 MB more) for soft backgrounds.
2. **Latin percussion from VCSL** (CC0, verified, small): congas, bongos, cowbell, claves, guiro,
   shaker - fills the Latin quartet's `missing` and suits Bossa nova / Samba / Latin jazz. Timbales
   still need a source.
3. **Trumpet and trombone from VSCO 2 CE** (CC0, verified): packed and playable (see above); next is an ear
   check of the demos, then offering a two-horn section in an ensemble behind `MUSIC_HORNS`.
4. Recorded electric bass (Growlybass), then an archtop guitar for Neo-soul.
