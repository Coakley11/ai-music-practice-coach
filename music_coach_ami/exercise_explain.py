"""AMI M1b: explain the working scale pattern from its own stored notes — deterministic, no API call, and never a new version.

"Why do those notes work over these chords?", "Which notes are chord tones?", "Show me the guide tones", "Explain the chromatic approaches",
"Why did you use those intervals?", "How would I use this pattern when improvising?"

Every statement is read from what AMI stored when it built the exercise: the notes as written, each note's chord and its role in that chord
(root / third / fifth / seventh / tension), the scale chosen for each chord and why, the recipe (interval shape, approaches, rhythm) and the
approach / anticipation records. Nothing is looked up from memory, so nothing can contradict the notation on screen. A key-based pattern
carries no chords, so it is explained in terms of its scale only.
"""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.exercise_model import GeneratedExercise

WHY, CHORD_TONES, GUIDE_TONES, APPROACHES, INTERVALS, IMPROVISE = "why_notes", "chord_tones", "guide_tones", "approaches", "intervals", "improvising"
LAST_CHANGE = "last_change"

_START = re.compile(r"^(?:(?:please|can you|could you|would you|now|then|and|ok|okay|so)[, ]+)*(?:explain|why|which|show|what|how|tell|list|identify|point out|walk me through|describe)\b")
_ABOUT_IT = re.compile(r"\b(?:this|it|that|these|those|your|my|the (?:exercise|pattern|line|notes?|phrase|lick)|you (?:used|chose|picked|added|played))\b")
_IMPLICIT = re.compile(r"^(?:(?:please|can you|could you|now|then|and|ok|okay)[, ]+)*(?:show|which|list|identify|point out)\b")
_ROLE_NAME = {"R": "root", "3": "third", "5": "fifth", "7": "seventh", "6": "sixth", "9": "ninth", "11": "eleventh", "13": "thirteenth"}
_CHORD_TONE_ROLES = ("R", "3", "5", "7", "6")


def parse_explanation(question: str) -> str:
    """Which explanation was asked for ("" when this is not one). Needs a question word so that "add accents on the guide tones" stays a revision."""
    low = re.sub(r"\s+", " ", str(question or "").lower()).strip(" .!?,;:")
    if not low or len(low.split()) > 22 or not _START.match(low):
        return ""
    # a general question ("What are chromatic approaches?", "How do I improvise over Blue Bossa?") is not about the exercise on screen
    about_it = bool(_ABOUT_IT.search(low)) or bool(_IMPLICIT.match(low))
    if re.search(r"\b(?:reasoning|reasons?|thinking|logic|why)\b.{0,40}\b(?:last|previous|latest|that|the|this) (?:change|revision|edit|update|modification)\b"
                 r"|\bwhat (?:did|have) you (?:just )?(?:change|changed|do|done)\b|\bwhy did you (?:make|do) that\b", low):
        return LAST_CHANGE

    def term(rx: str) -> bool:
        m = re.search(rx, low)
        return bool(m) and (about_it or bool(re.search(r"\b(?:the|your|those|these)\s+(?:\w+\s+)?$", low[: m.start()] + " ")))

    if term(r"\bguide[- ]tones?\b") and not re.search(r"\b(?:add|put|accent|play)\b", low):
        return GUIDE_TONES
    if term(r"\bchord[- ]tones?\b"):
        return CHORD_TONES
    if term(r"\b(?:chromatic|approach(?:es)?|enclosure)\b"):
        return APPROACHES
    if term(r"\bintervals?\b") and re.search(r"\b(?:why|explain|reason|how|chose|use|used|choose)\b", low):
        return INTERVALS
    if re.search(r"\b(?:improvis\w*|solo\w*|use (?:this|it|the pattern|that)|apply (?:this|it))\b", low) and re.search(r"\bhow\b", low) and about_it:
        return IMPROVISE
    if re.search(r"\b(?:notes?|pattern|line|exercise)\b.{0,30}\b(?:work|fit|sound|belong|good)\b|\bwork over\b|\bwhy (?:these|those|the)\b|\breasoning\b", low) \
            and (about_it or low.startswith(("explain", "why"))):
        return WHY
    return ""


# ---------------------------------------------------------------- the stored facts


def _clean(x: object) -> str:
    return str(x or "").strip()


def _notes(ex: GeneratedExercise) -> list[dict[str, Any]]:
    """One record per sounding note, in order: where it is, what it is called on the player's staff, the chord printed over it and its role."""
    rows = [r for r in ex.provenance["written_events"] if _clean(r.get("spelled")) and not _clean(r.get("duration")).lower().startswith("rest")]
    written = list(ex.written.get("notes") or [r["spelled"] for r in rows])
    out = []
    for i, r in enumerate(rows):
        chord_i = ex.chord_assignment[i] if ex.chord_assignment else 0
        out.append({
            "i": i, "bar": int(r.get("bar_index") or 0) + 1, "beat": float(r.get("beat") or 0.0) + 1.0, "name": written[i] if i < len(written) else _clean(r["spelled"]),
            "concert": ex.notes[i], "midi": ex.midi[i], "chord": _clean(r.get("chord")), "concert_chord": ex.chords[chord_i] if ex.chords else "",
            "role": ex.chord_roles[i] if i < len(ex.chord_roles) else "", "tone": _clean(r.get("tone_role")), "degree": ex.roles[i] if i < len(ex.roles) else "",
        })
    return out


def _is_chord_tone(n: dict[str, Any]) -> bool:
    return n["role"] in _CHORD_TONE_ROLES


def _beat_text(beat: float) -> str:
    whole = int(beat)
    return str(whole) if abs(beat - whole) < 1e-6 else f"the “and” of {whole}" if abs(beat - whole - 0.5) < 1e-6 else f"{beat:g}"


def _names(notes: list[dict[str, Any]], limit: int = 12) -> str:
    seen: list[str] = []
    for n in notes:
        if n["name"] not in seen:
            seen.append(n["name"])
    return " ".join(seen[:limit]) + (" …" if len(seen) > limit else "")


def _by_chord(notes: list[dict[str, Any]]) -> list[tuple[str, str, list[dict[str, Any]]]]:
    """[(printed chord, concert chord, its notes)] in order of first appearance; a chord that returns later keeps one entry."""
    order: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for n in notes:
        key = (n["chord"], n["concert_chord"])
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(n)
    return [(a, b, groups[(a, b)]) for a, b in order]


def _bars(notes: list[dict[str, Any]]) -> str:
    bars = sorted({n["bar"] for n in notes})
    return f"bar {bars[0]}" if len(bars) == 1 else (f"bars {bars[0]}–{bars[-1]}" if bars == list(range(bars[0], bars[-1] + 1)) else "bars " + ", ".join(str(b) for b in bars))


def _segment(ex: GeneratedExercise, concert_chord: str) -> dict[str, Any] | None:
    for seg in ex.provenance.get("segments") or []:
        if seg.get("chord") == concert_chord:
            return seg
    return None


def _tone_name(ex: GeneratedExercise, concert_chord: str, role: str) -> str:
    """The chord's third or seventh, spelled for the player's staff."""
    want = {pc for pc, r in sph.chord_tone_roles(concert_chord).items() if r == role}
    if not want:
        return ""
    seg = _segment(ex, concert_chord)
    concert = next((x for x in (seg or {}).get("scale_notes") or [] if sph.pc_of(x) in want), "")
    if not concert:
        from music_theory import spell_note_in_key

        concert = spell_note_in_key(next(iter(want)), "C")
    semis = int(ex.context.transposition_semitones or 0)
    return sph.transpose_spelled(concert, semis) if semis else concert


def _header(ex: GeneratedExercise) -> str:
    c = ex.context
    where = f"{c.song_title} — {c.section}" if c.song_title and c.section else (c.song_title or "this exercise")
    return (f"This is about the exercise on screen: {where}, written for {c.instrument or 'your instrument'} "
            f"(Practice Key {c.concert_key}, {ex.bars} bars, {len(ex.notes)} notes).")


# ---------------------------------------------------------------- explanations


def _why(ex: GeneratedExercise, notes: list[dict[str, Any]], chords: bool) -> list[str]:
    from music_coach_ami import exercise_scale_pattern as esp

    if not chords:
        key = ex.provenance.get("scale_key") or {}
        tonic_triad = [n for n in notes if n["degree"] in ("1", "3", "5")]
        return [f"Every note comes from the **{key.get('tonic')} {key.get('tonality')}** scale ({' '.join(ex.collection_notes)}), your Practice Key's own mode. "
                f"The line starts on scale degree 1 and moves through the scale in the shape set by the recipe; {len(tonic_triad)} of its {len(notes)} notes are "
                "degrees 1, 3 or 5 (the tonic triad).",
                "_This is a key-based pattern: it is not tied to any chord, so I'm not claiming the notes fit particular chords — ask for it “over the chord "
                "changes” to get that._"]
    lines = ["Each chord gets the scale that fits it, so the notes agree with the harmony under them:"]
    for printed, concert, group in _by_chord(notes):
        seg = _segment(ex, concert)
        tones = [n for n in group if _is_chord_tone(n)]
        extras = [n for n in group if not _is_chord_tone(n) and n["tone"] not in ("approach_below", "approach_above", "anticipation")]
        label = f"**{printed}**" + (f" (sounds as {concert})" if printed != concert else "")
        scale = f"{seg['scale']} — {' '.join(seg['scale_notes'])}" if seg else "its scale"
        why = (seg or {}).get("why", "")
        line = f"- {label}, {_bars(group)}: played over the **{scale}** scale" + (f" ({why})" if why else "") + "."
        if tones:
            line += " Chord tones in the line: " + ", ".join(f"{n_} ({_ROLE_NAME.get(r, r)})" for n_, r in
                                                              {(x['name'], x['role']): None for x in tones}) + "."
        if extras:
            line += f" The other notes ({_names(extras)}) are scale tones that connect them."
        lines.append(line)
    strong = [n for n in notes if abs(n["beat"] - round(n["beat"])) < 1e-6 and int(round(n["beat"])) in (1, 3)]
    on_tone = [n for n in strong if _is_chord_tone(n)]
    if strong:
        lines.append(f"On the strong beats (1 and 3), {len(on_tone)} of {len(strong)} notes are chord tones, so the harmony is clearest where the ear listens hardest.")
    lines.extend(esp.describe_recipe(ex)[:2])
    return lines


def _chord_tones(ex: GeneratedExercise, notes: list[dict[str, Any]], chords: bool) -> list[str]:
    if not chords:
        return ["A key-based pattern has no chords attached, so I can't call any note a chord tone. Its notes are degrees of the "
                f"{(ex.provenance.get('scale_key') or {}).get('tonic')} {(ex.provenance.get('scale_key') or {}).get('tonality')} scale; degrees 1, 3 and 5 make "
                "the tonic triad. Ask for the pattern “over the chord changes” to get chord tones."]
    lines = ["Chord tones are the root, third, fifth and seventh of the chord under each note. In this exercise:"]
    for printed, concert, group in _by_chord(notes):
        tones = [n for n in group if _is_chord_tone(n)]
        by_role: dict[str, list[str]] = {}
        for n in tones:
            by_role.setdefault(n["role"], [])
            if n["name"] not in by_role[n["role"]]:
                by_role[n["role"]].append(n["name"])
        listing = "; ".join(f"{_ROLE_NAME[r]} {' / '.join(by_role[r])}" for r in ("R", "3", "5", "7", "6") if r in by_role) or "none of its chord tones appear in this line"
        first = next(iter(tones), None)
        where = f" — the first lands in bar {first['bar']} on {_beat_text(first['beat'])}" if first else ""
        lines.append(f"- **{printed}** ({_bars(group)}): {listing}{where}.")
    return lines


def _guide_tones(ex: GeneratedExercise, notes: list[dict[str, Any]], chords: bool) -> list[str]:
    if not chords:
        return ["Guide tones are the third and seventh of each chord, so they need chords. A key-based pattern has none; ask for the pattern “over the "
                "chord changes” and I'll show them."]
    lines = ["Guide tones are the **third** and **seventh** of each chord: they say whether it is major, minor or dominant, and they move smoothly from chord to chord."]
    for printed, concert, group in _by_chord(notes):
        third, seventh = _tone_name(ex, concert, "3"), _tone_name(ex, concert, "7")
        played = {r: [n for n in group if n["role"] == r] for r in ("3", "7")}
        bits = []
        for role, name, label in (("3", third, "third"), ("7", seventh, "seventh")):
            if not name:
                continue
            hit = played[role][0] if played[role] else None
            bits.append(f"{label} **{name}**" + (f" (you play it in bar {hit['bar']} on {_beat_text(hit['beat'])})" if hit else " (not played in this line)"))
        lines.append(f"- **{printed}**: " + " and ".join(bits) + ".")
    lines.append("To practice them, ask for “accent the guide tones” — I'll mark exactly those notes without changing anything else.")
    return lines


def _approaches(ex: GeneratedExercise, notes: list[dict[str, Any]], chords: bool) -> list[str]:
    from music_coach_ami import exercise_scale_pattern as esp

    r = esp.recipe_of(ex)
    if not r.has_chromatic():
        return ["This exercise has no chromatic approach notes yet. Ask “add chromatic approaches” and I'll put a half-step approach in front of strong-beat "
                "chord tones (as a new version you can undo)."]
    lines = ["A chromatic approach note sits a **half step** away from the note it leads to and resolves straight into it. Because it is outside the scale, "
             "it creates a small tension that the target note releases."]
    lines.extend(esp.describe_recipe(ex))
    app = [n for n in notes if n["tone"] in ("approach_below", "approach_above")]
    if app:
        lines.append(f"In the notation they are the {len(app)} notes marked as approaches in the stored exercise: "
                     + "; ".join(f"{n['name']} in bar {n['bar']} on {_beat_text(n['beat'])}" for n in app[:6]) + (" …" if len(app) > 6 else "") + ".")
    return lines


def _intervals(ex: GeneratedExercise, notes: list[dict[str, Any]], chords: bool) -> list[str]:
    from music_coach_ami import exercise_scale_pattern as esp
    from music_coach_ami.scale_pattern_recipe import CELL_TEXT, SHAPE_NAME

    r = esp.recipe_of(ex)
    shape = SHAPE_NAME.get(r.shape, r.shape)
    cell = CELL_TEXT.get((r.shape, r.tier), "")
    lines = [f"The intervals come from the exercise's recipe: **{shape}** — {cell}. They are counted in scale steps, so the exact size of a "
             "“fourth” or “third” changes a little from scale to scale."]
    sample = [n for n in notes if n["bar"] == notes[0]["bar"]][:4]
    if len(sample) >= 2:
        steps = [sample[k + 1]["midi"] - sample[k]["midi"] for k in range(len(sample) - 1)]
        lines.append("For example, bar " + str(sample[0]["bar"]) + " starts " + " – ".join(n["name"] for n in sample) + ", which moves by "
                     + ", ".join(f"{abs(s)} semitone{'s' if abs(s) != 1 else ''} {'up' if s > 0 else 'down'}" for s in steps) + ".")
    remarks = esp.interval_remarks(ex)
    if remarks:
        lines.append("Note: " + "; ".join(remarks) + ".")
    lines.append("Why this shape: it is the interval vocabulary set by the pattern you asked for (and the level), not a rule of the harmony — say “change it to "
                 "thirds”, “fourths” or “fifths” to hear another.")
    return lines


def _improvise(ex: GeneratedExercise, notes: list[dict[str, Any]], chords: bool) -> list[str]:
    if not chords:
        key = ex.provenance.get("scale_key") or {}
        return [f"This pattern lives in one scale ({key.get('tonic')} {key.get('tonality')}), so use it as a vocabulary drill: play it in every octave you can, "
                "then start it from other scale degrees, and finally choose which cell to use while you improvise in that key.",
                "It doesn't follow chords, so for a solo over changes ask for the “… over the chord changes” version."]
    groups = _by_chord(notes)
    first = groups[0]
    second = groups[1] if len(groups) > 1 else None
    seg = _segment(ex, first[1])
    own = [n for n in first[2] if n["tone"] not in ("approach_below", "approach_above", "anticipation")] or first[2]
    lines = [f"Use it as a map of what to play over each chord. Start with {first[0]} ({seg['scale'] if seg else 'its scale'}): the notes {_names(own, 8)} are what the line plays there."]
    if second:
        lines.append(f"Then connect it to {second[0]}: finish a phrase on a chord tone of {first[0]} and start the next on the nearest chord tone of {second[0]}.")
    lines.append("Practice in three passes: (1) the pattern exactly as written; (2) the same shape, but start each chord from its third or seventh; "
                 "(3) keep only the strong-beat chord tones and fill between them with your own scale steps.")
    third, seventh = _tone_name(ex, first[1], "3"), _tone_name(ex, first[1], "7")
    if third and seventh:
        lines.append(f"Aim your phrases at the guide tones — for {first[0]} that's {third} and {seventh}. "
                     "Say “accent the guide tones” and I'll mark them in this exercise so you can hear it.")
    return lines


def _last_change(ex: GeneratedExercise, notes: list[dict[str, Any]], chords: bool, label: str = "", tempo: int = 0, first: bool = False) -> list[str]:
    """What the most recent version changed and why — read from the transform record stored with the version."""
    from music_coach_ami import exercise_scale_pattern as esp

    t = ex.transform or {}
    said = _clean(t.get("utterance"))
    if first or (not said and not label):
        return ["This is the first version of the exercise, so nothing has been changed yet. Ask for a change (for example “change it to fourths”) and I'll "
                "explain what it did."]
    if label and said and label != said:
        return [f"Your last request was “{label}”.", f"It changed only the tempo{f' (now {tempo} BPM)' if tempo else ''}: the notes, rhythm, articulation, key and chords are exactly as before."]
    lines = [f"Your last request was “{said or label}”."]
    ad = ex.provenance.get("adaptation") or {}
    if ad.get("kind") == "instrument":
        how = {"kept": "every note keeps its sounding pitch", "octave": f"the whole line moved {abs(int(ad.get('octave_shift') or 0))} octave(s) "
               f"{'up' if int(ad.get('octave_shift') or 0) > 0 else 'down'} so it fits the new range",
               "revoiced": "the sounding line didn't fit the new range at any octave, so the same pattern was rebuilt in its register"}.get(ad.get("how"), "")
        lines.append(f"It moved the exercise from {ad.get('from')} to {ad.get('to')}: {how}. Only the written key and note names differ for the player; the rhythm, "
                     "chords and markings are the same.")
    elif ad.get("kind") == "section":
        lines.append(f"It rebuilt the same pattern on {ad.get('to')} instead of {ad.get('from')}: every note is now chosen from the scale of the chord it sits on in the new "
                     "section, with that section's own chord durations.")
    else:
        changes = t.get("recipe_changes") or []
        if changes:
            lines.append("What it did: " + "; ".join(str(c) for c in changes) + ".")
        lines.extend(esp.describe_recipe(ex))
    if t.get("changed"):
        lines.append("Changed: " + ", ".join(str(c) for c in t["changed"]) + ".")
    if t.get("inherited"):
        lines.append("Kept: " + ", ".join(str(c) for c in t["inherited"]) + ".")
    lines.append("Say “undo that” to hear the version before it.")
    return lines


_DISPATCH = {WHY: _why, CHORD_TONES: _chord_tones, GUIDE_TONES: _guide_tones, APPROACHES: _approaches, INTERVALS: _intervals, IMPROVISE: _improvise}  # LAST_CHANGE is handled in explain()
_TITLE = {WHY: "Why these notes work", CHORD_TONES: "The chord tones in this exercise", GUIDE_TONES: "The guide tones", APPROACHES: "The chromatic approaches",
          INTERVALS: "The intervals", IMPROVISE: "Using this when improvising", LAST_CHANGE: "What the last change did"}


def explain(ex: GeneratedExercise, kind: str, *, label: str = "", tempo: int = 0, first: bool = False) -> dict[str, Any]:
    """The explanation as answer text. Reads only the stored exercise; the caller must not store a new version."""
    from music_coach_ami import exercise_scale_pattern as esp

    notes = _notes(ex)
    chords = esp.kind_of(ex) == esp.KIND_CHORDS
    body = _last_change(ex, notes, chords, label, tempo, first) if kind == LAST_CHANGE else _DISPATCH[kind](ex, notes, chords)
    return {
        "direct_answer": f"**{_TITLE[kind]}**\n\n{_header(ex)}",
        "practice_steps": body,
        "what_to_listen_for": [],
        "next_action": "Your exercise is unchanged. Ask for another change, or “undo that” / “redo” to move through its versions.",
        "kind": kind,
    }
