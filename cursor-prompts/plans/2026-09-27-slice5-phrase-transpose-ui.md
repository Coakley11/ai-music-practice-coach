# Slice 5 — Phrase / Motif, Transpose helpers, icons, Written charts, Composition UI

**Date:** 2026-09-27  
**Branch:** `feature/slice5-phrase-transpose-ui`  
**Baseline:** `origin/dev` @ `2a337099` (includes validated stabilization ancestor `c4113242`)  
**Out of scope:** monetization; broad ownership redesign; reopening closed Catalog/SBI/Jam/Mission/Composition Backing / PK / Back-Forward cycles unless a new regression appears.

---

## Closed (do not reopen)

Stabilization cycle accepted at `c4113242` with `LOCAL_DEV_POST_MERGE_BROWSER_SMOKE=PASS`:

- Catalog / SBI Custom / Jam-Entry / Missions / Composition ownership
- Backing owner envelopes + Practice Key across owners
- Polluted five-owner journey
- Back/Forward history + Creative workspaces as separate destinations

---

## Goals

### 1. Phrase / Motif

- Remove `Diatonic` as a user-facing option (or equivalent control).
- Remove redundant Descending button; keep **one** Ascending/Descending control.
- Make **Auto / Musical** capable of musically coherent non-diatonic / chromatic / accidental patterns — not Seconds-like behavior.

Implementation note: extend `improvisation_motif` / `motif_engine` (unified engine); UI only wires constraints.

### 2. Transpose Helpers — consolidate

Single section: **↔️ Transpose helpers**

**Guitar:** Original Key · Practice/Concert Key · transposition from Original · Shape Key · Capo · chart/shapes key  

**Clarinet / Saxophone:** Original Key · Practice/Concert Key · instrument · Written Key · written-chart ON/OFF · chart key · transposition from Original  

Do not repeat the same facts across multiple helper blocks.

### 3. Instrument / Shape icons

| Surface | Icon |
|---------|------|
| Clarinet badge | clarinet |
| Saxophone | sax |
| Guitar | guitar |
| Shape Key | guitar |

Avoid generic/sax icons on the wrong instrument.

### 4. Written chart toggle (Practice)

Practice-page written-chart checkbox must toggle ON/OFF reliably and persist without changing Practice Key or instrument.

### 5. Composition UI

- Remove redundant top **Edit** button.
- Under **Start New Song**, right-panel nav: Practice · Songs · Backing.
- Practice and Backing enabled only when the composition being edited is **active**.
- Improve chord alignment with melody notation (visual correspondence to note/onset timing).

---

## Suggested delivery order

1. Written-chart toggle persistence (small, high leverage)  
2. Transpose helpers consolidation  
3. Instrument / Shape icons  
4. Phrase / Motif controls + Auto/Musical musicality  
5. Composition nav + Edit cleanup + chord/melody alignment  

---

## Acceptance (manual / browser)

- [ ] Phrase/Motif: no Diatonic; single Asc/Desc; Auto/Musical produces coherent non-diatonic options  
- [ ] One Transpose helpers block per instrument family; no duplicate key facts  
- [ ] Icons match Clarinet / Sax / Guitar / Shape Key  
- [ ] Written charts ON/OFF persists across rerun; PK + instrument unchanged  
- [ ] Composition: no redundant Edit; Practice/Songs/Backing under Start New Song; Practice/Backing gated on active composition; chords track melody onsets visually  

---

## Notes

- Keep commits separate from monetization and from ownership/Back-Forward work.  
- Prefer SSOT modules for motif generation; pages stay UI shells.  
