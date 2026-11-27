-- READ ONLY: run in the intended Music TEST project before approving migrations.
-- No application rows, auth identities, secrets or payment payloads are selected.
-- This inventory is not an automatic schema-compatibility verdict.
begin read only;
select current_setting('server_version') as postgres_version;
select table_name, column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public' and table_name in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements')
order by table_name, ordinal_position;

select c.relname as table_name, c.relrowsecurity as rls_enabled,
 c.relforcerowsecurity as force_rls, pg_get_userbyid(c.relowner) as owner
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements');

select c.relname as table_name, co.conname, pg_get_constraintdef(co.oid) as definition
from pg_constraint co join pg_class c on c.oid = co.conrelid
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements')
order by c.relname, co.conname;
select tablename, indexname, indexdef from pg_indexes
where schemaname = 'public' and tablename in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements');
select tablename, policyname, permissive, roles, cmd, qual, with_check from pg_policies
where schemaname = 'public' and tablename in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements');

select p.proname, pg_get_function_identity_arguments(p.oid) as arguments,
 p.prosecdef as security_definer, p.proconfig,
 pg_get_userbyid(p.proowner) as owner, p.proacl,
 has_function_privilege('anon', p.oid, 'EXECUTE') as anon_execute,
 has_function_privilege('authenticated', p.oid, 'EXECUTE') as user_execute,
 has_function_privilege('service_role', p.oid, 'EXECUTE') as service_execute
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and (p.proname like 'billing_%' or p.proname like 'music_billing_%')
order by p.proname;
select c.relname as table_name, t.tgname, pg_get_triggerdef(t.oid) as definition
from pg_trigger t join pg_class c on c.oid = t.tgrelid
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'billing_customers' and not t.tgisinternal;

select r.role_name, c.relname as table_name,
 has_table_privilege(r.role_name, c.oid, 'SELECT') as can_select,
 has_table_privilege(r.role_name, c.oid, 'INSERT') as can_insert,
 has_table_privilege(r.role_name, c.oid, 'UPDATE') as can_update,
 has_table_privilege(r.role_name, c.oid, 'DELETE') as can_delete
from (values ('anon'), ('authenticated'), ('service_role')) r(role_name)
cross join pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements');
select rolname, rolbypassrls from pg_roles
where rolname in ('anon','authenticated','service_role');
select has_schema_privilege('anon','public','CREATE') as anon_create_public,
 has_schema_privilege('authenticated','public','CREATE') as user_create_public;
rollback;
