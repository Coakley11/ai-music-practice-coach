# Home

Home is the app's welcome screen: a signpost that points at every workspace and,
when there is one on record, offers to pick up the last practice session.

It is a real studio page (`studio_page == "home"`), and it participates in
back/forward history like any other destination. It leads every navigation — the
top nav, the quick-nav art row and the simple-nav fallback — with Practice
immediately after it.

**Practice is still the startup default.** Home is somewhere you can go, not
somewhere you are put. Making it the landing page is a separate change; what that
would take is set out at the end of this document.

## What Home is allowed to touch

Arriving on Home, and clicking through it, changes the *view* and nothing else.
`home_destinations.PROTECTED_STATE_KEYS` lists the state Home must never write —
song identity, instrument, the Practice/concert key, the written and shape keys,
capo, backing ownership and the chart sections — and
`tests/test_home_destinations.py` asserts that no card touches any of them.

Navigation goes through the established contracts and only those:

| What | Through |
| --- | --- |
| The page | `app_ui.navigate_studio_page` |
| The Creative Lab workspace | `studio_nav_history.apply_creative_history_destination` |
| A Browse genre pill | `songs.picker_session.WORKSPACE_GENRE_FILTERS_KEY` |

The genre pill is the one piece of state Home writes beyond the page itself. It
is a page-local view filter, the same one the pills on the Songs page write, and
it selects no song and activates nothing.

Home is also exempt from the catalog chart bundle
(`songs.chart_bundle_startup.CHART_BUNDLE_EXEMPT_STUDIO_PAGES`) and has no entry
in the `_studio_page_for_hydrate` chain, so landing on it hydrates no song source.

## Where the cards go

| Card | Page | Extra |
| --- | --- | --- |
| Start practicing / Practice & improve | `practice` | |
| Find a song / Browse entire catalog | `picker` | |
| Explore Pop, Explore Jazz | `picker` | ticks that genre pill |
| Play with backing tracks, Key Cycling | `backing` | |
| Record & multitrack | `multitrack` | |
| Create & compose | `composer` | |
| Missions & exercises | `creative` | `creative::Missions` |
| Song-Aware Coaching | `creative` | `creative::SBI` |
| Custom Progressions | `custom` | |
| Upload Analysis | `analysis` | |
| Practice Log | `log` | |

Missions and Song-Aware Coaching are deliberately **not** the same destination.
Both live under `studio_page == "creative"`, but they select different
workspaces, and `history_destination_id` reports them separately, so back/forward
distinguishes them.

## Recent practice

The card is built by `home_recent_session.verified_recent_session`, which reads
**saved Practice Log entries only**. A song loaded in the workspace is not
evidence that a previous session happened, so it is never used to build the card.
With no saved entry, Home shows the empty state and says why.

Keys come from `practice_log_state.entry_key_display_parts`, which labels them as
the Practice Log itself does: *Practice/Concert key*, *Written key* for a
transposing instrument, *Shape key* for guitar, and *Original key*. The concert
key is never presented as the written key.

**This slice reports; it does not resume.** The heading is "Recent practice", not
"Continue practicing", and the button names its destination — *Go to Practice*,
*Go to Backing*, *Go to Missions* — because that is all it does. It opens the
workspace that session was recorded in (`practice_type` → page) and restores no
musical state; the caption says the song is not reloaded. Nothing on the card
should read as a promise to put the workspace back the way it was.

Genuine resume is a later slice. It should go through
`music_resume_payload.apply_music_resume_payload` rather than anything new, and
it needs its own acceptance pass, because it necessarily writes the protected
state above. Only then should the wording change.

## Branding and assets

Home uses the canonical repository logo. `static/branding/mpc_logo_emblem_256.png`
and `..._96.png` are Lanczos downscales of `static/branding/mpc_logo_emblem.png`,
generated from it, not redrawn — same artwork, 80 KB and 17 KB instead of 1.3 MB.
Home embeds the 256px variant as a data URI, for the same reason the main brand
header embeds the full one: Streamlit Community Cloud does not reliably serve
`/app/static/`.

Colours are the app's own: purple `#312e81`, indigo `#4338ca`, yellow `#facc15`,
blue `#93c5fd`, ink `#0f172a`. On top of that, each card wears the canonical
accent of the page it opens, from `app_ui.STUDIO_PAGE_ACCENTS`, so the colour a
musician taps is the colour that greets them on arrival.

Every tap target is at least 44x44 CSS pixels. Below 640px the card grids
collapse to a single column.

> The React/TypeScript prototype this page was built from is kept as-is. Home's
> card copy, section order and visual structure deliberately mirror it, so the
> two can be compared when the frontend is modernized.

## Making Home the startup default

Not a one-line change. The work divides into four parts.

### 1. The bootstrap default

`app_ui.ensure_studio_page(session_state, default="practice")` delegates to
`studio_nav_state.bootstrap_studio_page_session`, which is hydration-aware: it
must not pin a landing page while a cloud workspace restore is still pending.
Changing the default means changing it in both, and in the restore resolver's own
terminal defaults (`studio_nav_state` lines around `empty_workspace_default` and
the final `return "practice", "default"`).

### 2. `_GENERIC_STARTUP_PAGES`

```python
_GENERIC_STARTUP_PAGES = frozenset({"", "picker", "practice"})
```

This is the set of pages the restore logic treats as *not a deliberate
destination*, so that a more specific saved target can win. If Home becomes the
landing page, `"home"` must join this set. Without that, every cold start would
look like a deliberate choice of Home and could block a legitimate workspace
restore — the most likely way this change would break resumption.

### 3. The remaining `"practice"` fallbacks

There are ~131 `or "practice"` / `default="practice"` sites across ~20 modules.
They are not interchangeable and must be triaged into two groups:

- **Routing defaults** — "where do we send someone with no page?" These become
  Home: `app_ui.ensure_studio_page`, `studio_nav_state`, `studio_nav_history`,
  `studio_page_persistence`, `suite_deep_links`, `suite_resume_launch`,
  `monetization_ui` (the post-pricing return page).
- **Labelling fallbacks** — "which page is the user on, for coaching context,
  logging and analytics?" These are in `music_activity`, `music_active_context`,
  `music_ami_context`, `music_coach_*`, `page_guidance` and
  `practice_log_state._STUDIO_PAGE_TO_PRACTICE_TYPE`. Home is not a practice
  type, so each needs a deliberate answer rather than a global replace. A
  practice-log entry quick-saved from Home, for instance, currently has no
  sensible `practice_type`.

### 4. Tests

`tests/test_home_page_registration.py::TestStartupDefaultHasNotMoved` pins the
current behaviour on purpose; it is the test to flip. Beyond it, the acceptance
pass should cover: cold start with an empty workspace; cold start with a saved
cloud workspace (the saved page must still win); refresh mid-session; a deep link
that names a page; the post-pricing return; and back/forward from a cold start on
Home.

## Fit with the React modernization

`home_page.py` renders Home but does not own it. The parts that would need to
survive a move to React are already separate and framework-free:

- `home_destinations.py` — the card list, where each one goes, and the one
  function allowed to act on a click. This is the navigation contract the
  prototype's `src/navigation.ts` describes, expressed in Python and backed by
  tests. A React Home would call the same contract through an endpoint rather
  than reimplementing it.
- `home_recent_session.py` — the verified-session projection. The prototype's
  `VerifiedRecentSession` type maps onto it field for field, including the
  insistence that it come from trusted server-side history rather than local
  storage.

Only `home_page.py` is Streamlit-specific, and it is the thinnest of the three.
That is the intended shape for the rest of the migration: push the contract and
the projection down into framework-free Python, keep the renderer replaceable.
