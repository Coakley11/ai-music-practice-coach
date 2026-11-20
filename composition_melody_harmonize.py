"""Harmonize an accepted Composition melody into chord progression candidates.

Used when the user writes Melody before Chords. Style + feeling still control
how the melody is harmonized; important melody pitches constrain chord choices.
"""

from __future__ import annotations

from typing import Any

from custom_progression_lab import format_entries_bar_line

from composition_chord_suggestions import symbols_to_entries


def _beats_per_bar(meter: str) -> float:
    raw = str(meter or "4/4")
    try:
        num, _den = raw.split("/", 1)
        return max(1.0, float(num))
    except Exception:
        return 4.0


def _pitch_class(ev: dict[str, Any]) -> int | None:
    if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
        return None
    try:
        if ev.get("midi") is not None:
            return int(ev["midi"]) % 12
    except (TypeError, ValueError):
        pass
    pitch = str(ev.get("pitch") or "")
    # Strip octave digits
    name = "".join(ch for ch in pitch if ch.isalpha() or ch in "#b")
    table = {
        "C": 0,
        "C#": 1,
        "Db": 1,
        "D": 2,
        "D#": 3,
        "Eb": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "Gb": 6,
        "G": 7,
        "G#": 8,
        "Ab": 8,
        "A": 9,
        "A#": 10,
        "Bb": 10,
        "B": 11,
    }
    return table.get(name)


def _key_tonic_pc(key: str) -> int:
    k = str(key or "C").replace("minor", "").replace("major", "").strip()
    root = k[:-1] if k.endswith("m") else k
    table = {
        "C": 0,
        "C#": 1,
        "Db": 1,
        "D": 2,
        "Eb": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "Gb": 6,
        "G": 7,
        "Ab": 8,
        "A": 9,
        "Bb": 10,
        "B": 11,
    }
    return table.get(root, 0)


def _key_scale_pcs(key: str) -> set[int]:
    """Pitch classes that belong to the key (minor = natural minor plus the raised 7th for V)."""
    text = str(key or "C").strip()
    low = text.lower()
    minor = "minor" in low or (text.endswith("m") and not low.endswith("maj"))
    tonic = _key_tonic_pc(key)
    degrees = (0, 2, 3, 5, 7, 8, 10, 11) if minor else (0, 2, 4, 5, 7, 9, 11)
    return {(tonic + d) % 12 for d in degrees}


# Fit penalty per chord tone outside the key that the melody never sounds. Qualities come from a
# per-style list, not per scale degree, so ties used to pick e.g. Amaj7 (G#) or Am7 (C) as V in D major.
_OUT_OF_KEY_TONE_PENALTY = 0.75


_EXTRA_QUALITY_DEGREES = {
    "sus4": (0, 5, 7), "sus2": (0, 2, 7), "sus": (0, 5, 7), "dim": (0, 3, 6), "aug": (0, 4, 8), "+": (0, 4, 8),
    "m6": (0, 3, 7, 9), "m9": (0, 3, 7, 10, 2), "maj9": (0, 4, 7, 11, 2), "add9": (0, 4, 7, 2), "7sus4": (0, 5, 7, 10),
    "dim7": (0, 3, 6, 9), "13": (0, 4, 7, 10, 9), "m11": (0, 3, 7, 10, 5),
}


def _symbol_tones(symbol: str) -> set[int] | None:
    """Chord tones of a simple symbol, or None when the quality is not recognised (left untouched)."""
    import re

    m = re.match(r"^([A-G][#b]?)([^/]*)", str(symbol or "").strip())
    if not m:
        return None
    root = _key_tonic_pc(m.group(1))
    qual = m.group(2)
    if qual in {"", "m", "m7", "m7b5", "7", "9", "maj7", "6"}:
        return _chord_tone_pcs(root, qual)
    degrees = _EXTRA_QUALITY_DEGREES.get(qual)
    return {(root + d) % 12 for d in degrees} if degrees else None


def _symbol_root_quality(symbol: str) -> tuple[int, str] | None:
    import re

    m = re.match(r"^([A-G][#b]?)([^/]*)", str(symbol or "").strip())
    return (_key_tonic_pc(m.group(1)), m.group(2)) if m else None


def _chromatic_chord_is_justified(symbol: str, next_symbol: str | None) -> bool:
    """Outside-the-key chords that harmony explains by where they go next (not a blanket ban):
    a secondary dominant (E7 -> A), a tritone substitute (Eb7 -> D) or a diminished passing chord (C#dim7 -> D)."""
    this = _symbol_root_quality(symbol)
    nxt = _symbol_root_quality(next_symbol) if next_symbol else None
    if not this or not nxt:
        return False
    root, qual = this
    target = nxt[0]
    dominant = qual in {"", "7", "9", "13", "7sus4"} or qual.startswith("7")
    if dominant and (root - target) % 12 == 7:  # V/x resolving down a fifth
        return True
    if qual in {"7", "9", "13"} and (root - target) % 12 == 1:  # tritone substitute, down a half step
        return True
    if qual in {"dim", "dim7", "m7b5"} and (target - root) % 12 == 1:  # leading-tone diminished passing chord
        return True
    return False


def _clashes_with_melody(tones: set[int], scale: set[int], melody_pcs: set[int]) -> bool:
    """An added chromatic chord tone a half step from a note the melody sounds (C natural under C#)."""
    for t in tones - scale - melody_pcs:
        if ((t + 1) % 12) in melody_pcs or ((t - 1) % 12) in melody_pcs:
            return True
    return False


def _keep_colour_that_fits_melody(
    picked: list[str],
    coloured: list[str],
    groups: list[list[tuple[int, float]]],
    *,
    key: str,
) -> list[str]:
    """Style/feeling colouring runs after the melody fit and never looks at the melody.

    A coloured chord is kept when every tone is in the key or sounded by the melody, or when its outside tones are
    explained by harmonic context (secondary dominant, tritone sub, diminished passing chord) AND do not rub a half
    step against the melody. Otherwise -- e.g. "melancholy" turning A into Am7 under a C# in D major -- the
    melody-fit chord stays. Chromatic harmony is not banned; only unjustified or clashing substitutions are undone.
    """
    if len(picked) != len(coloured):
        return coloured
    scale = _key_scale_pcs(key)
    out: list[str] = []
    for i, (orig, col) in enumerate(zip(picked, coloured)):
        tones = _symbol_tones(col)
        melody_pcs = {pc for pc, _w in (groups[i] if i < len(groups) else [])}
        outside = (tones - scale - melody_pcs) if tones is not None else set()
        if col == orig or tones is None or not outside:
            out.append(col)
            continue
        nxt = coloured[i + 1] if i + 1 < len(coloured) else None
        if _chromatic_chord_is_justified(col, nxt) and not _clashes_with_melody(tones, scale, melody_pcs):
            out.append(col)
        else:
            out.append(orig)
    return out


def _pc_name(pc: int, *, prefer_flats: bool = False) -> str:
    sharp = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    flat = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
    return (flat if prefer_flats else sharp)[int(pc) % 12]


def _strong_pcs_per_bar(
    events: list[dict[str, Any]],
    *,
    meter: str,
) -> list[list[tuple[int, float]]]:
    """Return per-bar list of (pitch_class, weight) from strong/held notes."""
    bar = _beats_per_bar(meter)
    buckets: dict[int, list[tuple[int, float]]] = {}
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        pc = _pitch_class(ev)
        if pc is None:
            continue
        beat = float(ev.get("beat") or 0.0)
        dur = float(ev.get("duration_beats") or 1.0)
        bar_i = int(beat // bar)
        # Strong beat bias + held-note weight
        in_bar = beat % bar
        strong = 2.0 if in_bar < 0.01 or abs(in_bar - 2.0) < 0.01 else 1.0
        weight = strong * max(0.5, dur)
        buckets.setdefault(bar_i, []).append((pc, weight))
    if not buckets:
        return []
    max_bar = max(buckets)
    return [buckets.get(i, []) for i in range(max_bar + 1)]


def _candidate_qualities(style_family: str, feeling: str) -> list[str]:
    fam = str(style_family or "pop")
    feel = str(feeling or "").lower()
    if fam in {"jazz", "bossa", "soul"}:
        quals = ["maj7", "m7", "7", ""]
        if fam == "bossa":
            # Smooth colorful — prefer maj7/m7; less bare dominant up front.
            quals = ["maj7", "m7", "6", "9", "7", ""]
        elif fam == "jazz":
            quals = ["maj7", "m7", "7", "m7b5", ""]
    elif fam == "rock":
        quals = ["", "m", "7"]
    elif fam.startswith("jewish_") and fam != "jewish_pop":
        quals = ["m", "", "7"]
    else:
        quals = ["", "m", "maj7" if feel == "melancholy" else ""]
    # Feeling nudges
    if feel == "tense":
        if fam == "jazz":
            quals = ["7", "m7b5", "m7", ""] + quals
        elif fam == "bossa":
            quals = ["m7", "7", "maj7", ""] + quals
        else:
            quals = ["7", "m7", ""] + quals
    elif feel == "melancholy":
        quals = ["m", "m7", ""] + quals
    elif feel == "uplifting":
        quals = ["", "maj7", ""] + quals
    # Dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for q in quals:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _chord_tone_pcs(root_pc: int, quality: str) -> set[int]:
    q = str(quality or "")
    if q in {"m", "m7", "m7b5"}:
        thirds = {0, 3, 7}
        if "7" in q:
            thirds.add(10)
        if "b5" in q:
            thirds.discard(7)
            thirds.add(6)
    elif q in {"7", "9"}:
        thirds = {0, 4, 7, 10}
        if q == "9":
            thirds.add(2)
    elif q in {"maj7", "6"}:
        thirds = {0, 4, 7}
        if q == "maj7":
            thirds.add(11)
        if q == "6":
            thirds.add(9)
    else:
        thirds = {0, 4, 7}
    return {(root_pc + d) % 12 for d in thirds}


def _pick_chord_for_pcs(
    pcs_weights: list[tuple[int, float]],
    *,
    key: str,
    style_family: str,
    feeling: str,
    prefer_root: int | None = None,
) -> tuple[str, str]:
    """Return (symbol, why_bit)."""
    if not pcs_weights:
        tonic = _pc_name(_key_tonic_pc(key))
        return tonic, f"grounds on {tonic}"
    # Aggregate weight by pitch class
    scores: dict[int, float] = {}
    for pc, w in pcs_weights:
        scores[pc] = scores.get(pc, 0.0) + float(w)
    top_pc = max(scores, key=scores.get)
    quals = _candidate_qualities(style_family, feeling)
    best_sym = _pc_name(top_pc) + (quals[0] if quals else "")
    best_score = -1.0
    best_why = ""
    roots = [top_pc]
    if prefer_root is not None:
        roots = [prefer_root, top_pc]
    # Also try diatonic neighbors relative to key tonic
    tonic = _key_tonic_pc(key)
    for off in (0, 5, 7, 9, 2):  # I IV V vi ii
        roots.append((tonic + off) % 12)
    tried: set[tuple[int, str]] = set()
    scale = _key_scale_pcs(key)
    melody_pcs = {pc for pc, _w in pcs_weights}
    for root in roots:
        for qual in quals:
            key_t = (root, qual)
            if key_t in tried:
                continue
            tried.add(key_t)
            tones = _chord_tone_pcs(root, qual)
            fit = sum(w for pc, w in pcs_weights if pc in tones)
            # A chromatic chord tone is fine when the melody itself sounds it; otherwise prefer the diatonic quality.
            fit -= _OUT_OF_KEY_TONE_PENALTY * len(tones - scale - melody_pcs)
            # Prefer melody note as chord tone (esp. third)
            third = (root + (3 if qual.startswith("m") else 4)) % 12
            if top_pc == third:
                fit += 1.5
            if top_pc == root:
                fit += 1.0
            if fit > best_score:
                best_score = fit
                sym = _pc_name(root) + qual
                role = (
                    "root"
                    if top_pc == root
                    else ("third" if top_pc == third else ("fifth" if top_pc == (root + 7) % 12 else "color tone"))
                )
                best_sym = sym
                best_why = f"{_pc_name(top_pc)} as {role} of {sym}"
    return best_sym, best_why


def harmonize_melody_to_progressions(
    events: list[dict[str, Any]],
    *,
    key: str,
    meter: str = "4/4",
    profile: dict[str, Any] | None = None,
    feeling: str = "",
    limit: int = 2,
) -> list[dict[str, Any]]:
    """Build style-aware chord candidates that fit the given melody events."""
    from composition_song_intent import (
        apply_feeling_chord_bias,
        apply_style_chord_color,
        describe_harmony_from_events,
    )

    profile = profile if isinstance(profile, dict) else {}
    fam = str(profile.get("style_family") or "pop")
    feel = str(feeling or profile.get("harmony_feeling") or "stable")
    bars = _strong_pcs_per_bar(events, meter=meter)
    if not bars:
        return []

    # One harmonic slot per melody bar (capped) so repeats expand the progression.
    n = len(bars)
    slots = min(16, max(1, n))
    chunk = max(1, (n + slots - 1) // slots)
    groups: list[list[tuple[int, float]]] = []
    for i in range(0, n, chunk):
        group: list[tuple[int, float]] = []
        for row in bars[i : i + chunk]:
            group.extend(row)
        if group:
            groups.append(group)
        if len(groups) >= slots:
            break
    if not groups:
        return []
    # Prefer exact one-chord-per-bar when the melody is moderate length.
    if n <= 16:
        groups = []
        for row in bars:
            groups.append(list(row) if row else [])
        # Drop trailing empty bars
        while groups and not groups[-1]:
            groups.pop()
        if not groups:
            return []

    out: list[dict[str, Any]] = []
    for variant in range(max(1, int(limit))):
        symbols: list[str] = []
        why_bits: list[str] = []
        prefer = _key_tonic_pc(key) if variant == 0 else None
        for gi, group in enumerate(groups):
            # Variant 1 leans minor/tense by preferring vi root
            pref = prefer
            if variant == 1 and gi == 0:
                pref = (_key_tonic_pc(key) + 9) % 12
            elif variant == 1 and feel == "tense":
                pref = (_key_tonic_pc(key) + 7) % 12
            sym, bit = _pick_chord_for_pcs(
                group,
                key=key,
                style_family=fam,
                feeling=feel,
                prefer_root=pref,
            )
            symbols.append(sym)
            why_bits.append(bit)
        picked = list(symbols)
        symbols = apply_style_chord_color(symbols, profile, variant=variant)
        symbols = apply_feeling_chord_bias(symbols, profile, feeling=feel, variant=variant)
        symbols = _keep_colour_that_fits_melody(picked, symbols, groups, key=key)
        entries = symbols_to_entries(symbols)
        grounded = describe_harmony_from_events(entries, profile=profile)
        fit_line = "; ".join(why_bits[:3])
        why = grounded
        if fit_line:
            why = f"{grounded} Fits the melody ({fit_line})."
        out.append(
            {
                "id": f"melody_fit_{fam}_{feel}_{variant}",
                "name": (
                    "Melody-fit harmony"
                    if variant == 0
                    else ("Melody-fit color" if variant == 1 else "Melody-fit alternate")
                ),
                "why": why,
                "chords": entries,
                "line": format_entries_bar_line(entries),
                "feeling": feel,
                "context": "melody_fit",
                "style_family": fam,
                "intent_profile": {
                    "style_family": fam,
                    "harmony_feeling": feel,
                    "section_goal": profile.get("section_goal"),
                    "from_melody": True,
                },
            }
        )
    return out
