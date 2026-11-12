# Issue 67 — Creative Lab follow-up (recorded, not fixed)

Found while investigating the Songs-page Harmony summary. **Nothing here was
changed by the Songs-card correction**: `improvisation_motif`,
`creative_lab_text` and `deep_harmonic_analyzer` are shared with Missions, the
Harmony Map and the Deep Harmonic Analyzer, so they are to be assessed
separately once the Songs card is certified.

All figures are measured over the 121 curated songs at `origin/dev` `c35e14c1`,
with `scripts/_audit_i67_harmony_loops.py` and the one-off surveys quoted below.

## 1. `improvisation_motif.flatten_sections` does not expand subdivided bars

**33 of 121 songs** feed chart cells, not chords, into harmonic analysis — tokens
such as `Bbm7|Eb7`, `C|G/B`, `F7:2|C7:2`. Every reader downstream then parses a
cell as if it were one chord symbol.

The sibling function in the same module, `section_harmony_rows`, already routes
through `chord_subdivisions.chord_stream` and is correct. The two paths disagree
for every song with a split bar.

Observed (whole-song flat progression):

```
Shape of You   Bm:2|Em:2p - G:2|A:2p - Bm:2|Em:2p - ...
Misty          Ebmaj7 - Bbm7|Eb7 - Abmaj7 - Abm7|Db7
Take On Me     Am - D/F# - G - C|G/B
```

First songs affected: Say, Shape of You, The Scientist, Piano Man, Just the Way
You Are, New York State of Mind, Hey Jude, Yesterday.

## 2. `creative_lab_text.first_matching_pattern` names the pattern from the first four tokens

```python
def first_matching_pattern(chords, key_name):
    roots = [root_pc(ch) for ch in chords]
    ...
        rel = [... for pc in roots[:4]]      # <- the first four, always
```

Callers pass the **whole-song** flat cycle, so the Intro names the song's
harmonic character. `deep_harmonic_analyzer.build_deep_harmonic_lesson` also
calls `_detect_character(cycle, …)` on that flat cycle *before* the shared-loop
override replaces `cycle`, so the character is decided from the intro even when a
section-level loop is known.

**5 songs** get a pattern name that contradicts their own section-level loop:

| song | named from the first four | section-level loop |
|---|---|---|
| Take On Me | `ii-V-I resolution` (`Am D/F# G`) | `Am D/F# Em Am` |
| Misty | `I-IV-V functional movement` | `Ebmaj7 Bbm7 Eb7 Abmaj7` |
| Yellow | `I-IV-V functional movement` | `B F# E` |
| All of Me (pop) | `vi-IV-I-V pop loop` | the chooser disagreed |
| Love Story | `I-V-vi-IV pop loop` | `F G Am C` |

Two of those names are computed from unparseable cell tokens (item 1).

## 3. `deep_harmonic_analyzer._detect_shared_loop` calls any common section cycle a loop

```python
counts = Counter(cycles)
main, n = counts.most_common(1)[0]
repeating = n >= 2 or len(counts) == 1
```

There is no test that the unit actually repeats, and `single_progression_cycle`
returns the entire section when nothing tiles. **37 songs** are therefore
reported as `repeating=True` with a "loop" longer than six chords, and
`_priority_concepts` then prints its first six chords as "Core progression":

```
Waiting on the World to Change   29-chord "loop"
New York State of Mind           23
We Are the Champions             20
Just the Way You Are             17
While My Guitar Gently Weeps     16
Piano Man / Wave                 15
Vienna                           14
Yesterday                        11
Let It Be / Hey Jude / In My Life  8
```

`Counter.most_common` also breaks ties by insertion order, which is chart order,
so the **Intro**'s cycle wins whenever every section differs.

## What the Songs-card correction did about each

Nothing, by instruction. The Songs card got its own, local versions of the two
ideas these functions need:

* `song_card_guidance._bar_chords` / `section_bars` — expansion through
  `chord_stream`, keeping bar boundaries;
* `song_card_guidance._choose_progression` — a recurring unit must actually
  recur, main sections are preferred, and a long non-repeating section is
  described as what it is rather than called a loop.

If this follow-up is approved, the same two ideas are what the shared functions
need; the risk is entirely in the blast radius (Missions, Harmony Map, Deep
Harmonic Analyzer), not in the analysis.

## Unrelated observation, recorded while here

`tests/test_song_card_guidance.py` contains two literal backspace characters
(0x08) inside a raw-string regex, `r"<BS>ii–v<BS>|turnaround|…"`, in
`test_all_of_me_is_a_minor_loop_not_a_jazz_standard`. They are present on
`origin/dev` and make that one `assertNotRegex` vacuous. Left alone — it is not
Issue 67's.
