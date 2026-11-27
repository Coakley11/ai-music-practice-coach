-- READ ONLY. First independently verify Dashboard URL and Settings > API both
-- identify smpyutzfktjgpdibdbqb. SQL current_database() is NOT project identity.
-- Never run an installer/test harness in qhprdlwoxjpkiukxhftp.
-- Run entire file; export the final single result grid. No identities returned.
begin transaction isolation level repeatable read read only;
set local statement_timeout='20s';
set local lock_timeout='3s';
do $$
declare t record; n bigint; counts jsonb:='[]';
begin
 for t in select ns.nspname,c.relname from pg_class c join pg_namespace ns on ns.oid=c.relnamespace
  where c.relkind in ('r','p') and (ns.nspname in ('public','private')
   or (ns.nspname='auth' and c.relname='users')
   or (ns.nspname='storage' and c.relname in ('objects','buckets')))
  order by ns.nspname,c.relname
 loop
  begin
   execute format('select count(*) from %I.%I',t.nspname,t.relname) into n;
   counts:=counts||jsonb_build_array(jsonb_build_object('schema',t.nspname,'table',t.relname,'rows',n));
  exception when insufficient_privilege then
   counts:=counts||jsonb_build_array(jsonb_build_object('schema',t.nspname,'table',t.relname,'error','UNVERIFIED_PERMISSION'));
  end;
 end loop;
 perform set_config('music_preflight.counts',counts::text,true);
end$$;
with sections(section,findings) as (
 select '01_context',jsonb_build_object('database',current_database(),'role',current_user,
  'version',current_setting('server_version'),'read_only',current_setting('transaction_read_only'),
  'owner_bypassrls',(select rolbypassrls or rolsuper from pg_roles where rolname=current_user),
  'project_identity','MANUAL_DASHBOARD_AND_API_URL_CONFIRMATION_REQUIRED')
 union all select '02_counts',current_setting('music_preflight.counts')::jsonb
 union all select '03_dependencies',jsonb_build_object('auth_users',to_regclass('auth.users') is not null,
  'auth_uid',to_regprocedure('auth.uid()') is not null,'uuid',to_regprocedure('pg_catalog.gen_random_uuid()') is not null,
  'create_public',has_schema_privilege(current_user,'public','CREATE'),
  'auth_uuid_key',exists(select 1 from pg_constraint k join pg_attribute a on a.attrelid=k.conrelid
   and a.attnum=any(k.conkey) where k.conrelid=to_regclass('auth.users') and k.contype in ('p','u')
   and cardinality(k.conkey)=1 and a.attname='id' and a.atttypid='uuid'::regtype))
 union all select '04_roles',coalesce(jsonb_agg(jsonb_build_object('name',e.name,'exists',r.oid is not null,
  'super',r.rolsuper,'bypassrls',r.rolbypassrls,'public_create',case when r.oid is not null then has_schema_privilege(r.oid,'public','CREATE') end,
  'public_usage',case when r.oid is not null then has_schema_privilege(r.oid,'public','USAGE') end,
  'auth_usage',case when r.oid is not null and to_regnamespace('auth') is not null then has_schema_privilege(r.oid,'auth','USAGE') end,
  'auth_uid_execute',case when r.oid is not null and to_regprocedure('auth.uid()') is not null then has_function_privilege(r.oid,to_regprocedure('auth.uid()'),'EXECUTE') end,
  'service_member',case when r.oid is not null and to_regrole('service_role') is not null then pg_has_role(r.oid,to_regrole('service_role'),'MEMBER') end)), '[]')
  from (values('anon'),('authenticated'),('service_role')) e(name) left join pg_roles r on r.rolname=e.name
 union all select '05_extensions',coalesce(jsonb_agg(jsonb_build_object('name',extname,'version',extversion)),'[]') from pg_extension
 union all select '06_namespace',coalesce(jsonb_agg(x),'[]') from (
  select jsonb_build_object('kind','relation','schema',n.nspname,'name',c.relname) x from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and left(c.relname,14)='music_billing_'
  union all select jsonb_build_object('kind','type','schema',n.nspname,'name',t.typname) from pg_type t join pg_namespace n on n.oid=t.typnamespace where n.nspname='public' and left(t.typname,14)='music_billing_'
  union all select jsonb_build_object('kind','function','schema',n.nspname,'name',p.oid::regprocedure::text) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and left(p.proname,14)='music_billing_'
  union all select jsonb_build_object('kind','constraint','name',conname) from pg_constraint where left(conname,14)='music_billing_'
  union all select jsonb_build_object('kind','trigger','name',tgname) from pg_trigger where left(tgname,14)='music_billing_') q
 union all select '07_default_acls',coalesce(jsonb_agg(jsonb_build_object('owner',pg_get_userbyid(defaclrole),'schema',n.nspname,'kind',defaclobjtype,'acl',defaclacl::text)),'[]') from pg_default_acl d left join pg_namespace n on n.oid=d.defaclnamespace
 union all select '08_event_triggers',coalesce(jsonb_agg(jsonb_build_object('name',evtname,'event',evtevent,'enabled',evtenabled,'function',evtfoid::regprocedure::text)),'[]') from pg_event_trigger
 union all select '09_auth_triggers',coalesce(jsonb_agg(jsonb_build_object('name',tgname,'definition',pg_get_triggerdef(oid))),'[]') from pg_trigger where tgrelid=to_regclass('auth.users') and not tgisinternal
 union all select '10_app_columns',coalesce(jsonb_agg(jsonb_build_object('schema',table_schema,'table',table_name,'column',column_name,'type',data_type)),'[]') from information_schema.columns where table_schema in ('public','private')
 union all select '11_app_functions',coalesce(jsonb_agg(jsonb_build_object('signature',p.oid::regprocedure::text,'owner',pg_get_userbyid(p.proowner),'security_definer',p.prosecdef,'settings',p.proconfig,'acl',p.proacl::text,'body_md5',md5(p.prosrc))),'[]') from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in ('public','private')
 union all select '12_policies',coalesce(jsonb_agg(to_jsonb(p)),'[]') from pg_policies p where schemaname in ('public','private')
 union all select '13_schemas',coalesce(jsonb_agg(jsonb_build_object('schema',nspname,'owner',pg_get_userbyid(nspowner),'acl',nspacl::text)),'[]') from pg_namespace where nspname not like 'pg_%' and nspname<>'information_schema'
 union all select '14_relations',coalesce(jsonb_agg(jsonb_build_object('schema',n.nspname,'name',c.relname,'kind',c.relkind,'owner',pg_get_userbyid(c.relowner))),'[]') from pg_class c join pg_namespace n on n.oid=c.relnamespace where c.relkind in ('r','p','v','m','f') and n.nspname not like 'pg_%' and n.nspname<>'information_schema'
)
select section,findings from sections order by section;
commit;
