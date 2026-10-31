-- Read-only audit of Custom Progression song persistence.
-- Run in the Supabase SQL editor, one numbered block at a time. Every statement is a SELECT
-- against catalog views or the app tables: nothing here inserts, updates, deletes, alters or
-- grants. Payloads are summarised, not printed, so no song content or credential is exposed.
-- Paste the results back (they contain ids and counts only) so the findings can be confirmed.

-- 1. Do the tables exist, and what are their columns?
select table_name, ordinal_position as pos, column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public'
  and table_name in ('suite_users', 'suite_saved_items')
order by table_name, ordinal_position;

-- 2. Constraints (primary / unique / foreign keys / checks) on both tables.
--    The app upserts with ON CONFLICT (user_id, app, item_type, item_key): a unique constraint
--    or unique index on exactly those columns must exist, otherwise every save returns 400.
select conrelid::regclass as table_name, conname, contype, pg_get_constraintdef(oid) as definition
from pg_constraint
where conrelid in ('public.suite_users'::regclass, 'public.suite_saved_items'::regclass)
order by 1, 2;

-- 3. Indexes on both tables (including unique ones that are not constraints).
select tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public' and tablename in ('suite_users', 'suite_saved_items')
order by tablename, indexname;

-- 4. Row level security: is it enabled, and which policies exist?
select c.relname as table_name, c.relrowsecurity as rls_enabled, c.relforcerowsecurity as rls_forced
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname in ('suite_users', 'suite_saved_items');

select tablename, policyname, permissive, roles, cmd, qual, with_check
from pg_policies
where schemaname = 'public' and tablename in ('suite_users', 'suite_saved_items')
order by tablename, policyname;

-- 5. Is suite_users.external_id actually unique today? Any rows returned are duplicates:
--    the app looks the account up by external_id and takes the first match, so duplicates
--    can make it read one account and write to another.
select external_id, count(*) as rows, array_agg(id) as user_ids
from public.suite_users
group by external_id
having count(*) > 1;

-- 6. All accounts the app could resolve (ids and labels only; no emails).
select id, external_id, display_name
from public.suite_users
order by external_id;

-- 7. Custom songs per account and per storage "app" key.
--    app = 'music' is the default workspace (daniel); 'music__<workspace>' is any other.
select u.external_id, s.user_id, s.app,
       count(*) filter (where s.valid) as valid_songs,
       count(*) filter (where not s.valid) as deleted_songs,
       min(s.updated_at) as oldest_update,
       max(s.updated_at) as newest_update
from public.suite_saved_items s
left join public.suite_users u on u.id = s.user_id
where s.item_type = 'custom_song'
group by u.external_id, s.user_id, s.app
order by u.external_id nulls first, s.app;

-- 8. Custom songs whose user_id has no suite_users row, or has no user_id at all (orphans).
select s.user_id, s.app, count(*) as songs
from public.suite_saved_items s
left join public.suite_users u on u.id = s.user_id
where s.item_type = 'custom_song' and s.valid and u.id is null
group by s.user_id, s.app;

-- 9. Duplicate identities. Both should return no rows.
--    9a: the same (user, app, type, key) more than once (would also make ON CONFLICT impossible).
select user_id, app, item_type, item_key, count(*) as copies
from public.suite_saved_items
where item_type = 'custom_song'
group by user_id, app, item_type, item_key
having count(*) > 1;

--    9b: the same song id stored under more than one item_key / app for one account.
select user_id, payload #>> '{progression,id}' as song_id,
       count(*) as rows, array_agg(distinct app) as apps, array_agg(item_key) as item_keys
from public.suite_saved_items
where item_type = 'custom_song' and valid
group by user_id, payload #>> '{progression,id}'
having count(*) > 1;

-- 10. Songs where the stored workspace tag disagrees with the app key (these were the rows
--     the old "limit, then filter by workspace" listing could hide). Should return no rows.
select s.app, s.payload ->> 'workspace_id' as payload_workspace, count(*) as songs
from public.suite_saved_items s
where s.item_type = 'custom_song' and s.valid
  and coalesce(nullif(s.payload ->> 'workspace_id', ''), 'daniel')
      <> case when s.app = 'music' then 'daniel' else split_part(s.app, '__', 2) end
group by s.app, s.payload ->> 'workspace_id';

-- 11. Is each song complete? Counts of structural keys, never the content itself.
select s.app,
       count(*) as songs,
       count(*) filter (where s.payload #> '{progression,original_sections}' is not null) as with_sections,
       count(*) filter (where s.payload #> '{progression,lyrics_by_section}' is not null) as with_lyrics_key,
       count(*) filter (where s.payload::text ~ '"chord": ?"[^"]*:[0-9.]+\|') as with_split_bars,
       count(*) filter (where s.payload::text like '%/%') as maybe_slash_chords,
       count(*) filter (where s.payload #>> '{progression,id}' is null) as missing_song_id,
       max(pg_column_size(s.payload)) as largest_payload_bytes
from public.suite_saved_items s
where s.item_type = 'custom_song' and s.valid
group by s.app
order by s.app;

-- 12. Same title saved as different songs for one account (the app keeps both, as "Title (2)").
select user_id, app, title, count(*) as songs, array_agg(item_key) as item_keys
from public.suite_saved_items
where item_type = 'custom_song' and valid
group by user_id, app, title
having count(*) > 1;

-- 13. Recent write activity (are saves reaching the database at all?).
select date_trunc('day', updated_at) as day, count(*) as writes
from public.suite_saved_items
where item_type = 'custom_song' and updated_at > now() - interval '30 days'
group by 1
order by 1 desc;
