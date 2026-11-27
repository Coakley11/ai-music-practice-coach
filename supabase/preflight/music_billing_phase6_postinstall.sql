-- READ ONLY. Export one grid after isolated-project installation.
begin transaction isolation level repeatable read read only;
set local statement_timeout='15s';
with tables as (
 select c.*,n.nspname from pg_class c join pg_namespace n on n.oid=c.relnamespace
 where n.nspname='public' and c.relkind='r' and left(c.relname,14)='music_billing_'
), funcs as (
 select p.* from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname='public' and left(p.proname,14)='music_billing_'
), report(section,findings) as (
 select '01_tables',coalesce(jsonb_agg(jsonb_build_object('name',relname,'owner',pg_get_userbyid(relowner),'rls',relrowsecurity,'acl',relacl::text)),'[]') from tables
 union all select '02_effective_table_permissions',coalesce(jsonb_agg(jsonb_build_object('role',r.rolname,'table',t.relname,
 'select',has_table_privilege(r.oid,t.oid,'SELECT'),'insert',has_table_privilege(r.oid,t.oid,'INSERT'),
 'update',has_table_privilege(r.oid,t.oid,'UPDATE'),'delete',has_table_privilege(r.oid,t.oid,'DELETE'),
 'truncate',has_table_privilege(r.oid,t.oid,'TRUNCATE'),'references',has_table_privilege(r.oid,t.oid,'REFERENCES'),
 'trigger',has_table_privilege(r.oid,t.oid,'TRIGGER'),'column_insert',has_any_column_privilege(r.oid,t.oid,'INSERT'),
 'column_update',has_any_column_privilege(r.oid,t.oid,'UPDATE'))),'[]') from tables t cross join pg_roles r where r.rolname in ('anon','authenticated','service_role')
 union all select '03_functions',coalesce(jsonb_agg(jsonb_build_object('signature',oid::regprocedure::text,'owner',pg_get_userbyid(proowner),'security_definer',prosecdef,'settings',proconfig,'acl',proacl::text,'body_md5',md5(prosrc))),'[]') from funcs
 union all select '04_effective_execute',coalesce(jsonb_agg(jsonb_build_object('role',r.rolname,'function',p.oid::regprocedure::text,'execute',has_function_privilege(r.oid,p.oid,'EXECUTE'))),'[]') from funcs p cross join pg_roles r where r.rolname in ('anon','authenticated','service_role')
 union all select '05_policies',coalesce(jsonb_agg(to_jsonb(p)),'[]') from pg_policies p where schemaname='public' and left(tablename,14)='music_billing_'
 union all select '06_indexes',coalesce(jsonb_agg(to_jsonb(i)),'[]') from pg_indexes i where schemaname='public' and left(tablename,14)='music_billing_'
 union all select '07_constraints',coalesce(jsonb_agg(jsonb_build_object('name',k.conname,'table',k.conrelid::regclass::text,'definition',pg_get_constraintdef(k.oid),'validated',k.convalidated)),'[]') from pg_constraint k join tables t on t.oid=k.conrelid
 union all select '08_triggers',coalesce(jsonb_agg(jsonb_build_object('table',tgrelid::regclass::text,'name',tgname,'internal',tgisinternal,'definition',pg_get_triggerdef(oid))),'[]') from pg_trigger where tgrelid in (select oid from tables) or (tgrelid=to_regclass('auth.users') and not tgisinternal)
)
select section,findings from report order by section;
commit;
