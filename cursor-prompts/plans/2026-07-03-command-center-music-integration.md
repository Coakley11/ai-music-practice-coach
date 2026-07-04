# Command Center ↔ Music integration sprint

**Last updated:** 2026-07-03  
**Branch:** `dev`  
**Status:** Music-side shipped (2026-07-03); Command Center homepage UI pending (external repo)

---

## Design rule

| Zone | Purpose | Click behavior |
|------|---------|----------------|
| **Continue cards** (top) | Specific resumable music tasks | Restore exact task context |
| **App Directory** (bottom) | Broader long-term workspace summary | Open Music to current/last general workspace |

**Continue = specific task restore.**  
**App Directory = general workstream entry.**

Account workspace isolation is mandatory: `coakley11` cards must only reflect `coakley11` workspace activity; Daniel activity must not leak across accounts.

---

## Continue cards — restore specific state

Each Continue card must deep-link into Music with a **resume payload** that restores:

| Card type | Restores |
|-----------|----------|
| Continue practicing a song | `active_catalog_pick_key`, instrument, display/concert key, BPM, practice focus, `studio_page=practice` |
| Continue multitrack recording | multitrack session id, slot state, `studio_page=multitrack` |
| Continue backing-track session | song/custom/creative backing ctx, scope, sections, BPM, groove, `studio_page=backing` |
| Continue Creative Lab setup | creative session, entry mode, style jam / SBI / mission ctx, `studio_page=creative` |
| Continue tone/tuner work | instrument, last tone take context, Practice tone panel |
| Continue upload/song workflow | upload analysis id or picker context, `studio_page=analysis` or `picker` |

### Example

Card: **Continue Shape of You — Tenor Sax — Key: B minor — 90 BPM**

Click must restore:
- Song: Shape of You (pick key)
- Instrument: Tenor Sax
- Key: B minor (concert + written as applicable)
- BPM: 90
- Page: Practice (or last page if encoded in resume payload)

Must **not** open blank/generic Music state.

### Music-side implementation

1. **`music_resume_payload.py`** (new) — canonical resume envelope per task type
2. **`suite_resume_launch.py`** — extend `finalize_*_restore` to apply music resume payloads from Command Center URL/query
3. **`suite_analytical_question.py`** / handoff builders — emit structured `context` + `resume_kind` + `resume_payload`
4. **Workspace gate** — every card build/read filters by `workspace_id` + `suite_user` identity
5. **Tests** — cross-user isolation; round-trip restore for practice + backing payloads

---

## App Directory — general workstream entry

Lower cards summarize longer-term activity; click opens Music without forcing an old song snapshot.

| Card example | Opens to |
|--------------|----------|
| Practicing Shape of You across recent sessions | Practice page, **current** workspace song if changed since card was built |
| Recent backing-track work | Backing Studio, last general backing workspace |
| Multitrack recording work | Multitrack page, active session list |
| Uploaded song library | Upload/Analysis or media library view |
| Tone practice history | Practice page tone section |

Preserves current workspace/account state; does not overwrite active song with stale card metadata unless user explicitly chose a Continue card.

---

## Command Center repo work (paired)

- Continue card builder: top section, one card per resumable task
- App Directory builder: bottom section, aggregated workstream summaries
- Storage: resume items keyed by `workspace_id`
- Deep link URL: `?resume=music&kind=practice&...` or signed resume token

---

## Acceptance tests

### Continue
- [ ] Practice continue restores song + instrument + key + BPM + page
- [ ] Backing continue restores scope/sections/BPM/style
- [ ] Creative continue restores entry mode + jam context
- [ ] Multitrack continue restores session
- [ ] coakley11 never sees Daniel continue cards

### App Directory
- [ ] Opens Music without blank state
- [ ] Does not clobber current active song when user changed song since card was written
- [ ] Workspace isolation on summaries

---

## Implementation order

1. Resume payload schema + workspace isolation tests (Music)
2. Practice + Backing continue restore (highest traffic)
3. Creative + Multitrack continue restore
4. Tone/upload continue restore
5. App Directory cards (summary-only, soft entry)
6. Command Center card UI + storage (external repo)
