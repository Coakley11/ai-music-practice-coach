-- PREPARED ONLY. Execute ONLY after separate approval in an isolated test clone.
-- Requires the NEW Music-only installer and TWO existing synthetic Auth users.
-- Never creates/deletes Auth users or touches Suite/Baseball tables.
-- psql -v user_a=<uuid> -v user_b=<uuid> -f music_billing_shared_roles.sql
\set ON_ERROR_STOP on
begin;
set local statement_timeout='30s';
select set_config('music_test.user_a', :'user_a',true) is not null as configured_a;
select set_config('music_test.user_b', :'user_b',true) is not null as configured_b;
do $$
begin
 if current_setting('music_test.user_a')=current_setting('music_test.user_b') then raise exception 'Use two different test accounts'; end if;
 if exists (select 1 from public.music_billing_customers where app_user_id in
  (current_setting('music_test.user_a')::uuid,current_setting('music_test.user_b')::uuid)) then
  raise exception 'Test accounts must have no existing Music billing records';
 end if;
end;
$$;
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

rollback;
