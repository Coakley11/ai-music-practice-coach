# Persistence contract — refresh / reboot (Creative / Backing)

**Last updated:** 2026-08-23  
**Status:** ACTIVE CONTRACT for Pass 8 Creative/Backing stabilization  
**Branch:** `feature/creative-backing-stabilization`  
**Related:** [2026-08-18-pass8-creative-backing-stabilization.md](./2026-08-18-pass8-creative-backing-stabilization.md), Item 5 refresh/cold-reboot ([2026-08-03-item5-refresh-cold-reboot-persistence.md](./2026-08-03-item5-refresh-cold-reboot-persistence.md))  
**Parked:** Practice Focus — do not touch

---

## Central rule

**Refresh / reboot must restore the user’s current workspace.**

It must **not** behave like:

- selecting a new song
- starting a new Creative session
- leaving Backing
- resetting instrument projection
- resetting selected chord/section
- resetting Practice Key

**Do NOT treat refresh/reboot as a reset of the user’s current workflow state.**

The left-panel **Practice / Concert Key** must remain **editable** everywhere the user is actively working with a musical source — including after refresh.

---

## Scope of persistence

The following state must persist across:

- Streamlit rerun
- browser refresh
- app reboot/restart
- returning to the same page after reload

**provided** the underlying active source/workflow itself has not been explicitly changed by the user.

---

## 1. Creative page selections must persist

Selections inside Creative tools persist on refresh/reboot, including:

- selected Mission
- selected Mission section
- selected Mission chord
- selected Live Coach chord
- selected Live Harmony / Harmony Map chord or section
- selected Motif chord
- selected SBI source tab
- current Custom progression used by SBI
- any other Creative sub-selection that defines what the user is working on

**Example:** Mission · Section = Verse 1 · Chord = F#m → refresh → same Mission, Verse 1, F#m.

Do **not** silently reset to first chord, home section, first Mission, or generic Creative state.

---

## 2. Instrument / Written / Shape settings must persist

Player-facing projection settings persist across refresh/reboot:

- selected instrument
- saxophone subtype (Alto / Tenor / …)
- Written Charts ON/OFF
- Guitar Shape mode ON/OFF
- selected Shape Key
- Capo state
- other relevant instrument/player projection settings

**Examples:** Alto Sax + Written ON → still Alto + Written ON with correct written projection. Guitar Shape Key D + Capo ON → same Shape/Capo.

Do **not** fall back to Piano, default instrument, Concert charts, or another Shape.

---

## 3. Practice / Concert Key must always be editable

Global UI rule: the left-panel Practice / Concert Key must **always** be changeable whenever the current workflow supports a musical source, including:

- Songs / Song Selection
- Custom page
- Creative page (Missions, SBI, Harmony Map, Live Coach, Motif, …)
- Practice
- regular Backing
- Mission / SBI / Custom SBI / Jam Generator / Entry Style Backing
- other specialized Backing pages

Do **not** disable, lock, remount, or ignore the Practice Key control merely because the user is on a Creative or Backing page.

When the user changes it, the **current owning workflow** updates coherently (progression, examples, staff, labels, map projection, etc.). The control must remain functional after refresh too.

---

## 4. Backing page type must persist on refresh / reboot

If the user is on a Backing page, refresh/reboot restores the **same** Backing workflow:

| Before refresh | After refresh |
|----------------|---------------|
| Regular Catalog Backing | Regular Catalog Backing |
| Mission Backing | same Mission Backing |
| SBI Active Backing | same SBI Active Backing |
| Custom SBI Backing | **same** Custom SBI Backing |
| Jam Session Generator Backing | same Jam Generator Backing |
| Entry Style Jam Backing | same Entry Style Backing |

Do **NOT** fall through to regular Catalog Backing merely because the app restarted.

---

## 5. Backing current settings must persist on refresh / reboot

While still in the **same** Backing play session, preserve:

- Backing type
- source identity
- current Practice Key
- current BPM
- current style/groove
- meter
- loop/scope
- selected sections
- Mission/SBI/Jam identity
- relevant temporary playback settings

**Example:** Custom SBI · Trial Song · E · 112 BPM · Blues · Chorus loop → refresh → exact same type/source/key/settings — **not** Shape of You / Catalog / defaults.

---

## 6. Refresh / reboot is not a true leave

| Event | Meaning |
|-------|---------|
| **REFRESH / REBOOT** | Restore current page + current workflow state |
| **TRUE LEAVE** | User explicitly navigates away to a different workflow/page |

Only a **TRUE LEAVE** may start logic that resets temporary Backing overrides on a **later new** play-session entry.

Do **not** use browser refresh as evidence that the user left Backing.

---

## 7. True leave / return contract still applies

During the **same** Backing visit: BPM/style/meter/loop/etc. persist through rerun/refresh/reboot.

After the user **genuinely leaves** that Backing workflow and later starts a **new** Backing play session:

- temporary advanced overrides **may** reset to the source’s durable/default values
- source identity/context may still restore when valid per ownership rules

**Example:** Jam Backing temp BPM 118 / Blues → refresh keeps 118/Blues → leave to Songs → later return to Jam: same Jam source/context may restore; temporary BPM/style can reset to Jam defaults.

---

## 8. Exact Custom SBI Backing must persist (regression hotspot)

**Setup:** Global Active = Shape of You · LAST_CUSTOM = Trial Song · SBI source = Custom · Trial Practice Key = E → open SBI Backing.

**Expected Backing:** `kind = song_improv` · source = Trial Song · subtype = Custom · Practice Key = E · Trial progression.

**After refresh/reboot:** exact same Custom SBI Backing + settings.

**Must not become:** regular Shape of You Backing · SBI Active Source · My Progression · Catalog fallback.

---

## 9. Creative page restores where the user left off

If the last Creative subpage was Mission / SBI / Harmony Map / Motif / Live Coach / etc., refresh/reboot restores that subpage and its current selections.

**Example:** Creative → SBI → Custom → Trial Song → refresh → Creative opens SBI, Custom still selected, Trial Song resolved, key appropriate.

Do not reset to Entry/Jam or another first/default Creative tool unless stored state is genuinely invalid.

---

## 10. One persisted workflow snapshot

Architecturally, persist enough state to reconstruct the current workflow **coherently** (one snapshot, not independent stale widgets):

**PAGE / WORKFLOW** — top-level page · Creative subpage · Backing kind  

**SOURCE** — Global Active · LAST_CUSTOM · SBI selected type · Mission/Jam/Entry identity · Backing source identity  

**MUSICAL STATE** — Practice Key · section · chord · Mission/example · Motif selection  

**PLAYER PROJECTION** — instrument · sax subtype · Written Charts · Guitar Shape · Shape Key · Capo  

**BACKING PLAY SESSION** — BPM · style/groove · meter · loop/scope · sections · other temporary session settings  

On hydrate, restore this coherently **before** rendering widgets. Do not independently hydrate each widget from unrelated stale state.

---

## 11. Live regressions (required gates)

| ID | Gate |
|----|------|
| **P1** | Mission / Verse 1 / F#m → refresh/reboot → same Mission / Verse 1 / F#m |
| **P2** | Live Coach / Harmony chord/section selection → refresh → same selection |
| **P3** | Alto Sax + Written Charts ON → refresh/reboot → still Alto + Written ON |
| **P4** | Guitar Shape mode + Shape Key D + Capo → refresh/reboot → same state |
| **P5** | Practice Key editable on Songs, Custom, Mission, Harmony Map, SBI, regular/Mission/SBI/Jam/Entry Backing |
| **P6** | Custom SBI Backing / Trial Song / E / distinctive BPM/style/loop → refresh → exact same |
| **P7** | Mission Backing → refresh → same Mission Backing + selected Mission/chord |
| **P8** | Jam Backing + distinctive settings → refresh → same Jam Backing/settings |
| **P9** | Entry Style Backing + distinctive settings → refresh → same Entry Backing/settings |

---

## 11b. First-click chord selection (live interaction bug)

**Status: ACCEPTED & FROZEN** (2026-08-23). C1 Mission / C2 Live Coach / C3 Harmony Map / C_LEAK all PASS. Do **not** reopen unless a later regression proves it necessary. Uncommitted on `feature/creative-backing-stabilization`. Continue P7→P8→P9→P1→P2→P5.

### Symptom

On Missions, Live Coach, Harmony Map, and other chord-selection Creative pages:

1. User clicks a chord tile once.
2. UI may show internal text like `requires_pre_widget_activation:mission_jam:display_key` or `Active owner mismatch.`
3. Selected chord does **not** change on that first click.
4. Second click finally applies the new chord.

### Root cause (confirmed)

Shared path: chord tile → `apply_atomic_mission_chord_selection` → `mutate_mission_chord_selection` → `mutate_active_workflow` → `commit_staged_workflow` → `project_active_blob_to_legacy_session`.

1. **One-click lag:** when widgets already locked, `RequiresPreWidgetActivation` triggered **full blob/session rollback**. `mission_chord_selection` was **not** in the `canonical_keep` set, so the sealed click was undone until a second click.
2. **Marker leak:** `MutationResult.error_message` carried `requires_pre_widget_activation:...` into `st.warning`; mid-click `activate_workflow` / `OWNER_MISMATCH` also stamped `WORKFLOW_ACTIVATION_ERROR_KEY`, resurfaced via `activation_user_notice` → `st.warning("Active owner mismatch.")`.

### Fix (shared helpers)

| File | Change |
|------|--------|
| `music_workflow_mutation.py` | Keep canonical on `mission_chord_selection` / `apply_atomic_mission_chord*` when pre-widget; empty `error_message` on `PROJECTION_DEFERRED`; skip mid-click `activate_workflow`; treat non-`mission_jam` / `OWNER_MISMATCH` as `CHORD_OWNER_ACTIVATE_DEFERRED` after session seal; clear activation error key |
| `active_musical_workflow_envelope.py` | Never `st.warning` internal pre-widget / owner-mismatch tokens |
| `music_workflow_activation.py` | `activation_user_notice` filters the same internal tokens |

### Regression matrix

| ID | Gate | Result |
|----|------|--------|
| **C1** | Mission: click other chord once → new chord; no internal marker | PASS (live) |
| **C2** | Live Coach: click once → active immediately | PASS (session/disk first-click) |
| **C3** | Harmony Map: same-run selection | PASS (live) |
| **C_LEAK** | No `requires_pre_widget_activation` / `Active owner mismatch` in UI | PASS (live) |
| **C4–C6** | refresh / Practice Key / Written·Shape | still queued with P1–P9 |

Unit: `tests/test_first_click_chord_commit.py` (4 tests OK).

Evidence: `scripts/evidence-creative-backing/first-click-chord-*`.

---

## Implementation notes (for Pass 8)

1. Distinguish **session hydration after refresh** from **true leave** in Backing open-intent / restore paths (`BACKING_INTENT_RESTORE_LAST` must remain armed across refresh when specialized context is still valid).
2. Creative subpage + chord/section selectors must be durable keys in the music workspace blob (Item 5 channels), not ephemeral-only widget defaults.
3. Instrument / Written / Shape / Capo already have projection owners — ensure cold start re-applies them before first paint of theory/chart surfaces.
4. Practice Key writes must remain owned by the current workflow (Mission / SBI / Jam / Catalog / Custom) and must not be no-ops on specialized pages.
5. Custom SBI Backing identity must seal `song_improv` + Custom/LAST_CUSTOM title/key — never Global Catalog card on refresh.

**Do not commit** until Pass 8 matrix + P1–P9 live gates are green (per Pass 8 plan).
