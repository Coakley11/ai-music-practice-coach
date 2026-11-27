-- NEW Music-only fresh install. DO NOT run historical generic migrations with this.
-- External execution requires separate approval. Confirm project in the dashboard.
-- Deliberately NOT replayable: any preexisting Music-named object aborts atomically.
begin;
set local lock_timeout = '3s';
set local statement_timeout = '30s';
set local search_path = pg_catalog;

do $preconditions$
begin
  if not pg_catalog.pg_try_advisory_xact_lock(pg_catalog.hashtextextended('music_billing_install_v1',0)) then
    raise exception 'Another Music installation is running';
  end if;
  if current_user in ('anon','authenticated','service_role') then
    raise exception 'Installation requires an approved database owner';
  end if;
  if not has_schema_privilege(current_user,'public','CREATE')
    or to_regclass('auth.users') is null or to_regprocedure('auth.uid()') is null
    or to_regprocedure('pg_catalog.gen_random_uuid()') is null then
    raise exception 'Required schema/auth/UUID prerequisites missing';
  end if;
  if not exists (select 1 from pg_attribute where attrelid='auth.users'::regclass
      and attname='id' and atttypid='uuid'::regtype and not attisdropped) then
    raise exception 'auth.users.id must be UUID';
  end if;
  if (select count(*) from pg_roles where rolname in ('anon','authenticated','service_role')) <> 3 then
    raise exception 'Required API roles missing';
  end if;
  if exists (select 1 from pg_roles where rolname in ('anon','authenticated') and (rolsuper or rolbypassrls))
    or pg_has_role('anon','service_role','MEMBER') or pg_has_role('authenticated','service_role','MEMBER')
    or has_schema_privilege('anon','public','CREATE') or has_schema_privilege('authenticated','public','CREATE') then
    raise exception 'Untrusted role/schema privileges require separate security review';
  end if;
  if exists (select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where n.nspname='public' and left(c.relname,14)='music_billing_')
    or exists (select 1 from pg_type t join pg_namespace n on n.oid=t.typnamespace
      where n.nspname='public' and left(t.typname,14)='music_billing_')
    or exists (select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
      where n.nspname='public' and left(p.proname,14)='music_billing_')
    or exists (select 1 from pg_constraint where left(conname,14)='music_billing_')
    or exists (select 1 from pg_trigger where left(tgname,14)='music_billing_') then
    raise exception 'Music namespace collision: stop and review ownership; nothing is adopted';
  end if;
end;
$preconditions$;

create table public.music_billing_customers (
 app_user_id uuid not null,
 stripe_customer_id text not null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 reconciliation_token uuid,
 reconciliation_expires timestamptz,
 checkout_token uuid,
 checkout_price_id text,
 checkout_expires timestamptz,
 constraint music_billing_customers_pk primary key(app_user_id),
 constraint music_billing_customers_stripe_key unique(stripe_customer_id),
 constraint music_billing_customers_owner_key unique(app_user_id,stripe_customer_id),
 constraint music_billing_customers_user_fk foreign key(app_user_id) references auth.users(id) on delete cascade,
 constraint music_billing_customers_id_check check(stripe_customer_id ~ '^cus_.+'),
 constraint music_billing_customers_lease_check check((reconciliation_token is null)=(reconciliation_expires is null)),
 constraint music_billing_customers_checkout_check check(
  (checkout_token is null and checkout_price_id is null and checkout_expires is null) or
  (checkout_token is not null and checkout_price_id is not null and checkout_expires is not null))
);
create table public.music_billing_subscriptions (
 stripe_subscription_id text not null,
 app_user_id uuid not null,
 stripe_customer_id text not null,
 stripe_product_id text,
 stripe_price_id text,
 provider_status text not null,
 current_period_end timestamptz,
 cancel_at_period_end boolean not null default false,
 trial_end timestamptz,
 latest_event_id text not null,
 latest_event_created bigint not null,
 projected_plan text not null,
 projected_status text not null,
 projected_reason text not null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 constraint music_billing_subscriptions_pk primary key(stripe_subscription_id),
 constraint music_billing_subscriptions_owner_fk foreign key(app_user_id,stripe_customer_id)
  references public.music_billing_customers(app_user_id,stripe_customer_id) on delete cascade,
 constraint music_billing_subscriptions_status_check check(provider_status in
  ('active','trialing','past_due','canceled','unpaid','incomplete','incomplete_expired','paused')),
 constraint music_billing_subscriptions_projection_check check(
  (projected_plan='free' and projected_status in ('authenticated_free','past_due','expired')) or
  (projected_plan='pro' and projected_status in ('active','trialing','canceled_period_end') and current_period_end is not null))
);
create index music_billing_subscriptions_user_idx on public.music_billing_subscriptions(app_user_id);
create table public.music_billing_webhook_events (
 stripe_event_id text not null,
 stripe_customer_id text not null,
 event_type text not null,
 event_created bigint not null,
 fingerprint text not null,
 processing_state text not null,
 lease_token uuid,
 attempt_count integer not null default 1,
 last_error text,
 received_at timestamptz not null default now(),
 processed_at timestamptz,
 updated_at timestamptz not null default now(),
 constraint music_billing_webhook_events_pk primary key(stripe_event_id),
 constraint music_billing_webhook_events_customer_fk foreign key(stripe_customer_id)
  references public.music_billing_customers(stripe_customer_id) on delete cascade,
 constraint music_billing_webhook_events_state_check check(processing_state in ('processing','processed','failed')),
 constraint music_billing_webhook_events_lease_check check((processing_state='processing')=(lease_token is not null)),
 constraint music_billing_webhook_events_fingerprint_check check(fingerprint ~ '^[0-9a-f]{64}$'),
 constraint music_billing_webhook_events_attempt_check check(attempt_count > 0 and event_created > 0)
);
create table public.music_billing_entitlements (
 app_user_id uuid not null,
 plan text not null,
 status text not null,
 current_period_end timestamptz,
 source_subscription_id text,
 source_event_id text not null,
 source_event_created bigint not null,
 reason text not null,
 updated_at timestamptz not null default now(),
 constraint music_billing_entitlements_pk primary key(app_user_id),
 constraint music_billing_entitlements_user_fk foreign key(app_user_id) references auth.users(id) on delete cascade,
 constraint music_billing_entitlements_plan_check check(plan in ('free','pro')),
 constraint music_billing_entitlements_paid_check check(plan<>'pro' or
  (status in ('active','trialing','canceled_period_end') and current_period_end is not null))
);

create function public.music_billing_preserve_customer_owner() returns trigger
language plpgsql set search_path = '' as $$
begin
 if new.app_user_id is distinct from old.app_user_id or new.stripe_customer_id is distinct from old.stripe_customer_id then
  raise exception 'Customer ownership is immutable';
 end if;
 return new;
end;
$$;
create trigger music_billing_customer_owner_immutable before update on public.music_billing_customers
for each row execute function public.music_billing_preserve_customer_owner();

create function public.music_billing_attach_customer(p_user_id uuid,p_customer_id text)
returns void language plpgsql security definer set search_path = '' as $$
declare stored text;
begin
 if p_user_id is null or p_customer_id is null or p_customer_id !~ '^cus_.+' then
  raise exception 'Invalid customer mapping';
 end if;
 insert into public.music_billing_customers(app_user_id,stripe_customer_id)
  values(p_user_id,p_customer_id) on conflict (app_user_id) do nothing;
 select stripe_customer_id into stored from public.music_billing_customers where app_user_id=p_user_id;
 if stored is distinct from p_customer_id then raise exception 'Customer ownership conflict'; end if;
end;
$$;

create function public.music_billing_reserve_checkout(p_user_id uuid,p_price_id text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare customer public.music_billing_customers%rowtype;
 token uuid; expires timestamptz;
begin
 select * into customer from public.music_billing_customers where app_user_id=p_user_id for update;
 if not found or p_price_id is null or p_price_id !~ '^price_.+' then raise exception 'Invalid Checkout owner or price'; end if;
 if exists (select 1 from public.music_billing_subscriptions where app_user_id=p_user_id
  and provider_status not in ('canceled','incomplete_expired')) then
  raise exception 'Existing subscription requires subscription management';
 end if;
 if customer.checkout_expires > clock_timestamp() then
  if customer.checkout_price_id is distinct from p_price_id then raise exception 'Another Checkout is pending'; end if;
  token := customer.checkout_token; expires := customer.checkout_expires;
 else
  token := gen_random_uuid();
  expires := to_timestamp(floor(extract(epoch from clock_timestamp()))+3600);
  update public.music_billing_customers set checkout_token=token,checkout_price_id=p_price_id,
   checkout_expires=expires where app_user_id=p_user_id;
 end if;
 return jsonb_build_object('token',token,'expires_at',extract(epoch from expires)::bigint);
end;
$$;

create function public.music_billing_claim_delivery(
  p_event_id text, p_event_type text, p_created bigint,
  p_fingerprint text, p_customer_id text
) returns text language plpgsql security definer set search_path = '' as $$
declare
  customer public.music_billing_customers%rowtype;
  event public.music_billing_webhook_events%rowtype;
  token uuid := gen_random_uuid();
begin
  if nullif(p_event_id,'') is null or nullif(p_event_type,'') is null or p_created is null or p_created<=0
    or p_fingerprint is null or p_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'Invalid event envelope';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(p_event_id, 0));
  select * into customer from public.music_billing_customers
    where stripe_customer_id = p_customer_id for update;
  if not found then raise exception 'Unmapped customer'; end if;
  -- All functions lock customer before event, serializing provider reads per user.
  select * into event from public.music_billing_webhook_events
    where stripe_event_id = p_event_id for update;
  if found then
    if event.fingerprint <> p_fingerprint or event.event_type <> p_event_type
      or event.event_created <> p_created or event.stripe_customer_id <> p_customer_id then
      return 'collision';
    end if;
    if event.processing_state = 'processed' then return ''; end if;
  end if;
  if customer.reconciliation_token is not null
      and customer.reconciliation_expires > clock_timestamp() then return 'busy'; end if;
  insert into public.music_billing_webhook_events as target (
    stripe_event_id, stripe_customer_id, event_type, event_created, processing_state,
    fingerprint, lease_token
  ) values (p_event_id, p_customer_id, p_event_type, p_created, 'processing', p_fingerprint, token)
  on conflict (stripe_event_id) do update set
    processing_state = 'processing', lease_token = token,
    attempt_count = target.attempt_count + 1, last_error = null, updated_at = now();
  update public.music_billing_customers set reconciliation_token = token,
    reconciliation_expires = clock_timestamp() + interval '5 minutes'
    where stripe_customer_id = p_customer_id;
  return token::text;
end;
$$;

create function public.music_billing_complete_delivery(
  p_event_id text, p_token uuid, p_record jsonb, p_entitlement jsonb
) returns void language plpgsql security definer set search_path = '' as $$
declare
  customer public.music_billing_customers%rowtype;
  event public.music_billing_webhook_events%rowtype;
  r public.music_billing_subscriptions%rowtype;
  chosen public.music_billing_subscriptions%rowtype;
  chosen_plan text;
  chosen_status text;
  chosen_reason text;
begin
  r := jsonb_populate_record(null::public.music_billing_subscriptions, p_record);
  select * into customer from public.music_billing_customers
    where stripe_customer_id = r.stripe_customer_id for update;
  if not found or p_token is null or customer.app_user_id is distinct from r.app_user_id
      or customer.reconciliation_token is distinct from p_token
      or customer.reconciliation_expires is null
      or customer.reconciliation_expires <= clock_timestamp() then
    raise exception 'Customer lease ownership lost';
  end if;
  select * into event from public.music_billing_webhook_events
    where stripe_event_id = p_event_id for update;
  if not found or event.processing_state <> 'processing'
      or event.stripe_customer_id is distinct from r.stripe_customer_id
      or event.lease_token is distinct from p_token
      or r.latest_event_id is distinct from p_event_id
      or r.latest_event_created is distinct from event.event_created then raise exception 'Event lease ownership lost'; end if;
  if exists (select 1 from public.music_billing_subscriptions
      where stripe_subscription_id = r.stripe_subscription_id
      and (app_user_id <> r.app_user_id or stripe_customer_id <> r.stripe_customer_id)) then
    raise exception 'Subscription ownership conflict';
  end if;
  if p_entitlement->>'plan' = 'pro' and (
      r.provider_status not in ('active','trialing') or r.current_period_end is null
      or r.current_period_end <= clock_timestamp() or nullif(r.stripe_price_id,'') is null
      or (r.provider_status='trialing' and p_entitlement->>'status' <> 'trialing')
      or (r.provider_status='active' and r.cancel_at_period_end and p_entitlement->>'status' <> 'canceled_period_end')
      or (r.provider_status='active' and not r.cancel_at_period_end and p_entitlement->>'status' <> 'active')) then
    raise exception 'Invalid paid subscription projection';
  end if;
  insert into public.music_billing_subscriptions (
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
  select * into chosen from public.music_billing_subscriptions
    where app_user_id = r.app_user_id and projected_plan = 'pro'
      and projected_status in ('active', 'trialing', 'canceled_period_end')
      and current_period_end > clock_timestamp()
    order by current_period_end desc, stripe_subscription_id limit 1;
  if not found then
    select * into chosen from public.music_billing_subscriptions
      where stripe_subscription_id = r.stripe_subscription_id;
  end if;
  chosen_plan := chosen.projected_plan;
  chosen_status := chosen.projected_status;
  chosen_reason := chosen.projected_reason;
  if chosen_plan = 'pro' and (chosen.current_period_end is null
      or chosen.current_period_end <= clock_timestamp()) then
    chosen_plan := 'free'; chosen_status := 'expired'; chosen_reason := 'period_expired';
  end if;
  insert into public.music_billing_entitlements (
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
  update public.music_billing_webhook_events set processing_state = 'processed',
    lease_token = null, last_error = null, processed_at = now(), updated_at = now()
    where stripe_event_id = p_event_id;
  update public.music_billing_customers set reconciliation_token = null, reconciliation_expires = null
    where stripe_customer_id = r.stripe_customer_id;
end;
$$;

create function public.music_billing_fail_delivery(p_event_id text, p_token uuid)
returns void language plpgsql security definer set search_path = '' as $$
declare customer_id text;
begin
  select stripe_customer_id into customer_id from public.music_billing_customers
    where reconciliation_token = p_token for update;
  if not found then return; end if;
  update public.music_billing_webhook_events set processing_state = 'failed', lease_token = null,
    last_error = 'Reconciliation failed', updated_at = now()
    where stripe_event_id = p_event_id and lease_token = p_token and processing_state = 'processing';
  if found then
    update public.music_billing_customers set reconciliation_token = null, reconciliation_expires = null
      where stripe_customer_id = customer_id;
  end if;
end;
$$;


-- Clear ALL defaults on ONLY the new objects, including unknown default grantees.
-- No ALTER DEFAULT PRIVILEGES, schema grants or existing application objects change.
do $clear_defaults$
declare item record; recipient text;
begin
 for item in
  select distinct n.nspname,c.relname,a.grantee from pg_class c join pg_namespace n on n.oid=c.relnamespace
  cross join lateral aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
  where n.nspname='public' and c.relname in
   ('music_billing_customers','music_billing_subscriptions','music_billing_webhook_events','music_billing_entitlements')
   and a.grantee<>c.relowner
 loop
  recipient := case when item.grantee=0 then 'PUBLIC' else quote_ident(pg_get_userbyid(item.grantee)) end;
  execute format('revoke all privileges on table %I.%I from %s',item.nspname,item.relname,recipient);
 end loop;
 for item in
  select p.oid,a.grantee from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  cross join lateral aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
  where n.nspname='public' and left(p.proname,14)='music_billing_' and a.grantee<>p.proowner
 loop
  recipient := case when item.grantee=0 then 'PUBLIC' else quote_ident(pg_get_userbyid(item.grantee)) end;
  execute format('revoke all privileges on function %s from %s',item.oid::regprocedure,recipient);
 end loop;
end;
$clear_defaults$;

revoke all privileges on table public.music_billing_customers,public.music_billing_subscriptions,
 public.music_billing_webhook_events,public.music_billing_entitlements from public,anon,authenticated,service_role;
alter table public.music_billing_customers enable row level security;
alter table public.music_billing_subscriptions enable row level security;
alter table public.music_billing_webhook_events enable row level security;
alter table public.music_billing_entitlements enable row level security;
grant select on public.music_billing_entitlements to authenticated;
create policy music_billing_entitlements_read_own on public.music_billing_entitlements
 for select to authenticated using (app_user_id=(select auth.uid()));
-- Backend writes only via checked, atomic RPCs. BYPASSRLS does not bypass ACLs.
grant select on public.music_billing_customers,public.music_billing_entitlements to service_role;
grant execute on function public.music_billing_attach_customer(uuid,text) to service_role;
grant execute on function public.music_billing_reserve_checkout(uuid,text) to service_role;
grant execute on function public.music_billing_claim_delivery(text,text,bigint,text,text) to service_role;
grant execute on function public.music_billing_complete_delivery(text,uuid,jsonb,jsonb) to service_role;
grant execute on function public.music_billing_fail_delivery(text,uuid) to service_role;

-- Fail the entire installation if inherited effective privileges defeat the ACLs.
do $postconditions$
declare target regclass; role_name text; privilege_name text; fn record;
begin
 foreach target in array array['public.music_billing_customers'::regclass,
  'public.music_billing_subscriptions'::regclass,'public.music_billing_webhook_events'::regclass,
  'public.music_billing_entitlements'::regclass] loop
  foreach role_name in array array['anon','authenticated','service_role'] loop
   foreach privilege_name in array array['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] loop
    if has_table_privilege(role_name,target,privilege_name) then
     raise exception 'Unsafe effective Music table privilege for role %',role_name;
    end if;
   end loop;
   if has_any_column_privilege(role_name,target,'INSERT') or has_any_column_privilege(role_name,target,'UPDATE') then
    raise exception 'Unsafe effective Music column privileges';
   end if;
   if has_table_privilege(role_name,target,'SELECT') is distinct from
    ((role_name='authenticated' and target='public.music_billing_entitlements'::regclass)
     or (role_name='service_role' and target in ('public.music_billing_customers'::regclass,
      'public.music_billing_entitlements'::regclass))) then
    raise exception 'Unexpected Music read privilege for role %',role_name;
   end if;
  end loop;
 end loop;
 for fn in select p.oid,p.proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public' and left(p.proname,14)='music_billing_' loop
  if has_function_privilege('anon',fn.oid,'EXECUTE') or has_function_privilege('authenticated',fn.oid,'EXECUTE') then
   raise exception 'Unsafe effective Music RPC privilege';
  end if;
  if has_function_privilege('service_role',fn.oid,'EXECUTE') is distinct from
   (fn.proname <> 'music_billing_preserve_customer_owner') then
   raise exception 'Unexpected backend Music RPC privilege';
  end if;
 end loop;
end;
$postconditions$;
commit;
