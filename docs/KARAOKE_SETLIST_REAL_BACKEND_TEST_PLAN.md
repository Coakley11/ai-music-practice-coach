# Plan: verifying Karaoke setlist durability against the real backend

**Status:** plan only. Nothing here has been run. It needs your explicit approval first, because it
writes test rows to a real Supabase project.

## Why

Every result so far (`scripts/_accept_karaoke_setlist_durability.py`, 33/33 and 47/52 with the five
failures traced to harness steps) used `scripts/_fake_supabase.py`: a local stand-in that speaks the
same REST protocol. It proves the app's logic, but not:

- the real project's row-level behaviour, triggers, size limits and latency;
- Streamlit Cloud's real container replacement (only simulated, by swapping the server and its disk);
- two physical devices on the Cloud app.

## Safety rules

1. **An isolated test identity, never yours.** The test app runs with `SUITE_USER_ID` set to a
   dedicated id such as `ksetlist_qa_<date>`. The app writes only rows keyed by that user. Your
   `daniel` row, and every other user's row, is never read for content or written.
2. **A separate test app, not your dev app.** A local app or a second, private Streamlit app,
   pointed at the backend by environment variables. Your Cloud dev app's URL is never driven by
   automation, because it autosaves into your workspace.
3. **Read-back only of the test rows.** Each check reads `suite_app_current_state` filtered by the
   test user's id and prints setlist length, titles, keys and stamps for that row only.
4. **Clean-up you can audit.** The test user's rows are listed before deletion; deletion is a
   separate step you approve, filtered by the test user id.
5. **No schema, policy, bucket or configuration change.**

## Which backend

Preferably the QA project (`bnfd…bmt`), which already holds QA identities. If you want the proof on
the dev project (`qhp…`), the same rules apply. It writes one isolated test-user row there, and
nothing else.

## Steps

1. Run the same harness with the real backend instead of the stand-in: SUITE_SUPABASE_URL / KEY
   from the environment of that test app (not printed, not logged), the test `SUITE_USER_ID`, and
   strict egress on.
2. Scenarios: build (3 songs, distinct keys) → refresh → stale tab → next-day session → End Set →
   restart the app process with a new empty data directory → two-session conflict → outage
   (simulated by an invalid key for one save) → Retry → Clear confirm/keep/erase.
3. Cloud restart for real: deploy the branch to a private test Streamlit app (with your approval),
   build a setlist there under the test identity, trigger a reboot from the Streamlit dashboard,
   reopen and compare.
4. Two devices: the same private test app opened on a laptop and a phone with the test identity.
   Edit on one, refresh the other.
5. Report: per step, the stored row's setlist (test user only) and what the page showed.

## What would count as done

Every step shows the same songs, order, keys and source identities in the stored row and on the
page. A refused or failed save is reported as NOT saved. A deliberate clear stays cleared, and
nothing returns that was removed.
