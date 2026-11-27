-- Shared Suite project qhprdlwoxjpkiukxhftp: SINGLE-GRID, READ-ONLY EXPORT.
-- Companion to music_billing_shared_suite_preflight.sql; same 27 inspection queries.
-- Confirm the intended project in the dashboard. Run this ENTIRE file once.
-- Expected result: exactly 27 rows, one per inspection block spanning sections 01-15.
-- Export that ONE result grid as CSV. findings is a JSON array within each CSV cell.
-- Empty sections remain visible as row_count=0 and findings=[]; missing evidence is
-- not silently dropped. SKIPPED in findings remains unresolved, not a passing check.
-- No billing RPC is invoked; no DDL/DML, identities, keys or row contents returned.
-- PostgreSQL 12+ required for MATERIALIZED CTEs. Entire statement has a 15s timeout.
begin transaction isolation level repeatable read read only;
set local statement_timeout = '15s';
set local lock_timeout = '3s';
WITH
-- 01_context
inspection_01 AS MATERIALIZED (
SELECT '01_context' AS section, CURRENT_USER AS inspection_role, current_setting('server_version') AS postgres_version, current_setting('transaction_read_only') AS must_be_on, (SELECT rolsuper FROM pg_roles WHERE rolname = CURRENT_USER) AS inspector_is_superuser, (SELECT rolbypassrls FROM pg_roles WHERE rolname = CURRENT_USER) AS inspector_bypasses_rls, current_setting('transaction_isolation') AS snapshot_isolation, to_regclass('auth.users') IS NOT NULL AS auth_users_exists, to_regprocedure('auth.uid()') IS NOT NULL AS auth_uid_exists, to_regprocedure('gen_random_uuid()') IS NOT NULL AS uuid_function_exists, to_regprocedure('pg_catalog.hashtextextended(text,bigint)') IS NOT NULL AS hash_function_exists, to_regprocedure('pg_catalog.pg_advisory_xact_lock(bigint)') IS NOT NULL AS advisory_lock_exists, to_regprocedure('pg_catalog.jsonb_populate_record(anyelement,jsonb)') IS NOT NULL AS populate_record_exists, has_schema_privilege(CURRENT_USER, 'public', 'CREATE') AS inspector_can_create_public
),
-- 01_roles
inspection_02 AS MATERIALIZED (
SELECT '01_roles' AS section, expected.role_name, r.oid IS NOT NULL AS role_exists, r.rolsuper, r.rolbypassrls, CASE WHEN r.oid IS NOT NULL THEN has_schema_privilege(r.oid, 'public', 'CREATE') END AS create_public, CASE WHEN r.oid IS NOT NULL THEN has_schema_privilege(r.oid, 'public', 'USAGE') END AS use_public FROM ((VALUES ('anon'), ('authenticated'), ('service_role'))) AS expected (role_name) LEFT JOIN pg_roles AS r ON r.rolname = expected.role_name
),
-- 02_columns
inspection_03 AS MATERIALIZED (
WITH expected(stage, table_name, column_name, type_name, not_null, default_sql) AS (VALUES ('M2', 'billing_customers', 'app_user_id', 'uuid', TRUE, ''), ('M2', 'billing_customers', 'stripe_customer_id', 'text', TRUE, ''), ('M2', 'billing_customers', 'email', 'text', FALSE, ''), ('M2', 'billing_customers', 'created_at', 'timestamptz', TRUE, 'now()'), ('M2', 'billing_customers', 'updated_at', 'timestamptz', TRUE, 'now()'), ('M2', 'billing_subscriptions', 'stripe_subscription_id', 'text', TRUE, ''), ('M2', 'billing_subscriptions', 'app_user_id', 'uuid', TRUE, ''), ('M2', 'billing_subscriptions', 'stripe_customer_id', 'text', TRUE, ''), ('M2', 'billing_subscriptions', 'stripe_product_id', 'text', FALSE, ''), ('M2', 'billing_subscriptions', 'stripe_price_id', 'text', FALSE, ''), ('M2', 'billing_subscriptions', 'provider_status', 'text', TRUE, ''), ('M2', 'billing_subscriptions', 'current_period_end', 'timestamptz', FALSE, ''), ('M2', 'billing_subscriptions', 'cancel_at_period_end', 'boolean', TRUE, 'FALSE'), ('M2', 'billing_subscriptions', 'trial_end', 'timestamptz', FALSE, ''), ('M2', 'billing_subscriptions', 'latest_event_id', 'text', TRUE, ''), ('M2', 'billing_subscriptions', 'latest_event_created', 'bigint', TRUE, ''), ('M2', 'billing_subscriptions', 'created_at', 'timestamptz', TRUE, 'now()'), ('M2', 'billing_subscriptions', 'updated_at', 'timestamptz', TRUE, 'now()'), ('M2', 'billing_webhook_events', 'stripe_event_id', 'text', TRUE, ''), ('M2', 'billing_webhook_events', 'event_type', 'text', TRUE, ''), ('M2', 'billing_webhook_events', 'event_created', 'bigint', TRUE, ''), ('M2', 'billing_webhook_events', 'payload', 'jsonb', TRUE, ''), ('M2', 'billing_webhook_events', 'processing_state', 'text', TRUE, ''), ('M2', 'billing_webhook_events', 'attempt_count', 'integer', TRUE, '1'), ('M2', 'billing_webhook_events', 'last_error', 'text', FALSE, ''), ('M2', 'billing_webhook_events', 'received_at', 'timestamptz', TRUE, 'now()'), ('M2', 'billing_webhook_events', 'processed_at', 'timestamptz', FALSE, ''), ('M2', 'billing_webhook_events', 'updated_at', 'timestamptz', TRUE, 'now()'), ('M2', 'billing_entitlements', 'app_user_id', 'uuid', TRUE, ''), ('M2', 'billing_entitlements', 'plan', 'text', TRUE, ''), ('M2', 'billing_entitlements', 'status', 'text', TRUE, ''), ('M2', 'billing_entitlements', 'current_period_end', 'timestamptz', FALSE, ''), ('M2', 'billing_entitlements', 'source_subscription_id', 'text', FALSE, ''), ('M2', 'billing_entitlements', 'source_event_id', 'text', TRUE, ''), ('M2', 'billing_entitlements', 'source_event_created', 'bigint', TRUE, ''), ('M2', 'billing_entitlements', 'reason', 'text', TRUE, ''), ('M2', 'billing_entitlements', 'updated_at', 'timestamptz', TRUE, 'now()'), ('Phase2', 'billing_customers', 'reconciliation_token', 'uuid', FALSE, ''), ('Phase2', 'billing_customers', 'reconciliation_expires', 'timestamptz', FALSE, ''), ('Phase2', 'billing_webhook_events', 'fingerprint', 'text', FALSE, ''), ('Phase2', 'billing_webhook_events', 'lease_token', 'uuid', FALSE, ''), ('Phase2', 'billing_subscriptions', 'projected_plan', 'text', FALSE, ''), ('Phase2', 'billing_subscriptions', 'projected_status', 'text', FALSE, ''), ('Phase2', 'billing_subscriptions', 'projected_reason', 'text', FALSE, '')) SELECT '02_columns' AS section, e.*, c.relkind, format_type(a.atttypid, a.atttypmod) AS actual_type, a.attnotnull AS actual_not_null, pg_get_expr(d.adbin, d.adrelid) AS actual_default, CASE WHEN c.oid IS NULL THEN 'MISSING_TABLE' WHEN c.relkind NOT IN ('r', 'p') THEN 'BLOCK_NOT_A_TABLE' WHEN a.attnum IS NULL THEN 'MISSING_COLUMN' WHEN a.atttypid <> to_regtype(e.type_name) OR a.atttypmod <> -1 THEN 'BLOCK_TYPE_MISMATCH' WHEN a.attnotnull <> e.not_null THEN 'REVIEW_NULLABILITY' WHEN a.attgenerated <> '' OR a.attidentity <> '' THEN 'BLOCK_GENERATED_OR_IDENTITY' ELSE 'TYPE_NULLABILITY_OK_CHECK_DEFAULT' END AS result FROM expected AS e LEFT JOIN pg_class AS c ON c.oid = to_regclass('public.' || e.table_name) LEFT JOIN pg_attribute AS a ON a.attrelid = c.oid AND a.attname = e.column_name AND NOT a.attisdropped LEFT JOIN pg_attrdef AS d ON d.adrelid = a.attrelid AND d.adnum = a.attnum ORDER BY e.table_name, e.stage, e.column_name
),
-- 02_all_columns
inspection_04 AS MATERIALIZED (
SELECT '02_all_columns' AS section, c.relname AS table_name, a.attname AS column_name, format_type(a.atttypid, a.atttypmod) AS data_type, a.attnotnull, pg_get_expr(d.adbin, d.adrelid) AS default_sql, a.attgenerated, a.attidentity FROM pg_class AS c INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace INNER JOIN pg_attribute AS a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped LEFT JOIN pg_attrdef AS d ON d.adrelid = a.attrelid AND d.adnum = a.attnum WHERE n.nspname = 'public' AND c.relname IN ('billing_customers', 'billing_subscriptions', 'billing_webhook_events', 'billing_entitlements') ORDER BY c.relname, a.attnum
),
-- 03_constraints
inspection_05 AS MATERIALIZED (
SELECT '03_constraints' AS section, n.nspname, c.relname, co.conname, co.contype, co.convalidated, co.condeferrable, co.condeferred, pg_get_constraintdef(co.oid) AS definition FROM pg_constraint AS co INNER JOIN pg_class AS c ON c.oid = co.conrelid INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE (n.nspname = 'public' AND c.relname IN ('billing_customers', 'billing_subscriptions', 'billing_webhook_events', 'billing_entitlements')) OR (n.nspname = 'auth' AND c.relname = 'users' AND co.contype = 'p') ORDER BY n.nspname, c.relname, co.conname
),
-- 03_indexes
inspection_06 AS MATERIALIZED (
SELECT '03_indexes' AS section, c.relname, i.relname AS index_name, x.indisvalid, x.indisready, x.indisunique, pg_get_indexdef(x.indexrelid) AS definition FROM pg_index AS x INNER JOIN pg_class AS c ON c.oid = x.indrelid INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace INNER JOIN pg_class AS i ON i.oid = x.indexrelid WHERE n.nspname = 'public' AND c.relname IN ('billing_customers', 'billing_subscriptions', 'billing_webhook_events', 'billing_entitlements')
),
-- 03_named_index_collisions
inspection_07 AS MATERIALIZED (
WITH expected(name, table_name) AS (VALUES ('billing_customers_pkey', 'billing_customers'), ('billing_customers_stripe_customer_id_key', 'billing_customers'), ('billing_subscriptions_pkey', 'billing_subscriptions'), ('billing_subscriptions_user_idx', 'billing_subscriptions'), ('billing_webhook_events_pkey', 'billing_webhook_events'), ('billing_entitlements_pkey', 'billing_entitlements')) SELECT '03_named_index_collisions' AS section, e.*, c.relkind, CASE WHEN c.oid IS NULL THEN 'ABSENT' WHEN c.relkind NOT IN ('i', 'I') OR x.indrelid IS DISTINCT FROM to_regclass('public.' || e.table_name) THEN 'BLOCK_NAME_COLLISION' ELSE 'CHECK_INDEX_DEFINITION' END AS result FROM expected AS e LEFT JOIN pg_class AS c ON c.oid = to_regclass('public.' || e.name) LEFT JOIN pg_index AS x ON x.indexrelid = c.oid
),
-- 04_rls
inspection_08 AS MATERIALIZED (
SELECT '04_rls' AS section, c.relname, c.relkind, c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner) AS owner, c.relacl, pg_has_role(CURRENT_USER, c.relowner, 'USAGE') AS inspector_has_owner_role FROM pg_class AS c INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relname IN ('billing_customers', 'billing_subscriptions', 'billing_webhook_events', 'billing_entitlements')
),
-- 04_policies
inspection_09 AS MATERIALIZED (
SELECT '04_policies' AS section, tablename, policyname, permissive, roles, cmd, qual, with_check FROM pg_policies WHERE schemaname = 'public' AND tablename IN ('billing_customers', 'billing_subscriptions', 'billing_webhook_events', 'billing_entitlements')
),
-- 04_privileges
inspection_10 AS MATERIALIZED (
SELECT '04_privileges' AS section, r.rolname, c.relname, has_table_privilege(r.oid, c.oid, 'SELECT') AS can_select, has_table_privilege(r.oid, c.oid, 'INSERT') AS can_insert, has_table_privilege(r.oid, c.oid, 'UPDATE') AS can_update, has_table_privilege(r.oid, c.oid, 'DELETE') AS can_delete, has_table_privilege(r.oid, c.oid, 'TRUNCATE') AS can_truncate, has_table_privilege(r.oid, c.oid, 'REFERENCES') AS can_reference, has_table_privilege(r.oid, c.oid, 'TRIGGER') AS can_trigger, has_any_column_privilege(r.oid, c.oid, 'SELECT') AS any_column_select, has_any_column_privilege(r.oid, c.oid, 'INSERT') AS any_column_insert, has_any_column_privilege(r.oid, c.oid, 'UPDATE') AS any_column_update FROM pg_roles AS r CROSS JOIN pg_class AS c INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE r.rolname IN ('anon', 'authenticated', 'service_role') AND n.nspname = 'public' AND c.relname IN ('billing_customers', 'billing_subscriptions', 'billing_webhook_events', 'billing_entitlements') AND c.relkind IN ('r', 'p')
),
-- 05_expected_rpcs
inspection_11 AS MATERIALIZED (
WITH expected(signature, returns, stage, expected_body_md5) AS (VALUES ('public.billing_claim_webhook_event(text,text,bigint,jsonb)', 'text', 'M2', 'b4f52182bcdea8f3788573518f6edb46'), ('public.billing_apply_subscription(uuid,text,text,text,text,text,timestamptz,boolean,timestamptz,text,bigint)', 'boolean', 'M2', '4cf495e6eb0ee1f90aaf491d624f13e6'), ('public.billing_save_entitlement(uuid,text,text,timestamptz,text,text,bigint,text)', 'void', 'M2', '05968934ef5c8d6da326ef46b4fa69f6'), ('public.billing_preserve_customer_owner()', 'trigger', 'Phase1', '6f3c5c44b88f05d33c6555756e59a84e'), ('public.music_billing_claim_delivery(text,text,bigint,text,text,jsonb)', 'text', 'Phase2', 'a3d1ae0d475d521615100ac99b3600d5'), ('public.music_billing_complete_delivery(text,uuid,jsonb,jsonb)', 'void', 'Phase2', 'aa0a9234f0c0caf9e570974c4cf5c4f5'), ('public.music_billing_fail_delivery(text,uuid)', 'void', 'Phase2', 'c98fc06e03aeaaf1feffdb569d7163ed')) SELECT '05_expected_rpcs' AS section, e.*, p.oid IS NOT NULL AS exists, CASE WHEN p.oid IS NOT NULL THEN pg_get_function_result(p.oid) END AS actual_returns, p.prosecdef AS security_definer, p.proconfig AS settings, md5(p.prosrc) AS actual_body_md5, CASE WHEN p.oid IS NULL THEN 'MISSING' WHEN md5(p.prosrc) = e.expected_body_md5 THEN 'EXACT_SOURCE_MATCH' ELSE 'REVIEW_CHANGED_DEFINITION' END AS body_result, pg_get_userbyid(p.proowner) AS owner FROM expected AS e LEFT JOIN pg_proc AS p ON p.oid = to_regprocedure(e.signature)
),
-- 05_all_rpc_permissions
inspection_12 AS MATERIALIZED (
SELECT '05_all_rpc_permissions' AS section, p.proname, pg_get_function_identity_arguments(p.oid) AS arguments, pg_get_function_result(p.oid) AS returns, l.lanname, p.prosecdef, p.proconfig, p.proacl, md5(p.prosrc) AS body_md5, r.rolname, has_function_privilege(r.oid, p.oid, 'EXECUTE') AS effective_execute FROM pg_proc AS p INNER JOIN pg_namespace AS n ON n.oid = p.pronamespace INNER JOIN pg_language AS l ON l.oid = p.prolang CROSS JOIN pg_roles AS r WHERE n.nspname = 'public' AND (p.proname LIKE pg_catalog.like_escape('billing\_%', '\') OR p.proname LIKE pg_catalog.like_escape('music\_billing\_%', '\')) AND r.rolname IN ('anon', 'authenticated', 'service_role') ORDER BY p.proname, arguments, r.rolname
),
-- 05_public_rpc_acl
inspection_13 AS MATERIALIZED (
SELECT '05_public_rpc_acl' AS section, p.proname, pg_get_function_identity_arguments(p.oid) AS arguments, a.privilege_type, a.is_grantable FROM pg_proc AS p INNER JOIN pg_namespace AS n ON n.oid = p.pronamespace CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) AS a WHERE n.nspname = 'public' AND a.grantee = 0 AND (p.proname LIKE pg_catalog.like_escape('billing\_%', '\') OR p.proname LIKE pg_catalog.like_escape('music\_billing\_%', '\'))
),
-- 06_triggers
inspection_14 AS MATERIALIZED (
SELECT '06_triggers' AS section, c.relname, t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition FROM pg_trigger AS t INNER JOIN pg_class AS c ON c.oid = t.tgrelid INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relname IN ('billing_customers', 'billing_subscriptions', 'billing_webhook_events', 'billing_entitlements') AND NOT t.tgisinternal
),
-- 06_dependencies
inspection_15 AS MATERIALIZED (
SELECT DISTINCT '06_dependencies' AS section, c.relname AS referenced_table, d.deptype, pg_describe_object(d.classid, d.objid, d.objsubid) AS dependent_object FROM pg_depend AS d INNER JOIN pg_class AS c ON c.oid = d.refobjid INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE d.refclassid = CAST('pg_class' AS regclass) AND n.nspname = 'public' AND c.relname IN ('billing_customers', 'billing_subscriptions', 'billing_webhook_events', 'billing_entitlements') ORDER BY referenced_table, dependent_object
),
-- 07_migration_history
inspection_16 AS MATERIALIZED (
WITH expected(version) AS (VALUES ('20260927'), ('20261111'), ('20261112')) SELECT '07_migration_history' AS section, version, CASE WHEN to_regclass('supabase_migrations.schema_migrations') IS NULL THEN 'UNKNOWN_NO_HISTORY' WHEN NOT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = to_regclass('supabase_migrations.schema_migrations') AND attname = 'version' AND NOT attisdropped) THEN 'UNKNOWN_HISTORY_LAYOUT' ELSE CASE WHEN CAST(CAST(((xpath('/table/row/n/text()', query_to_xml(format('select count(*) as n from supabase_migrations.schema_migrations where version::text = %L', version), FALSE, FALSE, ''))))[1] AS text) AS bigint) > 0 THEN 'VERSION_PRESENT_VERIFY_SCHEMA' ELSE 'VERSION_NOT_RECORDED' END END AS result FROM expected
),
-- 08_aggregate_integrity
inspection_17 AS MATERIALIZED (
WITH checks(label, requirements, sql_text) AS (VALUES ('customer_integrity', ARRAY['public.billing_customers.app_user_id:uuid', 'public.billing_customers.stripe_customer_id:text', 'auth.users.id:uuid'], 'select jsonb_build_object(
 ''rows'',count(*),
 ''duplicate_user_rows'',count(c.app_user_id)-count(distinct c.app_user_id),
 ''duplicate_customer_rows'',count(c.stripe_customer_id)-count(distinct c.stripe_customer_id),
 ''null_users'',count(*) filter(where c.app_user_id is null),
 ''empty_customer_ids'',count(*) filter(where nullif(btrim(c.stripe_customer_id),'''') is null),
 ''invalid_customer_prefix'',count(*) filter(where left(c.stripe_customer_id,4) <> ''cus_'' or length(c.stripe_customer_id) <= 4),
 ''users_missing_from_auth'',count(*) filter(where u.id is null)
) as metrics from public.billing_customers c left join auth.users u on u.id=c.app_user_id'), ('subscription_integrity', ARRAY['public.billing_subscriptions.stripe_subscription_id:text', 'public.billing_subscriptions.app_user_id:uuid', 'public.billing_subscriptions.stripe_customer_id:text', 'public.billing_subscriptions.provider_status:text', 'public.billing_subscriptions.current_period_end:timestamptz', 'public.billing_subscriptions.cancel_at_period_end:bool', 'public.billing_customers.stripe_customer_id:text', 'public.billing_customers.app_user_id:uuid', 'auth.users.id:uuid'], 'select jsonb_build_object(
 ''rows'',count(*),
 ''duplicate_subscription_rows'',count(s.stripe_subscription_id)-count(distinct s.stripe_subscription_id),
 ''empty_subscription_ids'',count(*) filter(where nullif(btrim(s.stripe_subscription_id),'''') is null),
 ''users_missing_from_auth'',count(*) filter(where u.id is null),
 ''unmapped_customers'',count(*) filter(where c.stripe_customer_id is null),
 ''owner_mismatch'',count(*) filter(where c.stripe_customer_id is not null and c.app_user_id is distinct from s.app_user_id),
 ''null_or_unknown_provider_status'',count(*) filter(where s.provider_status is null or s.provider_status not in
 (''active'',''trialing'',''past_due'',''canceled'',''unpaid'',''incomplete'',''incomplete_expired'',''paused'')),
 ''paid_status_without_end'',count(*) filter(where s.provider_status in (''active'',''trialing'') and s.current_period_end is null),
 ''paid_status_past_end'',count(*) filter(where s.provider_status in (''active'',''trialing'') and s.current_period_end <= current_timestamp),
 ''scheduled_cancellations'',count(*) filter(where s.cancel_at_period_end),
 ''users_with_multiple_paid_subscriptions'',(select count(*) from
  (select app_user_id from public.billing_subscriptions where provider_status in (''active'',''trialing'')
   and current_period_end > current_timestamp group by app_user_id having count(*) > 1) multi)
) as metrics from public.billing_subscriptions s
left join public.billing_customers c on c.stripe_customer_id=s.stripe_customer_id
left join auth.users u on u.id=s.app_user_id'), ('entitlement_integrity', ARRAY['public.billing_entitlements.app_user_id:uuid', 'public.billing_entitlements.plan:text', 'public.billing_entitlements.status:text', 'public.billing_entitlements.current_period_end:timestamptz', 'public.billing_entitlements.source_subscription_id:text', 'public.billing_subscriptions.stripe_subscription_id:text', 'public.billing_subscriptions.app_user_id:uuid', 'auth.users.id:uuid'], 'select jsonb_build_object(
 ''rows'',count(*),
 ''duplicate_user_rows'',count(e.app_user_id)-count(distinct e.app_user_id),
 ''users_missing_from_auth'',count(*) filter(where u.id is null),
 ''invalid_plans'',count(*) filter(where e.plan is null or e.plan not in (''free'',''pro'')),
 ''paid_status_conflicts'',count(*) filter(where e.plan=''pro'' and
  (e.status is null or e.status not in (''active'',''trialing'',''canceled_period_end''))),
 ''pro_missing_period_end'',count(*) filter(where e.plan=''pro'' and e.current_period_end is null),
 ''pro_past_period_end'',count(*) filter(where e.plan=''pro'' and e.current_period_end <= current_timestamp),
 ''missing_source_subscription'',count(*) filter(where nullif(e.source_subscription_id,'''') is not null and s.stripe_subscription_id is null),
 ''source_owner_mismatch'',count(*) filter(where s.stripe_subscription_id is not null and s.app_user_id is distinct from e.app_user_id)
) as metrics from public.billing_entitlements e
left join public.billing_subscriptions s on s.stripe_subscription_id=e.source_subscription_id
left join auth.users u on u.id=e.app_user_id'), ('webhook_integrity', ARRAY['public.billing_webhook_events.stripe_event_id:text', 'public.billing_webhook_events.processing_state:text', 'public.billing_webhook_events.payload:jsonb', 'public.billing_webhook_events.attempt_count:int4', 'public.billing_webhook_events.updated_at:timestamptz'], 'select jsonb_build_object(
 ''rows'',count(*),
 ''duplicate_event_rows'',count(stripe_event_id)-count(distinct stripe_event_id),
 ''invalid_states'',count(*) filter(where processing_state is null or processing_state not in (''processing'',''processed'',''failed'')),
 ''failed_events'',count(*) filter(where processing_state=''failed''),
 ''processing_events'',count(*) filter(where processing_state=''processing''),
 ''stale_processing_events'',count(*) filter(where processing_state=''processing'' and updated_at < current_timestamp-interval ''5 minutes''),
 ''invalid_attempts'',count(*) filter(where attempt_count is null or attempt_count < 1),
 ''payload_id_conflicts'',count(*) filter(where payload ? ''id'' and payload->>''id'' is distinct from stripe_event_id)
) as metrics from public.billing_webhook_events'), ('phase2_customer_leases', ARRAY['public.billing_customers.reconciliation_token:uuid', 'public.billing_customers.reconciliation_expires:timestamptz'], 'select jsonb_build_object(
 ''active_leases'',count(*) filter(where reconciliation_token is not null and reconciliation_expires > current_timestamp),
 ''expired_leases'',count(*) filter(where reconciliation_token is not null and reconciliation_expires <= current_timestamp),
 ''incomplete_lease_pairs'',count(*) filter(where (reconciliation_token is null) <> (reconciliation_expires is null))
) as metrics from public.billing_customers'), ('phase2_projection_backfill', ARRAY['public.billing_subscriptions.projected_plan:text', 'public.billing_subscriptions.projected_status:text', 'public.billing_subscriptions.projected_reason:text'], 'select jsonb_build_object(
 ''unprojected_subscriptions'',count(*) filter(where projected_plan is null),
 ''invalid_projected_plans'',count(*) filter(where projected_plan is not null and projected_plan not in (''free'',''pro'')),
 ''partial_projections'',count(*) filter(where projected_plan is not null and (projected_status is null or projected_reason is null))
) as metrics from public.billing_subscriptions'), ('phase2_event_fingerprints', ARRAY['public.billing_webhook_events.fingerprint:text', 'public.billing_webhook_events.lease_token:uuid', 'public.billing_webhook_events.processing_state:text', 'public.billing_webhook_events.payload:jsonb'], 'select jsonb_build_object(
 ''legacy_events_without_fingerprint'',count(*) filter(where fingerprint is null),
 ''legacy_events_without_original_envelope'',count(*) filter(where fingerprint is null and not coalesce(payload ? ''id'',false)),
 ''completed_events_with_lease_token'',count(*) filter(where processing_state=''processed'' and lease_token is not null)
) as metrics from public.billing_webhook_events')), guarded AS (SELECT *, NOT EXISTS (SELECT 1 FROM unnest(requirements) AS req LEFT JOIN pg_class AS c ON c.oid = to_regclass(split_part(req, '.', 1) || '.' || split_part(req, '.', 2)) LEFT JOIN pg_attribute AS a ON a.attrelid = c.oid AND a.attname = split_part(split_part(req, '.', 3), ':', 1) AND NOT a.attisdropped WHERE c.oid IS NULL OR c.relkind NOT IN ('r', 'p') OR a.attnum IS NULL OR a.atttypid <> to_regtype(split_part(req, ':', 2))) AS compatible FROM checks) SELECT '08_aggregate_integrity' AS section, label, CASE WHEN compatible THEN 'SCANNED' ELSE 'SKIPPED_MISSING_OR_INCOMPATIBLE_SCHEMA' END AS result, CASE WHEN compatible THEN CAST(CAST(((xpath('/table/row/metrics/text()', query_to_xml(sql_text, FALSE, FALSE, ''))))[1] AS text) AS jsonb) END AS counts FROM guarded ORDER BY label
),
-- 09_shared_objects
inspection_18 AS MATERIALIZED (
WITH expected(schema_name, object_name, purpose) AS (VALUES ('public', 'subscriptions', 'PROTECTED_BASEBALL'), ('private', 'baseball_billing_webhook_events', 'PROTECTED_BASEBALL'), ('private', 'baseball_billing_subscription_versions', 'PROTECTED_BASEBALL'), ('private', 'baseball_auth_project_billing_install', 'PROTECTED_BASEBALL_UNKNOWN_MARKER'), ('public', 'suite_users', 'PROTECTED_SUITE'), ('public', 'suite_activity_events', 'PROTECTED_SUITE'), ('public', 'suite_app_current_state', 'PROTECTED_SUITE'), ('auth', 'users', 'PROTECTED_AUTH'), ('public', 'music_billing_customers', 'PROPOSED_MUSIC'), ('public', 'music_billing_subscriptions', 'PROPOSED_MUSIC'), ('public', 'music_billing_webhook_events', 'PROPOSED_MUSIC'), ('public', 'music_billing_entitlements', 'PROPOSED_MUSIC')) SELECT '09_shared_objects' AS section, e.*, c.oid IS NOT NULL AS object_exists, c.relkind, c.relrowsecurity, c.relforcerowsecurity, c.reltuples AS estimated_rows, pg_get_userbyid(c.relowner) AS owner, c.relacl, CASE WHEN c.oid IS NULL AND purpose = 'PROPOSED_MUSIC' THEN 'NAME_AVAILABLE_VERIFY_DEPENDENCIES' WHEN c.oid IS NOT NULL AND purpose = 'PROPOSED_MUSIC' THEN 'STOP_REVIEW_EXISTING_OBJECT' WHEN c.oid IS NULL THEN 'STOP_EXPECTED_SHARED_OBJECT_MISSING' ELSE 'PRESERVE' END AS review FROM expected AS e LEFT JOIN pg_class AS c ON c.oid = to_regclass(format('%I.%I', schema_name, object_name))
),
-- 10_shared_columns
inspection_19 AS MATERIALIZED (
SELECT '10_shared_columns' AS section, n.nspname, c.relname, a.attname, format_type(a.atttypid, a.atttypmod) AS type, a.attnotnull, pg_get_expr(d.adbin, d.adrelid) AS default_sql FROM pg_class AS c INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace INNER JOIN pg_attribute AS a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped LEFT JOIN pg_attrdef AS d ON d.adrelid = a.attrelid AND d.adnum = a.attnum WHERE (n.nspname = 'public' AND c.relname IN ('subscriptions', 'suite_users', 'suite_activity_events', 'suite_app_current_state')) OR (n.nspname = 'private' AND c.relname IN ('baseball_billing_webhook_events', 'baseball_billing_subscription_versions', 'baseball_auth_project_billing_install')) ORDER BY n.nspname, c.relname, a.attnum
),
-- 10_shared_constraints
inspection_20 AS MATERIALIZED (
SELECT '10_shared_constraints' AS section, n.nspname, c.relname, co.conname, co.convalidated, pg_get_constraintdef(co.oid) AS definition FROM pg_constraint AS co INNER JOIN pg_class AS c ON c.oid = co.conrelid INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE (n.nspname = 'public' AND c.relname IN ('subscriptions', 'suite_users', 'suite_activity_events', 'suite_app_current_state')) OR (n.nspname = 'private' AND c.relname LIKE pg_catalog.like_escape('baseball\_%', '\'))
),
-- 11_shared_policies
inspection_21 AS MATERIALIZED (
SELECT '11_shared_policies' AS section, schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check FROM pg_policies WHERE (schemaname = 'public' AND tablename IN ('subscriptions', 'suite_users', 'suite_activity_events', 'suite_app_current_state')) OR (schemaname = 'private' AND tablename LIKE pg_catalog.like_escape('baseball\_%', '\'))
),
-- 11_shared_effective_access
inspection_22 AS MATERIALIZED (
SELECT '11_shared_effective_access' AS section, r.rolname, n.nspname, c.relname, has_schema_privilege(r.oid, n.oid, 'USAGE') AS schema_usage, has_table_privilege(r.oid, c.oid, 'SELECT') AS can_select, has_table_privilege(r.oid, c.oid, 'INSERT') AS can_insert, has_table_privilege(r.oid, c.oid, 'UPDATE') AS can_update, has_table_privilege(r.oid, c.oid, 'DELETE') AS can_delete, has_table_privilege(r.oid, c.oid, 'TRUNCATE') AS can_truncate, has_any_column_privilege(r.oid, c.oid, 'UPDATE') AS any_column_update FROM pg_roles AS r CROSS JOIN pg_class AS c INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE r.rolname IN ('anon', 'authenticated', 'service_role') AND c.relkind IN ('r', 'p') AND ((n.nspname = 'public' AND c.relname IN ('subscriptions', 'suite_users', 'suite_activity_events', 'suite_app_current_state')) OR (n.nspname = 'private' AND c.relname LIKE pg_catalog.like_escape('baseball\_%', '\')))
),
-- 12_default_acl
inspection_23 AS MATERIALIZED (
SELECT '12_default_acl' AS section, pg_get_userbyid(d.defaclrole) AS creator_role, COALESCE(n.nspname, 'ALL_SCHEMAS') AS schema_name, d.defaclobjtype, d.defaclacl FROM pg_default_acl AS d LEFT JOIN pg_namespace AS n ON n.oid = d.defaclnamespace WHERE d.defaclnamespace = 0 OR n.nspname IN ('public', 'private')
),
-- 12_memberships
inspection_24 AS MATERIALIZED (
SELECT '12_memberships' AS section, parent.rolname AS inherited_role, child.rolname AS member_role, m.admin_option FROM pg_auth_members AS m INNER JOIN pg_roles AS parent ON parent.oid = m.roleid INNER JOIN pg_roles AS child ON child.oid = m.member WHERE parent.rolname IN ('anon', 'authenticated', 'service_role') OR child.rolname IN ('anon', 'authenticated', 'service_role')
),
-- 13_function_boundary
inspection_25 AS MATERIALIZED (
SELECT '13_function_boundary' AS section, n.nspname, p.proname, pg_get_function_identity_arguments(p.oid) AS arguments, p.prosecdef, p.proconfig, p.proacl, pg_get_userbyid(p.proowner) AS owner, md5(p.prosrc) AS body_md5, p.prosrc ILIKE '%subscriptions%' AS mentions_subscriptions, p.prosrc ILIKE '%suite_%' AS mentions_suite, p.prosrc ILIKE '%billing_%' AS mentions_billing, r.rolname, has_function_privilege(r.oid, p.oid, 'EXECUTE') AS effective_execute FROM pg_proc AS p INNER JOIN pg_namespace AS n ON n.oid = p.pronamespace CROSS JOIN pg_roles AS r WHERE n.nspname IN ('public', 'private') AND p.prokind = 'f' AND (p.prosecdef OR p.proname LIKE pg_catalog.like_escape('baseball\_%', '\') OR p.proname LIKE pg_catalog.like_escape('billing\_%', '\') OR p.proname LIKE pg_catalog.like_escape('music\_billing\_%', '\')) AND r.rolname IN ('anon', 'authenticated', 'service_role') ORDER BY n.nspname, p.proname, arguments, r.rolname
),
-- 14_shared_triggers
inspection_26 AS MATERIALIZED (
SELECT '14_shared_triggers' AS section, n.nspname, c.relname, t.tgname, t.tgenabled, pg_get_triggerdef(t.oid) AS definition, p.proname AS function_name, pn.nspname AS function_schema, md5(p.prosrc) AS function_body_md5 FROM pg_trigger AS t INNER JOIN pg_class AS c ON c.oid = t.tgrelid INNER JOIN pg_namespace AS n ON n.oid = c.relnamespace INNER JOIN pg_proc AS p ON p.oid = t.tgfoid INNER JOIN pg_namespace AS pn ON pn.oid = p.pronamespace WHERE NOT t.tgisinternal AND ((n.nspname = 'auth' AND c.relname = 'users') OR (n.nspname = 'public' AND c.relname IN ('subscriptions', 'suite_users', 'suite_activity_events', 'suite_app_current_state')))
),
-- 15_shared_row_counts
inspection_27 AS MATERIALIZED (
WITH expected(schema_name, table_name) AS (VALUES ('public', 'subscriptions'), ('private', 'baseball_billing_webhook_events'), ('private', 'baseball_billing_subscription_versions'), ('private', 'baseball_auth_project_billing_install'), ('public', 'suite_users'), ('public', 'suite_activity_events'), ('public', 'suite_app_current_state')) SELECT '15_shared_row_counts' AS section, e.*, CASE WHEN c.relkind IN ('r', 'p') THEN 'SCANNED_ADMIN_VISIBILITY_REQUIRED' ELSE 'SKIPPED_MISSING_OR_NON_TABLE' END AS result, CASE WHEN c.relkind IN ('r', 'p') THEN CAST(CAST(((xpath('/table/row/n/text()', query_to_xml(format('select count(*) as n from %I.%I', schema_name, table_name), FALSE, FALSE, ''))))[1] AS text) AS bigint) END AS rows FROM expected AS e LEFT JOIN pg_class AS c ON c.oid = to_regclass(format('%I.%I', schema_name, table_name))
)
SELECT '01_context'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_01 AS result_row
UNION ALL
SELECT '01_roles'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_02 AS result_row
UNION ALL
SELECT '02_columns'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_03 AS result_row
UNION ALL
SELECT '02_all_columns'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_04 AS result_row
UNION ALL
SELECT '03_constraints'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_05 AS result_row
UNION ALL
SELECT '03_indexes'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_06 AS result_row
UNION ALL
SELECT '03_named_index_collisions'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_07 AS result_row
UNION ALL
SELECT '04_rls'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_08 AS result_row
UNION ALL
SELECT '04_policies'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_09 AS result_row
UNION ALL
SELECT '04_privileges'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_10 AS result_row
UNION ALL
SELECT '05_expected_rpcs'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_11 AS result_row
UNION ALL
SELECT '05_all_rpc_permissions'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_12 AS result_row
UNION ALL
SELECT '05_public_rpc_acl'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_13 AS result_row
UNION ALL
SELECT '06_triggers'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_14 AS result_row
UNION ALL
SELECT '06_dependencies'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_15 AS result_row
UNION ALL
SELECT '07_migration_history'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_16 AS result_row
UNION ALL
SELECT '08_aggregate_integrity'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_17 AS result_row
UNION ALL
SELECT '09_shared_objects'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_18 AS result_row
UNION ALL
SELECT '10_shared_columns'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_19 AS result_row
UNION ALL
SELECT '10_shared_constraints'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_20 AS result_row
UNION ALL
SELECT '11_shared_policies'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_21 AS result_row
UNION ALL
SELECT '11_shared_effective_access'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_22 AS result_row
UNION ALL
SELECT '12_default_acl'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_23 AS result_row
UNION ALL
SELECT '12_memberships'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_24 AS result_row
UNION ALL
SELECT '13_function_boundary'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_25 AS result_row
UNION ALL
SELECT '14_shared_triggers'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_26 AS result_row
UNION ALL
SELECT '15_shared_row_counts'::text AS section, count(*) AS row_count,
 coalesce(jsonb_agg(to_jsonb(result_row) - 'section'), '[]'::jsonb) AS findings
FROM inspection_27 AS result_row
ORDER BY section;
ROLLBACK;
