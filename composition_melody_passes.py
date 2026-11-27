"""Editing scope for a repeated section: the entire section, or one pass of it.

A section whose chords repeat - D | Bm | G | A | D | Bm | G | A - is two passes of the same
four bars. The musician wants both ways of working: shape the whole thing at once, or develop
the first phrase and then treat the second one differently. The existing repetition model in
``composition_melody_repeats`` already marks every event with its ``pass_index`` and can
transform "all repeats" or "the first occurrence"; what it cannot do is work on pass 2, copy
one pass into another, or keep a copied phrase from clashing with harmony it was not written
for. That is what this module adds.

Everything here is a pure function over an event list. It never touches the document, the
section's identity, its chord data or any Backing loop setting - a pass is a range of beats
inside one melody, not a playback repeat.

Two rules hold throughout:

* A pass edit changes only its own pass. Every other pass keeps its events and its absolute
  beats, so the section's length never moves and earlier work is never lost.
* Nothing is accepted here. These produce proposals; the caller decides.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

from composition_melody_repeats import (
    EDIT_SCOPE_ALL,
    EDIT_SCOPE_FIRST,
    detect_repeat_count,
    phrase_length_beats,
)

#: The musician's two choices. ``entire_section`` is the default everywhere.
SCOPE_ENTIRE = "entire_section"
SCOPE_ONE_PASS = "one_pass"
SCOPE_BARS = "bar_range"

SCOPE_LABELS: dict[str, str] = {
    SCOPE_ENTIRE: "Entire section",
    SCOPE_ONE_PASS: "One pass",
    SCOPE_BARS: "Selected bars",
}

#: Mapping onto the older two-value vocabulary, so a caller that still speaks it keeps working.
LEGACY_SCOPE: dict[str, str] = {
    SCOPE_ENTIRE: EDIT_SCOPE_ALL,
    SCOPE_ONE_PASS: EDIT_SCOPE_FIRST,
}


def _rows(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [copy.deepcopy(e) for e in list(events or []) if isinstance(e, dict)]


def _index_of(ev: dict[str, Any]) -> int | None:
    for field in ("pass_index", "repeat_index"):
        if ev.get(field) is not None:
            try:
                return int(ev.get(field))
            except (TypeError, ValueError):
                continue
    return None


def pass_count(events: list[dict[str, Any]] | None) -> int:
    """How many passes this melody has. One, for a melody that does not repeat."""
    return max(1, int(detect_repeat_count(events)))


def pass_span_beats(events: list[dict[str, Any]] | None) -> float:
    """Length of a single pass.

    Taken from the markers when they are there, because that is what the tiling actually used;
    the total divided by the number of passes otherwise.
    """
    rows = _rows(events)
    total = phrase_length_beats(rows)
    n = pass_count(rows)
    if n <= 1 or total <= 0:
        return total
    marked = [r for r in rows if _index_of(r) == 0]
    if marked:
        own = phrase_length_beats(marked)
        if own > 0:
            return own
    return total / n


def pass_bounds(events: list[dict[str, Any]] | None, index: int) -> tuple[float, float]:
    """``(start, end)`` beats of one pass. An out-of-range index gives an empty range."""
    rows = _rows(events)
    n = pass_count(rows)
    i = int(index)
    if not rows or i < 0 or i >= n:
        return (0.0, 0.0)
    span = pass_span_beats(rows)
    marked = [r for r in rows if _index_of(r) == i]
    if marked:
        start = min(float(r.get("beat") or 0.0) for r in marked)
        stop = max(
            float(r.get("beat") or 0.0) + float(r.get("duration_beats") or 0.0) for r in marked
        )
        # The slot is the pass's whole span, not just where its notes happen to start and
        # stop: a phrase that begins with a rest still owns the beats before its first note.
        return (round(min(start, i * span), 4), round(max(stop, (i + 1) * span), 4))
    return (round(i * span, 4), round((i + 1) * span, 4))


def events_in_pass(events: list[dict[str, Any]] | None, index: int) -> list[dict[str, Any]]:
    """The events belonging to one pass - by marker where there is one, by beat otherwise."""
    rows = _rows(events)
    i = int(index)
    marked = [r for r in rows if _index_of(r) == i]
    if marked:
        return marked
    if any(_index_of(r) is not None for r in rows):
        # Markers exist but none for this index: the pass is genuinely empty.
        return []
    start, end = pass_bounds(rows, i)
    return [r for r in rows if start - 0.001 <= float(r.get("beat") or 0.0) < end - 0.001]


def bar_beats(meter: str = "4/4") -> float:
    """Beats in one bar of this meter, counted the way the rest of Composition counts them."""
    try:
        from composition_melody_audit import bar_beats as _bars

        return float(_bars(str(meter or "4/4")))
    except Exception:
        try:
            return float(int(str(meter).split("/")[0]))
        except (TypeError, ValueError):
            return 4.0


def bar_bounds(first_bar: int, last_bar: int, *, meter: str = "4/4") -> tuple[float, float]:
    """``(start, end)`` beats of bars ``first_bar``..``last_bar``, counted from bar 1 inclusive.

    Bars are what the musician reads off the staff, so they are 1-based here even though beats
    are not. A reversed pair is read in the order meant rather than refused.
    """
    bar = bar_beats(meter)
    lo = max(1, int(min(first_bar, last_bar)))
    hi = max(1, int(max(first_bar, last_bar)))
    return (round((lo - 1) * bar, 4), round(hi * bar, 4))


def scope_window(
    events: list[dict[str, Any]] | None,
    *,
    scope: str = SCOPE_ENTIRE,
    pass_index: int = 0,
    bars: tuple[int, int] | None = None,
    meter: str = "4/4",
) -> tuple[float, float] | None:
    """The beat range an edit is allowed to touch, or ``None`` for the whole melody."""
    mode = str(scope or SCOPE_ENTIRE)
    if mode == SCOPE_ONE_PASS and pass_count(events) > 1:
        return pass_bounds(events, pass_index)
    if mode == SCOPE_BARS and bars:
        return bar_bounds(int(bars[0]), int(bars[1]), meter=meter)
    return None


def events_in_window(
    events: list[dict[str, Any]] | None, window: tuple[float, float] | None
) -> list[dict[str, Any]]:
    """Events whose ONSET falls inside the window. ``None`` means every event.

    **Selection is by onset, never by overlap.** A note that begins in bar 4 and sings into
    bar 5 belongs to bar 4: selecting bars 5-8 does not select it, and an edit there leaves it
    completely alone. The alternative - selecting anything that overlaps the range - would let
    an edit to bar 5 silently retune or shorten a note the musician can see starting in bar 4,
    which is the opposite of what a visible scope promises.

    The consequence is deliberate and worth stating: a selected range can be SOUNDING music
    that it does not own. Editing bars 5-8 cannot change the note still ringing from bar 4.
    """
    rows = _rows(events)
    if window is None:
        return rows
    lo, hi = float(window[0]), float(window[1])
    return [r for r in rows if lo - 0.001 <= float(r.get("beat") or 0.0) < hi - 0.001]


def scope_caption(
    scope: str,
    pass_index: int = 0,
    total: int | None = None,
    bars: tuple[int, int] | None = None,
) -> str:
    """One line naming what an edit will touch. The scope must never be a guess.

    Shown next to every generate/refine control, because "it changed something somewhere" is
    exactly the confusion that repeated passes create.
    """
    n = int(total or 1)
    if str(scope) == SCOPE_BARS and bars:
        lo, hi = int(min(bars)), int(max(bars))
        where = f"bar {lo}" if lo == hi else f"bars {lo}-{hi}"
        return f"Editing {where} - the rest of the section stays as it is."
    if str(scope) == SCOPE_ONE_PASS and n > 1:
        return f"Editing pass {int(pass_index) + 1} of {n} - the other passes stay as they are."
    if n > 1:
        return f"Editing the entire section - all {n} passes."
    return "Editing the entire section."


def apply_to_scope(
    events: list[dict[str, Any]] | None,
    transform: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    *,
    scope: str = SCOPE_ENTIRE,
    pass_index: int = 0,
    bars: tuple[int, int] | None = None,
    meter: str = "4/4",
) -> list[dict[str, Any]]:
    """Run ``transform`` over the whole melody, or over one pass, or over chosen bars.

    Membership is by onset (see ``events_in_window``): a note that begins outside the window
    is untouched even if it sounds inside it, and a note that begins inside keeps whatever
    length it already had even if that reaches past the end.

    Inside a window the events are handed to the transform in LOCAL beats, starting at zero.
    A refinement that talks about "the first note" or "the last measure" then means the first
    note and last measure of what the musician selected - and the result is shifted back and
    clamped to that window, so it cannot grow into music it was not asked to change.

    Everything outside the window is returned untouched: its events, its beats, its rests and
    its durations. That is the whole promise of a scoped edit.
    """
    rows = _rows(events)
    if not rows:
        return []
    window = scope_window(
        rows, scope=scope, pass_index=pass_index, bars=bars, meter=meter
    )
    if window is None:
        return list(transform(rows))

    start, end = float(window[0]), float(window[1])
    i = int(pass_index)
    by_pass = str(scope) == SCOPE_ONE_PASS
    marked = any(_index_of(r) is not None for r in rows)

    # Partition by POSITION in `rows`. events_in_pass / events_in_window hand back deep copies,
    # so filtering the originals by object identity removes nothing and every selected event
    # ends up in the result twice.
    if by_pass and marked:
        mine_at = [n for n, r in enumerate(rows) if _index_of(r) == i]
    else:
        mine_at = [
            n
            for n, r in enumerate(rows)
            if start - 0.001 <= float(r.get("beat") or 0.0) < end - 0.001
        ]
    if not mine_at:
        return rows
    chosen = set(mine_at)
    mine = [rows[n] for n in mine_at]
    others = [r for n, r in enumerate(rows) if n not in chosen]

    # How far the selection already reached. A note that sings across the boundary keeps its
    # length: the clamp is there to stop an edit growing into music it was not asked to touch,
    # not to crop a phrase that was already written that way.
    reach = max(
        (float(r.get("beat") or 0.0) + float(r.get("duration_beats") or 0.0) for r in mine),
        default=end,
    )
    limit = max(end, reach)

    local = []
    for row in mine:
        shifted = copy.deepcopy(row)
        shifted["beat"] = round(float(row.get("beat") or 0.0) - start, 4)
        local.append(shifted)

    changed = list(transform(local) or [])
    rebuilt: list[dict[str, Any]] = []
    for row in changed:
        out = copy.deepcopy(row)
        beat = float(out.get("beat") or 0.0) + start
        out["beat"] = round(beat, 4)
        if by_pass:
            out["pass_index"] = i
            out["repeat_index"] = i
        dur = float(out.get("duration_beats") or 0.0)
        if limit > start and beat + dur > limit:
            out["duration_beats"] = round(max(0.25, limit - beat) * 4) / 4
        rebuilt.append(out)

    merged = others + rebuilt
    merged.sort(key=lambda e: (float(e.get("beat") or 0.0), _index_of(e) or 0))
    return merged


def restore_pass(
    events: list[dict[str, Any]] | None,
    original: list[dict[str, Any]] | None,
    index: int,
) -> list[dict[str, Any]]:
    """Put one pass back the way ``original`` has it, leaving every other pass alone.

    This is how a musician undoes work on pass 2 after deciding they preferred it before,
    without losing what they have since done to pass 1 or pass 3. The restored pass keeps the
    original's rests and durations exactly - an expressive phrase restored approximately is not
    restored at all.
    """
    rows = _rows(events)
    src = _rows(original)
    if not rows or not src:
        return rows
    i = int(index)
    mine = events_in_pass(src, i)
    if not mine:
        return rows
    start, _end = pass_bounds(src, i)
    local = []
    for row in mine:
        out = copy.deepcopy(row)
        out["beat"] = round(float(row.get("beat") or 0.0) - start, 4)
        local.append(out)
    return apply_to_scope(rows, lambda _evs: local, scope=SCOPE_ONE_PASS, pass_index=i)


def coverage_report(
    events: list[dict[str, Any]] | None,
    chords: list[str] | None = None,
    *,
    meter: str = "4/4",
    section_beats: float | None = None,
) -> dict[str, Any]:
    """Does the melody reach the end of the section, and if not, does that look meant?

    The silence at the end of a section can be either of two completely different things, and
    the app must not treat them alike:

    * a phrase that breathes - it stops a beat or two early, or writes a rest to close the
      section. Nothing is wrong and nothing should be "repaired";
    * a melody that was truncated - a whole bar or more of chords playing with no melody over
      them and no rest saying so. That is the defect the musician reported.

    An explicit trailing rest always means the first. So does a short tail. A long silent tail
    with no rest row is reported as truncated, with the bars that are missing.
    """
    rows = _rows(events)
    bar = bar_beats(meter)
    total = float(section_beats) if section_beats else 0.0
    if total <= 0 and chords:
        try:
            from composition_melody_audit import chord_segments

            segs = chord_segments([str(c) for c in chords], meter)
            total = float(segs[-1][1]) if segs else 0.0
        except Exception:
            total = 0.0
    if total <= 0:
        total = phrase_length_beats(rows)

    sounding = [r for r in rows if not r.get("is_rest")]
    melody_end = max(
        (float(r.get("beat") or 0.0) + float(r.get("duration_beats") or 0.0) for r in sounding),
        default=0.0,
    )
    closing_rest = any(
        r.get("is_rest")
        and float(r.get("beat") or 0.0) + float(r.get("duration_beats") or 0.0) >= total - 0.01
        for r in rows
    )
    tail = max(0.0, round(total - melody_end, 4))
    covers = tail <= 0.01

    if covers:
        verdict, message = "covers", "The melody reaches the end of the section."
    elif closing_rest:
        verdict, message = (
            "intended_ending",
            "The melody ends early and a rest closes the section - that is written in, not missing.",
        )
    elif tail < bar:
        verdict, message = (
            "intended_ending",
            "The melody stops just short of the end, which reads as a phrase ending.",
        )
    else:
        missing = int(tail // bar) if bar > 0 else 0
        verdict, message = (
            "truncated",
            f"The last {missing} bar(s) have chords but no melody over them.",
        )
    return {
        "section_beats": round(total, 4),
        "melody_end_beat": round(melody_end, 4),
        "silent_tail_beats": tail,
        "silent_tail_bars": round(tail / bar, 3) if bar else 0.0,
        "closing_rest": bool(closing_rest),
        "covers": bool(covers),
        "verdict": verdict,
        "message": message,
    }


def _chord_at(beat: float, chords: list[str] | None, meter: str) -> str:
    if not chords:
        return ""
    try:
        from composition_melody_audit import chord_at_beat, chord_segments

        return str(chord_at_beat(chord_segments(list(chords), meter), float(beat)) or "")
    except Exception:
        return ""


def _chord_pcs(symbol: str, key: str) -> set[int]:
    if not symbol:
        return set()
    try:
        from composition_melody_audit import chord_info

        info = chord_info(symbol, key)
        if info is None:
            return set()
        return set(info.tone_pcs) | set(info.ext_pcs or ())
    except Exception:
        return set()


def _scale_pcs(key: str) -> set[int]:
    try:
        from composition_melody_audit import key_scale_pcs

        return set(key_scale_pcs(key))
    except Exception:
        return set()


def pass_clashes(
    events: list[dict[str, Any]] | None,
    chords: list[str] | None,
    *,
    key: str = "C",
    meter: str = "4/4",
    min_beats: float = 1.0,
) -> list[dict[str, Any]]:
    """Notes that would sound wrong where they now are, and only those.

    A copied phrase meets harmony it was not written for, and the usual result is one or two
    notes that were a chord tone in pass 1 and are a clash in pass 2. A note is reported only
    when it is outside the chord AND outside the key AND long enough to be heard as a mistake
    rather than as a passing note. A chromatic approach note, a leap and a syncopation all
    survive that test deliberately: they are not errors and must not be "corrected".
    """
    rows = _rows(events)
    scale = _scale_pcs(key)
    out: list[dict[str, Any]] = []
    for n, row in enumerate(rows):
        if row.get("is_rest") or row.get("midi") is None:
            continue
        dur = float(row.get("duration_beats") or 0.0)
        if dur < float(min_beats):
            continue
        beat = float(row.get("beat") or 0.0)
        symbol = _chord_at(beat, chords, meter)
        tones = _chord_pcs(symbol, key)
        if not tones:
            continue
        pc = int(row.get("midi")) % 12
        if pc in tones or pc in scale:
            continue
        out.append(
            {
                "index": n,
                "beat": beat,
                "pitch": str(row.get("pitch") or ""),
                "midi": int(row.get("midi")),
                "chord": symbol,
                "duration_beats": dur,
            }
        )
    return out


def _renamed(row: dict[str, Any], midi: int, key: str) -> str:
    try:
        from composition_melody_shape import _pitch_label

        return str(_pitch_label(int(midi), key))
    except Exception:
        return str(row.get("pitch") or "")


def fit_events_to_chords(
    events: list[dict[str, Any]] | None,
    chords: list[str] | None,
    *,
    key: str = "C",
    meter: str = "4/4",
    min_beats: float = 1.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Move only the clashing notes to the nearest chord tone. Returns ``(events, changes)``.

    The smallest move that works, so the copied phrase keeps its shape: a note travels one or
    two semitones, never an octave, and nothing but a reported clash is touched. Rhythm is
    never altered - this is about pitch meeting new harmony, not about rewriting the phrase.
    """
    rows = _rows(events)
    found = pass_clashes(rows, chords, key=key, meter=meter, min_beats=min_beats)
    changes: list[dict[str, Any]] = []
    for clash in found:
        n = int(clash["index"])
        row = rows[n]
        midi = int(row.get("midi") or 0)
        tones = _chord_pcs(str(clash["chord"]), key)
        if not tones:
            continue
        best = None
        for delta in (-1, 1, -2, 2):
            if (midi + delta) % 12 in tones:
                best = midi + delta
                break
        if best is None:
            continue
        row["midi"] = int(best)
        row["pitch"] = _renamed(row, best, key)
        changes.append(
            {
                "beat": float(clash["beat"]),
                "chord": str(clash["chord"]),
                "from": str(clash["pitch"]),
                "to": str(row.get("pitch") or ""),
                "semitones": int(best - midi),
            }
        )
    return rows, changes


def copy_pass(
    events: list[dict[str, Any]] | None,
    source_index: int,
    target_indexes: list[int] | None = None,
    *,
    chords: list[str] | None = None,
    key: str = "C",
    meter: str = "4/4",
    fit_to_chords: bool = True,
    variation: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Put one pass's phrase into later passes. Returns ``(events, changes)``.

    ``variation`` is applied to each copy before it lands, which is how "repeat it, but not
    identically" works: the same phrase with one refinement's worth of difference each time.
    With ``fit_to_chords`` the copy is checked against the harmony it lands on, so a blindly
    repeated phrase does not clash with a pass whose chords differ.

    The section's length cannot change: a copy fills the target pass's existing slot.
    """
    rows = _rows(events)
    total = pass_count(rows)
    src = int(source_index)
    if not rows or total <= 1 or src < 0 or src >= total:
        return rows, []
    source = events_in_pass(rows, src)
    if not source:
        return rows, []
    targets = [int(t) for t in (target_indexes if target_indexes is not None else range(total))]
    targets = [t for t in targets if 0 <= t < total and t != src]
    if not targets:
        return rows, []

    src_start, _src_end = pass_bounds(rows, src)
    marked = any(_index_of(r) is not None for r in rows)
    if marked:
        kept = [r for r in rows if _index_of(r) not in targets]
    else:
        # Unmarked events: fall back to beat ranges, so a hand-edited melody still works.
        kept = []
        for r in rows:
            beat = float(r.get("beat") or 0.0)
            in_target = False
            for t in targets:
                lo, hi = pass_bounds(rows, t)
                if lo - 0.001 <= beat < hi - 0.001:
                    in_target = True
                    break
            if not in_target:
                kept.append(r)

    all_changes: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    for t in targets:
        lo, hi = pass_bounds(rows, t)
        copied = []
        for row in source:
            out = copy.deepcopy(row)
            out["beat"] = round(float(row.get("beat") or 0.0) - src_start, 4)
            copied.append(out)
        if variation is not None:
            copied = list(variation(copied) or copied)
        placed = []
        for row in copied:
            out = copy.deepcopy(row)
            beat = float(out.get("beat") or 0.0) + lo
            out["beat"] = round(beat, 4)
            out["pass_index"] = t
            out["repeat_index"] = t
            dur = float(out.get("duration_beats") or 0.0)
            if beat + dur > hi:
                out["duration_beats"] = round(max(0.25, hi - beat) * 4) / 4
            placed.append(out)
        if fit_to_chords and chords:
            placed, changes = fit_events_to_chords(placed, chords, key=key, meter=meter)
            for ch in changes:
                ch["pass"] = t + 1
            all_changes.extend(changes)
        added.extend(placed)

    merged = kept + added
    merged.sort(key=lambda e: (float(e.get("beat") or 0.0), _index_of(e) or 0))
    return merged, all_changes
