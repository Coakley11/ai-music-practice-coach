"""Phrase slurs and articulations derived from generated events (not post-hoc ABC paint)."""

from __future__ import annotations

from typing import Any, Sequence


def _dur(item: dict[str, Any]) -> str:
    return str(item.get("duration") or "").lower()


def _is_rest(item: dict[str, Any]) -> bool:
    return _dur(item).startswith("rest") or not str(item.get("spelled") or "").strip()


def _is_short(item: dict[str, Any]) -> bool:
    return _dur(item) in {"eighth", "triplet_eighth", "sixteenth"}


def apply_phrase_articulation(
    events: list[dict[str, Any]],
    *,
    family: str = "",
    level: str = "intermediate",
    object_type: str = "improvisation",
    voice: str = "",
    preserve_existing: bool = False,
) -> list[dict[str, Any]]:
    """Annotate slur groups and accents on generated motion events in place."""
    if not events:
        return events
    if preserve_existing and any(e.get("slur_group") or e.get("articulation") for e in events):
        return events

    fam = str(family or "").lower()
    lvl = str(level or "intermediate").lower()
    obj = str(object_type or "").lower()
    wind = fam == "wind"
    piano_lh = fam in {"keyboard", "piano"} and str(voice or "").lower() in {"lh", "left_hand"}
    beginner = "begin" in lvl or "easy" in lvl
    advanced = "advanced" in lvl or "hard" in lvl
    jazz = obj in {"improvisation", "lick", "solo"} or advanced

    max_group = 3 if beginner else (5 if wind else 4)
    min_group = 2 if (beginner or wind) else 3

    group_id = 0
    i = 0
    n = len(events)
    while i < n:
        ev = events[i]
        ev.setdefault("articulation", ev.get("articulation") or "")
        ev.setdefault("slur_group", 0)
        if _is_rest(ev) or piano_lh:
            i += 1
            continue
        if not _is_short(ev):
            i += 1
            continue
        run: list[int] = [i]
        j = i + 1
        while j < n and len(run) < max_group:
            nxt = events[j]
            if _is_rest(nxt) or not _is_short(nxt):
                break
            if str(nxt.get("role") or ev.get("role") or "") not in {
                str(ev.get("role") or ""),
                "",
                str(nxt.get("role") or ""),
            } and ev.get("role") in {"rh", "lh"} and nxt.get("role") in {"rh", "lh"}:
                if nxt.get("role") != ev.get("role"):
                    break
            prev_midi = int(events[run[-1]].get("midi") or 0)
            midi = int(nxt.get("midi") or 0)
            if prev_midi and midi and abs(midi - prev_midi) > (4 if wind else 5):
                break
            if int(nxt.get("bar_index") or 0) > int(events[run[0]].get("bar_index") or 0) + 1:
                break
            run.append(j)
            j += 1
        if len(run) >= min_group:
            group_id += 1
            for idx in run:
                events[idx]["slur_group"] = group_id
            i = run[-1] + 1
        else:
            i += 1

    if piano_lh:
        for ev in events:
            if _is_rest(ev):
                continue
            beat = float(ev.get("beat") or 0.0)
            if abs(beat) < 1e-9 and advanced:
                ev["articulation"] = "tenuto"
        return events

    accent_budget = 1 if beginner else (3 if advanced else 2)
    accents = 0
    bars_seen: set[int] = set()
    for i, ev in enumerate(events):
        if _is_rest(ev) or accents >= accent_budget * max(1, 1 + int(ev.get("bar_index") or 0) // 4):
            continue
        beat = float(ev.get("beat") or 0.0)
        role = str(ev.get("tone_role") or "")
        bar = int(ev.get("bar_index") or 0)
        syncopated = abs(beat - 1.5) < 1e-9 or abs(beat - 2.5) < 1e-9 or abs(beat - 0.5) < 1e-9
        peak = False
        if i > 0 and i + 1 < n:
            pm = int(events[i - 1].get("midi") or 0)
            nm = int(events[i + 1].get("midi") or 0)
            midi = int(ev.get("midi") or 0)
            if midi and pm and nm and midi > pm and midi > nm and midi - min(pm, nm) >= 3:
                peak = True
        want_accent = False
        if jazz and syncopated and role in {"chord_tone", "extension", "approach"} and not beginner:
            want_accent = True
        elif peak and advanced and bar not in bars_seen:
            want_accent = True
        elif wind and role == "chord_tone" and abs(beat - 2.0) < 1e-9 and not beginner and bar % 2 == 1:
            want_accent = True
        if want_accent and not ev.get("articulation"):
            ev["articulation"] = "accent"
            accents += 1
            bars_seen.add(bar)

    if advanced and jazz and not beginner:
        for ev in events:
            if _is_rest(ev) or ev.get("articulation") or ev.get("slur_group"):
                continue
            if str(ev.get("duration") or "") == "quarter" and str(ev.get("tone_role") or "") == "chord_tone":
                beat = float(ev.get("beat") or 0.0)
                if abs(beat - 3.0) < 1e-9 or abs(beat - 2.0) < 1e-9:
                    ev["articulation"] = "tenuto"
                    break

    if beginner:
        # Cap slur density: keep first group per 2 bars only.
        keep: set[int] = set()
        last_keep_bar = -9
        for ev in events:
            g = int(ev.get("slur_group") or 0)
            bar = int(ev.get("bar_index") or 0)
            if not g or g in keep:
                continue
            if bar - last_keep_bar < 2 and keep:
                ev["slur_group"] = 0
                continue
            keep.add(g)
            last_keep_bar = bar
        for ev in events:
            if int(ev.get("slur_group") or 0) not in keep:
                ev["slur_group"] = 0
            if ev.get("articulation") == "accent" and int(ev.get("bar_index") or 0) > 3:
                ev["articulation"] = ""
        return events

    if advanced and jazz:
        staccato_budget = 1
        for ev in events:
            if staccato_budget <= 0:
                break
            if _is_rest(ev) or ev.get("articulation") or ev.get("slur_group"):
                continue
            if _dur(ev) != "eighth":
                continue
            beat = float(ev.get("beat") or 0.0)
            if abs(beat - 3.5) < 1e-9 or abs(beat - 1.5) < 1e-9:
                ev["articulation"] = "staccato"
                staccato_budget -= 1

    return events


def articulation_abc_prefix(articulation: str) -> str:
    art = str(articulation or "").lower()
    bits: list[str] = []
    if "accent" in art:
        bits.append("!>!")
    if "tenuto" in art:
        bits.append("!tenuto!")
    return "".join(bits)


def slur_bounds(events: Sequence[Any]) -> list[tuple[Any, bool, bool]]:
    """Return (event, slur_start, slur_end) in order."""
    out: list[tuple[Any, bool, bool]] = []
    n = len(events)

    def _group(e: Any) -> int:
        if isinstance(e, dict):
            return int(e.get("slur_group") or 0)
        return int(getattr(e, "slur_group", 0) or 0)

    for i, ev in enumerate(events):
        g = _group(ev)
        prev_g = _group(events[i - 1]) if i else 0
        next_g = _group(events[i + 1]) if i + 1 < n else 0
        out.append((ev, bool(g) and g != prev_g, bool(g) and g != next_g))
    return out
