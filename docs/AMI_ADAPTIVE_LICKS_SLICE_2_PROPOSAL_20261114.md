# Adaptive Licks Slice 2 proposal: harmonic adaptation through a selected chart

Proposal only. Requires separate approval; do not enable song adaptation as part of Slice 1.

Begin with the musician-selected Blue Bossa / Kenny Dorham catalog record and its actual section or whole-form snapshot. Use `warmup_song.read_song` and the existing section-selection/conflict rules, `scale_pattern_harmony.timeline_segments` and the authoritative chord subdivisions. Keep source key, current Practice Key, chart identity/hash, meter, section boundaries and instrument-written projection in the existing exercise context. Do not invent a chart or replace the snapshot with a guessed progression.

Three distinct operations need explicit names:

- Literal transposition preserves the cell's semitone offsets and rhythm. It does not claim that every resulting note fits every chord.
- Diatonic adaptation preserves the cell's degree relationships within an explicitly identified collection for each harmonic span. The resulting semitone intervals may change.
- Chord-role substitution preserves an agreed role pattern (for example root-third-fifth-seventh). It changes the original melodic intervals and must be described as an adaptation.

A chord symbol alone does not select a unique scale. Reuse only supported, documented harmonic rules from the existing chord-scale and chord-line generators. State the chosen collection and why. Altered dominants, ambiguous extensions, unsupported symbols and conflicting chart context require a choice or an explicit limitation; never silently select a scale. A chromatic approach from the original cell also needs an explicit approach/target rule rather than automatic removal.

Initial scheduler boundary: one four-attack cell, fixed rhythm, scheduled against exact Fraction beat spans. Include split measures. If the complete cell does not fit before a change, explain the available choices: a shorter note value, a cell explicitly allowed to continue across the change, or a different entry point. Do not silently drop attacks, shorten durations, add ties or move the harmony. Any continuation policy must verify every onset against the actual chord timeline and label cross-change notes. Rests and sustained notes remain explicit events.

Use the existing range profiles and written/concert offset, shared notation serializer, level-aware note-name display, owner-scoped history and read-only Explain behavior. Preserve the original cell separately from the adaptation. Explain must show the measured mapping and limitations without regenerating or committing a history version. A changed chart snapshot must invoke the existing stale-context protections.

Acceptance must include independently checked chord-at-onset fixtures from the actual selected chart, two-chord split measures, rhythm totals, exact cell count and identity, instrument ranges, written/concert spelling, conventional beaming, mobile/desktop staff, note-name defaults and overrides, exact Undo/Redo and account/workspace isolation. Use a concert instrument and alto saxophone, plus a B-flat instrument projection. Verify playback/Key Cycling and sidebar settings remain unchanged.

After Blue Bossa and a real split-measure fixture pass, propose All the Things You Are separately. Its catalog has multiple identities; use the selected record and actual available section names. A request for a verse is not permission to invent a verse or assume the whole 36-bar form. Broader whole-song scheduling and additional harmonic rule sets need their own acceptance gate.
