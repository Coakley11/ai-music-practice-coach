# Making Home the default landing page — findings and plan

Investigation only. No behaviour has been changed on this branch yet.

Target behaviour:

- A new user arrives at Home.
- A returning user opening the app normally arrives at Home, with recent-practice
  information where available.
- An explicit restoration — saved workspace, song, or practice session — is respected.
- Deep links open their requested destination.
- Reaching Home never resets the active song, instrument, source identity or Practice Key.
- Home and Practice stay distinct.

## 1. The landing decision is 5 sites, not 105

A grep for `or "practice"` finds 105 non-test sites, which overstates the work by
about twenty to one. They divide into four kinds, and only the first decides where
a launch lands.

**(a) Landing decisions — these are the change.**

| Site | Role |
| --- | --- |
| `app_ui.ensure_studio_page(default="practice")` | the entry point the app script calls |
| `studio_nav_state.bootstrap_studio_page_session(default="practice")` | hydration-aware bootstrap it delegates to |
| `studio_nav_state` `_finish("empty_workspace_default", "practice", …)` | confirmed-empty workspace |
| `studio_nav_state.resolve_studio_page_for_restore` → `return "practice", "default"` | last resort after a restore with no saved page |
| `studio_nav_state._GENERIC_STARTUP_PAGES` | see §2 |

**(b) Read-guards — leave alone.** ~28 sites of the shape
`str(session.get("studio_page") or "practice")`. By the time these run the page is
already set, so the fallback is dead code in practice. Changing them buys nothing
and risks a lot.

**(c) Labelling fallbacks — need a deliberate answer, not a replace.**
`music_activity`, `music_active_context`, `music_ami_context`, `music_coach_*`,
`page_guidance`, `practice_log_state`. These answer "which workspace is the user
in?" for coaching context, analytics and the practice log. Home is not a practice
type: `practice_log_state._STUDIO_PAGE_TO_PRACTICE_TYPE` has no entry for it, so a
log entry quick-saved from Home currently has no sensible type. Each of these needs
its own answer.

**(d) Not product code.** `scripts/_proof_*`, `portfolio_demo.py` — ignore.

## 2. `_GENERIC_STARTUP_PAGES` is the real hinge

```python
_GENERIC_STARTUP_PAGES = frozenset({"", "picker", "practice"})
_PERSISTED_VISIT_PAGES = frozenset({"backing", "custom"})
```

This set means "the saved page is not a deliberate destination, so a more specific
signal may win". It is consulted in four places in `studio_nav_state`, including the
two rules that let a persisted Backing or Custom session beat a generic saved page.

If Home becomes the landing page and `"home"` is **not** added here, every cold start
looks like a deliberate choice of Home and will suppress those restores. **This is the
single most likely way the change breaks resumption**, and it is why the fallbacks must
not be swept with a global replace: `_GENERIC_STARTUP_PAGES` and the `or "practice"`
guards look similar and do opposite jobs.

## 3. The open problem: an ordinary launch and a refresh look identical

This is the one requirement the code cannot currently satisfy, and it needs a product
decision before implementation.

"A returning user opening the app normally should arrive at Home" and "a user
explicitly restoring a saved workspace must have that restoration respected" only
conflict because of how Streamlit starts. A refresh and a brand-new launch both
produce empty `session_state` plus the same persisted workspace. From Python they are
indistinguishable:

- the websocket session id is new in both cases;
- `studio_nav_state_last_local_edit_ts` is cleared on restore and is session-scoped,
  so it does not survive to be compared;
- the persisted nav blob carries `{studio_page, page, last_write_reason}` and **no
  timestamp**;
- there is no existing launch/refresh/cold-start signal anywhere in the Python
  (`sessionStorage` is used, but only inside `backing_key_cycle.py`'s embedded JS,
  which does not report back to Python).

Today a refresh deliberately keeps you where you were — that is what
`_PERSISTED_VISIT_PAGES` and the `persisted_session_backing` / `persisted_session_custom`
rules exist for. Any rule that sends an ordinary launch to Home will also send a
refresh to Home unless a new signal is introduced.

What *is* already unambiguous, and must keep winning in all options:

| Explicit signal | Handled by |
| --- | --- |
| Deep link (`suite_resume`, `suite_resume_kind`, `suite_resume_payload`) | `suite_resume_launch` |
| Pending upload route | `pending_upload_route_precedence` |
| Creative return handoff | `music_workflow_pending_creative_return` |
| History back/forward | `_studio_nav_from_history` |
| AMI return | `applied_math_return_insight` |
| In-session user navigation | `is_studio_nav_locally_dirty` |

### Options

**A — Home only where Practice is the default today.** Change the five sites in §1(a),
add `"home"` to `_GENERIC_STARTUP_PAGES`. New users and confirmed-empty workspaces get
Home; returning users still land on their saved page. Smallest change, lowest risk,
nothing about refresh changes. Does **not** deliver "returning user arrives at Home".

**B — Home for every launch, saved page only for explicit restoration.** Delivers the
stated intent, but treats the autosaved page as implicit memory rather than
restoration, so it also changes refresh unless a signal is added. Would need the
`persisted_session_backing` / `persisted_session_custom` rules revisited, and those are
load-bearing for Backing and Custom.

**C — B plus a refresh signal.** Persist a `last_seen_at` stamp in the workspace and
treat a gap under a few minutes as a refresh (keep the page) and anything longer as a
launch (go Home). No JS, no new round-trip. The cost is a heuristic: pausing for longer
than the window and then refreshing sends the user Home. A `sessionStorage` marker via a
small component would be exact but adds a component round-trip on every start.

**Recommendation: A first, as its own reviewable commit, then decide between B and C.**
A is independently useful, independently revertible, and it forces `_GENERIC_STARTUP_PAGES`
and the labelling fallbacks to be settled under low risk. B and C change behaviour every
returning user will notice on every launch, and the refresh trade-off should be chosen
deliberately rather than inherited from an implementation detail.

## 4. Test plan

Beyond flipping `TestStartupDefaultHasNotMoved`:

- cold start, empty workspace → Home;
- cold start, saved workspace → per the chosen option, and Backing/Custom persisted
  sessions still honoured;
- refresh mid-session on each of practice, backing, custom, creative, multitrack;
- deep link naming a page, and a resume payload — destination still wins;
- post-pricing return (`monetization_ui` return page);
- back/forward from a cold start on Home;
- active song, instrument, source identity and Practice Key unchanged across all of
  the above;
- a practice-log quick save started from Home gets a sensible `practice_type`.
