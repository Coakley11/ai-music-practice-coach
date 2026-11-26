# `music-media` bucket: compatibility after the 2026-11-19 settings

**Applied by the owner on 2026-11-19** to project Daniel AI Suite (`qhprdlwoxjpkiukxhftp`), bucket
`music-media`:

- file size limit: 50 MB;
- Restrict MIME types: on;
- allowed types: `audio/*,application/pdf,image/jpeg,image/png,image/heic,image/heif`.

Nothing in this document changes any backend setting. Everything below comes from reading the code on
`feature/uploaded-melodies-references`, merged onto dev `5caee5e3`. The project itself was not read
from here.

## 1. What MP4 and MOV uploads actually send

**In the current Upload Analysis flow, a video is never stored as a video.**

1. `upload_media.prepare_upload_for_analysis` decodes MP4, MOV and other containers to **mono WAV**
   and renames the file `<name>.wav`.
2. The app keeps that WAV as the analysis audio. Its name (`<name>.wav`) becomes
   `last_analysis_source_label`.
3. `media_upload_catalog.build_upload_recording_fields` marks a recording as video only when that
   name ends in `.mp4`, `.mov`, `.webm` or `.mkv`. Since the name is `.wav`, the row is
   `media_type: audio`, `mime_type: audio/wav`.
4. The cloud upload declares the row's type, `audio/wav`, which `audio/*` allows.

**`video/mp4` is sent in one case only:** re-saving an older Upload History row whose stored filename
is still a video name. Opening a saved row sets the label from `rec.filename`. Even then the bytes are
WAV audio, and the type is mislabelled. **`video/quicktime` is never sent:** the only video type the
code can declare is `video/mp4`, for MOV as well.

### Exact list

- **No change needed for current behaviour.** Keep:
  `audio/*,application/pdf,image/jpeg,image/png,image/heic,image/heif`
- **If you also want the legacy re-save path covered**, this is the smallest addition:
  `audio/*,video/mp4,application/pdf,image/jpeg,image/png,image/heic,image/heif`
  Adding `video/quicktime` would change nothing, because the app never sends it.
- **Recommended app-side fix instead (small, not made yet):** declare `audio/wav` for every stored
  analysis recording, since the stored bytes are always the analysis WAV. Then no video type ever
  reaches the bucket. A related mislabel: an MP3 or M4A upload keeps its own bytes but is declared
  `audio/wav`. `audio/*` allows it either way.

## 2. Recordings larger than 50 MB

**What happens today:**

| Size of the analysis audio | Local copy | Cloud copy | What the musician is told |
|---|---|---|---|
| ≤ 50 MiB and within the bucket limit | written | uploaded | "Saved to media catalog (…)" |
| between the bucket limit and 50 MiB (only if the dashboard's "50 MB" means 50,000,000 bytes) | written | **refused** (413) | the same "Saved to media catalog (…)" **(false: server only)** |
| > 50 MiB (`media_storage.MAX_RECORDING_BYTES`) | **not written** | **not uploaded** | the same "Saved to media catalog (…)" **(false: the audio is kept nowhere)** |

The 50 MiB cap is **older than the bucket change**: `_validate_audio_bytes` has always refused larger
audio before either copy is written. The app accepts **uploads** up to 500 MB, and that limit is for
analysis. Nothing has ever been able to *persist* more than 50 MiB. The new bucket limit does not
lower what is kept, but it makes the missing message matter.

**What is wrong:** `save_upload_recording_with_notes` returns success once the catalog row is written,
whatever the audio persistence returned. `studio_history_ui` then shows "Saved to media catalog".
That is a **false save confirmation**. For audio over 50 MiB it hides that the recording itself was
not kept, which is **silent loss** of the take: the analysis text survives, but the audio does not.

**Proposed fix (truthful messaging, no change to recording functionality):**

1. Return the persistence result alongside `ok`, and word the message from it:
   - "Saved — the recording is in your account."
   - "Saved on this server only — the cloud copy was refused (too large / type). A restart of the app
     can lose it." (warning)
   - "The analysis is saved, but this recording (*N* MB) is larger than the 50 MB storage limit and
     was **not** kept. Download it now to keep it." (error, with a download button for the audio
     still in the session)
2. Say the storage limit **before** saving, beside Save to History, when the audio is over the limit.
3. Test with a real 60 MB file in the browser: no "saved" wording may appear for the audio.

## 3. Options for durable recordings larger than 50 MB

None of these changes how recording or analysis works.

| Option | What it takes | Trade-off |
|---|---|---|
| **A. Store a compressed copy** (FLAC lossless, or Opus/AAC) for durability, and keep analysing the WAV | App change in `persist_recording_audio`: encode before upload (libsndfile writes FLAC already) | FLAC roughly halves a WAV, so about 17 min of mono 44.1 kHz instead of about 9.5 min. Opus at 96 kbps fits over an hour in 50 MB, but is lossy |
| **B. Raise the bucket's file size limit** | Backend setting, plus the project's global upload limit (plan-dependent) | Simplest, but limited by the Supabase plan. Uploads over ~6 MB should then use resumable (TUS) uploads |
| **C. Resumable (TUS) uploads** | App change to the upload call | Reliability for big files on phones. Does **not** lift the size limit by itself |
| **D. Split into parts** | App change: chunked objects plus a manifest | Works under any limit, but adds the most complexity and the most ways to break. Not recommended |

**Recommendation:** first the truthful messaging (section 2), because it stops the false confirmation
now. Then **A (FLAC)**, which keeps quality and needs no backend change. Then **B** only if longer
recordings matter.
