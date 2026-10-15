"""Song-Aware Coaching (S2) — the guided plan for one selection of one song.

:func:`build_coaching_plan` turns an S1 :class:`~song_coach_scope.CoachScope` into a
:class:`CoachingPlan`: a few short challenges that grow **one** musical idea through the
selection's real chord changes, ending in a bar-by-bar phrase roadmap.

Design rules:

- **Only the chart.** Every note named comes from :mod:`song_coach_harmony` facts about the
  charted chords. There is no melody, recording or performance input, so nothing can be
  claimed about them; :data:`FORBIDDEN_CLAIMS` is enforced by :func:`validate_plan`.
- **Basis on every line.** ``harmony`` = a checkable fact about these chords (re-verified by
  :func:`validate_plan`); ``style`` = a suggestion from the song's style bucket (metadata,
  never the title), worded as an option; ``practice`` = technique.
- **One idea, developed.** The idea from the first challenge is carried through every
  change: the same rhythm cell, re-targeted by the smoothest voice leading
  (``span_motif_engine.voice_leading_cost``) — never a new phrase per chord.
- **Honest endings.** The roadmap ends the way the chords end: a cadence only when the chart
  has one; open, looping and leading-on endings stay open.
- **Projection-ready text.** Lines are templates whose note / chord slots hold concert facts;
  :meth:`Line.render` takes the UI's Written-Key / Shape projection.
- **Deterministic.** Same scope, level, focus, style and instrument → same plan and
  ``plan_id``; the only randomness (the rhythm cell) is seeded from the plan id.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence

from song_coach_harmony import (
    CHORD_TONE,
    CLASH,
    ENDING_AUTHENTIC,
    ENDING_DECEPTIVE,
    ENDING_HALF,
    ENDING_HOME,
    ENDING_HOME_COLOUR,
    ENDING_LEADS_ON,
    ENDING_LOOPS,
    ENDING_MID,
    ENDING_PLAGAL,
    EXTENSION,
    FAMILY_DOMINANT,
    FAMILY_SUS,
    HOLDABLE,
    PASSING,
    TENSION,
    Change,
    ChordFacts,
    SectionProfile,
    Tone,
    anchor_line,
    change_facts,
    check_collection,
    chord_facts,
    chord_palette,
    classify_ending,
    key_facts,
    key_pentatonic,
    key_scale,
    note_use,
    outside_tones,
    section_profile,
    signed_motion,
)

ENGINE_VERSION = "s2.1"

BASIS_HARMONY = "harmony"
BASIS_STYLE = "style"
BASIS_PRACTICE = "practice"

FOCUS_MELODIC = "melodic_phrasing"
FOCUS_RHYTHMIC = "rhythmic_development"
FOCUS_CHORD_TONE = "chord_tone_connections"
FOCUS_MOTIF = "motif_development"
FOCUSES = (FOCUS_MELODIC, FOCUS_RHYTHMIC, FOCUS_CHORD_TONE, FOCUS_MOTIF)
FOCUS_LABELS = {
    FOCUS_MELODIC: "Melodic Phrasing",
    FOCUS_RHYTHMIC: "Rhythmic Development",
    FOCUS_CHORD_TONE: "Chord-Tone Connections",
    FOCUS_MOTIF: "Motif Development",
}
LEVELS = ("Beginner", "Intermediate", "Advanced")

KIND_IDEA = "idea"
KIND_RHYTHM = "rhythm"
KIND_CONNECT = "connect"
KIND_EXPAND = "expand"
KIND_MOMENT = "moment"
KIND_ROADMAP = "roadmap"

FORBIDDEN_CLAIMS = re.compile(
    r"\bmelody\b|\bmelodies\b|\boriginal (solo|line|part|recording)\b|\bthe recording\b|\bon the record\b|"
    r"\bas recorded\b|\bthe singer\b|\bvocal line\b|\bthe (guitar|sax|piano) solo\b|\bfamous (lick|riff|solo)\b|"
    r"\bthe artist plays\b|\bin the song,? (he|she|they) (play|sing)",
    re.IGNORECASE,
)
BEGINNER_JARGON = re.compile(
    r"guide[- ]tone|secondary dominant|tritone|enclosure|displac|chromatic|mixolydian|dorian|lydian|"
    r"ii–V|V–I|cadence|tension|♭9|♯9|♯11|♭13|substitut",
    re.IGNORECASE,
)

_LEVEL_ROLES = {
    "Beginner": ("R", "3", "5"),
    "Intermediate": ("3", "7", "5"),
    "Advanced": ("3", "7", "5", "9th", "13th", "6th", "11th"),
}
_IDEA_NOTES = {"Beginner": 3, "Intermediate": 4, "Advanced": 5}
_FOCUS_PREF = {FOCUS_MELODIC: "lyrical", FOCUS_RHYTHMIC: "rhythm", FOCUS_CHORD_TONE: "chord_tones", FOCUS_MOTIF: "motif"}
_JAZZY = frozenset({"jazz", "jazz_ballad", "bossa", "blues"})
_LYRICAL = frozenset({"ballad", "jazz_ballad", "folk"})


# --------------------------------------------------------------------------- records


@dataclass(frozen=True)
class NoteRef:
    pc: int
    name: str  # concert spelling
    role: str
    chord: str  # concert chord symbol the note is judged against
    category: str


@dataclass(frozen=True)
class Claim:
    """A checkable harmonic statement (see :func:`validate_plan`)."""

    kind: str
    chord: str = ""
    pc: int = -1
    role: str = ""
    other_chord: str = ""
    other_pc: int = -1
    value: str = ""
    number: int = 0
    pcs: tuple[int, ...] = ()
    chords: tuple[str, ...] = ()


@dataclass(frozen=True)
class Line:
    basis: str
    template: str
    notes: tuple[NoteRef, ...] = ()
    chords: tuple[str, ...] = ()
    claims: tuple[Claim, ...] = ()

    def render(
        self,
        note: Callable[[NoteRef], str] | None = None,
        chord: Callable[[str], str] | None = None,
    ) -> str:
        """Fill the slots: concert names by default; the UI passes its projection."""
        nf = note or (lambda n: n.name)
        cf = chord or (lambda c: c)
        slots = {f"n{i}": nf(n) for i, n in enumerate(self.notes)}
        slots.update({f"c{i}": cf(c) for i, c in enumerate(self.chords)})
        return self.template.format(**slots)


@dataclass(frozen=True)
class Rhythm:
    figures: tuple[str, ...]
    display: str
    kind: str


@dataclass(frozen=True)
class Material:
    name: str
    pcs: tuple[int, ...]
    names: tuple[str, ...]
    verdict: str
    lines: tuple[Line, ...]


@dataclass(frozen=True)
class Challenge:
    kind: str
    title: str
    goal: Line
    steps: tuple[Line, ...]
    loop_start: int
    loop_end: int
    chords: tuple[str, ...]
    targets: tuple[NoteRef, ...] = ()
    checklist: tuple[str, ...] = ()
    example: dict[str, Any] = field(default_factory=dict)

    @property
    def lines(self) -> tuple[Line, ...]:
        return (self.goal,) + self.steps


@dataclass(frozen=True)
class RoadmapRow:
    role: str
    start_bar: int
    end_bar: int
    chords: tuple[str, ...]
    anchors: tuple[NoteRef, ...]
    line: Line


@dataclass(frozen=True)
class CoachingPlan:
    plan_id: str
    engine_version: str
    scope_id: str
    context_fingerprint: str
    section_label: str
    range_label: str
    start_bar: int
    end_bar: int
    key: str
    meter: str
    level: str
    focus: str
    style: str
    instrument: str
    chart_confidence: str
    chart_label: str
    chart_note: str
    ending: str
    summary: tuple[Line, ...]
    material: Material | None
    rhythm: Rhythm | None
    anchors: tuple[NoteRef, ...]
    challenges: tuple[Challenge, ...]
    roadmap: tuple[RoadmapRow, ...]
    reading_notes: tuple[str, ...] = ()

    @property
    def focus_label(self) -> str:
        return FOCUS_LABELS.get(self.focus, self.focus)

    def all_lines(self) -> list[Line]:
        out = list(self.summary)
        if self.material is not None:
            out.extend(self.material.lines)
        for ch in self.challenges:
            out.extend(ch.lines)
        out.extend(row.line for row in self.roadmap)
        return out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoachingPlan":
        return _plan_from_dict(data)


# --------------------------------------------------------------------------- helpers


def normalize_level(level: str) -> str:
    lv = str(level or "").strip().title()
    return lv if lv in LEVELS else "Intermediate"


def normalize_focus(focus: str) -> str:
    f = str(focus or "").strip().lower().replace("-", "_").replace(" ", "_")
    for fid, label in FOCUS_LABELS.items():
        if f in (fid, label.lower().replace("-", "_").replace(" ", "_")):
            return fid
    return FOCUS_MOTIF


def default_coaching_focus(global_focus: str) -> str:
    """The coaching focus that best matches the global Practice Focus (never written back)."""
    try:
        from span_motif_engine import focus_preference

        pref = focus_preference(global_focus)
    except ImportError:
        pref = "neutral"
    return {
        "lyrical": FOCUS_MELODIC,
        "pentatonic": FOCUS_MELODIC,
        "rhythm": FOCUS_RHYTHMIC,
        "chord_tones": FOCUS_CHORD_TONE,
        "guide_tones": FOCUS_CHORD_TONE,
        "scales": FOCUS_CHORD_TONE,
        "bebop": FOCUS_CHORD_TONE,
        "motif": FOCUS_MOTIF,
    }.get(pref, FOCUS_MELODIC)


def instrument_family(instrument: str) -> str:
    low = str(instrument or "").lower()
    if any(w in low for w in ("sax", "flute", "trumpet", "clarinet", "trombone", "horn")):
        return "wind"
    if "voice" in low or "vocal" in low:
        return "voice"
    if "bass" in low:
        return "bass"
    if "guitar" in low or "ukulele" in low:
        return "guitar"
    if "piano" in low or "keys" in low:
        return "piano"
    return "other"


def plan_id_for(scope_id: str, level: str, focus: str, style: str, instrument: str) -> str:
    blob = json.dumps(
        [ENGINE_VERSION, scope_id, level, focus, style, instrument_family(instrument)], separators=(",", ":")
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _tref(facts: ChordFacts, tone: Tone) -> NoteRef:
    return NoteRef(tone.pc, tone.name, tone.role, facts.symbol, CHORD_TONE if tone.kind == CHORD_TONE else EXTENSION)


def _uref(facts: ChordFacts, pc: int, key: str, style: str) -> NoteRef:
    u = note_use(facts, pc, key=key, style=style)
    return NoteRef(u.pc, u.name, u.role, facts.symbol, u.category)


def _tone_claim(ref: NoteRef) -> Claim:
    return Claim("note", chord=ref.chord, pc=ref.pc, role=ref.role, value=ref.category)


def L(basis: str, template: str, notes: Sequence[NoteRef] = (), chords: Sequence[str] = (), claims: Sequence[Claim] = ()) -> Line:
    """A line; every note slot automatically carries its own checkable note claim."""
    all_claims = tuple(claims) + tuple(_tone_claim(n) for n in notes)
    return Line(basis, template, tuple(notes), tuple(chords), all_claims)


def _motion_words(semitones: int, level: str) -> str:
    d = abs(semitones)
    if d == 0:
        return "stay on the same note"
    way = "up" if semitones > 0 else "down"
    if d == 1:
        return f"{way} a half step"
    if d == 2:
        return f"{way} a whole step"
    if d <= 4:
        return f"{way} a small leap"
    return f"{way} a leap"


def _beat_words(beat_in_bar: float) -> str:
    """Musician wording for a position inside the bar (0-based beats)."""
    whole = int(beat_in_bar)
    if abs(beat_in_bar - whole) < 1e-9:
        return f"beat {whole + 1}"
    if abs(beat_in_bar - whole - 0.5) < 1e-9:
        return f"the 'and' of beat {whole + 1}"
    return f"beat {beat_in_bar + 1:g}"


def _when(bar: int, beat_in_bar: float) -> str:
    return f"at bar {bar}" if beat_in_bar == 0 else f"in bar {bar}, on {_beat_words(beat_in_bar)}"


def _join(names: Sequence[str]) -> str:
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _slots(prefix: str, start: int, count: int) -> list[str]:
    return ["{" + f"{prefix}{start + i}" + "}" for i in range(count)]


def _level_tones(facts: ChordFacts, level: str) -> list[Tone]:
    """Notes a player at ``level`` builds with (landing targets are narrower: see anchors)."""
    stable = list(facts.stable)
    if level == "Beginner":
        stable = [t for t in facts.stable if t.engine_role in ("R", "3", "5") or t.role in ("2nd", "4th")]
    tones = stable or list(facts.stable)
    if level == "Advanced":
        tones += list(facts.extensions)
    return tones


def _bar_range(start: int, end: int, lo: int, hi: int) -> tuple[int, int]:
    return max(lo, start), min(hi, end)


# --------------------------------------------------------------------------- the build


@dataclass
class _Build:
    ctx: Any
    scope: Any
    level: str
    focus: str
    style: str
    instrument: str
    key: str
    profile: SectionProfile
    events: list[Any]
    facts: list[ChordFacts]
    changes: list[Change]
    anchors: list[Tone]
    rhythm: Rhythm | None
    variation: Rhythm | None
    material: Material | None
    following: ChordFacts | None


def _following_symbol(ctx: Any, scope: Any) -> str:
    """The chord right after the selection: the next bar in the section, else the next section."""
    from song_coach_scope import _bar_parts

    def first_chord(token: str) -> str:
        for sym, _beats, _push in _bar_parts(token, float(scope.beats_per_bar or 4.0)):
            if sym:
                return sym
        return ""

    names = [n for n, _ in ctx.sections]

    def after(name: str) -> str:
        idx = names.index(name)
        bars = list(ctx.sections[idx][1])
        if scope.end_bar < len(bars):
            return first_chord(bars[scope.end_bar])
        for _name, nxt in ctx.sections[idx + 1:]:
            for token in nxt:
                sym = first_chord(token)
                if sym:
                    return sym
        return ""

    found = {after(n) for n in scope.names if n in names}
    # A grouped section (Verse 1–4) is named only when every occurrence leads to the same chord.
    return found.pop() if len(found) == 1 else ""


def _rhythm_cells(meter: str, level: str, style: str, focus: str, seed: int) -> tuple[Rhythm | None, Rhythm | None]:
    try:
        from span_rhythm_grammar import cell_display, choose_cell, desired_count, vary_cell

        rng = random.Random(seed)
        want = desired_count(level, style=style)
        pref = _FOCUS_PREF[focus]
        cell = choose_cell(
            meter, level, style=style, focus_pref=pref, want=want, rng=rng,
            rhythmic=focus == FOCUS_RHYTHMIC and level != "Beginner", plain=level == "Beginner",
        )
        var = vary_cell(cell, meter, level, style=style, focus_pref=pref, rng=rng)
        base = Rhythm(tuple(cell.figures), cell_display(cell.figures, meter), cell.kind)
        varied = Rhythm(tuple(var.figures), cell_display(var.figures, meter), var.kind)
        return base, (varied if varied.figures != base.figures else None)
    except Exception:
        return None, None


def _material(b: _Build) -> Material | None:
    """Which notes to improvise with between targets, justified chord by chord."""
    chords = list(dict.fromkeys(b.facts))
    if not chords:
        return None
    lines: list[Line] = []
    jazzy = b.style in _JAZZY
    pent_name, pent = key_pentatonic(b.key)
    scale_name, scale = key_scale(b.key)
    pent_check = check_collection(pent_name, pent, chords, key=b.key, style=b.style)
    scale_check = check_collection(scale_name, scale, chords, key=b.key, style=b.style)
    want_pent = b.focus in (FOCUS_MELODIC, FOCUS_MOTIF, FOCUS_RHYTHMIC) and (b.level == "Beginner" or not jazzy)
    blues_check = None
    if b.style == "blues":
        kf = key_facts(b.key)
        blues_pcs = tuple((kf.tonic_pc + s_) % 12 for s_ in (0, 3, 5, 7, 10))
        blues_check = check_collection(f"{kf.tonic} minor pentatonic", blues_pcs, chords, key=b.key, style=b.style)
    choice = None
    if b.focus == FOCUS_CHORD_TONE:
        choice = None
    elif blues_check is not None and blues_check.usable and b.focus != FOCUS_CHORD_TONE:
        choice = blues_check
    elif want_pent and pent_check.usable:
        choice = pent_check
    elif scale_check.usable and b.level != "Beginner":
        choice = scale_check
    elif pent_check.usable:
        choice = pent_check
    if choice is None:
        tones = []
        for f in chords:
            tones.extend(t.name for t in _level_tones(f, b.level))
        claim = Claim("chord_tones_only", chords=tuple(f.symbol for f in chords))
        lines.append(L(BASIS_HARMONY, "Build everything from each chord's own notes and step between them.", claims=[claim]))
        rejected = pent_check if not pent_check.usable else None
        if rejected is not None and b.level != "Beginner":
            bad = next(f for f in rejected.fits if f.verdict == "clashes")
            clash = bad.clash[0]
            fx = chord_facts(bad.chord)
            ref = _uref(fx, clash.pc, b.key, b.style)
            lines.append(
                L(
                    BASIS_HARMONY,
                    f"The {pent_name} doesn't fit everywhere here: its {{n0}} rubs against {{c0}}.",
                    [ref], [fx.symbol],
                    [Claim("collection", value="clashes", pcs=tuple(pent), chords=tuple(f.symbol for f in chords))],
                )
            )
        return Material("Chord tones", (), tuple(dict.fromkeys(tones)), "chord_tones", tuple(lines))
    coll_claim = Claim("collection", value=choice.verdict, pcs=choice.pcs, chords=tuple(f.symbol for f in chords))
    if choice.verdict == "fits":
        lines.append(
            L(BASIS_HARMONY, f"The {choice.name} ({_join(choice.names)}) fits every chord in these bars.", claims=[coll_claim])
        )
    else:
        lines.append(
            L(BASIS_HARMONY, f"The {choice.name} ({_join(choice.names)}) works over these chords, with care:", claims=[coll_claim])
        )
    for fit in choice.fits:
        fx = chord_facts(fit.chord)
        if fit.missing_third:
            third = fx.third
            ref = _tref(fx, third)
            lines.append(
                L(
                    BASIS_HARMONY,
                    "over {c0} it has no {n0} (the chord's 3rd) — add {n0} when {c0} arrives, or lean on the notes it shares.",
                    [ref], [fx.symbol],
                )
            )
        if fit.tension and b.level != "Beginner":
            refs = [_uref(fx, u.pc, b.key, b.style) for u in fit.tension[:1]]
            lines.append(
                L(
                    BASIS_HARMONY,
                    "over {c0}, {n0} is a tension (the " + refs[0].role + ") against the chord's own notes — a deliberate colour; resolve it to a chord note.",
                    refs, [fx.symbol],
                )
            )
        if fit.passing and b.level != "Beginner":
            refs = [_uref(fx, u.pc, b.key, b.style) for u in fit.passing[:2]]
            slots = _slots("n", 0, len(refs))
            lines.append(
                L(
                    BASIS_HARMONY,
                    f"over {{c0}}, {_join(slots)} {'is a passing note' if len(refs) == 1 else 'are passing notes'}: move through, don't hold.",
                    refs, [fx.symbol],
                )
            )
    if choice is pent_check or choice is blues_check:
        lines.append(L(BASIS_STYLE, _style_pentatonic_line(b.style)))
    return Material(choice.name, choice.pcs, choice.names, choice.verdict, tuple(lines))


def _style_pentatonic_line(style: str) -> str:
    if style == "blues":
        return "This is the classic blues palette: its ♭3 and ♭7 rub bluesily against the chords — slide or bend them toward the chord notes."
    if style in _LYRICAL:
        return "A five-note scale keeps a slow song's phrases open and singable — leave room between them."
    if style in _JAZZY:
        return "Use it as a simple starting palette; aim for the chord notes when the harmony changes."
    return "A five-note scale makes short, catchy phrases easy — repeat them and let the band fill the space."


def _style_phrase_line(style: str) -> str:
    if style in ("ballad", "jazz_ballad"):
        return "In a slow song, long notes and breaths between phrases carry the feeling."
    if style == "folk":
        return "In a folk-style song, simple stepwise phrases that repeat sound natural."
    if style in ("jazz", "bossa"):
        return "In this style, mixing a few eighth-note runs with held notes is common."
    if style == "blues":
        return "In a blues, a phrase and its answer (call and response) is the classic shape."
    if style == "funk":
        return "In a funk groove, short, punchy notes and rests matter more than many notes."
    return "In this style, a short phrase repeated with small changes sounds strong."


def _instrument_line(family: str) -> str:
    return {
        "wind": "Breathe in the rests — the space is part of your phrase.",
        "voice": "Sing it on a simple syllable and breathe in the rests.",
        "guitar": "Find the notes in one position first so the phrase can flow.",
        "piano": "Play the idea in your right hand while your left hand keeps the chord's root.",
        "bass": "Play it as a fill, then come back to the root on the next chord's first beat.",
    }.get(family, "Keep it relaxed — the space between notes is part of the phrase.")


def _example(b: _Build, link_index: int, *, variant: str, length: str = "seed") -> dict[str, Any]:
    """A request a later slice can hand to the span motif engine (validated before showing)."""
    link = b.scope.chain[min(link_index, len(b.scope.chain) - 1)]
    beginner = b.level == "Beginner"
    constraints = {
        "simple_pitches": beginner and b.focus == FOCUS_RHYTHMIC,
        "plain_rhythm": beginner,
        "rhythm_focus": FOCUS_LABELS[b.focus] if b.focus == FOCUS_RHYTHMIC else "",
        "target_roles": ["R", "3", "5"] if beginner else ["3", "7"] if b.focus == FOCUS_CHORD_TONE else [],
        "no_chromatic": beginner,
        "smooth_targets": b.focus in (FOCUS_CHORD_TONE, FOCUS_MOTIF),
        "pitch_space": "chord" if b.focus == FOCUS_CHORD_TONE else "",
    }
    return {
        "link_index": link.index,
        "chords": list(link.chords),
        "start_bar": link.start_bar,
        "end_bar": link.end_bar,
        "exact_bar_timing": link.exact_bar_timing,
        "variant": variant,
        "length": length,
        "constraints": constraints,
    }


# ----- challenges


def _idea(b: _Build) -> Challenge:
    first_ev = b.events[0]
    f0 = b.facts[0]
    start = first_ev.start_bar
    end = max(start + 1, start + int(round(first_ev.beats / b.scope.beats_per_bar)) - 1)
    loop = _bar_range(start, min(end, start + 3), b.scope.start_bar, b.scope.end_bar)
    anchor = _tref(f0, b.anchors[0])
    count = _IDEA_NOTES[b.level] - (1 if b.focus == FOCUS_RHYTHMIC else 0)
    tones = _level_tones(f0, b.level)
    if b.focus == FOCUS_CHORD_TONE:
        tones = [t for t in f0.tones if t in tones] or tones
    picks = [anchor] + [_tref(f0, t) for t in tones if t.pc != anchor.pc]
    picks = picks[: max(2, min(count, len(picks)))]
    neighbour: NoteRef | None = None
    if b.focus in (FOCUS_MELODIC, FOCUS_MOTIF) and len(picks) < count:
        for step in (2, 1, -1, -2):
            pc = (anchor.pc + step) % 12
            ref = _uref(f0, pc, b.key, b.style)
            if ref.category in ("colour", PASSING) and pc in key_facts(b.key).in_key_pcs:
                neighbour = ref
                break
    notes = sorted(picks, key=lambda r: (r.pc - f0.root_pc) % 12)
    slots = _slots("n", 0, len(notes))
    word = "notes of the {c0} chord" if b.level == "Beginner" else "chord tones of {c0}"
    steps: list[Line] = [
        L(BASIS_HARMONY, f"Over {{c0}}, use {_join(slots)} — the {word}.", notes, [f0.symbol]),
    ]
    extras = [n for n in notes if n.category == EXTENSION]
    for ext in extras[:1]:
        steps.append(
            L(BASIS_HARMONY, "{n0} is written into the chord symbol ({c0}) — it adds colour and can be held.", [ext], [f0.symbol])
        )
    if neighbour is not None:
        kind = "a colour note" if neighbour.category == "colour" else "a passing note"
        tip = "it can be held for a softer colour" if neighbour.category == "colour" else "use it on the way to a chord note, not as your last note"
        steps.append(L(BASIS_HARMONY, f"Add {{n0}} as {kind} over {{c0}} — {tip}.", [neighbour], [f0.symbol]))
    space = {
        "Beginner": "Play for about two beats, then rest for two. The rest is part of the idea.",
        "Intermediate": "Leave at least one beat of space before you play it again.",
        "Advanced": "Start just after the downbeat so the phrase breathes, and leave space at its end.",
    }[b.level]
    steps.append(L(BASIS_PRACTICE, space))
    cell = b.rhythm.display if b.rhythm else ""
    if b.focus == FOCUS_MELODIC:
        top = max(notes, key=lambda r: (r.pc - f0.root_pc) % 12)
        steps.append(L(BASIS_PRACTICE, "Shape it: rise to {n0}, then come back down and finish on {n1}.", [top, anchor]))
    elif b.focus == FOCUS_RHYTHMIC:
        steps.append(
            L(BASIS_PRACTICE, f"Clap a short rhythm first{f' (try {cell})' if cell else ''}, then play it on just these notes — the rhythm is the idea.")
        )
    elif b.focus == FOCUS_CHORD_TONE:
        nxt = b.facts[1].symbol if len(b.facts) > 1 else f0.symbol
        steps.append(
            L(BASIS_PRACTICE, "Finish on {n0} (the " + anchor.role + " of {c0}) — the next challenge connects it to {c1}.", [anchor], [f0.symbol, nxt])
        )
    else:
        steps.append(
            L(BASIS_PRACTICE, f"Keep it short and recognisable: the same notes and the same rhythm every time{f' (try {cell})' if cell else ''}. This is your motif.")
        )
    steps.append(L(BASIS_PRACTICE, _instrument_line(instrument_family(b.instrument))))
    checklist = {
        FOCUS_MELODIC: ("My phrase has a clear high point.", "It ends on a chord note.", "I left space after it."),
        FOCUS_RHYTHMIC: ("I can repeat the same rhythm four times in a row.", "I left space after it."),
        FOCUS_CHORD_TONE: ("Every note is in the chord.", f"I finish on the target note."),
        FOCUS_MOTIF: ("I can play the idea the same way four times.", "It's short enough to remember.", "I left space after it."),
    }[b.focus]
    return Challenge(
        KIND_IDEA,
        "Create a musical idea",
        L(BASIS_PRACTICE, "Make a short idea over the opening chord and loop it until it feels natural."),
        tuple(steps),
        loop[0], loop[1],
        (f0.symbol,),
        targets=(anchor,),
        checklist=checklist,
        example=_example(b, 0, variant="normal"),
    )


def _rhythm(b: _Build) -> Challenge:
    first = b.events[0]
    start = first.start_bar
    end = start + max(2, int(round(first.beats / b.scope.beats_per_bar))) - 1
    loop = _bar_range(start, min(end, start + 3), b.scope.start_bar, b.scope.end_bar)
    lv = b.level
    steps: list[Line] = []
    if lv == "Beginner":
        steps.append(L(BASIS_PRACTICE, "Play your idea again with the same notes, but hold the last note longer."))
        steps.append(L(BASIS_PRACTICE, "Then start it one beat later than before — same notes, new place in the bar."))
    elif lv == "Intermediate":
        steps.append(L(BASIS_PRACTICE, "Start your idea on the off-beat (the 'and' after beat 1) instead of on the beat."))
        steps.append(L(BASIS_PRACTICE, "Repeat it, changing the length of just one note."))
    else:
        steps.append(L(BASIS_PRACTICE, "Displace your idea by an eighth note each time you repeat it, so it lands somewhere new in the bar."))
        steps.append(L(BASIS_PRACTICE, "Then play it twice as fast once, and stretched to twice as long once."))
    if b.variation is not None:
        steps.append(L(BASIS_PRACTICE, f"A variation of your rhythm to try: {b.variation.display}."))
    if b.focus == FOCUS_RHYTHMIC:
        f0 = b.facts[0]
        others = [_tref(f0, t) for t in f0.stable if t.pc != b.anchors[0].pc][:2]
        slots = _slots("n", 0, len(others))
        steps.append(
            L(BASIS_PRACTICE, f"Call and response: play the idea, rest, then answer with the same rhythm on {_join(slots)}.", others, [f0.symbol])
        )
    if b.focus == FOCUS_MOTIF:
        steps.append(L(BASIS_PRACTICE, "Keep the notes and their up-and-down shape — it must still sound like your motif."))
    pushes = [e for e in b.events if e.push]
    if pushes:
        p = pushes[0]
        steps.append(
            L(
                BASIS_HARMONY,
                f"The chart brings {{c0}} in early, on {_beat_words(p.beat_in_bar)} of bar {p.start_bar} — try placing a note there too.",
                chords=[p.chord],
                claims=[Claim("push", chord=p.chord, number=p.start_bar)],
            )
        )
    return Challenge(
        KIND_RHYTHM,
        "Develop the rhythm",
        L(BASIS_PRACTICE, "Keep your notes; change the rhythm and where the idea sits in the bar."),
        tuple(steps),
        loop[0], loop[1],
        (b.facts[0].symbol,),
        checklist=("The notes stayed the same.", "The rhythm changed but I can still recognise the idea."),
        example=_example(b, 0, variant="normal"),
    )


def _move_line(b: _Build, a: ChordFacts, at: Tone, bf: ChordFacts, bt: Tone, *, lead: str) -> Line:
    a_ref, b_ref = _tref(a, at), _tref(bf, bt)
    semis = signed_motion(at.pc, bt.pc)
    claim = Claim("move", chord=a.symbol, pc=at.pc, other_chord=bf.symbol, other_pc=bt.pc, number=semis)
    if semis == 0:
        return L(
            BASIS_HARMONY,
            lead + "hold {n0} across the change: the " + a_ref.role + " of {c0} becomes the " + b_ref.role + " of {c1}.",
            [a_ref, b_ref], [a.symbol, bf.symbol], [claim, Claim("common", chord=a.symbol, other_chord=bf.symbol, pc=at.pc)],
        )
    return L(
        BASIS_HARMONY,
        lead + "move {n0} → {n1}, " + _motion_words(semis, b.level) + ": the " + a_ref.role + " of {c0} becomes the "
        + b_ref.role + " of {c1}.",
        [a_ref, b_ref], [a.symbol, bf.symbol], [claim],
    )


def _change_lines(b: _Build, ch: Change) -> tuple[list[Line], list[NoteRef]]:
    """The change, voiced by the plan's one continuous line; other good moves as options."""
    lines: list[Line] = [
        L(BASIS_HARMONY, _when(ch.at_bar, b.events[_event_index(b, ch)].beat_in_bar).capitalize() + ", {c0} changes to {c1}.",
          chords=[ch.a.symbol, ch.b.symbol],
          claims=[Claim("change_at", chord=ch.a.symbol, other_chord=ch.b.symbol, number=ch.at_bar)])
    ]
    i = _event_index(b, ch)
    at, bt = b.anchors[max(0, i - 1)], b.anchors[i]
    lines.append(_move_line(b, ch.a, at, ch.b, bt, lead="Your line: "))
    targets = [_tref(ch.b, bt)]
    used = {(at.pc, bt.pc)}
    guide = next((m for m in ch.moves if m.guide_resolution), None)
    if guide is not None and b.level != "Beginner" and (guide.from_tone.pc, guide.to_tone.pc) not in used:
        a_ref, b_ref = _tref(ch.a, guide.from_tone), _tref(ch.b, guide.to_tone)
        lines.append(
            L(
                BASIS_HARMONY,
                "Also strong: {n0}, the " + a_ref.role + " of {c0}, falls " + _motion_words(guide.semitones, b.level).replace("down ", "")
                + " to {n1}, the " + b_ref.role + " of {c1}.",
                [a_ref, b_ref], [ch.a.symbol, ch.b.symbol],
                [Claim("move", chord=ch.a.symbol, pc=guide.from_tone.pc, other_chord=ch.b.symbol, other_pc=guide.to_tone.pc,
                       number=guide.semitones)],
            )
        )
        used.add((guide.from_tone.pc, guide.to_tone.pc))
        targets.append(b_ref)
    common = next((m for m in ch.common if (m.from_tone.pc, m.to_tone.pc) not in used), None)
    if common is not None:
        lines.append(_move_line(b, ch.a, common.from_tone, ch.b, common.to_tone, lead="Or "))
        targets.append(_tref(ch.b, common.to_tone))
    return lines, targets


def _connect(b: _Build, ch: Change, *, title: str) -> Challenge:
    before = [e for e in b.events if e.chord == ch.a.symbol and e.start_bar <= ch.at_bar and e.start_beat < _start_beat(b, ch)]
    a_start = before[-1].start_bar if before else ch.at_bar
    start = max(b.scope.start_bar, ch.at_bar - 2, a_start)
    loop = _bar_range(start, start + 3, b.scope.start_bar, b.scope.end_bar)
    lines, targets = _change_lines(b, ch)
    target = targets[0]
    fx = ch.b
    if b.focus == FOCUS_MELODIC:
        lines.append(L(BASIS_PRACTICE, "Play your idea over {c0}, then answer it over {c1}, landing on {n0} as the chord changes.", [target], [ch.a.symbol, fx.symbol]))
    elif b.focus == FOCUS_RHYTHMIC:
        lines.append(L(BASIS_PRACTICE, "Keep your rhythm exactly the same; only the notes move so the idea fits {c0}.", chords=[fx.symbol]))
    elif b.focus == FOCUS_CHORD_TONE:
        lines.append(L(BASIS_PRACTICE, f"Make the last note before bar {ch.at_bar} and the first note of bar {ch.at_bar} that connection."))
        if b.level == "Advanced":
            below, above = (target.pc - 1) % 12, (target.pc + 1) % 12
            refs = [_uref(fx, below, b.key, b.style), _uref(fx, above, b.key, b.style)]
            lines.append(
                L(
                    BASIS_HARMONY,
                    "Approach {n2} from a half step below ({n0}) or above ({n1}) on the beat before — chromatic approach notes pass quickly into the target.",
                    refs + [target], [fx.symbol],
                    [Claim("approach", chord=fx.symbol, pc=below, other_pc=target.pc), Claim("approach", chord=fx.symbol, pc=above, other_pc=target.pc)],
                )
            )
    else:
        tones = [_tref(fx, t) for t in _level_tones(fx, b.level)]
        slots = _slots("n", 1, len(tones))
        lines.append(
            L(
                BASIS_PRACTICE,
                "Move your whole motif so it lands on {n0}; keep its rhythm and its up-and-down shape. If a note rubs against {c0}, nudge it to the nearest of "
                + _join(slots) + ".",
                [target] + tones, [fx.symbol],
            )
        )
    lines.append(L(BASIS_PRACTICE, "It is still the same idea — only the notes adjust to the new chord."))
    checklist = ("I kept my rhythm through the change.", "I landed on the target note as the chord changed.")
    link = next((l for l in b.scope.chain if l.first_event <= _event_index(b, ch) <= l.last_event), b.scope.chain[0])
    return Challenge(
        KIND_CONNECT,
        title,
        L(BASIS_PRACTICE, "Carry your idea into the next chord without starting a new one."),
        tuple(lines),
        loop[0], loop[1],
        (ch.a.symbol, ch.b.symbol),
        targets=tuple(targets),
        checklist=checklist,
        example=_example(b, link.index, variant="normal", length="standard"),
    )


def _start_beat(b: _Build, ch: Change) -> float:
    return b.events[_event_index(b, ch)].start_beat


def _event_index(b: _Build, ch: Change) -> int:
    for i, e in enumerate(b.events):
        if e.start_bar == ch.at_bar and e.chord == ch.b.symbol:
            return i
    return 0


def _line_through(b: _Build, link: Any) -> Challenge:
    idx = range(link.first_event, link.last_event + 1)
    evs = [b.scope.events[i] for i in idx]
    harmonic = [i for i, e in enumerate(b.events) if e in evs]
    facts = [b.facts[i] for i in harmonic]
    tones = [b.anchors[i] for i in harmonic]
    refs = [_tref(f, t) for f, t in zip(facts, tones)]
    slots = _slots("n", 0, len(refs))
    claims = [
        Claim("move", chord=facts[i].symbol, pc=tones[i].pc, other_chord=facts[i + 1].symbol, other_pc=tones[i + 1].pc,
              number=signed_motion(tones[i].pc, tones[i + 1].pc))
        for i in range(len(facts) - 1)
    ]
    chord_slots = _slots("c", 0, len(facts))
    lines = [
        L(BASIS_HARMONY, f"A connected line through {' → '.join(chord_slots)}: {' → '.join(slots)}.", refs, [f.symbol for f in facts], claims),
    ]
    rel = _relationship(link)
    if rel and b.level != "Beginner":
        lines.append(
            L(BASIS_HARMONY, f"These chords form a {rel} — the line above follows its pull.",
              claims=[Claim("relationship", value=link.span.relationship, chords=tuple(link.chords))])
        )
    lines.append(L(BASIS_PRACTICE, "Play only these landing notes at first, one per chord, then fill the gaps with your idea's rhythm."))
    return Challenge(
        KIND_CONNECT,
        "Connect a chord sequence",
        L(BASIS_PRACTICE, "Link several chords with one line instead of separate ideas."),
        tuple(lines),
        link.start_bar, min(link.end_bar, link.start_bar + 3),
        tuple(f.symbol for f in facts),
        targets=tuple(refs),
        checklist=("I hit each landing note as its chord arrived.", "The line felt connected, not restarted."),
        example=_example(b, link.index, variant="normal", length="standard"),
    )


_REL_NEEDS_DOMINANT = {"ii_V": 1, "ii_V_I": 1, "V_I": 0, "secondary_dominant": 0, "applied": 0, "dominant_resolution": 0,
                       "ii_subV": 1, "subV_I": 0, "ii_subV_I": 1}


def _relationship(link: Any) -> str:
    """The MC1 relationship label, only when the chords' own facts confirm the dominant."""
    span = getattr(link, "span", None)
    if span is None:
        return ""
    rel = str(getattr(span, "relationship", "") or "")
    pos = _REL_NEEDS_DOMINANT.get(rel)
    if pos is None:
        return ""
    facts = chord_facts(link.chords[pos])
    if facts is None or facts.fn_family != FAMILY_DOMINANT or facts.function_root_pc >= 0:
        return ""
    return str(getattr(span, "relationship_label", "") or "")


def _expand(b: _Build) -> Challenge:
    n = len(b.events)
    climax_i = min(n - 1, max(0, (2 * n) // 3))
    ev = b.events[climax_i]
    fx = b.facts[climax_i]
    loop = _bar_range(ev.start_bar - 1 if ev.start_bar > b.scope.start_bar else ev.start_bar, ev.start_bar + 2,
                      b.scope.start_bar, b.scope.end_bar)
    if b.scope.bar_count <= 4:
        loop = (b.scope.start_bar, b.scope.end_bar)
    lines: list[Line] = []
    targets: list[NoteRef] = []
    lv = b.level
    if b.focus == FOCUS_MELODIC:
        high = _tref(fx, b.anchors[climax_i])
        if lv == "Beginner":
            lines.append(L(BASIS_PRACTICE, f"Play your idea, then play it again a little higher, reaching {{n0}} over {{c0}} around bar {ev.start_bar}.", [high], [fx.symbol]))
        elif lv == "Intermediate":
            lines.append(L(BASIS_PRACTICE, f"Build to a high point around bar {ev.start_bar}: reach {{n0}} (the {high.role} of {{c0}}) as the highest note of your phrase, then come back down.", [high], [fx.symbol]))
        else:
            colour = next((t for t in fx.extensions), None)
            colour_ref = _tref(fx, colour) if colour else next(
                (_uref(fx, (fx.root_pc + iv) % 12, b.key, b.style) for iv in (2, 9) if note_use(fx, (fx.root_pc + iv) % 12, key=b.key).category in HOLDABLE),
                high,
            )
            res = min(fx.stable, key=lambda t: (abs(signed_motion(colour_ref.pc, t.pc)) or 99, t.pc))
            lines.append(L(BASIS_PRACTICE, f"Make the high point around bar {ev.start_bar} a colour note: {{n0}} over {{c0}}, then let it step down to {{n1}}.",
                           [colour_ref, _tref(fx, res)], [fx.symbol]))
            high = colour_ref
        targets.append(high)
        lines.append(L(BASIS_STYLE, _style_phrase_line(b.style)))
    elif b.focus == FOCUS_RHYTHMIC:
        if lv == "Beginner":
            lines.append(L(BASIS_PRACTICE, "Play long notes when the chord changes and shorter notes in between."))
        else:
            nxt = next(((i, c) for i, c in enumerate(b.changes) if c.at_bar >= ev.start_bar), (0, b.changes[0]) if b.changes else None)
            if nxt is not None and nxt[1] is not None:
                ch = nxt[1]
                tgt = _tref(ch.b, b.anchors[min(len(b.anchors) - 1, _event_index(b, ch))])
                lines.append(L(BASIS_HARMONY, f"Arrive early: play {{n0}} from {{c0}} an eighth note before bar {ch.at_bar} so your phrase anticipates the change.",
                               [tgt], [ch.b.symbol], [Claim("change_at", chord=ch.a.symbol, other_chord=ch.b.symbol, number=ch.at_bar)]))
                targets.append(tgt)
            if not b.changes:
                lines.append(L(BASIS_PRACTICE, "With no chord changes, move the idea around the bar instead: start it on beat 1, then beat 2, then beat 3 — same notes each time."))
            if lv == "Advanced":
                lines.append(L(BASIS_PRACTICE, "Shift your idea by one beat each time through and let it run across the bar line."))
            if b.style in _JAZZY:
                lines.append(L(BASIS_STYLE, "In this style, a triplet or swung eighth-note feel is a natural option."))
            elif b.style in ("pop", "rock", "funk", "default"):
                lines.append(L(BASIS_STYLE, "In this style, a repeated syncopated figure (a 'hook') is a natural option."))
    elif b.focus == FOCUS_CHORD_TONE:
        if lv == "Beginner":
            tones = [_tref(fx, t) for t in _level_tones(fx, lv)]
            slots = _slots("n", 0, len(tones))
            lines.append(L(BASIS_HARMONY, f"Play {{c0}}'s notes upward ({_join(slots)}), then step to the nearest note of the next chord.", tones, [fx.symbol]))
            targets.extend(tones[:1])
        else:
            loop = (b.scope.start_bar, b.scope.end_bar)  # the line runs through every change
            guide = anchor_line(b.facts, roles=("3", "7"))
            refs = [_tref(f, t) for f, t in zip(b.facts, guide)]
            shown = refs[:8]
            slots = _slots("n", 0, len(shown))
            lines.append(
                L(BASIS_HARMONY, "A line of 3rds and 7ths through every change: " + " → ".join(slots) + ".", shown,
                  claims=[Claim("move", chord=shown[i].chord, pc=shown[i].pc, other_chord=shown[i + 1].chord, other_pc=shown[i + 1].pc,
                                number=signed_motion(shown[i].pc, shown[i + 1].pc)) for i in range(len(shown) - 1)])
            )
            targets.extend(shown)
            if lv == "Advanced":
                ten = _resolving_tension(b)
                if ten is not None:
                    t_ref, res_ref = ten
                    lines.append(
                        L(BASIS_HARMONY, "Over {c0}, try {n0} (" + t_ref.role + ") and resolve it a half step to {n1} on {c1}.",
                          [t_ref, res_ref], [t_ref.chord, res_ref.chord],
                          [Claim("move", chord=t_ref.chord, pc=t_ref.pc, other_chord=res_ref.chord, other_pc=res_ref.pc,
                                 number=signed_motion(t_ref.pc, res_ref.pc))])
                    )
                    lines.append(L(BASIS_STYLE, "Altered colours like this suit jazz-style playing; leave them out if they don't fit your sound."))
    else:
        if lv == "Beginner":
            lines.append(L(BASIS_PRACTICE, "Play your motif on each new chord — same rhythm, notes moved to the target notes."))
        elif lv == "Intermediate":
            lines.append(L(BASIS_PRACTICE, "Fragment it: repeat just the first two notes of your motif, then finish with the whole motif."))
        else:
            lines.append(L(BASIS_PRACTICE, "Turn it upside down (same rhythm, opposite direction) or move it up a step each bar — check that each landing note belongs to its chord."))
        anc = [_tref(f, t) for f, t in zip(b.facts, b.anchors)][:6]
        slots = _slots("n", 0, len(anc))
        lines.append(L(BASIS_HARMONY, "Landing notes for each chord: " + ", ".join(slots) + ".", anc))
        targets.extend(anc)
    title = {
        FOCUS_MELODIC: "Expand the phrase",
        FOCUS_RHYTHMIC: "Push the rhythm further",
        FOCUS_CHORD_TONE: "Connect through every change",
        FOCUS_MOTIF: "Develop the motif",
    }[b.focus]
    checklist = {
        FOCUS_MELODIC: ("My phrase rose to one clear high point.", "It came back down and ended calmly."),
        FOCUS_RHYTHMIC: ("My rhythm changed at least once in a planned way.", "I stayed in time with the backing."),
        FOCUS_CHORD_TONE: ("Each chord change had a planned landing note.",),
        FOCUS_MOTIF: ("A listener could still recognise my original idea.",),
    }[b.focus]
    return Challenge(
        KIND_EXPAND,
        title,
        L(BASIS_PRACTICE, "Grow the idea — it should still sound like the same idea."),
        tuple(lines),
        loop[0], loop[1],
        tuple(dict.fromkeys(f.symbol for f in b.facts)),
        targets=tuple(t for t in targets if t is not None),
        checklist=checklist,
        example=_example(b, min(len(b.scope.chain) - 1, 1), variant="harder" if lv == "Advanced" else "normal", length="standard"),
    )


def _resolving_tension(b: _Build) -> tuple[NoteRef, NoteRef] | None:
    for ch in b.changes:
        if ch.a.family != FAMILY_DOMINANT or (ch.a.fn_root_pc - ch.b.fn_root_pc) % 12 not in (7, 1):
            continue
        for iv in (1, 8, 3):
            pc = (ch.a.root_pc + iv) % 12
            use = note_use(ch.a, pc, key=b.key, style=b.style)
            if use.category not in (TENSION, EXTENSION):
                continue
            for t in ch.b.stable:
                if signed_motion(pc, t.pc) == -1:
                    return _uref(ch.a, pc, b.key, b.style), _tref(ch.b, t)
    return None


def _moment(b: _Build) -> Challenge | None:
    lv = b.level
    for i, (ev, fx) in enumerate(zip(b.events, b.facts)):
        out = outside_tones(fx, key=b.key)
        if not out:
            continue
        o = _tref(fx, out[0])
        if _blues_dominants(b, (fx.symbol,)) and o.role == "7th":
            lines = [
                L(BASIS_HARMONY, "{n0}, the 7th of {c0}, isn't in the " + b.key + " major scale — it's the bluesy note of this chord.",
                  [o], [fx.symbol], [Claim("outside", chord=fx.symbol, pc=o.pc)]),
                L(BASIS_PRACTICE, "Land on {n0} when {c0} arrives and let it be heard.", [o], [fx.symbol]),
            ]
        else:
            lines = [
                L(BASIS_HARMONY, "{c0} brings in {n0}, a note that isn't in the key of " + b.key + ".", [o], [fx.symbol],
                  [Claim("outside", chord=fx.symbol, pc=o.pc)]),
                L(BASIS_PRACTICE, "Land on {n0} when {c0} arrives — it's the sound that makes this chord special.", [o], [fx.symbol]),
            ]
        nxt = b.facts[i + 1] if i + 1 < len(b.facts) else None
        if nxt is not None:
            res = next((t for t in nxt.stable if abs(signed_motion(o.pc, t.pc)) in (1, 2)), None)
            if res is not None:
                r = _tref(nxt, res)
                lines.append(L(BASIS_HARMONY, "Then move it " + _motion_words(signed_motion(o.pc, r.pc), lv) + " to {n1} on {c1}.",
                               [o, r], [fx.symbol, nxt.symbol],
                               [Claim("move", chord=fx.symbol, pc=o.pc, other_chord=nxt.symbol, other_pc=r.pc, number=signed_motion(o.pc, r.pc))]))
            if fx.fn_family == FAMILY_DOMINANT and (fx.fn_root_pc - nxt.fn_root_pc) % 12 == 7 and lv != "Beginner":
                word = "a secondary dominant" if lv == "Advanced" and key_facts(b.key).degree(nxt.fn_root_pc) != 0 else "a dominant chord"
                lines.append(L(BASIS_HARMONY, "{c0} works as " + word + " here, pulling strongly towards {c1}.", chords=[fx.symbol, nxt.symbol],
                               claims=[Claim("resolves", chord=fx.symbol, other_chord=nxt.symbol)]))
        start = ev.start_bar
        loop = _bar_range(start - 1, start + 2, b.scope.start_bar, b.scope.end_bar)
        return Challenge(
            KIND_MOMENT, "Feature the special chord",
            L(BASIS_PRACTICE, "Make the selection's most distinctive chord a highlight of your phrase."),
            tuple(lines), loop[0], loop[1], (fx.symbol,) + ((nxt.symbol,) if nxt else ()),
            targets=(o,), checklist=("I landed on the special note when the chord arrived.",),
            example=_example(b, next((l.index for l in b.scope.chain if l.first_event <= i <= l.last_event), 0), variant="normal"),
        )
    for i, (ev, fx) in enumerate(zip(b.events, b.facts)):
        if fx.family != FAMILY_SUS:
            continue
        sus = next((t for t in fx.stable if t.role in ("4th", "2nd")), None)
        if sus is None:
            continue
        s = _tref(fx, sus)
        lines = [L(BASIS_HARMONY, "{c0} has no 3rd: its {n0} (the " + s.role + ") gives it an open, hanging sound.", [s], [fx.symbol])]
        nxt = b.facts[i + 1] if i + 1 < len(b.facts) else None
        if nxt is not None and nxt.fn_root_pc == fx.fn_root_pc and nxt.third is not None and fx.function_root_pc < 0:
            r = _tref(nxt, nxt.third)
            lines.append(L(BASIS_HARMONY, "When {c1} arrives, let {n0} move to {n1} — the suspension resolves.", [s, r], [fx.symbol, nxt.symbol],
                           [Claim("move", chord=fx.symbol, pc=s.pc, other_chord=nxt.symbol, other_pc=r.pc, number=signed_motion(s.pc, r.pc))]))
        else:
            lines.append(L(BASIS_PRACTICE, "Hold {n0} over {c0} and enjoy the open sound.", [s], [fx.symbol]))
        loop = _bar_range(ev.start_bar, ev.start_bar + 3, b.scope.start_bar, b.scope.end_bar)
        return Challenge(KIND_MOMENT, "Use the suspended chord", L(BASIS_PRACTICE, "Let the suspended chord's open note be heard."),
                         tuple(lines), loop[0], loop[1], (fx.symbol,), targets=(s,),
                         checklist=("I held the suspended note.",), example=_example(b, 0, variant="normal"))
    rests = [e for e in b.scope.events if e.no_chord]
    if rests:
        r = rests[0]
        after = next((i for i, e in enumerate(b.events) if e.start_beat > r.start_beat), None)
        if after is not None:
            t = _tref(b.facts[after], b.anchors[after])
            bar = b.events[after].start_bar
            lines = [
                L(BASIS_HARMONY, f"Bar {r.start_bar} has no chord (N.C.) — the band stops.", claims=[Claim("no_chord", number=r.start_bar)]),
                L(BASIS_PRACTICE, f"Fill the gap with a short pickup that lands on {{n0}} at bar {bar}, when {{c0}} comes back in.", [t], [b.facts[after].symbol]),
            ]
            loop = _bar_range(r.start_bar - 1, bar + 1, b.scope.start_bar, b.scope.end_bar)
            return Challenge(KIND_MOMENT, "Fill the break", L(BASIS_PRACTICE, "Use the break to lead back into the groove."),
                             tuple(lines), loop[0], loop[1], (b.facts[after].symbol,), targets=(t,),
                             checklist=("My pickup landed exactly when the band came back.",), example={})
    return None


# ----- roadmap


def _phrase_rows(b: _Build) -> list[tuple[int, int]]:
    """A phrase grid over the selection: 4-bar phrases (2-bar for short selections)."""
    first, last = b.scope.start_bar, b.scope.end_bar
    size = 2 if b.scope.bar_count <= 4 else 4
    rows = [(s_, min(s_ + size - 1, last)) for s_ in range(first, last + 1, size)]
    if len(rows) > 1 and (rows[-1][1] - rows[-1][0] + 1) < size / 2:
        tail = rows.pop()
        rows[-1] = (rows[-1][0], tail[1])
    return rows


def _events_in(b: _Build, start: int, end: int) -> list[int]:
    """Harmonic events that start in bars ``start``–``end``, else the one still sounding."""
    inside = [i for i, e in enumerate(b.events) if start <= e.start_bar <= end]
    if inside:
        return inside
    sounding = [i for i, e in enumerate(b.events) if e.start_bar < start]
    return sounding[-1:] if sounding else []


_ROLE_PLANS = {
    1: ("whole",),
    2: ("statement", "answer"),
    3: ("statement", "variation", "ending"),
    4: ("statement", "repeat", "development", "ending"),
}


def _roles(n: int) -> tuple[str, ...]:
    if n in _ROLE_PLANS:
        return _ROLE_PLANS[n]
    middle = tuple("development" if i % 2 else "variation" for i in range(n - 3))
    return ("statement", "repeat") + middle + ("ending",)


def _ending_line(b: _Build, last_ref: NoteRef) -> Line:
    e = b.profile.ending
    lv = b.level
    last = chord_facts(e.last)
    claim = Claim("ending", value=e.kind, chord=e.last, other_chord=e.following)
    if b.profile.vamp and e.kind in (ENDING_AUTHENTIC, ENDING_PLAGAL, ENDING_HOME):
        return L(BASIS_HARMONY, "Everything sits on {c0}, the home chord: end on {n0} and hold it.", [last_ref], [e.last], [claim])
    if e.kind in (ENDING_AUTHENTIC, ENDING_PLAGAL, ENDING_HOME):
        name = {ENDING_AUTHENTIC: "a V–I cadence", ENDING_PLAGAL: "a IV–I cadence", ENDING_HOME: "the home chord"}[e.kind]
        if lv == "Beginner" or e.kind == ENDING_HOME:
            text = "The section comes home to {c0} here. End on {n0} and hold it."
        else:
            text = f"The section closes with {name} into {{c0}}. End on {{n0}} and hold it."
        return L(BASIS_HARMONY, text, [last_ref], [e.last], [claim])
    if e.kind == ENDING_HALF:
        word = "the V chord, unresolved" if lv != "Beginner" else "a chord that wants to move on"
        if b.scope.whole_section:
            return L(BASIS_HARMONY, f"These bars end on {{c0}} — {word}. Finish on {{n0}} and let it hang; the next part answers it.",
                     [last_ref], [e.last], [claim])
        chords = [e.last] + ([e.following] if e.following else [])
        after = "; the harmony carries on with {c1}" if e.following else ""
        return L(BASIS_HARMONY, f"These bars end on {{c0}} — {word}. Finish on {{n0}} and let it hang{after}.",
                 [last_ref], chords, [claim])
    if e.kind == ENDING_DECEPTIVE:
        return L(BASIS_HARMONY, "{c1} would normally lead home, but the chart moves to {c0} instead — a surprise. Land on {n0} and let the surprise be heard.",
                 [last_ref], [e.last, e.previous], [claim])
    if e.kind in (ENDING_LEADS_ON, ENDING_MID) and e.following:
        fol = chord_facts(e.following)
        if fol is not None:
            nxt = min(fol.stable, key=lambda t: (abs(signed_motion(last_ref.pc, t.pc)), t.pc))
            n_ref = _tref(fol, nxt)
            lead = "leads into" if e.kind == ENDING_LEADS_ON else "is followed by"
            return L(BASIS_HARMONY, f"{{c0}} {lead} {{c1}} right after these bars. Keep the line moving: end on {{n0}} and step to {{n1}} as {{c1}} arrives.",
                     [last_ref, n_ref], [e.last, e.following], [claim])
    if e.kind == ENDING_HOME_COLOUR:
        return L(BASIS_HARMONY, "These bars end on {c0}: on the key's home note, but not its home chord. Land on {n0} for a soft, open finish.",
                 [last_ref], [e.last], [claim])
    if e.kind == ENDING_LOOPS:
        return L(BASIS_HARMONY, "The chords cycle back to the start. Finish with a short pickup that leads back into your opening idea, through {n0} over {c0}.",
                 [last_ref], [e.last], [claim])
    return L(BASIS_HARMONY, "These bars end on {c0}, not on the home chord, so keep the ending light: {n0} works, without a big finish.",
             [last_ref], [e.last], [claim])


def _roadmap(b: _Build) -> tuple[RoadmapRow, ...]:
    grid = _phrase_rows(b)
    roles = _roles(len(grid))
    rows: list[RoadmapRow] = []
    for n, (role, (start, end)) in enumerate(zip(roles, grid)):
        idx = _events_in(b, start, end)
        anchors = tuple(_tref(b.facts[i], b.anchors[i]) for i in idx)
        chords = tuple(b.facts[i].symbol for i in idx)
        if n == len(grid) - 1 and anchors:
            line = _ending_line(b, _tref(b.facts[-1], b.anchors[-1]))
            if role == "whole":
                line = Line(line.basis, "Play your idea, carry it through the changes, and finish here. " + line.template,
                            line.notes, line.chords, line.claims)
            elif len(anchors) > 1:
                pairs = [f"{{n{i}}} over {{c{i}}}" for i in range(len(anchors) - 1)]
                lead = L(BASIS_PRACTICE, "Head for the close through " + ", ".join(pairs) + ".", list(anchors[:-1]), list(chords[:-1]))
                shift = len(anchors) - 1
                line = Line(
                    line.basis,
                    lead.template + " " + _shift_slots(line.template, shift, shift if len(line.chords) else 0),
                    lead.notes + line.notes,
                    lead.chords + line.chords,
                    lead.claims + line.claims,
                )
        elif not anchors:
            line = L(BASIS_PRACTICE, "No chord sounds here — rest, or play a short pickup into the next bar.")
        else:
            pairs = [f"{{n{i}}} over {{c{i}}}" for i in range(len(anchors))]
            text = {
                "statement": "Play your idea as it is. Landing notes: ",
                "repeat": "Repeat it with the rhythm change you practised, moved to: ",
                "variation": "Vary it — same rhythm, notes adjusted to: ",
                "development": "Develop it (the expand challenge), aiming at: ",
                "answer": "Answer your idea, aiming at: ",
                "ending": "Bring it to a close through: ",
            }[role] + ", ".join(pairs) + "."
            line = L(BASIS_PRACTICE, text, list(anchors), list(chords))
        rows.append(RoadmapRow(role, start, end, chords, anchors, line))
    return tuple(rows)


def _shift_slots(template: str, note_shift: int, chord_shift: int) -> str:
    """Renumber ``{nK}`` / ``{cK}`` slots when two templates are joined."""
    template = re.sub(r"\{n(\d+)\}", lambda m: "{n" + str(int(m.group(1)) + note_shift) + "}", template)
    return re.sub(r"\{c(\d+)\}", lambda m: "{c" + str(int(m.group(1)) + chord_shift) + "}", template)


def _roadmap_challenge(b: _Build, rows: Sequence[RoadmapRow]) -> Challenge:
    steps = tuple(
        Line(r.line.basis, f"Bars {r.start_bar}–{r.end_bar} ({r.role}): " + r.line.template, r.line.notes, r.line.chords, r.line.claims)
        for r in rows
    )
    return Challenge(
        KIND_ROADMAP,
        "Build the complete phrase",
        L(BASIS_PRACTICE, "Put it together: one idea, developed through all of these bars."),
        steps,
        b.scope.start_bar, b.scope.end_bar,
        tuple(dict.fromkeys(f.symbol for f in b.facts)),
        targets=tuple(a for r in rows for a in r.anchors),
        checklist=("It sounded like one connected improvisation.", "I could hear my opening idea come back.", "The ending matched the chords."),
        example={},
    )


# ----- summary


def _blues_dominants(b: _Build, symbols: Sequence[str]) -> bool:
    """In a blues-style major-key song: these are dominant 7ths on I, IV or V (the blues form)."""
    kf = key_facts(b.key)
    if b.style != "blues" or kf.minor:
        return False
    for sym in symbols:
        f = chord_facts(sym)
        if f is None or f.fn_family != FAMILY_DOMINANT or kf.degree(f.fn_root_pc) not in (0, 5, 7):
            return False
    return True


def _summary(b: _Build) -> tuple[Line, ...]:
    p = b.profile
    feel = {"slow": "the chords change slowly", "steady": "about one chord per bar", "quick": "the chords change quickly"}[p.harmonic_rhythm]
    lines = [
        L(BASIS_HARMONY, f"{b.scope.range_label}: {p.changes} chord{'s' if p.changes != 1 else ''} over {p.bars} bar{'s' if p.bars != 1 else ''} — {feel}.",
          claims=[Claim("profile", number=p.changes, value=p.harmonic_rhythm)]),
    ]
    if p.vamp:
        lines.append(L(BASIS_HARMONY, "One chord throughout — your development comes from rhythm, register and shape."))
    elif p.loops:
        cs = _slots("c", 0, len(p.cycle))
        lines.append(L(BASIS_HARMONY, f"The chords repeat a {len(p.cycle)}-chord cycle: {' → '.join(cs)}.", chords=list(p.cycle),
                       claims=[Claim("cycle", chords=tuple(p.cycle))]))
    if p.out_of_key:
        cs = _slots("c", 0, len(p.out_of_key))
        claim = Claim("outside_chords", chords=tuple(p.out_of_key))
        if _blues_dominants(b, p.out_of_key):
            lines.append(L(BASIS_HARMONY, f"{_join(cs)} {'is a dominant 7th chord' if len(cs) == 1 else 'are dominant 7th chords'}"
                           f" whose 7ths lie outside the {b.key} major scale — the typical blues sound.",
                           chords=list(p.out_of_key), claims=[claim]))
        else:
            lines.append(L(BASIS_HARMONY, f"Outside the key of {b.key}: {_join(cs)}.", chords=list(p.out_of_key), claims=[claim]))
    if not p.exact_timing:
        lines.append(L(BASIS_HARMONY, "Some bars hold two chords, so a few changes fall mid-bar."))
    return tuple(lines)


# --------------------------------------------------------------------------- entry point


def build_coaching_plan(
    ctx: Any,
    scope: Any,
    *,
    level: str,
    focus: str,
    style: str | None = None,
    instrument: str | None = None,
) -> CoachingPlan:
    """A deterministic coaching plan for ``scope`` (an S1 CoachScope of ``ctx``)."""
    if not getattr(ctx, "available", False):
        raise ValueError("song context is not available")
    if scope.context_fingerprint != ctx.fingerprint:
        raise ValueError("scope belongs to another song context")
    lv = normalize_level(level)
    fc = normalize_focus(focus)
    st = str(style or ctx.style or "default")
    inst = str(instrument if instrument is not None else ctx.instrument or "")
    key = scope.key_center
    pid = plan_id_for(scope.scope_id, lv, fc, st, inst)
    events = []
    facts: list[ChordFacts] = []
    for e in scope.events:
        f = chord_facts(e.chord) if not e.no_chord else None
        if f is not None:
            events.append(e)
            facts.append(f)
    if not facts:
        raise ValueError("selection has no readable chords")
    following = _following_symbol(ctx, scope)
    profile = section_profile(scope, key=key, following=following)
    changes: list[Change] = []
    for i in range(1, len(events)):
        prev_ev, cur_ev = events[i - 1], events[i]
        gap = any(e.no_chord and prev_ev.start_beat < e.start_beat < cur_ev.start_beat for e in scope.events)
        if not gap:
            changes.append(change_facts(facts[i - 1], facts[i], at_bar=cur_ev.start_bar))
    roles = _LEVEL_ROLES[lv]
    ending = profile.ending
    if ending.resolves:
        end_roles = {"Beginner": ("R", "3"), "Intermediate": ("3", "R"), "Advanced": ("3", "5", "9th", "6th")}[lv]
    elif ending.kind == ENDING_HALF:
        end_roles = ("3", "5")
    else:
        end_roles = roles
    start_roles = ("R", "3") if lv == "Beginner" else None
    anchors = anchor_line(facts, roles=roles, end_roles=end_roles, start_roles=start_roles)
    rhythm, variation = _rhythm_cells(scope.meter, lv, st, fc, int(pid[:8], 16))
    b = _Build(ctx, scope, lv, fc, st, inst, key, profile, events, facts, changes, anchors, rhythm, variation, None,
               chord_facts(following) if following else None)
    b.material = _material(b)

    idea = _idea(b)
    rhythm_ch = _rhythm(b) if (lv == "Beginner" or fc in (FOCUS_RHYTHMIC, FOCUS_MOTIF) or profile.vamp) else None
    connects: list[Challenge] = []
    if changes:
        connects.append(_connect(b, changes[0], title="Connect to the next chord"))
        three = next((l for l in scope.chain if l.length == 3), None)
        if three is not None and (fc == FOCUS_CHORD_TONE or lv == "Advanced"):
            connects.append(_line_through(b, three))
        elif len(changes) > 1 and (scope.bar_count >= 8 or fc == FOCUS_CHORD_TONE):
            second = _pick_second_change(b)
            if second is not None:
                connects.append(_connect(b, second, title="Connect another change"))
    expand = _expand(b) if scope.bar_count >= 2 else None
    moment = _moment(b)
    order = {
        FOCUS_MELODIC: [idea, rhythm_ch, *connects, expand, moment],
        FOCUS_RHYTHMIC: [idea, rhythm_ch, *connects, expand, moment],
        FOCUS_CHORD_TONE: [idea, rhythm_ch, *connects, moment, expand],
        FOCUS_MOTIF: [idea, rhythm_ch, *connects, expand, moment],
    }[fc]
    body = [c for c in order if c is not None]
    # At most five practice challenges before the roadmap: drop the second connection
    # first, then the rhythm drill — never the song-specific moment.
    for drop in (connects[1:], [rhythm_ch] if fc not in (FOCUS_RHYTHMIC, FOCUS_MOTIF) else []):
        for c in drop:
            if len(body) > 5 and c in body:
                body.remove(c)
    body = body[:5]
    rows = _roadmap(b)
    challenges = tuple(body + [_roadmap_challenge(b, rows)])
    from song_coach_context import CHART_CONFIDENCE_LABELS, CHART_CONFIDENCE_NOTES

    reading = tuple(
        f"{f.symbol}: {note}" for f in dict.fromkeys(facts) for note in f.reading_notes
    )
    return CoachingPlan(
        plan_id=pid,
        engine_version=ENGINE_VERSION,
        scope_id=scope.scope_id,
        context_fingerprint=ctx.fingerprint,
        section_label=scope.section_label,
        range_label=scope.range_label,
        start_bar=scope.start_bar,
        end_bar=scope.end_bar,
        key=key,
        meter=scope.meter,
        level=lv,
        focus=fc,
        style=st,
        instrument=inst,
        chart_confidence=ctx.chart_confidence,
        chart_label=CHART_CONFIDENCE_LABELS.get(ctx.chart_confidence, ""),
        chart_note=CHART_CONFIDENCE_NOTES.get(ctx.chart_confidence, ""),
        ending=profile.ending.kind,
        summary=_summary(b),
        material=b.material,
        rhythm=rhythm,
        anchors=tuple(_tref(f, t) for f, t in zip(facts, anchors)),
        challenges=challenges,
        roadmap=rows,
        reading_notes=reading,
    )


def _pick_second_change(b: _Build) -> Change | None:
    rest = b.changes[1:]
    if not rest:
        return None
    for ch in rest:
        if outside_tones(ch.a, key=b.key) or outside_tones(ch.b, key=b.key):
            return ch
    if b.level != "Beginner":
        for ch in rest:
            if any(m.guide_resolution for m in ch.moves):
                return ch
    return rest[-1]


# --------------------------------------------------------------------------- validation


def validate_plan(plan: CoachingPlan, scope: Any) -> list[str]:
    """Re-derive every harmonic claim from the scope's chords; return the problems found."""
    problems: list[str] = []
    chords_in_scope = {e.chord for e in scope.events if not e.no_chord}
    allowed = set(chords_in_scope)
    if plan.ending and plan.roadmap:
        for row in plan.roadmap:
            for c in row.line.chords:
                allowed.add(c)
    if plan.scope_id != scope.scope_id:
        problems.append("plan belongs to another scope")
    for line in plan.all_lines():
        try:
            text = line.render()
        except (KeyError, IndexError) as exc:
            problems.append(f"unfilled slot {exc} in {line.template!r}")
            continue
        if "{" in text or "}" in text:
            problems.append(f"leftover brace in {text!r}")
        # The chart's own section names ("Melody A", "Chorus (Extension)") are not our words.
        own = text
        for label in {plan.section_label, plan.range_label}:
            own = own.replace(label, "")
        if FORBIDDEN_CLAIMS.search(own):
            problems.append(f"claims unknown performance/melody knowledge: {text!r}")
        if plan.level == "Beginner" and BEGINNER_JARGON.search(own):
            problems.append(f"Beginner text uses advanced theory: {text!r}")
        if line.basis not in (BASIS_HARMONY, BASIS_STYLE, BASIS_PRACTICE):
            problems.append(f"line without a basis: {text!r}")
        if line.basis == BASIS_STYLE and line.notes:
            problems.append(f"style suggestion names chart notes: {text!r}")
        for claim in line.claims:
            problems.extend(_check_claim(claim, plan, scope, chords_in_scope))
        problems.extend(_independent_line_checks(line, own, plan, scope))
    for ch in plan.challenges:
        if not (scope.start_bar <= ch.loop_start <= ch.loop_end <= scope.end_bar):
            problems.append(f"{ch.kind} loops bars {ch.loop_start}-{ch.loop_end} outside the selection")
        for t in ch.targets:
            facts = chord_facts(t.chord)
            if facts is None:
                problems.append(f"target on unreadable chord {t.chord}")
                continue
            use = note_use(facts, t.pc, key=plan.key, style=plan.style)
            if use.category not in HOLDABLE:
                problems.append(f"target {t.name} over {t.chord} is {use.category}, not a landing note")
            if not _oracle_holdable(t.chord, t.pc):
                problems.append(f"independent check: target {t.name} rubs against {t.chord}")
    if plan.material is not None and plan.material.pcs:
        facts = [chord_facts(c) for c in dict.fromkeys(e.chord for e in scope.events if not e.no_chord)]
        check = check_collection(plan.material.name, plan.material.pcs, [f for f in facts if f], key=plan.key, style=plan.style)
        if not check.usable:
            problems.append(f"recommended {plan.material.name} clashes with these chords")
    for a in plan.anchors:
        if a.chord not in chords_in_scope:
            problems.append(f"anchor on a chord outside the selection: {a.chord}")
    return problems


def _check_claim(claim: Claim, plan: CoachingPlan, scope: Any, chords: set[str]) -> list[str]:
    out: list[str] = []
    k = claim.kind
    key = plan.key

    def facts_of(sym: str) -> ChordFacts | None:
        f = chord_facts(sym)
        if f is None:
            out.append(f"{k}: unreadable chord {sym!r}")
        return f

    if k == "note":
        f = facts_of(claim.chord)
        if f is None:
            return out
        use = note_use(f, claim.pc, key=key, style=plan.style)
        if use.category != claim.value or use.role != claim.role:
            out.append(f"note {claim.pc} over {claim.chord}: plan says {claim.role}/{claim.value}, chart says {use.role}/{use.category}")
        if f.canonical_agrees and use.category == CHORD_TONE and claim.pc not in f.canonical_pcs:
            out.append(f"note {claim.pc} not among canonical chord tones of {claim.chord}")
    elif k in ("common", "move", "resolves", "change_at"):
        a, b = facts_of(claim.chord), facts_of(claim.other_chord)
        if a is None or b is None:
            return out
        if k == "common" and not (claim.pc in a.charted_pcs and claim.pc in b.charted_pcs):
            out.append(f"{claim.pc} is not common to {claim.chord} and {claim.other_chord}")
        if k == "move":
            if claim.pc not in a.charted_pcs and note_use(a, claim.pc, key=key, style=plan.style).category not in (TENSION, EXTENSION):
                out.append(f"move starts on {claim.pc}, not usable over {claim.chord}")
            if claim.other_pc not in b.charted_pcs:
                out.append(f"move lands on {claim.other_pc}, not a tone of {claim.other_chord}")
            if signed_motion(claim.pc, claim.other_pc) != claim.number:
                out.append(f"move distance {claim.number} wrong for {claim.pc}->{claim.other_pc}")
        if k == "resolves" and not (a.fn_family == FAMILY_DOMINANT and (a.fn_root_pc - b.fn_root_pc) % 12 == 7):
            out.append(f"{claim.chord} does not resolve to {claim.other_chord}")
        if k == "resolves" and not _oracle_resolves(claim.chord, claim.other_chord):
            out.append(f"independent check: {claim.chord} is not a dominant a 5th above {claim.other_chord}")
        if k == "change_at":
            starts = [e.start_bar for e in scope.events if e.chord == claim.other_chord and not e.no_chord]
            if claim.number not in starts:
                out.append(f"{claim.other_chord} does not start at bar {claim.number}")
    elif k == "outside":
        f = facts_of(claim.chord)
        if f is not None and (claim.pc not in f.stable_pcs or claim.pc in key_facts(key).in_key_pcs):
            out.append(f"{claim.pc} is not an outside tone of {claim.chord} in {key}")
    elif k == "outside_chords":
        for sym in claim.chords:
            f = facts_of(sym)
            if f is not None and not outside_tones(f, key=key):
                out.append(f"{sym} is in the key of {key}")
    elif k == "collection":
        facts = [chord_facts(c) for c in claim.chords]
        check = check_collection("collection", claim.pcs, [f for f in facts if f], key=key, style=plan.style)
        if check.verdict != claim.value:
            out.append(f"collection verdict {claim.value} but chords say {check.verdict}")
    elif k == "ending":
        evs = [e for e in scope.events if not e.no_chord]
        facts = [chord_facts(e.chord) for e in evs]
        fol = chord_facts(claim.other_chord) if claim.other_chord else None
        kind = classify_ending([f for f in facts if f], key=key, following=fol, loops=bool(scope.rhythm.cycle),
                               whole_section=scope.whole_section).kind
        if kind != claim.value:
            out.append(f"ending {claim.value} but chords say {kind}")
    elif k == "relationship":
        from harmonic_span_analyzer import analyze_harmonic_spans

        rows = [(scope.section_label, list(claim.chords), list(claim.chords))]
        spans = analyze_harmonic_spans(rows, key_center=key, length=len(claim.chords), include_weak=True)
        if not spans or spans[0].relationship != claim.value:
            out.append(f"relationship {claim.value} not confirmed for {claim.chords}")
    elif k == "approach":
        if abs(signed_motion(claim.pc, claim.other_pc)) != 1:
            out.append("approach note is not a half step from its target")
    elif k == "push":
        if not any(e.push and e.chord == claim.chord and e.start_bar == claim.number for e in scope.events):
            out.append(f"no anticipation of {claim.chord} in bar {claim.number}")
    elif k == "no_chord":
        if not any(e.no_chord and e.start_bar == claim.number for e in scope.events):
            out.append(f"bar {claim.number} has a chord")
    elif k == "cycle":
        if tuple(scope.rhythm.cycle) != claim.chords:
            out.append("cycle claim does not match the chart")
    elif k == "profile":
        if claim.number != scope.rhythm.changes:
            out.append("chord count claim does not match the chart")
    elif k == "chord_tones_only":
        pass
    else:
        out.append(f"unknown claim kind {k}")
    return out


# --------------------------------------------------------------------------- independent checks
#
# Everything below re-derives the facts WITHOUT the coaching chord reader
# (song_coach_harmony.chord_facts / note_use): chord tones come from the shared canonical
# speller plus explicit rules over the symbol text, names are re-decoded to pitch classes,
# intervals are recomputed from the named notes, and functions use their own root rule.
# A generator bug in the chord reader therefore cannot vouch for itself.

_ROLE_INTERVAL = {
    "root": 0, "♭9": 1, "9th": 2, "2nd": 2, "minor 3rd": 3, "♯9": 3, "3rd": 4, "4th": 5, "11th": 5,
    "♯11": 6, "♭5": 6, "5th": 7, "♯5": 8, "♭13": 8, "♭6": 8, "6th": 9, "13th": 9, "°7th": 9,
    "7th": 10, "♭7": 10, "major 7th": 11,
}
_ROLE_LETTER_STEPS = {
    "root": 0, "♭9": 1, "9th": 1, "2nd": 1, "♯9": 1, "minor 3rd": 2, "3rd": 2, "4th": 3, "11th": 3,
    "♯11": 3, "♭5": 4, "5th": 4, "♯5": 4, "♭13": 5, "♭6": 5, "6th": 5, "13th": 5, "7th": 6, "♭7": 6, "major 7th": 6,
}
_MOTION_SIZE = {0: "same note", 1: "half step", 2: "whole step", 3: "small leap", 4: "small leap"}


def _o_pc(name: str) -> int:
    from music_theory import pitch_class_from_spelled_note

    return int(pitch_class_from_spelled_note(name)) % 12


def _o_parts(symbol: str) -> tuple[str, str, str]:
    """(written root, body, written bass) straight from the symbol text."""
    from music_theory import normalize_chord_for_theory

    text = normalize_chord_for_theory(symbol)
    m = re.match(r"([A-G][#b]?)(.*)$", text)
    if not m:
        return "", "", ""
    root, rest = m.group(1), m.group(2)
    bass = ""
    slash = re.search(r"/([A-G][#b]?)$", rest)
    if slash:
        bass, rest = slash.group(1), rest[: slash.start()]
    return root, rest, bass


def _o_canonical(symbol: str) -> set[int]:
    from music_theory import normalize_chord_for_theory, spell_chord_tones

    return {_o_pc(n) for n in spell_chord_tones(normalize_chord_for_theory(symbol)) if n}


def _o_canonical_names(symbol: str) -> set[str]:
    from music_theory import normalize_chord_for_theory, spell_chord_tones

    return {n for n in spell_chord_tones(normalize_chord_for_theory(symbol)) if n}


def _o_supports(body: str, iv: int) -> bool:
    """Does the symbol text itself state this interval above its root?"""
    b = body.replace("Δ", "maj7").replace("ø", "m7b5").replace("°", "dim")
    minor = bool(re.match(r"(m(?!aj)|min|-|dim)", b))
    sus = "sus" in b or b == "5"
    plain = re.sub(r"add(2|4|6|9|11|13)", "", b)
    seven = bool(re.search(r"(?<![b#\d])(7|9|11|13)", plain))
    major7 = bool(re.search(r"maj|M7|M9|M13", b))
    rules = {
        0: True,
        1: "b9" in b or "alt" in b,
        2: bool(re.search(r"(?<![b#])(9|add2|sus2|6/9|69|11|13)", b)),
        3: (minor and not sus) or "#9" in b or "alt" in b,
        4: (not minor and not sus and b != "5"),
        5: bool(re.search(r"sus(?!2)|(?<![b#])11|add4", b)),
        6: bool(re.search(r"b5|#11|dim|m7b5", b)),
        7: not re.search(r"b5|#5|dim|aug|\+|m7b5", b),
        8: bool(re.search(r"#5|b13|aug|\+|alt", b)),
        9: bool(re.search(r"(?<![b\d])6|13|dim7", b)),
        10: seven and not major7 and "dim7" not in b,
        11: major7,
    }
    return bool(rules.get(iv, False))


def _o_chord_tones(symbol: str) -> set[int]:
    """Pitch classes the symbol states: canonical tones, what its own text writes, its bass."""
    root, body, bass = _o_parts(symbol)
    if not root:
        return set()
    rpc = _o_pc(root)
    tones = set(_o_canonical(symbol)) | {(rpc + iv) % 12 for iv in range(12) if _o_supports(body, iv)}
    if not _o_supports(body, 4) and _o_supports(body, 3):
        tones.discard((rpc + 4) % 12)  # m(maj7): the canonical major 3rd is not stated
    if bass:
        tones.add(_o_pc(bass))
    return tones


def _o_function_root(symbol: str) -> int:
    root, _body, bass = _o_parts(symbol)
    rpc = _o_pc(root)
    if bass and _o_pc(bass) not in _o_canonical(symbol) and (_o_pc(bass) - rpc) % 12 in (2, 5, 9):
        return _o_pc(bass)
    return rpc


def _oracle_holdable(symbol: str, pc: int) -> bool:
    """A landing note: a stated chord tone, or a note that is not a half step *above* a chord
    tone (the classic avoid note: 4th over a major 3rd, ♭6 over a 5th). A 9th sitting a half
    step below a minor 3rd is a normal extension."""
    tones = _o_chord_tones(symbol)
    if pc % 12 in tones:
        return True
    return all((pc - t) % 12 != 1 for t in tones)


def _oracle_resolves(a: str, b: str) -> bool:
    ra, rb = _o_function_root(a), _o_function_root(b)
    _r, body, _bass = _o_parts(a)
    return (ra - rb) % 12 == 7 and _o_supports(body, 4) and _o_supports(body, 10)


def _o_key(key: str) -> tuple[int, bool, set[int]]:
    from music_theory import split_key_center

    tonic, mode = split_key_center(key)
    t = _o_pc(tonic)
    minor = mode == "minor"
    steps = (0, 2, 3, 5, 7, 8, 10, 11) if minor else (0, 2, 4, 5, 7, 9, 11)
    return t, minor, {(t + s_) % 12 for s_ in steps}


_ROLE_PHRASE = re.compile(
    r"the (" + "|".join(sorted(map(re.escape, _ROLE_INTERVAL), key=len, reverse=True)) + r") of ([A-G][#b]?[^\s,.;:)—]*)"
)


def _independent_line_checks(line: Line, text: str, plan: CoachingPlan, scope: Any) -> list[str]:
    out: list[str] = []
    for n in line.notes:
        if _o_pc(n.name) != n.pc % 12:
            out.append(f"independent check: {n.name} is not pitch class {n.pc}")
        root, _body, bass = _o_parts(n.chord)
        if not root:
            continue
        if n.role == "bass":
            if not bass or _o_pc(bass) != n.pc:
                out.append(f"independent check: {n.name} is not the bass of {n.chord}")
            continue
        if n.category in (CHORD_TONE, EXTENSION):
            if n.pc not in _o_chord_tones(n.chord):
                out.append(f"independent check: {n.name} is not stated by {n.chord}")
            want = _ROLE_INTERVAL.get(n.role)
            if want is not None and (n.pc - _o_pc(root)) % 12 != want:
                out.append(f"independent check: {n.name} is not the {n.role} of {n.chord}")
            steps = _ROLE_LETTER_STEPS.get(n.role)
            if steps is not None and n.name[0] != "CDEFGAB"[("CDEFGAB".index(root[0]) + steps) % 7]:
                if n.name not in _o_canonical_names(n.chord):  # the shared speller's own names are accepted
                    out.append(f"independent check: {n.name} is misspelled as the {n.role} of {n.chord}")
    # every "the <role> of <chord>" phrase must be true of a note named in the line
    for m in _ROLE_PHRASE.finditer(text):
        role, chord = m.group(1), m.group(2)
        root, _b, _bass = _o_parts(chord)
        if not root:
            continue
        ok = any(
            n.chord == chord and (n.pc - _o_pc(root)) % 12 == _ROLE_INTERVAL[role] and n.pc in _o_chord_tones(chord)
            for n in line.notes
        )
        if not ok:
            out.append(f"independent check: no note in the line is the {role} of {chord}: {text!r}")
    # motion words recomputed from the two named notes
    moves = [c for c in line.claims if c.kind == "move"]
    if len(moves) == 1 and len(line.notes) >= 2 and re.search(r"\b(up|down) a\b|\bfalls\b|\bhold\b", text):
        a = next((n for n in line.notes if n.chord == moves[0].chord and n.pc == moves[0].pc), None)
        b = next((n for n in line.notes if n.chord == moves[0].other_chord and n.pc == moves[0].other_pc), None)
        if a is not None and b is not None:
            d = (_o_pc(b.name) - _o_pc(a.name)) % 12
            semis = d if d <= 6 else d - 12
            if semis != moves[0].number:
                out.append(f"independent check: {a.name}→{b.name} is {semis} semitones, plan says {moves[0].number}")
            size = _MOTION_SIZE.get(abs(semis), "leap")
            if semis == 0:
                if "hold" not in text:
                    out.append(f"independent check: a held note is not described as held: {text!r}")
            else:
                if size not in text:
                    out.append(f"independent check: {a.name}→{b.name} is a {size}: {text!r}")
                wrong = "down" if semis > 0 else "up"
                if re.search(rf"\b{wrong} a (half|whole|small|leap)", text) or ("falls" in text and semis > 0):
                    out.append(f"independent check: {a.name}→{b.name} moves the other way: {text!r}")
    for c in line.claims:
        if c.kind == "approach" and abs(signed_motion(c.pc, c.other_pc)) != 1:
            out.append("independent check: approach note is not a half step away")
        if c.kind == "outside":
            _t, _m, scale = _o_key(plan.key)
            if c.pc in scale or c.pc not in _o_chord_tones(c.chord):
                out.append(f"independent check: {c.pc} is not a chord tone of {c.chord} outside {plan.key}")
        if c.kind == "ending":
            out.extend(_oracle_ending(c, plan, scope, text))
    return out


def _oracle_ending(claim: Claim, plan: CoachingPlan, scope: Any, text: str) -> list[str]:
    """Necessary conditions for each ending kind, from function roots and the key alone."""
    tonic, minor, _scale = _o_key(plan.key)
    chords = [e.chord for e in scope.events if not e.no_chord]
    distinct = [c for i, c in enumerate(chords) if i == 0 or c != chords[i - 1]]
    last = _o_function_root(distinct[-1])
    prev = _o_function_root(distinct[-2]) if len(distinct) > 1 else None
    deg = (last - tonic) % 12
    pdeg = (prev - tonic) % 12 if prev is not None else None
    kind = claim.value
    ok = {
        ENDING_AUTHENTIC: deg == 0 and pdeg in (7, 1, 11),
        ENDING_PLAGAL: deg == 0 and pdeg == 5,
        ENDING_HOME: deg == 0,
        ENDING_HOME_COLOUR: deg == 0,
        ENDING_HALF: deg == 7,
        ENDING_DECEPTIVE: pdeg == 7 and deg == (8 if minor else 9),
        ENDING_LEADS_ON: bool(claim.other_chord) and (last - _o_function_root(claim.other_chord)) % 12 in (7, 1),
        ENDING_MID: not scope.whole_section,
        ENDING_LOOPS: bool(scope.rhythm.cycle),
    }.get(kind, deg != 0)
    out = [] if ok else [f"independent check: ending {kind} not supported by the chords"]
    if "cadence" in text and kind not in (ENDING_AUTHENTIC, ENDING_PLAGAL, ENDING_HALF, ENDING_DECEPTIVE):
        out.append("independent check: cadence named without a cadence")
    if ("comes home" in text or "the home chord:" in text) and deg != 0:
        out.append("independent check: 'home' named on a chord that is not the tonic")
    if "the V chord" in text and deg != 7:
        out.append("independent check: 'the V chord' is not on the 5th degree")
    return out


# --------------------------------------------------------------------------- JSON


def _t(seq: Any) -> tuple:
    return tuple(seq or ())


def _note_from(d: dict[str, Any]) -> NoteRef:
    return NoteRef(int(d["pc"]), d["name"], d["role"], d["chord"], d["category"])


def _claim_from(d: dict[str, Any]) -> Claim:
    return Claim(
        d["kind"], d.get("chord", ""), int(d.get("pc", -1)), d.get("role", ""), d.get("other_chord", ""),
        int(d.get("other_pc", -1)), d.get("value", ""), int(d.get("number", 0)), _t(d.get("pcs")), _t(d.get("chords")),
    )


def _line_from(d: dict[str, Any]) -> Line:
    return Line(
        d["basis"], d["template"], tuple(_note_from(n) for n in d.get("notes") or ()), _t(d.get("chords")),
        tuple(_claim_from(c) for c in d.get("claims") or ()),
    )


def _plan_from_dict(d: dict[str, Any]) -> CoachingPlan:
    mat = d.get("material")
    rhy = d.get("rhythm")
    return CoachingPlan(
        plan_id=d["plan_id"],
        engine_version=d["engine_version"],
        scope_id=d["scope_id"],
        context_fingerprint=d["context_fingerprint"],
        section_label=d["section_label"],
        range_label=d["range_label"],
        start_bar=int(d["start_bar"]),
        end_bar=int(d["end_bar"]),
        key=d["key"],
        meter=d["meter"],
        level=d["level"],
        focus=d["focus"],
        style=d["style"],
        instrument=d["instrument"],
        chart_confidence=d["chart_confidence"],
        chart_label=d["chart_label"],
        chart_note=d["chart_note"],
        ending=d["ending"],
        summary=tuple(_line_from(x) for x in d.get("summary") or ()),
        material=None if not mat else Material(
            mat["name"], _t(mat.get("pcs")), _t(mat.get("names")), mat["verdict"], tuple(_line_from(x) for x in mat.get("lines") or ())
        ),
        rhythm=None if not rhy else Rhythm(_t(rhy.get("figures")), rhy["display"], rhy["kind"]),
        anchors=tuple(_note_from(x) for x in d.get("anchors") or ()),
        challenges=tuple(
            Challenge(
                c["kind"], c["title"], _line_from(c["goal"]), tuple(_line_from(x) for x in c.get("steps") or ()),
                int(c["loop_start"]), int(c["loop_end"]), _t(c.get("chords")),
                tuple(_note_from(x) for x in c.get("targets") or ()), _t(c.get("checklist")), dict(c.get("example") or {}),
            )
            for c in d.get("challenges") or ()
        ),
        roadmap=tuple(
            RoadmapRow(r["role"], int(r["start_bar"]), int(r["end_bar"]), _t(r.get("chords")),
                       tuple(_note_from(x) for x in r.get("anchors") or ()), _line_from(r["line"]))
            for r in d.get("roadmap") or ()
        ),
        reading_notes=_t(d.get("reading_notes")),
    )


def plan_text(plan: CoachingPlan, note: Callable[[NoteRef], str] | None = None, chord: Callable[[str], str] | None = None) -> str:
    """A plain-text rendering (concert names by default) — for review and tests."""
    out = [f"{plan.range_label} · {plan.key} · {plan.level} · {plan.focus_label} · {plan.chart_label}"]
    out += [f"  [{ln.basis}] {ln.render(note, chord)}" for ln in plan.summary]
    if plan.material is not None:
        out.append(f"  Material: {plan.material.name}")
        out += [f"    [{ln.basis}] {ln.render(note, chord)}" for ln in plan.material.lines]
    if plan.rhythm is not None:
        out.append(f"  Rhythm cell: {plan.rhythm.display}")
    for i, ch in enumerate(plan.challenges, 1):
        out.append(f"  {i}. {ch.title}  (loop bars {ch.loop_start}–{ch.loop_end})")
        out.append(f"     {ch.goal.render(note, chord)}")
        out += [f"     - [{ln.basis}] {ln.render(note, chord)}" for ln in ch.steps]
    return "\n".join(out)


__all__ = [
    "BASIS_HARMONY",
    "BASIS_PRACTICE",
    "BASIS_STYLE",
    "BEGINNER_JARGON",
    "Challenge",
    "Claim",
    "CoachingPlan",
    "ENGINE_VERSION",
    "FOCUSES",
    "FOCUS_CHORD_TONE",
    "FOCUS_LABELS",
    "FOCUS_MELODIC",
    "FOCUS_MOTIF",
    "FOCUS_RHYTHMIC",
    "FORBIDDEN_CLAIMS",
    "KIND_CONNECT",
    "KIND_EXPAND",
    "KIND_IDEA",
    "KIND_MOMENT",
    "KIND_RHYTHM",
    "KIND_ROADMAP",
    "LEVELS",
    "Line",
    "Material",
    "NoteRef",
    "Rhythm",
    "RoadmapRow",
    "build_coaching_plan",
    "default_coaching_focus",
    "instrument_family",
    "normalize_focus",
    "normalize_level",
    "plan_id_for",
    "plan_text",
    "validate_plan",
]
