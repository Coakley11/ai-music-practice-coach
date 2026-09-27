-- Monetization M2 trusted billing records.
-- Apply through the Supabase migration pipeline; never from Streamlit.

create table if not exists public.billing_customers (
  app_user_id uuid primary key references auth.users(id) on delete cascade,
  stripe_customer_id text not null unique,
  email text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.billing_subscriptions (
  stripe_subscription_id text primary key,
  app_user_id uuid not null references auth.users(id) on delete cascade,
  stripe_customer_id text not null references public.billing_customers(stripe_customer_id),
  stripe_product_id text,
  stripe_price_id text,
  provider_status text not null,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  trial_end timestamptz,
  latest_event_id text not null,
  latest_event_created bigint not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists billing_subscriptions_user_idx
  on public.billing_subscriptions(app_user_id);

create table if not exists public.billing_webhook_events (
  stripe_event_id text primary key,
  event_type text not null,
  event_created bigint not null,
  payload jsonb not null,
  processing_state text not null check (processing_state in ('processing', 'processed', 'failed')),
  attempt_count integer not null default 1,
  last_error text,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.billing_entitlements (
  app_user_id uuid primary key references auth.users(id) on delete cascade,
  plan text not null check (plan in ('free', 'pro')),
  status text not null,
  current_period_end timestamptz,
  source_subscription_id text,
  source_event_id text not null,
  source_event_created bigint not null,
  reason text not null,
  updated_at timestamptz not null default now()
);

alter table public.billing_customers enable row level security;
alter table public.billing_subscriptions enable row level security;
alter table public.billing_webhook_events enable row level security;
alter table public.billing_entitlements enable row level security;

revoke all on public.billing_customers from anon, authenticated;
revoke all on public.billing_subscriptions from anon, authenticated;
revoke all on public.billing_webhook_events from anon, authenticated;
revoke all on public.billing_entitlements from anon, authenticated;
grant select on public.billing_entitlements to authenticated;

drop policy if exists billing_entitlements_read_own on public.billing_entitlements;
create policy billing_entitlements_read_own
  on public.billing_entitlements
  for select
  to authenticated
  using (app_user_id = auth.uid());

create or replace function public.billing_claim_webhook_event(
  p_event_id text,
  p_event_type text,
  p_event_created bigint,
  p_payload jsonb
) returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  existing_state text;
begin
  insert into public.billing_webhook_events(
    stripe_event_id, event_type, event_created, payload, processing_state
  ) values (
    p_event_id, p_event_type, p_event_created, p_payload, 'processing'
  ) on conflict (stripe_event_id) do nothing;

  if found then
    return 'new';
  end if;

  select processing_state into existing_state
    from public.billing_webhook_events
    where stripe_event_id = p_event_id
    for update;

  if existing_state = 'processed' then
    return 'duplicate';
  end if;

  update public.billing_webhook_events
    set processing_state = 'processing',
        attempt_count = attempt_count + 1,
        last_error = null,
        updated_at = now()
    where stripe_event_id = p_event_id;
  return 'retry';
end;
$$;

create or replace function public.billing_apply_subscription(
  p_app_user_id uuid,
  p_customer_id text,
  p_subscription_id text,
  p_product_id text,
  p_price_id text,
  p_status text,
  p_current_period_end timestamptz,
  p_cancel_at_period_end boolean,
  p_trial_end timestamptz,
  p_event_id text,
  p_event_created bigint
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  changed text;
begin
  insert into public.billing_subscriptions as target (
    app_user_id, stripe_customer_id, stripe_subscription_id,
    stripe_product_id, stripe_price_id, provider_status,
    current_period_end, cancel_at_period_end, trial_end,
    latest_event_id, latest_event_created
  ) values (
    p_app_user_id, p_customer_id, p_subscription_id,
    p_product_id, p_price_id, p_status,
    p_current_period_end, p_cancel_at_period_end, p_trial_end,
    p_event_id, p_event_created
  ) on conflict (stripe_subscription_id) do update set
    app_user_id = excluded.app_user_id,
    stripe_customer_id = excluded.stripe_customer_id,
    stripe_product_id = excluded.stripe_product_id,
    stripe_price_id = excluded.stripe_price_id,
    provider_status = excluded.provider_status,
    current_period_end = excluded.current_period_end,
    cancel_at_period_end = excluded.cancel_at_period_end,
    trial_end = excluded.trial_end,
    latest_event_id = excluded.latest_event_id,
    latest_event_created = excluded.latest_event_created,
    updated_at = now()
  where (target.latest_event_created, target.latest_event_id)
      < (excluded.latest_event_created, excluded.latest_event_id)
  returning stripe_subscription_id into changed;
  return changed is not null;
end;
$$;

create or replace function public.billing_save_entitlement(
  p_app_user_id uuid,
  p_plan text,
  p_status text,
  p_current_period_end timestamptz,
  p_subscription_id text,
  p_event_id text,
  p_event_created bigint,
  p_reason text
) returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.billing_entitlements as target (
    app_user_id, plan, status, current_period_end, source_subscription_id,
    source_event_id, source_event_created, reason
  ) values (
    p_app_user_id, p_plan, p_status, p_current_period_end, p_subscription_id,
    p_event_id, p_event_created, p_reason
  ) on conflict (app_user_id) do update set
    plan = excluded.plan,
    status = excluded.status,
    current_period_end = excluded.current_period_end,
    source_subscription_id = excluded.source_subscription_id,
    source_event_id = excluded.source_event_id,
    source_event_created = excluded.source_event_created,
    reason = excluded.reason,
    updated_at = now()
  where (target.source_event_created, target.source_event_id)
      <= (excluded.source_event_created, excluded.source_event_id);
end;
$$;

revoke execute on function public.billing_claim_webhook_event(text, text, bigint, jsonb)
  from public, anon, authenticated;
revoke execute on function public.billing_apply_subscription(
  uuid, text, text, text, text, text, timestamptz, boolean, timestamptz, text, bigint
) from public, anon, authenticated;
revoke execute on function public.billing_save_entitlement(
  uuid, text, text, timestamptz, text, text, bigint, text
) from public, anon, authenticated;

grant execute on function public.billing_claim_webhook_event(text, text, bigint, jsonb)
  to service_role;
grant execute on function public.billing_apply_subscription(
  uuid, text, text, text, text, text, timestamptz, boolean, timestamptz, text, bigint
) to service_role;
grant execute on function public.billing_save_entitlement(
  uuid, text, text, timestamptz, text, text, bigint, text
) to service_role;
