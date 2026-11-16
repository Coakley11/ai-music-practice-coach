# QA follow-up: reselecting the key you just sang in

**Status:** open, accepted as a documented limitation of the saved-Practice-Key hotfix
(`fix/karaoke-saved-practice-key`). Not a regression - before the hotfix this case "worked" only
because tonight's key was being written into the song's saved key, which is the defect.

## The limitation

After a Karaoke set ends, the key that set was sung in is **held** for that song: it will not be
saved as the song's permanent Practice Key until the musician chooses some other key, or starts
another set. So this sequence does not persist:

1. Say is saved in D, sung tonight in A♭.
2. End Set.
3. The musician decides they now want A♭ permanently and selects A♭.
4. It is refused; D stays.

The way through today is to choose any other key (which saves at once and clears the hold) and
then choose A♭.

## Why it is held

The write that used to destroy the saved key arrives **with** the explicit user-commit flags:

```
persist_sbi_active_sidebar_commit_before_render -> note_sbi_active_user_practice_key_edit
    -> set_practice_concert_key(..., allow_restore_original=True)
```

That path re-persists the **leftover sidebar widget value** as though the musician had just
chosen it. The widget still shows A♭ after End Set because a Streamlit widget's session value
cannot be rewritten once the widget has rendered in that run, and End Set is handled inline,
after the sidebar renders.

A genuine new selection of A♭ and that leftover are, at the write, identical: same pick, same
key, same flags, and in both cases the live key is already A♭. Nothing in the call separates
them. The hotfix therefore errs toward keeping the key the musician saved.

## What a proper fix needs

**An explicit new Practice Key selection must be distinguishable from a stale Karaoke widget
value, including when both carry the same key.** A legitimate selection should persist without
the musician having to pick an unrelated intermediate key.

Approaches worth evaluating (none attempted here - this needs review, not a quick patch):

- **Carry provenance on the gesture.** A widget `on_change` callback fires only for a real
  interaction. If the commit recorded *that it came from an on_change* - a nonce or run marker
  set in the callback and consumed by the write - a pre-render re-persist could not borrow it.
  `display_key_change_source` already exists and may be the right place.
- **Retire the leftover instead of holding against it.** If the sidebar's value were genuinely
  reset to the song's own key on the first run after End Set, there would be no leftover and no
  hold. That is the same ground as the open "sidebar temporary-key display residue" QA item, and
  fixing it would let this hold be narrowed or removed.
- **Ask the musician.** With the two cases genuinely indistinguishable at the write, a one-line
  confirmation after a set ("keep A♭ as Say's key?") is honest about the ambiguity. Cheapest to
  build, and the only option that cannot guess wrong.

Do **not** address this with a broad sidebar redesign inside the hotfix.

## Scope of the current hold

- One song: the pick that was being sung. Every other song, including Custom Progressions,
  saves normally - covered by tests.
- One key: the exact key handed back, compared by musical identity (`Ab` == `A♭ major`), so
  spelling cannot defeat it and an unrelated key is never held.
- One session: the hold is **not** persisted. The leftover it guards is session state, so a hold
  that survived a reload would outlive its own reason - the failure mode this hold was rewritten
  to avoid. It is per-user and per-device by construction.
- It clears on: any other key being saved for that song, or the next set starting.
