"""Helpers for catalog songs tagged as vocal-showcase repertoire."""

from __future__ import annotations

from typing import Any


_VOCAL_SHOWCASE_TAG_HINTS = (
    "vocal showcase",
    "female vocal showcase",
    "ensemble vocal",
    "musical theatre",
    "broadway",
    "disney",
    "inspirational ballad",
    "piano ballad",
    "storytelling song",
    "karaoke friendly",
)

_DISNEY_PRINCESS_BALLAD_TITLES = (
    "how far i'll go",
    "how far ill go",
    "let it go",
    "part of your world",
    "reflection",
)


def is_vocal_showcase(song_data: dict[str, Any] | None) -> bool:
    """True when the song is tagged for singer-first practice workflows."""
    if not song_data:
        return False
    ext = song_data.get("extensions") or {}
    if ext.get("vocal_showcase") or ext.get("broadway_disney") or ext.get("disney_ballad"):
        return True
    if ext.get("piano_centric"):
        return True
    tags = [str(t).strip().lower() for t in (ext.get("repertoire_tags") or [])]
    return any(any(hint in tag for hint in _VOCAL_SHOWCASE_TAG_HINTS) for tag in tags)


def vocal_showcase_harmony_blurb(song_data: dict[str, Any] | None) -> str:
    """Short harmony note for practice UI (empty when not applicable)."""
    if not is_vocal_showcase(song_data):
        return ""
    ext = song_data.get("extensions") or {}
    hints = ext.get("vocal_harmony_hints")
    if isinstance(hints, str) and hints.strip():
        return hints.strip()
    if isinstance(hints, dict):
        parts = [f"**{k}:** {v}" for k, v in hints.items() if k and v]
        return " ".join(parts)
    call_resp = ext.get("call_and_response")
    if isinstance(call_resp, dict) and call_resp:
        cr = " ".join(f"**{k}:** {v}" for k, v in call_resp.items() if k and v)
        if cr:
            return cr
    title = str(song_data.get("title") or "").lower()
    if "all of me" in title and ext.get("piano_centric"):
        return (
            "Piano wedding ballad: conversational verses, open vowels on the "
            "title hook, and breath before each **C/D → D** lift. Final chorus "
            "is the peak — save your warmest mix voice for 'all of me'."
        )
    if "heal the world" in title:
        return (
            "Inspirational anthem: warm verse storytelling, open vowels on the "
            "title hook, and choir-style blend in the chorus. Final chorus is the "
            "peak — breathe before each 'heal the world' entrance."
        )
    if ext.get("disney_ballad") or any(t in title for t in _DISNEY_PRINCESS_BALLAD_TITLES):
        return (
            "Disney ballad: prioritize storytelling, breath before long phrases, "
            "and emotional arc through the key change — save your widest tone for "
            "the final chorus and ending descent."
        )
    return (
        "Focus on blend and breath before the chorus lift; "
        "harmony parts sit above the melody on the title hook."
    )


__all__ = ["is_vocal_showcase", "vocal_showcase_harmony_blurb"]
