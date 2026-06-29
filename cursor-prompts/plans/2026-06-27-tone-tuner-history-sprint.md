# Tone & Tuner History sprint

**Date:** 2026-06-27 · **Branch:** `dev` · **Status:** Implemented (pending commit)

## Goal

Saved history/library for tuner/tone sessions on the Practice page — save takes after sustain analysis, instrument-filtered library, lazy audio via `music-media` storage, AMI summaries (no blobs).

## Architecture

- **Schema:** `tone_takes[]` in media catalog (`media_state.py`)
- **CRUD:** `media_persistence.py` (`add_tone_take`, `update_tone_take`, `delete_tone_take`)
- **Storage:** `media/tone_takes/{id}.wav` + Supabase `tone_takes/` prefix (`media_storage.py`)
- **Service:** `media_tone_catalog.py` — note context, save/load, AMI helpers
- **UI:** `tuner_tone_ui.py` + `tone_take_history_ui.py` on Practice page
- **AMI:** `build_media_ami_payload_from_catalog` → `tone_history`; wired in `practice_log_ami.py` + `music_ami_context.py`

## Acceptance

- [x] Save Flute + Tenor Sax takes with written/concert notes for transposing instruments
- [x] Default history filtered by active instrument; All instruments view
- [x] Filter by note, best/needs work, play, delete (tombstone)
- [x] Audio storage_ref/local_path; lazy playback
- [x] AMI payload grouped by instrument; no raw audio/base64/blob
- [x] `?dev=1` tone diagnostics
- [x] Tests: `tests/test_media_tone_catalog.py`

## Out of scope

- Attack quality scoring (field reserved; not computed yet)
- Cross-instrument AMI comparison UX (payload supports trends; coach copy TBD)
