-- OPTIONAL PRIVATE CODE REVIEW ONLY. No billing function is executed.
-- Inspect locally in the test project's SQL Editor; do not publish full definitions.
-- Unrecognized existing function code may contain embedded credentials or literals.
-- Share only function names/signatures, hash match status and sanitized findings.
begin transaction read only;
set local statement_timeout = '30s';
select p.proname, pg_get_function_identity_arguments(p.oid) as arguments,
 md5(p.prosrc) as body_md5, pg_get_functiondef(p.oid) as private_definition
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.prokind='f' and
 (p.proname like 'billing\_%' escape '\' or p.proname like 'music\_billing\_%' escape '\')
order by p.proname,arguments;
rollback;
