# Key Cycling follow-ups (recorded, not fixed)

Recorded 2026-11-14/15 when the Key Cycling upgrade was integrated into dev (`f8f55dea`).
That integration includes the transport fixes found during its QA:
- the Pause/Resume label (`00f77fcc`);
- the live-player Pause (`e9692f4d`);
- one Pause/Resume path for the Lead Sheet and the console (`0e975ee3`);
- Stop outranking an earlier Resume (`544ec028`, `1df14644`, `b47da0e9`).
- Pause or Stop cancelling a handoff already in flight (`be31fb18`).
- Resume never replaying a finished take, and a late Resume answer never stepping back (`7f8b4381`).
- One paused position at a take boundary, with the server following verified steps (`b65d278a`).
- A take marked playing is heard, Resume prepares the next key without waiting for the server,
  the cold load of a switched-in take runs, and the final key plays before the cycle ends (`f8f55dea`).
- The end-of-take switch promoting only the verified next key's take, never the finished one
  from the idle slot (`09b93037`).
- The completed final key ending the cycle on both the page and the server: the receiver now
  delivers `final_key_stop`, and the page never replays the completed take or offers Resume
  (`1139f3e1`).
- A new start after that end being a new cycle: the leftover completed take never ends it, and
  the console's Pause is usable at once (`e51e289a`).
- After Stop, a fresh Play showing Pause on the always-mounted console; listeners that must
  outlive the bridge frame registered by the parent realm (`d96f26e4`).

**None of the items below were changed by it.** Keep each one as its own item, so a fix
to one does not reopen the verified Pause, Resume and Stop behaviour.

---

## KC-F1. The server occasionally misses the confirmation of an automatic key change

**Seen:** during free-running playback (no Pause pressed), the page sometimes plays the
next key while the server's cycle key stays one behind. The server catches up on a later
handoff or at the next Pause.

**Rate:** about 6 per hour on the commit before the Pause fixes (`ebe7fd4f`): 6 skip
rejections and 1 `stale_epoch` in an hour of cycling. After `a6a497dc` it was about 3 skip
rejections and 2 `stale_epoch` per hour. **So it is pre-existing, and the Pause fix did
not cause it.**

**Confirmed 2026-11-14 (traced, real Lead Sheet and console buttons):** for Pauses
pressed 250 ms after an automatic change, the server was still one key behind when the
Pause arrived in 3 of 5 Lead Sheet presses and 2 of 4 console presses. Each time, the
Pause report's sounding key was adopted (`pause_report_adopt_sounding_key`, for example
Em→Am), so the frozen key was right. That is the existing protection doing its job. The
lost acknowledgment itself is still this item.

**Changed 2026-11-14 (`b65d278a`), for the Pause/Resume case only:** Pause and Resume epochs no longer make an ack stale (a Stop still does), and an ack two steps ahead is accepted when it comes FROM the expected key and plays the key after it in the same cycle. Acks lost for other reasons (network, a remount) are still handled only by that chained rule, so the root of this item (why an ack is lost) remains open.

**Where it is rejected:**
- `backing_key_cycle.py`, trigger `playing_ack_align_reject_skip`. An absolute-align ack
  whose key is not the next sequence entry is refused, so a key is never skipped.
  Once one natural ack is lost, the following one is two steps ahead and is refused too.
- `backing_key_cycle_handoff.validate_playing_ack`, reason `stale_epoch`. The ack's epoch
  is more than one behind `_kc_player_cmd_epoch`. That happens when two commands were
  issued while a take was handing off.

**Evidence to collect first:** with `MUSIC_APP_DATA_DIR` set, `_kc_handoff_acks.jsonl`
(events `validate`, with their reasons) and `_kc_key_writes.jsonl` (triggers containing
`reject`). Count them per hour of cycling. Then, for each rejection, look at the ack that
came before it. The working assumption is that the earlier ack was lost, not that it
was wrong. Do not confirm this by relaxing the skip guard. That guard is what stops the
"Fm ack saying Am" skip.

**Scope note:** fix this through the existing ack path (one owner of the cycle key). Do
not add a retry loop or a second writer of `current_playback_key`.

**One unreproduced observation that belongs here:** once, under heavy load (three other
jobs running, 1.4 GB free), a Lead Sheet Pause 250 ms after a change was heard on Ebm
but froze G#m, and Resume played C#m. The server reached G#m through a playing ack
(`playing_ack_advance_to_expected`), not through the Pause report. It was not
reproduced in 9 traced presses under normal load (5 Lead Sheet, 4 console), and in each
of those the frozen key matched the page's own sounding key. If it comes back, compare
`__kcAckLog` (page clock) with `_kc_key_writes.jsonl` around the press.

---

## KC-F2. Yellow "Playback settings changed" notice in shared Backing logic

**Where:** `streamlit_music_practice_app.py`, the `_show_regen_warning` block, about
lines 23120–23165 at the integration commit. It shows
`Playback settings changed… press Play Backing Track above to rebuild` when any of these
is true:
- `key_changed_this_run`
- a playable WAV is present while `BACKING_NEEDS_REGEN` is set
- there are regen reasons, such as a meter override

**Status:** this is an existing notice that the user raised. One cause came from Key
Cycling, and the upgrade fixed it: Play with cycling Off set "needs regenerate" over the
take being generated, so the notice showed over a fresh take. See the comment in
`backing_key_cycle.py` above `ensure_cycle_current_static_url`. The remaining cases are
in the shared condition above. **They were not investigated or measured** during the Key
Cycling work, so the first step is to reproduce them and name the trigger for each.

**Seen 2026-11-14, not investigated:** in the Mission Backing Stop tests,
`_play_trace.jsonl` logged `regen_warning_shown` with `needs_regen: true`,
`reasons: []` and `key_changed: false` on the runs right after a Key Cycling Stop.
`stop_key_cycle` sets `BACKING_NEEDS_REGEN` when the sounding key differed from the
saved Practice Key. That is a likely trigger to check first.

**Why it was left alone:** this is shared Backing logic, used by every Backing surface
and not only Key Cycling. The user explicitly excluded it from the Key Cycling Pause
work. A fix needs its own ownership decision: who says a rebuild is needed, and whether a
Key Cycling key change counts as a "settings change" at all. It also needs its own
regression across the Songs, Custom and Missions Backing paths. Each decision is traced
to `_play_trace.jsonl` as `regen_warning_shown` or `regen_warning_suppressed`.

---

## KC-F3. Slow server responses under heavy memory pressure

**Seen:** with about 0.7–0.9 GB of RAM free:
- Streamlit reruns that apply a browser ack lagged **10–30 s**.
- The server applied one Pause **8.5 s** after the click.

**Also measured 2026-11-14, with 2–3 GB free and nothing else running:**
- A Pause sent through the card channel (now also the Lead Sheet's path) was confirmed
  Held after **4–12 s**. The audio went silent at once; only the server's confirmation
  was slow.
- With playback running and the Lead Sheet open, the page's main thread is busy enough
  that a 100 ms sampler ran only every 1–2 s.
- After a Pause/Resume close to a take's end, the next key started **0.7–2.3 s** late
  (the page's own `gap_ms`), against 4–10 ms for normal handoffs.

The outcome stayed correct, because the page now ignores a pause or play instruction
built before the newest click, and Stop outranks an earlier Resume. Before those fixes,
this lag was what made Resume undo itself and a late Resume undo a Stop.

**Measured 2026-11-16 (`d01a0df3`, Shape of You, Guitar Shape, 3+ GB free, one browser):** in a
free-running boundary sweep, the server confirmed a Pause as Held after 1.82, 2.68, 3.16, 3.35,
3.48, 4.75 and 5.62 s, and one confirmation did not arrive within the probe's wait. The audio
went silent at once each time.

**Seen 2026-11-16 as audible silence (`5f5f9a7f`, six-round trace, start RAM 3.1 GB):** with Held
confirmed after 2.3-3.95 s in every round, the server left Held 4.4 s after a Lead Sheet Resume and
reached Dm 7.2 s after it, while the page had played Am's remainder and Dm. When Dm ended the page
still held no take for Gm (the server had not sent it), so it waited -- it never replays a finished
take (`09b93037`) -- and Gm started after more than 6 s of silence. The same build under normal load
(Held after 1.0-1.55 s) passed every round. The silence is the visible form of this item.

**Not a correctness bug now, but a responsiveness one.** Until the rerun catches up:
- the Key Cycling status row and the cards show the old state;
- the next take is prepared late.

**Starting points:** profile one ack-applying rerun under memory pressure, using the
heavy-memory method in the Key Cycling notes (one memory-ballast process with a safety
floor, one browser). Do not use `MUSIC_APP_DATA_DIR` for timing, because it turns on
debug traces that inflate the cost. Look at what the rerun does that is not needed to
apply an ack. Do not "fix" it with client-side timeouts or retries.

---

## KC-F4. "Back to loop start" still leaves Held through delayed timers

**Where:** `backing_key_cycle.py`, `parentWin.__kcSeekAndPlay`. From Held, it schedules
its server click and several play kicks with `window.setTimeout` (350 ms, and 0–2000 ms
kicks) on the bridge frame.

**Why it matters:** this is the same failure class as the fixed Lead Sheet Resume. That
Resume's 350 ms timer died when a Streamlit rerun replaced the bridge frame, so the
server stayed Held and the page's audio was paused again 1–3 s later (`0e975ee3`).

**Status:** not changed and not measured in a browser. Back to loop start is a different
action (seek to the loop's first chord, then play), so it was not folded into the shared
Pause/Resume press. Measure it first: Back to loop start from Held, then check whether
the server leaves Held and whether the audio keeps playing for 15 s.

---

## KC-F5. The Key Cycling click listener also catches other Pause/Resume buttons

**Reported 2026-11-15 by the usability work** (compact playback bar, `lead_sheet_page_follow.py`).

**Where:** `backing_key_cycle.py`, `parentWin.__kcOnTransportClick`. When no
`st-key-backing_key_cycle_*` class is on the click path, a fallback matches any
top-document `BUTTON` whose label reads "⏸ Pause" or "▶ Resume", or "Pause playback" or
"Resume playback", and calls `__kcPauseBtnHandler` and `__kcPauseRouted`. The fallback has
been there since `60d0095a` (2026-09-20); the Key Cycling upgrade did not add it.

**Effect:** the compact bar's `#ls-mini-pause` carries exactly that label. With Key Cycling
on, one bar press went through this handler **and** through the Lead Sheet's
`#live-stop-btn`. The usability work measured the result: a Stop about 3 s after a bar
Resume was undone for 2–3 s in 4 of 6 rounds.

**Current state:** the compact bar is not on dev yet. Its approved design (Option B) hides
and disables the bar's Pause/Resume while the Key Cycling console is rendered, so a disabled
button sends no click. Stop is unchanged.

**Required before the bar's Pause/Resume works during Key Cycling:** one transport owner,
not two. Do one of these and add a test:
- scope the fallback to Key Cycling's own controls: ignore `#ls-mini-pause` and any element
  outside the Key Cycling console and the Lead Sheet player;
- or route the bar's Pause/Resume only through `__kcRequestCyclePause` /
  `__kcRequestCycleResume`, the shared press the Lead Sheet already uses (`0e975ee3`), and
  not through `#live-stop-btn` as well.

Coordinate with the owner of the compact bar. Do not change their code from the Key Cycling
side.

---

## KC-F6. A volume or mute set on the player's own controls does not hold

**Seen 2026-11-15 (real-bridge tests, while verifying the silent-take fix):** the visible Key
Cycling take shows the browser's own media controls (`kc-buf-0 controls`), but the page
overrides a level or mute set there:
- each key change starts the incoming take at volume 1 (`kickPlay`, the warm promote, the
  resume kicks and the start's own kicks all write `volume = 1`);
- the page's one-audible-take sweep (`enforceAudibleSurfaces`) unmutes the active take and
  raises a volume under 0.05 to 1, within about 250 ms.

**Pre-existing**, unchanged by the Key Cycling upgrade. The silent-take fix
(`__kcEnsureAudible`) does respect the musician's choice: it restores only a ZERO volume,
to the level they last set (`st.intendedVolume`), and it never unmutes a take they muted
(`st.userMuted`, recorded by `__kcArmUserVolumeIntent`). The older writers above do not.

**If it is taken on:** make those writers use the same intended level and mute state, so one
setting holds across key changes. Do not add another owner of the player volume.

---

## KC-F7. The page's `late_prep_recover` report never reaches the server

**Found 2026-11-16, while fixing the end of the cycle (`1139f3e1`). Pre-existing.** When the
next take was never armed in time, the page (in `backing_key_cycle.py`, next to the
`kind: 'late_prep_recover'` ack) sends that report three ways, and none of them arrives:
- the playing-ack queue: `render_handoff_component` delivers only `playing`, `play_started`
  and (since `1139f3e1`) `final_key_stop`;
- a `kc_handoff` cookie, which no Python code reads;
- a `kc_handoff_ack_json` text input, which no Python code creates.

The pass bridge's `ack_kind == "late_prep_recover"` branch (one forced advance plus
CONTINUE_PLAY) is therefore unreachable. The `clickBridge('late_prep_recover::…')` fallback
runs only if building the ack throws.

**Do not just add the kind to the receiver.** The forced advance predates the boundary rule and
the wait for the verified next take (`09b93037`), so enabling it changes free-running playback
and needs its own browser verification. Decide first whether the recovery is still wanted.

---

## KC-F8. A slow Resume and a stale "paused" flag during free-running cycling

**Seen 2026-11-16 (boundary sweep on `d01a0df3`), and also on the 2026-11-13/14 builds, so
pre-existing:**
- one Resume took about **11 s** to become audible;
- the page's `userPaused` flag read true while audio was playing.

Neither replayed or skipped a key. Measure both with the page's own clock (`__kcPlayDiag`,
`__kcAckLog`) before changing anything.

---

## KC-F9. Three browser tests are flaky (seen 2026-11-16)

Both fail intermittently on `e51e289a` as well as later, so they are not caused by the fixes made
that day:
- `test_key_cycle_pause_reports_sounding_key.py::StopOutranksAnEarlierResume::test_after_the_servers_off_a_new_start_plays`:
  failed in 2 of 2 full-file runs on `e51e289a` and 1 of 2 on `d96f26e4`; it passes alone and in
  the related suite.
- `ATakeMarkedPlayingIsHeard::test_a_cold_take_started_from_a_silenced_slot_is_heard`: 1 of 6
  isolated runs on each build.
- `ATakeMarkedPlayingIsHeard::test_a_mute_the_musician_chose_is_kept`: 10 of 20 isolated runs on
  `e51e289a`, 11 of 20 on `d96f26e4`. It races the page's own unmute sweep (KC-F6): an unmute
  inside the 1.5 s after the touch overwrites the recorded mute.

Both depend on fixed waits inside the harness. Make them wait for the state they check before
reading it.

The older `plain_block` Backing probe in the Key Cycling scratchpad is out of date: its Lead Sheet
"pause" press is a Stop on the current controls, and it fails the same way on dev. Ordinary Backing
Pause / Resume / Stop is covered by the compact-bar probe's Key Cycling Off mode.

