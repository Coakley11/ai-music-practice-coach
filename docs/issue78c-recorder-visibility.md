# Issue 78C — the Record button was four pixels tall

Branch `fix/issue-78c-recorder-visibility`, off `origin/dev` `378fad17`.
**Not integrated. Integration needs separate approval.**

Urgent follow-up to Slice 78B: reported from an Android phone, where the Multitrack page showed
"Record — Sax / winds" and, beneath it, a thin red horizontal line and nothing else. No microphone
icon, no Record button, no count-in control, no error message.

---

## What was wrong

Three facts combined, all of them introduced by 78B's decision to mount the shared recorder inside
the per-layer panel.

1. **The layer panel is collapsed exactly while the layer is empty.**
   `streamlit_music_practice_app.py` opened it with
   `st.expander(f"Layer controls — {slot}", expanded=_slot_ready)`, and `_slot_ready` is
   `bool(mt_tracks.get(slot))`. A musician who has not recorded yet is, by definition, looking at a
   collapsed panel.

2. **A hidden iframe has no layout, so it measures zero.** The component's only height report was
   `send("streamlit:setFrameHeight", {height: document.body.scrollHeight + 4})`. Mounted inside a
   collapsed expander, `scrollHeight` is `0`, so it published **4 px** — and there was no floor.

3. **Opening an expander sends no render.** Expanding is pure client-side DOM. No
   `streamlit:render` message arrives, and `status()` — the only other caller of `setHeight()` —
   never runs again. The frame stayed 4 px tall for the rest of the session.

The Record button is in the component's *static HTML*, so it existed the whole time; its background
is `#ff4b4b`, Streamlit red. **The "thin red horizontal line" was the top sliver of the Record
button**, with the control, the count-in label, the "Preparing recorder…" message and the
"Microphone unavailable" message all below the fold of a 4-pixel window.

This is **not mobile-specific**: it affects every empty layer on every device. A phone is simply
where someone looked without first clicking something else.

The same component works on the Missions page because Mission renders it in a plain, always-visible
`st.container()` (`mission_upload_recording_ui.py`), never inside a collapsed expander.

## Why 78B's acceptance passed anyway

This is the important part, and the failure is in the harness, not in Streamlit.

The 78B gates measured the Record button's bounding box **inside the component's own
`contentDocument`**. That box is correct whatever the size of the iframe around it. They then
clicked the button **programmatically**, which also works at 4 px. The 390 px and 360 px checks
measured the page's horizontal overflow and the button's inner box — never the iframe's own height.

So the harness drove, and reported on, a recorder that no human could see: 52/52 component gates and
65/65 real-app gates, with the feature unusable. **A visibility test that cannot see clipping is not
a visibility test.**

## What was changed

Three changes, none of them touching capture, scheduling, the count-in, the handshake or the Align
contract. The 78B architecture is intact, and a test asserts the scheduling anchors are unchanged.

### `mission_recorder_component/index.html`

* **A floor.** `MIN_FRAME_H = 52` — one button row and its padding. The frame is never reported
  shorter than the control itself, so even if nothing ever re-measures, the button is visible and
  tappable.
* **Zero means "not laid out yet", not "zero tall".** `measuredHeight()` returns `null` for a
  measurement of 0 and `setHeight()` holds the floor instead of publishing it.
* **It re-measures when it becomes visible.** A `ResizeObserver` on `document.body` — the body goes
  from no layout to laid out the instant the expander opens, which is exactly the event that was
  missing — plus `resize` and `visibilitychange` listeners, plus a **self-limiting** 500 ms
  interval as a fallback for browsers without `ResizeObserver`. The interval stops as soon as a
  genuine measurement has been published, and gives up after 20 s, so no permanent timer is left
  running in any layer's iframe. Every `streamlit:render` re-arms the watch, because a layer can be
  collapsed and reopened later and the reopening sends no render of its own either.
* A height is published only when it actually changes, following the pattern
  `backing_transport_component` already uses in this codebase (initial fixed 52 px, re-measure,
  `Math.max(52, h)`).

### `multitrack_takes.py` and the Multitrack page

* `auto_open_slot()` — **one** empty layer starts open so the recording control is discoverable
  without a tap: the first slot with no audio. Opening every empty layer would make the phone page
  enormous, which the review ruled out. The decision is taken **once per session** and remembered,
  so a layer the musician deliberately collapses stays collapsed rather than springing open on the
  next rerun (Streamlit re-applies `expanded` on every rerun, so recomputing it would fight the
  user). A slot that already holds a take opens exactly as it did before.

## How it is verified

`scripts/_accept_issue78c_visibility.py` measures what a person sees, and refuses the mistake that
let this through:

* the **iframe element's own rectangle in the page**, and whether the button *and* the status text
  fit inside it;
* a **hit test** at the button's centre in page coordinates (`elementFromPoint`), so a control
  clipped out of its frame fails even if its inner box looks right;
* **real pointer and touch input** — `page.mouse.click` at page coordinates and
  `page.touchscreen.tap` on the mobile runs. A programmatic `element.click()` is used nowhere as
  evidence;
* screenshots of the recorder area at each stage;
* the ten states the review listed: a fresh empty layer, expanding a collapsed layer, collapsing and
  reopening it, guitar / saxophone / flute, a Streamlit rerun, navigating away and back, recording
  and stopping, and desktop / 390 px / 360 px.

Deterministic cover in `tests/test_issue78c_recorder_visibility.py` (23 tests) pins the floor, the
zero-is-not-a-height rule, the re-measurement, the self-limiting fallback, the one-layer rule and
its once-per-session memory — and that the harness itself still measures the iframe rather than its
contents.

## Measured

Same harness, same ten states, three viewports, against the tree without the fix and with it.

| state | before | after |
|---|---|---|
| desktop, fresh empty layer | **frame 4.0 px** | **103 px**, button 35 px, status visible |
| desktop, after opening a collapsed layer | **4.0 px** | 103 px |
| desktop, collapse and reopen | **4.0 px** | 103 px |
| desktop, guitar / saxophone / flute | **4.0 px** each | 103 px each |
| desktop, after a Streamlit rerun | **4.0 px** | 103 px |
| 390 px / 360 px | 103 / 133 px once a re-render had been forced | 103 / 133 px from the start |
| microphone denied | — | 122 px, button visible, refusal explained |
| microphone unavailable | — | 122 px, button visible, browser limitation explained |
| **gates** | **29 / 38** | **55 / 55** |

A real touch tap through the frame starts recording ("Counting you in, then recording…", frame
84 px with **■ Stop recording**), a second tap stops it, and the take lands.

* 31 deterministic tests (`tests/test_issue78c_recorder_visibility.py`).
* **Mission recorder compatibility: 161 tests pass** with the shared component changed —
  `test_mission_music_capture`, `test_mc4_backing_handshake`, `test_mc4_generated_backing_recorder`,
  the full 78B live-recorder contract and 78C's own suite.
* **Matched regression vs `origin/dev` `f3d33016`, 277 shared files: 3858 test IDs both sides,
  0 disappeared, 0 new, 0 outcome changes, 0 regressions** (83 failures identical on both and
  pre-existing).

### Three faults the acceptance found that the unit tests could not

* **My own auto-open rule closed the layer it had just opened.** Deciding once per session meant
  the next rerun re-applied `expanded=False`. Streamlit re-applies that value on every rerun, so
  the control the musician had just been given closed itself. It now stays open on every render
  while the project holds no audio at all, and stops once any layer has a take.
* **A denied microphone showed the ready text.** The error was written and then painted over by the
  following render. The component now remembers its last microphone failure until the next attempt.
* **An unavailable microphone showed a raw `TypeError`.** The common failures are now named in
  plain words, each offering the alternative that genuinely exists here: Upload.

### And three in the harness, all the same family as the defect itself

Scrolling and hit-testing in one `evaluate()` (a control below the fold read as "not hittable");
`page.screenshot(clip=…)` taking page coordinates while `getBoundingClientRect()` returns viewport
coordinates (the evidence photographs were offset by the scroll); and `elementFromPoint` arithmetic
as the oracle, replaced by `frame_locator(...).tap()` so the browser's own actionability checks
decide — they raise when a control cannot receive the event, which is the guarantee this acceptance
is about.

## Deployed version — still unknown

I have not obtained the runtime release SHA of the hosted app, so which build the phone was running
remains open. What is established:

* `origin/main` is **`5ef2dead`** and contains neither 78B nor Issue 79; the project's own
  `docs/DEV_WORKFLOW.md` notes that production tracks `main`.
* 78B reached `origin/dev` at **`12764ddf`** (2026-11-13), and Streamlit Cloud redeploys `dev` on
  push.
* No deployment was performed by me.

The app computes its own commit at runtime (`git rev-parse HEAD` → `_studio_ui_release_sha`) and
shows it in the sidebar caption; that line settles it. Two faster tells inside the layer: the 78B
recorder's button reads **"● Record with count-in"** when a count-in is configured, and its status
line uses the phrase **"on one clock"** — neither string exists before 78B.
