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

### 1. Phrase / Motif — Slice 5D DONE

- Remove `Diatonic` as a user-facing option (`PATTERN_TYPES_UI`; legacy `diatonic` → `scalar`).
- Remove redundant Descending button; keep **one** Ascending/Descending Direction selectbox.
- **Auto / Musical** uses chromatic collection + skip cell offsets (not Seconds); key-aware spelling via `_note_from_midi` / respell.

Implementation note: extend `improvisation_motif` / `motif_engine` (unified engine); UI only wires constraints.

### 2. Transpose Helpers — consolidate — Slice 5B DONE

Single section: **↔️ Transpose helpers** (`transpose_helpers_facts` / `render_unified_transpose_helpers`)

**Guitar:** Original Key · Practice/Concert Key · transposition from Original · Shape Key · Capo · chart/shapes key  

**Clarinet / Saxophone:** Original Key · Practice/Concert Key · instrument · Written Key · written-chart ON/OFF · chart key · transposition from Original  

Do not repeat the same facts across multiple helper blocks. Practice transpose tool no longer stacks separate sax / general / capo expanders.

### 3. Instrument / Shape icons — Slice 5C DONE

| Surface | Icon |
|---------|------|
| Clarinet badge | `instrument_icon("Clarinet")` (🎐; not sax/songs/note) |
| Saxophone | 🎷 |
| Guitar | 🎸 |
| Shape Key | 🎸 |
| Piano | 🎹 |

SSOT: `music_feature_icons.INSTRUMENT_ICONS` / `instrument_icon` / instrument-aware `semantic_field_icon("written_key", instrument=...)`.

### 4. Written chart toggle (Practice) — Slice 5A DONE

Practice-page written-chart checkbox must toggle ON/OFF reliably and persist without changing Practice Key or instrument.

**Root cause:** every-rerun `sync_written_key_instrument_anchor` hard-cleared ON when a stale wrong-family `_chart_written_key_instrument_anchor` lagged the live instrument (common after refresh/cloud). Soft sync now realigns the anchor only; hard clear remains on intentional Instrument change.

### 5. Composition UI — Slice 5E DONE

- Remove redundant top Review phase-jump row (`Return to editing` / `composer_review_edit_*`).
- Under **Start new song**, right-panel nav: Practice · Songs · Backing via `navigate_studio_page`.
- Practice and Backing enabled only when the Studio document is the Global Active Composition.
- Chord/melody alignment: ABC chord annotations at onsets + proportional chord-strip flex widths.

---

## Suggested delivery order

1. Written-chart toggle persistence (small, high leverage)  
2. Transpose helpers consolidation  
3. Instrument / Shape icons  
4. Phrase / Motif controls + Auto/Musical musicality  
5. Composition nav + Edit cleanup + chord/melody alignment  

---

## Acceptance (manual / browser)

- [x] Phrase/Motif: no Diatonic; single Asc/Desc; Auto/Musical produces coherent non-diatonic options (Slice 5D)  
- [x] One Transpose helpers block per instrument family; no duplicate key facts (Slice 5B)
- [x] Icons match Clarinet / Sax / Guitar / Shape Key (Slice 5C)
- [x] Written charts ON/OFF persists across rerun; PK + instrument unchanged (Slice 5A)
- [x] Composition: no redundant Edit; Practice/Songs/Backing under Start New Song; Practice/Backing gated on active composition; chords track melody onsets visually (Slice 5E)  

---

## Notes

- Keep commits separate from monetization and from ownership/Back-Forward work.  
- Prefer SSOT modules for motif generation; pages stay UI shells.  
