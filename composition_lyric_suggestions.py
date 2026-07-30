"""Rule-based lyric writing prompts for Composition Studio (CS-B4)."""

from __future__ import annotations

from typing import Any

LYRIC_SECTION_ROLES: tuple[tuple[str, str], ...] = (
    ("story", "Tell the story — what happened, what changed?"),
    ("question", "Ask a question — leave the listener wondering"),
    ("tension", "Create tension — something unresolved"),
    ("release", "Resolve tension — answer or emotional payoff"),
    ("message", "Deliver the main message — the line you want remembered"),
)

LYRIC_EMOTIONS: tuple[tuple[str, str], ...] = (
    ("hopeful", "Hopeful — light breaking through"),
    ("longing", "Longing — wanting what feels out of reach"),
    ("defiant", "Defiant — standing your ground"),
    ("tender", "Tender — vulnerable and intimate"),
    ("joyful", "Joyful — celebration and lift"),
    ("melancholy", "Melancholy — bittersweet reflection"),
)

DEFAULT_ROLE_BY_SECTION: dict[str, str] = {
    "Intro": "story",
    "Verse": "story",
    "Pre-Chorus": "tension",
    "Chorus": "message",
    "Bridge": "question",
    "Solo": "release",
    "Interlude": "release",
    "Outro": "release",
}

_PROMPT_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "story": [
        {
            "id": "story_scene",
            "name": "Paint a scene",
            "prompt": "Open with one concrete image — a place, a time of day, a small detail someone can see.",
            "why": "Specific images pull listeners into the world of the song before you explain anything.",
        },
        {
            "id": "story_moment",
            "name": "One moment that changed everything",
            "prompt": "Describe a single moment — before and after — in two short lines.",
            "why": "Verses land hardest when they zoom in on one turning point.",
        },
    ],
    "question": [
        {
            "id": "question_direct",
            "name": "Ask it outright",
            "prompt": "Write one honest question you'd ask the person (or yourself) at the center of this song.",
            "why": "A direct question invites the listener to lean in.",
        },
    ],
    "tension": [
        {
            "id": "tension_unsaid",
            "name": "What's left unsaid",
            "prompt": "Write what everyone in the room is thinking but no one says aloud.",
            "why": "Pre-choruses work when they name the elephant before the chorus explodes.",
        },
    ],
    "release": [
        {
            "id": "release_answer",
            "name": "The answer arrives",
            "prompt": "Give the emotional answer the song has been circling — even if it's not a neat happy ending.",
            "why": "Bridges and outros feel earned when they pay off setup from earlier sections.",
        },
    ],
    "message": [
        {
            "id": "message_hook",
            "name": "The line they'd quote",
            "prompt": "Write one line so plain and true that someone would tattoo it or text it to a friend.",
            "why": "Choruses live or die on one repeatable, believable truth.",
        },
        {
            "id": "message_title",
            "name": "Title as thesis",
            "prompt": "State the song's title idea as a feeling, not a label — what does it mean to you?",
            "why": "When the chorus *is* the title concept, the whole song clicks together.",
        },
    ],
}


def default_role_for_section(section: dict[str, Any]) -> str:
    label = str(section.get("label") or "Verse")
    return DEFAULT_ROLE_BY_SECTION.get(label, "story")


def collect_song_lyric_themes(doc: dict[str, Any]) -> list[str]:
    """Themes/images/emotions already introduced in earlier sections."""
    from composition_document import ordered_sections

    themes: list[str] = []
    meta = doc.get("metadata") or {}
    if meta.get("description"):
        themes.append(f"Song idea: {str(meta['description'])[:100]}")
    if meta.get("mood"):
        themes.append(f"Mood: {meta['mood']}")
    for sec in ordered_sections(doc):
        intent = (sec.get("lyrics") or {}).get("intent") or {}
        remember = str(intent.get("remember") or "").strip()
        if remember:
            variant = str(sec.get("label_variant") or sec.get("label") or "Section")
            themes.append(f"{variant}: {remember[:80]}")
        raw = str((sec.get("lyrics") or {}).get("raw_text") or "").strip()
        if raw:
            first_line = raw.splitlines()[0].strip()[:60]
            if first_line:
                variant = str(sec.get("label_variant") or sec.get("label") or "Section")
                themes.append(f"{variant} opens: “{first_line}”")
    return themes[:8]


_BRAINSTORM_SEEDS: dict[str, list[str]] = {
    "story": [
        "Start with where you are — one place, one time, one detail.",
        "Name the moment everything shifted, even in one line.",
        "Let the listener see through your eyes before you explain.",
    ],
    "question": [
        "Ask the question you've been afraid to say out loud.",
        "Turn the chorus hook into a question nobody can ignore.",
        "Leave one word unanswered — let the listener finish the thought.",
    ],
    "tension": [
        "Hold back the payoff — say what you're almost ready to admit.",
        "Stack two images that don't quite fit together yet.",
        "End on a line that feels one breath away from breaking.",
    ],
    "release": [
        "Name what finally became clear — even if it's messy.",
        "Let the melody's peak carry the word you've been circling.",
        "Answer the question you planted in an earlier section.",
    ],
    "message": [
        "Say the thesis in plain language — no poetry yet.",
        "Write the line you'd want shouted back at a show.",
        "Make the title idea feel inevitable, not clever.",
    ],
}

_EMOTION_TWEAKS: dict[str, str] = {
    "hopeful": "Let light leak in — even a small crack counts.",
    "longing": "Reach toward something just out of frame.",
    "defiant": "Stand your ground without shouting.",
    "tender": "Whisper the truth — vulnerability is strength here.",
    "joyful": "Let the lift feel earned, not forced.",
    "melancholy": "Hold beauty and ache in the same breath.",
}


def suggest_lyric_brainstorm_ideas(
    doc: dict[str, Any],
    section: dict[str, Any],
    role: str,
    *,
    emotion: str = "",
    communicate: str = "",
    remember: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    role = str(role or default_role_for_section(section)).strip().lower()
    seeds = list(_BRAINSTORM_SEEDS.get(role) or _BRAINSTORM_SEEDS["story"])
    if emotion and emotion in _EMOTION_TWEAKS:
        seeds = [f"{s} ({_EMOTION_TWEAKS[emotion]})" for s in seeds]
    if communicate.strip():
        seeds.insert(0, f"Focus on: {communicate.strip()[:80]}")
    if remember.strip():
        seeds.insert(0, f"Land on this idea: {remember.strip()[:80]}")

    out: list[dict[str, Any]] = []
    for i, seed in enumerate(seeds[:limit]):
        out.append(
            {
                "id": f"brainstorm_{role}_{i}",
                "name": f"Direction {i + 1}",
                "prompt": seed,
                "why": "A starting angle — borrow a phrase or let it spark your own line.",
                "role": role,
            }
        )
    return out


def suggest_lyric_prompts(
    doc: dict[str, Any],
    section: dict[str, Any],
    role: str,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    role = str(role or default_role_for_section(section)).strip().lower()
    recipes = list(_PROMPT_LIBRARY.get(role) or _PROMPT_LIBRARY["story"])
    if str(section.get("label") or "") == "Chorus":
        recipes = list(_PROMPT_LIBRARY.get("message", [])) + recipes

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for recipe in recipes:
        rid = str(recipe.get("id") or "")
        if rid in seen:
            continue
        seen.add(rid)
        out.append(
            {
                "id": rid,
                "name": str(recipe.get("name") or "Writing prompt"),
                "prompt": str(recipe.get("prompt") or ""),
                "why": str(recipe.get("why") or ""),
                "role": role,
            }
        )
        if len(out) >= limit:
            break
    return out


def coach_line_for_lyrics(
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    role: str = "",
    emotion: str = "",
    remember: str = "",
) -> str:
    variant = str(section.get("label_variant") or section.get("label") or "this section")
    themes = collect_song_lyric_themes(doc)
    theme_bit = ""
    if themes:
        joined = "; ".join(themes[:3])
        theme_bit = f"<br><br>So far in your song: {joined}. Keep the thread — echo an image or feeling you already planted."
    remember_bit = (
        f' You want them to remember: <em>"{remember[:120]}"</em>.'
        if remember.strip()
        else ""
    )
    return (
        f"For <strong>{variant}</strong>, start with what you're trying to say — not how to rhyme."
        f"{remember_bit}{theme_bit}<br><br>"
        f"Brainstorm, explore prompts, compare directions, then write. The editor is there when the idea is ready."
    )
