"""Songs-page card guidance: the song's own harmony, read for *this* player.

The card answers four questions for the selected Level × Instrument × Practice Focus:

- **Harmony** — what kind of harmony the song actually uses, derived from its chart
  (pipe bars such as ``Dm7|G7`` expanded so every chord counts) with the existing
  ``harmonic_span_analyzer`` pair classifiers. The facts never change with level;
  only the language does.
- **Melody** — a melody-learning objective built on facts the chart supports (form,
  meter, feel). The catalog has no verified original melodies, so nothing here
  describes the tune's notes; it points to the Practice page's *Generated Practice
  Melody*, which is composed for the chords and is **not** the original melody.
- **Your focus** — the player's selected focus applied to this song on this instrument.
- **Your challenge** — one concrete, achievable task in this song for this player.

Chord and note names are spelled in the chart key the player reads (written key for
transposing instruments, otherwise the Practice / Concert Key).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Sequence

LEVELS = ("Beginner", "Intermediate", "Advanced")
WINDS = ("sax", "brass", "flute", "clarinet")
GENERATED_MELODY = "Generated Practice Melody"
MELODY_TOOL = "Chart & Melody"

# Vocabulary a Beginner card must not use (tests hold the generator to this).
BEGINNER_FORBIDDEN = (
    "ii–v", "ii-v", "secondary dominant", "tritone", "chromatic", "enclosure", "voice leading",
    "voice-leading", "tonicize", "tonicization", "reharmon", "displacement", "subv", "diatonic",
    "altered", "motif", "superimpos", "guide-tone line",
)


def _level(level: str) -> str:
    low = str(level or "").strip().lower()
    if low.startswith("beg"):
        return "Beginner"
    if low.startswith("adv"):
        return "Advanced"
    return "Intermediate"


def instrument_family(instrument: str) -> str:
    """piano / guitar / bass / voice / sax / brass / flute / clarinet / other."""
    low = str(instrument or "").strip().lower()
    for needles, fam in (
        (("bass",), "bass"),
        (("guitar", "ukulele"), "guitar"),
        (("piano", "keys", "keyboard", "organ", "synth"), "piano"),
        (("voice", "vocal", "sing"), "voice"),
        (("sax",), "sax"),
        (("trumpet", "trombone", "horn", "cornet", "flugel", "tuba"), "brass"),
        (("flute",), "flute"),
        (("clarinet",), "clarinet"),
    ):
        if any(n in low for n in needles):
            return fam
    return "other"


def pretty(text: str) -> str:
    """Bb7 → B♭7, F#m → F♯m, bIII → ♭III, "C -> B" → "C → B"."""
    chord_tail = r"(?=maj|min|m|dim|aug|sus|add|\d|/|\s|[,.;:)–\-→|]|$)"
    out = re.sub(r"(?<![A-Za-z])([A-G])b" + chord_tail, r"\1♭", str(text or ""))
    out = re.sub(r"(?<![A-Za-z])([A-G])#" + chord_tail, r"\1♯", out)
    out = re.sub(r"(?<![A-Za-z])b(?=(?:VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)\b)", "♭", out)
    out = re.sub(r"(?<![A-Za-z])#(?=(?:VII|VI|IV|V|III|II|I|vii|vi|iv|v|iii|ii|i)\b)", "♯", out)
    out = re.sub(r"(?<=[0-9m])b(?=5|9|13)", "♭", re.sub(r"(?<=[0-9m])#(?=5|9|11)", "♯", out))
    return out.replace(" -> ", " → ")


def section_phrase(name: str) -> str:
    """How a chart section reads in a sentence: "A" → "the A section", "B (Bridge)" → "the bridge"."""
    raw = str(name or "").strip()
    if not raw:
        return "the song"
    m = re.match(r"^([A-D]\d*)\s*\((.+)\)$", raw)
    if m:
        return f"the {m.group(2).strip().lower()}"
    if re.search(r"(?:^|\s)[A-D]\d*$", raw):
        return f"the {raw} section"
    m = re.fullmatch(r"([A-D]\d*)\s+section", raw, re.I)
    if m:
        return f"the {m.group(1)} section"
    if re.search(r"\d+$", raw):
        return raw
    low = raw.lower()
    if any(w in low for w in ("intro", "verse", "chorus", "bridge", "outro", "interlude", "turnaround", "refrain")):
        return f"the {low}"
    return f"the {raw}"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _is_main_section(name: str) -> bool:
    return not re.search(r"intro|outro|ending|coda|turnaround|interlude|tag|solo", str(name), re.I)


# --------------------------------------------------------------------------- keys


def key_token(practice_key: str | None, original_key: str | None) -> str:
    """Key token whose mode comes from the song when the label omits it ("E" + "Cm" song → "Em")."""
    from music_theory import split_key_center

    pk = str(practice_key or "").strip()
    ok = str(original_key or "").strip() or "C"
    if not pk:
        return ok
    _tonic, mode = split_key_center(ok)
    explicit = bool(re.search(r"(m|min|minor|maj|major)$", pk, re.I)) and not re.fullmatch(r"[A-G][#b]?", pk)
    if explicit:
        return pk
    return f"{pk}m" if mode == "minor" else pk


def key_label(token: str) -> str:
    from music_theory import split_key_center

    tonic, mode = split_key_center(str(token or "C"))
    return f"{pretty(tonic)} {'minor' if mode == 'minor' else 'major'}"


# --------------------------------------------------------------------------- harmony facts


@dataclass
class HarmonyFacts:
    key: str
    minor: bool
    sections: list[tuple[str, list[str]]]
    distinct: list[str]
    frequent: list[str]
    ii_v: list[tuple[str, str, str, bool]] = field(default_factory=list)  # (ii, V, target numeral, resolved)
    secondary: list[tuple[str, str]] = field(default_factory=list)  # (dominant, target)
    secondary_labels: dict[str, str] = field(default_factory=dict)  # dominant → "V/vi"
    tonicized: list[tuple[str, str, str]] = field(default_factory=list)  # (target chord, numeral, section)
    chromatic_dominants: list[list[str]] = field(default_factory=list)
    deceptive: list[tuple[str, str]] = field(default_factory=list)
    loop: tuple[str, ...] = ()
    loop_numerals: tuple[str, ...] = ()
    contrast_section: tuple[str, list[str]] | None = None
    diatonic_share: float = 1.0
    slash: list[str] = field(default_factory=list)
    sus: bool = False
    sevenths: bool = False
    form: str = ""
    section_bars: int = 0
    verified_summary: str = ""
    functional_share: float = 0.0  # share of chord changes that are ii–V / dominant resolutions

    def dominant_chains(self) -> list[list[str]]:
        """Secondary dominants linked into chains: [E7, A7, Dm7], [D7, G7]."""
        chains: list[list[str]] = []
        for d, t in self.secondary:
            for ch in chains:
                if ch[-1] == d:
                    ch.append(t)
                    break
            else:
                chains.append([d, t])
        merged = True
        while merged:
            merged = False
            for a in chains:
                for b in chains:
                    if a is not b and a[-1] == b[0]:
                        a.extend(b[1:])
                        chains.remove(b)
                        merged = True
                        break
                if merged:
                    break
        return sorted(chains, key=len, reverse=True)

    @property
    def character(self) -> str:
        if len(self.ii_v) >= 2 and self.functional_share >= 0.35:
            return "functional"
        if self.loop:
            return "loop"
        if self.diatonic_share >= 0.9 and len(self.distinct) <= 7:
            return "diatonic"
        return "mixed"


def expand_sections(sections: dict[str, list[str]] | None) -> list[tuple[str, list[str]]]:
    """Every chord in order, ``Dm7|G7`` bars split into their two chords."""
    out = []
    for name, chords in (sections or {}).items():
        flat = []
        for bar in chords or []:
            for part in str(bar).split("|"):
                tok = part.strip()
                if tok and tok.upper() not in ("N.C.", "NC", "%", "-"):
                    flat.append(tok)
        if flat:
            out.append((str(name), flat))
    return out


def _form_label(record: dict[str, Any], names: Sequence[str]) -> str:
    ext = record.get("extensions") or {}
    form = str(ext.get("form") or "").strip()
    if form:
        return form
    letters = []
    for n in names:
        m = re.match(r"^\s*([A-D])\d*\b", str(n))
        if m:
            letters.append(m.group(1))
    if len(letters) >= 3 and len(letters) == len([n for n in names if not re.search(r"intro|outro|ending|turnaround|coda", n, re.I)]):
        return "".join(letters)
    return ""


def analyze_song_harmony(record: dict[str, Any], sections: dict[str, list[str]] | None = None) -> HarmonyFacts:
    """Harmony facts from the song's own chart (catalog key; level-independent)."""
    from harmonic_span_analyzer import (
        _classify_pair,
        _deg,
        _implied_target_quality,
        _is_diatonic,
        _key_info,
        _numeral,
        _parse,
    )

    key = str(record.get("key") or "C").strip() or "C"
    key_pc, minor = _key_info(key)
    rows = expand_sections(sections if sections is not None else record.get("sections"))
    all_chords = [c for _n, cs in rows for c in cs]
    counts = Counter(all_chords)
    distinct = list(dict.fromkeys(all_chords))
    facts = HarmonyFacts(
        key=key, minor=minor, sections=rows, distinct=distinct,
        frequent=[c for c, _n in counts.most_common(5)],
    )
    if not all_chords:
        return facts
    parsed = {c: _parse(c) for c in distinct}
    facts.diatonic_share = sum(
        n for c, n in counts.items() if parsed[c].pc >= 0 and _is_diatonic(parsed[c], key_pc, minor)
    ) / max(1, sum(counts.values()))
    facts.slash = [c for c in distinct if "/" in c]
    facts.sus = any("sus" in c.lower() for c in distinct)
    facts.sevenths = sum(1 for c in distinct if re.search(r"7|9|11|13|6", c)) >= max(2, len(distinct) // 2)
    seen_ii_v: set[tuple[str, str]] = set()
    changes = functional_changes = 0
    for name, chords in rows:
        motion = [c for i, c in enumerate(chords) if i == 0 or c != chords[i - 1]]
        for i in range(len(motion) - 1):
            a, b = parsed.get(motion[i]) or _parse(motion[i]), parsed.get(motion[i + 1]) or _parse(motion[i + 1])
            if a.pc < 0 or b.pc < 0:
                continue
            nxt = _parse(motion[i + 2]) if i + 2 < len(motion) else None
            rel = _classify_pair(a, b, key_pc, minor, nxt)
            changes += 1
            if rel.rel_id in ("ii_V", "secondary_dominant", "dominant_chain", "V_I", "ii_subV", "subV_I"):
                functional_changes += 1
            if rel.rel_id == "ii_V":
                target_deg = (rel.target_pc - key_pc) % 12
                resolved = nxt is not None and nxt.pc == rel.target_pc
                pair = (motion[i], motion[i + 1])
                if pair not in seen_ii_v:
                    seen_ii_v.add(pair)
                    facts.ii_v.append((pair[0], pair[1], _numeral(target_deg, rel.target_quality, minor), resolved))
                elif resolved:
                    facts.ii_v = [(a, b, t, r or (a, b) == pair) for a, b, t, r in facts.ii_v]
                if resolved and target_deg != 0 and nxt.quality != "dom" and not any(t[0] == motion[i + 2] for t in facts.tonicized):
                    facts.tonicized.append((motion[i + 2], _numeral(target_deg, nxt.quality, minor), name))
            elif rel.rel_id in ("secondary_dominant", "dominant_chain") and (motion[i], motion[i + 1]) not in facts.secondary:
                facts.secondary.append((motion[i], motion[i + 1]))
                deg_b = _deg(b, key_pc)
                target = _numeral(deg_b, _implied_target_quality(deg_b, False, minor), minor)
                facts.secondary_labels.setdefault(motion[i], f"V/{target}")
            elif rel.rel_id == "deceptive" and (motion[i], motion[i + 1]) not in facts.deceptive:
                facts.deceptive.append((motion[i], motion[i + 1]))
        # Dominants sliding down by half steps (B7–Bb7–A7).
        run: list[str] = []
        for c in motion:
            p = parsed.get(c) or _parse(c)
            if p.quality == "dom" and run and ((parsed.get(run[-1]) or _parse(run[-1])).pc - p.pc) % 12 == 1:
                run.append(c)
                continue
            if len(run) >= 3 and run not in facts.chromatic_dominants:
                facts.chromatic_dominants.append(run)
            run = [c] if p.quality == "dom" else []
        if len(run) >= 3 and run not in facts.chromatic_dominants:
            facts.chromatic_dominants.append(run)
    facts.functional_share = functional_changes / max(1, changes)
    # A repeated four-chord loop that carries much of the song.
    def fn(c: str) -> tuple[int, bool]:
        p = parsed.get(c) or _parse(c)
        return (p.pc, p.quality in ("minor", "m7", "half-dim", "dim"))

    grams: Counter = Counter()
    for _n, chords in rows:
        motion = [c for i, c in enumerate(chords) if i == 0 or c != chords[i - 1]]
        for i in range(len(motion) - 3):
            g = tuple(motion[i:i + 4])
            if len(set(g)) >= 3:
                grams[g] += 1
    if grams:
        top, n = grams.most_common(1)[0]
        loop_fns = {fn(c) for c in top}
        covered = sum(1 for _n, cs in rows for c in cs if fn(c) in loop_fns)
        if n >= 3 and covered / len(all_chords) >= 0.45:
            facts.loop = top
            facts.loop_numerals = tuple(
                _numeral(_deg(parsed[c], key_pc), parsed[c].quality, minor) if parsed[c].pc >= 0 else "?" for c in top
            )
            outside = [(name, cs) for name, cs in rows if sum(1 for c in cs if fn(c) not in loop_fns) / len(cs) >= 0.4]
            if outside:
                name, cs = outside[0]
                facts.contrast_section = (name, list(dict.fromkeys(cs))[:4])
    names = [n for n, _c in rows]
    facts.form = _form_label(record, names)
    sizes = Counter(len((sections or record.get("sections") or {}).get(n) or []) for n in names)
    facts.section_bars = sizes.most_common(1)[0][0] if sizes else 0
    summary = ((record.get("extensions") or {}).get("harmonic_analysis") or {})
    facts.verified_summary = str(summary.get("progression_summary") or "") if isinstance(summary, dict) else ""
    return facts


# --------------------------------------------------------------------------- context


@dataclass
class CardContext:
    record: dict[str, Any]
    facts: HarmonyFacts
    level: str
    fam: str
    instrument: str
    focus: str
    chart_key: str  # key token the chord/note names are spelled in (concert, written or shape)
    original_key: str  # the song chart's own key (canonical harmony)
    practice_key: str  # Practice / Concert Key (sounding)
    bpm: int
    meter: str
    groove: str

    def chart_symbol(self, sym: str) -> str:
        """Canonical chord → the player's chart, via the app's own projection (two steps:
        song key → Practice / Concert Key → written or shape chart key)."""
        from effective_practice_context import musician_facing_chord

        try:
            concert = musician_facing_chord(sym, concert_key=self.original_key, chart_key=self.practice_key)
            return musician_facing_chord(concert, concert_key=self.practice_key, chart_key=self.chart_key)
        except Exception:
            return sym

    def chord(self, sym: str) -> str:
        return pretty(self.chart_symbol(sym))

    def chords(self, syms: Sequence[str], sep: str = "–") -> str:
        return sep.join(self.chord(s) for s in syms)

    @property
    def swing(self) -> bool:
        return "swing" in self.groove.lower()

    @property
    def feel(self) -> str:
        if self.swing:
            return "swing"
        if self.meter in ("6/8", "12/8", "9/8"):
            return f"{self.meter} lilt"
        if "ballad" in self.groove.lower():
            return "ballad pulse"
        return f"{self.groove.lower() or 'steady'} pulse" if self.groove else "steady pulse"

    @property
    def first_section(self) -> tuple[str, list[str]]:
        """The first main section (verse / A / chorus), not an intro."""
        if not self.facts.sections:
            return ("", [])
        return next((s for s in self.facts.sections if _is_main_section(s[0])), self.facts.sections[0])

    @property
    def sec(self) -> str:
        return section_phrase(self.first_section[0])

    def home_notes(self) -> str:
        from music_theory import friendly_note_name, spell_chord_tones, split_key_center

        tonic, mode = split_key_center(self.chart_key)
        # Instructional note names use the app's friendly spelling (B♯ → C, E♯ → F); the chord is unchanged.
        tones = [pretty(friendly_note_name(t)) for t in spell_chord_tones(f"{tonic}{'m' if mode == 'minor' else ''}")[:3]]
        if len(tones) < 2:
            return pretty(tonic)
        return ", ".join(tones[:-1]) + f" and {tones[-1]}"

    def opening(self, n: int = 4) -> list[str]:
        _name, chords = self.first_section
        return list(dict.fromkeys(chords))[:n]

    @property
    def beats(self) -> int:
        """Felt beats per bar (6/8 → 2, 3/4 → 3, 4/4 → 4)."""
        try:
            num, den = (int(x) for x in self.meter.split("/", 1))
        except ValueError:
            return 4
        if den == 8 and num % 3 == 0 and num >= 6:
            return num // 3
        return num

    @property
    def count_aloud(self) -> str:
        try:
            num, den = (int(x) for x in self.meter.split("/", 1))
        except ValueError:
            num, den = 4, 4
        if den == 8 and num % 3 == 0 and num >= 6:
            groups = [f"{i * 3 + 1}-{i * 3 + 2}-{i * 3 + 3}" for i in range(num // 3)]
            return ", ".join(groups)
        return "-".join(str(i + 1) for i in range(num))

    @property
    def slow_bpm(self) -> int:
        factor = {"Beginner": 0.6, "Intermediate": 0.8, "Advanced": 1.0}[self.level]
        return max(40, int(round(self.bpm * factor / 5.0) * 5))

    @property
    def verb(self) -> str:
        return "sing" if self.fam == "voice" else "play"


def _guide_tones(ctx: CardContext, syms: Sequence[str]) -> tuple[str, str, str]:
    """(guide-tone list, first 7→3 move, chain) for chords spelled in the chart key."""
    from musician_coaching import _guide_tone_info

    gt, first, chain = _guide_tone_info([ctx.chart_symbol(s) for s in syms])
    return pretty(gt), pretty(first), pretty(chain)


def _chord_pentatonic(ctx: CardContext, sym: str) -> str:
    """"Dm7" → "D minor" (minor-quality chords) / "G7" → "G major" — the pentatonic that fits the chord."""
    from harmonic_span_analyzer import _parse

    shown = ctx.chord(sym).replace("♭", "b").replace("♯", "#")
    p = _parse(shown)
    m = re.match(r"^([A-G][b#]?)", shown)
    root = m.group(1) if m else shown
    kind = "minor" if p.quality in ("minor", "m7", "half-dim", "dim") else "major"
    return f"{pretty(root)} {kind}"


def _pentatonic(ctx: CardContext) -> str:
    from music_theory import split_key_center

    tonic, mode = split_key_center(ctx.chart_key)
    return f"{pretty(tonic)} {'minor' if mode == 'minor' else 'major'} pentatonic"


# --------------------------------------------------------------------------- harmony text


def harmony_text(ctx: CardContext) -> str:
    f, lvl = ctx.facts, ctx.level
    key = key_label(ctx.chart_key)
    if not f.distinct:
        return "Add a chord chart to see how this song's harmony moves."
    ii_v = f.ii_v
    ex = ", ".join(f"{ctx.chord(a)}–{ctx.chord(b)}" for a, b, _t, _r in ii_v[:3])
    bridge = f.tonicized[0] if f.tonicized else None
    if f.character == "functional" and len(f.secondary) > len(ii_v):
        chains = f.dominant_chains()
        chain = chains[0]
        chain_txt = " → ".join(ctx.chord(c) for c in chain)
        if lvl == "Beginner":
            return (f"Many chords lean hard into the next one (like {chain_txt}), passing the pull along a chain "
                    f"before landing home in {key}.")
        others = [" → ".join(ctx.chord(c) for c in ch) for ch in chains[1:2]]
        if lvl == "Intermediate":
            text = f"Built on chains of secondary dominants ({chain_txt}{'; ' + others[0] if others else ''}) in {key}"
            if ii_v:
                a, b, _t, _r = ii_v[-1]
                text += f", with ii–V cadences such as {ctx.chord(a)}–{ctx.chord(b)}"
            return text + "."
        labels = " → ".join(pretty(f.secondary_labels.get(c, "")) or ctx.chord(c) for c in chain[:-1])
        parts = [f"a secondary-dominant cycle ({chain_txt}: {labels})"]
        if others:
            parts.append(f"a second chain ({others[0]})")
        if ii_v:
            parts.append(f"ii–V cadences ({ex})")
        if f.tonicized:
            b = f.tonicized[0]
            parts.append(f"{section_phrase(b[2])} tonicizing {pretty(b[1])} ({ctx.chord(b[0])})")
        return _cap(_join(parts)) + f", all in {key}."
    if f.character == "functional":
        if lvl == "Beginner":
            first = ii_v[0]
            text = (
                f"The chords mostly come in pairs: a gentle chord, then one that leans forward "
                f"(like {ctx.chord(first[0])} → {ctx.chord(first[1])}). The pairs keep moving to new places before settling home in {key}."
            )
            if bridge:
                text += f" In {section_phrase(bridge[2])}, the music settles on a new home chord ({ctx.chord(bridge[0])}) for a while."
            return text
        targets = list(dict.fromkeys(t for _a, _b, t, _r in ii_v))
        if lvl == "Intermediate":
            text = f"Built mainly from ii–V pairs ({ex}) in {key}"
            text += " that point at different chords" if len(targets) > 1 else ""
            moved_to = {b[0] for b in f.tonicized}
            others = [(d, t) for d, t in f.secondary if t not in moved_to]
            if others:
                d, t = others[0]
                text += f", plus secondary dominants such as {ctx.chord(d)} → {ctx.chord(t)}"
            elif f.chromatic_dominants:
                text += f", plus dominant chords sliding down by half steps ({ctx.chords(f.chromatic_dominants[0])})"
            text += "."
            if bridge:
                text += f" {_cap(section_phrase(bridge[2]))} moves to {ctx.chord(bridge[0])} ({pretty(bridge[1])}) before returning."
            return text
        parts = [f"ii–V cells aimed at {', '.join(pretty(t) for t in targets[:4])} ({ex})"]
        moved_to = {b[0] for b in f.tonicized}
        others = [(d, t) for d, t in f.secondary if t not in moved_to]
        if f.chromatic_dominants:
            parts.append(f"a chromatic dominant descent ({ctx.chords(f.chromatic_dominants[0])})")
        elif others:
            d, t = others[0]
            parts.append(f"secondary dominants ({ctx.chord(d)} → {ctx.chord(t)})")
        if bridge:
            parts.append(f"{section_phrase(bridge[2])} tonicizing {pretty(bridge[1])} ({ctx.chord(bridge[0])})")
        unresolved = [x for x in ii_v if not x[3] and x[2] not in ("I", "i")]
        if unresolved and lvl == "Advanced":
            a, b, t, _r = unresolved[-1]
            parts.append(f"an unresolved ii–V of {pretty(t)} ({ctx.chord(a)}–{ctx.chord(b)})")
        return _join(parts) + f", all in {key}."
    if f.character == "loop":
        loop = ctx.chords(f.loop, " – ")
        contrast = f.contrast_section
        if lvl == "Beginner":
            text = f"Most of the song repeats the same four chords — {loop} — so once that pattern feels easy, you can play most of the song."
            if contrast:
                text += f" {_cap(section_phrase(contrast[0]))} changes the pattern for a moment ({ctx.chords(contrast[1], ', ')})."
            return text
        romans = pretty("–".join(f.loop_numerals))
        if lvl == "Intermediate":
            text = f"A repeating {romans} loop ({loop}) in {key}"
            text += f", with {section_phrase(contrast[0])} switching to {ctx.chords(contrast[1], '–')} for contrast." if contrast else "."
            return text
        extras = []
        if contrast:
            extras.append(f"contrast only from {section_phrase(contrast[0])} ({ctx.chords(contrast[1], '–')})")
        if f.slash:
            extras.append(f"bass motion through slash chords ({', '.join(ctx.chord(s) for s in f.slash[:2])})")
        if f.deceptive:
            a, b = f.deceptive[0]
            extras.append(f"a deceptive {ctx.chord(a)}–{ctx.chord(b)}")
        text = f"A static {romans} loop ({loop}) in {key}"
        return text + (f", with {_join(extras)}." if extras else "; interest has to come from voicing, rhythm and dynamics.")
    common = ", ".join(ctx.chord(c) for c in f.frequent[:4])
    if f.character == "diatonic":
        if lvl == "Beginner":
            return f"A few chords that all belong to {key} — mostly {common} — so the harmony sounds settled and easy to follow."
        extras = []
        if f.deceptive:
            a, b = f.deceptive[0]
            extras.append(f"a deceptive {ctx.chord(a)}–{ctx.chord(b)} turn")
        if f.slash:
            extras.append(f"bass motion through {', '.join(ctx.chord(s) for s in f.slash[:2])}")
        if f.sus:
            extras.append("suspended chords that delay resolution")
        lead = "Diatonic harmony" if lvl == "Intermediate" else "Entirely diatonic harmony"
        text = f"{lead} in {key} built on {common}"
        if lvl == "Advanced" and not extras:
            return text + "; color has to come from voicing, register and rhythm rather than chord choice."
        return text + (f", with {_join(extras)}." if extras else ".")
    outside = [c for c in f.distinct if c not in f.frequent][:2]
    if lvl == "Beginner":
        return f"Most chords belong to {key} ({common}); a few step outside the key for extra color."
    text = f"Mostly in {key} ({common})"
    if f.secondary:
        d, t = f.secondary[0]
        text += f", with secondary dominants such as {ctx.chord(d)} → {ctx.chord(t)}"
    elif outside:
        text += f", with outside colors such as {', '.join(ctx.chord(c) for c in outside)}"
    if f.slash and lvl == "Advanced":
        text += f" and slash-chord bass motion ({ctx.chord(f.slash[0])})"
    return text + "."


def _number_word(n: int) -> str:
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(int(n), str(n))


def _join(parts: Sequence[str]) -> str:
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


# --------------------------------------------------------------------------- melody text


def melody_text(ctx: CardContext) -> str:
    f, lvl = ctx.facts, ctx.level
    verb = ctx.verb.capitalize()
    where = f"the {GENERATED_MELODY} on the Practice page ({MELODY_TOOL})"
    caveat = "generated for this song's chords, not the original melody"
    if not f.distinct:
        return f"Once the song has a chord chart, {where} can generate practice phrases for it."
    form = f.form
    repeat = ""
    if re.match(r"^A+B", form or ""):
        repeat = "the A section comes back, so a phrase you learn there returns"
    elif f.loop:
        repeat = "the chord loop keeps returning, so a short phrase can repeat over it"
    if lvl == "Beginner":
        text = f"{verb} short, simple phrases over the first chords and repeat them slowly"
        text += f" — {repeat}." if repeat else "."
        return text + f" Try {where} to hear simple ideas that fit ({caveat})."
    if lvl == "Intermediate":
        bars = f" in {f.section_bars}-bar sections" if f.section_bars >= 4 else ""
        target = "the 3rd of each new chord" if f.sevenths or f.character == "functional" else "a chord tone of each new chord"
        text = f"Shape phrases{bars} that land on {target} as the harmony changes, keeping the {ctx.feel}."
        return text + f" {where[0].upper() + where[1:]} offers more ideas over these changes ({caveat})."
    contrast = ""
    if f.tonicized:
        contrast = f"re-aim it in {section_phrase(f.tonicized[0][2])}"
    elif f.contrast_section:
        contrast = f"vary it in {section_phrase(f.contrast_section[0])}"
    elif re.match(r"^A+B", form or ""):
        contrast = "vary it in the B section"
    text = "Develop one motif through the form: keep its rhythm, retarget its peak to each new chord"
    text += f", and {contrast}." if contrast else ", and vary its ending."
    return text + f" Use {where} as a starting point for improvising ({caveat})."


# --------------------------------------------------------------------------- focus + challenge


def focus_kind(focus: str) -> str:
    low = " ".join(str(focus or "").lower().split())
    table = (
        ("guide tone", "guide_tones"), ("voice leading", "voice_leading"),
        ("bebop", "bebop"), ("jazz phrasing", "bebop"), ("pentatonic", "pentatonics"),
        ("scale", "scales"), ("strum", "strumming"), ("rhythm guitar", "rhythm"), ("comping", "comping"),
        ("voicing", "voicings"), ("inversion", "voicings"), ("left-hand", "voicings"), ("left hand", "voicings"),
        ("reharmon", "reharmonization"), ("walking", "walking_bass"), ("root motion", "root_motion"),
        ("breath", "breath"), ("endurance", "breath"), ("articulation", "articulation"),
        ("vibrato", "tone"), ("guide", "guide_tones"), ("tone", "tone"), ("dynamic", "dynamics"),
        ("ear", "ear"), ("pitch", "pitch"), ("harmony singing", "harmony_singing"),
        ("emotional", "phrasing"), ("phrasing", "phrasing"), ("range", "range"),
        ("chord transition", "chord_changes"), ("barre", "chord_changes"), ("triad", "triads"),
        ("double stop", "triads"), ("fingerstyle", "fingerstyle"), ("lead", "improvisation"),
        ("solo", "improvisation"), ("improv", "improvisation"), ("melody", "melody"),
        ("timing", "timing"), ("groove", "rhythm"), ("pocket", "rhythm"), ("syncop", "rhythm"), ("rhythm", "rhythm"),
        ("harmony", "harmony"), ("chord", "harmony"), ("technique", "technique"),
    )
    for needle, kind in table:
        if needle in low:
            return kind
    try:
        from practice_focus_policy import category_for_focus

        return {
            "tone": "tone", "timing": "timing", "rhythm_groove": "rhythm", "melody": "melody",
            "harmony": "harmony", "improvisation": "improvisation", "technique": "technique",
            "phrasing": "phrasing", "articulation": "articulation", "dynamics": "dynamics",
            "ear_training": "ear",
        }.get(category_for_focus(focus), "general")
    except Exception:
        return "general"


def _hands(ctx: CardContext) -> str:
    return {
        "piano": "in the left hand with the right hand on top",
        "guitar": "on the middle strings",
        "bass": "in one position on the neck",
        "voice": "on a comfortable vowel",
    }.get(ctx.fam, "with a full, steady air stream" if ctx.fam in WINDS else "")


def _focus_and_challenge(ctx: CardContext) -> tuple[str, str]:
    kind = focus_kind(ctx.focus)
    lvl, fam, f = ctx.level, ctx.fam, ctx.facts
    sec = ctx.sec
    opening = ctx.opening(4)
    ch_open = ctx.chords(opening[:2])
    ch_four = ctx.chords(opening)
    bpm, slow = ctx.bpm, ctx.slow_bpm
    feel = ctx.feel
    gt, first_vl, chain = _guide_tones(ctx, opening)
    wind = fam in WINDS

    if kind in ("guide_tones", "voice_leading"):
        what = "guide-tone line (3rds and 7ths)" if kind == "guide_tones" else "voice-leading line"
        if fam == "piano":
            tool = "as two-note left-hand shells" if lvl != "Advanced" else "in compact three-note voicings"
        elif fam == "guitar":
            tool = "on two adjacent strings" if lvl != "Advanced" else "as three-note shells on the middle strings"
        elif fam == "bass":
            tool = "as the second note of each bar, after the root"
        elif fam == "voice":
            tool = "on a comfortable vowel"
        else:
            tool = "as long tones" if lvl == "Beginner" else "inside swung eighth-note lines" if ctx.swing else "inside flowing lines"
        if lvl == "Beginner":
            focus = (f"Find the two notes that give each chord its sound — the 3rd and the 7th — and {ctx.verb} them {tool}."
                     + (f" {gt}." if gt else ""))
            chal = (f"In {sec}, {ctx.verb} only the 3rd and 7th of {ch_open}, one per bar at {slow} BPM"
                    + (f", and notice how {first_vl} moves by step." if first_vl else "."))
            return focus, chal
        if lvl == "Intermediate":
            focus = (f"Connect the 3rds and 7ths through the changes so each one moves by a step or stays put, {ctx.verb}ing them {tool}."
                     + (f" Start with {first_vl}." if first_vl else ""))
            chal = (f"Through {sec} ({ch_four}), {ctx.verb} a guide-tone line with no leaps at {slow} BPM,"
                    f" keeping the {feel} steady.")
            return focus, chal
        target = (f"the chromatic dominants ({ctx.chords(f.chromatic_dominants[0])})" if f.chromatic_dominants
                  else section_phrase(f.tonicized[0][2]) if f.tonicized else "every chord change")
        focus = (f"Keep one continuous {what} {tool} through the whole form, including {target};"
                 f" decorate the targets with chromatic approaches.")
        chal = (f"Improvise over {sec} at {bpm} BPM while the 3rd or 7th of every chord lands on beat 1,"
                f" approached chromatically from above or below" + (f" (path: {chain})." if chain else "."))
        return focus, chal

    if kind in ("voicings", "comping", "reharmonization"):
        if fam != "piano" and fam != "guitar":
            kind = "harmony"
        else:
            hand = "left-hand" if fam == "piano" else "fretboard"
            if lvl == "Beginner":
                return (f"Use small chord shapes that move as little as possible between {ch_open}, keeping each shape close to the last.",
                        f"Loop {ch_four} at {slow} BPM, changing chords exactly on beat 1 without stopping.")
            if lvl == "Intermediate":
                return (f"Voice the changes with 3rds and 7ths in the {hand} shapes and move each note to the nearest note of the next chord.",
                        f"Comp through {sec} in the {feel} at {slow} BPM using only rootless or shell voicings.")
            extra = (f" and reharmonize one bar with a tritone substitute" if kind == "reharmonization" else "")
            return (f"Voice-lead upper-structure voicings through {sec}, keeping the top note moving by step{extra}.",
                    f"Comp the whole form at {bpm} BPM with no voicing repeated in two neighbouring bars and the top voice moving stepwise.")

    if kind == "bebop":
        swing = "swung eighth notes" if ctx.swing else "even eighth notes"
        if lvl == "Beginner":
            return (f"{ctx.verb.capitalize()} {swing} up and down the scale over {ch_open}, starting each bar on a chord note.",
                    f"At {slow} BPM, {ctx.verb} four bars of {swing} over {sec} that start every bar on the chord's root or 3rd.")
        if lvl == "Intermediate":
            return (f"Build eighth-note lines that put chord tones on the beat and add one chromatic passing note on the way to each new chord.",
                    f"Over {ch_four}, {ctx.verb} a continuous eighth-note line at {slow} BPM that lands on the 3rd of each chord on beat 1.")
        return ("Phrase in bebop language: enclosures around guide tones, chromatic approach notes, and rhythmic displacement of a repeated cell.",
                f"Play two choruses of {sec} at {bpm} BPM, enclosing the 3rd of every new chord and starting at least two phrases off the beat.")

    if kind in ("pentatonics", "scales"):
        pent = _pentatonic(ctx)
        scale = key_label(ctx.chart_key) + " scale"
        if kind == "pentatonics":
            fits = (f"over {sec}'s opening {ch_open}" if f.character == "functional"
                    else "over the loop" if f.loop else "over most of the song")
            if lvl == "Beginner":
                return (f"{ctx.verb.capitalize()} the {pent} slowly {fits}, starting and ending on its first note.",
                        f"At {slow} BPM, {ctx.verb} a four-note {pent} phrase over {ch_open} and repeat it until it feels easy.")
            if lvl == "Intermediate":
                return (f"Use the {pent} {fits} for short melodic phrases, landing on a chord tone when the chord changes.",
                        f"Over {ch_four} at {slow} BPM, {ctx.verb} pentatonic phrases that end on the 3rd or root of the next chord.")
            per_chord = ", ".join(_chord_pentatonic(ctx, c) for c in opening[:4])
            return (f"Give each chord its own pentatonic — {per_chord} — so your lines follow the changes instead of one key scale.",
                    f"Improvise over {sec} at {bpm} BPM, changing pentatonic with each chord and targeting a chord tone on every downbeat.")
        if lvl == "Beginner":
            return (f"Learn the {scale} {_hands(ctx)}, slowly and evenly, up and back.",
                    f"Play the {scale} at {slow} BPM, one note per beat, while the backing loops {sec}.")
        if lvl == "Intermediate":
            return (f"Connect scale runs between chords: start each bar on a chord tone and move by step to the next chord's nearest note.",
                    f"Over {ch_four} at {slow} BPM, play scale fragments that change direction at each new chord.")
        return ("Treat each chord as its own scale (mode) and connect them smoothly, adding chromatic passing tones between scale degrees.",
                f"Run continuous eighth notes through {sec} at {bpm} BPM, choosing the mode for every chord without breaking the line.")

    if kind == "tone":
        if fam == "piano":
            fb = ("Play each chord with a warm, even touch so every note sounds at the same volume.",
                  "Balance the voicings so the top note sings over the others, with relaxed wrist weight.",
                  "Control touch and voicing balance across registers so the melody line sings over inner voices.")
        elif fam == "guitar":
            fb = ("Press just behind the fret so every chord note rings clearly.",
                  "Keep a clean, even tone through the chord changes, with no buzz when the shape moves.",
                  "Shape tone with picking position, attack and fretting-hand muting so each phrase has its own color.")
        elif fam == "voice":
            fb = ("Sing on relaxed, open vowels with a steady breath.",
                  "Keep the vowel shape and resonance consistent from low to high notes in each phrase.",
                  "Match tone color across registers and choose where to brighten or darken it for the lyric.")
        elif fam == "bass":
            fb = ("Let every note sound full for its whole length before you move.",
                  "Keep note length and attack even so the bass line sounds consistent.",
                  "Shape tone with plucking position and note length to fit each section's energy.")
        else:
            fb = (f"Play steady long tones on {ctx.home_notes()} — the home chord of {key_label(ctx.chart_key)} — with a calm, centered sound.",
                  "Keep a centered sound and even air through every phrase and register in the song.",
                  "Match tone color from the low to the high register and shape it through each phrase.")
        focus = fb[LEVELS.index(lvl)]
        if lvl == "Beginner":
            chal = (f"Play one short phrase from {sec} with a steady, clear sound, then take a comfortable breath before repeating it."
                    if wind else f"{ctx.verb.capitalize()} {sec} at {slow} BPM, listening only for a clear, even sound on every note.")
        elif lvl == "Intermediate":
            chal = (f"Play {sec} at {slow} BPM with the same tone on the lowest and highest notes."
                    if wind or fam == "voice" else f"Play {sec} at {slow} BPM with every chord change sounding as clean as the chord before it.")
        else:
            chal = f"Record {sec} at {bpm} BPM twice — once dark, once bright — and keep the tone even within each take."
        return focus, chal

    if kind == "breath":
        if fam in WINDS or fam == "voice":
            phrase = f"{f.section_bars}-bar" if f.section_bars >= 4 else "short"
            if lvl == "Beginner":
                return (f"Breathe low and calmly before each phrase, and plan where you will breathe.",
                        f"Mark a breath every 2 bars in {sec}, then {ctx.verb} it at {slow} BPM without gasping.")
            if lvl == "Intermediate":
                return (f"Plan breaths at the ends of phrases so the {phrase} sections flow without breaking a line.",
                        f"{ctx.verb.capitalize()} {sec} at {slow} BPM breathing only every 4 bars, keeping the sound steady to the end of each phrase.")
            return ("Control the air across long phrases, saving breath for the climactic notes and staggering breaths that the rhythm hides.",
                    f"{ctx.verb.capitalize()} two {phrase} sections at {bpm} BPM with only one quick breath between them and no loss of tone.")
        kind = "phrasing"

    if kind == "articulation":
        if wind:
            fb = ("Start each note with a soft 'ta' or 'da' tongue and keep the air moving between notes.",
                  "Mix slurred and tongued notes" + (" in swing style: tongue off-beats, slur into beats" if ctx.swing else " so phrases have shape") + ".",
                  "Use articulation as phrasing: ghost notes, accents on the upbeats and long slurs to shape each line.")
        elif fam == "guitar":
            fb = ("Pick each note cleanly and let it ring until the next one.",
                  "Contrast legato hammer-ons and slides with crisp picked notes inside each phrase.",
                  "Shape lines with slides, ghost notes and staccato chords to match the song's feel.")
        elif fam == "piano":
            fb = ("Play some notes smoothly connected and some short, and listen for the difference.",
                  "Shape phrases with legato fingering and lighter, shorter chord stabs.",
                  "Contrast legato lines with crisp, accented comping figures that follow the groove.")
        elif fam == "voice":
            fb = ("Say the words clearly in rhythm before singing them.",
                  "Shape consonants and vowels so the words stay clear without breaking the line.",
                  "Use consonant timing and vowel length to place the lyric precisely in the groove.")
        else:
            fb = ("Start each note cleanly and evenly.", "Contrast smooth and short notes within each phrase.",
                  "Use articulation deliberately to shape every phrase.")
        chal = {
            "Beginner": f"{ctx.verb.capitalize()} four bars of {sec} at {slow} BPM with every note starting cleanly.",
            "Intermediate": f"{ctx.verb.capitalize()} {sec} at {slow} BPM twice: all smooth, then with contrasting short and accented notes.",
            "Advanced": f"Perform {sec} at {bpm} BPM with a planned articulation for every phrase, then record and check it.",
        }[lvl]
        return fb[LEVELS.index(lvl)], chal

    if kind in ("rhythm", "strumming"):
        sub = "swung eighths" if ctx.swing else ("the 6/8 triplet feel" if ctx.meter in ("6/8", "12/8") else "even eighth notes")
        sub_adj = "swung-eighth" if ctx.swing else ("6/8" if ctx.meter in ("6/8", "12/8") else "even-eighth")
        if fam == "guitar":
            what = "strumming" if kind == "strumming" else "rhythm playing"
            if lvl == "Beginner":
                return (f"Keep your strumming hand moving down and up in a steady beat, even when you are changing chords.",
                        f"Strum {ch_open} at {slow} BPM, {_number_word(ctx.beats)} down-strums per bar on the main beats, changing chords exactly on beat 1.")
            if lvl == "Intermediate":
                return (f"Lock your {what} to {sub} with clear accents, changing chords without losing the groove.",
                        f"Play {sec} at {slow} BPM, then at {bpm} BPM, keeping a consistent {sub_adj} subdivision with controlled accents and no speeding up.")
            return (f"Vary the {what} pattern by section while keeping the subdivision locked: accents, muted strums and space.",
                    f"Play the whole form at {bpm} BPM with a different accent pattern for each section, never drifting from the click.")
        if fam == "bass":
            fb = (f"Play the root on beat 1 of every bar with a steady pulse.",
                  f"Lock in with the drums: even note lengths and {sub} at {bpm} BPM.",
                  "Shape the groove with ghost notes, anticipations and note length while staying on top of the beat.")
        elif fam == "piano":
            fb = ("Count out loud and change chords exactly on beat 1.",
                  f"Comp in the {feel} with even {sub} and chord changes placed precisely.",
                  "Play with rhythmic displacement and anticipations while keeping the time feel locked.")
        else:
            fb = (f"Keep a steady beat while you {ctx.verb}, counting each bar.",
                  f"Maintain a steady pulse and accurate {sub} through the {feel} phrasing.",
                  "Place phrases with intent: anticipations, delayed entries and rhythmic displacement over a locked pulse.")
        chal = {
            "Beginner": f"{ctx.verb.capitalize()} {sec} at {slow} BPM with a metronome, counting {ctx.count_aloud} out loud.",
            "Intermediate": f"{ctx.verb.capitalize()} {sec} at {slow} BPM with the click only on beats 2 and 4, keeping the {sub} even.",
            "Advanced": f"Play {sec} at {bpm} BPM starting every phrase on a different beat or off-beat without losing the form.",
        }[lvl]
        return fb[LEVELS.index(lvl)], chal

    if kind in ("walking_bass", "root_motion"):
        if lvl == "Beginner":
            return ("Play the root of each chord on beat 1 and hold it, listening to how the roots move.",
                    f"Play roots of {ch_four} at {slow} BPM, one per bar, without looking for the next note.")
        if lvl == "Intermediate":
            return ("Walk four quarter notes per bar: root on beat 1, then chord or scale tones leading to the next root.",
                    f"Walk through {sec} at {slow} BPM with a step or half step into every new root.")
        return ("Shape walking lines with chromatic approaches, enclosures of the next root and occasional two-feel or held-root sections.",
                f"Walk two choruses of {sec} at {bpm} BPM without repeating the same line twice.")

    if kind in ("chord_changes", "triads", "fingerstyle"):
        thing = {"chord_changes": "chord changes", "triads": "triad shapes", "fingerstyle": "fingerpicking pattern"}[kind]
        if lvl == "Beginner":
            return (f"Practice the {thing} for {ch_open} slowly until your hand moves without stopping.",
                    f"Switch between {ch_open} at {slow} BPM, one change every bar, ten times in a row.")
        if lvl == "Intermediate":
            return (f"Make the {thing} through {sec} smooth by moving the fewest fingers between chords.",
                    f"Play {sec} at {slow} BPM with the {thing} landing exactly on beat 1 every bar.")
        return (f"Use the {thing} across the neck to keep a melodic top line moving through every change.",
                f"Play the full form at {bpm} BPM using a new position for each section, without a gap at any change.")

    if kind == "dynamics":
        fb = ("Play some phrases softly and some louder, and hear how the mood changes.",
              "Plan where each section grows louder and where it softens, and make the dynamic changes gradual.",
              "Shape a dynamic arc across the form, with crescendos into arrivals and contrast between sections.")
        chal = {
            "Beginner": f"{ctx.verb.capitalize()} {sec} twice at {slow} BPM: once soft, once strong.",
            "Intermediate": f"{ctx.verb.capitalize()} {sec} at {slow} BPM growing louder over 4 bars, then fading over the next 4.",
            "Advanced": f"Perform the whole form at {bpm} BPM with a written dynamic plan and record it to check the contrast.",
        }[lvl]
        return fb[LEVELS.index(lvl)], chal

    if kind in ("ear", "pitch", "harmony_singing"):
        if lvl == "Beginner":
            return ("Listen to each chord and sing or hum its lowest note before you play it.",
                    f"Hum the root of {ch_open} along with the backing, then check yourself on your instrument.")
        if lvl == "Intermediate":
            return ("Hear where each chord change goes before it arrives — sing the root or 3rd of the next chord.",
                    f"With {sec} looping, sing the 3rd of every chord before playing it, then check the pitch.")
        return ("Hear the chord qualities and their targets by ear, including the less expected changes.",
                f"Transcribe the bass motion of {sec} by ear, then sing a guide-tone line over the backing.")

    if kind == "timing":
        fb = ("Play with the metronome and change chords exactly when the beat arrives.",
              "Check your time against the click: every chord change and phrase start exactly on its beat.",
              "Hold the time yourself: practice with the click on fewer beats until the tempo never drifts.")
        chal = {
            "Beginner": f"Play {sec} at {slow} BPM with the metronome and record it; check that each chord starts on beat 1.",
            "Intermediate": f"Play {sec} at {slow} BPM with the click only on beat 1 of each bar, staying exactly in tempo.",
            "Advanced": f"Play the whole form at {bpm} BPM with the click on beat 1 of every other bar and finish exactly with it.",
        }[lvl]
        return fb[LEVELS.index(lvl)], chal

    if kind == "technique":
        mech = {
            "piano": ("relaxed fingers and wrist", "even finger strength and efficient fingering", "economy of motion and voicing control at tempo"),
            "guitar": ("relaxed fretting and clean chord grips", "efficient fingering between shapes", "economy of motion across positions at tempo"),
            "bass": ("relaxed plucking and clean fretting", "even plucking between fingers", "economy of motion across the neck at tempo"),
            "voice": ("relaxed posture and jaw", "a free, even onset on every note", "agility and control across the range at tempo"),
        }.get(fam, ("relaxed posture and steady air", "even fingers and air across the range", "fluent technique across the full range at tempo"))
        fb = (f"Build the basics this song needs: {mech[0]}, played slowly.",
              f"Work on {mech[1]} so the changes in {sec} feel easy.",
              f"Refine {mech[2]} so nothing technical gets in the way of the music.")
        chal = {
            "Beginner": f"Play the hardest two bars of {sec} at {slow} BPM five times in a row without tension.",
            "Intermediate": f"Raise the tempo of {sec} from {slow} to {bpm} BPM in 5 BPM steps, staying relaxed.",
            "Advanced": f"Play the whole form at {bpm} BPM and then at {bpm + 20} BPM with the same ease and accuracy.",
        }[lvl]
        return fb[LEVELS.index(lvl)], chal

    if kind == "melody":
        fb = (f"Learn melodic lines a few notes at a time, {ctx.verb}ing slowly until each one feels natural.",
              "Learn lines by their target notes first, then fill in the notes between them.",
              "Shape lines around harmonic targets: decide which chord tone each phrase is heading for.")
        chal = {
            "Beginner": f"{ctx.verb.capitalize()} a four-note line over {ch_open} at {slow} BPM until you can do it from memory.",
            "Intermediate": f"Over {ch_four}, {ctx.verb} a line that lands on a chord tone at the start of every bar, at {slow} BPM.",
            "Advanced": f"Write and {ctx.verb} an eight-bar line over {sec} at {bpm} BPM whose high point lands on the strongest chord change.",
        }[lvl]
        return fb[LEVELS.index(lvl)], chal

    if kind in ("phrasing", "range"):
        fb = (f"{ctx.verb.capitalize()} in short phrases with a breath or a rest between them.",
              f"Shape each phrase toward a high point and resolve it as the chords settle, keeping the {feel}.",
              "Phrase in sentences: vary phrase length, leave space, and let phrase endings line up with the harmony's resolutions.")
        chal = {
            "Beginner": f"{ctx.verb.capitalize()} two-bar phrases over {sec} at {slow} BPM, resting for two bars between them.",
            "Intermediate": f"Over {sec} at {slow} BPM, {ctx.verb} four-bar phrases that peak in bar 3 and settle in bar 4.",
            "Advanced": f"Over {sec} at {bpm} BPM, mix one-bar, two-bar and four-bar phrases while keeping a clear arc.",
        }[lvl]
        return fb[LEVELS.index(lvl)], chal

    if kind == "improvisation":
        fb = (f"Make up short phrases using a few notes that fit the chords, and leave space between them.",
              f"Improvise phrases that land on chord tones as the harmony changes, keeping the {feel}.",
              "Develop motifs through the form with rhythmic variation, targeted chord tones and tension that resolves.")
        chal = {
            "Beginner": f"Over {ch_open} at {slow} BPM, {ctx.verb} a three-note idea, then repeat it with a different rhythm.",
            "Intermediate": f"Improvise over {sec} at {slow} BPM, ending every phrase on a chord tone of the current chord.",
            "Advanced": f"Improvise two choruses at {bpm} BPM developing a single motif, with at least one phrase crossing the bar line.",
        }[lvl]
        return fb[LEVELS.index(lvl)], chal

    # harmony / technique / general
    if lvl == "Beginner":
        return (f"Learn how the chords move in {sec}: {ch_four}. Go slowly and keep a steady beat.",
                f"Play or {ctx.verb} along with {ch_four} at {slow} BPM, changing exactly on beat 1.")
    if lvl == "Intermediate":
        return (f"Understand how each chord in {sec} leads to the next, and let that guide your note choices.",
                f"Through {sec} at {slow} BPM, emphasize the note that changes most between neighbouring chords.")
    return ("Analyze the harmonic rhythm and tension points, and make every chord change audible in your line.",
            f"Perform the whole form at {bpm} BPM highlighting each harmonic arrival with your note choice.")


# --------------------------------------------------------------------------- public


def build_song_card_guidance(
    record: dict[str, Any],
    *,
    level: str,
    instrument: str,
    focus: str,
    practice_key: str | None = None,
    chart_key: str | None = None,
    bpm: int | None = None,
    time_signature: str = "4/4",
    groove: str = "",
    key_mode: str = "concert",
    transposing_type: str = "",
    capo_fret: int | None = None,
) -> dict[str, Any]:
    """Setup / Harmony / Melody / Focus / Challenge for the Songs-page card.

    ``practice_key`` is the sounding Practice / Concert Key; ``chart_key`` and ``key_mode``
    ("concert" / "written" / "shape") come from the app's key resolver, so the card spells
    chords exactly as the player's charts do. The harmony analysis always runs on the
    song's own chart, so the musical facts never change with the key or the mode.
    """
    lvl = _level(level)
    original = str(record.get("key") or "C").strip() or "C"
    practice_token = key_token(practice_key or original, original)
    chart_token = key_token(chart_key or practice_key or original, original)
    mode = str(key_mode or "concert").strip().lower()
    if mode == "shape":
        pass  # Capo Shape Mode stays labelled as shapes, even when the shapes sound as written (no capo)
    elif chart_token == practice_token:
        mode = "concert"
    elif mode != "written":
        mode = "written"  # never label transposed chords as concert pitch
    facts = analyze_song_harmony(record)
    ext = record.get("extensions") or {}
    ctx = CardContext(
        record=record, facts=facts, level=lvl, fam=instrument_family(instrument), instrument=str(instrument or ""),
        focus=str(focus or ""), chart_key=chart_token, original_key=original, practice_key=practice_token,
        bpm=int(bpm or ext.get("default_bpm") or 100),
        meter=str(time_signature or "4/4"), groove=str(groove or ext.get("default_groove") or ""),
    )
    focus_line, challenge = _focus_and_challenge(ctx)
    setup = " · ".join(p for p in (lvl, str(instrument or "").strip(), str(focus or "").strip()) if p)
    return {
        "setup": setup,
        "focus_label": str(focus or "").strip() or "General musicianship",
        "harmony": harmony_text(ctx),
        "melody": melody_text(ctx),
        "focus": focus_line,
        "challenge": challenge,
        "form": facts.form,
        "key_mode": mode,
        "key_mode_label": key_mode_label(
            mode, chart_key=chart_token, practice_key=practice_token, instrument=str(instrument or ""),
            transposing_type=transposing_type, capo_fret=capo_fret,
        ),
        "chart_key": chart_token,
        "facts": facts,
    }


def key_mode_label(
    mode: str, *, chart_key: str, practice_key: str, instrument: str = "", transposing_type: str = "",
    capo_fret: int | None = None,
) -> str:
    """Which key the card's chord and note names are in — always stated."""
    sounding = key_label(practice_key)
    if mode == "written":
        who = transposing_type or instrument or "your instrument"
        return f"Written key · {key_label(chart_key)} for {who} — chords and notes as written (sounds in {sounding})."
    if mode == "shape":
        from guitar_capo import shape_chart_label_for_concert

        try:
            shapes = shape_chart_label_for_concert(practice_key, chart_key)
        except Exception:
            shapes = key_label(chart_key)
        capo = f", capo {capo_fret}" if capo_fret else (", no capo" if capo_fret == 0 else "")
        return f"Shape key · {pretty(shapes)} shapes{capo} — chords shown as guitar shapes (sounds in {sounding})."
    return f"Concert key · {sounding} — chords and notes at concert pitch."


__all__ = [
    "BEGINNER_FORBIDDEN",
    "GENERATED_MELODY",
    "MELODY_TOOL",
    "HarmonyFacts",
    "analyze_song_harmony",
    "build_song_card_guidance",
    "expand_sections",
    "focus_kind",
    "harmony_text",
    "instrument_family",
    "key_label",
    "key_mode_label",
    "key_token",
    "melody_text",
]
