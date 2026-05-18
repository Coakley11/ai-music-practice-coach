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


def section_role(section_name):
    name = str(section_name or "").lower()
    if "chorus" in name and "pre" not in name:
        return "chorus"
    if "pre" in name:
        return "pre"
    if "verse" in name or "main loop" in name:
        return "verse"
    if "bridge" in name:
        return "bridge"
    if "intro" in name:
        return "intro"
    if "outro" in name or "ending" in name:
        return "outro"
    if "solo" in name:
        return "solo"
    return "section"


def compact_chord_path(chords, limit=6):
    if not chords:
        return "no chords"
    out = []
    for ch in chords:
        if not out or out[-1] != ch:
            out.append(ch)
    suffix = " ..." if len(out) > limit else ""
    return " | ".join(out[:limit]) + suffix


def chord_color_notes(chords, instrument):
    notes = []
    joined = " ".join(str(ch) for ch in chords).lower()
    family = "winds" if instrument in ["Saxophone", "Flute", "Trumpet"] else str(instrument).lower()

    def add_once(text):
        if text not in notes:
            notes.append(text)

    for ch in chords:
        low = str(ch).lower()
        if "add9" in low:
            add_once(f"**{ch}** has an open add9 color; let the 9th ring instead of over-strumming it.")
        if "maj7" in low:
            if family == "piano":
                add_once(f"**{ch}** wants a soft maj7 touch: keep the 7th inside the right-hand voicing and use light pedal.")
            elif family == "guitar":
                add_once(f"**{ch}** works well as a smaller top-four-string voicing so the maj7 sounds intimate, not heavy.")
            else:
                add_once(f"**{ch}** creates a softer emotional color; phrase into the 7th gently rather than attacking it.")
        if "m7" in low and "m7b5" not in low:
            add_once(f"**{ch}** is a stable minor-7 color; use it as a warm pad or a relaxed melodic landing.")
        if "sus" in low:
            add_once(f"**{ch}** delays resolution; hold the suspension a little longer before releasing the phrase.")
        if "dim" in low or "m7b5" in low:
            add_once(f"**{ch}** is a passing-tension color; keep it moving and resolve the line clearly.")
        if "7#9" in low or "7b9" in low or "13" in low:
            add_once(f"**{ch}** is altered/dominant tension; make it bite rhythmically, then relax into the next chord.")
        if "/" in str(ch):
            add_once(f"**{ch}** uses a written bass note for smooth motion; do not replace it with a plain root unless simplifying.")

    if not notes and "/" in joined:
        notes.append("Slash-chord motion is the main color here; keep the bass line connected.")
    return notes[:2]


def style_arrangement_profile(target_style, source_genre):
    style_text = f"{target_style} {source_genre}".lower()
    if "bossa" in style_text or "jobim" in style_text:
        return {
            "feel": "soft syncopated comping, light bass pulse, airy upper extensions",
            "verse": "nylon-string or soft piano offbeats; leave room around the melody",
            "pre": "slightly denser syncopation and rising inner voices",
            "chorus": "wider voicings, but keep the attack brushed and relaxed",
            "bridge": "use a pedal tone or chromatic passing chord for Jobim-like color",
        }
    if "neo" in style_text or "soul" in style_text:
        return {
            "feel": "laid-back pocket, dense voicings, upper extensions, subtle pushes behind the beat",
            "verse": "thin the texture to shells or two-note upper structures",
            "pre": "add inner-voice movement and anticipations before the chorus",
            "chorus": "stack 9ths/13ths, double the hook, and widen the register",
            "bridge": "try modal mixture or a suspended pedal before resolving",
        }
    if "jazz" in style_text or "fusion" in style_text:
        return {
            "feel": "extended harmony, guide-tone motion, syncopated comping, controlled reharm",
            "verse": "use shells and guide tones before adding substitutions",
            "pre": "increase harmonic rhythm with secondary dominants or ii-V approaches",
            "chorus": "use fuller extensions and stronger rhythmic hits",
            "bridge": "open space for reharm, pedal point, or modal vamp",
        }
    if "funk" in style_text:
        return {
            "feel": "tight pocket, short stabs, bass-driven repetition, syncopated scratches",
            "verse": "one or two-note stabs with muted subdivisions",
            "pre": "tighten the rhythm and add anticipations into section changes",
            "chorus": "stronger octave/riff doubling and clear backbeat accents",
            "bridge": "break down to bass/drums or a pedal vamp before the return",
        }
    if "rock" in style_text:
        return {
            "feel": "driving 8ths, bigger chorus lift, sustained power texture",
            "verse": "palm-muted pulse or arpeggiated open voicings",
            "pre": "build with rising inversions, snare-like accents, and denser rhythm",
            "chorus": "open strums, octave doubling, stronger downbeats",
            "bridge": "drop to half-time, pedal tone, or suspended harmony",
        }
    return {
        "feel": "clear song form, memorable hooks, rhythmic comping, register contrast",
        "verse": "sparse comping and fewer notes so the story stays forward",
        "pre": "increase motion and tension toward the hook",
        "chorus": "fuller voicings, doubled hooks, and stronger rhythmic emphasis",
        "bridge": "change color with pedal point, register shift, or reharm",
    }


def instrument_arrangement_detail(instrument, role, chords, target_style, level):
    first = chords[0] if chords else "the first chord"
    second = chords[1] if len(chords) > 1 else first
    advanced = level == "Advanced"
    if instrument == "Guitar":
        if role == "verse":
            return f"Use a capo/open-string color if it fits the key; fingerpick **{first} -> {second}** with bass on beat 1 and upper strings on the offbeats."
        if role == "chorus":
            return f"Move to open strums or octave shapes; add add9/sus colors on top so the hook sounds wider."
        if role == "bridge":
            return f"Try a pedal top string while changing the lower chord shapes; add ambient swells if the bridge needs contrast."
        return f"Use compact inversions for **{first} -> {second}**, then make one rhythmic strumming pattern the identity of this section."
    if instrument == "Piano":
        if role == "verse":
            return f"Left hand plays sparse roots or fifths; right hand uses shells for **{first} -> {second}** with the top note kept singable."
        if role == "pre":
            return "Use rising inversions or a stepwise top voice to make the pre-chorus feel like it is climbing."
        if role == "chorus":
            return "Spread the voicing: left-hand octave/root-fifth, right-hand 3rd/7th plus 9th or 13th on top."
        if role == "bridge" and advanced:
            return "Try a gospel or neo-soul color: upper structure voicings and a passing diminished chord into the return."
        return f"Connect **{first} -> {second}** by nearest voice leading before adding syncopated comping."
    if instrument == "Bass":
        if role == "verse":
            return "Keep the pocket simple: root/fifth with consistent note length and no fill until the section ending."
        if role == "pre":
            return f"Use chromatic approach notes into **{second}** and slightly denser rhythm to pull into the chorus."
        if role == "chorus":
            return "Lock with the kick and add octave pops or longer downbeat notes so the hook feels larger."
        if role == "bridge":
            return "Try a pedal tone for contrast, then walk back chromatically into the final section."
        return f"Outline roots first, then add one passing tone into **{second}** only at the phrase boundary."
    if instrument in ["Saxophone", "Flute", "Trumpet"]:
        if role == "chorus":
            return f"Write a counter-melody that targets the 3rd of **{first}** on the first strong beat, then answers the vocal/hook."
        if role == "verse":
            return "Use sustained harmony notes or short fills at phrase endings; avoid stepping on the melody."
        if role == "bridge":
            return "Change articulation: long connected phrase first, then a shorter answer phrase before the return."
        return "Use call-and-response phrasing: two bars of space, then a concise answer that lands on a guide tone."
    if instrument == "Voice":
        if role == "verse":
            return "Keep diction close and conversational; place breaths before long thoughts, not after every bar."
        if role == "pre":
            return "Narrow the vowel slightly and build intensity through longer phrases so the chorus entrance feels inevitable."
        if role == "chorus":
            return "Layer harmony on the hook: main melody strong, upper harmony lighter, and save the widest vowel for the emotional peak."
        if role == "bridge":
            return "Change emotional color: head voice/falsetto or softer consonants can make the bridge feel like a new perspective."
        return "Shape lyric delivery around breath placement and one clear emotional peak."
    return f"Make **{first} -> {second}** the arrangement focus: one texture, one dynamic shape, one clear phrase ending."


def section_arrangement_idea(section_name, chords, ctx, target_style):
    role = section_role(section_name)
    profile = style_arrangement_profile(target_style, ctx.get("genre", ""))
    role_text = profile.get(role, profile.get("verse"))
    instrument_text = instrument_arrangement_detail(
        ctx.get("instrument", ""),
        role,
        chords,
        target_style,
        ctx.get("level", "Intermediate"),
    )
    color_notes = chord_color_notes(chords, ctx.get("instrument", ""))
    path = compact_chord_path(chords)

    out = [f"### {section_name} - {len(chords)} bars"]
    out.append(f"- **Chart focus:** `{path}`")
    out.append(f"- **Arrangement move:** {role_text}.")
    out.append(f"- **{ctx.get('instrument', 'Instrument')} part:** {instrument_text}")
    for note in color_notes:
        out.append(f"- **Chord color:** {note}")
    if role == "outro":
        out.append("- **Ending idea:** repeat the strongest motif, thin the texture, and leave one suspended color ringing.")
    elif role == "intro":
        out.append("- **Entrance idea:** preview the groove or hook in a smaller register before the full form starts.")
    return out


def creativity_arrangement_text(ctx, target_style, selected_section="Full song"):
    out = []
    out.append(f"# Creative Arrangement Assistant — {ctx['song']}")
    out.append(
        f"**Target style:** {target_style} | **Instrument:** {ctx['instrument']} | "
        f"**Level:** {ctx['level']} | **Focus:** {ctx['focus']}"
    )

    profile = style_arrangement_profile(target_style, ctx.get("genre", ""))
    out.append("\n## Producer Direction")
    out.append(f"- **Overall feel:** {profile['feel']}.")
    if ctx["level"] == "Beginner":
        out.append("- Keep the reharm light: change texture and register before changing many chords.")
    elif ctx["level"] == "Intermediate":
        out.append("- Add one arrangement device per section: register, rhythm, voicing color, or density.")
    else:
        out.append("- Use advanced colors deliberately: upper extensions, pedal points, reharm, and rhythmic displacement only where the form needs lift.")

    sections = ctx["sections"]
    if selected_section and selected_section != "Full song":
        sections = {selected_section: ctx["sections"].get(selected_section, [])}
        out.append(f"\n## Focused Section: {selected_section}")
    else:
        out.append("\n## Section-by-Section Arrangement")

    for sec, chords in sections.items():
        out.extend(section_arrangement_idea(sec, chords, ctx, target_style))

    out.append("\n## Keep It Musical")
    out.append("- Preserve the original song identity: keep the strongest hook, phrase shape, or bass motion recognizable.")
    out.append("- Make contrast audible between verse, pre-chorus, chorus, bridge, and outro; do not make every section equally dense.")
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
