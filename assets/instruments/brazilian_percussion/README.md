# Brazilian percussion (Samba ensemble)

Acoustic recordings from the Versilian Community Sample Library (`sgossner/VCSL`, https://github.com/sgossner/VCSL),
released under CC0 (see `LICENSE`, copied from the VCSL repository): commercial use allowed, no royalties, no credit
required. The same library as the recorded grand piano and the Latin percussion pack.

No CC0 or otherwise freely redistributable recording of a real surdo, pandeiro or tamborim was found (searched VCSL,
GitHub sample repositories and the web: what exists is commercial, CC BY with attribution, or non-commercial). The
closest acoustic recordings stand in, and are named for the role they play:

| Voice | Recording | What it stands for |
|---|---|---|
| surdo_high | Bass Drum 1 (`BDrumNew_hit`, 4 layers x 2 round robins), about 85 Hz | surdo de segunda (marks 1) |
| surdo_low | Bass Drum 2 (`bassdrum_hit` pp..ff, 5 layers), about 42 Hz | surdo de primeira (the strong 2) |
| pandeiro_skin_muted / pandeiro_skin_open | large frame drum (`HDrumL` muted / open hits, 2 layers x 2) | the pandeiro's skin (thumb and open tones) |
| pandeiro_jingle / pandeiro_shake | Tambourine 1 and 2 hits and shakes | the pandeiro's jingles |
| tamborim | small frame drum, muted hits (`HDrumS_HitMuted`, 2 layers x 2) | tamborim (a stand-in: a hand-played frame drum, not a stick-struck tamborim) |
| ganza_down / ganza_up | small and large shakers, down / up strokes (4 round robins each) | ganza |
| agogo_high / agogo_low | Agogo Bells, high (3 layers) / low (2 layers) | agogo (the real instrument) |

The frame drum's "hand" stroke was left out (its peak was at the noise floor).

Processing: summed to mono, the silence before each onset removed (2 ms kept), the tail cut where it stays below
-60 dB of the hit's peak, a length cap per voice, an 8 ms fade-out, 16-bit FLAC at 44.1 kHz. No pitch change, EQ,
compression or normalisation. Prepared with the scratch script `prep_brazil_pack.py`.
