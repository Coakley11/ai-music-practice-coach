"""Text generators for Creative Lab (kept separate for maintainability)."""


def current_song_context_lab(
    *,
    genre,
    song,
    song_data,
    display_key,
    sections,
    instrument,
    level,
    focus,
):
    return {
        "genre": genre,
        "song": song,
        "artist": song_data.get("artist", ""),
        "composer": song_data.get("composer", ""),
        "key": song_data.get("key", ""),
        "display_key": display_key,
        "sections": sections,
        "instrument": instrument,
        "level": level,
        "focus": focus,
    }


def chord_quality(ch):
    c = str(ch).lower()
    if "m7b5" in c:
        return "half-diminished"
    if "dim" in c:
        return "diminished"
    if "maj7" in c:
        return "major seventh"
    if "m7" in c:
        return "minor seventh"
    if "m" in c and "maj" not in c:
        return "minor"
    if "7" in c:
        return "dominant seventh"
    return "major"


def chord_root(ch):
    ch = str(ch).split("/", 1)[0].strip()
    if len(ch) >= 2 and ch[1] in ["b", "#"]:
        return ch[:2]
    return ch[:1]


def section_patterns(section_name, chords):
    text = []
    roots = [chord_root(ch) for ch in chords]
    qualities = [chord_quality(ch) for ch in chords]
    joined = " ".join(chords)

    if any("m7b5" in str(ch).lower() for ch in chords) and any("7" in str(ch).lower() for ch in chords):
        text.append("- Contains minor ii-V language: half-diminished chords preparing dominant resolution.")
    if any("maj7" in q for q in qualities) and any("dominant" in q for q in qualities):
        text.append("- Alternates stable major colors with dominant pull, a common jazz/pop tension-release device.")
    if len(set(chords[:4])) <= 2 and len(chords) >= 4:
        text.append("- Uses repetition as a groove anchor; the musical interest comes from rhythm, melody, and arrangement.")
    if "/" in joined:
        text.append("- Slash chords create bass-line voice leading rather than block-chord jumps.")
    if any("dim" in str(ch).lower() for ch in chords):
        text.append("- Diminished color works as a passing or leading-tone sonority.")
    if len(roots) >= 4 and len(set(roots[:4])) == 4:
        text.append(f"- Opening root motion moves **{' -> '.join(roots[:4])}**, giving the section clear directional energy.")
    if not text:
        text.append("- Harmony is straightforward; focus on phrasing, groove, and section contrast.")

    return [f"### {section_name}"] + text


def instrument_analysis(ctx):
    inst = ctx.get("instrument", "")
    if inst == "Guitar":
        return [
            "- Use compact voicings on middle strings so changes connect smoothly.",
            "- For comping, alternate muted groove bars with fuller section accents.",
            "- For lead playing, target 3rds/7ths and use slides into phrase peaks.",
        ]
    if inst == "Piano":
        return [
            "- Put roots or shells in the left hand; keep 3rds/7ths in the right hand.",
            "- Practice nearest-voicing motion between adjacent chords before adding rhythm.",
            "- In chorus/lift sections, widen voicings or add octaves for dynamic shape.",
        ]
    if inst == "Bass":
        return [
            "- Outline roots first, then add fifths and chromatic approach tones into section downbeats.",
            "- Where slash chords appear, treat the written bass note as intentional voice leading.",
            "- Build groove by varying note length, not by adding too many passing notes.",
        ]
    if inst in ["Saxophone", "Flute", "Trumpet"]:
        return [
            "- Target chord 3rds on strong beats to make the harmony audible in single-note lines.",
            "- Use long tones on stable chords and more articulated motion over dominant chords.",
            "- Shape phrases across section boundaries; do not restart every bar.",
        ]
    if inst == "Voice":
        return [
            "- Map breaths to section boundaries and avoid spending all air before the harmonic arrival.",
            "- Use lighter tone in setup sections and stronger vowels at chorus/hook arrival points.",
            "- Practice lyric rhythm over the chord grid before singing full pitch.",
        ]
    return [
        "- Identify the strongest arrival chord in each section and shape your phrase toward it.",
        "- Practice the section once for time, once for tone, and once for musical direction.",
    ]


def deep_harmonic_analysis_text(ctx, all_chords_from_sections, chord_quality_fn):
    all_chords = all_chords_from_sections(ctx["sections"])
    qualities = [chord_quality_fn(ch) for ch in all_chords]
    dominant_count = sum(1 for q in qualities if "dominant" in q)
    minor_count = sum(1 for q in qualities if "minor" in q)
    maj7_count = sum(1 for q in qualities if "major seventh" in q)

    out = []
    out.append(f"# Deep Harmonic Analyzer — {ctx['song']}")
    line = f"**Artist:** {ctx['artist']}"
    if ctx.get("composer"):
        line += f" | **Composer:** {ctx['composer']}"
    out.append(line)
    out.append(f"**Style:** {ctx['genre']}")
    out.append(f"**Original key:** {ctx['key']} | **Displayed key:** {ctx['display_key']}")

    out.append("\n## Harmonic Character")
    if ctx["genre"] == "Jazz":
        out.append("- This chart uses extended harmony and functional motion.")
        out.append("- Dominant seventh chords usually create forward pull into a resolution.")
        out.append("- Minor seventh and half-diminished chords often prepare ii–V or minor-key motion.")
    elif ctx["genre"] in ["Pop", "Rock"]:
        out.append("- The song is built around memorable section loops rather than dense jazz harmony.")
        out.append("- Repetition creates stability; section contrast creates emotional motion.")
        out.append("- Verse, chorus, and bridge differences are the main dramatic engine.")
    elif ctx["genre"] == "Funk":
        out.append("- The harmony is groove-centered; repeated vamps matter more than constant chord changes.")
    elif ctx["genre"] == "Blues":
        out.append("- The form is built around dominant tension and call-and-response phrasing.")
    else:
        out.append("- The harmony supports melodic development and formal balance.")

    out.append("\n## Chord Color Summary")
    out.append(f"- Dominant-type chords: {dominant_count}")
    out.append(f"- Minor-type chords: {minor_count}")
    out.append(f"- Major-seventh color chords: {maj7_count}")

    out.append("\n## Section Function")
    for sec, chords in ctx["sections"].items():
        out.extend(section_patterns(sec, chords))

    out.append("\n## Instrument-Specific Lens")
    out.extend(instrument_analysis(ctx))

    out.append("\n## Improvisation Ideas")
    if ctx["level"] == "Beginner":
        out.append("- Start with chord roots, then add 3rds and 5ths.")
        out.append("- Use short phrases, not long scale runs.")
    elif ctx["level"] == "Intermediate":
        out.append("- Target the 3rd of each chord on strong beats.")
        out.append("- Use one repeated motif and move it through the sections.")
        out.append("- Practice guide tones between adjacent chords.")
    else:
        out.append("- Use guide-tone lines, chromatic approaches, delayed resolutions, and rhythmic displacement.")
        out.append("- Try reharmonizing one repeated section with secondary dominants or tritone substitutions.")
        out.append("- Build solos from motivic development rather than scale patterns.")

    return "\n".join(out)


def creativity_arrangement_text(ctx, target_style):
    out = []
    out.append(f"# Creative Arrangement Assistant — {ctx['song']}")
    out.append(f"Transforming toward: **{target_style}**")
    out.append("\n## Arrangement Strategy")
    if target_style == "Jobim / Bossa":
        out.append("- Use softer rhythmic syncopation and gentler harmonic motion.")
        out.append("- Add major 7ths, minor 9ths, and smoother bass motion.")
        out.append("- Keep the melody relaxed and slightly behind the beat.")
    elif target_style == "Jazz Fusion":
        out.append("- Use extended voicings, electric piano textures, and syncopated bass.")
        out.append("- Add modal solo sections over one or two-chord vamps.")
    elif target_style == "Neo-Soul":
        out.append("- Add lush voicings: maj9, m9, 13sus, and passing diminished chords.")
        out.append("- Use laid-back groove, inner voice movement, and reharmonized turnarounds.")
    elif target_style == "Rock Ballad":
        out.append("- Simplify voicings and emphasize emotional build.")
        out.append("- Add bigger chorus texture, sustained chords, and dynamic lift.")
    elif target_style == "Funk":
        out.append("- Reduce harmonic motion and emphasize groove.")
        out.append("- Use stabs, scratches, syncopated comping, and bass-driven repetition.")
    else:
        out.append("- Keep the melody recognizable but change groove, voicing, and form.")

    out.append("\n## Section-by-Section Ideas")
    for sec, chords in ctx["sections"].items():
        out.append(f"### {sec}")
        out.append("- Original: | " + " | ".join(chords) + " |")
        if target_style in ["Neo-Soul", "Jazz Fusion", "Jobim / Bossa"]:
            out.append("- Try adding color tones: 7ths, 9ths, 11ths, or 13ths.")
        if target_style == "Funk":
            out.append("- Try reducing to a 1–2 chord vamp and focus on rhythmic variation.")
        if target_style == "Rock Ballad":
            out.append("- Try bigger sustained voicings and a stronger chorus lift.")
    return "\n".join(out)


def improvisation_intelligence_text(ctx):
    out = []
    out.append(f"# Improvisation Intelligence System — {ctx['song']}")
    out.append("\n## What the system is tracking")
    out.append("- chord-tone targeting")
    out.append("- repeated rhythmic habits")
    out.append("- overused scalar motion")
    out.append("- phrase length variety")
    out.append("- tension and release")
    out.append("- motif development")
    out.append("- avoided intervals or registers")
    out.append("\n## Forced Creativity Challenges")
    if ctx["level"] == "Beginner":
        out.append("- Improvise using only roots.")
        out.append("- Then roots + 3rds.")
        out.append("- Use only 2-bar phrases.")
    elif ctx["level"] == "Intermediate":
        out.append("- Chorus 1: chord tones only.")
        out.append("- Chorus 2: one motif moved through the form.")
        out.append("- Chorus 3: avoid starting phrases on beat 1.")
    else:
        out.append("- Use no scalar runs for one chorus.")
        out.append("- Resolve every tension note intentionally.")
        out.append("- Develop one 3-note motif through all sections.")
        out.append("- Use rhythmic displacement.")
    return "\n".join(out)


def adaptive_weakness_detection_text(ctx):
    out = []
    out.append(f"# Adaptive Weakness Detection — {ctx['song']}")
    out.append("\n## Current practice targets")
    if ctx["focus"] == "Improvisation":
        out.append("- Target stronger chord-tone resolution and less repetitive phrasing.")
    elif ctx["focus"] == "Rhythm":
        out.append("- Target steadier pulse, cleaner entrances, and less rushing.")
    elif ctx["focus"] == "Harmony":
        out.append("- Target smoother chord transitions and clearer section function.")
    elif ctx["focus"] == "Melody":
        out.append("- Target phrase shape, note accuracy, and melodic continuity.")
    else:
        out.append("- Target technique, tone, and consistency.")
    out.append("\n## Generated Drill")
    out.append("- Pick the hardest section.")
    out.append("- Loop it slowly 5 times.")
    out.append("- Record one take.")
    out.append("- Listen for only one weakness.")
    out.append("- Repeat with one correction.")
    return "\n".join(out)


def musical_development_tracker_text(load_logs_fn):
    logs = load_logs_fn() if callable(load_logs_fn) else []
    out = ["# AI-Guided Musical Development Tracking"]
    if not logs:
        out.append("No practice logs yet. Start logging sessions to build a development profile.")
        return "\n".join(out)
    import pandas as pd

    df = pd.DataFrame(logs)
    out.append(f"Total logged sessions: **{len(df)}**")
    if "focus" in df.columns:
        out.append("\n## Focus Distribution")
        for k, v in df["focus"].value_counts().to_dict().items():
            out.append(f"- {k}: {v} sessions")
    if "song" in df.columns:
        out.append("\n## Most Practiced Songs")
        for k, v in df["song"].value_counts().head(5).to_dict().items():
            out.append(f"- {k}: {v} sessions")
    if "rating" in df.columns:
        try:
            out.append(f"\nAverage self-rating: **{df['rating'].astype(float).mean():.1f}/10**")
        except Exception:
            pass
    out.append("\n## Development Recommendation")
    out.append("- Balance song learning with improvisation and ear-training.")
    out.append("- Revisit the same song across multiple styles.")
    out.append("- Track whether your weak area changes over time.")
    return "\n".join(out)
