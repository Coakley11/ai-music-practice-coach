"""Dynamic Practice Focus helper for Missions (MC3.1).

Replaces the fixed per-profile sentence with a short line built from what the player has
actually set up: Level, instrument, Practice Focus, song style, the selected Mission, the
Target Scope (single / 2 / 3 chords) and — for a span — the harmonic relationship and its
real chords (spelled in the player's chart).

At most three short sentences: the focus applied at this level, one concrete harmonic
pointer (actual note names when they help), and one instrument / Mission note. Mission
constraints stay primary; the focus is described as a bias on top of the Mission.
"""

from __future__ import annotations

from typing import Sequence

_JAZZ = {"jazz", "jazz_ballad", "bossa", "blues"}
_LYRICAL = {"ballad", "jazz_ballad", "folk"}
_DRIVING = {"pop", "rock", "funk"}

_KIND = {
    "guide tones": "guide",
    "voice leading": "voicing", "voicings": "voicing", "inversions": "voicing", "comping": "voicing",
    "left-hand patterns": "voicing", "reharmonization": "voicing", "harmony singing": "voicing",
    "triads": "voicing", "double stops": "voicing",
    "articulation": "articulation",
    "dynamics": "dynamics",
    "strumming": "rhythm", "rhythm guitar": "rhythm", "groove": "rhythm", "pocket": "rhythm", "syncopation": "rhythm",
    "pentatonics": "pentatonic",
    "tone": "tone", "breath support": "tone", "breath control": "tone", "vibrato": "tone", "range": "tone",
    "endurance": "tone", "pitch accuracy": "tone",
    "bebop phrasing": "phrasing", "jazz phrasing": "phrasing", "phrasing": "phrasing",
    "emotional delivery": "phrasing", "soloing": "phrasing", "lead guitar": "phrasing",
    "scales": "scales",
    "walking bass": "bassline", "root motion": "bassline",
    "chord transitions": "changes", "barre chords": "changes", "fingerstyle": "changes",
    "ear training": "ear",
}

_RELATION_TEXT = {
    "ii_V_I": "ii–V–I", "minor_ii_V_i": "iiø–V–i", "ii_V": "ii–V", "ii_subV_I": "ii–subV–I", "V_I": "V–I",
    "turnaround": "turnaround", "vamp": "vamp",
}


def focus_kind(focus: str) -> str:
    return _KIND.get(str(focus or "").strip().lower(), "general")


def _family(instrument: str) -> str:
    low = str(instrument or "").lower()
    if any(w in low for w in ("sax", "flute", "clarinet", "trumpet", "trombone", "horn")):
        return "wind"
    for fam in ("guitar", "piano", "bass", "voice"):
        if fam in low:
            return fam
    return "other"


def _gt(chord: str) -> tuple[str, str]:
    try:
        from music_theory import guide_tones_for_chord

        _r, third, seventh = guide_tones_for_chord(str(chord or ""))
        return third, seventh
    except Exception:
        return "", ""


def _pretty(text: str) -> str:
    return str(text or "").replace("b", "♭").replace("#", "♯") if len(str(text or "")) <= 2 else str(text or "")


def _resolution(chords: Sequence[str]) -> str:
    """First 7th → 3rd step across a change, e.g. ``C → B into G7``."""
    for a, b in zip(chords, chords[1:]):
        _t3, s7 = _gt(a)
        t3, _s7 = _gt(b)
        if s7 and t3:
            try:
                from music_theory import pitch_class_from_spelled_note as note_to_pc

                d = (note_to_pc(t3) - note_to_pc(s7)) % 12
                if d in (11, 1, 10, 2, 0):
                    return f"{_pretty(s7)} → {_pretty(t3)} into {b}"
            except Exception:
                return f"{_pretty(s7)} → {_pretty(t3)} into {b}"
    return ""


def _dominant(chords: Sequence[str]) -> str:
    for c in chords:
        head = str(c).split("/")[0]
        if "7" in head and "maj7" not in head and "m7" not in head and "dim" not in head:
            return c
    return ""


def harmonic_context(*, scope: str, chord: str = "", chords: Sequence[str] = (), relationship: str = "") -> str:
    if scope == "single" or not chords:
        return f"on {chord}" if chord else ""
    rel = _RELATION_TEXT.get(relationship, "")
    seq = " → ".join(chords)
    return f"through the {rel} ({seq})" if rel else f"through {seq}"


def focus_guidance(
    *,
    focus: str,
    level: str,
    instrument: str,
    style: str = "default",
    mission: str = "",
    scope: str = "single",
    chord: str = "",
    chords: Sequence[str] = (),
    relationship: str = "",
) -> str:
    """Two or three short sentences of Practice Focus guidance for the current Mission."""
    kind = focus_kind(focus)
    lvl = level if level in ("Beginner", "Intermediate", "Advanced") else "Intermediate"
    fam = _family(instrument)
    sty = str(style or "default").lower()
    jazz = sty in _JAZZ
    where = harmonic_context(scope=scope, chord=chord, chords=chords, relationship=relationship)
    span_chords = list(chords) if chords else ([chord] if chord else [])
    mission_low = str(mission or "").lower()
    rhythm_mission = "rhythm" in mission_low or "syncopat" in mission_low
    out: list[str] = []

    sevenths = [s for c in span_chords for _t, s in [_gt(c)] if s]
    rel_only = (f"through the {_RELATION_TEXT[relationship]}" if relationship in _RELATION_TEXT and scope != "single"
                else ("across the changes" if scope != "single" else (f"on {chord}" if chord else "")))
    if kind == "guide" and rhythm_mission:
        notes = "; ".join(f"{c}: {_pretty(t)}" + (f" & {_pretty(s)}" if s else "") for c in span_chords[:3] for t, s in [_gt(c)] if t)
        out.append(f"Use only the guide tones {rel_only}".strip() + (f" ({notes})" if notes else "") + " as your few pitches.")
        out.append("The Mission is rhythm: repeat one short rhythm and let it carry the idea.")
    elif kind == "guide" and not sevenths:
        notes = "; ".join(f"{c}: {_pretty(t)}" for c in span_chords[:3] for t, _s in [_gt(c)] if t)
        if lvl == "Beginner":
            out.append(f"Find the 3rd of each chord {rel_only}".strip() + (f" ({notes})" if notes else "") + " and land on it when the chord changes.")
        else:
            out.append(f"Connect the 3rds {rel_only}".strip() + (f" ({notes})" if notes else "") + " by the smallest step; add the 6th or 9th as color.")
    elif kind == "guide" and scope == "single":
        t3, s7 = _gt(chord)
        pair = f"{_pretty(t3)} and {_pretty(s7)}"
        if lvl == "Beginner":
            out.append(f"On {chord}, find the 3rd and 7th ({pair}) and hold them as long, easy notes.")
        elif lvl == "Intermediate":
            out.append(f"On {chord}, outline {pair} and let the 7th step down at the end of the phrase.")
        else:
            dom = _dominant([chord])
            out.append(f"On {chord}, frame {pair} with enclosures and add the 9th/13th"
                       + ("; altered ♭9/♯9 only when it resolves." if jazz and dom else "."))
    elif kind == "guide":
        notes = "; ".join(f"{c}: {_pretty(t)} & {_pretty(s)}" for c in span_chords[:3] for t, s in [_gt(c)] if t and s)
        res = _resolution(span_chords)
        if lvl == "Beginner":
            out.append(f"Find the 3rd and 7th of each chord {rel_only if notes else where}".strip() + (f" ({notes})." if notes else "."))
            out.append("Move to the closest one when the chord changes and keep the rhythm easy.")
        elif lvl == "Intermediate":
            out.append(f"Connect 3rds and 7ths {where}".strip() + (f" — for example {res}." if res else " by step."))
            out.append("Then decorate the line, landing a guide tone on each change.")
        else:
            out.append(f"Let each 7th fall to the next 3rd {where}".strip() + (f" ({res})" if res else "") + ", then add 9ths/13ths on top.")
            dom = _dominant(span_chords)
            if jazz and dom:
                out.append(f"Approach the targets with enclosures; altered color (♭9/♯9) on {dom} only where it resolves.")
            else:
                out.append("Approach the targets by half step or enclosure.")
    elif kind == "voicing":
        res = _resolution(span_chords)
        if lvl == "Beginner":
            out.append(f"Play the chord tones {where} and keep common tones where they are.".replace("  ", " "))
        elif lvl == "Intermediate":
            out.append(f"Move each voice to the nearest chord tone {where}".strip() + (f" ({res})." if res else "."))
        else:
            out.append(f"Voice-lead {where} with 3rd/7th shells plus 9/13 on top".strip() + (f" ({res})." if res else "."))
    elif kind == "articulation":
        if lvl == "Beginner":
            out.append("Slur two, tongue two — one simple pattern, the same all the way through; it is written into the notation.")
        elif lvl == "Intermediate":
            out.append("Contrast a slurred phrase with a tongued, detached answer — follow the slurs and dots in the notation.")
        else:
            out.append("Swing articulation: tongue the off-beats, slur into the beat, accent the syncopations." if jazz
                       else "Shape each phrase: slur up to the peak, accent it, detach what falls away.")
    elif kind == "dynamics":
        if lvl == "Beginner":
            out.append("One clear contrast: start soft, then a little louder from the middle — the marks are under the staff.")
        elif lvl == "Intermediate":
            out.append("Crescendo to the high point, then diminuendo to the end of the phrase.")
        else:
            out.append("Give every phrase its own arc and save the loudest moment for the overall peak.")
    elif kind == "rhythm":
        if lvl == "Beginner":
            out.append("Keep a steady pulse and repeat one short rhythm; let the notes stay simple.")
        elif jazz:
            out.append("Swing the eighths and place some notes just before the beat (anticipations).")
        elif sty in _LYRICAL:
            out.append("Keep the pulse calm and leave space; a single anticipation is enough.")
        else:
            out.append("Lock to the groove — mostly on the beat, with one or two off-beat accents.")
    elif kind == "pentatonic":
        if lvl == "Beginner":
            out.append(f"Use the pentatonic that matches each chord's sound {where}, in short fragments.".replace("  ", " "))
        else:
            out.append(f"Pick the pentatonic per chord quality {where}, and change position as the chords move.".replace("  ", " "))
    elif kind == "tone":
        out.append("Long, centered notes first; keep the sound even from low to high." if lvl == "Beginner"
                   else "Keep the tone even through every leap and at phrase ends.")
    elif kind == "phrasing":
        if lvl == "Beginner":
            out.append("Play short phrases with a clear breath between them.")
        elif jazz:
            out.append("Phrase in eighth-note lines that start off the beat and land on a chord tone.")
        else:
            out.append("Shape each phrase as a question and answer, and leave space between them.")
    elif kind == "scales":
        out.append(f"Use the scale of each chord {where}, but start and end on chord tones.".replace("  ", " "))
    elif kind == "bassline":
        out.append(f"Root on beat 1 of each chord {where}" .strip() + (", then walk by step into the next root." if lvl != "Beginner" else "."))
    elif kind == "changes":
        out.append(f"Prepare each change {where} a beat early so the new chord lands exactly on time.".replace("  ", " "))
    elif kind == "ear":
        out.append("Sing the target note of each chord before you play it.")
    else:
        out.append(f"Keep the Mission's idea clear {where}.".replace("  ", " ") if where else "Keep the Mission's idea clear.")

    # Mission first: the focus shapes *how*, never *what* the Mission asks for.
    long_already = len(" ".join(out)) > 170
    if rhythm_mission and kind in ("voicing", "pentatonic", "scales"):
        out.append("This Mission is about rhythm, so keep the pitches to a few notes and let the rhythm carry it.")
    elif long_already or (rhythm_mission and kind == "guide"):
        pass
    elif fam == "wind" and kind not in ("articulation", "dynamics", "tone"):
        out.append("Plan breaths at phrase ends and shape each phrase with your air.")
    elif fam == "guitar" and kind in ("guide", "voicing", "pentatonic", "scales", "phrasing", "general"):
        out.append("Stay in one position so the shapes connect across the changes.")
    elif fam == "piano" and kind in ("guide", "phrasing", "pentatonic", "scales", "general"):
        out.append("Left hand holds the shell; right hand connects the chord tones.")
    elif fam == "bass" and kind not in ("bassline",):
        out.append("Keep the root solid on the downbeat under the idea.")
    return " ".join(s.strip() for s in out[:3] if s.strip())


__all__ = ["focus_guidance", "focus_kind", "harmonic_context"]
