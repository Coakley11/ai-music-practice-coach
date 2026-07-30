"""Instrument × level × focus personalization for Deep Harmonic Analyzer lessons."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deep_harmonic_analyzer import HarmonicAnalysisInput


def _normalize_level(level: str) -> str:
    low = str(level or "").strip().lower()
    if "begin" in low:
        return "Beginner"
    if "adv" in low:
        return "Advanced"
    return "Intermediate"


def _instrument_family(instrument: str) -> str:
    from deep_harmonic_analyzer import instrument_family

    return instrument_family(instrument)


def normalize_focus(focus: str) -> str:
    low = str(focus or "").strip().lower()
    if any(w in low for w in ("strum", "rhythm guitar", "groove", "pocket")):
        return "strumming"
    if any(w in low for w in ("voic", "inversion", "comp", "reharm", "voice lead", "left-hand")):
        return "voicings"
    if any(w in low for w in ("ear", "listen", "sing root", "cadence")):
        return "ear_training"
    if any(w in low for w in ("improv", "solo", "melodic", "phrase", "bebop")):
        return "improvisation"
    return "general"


def _focus_headline(focus_key: str) -> str:
    return {
        "strumming": "groove, accents, muting, and feel",
        "voicings": "inversions, voice leading, extensions, and spacing",
        "improvisation": "melodic targets, guide tones, phrases, and tension/release",
        "ear_training": "hearing roots, resolutions, cadences, and chord color",
        "general": "musicality that matches your current goal",
    }.get(focus_key, "your practice goal")


def personalized_greeting(inp: "HarmonicAnalysisInput", character: dict[str, str]) -> str:
    level = _normalize_level(inp.level)
    inst = inp.instrument or "your instrument"
    song = inp.song_title or "this song"
    key = inp.display_key or inp.key_center or "C"
    focus_key = normalize_focus(inp.focus)
    feel = character.get("feel") or "the mood of this chart"
    headline = _focus_headline(focus_key)

    return (
        f"Hey — let's work on **{song}** in **{key}** together. "
        f"I'm tailoring this lesson for **{inst}** at **{level}** level, with your focus on "
        f"**{inp.focus or 'musicality'}** ({headline}). "
        f"Right now the harmony feels like *{feel}* — we'll take it one step at a time."
    )


def personalized_priorities(
    inp: "HarmonicAnalysisInput",
    base: list[str],
    *,
    cycle: list[str],
) -> list[str]:
    level = _normalize_level(inp.level)
    inst = inp.instrument or "your instrument"
    focus_key = normalize_focus(inp.focus)
    family = _instrument_family(inst)
    home = cycle[0] if cycle else "home"
    extra: list[str] = []

    if focus_key == "strumming":
        extra.append(
            "**Groove first:** steady time, clear downbeats, and intentional muting matter more than extra notes."
        )
        if family == "guitar":
            extra.append(
                "Treat each chord change as a **rhythm event** — practice the strum pattern before you worry about extensions."
            )
    elif focus_key == "voicings":
        extra.append(
            "**Voice leading wins:** the top note and inner lines should move smoothly — avoid jumping the whole hand every bar."
        )
        if family == "piano":
            extra.append("Shells in the left hand, color in the right — add extensions only when the groove is locked.")
    elif focus_key == "improvisation":
        extra.append(
            f"**Land on chord tones** on strong beats — especially when **{home}** arrives, let your phrase rest there."
        )
        if family == "wind":
            extra.append("Phrase like speech: breathe, articulate clearly, and aim for one melodic idea per loop.")
    elif focus_key == "ear_training":
        extra.append("**Sing the roots** out loud while you play — if you can hear the harmony, your fingers will follow.")
        extra.append("When a chord feels like it *wants* to move, notice whether it resolves or keeps tension.")

    if level == "Beginner" and family == "guitar" and focus_key == "strumming":
        extra.append("Master **two strum patterns** (straight + one syncopated) before adding fills.")
    elif level == "Advanced" and family == "piano" and focus_key == "voicings":
        extra.append("Experiment with **upper extensions** and reharm colors one chord per pass — not all at once.")
    elif level == "Intermediate" and family == "wind" and focus_key == "improvisation":
        extra.append("Use **guide tones** (3rd & 7th) as melodic targets across each change.")

    merged = list(base)
    for line in extra:
        if line not in merged:
            merged.append(line)
    return merged[:6]


def adapt_lesson_steps(
    inp: "HarmonicAnalysisInput",
    steps: list[dict[str, Any]],
    *,
    cycle: list[str],
) -> list[dict[str, Any]]:
    """Inject focus- and instrument-specific callouts into the guided steps."""
    if not steps:
        return steps
    level = _normalize_level(inp.level)
    inst = inp.instrument or "your instrument"
    focus_key = normalize_focus(inp.focus)
    family = _instrument_family(inst)
    home = cycle[0] if cycle else "the home chord"
    out = [dict(s) for s in steps]

    focus_callout: dict[str, str] | None = None
    if focus_key == "strumming":
        focus_callout = {
            "kind": "try",
            "body": "Loop the progression and exaggerate **accents** on beats 2 & 4 (or the backbeat your style uses). "
            "Add left-hand muting between strums so the groove stays tight.",
        }
    elif focus_key == "voicings":
        focus_callout = {
            "kind": "try",
            "body": "Move to the next chord using the **closest inversion** — keep common tones ringing when you can.",
        }
    elif focus_key == "improvisation":
        focus_callout = {
            "kind": "try",
            "body": f"Improvise one chorus using only **guide tones**; on **{home}**, let the phrase **come to rest**.",
        }
    elif focus_key == "ear_training":
        focus_callout = {
            "kind": "listen",
            "body": "Sing the root of each chord before you play it — then check if the **quality** (major/minor/dominant) matches what you hear.",
        }

    if focus_callout and len(out) >= 2:
        callouts = list(out[1].get("callouts") or [])
        callouts.insert(0, focus_callout)
        out[1]["callouts"] = callouts

    if family == "guitar" and focus_key == "strumming" and level == "Beginner":
        out[0]["body"] = (
            f"We'll connect **{inp.song_title or 'this song'}** to **chord shapes, rhythm, and clean changes** on guitar — "
            "not theory jargon."
        )
    elif family == "piano" and focus_key == "voicings" and level == "Advanced":
        out[0]["body"] = (
            f"This is a **voicing lab** for **{inp.song_title or 'this song'}** — voice leading, shells, extensions, "
            "and reharm ideas at the piano."
        )
    elif family == "wind" and focus_key == "improvisation":
        out[0]["body"] = (
            f"Think like a **sax teacher**: phrasing, breathing, articulation, and landing **guide tones** through "
            f"**{inp.song_title or 'this song'}**."
        )

    return out


def build_homework(inp: "HarmonicAnalysisInput", *, cycle: list[str]) -> dict[str, Any]:
    level = _normalize_level(inp.level)
    focus_key = normalize_focus(inp.focus)
    inst = inp.instrument or "your instrument"
    tempo = inp.bpm or 80
    home = cycle[0] if cycle else "the home chord"

    tasks: list[str] = [
        f"Play the progression **five times** with steady time at ~{tempo} BPM (use a metronome or backing).",
    ]
    if focus_key == "strumming":
        tasks.append("Practice **one muting pattern** and one **accent pattern** — record 30 seconds of each.")
    elif focus_key == "voicings":
        tasks.append("Voice-lead through the loop using **only shells**; then add one **color tone** per chorus.")
    elif focus_key == "improvisation":
        tasks.append(f"Add **one passing tone** between each chord change, landing on a chord tone on **{home}**.")
    elif focus_key == "ear_training":
        tasks.append("**Sing roots** through the form twice, then play roots once without looking at the chart.")
    else:
        tasks.append(f"On **{inst}**, loop until **{home}** feels like true rest — then add one new idea.")

    if level == "Beginner":
        tasks.append("Record yourself once and listen for **rhythm** before worrying about notes.")
    else:
        tasks.append("Record one take and note where your phrase **settles** vs. still feels restless.")

    tasks.append("Return tomorrow and add **one color tone** (or one rhythmic variation) — not ten.")

    return {"title": "Today's Assignment", "tasks": tasks}


def conversational_character_md(character: dict[str, str], inp: "HarmonicAnalysisInput") -> str:
    feel = character.get("feel") or "grounded and clear"
    movement = character.get("movement") or "stepwise root motion through the form"
    signature = character.get("signature") or "Listen for where the chorus opens up."
    inst = inp.instrument or "your instrument"
    focus_key = normalize_focus(inp.focus)

    lines = [
        f"This song should feel **{feel}** on **{inst}** — let that guide your dynamics before you add complexity.",
        f"The harmony moves like this: {movement}. Follow the bass in your ear when you're unsure.",
        signature,
    ]
    if focus_key == "strumming":
        lines.append("Your job today: make the **groove** feel good even if you only strum roots and fifths.")
    elif focus_key == "voicings":
        lines.append("Ask: *what is the smoothest top voice* I can keep through the next change?")
    elif focus_key == "improvisation":
        lines.append("When a chord arrives, treat it as a **place to land** — not a speed bump.")
    elif focus_key == "ear_training":
        lines.append("Hum the bass line once — you'll hear where the song wants to breathe.")
    return "\n\n".join(lines)


def conversational_section_md(
    name: str,
    chords: list[str],
    key: str,
    level: str,
    inp: "HarmonicAnalysisInput",
) -> str:
    from deep_harmonic_analyzer import section_role, single_progression_cycle

    role = section_role(name)
    cycle = single_progression_cycle(chords)
    if not cycle:
        return f"No chords yet for **{name}** — add changes to unlock this section."

    chord_str = " · ".join(cycle)
    home = cycle[0]
    last = cycle[-1]
    level_norm = _normalize_level(level)

    if role == "verse":
        tone = (
            f"**{name}** should feel relaxed and grounded. Don't rush to add fancy notes yet — "
            f"try making every change feel smooth: **{chord_str}**."
        )
    elif role == "chorus":
        tone = (
            f"**{name}** is the emotional lift — same harmony can feel bigger with **dynamics and space**. "
            f"Loop: **{chord_str}**."
        )
    elif role == "bridge":
        tone = (
            f"**{name}** is your color change — contrast register or articulation so the return to the chorus feels fresh."
        )
    else:
        tone = f"**{name}** supports the story — progression **{chord_str}**."

    landing = (
        f"When **{home}** or **{last}** arrives, let your phrase **come to rest here** — that's where the ear expects resolution."
    )
    if level_norm == "Beginner":
        practice = f"Play roots only through **{name}** three times in a row with a steady count."
    elif level_norm == "Advanced":
        practice = f"One pass: chord tones only. Next pass: one **chromatic approach** into each new chord."
    else:
        practice = f"Sing the roots of **{name}**, then add 3rds on the strong beats."

    focus_key = normalize_focus(inp.focus)
    if focus_key == "strumming":
        practice += " Keep the **strum pattern identical** — change chords without changing the groove."
    elif focus_key == "voicings":
        practice += " Move the **top voice by step** whenever possible."
    elif focus_key == "improvisation":
        practice += " End each mini-phrase on a **chord tone**."
    elif focus_key == "ear_training":
        practice += " Close your eyes for one pass and **name the root** out loud on each change."

    return f"{tone}\n\n{landing}\n\n**Try this:** {practice}"


def chord_tone_visual_html(chord: str) -> str:
    """Mini visual: chord name + role hint (HTML snippet)."""
    import html as html_mod

    ch = html_mod.escape(str(chord or "").strip())
    hint = "home" if ch else ""
    if "7" in ch.lower() and "maj7" not in ch.lower():
        hint = "tension → resolve"
    elif "m" in ch.lower() and not ch.lower().endswith("maj7"):
        hint = "color / minor"
    return (
        f'<span class="dh-chord-chip" title="{html_mod.escape(hint)}">{ch}</span>'
    )
