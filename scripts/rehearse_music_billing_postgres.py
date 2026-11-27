"""Disposable localhost-only PostgreSQL rehearsal; never accepts a remote database URL."""
from pathlib import Path
import json, os, socket, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get('MUSIC_TEST_PG_BIN', r'C:\Program Files\PostgreSQL\17\bin'))
USER_A = '00000000-0000-4000-8000-000000000001'
USER_B = '00000000-0000-4000-8000-000000000002'

def main():
    import psutil
    available = psutil.virtual_memory().available / 2**30
    if available < 1:
        raise SystemExit('Need at least 1 GB available RAM for this small native rehearsal')
    root = Path(tempfile.mkdtemp(prefix='music-pg-rehearsal-'))
    data = root / 'data'
    def run(name, *args, check=True):
        # Windows server children can inherit PIPE handles and block communicate().
        with (root / (name + '-output.log')).open('w+', encoding='utf8') as output:
            result = subprocess.run([str(BIN / (name + '.exe')), *map(str,args)], stdout=output, stderr=subprocess.STDOUT, text=True, timeout=180)
            output.seek(0); result.stdout=output.read(); result.stderr=''
        if check and result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    run('initdb','-D',data,'-U','music_rehearsal','--auth=trust','--no-locale','--encoding=UTF8')
    (data/'postgresql.conf').write_text(f"\nlisten_addresses='127.0.0.1'\nport={port}\nshared_buffers='16MB'\nmax_connections=5\nwork_mem='1MB'\nmaintenance_work_mem='16MB'\nmax_worker_processes=1\nmax_parallel_workers=0\n",encoding='utf8')
    started = False
    def sql(source, check=True):
        result = subprocess.run([str(BIN/'psql.exe'),'-X','-h','127.0.0.1','-p',str(port),'-U','music_rehearsal','-d','postgres','-v','ON_ERROR_STOP=1','-At'],input=source,capture_output=True,text=True,timeout=60)
        if check and result.returncode: raise RuntimeError(result.stdout+result.stderr)
        return result
    try:
        started=True
        run('pg_ctl','-D',data,'-l',root/'server.log','-w','start')
        sql('''create role anon; create role authenticated; create role service_role bypassrls;
create role extra_default_grantee;
revoke create on schema public from public;
grant usage on schema public to anon,authenticated,service_role,extra_default_grantee;
create schema auth; create schema private;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
grant usage on schema auth to anon,authenticated,service_role;
grant execute on function auth.uid() to anon,authenticated,service_role;
create function auth.fixture_signup() returns trigger language plpgsql as $$begin return new; end$$;
create trigger fixture_signup after insert on auth.users for each row execute function auth.fixture_signup();
insert into auth.users values (''' + "'"+USER_A+"'),('"+USER_B+"');" + '''
create table public.subscriptions(id int primary key, fixture text);
insert into public.subscriptions values(1,'baseball-preserve');
create table private.baseball_billing_webhook_events(id int);
create table private.baseball_billing_subscription_versions(id int);
create table private.baseball_auth_project_billing_install(id int);
create table public.suite_users(id int);
create table public.suite_activity_events(id int);
create table public.suite_app_current_state(id int);
insert into private.baseball_billing_webhook_events values(1);
insert into private.baseball_billing_subscription_versions values(1);
insert into private.baseball_auth_project_billing_install values(1);
insert into public.suite_users values(1);
insert into public.suite_activity_events values(1);
insert into public.suite_app_current_state values(1);
do $$declare t text; begin foreach t in array array['public.subscriptions','private.baseball_billing_webhook_events','private.baseball_billing_subscription_versions','private.baseball_auth_project_billing_install','public.suite_users','public.suite_activity_events','public.suite_app_current_state'] loop execute 'alter table '||t||' enable row level security'; end loop; end$$;
grant all on public.suite_activity_events,public.suite_app_current_state to anon,authenticated;
create function public.baseball_fixture() returns int language sql as $$select 42$$;
alter default privileges in schema public grant all on tables to public,anon,authenticated,service_role,extra_default_grantee;
alter default privileges in schema public grant execute on functions to extra_default_grantee;
''')
        # Compare a stable catalog/row snapshot instead: pg_dump randomizes restriction keys.
        snapshot = '''select jsonb_agg(x order by x::text) from (
select jsonb_build_array('table',n.nspname,c.relname,c.relacl::text,c.relrowsecurity) x from pg_class c join pg_namespace n on n.oid=c.relnamespace where c.relkind='r' and n.nspname in ('public','private','auth') and c.relname not like 'music_billing_%'
union all select jsonb_build_array('function',p.oid::regprocedure::text,pg_get_functiondef(p.oid),p.proacl::text) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in ('public','private','auth') and p.proname not like 'music_billing_%'
union all select jsonb_build_array('trigger',tgname,pg_get_triggerdef(oid)) from pg_trigger where not tgisinternal and tgname not like 'music_billing_%'
union all select jsonb_build_array('rows', 'subscriptions',to_jsonb(t)) from public.subscriptions t
union all select jsonb_build_array('rows','auth.users',to_jsonb(t)) from auth.users t
union all select jsonb_build_array('policy',schemaname,tablename,policyname,roles,cmd,qual,with_check) from pg_policies where tablename not like 'music_billing_%'
union all select jsonb_build_array('rows','suite_users',to_jsonb(t)) from public.suite_users t
union all select jsonb_build_array('rows','suite_activity_events',to_jsonb(t)) from public.suite_activity_events t
union all select jsonb_build_array('rows','suite_app_current_state',to_jsonb(t)) from public.suite_app_current_state t
union all select jsonb_build_array('rows','baseball_events',to_jsonb(t)) from private.baseball_billing_webhook_events t
union all select jsonb_build_array('rows','baseball_versions',to_jsonb(t)) from private.baseball_billing_subscription_versions t
union all select jsonb_build_array('rows','baseball_install',to_jsonb(t)) from private.baseball_auth_project_billing_install t
union all select jsonb_build_array('default_acl',defaclrole,defaclnamespace,defaclobjtype,defaclacl::text) from pg_default_acl
) s;'''
        before = sql(snapshot).stdout
        # Phase 6's inspection SQL is also executed against these local fixtures;
        # it must leave the protected snapshot unchanged and return all sections.
        preflight = ROOT/'supabase/preflight/music_billing_isolated_phase6.sql'
        if preflight.exists():
            output = sql(preflight.read_text(encoding='utf8')).stdout
            assert sum(line[:2].isdigit() and '|' in line for line in output.splitlines()) == 14
            assert before == sql(snapshot).stdout
        installer = (ROOT/'supabase/install/20261112_music_billing_shared_install.sql').read_text(encoding='utf8')
        # Failure near COMMIT proves rollback of tables, functions, grants and FK triggers.
        failure = installer.rsplit('commit;',1)[0] + "do $$begin raise exception 'rehearsal injected late failure';end$$; commit;"
        result = sql(failure,check=False)
        assert result.returncode and 'rehearsal injected late failure' in result.stderr, result.stderr
        count = "select count(*) from pg_class where relname like 'music_billing_%';"
        assert sql(count).stdout.strip()=='0'
        assert sql("select (select count(*) from pg_proc where proname like 'music_billing_%')+(select count(*) from pg_type where typname like 'music_billing_%')+(select count(*) from pg_constraint where conname like 'music_billing_%')+(select count(*) from pg_trigger where tgname like 'music_billing_%');").stdout.strip()=='0'
        assert before==sql(snapshot).stdout
        sql('create table public.music_billing_collision_fixture(id int);')
        result=sql(installer,check=False)
        assert result.returncode and 'Music namespace collision' in result.stderr, result.stderr
        assert sql(count).stdout.strip()=='1'
        sql('drop table public.music_billing_collision_fixture;')
        sql(installer)
        postinstall = ROOT/'supabase/preflight/music_billing_phase6_postinstall.sql'
        if postinstall.exists():
            output = sql(postinstall.read_text(encoding='utf8')).stdout
            assert sum(line[:2].isdigit() and '|' in line for line in output.splitlines()) == 8
        assert before==sql(snapshot).stdout, 'Protected metadata or rows changed'
        harness=(ROOT/'scripts/sql_tests/music_billing_shared_roles.sql').read_text(encoding='utf8')
        harness='\n'.join(line for line in harness.splitlines() if not line.startswith('\\'))
        harness=harness.replace(":'user_a'", "'"+USER_A+"'").replace(":'user_b'", "'"+USER_B+"'")
        sql(harness)
        lifecycle=(ROOT/'scripts/sql_tests/music_billing_lifecycle_rehearsal.sql').read_text(encoding='utf-8-sig')
        sql("select set_config('music_test.user_a','"+USER_A+"',false);"+lifecycle)
        assert sql('select count(*) from public.music_billing_customers;').stdout.strip()=='0', 'Harness did not roll back'
        assert before==sql(snapshot).stdout
        result=sql(installer,check=False)
        assert result.returncode and 'Music namespace collision' in result.stderr
        sql("""begin;
select public.music_billing_attach_customer('00000000-0000-4000-8000-000000000001','cus_owner_a');
do $$begin
 begin perform public.music_billing_attach_customer('00000000-0000-4000-8000-000000000001','cus_rebind'); raise exception 'Rebind accepted'; exception when raise_exception then if sqlerrm='Rebind accepted' then raise; end if; end;
 begin perform public.music_billing_attach_customer('00000000-0000-4000-8000-000000000002','cus_owner_a'); raise exception 'Sharing accepted'; exception when unique_violation then null; end;
 begin update public.music_billing_customers set stripe_customer_id='cus_rebound'; raise exception 'Trigger bypass'; exception when raise_exception then if sqlerrm='Trigger bypass' then raise; end if; end;
end$$; rollback;""")
        report={'postgres':run('postgres','--version').stdout.strip(),'checks':['late failure atomic rollback','namespace collision rollback','fresh installation','role/RLS/atomic delivery harness','10 SQL lifecycle transitions and lease exclusion','customer rebind/sharing/trigger rejection','repeat installation rejection','protected fixture metadata/rows unchanged'],'available_ram_gb_start':round(available,2),'available_ram_gb_end':round(psutil.virtual_memory().available/2**30,2),'local_artifacts':str(root)}
        print(json.dumps(report,indent=2))
    finally:
        if started and run('pg_ctl','-D',data,'status',check=False).returncode==0:
            run('pg_ctl','-D',data,'-m','fast','-w','stop')
            print('Disposable rehearsal cluster stopped.')

if __name__=='__main__': main()
