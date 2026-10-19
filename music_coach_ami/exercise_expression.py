"""AMI Slice 3: articulation and dynamics as structured, canonical properties of a ``GeneratedExercise``.

natural-language request → ``parse_expression`` (rules, not strings) → ``apply_expression`` (per-note data on
the exercise) → ``expression_abc`` (notation) → prose. ABC is only ever an output.

Per-note canonical fields on the exercise (all index-aligned with ``notes``):

* ``articulation``  "" | "staccato" | "tenuto" | "tongued"   ("tongued" has no glyph: it is the unslurred half of an
                    alternating tongued / slurred pattern and shows as the absence of a slur)
* ``accents``       True where the note is accented
* ``slur_groups``   0 = none; notes sharing an id > 0 are slurred together
* ``dynamics``      the effective level pp..ff at that note ("" = unmarked)

Phrase level: ``dynamic_marks`` — the notated level changes and hairpins, as note indexes — and
``expression`` — the structured request, the rules that were applied (with the notes each matched), the roles
used, the dynamic map, a plain-language summary, and the renderer / playback capability.

Expression is attached to note positions, so it is invariant under the Written Key projection (pitches move,
markings stay on the same notes). Role-based rules read the exercise's own ``roles`` / ``chord_roles`` — never
the rendered note names — and a rule that matches nothing is reported, not invented.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Any

LEVELS = ("pp", "p", "mp", "mf", "f", "ff")

_LEVEL_WORDS = {
    "pianissimo": "pp", "pp": "pp", "piano": "p", "p": "p", "mezzo piano": "mp", "mezzo-piano": "mp", "mezzopiano": "mp",
    "mp": "mp", "mezzo forte": "mf", "mezzo-forte": "mf", "mezzoforte": "mf", "mf": "mf", "forte": "f", "f": "f",
    "fortissimo": "ff", "ff": "ff",
}
_LV = r"(?:pianissimo|mezzo[- ]?piano|mezzo[- ]?forte|fortissimo|piano|forte|pp|mp|mf|ff|p|f)"
_DEFAULT_CRESC = ("mp", "f")
_DEFAULT_DIM = ("f", "mp")

ABC_CAPABILITY: dict[str, Any] = {
    "abc_renderer": "abcjs 6.4.4 (abcjs-basic-min)",
    "notation": {
        "staccato": "dot before the note (the !staccato! form raises renderer warnings, so it is not used)",
        "accent": "!accent!", "tenuto": "!tenuto!", "slur": "( ... )",
        "dynamics": "!pp! !p! !mp! !mf! !f! !ff!", "hairpin": "!crescendo(! ... !crescendo)! / !diminuendo(! ... !diminuendo)!",
        "tongued": "no glyph — shown as the absence of a slur",
    },
    "playback": {
        "ami_card": "none — the AMI card draws static notation and has no player",
        "abcjs_synth_if_a_player_were_added": {
            "accent": "raises velocity", "dynamics": "set velocity", "hairpin": "ramps velocity",
            "staccato": "no audible change", "tenuto": "no audible change", "slur": "no audible change",
        },
    },
}

_ROLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("guide_tone", r"guide[- ]?tones?"),
    ("chord_tone", r"chord[- ]?tones?"),
    ("destination", r"destinations?|arrival (?:notes?|tones?)|phrase ends?|landing (?:notes?|tones?)"),
    ("target", r"targets?(?: notes?| tones?)?|target[- ]notes?"),
    ("approach", r"approach(?:es)?(?: notes?| tones?)?|passing (?:notes?|tones?)|neighbou?r (?:notes?|tones?)"),
    ("tension", r"tensions?(?: notes?| tones?)?|blue notes?"),
    ("resolution", r"resolutions?(?: notes?| tones?)?|resolving (?:notes?|tones?)"),
    ("downbeat", r"downbeats?"),
)
_ROLE_LABEL = {
    "guide_tone": "guide tones", "chord_tone": "chord tones", "destination": "phrase destinations", "target": "target notes",
    "approach": "approach notes", "tension": "tension notes", "resolution": "resolution notes", "downbeat": "downbeats",
}
_ACCENT_WORDS = r"accent(?:ed|s|ing)?|emphasi[sz](?:e|ed|es)|stress(?:ed|es)?"
_LIGHT_WORDS = r"light(?:er|ly)?|detached"
_STACC_WORDS = r"staccato|short"
_SOFT_WORDS = r"softer|quieter|gentler|softly|weaker"
_LOUD_WORDS = r"louder|stronger|strongest|heavier|more powerful"

_NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "second": 2, "third": 3, "fourth": 4, "pair": 2, "1": 1, "2": 2, "3": 3,
           "4": 4, "5": 5, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "first": 1}


def _level(word: str) -> str:
    return _LEVEL_WORDS.get(re.sub(r"\s+", " ", str(word or "").strip().lower()), "")


def _step(level: str, delta: int) -> str:
    return LEVELS[max(0, min(len(LEVELS) - 1, LEVELS.index(level) + delta))]


# ---------------------------------------------------------------- parsing


def empty_request() -> dict[str, Any]:
    return {"articulation": [], "dynamics": [], "mode": "replace", "vary": "", "raw": ""}


def has_rules(req: dict[str, Any] | None) -> bool:
    return bool(req) and bool(req.get("articulation") or req.get("dynamics") or req.get("vary"))


def _split_clauses(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in re.finditer(r"[,;.]|\band\b|\bbut\b|\bwhile\b|\bthen\b", text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if b > a]


def parse_expression(question: str) -> dict[str, Any]:
    """Structured expression request from natural language. ``spans`` lists the matched text (for follow-up parsing)."""
    low = re.sub(r"\s+", " ", str(question or "").lower())
    req = empty_request()
    req["raw"] = str(question or "").strip()
    spans: list[tuple[int, int]] = []
    blank = list(low)

    def consume(m: re.Match[str]) -> None:
        spans.append((m.start(), m.end()))
        for i in range(m.start(), m.end()):
            blank[i] = " "

    def work() -> str:
        return "".join(blank)

    if re.search(r"\b(?:add|also|plus|on top|as well)\b", low):
        req["mode"] = "add"

    # --- variety requests ("different articulation", "another dynamic shape") --------------------------------------
    m = re.search(r"\b(?:different|another|new|alternative|other)\s+(?:dynamics?|dynamic\s+shapes?|dynamic\s+shaping)\b|\bchange\s+the\s+dynamics\b", low)
    if m:
        req["vary"] = "dynamics"
        consume(m)
    m = re.search(r"\b(?:different|another|new|alternative|other)\s+articulations?\b|\bchange\s+the\s+articulations?\b|\bre-?articulate\b", work())
    if m:
        req["vary"] = "articulation" if not req["vary"] else req["vary"]
        consume(m)

    # --- role clauses: "<modifier> ... <role>" in the same clause --------------------------------------------------
    role_rx = "|".join(f"(?P<{name}>{pat})" for name, pat in _ROLE_PATTERNS)
    mod_rx = (rf"(?P<accent>{_ACCENT_WORDS})|(?P<light>{_LIGHT_WORDS})|(?P<stacc>{_STACC_WORDS})|(?P<soft>{_SOFT_WORDS})|(?P<loud>{_LOUD_WORDS})")
    for a, b in _split_clauses(work()):
        clause = work()[a:b]
        roles = [(m.start(), m.end(), m.lastgroup) for m in re.finditer(role_rx, clause)]
        mods = [(m.start(), m.end(), m.lastgroup) for m in re.finditer(mod_rx, clause)]
        if not roles or not mods:
            continue
        names = [r[2] for r in roles]
        # "guide-tone destinations" is one idea: the destinations that are guide tones
        role_key = "guide_tone&destination" if {"guide_tone", "destination"} <= set(names) else None
        for name in ([role_key] if role_key else dict.fromkeys(names)):
            for _s, _e, kind in mods:
                if kind == "accent":
                    req["articulation"].append({"rule": "role", "role": name, "mark": "accent"})
                elif kind in ("light", "stacc"):
                    req["articulation"].append({"rule": "role", "role": name, "mark": "staccato"})
                    if kind == "light":
                        req["dynamics"].append({"rule": "role_delta", "role": name, "delta": -1})
                elif kind == "soft":
                    req["dynamics"].append({"rule": "role_delta", "role": name, "delta": -1})
                elif kind == "loud":
                    req["dynamics"].append({"rule": "role_delta", "role": name, "delta": 1})
        for i in range(a, b):
            blank[i] = " "
        spans.append((a, b))

    text = work()
    # --- bars: "first bar mp, second bar f" -------------------------------------------------------------------------
    bars = []
    for m in re.finditer(rf"\b(first|1st|second|2nd|third|3rd|fourth|4th)\s+bars?\s*(?:is\s+|at\s+|in\s+|play\s+)?(?P<lv>{_LV})\b", text):
        bars.append((_NUMBER.get(m.group(1), 1), _level(m.group("lv"))))
        consume(m)
    if bars:
        bars.sort()
        levels = [lv for _n, lv in bars if lv]
        if levels:
            req["dynamics"].append({"rule": "bars", "levels": levels})
    text = work()

    # --- ramps and hairpins -----------------------------------------------------------------------------------------
    start = re.search(rf"\b(?:start(?:ing|s)?|begin(?:ning|s)?|open(?:ing)?)\s+(?:(?:at|on|with|in)\s+)?(?P<lv>{_LV})\b", text)
    end_to = re.search(
        rf"\b(?:end(?:ing|s)?|finish(?:ing)?)\s+(?:(?:at|on|with|in)\s+)?(?P<lv>{_LV})\b"
        rf"|\b(?:crescendo|diminuendo|decrescendo|build|grow|fade|get\s+louder|get\s+softer|gradually\s+(?:louder|softer))\s*(?:up\s+|down\s+)?to\s+(?P<lv2>{_LV})\b",
        text)
    cresc = re.search(r"\bcrescendo\b|\bbuild(?:ing)?\b|\bget(?:ting)?\s+louder\b|\bgrow(?:ing)?\b", text)
    dim = re.search(r"\bdiminuendo\b|\bdecrescendo\b|\bfad(?:e|ing)\b|\bget(?:ting)?\s+softer\b|\bdie\s+away\b", text)
    if start or end_to or cresc or dim:
        a = _level(start.group("lv")) if start else ""
        b = _level((end_to.group("lv") or end_to.group("lv2")) if end_to else "")
        direction = "crescendo" if cresc and not dim else ("diminuendo" if dim and not cresc else "")
        if a and b:
            req["dynamics"].append({"rule": "ramp", "from": a, "to": b})
        elif b and direction == "crescendo":
            req["dynamics"].append({"rule": "ramp", "from": _step(b, -2), "to": b})
        elif b and direction == "diminuendo":
            req["dynamics"].append({"rule": "ramp", "from": _step(b, 2), "to": b})
        elif a and direction == "crescendo":
            req["dynamics"].append({"rule": "ramp", "from": a, "to": _step(a, 2)})
        elif a and direction == "diminuendo":
            req["dynamics"].append({"rule": "ramp", "from": a, "to": _step(a, -2)})
        elif a and not direction:
            req["dynamics"].append({"rule": "level", "level": a})
        elif direction:
            req["dynamics"].append({"rule": "hairpin", "dir": direction})
        for rx in (start, end_to, cresc, dim):
            if rx:
                consume(rx)
        text = work()
    elif not req["dynamics"] or all(r.get("rule") == "role_delta" for r in req["dynamics"]):
        m = re.search(rf"(?:\bat\s+|\bin\s+|\bplay(?:ed|ing)?\s+(?:it\s+)?|\bmake\s+it\s+|\bkeep\s+it\s+|\bwith\s+)(?P<lv>{_LV})\b(?!\s+(?:major|minor|key|chord|scale))", text)
        if m and m.group("lv") not in ("p", "f") or (m and re.search(r"\b(?:make|play|keep)\b", text)):
            lv = _level(m.group("lv"))
            if lv:
                req["dynamics"].append({"rule": "level", "level": lv})
                consume(m)
                text = work()

    # --- global / positional articulation ---------------------------------------------------------------------------
    m = re.search(r"\balternat(?:e|ing)\b[^.,;]*\b(?:tongu|slur)\w*[^.,;]*", text)
    if m:
        req["articulation"].append({"rule": "alternate"})
        consume(m)
        text = work()
    m = re.search(rf"\b(?:slur(?:s|red)?|legato\s+groups?)\s+(?:(?:over|every|each)\s+)?(?:(?:the\s+)?(?P<n>one|two|three|four|five|pair|[2-5])[- ]?(?:notes?|note\s+groups?|beats?)?|pairs?)\b"
                  rf"|\b(?P<n2>two|three|four|five|[2-5])[- ]notes?\s+slurs?\b|\bslur(?:s|red)?\s+(?:each|every)\s+(?P<n3>pair)\b|\bslur(?:s)?\s+(?:over\s+)?(?:each|every)\s+(?P<n4>two|three|four|[2-4])[- ]note", text)
    if m:
        n = _NUMBER.get(m.group("n") or m.group("n2") or m.group("n3") or m.group("n4") or "pair", 2)
        req["articulation"].append({"rule": "slur_groups", "size": max(2, n)})
        consume(m)
        text = work()
    m = re.search(r"\blegato\b|\bsmooth(?:ly)?\b|\bslurred\b|\bconnected\b", text)
    if m:
        req["articulation"].append({"rule": "legato"})
        consume(m)
        text = work()
    for m in re.finditer(rf"\b(?:{_ACCENT_WORDS})\s+(?:on\s+|the\s+)*(?:beat\s+(?P<beat>one|two|three|four|[1-4])|(?:every|each)\s+(?P<nth>second|third|fourth|2nd|3rd|4th|two|three|four|[2-4])(?:nd|rd|th)?\s+note|downbeats?)", text):
        if m.group("beat"):
            req["articulation"].append({"rule": "beat", "beat": _NUMBER.get(m.group("beat"), 1), "mark": "accent"})
        elif m.group("nth"):
            req["articulation"].append({"rule": "every_nth", "n": _NUMBER.get(m.group("nth"), 2), "mark": "accent"})
        else:
            req["articulation"].append({"rule": "beat", "beat": 1, "mark": "accent"})
        consume(m)
    text = work()
    for m in re.finditer(rf"\b(?:{_ACCENT_WORDS})\s+(?:the\s+)?(?P<which>first|last|final)\s+note\b", text):
        req["articulation"].append({"rule": "position", "which": "first" if m.group("which") == "first" else "last", "mark": "accent"})
        consume(m)
    text = work()
    m = re.search(r"\bstaccato\b|\bdetached\b", text)
    if m:
        req["articulation"].append({"rule": "all", "art": "staccato"})
        consume(m)
        text = work()
    m = re.search(r"\btenuto\b", text)
    if m:
        req["articulation"].append({"rule": "all", "art": "tenuto"})
        consume(m)
    req["spans"] = sorted(spans)
    return req


def merge_requests(parent: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, Any]:
    """The request an exercise carries after a follow-up: new rules replace (or, with "add", extend) the parent's."""
    base = {"articulation": list((parent or {}).get("articulation") or []), "dynamics": list((parent or {}).get("dynamics") or [])}
    new = new or {}
    add = new.get("mode") == "add"
    for dim in ("articulation", "dynamics"):
        rules = list(new.get(dim) or [])
        if not rules:
            continue
        base[dim] = (base[dim] + [r for r in rules if r not in base[dim]]) if add else rules
    base["mode"] = "replace"
    base["vary"] = ""
    base["raw"] = (new.get("raw") or (parent or {}).get("raw") or "")
    return base


_ART_PRESETS: tuple[list[dict[str, Any]], ...] = (
    [{"rule": "all", "art": "staccato"}],
    [{"rule": "slur_groups", "size": 2}],
    [{"rule": "beat", "beat": 1, "mark": "accent"}],
    [{"rule": "alternate"}],
    [{"rule": "legato"}],
    [{"rule": "every_nth", "n": 3, "mark": "accent"}],
)
_DYN_PRESETS: tuple[list[dict[str, Any]], ...] = (
    [{"rule": "hairpin", "dir": "crescendo"}],
    [{"rule": "hairpin", "dir": "diminuendo"}],
    [{"rule": "ramp", "from": "p", "to": "f"}],
    [{"rule": "bars", "levels": ["mp", "f"]}],
    [{"rule": "level", "level": "mf"}],
    [{"rule": "ramp", "from": "f", "to": "p"}],
)


def vary_request(current: dict[str, Any] | None, dimension: str, nonce: int) -> dict[str, Any]:
    """A deterministic alternative articulation (or dynamic shape): the nonce picks the first preset that differs."""
    presets = _ART_PRESETS if dimension == "articulation" else _DYN_PRESETS
    cur = list((current or {}).get(dimension) or [])
    for k in range(len(presets)):
        cand = presets[(max(0, nonce) + k) % len(presets)]
        if cand != cur:
            return {dimension: [dict(r) for r in cand], "mode": "replace", "vary": "", "raw": f"different {dimension}"}
    return {dimension: [dict(r) for r in presets[0]], "mode": "replace", "vary": "", "raw": f"different {dimension}"}


# ---------------------------------------------------------------- roles and positions


def _beats_per_bar(meter: str) -> Fraction:
    return Fraction({"3/4": 3, "6/8": 3, "2/4": 2}.get(str(meter or "4/4"), 4))


def note_onsets(ex: Any) -> list[Fraction]:
    """Onset (in beats) of each note, from the exercise's own rhythm events (or its rhythm symbols)."""
    n = len(ex.notes)
    out: list[Fraction] = [Fraction(-1)] * n
    for e in ex.rhythm_events or []:
        if e.get("rest") or e.get("n") is None:
            continue
        try:
            i = int(e["n"])
            if 0 <= i < n:
                out[i] = Fraction(str(e.get("on")))
        except Exception:
            continue
    if all(o >= 0 for o in out) and n:
        return out
    try:
        from improvisation_motif import _RHYTHM_BEATS

        t, res = Fraction(0), []
        for i in range(n):
            res.append(t)
            sym = ex.rhythm_symbols[i] if i < len(ex.rhythm_symbols) else "♩"
            t += Fraction(float(_RHYTHM_BEATS.get(sym, 1.0))).limit_denominator(8)
        return res
    except Exception:
        return [Fraction(i) for i in range(n)]


def role_indices(ex: Any, role: str) -> list[int]:
    """Note indexes for a semantic role, from the exercise's own role metadata (never from note names)."""
    n = len(ex.notes)
    chord_roles = list(ex.chord_roles or [""] * n)
    midi = list(ex.midi)
    onsets = note_onsets(ex)
    bar = _beats_per_bar(ex.meter)
    if "&" in role:
        sets = [set(role_indices(ex, r)) for r in role.split("&")]
        return sorted(set.intersection(*sets)) if sets else []
    if role == "guide_tone":
        return [i for i, r in enumerate(chord_roles) if r in ("3", "7")]
    if role in ("chord_tone", "target"):
        return [i for i, r in enumerate(chord_roles) if r]
    if role == "destination":
        last_in_bar: dict[int, int] = {}
        for i, o in enumerate(onsets):
            last_in_bar[int(o // bar)] = i
        idx = set(last_in_bar.values())
        idx.add(n - 1)
        return sorted(i for i in idx if 0 <= i < n)
    if role in ("tension", "approach", "resolution"):
        tension = [i for i, r in enumerate(chord_roles) if not r]
        if role == "tension":
            return tension
        if role == "approach":
            return [i for i in tension if i + 1 < n and chord_roles[i + 1] and abs(midi[i + 1] - midi[i]) <= 2]
        return [i for i in range(1, n) if chord_roles[i] and not chord_roles[i - 1]]
    if role == "downbeat":
        return [i for i, o in enumerate(onsets) if o % bar == 0]
    return []


# ---------------------------------------------------------------- applying


def clear_expression(ex: Any) -> None:
    n = len(ex.notes)
    ex.articulation, ex.accents, ex.slur_groups = [""] * n, [False] * n, [0] * n
    ex.dynamics, ex.dynamic_marks, ex.expression = [""] * n, [], {}


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


def apply_expression(ex: Any, request: dict[str, Any] | None, *, source: dict[str, str] | None = None) -> None:
    """Compute and attach per-note articulation / accents / slurs / dynamics from ``request`` (deterministic)."""
    clear_expression(ex)
    request = {"articulation": list((request or {}).get("articulation") or []), "dynamics": list((request or {}).get("dynamics") or []),
               "raw": (request or {}).get("raw", "")}
    n = len(ex.notes)
    if not n or not (request["articulation"] or request["dynamics"]):
        ex.expression = {"request": request, "rules_applied": [], "roles_used": {}, "unmatched": [], "summary": {"articulation": "", "dynamics": ""},
                         "source": dict(source or {}), "capability": ABC_CAPABILITY, "attached_by": "note_index"}
        return
    onsets, bar = note_onsets(ex), _beats_per_bar(ex.meter)
    art, acc, slur = [""] * n, [False] * n, [0] * n
    applied: list[dict[str, Any]] = []
    roles_used: dict[str, int] = {}
    unmatched: list[str] = []
    art_text: list[str] = []
    next_slur = 1

    def mark(indices: list[int], what: str) -> None:
        for i in indices:
            if what == "accent":
                acc[i] = True
            elif what in ("staccato", "tenuto", "tongued"):
                art[i] = what

    def new_slurs(groups: list[list[int]]) -> int:
        nonlocal next_slur
        made = 0
        for g in groups:
            if len(g) >= 2:
                for i in g:
                    slur[i] = next_slur
                next_slur += 1
                made += 1
        return made

    for rule in request["articulation"]:
        kind = rule.get("rule")
        if kind == "all":
            mark(list(range(n)), rule["art"])
            applied.append({"rule": kind, "art": rule["art"], "notes": n})
            art_text.append(rule["art"])
        elif kind == "legato":
            bars_idx: dict[int, list[int]] = {}
            for i, o in enumerate(onsets):
                bars_idx.setdefault(int(o // bar), []).append(i)
            made = new_slurs(list(bars_idx.values()))
            applied.append({"rule": kind, "slurs": made})
            art_text.append("legato, slurred within each bar")
        elif kind == "slur_groups":
            size = int(rule.get("size", 2))
            made = new_slurs([list(range(i, min(n, i + size))) for i in range(0, n, size)])
            applied.append({"rule": kind, "size": size, "slurs": made})
            art_text.append({2: "two-note", 3: "three-note", 4: "four-note", 5: "five-note"}.get(size, f"{size}-note") + " slurs")
        elif kind == "alternate":
            groups = [list(range(i, min(n, i + 2))) for i in range(0, n, 2)]
            slurred = [g for k, g in enumerate(groups) if k % 2 == 1]
            new_slurs(slurred)
            for k, g in enumerate(groups):
                if k % 2 == 0:
                    mark(g, "tongued")
            applied.append({"rule": kind, "tongued_pairs": len(groups) - len(slurred), "slurred_pairs": len(slurred)})
            art_text.append("alternating tongued and slurred pairs")
        elif kind == "every_nth":
            nth = max(1, int(rule.get("n", 2)))
            idx = list(range(nth - 1, n, nth))
            mark(idx, rule.get("mark", "accent"))
            applied.append({"rule": kind, "n": nth, "notes": idx})
            art_text.append(f"{rule.get('mark', 'accent')} on every {nth}{'nd' if nth == 2 else 'rd' if nth == 3 else 'th'} note")
        elif kind == "beat":
            beat = int(rule.get("beat", 1))
            idx = [i for i, o in enumerate(onsets) if o % bar == beat - 1]
            mark(idx, rule.get("mark", "accent"))
            applied.append({"rule": kind, "beat": beat, "notes": idx})
            art_text.append(f"{rule.get('mark', 'accent')} on beat {beat}" + ("" if idx else " (no note falls there)"))
            if not idx:
                unmatched.append(f"beat {beat}")
        elif kind == "position":
            idx = [0] if rule.get("which") == "first" else [n - 1]
            mark(idx, rule.get("mark", "accent"))
            applied.append({"rule": kind, "which": rule.get("which"), "notes": idx})
            art_text.append(f"{rule.get('mark', 'accent')} on the {rule.get('which')} note")
        elif kind == "role":
            role = rule["role"]
            idx = role_indices(ex, role)
            label = " ".join(_ROLE_LABEL.get(r, r) for r in role.split("&")) if "&" not in role else "guide-tone destinations"
            if not idx:
                unmatched.append(label)
                applied.append({"rule": kind, "role": role, "notes": [], "matched": False})
                art_text.append(f"{rule.get('mark')} on {label} (none in this line)")
                continue
            mark(idx, rule.get("mark", "accent"))
            roles_used[label] = len(idx)
            applied.append({"rule": kind, "role": role, "mark": rule.get("mark"), "notes": idx, "matched": True})
            art_text.append(f"{rule.get('mark')} on {label} ({len(idx)} note{_plural(len(idx))})")

    # ---- dynamics: per-note effective level + notated marks ------------------------------------------------------
    level_idx: list[int | None] = [None] * n
    marks: list[dict[str, Any]] = []
    dyn_text: list[str] = []
    hairpin_interior: set[int] = set()
    dyn_map: dict[str, Any] = {}
    for rule in request["dynamics"]:
        kind = rule.get("rule")
        if kind == "level":
            lv = LEVELS.index(rule["level"])
            level_idx = [lv] * n
            marks.append({"type": "level", "at": 0, "level": rule["level"]})
            dyn_text.append(rule["level"])
            applied.append({"rule": kind, "level": rule["level"]})
        elif kind in ("ramp", "hairpin"):
            a, b = (rule["from"], rule["to"]) if kind == "ramp" else (_DEFAULT_CRESC if rule["dir"] == "crescendo" else _DEFAULT_DIM)
            ia, ib = LEVELS.index(a), LEVELS.index(b)
            direction = "crescendo" if ib > ia else ("diminuendo" if ib < ia else "level")
            level_idx = [ia if n == 1 else int(round(ia + (ib - ia) * i / (n - 1))) for i in range(n)]
            if n >= 2 and direction != "level":
                marks.append({"type": "level", "at": 0, "level": a})
                marks.append({"type": "hairpin", "dir": direction, "start": 0, "end": n - 1, "from": a, "to": b})
                marks.append({"type": "level", "at": n - 1, "level": b})
                hairpin_interior = set(range(1, n - 1))
            else:
                marks.append({"type": "level", "at": 0, "level": a})
            dyn_text.append(f"{a} → {b} {direction}" if direction != "level" else a)
            applied.append({"rule": kind, "from": a, "to": b, "direction": direction})
        elif kind == "bars":
            levels = [lv for lv in rule.get("levels", []) if lv in LEVELS]
            if levels:
                bar_of = [int(o // bar) for o in onsets]
                first_seen: dict[int, int] = {}
                for i, bi in enumerate(bar_of):
                    first_seen.setdefault(bi, i)
                ordered = sorted(first_seen)
                for rank, bi in enumerate(ordered):
                    lv = levels[min(rank, len(levels) - 1)]
                    for i, b2 in enumerate(bar_of):
                        if b2 == bi:
                            level_idx[i] = LEVELS.index(lv)
                    marks.append({"type": "level", "at": first_seen[bi], "level": lv})
                dyn_text.append(", then ".join(levels[: len(ordered)]) + (" by bar" if len(ordered) > 1 else ""))
                applied.append({"rule": kind, "levels": levels, "bars": len(ordered)})
    deltas = [r for r in request["dynamics"] if r.get("rule") == "role_delta"]
    if deltas:
        if all(v is None for v in level_idx):
            level_idx = [LEVELS.index("mf")] * n
            marks.insert(0, {"type": "level", "at": 0, "level": "mf"})
        for rule in deltas:
            role = rule["role"]
            idx = role_indices(ex, role)
            label = _ROLE_LABEL.get(role, role) if "&" not in role else "guide-tone destinations"
            if not idx:
                unmatched.append(label)
                applied.append({"rule": "role_delta", "role": role, "notes": [], "matched": False})
                dyn_text.append(f"{label} {'louder' if rule['delta'] > 0 else 'softer'} (none in this line)")
                continue
            for i in idx:
                level_idx[i] = max(0, min(len(LEVELS) - 1, (level_idx[i] or 0) + int(rule["delta"])))
            roles_used.setdefault(label, len(idx))
            applied.append({"rule": "role_delta", "role": role, "delta": rule["delta"], "notes": idx, "matched": True})
            dyn_text.append(f"{label} {'louder' if rule['delta'] > 0 else 'softer'}")
        # notate the per-note changes the role rules introduced (not inside a hairpin)
        prev = None
        have_mark_at = {m["at"] for m in marks if m["type"] == "level"}
        for i in range(n):
            cur = level_idx[i]
            if prev is not None and cur != prev and i not in hairpin_interior and i not in have_mark_at:
                marks.append({"type": "level", "at": i, "level": LEVELS[cur]})
            prev = cur
    marks.sort(key=lambda m: (m.get("at", m.get("start", 0)), 0 if m["type"] == "level" else 1))
    ex.articulation, ex.accents, ex.slur_groups = art, acc, slur
    ex.dynamics = [LEVELS[v] if v is not None else "" for v in level_idx]
    ex.dynamic_marks = marks
    dyn_map = {"levels": list(ex.dynamics), "marks": marks}
    ex.expression = {
        "request": request, "rules_applied": applied, "roles_used": roles_used, "unmatched": unmatched,
        "dynamic_map": dyn_map, "summary": {"articulation": "; ".join(art_text), "dynamics": "; ".join(dyn_text)},
        "source": dict(source or {}), "capability": ABC_CAPABILITY, "attached_by": "note_index",
    }


# ---------------------------------------------------------------- notation


def expression_abc(ex: Any) -> dict[str, Any]:
    """Positional ABC decorations derived from the exercise's expression data (the ABC is output only)."""
    n = len(ex.notes)
    pre = [""] * n
    opens, closes = [False] * n, [False] * n
    if not n:
        return {}
    for m in ex.dynamic_marks or []:
        if m["type"] == "level":
            pre[m["at"]] += f"!{m['level']}!"
        elif m["type"] == "hairpin":
            d = m["dir"]
            pre[m["start"]] += f"!{d}(!"
            pre[m["end"]] += f"!{d})!"
    for i in range(n):
        if i < len(ex.accents) and ex.accents[i]:
            pre[i] += "!accent!"
        a = ex.articulation[i] if i < len(ex.articulation) else ""
        if a == "tenuto":
            pre[i] += "!tenuto!"
        elif a == "staccato":
            pre[i] += "."
    groups: dict[int, list[int]] = {}
    for i, g in enumerate(ex.slur_groups or []):
        if g:
            groups.setdefault(g, []).append(i)
    for members in groups.values():
        if len(members) >= 2:
            opens[min(members)] = True
            closes[max(members)] = True
    if not any(pre) and not any(opens):
        return {}
    return {"pre": pre, "slur_open": opens, "slur_close": closes}


def summary_lines(ex: Any, *, instrument_family: str = "") -> list[str]:
    s = (ex.expression or {}).get("summary") or {}
    out = []
    if s.get("articulation"):
        text = s["articulation"]
        if instrument_family == "guitar":
            text = text.replace("tongued", "picked")
        out.append(f"**Articulation:** {text}")
    if s.get("dynamics"):
        out.append(f"**Dynamics:** {s['dynamics']}")
    unmatched = (ex.expression or {}).get("unmatched") or []
    if unmatched:
        out.append(f"_No {', '.join(dict.fromkeys(unmatched))} in this line, so nothing was marked for that part of the request._")
    if (ex.expression or {}).get("summary") and any((ex.expression["summary"]).values()):
        if "tongued" in (s.get("articulation") or ""):
            out.append("_Tongued notes have no symbol in notation; they show as the unslurred notes._")
    return out
