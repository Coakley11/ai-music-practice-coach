"""App feature knowledge — navigation and Creative help (not music theory)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AppFeature:
    feature_id: str
    display_name: str
    purpose: str
    when_to_use: str
    usage_steps: tuple[str, ...]
    related_features: tuple[str, ...] = ()
    example_questions: tuple[str, ...] = ()


FEATURES: dict[str, AppFeature] = {
    "practice_log": AppFeature(
        feature_id="practice_log",
        display_name="Practice Log",
        purpose="Record what you practiced, for how long, and on which songs or skills.",
        when_to_use="When you want a history of sessions, trends, or evidence for coaching.",
        usage_steps=(
            "Open **Practice Log** from the suite navigation.",
            "Add or edit a session with date, duration, instrument, and notes.",
            "Save the entry — it feeds progress reports and AMI practice-history analysis.",
        ),
        related_features=("upload_analysis", "backing"),
        example_questions=("Where do I log my practice?", "How do I save a practice session?"),
    ),
    "backing": AppFeature(
        feature_id="backing",
        display_name="Backing Track Studio",
        purpose="Play along with accompaniment for a song, chord progression, or generated jam context.",
        when_to_use="When you need tempo, groove, and harmonic context while practicing your part.",
        usage_steps=(
            "Select a song or open Backing from Creative / Practice.",
            "Set **practice key**, **tempo**, **groove**, and **section scope** (Full song or a section).",
            "Press play and practice your part over the backing.",
        ),
        related_features=("creative", "missions"),
        example_questions=("What does Backing do?", "How do I create a backing track?"),
    ),
    "upload_analysis": AppFeature(
        feature_id="upload_analysis",
        display_name="Upload & Analysis",
        purpose="Upload a recording and get structured feedback on your take.",
        when_to_use="When you want feedback on an existing performance rather than live coaching.",
        usage_steps=(
            "Go to **Upload** / analysis workflow for your workspace.",
            "Upload your recording and run analysis.",
            "Review the report and optional AMI follow-up on the results.",
        ),
        related_features=("practice_log",),
        example_questions=("Where do I upload a recording?", "How do I analyze a recording?"),
    ),
    "creative": AppFeature(
        feature_id="creative",
        display_name="Creative (Improvisation Studio)",
        purpose="Structured improvisation practice: jams, missions, harmony tools, and live coaching.",
        when_to_use="When you are working on improvisation, motifs, or style-based jamming.",
        usage_steps=(
            "Open **Creative** from the studio navigation.",
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
        usage_steps=(
            "In Creative, open **Entry & Jam** → **Jam Session Generator**.",
            "Choose key, style, mood, and generate.",
            "Practice over the sections; open **Backing** for play-along when ready.",
        ),
        related_features=("style_jam", "backing", "live_coach"),
        example_questions=("What is the Jam Session Generator?",),
    ),
    "style_jam": AppFeature(
        feature_id="style_jam",
        display_name="Style Jam",
        purpose="Explore improvisation inside a chosen style, mood, and groove.",
        when_to_use="When you want style-specific jamming (Bossa, Swing, etc.) rather than a one-off generated chart.",
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
        purpose="Focused improvisation assignments with a specific objective (e.g., develop one motif through a section).",
        when_to_use="When you want a structured challenge tied to a song and a concrete musical goal.",
        usage_steps=(
            "Open **Creative** → **Missions** with an active song.",
            "Pick a mission, practice key, section, and chord focus.",
            "Use **Generate Example**, notation, and **Mission Backing** as needed.",
        ),
        related_features=("motif", "live_coach", "harmony_map", "backing"),
        example_questions=("What are Missions?", "How do I practice a Mission?"),
    ),
    "live_coach": AppFeature(
        feature_id="live_coach",
        display_name="Live Coach",
        purpose="Immediate musical guidance for what to target over the current chord or harmonic context.",
        when_to_use="During Creative practice when you want in-the-moment targets ( chord tones, rhythm, motif ).",
        usage_steps=(
            "Stay on the Creative page with an active chord/progression context.",
            "Open or enable **Live Coach** in the improvisation UI.",
            "Follow the suggested targets while you play.",
        ),
        related_features=("harmony_map", "motif", "missions"),
        example_questions=("What does Live Coach do?",),
    ),
    "harmony_map": AppFeature(
        feature_id="harmony_map",
        display_name="Harmony Map",
        purpose="Visual map of harmonic relationships and available note/chord choices in the current key.",
        when_to_use="When you need to see how chords relate before or while improvising.",
        usage_steps=(
            "Open **Harmony Map** from the Creative improvisation tools.",
            "Use the current practice key and progression context shown in the UI.",
            "Try suggested tones/chords over the active harmony.",
        ),
        related_features=("live_coach", "motif"),
        example_questions=("What does Harmony Map do?",),
    ),
    "motif": AppFeature(
        feature_id="motif",
        display_name="Motif / Phrase tools",
        purpose="Develop a small musical idea (motif) instead of playing disconnected notes.",
        when_to_use="When Missions or improvisation work asks you to develop, vary, or sequence a motif.",
        usage_steps=(
            "In **Missions** or **Phrase / Motif** areas, select a motif or generate an example.",
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
        when_to_use="When choosing repertoire or switching the active song for the workspace.",
        usage_steps=(
            "Open the **song picker** or catalog from Practice / Creative.",
            "Select a song to set it as the active workspace song.",
            "Practice, Backing, and Missions use that active song context.",
        ),
        example_questions=("Where can I see my songs?",),
    ),
}


CREATIVE_COMPARISONS: dict[str, str] = {
    "missions_vs_jam": (
        "**Missions** give a structured assignment on the active song (motif, section, chord goal). "
        "**Jam Session Generator** builds a standalone generated progression for open-ended jamming. "
        "Use Missions for focused homework; use Jam Generator when you want to explore freely."
    ),
}


def feature_by_question(low: str) -> str:
    """Best-effort feature_id from question text."""
    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("practice_log", ("log my practice", "practice log", "save a practice session", "log practice")),
        ("backing", ("backing page", "backing track", "backing do", "create a backing")),
        ("upload_analysis", ("upload", "analyze a recording", "upload analysis", "upload a recording")),
        ("missions", ("what are missions", "practice a mission", "missions in creative")),
        ("jam_session_generator", ("jam session generator", "what is the jam session")),
        ("style_jam", ("style jam",)),
        ("live_coach", ("live coach",)),
        ("harmony_map", ("harmony map",)),
        ("motif", ("what is a motif", "practice a motif", "phrase / motif")),
        ("creative", ("what is creative", "entry & jam", "entry and jam")),
        ("songs", ("see my songs", "where are my songs", "song list")),
    )
    for fid, phrases in rules:
        if any(p in low for p in phrases):
            return fid
    return ""
