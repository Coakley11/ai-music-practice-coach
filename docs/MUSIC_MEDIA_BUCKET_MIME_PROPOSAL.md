# Proposed: allow reference types on the `music-media` bucket

**Status:** proposal only. **Nothing has been applied to any live bucket**, and nothing here can
be applied without the project reference and your approval.

## Why

A PDF reference uploaded from a phone was kept on the device and refused by the cloud:

```
415 invalid_mime_type: application/pdf is not supported
"Saved 1 reference, 1 on this device only."
```

The app declared `application/pdf` (now it declares the type each file really is). Audio uploads
to the **same** bucket succeed, so the bucket is restricting its allowed types rather than
failing. References therefore cannot follow a musician to another device.

## What I could establish from the repository

| Question | Answer | Confidence |
|---|---|---|
| Bucket name | `music-media` (`media_storage.DEFAULT_BUCKET`), overridable per deployment with `MUSIC_MEDIA_STORAGE_BUCKET` | certain, from code |
| Credentials | `[suite_activity] supabase_url` / `supabase_key` in Streamlit Cloud Secrets, or `SUITE_SUPABASE_URL` / `SUITE_SUPABASE_KEY` locally (`suite_storage_config.py`) | certain |
| Key type | the **service-role** key (`supabase_key = "YOUR_SERVICE_ROLE_KEY"`) | certain |
| Project shared? | **The Supabase project is shared.** `suite_storage_config.py`: "credentials for shared suite activity (all deployments) … Same block on Command Center and every suite app", "Same on phone, laptop, and every suite app (unified account memory)" | certain, from code |
| Content types this app sends to the bucket | `audio/wav` (recordings, tone takes, mix exports), and for references the file's own type — `application/pdf`, `image/jpeg`, `image/png`, `image/heic`, `image/heif` | certain |
| Staging bucket | **none is configured.** One bucket name, one project; local and CI use the same credentials | certain |

## What I could NOT establish, and will not guess

- **The exact project reference and environment.** It lives in Streamlit Cloud Secrets, not in
  the repository (the repo carries only a `YOUR_PROJECT_REF` placeholder). No credentials are
  present in this development environment, so I could not read it.
- **The complete existing allowed-MIME list.** That is server state. It cannot be read without
  credentials, and I have not attempted to reach your project.
- **Whether other suite apps write to `music-media` specifically.** The *project* is certainly
  shared; this repository is the only place I can see that names this bucket. Other suite apps'
  code is not available to me.

### Read-only commands to answer those three

Run with the service-role key for the project (read-only; changes nothing):

```bash
curl -s -X GET "$SUITE_SUPABASE_URL/storage/v1/bucket/music-media" \
  -H "Authorization: Bearer $SUITE_SUPABASE_KEY" -H "apikey: $SUITE_SUPABASE_KEY"
```

The reply gives `id`, `public`, `file_size_limit` and `allowed_mime_types` — the current list.
`GET /storage/v1/bucket` lists every bucket in the project, which shows whether other apps have
buckets of their own (and so whether this one is likely theirs too).

## The proposed change — additive only

Add five types to `allowed_mime_types`, **keeping every existing entry**:

```
application/pdf
image/jpeg
image/png
image/heic
image/heif
```

Dashboard: Storage → `music-media` → Settings → Allowed MIME types → append.

Or, equivalently, with the current list read first and re-sent in full plus the new entries:

```bash
# EXISTING must be the exact list the GET above returned.
curl -s -X PUT "$SUITE_SUPABASE_URL/storage/v1/bucket/music-media" \
  -H "Authorization: Bearer $SUITE_SUPABASE_KEY" -H "apikey: $SUITE_SUPABASE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"allowed_mime_types": [ EXISTING..., "application/pdf", "image/jpeg", "image/png", "image/heic", "image/heif" ]}'
```

**The PUT replaces the list**, so the existing entries must be read and included or audio
uploads break. That is the one way this change could cause harm, and it is why the GET comes
first and why nobody should type this from memory.

## Compatibility and security impact

- **Audio is unaffected** provided the existing entries are preserved verbatim. Nothing in the
  change touches `audio/*`.
- **Privacy is unchanged.** The bucket stays private; `public` is untouched. Objects keep their
  per-user key prefixes (`build_song_document_object_key` scopes every object under the user id),
  so no cross-user exposure is introduced.
- **No RLS or access-control change.** None is proposed, and none is needed for this.
- **What does widen:** the app authenticates with the service-role key, which bypasses RLS, so
  the bucket's MIME list is one of the few restrictions actually in force at upload time. After
  the change it will also admit PDFs and those four image types. That is the intended effect, and
  it is the narrowest list that supports the feature — no `image/*` wildcard, no
  `application/octet-stream`.
- **The project is shared with other suite apps**, so this is a shared-resource change. If
  another app relies on `music-media` refusing PDFs or images as a guard, this would weaken that.
  I cannot rule that out from here; the bucket listing above is the cheapest way to find out.
- **`file_size_limit`** is not proposed for change. If it is currently below 50 MB, the app's own
  50 MB document limit would be the looser of the two and large scans would still be refused by
  the store — worth reading in the same GET.

## Validating without touching production

No staging bucket exists today. Two options, in order of preference:

1. **An isolated test bucket**, in a non-production project if one exists, or a new private
   bucket such as `music-media-mimetest` with only the five new types. Point a local run at it
   with `MUSIC_MEDIA_STORAGE_BUCKET=music-media-mimetest` — the override already exists, so no
   code change is needed — and upload a PDF, a JPEG, a PNG and a HEIC. Creating a bucket is still
   a live storage change and needs your approval.
2. **Read-only confirmation first:** the GET above tells us whether `application/pdf` is genuinely
   absent, which confirms the diagnosis before anything is altered. This costs nothing and risks
   nothing, and I would do this first in either case.

## Meanwhile, in the app

References keep their correct validated content type. The `application/octet-stream` bridge is
**off by default** and only runs with `MUSIC_DOCUMENT_CLOUD_TYPE_BRIDGE=1`, as a deliberate,
temporary way to get references off a single device while the bucket is still refusing them. A
file should keep the type it really has, and the fix is the bucket.
