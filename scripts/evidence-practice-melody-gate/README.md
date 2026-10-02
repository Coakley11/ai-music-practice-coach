# Gate F1-V1 / F1-V2 — browser verification evidence

Produced by `scripts/_browser_practice_melody_gate_v1_8570.py` (transposing
instrument) and `scripts/_browser_practice_melody_gate_v2_8570.py` (active
Key Cycle), run before Slice F2 per the acceptance gate.

## Gate F1-V1 — Tenor Saxophone (`v1-*`)

**14/14 gates passed** (`v1-summary.json`), clean single run:

- Switched Instrument -> Saxophone -> Tenor Saxophone, enabled "Show chart
  in written key for instrument".
- With Practice Concert Key = C, the Chart & Melody workspace's own
  context line read "Chart key **D**" (Bb tenor sax, +2 semitones written)
  -- and the Generated Practice Melody panel's key matched it exactly
  (`v1-02-melody-written-key.png`): no Practice-Melody-specific instrument
  logic, it's reading the same `chart_key` Practice's notation tool
  already used.
- Handed off to Backing: the melody panel there showed the same written
  key `D` (`v1-03-backing-tenor-sax.png`).
- Changed Practice Concert Key C -> D: the melody's key correctly became
  `E` (D concert + 2 semitones), same composition (`alternative #1`
  unchanged), no regeneration (`v1-04-backing-after-key-change.png`).

## Gate F1-V2 — active Key Cycle (`v2-*`)

**14/14 gates passed** on the persisted run (`v2-summary.json`), confirmed
independently a second time in-session (not separately saved to disk due
to a later browser crash, but observed with the same result: melody key
advancing C -> D in step with Key Cycle's own "Sounding" key, with
`alternative #1` unchanged across the transition).

- Turned "Key cycling" on from Backing's Advanced playback settings (a
  custom-styled radio that needed Playwright's `get_by_role("radio",
  ...).check()` rather than a plain label click or JS `element.click()`
  to register -- documented in the script for future reuse).
- `v2-02-after-next-1.png` shows the full picture at once: "Sounding **C**
  · saved C" with the key-sequence chip row, Pause/Previous key/Next
  key/Turn off cycling controls, the Practice Melody panel immediately
  below reading "...key **C**... alternative #1..." -- matching exactly
  -- and the sidebar "Practice / Concert Key" still reading **C**
  (canonical key untouched by cycling).
- A separate successful run (observed in-session) advanced "Next key"
  again and confirmed the melody panel's key moved from C to **D** in
  step with Key Cycle's "Sounding D", `alternative #1` still unchanged --
  i.e. the same composition, re-projected, not regenerated, across a real
  temporary-key transition.

Note on method: this specific Key Cycle "On" toggle proved to be the
single flakiest interaction automated in this entire project -- a bare JS
`element.click()` and a plain Playwright `.click()` on the role=radio
locator would both silently "succeed" (no exception) without the
underlying Streamlit callback actually firing. `get_by_role("radio",
name="On").check(force=True)` was the one approach that reliably worked;
see the script for the full fallback chain kept for robustness.
