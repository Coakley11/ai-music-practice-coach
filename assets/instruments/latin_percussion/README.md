# Latin percussion

One-shot hits from the Versilian Community Sample Library (`sgossner/VCSL`, https://github.com/sgossner/VCSL):
conga, tumba and bongos (`Membranophones/Struck Membranophones`), claves, small shaker, cowbell, agogo bells,
tambourine and cabasa (`Idiophones/Struck Idiophones`).
Released under CC0: see `LICENSE` (copied from the VCSL repository). Commercial use is allowed, with no royalties and
no credit required. This is the same library the recorded grand piano comes from.

Processing: summed to mono, the silence before each onset removed (2 ms kept), the tail cut where it stays below
-60 dB of the hit's peak, a length cap per voice, an 8 ms fade-out, 16-bit FLAC. No EQ, compression or
normalisation: the engine levels each hit by its energy when it loads it. One tumba round robin was left out (its
peak was at the noise floor).

`manifest.json` maps each voice to its velocity layers (soft to loud), each a list of round robins, in the format of
`assets/drum_kit` (read by `backing_drum_samples.SamplePack`).

| Voice | Source files |
|---|---|
| conga_open | Conga_HitN (open tone), 3 layers |
| conga_muted | Conga_HitFM (muted), 2 layers |
| tumba_open | Tumba_HitN (low drum, open tone), 4 layers |
| bongo_high / bongo_low | BongoH_Hit1 / BongoL_Hit1, 3 layers |
| clave | Claves1_Hit, 3 layers |
| shaker_down / shaker_up | Shaker, Small: Mid_ShakerHighFaster Down / Up strokes |
| cowbell / cowbell_muted | Cowbell1 Normal / Muted, 2 layers |
| agogo_high / agogo_low | Agogo_High (3 layers) / Agogo_Low (2 layers) |
| tamb | Tambourine 1 hit, 2 layers (stands in for the pandeiro's jingles) |
| cabasa | Cabasa1 hit |

Prepared with the scratch script `prep_latin_pack.py` (download to a folder outside the repository, then process).
