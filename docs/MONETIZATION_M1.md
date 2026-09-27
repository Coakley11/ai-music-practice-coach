# Monetization M1 — entitlement foundation

Status: local architecture checkpoint. No live checkout, Stripe SDK, webhook, or
production paid entitlement is connected in M1.

## Audit findings

### Accounts and identity

- `suite_auth.py` contains optional Supabase email/password authentication behind
  `SUITE_AUTH_ENABLED`. Auth is disabled by default; when disabled, the app uses
  suite workspace/profile identity rather than a verified end-user login.
- Authenticated sessions carry a Supabase user id and email. Workspace ownership
  is enforced separately by `suite_workspace_registry.py`.
- Workspace ids and display names are not sufficient proof of account identity.
  Monetization must key production billing records to the verified auth user id.

### Persistence and database

- Local state is JSON under `data/workspaces/{workspace_id}` and can be redirected
  with `MUSIC_APP_DATA_DIR` for isolated tests.
- Optional cross-device state uses Supabase through `suite_storage_supabase.py`,
  `suite_cloud_state.py`, and the suite account/storage shims.
- The music workspace has carefully separated global musical state, per-page
  snapshots, source ownership, and cloud restore. Entitlement state must not be
  written into the music workspace envelope or used as a source of musical truth.

### Runtime and configuration

- The application is a Python 3.12 Streamlit application. The repository includes
  Streamlit configuration and a Codespaces/dev-container launch path.
- Runtime packages include Streamlit, Supabase, OpenAI, and the audio stack. There
  is no Stripe dependency in M1.
- Secrets are loaded from Streamlit secrets and environment variables. The
  `.streamlit/secrets.toml` file and `.env` are gitignored; the committed secrets
  example contains placeholders only.

### Existing billing and access decisions

- No Stripe, checkout, subscription, billing, webhook, or prior entitlement code
  existed at the `e500e747` baseline.
- Most product workspaces were fully open. Existing conditional access was
  operational rather than commercial: the global auth gate, OpenAI-key
  availability, developer/admin diagnostics, and workflow-specific state guards.
- Those checks should remain independent. A paid plan must never be inferred from
  an OpenAI key, developer mode, a workspace id, or a client/session flag.

## M1 architecture

`monetization_entitlements.py` is the product policy boundary:

1. `Feature` is the centralized feature-key vocabulary.
2. `FEATURE_CATALOG` owns display names, summaries, and required plans.
3. `Entitlement` represents product state without Stripe objects.
4. `EntitlementProvider` is the trusted boundary for the future server/database
   implementation.
5. Pages call `can_use(feature)` or `access_decision(feature)` and do not inspect
   Stripe status, price ids, or session flags.

The model supports:

- anonymous free
- authenticated free
- trialing Pro
- active Pro
- canceled but entitled through period end
- past due (not entitled in the initial policy)
- expired
- explicit local/test development access

Unknown feature keys fail closed. `past_due` and `expired` do not grant Pro.
`canceled_period_end` continues to grant Pro until the trusted provider changes
the stored status at period end.

`monetization_ui.py` owns shared presentation:

- membership status and plan entry point
- pricing/upgrade surface
- locked-feature treatment
- local/test entitlement selector
- non-destructive open/close behavior that leaves `studio_page`, song identity,
  key state, backing owner/envelopes, and navigation stacks untouched

The M1 pricing surface explicitly states that checkout is not connected and uses
a disabled checkout placeholder. It cannot claim or simulate a completed payment.

### Development controls

The Free/Pro selector appears only when both server-owned settings are present:

```text
MUSIC_ENTITLEMENT_DEV_CONTROLS=1
MUSIC_ENTITLEMENT_RUNTIME=local   # or test
```

`MUSIC_ENTITLEMENT_DEV_PLAN=free|pro` can set the initial preview plan. The
session selection is ignored unless the server gate and local/test runtime are
both active. Production deployments must leave these unset. This mechanism is
for UI/test simulation only and is not an authoritative paid-access source.

## Proposed Free / Pro model

This is a reviewable starting point, not final pricing strategy.

### Free foundation

- Practice basics, charts, metronome, tuner, and tone tools
- Song catalog/library and active-song workflow
- Backing Studio core generation
- Custom Progression Lab
- Creative Entry & Jam
- Missions and Phrase / Motif
- Instrument transposition, written-key tools, and capo support
- Core Practice Log

This keeps the complete practice loop useful and avoids turning the existing app
into a collection of locks.

### Pro candidates

- Composition Studio
- Advanced/repeated upload analysis and retained analysis history
- Multitrack projects and export
- Higher-cost personalized AI coaching
- Longitudinal/advanced analytics
- Advanced karaoke and larger setlists
- Future premium content packs or generous usage limits

Only **Composition Studio** is actively gated in M1. The remaining Pro candidates
are cataloged centrally for product review but are not yet gated. Usage limits
should be designed around real cost and engagement data, not guessed in code.

## Why Composition is the M1 proof gate

Composition is a coherent advanced creation workspace and a natural Pro candidate.
It also has a single page boundary, which proves centralized access control without
placing checks inside musical mutation functions. A Free user sees the shared
locked state; a Pro/test-entitled user reaches the unchanged Composition renderer.
Encountering the gate does not activate a different song, change Practice Key,
claim a backing owner, clear page history, or rewrite persistence.

## M2 Stripe boundary (proposal; not implemented)

### Integration points

1. Require verified Supabase auth before starting checkout.
2. A trusted server/edge endpoint creates Stripe Checkout Sessions. The browser
   sends a requested product/price key, never an amount or entitlement grant.
3. Webhooks verify Stripe signatures and project subscription state into Supabase.
4. A Supabase-backed `EntitlementProvider` reads the server-owned projection.
5. A billing portal endpoint lets authenticated customers manage payment methods
   and cancellation.
6. The Streamlit app only reads normalized entitlements and opens trusted checkout
   or portal URLs returned by the server.

### Required secrets/config

- `STRIPE_SECRET_KEY` — trusted server only
- `STRIPE_WEBHOOK_SECRET` — trusted webhook handler only
- `STRIPE_PRO_PRICE_ID` — server configuration
- `STRIPE_PUBLISHABLE_KEY` — only if a future client integration needs it
- checkout success/cancel base URLs
- existing Supabase URL plus server/service-role credentials for webhook writes

No secret key belongs in Streamlit client state, query params, logs, or source.

### Proposed data model

- `billing_customers`: `user_id` (unique FK to the verified suite user),
  `stripe_customer_id` (unique), timestamps.
- `billing_subscriptions`: `user_id`, `stripe_subscription_id` (unique), status,
  price/product ids, `current_period_end`, `cancel_at_period_end`, timestamps.
- `billing_events`: Stripe event id (primary key), type, payload hash, received and
  processed timestamps, processing result/error. This is the idempotency ledger.
- Optional `user_entitlements` projection: user id, plan, normalized status,
  entitlement end, source subscription, and monotonic update/version fields.

Do not store full Stripe payloads in the music workspace state. Retain only the
billing data needed for reconciliation and auditing, with an explicit retention
policy.

### Webhook events

The initial subscription implementation should handle at least:

- checkout session completion
- subscription creation/update/deletion
- successful invoice payment
- failed invoice payment
- trial-ending notification if trials are enabled

The webhook is authoritative. The success redirect may show a pending state while
the verified webhook projection catches up; it must not grant access by itself.

### Idempotency and ordering

- Insert each Stripe event id once before applying it; duplicate delivery becomes
  a no-op.
- Store Stripe object/event timestamps or a monotonic version and reject older
  events that would overwrite newer subscription state.
- Use Stripe idempotency keys when creating Checkout Sessions, derived from a
  short-lived server-side attempt id rather than a reusable browser value.
- Reconcile periodically from Stripe to repair missed or delayed webhook delivery.

### Cancellation and payment failure

- `cancel_at_period_end=true`: keep Pro through `current_period_end`, surface the
  scheduled end date, and allow reactivation.
- Immediate cancellation/refund: policy decision required; the provider can map it
  to expired immediately or to a support-controlled grace state.
- `past_due`: M1 policy fails closed for Pro. Before launch, decide whether to add
  a short grace period. The UI should offer billing repair, not a new checkout.
- `unpaid`/expired/deleted: Free access remains and paid-only work is retained, not
  deleted. The user can regain access after successful payment.

### Local/test strategy

- Unit-test provider projections with deterministic subscription fixtures.
- Use Stripe test mode and Stripe CLI webhook forwarding in M2.
- Exercise duplicate and out-of-order webhook delivery.
- Use separate Stripe test price ids and a separate Supabase project/schema where
  practical.
- Keep the M1 local/test entitlement simulator for UI tests; never use it to test
  webhook correctness.

## Decisions requiring product approval before M2

1. Confirm Composition as the first paid feature and decide which other candidates
   become actual gates.
2. Decide monthly/annual pricing, currency, tax handling, and whether regional
   pricing is needed.
3. Decide whether to launch trials, their duration, and whether payment details are
   required up front.
4. Decide the `past_due` grace policy and immediate-cancellation/refund behavior.
5. Decide which usage limits (AI calls, analyses, exports, setlist size) are useful
   and understandable to musicians.
6. Decide whether production paid launch waits for Supabase Real Accounts to be
   enabled for every user.
7. Approve customer-support, refund, privacy, data-retention, terms, and tax flows
   before accepting money.

