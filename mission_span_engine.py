"""MC3 — Multi-chord Missions: a musical objective carried through a 2-/3-chord HarmonicSpan.

A span Mission never generates notes itself. It turns its intent into
:class:`span_motif_engine.SpanConstraints` (target roles, pitch space, approach type,
dominant colour, rhythm intent) plus a short list of strategy families, asks
:func:`span_motif_engine.generate_span_motif` for a connected line (Build develops it for
Harder), and then validates the result **per chord and per transition**. A candidate that
does not demonstrate the Mission is rejected and the next seed is tried.

Single-chord Missions (``improvisation_missions``) are untouched; this module only serves
the Missions page when Target Scope is 2 or 3 chords.

Pipeline::

    Mission intent → constraints / families → generate_span_motif(...) [→ develop_span_motif]
                   → validate_mission_line(...) → accept (or try the next seed)

The returned example carries a ``handoff`` block (Mission id, span id, chord timeline,
example identity, note/chord assignment, loop length) for a later Mission Backing slice.
"""

from __future__ import annotations

import hashlib
import zlib
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Sequence

LEVELS = ("Beginner", "Intermediate", "Advanced")
DIFFICULTIES = ("easier", "normal", "harder")
JAZZY = {"jazz", "jazz_ballad", "bossa", "blues", "default"}
# Missions whose objective *is* chromatic or coloured — style may restrain them, not remove them.
_CHROMATIC_INTENT = {"approach_next_chord", "enclose_next_target", "dominant_tension_resolution", "bebop_line",
                     "ii_v_i_resolution"}
_RESOLVING = {"V_I", "ii_V_I", "secondary_dominant", "dominant_resolution", "subV_I", "ii_subV_I", "cadence"}


# --------------------------------------------------------------------------- catalog


@dataclass(frozen=True)
class SpanMission:
    id: str
    label: str
    kind: str  # span_compatible | span_specific
    brief: str
    levels: tuple[str, ...] = LEVELS
    realizes: tuple[str, ...] = ()  # single-chord Mission labels this carries across a span


SPAN_MISSIONS: tuple[SpanMission, ...] = (
    # New multi-chord Missions.
    SpanMission("guide_tone_voice_leading", "Voice-lead the guide tones", "span_compatible",
                "Connect the 3rd and 7th of each chord as smoothly as you can — hold common tones, move by half "
                "or whole steps, and let a 7th fall to the next chord's 3rd.",
                realizes=("Target only guide tones (3rds & 7ths)",)),
    SpanMission("target_each_change", "Target each chord change", "span_compatible",
                "Land on a meaningful chord tone of each new chord exactly as it arrives.",
                realizes=("Resolve every phrase on beat 1",)),
    SpanMission("motif_through_changes", "Motif through the changes", "span_compatible",
                "Keep one recognizable idea — same rhythm, same shape — and adapt it to each chord.",
                realizes=("Develop one motif for the entire solo",)),
    SpanMission("common_tone_voice_leading", "Common tones + nearest voice leading", "span_compatible",
                "Hold a note when the next chord shares it; otherwise move to the nearest note that fits."),
    SpanMission("approach_next_chord", "Approach the next chord", "span_compatible",
                "Use the last note of each chord to lead into an important note of the next one.",
                realizes=("Approach a chord tone chromatically",)),
    SpanMission("enclose_next_target", "Enclose the next target", "span_compatible",
                "Surround a target note of the next chord from above and below, then land on it at the change.",
                realizes=("Enclose a target chord tone before resolving",)),
    SpanMission("ii_v_i_resolution", "Resolve through a ii–V–I", "span_specific",
                "One phrase whose tension builds through ii and V and resolves clearly on I."),
    SpanMission("one_common_scale", "Use one common scale", "span_specific",
                "Play the whole span inside one scale that fits every chord — and hear each chord change color it."),
    SpanMission("dominant_tension_resolution", "Dominant tension → resolution", "span_specific",
                "Build tension on the dominant chord and resolve it into the next chord.",
                levels=("Intermediate", "Advanced"), realizes=("Create tension on dominant chords",)),
    # Existing single-chord Missions, adapted to a span.
    SpanMission("chord_tones_each_chord", "Improvise using only chord tones", "span_compatible",
                "Use only the notes of the chord that is sounding — switch notes when the chord changes."),
    SpanMission("rhythm_over_notes", "Focus on rhythm over note choice", "span_compatible",
                "Make one rhythmic idea the star; keep the notes simple and right for each chord."),
    SpanMission("scalar_runs", "Only scalar runs", "span_compatible",
                "Connect the chords with stepwise scale lines that land on a chord tone at each change."),
    SpanMission("resolve_to_third", "Resolve convincingly to the chord's 3rd", "span_compatible",
                "Arrive on the 3rd of every new chord by step."),
    SpanMission("bebop_line", "Create a bebop-style line", "span_compatible",
                "Flowing eighth notes with chord tones on the beat and chromatic approaches into each change.",
                levels=("Intermediate", "Advanced")),
    SpanMission("pentatonic_per_chord", "Improvise using a pentatonic scale that fits the chord", "span_compatible",
                "Use a pentatonic that fits each chord — and switch where the chord asks for a different one."),
    SpanMission("syncopated_phrase", "Create a phrase using a syncopated rhythm", "span_compatible",
                "A repeated off-beat rhythm through the changes, still landing on the right notes.",
                levels=("Intermediate", "Advanced")),
)
MISSIONS_BY_ID: dict[str, SpanMission] = {m.id: m for m in SPAN_MISSIONS}

# Every existing single-chord Mission, classified for span scope.
SINGLE_CHORD_CLASSIFICATION: dict[str, str] = {
    "Improvise using only chord tones": "span_compatible",
    "Use only 5 notes in one register": "single_chord_only",
    "Focus on rhythm over note choice": "span_compatible",
    "Create tension on dominant chords": "span_specific",  # → Dominant tension → resolution
    "Develop one motif for the entire solo": "span_compatible",  # → Motif through the changes
    "Use silence intentionally (rest every 2 bars)": "single_chord_only",
    "Resolve every phrase on beat 1": "span_compatible",  # → Target each chord change
    "No repeated rhythmic pattern twice in a row": "single_chord_only",
    "Target only guide tones (3rds & 7ths)": "span_compatible",  # → Voice-lead the guide tones
    "Play one chorus without scalar runs": "single_chord_only",
    "Only scalar runs": "span_compatible",
    "Approach a chord tone chromatically": "span_compatible",  # → Approach the next chord
    "Enclose a target chord tone before resolving": "span_compatible",  # → Enclose the next target
    "Resolve convincingly to the chord's 3rd": "span_compatible",
    "Create a bebop-style line": "span_compatible",
    "Improvise using a pentatonic scale that fits the chord": "span_compatible",
    "Improvise using a blues scale that fits the chord": "single_chord_only",
    "Create a phrase using a syncopated rhythm": "span_compatible",
}


def _level(level: str) -> str:
    low = str(level or "").strip().lower()
    return "Beginner" if low.startswith("beg") else "Advanced" if low.startswith("adv") else "Intermediate"


def _difficulty(variant: str) -> str:
    v = str(variant or "normal").strip().lower()
    return v if v in DIFFICULTIES else "normal"


# --------------------------------------------------------------------------- span facts


def _ctx(span: Any, chord: str):
    from span_motif_engine import _ctx as ctx

    return ctx(span.key_center, chord)


def _dominant_resolutions(span: Any) -> list[int]:
    """Indices of span chords that are dominants resolving (down a 5th or a half step) to the next."""
    out = []
    chords = list(span.chords)
    for i in range(len(chords) - 1):
        a, b = _ctx(span, chords[i]), _ctx(span, chords[i + 1])
        if a.quality not in ("dom", "aug"):
            continue
        motion = (b.chord_pcs[0] - a.chord_pcs[0]) % 12
        if motion in (5, 11) and b.quality not in ("dom",):
            out.append(i)
    return out


def _fifth_motions(span: Any) -> list[int]:
    """Chord pairs whose root falls a 5th from a 7th chord (where a 7th resolves to the next 3rd)."""
    out = []
    chords = list(span.chords)
    for i in range(len(chords) - 1):
        a, b = _ctx(span, chords[i]), _ctx(span, chords[i + 1])
        if (b.chord_pcs[0] - a.chord_pcs[0]) % 12 == 5 and len(a.chord_pcs) >= 4:
            out.append(i)
    return out


def common_collection(span: Any, *, key: str | None = None) -> tuple[str, tuple[int, ...], list[str]] | None:
    """(name, pitch classes, spelled notes) of a defensible scale shared by every chord, or None.

    ``key``: spell it in another chart (a written-key projection of the span).
    """
    names = tuple(getattr(span, "common_scales", ()) or ())
    if not names:
        return None
    from music_theory import pitch_class_from_spelled_note, semitone_distance, spell_diatonic_scale_from_root

    name = names[0]
    root, kind = name.split(" ", 1)
    if key and key != span.key_center:
        from music_theory import spell_note_in_key

        shift = int(semitone_distance(span.key_center, key) or 0)
        root = spell_note_in_key((pitch_class_from_spelled_note(root) + shift) % 12, key)
        name = f"{root} {kind}"
    steps = {"major": (0, 2, 4, 5, 7, 9, 11), "harmonic minor": (0, 2, 3, 5, 7, 8, 11)}.get(kind)
    if steps is None:
        return None
    rpc = pitch_class_from_spelled_note(root)
    pcs = tuple((rpc + s) % 12 for s in steps)
    from span_motif_explain import pretty

    try:
        notes = [pretty(n) for n in spell_diatonic_scale_from_root(root, list(steps))]
    except Exception:
        notes = []
    return pretty(name), pcs, notes


def unavailable_reason(mission: SpanMission | str, span: Any, *, level: str, style: str = "default") -> str:
    """Why ``mission`` cannot be offered on ``span`` for this player ("" = available)."""
    m = MISSIONS_BY_ID[mission] if isinstance(mission, str) else mission
    lvl = _level(level)
    if lvl not in m.levels:
        return f"needs {' or '.join(m.levels)} level"
    ctxs = [_ctx(span, c) for c in span.chords]
    if m.id == "guide_tone_voice_leading" and sum(1 for c in ctxs if len(c.chord_pcs) >= 4) < 2:
        return "needs at least two chords with a 7th"
    if m.id == "ii_v_i_resolution" and span.relationship != "ii_V_I":
        return "the span is not a ii–V–I"
    if m.id == "one_common_scale" and common_collection(span) is None:
        return "no single scale fits every chord here"
    if m.id == "dominant_tension_resolution" and not _dominant_resolutions(span):
        return "no dominant chord resolves inside this span"
    if m.id == "common_tone_voice_leading" and not any(
        set(a.chord_pcs) & set(b.chord_pcs) for a, b in zip(ctxs, ctxs[1:])
    ):
        return "neighbouring chords share no note"
    if m.id == "resolve_to_third" and any(c.quality == "sus" for c in ctxs):
        return "a suspended chord has no 3rd"
    if m.id == "bebop_line" and style not in JAZZY:
        return "bebop language does not fit this song's style"
    return ""


def available_span_missions(span: Any, *, level: str, style: str = "default") -> list[SpanMission]:
    return [m for m in SPAN_MISSIONS if not unavailable_reason(m, span, level=level, style=style)]


# --------------------------------------------------------------------------- mission → constraints


def mission_plan(mission_id: str, *, level: str, variant: str, span: Any, style: str = "default") -> tuple[tuple[str, ...], Any]:
    """(strategy families to try, SpanConstraints) for this Mission at this level / difficulty."""
    from span_motif_engine import SpanConstraints

    lvl = _level(level)
    beg, adv = lvl == "Beginner", lvl == "Advanced"
    fam: dict[str, tuple[str, ...]]
    c = SpanConstraints()
    if mission_id == "guide_tone_voice_leading":
        fam = {"Beginner": ("common_tone_anchor", "chord_tone_cell"), "Intermediate": ("guide_tone_line", "sequence"),
               "Advanced": ("guide_tone_line", "enclosure_line")}
        c = SpanConstraints(target_roles=("3", "7"), smooth_targets=True, connector="step" if beg else "")
    elif mission_id == "target_each_change":
        fam = {"Beginner": ("chord_tone_cell", "scalar_fragment", "lyrical_arch"),
               "Intermediate": ("scalar_fragment", "arpeggio_scale", "guide_tone_line"),
               "Advanced": ("enclosure_line", "arpeggio_scale", "bebop_run")}
        roles = ("R", "3", "5") if beg else ("3", "7")
        c = SpanConstraints(target_roles=roles, connector="step" if beg else "")
    elif mission_id == "motif_through_changes":
        fam = {"Beginner": ("chord_tone_cell", "scalar_fragment"), "Intermediate": ("sequence", "call_response"),
               "Advanced": ("sequence", "intervallic_cell", "call_response")}
        c = SpanConstraints(rhythm_focus="Improvisation")
    elif mission_id == "common_tone_voice_leading":
        fam = {"Beginner": ("common_tone_anchor", "lyrical_arch"), "Intermediate": ("common_tone_anchor", "guide_tone_line"),
               "Advanced": ("guide_tone_line", "scalar_fragment")}
        c = SpanConstraints(smooth_targets=True, connector="step")
    elif mission_id == "approach_next_chord":
        fam = {"Beginner": ("scalar_fragment", "chord_tone_cell"), "Intermediate": ("scalar_fragment", "arpeggio_scale"),
               "Advanced": ("enclosure_line", "arpeggio_scale", "bebop_run")}
        c = SpanConstraints(connector="step" if beg else "double" if adv else "chromatic", tail_short=True, color="forbid")
    elif mission_id == "enclose_next_target":
        fam = {"Beginner": ("scalar_fragment", "chord_tone_cell"), "Intermediate": ("enclosure_line", "scalar_fragment"),
               "Advanced": ("enclosure_line", "bebop_run")}
        c = SpanConstraints(connector="enclosure", tail_short=True, color="forbid", target_roles=() if beg else ("3", "7", "R"))
    elif mission_id == "ii_v_i_resolution":
        fam = {"Beginner": ("chord_tone_cell", "scalar_fragment"), "Intermediate": ("guide_tone_line", "enclosure_line"),
               "Advanced": ("guide_tone_line", "bebop_run", "enclosure_line")}
        if beg:
            c = SpanConstraints(target_roles=("R", "3", "5"), connector="step", no_chromatic=True)
        elif adv:
            c = SpanConstraints(target_roles=("3", "7"), color="require")
        else:
            c = SpanConstraints(target_roles=("3", "7"), connector="chromatic", tail_short=True)
    elif mission_id == "one_common_scale":
        fam = {"Beginner": ("scalar_fragment", "lyrical_arch"), "Intermediate": ("scalar_fragment", "arpeggio_scale"),
               "Advanced": ("scalar_fragment", "arpeggio_scale", "intervallic_cell")}
        coll = common_collection(span)
        c = SpanConstraints(pitch_space="common", common_pcs=coll[1] if coll else (), no_chromatic=True, connector="step")
    elif mission_id == "dominant_tension_resolution":
        fam = {"Intermediate": ("guide_tone_line", "enclosure_line"), "Advanced": ("bebop_run", "enclosure_line", "guide_tone_line"),
               "Beginner": ("chord_tone_cell",)}
        c = (SpanConstraints(color="require", target_roles=("3", "7")) if adv
             else SpanConstraints(target_roles=("3", "7"), connector="chromatic", tail_short=True))
    elif mission_id == "chord_tones_each_chord":
        fam = {lv: ("chord_tone_cell", "rhythmic_motif") for lv in LEVELS}
        c = SpanConstraints(pitch_space="chord", no_chromatic=True)
    elif mission_id == "rhythm_over_notes":
        fam = {lv: ("rhythmic_motif", "chord_tone_cell") for lv in LEVELS}
        # Few, simple pitches so the rhythm is the challenge; jazz above Beginner swings it.
        c = SpanConstraints(rhythm_focus="Rhythm", simple_pitches=True, free_ending=False,
                            require_syncopation=style in JAZZY and not beg)
    elif mission_id == "scalar_runs":
        fam = {lv: ("scalar_fragment",) for lv in LEVELS}
        c = SpanConstraints(pitch_space="scale", connector="step", no_chromatic=beg)
    elif mission_id == "resolve_to_third":
        fam = {"Beginner": ("scalar_fragment", "chord_tone_cell"), "Intermediate": ("guide_tone_line", "scalar_fragment"),
               "Advanced": ("guide_tone_line", "enclosure_line")}
        c = SpanConstraints(target_roles=("3",), connector="step" if beg else "", color="forbid")
    elif mission_id == "bebop_line":
        fam = {"Intermediate": ("enclosure_line", "scalar_fragment"), "Advanced": ("bebop_run", "enclosure_line"),
               "Beginner": ("scalar_fragment",)}
        c = SpanConstraints(rhythm_focus="Bebop Phrasing", connector="chromatic" if not adv else "", tail_short=True)
    elif mission_id == "pentatonic_per_chord":
        fam = {lv: ("pentatonic_cell",) for lv in LEVELS}
        c = SpanConstraints(pitch_space="pentatonic", no_chromatic=True, connector="step")
    elif mission_id == "syncopated_phrase":
        fam = {lv: ("rhythmic_motif", "scalar_fragment") for lv in LEVELS}
        c = SpanConstraints(rhythm_focus="Syncopation", require_syncopation=True)
    else:
        raise KeyError(mission_id)
    if mission_id in _STRUCTURAL_ENDING:
        from dataclasses import replace

        c = replace(c, free_ending=False)  # the Mission's resolution wins over an extension ending
    return fam.get(lvl, ()), c


# Missions whose point is a structural landing (root / 3rd / guide tone / chord tone / common
# collection): the phrase never ends on a 9th / 6th / 11th there.
_STRUCTURAL_ENDING = {
    "guide_tone_voice_leading", "common_tone_voice_leading", "ii_v_i_resolution", "resolve_to_third",
    "dominant_tension_resolution", "chord_tones_each_chord", "one_common_scale", "pentatonic_per_chord",
    "rhythm_over_notes",
}


# --------------------------------------------------------------------------- the line, read per chord


@dataclass
class MissionCheck:
    name: str
    passed: bool
    where: str
    text: str


@dataclass
class MissionReport:
    checks: list[MissionCheck] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def add(self, name: str, passed: bool, where: str, text: str) -> None:
        self.checks.append(MissionCheck(name, bool(passed), where, text))

    def problems(self) -> list[str]:
        return [f"{c.where}: {c.name}" for c in self.checks if not c.passed]

    def evidence(self) -> list[dict[str, str]]:
        return [{"where": c.where, "text": c.text, "check": c.name} for c in self.checks if c.passed]


class _Line:
    """A generated span line, addressable by chord slot and chord change.

    ``key`` / ``chords``: read a projected (written-key) line in its own chart spelling.
    """

    def __init__(self, motif: dict[str, Any], span: Any, *, key: str | None = None, chords: Sequence[str] | None = None) -> None:
        from melodic_rhythm_engine import events_from_json
        from span_motif_explain import pretty

        self.m = motif
        self.span = span
        self.midis = [int(x) for x in motif["midi"]]
        self.names = [pretty(n) for n in motif["notes"]]
        self.cis = [int(c) for c in motif["note_chord_index"]]
        self.timeline = list(motif["chord_timeline"])
        self.events = [e for e in events_from_json(motif.get("rhythm_events") or []) if not e.rest]
        from melodic_pattern_engine import build_context

        shown = list(chords) if chords else [t["chord"] for t in self.timeline]
        self.key = key or span.key_center
        self.ctxs = [build_context(self.key, shown[i]) for i in range(len(self.timeline))]
        self.chords = [pretty(c) for c in shown]

    def slot(self, i: int) -> range:
        t = self.timeline[i]
        return range(int(t["first_note"]), int(t["last_note"]) + 1)

    @property
    def changes(self) -> list[int]:
        return list(range(1, len(self.timeline)))

    def target(self, i: int) -> int:
        return int(self.timeline[i]["first_note"])

    def role(self, k: int) -> str:
        from span_motif_explain import degree_label

        return degree_label(self.ctxs[self.cis[k]], self.midis[k] % 12)

    def is_chord_tone(self, k: int) -> bool:
        return self.midis[k] % 12 in self.ctxs[self.cis[k]].chord_pcs

    def in_scale(self, k: int) -> bool:
        return self.midis[k] % 12 in self.ctxs[self.cis[k]].scale_pcs

    def onset_ok(self, i: int) -> bool:
        k = self.target(i)
        return k < len(self.events) and self.events[k].onset == Fraction(self.timeline[i]["start"])

    def note(self, k: int) -> str:
        return f"{self.names[k]} ({self.role(k)} of {self.chords[self.cis[k]]})"

    def change_label(self, i: int) -> str:
        return f"{self.chords[i - 1]} → {self.chords[i]}"


# --------------------------------------------------------------------------- validators


def _approach_ok(line: _Line, i: int, *, level: str) -> tuple[bool, str]:
    t = line.target(i)
    b = t - 1
    d = line.midis[t] - line.midis[b]
    if level == "Beginner":
        ok = 1 <= abs(d) <= 2 and line.in_scale(b)
        return ok, f"{line.names[b]} steps {'up' if d > 0 else 'down'} into {line.note(t)}"
    if level == "Intermediate":
        ok = abs(d) == 1
        kind = "chromatic" if not line.in_scale(b) else "half-step"
        return ok, f"{line.names[b]} → {line.note(t)}: {kind} approach from {'below' if d > 0 else 'above'}"
    a = b - 1
    if a < 0 or line.cis[a] != line.cis[b]:
        return False, "no room for a double approach"
    da, db = line.midis[t] - line.midis[a], line.midis[t] - line.midis[b]
    same_side = (da > 0) == (db > 0) and abs(db) == 1 and 1 <= abs(da) <= 2
    straddle = da * db < 0 and abs(da) <= 2 and abs(db) <= 2
    kind = "double chromatic approach" if same_side else "enclosure"
    return same_side or straddle, f"{line.names[a]}–{line.names[b]} → {line.note(t)}: {kind}"


def _enclosure_ok(line: _Line, i: int, *, level: str) -> tuple[bool, str]:
    t = line.target(i)
    a, b = t - 2, t - 1
    if a < 0 or line.cis[a] != line.cis[b]:
        return False, "no room for an enclosure"
    da, db = line.midis[a] - line.midis[t], line.midis[b] - line.midis[t]
    ok = da * db < 0 and 1 <= abs(da) <= 2 and 1 <= abs(db) <= 2
    if level == "Beginner":
        tgt_scale = line.ctxs[line.cis[t]].scale_pcs
        ok = ok and all(line.midis[x] % 12 in line.ctxs[line.cis[x]].scale_pcs or line.midis[x] % 12 in tgt_scale for x in (a, b))
    else:
        ok = ok and 1 in (abs(da), abs(db))
    return ok, f"{line.names[a]} and {line.names[b]} enclose {line.note(t)}"


def validate_mission_line(
    mission_id: str, motif: dict[str, Any], span: Any, *, level: str, style: str = "default",
    key: str | None = None, chords: Sequence[str] | None = None,
) -> MissionReport:
    """Check that ``motif`` actually demonstrates ``mission_id`` — per chord and per change.

    ``key`` / ``chords`` validate (and word the evidence for) a written-key projection.
    """
    from span_rhythm_grammar import rhythm_coherence

    lvl = _level(level)
    line = _Line(motif, span, key=key, chords=chords)
    rep = MissionReport()
    n_slots = len(line.timeline)

    if mission_id in ("guide_tone_voice_leading", "resolve_to_third", "target_each_change"):
        allowed = {"guide_tone_voice_leading": {"3rd", "7th"}, "resolve_to_third": {"3rd"}}.get(
            mission_id, {"root", "3rd", "5th"} if lvl == "Beginner" else {"3rd", "7th"}
        )
        for i in range(n_slots):
            t = line.target(i)
            ok = line.role(t) in allowed and line.is_chord_tone(t) and line.onset_ok(i)
            rep.add("lands on " + "/".join(sorted(allowed)), ok, line.chords[i],
                    f"{line.note(t)} lands on beat 1 of {line.chords[i]}")
    if mission_id == "guide_tone_voice_leading":
        seven_three = 0
        for i in line.changes:
            prev = [k for k in line.slot(i - 1) if line.role(k) in ("3rd", "7th") and line.is_chord_tone(k)]
            t = line.target(i)
            if not prev:
                rep.add("guide tone before the change", False, line.change_label(i), "")
                continue
            g = prev[-1]
            d = abs(line.midis[g] - line.midis[t])
            is73 = line.role(g) == "7th" and line.role(t) == "3rd" and 1 <= d <= 2
            seven_three += is73
            how = "7th resolves to 3rd" if is73 else "held common tone" if d == 0 else f"moves by {'a half' if d == 1 else 'a whole'} step" if d <= 2 else f"leaps {d} semitones"
            rep.add("guide tones voice-led", d <= 2, line.change_label(i), f"{line.note(g)} → {line.note(t)} — {how}")
        if _fifth_motions(span):
            rep.add("7th → 3rd resolution", seven_three >= 1, "span", f"{seven_three} guide-tone resolution(s)")
    elif mission_id == "target_each_change":
        for i in line.changes if lvl != "Beginner" else ():
            t = line.target(i)
            d = abs(line.midis[t] - line.midis[t - 1])
            rep.add("approached by step", d <= 2, line.change_label(i),
                    f"{line.names[t - 1]} leads into {line.note(t)}")
    elif mission_id == "resolve_to_third":
        for i in line.changes:
            t = line.target(i)
            d = abs(line.midis[t] - line.midis[t - 1])
            rep.add("arrives by step", 1 <= d <= 2, line.change_label(i), f"{line.names[t - 1]} steps to {line.note(t)}")
    elif mission_id == "motif_through_changes":
        coh = rhythm_coherence(line.events, motif.get("meter") or "4/4", style=style)
        restated = motif.get("development_strategy") == "vamp_restatement"
        rep.add("rhythmic cell repeats", coh.get("cell_identity", 0) >= 0.6 or restated, "rhythm",
                f"the bar-1 rhythm returns in {round(100 * coh.get('cell_identity', 0))}% of the active bars")
        shapes = []
        for i in range(n_slots):
            ks = list(line.slot(i))[:3]
            shapes.append(tuple((line.midis[b] > line.midis[a]) - (line.midis[b] < line.midis[a]) for a, b in zip(ks, ks[1:])))
        same = sum(1 for s in shapes[1:] if s == shapes[0])
        mirror = sum(1 for s in shapes[1:] if s == tuple(-x for x in shapes[0]) and any(shapes[0]))
        how = (f"returns on {same} later chord(s)" if same else f"returns inverted (call and response) on {mirror} later chord(s)")
        rep.add("shape repeats", same + mirror >= 1 or restated, "contour",
                f"the opening shape ({_shape_word(shapes[0])}) {how}")
        ident = motif.get("motif_identity")
        if isinstance(ident, dict):
            rep.add("seed audible in the development", ident.get("total", 0) >= 0.8, "development",
                    f"seed identity {round(100 * ident.get('total', 0))}%")
    elif mission_id == "common_tone_voice_leading":
        for i in line.changes:
            t = line.target(i)
            prev_pcs = set(line.ctxs[i - 1].chord_pcs)
            d = abs(line.midis[t] - line.midis[t - 1])
            common = line.midis[t] % 12 in prev_pcs
            rep.add("nearest voice leading", d <= 2, line.change_label(i),
                    f"{line.note(t)} is {'common to both chords' if common else 'the nearest chord tone'} — {line.names[t - 1]} moves {d} semitone(s)")
        steps = [abs(a - b) for a, b in zip(line.midis, line.midis[1:])]
        rep.add("economical motion", sum(steps) / max(1, len(steps)) <= 3.0, "line",
                f"average move {round(sum(steps) / max(1, len(steps)), 1)} semitones")
    elif mission_id == "approach_next_chord":
        for i in line.changes:
            ok, text = _approach_ok(line, i, level=lvl)
            rep.add("approach into the next chord", ok and line.is_chord_tone(line.target(i)), line.change_label(i), text)
    elif mission_id == "enclose_next_target":
        for i in line.changes:
            ok, text = _enclosure_ok(line, i, level=lvl)
            rep.add("enclosure resolves at the change", ok and line.is_chord_tone(line.target(i)), line.change_label(i), text)
    elif mission_id == "ii_v_i_resolution":
        v, one = n_slots - 2, n_slots - 1
        vk = [k for k in line.slot(v) if line.role(k) in ("3rd", "7th") and line.is_chord_tone(k)]
        shown = list(dict.fromkeys(line.note(k) for k in vk))[:2]
        rep.add("V states its tension", bool(vk), line.chords[v],
                f"{' and '.join(shown)} {'define' if len(shown) > 1 else 'defines'} the dominant" if vk else "")
        t = line.target(one)
        d = abs(line.midis[t] - line.midis[t - 1])
        rep.add("V resolves by step", d <= 2, line.change_label(one), f"{line.names[t - 1]} resolves to {line.note(t)}")
        last = len(line.midis) - 1
        rep.add("I is a stable landing", line.role(last) in ("root", "3rd") and line.events[last].duration >= 1,
                line.chords[one], f"ends on {line.note(last)}")
        if lvl == "Advanced":
            outside = [k for k in line.slot(v) if not line.in_scale(k)]
            rep.add("dominant colour", bool(outside), line.chords[v],
                    f"{', '.join(dict.fromkeys(line.names[k] for k in outside))} color the dominant before it resolves" if outside else "")
    elif mission_id == "one_common_scale":
        coll = common_collection(span, key=line.key)
        if coll is None:
            rep.add("common scale exists", False, "span", "")
        else:
            name, pcs, notes = coll
            outside = [k for k in range(len(line.midis)) if line.midis[k] % 12 not in pcs]
            rep.add("every note in the named scale", not outside, "span",
                    f"every note is from {name}: {'–'.join(notes)}" if not outside else
                    f"outside notes: {', '.join(line.names[k] for k in outside)}")
            rep.add("each chord still lands on its own chord tone",
                    all(line.is_chord_tone(line.target(i)) for i in range(n_slots)), "changes",
                    "; ".join(f"{line.chords[i]}: {line.note(line.target(i))}" for i in range(n_slots)))
    elif mission_id == "dominant_tension_resolution":
        doms = [i for i in _dominant_resolutions(span) if i < n_slots - 1]
        for i in doms:
            ks = list(line.slot(i))
            t = line.target(i + 1)
            if lvl == "Advanced":
                outside = [k for k in ks if not line.in_scale(k)]
                rep.add("dominant tension", bool(outside), line.chords[i],
                        f"{', '.join(dict.fromkeys(line.names[k] for k in outside))} color {line.chords[i]}" if outside else "")
            else:
                gt = [k for k in ks if line.role(k) in ("3rd", "7th") and line.is_chord_tone(k)]
                chrom = not line.in_scale(t - 1) or abs(line.midis[t] - line.midis[t - 1]) == 1
                shown = list(dict.fromkeys(line.note(k) for k in gt))[:2]
                rep.add("dominant tension", bool(gt) and chrom, line.chords[i],
                        f"{' and '.join(shown)}, then {line.names[t - 1]} pulls into the resolution")
            d = abs(line.midis[t] - line.midis[t - 1])
            rep.add("tension resolves", d <= 2 and line.is_chord_tone(t), line.change_label(i + 1),
                    f"{line.names[t - 1]} resolves to {line.note(t)}")
        if not doms:
            rep.add("dominant resolution exists", False, "span", "")
    elif mission_id == "chord_tones_each_chord":
        bad = [k for k in range(len(line.midis)) if not line.is_chord_tone(k)]
        rep.add("only chord tones of the sounding chord", not bad, "line",
                "every note belongs to the chord sounding at that moment" if not bad else
                f"non-chord tones: {', '.join(line.names[k] for k in bad)}")
        for i in line.changes:
            new_pcs = set(line.ctxs[i].chord_pcs) - set(line.ctxs[i - 1].chord_pcs)
            marks = [k for k in line.slot(i) if line.midis[k] % 12 in new_pcs]
            rep.add("the change is audible", bool(marks) or not new_pcs, line.change_label(i),
                    f"{line.note(marks[0])} is a note only {line.chords[i]} has" if marks else "the chords share every note")
    elif mission_id in ("rhythm_over_notes", "syncopated_phrase"):
        coh = rhythm_coherence(line.events, motif.get("meter") or "4/4", style=style)
        rep.add("one rhythmic idea", coh.get("cell_identity", 0) >= 0.6, "rhythm",
                f"rhythmic cell {motif.get('rhythm', '').split('|')[0].strip()} repeats")
        targets_ok = all(line.is_chord_tone(line.target(i)) for i in range(n_slots))
        rep.add("right notes at each change", targets_ok, "changes",
                "; ".join(f"{line.chords[i]}: {line.note(line.target(i))}" for i in range(n_slots)))
        if mission_id == "rhythm_over_notes":
            cap = 3 if _level(level) == "Beginner" else 4
            per_chord = []
            for i in range(n_slots):
                names = list(dict.fromkeys(line.names[k] for k in line.slot(i)))
                pcs = {line.midis[k] % 12 for k in line.slot(i)}
                per_chord.append((line.chords[i], names, len(pcs)))
            rep.add("simple pitches", all(n <= cap for _c, _names, n in per_chord), "pitches",
                    "; ".join(f"{c}: only {', '.join(names)}" for c, names, _n in per_chord)
                    + " — the rhythm carries the idea")
        if mission_id == "syncopated_phrase":
            sync = [k for k, e in enumerate(line.events) if _crosses(e)]
            ratio = len(sync) / max(1, len(line.events))
            cap = 1.0 if style in JAZZY or style == "funk" else 0.4
            rep.add("syncopation", bool(sync) and ratio <= cap, "rhythm",
                    f"{len(sync)} syncopated entries, e.g. {line.names[sync[0]]} on an off-beat over {line.chords[line.cis[sync[0]]]}" if sync else "")
    elif mission_id == "scalar_runs":
        steps = [abs(a - b) for a, b in zip(line.midis, line.midis[1:])]
        share = sum(1 for s in steps if 1 <= s <= 2) / max(1, len(steps))
        rep.add("stepwise", share >= 0.75, "line", f"{round(100 * share)}% of moves are scale steps")
        rep.add("chord tone at each change", all(line.is_chord_tone(line.target(i)) for i in range(n_slots)), "changes",
                "; ".join(f"{line.chords[i]}: {line.note(line.target(i))}" for i in range(n_slots)))
    elif mission_id == "bebop_line":
        short = sum(1 for e in line.events if e.duration <= Fraction(1, 2)) / max(1, len(line.events))
        on_beat = [k for k, e in enumerate(line.events) if e.onset % 1 == 0]
        ct = sum(1 for k in on_beat if line.is_chord_tone(k)) / max(1, len(on_beat))
        chrom = [k for k in range(len(line.midis)) if not line.in_scale(k)]
        need = 0.3 if motif.get("variant") == "easier" else 0.5  # Easier is sparser by design
        rep.add("eighth-note flow", short >= need, "rhythm", f"{round(100 * short)}% eighths or shorter")
        rep.add("chord tones on the beat", ct >= 0.5, "beats", f"{round(100 * ct)}% of on-beat notes are chord tones")
        rep.add("chromatic approach", bool(chrom), "line",
                f"chromatic notes: {', '.join(line.names[k] for k in chrom[:3])}" if chrom else "")
    elif mission_id == "pentatonic_per_chord":
        from span_motif_engine import _pentatonic
        from span_motif_explain import _pentatonic_info

        for i in range(n_slots):
            ks = [k for k in line.slot(i) if not (k + 1 < len(line.midis) and line.cis[k + 1] != i)]
            pent = set(_pentatonic(line.ctxs[i]))
            info = _pentatonic_info(line.ctxs[i], line.timeline[i]["chord"])
            label = f"{info['name']}: {'–'.join(info['notes'])}" if info else "its pentatonic"
            rep.add("notes from the chord's pentatonic", all(line.midis[k] % 12 in pent for k in ks), line.chords[i],
                    f"{line.chords[i]} uses {label}")
    else:
        raise KeyError(mission_id)
    return rep


def _crosses(e: Any) -> bool:
    return e.onset % 1 != 0 and e.onset + e.duration > e.onset - e.onset % 1 + 1


def _shape_word(shape: Sequence[int]) -> str:
    words = {1: "up", -1: "down", 0: "same"}
    return "–".join(words[s] for s in shape) or "one note"


# --------------------------------------------------------------------------- generation


def _seed(*parts: Any) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


def materially_different(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """A New Idea must change the idea, not one note."""
    if a.get("strategy_family") != b.get("strategy_family"):
        return True
    ra, rb = (a.get("rhythm_plan") or {}).get("cell"), (b.get("rhythm_plan") or {}).get("cell")
    if ra and rb and ra != rb:
        return True
    ma, mb = list(a.get("midi") or []), list(b.get("midi") or [])
    diff = sum(1 for x, y in zip(ma, mb) if x != y) + abs(len(ma) - len(mb))
    return diff >= 0.4 * max(len(ma), len(mb), 1)


def generate_mission_span_example(
    mission: SpanMission | str,
    span: Any,
    *,
    level: str,
    variant: str = "normal",
    instrument: str = "",
    seed: int | None = None,
    idea: int = 0,
    style: str = "default",
    focus: str = "",
    avoid: Sequence[dict[str, Any]] = (),
    attempts: int = 40,
) -> dict[str, Any]:
    """One validated Mission example over ``span`` (see module docstring).

    ``variant``: easier / normal / harder inside the player's Level (never outside it).
    ``idea``: New Idea index — rotates strategy family and seed. ``avoid``: earlier examples
    a New Idea must differ from materially.
    """
    from span_motif_engine import develop_span_motif, generate_span_motif

    m = MISSIONS_BY_ID[mission] if isinstance(mission, str) else mission
    lvl = _level(level)
    diff = _difficulty(variant)
    reason = unavailable_reason(m, span, level=lvl, style=style)
    if reason:
        raise ValueError(f"{m.label} is not available on {' → '.join(span.chords)}: {reason}")
    families, constraints = mission_plan(m.id, level=lvl, variant=diff, span=span, style=style)
    if style not in JAZZY and m.id not in _CHROMATIC_INTENT:
        # Pop / rock / folk / ballad: a Mission that is not about chromaticism stays diatonic.
        from dataclasses import replace

        constraints = replace(
            constraints,
            connector=constraints.connector or "step",
            color="forbid" if constraints.color != "require" else constraints.color,
            no_chromatic=True,
        )
    if diff == "easier" and m.id not in ("bebop_line", "syncopated_phrase"):  # there the rhythm is the Mission
        from dataclasses import replace

        constraints = replace(constraints, plain_rhythm=True)
    if diff == "harder" and m.id == "rhythm_over_notes" and style not in ("ballad", "jazz_ballad", "folk"):
        from dataclasses import replace

        # The rhythm Mission gets harder in its rhythm: a syncopated cell (style-restrained).
        constraints = replace(constraints, require_syncopation=True)
    tier = {"easier": "easier", "normal": "normal", "harder": "harder"}[diff]
    base = _seed(m.id, span.span_id, lvl, diff, idea) if seed is None else int(seed)
    # Mission intent wins; a compatible Practice Focus still shapes the realization.
    focus_eff = focus if not constraints.rhythm_focus else constraints.rhythm_focus
    # Easier is never busier than Normal for the same Mission / span / idea.
    max_notes = None
    if diff == "easier":
        ref = generate_mission_span_example(
            m, span, level=lvl, variant="normal", instrument=instrument, idea=idea, style=style, focus=focus,
            attempts=attempts,
        )
        max_notes = len(ref["motif"]["midi"])
    best: tuple[int, dict[str, Any], MissionReport] | None = None
    for k in range(max(1, attempts)):
        family = families[(idea + k) % len(families)] if families else "auto"
        s = base + 7919 * k
        motif = generate_span_motif(
            span, level=lvl, variant=tier, instrument=instrument, seed=s, vocabulary=family, focus=focus_eff,
            style=style, constraints=constraints,
        )
        if diff == "harder":
            # (For the rhythm Mission the Build splits notes into repeated notes — a denser
            # rhythm on the same tiny pitch cell; see ``_try_ornament``.)
            motif = develop_span_motif(span, motif, length="standard")
        report = validate_mission_line(m.id, motif, span, level=lvl, style=style)
        fresh = all(materially_different(motif, prior.get("motif", prior)) for prior in avoid)
        lighter = max_notes is None or len(motif["midi"]) <= max_notes
        score = len(report.problems()) + (0 if fresh else 5) + (0 if lighter else 3)
        if best is None or score < best[0]:
            best = (score, motif, report)
        if report.valid and fresh and lighter:
            break
    assert best is not None
    _score, motif, report = best
    return _example_payload(m, span, motif, report, level=lvl, difficulty=diff, idea=idea, style=style, focus=focus)


def _example_payload(
    m: SpanMission, span: Any, motif: dict[str, Any], report: MissionReport, *, level: str, difficulty: str,
    idea: int, style: str, focus: str,
) -> dict[str, Any]:
    from melodic_rhythm_engine import parse_meter

    raw = f"{m.id}|{span.span_id}|{level}|{difficulty}|{idea}|{motif.get('midi')}|{motif.get('rhythm_events')}"
    example_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    meter = str(motif.get("meter") or "4/4")
    bars = int(sum(int(t["bars"]) for t in motif.get("chord_timeline") or []))
    coll = common_collection(span) if m.id == "one_common_scale" else None
    return {
        "kind": "span_mission",
        "mission_id": m.id,
        "mission_label": m.label,
        "mission_brief": m.brief,
        "span_id": span.span_id,
        "span_chords": list(span.chords),
        "span_relationship": span.relationship,
        "level": level,
        "difficulty": difficulty,
        "idea": int(idea),
        "style": style,
        "focus": focus,
        "valid": report.valid,
        "problems": report.problems(),
        "evidence": report.evidence(),
        "common_scale": {"name": coll[0], "notes": coll[2]} if coll else None,
        "motif": motif,
        # MC4 seam: everything a span-aware Mission Backing needs, no new format.
        "handoff": {
            "version": 1,
            "mission_id": m.id,
            "span_id": span.span_id,
            "span_chords": list(span.chords),
            "chord_timeline": list(motif.get("chord_timeline") or []),
            "example_id": example_id,
            "note_chord_index": list(motif.get("note_chord_index") or []),
            "meter": meter,
            "loop_bars": bars,
            "loop_beats": str(parse_meter(meter).bar * bars),
            "practice_key": "",  # filled by the caller from the live Practice Key
        },
    }


__all__ = [
    "DIFFICULTIES",
    "MISSIONS_BY_ID",
    "MissionReport",
    "SINGLE_CHORD_CLASSIFICATION",
    "SPAN_MISSIONS",
    "SpanMission",
    "available_span_missions",
    "common_collection",
    "generate_mission_span_example",
    "materially_different",
    "mission_plan",
    "unavailable_reason",
    "validate_mission_line",
]
