# A karaoke retune on the Backing page still replaces the song's saved Practice Key

**Status:** defect, reproduced in a real browser against `origin/dev` + Slice 1 (`9904b588`).
Not fixed. The fix touches code already integrated, so it needs approval.

**Severity:** the musician's own saved Practice Key is permanently lost. Singing Say in A♭ for
one evening leaves Say saved in A♭, and End Set does not restore it.

## What was measured

Scenario, in the browser (`scripts/_accept_karaoke_stop_transport_v2.py`, port 8623):

1. Say is added to the Karaoke Set, so the entry keeps Say's own **B♭**.
2. With nothing performing, Say's own Practice Key is set to **D** - the musician's choice.
3. The set is started and the take plays.
4. On the **Backing** page, the sidebar Practice / Concert Key is moved to **A♭** for tonight.
5. Stop is pressed from the transport, then End Set.

The persisted store, read from `music_user_state.json` rather than from the sidebar:

| point | `practice_key_by_source` | saved setlist entry |
|---|---|---|
| before the performance | `{"Pop␟Say — John Mayer": "D"}` | B♭ |
| after Stop | `{"Pop␟Say — John Mayer": "Ab"}` | B♭ |
| after End Set | `{"Pop␟Say — John Mayer": "Ab"}` | B♭ |

The setlist entry is correct throughout - Part 3 holds. What is lost is the song's own saved
key. There is exactly one `practice_key_by_source` site in the persisted state
(`state.session.practice_key_by_source`), so this is not a session snapshot being mistaken for
the durable store, and persistence copies that session key verbatim.

## Why the Part 3b freeze did not stop it

Instrumenting every store assignment (temporary, env-gated, not committed) gives the writer:

```
D -> Ab   locked=False
    streamlit_music_practice_app.py:17715:_on_mission_or_global_pk_change
    backing_practice_key_control.py:763:commit_backing_practice_key
    practice_key_state.py:1328:set_practice_concert_key
```

Inside the one sidebar callback `_on_mission_or_global_pk_change`:

* **line 17715** - when `studio_page == "backing"`, `commit_backing_practice_key` writes the
  durable store through `set_practice_concert_key(..., allow_restore_original=True)`;
* **line 17758** - only *then* does `_karaoke_retune_after_explicit_key_change` run, and that is
  what calls `note_performance_retune` and registers the entry.

The freeze asks `performance_owns_song_key`, which is True only once the entry id is in
`performance_retuned_entry_ids`:

```python
if not entry_id or entry_id not in performance_retuned_entry_ids(session_state):
    return False
```

At line 17715 nothing is registered yet, so the guard answers False, the freeze is open, and the
write lands. **The guard is order-dependent: it protects the second and later retunes of a set
and not the first.** The trace confirms `locked=False` at the write.

Two reasons this was not caught earlier:

* `tests/test_karaoke_performance_key_persistence.py` uses a `durable_commit` helper that is
  *copied* from the real lane ("Copied rather than called because the real one needs a Streamlit
  script run") and copies it in the order retune-then-commit. In that order the freeze holds, so
  44 tests pass while the real callback commits first.
* the path is specific to `studio_page == "backing"`. A retune made from another page takes a
  different branch where the freeze does hold, which is what the Part 3b browser check exercised.

## Proposed fix (not implemented)

Two options; the second is preferred because it removes the ordering dependence rather than
re-tuning it.

**A. Register before committing.** Move `_karaoke_retune_after_explicit_key_change(tok)` ahead
of the per-widget durable commits in `_on_mission_or_global_pk_change`. Smallest change, but it
leaves the freeze depending on call order, and there are several commit branches in that
callback plus two other explicit controls that each reach the retune at a different point.

**B. Make the freeze order-independent.** Freeze the saved key of the song being sung whenever a
set is performing that pick, instead of only after it has been retuned once:

```python
# performance_owns_song_key: a set performing this song is enough; the register then only
# says whether tonight's key DIFFERS, which is a question for the read layer, not the freeze.
```

This matches the stated requirement - while a set is performing a song, a key gesture is a
performance retune and never a durable change - and it cannot be defeated by the order in which
one callback happens to run. It needs a separate decision about the read layer, which should
keep using the register so a song that was never retuned still reads its own saved key.

Either way the regression test must **call the real lane** rather than copy it, or the next
re-ordering of that callback reopens the hole silently.

## Related

* `docs/KARAOKE_LYRICS_MOUNT_PROPOSAL.md` - the Slice 2 mount correction, unrelated.
* The "sidebar still shows A♭ after End Set" observation recorded earlier as display residue is
  **not** residue: the sidebar is faithfully showing a store that really holds A♭. The separate
  display-residue QA item should be re-checked once this is fixed.
