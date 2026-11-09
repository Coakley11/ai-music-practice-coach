# Issue 62 — prepared integration for `streamlit_music_practice_app.py`

Everything else in this branch lives in isolated modules. The two changes below have to go
into `streamlit_music_practice_app.py`, which three branches owned by the other agent are
also editing, so they are kept here as a patch rather than committed to the shared file.

## The patch

`issue62-multitrack-capture-quality.patch` — apply from the repository root:

```sh
git apply prepared_integration/issue62-multitrack-capture-quality.patch
```

It makes two edits inside the `elif _studio_page == "multitrack":` block:

1. **Install instrument-friendly microphone capture** for every layer mic, by calling
   `install_multitrack_music_capture(st, st.session_state, MT_SLOTS)` once before the slot
   loop. This reuses the existing `mission_music_capture` script — it is not a second
   mechanism — so the Multitrack mics get `echoCancellation / noiseSuppression /
   autoGainControl: false` the way the Mission recorder already does.

2. **Capture at a musical sample rate.** `st.audio_input` defaults to `sample_rate=16000`,
   a speech rate whose 8 kHz ceiling removes the upper partials of high flute notes,
   saxophone edge and guitar attacks. The patch passes
   `sample_rate=capture_sample_rate()` (48 kHz). The keyword is passed through a kwargs
   dict so an older Streamlit without the argument still renders the recorder.

Both call into `multitrack_capture_quality.py`, which is committed on this branch and
covered by `tests/test_multitrack_capture_quality.py`.

## Conflict risk: none measured

| Branch | Hunks in the app file | Line range |
| --- | --- | --- |
| `integrate/backing-controls-20261109` | 9 | 534 – 25220 |
| `integrate/chord-tone-hints-levels-20261109` | 3 | backing / key-cycle region |
| `feature/backing-loudness-match` | 1 | backing region |
| **this patch** | **2** | **27747, 27805** |

The patch touches only the Multitrack page; the other branches stop well short of it.
`git apply --check` passes against `origin/dev` (3326a87e).

## What still needs verifying in a browser

The patch is covered by unit tests at the policy level only. Two things cannot be settled
without recording through a real microphone in a real browser:

- that the 48 kHz request is actually granted by the device, and the returned WAV really
  carries content above 8 kHz;
- that the mic-constraint script matches the Multitrack widget keys. The key for a slot
  contains spaces and a slash (`mt_record_Sax / winds`), and the frontend rewrites those
  into the element's `st-key-*` class. `widget_key_class_candidates` offers every plausible
  spelling so that one of them matches, but which one the browser produces has not been
  observed. `window.__mcMusicCapture.takes[-1].settings` in the browser console reports the
  constraints the track actually received and is the quickest way to confirm it.
