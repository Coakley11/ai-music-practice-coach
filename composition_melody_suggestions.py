"""Rule-based melodic concept suggestions for Composition Studio (CS-B3).

Concepts include playable note/duration events derived from the Composition key
and (when present) section harmony — not prose-only placeholders.
"""

from __future__ import annotations

from typing import Any

from music_theory import (
    NOTE_TO_MIDI,
    key_is_minor,
    spell_note_in_key,
    split_chord,
    split_key_center,
)

MELODY_FEELINGS: tuple[tuple[str, str], ...] = (
    ("smooth", "Smooth — flowing and connected"),
    ("bold", "Bold — confident leaps and strong peaks"),
    ("lyrical", "Lyrical — singable, speech-like phrases"),
    ("rhythmic", "Rhythmic — groove-driven and syncopated"),
    ("emotional", "Emotional — expressive arcs and dynamic contour"),
    ("energetic", "Energetic — forward motion and lift"),
)

MELODY_STYLES: tuple[tuple[str, str], ...] = (
    ("simple", "Simple & singable — easy to remember after one listen"),
    ("expressive", "More expressive — room for nuance and variation"),
)

DEFAULT_MELODY_FEEL_BY_SECTION: dict[str, str] = {
    "Intro": "smooth",
    "Verse": "lyrical",
    "Pre-Chorus": "energetic",
    "Chorus": "bold",
    "Bridge": "emotional",
    "Solo": "energetic",
    "Interlude": "smooth",
    "Outro": "smooth",
    "Breakdown": "rhythmic",
}

# Degree patterns relative to tonic (1=root … 8=octave). Minor uses natural minor degrees.
_CONCEPT_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "smooth": [
        {
            "id": "smooth_stepwise",
            "name": "Gentle stepwise line",
            "contour": "Move mostly by step — calm and approachable.",
            "motif_hint": "Root → 2nd → 3rd → 2nd → root",
            "why": "Stepwise motion feels natural to sing and keeps focus on the lyric.",
            "degrees": [1, 2, 3, 2, 1],
            "durations": [1, 1, 1, 1, 2],
        },
        {
            "id": "smooth_arc",
            "name": "Soft arch",
            "contour": "Rise through the phrase, then settle back down by step.",
            "motif_hint": "Climb to the 5th, float down to the 3rd",
            "why": "A gentle arch creates emotional shape without demanding range.",
            "degrees": [1, 3, 5, 3, 2, 1],
            "durations": [1, 1, 2, 1, 1, 2],
        },
    ],
    "bold": [
        {
            "id": "bold_leap_hook",
            "name": "Leap to the hook",
            "contour": "Open with a confident interval jump onto a strong chord tone.",
            "motif_hint": "5th → root leap, then up to the 3rd",
            "why": "Strategic leaps make a chorus feel anthemic and memorable.",
            "degrees": [5, 1, 3, 5, 8],
            "durations": [1, 1, 1, 1, 2],
        },
        {
            "id": "bold_peak",
            "name": "High-point arrival",
            "contour": "Build toward one peak note that lands with the harmony.",
            "motif_hint": "Hold the 3rd, leap to the 5th on the change",
            "why": "One clear peak gives listeners something to wait for.",
            "degrees": [1, 2, 3, 3, 5, 3],
            "durations": [1, 1, 2, 1, 2, 1],
        },
    ],
    "lyrical": [
        {
            "id": "lyrical_conversation",
            "name": "Conversational phrase",
            "contour": "Short groups of notes that mirror natural speech rhythm.",
            "motif_hint": "Three-note cells with a short rest of space between",
            "why": "Speech-like phrasing helps verses feel like storytelling.",
            "degrees": [1, 2, 3, 1, 2, 5],
            "durations": [0.5, 0.5, 1, 0.5, 0.5, 2],
        },
        {
            "id": "lyrical_question",
            "name": "Question & answer",
            "contour": "First phrase rises (question), second resolves (answer).",
            "motif_hint": "End first idea on 2nd; answer steps down to root",
            "why": "Call-and-response keeps verses engaging across lines.",
            "degrees": [1, 3, 5, 2, 5, 3, 1],
            "durations": [1, 1, 1, 2, 1, 1, 2],
        },
    ],
    "rhythmic": [
        {
            "id": "rhythmic_syncopated",
            "name": "Off-beat accent",
            "contour": "Emphasize notes that sit slightly ahead of the beat.",
            "motif_hint": "Repeated 3-note cell with lighter longer landings",
            "why": "Syncopation adds groove without changing your chords.",
            "degrees": [1, 1, 5, 1, 1, 5, 3],
            "durations": [0.5, 0.5, 1, 0.5, 0.5, 1, 2],
        },
        {
            "id": "rhythmic_pocket",
            "name": "Groove pocket",
            "contour": "Fewer notes, stronger rhythm — let space do the work.",
            "motif_hint": "Root on 1, 5th later, 3rd to close",
            "why": "A rhythmic pocket feels modern and leaves room to breathe.",
            "degrees": [1, 5, 3, 1],
            "durations": [2, 1, 1, 2],
        },
    ],
    "emotional": [
        {
            "id": "emotional_sigh",
            "name": "Sighing descent",
            "contour": "Start high, descend by step — like an exhale.",
            "motif_hint": "Begin on 5th or 6th, step down to root",
            "why": "Descending stepwise lines carry intimacy.",
            "degrees": [5, 4, 3, 2, 1],
            "durations": [2, 1, 1, 1, 2],
        },
        {
            "id": "emotional_delayed",
            "name": "Delayed resolution",
            "contour": "Hold tension on a non-root tone, then resolve late.",
            "motif_hint": "Sit on the 2nd, resolve to root or 3rd",
            "why": "Delaying resolution creates yearning before the line lands.",
            "degrees": [2, 2, 2, 1, 3],
            "durations": [1, 1, 2, 1, 2],
        },
    ],
    "energetic": [
        {
            "id": "energy_rise",
            "name": "Forward climb",
            "contour": "Steady upward motion through the phrase.",
            "motif_hint": "Root → 2 → 3 → 4 → 5 across the opening",
            "why": "Rising lines build momentum into a chorus or pre-chorus.",
            "degrees": [1, 2, 3, 4, 5],
            "durations": [1, 1, 1, 1, 2],
        },
        {
            "id": "energy_repetition",
            "name": "Motif repetition",
            "contour": "Repeat a short cell with one note changing each time.",
            "motif_hint": "Do–Mi–Sol, Do–Mi–La, Do–Mi–Sol",
            "why": "Repetition with tiny variation is how hooks stick.",
            "degrees": [1, 3, 5, 1, 3, 6, 1, 3, 5],
            "durations": [0.5, 0.5, 1, 0.5, 0.5, 1, 0.5, 0.5, 2],
        },
    ],
}


def default_melody_feel_for_section(section: dict[str, Any]) -> str:
    label = str(section.get("label") or "Verse")
    return DEFAULT_MELODY_FEEL_BY_SECTION.get(label, "lyrical")


def feel_label(feel_id: str) -> str:
    for fid, label in MELODY_FEELINGS:
        if fid == feel_id:
            return label
    return feel_id


def style_label(style_id: str) -> str:
    for sid, label in MELODY_STYLES:
        if sid == style_id:
            return label
    return style_id


_MAJOR_DEGREE_SEMIS = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11, 8: 12}
_MINOR_DEGREE_SEMIS = {1: 0, 2: 2, 3: 3, 4: 5, 5: 7, 6: 8, 7: 10, 8: 12}


def _tonic_midi(key: str) -> int:
    tonic, _mode = split_key_center(key)
    base = NOTE_TO_MIDI.get(tonic) or NOTE_TO_MIDI.get(tonic.replace("b", "")) or 60
    # Prefer a mid-register melody tonic around C4–A4.
    while base < 55:
        base += 12
    while base > 69:
        base -= 12
    return int(base)


def _degree_to_pitch(degree: int, *, key: str) -> tuple[str, int]:
    table = _MINOR_DEGREE_SEMIS if key_is_minor(key) else _MAJOR_DEGREE_SEMIS
    deg = int(degree)
    octaves = 0
    while deg > 8:
        deg -= 7
        octaves += 1
    while deg < 1:
        deg += 7
        octaves -= 1
    midi = _tonic_midi(key) + int(table.get(deg, 0)) + (12 * octaves)
    pc = midi % 12
    name = spell_note_in_key(pc, key)
    return name, midi


def build_melody_events_from_degrees(
    degrees: list[int],
    durations: list[float],
    *,
    key: str,
    beats_per_bar: float = 4.0,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    beat = 0.0
    bar = max(1.0, float(beats_per_bar or 4.0))
    for i, deg in enumerate(degrees):
        dur = float(durations[i]) if i < len(durations) else 1.0
        pitch, midi = _degree_to_pitch(int(deg), key=key)
        events.append(
            {
                "pitch": pitch,
                "midi": midi,
                "duration_beats": dur,
                "beat": beat,
                "measure": int(beat // bar) + 1,
            }
        )
        beat += dur
    return events


def _quality_intervals(quality: str) -> list[int]:
    q = str(quality or "").lower()
    if "dim" in q:
        return [0, 3, 6]
    if "aug" in q:
        return [0, 4, 8]
    minorish = q.startswith("m") and not q.startswith("maj") and not q.startswith("ma7")
    if minorish or q.startswith("min"):
        return [0, 3, 7, 10] if "7" in q else [0, 3, 7]
    if "maj7" in q or "ma7" in q:
        return [0, 4, 7, 11]
    if "7" in q:
        return [0, 4, 7, 10]
    return [0, 4, 7]


def _chord_tone_midis(symbol: str, register: int = 60) -> list[int]:
    from music_theory import NOTE_TO_MIDI, split_chord

    root, quality = split_chord(str(symbol or "C"))
    base = NOTE_TO_MIDI.get(root) or NOTE_TO_MIDI.get(str(root).replace("b", "")) or 60
    while base < register - 6:
        base += 12
    while base > register + 6:
        base -= 12
    return [base + iv for iv in _quality_intervals(quality)]


def _snap_midi_to_chord_tone(midi: int, chord: str) -> int:
    tones = _chord_tone_midis(chord, register=int(midi))
    if not tones:
        return int(midi)
    candidates: list[int] = []
    for tone in tones:
        for octv in (-12, 0, 12):
            candidates.append(tone + octv)
    return min(candidates, key=lambda m: (abs(m - int(midi)), abs(m - 60)))


def _section_beats(doc: dict[str, Any], section: dict[str, Any]) -> tuple[float, float, str]:
    from composition_document import playback_globals, section_playback_bars

    pg = playback_globals(doc)
    meter = str(pg.get("time_signature") or "4/4")
    if "/" in meter:
        try:
            bpb = float(int(meter.split("/", 1)[0]))
        except ValueError:
            bpb = 4.0
    else:
        bpb = 4.0
    bars = max(1, int(section_playback_bars(doc, section) or 1))
    return float(bars) * bpb, bpb, meter


def _chord_spans_for_section(doc: dict[str, Any], section: dict[str, Any]) -> list[dict[str, Any]]:
    from composition_hum_transcription import build_section_record_timeline

    sid = str(section.get("id") or "")
    timeline = build_section_record_timeline(doc, sid) if sid else {}
    changes = list(timeline.get("chord_changes") or [])
    if changes:
        return changes
    total_beats, bpb, _meter = _section_beats(doc, section)
    from composition_document import chords_for_playback

    chords = chords_for_playback(doc, scope="section", section_id=sid) if sid else []
    if not chords:
        return [{"beat": 0.0, "duration_beats": total_beats, "chord": ""}]
    span = total_beats / float(len(chords))
    return [
        {"beat": i * span, "duration_beats": span, "chord": str(ch)}
        for i, ch in enumerate(chords)
    ]


def _chord_at_beat(spans: list[dict[str, Any]], beat: float) -> str:
    sounding = ""
    for row in spans:
        if beat + 1e-6 >= float(row.get("beat") or 0.0):
            sounding = str(row.get("chord") or "")
        else:
            break
    return sounding


def expand_melody_events_to_section(
    events: list[dict[str, Any]],
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    key: str = "",
) -> list[dict[str, Any]]:
    """Tile a motif across the declared section length and chord timeline."""
    from composition_document import normalize_melody_events, playback_globals
    from composition_hum_transcription import spell_midi_in_key

    motif = normalize_melody_events(events)
    total_beats, bpb, _meter = _section_beats(doc, section)
    pg = playback_globals(doc)
    key_token = str(key or pg.get("key_center") or "C")
    spans = _chord_spans_for_section(doc, section)
    if not motif:
        motif = [
            {
                "pitch": "C",
                "midi": 60,
                "duration_beats": min(1.0, total_beats),
                "beat": 0.0,
                "measure": 1,
            }
        ]

    motif_len = sum(float(e.get("duration_beats") or 1.0) for e in motif)
    if motif_len <= 0:
        motif_len = 1.0

    tiled: list[dict[str, Any]] = []
    cursor = 0.0
    guard = 0
    while cursor < total_beats - 1e-6 and guard < 256:
        guard += 1
        for src in motif:
            dur = float(src.get("duration_beats") or 1.0)
            remaining = total_beats - cursor
            if remaining <= 1e-6:
                break
            use = min(dur, remaining)
            copied = dict(src)
            copied["beat"] = cursor
            copied["duration_beats"] = use
            copied["measure"] = int(cursor // bpb) + 1
            chord = _chord_at_beat(spans, cursor)
            on_chord_change = any(
                abs(cursor - float(span.get("beat") or 0.0)) < 0.26 for span in spans
            )
            if (
                chord
                and on_chord_change
                and not copied.get("is_rest")
                and str(copied.get("pitch") or "").lower() != "rest"
            ):
                try:
                    midi_i = int(copied.get("midi") or 60)
                except (TypeError, ValueError):
                    midi_i = 60
                snapped = _snap_midi_to_chord_tone(midi_i, chord)
                copied["midi"] = snapped
                copied["pitch"] = spell_midi_in_key(snapped, key_token)
                copied["chord"] = chord
            tiled.append(copied)
            cursor += use

    # Guarantee an onset on every chord change.
    existing_onsets = [float(e.get("beat") or 0.0) for e in tiled]
    for span in spans:
        start = float(span.get("beat") or 0.0)
        end = start + float(span.get("duration_beats") or bpb)
        chord = str(span.get("chord") or "")
        if start >= total_beats - 1e-6:
            continue
        if any(start - 1e-6 <= o < end - 1e-6 for o in existing_onsets):
            continue
        midi_i = _snap_midi_to_chord_tone(60, chord or "C")
        tiled.append(
            {
                "pitch": spell_midi_in_key(midi_i, key_token),
                "midi": midi_i,
                "duration_beats": min(1.0, max(0.5, end - start)),
                "beat": start,
                "measure": int(start // bpb) + 1,
                "chord": chord,
            }
        )
        existing_onsets.append(start)

    tiled.sort(key=lambda e: float(e.get("beat") or 0.0))
    # Pad a trailing rest if the line still ends early.
    if tiled:
        end = max(float(e.get("beat") or 0.0) + float(e.get("duration_beats") or 0.0) for e in tiled)
        if end < total_beats - 0.26:
            tiled.append(
                {
                    "pitch": "rest",
                    "midi": None,
                    "duration_beats": total_beats - end,
                    "beat": end,
                    "measure": int(end // bpb) + 1,
                    "is_rest": True,
                }
            )
        elif end > total_beats + 1e-6:
            last = tiled[-1]
            last["duration_beats"] = max(0.25, float(last.get("duration_beats") or 1.0) - (end - total_beats))
    return normalize_melody_events(tiled)


def melody_section_coverage(
    events: list[dict[str, Any]],
    doc: dict[str, Any],
    section: dict[str, Any],
) -> dict[str, Any]:
    """Validate onsets/durations through the section boundary and each chord change."""
    total_beats, _bpb, _meter = _section_beats(doc, section)
    spans = _chord_spans_for_section(doc, section)
    if not events:
        return {
            "covers": False,
            "aligned": False,
            "start": 0.0,
            "end": 0.0,
            "target_beats": total_beats,
            "missing_chords": [str(s.get("chord") or "") for s in spans],
        }
    start = min(float(e.get("beat") or 0.0) for e in events)
    end = max(float(e.get("beat") or 0.0) + float(e.get("duration_beats") or 0.0) for e in events)
    covers = start <= 0.26 and end >= total_beats - 0.51
    missing: list[str] = []
    for span in spans:
        ch_start = float(span.get("beat") or 0.0)
        ch_end = ch_start + float(span.get("duration_beats") or 0.0)
        hit = any(
            ch_start - 1e-6 <= float(e.get("beat") or 0.0) < ch_end - 1e-6
            for e in events
            if isinstance(e, dict)
        )
        if not hit:
            missing.append(str(span.get("chord") or ""))
    return {
        "covers": covers,
        "aligned": not missing,
        "start": start,
        "end": end,
        "target_beats": total_beats,
        "missing_chords": missing,
    }


def _section_key(doc: dict[str, Any]) -> str:
    g = doc.get("global") or {}
    return str(g.get("original_key_center") or "C")


def suggest_melody_concepts(
    doc: dict[str, Any],
    section: dict[str, Any],
    feel: str,
    style: str = "simple",
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    feel = str(feel or default_melody_feel_for_section(section)).strip().lower()
    style = str(style or "simple").strip().lower()
    key = _section_key(doc)
    recipes = list(_CONCEPT_LIBRARY.get(feel) or _CONCEPT_LIBRARY["lyrical"])

    section_label = str(section.get("label") or "")
    if section_label == "Chorus" and feel not in {"bold", "energetic"}:
        recipes = list(_CONCEPT_LIBRARY.get("bold", [])) + recipes
    elif section_label == "Verse" and feel not in {"lyrical", "smooth"}:
        recipes = list(_CONCEPT_LIBRARY.get("lyrical", [])) + recipes

    if style == "simple":
        recipes = sorted(recipes, key=lambda r: len(list(r.get("degrees") or [])), reverse=False)

    # Prefer concepts that sit near chord tones when harmony exists.
    try:
        from composition_document import chords_for_playback, section_by_id

        sid = str(section.get("id") or "")
        chords = chords_for_playback(doc, scope="section", section_id=sid) if sid else []
    except Exception:
        chords = []

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for recipe in recipes:
        rid = str(recipe.get("id") or "")
        if rid in seen:
            continue
        seen.add(rid)
        degrees = [int(d) for d in list(recipe.get("degrees") or [1, 3, 5])]
        durations = [float(d) for d in list(recipe.get("durations") or [1] * len(degrees))]
        if style == "simple" and len(degrees) > 6:
            degrees = degrees[:5]
            durations = durations[:5]
        events = build_melody_events_from_degrees(degrees, durations, key=key)
        events = expand_melody_events_to_section(events, doc, section, key=key)
        notes_line = " ".join(str(e["pitch"]) for e in events if not e.get("is_rest"))
        why = str(recipe.get("why") or "")
        if chords:
            why = f"{why} Shaped to sit over this section's full harmony in {key}."
        out.append(
            {
                "id": rid,
                "name": str(recipe.get("name") or "Melodic idea"),
                "contour": str(recipe.get("contour") or ""),
                "motif_hint": str(recipe.get("motif_hint") or ""),
                "why": why,
                "feel": feel,
                "style": style,
                "events": events,
                "notes_line": notes_line,
                "notes_events": events,
            }
        )
        if len(out) >= limit:
            break
    return out


def coach_line_for_melody(
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    feel: str = "",
    remember: str = "",
) -> str:
    variant = str(section.get("label_variant") or section.get("label") or "this section")
    label = str(section.get("label") or "Section")
    feel_txt = feel_label(feel or default_melody_feel_for_section(section)).split("—")[0].strip().lower()
    remember_bit = (
        f' You said listeners should remember: <em>"{remember[:120]}"</em>.'
        if remember.strip()
        else ""
    )
    jobs = {
        "Intro": "invite the listener in without giving everything away",
        "Verse": "carry the story in a way that feels natural to sing",
        "Pre-Chorus": "build anticipation toward the hook",
        "Chorus": "deliver the line everyone hums after the song ends",
        "Bridge": "offer a fresh melodic angle before the final return",
        "Solo": "express personality over the harmony",
        "Interlude": "create breathing room",
        "Outro": "leave a lasting final image",
    }
    job = jobs.get(label, "give this section its own musical identity")
    return (
        f"For <strong>{variant}</strong>, imagine a <strong>{feel_txt}</strong> melody that will {job}."
        f"{remember_bit}<br><br>"
        f"Hum an idea, explore concepts with real notes, preview over the chords — then refine. "
        f"You remain the composer."
    )


MELODY_REFINEMENTS: tuple[tuple[str, str, str], ...] = (
    ("smoother", "Make it smoother", "Connect notes with smaller steps; fewer leaps."),
    ("energetic", "Make it more energetic", "Add forward motion — shorter notes, more lift on peaks."),
    ("rhythm", "Add more rhythm", "Syncopate or repeat a rhythmic cell twice."),
    ("simplify", "Simplify it", "Fewer notes; one clear shape per phrase."),
    ("emotional", "Make it more emotional", "Widen the dynamic arc — longer notes at the peak."),
    ("range_up", "Increase the range", "Reach one step higher on the climax note."),
    ("singable", "Make it easier to sing", "Stay in a narrow range with mostly steps."),
)


def melody_notation_line(concept: dict[str, Any]) -> str:
    """Readable note line for UI (staff notation deferred)."""
    notes = str(concept.get("notes_line") or "").strip()
    if notes:
        return f"♪ {notes[:72]}{'…' if len(notes) > 72 else ''}"
    events = list(concept.get("events") or [])
    if events:
        line = " ".join(str(e.get("pitch") or "") for e in events if isinstance(e, dict))
        if line:
            return f"♪ {line[:72]}{'…' if len(line) > 72 else ''}"
    motif = str(concept.get("motif_hint") or concept.get("motif") or "").strip()
    if not motif:
        return "♩ ♪ ♪ ♩  (melodic contour — hear it on your harmony)"
    return f"♪ {motif[:72]}{'…' if len(motif) > 72 else ''}"


def _rewrite_event_pitch(event: dict[str, Any], midi: int, key: str) -> dict[str, Any]:
    from composition_hum_transcription import spell_midi_in_key

    copied = dict(event)
    midi_i = max(48, min(84, int(midi)))
    copied["midi"] = midi_i
    copied["pitch"] = spell_midi_in_key(midi_i, key)
    copied["is_rest"] = False
    return copied


def shape_accepted_melody_events(
    events: list[dict[str, Any]] | None,
    *,
    key: str = "C",
) -> list[dict[str, Any]]:
    """Bounded contour reshape: invert around the median, keep rhythm and order."""
    from composition_document import normalize_melody_events

    src = normalize_melody_events(events)
    pitched_idx = [
        i
        for i, ev in enumerate(src)
        if not ev.get("is_rest") and str(ev.get("pitch") or "").lower() != "rest"
    ]
    if not pitched_idx:
        return src
    midis = [int(src[i].get("midi") or 60) for i in pitched_idx]
    median = sorted(midis)[len(midis) // 2]
    out: list[dict[str, Any]] = []
    changed = False
    for i, ev in enumerate(src):
        if i not in pitched_idx:
            out.append(dict(ev))
            continue
        midi = int(ev.get("midi") or 60)
        shaped = median - (midi - median)
        shaped = max(55, min(74, shaped))
        if shaped == midi:
            shaped = max(55, min(74, midi + (2 if i >= pitched_idx[len(pitched_idx) // 2] else -2)))
        if shaped != midi:
            changed = True
        out.append(_rewrite_event_pitch(ev, shaped, key))
    if not changed and pitched_idx:
        last = pitched_idx[-1]
        out[last] = _rewrite_event_pitch(out[last], int(out[last].get("midi") or 60) + 2, key)
    return out


def refine_accepted_melody_events(
    events: list[dict[str, Any]] | None,
    *,
    key: str = "C",
    doc: dict[str, Any] | None = None,
    section: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Smooth leaps and ease notes toward the sounding chord tone. Keeps the line."""
    from composition_document import normalize_melody_events

    src = normalize_melody_events(events)
    spans = _chord_spans_for_section(doc, section) if doc and section else []
    out: list[dict[str, Any]] = []
    prev_midi: int | None = None
    changed = False
    for ev in src:
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            out.append(dict(ev))
            continue
        midi = int(ev.get("midi") or 60)
        refined = midi
        if prev_midi is not None and abs(midi - prev_midi) > 4:
            step = 2 if midi > prev_midi else -2
            refined = prev_midi + step
            changed = True
        chord = _chord_at_beat(spans, float(ev.get("beat") or 0.0)) if spans else ""
        if chord:
            snapped = _snap_midi_to_chord_tone(refined, chord)
            if abs(snapped - refined) >= 1:
                refined = snapped
                changed = True
        if refined != midi:
            changed = True
        written = _rewrite_event_pitch(ev, refined, key)
        if chord:
            written["chord"] = chord
        out.append(written)
        prev_midi = int(written.get("midi") or refined)
    if not changed:
        pitched = [
            i
            for i, ev in enumerate(out)
            if not ev.get("is_rest") and str(ev.get("pitch") or "").lower() != "rest"
        ]
        if pitched:
            i = pitched[min(1, len(pitched) - 1)]
            out[i] = _rewrite_event_pitch(out[i], int(out[i].get("midi") or 60) - 1, key)
    return out


def apply_shaped_or_refined_melody(
    doc: dict[str, Any],
    section_id: str,
    *,
    action: str,
) -> str:
    """Shape or refine accepted events, then write the single melody authority."""
    from composition_document import (
        apply_accepted_melody_edits,
        playback_globals,
        section_by_id,
        section_melody_events,
    )

    sec = section_by_id(doc, section_id)
    if not sec:
        return ""
    events = section_melody_events(sec)
    if not events:
        return ""
    key = str(playback_globals(doc).get("key_center") or "C")
    kind = str(action or "").strip().lower()
    if kind == "shape":
        updated = shape_accepted_melody_events(events, key=key)
        label = "Shaped the accepted melody — contour changed; rhythm kept."
    else:
        updated = refine_accepted_melody_events(events, key=key, doc=doc, section=sec)
        label = "Refined the accepted melody — smoother motion over the chords."
    apply_accepted_melody_edits(doc, section_id, updated)
    return label


def apply_melody_refinement_to_section(
    doc: dict[str, Any],
    section_id: str,
    refinement_id: str,
) -> str:
    """Apply a structured local edit to accepted melody events when present.

    Falls back to prose motif hints when no events exist. Does not invent fake
    transcription from hum capture.
    """
    from composition_document import (
        section_by_id,
        touch_composition,
        _ensure_melody_block,
        section_melody_events,
    )

    sec = section_by_id(doc, section_id)
    if not sec:
        return ""
    hint = next((h for rid, _, h in MELODY_REFINEMENTS if rid == refinement_id), "")
    if not hint:
        return ""

    events = section_melody_events(sec)
    key = _section_key(doc)
    if events:
        from composition_document import apply_accepted_melody_edits
        from composition_hum_transcription import spell_midi_in_key

        updated = [dict(e) for e in events]
        if refinement_id == "smoother":
            updated = refine_accepted_melody_events(updated, key=key, doc=doc, section=sec)
        elif refinement_id == "range_up" and updated:
            peak = max(range(len(updated)), key=lambda i: int(updated[i].get("midi") or 60))
            midi = int(updated[peak].get("midi") or 60) + 2
            updated[peak]["midi"] = midi
            updated[peak]["pitch"] = spell_midi_in_key(midi, key)
        elif refinement_id == "simplify" and len(updated) > 4:
            updated = updated[::2]
            beat = 0.0
            for ev in updated:
                ev["beat"] = beat
                beat += float(ev.get("duration_beats") or 1.0)
        elif refinement_id in {"energetic", "rhythm"}:
            for ev in updated:
                dur = float(ev.get("duration_beats") or 1.0)
                ev["duration_beats"] = max(0.5, dur * 0.75)
        elif refinement_id == "emotional" and updated:
            updated[-1]["duration_beats"] = float(updated[-1].get("duration_beats") or 1.0) + 1.0
        elif refinement_id in {"singable"}:
            updated = refine_accepted_melody_events(updated, key=key, doc=doc, section=sec)
        apply_accepted_melody_edits(doc, section_id, updated)
        melody = _ensure_melody_block(sec)
        phrases = list(melody.get("phrases") or [])
        if phrases and isinstance(phrases[-1], dict):
            phrases[-1]["notes"] = " ".join(str(e.get("pitch") or "") for e in melody["events"])
            phrases[-1]["refinement"] = refinement_id
        touch_composition(doc)
        return hint

    melody = _ensure_melody_block(sec)
    phrases = list(melody.get("phrases") or [])
    if phrases and isinstance(phrases[-1], dict):
        p = phrases[-1]
        base = str(p.get("motif") or p.get("notes") or "").strip()
        p["motif"] = f"{base} — {hint}".strip(" —") if base else hint
        p["refinement"] = refinement_id
    else:
        intent = melody.setdefault("intent", {})
        existing = str(intent.get("hum_notes") or "").strip()
        intent["hum_notes"] = f"{existing}\n{hint}".strip() if existing else hint
    touch_composition(doc)
    return hint
