"""Canonical app feature knowledge — navigation, comparisons, recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AppFeature:
    feature_id: str
    display_name: str
    purpose: str
    when_to_use: str
    usage_steps: tuple[str, ...]
    navigation_path: str = ""
    user_goals: tuple[str, ...] = ()
    when_not_to_use: str = ""
    related_features: tuple[str, ...] = ()
    distinctions: str = ""
    example_questions: tuple[str, ...] = ()


FEATURES: dict[str, AppFeature] = {
    "practice_log": AppFeature(
        feature_id="practice_log",
        display_name="Practice Log",
        purpose="Record what you practiced, for how long, and on which songs or skills.",
        when_to_use="When you want a history of sessions, trends, or evidence for coaching.",
        navigation_path="Studio sidebar → **Practice Log** (📓).",
        user_goals=("log practice", "track sessions", "review history", "practice diary"),
        usage_steps=(
            "Use **Quick Save** to log your current song, instrument, key, BPM, and focus, "
            "or **Add Session Manually** to enter a session in detail.",
            "Set duration, section practiced, focus area, practice type, notes, and optional 1–5 session ratings.",
            "Browse, filter, edit, or delete saved entries in the session list.",
            "Open **Practice Analysis** on this page for a recent-session summary (optional Command Center handoff).",
        ),
        when_not_to_use="When you need live feedback on a take you just played (use Upload Analysis).",
        related_features=("upload_analysis", "backing"),
        example_questions=("Where do I log my practice?", "How do I save a practice session?"),
    ),
    "practice": AppFeature(
        feature_id="practice",
        display_name="Practice",
        purpose="Core practice workspace: active song, charts, technique work, and Music Coach.",
        when_to_use="When you are working through repertoire, reading, or asking Music Coach for scale/theory help.",
        navigation_path="Studio sidebar → **Practice**.",
        user_goals=("practice song", "read chart", "scale help", "music coach"),
        usage_steps=(
            "Open **Practice** from the studio sidebar.",
            "Select or confirm your active song and section.",
            "Use **Music Coach** in the panel for questions, scale notation, or workflow guidance.",
        ),
        related_features=("music_coach", "backing", "songs"),
        distinctions="Practice is the home for song work and Music Coach; Backing adds play-along tempo/groove.",
        example_questions=("Where can I practice scales?", "Where is Music Coach?"),
    ),
    "music_coach": AppFeature(
        feature_id="music_coach",
        display_name="Music Coach (AMI)",
        purpose="Structured answers for theory, scale exercises (with notation), app navigation, and practice workflow.",
        when_to_use="When you want scale sheet music, chord/scale guidance, or where to go in the app.",
        navigation_path="**Practice** or **Creative** → Music Coach / Ask panel.",
        user_goals=("scale notation", "theory question", "where in app", "how to practice"),
        usage_steps=(
            "Open **Practice** (or **Creative**) and find the **Music Coach** question panel.",
            "Ask for scale material (e.g. “Show me B♭ major in thirds”) or app help (e.g. “How do I log my practice?”).",
            "Use the staff notation when the coach generates an exercise.",
        ),
        related_features=("practice", "harmony_map"),
        distinctions=(
            "**Music Coach** is best for theory questions, scale exercises with notation, and coaching text. "
            "**Harmony Map** is best for visually exploring chord relationships in your current practice key."
        ),
        example_questions=(
            "Where can I get scale help?",
            "Show me a scale in sheet music.",
        ),
    ),
    "backing": AppFeature(
        feature_id="backing",
        display_name="Backing Track Studio",
        purpose="Play along with accompaniment for a song, chord progression, or generated jam context.",
        when_to_use="When you need tempo, groove, and harmonic context while practicing your part.",
        navigation_path="Studio sidebar → **Backing** (or Backing from Creative).",
        user_goals=("loop progression", "change tempo", "play along", "groove practice"),
        usage_steps=(
            "Open **Backing Track Studio** from the sidebar.",
            "Set **practice key**, **tempo (BPM)**, **groove**, and **section scope**.",
            "Press play and practice your part over the backing.",
        ),
        when_not_to_use="When you want a freshly generated chart with no active song (try Jam Session Generator).",
        related_features=("creative", "missions", "jam_session_generator"),
        distinctions=(
            "**Backing** loops the active song or progression with tempo control. "
            "**Jam Session Generator** builds a new progression for open-ended jamming."
        ),
        example_questions=(
            "How do I change the tempo of a backing track?",
            "What does Backing do?",
        ),
    ),
    "upload_analysis": AppFeature(
        feature_id="upload_analysis",
        display_name="Upload & Analysis",
        purpose="Upload or record a single take and get structured feedback on your performance.",
        when_to_use="When you already have a recording (or one live take) and want analysis and coaching feedback.",
        navigation_path="Studio sidebar → **Upload Analysis** (🎙️).",
        user_goals=("analyze recording", "upload take", "get feedback on recording", "analyze my take"),
        usage_steps=(
            "Go to **Upload Analysis** from the studio sidebar.",
            "Upload an audio file or record a single take with the mic.",
            "Run analysis and review timing, pitch, tone, and musicality feedback.",
            "Use the suggested practice plan or Music Coach follow-up.",
        ),
        when_not_to_use=(
            "When you want to build a multi-part recording with separate layers, mute/solo, and mix controls "
            "(use **Multitrack**). When you want live targets while playing (use **Live Coach**)."
        ),
        related_features=("multitrack", "practice_log", "live_coach"),
        distinctions=(
            "**Upload & Analysis** reviews a finished take for feedback. "
            "**Multitrack** is for recording/layering multiple parts and mixing them. "
            "**Live Coach** suggests targets while you improvise."
        ),
        example_questions=("How do I analyze a recording?", "Where can I get feedback on my recording?"),
    ),
    "multitrack": AppFeature(
        feature_id="multitrack",
        display_name="Multitrack",
        purpose="Record, upload, align, and mix multiple instrument layers into one session.",
        when_to_use=(
            "When you want to overdub separate parts, layer recordings, or balance several tracks together."
        ),
        navigation_path="Studio sidebar → **Multitrack** (🎚️).",
        user_goals=(
            "multitrack",
            "multitrack recorder",
            "multi track",
            "record layers",
            "overdub",
            "layer recordings",
            "record several parts",
            "record another part",
            "harmony overdub",
        ),
        usage_steps=(
            "**Step 1 — Session setup:** Choose playback scope (full song, single section, multiple sections, "
            "or **Free layering (no backing)**), set BPM, section repeats, groove/backing context when applicable.",
            "**Step 2 — Layers:** Record or upload each instrument slot (Guitar, Bass, Piano/Keys, Vocals, "
            "Sax/winds, Extra layer), then adjust volume, **Align** (shift earlier/later), **Mute**, **Solo**, "
            "**Monitor backing**, and **Loop selected section** while recording.",
            "**Step 3 — Transport & mixer:** Use transport controls for playback/monitor behavior — loop section, "
            "metronome click, hear backing while recording, and include backing in the final mix when enabled.",
            "Play back all layers together; save the project to the library or use **Step 4 — Save Export** when your mix is ready.",
        ),
        when_not_to_use=(
            "When you only want feedback on one finished take without layering (use **Upload & Analysis**)."
        ),
        related_features=("upload_analysis", "backing", "practice_log"),
        distinctions=(
            "**Multitrack** builds and mixes multiple layers you record or upload. "
            "**Upload & Analysis** analyzes a take for coaching feedback — not a layer mixer."
        ),
        example_questions=(
            "How do I use the multitrack recorder?",
            "Where is the multitrack recorder?",
            "How do I record myself playing multiple parts?",
        ),
    ),
    "creative": AppFeature(
        feature_id="creative",
        display_name="Creative (Improvisation Studio)",
        purpose="Structured improvisation practice: jams, missions, harmony tools, and live coaching.",
        when_to_use="When you are working on improvisation, motifs, or style-based jamming.",
        navigation_path="Studio sidebar → **Creative**.",
        user_goals=("improvise", "missions", "motif", "jam"),
        usage_steps=(
            "Open **Creative** from the studio sidebar.",
            "Choose **Entry & Jam**, **Missions**, or related tabs.",
            "Generate or select a musical context, then practice with Live Coach or Backing.",
        ),
        related_features=("jam_session_generator", "style_jam", "missions", "live_coach"),
    ),
    "jam_session_generator": AppFeature(
        feature_id="jam_session_generator",
        display_name="Jam Session Generator",
        purpose="Creates a fresh progression and musical context for open-ended improvisation practice.",
        when_to_use="When you want to improvise freely with a generated harmonic setting.",
        navigation_path="**Creative** → **Entry & Jam** → **Jam Session Generator**.",
        user_goals=("open jam", "generated progression", "explore freely"),
        usage_steps=(
            "In Creative, open **Entry & Jam** → **Jam Session Generator**.",
            "Choose key, style, mood, and generate.",
            "Practice over the sections; open **Backing** for play-along when ready.",
        ),
        when_not_to_use=(
            "When you need to loop the **current song's** progression — use **Backing** instead. "
            "Matching key alone does not reproduce the song's harmony."
        ),
        related_features=("style_jam", "backing", "live_coach"),
        distinctions=(
            "**Jam Session Generator** builds a **new** progression for open-ended jamming. "
            "**Backing** loops your active song or section at a chosen tempo."
        ),
        example_questions=("What is the Jam Session Generator?",),
    ),
    "style_jam": AppFeature(
        feature_id="style_jam",
        display_name="Style Jam",
        purpose="Explore improvisation inside a chosen style, mood, and groove.",
        when_to_use="When you want style-specific jamming rather than a one-off generated chart.",
        navigation_path="**Creative** → **Entry & Jam** → **Style Jam**.",
        user_goals=("style improv", "bossa", "swing jam"),
        usage_steps=(
            "In Creative → **Entry & Jam** → **Style Jam Mode**.",
            "Set concert key, style, mood, and BPM; generate.",
            "Use section loops and Backing for play-along practice.",
        ),
        related_features=("jam_session_generator", "missions"),
    ),
    "missions": AppFeature(
        feature_id="missions",
        display_name="Missions",
        purpose="Focused improvisation assignments with a specific objective on the active song.",
        when_to_use="When you want a structured challenge (motif, section, chord goal).",
        navigation_path="**Creative** → **Missions** (active song required).",
        user_goals=("structured improv", "motif mission", "focused challenge"),
        usage_steps=(
            "Open **Creative** → **Missions** with an active song.",
            "Pick a mission, practice key, section, and chord focus.",
            "Use **Generate Example**, notation, and **Mission Backing** as needed.",
        ),
        when_not_to_use=(
            "When you only want a free jam with no assignment (Jam Session Generator). "
            "When the mission would not use your current song/section progression."
        ),
        related_features=("motif", "live_coach", "harmony_map", "backing"),
        distinctions=(
            "**Missions** = structured homework on your song. **Live Coach** = in-the-moment targets while you play."
        ),
        example_questions=("What are Missions?", "Should I use Missions or Live Coach?"),
    ),
    "live_coach": AppFeature(
        feature_id="live_coach",
        display_name="Live Coach",
        purpose="Immediate musical guidance for what to target over the current chord or progression.",
        when_to_use="During Creative practice when you want in-the-moment targets.",
        navigation_path="**Creative** with active harmony → enable **Live Coach** in the improvisation UI.",
        user_goals=("live targets", "what to play now", "chord tones now"),
        usage_steps=(
            "Stay on **Creative** with an active chord/progression context.",
            "Open or enable **Live Coach** in the improvisation UI.",
            "Follow the suggested targets while you play.",
        ),
        related_features=("harmony_map", "motif", "missions"),
        distinctions="Use during playing; use **Upload Analysis** after you record a take.",
        example_questions=("What does Live Coach do?",),
    ),
    "harmony_map": AppFeature(
        feature_id="harmony_map",
        display_name="Harmony Map",
        purpose="Visual map of harmonic relationships and note/chord choices in the current key.",
        when_to_use="When you need to see how chords relate before or while improvising.",
        navigation_path="**Creative** → **Harmony Map** (improvisation tools).",
        user_goals=("understand chords", "harmonic relationships", "chord theory visual"),
        usage_steps=(
            "Open **Harmony Map** from the Creative improvisation tools.",
            "Review **stable tones** and **color tones** for each chord in the current section.",
            "Use the map while you experiment over the active harmony (with Live Coach or backing if enabled).",
        ),
        related_features=("live_coach", "motif", "music_coach"),
        distinctions=(
            "**Harmony Map** helps you **see** chord relationships and suggested tones in the current key. "
            "**Music Coach** answers theory questions and generates scale exercises in text and notation."
        ),
        example_questions=("What does Harmony Map do?", "What part of the app helps with chord theory?"),
    ),
    "motif": AppFeature(
        feature_id="motif",
        display_name="Motif / Phrase tools",
        purpose="Develop a small musical idea (motif) instead of playing disconnected notes.",
        when_to_use="When Missions or improvisation work asks you to develop, vary, or sequence a motif.",
        navigation_path="**Creative** → **Missions** or motif/phrase tools in improvisation UI.",
        user_goals=("motif", "phrasing", "develop idea"),
        usage_steps=(
            "In **Missions** or motif areas, select or generate a motif example.",
            "Practice repeating, varying rhythm, and transposing the motif across the section.",
            "Use notation/examples as a reference, then play from memory.",
        ),
        related_features=("missions", "live_coach"),
        example_questions=("What is a motif?", "How should I practice a motif?"),
    ),
    "songs": AppFeature(
        feature_id="songs",
        display_name="Songs / Catalog",
        purpose="Browse and select songs for practice, backing, and Creative missions.",
        when_to_use="When choosing repertoire or switching the active song.",
        navigation_path="Studio sidebar → **Song picker** / catalog (often from Practice).",
        user_goals=("find songs", "active song", "repertoire"),
        usage_steps=(
            "Open the **song picker** or catalog from Practice.",
            "Select a song to set it as the active workspace song.",
            "Practice, Backing, and Missions use that active song context.",
        ),
        example_questions=("Where can I find the songs I'm working on?",),
    ),
}


CREATIVE_COMPARISONS: dict[str, str] = {
    "missions_vs_jam": (
        "**Missions** give a structured assignment on the active song (motif, section, chord goal). "
        "**Jam Session Generator** builds a standalone generated progression for open-ended jamming. "
        "Use Missions for focused homework; use Jam Generator when you want to explore freely."
    ),
    "backing_vs_jam": (
        "**Backing Track Studio** is best when you already have a song or progression to loop at a chosen tempo. "
        "**Jam Session Generator** is best when you want a fresh generated chart to improvise over. "
        "Use **Backing** to practice the current song; use **Jam Session Generator** to explore new harmony."
    ),
    "missions_vs_live_coach": (
        "**Missions** set a multi-step assignment on your song (motif, section, constraint). "
        "**Live Coach** gives immediate targets over the chord you are on right now. "
        "Use **Missions** for homework; use **Live Coach** while you are actively playing."
    ),
    "upload_vs_live_coach": (
        "**Upload & Analysis** reviews a recording you already made. "
        "**Live Coach** guides you in real time during Creative practice. "
        "Record and upload when you want a report; use Live Coach when you want live targets."
    ),
    "style_jam_vs_jam": (
        "**Style Jam** keeps you inside a chosen style, mood, and groove for style-specific improvisation. "
        "**Jam Session Generator** builds a fresh progression/chart for open-ended jamming. "
        "Choose **Style Jam** when the groove/style context matters; choose **Jam Session Generator** "
        "when you want a new harmonic setting to explore."
    ),
    "entry_jam_vs_jam": (
        "**Entry & Jam** is the Creative workflow area that contains jam tools such as **Style Jam** "
        "and **Jam Session Generator**. **Jam Session Generator** is one specific mode inside that area."
    ),
    "multitrack_vs_upload": (
        "**Multitrack** is for building a session from multiple recorded/uploaded layers with align, "
        "mute, solo, and mix controls. **Upload & Analysis** is for analyzing a finished take and "
        "getting coaching feedback — not layering parts."
    ),
    "practice_key_vs_chord_edit": (
        "**Practice Key** transposes how you read/practice the song without rewriting the chart. "
        "**Editing song chords** changes the underlying progression/chart itself. "
        "Use Practice Key for performance comfort; edit chords when the harmony itself needs to change."
    ),
}


def feature_by_question(low: str) -> str:
    """Best-effort feature_id from question text."""
    from music_coach_ami.feature_comparison import (
        multitrack_intent_in_question,
        practice_log_intent_in_question,
        upload_analysis_intent_in_question,
    )

    text = str(low or "").lower()
    if practice_log_intent_in_question(text):
        return "practice_log"
    if multitrack_intent_in_question(text):
        return "multitrack"
    if upload_analysis_intent_in_question(text):
        return "upload_analysis"

    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("practice_log", ("log my practice", "practice log", "save a practice session", "log practice")),
        ("music_coach", ("scale help", "chord theory", "music coach", "ask the coach")),
        ("backing", ("backing track", "backing do", "change the tempo", "tempo of a backing", "backing page")),
        ("multitrack", ("multitrack recorder", "multitrack", "multi track", "multi-track", "overdub")),
        ("upload_analysis", ("upload analysis", "analyze a recording", "analyze myself")),
        ("missions", ("what are missions", "practice a mission", "missions in creative")),
        ("jam_session_generator", ("jam session generator", "what is the jam session")),
        ("style_jam", ("entry style jam", "style jam mode", "style jam")),
        ("live_coach", ("live coach",)),
        ("harmony_map", ("harmony map", "understand chords")),
        ("motif", ("what is a motif", "practice a motif", "phrase / motif", "improve my phrasing")),
        ("creative", ("what is creative", "improvisation studio")),
        ("songs", ("see my songs", "where are my songs", "song list", "songs i'm working")),
        ("practice", ("where can i practice", "practice scales")),
    )
    for fid, phrases in rules:
        if any(p in text for p in phrases):
            return fid
    return ""


def compare_features(key: str) -> str:
    return CREATIVE_COMPARISONS.get(key, "")


def recommend_feature_for_goal(low: str) -> tuple[str, str]:
    """Return (feature_id, reason) for recommendation questions."""
    if any(p in low for p in ("phrasing", "motif", "motifs")):
        return "missions", "Missions and motif tools focus on repeatable musical ideas instead of random notes."
    if "timing" in low or "rhythm" in low:
        return "backing", "Loop a section at a slow tempo in Backing to stabilize timing."
    if "improv" in low or "solo" in low:
        return "missions", "Missions give a concrete improvisation goal on your active song."
    if "log" in low or "track what i practiced" in low:
        return "practice_log", "Practice Log stores session history for review."
    if "feedback" in low and "record" in low:
        return "upload_analysis", "Upload Analysis gives structured feedback on a finished take."
    if "what should i use" in low or "what part of the app" in low:
        return "creative", "Creative bundles improvisation workflows (Missions, Jam, Live Coach)."
    return "practice", "Start from Practice to confirm your song and open Music Coach for guidance."


def context_completeness(ctx: object) -> str:
    title = str(getattr(ctx, "active_song_title", "") or "").strip()
    section = str(getattr(ctx, "active_section", "") or "").strip()
    prog = str(getattr(ctx, "progression_summary", "") or "").strip()
    chord = str(getattr(ctx, "current_chord", "") or "").strip()
    if title and (prog or chord or section):
        return "exact"
    if title or section or chord:
        return "partial"
    return "none"
