"""Curated song-specific performance coaching — masterclass lesson API.

Profiles live in ``song_performance_profiles`` as private-lesson notes.
Generic templates in ``musician_coaching`` remain the fallback for non-flagship songs.

**Framework frozen 2026-07-29** — see ``cursor-prompts/plans/2026-07-29-flagship-coaching-quality-standard.md``.
Future progress-aware adaptation will layer on top; do not redesign this module for that.
"""

from __future__ import annotations

from typing import Any

from song_coaching import _instrument_key, _norm_title
from song_performance_profiles import CURATED_PERFORMANCE

LevelTips = dict[str, str]
LevelBlock = dict[str, LevelTips]
SectionBlock = dict[str, LevelBlock]
PerformanceProfile = dict[str, Any]


def _level_key(level: str) -> str:
    low = (level or "Intermediate").strip().lower()
    if low.startswith("beg"):
        return "Beginner"
    if low.startswith("adv"):
        return "Advanced"
    return "Intermediate"


def _pick_level_block(block: LevelBlock | None, level: str) -> LevelTips:
    if not block:
        return {}
    lk = _level_key(level)
    return dict(block.get(lk) or block.get("Intermediate") or block.get("Beginner") or {})


def _pick_instrument_text(tips: LevelTips, instrument: str) -> str:
    if not tips:
        return ""
    key = _instrument_key(instrument)
    return str(tips.get(key) or tips.get("general") or "").strip()


def _adapt_key_text(
    text: str,
    *,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    if not text or not catalog_key or not practice_key:
        return text
    try:
        from musician_coaching import adapt_text_to_practice_key

        return adapt_text_to_practice_key(
            text, catalog_key=catalog_key, practice_key=practice_key
        )
    except Exception:
        return text


def _section_role_key(section_name: str) -> str:
    low = str(section_name or "").lower()
    if "chorus" in low and "pre" not in low:
        return "_role:chorus"
    if "pre" in low and "chorus" in low:
        return "_role:pre"
    if "verse" in low:
        return "_role:verse"
    if "bridge" in low:
        return "_role:bridge"
    if "instrumental" in low or "solo" in low:
        return "_role:instrumental"
    if "intro" in low:
        return "_role:intro"
    if "outro" in low or "ending" in low:
        return "_role:outro"
    return "_role:neutral"


def lookup_performance_profile(
    title: str,
    artist: str | None = None,
) -> PerformanceProfile | None:
    key = _norm_title(title)
    profile = CURATED_PERFORMANCE.get(key)
    if profile:
        return dict(profile)
    return None


def has_curated_performance(title: str) -> bool:
    return _norm_title(title) in CURATED_PERFORMANCE


def _interpretation(title: str, artist: str | None = None) -> dict[str, str]:
    profile = lookup_performance_profile(title, artist)
    if not profile:
        return {}
    raw = profile.get("interpretation") or {}
    return {str(k): str(v).strip() for k, v in raw.items() if v}


def _lesson_block(
    title: str,
    *,
    instrument: str,
    level: str,
    artist: str | None = None,
) -> dict[str, Any]:
    profile = lookup_performance_profile(title, artist)
    if not profile:
        return {}
    lessons: dict[str, LevelBlock] = profile.get("lessons") or {}
    by_level = lessons.get(_level_key(level)) or lessons.get("Intermediate") or {}
    inst_key = _instrument_key(instrument)
    block = by_level.get(inst_key) or by_level.get("general")
    if not block and by_level:
        block = next(iter(by_level.values()), None)
    return dict(block) if isinstance(block, dict) else {}


def teacher_intro_for_song(
    title: str,
    *,
    instrument: str,
    level: str,
    artist: str | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    lesson = _lesson_block(title, instrument=instrument, level=level, artist=artist)
    opening = str(lesson.get("opening") or "").strip()
    if opening:
        return _adapt_key_text(
            opening, catalog_key=catalog_key, practice_key=practice_key
        )
    profile = lookup_performance_profile(title, artist)
    if not profile:
        return ""
    legacy = _pick_level_block(profile.get("teacher_intro"), level)
    return _adapt_key_text(
        _pick_instrument_text(legacy, instrument),
        catalog_key=catalog_key,
        practice_key=practice_key,
    )


def practice_focus_for_song(
    title: str,
    *,
    instrument: str,
    level: str,
    artist: str | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    profile = lookup_performance_profile(title, artist)
    if not profile:
        return ""
    block = _pick_level_block(profile.get("practice_focus"), level)
    text = _pick_instrument_text(block, instrument)
    if text:
        return _adapt_key_text(text, catalog_key=catalog_key, practice_key=practice_key)
    if block.get("general"):
        return _adapt_key_text(
            str(block["general"]).strip(),
            catalog_key=catalog_key,
            practice_key=practice_key,
        )
    interp = _interpretation(title, artist)
    parts = [
        interp.get("emotional_character", "")[:60],
        interp.get("master_challenge", "")[:60],
    ]
    parts = [p for p in parts if p]
    joined = " · ".join(parts)[:120] if parts else ""
    return _adapt_key_text(joined, catalog_key=catalog_key, practice_key=practice_key)


def _journey_entry_for_section(
    lesson: dict[str, Any],
    section_name: str,
) -> dict[str, str] | None:
    journey = lesson.get("journey") or []
    sec_low = str(section_name or "").strip().lower()
    for step in journey:
        if str(step.get("section") or "").strip().lower() == sec_low:
            return step
    role = _section_role_key(section_name)
    for step in journey:
        if str(step.get("role") or "") == role:
            return step
    for step in journey:
        if str(step.get("role") or "") == "_role:neutral":
            return step
    return None


def _lesson_block_with_fallback(
    title: str,
    *,
    instrument: str,
    level: str,
    artist: str | None = None,
) -> dict[str, Any]:
    """Return the lesson block for this level — no cross-level prose merge."""
    return _lesson_block(title, instrument=instrument, level=level, artist=artist)


def section_coaching_for_song(
    title: str,
    *,
    section_name: str,
    instrument: str,
    level: str,
    artist: str | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    lesson = _lesson_block_with_fallback(title, instrument=instrument, level=level, artist=artist)
    if lesson:
        step = _journey_entry_for_section(lesson, section_name)
        if step:
            body = str(step.get("body") or "").strip()
            if body:
                return _adapt_key_text(
                    body, catalog_key=catalog_key, practice_key=practice_key
                )
    profile = lookup_performance_profile(title, artist)
    if not profile:
        return ""
    sections: SectionBlock = profile.get("sections") or {}
    sec_key = None
    for name in sections:
        if not name.startswith("_role:") and name.lower() == section_name.lower():
            sec_key = name
            break
    role_key = _section_role_key(section_name)
    block = sections.get(sec_key) if sec_key else sections.get(role_key)
    if not block and sec_key:
        block = sections.get(role_key)
    tips = _pick_level_block(block, level)
    return _adapt_key_text(
        _pick_instrument_text(tips, instrument),
        catalog_key=catalog_key,
        practice_key=practice_key,
    )


def section_lesson_heading(
    title: str,
    *,
    section_name: str,
    instrument: str,
    level: str,
    artist: str | None = None,
) -> str:
    lesson = _lesson_block_with_fallback(title, instrument=instrument, level=level, artist=artist)
    if not lesson:
        return ""
    step = _journey_entry_for_section(lesson, section_name)
    if not step:
        return ""
    return str(step.get("heading") or "").strip()


def harmony_tip_for_song(
    title: str,
    section_name: str,
    *,
    artist: str | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    profile = lookup_performance_profile(title, artist)
    if not profile:
        return ""
    tips: dict[str, str] = profile.get("harmony_tips") or {}
    if section_name in tips:
        return _adapt_key_text(
            str(tips[section_name]).strip(),
            catalog_key=catalog_key,
            practice_key=practice_key,
        )
    role = _section_role_key(section_name)
    return _adapt_key_text(
        str(tips.get(role) or "").strip(),
        catalog_key=catalog_key,
        practice_key=practice_key,
    )


def song_mood_summary(title: str, *, artist: str | None = None) -> str:
    interp = _interpretation(title, artist)
    if not interp:
        return ""
    parts = [
        interp.get("emotional_character", ""),
        interp.get("listen_for", ""),
    ]
    return " ".join(p for p in parts if p).strip()


def song_challenge(title: str, *, artist: str | None = None) -> str:
    interp = _interpretation(title, artist)
    return interp.get("master_challenge") or interp.get("challenge") or ""


def challenge_blurb_for_song(
    title: str,
    *,
    instrument: str = "",
    level: str = "Intermediate",
    artist: str | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    """Short performance challenge for cards — one teacher sentence."""
    lesson = _lesson_block(title, instrument=instrument, level=level, artist=artist)
    card = str(lesson.get("challenge_summary") or "").strip()
    if card:
        return _adapt_key_text(card, catalog_key=catalog_key, practice_key=practice_key)
    raw = song_challenge(title, artist=artist)
    if not raw:
        return ""
    first = raw.split(".")[0].strip()
    if first and not first.endswith("."):
        first += "."
    return _adapt_key_text(first, catalog_key=catalog_key, practice_key=practice_key)


def harmony_blurb_for_song(
    title: str,
    *,
    instrument: str = "",
    level: str = "Intermediate",
    artist: str | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    """Short harmony/listening line for cards."""
    lesson = _lesson_block(title, instrument=instrument, level=level, artist=artist)
    card = str(lesson.get("harmony_summary") or "").strip()
    if card:
        return _adapt_key_text(card, catalog_key=catalog_key, practice_key=practice_key)
    interp = _interpretation(title, artist)
    listen = str(interp.get("listen_for") or "").strip()
    if listen:
        first = listen.split(".")[0].strip()
        if first and not first.endswith("."):
            first += "."
        return _adapt_key_text(first, catalog_key=catalog_key, practice_key=practice_key)
    profile = lookup_performance_profile(title, artist)
    if not profile:
        return ""
    tips: dict[str, str] = profile.get("harmony_tips") or {}
    for key in (ROLE_VERSE, ROLE_INTRO, ROLE_OUTRO):
        if tips.get(key):
            line = str(tips[key]).split(".")[0].strip() + "."
            return _adapt_key_text(line, catalog_key=catalog_key, practice_key=practice_key)
    return ""


def _interpretation_woven_prose(interp: dict[str, str]) -> str:
    """Flowing lesson prose from interpretation fields — not a checklist."""
    if not interp:
        return ""
    sentences: list[str] = []

    char = str(interp.get("emotional_character") or "").strip()
    if char:
        sentences.append(char.rstrip(".") + ".")

    listen = str(interp.get("listen_for") or "").strip()
    if listen:
        low = listen.lower()
        if low.startswith(("listen", "watch", "hear", "the ")):
            sentences.append(listen.rstrip(".") + ".")
        else:
            sentences.append(f"Listen for {listen[0].lower()}{listen[1:].rstrip('.') + '.'}")

    accomp = str(interp.get("accompaniment") or "").strip()
    if accomp:
        sentences.append(accomp.rstrip(".") + ".")

    build = str(interp.get("build_where") or "").strip()
    relax = str(interp.get("relax_where") or "").strip()
    if build and relax:
        b = build[0].lower() + build[1:] if build else build
        r = relax[0].lower() + relax[1:] if relax else relax
        if not b.lower().startswith(("let ", "build ", "allow ")):
            b = f"build intensity where {b.rstrip('.')}"
        if not r.lower().startswith(("stay ", "keep ", "verses")):
            r = f"stay soft where {r.rstrip('.')}"
        sentences.append(f"{b.rstrip('.')}, and {r.rstrip('.')}.")
    elif build:
        sentences.append(build.rstrip(".") + ".")
    elif relax:
        sentences.append(relax.rstrip(".") + ".")

    rush = str(interp.get("rush_prone") or "").strip()
    if rush:
        sentences.append(f"The section most players rush: {rush[0].lower()}{rush[1:].rstrip('.') + '.'}")

    trans = str(interp.get("key_transitions") or "").strip()
    if trans:
        sentences.append(f"Woodshed these transitions: {trans[0].lower()}{trans[1:].rstrip('.') + '.'}")

    challenge = str(interp.get("master_challenge") or "").strip()
    if challenge:
        sentences.append(f"The central performance challenge is this: {challenge[0].lower()}{challenge[1:].rstrip('.') + '.'}")

    return " ".join(sentences).strip()


def _interpretation_coach_prose(interp: dict[str, str]) -> str:
    """Short Coach-tab context — not the full interpretation essay."""
    if not interp:
        return ""
    parts: list[str] = []
    char = str(interp.get("emotional_character") or "").strip()
    if char:
        parts.append(char.rstrip(".") + ".")
    listen = str(interp.get("listen_for") or "").strip()
    if listen:
        parts.append(listen.rstrip(".") + ".")
    return " ".join(parts[:2]).strip()


def instructor_card_summary(
    title: str,
    *,
    instrument: str,
    level: str,
    artist: str | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    """Short pre-practice objective for Active Song card and chart subtitle (~20–40 sec)."""
    lesson = _lesson_block(title, instrument=instrument, level=level, artist=artist)
    card = str(lesson.get("card_summary") or "").strip()
    if card:
        return _adapt_key_text(card, catalog_key=catalog_key, practice_key=practice_key)
    return _adapt_key_text(
        str(lesson.get("opening") or "").strip(),
        catalog_key=catalog_key,
        practice_key=practice_key,
    )


def instructor_lesson_opener(
    title: str,
    *,
    instrument: str,
    level: str,
    artist: str | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    """Unified teacher voice for cards and summaries — brief, not a lesson transcript."""
    return instructor_card_summary(
        title,
        instrument=instrument,
        level=level,
        artist=artist,
        catalog_key=catalog_key,
        practice_key=practice_key,
    )


def masterclass_lesson_markdown(
    title: str,
    *,
    instrument: str,
    level: str,
    artist: str | None = None,
    sections: dict[str, list[str]] | None = None,
    catalog_key: str | None = None,
    practice_key: str | None = None,
) -> str:
    """Full masterclass narrative for the Coach tab."""
    lesson = _lesson_block_with_fallback(title, instrument=instrument, level=level, artist=artist)
    if not lesson:
        return ""
    interp = _interpretation(title, artist)
    lines: list[str] = ["#### Masterclass notes"]

    opening = str(lesson.get("opening") or "").strip()
    if opening:
        lines.append(opening)

    coach_ctx = str(lesson.get("coach_context") or "").strip()
    if not coach_ctx:
        coach_ctx = _interpretation_coach_prose(interp)
    if coach_ctx and coach_ctx not in opening:
        lines.append("")
        lines.append(coach_ctx)

    if sections:
        lines.append("")
        for sec_name in sections:
            step = _journey_entry_for_section(lesson, sec_name)
            if not step:
                continue
            heading = str(step.get("heading") or "").strip()
            body = str(step.get("body") or "").strip()
            if not body:
                continue
            label = heading or sec_name
            lines.append(f"\n**{label}** — {body}")
    else:
        journey = list(lesson.get("journey") or [])
        if journey:
            lines.append("")
            for step in journey:
                heading = str(step.get("heading") or "").strip()
                body = str(step.get("body") or "").strip()
                if not body:
                    continue
                if heading:
                    lines.append(f"\n**{heading}** — {body}")
                else:
                    lines.append(f"\n{body}")

    closing = str(lesson.get("closing") or "").strip()
    if closing:
        lines.append("")
        lines.append(f"**Before you leave the practice room** — {closing}")

    return _adapt_key_text(
        "\n".join(lines).strip(),
        catalog_key=catalog_key,
        practice_key=practice_key,
    )


def enrich_coaching_block(
    block: dict[str, str],
    record: dict[str, Any],
    *,
    instrument: str,
    level: str,
    practice_key: str | None = None,
) -> dict[str, str]:
    title = str(record.get("title") or "")
    artist = str(record.get("artist") or "")
    catalog_key = str(record.get("key") or "")
    profile = lookup_performance_profile(title, artist)
    if not profile:
        return block
    out = dict(block)
    opener = instructor_card_summary(
        title,
        instrument=instrument,
        level=level,
        artist=artist,
        catalog_key=catalog_key,
        practice_key=practice_key,
    )
    if opener:
        out["what_matters"] = opener
    intro = teacher_intro_for_song(
        title,
        instrument=instrument,
        level=level,
        artist=artist,
        catalog_key=catalog_key,
        practice_key=practice_key,
    )
    if intro:
        out["instrument_tip"] = intro
    elif opener:
        out["instrument_tip"] = opener
    challenge = song_challenge(title, artist=artist)
    if challenge:
        blurb = challenge_blurb_for_song(
            title,
            instrument=instrument,
            level=level,
            artist=artist,
            catalog_key=catalog_key,
            practice_key=practice_key,
        )
        out["biggest_challenge"] = blurb or _adapt_key_text(
            challenge, catalog_key=catalog_key, practice_key=practice_key
        )
    return out
