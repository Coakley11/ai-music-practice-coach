"""Song-Aware Coaching (S4) — optional example phrases for a coaching plan's challenges.

Examples are original practice phrases generated from the selected bars' **chart harmony**
with the existing MC2 span-motif engine — never a claim about the song's melody, a recorded
solo or a performance.

Continuity: one **seed motif** per plan (deterministic from the plan id and the musician's
"new idea" counter) over the first notatable chord window. Every other example derives from it:

- Idea — the seed itself.
- Rhythm — the seed's notes with another motivic rhythm (``cycle_span_rhythm``).
- Connect / Moment / Roadmap — the seed's plan (seed, strategy family, rhythm cell) replayed on
  another chord window, so its rhythmic identity and contour carry while the notes retarget.
- Expand — the idea *developed*, never just given more notes: the same rhythm answered with a
  higher high point, Advanced call and answer, a diatonic sequence, a chord-tone climb (or a
  lower answer when climbing would leave the range and the challenge doesn't ask for a high
  point), or a register shift. The caption only names what was measured.

Phrasing: seeds are chosen within a per-level density cap (3 / 4 / 5 notes per 4/4 bar), and
every shown phrase breathes — each 2-bar group ends with a rest taken from its last held note
(onsets, pitches and chord mapping unchanged, and the result is re-validated).

Every motif is checked against the coaching chord reader (S2, which reads ``Cadd9`` / ``F/G``
correctly where MC2's shared speller does not), placing each note by *when it sounds*: chord
arrivals, downbeats and the last note must be holdable; any other note must move on by step.
A rejected candidate is retried with safer pitch choices (no outside notes, then chord tones
only) — never with a looser check. Mid-bar chord timing, pickups, missing chord windows and
one-chord vamps produce an explicit limitation instead of notation that would be wrong.

Examples are generated in concert pitch; the UI projects them for display only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Iterator

EXAMPLE_VERSION = "s4.2"
MAX_ATTEMPTS = 6
MAX_ROADMAP_SEGMENTS = 4
# Phrasing: how busy an example may be (notes per quarter note: 3 / 4 / 5 in a 4/4 bar) and how
# often it leaves room to breathe. Denser candidates are only used when nothing calmer is valid.
DENSITY_CAP = {"Beginner": Fraction(3, 4), "Intermediate": Fraction(1), "Advanced": Fraction(5, 4)}
EXPAND_DENSITY_CAP = {"Beginner": Fraction(1), "Intermediate": Fraction(5, 4), "Advanced": Fraction(3, 2)}
BREATH_EVERY_BARS = 2

LIMIT_TIMING = "These bars change chord in the middle of a bar, which example notation can't show correctly yet — use the landing notes above instead."
LIMIT_NO_WINDOW = "Examples need at least two chords in a row here; this part of the selection holds a single chord."
LIMIT_UNAVAILABLE = "No example in these bars passed the note check, so none is shown — the landing notes above still apply."
LIMIT_VAMP = "Examples need chord changes; a one-chord vamp isn't supported yet. Use the rhythm and shape ideas above."
LIMIT_PICKUP = "This moment is a pickup into a break, and examples can't notate pickups or anticipations yet — play the pickup yourself and land exactly on the bar line."
LIMIT_EXPAND_RANGE = ("This idea already covers a wide range, so no developed version fits comfortably on the "
                      "staff — try a different example idea, or develop it yourself by repeating its rhythm higher.")
LIMIT_ROADMAP = "The roadmap is the plan — play it in your own words. Examples for its individual steps are on the earlier challenges."


@dataclass(frozen=True)
class Segment:
    start_bar: int
    end_bar: int
    chords: tuple[str, ...]
    motif: dict[str, Any]  # concert pitch
    label: str = ""


@dataclass(frozen=True)
class Example:
    stage: int
    kind: str
    caption: str
    segments: tuple[Segment, ...] = ()
    limitation: str = ""
    continuity: dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return bool(self.segments)


# --------------------------------------------------------------------------- helpers


def example_seed_value(plan_id: str, nonce: int) -> int:
    digest = hashlib.sha256(f"{EXAMPLE_VERSION}|{plan_id}|{int(nonce)}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _focus_label(plan: Any) -> str:
    from song_coach_plan import FOCUS_LABELS

    return FOCUS_LABELS.get(plan.focus, "")


def _constraints(challenge: Any) -> Any:
    from span_motif_engine import SpanConstraints

    raw = (challenge.example or {}).get("constraints") if challenge is not None else None
    return SpanConstraints.from_dict(dict(raw)) if isinstance(raw, dict) and raw else None


def _notatable(link: Any) -> bool:
    return link is not None and link.span is not None and link.exact_bar_timing


def quarters_per_bar(meter: str) -> Fraction:
    try:
        num, den = str(meter or "4/4").split("/")
        return Fraction(int(num) * 4, int(den))
    except (TypeError, ValueError, ZeroDivisionError):
        return Fraction(4)


def note_bars(motif: dict[str, Any]) -> list[tuple[int, Fraction]]:
    """``(bar index in the motif, onset within that bar)`` for every sounding note, from the
    rhythm's absolute onsets (quarter notes from the motif start) and its meter."""
    bar = quarters_per_bar(str((motif.get("rhythm_meta") or {}).get("meter") or "4/4"))
    out: list[tuple[int, Fraction]] = []
    for ev in motif.get("rhythm_events") or []:
        if ev.get("rest"):
            continue
        on = Fraction(str(ev.get("on") or "0"))
        out.append((int(on // bar), on % bar))
    return out


def validate_motif(motif: dict[str, Any], link: Any, *, key: str, style: str = "default") -> list[str]:
    """Check a concert motif against the chart chords of ``link`` (S2 chord reader).

    Each note's chord is found from *when it sounds* (its bar, against the timeline's bar
    lengths), and must agree with the generator's own note-to-chord mapping. Downbeats, chord
    arrivals and the last note must be holdable; any other note must move on by step."""
    from song_coach_harmony import HOLDABLE, chord_facts, note_use, pc_of

    problems: list[str] = []
    timeline = list(motif.get("chord_timeline") or [])
    if tuple(str(s.get("chord")) for s in timeline) != tuple(link.chords):
        problems.append(f"chord timeline {[s.get('chord') for s in timeline]} != {list(link.chords)}")
        return problems
    bars = sum(int(s.get("bars") or 0) for s in timeline)
    if bars != link.end_bar - link.start_bar + 1:
        problems.append(f"motif covers {bars} bars, the window has {link.end_bar - link.start_bar + 1}")
    midis = [int(m) for m in motif.get("midi") or []]
    names = list(motif.get("notes") or [])
    positions = note_bars(motif)
    if len(midis) != len(names) or not midis or len(positions) != len(midis):
        return problems + ["notes, pitches and rhythm disagree"]
    for name, m in zip(names, midis):
        if pc_of(name.replace("♭", "b").replace("♯", "#")) != m % 12:
            problems.append(f"{name} is not pitch {m}")
    starts, total = [], 0
    for s in timeline:
        starts.append(total)
        total += int(s.get("bars") or 0)
    prev_slot = -1
    for i, (m, (bar, onset)) in enumerate(zip(midis, positions)):
        if bar >= total:
            problems.append(f"note {i} sounds after the last bar")
            continue
        k = max(j for j, b in enumerate(starts) if b <= bar)
        slot = timeline[k]
        if not int(slot["first_note"]) <= i <= int(slot["last_note"]):
            problems.append(f"note {i} sounds over {slot['chord']} but is mapped to another chord")
        facts = chord_facts(str(slot["chord"]))
        arrival = k != prev_slot
        prev_slot = k
        if facts is None:
            continue
        use = note_use(facts, m % 12, key=key, style=style)
        if use.category in HOLDABLE:
            continue
        if arrival or onset == 0 or i == len(midis) - 1:
            problems.append(f"{names[i]} ({use.role}, {use.category}) on a strong point over {slot['chord']}")
            continue
        if i + 1 >= len(midis) or abs(midis[i + 1] - m) > 2:
            problems.append(f"{names[i]} ({use.category}) over {slot['chord']} does not move on by step")
    return problems


def opening_contour(motif: dict[str, Any], n: int = 4) -> tuple[int, ...]:
    m = [int(x) for x in motif.get("midi") or []][: n + 1]
    return tuple((b > a) - (b < a) for a, b in zip(m, m[1:]))


def continuity(seed: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """How much of the seed survives: its rhythm cell and its opening shape."""
    s_cell = list((seed.get("span_seed") or {}).get("rhythm_cell") or [])
    o_cell = list((other.get("span_seed") or {}).get("rhythm_cell") or [])
    return {
        "same_rhythm_cell": bool(s_cell) and s_cell == o_cell,
        "same_opening_shape": opening_contour(seed) == opening_contour(other),
        "same_pitches": [int(x) for x in seed.get("midi") or []] == [int(x) for x in other.get("midi") or []],
    }


# --------------------------------------------------------------------------- phrasing


def _durations(motif: dict[str, Any]) -> list[tuple[Fraction, Fraction, bool]]:
    return [(Fraction(str(e.get("on") or "0")), Fraction(str(e.get("dur") or "0")), bool(e.get("rest")))
            for e in motif.get("rhythm_events") or []]


def note_density(motif: dict[str, Any]) -> Fraction:
    """Sounding notes per quarter note over the whole example."""
    events = _durations(motif)
    total = sum((d for _o, d, _r in events), Fraction(0))
    notes = sum(1 for _o, _d, rest in events if not rest)
    return Fraction(notes) / total if total else Fraction(0)


def breathless_bars(motif: dict[str, Any]) -> Fraction:
    """The longest stretch (in bars) with no rest and no held note (half a bar or longer) to
    breathe at — what a wind player has to play in one breath."""
    bar = quarters_per_bar(str((motif.get("rhythm_meta") or {}).get("meter") or "4/4"))
    run = longest = Fraction(0)
    for _on, dur, rest in _durations(motif):
        if rest:
            run = Fraction(0)
            continue
        run += dur
        longest = max(longest, run)
        if dur >= bar / 2:
            run = Fraction(0)
    return longest / bar


def with_breaths(motif: dict[str, Any], *, every_bars: int = BREATH_EVERY_BARS) -> dict[str, Any]:
    """Phrase the example: every ``every_bars`` bars, the last held note before the phrase
    boundary gives up its tail to a rest (a quarter becomes an eighth and an eighth rest, a half
    a quarter and a quarter rest …). No onset, pitch or note-to-chord mapping changes, so the
    note check still applies exactly; the final note of the example is never shortened."""
    bar = quarters_per_bar(str((motif.get("rhythm_meta") or {}).get("meter") or "4/4"))
    events = [dict(e) for e in motif.get("rhythm_events") or []]
    end = sum((Fraction(str(e.get("dur") or "0")) for e in events), Fraction(0))
    step = bar * every_bars
    boundary = step
    while boundary < end:
        window = [
            i for i, e in enumerate(events)
            if Fraction(str(e["on"])) < boundary <= Fraction(str(e["on"])) + Fraction(str(e["dur"])) + bar
            and Fraction(str(e["on"])) + Fraction(str(e["dur"])) <= boundary
        ]
        if not any(events[i].get("rest") for i in window):
            held = [i for i in window if not events[i].get("rest") and not events[i].get("tup")
                    and Fraction(str(events[i]["dur"])) >= 1]
            if held:
                i = held[-1]
                on, dur = Fraction(str(events[i]["on"])), Fraction(str(events[i]["dur"]))
                rest = Fraction(1, 2) if dur < 2 else Fraction(1)
                events[i] = {**events[i], "dur": str(dur - rest), "w": str(dur - rest)}
                events.insert(i + 1, {"on": str(on + dur - rest), "dur": str(rest), "w": str(rest), "rest": True,
                                      "tup": None, "ts": False, "n": None})
        boundary += step
    out = dict(motif)
    out["rhythm_events"] = events
    return out


def _phrased(plan: Any, link: Any, motif: dict[str, Any]) -> dict[str, Any]:
    """``motif`` with breaths — re-checked by the validator; the unphrased motif is kept if the
    phrased one ever fails (it cannot, since only note lengths change, but it is never assumed)."""
    phrased = with_breaths(motif)
    if validate_motif(phrased, _repeat_link(link, phrased), key=plan.key, style=plan.style):
        return motif
    return phrased


# --------------------------------------------------------------------------- generation


def _generate(link: Any, plan: Any, *, instrument: str, seed: int | None = None, mc2_plan: dict | None = None,
              constraints: Any = None, length: str = "seed") -> dict[str, Any]:
    from span_motif_engine import generate_span_motif

    return generate_span_motif(
        link.span, level=plan.level, instrument=instrument, meter=plan.meter, seed=seed, plan=mc2_plan,
        focus=_focus_label(plan), style=plan.style, constraints=constraints, length=length,
    )


def seed_motif(plan: Any, scope: Any, *, nonce: int, instrument: str, plan_key: str = "") -> tuple[dict[str, Any] | None, Any, str]:
    """The plan's seed: ``(motif, link, limitation)`` — deterministic for plan + nonce.

    The first valid candidate within the level's density cap wins; if none is that calm, the
    least busy valid candidate is used."""
    links = [link for link in scope.chain if link.span is not None]
    if not links:
        return None, None, LIMIT_VAMP if scope.rhythm.distinct_chords <= 1 else LIMIT_NO_WINDOW
    link = next((link for link in links if link.exact_bar_timing), None)
    if link is None:
        return None, None, LIMIT_TIMING
    idea = next((c for c in plan.challenges if c.kind == "idea"), None)
    base = example_seed_value(plan_key or plan.plan_id, nonce)
    cap = DENSITY_CAP.get(plan.level, Fraction(1))
    calmest: dict[str, Any] | None = None
    for constraints in _ladder(_constraints(idea)):
        for k in range(MAX_ATTEMPTS):
            try:
                motif = _generate(link, plan, instrument=instrument, seed=base + k, constraints=constraints)
            except Exception:
                continue
            if validate_motif(motif, link, key=plan.key, style=plan.style):
                continue
            if note_density(motif) <= cap:
                return motif, link, ""
            if calmest is None or note_density(motif) < note_density(calmest):
                calmest = motif
    if calmest is not None:
        return calmest, link, ""
    return None, link, LIMIT_UNAVAILABLE


def _ladder(constraints: Any) -> list[Any]:
    """The challenge's own constraints first, then progressively safer pitch choices: no outside
    notes, then chord tones only. Every rung is still validated; nothing is ever relaxed."""
    import dataclasses

    from span_motif_engine import SpanConstraints

    base = constraints or SpanConstraints()
    rungs = [constraints, dataclasses.replace(base, no_chromatic=True),
             dataclasses.replace(base, no_chromatic=True, pitch_space="chord")]
    out: list[Any] = []
    for rung in rungs:
        if rung not in out:
            out.append(rung)
    return out


def carries(seed: dict[str, Any], link: Any, plan: Any, *, instrument: str, constraints: Any = None) -> Iterator[dict[str, Any]]:
    """The seed's idea (seed, family, rhythm cell) replayed on ``link``'s chords: every distinct
    version that passes :func:`validate_motif`, best first (deterministic)."""
    base = {k: v for k, v in (seed.get("span_seed") or {}).items() if k != "attempt"}
    if not base:
        return
    seen: set[tuple[int, ...]] = set()
    for rung in _ladder(constraints):
        for k in range(MAX_ATTEMPTS):
            try:
                motif = _generate(link, plan, instrument=instrument, mc2_plan={**base, "attempt": k}, constraints=rung)
            except Exception:
                continue
            ident = tuple(int(m) for m in motif.get("midi") or [])
            if ident in seen or validate_motif(motif, link, key=plan.key, style=plan.style):
                continue
            seen.add(ident)
            yield motif


def carry(seed: dict[str, Any], link: Any, plan: Any, *, instrument: str, constraints: Any = None) -> dict[str, Any] | None:
    """The first validated :func:`carries` version, or ``None``."""
    return next(carries(seed, link, plan, instrument=instrument, constraints=constraints), None)


def _segment(link: Any, motif: dict[str, Any], label: str = "", plan: Any = None) -> Segment:
    """A shown phrase: phrased with breaths (re-validated) when the plan is given."""
    shown = _phrased(plan, link, motif) if plan is not None else motif
    return Segment(link.start_bar, link.end_bar, tuple(link.chords), shown, label)


def _link(scope: Any, index: int) -> Any:
    return next((link for link in scope.chain if link.index == index), None)


def build_example(plan: Any, scope: Any, stage: int, *, nonce: int = 0, instrument: str = "", plan_key: str = "") -> Example:
    """The example for challenge ``stage`` of ``plan`` (``scope`` is the plan's S1 scope).

    ``plan_key`` (the stored plan id) and ``instrument`` (the instrument the plan was built
    for) fix the example's identity; the default is the plan's own."""
    ch = plan.challenges[stage]
    inst = instrument or plan.instrument
    seed, seed_link, limitation = seed_motif(plan, scope, nonce=nonce, instrument=inst, plan_key=plan_key)
    if ch.kind == "roadmap":
        return _roadmap(plan, scope, stage, seed, seed_link, inst, limitation)
    if seed is None:
        return Example(stage, ch.kind, "", limitation=limitation)
    if ch.kind == "idea":
        moved = (
            f"The opening bars can't be notated exactly (a single chord or mid-bar changes), so this idea is built on "
            f"bars {seed_link.start_bar}–{seed_link.end_bar}." if seed_link.index != scope.chain[0].index else ""
        )
        return Example(
            stage, ch.kind,
            "One possible starting idea over these chords — learn it, then make it your own.",
            (_segment(seed_link, seed, "Your idea", plan=plan),), limitation=moved, continuity=continuity(seed, seed),
        )
    if ch.kind == "rhythm":
        varied = _new_rhythm(seed, seed_link, plan)
        if varied is None:
            return Example(stage, ch.kind, "", limitation="No other rhythm fits these notes' bar layout cleanly, so no re-timed version is shown.")
        return Example(
            stage, ch.kind,
            "The same notes as the starting idea, re-timed: listen for the new rhythm while the shape stays.",
            (_segment(seed_link, seed, "Starting idea", plan=plan), _segment(seed_link, varied, "New rhythm", plan=plan)),
            continuity=continuity(seed, varied),
        )
    if ch.kind == "moment" and not ch.example:
        return Example(stage, ch.kind, "", limitation=LIMIT_PICKUP)
    target = _link(scope, int((ch.example or {}).get("link_index", 0)))
    if ch.kind == "moment" and ch.targets and (target is None or ch.targets[0].chord not in target.chords):
        target = next((l for l in scope.chain if ch.targets[0].chord in l.chords and _notatable(l)), target)
    if not _notatable(target):
        return Example(stage, ch.kind, "", limitation=LIMIT_TIMING if target is not None and target.span is not None else LIMIT_NO_WINDOW)
    if ch.kind == "moment":
        return _moment(plan, ch, stage, seed, target, inst)
    constraints = _constraints(ch)
    if ch.kind == "connect":
        carried = seed if target.index == seed_link.index else carry(seed, target, plan, instrument=inst, constraints=constraints)
        if carried is None:
            return Example(stage, ch.kind, "", limitation=LIMIT_UNAVAILABLE)
        kept = continuity(seed, carried)
        if carried is seed:
            caption = "The starting idea already crosses this change — notice where it lands when the chord moves."
        elif kept["same_rhythm_cell"]:
            caption = "The starting idea's rhythm carried into these chords — the notes move to fit, the idea stays recognisable."
        else:
            caption = "The starting idea carried into these chords — the notes move to fit the new harmony."
        return Example(stage, ch.kind, caption, (_segment(target, carried, "Idea, carried", plan=plan),), continuity=kept)
    if ch.kind == "expand":
        return _expand(plan, ch, stage, seed, seed_link, target, inst, constraints)
    return Example(stage, ch.kind, "", limitation=LIMIT_UNAVAILABLE)


def _new_rhythm(seed: dict[str, Any], link: Any, plan: Any) -> dict[str, Any] | None:
    """The seed's pitches in the next motivic rhythm that still passes the note check (re-timing
    can move a passing note onto a downbeat, so each rhythm is validated)."""
    from span_motif_engine import cycle_span_rhythm

    current = seed
    for _ in range(4):
        try:
            current = cycle_span_rhythm(current)
        except Exception:
            return None
        if current is None or current.get("rhythm_events") == seed.get("rhythm_events"):
            return None
        if not validate_motif(current, link, key=plan.key, style=plan.style):
            return current
    return None


def _anticipates(ch: Any) -> bool:
    return any(c.kind == "change_at" for ln in ch.lines for c in ln.claims)


_RISE_WORDS = {1: "a half step", 2: "a step", 3: "a third", 4: "a third", 5: "a fourth", 7: "a fifth",
               8: "a sixth", 9: "a sixth"}
CONCERT_REGISTER = (55, 81)  # MC2's comfortable range (G3–A5); a register shift must stay inside it


def _expand(plan: Any, ch: Any, stage: int, seed: dict[str, Any], seed_link: Any, link: Any, instrument: str,
            constraints: Any) -> Example:
    """Develop the idea — never just "more notes". In preference order for the level:

    - **answered higher**: the same rhythm cell carried again with a higher high point (a step
      to a fifth up) — a register shift / climax the ear follows (Beginner's "play it again a
      little higher");
    - **call and answer** (Advanced): MC2's two-pass development, the second pass answering;
    - **filled in**: MC2's one-pass development, only when it also climbs and stays calm;
    - **sequence** (simple, deterministic): the idea moved up a third (else a step, else a
      fifth) inside the key — same rhythm, same shape, a higher answer;
    - **chord-tone climb** (simple, deterministic): each chord note moves up to the next note of
      its own chord — an arpeggio idea climbing an inversion, same rhythm and shape;
    - **answered lower**: the same chord-tone move downwards, when climbing would leave the
      comfortable range;
    - **register shift** (last resort): the idea itself an octave higher (or lower when it
      would leave the comfortable range) — same notes, same rhythm, a new colour.

    Every candidate passes the note check and the level's density cap; a melodic-phrasing
    challenge prefers a high point on its own target note. The caption only names what was
    measured."""
    from itertools import islice

    from span_motif_engine import develop_span_motif

    carried = seed if link.index == seed_link.index else carry(seed, link, plan, instrument=instrument, constraints=constraints)
    if carried is None:
        return Example(stage, ch.kind, "", limitation=LIMIT_UNAVAILABLE)
    cap = EXPAND_DENSITY_CAP.get(plan.level, Fraction(5, 4))
    peak_target = ch.targets[0] if ch.targets and plan.focus == "melodic_phrasing" else None
    top = max(int(m) for m in carried["midi"])
    options: dict[str, list[tuple[tuple, dict[str, Any]]]] = {
        "higher": [], "answer": [], "filled": [], "sequence": [], "climb": [], "descend": [], "register": []}

    for alt in islice(carries(seed, link, plan, instrument=instrument, constraints=constraints), 8):
        rise = max(int(m) for m in alt["midi"]) - top
        if rise in _RISE_WORDS and note_density(alt) <= cap:
            on_target = peak_target is not None and _peak(alt) == (peak_target.pc, peak_target.chord)
            options["higher"].append(((on_target, -abs(rise - 3)), alt))
    for length, kind in (("extended", "answer"), ("standard", "filled")):
        if kind == "answer" and plan.level != "Advanced":
            continue
        try:
            developed = develop_span_motif(link.span, carried, length=length)
        except Exception:
            continue
        if not developed or validate_motif(developed, _repeat_link(link, developed), key=plan.key, style=plan.style):
            continue
        if note_density(developed) > cap:
            continue
        climbs = max(int(m) for m in developed["midi"]) > top
        if (kind == "filled" or plan.focus == "melodic_phrasing") and not climbs:
            continue  # "more notes" alone, or no high point when the challenge asks for one
        on_target = peak_target is not None and _peak(developed) == (peak_target.pc, peak_target.chord)
        options[kind].append(((on_target, climbs), developed))

    lo, hi = CONCERT_REGISTER
    for steps in (2, 1, 4):
        moved = _diatonic_shift(carried, steps, plan.key)
        if (moved is not None and max(moved["midi"]) <= hi
                and not validate_motif(moved, link, key=plan.key, style=plan.style)):
            on_target = peak_target is not None and _peak(moved) == (peak_target.pc, peak_target.chord)
            options["sequence"].append(((on_target, steps == 2), moved))
            break
    climbed = _chord_tone_climb(carried)
    if climbed is not None and max(climbed["midi"]) <= hi and not validate_motif(climbed, link, key=plan.key, style=plan.style):
        on_target = peak_target is not None and _peak(climbed) == (peak_target.pc, peak_target.chord)
        options["climb"].append(((on_target, True), climbed))
    # A challenge that asks for a higher point (melodic phrasing) is never answered lower.
    wants_higher = plan.focus == "melodic_phrasing"
    climb_too_high = climbed is not None and max(climbed["midi"]) > hi and not validate_motif(
        climbed, link, key=plan.key, style=plan.style)
    lower = _chord_tone_climb(carried, -1)
    if (not wants_higher and lower is not None and min(lower["midi"]) >= lo
            and not validate_motif(lower, link, key=plan.key, style=plan.style)):
        options["descend"].append(((False, True), lower))
    for octave in ((12,) if wants_higher else (12, -12)):
        moved = _octave_shift(carried, octave)
        if lo <= min(moved["midi"]) and max(moved["midi"]) <= hi and not validate_motif(moved, link, key=plan.key, style=plan.style):
            options["register"] = [((False, octave > 0), moved)]
            break
    order = ("answer", "higher", "filled") if plan.level == "Advanced" else ("higher", "filled")
    order += ("sequence", "climb", "descend", "register")
    if peak_target is not None:  # the challenge names a high note: an on-target version wins
        on_target = [k for k in order if any(r[0] for r, _m in options[k])]
        order = tuple(on_target) + tuple(k for k in order if k not in on_target)
    kind = next((k for k in order if options[k]), None)
    if kind is None:
        out_of_range = any(
            m is not None and not validate_motif(m, link, key=plan.key, style=plan.style)
            for m in (climbed, lower)
        )
        return Example(stage, ch.kind, "", limitation=LIMIT_EXPAND_RANGE if out_of_range else LIMIT_UNAVAILABLE)
    _rank, developed = max(options[kind], key=lambda o: o[0])  # stable: first best wins
    if kind == "higher":
        rise = max(int(m) for m in developed["midi"]) - top
        words = [f"the same rhythm with new notes, and its high point is {_RISE_WORDS[rise]} higher — "
                 "a new high point to aim for"]
        label = "Answered higher"
    elif kind == "sequence":
        steps = {2: "a third", 1: "a step", 4: "a fifth"}
        moved_by = next(w for k, w in steps.items() if _diatonic_shift(carried, k, plan.key) is not None
                        and _diatonic_shift(carried, k, plan.key)["midi"] == developed["midi"])
        words = [f"the idea sequenced up {moved_by} inside the key — same rhythm, same shape, a higher answer"]
        label = "Sequenced higher"
    elif kind == "climb":
        words = ["the same rhythm and shape, each chord note moved up to the next note of its chord — "
                 "the idea climbs to a higher answer"]
        label = "Climbing higher"
    elif kind == "descend":
        words = ["the same rhythm and shape, each chord note moved down to the next note of its chord — "
                 "the idea answered lower, a calmer reply"
                 + (" (climbing would leave the comfortable range here)" if climb_too_high else "")]
        label = "Answered lower"
    elif kind == "register":
        up = max(int(m) for m in developed["midi"]) > top
        words = [f"the same idea moved an octave {'higher' if up else 'lower'} — a register shift changes its colour "
                 "while every note still fits the chords"]
        label = "An octave higher" if up else "An octave lower"
    else:
        words = _development_words(carried, developed, "extended" if kind == "answer" else "standard", plan)
        label = "Developed"
    if peak_target is not None and _peak(developed) == (peak_target.pc, peak_target.chord):
        words.append(f"its high point is the target note over {peak_target.chord}")
    caption = "The idea developed: " + "; ".join(words) + "."
    note = (
        "The challenge asks you to anticipate a chord change by an eighth note; this example lands exactly "
        "on the bar line because example notation can't show anticipations yet." if _anticipates(ch) else ""
    )
    return Example(
        stage, ch.kind, caption,
        (_segment(link, carried, "Idea", plan=plan), _segment(link, developed, label, plan=plan)),
        limitation=note, continuity={**continuity(seed, developed), "development": kind},
    )


def _diatonic_shift(motif: dict[str, Any], steps: int, key: str) -> dict[str, Any] | None:
    """The motif moved ``steps`` scale degrees up inside ``key`` (a sequence), respelled in the
    key. A note outside the scale (a chromatic approach) moves by the same interval as the scale
    note it leads into, so it stays an approach; ``None`` when there is no such note."""
    from song_coach_harmony import key_facts

    kf = key_facts(key)
    scale = list(kf.scale_pcs)
    src = [int(m) for m in motif.get("midi") or []]
    up: list[int | None] = []
    for m in src:
        if m % 12 in scale:
            pc = scale[(scale.index(m % 12) + steps) % len(scale)]
            up.append((pc - m % 12) % 12 or 12)
        else:
            up.append(None)
    for i in range(len(up) - 1, -1, -1):  # chromatic notes borrow the next scale note's interval
        if up[i] is None:
            up[i] = up[i + 1] if i + 1 < len(up) else None
    if not up or any(u is None for u in up):
        return None
    midis = [m + u for m, u in zip(src, up)]
    out = dict(motif)
    out["midi"] = midis
    out["notes"] = [kf.spell(m % 12) for m in midis]
    return out


def _chord_tone_climb(motif: dict[str, Any], direction: int = 1) -> dict[str, Any] | None:
    """Each note that belongs to its chord moves to that chord's next tone up (``direction``
    1) or down (-1); any other note moves by the same interval as the note it leads into.
    ``None`` if that is impossible."""
    from song_coach_harmony import chord_facts, key_facts

    src = [int(m) for m in motif.get("midi") or []]
    timeline = list(motif.get("chord_timeline") or [])
    up: list[int | None] = []
    names: list[str | None] = []
    for i, m in enumerate(src):
        slot = next((t for t in timeline if int(t["first_note"]) <= i <= int(t["last_note"])), None)
        facts = chord_facts(str(slot["chord"])) if slot else None
        tones = sorted({t.pc for t in facts.tones}) if facts else []
        if facts is None or m % 12 not in tones:
            up.append(None)
            names.append(None)
            continue
        if direction > 0:
            nxt = min(tones, key=lambda pc: ((pc - m % 12) % 12 or 12))
            up.append((nxt - m % 12) % 12 or 12)
        else:
            nxt = min(tones, key=lambda pc: ((m % 12 - pc) % 12 or 12))
            up.append(-((m % 12 - nxt) % 12 or 12))
        tone = facts.tone_for_pc(nxt)
        names.append(tone.name if tone else None)
    for i in range(len(up) - 1, -1, -1):
        if up[i] is None:
            up[i] = up[i + 1] if i + 1 < len(up) else None
    if not up or any(u is None for u in up):
        return None
    midis = [m + u for m, u in zip(src, up)]
    key = str(motif.get("key_center") or "C")
    out = dict(motif)
    out["midi"] = midis
    out["notes"] = [n if n else key_facts(key).spell(m % 12) for n, m in zip(names, midis)]
    return out


def _octave_shift(motif: dict[str, Any], semitones: int) -> dict[str, Any]:
    """The same motif in another octave (names keep their spelling; every pitch class, onset
    and chord mapping is unchanged)."""
    out = dict(motif)
    out["midi"] = [int(m) + semitones for m in motif.get("midi") or []]
    return out


def _peak(motif: dict[str, Any]) -> tuple[int, str]:
    """(pitch class, chord) of the motif's highest note (its first occurrence)."""
    midis = [int(m) for m in motif.get("midi") or []]
    i = midis.index(max(midis))
    slot = next((s for s in motif.get("chord_timeline") or [] if int(s["first_note"]) <= i <= int(s["last_note"])), {})
    return midis[i] % 12, str(slot.get("chord") or "")


def _development_words(carried: dict[str, Any], developed: dict[str, Any], length: str, plan: Any) -> list[str]:
    """What actually changed between ``carried`` and ``developed`` — measured here with the
    coaching chord reader, never taken from the generator's own labels."""
    from song_coach_harmony import HOLDABLE, chord_facts, key_facts, note_use

    a = [int(m) for m in carried.get("midi") or []]
    b = [int(m) for m in developed.get("midi") or []]
    words: list[str] = []
    twice = length == "extended" and len(developed.get("chord_timeline") or []) > len(carried.get("chord_timeline") or [])
    if twice:
        words.append("it plays twice, and the second time answers the first")
    if max(b) > max(a):
        words.append("it climbs to a higher point")
    origin = list(developed.get("seed_note_origin") or [])
    timeline = list(developed.get("chord_timeline") or [])
    added = [i for i, o in enumerate(origin) if o is None and i < len(b)]
    chord_notes = 0
    for i in added:
        slot = next((t for t in timeline if int(t["first_note"]) <= i <= int(t["last_note"])), None)
        facts = chord_facts(str(slot["chord"])) if slot else None
        if facts is not None and note_use(facts, b[i] % 12, key=plan.key, style=plan.style).category in HOLDABLE:
            chord_notes += 1
    if added:
        parts = []
        if chord_notes:
            parts.append(f"{chord_notes} chord note{'s' if chord_notes != 1 else ''}")
        if len(added) - chord_notes:
            n = len(added) - chord_notes
            parts.append(f"{n} passing note{'s' if n != 1 else ''} that step on")
        words.append(f"{len(added)} note{'s' if len(added) != 1 else ''} added between the idea's notes ({' and '.join(parts)})")
    in_key = key_facts(plan.key).in_key_pcs
    if any(m % 12 not in in_key and i + 1 < len(b) and abs(b[i + 1] - m) == 1 for i, m in enumerate(b)):
        words.append("a note from outside the key leads by half step into the next note" if plan.level == "Beginner"
                     else "a chromatic note leads by half step into the next note")
    return words or ["the same idea, re-shaped to fill the bars"]


def _repeat_link(link: Any, motif: dict[str, Any]) -> Any:
    """A developed 'extended' motif plays the window twice: validate against that timeline."""
    from types import SimpleNamespace

    chords = tuple(str(s.get("chord")) for s in motif.get("chord_timeline") or [])
    if chords == tuple(link.chords):
        return link
    span_bars = link.end_bar - link.start_bar + 1
    passes = max(1, len(chords) // max(1, len(link.chords)))
    return SimpleNamespace(chords=chords, start_bar=link.start_bar, end_bar=link.start_bar + span_bars * passes - 1)


def _moment(plan: Any, ch: Any, stage: int, seed: dict[str, Any], link: Any, instrument: str) -> Example:
    """Demonstrate the special note: the carried idea must land on it when its chord arrives."""
    import dataclasses

    from song_coach_harmony import chord_facts
    from span_motif_engine import SpanConstraints

    target = ch.targets[0] if ch.targets else None
    facts = chord_facts(target.chord) if target else None
    if target is None or facts is None or target.chord not in link.chords:
        return Example(stage, ch.kind, "", limitation=LIMIT_UNAVAILABLE)
    tone = facts.tone_for_pc(target.pc)
    role = tone.engine_role if tone else ""
    slot_index = list(link.chords).index(target.chord)
    base = _constraints(ch) or SpanConstraints()
    tries = ([dataclasses.replace(base, target_roles=(role,))] if role in ("R", "3", "5", "7") else []) + [base]
    for constraints in tries:
        motif = carry(seed, link, plan, instrument=instrument, constraints=constraints)
        if motif is None:
            continue
        slot = (motif.get("chord_timeline") or [])[slot_index]
        sounding = [int(m) % 12 for m in (motif.get("midi") or [])[int(slot["first_note"]): int(slot["last_note"]) + 1]]
        if target.pc in sounding:
            first = sounding[0] == target.pc
            caption = (
                f"The idea carried here lands on the special note as {target.chord} arrives."
                if first else f"The idea carried here uses the special note over {target.chord}."
            )
            return Example(stage, ch.kind, caption, (_segment(link, motif, "Idea, carried", plan=plan),), continuity=continuity(seed, motif))
    return Example(stage, ch.kind, "", limitation="No example here features the special note cleanly — try landing on it yourself as the chord arrives.")


def _roadmap(plan: Any, scope: Any, stage: int, seed: dict[str, Any] | None, seed_link: Any, instrument: str,
             limitation: str) -> Example:
    """The seed carried window by window: one practice sketch of a longer phrase."""
    if seed is None:
        return Example(stage, "roadmap", "", limitation=limitation or LIMIT_ROADMAP)
    constraints = _constraints(next((c for c in plan.challenges if c.kind == "idea"), None))
    segments: list[Segment] = []
    skipped = 0
    for link in scope.chain:
        if len(segments) >= MAX_ROADMAP_SEGMENTS:
            break
        if not _notatable(link):
            skipped += 1
            continue
        motif = seed if link.index == seed_link.index else carry(seed, link, plan, instrument=instrument, constraints=constraints)
        if motif is None:
            skipped += 1
            continue
        segments.append(_segment(link, motif, f"Bars {link.start_bar}–{link.end_bar}", plan=plan))
    if not segments:
        return Example(stage, "roadmap", "", limitation=LIMIT_ROADMAP)
    caption = (
        "One way your idea could travel through these bars, window by window — a practice sketch, "
        "not the song's own line. Join the pieces in your own words."
    )
    note = " Some bars are left for you (a single chord or mid-bar changes)." if skipped else ""
    return Example(stage, "roadmap", caption + note, tuple(segments),
                   continuity={"windows": len(segments), "same_rhythm_cell": all(
                       continuity(seed, s.motif)["same_rhythm_cell"] for s in segments)})


# --------------------------------------------------------------------------- display


# The app's transposition contract is pitch-class only (written key + 0–11 semitones). That is
# the true written interval for alto (M6), soprano (M2), B♭ trumpet and clarinet (M2), but the
# tenor sax sounds a major 9th and the baritone an octave + major 6th below written: their
# written line is an octave higher than the pitch-class shift. Applied here, for coaching
# examples only — the shared transposition engine and Missions are unchanged.
WRITTEN_EXTRA_OCTAVE = ("tenor", "baritone")
SAX_WRITTEN_RANGE = (58, 90)  # written B♭3–F♯6, the saxophone family's normal range
SAX_OCTAVE_NOTE = ("Written an octave lower than the concert example so it stays in the saxophone's normal "
                   "range — on your horn it sounds an octave below the piano version.")


def written_semitones(concert_key: str, chart_key: str, transposing_type: str = "") -> int:
    """Concert → written interval in semitones for the example's notation."""
    from music_theory import semitone_distance

    if not chart_key or chart_key == concert_key:
        return 0
    shift = int(semitone_distance(concert_key, chart_key) or 0)
    if any(word in str(transposing_type or "").lower() for word in WRITTEN_EXTRA_OCTAVE):
        shift += 12
    return shift


@dataclass(frozen=True)
class Notation:
    """One segment as the player reads it: projected notes / chords, ABC, optional guitar TAB."""

    abc: str
    key: str
    chords: tuple[str, ...]
    notes: tuple[str, ...]
    midi: tuple[int, ...]
    tab: str = ""
    shift: int = 0
    note: str = ""


def segment_notation(
    segment: Segment,
    *,
    concert_key: str,
    chart_key: str = "",
    project_chord: Any = None,
    instrument: str = "",
    bpm: int = 0,
    title: str = "",
    transposing_type: str = "",
) -> Notation:
    """Project a concert segment into the player's Written / Shape key for display only (the
    same projection and renderers as the Missions span examples), at the instrument's true
    written octave (see :data:`WRITTEN_EXTRA_OCTAVE`)."""
    from improvisation_motif import build_motif_abc, build_motif_guitar_tab, notation_clef_for_instrument
    from span_motif_engine import project_span_motif

    chart = chart_key or concert_key
    shift = written_semitones(concert_key, chart, transposing_type)
    note = ""
    midis = [int(m) for m in segment.motif.get("midi") or []]
    lo, hi = SAX_WRITTEN_RANGE
    if "saxophone" in str(transposing_type or "").lower():
        while midis and max(midis) + shift > hi and min(midis) + shift - 12 >= lo:
            shift -= 12  # the whole phrase, never one note
            note = SAX_OCTAVE_NOTE
    project = project_chord if (shift and project_chord is not None) else None
    shown = project_span_motif(segment.motif, semitones=shift, chart_key=chart, project_chord=project)
    abc_key = concert_key if not shift else chart
    abc = build_motif_abc(shown, key_center=abc_key, bpm=int(bpm or 90), title=title,
                          clef=notation_clef_for_instrument(instrument))
    chords = tuple((project or (lambda c: c))(str(t["chord"])) for t in segment.motif.get("chord_timeline") or [])
    tab = build_motif_guitar_tab(shown) if "guitar" in str(instrument or "").lower() else ""
    return Notation(abc, abc_key, chords, tuple(shown.get("notes") or ()), tuple(int(m) for m in shown.get("midi") or ()),
                    tab, shift, note)


__all__ = [
    "EXAMPLE_VERSION",
    "Example",
    "LIMIT_EXPAND_RANGE",
    "LIMIT_NO_WINDOW",
    "LIMIT_PICKUP",
    "LIMIT_ROADMAP",
    "LIMIT_TIMING",
    "LIMIT_UNAVAILABLE",
    "LIMIT_VAMP",
    "Notation",
    "Segment",
    "build_example",
    "carries",
    "carry",
    "continuity",
    "example_seed_value",
    "breathless_bars",
    "note_bars",
    "note_density",
    "quarters_per_bar",
    "opening_contour",
    "seed_motif",
    "segment_notation",
    "with_breaths",
    "written_semitones",
    "validate_motif",
]
