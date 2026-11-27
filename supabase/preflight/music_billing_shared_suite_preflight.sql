-- Shared-Suite Music preflight: READ-ONLY, not a migration.
-- Sections 01-08 audit legacy generic names, not approval to install them.
-- Sections 09-15 protect existing Baseball/Suite objects and inspect proposed names.
-- TARGET: operator-confirmed shared Suite project qhprdlwoxjpkiukxhftp.
-- SQL cannot infer the dashboard project ref reliably; confirm it before running.
-- Run the WHOLE script in the Supabase SQL Editor; no billing RPC is called.
-- Never calls billing RPCs, runs DDL/DML, or selects identities, keys or payloads.
-- Missing relations/columns skip dependent scans. A skip is NOT a passing check.
-- Every result section is labeled. Result grids may require scrolling in the editor.
begin transaction isolation level repeatable read read only;
set local statement_timeout = '15s';
set local lock_timeout = '3s';

-- 01. Execution context and prerequisites (no credentials / host / project IDs).
select '01_context' as section, current_user as inspection_role,
 current_setting('server_version') as postgres_version,
 current_setting('transaction_read_only') as must_be_on,
 (select rolsuper from pg_roles where rolname=current_user) as inspector_is_superuser,
 (select rolbypassrls from pg_roles where rolname=current_user) as inspector_bypasses_rls,
 current_setting('transaction_isolation') as snapshot_isolation,
 to_regclass('auth.users') is not null as auth_users_exists,
 to_regprocedure('auth.uid()') is not null as auth_uid_exists,
 to_regprocedure('gen_random_uuid()') is not null as uuid_function_exists,
 to_regprocedure('pg_catalog.hashtextextended(text,bigint)') is not null as hash_function_exists,
 to_regprocedure('pg_catalog.pg_advisory_xact_lock(bigint)') is not null as advisory_lock_exists,
 to_regprocedure('pg_catalog.jsonb_populate_record(anyelement,jsonb)') is not null as populate_record_exists,
 has_schema_privilege(current_user,'public','CREATE') as inspector_can_create_public;
select '01_roles' as section, expected.role_name,
 r.oid is not null as role_exists, r.rolsuper, r.rolbypassrls,
 case when r.oid is not null then has_schema_privilege(r.oid,'public','CREATE') end as create_public,
 case when r.oid is not null then has_schema_privilege(r.oid,'public','USAGE') end as use_public
from (values ('anon'),('authenticated'),('service_role')) expected(role_name)
left join pg_roles r on r.rolname = expected.role_name;

-- 02. Exact expected base/additive columns, types and nullability.
-- Defaults are shown side-by-side for human comparison (equivalent SQL can differ).
with expected(stage,table_name,column_name,type_name,not_null,default_sql) as (values
  ('M2', 'billing_customers', 'app_user_id', 'uuid', true, ''),
  ('M2', 'billing_customers', 'stripe_customer_id', 'text', true, ''),
  ('M2', 'billing_customers', 'email', 'text', false, ''),
  ('M2', 'billing_customers', 'created_at', 'timestamptz', true, 'now()'),
  ('M2', 'billing_customers', 'updated_at', 'timestamptz', true, 'now()'),
  ('M2', 'billing_subscriptions', 'stripe_subscription_id', 'text', true, ''),
  ('M2', 'billing_subscriptions', 'app_user_id', 'uuid', true, ''),
  ('M2', 'billing_subscriptions', 'stripe_customer_id', 'text', true, ''),
  ('M2', 'billing_subscriptions', 'stripe_product_id', 'text', false, ''),
  ('M2', 'billing_subscriptions', 'stripe_price_id', 'text', false, ''),
  ('M2', 'billing_subscriptions', 'provider_status', 'text', true, ''),
  ('M2', 'billing_subscriptions', 'current_period_end', 'timestamptz', false, ''),
  ('M2', 'billing_subscriptions', 'cancel_at_period_end', 'boolean', true, 'FALSE'),
  ('M2', 'billing_subscriptions', 'trial_end', 'timestamptz', false, ''),
  ('M2', 'billing_subscriptions', 'latest_event_id', 'text', true, ''),
  ('M2', 'billing_subscriptions', 'latest_event_created', 'bigint', true, ''),
  ('M2', 'billing_subscriptions', 'created_at', 'timestamptz', true, 'now()'),
  ('M2', 'billing_subscriptions', 'updated_at', 'timestamptz', true, 'now()'),
  ('M2', 'billing_webhook_events', 'stripe_event_id', 'text', true, ''),
  ('M2', 'billing_webhook_events', 'event_type', 'text', true, ''),
  ('M2', 'billing_webhook_events', 'event_created', 'bigint', true, ''),
  ('M2', 'billing_webhook_events', 'payload', 'jsonb', true, ''),
  ('M2', 'billing_webhook_events', 'processing_state', 'text', true, ''),
  ('M2', 'billing_webhook_events', 'attempt_count', 'integer', true, '1'),
  ('M2', 'billing_webhook_events', 'last_error', 'text', false, ''),
  ('M2', 'billing_webhook_events', 'received_at', 'timestamptz', true, 'now()'),
  ('M2', 'billing_webhook_events', 'processed_at', 'timestamptz', false, ''),
  ('M2', 'billing_webhook_events', 'updated_at', 'timestamptz', true, 'now()'),
  ('M2', 'billing_entitlements', 'app_user_id', 'uuid', true, ''),
  ('M2', 'billing_entitlements', 'plan', 'text', true, ''),
  ('M2', 'billing_entitlements', 'status', 'text', true, ''),
  ('M2', 'billing_entitlements', 'current_period_end', 'timestamptz', false, ''),
  ('M2', 'billing_entitlements', 'source_subscription_id', 'text', false, ''),
  ('M2', 'billing_entitlements', 'source_event_id', 'text', true, ''),
  ('M2', 'billing_entitlements', 'source_event_created', 'bigint', true, ''),
  ('M2', 'billing_entitlements', 'reason', 'text', true, ''),
  ('M2', 'billing_entitlements', 'updated_at', 'timestamptz', true, 'now()'),
  ('Phase2', 'billing_customers', 'reconciliation_token', 'uuid', false, ''),
  ('Phase2', 'billing_customers', 'reconciliation_expires', 'timestamptz', false, ''),
  ('Phase2', 'billing_webhook_events', 'fingerprint', 'text', false, ''),
  ('Phase2', 'billing_webhook_events', 'lease_token', 'uuid', false, ''),
  ('Phase2', 'billing_subscriptions', 'projected_plan', 'text', false, ''),
  ('Phase2', 'billing_subscriptions', 'projected_status', 'text', false, ''),
  ('Phase2', 'billing_subscriptions', 'projected_reason', 'text', false, '')
)
select '02_columns' as section, e.*, c.relkind,
 format_type(a.atttypid,a.atttypmod) as actual_type, a.attnotnull as actual_not_null,
 pg_get_expr(d.adbin,d.adrelid) as actual_default,
 case when c.oid is null then 'MISSING_TABLE'
      when c.relkind not in ('r','p') then 'BLOCK_NOT_A_TABLE'
      when a.attnum is null then 'MISSING_COLUMN'
      when a.atttypid <> to_regtype(e.type_name) or a.atttypmod <> -1 then 'BLOCK_TYPE_MISMATCH'
      when a.attnotnull <> e.not_null then 'REVIEW_NULLABILITY'
      when a.attgenerated <> '' or a.attidentity <> '' then 'BLOCK_GENERATED_OR_IDENTITY'
      else 'TYPE_NULLABILITY_OK_CHECK_DEFAULT' end as result
from expected e
left join pg_class c on c.oid = to_regclass('public.' || e.table_name)
left join pg_attribute a on a.attrelid = c.oid and a.attname = e.column_name and not a.attisdropped
left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
order by e.table_name,e.stage,e.column_name;

-- Includes EXTRA columns that could introduce non-null insert failures.
select '02_all_columns' as section, c.relname as table_name, a.attname as column_name,
 format_type(a.atttypid,a.atttypmod) as data_type, a.attnotnull,
 pg_get_expr(d.adbin,d.adrelid) as default_sql, a.attgenerated, a.attidentity
from pg_class c join pg_namespace n on n.oid = c.relnamespace
join pg_attribute a on a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
where n.nspname = 'public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements')
order by c.relname,a.attnum;

-- 03. Constraints/indexes, including auth.users PK needed by new FKs.
select '03_constraints' as section, n.nspname, c.relname, co.conname,
 co.contype, co.convalidated, co.condeferrable, co.condeferred,
 pg_get_constraintdef(co.oid) as definition
from pg_constraint co join pg_class c on c.oid = co.conrelid
join pg_namespace n on n.oid = c.relnamespace
where (n.nspname='public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements'))
 or (n.nspname='auth' and c.relname='users' and co.contype='p')
order by n.nspname,c.relname,co.conname;
select '03_indexes' as section, c.relname, i.relname as index_name,
 x.indisvalid, x.indisready, x.indisunique, pg_get_indexdef(x.indexrelid) as definition
from pg_index x join pg_class c on c.oid=x.indrelid
join pg_namespace n on n.oid=c.relnamespace join pg_class i on i.oid=x.indexrelid
where n.nspname='public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements');

-- Named index collisions can exist even when the expected table is absent.
with expected(name,table_name) as (values
 ('billing_customers_pkey','billing_customers'),
 ('billing_customers_stripe_customer_id_key','billing_customers'),
 ('billing_subscriptions_pkey','billing_subscriptions'),
 ('billing_subscriptions_user_idx','billing_subscriptions'),
 ('billing_webhook_events_pkey','billing_webhook_events'),
 ('billing_entitlements_pkey','billing_entitlements')
)
select '03_named_index_collisions' as section, e.*, c.relkind,
 case when c.oid is null then 'ABSENT'
 when c.relkind not in ('i','I') or x.indrelid is distinct from to_regclass('public.'||e.table_name)
 then 'BLOCK_NAME_COLLISION' else 'CHECK_INDEX_DEFINITION' end as result
from expected e left join pg_class c on c.oid=to_regclass('public.'||e.name)
left join pg_index x on x.indexrelid=c.oid;

-- 04. RLS, all policies, and effective permissions (including inherited grants).
select '04_rls' as section, c.relname, c.relkind, c.relrowsecurity, c.relforcerowsecurity,
 pg_get_userbyid(c.relowner) as owner, c.relacl,
 pg_has_role(current_user,c.relowner,'USAGE') as inspector_has_owner_role
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements');
select '04_policies' as section, tablename, policyname, permissive, roles, cmd, qual, with_check
from pg_policies where schemaname='public' and tablename in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements');
select '04_privileges' as section, r.rolname, c.relname,
 has_table_privilege(r.oid,c.oid,'SELECT') as can_select,
 has_table_privilege(r.oid,c.oid,'INSERT') as can_insert,
 has_table_privilege(r.oid,c.oid,'UPDATE') as can_update,
 has_table_privilege(r.oid,c.oid,'DELETE') as can_delete,
 has_table_privilege(r.oid,c.oid,'TRUNCATE') as can_truncate,
 has_table_privilege(r.oid,c.oid,'REFERENCES') as can_reference,
 has_table_privilege(r.oid,c.oid,'TRIGGER') as can_trigger,
 has_any_column_privilege(r.oid,c.oid,'SELECT') as any_column_select,
 has_any_column_privilege(r.oid,c.oid,'INSERT') as any_column_insert,
 has_any_column_privilege(r.oid,c.oid,'UPDATE') as any_column_update
from pg_roles r cross join pg_class c join pg_namespace n on n.oid=c.relnamespace
where r.rolname in ('anon','authenticated','service_role') and n.nspname='public'
 and c.relname in ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements')
 and c.relkind in ('r','p');

-- 05. Expected RPC signatures/returns; missing functions do not cause errors.
with expected(signature,returns,stage,expected_body_md5) as (values
 ('public.billing_claim_webhook_event(text,text,bigint,jsonb)','text','M2','b4f52182bcdea8f3788573518f6edb46'),
 ('public.billing_apply_subscription(uuid,text,text,text,text,text,timestamptz,boolean,timestamptz,text,bigint)','boolean','M2','4cf495e6eb0ee1f90aaf491d624f13e6'),
 ('public.billing_save_entitlement(uuid,text,text,timestamptz,text,text,bigint,text)','void','M2','05968934ef5c8d6da326ef46b4fa69f6'),
 ('public.billing_preserve_customer_owner()','trigger','Phase1','6f3c5c44b88f05d33c6555756e59a84e'),
 ('public.music_billing_claim_delivery(text,text,bigint,text,text,jsonb)','text','Phase2','a3d1ae0d475d521615100ac99b3600d5'),
 ('public.music_billing_complete_delivery(text,uuid,jsonb,jsonb)','void','Phase2','aa0a9234f0c0caf9e570974c4cf5c4f5'),
 ('public.music_billing_fail_delivery(text,uuid)','void','Phase2','c98fc06e03aeaaf1feffdb569d7163ed')
)
select '05_expected_rpcs' as section, e.*, p.oid is not null as exists,
 case when p.oid is not null then pg_get_function_result(p.oid) end as actual_returns,
 p.prosecdef as security_definer, p.proconfig as settings,
 md5(p.prosrc) as actual_body_md5,
 case when p.oid is null then 'MISSING' when md5(p.prosrc)=e.expected_body_md5
  then 'EXACT_SOURCE_MATCH' else 'REVIEW_CHANGED_DEFINITION' end as body_result,
 pg_get_userbyid(p.proowner) as owner
from expected e left join pg_proc p on p.oid=to_regprocedure(e.signature);
-- Includes unexpected overloads that could retain client execution privileges.
select '05_all_rpc_permissions' as section, p.proname,
 pg_get_function_identity_arguments(p.oid) as arguments,
 pg_get_function_result(p.oid) as returns, l.lanname, p.prosecdef, p.proconfig, p.proacl,
 md5(p.prosrc) as body_md5, r.rolname,
 has_function_privilege(r.oid,p.oid,'EXECUTE') as effective_execute
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
join pg_language l on l.oid=p.prolang cross join pg_roles r
where n.nspname='public' and (p.proname like 'billing\_%' escape '\'
 or p.proname like 'music\_billing\_%' escape '\')
 and r.rolname in ('anon','authenticated','service_role')
order by p.proname,arguments,r.rolname;
-- Explicit PUBLIC function ACL entries (default PUBLIC execute included).
select '05_public_rpc_acl' as section, p.proname,
 pg_get_function_identity_arguments(p.oid) as arguments, a.privilege_type, a.is_grantable
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
cross join lateral aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
where n.nspname='public' and a.grantee=0 and
 (p.proname like 'billing\_%' escape '\' or p.proname like 'music\_billing\_%' escape '\');

-- 06. Triggers/dependencies; definitions are metadata, never invoked here.
select '06_triggers' as section, c.relname, t.tgname, t.tgenabled,
 pg_get_triggerdef(t.oid) as definition
from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements') and not t.tgisinternal;
select distinct '06_dependencies' as section, c.relname as referenced_table,
 d.deptype, pg_describe_object(d.classid,d.objid,d.objsubid) as dependent_object
from pg_depend d join pg_class c on c.oid=d.refobjid
join pg_namespace n on n.oid=c.relnamespace
where d.refclassid='pg_class'::regclass and n.nspname='public' and c.relname in
 ('billing_customers','billing_subscriptions','billing_webhook_events','billing_entitlements')
order by referenced_table,dependent_object;

-- 07. Migration history: presence only, no SQL statements, operator names or data.
-- Eight-digit local version prefixes: absent history is UNKNOWN, not unapplied.
with expected(version) as (values ('20260927'),('20261111'),('20261112'))
select '07_migration_history' as section, version,
 case when to_regclass('supabase_migrations.schema_migrations') is null then 'UNKNOWN_NO_HISTORY'
 when not exists (select 1 from pg_attribute where attrelid=to_regclass('supabase_migrations.schema_migrations')
   and attname='version' and not attisdropped) then 'UNKNOWN_HISTORY_LAYOUT'
 else case when ((xpath('/table/row/n/text()', query_to_xml(
   format('select count(*) as n from supabase_migrations.schema_migrations where version::text = %L',version),
   false,false,'')))[1]::text)::bigint > 0 then 'VERSION_PRESENT_VERIFY_SCHEMA' else 'VERSION_NOT_RECORDED' end
 end as result from expected;

-- 08. Guarded aggregate scans follow; fixed SELECT-only SQL is the entire dynamic surface.
-- RLS/permission failures or timeout must be reviewed, never interpreted as zero.
with checks(label,requirements,sql_text) as (values
 ('customer_integrity', ARRAY['public.billing_customers.app_user_id:uuid','public.billing_customers.stripe_customer_id:text','auth.users.id:uuid'], $scan$select jsonb_build_object(
 'rows',count(*),
 'duplicate_user_rows',count(c.app_user_id)-count(distinct c.app_user_id),
 'duplicate_customer_rows',count(c.stripe_customer_id)-count(distinct c.stripe_customer_id),
 'null_users',count(*) filter(where c.app_user_id is null),
 'empty_customer_ids',count(*) filter(where nullif(btrim(c.stripe_customer_id),'') is null),
 'invalid_customer_prefix',count(*) filter(where left(c.stripe_customer_id,4) <> 'cus_' or length(c.stripe_customer_id) <= 4),
 'users_missing_from_auth',count(*) filter(where u.id is null)
) as metrics from public.billing_customers c left join auth.users u on u.id=c.app_user_id$scan$),
 ('subscription_integrity', ARRAY['public.billing_subscriptions.stripe_subscription_id:text','public.billing_subscriptions.app_user_id:uuid','public.billing_subscriptions.stripe_customer_id:text','public.billing_subscriptions.provider_status:text','public.billing_subscriptions.current_period_end:timestamptz','public.billing_subscriptions.cancel_at_period_end:bool','public.billing_customers.stripe_customer_id:text','public.billing_customers.app_user_id:uuid','auth.users.id:uuid'], $scan$select jsonb_build_object(
 'rows',count(*),
 'duplicate_subscription_rows',count(s.stripe_subscription_id)-count(distinct s.stripe_subscription_id),
 'empty_subscription_ids',count(*) filter(where nullif(btrim(s.stripe_subscription_id),'') is null),
 'users_missing_from_auth',count(*) filter(where u.id is null),
 'unmapped_customers',count(*) filter(where c.stripe_customer_id is null),
 'owner_mismatch',count(*) filter(where c.stripe_customer_id is not null and c.app_user_id is distinct from s.app_user_id),
 'null_or_unknown_provider_status',count(*) filter(where s.provider_status is null or s.provider_status not in
 ('active','trialing','past_due','canceled','unpaid','incomplete','incomplete_expired','paused')),
 'paid_status_without_end',count(*) filter(where s.provider_status in ('active','trialing') and s.current_period_end is null),
 'paid_status_past_end',count(*) filter(where s.provider_status in ('active','trialing') and s.current_period_end <= current_timestamp),
 'scheduled_cancellations',count(*) filter(where s.cancel_at_period_end),
 'users_with_multiple_paid_subscriptions',(select count(*) from
  (select app_user_id from public.billing_subscriptions where provider_status in ('active','trialing')
   and current_period_end > current_timestamp group by app_user_id having count(*) > 1) multi)
) as metrics from public.billing_subscriptions s
left join public.billing_customers c on c.stripe_customer_id=s.stripe_customer_id
left join auth.users u on u.id=s.app_user_id$scan$),
 ('entitlement_integrity', ARRAY['public.billing_entitlements.app_user_id:uuid','public.billing_entitlements.plan:text','public.billing_entitlements.status:text','public.billing_entitlements.current_period_end:timestamptz','public.billing_entitlements.source_subscription_id:text','public.billing_subscriptions.stripe_subscription_id:text','public.billing_subscriptions.app_user_id:uuid','auth.users.id:uuid'], $scan$select jsonb_build_object(
 'rows',count(*),
 'duplicate_user_rows',count(e.app_user_id)-count(distinct e.app_user_id),
 'users_missing_from_auth',count(*) filter(where u.id is null),
 'invalid_plans',count(*) filter(where e.plan is null or e.plan not in ('free','pro')),
 'paid_status_conflicts',count(*) filter(where e.plan='pro' and
  (e.status is null or e.status not in ('active','trialing','canceled_period_end'))),
 'pro_missing_period_end',count(*) filter(where e.plan='pro' and e.current_period_end is null),
 'pro_past_period_end',count(*) filter(where e.plan='pro' and e.current_period_end <= current_timestamp),
 'missing_source_subscription',count(*) filter(where nullif(e.source_subscription_id,'') is not null and s.stripe_subscription_id is null),
 'source_owner_mismatch',count(*) filter(where s.stripe_subscription_id is not null and s.app_user_id is distinct from e.app_user_id)
) as metrics from public.billing_entitlements e
left join public.billing_subscriptions s on s.stripe_subscription_id=e.source_subscription_id
left join auth.users u on u.id=e.app_user_id$scan$),
 ('webhook_integrity', ARRAY['public.billing_webhook_events.stripe_event_id:text','public.billing_webhook_events.processing_state:text','public.billing_webhook_events.payload:jsonb','public.billing_webhook_events.attempt_count:int4','public.billing_webhook_events.updated_at:timestamptz'], $scan$select jsonb_build_object(
 'rows',count(*),
 'duplicate_event_rows',count(stripe_event_id)-count(distinct stripe_event_id),
 'invalid_states',count(*) filter(where processing_state is null or processing_state not in ('processing','processed','failed')),
 'failed_events',count(*) filter(where processing_state='failed'),
 'processing_events',count(*) filter(where processing_state='processing'),
 'stale_processing_events',count(*) filter(where processing_state='processing' and updated_at < current_timestamp-interval '5 minutes'),
 'invalid_attempts',count(*) filter(where attempt_count is null or attempt_count < 1),
 'payload_id_conflicts',count(*) filter(where payload ? 'id' and payload->>'id' is distinct from stripe_event_id)
) as metrics from public.billing_webhook_events$scan$),
 ('phase2_customer_leases', ARRAY['public.billing_customers.reconciliation_token:uuid','public.billing_customers.reconciliation_expires:timestamptz'], $scan$select jsonb_build_object(
 'active_leases',count(*) filter(where reconciliation_token is not null and reconciliation_expires > current_timestamp),
 'expired_leases',count(*) filter(where reconciliation_token is not null and reconciliation_expires <= current_timestamp),
 'incomplete_lease_pairs',count(*) filter(where (reconciliation_token is null) <> (reconciliation_expires is null))
) as metrics from public.billing_customers$scan$),
 ('phase2_projection_backfill', ARRAY['public.billing_subscriptions.projected_plan:text','public.billing_subscriptions.projected_status:text','public.billing_subscriptions.projected_reason:text'], $scan$select jsonb_build_object(
 'unprojected_subscriptions',count(*) filter(where projected_plan is null),
 'invalid_projected_plans',count(*) filter(where projected_plan is not null and projected_plan not in ('free','pro')),
 'partial_projections',count(*) filter(where projected_plan is not null and (projected_status is null or projected_reason is null))
) as metrics from public.billing_subscriptions$scan$),
 ('phase2_event_fingerprints', ARRAY['public.billing_webhook_events.fingerprint:text','public.billing_webhook_events.lease_token:uuid','public.billing_webhook_events.processing_state:text','public.billing_webhook_events.payload:jsonb'], $scan$select jsonb_build_object(
 'legacy_events_without_fingerprint',count(*) filter(where fingerprint is null),
 'legacy_events_without_original_envelope',count(*) filter(where fingerprint is null and not coalesce(payload ? 'id',false)),
 'completed_events_with_lease_token',count(*) filter(where processing_state='processed' and lease_token is not null)
) as metrics from public.billing_webhook_events$scan$)
), guarded as (
 select *, not exists (
  select 1 from unnest(requirements) req
  left join pg_class c on c.oid=to_regclass(split_part(req,'.',1)||'.'||split_part(req,'.',2))
  left join pg_attribute a on a.attrelid=c.oid
   and a.attname=split_part(split_part(req,'.',3),':',1) and not a.attisdropped
  where c.oid is null or c.relkind not in ('r','p') or a.attnum is null
   or a.atttypid <> to_regtype(split_part(req,':',2))
 ) as compatible
 from checks
)
select '08_aggregate_integrity' as section, label,
 case when compatible then 'SCANNED' else 'SKIPPED_MISSING_OR_INCOMPATIBLE_SCHEMA' end as result,
 case when compatible then ((xpath('/table/row/metrics/text()',
  query_to_xml(sql_text,false,false,'')))[1]::text)::jsonb end as counts
from guarded order by label;

-- SHARED 09: protected objects and proposed Music namespace. No rows selected.
with expected(schema_name,object_name,purpose) as (values
 ('public','subscriptions','PROTECTED_BASEBALL'),
 ('private','baseball_billing_webhook_events','PROTECTED_BASEBALL'),
 ('private','baseball_billing_subscription_versions','PROTECTED_BASEBALL'),
 ('private','baseball_auth_project_billing_install','PROTECTED_BASEBALL_UNKNOWN_MARKER'),
 ('public','suite_users','PROTECTED_SUITE'),
 ('public','suite_activity_events','PROTECTED_SUITE'),
 ('public','suite_app_current_state','PROTECTED_SUITE'),
 ('auth','users','PROTECTED_AUTH'),
 ('public','music_billing_customers','PROPOSED_MUSIC'),
 ('public','music_billing_subscriptions','PROPOSED_MUSIC'),
 ('public','music_billing_webhook_events','PROPOSED_MUSIC'),
 ('public','music_billing_entitlements','PROPOSED_MUSIC')
)
select '09_shared_objects' as section,e.*,c.oid is not null as object_exists,
 c.relkind,c.relrowsecurity,c.relforcerowsecurity,c.reltuples as estimated_rows,
 pg_get_userbyid(c.relowner) as owner,c.relacl,
 case when c.oid is null and purpose='PROPOSED_MUSIC' then 'NAME_AVAILABLE_VERIFY_DEPENDENCIES'
 when c.oid is not null and purpose='PROPOSED_MUSIC' then 'STOP_REVIEW_EXISTING_OBJECT'
 when c.oid is null then 'STOP_EXPECTED_SHARED_OBJECT_MISSING'
 else 'PRESERVE' end as review
from expected e left join pg_class c on c.oid=to_regclass(format('%I.%I',schema_name,object_name));

-- All shared protected columns including the install marker: metadata only.
select '10_shared_columns' as section,n.nspname,c.relname,a.attname,
 format_type(a.atttypid,a.atttypmod) as type,a.attnotnull,
 pg_get_expr(d.adbin,d.adrelid) as default_sql
from pg_class c join pg_namespace n on n.oid=c.relnamespace
join pg_attribute a on a.attrelid=c.oid and a.attnum>0 and not a.attisdropped
left join pg_attrdef d on d.adrelid=a.attrelid and d.adnum=a.attnum
where (n.nspname='public' and c.relname in
 ('subscriptions','suite_users','suite_activity_events','suite_app_current_state'))
 or (n.nspname='private' and c.relname in
 ('baseball_billing_webhook_events','baseball_billing_subscription_versions','baseball_auth_project_billing_install'))
order by n.nspname,c.relname,a.attnum;
select '10_shared_constraints' as section,n.nspname,c.relname,co.conname,
 co.convalidated,pg_get_constraintdef(co.oid) as definition
from pg_constraint co join pg_class c on c.oid=co.conrelid
join pg_namespace n on n.oid=c.relnamespace
where (n.nspname='public' and c.relname in
 ('subscriptions','suite_users','suite_activity_events','suite_app_current_state'))
 or (n.nspname='private' and c.relname like 'baseball\_%' escape '\');

select '11_shared_policies' as section,schemaname,tablename,policyname,
 permissive,roles,cmd,qual,with_check
from pg_policies where (schemaname='public' and tablename in
 ('subscriptions','suite_users','suite_activity_events','suite_app_current_state'))
 or (schemaname='private' and tablename like 'baseball\_%' escape '\');
select '11_shared_effective_access' as section,r.rolname,n.nspname,c.relname,
 has_schema_privilege(r.oid,n.oid,'USAGE') as schema_usage,
 has_table_privilege(r.oid,c.oid,'SELECT') as can_select,
 has_table_privilege(r.oid,c.oid,'INSERT') as can_insert,
 has_table_privilege(r.oid,c.oid,'UPDATE') as can_update,
 has_table_privilege(r.oid,c.oid,'DELETE') as can_delete,
 has_table_privilege(r.oid,c.oid,'TRUNCATE') as can_truncate,
 has_any_column_privilege(r.oid,c.oid,'UPDATE') as any_column_update
from pg_roles r cross join pg_class c join pg_namespace n on n.oid=c.relnamespace
where r.rolname in ('anon','authenticated','service_role') and c.relkind in ('r','p') and
 ((n.nspname='public' and c.relname in
 ('subscriptions','suite_users','suite_activity_events','suite_app_current_state'))
 or (n.nspname='private' and c.relname like 'baseball\_%' escape '\'));

-- Default grants and inherited role privileges affect future Music tables/functions.
select '12_default_acl' as section,pg_get_userbyid(d.defaclrole) as creator_role,
 coalesce(n.nspname,'ALL_SCHEMAS') as schema_name,d.defaclobjtype,d.defaclacl
from pg_default_acl d left join pg_namespace n on n.oid=d.defaclnamespace
where d.defaclnamespace=0 or n.nspname in ('public','private');
select '12_memberships' as section,parent.rolname as inherited_role,child.rolname as member_role,
 m.admin_option
from pg_auth_members m join pg_roles parent on parent.oid=m.roleid
join pg_roles child on child.oid=m.member
where parent.rolname in ('anon','authenticated','service_role')
 or child.rolname in ('anon','authenticated','service_role');

-- Definition hashes/flags only. No function source, marker contents or identities.
-- Include every public/private definer function: unexpected RPCs can cross app boundaries.
select '13_function_boundary' as section,n.nspname,p.proname,
 pg_get_function_identity_arguments(p.oid) as arguments,p.prosecdef,p.proconfig,p.proacl,
 pg_get_userbyid(p.proowner) as owner,md5(p.prosrc) as body_md5,
 (p.prosrc ilike '%subscriptions%') as mentions_subscriptions,
 (p.prosrc ilike '%suite_%') as mentions_suite,
 (p.prosrc ilike '%billing_%') as mentions_billing,
 r.rolname,has_function_privilege(r.oid,p.oid,'EXECUTE') as effective_execute
from pg_proc p join pg_namespace n on n.oid=p.pronamespace cross join pg_roles r
where n.nspname in ('public','private') and p.prokind='f'
 and (p.prosecdef or p.proname like 'baseball\_%' escape '\'
  or p.proname like 'billing\_%' escape '\' or p.proname like 'music\_billing\_%' escape '\')
 and r.rolname in ('anon','authenticated','service_role')
order by n.nspname,p.proname,arguments,r.rolname;

-- Auth signup triggers can already create Baseball rows for all Suite users.
-- Preserve definitions and review them before registering synthetic test accounts.
select '14_shared_triggers' as section,n.nspname,c.relname,t.tgname,t.tgenabled,
 pg_get_triggerdef(t.oid) as definition,p.proname as function_name,
 pn.nspname as function_schema,md5(p.prosrc) as function_body_md5
from pg_trigger t join pg_class c on c.oid=t.tgrelid
join pg_namespace n on n.oid=c.relnamespace join pg_proc p on p.oid=t.tgfoid
join pg_namespace pn on pn.oid=p.pronamespace
where not t.tgisinternal and ((n.nspname='auth' and c.relname='users')
 or (n.nspname='public' and c.relname in
 ('subscriptions','suite_users','suite_activity_events','suite_app_current_state')));

-- Aggregate-only baseline for all seven confirmed shared tables.
with expected(schema_name,table_name) as (values
 ('public','subscriptions'),('private','baseball_billing_webhook_events'),
 ('private','baseball_billing_subscription_versions'),('private','baseball_auth_project_billing_install'),
 ('public','suite_users'),('public','suite_activity_events'),('public','suite_app_current_state')
)
select '15_shared_row_counts' as section,e.*,
 case when c.relkind in ('r','p') then 'SCANNED_ADMIN_VISIBILITY_REQUIRED'
 else 'SKIPPED_MISSING_OR_NON_TABLE' end as result,
 case when c.relkind in ('r','p') then ((xpath('/table/row/n/text()',
 query_to_xml(format('select count(*) as n from %I.%I',schema_name,table_name),false,false,'')))[1]::text)::bigint end as rows
from expected e left join pg_class c on c.oid=to_regclass(format('%I.%I',schema_name,table_name));
rollback;
