# Music Practice Coach — Mobile / Responsive UX Audit

**Date:** 2026-09-27  
**Branch:** `feature/mobile-responsive-ux`  
**Worktree:** `.worktrees/mobile-responsive-ux`  
**Audit commit:** `c7931097` (preserved)  
**Authoritative baseline after integrate:** `origin/dev` @ `b3cc2e70` (merge `9d01a0ea`)  
**Original audit baseline:** `origin/dev` @ `e500e747` (Slice 5)  
**Current product baseline:** `origin/dev` @ `b3cc2e70` (merged into this branch)  
**Scope:** Audit accepted; M1 implementation in progress — separate from monetization  
**Evidence:** `scripts/evidence-mobile-audit/` · runner `scripts/_audit_mobile_responsive_ux.py`

---

## Executive summary

On phone widths (~360–430px), the studio feels like a **desktop shell stacked into a column**, not a phone-first product.

Highest-impact finding:

| Surface | Phone nav panel height | Desktop nav panel height |
|---------|------------------------|--------------------------|
| Quick nav (`studio_quick_nav_panel`) | **~828px** | **~204px** |

At 360×740 the quick-nav alone exceeds the viewport. Primary page content is pushed far below the fold. Floating Back/Forward overlays sit on top of nav Open buttons.

**Recommended first implementation slice: Mobile M1 — Global navigation.**

Functional freeze remains: no ownership / PK / Backing / history / generation changes for layout reasons.

---

## 1. Responsive architecture map

### Style delivery

- **No standalone CSS files** — styles are Python-injected `<style>` strings.
- Dominant owner: `app_ui.inject_app_theme` + `_inject_app_theme_polish` / `_studio_panels_css`.
- Page re-injectors: backing / picker / practice / creative / custom / upload / multitrack.
- Also: `portfolio_polish.py`, `composition_studio_page.inject_composition_studio_styles`, `practice_tools_ui`, chart/lyric modules, analysis UIs.

### Breakpoints (ad hoc — no shared token module)

| px | Typical use |
|----|-------------|
| 420 | Floating Back/Forward → icon-only |
| 640 | Tutorial grids; practice tool chips; Creative radio density |
| 720 | Active song / song cards → 1 col; backing setup collapse |
| 760 | Page padding; chart `lead-grid` 4→2; follow grids |
| 768 | Notation denser; portfolio column `min-width:0` |
| 900 | Brand denser; multitrack/RA/MA grids → 1 col |
| 1100 | `.block-container` side padding |

**No `is_mobile` / shared breakpoint helper.** Phone behavior is CSS-only via `@media`.

### Navigation architecture

| Surface | Owner | Phone behavior today |
|---------|-------|----------------------|
| Main quick nav | `app_ui.render_page_quick_nav` — 2× `st.columns` rows (4 + 5 pages) | Columns wrap → **vertical stack of icon + Open** (~9 destinations) |
| Sidebar Pages | `render_sidebar_studio_nav` | Default **collapsed** (`☰ Pages`) — good |
| Floating history | `studio_nav_history.render_floating_nav_history` | Mid-viewport pills; overlaps Open buttons on phone |
| Cross-page links | Practice/Backing quicklinks | Extra height on already-tall pages |

Page IDs: `practice`, `picker`, `backing`, `custom`, `composer`, `creative`, `analysis`, `multitrack`, `log`  
Authority: `studio_nav_history.navigate_studio_page` (must not change semantics).

### Desktop-only assumptions (examples)

- Composition `.st-key-composer_desktop_split` forces `flex-wrap: nowrap` + ~340px utility column — **no `@media`**.
- Wide Streamlit ratios: `[2.6,1]`, `[2.3,1]`, karaoke `[6.5,1.5,1,1,1]`.
- Quick nav cells use decorative Caveat script + separate Open button (tall on wrap).

---

## 2. Shared root causes of poor phone UX

1. **Quick nav density model** — designed as a 2-row desktop strip; on wrap each destination becomes a full-width art face + Open (~80–100px × 9).
2. **Hero / restore / Tutorial chrome** above nav still compete for first viewport.
3. **Floating Back/Forward** fixed mid-screen over primary controls.
4. **Decks + expanders** (Backing Advanced, Practice tools, Creative modes) stack without a mobile “primary vs secondary” contract.
5. **`st.columns(N) + i % N`** for section/chord strips → column-major visual order when Streamlit stacks columns.
6. **Breakpoint sprawl** without shared primitives → inconsistent collapse behavior.
7. **Composition desktop split** does not reflow to stacked main→utility on phone.

---

## 3. High-impact mobile problem inventory

| ID | Problem | Impact | Evidence |
|----|---------|--------|----------|
| P-NAV-1 | Quick nav ~828px tall on phone | Critical | `phone360_*.png`, metrics `navH=828` |
| P-NAV-2 | Floating Back/Forward occludes Open | High | phone screenshots |
| P-NAV-3 | 9× Open buttons; inactive Open contrast weak | High | phone360_practice |
| P-HEIGHT-1 | Hero + restore banner + Tutorial before content | High | phone390_backing |
| P-HEIGHT-2 | Backing Advanced / transport / charts stack | High | code + scrolled shots |
| P-HEIGHT-3 | Practice Control Center + toolkits + expanders | High | architecture |
| P-HEIGHT-4 | Creative Analysis mode + radios + maps | High | architecture |
| P-ORDER-1 | Composition section strips `i % n` | High | code audit |
| P-ORDER-2 | Harmony Map chord buttons `i % n` | High | code audit |
| P-ORDER-3 | Charts trust `sections.items()` without re-apply `section_order` | Med | functional risk if callers unordered |
| P-CTRL-1 | Karaoke setlist 5-col action rows crush | Med | `karaoke_ui` |
| P-COMP-1 | Composition nowrap desktop split | High | CSS in composition injector |

Browser metrics snapshot (audit run):

| viewport | navH (typical) | desktop navH |
|----------|----------------|--------------|
| phone360/390/430 | **828** | — |
| desktop | — | **204** |

`openButtonCount` ≈ 9 on every page — confirms full destination strip always mounted.

---

## 4. Semantic / musical ordering risks

| Risk | Mechanism | Rating | Notes |
|------|-----------|--------|-------|
| Composition Structure / section jump strips | `st.columns(min(n,8))` + `cols[i % n]` | **High** | Column-major when columns stack; data from `ordered_sections` is correct |
| Harmony Map chord tiles | same modulo pattern | **High** | Fix layout, not data |
| Mission chord map | row chunks of 8 (safer) | Low–Med | Prefer this pattern |
| Chart `lead-grid` | CSS grid DOM order | Low | Safe if cells emitted in bar order |
| Karaoke queue | `enumerate(queue)` rows | Low | Order OK; controls crush |
| Practice section jump radio | wrap preserves option order | Med (readability) | |
| CPL UI section order | Verse-first UI vs Intro-first arrangement | **Functional** | Separate from CSS wrap |

**Principle:** Do not “fix” data order with CSS. Prefer stacked / one-row-per-chunk / horizontal scroll strips that iterate the data list in order.

---

## 5. Shared responsive-component opportunities

| Primitive | Purpose | Likely homes |
|-----------|---------|--------------|
| **`ResponsiveNavShell`** | Phone: compact grid / chip strip / drawer; desktop: current 2-row art | `render_page_quick_nav` |
| **`SectionChipStrip`** | Ordered section chips without `i % n` | Composition strips, section jumpers |
| **`ChordTileGrid`** | Row-chunk tiles (Mission pattern) | Harmony Map, Creative maps |
| **`StudioDeck` density contract** | Primary controls vs Advanced accordion | Backing / Practice / Creative |
| **`ActionRow`** | Overflow for karaoke/hub actions | `karaoke_ui`, songs hub |
| **`PageSplit`** | Desktop split / mobile stack | Composition |
| **`BadgeRow`** | Cap chip lines | status badges |
| **Breakpoint tokens** | Shared 420/640/760/900 | `app_ui` + injectors |

Avoid a speculative full layout framework rewrite — introduce primitives as M1–M3 land.

---

## 6. Special-case pages

| Page | Why custom treatment |
|------|----------------------|
| **Composition** | nowrap split; many section strips; little `@media` |
| **Backing** | Tall deck + Advanced + charts + transport |
| **Creative / Missions / Motif** | Mode select + dense maps + ownership UI |
| **Practice** | Toolkit + many expanders + notation |
| **Karaoke / setlists** | 5-col rows; performance overlays |
| **Multitrack / Upload** | Long dashboards when grids collapse to 1-col |
| **Live follow / overlays** | Full-viewport; thumb reach / safe-area |

---

## 7. Representative browser evidence

**Runner:** `python scripts/_audit_mobile_responsive_ux.py http://127.0.0.1:8580`  
**Viewports:** 360×740, 390×844, 430×932, 1280×900  
**Pages:** Practice, Songs, Backing, Creative, Compose (Catalog seed: Perfect)

**Artifacts:** `scripts/evidence-mobile-audit/`

- `phone360_practice.png` — nav stack dominates; Back/Forward overlay Open
- `phone390_backing.png` — hero + Tutorial + stacked Open
- `phone430_compose.png` — Compose active Open visible; content still below
- `desktop_practice.png` / compose — 2-row quick nav (~204px) healthy
- `audit_summary.json` — metrics

**Above-the-fold on phone today (typical):** Streamlit chrome → hero/restore → Tutorial → **nav Open stack** (primary content rarely visible).

---

## 8. Proposed implementation slices

### Mobile M1 — Global navigation *(accepted audit → implementation)*

- **Scope:** Compact phone presentation for top-level destinations; reduce quick-nav height by ~60–80%; keep desktop 2-row art.
- **Shared:** `responsive_layout.py` (`PHONE_MAX_WIDTH_PX=720`) + phone CSS for `studio_quick_nav_panel`; floating history bottom-dock / mid-side fallback.
- **Pages:** All (global chrome).
- **UX:** Primary page content reachable without scrolling past 9 Open buttons.
- **Frozen:** `navigate_studio_page`, history push/noop, page ownership, sidebar collapse defaults (unless nav UX requires only presentation changes).
- **Tests:** `tests/test_mobile_m1_global_nav.py`; browser `scripts/_proof_mobile_m1_nav.py`.
- **Browser:** 360/390/430 — Practice/Songs/Backing/Creative/Compose open; desktop regression screenshots.
- **Status:** Implemented on branch after `b3cc2e70` integrate; awaiting Daniel acceptance before M2.

### Mobile M2 — Shared density primitives *(implemented — awaiting acceptance)*

- Badge rows, action rows, deck chrome, page heads, spacing tokens via `responsive_layout` + `_mobile_density_chrome_css`.
- Songs hub actions wrap 2-col on phone (`*_nav_actions` keyed container).
- Pages benefit: Practice / Songs / Backing / Creative / Composition shared chrome (not full page redesigns).
- Desktop spacing unchanged (phone media only).
- Evidence: `scripts/evidence-mobile-m2/` · hub actions ~264→123px at 390.

### Mobile M3 — Ordered musical content

- Replace `i % n` section/chord strips with ordered chip/grid helpers.
- Composition Structure + Harmony Map + section jumpers.
- Explicit order tests (data sequence == DOM/read order).

### Mobile M4 — Practice + Backing

- Primary controls above fold; Advanced collapsed by default on phone; charts readable; transpose helpers density.
- Frozen: PK / written / instrument / backing envelopes.

### Mobile M5 — Creative

- Entry/Jam, SBI, Missions, Phrase/Motif, Live Coach density + maps.
- Frozen: Creative ownership / source authority.

### Mobile M6 — Composition / Custom / Upload / Karaoke

- PageSplit for Composition; CPL section picker clarity; karaoke action overflow; upload dashboards.

### Mobile M7 — App-wide regression / polish

- Full phone matrix + desktop smoke; before/after gallery; backlog cleanup.

---

## 9. Test / browser acceptance matrix (per slice)

| Check | How |
|-------|-----|
| Semantic / musical order | Unit: list order == rendered order; Composition strip DOM |
| Nav understandable | Browser: destinations reachable ≤1 tap from compact shell |
| Primary content sooner | Metric: `navH` phone ≪ viewport; first content Y in first screen |
| Scroll reduction | Before/after `scrollH` / screenshots |
| No whole-page h-overflow | Playwright `scrollWidth ≤ clientWidth + ε` |
| No clipping / overlap | Screenshots; floating nav not over primary CTAs |
| Touch-friendly | Targets ≥ ~44px |
| No responsive state mutation | Session ownership keys unchanged across resize/rerun |
| Back/Forward / refresh | Existing history + persistence smokes |
| Desktop correct | 1280 screenshots + quick nav 2-row |

Priority: semantic correctness → navigation efficiency → readability → touch → scroll reduction.

---

## 10. Recommended first slice

**Mobile M1 — Global navigation**

Why:

1. Largest measured height win (`navH` 828 → target ~160–280 on phone).
2. Unblocks every page’s above-the-fold content.
3. Contained in `app_ui` quick-nav + floating history CSS/presentation.
4. Low collision with frozen ownership/Backing logic if navigation continues to call `navigate_studio_page` only.
5. Clear before/after evidence path already established.

**Out of scope for M1:** Composition split, chord grids, Backing Advanced, Creative tool internals (M2+).

---

## Functional issues (separate from layout)

| Issue | Type | Action |
|-------|------|--------|
| CPL `CPL_UI_SECTION_ORDER` Verse-first vs Intro-first arrangement | Functional / data | Track separately; do not “fix” with CSS |
| Charts iterating `sections.items()` without ensuring `section_order` | Functional risk | Verify callers; fix data path if unordered |
| Hebrew lyrics fallback `sorted(...)` when order missing | Functional | Separate bug if still live |
| Quick-nav inactive Open low contrast | UX / a11y | Address in M1 presentation |

No ownership/Back-Forward regression identified in this audit.

---

## Files added for this audit

| File | Role |
|------|------|
| `scripts/_audit_mobile_responsive_ux.py` | Phone/desktop Playwright capture |
| `scripts/evidence-mobile-audit/*` | Screenshots + `audit_summary.json` |
| `cursor-prompts/plans/2026-09-27-mobile-responsive-ux-audit.md` | This document |

No product/runtime logic changed.

---

## Notes

- Do not push / merge until Daniel reviews audit and approves M1.
- Do not build on Slice 5 feature branch or monetization branch — baseline stays `e500e747` lineage on `dev`.
- Streamlit Cloud phone testing should use the same viewports after M1 lands.
