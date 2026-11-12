# Issue 69 Part D — how a Practice Key reaches the music

Written for whoever next changes key handling, Karaoke or backing. It records what the
code does today, where the two authorities meet, and which of those joins are load-
bearing — because the reported defect was not a broken transposer but a disagreement
between two correct owners.

## The reported symptom

Practising *Say* with the Practice Concert Key moved off the song's original B-flat:

| Surface | Showed | Should have shown |
| --- | --- | --- |
| Phrasing Guide, Intro cue | `B♭ · E♭ · Bm · A`, later `D♯♭ · G♯♭ · Bm · A` | `D · G · Bm · A` |
| Chord tiles | `Dsus4`, `Dsus4/E` | agreed |
| Current / Next Chord | `Csus4/D` | `Dsus4/E` |

Two unrelated causes. The cue line was a text-transposition defect (Parts A and B); the
Current Chord was an ownership disagreement (Part C).

## The transposition engine is not implicated

`music_theory.transpose_chord` is correct for every case in the report, including
typographic accidentals and slash chords:

```
B♭  +4 → D          E♭ +4 → G
Csus4/D +2 → Dsus4/E
D/F♯   +2 → E/G♯
A/C♯   +2 → B/D♯
```

Nothing here needed a second engine, and nothing was added.

## Path 1 — chord symbols inside prose (cues, Phrasing Guide)

```
song_catalog/curated_songs.py   lyric_cues: {"Intro": ["Instrumental — B♭ · E♭ · Gm · F"]}
        │                       literal text, in the song's own original key
        ▼
musician_coaching.transpose_lyric_cues / transpose_lyric_cue
        └── adapt_text_to_practice_key(text, catalog_key, practice_key)
                ├── _CHORD_IN_PROSE  ── matches a chord symbol in prose
                └── music_theory.transpose_chord
        ▼
lyrics_presentation.phrasing_guide_html(section_lyrics, lyric_cues, …)
        └── takes NO key argument. It renders whatever it is handed, escaped.
```

The Phrasing Guide is a renderer, not a transposer. Anything wrong with its chords
happened upstream. Both Part A/B defects were in `adapt_text_to_practice_key`:

1. `_CHORD_IN_PROSE` spelled its accidentals `(?:#|b)` — ASCII only — so `B♭` matched as
   bare `B`, moved to `D#`, and the original flat stayed glued on: `D#♭`.
2. The catalog key's name was then replaced through the result as a plain substring, a
   second pass that could not tell prose from the first pass's own output. `D` → `F#`
   turned a correct `D#` into `F##`; `G` → `Bb` turned a correct `Gb` into `Bbb`.

Both are now one pass. The bare key name needs no rule: transposing it as a chord moves
the catalog key to the practice key by definition.

## Path 2 — the chord-event timeline (Current Chord, Next Chord, tiles, audio)

```
sections  (the chart, in chart_key)
    │
    ├── _capo_ctx / written-chart branch  (app ~18600)
    │       sections_for_backing = transpose_sections_dict(sections, chart_key, concert_key)
    │
    ├── Creative / Composition / Key-Cycle branches reassign sections_for_backing
    │
    └── KARAOKE SESSION  (app ~22077)   ← load-bearing
            if voice mode and karaoke session active and sections:
                sections_for_backing = sections
            # The karaoke chart is authoritative for the performance. Added because
            # _backing_musical.concert_sections is resolved from the sealed
            # BackingContext, which LAGS a karaoke transition: measured live, Perfect
            # rendered 4 chords and The Scientist 0.
    ▼
_humanized_backing_sections(...)  →  performed_sections
    ▼
chord_events_for_selected_sections(performed_sections, selected_section_names)  →  backing_events
    ▼
_cached_backing_timeline(signature, backing_events=…)   →  timeline
    │   signature = _backing_signature_for_bpm(bpm), whose 2nd element is
    │   _audio_signature_key:
    │       normally  progression_key_audio or practice_concert_key
    │       key cycle  temporary_playback_key
    │       KARAOKE   km.current_session_practice_key()   ← the ENTRY's key (app ~22213)
    ▼
playback_follow_position(timeline)  →  event["chord"], event["next_chord"]
    ▼
app_ui.follow_along_status_html(pos)  →  "Current chord" / "Next"
```

and in parallel, once a take is generated:

```
backing_key_cycle.stash_audible_arrangement_after_generate(timeline, signature, chart_html…)
    ├── _kc_audible_follow_timeline (+ _signature, _space)   the timeline actually installed
    ├── _last_backing_timeline      (+ _signature)
    ├── _kc_audible_chart_html / _kc_last_open_chart_html    the chords on screen
    └── _kc_audible_signature
    # "Each timeline carries the signature (and so the key) it was rendered in."
```

## Where the two authorities meet

| Authority | Set by | Drives |
| --- | --- | --- |
| Global **Practice Concert Key** | sidebar widget → `songs.practice_key_state` (pick-scoped store, override marks, commit tokens, Fixed Key) | sidebar, `display_key`, chart tiles outside a performance |
| Karaoke **entry** `practice_key` | frozen when the song is queued; `_snapshot_practice_key` at `add_to_queue` | `_audio_signature_key`, the re-asserted karaoke chart, the timeline, Current / Next Chord, the audible take |

The flow between them ran **one way only**: `apply_entry_practice_key` pushes entry →
session. Nothing pushed back, deliberately — a global change must not re-key a song that
is merely being *edited* in another key elsewhere. So moving the Practice Key moved the
tiles and left the performance where it was, and both displays were correct by their own
rule. That is the whole of Part C.

## What changed in Part C

`karaoke_mode.retune_now_singing_entry(session_state, key)` — the single authorized
writer, modelled on `record_entry_feel_override` ("Keep an explicit Feel / meter change
with the entry being sung"), which is the architecture's existing answer to the same
shape of problem.

* **Reached only from the sidebar's own `on_change`.** A callback fires for a musician's
  action and nothing else, so reruns, hydration, page navigation and backing updates
  cannot re-key a performance. Proven from the other side too: writing the Practice Key
  store directly still leaves `current_session_practice_key` unchanged, because the store
  has no route into the queue.
* **Now Singing only**, written back through `_write_queue`; other queued entries and
  every other field of the row are untouched.
* **The old key's audio and chords are dropped together** — the take is retired via
  `bump_karaoke_playback_generation`, and so are
  `_last_backing_wav*`, `_last_backing_signature`, `_backing_wav_building_signature`,
  `_kc_current_static_url`, `_kc_arrangement_url`, **and** the timeline and chart state
  listed above. Clearing only the audio would have left the tiles and the Current Chord
  reading the old key — the original defect, reintroduced by its own fix. This map is
  what caught that.
* **Deliberately not** the song-change reset: tempo, scope, section selection, play
  session and Backing context survive, because a key change happens *inside* one song.
* **Transport** through `backing_transport_intent`: `stop_playback` if it was playing,
  then `note_playback_settings_changed` so a paused take resumes in the new key.
* **Controlled transition**: `pending_` / `confirm_` / `rollback_now_singing_retune`. A
  failed regeneration restores the previous key and retires the failed take. Re-keying to
  the key already in force is a no-op, so there is no double transposition and a correct
  performance is never silenced.
* **A notice names the moment** — the new key with the old one, or, on failure, which key
  the performance is still in. The sidebar is never left claiming D while the music is
  quietly in C.

## Recorded takes are not touched

A karaoke queue entry carries `entry_id`, `pick_key`, `source`, `practice_key`,
`play_count`, `title`, `artist`, `bpm`, `groove`, `meter` — and no recording identity,
take id or audio reference. There is nothing in it to relabel. Saved takes keep their own
`recording_concert_key` in the media catalog, which is Issue 64's work and is reached
from a different path entirely. Asserted three ways: the absent fields, an AST check that
the retune imports nothing and calls nothing matching delete/save/store/catalog/media,
and `mt_tracks` plus the media-catalog cache surviving a retune unchanged.

## Still true after this work

* The **original** key of a song is catalog metadata and is never written by any of this.
  (The separate Issue 74 report — Original Key appearing to follow the Practice Key on
  Missions — is a different surface and is not addressed here.)
* **Concert**, **instrument-written** and **capo-shape** keys stay distinct: the written
  branch at app ~18600 converts the chart to concert for the backing precisely because
  reading and sounding are different, and the karaoke re-assertion does not disturb that
  for non-performance paths.
