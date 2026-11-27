-- Phase 2, test environment only. Requires M2 and Phase 1 ownership migration.
-- No migration was applied by the assignment.
alter table public.billing_customers
  add column if not exists reconciliation_token uuid,
  add column if not exists reconciliation_expires timestamptz;
alter table public.billing_webhook_events
  add column if not exists fingerprint text,
  add column if not exists lease_token uuid;
alter table public.billing_subscriptions
  add column if not exists projected_plan text,
  add column if not exists projected_status text,
  add column if not exists projected_reason text;

-- Preserve previously derived source subscriptions until provider reconciliation.
update public.billing_subscriptions s set
  projected_plan = e.plan, projected_status = e.status, projected_reason = e.reason
from public.billing_entitlements e
where e.source_subscription_id = s.stripe_subscription_id
  and e.app_user_id = s.app_user_id and s.projected_plan is null;

create or replace function public.music_billing_claim_delivery(
  p_event_id text, p_event_type text, p_created bigint,
  p_fingerprint text, p_customer_id text, p_payload jsonb
) returns text language plpgsql security definer set search_path = public as $$
declare
  customer public.billing_customers%rowtype;
  event public.billing_webhook_events%rowtype;
  token uuid := gen_random_uuid();
begin
  perform pg_advisory_xact_lock(hashtextextended(p_event_id, 0));
  select * into customer from public.billing_customers
    where stripe_customer_id = p_customer_id for update;
  if not found then raise exception 'Unmapped customer'; end if;
  -- All functions lock customer before event, serializing provider reads per user.
  select * into event from public.billing_webhook_events
    where stripe_event_id = p_event_id for update;
  if found then
    if event.fingerprint is null then
      -- Legacy M2 ledger: validate the complete original payload before adoption.
      if (event.payload - 'pending_webhooks') is distinct from (p_payload - 'pending_webhooks') then
        return 'collision';
      end if;
      update public.billing_webhook_events set fingerprint = p_fingerprint
        where stripe_event_id = p_event_id;
    elsif event.fingerprint <> p_fingerprint then return 'collision'; end if;
    if event.processing_state = 'processed' then return ''; end if;
  end if;
  if customer.reconciliation_token is not null
      and customer.reconciliation_expires > clock_timestamp() then return 'busy'; end if;
  insert into public.billing_webhook_events as target (
    stripe_event_id, event_type, event_created, payload, processing_state,
    fingerprint, lease_token
  ) values (p_event_id, p_event_type, p_created, '{}'::jsonb, 'processing', p_fingerprint, token)
  on conflict (stripe_event_id) do update set
    processing_state = 'processing', lease_token = token,
    attempt_count = target.attempt_count + 1, last_error = null, updated_at = now();
  update public.billing_customers set reconciliation_token = token,
    reconciliation_expires = clock_timestamp() + interval '5 minutes'
    where stripe_customer_id = p_customer_id;
  return token::text;
end;
$$;

create or replace function public.music_billing_complete_delivery(
  p_event_id text, p_token uuid, p_record jsonb, p_entitlement jsonb
) returns void language plpgsql security definer set search_path = public as $$
declare
  customer public.billing_customers%rowtype;
  event public.billing_webhook_events%rowtype;
  r public.billing_subscriptions%rowtype;
  chosen public.billing_subscriptions%rowtype;
  chosen_plan text;
  chosen_status text;
  chosen_reason text;
begin
  r := jsonb_populate_record(null::public.billing_subscriptions, p_record);
  select * into customer from public.billing_customers
    where stripe_customer_id = r.stripe_customer_id for update;
  if not found or p_token is null or customer.app_user_id is distinct from r.app_user_id
      or customer.reconciliation_token is distinct from p_token
      or customer.reconciliation_expires is null
      or customer.reconciliation_expires <= clock_timestamp() then
    raise exception 'Customer lease ownership lost';
  end if;
  select * into event from public.billing_webhook_events
    where stripe_event_id = p_event_id for update;
  if not found or event.processing_state <> 'processing'
      or event.lease_token is distinct from p_token
      or r.latest_event_id is distinct from p_event_id
      or r.latest_event_created is distinct from event.event_created then raise exception 'Event lease ownership lost'; end if;
  if exists (select 1 from public.billing_subscriptions
      where stripe_subscription_id = r.stripe_subscription_id
      and (app_user_id <> r.app_user_id or stripe_customer_id <> r.stripe_customer_id)) then
    raise exception 'Subscription ownership conflict';
  end if;
  insert into public.billing_subscriptions (
    stripe_subscription_id, app_user_id, stripe_customer_id, stripe_product_id,
    stripe_price_id, provider_status, current_period_end, cancel_at_period_end,
    trial_end, latest_event_id, latest_event_created,
    projected_plan, projected_status, projected_reason
  ) values (
    r.stripe_subscription_id, r.app_user_id, r.stripe_customer_id, r.stripe_product_id,
    r.stripe_price_id, r.provider_status, r.current_period_end, r.cancel_at_period_end,
    r.trial_end, r.latest_event_id, r.latest_event_created,
    p_entitlement->>'plan', p_entitlement->>'status', p_entitlement->>'reason'
  ) on conflict (stripe_subscription_id) do update set
    stripe_product_id = excluded.stripe_product_id, stripe_price_id = excluded.stripe_price_id,
    provider_status = excluded.provider_status, current_period_end = excluded.current_period_end,
    cancel_at_period_end = excluded.cancel_at_period_end, trial_end = excluded.trial_end,
    latest_event_id = excluded.latest_event_id, latest_event_created = excluded.latest_event_created,
    projected_plan = excluded.projected_plan, projected_status = excluded.projected_status,
    projected_reason = excluded.projected_reason, updated_at = now();
  -- An obsolete subscription deletion must not revoke another valid subscription.
  select * into chosen from public.billing_subscriptions
    where app_user_id = r.app_user_id and projected_plan = 'pro'
      and projected_status in ('active', 'trialing', 'canceled_period_end')
      and current_period_end > clock_timestamp()
    order by current_period_end desc, stripe_subscription_id limit 1;
  if not found then
    select * into chosen from public.billing_subscriptions
      where stripe_subscription_id = r.stripe_subscription_id;
  end if;
  chosen_plan := chosen.projected_plan;
  chosen_status := chosen.projected_status;
  chosen_reason := chosen.projected_reason;
  if chosen_plan = 'pro' and (chosen.current_period_end is null
      or chosen.current_period_end <= clock_timestamp()) then
    chosen_plan := 'free'; chosen_status := 'expired'; chosen_reason := 'period_expired';
  end if;
  insert into public.billing_entitlements (
    app_user_id, plan, status, current_period_end, source_subscription_id,
    source_event_id, source_event_created, reason
  ) values (r.app_user_id, chosen_plan, chosen_status,
    chosen.current_period_end, chosen.stripe_subscription_id,
    chosen.latest_event_id, chosen.latest_event_created, chosen_reason)
  on conflict (app_user_id) do update set
    plan = excluded.plan, status = excluded.status,
    current_period_end = excluded.current_period_end,
    source_subscription_id = excluded.source_subscription_id,
    source_event_id = excluded.source_event_id, source_event_created = excluded.source_event_created,
    reason = excluded.reason, updated_at = now();
  update public.billing_webhook_events set processing_state = 'processed',
    lease_token = null, last_error = null, processed_at = now(), updated_at = now()
    where stripe_event_id = p_event_id;
  update public.billing_customers set reconciliation_token = null, reconciliation_expires = null
    where stripe_customer_id = r.stripe_customer_id;
end;
$$;

create or replace function public.music_billing_fail_delivery(p_event_id text, p_token uuid)
returns void language plpgsql security definer set search_path = public as $$
declare customer_id text;
begin
  select stripe_customer_id into customer_id from public.billing_customers
    where reconciliation_token = p_token for update;
  if not found then return; end if;
  update public.billing_webhook_events set processing_state = 'failed', lease_token = null,
    last_error = 'Reconciliation failed', updated_at = now()
    where stripe_event_id = p_event_id and lease_token = p_token and processing_state = 'processing';
  if found then
    update public.billing_customers set reconciliation_token = null, reconciliation_expires = null
      where stripe_customer_id = customer_id;
  end if;
end;
$$;

revoke all on function public.music_billing_claim_delivery(text,text,bigint,text,text,jsonb) from public, anon, authenticated;
revoke all on function public.music_billing_complete_delivery(text,uuid,jsonb,jsonb) from public, anon, authenticated;
revoke all on function public.music_billing_fail_delivery(text,uuid) from public, anon, authenticated;
grant execute on function public.music_billing_claim_delivery(text,text,bigint,text,text,jsonb) to service_role;
grant execute on function public.music_billing_complete_delivery(text,uuid,jsonb,jsonb) to service_role;
grant execute on function public.music_billing_fail_delivery(text,uuid) to service_role;
-- Block obsolete non-atomic billing service versions after cutover.
revoke execute on function public.billing_claim_webhook_event(text,text,bigint,jsonb) from service_role;
revoke execute on function public.billing_apply_subscription(uuid,text,text,text,text,text,timestamptz,boolean,timestamptz,text,bigint) from service_role;
revoke execute on function public.billing_save_entitlement(uuid,text,text,timestamptz,text,text,bigint,text) from service_role;
