# Authentic Samba percussion (MUSIC_SAMBA_AUTHENTIC)

Single strokes of real Brazilian instruments cut from Freesound recordings; credits in `CREDITS.md`, per-file provenance in
`ATTRIBUTION.json`. Played by `backing_samba_ensemble` when `MUSIC_SAMBA_AUTHENTIC` is `1` (all) or a list such as
`surdo,tamborim`.

| Voice | Recording | Takes |
|---|---|---|
| surdo_low_open | Vivabarca1899 "Surdo.wav", the ~50 Hz drum (CC BY 3.0) | 4 (decay to -40 dB inside each slice; a tight drum: -20 dB after ~0.2 s) |
| surdo_high_open | igorfiche01 "AKG 414 Surdo Processed" (CC0; the processing is not described) | 8 (2 layers) |
| pandeiro_bass | MeanRaccoon "pandeiro A collection" (CC0) | 5 |
| pandeiro_jingle | MeanRaccoon "pandeiro A collection" (CC0) | 14 (3 layers) |
| tamborim_muted | MeanRaccoon "tamborim A1" / "tamborim B" collections (CC0) | 10 (2 layers) |

Selection rules (scratch `build_authentic_pack.py`): no clipped stroke; peak >= -30 dBFS; articulation from measurements;
dynamic layers from peak level; takes spread through each recording; no near-duplicates (correlation < 0.98). A stroke the
next stroke cut while still ringing gets a 60 ms fade; it is rejected when still louder than -18 dB re its peak at the cut
(surdos), -15 dB (pandeiro bass) or -10 / -12 dB (the short, damped tamborim and jingle strokes).

Investigated and left out:
- Paulo Goncalves' pandeiro (CC BY 4.0; genuine, goat-leather head): a different, much brighter pandeiro than MeanRaccoon's
  (55-80 % of its jingle energy above 9 kHz, against 48 %, with almost no 2-9 kHz body); mixed in, the instrument would change
  from stroke to stroke and add top-end edge. Only 5 sounds in all.
- The single open tamborim stroke (one take would repeat mechanically).
- Kayo_martins' pandeiro (CC0): 52 clipped strokes. gilblack1234's "Surdo" (CC0): a 0.17 s studio drum hit.
- Every non-commercial (NC) recording.

All samples come from Freesound's public HQ previews (MP3, about 185 kbps; no account used). The full-quality originals need a
Freesound login.
