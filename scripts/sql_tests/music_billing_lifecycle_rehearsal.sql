-- Disposable synthetic PostgreSQL/Supabase test project ONLY; all writes roll back.
-- Requires two synthetic auth users; runner sets music_test.user_a/user_b.
begin;
set local statement_timeout='30s';
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
rollback;
