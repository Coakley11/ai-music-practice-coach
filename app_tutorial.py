"""Friendly first-time musician tutorial for the music practice studio.

Quick Tour = first useful workflows. Explore More = extra tools.
Detailed save/edit language lives in Learn more expanders — not the main flow.
"""

from __future__ import annotations

import html
import re
from typing import Any, Callable

from studio_page_state import CREATIVE_TOOL_ICONS

TUTORIAL_DISMISSED_KEY = "tutorial_dismissed"
TUTORIAL_OPEN_KEY = "tutorial_open"
TUTORIAL_STEP_KEY = "tutorial_step"
TUTORIAL_DISMISS_CHECKBOX_KEY = "tutorial_dismiss_checkbox"

# Valid studio page ids that tutorial action buttons may navigate to.
_VALID_NAV_PAGE_IDS = frozenset(
    {
        "practice",
        "picker",
        "backing",
        "custom",
        "composer",
        "creative",
        "multitrack",
        "analysis",
        "log",
        "openai",
    }
)

# --- Quick Tour (welcome + 7 basics) ---------------------------------
# --- Explore More (optional) -----------------------------------------

TUTORIAL_STEPS: list[dict[str, Any]] = [
    {
        "id": "welcome",
        "layer": "welcome",
        "page_id": "",
        "icon": "🎵",
        "script": "Welcome",
        "title": "Your music. Your practice. One workspace.",
        "summary": (
            "Pick a song. Choose what you want to work on. Practice with backing "
            "tracks and focused tools. Create new ideas. Record yourself. Ask your "
            "Music Coach for help. Keep track of what you practiced — and come back "
            "tomorrow ready to continue."
        ),
        "try_this": "Take a one-minute look around. You can skip anytime.",
        "why": "Everything here stays around the music you’re working on today.",
        "cards": [
            {
                "icon": "🎯",
                "title": "Practice",
                "body": "Work on songs, technique, timing, tone, and specific sections.",
                "tone": "practice",
            },
            {
                "icon": "🎨",
                "title": "Create",
                "body": "Jam, explore harmony, generate ideas, and give yourself Missions.",
                "tone": "creative",
            },
            {
                "icon": "🎙️",
                "title": "Listen & Improve",
                "body": "Record, analyze, log your work, and ask Music Coach what to try next.",
                "tone": "analysis",
            },
        ],
        "bullets": [],
        "action_label": "",
        "sections": [
            {
                "title": "Learn more — how the pieces connect",
                "bullets": [
                    "Your **active song**, **instrument**, **level**, **focus**, and "
                    "**Practice / Concert Key** carry into Practice, Backing, Creative Lab, "
                    "Karaoke (when Instrument is Voice), Music Coach, and recording.",
                    "Instead of hunting for a chart, metronome, backing track, notebook, "
                    "and a generic AI elsewhere, you keep working in one place.",
                ],
            },
        ],
    },
    {
        "id": "setup",
        "layer": "quick",
        "page_id": "practice",
        "icon": "🎚️",
        "script": "Set up",
        "title": "Tell the app who you are today",
        "summary": "Three simple choices on the left. They help the app adapt to you.",
        "try_this": "In Practice Setup, pick your instrument. Then choose your level and focus.",
        "why": "You can change focus anytime without changing songs.",
        "cards": [
            {
                "icon": "🎷",
                "title": "Who are you playing as?",
                "body": "**Instrument** — Piano, Guitar, Bass, Saxophone, Flute, Trumpet, Clarinet, Voice, or Other.",
                "tone": "practice",
            },
            {
                "icon": "📈",
                "title": "How challenging should it be?",
                "body": "**Level** — Beginner keeps things simpler. Intermediate adds variety. Advanced can feel more demanding.",
                "tone": "picker",
            },
            {
                "icon": "🎯",
                "title": "What do you want to work on?",
                "body": "**Practice Focus** — tone, phrasing, rhythm, technique, improvisation, or an instrument-specific goal.",
                "tone": "log",
            },
        ],
        "bullets": [
            "These choices help the app adapt to you — not just relabel the screen.",
        ],
        "action_label": "Start practicing →",
        "sections": [
            {
                "title": "Learn more — how instrument changes the app",
                "bullets": [
                    "Focus lists change by instrument (Walking Bass on Bass, Breath Control on Voice, Lead Guitar on Guitar).",
                    "**Voice** unlocks Karaoke Performance Setlist and Vocal Performance Mode.",
                    "**Saxophone** lets you pick Alto, Tenor, Soprano, or Baritone — written key and range differ.",
                    "**Clarinet / Trumpet / Saxophone** can show charts in the key you actually read.",
                    "**Guitar** can use Capo Shape Mode so sounding Practice Key and chord shapes stay clear.",
                    "**Piano** is a natural home for chords, voicings, and left-hand / right-hand work.",
                    "**Bass** includes groove and Walking Bass focuses. Other instruments can still work on supportive bass-role ideas.",
                    "**Flute** and other winds can emphasize tone, articulation, breath, and phrasing.",
                ],
            },
        ],
    },
    {
        "id": "music",
        "layer": "quick",
        "page_id": "picker",
        "icon": "🎼",
        "script": "Pick music",
        "title": "Choose something to play",
        "summary": "Start with a catalog song, or build your own progression.",
        "try_this": "Open Song Selection and pick a song you already know.",
        "why": "Whatever you choose becomes your active song — Practice, Backing, and Creative can use it.",
        "cards": [
            {
                "icon": "🎵",
                "title": "Pick a song from the Catalog",
                "body": "Ready-made music and charts. Great for repertoire.",
                "tone": "picker",
            },
            {
                "icon": "✍️",
                "title": "Create your own",
                "body": "Custom Progression for an original song, lesson, exercise, or improv idea.",
                "tone": "custom",
            },
        ],
        "bullets": [
            "You can also personalize charts and lyrics where the app supports it.",
        ],
        "action_label": "Pick a song →",
        "sections": [
            {
                "title": "Learn more — catalog vs your own songs",
                "bullets": [
                    "Catalog edits are *your* copy: **Edit Song Chart** → Enable editing → **Save corrected chart**. "
                    "**Lyrics & Cues** → **Save Lyrics & Cues**. Revert when you want the catalog version back — "
                    "this does not rewrite the master catalog.",
                    "Custom Progression: build chords, **Save to library**, **Set as Active Song**, "
                    "reopen later with **Load selected**. **Finish Song** when the form is ready to practice.",
                ],
            },
        ],
    },
    {
        "id": "keys",
        "layer": "quick",
        "page_id": "picker",
        "icon": "🔑",
        "script": "The key",
        "title": "Put it in a comfortable key",
        "summary": "Change the Practice / Concert Key anytime. The original song stays the original song.",
        "try_this": "In the left Practice Setup panel, move Practice / Concert Key to something comfortable.",
        "why": "Same song, easier range — especially useful for singers and transposing instruments.",
        "cards": [
            {
                "icon": "📜",
                "title": "Original Key",
                "body": "The song’s original key.",
                "tone": "slate",
            },
            {
                "icon": "🎹",
                "title": "Practice / Concert Key",
                "body": "The key you want to play or sing it in today.",
                "tone": "picker",
            },
        ],
        "bullets": [
            "Playing Clarinet, Trumpet, or Saxophone? The app can also account for the key you actually read. "
            "Example: Concert C → Clarinet reads D.",
        ],
        "action_label": "Pick a song →",
        "sections": [
            {
                "title": "Learn more — written key, sax types, guitar capo",
                "bullets": [
                    "Use **Show chart in written key for instrument** when you want charts in written spelling.",
                    "Saxophone **Alto / Tenor / Soprano / Baritone** do not all read the same way.",
                    "Guitar **Capo Shape Mode** keeps sounding Practice Key and capo/chord shapes clearly separate.",
                    "Changing Practice Key does not rewrite the original catalog song.",
                ],
            },
        ],
    },
    {
        "id": "practice",
        "layer": "quick",
        "page_id": "practice",
        "icon": "🎯",
        "script": "Practice",
        "title": "This is where you actually work",
        "summary": "Pick one goal, work on it for a few minutes, then put it into music with Backing.",
        "try_this": "Open Practice. Choose one section — maybe just the chorus — and one tool.",
        "why": "You don’t have to play the whole song every time.",
        "cards": [
            {
                "icon": "⏱️",
                "title": "Time",
                "body": "Metronome and tempo practice.",
                "tone": "backing",
            },
            {
                "icon": "🎯",
                "title": "Pitch & Tone",
                "body": "Tuner and tone development.",
                "tone": "practice",
            },
            {
                "icon": "🎼",
                "title": "Music",
                "body": "Chart, notation, lyrics, and harmony tools.",
                "tone": "picker",
            },
            {
                "icon": "🔁",
                "title": "Focus",
                "body": "Work on one section instead of always playing the entire song.",
                "tone": "log",
            },
        ],
        "bullets": [
            "Want a tricky chorus cleaner? Stay on that section until it feels easier, then raise the tempo.",
        ],
        "action_label": "Start practicing →",
        "sections": [
            {
                "title": "Learn more — Practice tools",
                "bullets": [
                    "**Harmony & technique** → Chord & song coach.",
                    "**Time & pitch** → Metronome, Tuner & Tone.",
                    "**Charts & lyrics** → Chart & notation, Lyrics & phrasing.",
                    "**Reference** → Transpose helpers (and Guitar capo helper when relevant).",
                    "Music Coach sits nearby so you can ask for a plan without leaving Practice.",
                ],
            },
        ],
    },
    {
        "id": "backing",
        "layer": "quick",
        "page_id": "backing",
        "icon": "🎧",
        "script": "Play along",
        "title": "Turn the song into something you can play with",
        "summary": "Loop the verse. Slow down the bridge. Improvise over the changes. Raise the tempo when you’re ready.",
        "try_this": "Open Backing Track → choose a section → choose tempo → press **Play Backing Track**.",
        "why": "A metronome keeps time. Backing plays the accompaniment so you can practice inside the music.",
        "cards": [
            {
                "icon": "1️⃣",
                "title": "Choose section",
                "body": "Full song, or just the part you’re working on.",
                "tone": "backing",
            },
            {
                "icon": "2️⃣",
                "title": "Choose tempo",
                "body": "Start slower than performance tempo if you need to.",
                "tone": "backing",
            },
            {
                "icon": "3️⃣",
                "title": "Play Backing Track",
                "body": "Press **Play Backing Track** to hear the accompaniment and play along.",
                "tone": "practice",
            },
        ],
        "bullets": [
            "This uses your active song. It’s different from Jam Session Generator (a new practice situation) and Multitrack (your own recorded layers).",
        ],
        "action_label": "Play with a backing track →",
        "sections": [],
    },
    {
        "id": "coach",
        "layer": "quick",
        "page_id": "practice",
        "icon": "💬",
        "script": "Ask",
        "title": "Ask your Music Coach",
        "summary": "You don’t need special prompts. Ask the kinds of questions you would ask a teacher.",
        "try_this": "Open Music Coach and ask something musical — a bass line, a pattern, or how to practice this chorus.",
        "why": "Music Coach can use relevant context from the app — instrument, level, focus, active song, section, Practice Key, and your Practice Log — so you don’t always have to explain everything from scratch.",
        "cards": [],
        "questions": [
            "Give me a good bass line for this song.",
            "Give me a harmonic minor pattern in B-flat minor.",
            "Give me a 4-bar descending harmonic minor pattern in A minor.",
            "Give me an 8-bar ascending eighth-note pattern in D harmonic minor at 90 BPM.",
            "Give me a very easy 4-bar lick in C minor.",
            "Give me a 4-bar phrase over the chorus.",
            "What should I practice for 20 minutes today?",
            "How should I work on this chorus?",
            "Should I use Upload Analysis or Multitrack?",
            "Where do I upload a recording?",
        ],
        "bullets": [
            "Ask in plain musical language. That’s enough.",
        ],
        "action_label": "Ask Music Coach →",
        "sections": [],
    },
    {
        "id": "log",
        "layer": "quick",
        "page_id": "log",
        "icon": "📓",
        "script": "Remember",
        "title": "Don’t start from zero tomorrow",
        "summary": "Save what you practiced today so you can see your progress and remember where to continue.",
        "try_this": "After you play, open Practice Log and Quick Save.",
        "why": "Your Practice Log tells you what you did. Practice Analysis helps you look for patterns over time.",
        "cards": [
            {
                "icon": "⚡",
                "title": "Quick Save",
                "body": "Fast entry from your current song, instrument, key, BPM, and focus.",
                "tone": "log",
            },
            {
                "icon": "✏️",
                "title": "Add a session manually",
                "body": "When you want fuller notes.",
                "tone": "slate",
            },
            {
                "icon": "🧠",
                "title": "Practice Analysis",
                "body": "Look for patterns and what to work on next.",
                "tone": "creative",
            },
        ],
        "bullets": [
            "Keeping a simple log also helps Music Coach continue from real work.",
        ],
        "action_label": "See my Practice Log →",
        "sections": [
            {
                "title": "Learn more — logging details",
                "bullets": [
                    "Use **Quick Save Practice Session** or **Add Session Manually**. "
                    "You can edit, delete, and filter history.",
                    "**Analyze My Practice** opens Practice Analysis.",
                    "Not every page auto-logs — save when you want the diary to remember.",
                ],
            },
        ],
    },
    {
        "id": "karaoke",
        "layer": "explore",
        "page_id": "backing",
        "icon": "🎤",
        "script": "Sing",
        "title": "Singing? Switch to Voice.",
        "summary": "Choose Voice, pick a comfortable Practice Key, then sing with lyrics and accompaniment.",
        "try_this": "Tap **Karaoke Performance** to sing in Vocal Performance Mode.",
        "why": "Karaoke is for singing the song. Upload Analysis is for feedback on a recorded take. Multitrack is for layering parts.",
        "cards": [
            {
                "icon": "1️⃣",
                "title": "Choose Voice",
                "body": "Set Instrument to Voice in Practice Setup.",
                "tone": "voice",
            },
            {
                "icon": "2️⃣",
                "title": "Pick a song & key",
                "body": "Move Practice / Concert Key to a comfortable singing range.",
                "tone": "picker",
            },
            {
                "icon": "3️⃣",
                "title": "Open Karaoke",
                "body": "Song Selection becomes Karaoke Performance Setlist. Backing becomes Vocal Performance Mode.",
                "tone": "practice",
            },
            {
                "icon": "4️⃣",
                "title": "Sing, then record if you want",
                "body": "Use Upload Analysis when you want feedback on one vocal take.",
                "tone": "analysis",
            },
        ],
        "bullets": [
            "Voice focuses include Breath Control, Phrasing, Pitch Accuracy, Emotional Delivery, Harmony Singing, Vibrato, Dynamics, and Ear Training.",
        ],
        "action_label": "Karaoke Performance",
        "action_prep": "voice_instrument",
        "sections": [
            {
                "title": "Learn more — finding Karaoke",
                "bullets": [
                    "There is no separate Karaoke studio page — Voice turns Song Selection + Backing into the karaoke workflow.",
                    "Karaoke uses your active song, lyrics/cues, and Practice / Concert Key.",
                ],
            },
        ],
    },
    {
        "id": "creative",
        "layer": "explore",
        "page_id": "creative",
        "icon": "🎨",
        "script": "Explore",
        "title": "Creative Lab — when you want more than repeating the song",
        "summary": "Jam, generate a fresh practice situation, take a Mission, or see how the harmony fits together.",
        "try_this": "Open Creative Lab. Try Harmony Map once on a song you already know.",
        "why": "Creative is where you explore. Custom Progression is where you write your own chords.",
        "cards": [
            {
                "icon": CREATIVE_TOOL_ICONS["Song-Based Improvisation"],
                "title": "Play Song-Based Improvisation",
                "body": "Improvise over the song you’re already working on.",
                "tone": "creative",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Style Jam Mode"],
                "title": "Style Jam Mode",
                "body": "Start from a style or groove when you want feel first, not a specific tune.",
                "tone": "picker",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Jam Session Generator"],
                "title": "Jam Session Generator",
                "body": "Create a fresh practice situation without designing everything by hand.",
                "tone": "analysis",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Missions"],
                "title": "Missions",
                "body": "Give yourself a focused challenge — phrasing, rhythm, or developing a simple idea.",
                "tone": "practice",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Harmony Map"],
                "title": "Harmony Map",
                "body": "See how the progression fits together — useful when improvising or composing.",
                "tone": "log",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Phrase / Motif"],
                "title": "Phrase / Motif",
                "body": "Develop musical ideas, then notate them.",
                "tone": "backing",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Live Coach"],
                "title": "Live Coach",
                "body": "Scales, chord tones, and tips for the harmony you’re on.",
                "tone": "voice",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Metrics & AI"],
                "title": "Metrics & AI",
                "body": "Choose what Upload Analysis should pay attention to.",
                "tone": "slate",
            },
        ],
        "bullets": [
            "Song-Based, Style Jam, and Jam Session Generator live under **Entry & Jam**. Then wander — you don’t have to memorize every tab.",
        ],
        "action_label": "Explore Creative →",
        "sections": [
            {
                "title": "Learn more — Creative tabs & Missions",
                "bullets": [
                    "Tabs: Entry & Jam, Live Coach, Phrase / Motif, Missions, Harmony Map, Deep Harmony, Metrics & AI — same icons as in this tour.",
                    "Entry modes: Song-Based Improvisation, Style Jam Mode, Jam Session Generator.",
                    "A Mission is a specific challenge — not “just play the song.” Play with backing when it’s available, and record a take if you want to review it.",
                    "Deep Harmony is a slower guided harmonic lesson when you want that pace.",
                ],
            },
        ],
    },
    {
        "id": "composer",
        "layer": "explore",
        "page_id": "composer",
        "icon": "🎹",
        "script": "Write",
        "title": "Writing a song? Open Composition Studio",
        "summary": "When a custom progression isn’t enough structure, Composition Studio helps you shape a fuller idea.",
        "try_this": "If you’re writing, open Composition Studio and sketch a short verse/chorus form first.",
        "why": "Custom Progression is great for chords. Composition Studio is for a fuller song idea.",
        "cards": [
            {
                "icon": "✍️",
                "title": "Custom Progression",
                "body": "Build and save your own harmony, then Set as Active Song.",
                "tone": "custom",
            },
            {
                "icon": "🎹",
                "title": "Composition Studio",
                "body": "Vision, structure, chords, melody, lyrics, and review.",
                "tone": "creative",
            },
        ],
        "bullets": [
            "Once an idea is active, you can still practice it with Backing or Creative.",
        ],
        "action_label": "Open Composition Studio →",
        "sections": [],
    },
    {
        "id": "recording",
        "layer": "explore",
        "page_id": "analysis",
        "icon": "🎙️",
        "script": "Record",
        "title": "What do you want to record?",
        "summary": "One take, several parts, or just a note that you practiced — pick the path that matches the job.",
        "try_this": "If you already have one performance, go to Upload Analysis.",
        "why": "Upload Analysis coaches the take. Multitrack builds the arrangement. Practice Log keeps the diary.",
        "cards": [
            {
                "icon": "🎧",
                "title": "One take",
                "body": "**Upload Analysis** — feedback on one performance.",
                "tone": "analysis",
            },
            {
                "icon": "🎚️",
                "title": "Several parts",
                "body": "**Multitrack** — layer recordings or hear parts together.",
                "tone": "multitrack",
            },
            {
                "icon": "📓",
                "title": "Just remember",
                "body": "**Practice Log** — save that you practiced.",
                "tone": "log",
            },
            {
                "icon": "🎯",
                "title": "Mission take",
                "body": "Use the Mission’s play/record options when they appear.",
                "tone": "practice",
            },
        ],
        "bullets": [
            "From Multitrack you can also send a mix toward Upload Analysis when you want feedback.",
        ],
        "action_label": "Record a take →",
        "sections": [
            {
                "title": "Learn more — Upload Analysis vs Multitrack",
                "bullets": [
                    "Upload Analysis (*Upload & AI Coach*): drop/upload a recording and review timing, pitch, and next-step suggestions.",
                    "Multitrack (*Multitrack Session Workspace*): layers, mute/solo/volume, monitor backing, transport, mix/export where available.",
                ],
            },
        ],
    },
    {
        "id": "saving",
        "layer": "explore",
        "page_id": "picker",
        "icon": "💾",
        "script": "Come back",
        "title": "Leave a trail you can follow tomorrow",
        "summary": "Practice Key is just for today. Chart and lyric edits, custom songs, and Practice Log entries need an explicit save.",
        "try_this": "If you edited chords or lyrics, look for Save before you switch songs.",
        "why": "Coming back is easier when the song, key, and notes are still there.",
        "cards": [
            {
                "icon": "🔑",
                "title": "Practice Key",
                "body": "Practice transposition — does not rewrite Original Key.",
                "tone": "picker",
            },
            {
                "icon": "📝",
                "title": "Charts & lyrics",
                "body": "Save corrected chart / Save Lyrics & Cues. Revert toward catalog if you want.",
                "tone": "slate",
            },
            {
                "icon": "📚",
                "title": "Custom songs",
                "body": "Save to library, then Load selected / Set as Active Song later.",
                "tone": "custom",
            },
        ],
        "bullets": [
            "Return via Song Selection, your last active song, and Practice Log history.",
        ],
        "action_label": "Pick a song →",
        "sections": [
            {
                "title": "Learn more — what needs Save",
                "bullets": [
                    "Catalog chart / lyrics: explicit Save buttons. Revert returns toward catalog material — this does not rewrite the original catalog for everyone.",
                    "Custom: **Save to library**, then **Load selected** / **Set as Active Song**.",
                    "Practice Log: Quick Save or Add Session Manually — not every page auto-logs.",
                    "Multitrack / uploads: use save/export on those pages when you need the files later.",
                ],
            },
        ],
    },
    {
        "id": "which_tool",
        "layer": "explore",
        "page_id": "",
        "icon": "🌙",
        "script": "Tonight",
        "title": "A simple night of practice",
        "summary": "Tomorrow, pick up where you left off.",
        "try_this": "Use this as a template, then change the instrument and song to yours.",
        "why": "The tools are more useful together than as separate apps.",
        "journey": [
            "🎷 Choose Clarinet",
            "🎵 Pick a song",
            "🔑 Move it to a comfortable Practice Key",
            "🎯 Work on one section",
            "🎧 Play it with Backing",
            "💬 Ask Music Coach what to improve",
            "🎙️ Record one take",
            "📓 Log the session",
        ],
        "cards": [
            {
                "icon": "🎵",
                "title": "Practice an existing song",
                "body": "Song Selection + Practice.",
                "tone": "picker",
            },
            {
                "icon": "✍️",
                "title": "Create my own progression",
                "body": "Custom Progression.",
                "tone": "custom",
            },
            {
                "icon": "🎧",
                "title": "Accompaniment",
                "body": "Backing Track.",
                "tone": "backing",
            },
            {
                "icon": "🎤",
                "title": "Sing with lyrics",
                "body": "Voice + Karaoke / Vocal Performance Mode.",
                "tone": "voice",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Jam Session Generator"],
                "title": "Generated jam",
                "body": "Creative Lab → Jam Session Generator.",
                "tone": "creative",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Missions"],
                "title": "Focused improv challenge",
                "body": "Creative Lab → Missions.",
                "tone": "practice",
            },
            {
                "icon": CREATIVE_TOOL_ICONS["Harmony Map"],
                "title": "Understand the progression",
                "body": "Harmony Map.",
                "tone": "log",
            },
            {
                "icon": "🎙️",
                "title": "Feedback on one take",
                "body": "Upload Analysis.",
                "tone": "analysis",
            },
            {
                "icon": "🎚️",
                "title": "Layer several recordings",
                "body": "Multitrack.",
                "tone": "multitrack",
            },
            {
                "icon": "📓",
                "title": "Remember what I practiced",
                "body": "Practice Log.",
                "tone": "log",
            },
            {
                "icon": "💬",
                "title": "Guidance",
                "body": "Music Coach.",
                "tone": "slate",
            },
            {
                "icon": "🎹",
                "title": "Write a fuller song idea",
                "body": "Composition Studio.",
                "tone": "creative",
            },
        ],
        "bullets": [],
        "action_label": "",
        "sections": [],
    },
]

TOTAL_STEPS = len(TUTORIAL_STEPS)
QUICK_TOUR_IDS: tuple[str, ...] = (
    "welcome",
    "setup",
    "music",
    "keys",
    "practice",
    "backing",
    "coach",
    "log",
)
EXPLORE_MORE_IDS: tuple[str, ...] = (
    "karaoke",
    "creative",
    "composer",
    "recording",
    "saving",
    "which_tool",
)
QUICK_TOUR_END_INDEX = len(QUICK_TOUR_IDS) - 1
EXPLORE_START_INDEX = len(QUICK_TOUR_IDS)
EXPLORE_MORE_CTA = "See Karaoke, Creative & more →"


def init_tutorial_state(session_state: dict) -> None:
    session_state.setdefault(TUTORIAL_DISMISSED_KEY, False)
    session_state.setdefault(TUTORIAL_OPEN_KEY, False)
    session_state.setdefault(TUTORIAL_STEP_KEY, 0)


def tutorial_entry_visible(session_state: dict) -> bool:
    """Top Tutorial button — hidden after finish or opt-out."""
    return not bool(session_state.get(TUTORIAL_DISMISSED_KEY))


def open_tutorial(session_state: dict, *, reset_step: bool = False) -> None:
    """Open tutorial; by default resumes the last step."""
    session_state[TUTORIAL_OPEN_KEY] = True
    if reset_step:
        session_state[TUTORIAL_STEP_KEY] = 0
    else:
        session_state[TUTORIAL_STEP_KEY] = _clamp_step(
            session_state.get(TUTORIAL_STEP_KEY, 0)
        )


def close_tutorial(session_state: dict) -> None:
    """Close panel but keep the top Tutorial button available."""
    session_state[TUTORIAL_OPEN_KEY] = False


def complete_tutorial(session_state: dict) -> None:
    """Finish or opt out — no auto-start, hide top Tutorial button."""
    session_state[TUTORIAL_DISMISSED_KEY] = True
    session_state[TUTORIAL_OPEN_KEY] = False


def _clamp_step(step: int) -> int:
    return max(0, min(int(step), TOTAL_STEPS - 1))


def step_index_for_page(page_id: str) -> int | None:
    """Map a studio page to a tutorial chapter (first matching chapter wins)."""
    pid = str(page_id or "").strip()
    if not pid:
        return None
    for i, step in enumerate(TUTORIAL_STEPS):
        if step.get("page_id") == pid:
            return i
    return None


def tutorial_nav_page_ids() -> list[str]:
    """Page ids used by action buttons — for tests."""
    return [
        str(s.get("page_id") or "")
        for s in TUTORIAL_STEPS
        if str(s.get("page_id") or "").strip()
    ]


def tutorial_chapter_ids() -> list[str]:
    return [str(s.get("id") or "") for s in TUTORIAL_STEPS]


def apply_tutorial_voice_instrument(session_state: dict) -> None:
    """Queue Voice for the next pre-widget hydrate — never write widget keys here.

    Tutorial CTAs run after the Instrument selectbox exists. Direct
    ``session_state["instrument"] = ...`` would raise StreamlitAPIException.
    """
    from practice_setup_controls import focus_options_for_instrument
    from session_widget_safe import safe_session_assign

    # Tutorial always renders after sidebar widgets. Force the pending path
    # even if the lock flag was somehow missing.
    session_state["_streamlit_widgets_locked_this_run"] = True

    current = str(session_state.get("instrument") or "").strip()
    if current != "Voice":
        safe_session_assign(session_state, "instrument", "Voice")

    focus_opts = focus_options_for_instrument("Voice")
    current_focus = str(session_state.get("focus") or "").strip()
    if focus_opts and current_focus not in focus_opts:
        safe_session_assign(session_state, "focus", focus_opts[0])

    try:
        from active_song_state import mark_active_song_local_edit

        mark_active_song_local_edit(session_state)
    except Exception:
        pass


def _esc(text: Any) -> str:
    return html.escape(str(text or ""), quote=False)


def _inline_md(text: Any) -> str:
    escaped = html.escape(str(text or ""), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _cards_html(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    parts = ['<div class="tutorial-card-grid">']
    for card in cards:
        tone = html.escape(str(card.get("tone") or "slate"))
        icon = _esc(card.get("icon") or "")
        title = _esc(card.get("title") or "")
        body_html = _inline_md(card.get("body") or "")
        parts.append(
            f'<div class="tutorial-mini-card tone-{tone}">'
            f'<p class="tutorial-mini-icon">{icon}</p>'
            f'<p class="tutorial-mini-title">{title}</p>'
            f'<p class="tutorial-mini-body">{body_html}</p>'
            f"</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _try_this_html(text: str) -> str:
    if not text:
        return ""
    return (
        f'<div class="tutorial-try">'
        f'<p class="tutorial-try-kicker">Try this</p>'
        f'<p class="tutorial-try-body">{_esc(text)}</p>'
        f"</div>"
    )


def _why_html(text: str) -> str:
    if not text:
        return ""
    return (
        f'<div class="tutorial-why">'
        f'<p class="tutorial-why-kicker">Why it helps</p>'
        f'<p class="tutorial-why-body">{_esc(text)}</p>'
        f"</div>"
    )


def _questions_html(questions: list[str]) -> str:
    if not questions:
        return ""
    parts = ['<div class="tutorial-bubbles">']
    for q in questions:
        parts.append(f'<p class="tutorial-bubble">“{_esc(q)}”</p>')
    parts.append("</div>")
    return "".join(parts)


def _journey_html(steps: list[str]) -> str:
    if not steps:
        return ""
    parts = ['<div class="tutorial-journey">']
    for i, item in enumerate(steps):
        parts.append(f'<div class="tutorial-journey-step">{_esc(item)}</div>')
        if i < len(steps) - 1:
            parts.append('<div class="tutorial-journey-arrow" aria-hidden="true">↓</div>')
    parts.append("</div>")
    return "".join(parts)


def _progress_label(step: int, data: dict[str, Any]) -> tuple[str, int]:
    """Return (label, percent 0-100) for the current layer."""
    layer = str(data.get("layer") or "")
    if layer == "welcome":
        return "Welcome", 8
    if layer == "quick":
        quick_i = step  # welcome is 0; setup is 1 of 7
        return f"Quick tour · {quick_i} of {QUICK_TOUR_END_INDEX}", int(
            quick_i / QUICK_TOUR_END_INDEX * 100
        )
    explore_i = step - EXPLORE_START_INDEX + 1
    explore_n = len(EXPLORE_MORE_IDS)
    return f"Explore more · {explore_i} of {explore_n}", int(explore_i / explore_n * 100)


def render_tutorial_walkthrough(
    st_module: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
    navigate_fn: Callable[[str], None] | None = None,
) -> None:
    """Friendly tour panel (shown above page content when tutorial_open is True)."""
    step = _clamp_step(session_state.get(TUTORIAL_STEP_KEY, 0))
    data = TUTORIAL_STEPS[step]
    progress_label, progress_pct = _progress_label(step, data)
    icon = _esc(data.get("icon") or "🎵")
    script = _esc(data.get("script") or "Tutorial")
    title = _esc(data.get("title") or "")
    summary = _esc(data.get("summary") or "")
    layer = str(data.get("layer") or "")

    st_module.markdown(
        f"""
<div class="tutorial-hero layer-{html.escape(layer or 'quick')}">
  <div class="tutorial-hero-head">
    <span class="tutorial-hero-icon">{icon}</span>
    <div>
      <p class="tutorial-kicker">{_esc(progress_label)}</p>
      <p class="tutorial-script">{script}</p>
      <h2 class="tutorial-title">{title}</h2>
      <p class="tutorial-sub">{summary}</p>
    </div>
  </div>
  <div class="tutorial-progress-track" aria-hidden="true">
    <div class="tutorial-progress-fill" style="width:{progress_pct}%;"></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    try_html = _try_this_html(str(data.get("try_this") or ""))
    if try_html:
        st_module.markdown(try_html, unsafe_allow_html=True)

    cards_html = _cards_html(list(data.get("cards") or []))
    if cards_html:
        st_module.markdown(cards_html, unsafe_allow_html=True)

    questions_html = _questions_html(list(data.get("questions") or []))
    if questions_html:
        st_module.markdown(questions_html, unsafe_allow_html=True)

    journey_html = _journey_html(list(data.get("journey") or []))
    if journey_html:
        st_module.markdown(journey_html, unsafe_allow_html=True)

    for bullet in (data.get("bullets") or [])[:4]:
        st_module.markdown(f"- {bullet}")

    why_html = _why_html(str(data.get("why") or ""))
    if why_html:
        st_module.markdown(why_html, unsafe_allow_html=True)

    if step == QUICK_TOUR_END_INDEX:
        st_module.markdown(
            "You’ve got the basics. **Next** continues into Karaoke, Creative Lab, "
            "recording, and coming back later."
        )

    for section in data.get("sections") or []:
        with st_module.expander(str(section.get("title") or "Learn more"), expanded=False):
            for bullet in section.get("bullets") or []:
                st_module.markdown(f"- {bullet}")

    with st_module.expander("Jump around", expanded=False):
        st_module.caption("Quick tour")
        for i, ch in enumerate(TUTORIAL_STEPS[:EXPLORE_START_INDEX]):
            mark = "→ " if i == step else ""
            st_module.markdown(f"{mark}**{ch.get('script')}** — {ch.get('title')}")
            if st_module.button(
                str(ch.get("script") or f"Step {i + 1}"),
                key=f"tutorial_jump_{i}",
                use_container_width=True,
            ):
                session_state[TUTORIAL_STEP_KEY] = i
                rerun_fn()
        st_module.caption("Explore more")
        for i, ch in enumerate(TUTORIAL_STEPS[EXPLORE_START_INDEX:], start=EXPLORE_START_INDEX):
            mark = "→ " if i == step else ""
            st_module.markdown(f"{mark}**{ch.get('script')}** — {ch.get('title')}")
            if st_module.button(
                str(ch.get("script") or f"Step {i + 1}"),
                key=f"tutorial_jump_{i}",
                use_container_width=True,
            ):
                session_state[TUTORIAL_STEP_KEY] = i
                rerun_fn()

    if layer == "welcome":
        go, skip = st_module.columns([2, 1])
        with go:
            if st_module.button(
                "Start the tour →",
                key="tutorial_next",
                type="primary",
                use_container_width=True,
            ):
                session_state[TUTORIAL_STEP_KEY] = 1
                rerun_fn()
        with skip:
            if st_module.button(
                "Explore on my own",
                key="tutorial_close",
                use_container_width=True,
            ):
                close_tutorial(session_state)
                rerun_fn()
        more = st_module.columns(1)[0]
        with more:
            if st_module.button(
                "Skip tour",
                key="tutorial_finish",
                use_container_width=True,
            ):
                complete_tutorial(session_state)
                rerun_fn()
        return

    nav1, nav2, nav3 = st_module.columns([1, 1, 1])
    with nav1:
        if st_module.button(
            "← Back",
            key="tutorial_back",
            disabled=step <= 0,
            use_container_width=True,
        ):
            session_state[TUTORIAL_STEP_KEY] = step - 1
            rerun_fn()
    with nav2:
        if step == QUICK_TOUR_END_INDEX:
            next_label = EXPLORE_MORE_CTA
        elif step >= TOTAL_STEPS - 1:
            next_label = "Finish tour ✓"
        else:
            next_label = "Next →"
        if st_module.button(
            next_label,
            key="tutorial_next",
            type="primary",
            use_container_width=True,
        ):
            if step >= TOTAL_STEPS - 1:
                complete_tutorial(session_state)
            else:
                session_state[TUTORIAL_STEP_KEY] = step + 1
            rerun_fn()
    with nav3:
        page_id = str(data.get("page_id") or "").strip()
        open_label = str(data.get("action_label") or "").strip() or "Open this page →"
        if page_id and page_id in _VALID_NAV_PAGE_IDS and navigate_fn and open_label:
            if st_module.button(open_label, key="tutorial_go_page", use_container_width=True):
                if str(data.get("action_prep") or "") == "voice_instrument":
                    apply_tutorial_voice_instrument(session_state)
                idx = step_index_for_page(page_id)
                if idx is not None:
                    session_state[TUTORIAL_STEP_KEY] = idx
                session_state[TUTORIAL_OPEN_KEY] = False
                navigate_fn(page_id)
        elif not page_id:
            if st_module.button(
                "Explore on my own",
                key="tutorial_go_page",
                use_container_width=True,
            ):
                close_tutorial(session_state)
                rerun_fn()
        else:
            st_module.button(
                open_label,
                key="tutorial_go_page",
                disabled=True,
                use_container_width=True,
            )

    foot1, foot2, foot3 = st_module.columns([1, 1, 1])
    with foot1:
        if step >= EXPLORE_START_INDEX and st_module.button(
            "← Back to quick tour",
            key="tutorial_jump_explore",
            use_container_width=True,
        ):
            session_state[TUTORIAL_STEP_KEY] = 1
            rerun_fn()
    with foot2:
        if st_module.button("Explore on my own", key="tutorial_close", use_container_width=True):
            close_tutorial(session_state)
            rerun_fn()
    with foot3:
        if st_module.button("Skip tour", key="tutorial_finish", use_container_width=True):
            complete_tutorial(session_state)
            rerun_fn()

    st_module.caption(
        "Jump into a real page anytime. Your place in the tour is saved if you come back."
    )
