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
from improvisation_missions import instrument_family
from improvisation_motif import chord_tone_names, dedupe_sections_for_display, single_progression_cycle
from songs.form import section_order
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
    section_order: list[str] = field(default_factory=list)


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
    from music_theory import classify_chord_quality, normalize_chord_for_theory

    q = chord_quality(ch)
    qual = classify_chord_quality(ch)
    if qual == "sus":
        return "suspended color — delays resolution and keeps the phrase hovering"
    if qual == "dom":
        return "dominant tension — wants to resolve forward"
    if qual in ("dim", "half-dim"):
        return "passing tension — short, directional color"
    norm = normalize_chord_for_theory(ch)
    if "/" in norm:
        bass = norm.split("/", 1)[1].strip()
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


def _chord_change_pairs(section_map: list[tuple[str, list[str]]], limit: int = 6) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for _sec, chords in section_map:
        cyc = single_progression_cycle(chords)
        for i in range(len(cyc) - 1):
            pairs.append((cyc[i], cyc[i + 1]))
        if len(cyc) >= 2:
            pairs.append((cyc[-1], cyc[0]))
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for a, b in pairs:
        if (a, b) in seen:
            continue
        seen.add((a, b))
        out.append((a, b))
        if len(out) >= limit:
            break
    return out


def _wind_playbook(
    inp: HarmonicAnalysisInput,
    section_map: list[tuple[str, list[str]]],
    cycle: list[str],
) -> list[str]:
    inst = inp.instrument or "Saxophone"
    key = inp.display_key
    level = inp.level
    focus = (inp.focus or "").lower()
    lines = [f"## {inst} — Melodic & Harmonic Playbook"]

    lines.append("### Target notes & guide tones")
    lines.append(
        "- On each chord change, **aim for the 3rd and 7th** on strong beats — they tell the listener the harmony."
    )
    if cycle:
        tones = chord_tone_names(cycle[0])
        if len(tones) >= 4:
            lines.append(
                f"- Home sonority **{cycle[0]}**: stable targets **{', '.join(tones[:3])}**; "
                f"color with the 7th ({tones[3]}) if the chart includes it."
            )
        elif len(tones) >= 3:
            lines.append(
                f"- Home sonority **{cycle[0]}**: stable targets **{', '.join(tones[:3])}** "
                "(root, 3rd, 5th) — land these chord tones on strong beats."
            )
    lines.append(
        f"- In **{key}**, chord-tone soloing beats running scales — land roots/3rds/5ths first, "
        "then add passing tones between guide tones."
    )

    lines.append("### Melodic voice leading")
    for a, b in _chord_change_pairs(section_map):
        lines.append(f"- {_voice_lead_pair(a, b)}")
    lines.append(
        "- Think **stepwise motion** between chord tones; save leaps for phrase peaks or chorus lift."
    )

    lines.append("### Breath & phrasing")
    lines.append("- **2-bar question, 2-bar answer** — breathe *before* the chorus or after a tension chord.")
    lines.append("- Tongue lighter on faster subdivisions; support long notes with steady air.")
    if "rhythm" in focus:
        lines.append("- **Focus = Rhythm:** lock time first; one rhythm cell per section before adding notes.")

    lines.append("### Articulation")
    if level == "Beginner":
        lines.append("- Keep attacks consistent; accent beat 1 of each bar only.")
    else:
        lines.append("- Mix legato lines with one accented approach note into each new chord.")

    lines.append("### Scales vs chord tones")
    lines.append(
        "- Use the scale list below as a **source pool** — still resolve phrases on chord tones at cadences."
    )
    return lines


def _guitar_playbook(
    inp: HarmonicAnalysisInput,
    section_map: list[tuple[str, list[str]]],
    cycle: list[str],
) -> list[str]:
    level = inp.level
    lines = [f"## Guitar — Fretboard & Harmony Playbook"]

    lines.append("### Chord shapes & string sets")
    if cycle:
        lines.append(
            f"- Core loop: **{' · '.join(cycle[:4])}** — learn one compact grip per chord in the same fretboard zone."
        )
    lines.append("- Verse: middle-string triads; chorus: widen to include high E or bass note on slash chords.")
    if "/" in " ".join(inp.progression_flat or []):
        lines.append("- **Slash bass:** keep the written bass on the lowest string — do not replace with a root-only grip.")

    lines.append("### Voice leading on the neck")
    for a, b in _chord_change_pairs(section_map):
        lines.append(f"- {_voice_lead_pair(a, b)} — find the nearest grip; move the **top voice** by step when possible.")
    lines.append("- TAB idea: arpeggiate each chord once per bar, then add one passing tone on beat 4.")

    lines.append("### Picking & rhythm")
    lines.append("- Match the song groove first; muting on 2 & 4 can make the verse feel intimate.")
    if level == "Advanced":
        lines.append("- Add 9ths on one chorus pass only — same rhythm, one higher color note per chord.")

    lines.append("### Improvising")
    lines.append(
        "- Target chord tones on downbeats; use pentatonic/major scale fills between chord grips in the same position."
    )
    return lines


def _piano_playbook(
    inp: HarmonicAnalysisInput,
    section_map: list[tuple[str, list[str]]],
    cycle: list[str],
) -> list[str]:
    level = inp.level
    lines = [f"## Piano — Voicing Playbook"]

    lines.append("### LH / RH roles")
    lines.append("- **Left hand:** root + 5th or shell (root + 7th) — anchor the harmony.")
    lines.append("- **Right hand:** 3rd + 7th + optional 9th — this is your melodic top voice.")
    if cycle:
        lines.append(f"- Verse colors: **{' · '.join(cycle[:4])}** with shell voicings; chorus: spread RH or octave double.")

    lines.append("### Voice leading & inversions")
    for a, b in _chord_change_pairs(section_map):
        lines.append(f"- {_voice_lead_pair(a, b)} — move the **top note** stepwise; keep LH on root or shell.")
    lines.append("- Use inversions to avoid jumping the RH more than a 4th between chords.")

    lines.append("### Chord-tone improvising")
    lines.append("- RH melodic lines: chord tones on beats 1 and 3; passing tones on weaker beats.")
    if level == "Advanced":
        lines.append("- Try upper structures (9, 13) on dominant chords only — one color per chorus.")

    lines.append("### Voicing suggestions")
    lines.append("- Ballad: light pedal; change pedal on root movement, not every inner voice shift.")
    return lines


def _bass_playbook(
    inp: HarmonicAnalysisInput,
    section_map: list[tuple[str, list[str]]],
    cycle: list[str],
) -> list[str]:
    lines = ["## Bass — Line & Groove Playbook"]
    lines.append("- The written bass notes **are** the harmony — connect roots with stepwise or chromatic approaches.")
    if cycle:
        lines.append(f"- Outline: **{' → '.join(cycle[:4])}** — lock with the kick; add passing tones into each root.")
    lines.append("- Chorus: slightly more forward in the mix; verse: leave space for vocal/melody.")
    return lines


def _generic_playbook(
    inp: HarmonicAnalysisInput,
    section_map: list[tuple[str, list[str]]],
) -> list[str]:
    lines = [f"## Improvisation on **{inp.song_title}**"]
    for a, b in _chord_change_pairs(section_map):
        lines.append(f"- {_voice_lead_pair(a, b)}")
    lines.append("- Connect chord tones on strong beats; use the scale section for pitch choices.")
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


def _scales_section(
    section_map: list[tuple[str, list[str]]],
    key: str,
    level: str,
    *,
    instrument: str = "Guitar",
) -> list[str]:
    family = instrument_family(instrument)
    lines = ["## Scales / Modes (per section)"]
    if family == "wind":
        lines.append("*Pool of pitches — still land on chord tones and guide tones at phrase endings.*")
    elif family == "guitar":
        lines.append("*Use in the same fretboard area as your chord grips — chord tones on downbeats.*")
    elif family == "piano":
        lines.append("*RH lines from these sets; LH stays on shells/voicings.*")
    else:
        lines.append("*Use chord tones on strong beats when improvising.*")
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


def _normalize_level(level: str) -> str:
    low = str(level or "").strip().lower()
    if "begin" in low:
        return "Beginner"
    if "adv" in low:
        return "Advanced"
    return "Intermediate"


def _coach_opening(inp: HarmonicAnalysisInput, character: dict[str, str]) -> list[str]:
    """First-person coach intro — adapts to instrument, level, focus, and song."""
    level = _normalize_level(inp.level)
    inst = inp.instrument or "your instrument"
    focus = (inp.focus or "improvisation").strip()
    song = inp.song_title or "this song"
    feel = character.get("feel") or "the mood of the chart"
    key = inp.display_key or inp.key_center or "C"

    if level == "Beginner":
        return [
            f"Let's walk through **{song}** together in **{key}** — I'll keep the theory light and give you "
            f"clear steps on **{inst}** so you can *feel* the harmony, not memorize labels.",
            f"> **Practice tip:** Set a slow tempo (~{inp.bpm or 80} BPM). Play one chord at a time and name "
            f"the root out loud before you add anything else.",
        ]
    if level == "Advanced":
        return [
            f"**{song}** in **{key}** — {feel}. On **{inst}**, we'll treat this as a living progression: "
            f"function, color, substitutions, and how you'd *improvise* through it with intention.",
            f"> **Try this:** Loop one section and solo using only guide tones — then add one substitution "
            f"color per chorus while keeping your **{focus}** front and center.",
        ]
    return [
        f"Here's how I'd teach **{song}** to a **{inst}** student at your level — key **{key}**, "
        f"focus on **{focus}**. We'll connect *why* the chords work to *what* you should practice.",
        f"> **Key takeaway:** {character.get('signature') or 'The recognizable sound lives in how the bass and top voice move between chords.'}",
    ]


def _practice_steps_for_level(inp: HarmonicAnalysisInput, cycle: list[str]) -> list[str]:
    level = _normalize_level(inp.level)
    home = cycle[0] if cycle else "the home chord"
    lines = ["\n## Your practice plan"]
    if level == "Beginner":
        lines.extend(
            [
                "> **Try this:** Play the root of each chord on beat 1 for one full pass — no fills yet.",
                "> **Try this:** Add the 3rd on beat 3; keep the same rhythm for every bar.",
                f"> **Practice tip:** When you return to **{home}**, let it breathe — that's your musical “home base.”",
            ]
        )
    elif level == "Advanced":
        lines.extend(
            [
                "> **Try this:** Improvise one chorus using only chord tones, one using approach tones into 3rds/7ths.",
                "> **Try this:** On the repeat, substitute one dominant color (b9, #11, or sus) before resolving.",
                "> **Practice tip:** Record yourself — compare whether tension chords *release* where you expect.",
            ]
        )
    else:
        lines.extend(
            [
                f"> **Try this:** Map the 3rd and 7th of **{home}** on your **{inp.instrument}**, then find the nearest "
                "shape for the next chord without jumping registers.",
                "> **Practice tip:** Sing the roots while you play — if you can sing the harmony, you can improvise on it.",
            ]
        )
    return lines


def _cycle_tuple(chords: list[str]) -> tuple[str, ...]:
    return tuple(single_progression_cycle(chords or []))


def _detect_shared_loop(
    section_map: list[tuple[str, list[str]]],
) -> tuple[list[str], bool, int]:
    cycles = [_cycle_tuple(ch) for _n, ch in section_map if ch]
    if not cycles:
        return [], False, 0
    from collections import Counter

    counts = Counter(cycles)
    main, n = counts.most_common(1)[0]
    repeating = n >= 2 or len(counts) == 1
    return list(main), repeating, n


def _priority_concepts(
    inp: HarmonicAnalysisInput,
    cycle: list[str],
    *,
    repeating: bool,
    character: dict[str, str],
) -> list[str]:
    concepts: list[str] = []
    song = inp.song_title or "this song"
    inst = inp.instrument or "your instrument"
    level = _normalize_level(inp.level)
    loop_str = " · ".join(cycle[:6])

    if repeating and cycle and len(cycle) <= 6:
        concepts.append(
            f"This is a **repeating {len(cycle)}-chord loop** ({loop_str}) — it drives most of **{song}**."
        )
    elif cycle:
        concepts.append(f"Core progression: **{loop_str}** — learn this path before adding extras.")

    if cycle:
        concepts.append(f"**{cycle[0]}** feels like *home* — your ear expects phrases to settle there.")

    genre_low = (inp.genre or character.get("style") or "").lower()
    if any(w in genre_low for w in ("pop", "edm", "dance", "groove", "funk")) or "groove" in (
        character.get("feel") or ""
    ).lower():
        concepts.append("The **groove** matters more than fancy harmony — time feel comes first.")
    elif level == "Beginner":
        concepts.append("Keep the **rhythm steady** — simple chords in time beat clever notes.")

    if level != "Beginner" and len(cycle) >= 2:
        concepts.append(
            "**Smooth voice leading** between chord tones will make the loop sound professional on "
            f"{inst}."
        )

    if level == "Beginner":
        concepts.append("**Master this loop before worrying about scales** — chord tones carry the melody.")
    elif level == "Advanced":
        concepts.append("When the loop is automatic, add **color tones and approach notes** one pass at a time.")
    else:
        concepts.append("Spend most of your practice time on this loop — it pays off across the whole form.")

    return concepts[:5]


def _section_diff_notes(
    section_map: list[tuple[str, list[str]]],
    main_cycle: list[str],
) -> list[dict[str, str]]:
    main_t = _cycle_tuple(main_cycle)
    diffs: list[dict[str, str]] = []
    same = 0
    for name, chords in section_map:
        cyc = _cycle_tuple(chords)
        if not cyc:
            continue
        if cyc == main_t:
            same += 1
            continue
        role = section_role(name)
        diffs.append(
            {
                "name": name,
                "note": f"**{role.title()}** uses a different path: {' · '.join(cyc)} — compare to the main loop.",
            }
        )
    if same >= 2 and not diffs:
        return [
            {
                "name": "Form",
                "note": "Sections share the **same harmonic loop** — you do not need to relearn the progression "
                "for each pass. Focus on *expression* and dynamics instead.",
            }
        ]
    return diffs


def _lesson_steps(
    inp: HarmonicAnalysisInput,
    cycle: list[str],
    *,
    repeating: bool,
    priorities: list[str],
    section_diffs: list[dict[str, str]],
) -> list[dict[str, Any]]:
    level = _normalize_level(inp.level)
    inst = inp.instrument or "your instrument"
    home = cycle[0] if cycle else "the home chord"
    loop_line = " · ".join(cycle) if cycle else "(add chords to begin)"

    steps: list[dict[str, Any]] = [
        {
            "title": "Let's learn this song together",
            "body": (
                f"I'll keep us focused on what matters most for **{inp.song_title}** on **{inst}**. "
                "We will take it one step at a time — play each step before moving on."
            ),
            "callouts": [
                {"kind": "goal", "body": priorities[0] if priorities else "Hear the form before analyzing it."},
            ],
        },
        {
            "title": "Meet the loop",
            "body": (
                f"{'This progression repeats across the song' if repeating else 'Start with the core progression'}. "
                f"Loop: **{loop_line}**."
            ),
            "callouts": [
                {
                    "kind": "try",
                    "body": f"Play only the roots of each chord in order. Don't worry about scales yet — "
                    f"feel how **{home}** feels like home.",
                },
                {
                    "kind": "listen",
                    "body": "Listen for when the harmony feels settled (home) vs. when it wants to move forward.",
                },
            ],
        },
        {
            "title": "Make it feel good",
            "body": (
                "Once roots are easy, connect **3rds** (and 7ths if you hear them). "
                "Let your top note move by step when the chord changes."
            ),
            "callouts": [
                {
                    "kind": "try",
                    "body": "Loop the progression slowly and hold one chord tone per bar — no extra fills.",
                },
                {
                    "kind": "mistake",
                    "body": "Rushing to solo before the groove is steady — the pocket carries this song.",
                },
            ],
        },
    ]

    if section_diffs and not (len(section_diffs) == 1 and section_diffs[0]["name"] == "Form"):
        steps.append(
            {
                "title": "What actually changes between sections",
                "body": "The harmony mostly repeats — here is what is different section to section.",
                "callouts": [{"kind": "tip", "body": d["note"]} for d in section_diffs[:3]],
            }
        )
    elif repeating:
        steps.append(
            {
                "title": "Same chords, new energy",
                "body": "Because the loop repeats, your job is **performance** — dynamics, articulation, and space.",
                "callouts": [
                    {
                        "kind": "tip",
                        "body": "This progression repeats almost the entire song — time here gives the biggest payoff.",
                    },
                    {
                        "kind": "try",
                        "body": "Play the loop whisper-quiet, then once at full chorus energy. Same notes, different story.",
                    },
                ],
            }
        )

    if level != "Beginner":
        steps.append(
            {
                "title": "When you're ready for more color",
                "body": "Open **Go deeper** below for tension maps, instrument playbook, and scale pools.",
                "callouts": [
                    {
                        "kind": "tip",
                        "body": "Once this feels easy, we'll add color tones — one new idea per practice session.",
                    },
                ],
            }
        )
    else:
        steps.append(
            {
                "title": "Next session",
                "body": "When the loop feels easy in time, come back for the deeper theory sections below.",
                "callouts": [
                    {"kind": "goal", "body": "Comfortable looping the progression at performance tempo with steady rhythm."},
                ],
            }
        )

    return steps


def _build_reference_cards(
    inp: HarmonicAnalysisInput,
    section_map: list[tuple[str, list[str]]],
    cycle: list[str],
    character: dict[str, str],
    level_norm: str,
) -> list[dict[str, Any]]:
    """Structured reference cards for collapsible UI (not one long markdown wall)."""
    from deep_harmonic_personalization import conversational_character_md, conversational_section_md

    key = inp.display_key or inp.key_center or "C"
    cards: list[dict[str, Any]] = []

    char_md = conversational_character_md(character, inp)
    cards.append({"kind": "character", "title": "Harmonic Character", "markdown": char_md})

    family = instrument_family(inp.instrument)
    playbook: list[str] = []
    if family == "wind":
        playbook = _wind_playbook(inp, section_map, cycle)
    elif family == "guitar":
        playbook = _guitar_playbook(inp, section_map, cycle)
    elif family == "piano":
        playbook = _piano_playbook(inp, section_map, cycle)
    elif family == "bass":
        playbook = _bass_playbook(inp, section_map, cycle)
    else:
        playbook = _generic_playbook(inp, section_map)
    if playbook:
        cards.append(
            {
                "kind": "playbook",
                "title": f"{inp.instrument} Playbook",
                "markdown": "\n".join(playbook[1:]),
            }
        )

    section_items: list[dict[str, str]] = []
    for name, chords in section_map:
        cyc = single_progression_cycle(chords)
        if not cyc:
            continue
        section_items.append(
            {
                "name": name,
                "markdown": conversational_section_md(name, chords, key, level_norm, inp),
                "chords": " · ".join(cyc),
            }
        )
    if section_items:
        cards.append({"kind": "sections", "title": "Song Sections", "sections": section_items})

    if level_norm != "Beginner":
        tension = "\n".join(_tension_release_section(cycle, key)[1:])
        cards.append({"kind": "tension", "title": "Tension Map", "markdown": tension})

    if level_norm != "Beginner":
        scale_md = "\n".join(_scales_section(section_map, key, level_norm, instrument=inp.instrument)[1:])
        cards.append({"kind": "scales", "title": "Scale Suggestions", "markdown": scale_md})

    return cards


def _build_deep_dive_markdown(
    inp: HarmonicAnalysisInput,
    section_map: list[tuple[str, list[str]]],
    cycle: list[str],
    character: dict[str, str],
    level_norm: str,
) -> list[dict[str, str]]:
    """Appendix sections for expanders — full detail on demand."""
    key = inp.display_key or inp.key_center or "C"
    parts: list[dict[str, str]] = []

    char_lines = [
        f"- **Feel:** {character.get('feel', '')}",
        f"- **Motion:** {character.get('movement', '')}",
        f"- **Signature:** {character.get('signature', '')}",
    ]
    parts.append({"title": "Harmonic character (detail)", "markdown": "\n".join(char_lines)})

    if level_norm != "Beginner":
        tension = "\n".join(_tension_release_section(cycle, key)[1:])
        parts.append({"title": "Tension & release map", "markdown": tension})

    for name, chords in section_map:
        cyc = single_progression_cycle(chords)
        if not cyc:
            continue
        block = "\n".join(_section_block(name, chords, key, level_norm))
        parts.append({"title": f"Section: {name}", "markdown": block})

    family = instrument_family(inp.instrument)
    playbook: list[str] = []
    if family == "wind":
        playbook = _wind_playbook(inp, section_map, cycle)
    elif family == "guitar":
        playbook = _guitar_playbook(inp, section_map, cycle)
    elif family == "piano":
        playbook = _piano_playbook(inp, section_map, cycle)
    elif family == "bass":
        playbook = _bass_playbook(inp, section_map, cycle)
    else:
        playbook = _generic_playbook(inp, section_map)
    if playbook:
        parts.append({"title": f"{inp.instrument} playbook", "markdown": "\n".join(playbook[1:])})

    if level_norm != "Beginner":
        scale_md = "\n".join(_scales_section(section_map, key, level_norm, instrument=inp.instrument)[1:])
        parts.append({"title": "Scale pools (reference)", "markdown": scale_md})

    return parts


def build_deep_harmonic_lesson(inp: HarmonicAnalysisInput) -> dict[str, Any]:
    """Interactive lesson payload for Deep Harmonic Analyzer UI."""
    section_names = list(inp.section_order) if inp.section_order else None
    section_map = dedupe_sections_for_display(
        inp.sections,
        section_names=section_names,
    )
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
    level_norm = _normalize_level(inp.level)
    main_cycle, repeating, _repeat_count = _detect_shared_loop(section_map)
    if main_cycle:
        cycle = main_cycle

    from deep_harmonic_personalization import (
        adapt_lesson_steps,
        build_homework,
        personalized_greeting,
        personalized_priorities,
    )

    priorities = _priority_concepts(inp, cycle, repeating=repeating, character=character)
    priorities = personalized_priorities(inp, priorities, cycle=cycle)
    section_diffs = _section_diff_notes(section_map, cycle)
    steps = _lesson_steps(
        inp,
        cycle,
        repeating=repeating,
        priorities=priorities,
        section_diffs=section_diffs,
    )
    steps = adapt_lesson_steps(inp, steps, cycle=cycle)
    reference_cards = _build_reference_cards(inp, section_map, cycle, character, level_norm)
    homework = build_homework(inp, cycle=cycle)

    return {
        "song_title": inp.song_title,
        "artist": inp.artist,
        "meta": f"{key} · {inp.instrument} · {level_norm} · {inp.focus}",
        "greeting": personalized_greeting(inp, character),
        "priorities": priorities,
        "steps": steps,
        "loop": {"chords": cycle, "repeating": repeating},
        "section_diffs": section_diffs,
        "reference_cards": reference_cards,
        "homework": homework,
        "deep_dive": [
            {"title": c["title"], "markdown": c.get("markdown") or ""}
            for c in reference_cards
            if c.get("markdown")
        ],
    }


def build_deep_harmonic_analysis(
  inp: HarmonicAnalysisInput,
) -> str:
    """Compact markdown export (legacy / diagnostics). UI: ``deep_harmonic_analyzer_ui.render_deep_harmonic_analyzer_tab``."""
    lesson = build_deep_harmonic_lesson(inp)
    lines = [
        f"### {lesson['song_title']}",
        lesson["greeting"],
        "",
        "#### Start here",
    ]
    for p in lesson["priorities"]:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("#### Steps")
    for i, step in enumerate(lesson["steps"], 1):
        lines.append(f"{i}. **{step['title']}** — {step['body']}")
    return "\n".join(lines)


def _legacy_build_deep_harmonic_analysis_full(
  inp: HarmonicAnalysisInput,
) -> str:
    """Legacy full report builder (tests / reference)."""
    section_names = list(inp.section_order) if inp.section_order else None
    section_map = dedupe_sections_for_display(
        inp.sections,
        section_names=section_names,
    )
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
    level_norm = _normalize_level(inp.level)

    out: list[str] = [
        f"### {inp.song_title}",
        f"*{inp.artist}* · practicing in **{key}** · **{inp.instrument}** · **{level_norm}** · **{inp.focus}**",
    ]
    out.extend(_coach_opening(inp, character))
    if inp.bpm:
        out.append(f"\n*Tempo reference: ~{inp.bpm} BPM* · Meter: {inp.time_signature or '4/4'}")
    if inp.arrangement_notes:
        out.append(
            f"\n> **Arrangement note:** {inp.arrangement_notes[:320]}{'…' if len(inp.arrangement_notes) > 320 else ''}"
        )

    out.append("\n## What makes this song tick")
    out.append(f"- **Feel:** {character.get('feel', '')}")
    out.append(f"- **Motion:** {character.get('movement', '')}")
    out.append(f"- **Signature:** {character.get('signature', '')}")
    if character.get("similar"):
        out.append(f"- **If you know:** {character['similar']}")
    if character.get("meter"):
        out.append(character["meter"])

    out.append("\n## Section by section")
    if not section_map:
        out.append("> **Practice tip:** Select a song with a chart, or build a custom progression — I'll walk you through it section by section.")
    for name, chords in section_map:
        out.extend(_section_block(name, chords, key, level_norm))

    if level_norm != "Beginner":
        out.extend(_tension_release_section(cycle, key))
    else:
        out.append("\n## Tension & release (simple view)")
        if cycle:
            out.append(
                f"> **Key takeaway:** Chords that feel “unfinished” (often with **7** in the symbol) want to move forward; "
                f"**{cycle[0]}** is where the loop feels like home."
            )

    out.extend(_harmonic_idea_section(character, cycle, inp.song_title))
    out.extend(_practice_steps_for_level(inp, cycle))

    family = instrument_family(inp.instrument)
    if family == "wind":
        out.extend(_wind_playbook(inp, section_map, cycle))
    elif family == "guitar":
        out.extend(_guitar_playbook(inp, section_map, cycle))
    elif family == "piano":
        out.extend(_piano_playbook(inp, section_map, cycle))
    elif family == "bass":
        out.extend(_bass_playbook(inp, section_map, cycle))
    else:
        out.extend(_generic_playbook(inp, section_map))

    if level_norm != "Beginner":
        out.extend(_scales_section(section_map, key, level_norm, instrument=inp.instrument))
    else:
        out.append("\n## Scales (when you're ready)")
        out.append(
            "> **Practice tip:** Stay on chord roots and 3rds first — add scale runs only after the form feels comfortable."
        )

    focus = (inp.focus or "").lower()
    if "rhythm" in focus:
        out.append(
            f"\n> **Focus — Rhythm:** Lock the groove of **{inp.song_title}** before adding notes. "
            "Clap the chord rhythm, then play roots only."
        )
    elif "harmony" in focus or "chord" in focus or "voicing" in focus:
        out.append(
            "\n> **Focus — Harmony:** Prioritize 3rds and 7ths — they tell the listener the chord quality. "
            "Resolve phrases on chord tones at cadences."
        )
    elif "improv" in focus:
        out.append(
            "\n> **Focus — Improvisation:** Aim for one clear idea per chorus — repeat it, then vary it on the next pass."
        )

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
    section_names = list(ctx.get("section_order") or [])
    flat: list[str] = []
    for _n, chs in section_order(sections, section_names=section_names or None):
        flat.extend(chs or [])
    ext = ctx.get("extensions") or {}
    return build_deep_harmonic_analysis(
        HarmonicAnalysisInput(
            song_title=str(ctx.get("song") or "Song"),
            artist=str(ctx.get("artist") or ""),
            key_center=str(
                ctx.get("practice_concert_key") or ctx.get("concert_key") or ctx.get("key") or "C"
            ),
            display_key=str(ctx.get("chart_key") or ctx.get("display_key") or ctx.get("key") or "C"),
            sections=sections,
            section_order=section_names,
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
