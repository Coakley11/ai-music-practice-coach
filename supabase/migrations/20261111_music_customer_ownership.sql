-- Preserve existing bindings; reject reassignment even by billing service writes.
-- Apply after 20260927_monetization_m2.sql. No existing rows are changed.
create or replace function public.billing_preserve_customer_owner()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.app_user_id is distinct from old.app_user_id
     or new.stripe_customer_id is distinct from old.stripe_customer_id then
    raise exception 'Customer ownership is immutable';
  end if;
  return new;
end;
$$;

revoke execute on function public.billing_preserve_customer_owner()
  from public, anon, authenticated;

drop trigger if exists billing_customer_owner_immutable on public.billing_customers;
create trigger billing_customer_owner_immutable
before update on public.billing_customers
for each row execute function public.billing_preserve_customer_owner();
