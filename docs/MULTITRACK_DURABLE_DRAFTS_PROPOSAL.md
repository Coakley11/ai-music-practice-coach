# Proposal: durable Multitrack drafts (stage 2)

**Status:** design only. Nothing here is built, deployed, or applied to Supabase. Stage 1 (a
temporary file per take on the app server's disk) is implemented locally on
`fix/multitrack-backing-delivery` and is what this builds on.

## The problem stage 1 cannot solve

Measured on the current code (browser, isolated data, a local Supabase stand-in for tables and the
storage bucket, strict egress; `scripts/_accept_mt_draft_reload.py`,
`scripts/_accept_mt_save_project_durability.py`):

| take | workspace save | stage 1 file | survives refresh | survives a Cloud restart |
|---|---|---|---|---|
| 3 s (0.50 MiB) | kept | kept | yes | **no** (not uploaded) |
| 30 s unsaved (2.97 MiB) | **dropped** (2 MiB cap) | kept | yes (stage 1) | **no** |
| 30 s **with Save layer** | **dropped** | kept, marked saved | yes (stage 1) | **no** |
| ~70 s unsaved (6.38 MiB) | **dropped** | kept | yes (stage 1) | **no** |
| 88 s **Save layer + Save project** | dropped | kept | yes | **yes - bytes in the bucket** |

The workspace save passes every layer, saved or not, through `MAX_MT_TRACK_BYTES = 2 MiB` - about
11 s of the recorder's 48 kHz mono 16-bit audio. Stage 1 keeps each take as a file on the app
server's disk, which a Streamlit Cloud restart, sleep or redeploy replaces. **Save layer alone is
therefore not durable for a long take; Save project is.**

### Save project, measured (88.09 s, 8,456,748 bytes)

- The take's exact bytes (same SHA-256) are uploaded to the private `music-media` bucket under
  `<user_id>/<workspace_id>/multitrack/<project_id>/<track_id>.wav`, and decode at the same length.
- The project row reaches the cloud library (`suite_saved_items`).
- After the app server and its disk were replaced, **New Project, then Load** brings the layer back
  with the same fingerprint, decoded to the same 88.09 s; so does another new session after that.
- **Defect found (fixed in 58d09353, see below):** every reopened session - same server, after a restart, another session - shows
  the project as *currently loaded* with **no audio**, no Load button, and the hint "Record or
  upload at least one layer". The workspace restore brings back the active project id, the 2 MiB cap
  dropped the layer, and nothing re-fetches it from the library; a deliberate Load is the only path
  that calls `load_track_audio`. A musician would reasonably conclude the recording is gone.
- **Defect found (fixed in 58d09353):** `persist_track_audio` returned `ok: True` when only the local copy was written
  (`if local_ok or storage_ref`), so a failed upload is reported as a saved project. The save message
  must distinguish "saved to your account" from "kept on this server only".
- Not established here: synchronized playback of the reopened project. The transport timing check
  scheduled nothing within its fixed wait for an 8 MiB layer, and the test project had no saved
  backing to align against. Needs a longer-wait timing run or a real-app playback check.

## Goals (from the request)

1. Keep unfinished recordings without treating them as saved layers.
2. Isolate by user, song and project, with authorization.
3. Respect the strict-egress policy rather than bypass it.
4. Full-length audio, never inside the workspace JSON.
5. Claim a draft is protected only after a verified upload and read-back.
6. Quotas, retention and cleanup of discarded drafts.
7. Preserve existing recordings and privacy.

## Design

### Where the bytes go - reuse the library's track storage

The measurement above settles the earlier open question: the project library already stores a
full-length layer durably, as its own object in the private `music-media` bucket, and reads it back
through `load_track_audio` (local first, then a server-side download). Stage 2 reuses that
mechanism instead of adding a parallel store:

```
<user_id>/<workspace_id>/multitrack-drafts/<identity_hash>/<slot_hash>.wav     (draft audio)
<user_id>/<workspace_id>/multitrack-drafts/<identity_hash>/<slot_hash>.json    (sidecar)
```

- Same upload/download functions as `persist_track_audio` / `load_track_audio`, with a separate
  `multitrack-drafts/` prefix so a draft is never mistaken for a saved library track and can be
  swept without touching saved work.
- `user_id` and `workspace_id` lead the key exactly as `build_supabase_object_key` does today.
- `identity_hash` and `slot_hash` are the stage-1 hashes (workspace + song + project, and the slot).
  **No title or slot text ever becomes part of a key**, as in stage 1.
- The sidecar holds the stage-1 record - identity, slot, SHA-256, timing, alignment controls, name,
  source, saved state - and is checked on every read. A draft whose identity does not match the
  session is not returned.
- **No bucket configuration change is needed** (`allowed_mime_types: null` on this bucket).

### Authorization - stated plainly

The app writes with the **service-role key**, which bypasses Row Level Security. So isolation does
not come from the database; it comes from three things the app controls, all of which stage 1 already
does locally:

1. the key prefix is built from the authenticated `user_id`, never from anything the browser sends;
2. the sidecar's identity must match the session's on every read;
3. downloads happen server-side - the browser never receives a storage URL, signed or otherwise.

If per-user RLS is wanted later, it is a separate decision; nothing here depends on or weakens it.

### When an upload happens, and strict egress

Stage 2 must not ride on autosave - under `MUSIC_EGRESS_STRICT`, autosave cloud writes are blocked
**by design**, and bypassing that would defeat the policy. Instead:

- **One upload per take, when the take lands.** Recording a take is an intentional act, so it fits
  the policy's own category of "intentional user actions" - one bounded write, not a stream.
- That needs **one new allowed reason**, e.g. `multitrack_take_recorded`, added to
  `_STRICT_INTENTIONAL_USER_SAVE_REASONS` beside the existing `multitrack_layer_save` and
  `multitrack_upload`. That is a policy change and needs its own approval.
- Uploads are bounded by the quotas below, so a burst of re-recordings cannot become unbounded
  egress.

### "Protected" means verified

The status line changes only after the upload is proven:

1. upload the WAV and the sidecar;
2. read the object back (a ranged read of the header plus the stored size, or a full download for
   short takes) and compare the SHA-256 recorded in the sidecar;
3. only then: **"Unsaved Draft — protected in your private storage."** Until then, and if any step
   fails, the line stays **"Unsaved Draft — Temporary"** with the stage-1 limitation.

A failed upload is never retried silently in a loop: it is retried on the next landed take or on an
explicit **Retry protecting this draft** action, and the reason is shown.

### Recovery

On the Multitrack page, for each slot with no live audio and no stage-1 file (the case a restart
leaves), list the draft object for this identity and slot, download it server-side, verify the
SHA-256, and restore it with the saved state its sidecar records - **before**
`adopt_restored_layers_as_saved`, exactly as stage 1 does.

### Save layer becomes durable too

The same mechanism with `saved: true` closes the second defect: **Save layer** uploads (or keeps)
the layer as its own verified object, so a saved song-length layer survives a restart instead of
existing only in session.

### Two fixes that do not need stage 2 - DONE (58d09353, local)

1. **The active project's audio comes back on restore** (`multitrack_project_audio_restore`): each
   slot the saved project records as playable and the session lacks is fetched through
   `load_track_audio`, validated, marked a saved layer, cached for the session and refilled on every
   rerun; drafts restore first; a deliberately removed layer stays removed. Browser: back without
   pressing anything in a new session, after a server replacement and in a second session after
   that; Play decodes the full 90.38 s buffer and starts it.
2. **Honest Save project message.** An upload counts only once the bucket lists the object at the
   size sent (`verify_uploaded_object`); "saved to your account" only when every layer is verified,
   otherwise the message names what is kept on this server only. Browser: verified in a simulated
   outage.

Still not established: playback in sync with a SAVED backing - the tested project saved no backing
audio, so only the layer started. Alignment was tested at the default offset only.

### Quotas, retention, cleanup

| rule | proposal |
|---|---|
| per-user draft storage | 250 MB, oldest unsaved drafts evicted first, with a visible notice |
| per-project draft count | one per slot (a new take in a slot replaces its draft) |
| idle retention | 14 days for unsaved drafts, matching stage 1's sweep |
| discard | delete the object and write a tombstone of its SHA-256 in the sidecar's place |
| save to library | the draft object is removed once the library copy is verified |
| saved layers | never evicted by the draft quota |

Tombstones are what make "a discarded take never comes back" hold across devices and restarts: a
stale object that failed to delete is refused by hash, exactly as stage 1 refuses a stale file.

### Privacy and existing recordings

- The bucket stays private; no public or signed URL is created.
- The new prefix is separate from `recordings/`, `song-documents/` and every existing key, so no
  existing object is read, moved, overwritten or deleted by draft handling.
- Draft audio is never logged; the trace records sizes and fingerprints only.

## Open questions before building

1. ~~Is the library save durable for long takes?~~ **Measured: yes** (88 s take, exact bytes in the
   bucket, recovered after a server replacement). Stage 2 reuses it - see "Where the bytes go".
2. **The strict-egress reason** - approve `multitrack_take_recorded` (or prefer upload only on Save
   layer, accepting that unsaved drafts stay temporary).
3. **The quota** - 250 MB is a placeholder; it should be set against real per-user storage costs.

## Rollback

Stage 2 is additive: a new prefix, a new reason, new code paths behind the same checks. Disabling
it is removing the allowed reason and the upload call; stage 1 keeps working unchanged, and any
draft objects already written can be removed by deleting the `multitrack-drafts/` prefix, which
nothing else uses.
