"""Harmonic explanations generated from the actual chords and key.

Every sentence is derived from :func:`roman_numeral_analysis.analyze_progression_detailed`
(the same labels the suggestion card prints), so chord symbols, Roman numerals and
the explanation cannot disagree. Nothing here is keyed on a suggestion's name.
"""

from __future__ import annotations

from typing import Any

from music_theory import CHROMATIC, normalize_root, split_key_center
from roman_numeral_analysis import (
    _DEGREE_ROMAN,
    _DIATONIC_QUALITY_MAJOR,
    _DIATONIC_QUALITY_MINOR,
    _case_roman,
    _parse_for_analysis,
    analyze_progression_detailed,
)

_DOMINANT_TYPE = {"secondary_dominant", "dominant"}

# Chord quality -> scale-degree quality family (dominant-quality chords are classified elsewhere).
_QUALITY_FAMILY = {"major": "major", "maj7": "major", "minor": "minor", "m7": "minor", "dim": "dim", "half-dim": "dim"}


def _key_name(key: str) -> str:
    tonic, mode = split_key_center(str(key or "C").strip() or "C")
    return f"{tonic} {'minor' if mode == 'minor' else 'major'}"


def infer_key(chords: list[str]) -> str:
    """Best-guess key for a progression when the caller does not know it."""
    syms = [str(c).strip() for c in chords if str(c).strip()]
    if not syms:
        return "C"
    best_key, best_score = "C", float("-inf")
    for mode_suffix in ("", "m"):
        for tonic in CHROMATIC:
            key = tonic + mode_suffix
            rows = analyze_progression_detailed(syms, key)
            score = 0.0
            for r in rows:
                role = r["role"]
                if role in {"diatonic", "dominant"}:
                    score += 2
                elif role == "secondary_dominant":
                    score += 1
                elif role in {"tritone_sub", "leading_tone_dim"}:
                    score += 0.5
                elif role == "borrowed":
                    score -= 0.5
            first, last = rows[0], rows[-1]
            if first.get("degree") == 0 and first.get("alt") == 0:
                score += 3
            if last.get("degree") == 0 and last.get("alt") == 0:
                score += 2
            elif last["role"] == "dominant":
                score += 1.5
            if mode_suffix == "m":
                score -= 0.25
            if score > best_score:
                best_key, best_score = key, score
    return best_key


def _family_phrase(row: dict[str, Any], mode: str) -> str:
    """Short function description for a diatonic chord, from degree and mode."""
    deg = row.get("degree")
    if mode == "minor":
        return {
            0: "the minor tonic, home",
            1: "a predominant chord that leads toward the dominant",
            2: "the relative major, a tonic-family chord",
            3: "subdominant colour that moves away from home",
            4: "the natural-minor v, a dominant-family chord with a softer pull",
            5: "a tonic-family chord (the submediant)",
            6: "the subtonic, which leads back to the tonic or up to III",
        }.get(deg, "a diatonic chord")
    return {
        0: "the home chord",
        1: "a predominant chord that normally leads to V",
        2: "a tonic-family chord that continues the home sound without resolving",
        3: "subdominant colour that moves away from home",
        4: "the dominant, which pulls back to I",
        5: "the relative minor, a tonic-family chord with a softer feel",
        6: "a leading-tone chord with dominant function",
    }.get(deg, "a diatonic chord")


_ORDINAL = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh")


def _diatonic_numeral(row: dict[str, Any], mode: str) -> str:
    """The key's own numeral for this chord's degree (e.g. ``ii7`` for D in C)."""
    table = _DIATONIC_QUALITY_MAJOR if mode == "major" else _DIATONIC_QUALITY_MINOR
    deg = int(row.get("degree") or 0)
    seventh = "7" if row.get("quality") in {"dom", "m7", "maj7"} else ""
    return _case_roman(_DEGREE_ROMAN[deg], table[deg]) + seventh


def _is_minor_seventh_type(row: dict[str, Any]) -> bool:
    return row.get("quality") in {"m7", "half-dim", "minor"}


def _borrowed_phrase(row: dict[str, Any], mode: str) -> str:
    roman = str(row.get("plain_roman") or row.get("roman") or "")
    if mode == "major":
        if row.get("alt") == -1 and row.get("degree") in {2, 5, 6}:
            return "borrowed from the parallel minor (modal mixture)"
        if row.get("alt") == 0 and row.get("degree") == 3 and row.get("quality") in {"minor", "m7"}:
            return "the minor iv borrowed from the parallel minor"
        if row.get("alt") == 0 and row.get("quality") == "dom":
            return "a dominant-quality chord on a diatonic degree (blues/mixolydian colour)"
        if row.get("alt") == -1 and row.get("degree") == 1:
            return "a flat-II colour chord (Neapolitan-style)"
    if row.get("alt") != 0:
        return "a chromatic chord outside the key"
    if roman:
        return "a chord whose quality differs from the key's own scale"
    return "a colour chord"


def progression_roles(chords: list[str], key: str) -> list[dict[str, Any]]:
    """Analysis rows with root pitch classes attached (used by the explainer and tests)."""
    rows = analyze_progression_detailed(chords, key)
    _, key_mode = split_key_center(str(key or "C").strip() or "C")
    table = _DIATONIC_QUALITY_MINOR if key_mode == "minor" else _DIATONIC_QUALITY_MAJOR
    for r in rows:
        p = _parse_for_analysis(r["chord"], key)
        r["root_pc"] = p["root_pc"] if p else None
        r["tonic_pc"] = p["tonic_pc"] if p else None
        # The analysis labels a seventh chord on a diatonic root "diatonic" whatever its
        # quality (Cm7 / Gm7 / Fm7 in C major, Dmaj7 ...). Only the key's own quality on that
        # degree is diatonic; anything else is a colour chord, never "diatonic v7".
        fam = _QUALITY_FAMILY.get(str(r.get("quality") or ""))
        if (
            r.get("role") == "diatonic"
            and r.get("alt") == 0
            and fam is not None
            and (
                fam != table.get(int(r.get("degree") or 0))
                or (r.get("quality") == "maj7" and r.get("degree") == 4 and key_mode != "minor")  # Vmaj7 is not the key's V7
            )
        ):
            r["role"] = "borrowed"
    return rows


def harmonic_identity(chords: list[str], key: str) -> tuple[str, ...]:
    """Fingerprint (context-aware Roman labels) used to compare suggestions."""
    return tuple(r["roman"] for r in analyze_progression_detailed(chords, key))


def explain_progression(chords: list[str], key: str = "", *, max_body: int = 3) -> str:
    """Musician-readable explanation derived from the chords and key.

    ``key`` may be blank, in which case it is inferred from the progression.
    """
    syms = [str(c).strip() for c in chords if str(c).strip()]
    if not syms:
        return "No chords to describe yet."
    key = str(key or "").strip() or infer_key(syms)
    rows = progression_roles(syms, key)
    _, mode = split_key_center(key)
    mode = "minor" if mode == "minor" else "major"
    n = len(rows)

    path = " → ".join(syms[:6]) + (" …" if n > 6 else "")
    sentences_open = []
    first = rows[0]
    if first["role"] == "diatonic" and first.get("degree") == 0:
        what = "the home chord"
    elif first["role"] == "diatonic":
        what = _family_phrase(first, mode)
    elif first["role"] in _DOMINANT_TYPE:
        what = "a dominant-function chord"
    else:
        what = _borrowed_phrase(first, mode)
    sentences_open.append(
        f"In {_key_name(key)}: {path}. Opens on {syms[0]} ({first['roman']}), {what}."
    )

    # Dominant chains: consecutive dominant-type chords each resolving into the next.
    chain_member: dict[int, int] = {}
    chains: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if rows[i]["role"] in _DOMINANT_TYPE:
            j = i
            while (
                j + 1 < n
                and rows[j + 1]["role"] in _DOMINANT_TYPE
                and rows[j]["target_index"] == j + 1
            ):
                j += 1
            if j > i:
                chains.append((i, j))
                for k in range(i, j + 1):
                    chain_member[k] = i
            i = j + 1
        else:
            i += 1

    body: list[tuple[int, int, str]] = []  # (priority, position, sentence)
    handled: set[int] = set()
    for a, b in chains:
        names = " → ".join(syms[a : b + 1])
        romans = " → ".join(rows[k]["roman"] for k in range(a, b + 1))
        if b - a >= 2:
            text = (
                f"{names} is a chain of dominants ({romans}), each resolving down a fifth into the next."
            )
        else:
            first_row = rows[a]
            if first_row["role"] == "secondary_dominant":
                text = (
                    f"{syms[a]} is {first_row['roman']}, a secondary dominant: a major-quality dominant on the "
                    f"{_ORDINAL[int(first_row.get('degree') or 0)]} degree (not the diatonic {_diatonic_numeral(first_row, mode)}) "
                    f"that resolves down a fifth to {syms[b]} ({rows[b]['roman']})."
                )
            else:
                text = f"{names} ({romans}) resolves down a fifth."
        body.append((0, a, text))
        handled.update(range(a, b + 1))

    # Diatonic ii-V (m7 on degree ii leading to the key's own V).
    for i in range(n - 1):
        r = rows[i]
        if (
            i not in handled
            and r["role"] == "diatonic"
            and _is_minor_seventh_type(r)
            and r.get("degree") == 1
            and rows[i + 1]["role"] == "dominant"
        ):
            tail_txt = (
                f" into {syms[i + 2]}"
                if i + 2 < n and rows[i + 1]["target_index"] == i + 2
                else ""
            )
            body.append((0, i, f"{syms[i]} → {syms[i + 1]} is the diatonic ii–V{tail_txt}."))
            handled.update({i, i + 1})

    borrowed_groups: dict[str, tuple[int, list[str]]] = {}
    for i, r in enumerate(rows):
        if i == 0 or i in handled:
            continue
        sym, roman, role = syms[i], r["roman"], r["role"]
        prev = rows[i - 1]
        if role == "secondary_dominant":
            tgt = r["target_roman"]
            if r["target_index"] is not None:
                landing = f"resolving to {syms[r['target_index']]} ({rows[r['target_index']]['roman']})"
            else:
                landing = f"aimed at the {tgt} chord"
            lead = ""
            if _is_minor_seventh_type(prev) and prev.get("root_pc") is not None and r.get("root_pc") is not None \
                    and (prev["root_pc"] + 5) % 12 == r["root_pc"]:
                lead = f"{syms[i - 1]} → {sym} is a ii–V that briefly tonicizes {tgt}: "
            body.append((0, i, f"{lead}{sym} is {roman}, a secondary dominant {landing}."))
        elif role == "tritone_sub":
            nxt = syms[r["target_index"]] if r["target_index"] is not None else "the next chord"
            body.append((0, i, f"{sym} ({roman}) is a tritone substitute for the V7 of {nxt}, resolving down a half step to it."))
        elif role == "leading_tone_dim":
            nxt = syms[r["target_index"]] if r["target_index"] is not None else "the next chord"
            body.append((0, i, f"{sym} ({roman}) is a diminished passing chord leading up a half step into {nxt}."))
        elif role == "borrowed":
            phrase = _borrowed_phrase(r, mode)
            label = f"{sym} ({roman})"
            if phrase in borrowed_groups:
                if label not in borrowed_groups[phrase][1]:
                    borrowed_groups[phrase][1].append(label)
            else:
                borrowed_groups[phrase] = (i, [label])
        elif role == "dominant":
            if r["quality"] == "sus":
                body.append((1, i, f"{sym} ({roman}) suspends the dominant, delaying its resolution."))
            elif i + 1 < n and r["target_index"] == i + 1:
                pass  # covered by the closing/ii–V sentences
        elif role == "diatonic":
            if r.get("degree") == 0:
                continue
            else:
                body.append((1, i, f"{sym} is diatonic {r['roman']}, {_family_phrase(r, mode)}."))
    for phrase, (pos, labels) in borrowed_groups.items():
        subject = " and ".join(labels)
        body.append((0, pos, f"{subject} is {phrase}." if len(labels) == 1 else f"{subject} each is {phrase}."))

    # keep the strongest sentences, in progression order
    body.sort(key=lambda t: (t[0], t[1]))
    picked = sorted(body[:max_body], key=lambda t: t[1])
    # drop duplicate sentences
    seen: set[str] = set()
    parts = list(sentences_open)
    for _, _, text in picked:
        if text in seen:
            continue
        seen.add(text)
        parts.append(text)

    last = rows[-1]
    s_last = syms[-1]
    wraps_to_first = (
        last.get("root_pc") is not None
        and first.get("root_pc") is not None
        and (last["root_pc"] + 5) % 12 == first["root_pc"]
    )
    if last["role"] == "dominant":
        tail = f"Ends on {s_last} ({last['roman']}), the dominant, so it stays open and pulls back to {syms[0]} when it loops."
        if n == 1:
            tail = ""
    elif last["role"] == "secondary_dominant":
        if wraps_to_first and n > 1:
            tail = (
                f"Ends on {s_last} ({last['roman']}), which resolves back down a fifth into the opening "
                f"{syms[0]} ({first['roman']}) when it loops."
            )
        else:
            tail = f"Ends on {s_last} ({last['roman']}), a secondary dominant, so it leaves the ending open."
    elif last["role"] == "diatonic" and last.get("degree") == 0:
        tail = f"Lands home on {s_last} ({last['roman']})." if n > 1 else ""
    elif n > 1:
        tail = f"Ends on {s_last} ({last['roman']}), an open, non-tonic ending."
    else:
        tail = ""
    if tail:
        parts.append(tail)
    return " ".join(p.strip() for p in parts if p.strip())
