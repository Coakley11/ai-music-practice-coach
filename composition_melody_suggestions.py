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
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    beat = 0.0
    for i, deg in enumerate(degrees):
        dur = float(durations[i]) if i < len(durations) else 1.0
        pitch, midi = _degree_to_pitch(int(deg), key=key)
        events.append(
            {
                "pitch": pitch,
                "midi": midi,
                "duration_beats": dur,
                "beat": beat,
                "measure": int(beat // 4) + 1,
            }
        )
        beat += dur
    return events


def _beats_per_bar(meter: str) -> float:
    try:
        from composition_melody_notation import beats_per_bar

        return float(beats_per_bar(meter))
    except Exception:
        return 4.0


def _chord_tone_midis(chord: str, *, key: str, octave: int = 4) -> list[tuple[str, int]]:
    """Spelled chord tones with MIDI for melodic writing over one occurrence."""
    from improvisation_motif import _midi_from_note, chord_tone_names

    tones = chord_tone_names(chord, reference_key=key) or []
    out: list[tuple[str, int]] = []
    for name in tones:
        label = str(name or "C").strip() or "C"
        midi = int(_midi_from_note(label, octave))
        out.append((f"{label}{octave}", midi))
    if not out:
        pitch, midi = _degree_to_pitch(1, key=key)
        out.append((f"{pitch}{octave}", int(midi)))
    return out


def _pick_tone(
    tones: list[tuple[str, int]],
    *,
    index: int,
    preference: str,
) -> tuple[str, int]:
    if not tones:
        return ("C4", 60)
    pref = str(preference or "root").lower()
    if pref in {"fifth", "5", "peak"} and len(tones) >= 3:
        return tones[2]
    if pref in {"third", "3", "guide"} and len(tones) >= 2:
        return tones[1]
    if pref in {"seventh", "7", "color"} and len(tones) >= 4:
        return tones[3]
    if pref in {"step", "walk"}:
        return tones[int(index) % len(tones)]
    return tones[int(index) % len(tones)]


def _sounding_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        if e.get("is_rest") or str(e.get("pitch") or "").lower() == "rest":
            continue
        out.append(e)
    return out


def _event_midi(ev: dict[str, Any]) -> int:
    try:
        if ev.get("midi") is not None:
            return int(ev["midi"])
    except (TypeError, ValueError):
        pass
    return 60


def describe_melody_from_events(
    events: list[dict[str, Any]],
    *,
    chord_count: int = 0,
) -> str:
    """Musician-readable description derived only from actual melody events."""
    rows = [dict(e) for e in (events or []) if isinstance(e, dict)]
    sounding = _sounding_events(rows)
    if not sounding:
        rests = sum(1 for e in rows if e.get("is_rest") or str(e.get("pitch") or "").lower() == "rest")
        if rests:
            return "Mostly rests / space — little pitched material yet."
        return "No pitched melody events to describe yet."

    midis = [_event_midi(e) for e in sounding]
    pitches = [str(e.get("pitch") or "?") for e in sounding]
    durs = [float(e.get("duration_beats") or 1.0) for e in sounding]
    intervals = [midis[i + 1] - midis[i] for i in range(len(midis) - 1)]

    parts: list[str] = []

    # Opening motion
    if intervals:
        first = intervals[0]
        if abs(first) >= 7:
            direction = "up" if first > 0 else "down"
            parts.append(f"Opens with a {abs(first)}-semitone leap {direction} from {pitches[0]} to {pitches[1]}")
        elif abs(first) >= 3:
            direction = "rising" if first > 0 else "falling"
            parts.append(f"Opens with a {direction} skip from {pitches[0]} to {pitches[1]}")
        elif first > 0:
            parts.append(f"Starts with a rising step from {pitches[0]} to {pitches[1]}")
        elif first < 0:
            parts.append(f"Starts with a descending step from {pitches[0]} to {pitches[1]}")
        else:
            parts.append(f"Begins by repeating {pitches[0]}")
    else:
        parts.append(f"Centers on {pitches[0]}")

    # Contour / direction of first half vs second
    if len(midis) >= 4:
        mid = len(midis) // 2
        early = midis[mid - 1] - midis[0]
        late = midis[-1] - midis[mid]
        if early > 2 and late < -1:
            parts.append("builds upward early, then settles down")
        elif early < -2 and late > 1:
            parts.append("moves downward at first, then lifts again")
        elif midis[-1] - midis[0] >= 4:
            parts.append("keeps an overall rising shape")
        elif midis[0] - midis[-1] >= 4:
            parts.append("trends downward overall")

    # Leap presence (beyond opening)
    big_leaps = [iv for iv in intervals[1:] if abs(iv) >= 7]
    stepish = sum(1 for iv in intervals if abs(iv) <= 2)
    if big_leaps and intervals:
        parts.append(f"includes a later leap of {abs(big_leaps[0])} semitones")
    elif intervals and stepish >= max(1, int(0.7 * len(intervals))):
        parts.append("moves mostly by step")

    # Motif / repetition (pitch-class digrams)
    digrams: list[tuple[int, int]] = []
    for i in range(len(midis) - 1):
        digrams.append((midis[i] % 12, midis[i + 1] % 12))
    repeated = None
    for i, d in enumerate(digrams):
        for j in range(i + 2, len(digrams)):
            if digrams[j] == d:
                repeated = (pitches[i], pitches[i + 1])
                break
        if repeated:
            break
    if repeated:
        parts.append(f"repeats a short {repeated[0]}–{repeated[1]} figure")

    # Peak
    peak_i = max(range(len(midis)), key=lambda i: midis[i])
    peak_pos = "near the end" if peak_i >= len(midis) * 0.6 else ("early" if peak_i <= len(midis) * 0.35 else "mid-phrase")
    parts.append(f"reaches its high point on {pitches[peak_i]} {peak_pos}")

    # Held note / space
    if durs:
        longest_i = max(range(len(durs)), key=lambda i: durs[i])
        if durs[longest_i] >= max(durs) and durs[longest_i] >= 1.5 * (sum(durs) / len(durs)):
            where = "closing" if longest_i == len(durs) - 1 else f"on {pitches[longest_i]}"
            parts.append(f"holds a longer note {where} ({durs[longest_i]:g} beats)")
    rest_count = sum(1 for e in rows if e.get("is_rest") or str(e.get("pitch") or "").lower() == "rest")
    if rest_count:
        parts.append(f"leaves space with {rest_count} rest{'s' if rest_count != 1 else ''}")

    # Ending
    if len(midis) >= 2:
        last_iv = midis[-1] - midis[-2]
        if last_iv < -1:
            parts.append(f"resolves downward to {pitches[-1]}")
        elif last_iv > 1:
            parts.append(f"ends by lifting to {pitches[-1]}")
        else:
            parts.append(f"closes on {pitches[-1]}")

    # Join into readable prose
    cleaned = [p.strip().rstrip(".") for p in parts if p and str(p).strip()]
    if not cleaned:
        return "Melody events are present."
    text = cleaned[0]
    for p in cleaned[1:]:
        text = f"{text}; {p}"
    if chord_count:
        text = f"{text}. Written across all {chord_count} chord occurrences."
    else:
        text = f"{text}."
    return text[0].upper() + text[1:] if text else text


def _intent_flags(remember: str, notes: str) -> dict[str, bool]:
    blob = f"{remember} {notes}".lower()
    return {
        "rising": any(w in blob for w in ("ris", "soar", "uplift", "upward", "build up", "climb", "peak near the end", "peaks near")),
        "peak_end": any(w in blob for w in ("peak near", "peaks near", "near the end", "final peak", "chorus peak")),
        "hook_repeat": any(w in blob for w in ("hook", "repeat", "motif", "memorable")),
        "opening": any(w in blob for w in ("opening", "start", "begin")),
        "space": any(w in blob for w in ("space", "rest", "breathe", "leave a little")),
        "hold_last": any(w in blob for w in ("hold the final", "hold the last", "longer last", "sustain the last", "hold the final note")),
        "start_low": any(w in blob for w in ("start low", "start fairly low", "begin low", "low and build")),
        "comfortable": any(w in blob for w in ("comfortable", "singable", "narrow range", "easy to sing")),
        "rhythmic": any(w in blob for w in ("rhythmic", "syncop", "groove")),
        "intense_second": any(w in blob for w in ("second half", "more intense", "later phrase")),
    }


def shape_melody_with_intent(
    events: list[dict[str, Any]],
    *,
    feel: str,
    style: str,
    remember: str = "",
    notes: str = "",
    variant: int = 0,
    key: str = "C",
    meter: str = "4/4",
    song_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Materially reshape generated events from feel/style/remember/notes + song profile."""
    from composition_melody_shape import _pitch_label, _repack_beats

    rows = [dict(e) for e in (events or []) if isinstance(e, dict)]
    if not rows:
        return []
    feel = str(feel or "lyrical").lower()
    style = str(style or "simple").lower()
    flags = _intent_flags(remember, notes)
    variant = int(variant) % 3
    profile = song_profile if isinstance(song_profile, dict) else {}
    song_flags = profile.get("flags") if isinstance(profile.get("flags"), dict) else {}
    bias = {}
    try:
        from composition_song_intent import style_melody_bias

        bias = style_melody_bias(profile) if profile else {}
    except ImportError:
        bias = {}

    sounding_idx = [
        i
        for i, e in enumerate(rows)
        if not (e.get("is_rest") or str(e.get("pitch") or "").lower() == "rest")
    ]
    if not sounding_idx:
        return rows

    def set_midi(i: int, midi: int) -> None:
        rows[i]["midi"] = int(midi)
        rows[i]["pitch"] = _pitch_label(int(midi), key)
        rows[i]["is_rest"] = False

    density = float(bias.get("density") or (0.7 if style == "expressive" else 0.5))
    # Feel / song density: shorten values when energetic or high melodic density
    if feel in {"rhythmic", "energetic"} or style == "expressive" or variant == 1 or density >= 0.65:
        for i in sounding_idx:
            d = float(rows[i].get("duration_beats") or 1.0)
            if d >= 1.0:
                rows[i]["duration_beats"] = max(0.5, d * (0.45 if density >= 0.7 else 0.5))
        if (variant == 1 or bias.get("syncopate")) and sounding_idx:
            i0 = sounding_idx[0]
            d = float(rows[i0].get("duration_beats") or 1.0)
            if d >= 0.75:
                half = d / 2.0
                rows[i0]["duration_beats"] = half
                extra = dict(rows[i0])
                midi = _event_midi(rows[i0]) + (2 if feel != "smooth" else 1)
                extra["duration_beats"] = half
                extra["midi"] = midi
                extra["pitch"] = _pitch_label(midi, key)
                rows.insert(i0 + 1, extra)
                sounding_idx = [
                    i
                    for i, e in enumerate(rows)
                    if not (e.get("is_rest") or str(e.get("pitch") or "").lower() == "rest")
                ]

    smooth = feel in {"smooth", "lyrical"} or flags["comfortable"] or bias.get("smooth_contour")
    if smooth:
        midis = [_event_midi(rows[i]) for i in sounding_idx]
        center = int(round(sum(midis) / len(midis)))
        span = 5 if bias.get("smooth_contour") else 7
        for i in sounding_idx:
            m = _event_midi(rows[i])
            if abs(m - center) > span:
                set_midi(i, center + (2 if m > center else -2))
        leap_limit = 4 if bias.get("smooth_contour") else 5
        for n in range(1, len(sounding_idx)):
            a, b = sounding_idx[n - 1], sounding_idx[n]
            ma, mb = _event_midi(rows[a]), _event_midi(rows[b])
            if abs(mb - ma) > leap_limit:
                set_midi(b, ma + (2 if mb > ma else -2))

    wide = feel in {"bold", "energetic", "emotional"} or variant == 2 or bias.get("wider_leaps")
    if wide:
        peak_i = sounding_idx[min(len(sounding_idx) - 1, max(1, int(len(sounding_idx) * 0.7)))]
        base = _event_midi(rows[peak_i])
        bump = 7 if bias.get("wider_leaps") and str(profile.get("section_goal")) == "hook_peak" else (5 if feel == "bold" else 3)
        set_midi(peak_i, base + bump)

    if feel == "emotional" or flags["hold_last"] or song_flags.get("ballad") or str(profile.get("energy_tier")) == "low":
        last = sounding_idx[-1]
        rows[last]["duration_beats"] = min(4.0, float(rows[last].get("duration_beats") or 1.0) + 1.0)

    # Remember / notes driven transforms (existing)
    if flags["start_low"] or (flags["rising"] and flags["opening"]) or song_flags.get("intimate"):
        early = sounding_idx[: max(1, len(sounding_idx) // 3)]
        for i in early:
            set_midi(i, _event_midi(rows[i]) - 5)

    if flags["rising"] or flags["peak_end"] or feel in {"energetic", "bold"} or song_flags.get("anthem") or song_flags.get("build_chorus"):
        late = sounding_idx[len(sounding_idx) // 2 :]
        for n, i in enumerate(late):
            set_midi(i, _event_midi(rows[i]) + 1 + (1 if n == len(late) - 1 and (flags["peak_end"] or song_flags.get("anthem")) else 0))

    if (flags["hook_repeat"] or bias.get("repeat_hook")) and len(sounding_idx) >= 4:
        a, b = sounding_idx[0], sounding_idx[1]
        ma, mb = _event_midi(rows[a]), _event_midi(rows[b])
        t0 = sounding_idx[max(2, len(sounding_idx) // 2)]
        t1 = sounding_idx[min(len(sounding_idx) - 1, sounding_idx.index(t0) + 1 if t0 in sounding_idx else len(sounding_idx) // 2 + 1)]
        set_midi(t0, ma)
        set_midi(t1, mb)

    if flags["space"] or str(profile.get("energy_tier")) == "low":
        # Insert a rest mid-phrase when density allows.
        mid = sounding_idx[len(sounding_idx) // 2]
        if float(rows[mid].get("duration_beats") or 1.0) >= 0.75:
            rest = {
                "pitch": "rest",
                "midi": None,
                "duration_beats": 0.5,
                "is_rest": True,
            }
            rows[mid]["duration_beats"] = max(0.5, float(rows[mid].get("duration_beats") or 1.0) - 0.5)
            rows.insert(mid + 1, rest)

    if flags["intense_second"] or str(profile.get("section_goal")) in {"hook_peak", "build"}:
        half = sounding_idx[len(sounding_idx) // 2 :]
        for i in half:
            set_midi(i, _event_midi(rows[i]) + 2)

    # Jazz/bossa: bias toward chordal extensions via +3/+4 semitone color tones late
    if bias.get("prefer_extensions") and len(sounding_idx) >= 3:
        i = sounding_idx[-2]
        set_midi(i, _event_midi(rows[i]) + (4 if variant % 2 else 3))

    # Modal / klezmer flavor: occasional +1 semitone leading color
    if bias.get("modal_flavor") and len(sounding_idx) >= 2:
        set_midi(sounding_idx[1], _event_midi(rows[sounding_idx[1]]) + 1)

    try:
        rows = _repack_beats(rows, meter=meter)
    except Exception:
        pass
    return rows


def build_melody_events_over_chords(
    chords: list[str],
    *,
    key: str,
    meter: str = "4/4",
    recipe: dict[str, Any] | None = None,
    style: str = "simple",
    feel: str = "",
    song_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build a melody that spans every chord occurrence in order (no base-loop tiling)."""
    symbols = [str(c).strip() for c in (chords or []) if str(c).strip()]
    if not symbols:
        return []
    bar = max(1.0, _beats_per_bar(meter))
    recipe = recipe or {}
    style = str(style or "simple").lower()
    feel = str(feel or "").lower()
    bias: dict[str, Any] = {}
    try:
        from composition_song_intent import style_melody_bias

        if isinstance(song_profile, dict) and song_profile:
            bias = style_melody_bias(song_profile)
    except ImportError:
        bias = {}
    density = float(bias.get("density") or 0.5)
    # Density from style + feel + recipe id + song-intent bias
    dense = (
        style != "simple"
        or feel in {"rhythmic", "energetic"}
        or density >= 0.65
        or str(recipe.get("id") or "").startswith(("rhythmic", "energy", "bold"))
    )
    prefs = list(recipe.get("tone_prefs") or ["root", "third", "fifth", "third"])
    if bias.get("prefer_extensions"):
        prefs = ["third", "seventh", "fifth", "third"]
    elif feel in {"smooth", "lyrical"}:
        prefs = ["root", "third", "root", "third"]
    elif feel in {"bold", "energetic"}:
        prefs = ["fifth", "root", "third", "fifth"]
    elif feel == "emotional":
        prefs = ["third", "fifth", "third", "root"]
    if not prefs:
        prefs = ["root", "third", "fifth", "third"]

    events: list[dict[str, Any]] = []
    beat = 0.0
    for i, chord in enumerate(symbols):
        octave = 3 if (feel in {"smooth", "lyrical"} and i < len(symbols) // 3) else 4
        if feel in {"bold", "energetic"} and i >= len(symbols) // 2:
            octave = 4
        if bias.get("wider_leaps") and i >= len(symbols) // 2:
            octave = 4
        tones = _chord_tone_midis(chord, key=key, octave=octave)
        half_boost = 1 if i >= max(1, len(symbols) // 2) and len(tones) > 1 else 0
        if dense:
            durs = [bar / 2.0, bar / 2.0]
            picks = [
                _pick_tone(tones, index=i + half_boost, preference=prefs[i % len(prefs)]),
                _pick_tone(
                    tones,
                    index=i + 1 + half_boost,
                    preference=prefs[(i + 1) % len(prefs)],
                ),
            ]
        else:
            # Slow / intimate: one tone per bar (more space)
            if density <= 0.35 and str((song_profile or {}).get("energy_tier") or "") == "low":
                durs = [bar]
                picks = [_pick_tone(tones, index=i + half_boost, preference=prefs[i % len(prefs)])]
            else:
                durs = [bar]
                picks = [_pick_tone(tones, index=i + half_boost, preference=prefs[i % len(prefs)])]
        for (pitch, midi), dur in zip(picks, durs):
            pitch_out = str(pitch)
            if pitch_out and not pitch_out[-1].isdigit():
                pitch_out = f"{pitch_out}{octave}"
            events.append(
                {
                    "pitch": pitch_out,
                    "midi": int(midi),
                    "duration_beats": float(dur),
                    "beat": float(beat),
                    "measure": int(beat // bar) + 1,
                    "chord_index": i,
                    "chord": chord,
                }
            )
            beat += float(dur)
    return events


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
    remember: str = "",
    notes: str = "",
) -> list[dict[str, Any]]:
    from composition_song_intent import build_song_intent_profile

    feel = str(feel or default_melody_feel_for_section(section)).strip().lower()
    style = str(style or "simple").strip().lower()
    rem = str(remember or "").strip()
    jot = str(notes or "").strip()
    profile = build_song_intent_profile(
        doc,
        section,
        melody_feel=feel,
        melody_style=style,
        remember=rem,
        melody_notes=jot,
    )
    key = str(profile.get("key_center") or _section_key(doc))
    meter = str(profile.get("meter") or (doc.get("global") or {}).get("time_signature") or "4/4")
    fam = str(profile.get("style_family") or "pop")
    recipes = list(_CONCEPT_LIBRARY.get(feel) or _CONCEPT_LIBRARY["lyrical"])

    section_label = str(section.get("label") or profile.get("section_label") or "")
    if section_label == "Chorus" and feel not in {"bold", "energetic"}:
        recipes = list(_CONCEPT_LIBRARY.get("bold", [])) + recipes
    elif section_label == "Verse" and feel not in {"lyrical", "smooth"}:
        recipes = list(_CONCEPT_LIBRARY.get("lyrical", [])) + recipes
    elif section_label == "Bridge":
        recipes = list(_CONCEPT_LIBRARY.get("emotional", [])) + recipes

    if style == "simple" and fam in {"pop", "folk", "country", "jewish_pop"}:
        recipes = sorted(recipes, key=lambda r: len(list(r.get("degrees") or [])), reverse=False)
    elif fam in {"jazz", "bossa"} or style == "expressive":
        recipes = sorted(recipes, key=lambda r: len(list(r.get("degrees") or [])), reverse=True)

    try:
        from composition_document import chords_for_playback

        sid = str(section.get("id") or "")
        chords = chords_for_playback(doc, scope="section", section_id=sid) if sid else []
    except Exception:
        chords = []

    # Distinct tone cycles per suggestion so variants stay different after intent shaping.
    if fam in {"jazz", "bossa", "soul"}:
        tone_cycles = (
            ["third", "seventh", "fifth", "third"],
            ["seventh", "third", "ninth", "fifth"],
            ["fifth", "seventh", "third", "root"],
        )
    elif fam.startswith("jewish_") and fam != "jewish_pop":
        tone_cycles = (
            ["root", "second", "third", "fifth"],
            ["third", "fifth", "root", "second"],
            ["fifth", "third", "second", "root"],
        )
    else:
        tone_cycles = (
            ["root", "third", "fifth", "third"],
            ["third", "fifth", "root", "fifth"],
            ["fifth", "root", "third", "seventh"],
        )
    variant_names = ("Direct line", "Rhythmic take", "Expressive contour")

    seen: set[str] = set()
    seen_sigs: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for ri, recipe in enumerate(recipes):
        rid = str(recipe.get("id") or "")
        if rid in seen:
            continue
        seen.add(rid)
        shaped = dict(recipe)
        shaped["tone_prefs"] = list(tone_cycles[ri % len(tone_cycles)])
        if chords:
            base_events = build_melody_events_over_chords(
                chords,
                key=key,
                meter=meter,
                recipe=shaped,
                style=style,
                feel=feel,
                song_profile=profile,
            )
        else:
            degrees = [int(d) for d in list(recipe.get("degrees") or [1, 3, 5])]
            durations = [float(d) for d in list(recipe.get("durations") or [1] * len(degrees))]
            if style == "simple" and len(degrees) > 6:
                degrees = degrees[:5]
                durations = durations[:5]
            base_events = build_melody_events_from_degrees(degrees, durations, key=key)

        from composition_melody_shape import events_signature as _esig

        events = shape_melody_with_intent(
            base_events,
            feel=feel,
            style=style,
            remember=rem,
            notes=jot,
            variant=ri,
            key=key,
            meter=meter,
            song_profile=profile,
        )
        nudge = 0
        while _esig(events) in seen_sigs and nudge < 6:
            nudge += 1
            events = shape_melody_with_intent(
                base_events,
                feel=feel,
                style=style,
                remember=rem,
                notes=jot,
                variant=ri + nudge,
                key=key,
                meter=meter,
                song_profile=profile,
            )
        # Last-resort differentiation so card descriptions stay unique.
        if _esig(events) in seen_sigs:
            from composition_melody_shape import _pitch_label

            rows = [dict(e) for e in events]
            sounding = [
                i
                for i, e in enumerate(rows)
                if not (e.get("is_rest") or str(e.get("pitch") or "").lower() == "rest")
            ]
            if sounding:
                bump = 2 + (ri % 3)
                i = sounding[min(len(sounding) - 1, max(0, len(sounding) // 2 + ri))]
                try:
                    midi = int(rows[i].get("midi") or 60) + bump
                except (TypeError, ValueError):
                    midi = 60 + bump
                rows[i]["midi"] = midi
                rows[i]["pitch"] = _pitch_label(midi, key)
                events = rows
        seen_sigs.add(_esig(events))
        description = describe_melody_from_events(events, chord_count=len(chords))
        notes_line = " ".join(str(e.get("pitch") or "") for e in events)
        name = str(recipe.get("name") or "Melodic idea")
        if ri < len(variant_names):
            name = f"{variant_names[ri]} · {name}"
        out.append(
            {
                "id": rid,
                "name": name,
                # Contour/why are event-grounded — never canned recipe prose.
                "contour": description,
                "motif_hint": description,
                "why": description,
                "feel": feel,
                "style": style,
                "remember": rem,
                "notes_intent": jot,
                "events": events,
                "notes_line": notes_line,
                "notes_events": events,
                "chord_span": len(chords),
                "style_family": fam,
                "intent_profile": {
                    "style_family": fam,
                    "song_style_family": profile.get("song_style_family"),
                    "energy_tier": profile.get("energy_tier"),
                    "section_goal": profile.get("section_goal"),
                    "melodic_density": profile.get("melodic_density"),
                },
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
        f"Hum or sing an idea, explore concepts with real notes, preview over the full progression — then refine. "
        f"You remain the composer."
    )


from composition_melody_shape import (
    MELODY_REFINEMENTS,
    propose_melody_refinement,
)

# Re-export for existing imports
__all_refinements__ = MELODY_REFINEMENTS


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
        normalize_melody_events,
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
        result = propose_melody_refinement(events, refinement_id, key=key)
        if result.get("ok") and not result.get("unchanged"):
            melody = _ensure_melody_block(sec)
            melody["events"] = normalize_melody_events(list(result.get("events") or []))
            phrases = list(melody.get("phrases") or [])
            if phrases and isinstance(phrases[-1], dict):
                phrases[-1]["notes"] = " ".join(str(e.get("pitch") or "") for e in melody["events"])
                phrases[-1]["refinement"] = refinement_id
            touch_composition(doc)
            return str(result.get("summary") or hint)
        return str(result.get("summary") or hint)

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
