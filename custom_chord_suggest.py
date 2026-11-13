"""Context-aware "Suggested Next Chord" engine for the Custom Progressions editor.

Pure and deterministic: no Streamlit, no I/O, no randomness.

``suggest_next_chord(key, mode, style, section_role, current_chords, previous_sections)``
scores every candidate next chord from

* the key and major/minor mode,
* the style profile (Pop, Jazz, Blues, Rock, Ballad; Soul/R&B, Funk and Bossa map onto these),
* the chords already entered in this section (pattern/cadence/loop continuation,
  dominant resolution, chains of applied dominants, 12-bar blues position),
* the preceding sections (how they ended / opened, harmonic vocabulary), and
* the section's role (Verse, Chorus, Pre-Chorus, Bridge, Intro, Outro/Ending, Solo),
* the bar position inside 4/8/12-bar periods.

Chords are spelled in the key's accidental family (flat keys flat, sharp keys sharp) so the
suggestion matches how the editor stores and displays chords for that key. The explanation is
generated from the chosen chord, the key and the context through
:func:`roman_numeral_analysis.analyze_progression_detailed` and the phrase helpers of
:mod:`composition_harmony_explain`; no text is keyed on a particular example.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from music_theory import split_key_center, spell_note_in_key
from roman_numeral_analysis import _DIATONIC_QUALITY_MAJOR, _DIATONIC_QUALITY_MINOR, _parse_for_analysis

_MAJOR_OFFSETS = {"I": 0, "II": 2, "III": 4, "IV": 5, "V": 7, "VI": 9, "VII": 11}
_NUMERALS = ("VII", "VI", "IV", "V", "III", "II", "I")  # longest-first
_KIND_SUFFIX = {"M": "", "m": "m", "M7": "maj7", "m7": "m7", "7": "7", "hd": "m7b5", "d": "dim", "d7": "dim7"}
_FAMILY = {"M": "M", "M7": "M", "m": "m", "m7": "m", "7": "7", "hd": "d", "d": "d", "d7": "d"}
_KIND_TRIAD_QUALITY = {"major": "M", "minor": "m", "m7": "m7", "maj7": "M7", "dom": "7",
                       "half-dim": "hd", "dim": "d", "aug": "M", "sus": "M", "minmaj7": "m"}

STYLE_ALIASES = {
    "pop": "pop", "soul/r&b": "pop", "r&b": "pop", "soul": "pop", "funk": "pop",
    "jazz": "jazz", "bossa": "jazz", "bossa nova": "jazz",
    "blues": "blues", "rock": "rock", "ballad": "ballad",
}
_SEVENTH_STYLES = {"Soul/R&B", "Funk"}


def _tok(text: str) -> tuple[int, str]:
    """Parse a roman token ("bVII", "ii7", "IM7", "iiø", "V7") into ``(rel, kind)``."""
    s = text.strip()
    alt = 0
    while s and s[0] in "b#":
        alt += -1 if s[0] == "b" else 1
        s = s[1:]
    for n in _NUMERALS:
        if s.upper().startswith(n):
            numeral, rest, upper = s[: len(n)], s[len(n):], s[: len(n)].isupper()
            break
    else:
        raise ValueError(text)
    rel = (_MAJOR_OFFSETS[numeral.upper()] + alt) % 12
    if rest in ("ø", "ø7"):
        kind = "hd"
    elif rest in ("o", "o7"):
        kind = "d"
    elif rest == "M7":
        kind = "M7"
    elif rest == "7":
        kind = "7" if upper else "m7"
    else:
        kind = "M" if upper else "m"
    return rel, kind


# name, tokens, cyclic, {style: weight}
_T = tuple[str, bool, dict]
_TEMPLATES: dict[str, list[tuple[str, bool, dict[str, float]]]] = {
    "major": [
        ("I V vi IV", True, {"pop": 1.0, "rock": 0.6, "ballad": 0.8, "jazz": 0.1}),
        ("I vi IV V", True, {"pop": 0.9, "ballad": 0.9, "rock": 0.4}),
        ("vi IV I V", True, {"pop": 0.9, "ballad": 0.7, "rock": 0.5}),
        ("I IV vi V", True, {"pop": 0.7, "ballad": 0.8}),
        ("I V IV", True, {"pop": 0.6, "rock": 0.9}),
        ("I IV V", True, {"pop": 0.7, "rock": 0.8, "ballad": 0.5}),
        ("I IV V I", False, {"pop": 0.8, "rock": 0.8, "ballad": 0.6}),
        ("I iii IV V", True, {"ballad": 1.0, "pop": 0.5}),
        ("I V vi iii IV I IV V", False, {"ballad": 0.9, "pop": 0.5}),
        ("I bVII IV I", True, {"rock": 1.0, "pop": 0.2}),
        ("I IV bVII IV", True, {"rock": 0.9}),
        ("I bIII IV", True, {"rock": 0.7}),
        ("I bVI bVII I", True, {"rock": 0.8, "pop": 0.2}),
        ("bVII IV I", False, {"rock": 0.7}),
        ("IV V I", False, {"pop": 0.5, "rock": 0.5, "ballad": 0.4}),
        ("ii V I", False, {"jazz": 1.0, "pop": 0.4, "ballad": 0.3}),
        ("iii vi ii V I", False, {"jazz": 0.9}),
        ("I vi ii V", True, {"jazz": 0.9, "pop": 0.4, "ballad": 0.4}),
        ("ii V I vi", False, {"jazz": 0.7}),
    ],
    "minor": [
        ("i bVI bIII bVII", True, {"pop": 1.0, "rock": 0.7, "ballad": 0.9}),
        ("i iv bVII bIII", True, {"pop": 0.7, "rock": 0.7, "ballad": 0.6}),
        ("i bVII bVI V", False, {"pop": 0.7, "rock": 0.9, "ballad": 0.6}),
        ("i bVI bVII i", False, {"pop": 0.6, "rock": 0.8}),
        ("i iv V i", False, {"pop": 0.7, "ballad": 0.7, "rock": 0.5}),
        ("i iv v i", False, {"pop": 0.5, "rock": 0.6, "ballad": 0.5}),
        ("i bVII bVI bVII", True, {"rock": 0.9}),
        ("iiø V7 i", False, {"jazz": 1.0, "pop": 0.3}),
        ("i iv7 bVII7 bIIIM7", False, {"jazz": 0.8}),
        ("i bVI bIII bVII", True, {"jazz": 0.3}),
    ],
}

_BLUES_FORM_MAJOR = ("I7", "I7", "I7", "I7", "IV7", "IV7", "I7", "I7", "V7", "IV7", "I7", "V7")
_BLUES_FORM_MINOR = ("i7", "i7", "i7", "i7", "iv7", "iv7", "i7", "i7", "bVI7", "V7", "i7", "V7")

# base functional transitions (rel of last chord -> [(token, weight)])
_TRANS = {
    "major": {
        0: [("IV", .30), ("V", .24), ("vi", .22), ("ii", .10), ("iii", .05), ("bVII", .05)],
        2: [("V", .55), ("IV", .12), ("vi", .12), ("I", .08), ("iii", .05)],
        4: [("vi", .35), ("IV", .30), ("ii", .15), ("V", .12), ("I", .05)],
        5: [("V", .32), ("I", .28), ("ii", .12), ("vi", .10), ("bVII", .08), ("iv", .06)],
        7: [("I", .30), ("vi", .28), ("IV", .27), ("iii", .05)],
        9: [("IV", .38), ("ii", .17), ("V", .17), ("I", .10), ("iii", .08)],
        11: [("I", .60), ("iii", .20), ("vi", .20)],
        10: [("IV", .38), ("I", .30), ("bVI", .10), ("V", .08)],
        8: [("bVII", .50), ("IV", .15), ("V", .15), ("I", .10)],
        3: [("IV", .50), ("bVI", .20), ("bVII", .20)],
        "_": [("V", .30), ("I", .30), ("IV", .20), ("vi", .10)],
    },
    "minor": {
        0: [("bVI", .26), ("iv", .24), ("bVII", .20), ("bIII", .12), ("V", .08)],
        2: [("V", .70), ("i", .10), ("bVII", .10)],
        3: [("bVII", .35), ("iv", .25), ("bVI", .20), ("i", .10)],
        5: [("V", .28), ("bVII", .25), ("i", .22), ("bVI", .10), ("bIII", .08)],
        7: [("i", .45), ("bVI", .20), ("bIII", .15), ("iv", .10)],
        8: [("bVII", .36), ("bIII", .20), ("iv", .15), ("V", .13), ("i", .10)],
        10: [("i", .35), ("bIII", .30), ("bVI", .15), ("iv", .10)],
        "_": [("i", .40), ("V", .20), ("iv", .20), ("bVII", .10)],
    },
}
_STYLE_EXTRA = {  # (style, mode) -> {last_rel: [(token, weight)]}
    ("jazz", "major"): {
        0: [("ii", .30), ("vi", .22), ("iii", .15), ("IV", .18), ("VI7", .18)],
        2: [("V", .60), ("bII7", .12)],
        4: [("vi", .30), ("VI7", .30)],
        5: [("V", .30), ("iv", .20), ("bVII7", .12)],
        7: [("I", .60), ("vi", .20)],
        9: [("ii", .35), ("II7", .25)],
    },
    ("jazz", "minor"): {
        0: [("iiø", .30), ("iv", .25), ("bVI", .15), ("bVII7", .15)],
        2: [("V7", .90)],
        5: [("bVII7", .30), ("V7", .30)],
        7: [("i", .70)],
    },
    ("rock", "major"): {0: [("bVII", .20), ("bVI", .12)], 10: [("IV", .20)], 8: [("bVII", .20)]},
    ("rock", "minor"): {0: [("bVII", .20)], 8: [("bVII", .20)]},
    ("ballad", "major"): {0: [("iii", .12)], 4: [("IV", .15)]},
}
_STYLE_MULT = {  # style -> {rel: multiplier on all candidates at that rel (major-mode numerals)}
    "rock": {2: 0.5, 4: 0.5, 10: 1.5},
    "ballad": {9: 1.2, 4: 1.3, 5: 1.1},
}

_OPENINGS = {
    ("major", "pop"): {"verse": [("I", .55), ("vi", .18), ("IV", .12), ("ii", .05), ("V", .05), ("iii", .05)],
                       "chorus": [("I", .30), ("IV", .28), ("vi", .25), ("V", .12)],
                       "prechorus": [("vi", .30), ("IV", .30), ("ii", .25), ("I", .10)],
                       "bridge": [("vi", .30), ("IV", .25), ("ii", .15), ("bVI", .10), ("iii", .10), ("V", .10)],
                       "intro": [("I", .50), ("vi", .20), ("IV", .20)],
                       "outro": [("I", .40), ("IV", .30), ("vi", .20)],
                       "solo": [("I", .40), ("vi", .25), ("IV", .25)]},
    ("major", "jazz"): {"_": [("I", .40), ("ii", .32), ("iii", .10), ("vi", .10), ("IV", .08)],
                        "bridge": [("III7", .25), ("vi", .20), ("IV", .20), ("ii", .20), ("bVI", .10)]},
    ("major", "blues"): {"_": [("I7", .90), ("IV7", .10)]},
    ("major", "rock"): {"_": [("I", .50), ("bVII", .15), ("IV", .15), ("vi", .10), ("V", .10)],
                        "chorus": [("IV", .30), ("I", .30), ("bVII", .20), ("V", .20)]},
    ("major", "ballad"): {"_": [("I", .45), ("vi", .20), ("IV", .20), ("iii", .15)],
                          "chorus": [("IV", .30), ("I", .30), ("vi", .25), ("V", .15)]},
    ("minor", "pop"): {"_": [("i", .60), ("bVI", .15), ("iv", .10), ("bIII", .08), ("V", .07)],
                       "chorus": [("bVI", .30), ("i", .30), ("bIII", .20), ("iv", .20)],
                       "bridge": [("bVI", .30), ("bIII", .25), ("iv", .25), ("V", .20)]},
    ("minor", "jazz"): {"_": [("i", .45), ("iiø", .40), ("iv", .15)]},
    ("minor", "blues"): {"_": [("i7", .90), ("iv7", .10)]},
}


def _role_key(section_role: str) -> str:
    s = re.sub(r"[\d\s]+", " ", str(section_role or "").lower()).strip()
    if "pre" in s and "chorus" in s:
        return "prechorus"
    for needle, role in (("chorus", "chorus"), ("verse", "verse"), ("bridge", "bridge"),
                         ("intro", "intro"), ("outro", "outro"), ("ending", "outro"), ("coda", "outro"),
                         ("solo", "solo"), ("instrumental", "solo"), ("refrain", "chorus")):
        if needle in s:
            return role
    return "verse"


def _opening_table(mode: str, style: str, role: str) -> list[tuple[str, float]]:
    table = _OPENINGS.get((mode, style)) or _OPENINGS.get((mode, "pop")) or _OPENINGS[("major", "pop")]
    return table.get(role) or table.get("_") or table.get("verse") or next(iter(table.values()))


def _parse_chord(chord: str, key: str) -> dict[str, Any] | None:
    p = _parse_for_analysis(chord, key)
    if p is None:
        return None
    kind = _KIND_TRIAD_QUALITY.get(p["quality"], "M")
    if kind == "d" and "7" in (p["suffix"] or "") and p["quality"] == "dim":
        kind = "d7"
    return {"rel": p["interval"], "kind": kind, "fam": _FAMILY[kind], "p": p, "chord": str(chord).strip()}


def _match(chord: dict[str, Any], tok: tuple[int, str]) -> float:
    if chord["rel"] != tok[0]:
        return 0.0
    if chord["kind"] == tok[1]:
        return 1.0
    if chord["fam"] == _FAMILY[tok[1]]:
        return 0.9
    if {chord["fam"], _FAMILY[tok[1]]} == {"M", "7"}:
        return 0.6
    return 0.0


def _expand(chords: Iterable[Any]) -> list[str]:
    """Flatten entered chords (``C:2|F:2`` subdivisions, ``%`` holds) into plain symbols."""
    out: list[str] = []
    for raw in chords or ():
        text = str(raw or "").strip()
        if not text or text == "%":
            continue
        try:
            from chord_subdivisions import parse_subdivisions

            subs = parse_subdivisions(text) if ("|" in text or ":" in text) else None
        except Exception:
            subs = None
        if subs:
            out.extend(str(s.chord).strip() for s in subs if str(getattr(s, "chord", "")).strip())
        else:
            out.append(text)
    return out


def _spell_chord(rel: int, kind: str, tonic_pc: int, key: str) -> str:
    return spell_note_in_key((tonic_pc + rel) % 12, key) + _KIND_SUFFIX[kind]


def _final_kind(rel: int, kind: str, style: str, mode: str, sevenths: bool) -> str:
    if style == "jazz":
        if kind == "M":
            return "7" if rel == 7 else "M7"
        if kind == "m":
            return "m7"
    elif style == "blues":
        if kind == "M" and rel in (0, 5, 7):
            return "7"
        if kind == "m" and rel in (0, 5):
            return "m7"
    elif sevenths:
        if kind == "M":
            return "7" if rel == 7 else "M7"
        if kind == "m":
            return "m7"
    return kind


def _is_dominant(c: dict[str, Any]) -> bool:
    return c["kind"] == "7"


class _Cands:
    def __init__(self) -> None:
        self.score: dict[tuple[int, str], float] = {}
        self.tags: dict[tuple[int, str], list[str]] = {}
        self.match_score: dict[tuple[int, str], float] = {}
        self.match_len: dict[tuple[int, str], tuple[int, str, bool, bool]] = {}

    def add(self, rel: int, kind: str, w: float, tag: str = "") -> None:
        k = (rel % 12, kind)
        self.score[k] = self.score.get(k, 0.0) + w
        if tag:
            self.tags.setdefault(k, []).append(tag)


def _diatonic_kind(rel: int, mode: str) -> str | None:
    scale = (0, 2, 4, 5, 7, 9, 11) if mode == "major" else (0, 2, 3, 5, 7, 8, 10)
    if rel not in scale:
        return None
    table = _DIATONIC_QUALITY_MAJOR if mode == "major" else _DIATONIC_QUALITY_MINOR
    q = table[scale.index(rel)]
    return {"major": "M", "minor": "m", "dim": "d"}[q]


def _bars_value(bars: float | None, n: int) -> int:
    try:
        return int(round(float(bars))) if bars is not None else n
    except (TypeError, ValueError):
        return n


def suggest_next_chord(
    key: str,
    mode: str | None = None,
    style: str = "Pop",
    section_role: str = "Verse",
    current_chords: Sequence[Any] = (),
    previous_sections: Sequence[Any] = (),
    *,
    bars: float | None = None,
    max_alternatives: int = 3,
) -> dict[str, Any]:
    """Recommend the next chord. Returns a dict:

    ``chord`` (spelled for the key, or ``None`` when the section looks complete), ``roman``,
    ``reason``, ``alternatives`` (list of ``{chord, roman}``), ``intent`` (continue|tension|resolve),
    ``complete`` (bool), ``position`` (bars entered) and ``role`` / ``style`` actually used.

    ``previous_sections`` is a sequence of chord lists, or ``(name, chord list)`` pairs, in song order.
    ``bars`` is the number of bars already entered (defaults to the chord count).
    """
    tonic, key_mode = split_key_center(str(key or "C").strip() or "C")
    mode = "minor" if str(mode or key_mode).lower().startswith("min") else "major"
    key_token = tonic + ("m" if mode == "minor" else "")
    from roman_numeral_analysis import _root_pc

    tonic_pc = _root_pc(tonic)
    style_raw = str(style or "Pop").strip()
    st = STYLE_ALIASES.get(style_raw.lower(), "pop")
    role = _role_key(section_role)

    chords = _expand(current_chords)
    parsed = [c for c in (_parse_chord(x, key_token) for x in chords) if c]
    syms = [c["chord"] for c in parsed]
    pos = _bars_value(bars, len(parsed)) if parsed or bars else 0
    sevenths = bool(parsed) and sum(1 for c in parsed if c["kind"] in ("M7", "m7", "7")) * 2 > len(parsed)
    sevenths = sevenths or style_raw in _SEVENTH_STYLES
    prev = _previous_info(previous_sections, key_token)

    cands = _Cands()
    last = parsed[-1] if parsed else None
    blues_note: dict[str, Any] = {}
    form = None

    if st == "blues":
        form = [_tok(t) for t in (_BLUES_FORM_MINOR if mode == "minor" else _BLUES_FORM_MAJOR)]

    complete = False
    complete_reason = ""
    if not parsed:
        for t, w in _opening_table(mode, st, role):
            rel, kind = _tok(t)
            w = _opening_adjust(w, rel, role, prev, mode)
            cands.add(rel, kind, w, "opening")
    else:
        # --- section-complete detection (full period reached on a closing chord) ---
        period = 12 if st == "blues" else 8
        if pos >= period and pos % (4 if st != "blues" else 12) == 0:
            closing = last["rel"] == 0 or (st != "blues" and _loop_closed(parsed, mode, st))
            if st == "blues":
                closing = True
            if closing:
                complete = True
                complete_reason = (
                    f"{pos} bars are in place"
                    + (" (one full 12-bar blues chorus)" if st == "blues" else "")
                    + f" and the section ends on {last['chord']}, so it looks complete."
                )
        # --- blues form position ---
        if form is not None:
            _blues_candidates(cands, parsed, form, pos, blues_note)
        # --- templates ---
        _template_candidates(cands, parsed, mode, st)
        # --- base transitions ---
        trans = _TRANS[mode].get(last["rel"], _TRANS[mode]["_"])
        if st == "blues":
            trans = _blues_trans(mode, last)
        scale = 0.6 if st == "blues" and blues_note else 1.0
        for t, w in trans:
            rel, kind = _tok(t)
            m = _STYLE_MULT.get(st, {}).get(rel, 1.0)
            cands.add(rel, kind, w * m * scale, "transition")
        for t, w in _STYLE_EXTRA.get((st, mode), {}).get(last["rel"], []):
            rel, kind = _tok(t)
            cands.add(rel, kind, w, "style")
        # --- dominant resolution / chains of applied dominants ---
        _dominant_candidates(cands, last, mode, st, tonic_pc)
        # --- phrase / role / song-context shaping ---
        _shape(cands, parsed, pos, mode, st, role, prev)

    # --- finalise candidate chords ---
    scored: dict[str, dict[str, Any]] = {}
    last_str = last["chord"] if last else ""
    for (rel, kind), score in cands.score.items():
        fk = _final_kind(rel, kind, st, mode, sevenths)
        if last and last["rel"] == rel and last["fam"] == _FAMILY[fk] and not (st == "blues" and blues_note.get("hold_ok")):
            score *= 0.12
        text = _spell_chord(rel, fk, tonic_pc, key_token)
        if text == last_str:
            score = 0.0
        if score <= 0:
            continue
        row = scored.setdefault(text, {"chord": text, "rel": rel, "kind": fk, "score": 0.0, "tags": []})
        row["score"] += score
        row["tags"].extend(cands.tags.get((rel, kind), []))
        if (rel, kind) in cands.match_len:
            row["match"] = max(row.get("match", (0, "", False, False)), cands.match_len[(rel, kind)])
    ranked = sorted(scored.values(), key=lambda r: (-round(r["score"], 6), r["rel"], r["chord"]))
    if not ranked:  # pragma: no cover - defensive
        ranked = [{"chord": _spell_chord(0, "m" if mode == "minor" else "M", tonic_pc, key_token),
                   "rel": 0, "kind": "m" if mode == "minor" else "M", "score": 1.0, "tags": []}]
    best = ranked[0]
    tail = syms[-3:]
    roman = _roman(tail + [best["chord"]], key_token)
    alternatives = [
        {"chord": r["chord"], "roman": _roman(tail + [r["chord"]], key_token)}
        for r in ranked[1 : 1 + max(0, max_alternatives)]
    ]
    intent = _intent(best, last, mode, tonic_pc, key_token, st)
    reason = _explain(best, tail, key_token, mode, st, role, pos, prev, blues_note, bool(parsed), tonic_pc)
    chord_out: str | None = best["chord"]
    if complete:
        chord_out, roman = None, ""
        alternatives = [{"chord": best["chord"], "roman": _roman(tail + [best["chord"]], key_token)}] + alternatives[:1]
        intent = "resolve"
        reason = (
            complete_reason + f" To keep going, {best['chord']} ({alternatives[0]['roman']}) would lead into what follows."
        )
    return {
        "chord": chord_out,
        "roman": roman,
        "reason": reason,
        "alternatives": alternatives,
        "intent": intent,
        "complete": complete,
        "position": pos,
        "role": role,
        "style": st,
    }


# ---------------------------------------------------------------------------- helpers


def _previous_info(previous_sections: Sequence[Any], key_token: str) -> dict[str, Any]:
    info: dict[str, Any] = {"vocab": set(), "last_end": None, "last_open": None, "any": False, "opens": []}
    for item in previous_sections or ():
        name, chords = "", item
        if isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], (list, tuple)):
            name, chords = item
        parsed = [c for c in (_parse_chord(x, key_token) for x in _expand(chords)) if c]
        if not parsed:
            continue
        info["any"] = True
        info["last_open"] = parsed[0]
        info["last_end"] = parsed[-1]
        info["opens"].append(parsed[0]["rel"])
        info["vocab"].update((c["rel"], c["fam"]) for c in parsed)
    return info


def _opening_adjust(w: float, rel: int, role: str, prev: dict[str, Any], mode: str) -> float:
    if not prev["any"]:
        return w
    end, opened = prev["last_end"], prev["last_open"]
    if end["rel"] == 7 or (end["fam"] == "7" and end["rel"] != 0):
        w *= 1.6 if rel in (0,) else 1.2 if rel in (9, 8, 5) else 1.0  # previous section ended on dominant -> resolve
    if role in ("chorus", "bridge", "prechorus") and rel == opened["rel"]:
        w *= {"chorus": 0.6, "bridge": 0.35, "prechorus": 0.5}[role]  # contrast with the previous opening
    if role == "chorus" and end["rel"] == 7 and rel == 0:
        w *= 1.3
    if role == "bridge" and rel in prev["opens"]:
        w *= 0.7
    return w


def _blues_trans(mode: str, last: dict[str, Any]) -> list[tuple[str, float]]:
    if mode == "minor":
        return {0: [("iv7", .5), ("V7", .2), ("bVI7", .1)], 5: [("i7", .5), ("V7", .25)],
                7: [("iv7", .4), ("i7", .5)], 8: [("V7", .6), ("i7", .2)]}.get(last["rel"], [("i7", .5), ("iv7", .3), ("V7", .2)])
    return {0: [("IV7", .5), ("V7", .2), ("bVII7", .05)], 5: [("I7", .5), ("V7", .25), ("IV7", .0)],
            7: [("IV7", .4), ("I7", .5)], 10: [("IV7", .5), ("I7", .3)]}.get(last["rel"], [("I7", .5), ("IV7", .3), ("V7", .2)])


def _blues_candidates(cands: _Cands, parsed: list[dict[str, Any]], form: list[tuple[int, str]],
                      pos: int, note: dict[str, Any]) -> None:
    n = pos % 12
    last = parsed[-1]
    prior = (pos - 1) % 12
    if last["rel"] != form[prior][0]:
        return
    j = n
    for step in range(12):
        idx = (n + step) % 12
        if form[idx][0] != last["rel"]:
            j = idx
            break
    else:
        return
    # next bar at/after position whose chord differs from the one just entered
    note.update({"bar": n + 1, "form_idx": j, "hold_ok": False, "last_end": _form_segment_end(form, prior)})
    cands.add(form[j][0], form[j][1], 2.0, "blues_form")


def _form_segment_end(form: list[tuple[int, str]], idx: int) -> int:
    end = idx
    while end + 1 < len(form) and form[end + 1][0] == form[idx][0]:
        end += 1
    return end + 1  # 1-based bar number


def _template_candidates(cands: _Cands, parsed: list[dict[str, Any]], mode: str, st: str) -> None:
    n = len(parsed)
    for name, cyclic, weights in _TEMPLATES.get(mode, []):
        tw = weights.get(st, 0.0)
        if tw <= 0:
            continue
        toks = [_tok(t) for t in name.split()]
        L = len(toks)
        best: tuple[float, int, bool, int] | None = None
        for j in range(L):  # j = index of the template token matching the last chord
            for m in range(min(n, L if not cyclic else max(L, n)), 0, -1):
                ok, quality = True, 0.0
                for back in range(m):
                    ti = j - back
                    if ti < 0:
                        if not cyclic:
                            ok = False
                            break
                        ti %= L
                    q = _match(parsed[n - 1 - back], toks[ti])
                    if q <= 0:
                        ok = False
                        break
                    quality += q
                if not ok:
                    continue
                start_aligned = m == n and (j - m + 1 == 0 or (cyclic and (j - m + 1) % L == 0))
                if m == 1 and not start_aligned:
                    continue
                nxt = j + 1
                if nxt >= L and not cyclic:
                    break
                score = tw * (0.3 + 0.35 * (m - 1)) * (quality / m) * (1.5 if start_aligned else 1.0)
                if best is None or score > best[0]:
                    best = (score, m, start_aligned, nxt % L)
                break
        if best is None:
            continue
        score, m, aligned, nxt = best
        rel, kind = toks[nxt]
        cands.add(rel, kind, score, f"template:{name}")
        key = (rel, kind)
        prev_best = cands.match_score.get(key, -1.0)
        if score > prev_best:
            cands.match_score[key] = score
            cands.match_len[key] = (m, name, cyclic, nxt == L - 1)


def _dominant_candidates(cands: _Cands, last: dict[str, Any], mode: str, st: str, tonic_pc: int) -> None:
    if not _is_dominant(last) and not (last["kind"] == "M" and last["rel"] == 7 and st != "blues"):
        return
    if st == "blues":
        return
    r = last["rel"]
    target = (r + 5) % 12
    is_true_dom = _is_dominant(last)
    if r == 7:
        cands.add(0, "m" if mode == "minor" else "M", 0.9 if st == "jazz" else 0.45, "resolve")
        return
    if not is_true_dom:
        return
    dia = _diatonic_kind(target, mode) or "M"
    chain_w = {"jazz": 1.1}.get(st, 0.35)
    res_w = 0.75 if st == "jazz" else 0.9
    cands.add(target, dia if dia != "d" else "m", res_w, "resolve")
    if target != 0 and r != 0:
        cands.add(target, "7", chain_w, "chain")


def _shape(cands: _Cands, parsed: list[dict[str, Any]], pos: int, mode: str, st: str, role: str,
           prev: dict[str, Any]) -> None:
    last = parsed[-1]
    last_bar = pos % 8 == 7 and st != "blues"
    for (rel, kind) in list(cands.score):
        w = cands.score[(rel, kind)]
        mult = 1.0
        dominant_fn = rel == 7 or (rel == 11 and kind in ("d", "d7", "hd"))
        if last_bar and dominant_fn:
            mult *= 1.8
        elif pos % 4 == 3 and dominant_fn and st != "blues":
            mult *= 1.25
        if role in ("bridge", "prechorus") and pos >= 3 and pos % 4 == 3 and dominant_fn:
            mult *= 1.8 if role == "bridge" else 1.6  # lead back into the next section
        if role == "outro" and pos >= 3:
            if rel == 0 and last["rel"] in (5, 7):
                mult *= 2.4
            elif dominant_fn:
                mult *= 0.7
        if pos >= 4 and pos % 8 == 0 and rel == 0 and st != "blues":
            mult *= 1.3  # new period restarts on home
        if prev["any"]:
            if (rel, _FAMILY[kind]) in prev["vocab"]:
                mult *= 1.12
            elif role == "bridge":
                mult *= 1.12
        cands.score[(rel, kind)] = w * mult


def _loop_closed(parsed: list[dict[str, Any]], mode: str, st: str) -> bool:
    """True when the entered chords are a whole number of repeats of a cyclic loop."""
    n = len(parsed)
    for name, cyclic, weights in _TEMPLATES.get(mode, []):
        if not cyclic or weights.get(st, 0) < 0.5:
            continue
        toks = [_tok(t) for t in name.split()]
        L = len(toks)
        if n >= L and n % L == 0 and all(_match(c, toks[i % L]) > 0 for i, c in enumerate(parsed)):
            return True
    return False


def _roman(chords: list[str], key: str) -> str:
    from roman_numeral_analysis import analyze_progression

    rows = analyze_progression(chords, key)
    return rows[-1] if rows else ""


def _intent(best: dict[str, Any], last: dict[str, Any] | None, mode: str, tonic_pc: int, key: str,
            style: str = "pop") -> str:
    rel, kind = best["rel"], best["kind"]
    if rel == 0 and kind in ("M", "m", "M7", "m7") and (last is None or last["rel"] != 0):
        return "resolve" if last is not None else "continue"
    if last is not None and last["fam"] == "7" and last["rel"] != 0 and (last["rel"] + 5) % 12 == rel:
        return "resolve"
    if (kind == "7" and style != "blues") or rel == 7 or (rel == 11 and kind in ("d", "d7", "hd")):
        return "tension"
    if kind == "hd" or (rel == 2 and kind in ("m", "m7")):
        return "tension"
    return "continue"


def _explain(best, tail, key, mode, st, role, pos, prev, blues_note, has_chords, tonic_pc) -> str:
    from composition_harmony_explain import _borrowed_phrase, _family_phrase, progression_roles

    chord = best["chord"]
    chords = tail + [chord]
    rows = progression_roles(chords, key)
    row = rows[-1]
    roman = row["roman"]
    tonic_name = split_key_center(key)[0]
    key_name = f"{tonic_name} {'minor' if mode == 'minor' else 'major'}"
    role_name = {"prechorus": "pre-chorus", "outro": "ending"}.get(role, role)
    parts: list[str] = []

    if not has_chords:
        if best["rel"] == 0:
            parts.append(f"{chord} ({roman}) establishes {key_name} as home to open the {role_name}.")
        else:
            parts.append(
                f"{chord} ({roman}) opens the {role_name} away from the tonic: {_family_phrase(row, mode)}."
                if row["role"] == "diatonic"
                else f"{chord} ({roman}) opens the {role_name} as {_borrowed_phrase(row, mode)}."
            )
        if prev["any"]:
            end, opened = prev["last_end"], prev["last_open"]
            if end["fam"] == "7" or end["rel"] == 7:
                parts.append(f"The previous section ended on {end['chord']} (dominant), so this opening answers it.")
            elif best["rel"] != opened["rel"] and role in ("chorus", "bridge", "prechorus"):
                parts.append(f"It contrasts with the previous section's {opened['chord']} opening.")
        return " ".join(parts)

    prev_row = rows[-2]
    tags = best.get("tags", [])
    if blues_note.get("bar") and any(t == "blues_form" for t in tags):
        seg_end = blues_note["last_end"]
        parts.append(
            f"Bar {blues_note['bar']} of the 12-bar blues: {prev_row['chord']} ({prev_row['roman']}) normally holds "
            f"through bar {seg_end}, then {chord} ({roman}) takes over at bar {blues_note['form_idx'] + 1}."
        )
        parts.append("Set the duration of each chord to match the form.")
        return " ".join(parts)

    prev_target = prev_row.get("target_index")
    if "chain" in tags and prev_row["role"] in ("secondary_dominant", "dominant"):
        path, rel = [], (best["rel"] + 5) % 12
        while rel != 0 and len(path) < 6:
            path.append(_spell_chord(rel, "7", tonic_pc, key))
            rel = (rel + 5) % 12
        path.append(_spell_chord(0, "m" if mode == "minor" else "M", tonic_pc, key))
        parts.append(
            f"{prev_row['chord']} ({prev_row['roman']}) wants to fall a fifth to {chord} ({roman}); "
            f"keeping the chain of dominants going leads home via {', '.join(path)}."
        )
    elif prev_target == len(rows) - 1:
        parts.append(f"{chord} ({roman}) resolves {prev_row['chord']} ({prev_row['roman']}).")
    elif row["role"] == "secondary_dominant":
        parts.append(f"{chord} is {roman}, a secondary dominant that pushes toward its target a fifth below.")
    elif row["role"] == "dominant":
        parts.append(f"{chord} ({roman}) is the dominant and builds tension toward home.")
    elif row["role"] == "diatonic":
        parts.append(f"{chord} ({roman}) is {_family_phrase(row, mode)}.")
    elif row["role"] == "borrowed":
        parts.append(f"{chord} ({roman}) is {_borrowed_phrase(row, mode)}.")
    else:
        parts.append(f"{chord} ({roman}) continues the line.")

    m = best.get("match")
    if m and m[0] >= 2 and any(t.startswith("template:") for t in tags):
        name = m[1]
        names = _template_roman_name(name, key, mode, st)
        parts.append(f"It {'completes' if m[3] else 'continues'} the {names} {'loop' if m[2] else 'pattern'}.")
    if pos % 8 == 7 and st != "blues" and best["rel"] == 7:
        parts.append(f"Bar {pos + 1} of an 8-bar period: a dominant sets up the cadence.")
    elif role in ("bridge", "prechorus") and pos % 4 == 3 and best["rel"] == 7:
        parts.append(f"A {role_name} often closes on the dominant to lead back.")
    elif role == "outro" and best["rel"] == 0:
        parts.append("An ending is best settled on the tonic.")
    return " ".join(parts)


def _template_roman_name(name: str, key: str, mode: str, st: str) -> str:
    return "–".join(name.replace("M7", "maj7").split())
