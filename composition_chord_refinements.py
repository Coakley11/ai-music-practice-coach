"""Structured chord-refinement proposals for Composition Studio.

Local musical transforms only - never silently mutate the composition.
Each proposal is Preview / Use this / Try another / Dismiss.

Every intent is a *ladder* of candidate transforms. The first candidate that
really changes the progression (and stays playable) is the proposal; "Try
another" walks to the next distinct candidate of the same intent (``variant``).
When no candidate changes anything the result is an honest ``available=False``
proposal - an unchanged progression is never presented as a successful change.

The explanation (``why``) and the chord-by-chord ``changes`` are generated from
the before/after symbols with :mod:`roman_numeral_analysis`, so the text cannot
disagree with the music.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from custom_progression_lab import format_entries_bar_line, is_repeat_entry, normalize_chord_symbol
from music_theory import is_no_chord_token, key_is_minor, split_chord, transpose_chord

from composition_chord_suggestions import symbols_to_entries

CHORD_REFINEMENT_INTENTS: tuple[tuple[str, str], ...] = (
    ("happier", "Make this happier"),
    ("darker", "Make it darker"),
    ("more_tension", "More tension"),
    ("more_resolution", "Stronger resolution"),
    ("surprise", "Surprise chord"),
    ("stronger_lift", "Stronger lift"),
    ("simpler", "Simplify"),
    ("more_emotional", "More emotional"),
)

_NO_CHANGE_MESSAGES: dict[str, str] = {
    "happier": "No brighter version available for this progression.",
    "darker": "No darker version available for this progression.",
    "more_tension": "No further tension available for this progression.",
    "more_resolution": "No stronger resolution available - this progression already resolves clearly.",
    "surprise": "No surprise chord available that differs from this progression.",
    "stronger_lift": "No stronger lift available for this progression.",
    "simpler": "Already as simple as it gets - this progression only uses plain triads.",
    "more_emotional": "No further emotional color available for this progression.",
}

_ROMAN_BASE_RE = re.compile(r"^[♭♯#b]*[IViv]+")


def refinement_intent_label(intent_id: str) -> str:
    for iid, label in CHORD_REFINEMENT_INTENTS:
        if iid == intent_id:
            return label
    return str(intent_id or "Refine")


# --------------------------------------------------------------------------- symbols


def _entry_symbols(entries: list[dict[str, Any]] | None) -> list[str]:
    """Symbols aligned 1:1 with ``entries`` ('%' repeats stay '%', empty -> '')."""
    out: list[str] = []
    for entry in entries or []:
        if isinstance(entry, dict):
            if is_repeat_entry(entry):
                out.append("%")
                continue
            sym = str(entry.get("chord") or "").strip()
        else:
            sym = str(entry or "").strip()
        out.append((normalize_chord_symbol(sym) or sym) if sym else "")
    return out


def _entries_from_symbols(symbols: list[str], template: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if template and len(template) == len(symbols):
        out: list[dict[str, Any]] = []
        for sym, old in zip(symbols, template):
            row = dict(old) if isinstance(old, dict) else {"chord": sym, "bars": 1}
            if sym != "%":
                row["chord"] = sym
            out.append(row)
        return out
    return symbols_to_entries(symbols)


def _resolved(symbols: list[str]) -> list[str]:
    """Sounding chord per entry ('%' repeats the previous chord)."""
    out: list[str] = []
    last = ""
    for sym in symbols:
        if sym == "%":
            out.append(last)
        else:
            out.append(sym)
            if sym:
                last = sym
    return out


def _parts(sym: str) -> tuple[str, str, str]:
    head, _, bass = str(sym or "").partition("/")
    root, suffix = split_chord(head)
    return root, str(suffix or ""), bass


def _join(root: str, suffix: str, bass: str = "") -> str:
    return f"{root}{suffix}" + (f"/{bass}" if bass else "")


def _editable(sym: str) -> bool:
    return bool(sym) and sym != "%" and not is_no_chord_token(sym)


def _root_pc(sym: str) -> int:
    from roman_numeral_analysis import _root_pc as rpc

    root, _, _ = _parts(sym)
    return rpc(root)


def _low(suffix: str) -> str:
    return str(suffix or "").lower()


def _is_dominant(sym: str) -> bool:
    """Plain or extended dominant (7/9/13, possibly altered), not sus/dim/aug/maj/minor."""
    _, suf, _ = _parts(sym)
    low = _low(suf)
    if not low or "maj" in low or "sus" in low or "dim" in low or "aug" in low or "°" in suf:
        return False
    if low.startswith("m") or "m7b5" in low:
        return False
    return bool(re.match(r"^(7|9|11|13)", low))


def _is_minor_quality(sym: str) -> bool:
    _, suf, _ = _parts(sym)
    low = _low(suf)
    return low.startswith("m") and not low.startswith("maj") and "m7b5" not in low


def _is_plain_triad(sym: str) -> bool:
    _, suf, _ = _parts(sym)
    return _low(suf) in ("", "m")


def _tonic_for_key(key: str) -> str:
    text = str(key or "C").strip() or "C"
    if key_is_minor(text):
        root, _ = split_chord(text if text.endswith("m") else f"{text}m")
        return f"{root}m"
    root, _ = split_chord(text.rstrip("m") if text.endswith("m") else text)
    return root


def _tonic_root(key: str) -> str:
    return split_chord(_tonic_for_key(key))[0]


def _dominant_for_key(key: str) -> str:
    return transpose_chord(_tonic_root(key), 7, reference_key=key)


def _subdominant_for_key(key: str) -> str:
    return transpose_chord(_tonic_root(key), 5, reference_key=key)


def _make_majorish(sym: str) -> str:
    root, suffix, bass = _parts(sym)
    low = _low(suffix)
    if low.startswith("m") and not low.startswith("maj") and "m7b5" not in low:
        return _join(root, "", bass)
    if "dim" in low or "ø" in suffix or "m7b5" in low:
        return _join(root, "", bass)
    return sym


def _make_minorish(sym: str) -> str:
    root, suffix, bass = _parts(sym)
    low = _low(suffix)
    if low.startswith("m") and not low.startswith("maj"):
        return sym
    if "maj7" in low:
        return _join(root, "m7", bass)
    if re.match(r"^(7|9|13)", low):
        return _join(root, "m7", bass)
    return _join(root, "m", bass)


def _add_extension(sym: str, *, kind: str) -> str:
    """Kept for callers; ``add9`` colours by chord type, ``7`` adds a seventh."""
    root, suffix, bass = _parts(sym)
    low = _low(suffix)
    if kind == "7":
        if "7" in low or "9" in low:
            return sym
        if low.startswith("m") and not low.startswith("maj"):
            return _join(root, "m7", bass)
        if "maj" in low:
            return _join(root, "maj7", bass)
        return _join(root, "7", bass)
    if kind == "add9":
        return _color_ninth(sym)
    if kind == "sus4":
        if "sus" in low:
            return sym
        return _join(root, "sus4", bass)
    return sym


def _color_ninth(sym: str) -> str:
    """Add a 9th in the way that suits the chord type (no ``D7add9``-style oddities)."""
    root, suffix, bass = _parts(sym)
    low = _low(suffix)
    if "9" in low or "11" in low or "13" in low or "sus" in low or "dim" in low or "alt" in low:
        return sym
    if "maj7" in low:
        return _join(root, "maj9", bass)
    if low == "m7":
        return _join(root, "m9", bass)
    if low == "7":
        return _join(root, "9", bass)
    if low == "m":
        return _join(root, "madd9", bass)
    if low == "":
        return _join(root, "add9", bass)
    return sym


def _playable(sym: str) -> bool:
    try:
        from backing_audio import chord_notes

        return bool(chord_notes(sym))
    except Exception:
        return False


def _audibly_different(a: str, b: str) -> bool:
    if a == b:
        return False
    try:
        from backing_audio import chord_notes

        return list(chord_notes(a)) != list(chord_notes(b))
    except Exception:
        return True


# --------------------------------------------------------------------------- analysis


def _roman_base(roman: str) -> str:
    m = _ROMAN_BASE_RE.match(str(roman or ""))
    return m.group(0) if m else ""


def _loop_next(res: list[str], i: int) -> str | None:
    """The chord after bar i; the last chord wraps to the first (progressions loop),
    so a closing A7 in Dm7 G7 Cmaj7 A7 is V7/ii, matching the Roman line shown."""
    if i + 1 < len(res):
        return res[i + 1]
    return res[0] if len(res) > 1 else None


def functional_label(sym: str, key: str, next_sym: str | None = None) -> str:
    """Roman numeral, upgraded to a secondary-dominant label (V7/V) when the chord
    is a dominant resolving down a fifth to a non-tonic diatonic chord."""
    from roman_numeral_analysis import chord_to_roman

    roman = chord_to_roman(sym, key)
    if not roman or not next_sym or not _editable(next_sym) or not _is_dominant(sym):
        return roman
    pc, npc = _root_pc(sym), _root_pc(next_sym)
    if pc < 0 or npc < 0 or (pc - npc) % 12 != 7:
        return roman
    target = chord_to_roman(next_sym, key)
    base = _roman_base(target)
    if not base or base in ("I", "i"):
        return roman
    if base.startswith(("♭", "♯", "#", "b")):
        return roman
    ext = "7" if "7" in roman or "9" in roman or "13" in roman else ""
    return f"V{ext}/{base}"


# --------------------------------------------------------------------------- candidates
# A candidate is (changes, why_header) where changes = [(index, new_symbol, kind)].

Cand = list[tuple[int, str, str]]


def _dom_indices(res: list[str], syms: list[str]) -> list[int]:
    return [i for i in range(len(syms) - 1, -1, -1) if _editable(syms[i]) and _is_dominant(res[i])]


def _tension_candidates(syms: list[str], res: list[str], key: str) -> list[Cand]:
    out: list[Cand] = []
    doms = _dom_indices(res, syms)
    for i in doms:  # flat 9 on each dominant, last first
        root, suf, bass = _parts(syms[i])
        low = _low(suf)
        if low in ("7", "9", "13", "11"):
            out.append([(i, _join(root, "7b9", bass), "b9")])
    for i in doms:  # tritone substitution
        root, suf, bass = _parts(syms[i])
        sub_root = transpose_chord(root, 6, reference_key=key)
        low = _low(suf)
        new_suf = suf if low in ("7", "9", "13") else "7"
        out.append([(i, _join(sub_root, new_suf, ""), "tritone")])
    for i in doms:  # fully altered after a b9 / #9 already present
        root, suf, bass = _parts(syms[i])
        low = _low(suf)
        if "b9" in low or "#9" in low:
            out.append([(i, _join(root, "7alt", bass), "alt")])
    for i in doms:
        root, suf, bass = _parts(syms[i])
        if _low(suf) in ("7", "9", "13"):
            out.append([(i, _join(root, "7#9", bass), "s9")])
    for i in doms:
        root, suf, bass = _parts(syms[i])
        if _low(suf) in ("7", "9", "13"):
            out.append([(i, _join(root, "7#11", bass), "s11")])
    for i in range(len(syms) - 1, -1, -1):  # colour / suspension on non-dominants
        if not _editable(syms[i]) or _is_dominant(res[i]):
            continue
        root, suf, bass = _parts(syms[i])
        low = _low(suf)
        if low == "maj7":
            out.append([(i, _join(root, "maj7#11", bass), "lydian")])
        elif low == "m":
            out.append([(i, _join(root, "mmaj7", bass), "mmaj7")])
        elif low == "":
            out.append([(i, _join(root, "sus4", bass), "sus4")])
    for i in range(len(syms) - 2, -1, -1):  # secondary dominant of the next chord
        if not _editable(syms[i]) or not _editable(syms[i + 1]):
            continue
        if _is_dominant(res[i]) or "dim" in _low(_parts(syms[i])[1]):
            continue
        nroot = _parts(res[i + 1])[0]
        new = _join(transpose_chord(nroot, 7, reference_key=key), "7")
        out.append([(i, new, "secdom")])
    return out


def _happier_candidates(syms: list[str], res: list[str], key: str) -> list[Cand]:
    out: list[Cand] = []
    for i in range(len(syms) - 1, -1, -1):
        if _editable(syms[i]):
            new = _color_ninth(syms[i]) if _low(_parts(syms[i])[1]) in ("", "maj7") else syms[i]
            if new != syms[i]:
                out.append([(i, new, "bright9")])
    for i in range(len(syms) - 1, -1, -1):
        if _editable(syms[i]) and _low(_parts(syms[i])[1]) == "":
            root, _, bass = _parts(syms[i])
            out.append([(i, _join(root, "6", bass), "sixth")])
    for i in range(len(syms) - 1, -1, -1):
        if _editable(syms[i]) and _is_minor_quality(syms[i]):
            out.append([(i, _make_majorish(syms[i]), "min2maj")])
    return out


def _darker_candidates(syms: list[str], res: list[str], key: str) -> list[Cand]:
    out: list[Cand] = []
    order = [i for i in range(len(syms) - 1, -1, -1) if not _is_dominant(res[i])]
    order += [i for i in range(len(syms) - 1, -1, -1) if _is_dominant(res[i])]
    for i in order:
        if _editable(syms[i]) and not _is_minor_quality(syms[i]) and "dim" not in _low(_parts(syms[i])[1]):
            new = _make_minorish(syms[i])
            if new != syms[i]:
                out.append([(i, new, "maj2min")])
    for i in range(len(syms) - 1, -1, -1):
        if _editable(syms[i]) and _low(_parts(syms[i])[1]) == "m7":
            root, _, bass = _parts(syms[i])
            out.append([(i, _join(root, "m7b5", bass), "halfdim")])
    return out


def _surprise_candidates(syms: list[str], res: list[str], key: str) -> list[Cand]:
    out: list[Cand] = []
    last = len(syms) - 1
    while last >= 0 and not _editable(syms[last]):
        last -= 1
    if last < 0:
        return out
    troot = _tonic_root(key)
    if key_is_minor(key):
        offsets = (8, 1, 5)  # bVI, bII (Phrygian), IV (Dorian)
    else:
        offsets = (10, 8, 3)  # bVII, bVI, bIII (borrowed from the parallel minor)
    for off in offsets:
        out.append([(last, transpose_chord(troot, off, reference_key=key), "borrow")])
    if key_is_minor(key) is False:
        out.append([(last, _join(transpose_chord(troot, 5, reference_key=key), "m"), "borrow")])
    for i in _dom_indices(res, syms):
        root, suf, _ = _parts(syms[i])
        out.append([(i, _join(transpose_chord(root, 6, reference_key=key), suf if _low(suf) else "7"), "tritone")])
    return out


def _resolution_candidates(syms: list[str], res: list[str], key: str) -> list[Cand]:
    out: list[Cand] = []
    minor = key_is_minor(key)
    sevenths = any("7" in _low(_parts(s)[1]) for s in syms if _editable(s))
    maj_flavour = any("maj7" in _low(_parts(s)[1]) for s in syms if _editable(s))
    troot = _tonic_root(key)
    tonic = _join(troot, ("m7" if sevenths else "m") if minor else ("maj7" if maj_flavour else ""))
    last = len(syms) - 1
    while last >= 0 and not _editable(syms[last]):
        last -= 1
    if last < 0:
        return out
    if _root_pc(syms[last]) != _root_pc(tonic) or _is_dominant(syms[last]):
        out.append([(last, tonic, "land_home")])
    elif _low(_parts(syms[last])[1]) != _low(_parts(tonic)[1]):
        pass  # already on the tonic: do not rewrite its colour
    prev = last - 1
    while prev >= 0 and not _editable(syms[prev]):
        prev -= 1
    if prev >= 0 and _root_pc(syms[last]) == _root_pc(tonic) and not _is_dominant(res[prev]):
        dom = _join(_dominant_for_key(key), "7")
        if not (_root_pc(syms[prev]) == _root_pc(dom) and _is_dominant(syms[prev])):
            out.append([(prev, dom, "dom_before_home")])
        sub = _join(_subdominant_for_key(key), "m" if minor else "")
        if _root_pc(syms[prev]) != _root_pc(sub):
            out.append([(prev, sub, "plagal")])
    return out


def _lift_candidates(syms: list[str], res: list[str], key: str) -> list[Cand]:
    out: list[Cand] = []
    sub = _subdominant_for_key(key)
    if key_is_minor(key):
        sub = _join(sub, "m")
    tonic = _tonic_for_key(key)
    idx = [i for i, s in enumerate(syms) if _editable(s)]
    if not idx:
        return out
    first, last = idx[0], idx[-1]
    if len(idx) >= 2:
        out.append([(first, sub, "open_iv"), (last, tonic, "land_home")])
    out.append([(first, sub, "open_iv")])
    dom = _dominant_for_key(key)
    out.append([(last, dom, "pre_lift")])
    return out


def _simpler_candidates(syms: list[str], res: list[str], key: str) -> list[Cand]:
    change: Cand = []
    for i, sym in enumerate(syms):
        if not _editable(sym):
            continue
        root, suffix, _ = _parts(sym)
        low = _low(suffix)
        new = f"{root}m" if low.startswith("m") and not low.startswith("maj") else root
        if new != sym:
            change.append((i, new, "triad"))
    return [change] if change else []


def _emotional_candidates(syms: list[str], res: list[str], key: str) -> list[Cand]:
    out: list[Cand] = []
    idx = [i for i, s in enumerate(syms) if _editable(s)]
    if not idx:
        return out
    second = idx[min(1, len(idx) - 1)]
    inner: Cand = []
    c9 = _color_ninth(syms[second])
    if c9 != syms[second]:
        inner.append((second, c9, "ninth"))
    if len(idx) >= 3 and not key_is_minor(key) and not _is_dominant(res[idx[-2]]):
        pen = idx[-2]
        mn = _make_minorish(syms[pen])
        if mn != syms[pen] and all(pen != c[0] for c in inner):
            inner.append((pen, mn, "soften"))
    if inner:
        out.append(inner)
    for i in reversed(idx):
        c9 = _color_ninth(syms[i])
        if c9 != syms[i]:
            out.append([(i, c9, "ninth")])
    for i in reversed(idx):
        root, suf, bass = _parts(syms[i])
        if _low(suf) == "m":
            out.append([(i, _join(root, "m7", bass), "seventh")])
        elif _low(suf) == "" and not any(_low(_parts(s)[1]) == "maj7" for s in syms if _editable(s)):
            out.append([(i, _join(root, "maj7", bass), "seventh")])
    return out


_BUILDERS: dict[str, Callable[[list[str], list[str], str], list[Cand]]] = {
    "happier": _happier_candidates,
    "darker": _darker_candidates,
    "more_tension": _tension_candidates,
    "more_resolution": _resolution_candidates,
    "surprise": _surprise_candidates,
    "stronger_lift": _lift_candidates,
    "simpler": _simpler_candidates,
    "more_emotional": _emotional_candidates,
}


def _apply(syms: list[str], cand: Cand) -> list[str]:
    out = list(syms)
    for i, new, _kind in cand:
        out[i] = new
    return out


def _valid_candidates(syms: list[str], res: list[str], key: str, intent: str) -> list[tuple[list[str], Cand]]:
    """Distinct candidates that really change the progression and stay playable."""
    seen: set[tuple[str, ...]] = {tuple(syms)}
    valid: list[tuple[list[str], Cand]] = []
    for cand in _BUILDERS[intent](syms, res, key):
        cand = [(i, n, k) for i, n, k in cand if _editable(syms[i]) and _audibly_different(syms[i], n)]
        if not cand:
            continue
        if not all(_playable(n) for _i, n, _k in cand):
            continue
        new = _apply(syms, cand)
        sig = tuple(new)
        if sig in seen:
            continue
        seen.add(sig)
        valid.append((new, cand))
    return valid


# --------------------------------------------------------------------------- explanation


def _target_name(res: list[str], i: int) -> str:
    if i + 1 < len(res) and res[i + 1]:
        return res[i + 1]
    return "the next chord"


def _reason(kind: str, old: str, new: str, key: str, before_res: list[str], after_res: list[str], i: int) -> str:
    from roman_numeral_analysis import chord_to_roman

    fn_old = functional_label(before_res[i], key, _loop_next(before_res, i))
    rn_new = chord_to_roman(after_res[i], key)
    tgt = _target_name(after_res, i)
    old_part = f"{old} ({fn_old})" if fn_old else old
    new_part = f"{new} ({rn_new})" if rn_new else new
    head = f"{old_part} → {new_part}: "
    if kind == "b9":
        return head + f"adds a ♭9, a dissonance outside the key that leans toward {tgt}."
    if kind == "s9":
        return head + f"adds a ♯9 for a bluesy, gritty edge that still wants to resolve toward {tgt}."
    if kind == "s11":
        return head + "adds a ♯11 for a more unsettled, floating dominant sound."
    if kind == "alt":
        return head + "uses the fully altered dominant scale, maximum pull toward resolution."
    if kind == "tritone":
        extra = ""
        if i + 1 < len(after_res) and after_res[i + 1] and _root_pc(after_res[i + 1]) >= 0:
            if (_root_pc(new) - _root_pc(after_res[i + 1])) % 12 == 1:
                extra = f" Its root sits a half step above {after_res[i + 1]}, so the bass slides down into it."
        return head + "tritone substitution: the dominant is swapped for the dominant a tritone away, keeping the same 3rd and 7th." + extra
    if kind == "lydian":
        return head + "adds a ♯11 (Lydian color), a bright but unresolved extra tone."
    if kind == "mmaj7":
        return head + "adds a major 7th over the minor chord, a tense, film-noir color."
    if kind == "sus4":
        return head + "suspends the third with a 4th, so the chord hangs until it resolves."
    if kind == "secdom":
        return head + f"turns the chord into the dominant of {tgt}, a stronger push forward."
    if kind == "min2maj":
        return head + "swaps the minor third for a major third, a brighter color."
    if kind == "bright9":
        return head + "adds an open 9th for a lighter, more airy sound."
    if kind == "sixth":
        return head + "adds a major 6th for a sunnier, relaxed color."
    if kind == "maj2min":
        return head + "lowers the third (major → minor) for a darker color."
    if kind == "halfdim":
        return head + "flattens the 5th (half-diminished) for a darker, more yearning color."
    if kind == "borrow":
        return head + "borrows a chord from outside the key for a surprising turn."
    if kind == "land_home":
        return head + "lands on the home chord for a clear arrival."
    if kind == "dom_before_home":
        return head + "puts the dominant right before home so the last chord arrives with a V→I pull."
    if kind == "plagal":
        return head + "approaches home from the subdominant (plagal 'amen' motion) for a gentler arrival."
    if kind == "open_iv":
        return head + "opens on the subdominant for an immediate lift away from home."
    if kind == "pre_lift":
        return head + "ends on the dominant, setting up the next section to feel like it opens up."
    if kind == "triad":
        return head + "strips the extension back to a plain triad."
    if kind == "ninth":
        return head + "adds a 9th for extra emotional color."
    if kind == "soften":
        return head + "softens the inner chord from major to minor."
    if kind == "seventh":
        return head + "adds a 7th for a richer, more emotional sound."
    return head + "changed."


def _build_changes(
    syms: list[str], proposed: list[str], cand: Cand, key: str
) -> list[dict[str, Any]]:
    before_res = _resolved(syms)
    after_res = _resolved(proposed)
    kinds = {i: k for i, _n, k in cand}
    changes: list[dict[str, Any]] = []
    from roman_numeral_analysis import chord_to_roman

    for i, (a, b) in enumerate(zip(syms, proposed)):
        if a == b:
            continue
        nxt_b = _loop_next(before_res, i)
        nxt_a = _loop_next(after_res, i)
        changes.append(
            {
                "index": i,
                "before": a,
                "after": b,
                "before_roman": functional_label(before_res[i], key, nxt_b),
                "after_roman": functional_label(after_res[i], key, nxt_a) or chord_to_roman(after_res[i], key),
                "kind": kinds.get(i, "changed"),
                "reason": _reason(kinds.get(i, "changed"), a, b, key, before_res, after_res, i),
            }
        )
    return changes


# --------------------------------------------------------------------------- public API


def diff_html_parts(before: list[str], after: list[str]) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]]]:
    """Per-position (symbol, changed) lists so the UI can highlight differences."""
    n = max(len(before), len(after))
    b = [(before[i] if i < len(before) else "", i >= len(before) or i >= len(after) or before[i] != after[i]) for i in range(n)]
    a = [(after[i] if i < len(after) else "", i >= len(before) or i >= len(after) or before[i] != after[i]) for i in range(n)]
    return b, a


def propose_chord_refinement(
    doc: dict[str, Any],
    section: dict[str, Any],
    intent: str,
    *,
    entries: list[dict[str, Any]] | None = None,
    variant: int = 0,
) -> dict[str, Any] | None:
    """Return a proposed progression change without mutating ``doc``.

    ``available`` is False (and ``chords`` equal to the source) when no musically
    appropriate change exists; callers must show ``why`` instead of a success card.
    ``variant`` selects among the distinct candidates of the intent (Try another).
    """
    g = doc.get("global") or {}
    key = str(g.get("original_key_center") or "C")
    intent = str(intent or "").strip().lower()
    if intent not in _BUILDERS:
        return None
    source_entries = list(entries if entries is not None else (section.get("chords") or []))
    syms = _entry_symbols(source_entries)
    if not any(_editable(s) for s in syms):
        return None

    label = str(section.get("label") or "Section")
    name = refinement_intent_label(intent)
    res = _resolved(syms)
    valid = _valid_candidates(syms, res, key, intent)
    base = {
        "intent": intent,
        "name": name,
        "mutates": False,
        "section_id": str(section.get("id") or ""),
        "key": key,
        "source_symbols": list(syms),
        "source_line": format_entries_bar_line(source_entries),
    }
    if not valid:
        return {
            **base,
            "id": f"refine_{intent}_{label.lower()}",
            "available": False,
            "changed": False,
            "why": _NO_CHANGE_MESSAGES[intent],
            "chords": _entries_from_symbols(list(syms), source_entries),
            "line": format_entries_bar_line(source_entries),
            "proposed_symbols": list(syms),
            "changes": [],
            "variant": 0,
            "variant_count": 0,
        }

    v = int(variant or 0) % len(valid)
    proposed, cand = valid[v]
    changes = _build_changes(syms, proposed, cand, key)
    entries_out = _entries_from_symbols(proposed, source_entries)
    why = " ".join(c["reason"] for c in changes)
    pid = f"refine_{intent}_{label.lower()}" + (f"_v{v}" if v else "")
    return {
        **base,
        "id": pid,
        "available": True,
        "changed": True,
        "why": why,
        "chords": entries_out,
        "line": format_entries_bar_line(entries_out),
        "proposed_symbols": list(proposed),
        "changes": changes,
        "variant": v,
        "variant_count": len(valid),
    }


def proposal_is_current(proposal: Any, section_id: str, entries: list[dict[str, Any]] | None, key: str) -> bool:
    """False when a stored proposal belongs to another section, key or progression."""
    if not isinstance(proposal, dict):
        return False
    if str(proposal.get("section_id") or "") != str(section_id or ""):
        return False
    if str(proposal.get("key") or "") != str(key or "C"):
        return False
    return list(proposal.get("source_symbols") or []) == _entry_symbols(entries)


def diff_card_html(proposal: dict[str, Any], show_after: bool = True) -> str:
    """Escaped HTML: before/after bar lines with changed chords highlighted + a change list."""
    import html as _html

    before = list(proposal.get("source_symbols") or [])
    after = list(proposal.get("proposed_symbols") or [])
    b, a = diff_html_parts(before, after)

    def _line(parts: list[tuple[str, bool]], strong: bool) -> str:
        cells = []
        for sym, changed in parts:
            txt = _html.escape(sym or "-")
            if changed:
                style = (
                    "background:rgba(99,102,241,0.22);border-radius:4px;padding:0 4px;font-weight:700;"
                    if strong
                    else "text-decoration:line-through;opacity:0.7;padding:0 4px;"
                )
                cells.append(f'<span style="{style}">{txt}</span>')
            else:
                cells.append(f'<span style="padding:0 4px;opacity:0.85;">{txt}</span>')
        return "|" + "|".join(cells) + "|"

    rows = [f'<div><span style="opacity:0.6">Before</span> {_line(b, False)}</div>']
    if show_after:
        rows.append(f'<div><span style="opacity:0.6">After&nbsp;</span> {_line(a, True)}</div>')
    items = []
    for c in proposal.get("changes") or []:
        items.append(
            "<li><strong>Bar {bar}:</strong> {old} \u2192 <strong>{new}</strong> "
            "<span style=\"opacity:0.7\">({ro} \u2192 {rn})</span><br>{why}</li>".format(
                bar=int(c.get("index", 0)) + 1,
                old=_html.escape(str(c.get("before"))),
                new=_html.escape(str(c.get("after"))),
                ro=_html.escape(str(c.get("before_roman") or "-")),
                rn=_html.escape(str(c.get("after_roman") or "-")),
                why=_html.escape(str(c.get("reason") or "")),
            )
        )
    lst = f'<ul style="margin:6px 0 0 16px;padding:0;font-size:0.85rem;">{"".join(items)}</ul>' if items else ""
    return "".join(rows) + lst
