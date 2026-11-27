-- Run ONLY after approval, against a disposable Music test database.
-- Supply test_user_id for an existing auth.users account with NO billing records.
-- Example: psql <test-connection> -v test_user_id=<test-auth-uuid> -f this-file.sql
\set ON_ERROR_STOP on
begin;
select set_config('music_billing_test.user_id', :'test_user_id', true);
do $$
declare
  uid uuid := current_setting('music_billing_test.user_id')::uuid;
  lease text;
  result text;
  record_data jsonb;
  projection jsonb;
begin
  if not exists (select 1 from auth.users where id = uid) then
    raise exception 'Use an existing test auth user';
  end if;
  if exists (select 1 from public.billing_customers where app_user_id = uid) then
    raise exception 'Use a test user without an existing billing mapping';
  end if;
  if has_table_privilege('authenticated', 'public.billing_entitlements', 'UPDATE')
    or has_table_privilege('anon', 'public.billing_entitlements', 'SELECT')
    or has_function_privilege('authenticated',
      'public.music_billing_complete_delivery(text,uuid,jsonb,jsonb)', 'EXECUTE')
    or has_function_privilege('anon',
      'public.music_billing_claim_delivery(text,text,bigint,text,text,jsonb)', 'EXECUTE') then
    raise exception 'Client billing privileges are unsafe';
  end if;
  insert into public.billing_customers(app_user_id, stripe_customer_id)
    values (uid, 'cus_music_phase2_sql_fixture');
  begin
    update public.billing_customers set stripe_customer_id = 'cus_forbidden_rebinding'
      where app_user_id = uid;
    raise exception 'Ownership mutation was accepted';
  exception when raise_exception then
    if sqlerrm <> 'Customer ownership is immutable' then raise; end if;
  end;
  lease := public.music_billing_claim_delivery('evt_music_phase2_sql', 'customer.subscription.updated',
    100, 'fixture-fingerprint', 'cus_music_phase2_sql_fixture', '{}'::jsonb);
  result := public.music_billing_claim_delivery('evt_music_phase2_busy', 'customer.subscription.updated',
    101, 'busy-fingerprint', 'cus_music_phase2_sql_fixture', '{}'::jsonb);
  if result <> 'busy' then raise exception 'Customer lease was not exclusive'; end if;
  record_data := jsonb_build_object('app_user_id', uid,
    'stripe_customer_id', 'cus_music_phase2_sql_fixture', 'stripe_subscription_id', 'sub_music_phase2_sql',
    'stripe_product_id', 'prod_fixture', 'stripe_price_id', 'price_fixture', 'provider_status', 'active',
    'current_period_end', now() + interval '30 days', 'cancel_at_period_end', false,
    'latest_event_id', 'evt_music_phase2_sql', 'latest_event_created', 100);
  projection := jsonb_build_object('plan', 'pro', 'status', 'active', 'reason', 'active');
  -- Deliberately fail the entitlement CHECK after subscription persistence.
  begin
    perform public.music_billing_complete_delivery('evt_music_phase2_sql', lease::uuid,
      record_data, projection || '{"plan":"invalid"}'::jsonb);
    raise exception 'Expected entitlement constraint failure';
  exception when check_violation then null;
  end;
  if exists (select 1 from public.billing_subscriptions where stripe_subscription_id = 'sub_music_phase2_sql')
    or exists (select 1 from public.billing_entitlements where app_user_id = uid)
    or not exists (select 1 from public.billing_webhook_events
      where stripe_event_id = 'evt_music_phase2_sql' and processing_state = 'processing') then
    raise exception 'Failed RPC left partial billing state';
  end if;
  perform public.music_billing_complete_delivery('evt_music_phase2_sql', lease::uuid, record_data, projection);
  if not exists (select 1 from public.billing_entitlements where app_user_id = uid and plan = 'pro') then
    raise exception 'Valid commit did not activate Pro';
  end if;
  result := public.music_billing_claim_delivery('evt_music_phase2_sql', 'customer.subscription.updated',
    100, 'fixture-fingerprint', 'cus_music_phase2_sql_fixture', '{}'::jsonb);
  if result <> '' then raise exception 'Completed event was not deduplicated'; end if;
  result := public.music_billing_claim_delivery('evt_music_phase2_sql', 'customer.subscription.updated',
    100, 'different-fingerprint', 'cus_music_phase2_sql_fixture', '{}'::jsonb);
  if result <> 'collision' then raise exception 'Changed event identity was accepted'; end if;
end;
$$;
rollback;
