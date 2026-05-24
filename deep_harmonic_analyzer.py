"""Deep Harmonic Analyzer — song-aware harmonic analysis for Improvisation Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from creative_lab_text import (
    chord_quality,
    chord_root,
    first_matching_pattern,
    roman_path,
    root_path,
    section_role,
)
from improvisation_intelligence import (
    ImprovSessionContext,
    build_scale_suggestion,
    format_scale_line,
)
from improvisation_motif import chord_tone_names, dedupe_sections_for_display, single_progression_cycle
from music_theory import CHROMATIC, normalize_root, split_chord


@dataclass
class HarmonicAnalysisInput:
    song_title: str
    artist: str
    key_center: str
    display_key: str
    sections: dict[str, list[str]]
    instrument: str
    level: str
    focus: str
    genre: str = ""
    bpm: int = 100
    time_signature: str = ""
    arrangement_notes: str = ""
    progression_flat: list[str] = field(default_factory=list)


def _pc(note: str) -> str | None:
    root, _ = split_chord(str(note))
    r = normalize_root(root)
    return r if r in CHROMATIC else None


def _semitone_dist(a: str, b: str) -> int:
    pa, pb = _pc(a), _pc(b)
    if not pa or not pb:
        return 99
    return min((CHROMATIC.index(pb) - CHROMATIC.index(pa)) % 12, (CHROMATIC.index(pa) - CHROMATIC.index(pb)) % 12)


def _voice_lead_pair(ch_a: str, ch_b: str) -> str:
    tones_a = chord_tone_names(ch_a)
    tones_b = chord_tone_names(ch_b)
    if not tones_a or not tones_b:
        return f"Connect **{ch_a}** to **{ch_b}** through nearest chord tones."
    common = [t for t in tones_a if t in tones_b]
    moves: list[str] = []
    for t in tones_a[:3]:
        if t in common:
            moves.append(f"**{t}** holds as a common tone")
            continue
        nearest = min(tones_b, key=lambda x: _semitone_dist(t, x))
        dist = _semitone_dist(t, nearest)
        if dist <= 1:
            moves.append(f"**{t}** steps to **{nearest}**")
        elif dist == 2:
            moves.append(f"**{t}** moves by step toward **{nearest}**")
        else:
            moves.append(f"**{t}** can leap to **{nearest}** on a strong beat")
    common_txt = f" ({', '.join(common)} shared)" if common else ""
    return (
        f"Over **{ch_a}** → **{ch_b}**: "
        + "; ".join(moves[:3])
        + common_txt
        + "."
    )


def _chord_tension_label(ch: str, next_ch: str, key: str) -> str:
    q = chord_quality(ch)
    low = str(ch).lower()
    if "sus" in low:
        return "suspended color — delays resolution and keeps the phrase hovering"
    if q in ("dominant seventh",) or (q == "dominant seventh" and "7" in low):
        return "dominant tension — wants to resolve forward"
    if "dim" in low or "m7b5" in low or "half-diminished" in q:
        return "passing tension — short, directional color"
    if "/" in str(ch):
        bass = str(ch).split("/", 1)[1].strip()
        return f"slash bass **{bass}** creates forward pull into the next harmony"
    if next_ch:
        nt = chord_tone_names(next_ch)
        if nt and chord_root(ch) != chord_root(next_ch):
            return f"sets up **{next_ch}** — the bass or top line leads the ear forward"
    if q == "major seventh":
        return "stable, dreamy color — emotional release when the phrase lands here"
    if q in ("minor", "minor seventh"):
        return "minor color — introspective, can act as relative darkness before lift"
    return "stable harmonic color in this key"


def _detect_character(
    cycle: list[str],
    key: str,
    genre: str,
    title: str,
    meter: str,
) -> dict[str, str]:
    pattern = first_matching_pattern(cycle, key) if cycle else ""
    g = (genre or "").lower()
    t = (title or "").lower()
    meter_note = f" Written in **{meter}** — phrasing should follow the compound pulse." if meter else ""

    if "perfect" in t:
        return {
            "style": "Acoustic **pop ballad** / singer-songwriter progression",
            "feel": "Warm, intimate, wedding-song emotional arc — gentle lift in the chorus without jazz complexity.",
            "movement": (
                "Verse centers on **G–Em7–Cadd9–D/F#** (home → relative minor → subdominant color → dominant with bass lead). "
                "Chorus rotates **Em7–Cadd9–G–D/F#** for open, singable lift. Intro/Outro use a descending walk back to **G**."
            ),
            "signature": "Slash bass on **D/F#** and add9/sus extensions on **C** — that is the recognizable color.",
            "similar": "Similar harmonic *feel* to modern acoustic pop ballads (I–vi–IV–V family with bass-line motion).",
            "meter": meter_note or " **6/8** ballad feel — two beats per bar group, long chord holds in the verse.",
        }

    if "blue bossa" in t or "bossa" in g:
        return {
            "style": "**Bossa nova / jazz standard** harmony",
            "feel": "Cool, swaying, minor-key sophistication with ii–V language.",
            "movement": "Minor-key centers with ii–V–I motion and modal interchange.",
            "signature": "Maj7 and m7 colors, chromatic bass, and rhythmic space.",
            "similar": "Comparable to Jobim-era bossa and minor jazz standards.",
            "meter": meter_note,
        }

    if pattern == "vi-IV-I-V pop loop":
        return {
            "style": "**vi–IV–I–V pop** / singer-songwriter loop",
            "feel": "Nostalgic, anthemic — verse feels grounded, chorus feels like arrival.",
            "movement": f"Core cell: **{roman_path(cycle, key, 4) or 'vi–IV–I–V'}** — repetition is the identity.",
            "signature": "Emotional lift comes from returning to **I**, not from dense reharmonization.",
            "similar": "Same family as countless pop/rock ballads and folk-crossover hits.",
            "meter": meter_note,
        }
    if pattern == "I-V-vi-IV pop loop":
        return {
            "style": "**I–V–vi–IV** pop song-form loop",
            "feel": "Forward, open, radio-friendly harmonic direction.",
            "movement": f"Loop: **{roman_path(cycle, key, 4)}** with strong dominant pull mid-loop.",
            "signature": "The **V** chord creates the main tension before the vi color.",
            "similar": "Matches mainstream pop progression vocabulary.",
            "meter": meter_note,
        }
    if pattern == "ii-V-I resolution":
        return {
            "style": "**Jazz standard** functional harmony (ii–V–I)",
            "feel": "Sophisticated tension and release — every dominant asks a question.",
            "movement": "ii–V–I chains and secondary dominants define the form.",
            "signature": "Guide tones (3rds & 7ths) tell the story more than the root alone.",
            "similar": "Classic jazz standard / Great American Songbook language.",
            "meter": meter_note,
        }
    if any("maj7" in chord_quality(c) for c in cycle[:6]):
        jazzish = "jazz" in g or "jazz" in t
        return {
            "style": "**Jazz-influenced** harmony" if jazzish else "**Major-seventh pop/jazz** color",
            "feel": "Dreamy, polished — maj7 chords soften the emotional temperature.",
            "movement": f"Root motion: **{root_path(cycle, limit=5)}** with extended tertian color.",
            "signature": "Maj7 extensions on tonic and subdominant chords.",
            "similar": "Neo-soul and jazz-ballad vocabulary." if jazzish else "Adult contemporary / sophisti-pop.",
            "meter": meter_note,
        }

    if len(set(cycle)) <= 2 and len(cycle) >= 2:
        return {
            "style": "**Modal vamp** / groove-centered harmony",
            "feel": "Hypnotic, groove-first — harmony repeats while melody and rhythm develop.",
            "movement": f"Harmony cycles **{' | '.join(cycle[:4])}** with minimal functional change.",
            "signature": "The *groove* and *register* create interest, not chord count.",
            "similar": "Funk, EDM, and modal jam forms.",
            "meter": meter_note,
        }

    if "blues" in g or "blues" in t:
        return {
            "style": "**Blues-based** harmony",
            "feel": "Raw tension, call-and-response, dominant seventh color.",
            "movement": "Dominant seventh stacks and IV–I cadential feeling.",
            "signature": "Blue notes and dominant chords over a steady pulse.",
            "similar": "Blues, blues-rock, and soul grooves.",
            "meter": meter_note,
        }

    return {
        "style": f"**{genre or 'Song-specific'}** harmonic language in **{key}**",
        "feel": "Shape comes from section contrast and how roots move through the form.",
        "movement": f"Primary root motion: **{root_path(cycle, limit=6) or 'see sections below'}**.",
        "signature": "Listen for slash chords, extensions, and where the chorus widens the palette.",
        "similar": "Analysis is tied to *this* chart — not a generic theory template.",
        "meter": meter_note,
    }


def _section_block(
    name: str,
    chords: list[str],
    key: str,
    level: str,
) -> list[str]:
    role = section_role(name)
    cycle = single_progression_cycle(chords)
    if not cycle:
        return [f"### {name}", "- No chords entered for this section."]

    pattern = first_matching_pattern(cycle, key)
    roman = roman_path(cycle, key, 6)
    bass = root_path(cycle, use_bass=True, limit=6)
    chord_str = " · ".join(cycle)

    lines = [f"### {name}", f"**Progression:** {chord_str}"]
    if roman:
        lines.append(f"**Harmonic movement:** {roman} in **{key}**.")

    if role == "verse":
        lines.append(
            "- **Function:** establishes the emotional home — stable storytelling harmony with room to develop."
        )
        if pattern and "vi" in pattern:
            lines.append(
                "- **Direction:** I–vi motion creates a stable center before **IV** lifts the line toward the chorus."
            )
    elif role == "chorus":
        lines.append(
            "- **Function:** main emotional arrival — the harmony should feel wider and more open than the verse."
        )
        lines.append(
            "- **Tension/release:** chorus chords are the *release* after verse setup; land phrases on tonic-family tones."
        )
    elif role == "bridge":
        lines.append(
            "- **Function:** color change — makes the final return to the chorus feel renewed."
        )
    elif role in ("intro", "outro"):
        lines.append(
            "- **Function:** bookends the form — sets expectation (intro) or resolves the journey (outro)."
        )
    else:
        lines.append(f"- **Function:** supports the **{role}** role in the overall form.")

    if "/" in " ".join(cycle):
        lines.append(f"- **Bass motion:** {bass} — the written bass line is part of the identity.")
    lines.append(f"- **Resolution points:** strongest arrivals on **{cycle[0]}** and **{cycle[-1]}** within the loop.")

    if level == "Beginner":
        lines.append(
            f"- **Emotional effect:** keep it simple — sing/play chord roots and 3rds; feel how **{cycle[0]}** feels like home."
        )
    elif level == "Advanced":
        lines.append(
            "- **Emotional effect:** use extensions and approach tones; delayed resolutions make the section feel personal."
        )
    else:
        lines.append(
            "- **Emotional effect:** contrast register and dynamics here vs other sections — harmony repeats, *performance* creates lift."
        )

    return lines


def _tension_release_section(cycle: list[str], key: str) -> list[str]:
    lines = ["## Tension & Release"]
    if not cycle:
        lines.append("- Add chords to see tension maps.")
        return lines
    for i, ch in enumerate(cycle[:8]):
        nxt = cycle[(i + 1) % len(cycle)] if len(cycle) > 1 else ""
        label = _chord_tension_label(ch, nxt, key)
        if "/" in str(ch) and nxt:
            lines.append(f"- **{ch}** → **{nxt}**: {label}.")
        elif "7" in str(ch).lower() and "maj7" not in str(ch).lower():
            lines.append(f"- **{ch}**: dominant pull — resolves toward the next chord in the loop.")
        elif "sus" in str(ch).lower() or "add" in str(ch).lower():
            lines.append(f"- **{ch}**: open, modern color — {label}.")
        else:
            lines.append(f"- **{ch}**: {label.capitalize()}.")
    if len(cycle) >= 2:
        lines.append(
            f"- **Cadence feel:** returning to **{cycle[0]}** after **{cycle[-1]}** completes the emotional cycle."
        )
    return lines


def _voice_leading_section(
    section_map: list[tuple[str, list[str]]],
    instrument: str,
    level: str,
) -> list[str]:
    lines = ["## Voice Leading"]
    inst = (instrument or "").lower()
    if any(x in inst for x in ("sax", "trumpet", "flute", "clarinet", "voice")):
        lines.append(
            "For winds/voice: think in **lines**, not scales — connect chord 3rds and 7ths, breathe at section peaks."
        )
    elif "piano" in inst:
        lines.append("For piano: keep the top voice smooth; let inner notes move stepwise while bass anchors the form.")
    elif "guitar" in inst:
        lines.append("For guitar: favor nearby chord tones on adjacent strings; let slash bass notes match the chart.")
    elif "bass" in inst:
        lines.append("For bass: the written bass notes *are* the voice leading — connect roots and approach tones.")

    pairs: list[tuple[str, str]] = []
    for _sec, chords in section_map:
        cyc = single_progression_cycle(chords)
        for i in range(len(cyc) - 1):
            pairs.append((cyc[i], cyc[i + 1]))
        if len(cyc) >= 2:
            pairs.append((cyc[-1], cyc[0]))

    seen: set[tuple[str, str]] = set()
    for a, b in pairs:
        if (a, b) in seen:
            continue
        seen.add((a, b))
        lines.append(f"- {_voice_lead_pair(a, b)}")
        if len(seen) >= 6:
            break

    if level == "Beginner":
        lines.append("- **Practice:** play only roots and 3rds through each move above — one note per beat.")
    elif level == "Advanced":
        lines.append(
            "- **Practice:** add chromatic approaches to the 3rd of each target chord; delay resolution by half a beat."
        )
    return lines


def _harmonic_idea_section(
    character: dict[str, str],
    cycle: list[str],
    title: str,
) -> list[str]:
    lines = ["## Harmonic Idea — Why It Sounds Like This"]
    lines.append(f"- **Character:** {character.get('signature', '')}")
    lines.append(f"- **Atmosphere:** {character.get('feel', '')}")

    colors: list[str] = []
    joined = " ".join(cycle).lower()
    if "add9" in joined or "add2" in joined:
        colors.append("**add9/add2** chords add open, singer-songwriter brightness without jazz density.")
    if "sus" in joined:
        colors.append("**Sus** chords create floating, unresolved color — great for builds before a chorus.")
    if "maj7" in joined or "maj9" in joined:
        colors.append("**Maj7/maj9** extensions feel dreamy and polished — emotional softness.")
    if "m7" in joined and "m7b5" not in joined:
        colors.append("**Minor 7** colors feel soulful and relaxed — less tragic than plain minor triads.")
    if "/" in joined:
        colors.append("**Slash chords** make the bass sing — the progression *moves* even when chords repeat.")
    if not colors:
        colors.append(
            "The progression relies on clear triads/sevenths — make it musical with dynamics, register, and phrasing."
        )
    lines.extend(f"- {c}" for c in colors[:5])

    if title:
        lines.append(f"- **On *{title}*:** the recognizable sound is this exact chord sequence in performance — not abstract theory.")
    return lines


def _instrument_lens(
    inp: HarmonicAnalysisInput,
    section_map: list[tuple[str, list[str]]],
) -> list[str]:
    inst = inp.instrument or "Guitar"
    low = inst.lower()
    level = inp.level or "Intermediate"
    key = inp.display_key
    lines = [f"## Instrument-Specific Lens — {inst} ({level})"]

    chorus_chords = ""
    for name, chs in section_map:
        if section_role(name) == "chorus" and chs:
            chorus_chords = " · ".join(single_progression_cycle(chs)[:4])
            break

    if "guitar" in low:
        lines.append(
            "- Use **compact voicings** in the verse (middle strings); open the voicing width in the chorus."
        )
        if chorus_chords:
            lines.append(f"- Chorus target shapes: **{chorus_chords}** — let the top note of each chord sing.")
        if "/" in " ".join(inp.progression_flat or []):
            lines.append("- **Slash bass:** play the written bass note on the lowest string — do not replace with a root shape.")
        if level == "Beginner":
            lines.append("- Capo only if it helps you *sing* in your range — keep the same chord *names* as the chart.")
        elif level == "Advanced":
            lines.append("- Try upper-structure color (9ths) on one chord per chorus — not every bar.")
    elif "piano" in low:
        lines.append("- **LH:** roots or shell (root + 7th); **RH:** 3rd + 7th + optional extension.")
        lines.append("- Verse: shell voicings; chorus: spread RH or octave double for lift.")
        if level == "Advanced":
            lines.append("- Reharm experiment: substitute **V** with secondary dominant only in the bridge, not the main loop.")
    elif "bass" in low:
        lines.append("- Outline **roots first**, then add passing tones approaching the next chord's root.")
        lines.append("- Groove consistency matters more than note count — lock with the kick in 6/8 or 4/4.")
    elif any(x in low for x in ("sax", "trumpet", "flute", "clarinet")):
        lines.append("- **Target notes:** 3rds and 7ths on strong beats; chord roots on downbeats when outlining harmony.")
        lines.append("- **Phrasing:** 2-bar questions, 2-bar answers; breathe *before* the chorus entrance.")
        if level == "Beginner":
            lines.append(f"- Stay in **{key} major** (or relative minor) until chord tones feel automatic.")
        else:
            lines.append("- Use guide-tone lines from the Voice Leading section as your practice etude.")
    elif "voice" in low:
        lines.append("- Mark breaths before chorus lines; harmony tells you when to widen vowels (chorus arrival).")
    else:
        lines.append("- Connect each phrase to the nearest chord tone of the moment — harmony moves, your line should follow.")

    focus = (inp.focus or "").lower()
    if "rhythm" in focus:
        lines.append("- **Focus = Rhythm:** harmony supports rhythm — practice the chord *rhythm* before adding notes.")
    elif "scale" in focus:
        lines.append("- **Focus = Scales:** use the scale section below, but land on chord tones at cadences.")
    return lines


def _scales_section(
    section_map: list[tuple[str, list[str]]],
    key: str,
    level: str,
) -> list[str]:
    lines = ["## Scales / Modes (general options per section)"]
    lines.append("*Simpler reference — use chord tones on strong beats when improvising.*")
    is_minor_key = str(key).endswith("m")
    parent = key.replace("m", "") if is_minor_key else key
    rel_minor = parent
    if not is_minor_key:
        try:
            idx = CHROMATIC.index(normalize_root(split_chord(parent)[0]))
            rel_minor = CHROMATIC[(idx + 9) % 12] + " minor"
        except ValueError:
            rel_minor = f"{parent} minor"

    for name, chords in section_map[:6]:
        cyc = single_progression_cycle(chords)
        if not cyc:
            continue
        role = section_role(name)
        root0 = chord_root(cyc[0])
        lines.append(f"\n### {name}")
        suggestions: list[str] = []
        if level == "Beginner":
            suggestions = [
                f"{parent} major",
                f"{parent} major pentatonic",
            ]
        elif role == "chorus" and not is_minor_key:
            suggestions = [
                f"{parent} major",
                f"{rel_minor}",
                f"{chord_root(cyc[-1])} mixolydian" if cyc else f"{parent} mixolydian",
            ]
        elif is_minor_key or "m" in str(cyc[0]).lower():
            suggestions = [
                f"{parent} natural minor",
                f"{parent} minor pentatonic",
                f"{root0} dorian",
            ]
        else:
            suggestions = [
                f"{parent} major",
                f"{parent} major pentatonic",
                f"{rel_minor}",
            ]
        for label in suggestions[:3]:
            sug = build_scale_suggestion(label)
            tones = chord_tone_names(cyc[0])
            lines.append(f"- {format_scale_line(sug, tones)}")
    return lines


def build_deep_harmonic_analysis(
  inp: HarmonicAnalysisInput,
) -> str:
    """Full markdown report for the active song."""
    section_map = dedupe_sections_for_display(inp.sections)
    flat = inp.progression_flat or []
    cycle = single_progression_cycle(flat) if flat else []
    if not cycle and section_map:
        cycle = single_progression_cycle(section_map[0][1])

    key = inp.display_key or inp.key_center or "C"
    character = _detect_character(
        cycle,
        key,
        inp.genre,
        inp.song_title,
        inp.time_signature,
    )

    out: list[str] = [
        f"# Deep Harmonic Analyzer — {inp.song_title}",
        f"**Artist:** {inp.artist or '—'} · **Key:** {inp.key_center} → **Display:** {key}",
        f"**Instrument:** {inp.instrument} · **Level:** {inp.level} · **Focus:** {inp.focus}",
    ]
    if inp.bpm:
        out.append(f"**Tempo reference:** ~{inp.bpm} BPM")
    if inp.time_signature:
        out.append(f"**Meter:** {inp.time_signature}")
    if inp.arrangement_notes:
        out.append(f"\n> {inp.arrangement_notes[:400]}{'…' if len(inp.arrangement_notes) > 400 else ''}")

    out.append("\n## Harmonic Character")
    out.append(f"- **Style:** {character.get('style', '')}")
    out.append(f"- **Emotional feel:** {character.get('feel', '')}")
    out.append(f"- **How it moves:** {character.get('movement', '')}")
    out.append(f"- **What makes it recognizable:** {character.get('signature', '')}")
    if character.get("similar"):
        out.append(f"- **Comparison:** {character['similar']}")
    if character.get("meter"):
        out.append(character["meter"])

    out.append("\n## Section Function & Movement")
    if not section_map:
        out.append("- No sections in the active chart — select a song or build a custom progression.")
    for name, chords in section_map:
        out.extend(_section_block(name, chords, key, inp.level))

    out.extend(_voice_leading_section(section_map, inp.instrument, inp.level))
    out.extend(_tension_release_section(cycle, key))
    out.extend(_harmonic_idea_section(character, cycle, inp.song_title))
    out.extend(_instrument_lens(inp, section_map))
    out.extend(_scales_section(section_map, key, inp.level))

    return "\n".join(out)


def build_from_improv_context(
    ctx: ImprovSessionContext,
    *,
    genre: str = "",
    time_signature: str = "",
    arrangement_notes: str = "",
) -> str:
    return build_deep_harmonic_analysis(
        HarmonicAnalysisInput(
            song_title=ctx.song_title,
            artist=ctx.artist,
            key_center=ctx.key_center,
            display_key=ctx.display_key,
            sections=ctx.sections,
            instrument=ctx.instrument,
            level=ctx.level,
            focus=ctx.focus,
            genre=genre or ctx.style_label,
            bpm=ctx.bpm,
            time_signature=time_signature,
            arrangement_notes=arrangement_notes,
            progression_flat=list(ctx.progression_flat or []),
        )
    )


def build_from_lab_context(ctx: dict[str, Any]) -> str:
    """Adapter for Creative Lab `current_song_context_lab()` dict."""
    sections = ctx.get("sections") or {}
    flat: list[str] = []
    for _n, chs in sections.items():
        flat.extend(chs or [])
    ext = ctx.get("extensions") or {}
    return build_deep_harmonic_analysis(
        HarmonicAnalysisInput(
            song_title=str(ctx.get("song") or "Song"),
            artist=str(ctx.get("artist") or ""),
            key_center=str(ctx.get("key") or ""),
            display_key=str(ctx.get("display_key") or ctx.get("key") or "C"),
            sections=sections,
            instrument=str(ctx.get("instrument") or "Guitar"),
            level=str(ctx.get("level") or "Intermediate"),
            focus=str(ctx.get("focus") or "Improvisation"),
            genre=str(ctx.get("genre") or ""),
            bpm=int(ctx.get("bpm") or ext.get("default_bpm") or 0),
            time_signature=str(ext.get("time_signature") or ctx.get("time_signature") or ""),
            arrangement_notes=str(ext.get("arrangement_notes") or ctx.get("arrangement_notes") or ""),
            progression_flat=flat,
        )
    )
