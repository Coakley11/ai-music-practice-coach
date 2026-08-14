"""Instrument-aware coaching language for Music Coach instant solvers."""

from __future__ import annotations


def instrument_family(instrument: str) -> str:
    """Map a display instrument name to a coaching voice family."""
    low = str(instrument or "").lower()
    if any(x in low for x in ("voice", "vocal", "singer", "karaoke")):
        return "voice"
    if any(
        x in low
        for x in (
            "sax",
            "flute",
            "clarinet",
            "oboe",
            "trumpet",
            "horn",
            "trombone",
            "tuba",
            "flugel",
        )
    ):
        return "wind"
    if any(x in low for x in ("piano", "keyboard", "keys", "organ", "synth")):
        return "keyboard"
    if "bass" in low:
        return "bass"
    if any(x in low for x in ("guitar", "ukulele", "banjo", "mandolin")):
        return "fretted"
    if any(x in low for x in ("drum", "percussion", "cajon")):
        return "percussion"
    return "general"


def practice_plan_profile(
    instrument: str,
    *,
    chord_focus: bool,
) -> tuple[dict[str, float], str]:
    fam = instrument_family(instrument)
    if fam == "wind":
        if chord_focus:
            return (
                {
                    "harmonic outline / arpeggios": 0.30,
                    "melodic contour & phrasing": 0.30,
                    "rhythm & articulation": 0.25,
                    "full run-through": 0.15,
                },
                "Connect each harmonic shift to a clear melodic target while keeping tone and breath steady.",
            )
        return (
            {
                "long tones & tone production": 0.25,
                "melodic contour & phrasing": 0.30,
                "rhythm & articulation": 0.25,
                "full run-through": 0.20,
            },
            "Prioritize lyrical phrasing, breath control, and tone before pushing tempo.",
        )
    if fam == "voice":
        if chord_focus:
            return (
                {
                    "pitch & interval accuracy": 0.30,
                    "lyric phrasing & vowels": 0.30,
                    "dynamics (verse vs chorus)": 0.25,
                    "full run-through": 0.15,
                },
                "Lock in pitch on each chord change before adding expressive dynamics.",
            )
        return (
            {
                "breath & support": 0.25,
                "lyric phrasing & vowels": 0.30,
                "dynamics & storytelling": 0.25,
                "full run-through": 0.20,
            },
            "Build breath support and vowel clarity before chasing full-tempo delivery.",
        )
    if fam == "keyboard":
        if chord_focus:
            return (
                {
                    "chord voicings & transitions": 0.35,
                    "left-hand pulse / bass movement": 0.25,
                    "melody & right-hand balance": 0.25,
                    "full run-through": 0.15,
                },
                "Prioritize clean voicings and voice-leading before speed.",
            )
        return (
            {
                "technique & hand independence": 0.30,
                "rhythm & groove": 0.25,
                "repertoire section": 0.25,
                "full run-through": 0.20,
            },
            "Balance hand independence, time feel, and musical run-throughs.",
        )
    if fam == "fretted":
        if chord_focus:
            return (
                {
                    "chord transitions": 0.40,
                    "rhythm / strumming or picking": 0.30,
                    "melody / licks": 0.20,
                    "full run-through": 0.10,
                },
                "Prioritize clean chord changes before speed.",
            )
        return (
            {
                "technique / drills": 0.35,
                "rhythm / groove": 0.25,
                "repertoire section": 0.25,
                "full run-through": 0.15,
            },
            "Balance technique, time feel, and musical run-throughs.",
        )
    if fam == "bass":
        return (
            {
                "groove & note length": 0.30,
                "root movement & chord tones": 0.30,
                "lock with the kick / harmony": 0.25,
                "full run-through": 0.15,
            },
            "Anchor the harmony with steady groove and clear root movement.",
        )
    if fam == "percussion":
        return (
            {
                "time feel & subdivisions": 0.35,
                "fills & transitions": 0.25,
                "dynamics with the song": 0.25,
                "full run-through": 0.15,
            },
            "Keep the pulse steady before adding fills or section accents.",
        )
    if chord_focus:
        return (
            {
                "chord transitions": 0.40,
                "rhythm / groove": 0.30,
                "melody / licks": 0.20,
                "full run-through": 0.10,
            },
            "Prioritize clean harmonic changes before speed.",
        )
    return (
        {
            "technique / drills": 0.35,
            "rhythm / groove": 0.25,
            "repertoire section": 0.25,
            "full run-through": 0.15,
        },
        "Balance technique, time feel, and musical run-throughs.",
    )


def similar_song_style_hint(instrument: str) -> str:
    fam = instrument_family(instrument)
    hints = {
        "wind": "mid-tempo ballad feel, singable melodic contour, breath-friendly phrasing",
        "voice": "singable melody, clear lyric story, comfortable range for your voice",
        "keyboard": "steady harmonic pulse, singable melody, manageable left-hand movement",
        "fretted": "acoustic pop ballad feel, steady groove, singable melody",
        "bass": "root-driven groove, singable top line, steady harmonic movement",
        "percussion": "steady backbeat, clear section dynamics, singable top-line hook",
    }
    return hints.get(fam, "mid-tempo feel, steady groove, singable melody")


def similar_songs_coaching_tip(instrument: str) -> str:
    fam = instrument_family(instrument)
    tips = {
        "wind": (
            "Use them to practice lyrical phrasing, breath control, tone production, "
            "long-tone support, melodic contour, verse–chorus dynamics, and articulation "
            "without learning a brand-new harmonic language."
        ),
        "voice": (
            "Use them to practice breath support, vowel shaping, lyric delivery, "
            "verse–chorus dynamics, and pitch accuracy on familiar pop harmony."
        ),
        "keyboard": (
            "Use them to practice left-hand pulse, chord voicings, verse–chorus dynamics, "
            "and melodic balance without learning a brand-new harmonic language."
        ),
        "fretted": (
            "Use them to practice strumming/pulse, verse–chorus dynamics, and left-hand changes "
            "without learning a brand-new harmonic language."
        ),
        "bass": (
            "Use them to practice root movement, note length, groove lock, and verse–chorus dynamics "
            "on familiar pop harmony."
        ),
        "percussion": (
            "Use them to practice time feel, section dynamics, and groove consistency "
            "on familiar pop ballad tempos."
        ),
    }
    return tips.get(
        fam,
        "Use them to practice the same feel, dynamics, and melodic shape without learning a brand-new harmonic language.",
    )


def format_level_phrase(level: str) -> str:
    """Avoid duplicated phrasing like 'your level level' in answer headers."""
    raw = str(level or "").strip()
    if not raw or raw.lower() in {"your level", "level"}:
        return ""
    if raw.lower().endswith(" level"):
        return raw
    return raw


def _normalize_song_key(title: str) -> str:
    return str(title or "").split("—", 1)[0].strip().lower()


_SIMILAR_SONG_TEACHER_NOTES: dict[str, dict[str, str]] = {
    "wind": {
        "thinking out loud": "lyrical phrasing and breath control",
        "all of me": "smooth melodic lines and dynamic shaping",
        "say you won't let go": "long-tone support through the chorus",
        "a thousand years": "dynamic control and expressive articulation",
        "photograph": "long-tone support and melodic shaping",
        "perfect": "ballad phrasing and breath pacing",
    },
    "voice": {
        "thinking out loud": "storytelling phrasing and vowel clarity",
        "all of me": "emotional delivery on a singable range",
        "say you won't let go": "breath support through sustained lines",
        "a thousand years": "dynamic build from verse to chorus",
        "photograph": "intimate lyric delivery and pitch stability",
        "perfect": "warm vowels and steady breath support",
    },
    "keyboard": {
        "thinking out loud": "broken-chord accompaniment patterns",
        "all of me": "common pop-ballad voicings",
        "say you won't let go": "left-hand pulse with simple right-hand melody",
        "a thousand years": "sustain-pedal control and legato phrasing",
        "photograph": "melody/accompaniment balance",
        "perfect": "ballad voicings with steady harmonic pulse",
    },
    "fretted": {
        "thinking out loud": "steady strumming and singable chord shapes",
        "all of me": "open-position changes with a ballad groove",
        "say you won't let go": "fingerstyle or strum patterns with clean changes",
        "a thousand years": "dynamic strumming from verse to chorus",
        "photograph": "arpeggio-friendly changes and melodic picking",
        "perfect": "capo-friendly shapes with a steady pulse",
    },
    "bass": {
        "thinking out loud": "root-driven groove and note length",
        "all of me": "walking root movement on a slow ballad",
        "say you won't let go": "locked pulse with the kick drum",
        "a thousand years": "dynamic note length through sections",
        "photograph": "simple root patterns with melodic fills",
        "perfect": "steady eighth-note groove support",
    },
}


def similar_song_teacher_note(instrument: str, song_title: str) -> str:
    fam = instrument_family(instrument)
    key = _normalize_song_key(song_title)
    return _SIMILAR_SONG_TEACHER_NOTES.get(fam, {}).get(key, "")


def chord_transition_lines(instrument: str, minutes: int, bpm: str) -> list[str]:
    fam = instrument_family(instrument)
    inst = str(instrument or "your instrument").strip()
    if fam == "wind":
        lines = [
            f"Spend about **{minutes} minutes** on harmonic-outline drills, then plug them into the song.",
            "- Loop each chord change slowly and land on a clear target tone (root or chord tone).",
            "- Practice smooth breath resets between phrases so tone stays even through the shift.",
            f"- Run 4-bar loops, then 8-bar loops, then add articulation on **{inst}**.",
        ]
    elif fam == "voice":
        lines = [
            f"Spend about **{minutes} minutes** on pitch-through-the-change drills, then sing the section.",
            "- Loop each chord pair slowly and hold the new pitch cleanly before moving on.",
            "- Match vowel shape and breath support across the change.",
            f"- Run 4-bar loops, then 8-bar loops, then add lyric phrasing on **{inst}**.",
        ]
    elif fam == "keyboard":
        lines = [
            f"Spend about **{minutes} minutes** on voicing-change drills, then plug them into the song.",
            "- Loop pairs of chords slowly (metronome 60–70% of target tempo).",
            "- Keep common tones and move only the fingers that must change.",
            f"- Run 4-bar loops, then 8-bar loops, then add left-hand pulse on **{inst}**.",
        ]
    elif fam == "fretted":
        lines = [
            f"Spend about **{minutes} minutes** on chord-change drills, then plug them into the song.",
            "- Loop pairs of chords slowly (metronome 60–70% of target tempo).",
            "- Practice common-finger anchors and lift only the fingers that must move.",
            f"- Run 4-bar loops, then 8-bar loops, then add rhythm on **{inst}**.",
        ]
    else:
        lines = [
            f"Spend about **{minutes} minutes** on change drills, then plug them into the song.",
            "- Loop each harmonic shift slowly (metronome 60–70% of target tempo).",
            "- Isolate the hardest change before running the full progression.",
            f"- Run 4-bar loops, then 8-bar loops, then integrate on **{inst}**.",
        ]
    if bpm:
        lines.append(f"- Target tempo ladder: 70% → 85% → 100% of **{bpm} BPM**.")
    else:
        lines.append("- Target tempo ladder: comfortable → medium → performance tempo.")
    return lines


def section_focus_coaching(instrument: str, section: str, drill: int, connect: int) -> str:
    fam = instrument_family(instrument)
    if fam == "wind":
        return (
            f"For **{section}**: loop **{drill} min** slow reps focusing on tone and phrasing, "
            f"**{drill} min** articulation and breath control, "
            f"then **{connect} min** connecting into the full song."
        )
    if fam == "voice":
        return (
            f"For **{section}**: loop **{drill} min** slow pitch-and-vowel reps, "
            f"**{drill} min** lyric phrasing and dynamics, "
            f"then **{connect} min** connecting into the full song."
        )
    if fam == "keyboard":
        return (
            f"For **{section}**: loop **{drill} min** slow hand-independence reps, "
            f"**{drill} min** rhythm and voicing focus, "
            f"then **{connect} min** connecting into the full song."
        )
    if fam == "fretted":
        return (
            f"For **{section}**: loop **{drill} min** slow reps, **{drill} min** rhythm-focused reps, "
            f"then **{connect} min** connecting into the full song."
        )
    return (
        f"For **{section}**: loop **{drill} min** slow reps, **{drill} min** rhythm-focused reps, "
        f"then **{connect} min** connecting into the full song."
    )


def backing_track_coaching(instrument: str, groove: str, section: str) -> str:
    fam = instrument_family(instrument)
    if fam == "wind":
        return (
            f"Loop **{section}** with **{groove}** at a comfortable tempo. "
            "Practice the melody and harmonic outline first without the backing, "
            "then add the track for time feel, breath pacing, and tone in context."
        )
    if fam == "voice":
        return (
            f"Loop **{section}** with **{groove}** at a comfortable tempo. "
            "Practice pitch and lyric phrasing a cappella first, "
            "then add the track for breath pacing and dynamics."
        )
    if fam == "keyboard":
        return (
            f"Loop **{section}** with **{groove}** at a comfortable tempo. "
            "Practice voicings and hand independence first without the backing, "
            "then add the track for time feel."
        )
    return (
        f"Loop **{section}** with **{groove}** at a comfortable tempo. "
        "Practice chord changes first without the backing, then add the track for time feel."
    )


def skill_technique_coaching(instrument: str, level: str) -> str:
    fam = instrument_family(instrument)
    inst = str(instrument or "your instrument").strip()
    if fam == "wind":
        return (
            f"At **{level}** on **{inst}**, build tone and phrasing before full-tempo performance: "
            "long-tone support, slow melodic reps with a metronome, short bursts at target tempo, then rest. "
            "If the song feels too hard, reduce tempo 20% and isolate the hardest phrase."
        )
    if fam == "voice":
        return (
            f"At **{level}** on **{inst}**, build breath support and pitch accuracy before full-tempo performance: "
            "slow phrase reps with a metronome, short bursts at target tempo, then rest. "
            "If the song feels too hard, reduce tempo 20% and isolate the hardest line."
        )
    if fam == "keyboard":
        return (
            f"At **{level}** on **{inst}**, build hand independence before full-tempo performance: "
            "slow reps with a metronome, short bursts at target tempo, then rest. "
            "If the song feels too hard, reduce tempo 20% and isolate the hardest bar."
        )
    return (
        f"At **{level}** on **{inst}**, build technique before full-tempo performance: "
        "slow reps with a metronome, short bursts at target tempo, then rest. "
        "If the song feels too hard, reduce tempo 20% and isolate the hardest bar."
    )


def tempo_key_coaching(instrument: str, level: str, tempo_line: str, key_line: str) -> str:
    fam = instrument_family(instrument)
    if fam == "wind":
        extra = "Add +5 BPM only after two clean passes with steady tone and breath."
    elif fam == "voice":
        extra = "Add +5 BPM only after two clean passes with stable pitch and breath support."
    elif fam == "keyboard":
        extra = "Add +5 BPM only after two clean passes with even hands."
    else:
        extra = "Add +5 BPM only after two clean passes."
    return f"{tempo_line}\n{key_line}\nFor **{level}** players, {extra}"


def music_theory_coaching(instrument: str, display_key: str, section: str) -> str:
    fam = instrument_family(instrument)
    if fam == "wind":
        angle = (
            "Map each chord to a scale degree, then hear how the melody moves through those tones. "
            "On a wind instrument, connect theory to fingering patterns and where you breathe in the phrase."
        )
    elif fam == "voice":
        angle = (
            "Map each chord to a scale degree, then sing the root or third of each change to internalize the harmony. "
            "Notice where vowel shape and breath reset help you land each new pitch."
        )
    elif fam == "keyboard":
        angle = (
            "Map each chord to a scale degree, then play the progression in root position and one inversion. "
            "Notice voice-leading between left-hand roots and right-hand melody tones."
        )
    elif fam == "fretted":
        angle = (
            "Map each chord to a scale degree, then connect that to chord shapes and common-tone finger anchors. "
            "Isolate the hardest change and compare the voice-leading between shapes."
        )
    else:
        angle = (
            "Name the chords as scale degrees first, then connect that to what you hear in the progression. "
            "If you share a specific chord change from the question, isolate that pair and compare the voice-leading."
        )
    return (
        f"For **{section}** in **{display_key}**, start with the **tonic scale** and chord functions: "
        "I = home, IV = lift, V = tension, vi = emotional color in pop harmony. "
        f"{angle}"
    )


def _musical_application_phrase(song_title: str, section: str) -> str:
    title = str(song_title or "").strip()
    sec = str(section or "").strip()
    if not title or title.lower() in {"full song", "full", "song"}:
        return "a short phrase from a current song or etude"
    if sec and sec.lower() not in {"full song", "full", "all", "song"}:
        return f'"{title}" — focus on **{sec}**'
    return f'"{title}"'


def _beginner_level(level: str) -> bool:
    low = str(level or "").lower()
    return not low or "begin" in low or "easy" in low


def tone_focused_practice_plan(
    instrument: str,
    total_minutes: int,
    *,
    level: str = "",
    song_title: str = "",
    section: str = "",
) -> dict[str, object]:
    """Structured tone-first practice plan blocks (instrument-family voice)."""
    fam = instrument_family(instrument)
    inst = str(instrument or "your instrument").strip()
    beginner = _beginner_level(level)
    song_phrase = _musical_application_phrase(song_title, section)

    if fam == "wind":
        weights = (8, 6, 5, 8, 3) if total_minutes >= 30 else (5, 4, 4, 5, 2)
        m1, m2, m3, m4, m5 = _scale_tone_blocks(total_minutes, weights)
        hold = "6–8 seconds" if beginner else "8–10 seconds"
        goal = (
            f"**Today's goal:** produce a centered, stable **{inst}** tone that stays consistent "
            "through sustained notes, articulation, and actual music."
        )
        headline = f"**{total_minutes}-minute {inst} tone session**"
        steps = [
            f"### 1. {m1} min — Centered long tones\n\n"
            f"- Start in a comfortable **middle register**.\n"
            f"- Hold each note about **{hold}** at a medium-soft dynamic.\n"
            "- Keep the air steady through the entire note; rest briefly between reps.\n"
            "- Move chromatically or through a simple scale across **5–7 notes**.\n\n"
            "**Listen for:** clean start, centered core, stable pitch, even volume, minimal air noise.\n\n"
            f"**Ready when:** **4 of 5** notes begin cleanly and stay stable for {hold.split('–')[-1]}.",
            f"### 2. {m2} min — Tone through register changes\n\n"
            "- Play **slow 4–6 note slurred fragments** (scale or simple interval).\n"
            "- Match tone color when crossing register boundaries.\n"
            "- Repeat each fragment until low/middle/high feel connected.\n\n"
            "**Listen for:** no sudden thinning or spreading of sound between registers.\n\n"
            "**Ready when:** you can play the fragment **3 times** with no obvious tone drop between registers.",
            f"### 3. {m3} min — Clear attacks without losing tone\n\n"
            "- On one comfortable note: **slur 4**, then **tongue 4** at the same dynamic.\n"
            "- Keep the tone centered immediately after the tongue releases.\n"
            "- Expand to a short **2–3 note pattern** if stable.\n\n"
            "**Listen for:** attacks that are clear but not explosive or breathy.\n\n"
            "**Ready when:** **8 of 10** attacks are clean without a thin or airy start.",
            f"### 4. {m4} min — Musical application\n\n"
            f"- Apply the same tone work to a short phrase from {song_phrase}.\n"
            "- Play **very slowly**; preserve the centered sound from your long-tone work.\n"
            "- Choose a phrase that moves through more than one register if possible.\n\n"
            "**Listen for:** tone quality stays as good in the phrase as on isolated notes.\n\n"
            "**Ready when:** the phrase stays centered **3 times in a row** at a slow tempo.",
            f"### 5. {m5} min — Review\n\n"
            "- Replay the **hardest note or phrase** from the session.\n"
            "- Optional: record one short take.\n"
            "- Name **one specific tone issue** to target next time.\n\n"
            "**At the end:** judge whether your sound has a clearer core and steadier air than when you started.",
        ]
        listen = [
            "Focused core rather than airy or diffuse sound",
            "Stable pitch and steady air through the note",
            "Even dynamic from start to finish",
        ]
        return {
            "headline": headline,
            "goal": goal,
            "steps": steps,
            "listen": listen,
            "closing": "If tone stayed centered through long tones **and** your phrase, you met today's goal.",
        }

    if fam == "keyboard":
        weights = (8, 7, 5, 7, 3)
        blocks = _scale_tone_blocks(total_minutes, weights)
        headline = f"**{total_minutes}-minute {inst} tone & touch session**"
        goal = "**Today's goal:** even, singing tone at the keyboard with consistent touch and balance between hands."
        steps = [
            f"### 1. {blocks[0]} min — Legato tone production\n"
            "- Mid-register long tones with **weighted, relaxed fingers**.\n"
            "**Listen for:** even tone without harsh attack.\n"
            "**Ready when:** 4 of 5 notes speak with the same color.",
            f"### 2. {blocks[1]} min — Slow melodic lines\n"
            "- 4–8 note phrases, slurred, very slow.\n"
            "**Ready when:** 3 clean repetitions with matched tone.",
            f"### 3. {blocks[2]} min — Articulation balance\n"
            "- Alternate detached and legato on the same pattern.\n"
            "**Ready when:** detached notes stay round, not brittle.",
            f"### 4. {blocks[3]} min — Apply to {song_phrase}\n"
            "- One short passage, slow tempo.\n"
            "**Ready when:** phrase feels as controlled as your drills.",
            f"### 5. {blocks[4]} min — Review\n"
            "- Repeat the hardest bar; note one touch issue for next time.",
        ]
        return {"headline": headline, "goal": goal, "steps": steps, "listen": ["Even tone", "Relaxed hand"], "closing": ""}

    weights = (7, 6, 5, 9, 3)
    blocks = _scale_tone_blocks(total_minutes, weights)
    headline = f"**{total_minutes}-minute tone-focused session for {inst}**"
    goal = "**Today's goal:** consistent, centered sound on sustained and moving notes."
    steps = [
        f"### 1. {blocks[0]} min — Sustained tone\n"
        "- Comfortable register, steady time on each note.\n"
        "**Ready when:** 4 of 5 reps stay stable.",
        f"### 2. {blocks[1]} min — Slow lines\n"
        "- Short slurred phrases; match tone note to note.",
        f"### 3. {blocks[2]} min — Articulation\n"
        "- Keep tone quality on repeated attacks.",
        f"### 4. {blocks[3]} min — Song phrase from {song_phrase}\n"
        "- Slow application of the same tone focus.",
        f"### 5. {blocks[4]} min — Review\n"
        "- One hardest moment; one goal for next practice.",
    ]
    return {"headline": headline, "goal": goal, "steps": steps, "listen": ["Stable tone"], "closing": ""}


def _scale_tone_blocks(total: int, weights: tuple[int, ...]) -> tuple[int, ...]:
    wsum = sum(weights) or 1
    raw = [total * w / wsum for w in weights]
    rounded = [int(x) for x in raw]
    while sum(rounded) < total:
        for i in range(len(rounded)):
            if sum(rounded) >= total:
                break
            rounded[i] += 1
    while sum(rounded) > total and any(x > 1 for x in rounded):
        for i in range(len(rounded)):
            if sum(rounded) <= total:
                break
            if rounded[i] > 1:
                rounded[i] -= 1
    return tuple(rounded)

