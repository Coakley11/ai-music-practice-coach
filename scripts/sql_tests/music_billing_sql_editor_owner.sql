-- Run the ENTIRE script, only in smpyutzfktjgpdibdbqb SQL Editor, as postgres.
-- First create TWO NEW synthetic users through Authentication > Users > Add user.
-- Replace the two UUID placeholders below. Existing test users with billing records are rejected.
-- No schema installation, permanent grants, or Auth writes occur here.
BEGIN;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';
SELECT set_config('music_test.user_a', '8beda112-370e-4711-9c06-d6e98341e791', true);
SELECT set_config('music_test.user_b', 'af2b6810-1272-499c-bb0f-606c68a9c137', true);

DO $$
DECLARE a uuid := current_setting('music_test.user_a')::uuid;
        b uuid := current_setting('music_test.user_b')::uuid;
        t text;
BEGIN
 IF a=b THEN RAISE EXCEPTION 'Use two distinct fresh synthetic accounts'; END IF;
 IF (SELECT count(*) FROM auth.users WHERE id IN(a,b)
     AND email LIKE '%@example.invalid') <> 2 THEN
   RAISE EXCEPTION 'Both users must exist and use synthetic example.invalid email addresses';
 END IF;
 FOREACH t IN ARRAY ARRAY['music_billing_customers','music_billing_subscriptions','music_billing_webhook_events','music_billing_entitlements'] LOOP
   IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname='public' AND c.relname=t AND c.relrowsecurity) THEN
     RAISE EXCEPTION 'Missing table or disabled RLS: %',t;
   END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM public.music_billing_customers WHERE app_user_id IN(a,b))
 OR EXISTS(SELECT 1 FROM public.music_billing_subscriptions WHERE app_user_id IN(a,b))
 OR EXISTS(SELECT 1 FROM public.music_billing_entitlements WHERE app_user_id IN(a,b)) THEN
   RAISE EXCEPTION 'Fresh users already have billing records; preserve them and select different users';
 END IF;
 IF EXISTS(SELECT 1 FROM public.music_billing_customers
           WHERE stripe_customer_id LIKE 'cus_music_role_fixture_%' OR stripe_customer_id='cus_music_lifecycle')
 OR EXISTS(SELECT 1 FROM public.music_billing_subscriptions
           WHERE stripe_subscription_id LIKE 'sub_music_role_fixture_%' OR stripe_subscription_id='sub_music_lifecycle')
 OR EXISTS(SELECT 1 FROM public.music_billing_webhook_events
           WHERE stripe_event_id LIKE 'evt_music_role_fixture_%' OR stripe_event_id='evt_music_atomic_fixture'
           OR stripe_event_id LIKE 'evt_music_lifecycle_%' OR stripe_event_id LIKE 'evt_music_parallel_%')
 OR EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='public.music_billing_entitlements'::regclass
           AND conname='music_billing_test_reject_reason') THEN
   RAISE EXCEPTION 'Fixture collision or leftover constraint: stop; do not delete existing data';
 END IF;
END $$;

-- The savepoint lets the lifecycle harness reuse the same clean users.
SAVEPOINT before_role_tests;
-- Test-only failure injection, rolled back. Never run this against production.
alter table public.music_billing_entitlements add constraint music_billing_test_reject_reason check(reason<>'fixture_reject');
set local role service_role;
do $$
declare uid uuid; customer_id text; event_id text; token text; record_data jsonb; projection jsonb; n integer;
begin
 for n in 1..2 loop
  uid := current_setting(case when n=1 then 'music_test.user_a' else 'music_test.user_b' end)::uuid;
  customer_id := 'cus_music_role_fixture_'||n; event_id := 'evt_music_role_fixture_'||n;
  perform public.music_billing_attach_customer(uid,customer_id);
  token := public.music_billing_claim_delivery(event_id,'customer.subscription.updated',100,repeat('a',64),customer_id);
  record_data := jsonb_build_object('app_user_id',uid,'stripe_customer_id',customer_id,
   'stripe_subscription_id','sub_music_role_fixture_'||n,'stripe_product_id','prod_fixture','stripe_price_id','price_fixture',
   'provider_status',case when n=1 then 'active' else 'canceled' end,
   'current_period_end',now()+interval '1 day','cancel_at_period_end',false,
   'latest_event_id',event_id,'latest_event_created',100);
  projection := jsonb_build_object('plan',case when n=1 then 'pro' else 'free' end,
   'status',case when n=1 then 'active' else 'expired' end,'reason','fixture');
  perform public.music_billing_complete_delivery(event_id,token::uuid,record_data,projection);
 end loop;
 if (select count(*) from public.music_billing_customers where stripe_customer_id like 'cus_music_role_fixture_%')<>2 then
  raise exception 'Service read/attach failed';
 end if;
end;
$$;
reset role;
-- Verify rollback AFTER subscription mutation, through an entitlement constraint failure.
set local role service_role;
do $$
declare uid uuid:=current_setting('music_test.user_a')::uuid; token text; r jsonb; e jsonb;
begin
 token := public.music_billing_claim_delivery('evt_music_atomic_fixture','customer.subscription.updated',101,repeat('b',64),'cus_music_role_fixture_1');
 r := jsonb_build_object('app_user_id',uid,'stripe_customer_id','cus_music_role_fixture_1',
  'stripe_subscription_id','sub_music_role_fixture_1','stripe_product_id','prod_fixture','stripe_price_id','price_fixture',
  'provider_status','active','current_period_end',now()+interval '2 days','cancel_at_period_end',false,
  'latest_event_id','evt_music_atomic_fixture','latest_event_created',101);
 e := jsonb_build_object('plan','pro','status','active','reason','fixture_reject');
 begin
  perform public.music_billing_complete_delivery('evt_music_atomic_fixture',token::uuid,r,e);
  raise exception 'Expected constraint failure';
 exception when check_violation then null;
 end;
 -- Entitlement read is allowed; raw subscription/event reads intentionally are not.
 if not exists (select 1 from public.music_billing_entitlements where app_user_id=uid
  and source_event_id='evt_music_role_fixture_1') then raise exception 'Atomic rollback failed'; end if;
 perform public.music_billing_complete_delivery('evt_music_atomic_fixture',token::uuid,r,e||'{"reason":"fixture"}'::jsonb);
 if public.music_billing_claim_delivery('evt_music_atomic_fixture','customer.subscription.updated',101,repeat('b',64),'cus_music_role_fixture_1')<>'' then
  raise exception 'Duplicate was not deduplicated';
 end if;
 if public.music_billing_claim_delivery('evt_music_atomic_fixture','customer.subscription.updated',101,repeat('c',64),'cus_music_role_fixture_1')<>'collision' then
  raise exception 'Collision was accepted';
 end if;
end;
$$;
reset role;
-- Owner can inspect all three atomic effects without giving raw access to backend.
do $$
begin
 if not exists(select 1 from public.music_billing_subscriptions where stripe_subscription_id='sub_music_role_fixture_1'
  and latest_event_id='evt_music_atomic_fixture') or not exists(select 1 from public.music_billing_webhook_events
  where stripe_event_id='evt_music_atomic_fixture' and processing_state='processed') then
  raise exception 'Atomic completion missing';
 end if;
end;
$$;

set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('music_test.user_a'),true) is not null as claims_a;
select set_config('request.jwt.claims',jsonb_build_object('sub',current_setting('music_test.user_a'),'role','authenticated')::text,true) is not null as claims_json_a;
do $$
begin
 if auth.uid() is distinct from current_setting('music_test.user_a')::uuid then raise exception 'Auth simulation failed'; end if;
 if (select count(*) from public.music_billing_entitlements)<>1
  or exists(select 1 from public.music_billing_entitlements where app_user_id=current_setting('music_test.user_b')::uuid) then
  raise exception 'User A RLS isolation failed';
 end if;
end;
$$;
select set_config('request.jwt.claim.sub',current_setting('music_test.user_b'),true) is not null as claims_b;
select set_config('request.jwt.claims',jsonb_build_object('sub',current_setting('music_test.user_b'),'role','authenticated')::text,true) is not null as claims_json_b;
do $$
begin
 if (select count(*) from public.music_billing_entitlements)<>1
  or exists(select 1 from public.music_billing_entitlements where app_user_id=current_setting('music_test.user_a')::uuid) then
  raise exception 'User B RLS isolation failed';
 end if;
end;
$$;
reset role;

-- Real role execution attempts, not merely catalog ACL assertions.

set local role anon;
do $$
declare target text; statement text;
begin
 foreach target in array array['music_billing_customers','music_billing_subscriptions','music_billing_webhook_events','music_billing_entitlements'] loop
  foreach statement in array array['insert into public.'||quote_ident(target)||' default values',
   'update public.'||quote_ident(target)||' set updated_at=updated_at',
   'delete from public.'||quote_ident(target), 'truncate table public.'||quote_ident(target)] loop
   begin
    execute statement;
    raise exception 'Unexpected direct write privilege';
   exception when insufficient_privilege then null;
   end;
  end loop;
 end loop;
 foreach statement in array array[
  'select public.music_billing_attach_customer(null,null)',
  'select public.music_billing_reserve_checkout(null,null)',
  'select public.music_billing_claim_delivery(null,null,null,null,null)',
  'select public.music_billing_complete_delivery(null,null,null,null)',
  'select public.music_billing_fail_delivery(null,null)'] loop
  begin execute statement; raise exception 'Unexpected RPC execution';
  exception when insufficient_privilege then null; end;
 end loop;
 foreach target in array array['music_billing_customers','music_billing_subscriptions','music_billing_webhook_events','music_billing_entitlements'] loop
  begin execute 'select 1 from public.'||quote_ident(target)||' limit 1'; raise exception 'Unexpected raw read';
  exception when insufficient_privilege then null; end;
 end loop;
end;
$$;
reset role;

set local role authenticated;
do $$
declare target text; statement text;
begin
 foreach target in array array['music_billing_customers','music_billing_subscriptions','music_billing_webhook_events','music_billing_entitlements'] loop
  foreach statement in array array['insert into public.'||quote_ident(target)||' default values',
   'update public.'||quote_ident(target)||' set updated_at=updated_at',
   'delete from public.'||quote_ident(target), 'truncate table public.'||quote_ident(target)] loop
   begin
    execute statement;
    raise exception 'Unexpected direct write privilege';
   exception when insufficient_privilege then null;
   end;
  end loop;
 end loop;
 foreach statement in array array[
  'select public.music_billing_attach_customer(null,null)',
  'select public.music_billing_reserve_checkout(null,null)',
  'select public.music_billing_claim_delivery(null,null,null,null,null)',
  'select public.music_billing_complete_delivery(null,null,null,null)',
  'select public.music_billing_fail_delivery(null,null)'] loop
  begin execute statement; raise exception 'Unexpected RPC execution';
  exception when insufficient_privilege then null; end;
 end loop;
 foreach target in array array['music_billing_customers','music_billing_subscriptions','music_billing_webhook_events'] loop
  begin execute 'select 1 from public.'||quote_ident(target)||' limit 1'; raise exception 'Unexpected raw read';
  exception when insufficient_privilege then null; end;
 end loop;
end;
$$;
reset role;

set local role service_role;
do $$
declare target text; statement text;
begin
 foreach target in array array['music_billing_customers','music_billing_subscriptions','music_billing_webhook_events','music_billing_entitlements'] loop
  foreach statement in array array['insert into public.'||quote_ident(target)||' default values',
   'update public.'||quote_ident(target)||' set updated_at=updated_at',
   'delete from public.'||quote_ident(target), 'truncate table public.'||quote_ident(target)] loop
   begin
    execute statement;
    raise exception 'Unexpected direct write privilege';
   exception when insufficient_privilege then null;
   end;
  end loop;
 end loop;
 foreach target in array array['music_billing_subscriptions','music_billing_webhook_events'] loop
  begin execute 'select 1 from public.'||quote_ident(target)||' limit 1'; raise exception 'Unexpected raw read';
  exception when insufficient_privilege then null; end;
 end loop;
end;
$$;
reset role;


ROLLBACK TO SAVEPOINT before_role_tests;
-- The fixture rows and temporary constraint above have now been undone.
set local role service_role;
do $$
declare
 uid uuid:=current_setting('music_test.user_a')::uuid;
 token text; r jsonb; e jsonb; step int; provider text; paid boolean;
 scheduled boolean; event_id text; event_created bigint; expected_status text;
 reservation jsonb;
begin
 perform public.music_billing_attach_customer(uid,'cus_music_lifecycle');
 if exists(select 1 from public.music_billing_entitlements where app_user_id=uid) then raise exception 'Free account unexpectedly paid'; end if;
 reservation:=public.music_billing_reserve_checkout(uid,'price_fixture');
 if reservation is distinct from public.music_billing_reserve_checkout(uid,'price_fixture') then raise exception 'Checkout reservation not stable'; end if;
 -- Creation, renewal, scheduled cancellation, expiration, recovery, immediate
 -- termination, recovery, failed payment, recovery and an older notification
 -- reconciled using a fresh provider snapshot (not its old embedded payload).
 for step in 1..10 loop
  provider:=case when step in (4,6) then 'canceled' when step=8 then 'past_due' else 'active' end;
  paid:=provider='active'; scheduled:=step=3;
  expected_status:=case when step=3 then 'canceled_period_end' when paid then 'active' when step=8 then 'past_due' else 'expired' end;
  event_id:='evt_music_lifecycle_'||step;
  event_created:=case when step=10 then 50 else 200+step end;
  token:=public.music_billing_claim_delivery(event_id,'customer.subscription.updated',event_created,repeat('d',64),'cus_music_lifecycle');
  if token in ('','busy','collision') then raise exception 'Unexpected claim result'; end if;
  if public.music_billing_claim_delivery('evt_music_parallel_'||step,'customer.subscription.updated',500+step,repeat('e',64),'cus_music_lifecycle')<>'busy' then raise exception 'Customer lease not exclusive'; end if;
  r:=jsonb_build_object('app_user_id',uid,'stripe_customer_id','cus_music_lifecycle',
   'stripe_subscription_id','sub_music_lifecycle','stripe_product_id','prod_fixture','stripe_price_id','price_fixture',
   'provider_status',provider,'current_period_end',case when step=4 then now()-interval '1 second' else now()+step*interval '1 day' end,
   'cancel_at_period_end',scheduled,'latest_event_id',event_id,'latest_event_created',event_created);
  e:=jsonb_build_object('plan',case when paid then 'pro' else 'free' end,'status',expected_status,'reason','synthetic_lifecycle');
  perform public.music_billing_complete_delivery(event_id,token::uuid,r,e);
  if not exists(select 1 from public.music_billing_entitlements where app_user_id=uid and plan=e->>'plan' and status=expected_status and source_event_id=event_id) then raise exception 'Lifecycle mismatch at step %',step; end if;
  if public.music_billing_claim_delivery(event_id,'customer.subscription.updated',event_created,repeat('d',64),'cus_music_lifecycle')<>'' then raise exception 'Duplicate not ignored'; end if;
 end loop;
end$$;
reset role;

-- End of ALL test writes. Never replace this with COMMIT.
ROLLBACK;

-- Read-only post-check: this should return PASS and zero fixture counts.
SELECT
 CASE WHEN NOT EXISTS(SELECT 1 FROM pg_constraint
      WHERE conrelid='public.music_billing_entitlements'::regclass
        AND conname='music_billing_test_reject_reason')
   AND NOT EXISTS(SELECT 1 FROM public.music_billing_customers
      WHERE stripe_customer_id LIKE 'cus_music_role_fixture_%' OR stripe_customer_id='cus_music_lifecycle')
   AND NOT EXISTS(SELECT 1 FROM public.music_billing_subscriptions
      WHERE stripe_subscription_id LIKE 'sub_music_role_fixture_%' OR stripe_subscription_id='sub_music_lifecycle')
   AND NOT EXISTS(SELECT 1 FROM public.music_billing_webhook_events
      WHERE stripe_event_id LIKE 'evt_music_role_fixture_%' OR stripe_event_id='evt_music_atomic_fixture'
         OR stripe_event_id LIKE 'evt_music_lifecycle_%' OR stripe_event_id LIKE 'evt_music_parallel_%')
 THEN 'PASS: owner harnesses completed; rollback left no test fixtures or constraint'
 ELSE 'FAIL: inspect retained fixtures; do not delete records'
 END AS owner_test_result;
